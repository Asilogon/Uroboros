"""
Uroboros - Native Desktop GUI Launcher
Runs Flask backend and opens frameless desktop window via pywebview / Chrome app mode.
"""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from deepseek_gui.app import app


class WindowApi:
    """Bridge for JavaScript to control window. Uses webview.active_window() without storing COM references."""
    def __init__(self):
        self._is_maximized = False

    def minimize(self):
        try:
            import webview
            win = webview.active_window()
            if win:
                win.minimize()
        except Exception:
            pass

    def toggle_maximize(self):
        try:
            import webview
            win = webview.active_window()
            if win:
                if self._is_maximized:
                    win.restore()
                    self._is_maximized = False
                else:
                    win.maximize()
                    self._is_maximized = True
        except Exception:
            pass

    def close(self):
        try:
            import webview
            win = webview.active_window()
            if win:
                win.destroy()
        except Exception:
            pass


def find_free_port(default_port: int = 5000) -> int:
    """Finds an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", default_port))
            return default_port
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def run_flask(port: int):
    """Runs the Flask application."""
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def launch_chrome_app(url: str) -> bool:
    """Attempts to launch Chrome in standalone desktop app mode."""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([
                    path,
                    f"--app={url}",
                    "--window-size=1380,880",
                    "--disable-features=Translate",
                ])
                return True
            except Exception:
                pass
    return False


def find_uroboros_hwnds():
    """Finds all HWNDs belonging to Uroboros window via EnumWindows."""
    import ctypes
    user32 = ctypes.windll.user32
    hwnds = []

    def enum_cb(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            if "Uroboros" in buff.value:
                hwnds.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return hwnds


def get_saved_theme() -> str:
    """Reads saved theme from data/session.json."""
    session_file = ROOT_DIR / "data" / "session.json"
    if session_file.exists():
        try:
            import json
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("theme", "dark")
        except Exception:
            pass
    return "dark"


def apply_native_dark_mode():
    """Applies Windows Immersive Dark or Light Mode to native window titlebar based on saved theme."""
    import ctypes
    from ctypes import c_int, byref, sizeof
    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi

    theme = get_saved_theme()
    is_dark = 1 if theme != "light" else 0
    dark_val = c_int(is_dark)
    caption_color = c_int(0x000E0C0C if is_dark else 0x00F5F4F3)
    border_color = c_int(0x00181616 if is_dark else 0x00E5E7EB)

    for _ in range(80):
        time.sleep(0.15)
        hwnds = find_uroboros_hwnds()
        if hwnds:
            for hwnd in hwnds:
                try:
                    # Windows 10 2004+ and Windows 11
                    dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(dark_val), sizeof(dark_val))
                    # Windows 10 1903/1909
                    dwmapi.DwmSetWindowAttribute(hwnd, 19, byref(dark_val), sizeof(dark_val))
                    # Windows 11 caption & border colors
                    dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), sizeof(caption_color))
                    dwmapi.DwmSetWindowAttribute(hwnd, 34, byref(border_color), sizeof(border_color))
                    # Force window frame redraw immediately
                    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
                except Exception:
                    pass
            break


def main():
    port = find_free_port(5000)
    url = f"http://127.0.0.1:{port}"

    # Start Flask server in background thread
    server_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be responsive
    time.sleep(0.6)

    print("\n" + "=" * 65)
    print("      UROBOROS - DEEPSEEK REVERSE API STUDIO")
    print(f"      Backend server running at: {url}")
    print("=" * 65 + "\n")

    api = WindowApi()
    launched = False

    try:
        import webview
        print("[GUI] Launching native Uroboros window with Windows Aero Snap support...")
        win = webview.create_window(
            title="Uroboros",
            url=url,
            width=1380,
            height=880,
            background_color="#111113",
            frameless=False,
            resizable=True,
            easy_drag=False,
            text_select=True,
            js_api=api,
        )
        threading.Thread(target=apply_native_dark_mode, daemon=True).start()
        webview.start(apply_native_dark_mode)
        launched = True
    except Exception as e:
        print(f"[GUI Note] pywebview error: {e}. Falling back to Chrome App Mode...")

    if not launched:
        if launch_chrome_app(url):
            print("[GUI] Opened Uroboros in Chrome App Mode.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[GUI] Closing...")
        else:
            print("[GUI] Opening Uroboros in default browser...")
            webbrowser.open(url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[GUI] Closing...")


if __name__ == "__main__":
    main()
