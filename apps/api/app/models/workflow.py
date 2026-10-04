from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

StepType = Literal["run_started", "agent_started", "tool_call", "tool_result", "agent_finished", "run_finished",
                   "error"]


class AgentNode(BaseModel):
    name: str
    label: str
    kind: Literal["sequential", "parallel", "llm"]
    description: str
    tools: list[str] = []
    children: list[AgentNode] = []


class AgentStep(BaseModel):
    seq: int
    type: StepType
    agent: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None
    summary: str | None = None
    text: str | None = None
    at_ms: int


class AgentFinding(BaseModel):
    agent: str
    label: str
    text: str
    method: Literal["adk_gemini", "deterministic"]
    grounded: bool
    unverified_values: list[str]


class WorkflowRun(BaseModel):
    run_id: str
    event_id: str
    mode: Literal["adk_gemini", "deterministic"]
    model: str | None
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    tree: AgentNode
    steps: list[AgentStep]
    findings: list[AgentFinding]
    analysis_id: str | None = None
    proposed_plan_id: str | None = None
    notice: str | None = None
    error: str | None = None


class WorkflowRequest(BaseModel):
    event_id: str
