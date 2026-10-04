from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    event_id: str
    question: str = Field(min_length=1, max_length=1000)
    session_id: str = Field(default="default", max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    product_id: str | None = Field(default=None, description="Product the user is currently viewing, if any.")


class ToolCall(BaseModel):
    name: str
    args: dict


class Grounding(BaseModel):
    verified: bool
    unverified_values: list[str]


class AssistantAnswer(BaseModel):
    answer: str
    method: Literal["adk_gemini", "deterministic"]
    model: str | None
    tool_calls: list[ToolCall]
    scenario_id: str | None
    grounding: Grounding
    notice: str | None = None


class ExplainRequest(BaseModel):
    product_id: str | None = None


class Explanation(BaseModel):
    text: str
    method: Literal["gemini", "deterministic"]
    model: str | None
    grounding: Grounding
