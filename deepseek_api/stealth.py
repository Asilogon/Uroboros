import os
import re
import shutil
from pathlib import Path
from typing import Optional

from selenium import webdriver

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DRIVER_DIR = DATA_DIR / "driver"
PATCHED_CHROMEDRIVER = DRIVER_DIR / "chromedriver.exe"


def find_system_chromedriver() -> Optional[Path]:
    """Finds chromedriver downloaded by Selenium Manager in user cache or system PATH."""
    user_cache = Path(os.path.expandvars(r"%USERPROFILE%\.cache\selenium\chromedriver\win64"))
    if user_cache.exists():
        drivers = list(user_cache.glob("*/chromedriver.exe"))
        if drivers:
            drivers.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return drivers[0]

    sh_driver = shutil.which("chromedriver")
    if sh_driver:
        return Path(sh_driver)

    return None


def get_patched_chromedriver() -> Optional[Path]:
    """
    Returns path to a patched chromedriver.exe where the cdc_ anti-bot signature
    is neutralized.
    """
    DRIVER_DIR.mkdir(parents=True, exist_ok=True)

    src_driver = find_system_chromedriver()
    if not src_driver or not src_driver.exists():
        return None

    need_patch = False
    if not PATCHED_CHROMEDRIVER.exists():
        need_patch = True
    else:
        if src_driver.stat().st_mtime > PATCHED_CHROMEDRIVER.stat().st_mtime:
            need_patch = True

    if need_patch:
        try:
            with open(src_driver, "rb") as f:
                content = f.read()

            match = re.search(rb"\{window\.cdc.*?;\}", content)
            if match:
                target_bytes = match[0]
                new_target = b'{/* safe */};'.ljust(len(target_bytes), b" ")
                content = content.replace(target_bytes, new_target)
                with open(PATCHED_CHROMEDRIVER, "wb") as f:
                    f.write(content)
                print(f"[Stealth] Patched ChromeDriver saved to {PATCHED_CHROMEDRIVER} (CDC neutralized)")
            else:
                shutil.copy2(src_driver, PATCHED_CHROMEDRIVER)
        except Exception as e:
            print(f"[Stealth Warning] Failed patching chromedriver: {e}")
            return src_driver

    return PATCHED_CHROMEDRIVER


STEALTH_JS_INJECTION = """
(function () {
    'use strict';

    // 1. Remove navigator.webdriver completely
    try {
        delete Navigator.prototype.webdriver;
    } catch (e) {}
    try {
        delete navigator.__proto__.webdriver;
    } catch (e) {}
    try {
        delete navigator.webdriver;
    } catch (e) {}

    // 2. Realistic window.chrome object
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.app) {
        window.chrome.app = {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
        };
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
            OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
            PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
            RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }
        };
    }

    // 3. Permissions API (Notifications)
    if (navigator.permissions && navigator.permissions.query) {
        const origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function query(param) {
            if (param && param.name === 'notifications') {
                return Promise.resolve({
                    state: window.Notification ? window.Notification.permission : 'default',
                    onchange: null
                });
            }
            return origQuery(param);
        };
    }

    // NOTE: Real hardware WebGL is preserved to match real Intel/NVIDIA shader math!
    // Faking WebGL causes Volcengine / Turnstile shader math mismatches and fails captchas.

    console.log('[Stealth] Anti-bot stealth active.');
})();
"""


def apply_stealth_to_driver(driver: webdriver.Chrome):
    """Injects stealth evasions via Chrome DevTools Protocol."""
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": STEALTH_JS_INJECTION},
        )
    except Exception as e:
        print(f"[Stealth Warning] Failed applying CDP stealth script: {e}")
