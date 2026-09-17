class OutOfStock(Exception):
    pass


class Inventory:
    def __init__(self) -> None:
        self._stock: dict[str, int] = {}

    def restock(self, sku: str, quantity: int) -> None:
        self._stock[sku] = self._stock.get(sku, 0) + quantity

    def reserve(self, sku: str, quantity: int) -> None:
        available = self._stock.get(sku, 0)
        if quantity > available:
            raise OutOfStock(sku)
        self._stock[sku] = available - quantity

    def available(self, sku: str) -> int:
        return self._stock.get(sku, 0)
