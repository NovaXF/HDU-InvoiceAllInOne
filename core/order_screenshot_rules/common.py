import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


AMOUNT_PATTERN = re.compile(r"(?:[¥￥]|Y|y)?\s*([0-9]+(?:\.[0-9]{1,2})?)")
CURRENCY_SYMBOLS = ("¥", "￥", "?")
_OCR_ENGINE = None


@dataclass
class OCRToken:
    text: str
    left: float
    right: float
    top: float
    bottom: float

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


# 通用 OCR / 文本工具：平台规则只关心“如何识别自己的金额”，不重复处理底层 OCR。
def extract_ocr_tokens(image_path: Path) -> list[OCRToken]:
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError:
        raise RuntimeError("请先安装 Pillow：pip install Pillow")

    engine = _get_ocr_engine()
    with Image.open(image_path) as image:
        processed = ImageOps.grayscale(image)
        processed = ImageEnhance.Contrast(processed).enhance(1.8)
        processed = processed.resize((processed.width * 2, processed.height * 2))
        result, _ = engine(processed)

    tokens: list[OCRToken] = []
    for item in result or []:
        if len(item) < 2 or not item[1]:
            continue
        box = item[0]
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        tokens.append(
            OCRToken(
                text=normalize_text(item[1]).strip(),
                left=min(xs),
                right=max(xs),
                top=min(ys),
                bottom=max(ys),
            )
        )
    return tokens


def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            raise RuntimeError("请先安装 rapidocr-onnxruntime：pip install rapidocr-onnxruntime")
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def normalize_text(text: str) -> str:
    normalized = text.replace("\r", "\n")
    normalized = normalized.replace("Y", "¥").replace("y", "¥")
    normalized = normalized.replace("羊", "¥")
    normalized = normalized.replace("?", "￥")
    normalized = normalized.replace("O", "0").replace("o", "0")
    normalized = normalized.replace("~", "")
    return normalized


def to_float(value: str) -> Optional[float]:
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def extract_numeric_amount(text: str) -> Optional[float]:
    cleaned = normalize_text(text)
    numeric_matches = re.findall(r"([0-9]+(?:\.[0-9]{1,2})?)", cleaned)
    if not numeric_matches:
        return None
    return to_float(numeric_matches[-1])


def extract_currency_amount(text: str) -> Optional[float]:
    cleaned = normalize_text(text)
    matches = [match.group(1) for match in AMOUNT_PATTERN.finditer(cleaned)]
    if not matches:
        return None
    return to_float(matches[-1])


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def tokens_near_label(tokens: list[OCRToken], label_keywords: tuple[str, ...], *, y_tolerance: float = 80.0) -> list[tuple[OCRToken, OCRToken]]:
    pairs: list[tuple[OCRToken, OCRToken]] = []
    labels = [token for token in tokens if contains_any(token.text, label_keywords)]
    for label in labels:
        candidates: list[tuple[float, OCRToken]] = []
        for token in tokens:
            if token is label:
                continue
            amount = extract_currency_amount(token.text) or extract_numeric_amount(token.text)
            if amount is None:
                continue
            if abs(token.center_y - label.center_y) > y_tolerance:
                continue
            if token.left < label.left - 100:
                continue
            score = abs(token.center_y - label.center_y) * 3 + max(0.0, token.left - label.right)
            candidates.append((score, token))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            pairs.append((label, candidates[0][1]))
    return pairs
