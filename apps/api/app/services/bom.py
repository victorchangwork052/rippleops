"""Multi-level BOM traversal and effective-quantity math.

`paths_from_edges` is the in-memory traversal used by the local backend and
as the reference implementation in tests. BigQuery backends produce raw paths
through GQL / recursive SQL and hand them to `summarize_paths`, so the
effective-quantity rule lives in exactly one place.
"""

from __future__ import annotations

from collections import defaultdict
from math import prod

from app.models.bom import BomPath, BomTrace, ProductUsage
from app.services.index import DataIndex

FINISHED_GOOD = "FINISHED_GOOD"
MAX_DEPTH = 8


class BomCycleError(ValueError):
    pass


def paths_from_edges(index: DataIndex, component_id: str) -> list[BomPath]:
    """Every path from a finished good down to `component_id`."""
    out: list[BomPath] = []

    def walk(item_id: str, chain: list[str], qtys: list[float]) -> None:
        # chain/qtys are built bottom-up (component first).
        if len(chain) > MAX_DEPTH + 1:
            raise BomCycleError(f"BOM deeper than {MAX_DEPTH} levels above {component_id}")
        item = index.items.get(item_id)
        if item is not None and item.item_type == FINISHED_GOOD and len(chain) > 1:
            nodes = list(reversed(chain))
            edge_qtys = list(reversed(qtys))
            out.append(BomPath(product_id=item_id, nodes=nodes, edge_qtys=edge_qtys, path_qty=prod(edge_qtys)))
            return
        for edge in index.parents.get(item_id, []):
            if edge.parent_item_id in chain:
                raise BomCycleError(f"Cycle detected at {edge.parent_item_id}")
            walk(edge.parent_item_id, chain + [edge.parent_item_id], qtys + [edge.qty_per_parent])

    walk(component_id, [component_id], [])
    return sort_paths(out)


def sort_paths(paths: list[BomPath]) -> list[BomPath]:
    return sorted(paths, key=lambda p: (p.product_id, len(p.nodes), p.nodes))


def summarize_paths(component_id: str, paths: list[BomPath], trace_method: str) -> BomTrace:
    """Effective qty per product = SUM over paths of PRODUCT(edge qty)."""
    total: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    for p in paths:
        total[p.product_id] += p.path_qty
        count[p.product_id] += 1
    products = [
        ProductUsage(product_id=pid, effective_component_qty=round(total[pid], 6), paths_to_component=count[pid])
        for pid in sorted(total)
    ]
    return BomTrace(
        component_id=component_id,
        affected_product_count=len(products),
        trace_method=trace_method,
        paths=sort_paths(paths),
        products=products,
    )


def order_edge_chain(product_id: str, component_id: str, edges: list[tuple[str, str, float]]) -> BomPath:
    """Rebuild an ordered path from an unordered set of (parent, child, qty) edges.

    Graph engines do not guarantee the order of aggregated path elements, so
    the chain is re-linked from the finished good down.
    """
    by_parent = {parent: (child, qty) for parent, child, qty in edges}
    if len(by_parent) != len(edges):
        raise ValueError(f"Path for {product_id} revisits a parent node")
    nodes = [product_id]
    qtys: list[float] = []
    cur = product_id
    while cur in by_parent:
        child, qty = by_parent[cur]
        nodes.append(child)
        qtys.append(qty)
        cur = child
    if cur != component_id or len(qtys) != len(edges):
        raise ValueError(f"Could not link path edges for {product_id} -> {component_id}")
    return BomPath(product_id=product_id, nodes=nodes, edge_qtys=qtys, path_qty=prod(qtys))


def trace_in_memory(index: DataIndex, component_id: str) -> BomTrace:
    return summarize_paths(component_id, paths_from_edges(index, component_id), "in_memory")
