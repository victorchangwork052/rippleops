from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.assistant import Grounding

Department = Literal["Procurement", "Engineering", "Operations", "Finance", "Sales / Product"]
Priority = Literal["HIGH", "MEDIUM", "LOW"]
ActionStatus = Literal["PROPOSED", "ACCEPTED", "IN_PROGRESS", "DONE"]


class Action(BaseModel):
    action_id: str
    event_id: str
    department: Department
    priority: Priority
    title: str
    reason: str
    facts: list[str]  # the calculated facts this action is grounded in
    related_products: list[str]
    owner: str
    status: ActionStatus = "PROPOSED"
    rule: str  # which deterministic rule produced the action


class ActionPlan(BaseModel):
    event_id: str
    scenario_id: str | None
    scenario_name: str
    summary: str
    method: Literal["gemini", "deterministic"]
    model: str | None
    generated_at: str
    grounding: Grounding
    actions: list[Action]


class GenerateActionsRequest(BaseModel):
    event_id: str
    scenario_id: str | None = None


class ActionUpdate(BaseModel):
    status: ActionStatus | None = None
    owner: str | None = Field(default=None, min_length=1, max_length=80)


class ActionsSummary(BaseModel):
    total: int
    open: int
    by_status: dict[str, int]


# Schema Gemini fills when rewriting the rule-based candidates.
class ActionRewrite(BaseModel):
    id: str
    title: str
    reason: str


class PlanRewrite(BaseModel):
    summary: str
    actions: list[ActionRewrite]
