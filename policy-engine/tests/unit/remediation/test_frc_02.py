"""Test-first witness for FRC-02 backtest evidence production.

The plan already owns model and policy specification references.  This slice
proves that the existing orchestrator and matrix persistence paths retain
those references and that a persisted ``BacktestReport`` can produce neutral,
reconciled empirical evidence without changing its public DTO.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from polisyos.calibration.forecast_bridge import (
    EmpiricalCalibrationContext,
    produce_empirical_calibration_evidence,
)
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    OutcomeComparison,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource


def _persist_spec_ref(store: FileSystemCAS, *, spec_kind: str) -> str:
    ref = store.put_json(
        {"spec_id": f"frc-02-{spec_kind}", "source": "test_frc_02"},
        PutOptions(
            kind=f"test.frc02.{spec_kind}_spec",
            media_type="application/json",
        ),
    )
    return str(ref.artifact_id)


def _plan(
    tmp_path: Path,
    *,
    model_spec_ref: str | None,
    policy_spec_ref: str | None,
    exact_predictions: bool = False,
) -> HistoricalValidationPlan:
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps({"metric": [1.0, 1.05, 1.1, 1.15]}),
        encoding="utf-8",
    )
    return HistoricalValidationPlan(
        plan_id="frc-02-ref-transport",
        plan_label="FRC-02 reference transport",
        historical_data_path=str(history_path),
        intervention_step=2,
        ground_truth_outcomes={"metric": [1.1, 1.15]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={
            "metric": [1.1, 1.15] if exact_predictions else [1.08, 1.13]
        },
        model_spec_ref=model_spec_ref,
        policy_spec_ref=policy_spec_ref,
    )


def _persisted_report(
    tmp_path: Path,
    *,
    runner_name: str,
    include_model_ref: bool,
    include_policy_ref: bool,
) -> tuple[BacktestReport, str | None, str | None]:
    store = FileSystemCAS(tmp_path / f"{runner_name}-cas")
    model_spec_ref = (
        _persist_spec_ref(store, spec_kind="model") if include_model_ref else None
    )
    policy_spec_ref = (
        _persist_spec_ref(store, spec_kind="policy") if include_policy_ref else None
    )
    plan = _plan(
        tmp_path,
        model_spec_ref=model_spec_ref,
        policy_spec_ref=policy_spec_ref,
        exact_predictions=not include_model_ref and not include_policy_ref,
    )

    if runner_name == "orchestrator":
        report = BacktestOrchestrator(cas=store).run([plan])
        assert report.cas_artifact_id is not None
        report_ref = BacktestReportRef.model_validate(
            {"artifact_id": report.cas_artifact_id}
        )
    else:
        bundle = BacktestPlanBundle(
            contract_target=ContractCompatibilityTarget(
                contract_id="frc02_ref_transport",
                contract_fqn="polisyos.tests.FRC02ReferenceTransport",
            ),
            required_fields=["metric"],
            plans=[plan.model_dump(mode="json")],
            historical_payloads={"household": {"metric": [1.0, 1.05, 1.1, 1.15]}},
        )
        result = BacktestMatrixRunner(store).run({BacktestKind.HOUSEHOLD: bundle})
        assert result.backtest_report_ref is not None
        report_ref = result.backtest_report_ref

    return load_backtest_report(store, report_ref), model_spec_ref, policy_spec_ref


@pytest.mark.parametrize(
    "runner_name",
    ("orchestrator", "matrix"),
    ids=("orchestrator", "matrix"),
)
def test_plan_model_policy_refs_survive_orchestrator_and_matrix_persisted_report_roundtrip(
    runner_name: str,
    tmp_path: Path,
) -> None:
    """Persisted reports retain both refs supplied by their validation plan."""

    persisted, model_spec_ref, policy_spec_ref = _persisted_report(
        tmp_path,
        runner_name=runner_name,
        include_model_ref=True,
        include_policy_ref=True,
    )

    assert persisted.model_spec_ref == model_spec_ref
    assert persisted.policy_spec_ref == policy_spec_ref


@pytest.mark.parametrize(
    ("runner_name", "partial_ref"),
    (
        ("orchestrator", "model"),
        ("orchestrator", "policy"),
        ("matrix", "model"),
        ("matrix", "policy"),
    ),
    ids=(
        "orchestrator-model-only",
        "orchestrator-policy-only",
        "matrix-model-only",
        "matrix-policy-only",
    ),
)
def test_partial_plan_refs_fail_closed_after_persisted_report_roundtrip(
    runner_name: str,
    partial_ref: str,
    tmp_path: Path,
) -> None:
    """A partial model/policy pair cannot become report provenance."""

    persisted, _model_spec_ref, _policy_spec_ref = _persisted_report(
        tmp_path,
        runner_name=runner_name,
        include_model_ref=partial_ref == "model",
        include_policy_ref=partial_ref == "policy",
    )

    assert persisted.model_spec_ref is None
    assert persisted.policy_spec_ref is None
    assert persisted.degraded is True
    assert persisted.trust_eligible is False
    assert (
        "model_spec_ref/policy_spec_ref is incomplete across aggregated plans"
        in persisted.degraded_reasons
    )


@pytest.mark.parametrize(
    "runner_name",
    ("orchestrator", "matrix"),
    ids=("orchestrator", "matrix"),
)
def test_no_plan_refs_preserve_existing_report_compatibility(
    runner_name: str,
    tmp_path: Path,
) -> None:
    """Existing plans without specification refs remain valid no-ref reports."""

    persisted, model_spec_ref, policy_spec_ref = _persisted_report(
        tmp_path,
        runner_name=runner_name,
        include_model_ref=False,
        include_policy_ref=False,
    )

    assert model_spec_ref is None
    assert policy_spec_ref is None
    assert persisted.model_spec_ref is None
    assert persisted.policy_spec_ref is None
    assert persisted.degraded is False
    assert persisted.degraded_reasons == []


def test_different_plan_ref_pairs_fail_closed_in_persisted_report(
    tmp_path: Path,
) -> None:
    """Aggregating different complete pairs cannot mix report provenance."""

    store = FileSystemCAS(tmp_path / "orchestrator-cas")
    first_model_ref = _persist_spec_ref(store, spec_kind="model-a")
    first_policy_ref = _persist_spec_ref(store, spec_kind="policy-a")
    second_model_ref = _persist_spec_ref(store, spec_kind="model-b")
    second_policy_ref = _persist_spec_ref(store, spec_kind="policy-b")
    first = _plan(
        tmp_path,
        model_spec_ref=first_model_ref,
        policy_spec_ref=first_policy_ref,
        exact_predictions=True,
    )
    second = first.model_copy(
        update={
            "plan_id": "frc-02-ref-transport-second",
            "model_spec_ref": second_model_ref,
            "policy_spec_ref": second_policy_ref,
        }
    )

    report = BacktestOrchestrator(cas=store).run([first, second])
    assert report.cas_artifact_id is not None
    report_ref = BacktestReportRef.model_validate(
        {"artifact_id": report.cas_artifact_id}
    )
    persisted = load_backtest_report(store, report_ref)

    assert persisted.model_spec_ref is None
    assert persisted.policy_spec_ref is None
    assert persisted.degraded is True
    assert persisted.trust_eligible is False
    assert (
        "model_spec_ref/policy_spec_ref is inconsistent across aggregated plans"
        in persisted.degraded_reasons
    )


def _calibration_context(
    *,
    model_spec_ref: str,
    policy_spec_ref: str,
    **overrides: object,
) -> EmpiricalCalibrationContext:
    """Build the explicit semantic/time binding required by the producer."""

    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload: dict[str, object] = {
        "model_spec_ref": model_spec_ref,
        "policy_spec_ref": policy_spec_ref,
        "estimand": "average-treatment-effect-on-metric",
        "method_ref": "method://did",
        "method_version": "1.0.0",
        "rule_version_ref": "policyos.layer2.s10.outcome_prediction.v1",
        "calibration_threshold": 0.5,
        "calibration_threshold_ref": "threshold://frc02/s10-floor",
        "observed_outcome_ref": "observation://frc02/outcomes/v1",
        "prediction_ref": "prediction://frc02/held-out/v1",
        "evaluation_design_ref": "evaluation://frc02/design/v1",
        "credible_evaluation_evidence_ref": "evaluation-evidence://frc02/v1",
        "source_lineage_refs": ("source://panel/v1",),
        "method_lineage_refs": ("method-lineage://did/v1",),
        "prediction_time": start,
        "observation_time": start + timedelta(days=1),
        "policy_effective_time": start + timedelta(days=2),
        "data_valid_time": start + timedelta(days=3),
        "calibration_window_start": start - timedelta(days=30),
        "calibration_window_end": start - timedelta(days=1),
    }
    payload.update(overrides)
    return EmpiricalCalibrationContext.model_validate(payload)


def _persist_empirical_report(
    tmp_path: Path,
    *,
    within_ci: tuple[bool | None, ...],
    label: str,
    model_spec_ref: str | None = "model://frc02/v1",
    policy_spec_ref: str | None = "policy://frc02/v1",
    persisted_hit_count: int | None = None,
    persisted_evaluated_count: int | None = None,
    metadata: dict[str, object] | None = None,
    nominal_confidence_level: float | None = 0.95,
    force_first_observation_outside: bool = False,
) -> tuple[FileSystemCAS, BacktestReportRef, str | None, str | None]:
    """Persist a report whose interval counters can be reconciled from rows."""

    store = FileSystemCAS(tmp_path / f"bridge-{label}-cas")
    comparisons = [
        OutcomeComparison(
            metric_name=f"metric-{index}",
            y_pred=1.0 + index,
            y_true=(
                4.0
                if (force_first_observation_outside and index == 0) or inside is False
                else 1.0 + index
            ),
            absolute_error=(
                3.0
                if (force_first_observation_outside and index == 0) or inside is False
                else 0.0
            ),
            within_ci=inside,
            ci_lower=0.0 if inside is not None else None,
            ci_upper=3.0 if inside is not None else None,
        )
        for index, inside in enumerate(within_ci)
    ]
    evaluated = sum(inside is not None for inside in within_ci)
    hits = sum(inside is True for inside in within_ci)
    scenario = BacktestScenario(
        scenario_id="frc02-scenario",
        scenario_label="persisted FRC-02 empirical scenario",
        intervention_date="2026-01-01",
        data_source="measured-panel",
        outcome_comparisons=comparisons,
        requested_count=len(comparisons),
        compared_count=len(comparisons),
        interval_requested_count=len(comparisons),
        interval_available_count=evaluated,
        interval_evaluated_count=(
            evaluated if persisted_evaluated_count is None else persisted_evaluated_count
        ),
        interval_hit_count=hits if persisted_hit_count is None else persisted_hit_count,
        interval_availability=evaluated / len(comparisons) if comparisons else 0.0,
        interval_hit_rate=(hits / evaluated if evaluated else None),
        nominal_confidence_level=nominal_confidence_level,
        interval_type="prediction",
    )
    report_metadata: dict[str, object] = {
        "model_spec_ref": model_spec_ref,
        "policy_spec_ref": policy_spec_ref,
        "method_ref": "method://did",
        "method_version": "1.0.0",
        "rule_version_ref": "policyos.layer2.s10.outcome_prediction.v1",
        "estimand": "average-treatment-effect-on-metric",
    }
    report_metadata.update(metadata or {})
    report = BacktestReport(
        report_id=f"frc02-empirical-{label}",
        model_spec_ref=model_spec_ref,
        policy_spec_ref=policy_spec_ref,
        scenarios=[scenario],
        overall_coverage_probability=(hits / evaluated if evaluated else None),
        n_scenarios=1,
        n_metrics_evaluated=len(comparisons),
        metadata=report_metadata,
    )
    return store, persist_backtest_report(store, report), model_spec_ref, policy_spec_ref


def test_persisted_backtest_report_readback_produces_neutral_empirical_evidence(
    tmp_path: Path,
) -> None:
    """A persisted report produces reconciled evidence with the same identity refs."""

    store, report_ref, model_ref, policy_ref = _persist_empirical_report(
        tmp_path,
        within_ci=(True, False),
        label="positive",
    )
    persisted = load_backtest_report(store, report_ref)
    assert persisted.report_id == "frc02-empirical-positive"

    evidence = produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=_calibration_context(
            model_spec_ref=str(model_ref),
            policy_spec_ref=str(policy_ref),
        ),
    )

    assert evidence.evidence_kind == "observed_interval_comparisons"
    assert evidence.context_bound is True
    assert evidence.empirical_observations_available is True
    assert evidence.usable_for_calibration is True
    assert evidence.floor_passed is True
    assert (
        evidence.recomputed_numerator,
        evidence.recomputed_denominator,
        evidence.recomputed_pass_rate,
    ) == (1, 2, 0.5)
    assert (evidence.within_ci_numerator, evidence.within_ci_denominator) == (1, 2)
    assert (evidence.persisted_numerator, evidence.persisted_denominator) == (1, 2)
    assert evidence.observed_outcome_ref == "observation://frc02/outcomes/v1"
    assert evidence.failure_codes == ()


def test_observed_comparisons_change_empirical_admission_not_nominal_confidence(
    tmp_path: Path,
) -> None:
    """Changing observations changes the floor result; nominal CI does not."""

    pass_store, pass_ref, pass_model, pass_policy = _persist_empirical_report(
        tmp_path,
        within_ci=(True, True),
        label="all-hit",
    )
    fail_store, fail_ref, fail_model, fail_policy = _persist_empirical_report(
        tmp_path,
        within_ci=(True, False),
        label="one-miss",
    )
    pass_context = _calibration_context(
        model_spec_ref=str(pass_model),
        policy_spec_ref=str(pass_policy),
        calibration_threshold=1.0,
    )
    fail_context = _calibration_context(
        model_spec_ref=str(fail_model),
        policy_spec_ref=str(fail_policy),
        calibration_threshold=1.0,
    )

    passing = produce_empirical_calibration_evidence(
        pass_store, pass_ref, context=pass_context
    )
    limited = produce_empirical_calibration_evidence(
        fail_store, fail_ref, context=fail_context
    )

    assert passing.recomputed_pass_rate == 1.0
    assert passing.usable_for_calibration is True
    assert limited.recomputed_pass_rate == 0.5
    assert limited.usable_for_calibration is False
    assert limited.floor_passed is False
    assert "calibration_floor_not_met" in limited.failure_codes


def test_nominal_confidence_without_observations_is_not_empirical_evidence(
    tmp_path: Path,
) -> None:
    """A nominal confidence field cannot create an empirical denominator."""

    store, report_ref, model_ref, policy_ref = _persist_empirical_report(
        tmp_path,
        within_ci=(None,),
        label="nominal-only",
    )
    evidence = produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=_calibration_context(
            model_spec_ref=str(model_ref),
            policy_spec_ref=str(policy_ref),
        ),
    )

    assert evidence.evidence_kind == "unavailable"
    assert evidence.recomputed_denominator == 0
    assert evidence.recomputed_pass_rate is None
    assert evidence.usable_for_calibration is False
    assert "nominal_confidence_only" in evidence.failure_codes
    assert "zero_observation_denominator" in evidence.failure_codes


@pytest.mark.parametrize(
    "case",
    (
        "incomplete_pair",
        "mixed_pair_refs",
        "persisted_counter_mismatch",
        "model_binding_mismatch",
        "rule_binding_mismatch",
        "estimand_mismatch",
    ),
)
def test_empirical_producer_fail_closed_negative_matrix(case: str, tmp_path: Path) -> None:
    """Missing or incompatible identity/evidence never becomes usable evidence."""

    report_kwargs: dict[str, object] = {"within_ci": (True, False), "label": case}
    context_overrides: dict[str, object] = {}
    metadata: dict[str, object] = {}
    if case == "incomplete_pair":
        report_kwargs.update({"model_spec_ref": None, "policy_spec_ref": None})
    elif case == "mixed_pair_refs":
        metadata.update({"model_spec_refs": ["model://frc02/v1", "model://frc02/v2"]})
    elif case == "persisted_counter_mismatch":
        report_kwargs["persisted_hit_count"] = 0
    elif case == "model_binding_mismatch":
        context_overrides["model_spec_ref"] = "model://other/v1"
    elif case == "rule_binding_mismatch":
        metadata["rule_version_ref"] = "policyos.layer2.s10.outcome_prediction.v0"
    elif case == "estimand_mismatch":
        metadata["estimand"] = "different-estimand"

    store, report_ref, model_ref, policy_ref = _persist_empirical_report(
        tmp_path,
        metadata=metadata,
        **report_kwargs,
    )
    context = _calibration_context(
        model_spec_ref=str(model_ref or "model://frc02/v1"),
        policy_spec_ref=str(policy_ref or "policy://frc02/v1"),
        **context_overrides,
    )
    evidence = produce_empirical_calibration_evidence(store, report_ref, context=context)

    assert evidence.usable_for_calibration is False
    assert evidence.failure_codes


def test_within_ci_flags_cannot_override_recomputed_bounds(tmp_path: Path) -> None:
    """A contradictory persisted flag blocks evidence derived from actual bounds."""

    store, report_ref, model_ref, policy_ref = _persist_empirical_report(
        tmp_path,
        within_ci=(True, False),
        force_first_observation_outside=True,
        label="contradictory-flag",
    )
    evidence = produce_empirical_calibration_evidence(
        store,
        report_ref,
        context=_calibration_context(
            model_spec_ref=str(model_ref),
            policy_spec_ref=str(policy_ref),
        ),
    )

    assert (evidence.recomputed_numerator, evidence.recomputed_denominator) == (0, 2)
    assert (evidence.within_ci_numerator, evidence.within_ci_denominator) == (1, 2)
    assert evidence.usable_for_calibration is False
    assert "within_ci_mismatch" in evidence.failure_codes


def test_producer_without_explicit_context_remains_non_usable(tmp_path: Path) -> None:
    """Report observations alone do not establish the semantic caller binding."""

    store, report_ref, _model_ref, _policy_ref = _persist_empirical_report(
        tmp_path,
        within_ci=(True,),
        label="unbound",
    )

    evidence = produce_empirical_calibration_evidence(store, report_ref)

    assert evidence.empirical_observations_available is True
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False
    assert "explicit_context_missing" in evidence.failure_codes


def test_calibration_context_rejects_duplicate_times_and_synthetic_lineage() -> None:
    """The typed caller context rejects temporal aliasing and fake provenance."""

    with pytest.raises(ValueError, match="temporal roles"):
        _calibration_context(
            model_spec_ref="model://frc02/v1",
            policy_spec_ref="policy://frc02/v1",
            observation_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="synthetic|self-attested"):
        _calibration_context(
            model_spec_ref="model://frc02/v1",
            policy_spec_ref="policy://frc02/v1",
            source_lineage_refs=("synthetic_fixture://not-evidence",),
        )
