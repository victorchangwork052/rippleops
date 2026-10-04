"""Recommended cross-functional response."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import repo, settings, store
from app.api.routes_ai import tool_session
from app.config import Settings
from app.db.repository import Repository
from app.models.actions import Action, ActionPlan, ActionsSummary, ActionUpdate, GenerateActionsRequest
from app.models.scenario import ScenarioRequest
from app.observability import Timer
from app.services.actions import build_plan
from app.services.scenario import run_scenario
from app.services.store import DemoStore

router = APIRouter(prefix="/api")


@router.post("/actions/generate", response_model=ActionPlan)
def generate_actions(body: GenerateActionsRequest, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
                     cfg: Settings = Depends(settings)):
    session = tool_session(body.event_id, st, rp, cfg)
    if body.scenario_id:
        scenario = st.get_scenario(body.scenario_id)
    else:
        history = st.list_scenarios(body.event_id)
        if history:
            scenario = history[0]
        else:
            # No scenario yet: plan against the recommended replacement.
            req = ScenarioRequest(event_id=body.event_id,
                                  replacement_part_id=session.analysis.summary.replacement_part_id,
                                  margin_threshold=session.analysis.summary.margin_threshold)
            scenario = run_scenario(rp, session.analysis.component.part_id, req, cfg.demand_horizon_months)
            st.save_scenario(scenario)
    with Timer("tool", tool="generate_action_plan", scenario_id=scenario.scenario_id):
        plan = build_plan(session.event, session.analysis, scenario)
    st.save_plan(plan)
    return plan


@router.get("/actions/summary", response_model=ActionsSummary)
def actions_summary(st: DemoStore = Depends(store)):
    actions = st.all_actions()
    by_status: dict[str, int] = {}
    for a in actions:
        by_status[a.status] = by_status.get(a.status, 0) + 1
    return ActionsSummary(total=len(actions), open=sum(a.status != "DONE" for a in actions), by_status=by_status)


@router.get("/actions", response_model=ActionPlan | None)
def get_actions(event_id: str, st: DemoStore = Depends(store)):
    """The event's current plan, or null when none has been generated yet."""
    st.get_event(event_id)  # 404 only for unknown events
    return st.action_plans.get(event_id)


@router.patch("/actions/{action_id}", response_model=Action)
def update_action(action_id: str, body: ActionUpdate, st: DemoStore = Depends(store)):
    return st.update_action(action_id, body)
