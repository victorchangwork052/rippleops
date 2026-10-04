"""Demand-horizon helpers shared by the impact and scenario engines."""

from __future__ import annotations

import calendar
from datetime import date

from app.services.index import DataIndex


def horizon_months(as_of: date, months: int) -> list[date]:
    """First day of each month in the horizon, starting with the as-of month."""
    out = []
    y, m = as_of.year, as_of.month
    for _ in range(months):
        out.append(date(y, m, 1))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def horizon_days(months: list[date]) -> int:
    return sum(calendar.monthrange(d.year, d.month)[1] for d in months)


def forecast_qty(index: DataIndex, product_id: str, months: list[date]) -> float:
    wanted = set(months)
    return sum(d.forecast_qty for d in index.demand.get(product_id, []) if d.forecast_month in wanted)


def open_order_qty(index: DataIndex, product_id: str, months: list[date]) -> float:
    wanted = set(months)
    return sum(d.open_order_qty for d in index.demand.get(product_id, []) if d.forecast_month in wanted)
