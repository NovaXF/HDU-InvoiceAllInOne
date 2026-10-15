from core.order_screenshot_rules.common import OCRToken, contains_any, extract_currency_amount


# 立创下单助手 PCB 规则：长截图中会出现多个订单卡片，每个卡片通常有“在线支付价”锚点；需要逐卡片提取并返回多个金额。
PLATFORM_KEYWORDS = ("二维码编辑", "查看生产稿", "在线支付价", "样板", "下载工程文件")
PRICE_LABELS = ("在线支付价",)


def matches(tokens: list[OCRToken], full_text: str) -> bool:
    hits = sum(1 for keyword in PLATFORM_KEYWORDS if keyword in full_text)
    return hits >= 2


def extract_amounts(tokens: list[OCRToken], full_text: str) -> list[float]:
    anchors = [token for token in tokens if contains_any(token.text, PRICE_LABELS)]
    if not anchors:
        return []

    amounts: list[float] = []
    for anchor in anchors:
        candidate = _find_card_price(anchor, tokens)
        if candidate is None:
            continue
        amounts.append(candidate)
    return amounts


def _find_card_price(anchor: OCRToken, tokens: list[OCRToken]):
    candidates: list[tuple[float, float]] = []
    for token in tokens:
        if token is anchor:
            continue
        amount = extract_currency_amount(token.text)
        if amount is None:
            continue
        if amount <= 0 or amount >= 1000:
            continue
        if token.center_y >= anchor.center_y:
            continue
        vertical_gap = anchor.center_y - token.center_y
        if vertical_gap > 120:
            continue
        horizontal_overlap = min(token.right, anchor.right) - max(token.left, anchor.left)
        if horizontal_overlap < 40 and abs(token.center_x - anchor.center_x) > 180:
            continue
        score = vertical_gap * 4 + abs(token.center_x - anchor.center_x)
        candidates.append((score, amount))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]
