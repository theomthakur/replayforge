from shop.formatting import format_money


def test_whole_dollars():
    assert format_money(1200) == "USD 12.00"


def test_under_one_dollar():
    assert format_money(5) == "USD 0.05"


def test_other_currency():
    assert format_money(1234, "EUR") == "EUR 12.34"
