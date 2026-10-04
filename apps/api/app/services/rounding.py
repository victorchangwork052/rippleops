"""Presentation rounding. Calculations stay unrounded until the output edge."""

from decimal import ROUND_HALF_UP, Decimal


def _half_up(x: float, places: str) -> float:
    # Round to 9 places first so binary noise (4.72499999...) cannot flip a half-up.
    return float(Decimal(repr(round(x, 9))).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def money(x: float) -> float:
    return _half_up(x, "0.01")


def ratio(x: float) -> float:
    """Fractions such as margins, kept to 0.01 percentage point."""
    return _half_up(x, "0.0001")


def points(x: float) -> float:
    return _half_up(x, "0.01")


def qty(x: float) -> float:
    return _half_up(x, "0.01")


def days(x: float) -> float:
    return _half_up(x, "0.1")
