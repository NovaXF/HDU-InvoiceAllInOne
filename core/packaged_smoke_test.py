"""Noninteractive verification entry point for release executables."""

import json
import sys
import tempfile
import traceback
from pathlib import Path


def _sample_pdf(path):
    stream = b"BT /F1 14 Tf 50 700 Td (\\24516.00) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, content in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + content + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(data)


def run(output_path):
    report = {"success": False, "frozen": bool(getattr(sys, "frozen", False))}
    window = None
    try:
        from PySide6.QtWidgets import QApplication
        from PIL import Image
        from core.order_screenshot_rules.common import extract_ocr_tokens
        from core.pdf_parser import extract_invoice_data
        from core.app_paths import default_data_directory, load_settings, relocate_data_directory, settings_path
        from ui.main_window import MainWindow
        from ui.splash_screen import SplashScreen
        app = QApplication([])
        app.setStyle("Fusion")
        window = MainWindow()
        window.show()
        app.processEvents()
        splash = SplashScreen()
        assert splash.logo_label.renderer.isValid()
        assert splash.wordmark.renderer.isValid()
        assert window.version_panel._renderer.isValid()
        report["ui"] = window.isVisible()
        window._save_settings()
        assert settings_path().is_file()
        destination = default_data_directory().parent / "custom-data"
        window.settings_path = relocate_data_directory(destination, window.settings)
        assert settings_path() == window.settings_path
        assert load_settings() == window.settings
        report["data_migration"] = True
        report["settings"] = str(settings_path())
        with tempfile.TemporaryDirectory(prefix="hdu-portable-smoke-") as folder:
            path = Path(folder)
            _sample_pdf(path / "sample.pdf")
            assert extract_invoice_data(path / "sample.pdf").amount == 16
            report["pdf"] = True
            Image.new("RGB", (320, 100), "white").save(path / "blank.png")
            assert extract_ocr_tokens(path / "blank.png") == []
            report["ocr"] = True
        splash.close()
        report["success"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if window is not None:
            window.close()
        Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1
