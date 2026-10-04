"""RippleOps orchestrator: one Google ADK agent plus deterministic tools.

Gemini understands the question, picks tools and explains their structured
output. Numbers in the answer are checked against the tool outputs; if Gemini
is unavailable the deterministic answerer takes over.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from app.agents import fallback
from app.ai import prompts
from app.ai.gemini import GeminiUnavailable
from app.ai.grounding import collect_numbers, unverified_numbers
from app.config import get_settings
from app.models.assistant import AssistantAnswer, Grounding, ToolCall
from app.observability import Timer
from app.tools.registry import ToolSession, build_tools

log = logging.getLogger("rippleops.agent")
APP_NAME = "rippleops"
TIMEOUT_S = 45
_session_service = None


def _sessions():
    global _session_service
    if _session_service is None:
        from google.adk.sessions import InMemorySessionService

        _session_service = InMemorySessionService()
    return _session_service


def _configure_adk_env() -> None:
    """ADK builds its own GenAI client from environment variables."""
    s = get_settings()
    if s.gemini_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", s.gemini_api_key)
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
    else:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", s.google_cloud_project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", s.google_cloud_location)


def event_context(session: ToolSession, product_id: str | None) -> dict:
    ev, a = session.event, session.analysis
    return {
        "event_id": ev.event_id, "event_type": ev.event_type, "component": a.component.part_id,
        "component_name": a.component.name, "supplier": a.component.supplier_name,
        "last_time_buy_date": str(ev.last_time_buy_date) if ev.last_time_buy_date else None,
        "last_ship_date": str(ev.last_ship_date) if ev.last_ship_date else None,
        "recommended_replacement": ev.recommended_alternative_item_id,
        "affected_products": [p.product_id for p in a.products],
        "product_in_view": product_id,
        "shipping_lanes": [lane.shipping_lane_id for lane in session.repo.index().snapshot.shipping_lanes],
        "demand_horizon_months": a.summary.horizon_months,
    }


async def _run_agent(session: ToolSession, question: str, session_id: str, context: dict) -> str:
    from google.adk.agents import LlmAgent
    from google.adk.runners import Runner
    from google.genai import types

    _configure_adk_env()
    agent = LlmAgent(
        name="rippleops_orchestrator",
        model=get_settings().gemini_model,
        description="Explains change impact using deterministic BOM, cost and scenario tools.",
        instruction=prompts.ASSISTANT + "\nCurrent context (JSON):\n" + json.dumps(context),
        tools=build_tools(session),
        generate_content_config=types.GenerateContentConfig(temperature=0.1),
    )
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=_sessions(), auto_create_session=True)
    message = types.Content(role="user", parts=[types.Part(text=question)])
    final = ""
    async for event in runner.run_async(user_id="demo-user", session_id=session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            final = "".join(p.text or "" for p in event.content.parts if getattr(p, "text", None))
    if not final.strip():
        raise GeminiUnavailable("Empty agent response")
    return final.strip()


async def ask(session: ToolSession, question: str, session_id: str, product_id: str | None) -> AssistantAnswer:
    settings = get_settings()
    context = event_context(session, product_id)
    method, model, notice = "deterministic", None, None
    text = ""
    if settings.gemini_configured:
        try:
            with Timer("agent_run", prompt_version=prompts.ASSISTANT_VERSION, model=settings.gemini_model):
                text = await asyncio.wait_for(
                    _run_agent(session, question, f"{session_id}-{session.event.event_id}", context), TIMEOUT_S)
            method, model = "adk_gemini", settings.gemini_model
        except Exception as exc:  # noqa: BLE001 - any agent failure falls back
            log.warning("agent_failed", extra={"error_category": type(exc).__name__, "detail": str(exc)[:300]})
            notice = "Gemini is unavailable, so this answer was assembled from the calculated results."
            session.calls.clear()
            session.outputs.clear()
    else:
        notice = "Gemini is not configured, so this answer was assembled from the calculated results."
    if method == "deterministic":
        text = fallback.answer(session, question, product_id)

    pool = collect_numbers(session.outputs) | collect_numbers(context)
    unverified = unverified_numbers(text, pool)
    if unverified and method == "adk_gemini":
        log.warning("ungrounded_answer", extra={"values": unverified})
    return AssistantAnswer(
        answer=text, method=method, model=model,
        tool_calls=[ToolCall(**c) for c in session.calls],
        scenario_id=session.scenario_ids[-1] if session.scenario_ids else None,
        grounding=Grounding(verified=not unverified, unverified_values=unverified), notice=notice,
    )
