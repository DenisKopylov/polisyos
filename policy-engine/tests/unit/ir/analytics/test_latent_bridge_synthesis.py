"""Unit tests for fail-closed automatic latent-bridge synthesis (Stage 2.4)."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.alignment_certification import (
    AlignmentReviewerState,
    AlignmentReviewStatus,
    AlignmentType,
    AlignmentVerificationConfig,
    VariableAlignmentCertificate,
    verify_fragment_alignment,
)
from polisyos.ir.analytics.cross_graph import SCMFragment
from polisyos.ir.analytics.latent_bridge_synthesis import (
    LatentBridgeBlockReason,
    LatentBridgeCandidate,
    LatentBridgeEvidence,
    LatentBridgeFalsificationTest,
    LatentBridgeFalsificationTestFamily,
    LatentBridgeFalsificationTestStatus,
    LatentBridgeHeldoutMetrics,
    LatentBridgeHypothesis,
    LatentBridgeInvarianceLevel,
    LatentBridgeProxyFamily,
    LatentBridgeStatus,
    LatentBridgeSynthesisMode,
    LatentBridgeSynthesisPolicy,
    build_pair_key,
    load_latent_bridge_hypothesis,
    persist_latent_bridge_hypothesis,
    synthesize_latent_bridge,
)
from polisyos.ir.registry.refs import LatentBridgeHypothesisRef
from polisyos.scientist.cross_graph.compiler import (
    _verify_fragment_bundle_alignment_with_governance,
)

PAIR_KEY = "fragA:var|fragB:var"


def _accept_policy(**overrides: object) -> LatentBridgeSynthesisPolicy:
    base = {"enable_auto_latent_bridge": True}
    base.update(overrides)
    return LatentBridgeSynthesisPolicy(**base)


def _passing_falsification_pack() -> list[LatentBridgeFalsificationTest]:
    return [
        LatentBridgeFalsificationTest(
            test_family=LatentBridgeFalsificationTestFamily.CTA,
            status=LatentBridgeFalsificationTestStatus.PASS,
            p_value=0.35,
        ),
        LatentBridgeFalsificationTest(
            test_family=LatentBridgeFalsificationTestFamily.ALTERNATIVE_MODEL,
            status=LatentBridgeFalsificationTestStatus.PASS,
            statistic=4.1,
        ),
        LatentBridgeFalsificationTest(
            test_family=LatentBridgeFalsificationTestFamily.STABILITY,
            status=LatentBridgeFalsificationTestStatus.PASS,
        ),
    ]


def _good_candidate(
    *,
    candidate_id: str = "cand-1",
    mode: LatentBridgeSynthesisMode = LatentBridgeSynthesisMode.MEASUREMENT_MODEL,
    delta_cv: float = 0.14,
    lower_ci: float = 0.05,
    stability: float = 0.92,
) -> LatentBridgeCandidate:
    return LatentBridgeCandidate(
        candidate_id=candidate_id,
        synthesis_mode=mode,
        heldout_metrics=LatentBridgeHeldoutMetrics(
            delta_cv=delta_cv,
            lower_ci=lower_ci,
            upper_ci=delta_cv + 0.05,
            scoring_rule="loglik",
        ),
        stability_frequency=stability,
        alternative_model_beaten=True,
        post_hoc_modifications=False,
        heywood_improper_solution=False,
        reflective_direction_supported=True,
        falsification_tests=_passing_falsification_pack(),
    )


def _admissible_measurement_evidence(
    *,
    candidate: LatentBridgeCandidate | None = None,
) -> LatentBridgeEvidence:
    return LatentBridgeEvidence(
        measurement_side_a_refs=["ind:a1", "ind:a2"],
        measurement_side_b_refs=["ind:b1", "ind:b2"],
        tetrad_tests_available=True,
        local_dependence_controlled=True,
        reflective_direction_supported=True,
        bridge_model_ref="artifact:bridge-model:1",
        baseline_model_refs=["artifact:baseline:1"],
        candidates=[candidate or _good_candidate()],
    )


# ------------------------------------------------------------------ policy
def test_build_pair_key_is_order_independent() -> None:
    left = build_pair_key("fragA", "var", "fragB", "var")
    right = build_pair_key("fragB", "var", "fragA", "var")
    assert left == right == PAIR_KEY


def test_policy_defaults_fail_closed() -> None:
    policy = LatentBridgeSynthesisPolicy()
    assert policy.enable_auto_latent_bridge is False
    assert policy.opaque_label_required is True
    assert policy.block_on_ambiguity is True


def test_auto_synthesis_disabled_returns_blocked_with_reason() -> None:
    evidence = _admissible_measurement_evidence()
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=LatentBridgeSynthesisPolicy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert LatentBridgeBlockReason.AUTO_SYNTHESIS_DISABLED in hypothesis.block_conditions_checked
    assert hypothesis.latent_label is None
    assert hypothesis.heldout_metrics is None


# ------------------------------------------------------------------ admit path
def test_measurement_mode_admit_path_emits_proposed_hypothesis() -> None:
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=_admissible_measurement_evidence(),
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.PROPOSED
    assert hypothesis.synthesis_mode is LatentBridgeSynthesisMode.MEASUREMENT_MODEL
    assert hypothesis.heldout_metrics is not None
    assert hypothesis.heldout_metrics.lower_ci > 0
    assert hypothesis.falsification_tests
    assert hypothesis.block_conditions_checked == []
    assert hypothesis.latent_label is None
    assert hypothesis.metadata["opaque_label_required"] is True
    assert hypothesis.metadata["semantic_interpretation_confidence"] == "none"
    assert hypothesis.metadata["selected_candidate_id"] == "cand-1"
    assert hypothesis.bridge_id.startswith("latent::bridge::")


def test_proxy_only_admit_path_emits_proposed_hypothesis() -> None:
    evidence = LatentBridgeEvidence(
        proxy_families=[
            LatentBridgeProxyFamily(
                family_id="px1",
                side="a",
                proxy_refs=["proxy:a:1"],
                rank_condition_satisfied=True,
                bridge_operator_built=True,
            ),
            LatentBridgeProxyFamily(
                family_id="px2",
                side="b",
                proxy_refs=["proxy:b:1"],
                rank_condition_satisfied=True,
                bridge_operator_built=True,
            ),
        ],
        candidates=[_good_candidate(mode=LatentBridgeSynthesisMode.PROXY)],
        bridge_model_ref="artifact:bridge-model:proxy",
        baseline_model_refs=["artifact:baseline:p"],
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.PROPOSED
    assert hypothesis.synthesis_mode is LatentBridgeSynthesisMode.PROXY
    assert hypothesis.proxy_refs == ["proxy:a:1", "proxy:b:1"]


# ------------------------------------------------------------------ hard gates
def test_hard_metadata_mismatch_blocks_synthesis() -> None:
    evidence = _admissible_measurement_evidence().model_copy(
        update={"hard_metadata_mismatch": True}
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert LatentBridgeBlockReason.HARD_METADATA_MISMATCH in hypothesis.block_conditions_checked


def test_direction_ambiguity_blocks_synthesis() -> None:
    evidence = _admissible_measurement_evidence().model_copy(
        update={"direction_ambiguity_resolved": False}
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert (
        LatentBridgeBlockReason.DIRECTION_AMBIGUITY_UNRESOLVED
        in hypothesis.block_conditions_checked
    )


# ------------------------------------------------------------------ mode gates
def test_insufficient_indicators_blocks_measurement_mode() -> None:
    evidence = LatentBridgeEvidence(
        measurement_side_a_refs=["ind:a1"],
        measurement_side_b_refs=["ind:b1"],
        tetrad_tests_available=True,
        candidates=[_good_candidate()],
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(allow_proxy_only_mode=False),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    reasons = set(hypothesis.block_conditions_checked)
    assert LatentBridgeBlockReason.NO_ADMISSIBLE_CANDIDATE in reasons or any(
        r in reasons
        for r in (
            LatentBridgeBlockReason.INSUFFICIENT_INDICATORS,
            LatentBridgeBlockReason.INSUFFICIENT_INDICATORS_PER_SIDE,
        )
    )


def test_environment_only_evidence_is_refused_by_default() -> None:
    evidence = LatentBridgeEvidence(
        environment_refs=["env:x", "env:y"],
        invariance_level=LatentBridgeInvarianceLevel.METRIC,
        anchor_items=["item1", "item2"],
        dif_free_anchor_set=True,
        leave_one_anchor_out_stable=True,
        candidates=[_good_candidate(mode=LatentBridgeSynthesisMode.MULTI_ENVIRONMENT)],
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert LatentBridgeBlockReason.ENVIRONMENT_ONLY_EVIDENCE in hypothesis.block_conditions_checked


def test_missing_metric_invariance_blocks_environment_mode_when_scaffold_present() -> None:
    evidence = LatentBridgeEvidence(
        measurement_side_a_refs=["ind:a1", "ind:a2"],
        measurement_side_b_refs=["ind:b1", "ind:b2"],
        tetrad_tests_available=True,
        environment_refs=["env:x", "env:y"],
        invariance_level=LatentBridgeInvarianceLevel.CONFIGURAL,
        anchor_items=["anchor:1", "anchor:2"],
        dif_free_anchor_set=True,
        leave_one_anchor_out_stable=True,
        candidates=[_good_candidate(mode=LatentBridgeSynthesisMode.MEASUREMENT_MODEL)],
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.PROPOSED
    assert hypothesis.synthesis_mode is LatentBridgeSynthesisMode.MEASUREMENT_MODEL


def test_single_proxy_family_blocks_proxy_mode() -> None:
    evidence = LatentBridgeEvidence(
        proxy_families=[
            LatentBridgeProxyFamily(
                family_id="px1",
                side="a",
                proxy_refs=["proxy:a:1"],
                rank_condition_satisfied=True,
                bridge_operator_built=True,
            )
        ],
        candidates=[_good_candidate(mode=LatentBridgeSynthesisMode.PROXY)],
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert (
        LatentBridgeBlockReason.NO_ADMISSIBLE_CANDIDATE in hypothesis.block_conditions_checked
        or LatentBridgeBlockReason.INSUFFICIENT_PROXY_FAMILIES
        in hypothesis.block_conditions_checked
    )


def test_proxy_rank_condition_failure_is_captured() -> None:
    evidence = LatentBridgeEvidence(
        proxy_families=[
            LatentBridgeProxyFamily(
                family_id="px1",
                side="a",
                proxy_refs=["proxy:a:1"],
                rank_condition_satisfied=False,
                bridge_operator_built=True,
            ),
            LatentBridgeProxyFamily(
                family_id="px2",
                side="b",
                proxy_refs=["proxy:b:1"],
                rank_condition_satisfied=True,
                bridge_operator_built=False,
            ),
        ],
        candidates=[_good_candidate(mode=LatentBridgeSynthesisMode.PROXY)],
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    reasons = set(hypothesis.block_conditions_checked)
    assert LatentBridgeBlockReason.PROXY_RANK_CONDITION_FAILED in reasons
    assert LatentBridgeBlockReason.BRIDGE_OPERATOR_NOT_BUILT in reasons


# ------------------------------------------------------------------ candidate gates
def test_nonpositive_heldout_lower_ci_blocks_candidate() -> None:
    evidence = _admissible_measurement_evidence(
        candidate=_good_candidate(lower_ci=-0.01, delta_cv=0.05),
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert (
        LatentBridgeBlockReason.HELDOUT_IMPROVEMENT_NONPOSITIVE
        in hypothesis.block_conditions_checked
    )


def test_bootstrap_instability_blocks_candidate() -> None:
    evidence = _admissible_measurement_evidence(
        candidate=_good_candidate(stability=0.40),
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert LatentBridgeBlockReason.BOOTSTRAP_INSTABILITY in hypothesis.block_conditions_checked


def test_alternative_model_not_beaten_blocks_candidate() -> None:
    evidence = _admissible_measurement_evidence(
        candidate=_good_candidate().model_copy(update={"alternative_model_beaten": False}),
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert (
        LatentBridgeBlockReason.ALTERNATIVE_MODEL_NOT_BEATEN in hypothesis.block_conditions_checked
    )


def test_post_hoc_modifications_block_candidate() -> None:
    evidence = _admissible_measurement_evidence(
        candidate=_good_candidate().model_copy(update={"post_hoc_modifications": True}),
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert LatentBridgeBlockReason.POST_HOC_MODIFICATIONS in hypothesis.block_conditions_checked


def test_heywood_improper_solution_blocks_candidate() -> None:
    evidence = _admissible_measurement_evidence(
        candidate=_good_candidate().model_copy(update={"heywood_improper_solution": True}),
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert LatentBridgeBlockReason.HEYWOOD_IMPROPER_SOLUTION in hypothesis.block_conditions_checked


def test_failing_falsification_test_blocks_candidate() -> None:
    evidence = _admissible_measurement_evidence(
        candidate=_good_candidate().model_copy(
            update={
                "falsification_tests": [
                    LatentBridgeFalsificationTest(
                        test_family=LatentBridgeFalsificationTestFamily.CTA,
                        status=LatentBridgeFalsificationTestStatus.FAIL,
                        p_value=0.001,
                    )
                ]
            }
        ),
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED
    assert LatentBridgeBlockReason.FALSIFICATION_TEST_FAILED in hypothesis.block_conditions_checked


# ------------------------------------------------------------------ ambiguity
def test_multiple_surviving_candidates_yield_blocked_ambiguous() -> None:
    evidence = _admissible_measurement_evidence().model_copy(
        update={
            "candidates": [
                _good_candidate(candidate_id="cand-a"),
                _good_candidate(candidate_id="cand-b"),
            ]
        }
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(),
    )
    assert hypothesis.status is LatentBridgeStatus.BLOCKED_AMBIGUOUS
    assert (
        LatentBridgeBlockReason.AMBIGUOUS_COMPETING_LATENTS in hypothesis.block_conditions_checked
    )
    assert hypothesis.metadata["surviving_candidate_ids"] == ["cand-a", "cand-b"]


def test_block_on_ambiguity_disabled_picks_first_survivor() -> None:
    evidence = _admissible_measurement_evidence().model_copy(
        update={
            "candidates": [
                _good_candidate(candidate_id="cand-a"),
                _good_candidate(candidate_id="cand-b"),
            ]
        }
    )
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=evidence,
        policy=_accept_policy(block_on_ambiguity=False),
    )
    assert hypothesis.status is LatentBridgeStatus.PROPOSED
    assert hypothesis.metadata["selected_candidate_id"] == "cand-a"


# ------------------------------------------------------------------ invariants
def test_hypothesis_rejects_semantic_label_by_default() -> None:
    with pytest.raises(ValueError, match="latent_label is only permitted"):
        LatentBridgeHypothesis(
            bridge_id="latent::bridge::x",
            pair_key=PAIR_KEY,
            status=LatentBridgeStatus.PROPOSED,
            synthesis_mode=LatentBridgeSynthesisMode.MEASUREMENT_MODEL,
            latent_label="civic_trust",
            heldout_metrics=LatentBridgeHeldoutMetrics(delta_cv=0.1, lower_ci=0.01),
            falsification_tests=_passing_falsification_pack(),
            metadata={
                "opaque_label_required": True,
                "semantic_interpretation_confidence": "none",
            },
        )


def test_proposed_hypothesis_requires_falsification_pack() -> None:
    with pytest.raises(ValueError, match="falsification pack"):
        LatentBridgeHypothesis(
            bridge_id="latent::bridge::x",
            pair_key=PAIR_KEY,
            status=LatentBridgeStatus.PROPOSED,
            synthesis_mode=LatentBridgeSynthesisMode.MEASUREMENT_MODEL,
            heldout_metrics=LatentBridgeHeldoutMetrics(delta_cv=0.1, lower_ci=0.01),
            falsification_tests=[],
        )


def test_blocked_hypothesis_requires_block_condition() -> None:
    with pytest.raises(ValueError, match="BLOCKED latent bridge"):
        LatentBridgeHypothesis(
            bridge_id="latent::bridge::x",
            pair_key=PAIR_KEY,
            status=LatentBridgeStatus.BLOCKED,
            synthesis_mode=LatentBridgeSynthesisMode.NONE,
            block_conditions_checked=[],
        )


def test_variable_alignment_certificate_requires_latent_bridge_contract() -> None:
    with pytest.raises(
        ValueError,
        match="latent_bridge_hypothesis_ref or latent_bridge_ref must be non-empty",
    ):
        VariableAlignmentCertificate(
            variable_a="v",
            fragment_a_id="fragA",
            variable_b="v",
            fragment_b_id="fragB",
            alignment_type=AlignmentType.LATENT_BRIDGE,
            latent_bridge_ref=None,
            reviewer=AlignmentReviewerState.PENDING_REVIEW,
        )


# ------------------------------------------------------------------ persistence
def test_latent_bridge_hypothesis_round_trip_through_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    hypothesis = synthesize_latent_bridge(
        pair_key=PAIR_KEY,
        evidence=_admissible_measurement_evidence(),
        policy=_accept_policy(),
    )
    ref = persist_latent_bridge_hypothesis(store, hypothesis)
    assert isinstance(ref, LatentBridgeHypothesisRef)
    assert ref.kind == "ir.latent_bridge_hypothesis"
    loaded = load_latent_bridge_hypothesis(store, ref)
    assert loaded == hypothesis


# ------------------------------------------------------------------ verify integration
def _pair_fragments() -> tuple[SCMFragment, SCMFragment]:
    fragment_a = SCMFragment(
        fragment_id="labor",
        graph_ref="artifact:graph:labor",
        semantic_namespace="policy.labor",
        interface_variables=["civic_trust_index"],
        exposed_outputs=["civic_trust_index"],
        variable_definitions={"civic_trust_index": "Composite civic trust index"},
    )
    fragment_b = SCMFragment(
        fragment_id="health",
        graph_ref="artifact:graph:health",
        semantic_namespace="policy.health",
        interface_variables=["civic_trust_index"],
        exposed_inputs=["civic_trust_index"],
        variable_definitions={"civic_trust_index": "Composite civic trust index"},
    )
    return fragment_a, fragment_b


def test_verify_fragment_alignment_emits_auto_latent_bridge_when_policy_enabled(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    fragment_a, fragment_b = _pair_fragments()
    pair_key = build_pair_key(
        fragment_a.fragment_id,
        "civic_trust_index",
        fragment_b.fragment_id,
        "civic_trust_index",
    )
    evidence = _admissible_measurement_evidence()
    config = AlignmentVerificationConfig(
        latent_bridge_policy=_accept_policy(),
        latent_bridge_evidence={pair_key: evidence},
    )
    report, _mapping = _verify_fragment_bundle_alignment_with_governance(
        [fragment_a, fragment_b],
        config=config,
        artifact_store=store,
    )

    certificate = report.per_variable_certificates[0]
    assert certificate.alignment_type is AlignmentType.LATENT_BRIDGE
    assert certificate.latent_bridge_hypothesis_ref is not None
    assert certificate.latent_bridge_ref is None
    assert any(
        assumption.startswith("latent_bridge:auto:")
        for assumption in certificate.assumptions_introduced
    )
    snapshot = certificate.metadata["latent_bridge_status_snapshot"]
    assert snapshot["status"] == "proposed"
    assert snapshot["metadata"]["opaque_label_required"] is True
    loaded = load_latent_bridge_hypothesis(store, certificate.latent_bridge_hypothesis_ref)
    assert loaded.bridge_id.startswith("latent::bridge::")
    assert loaded.promotion_evidence is None
    assert loaded.promotion_verdict is None
    assert loaded.readiness_cap == "proof_only"
    assert loaded.promotion_allowed is False
    assert certificate.reviewer is AlignmentReviewerState.PENDING_REVIEW
    assert report.review_status is AlignmentReviewStatus.PENDING_REVIEW


def test_verify_fragment_alignment_requires_artifact_store_for_auto_latent_bridge() -> None:
    fragment_a, fragment_b = _pair_fragments()
    pair_key = build_pair_key(
        fragment_a.fragment_id,
        "civic_trust_index",
        fragment_b.fragment_id,
        "civic_trust_index",
    )
    config = AlignmentVerificationConfig(
        latent_bridge_policy=_accept_policy(),
        latent_bridge_evidence={pair_key: _admissible_measurement_evidence()},
    )

    with pytest.raises(
        ValueError,
        match="artifact_store is required to persist governed latent bridge hypotheses",
    ):
        _verify_fragment_bundle_alignment_with_governance(
            [fragment_a, fragment_b],
            config=config,
        )


def test_legacy_latent_bridge_cannot_activate_governed_alignment() -> None:
    fragment_a, fragment_b = _pair_fragments()
    pair_key = build_pair_key(
        fragment_a.fragment_id,
        "civic_trust_index",
        fragment_b.fragment_id,
        "civic_trust_index",
    )
    config = AlignmentVerificationConfig(
        explicit_latent_bridges={pair_key: "artifact:manual:bridge"},
        latent_bridge_policy=_accept_policy(),
        latent_bridge_evidence={pair_key: _admissible_measurement_evidence()},
    )
    report, _ = verify_fragment_alignment(fragment_a, fragment_b, config=config)

    certificate = report.per_variable_certificates[0]
    assert certificate.alignment_type is not AlignmentType.LATENT_BRIDGE
    assert certificate.latent_bridge_hypothesis_ref is None
    assert certificate.latent_bridge_ref is None
    assert certificate.metadata["legacy_latent_bridge_ref"] == "artifact:manual:bridge"
    assert certificate.metadata["latent_bridge_governance"]["promotion_allowed"] is False
    assert not any(
        assumption.startswith("latent_bridge:auto:")
        for assumption in certificate.assumptions_introduced
    )


def test_explicit_typed_latent_bridge_ref_is_canonical(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    fragment_a, fragment_b = _pair_fragments()
    pair_key = build_pair_key(
        fragment_a.fragment_id,
        "civic_trust_index",
        fragment_b.fragment_id,
        "civic_trust_index",
    )
    hypothesis = persist_latent_bridge_hypothesis(
        store,
        synthesize_latent_bridge(
            pair_key=pair_key,
            evidence=_admissible_measurement_evidence(),
            policy=_accept_policy(),
        ),
    )
    config = AlignmentVerificationConfig(
        explicit_latent_bridges={pair_key: hypothesis},
        latent_bridge_policy=_accept_policy(),
        latent_bridge_evidence={pair_key: _admissible_measurement_evidence()},
    )

    report, _ = _verify_fragment_bundle_alignment_with_governance(
        [fragment_a, fragment_b],
        config=config,
        artifact_store=store,
    )

    certificate = report.per_variable_certificates[0]
    assert certificate.alignment_type is AlignmentType.LATENT_BRIDGE
    assert certificate.latent_bridge_hypothesis_ref is not None
    assert certificate.latent_bridge_ref is None
    provenance = certificate.metadata["latent_governance_provenance"]
    assert provenance["candidate_artifact_content_hash"] == str(hypothesis.artifact_id)
    assert provenance["governed_content_hash"] == str(
        certificate.latent_bridge_hypothesis_ref.artifact_id
    )
    governed = load_latent_bridge_hypothesis(store, certificate.latent_bridge_hypothesis_ref)
    assert governed.metadata["latent_governance"]["promotion_allowed"] is False


def test_verify_fragment_alignment_blocks_auto_synthesis_when_evidence_missing() -> None:
    fragment_a, fragment_b = _pair_fragments()
    config = AlignmentVerificationConfig(latent_bridge_policy=_accept_policy())
    report, _ = verify_fragment_alignment(fragment_a, fragment_b, config=config)

    certificate = report.per_variable_certificates[0]
    assert certificate.alignment_type is not AlignmentType.LATENT_BRIDGE
    assert "latent_bridge_status_snapshot" not in certificate.metadata


def test_verify_fragment_alignment_records_blocked_snapshot_when_candidate_fails() -> None:
    fragment_a, fragment_b = _pair_fragments()
    pair_key = build_pair_key(
        fragment_a.fragment_id,
        "civic_trust_index",
        fragment_b.fragment_id,
        "civic_trust_index",
    )
    failing_evidence = _admissible_measurement_evidence(
        candidate=_good_candidate(lower_ci=-0.1, delta_cv=0.0),
    )
    config = AlignmentVerificationConfig(
        latent_bridge_policy=_accept_policy(),
        latent_bridge_evidence={pair_key: failing_evidence},
    )
    report, _ = verify_fragment_alignment(fragment_a, fragment_b, config=config)

    certificate = report.per_variable_certificates[0]
    assert certificate.alignment_type is not AlignmentType.LATENT_BRIDGE
    snapshot = certificate.metadata["latent_bridge_status_snapshot"]
    assert snapshot["status"] == "blocked"
    assert any(
        reason == LatentBridgeBlockReason.HELDOUT_IMPROVEMENT_NONPOSITIVE.value
        for reason in snapshot["block_conditions_checked"]
    )
