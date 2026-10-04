"""Lookup structures built once per snapshot."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.db.schema import (
    AlternatePart,
    BomEdge,
    ItemMaster,
    MaterialExposure,
    ProductDemand,
    Snapshot,
    Supplier,
    SupplierPart,
)

DEFAULT_MARKET = "US"


def _edge_active(edge: BomEdge, as_of: date) -> bool:
    if edge.effective_from > as_of:
        return False
    return edge.effective_to is None or edge.effective_to >= as_of


@dataclass
class DataIndex:
    snapshot: Snapshot
    as_of: date
    items: dict[str, ItemMaster] = field(default_factory=dict)
    children: dict[str, list[BomEdge]] = field(default_factory=dict)
    parents: dict[str, list[BomEdge]] = field(default_factory=dict)
    supplier_part: dict[str, SupplierPart] = field(default_factory=dict)
    suppliers: dict[str, Supplier] = field(default_factory=dict)
    lane_rate: dict[str, float] = field(default_factory=dict)
    material_price: dict[str, float] = field(default_factory=dict)
    exposures: dict[str, list[MaterialExposure]] = field(default_factory=dict)
    selling_price: dict[str, float] = field(default_factory=dict)
    demand: dict[str, list[ProductDemand]] = field(default_factory=dict)
    available_qty: dict[str, float] = field(default_factory=dict)
    alternates: dict[str, list[AlternatePart]] = field(default_factory=dict)

    @classmethod
    def build(cls, snapshot: Snapshot, as_of: date) -> DataIndex:
        idx = cls(snapshot=snapshot, as_of=as_of)
        idx.items = {i.item_id: i for i in snapshot.item_master}
        children: dict[str, list[BomEdge]] = defaultdict(list)
        parents: dict[str, list[BomEdge]] = defaultdict(list)
        for e in snapshot.bom_edges:
            if _edge_active(e, as_of):
                children[e.parent_item_id].append(e)
                parents[e.child_item_id].append(e)
        idx.children = dict(children)
        idx.parents = dict(parents)

        # One sourcing record per part: prefer ACTIVE, then EOL_ANNOUNCED.
        rank = {"ACTIVE": 0, "EOL_ANNOUNCED": 1}
        for sp in sorted(snapshot.supplier_parts, key=lambda s: rank.get(s.status, 9)):
            idx.supplier_part.setdefault(sp.part_id, sp)
        idx.suppliers = {s.supplier_id: s for s in snapshot.suppliers}
        idx.lane_rate = {lane.shipping_lane_id: lane.freight_rate_per_kg for lane in snapshot.shipping_lanes}

        latest_mp: dict[str, tuple[date, float]] = {}
        for mp in snapshot.material_price:
            if mp.effective_date <= as_of:
                cur = latest_mp.get(mp.material_code)
                if cur is None or mp.effective_date > cur[0]:
                    latest_mp[mp.material_code] = (mp.effective_date, mp.price_per_kg)
        idx.material_price = {k: v[1] for k, v in latest_mp.items()}

        exposures: dict[str, list[MaterialExposure]] = defaultdict(list)
        for ex in snapshot.material_exposure:
            exposures[ex.item_id].append(ex)
        idx.exposures = dict(exposures)

        latest_price: dict[str, tuple[date, float]] = {}
        for pp in snapshot.product_price:
            if pp.market == DEFAULT_MARKET and pp.effective_date <= as_of:
                cur = latest_price.get(pp.product_id)
                if cur is None or pp.effective_date > cur[0]:
                    latest_price[pp.product_id] = (pp.effective_date, pp.selling_price)
        idx.selling_price = {k: v[1] for k, v in latest_price.items()}

        demand: dict[str, list[ProductDemand]] = defaultdict(list)
        for d in snapshot.product_demand:
            demand[d.product_id].append(d)
        idx.demand = {k: sorted(v, key=lambda d: d.forecast_month) for k, v in demand.items()}

        avail: dict[str, float] = defaultdict(float)
        for inv in snapshot.inventory:
            avail[inv.item_id] += inv.available_qty
        idx.available_qty = dict(avail)

        alts: dict[str, list[AlternatePart]] = defaultdict(list)
        for a in snapshot.alternate_parts:
            alts[a.source_part_id].append(a)
        idx.alternates = dict(alts)
        return idx

    def item_name(self, item_id: str) -> str:
        item = self.items.get(item_id)
        return item.item_name if item else item_id

    def supplier_name_for_part(self, part_id: str) -> str | None:
        sp = self.supplier_part.get(part_id)
        if sp is None:
            return None
        sup = self.suppliers.get(sp.supplier_id)
        return sup.supplier_name if sup else None

    def alternative_ids(self, source_part_id: str) -> list[str]:
        seen: list[str] = []
        for a in self.alternates.get(source_part_id, []):
            if a.alternative_part_id not in seen:
                seen.append(a.alternative_part_id)
        return seen

    def approval_for(self, source_part_id: str, alternative_part_id: str, product_id: str) -> AlternatePart | None:
        """Product-specific approval overrides the part-level default."""
        default: AlternatePart | None = None
        for a in self.alternates.get(source_part_id, []):
            if a.alternative_part_id != alternative_part_id:
                continue
            if a.product_id == product_id:
                return a
            if a.product_id is None:
                default = a
        return default
