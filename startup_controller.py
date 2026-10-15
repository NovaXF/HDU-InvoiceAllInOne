from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen


class StartupController:
    def __init__(self, app: QApplication):
        self.app = app
        self.splash = SplashScreen()
        self.window: MainWindow | None = None

    def start(self):
        self._center_splash()
        self.splash.show()
        self.app.processEvents()
        self.splash.update_status("正在加载主界面…")
        QTimer.singleShot(120, self._create_main_window)

    def _center_splash(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.x() + (geometry.width() - self.splash.width()) // 2
        y = geometry.y() + (geometry.height() - self.splash.height()) // 2
        self.splash.move(x, y)

    def _create_main_window(self):
        self.window = MainWindow()
        self.splash.update_status("正在准备工作区…")
        QTimer.singleShot(120, self._show_main_window)

    def _show_main_window(self):
        if self.window is None:
            return
        self.window.show()
        self.splash.finish(self.window)
