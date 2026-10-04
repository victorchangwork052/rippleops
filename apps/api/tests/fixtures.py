"""Tiny hand-built datasets whose correct answers can be checked by hand."""

from __future__ import annotations

from datetime import date

from app.db.schema import (
    BomEdge,
    Inventory,
    ItemMaster,
    MaterialExposure,
    MaterialPrice,
    ProductDemand,
    ProductPrice,
    ShippingLane,
    Snapshot,
    Supplier,
    SupplierPart,
)
from app.services.index import DataIndex

AS_OF = date(2026, 10, 1)
FROM = date(2025, 1, 1)


def item(item_id: str, item_type: str, processing: float = 0.0, weight: float = 0.0,
         family: str | None = None) -> ItemMaster:
    return ItemMaster(item_id, item_id, item_type, family, "", processing, weight, "ACTIVE")


def edge(parent: str, child: str, qty: float, effective_to: date | None = None,
         effective_from: date = FROM) -> BomEdge:
    return BomEdge(parent, child, qty, "EA", effective_from, effective_to)


def small_snapshot() -> Snapshot:
    """
    FG1 --2--> ASM-A --2--> SUB-C --1--> X        path qty 4
    FG1 --1--> X                                   path qty 1   => FG1 effective 5
    FG2 --3--> ASM-B --1--> X                      path qty 3   => FG2 effective 3
    FG3 --1--> ASM-D (no X)                                     => not affected
    FG2 --5--> X  (expired 2025-12-31)                          => ignored
    """
    return Snapshot(
        item_master=[
            item("FG1", "FINISHED_GOOD", processing=10.0, family="F1"),
            item("FG2", "FINISHED_GOOD", processing=5.0, family="F2"),
            item("FG3", "FINISHED_GOOD", processing=1.0, family="F1"),
            item("ASM-A", "ASSEMBLY", processing=2.0),
            item("ASM-B", "ASSEMBLY", processing=1.0),
            item("ASM-D", "ASSEMBLY"),
            item("SUB-C", "ASSEMBLY", processing=0.5),
            item("X", "COMPONENT", weight=0.1),
            item("X2", "COMPONENT", weight=0.1),
            item("Y", "COMPONENT", weight=1.0),
            item("Z", "COMPONENT", weight=0.5),
        ],
        bom_edges=[
            edge("FG1", "ASM-A", 2), edge("ASM-A", "SUB-C", 2), edge("SUB-C", "X", 1), edge("FG1", "X", 1),
            edge("FG2", "ASM-B", 3), edge("ASM-B", "X", 1), edge("FG2", "X", 5, effective_to=date(2025, 12, 31)),
            edge("FG3", "ASM-D", 1), edge("ASM-D", "Y", 1), edge("ASM-A", "Y", 1),
        ],
        suppliers=[Supplier("S1", "Supplier One", "Taiwan", "LOW")],
        supplier_parts=[
            SupplierPart("S1", "X", "S1-X", 10.0, 30, 100, "EOL_ANNOUNCED", "LANE-1"),
            SupplierPart("S1", "X2", "S1-X2", 12.0, 30, 100, "ACTIVE", "LANE-1"),
            SupplierPart("S1", "Y", "S1-Y", 4.0, 30, 100, "ACTIVE", "LANE-2"),
            SupplierPart("S1", "Z", "S1-Z", 1.0, 30, 100, "ACTIVE", "LANE-2"),
        ],
        shipping_lanes=[
            ShippingLane("LANE-1", "Taiwan", "United States", "Ocean", 2.0, "USD"),
            ShippingLane("LANE-2", "Mexico", "United States", "Truck", 1.0, "USD"),
        ],
        material_price=[MaterialPrice("COPPER", 10.0, "USD", FROM), MaterialPrice("STEEL", 1.0, "USD", FROM)],
        material_exposure=[MaterialExposure("Y", "COPPER", 0.2), MaterialExposure("Y", "STEEL", 0.5)],
        product_price=[ProductPrice("FG1", "US", 200.0, "USD", FROM), ProductPrice("FG2", "US", 100.0, "USD", FROM),
                       ProductPrice("FG3", "US", 50.0, "USD", FROM)],
        product_demand=[ProductDemand("FG1", date(2026, 10, 1), 30.0, 10.0),
                        ProductDemand("FG2", date(2026, 10, 1), 60.0, 0.0)],
        inventory=[Inventory("X", "L1", 400.0, 100.0, 300.0, AS_OF)],
    )


def small_index() -> DataIndex:
    return DataIndex.build(small_snapshot(), AS_OF)
