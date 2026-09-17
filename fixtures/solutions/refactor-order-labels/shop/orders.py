STATUS_LABELS = {
    "new": "New order",
    "paid": "Paid",
    "shipped": "Shipped",
    "cancelled": "Cancelled",
}


def order_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "Unknown")
