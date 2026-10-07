"""Bounded FRC-01 S10 consumer witnesses.

These tests keep estimator-shape output separate from observed interval
evidence. The persisted bridge fixture exercises the old typed DTO path only;
it is not a production run or a C-admitted source series, and its bounded
result does not establish the configured production S10 route.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _generation_cycle(name: str) -> Any:
    import polisyos.runtime.quality.generation_cycle as module

    return getattr(module, name)


def _finite_estimator_report(
    *, confidence_level: float = 0.95, diagnostics: tuple[Any, ...] = ()
) -> Any:
    """Return estimator-shaped output with no observation-side calibration data."""

    return SimpleNamespace(
        point_estimate=1.5,
        confidence_interval=(1.0, 2.0),
        standard_error=0.2,
        confidence_level=confidence_level,
        diagnostics=diagnostics,
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=4,
        post_periods=4,
    )


def _persisted_bridge_fixture(
    tmp_path: Path,
    *,
    observations: tuple[bool | None, ...] = (True, False),
) -> tuple[Any, Any, Any]:
    """Build persisted typed bridge evidence for a focused S10 consumer test.

    This is a synthetic old-contract forecast-bridge fixture. It exercises CAS
    persistence, the strict E DTO/loader, and A's independent resolver path; it
    does not represent a production run or a C-admitted source series.
    """

    import importlib

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.ir.analytics.backtest import (
        BacktestReport,
        BacktestScenario,
        OutcomeComparison,
        load_backtest_report,
        persist_backtest_report,
    )
    from polisyos.ir.artifacts import InputRef, put_json_artifact

    bridge = importlib.import_module("polisyos.calibration.forecast_bridge")
    store = FileSystemCAS(tmp_path / "frc01-typed-evidence-cas")
    # A neutral identity reaches the E mechanism; this remains the synthetic
    # control described above, with no admitted source/history or authority.
    report_id = "frc01-s10-interval-control"
    model_ref = "model://frc01/ets/v1"
    policy_ref = "policy://frc01/ets/v1"
    estimand = "predictive_interval_coverage"
    method_ref = "forecasting.univariate.exponential_smoothing"
    method_version = "1.0.0"
    rule_ref = "rolling-origin-residual-conformal.v1"
    threshold = 1.0
    profiles = {
        "scope_binding": (
            "ir.calibration.scope_binding",
            "polisyos.calibration.scope_binding",
        ),
        "calibration_threshold": (
            "ir.calibration.threshold",
            "polisyos.calibration.threshold",
        ),
        "observed_outcome": (
            "ir.calibration.observed_outcome",
            "polisyos.calibration.observed_outcome",
        ),
        "prediction": ("ir.calibration.prediction", "polisyos.calibration.prediction"),
        "evaluation_design": (
            "ir.calibration.evaluation_design",
            "polisyos.calibration.evaluation_design",
        ),
        "credible_evaluation": (
            "ir.calibration.credible_evaluation",
            "polisyos.calibration.credible_evaluation",
        ),
        "source_lineage": (
            "ir.calibration.source_lineage",
            "polisyos.calibration.source_lineage",
        ),
        "method_lineage": (
            "ir.calibration.method_lineage",
            "polisyos.calibration.method_lineage",
        ),
    }
    scope_binding = {
        "report_id": report_id,
        "model_spec_ref": model_ref,
        "policy_spec_ref": policy_ref,
        "estimand": estimand,
        "method_ref": method_ref,
        "method_version": method_version,
        "rule_version_ref": rule_ref,
        "calibration_threshold": f"{threshold:.2f}",
    }
    specs = (
        ("scope_binding", report_id, "report_id", scope_binding),
        (
            "calibration_threshold",
            "threshold://frc01/1.00",
            "identity",
            {"threshold": Decimal(f"{threshold:.2f}")},
        ),
        ("observed_outcome", "observation://frc01/held-out/v1", "identity", {}),
        ("prediction", "prediction://frc01/held-out/v1", "identity", {}),
        ("evaluation_design", "evaluation://frc01/rolling-origin/v1", "identity", {}),
        ("credible_evaluation", "evaluation-evidence://frc01/v1", "identity", {}),
        ("source_lineage", "source://frc01/panel/v1", "identity", {}),
        ("method_lineage", "method-lineage://frc01/ets/v1", "identity", {}),
    )
    refs: dict[str, dict[str, str]] = {}
    for role, identity, identity_path, fields in specs:
        kind, schema_name = profiles[role]
        payload: dict[str, object] = {
            "role": role,
            "report_id": report_id,
            "identity": identity,
        }
        if identity_path == "report_id":
            payload["report_id"] = identity
        if role == "scope_binding":
            payload["binding"] = dict(fields)
        else:
            payload.update(fields)
        ref = put_json_artifact(
            store,
            payload,
            kind=kind,
            schema_name=schema_name,
            schema_version="1.0",
        )
        ref.update(
            {
                "role": role,
                "schema_name": schema_name,
                "schema_version": "1.0",
                "identity_path": identity_path,
                "identity_value": identity,
            }
        )
        refs[role] = ref

    comparisons = []
    for index, within_ci in enumerate(observations, start=1):
        observed = within_ci is not None
        comparisons.append(
            OutcomeComparison(
                metric_name=f"frc01-metric-{index}",
                y_pred=float(index),
                y_true=float(index) if within_ci is not False else float(index) + 5.0,
                absolute_error=5.0 if within_ci is False else 0.0,
                within_ci=within_ci,
                ci_lower=float(index) - 0.5 if observed else None,
                ci_upper=float(index) + 0.5 if observed else None,
            )
        )
    denominator = sum(value is not None for value in observations)
    numerator = sum(value is True for value in observations)
    pass_rate = numerator / denominator if denominator else None
    report = BacktestReport(
        schema_version="1.0",
        report_id=report_id,
        model_spec_ref=model_ref,
        policy_spec_ref=policy_ref,
        scenarios=[
            BacktestScenario(
                scenario_id="frc01-s10-scenario",
                scenario_label="persisted FRC-01 synthetic interval comparisons",
                data_source="held-out-observations",
                outcome_comparisons=comparisons,
                requested_count=len(observations),
                compared_count=len(observations),
                interval_requested_count=len(observations),
                interval_available_count=denominator,
                interval_evaluated_count=denominator,
                interval_hit_count=numerator,
                interval_availability=(
                    denominator / len(observations) if observations else 0.0
                ),
                interval_hit_rate=pass_rate,
                nominal_confidence_level=0.95,
                interval_type="prediction",
            )
        ],
        overall_coverage_probability=pass_rate,
        n_scenarios=1,
        n_metrics_evaluated=len(observations),
        metadata={
            "model_spec_ref": model_ref,
            "policy_spec_ref": policy_ref,
            "method_ref": method_ref,
            "method_version": method_version,
            "rule_version_ref": rule_ref,
            "estimand": estimand,
            "authority_scope": "predictive_only",
            "calibration_numerator": numerator,
            "calibration_denominator": denominator,
            "interval_hit_count": numerator,
            "interval_evaluated_count": denominator,
        },
    )
    report_ref = persist_backtest_report(
        store,
        report,
        inputs=[InputRef(artifact_id=ref["artifact_id"], role=role) for role, ref in refs.items()],
    )
    load_backtest_report(store, report_ref)

    typed_refs = {
        role: bridge.EvidenceArtifactRef.model_validate(ref) for role, ref in refs.items()
    }
    start = datetime(2026, 1, 1, tzinfo=UTC)
    context = bridge.EmpiricalCalibrationContext.model_validate(
        {
            "model_spec_ref": model_ref,
            "policy_spec_ref": policy_ref,
            "estimand": estimand,
            "method_ref": method_ref,
            "method_version": method_version,
            "rule_version_ref": rule_ref,
            "calibration_threshold": threshold,
            "scope_binding_ref": typed_refs["scope_binding"],
            "calibration_threshold_ref": typed_refs["calibration_threshold"],
            "observed_outcome_ref": typed_refs["observed_outcome"],
            "prediction_ref": typed_refs["prediction"],
            "evaluation_design_ref": typed_refs["evaluation_design"],
            "credible_evaluation_evidence_ref": typed_refs["credible_evaluation"],
            "source_lineage_refs": (typed_refs["source_lineage"],),
            "method_lineage_refs": (typed_refs["method_lineage"],),
            "data_valid_time": start,
            "calibration_window_start": start + timedelta(days=1),
            "calibration_window_end": start + timedelta(days=2),
            "policy_effective_time": start + timedelta(days=3),
            "prediction_time": start + timedelta(days=4),
            "observation_time": start + timedelta(days=5),
            "evidence_origin": "persisted_backtest",
        }
    )
    evidence = bridge.produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=context,
    )
    evidence_ref = bridge.persist_empirical_calibration_evidence(store, evidence)
    loaded = bridge.load_empirical_calibration_evidence(store, evidence_ref)
    assert loaded == evidence
    return store, evidence_ref, loaded


class _PersistedForecastEvidenceResolver:
    """Resolve the typed synthetic bridge fixture through the production loader."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.resolved_refs: list[object] = []

    def __call__(self, evidence_ref: object) -> object:
        import importlib

        self.resolved_refs.append(evidence_ref)
        bridge = importlib.import_module("polisyos.calibration.forecast_bridge")
        return bridge.load_empirical_calibration_evidence(self.store, evidence_ref)


def _frc01_subjects() -> tuple[Any, Any, Any]:
    world_record = SimpleNamespace(
        world_model_record_id="world_model_record_frc01",
        content_hash="sha256:" + "a" * 64,
        valid_time_scope="2025-Q2",
        region_or_jurisdiction="UA",
    )
    problem = SimpleNamespace(
        design_problem_id="frc01-problem",
        outcome_of_interest=SimpleNamespace(target_variable="firm_survival"),
    )
    candidate = SimpleNamespace(candidate_id="frc01-candidate")
    return candidate, problem, world_record


def _gateway_inputs_for_bridge_evidence(
    store: Any,
    evidence_ref: Any,
    evidence: Any,
) -> tuple[Mapping[str, Any], _PersistedForecastEvidenceResolver]:
    """Run the production-named gateway over canonical CAS evidence."""

    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

    candidate, problem, world_record = _frc01_subjects()
    resolver = _PersistedForecastEvidenceResolver(store)
    method_result = SimpleNamespace(
        output={
            "report": _finite_estimator_report(),
            "empirical_calibration_evidence_ref": evidence_ref,
            "expected_rule_version_ref": "rolling-origin-residual-conformal.v1",
        },
        temporal_roles=SimpleNamespace(
            prediction_time=evidence.prediction_time,
            observation_time=evidence.observation_time,
            policy_effective_time=evidence.policy_effective_time,
            data_valid_time=evidence.data_valid_time,
            calibration_window_start=evidence.calibration_window_start,
            calibration_window_end=evidence.calibration_window_end,
        ),
    )
    inputs = RealValueOwnerGateway(
        repo_root=store.root,
        empirical_evidence_resolver=resolver,
    ).produce_forecast_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn="forecasting.univariate.exponential_smoothing@1.0.0",
    )
    return inputs, resolver


@pytest.mark.parametrize(
    ("observations", "expected_numerator", "expected_denominator", "expected_rate"),
    [
        pytest.param((None,), 0, 0, None, id="unavailable-observation"),
        pytest.param((False,), 0, 1, 0.0, id="observed-zero-rate"),
    ],
)
def test_gateway_preserves_missing_calibration_metric_as_distinct_from_observed_zero(
    tmp_path: Path,
    observations: tuple[bool | None, ...],
    expected_numerator: int,
    expected_denominator: int,
    expected_rate: float | None,
) -> None:
    """Canonical E readback keeps absence distinct from a measured zero."""

    store, evidence_ref, evidence = _persisted_bridge_fixture(
        tmp_path,
        observations=observations,
    )
    assert evidence.recomputed_numerator == expected_numerator
    assert evidence.recomputed_denominator == expected_denominator
    assert evidence.recomputed_pass_rate == expected_rate

    projection, projection_error = _generation_cycle("_s10_empirical_projection")(
        evidence_ref=evidence_ref,
        evidence=evidence,
    )
    assert projection_error is None
    assert projection is not None
    assert projection["numerator"] == expected_numerator
    assert projection["denominator"] == expected_denominator
    assert projection["pass_rate"] == expected_rate

    inputs, resolver = _gateway_inputs_for_bridge_evidence(
        store,
        evidence_ref,
        evidence,
    )
    support = inputs["forecast_support"]
    record = inputs["forecast_calibration_record"]

    assert resolver.resolved_refs == [evidence_ref]
    assert support.forecast_tier == "blocked"
    if expected_denominator == 0:
        assert evidence.evidence_kind == "unavailable"
        assert evidence.usable_for_calibration is False
        assert evidence.floor_passed is False
        assert "zero_observation_denominator" in evidence.failure_codes
        assert record is None
        assert support.calibration_record_ref is None
        assert "zero_observation_denominator" in (
            support.forecast_authority_disposition_reason
        )
        assert support.s6_limitation_refs
    else:
        assert evidence.evidence_kind == "observed_interval_comparisons"
        assert evidence.usable_for_calibration is False
        assert record is not None
        assert record.denominator == 1
        assert record.numerator == 0
        assert record.pass_rate == 0.0
        assert record.calibration_status == "limit"
        assert support.calibration_record_ref == record.calibration_ref


@pytest.mark.parametrize(
    ("observations", "field", "value"),
    [
        pytest.param((True,), "recomputed_pass_rate", True, id="boolean-rate"),
        pytest.param((False,), "recomputed_pass_rate", False, id="boolean-zero-rate"),
        pytest.param((True,), "recomputed_pass_rate", "1.0", id="string-rate"),
        pytest.param((True,), "recomputed_pass_rate", float("nan"), id="nan-rate"),
        pytest.param((True,), "recomputed_pass_rate", float("inf"), id="infinite-rate"),
        pytest.param((False,), "recomputed_pass_rate", None, id="missing-rate-with-data"),
        pytest.param((None,), "recomputed_pass_rate", 0.0, id="rate-without-data"),
        pytest.param((True,), "recomputed_numerator", True, id="boolean-numerator"),
        pytest.param((True,), "recomputed_numerator", "1", id="string-numerator"),
        pytest.param((True,), "recomputed_numerator", 1.0, id="float-numerator"),
        pytest.param((True,), "recomputed_denominator", True, id="boolean-denominator"),
        pytest.param((True,), "recomputed_denominator", "1", id="string-denominator"),
        pytest.param((True,), "recomputed_denominator", 1.0, id="float-denominator"),
    ],
)
def test_empirical_projection_rejects_malformed_optional_rate_and_counters(
    tmp_path: Path,
    observations: tuple[bool | None, ...],
    field: str,
    value: object,
) -> None:
    """A projection cannot coerce malformed metrics into plausible numbers."""

    _store, evidence_ref, evidence = _persisted_bridge_fixture(
        tmp_path,
        observations=observations,
    )
    # This in-memory variant attacks the projection boundary; only the two
    # gateway cases above claim canonical persisted E readback.
    malformed = evidence.model_copy(update={field: value})

    projection, error = _generation_cycle("_s10_empirical_projection")(
        evidence_ref=evidence_ref,
        evidence=malformed,
    )

    assert projection is None
    assert error == "empirical_evidence_metrics_mismatch"


def test_finite_estimator_report_without_observations_cannot_pass_calibration() -> None:
    """Finite point/CI diagnostics are not an observed calibration corpus."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report()
    )

    assert evidence["calibration_status"] in {"limit", "insufficient_history", "blocked"}
    assert evidence["denominator"] == 0
    assert evidence["numerator"] == 0
    assert evidence["pass_rate"] is None
    assert evidence["floor_passed"] is False
    assert evidence["counterfactual_credibility"] != "credible"


def test_nominal_confidence_is_not_empirical_coverage_without_observations() -> None:
    """Changing only the declared CI level must not change measured coverage."""

    evidence_80 = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report(confidence_level=0.80)
    )
    evidence_95 = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report(confidence_level=0.95)
    )

    assert evidence_80["calibration_status"] != "pass"
    assert evidence_95["calibration_status"] != "pass"
    assert evidence_80["interval_coverage_metric"] is None
    assert evidence_95["interval_coverage_metric"] is None
    assert evidence_80["calibration_error_metric"] is None
    assert evidence_95["calibration_error_metric"] is None


def test_missing_report_remains_blocked_and_records_false_clear() -> None:
    """A missing estimator report remains an explicit fail-closed boundary."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(None)

    assert evidence["calibration_status"] == "blocked"
    assert evidence["floor_passed"] is False
    assert evidence["pass_rate"] is None
    assert evidence["counterfactual_credibility"] != "credible"
    assert (
        evidence["false_clear_counts"]["uncalibrated_observable_promotion_false_clear_count"] >= 1
    )


def test_failed_estimator_diagnostic_remains_limited() -> None:
    """Estimator diagnostics still surface a bounded non-pass outcome."""

    evidence = _generation_cycle("_s10_calibration_evidence_from_report")(
        _finite_estimator_report(diagnostics=(SimpleNamespace(passed=False),))
    )

    assert evidence["calibration_status"] != "pass"
    assert evidence["floor_passed"] is False
    assert evidence["numerator"] == 0
    assert evidence["pass_rate"] is None


def test_calibration_time_roles_are_preserved_from_bound_evidence(
    tmp_path: Path,
) -> None:
    """A loaded limited DTO preserves its six roles without passing calibration."""

    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

    store, evidence_ref, evidence = _persisted_bridge_fixture(tmp_path)
    resolver = _PersistedForecastEvidenceResolver(store)
    candidate, problem, world_record = _frc01_subjects()
    method_result = SimpleNamespace(
        output={
            "report": _finite_estimator_report(),
            "empirical_calibration_evidence_ref": evidence_ref,
            "expected_rule_version_ref": "rolling-origin-residual-conformal.v1",
        },
        temporal_roles=SimpleNamespace(
            prediction_time=evidence.prediction_time,
            observation_time=evidence.observation_time,
            policy_effective_time=evidence.policy_effective_time,
            data_valid_time=evidence.data_valid_time,
            calibration_window_start=evidence.calibration_window_start,
            calibration_window_end=evidence.calibration_window_end,
        ),
    )
    inputs = RealValueOwnerGateway(
        repo_root=store.root,
        empirical_evidence_resolver=resolver,
    ).produce_forecast_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn=("forecasting.univariate.exponential_smoothing@1.0.0"),
    )
    record = inputs["forecast_calibration_record"]

    assert record is not None
    assert resolver.resolved_refs == [evidence_ref]
    assert inputs["forecast_support"].forecast_tier == "blocked"
    assert record.calibration_status == "limit"
    assert record.empirical_evidence_ref is not None
    assert record.empirical_evidence_ref.artifact_id == evidence_ref.artifact_id
    assert record.prediction_time == evidence.prediction_time
    assert record.observation_time == evidence.observation_time
    assert record.policy_effective_time == evidence.policy_effective_time
    assert record.data_valid_time == evidence.data_valid_time
    assert record.calibration_window_start == evidence.calibration_window_start
    assert record.calibration_window_end == evidence.calibration_window_end
    assert record.observed_outcome_ref == str(evidence.observed_outcome_ref.artifact_id)
    assert record.prediction_ref == str(evidence.prediction_ref.artifact_id)
    assert record.calibration_threshold_ref == str(evidence.calibration_threshold_ref.artifact_id)
    assert record.historical_implementation_ref == str(evidence.report_ref.artifact_id)
    assert record.evaluation_design_ref == str(evidence.evaluation_design_ref.artifact_id)
    assert record.credible_evaluation_evidence_ref == str(
        evidence.credible_evaluation_evidence_ref.artifact_id
    )
    assert record.source_lineage_refs == [
        str(ref.artifact_id) for ref in evidence.source_lineage_refs
    ]
    assert record.method_lineage_refs == [
        str(ref.artifact_id) for ref in evidence.method_lineage_refs
    ]
    assert (
        len(
            {
                record.prediction_time,
                record.observation_time,
                record.policy_effective_time,
                record.data_valid_time,
                record.calibration_window_start,
                record.calibration_window_end,
            }
        )
        == 6
    )


@pytest.mark.parametrize(
    (
        "projection_status",
        "caller_calibration_status",
        "floor_passed",
        "requested_tier",
    ),
    [
        ("limit", "limit", False, "blocked"),
        ("pass", "pass", True, "observable_calibrated"),
        ("pass", None, True, "observable_calibrated"),
    ],
    ids=("owner-limited", "caller-forged-pass", "omitted-status-forged-pass"),
)
def test_content_complete_projection_without_resolved_evidence_stays_blocked(
    tmp_path: Path,
    projection_status: str,
    caller_calibration_status: str | None,
    floor_passed: bool,
    requested_tier: str,
) -> None:
    """Unresolved projections stay blocked even when caller fields claim pass."""

    _store, evidence_ref, evidence = _persisted_bridge_fixture(tmp_path)
    owner_projection, error = _generation_cycle("_s10_empirical_projection")(
        evidence_ref=evidence_ref,
        evidence=evidence,
    )
    assert error is None
    assert owner_projection is not None
    assert owner_projection["calibration_status"] == "limit"
    assert evidence.usable_for_calibration is False
    assert evidence.floor_passed is False
    projection = dict(owner_projection)
    # These caller-authored status fields are not recomputed evidence. In the
    # forged-pass case, preserve every CAS reference and measurement from the
    # limited loaded DTO while changing only the projection claim.
    projection["calibration_status"] = projection_status
    projection["floor_passed"] = floor_passed
    projection["forecast_tier"] = requested_tier
    assert projection["empirical_evidence_ref"].artifact_id == evidence_ref.artifact_id
    status_fields = {"calibration_status", "floor_passed", "forecast_tier"}
    assert {key: value for key, value in projection.items() if key not in status_fields} == {
        key: value for key, value in owner_projection.items() if key not in status_fields
    }
    candidate, problem, world_record = _frc01_subjects()
    inputs = _generation_cycle("_build_s10_forecast_inputs")(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=SimpleNamespace(output={"report": _finite_estimator_report()}),
        selected_method_fqn="forecasting.univariate.exponential_smoothing@1.0.0",
        forecast_tier=requested_tier,
        calibration_status=caller_calibration_status,
        policy_context_ref="policy-context://world_model_record_frc01",
        expected_policy_context_ref="policy-context://world_model_record_frc01",
        false_clear_counts={},
        calibration_evidence=projection,
    )

    support = inputs["forecast_support"]
    assert inputs["forecast_calibration_record"] is None
    assert support.forecast_tier == "blocked"
    assert support.calibration_record_ref is None
    assert "s10://calibration/fail-closed/insufficient-history" in (support.s6_limitation_refs)


def test_gateway_rejects_temporal_roles_that_disagree_with_loaded_evidence(
    tmp_path: Path,
) -> None:
    """A valid CAS body cannot repair caller roles that disagree with its bytes."""

    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

    store, evidence_ref, evidence = _persisted_bridge_fixture(tmp_path)
    resolver = _PersistedForecastEvidenceResolver(store)
    candidate, problem, world_record = _frc01_subjects()
    method_result = SimpleNamespace(
        output={
            "report": _finite_estimator_report(),
            "empirical_calibration_evidence_ref": evidence_ref,
            "expected_rule_version_ref": "rolling-origin-residual-conformal.v1",
        },
        temporal_roles=SimpleNamespace(
            prediction_time=evidence.prediction_time + timedelta(hours=1),
            observation_time=evidence.observation_time,
            policy_effective_time=evidence.policy_effective_time,
            data_valid_time=evidence.data_valid_time,
            calibration_window_start=evidence.calibration_window_start,
            calibration_window_end=evidence.calibration_window_end,
        ),
    )
    inputs = RealValueOwnerGateway(
        repo_root=store.root,
        empirical_evidence_resolver=resolver,
    ).produce_forecast_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn=("forecasting.univariate.exponential_smoothing@1.0.0"),
    )

    assert resolver.resolved_refs == [evidence_ref]
    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"
    assert any(
        "empirical_evidence_time_mismatch" in reason
        for reason in inputs["forecast_support"].s6_limitation_refs
    )


def test_missing_calibration_evidence_refs_stays_typed_blocked() -> None:
    """Temporal dates alone cannot mint a calibration record or pass-through tier."""

    build_inputs = _generation_cycle("_build_s10_forecast_inputs")
    timestamp = datetime(2025, 1, 15, 8, 30, tzinfo=UTC).isoformat()
    world_record = SimpleNamespace(
        world_model_record_id="world_model_record_frc01",
        content_hash="sha256:" + "a" * 64,
        valid_time_scope="2025-Q2",
        region_or_jurisdiction="UA",
    )
    problem = SimpleNamespace(
        design_problem_id="frc01-problem",
        outcome_of_interest=SimpleNamespace(target_variable="firm_survival"),
    )
    candidate = SimpleNamespace(candidate_id="frc01-candidate")
    method_result = SimpleNamespace(output={"report": _finite_estimator_report()})

    evidence_without_status = {
        "counterfactual_credibility": "insufficient_history",
        "prediction_time": timestamp,
        "observation_time": timestamp,
        "policy_effective_time": timestamp,
        "data_valid_time": timestamp,
        "calibration_window_start": timestamp,
        "calibration_window_end": timestamp,
    }
    assert "calibration_status" not in evidence_without_status
    inputs = build_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn="foundry.methods.example",
        forecast_tier="observable_calibrated",
        calibration_status="limit",
        policy_context_ref="policy-context://world_model_record_frc01",
        expected_policy_context_ref="policy-context://world_model_record_frc01",
        false_clear_counts={},
        calibration_evidence=evidence_without_status,
    )

    support = inputs["forecast_support"]
    assert inputs["forecast_calibration_record"] is None
    assert support.forecast_tier == "blocked"
    assert support.calibration_record_ref is None
    assert "s10://calibration/fail-closed/insufficient-history" in support.s6_limitation_refs


def test_unbound_forecast_without_calibration_status_has_no_history_claim() -> None:
    """Missing status stays unknown instead of becoming a fabricated history limit."""

    candidate, problem, world_record = _frc01_subjects()
    inputs = _generation_cycle("_build_s10_forecast_inputs")(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=SimpleNamespace(output={"report": _finite_estimator_report()}),
        selected_method_fqn="forecasting.univariate.exponential_smoothing@1.0.0",
        forecast_tier="blocked",
        calibration_status=None,
        policy_context_ref="policy-context://world_model_record_frc01",
        expected_policy_context_ref="policy-context://world_model_record_frc01",
        false_clear_counts={},
        calibration_evidence={},
    )

    assert inputs["forecast_calibration_record"] is None
    assert inputs["forecast_support"].forecast_tier == "blocked"
    assert not any(
        ref.endswith("insufficient-history")
        for ref in inputs["forecast_support"].s6_limitation_refs
    )


def test_s10_authority_boundary_keeps_purpose_denials() -> None:
    """Bounded FRC-01 evidence cannot become recommendation or S11 authority."""

    boundary = _generation_cycle("_s10_value_authority_boundary")()

    assert boundary["posture"] == "shadow"
    assert {
        "production_recommendation",
        "production_claim_authority",
        "claim_authority",
        "closeout_authority",
        "s11_calibration",
    } <= set(boundary["may_not_use_for"])
