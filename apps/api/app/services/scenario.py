"""Deterministic what-if engine (handoff section 15).

Deltas are attributed in a fixed order - replacement, then raw material, then
freight - by rolling up cumulative parameter sets, so the three driver deltas
always add up to the total unit-cost delta.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.db.repository import Repository
from app.models.scenario import DeltaBreakdown, ScenarioProduct, ScenarioRequest, ScenarioResult, ScenarioSummary
from app.services import rounding as rnd
from app.services.costing import CostEngine, CostParams, gross_margin
from app.services.impact import coverage_context, validate_component
from app.services.index import DataIndex
from app.services.risk import RISK_ORDER, RiskInput, assess

MIN_ADJUSTMENT = -0.9
MAX_ADJUSTMENT = 3.0


class ScenarioInputError(ValueError):
    pass


def validate_request(index: DataIndex, part_id: str, req: ScenarioRequest) -> None:
    if req.replacement_part_id and req.replacement_part_id not in index.alternative_ids(part_id):
        raise ScenarioInputError(f"{req.replacement_part_id} is not a listed alternative for {part_id}.")
    for code, pct in req.commodity_adjustments.items():
        if code not in index.material_price:
            raise ScenarioInputError(f"Unknown raw material '{code}'.")
        if not MIN_ADJUSTMENT <= pct <= MAX_ADJUSTMENT:
            raise ScenarioInputError(f"Adjustment for {code} must be between -90% and +300%.")
    for lane, pct in req.freight_adjustments.items():
        if lane not in index.lane_rate:
            raise ScenarioInputError(f"Unknown shipping lane '{lane}'.")
        if not MIN_ADJUSTMENT <= pct <= MAX_ADJUSTMENT:
            raise ScenarioInputError(f"Adjustment for {lane} must be between -90% and +300%.")


def describe(req: ScenarioRequest, part_id: str) -> str:
    parts = []
    if req.replacement_part_id:
        parts.append(f"{part_id} → {req.replacement_part_id}")
    parts += [f"{code.title()} {pct:+.0%}" for code, pct in req.commodity_adjustments.items() if pct]
    parts += [f"{lane} freight {pct:+.0%}" for lane, pct in req.freight_adjustments.items() if pct]
    return ", ".join(parts) if parts else "Current state"


def run_scenario(repo: Repository, part_id: str, req: ScenarioRequest, horizon: int) -> ScenarioResult:
    index = repo.index()
    validate_component(index, part_id)
    validate_request(index, part_id, req)
    trace = repo.trace(part_id)
    ctx = coverage_context(index, part_id, trace, horizon)

    subs = {part_id: req.replacement_part_id} if req.replacement_part_id else {}
    mats = {k: v for k, v in req.commodity_adjustments.items() if v}
    lanes = {k: v for k, v in req.freight_adjustments.items() if v}
    base = CostEngine(index)
    step1 = CostEngine(index, CostParams(substitutions=subs))
    step2 = CostEngine(index, CostParams(substitutions=subs, material_adjustments=mats))
    final = CostEngine(index, CostParams(substitutions=subs, material_adjustments=mats, freight_adjustments=lanes))

    products: list[ScenarioProduct] = []
    raw_deltas: list[tuple[float, float, float, float]] = []
    raw_costs: list[tuple[float, float]] = []
    raw_margins: list[tuple[float, float]] = []
    gp_impact = 0.0
    for usage in trace.products:
        pid = usage.product_id
        item = index.items[pid]
        price = index.selling_price[pid]
        c0, c1, c2, c3 = (e.cost(pid).total for e in (base, step1, step2, final))
        m0, m3 = gross_margin(price, c0), gross_margin(price, c3)
        cov = ctx.products[pid]
        approval = index.approval_for(part_id, req.replacement_part_id, pid) if req.replacement_part_id else None
        level, reasons = assess(RiskInput(
            # Without a replacement in the scenario, the product still depends on the EOL part.
            has_approved_alternative=approval is not None and approval.approval_status == "APPROVED",
            coverage_days=cov.coverage_days, margin=m3, margin_threshold=req.margin_threshold,
            replacement_cost_increase_pct=(c1 - c0) / c0 if subs else None,
        ))
        raw_deltas.append((c3 - c0, c1 - c0, c2 - c1, c3 - c2))
        raw_costs.append((c0, c3))
        raw_margins.append((m0, m3))
        gp_impact += (c3 - c0) * cov.forecast_qty
        products.append(ScenarioProduct(
            product_id=pid, name=item.item_name, product_family=item.product_family or "Unassigned",
            effective_component_qty=usage.effective_component_qty, selling_price=rnd.money(price),
            current_unit_cost=rnd.money(c0), scenario_unit_cost=rnd.money(c3), unit_cost_delta=rnd.money(c3 - c0),
            delta_breakdown=DeltaBreakdown(component_replacement=rnd.money(c1 - c0), material=rnd.money(c2 - c1),
                                           freight=rnd.money(c3 - c2)),
            current_margin=rnd.ratio(m0), scenario_margin=rnd.ratio(m3),
            margin_delta_points=rnd.points((m3 - m0) * 100),
            below_threshold=m3 < req.margin_threshold,
            crosses_threshold=m0 >= req.margin_threshold > m3,
            horizon_forecast_qty=cov.forecast_qty, revenue_exposure=rnd.money(price * cov.forecast_qty),
            gross_profit_impact=rnd.money((c3 - c0) * cov.forecast_qty),
            replacement_approval=approval.approval_status if approval else None,
            risk_level=level, risk_reasons=reasons,
        ))
    products.sort(key=lambda p: (not p.below_threshold, RISK_ORDER[p.risk_level], p.scenario_margin))

    n = max(len(products), 1)
    summary = ScenarioSummary(
        product_count=len(products),
        average_current_unit_cost=rnd.money(sum(c0 for c0, _ in raw_costs) / n),
        average_scenario_unit_cost=rnd.money(sum(c3 for _, c3 in raw_costs) / n),
        average_unit_cost_delta=rnd.money(sum(d[0] for d in raw_deltas) / n),
        average_margin_delta_points=rnd.points(sum((m3 - m0) * 100 for m0, m3 in raw_margins) / n),
        average_current_margin=rnd.ratio(sum(m0 for m0, _ in raw_margins) / n),
        average_scenario_margin=rnd.ratio(sum(m3 for _, m3 in raw_margins) / n),
        current_products_below_threshold=sum(m0 < req.margin_threshold for m0, _ in raw_margins),
        products_below_margin_threshold=sum(p.below_threshold for p in products),
        products_newly_below_threshold=sum(p.crosses_threshold for p in products),
        revenue_at_risk=rnd.money(sum(p.revenue_exposure for p in products if p.below_threshold)),
        total_revenue_exposure=rnd.money(sum(p.revenue_exposure for p in products)),
        gross_profit_impact=rnd.money(gp_impact),
        driver_average_delta=DeltaBreakdown(
            component_replacement=rnd.money(sum(d[1] for d in raw_deltas) / n),
            material=rnd.money(sum(d[2] for d in raw_deltas) / n),
            freight=rnd.money(sum(d[3] for d in raw_deltas) / n)),
        horizon_months=horizon,
    )
    return ScenarioResult(
        scenario_id=f"SCN-{uuid.uuid4().hex[:8].upper()}", event_id=req.event_id,
        name=req.name or describe(req, part_id), created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        part_id=part_id, inputs=req, summary=summary, products=products,
    )
