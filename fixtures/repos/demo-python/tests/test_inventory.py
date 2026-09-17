import pytest

from shop.inventory import Inventory, OutOfStock


def test_reserve_within_stock():
    inventory = Inventory()
    inventory.restock("mug", 3)
    inventory.reserve("mug", 3)
    assert inventory.available("mug") == 0


def test_cannot_reserve_more_than_available():
    inventory = Inventory()
    inventory.restock("mug", 3)
    with pytest.raises(OutOfStock):
        inventory.reserve("mug", 4)
    assert inventory.available("mug") == 3
