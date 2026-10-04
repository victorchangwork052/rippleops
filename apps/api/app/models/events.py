from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "COMPONENT_EOL", "SUPPLIER_PRICE_INCREASE", "MATERIAL_PRICE_CHANGE", "FREIGHT_CHANGE", "OTHER"
]
EventSource = Literal["seed", "demo", "upload", "manual"]
EventStatus = Literal["NEW", "ANALYZED", "MONITORING"]

# Event types that are traced through the BOM from a single component.
COMPONENT_EVENTS = {"COMPONENT_EOL", "SUPPLIER_PRICE_INCREASE"}


class EventCreate(BaseModel):
    event_type: EventType = "COMPONENT_EOL"
    supplier_name: str | None = Field(default=None, max_length=120)
    part_id: str = Field(min_length=1, max_length=64)
    last_time_buy_date: date | None = None
    last_ship_date: date | None = None
    recommended_alternative_part_id: str | None = Field(default=None, max_length=64)
    source: EventSource = "manual"
    source_document_name: str | None = Field(default=None, max_length=200)
    extraction_method: str | None = None


class ChangeEventOut(BaseModel):
    event_id: str
    event_type: EventType
    title: str
    summary: str
    supplier_id: str | None
    supplier_name: str | None
    affected_item_id: str | None
    affected_item_name: str | None
    event_date: date
    last_time_buy_date: date | None
    last_ship_date: date | None
    recommended_alternative_item_id: str | None
    source: EventSource
    source_document_name: str | None
    extraction_method: str | None
    status: EventStatus
    created_at: str
    analyzable: bool
    latest_analysis_id: str | None = None
    latest_scenario_id: str | None = None
