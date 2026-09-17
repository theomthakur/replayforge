def tax_cents(subtotal_cents: int, tax_rate_percent: int) -> int:
    return subtotal_cents * tax_rate_percent // 100


def receipt_lines(subtotal_cents: int, tax_rate_percent: int) -> list[str]:
    tax = tax_cents(subtotal_cents, tax_rate_percent)
    return [f"subtotal {subtotal_cents}", f"tax {tax}", f"total {subtotal_cents + tax}"]
