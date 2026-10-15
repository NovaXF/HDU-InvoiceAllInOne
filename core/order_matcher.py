from collections import defaultdict

from models.invoice import Invoice, OrderScreenshot


MATCH_EPSILON = 1e-6


def match_screenshots_to_invoices(invoices: list[Invoice], screenshots: list[OrderScreenshot]) -> None:
    _clear_all_matches(invoices, screenshots)

    available_invoices = [invoice for invoice in invoices if invoice.amount is not None]
    available_screenshots = [screenshot for screenshot in screenshots if screenshot.amount is not None and screenshot.error is None]

    invoices_by_amount = _group_invoices_by_amount(available_invoices)
    screenshots_by_amount = _group_screenshots_by_amount(available_screenshots)

    for amount, invoice_group in invoices_by_amount.items():
        screenshot_group = screenshots_by_amount.get(amount)
        if screenshot_group is None:
            continue
        if len(invoice_group) == 1 and len(screenshot_group) == 1:
            bind_screenshot_to_invoice(screenshot_group[0], invoice_group[0])


def bind_screenshot_to_invoice(screenshot: OrderScreenshot, invoice: Invoice) -> None:
    screenshot.matched_invoice_id = invoice.invoice_id
    screenshot.matched_stack_index = invoice.stack_index
    invoice.matched_screenshot_id = screenshot.screenshot_id


def unbind_screenshot(screenshot: OrderScreenshot, invoices: list[Invoice]) -> None:
    if screenshot.matched_invoice_id is None:
        screenshot.matched_stack_index = None
        return
    for invoice in invoices:
        if invoice.invoice_id == screenshot.matched_invoice_id:
            invoice.matched_screenshot_id = None
            break
    screenshot.matched_invoice_id = None
    screenshot.matched_stack_index = None


def sync_screenshot_stack_indexes(invoices: list[Invoice], screenshots: list[OrderScreenshot]) -> None:
    invoice_map = {invoice.invoice_id: invoice for invoice in invoices}
    for screenshot in screenshots:
        if screenshot.matched_invoice_id is None:
            screenshot.matched_stack_index = None
            continue
        invoice = invoice_map.get(screenshot.matched_invoice_id)
        if invoice is None:
            screenshot.matched_invoice_id = None
            screenshot.matched_stack_index = None
            continue
        screenshot.matched_stack_index = invoice.stack_index
        invoice.matched_screenshot_id = screenshot.screenshot_id


def _clear_all_matches(invoices: list[Invoice], screenshots: list[OrderScreenshot]) -> None:
    for invoice in invoices:
        invoice.matched_screenshot_id = None
    for screenshot in screenshots:
        screenshot.matched_invoice_id = None
        screenshot.matched_stack_index = None


def _group_invoices_by_amount(invoices: list[Invoice]) -> dict[float, list[Invoice]]:
    grouped: dict[float, list[Invoice]] = defaultdict(list)
    for invoice in invoices:
        grouped[_normalize_amount(invoice.amount)].append(invoice)
    return dict(grouped)


def _group_screenshots_by_amount(screenshots: list[OrderScreenshot]) -> dict[float, list[OrderScreenshot]]:
    grouped: dict[float, list[OrderScreenshot]] = defaultdict(list)
    for screenshot in screenshots:
        grouped[_normalize_amount(screenshot.amount)].append(screenshot)
    return dict(grouped)


def _normalize_amount(amount: float | None) -> float:
    if amount is None:
        raise ValueError("amount cannot be None")
    return round(amount + MATCH_EPSILON, 2)
