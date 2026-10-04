"""Deterministic cost roll-up (handoff section 14).

Item Cost = Base Processing Cost + Purchase Price + Raw Material Cost
            + Allocated Freight Cost + SUM(qty x Child Item Cost)

Purchased components carry an index-linked raw-material surcharge that is
modelled separately from the purchase price, which is what lets a copper
price change flow through to finished goods.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.index import DataIndex


@dataclass(frozen=True)
class CostParams:
    # source part -> replacement part, applied wherever the source is a child.
    substitutions: dict[str, str] = field(default_factory=dict)
    # material code -> fractional change, e.g. {"COPPER": 0.12}
    material_adjustments: dict[str, float] = field(default_factory=dict)
    # shipping lane -> fractional change, e.g. {"TW-US-OCEAN": 0.15}
    freight_adjustments: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CostBreakdown:
    """Fully rolled-up cost of one unit, split by cost driver."""

    purchase: float
    material: float
    freight: float
    processing: float

    @property
    def total(self) -> float:
        return self.purchase + self.material + self.freight + self.processing

    def plus(self, other: CostBreakdown, qty: float = 1.0) -> CostBreakdown:
        return CostBreakdown(
            purchase=self.purchase + qty * other.purchase,
            material=self.material + qty * other.material,
            freight=self.freight + qty * other.freight,
            processing=self.processing + qty * other.processing,
        )


ZERO = CostBreakdown(0.0, 0.0, 0.0, 0.0)


class UnknownItemError(KeyError):
    pass


def material_price(index: DataIndex, code: str, params: CostParams) -> float:
    return index.material_price.get(code, 0.0) * (1.0 + params.material_adjustments.get(code, 0.0))


def lane_rate(index: DataIndex, lane_id: str, params: CostParams) -> float:
    return index.lane_rate.get(lane_id, 0.0) * (1.0 + params.freight_adjustments.get(lane_id, 0.0))


def own_cost(index: DataIndex, item_id: str, params: CostParams) -> CostBreakdown:
    """Cost incurred at this item's own level, excluding children."""
    item = index.items.get(item_id)
    if item is None:
        raise UnknownItemError(item_id)
    material = sum(
        ex.material_weight_kg * material_price(index, ex.material_code, params)
        for ex in index.exposures.get(item_id, [])
    )
    purchase = 0.0
    freight = 0.0
    sp = index.supplier_part.get(item_id)
    if sp is not None:
        purchase = sp.current_unit_price
        freight = item.unit_weight_kg * lane_rate(index, sp.shipping_lane_id, params)
    return CostBreakdown(purchase=purchase, material=material, freight=freight, processing=item.base_processing_cost)


class CostEngine:
    """Memoised roll-up for one set of scenario parameters."""

    def __init__(self, index: DataIndex, params: CostParams | None = None) -> None:
        self.index = index
        self.params = params or CostParams()
        self._memo: dict[str, CostBreakdown] = {}

    def cost(self, item_id: str) -> CostBreakdown:
        item_id = self.params.substitutions.get(item_id, item_id)
        return self._rolled(item_id, ())

    def _rolled(self, item_id: str, stack: tuple[str, ...]) -> CostBreakdown:
        if item_id in self._memo:
            return self._memo[item_id]
        if item_id in stack:
            raise ValueError(f"BOM cycle at {item_id}")
        total = own_cost(self.index, item_id, self.params)
        for edge in self.index.children.get(item_id, []):
            child = self.params.substitutions.get(edge.child_item_id, edge.child_item_id)
            total = total.plus(self._rolled(child, stack + (item_id,)), edge.qty_per_parent)
        self._memo[item_id] = total
        return total


def gross_margin(selling_price: float, unit_cost: float) -> float:
    """(Selling Price - Product Cost) / Selling Price, as a fraction."""
    if selling_price <= 0:
        raise ValueError("Selling price must be positive")
    return (selling_price - unit_cost) / selling_price


def margin_delta_points(current_margin: float, scenario_margin: float) -> float:
    """Change in percentage points (not percent)."""
    return (scenario_margin - current_margin) * 100.0
