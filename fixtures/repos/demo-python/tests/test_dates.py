from datetime import date

from shop.dates import parse_order_date


def test_parses_iso_date():
    assert parse_order_date("2026-09-17") == date(2026, 9, 17)


def test_strips_whitespace():
    assert parse_order_date(" 2026-01-31 ") == date(2026, 1, 31)
