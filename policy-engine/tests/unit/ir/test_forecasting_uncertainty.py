from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastingUncertaintyBundle,
    ForecastingUncertaintyBundleV2,
    ForecastIntervalSemantics,
    HorizonDiagnosticState,
    HorizonInterval,
    HorizonPolicyRule,
    HorizonPolicySpec,
    HorizonQuantileSet,
    ReconciliationCertificate,
    ReconciliationMethod,
    ReconciliationStatus,
    load_forecasting_uncertainty_bundle,
    persist_forecasting_uncertainty_bundle,
)
from polisyos.ir.artifacts.io import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.registry.refs import ForecastingUncertaintyBundleRef
from polisyos.ir.schemas import get_ir_type


def _now() -> datetime:
    return datetime.now(UTC)


def _sample_bundle() -> ForecastingUncertaintyBundle:
    generated_at = _now()
    return ForecastingUncertaintyBundle(
        method_fqn="forecasting.univariate.exponential_smoothing@1.0.0",
        target_id="series",
        generated_at=generated_at,
        prediction_interval=(
            HorizonInterval(
                horizon=1,
                point=10.0,
                lower=9.0,
                upper=11.0,
                coverage_target=0.9,
                constructor=ForecastCalibrationMethod.CONFORMAL,
                sample_count=12,
            ),
            HorizonInterval(
                horizon=2,
                point=10.5,
                lower=8.8,
                upper=12.2,
                coverage_target=0.9,
                constructor=ForecastCalibrationMethod.CONFORMAL,
                sample_count=11,
            ),
        ),
        fan_chart=FanChartSpec(
            quantile_levels=(0.05, 0.5, 0.95),
            horizons=(
                HorizonQuantileSet(horizon=1, quantiles={"0.05": 9.0, "0.5": 10.0, "0.95": 11.0}),
                HorizonQuantileSet(horizon=2, quantiles={"0.05": 8.8, "0.5": 10.5, "0.95": 12.2}),
            ),
        ),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            empirical_coverage_by_horizon={1: 0.92, 2: 0.91},
            coverage_gap_by_horizon={1: 0.02, 2: 0.01},
            mean_interval_width_by_horizon={1: 2.0, 2: 3.4},
            conditional_coverage_pvalue_by_horizon={1: 0.31, 2: 0.28},
            independence_pvalue_by_horizon={1: 0.44, 2: 0.41},
            wis_by_horizon={1: 1.3, 2: 1.8},
            sample_count_by_horizon={1: 12, 2: 11},
            calibration_window=24,
            regime_flags=("marginal_coverage_only",),
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.CONFORMAL,
            rules=(
                HorizonPolicyRule(
                    horizon_start=1,
                    horizon_end=1,
                    diagnostic_state=HorizonDiagnosticState.GREEN,
                    allowed_methods=(ForecastCalibrationMethod.CONFORMAL,),
                    gate_eligible=True,
                ),
                HorizonPolicyRule(
                    horizon_start=2,
                    horizon_end=2,
                    diagnostic_state=HorizonDiagnosticState.AMBER,
                    allowed_methods=(ForecastCalibrationMethod.CONFORMAL,),
                    gate_eligible=True,
                    fallback=ForecastCalibrationMethod.BOOTSTRAP,
                ),
            ),
            gate_eligible=True,
            summary="Phase 0 default",
        ),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="rolling-origin residual windows by horizon",
        regime_assumption="marginal coverage only",
    )


def _sample_reconciliation_certificate(
    *,
    status: ReconciliationStatus = ReconciliationStatus.CERTIFIED,
) -> ReconciliationCertificate:
    return ReconciliationCertificate(
        status=status,
        method=ReconciliationMethod.BOTTOM_UP,
        constraints_kind="hierarchical",
        coherent_points=True,
        coherent_paths=False,
        coverage_scope="per_series_marginal"
        if status is ReconciliationStatus.CERTIFIED
        else "uncertified",
        preconditions_passed=status is ReconciliationStatus.CERTIFIED,
        preconditions={
            "rolling_origin_residual_bank": status is ReconciliationStatus.CERTIFIED,
            "minimum_calibration_count": status is ReconciliationStatus.CERTIFIED,
        },
        diagnostics={
            "max_point_aggregation_error_by_horizon": {1: 0.0, 2: 0.0},
            "aggregation_gap_by_horizon": {1: 0.0, 2: 0.0},
            "empirical_coverage_by_horizon": {1: 0.92, 2: 0.91},
            "mean_interval_width_by_horizon": {1: 2.0, 2: 3.4},
            "width_reduction_vs_unreconciled_by_horizon": {},
            "sample_count_by_horizon": {1: 12, 2: 11},
            "diagnostic_state_by_horizon": {1: "green", 2: "amber"},
        },
        fallback_reason=None
        if status is ReconciliationStatus.CERTIFIED
        else "reconciled calibration residual bank is missing",
    )


def test_forecasting_uncertainty_bundle_creation() -> None:
    bundle = _sample_bundle()

    assert bundle.source_method == bundle.method_fqn
    assert bundle.interval_semantics is ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
    assert len(bundle.prediction_interval) == 2
    assert bundle.coverage_diagnostic.empirical_coverage_by_horizon[1] == pytest.approx(0.92)
    assert bundle.horizon_policy.rules[0].diagnostic_state is HorizonDiagnosticState.GREEN
    receipt = bundle.to_truthfulness_receipt()
    assert receipt.truthfulness_scope == "marginal_coverage"
    assert receipt.runtime_truthfulness_tier == "approximate_calibrated"
    assert receipt.diagnostics["source_method"] == bundle.method_fqn


def test_forecasting_uncertainty_bundle_rejects_point_outside_interval() -> None:
    with pytest.raises(ValidationError):
        HorizonInterval(
            horizon=1,
            point=3.0,
            lower=3.1,
            upper=3.2,
            constructor=ForecastCalibrationMethod.CONFORMAL,
        )


def test_forecasting_uncertainty_bundle_cas_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = _sample_bundle()

    ref_1 = persist_forecasting_uncertainty_bundle(_ensure_ir_artifact_store(store), bundle)
    ref_2 = persist_forecasting_uncertainty_bundle(_ensure_ir_artifact_store(store), bundle)
    loaded = load_forecasting_uncertainty_bundle(_ensure_ir_artifact_store(store), ref_1)

    assert ref_1.kind == "ir.forecasting_uncertainty_bundle"
    assert ref_1.manifest_profile_sha256 is None
    assert ref_2.manifest_profile_sha256 is None
    assert ref_1.artifact_id == ref_2.artifact_id
    assert loaded == bundle


def test_forecasting_uncertainty_bundle_returns_selected_write_profile(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _sample_bundle()

    ref = persist_forecasting_uncertainty_bundle(
        _ensure_ir_artifact_store(store), bundle, return_selected_profile=True
    )

    assert ref.manifest_profile_sha256 is not None
    manifest = store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)
    assert str(manifest.artifact_id) == str(ref.artifact_id)
    assert artifact_manifest_profile_sha256(manifest) == ref.manifest_profile_sha256
    assert manifest.kind == ref.kind == "ir.forecasting_uncertainty_bundle"
    assert manifest.media_type == "application/json"
    assert load_forecasting_uncertainty_bundle(_ensure_ir_artifact_store(store), ref) == bundle


def test_forecasting_uncertainty_bundle_v1_rejects_reconciliation_certificate() -> None:
    payload = _sample_bundle().model_dump(mode="python", round_trip=True)
    payload["reconciliation_certificate"] = _sample_reconciliation_certificate().model_dump(
        mode="python"
    )

    with pytest.raises(ValidationError):
        ForecastingUncertaintyBundle.model_validate(payload)


def test_forecasting_uncertainty_bundle_v2_receipt_uses_reconciliation_certificate() -> None:
    payload = _sample_bundle().model_dump(mode="python", round_trip=True)
    payload["schema_version"] = "2.0"
    payload["calibration_method"] = ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
    payload["horizon_policy"]["default_method"] = (
        ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
    )
    for interval in payload["prediction_interval"]:
        interval["constructor"] = ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
    for rule in payload["horizon_policy"]["rules"]:
        rule["allowed_methods"] = (ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION,)
    payload["reconciliation_certificate"] = _sample_reconciliation_certificate().model_dump(
        mode="python"
    )

    bundle = ForecastingUncertaintyBundleV2.model_validate(payload)

    assert bundle.contract_id == "ir.forecasting_uncertainty_bundle.v2"
    assert bundle.reconciliation_certificate is not None
    assert bundle.reconciliation_certificate.status is ReconciliationStatus.CERTIFIED
    receipt = bundle.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier.value == "approximate_calibrated"
    assert receipt.truthfulness_scope.value == "marginal_coverage"
    assert "reconciliation_certificate" in receipt.diagnostics


def test_forecasting_uncertainty_bundle_v2_preserves_base_ordering_validation() -> None:
    payload = _sample_bundle().model_dump(mode="python", round_trip=True)
    payload["schema_version"] = "2.0"
    payload["prediction_interval"] = tuple(reversed(payload["prediction_interval"]))

    with pytest.raises(ValidationError, match="prediction intervals must be sorted by horizon"):
        ForecastingUncertaintyBundleV2.model_validate(payload)


def test_forecasting_uncertainty_bundle_v2_cas_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = _sample_bundle_v2()

    ref = persist_forecasting_uncertainty_bundle(_ensure_ir_artifact_store(store), bundle)
    loaded = load_forecasting_uncertainty_bundle(_ensure_ir_artifact_store(store), ref)

    assert ref.kind == "ir.forecasting_uncertainty_bundle"
    assert isinstance(loaded, ForecastingUncertaintyBundleV2)
    assert loaded.schema_version == "2.0"
    assert loaded.reconciliation_certificate is not None


def test_forecasting_uncertainty_bundle_registered_in_abi_catalog() -> None:
    entry = get_ir_type("ForecastingUncertaintyBundle")

    assert entry.abi_key == "forecasting_uncertainty_bundle"
    assert entry.abi_schema_file == "forecasting_uncertainty_bundle.schema.json"
    assert entry.abi_priority == "p1"


def test_forecasting_uncertainty_bundle_emits_truthfulness_receipt() -> None:
    bundle = _sample_bundle()
    receipt = bundle.to_truthfulness_receipt()

    assert receipt.runtime_truthfulness_tier.value == "approximate_calibrated"
    assert receipt.truthfulness_scope.value == "marginal_coverage"
    assert receipt.diagnostics["mean_interval_width_by_horizon"][1] == pytest.approx(2.0)


class _CountingPayloadReader:
    def __init__(self, store) -> None:
        self.store = store
        self.payload_reads = 0

    def __getattr__(self, name: str):
        return getattr(self.store, name)

    def get_bytes(self, selector) -> bytes:
        self.payload_reads += 1
        return self.store.get_bytes(selector)


def test_forecasting_wrong_profile_refuses_before_v1_to_v2_fallback(tmp_path) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    bundle = _sample_bundle()
    raw_ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json", round_trip=True),
        kind="ir.forecasting_uncertainty_bundle",
        schema_name="ir.forecasting_uncertainty_bundle",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False, sort_keys=False),
    )
    reader = _CountingPayloadReader(store)
    ref = ForecastingUncertaintyBundleRef.model_validate(raw_ref)

    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        load_forecasting_uncertainty_bundle(reader, ref)

    assert reader.payload_reads == 0


def test_forecasting_payload_version_mismatch_does_not_fall_back_to_v2(
    tmp_path,
) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    payload = _sample_bundle().model_dump(mode="json", round_trip=True)
    payload["schema_version"] = "2.0"
    raw_ref = put_json_artifact(
        store,
        payload,
        kind="ir.forecasting_uncertainty_bundle",
        schema_name="ir.forecasting_uncertainty_bundle",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    reader = _CountingPayloadReader(store)
    ref = ForecastingUncertaintyBundleRef.model_validate(raw_ref)

    with pytest.raises(CanonViolation, match="ir_owned_artifact_representation_unreadable"):
        load_forecasting_uncertainty_bundle(reader, ref)

    assert reader.payload_reads == 1


class _CountingWriteStore:
    def __init__(self, store) -> None:
        self.store = store
        self.put_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.store, name)

    def put_json(self, *args, **kwargs):
        self.put_calls += 1
        return self.store.put_json(*args, **kwargs)


def _sample_bundle_v2() -> ForecastingUncertaintyBundleV2:
    payload = _sample_bundle().model_dump(mode="python", round_trip=True)
    payload["schema_version"] = "2.0"
    payload["calibration_method"] = ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
    payload["horizon_policy"]["default_method"] = (
        ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
    )
    for interval in payload["prediction_interval"]:
        interval["constructor"] = ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
    for rule in payload["horizon_policy"]["rules"]:
        rule["allowed_methods"] = (ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION,)
    payload["reconciliation_certificate"] = _sample_reconciliation_certificate().model_dump(
        mode="python"
    )
    return ForecastingUncertaintyBundleV2.model_validate(payload)


@pytest.mark.parametrize("invalid_flag", [None, 0, 1, "true"])
def test_forecast_writer_rejects_nonbool_selected_profile_before_cas(
    tmp_path,
    invalid_flag: object,
) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    probe = _CountingWriteStore(store)

    with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
        persist_forecasting_uncertainty_bundle(
            probe,
            _sample_bundle(),
            return_selected_profile=invalid_flag,
        )

    assert probe.put_calls == 0


def test_v2_explicit_legacy_schema_selection_refuses_before_cas(tmp_path) -> None:
    default_schema_version = persist_forecasting_uncertainty_bundle.__kwdefaults__["schema_version"]
    assert isinstance(default_schema_version, str)
    assert default_schema_version == "1.0"

    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    probe = _CountingWriteStore(store)
    bundle = _sample_bundle_v2()

    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_write_override_unregistered",
    ):
        persist_forecasting_uncertainty_bundle(
            probe,
            bundle,
            schema_version="1.0",
        )

    assert probe.put_calls == 0
