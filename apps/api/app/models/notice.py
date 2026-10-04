from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.events import EventSource, EventType


class NoticeExtraction(BaseModel):
    """Schema Gemini must fill for a supplier notice."""

    event_type: Literal["COMPONENT_EOL", "SUPPLIER_PRICE_INCREASE", "OTHER"]
    supplier_name: str | None = None
    part_id: str | None = None
    last_time_buy_date: str | None = Field(default=None, description="YYYY-MM-DD")
    last_ship_date: str | None = Field(default=None, description="YYYY-MM-DD")
    recommended_alternative_part_id: str | None = None
    reason: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ParseRequest(BaseModel):
    document_text: str = Field(min_length=1, max_length=50_000)
    document_name: str | None = Field(default=None, max_length=200)


class NoticeValidation(BaseModel):
    part_found: bool
    part_name: str | None
    part_status: str | None
    supplier_name: str | None  # supplier on record for the part
    supplier_matches: bool
    alternative_found: bool
    alternative_name: str | None
    warnings: list[str]


class ExtractedFields(BaseModel):
    """Same shape as EventCreate, but every field may still be empty for the user to fill."""

    event_type: EventType = "COMPONENT_EOL"
    supplier_name: str | None = None
    part_id: str = ""
    last_time_buy_date: date | None = None
    last_ship_date: date | None = None
    recommended_alternative_part_id: str | None = None
    source: EventSource = "upload"
    source_document_name: str | None = None
    extraction_method: str | None = None


class ParsedNotice(BaseModel):
    fields: ExtractedFields
    reason: str | None
    confidence: float | None
    extraction_method: Literal["gemini", "rules"]
    model: str | None
    fallback_reason: str | None
    document_name: str | None
    validation: NoticeValidation
