from shop.cart import Cart, LineItem


def test_total_uses_quantity():
    cart = Cart()
    cart.add(LineItem("mug", 1200, 2))
    cart.add(LineItem("spoon", 300, 3))
    assert cart.total_cents() == 3300


def test_empty_cart():
    assert Cart().total_cents() == 0
