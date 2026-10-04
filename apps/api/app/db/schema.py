"""Typed rows for every RippleOps table.

The same definitions drive the in-memory backend, the BigQuery table schemas
(`BQ_SCHEMAS`) and the CSV export, so the two backends cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ItemMaster:
    item_id: str
    item_name: str
    item_type: str  # FINISHED_GOOD | ASSEMBLY | COMPONENT
    product_family: str | None
    description: str
    base_processing_cost: float
    unit_weight_kg: float
    status: str


@dataclass(frozen=True)
class BomEdge:
    parent_item_id: str
    child_item_id: str
    qty_per_parent: float
    uom: str
    effective_from: date
    effective_to: date | None


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    supplier_name: str
    country: str
    risk_level: str


@dataclass(frozen=True)
class SupplierPart:
    supplier_id: str
    part_id: str
    supplier_part_number: str
    current_unit_price: float
    lead_time_days: int
    minimum_order_qty: int
    status: str
    shipping_lane_id: str


@dataclass(frozen=True)
class AlternatePart:
    source_part_id: str
    alternative_part_id: str
    approval_status: str  # APPROVED | VALIDATION_REQUIRED | NOT_APPROVED
    qualification_lead_time_days: int
    notes: str
    # Extension to the handoff schema: NULL applies to every product, a value
    # overrides the approval for that one finished good.
    product_id: str | None = None


@dataclass(frozen=True)
class Inventory:
    item_id: str
    location_id: str
    on_hand_qty: float
    allocated_qty: float
    available_qty: float
    snapshot_date: date


@dataclass(frozen=True)
class ProductDemand:
    product_id: str
    forecast_month: date
    forecast_qty: float
    open_order_qty: float


@dataclass(frozen=True)
class ProductPrice:
    product_id: str
    market: str
    selling_price: float
    currency: str
    effective_date: date


@dataclass(frozen=True)
class MaterialExposure:
    item_id: str
    material_code: str
    material_weight_kg: float


@dataclass(frozen=True)
class MaterialPrice:
    material_code: str
    price_per_kg: float
    currency: str
    effective_date: date


@dataclass(frozen=True)
class ShippingLane:
    shipping_lane_id: str
    origin: str
    destination: str
    mode: str
    freight_rate_per_kg: float
    currency: str


@dataclass(frozen=True)
class ChangeEvent:
    event_id: str
    event_type: str
    supplier_id: str | None
    affected_item_id: str | None
    event_date: date
    last_time_buy_date: date | None
    last_ship_date: date | None
    recommended_alternative_item_id: str | None
    source_document_uri: str | None
    status: str
    # Extension: short English title shown on event cards.
    title: str = ""
    summary: str = ""


@dataclass(frozen=True)
class SupplierPerformance:
    """Quarterly supplier KPIs from the ERP / quality system."""

    supplier_id: str
    quarter_end: date
    on_time_delivery_rate: float  # fraction of PO lines received on time
    quality_ppm: float  # defective parts per million received
    avg_lead_time_days: float
    lead_time_variance_days: float  # standard deviation of actual vs quoted lead time


@dataclass(frozen=True)
class ProductionLine:
    line_id: str
    line_name: str
    site: str
    weekly_capacity_hours: float
    status: str


@dataclass(frozen=True)
class ProductRouting:
    product_id: str
    line_id: str
    routing_type: str  # PRIMARY | ALTERNATE
    hours_per_unit: float


@dataclass(frozen=True)
class WorkOrder:
    work_order_id: str
    product_id: str
    line_id: str
    planned_week: date  # Monday of the planned build week
    quantity: float
    status: str  # RELEASED | PLANNED
    customer_priority: str  # STRATEGIC | STANDARD


@dataclass(frozen=True)
class DemandHistory:
    product_id: str
    month: date
    shipped_qty: float


TABLES: dict[str, type] = {
    "item_master": ItemMaster,
    "bom_edges": BomEdge,
    "suppliers": Supplier,
    "supplier_parts": SupplierPart,
    "alternate_parts": AlternatePart,
    "inventory": Inventory,
    "product_demand": ProductDemand,
    "product_price": ProductPrice,
    "material_exposure": MaterialExposure,
    "material_price": MaterialPrice,
    "shipping_lanes": ShippingLane,
    "change_events": ChangeEvent,
    "supplier_performance": SupplierPerformance,
    "production_lines": ProductionLine,
    "product_routings": ProductRouting,
    "work_orders": WorkOrder,
    "demand_history": DemandHistory,
}


@dataclass
class Snapshot:
    """A complete, immutable-by-convention copy of the demo dataset."""

    item_master: list[ItemMaster] = field(default_factory=list)
    bom_edges: list[BomEdge] = field(default_factory=list)
    suppliers: list[Supplier] = field(default_factory=list)
    supplier_parts: list[SupplierPart] = field(default_factory=list)
    alternate_parts: list[AlternatePart] = field(default_factory=list)
    inventory: list[Inventory] = field(default_factory=list)
    product_demand: list[ProductDemand] = field(default_factory=list)
    product_price: list[ProductPrice] = field(default_factory=list)
    material_exposure: list[MaterialExposure] = field(default_factory=list)
    material_price: list[MaterialPrice] = field(default_factory=list)
    shipping_lanes: list[ShippingLane] = field(default_factory=list)
    change_events: list[ChangeEvent] = field(default_factory=list)
    supplier_performance: list[SupplierPerformance] = field(default_factory=list)
    production_lines: list[ProductionLine] = field(default_factory=list)
    product_routings: list[ProductRouting] = field(default_factory=list)
    work_orders: list[WorkOrder] = field(default_factory=list)
    demand_history: list[DemandHistory] = field(default_factory=list)

    def table(self, name: str) -> list[Any]:
        return getattr(self, name)


def _bq_type(annotation: str) -> str:
    base = annotation.replace(" | None", "").strip()
    return {"str": "STRING", "float": "NUMERIC", "int": "INT64", "date": "DATE"}[base]


def bq_schema(row_type: type) -> list[tuple[str, str, str]]:
    """(name, BigQuery type, mode) for each column of a row dataclass."""
    out = []
    for f in fields(row_type):
        ann = f.type if isinstance(f.type, str) else f.type.__name__
        mode = "NULLABLE" if "None" in ann else "REQUIRED"
        out.append((f.name, _bq_type(ann), mode))
    return out
