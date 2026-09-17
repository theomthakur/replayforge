import pytest

from shop.orders import order_status_label


@pytest.mark.parametrize(
    ("status", "label"),
    [("new", "New order"), ("paid", "Paid"), ("shipped", "Shipped"),
     ("cancelled", "Cancelled"), ("lost", "Unknown")],
)
def test_labels(status, label):
    assert order_status_label(status) == label
