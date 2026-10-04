"""Demand forecast, material requirements and the OR-Tools production plan."""

import pytest

from app.integrations.providers import get_integrations
from app.seed.generator import generate
from app.services.forecast import forecast_demand
from app.services.planning import PlanningInputError, material_plan, optimize_production

AFFECTED = ["P100", "P110", "P120", "P200", "P210", "P220", "P230", "P300", "P410", "P420", "P430", "P500"]


def test_operations_tables_are_seeded():
    snap = generate()
    assert len(snap.production_lines) == 5
    assert len(snap.work_orders) == 50 * 13
    assert len(snap.demand_history) == 50 * 24
    assert {p.supplier_id for p in snap.supplier_performance} == {s.supplier_id for s in snap.suppliers}


def test_local_forecast_is_deterministic_and_flags_p300(seed_repo):
    f1 = forecast_demand(seed_repo, AFFECTED)
    f2 = forecast_demand(seed_repo, AFFECTED)
    assert f1 == f2 and f1.method == "seasonal_trend"
    top = max(f1.products, key=lambda p: p.delta_pct)
    assert top.product_id == "P300" and top.delta_pct > 0.05
    for p in f1.products:
        assert all(pt.lower <= pt.forecast_qty <= pt.upper for pt in p.points)


def test_material_plan_finds_the_stockout_week(seed_repo):
    m = material_plan(seed_repo, "MCU-X100")
    assert m.available_qty == seed_repo.index().available_qty["MCU-X100"]
    assert m.total_requirement > m.available_qty
    assert m.stockout_week == "2026-11-30"


@pytest.fixture(scope="module")
def plans(seed_repo):
    ig = get_integrations()
    return {q: optimize_production(seed_repo, ig, "MCU-X100", "MCU-X200", q) for q in (0, 500)}


def test_optimizer_beats_the_current_schedule(plans):
    p = plans[0]
    assert p.solver.status == "OPTIMAL"
    assert p.optimized.affected_fill_rate > p.baseline.affected_fill_rate
    assert p.optimized.gross_margin > p.baseline.gross_margin
    assert p.optimized.late_unit_weeks < p.baseline.late_unit_weeks


def test_plan_respects_supply_capacity_and_approvals(plans):
    p = plans[0]
    assert p.optimized.component_used <= p.inputs.component_on_hand
    for load in p.line_loads:
        assert load.planned_hours <= load.capacity_hours + 1e-6
    rows = {r.product_id: r for r in p.products}
    # P300 needs MCU-X200 validation (45 days), so it may only switch from week 7.
    assert rows["P300"].alternative_from_week == "2026-11-23"
    alt_weeks = {c.week for c in p.schedule if c.product_id == "P300" and c.alternative_qty > 0}
    assert all(w >= "2026-11-23" for w in alt_weeks)
    assert sum(r.built for r in p.products) == p.optimized.built_units


def test_small_bridge_buy_closes_the_gap_and_pays_back(plans):
    base, bridged = plans[0], plans[500]
    assert base.optimized.unmet_units > 0
    assert bridged.optimized.affected_fill_rate > base.optimized.affected_fill_rate
    assert bridged.optimized.unmet_units < base.optimized.unmet_units
    assert bridged.optimized.bridge_premium == pytest.approx(500 * (24.80 - 15.00))
    assert bridged.optimized.gross_margin > base.optimized.gross_margin
    assert any(c.kind == "BRIDGE_BUY" for c in bridged.changes)


def test_plan_is_deterministic(seed_repo, plans):
    again = optimize_production(seed_repo, get_integrations(), "MCU-X100", "MCU-X200", 0)
    assert again.schedule == plans[0].schedule


def test_bridge_cannot_exceed_broker_stock(seed_repo):
    with pytest.raises(PlanningInputError):
        optimize_production(seed_repo, get_integrations(), "MCU-X100", "MCU-X200", 50_000)
