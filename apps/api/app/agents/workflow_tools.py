"""Deterministic tools for the change-response agents, plus deterministic findings.

Each tool computes through `EventContext` (so pages and agents see the same
numbers) and returns compact JSON with a one-line `headline` used in the live
progress view. `deterministic_finding` writes each agent's finding from the
same artifacts; it is used when Gemini is unavailable and to replace any
agent text that quotes a number no tool returned.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from app.services.response import EventContext

BRIDGE_LOT = 500  # broker quantities are rounded up to this lot size
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _usd(x: float) -> str:
    return f"${x / 1_000_000:.2f}M" if abs(x) >= 1_000_000 else f"${x:,.0f}"


def _week(iso: str | None) -> str:
    if not iso:
        return "not within the plan horizon"
    y, m, d = (int(v) for v in iso.split("-"))
    return f"the week of {MONTHS[m - 1]} {d}"


def _plan_view(plan) -> dict[str, Any]:
    o, b = plan.optimized, plan.baseline
    unmet = [r for r in plan.products if r.affected and r.unmet > 0]
    kpi = lambda k: {"fill_rate": k.fill_rate, "affected_fill_rate": k.affected_fill_rate,  # noqa: E731
                     "strategic_fill_rate": k.strategic_fill_rate, "unmet_units": k.unmet_units,
                     "late_unit_weeks": k.late_unit_weeks, "gross_margin": k.gross_margin}
    return {
        "plan_id": plan.plan_id, "bridge_buy_qty": plan.inputs.bridge_buy_qty,
        "solver": f"{plan.solver.name} ({plan.solver.status})",
        "current_schedule": kpi(b),
        "optimized": {**kpi(o), "bridge_premium": o.bridge_premium, "component_used": o.component_used,
                      "alternative_used": o.alternative_used},
        "unmet_products": [{"product_id": r.product_id, "unmet_units": r.unmet, "strategic": r.strategic}
                           for r in unmet],
        "changes": [c.description for c in plan.changes],
    }


class WorkflowTools:
    """Tool functions bound to one event. Names and docstrings are what Gemini sees."""

    def __init__(self, ctx: EventContext) -> None:
        self.ctx = ctx

    # -- impact -------------------------------------------------------------

    def analyze_change_impact(self) -> dict:
        """Trace the affected component through the multi-level BOM (BigQuery Graph) and calculate
        the business impact: affected products, revenue exposure, inventory coverage and risk."""
        a = self.ctx.analysis()
        s = a.summary
        return {
            "component": a.component.part_id, "supplier": a.component.supplier_name,
            "affected_products": s.affected_product_count, "product_families": s.product_families,
            "revenue_exposure_6m": s.revenue_exposure, "inventory_coverage_days": int(s.inventory_coverage_days),
            "products_without_approved_alternative": s.products_without_approved_alternative,
            "trace_method": a.trace_method,
            "products": [{"product_id": p.product_id, "risk_level": p.risk_level,
                          "inventory_coverage_days": int(p.inventory_coverage_days),
                          "alternative_approval": p.alternative.approval_status if p.alternative else "NONE"}
                         for p in a.products],
            "headline": f"{s.affected_product_count} products in {len(s.product_families)} families, "
                        f"{_usd(s.revenue_exposure)} exposure, {int(s.inventory_coverage_days)} days of coverage",
        }

    # -- sourcing -------------------------------------------------------------

    def find_sourcing_options(self) -> dict:
        """Search the internal approved-vendor list and the distributor cross-reference catalog for
        alternative parts and suppliers for the affected component."""
        s = self.ctx.sourcing()
        internal = sum(c.source == "INTERNAL_AVL" for c in s.candidates)
        return {
            "part": s.part_id, "current_supplier": s.current_supplier, "current_unit_price": s.current_unit_price,
            "candidates": [{"candidate_id": c.candidate_id, "part_id": c.part_id, "supplier": c.supplier_name,
                            "country": c.country, "source": c.source, "channel": c.channel,
                            "match_type": c.match_type, "approval_status": c.approval_status,
                            "products_needing_validation": len(c.products_needing_validation),
                            "unit_price": c.unit_price, "price_change": c.price_delta_pct,
                            "lead_time_days": c.lead_time_days, "available_stock": c.available_stock}
                           for c in s.candidates],
            "headline": f"{len(s.candidates)} options: {internal} on the approved-vendor list, "
                        f"{len(s.candidates) - internal} from the distributor catalog",
        }

    def get_supplier_performance(self) -> dict:
        """Delivery, quality and lead-time KPIs for every candidate supplier from the ERP and quality
        system (last four quarters)."""
        ev = self.ctx.evidence("performance")
        rows = [{"supplier": e.supplier_name,
                 **({"quarters": e.performance.quarters, "on_time_delivery_rate": e.performance.on_time_delivery_rate,
                     "quality_ppm": e.performance.quality_ppm, "avg_lead_time_days": e.performance.avg_lead_time_days,
                     "on_time_trend_points": e.performance.on_time_trend_points}
                    if e.performance else {"history": "none"})} for e in ev]
        with_history = sum(e.performance is not None for e in ev)
        return {"suppliers": rows,
                "headline": f"KPIs for {with_history} suppliers; {len(ev) - with_history} have no history"}

    def screen_suppliers(self) -> dict:
        """Screen every candidate supplier (and the distributor selling the part) against sanctions
        and export-control lists."""
        ev = self.ctx.evidence("sanctions")
        hits = [{"supplier": e.supplier_name, "matches": [h.model_dump() for h in e.sanctions_hits]}
                for e in ev if e.sanctions_hits]
        return {"screened": len(ev), "list": self.ctx.integrations.sanctions.list_name, "matches": hits,
                "headline": f"Screened {len(ev)} suppliers: {len(hits)} match" + ("" if len(hits) == 1 else "es")}

    def search_supplier_news(self) -> dict:
        """Recent news about every candidate supplier: capacity, quality, financial and disruption events."""
        ev = self.ctx.evidence("news")
        rows = [{"supplier": e.supplier_name,
                 "articles": [{"date": n.date, "severity": n.severity, "category": n.category,
                               "headline": n.headline} for n in e.news]} for e in ev if e.news]
        high = sum(n.severity == "HIGH" for e in ev for n in e.news)
        total = sum(len(e.news) for e in ev)
        return {"suppliers": rows, "headline": f"{total} articles found, {high} high-severity"}

    def score_suppliers(self) -> dict:
        """Score every sourcing option 0-100 on delivery, quality, lead time, cost, supply risk and
        qualification (fixed weights), apply the compliance gate, and pick the transition part, the
        long-term second source and any bridge stock."""
        a = self.ctx.assessment()
        cards = [{"candidate_id": c.candidate_id, "part_id": c.part_id, "supplier": c.supplier_name,
                  "score": c.total_score, "tier": c.tier, "flags": c.flags} for c in a.scorecards]
        rec = next((c for c in a.scorecards if c.candidate_id == a.recommended_candidate_id), None)
        return {"weights": a.weights, "scorecards": cards, "recommended_transition": a.recommended_candidate_id,
                "second_source": a.second_source_candidate_id, "bridge_stock": a.bridge_candidate_id,
                "blocked": a.blocked_candidate_ids,
                "headline": (f"Transition: {rec.part_id} ({rec.total_score:.1f})" if rec else "No approved transition")
                + f"; {len(a.blocked_candidate_ids)} blocked"}

    # -- planning -------------------------------------------------------------

    def forecast_demand(self) -> dict:
        """Statistical demand forecast for the affected products (BigQuery AI.FORECAST with TimesFM, or
        a seasonal-trend baseline locally), compared with the current demand plan."""
        f = self.ctx.forecast()
        rows = [{"product_id": p.product_id, "plan_6m": p.plan_total, "forecast_6m": p.forecast_total,
                 "forecast_vs_plan": p.delta_pct} for p in f.products]
        top = max(f.products, key=lambda p: p.delta_pct) if f.products else None
        return {"method": f.model, "products": rows,
                "headline": f"{f.model}: "
                            + (f"{top.product_id} {top.delta_pct * 100:+.1f}% vs plan" if top else "no data")}

    def calculate_material_requirements(self) -> dict:
        """Explode the 13-week work orders into weekly requirements for the affected component and
        find the week it runs out, at plan and at the statistical forecast."""
        m = self.ctx.materials()
        return {"part": m.part_id, "available_qty": m.available_qty, "requirement_13_weeks": m.total_requirement,
                "stockout_week_at_plan": m.stockout_week, "stockout_week_at_forecast": m.stockout_week_forecast,
                "headline": f"{m.part_id} runs out {_week(m.stockout_week)} at plan"}

    def get_bridge_supply_options(self) -> dict:
        """Broker offers of the affected part itself that could bridge a shortage, with price premium
        and lead time including incoming inspection."""
        s = self.ctx.sourcing()
        offers = [{"candidate_id": c.candidate_id, "supplier": c.supplier_name, "available_stock": c.available_stock,
                   "unit_price": c.unit_price, "premium_per_unit": round(c.unit_price - s.current_unit_price, 2),
                   "lead_time_days": c.lead_time_days, "inspection_days": c.qualification_lead_time_days,
                   "lot_size": BRIDGE_LOT}
                  for c in s.candidates if c.match_type == "SAME_PART" and c.channel == "BROKER"]
        return {"offers": offers, "headline": f"{len(offers)} broker offer(s)"}

    def optimize_production_plan(self, bridge_buy_qty: int = 0) -> dict:
        """Re-plan the next 13 weeks of production with the Google OR-Tools CP-SAT solver: lines,
        weeks, which units switch to the alternative part, within capacity and component supply.

        Args:
            bridge_buy_qty: units of the affected part to buy from broker stock (0 for none). Use a
                multiple of the broker lot size.
        """
        plan = self.ctx.optimize(max(0, int(bridge_buy_qty)))
        view = _plan_view(plan)
        usage = {p.product_id: p.effective_component_qty for p in self.ctx.analysis().products}
        need = sum(u["unmet_units"] * usage.get(u["product_id"], 1.0) for u in view["unmet_products"])
        view["component_shortfall_units"] = need
        view["suggested_bridge_qty"] = int(math.ceil(need / BRIDGE_LOT) * BRIDGE_LOT) if need else 0
        o = plan.optimized
        view["headline"] = (f"{plan.plan_id}: fill {_pct(o.fill_rate)} (current {_pct(plan.baseline.fill_rate)}), "
                            f"margin {_usd(o.gross_margin)}")
        return view

    def propose_production_plan(self, plan_id: str, rationale: str) -> dict:
        """Submit one optimized plan for human approval by the Operations Manager.

        Args:
            plan_id: the plan to propose, as returned by optimize_production_plan.
            rationale: one or two sentences on why this plan is preferred.
        """
        plan = self.ctx.propose(plan_id.strip(), rationale.strip())
        return {"plan_id": plan.plan_id, "status": plan.status, "awaiting": "Operations Manager approval",
                "headline": f"{plan.plan_id} proposed for approval"}

    # -- response ---------------------------------------------------------------

    def generate_action_plan(self) -> dict:
        """Build the cross-functional action plan from the impact analysis, the supplier assessment
        and the proposed production plan."""
        plan = self.ctx.action_plan(rewrite=False)  # the coordinator writes the narrative
        return {"summary": plan.summary,
                "actions": [{"department": a.department, "priority": a.priority, "title": a.title}
                            for a in plan.actions],
                "headline": f"{len(plan.actions)} actions across "
                            f"{len({a.department for a in plan.actions})} departments"}

    def all(self) -> dict[str, Callable[..., dict]]:
        return {name: getattr(self, name) for name in (
            "analyze_change_impact", "find_sourcing_options", "get_supplier_performance", "screen_suppliers",
            "search_supplier_news", "score_suppliers", "forecast_demand", "calculate_material_requirements",
            "get_bridge_supply_options", "optimize_production_plan", "propose_production_plan",
            "generate_action_plan")}


# -- deterministic findings -------------------------------------------------------


def choose_plan(call: Callable[..., dict]) -> tuple[str, str]:
    """The deterministic planner: try a bridge buy only if demand is left unmet,
    and keep it only if it fills more demand without costing more margin.
    `call(tool_name, **args)` runs a tool (and lets the caller record the step)."""
    base = call("optimize_production_plan", bridge_buy_qty=0)
    if not base["unmet_products"]:
        return base["plan_id"], "The optimized plan meets all demand without a bridge buy."
    offers = call("get_bridge_supply_options")["offers"]
    if not offers:
        return base["plan_id"], "No bridge stock is available, so the optimized plan is proposed as is."
    qty = min(base["suggested_bridge_qty"], offers[0]["available_stock"] or base["suggested_bridge_qty"])
    bridged = call("optimize_production_plan", bridge_buy_qty=qty)
    better_fill = bridged["optimized"]["affected_fill_rate"] > base["optimized"]["affected_fill_rate"]
    keeps_margin = bridged["optimized"]["gross_margin"] >= base["optimized"]["gross_margin"]
    if better_fill and keeps_margin:
        return bridged["plan_id"], (f"A {bridged['bridge_buy_qty']:,}-unit bridge buy closes the remaining gap and "
                                    "earns more margin than it costs in broker premium.")
    return base["plan_id"], "The bridge buy does not pay back its broker premium, so the plan without it is preferred."


def deterministic_finding(agent: str, ctx: EventContext) -> str:
    st = ctx.store
    eid = ctx.event_id
    if agent == "impact_analyst":
        s = ctx.analysis().summary
        return (f"{ctx.part_id} affects {s.affected_product_count} products across {s.product_family_count} "
                f"families, with {_usd(s.revenue_exposure)} of revenue exposure over {s.horizon_months} months. "
                f"Inventory covers {int(s.inventory_coverage_days)} days, and "
                f"{s.products_without_approved_alternative} products have no approved alternative.")
    if agent == "sourcing_scout":
        s = ctx.sourcing()
        internal = [c.part_id for c in s.candidates if c.source == "INTERNAL_AVL"]
        external = [f"{c.part_id} ({c.supplier_name})" for c in s.candidates if c.source != "INTERNAL_AVL"]
        return (f"Found {len(s.candidates)} sourcing options for {s.part_id}: {', '.join(internal)} on the approved-"
                f"vendor list, and {', '.join(external)} from the distributor catalog.")
    if agent == "performance_auditor":
        ev = ctx.evidence("performance")
        parts = []
        for e in ev:
            p = e.performance
            if p:
                parts.append(f"{e.supplier_name} delivers {_pct(p.on_time_delivery_rate)} on time "
                             f"({p.on_time_trend_points:+.1f} points over {p.quarters} quarters)")
        none = [e.supplier_name for e in ev if e.performance is None]
        return "; ".join(parts) + "." + (f" No history for {', '.join(none)}." if none else "")
    if agent == "compliance_screener":
        ev2 = ctx.evidence("sanctions")
        hits = [e for e in ev2 if e.sanctions_hits]
        if not hits:
            return f"Screened {len(ev2)} suppliers; none match the {ctx.integrations.sanctions.list_name}."
        h = hits[0].sanctions_hits[0]
        return (f"Screened {len(ev2)} suppliers. {hits[0].supplier_name} matches {h.listed_name} on the "
                f"{h.list_name} ({h.program}), so it must be excluded.")
    if agent == "risk_news_monitor":
        ev3 = ctx.evidence("news")
        items = sorted(((n, e.supplier_name) for e in ev3 for n in e.news),
                       key=lambda t: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2, "POSITIVE": 3}[t[0].severity], t[0].date))
        high = [f"{name}: {n.headline}" for n, name in items if n.severity == "HIGH"]
        return (f"{len(items)} recent articles. High-severity: " + "; ".join(high) + "."
                if high else f"{len(items)} recent articles, none high-severity.")
    if agent == "supplier_evaluator":
        a = st.assessments.get(eid) or ctx.assessment()
        cards = {c.candidate_id: c for c in a.scorecards}
        out = []
        if a.recommended_candidate_id:
            c = cards[a.recommended_candidate_id]
            out.append(f"Transition to {c.part_id} from {c.supplier_name} (score {c.total_score:.1f}), the fastest "
                       "approved option")
        if a.second_source_candidate_id:
            c = cards[a.second_source_candidate_id]
            out.append(f"develop {c.part_id} from {c.supplier_name} (score {c.total_score:.1f}) as a second source")
        if a.bridge_candidate_id:
            c = cards[a.bridge_candidate_id]
            out.append(f"treat {c.supplier_name} stock as bridge-only")
        for cid in a.blocked_candidate_ids:
            out.append(f"exclude {cards[cid].supplier_name} (compliance block)")
        text = "; ".join(out)
        return text[:1].upper() + text[1:] + "."
    if agent == "demand_planner":
        f, m = ctx.forecast(), ctx.materials()
        top = max(f.products, key=lambda p: p.delta_pct)
        return (f"{f.model} puts {top.product_id} {top.delta_pct * 100:+.1f}% above plan over "
                f"{f.horizon_months} months. {m.part_id} runs out {_week(m.stockout_week)} at plan and "
                f"{_week(m.stockout_week_forecast)} at the statistical forecast.")
    if agent == "production_planner":
        plan = ctx.proposed_plan()
        if plan is None:
            return "No production plan was proposed."
        o, b = plan.optimized, plan.baseline
        bridge = (f" with a {plan.inputs.bridge_buy_qty:,}-unit bridge buy" if plan.inputs.bridge_buy_qty else "")
        return (f"Proposed {plan.plan_id}{bridge}: OR-Tools fills {_pct(o.affected_fill_rate)} of affected-product "
                f"demand versus {_pct(b.affected_fill_rate)} in the current schedule, at {_usd(o.gross_margin)} "
                f"gross margin versus {_usd(b.gross_margin)}. It awaits Operations Manager approval.")
    if agent == "response_coordinator":
        plan = st.action_plans.get(eid) or ctx.action_plan()
        high = [a.title for a in plan.actions if a.priority == "HIGH"]
        return plan.summary + (" Priority actions: " + "; ".join(high[:4]) + "." if high else "")
    return ""
