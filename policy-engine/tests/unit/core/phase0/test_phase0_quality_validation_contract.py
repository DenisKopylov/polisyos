from __future__ import annotations

from polisyos.data_forge.kernel.quality import evaluate_phase0_quality


def test_phase0_quality_validation_passes_with_threshold_compliant_metrics() -> None:
    report = evaluate_phase0_quality(
        article_count=50,
        claims_count=220,
        parameters_count=140,
        canonical_claim_variable_pct=85.0,
        alignment_seed_parity_pct=100.0,
        hard_constraints_present=True,
        hard_constraint_block_signal=True,
        dataset_coverage_pct=80.0,
        proxy_share_pct=20.0,
        temporal_extrapolation_share_pct=10.0,
    )
    assert report.passed is True
    assert report.critical_failed == []


def test_phase0_quality_validation_fails_without_block_signal_for_hard_constraints() -> None:
    report = evaluate_phase0_quality(
        article_count=50,
        claims_count=220,
        parameters_count=140,
        canonical_claim_variable_pct=85.0,
        alignment_seed_parity_pct=100.0,
        hard_constraints_present=True,
        hard_constraint_block_signal=False,
    )
    assert report.passed is False
    assert any(
        check.name == "hard_constraint_block_signal" and not check.passed for check in report.checks
    )
