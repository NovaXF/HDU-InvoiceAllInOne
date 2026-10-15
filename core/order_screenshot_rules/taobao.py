from core.order_screenshot_rules.common import OCRToken, contains_any, extract_currency_amount, extract_numeric_amount


# 淘宝规则：优先使用“实付款/实付”所在汇总行提取最终成交金额；只有在汇总区缺失时才回退到淘宝页面内的近邻策略，避免抓到商品单价。
PAID_KEYWORDS = ("实付款", "实付")
DISCOUNT_KEYWORDS = ("共减", "立减", "优惠", "红包", "淘金币", "返现", "减", "省", "已抵")
SUMMARY_KEYWORDS = ("商品总价", "店铺优惠", "官方立减", "成交时间", "付款时间", "创建时间", "发货时间")


def matches(tokens: list[OCRToken], full_text: str) -> bool:
    return contains_any(full_text, PAID_KEYWORDS)


def extract_amounts(tokens: list[OCRToken], full_text: str) -> list[float]:
    amounts: list[float] = []
    paid_tokens = [token for token in tokens if contains_any(token.text, PAID_KEYWORDS)]
    for paid_token in paid_tokens:
        amount = _extract_summary_amount(paid_token, tokens)
        if amount is None:
            amount = _extract_row_amount(paid_token, tokens)
        if amount is None:
            amount = _extract_neighbor_amount(paid_token, tokens)
        if amount is not None:
            amounts.append(amount)
    return amounts


def _extract_summary_amount(paid_token: OCRToken, tokens: list[OCRToken]):
    left_bound = paid_token.left - 60
    right_bound = max(paid_token.right + 900, paid_token.left + 700)
    top_bound = paid_token.top - 40
    bottom_bound = paid_token.bottom + 140

    candidates: list[tuple[float, float]] = []
    has_summary_context = any(
        token is not paid_token
        and token.left >= left_bound - 120
        and token.right <= right_bound
        and token.top >= top_bound - 120
        and token.bottom <= bottom_bound + 180
        and contains_any(token.text, SUMMARY_KEYWORDS)
        for token in tokens
    )

    for token in tokens:
        if token is paid_token:
            continue
        if token.left < left_bound or token.right > right_bound:
            continue
        if token.top < top_bound or token.bottom > bottom_bound:
            continue
        amount = extract_currency_amount(token.text)
        if amount is None or amount <= 0:
            continue
        if amount >= 100000:
            continue
        if contains_any(token.text, DISCOUNT_KEYWORDS):
            continue
        score = abs(token.center_y - paid_token.center_y) * 4 + max(0.0, paid_token.right - token.left)
        if has_summary_context:
            score -= 30
        candidates.append((score, amount))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _extract_row_amount(paid_token: OCRToken, tokens: list[OCRToken]):
    candidates: list[tuple[float, float]] = []
    row_tolerance = max(paid_token.height * 0.8, 36.0)
    for token in tokens:
        if token is paid_token:
            continue
        if token.left < paid_token.right - 20:
            continue
        if abs(token.center_y - paid_token.center_y) > row_tolerance:
            continue
        amount = _extract_candidate_amount(token, allow_plain_numeric=True)
        if amount is None:
            continue
        has_currency = extract_currency_amount(token.text) is not None
        score = max(0.0, token.left - paid_token.right)
        if not has_currency:
            score += 120
        candidates.append((score, amount))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _extract_neighbor_amount(paid_token: OCRToken, tokens: list[OCRToken]):
    candidates: list[tuple[float, float]] = []
    vertical_limit = max(paid_token.height * 2.2, 110.0)
    horizontal_limit = 360.0
    for token in tokens:
        if token is paid_token:
            continue
        horizontal_gap = 0.0
        if token.right < paid_token.left:
            horizontal_gap = paid_token.left - token.right
        elif token.left > paid_token.right:
            horizontal_gap = token.left - paid_token.right
        if horizontal_gap > horizontal_limit:
            continue
        vertical_gap = abs(token.center_y - paid_token.center_y)
        if vertical_gap > vertical_limit:
            continue
        amount = _extract_candidate_amount(token, allow_plain_numeric=vertical_gap <= max(paid_token.height * 1.1, 44.0))
        if amount is None:
            continue
        has_currency = extract_currency_amount(token.text) is not None
        score = vertical_gap * 4 + horizontal_gap
        if not has_currency:
            score += 180
        if token.center_y < paid_token.center_y:
            score += 40
        candidates.append((score, amount))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _extract_candidate_amount(token: OCRToken, *, allow_plain_numeric: bool):
    cleaned = token.text
    if contains_any(cleaned, DISCOUNT_KEYWORDS):
        return None

    import re
    from core.order_screenshot_rules.common import to_float

    paid_inline_pattern = re.compile(r"(?:实付款|实付)[^0-9¥￥?]{0,8}[¥￥?]?\s*([0-9]+(?:\.[0-9]{1,2})?)")
    match = paid_inline_pattern.search(cleaned)
    if match is not None:
        return to_float(match.group(1))

    amount = extract_currency_amount(cleaned)
    if amount is not None:
        if amount > 2000:
            return None
        return amount

    if not allow_plain_numeric:
        return None

    amount = extract_numeric_amount(cleaned)
    if amount is None:
        return None
    if amount > 2000:
        return None
    return amount
