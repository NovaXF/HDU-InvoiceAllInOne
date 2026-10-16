from pathlib import Path

from PySide6.QtCore import QByteArray, QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from app_version import APP_VERSION
from core.app_paths import load_settings
from ui.main_window import DEFAULT_THEME_KEY, THEMES


APP_NAME = "HDU 发票工作台"
ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSET_DIR / "logo.svg"


class SplashLogo(QWidget):
    """Paint vector paths directly on Qt's DPI-aware widget surface."""

    def __init__(self, filename: str, color: str, width: int, height: int):
        super().__init__()
        source = (ASSET_DIR / filename).read_text(encoding="utf-8")
        source = source.replace("#2563eb", color).replace("#2563EB", color)
        self.renderer = QSvgRenderer(QByteArray(source.encode("utf-8")), self)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.renderer.render(painter, QRectF(self.rect()))
        painter.end()


class SplashScreen(QWidget):
    def __init__(self, theme_key: str | None = None):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(APP_NAME)
        if theme_key is None:
            theme_key = load_settings().get("theme")
        self.theme = THEMES.get(theme_key, THEMES[DEFAULT_THEME_KEY])
        theme = self.theme
        self.resize(520, 296)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.container = QFrame()
        self.container.setObjectName("SplashPanel")
        outer.addWidget(self.container)
        self.setStyleSheet(f"""
            QFrame#SplashPanel {{
                background: {theme['panel']};
                border: 1px solid {theme['border']};
                border-radius: 20px;
            }}
            QLabel {{ background: transparent; border: none; color: {theme['text']}; }}
            QLabel#SplashEyebrow {{ color: {theme['muted']}; font-size: 11px; font-weight: 600; }}
            QLabel#SplashTitle {{ font-size: 30px; font-weight: 800; }}
            QLabel#SplashSubtitle {{ color: {theme['muted']}; font-size: 12px; }}
            QLabel#SplashVersion {{
                color: {theme['muted']}; background: {theme['panel_alt']};
                border: 1px solid {theme['border']}; border-radius: 11px;
                padding: 4px 10px; font-size: 11px; font-weight: 600;
            }}
            QLabel#SplashStatus {{ color: {theme['muted']}; font-size: 12px; }}
            QFrame#SplashDivider {{ background: {theme['border']}; border: none; }}
            QProgressBar {{
                border: none; background: {theme['accent_soft']}; border-radius: 2px;
                min-height: 4px; max-height: 4px;
            }}
            QProgressBar::chunk {{ background: {theme['accent']}; border-radius: 2px; }}
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setSpacing(10)
        self.logo_label = SplashLogo("logo.svg", theme["accent"], 36, 36)
        header.addWidget(self.logo_label)
        eyebrow = QLabel("INVOICE WORKBENCH")
        eyebrow.setObjectName("SplashEyebrow")
        header.addWidget(eyebrow)
        header.addStretch()
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setObjectName("SplashVersion")
        header.addWidget(self.version_label, 0, Qt.AlignVCenter)
        layout.addLayout(header)
        layout.addSpacing(24)
        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("SplashTitle")
        layout.addWidget(self.title_label)
        layout.addSpacing(6)
        subtitle = QLabel("发票识别 · 智能分叠 · 报销整理")
        subtitle.setObjectName("SplashSubtitle")
        layout.addWidget(subtitle)
        layout.addStretch(1)
        divider = QFrame()
        divider.setObjectName("SplashDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(16)
        footer = QHBoxLayout()
        self.status_label = QLabel("正在启动…")
        self.status_label.setObjectName("SplashStatus")
        footer.addWidget(self.status_label)
        footer.addStretch()
        self.wordmark = SplashLogo("novax-wordmark.svg", theme["muted"], 88, 23)
        footer.addWidget(self.wordmark)
        layout.addLayout(footer)
        layout.addSpacing(12)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self._progress_animation = QVariantAnimation(self)
        self._progress_animation.setDuration(160)
        self._progress_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._progress_animation.valueChanged.connect(lambda value: self.progress.setValue(round(value)))

    def update_status(self, message: str, progress: int | None = None):
        self.status_label.setText(message)
        if progress is not None:
            self._progress_animation.stop()
            self._progress_animation.setStartValue(self.progress.value())
            self._progress_animation.setEndValue(max(0, min(progress, 100)))
            self._progress_animation.start()

    def finish(self, window):
        self._progress_animation.stop()
        self.progress.setValue(100)
        self.close()
