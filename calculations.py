"""Pure portfolio valuation helpers. Values returned here are Iranian rials."""


def fund_value_irr(quantity: float, unit_price_irr: float) -> float:
    if quantity < 0 or unit_price_irr < 0:
        raise ValueError("quantity and price must be non-negative")
    return float(quantity) * float(unit_price_irr)


def crypto_value_irr(quantity: float, unit_price_usd: float, usd_rate_irr: float) -> float:
    if quantity < 0 or unit_price_usd < 0 or usd_rate_irr < 0:
        raise ValueError("quantity and prices must be non-negative")
    return float(quantity) * float(unit_price_usd) * float(usd_rate_irr)


def usd_value_irr(usd_amount: float, usd_rate_irr: float) -> float:
    if usd_amount < 0 or usd_rate_irr < 0:
        raise ValueError("amount and rate must be non-negative")
    return float(usd_amount) * float(usd_rate_irr)
