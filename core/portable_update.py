"""Replace a running portable executable after it exits, preserving user data."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from core.app_paths import write_json_atomic


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_update(source: Path, target: Path, data_directory: Path) -> Path:
    source, target = source.resolve(), target.resolve()
    if source == target or source.suffix.lower() != ".exe" or not target.is_file():
        raise ValueError("便携版更新文件或目标位置无效。")
    # Fail before closing the app if its directory cannot be written to.
    with tempfile.TemporaryFile(dir=target.parent):
        pass
    directory = data_directory / "updates"
    directory.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix="update-", dir=directory))
    plan = working / "plan.json"
    write_json_atomic(plan, {"app": "HDU-InvoiceAllInOne", "source": str(source),
                             "target": str(target), "sha256": file_digest(source)})
    return plan


def launch_helper(source: Path, plan: Path):
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen([str(source), "--apply-update", str(plan)], env=env)


def apply_update(plan_path: Path) -> dict:
    stage = None
    replaced = False
    report = {"success": False}
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if plan.get("app") != "HDU-InvoiceAllInOne":
            raise ValueError("更新计划无效。")
        source, target = Path(plan["source"]).resolve(), Path(plan["target"]).resolve()
        if source != Path(sys.executable).resolve() or target.suffix.lower() != ".exe" or source == target:
            raise ValueError("更新来源或目标无效。")
        if file_digest(source) != plan["sha256"]:
            raise ValueError("更新文件校验失败。")
        backup = plan_path.parent / "previous.exe"
        shutil.copy2(target, backup)
        stage = target.with_name(f".{target.name}.{uuid.uuid4().hex}.update")
        shutil.copy2(source, stage)
        deadline = time.monotonic() + 90
        while True:
            try:
                os.replace(stage, target)
                replaced = True
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("旧程序尚未退出或目录无法写入，请关闭程序后手动替换。")
                time.sleep(0.25)
        env = os.environ.copy()
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        subprocess.Popen([str(target)], env=env, cwd=target.parent)
        report["success"] = True
    except Exception as error:
        report["error"] = str(error)
        if replaced:
            try:
                shutil.copy2(backup, target)
                report["restored"] = True
            except OSError:
                report["backup"] = str(backup)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
        write_json_atomic(plan_path.parent / "result.json", report)
    return report
