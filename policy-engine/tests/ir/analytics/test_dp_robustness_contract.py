from __future__ import annotations

import math

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.dp_robustness import (
    DPGraphProvenance,
    DPGraphProvenanceSource,
    DPHardBlock,
    DPHardBlockReason,
    DPEffectiveValidity,
    DPLocalStability,
    DPMechanismFamily,
    DPMechanismSpec,
    DPProofStepKind,
    DPProofTraceAuditStep,
    DPReleasedStatistics,
    DPReleaseScope,
    DPRobustnessStatus,
    DPSensitivityNorm,
    apply_dp_readiness_gate,
    attach_dp_robustness_to_proof_bundle,
    build_dp_distortion_model,
    build_dp_robustness_certificate,
    laplace_histogram_linf_radius,
    load_dp_robustness_certificate,
    persist_dp_robustness_certificate,
)
from polisyos.ir.analytics.causal import build_data_readiness_report


def _proof_bundle() -> ProofBundle:
    return ProofBundle(
        proof_status="identified",
        proof_stratum="A0_trusted",
        theorem_family="id_v1",
        completeness_regime="complete",
        implementation_coverage="declared-scope:id_v1",
        proof_trace=["d-separation", "divide"],
        metadata={"status": "identified"},
    )


def _laplace_mechanism(*, epsilon: float = 2.0) -> DPMechanismSpec:
    return DPMechanismSpec(
        family=DPMechanismFamily.LAPLACE,
        epsilon=epsilon,
        sensitivity_norm=DPSensitivityNorm.L1,
        sensitivity_value=1.0,
    )


def _release_scope(*, n: int = 10_000, k: int = 16) -> DPReleaseScope:
    return DPReleaseScope(
        released_statistics=DPReleasedStatistics.FULL_HISTOGRAM,
        cell_count_k=k,
        sample_size_n=n,
    )


def test_laplace_histogram_radius_matches_stage_15_formula() -> None:
    radius = laplace_histogram_linf_radius(
        alpha=0.01,
        cell_count_k=16,
        sample_size_n=10_000,
        epsilon=2.0,
    )

    assert radius == math.log(16 / 0.01) / 20_000


def test_dp_certificate_keeps_structural_proof_but_blocks_support_failure() -> None:
    mechanism = _laplace_mechanism()
    release_scope = _release_scope(n=1_000, k=64)
    distortion = build_dp_distortion_model(mechanism, release_scope, alpha=0.01)
    certificate = build_dp_robustness_certificate(
        proof_status="identified",
        mechanism=mechanism,
        release_scope=release_scope,
        graph_provenance=DPGraphProvenance(
            source=DPGraphProvenanceSource.TRUSTED_EXTERNAL,
            graph_ref="sha256:graph",
        ),
        distortion_model=distortion,
        proof_trace_audit=[
            DPProofTraceAuditStep(
                step_id="s1",
                kind=DPProofStepKind.GRAPH_ONLY,
                operation="d_separation",
                robust=True,
            ),
            DPProofTraceAuditStep(
                step_id="s2",
                kind=DPProofStepKind.ALGEBRAIC,
                operation="divide",
                robust=True,
                requires_margin=True,
                margin_certified=True,
            ),
        ],
        local_stability=DPLocalStability(
            min_denominator_margin=distortion.radius,
            lipschitz_upper_bound=2.0,
            policy_tolerance=0.01,
        ),
    )

    assert certificate.effective_validity.status is DPRobustnessStatus.BLOCKED
    assert certificate.hard_block.block_reason_code is not None
    assert certificate.hard_block.block_reason_code.value == "support_margin_failed"


def test_dp_certificate_degrades_to_bounded_when_tolerance_is_not_met() -> None:
    mechanism = _laplace_mechanism(epsilon=0.5)
    release_scope = _release_scope(n=1_000, k=32)
    distortion = build_dp_distortion_model(mechanism, release_scope, alpha=0.01)
    certificate = build_dp_robustness_certificate(
        proof_status="identified",
        mechanism=mechanism,
        release_scope=release_scope,
        graph_provenance=DPGraphProvenance(
            source=DPGraphProvenanceSource.TRUSTED_EXTERNAL,
        ),
        distortion_model=distortion,
        local_stability=DPLocalStability(
            min_denominator_margin=1.0,
            lipschitz_upper_bound=100.0,
            policy_tolerance=0.001,
        ),
    )

    assert certificate.effective_validity.status is DPRobustnessStatus.BOUNDED
    assert certificate.hard_block.blocked is False
    assert certificate.amplification_requirements.sample_size_amplification_required is True


def test_uncertified_ci_step_hard_blocks_private_discovery() -> None:
    mechanism = _laplace_mechanism()
    release_scope = _release_scope()
    certificate = build_dp_robustness_certificate(
        proof_status="identified",
        mechanism=mechanism,
        release_scope=release_scope,
        graph_provenance=DPGraphProvenance(
            source=DPGraphProvenanceSource.LEARNED_PRIVATE,
        ),
        distortion_model=build_dp_distortion_model(mechanism, release_scope, alpha=0.01),
        proof_trace_audit=[
            DPProofTraceAuditStep(
                step_id="ci-1",
                kind=DPProofStepKind.THRESHOLD_TEST,
                operation="ci_test",
                robust=False,
            )
        ],
        local_stability=DPLocalStability(
            min_denominator_margin=1.0,
            lipschitz_upper_bound=1.0,
            policy_tolerance=1.0,
        ),
    )

    assert certificate.effective_validity.status is DPRobustnessStatus.BLOCKED
    assert certificate.hard_block.block_reason_code is not None
    assert certificate.hard_block.block_reason_code.value == "naive_ci_on_private_data"


def test_dp_certificate_round_trip_and_proof_bundle_metadata_attachment(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    mechanism = _laplace_mechanism(epsilon=8.0)
    release_scope = _release_scope(n=100_000, k=8)
    certificate = build_dp_robustness_certificate(
        proof_status="identified",
        mechanism=mechanism,
        release_scope=release_scope,
        graph_provenance=DPGraphProvenance(
            source=DPGraphProvenanceSource.TRUSTED_EXTERNAL,
        ),
        distortion_model=build_dp_distortion_model(mechanism, release_scope, alpha=0.01),
        local_stability=DPLocalStability(
            min_denominator_margin=0.10,
            lipschitz_upper_bound=2.0,
            policy_tolerance=0.01,
        ),
    )

    ref = persist_dp_robustness_certificate(store, certificate)
    loaded = load_dp_robustness_certificate(store, ref)
    attached = attach_dp_robustness_to_proof_bundle(_proof_bundle(), ref, loaded)

    assert loaded == certificate
    assert attached.proof_status == "identified"
    assert attached.dp_robustness_ref == ref
    assert attached.metadata["dp_effective_status"] == "identified"
    assert attached.metadata["dp_robustness_ref"]["kind"] == "ir.dp_robustness_certificate"


def test_apply_dp_readiness_gate_blocks_execution_for_hard_block_certificate() -> None:
    mechanism = _laplace_mechanism()
    release_scope = _release_scope()
    certificate = build_dp_robustness_certificate(
        proof_status="identified",
        mechanism=mechanism,
        release_scope=release_scope,
        graph_provenance=DPGraphProvenance(
            source=DPGraphProvenanceSource.TRUSTED_EXTERNAL,
        ),
        distortion_model=build_dp_distortion_model(mechanism, release_scope, alpha=0.01),
        local_stability=DPLocalStability(
            min_denominator_margin=0.01,
            lipschitz_upper_bound=1.0,
            policy_tolerance=1.0,
        ),
    ).model_copy(
        update={
            "effective_validity": DPEffectiveValidity(
                status=DPRobustnessStatus.BLOCKED,
                reason="DP support margin failed",
                tolerance_met=False,
            ),
            "hard_block": DPHardBlock(
                blocked=True,
                block_reason_code=DPHardBlockReason.SUPPORT_MARGIN_FAILED,
            ),
        }
    )

    gated = apply_dp_readiness_gate(
        build_data_readiness_report(
            sample_size=500,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        certificate,
    )

    assert gated.decision == "block"
    assert gated.can_compile_estimation is False
    assert gated.can_run_estimation is False
    assert "support_margin_failed" in gated.blocking_reasons
    assert gated.dp_distortion is not None
    assert gated.dp_distortion["effective_status"] == "blocked"
