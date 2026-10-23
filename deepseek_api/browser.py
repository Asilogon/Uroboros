import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchWindowException

from .logger import TrafficLogger, default_logger

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSION_FILE = DATA_DIR / "session.json"
PROFILE_DIR = DATA_DIR / "chrome_profile"


def find_chrome_executable() -> Optional[Path]:
    """Finds the real installed Google Chrome executable on Windows."""
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
    ]
    for p in candidates:
        if p.exists():
            return p
    which_chrome = shutil.which("chrome")
    if which_chrome:
        return Path(which_chrome)
    return None


def get_free_port() -> int:
    """Finds an available TCP port for remote debugging."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def kill_stale_uroboros_chrome():
    """Kills any previous Chrome process that was using the Uroboros profile directory."""
    try:
        cmd = 'Get-CimInstance Win32_Process -Filter "Name = \'chrome.exe\'" | Where-Object { $_.CommandLine -like "*Uroboros*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }'
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=5)
    except Exception:
        pass


class DeepSeekBrowser:
    """
    Launches genuine Google Chrome as a standalone desktop application
    with remote debugging and connects Selenium to it.
    Zero automation flags or script injections that could trigger captcha failures.
    """

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
        self.process: Optional[subprocess.Popen] = None
        self.debug_port: Optional[int] = None
        self._monitoring_stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self.last_saved_session: Optional[Dict[str, Any]] = None

    def reset_profile(self):
        """Clears the Chrome profile directory to reset failed captcha attempt history."""
        kill_stale_uroboros_chrome()
        time.sleep(0.5)
        if self.profile_dir.exists():
            try:
                shutil.rmtree(self.profile_dir, ignore_errors=True)
                print("[Browser] Profile directory reset successfully.")
            except Exception as e:
                print(f"[Browser Warning] Failed resetting profile: {e}")

    def start(self) -> webdriver.Chrome:
        """
        Launches real Google Chrome as a genuine OS process (no ChromeDriver wrapper),
        then attaches Selenium to it.
        """
        kill_stale_uroboros_chrome()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        chrome_exe = find_chrome_executable()

        if not chrome_exe or not chrome_exe.exists():
            raise FileNotFoundError("Google Chrome executable not found on system.")

        self.debug_port = get_free_port()
        target_url = "https://chat.deepseek.com/"

        # Launch real Chrome directly as a normal desktop application
        cmd = [
            str(chrome_exe),
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={self.profile_dir.resolve()}",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-service-autorun",
            "--password-store=basic",
            "--lang=ru,en",
            "--window-size=1360,920",
            target_url,
        ]

        if self.headless:
            cmd.append("--headless=new")

        print(f"[Browser] Launching genuine Chrome on port {self.debug_port}...")
        self.process = subprocess.Popen(cmd)

        # Wait until Chrome debugging endpoint is responsive
        ready = False
        for _ in range(30):
            try:
                r = requests.get(f"http://127.0.0.1:{self.debug_port}/json/version", timeout=1)
                if r.status_code == 200:
                    ready = True
                    break
            except Exception:
                time.sleep(0.3)

        if not ready:
            raise RuntimeError(f"Chrome failed to start on port {self.debug_port}")

        # Connect Selenium via debuggerAddress
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.debug_port}")

        print("[Browser] Attaching Selenium to genuine Chrome instance...")
        self.driver = webdriver.Chrome(options=options)
        print("[Browser] Connected successfully! 100% genuine Chrome session.")

        return self.driver

    def open_deepseek(self):
        """Navigates to DeepSeek chat website if not already there."""
        if not self.driver:
            self.start()
        else:
            try:
                if "deepseek.com" not in self.driver.current_url:
                    self.driver.get("https://chat.deepseek.com/")
            except Exception:
                pass

    def _monitor_loop(self, print_traffic: bool = False):
        """Background thread loop to continuously sync cookies, tokens and localStorage."""
        while not self._monitoring_stop_event.is_set():
            try:
                if not self.driver or (self.process and self.process.poll() is not None):
                    break

                self.save_session()
            except Exception:
                pass

            time.sleep(2.0)

    def start_traffic_monitor(self, print_traffic: bool = False):
        """Starts background session sync thread."""
        self._monitoring_stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(print_traffic,),
            daemon=True,
        )
        self._monitor_thread.start()

    def stop_traffic_monitor(self):
        """Stops background session sync."""
        self._monitoring_stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)

    def get_token(self) -> Optional[str]:
        """Retrieves user auth token from localStorage."""
        if not self.driver:
            return None
        try:
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
            if token_raw:
                return str(token_raw).strip('"')
            return None
        except Exception:
            return None

    def save_session(self, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Extracts cookies, tokens, localStorage, user-agent and saves to JSON."""
        target_path = Path(path) if path else SESSION_FILE
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.driver:
            return self.last_saved_session

        try:
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
                "captured_headers": {},
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            self.last_saved_session = session_data
            return session_data
        except Exception as e:
            return self.last_saved_session

    def wait_until_closed_by_user(self):
        """
        Keeps the browser open and continuously captures cookies and tokens.
        Does NOT close the browser automatically.
        Waits until the user manually closes the Chrome browser window.
        """
        print("\n" + "=" * 65)
        print(">>> БРАУЗЕР ОТКРЫТ (НАСТОЯЩИЙ CHROME БЕЗ АВТОМАТИЗАЦИИ) <<<")
        print("Выполните вход в открывшемся окне Chrome. Капча пройдет успешно.")
        print("Окно НЕ закроется само — работайте в нем столько, сколько потребуется.")
        print("Когда вы решите закончить — просто закройте окно Chrome (крестиком).")
        print("=" * 65 + "\n")

        while True:
            try:
                if self.process and self.process.poll() is not None:
                    print("[Browser] Процесс Chrome завершен пользователем.")
                    break

                if not self.driver:
                    break

                handles = self.driver.window_handles
                if not handles or len(handles) == 0:
                    print("[Browser] Все вкладки Chrome закрыты.")
                    break

                # Continuous background save of session data
                self.save_session()
                time.sleep(2.0)

            except (WebDriverException, NoSuchWindowException):
                print("[Browser] Обнаружено закрытие окна Chrome пользователем.")
                break
            except Exception:
                time.sleep(1.0)

        # Final save
        self.stop_traffic_monitor()
        self.driver = None
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.process = None
        print("[Browser] Сессия успешно сохранена в data/session.json.")

    def close(self):
        """Stops monitor and closes Chrome."""
        self.stop_traffic_monitor()
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None
        kill_stale_uroboros_chrome()
        print("[Browser] Browser closed.")
