def points_for(subtotal_cents: int) -> int:
    """One loyalty point per whole dollar spent."""
    return subtotal_cents // 100
