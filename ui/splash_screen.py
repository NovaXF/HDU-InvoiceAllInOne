from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QLabel, QProgressBar, QSplashScreen, QVBoxLayout, QWidget
from app_version import APP_VERSION

APP_NAME = "HDU Invoice All In One"
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.svg"


class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__(QPixmap(420, 360))
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint)

        self.container = QWidget()
        self.container.setObjectName("splashContainer")
        self.container.setFixedSize(420, 360)
        self.container.setStyleSheet(
            """
            QWidget#splashContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0f172a,
                    stop: 1 #1e293b
                );
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 18px;
            }
            QLabel {
                color: white;
                background: transparent;
            }
            QProgressBar {
                border: none;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                text-align: center;
                color: rgba(255, 255, 255, 0.92);
                min-height: 12px;
                max-height: 12px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #22c55e,
                    stop: 1 #06b6d4
                );
            }
            """
        )

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(14)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFixedHeight(220)
        if LOGO_PATH.is_file():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                self.logo_label.setPixmap(
                    pixmap.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

        self.title_label = QLabel(APP_NAME)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Microsoft YaHei UI", 18, QFont.Bold))

        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setFont(QFont("Microsoft YaHei UI", 10))
        self.version_label.setStyleSheet("color: rgba(255, 255, 255, 0.72);")

        self.status_label = QLabel("正在启动…")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Microsoft YaHei UI", 10))
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.84);")

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)

        layout.addWidget(self.logo_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.version_label)
        layout.addSpacing(6)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)

        self._render()

    def _render(self):
        pixmap = QPixmap(self.container.size())
        pixmap.fill(Qt.transparent)
        self.container.render(pixmap)
        self.setPixmap(pixmap)
        self.setMask(pixmap.mask())
        self.resize(pixmap.size())

    def update_status(self, message: str):
        self.status_label.setText(message)
        self._render()
