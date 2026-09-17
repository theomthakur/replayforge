import pytest

from shop.pricing import apply_discount


def test_ten_percent():
    assert apply_discount(2000, 10) == 1800


def test_rounds_down():
    assert apply_discount(999, 15) == 849


def test_rejects_invalid_percent():
    with pytest.raises(ValueError):
        apply_discount(100, 120)
