from __future__ import annotations

from pydantic import BaseModel


class BomPath(BaseModel):
    product_id: str
    # Finished good first, affected component last.
    nodes: list[str]
    # qty_per_parent for each edge; len(edge_qtys) == len(nodes) - 1.
    edge_qtys: list[float]
    path_qty: float


class ProductUsage(BaseModel):
    product_id: str
    effective_component_qty: float
    paths_to_component: int


class BomTrace(BaseModel):
    component_id: str
    affected_product_count: int
    trace_method: str  # bigquery_graph | recursive_sql | in_memory
    paths: list[BomPath]
    products: list[ProductUsage]
