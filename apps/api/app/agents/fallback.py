"""Deterministic answers used when Gemini is unavailable.

They call the same tools as the agent and fill fixed English templates, so the
demo keeps working (and stays grounded) without any external AI call.
"""

from __future__ import annotations

import re

from app.tools.registry import ToolSession, build_tools

MATERIALS = ("COPPER", "ALUMINUM", "STEEL", "RESIN", "TIN")


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def explain_product(row: dict, trace: dict, part: str, include_reasons: bool = True) -> str:
    paths = trace["paths"]
    via = "; ".join(" → ".join(p["nodes"]) + f" (qty {p['path_qty']:g})" for p in paths)
    text = (f"{row['product_id']} {row['name']} uses {row['effective_component_qty']:g} {part} units per product "
            f"through {len(paths)} BOM path{'s' if len(paths) != 1 else ''}: {via}. "
            f"It currently earns a {_pct(row['gross_margin'])} gross margin and inventory covers "
            f"{row['inventory_coverage_days']} days.")
    if row.get("replacement_margin") is not None and row.get("replacement_part"):
        text += (f" Switching to {row['replacement_part']} adds ${row['replacement_unit_cost_delta']:.2f} per unit "
                 f"and moves the margin to {_pct(row['replacement_margin'])}.")
    if row["alternative_approval"] != "APPROVED" and row.get("replacement_part"):
        text += (f" {row['replacement_part']} is not yet approved for this product"
                 f" ({row.get('qualification_lead_time_days') or 0}-day qualification).")
    if include_reasons:
        text += f" Risk is {row['risk_level'].title()}: " + " ".join(row["risk_reasons"])
    return text


def answer(session: ToolSession, question: str, product_hint: str | None) -> str:
    tools = {f.__name__: f for f in build_tools(session)}
    part = session.analysis.component.part_id
    q = question.upper()
    product = re.search(r"\bP\d{3}\b", q)
    pid = product.group(0) if product else None
    pcts = [float(x) / 100 for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", question)]

    what_if = any(k in q for k in ("WHAT IF", "WHAT HAPPENS", "INCREASE", "RISE", "REPLACE", "SCENARIO", "FREIGHT"))
    if what_if and (pcts or "REPLACE" in q):
        material = next((m for m in MATERIALS if m in q), "")
        freight = "FREIGHT" in q or "SHIPPING" in q
        alt = next((a.part_id for a in session.analysis.alternatives if a.part_id in q), "")
        if not alt and "REPLACE" in q:
            alt = next((a.part_id for a in session.analysis.alternatives if a.recommended), "")
        m_pct = pcts[0] if material and pcts else 0.0
        f_pct = (pcts[1] if material and len(pcts) > 1 else pcts[0] if pcts else 0.0) if freight else 0.0
        r = tools["run_scenario"](replacement_part_id=alt, material_code=material, material_change=m_pct,
                                  shipping_lane_id="TW-US-OCEAN" if freight else "", freight_change=f_pct)
        if "error" in r:
            return r["error"]
        s = r["summary"]
        below = [p["product_id"] for p in r["products"] if p["below_threshold"]]
        return (f"Scenario: {r['scenario']}. Average unit cost changes by ${s['average_unit_cost_delta']:.2f} and "
                f"average gross margin by {s['average_margin_delta_points']:.2f} pts "
                f"({_pct(s['average_current_margin'])} to {_pct(s['average_scenario_margin'])}). "
                f"{s['products_below_margin_threshold']} products fall below the target"
                + (f": {', '.join(below)}." if below else "."))

    if pid or (product_hint and any(k in q for k in ("WHY", "RISK", "THIS PRODUCT"))):
        pid = pid or product_hint
        row = tools["get_product_impact"](product_id=pid)
        if not row.get("found"):
            return row.get("message", f"{pid} does not use {part}.")
        return explain_product(row, tools["trace_bom_impact"](product_id=pid), part)

    if "ACTION" in q or "PRIORIT" in q:
        plan = tools["get_action_plan"]()
        if not plan["generated"]:
            return "No action plan has been generated yet. Open Actions and select Generate Response."
        top = [a for a in plan["actions"] if a["priority"] == "HIGH"][:4] or plan["actions"][:4]
        return "Prioritize: " + " ".join(f"{a['department']}: {a['title']}." for a in top)

    impact = tools["calculate_business_impact"]()
    s = impact["summary"]
    ranked = sorted(impact["products"], key=lambda p: (p["risk_level"] != "HIGH", -p["effective_component_qty"]))[:3]
    return (f"{part} affects {s['affected_products']} products with ${s['revenue_exposure_6m']:,.0f} of forecast "
            f"revenue over the next 6 months. Inventory covers {s['inventory_coverage_days']} days. The most exposed "
            "products are " + ", ".join(f"{p['product_id']} ({p['effective_component_qty']:g} units, "
                                        f"{_pct(p['gross_margin'])} margin)" for p in ranked) + ".")
