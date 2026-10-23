import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from .logger import TrafficLogger, default_logger

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSION_FILE = DATA_DIR / "session.json"
PROFILE_DIR = DATA_DIR / "chrome_profile"
INTERCEPTOR_PATH = Path(__file__).resolve().parent / "interceptor.js"


class DeepSeekBrowser:
    """Controls Chrome via Selenium to authenticate, intercept traffic, and save sessions."""

    def __init__(
        self,
        headless: bool = False,
        profile_dir: Optional[Path] = None,
        logger: Optional[TrafficLogger] = None,
    ):
        self.headless = headless
        self.profile_dir = Path(profile_dir) if profile_dir else PROFILE_DIR
        self.logger = logger or default_logger
        self.driver: Optional[webdriver.Chrome] = None
        self._monitoring_stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self.captured_auth: Dict[str, Any] = {}

    def start(self) -> webdriver.Chrome:
        """Launches Chrome with anti-detection and network interceptor injected."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")

        # Stealth and stability arguments
        options.add_argument(f"--user-data-dir={self.profile_dir.resolve()}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-first-run")
        options.add_argument("--no-service-autorun")
        options.add_argument("--password-store=basic")
        options.add_argument("--lang=ru,en-US,en")
        options.add_argument("--window-size=1280,900")

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Logging prefs
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

        print("[Browser] Launching Chrome...")
        self.driver = webdriver.Chrome(options=options)

        # CDP: remove navigator.webdriver flag
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
            },
        )

        # Inject our network interceptor
        if INTERCEPTOR_PATH.exists():
            with open(INTERCEPTOR_PATH, "r", encoding="utf-8") as f:
                interceptor_js = f.read()
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": interceptor_js},
            )
            print("[Browser] Network interceptor script injected via CDP.")

        return self.driver

    def open_deepseek(self):
        """Navigates to DeepSeek chat website."""
        if not self.driver:
            self.start()
        print("[Browser] Navigating to https://chat.deepseek.com/ ...")
        self.driver.get("https://chat.deepseek.com/")

    def _monitor_loop(self, print_traffic: bool = False):
        """Background thread loop to drain logs from browser window.__ds_logs."""
        while not self._monitoring_stop_event.is_set():
            try:
                if not self.driver:
                    break

                # 1. Drain network logs from in-page interceptor
                logs = self.driver.execute_script(
                    """
                    if (window.__ds_logs && window.__ds_logs.length > 0) {
                        return window.__ds_logs.splice(0, window.__ds_logs.length);
                    }
                    return [];
                """
                )

                if logs:
                    for entry in logs:
                        # Check if auth token is captured
                        self.logger.log(entry, print_to_console=print_traffic)

                # 2. Check captured auth object from browser
                auth = self.driver.execute_script(
                    """
                    return window.__ds_auth_captured || {};
                """
                )
                if auth and isinstance(auth, dict):
                    self.captured_auth.update(auth)

            except Exception:
                # Browser might be navigating or closing
                pass

            time.sleep(1.0)

    def start_traffic_monitor(self, print_traffic: bool = False):
        """Starts background traffic recording thread."""
        self._monitoring_stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(print_traffic,),
            daemon=True,
        )
        self._monitor_thread.start()
        print("[Browser] Traffic logger started.")

    def stop_traffic_monitor(self):
        """Stops background traffic recording."""
        self._monitoring_stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        print("[Browser] Traffic logger stopped.")

    def is_logged_in(self) -> bool:
        """Checks whether the user is logged into DeepSeek."""
        if not self.driver:
            return False
        try:
            # Check localStorage for userToken
            token = self.driver.execute_script(
                """
                try {
                    const ut = localStorage.getItem('userToken');
                    if (ut) return ut;
                    const ds = localStorage.getItem('ds_token');
                    if (ds) return ds;
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && key.toLowerCase().includes('token')) {
                            return localStorage.getItem(key);
                        }
                    }
                } catch(e) {}
                return null;
            """
            )
            if token:
                return True

            # Check if captured auth token exists
            if self.captured_auth.get("token"):
                return True

            # Check cookies
            cookies = self.driver.get_cookies()
            cookie_names = [c.get("name", "") for c in cookies]
            if "ds_session_id" in cookie_names or "userToken" in cookie_names:
                return True

            return False
        except Exception:
            return False

    def get_token(self) -> Optional[str]:
        """Retrieves user auth token from localStorage or intercepted headers."""
        if not self.driver:
            return None
        try:
            # Check localStorage
            token_raw = self.driver.execute_script(
                """
                try {
                    const ut = localStorage.getItem('userToken');
                    if (ut) {
                        try {
                            const parsed = JSON.parse(ut);
                            return parsed.value || parsed.token || ut;
                        } catch(e) {
                            return ut;
                        }
                    }
                } catch(e) {}
                return null;
            """
            )
            if token_raw:
                return str(token_raw).strip('"')

            if self.captured_auth.get("token"):
                return self.captured_auth["token"]

            return None
        except Exception:
            return None

    def save_session(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """Extracts cookies, tokens, localStorage, user-agent and saves to JSON."""
        target_path = Path(path) if path else SESSION_FILE
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.driver:
            raise RuntimeError("Browser is not running.")

        cookies = self.driver.get_cookies()
        user_agent = self.driver.execute_script("return navigator.userAgent;")
        local_storage = self.driver.execute_script(
            "try { return {...localStorage}; } catch(e) { return {}; }"
        )
        session_storage = self.driver.execute_script(
            "try { return {...sessionStorage}; } catch(e) { return {}; }"
        )
        token = self.get_token()

        session_data = {
            "token": token,
            "user_agent": user_agent,
            "cookies": cookies,
            "local_storage": local_storage,
            "session_storage": session_storage,
            "captured_headers": self.captured_auth,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        print(f"[Browser] Session successfully saved to {target_path}")
        print(f"[Browser] Token found: {'YES (' + token[:10] + '...)' if token else 'NO (relying on cookies)'}")
        print(f"[Browser] Cookies saved: {len(cookies)}")
        return session_data

    def wait_for_user_login(
        self,
        timeout_seconds: int = 300,
        interactive: bool = True,
    ) -> bool:
        """
        Waits until the user completes login in the browser.
        Can auto-detect or wait for user to press Enter.
        """
        print("\n" + "=" * 60)
        print(">>> ОЖИДАНИЕ АВТОРИЗАЦИИ В DEEPSEEK <<<")
        print("Пожалуйста, войдите в свой аккаунт в открывшемся окне Chrome.")
        print("Как только вы войдете, сессия и куки будут автоматически сохранены.")
        if interactive:
            print("Либо нажмите ENTER в этой консоли, если вы уже вошли.")
        print("=" * 60 + "\n")

        start_time = time.time()
        stop_wait = threading.Event()

        def user_input_thread():
            if interactive:
                try:
                    input("Нажмите ENTER после успешного входа: ")
                    stop_wait.set()
                except Exception:
                    pass

        t = threading.Thread(target=user_input_thread, daemon=True)
        t.start()

        while time.time() - start_time < timeout_seconds:
            if stop_wait.is_set():
                print("[Browser] Пользователь подтвердил вход.")
                break

            if self.is_logged_in():
                token = self.get_token()
                if token:
                    print("[Browser] Вход обнаружен автоматически (найден токен авторизации)!")
                    # Give it a moment to finish any follow-up requests/cookies
                    time.sleep(2)
                    break

            time.sleep(1.5)

        # Save session
        self.save_session()
        return True

    def close(self):
        """Stops monitor and closes Chrome."""
        self.stop_traffic_monitor()
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            print("[Browser] Browser closed.")
