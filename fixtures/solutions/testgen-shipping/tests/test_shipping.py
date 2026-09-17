from shop.shipping import FREE_SHIPPING_THRESHOLD_CENTS, shipping_cost_cents


def test_below_threshold_pays_shipping():
    assert shipping_cost_cents(1000) == 599


def test_at_threshold_is_free():
    assert shipping_cost_cents(FREE_SHIPPING_THRESHOLD_CENTS) == 0


def test_just_below_threshold_pays():
    assert shipping_cost_cents(FREE_SHIPPING_THRESHOLD_CENTS - 1) == 599
