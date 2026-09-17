from shop.customers import is_valid_email


def test_accepts_normal_address():
    assert is_valid_email("ana@example.com")


def test_rejects_domain_without_dot():
    assert not is_valid_email("ana@localhost")


def test_rejects_empty_local_part():
    assert not is_valid_email("@example.com")


def test_rejects_trailing_dot_domain():
    assert not is_valid_email("ana@example.")
