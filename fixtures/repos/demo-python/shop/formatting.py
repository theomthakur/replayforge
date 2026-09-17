def format_money(cents: int, currency: str = "USD") -> str:
    """Format an amount in cents for display, e.g. 1234 -> 'USD 12.34'."""
    return f"{currency} {cents // 100}.{cents % 100:02d}"
