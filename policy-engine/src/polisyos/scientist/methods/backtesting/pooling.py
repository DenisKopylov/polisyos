"""Bind preselected backtest pooling to Catalog meaning and exact source rows."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ArtifactRef,
    ensure_ir_artifact_store,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    compare_measurement_representation_axes,
    load_variable_representation,
)
from polisyos.fabric.connectors.types.fixed_units import (
    FixedUnitFactorError,
    resolve_fixed_unit_factor,
)
from polisyos.ir.analytics.backtest_pooling import (
    BacktestFixedUnitTransform,
    BacktestPoolingMeasure,
    BacktestPoolingMember,
    BacktestPoolingPolicy,
    SelectedDefinitionRef,
    load_backtest_pooling_policy,
    read_selected_inputs,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.methods.backtesting.plan import PredictionSource

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
    from polisyos.core.run.context import RunContext
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.ir.analytics.backtest import BacktestReport
    from polisyos.ir.analytics.backtest_pooling import BacktestPoolingPolicyRef
    from polisyos.ir.artifacts import ArtifactStore
    from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan

_AXES = (
    MeasurementAxis.QUANTITY_KIND,
    MeasurementAxis.MEASURE_FORM,
    MeasurementAxis.UNIT_ID,
    MeasurementAxis.SCALE_TO_UNIT,
    MeasurementAxis.TIME_SUPPORT,
    MeasurementAxis.AGGREGATION,
    MeasurementAxis.GRAIN,
    MeasurementAxis.POPULATION_REF,
)


@dataclass(frozen=True, slots=True)
class SelectedBacktestPoolingRun:
    """Select the independently retained Core run and its exact terminal profile."""

    run_dir: Path
    run_id: str
    terminal_ref: ArtifactRef
    access_scope: AccessScope | None = None


class BacktestPoolingRunSelectionRequiredError(ValueError):
    """A pooled report requires an independent terminal run selection."""


def record_backtest_pooling_policy(
    context: RunContext,
    store: CoreArtifactStore,
    ref: BacktestPoolingPolicyRef,
) -> None:
    """Record a previously resolved policy on its active Core run before row intake."""
    if context.store is not store or context.trace_path is None or context._active_lease is None:
        raise ValueError("backtest pooling requires an active run on the same artifact store")
    if any(item.kind == ref.kind for item in context.run_manifest.inputs):
        raise ValueError("backtest pooling run already selected a policy")
    context.add_input(ArtifactRef.model_validate(dict(ref)))


def _verify_selected_run(
    store: CoreArtifactStore,
    selected: SelectedBacktestPoolingRun,
    report_ref: BacktestReportRef,
    policy_ref: BacktestPoolingPolicyRef,
) -> None:
    from polisyos.core.run.context import read_terminal_run
    from polisyos.core.trace.record import TraceRecord

    if selected.terminal_ref.manifest_profile_sha256 is None:
        raise ValueError("backtest pooling requires an exact selected terminal run profile")
    terminal = read_terminal_run(
        store, selected.run_dir, run_id=selected.run_id, access_scope=selected.access_scope
    )
    if terminal.run_ref != selected.terminal_ref or terminal.run_manifest.status != "ok":
        raise ValueError("backtest pooling terminal selection differs")
    policy = ArtifactRef.model_validate(dict(policy_ref))
    report = ArtifactRef.model_validate(dict(report_ref))
    manifest = terminal.run_manifest
    if [item for item in manifest.inputs if item.kind == policy.kind] != [policy]:
        raise ValueError("backtest pooling terminal policy differs")
    if manifest.outputs.count(report) != 1 or manifest.trace_ref is None:
        raise ValueError("backtest pooling terminal report selection differs")

    policy_events: list[int] = []
    report_events: list[int] = []
    for index, line in enumerate(store.get_bytes(manifest.trace_ref).splitlines()):
        record = TraceRecord.model_validate_json(line)
        if record.event == "RUN_INPUT_ADDED" and policy in record.refs.inputs:
            policy_events.append(index)
        if record.event == "RUN_OUTPUT_ADDED" and report in record.refs.outputs:
            report_events.append(index)
    if len(policy_events) != 1 or len(report_events) != 1 or policy_events[0] >= report_events[0]:
        raise ValueError("backtest pooling run input and output order differs")


def _selected_window(
    store: ArtifactStore,
    member: BacktestPoolingMember,
) -> tuple[dict[str, object], tuple[float, ...]]:
    source = member.historical_rows_ref
    representation = member.comparison_representation_ref
    if representation is not None:
        role = f"measurement:{member.metric_name}"
        edges = [edge for edge in read_selected_inputs(store, source) if edge.role == role]
        if edges != [
            InputRef(
                artifact_id=representation.artifact_id,
                role=role,
                manifest_profile_sha256=representation.manifest_profile_sha256,
            )
        ]:
            raise ValueError("backtest selected source does not bind the declared measurement")
    data = load_core_json_artifact(store, ArtifactRef.model_validate(dict(source)))
    if not isinstance(data, dict):
        raise ValueError("backtest pooling requires a historical source object")
    values = data.get(member.metric_name)
    times = data.get("time_index")
    start = member.observation_start
    stop = start + len(member.predictions)
    if (
        not isinstance(values, list)
        or not isinstance(times, list)
        or len(values) != len(times)
        or len(values) < stop
    ):
        raise ValueError("backtest pooling holdout window is outside the selected source")
    selected = values[start:stop]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in selected):
        raise ValueError("backtest pooling holdout window must contain finite numeric values")
    return data, tuple(float(value) for value in selected)


def _resolve_measurement(
    store: ArtifactStore,
    member: BacktestPoolingMember,
) -> BacktestPoolingMeasure:
    raw_ref = member.comparison_representation_ref
    canonical_ref = member.canonical_representation_ref
    if raw_ref is None or canonical_ref is None:
        return BacktestPoolingMeasure(limitation="measurement_comparability_unknown")
    raw = load_variable_representation(
        store, VariableRepresentationRef.model_validate(dict(raw_ref))
    )
    canonical = load_variable_representation(
        store, VariableRepresentationRef.model_validate(dict(canonical_ref))
    )
    validate_core_model_json_artifact(
        VariableSemanticDefinition, store, raw.semantic_definition_ref
    )
    if raw.semantic_definition_ref != canonical.semantic_definition_ref:
        validate_core_model_json_artifact(
            VariableSemanticDefinition, store, canonical.semantic_definition_ref
        )
        return BacktestPoolingMeasure(limitation="measurement_quantity_differs")
    if raw.unit_id is None or canonical.unit_id is None:
        return BacktestPoolingMeasure(limitation="measurement_unit_unknown")

    required = _AXES
    if raw.time_support != "not_applicable" or canonical.time_support != "not_applicable":
        required += (MeasurementAxis.TEMPORAL_GRANULARITY,)
    if (
        raw.measure_form in {"ratio", "rate"}
        or canonical.measure_form in {"ratio", "rate"}
        or raw.numerator_ref is not None
        or canonical.numerator_ref is not None
        or raw.denominator_ref is not None
        or canonical.denominator_ref is not None
    ):
        required += (MeasurementAxis.NUMERATOR_REF, MeasurementAxis.DENOMINATOR_REF)
    axes = MeasurementBindingProfile(
        schema_version="polisyos.catalog.measurement_binding_profile.v3",
        profile_id="scientist.backtest.fixed_unit_pooling",
        revision="1",
        required_axes=required,
        optional_axes=(MeasurementAxis.METHODOLOGY_REF, MeasurementAxis.MONEY_UNIT),
    )
    # Unit equality is checked after holding every other representation axis fixed.
    # The claimed unit change itself is established by the Fabric owner below.
    _, _, reasons = compare_measurement_representation_axes(
        raw.model_copy(update={"unit_id": canonical.unit_id}), canonical, axes
    )
    if (
        reasons
        or raw.methodology_ref != canonical.methodology_ref
        or raw.money_unit != canonical.money_unit
    ):
        return BacktestPoolingMeasure(limitation="measurement_representation_scope_differs")
    transform = None
    if raw.unit_id != canonical.unit_id:
        try:
            factor = resolve_fixed_unit_factor(raw.unit_id, canonical.unit_id)
        except FixedUnitFactorError as exc:
            return BacktestPoolingMeasure(limitation=exc.code)
        transform = BacktestFixedUnitTransform.model_validate(asdict(factor))
    return BacktestPoolingMeasure(
        semantic_definition_ref=SelectedDefinitionRef.model_validate(
            dict(canonical.semantic_definition_ref.model_dump(mode="json"))
        ),
        canonical_unit=canonical.unit_id,
        transform=transform,
    )


def prepare_backtest_pooling(
    store: ArtifactStore,
    policy: BacktestPoolingPolicy,
    plans: Sequence[HistoricalValidationPlan],
) -> tuple[BacktestPoolingMeasure, ...]:
    """Resolve a selected policy and every declared holdout before forecasting."""
    from polisyos.scientist.methods.backtesting.masking import OutcomeMasker

    by_id = {plan.plan_id: plan for plan in plans}
    if len(by_id) != len(plans) or set(by_id) != {member.scenario_id for member in policy.members}:
        raise ValueError("backtest pooling policy and incoming plans differ")
    measures: list[BacktestPoolingMeasure] = []
    for member in policy.members:
        plan = by_id[member.scenario_id]
        selection = plan.historical_replay_source
        metric = member.metric_name
        if (
            plan.prediction_source is not PredictionSource.PROVIDED
            or selection is None
            or selection.source_data_ref.model_dump(mode="json") != dict(member.historical_rows_ref)
            or plan.target_metrics != [metric]
            or set(plan.ground_truth_outcomes) != {metric}
            or plan.predicted_outcomes != {metric: list(member.predictions)}
        ):
            raise ValueError("backtest pooling plan differs from the preselected provided case")
        source, observed = _selected_window(store, member)
        if (
            tuple(plan.ground_truth_outcomes[metric]) != observed
            or OutcomeMasker._resolve_cutoff(source, plan) != member.observation_start
        ):
            raise ValueError("backtest pooling plan and selected holdout differ")
        measures.append(_resolve_measurement(store, member))
    return tuple(measures)


def load_pooled_backtest_report(
    store: CoreArtifactStore,
    ref: BacktestReportRef,
    *,
    selected_run: SelectedBacktestPoolingRun | None = None,
) -> BacktestReport:
    """Verify a saved comparison against selected measurements, factors and holdout rows."""
    from polisyos.ir.analytics.backtest import load_backtest_report_candidate

    ir_store = ensure_ir_artifact_store(store)
    report = load_backtest_report_candidate(ir_store, ref)
    projection = report.pooling
    if projection is None:
        raise ValueError("backtest report has no selected pooling policy")
    if selected_run is None:
        raise BacktestPoolingRunSelectionRequiredError("backtest_pooling_run_selection_required")
    provided = PredictionSource.PROVIDED.value
    if report.prediction_mode_requested != provided or report.prediction_mode_effective != provided:
        raise ValueError("backtest pooling requires the selected provided prediction source")
    policy = load_backtest_pooling_policy(ir_store, projection.policy_ref)
    by_id = {scenario.scenario_id: scenario for scenario in report.scenarios}
    for member, measure in zip(policy.members, projection.measures, strict=True):
        if _resolve_measurement(ir_store, member) != measure:
            raise ValueError("backtest pooling measurement or applied factor differs")
        _, observed = _selected_window(ir_store, member)
        scenario = by_id[member.scenario_id]
        raw_pairs = [
            (prediction, actual)
            for prediction, actual in zip(member.predictions, observed, strict=True)
            if math.isfinite(prediction - actual)
        ]
        if (
            scenario.data_source != str(member.historical_rows_ref.artifact_id)
            or scenario.requested_count != len(observed)
            or scenario.metadata.get("prediction_source_requested") != provided
            or scenario.metadata.get("prediction_source_effective") != provided
            or [(row.y_pred, row.y_true) for row in scenario.outcome_comparisons] != raw_pairs
        ):
            raise ValueError("backtest pooling report rows differ from the selected holdout")
    _verify_selected_run(store, selected_run, ref, projection.policy_ref)
    return report
