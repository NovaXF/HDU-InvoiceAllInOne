from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import uuid4
import unicodedata


@dataclass
class Invoice:
    source_path: Path
    amount: Optional[float] = None
    error: Optional[str] = None
    invoice_id: str = field(default_factory=lambda: str(uuid4()))
    display_name: str = ""
    stack_index: Optional[int] = None
    output_path: Optional[Path] = None
    is_existing: bool = False
    matched_screenshot_id: Optional[str] = None
    invoice_code: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    item_names: Optional[list[str]] = None
    remark: str = ""

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.source_path.name

    @property
    def filename(self) -> str:
        return self.display_name or self.source_path.name

    @property
    def unique_key(self) -> Optional[str]:
        number = unicodedata.normalize("NFKC", self.invoice_number or "")
        return "".join(number.split()) or None

    def to_dict(self) -> dict:
        return {
            "invoice_id": self.invoice_id,
            "source": str(self.source_path),
            "display_name": self.display_name,
            "amount": self.amount,
            "error": self.error,
            "stack_index": self.stack_index,
            "output_path": str(self.output_path) if self.output_path else None,
            "is_existing": self.is_existing,
            "matched_screenshot_id": self.matched_screenshot_id,
            "invoice_code": self.invoice_code,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "item_names": self.item_names,
            "remark": self.remark,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Invoice":
        output_path = data.get("output_path")
        return cls(
            source_path=Path(data["source"]),
            amount=data.get("amount"),
            error=data.get("error"),
            invoice_id=data.get("invoice_id") or str(uuid4()),
            display_name=data.get("display_name") or Path(data["source"]).name,
            stack_index=data.get("stack_index"),
            output_path=Path(output_path) if output_path else None,
            is_existing=bool(data.get("is_existing")),
            matched_screenshot_id=data.get("matched_screenshot_id"),
            invoice_code=data.get("invoice_code"),
            invoice_number=data.get("invoice_number"),
            invoice_date=data.get("invoice_date"),
            item_names=data.get("item_names"),
            remark=data.get("remark") or "",
        )


@dataclass
class OrderScreenshot:
    source_path: Path
    amount: Optional[float] = None
    error: Optional[str] = None
    screenshot_id: str = field(default_factory=lambda: str(uuid4()))
    matched_invoice_id: Optional[str] = None
    matched_stack_index: Optional[int] = None
    display_name: str = ""
    output_path: Optional[Path] = None
    platform: Optional[str] = None

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.source_path.name

    @property
    def filename(self) -> str:
        return self.display_name or self.source_path.name

    def to_dict(self) -> dict:
        return {
            "screenshot_id": self.screenshot_id,
            "source": str(self.source_path),
            "display_name": self.display_name,
            "amount": self.amount,
            "error": self.error,
            "matched_invoice_id": self.matched_invoice_id,
            "matched_stack_index": self.matched_stack_index,
            "output_path": str(self.output_path) if self.output_path else None,
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrderScreenshot":
        output_path = data.get("output_path")
        return cls(
            source_path=Path(data["source"]),
            amount=data.get("amount"),
            error=data.get("error"),
            screenshot_id=data.get("screenshot_id") or str(uuid4()),
            matched_invoice_id=data.get("matched_invoice_id"),
            matched_stack_index=data.get("matched_stack_index"),
            display_name=data.get("display_name") or Path(data["source"]).name,
            output_path=Path(output_path) if output_path else None,
            platform=data.get("platform"),
        )


@dataclass
class Stack:
    index: int
    invoices: list[Invoice] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(inv.amount for inv in self.invoices if inv.amount is not None)

    @property
    def count(self) -> int:
        return len(self.invoices)

    def folder_name(self, date_str: str) -> str:
        return f"{date_str}报销第{self.index}叠"

    def to_dict(self) -> dict:
        return {
            "stack_index": self.index,
            "count": self.count,
            "total": round(self.total, 2),
            "invoices": [inv.to_dict() for inv in self.invoices],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Stack":
        stack = cls(index=data["stack_index"])
        stack.invoices = [Invoice.from_dict(inv) for inv in data.get("invoices", [])]
        for invoice in stack.invoices:
            invoice.stack_index = stack.index
        return stack


@dataclass
class DateGroup:
    date_str: str
    output_dir: Path
    stacks: list[Stack] = field(default_factory=list)
    screenshots: list[OrderScreenshot] = field(default_factory=list)
    source_state_files: list[Path] = field(default_factory=list)
    locked: bool = True
    active_stack_index: Optional[int] = None

    def all_invoices(self) -> list[Invoice]:
        invoices: list[Invoice] = []
        for stack in self.stacks:
            invoices.extend(stack.invoices)
        return invoices


@dataclass
class Batch:
    date_str: str
    output_dir: Path
    stacks: list[Stack] = field(default_factory=list)
    screenshots: list[OrderScreenshot] = field(default_factory=list)
    batch_version: int = 1
    stack_dir: Optional[Path] = None
    active_stack_index: Optional[int] = None

    def all_invoices(self) -> list[Invoice]:
        invoices: list[Invoice] = []
        for stack in self.stacks:
            invoices.extend(stack.invoices)
        return invoices

    def to_dict(self) -> dict:
        return {
            "batch_version": self.batch_version,
            "date_str": self.date_str,
            "output_dir": str(self.output_dir),
            "stack_dir": str(self.stack_dir) if self.stack_dir else None,
            "active_stack_index": self.active_stack_index,
            "stacks": [stack.to_dict() for stack in self.stacks],
            "screenshots": [screenshot.to_dict() for screenshot in self.screenshots],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Batch":
        stack_dir = data.get("stack_dir")
        batch = cls(
            date_str=data["date_str"],
            output_dir=Path(data["output_dir"]),
            batch_version=data.get("batch_version", 1),
            stack_dir=Path(stack_dir) if stack_dir else None,
            active_stack_index=data.get("active_stack_index"),
            screenshots=[OrderScreenshot.from_dict(item) for item in data.get("screenshots", [])],
        )
        batch.stacks = [Stack.from_dict(stack) for stack in data.get("stacks", [])]
        return batch
