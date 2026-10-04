"""Deterministic tools exposed to the RippleOps orchestrator.

Each tool returns compact, typed JSON computed by the BOM / cost / scenario
engines. Tools never ask the model for numbers; the model only chooses which
tool to call and explains the result. Every output is recorded so the final
answer can be checked for invented values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.db.repository import Repository
from app.models.events import ChangeEventOut
from app.models.impact import ImpactAnalysis
from app.models.scenario import ScenarioRequest
from app.observability import Timer
from app.services.scenario import ScenarioInputError
from app.services.scenario import run_scenario as run_scenario_engine
from app.services.store import DemoStore


@dataclass
class ToolSession:
    repo: Repository
    store: DemoStore
    settings: Settings
    event: ChangeEventOut
    analysis: ImpactAnalysis
    outputs: list[Any] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    scenario_ids: list[str] = field(default_factory=list)

    def record(self, name: str, args: dict, result: Any) -> Any:
        self.calls.append({"name": name, "args": args})
        self.outputs.append(result)
        return result


def _product_row(p) -> dict:
    return {
        "product_id": p.product_id, "name": p.name, "family": p.product_family,
        "effective_component_qty": p.effective_component_qty, "paths_to_component": p.paths_to_component,
        "unit_cost": p.unit_cost, "selling_price": p.selling_price, "gross_margin": p.current_margin,
        "revenue_exposure_6m": p.revenue_exposure, "inventory_coverage_days": int(p.inventory_coverage_days),
        "alternative_approval": p.alternative.approval_status if p.alternative else "NONE",
        "risk_level": p.risk_level, "risk_reasons": p.risk_reasons,
    }


def build_tools(s: ToolSession) -> list:
    part = s.analysis.component.part_id

    def calculate_business_impact() -> dict:
        """Current business impact of the change event: affected products, revenue exposure,
        inventory coverage, margins, risk levels and approved alternatives."""
        with Timer("tool", tool="calculate_business_impact"):
            a = s.analysis
            result = {
                "component": part, "supplier": a.component.supplier_name,
                "summary": {
                    "affected_products": a.summary.affected_product_count,
                    "product_families": a.summary.product_families,
                    "revenue_exposure_6m": a.summary.revenue_exposure,
                    "inventory_coverage_days": int(a.summary.inventory_coverage_days),
                    "products_without_approved_alternative": a.summary.products_without_approved_alternative,
                    "average_gross_margin": a.summary.average_current_margin,
                    "margin_threshold": a.summary.margin_threshold,
                    "risk_counts": a.summary.risk_counts,
                },
                "alternatives": [
                    {"part_id": x.part_id, "unit_price_change": x.unit_price_delta_pct,
                     "approved_products": x.approved_products, "average_unit_cost_delta": x.average_unit_cost_delta,
                     "average_margin_delta_points": x.average_margin_delta_points,
                     "products_below_threshold": x.products_below_margin_threshold}
                    for x in a.alternatives],
                "products": [_product_row(p) for p in a.products],
            }
        return s.record("calculate_business_impact", {}, result)

    def trace_bom_impact(product_id: str) -> dict:
        """BOM dependency paths from a finished product down to the affected component, with the
        quantity on each edge and the effective component quantity per product unit."""
        pid = product_id.strip().upper()
        with Timer("tool", tool="trace_bom_impact"):
            paths = [p for p in s.analysis.paths if p.product_id == pid]
            result = {
                "product_id": pid, "component": part, "found": bool(paths),
                "paths": [{"nodes": p.nodes, "edge_qtys": p.edge_qtys, "path_qty": p.path_qty} for p in paths],
                "effective_component_qty": sum(p.path_qty for p in paths),
            }
        return s.record("trace_bom_impact", {"product_id": pid}, result)

    def get_product_impact(product_id: str) -> dict:
        """Full calculated impact for one finished product: cost breakdown, margin, coverage,
        alternative approval, replacement cost delta and the deterministic risk reasons."""
        pid = product_id.strip().upper()
        p = next((x for x in s.analysis.products if x.product_id == pid), None)
        if p is None:
            return s.record("get_product_impact", {"product_id": pid},
                            {"found": False, "message": f"{pid} does not use {part}."})
        result = {**_product_row(p), "found": True, "cost_breakdown": p.cost_breakdown.model_dump(),
                  "component_cost_share": p.component_cost_share,
                  "finished_goods_days": int(p.finished_goods_days),
                  "component_stock_days": int(s.analysis.summary.inventory_coverage_days),
                  "replacement_part": p.alternative.part_id if p.alternative else None,
                  "replacement_unit_cost_delta": p.replacement_unit_cost_delta,
                  "replacement_margin": p.replacement_margin,
                  "qualification_lead_time_days": p.alternative.qualification_lead_time_days if p.alternative else None}
        return s.record("get_product_impact", {"product_id": pid}, result)

    def run_scenario(replacement_part_id: str = "", material_code: str = "", material_change: float = 0.0,
                     shipping_lane_id: str = "", freight_change: float = 0.0, margin_threshold: float = 0.0) -> dict:
        """Deterministic what-if calculation on the affected products.

        Args:
            replacement_part_id: alternative to use instead of the affected component, e.g. "MCU-X200";
                empty to keep the current part.
            material_code: raw material to change: COPPER, ALUMINUM, STEEL, RESIN or TIN; empty for none.
            material_change: fractional change, e.g. 0.12 for +12%.
            shipping_lane_id: lane to change, e.g. "TW-US-OCEAN"; empty for none.
            freight_change: fractional change, e.g. 0.15 for +15%.
            margin_threshold: target gross margin as a fraction; 0 uses the event default (0.20).
        """
        args = {k: v for k, v in dict(replacement_part_id=replacement_part_id, material_code=material_code,
                                        material_change=material_change, shipping_lane_id=shipping_lane_id,
                                        freight_change=freight_change, margin_threshold=margin_threshold).items() if v}
        materials = {material_code.strip().upper(): material_change} if material_code and material_change else {}
        lanes = {shipping_lane_id.strip().upper(): freight_change} if shipping_lane_id and freight_change else {}
        req = ScenarioRequest(
            event_id=s.event.event_id,
            replacement_part_id=replacement_part_id.strip().upper() or None,
            commodity_adjustments=materials,
            freight_adjustments=lanes,
            margin_threshold=margin_threshold or s.analysis.summary.margin_threshold,
        )
        try:
            with Timer("tool", tool="run_scenario"):
                r = run_scenario_engine(s.repo, part, req, s.settings.demand_horizon_months)
        except ScenarioInputError as exc:
            return s.record("run_scenario", args, {"error": str(exc)})
        s.store.save_scenario(r)
        s.scenario_ids.append(r.scenario_id)
        result = {
            "scenario_id": r.scenario_id, "scenario": r.name,
            "summary": r.summary.model_dump(exclude={"product_count"}),
            "products": [{"product_id": p.product_id, "unit_cost_delta": p.unit_cost_delta,
                          "current_margin": p.current_margin, "scenario_margin": p.scenario_margin,
                          "margin_delta_points": p.margin_delta_points, "below_threshold": p.below_threshold,
                          "risk_level": p.risk_level} for p in r.products],
        }
        return s.record("run_scenario", args, result)

    def get_action_plan() -> dict:
        """The current recommended cross-functional action plan for this event, if one was generated."""
        plan = s.store.action_plans.get(s.event.event_id)
        result = {"generated": plan is not None, "summary": plan.summary if plan else None,
                  "scenario": plan.scenario_name if plan else None,
                  "actions": [a.model_dump(include={"department", "priority", "title", "reason", "status", "owner"})
                              for a in (plan.actions if plan else [])]}
        return s.record("get_action_plan", {}, result)

    def _workflow_tools():
        from app.agents.workflow_tools import WorkflowTools
        from app.services.response import EventContext

        return WorkflowTools(EventContext(s.repo, s.store, s.settings, s.event))

    def get_sourcing_assessment() -> dict:
        """Alternative parts and suppliers for the affected component with their 0-100 scorecards,
        compliance blocks, and the recommended transition, second source and bridge stock."""
        with Timer("tool", tool="get_sourcing_assessment"):
            result = _workflow_tools().score_suppliers()
        return s.record("get_sourcing_assessment", {}, result)

    def get_demand_forecast() -> dict:
        """Statistical demand forecast per affected product compared with the demand plan, and the
        week the affected component runs out."""
        t = _workflow_tools()
        with Timer("tool", tool="get_demand_forecast"):
            result = {**t.forecast_demand(), "materials": t.calculate_material_requirements()}
        return s.record("get_demand_forecast", {}, result)

    def get_production_plan(bridge_buy_qty: int = 0) -> dict:
        """Optimized 13-week production plan (Google OR-Tools) versus the current schedule.

        Args:
            bridge_buy_qty: units of the affected part to buy from broker stock; 0 for none.
        """
        with Timer("tool", tool="get_production_plan"):
            result = _workflow_tools().optimize_production_plan(bridge_buy_qty)
        return s.record("get_production_plan", {"bridge_buy_qty": bridge_buy_qty}, result)

    return [calculate_business_impact, trace_bom_impact, get_product_impact, run_scenario, get_action_plan,
            get_sourcing_assessment, get_demand_forecast, get_production_plan]
