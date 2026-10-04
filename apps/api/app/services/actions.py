"""Cross-functional action plan (handoff Phase 9).

Rules decide *which* actions are needed, their department and priority, from
calculated facts. Gemini may rewrite titles and reasons in plain business
English, but a rewrite is only accepted when every number in it traces back to
the facts; otherwise the rule-based wording is kept.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

from app.ai import prompts
from app.ai.gemini import GeminiUnavailable, generate_structured
from app.ai.grounding import collect_numbers, unverified_numbers
from app.config import get_settings
from app.models.actions import Action, ActionPlan, PlanRewrite
from app.models.assistant import Grounding
from app.models.events import ChangeEventOut
from app.models.impact import ImpactAnalysis
from app.models.planning import ProductionPlan
from app.models.scenario import ScenarioResult
from app.models.sourcing import SupplierAssessment

log = logging.getLogger("rippleops.actions")

OWNERS = {
    "Procurement": "Procurement Lead",
    "Engineering": "Engineering Manager",
    "Operations": "Operations Manager",
    "Finance": "Finance Controller",
    "Sales / Product": "Product Manager",
}
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _pct0(x: float) -> str:
    return f"{x * 100:.0f}%" if round(x * 100, 1).is_integer() else _pct(x)


def _d(x: date | None) -> str:
    return x.strftime("%b %d, %Y").replace(" 0", " ") if x else "not stated"


def _usd(x: float) -> str:
    return f"${x:,.0f}" if abs(x) >= 1000 else f"${x:,.2f}"


def _list(ids: list[str], limit: int = 5) -> str:
    return ", ".join(ids[:limit]) + (f" and {len(ids) - limit} more" if len(ids) > limit else "")


def candidate_actions(event: ChangeEventOut, analysis: ImpactAnalysis, scenario: ScenarioResult,
                      assessment: SupplierAssessment | None = None, plan: ProductionPlan | None = None) -> list[Action]:
    s = analysis.summary
    part = analysis.component.part_id
    supplier = analysis.component.supplier_name or "the supplier"
    alt = scenario.inputs.replacement_part_id
    alt_info = next((a for a in analysis.alternatives if a.part_id == alt), None)
    cov = int(s.inventory_coverage_days)
    shortfall = max(0.0, s.component_horizon_requirement - s.component_available_qty)
    threshold = scenario.inputs.margin_threshold
    below = [p for p in scenario.products if p.below_threshold]
    needs_validation = [p.product_id for p in analysis.products
                        if not p.alternative or p.alternative.approval_status != "APPROVED"]
    low_cov = sorted((p for p in analysis.products if p.inventory_coverage_days < 90),
                     key=lambda p: p.inventory_coverage_days)
    high_risk = [p for p in analysis.products if p.risk_level in ("CRITICAL", "HIGH")]
    runout = date.fromisoformat(analysis.as_of_date) + timedelta(days=cov)
    out: list[dict] = []

    # Procurement
    out.append(dict(
        department="Procurement", priority="HIGH" if cov < 90 else "MEDIUM", rule="ltb_allocation",
        title=f"Secure a six-month last-time-buy allocation of {part}",
        reason=(f"Current inventory covers only {cov} days. The next {s.horizon_months} months need "
                f"{s.component_horizon_requirement:,.0f} units against {s.component_available_qty:,.0f} available, "
                f"a shortfall of {shortfall:,.0f} units."),
        facts=[f"Inventory coverage: {cov} days", f"Shortfall: {shortfall:,.0f} units",
               f"Last time buy: {_d(event.last_time_buy_date)}"],
        related=[]))
    if event.last_time_buy_date:
        out.append(dict(
            department="Procurement", priority="MEDIUM", rule="confirm_deadline",
            title=f"Confirm allocation deadline with {supplier}",
            reason=(f"Last-time-buy orders close on {_d(event.last_time_buy_date)} and the last shipment is "
                    f"{_d(event.last_ship_date)}. Confirm allocation terms before committing volumes."),
            facts=[f"Last time buy: {_d(event.last_time_buy_date)}", f"Last ship date: {_d(event.last_ship_date)}"],
            related=[]))
    if alt and alt_info and (alt_info.unit_price_delta_pct or 0) > 0:
        out.append(dict(
            department="Procurement", priority="MEDIUM", rule="negotiate_price",
            title=f"Negotiate {alt} pricing",
            reason=(f"{alt} costs {_pct(alt_info.unit_price_delta_pct or 0)} more than {part}, adding "
                    f"{_usd(alt_info.average_unit_cost_delta)} to the average product unit cost."),
            facts=[f"Price change: +{_pct(alt_info.unit_price_delta_pct or 0)}",
                   f"Average unit cost change: +{_usd(alt_info.average_unit_cost_delta)}"],
            related=[]))

    # Engineering
    if alt and needs_validation:
        qual = alt_info.max_qualification_lead_time_days if alt_info else 0
        out.append(dict(
            department="Engineering", priority="HIGH", rule="validate_alternative",
            title=f"Validate {alt} for {_list(needs_validation, 4)}",
            reason=(f"{len(needs_validation)} products have no approved alternative for {part}. Qualification takes "
                    f"about {qual} days, so it must start well before inventory runs out in {cov} days."),
            facts=[f"Products needing validation: {len(needs_validation)}", f"Qualification lead time: {qual} days"],
            related=needs_validation))
    if low_cov:
        out.append(dict(
            department="Engineering", priority="MEDIUM", rule="prioritize_low_coverage",
            title="Prioritize products with low inventory coverage",
            reason=("Sequence the transition by coverage: "
                    + ", ".join(f"{p.product_id} ({int(p.inventory_coverage_days)} days)" for p in low_cov[:5]) + "."),
            facts=[f"{p.product_id}: {int(p.inventory_coverage_days)} days" for p in low_cov[:5]],
            related=[p.product_id for p in low_cov]))

    # Finance
    if below:
        out.append(dict(
            department="Finance", priority="HIGH", rule="review_pricing",
            title=f"Review pricing for products below the {_pct0(threshold)} target margin",
            reason=(f"In the {scenario.name} scenario, {len(below)} products fall below target: "
                    + ", ".join(f"{p.product_id} ({_pct(p.scenario_margin)})" for p in below[:5])
                    + f". Revenue at risk is {_usd(scenario.summary.revenue_at_risk)} over "
                      f"{scenario.summary.horizon_months} months."),
            facts=[f"Products below target: {len(below)}",
                   f"Revenue at risk: {_usd(scenario.summary.revenue_at_risk)}"],
            related=[p.product_id for p in below]))
    if scenario.summary.average_unit_cost_delta > 0:
        out.append(dict(
            department="Finance", priority="MEDIUM", rule="update_standard_cost",
            title="Update standard costs and margin forecast",
            reason=(f"Average unit cost rises by {_usd(scenario.summary.average_unit_cost_delta)}, reducing gross "
                    f"profit by {_usd(scenario.summary.gross_profit_impact)} over the next "
                    f"{scenario.summary.horizon_months} months."),
            facts=[f"Average unit cost change: +{_usd(scenario.summary.average_unit_cost_delta)}",
                   f"Gross profit impact: {_usd(scenario.summary.gross_profit_impact)}"],
            related=[]))

    # Sales / Product
    if high_risk:
        open_orders = sum(p.horizon_open_order_qty for p in high_risk)
        out.append(dict(
            department="Sales / Product", priority="HIGH", rule="review_quotes",
            title="Review open quotes for high-risk products",
            reason=(f"{len(high_risk)} high-risk products carry {open_orders:,.0f} units of open orders: "
                    f"{_list([p.product_id for p in high_risk], 6)}."),
            facts=[f"High-risk products: {len(high_risk)}", f"Open order units: {open_orders:,.0f}"],
            related=[p.product_id for p in high_risk]))
    out.append(dict(
        department="Sales / Product", priority="MEDIUM", rule="flag_commitments",
        title="Flag pricing commitments that extend past inventory coverage",
        reason=(f"{part} stock runs out around {_d(runout)} at current forecast. Commitments beyond that date "
                "depend on the replacement plan and its cost."),
        facts=[f"Estimated run-out: {_d(runout)}"],
        related=[]))

    out += _sourcing_actions(part, assessment) + _plan_actions(plan)

    actions = [
        Action(action_id=f"{event.event_id}-A{i + 1:02d}", event_id=event.event_id, department=a["department"],
               priority=a["priority"], title=a["title"], reason=a["reason"], facts=a["facts"],
               related_products=a["related"], owner=OWNERS[a["department"]], rule=a["rule"])
        for i, a in enumerate(out)
    ]
    return sorted(actions, key=lambda a: (list(OWNERS).index(a.department), PRIORITY_ORDER[a.priority]))


def _sourcing_actions(part: str, assessment: SupplierAssessment | None) -> list[dict]:
    if assessment is None:
        return []
    out: list[dict] = []
    cards = {c.candidate_id: c for c in assessment.scorecards}
    rec = cards.get(assessment.recommended_candidate_id or "")
    second = cards.get(assessment.second_source_candidate_id or "")
    if second:
        qual = next((c.evidence for c in second.components if c.criterion == "Qualification"), "")
        vs = f" versus {rec.total_score:.1f} for {rec.part_id} from {rec.supplier_name}" if rec else ""
        out.append(dict(
            department="Procurement", priority="MEDIUM", rule="second_source",
            title=f"Develop {second.supplier_name} {second.part_id} as a second source",
            reason=(f"{second.supplier_name} scores {second.total_score:.1f} of 100{vs}. "
                    f"A second source reduces dependence on a single supplier. {qual}."),
            facts=[f"{second.part_id} score: {second.total_score:.1f}"]
            + ([f"{rec.part_id} score: {rec.total_score:.1f}"] if rec else []),
            related=[]))
    for cid in assessment.blocked_candidate_ids:
        card = cards[cid]
        out.append(dict(
            department="Procurement", priority="HIGH", rule="compliance_block",
            title=f"Exclude {card.supplier_name} from sourcing",
            reason=f"{card.flags[0]}. Its {card.part_id} offer cannot be used.",
            facts=[card.flags[0]], related=[]))
    return out


def _plan_actions(plan: ProductionPlan | None) -> list[dict]:
    if plan is None:
        return []
    out: list[dict] = []
    b, o = plan.baseline, plan.optimized
    out.append(dict(
        department="Operations", priority="HIGH", rule="approve_replan",
        title="Approve the re-planned 13-week production schedule",
        reason=(f"The optimized plan builds {o.built_units:,.0f} of {o.demand_units:,.0f} units "
                f"({_pct(o.fill_rate)} fill rate) versus {_pct(b.fill_rate)} in the current schedule, and fills "
                f"{_pct(o.affected_fill_rate)} of affected-product demand versus {_pct(b.affected_fill_rate)}. "
                f"Gross margin is {_usd(o.gross_margin)} versus {_usd(b.gross_margin)}."),
        facts=[f"Fill rate: {_pct(o.fill_rate)} vs {_pct(b.fill_rate)}",
               f"Gross margin: {_usd(o.gross_margin)} vs {_usd(b.gross_margin)}"],
        related=[]))
    moves = [ch for ch in plan.changes if ch.kind == "MOVE_LINE"]
    if moves:
        units = sum(ch.units for ch in moves)
        out.append(dict(department="Operations", priority="MEDIUM", rule="rebalance_lines",
                        title=f"Rebalance {units:,.0f} units across production lines",
                        reason=" ".join(ch.description for ch in moves),
                        facts=[f"Units moved: {units:,.0f}"],
                        related=sorted({p for ch in moves for p in ch.product_ids})))
    for ch in plan.changes:
        if ch.kind == "BRIDGE_BUY":
            out.append(dict(department="Procurement", priority="HIGH", rule="bridge_buy",
                            title=f"Place a bridge buy of {ch.units:,.0f} units with full traceability",
                            reason=(f"{ch.description} The broker premium is {_usd(o.bridge_premium)}; require "
                                    "traceability documents and incoming inspection."),
                            facts=[f"Bridge buy: {ch.units:,.0f} units", f"Premium: {_usd(o.bridge_premium)}"],
                            related=[]))
    switch = [ch for ch in plan.changes if ch.kind == "SWITCH_COMPONENT"]
    if switch:
        units = sum(ch.units for ch in switch)
        products = sorted({p for ch in switch for p in ch.product_ids})
        out.append(dict(
            department="Operations", priority="MEDIUM", rule="switch_schedule",
            title=f"Schedule the switch to {plan.inputs.alternative_part_id} by product",
            reason=(f"Build {units:,.0f} units of {len(products)} products with {plan.inputs.alternative_part_id} "
                    f"as approvals allow: " + " ".join(ch.description for ch in switch[:3])),
            facts=[f"Units on alternative: {units:,.0f}"], related=products))
    return out


def deterministic_summary(analysis: ImpactAnalysis, scenario: ScenarioResult) -> str:
    s = analysis.summary
    return (f"{analysis.component.part_id} affects {s.affected_product_count} products and "
            f"{_usd(s.revenue_exposure)} of forecast revenue, with inventory covering {int(s.inventory_coverage_days)} "
            f"days. In the {scenario.name} scenario, {scenario.summary.products_below_margin_threshold} products fall "
            f"below the {_pct0(scenario.inputs.margin_threshold)} target margin.")


def build_plan(event: ChangeEventOut, analysis: ImpactAnalysis, scenario: ScenarioResult,
               assessment: SupplierAssessment | None = None, plan: ProductionPlan | None = None,
               rewrite: bool = True) -> ActionPlan:
    actions = candidate_actions(event, analysis, scenario, assessment, plan)
    summary = deterministic_summary(analysis, scenario)
    facts = {"analysis_summary": analysis.summary.model_dump(), "scenario": scenario.name,
             "scenario_summary": scenario.summary.model_dump(),
             "candidates": [a.model_dump(include={"action_id", "department", "priority", "title", "reason", "facts"})
                            for a in actions]}
    pool = collect_numbers(facts) | collect_numbers([a.reason for a in actions])
    method, model = "deterministic", None
    settings = get_settings()
    if rewrite and settings.gemini_configured:
        try:
            result = generate_structured(prompts.ACTION_PLAN, ["FACTS (JSON):\n" + json.dumps(facts, default=str)],
                                          PlanRewrite, purpose="generate_action_plan",
                                          prompt_version=prompts.ACTION_PLAN_VERSION)
            by_id = {r.id: r for r in result.actions}
            accepted = 0
            for i, a in enumerate(actions):
                r = by_id.get(a.action_id)
                if r and not unverified_numbers(r.title + " " + r.reason, pool):
                    actions[i] = a.model_copy(update={"title": r.title.strip(), "reason": r.reason.strip()})
                    accepted += 1
            if not unverified_numbers(result.summary, pool):
                summary = result.summary.strip()
            if accepted:
                method, model = "gemini", settings.gemini_model
            log.info("action_plan_rewrite", extra={"accepted": accepted, "total": len(actions)})
        except GeminiUnavailable:
            pass
    unverified = unverified_numbers(summary + " " + " ".join(a.reason for a in actions), pool)
    return ActionPlan(
        event_id=event.event_id, scenario_id=scenario.scenario_id, scenario_name=scenario.name, summary=summary,
        method=method, model=model, generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        grounding=Grounding(verified=not unverified, unverified_values=unverified), actions=actions,
    )
