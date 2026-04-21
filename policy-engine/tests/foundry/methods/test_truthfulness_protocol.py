from __future__ import annotations

from polisyos.core.contracts.execution_plan import MethodCatalogEntry
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
    reconcile_truthfulness_tiers,
)
from polisyos.foundry.methods.base import MethodMetadata
from polisyos.foundry.methods.catalog.ml.protocols import PredictionIntervalResult
from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationDiagnosticsReport,
    CalibrationMetrics,
)


def test_truthfulness_reconcile_downgrades_to_runtime_certificate() -> None:
    effective, status = reconcile_truthfulness_tiers("exact", "approximate_calibrated")

    assert effective == TruthfulnessTier.APPROXIMATE_CALIBRATED
    assert status == "runtime_downgraded"


def test_truthfulness_reconcile_caps_catalog_underclaim() -> None:
    effective, status = reconcile_truthfulness_tiers("asymptotic", "exact")

    assert effective == TruthfulnessTier.ASYMPTOTIC
    assert status == "catalog_underclaims"


def test_method_catalog_entry_maps_legacy_truthfulness_label_to_implementation_depth() -> None:
    entry = MethodCatalogEntry(
        fqn="test.method@1.0.0",
        namespace="test",
        name="method",
        version="1.0.0",
        backend="numpy",
        execution_backend="numpy",
        kind="pure",
        family="test",
        variant="default",
        fidelity_tier="medium",
        truthfulness_tier="production_method",
    )

    assert entry.implementation_depth_tier == "production_method"
    assert entry.truthfulness_tier == "unverified"
    assert entry.truthfulness_status == "missing_both"


def test_prediction_interval_result_returns_truthfulness_receipt() -> None:
    result = PredictionIntervalResult(
        method_name="conformal_prediction",
        predictions=[1.0, 2.0],
        lower=[0.5, 1.5],
        upper=[1.5, 2.5],
        truthfulness_receipt=TruthfulnessReceipt(
            runtime_truthfulness_tier=TruthfulnessTier.EXACT,
            truthfulness_scope=TruthfulnessScope.MARGINAL_COVERAGE,
        ),
    )

    receipt = result.to_truthfulness_receipt()
    assert receipt is not None
    assert receipt.runtime_truthfulness_tier == "exact"
    assert receipt.truthfulness_scope == "marginal_coverage"


def test_method_metadata_normalizes_truthfulness_declarations() -> None:
    metadata = MethodMetadata(
        description="truthfulness-aware",
        declared_truthfulness_tier="EXACT",
        truthfulness_scope="MARGINAL_COVERAGE",
    )

    assert metadata.declared_truthfulness_tier == "exact"
    assert metadata.truthfulness_scope == "marginal_coverage"


def test_calibration_diagnostics_report_returns_conservative_truthfulness_receipt() -> None:
    report = CalibrationDiagnosticsReport(
        task="binary",
        target_type="probability",
        metrics=CalibrationMetrics(n_obs=64, brier=0.08, ece=0.03),
    )

    receipt = report.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier == "approximate_calibrated"
    assert receipt.truthfulness_scope == "predictive_calibration"
