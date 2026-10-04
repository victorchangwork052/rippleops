"""Gemini explanations of calculated impact, with a deterministic fallback."""

from __future__ import annotations

import json
import logging

from app.agents import fallback
from app.ai import prompts
from app.ai.gemini import GeminiUnavailable, generate_text
from app.ai.grounding import collect_numbers, unverified_numbers
from app.config import get_settings
from app.models.assistant import Explanation, Grounding
from app.tools.registry import ToolSession, build_tools

log = logging.getLogger("rippleops.explain")


def explain(session: ToolSession, product_id: str | None) -> Explanation:
    tools = {f.__name__: f for f in build_tools(session)}
    part = session.analysis.component.part_id
    if product_id:
        row = tools["get_product_impact"](product_id=product_id)
        trace = tools["trace_bom_impact"](product_id=product_id)
        facts = {"product": row, "bom_trace": trace, "margin_threshold": session.analysis.summary.margin_threshold}
        ask = (f"Explain in 3-4 sentences why {product_id} is at {row.get('risk_level', 'this')} risk from the "
               f"{part} change, referring to its BOM paths, effective quantity, margin and inventory coverage.")
        # The panel already lists the risk reasons, so the explanation focuses on the "why".
        deterministic = (fallback.explain_product(row, trace, part, include_reasons=False) if row.get("found")
                         else row.get("message", ""))
    else:
        facts = tools["calculate_business_impact"]()
        ask = f"Summarize the business impact of the {part} change in 3-4 sentences for a cross-functional audience."
        deterministic = fallback.answer(session, "summary", None)

    pool = collect_numbers(session.outputs)
    if get_settings().gemini_configured:
        try:
            text = generate_text(prompts.IMPACT_EXPLANATION, [ask, "FACTS (JSON):\n" + json.dumps(facts)],
                                 purpose="explain_impact", prompt_version=prompts.IMPACT_EXPLANATION_VERSION)
            unverified = unverified_numbers(text, pool)
            if not unverified:
                return Explanation(text=text, method="gemini", model=get_settings().gemini_model,
                                   grounding=Grounding(verified=True, unverified_values=[]))
            # Guardrail: never show an explanation with figures we cannot trace.
            log.warning("explanation_ungrounded", extra={"values": unverified})
        except GeminiUnavailable:
            pass
    return Explanation(text=deterministic, method="deterministic", model=None,
                       grounding=Grounding(verified=not unverified_numbers(deterministic, pool),
                                           unverified_values=unverified_numbers(deterministic, pool)))
