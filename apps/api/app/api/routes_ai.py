"""AI endpoints: context-aware assistant and grounded explanations."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agents.orchestrator import ask
from app.api.deps import repo, settings, store
from app.api.routes_core import analyze_event
from app.config import Settings
from app.db.repository import Repository
from app.models.assistant import AskRequest, AssistantAnswer, ExplainRequest, Explanation
from app.services.explain import explain
from app.services.store import DemoStore, NotFoundError
from app.tools.registry import ToolSession

router = APIRouter(prefix="/api")


def tool_session(event_id: str, st: DemoStore, rp: Repository, cfg: Settings) -> ToolSession:
    event = st.get_event(event_id)
    try:
        analysis = st.get_analysis(event_id)
    except NotFoundError:
        analysis = analyze_event(st, rp, cfg, event_id)
    return ToolSession(repo=rp, store=st, settings=cfg, event=event, analysis=analysis)


@router.post("/assistant/ask", response_model=AssistantAnswer)
async def assistant_ask(body: AskRequest, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
                        cfg: Settings = Depends(settings)):
    session = tool_session(body.event_id, st, rp, cfg)
    return await ask(session, body.question.strip(), body.session_id, body.product_id)


@router.post("/impact/{event_id}/explain", response_model=Explanation)
def impact_explain(event_id: str, body: ExplainRequest, st: DemoStore = Depends(store),
                   rp: Repository = Depends(repo), cfg: Settings = Depends(settings)):
    session = tool_session(event_id, st, rp, cfg)
    return explain(session, body.product_id.strip().upper() if body.product_id else None)
