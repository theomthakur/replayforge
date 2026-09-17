from shop.receipt import receipt_lines


def test_receipt_lines():
    assert receipt_lines(1000, 8) == ["subtotal 1000", "tax 80", "total 1080"]


def test_receipt_rounds_tax_down():
    assert receipt_lines(999, 8) == ["subtotal 999", "tax 79", "total 1078"]
