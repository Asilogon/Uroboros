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

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from deepseek_gui.app import app


class WindowApi:
    """Bridge for JavaScript to control frameless window (minimize, maximize, close)."""
    def __init__(self):
        self.window = None
        self._is_maximized = False

    def set_window(self, window):
        self.window = window

    def minimize(self):
        if self.window:
            self.window.minimize()

    def toggle_maximize(self):
        if self.window:
            if self._is_maximized:
                self.window.restore()
                self._is_maximized = False
            else:
                self.window.maximize()
                self._is_maximized = True

    def close(self):
        if self.window:
            self.window.destroy()


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


def main():
    port = find_free_port(5000)
    url = f"http://127.0.0.1:{port}"

    # Start Flask server in background thread
    server_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to start
    time.sleep(0.8)

    print("\n" + "=" * 65)
    print("      UROBOROS - DEEPSEEK REVERSE API STUDIO")
    print(f"      Backend server running at: {url}")
    print("=" * 65 + "\n")

    api = WindowApi()
    launched = False

    try:
        import webview
        print("[GUI] Launching frameless Uroboros window...")
        window = webview.create_window(
            title="Uroboros",
            url=url,
            width=1380,
            height=880,
            background_color="#111113",
            frameless=True,
            resizable=True,
            easy_drag=True,
            text_select=True,
            js_api=api,
        )
        api.set_window(window)
        webview.start()
        launched = True
    except Exception as e:
        print(f"[GUI Note] pywebview frameless mode: {e}. Falling back to Chrome App Mode...")

    if not launched:
        # Fallback to Chrome App mode
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
