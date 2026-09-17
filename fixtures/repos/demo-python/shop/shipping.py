FREE_SHIPPING_THRESHOLD_CENTS = 5000


def shipping_cost_cents(subtotal_cents: int) -> int:
    return 0 if subtotal_cents >= FREE_SHIPPING_THRESHOLD_CENTS else 599
