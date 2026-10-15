import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class InvoiceParseResult:
    amount: Optional[float]
    invoice_code: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    item_names: Optional[list[str]] = None


def extract_amount(pdf_path: Path) -> Optional[float]:
    return extract_invoice_data(pdf_path).amount


def extract_invoice_data(pdf_path: Path) -> InvoiceParseResult:
    """从电子发票 PDF 中提取金额、发票代码、发票号码、开票日期和项目名称。"""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("请先安装 pdfplumber：pip install pdfplumber")

    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        item_names: list[str] = []
        for page in pdf.pages:
            text += page.extract_text() or ""
            page_items = _parse_item_names_from_page(page)
            item_names.extend(page_items)

    amount = _parse_amount(text)
    return InvoiceParseResult(
        amount=amount,
        invoice_code=_parse_invoice_code(text),
        invoice_number=_parse_invoice_number(text),
        invoice_date=_parse_invoice_date(text),
        item_names=item_names or None,
    )


def _parse_amount(text: str) -> Optional[float]:
    m = re.search(r'[（(]\s*小写\s*[）)]\s*[¥￥]\s*([\d,]+\.?\d*)', text)
    if m:
        return _to_float(m.group(1))

    m = re.search(r'价税合计.{0,60}[¥￥]\s*([\d,]+\.?\d*)', text, re.DOTALL)
    if m:
        return _to_float(m.group(1))

    amounts = re.findall(r'[¥￥]\s*([\d,]+\.?\d*)', text)
    if amounts:
        values = [_to_float(a) for a in amounts if _to_float(a) is not None]
        if values:
            return max(values)

    return None


def _parse_invoice_code(text: str) -> Optional[str]:
    patterns = [
        r'发票代码[:：]?\s*(\d{10,20})',
        r'票据代码[:：]?\s*(\d{10,20})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1)
    return None


def _parse_invoice_number(text: str) -> Optional[str]:
    text = unicodedata.normalize("NFKC", text)
    match = re.search(
        r'(?:发\s*票|票\s*据)\s*号\s*(?:码\s*)?:?\s*'
        r'([0-9](?:[ \t]*[0-9]){5,19})(?![ \t]*[0-9])', text,
    )
    if match:
        return "".join(match.group(1).split())
    return None


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(',', '').strip())
    except ValueError:
        return None


def _parse_invoice_date(text: str) -> Optional[str]:
    """提取开票日期，返回八位数字字符串如 20250115。"""
    m = re.search(r'开票日期[:：]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
    m = re.search(r'开票日期[:：]?\s*(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
    m = re.search(r'开票日期[:：]?\s*(\d{8})', text)
    if m:
        return m.group(1)
    return None


def _parse_item_names_from_page(page) -> list[str]:
    words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
    if not words:
        return []

    header_project = next((w for w in words if w.get("text") == "项目名称"), None)
    header_spec = next((w for w in words if w.get("text") == "规格型号"), None)
    if header_project is None or header_spec is None:
        return []

    he_words = [w for w in words if w.get("text") == "合"]
    ji_words = [w for w in words if w.get("text") == "计"]
    total_top = None
    for he in he_words:
        for ji in ji_words:
            if abs(float(he["top"]) - float(ji["top"])) <= 3 and float(ji["x0"]) > float(he["x1"]):
                total_top = min(float(he["top"]), float(ji["top"]))
                break
        if total_top is not None:
            break
    if total_top is None:
        return []

    left = max(0.0, float(header_project["x0"]) - 40)
    right = float(header_spec["x0"]) - 2
    top = float(max(header_project["bottom"], header_spec["bottom"])) + 2
    bottom = total_top - 2
    if right <= left or bottom <= top:
        return []

    crop = page.crop((left, top, right, bottom))
    text = crop.extract_text(x_tolerance=2, y_tolerance=2) or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines


def _parse_item_names(text: str) -> Optional[list[str]]:
    return None
