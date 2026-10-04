from app.services.risk import RiskInput, assess


def risk(**kw):
    base = dict(has_approved_alternative=True, coverage_days=120, margin=0.30, margin_threshold=0.20,
                replacement_cost_increase_pct=0.0)
    base.update(kw)
    return assess(RiskInput(**base))[0]


def test_critical_when_no_alternative_and_short_coverage():
    assert risk(has_approved_alternative=False, coverage_days=30) == "CRITICAL"


def test_critical_when_margin_below_ten_percent():
    assert risk(margin=0.08) == "CRITICAL"


def test_high_for_short_coverage_or_margin_below_target():
    assert risk(coverage_days=60) == "HIGH"
    assert risk(margin=0.18) == "HIGH"


def test_medium_for_material_cost_impact_or_pending_validation():
    assert risk(replacement_cost_increase_pct=0.02) == "MEDIUM"
    assert risk(has_approved_alternative=False) == "MEDIUM"


def test_low_when_covered_and_alternative_is_cheap():
    assert risk(replacement_cost_increase_pct=0.005) == "LOW"


def test_reasons_are_never_empty():
    for kw in ({}, {"coverage_days": 60}, {"margin": 0.05}, {"replacement_cost_increase_pct": 0.05}):
        assert assess(RiskInput(**{**dict(has_approved_alternative=True, coverage_days=120, margin=0.30,
                                          margin_threshold=0.20, replacement_cost_increase_pct=0.0), **kw}))[1]
