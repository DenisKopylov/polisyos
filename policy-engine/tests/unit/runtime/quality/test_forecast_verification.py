"""Bounded tests for the independent forecast verification boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.ir.analytics.backtest import BacktestReport, BacktestScenario, OutcomeComparison
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastingUncertaintyBundle,
    ForecastIntervalSemantics,
    HorizonInterval,
    HorizonPolicySpec,
)
from polisyos.ir.artifacts import ArtifactID
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity.loaders import load_model_spec, load_policy_spec
from polisyos.runtime.quality.design_axes.forecast_verification import (
    _manifest_input_edges,
    _reconcile_report_observations,
    _validate_model_policy_content,
    _validate_stored_uncertainty_bundle,
    _VerificationRefusalError,
    verify_forecast_calibration,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    CalibrationRuleBinding,
    ForecastOwnerRequest,
    ForecastTemporalRoles,
    TrainHoldoutSplit,
)

METHOD_FQN = "forecasting.univariate.exponential_smoothing@1.0.0"
RULE_ID = "rolling-origin-residual-conformal.v1"


class _MissingCas:
    """CAS that exposes an absent evidence manifest and no other bytes."""

    def get_manifest(self, artifact_id: object) -> object:
        raise FileNotFoundError(str(artifact_id))

    def get_bytes(self, artifact_id: object) -> bytes:
        raise AssertionError("unresolved evidence must refuse before reading source bytes")

    def iter_artifact_ids(self) -> list[str]:
        return []


class _ManifestCas:
    """CAS manifest adapter for narrow manifest-role falsifiers."""

    def __init__(self, inputs: list[dict[str, str]]) -> None:
        self.inputs = inputs

    def get_manifest(self, artifact_id: object) -> object:
        return {"inputs": self.inputs}


def _request() -> ForecastOwnerRequest:
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    rule_ref = ArtifactRefModel(
        artifact_id=ArtifactID("sha256:" + "1" * 64),
        kind="ir.forecast_calibration_rule",
        media_type="application/json",
    )
    return ForecastOwnerRequest(
        observed_source_ref=DataSnapshotRef(
            artifact_id=ArtifactID("sha256:" + "2" * 64),
        ),
        split=TrainHoldoutSplit(
            train_start=0,
            train_end=8,
            holdout_start=8,
            holdout_end=10,
            horizon=2,
        ),
        target_metric="metric",
        method_fqn=METHOD_FQN,
        method_params={"horizon": 2, "alpha": 0.3, "beta": 0.1},
        report_id="forecast-test",
        calibration_rule=CalibrationRuleBinding(rule_id=RULE_ID, artifact_ref=rule_ref),
        temporal_roles=ForecastTemporalRoles(
            data_valid_time=origin,
            calibration_window_start=origin + timedelta(days=1),
            calibration_window_end=origin + timedelta(days=2),
            policy_effective_time=origin + timedelta(days=3),
            prediction_time=origin + timedelta(days=4),
            observation_time=origin + timedelta(days=5),
        ),
    )


def _scenario(*, first_y_true: float = 10.0, reported_hits: int = 2) -> BacktestScenario:
    return BacktestScenario(
        scenario_id="forecast-test:ets",
        scenario_label="ETS",
        outcome_comparisons=[
            OutcomeComparison(
                metric_name="metric",
                y_pred=10.0,
                y_true=first_y_true,
                absolute_error=abs(first_y_true - 10.0),
                within_ci=True,
                ci_lower=9.0,
                ci_upper=11.0,
            ),
            OutcomeComparison(
                metric_name="metric",
                y_pred=20.0,
                y_true=20.0,
                absolute_error=0.0,
                within_ci=True,
                ci_lower=19.0,
                ci_upper=21.0,
            ),
        ],
        coverage_probability=reported_hits / 2,
        requested_count=2,
        compared_count=2,
        missing_count=0,
        invalid_count=0,
        interval_requested_count=2,
        interval_available_count=2,
        interval_evaluated_count=2,
        interval_hit_count=reported_hits,
        interval_availability=1.0,
        interval_hit_rate=reported_hits / 2,
        nominal_confidence_level=0.9,
        metadata={
            "method_ref": "forecasting.univariate.exponential_smoothing",
            "method_version": "1.0.0",
            "rule_version_ref": RULE_ID,
            "estimand": "predictive_interval_coverage",
            "authority_scope": "predictive_only",
            "bridge_status": "bridge_pending",
            "observed_source_ref": _request().observed_source_ref.model_dump(mode="json"),
            "temporal_roles": _request().temporal_roles.model_dump(mode="json"),
        },
    )


def _report(scenario: BacktestScenario) -> BacktestReport:
    return BacktestReport(
        report_id="forecast-test",
        historical_data_ref="sha256:" + "3" * 64,
        scenarios=[scenario],
        overall_coverage_probability=scenario.coverage_probability,
        n_scenarios=1,
        n_metrics_evaluated=2,
    )


def test_missing_evidence_refuses_before_source_resolution_or_ets() -> None:
    evidence_ref = {
        "artifact_id": "sha256:" + "4" * 64,
        "kind": "ir.empirical_calibration_evidence",
        "media_type": "application/json",
    }

    result = verify_forecast_calibration(_MissingCas(), _request(), evidence_ref)  # type: ignore[arg-type]

    assert result.status == "blocked"
    assert result.reason_codes == ("empirical_evidence_unresolved",)
    assert result.numerator is None
    assert result.source_scope_status == "not_established"


def test_malformed_evidence_ref_fails_closed_without_becoming_a_result_ref() -> None:
    malformed_ref = {
        "artifact_id": "sha256:" + "4" * 64,
        "kind": "ir.forecast_owner_result",
        "media_type": "application/json",
    }

    result = verify_forecast_calibration(  # type: ignore[arg-type]
        _MissingCas(),
        _request(),
        malformed_ref,
    )

    assert result.status == "blocked"
    assert result.reason_codes == ("empirical_evidence_ref_invalid",)
    assert result.empirical_evidence_ref is None


def test_report_comparison_rejects_internally_consistent_but_forged_count() -> None:
    request = _request()
    scenario = _scenario(reported_hits=1)

    with pytest.raises(
        _VerificationRefusalError, match="report_calibration_counts_or_rate_mismatch"
    ):
        _reconcile_report_observations(
            _report(scenario),
            scenario,
            request=request,
            point_forecast=(10.0, 20.0),
            intervals=((9.0, 11.0), (19.0, 21.0)),
            holdout=np.asarray([10.0, 20.0]),
            nominal_coverage=0.9,
        )


def test_report_comparison_rejects_heldout_value_not_from_resolved_source() -> None:
    request = _request()
    scenario = _scenario(first_y_true=10.5)

    with pytest.raises(_VerificationRefusalError, match="report_heldout_comparison_mismatch_1"):
        _reconcile_report_observations(
            _report(scenario),
            scenario,
            request=request,
            point_forecast=(10.0, 20.0),
            intervals=((9.0, 11.0), (19.0, 21.0)),
            holdout=np.asarray([10.0, 20.0]),
            nominal_coverage=0.9,
        )


def test_manifest_input_edges_reject_duplicate_role_artifact_binding() -> None:
    artifact_id = "sha256:" + "5" * 64
    ref = ArtifactRefModel(
        artifact_id=ArtifactID("sha256:" + "6" * 64),
        kind="ir.backtest_report",
        media_type="application/json",
    )
    store = _ManifestCas(
        inputs=[
            {"artifact_id": artifact_id, "role": "observed_source"},
            {"artifact_id": artifact_id, "role": "observed_source"},
        ]
    )

    with pytest.raises(_VerificationRefusalError, match="report_manifest_input_edge_not_unique"):
        _manifest_input_edges(store, ref)  # type: ignore[arg-type]


def test_stored_uncertainty_rejects_rerun_sample_count_mismatch() -> None:
    request = _request()
    intervals = tuple(
        HorizonInterval.model_construct(
            horizon=horizon,
            point=point,
            lower=point - 1.0,
            upper=point + 1.0,
            constructor=ForecastCalibrationMethod.CONFORMAL,
            sample_count=4,
        )
        for horizon, point in enumerate((10.0, 20.0), start=1)
    )
    stored = ForecastingUncertaintyBundle(
        method_fqn=METHOD_FQN,
        target_id="metric",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        prediction_interval=intervals,
        fan_chart=FanChartSpec(),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            last_recalibrated_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        horizon_policy=HorizonPolicySpec(default_method=ForecastCalibrationMethod.CONFORMAL),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="bounded test fixture",
    )

    with pytest.raises(
        _VerificationRefusalError,
        match="stored_uncertainty_sample_count_replay_mismatch",
    ):
        _validate_stored_uncertainty_bundle(
            stored,
            request=request,
            point_forecast=(10.0, 20.0),
            intervals=((9.0, 11.0), (19.0, 21.0)),
            sample_counts=(3, 4),
            nominal_coverage=0.9,
        )


def test_supplied_model_policy_pair_resolves_under_canonical_core_loaders(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    model_ref = store.put_json(
        ModelSpec(
            model_id="verifier_model",
            data_snapshot_ref="sha256:" + "7" * 64,
        ).model_dump(mode="json"),
        PutOptions(kind="ir.model_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    policy_ref = store.put_json(
        PolicySpec(policy_id="verifier_policy").model_dump(mode="json"),
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    request = _request().model_copy(
        update={
            "model_spec_ref": model_ref.artifact_id,
            "policy_spec_ref": policy_ref.artifact_id,
        }
    )

    _validate_model_policy_content(store, request)

    assert load_model_spec(store.get_bytes(model_ref.artifact_id)).model_id == "verifier_model"
    assert load_policy_spec(store.get_bytes(policy_ref.artifact_id)).policy_id == "verifier_policy"


def test_model_policy_pair_refuses_content_with_unknown_core_fields(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    model_ref = store.put_json(
        {
            "schema_version": "1.0",
            "model_id": "verifier_model",
            "data_snapshot_ref": "sha256:" + "7" * 64,
            "unexpected_authority": True,
        },
        PutOptions(kind="ir.model_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    policy_ref = store.put_json(
        PolicySpec(policy_id="verifier_policy").model_dump(mode="json"),
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    request = _request().model_copy(
        update={
            "model_spec_ref": model_ref.artifact_id,
            "policy_spec_ref": policy_ref.artifact_id,
        }
    )

    with pytest.raises(_VerificationRefusalError, match="model_spec_content_invalid"):
        _validate_model_policy_content(store, request)


def test_model_policy_pair_refuses_wrong_manifest_kind(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    model_ref = store.put_json(
        ModelSpec(
            model_id="verifier_model",
            data_snapshot_ref="sha256:" + "7" * 64,
        ).model_dump(mode="json"),
        PutOptions(kind="test.forecast.model_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    policy_ref = store.put_json(
        PolicySpec(policy_id="verifier_policy").model_dump(mode="json"),
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    request = _request().model_copy(
        update={
            "model_spec_ref": model_ref.artifact_id,
            "policy_spec_ref": policy_ref.artifact_id,
        }
    )

    with pytest.raises(_VerificationRefusalError, match="model_spec_content_unresolved"):
        _validate_model_policy_content(store, request)


def test_model_policy_pair_refuses_policy_content_with_unknown_core_fields(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    model_ref = store.put_json(
        ModelSpec(
            model_id="verifier_model",
            data_snapshot_ref="sha256:" + "7" * 64,
        ).model_dump(mode="json"),
        PutOptions(kind="ir.model_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    policy_ref = store.put_json(
        {
            "schema_version": "1.0",
            "policy_id": "verifier_policy",
            "unexpected_authority": True,
        },
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    request = _request().model_copy(
        update={
            "model_spec_ref": model_ref.artifact_id,
            "policy_spec_ref": policy_ref.artifact_id,
        }
    )

    with pytest.raises(_VerificationRefusalError, match="policy_spec_content_invalid"):
        _validate_model_policy_content(store, request)


def test_model_policy_pair_refuses_incomplete_pair_before_cas_resolution() -> None:
    request = _request().model_copy(update={"model_spec_ref": ArtifactID("sha256:" + "8" * 64)})

    with pytest.raises(_VerificationRefusalError, match="model_policy_spec_pair_incomplete"):
        _validate_model_policy_content(_MissingCas(), request)  # type: ignore[arg-type]
