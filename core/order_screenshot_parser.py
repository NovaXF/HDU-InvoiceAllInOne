from core.order_screenshot_rules.common import OCRToken
from core.order_screenshot_rules.lcsc_pcb import extract_amounts as extract_lcsc_pcb_amounts
from core.order_screenshot_rules.lcsc_pcb import matches as matches_lcsc_pcb
from core.order_screenshot_rules.quanzhou import extract_amounts as extract_quanzhou_amounts
from core.order_screenshot_rules.quanzhou import matches as matches_quanzhou
from core.order_screenshot_rules.taobao import extract_amounts as extract_taobao_amounts
from core.order_screenshot_rules.taobao import matches as matches_taobao


def extract_paid_amount(image_path):
    platform, amounts = extract_paid_amount_details(image_path)
    if not amounts:
        raise ValueError("未能从订单截图中识别金额")
    return round(sum(amounts), 2)


def extract_paid_amount_details(image_path):
    tokens = extract_ocr_tokens(image_path)
    full_text = "\n".join(token.text for token in tokens)

    rules = [
        ("lcsc_pcb", matches_lcsc_pcb, extract_lcsc_pcb_amounts),
        ("quanzhou", matches_quanzhou, extract_quanzhou_amounts),
        ("taobao", matches_taobao, extract_taobao_amounts),
    ]

    for platform, matcher, extractor in rules:
        if not matcher(tokens, full_text):
            continue
        amounts = extractor(tokens, full_text)
        if amounts:
            return platform, amounts

    return None, []


def extract_paid_amounts(text):
    token = OCRToken(text=text, left=0, right=0, top=0, bottom=0)
    _, amounts = extract_paid_amounts_from_tokens([token])
    return amounts


def extract_text(image_path):
    tokens = extract_ocr_tokens(image_path)
    return "\n".join(token.text for token in tokens)


def extract_ocr_tokens(image_path):
    from core.order_screenshot_rules.common import extract_ocr_tokens as _extract_ocr_tokens

    return _extract_ocr_tokens(image_path)


def extract_paid_amounts_from_tokens(tokens):
    full_text = "\n".join(token.text for token in tokens)
    rules = [
        ("lcsc_pcb", matches_lcsc_pcb, extract_lcsc_pcb_amounts),
        ("quanzhou", matches_quanzhou, extract_quanzhou_amounts),
        ("taobao", matches_taobao, extract_taobao_amounts),
    ]
    for platform, matcher, extractor in rules:
        if matcher(tokens, full_text):
            amounts = extractor(tokens, full_text)
            if amounts:
                return platform, amounts
    return None, []
