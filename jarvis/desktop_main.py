#!/usr/bin/env python
import sys
import os
import time
import subprocess
import argparse
import atexit
import urllib.request
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# --- Qt plugin path fix for cx_Freeze bundles ---
# Must be set BEFORE importing/creating QApplication
def _setup_qt_plugin_path():
    if getattr(sys, 'frozen', False):
        # Running in a cx_Freeze bundle
        bundle_dir = Path(sys.executable).parent
        plugins_dir = bundle_dir / 'plugins'
        if plugins_dir.exists():
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = str(plugins_dir)
            # Also set QT_QPA_PLATFORM for Windows
            os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

_setup_qt_plugin_path()

import sys
import os
import time
import subprocess
import argparse
import atexit
import urllib.request
import threading
import uvicorn
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import QUrl, QTimer, Qt, QCoreApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings


class JarvisWindow(QMainWindow):
    def __init__(self, dashboard_url, server_process=None):
        super().__init__()
        self.dashboard_url = dashboard_url
        self.server_process = server_process
        self.setWindowTitle("JARVIS - Personal AI Control Center")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        icon_path = PROJECT_ROOT / "assets" / "jarvis.ico"
        if icon_path.exists():
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(str(icon_path)))

        self.web_view = QWebEngineView()
        self.setCentralWidget(self.web_view)

        self._configure_web_engine()

        self.web_view.load(QUrl(dashboard_url))

        self.web_view.loadFinished.connect(self._on_load_finished)

        self.web_view.page().windowCloseRequested.connect(self.close)

        self._loaded = False

    def _configure_web_engine(self):
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentStoragePath(str(PROJECT_ROOT / "webengine_cache"))
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)

        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)


    def _on_load_finished(self, ok):
        if ok:
            self._loaded = True
            self.statusBar().showMessage("JARVIS Dashboard Loaded", 3000)
        else:
            self.statusBar().showMessage("Failed to load dashboard", 5000)

    def closeEvent(self, event):
        event.accept()
        QCoreApplication.quit()


class JarvisDesktopApp:
    def __init__(self):
        self.app = None
        self.window = None
        self.server_thread = None
        self.server_ready = False
        self.dashboard_url = "http://127.0.0.1:3000"

    def _get_python_executable(self):
        """Get the correct Python executable for the current environment."""
        if getattr(sys, 'frozen', False):
            # Running in a cx_Freeze bundle
            # The Python interpreter is typically in the same directory as the executable
            # or in a 'python' subdirectory
            bundle_dir = Path(sys.executable).parent
            python_exe = bundle_dir / 'python.exe'
            if python_exe.exists():
                return str(python_exe)
            # Fallback: try to find python in the bundle
            for candidate in [bundle_dir / 'python.exe', bundle_dir / 'python3.exe']:
                if candidate.exists():
                    return str(candidate)
            # Fallback: use sys.executable (might be the bundled executable itself)
            return sys.executable
        else:
            # Running in development mode
            return sys.executable

    def run_uvicorn(self):
        """Run uvicorn in a separate thread."""
        config = uvicorn.Config("app.main:app", host="127.0.0.1", port=3000, log_level="info")
        server = uvicorn.Server(config)
        server.run()

    def start_server(self):
        self.server_thread = threading.Thread(target=self.run_uvicorn, daemon=True)
        self.server_thread.start()

        self._wait_for_server()

    def _wait_for_server(self, timeout=30):
        import urllib.request
        start = time.time()
        while time.time() - start < timeout:
            try:
                with urllib.request.urlopen(self.dashboard_url + "/health", timeout=2) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("Server did not start within " + str(timeout) + " seconds")

    def create_window(self):
        self.window = JarvisWindow(self.dashboard_url)
        self.window.show()

    def run(self):
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

        self.app = QApplication(sys.argv)
        self.app.setApplicationName("JARVIS")
        self.app.setApplicationDisplayName("JARVIS - Personal AI Control Center")
        self.app.setOrganizationName("JARVIS")

        icon_path = PROJECT_ROOT / "assets" / "jarvis.ico"
        if icon_path.exists():
            from PySide6.QtGui import QIcon
            self.app.setWindowIcon(QIcon(str(icon_path)))

        print("Starting JARVIS server...")
        try:
            self.start_server()
        except Exception as e:
            QMessageBox.critical(None, "JARVIS Startup Error",
                "Failed to start server:\\n" + str(e))
            return 1

        print("Server ready. Creating window...")
        self.create_window()

        def cleanup():
            pass

        atexit.register(cleanup)

        return self.app.exec()


def main():
    parser = argparse.ArgumentParser(description="JARVIS Desktop Application")
    parser.add_argument("--test-server", action="store_true", help="Test server startup without GUI")
    args = parser.parse_args()

    if args.test_server:
        print("Testing server startup...")
        import uvicorn
        import threading
        import urllib.request
        import time

        def run_uvicorn():
            config = uvicorn.Config("app.main:app", host="127.0.0.1", port=3000, log_level="info")
            server = uvicorn.Server(config)
            server.run()

        server_thread = threading.Thread(target=lambda: uvicorn.run("app.main:app", host="127.0.0.1", port=3000, log_level="info"), daemon=True)
        server_thread.start()

        start = time.time()
        while time.time() - start < 30:
            try:
                with urllib.request.urlopen("http://127.0.0.1:3000/health", timeout=2) as resp:
                    if resp.status == 200:
                        print("Server started successfully")
                        return 0
            except Exception:
                pass
            time.sleep(0.5)
        print("Server did not start within timeout")
        return 1

    if args.test_server:
        print("Testing server startup...")
        import uvicorn
        import threading
        import urllib.request
        import time

        def run_uvicorn():
            config = uvicorn.Config("app.main:app", host="127.0.0.1", port=3000, log_level="info")
            server = uvicorn.Server(config)
            server.run()

        server_thread = threading.Thread(target=lambda: uvicorn.run("app.main:app", host="127.0.0.1", port=3000, log_level="info"), daemon=True)
        server_thread.start()

        start = time.time()
        while time.time() - start < 30:
            try:
                with urllib.request.urlopen("http://127.0.0.1:3000/health", timeout=2) as resp:
                    if resp.status == 200:
                        print("Server started successfully")
                        return 0
            except Exception:
                pass
            time.sleep(0.5)
        print("Server did not start within timeout")
        return 1

    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEngineProfile
    except ImportError as e:
        print("ERROR: Missing Qt WebEngine: " + str(e))
        print("Install with: pip install PySide6")
        return 1

    model_path = PROJECT_ROOT / "Qwen3-1.7B-Q4_K_M.gguf"
    if not model_path.exists():
        print("WARNING: Model file not found at " + str(model_path))
        print("Local AI inference may not work.")

    from app.config import get_settings
    settings = get_settings()
    if settings.speech_provider == "vosk" and settings.vosk_model_path:
        vosk_path = Path(settings.vosk_model_path)
        if not vosk_path.exists():
            print("WARNING: Vosk model not found at " + str(vosk_path))
            print("Offline speech recognition may not work.")

    desktop_app = JarvisDesktopApp()
    return desktop_app.run()


if __name__ == "__main__":
    sys.exit(main())
