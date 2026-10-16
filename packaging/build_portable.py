"""Build the Windows portable application without bundling local preferences."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app_version import APP_VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", default="dist")
    args = parser.parse_args()
    build = ROOT / "build" / "portable"
    build.mkdir(parents=True, exist_ok=True)
    name = f"HDU-InvoiceAllInOne-v{APP_VERSION}-Portable"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onefile",
        "--name", name, "--distpath", str(ROOT / args.dist_dir),
        "--workpath", str(build), "--specpath", str(build),
        "--add-data", f"{ROOT / 'assets'}:assets",
        "--collect-all", "rapidocr_onnxruntime", "--collect-all", "onnxruntime",
        str(ROOT / "main.py"),
    ]
    log = build / "build.log"
    print(f"Building {name}.exe; log: {log}", flush=True)
    with log.open("w", encoding="utf-8") as output:
        result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(encoding="utf-8", errors="replace")[-6000:])
        raise SystemExit(result.returncode)
    print(f"Built: {ROOT / args.dist_dir / (name + '.exe')}", flush=True)


if __name__ == "__main__":
    main()
