from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor, QGuiApplication
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
        self.splash.update_status("正在加载主界面…", 15)
        QTimer.singleShot(120, self._create_main_window)

    def _center_splash(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.x() + (geometry.width() - self.splash.width()) // 2
        y = geometry.y() + (geometry.height() - self.splash.height()) // 2
        self.splash.move(x, y)

    def _create_main_window(self):
        self.window = MainWindow()
        self.splash.update_status("正在准备工作区…", 80)
        QTimer.singleShot(120, self._show_main_window)

    def _show_main_window(self):
        if self.window is None:
            return
        screen = self.splash.screen()
        if screen is not None:
            geometry = screen.availableGeometry()
            self.window.move(geometry.center() - self.window.rect().center())
        self.window.show()
        self.splash.finish(self.window)
