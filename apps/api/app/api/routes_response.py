"""Sourcing, production planning and the multi-agent change-response workflow."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents import workflow
from app.api.deps import UserFacingError, repo, settings, store
from app.config import Settings
from app.db.repository import Repository
from app.models.actions import ActionUpdate
from app.models.planning import DemandForecast, MaterialPlan, PlanDecision, ProductionPlan
from app.models.sourcing import SourcingResult, SupplierAssessment
from app.models.workflow import AgentNode, WorkflowRequest, WorkflowRun
from app.services.planning import PlanningInputError
from app.services.response import EventContext
from app.services.store import DemoStore

router = APIRouter(prefix="/api")


def event_context(event_id: str, st: DemoStore, rp: Repository, cfg: Settings) -> EventContext:
    ev = st.get_event(event_id)
    if not ev.analyzable or not ev.affected_item_id:
        raise UserFacingError("This event is not linked to a single component, so sourcing and production "
                              "planning are not available for it.", code="not_analyzable")
    return EventContext(rp, st, cfg, ev)


# -- sourcing ---------------------------------------------------------------------


class SourcingView(BaseModel):
    sourcing: SourcingResult
    assessment: SupplierAssessment


@router.get("/sourcing/{event_id}", response_model=SourcingView)
def get_sourcing(event_id: str, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
                 cfg: Settings = Depends(settings)):
    ctx = event_context(event_id, st, rp, cfg)
    return SourcingView(sourcing=ctx.sourcing(), assessment=ctx.cached_assessment())


# -- planning ---------------------------------------------------------------------


class PlanningView(BaseModel):
    forecast: DemandForecast
    materials: MaterialPlan
    plans: list[ProductionPlan]
    proposed_plan_id: str | None


class OptimizeRequest(BaseModel):
    bridge_buy_qty: int = Field(default=0, ge=0, le=100_000)


def _planning_view(ctx: EventContext) -> PlanningView:
    if not ctx.store.event_plans(ctx.event_id):
        ctx.optimize(0)
    proposed = ctx.proposed_plan()
    return PlanningView(forecast=ctx.forecast(), materials=ctx.materials(),
                        plans=sorted(ctx.store.event_plans(ctx.event_id), key=lambda p: p.plan_id),
                        proposed_plan_id=proposed.plan_id if proposed else None)


@router.get("/planning/{event_id}", response_model=PlanningView)
def get_planning(event_id: str, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
                 cfg: Settings = Depends(settings)):
    return _planning_view(event_context(event_id, st, rp, cfg))


@router.post("/planning/{event_id}/optimize", response_model=ProductionPlan)
def optimize(event_id: str, body: OptimizeRequest, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
             cfg: Settings = Depends(settings)):
    try:
        return event_context(event_id, st, rp, cfg).optimize(body.bridge_buy_qty)
    except PlanningInputError as exc:
        raise UserFacingError(str(exc), code="invalid_plan") from exc


@router.post("/planning/plans/{plan_id}/propose", response_model=ProductionPlan)
def propose(plan_id: str, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
            cfg: Settings = Depends(settings)):
    plan = st.get_production_plan(plan_id)
    return event_context(plan.event_id or "", st, rp, cfg).propose(plan_id, "Proposed from the planning page.")


@router.post("/planning/plans/{plan_id}/decision", response_model=ProductionPlan)
def decide(plan_id: str, body: PlanDecision, st: DemoStore = Depends(store)):
    """Human-in-the-loop: the Operations Manager approves or rejects a proposed plan."""
    plan = st.get_production_plan(plan_id)
    if plan.status not in ("PROPOSED", "APPROVED", "REJECTED"):
        raise UserFacingError("Only a proposed plan can be approved or rejected.", code="not_proposed")
    plan = st.set_plan_status(plan_id, status=body.decision, decided_by=body.decided_by,
                              decided_at=datetime.now(UTC).isoformat(timespec="seconds"))
    if body.decision == "APPROVED" and plan.event_id in st.action_plans:
        for action in st.action_plans[plan.event_id].actions:
            if action.rule == "approve_replan":
                st.update_action(action.action_id, ActionUpdate(status="DONE"))
    return plan


# -- multi-agent workflow ----------------------------------------------------------


@router.get("/workflow/tree", response_model=AgentNode)
def workflow_tree():
    return workflow.agent_tree()


@router.get("/workflow/{event_id}", response_model=WorkflowRun | None)
def get_workflow(event_id: str, st: DemoStore = Depends(store)):
    st.get_event(event_id)
    return st.workflow_runs.get(event_id)


@router.post("/workflow/run")
async def run_workflow(body: WorkflowRequest, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
                       cfg: Settings = Depends(settings)):
    """Run the agents and stream every step as server-sent events.

    The run keeps going if the client disconnects; its result stays available
    from GET /api/workflow/{event_id}.
    """
    ctx = event_context(body.event_id, st, rp, cfg)
    run = workflow.new_run(ctx)
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(workflow.execute(ctx, run, queue))

    async def stream():
        yield f"event: run\ndata: {run.model_dump_json(include={'run_id', 'event_id', 'mode', 'model', 'tree'})}\n\n"
        while True:
            step = await queue.get()
            if step is None:
                break
            yield f"event: step\ndata: {step.model_dump_json()}\n\n"
        await task
        yield f"event: done\ndata: {run.model_dump_json(exclude={'steps', 'tree'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
