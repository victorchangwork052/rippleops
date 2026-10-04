"""Alternative sourcing and supplier scorecards."""

import pytest

from app.integrations.providers import get_integrations
from app.services.sourcing import find_sourcing_options, gather_evidence, providers_of, score_candidates


@pytest.fixture(scope="module")
def assessment(seed_repo):
    idx = seed_repo.index()
    products = [p.product_id for p in seed_repo.trace("MCU-X100").products]
    ig = get_integrations()
    options = find_sourcing_options(idx, ig, "MCU-X100", products)
    return options, score_candidates(idx, options, gather_evidence(idx, ig, options), providers_of(ig))


def test_merges_internal_avl_and_catalog(assessment):
    options, _ = assessment
    by_id = {c.candidate_id: c for c in options.candidates}
    assert set(by_id) == {"MCU-X200@SUP-NOVA", "MCU-X150@SUP-CRES", "LMC-4410@EXT-LUMEN", "HMX-100@EXT-HANS",
                          "MCU-X100@EXT-QRP"}
    x200 = by_id["MCU-X200@SUP-NOVA"]
    assert x200.source == "INTERNAL_AVL" and x200.approval_status == "APPROVED"
    assert x200.products_approved == 8
    assert x200.products_needing_validation == ["P300", "P410", "P420", "P500"]
    assert x200.price_delta_pct == pytest.approx(0.18)
    assert by_id["LMC-4410@EXT-LUMEN"].is_new_supplier
    assert by_id["MCU-X100@EXT-QRP"].match_type == "SAME_PART"


def test_sanctions_match_blocks_the_candidate(assessment):
    _, a = assessment
    assert a.blocked_candidate_ids == ["HMX-100@EXT-HANS"]
    card = next(c for c in a.scorecards if c.candidate_id == "HMX-100@EXT-HANS")
    assert card.total_score == 0 and card.tier == "BLOCKED"
    assert card.flags[0].startswith("Compliance block")


def test_recommendation_roles(assessment):
    _, a = assessment
    assert a.recommended_candidate_id == "MCU-X200@SUP-NOVA"  # fastest approved transition
    assert a.second_source_candidate_id == "MCU-X150@SUP-CRES"  # best-scoring long-term source
    assert a.bridge_candidate_id == "MCU-X100@EXT-QRP"
    scores = {c.candidate_id: c.total_score for c in a.scorecards}
    assert scores["MCU-X150@SUP-CRES"] > scores["MCU-X200@SUP-NOVA"]


def test_scorecard_weights_sum_to_100(assessment):
    _, a = assessment
    assert sum(a.weights.values()) == 100
    for card in a.scorecards:
        assert all(0 <= c.score <= c.weight for c in card.components)
