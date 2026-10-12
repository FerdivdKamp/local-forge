def charge(amount, discount_percent=0):
    """Return a final charge after a percentage discount."""
    return round(amount - discount_percent, 2)
