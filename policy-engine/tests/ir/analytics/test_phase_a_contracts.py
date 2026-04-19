from __future__ import annotations

from types import SimpleNamespace

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
from polisyos.ir.analytics.causal import (
    build_data_readiness_report,
    load_data_readiness_report,
    load_proof_bundle,
    persist_data_readiness_report,
    persist_proof_bundle,
    proof_bundle_from_identification_result,
)
from polisyos.ir.analytics.dynamic_causal_semantics import (
    DynamicReductionStatus,
    DynamicSemanticsAttachment,
    DynamicSemanticsFamily,
    GraphicalMarkovCertificate,
    GraphicalOracleKind,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsReport,
    PartialIdentificationResult,
    bounds_bundle_from_bounds_report,
    load_bounds_bundle,
    persist_bounds_bundle,
)


def _partial(lower: float, upper: float, *, method: BoundMethod) -> PartialIdentificationResult:
    return PartialIdentificationResult(
        method=method,
        lower_bound=lower,
        upper_bound=upper,
        confidence=0.9,
    )


def test_proof_bundle_translation_preserves_identified_status() -> None:
    result = SimpleNamespace(
        status=IdentificationStatus.IDENTIFIED,
        algorithm_version="id_v1",
        estimand_ast=None,
        trace=["rule1", "rule2"],
        query_str="P(Y|do(X))",
        required_distributions=[],
    )

    bundle = proof_bundle_from_identification_result(result)

    assert bundle.proof_status == "identified"
    assert bundle.completeness_regime == "complete"
    assert bundle.proof_trace == ["rule1", "rule2"]


def test_proof_bundle_translation_marks_dynamic_cyclic_path_as_heuristic() -> None:
    result = SimpleNamespace(
        status=IdentificationStatus.IDENTIFIED,
        algorithm_version="cyclic_id_experimental_v1",
        estimand_ast=None,
        trace=["cyclic-start", "sigma-check"],
        query_str="P(Y|cyclic do(X))",
        required_distributions=[],
        metadata={
            "dynamic_semantics": DynamicSemanticsAttachment(
                semantics_family=DynamicSemanticsFamily.IOSCM,
                reduction_status=DynamicReductionStatus.HEURISTIC_ONLY,
                markov_criterion_certificate=GraphicalMarkovCertificate(
                    semantics_family=DynamicSemanticsFamily.IOSCM,
                    graphical_oracle=GraphicalOracleKind.SIGMA,
                    theorem_family="Forre-Mooij-2018",
                ),
            ).model_dump(mode="json")
        },
    )

    bundle = proof_bundle_from_identification_result(result)

    assert bundle.proof_status == "identified"
    assert bundle.proof_stratum == "A1_dynamic"
    assert bundle.completeness_regime == "heuristic_backed"
    assert bundle.dynamic_semantics is not None
    assert bundle.dynamic_semantics.reduction_status is DynamicReductionStatus.HEURISTIC_ONLY


def test_bounds_bundle_translation_preserves_consensus_and_gates_sharpness_on_certificate() -> None:
    report = BoundsReport(
        estimand_type="ate",
        results=[
            _partial(-0.5, 0.8, method=BoundMethod.MANSKI),
            PartialIdentificationResult(
                method=BoundMethod.LP_BALKE_PEARL,
                lower_bound=-0.1,
                upper_bound=0.4,
                confidence=0.9,
                bounds_type="sharp_lp",
            ),
        ],
    )

    bundle = bounds_bundle_from_bounds_report(report)

    assert bundle.lower_bound == report.tightest_lower
    assert bundle.upper_bound == report.tightest_upper
    assert bundle.consensus_lower == report.consensus_lower
    assert bundle.consensus_upper == report.consensus_upper
    assert bundle.sharpness_status == "unknown"


def test_data_readiness_thresholds_block_warn_unknown() -> None:
    blocked = build_data_readiness_report(
        positivity={
            "passes_positivity": False,
            "min_propensity_observed": 0.0,
            "max_propensity_observed": 1.0,
            "effective_sample_size": 10.0,
            "ess_fraction": 0.2,
            "overlap_score": 0.4,
            "n_obs": 100,
        },
        sample_size=100,
        fallback_data_available=True,
    )
    warned = build_data_readiness_report(
        sample_size=40,
        measurement_quality="unknown",
        fallback_data_available=True,
    )
    unknown = build_data_readiness_report()

    assert blocked.decision == "block"
    assert warned.decision == "warn"
    assert warned.can_run_estimation is True
    assert unknown.decision == "unknown"
    assert unknown.can_run_estimation is False


def test_recoverability_certificate_embeds_in_proof_and_readiness() -> None:
    from polisyos.ir.analytics.recoverability import (
        MinimalRepairSet,
        RecoverabilityCertificate,
        RecoverabilityCertificateStatus,
        RecoveryScope,
        RepairSetTestability,
        RepairSetType,
    )

    certificate = RecoverabilityCertificate(
        target_query="P(Y|do(X))",
        mgraph_fingerprint="sha256:test",
        status=RecoverabilityCertificateStatus.RECOVERABLE_UNDER_ASSUMPTIONS,
        recovery_scope=RecoveryScope.CAUSAL_QUERY,
        blocking_r_nodes=("R_X",),
        minimal_repair_sets=(
            MinimalRepairSet(
                repair_type=RepairSetType.ASSUMPTION,
                items=("remove_edge(X -> R_X)",),
                testability=RepairSetTestability.NOT_TESTABLE,
            ),
        ),
        warnings=("assumption_dependent_missingness_recovery",),
    )
    result = SimpleNamespace(
        status=IdentificationStatus.IDENTIFIED,
        algorithm_version="id_v1",
        estimand_ast=None,
        trace=[],
        query_str="P(Y|do(X))",
        required_distributions=[],
    )

    proof = proof_bundle_from_identification_result(
        result,
        recoverability_certificate=certificate,
    )
    readiness = build_data_readiness_report(
        recoverability_certificate=certificate,
        fallback_data_available=True,
    )

    assert proof.metadata["recoverability"]["status"] == "recoverable_under_assumptions"
    assert proof.metadata["recoverability"]["blocking_r_nodes"] == ["R_X"]
    assert readiness.decision == "warn"
    assert readiness.can_run_estimation is True
    assert "assumption_dependent_missingness_recovery" in readiness.warnings
    assert readiness.recoverability is not None


def test_data_readiness_blocks_not_recoverable_missingness() -> None:
    from polisyos.ir.analytics.recoverability import (
        RecoverabilityCertificate,
        RecoverabilityCertificateStatus,
        RecoveryScope,
    )

    certificate = RecoverabilityCertificate(
        target_query="P(Y|do(X))",
        mgraph_fingerprint="sha256:test",
        status=RecoverabilityCertificateStatus.NOT_RECOVERABLE,
        recovery_scope=RecoveryScope.CAUSAL_QUERY,
        blocking_r_nodes=("R_X",),
    )

    readiness = build_data_readiness_report(
        recoverability_certificate=certificate,
        fallback_data_available=True,
    )

    assert readiness.decision == "block"
    assert readiness.can_run_estimation is False
    assert "not_recoverable_missingness" in readiness.blocking_reasons


def test_data_readiness_marks_malformed_positivity_as_warning_not_absence() -> None:
    malformed = build_data_readiness_report(
        positivity={"passes_positivity": "bad"},
        fallback_data_available=True,
    )

    assert malformed.decision == "warn"
    assert "positivity_parse_failed" in malformed.warnings


def test_canonical_artifacts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    proof = proof_bundle_from_identification_result(
        SimpleNamespace(
            status=IdentificationStatus.IDENTIFIED,
            algorithm_version="id_v1",
            estimand_ast=None,
            trace=["rule1"],
            query_str="P(Y|do(X))",
            required_distributions=[],
        )
    )
    bounds = bounds_bundle_from_bounds_report(
        BoundsReport(
            estimand_type="ate",
            results=[_partial(-0.2, 0.4, method=BoundMethod.MANSKI)],
        )
    )
    readiness = build_data_readiness_report(
        sample_size=120,
        measurement_quality="known_good",
        fallback_data_available=True,
    )

    proof_ref = persist_proof_bundle(store, proof)
    bounds_ref = persist_bounds_bundle(store, bounds)
    readiness_ref = persist_data_readiness_report(store, readiness)

    assert load_proof_bundle(store, proof_ref) == proof
    assert load_bounds_bundle(store, bounds_ref) == bounds
    assert load_data_readiness_report(store, readiness_ref) == readiness
