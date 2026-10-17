"""Use the workbench logo for Windows taskbar grouping and Qt windows."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


APP_ID = "NovaXF.HDUInvoiceAllInOne"
APP_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "app.ico"


def set_windows_app_id():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def apply_application_icon(app):
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
