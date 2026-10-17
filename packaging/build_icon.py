"""Render the existing vector logo into a transparent, multi-resolution ICO."""

import io
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def build_icon():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PIL import Image
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    # Keep the existing mark, with the default indigo theme and even icon margins.
    svg = (ROOT / "assets" / "logo.svg").read_text(encoding="utf-8")
    svg = svg.replace("#2563EB", "#313c69").replace('viewBox="0 0 96 96"', 'viewBox="12 9 72 72"')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("The application logo is not a valid SVG")
    images = []
    for size in ICON_SIZES:
        image = QImage(size * 4, size * 4, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        raster = Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGBA")
        images.append(raster.resize((size, size), Image.Resampling.LANCZOS))
    target = ROOT / "assets" / "app.ico"
    images[-1].save(target, format="ICO", sizes=[(s, s) for s in ICON_SIZES], append_images=images[:-1])
    return target


if __name__ == "__main__":
    print(build_icon())
