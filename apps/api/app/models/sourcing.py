from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceType = Literal["INTERNAL_AVL", "DISTRIBUTOR_CATALOG"]
Channel = Literal["MANUFACTURER", "AUTHORIZED", "BROKER", "FACTORY_DIRECT"]
Tier = Literal["PREFERRED", "VIABLE", "BRIDGE_ONLY", "NOT_RECOMMENDED", "BLOCKED"]


class SourcingCandidate(BaseModel):
    candidate_id: str
    part_id: str
    manufacturer: str
    supplier_id: str
    supplier_name: str
    country: str
    source: SourceType
    channel: Channel
    match_type: str  # SAME_PART | DIRECT_SUCCESSOR | FUNCTIONAL_EQUIVALENT | PIN_TO_PIN_CLONE
    pin_compatible: bool
    is_new_supplier: bool
    approval_status: str  # APPROVED | VALIDATION_REQUIRED | NOT_APPROVED | NOT_QUALIFIED
    products_approved: int
    products_needing_validation: list[str]
    qualification_lead_time_days: int
    unit_price: float
    price_delta_pct: float  # vs. the affected part's current price
    lead_time_days: int
    available_stock: int | None
    notes: str


class SourcingResult(BaseModel):
    event_id: str | None
    part_id: str
    part_name: str
    current_supplier: str | None
    current_unit_price: float
    affected_products: int
    catalog_provider: str
    candidates: list[SourcingCandidate]


class ScoreComponent(BaseModel):
    criterion: str
    weight: float
    score: float
    evidence: str


class SanctionsHit(BaseModel):
    entity_id: str
    listed_name: str
    list_name: str
    program: str
    listed_on: str


class NewsItem(BaseModel):
    date: str
    category: str
    severity: str
    source: str
    headline: str
    summary: str


class PerformanceSnapshot(BaseModel):
    quarters: int
    on_time_delivery_rate: float
    quality_ppm: float
    avg_lead_time_days: float
    lead_time_variance_days: float
    on_time_trend_points: float  # latest quarter minus first quarter, in percentage points


class SupplierEvidence(BaseModel):
    supplier_id: str
    supplier_name: str
    performance: PerformanceSnapshot | None
    sanctions_screened: bool
    sanctions_hits: list[SanctionsHit]
    news: list[NewsItem]


class Scorecard(BaseModel):
    candidate_id: str
    part_id: str
    supplier_name: str
    total_score: float
    tier: Tier
    components: list[ScoreComponent]
    flags: list[str]


class SupplierAssessment(BaseModel):
    event_id: str | None
    part_id: str
    weights: dict[str, float]
    evidence: list[SupplierEvidence]
    scorecards: list[Scorecard]
    recommended_candidate_id: str | None  # fastest approved transition
    second_source_candidate_id: str | None  # best-scoring long-term second source
    bridge_candidate_id: str | None  # same part from a broker, to bridge the gap
    blocked_candidate_ids: list[str]
    providers: dict[str, str]
