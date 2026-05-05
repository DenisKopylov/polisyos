from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    negative_certificate_from_bridge_plausibility_report,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
    annotate_bounds_bundle_for_proximal_bridge_failure,
    bounds_bundle_from_partial_identification_result,
)
from polisyos.ir.analytics.proximal import (
    BridgeFailureMode,
    BridgeFallbackDisposition,
    BridgePlausibilityReport,
    BridgePlausibilitySeverity,
    load_bridge_plausibility_report,
    persist_bridge_plausibility_report,
)


def _partial_bounds() -> PartialIdentificationResult:
    return PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=-0.2,
        upper_bound=0.6,
        confidence=0.9,
    )


def test_bridge_plausibility_report_derives_block_on_infeasible_red() -> None:
    report = BridgePlausibilityReport(
        equation_type="outcome_bridge",
        residual_r=0.38,
        residual_interval=(0.22, 0.44),
        bridge_existence_supported=False,
        completeness_plausible=False,
        suspected_failure_mode=BridgeFailureMode.INFEASIBLE_EQUATION,
        severity=BridgePlausibilitySeverity.RED,
        reasons=("heldout_residual_large",),
    )

    assert report.fallback_disposition is BridgeFallbackDisposition.BLOCK_POINT_ESTIMATE


def test_bridge_plausibility_report_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = BridgePlausibilityReport(
        equation_type="both",
        residual_r=0.04,
        residual_interval=(0.01, 0.08),
        effective_rank=3.0,
        sigma_min=0.11,
        ill_posedness_index=15.0,
        proxy_association_score=0.42,
        bridge_existence_supported=True,
        completeness_plausible=True,
        suspected_failure_mode=BridgeFailureMode.NONE,
        severity=BridgePlausibilitySeverity.GREEN,
        reasons=("stable_sieve_projection",),
    )

    ref = persist_bridge_plausibility_report(store, report)
    loaded = load_bridge_plausibility_report(store, ref)

    assert loaded == report


def test_annotate_bounds_bundle_for_proximal_bridge_failure_adds_metadata() -> None:
    bundle = bounds_bundle_from_partial_identification_result(_partial_bounds())
    report = BridgePlausibilityReport(
        equation_type="outcome_bridge",
        residual_r=0.08,
        effective_rank=1.0,
        sigma_min=0.002,
        ill_posedness_index=420.0,
        bridge_existence_supported=True,
        completeness_plausible=False,
        functional_invariant_to_nonuniqueness=False,
        suspected_failure_mode=BridgeFailureMode.WEAK_COMPLETENESS,
        severity=BridgePlausibilitySeverity.YELLOW,
        reasons=("weak_proxy_rank",),
        recommended_rescue_actions=("Add another independent proxy family.",),
    )

    annotated = annotate_bounds_bundle_for_proximal_bridge_failure(bundle, report)

    assert "proximal_completeness_unlikely" in annotated.warnings
    assert "proximal_bounds_required" in annotated.warnings
    assert "Add another independent proxy family." in annotated.rescue_actions
    assert annotated.metadata["proximal_bridge_failure_mode"] == "weak_completeness"
    assert annotated.metadata["proximal_fallback_disposition"] == "require_bounds"


def test_negative_certificate_from_bridge_plausibility_builds_infeasible_blocker() -> None:
    report = BridgePlausibilityReport(
        equation_type="outcome_bridge",
        residual_r=0.31,
        residual_interval=(0.24, 0.39),
        bridge_existence_supported=False,
        completeness_plausible=False,
        suspected_failure_mode=BridgeFailureMode.INFEASIBLE_EQUATION,
        severity=BridgePlausibilitySeverity.RED,
        reasons=("projection_residual_nonzero",),
        recommended_rescue_actions=("Fall back to a certified bounds bundle.",),
    )

    cert = negative_certificate_from_bridge_plausibility_report(
        report,
        partial_bounds=_partial_bounds(),
        missing_vars=("Z", "W"),
    )

    assert cert.blocking_type is BlockingType.BRIDGE_EQUATION_INFEASIBLE
    assert cert.bounds_bundle is not None
    assert "proximal_bridge_equation_infeasible" in cert.bounds_bundle.warnings
    assert "proximal_point_estimate_blocked" in cert.bounds_bundle.warnings
    assert cert.quantitative_diagnostics["bridge_failure_mode"] == "infeasible_equation"
    assert cert.recovery_plan is not None


def test_negative_certificate_from_bridge_plausibility_uses_completeness_blocker() -> None:
    report = BridgePlausibilityReport(
        equation_type="treatment_bridge",
        residual_r=0.07,
        residual_interval=(0.02, 0.09),
        effective_rank=1.0,
        sigma_min=0.004,
        bridge_existence_supported=True,
        completeness_plausible=False,
        functional_invariant_to_nonuniqueness=False,
        suspected_failure_mode=BridgeFailureMode.NONUNIQUE_SOLUTION,
        severity=BridgePlausibilitySeverity.YELLOW,
        reasons=("functional_depends_on_kernel_choice",),
    )

    cert = negative_certificate_from_bridge_plausibility_report(
        report,
        bounds_bundle=bounds_bundle_from_partial_identification_result(_partial_bounds()),
    )

    assert cert.blocking_type is BlockingType.COMPLETENESS_UNLIKELY
    assert cert.bounds_bundle is not None
    assert "proximal_bounds_required" in cert.bounds_bundle.warnings
