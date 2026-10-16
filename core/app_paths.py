"""Keep user preferences outside the temporary directory used by one-file builds."""

import json
import os
import sys
import tempfile
from pathlib import Path


RESOURCE_ROOT = Path(__file__).resolve().parent.parent


def default_data_directory() -> Path:
    if getattr(sys, "frozen", False):
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return local / "HDU-InvoiceAllInOne"
    return RESOURCE_ROOT


def _location_file() -> Path:
    name = "data-location.json" if getattr(sys, "frozen", False) else ".local-data-location.json"
    return default_data_directory() / name


def settings_path() -> Path:
    try:
        location = json.loads(_location_file().read_text(encoding="utf-8"))
        directory = Path(location["data_directory"])
        if directory.is_absolute():
            return directory / "settings.json"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return default_data_directory() / "settings.json"


def write_json_atomic(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def relocate_data_directory(directory: Path, settings: dict) -> Path:
    directory = directory.expanduser().resolve()
    if getattr(sys, "frozen", False) and directory.is_relative_to(RESOURCE_ROOT.resolve()):
        raise ValueError("请选择程序临时目录以外的持久保存位置。")
    destination = directory / "settings.json"
    if destination == settings_path().resolve():
        return destination
    if destination.exists():
        try:
            previous = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None
        if previous != settings:
            raise ValueError("目标文件夹已有其他设置，请选择空文件夹，避免覆盖。")
    write_json_atomic(destination, settings)
    # Switch only after the current preferences have been copied successfully.
    # Keep the original as a recoverable backup; do not move invoices or exports.
    write_json_atomic(_location_file(), {"data_directory": str(directory)})
    return destination


def load_settings(path: Path | None = None) -> dict:
    path = path or settings_path()
    candidates = [path]
    if getattr(sys, "frozen", False):
        candidates.extend((Path(sys.executable).parent / "settings.json", RESOURCE_ROOT / "settings.json"))
    for candidate in dict.fromkeys(candidates):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return {}
