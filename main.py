import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from startup_controller import StartupController


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    controller = StartupController(app)
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
