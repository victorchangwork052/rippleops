"""Cost roll-up, margin, and scenario adjustments against hand-computed values.

Fixture unit costs (see tests/fixtures.py):
  X     = 10 purchase + 0.1 kg x 2.0 freight                  = 10.2
  Y     = 4 purchase + (0.2 x 10 + 0.5 x 1) material + 1.0 x 1 = 7.5
  SUB-C = 0.5 + 1 x X                                          = 10.7
  ASM-A = 2.0 + 2 x SUB-C + 1 x Y                              = 30.9
  FG1   = 10 + 2 x ASM-A + 1 x X                               = 82.0
"""

import pytest

from app.services.costing import CostEngine, CostParams, gross_margin, margin_delta_points
from tests.fixtures import small_index


def approx(x):
    return pytest.approx(x, abs=1e-9)


def test_component_cost_includes_purchase_material_and_freight():
    engine = CostEngine(small_index())
    assert engine.cost("X").total == approx(10.2)
    y = engine.cost("Y")
    assert (y.purchase, y.material, y.freight, y.processing) == (approx(4), approx(2.5), approx(1.0), approx(0))


def test_rollup_multiplies_child_cost_by_bom_quantity():
    engine = CostEngine(small_index())
    assert engine.cost("SUB-C").total == approx(10.7)
    assert engine.cost("ASM-A").total == approx(30.9)
    assert engine.cost("FG1").total == approx(82.0)


def test_rollup_breakdown_sums_to_total():
    fg1 = CostEngine(small_index()).cost("FG1")
    assert fg1.purchase == approx(58.0)
    assert fg1.material == approx(5.0)
    assert fg1.freight == approx(3.0)
    assert fg1.processing == approx(16.0)
    assert fg1.total == approx(82.0)


def test_gross_margin_and_points():
    assert gross_margin(200.0, 82.0) == approx(0.59)
    assert margin_delta_points(0.241, 0.203) == approx(-3.8)
    with pytest.raises(ValueError):
        gross_margin(0.0, 10.0)


def test_component_replacement_uses_effective_quantity():
    idx = small_index()
    base = CostEngine(idx).cost("FG1").total
    replaced = CostEngine(idx, CostParams(substitutions={"X": "X2"})).cost("FG1").total
    assert replaced - base == approx(5 * 2.0)  # effective qty 5 x $2 price delta


def test_material_adjustment_only_affects_exposed_items():
    idx = small_index()
    params = CostParams(material_adjustments={"COPPER": 0.10})
    engine = CostEngine(idx, params)
    assert engine.cost("X").total == approx(10.2)  # no copper exposure
    assert engine.cost("Y").total == approx(7.7)  # 0.2 kg x $1 more
    assert engine.cost("FG1").total == approx(82.4)  # FG1 contains 2 x Y


def test_freight_adjustment_only_affects_that_lane():
    idx = small_index()
    engine = CostEngine(idx, CostParams(freight_adjustments={"LANE-1": 0.50}))
    assert engine.cost("Y").total == approx(7.5)  # LANE-2 unchanged
    assert engine.cost("FG1").total == approx(82.5)  # 5 x X, freight 0.2 -> 0.3


def test_compound_scenario_combines_all_adjustments():
    params = CostParams(substitutions={"X": "X2"}, material_adjustments={"COPPER": 0.10},
                        freight_adjustments={"LANE-1": 0.50})
    # 5 x X2 at 12.3 = 61.5 replaces 5 x X at 10.2 = 51.0 (+10.5), copper +0.4
    assert CostEngine(small_index(), params).cost("FG1").total == approx(92.9)
