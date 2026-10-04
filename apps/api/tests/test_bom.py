import random

import pytest

from app.db.bigquery_repo import parse_edge_strings
from app.db.schema import Snapshot
from app.services.bom import (
    BomCycleError,
    order_edge_chain,
    paths_from_edges,
    summarize_paths,
    trace_in_memory,
)
from app.services.index import DataIndex
from tests.fixtures import AS_OF, edge, item, small_index


def test_effective_quantity_multiplies_along_path_and_sums_across_paths():
    trace = trace_in_memory(small_index(), "X")
    usage = {p.product_id: p for p in trace.products}
    assert set(usage) == {"FG1", "FG2"}
    assert usage["FG1"].effective_component_qty == 5  # 2*2*1 + 1
    assert usage["FG1"].paths_to_component == 2
    assert usage["FG2"].effective_component_qty == 3  # expired direct edge ignored
    assert usage["FG2"].paths_to_component == 1
    assert trace.affected_product_count == 2


def test_paths_run_from_finished_good_to_component():
    paths = paths_from_edges(small_index(), "X")
    deep = next(p for p in paths if len(p.nodes) == 4)
    assert deep.nodes == ["FG1", "ASM-A", "SUB-C", "X"]
    assert deep.edge_qtys == [2, 2, 1]
    assert deep.path_qty == 4


def test_unaffected_products_are_excluded():
    trace = trace_in_memory(small_index(), "X")
    assert "FG3" not in {p.product_id for p in trace.products}


def test_component_used_nowhere_returns_empty_trace():
    trace = trace_in_memory(small_index(), "Z")
    assert trace.affected_product_count == 0
    assert trace.paths == []


def test_cycle_is_detected():
    snap = Snapshot(
        item_master=[item("FG", "FINISHED_GOOD"), item("A", "ASSEMBLY"), item("B", "ASSEMBLY"),
                     item("X", "COMPONENT")],
        bom_edges=[edge("FG", "A", 1), edge("A", "B", 1), edge("B", "A", 1), edge("B", "X", 1)],
    )
    with pytest.raises(BomCycleError):
        trace_in_memory(DataIndex.build(snap, AS_OF), "X")


def test_order_edge_chain_relinks_unordered_graph_output():
    edges = [("FG1", "ASM-A", 2.0), ("ASM-A", "SUB-C", 2.0), ("SUB-C", "X", 1.0)]
    shuffled = edges[:]
    random.Random(3).shuffle(shuffled)
    path = order_edge_chain("FG1", "X", shuffled)
    assert path.nodes == ["FG1", "ASM-A", "SUB-C", "X"]
    assert path.path_qty == 4


def test_order_edge_chain_rejects_broken_chain():
    with pytest.raises(ValueError):
        order_edge_chain("FG1", "X", [("FG1", "ASM-A", 2.0), ("SUB-C", "X", 1.0)])


def test_bigquery_edge_strings_match_in_memory_trace():
    """Rows shaped like the GQL / recursive-SQL output give the same summary."""
    index = small_index()
    expected = trace_in_memory(index, "X")
    rows = []
    for p in expected.paths:
        raw = [f"{a}|{b}|{q}" for a, b, q in zip(p.nodes[:-1], p.nodes[1:], p.edge_qtys, strict=True)]
        rows.append(parse_edge_strings(p.product_id, "X", list(reversed(raw))))
    got = summarize_paths("X", rows, "bigquery_graph")
    assert got.products == expected.products
    assert [p.nodes for p in got.paths] == [p.nodes for p in expected.paths]
