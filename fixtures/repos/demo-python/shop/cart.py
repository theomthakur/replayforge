from dataclasses import dataclass, field


@dataclass
class LineItem:
    sku: str
    unit_price_cents: int
    quantity: int = 1


@dataclass
class Cart:
    items: list[LineItem] = field(default_factory=list)

    def add(self, item: LineItem) -> None:
        self.items.append(item)

    def total_cents(self) -> int:
        return sum(item.unit_price_cents for item in self.items)
