def receipt_lines(subtotal_cents: int, tax_rate_percent: int) -> list[str]:
    lines = [f"subtotal {subtotal_cents}"]
    lines.append(f"tax {subtotal_cents * tax_rate_percent // 100}")
    lines.append(f"total {subtotal_cents + subtotal_cents * tax_rate_percent // 100}")
    return lines
