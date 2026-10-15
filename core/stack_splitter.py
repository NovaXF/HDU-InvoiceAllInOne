from models.invoice import Invoice, Stack


MAX_COUNT = 25
MAX_AMOUNT = 2500.0


def split_into_stacks(
    invoices: list[Invoice],
    max_count: int = MAX_COUNT,
    max_amount: float = MAX_AMOUNT,
) -> list[Stack]:
    stacks: list[Stack] = []
    current = Stack(index=1)

    for invoice in invoices:
        if invoice.amount is None:
            invoice.stack_index = None
            continue
        would_exceed_count = current.count >= max_count
        would_exceed_amount = current.total + invoice.amount > max_amount + 1e-9
        if current.count > 0 and (would_exceed_count or would_exceed_amount):
            stacks.append(current)
            current = Stack(index=len(stacks) + 1)
        assign_invoice_to_stack(invoice, current)

    if current.invoices:
        stacks.append(current)

    return stacks


def assign_invoice_to_stack(invoice: Invoice, stack: Stack, position: int | None = None) -> None:
    remove_invoice_from_stack(invoice)
    invoice.stack_index = stack.index
    if position is None or position >= len(stack.invoices):
        stack.invoices.append(invoice)
    else:
        stack.invoices.insert(position, invoice)


def remove_invoice_from_stack(invoice: Invoice, stacks: list[Stack] | None = None) -> None:
    if not stacks or invoice.stack_index is None:
        invoice.stack_index = None
        return
    for stack in stacks:
        for existing in list(stack.invoices):
            if existing.invoice_id == invoice.invoice_id:
                stack.invoices.remove(existing)
                invoice.stack_index = None
                return


def move_invoice(invoice_id: str, stacks: list[Stack], target_stack_index: int, position: int | None = None) -> bool:
    invoice = find_invoice(invoice_id, stacks)
    target_stack = find_stack(target_stack_index, stacks)
    if not invoice or not target_stack:
        return False
    remove_invoice_from_stack(invoice, stacks)
    assign_invoice_to_stack(invoice, target_stack, position)
    normalize_stack_indexes(stacks)
    return True


def auto_assign_unassigned(invoices: list[Invoice], stacks: list[Stack]) -> list[Stack]:
    assigned_ids = {invoice.invoice_id for stack in stacks for invoice in stack.invoices}
    unassigned = [invoice for invoice in invoices if invoice.amount is not None and invoice.invoice_id not in assigned_ids]
    if not unassigned:
        normalize_stack_indexes(stacks)
        return stacks

    working = list(stacks)
    if not working:
        working.append(Stack(index=1))

    for invoice in unassigned:
        placed = False
        for stack in working:
            if can_fit(stack, invoice):
                assign_invoice_to_stack(invoice, stack)
                placed = True
                break
        if not placed:
            new_stack = Stack(index=len(working) + 1)
            assign_invoice_to_stack(invoice, new_stack)
            working.append(new_stack)

    normalize_stack_indexes(working)
    return working


def validate_stacks(
    stacks: list[Stack],
    max_count: int = MAX_COUNT,
    max_amount: float = MAX_AMOUNT,
) -> list[dict]:
    issues = []
    for stack in stacks:
        count_exceeded = stack.count > max_count
        amount_exceeded = stack.total > max_amount + 1e-9
        if count_exceeded or amount_exceeded:
            issues.append(
                {
                    "stack_index": stack.index,
                    "count": stack.count,
                    "total": round(stack.total, 2),
                    "count_exceeded": count_exceeded,
                    "amount_exceeded": amount_exceeded,
                }
            )
    return issues


def can_fit(stack: Stack, invoice: Invoice, max_count: int = MAX_COUNT, max_amount: float = MAX_AMOUNT) -> bool:
    if invoice.amount is None:
        return False
    return stack.count < max_count and stack.total + invoice.amount <= max_amount + 1e-9


def normalize_stack_indexes(stacks: list[Stack]) -> None:
    for idx, stack in enumerate(stacks, 1):
        stack.index = idx
        for invoice in stack.invoices:
            invoice.stack_index = idx


def find_stack(stack_index: int, stacks: list[Stack]) -> Stack | None:
    for stack in stacks:
        if stack.index == stack_index:
            return stack
    return None


def find_invoice(invoice_id: str, stacks: list[Stack]) -> Invoice | None:
    for stack in stacks:
        for invoice in stack.invoices:
            if invoice.invoice_id == invoice_id:
                return invoice
    return None
