"""Current-state business impact of a component change (handoff Phase 4)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.db.repository import Repository
from app.models.bom import BomTrace
from app.models.impact import (
    AlternativeApproval,
    AlternativeComparison,
    ComponentInfo,
    CostBreakdownOut,
    GraphEdge,
    GraphNode,
    ImpactAnalysis,
    ImpactGraph,
    ImpactSummary,
    ProductImpact,
)
from app.services import rounding as rnd
from app.services.costing import CostBreakdown, CostEngine, CostParams, gross_margin
from app.services.demand import forecast_qty, horizon_days, horizon_months, open_order_qty
from app.services.index import DataIndex
from app.services.risk import RISK_ORDER, RiskInput, assess


class UnknownPartError(ValueError):
    pass


def breakdown_out(b: CostBreakdown) -> CostBreakdownOut:
    return CostBreakdownOut(purchase=rnd.money(b.purchase), material=rnd.money(b.material),
                            freight=rnd.money(b.freight), processing=rnd.money(b.processing),
                            total=rnd.money(b.total))


def validate_component(index: DataIndex, part_id: str) -> None:
    item = index.items.get(part_id)
    if item is None or item.item_type != "COMPONENT":
        raise UnknownPartError(part_id)


def default_replacement(index: DataIndex, part_id: str, preferred: str | None) -> str | None:
    options = index.alternative_ids(part_id)
    if preferred and preferred in options:
        return preferred
    for a in index.alternates.get(part_id, []):
        if a.product_id is None and a.approval_status == "APPROVED":
            return a.alternative_part_id
    return options[0] if options else None


def approval(index: DataIndex, part_id: str, alt_id: str | None, product_id: str) -> AlternativeApproval | None:
    if alt_id is None:
        return None
    a = index.approval_for(part_id, alt_id, product_id)
    if a is None:
        return AlternativeApproval(part_id=alt_id, approval_status="NONE", qualification_lead_time_days=0, notes="")
    return AlternativeApproval(part_id=alt_id, approval_status=a.approval_status,
                               qualification_lead_time_days=a.qualification_lead_time_days, notes=a.notes)


def component_info(index: DataIndex, part_id: str, engine: CostEngine) -> ComponentInfo:
    item = index.items[part_id]
    sp = index.supplier_part.get(part_id)
    return ComponentInfo(
        part_id=part_id, name=item.item_name, status=item.status,
        supplier_id=sp.supplier_id if sp else None, supplier_name=index.supplier_name_for_part(part_id),
        unit_price=sp.current_unit_price if sp else None, unit_cost=rnd.money(engine.cost(part_id).total),
        lead_time_days=sp.lead_time_days if sp else None, shipping_lane_id=sp.shipping_lane_id if sp else None,
        available_qty=index.available_qty.get(part_id, 0.0),
    )


def build_graph(index: DataIndex, trace: BomTrace, product_risk: dict[str, str]) -> ImpactGraph:
    depth: dict[str, int] = {trace.component_id: 0}
    edges: dict[str, GraphEdge] = {}
    for path in trace.paths:
        bottom_up = list(reversed(path.nodes))
        for d, node in enumerate(bottom_up):
            depth[node] = max(depth.get(node, 0), d)
        for parent, child, qty in zip(path.nodes[:-1], path.nodes[1:], path.edge_qtys, strict=True):
            eid = f"{parent}->{child}"
            edges[eid] = GraphEdge(id=eid, source=parent, target=child, qty_per_parent=qty)
    usage = {p.product_id: p.effective_component_qty for p in trace.products}
    nodes = [
        GraphNode(id=node_id, label=index.item_name(node_id), item_type=index.items[node_id].item_type,
                  depth=d, risk_level=product_risk.get(node_id), effective_component_qty=usage.get(node_id),
                  status=index.items[node_id].status)
        for node_id, d in sorted(depth.items(), key=lambda kv: (kv[1], kv[0]))
    ]
    return ImpactGraph(nodes=nodes, edges=sorted(edges.values(), key=lambda e: e.id))


def compare_alternatives(index: DataIndex, part_id: str, trace: BomTrace, base: CostEngine,
                         margin_threshold: float, recommended: str | None) -> list[AlternativeComparison]:
    out: list[AlternativeComparison] = []
    src = index.supplier_part.get(part_id)
    for alt_id in index.alternative_ids(part_id):
        if alt_id not in index.items:
            continue
        engine = CostEngine(index, CostParams(substitutions={part_id: alt_id}))
        counts: dict[str, int] = defaultdict(int)
        max_qual = 0
        cost_deltas, margin_deltas, below = [], [], 0
        for usage in trace.products:
            pid = usage.product_id
            a = index.approval_for(part_id, alt_id, pid)
            status = a.approval_status if a else "NONE"
            counts[status] += 1
            if a and status != "APPROVED":
                max_qual = max(max_qual, a.qualification_lead_time_days)
            price = index.selling_price[pid]
            c0, c1 = base.cost(pid).total, engine.cost(pid).total
            cost_deltas.append(c1 - c0)
            margin_deltas.append((gross_margin(price, c1) - gross_margin(price, c0)) * 100)
            below += gross_margin(price, c1) < margin_threshold
        sp = index.supplier_part.get(alt_id)
        default = next((a.approval_status for a in index.alternates.get(part_id, [])
                        if a.alternative_part_id == alt_id and a.product_id is None), "NONE")
        n = max(len(trace.products), 1)
        out.append(AlternativeComparison(
            part_id=alt_id, name=index.item_name(alt_id), supplier_name=index.supplier_name_for_part(alt_id),
            unit_price=sp.current_unit_price if sp else None,
            unit_price_delta_pct=rnd.ratio(sp.current_unit_price / src.current_unit_price - 1) if sp and src else None,
            lead_time_days=sp.lead_time_days if sp else None, default_approval=default,
            approved_products=counts["APPROVED"], validation_required_products=counts["VALIDATION_REQUIRED"],
            not_approved_products=counts["NOT_APPROVED"] + counts["NONE"],
            max_qualification_lead_time_days=max_qual,
            average_unit_cost_delta=rnd.money(sum(cost_deltas) / n),
            average_margin_delta_points=rnd.points(sum(margin_deltas) / n),
            products_below_margin_threshold=below, recommended=alt_id == recommended,
        ))
    return out


@dataclass(frozen=True)
class ProductCoverage:
    forecast_qty: float
    finished_goods_available: float
    finished_goods_days: float
    coverage_days: float  # shared component stock + this product's finished-goods stock


@dataclass(frozen=True)
class CoverageContext:
    months: list[date]
    horizon_days: int
    component_available: float
    total_requirement: float
    daily_requirement: float
    component_days: float
    products: dict[str, ProductCoverage]


def coverage_context(index: DataIndex, part_id: str, trace: BomTrace, horizon: int) -> CoverageContext:
    """Inventory coverage = available stock / average daily requirement over the horizon."""
    months = horizon_months(index.as_of, horizon)
    n_days = horizon_days(months)
    total = sum(u.effective_component_qty * forecast_qty(index, u.product_id, months) for u in trace.products)
    daily = total / n_days if n_days else 0.0
    available = index.available_qty.get(part_id, 0.0)
    component_days = available / daily if daily else 0.0
    products = {}
    for u in trace.products:
        f_qty = forecast_qty(index, u.product_id, months)
        fg = index.available_qty.get(u.product_id, 0.0)
        fg_days = fg / (f_qty / n_days) if f_qty else 0.0
        products[u.product_id] = ProductCoverage(f_qty, fg, fg_days, component_days + fg_days)
    return CoverageContext(months, n_days, available, total, daily, component_days, products)


def analyze_impact(repo: Repository, part_id: str, margin_threshold: float, horizon: int,
                   event_id: str | None = None, preferred_alternative: str | None = None) -> ImpactAnalysis:
    index = repo.index()
    validate_component(index, part_id)
    trace = repo.trace(part_id)
    ctx = coverage_context(index, part_id, trace, horizon)
    months = ctx.months
    base = CostEngine(index)
    replacement = default_replacement(index, part_id, preferred_alternative)
    rep_engine = CostEngine(index, CostParams(substitutions={part_id: replacement})) if replacement else None
    component_unit_cost = base.cost(part_id).total

    products: list[ProductImpact] = []
    gp_at_risk = 0.0
    for usage in trace.products:
        pid = usage.product_id
        item = index.items[pid]
        price = index.selling_price[pid]
        cost = base.cost(pid)
        margin = gross_margin(price, cost.total)
        cov = ctx.products[pid]
        f_qty, fg_available, fg_days, coverage = (cov.forecast_qty, cov.finished_goods_available,
                                                  cov.finished_goods_days, cov.coverage_days)
        alt = approval(index, part_id, replacement, pid)
        rep_delta = rep_margin = None
        if rep_engine is not None:
            rep_cost = rep_engine.cost(pid).total
            rep_delta = rep_cost - cost.total
            rep_margin = gross_margin(price, rep_cost)
            gp_at_risk += rep_delta * f_qty
        level, reasons = assess(RiskInput(
            has_approved_alternative=alt is not None and alt.approval_status == "APPROVED",
            coverage_days=coverage, margin=margin, margin_threshold=margin_threshold,
            replacement_cost_increase_pct=(rep_delta / cost.total) if rep_delta is not None else None,
        ))
        products.append(ProductImpact(
            product_id=pid, name=item.item_name, product_family=item.product_family or "Unassigned",
            effective_component_qty=usage.effective_component_qty, paths_to_component=usage.paths_to_component,
            selling_price=rnd.money(price), unit_cost=rnd.money(cost.total), current_margin=rnd.ratio(margin),
            cost_breakdown=breakdown_out(cost),
            component_cost_share=rnd.ratio(usage.effective_component_qty * component_unit_cost / cost.total),
            horizon_forecast_qty=f_qty, horizon_open_order_qty=open_order_qty(index, pid, months),
            revenue_exposure=rnd.money(price * f_qty),
            component_requirement=rnd.qty(usage.effective_component_qty * f_qty),
            finished_goods_available=fg_available, finished_goods_days=rnd.days(fg_days),
            inventory_coverage_days=rnd.days(coverage), alternative=alt,
            replacement_unit_cost_delta=rnd.money(rep_delta) if rep_delta is not None else None,
            replacement_margin=rnd.ratio(rep_margin) if rep_margin is not None else None,
            risk_level=level, risk_reasons=reasons,
        ))
    products.sort(key=lambda p: (RISK_ORDER[p.risk_level], -p.effective_component_qty, p.product_id))

    families = sorted({p.product_family for p in products})
    risk_counts = {level: sum(p.risk_level == level for p in products) for level in RISK_ORDER}
    n = max(len(products), 1)
    summary = ImpactSummary(
        affected_product_count=len(products), product_family_count=len(families), product_families=families,
        revenue_exposure=rnd.money(sum(p.revenue_exposure for p in products)), horizon_months=horizon,
        horizon_start=months[0].isoformat(), horizon_days=ctx.horizon_days,
        inventory_coverage_days=rnd.days(ctx.component_days),
        component_available_qty=ctx.component_available, component_daily_requirement=rnd.qty(ctx.daily_requirement),
        component_horizon_requirement=rnd.qty(ctx.total_requirement),
        products_without_approved_alternative=sum(
            1 for p in products if p.alternative is None or p.alternative.approval_status != "APPROVED"),
        margin_threshold=margin_threshold,
        products_below_margin_threshold=sum(p.current_margin < margin_threshold for p in products),
        average_current_margin=rnd.ratio(sum(p.current_margin for p in products) / n),
        replacement_part_id=replacement,
        replacement_gross_profit_at_risk=rnd.money(gp_at_risk) if rep_engine else None,
        risk_counts=risk_counts,
    )
    return ImpactAnalysis(
        analysis_id=f"ANL-{uuid.uuid4().hex[:8].upper()}", event_id=event_id,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"), as_of_date=index.as_of.isoformat(),
        data_source=repo.backend, trace_method=trace.trace_method,
        component=component_info(index, part_id, base), summary=summary, products=products, paths=trace.paths,
        alternatives=compare_alternatives(index, part_id, trace, base, margin_threshold, replacement),
        graph=build_graph(index, trace, {p.product_id: p.risk_level for p in products}),
    )
