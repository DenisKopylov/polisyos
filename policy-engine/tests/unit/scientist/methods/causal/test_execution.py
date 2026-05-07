from __future__ import annotations

from datetime import date

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.dual_certificate import (
    load_dual_certificate_bundle,
    validate_dual_certificate_bundle,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    TighteningStatus,
    load_bounds_bundle,
    load_bounds_tightening_log,
)
from polisyos.ir.observation.bundles import BoundsChannelSpec, BoundsEstimationBundle
from polisyos.ir.observation.causal_execution import BoundsEstimationTask
from polisyos.ir.observation.contract_compilers import (
    BoundsEstimationCompileSpec,
    BoundsEstimationInput,
    ObservationContractCompilerSuite,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.ir.types import TimeFrequency
from polisyos.scientist.methods.causal.execution import BoundsEstimationRunner


def _period() -> tuple[date, date]:
    return date(2024, 3, 1), date(2024, 3, 31)


def _bounds_input(*, selected: list[float] | None = None) -> BoundsEstimationInput:
    outcome = [0.1, 0.2, 0.15, 0.3, 0.75, 0.8, 0.85, 0.9]
    treatment = [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
    instrument = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    return BoundsEstimationInput(
        outcome=[
            value if selected is None else value * flag
            for value, flag in zip(outcome, selected, strict=False)
        ],
        treatment=treatment,
        instrument=instrument,
        selected=selected,
    )


def _bounds_bundle() -> BoundsEstimationBundle:
    return BoundsEstimationBundle(
        channels=[
            BoundsChannelSpec(
                family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                bound_strategy="selection_bounds",
                fallback_reason="synthetic_test",
            )
        ]
    )


def _panel(*, selected_pattern: list[float]) -> ObservationPanel:
    period_start, period_end = _period()
    records: list[ObservationRecord] = []
    outcome = [0.1, 0.2, 0.15, 0.3, 0.75, 0.8, 0.85, 0.9]
    treatment = [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
    instrument = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    miv_proxy = [0.0, 0.1, 0.2, 0.3, 0.6, 0.7, 0.8, 0.9]
    for unit_idx in range(len(outcome)):
        unit_id = f"hh_{unit_idx:02d}"
        metrics = {
            "outcome_score": outcome[unit_idx] * selected_pattern[unit_idx],
            "treatment": treatment[unit_idx],
            "instrument": instrument[unit_idx],
            "selected": selected_pattern[unit_idx],
            "miv_proxy": miv_proxy[unit_idx],
        }
        for metric_id, value in metrics.items():
            records.append(
                ObservationRecord(
                    observation_id=f"obs_{unit_id}_{metric_id}",
                    family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                    time_grain=TimeFrequency.MONTH,
                    period_start=period_start,
                    period_end=period_end,
                    entity_scope=EntityScope.HOUSEHOLD,
                    entity_id=unit_id,
                    metric_id=metric_id,
                    observed_value=value,
                    unit="value",
                    coverage_estimate=0.95,
                    measurement_bias_flag=False,
                    censoring_mask=False,
                    trust_weight=1.0,
                    lag_days_estimate=1,
                    source_id="synthetic_bounds_panel",
                    source_version="1.0",
                    regime_id="ua_2024",
                    shock_mask=False,
                    schema_regime_id="schema_v1",
                    identification_mode=IdentificationMode.BOUNDS_ONLY,
                    source_confidence_tier=SourceConfidenceTier.VALIDATED,
                )
            )
    return ObservationPanel(
        panel_id="synthetic_bounds_panel",
        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        time_grain=TimeFrequency.MONTH,
        records=records,
    )


def test_bounds_estimation_runner_persists_interval_and_width_reflects_censoring(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    runner = BoundsEstimationRunner(store=store)
    low_censoring = BoundsEstimationTask(
        task_id="bounds_low_censoring",
        bounds_input=_bounds_input(selected=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        bundle=_bounds_bundle(),
        params={"has_selection": True},
    )
    high_censoring = BoundsEstimationTask(
        task_id="bounds_high_censoring",
        bounds_input=_bounds_input(selected=[1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]),
        bundle=_bounds_bundle(),
        params={"has_selection": True},
    )

    low_entry, high_entry = runner.run([low_censoring, high_censoring])

    assert low_entry.status == "ok"
    assert low_entry.interval is not None
    assert low_entry.bounds_bundle_ref is not None
    assert high_entry.status == "ok"
    assert high_entry.interval is not None
    assert high_entry.width is not None
    assert low_entry.width is not None
    assert high_entry.width >= low_entry.width

    persisted = load_bounds_bundle(store, low_entry.bounds_bundle_ref)
    assert persisted.lower_bound is not None
    assert persisted.upper_bound is not None


def test_bounds_estimation_runner_enables_iv_selection_and_surfaces_missing_path_warnings(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    runner = BoundsEstimationRunner(store=store)
    ok_task = BoundsEstimationTask(
        task_id="bounds_iv_and_selection",
        bounds_input=_bounds_input(selected=[1.0] * 8),
        bundle=_bounds_bundle(),
    )
    warning_task = BoundsEstimationTask(
        task_id="bounds_missing_selection",
        bounds_input=BoundsEstimationInput(
            outcome=[0.1, 0.2, 0.8, 0.9],
            treatment=[0.0, 0.0, 1.0, 1.0],
        ),
        bundle=_bounds_bundle(),
        params={"has_selection": True, "has_iv": True},
    )

    ok_entry, warning_entry = runner.run([ok_task, warning_task])

    assert ok_entry.bounds_bundle_ref is not None
    ok_bundle = load_bounds_bundle(store, ok_entry.bounds_bundle_ref)
    methods = {summary.method for summary in ok_bundle.method_summaries}
    assert BoundMethod.LP_BALKE_PEARL in methods
    assert BoundMethod.IV_BOUNDS in methods

    assert warning_entry.status == "ok"
    assert any("skipped" in warning.lower() for warning in warning_entry.warnings)


def test_c3_bounds_compiler_to_runner_integration_produces_interval_output(tmp_path) -> None:
    suite = ObservationContractCompilerSuite()
    compiled = suite.compile_all(
        observation_panel=_panel(selected_pattern=[1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]),
        bounds_spec=BoundsEstimationCompileSpec(
            spec_id="bounds_spec",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            instrument_metric_id="instrument",
            selected_metric_id="selected",
            miv_proxy_metric_id="miv_proxy",
        ),
    )

    artifact = compiled.artifacts["bounds_estimation_input"]
    runner = BoundsEstimationRunner(store=FileSystemCAS(tmp_path))
    [entry] = runner.run(
        [
            BoundsEstimationTask(
                task_id="compiled_bounds_task",
                bounds_input=artifact.contract,
                bundle=artifact.bundle,
            )
        ]
    )

    assert entry.status == "ok"
    assert entry.interval is not None
    assert entry.bounds_bundle_ref is not None


def test_bounds_estimation_runner_sanitizes_non_finite_thresholds(tmp_path) -> None:
    runner = BoundsEstimationRunner(store=FileSystemCAS(tmp_path))
    [entry] = runner.run(
        [
            BoundsEstimationTask(
                task_id="nan-threshold",
                bounds_input=_bounds_input(selected=[1.0] * 8),
                bundle=_bounds_bundle(),
                params={"informative_threshold": float("nan")},
            )
        ]
    )

    assert entry.status == "ok"
    assert entry.bounds_bundle_ref is not None


def test_bounds_estimation_runner_persists_dual_certificate_for_exact_auto_bounds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    runner = BoundsEstimationRunner(store=store)
    [entry] = runner.run(
        [
            BoundsEstimationTask(
                task_id="exact-auto-bounds",
                bounds_input=BoundsEstimationInput(
                    outcome=[0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                    treatment=[0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
                ),
                bundle=_bounds_bundle(),
                params={"use_auto_bounds": True, "has_monotone": True},
            )
        ]
    )

    assert entry.status == "ok"
    assert entry.bounds_bundle_ref is not None
    bundle = load_bounds_bundle(store, entry.bounds_bundle_ref)
    assert bundle.dual_certificate_ref is not None
    assert bundle.sharpness_status == "sharp"
    assert bundle.tightening_status is TighteningStatus.IMPROVED
    assert bundle.best_in_class_claim is not None
    assert bundle.tightening_log_ref is not None
    assert bundle.best_in_class_claim.proof_ref == bundle.tightening_log_ref

    cert = load_dual_certificate_bundle(store, bundle.dual_certificate_ref)
    validation = validate_dual_certificate_bundle(cert)
    assert validation.ok, validation.errors
    tightening_log = load_bounds_tightening_log(store, bundle.tightening_log_ref)
    assert tightening_log.status is TighteningStatus.IMPROVED
    assert tightening_log.entries


def test_bounds_estimation_runner_persists_dual_certificate_for_exact_iv_bounds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    runner = BoundsEstimationRunner(store=store)
    [entry] = runner.run(
        [
            BoundsEstimationTask(
                task_id="exact-iv-bounds",
                bounds_input=BoundsEstimationInput(
                    outcome=[0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                    treatment=[0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
                    instrument=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
                ),
                bundle=_bounds_bundle(),
                params={"has_iv": True, "use_auto_bounds": True},
            )
        ]
    )

    assert entry.status == "ok"
    assert entry.bounds_bundle_ref is not None
    bundle = load_bounds_bundle(store, entry.bounds_bundle_ref)
    assert bundle.dual_certificate_ref is not None
    assert bundle.sharpness_status == "sharp"
    assert bundle.tightening_status is TighteningStatus.IMPROVED
    assert bundle.best_in_class_claim is not None
    assert bundle.tightening_log_ref is not None
    assert bundle.best_in_class_claim.proof_ref == bundle.tightening_log_ref

    cert = load_dual_certificate_bundle(store, bundle.dual_certificate_ref)
    validation = validate_dual_certificate_bundle(cert)
    assert validation.ok, validation.errors
    tightening_log = load_bounds_tightening_log(store, bundle.tightening_log_ref)
    assert tightening_log.status is TighteningStatus.IMPROVED
    assert tightening_log.entries
