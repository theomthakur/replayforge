from shop.loyalty import points_for


def test_points_for_member_order(member_subtotal):
    assert points_for(member_subtotal) == 25
