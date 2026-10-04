from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ForecastMethod = Literal["bigquery_timesfm", "seasonal_trend"]


class HistoryPoint(BaseModel):
    month: str
    qty: float


class ForecastPoint(BaseModel):
    month: str
    plan_qty: float
    forecast_qty: float
    lower: float
    upper: float


class ProductForecast(BaseModel):
    product_id: str
    name: str
    history: list[HistoryPoint]
    points: list[ForecastPoint]
    plan_total: float
    forecast_total: float
    delta_pct: float  # statistical forecast vs. demand plan


class DemandForecast(BaseModel):
    method: ForecastMethod
    model: str
    horizon_months: int
    confidence_level: float
    products: list[ProductForecast]
    notice: str | None = None


class MaterialWeek(BaseModel):
    week: str
    requirement: float  # component units needed by the current work orders
    requirement_forecast: float  # same, with demand scaled to the statistical forecast
    projected_available: float
    projected_available_forecast: float


class MaterialPlan(BaseModel):
    part_id: str
    available_qty: float
    weeks: list[MaterialWeek]
    total_requirement: float
    stockout_week: str | None
    stockout_week_forecast: str | None
    products: dict[str, float]  # component units per product over the plan horizon


class PlanKpis(BaseModel):
    demand_units: float
    built_units: float
    unmet_units: float
    fill_rate: float
    affected_fill_rate: float
    strategic_fill_rate: float
    late_unit_weeks: float
    gross_margin: float  # after any bridge-buy premium
    bridge_premium: float
    component_used: float
    component_supply: float
    component_remaining: float
    alternative_used: float


class LineWeekLoad(BaseModel):
    line_id: str
    week: str
    capacity_hours: float
    planned_hours: float
    utilization: float


class ProductPlanRow(BaseModel):
    product_id: str
    name: str
    affected: bool
    strategic: bool
    primary_line: str
    demand: float
    baseline_built: float
    built: float
    built_with_original: float
    built_with_alternative: float
    built_on_alternate_line: float
    unmet: float
    alternative_from_week: str | None  # first week the alternative may be used
    unit_margin_original: float
    unit_margin_alternative: float | None


class ScheduleCell(BaseModel):
    product_id: str
    line_id: str
    week: str
    qty: float
    alternative_qty: float


class PlanChange(BaseModel):
    kind: Literal["SWITCH_COMPONENT", "RESERVE_STOCK", "MOVE_LINE", "UNMET_DEMAND", "BRIDGE_BUY"]
    product_ids: list[str]
    units: float
    description: str


class SolverInfo(BaseModel):
    name: str
    status: str
    objective: float
    variables: int
    constraints: int
    solve_ms: int
    gap_limit: float  # OPTIMAL means within this relative gap of the proven bound


class PlanInputs(BaseModel):
    part_id: str
    alternative_part_id: str | None
    bridge_buy_qty: int
    bridge_arrival_week: str | None
    component_on_hand: float
    alternative_early_supply: float
    alternative_lead_time_weeks: int


class ProductionPlan(BaseModel):
    plan_id: str
    event_id: str | None
    label: str
    weeks: list[str]
    inputs: PlanInputs
    solver: SolverInfo
    baseline: PlanKpis
    optimized: PlanKpis
    products: list[ProductPlanRow]
    schedule: list[ScheduleCell]
    line_loads: list[LineWeekLoad]
    baseline_line_loads: list[LineWeekLoad]  # work orders as scheduled, before re-planning
    lines: dict[str, str]
    changes: list[PlanChange]
    status: Literal["DRAFT", "PROPOSED", "APPROVED", "REJECTED"] = "DRAFT"
    proposal_note: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None


class PlanDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    decided_by: str = "Operations Manager"
