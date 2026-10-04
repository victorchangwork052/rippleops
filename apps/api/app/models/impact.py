from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.models.bom import BomPath

RiskLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ApprovalStatus = Literal["APPROVED", "VALIDATION_REQUIRED", "NOT_APPROVED", "NONE"]


class CostBreakdownOut(BaseModel):
    purchase: float
    material: float
    freight: float
    processing: float
    total: float


class ComponentInfo(BaseModel):
    part_id: str
    name: str
    status: str
    supplier_id: str | None
    supplier_name: str | None
    unit_price: float | None
    unit_cost: float
    lead_time_days: int | None
    shipping_lane_id: str | None
    available_qty: float


class AlternativeApproval(BaseModel):
    part_id: str
    approval_status: ApprovalStatus
    qualification_lead_time_days: int
    notes: str


class ProductImpact(BaseModel):
    product_id: str
    name: str
    product_family: str
    effective_component_qty: float
    paths_to_component: int
    selling_price: float
    unit_cost: float
    current_margin: float
    cost_breakdown: CostBreakdownOut
    component_cost_share: float  # share of unit cost from the affected component
    horizon_forecast_qty: float
    horizon_open_order_qty: float
    revenue_exposure: float
    component_requirement: float  # component units needed over the horizon
    finished_goods_available: float
    finished_goods_days: float
    inventory_coverage_days: float
    alternative: AlternativeApproval | None
    replacement_unit_cost_delta: float | None
    replacement_margin: float | None
    risk_level: RiskLevel
    risk_reasons: list[str]


class ImpactSummary(BaseModel):
    affected_product_count: int
    product_family_count: int
    product_families: list[str]
    revenue_exposure: float
    horizon_months: int
    horizon_start: str
    horizon_days: int
    inventory_coverage_days: float
    component_available_qty: float
    component_daily_requirement: float
    component_horizon_requirement: float
    products_without_approved_alternative: int
    margin_threshold: float
    products_below_margin_threshold: int
    average_current_margin: float
    replacement_part_id: str | None
    replacement_gross_profit_at_risk: float | None
    risk_counts: dict[str, int]


class AlternativeComparison(BaseModel):
    part_id: str
    name: str
    supplier_name: str | None
    unit_price: float | None
    unit_price_delta_pct: float | None
    lead_time_days: int | None
    default_approval: ApprovalStatus
    approved_products: int
    validation_required_products: int
    not_approved_products: int
    max_qualification_lead_time_days: int
    average_unit_cost_delta: float
    average_margin_delta_points: float
    products_below_margin_threshold: int
    recommended: bool


class GraphNode(BaseModel):
    id: str
    label: str
    item_type: str
    depth: int  # longest distance from the affected component
    risk_level: RiskLevel | None = None
    effective_component_qty: float | None = None
    status: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str  # parent
    target: str  # child
    qty_per_parent: float


class ImpactGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ImpactAnalysis(BaseModel):
    analysis_id: str
    event_id: str | None
    generated_at: str
    as_of_date: str
    data_source: str
    trace_method: str
    component: ComponentInfo
    summary: ImpactSummary
    products: list[ProductImpact]
    paths: list[BomPath]
    alternatives: list[AlternativeComparison]
    graph: ImpactGraph
