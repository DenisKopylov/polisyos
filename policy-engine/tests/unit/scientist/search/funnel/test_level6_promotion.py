"""No promotion-purpose issuer/verifier/serialized commit API is integrated."""

from threading import Barrier, Thread

import pytest

from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.funnel.level6_promotion import Level6PromotionStage


@pytest.mark.parametrize("preflight", [None, False, {"allowed": False}, "allow", 1, [True], True])
def test_retained_preflight_markers_never_admit_effectful_generic_callback(preflight):
    writes = []
    stage = Level6PromotionStage(
        promotion_runner=lambda candidate, context: writes.append(candidate) or {"promoted": True},
        promotion_owner_recheck=(
            None if preflight is None else lambda candidate, context: preflight
        ),
    )
    result = stage.evaluate(
        {"candidate_id": "candidate-1"},
        {"promotion_owner_recheck_passed": True, "owner_verified": True, "permit": preflight},
    )
    assert writes == []
    assert result.terminal_action == "defer_to_human"
    assert result.feedback["promotion_admission_status"] == "bridge_missing"
    assert (
        result.feedback["promotion_required_contract"]
        == "owner_issued_promotion_permit_and_revoke_serialized_commit"
    )


def test_revoke_after_true_preflight_barrier_has_zero_effects():
    writes = []
    ready = Barrier(2)
    revoked = Barrier(2)
    retained = {"preflight": True, "revoked": False}
    stage = Level6PromotionStage(
        promotion_runner=lambda candidate, context: writes.append(candidate) or {"promoted": True},
        promotion_owner_recheck=lambda candidate, context: retained["preflight"],
    )
    results = []

    def evaluate_after_revoke():
        ready.wait()
        revoked.wait()
        results.append(
            stage.evaluate({}, {"promotion_owner_recheck_passed": retained["preflight"]})
        )

    worker = Thread(target=evaluate_after_revoke)
    worker.start()
    ready.wait()
    retained["revoked"] = True
    revoked.wait()
    worker.join()
    assert retained == {"preflight": True, "revoked": True}
    assert writes == []
    assert results[0].terminal_action == "defer_to_human"


def test_prepared_payload_is_read_only_interpretation_without_callback_effects():
    writes = []
    stage = Level6PromotionStage(
        promotion_runner=lambda candidate, context: writes.append(candidate)
    )
    result = stage.evaluate({}, {"promotion_result": {"decision": "complete", "promoted": True}})
    assert result.terminal_action == "complete"
    assert writes == []
    assert result.feedback["promotion_result_read_only"] is True


def test_duration_and_configuration_costs_remain_estimates_at_l5_and_l6():
    l5_result = Level5RefutationGovernanceStage().evaluate({}, {})
    l6_result = Level6PromotionStage().evaluate({}, {})

    assert l5_result.compute_cost_usd is not None
    assert l5_result.compute_cost_origin == "estimated"
    assert l6_result.compute_cost_usd is not None
    assert l6_result.compute_cost_origin == "estimated"
