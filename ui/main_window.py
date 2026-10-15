import json
import subprocess
from copy import deepcopy
from functools import wraps
from pathlib import Path

from PySide6.QtCore import QByteArray, QEasingCurve, QDate, QEvent, QItemSelectionModel, QMimeData, QPoint, QRect, QRectF, QSize, Qt, QThread, QTimer, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QBrush, QDesktopServices, QDrag, QDragEnterEvent, QDropEvent, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractButton,
    QAbstractSpinBox,
    QStyle,
    QStyleOptionViewItem,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from core.file_manager import (
    STATE_FILE,
    create_new_batch,
    load_batch,
    load_date_groups_from_parent,
    materialize_batch,
    materialize_selected_stacks,
)
from core.order_matcher import bind_screenshot_to_invoice, match_screenshots_to_invoices, sync_screenshot_stack_indexes, unbind_screenshot
from core.order_screenshot_parser import extract_paid_amount_details
from core.pdf_parser import extract_invoice_data
from core.recycle_bin import recycle_file
from core.app_updates import check_latest_release, download_installer, normalize_repository, version_tuple
from app_version import APP_VERSION, GITHUB_REPOSITORY
from core.stack_splitter import (
    MAX_AMOUNT,
    MAX_COUNT,
    Stack,
    assign_invoice_to_stack,
    can_fit,
    normalize_stack_indexes,
    validate_stacks,
)
from models.invoice import Batch, DateGroup, Invoice, OrderScreenshot


SETTINGS_FILE = "settings.json"
ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
DEFAULT_THEME_KEY = "indigo_khaki"
THEMED_SVG_PIXMAP_CACHE: dict[tuple[str, str, int], QPixmap] = {}

THEMES = {
    "indigo_khaki": {
        "name": "靛蓝卡其",
        "bg": "#f3f4f8",
        "panel": "#ffffff",
        "panel_alt": "#f7f7fb",
        "field": "#f7f7fb",
        "border": "#d9dbe8",
        "text": "#22283f",
        "muted": "#62687e",
        "accent": "#313c69",
        "secondary": "#ccb16e",
        "highlight": "#f4ecd3",
        "accent_hover": "#263053",
        "accent_soft": "#eceef7",
        "danger": "#b64a55",
        "success": "#627f6c",
        "success_soft": "#eaf0ec",
        "warning": "#fbf3da",
        "selected_text": "#22283f",
    },
    "taupe_ink": {
        "name": "陶土墨蓝",
        "bg": "#f7f1e9",
        "panel": "#ffffff",
        "panel_alt": "#fbf6ef",
        "field": "#fbf6ef",
        "border": "#e2cfb7",
        "text": "#30323f",
        "muted": "#746755",
        "accent": "#b28e5a",
        "secondary": "#30323f",
        "highlight": "#f0dec6",
        "accent_hover": "#967544",
        "accent_soft": "#f0dec6",
        "danger": "#b42318",
        "success": "#708257",
        "success_soft": "#edf0e5",
        "warning": "#fff4d8",
        "selected_text": "#30323f",
    },
    "premium_blue_gray": {
        "name": "蓝灰高级",
        "bg": "#edf1fd",
        "panel": "#ffffff",
        "panel_alt": "#f7f9ff",
        "field": "#f7f9ff",
        "border": "#cfd8ea",
        "text": "#0f172a",
        "muted": "#5d6b7c",
        "accent": "#334155",
        "secondary": "#38bdf8",
        "highlight": "#e0f2fe",
        "accent_hover": "#0f172a",
        "accent_soft": "#e6ecfb",
        "danger": "#ea4335",
        "success": "#347a70",
        "success_soft": "#e5f1ee",
        "warning": "#fff7df",
        "selected_text": "#0f172a",
    },
    "matcha_graphite": {
        "name": "抹茶石墨",
        "bg": "#f4f7f2",
        "panel": "#ffffff",
        "panel_alt": "#f8faf6",
        "field": "#f8faf6",
        "border": "#d8e0d3",
        "text": "#2f3340",
        "muted": "#656b73",
        "accent": "#75bb72",
        "secondary": "#3b3d4c",
        "highlight": "#e4f3e1",
        "accent_hover": "#579b54",
        "accent_soft": "#e4f3e1",
        "danger": "#e15b4f",
        "success": "#579b54",
        "success_soft": "#e4f3e1",
        "warning": "#fff5d6",
        "selected_text": "#2f3340",
    },
    "business_taupe": {
        "name": "商务灰褐",
        "bg": "#fbf7f0",
        "panel": "#ffffff",
        "panel_alt": "#fdfaf5",
        "field": "#fdfaf5",
        "border": "#e1d3c1",
        "text": "#303133",
        "muted": "#6f675f",
        "accent": "#d4a26a",
        "secondary": "#3a3b3c",
        "highlight": "#f2dfc9",
        "accent_hover": "#b8834d",
        "accent_soft": "#f2dfc9",
        "danger": "#b42318",
        "success": "#74845e",
        "success_soft": "#edf0e6",
        "warning": "#fff1ce",
        "selected_text": "#303133",
    },
    "berry_charcoal": {
        "name": "莓红炭灰",
        "bg": "#f8f9fa",
        "panel": "#ffffff",
        "panel_alt": "#f4f5f6",
        "field": "#f4f5f6",
        "border": "#d9dde2",
        "text": "#222222",
        "muted": "#65676b",
        "accent": "#d64a6c",
        "secondary": "#222222",
        "highlight": "#fde8ee",
        "accent_hover": "#b83958",
        "accent_soft": "#fde8ee",
        "danger": "#c62828",
        "success": "#378965",
        "success_soft": "#e7f3ed",
        "warning": "#fff2d6",
        "selected_text": "#222222",
    },
    "minimal_bw": {
        "name": "极简黑白",
        "bg": "#f5f5f5",
        "panel": "#ffffff",
        "panel_alt": "#fafafa",
        "field": "#fafafa",
        "border": "#d7d7d7",
        "text": "#0a0a0a",
        "muted": "#666666",
        "accent": "#0a0a0a",
        "secondary": "#a3a3a3",
        "highlight": "#ececec",
        "accent_hover": "#2b2b2b",
        "accent_soft": "#ececec",
        "danger": "#d93025",
        "success": "#4f735d",
        "success_soft": "#eaf0ec",
        "warning": "#fff4d6",
        "selected_text": "#0a0a0a",
    },
    "expo_cool": {
        "name": "银紫冷调",
        "bg": "#e0e4e8",
        "panel": "#f8f9fb",
        "panel_alt": "#eef1f5",
        "field": "#eef1f5",
        "border": "#c6ccd6",
        "text": "#242e42",
        "muted": "#667080",
        "accent": "#947fc1",
        "secondary": "#242e42",
        "highlight": "#eee8f7",
        "accent_hover": "#7862a5",
        "accent_soft": "#eee8f7",
        "danger": "#d94a6a",
        "success": "#618876",
        "success_soft": "#e8efec",
        "warning": "#fff3d8",
        "selected_text": "#242e42",
    },
    "forest_cloud_sea": {
        "name": "雾林湖青",
        "bg": "#eef1f1",
        "panel": "#fbfcfc",
        "panel_alt": "#f2f4f4",
        "field": "#f4f6f6",
        "border": "#c8d0d0",
        "text": "#272a1d",
        "muted": "#5f6f70",
        "accent": "#36514e",
        "secondary": "#6b8e91",
        "highlight": "#dde6e7",
        "accent_hover": "#293f3c",
        "accent_soft": "#e3e9e8",
        "danger": "#b74c45",
        "success": "#4f7468",
        "success_soft": "#e6efeb",
        "warning": "#f4ecd4",
        "selected_text": "#272a1d",
    },
    "summer_berry_plate": {
        "name": "夏莓瓷盘",
        "bg": "#fbecea",
        "panel": "#ffffff",
        "panel_alt": "#fdf3f1",
        "field": "#fdf6f4",
        "border": "#e7ccc8",
        "text": "#353543",
        "muted": "#756d72",
        "accent": "#68869e",
        "secondary": "#e99d94",
        "highlight": "#f7e1dd",
        "accent_hover": "#526f87",
        "accent_soft": "#e9eff3",
        "danger": "#c95f5b",
        "success": "#587b69",
        "success_soft": "#e7efea",
        "warning": "#f8edd7",
        "selected_text": "#353543",
    },
    "autumn_maple_pencil": {
        "name": "枫橙纸白",
        "bg": "#fbf4ee",
        "panel": "#fffdfb",
        "panel_alt": "#fdf8f4",
        "field": "#fdf8f4",
        "border": "#ead5c7",
        "text": "#4b352f",
        "muted": "#7a6258",
        "accent": "#d96731",
        "secondary": "#6d4a3d",
        "highlight": "#f9e8d8",
        "accent_hover": "#b95026",
        "accent_soft": "#fbe7db",
        "danger": "#b42318",
        "success": "#6f7c52",
        "success_soft": "#edf0e5",
        "warning": "#fff1d6",
        "selected_text": "#4b352f",
    },
    "charcoal_red_cream": {
        "name": "炭红奶油",
        "bg": "#f7eee8",
        "panel": "#fffaf6",
        "panel_alt": "#fff5ed",
        "field": "#fff8f2",
        "border": "#e4ccc0",
        "text": "#312520",
        "muted": "#77645c",
        "accent": "#7b2d29",
        "secondary": "#312520",
        "highlight": "#f5d9cf",
        "accent_hover": "#61211e",
        "accent_soft": "#f4ded7",
        "danger": "#b42318",
        "success": "#5f7b65",
        "success_soft": "#e8efe8",
        "warning": "#f8e8c9",
        "selected_text": "#312520",
    },
}

THEME_DESCRIPTIONS = {
    key: ""
    for key in THEMES
}

THEME_PALETTES = {
    "indigo_khaki": ["#313c69", "#d9dbe8", "#ccb16e"],
    "taupe_ink": ["#b28e5a", "#30323f", "#f0dec6"],
    "premium_blue_gray": ["#0f172a", "#334155", "#38bdf8", "#edf1fd"],
    "matcha_graphite": ["#75bb72", "#3b3d4c"],
    "business_taupe": ["#d4a26a", "#3a3b3c", "#fbf7f0"],
    "berry_charcoal": ["#f8f9fa", "#222222", "#d64a6c"],
    "minimal_bw": ["#0a0a0a", "#a3a3a3", "#f5f5f5"],
    "expo_cool": ["#e0e4e8", "#242e42", "#947fc1"],
    "forest_cloud_sea": ["#cfced1", "#acb7bb", "#272a1d", "#36514e", "#6b8e91"],
    "summer_berry_plate": ["#68869e", "#e99d94", "#353543", "#f7e1dd"],
    "autumn_maple_pencil": ["#d96731", "#f09b57", "#f9e8d8", "#6d4a3d"],
    "charcoal_red_cream": ["#7b2d29", "#fff2df", "#312520"],
}


def _mix_color(first: QColor, second: QColor, amount: float) -> QColor:
    return QColor(
        round(first.red() + (second.red() - first.red()) * amount),
        round(first.green() + (second.green() - first.green()) * amount),
        round(first.blue() + (second.blue() - first.blue()) * amount),
    )


def _text_on_fill(color: str) -> str:
    qcolor = QColor(color)
    luminance = qcolor.red() * 0.299 + qcolor.green() * 0.587 + qcolor.blue() * 0.114
    return "#0f172a" if luminance >= 190 else "#ffffff"


def _themed_svg_pixmap(filename: str, color: QColor, size: int) -> QPixmap:
    key = (filename, color.name(), size)
    if key in THEMED_SVG_PIXMAP_CACHE:
        return THEMED_SVG_PIXMAP_CACHE[key]
    svg_path = ICON_DIR / filename
    if not svg_path.is_file():
        svg_path = Path(__file__).resolve().parent.parent / "assets" / filename
    svg = svg_path.read_text(encoding="utf-8")
    color_name = color.name()
    for existing in ("#2563eb", "#2563EB", "#64748b", "#0f172a", "#ffffff"):
        svg = svg.replace(existing, color_name)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    THEMED_SVG_PIXMAP_CACHE[key] = pixmap
    return pixmap


class ThemedSvgIcon(QWidget):
    """Directly renders a theme-colored SVG onto a transparent widget."""

    def __init__(self, filename: str, color: QColor, icon_size: int, box_size: int, parent=None):
        super().__init__(parent)
        svg_path = ICON_DIR / filename
        if not svg_path.is_file():
            svg_path = Path(__file__).resolve().parent.parent / "assets" / filename
        svg = svg_path.read_text(encoding="utf-8")
        color_name = color.name()
        for existing in ("#2563eb", "#2563EB", "#64748b", "#0f172a", "#ffffff"):
            svg = svg.replace(existing, color_name)
        self._renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")), self)
        self._icon_size = icon_size
        self.setFixedSize(box_size, box_size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        left = (self.width() - self._icon_size) // 2
        top = (self.height() - self._icon_size) // 2
        self._renderer.render(painter, QRect(left, top, self._icon_size, self._icon_size))
        painter.end()


class SquareCheckButton(QAbstractButton):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setCheckable(True)
        self.setChecked(True)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(28, 28)

    def paintEvent(self, event):
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        accent = QColor(self._theme["accent"])
        border = accent if self.isChecked() else QColor(self._theme["border"])
        fill = accent if self.isChecked() else QColor(self._theme["panel"])
        painter.setPen(QPen(border, 2))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 6, 6)
        if self.isChecked():
            pen = QPen(QColor("#ffffff"), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(QPoint(7, 14), QPoint(12, 19))
            painter.drawLine(QPoint(12, 19), QPoint(21, 9))
        painter.end()


class SaveFilterButton(QAbstractButton):
    def __init__(self, label: str, count: int, kind: str, theme: dict, parent=None):
        super().__init__(parent)
        self._label = label
        self._count = count
        self._kind = kind
        self._theme = theme
        self.setCheckable(True)
        self.setMinimumWidth(142)
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(142, 44)

    def paintEvent(self, event):
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        accent = QColor(self._theme["accent"])
        if self.isChecked():
            background = accent
            label_color = QColor("#ffffff")
            badge_background = QColor("#ffffff")
            badge_color = accent
        else:
            background = QColor(self._theme["accent_soft"] if self.underMouse() else "#00000000")
            label_color = QColor(self._theme["text"])
            if self._kind == "new" and self._count:
                badge_background = QColor(self._theme["success_soft"])
                badge_color = QColor(self._theme["success"])
            elif self._kind == "modified" and self._count:
                badge_background = QColor(self._theme["accent_soft"])
                badge_color = accent
            else:
                badge_background = QColor(self._theme["panel"])
                badge_color = QColor(self._theme["muted"])

        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 10, 10)

        label_font = QFont(self.font())
        label_font.setBold(True)
        label_font.setPointSizeF(max(label_font.pointSizeF(), 12))
        count_font = QFont(label_font)
        count_font.setPointSizeF(max(label_font.pointSizeF() - 1, 11))
        painter.setFont(label_font)
        label_width = painter.fontMetrics().horizontalAdvance(self._label)
        badge_size = 28
        gap = 12
        content_width = label_width + gap + badge_size
        left = rect.left() + (rect.width() - content_width) // 2
        painter.setPen(label_color)
        painter.drawText(QRect(left, rect.top(), label_width, rect.height()), Qt.AlignVCenter | Qt.AlignLeft, self._label)

        badge_rect = QRect(left + label_width + gap, rect.top() + (rect.height() - badge_size) // 2, badge_size, badge_size)
        painter.setPen(Qt.NoPen)
        painter.setBrush(badge_background)
        painter.drawEllipse(badge_rect)
        painter.setFont(count_font)
        painter.setPen(badge_color)
        painter.drawText(badge_rect, Qt.AlignCenter, str(self._count))
        painter.end()


class UpdateWorker(QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, repository, release=None):
        super().__init__()
        self.repository = repository
        self.release = release

    def run(self):
        try:
            result = (download_installer(self.release, self.repository, self.progress.emit)
                      if self.release else check_latest_release(self.repository))
            self.result.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class VersionPanel(QFrame):
    """Quiet, theme-tinted wordmark behind the current version information."""

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self._renderer = QSvgRenderer(str(ICON_DIR.parent / "novax-wordmark.svg"), self)
        self.set_theme(THEMES[DEFAULT_THEME_KEY])

    def set_theme(self, theme):
        source = (ICON_DIR.parent / "novax-wordmark.svg").read_text(encoding="utf-8")
        self._renderer.load(QByteArray(source.replace("#2563eb", theme["accent"]).encode("utf-8")))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Multiply)
        painter.setOpacity(0.065)
        width = min(self.width() * 0.58, 500)
        height = width * 246 / 970
        self._renderer.render(painter, QRectF(self.width() - width - 22, 8, width, height))
        painter.end()


class ParseWorker(QThread):
    result = Signal(str, object, object)

    def __init__(self, invoices: list[Invoice]):
        super().__init__()
        self.invoices = list(invoices)

    def run(self):
        for invoice in self.invoices:
            try:
                parsed = extract_invoice_data(invoice.source_path)
                error = None if parsed.amount is not None else "未能从 PDF 中识别价税合计金额"
                self.result.emit(invoice.invoice_id, parsed, error)
            except Exception as e:
                self.result.emit(invoice.invoice_id, None, str(e))


class ScreenshotParseWorker(QThread):
    result = Signal(int, object, object)

    def __init__(self, start_index: int, paths: list[Path]):
        super().__init__()
        self.start_index = start_index
        self.paths = paths

    def run(self):
        for offset, path in enumerate(self.paths):
            try:
                platform, amounts = extract_paid_amount_details(path)
                amount = round(sum(amounts), 2) if amounts else None
                self.result.emit(self.start_index + offset, (platform, amount), None)
            except Exception as e:
                self.result.emit(self.start_index + offset, None, str(e))


class InvoiceTable(QTableWidget):
    files_dropped = Signal(list)
    invoice_dropped_to_left = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDragEnabled(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-invoice-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-invoice-id"):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            paths = [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.toLocalFile().lower().endswith(".pdf")
            ]
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        if event.mimeData().hasFormat("application/x-invoice-id"):
            raw = bytes(event.mimeData().data("application/x-invoice-id")).decode("utf-8")
            invoice_ids = [line for line in raw.splitlines() if line]
            if invoice_ids:
                self.invoice_dropped_to_left.emit(invoice_ids)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def startDrag(self, supported_actions):
        rows = sorted({item.row() for item in self.selectedItems()})
        if not rows:
            return
        ids = []
        for row in rows:
            item = self.item(row, 0)
            if item and item.data(Qt.UserRole):
                ids.append(item.data(Qt.UserRole))
        if not ids:
            return

        mime = QMimeData()
        mime.setData("application/x-invoice-id", "\n".join(ids).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)


class ScreenshotTable(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDragEnabled(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-screenshot-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-screenshot-id"):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            paths = [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.toLocalFile().lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
        event.ignore()

    def startDrag(self, supported_actions):
        rows = sorted({item.row() for item in self.selectedItems()})
        if not rows:
            return
        ids = []
        for row in rows:
            item = self.item(row, 0)
            if item and item.data(Qt.UserRole):
                ids.append(item.data(Qt.UserRole))
        if not ids:
            return

        mime = QMimeData()
        mime.setData("application/x-screenshot-id", "\n".join(ids).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)


class StackTree(QTreeWidget):
    invoice_dropped = Signal(list, str, int, int)
    screenshot_dropped = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self._invoice_drop_target: tuple[str, int, int] | None = None
        self._invoice_drop_indicator_y = -1
        self._drop_transition = None
        self._drop_overlay = None

        self.frozen_sequence_header = QLabel("序", self.header().viewport())
        self.frozen_sequence_header.setAlignment(Qt.AlignCenter)
        self.frozen_sequence_header.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.header().geometriesChanged.connect(self.update_frozen_header)

    def update_frozen_header(self):
        if self.columnCount() >= 7:
            remaining_width = self.viewport().width() - sum(self.columnWidth(i) for i in range(6))
            last_width = max(110, remaining_width)
            if self.columnWidth(6) != last_width:
                self.setColumnWidth(6, last_width)
        theme = getattr(self, "_theme", THEMES[DEFAULT_THEME_KEY])
        header_bg = _mix_color(QColor(theme["panel_alt"]), QColor(theme["border"]), 0.88).name()
        self.frozen_sequence_header.setStyleSheet(
            f"background: {header_bg}; color: {theme['muted']}; "
            f"border: none; border-right: 1px solid {theme['border']}; "
            f"border-bottom: 1px solid {theme['border']}; font-weight: 900;"
        )
        self.frozen_sequence_header.setGeometry(
            0, 0, self.columnWidth(0), self.header().height(),
        )
        self.frozen_sequence_header.raise_()
        self.frozen_sequence_header.show()

    def resizeEvent(self, event):
        self._finish_drop_transition()
        super().resizeEvent(event)
        if hasattr(self, "frozen_sequence_header"):
            self.update_frozen_header()

    def _finish_drop_transition(self):
        if self._drop_transition is not None:
            self._drop_transition.stop()
            self._drop_transition.deleteLater()
            self._drop_transition = None
        if self._drop_overlay is not None:
            self._drop_overlay.hide()
            self._drop_overlay.deleteLater()
            self._drop_overlay = None

    def _capture_drop_view(self):
        self._finish_drop_transition()
        self.viewport().repaint()
        return self.viewport().grab()

    def _animate_drop_transition(self, before):
        # Fade the previous rows into their new order without moving the viewport.
        self._finish_drop_transition()
        overlay = QLabel(self.viewport())
        overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        overlay.setPixmap(before)
        overlay.setGeometry(self.viewport().rect())
        opacity = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(opacity)
        animation = QVariantAnimation(self)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.valueChanged.connect(lambda value: opacity.setOpacity(float(value)))
        animation.finished.connect(self._finish_drop_transition)
        self._drop_overlay = overlay
        self._drop_transition = animation
        overlay.show()
        animation.start()

    def scrollContentsBy(self, dx, dy):
        self._finish_drop_transition()
        super().scrollContentsBy(dx, dy)
        if hasattr(self, "frozen_sequence_header"):
            self.update_frozen_header()
        self.viewport().update()

    def indexAt(self, point):
        index = super().indexAt(point)
        if self.columnCount() >= 7 and 0 <= point.x() < self.columnWidth(0):
            payload = index.siblingAtColumn(0).data(Qt.UserRole)
            if isinstance(payload, tuple) and payload[0] == "invoice":
                return index.siblingAtColumn(0)
        return index

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.columnCount() < 7:
            return
        painter = QPainter(self.viewport())
        theme = getattr(self, "_theme", THEMES[DEFAULT_THEME_KEY])
        item = self.topLevelItem(0)
        row = 0
        while item is not None:
            rect = self.visualItemRect(item)
            if rect.top() >= self.viewport().height():
                break
            payload = item.data(0, Qt.UserRole)
            if rect.bottom() >= 0 and isinstance(payload, tuple) and payload[0] == "invoice":
                frozen_rect = QRect(0, rect.top(), self.columnWidth(0), rect.height())
                option = QStyleOptionViewItem()
                self.initViewItemOption(option)
                option.rect = frozen_rect
                option.widget = self
                if item.isSelected():
                    option.state |= QStyle.State_Selected
                if row % 2 and self.alternatingRowColors():
                    option.features |= QStyleOptionViewItem.Alternate
                painter.fillRect(frozen_rect, QColor(theme["panel_alt"] if row % 2 else theme["panel"]))
                self.itemDelegate().paint(painter, option, self.indexFromItem(item, 0))
                painter.setPen(QColor(theme["border"]))
                painter.drawLine(frozen_rect.topRight(), frozen_rect.bottomRight())
            item = self.itemBelow(item)
            row += 1
        if self._invoice_drop_indicator_y >= 0:
            indicator_color = QColor(theme["accent"])
            y = max(1, min(self._invoice_drop_indicator_y, self.viewport().height() - 2))
            triangle = QPainterPath()
            triangle.moveTo(0, y - 6)
            triangle.lineTo(0, y + 6)
            triangle.lineTo(10, y)
            triangle.closeSubpath()
            painter.fillPath(triangle, indicator_color)
            painter.fillRect(QRect(9, y - 1, self.viewport().width() - 9, 3), indicator_color)
        painter.end()

    def _clear_invoice_drop_indicator(self) -> None:
        if self._invoice_drop_target is None and self._invoice_drop_indicator_y < 0:
            return
        self._invoice_drop_target = None
        self._invoice_drop_indicator_y = -1
        self.viewport().update()

    def _invoice_drop_location(self, point: QPoint) -> tuple[str, int, int, int] | None:
        item = self.itemAt(point)
        if item is None:
            return None
        payload = item.data(0, Qt.UserRole)
        stack_item = None
        insert_index = 0
        indicator_y = -1
        if isinstance(payload, tuple) and payload[0] == MainWindow.STACK_ITEM:
            stack_item = item
            insert_index = stack_item.childCount()
            if insert_index:
                indicator_y = self.visualItemRect(stack_item.child(insert_index - 1)).bottom() + 1
            else:
                indicator_y = self.visualItemRect(stack_item).bottom() + 1
        elif isinstance(payload, tuple) and payload[0] == MainWindow.INVOICE_ITEM and item.parent() is not None:
            stack_item = item.parent()
            row = stack_item.indexOfChild(item)
            rect = self.visualItemRect(item)
            drop_before = point.y() < rect.center().y()
            insert_index = row if drop_before else row + 1
            indicator_y = rect.top() if drop_before else rect.bottom() + 1
        if stack_item is None:
            return None
        stack_payload = stack_item.data(0, Qt.UserRole)
        if not isinstance(stack_payload, tuple) or len(stack_payload) < 3:
            return None
        _, date_str, stack_index = stack_payload
        return date_str, stack_index, insert_index, indicator_y

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-invoice-id") or event.mimeData().hasFormat("application/x-screenshot-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-invoice-id"):
            location = self._invoice_drop_location(event.position().toPoint())
            if location is None:
                self._clear_invoice_drop_indicator()
                event.ignore()
                return
            date_str, stack_index, insert_index, indicator_y = location
            target = (date_str, stack_index, insert_index)
            if target != self._invoice_drop_target or indicator_y != self._invoice_drop_indicator_y:
                self._invoice_drop_target = target
                self._invoice_drop_indicator_y = indicator_y
                self.viewport().update()
            event.acceptProposedAction()
            return
        self._clear_invoice_drop_indicator()
        if event.mimeData().hasFormat("application/x-screenshot-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._clear_invoice_drop_indicator()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._clear_invoice_drop_indicator()
        if event.mimeData().hasFormat("application/x-screenshot-id"):
            raw = bytes(event.mimeData().data("application/x-screenshot-id")).decode("utf-8")
            screenshot_ids = [line for line in raw.splitlines() if line]
            if not screenshot_ids:
                event.ignore()
                return
            item = self.itemAt(event.position().toPoint())
            if item is None:
                event.ignore()
                return
            payload = item.data(0, Qt.UserRole)
            if not isinstance(payload, tuple) or len(payload) < 2 or payload[0] != MainWindow.INVOICE_ITEM:
                event.ignore()
                return
            invoice_id = payload[1]
            before = self._capture_drop_view()
            self.screenshot_dropped.emit(screenshot_ids[0], invoice_id)
            self._animate_drop_transition(before)
            event.acceptProposedAction()
            return

        if not event.mimeData().hasFormat("application/x-invoice-id"):
            event.ignore()
            return

        raw = bytes(event.mimeData().data("application/x-invoice-id")).decode("utf-8")
        invoice_ids = [line for line in raw.splitlines() if line]
        location = self._invoice_drop_location(event.position().toPoint())
        if location is None:
            event.ignore()
            return
        date_str, stack_index, insert_index, _ = location
        before = self._capture_drop_view()
        self.invoice_dropped.emit(invoice_ids, date_str, stack_index, insert_index)
        self._animate_drop_transition(before)
        event.acceptProposedAction()

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole)
        if not isinstance(payload, tuple) or len(payload) < 2 or payload[0] != MainWindow.INVOICE_ITEM:
            return
        invoice_id = payload[1]
        if not invoice_id:
            return
        mime = QMimeData()
        mime.setData("application/x-invoice-id", invoice_id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)
        self._clear_invoice_drop_indicator()


class RemovableComboItemDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        super().paint(painter, option, index)
        view = option.widget
        if not isinstance(view, RemovableComboView) and option.widget is not None:
            view = option.widget.parent()
        delete_rect = view.delete_rect(index) if isinstance(view, RemovableComboView) else QRect()
        if delete_rect.isNull():
            return
        progress = view.delete_hover_progress(index.row()) if isinstance(view, RemovableComboView) else 0.0
        font_size = 11 + progress * 2
        font_weight = round(QFont.DemiBold + (QFont.Black - QFont.DemiBold) * progress)
        base_color = QColor("#5d6b7c")
        hover_color = QColor("#ea4335")
        color = QColor(
            round(base_color.red() + (hover_color.red() - base_color.red()) * progress),
            round(base_color.green() + (hover_color.green() - base_color.green()) * progress),
            round(base_color.blue() + (hover_color.blue() - base_color.blue()) * progress),
        )
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(color)
        font = QFont("Microsoft YaHei UI")
        font.setPointSizeF(font_size)
        font.setWeight(QFont.Weight(font_weight))
        painter.setFont(font)
        painter.drawText(delete_rect, Qt.AlignCenter, "×")
        painter.restore()


class RemovableComboView(QListView):
    remove_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.hover_delete_row = -1
        self._delete_hover_values: dict[int, float] = {}
        self._delete_hover_animations: dict[int, QVariantAnimation] = {}
        self.setMouseTracking(True)
        self.setItemDelegate(RemovableComboItemDelegate(self))

    def delete_rect(self, index) -> QRect:
        if not index.isValid():
            return QRect()
        rect = self.visualRect(index)
        return QRect(rect.right() - 32, rect.top(), 28, rect.height())

    def delete_hover_progress(self, row: int) -> float:
        return self._delete_hover_values.get(row, 0.0)

    def _animate_delete_hover(self, row: int, target: float) -> None:
        if row < 0:
            return
        animation = self._delete_hover_animations.pop(row, None)
        if animation is not None:
            animation.stop()

        start = self._delete_hover_values.get(row, 0.0)
        if abs(start - target) < 0.01:
            self._delete_hover_values[row] = target
            self.viewport().update(self.visualRect(self.model().index(row, 0)))
            return

        animation = QVariantAnimation(self)
        animation.setStartValue(start)
        animation.setEndValue(target)
        animation.setDuration(120)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.valueChanged.connect(lambda value, animated_row=row: self._set_delete_hover_progress(animated_row, float(value)))
        animation.finished.connect(lambda animated_row=row: self._finish_delete_hover_animation(animated_row))
        self._delete_hover_animations[row] = animation
        animation.start()

    def _set_delete_hover_progress(self, row: int, value: float) -> None:
        self._delete_hover_values[row] = value
        self.viewport().update(self.visualRect(self.model().index(row, 0)))

    def _finish_delete_hover_animation(self, row: int) -> None:
        animation = self._delete_hover_animations.pop(row, None)
        if animation is None:
            return
        value = float(animation.endValue())
        if value <= 0.0:
            self._delete_hover_values.pop(row, None)
        else:
            self._delete_hover_values[row] = value
        self.viewport().update(self.visualRect(self.model().index(row, 0)))

    def mouseMoveEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        row = index.row() if index.isValid() and self.delete_rect(index).contains(event.position().toPoint()) else -1
        if row != self.hover_delete_row:
            old_row = self.hover_delete_row
            self.hover_delete_row = row
            self.viewport().setCursor(Qt.PointingHandCursor if row >= 0 else Qt.ArrowCursor)
            if old_row >= 0:
                self._animate_delete_hover(old_row, 0.0)
            if row >= 0:
                self._animate_delete_hover(row, 1.0)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and self.delete_rect(index).contains(event.position().toPoint()):
            self.remove_requested.emit(str(index.data() or ""))
            return
        super().mousePressEvent(event)

    def leaveEvent(self, event):
        old_row = self.hover_delete_row
        self.hover_delete_row = -1
        self.viewport().unsetCursor()
        if old_row >= 0:
            self._animate_delete_hover(old_row, 0.0)
        super().leaveEvent(event)


class RemovableComboBox(QComboBox):
    item_remove_requested = Signal(str)

    def __init__(self):
        super().__init__()
        view = RemovableComboView()
        view.remove_requested.connect(self.item_remove_requested)
        self.setView(view)


class StatusItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = THEMES[DEFAULT_THEME_KEY]

    def set_theme(self, theme: dict) -> None:
        self.theme = theme

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        if not index.data(Qt.DecorationRole):
            super().paint(painter, option, index)
            return

        text = str(index.data(Qt.DisplayRole) or "")
        color = QColor(self.theme["danger"])
        icon_size = 14
        gap = 4

        painter.save()
        self.initStyleOption(option, index)
        option.icon = QIcon()
        option.text = ""
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)

        painter.setFont(option.font)
        text_width = painter.fontMetrics().horizontalAdvance(text)
        total_width = icon_size + gap + text_width
        left = option.rect.left() + max((option.rect.width() - total_width) // 2, 2)
        top = option.rect.top() + (option.rect.height() - icon_size) // 2
        painter.drawPixmap(QRect(left, top, icon_size, icon_size), _themed_svg_pixmap("triangle-alert.svg", color, icon_size))
        painter.setPen(color)
        painter.drawText(
            QRect(left + icon_size + gap, option.rect.top(), text_width + 2, option.rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            text,
        )
        painter.restore()


class StackTreeItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = THEMES[DEFAULT_THEME_KEY]

    def set_theme(self, theme: dict) -> None:
        self.theme = theme

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        payload = index.siblingAtColumn(0).data(Qt.UserRole)
        if isinstance(payload, tuple) and payload[0] == "date":
            hint.setHeight(max(hint.height(), option.fontMetrics.height() + 28, 44))
        return hint

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        row_payload = index.sibling(index.row(), 0).data(Qt.UserRole)
        if not isinstance(row_payload, tuple) or len(row_payload) < 6 or row_payload[0] != "date":
            if isinstance(option.widget, QTreeWidget):
                view = option.widget
            elif option.widget is not None and isinstance(option.widget.parent(), QTreeWidget):
                view = option.widget.parent()
            else:
                view = self.parent()
            is_invoice_row = isinstance(row_payload, tuple) and row_payload[0] == "invoice"
            if is_invoice_row and index.column() == 0:
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing, False)
                sequence_bg = _mix_color(QColor(self.theme["panel_alt"]), QColor(self.theme["border"]), 0.78)
                selected = bool(option.state & QStyle.State_Selected)
                if selected:
                    sequence_bg = _mix_color(sequence_bg, QColor(self.theme["accent"]), 0.30)
                painter.fillRect(option.rect, sequence_bg)
                painter.setFont(option.font)
                painter.setPen(QColor(self.theme["text"] if selected else self.theme["muted"]))
                painter.drawText(option.rect.adjusted(2, 0, -2, 0), Qt.AlignCenter, str(index.data(Qt.DisplayRole) or ""))
                painter.setPen(QColor(self.theme["border"]))
                x = option.rect.right() - 1
                painter.drawLine(x, option.rect.top() + 1, x, option.rect.bottom() - 1)
                painter.restore()
                return

            super().paint(painter, option, index)
            if (
                isinstance(view, QTreeWidget)
                and is_invoice_row
                and index.column() < view.columnCount() - 1
            ):
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing, False)
                painter.setPen(QColor(self.theme["border"]))
                x = option.rect.right() - 1
                painter.drawLine(x, option.rect.top() + 1, x, option.rect.bottom() - 1)
                painter.restore()
            return

        date_str = str(row_payload[1])
        stack_count = int(row_payload[2])
        invoice_count = int(row_payload[3])
        total = float(row_payload[4])
        locked = bool(row_payload[5])
        viewport = option.widget.viewport() if option.widget is not None else None
        full_width = viewport.width() if viewport is not None else option.rect.width()
        row_rect = QRect(6, option.rect.top() + 4, max(full_width - 12, 0), option.rect.height() - 8)
        accent = QColor(self.theme["accent"])
        secondary = QColor(self.theme.get("secondary", self.theme["accent"]))
        highlight = QColor(self.theme.get("highlight", self.theme["accent_soft"]))
        accent_soft = QColor(self.theme["accent_soft"])
        surface = QColor(self.theme["panel"])
        surface_alt = QColor(self.theme["panel_alt"])
        field = QColor(self.theme["field"])
        border = QColor(self.theme["border"])
        text = QColor(self.theme["text"])
        muted = QColor(self.theme["muted"])
        group_bg = _mix_color(surface, accent_soft, 0.36 if not locked else 0.18)
        chip_bg = _mix_color(field, accent_soft, 0.34 if not locked else 0.14)
        secondary_chip_bg = _mix_color(field, highlight, 0.46 if not locked else 0.18)
        neutral_chip_bg = _mix_color(surface_alt, field, 0.55)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(group_bg)
        painter.drawRoundedRect(row_rect, 6, 6)
        row_clip = QPainterPath()
        row_clip.addRoundedRect(row_rect, 6, 6)
        painter.setClipPath(row_clip)

        painter.setBrush(muted if locked else accent)
        painter.drawRoundedRect(QRect(row_rect.left(), row_rect.top(), 4, row_rect.height()), 2, 2)

        icon_rect = QRect(row_rect.left() + 18, row_rect.top() + (row_rect.height() - 18) // 2, 18, 18)
        icon_name = "lock-keyhole.svg" if locked else "calendar-days.svg"
        painter.drawPixmap(icon_rect, _themed_svg_pixmap(icon_name, muted if locked else accent, 18))

        title_font = QFont(option.font)
        title_font.setBold(True)
        title_font.setPointSizeF(title_font.pointSizeF() + 1)
        painter.setFont(title_font)
        painter.setPen(text)
        title_width = painter.fontMetrics().horizontalAdvance(date_str)
        title_rect = QRect(icon_rect.right() + 10, row_rect.top(), title_width, row_rect.height())
        painter.drawText(title_rect, Qt.AlignVCenter | Qt.AlignLeft, date_str)

        chips = [
            (f"{stack_count} 叠", chip_bg, accent if not locked else muted, None),
            (f"{invoice_count} 张", secondary_chip_bg, secondary if not locked else muted, None),
            (f"¥{total:.2f}", neutral_chip_bg, secondary if not locked else text, None),
            ("已锁定" if locked else "可编辑", chip_bg, muted if locked else accent, "lock-keyhole.svg" if locked else "lock-keyhole-open.svg"),
        ]
        chip_font = QFont(option.font)
        chip_font.setBold(True)
        chip_font.setPointSizeF(max(option.font.pointSizeF() - 1, 9))
        painter.setFont(chip_font)
        chip_gap = 8
        chip_widths = [
            painter.fontMetrics().horizontalAdvance(label) + 22 + (18 if icon is not None else 0)
            for label, _, _, icon in chips
        ]
        chip_right = row_rect.right() - 12
        chip_left_limit = title_rect.right() + 16
        available_width = max(chip_right - chip_left_limit, 0)
        chips_width = sum(chip_widths) + chip_gap * (len(chips) - 1)
        if chips_width > available_width:
            # The edit state is the rightmost and most important status. Collapse
            # it to an icon before omitting less important chips on the left.
            label, bg, fg, icon = chips[-1]
            chips[-1] = ("", bg, fg, icon)
            chip_widths[-1] = 32
            chip_gap = 6

        chip_x = chip_right
        chip_height = min(max(painter.fontMetrics().height() + 8, 24), row_rect.height() - 4)
        for (text, bg, fg, icon), chip_width in reversed(list(zip(chips, chip_widths))):
            chip_rect = QRect(chip_x - chip_width, row_rect.center().y() - chip_height // 2, chip_width, chip_height)
            is_status_chip = icon is not None
            if chip_rect.left() < chip_left_limit and not is_status_chip:
                continue
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(chip_rect, 5, 5)
            text_left = chip_rect.left() + 11
            if icon is not None:
                icon_left = chip_rect.left() + ((chip_rect.width() - 14) // 2 if not text else 9)
                icon_rect = QRect(icon_left, chip_rect.top() + (chip_rect.height() - 14) // 2, 14, 14)
                painter.drawPixmap(icon_rect, _themed_svg_pixmap(icon, fg, 14))
                text_left = icon_rect.right() + 6
            if text:
                painter.setPen(fg)
                painter.drawText(QRect(text_left, chip_rect.top(), chip_rect.right() - text_left - 9, chip_rect.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
            chip_x = chip_rect.left() - chip_gap

        painter.setClipping(False)
        painter.setPen(border)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(row_rect.adjusted(0, 0, -1, -1), 6, 6)
        painter.restore()


class HistoryActionButton(QAbstractButton):
    """Fixed geometry and direct SVG painting, independent of QPushButton polish."""

    def __init__(self, filename: str, label: str):
        super().__init__()
        self._svg_source = (ICON_DIR / filename).read_text(encoding="utf-8")
        self._renderers = {}
        self.setAccessibleName(label)
        self.setFixedSize(40, 40)
        self.setFocusPolicy(Qt.StrongFocus)
        self.set_theme(THEMES[DEFAULT_THEME_KEY])

    def set_theme(self, theme):
        self._theme = theme
        for renderer in self._renderers.values():
            renderer.deleteLater()
        self._renderers = {
            state: QSvgRenderer(QByteArray(self._svg_source.replace("#2563eb", theme[color]).encode("utf-8")), self)
            for state, color in (("enabled", "accent"), ("disabled", "muted"))
        }
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        theme = self._theme
        enabled = self.isEnabled()
        hovered = enabled and self.underMouse()
        background = theme["field"] if not enabled else theme["panel"]
        if hovered or self.isDown():
            background = theme["accent_soft"]
        border = theme["accent"] if hovered or self.hasFocus() else theme["border"]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
        # Render SVG paths onto the widget's DPI-aware paint device, rather than
        # scaling a 20-pixel bitmap on high-density displays.
        self._renderers["enabled" if enabled else "disabled"].render(painter, QRect(10, 10, 20, 20))
        painter.end()


class CompactActionButton(QPushButton):
    """Keep the full size hint while allowing the layout to squeeze to a short label."""

    def __init__(self, text: str, compact_text: str):
        self.full_text = text
        self.compact_text = compact_text
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setToolTip(text)

    def sizeHint(self):
        hint = super().sizeHint()
        metrics = self.fontMetrics()
        hint.setWidth(hint.width() + metrics.horizontalAdvance(self.full_text) - metrics.horizontalAdvance(self.text()))
        return hint

    def minimumSizeHint(self):
        hint = self.sizeHint()
        metrics = self.fontMetrics()
        hint.setWidth(hint.width() - metrics.horizontalAdvance(self.full_text) + metrics.horizontalAdvance(self.compact_text))
        return hint

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.compact_text if self.width() < self.sizeHint().width() else self.full_text)


class ThemeCardButton(QPushButton):
    def __init__(self, theme_key: str, parent=None):
        super().__init__(parent)
        self.theme_key = theme_key
        self.theme = THEMES[theme_key]
        self.current_theme = THEMES[DEFAULT_THEME_KEY]
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setMinimumWidth(132)

    def set_card_theme(self, current_theme: dict, selected: bool) -> None:
        self.current_theme = current_theme
        self.setChecked(selected)
        self.update()

    def paintEvent(self, event):
        _ = event
        selected = self.isChecked()
        hovered = self.underMouse()
        accent = QColor(self.theme["accent"])
        card_surface = QColor(self.current_theme["panel"])
        current_soft = QColor(self.current_theme["accent_soft"])
        bg = _mix_color(card_surface, current_soft, 0.58) if selected or hovered else card_surface
        border = accent if selected or hovered else QColor(self.current_theme["border"])
        text = QColor(self.current_theme["text"])

        rect = self.rect().adjusted(0, 0, -1, -1)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 8, 8)

        strip_width = 28
        strip_rect = QRect(rect.left(), rect.top(), strip_width, rect.height())
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, 8, 8)
        painter.setClipPath(card_path)
        painter.setClipRect(strip_rect, Qt.IntersectClip)
        palette = THEME_PALETTES.get(self.theme_key, [self.theme["accent"]])
        segment_height = rect.height() / max(len(palette), 1)
        for index, color in enumerate(palette):
            segment_top = round(rect.top() + index * segment_height)
            segment_bottom = round(rect.top() + (index + 1) * segment_height)
            segment_rect = QRect(rect.left(), segment_top, strip_width, max(segment_bottom - segment_top, 1))
            painter.setBrush(QColor(color))
            painter.drawRect(segment_rect)
        painter.setClipping(False)

        painter.setPen(border)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)

        if selected:
            check_rect = QRect(rect.left() + 8, rect.top() + (rect.height() - 16) // 2, 16, 16)
            painter.drawPixmap(check_rect, _themed_svg_pixmap("check.svg", QColor("#ffffff"), 16))

        text_left = rect.left() + strip_width + 14
        title_font = QFont(self.font())
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(text)
        title_rect = QRect(text_left, rect.top(), rect.width() - text_left - 12, rect.height())
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, self.theme["name"])


class SaveScopeDialog(QDialog):
    def __init__(
        self,
        parent,
        new_stacks: list[dict],
        modified_stacks: list[dict],
        theme: dict,
    ):
        super().__init__(parent)
        self.selected_items: list[dict] | None = None
        self._accent = theme["accent"]
        self._drag_offset: QPoint | None = None
        self._entries = [
            *[(item, "new") for item in new_stacks],
            *[(item, "modified") for item in modified_stacks],
        ]
        self._cards: list[dict] = []
        self._filter_buttons: dict[str, SaveFilterButton] = {}
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(900, 650)
        self.resize(980, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        card = QFrame()
        card.setObjectName("SaveDialogCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(15, 23, 42, 65))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 0)
        layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("SaveDialogHeader")
        header.installEventFilter(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("输出变更")
        title.setObjectName("SaveDialogTitle")
        title.installEventFilter(self)
        header_layout.addWidget(title)
        header_layout.addStretch()
        close_button = QPushButton("×")
        close_button.setObjectName("SaveDialogClose")
        close_button.setFixedSize(36, 36)
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.clicked.connect(self.reject)
        header_layout.addWidget(close_button)
        layout.addWidget(header)

        banner = QFrame()
        banner.setObjectName("SaveDialogBanner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(22, 16, 22, 16)
        banner_layout.setSpacing(16)
        banner_icon = ThemedSvgIcon("layers.svg", QColor(theme["accent"]), 38, 58)
        banner_layout.addWidget(banner_icon)
        banner_text = QVBoxLayout()
        banner_text.setSpacing(4)
        total_count = len(self._entries)
        headline = QLabel(
            f"共检测到&nbsp; <span style='color:{theme['accent']}; font-size:24px; font-weight:900'>"
            f"{total_count} 个需要处理的叠</span>"
        )
        headline.setObjectName("SaveDialogBannerTitle")
        headline.setTextFormat(Qt.RichText)
        explanation = QLabel("当前操作会完整覆盖所选叠中的发票顺序、截图、Excel 和状态文件。")
        explanation.setObjectName("SaveDialogBannerText")
        banner_text.addWidget(headline)
        banner_text.addWidget(explanation)
        banner_layout.addLayout(banner_text, 1)
        layout.addWidget(banner)

        filters = QFrame()
        filters.setObjectName("SaveDialogFilters")
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(4, 4, 4, 4)
        filter_layout.setSpacing(0)
        for key, label, count in (
            ("all", "全部", len(self._entries)),
            ("new", "新增", len(new_stacks)),
            ("modified", "修改", len(modified_stacks)),
        ):
            button = SaveFilterButton(label, count, key, theme)
            button.setChecked(key == "all")
            button.clicked.connect(lambda checked=False, selected=key: self._set_filter(selected))
            self._filter_buttons[key] = button
            filter_layout.addWidget(button)
        filter_layout.addStretch()
        layout.addWidget(filters)

        scroll = QScrollArea()
        scroll.setObjectName("SaveDialogScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setObjectName("SaveDialogScrollViewport")
        scroll_content = QWidget()
        scroll_content.setObjectName("SaveDialogScrollContent")
        self._cards_layout = QVBoxLayout(scroll_content)
        self._cards_layout.setContentsMargins(0, 2, 4, 8)
        self._cards_layout.setSpacing(12)
        for item, kind in self._entries:
            self._cards_layout.addWidget(self._create_stack_card(item, kind, theme))
        self._cards_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("SaveDialogFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 16, 0, 18)
        footer_layout.setSpacing(12)
        self._selected_label = QLabel()
        self._selected_label.setObjectName("SaveDialogSelected")
        self._selected_label.setTextFormat(Qt.RichText)
        footer_layout.addWidget(self._selected_label, 1)
        cancel_button = QPushButton("取消")
        cancel_button.setObjectName("SaveDialogSecondaryButton")
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_button)
        self._save_button = QPushButton("保存并输出")
        self._save_button.setObjectName("SaveDialogPrimaryButton")
        self._save_button.setCursor(Qt.PointingHandCursor)
        self._save_button.clicked.connect(self._accept_selection)
        footer_layout.addWidget(self._save_button)
        layout.addWidget(footer)

        self.setStyleSheet(self._stylesheet(theme))
        self._update_selection()

    def _create_stack_card(self, item: dict, kind: str, theme: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SaveDialogStackCard")
        frame.setProperty("selected", True)
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        main_row = QHBoxLayout()
        main_row.setSpacing(14)
        select_button = SquareCheckButton(theme)
        main_row.addWidget(select_button)

        stack_icon = ThemedSvgIcon("layers.svg", QColor(theme["accent"]), 42, 58)
        main_row.addWidget(stack_icon)

        stack = item["stack"]
        identity_widget = QWidget()
        identity_widget.setObjectName("SaveDialogIdentity")
        identity_widget.setFixedWidth(280)
        identity = QVBoxLayout(identity_widget)
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(5)
        identity_title = QLabel(f"{item['date']} · 第 {stack.index} 叠")
        identity_title.setObjectName("SaveDialogStackTitle")
        identity_meta = QLabel(
            f"{stack.count} 张发票&nbsp;&nbsp;·&nbsp;&nbsp;合计 "
            f"<span style='color:{theme['accent']}; font-size:18px; font-weight:900'>¥{stack.total:.2f}</span>"
        )
        identity_meta.setObjectName("SaveDialogStackMeta")
        identity_meta.setTextFormat(Qt.RichText)
        identity.addWidget(identity_title)
        identity.addWidget(identity_meta)
        main_row.addWidget(identity_widget)

        divider = QFrame()
        divider.setObjectName("SaveDialogVerticalDivider")
        divider.setFixedSize(1, 58)
        main_row.addWidget(divider)

        changes = QVBoxLayout()
        changes.setSpacing(3)
        changes_title = QLabel("文件变化")
        changes_title.setObjectName("SaveDialogChangesTitle")
        changes.addWidget(changes_title)
        for change_text, change_kind in self._change_summary(item, kind):
            change = QLabel(change_text)
            change.setObjectName("SaveDialogAdded" if change_kind == "add" else "SaveDialogRemoved")
            changes.addWidget(change)
        main_row.addLayout(changes)
        main_row.addStretch()

        details_button = QPushButton("查看文件列表  ﹀")
        details_button.setObjectName("SaveDialogDetailsButton")
        details_button.setCheckable(True)
        details_button.setCursor(Qt.PointingHandCursor)
        main_row.addWidget(details_button)
        card_layout.addLayout(main_row)

        details_frame = QFrame()
        details_frame.setObjectName("SaveDialogFileDetails")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(14, 12, 14, 12)
        for detail_line in self._detail_lines(item, kind):
            details_label = QLabel(detail_line)
            if detail_line.startswith("+"):
                details_label.setObjectName("SaveDialogFileAdded")
            elif detail_line.startswith("-"):
                details_label.setObjectName("SaveDialogFileRemoved")
            else:
                details_label.setObjectName("SaveDialogFileNeutral")
            details_label.setWordWrap(True)
            details_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            details_layout.addWidget(details_label)
        details_frame.hide()
        card_layout.addWidget(details_frame)

        entry = {
            "item": item,
            "kind": kind,
            "frame": frame,
            "select": select_button,
            "details": details_frame,
            "details_button": details_button,
        }
        self._cards.append(entry)
        select_button.toggled.connect(lambda checked, current=entry: self._toggle_item(current, checked))
        details_button.toggled.connect(lambda expanded, current=entry: self._toggle_details(current, expanded))
        return frame

    def _change_summary(self, item: dict, kind: str) -> list[tuple[str, str]]:
        if kind == "new":
            invoice_ids = {invoice.invoice_id for invoice in item["stack"].invoices}
            screenshot_count = sum(
                1 for screenshot in item.get("screenshots", [])
                if screenshot.matched_invoice_id in invoice_ids
            )
            return [
                (f"+ {item['stack'].count} 张发票", "add"),
                (f"+ {screenshot_count} 张订单截图", "add"),
            ]
        added = len(item.get("added", []))
        removed = len(item.get("removed", []))
        screenshots_added = len(item.get("screenshots_added", []))
        screenshots_removed = len(item.get("screenshots_removed", []))
        changes: list[tuple[str, str]] = []
        if added or not removed:
            changes.append((f"+ {added} 张发票", "add"))
        if removed:
            changes.append((f"- {removed} 张发票", "remove"))
        if screenshots_added:
            changes.append((f"+ {screenshots_added} 张订单截图", "add"))
        if screenshots_removed:
            changes.append((f"- {screenshots_removed} 张订单截图", "remove"))
        if item.get("order_changed") and len(changes) < 2:
            changes.append(("发票顺序已调整", "add"))
        return changes[:2]

    def _detail_lines(self, item: dict, kind: str) -> list[str]:
        lines: list[str] = []
        if kind == "new":
            lines.extend(f"+ 新增发票：{name}" for name in item.get("added", []))
        else:
            lines.extend(f"+ 新增发票：{name}" for name in item.get("added", []))
            lines.extend(f"- 删除发票：{name}" for name in item.get("removed", []))
            lines.extend(f"+ 新增截图：{name}" for name in item.get("screenshots_added", []))
            lines.extend(f"- 删除截图：{name}" for name in item.get("screenshots_removed", []))
            if item.get("order_changed"):
                lines.append("• 发票顺序已调整")
            if item.get("details_changed"):
                lines.append("• 发票信息、实际报销人或截图绑定已调整")
        return lines or ["没有可列出的文件名称变化"]

    def _set_filter(self, selected: str) -> None:
        for key, button in self._filter_buttons.items():
            button.setChecked(key == selected)
        for entry in self._cards:
            in_scope = selected == "all" or entry["kind"] == selected
            entry["frame"].setVisible(in_scope)
            entry["select"].setChecked(in_scope)

    def _toggle_item(self, entry: dict, checked: bool) -> None:
        entry["frame"].setProperty("selected", checked)
        entry["frame"].style().unpolish(entry["frame"])
        entry["frame"].style().polish(entry["frame"])
        entry["frame"].update()
        self._update_selection()

    def _toggle_details(self, entry: dict, expanded: bool) -> None:
        entry["details"].setVisible(expanded)
        entry["details_button"].setText("收起文件列表  ︿" if expanded else "查看文件列表  ﹀")

    def _update_selection(self) -> None:
        count = sum(1 for entry in self._cards if entry["select"].isChecked())
        self._selected_label.setText(f"已选择&nbsp; <span style='color:{self._accent}; font-size:18px; font-weight:900'>{count}</span> 个叠")
        self._save_button.setEnabled(count > 0)

    def _accept_selection(self) -> None:
        selected = [entry["item"] for entry in self._cards if entry["select"].isChecked()]
        if not selected:
            return
        self.selected_items = selected
        self.accept()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            return True
        if event.type() == QEvent.MouseMove and self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            return True
        if event.type() == QEvent.MouseButtonRelease:
            self._drag_offset = None
            return True
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            self.move(parent.frameGeometry().center() - self.rect().center())

    @staticmethod
    def _stylesheet(theme: dict) -> str:
        return f"""
            QFrame#SaveDialogCard {{
                background: {theme['panel']};
                border: 1px solid {theme['border']};
                border-radius: 18px;
            }}
            QFrame#SaveDialogHeader {{ border: none; background: transparent; }}
            QLabel#SaveDialogTitle {{
                color: {theme['text']}; border: none;
                font-size: 24px; font-weight: 900;
            }}
            QPushButton#SaveDialogClose {{
                color: {theme['text']}; background: transparent; border: none;
                border-radius: 18px; font-size: 25px; font-weight: 400;
            }}
            QPushButton#SaveDialogClose:hover {{ background: {theme['field']}; }}
            QFrame#SaveDialogBanner {{
                background: {theme['accent_soft']}; border: none; border-radius: 14px;
            }}
            QLabel#SaveDialogBannerTitle {{
                color: {theme['text']}; border: none; font-size: 18px; font-weight: 900;
            }}
            QLabel#SaveDialogBannerText {{
                color: {theme['muted']}; border: none; font-size: 14px;
            }}
            QFrame#SaveDialogFilters {{
                background: {theme['field']}; border: 1px solid {theme['border']}; border-radius: 13px;
            }}
            QPushButton#SaveDialogFilter {{
                min-width: 126px; min-height: 42px; padding: 0 16px;
                color: {theme['text']}; background: transparent; border: none;
                border-radius: 10px; font-size: 15px; font-weight: 800;
            }}
            QPushButton#SaveDialogFilter:checked {{ color: white; background: {theme['accent']}; }}
            QScrollArea#SaveDialogScroll, QWidget#SaveDialogScrollViewport, QWidget#SaveDialogScrollContent {{
                background: transparent; border: none;
            }}
            QFrame#SaveDialogStackCard {{
                background: {theme['panel']}; border: 1px solid {theme['border']}; border-radius: 13px;
            }}
            QFrame#SaveDialogStackCard[selected="true"] {{
                background: {theme['accent_soft']}; border: 1px solid {theme['accent']};
            }}
            QLabel#SaveDialogStackTitle {{ color: {theme['text']}; border: none; font-size: 18px; font-weight: 900; }}
            QLabel#SaveDialogStackMeta {{ color: {theme['muted']}; border: none; font-size: 14px; }}
            QFrame#SaveDialogVerticalDivider {{ background: {theme['border']}; border: none; }}
            QLabel#SaveDialogChangesTitle {{ color: {theme['text']}; border: none; font-size: 14px; font-weight: 900; }}
            QLabel#SaveDialogAdded {{ color: {theme['success']}; border: none; font-size: 14px; font-weight: 800; }}
            QLabel#SaveDialogRemoved {{ color: {theme['danger']}; border: none; font-size: 14px; font-weight: 800; }}
            QPushButton#SaveDialogDetailsButton {{
                min-width: 146px; min-height: 40px; padding: 0 12px;
                color: {theme['muted']}; background: {theme['panel']};
                border: 1px solid {theme['border']}; border-radius: 9px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton#SaveDialogDetailsButton:hover {{ color: {theme['accent']}; border-color: {theme['accent']}; }}
            QFrame#SaveDialogFileDetails {{
                background: {theme['panel']}; border: 1px solid {theme['border']}; border-radius: 9px;
            }}
            QLabel#SaveDialogFileAdded {{ color: {theme['success']}; border: none; font-size: 13px; }}
            QLabel#SaveDialogFileRemoved {{ color: {theme['danger']}; border: none; font-size: 13px; }}
            QLabel#SaveDialogFileNeutral {{ color: {theme['muted']}; border: none; font-size: 13px; }}
            QFrame#SaveDialogFooter {{
                background: {theme['panel']}; border: none; border-top: 1px solid {theme['border']};
            }}
            QLabel#SaveDialogSelected {{ color: {theme['text']}; border: none; font-size: 15px; font-weight: 800; }}
            QPushButton#SaveDialogSecondaryButton, QPushButton#SaveDialogPrimaryButton {{
                min-width: 128px; min-height: 48px; padding: 0 18px;
                border-radius: 10px; font-size: 16px; font-weight: 900;
            }}
            QPushButton#SaveDialogSecondaryButton {{
                color: {theme['text']}; background: {theme['panel']}; border: 1px solid {theme['border']};
            }}
            QPushButton#SaveDialogSecondaryButton:hover {{ background: {theme['field']}; }}
            QPushButton#SaveDialogPrimaryButton {{
                color: white; background: {theme['accent']}; border: 1px solid {theme['accent']};
            }}
            QPushButton#SaveDialogPrimaryButton:hover {{ background: {theme['accent_hover']}; }}
            QPushButton#SaveDialogPrimaryButton:disabled {{ color: {theme['muted']}; background: {theme['field']}; border-color: {theme['border']}; }}
        """


def workspace_edit(label):
    def decorate(method):
        @wraps(method)
        def wrapped(self, *args, **kwargs):
            if self._workspace_busy():
                return
            outer = self._history_depth == 0
            before = self._capture_workspace() if outer else None
            self._history_depth += 1
            try:
                return method(self, *args, **kwargs)
            finally:
                self._history_depth -= 1
                if outer:
                    self._record_workspace_edit(label, before)
        return wrapped
    return decorate


class MainWindow(QMainWindow):
    DATE_ITEM = "date"
    STACK_ITEM = "stack"
    INVOICE_ITEM = "invoice"

    def __init__(self):
        super().__init__()
        self.settings_path = Path(__file__).resolve().parent.parent / SETTINGS_FILE
        self.settings = self._load_settings()
        self.invoices: list[Invoice] = []
        self.screenshots: list[OrderScreenshot] = []
        self.stacks: list[Stack] = []
        self.date_groups: list[DateGroup] = []
        self.batch: Batch | None = None
        self.mode = "new"
        self._worker: ParseWorker | None = None
        self._pending_paths: list[Path] = []
        self._screenshot_worker: ScreenshotParseWorker | None = None
        self._pending_screenshot_paths: list[Path] = []
        self._opened_stack_snapshots: dict[tuple[str, int], dict] = {}
        self._undo_history = []
        self._redo_history = []
        self._history_depth = 0
        self._import_before = None
        self._parsing_invoices = False
        self._parsing_screenshots = False
        self._update_worker = None
        self._update_release = None
        self._downloaded_installer = None

        self._build_ui()
        for button in self.findChildren(QPushButton):
            if button.objectName() in ("PrimaryButton", "SecondaryButton", "OutlineButton"):
                button.installEventFilter(self)
        self._install_shortcuts()
        self.setWindowTitle("HDU 发票工作台")
        self.resize(1480, 900)
        self.setMinimumSize(1220, 760)
        self.setAcceptDrops(True)
        self._apply_theme_settings()
        self._apply_rule_settings()
        self._apply_output_settings()
        self._apply_reimburser_settings()
        self._apply_remark_settings()
        self._render_all()
        self._update_bind_hint()

    def showEvent(self, event):
        super().showEvent(event)
        # The splitter receives its final size only after the top-level window is shown.
        # Reposition overlays on the next event-loop turn instead of keeping the
        # construction-time geometry until the user moves the splitter.
        QTimer.singleShot(0, self._position_all_empty_hints)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "tree"):
            QTimer.singleShot(0, self._position_all_empty_hints)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        layout.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_invoice_page())
        self.pages.addWidget(self._build_placeholder_page("财务分析"))
        self.pages.addWidget(self._build_help_page())
        self.pages.addWidget(self._build_settings_page())
        layout.addWidget(self.pages, 1)
        self._switch_page(0)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(8)

        logo = QLabel()
        logo.setObjectName("BrandLogo")
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignCenter)
        self.brand_logo = logo
        layout.addWidget(logo, 0, Qt.AlignHCenter)

        brand = QLabel("HDU 发票工作台")
        brand.setObjectName("BrandTitle")
        brand.setAlignment(Qt.AlignCenter)
        brand.setWordWrap(True)
        brand.setMinimumWidth(180)
        layout.addWidget(brand)

        subtitle = QLabel("- All in one -")
        subtitle.setObjectName("BrandSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        self.nav_buttons: list[QPushButton] = []
        self.nav_icon_files: list[str] = []
        nav_items = [
            ("发票分叠", "layers.svg"),
            ("财务分析", "chart.svg"),
            ("使用说明", "book-open.svg"),
        ]
        for index, (text, icon) in enumerate(nav_items):
            button = QPushButton(f"  {text}")
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setFixedHeight(54)
            button.setIcon(self._icon(icon))
            button.setIconSize(QSize(20, 20))
            button.clicked.connect(lambda _checked=False, page=index: self._switch_page(page))
            self.nav_buttons.append(button)
            self.nav_icon_files.append(icon)
            layout.addWidget(button)

        layout.addStretch()
        settings_button = QPushButton("  设置")
        settings_button.setObjectName("NavButton")
        settings_button.setCheckable(True)
        settings_button.setFixedHeight(54)
        settings_button.setIcon(self._icon("settings.svg"))
        settings_button.setIconSize(QSize(20, 20))
        settings_button.clicked.connect(lambda _checked=False: self._switch_page(3))
        self.nav_buttons.append(settings_button)
        self.nav_icon_files.append("settings.svg")
        layout.addWidget(settings_button)
        return sidebar

    def _icon(self, filename: str, active: bool = False) -> QIcon:
        icon_path = ICON_DIR / filename
        if active:
            icon_path = ICON_DIR / filename.replace(".svg", "-active.svg")
        return QIcon(str(icon_path))

    def _build_invoice_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_workspace_header())

        self.workspace_splitter = QSplitter(Qt.Horizontal)
        self.workspace_splitter.setObjectName("WorkspaceSplitter")
        self.workspace_splitter.setHandleWidth(18)
        self.workspace_splitter.addWidget(self._build_left())
        self.workspace_splitter.addWidget(self._build_right())
        self.workspace_splitter.setSizes([780, 620])
        self.workspace_splitter.splitterMoved.connect(lambda _pos, _index: self._position_all_empty_hints())
        layout.addWidget(self.workspace_splitter, 1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.screenshot_progress = QProgressBar()
        self.screenshot_progress.setTextVisible(True)
        self.screenshot_progress.setVisible(False)
        layout.addWidget(self.screenshot_progress)
        return page

    def _build_workspace_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("TopPanel")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(2)
        title = QLabel("发票分叠")
        title.setObjectName("PageTitle")
        title_group.addWidget(title)
        title_row.addLayout(title_group, 1)

        self.btn_undo = HistoryActionButton("undo-2.svg", "撤销")
        self.btn_undo.clicked.connect(self._undo_workspace)
        title_row.addWidget(self.btn_undo)
        self.btn_redo = HistoryActionButton("redo-2.svg", "重做")
        self.btn_redo.clicked.connect(self._redo_workspace)
        title_row.addWidget(self.btn_redo)

        self.btn_open = QPushButton("打开已有叠")
        self.btn_open.setObjectName("PrimaryButton")
        self.btn_open.setFixedHeight(40)
        self.btn_open.clicked.connect(self._open_batch)
        title_row.addWidget(self.btn_open)

        self.btn_save_output = QPushButton("保存并输出")
        self.btn_save_output.setObjectName("SecondaryButton")
        self.btn_save_output.setFixedHeight(40)
        self.btn_save_output.clicked.connect(self._save_output)
        title_row.addWidget(self.btn_save_output)
        layout.addLayout(title_row)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("输出路径"))
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("选择输出文件夹...")
        self.edit_output.textChanged.connect(self._on_output_path_changed)
        controls.addWidget(self.edit_output, 1)

        btn_browse = QPushButton("浏览")
        btn_browse.setObjectName("OutlineButton")
        btn_browse.setFixedHeight(36)
        btn_browse.clicked.connect(self._browse)
        controls.addWidget(btn_browse)

        controls.addSpacing(8)
        controls.addWidget(QLabel("预约人"))
        self.combo_reimburser = RemovableComboBox()
        self.combo_reimburser.setEditable(True)
        self.combo_reimburser.setMinimumWidth(170)
        self.combo_reimburser.currentTextChanged.connect(self._on_reimburser_changed)
        self.combo_reimburser.item_remove_requested.connect(self._remove_common_reimburser_value)
        controls.addWidget(self.combo_reimburser)
        layout.addLayout(controls)
        return header

    def _build_placeholder_page(self, title_text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        panel = QFrame()
        panel.setObjectName("TopPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(6)
        title = QLabel(title_text)
        title.setObjectName("PageTitle")
        panel_layout.addWidget(title)
        subtitle = QLabel("预留模块，待拓展（懒得写了哈哈）")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        panel_layout.addWidget(subtitle)
        layout.addWidget(panel)

        empty = QFrame()
        empty.setObjectName("EmptyPanel")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.addStretch()
        label = QLabel("功能预留")
        label.setObjectName("EmptyTitle")
        label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(label)
        empty_layout.addStretch()
        layout.addWidget(empty, 1)
        return page

    def _build_help_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("TopPanel")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 18, 22, 18)
        header_layout.setSpacing(6)
        title = QLabel("使用说明")
        title.setObjectName("PageTitle")
        header_layout.addWidget(title)
        version = QLabel(f"适用版本 v{APP_VERSION}")
        version.setObjectName("HelpVersion")
        header_layout.addWidget(version)
        page_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("HelpScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setObjectName("HelpScrollViewport")

        content = QWidget()
        content.setObjectName("HelpContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 10, 12)
        content_layout.setSpacing(12)

        sections = [
            (
                "01",
                "基础使用",
                "选择输出路径并填写预约人；把 PDF 发票拖入“发票”，把 JPG / PNG 订单截图拖入“订单截图”。",
                [
                    "左侧数量只统计仍未分类、未匹配的文件；框内为空时显示 0 张。",
                    "选中右侧目标叠和左侧发票后，点击“加入所选叠”；实际报销人会在加入时写入这些发票。",
                    "拖动左右分隔栏可以调整宽度；左侧变窄时，“一键分叠 / 加入所选叠”会先缩为“一键 / 加入”，继续左拉可收起左侧。",
                ],
            ),
            (
                "02",
                "一键分叠",
                "点击“一键分叠”，自动处理左侧所有已识别金额的发票，无需逐张选择。",
                [
                    "工作区没有叠时，按今天的日期新建；已有叠时，优先使用右侧所选叠的日期，没有选中叠则使用日期框中的日期。",
                    "先放入目标日期下仍能容纳的已有叠；只有所有已有叠都无法同时满足张数和金额预设时，才新建下一叠。",
                    "分叠同时遵守设置中的“每叠最多张数”和“金额不超过”，并写入当前实际报销人。",
                    "单张金额超过每叠上限或金额未识别的发票会留在左侧；已分叠的发票不会再次分配。",
                ],
            ),
            (
                "03",
                "重复发票会被主动拦截",
                "导入时在后台读取发票号码，与左侧列表及右侧已打开各叠中的发票比较，不依赖文件名。",
                [
                    "同一路径文件再次拖入时会直接提示“已存在”，不会重复解析。",
                    "发票号码相同时，新导入文件会自动跳过并提示；改名或缺少发票代码不影响查重。",
                    "提示会标明发票号码和已有位置，可定位文件，或将新增的重复 PDF 移入回收站。",
                    "重复提示会直接弹出并临时置顶；关闭提示后，主窗口恢复正常显示。",
                    "金额未识别时仍会按已识别的号码查重；号码未识别时，左侧状态会提示“未识别发票号码，无法查重”。",
                ],
            ),
            (
                "04",
                "截图匹配不会擅自猜测",
                "订单截图会识别实付款，只有金额对应关系唯一时才会自动绑定。",
                [
                    "同一金额出现多张截图时显示“截图金额重复”；出现多张发票时显示“发票金额重复”，并留给人工处理。",
                    "没有同金额发票时会明确显示“未找到同金额发票”，不会随意绑定到其他金额。",
                    "手动绑定金额不一致的发票和截图时会再次确认；选择继续后才会建立绑定。",
                    "一张发票只保留一张截图；重新绑定时，旧截图会自动解除，避免同一发票挂两张订单图。",
                ],
            ),
            (
                "05",
                "拖动调整与 Delete 删除",
                "Delete 的作用取决于当前操作的区域，发票区和订单截图区均支持多选。",
                [
                    "右侧选中发票按 Delete，会将发票及绑定截图返还左侧，同时解除绑定；也可将发票直接拖回左侧。",
                    "左侧选中发票或订单截图按 Delete，只从工作区移除所选项目，源文件仍然保留。",
                    "右侧支持拖动排序，行间插入线和左侧三角形表示准确位置；松手后保留滚动位置，并显示短暂过渡动画。",
                    "手动调整可能造成超限；超限叠会显示警告标记，并在保存时列出超出的张数或金额并停止输出。",
                    "拖动发票换叠后，已绑定截图的叠序会同步更新，不需要重新绑定。",
                    "右侧序号列固定，选中行时序号也会加深；长文件名可横向滚动查看。",
                ],
            ),
            (
                "06",
                "撤销与重做",
                "“打开已有叠”左侧的两个回转箭头分别是撤销和重做，悬停可查看操作名称及快捷键。",
                [
                    "Ctrl+Z 撤销，Ctrl+Y 重做；支持导入、删除、分叠、移动、空叠增删、截图绑定和日期锁定操作。",
                    "撤销会一起恢复发票所在叠、叠编号和截图绑定；最近保留 50 步记录。",
                    "撤销后执行新的编辑，会清空原来的重做记录；保存或打开其他工作区后，撤销记录也会清空。",
                    "后台识别期间暂时禁用撤销与重做，导入完成后作为一步记录；输入框中的 Ctrl+Z / Ctrl+Y 用于撤销或重做文字修改。",
                ],
            ),
            (
                "07",
                "打开已有叠时的编辑保护",
                "程序会递归查找所选目录中的 invoices.json，按日期合并载入已有叠。",
                [
                    "载入后各日期默认锁定，仅自动解锁最新日期；点击日期行可切换锁定状态。锁定日期不能拖入、拖出、新建或重新分叠。",
                    "保存只处理已解锁日期，并比较发票增删、顺序、信息、实际报销人和截图绑定等变化。",
                    "确认窗口可筛选“全部 / 新增 / 修改”，并选择仅新增、仅修改或新增并修改；新增显示绿色，删除显示红色。",
                    "没有检测到变化时会直接提示无需输出，避免无意义地重复覆盖文件。",
                ],
            ),
            (
                "08",
                "输出时会先准备、再整体替换",
                "选中的叠会先在临时目录中完整生成，全部准备成功后才替换正式目录。",
                [
                    "修改已有叠会按当前顺序重新生成发票、订单截图、Excel 和 invoices.json，不保留旧顺序或旧文件。",
                    "替换前会暂存旧目录；如果中途出错，会恢复已备份内容，避免留下只写了一半的叠。",
                    "发票和截图按“序号、金额”重新命名；截图序号与所绑定发票保持一致。",
                    "Excel 包含序号、项目名称、发票代码、发票号码、发票金额和实际报销人。若文件被占用，请关闭后重试。",
                ],
            ),
            (
                "09",
                "当前版本与更新",
                "设置页会显示当前版本；使用说明标题下的“适用版本”与其保持一致。",
                [
                    "填写公开 GitHub 仓库地址后点击“检查更新”，程序会在后台查找最新正式 Release；未发布版本时会明确提示。",
                    "发现带有可校验 Windows 安装包的新版后，“一键更新”才会启用；没有安装包时可点击“查看发布说明”。",
                    "更新前先保存工作区；安装包下载完成并通过校验后，启动安装程序，按提示完成升级。",
                    "源码运行环境不会被直接覆盖；安装包用于创建或升级已安装的 Windows 应用。",
                ],
            ),
        ]
        for number, section_title, summary, points in sections:
            content_layout.addWidget(self._make_help_section(number, section_title, summary, points))

        content_layout.addStretch()
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        return page

    def _make_help_section(self, number: str, title: str, summary: str, points: list[str]) -> QFrame:
        card = QFrame()
        card.setObjectName("HelpCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 17, 20, 18)
        layout.setSpacing(16)

        badge = QLabel(number)
        badge.setObjectName("HelpNumber")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(42, 42)
        layout.addWidget(badge, 0, Qt.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(7)
        heading = QLabel(title)
        heading.setObjectName("HelpCardTitle")
        body.addWidget(heading)
        summary_label = QLabel(summary)
        summary_label.setObjectName("HelpCardSummary")
        summary_label.setWordWrap(True)
        body.addWidget(summary_label)
        for point in points:
            point_label = QLabel(f"•  {point}")
            point_label.setObjectName("HelpBullet")
            point_label.setWordWrap(True)
            body.addWidget(point_label)
        layout.addLayout(body, 1)
        return card

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        panel = QFrame()
        panel.setObjectName("TopPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(6)
        title = QLabel("设置")
        title.setObjectName("PageTitle")
        panel_layout.addWidget(title)
        layout.addWidget(panel)

        self.version_panel = VersionPanel()
        version_layout = QVBoxLayout(self.version_panel)
        version_layout.setContentsMargins(22, 18, 22, 18)
        version_layout.setSpacing(10)
        version_row = QHBoxLayout()
        version_labels = QVBoxLayout()
        version_labels.setSpacing(2)
        caption = QLabel("当前版本")
        caption.setObjectName("HelperText")
        version_labels.addWidget(caption)
        version_number = QLabel(f"v{APP_VERSION}")
        version_number.setObjectName("VersionNumber")
        version_labels.addWidget(version_number)
        version_row.addLayout(version_labels)
        version_row.addStretch()
        self.btn_check_updates = QPushButton("检查更新")
        self.btn_check_updates.setObjectName("OutlineButton")
        self.btn_check_updates.setFixedHeight(36)
        self.btn_check_updates.clicked.connect(self._check_updates)
        version_row.addWidget(self.btn_check_updates)
        self.btn_install_update = QPushButton("一键更新")
        self.btn_install_update.setObjectName("PrimaryButton")
        self.btn_install_update.setFixedHeight(36)
        self.btn_install_update.setEnabled(False)
        self.btn_install_update.clicked.connect(self._install_update)
        version_row.addWidget(self.btn_install_update)
        version_layout.addLayout(version_row)
        repository_row = QHBoxLayout()
        repository_row.addWidget(QLabel("GitHub 仓库"))
        self.edit_update_repository = QLineEdit(self.settings.get("github_repository", GITHUB_REPOSITORY))
        self.edit_update_repository.setPlaceholderText("https://github.com/用户名/HDU-InvoiceAllInOne")
        self.edit_update_repository.editingFinished.connect(self._save_update_repository)
        repository_row.addWidget(self.edit_update_repository, 1)
        version_layout.addLayout(repository_row)
        self.lbl_update_status = QLabel("设置 GitHub 仓库后，即可检查正式版本更新。")
        self.lbl_update_status.setObjectName("HelperText")
        self.lbl_update_status.setWordWrap(True)
        version_layout.addWidget(self.lbl_update_status)
        self.btn_release_page = QPushButton("查看发布说明")
        self.btn_release_page.setObjectName("OutlineButton")
        self.btn_release_page.setVisible(False)
        self.btn_release_page.clicked.connect(self._open_release_page)
        version_layout.addWidget(self.btn_release_page, 0, Qt.AlignLeft)
        layout.addWidget(self.version_panel)

        theme_panel = QFrame()
        theme_panel.setObjectName("Panel")
        theme_layout = QVBoxLayout(theme_panel)
        theme_layout.setContentsMargins(16, 14, 16, 14)
        theme_layout.setSpacing(10)

        theme_title = QLabel("界面配色")
        theme_title.setObjectName("SectionTitle")
        theme_layout.addWidget(theme_title)

        swatches = QGridLayout()
        swatches.setHorizontalSpacing(10)
        swatches.setVerticalSpacing(8)
        self.theme_buttons: dict[str, ThemeCardButton] = {}
        for index, key in enumerate(THEMES):
            button = ThemeCardButton(key)
            button.clicked.connect(lambda _checked=False, theme_key=key: self._select_theme(theme_key))
            self.theme_buttons[key] = button
            swatches.addWidget(button, index // 5, index % 5)
        for column in range(5):
            swatches.setColumnStretch(column, 1)
        theme_layout.addLayout(swatches)
        layout.addWidget(theme_panel)

        rule_panel = QFrame()
        rule_panel.setObjectName("Panel")
        rule_layout = QVBoxLayout(rule_panel)
        rule_layout.setContentsMargins(16, 14, 16, 14)
        rule_layout.setSpacing(10)

        rule_title = QLabel("分叠规则")
        rule_title.setObjectName("SectionTitle")
        rule_layout.addWidget(rule_title)

        rule_row = QHBoxLayout()
        rule_row.setSpacing(10)
        rule_row.addWidget(QLabel("每叠最多"))
        self.spin_max_count = QSpinBox()
        self.spin_max_count.setRange(1, 999)
        self.spin_max_count.setValue(MAX_COUNT)
        self.spin_max_count.setSuffix(" 张")
        self.spin_max_count.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_max_count.setFixedWidth(92)
        self.spin_max_count.valueChanged.connect(self._on_rule_changed)
        rule_row.addWidget(self.spin_max_count)
        rule_row.addWidget(QLabel("金额不超过"))
        self.spin_max_amount = QDoubleSpinBox()
        self.spin_max_amount.setRange(0.01, 99999999.99)
        self.spin_max_amount.setDecimals(2)
        self.spin_max_amount.setSingleStep(100.0)
        self.spin_max_amount.setValue(MAX_AMOUNT)
        self.spin_max_amount.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_max_amount.setFixedWidth(128)
        self.spin_max_amount.valueChanged.connect(self._on_rule_changed)
        rule_row.addWidget(self.spin_max_amount)
        rule_row.addStretch()
        rule_layout.addLayout(rule_row)
        layout.addWidget(rule_panel)

        layout.addStretch()
        return page

    def _save_update_repository(self):
        value = self.edit_update_repository.text().strip()
        if value:
            try:
                value = normalize_repository(value)
            except ValueError as error:
                self.lbl_update_status.setText(str(error))
                self._update_release = None
                self._downloaded_installer = None
                self.btn_install_update.setEnabled(False)
                self.btn_release_page.setVisible(False)
                return
        if value != self.settings.get("github_repository", GITHUB_REPOSITORY):
            self.settings["github_repository"] = value
            self._save_settings()
            self._update_release = None
            self._downloaded_installer = None
            self.btn_install_update.setEnabled(False)
            self.btn_release_page.setVisible(False)

    def _check_updates(self):
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        try:
            repository = normalize_repository(self.edit_update_repository.text())
        except ValueError as error:
            self.lbl_update_status.setText(str(error))
            return
        self._save_update_repository()
        self._update_release = None
        self._downloaded_installer = None
        self.btn_install_update.setEnabled(False)
        self.btn_release_page.setVisible(False)
        self.lbl_update_status.setText("正在检查 GitHub 正式版本…")
        self._start_update_worker(UpdateWorker(repository), self._on_update_checked)

    def _start_update_worker(self, worker, callback):
        self._update_worker = worker
        self.btn_check_updates.setEnabled(False)
        self.edit_update_repository.setEnabled(False)
        worker.result.connect(callback)
        worker.failed.connect(self._on_update_error)
        worker.finished.connect(self._on_update_finished)
        worker.start()

    def _on_update_finished(self):
        self.btn_check_updates.setEnabled(True)
        self.edit_update_repository.setEnabled(True)

    def _on_update_checked(self, release):
        self._update_release = release
        self.btn_release_page.setVisible(True)
        newer = version_tuple(release.version) > version_tuple(APP_VERSION)
        self.btn_install_update.setEnabled(newer and release.asset is not None)
        if not newer:
            self.lbl_update_status.setText(f"当前已是最新版本 v{APP_VERSION}。")
        elif release.asset is None:
            self.lbl_update_status.setText(f"发现 {release.version}，此版本尚未提供可校验的安装包，可前往发布页查看。")
        else:
            self.lbl_update_status.setText(f"发现 {release.version}，可一键下载并启动安装。")

    def _on_update_error(self, message):
        self.lbl_update_status.setText(f"更新未完成：{message}")
        release = self._update_release
        self.btn_install_update.setEnabled(bool(release and release.asset and version_tuple(release.version) > version_tuple(APP_VERSION)))

    def _open_release_page(self):
        if self._update_release:
            QDesktopServices.openUrl(QUrl(self._update_release.url))

    def _install_update(self):
        if not self._update_release or not self._update_release.asset:
            return
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        if self._workspace_busy() or self._undo_history:
            self.lbl_update_status.setText("请先完成识别并保存工作区，再进行更新。")
            return
        if self._downloaded_installer is not None and self._downloaded_installer.is_file():
            self._on_installer_ready(self._downloaded_installer)
            return
        self.btn_install_update.setEnabled(False)
        worker = UpdateWorker(normalize_repository(self.edit_update_repository.text()), self._update_release)
        worker.progress.connect(lambda value: self.lbl_update_status.setText(f"正在下载安装包… {value}%"))
        self._start_update_worker(worker, self._on_installer_ready)

    def _on_installer_ready(self, path):
        self._downloaded_installer = path
        if self._workspace_busy() or self._undo_history:
            self.lbl_update_status.setText("安装包已下载；请先保存工作区，再点击“一键更新”。")
            self.btn_install_update.setEnabled(True)
            return
        try:
            if path.suffix.lower() == ".msi":
                subprocess.Popen(["msiexec.exe", "/i", str(path)])
            else:
                subprocess.Popen([str(path)])
            self.lbl_update_status.setText("安装程序已启动，请按安装提示完成更新。")
        except OSError as error:
            self._on_update_error(str(error))

    def closeEvent(self, event):
        if self._update_worker is not None and self._update_worker.isRunning():
            self._switch_page(3)
            self.lbl_update_status.setText("更新任务仍在进行，请完成后再关闭窗口。")
            event.ignore()
            return
        super().closeEvent(event)

    def _switch_page(self, index: int) -> None:
        if not hasattr(self, "pages"):
            return
        self.pages.setCurrentIndex(index)
        for button_index, button in enumerate(getattr(self, "nav_buttons", [])):
            active = button_index == index
            button.setChecked(active)
            button.setProperty("active", active)
            if button_index < len(getattr(self, "nav_icon_files", [])):
                button.setIcon(self._icon(self.nav_icon_files[button_index], active))
            button.style().unpolish(button)
            button.style().polish(button)

    def _install_shortcuts(self) -> None:
        self._delete_shortcuts = []
        for view, handler in ((self.tree, self._delete_selected_tree_invoices),
                              (self.table, self._delete_selected_left_invoices),
                              (self.screenshot_table, self._delete_selected_left_screenshots)):
            shortcut = QShortcut(QKeySequence("Delete"), view)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._delete_shortcuts.append(shortcut)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self._undo_workspace)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self._redo_workspace)

    def _workspace_busy(self):
        return self._parsing_invoices or self._parsing_screenshots

    def _capture_workspace(self):
        # Copy the whole graph together to preserve invoice and stack aliases.
        return deepcopy({
            "invoices": self.invoices, "screenshots": self.screenshots,
            "stacks": self.stacks, "date_groups": self.date_groups,
            "batch": self.batch, "mode": self.mode,
            "date": self.date_edit.date().toString(Qt.ISODate),
        })

    def _record_workspace_edit(self, label, before):
        after = self._capture_workspace()
        if before != after:
            self._undo_history.append((label, before, after))
            del self._undo_history[:-50]
            self._redo_history.clear()
        self._refresh_buttons()

    def _restore_workspace(self, snapshot):
        state = deepcopy(snapshot)
        for name in ("invoices", "screenshots", "stacks", "date_groups", "batch", "mode"):
            setattr(self, name, state[name])
        self.date_edit.setDate(QDate.fromString(state["date"], Qt.ISODate))
        self._render_all()
        self._update_bind_hint()

    def _undo_workspace(self):
        focused = self.focusWidget()
        if isinstance(focused, QLineEdit):
            focused.undo()
            return
        if self._workspace_busy() or not self._undo_history:
            return
        entry = self._undo_history.pop()
        self._redo_history.append(entry)
        self._restore_workspace(entry[1])

    def _redo_workspace(self):
        focused = self.focusWidget()
        if isinstance(focused, QLineEdit):
            focused.redo()
            return
        if self._workspace_busy() or not self._redo_history:
            return
        entry = self._redo_history.pop()
        self._undo_history.append(entry)
        self._restore_workspace(entry[2])

    def _finish_import_history(self):
        if not self._workspace_busy() and self._import_before is not None:
            before, self._import_before = self._import_before, None
            self._record_workspace_edit("导入文件", before)

    def _reset_workspace_history(self):
        self._undo_history.clear()
        self._redo_history.clear()
        self._import_before = None
        self._refresh_buttons()

    def _build_left(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(18, 18, 18, 18)
        vbox.setSpacing(16)

        invoice_frame = QFrame()
        invoice_frame.setObjectName("SubPanel")
        invoice_layout = QVBoxLayout(invoice_frame)
        invoice_layout.setContentsMargins(0, 0, 0, 0)
        invoice_layout.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel("发票")
        title.setObjectName("SectionTitle")
        top.addWidget(title)
        title_sep = QFrame()
        title_sep.setObjectName("SectionSeparator")
        title_sep.setFrameShape(QFrame.VLine)
        title_sep.setFrameShadow(QFrame.Plain)
        title_sep.setFixedHeight(18)
        top.addSpacing(8)
        top.addWidget(title_sep)
        top.addSpacing(8)
        self.lbl_count = QLabel("0 张")
        self.lbl_count.setObjectName("CounterLabel")
        self.lbl_count.setAlignment(Qt.AlignCenter)
        self.lbl_count.setFixedHeight(24)
        top.addWidget(self.lbl_count)
        top.addStretch()
        top.addWidget(QLabel("实际报销人:"))
        self.combo_remark = RemovableComboBox()
        self.combo_remark.setEditable(True)
        self.combo_remark.setFixedWidth(self.fontMetrics().horizontalAdvance("实际报销人") + 56)
        self.combo_remark.currentTextChanged.connect(self._on_remark_changed)
        self.combo_remark.item_remove_requested.connect(self._remove_common_remark_value)
        top.addWidget(self.combo_remark)
        self.btn_split_stacks = CompactActionButton("一键分叠", "一键")
        self.btn_split_stacks.setObjectName("PrimaryButton")
        self.btn_split_stacks.setFixedHeight(40)
        self.btn_split_stacks.setToolTip("将左侧全部已识别发票按张数和金额预设自动分叠")
        self.btn_split_stacks.clicked.connect(self._split_left_invoices_into_stacks)
        top.addWidget(self.btn_split_stacks)
        self.btn_assign_selected = CompactActionButton("加入所选叠", "加入")
        self.btn_assign_selected.setObjectName("SecondaryButton")
        self.btn_assign_selected.setFixedHeight(40)
        self.btn_assign_selected.clicked.connect(self._assign_selected_invoices_to_current_stack)
        top.addWidget(self.btn_assign_selected)
        invoice_layout.addLayout(top)

        self.table = InvoiceTable()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["文件名", "金额", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 72)
        self.table.setColumnWidth(2, 88)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.invoice_status_delegate = StatusItemDelegate(self.table)
        self.table.setItemDelegateForColumn(2, self.invoice_status_delegate)
        self._install_table_empty_hint(self.table)
        self.table.files_dropped.connect(self._on_drop)
        self.table.invoice_dropped_to_left.connect(self._return_invoices_to_left)
        invoice_layout.addWidget(self.table)
        vbox.addWidget(invoice_frame, 1)

        screenshot_frame = QFrame()
        screenshot_frame.setObjectName("SubPanel")
        screenshot_layout = QVBoxLayout(screenshot_frame)
        screenshot_layout.setContentsMargins(0, 0, 0, 0)
        screenshot_layout.setSpacing(6)

        screenshot_top = QHBoxLayout()
        screenshot_title = QLabel("订单截图")
        screenshot_title.setObjectName("SectionTitle")
        screenshot_top.addWidget(screenshot_title)
        screenshot_sep = QFrame()
        screenshot_sep.setObjectName("SectionSeparator")
        screenshot_sep.setFrameShape(QFrame.VLine)
        screenshot_sep.setFrameShadow(QFrame.Plain)
        screenshot_sep.setFixedHeight(18)
        screenshot_top.addSpacing(8)
        screenshot_top.addWidget(screenshot_sep)
        screenshot_top.addSpacing(8)
        self.lbl_screenshot_count = QLabel("0 张")
        self.lbl_screenshot_count.setObjectName("CounterLabel")
        self.lbl_screenshot_count.setAlignment(Qt.AlignCenter)
        self.lbl_screenshot_count.setFixedHeight(24)
        screenshot_top.addWidget(self.lbl_screenshot_count)
        screenshot_top.addStretch()
        self.btn_bind_screenshot = QPushButton("绑定到右侧所选发票")
        self.btn_bind_screenshot.setObjectName("PrimaryButton")
        self.btn_bind_screenshot.setFixedHeight(40)
        self.btn_bind_screenshot.clicked.connect(self._bind_selected_screenshot)
        screenshot_top.addWidget(self.btn_bind_screenshot)
        screenshot_layout.addLayout(screenshot_top)

        self.lbl_bind_hint = QLabel("")
        self.lbl_bind_hint.setObjectName("AccentHint")
        self.lbl_bind_hint.setVisible(False)

        self.screenshot_table = ScreenshotTable()
        self.screenshot_table.setColumnCount(3)
        self.screenshot_table.setHorizontalHeaderLabels(["文件名", "金额", "状态"])
        self.screenshot_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.screenshot_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.screenshot_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.screenshot_table.setColumnWidth(0, 220)
        self.screenshot_table.setColumnWidth(1, 72)
        self.screenshot_table.setColumnWidth(2, 120)
        self.screenshot_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.screenshot_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.screenshot_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.screenshot_table.setAlternatingRowColors(True)
        self.screenshot_table.setShowGrid(True)
        self.screenshot_table.verticalHeader().setVisible(False)
        self.screenshot_table.verticalHeader().setDefaultSectionSize(32)
        self.screenshot_status_delegate = StatusItemDelegate(self.screenshot_table)
        self.screenshot_table.setItemDelegateForColumn(2, self.screenshot_status_delegate)
        self._install_table_empty_hint(self.screenshot_table)
        self.screenshot_table.files_dropped.connect(self._on_screenshot_drop)
        self.screenshot_table.itemSelectionChanged.connect(self._update_bind_hint)
        screenshot_layout.addWidget(self.screenshot_table)
        vbox.addWidget(screenshot_frame, 1)
        return frame

    def _build_right(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(24, 18, 18, 18)
        vbox.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("分叠编辑区")
        title.setObjectName("SectionTitle")
        top.addWidget(title)
        title_sep = QFrame()
        title_sep.setObjectName("SectionSeparator")
        title_sep.setFrameShape(QFrame.VLine)
        title_sep.setFrameShadow(QFrame.Plain)
        title_sep.setFixedHeight(18)
        top.addSpacing(8)
        top.addWidget(title_sep)
        top.addSpacing(8)
        self.lbl_stacks = QLabel("")
        self.lbl_stacks.setObjectName("CounterLabel")
        self.lbl_stacks.setAlignment(Qt.AlignCenter)
        self.lbl_stacks.setFixedHeight(24)
        top.addWidget(self.lbl_stacks)
        top.addStretch()
        vbox.addLayout(top)

        tools = QHBoxLayout()
        tools.addWidget(QLabel("日期:"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy年MM月dd日")
        self.date_edit.setCalendarPopup(True)
        self._set_date_edit_width()
        tools.addWidget(self.date_edit)
        self.btn_add_stack = QPushButton("新建空叠")
        self.btn_add_stack.setObjectName("PrimaryButton")
        self.btn_add_stack.setFixedHeight(36)
        self.btn_add_stack.clicked.connect(self._add_empty_stack)
        tools.addWidget(self.btn_add_stack)
        btn_remove = QPushButton("删除空叠")
        btn_remove.setObjectName("SecondaryButton")
        btn_remove.setFixedHeight(36)
        btn_remove.clicked.connect(self._remove_empty_stacks)
        tools.addWidget(btn_remove)
        vbox.addLayout(tools)

        self.tree = StackTree()
        self.tree.setHeaderLabels(["序", "发票名称", "发票号码", "发票金额", "截图名称", "截图金额", "实际报销人"])
        self.tree.headerItem().setTextAlignment(0, Qt.AlignCenter)
        self.tree.header().setStretchLastSection(False)
        for column, width in enumerate((42, 180, 190, 90, 150, 90, 110)):
            self.tree.header().setSectionResizeMode(column, QHeaderView.Interactive)
            self.tree.setColumnWidth(column, width)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tree.header().setSectionResizeMode(6, QHeaderView.Fixed)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setIndentation(0)
        self.tree.setUniformRowHeights(False)
        self.tree.setFocusPolicy(Qt.StrongFocus)
        self.tree.setItemDelegate(StackTreeItemDelegate(self.tree))
        self._install_tree_empty_hint(self.tree)
        self.tree.invoice_dropped.connect(self._handle_invoice_drop)
        self.tree.screenshot_dropped.connect(self._handle_screenshot_drop)
        self.tree.currentItemChanged.connect(self._update_bind_hint)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        vbox.addWidget(self.tree)
        return frame

    def _load_settings(self) -> dict:
        if not self.settings_path.is_file():
            return {}
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_settings(self) -> None:
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    def _apply_theme_settings(self) -> None:
        theme_key = self.settings.get("theme")
        if theme_key not in THEMES:
            theme_key = DEFAULT_THEME_KEY
        self.settings["theme"] = theme_key
        theme = THEMES[theme_key]
        self.version_panel.set_theme(theme)
        self.btn_undo.set_theme(theme)
        self.btn_redo.set_theme(theme)
        if hasattr(self, "brand_logo"):
            self.brand_logo.setPixmap(_themed_svg_pixmap("logo.svg", QColor(theme["accent"]), 44))
        if hasattr(self, "tree"):
            self.tree._theme = theme
            self.tree.update_frozen_header()
            delegate = self.tree.itemDelegate()
            if isinstance(delegate, StackTreeItemDelegate):
                delegate.set_theme(theme)
                self.tree.viewport().update()
        for delegate_name, view_name in (
            ("invoice_status_delegate", "table"),
            ("screenshot_status_delegate", "screenshot_table"),
        ):
            if hasattr(self, delegate_name):
                status_delegate = getattr(self, delegate_name)
                if isinstance(status_delegate, StatusItemDelegate):
                    status_delegate.set_theme(theme)
                    if hasattr(self, view_name):
                        getattr(self, view_name).viewport().update()
        self.setStyleSheet(self._theme_stylesheet(theme))
        self._refresh_theme_cards()
        if hasattr(self, "date_edit"):
            self._set_date_edit_width()
        if hasattr(self, "tree") and hasattr(self, "invoices"):
            self._render_all()
            self._update_bind_hint()

    def _current_theme(self) -> dict:
        theme_key = self.settings.get("theme")
        return THEMES[theme_key] if theme_key in THEMES else THEMES[DEFAULT_THEME_KEY]

    def _status_warning_color(self) -> QColor:
        theme = self._current_theme()
        return QColor(theme["danger"])

    def _set_date_edit_width(self) -> None:
        text_width = self.date_edit.fontMetrics().horizontalAdvance("2099年12月31日")
        self.date_edit.setFixedWidth(max(text_width + 100, 190))

    def _select_theme(self, theme_key: str) -> None:
        if theme_key not in THEMES:
            return
        self.settings["theme"] = theme_key
        self._save_settings()
        self._apply_theme_settings()

    def _refresh_theme_cards(self) -> None:
        if not hasattr(self, "theme_buttons"):
            return
        active_key = self.settings.get("theme")
        current_theme = self._current_theme()
        for key, button in self.theme_buttons.items():
            selected = key == active_key
            button.set_card_theme(current_theme, selected)
            button.setToolTip(THEMES[key]["name"])

    def _theme_stylesheet(self, theme: dict) -> str:
        app_bg = theme["bg"]
        surface = theme["panel"]
        surface_alt = theme["panel_alt"]
        surface_hover = theme["accent_soft"]
        surface_active = theme["accent_soft"]
        field = theme["field"]
        border = theme["border"]
        text = theme["text"]
        muted = theme["muted"]
        primary = theme["accent"]
        secondary = theme.get("secondary", primary)
        highlight = theme.get("highlight", theme["accent_soft"])
        counter = theme.get("counter", secondary)
        primary_hover = theme["accent_hover"]
        primary_soft = theme["accent_soft"]
        danger = theme["danger"]
        selected_text = theme["selected_text"]
        header_bg = _mix_color(QColor(surface_alt), QColor(border), 0.68).name()
        sequence_header_bg = _mix_color(QColor(surface_alt), QColor(border), 0.88).name()
        secondary_hover = QColor(secondary).darker(160).name()
        outline_hover = QColor(surface).darker(110).name()
        on_primary = _text_on_fill(primary)
        on_secondary = _text_on_fill(secondary)
        counter_line = _mix_color(QColor(counter), QColor(surface), 0.18).name()
        counter_bg = _mix_color(QColor(surface), QColor(counter_line), 0.10).name()
        table_radius = "6px"
        return f"""
            QMainWindow {{
                background: {app_bg};
                color: {text};
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
                font-size: 13px;
            }}
            QWidget {{
                color: {text};
                font-family: "Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif;
                selection-background-color: {primary_soft};
                selection-color: {selected_text};
            }}
            QFrame#Sidebar {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QLabel#BrandTitle {{
                font-size: 20px;
                font-weight: 900;
                color: {text};
            }}
            QLabel#BrandSubtitle {{
                margin-top: 2px;
            }}
            QLabel#BrandLogo {{
                background: transparent;
                border: none;
            }}
            QLabel#BrandSubtitle, QLabel#HelperText {{
                color: {muted};
                font-size: 12px;
            }}
            QLabel#PageTitle {{
                font-size: 28px;
                font-weight: 800;
                color: {text};
                min-height: 40px;
                max-height: 40px;
            }}
            QLabel#VersionNumber {{
                color: {text};
                font-size: 32px;
                font-weight: 900;
                background: transparent;
            }}
            QLabel#SectionTitle {{
                font-size: 16px;
                font-weight: 800;
                color: {text};
            }}
            QLabel#CounterLabel {{
                color: {counter_line};
                background: {counter_bg};
                border: 1px solid {counter_line};
                border-radius: 12px;
                padding: 0 14px;
                min-width: 48px;
                font-size: 13px;
                font-weight: 900;
            }}
            QFrame#SectionSeparator {{
                background: {border};
                border: none;
                min-width: 1px;
                max-width: 1px;
                margin: 0 2px;
            }}
            QLabel#AccentHint {{
                color: {primary};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#DropHint {{
                color: {muted};
                background: {surface_alt};
                border: 2px dashed {border};
                border-radius: 16px;
                padding: 16px;
                font-size: 13px;
                font-weight: 700;
            }}
            QLabel#EmptyTitle {{
                font-size: 22px;
                font-weight: 800;
                color: {muted};
            }}
            QLabel#TableEmptyHint {{
                color: {muted};
                background: transparent;
                font-size: 15px;
                font-weight: 700;
                padding: 12px;
            }}
            QFrame#TopPanel, QFrame#Panel {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QFrame#SubPanel {{
                background: transparent;
                border: none;
            }}
            QFrame#EmptyPanel {{
                background: {surface};
                border: 1px dashed {border};
                border-radius: 18px;
            }}
            QScrollArea#HelpScroll, QWidget#HelpScrollViewport, QWidget#HelpContent {{
                background: transparent;
                border: none;
            }}
            QLabel#PageSubtitle, QLabel#HelpVersion {{
                color: {muted};
                font-size: 12px;
                font-weight: 600;
            }}
            QFrame#HelpCard {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 16px;
            }}
            QLabel#HelpCardTitle {{
                color: {text};
                font-size: 17px;
                font-weight: 900;
            }}
            QLabel#HelpNumber {{
                color: {on_primary};
                background: {primary};
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 900;
            }}
            QLabel#HelpCardSummary {{
                color: {text};
                font-size: 13px;
                font-weight: 700;
                padding-bottom: 2px;
            }}
            QLabel#HelpBullet {{
                color: {muted};
                font-size: 13px;
                line-height: 1.55;
                padding: 2px 0;
            }}
            QPushButton {{
                background: {surface_alt};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 5px 12px;
                min-height: 26px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                border-color: {primary};
                background: {surface_hover};
            }}
            QPushButton:pressed {{
                background: {surface_active};
                border-color: {primary};
            }}
            QPushButton:disabled {{
                color: {muted};
                background: {field};
                border-color: {border};
            }}
            QPushButton#PrimaryButton {{
                background: {primary};
                border-color: {primary};
                color: {on_primary};
                font-weight: 900;
            }}
            QPushButton#PrimaryButton:hover, QPushButton#PrimaryButton[pointerOver="true"] {{
                background: {primary_hover};
                border-color: {primary_hover};
            }}
            QPushButton#PrimaryButton:pressed {{
                background: {primary_hover};
                color: {on_primary};
            }}
            QPushButton#SecondaryButton {{
                background: {secondary};
                border-color: {secondary};
                color: {on_secondary};
                font-weight: 900;
            }}
            QPushButton#SecondaryButton:hover, QPushButton#SecondaryButton[pointerOver="true"] {{
                background: {secondary_hover};
                border-color: {secondary_hover};
                color: {on_secondary};
            }}
            QPushButton#SecondaryButton:pressed {{
                background: {secondary_hover};
                border-color: {secondary_hover};
                color: {on_secondary};
            }}
            QPushButton#OutlineButton {{
                background: {surface};
                border-color: {border};
                color: {text};
            }}
            QPushButton#OutlineButton:hover, QPushButton#OutlineButton[pointerOver="true"] {{
                background: {outline_hover};
                border-color: {primary};
                color: {primary};
            }}
            QPushButton#GhostButton {{
                background: transparent;
                border-color: transparent;
                color: {muted};
            }}
            QPushButton#GhostButton:hover {{
                background: {surface_alt};
                border-color: {border};
                color: {text};
            }}
            QPushButton#NavButton {{
                text-align: left;
                background: {surface};
                border: 1px solid {border};
                border-radius: 16px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 900;
            }}
            QPushButton#NavButton:hover {{
                background: {surface_hover};
                border-color: {primary};
            }}
            QPushButton#NavButton[active="true"] {{
                background: {primary};
                border-color: {primary};
                color: {on_primary};
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
                background: {field};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 5px 10px;
                min-height: 26px;
                font-weight: 700;
            }}
            QComboBox {{
                padding-right: 28px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid {border};
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
                background: {surface_alt};
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {muted};
                width: 0;
                height: 0;
            }}
            QComboBox QAbstractItemView {{
                background: {surface};
                color: {text};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 4px;
                outline: 0;
                selection-background-color: {primary_soft};
                selection-color: {selected_text};
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 6px 8px;
                border-radius: 9px;
                color: {text};
                background: transparent;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {surface_alt};
                color: {text};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {primary_soft};
                color: {selected_text};
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
                border-color: {border};
            }}
            QAbstractSpinBox {{
                padding-right: 10px;
            }}
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
                width: 0;
                height: 0;
                border: none;
            }}
            QDateEdit {{
                padding-right: 30px;
            }}
            QDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid {border};
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
                background: {surface_alt};
            }}
            QDateEdit::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {muted};
                width: 0;
                height: 0;
            }}
            QMenu {{
                background: {surface};
                color: {text};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 7px 12px;
                border-radius: 9px;
            }}
            QMenu::item:selected {{
                background: {primary_soft};
                color: {selected_text};
            }}
            QCalendarWidget QWidget {{
                background: {surface};
                color: {text};
            }}
            QCalendarWidget QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                color: {text};
                padding: 5px 8px;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {primary_soft};
                border-color: {primary};
            }}
            QTableWidget, QTreeWidget {{
                background: {surface};
                alternate-background-color: {surface_alt};
                border: 1px solid {border};
                border-radius: {table_radius};
                gridline-color: {border};
                selection-background-color: {primary_soft};
                selection-color: {selected_text};
                outline: 0;
            }}
            QTableWidget::viewport, QTreeWidget::viewport {{
                background: {surface};
                border: none;
            }}
            QTableWidget::item, QTreeWidget::item {{
                padding: 6px;
                border: none;
            }}
            QTableWidget::item:selected, QTreeWidget::item:selected {{
                background: {primary_soft};
                color: {selected_text};
            }}
            QTableWidget::item:focus, QTreeWidget::item:focus {{
                outline: 0;
                border: none;
            }}
            QTableWidget::horizontalHeader::section,
            QTreeWidget::header::section {{
                background: {header_bg};
                color: {muted};
                border-right: 1px solid {border};
                border-bottom: 1px solid {border};
                padding: 8px 10px;
                font-weight: 800;
            }}
            QTableWidget::horizontalHeader::section:first,
            QTreeWidget::header::section:first {{
                border-top-left-radius: {table_radius};
                border-left: 1px solid {border};
            }}
            QTreeWidget::header::section:first {{
                background: {sequence_header_bg};
                padding: 8px 2px;
            }}
            QTableWidget::horizontalHeader::section:last,
            QTreeWidget::header::section:last {{
                border-top-right-radius: {table_radius};
                border-right: 1px solid {border};
            }}
            QTableWidget::horizontalHeader::section:only-one,
            QTreeWidget::header::section:only-one {{
                border-top-left-radius: {table_radius};
                border-top-right-radius: {table_radius};
                border-left: 1px solid {border};
                border-right: 1px solid {border};
            }}
            QTableCornerButton::section {{
                background: {header_bg};
                border: 1px solid {border};
                border-top-left-radius: {table_radius};
            }}
            QHeaderView {{
                background: transparent;
                border: none;
            }}
            QHeaderView::section {{
                background: {header_bg};
                color: {muted};
                border: none;
                border-right: 1px solid {border};
                border-bottom: 1px solid {border};
                padding: 8px 10px;
                font-weight: 900;
            }}
            QHeaderView::section:first {{
                border-top-left-radius: {table_radius};
            }}
            QHeaderView::section:last {{
                border-top-right-radius: {table_radius};
                border-right: none;
            }}
            QHeaderView::section:only-one {{
                border-top-left-radius: {table_radius};
                border-top-right-radius: {table_radius};
                border-right: none;
            }}
            QTableCornerButton::section {{
                background: {header_bg};
                border: none;
                border-right: 1px solid {border};
                border-bottom: 1px solid {border};
                border-top-left-radius: {table_radius};
            }}
            QScrollBar:vertical {{
                background: {surface_alt};
                width: 10px;
                border: none;
                margin: 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                border-radius: 5px;
                min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {muted};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background: {surface_alt};
                height: 10px;
                border: none;
                margin: 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background: {border};
                border-radius: 5px;
                min-width: 28px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {muted};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            QProgressBar {{
                background: {field};
                border: 1px solid {border};
                border-radius: 9px;
                height: 12px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {secondary};
                border-radius: 6px;
            }}
            QSplitter::handle {{
                background: {app_bg};
                width: 18px;
            }}
        """

    def _apply_rule_settings(self) -> None:
        rules = self.settings.get("stack_rules")
        if not isinstance(rules, dict):
            return
        max_count = rules.get("max_count")
        if isinstance(max_count, int):
            self.spin_max_count.setValue(max(1, max_count))
        max_amount = rules.get("max_amount")
        if isinstance(max_amount, (int, float)):
            self.spin_max_amount.setValue(max(0.01, float(max_amount)))

    def _apply_output_settings(self) -> None:
        output_dir = self.settings.get("output_dir")
        if isinstance(output_dir, str):
            self.edit_output.setText(output_dir)

    def _apply_reimburser_settings(self) -> None:
        common_reimbursers = self.settings.get("common_reimbursers")
        current_text = self.settings.get("current_reimburser")
        items = [item.strip() for item in common_reimbursers if isinstance(item, str) and item.strip()] if isinstance(common_reimbursers, list) else []
        self.combo_reimburser.blockSignals(True)
        self.combo_reimburser.clear()
        self.combo_reimburser.addItems(items)
        if isinstance(current_text, str):
            self.combo_reimburser.setCurrentText(current_text)
        self.combo_reimburser.blockSignals(False)

    def _apply_remark_settings(self) -> None:
        common_remarks = self.settings.get("common_remarks")
        current_text = self.settings.get("current_remark")
        items = [item.strip() for item in common_remarks if isinstance(item, str) and item.strip()] if isinstance(common_remarks, list) else []
        self.combo_remark.blockSignals(True)
        self.combo_remark.clear()
        self.combo_remark.addItems(items)
        if isinstance(current_text, str):
            self.combo_remark.setCurrentText(current_text)
        self.combo_remark.blockSignals(False)

    def _on_rule_changed(self) -> None:
        self.settings["stack_rules"] = {
            "max_count": self.spin_max_count.value(),
            "max_amount": round(self.spin_max_amount.value(), 2),
        }
        self._save_settings()
        self._render_all()

    def _on_output_path_changed(self, text: str) -> None:
        self.settings["output_dir"] = text.strip()
        self._save_settings()
        self._refresh_buttons()

    def _on_reimburser_changed(self, text: str) -> None:
        self.settings["current_reimburser"] = text.strip()
        self._save_settings()

    def _on_remark_changed(self, text: str) -> None:
        self.settings["current_remark"] = text.strip()
        self._save_settings()

    def _add_common_reimburser(self) -> None:
        value = self.combo_reimburser.currentText().strip()
        if not value:
            QMessageBox.information(self, "提示", "请先输入预约人。")
            return
        self._remember_common_reimburser(value)

    def _remove_common_reimburser(self) -> None:
        self._remove_common_reimburser_value(self.combo_reimburser.currentText().strip())

    def _remember_common_reimburser(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        items = self.settings.get("common_reimbursers")
        common_reimbursers = [item for item in items if isinstance(item, str) and item.strip()] if isinstance(items, list) else []
        if value not in common_reimbursers:
            common_reimbursers.append(value)
        self.settings["common_reimbursers"] = common_reimbursers
        self.settings["current_reimburser"] = value
        self._save_settings()
        self._apply_reimburser_settings()

    def _remove_common_reimburser_value(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        items = self.settings.get("common_reimbursers")
        common_reimbursers = [item for item in items if isinstance(item, str) and item.strip()] if isinstance(items, list) else []
        if value in common_reimbursers:
            common_reimbursers.remove(value)
        current_text = self.combo_reimburser.currentText().strip()
        self.settings["common_reimbursers"] = common_reimbursers
        self.settings["current_reimburser"] = "" if current_text == value else current_text
        self._save_settings()
        self._apply_reimburser_settings()

    def _add_common_remark(self) -> None:
        value = self.combo_remark.currentText().strip()
        if not value:
            QMessageBox.information(self, "提示", "请先输入实际报销人。")
            return
        self._remember_common_remark(value)

    def _remove_common_remark(self) -> None:
        self._remove_common_remark_value(self.combo_remark.currentText().strip())

    def _remember_common_remark(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        items = self.settings.get("common_remarks")
        common_remarks = [item for item in items if isinstance(item, str) and item.strip()] if isinstance(items, list) else []
        if value not in common_remarks:
            common_remarks.append(value)
        self.settings["common_remarks"] = common_remarks
        self.settings["current_remark"] = value
        self._save_settings()
        self._apply_remark_settings()

    def _remove_common_remark_value(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        items = self.settings.get("common_remarks")
        common_remarks = [item for item in items if isinstance(item, str) and item.strip()] if isinstance(items, list) else []
        if value in common_remarks:
            common_remarks.remove(value)
        current_text = self.combo_remark.currentText().strip()
        self.settings["common_remarks"] = common_remarks
        self.settings["current_remark"] = "" if current_text == value else current_text
        self._save_settings()
        self._apply_remark_settings()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        invoice_paths = []
        screenshot_paths = []
        for url in event.mimeData().urls():
            local = url.toLocalFile().lower()
            if local.endswith(".pdf"):
                invoice_paths.append(Path(url.toLocalFile()))
            elif local.endswith((".jpg", ".jpeg", ".png")):
                screenshot_paths.append(Path(url.toLocalFile()))
        if invoice_paths:
            self._on_drop(invoice_paths)
        if screenshot_paths:
            self._on_screenshot_drop(screenshot_paths)
        event.acceptProposedAction()

    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton) and event.type() in (QEvent.Enter, QEvent.Leave):
            # Disabled buttons still receive enter/leave events, but Qt omits :hover.
            obj.setProperty("pointerOver", event.type() == QEvent.Enter)
            obj.style().unpolish(obj)
            obj.style().polish(obj)
            obj.update()
        if event.type() == QEvent.Resize:
            for table in (getattr(self, "table", None), getattr(self, "screenshot_table", None)):
                if table is not None and obj is table.viewport():
                    self._position_table_empty_hint(table)
                    return False
            tree = getattr(self, "tree", None)
            if tree is not None and obj is tree.viewport():
                self._position_tree_empty_hint(tree)
                return False
        return super().eventFilter(obj, event)

    def _on_drop(self, paths: list[Path]):
        existing_paths = {str(inv.source_path.resolve()) for inv in self.invoices}
        new_paths = [p for p in paths if str(p.resolve()) not in existing_paths]
        skipped_same_path = [p for p in paths if str(p.resolve()) in existing_paths]
        if skipped_same_path:
            names = "\n".join(path.name for path in skipped_same_path[:8])
            suffix = "" if len(skipped_same_path) <= 8 else f"\n……另有 {len(skipped_same_path) - 8} 个同路径文件"
            QMessageBox.information(self, "已存在", f"以下发票已在当前列表中：\n{names}{suffix}")
        if not new_paths:
            return

        if self._import_before is None:
            self._import_before = self._capture_workspace()
        start = len(self.invoices)
        for path in new_paths:
            inv = Invoice(source_path=path)
            self.invoices.append(inv)

        self._render_unassigned_table()

        if self._worker and self._worker.isRunning():
            self._pending_paths.extend(new_paths)
        else:
            self._start_parse(start, new_paths)

    def _on_screenshot_drop(self, paths: list[Path]):
        existing = {str(item.source_path.resolve()) for item in self.screenshots}
        new_paths = [p for p in paths if str(p.resolve()) not in existing]
        if not new_paths:
            return

        if self._import_before is None:
            self._import_before = self._capture_workspace()
        start = len(self.screenshots)
        for path in new_paths:
            screenshot = OrderScreenshot(source_path=path)
            self.screenshots.append(screenshot)

        self._render_screenshot_table()

        if self._screenshot_worker and self._screenshot_worker.isRunning():
            self._pending_screenshot_paths.extend(new_paths)
        else:
            self._start_screenshot_parse(start, new_paths)

    def _start_parse(self, start: int, paths: list[Path]):
        self._parsing_invoices = True
        self.progress.setVisible(True)
        self.progress.setRange(0, len(paths))
        self.progress.setValue(0)
        self._refresh_buttons()
        path_set = {path.resolve() for path in paths}
        self._worker = ParseWorker([invoice for invoice in self.invoices if invoice.source_path.resolve() in path_set])
        self._worker.result.connect(self._on_result)
        self._worker.finished.connect(self._on_parse_done)
        self._worker.start()
        self._refresh_buttons()

    def _start_screenshot_parse(self, start: int, paths: list[Path]):
        self._parsing_screenshots = True
        self.screenshot_progress.setVisible(True)
        self.screenshot_progress.setRange(0, len(paths))
        self.screenshot_progress.setValue(0)
        self._refresh_buttons()
        self._screenshot_worker = ScreenshotParseWorker(start, paths)
        self._screenshot_worker.result.connect(self._on_screenshot_result)
        self._screenshot_worker.finished.connect(self._on_screenshot_parse_done)
        self._screenshot_worker.start()
        self._refresh_buttons()

    def _on_result(self, invoice_id: str, parsed, error: str | None):
        invoice = next((item for item in self.invoices if item.invoice_id == invoice_id), None)
        if invoice is None:
            return
        if parsed is not None:
            invoice.amount = parsed.amount
            invoice.invoice_code = parsed.invoice_code
            invoice.invoice_number = parsed.invoice_number
            invoice.invoice_date = parsed.invoice_date
            invoice.item_names = parsed.item_names
            invoice.error = error
            duplicate = self._find_duplicate_invoice(invoice)
            if duplicate is not None:
                self.invoices.remove(invoice)
                self.progress.setValue(self.progress.value() + 1)
                self._show_duplicate_invoice_dialog(invoice, duplicate)
                self._render_all()
                return
        else:
            invoice.amount = None
            invoice.invoice_code = None
            invoice.invoice_number = None
            invoice.invoice_date = None
            invoice.item_names = None
            invoice.error = error
        self.progress.setValue(self.progress.value() + 1)
        self._render_unassigned_table()

    def _on_screenshot_result(self, idx: int, parsed, error: str | None):
        screenshot = self.screenshots[idx]
        if parsed is None:
            screenshot.amount = None
            screenshot.platform = None
        else:
            platform, amount = parsed
            screenshot.platform = platform
            screenshot.amount = amount
        screenshot.error = error
        self.screenshot_progress.setValue(self.screenshot_progress.value() + 1)

    def _on_parse_done(self):
        self.progress.setVisible(False)
        if self._pending_paths:
            paths = list(self._pending_paths)
            self._pending_paths.clear()
            start = len(self.invoices) - len(paths)
            self._start_parse(start, paths)
            return

        self._rematch_screenshots()
        self._parsing_invoices = False
        self._finish_import_history()
        self._render_all()
        self._update_bind_hint()

    def _on_screenshot_parse_done(self):
        self.screenshot_progress.setVisible(False)
        if self._pending_screenshot_paths:
            paths = list(self._pending_screenshot_paths)
            self._pending_screenshot_paths.clear()
            start = len(self.screenshots) - len(paths)
            self._start_screenshot_parse(start, paths)
            return
        self._rematch_screenshots()
        self._parsing_screenshots = False
        self._finish_import_history()
        self._render_all()
        self._update_bind_hint()

    def _rematch_screenshots(self):
        match_screenshots_to_invoices(self.invoices, self.screenshots)
        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        self._sync_group_screenshots()

    def _sync_group_screenshots(self):
        for group in self.date_groups:
            invoice_ids = {invoice.invoice_id for invoice in group.all_invoices()}
            group.screenshots[:] = [screenshot for screenshot in self.screenshots if screenshot.matched_invoice_id in invoice_ids]

    def _render_all(self):
        if self.date_groups:
            for group in self.date_groups:
                normalize_stack_indexes(group.stacks)
        else:
            normalize_stack_indexes(self.stacks)
        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        self._sync_group_screenshots()
        self._render_unassigned_table()
        self._render_screenshot_table()
        self._render_tree()
        self._refresh_buttons()

    @workspace_edit("切换日期锁定")
    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int):
        _ = _column
        payload = item.data(0, Qt.UserRole)
        if not isinstance(payload, tuple) or payload[0] != self.DATE_ITEM:
            return
        date_str = payload[1]
        group = next((entry for entry in self.date_groups if entry.date_str == date_str), None)
        if group is None:
            return
        group.locked = not group.locked
        self._render_tree()
        self._refresh_buttons()

    def _render_unassigned_table(self):
        unassigned = [inv for inv in self.invoices if inv.stack_index is None]
        self.lbl_count.setText(f"{len(unassigned)} 张")
        self.table.setRowCount(0)
        self.table.clearSpans()
        if not unassigned:
            hint = "拖入 PDF；可拖拽发票至右边任一叠" if not self.invoices else "未分配发票为空；可从右侧拖回这里重新分配"
            self._show_table_empty_hint(self.table, hint)
            return
        self._hide_table_empty_hint(self.table)
        name_width = self.fontMetrics().horizontalAdvance("文件名") + 28
        status_width = self.fontMetrics().horizontalAdvance("状态") + 28
        for row, inv in enumerate(unassigned):
            self.table.insertRow(row)
            name_item = QTableWidgetItem(inv.filename)
            name_item.setData(Qt.UserRole, inv.invoice_id)
            self.table.setItem(row, 0, name_item)
            name_width = max(name_width, self.fontMetrics().horizontalAdvance(inv.filename) + 28)
            amt_item = QTableWidgetItem(f"{inv.amount:.2f}" if inv.amount is not None else "-")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, amt_item)
            status = "未分配"
            if inv.amount is None:
                status = inv.error or "未识别"
            elif inv.unique_key is None:
                status = "未识别发票号码，无法查重"
            elif inv.matched_screenshot_id:
                status = "已匹配截图"
            st_item = QTableWidgetItem(status)
            st_item.setTextAlignment(Qt.AlignCenter)
            if inv.amount is None or inv.unique_key is None:
                status_color = self._status_warning_color()
                st_item.setData(Qt.DecorationRole, True)
                st_item.setForeground(status_color)
            self.table.setItem(row, 2, st_item)
            status_width = max(status_width, self.fontMetrics().horizontalAdvance(status) + 28)
        self.table.setColumnWidth(0, min(name_width, 520))
        self.table.setColumnWidth(1, 72)

    def _render_screenshot_table(self):
        self.screenshot_table.setRowCount(0)
        self.screenshot_table.clearSpans()
        invoice_map = {invoice.invoice_id: invoice for invoice in self.invoices}
        duplicate_amounts = self._duplicate_screenshot_amounts()
        visible_screenshots = [
            screenshot for screenshot in self.screenshots if screenshot.error or not screenshot.matched_invoice_id
        ]
        self.lbl_screenshot_count.setText(f"{len(visible_screenshots)} 张")
        if not visible_screenshots:
            hint = "拖入 JPG / PNG 订单截图；自动提取实付款并匹配同金额发票" if not self.screenshots else "未匹配截图为空；已匹配截图会随发票输出"
            self._show_table_empty_hint(self.screenshot_table, hint)
            return
        self._hide_table_empty_hint(self.screenshot_table)
        name_width = self.fontMetrics().horizontalAdvance("文件名") + 28
        status_width = self.fontMetrics().horizontalAdvance("状态") + 28
        for row, screenshot in enumerate(visible_screenshots):
            self.screenshot_table.insertRow(row)
            name_item = QTableWidgetItem(screenshot.filename)
            name_item.setData(Qt.UserRole, screenshot.screenshot_id)
            self.screenshot_table.setItem(row, 0, name_item)
            name_width = max(name_width, self.fontMetrics().horizontalAdvance(screenshot.filename) + 28)
            amt_item = QTableWidgetItem(f"{screenshot.amount:.2f}" if screenshot.amount is not None else "-")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.screenshot_table.setItem(row, 1, amt_item)

            status = self._screenshot_status_text(screenshot, invoice_map, duplicate_amounts)
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if screenshot.error or "待人工处理" in status or status == "未找到同金额发票":
                status_color = self._status_warning_color()
                status_item.setData(Qt.DecorationRole, True)
                status_item.setForeground(status_color)
            self.screenshot_table.setItem(row, 2, status_item)
            status_width = max(status_width, self.fontMetrics().horizontalAdvance(status) + 28)
        self.screenshot_table.setColumnWidth(0, min(name_width, 520))
        self.screenshot_table.setColumnWidth(1, 72)

    def _install_table_empty_hint(self, table: QTableWidget) -> None:
        hint = QLabel(table.viewport())
        hint.setObjectName("TableEmptyHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        hint.hide()
        table._empty_hint_label = hint
        table.viewport().installEventFilter(self)

    def _show_table_empty_hint(self, table: QTableWidget, text: str) -> None:
        hint = getattr(table, "_empty_hint_label", None)
        if hint is None:
            return
        hint.setText(text)
        hint.show()
        hint.raise_()
        self._position_table_empty_hint(table)

    def _hide_table_empty_hint(self, table: QTableWidget) -> None:
        hint = getattr(table, "_empty_hint_label", None)
        if hint is not None:
            hint.hide()

    def _position_table_empty_hint(self, table: QTableWidget) -> None:
        hint = getattr(table, "_empty_hint_label", None)
        if hint is None or not hint.isVisible():
            return
        hint.setGeometry(table.viewport().rect())

    def _render_empty_tree_hint(self, text: str) -> None:
        self.tree.clear()
        self._show_tree_empty_hint(self.tree, text)

    def _install_tree_empty_hint(self, tree: QTreeWidget) -> None:
        hint = QLabel(tree.viewport())
        hint.setObjectName("TableEmptyHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        hint.hide()
        tree._empty_hint_label = hint
        tree.viewport().installEventFilter(self)

    def _show_tree_empty_hint(self, tree: QTreeWidget, text: str) -> None:
        hint = getattr(tree, "_empty_hint_label", None)
        if hint is None:
            return
        hint.setText(text)
        hint.show()
        hint.raise_()
        self._position_tree_empty_hint(tree)

    def _hide_tree_empty_hint(self, tree: QTreeWidget) -> None:
        hint = getattr(tree, "_empty_hint_label", None)
        if hint is not None:
            hint.hide()

    def _position_tree_empty_hint(self, tree: QTreeWidget) -> None:
        hint = getattr(tree, "_empty_hint_label", None)
        if hint is None or not hint.isVisible():
            return
        hint.setGeometry(tree.viewport().rect())

    def _position_all_empty_hints(self) -> None:
        for table in (getattr(self, "table", None), getattr(self, "screenshot_table", None)):
            if table is not None:
                self._position_table_empty_hint(table)
        tree = getattr(self, "tree", None)
        if tree is not None:
            self._position_tree_empty_hint(tree)

    def _duplicate_screenshot_amounts(self) -> set[float]:
        counts: dict[float, int] = {}
        for screenshot in self.screenshots:
            if screenshot.amount is None or screenshot.error:
                continue
            key = round(screenshot.amount, 2)
            counts[key] = counts.get(key, 0) + 1
        return {amount for amount, count in counts.items() if count > 1}

    def _screenshot_status_text(self, screenshot: OrderScreenshot, invoice_map: dict[str, Invoice], duplicate_amounts: set[float]) -> str:
        if screenshot.amount is None:
            return screenshot.error or "未识别"
        if screenshot.matched_invoice_id:
            invoice = invoice_map.get(screenshot.matched_invoice_id)
            if invoice is not None and invoice.stack_index is not None:
                return f"已匹配 第{invoice.stack_index}叠"
            return "已匹配"
        if round(screenshot.amount, 2) in duplicate_amounts:
            return "待人工处理：截图金额重复"
        same_amount_invoices = [invoice for invoice in self.invoices if invoice.amount is not None and round(invoice.amount, 2) == round(screenshot.amount, 2)]
        if len(same_amount_invoices) > 1:
            return "待人工处理：发票金额重复"
        if not same_amount_invoices:
            return "未找到同金额发票"
        return "待匹配"

    def _render_tree(self):
        # Rebuilding the items resets Qt's scrollbars and current selection.
        # Restore them before painting so a drop never flashes back to the top.
        tree = self.tree
        tree._finish_drop_transition()
        vertical = tree.verticalScrollBar().value()
        horizontal = tree.horizontalScrollBar().value()

        def item_key(item):
            if item is None:
                return None
            payload = item.data(0, Qt.UserRole)
            if not isinstance(payload, tuple):
                return None
            return payload[:2] if payload[0] == self.DATE_ITEM else payload

        current_key = item_key(tree.currentItem())
        selected_keys = {item_key(item) for item in tree.selectedItems()}
        expanded = {}
        iterator = QTreeWidgetItemIterator(tree)
        while iterator.value():
            item = iterator.value()
            if item.childCount():
                expanded[item_key(item)] = item.isExpanded()
            iterator += 1

        tree.setUpdatesEnabled(False)
        try:
            self._populate_tree()
            iterator = QTreeWidgetItemIterator(tree)
            while iterator.value():
                item = iterator.value()
                key = item_key(item)
                if key in expanded:
                    item.setExpanded(expanded[key])
                if key is not None and key == current_key:
                    tree.setCurrentItem(item, 0, QItemSelectionModel.NoUpdate)
                if key in selected_keys:
                    item.setSelected(True)
                iterator += 1
            tree.doItemsLayout()
            tree.horizontalScrollBar().setValue(horizontal)
            tree.verticalScrollBar().setValue(vertical)
        finally:
            tree.setUpdatesEnabled(True)

    def _populate_tree(self):
        self.tree.clear()
        self._hide_tree_empty_hint(self.tree)
        total_all = 0.0
        bold = QFont()
        bold.setBold(True)
        theme = self._current_theme()
        secondary_color = QColor(theme.get("secondary", theme["accent"]))
        muted_color = QColor(theme["muted"])
        warning_color = self._status_warning_color()
        warning_icon = QIcon(_themed_svg_pixmap("triangle-alert.svg", warning_color, 14))

        sequence_width = self.fontMetrics().horizontalAdvance("99") + 18
        sequence_bg = QBrush(_mix_color(QColor(theme["panel_alt"]), QColor(theme["border"]), 0.78))
        sequence_fg = QBrush(QColor(theme["muted"]))
        self.tree.headerItem().setBackground(0, sequence_bg)
        self.tree.headerItem().setForeground(0, sequence_fg)

        if self.date_groups:
            for group in self.date_groups:
                date_item = QTreeWidgetItem(self.tree)
                stack_count = len(group.stacks)
                group_invoice_count = sum(stack.count for stack in group.stacks)
                group_total = sum(stack.total for stack in group.stacks)
                date_item.setData(0, Qt.UserRole, (self.DATE_ITEM, group.date_str, stack_count, group_invoice_count, group_total, group.locked))
                date_item.setFirstColumnSpanned(True)
                date_item.setText(0, group.date_str)
                date_item.setFont(0, bold)
                date_item.setSizeHint(0, QSize(0, 44))
                date_item.setExpanded(True)

                issues = {
                    item["stack_index"]: item
                    for item in validate_stacks(group.stacks, self._current_max_count(), self._current_max_amount())
                }
                screenshot_map = {
                    screenshot.matched_invoice_id: screenshot
                    for screenshot in group.screenshots
                    if screenshot.matched_invoice_id
                }
                screenshot_by_id = {screenshot.screenshot_id: screenshot for screenshot in group.screenshots}

                if not group.stacks:
                    empty_item = QTreeWidgetItem(date_item)
                    empty_item.setText(0, "暂无分叠；解锁该日期后可新建空叠")
                    empty_item.setForeground(0, muted_color)
                    continue

                for stack in group.stacks:
                    stack_item = QTreeWidgetItem(date_item)
                    stack_item.setData(0, Qt.UserRole, (self.STACK_ITEM, group.date_str, stack.index))
                    label = f"第 {stack.index} 叠"
                    if stack.index in issues:
                        label += "  超限"
                        stack_item.setIcon(0, warning_icon)
                    stack_item.setFirstColumnSpanned(True)
                    stack_item.setText(0, f"{label}        {stack.count} 张发票        ¥{stack.total:.2f}")
                    stack_item.setFont(0, bold)
                    stack_item.setForeground(0, warning_color if stack.index in issues else (secondary_color if stack.count else muted_color))
                    stack_item.setExpanded(True)
                    for i, inv in enumerate(stack.invoices, 1):
                        child = QTreeWidgetItem(stack_item)
                        child.setData(0, Qt.UserRole, (self.INVOICE_ITEM, inv.invoice_id))
                        child.setText(0, str(i))
                        child.setTextAlignment(0, Qt.AlignCenter)
                        child.setBackground(0, sequence_bg)
                        child.setForeground(0, sequence_fg)
                        sequence_width = max(sequence_width, self.fontMetrics().horizontalAdvance(str(i)) + 18)
                        invoice_name = Path(inv.source_path).name
                        child.setText(1, invoice_name)
                        screenshot = screenshot_map.get(inv.invoice_id)
                        if screenshot is None and inv.matched_screenshot_id:
                            screenshot = screenshot_by_id.get(inv.matched_screenshot_id)
                        screenshot_name = Path(screenshot.source_path).name if screenshot is not None else ""
                        child.setToolTip(1, invoice_name)
                        child.setText(2, inv.invoice_number or "")
                        child.setText(3, f"{inv.amount:.2f}" if inv.amount is not None else "-")
                        child.setText(4, screenshot_name)
                        child.setToolTip(4, screenshot_name)
                        child.setText(5, f"{screenshot.amount:.2f}" if screenshot is not None and screenshot.amount is not None else "")
                        child.setText(6, inv.remark)
                        child.setToolTip(6, inv.remark)
                    total_all += stack.total
        elif self.mode == "workspace":
            if not self.stacks:
                self._render_empty_tree_hint("未找到可分组的日期数据")
                self.lbl_stacks.setText("共 0 叠，合计 ¥0.00")
                return
            issues = {
                item["stack_index"]: item
                for item in validate_stacks(self.stacks, self._current_max_count(), self._current_max_amount())
            }
            screenshot_map = {screenshot.matched_invoice_id: screenshot for screenshot in self.screenshots if screenshot.matched_invoice_id}
            screenshot_by_id = {screenshot.screenshot_id: screenshot for screenshot in self.screenshots}

            for stack in self.stacks:
                stack_item = QTreeWidgetItem(self.tree)
                stack_item.setData(0, Qt.UserRole, (self.STACK_ITEM, self.date_edit.date().toString("yyyy年MM月dd日"), stack.index))
                label = f"第 {stack.index} 叠"
                if stack.index in issues:
                    label += "  超限"
                    stack_item.setIcon(0, warning_icon)
                stack_item.setFirstColumnSpanned(True)
                stack_item.setText(0, f"{label}        {stack.count} 张发票        ¥{stack.total:.2f}")
                stack_item.setFont(0, bold)
                stack_item.setForeground(0, warning_color if stack.index in issues else (secondary_color if stack.count else muted_color))
                stack_item.setExpanded(True)
                for i, inv in enumerate(stack.invoices, 1):
                    child = QTreeWidgetItem(stack_item)
                    child.setData(0, Qt.UserRole, (self.INVOICE_ITEM, inv.invoice_id))
                    child.setText(0, str(i))
                    child.setTextAlignment(0, Qt.AlignCenter)
                    child.setBackground(0, sequence_bg)
                    child.setForeground(0, sequence_fg)
                    sequence_width = max(sequence_width, self.fontMetrics().horizontalAdvance(str(i)) + 18)
                    invoice_name = Path(inv.source_path).name
                    child.setText(1, invoice_name)
                    screenshot = screenshot_map.get(inv.invoice_id)
                    if screenshot is None and inv.matched_screenshot_id:
                        screenshot = screenshot_by_id.get(inv.matched_screenshot_id)
                    screenshot_name = Path(screenshot.source_path).name if screenshot is not None else ""
                    child.setToolTip(1, invoice_name)
                    child.setText(2, inv.invoice_number or "")
                    child.setText(3, f"{inv.amount:.2f}" if inv.amount is not None else "-")
                    child.setText(4, screenshot_name)
                    child.setToolTip(4, screenshot_name)
                    child.setText(5, f"{screenshot.amount:.2f}" if screenshot is not None and screenshot.amount is not None else "")
                    child.setText(6, inv.remark)
                    child.setToolTip(6, inv.remark)
                total_all += stack.total

        if not self.date_groups and not self.stacks:
            self._render_empty_tree_hint("暂无分叠\n点击“新建空叠”或拖入 PDF 自动分叠")
            self.lbl_stacks.setText("共 0 叠，合计 ¥0.00")
            return

        self.tree.setColumnWidth(0, min(max(sequence_width, 40), 46))
        stack_count = sum(len(group.stacks) for group in self.date_groups) if self.date_groups else len(self.stacks)
        self.lbl_stacks.setText(f"共 {stack_count} 叠，合计 ¥{total_all:.2f}")

    @workspace_edit("移动发票")
    def _handle_invoice_drop(self, invoice_ids: list[str], date_str: str, stack_index: int, insert_index: int):
        target_stack = self._find_stack(date_str, stack_index)
        if target_stack is None:
            return
        if self._is_date_locked(date_str):
            QMessageBox.information(self, "提示", f"{date_str} 已锁定，不能拖入。")
            return

        ordered = []
        original_target_positions = {
            invoice.invoice_id: position
            for position, invoice in enumerate(target_stack.invoices)
        }
        apply_remark = False
        for invoice_id in invoice_ids:
            inv = next((x for x in self.invoices if x.invoice_id == invoice_id), None)
            if inv:
                source_date = self._invoice_date(inv.invoice_id)
                if source_date and self._is_date_locked(source_date):
                    QMessageBox.information(self, "提示", f"{source_date} 已锁定，不能拖出。")
                    return
                ordered.append(inv)
                apply_remark = apply_remark or inv.stack_index is None
                self._remove_invoice_from_current_group(inv)

        removed_before_target = sum(
            1
            for inv in ordered
            if original_target_positions.get(inv.invoice_id, insert_index) < insert_index
        )
        target_position = max(0, min(insert_index - removed_before_target, len(target_stack.invoices)))
        for offset, inv in enumerate(ordered):
            assign_invoice_to_stack(inv, target_stack, target_position + offset)

        if apply_remark:
            self._apply_current_remark_to_invoices(ordered)

        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        self._render_all()
        self._update_bind_hint()

    def _assign_selected_invoices_to_current_stack(self):
        selected_ids = self._selected_left_invoice_ids()
        if not selected_ids:
            QMessageBox.information(self, "提示", "请先在左侧选中至少一张发票。")
            return

        stack = self._selected_stack()
        if stack is None:
            QMessageBox.information(self, "提示", "请先在右侧选中一个目标叠。")
            return

        date_str = self._selected_stack_date()
        self._assign_invoices_to_stack(selected_ids, stack.index, date_str=date_str, apply_remark=True)

    @workspace_edit("一键分叠")
    def _split_left_invoices_into_stacks(self):
        candidates = [invoice for invoice in self.invoices if invoice.stack_index is None and invoice.amount is not None]
        if not candidates:
            QMessageBox.information(self, "提示", "左侧没有可分叠的已识别发票。")
            return

        max_count = self._current_max_count()
        max_amount = self._current_max_amount()
        oversized = [invoice for invoice in candidates if invoice.amount > max_amount + 1e-9]
        candidates = [invoice for invoice in candidates if invoice.amount <= max_amount + 1e-9]
        if not candidates:
            QMessageBox.information(self, "无法分叠", f"单张发票金额均超过每叠上限 ¥{max_amount:.2f}，已保留在左侧列表。")
            return

        has_stacks = bool(self.stacks) or any(group.stacks for group in self.date_groups)
        target_date = self.date_edit.date() if has_stacks else QDate.currentDate()
        date_str = self._selected_stack_date() if has_stacks else None
        date_str = date_str or target_date.toString("yyyy年MM月dd日")
        if self._is_date_locked(date_str):
            QMessageBox.information(self, "提示", f"{date_str} 已锁定，请先解锁后再分叠。")
            return
        self.date_edit.setDate(QDate.fromString(date_str, "yyyy年MM月dd日"))
        group = self._ensure_current_date_group()
        normalize_stack_indexes(group.stacks)
        for invoice in candidates:
            target = next((stack for stack in group.stacks if can_fit(stack, invoice, max_count, max_amount)), None)
            if target is None:
                target = Stack(index=len(group.stacks) + 1)
                group.stacks.append(target)
            assign_invoice_to_stack(invoice, target)
        self.stacks = group.stacks
        self.mode = "workspace"
        self._apply_current_remark_to_invoices(candidates)

        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        self._render_all()
        self._update_bind_hint()
        self.tree.expandAll()
        self._select_stack_item(date_str, candidates[-1].stack_index)
        if oversized:
            QMessageBox.information(self, "部分发票未分叠", f"{len(oversized)} 张发票的单张金额超过每叠上限 ¥{max_amount:.2f}，已保留在左侧列表。")

    @workspace_edit("返还发票和截图")
    def _return_invoices_to_left(self, invoice_ids: list[str]):
        returning = [invoice for invoice in self.invoices if invoice.invoice_id in invoice_ids and invoice.stack_index is not None]
        for invoice in returning:
            source_date = self._invoice_date(invoice.invoice_id)
            if source_date and self._is_date_locked(source_date):
                QMessageBox.information(self, "提示", f"{source_date} 已锁定，不能移出发票。")
                return
        for invoice in returning:
            self._remove_invoice_from_current_group(invoice)
            for screenshot in self.screenshots:
                if screenshot.matched_invoice_id == invoice.invoice_id:
                    unbind_screenshot(screenshot, self.invoices)
            invoice.matched_screenshot_id = None
        if not returning:
            return
        self._remove_empty_stacks()

    def _delete_selected_tree_invoices(self) -> None:
        current_item = self.tree.currentItem()
        if current_item is None:
            return
        selected_invoice_ids = []
        for item in self.tree.selectedItems():
            payload = item.data(0, Qt.UserRole)
            if isinstance(payload, tuple) and len(payload) >= 2 and payload[0] == self.INVOICE_ITEM:
                selected_invoice_ids.append(payload[1])
        if not selected_invoice_ids:
            return
        self._return_invoices_to_left(selected_invoice_ids)

    @workspace_edit("删除未分叠发票")
    def _delete_selected_left_invoices(self):
        selected = set(self._selected_left_invoice_ids())
        removing = {invoice.invoice_id for invoice in self.invoices if invoice.invoice_id in selected and invoice.stack_index is None}
        for screenshot in self.screenshots:
            if screenshot.matched_invoice_id in removing:
                unbind_screenshot(screenshot, self.invoices)
        self.invoices[:] = [invoice for invoice in self.invoices if invoice.invoice_id not in removing]
        self._render_all()
        self._update_bind_hint()

    @workspace_edit("删除左侧订单截图")
    def _delete_selected_left_screenshots(self):
        selected = {self.screenshot_table.item(row, 0).data(Qt.UserRole)
                    for row in {item.row() for item in self.screenshot_table.selectedItems()}}
        visible = {self.screenshot_table.item(row, 0).data(Qt.UserRole)
                   for row in range(self.screenshot_table.rowCount())}
        removing = selected & visible
        for screenshot in self.screenshots:
            if screenshot.screenshot_id in removing:
                unbind_screenshot(screenshot, self.invoices)
        self.screenshots[:] = [screenshot for screenshot in self.screenshots if screenshot.screenshot_id not in removing]
        self._render_all()
        self._update_bind_hint()

    @workspace_edit("加入所选叠")
    def _assign_invoices_to_stack(
        self,
        invoice_ids: list[str],
        stack_index: int,
        date_str: str | None = None,
        apply_remark: bool = False,
    ):
        target_date = date_str or self.date_edit.date().toString("yyyy年MM月dd日")
        target_stack = self._find_stack(target_date, stack_index)
        if target_stack is None:
            target_stack = next((stack for stack in self.stacks if stack.index == stack_index), None)
        if target_stack is None:
            return

        ordered = []
        for invoice_id in invoice_ids:
            invoice = next((item for item in self.invoices if item.invoice_id == invoice_id), None)
            if invoice is None:
                continue
            ordered.append(invoice)
            self._remove_invoice_from_current_group(invoice)

        for invoice in ordered:
            assign_invoice_to_stack(invoice, target_stack)

        if apply_remark:
            self._apply_current_remark_to_invoices(ordered)

        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        self._render_all()
        self._update_bind_hint()
        self.tree.expandAll()

    def _apply_current_remark_to_invoices(self, invoices: list[Invoice]) -> None:
        remark = self.combo_remark.currentText().strip()
        for invoice in invoices:
            invoice.remark = remark
        if invoices and remark:
            self._remember_common_remark(remark)

    def _find_stack(self, date_str: str, stack_index: int) -> Stack | None:
        if self.date_groups:
            group = next((item for item in self.date_groups if item.date_str == date_str), None)
            if group is None:
                return None
            return next((stack for stack in group.stacks if stack.index == stack_index), None)
        return next((stack for stack in self.stacks if stack.index == stack_index), None)

    def _ensure_current_date_group(self) -> DateGroup:
        date_str = self.date_edit.date().toString("yyyy年MM月dd日")
        group = next((item for item in self.date_groups if item.date_str == date_str), None)
        if group is None:
            group = DateGroup(date_str=date_str, output_dir=Path(self.edit_output.text().strip() or "."), locked=False)
            self.date_groups.append(group)
            self.date_groups.sort(key=lambda item: item.date_str)

        stacks_are_already_grouped = any(self.stacks is item.stacks for item in self.date_groups)
        if self.stacks and not stacks_are_already_grouped:
            normalize_stack_indexes(self.stacks)
            next_index = len(group.stacks) + 1
            for stack in self.stacks:
                if any(stack is existing for item in self.date_groups for existing in item.stacks):
                    continue
                stack.index = next_index
                for invoice in stack.invoices:
                    invoice.stack_index = next_index
                group.stacks.append(stack)
                next_index += 1
            self.stacks = group.stacks

        return group

    def _invoice_date(self, invoice_id: str) -> str | None:
        for group in self.date_groups:
            for stack in group.stacks:
                if any(invoice.invoice_id == invoice_id for invoice in stack.invoices):
                    return group.date_str
        return None

    def _remove_invoice_from_current_group(self, invoice: Invoice) -> None:
        stacks = [stack for group in self.date_groups for stack in group.stacks] if self.date_groups else self.stacks
        for stack in stacks:
            stack.invoices[:] = [existing for existing in stack.invoices if existing.invoice_id != invoice.invoice_id]
        invoice.stack_index = None

    def _is_date_locked(self, date_str: str) -> bool:
        group = next((item for item in self.date_groups if item.date_str == date_str), None)
        return bool(group.locked) if group is not None else False

    def _selected_left_invoice_ids(self) -> list[str]:
        rows = sorted({item.row() for item in self.table.selectedItems()})
        ids: list[str] = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.UserRole):
                ids.append(item.data(Qt.UserRole))
        return ids

    def _selected_stack(self) -> Stack | None:
        current_item = self.tree.currentItem()
        if current_item is None:
            return None
        payload = current_item.data(0, Qt.UserRole)
        if not isinstance(payload, tuple):
            return None
        if payload[0] == self.STACK_ITEM:
            return self._find_stack(payload[1], payload[2])
        if payload[0] == self.INVOICE_ITEM and current_item.parent() is not None:
            parent_payload = current_item.parent().data(0, Qt.UserRole)
            if isinstance(parent_payload, tuple) and parent_payload[0] == self.STACK_ITEM:
                return self._find_stack(parent_payload[1], parent_payload[2])
        return None

    def _selected_stack_date(self) -> str | None:
        current_item = self.tree.currentItem()
        if current_item is None:
            return None
        payload = current_item.data(0, Qt.UserRole)
        if isinstance(payload, tuple) and payload[0] == self.STACK_ITEM:
            return payload[1]
        if isinstance(payload, tuple) and payload[0] == self.INVOICE_ITEM and current_item.parent() is not None:
            parent_payload = current_item.parent().data(0, Qt.UserRole)
            if isinstance(parent_payload, tuple) and parent_payload[0] == self.STACK_ITEM:
                return parent_payload[1]
        return None

    def _select_stack_item(self, date_str: str, stack_index: int) -> None:
        target_payload = (self.STACK_ITEM, date_str, stack_index)
        for i in range(self.tree.topLevelItemCount()):
            date_item = self.tree.topLevelItem(i)
            date_item.setExpanded(True)
            for j in range(date_item.childCount()):
                stack_item = date_item.child(j)
                if stack_item.data(0, Qt.UserRole) == target_payload:
                    self.tree.setCurrentItem(stack_item)
                    self.tree.scrollToItem(stack_item)
                    return

    def _find_duplicate_invoice(self, candidate: Invoice) -> Invoice | None:
        if candidate.unique_key is None:
            return None
        for invoice in self.invoices:
            if invoice is candidate:
                continue
            if invoice.unique_key == candidate.unique_key:
                return invoice
        return None

    def _open_in_explorer(self, path: Path) -> None:
        target = path.resolve()
        if not target.exists():
            QMessageBox.warning(self, "文件不存在", str(path))
            return
        subprocess.run(["explorer", "/select,", str(target)], check=False)

    def _show_duplicate_invoice_dialog(self, imported: Invoice, duplicate: Invoice) -> None:
        duplicate_date = self._invoice_date(duplicate.invoice_id)
        duplicate_stack = duplicate.stack_index
        duplicate_key = self._format_invoice_identity(duplicate)
        location = f"{duplicate_date} 第{duplicate_stack}叠" if duplicate_date and duplicate_stack else "未分叠"
        message_box = QMessageBox(self)
        message_box.setWindowModality(Qt.WindowModal)
        message_box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        message_box.setIcon(QMessageBox.Warning)
        message_box.setWindowTitle("重复发票")
        message_box.setText(
            f"发现相同发票号码，新增项已从工作区移除。\n"
            f"{duplicate_key}\n"
            f"已有位置：{location}\n\n"
            f"新文件：{imported.source_path}\n"
            f"已有文件：{duplicate.source_path}\n\n"
            "可将新增的重复 PDF 移入回收站，已录入发票会保留。"
        )
        open_new_button = message_box.addButton("定位新文件", QMessageBox.ActionRole)
        open_old_button = message_box.addButton("定位历史文件", QMessageBox.ActionRole)
        delete_button = message_box.addButton("删除新增的重复发票", QMessageBox.DestructiveRole)
        protected_paths = {
            path.resolve() for invoice in self.invoices
            for path in (invoice.source_path, invoice.output_path) if path is not None
        }
        delete_button.setEnabled(imported.source_path.resolve() not in protected_paths)
        message_box.addButton(QMessageBox.Ok)
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()
        # Show the native window before requesting foreground activation. Only
        # this short-lived dialog stays on top, not the main workspace.
        message_box.show()
        message_box.raise_()
        message_box.activateWindow()
        message_box.exec()
        clicked = message_box.clickedButton()
        if clicked is open_new_button:
            self._open_in_explorer(imported.source_path)
        elif clicked is open_old_button:
            self._open_in_explorer(duplicate.source_path)
        elif clicked is delete_button:
            try:
                recycle_file(imported.source_path)
            except OSError as error:
                QMessageBox.warning(self, "删除失败", f"新增项已从工作区移除，但文件未能移入回收站：\n{error}")

    def _format_invoice_identity(self, invoice: Invoice) -> str:
        if invoice.unique_key is None:
            return "未识别到发票号码"
        return f"发票号码：{invoice.unique_key}"

    def _bind_selected_screenshot(self):
        screenshot = self._selected_screenshot()
        if screenshot is None:
            QMessageBox.information(self, "提示", "请先在左侧选中一张订单截图。")
            return
        if screenshot.amount is None:
            QMessageBox.warning(self, "无法绑定", "该截图尚未识别出实付款金额。")
            return

        invoice = self._selected_invoice()
        if invoice is None:
            QMessageBox.information(self, "提示", "请再在右侧选中一张发票。")
            return
        self._bind_screenshot_to_invoice(screenshot.screenshot_id, invoice.invoice_id, interactive=True)

    def _handle_screenshot_drop(self, screenshot_id: str, invoice_id: str):
        self._bind_screenshot_to_invoice(screenshot_id, invoice_id, interactive=True)

    def _update_bind_hint(self):
        selected_screenshot = self._selected_screenshot()
        selected_invoice = self._selected_invoice()
        if selected_screenshot is None and selected_invoice is None:
            self.lbl_bind_hint.setText("请先选中一张订单截图，再在右侧选中一张发票。")
            return
        if selected_screenshot is None:
            self.lbl_bind_hint.setText("已选右侧发票，请再选中左侧一张订单截图。")
            return
        if selected_invoice is None:
            self.lbl_bind_hint.setText(f"已选截图：{selected_screenshot.filename}；请再在右侧选中一张发票。")
            return
        self.lbl_bind_hint.setText(f"准备绑定：{selected_screenshot.filename} → {selected_invoice.filename}")

    def _selected_screenshot(self) -> OrderScreenshot | None:
        row = self.screenshot_table.currentRow()
        if row < 0:
            return None
        screenshot_item = self.screenshot_table.item(row, 0)
        if screenshot_item is None:
            return None
        screenshot_id = screenshot_item.data(Qt.UserRole)
        return next((item for item in self.screenshots if item.screenshot_id == screenshot_id), None)

    def _selected_invoice(self) -> Invoice | None:
        current_item = self.tree.currentItem()
        if current_item is None:
            return None
        payload = current_item.data(0, Qt.UserRole)
        if not isinstance(payload, tuple) or len(payload) < 2 or payload[0] != self.INVOICE_ITEM:
            return None
        invoice_id = payload[1]
        return next((item for item in self.invoices if item.invoice_id == invoice_id), None)

    @workspace_edit("绑定订单截图")
    def _bind_screenshot_to_invoice(self, screenshot_id: str, invoice_id: str, interactive: bool = False):
        screenshot = next((item for item in self.screenshots if item.screenshot_id == screenshot_id), None)
        if screenshot is None:
            return
        invoice = next((item for item in self.invoices if item.invoice_id == invoice_id), None)
        if invoice is None:
            return
        invoice_date = self._invoice_date(invoice.invoice_id)
        if invoice_date and self._is_date_locked(invoice_date):
            if interactive:
                QMessageBox.information(self, "提示", f"{invoice_date} 已锁定，不能绑定截图。")
            return
        if screenshot.amount is None:
            if interactive:
                QMessageBox.warning(self, "无法绑定", "该截图尚未识别出实付款金额。")
            return
        if invoice.amount is None:
            if interactive:
                QMessageBox.warning(self, "无法绑定", "目标发票尚未识别出金额。")
            return
        if interactive and round(invoice.amount, 2) != round(screenshot.amount, 2):
            choice = QMessageBox.question(
                self,
                "金额不一致",
                f"当前截图识别金额为 ¥{screenshot.amount:.2f}，所选发票金额为 ¥{invoice.amount:.2f}。\n是否仍然绑定？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                return

        unbind_screenshot(screenshot, self.invoices)
        if invoice.matched_screenshot_id:
            existing = next((item for item in self.screenshots if item.screenshot_id == invoice.matched_screenshot_id), None)
            if existing is not None:
                unbind_screenshot(existing, self.invoices)
        bind_screenshot_to_invoice(screenshot, invoice)
        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        self._render_all()
        self._update_bind_hint()

    @workspace_edit("新建空叠")
    def _add_empty_stack(self):
        date_str = self.date_edit.date().toString("yyyy年MM月dd日")
        group = self._ensure_current_date_group()
        if group.locked:
            QMessageBox.information(self, "提示", f"{date_str} 已锁定，请先解锁后再新建空叠。")
            return

        normalize_stack_indexes(group.stacks)
        stack = Stack(index=len(group.stacks) + 1)
        group.stacks.append(stack)
        self.stacks = group.stacks
        self.mode = "workspace"
        self._render_all()
        self._update_bind_hint()
        self.tree.expandAll()
        self._select_stack_item(date_str, stack.index)

    @workspace_edit("删除空叠")
    def _remove_empty_stacks(self):
        if self.date_groups:
            for group in self.date_groups:
                if group.locked:
                    continue
                # self.stacks aliases this list; replacing it makes the next
                # split mistake the old list for ungrouped stacks and add it twice.
                group.stacks[:] = [stack for stack in group.stacks if stack.invoices]
            self._render_all()
            self._update_bind_hint()
            return
        self.stacks = [stack for stack in self.stacks if stack.invoices]
        self._render_all()
        self._update_bind_hint()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if path:
            self.edit_output.setText(path)

    def _open_batch(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "选择包含多个叠目录的上级文件夹",
            self.edit_output.text().strip() or "",
        )
        if not path:
            return
        try:
            date_groups, errors = load_date_groups_from_parent(Path(path))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", str(e))
            return
        if not date_groups:
            message = "所选目录下未找到可打开的 invoices.json。"
            if errors:
                message += "\n\n" + "\n".join(errors[:8])
            QMessageBox.information(self, "提示", message)
            return

        self.date_groups = date_groups
        self.stacks = []
        self.batch = None
        self.mode = "workspace"
        self.invoices = []
        self.screenshots = []
        for group in self.date_groups:
            self.invoices.extend(group.all_invoices())
            self.screenshots.extend(group.screenshots)
        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        newest_group = max(self.date_groups, key=lambda item: item.date_str)
        newest_group.locked = False
        self.edit_output.setText(str(newest_group.output_dir))
        qdate = QDate.fromString(newest_group.date_str, "yyyy年MM月dd日")
        if qdate.isValid():
            self.date_edit.setDate(qdate)
        self._render_all()
        self._update_bind_hint()
        self._opened_stack_snapshots = self._snapshot_stacks(
            (group.date_str, stack, group.screenshots)
            for group in self.date_groups
            for stack in group.stacks
        )
        QMessageBox.information(self, "已打开", f"已按日期分组载入 {len(self.date_groups)} 个日期。")
        if errors:
            QMessageBox.warning(self, "部分文件未能打开", "\n".join(errors[:8]))
        self._reset_workspace_history()

    def _stack_snapshot(self, stack: Stack, screenshots: list[OrderScreenshot]) -> dict:
        invoice_ids = {invoice.invoice_id for invoice in stack.invoices}
        screenshot_map = {
            screenshot.matched_invoice_id: screenshot
            for screenshot in screenshots
            if screenshot.matched_invoice_id in invoice_ids
        }
        return {
            "invoice_order": [invoice.invoice_id for invoice in stack.invoices],
            "invoice_names": {invoice.invoice_id: invoice.filename for invoice in stack.invoices},
            "invoice_data": {
                invoice.invoice_id: (
                    invoice.amount,
                    invoice.invoice_code,
                    invoice.invoice_number,
                    invoice.remark,
                    invoice.matched_screenshot_id,
                )
                for invoice in stack.invoices
            },
            "screenshots": {
                invoice_id: (screenshot.screenshot_id, screenshot.filename, screenshot.amount)
                for invoice_id, screenshot in screenshot_map.items()
            },
        }

    def _snapshot_stacks(self, entries) -> dict[tuple[str, int], dict]:
        return {
            (date_str, stack.index): self._stack_snapshot(stack, screenshots)
            for date_str, stack, screenshots in entries
        }

    def _stack_snapshot_content(self, snapshot: dict) -> tuple:
        return (
            tuple(snapshot["invoice_order"]),
            tuple(sorted(snapshot["invoice_data"].items())),
            tuple(sorted((invoice_id, value[0], value[2]) for invoice_id, value in snapshot["screenshots"].items())),
        )

    def _collect_stack_changes(self, entries) -> tuple[list[dict], list[dict]]:
        new_stacks: list[dict] = []
        modified_stacks: list[dict] = []
        for date_str, stack, screenshots in entries:
            key = (date_str, stack.index)
            current = self._stack_snapshot(stack, screenshots)
            original = self._opened_stack_snapshots.get(key)
            item = {
                "key": key,
                "date": date_str,
                "stack": stack,
                "screenshots": screenshots,
                "snapshot": current,
            }
            if original is None:
                item["added"] = list(current["invoice_names"].values())
                new_stacks.append(item)
                continue
            if self._stack_snapshot_content(current) == self._stack_snapshot_content(original):
                continue

            original_ids = set(original["invoice_order"])
            current_ids = set(current["invoice_order"])
            added_ids = current_ids - original_ids
            removed_ids = original_ids - current_ids
            common_original = [item_id for item_id in original["invoice_order"] if item_id in current_ids]
            common_current = [item_id for item_id in current["invoice_order"] if item_id in original_ids]
            original_screenshot_ids = {value[0] for value in original["screenshots"].values()}
            current_screenshot_ids = {value[0] for value in current["screenshots"].values()}
            item.update({
                "added": [current["invoice_names"][item_id] for item_id in current["invoice_order"] if item_id in added_ids],
                "removed": [original["invoice_names"][item_id] for item_id in original["invoice_order"] if item_id in removed_ids],
                "order_changed": common_original != common_current,
                "screenshots_added": [
                    value[1] for value in current["screenshots"].values()
                    if value[0] not in original_screenshot_ids
                ],
                "screenshots_removed": [
                    value[1] for value in original["screenshots"].values()
                    if value[0] not in current_screenshot_ids
                ],
                "details_changed": current["invoice_data"] != original["invoice_data"],
            })
            modified_stacks.append(item)
        return new_stacks, modified_stacks

    def _format_stack_changes(self, new_stacks: list[dict], modified_stacks: list[dict]) -> str:
        lines: list[str] = []
        if new_stacks:
            lines.append("新增叠：")
            for item in new_stacks:
                lines.append(f"  {item['date']} 第{item['stack'].index}叠（{item['stack'].count} 张发票）")
                for name in item["added"]:
                    lines.append(f"    + {name}")
        if modified_stacks:
            if lines:
                lines.append("")
            lines.append("已修改叠：")
            for item in modified_stacks:
                lines.append(f"  {item['date']} 第{item['stack'].index}叠")
                for name in item["added"]:
                    lines.append(f"    + 新增发票：{name}")
                for name in item["removed"]:
                    lines.append(f"    - 删除发票：{name}")
                for name in item["screenshots_added"]:
                    lines.append(f"    + 新增截图：{name}")
                for name in item["screenshots_removed"]:
                    lines.append(f"    - 删除截图：{name}")
                if item["order_changed"]:
                    lines.append("    • 发票顺序已调整")
                if item["details_changed"] and not (item["added"] or item["removed"] or item["order_changed"]):
                    lines.append("    • 发票信息、实际报销人或截图绑定已调整")
                elif not (
                    item["added"] or item["removed"] or item["order_changed"]
                    or item["screenshots_added"] or item["screenshots_removed"]
                    or item["details_changed"]
                ):
                    lines.append("    • 截图信息已调整")
        return "\n".join(lines)

    def _choose_stack_changes(self, new_stacks: list[dict], modified_stacks: list[dict]) -> list[dict] | None:
        if not new_stacks and not modified_stacks:
            QMessageBox.information(self, "没有改动", "未检测到新增叠或已修改叠，无需输出。")
            return None
        dialog = SaveScopeDialog(
            self,
            new_stacks,
            modified_stacks,
            self._current_theme(),
        )
        dialog.exec()
        return dialog.selected_items

    def _remember_saved_snapshots(self, items: list[dict]) -> None:
        for item in items:
            self._opened_stack_snapshots[item["key"]] = self._stack_snapshot(
                item["stack"], item["screenshots"]
            )

    def _save_output(self):
        output_dir = Path(self.edit_output.text().strip())
        if not output_dir.is_dir():
            QMessageBox.warning(self, "错误", "输出路径不存在，请重新选择。")
            return
        reimburser = self.combo_reimburser.currentText().strip()

        if self.date_groups:
            unlocked_groups = [group for group in self.date_groups if not group.locked]
            if not unlocked_groups:
                QMessageBox.information(self, "提示", "当前没有已解锁的日期，无需输出。")
                return
            entries = [
                (group.date_str, stack, group.screenshots)
                for group in unlocked_groups
                for stack in group.stacks
            ]
            new_stacks, modified_stacks = self._collect_stack_changes(entries)
            selected_items = self._choose_stack_changes(new_stacks, modified_stacks)
            if selected_items is None:
                return
            all_results: list[dict] = []
            for group in unlocked_groups:
                selected_indexes = {
                    item["stack"].index for item in selected_items
                    if item["date"] == group.date_str
                }
                if not selected_indexes:
                    continue
                selected_stacks = [stack for stack in group.stacks if stack.index in selected_indexes]
                issues = validate_stacks(selected_stacks, self._current_max_count(), self._current_max_amount())
                if issues:
                    QMessageBox.warning(self, "超限", f"{group.date_str} 存在超限叠：\n{self._format_issues(issues)}")
                    return
                batch = Batch(
                    date_str=group.date_str,
                    output_dir=output_dir if group.output_dir is None else group.output_dir,
                    stacks=group.stacks,
                    screenshots=group.screenshots,
                    active_stack_index=group.active_stack_index,
                )
                try:
                    results = materialize_selected_stacks(batch, selected_indexes, reimburser)
                except Exception as e:
                    QMessageBox.critical(self, "输出失败", f"{group.date_str}\n{e}")
                    return
                group.output_dir = batch.output_dir
                all_results.extend(results)
            self._remember_saved_snapshots(selected_items)
            self._remember_common_reimburser(reimburser)
            self._render_all()
            self._update_bind_hint()
            self._reset_workspace_history()
            QMessageBox.information(self, "完成", self._format_results(all_results, "已保存并输出"))
            return

        self._generate_or_update_single(output_dir, reimburser)

    def _generate_or_update_single(self, output_dir: Path, reimburser: str):
        issues = validate_stacks(self.stacks, self._current_max_count(), self._current_max_amount())
        if issues:
            QMessageBox.warning(self, "超限", self._format_issues(issues))
            return
        if not self.stacks:
            QMessageBox.information(self, "提示", "没有可输出的分叠。")
            return
        failed = [inv for inv in self.invoices if inv.amount is None]
        if failed and QMessageBox.question(
            self,
            "有发票未能识别",
            "存在未识别金额的 PDF，它们不会被放入任何叠。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        date_str = self.date_edit.date().toString("yyyy年MM月dd日")
        if self.batch is None:
            try:
                self.batch, results = create_new_batch(self.stacks, output_dir, date_str, self.screenshots, reimburser)
            except Exception as e:
                QMessageBox.critical(self, "输出失败", str(e))
                return
            self.mode = "update"
            self.edit_output.setText(str(self.batch.output_dir))
            self._remember_common_reimburser(reimburser)
            self._render_all()
            self._update_bind_hint()
            self._opened_stack_snapshots = self._snapshot_stacks(
                (date_str, stack, self.screenshots) for stack in self.stacks
            )
            self._reset_workspace_history()
            QMessageBox.information(self, "完成", self._format_results(results, "已保存并输出"))
            return

        self.batch.stacks = self.stacks
        self.batch.screenshots = self.screenshots
        self.batch.date_str = date_str
        self.batch.output_dir = output_dir
        current_item = self.tree.currentItem()
        if current_item is not None:
            stack = self._selected_stack()
            if stack is not None:
                self.batch.active_stack_index = stack.index
        elif self.stacks:
            self.batch.active_stack_index = self.stacks[0].index
        if self.batch.stack_dir is None and self.stacks:
            active_index = self.batch.active_stack_index or self.stacks[0].index
            active_stack = next((s for s in self.stacks if s.index == active_index), self.stacks[0])
            self.batch.stack_dir = self.batch.output_dir / active_stack.folder_name(self.batch.date_str)
        entries = [(date_str, stack, self.screenshots) for stack in self.stacks]
        new_stacks, modified_stacks = self._collect_stack_changes(entries)
        selected_items = self._choose_stack_changes(new_stacks, modified_stacks)
        if selected_items is None:
            return
        selected_indexes = {item["stack"].index for item in selected_items}
        try:
            results = materialize_selected_stacks(self.batch, selected_indexes, reimburser)
        except Exception as e:
            QMessageBox.critical(self, "输出失败", str(e))
            return
        self.invoices = self.batch.all_invoices() + [inv for inv in self.invoices if inv.stack_index is None]
        self.screenshots = self.batch.screenshots
        sync_screenshot_stack_indexes(self.invoices, self.screenshots)
        self._remember_saved_snapshots(selected_items)
        self._remember_common_reimburser(reimburser)
        self._render_all()
        self._update_bind_hint()
        self._reset_workspace_history()
        QMessageBox.information(self, "完成", self._format_results(results, "已保存并输出"))

    def _refresh_buttons(self):
        has_output = bool(self.edit_output.text().strip())
        invoice_idle = self._worker is None or not self._worker.isRunning()
        screenshot_idle = self._screenshot_worker is None or not self._screenshot_worker.isRunning()
        is_idle = invoice_idle and screenshot_idle
        has_stacks = bool(self.stacks) or any(group.stacks for group in self.date_groups)
        has_left_invoices = any(invoice.stack_index is None for invoice in self.invoices)
        self.btn_save_output.setEnabled(has_output and is_idle and has_stacks)
        self.btn_bind_screenshot.setEnabled(bool(self.screenshots) and is_idle)
        self.btn_assign_selected.setEnabled(has_left_invoices and has_stacks and is_idle)
        self.btn_split_stacks.setEnabled(has_left_invoices and is_idle)
        idle = not self._workspace_busy()
        self.btn_undo.setEnabled(bool(self._undo_history) and idle)
        self.btn_redo.setEnabled(bool(self._redo_history) and idle)
        self.btn_undo.setToolTip(f"撤销：{self._undo_history[-1][0]}（Ctrl+Z）" if self._undo_history else "撤销（Ctrl+Z）")
        self.btn_redo.setToolTip(f"重做：{self._redo_history[-1][0]}（Ctrl+Y）" if self._redo_history else "重做（Ctrl+Y）")
        self.btn_open.setEnabled(idle)

    def _current_max_count(self) -> int:
        return self.spin_max_count.value()

    def _current_max_amount(self) -> float:
        return self.spin_max_amount.value()

    def _clear_workspace(self):
        self.invoices = []
        self.screenshots = []
        self.stacks = []
        self.date_groups = []
        self.batch = None
        self.mode = "new"
        self._opened_stack_snapshots = {}
        self.table.setRowCount(0)
        self.screenshot_table.setRowCount(0)
        self.tree.clear()
        self.lbl_count.setText("0 张")
        self.lbl_screenshot_count.setText("0 张")
        self.lbl_stacks.setText("")
        self._update_bind_hint()
        self._refresh_buttons()
        self._reset_workspace_history()

    def _format_issues(self, issues: list[dict]) -> str:
        lines = []
        max_count = self._current_max_count()
        max_amount = self._current_max_amount()
        for item in issues:
            parts = []
            if item["count_exceeded"]:
                parts.append(f"张数 {item['count']} > {max_count}")
            if item["amount_exceeded"]:
                parts.append(f"金额 ¥{item['total']:.2f} > ¥{max_amount:.2f}")
            lines.append(f"第{item['stack_index']}叠：" + "，".join(parts))
        return "\n".join(lines)

    def _format_results(self, results: list[dict], prefix: str) -> str:
        summary = "\n".join(
            f"第{r['stack_index']}叠：{r['count']} 张发票，{r['screenshot_count']} 张截图，¥{r['total']:.2f}，状态文件：{Path(r['folder']) / STATE_FILE}"
            for r in results
        )
        return f"{prefix} {len(results)} 叠：\n{summary}\n\n总输出目录：{self.edit_output.text().strip()}"
