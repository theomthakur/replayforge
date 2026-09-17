from datetime import date


def parse_order_date(value: str) -> date:
    """Parse an ISO order date like 2026-09-17."""
    year, month, day = value.strip().split("-")
    return date(int(year), int(month), int(day))
