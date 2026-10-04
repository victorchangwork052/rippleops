"""Integration tests: the seeded dataset must reproduce the demo story (handoff 5, 16, 36)."""

import pytest

from app.models.scenario import ScenarioRequest
from app.services.impact import UnknownPartError, analyze_impact
from app.services.scenario import ScenarioInputError, run_scenario

PART = "MCU-X100"
H = 6


@pytest.fixture(scope="module")
def impact(seed_repo):
    return analyze_impact(seed_repo, PART, 0.20, H)


def scenario(repo, **kw):
    return run_scenario(repo, PART, ScenarioRequest(margin_threshold=0.20, **kw), H)


def test_mcu_x100_affected_products(impact):
    s = impact.summary
    assert s.affected_product_count == 12
    assert s.product_family_count == 3
    assert 4_150_000 <= s.revenue_exposure <= 4_250_000  # "$4.2M"
    assert int(s.inventory_coverage_days) == 58
    assert s.products_without_approved_alternative == 4
    assert s.products_below_margin_threshold == 0
    p300 = next(p for p in impact.products if p.product_id == "P300")
    assert p300.effective_component_qty == 4
    assert p300.paths_to_component == 2
    assert p300.risk_level == "HIGH"
    assert 0.20 <= p300.current_margin < 0.23  # close to target


def test_graph_contains_every_path_node(impact):
    ids = {n.id for n in impact.graph.nodes}
    for path in impact.paths:
        assert set(path.nodes) <= ids
    component = next(n for n in impact.graph.nodes if n.id == PART)
    assert component.depth == 0


def test_alternatives_are_compared(impact):
    alts = {a.part_id: a for a in impact.alternatives}
    assert set(alts) == {"MCU-X200", "MCU-X150"}
    x200 = alts["MCU-X200"]
    assert x200.recommended
    assert x200.approved_products == 8 and x200.validation_required_products == 4
    assert x200.unit_price_delta_pct == pytest.approx(0.18)


def test_replacement_with_mcu_x200(seed_repo):
    r = scenario(seed_repo, replacement_part_id="MCU-X200")
    assert r.summary.average_unit_cost_delta == 4.73
    assert round(r.summary.average_margin_delta_points, 1) == -1.9
    assert r.summary.products_below_margin_threshold == 3
    assert {p.product_id for p in r.products if p.below_threshold} == {"P300", "P500", "P200"}
    for p in r.products:
        assert p.delta_breakdown.material == 0 and p.delta_breakdown.freight == 0


def test_copper_only_changes_copper_exposed_cost(seed_repo):
    r = scenario(seed_repo, commodity_adjustments={"COPPER": 0.12})
    assert r.summary.average_unit_cost_delta > 0
    assert all(p.delta_breakdown.component_replacement == 0 for p in r.products)
    assert r.summary.products_below_margin_threshold == 0


def test_replacement_plus_copper(seed_repo):
    rep = scenario(seed_repo, replacement_part_id="MCU-X200")
    both = scenario(seed_repo, replacement_part_id="MCU-X200", commodity_adjustments={"COPPER": 0.12})
    assert both.summary.average_unit_cost_delta > rep.summary.average_unit_cost_delta
    assert both.summary.products_below_margin_threshold >= rep.summary.products_below_margin_threshold


def test_compound_scenario_pushes_five_products_below_target(seed_repo):
    r = scenario(seed_repo, replacement_part_id="MCU-X200", commodity_adjustments={"COPPER": 0.12},
                 freight_adjustments={"TW-US-OCEAN": 0.15})
    assert r.summary.products_below_margin_threshold == 5
    assert {p.product_id for p in r.products if p.below_threshold} == {"P300", "P500", "P200", "P120", "P410"}
    for p in r.products:
        parts = p.delta_breakdown
        total = parts.component_replacement + parts.material + parts.freight
        assert total == pytest.approx(p.unit_cost_delta, abs=0.011)
        assert parts.freight > 0 and parts.material > 0


def test_scenarios_are_deterministic(seed_repo):
    kw = dict(replacement_part_id="MCU-X200", commodity_adjustments={"COPPER": 0.12})
    a, b = scenario(seed_repo, **kw), scenario(seed_repo, **kw)
    assert a.summary == b.summary and a.products == b.products


def test_invalid_inputs_are_rejected(seed_repo):
    with pytest.raises(ScenarioInputError):
        scenario(seed_repo, replacement_part_id="MCU-K300")
    with pytest.raises(ScenarioInputError):
        scenario(seed_repo, commodity_adjustments={"UNOBTAINIUM": 0.1})
    with pytest.raises(UnknownPartError):
        analyze_impact(seed_repo, "NOPE-1", 0.2, H)
    with pytest.raises(UnknownPartError):
        analyze_impact(seed_repo, "P300", 0.2, H)  # finished good, not a component
