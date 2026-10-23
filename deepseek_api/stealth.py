import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DRIVER_DIR = DATA_DIR / "driver"
PATCHED_CHROMEDRIVER = DRIVER_DIR / "chromedriver.exe"


def find_system_chromedriver() -> Optional[Path]:
    """Finds chromedriver downloaded by Selenium Manager in user cache or system PATH."""
    user_cache = Path(os.path.expandvars(r"%USERPROFILE%\.cache\selenium\chromedriver\win64"))
    if user_cache.exists():
        # Find the latest version folder
        drivers = list(user_cache.glob("*/chromedriver.exe"))
        if drivers:
            drivers.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return drivers[0]

    # Check PATH
    sh_driver = shutil.which("chromedriver")
    if sh_driver:
        return Path(sh_driver)

    return None


def get_patched_chromedriver() -> Optional[Path]:
    """
    Returns path to a patched chromedriver.exe where the cdc_ anti-bot signature
    is neutralized. Creates or updates it if needed.
    """
    DRIVER_DIR.mkdir(parents=True, exist_ok=True)

    src_driver = find_system_chromedriver()
    if not src_driver or not src_driver.exists():
        # Let Selenium Manager handle it normally if source cannot be found
        return None

    need_patch = False
    if not PATCHED_CHROMEDRIVER.exists():
        need_patch = True
    else:
        # Check if source is newer
        if src_driver.stat().st_mtime > PATCHED_CHROMEDRIVER.stat().st_mtime:
            need_patch = True

    if need_patch:
        try:
            with open(src_driver, "rb") as f:
                content = f.read()

            # Neutralize the window.cdc injection code block
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

    // 1. Remove navigator.webdriver completely from prototype and instance
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
    if (!window.chrome.loadTimes) {
        window.chrome.loadTimes = function () {
            const now = performance.now() / 1000;
            return {
                requestTime: now - 0.05,
                startLoadTime: now - 0.05,
                commitLoadTime: now - 0.03,
                finishDocumentLoadTime: now - 0.01,
                firstPaintTime: now - 0.02,
                firstPaintAfterLoadTime: 0,
                navigationType: 'Other',
                wasFetchedViaSpdy: true,
                wasNpnNegotiated: true,
                npnNegotiatedProtocol: 'h2',
                wasAlternateProtocolAvailable: false,
                connectionInfo: 'h2'
            };
        };
    }
    if (!window.chrome.csi) {
        window.chrome.csi = function () {
            return {
                startE: performance.timing ? performance.timing.navigationStart : Date.now() - 500,
                onloadT: performance.timing ? performance.timing.loadEventEnd : Date.now(),
                pageT: performance.now(),
                tran: 15
            };
        };
    }

    // 3. Realistic Plugins & MimeTypes
    const fakePlugins = [
        { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
    ];

    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const arr = Object.create(PluginArray.prototype);
            fakePlugins.forEach((p, idx) => {
                const plugin = Object.create(Plugin.prototype);
                Object.assign(plugin, p);
                arr[idx] = plugin;
                arr[p.name] = plugin;
            });
            Object.defineProperty(arr, 'length', { value: fakePlugins.length });
            return arr;
        },
        configurable: true
    });

    // 4. Permissions API Spoofing (Notifications)
    if (navigator.permissions && navigator.permissions.query) {
        const origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function (param) {
            if (param && param.name === 'notifications') {
                return Promise.resolve({
                    state: window.Notification ? window.Notification.permission : 'default',
                    onchange: null
                });
            }
            return origQuery(param);
        };
    }

    // 5. Languages & Hardware
    Object.defineProperty(navigator, 'languages', {
        get: () => ['ru-RU', 'ru', 'en-US', 'en'],
        configurable: true
    });

    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
        configurable: true
    });

    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true
    });

    // 6. WebGL Vendor / Renderer Masking
    const getParameterProto = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function (parameter) {
        // UNMASKED_VENDOR_WEBGL
        if (parameter === 37445) return 'Google Inc. (NVIDIA)';
        // UNMASKED_RENDERER_WEBGL
        if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        return getParameterProto.apply(this, arguments);
    };

    if (window.WebGL2RenderingContext) {
        const getParameter2Proto = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function (parameter) {
            if (parameter === 37445) return 'Google Inc. (NVIDIA)';
            if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            return getParameter2Proto.apply(this, arguments);
        };
    }

    console.log('[Stealth] Comprehensive anti-bot defenses active.');
})();
"""


def apply_stealth_to_driver(driver: webdriver.Chrome):
    """Injects all stealth evasions via Chrome DevTools Protocol."""
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": STEALTH_JS_INJECTION},
        )
    except Exception as e:
        print(f"[Stealth Warning] Failed applying CDP stealth script: {e}")
