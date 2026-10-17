import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from startup_controller import StartupController
from ui.app_identity import apply_application_icon, set_windows_app_id


def main():
    set_windows_app_id()
    if len(sys.argv) == 3 and sys.argv[1] == "--apply-update":
        from pathlib import Path
        from core.portable_update import apply_update
        result = apply_update(Path(sys.argv[2]))
        if not result["success"]:
            from PySide6.QtWidgets import QMessageBox
            app = QApplication([])
            apply_application_icon(app)
            QMessageBox.warning(None, "更新未完成", result.get("error", "请从发布页重新下载便携版。"))
        raise SystemExit(0 if result["success"] else 1)
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        from core.packaged_smoke_test import run
        raise SystemExit(run(sys.argv[2]))
    app = QApplication(sys.argv)
    apply_application_icon(app)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    controller = StartupController(app)
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
