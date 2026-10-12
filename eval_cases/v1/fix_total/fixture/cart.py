def total(items, discount_percent=0):
    """Return the discounted sum of (unit_price, quantity) pairs."""
    subtotal = sum(price for price, quantity in items)
    return round(subtotal * (1 - discount_percent / 100), 2)
