"""Change-response workflow: a Google ADK multi-agent system.

    change_response_workflow            SequentialAgent
    ├─ impact_analyst                   LlmAgent  (BOM trace + business impact)
    ├─ response_research                ParallelAgent
    │   ├─ sourcing_team                SequentialAgent
    │   │   ├─ sourcing_scout           LlmAgent  (approved vendors + distributor catalog)
    │   │   ├─ supplier_due_diligence   ParallelAgent
    │   │   │   ├─ performance_auditor  LlmAgent  (ERP / quality KPIs)
    │   │   │   ├─ compliance_screener  LlmAgent  (sanctions / export control)
    │   │   │   └─ risk_news_monitor    LlmAgent  (supplier news)
    │   │   └─ supplier_evaluator       LlmAgent  (weighted scorecards)
    │   └─ planning_team                SequentialAgent
    │       ├─ demand_planner           LlmAgent  (TimesFM forecast + material requirements)
    │       └─ production_planner       LlmAgent  (OR-Tools re-plan, proposes for approval)
    └─ response_coordinator             LlmAgent  (action plan + executive brief)

Agents choose and sequence deterministic tools and explain the results; the
numbers come from the tools. Agents share findings through session state
(`output_key` + `{key?}` instruction templating). ADK callbacks stream every
agent and tool step to the UI, and an `after_model_callback` replaces any
agent text that quotes a number no tool returned. The production plan is only
proposed; a person approves it. Without Gemini, the same tools run in the same
order and deterministic findings are written instead.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.agents.orchestrator import _configure_adk_env
from app.agents.workflow_tools import WorkflowTools, choose_plan, deterministic_finding
from app.ai.grounding import collect_numbers, unverified_numbers
from app.config import get_settings
from app.models.workflow import AgentFinding, AgentNode, AgentStep, WorkflowRun
from app.observability import Timer
from app.services.response import EventContext

log = logging.getLogger("rippleops.workflow")
APP_NAME = "rippleops_change_response"
PROMPT_VERSION = "change-response/v1"
TIMEOUT_S = 150
DETERMINISTIC_PACING_S = 0.25

# name: (label, description, tools, output_key)
AGENTS: dict[str, tuple[str, str, list[str], str | None]] = {
    "change_response_workflow": ("Change Response Workflow", "Coordinates the full response to a change event.", [],
                                 None),
    "impact_analyst": ("Impact Analyst", "Traces the BOM and quantifies the business impact.",
                       ["analyze_change_impact"], "impact_findings"),
    "response_research": ("Response Research", "Runs sourcing and planning in parallel.", [], None),
    "sourcing_team": ("Sourcing Team", "Finds and evaluates alternative sources.", [], None),
    "sourcing_scout": ("Sourcing Scout", "Searches approved vendors and the distributor catalog.",
                       ["find_sourcing_options"], "sourcing_options"),
    "supplier_due_diligence": ("Supplier Due Diligence", "Checks every candidate supplier in parallel.", [], None),
    "performance_auditor": ("Performance Auditor", "Reviews delivery, quality and lead-time history.",
                            ["get_supplier_performance"], "performance_findings"),
    "compliance_screener": ("Compliance Screener", "Screens suppliers against sanctions and export-control lists.",
                            ["screen_suppliers"], "compliance_findings"),
    "risk_news_monitor": ("Risk News Monitor", "Scans supplier news for capacity, quality and financial risk.",
                          ["search_supplier_news"], "news_findings"),
    "supplier_evaluator": ("Supplier Evaluator", "Scores the options and recommends a sourcing strategy.",
                           ["score_suppliers"], "sourcing_recommendation"),
    "planning_team": ("Planning Team", "Forecasts demand and re-plans production.", [], None),
    "demand_planner": ("Demand Planner", "Forecasts demand and finds when the component runs out.",
                       ["forecast_demand", "calculate_material_requirements"], "demand_findings"),
    "production_planner": ("Production Planner", "Re-plans lines and weeks with OR-Tools and proposes a plan.",
                           ["optimize_production_plan", "get_bridge_supply_options", "propose_production_plan"],
                           "production_findings"),
    "response_coordinator": ("Response Coordinator", "Builds the action plan and the executive brief.",
                             ["generate_action_plan"], "executive_brief"),
}

TREE = ("change_response_workflow", "sequential", [
    ("impact_analyst", "llm", []),
    ("response_research", "parallel", [
        ("sourcing_team", "sequential", [
            ("sourcing_scout", "llm", []),
            ("supplier_due_diligence", "parallel", [
                ("performance_auditor", "llm", []),
                ("compliance_screener", "llm", []),
                ("risk_news_monitor", "llm", []),
            ]),
            ("supplier_evaluator", "llm", []),
        ]),
        ("planning_team", "sequential", [
            ("demand_planner", "llm", []),
            ("production_planner", "llm", []),
        ]),
    ]),
    ("response_coordinator", "llm", []),
])

COMMON = """\
You are the {role} in RippleOps, an enterprise team of AI agents responding to a supply change.
Event: {event}

Rules:
- Get facts only by calling your tools. Never calculate, estimate or invent a number.
- Quote numbers exactly as the tools return them. Fractions such as 0.958 are percentages (95.8%).
- Write money of a million dollars or more as $X.XXM (for example $4.20M), other money in whole dollars.
- Write at most 60 words of plain business English: the conclusion first, then the key figures.
  No markdown, no lists, no headings, no restating of other agents' findings.
"""

INSTRUCTIONS = {
    "impact_analyst": "Call analyze_change_impact. Summarise the scale of the impact: products, families, "
                      "revenue exposure, inventory coverage and products without an approved alternative.",
    "sourcing_scout": "Call find_sourcing_options. Summarise the options by where they came from (approved-vendor "
                      "list or distributor catalog) and how they differ in approval, price change and lead time.",
    "performance_auditor": "Call get_supplier_performance. Point out the strongest and weakest delivery records, "
                           "any declining trend, and which suppliers have no history.",
    "compliance_screener": "Call screen_suppliers. State clearly which supplier, if any, must be excluded and why.",
    "risk_news_monitor": "Call search_supplier_news. Summarise only high- and medium-severity risks and what they "
                         "mean for sourcing.",
    "supplier_evaluator": "Call score_suppliers. Recommend the transition part, the long-term second source and "
                          "why, whether broker stock may be used only as a bridge, and which suppliers are blocked.\n"
                          "Team findings: performance: {performance_findings?} compliance: {compliance_findings?} "
                          "news: {news_findings?}",
    "demand_planner": "Call forecast_demand and calculate_material_requirements. Explain where the statistical "
                      "forecast differs most from the plan and in which week the component runs out.",
    "production_planner": "1) Call optimize_production_plan with bridge_buy_qty 0.\n"
                          "2) If unmet_products is not empty, call get_bridge_supply_options, then call "
                          "optimize_production_plan again with bridge_buy_qty set to suggested_bridge_qty (never more "
                          "than the broker's available_stock).\n"
                          "3) Compare the plans on affected_fill_rate, strategic_fill_rate, late_unit_weeks and "
                          "gross_margin (gross_margin already deducts the broker premium). Prefer the plan that fills "
                          "more demand unless its gross margin is lower.\n"
                          "4) Call propose_production_plan with the chosen plan_id and a one-sentence rationale.\n"
                          "5) Summarise the proposed plan against the current schedule and say it awaits approval.\n"
                          "Demand context: {demand_findings?}",
    "response_coordinator": "Call generate_action_plan. Then write an executive brief of at most 90 words (this "
                            "overrides the 60-word limit) that connects the team's findings and ends with the "
                            "decision that needs human approval.\n"
                            "Impact: {impact_findings?}\nSourcing: {sourcing_recommendation?}\n"
                            "Production: {production_findings?}",
}


def agent_tree(name: str = TREE[0], kind: str = TREE[1], children: list | None = None) -> AgentNode:
    children = TREE[2] if children is None else children
    label, desc, tools, _ = AGENTS[name]
    return AgentNode(name=name, label=label, kind=kind, description=desc, tools=tools,
                     children=[agent_tree(n, k, c) for n, k, c in children])


def _llm_order(node: tuple = TREE) -> list[str]:
    name, kind, children = node
    if kind == "llm":
        return [name]
    return [n for child in children for n in _llm_order(child)]


class Recorder:
    """Appends steps to the run and pushes them to the live stream."""

    def __init__(self, run: WorkflowRun, queue: asyncio.Queue | None) -> None:
        self.run = run
        self.queue = queue
        self._t0 = time.perf_counter()
        self.finished: set[str] = set()
        self.tool_outputs: list[Any] = []  # every tool result, for the grounding check

    def emit(self, type_: str, **kw: Any) -> AgentStep:
        step = AgentStep(seq=len(self.run.steps) + 1, type=type_,
                         at_ms=int((time.perf_counter() - self._t0) * 1000), **kw)
        self.run.steps.append(step)
        if self.queue is not None:
            self.queue.put_nowait(step)
        return step

    def finding(self, agent: str, text: str, method: str, unverified: list[str]) -> None:
        self.run.findings = [f for f in self.run.findings if f.agent != agent] + [AgentFinding(
            agent=agent, label=AGENTS[agent][0], text=text, method=method, grounded=not unverified,
            unverified_values=unverified)]

    def text_of(self, agent: str) -> str | None:
        return next((f.text for f in self.run.findings if f.agent == agent), None)


def _event_line(ctx: EventContext) -> str:
    ev = ctx.event
    alt = ctx.alternative()
    return (f"{ev.event_id}, {ev.title} ({ev.event_type}) from {ev.supplier_name or 'the supplier'}"
            + (f"; recommended replacement {alt}" if alt else "") + ".")


def _pool(ctx: EventContext, rec: Recorder) -> set[float]:
    plan_weeks = {float(len(p.weeks)) for p in ctx.store.event_plans(ctx.event_id)}
    return (collect_numbers(ctx.numbers_pool()) | collect_numbers(rec.tool_outputs) | plan_weeks
            | {float(ctx.settings.demand_horizon_months)})


# -- ADK ------------------------------------------------------------------------


def build_agents(ctx: EventContext, tools: WorkflowTools, rec: Recorder):
    from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
    from google.adk.models import LlmResponse
    from google.genai import types

    settings = get_settings()
    fns = tools.all()
    config = types.GenerateContentConfig(temperature=0.1, thinking_config=types.ThinkingConfig(thinking_budget=0))
    event = _event_line(ctx)

    def before_agent(callback_context):
        rec.emit("agent_started", agent=callback_context.agent_name)

    def after_agent(callback_context):
        name = callback_context.agent_name
        rec.finished.add(name)
        rec.emit("agent_finished", agent=name, text=rec.text_of(name))

    def before_tool(tool, args, tool_context):
        rec.emit("tool_call", agent=tool_context.agent_name, tool=tool.name, args=dict(args or {}))

    def after_tool(tool, args, tool_context, tool_response):
        rec.tool_outputs.append(tool_response)
        summary = tool_response.get("headline") if isinstance(tool_response, dict) else None
        rec.emit("tool_result", agent=tool_context.agent_name, tool=tool.name, summary=summary)

    def ground(callback_context, llm_response):
        """Guardrail: every number in an agent's final text must come from a tool output."""
        content = llm_response.content
        if not content or not content.parts or any(p.function_call for p in content.parts):
            return None
        text = "".join(p.text or "" for p in content.parts if not getattr(p, "thought", False)).strip()
        if not text:
            return None
        agent = callback_context.agent_name
        bad = unverified_numbers(text, _pool(ctx, rec))
        if not bad:
            rec.finding(agent, text, "adk_gemini", [])
            return None
        log.warning("ungrounded_agent_text", extra={"agent": agent, "values": bad})
        fallback = deterministic_finding(agent, ctx)
        rec.finding(agent, fallback, "deterministic", bad)
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=fallback)]))

    def llm(name: str) -> LlmAgent:
        label, desc, tool_names, output_key = AGENTS[name]
        return LlmAgent(
            name=name, model=settings.gemini_model, description=desc,
            instruction=COMMON.replace("{role}", label).replace("{event}", event) + "\n" + INSTRUCTIONS[name],
            tools=[fns[t] for t in tool_names], output_key=output_key, generate_content_config=config,
            disallow_transfer_to_parent=True, disallow_transfer_to_peers=True,
            before_agent_callback=before_agent, after_agent_callback=after_agent,
            before_tool_callback=before_tool, after_tool_callback=after_tool, after_model_callback=ground)

    def build(node: tuple):
        name, kind, children = node
        if kind == "llm":
            return llm(name)
        cls = SequentialAgent if kind == "sequential" else ParallelAgent
        return cls(name=name, description=AGENTS[name][1], sub_agents=[build(c) for c in children],
                   before_agent_callback=before_agent, after_agent_callback=after_agent)

    return build(TREE)


async def _run_adk(ctx: EventContext, tools: WorkflowTools, rec: Recorder) -> None:
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    _configure_adk_env()
    root = build_agents(ctx, tools, rec)
    runner = Runner(app=App(name=APP_NAME, root_agent=root), session_service=InMemorySessionService(),
                    auto_create_session=True)
    message = types.Content(role="user", parts=[types.Part(text=f"Respond to change event {ctx.event_id}.")])
    async for _ in runner.run_async(user_id="demo-user", session_id=rec.run.run_id, new_message=message):
        pass


# -- deterministic ----------------------------------------------------------------


async def _run_deterministic(ctx: EventContext, tools: WorkflowTools, rec: Recorder, only: set[str] | None) -> None:
    fns = tools.all()

    def call(agent: str) -> Callable[..., dict]:
        def run_tool(name: str, **args) -> dict:
            rec.emit("tool_call", agent=agent, tool=name, args=args)
            result = fns[name](**args)
            rec.tool_outputs.append(result)
            rec.emit("tool_result", agent=agent, tool=name, summary=result.get("headline"))
            return result
        return run_tool

    async def visit(node: tuple) -> None:
        name, kind, children = node
        if only is not None and kind == "llm" and name not in only:
            return
        rec.emit("agent_started", agent=name)
        if kind == "llm":
            run_tool = call(name)
            if name == "production_planner":
                plan_id, why = choose_plan(run_tool)
                run_tool("propose_production_plan", plan_id=plan_id, rationale=why)
            else:
                for tool in AGENTS[name][2]:
                    run_tool(tool)
            rec.finding(name, deterministic_finding(name, ctx), "deterministic", [])
            await asyncio.sleep(DETERMINISTIC_PACING_S)
        else:
            for child in children:
                await visit(child)
        rec.finished.add(name)
        rec.emit("agent_finished", agent=name, text=rec.text_of(name))

    await visit(TREE)


# -- entry point ----------------------------------------------------------------


def new_run(ctx: EventContext) -> WorkflowRun:
    settings = get_settings()
    run = WorkflowRun(
        run_id=ctx.store.next_run_id(), event_id=ctx.event_id,
        mode="adk_gemini" if settings.gemini_configured else "deterministic",
        model=settings.gemini_model if settings.gemini_configured else None, status="RUNNING",
        started_at=datetime.now(UTC).isoformat(timespec="seconds"), tree=agent_tree(), steps=[], findings=[])
    ctx.store.workflow_runs[ctx.event_id] = run
    return run


async def execute(ctx: EventContext, run: WorkflowRun, queue: asyncio.Queue | None = None) -> WorkflowRun:
    rec = Recorder(run, queue)
    tools = WorkflowTools(ctx)
    started = time.perf_counter()
    rec.emit("run_started", summary=run.mode)
    try:
        if run.mode == "adk_gemini":
            try:
                with Timer("workflow_run", prompt_version=PROMPT_VERSION, model=run.model):
                    await asyncio.wait_for(_run_adk(ctx, tools, rec), TIMEOUT_S)
            except Exception as exc:  # noqa: BLE001 - finish the remaining agents deterministically
                log.warning("workflow_adk_failed", extra={"error_category": type(exc).__name__,
                                                          "detail": str(exc)[:300]})
                remaining = {a for a in _llm_order() if a not in rec.finished}
                run.notice = ("Gemini was unavailable for part of this run, so "
                              f"{len(remaining)} agent(s) finished with deterministic findings.")
                if remaining:
                    await _run_deterministic(ctx, tools, rec, remaining)
        else:
            run.notice = "Gemini is not configured, so agents ran their tools with deterministic findings."
            await _run_deterministic(ctx, tools, rec, None)

        # The workflow must always end with a proposal and an action plan.
        if ctx.proposed_plan() is None:
            plan_id, why = choose_plan(lambda name, **args: tools.all()[name](**args))
            ctx.propose(plan_id, why)
        if ctx.event_id not in ctx.store.action_plans:
            ctx.action_plan()
        proposed = ctx.proposed_plan()
        run.proposed_plan_id = proposed.plan_id if proposed else None
        run.analysis_id = ctx.analysis().analysis_id
        run.status = "COMPLETED"
        rec.emit("run_finished", summary=run.proposed_plan_id)
    except Exception:  # noqa: BLE001 - surface a clean error to the UI
        log.exception("workflow_failed")
        run.status, run.error = "FAILED", "The response workflow could not finish. Please try again."
        rec.emit("error", summary=run.error)
    finally:
        run.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        if queue is not None:
            queue.put_nowait(None)
    return run
