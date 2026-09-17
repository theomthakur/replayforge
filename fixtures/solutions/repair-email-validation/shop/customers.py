def is_valid_email(address: str) -> bool:
    """Accept addresses with exactly one @, a non-empty local part and a dotted domain."""
    if address.count("@") != 1:
        return False
    local, domain = address.split("@")
    labels = domain.split(".")
    return bool(local) and len(labels) >= 2 and all(labels)
