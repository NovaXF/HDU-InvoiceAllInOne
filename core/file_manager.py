import json
import shutil
import tempfile
from pathlib import Path

from core.excel_writer import generate_stack_excel
from models.invoice import Batch, DateGroup, OrderScreenshot, Stack


STATE_FILE = "invoices.json"


def _state_path_for_stack(stack_dir: Path) -> Path:
    return stack_dir / STATE_FILE


def _write_stack_state(batch: Batch, stack: Stack, stack_dir: Path | None = None) -> None:
    stack_dir = stack_dir or batch.output_dir / stack.folder_name(batch.date_str)
    stack_dir.mkdir(parents=True, exist_ok=True)
    invoice_ids = {invoice.invoice_id for invoice in stack.invoices}
    stack_batch = Batch(
        date_str=batch.date_str,
        output_dir=batch.output_dir,
        stacks=[stack],
        screenshots=[
            screenshot for screenshot in batch.screenshots
            if screenshot.matched_invoice_id in invoice_ids
        ],
        batch_version=batch.batch_version,
        stack_dir=stack_dir,
        active_stack_index=stack.index,
    )
    with open(_state_path_for_stack(stack_dir), "w", encoding="utf-8") as f:
        json.dump(stack_batch.to_dict(), f, ensure_ascii=False, indent=2)


def save_batch(batch: Batch) -> None:
    for stack in batch.stacks:
        _write_stack_state(batch, stack)


def load_batch(path: Path) -> Batch:
    stack_dir = path if path.is_dir() else path.parent
    json_path = path if path.is_file() else _state_path_for_stack(stack_dir)
    if not json_path.is_file():
        raise FileNotFoundError("未找到该叠目录内的 invoices.json。")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    batch = Batch.from_dict(data)
    batch.stack_dir = stack_dir
    batch.output_dir = stack_dir.parent
    for invoice in batch.all_invoices():
        if invoice.output_path and invoice.output_path.is_file():
            invoice.source_path = invoice.output_path
            invoice.is_existing = True
    for screenshot in batch.screenshots:
        if screenshot.output_path and screenshot.output_path.is_file():
            screenshot.source_path = screenshot.output_path
    return batch


def discover_state_files(parent_dir: Path) -> list[Path]:
    if not parent_dir.is_dir():
        raise FileNotFoundError("未找到可扫描的目录。")
    return sorted(path for path in parent_dir.rglob(STATE_FILE) if path.is_file())


def load_date_groups_from_parent(parent_dir: Path) -> tuple[list[DateGroup], list[str]]:
    state_files = discover_state_files(parent_dir)
    grouped: dict[str, DateGroup] = {}
    errors: list[str] = []
    seen_state_files: set[Path] = set()

    for state_file in state_files:
        resolved_state_file = state_file.resolve()
        if resolved_state_file in seen_state_files:
            continue
        seen_state_files.add(resolved_state_file)
        try:
            batch = load_batch(state_file)
        except Exception as exc:
            errors.append(f"{state_file}: {exc}")
            continue

        group = grouped.get(batch.date_str)
        if group is None:
            group = DateGroup(
                date_str=batch.date_str,
                output_dir=batch.output_dir,
                stacks=[],
                screenshots=[],
                source_state_files=[],
                locked=True,
                active_stack_index=batch.active_stack_index,
            )
            grouped[batch.date_str] = group

        existing_invoice_keys = {
            invoice.invoice_id
            for stack in group.stacks
            for invoice in stack.invoices
        }
        screenshot_ids = {screenshot.screenshot_id for screenshot in group.screenshots}
        invoice_id_to_new_stack_index: dict[str, int] = {}

        source_stacks = batch.stacks
        if batch.active_stack_index is not None:
            active_stack = next(
                (stack for stack in batch.stacks if stack.index == batch.active_stack_index),
                None,
            )
            if active_stack is not None:
                source_stacks = [active_stack]

        for stack in source_stacks:
            unique_invoices = [invoice for invoice in stack.invoices if invoice.invoice_id not in existing_invoice_keys]
            if stack.invoices and not unique_invoices:
                continue
            new_index = len(group.stacks) + 1
            stack.index = new_index
            stack.invoices = unique_invoices
            for invoice in stack.invoices:
                invoice.stack_index = new_index
                existing_invoice_keys.add(invoice.invoice_id)
                invoice_id_to_new_stack_index[invoice.invoice_id] = new_index
            group.stacks.append(stack)

        for screenshot in batch.screenshots:
            if screenshot.screenshot_id in screenshot_ids:
                continue
            if screenshot.matched_invoice_id not in invoice_id_to_new_stack_index:
                continue
            if screenshot.matched_invoice_id:
                screenshot.matched_stack_index = invoice_id_to_new_stack_index.get(
                    screenshot.matched_invoice_id,
                    screenshot.matched_stack_index,
                )
            group.screenshots.append(screenshot)
            screenshot_ids.add(screenshot.screenshot_id)

        group.source_state_files.append(state_file)
        if group.output_dir != batch.output_dir:
            group.output_dir = batch.output_dir
        if batch.active_stack_index is not None:
            group.active_stack_index = min(batch.active_stack_index, len(group.stacks)) if group.stacks else None

    return sorted(grouped.values(), key=lambda item: item.date_str), errors


def _copy_source(source_path: Path, output_path: Path | None, destination: Path) -> None:
    source = source_path if source_path.is_file() else output_path
    if source is None or not source.is_file():
        raise FileNotFoundError(f"源文件不存在：{source_path}")
    shutil.copy2(source, destination)


def _prepare_stack(batch: Batch, stack: Stack, reimburser: str) -> tuple[Path, Path, dict]:
    target_dir = batch.output_dir / stack.folder_name(batch.date_str)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{target_dir.name}.tmp-", dir=batch.output_dir))
    invoice_dir = temp_dir / "发票"
    screenshot_dir = temp_dir / "订单截图"
    invoice_dir.mkdir()
    screenshot_dir.mkdir()
    screenshot_by_invoice_id = {
        screenshot.matched_invoice_id: screenshot
        for screenshot in batch.screenshots
        if screenshot.matched_invoice_id
    }
    stack_result = {
        "folder": str(target_dir),
        "date": batch.date_str,
        "stack_index": stack.index,
        "count": stack.count,
        "total": round(stack.total, 2),
        "screenshot_count": 0,
        "invoices": [],
        "screenshots": [],
    }
    try:
        for i, invoice in enumerate(stack.invoices, 1):
            amount_str = f"{invoice.amount:.2f}" if invoice.amount is not None else "未知"
            new_name = f"{i}、{amount_str}.pdf"
            dest = invoice_dir / new_name
            _copy_source(invoice.source_path, invoice.output_path, dest)
            invoice.stack_index = stack.index
            invoice.output_path = target_dir / "发票" / new_name
            invoice.display_name = new_name
            stack_result["invoices"].append({
                "index": i,
                "filename": new_name,
                "amount": invoice.amount,
                "source": str(invoice.source_path),
            })

            screenshot = screenshot_by_invoice_id.get(invoice.invoice_id)
            if screenshot is None:
                continue
            screenshot_name = f"{i}、{amount_str}{screenshot.source_path.suffix.lower()}"
            screenshot_dest = screenshot_dir / screenshot_name
            _copy_source(screenshot.source_path, screenshot.output_path, screenshot_dest)
            screenshot.matched_stack_index = stack.index
            screenshot.output_path = target_dir / "订单截图" / screenshot_name
            screenshot.display_name = screenshot_name
            stack_result["screenshot_count"] += 1
            stack_result["screenshots"].append({
                "index": i,
                "filename": screenshot_name,
                "amount": screenshot.amount,
                "source": str(screenshot.source_path),
            })

        generate_stack_excel(stack, batch.date_str, batch.output_dir, reimburser, stack_dir=temp_dir)
        _write_stack_state(batch, stack, temp_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return temp_dir, target_dir, stack_result


def materialize_selected_stacks(
    batch: Batch,
    stack_indexes: set[int] | None = None,
    reimburser: str = "",
) -> list[dict]:
    batch.output_dir.mkdir(parents=True, exist_ok=True)
    selected = [stack for stack in batch.stacks if stack_indexes is None or stack.index in stack_indexes]
    prepared: list[tuple[Path, Path, dict]] = []
    replaced: list[tuple[Path, Path | None]] = []
    try:
        # Prepare all selected stacks first so moving a file between existing
        # stacks cannot delete the source before the destination is ready.
        for stack in selected:
            prepared.append(_prepare_stack(batch, stack, reimburser))
        for temp_dir, target_dir, _ in prepared:
            backup_dir = None
            if target_dir.exists():
                backup_dir = Path(tempfile.mkdtemp(prefix=f".{target_dir.name}.backup-", dir=batch.output_dir))
                backup_dir.rmdir()
                target_dir.rename(backup_dir)
            try:
                temp_dir.rename(target_dir)
            except Exception:
                if backup_dir is not None and backup_dir.exists():
                    backup_dir.rename(target_dir)
                raise
            replaced.append((target_dir, backup_dir))
        for _, backup_dir in replaced:
            if backup_dir is not None:
                shutil.rmtree(backup_dir, ignore_errors=True)
    except Exception:
        for target_dir, backup_dir in reversed(replaced):
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            if backup_dir is not None and backup_dir.exists():
                backup_dir.rename(target_dir)
        for temp_dir, _, _ in prepared:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    if batch.active_stack_index is not None:
        active = next((s for s in batch.stacks if s.index == batch.active_stack_index), None)
        if active is not None:
            batch.stack_dir = batch.output_dir / active.folder_name(batch.date_str)
    elif batch.stacks:
        batch.stack_dir = batch.output_dir / batch.stacks[0].folder_name(batch.date_str)
    return [result for _, _, result in prepared]


def materialize_batch(batch: Batch, reimburser: str = "") -> list[dict]:
    return materialize_selected_stacks(batch, reimburser=reimburser)


def create_new_batch(stacks: list[Stack], output_dir: Path, date_str: str, screenshots: list[OrderScreenshot] | None = None, reimburser: str = "") -> tuple[Batch, list[dict]]:
    if not stacks:
        raise ValueError("没有可生成的发票叠。")
    batch = Batch(
        date_str=date_str,
        output_dir=output_dir,
        stacks=stacks,
        screenshots=screenshots or [],
        stack_dir=output_dir / stacks[0].folder_name(date_str),
        active_stack_index=1,
    )
    results = materialize_batch(batch, reimburser)
    return batch, results
