from core.order_screenshot_rules.common import OCRToken, contains_any, extract_currency_amount, extract_numeric_amount, tokens_near_label


# 铨洲智造规则：顶部“订单信息”区域通常直接给出“实付金额/微信支付金额”；要避开订单总额、优惠金额、运费和商品表格里的数值。
PLATFORM_KEYWORDS = ("订单信息", "订单模型信息", "微信支付", "开票号")
PRIMARY_LABELS = ("实付金额",)
SECONDARY_LABELS = ("微信支付金额",)
EXCLUDED_LABELS = ("订单总额", "优惠金额", "运费", "总价", "单价", "其他金额")


def matches(tokens: list[OCRToken], full_text: str) -> bool:
    hits = sum(1 for keyword in PLATFORM_KEYWORDS if keyword in full_text)
    return hits >= 2


def extract_amounts(tokens: list[OCRToken], full_text: str) -> list[float]:
    amounts = _extract_from_labels(tokens, PRIMARY_LABELS)
    if amounts:
        return amounts
    amounts = _extract_from_labels(tokens, SECONDARY_LABELS)
    if amounts:
        return amounts
    return []


def _extract_from_labels(tokens: list[OCRToken], labels: tuple[str, ...]) -> list[float]:
    label_hits = [token for token in tokens if contains_any(token.text, labels)]
    results: list[float] = []
    for label_token in label_hits:
        row_amounts = [
            token
            for token in tokens
            if token is not label_token
            and token.top >= label_token.top - 35
            and token.bottom <= label_token.bottom + 35
            and token.left > label_token.right - 20
            and token.left < label_token.left + 1500
        ]
        row_amounts.sort(key=lambda token: token.left)
        for amount_token in row_amounts:
            if contains_any(amount_token.text, EXCLUDED_LABELS):
                continue
            amount = extract_currency_amount(amount_token.text) or extract_numeric_amount(amount_token.text)
            if amount is None or amount <= 0:
                continue
            if amount >= 100000:
                continue
            results.append(amount)
            return results[:1]
    return results[:1]
