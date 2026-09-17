from shop.receipt import receipt_lines


def test_zero_subtotal():
    assert receipt_lines(0, 8) == ["subtotal 0", "tax 0", "total 0"]


def test_zero_tax_rate():
    assert receipt_lines(1000, 0) == ["subtotal 1000", "tax 0", "total 1000"]


def test_large_subtotal():
    assert receipt_lines(100000, 10) == ["subtotal 100000", "tax 10000", "total 110000"]
