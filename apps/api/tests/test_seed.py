"""The seeded dataset must support the demo narrative (handoff section 16)."""

from collections import Counter

from app.seed.generator import generate


def test_generator_is_deterministic():
    assert generate() == generate()


def test_dataset_size_matches_handoff():
    snap = generate()
    types = Counter(i.item_type for i in snap.item_master)
    assert types == {"FINISHED_GOOD": 50, "ASSEMBLY": 30, "COMPONENT": 150}
    assert 8 <= len(snap.suppliers) <= 12
    assert 4 <= len({m.material_code for m in snap.material_price}) <= 6
    assert 5 <= len(snap.shipping_lanes) <= 8


def test_every_bom_edge_references_known_items():
    snap = generate()
    ids = {i.item_id for i in snap.item_master}
    for e in snap.bom_edges:
        assert e.parent_item_id in ids and e.child_item_id in ids


def test_every_component_has_a_sourcing_record():
    snap = generate()
    sourced = {sp.part_id for sp in snap.supplier_parts}
    for i in snap.item_master:
        if i.item_type == "COMPONENT":
            assert i.item_id in sourced


def test_anchor_trace(seed_repo):
    trace = seed_repo.trace("MCU-X100")
    usage = {p.product_id: p.effective_component_qty for p in trace.products}
    assert trace.affected_product_count == 12
    assert usage["P100"] == 1
    assert usage["P200"] == 2
    assert usage["P300"] == 4
    assert usage["P410"] == 1
    assert usage["P500"] == 3
    families = {seed_repo.index().items[p].product_family for p in usage}
    assert len(families) == 3


def test_anchor_trace_covers_multi_level_and_multi_path(seed_repo):
    trace = seed_repo.trace("MCU-X100")
    depths = {len(p.nodes) - 1 for p in trace.paths}
    assert min(depths) == 2 and max(depths) == 4
    p300 = [p for p in trace.paths if p.product_id == "P300"]
    assert len(p300) == 2
    assert sorted(p.path_qty for p in p300) == [2, 2]


def test_replacement_costs_about_18_percent_more(seed_repo):
    sp = seed_repo.index().supplier_part
    ratio = sp["MCU-X200"].current_unit_price / sp["MCU-X100"].current_unit_price
    assert abs(ratio - 1.18) < 0.005
