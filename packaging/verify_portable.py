"""Verify a standalone executable in an isolated folder with no source files."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app_version import APP_VERSION


def main():
    executable = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / f"HDU-InvoiceAllInOne-v{APP_VERSION}-Portable.exe"
    with tempfile.TemporaryDirectory(prefix="hdu-portable-verify-") as folder:
        isolated = Path(folder)
        copy = isolated / executable.name
        shutil.copy2(executable, copy)
        report = isolated / "smoke.json"
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["LOCALAPPDATA"] = str(isolated / "user-data")
        env.pop("PYTHONPATH", None)
        result = subprocess.run([str(copy), "--smoke-test", str(report)], cwd=isolated, env=env, timeout=180)
        data = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {"error": "No smoke-test report"}
        print(json.dumps(data, ensure_ascii=True, indent=2))
        if result.returncode or not data.get("success") or not data.get("frozen"):
            raise SystemExit(1)
        # A second process must discover the migrated directory independently.
        first_settings = data["settings"]
        result = subprocess.run([str(copy), "--smoke-test", str(report)], cwd=isolated, env=env, timeout=180)
        data = json.loads(report.read_text(encoding="utf-8"))
        if result.returncode or not data.get("success") or data["settings"] != first_settings:
            raise SystemExit("Preferences did not persist across portable launches")
    print("PASS: standalone executable, UI assets, settings migration across launches, PDF parsing and OCR models")


if __name__ == "__main__":
    main()
