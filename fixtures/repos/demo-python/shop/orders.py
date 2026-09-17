def order_status_label(status: str) -> str:
    if status == "new":
        return "New order"
    elif status == "paid":
        return "Paid"
    elif status == "shipped":
        return "Shipped"
    elif status == "cancelled":
        return "Cancelled"
    else:
        return "Unknown"
