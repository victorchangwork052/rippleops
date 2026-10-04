from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.impact import RiskLevel


class ScenarioRequest(BaseModel):
    event_id: str | None = None
    part_id: str | None = Field(default=None, description="Affected component; taken from the event if omitted.")
    replacement_part_id: str | None = None
    commodity_adjustments: dict[str, float] = Field(default_factory=dict, description='e.g. {"COPPER": 0.12}')
    freight_adjustments: dict[str, float] = Field(default_factory=dict, description='e.g. {"TW-US-OCEAN": 0.15}')
    margin_threshold: float = Field(default=0.20, ge=0.0, lt=1.0)
    name: str | None = None


class DeltaBreakdown(BaseModel):
    component_replacement: float
    material: float
    freight: float


class ScenarioProduct(BaseModel):
    product_id: str
    name: str
    product_family: str
    effective_component_qty: float
    selling_price: float
    current_unit_cost: float
    scenario_unit_cost: float
    unit_cost_delta: float
    delta_breakdown: DeltaBreakdown
    current_margin: float
    scenario_margin: float
    margin_delta_points: float
    below_threshold: bool
    crosses_threshold: bool
    horizon_forecast_qty: float
    revenue_exposure: float
    gross_profit_impact: float  # unit cost delta x horizon volume (positive = profit lost)
    replacement_approval: str | None
    risk_level: RiskLevel
    risk_reasons: list[str]


class ScenarioSummary(BaseModel):
    product_count: int
    average_current_unit_cost: float
    average_scenario_unit_cost: float
    average_unit_cost_delta: float
    average_margin_delta_points: float
    average_current_margin: float
    average_scenario_margin: float
    current_products_below_threshold: int
    products_below_margin_threshold: int
    products_newly_below_threshold: int
    revenue_at_risk: float
    total_revenue_exposure: float
    gross_profit_impact: float
    driver_average_delta: DeltaBreakdown
    horizon_months: int


class ScenarioResult(BaseModel):
    scenario_id: str
    event_id: str | None
    name: str
    created_at: str
    part_id: str
    inputs: ScenarioRequest
    summary: ScenarioSummary
    products: list[ScenarioProduct]
