"""Operations data for sourcing and production planning.

Generated after the core dataset with its own fixed-seed RNG, so adding these
tables never changes the calibrated BOM, cost, demand or inventory values.
Anchor facts:

* Five production lines: one dedicated line per product family plus a
  Monterrey flex line that can build Edge, Gateway and Vision products at a
  slower rate.
* The Edge Control line (LINE-A) is loaded slightly above capacity, so the
  current schedule already has late units; the flex line has spare hours.
* 13 weeks of work orders mirror the monthly demand plan. The first four
  weeks are released; P300, P500, P420 and P210 carry strategic customers.
* 24 months of shipment history. P300 grows faster than the plan assumes, so
  a statistical forecast runs ahead of the demand plan for it.
"""

from __future__ import annotations

import calendar
import math
import random
from collections import defaultdict
from datetime import date, timedelta

from app.db.schema import (
    DemandHistory,
    ProductionLine,
    ProductRouting,
    Snapshot,
    SupplierPerformance,
    WorkOrder,
)

OPS_SEED = 20261019
PLAN_START = date(2026, 10, 5)  # first Monday after the demo as-of date
PLAN_WEEKS = 13
HISTORY_MONTHS = 24

FAMILY_LINE = {
    "Edge Control": "LINE-A",
    "Industrial Gateway": "LINE-B",
    "Vision System": "LINE-C",
    "Smart I/O": "LINE-D",
}
FLEX_LINE = "LINE-F"
FLEX_FAMILIES = {"Edge Control", "Industrial Gateway", "Vision System"}
FLEX_SLOWDOWN = 1.25  # flex line needs 25% more hours per unit

# (line, name, site, capacity factor vs. average primary load)
LINES = [
    ("LINE-A", "Edge Control Line A", "Austin, TX", 0.93),
    ("LINE-B", "Gateway Line B", "Austin, TX", 1.04),
    ("LINE-C", "Vision Line C", "Austin, TX", 1.15),
    ("LINE-D", "Smart I/O Line D", "Austin, TX", 1.20),
]
FLEX_CAPACITY_HOURS = 220.0

STRATEGIC = {"P300", "P500", "P420", "P210"}
FAST_GROWTH = {"P300": 0.22, "P500": 0.10}

QUARTERS = [date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30)]
# Supplier KPI profiles per quarter: (on-time rate, ppm, lead time days, variance days).
PERFORMANCE = {
    "SUP-NOVA": [(0.91, 150, 68, 6), (0.88, 165, 70, 8), (0.84, 190, 76, 11), (0.80, 210, 84, 14)],
    "SUP-CRES": [(0.95, 95, 98, 6), (0.96, 90, 98, 5), (0.95, 85, 97, 5), (0.96, 80, 98, 5)],
    "SUP-ATLAS": [(0.93, 140, 50, 5), (0.94, 130, 49, 5), (0.92, 150, 52, 6), (0.93, 135, 49, 5)],
}

SEASONALITY_BY_MONTH = {10: 1.00, 11: 1.04, 12: 0.96, 1: 0.92, 2: 1.02, 3: 1.06,
                        4: 1.03, 5: 0.98, 6: 1.01, 7: 1.05, 8: 0.97, 9: 1.00}


def plan_weeks() -> list[date]:
    return [PLAN_START + timedelta(weeks=i) for i in range(PLAN_WEEKS)]


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def weekly_qty(monthly: float, week: date) -> float:
    days = calendar.monthrange(week.year, week.month)[1]
    return float(max(1, round(monthly * 7 / days)))


def add_operations_data(snap: Snapshot) -> None:
    rng = random.Random(OPS_SEED)
    fgs = [i for i in snap.item_master if i.item_type == "FINISHED_GOOD"]
    price = {p.product_id: p.selling_price for p in snap.product_price}
    monthly = {(d.product_id, d.forecast_month): d.forecast_qty for d in snap.product_demand}
    weeks = plan_weeks()

    # Supplier performance.
    perf: list[SupplierPerformance] = []
    for sup in snap.suppliers:
        profile = PERFORMANCE.get(sup.supplier_id)
        for qi, q in enumerate(QUARTERS):
            if profile:
                otd, ppm, lead, var = profile[qi]
            else:
                otd = round(rng.uniform(0.88, 0.97), 3)
                ppm = float(rng.randrange(60, 420, 5))
                lead = float(rng.randrange(28, 70))
                var = float(rng.randrange(3, 10))
            perf.append(SupplierPerformance(sup.supplier_id, q, float(otd), float(ppm), float(lead), float(var)))
    snap.supplier_performance = perf

    # Routings: hours per unit scale with product complexity (price).
    routings: list[ProductRouting] = []
    hours: dict[str, float] = {}
    for fg in fgs:
        h = round(0.30 + price[fg.item_id] / 650 + rng.uniform(0.0, 0.08), 2)
        hours[fg.item_id] = h
        routings.append(ProductRouting(fg.item_id, FAMILY_LINE[fg.product_family or ""], "PRIMARY", h))
        if fg.product_family in FLEX_FAMILIES:
            routings.append(ProductRouting(fg.item_id, FLEX_LINE, "ALTERNATE", round(h * FLEX_SLOWDOWN, 2)))
    snap.product_routings = routings

    # Work orders mirror the monthly plan, split into weeks.
    orders: list[WorkOrder] = []
    load: dict[str, list[float]] = defaultdict(lambda: [0.0] * PLAN_WEEKS)
    for fg in fgs:
        line = FAMILY_LINE[fg.product_family or ""]
        strategic = fg.item_id in STRATEGIC
        for wi, wk in enumerate(weeks):
            qty = weekly_qty(monthly.get((fg.item_id, _month_start(wk)), 0.0), wk)
            orders.append(WorkOrder(
                f"WO-{wk:%y%m%d}-{fg.item_id}", fg.item_id, line, wk, qty,
                "RELEASED" if wi < 4 else "PLANNED", "STRATEGIC" if strategic else "STANDARD"))
            load[line][wi] += qty * hours[fg.item_id]
    snap.work_orders = orders

    lines = []
    for line_id, name, site, factor in LINES:
        avg = sum(load[line_id]) / PLAN_WEEKS
        lines.append(ProductionLine(line_id, name, site, float(math.ceil(avg * factor / 10) * 10), "ACTIVE"))
    lines.append(ProductionLine(FLEX_LINE, "Flex Line F", "Monterrey, MX", FLEX_CAPACITY_HOURS, "ACTIVE"))
    snap.production_lines = lines

    # Shipment history: 24 months ending the month before the plan starts,
    # scaled back from the plan's first month with a per-product growth rate.
    first_plan_month = _month_start(weeks[0])
    history: list[DemandHistory] = []
    for fg in fgs:
        base = monthly.get((fg.item_id, first_plan_month), 0.0) / SEASONALITY_BY_MONTH[first_plan_month.month]
        growth = FAST_GROWTH.get(fg.item_id, rng.uniform(0.02, 0.08))
        for k in range(HISTORY_MONTHS, 0, -1):
            month = _add_months(first_plan_month, -k)
            trend = (1 + growth) ** (-k / 12)
            noise = rng.uniform(0.95, 1.05)
            history.append(DemandHistory(fg.item_id, month,
                                         float(round(base * trend * SEASONALITY_BY_MONTH[month.month] * noise))))
    snap.demand_history = history
