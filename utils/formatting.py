"""Amount formatting and parsing utilities."""


def format_amount(amount_wei: int, decimals: int) -> str:
    """Format wei amount to human-readable string."""
    amount = amount_wei / (10 ** decimals)
    if amount == 0:
        return "0"
    if amount < 0.000001:
        return f"{amount:.10f}"
    if amount < 1:
        return f"{amount:.6f}"
    return f"{amount:.4f}"


def parse_amount(amount_str: str, decimals: int) -> int:
    """Parse human-readable amount to wei."""
    amount = float(amount_str)
    return int(amount * (10 ** decimals))


def format_price(price: float) -> str:
    """Format price for display."""
    if price < 0.000001:
        return f"{price:.10f}"
    if price < 1:
        return f"{price:.6f}"
    if price < 1000:
        return f"{price:.4f}"
    return f"{price:,.2f}"


def format_gas(gas_wei: int) -> str:
    """Format gas in Gwei."""
    return f"{gas_wei / 1e9:.2f} Gwei"
