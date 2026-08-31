"""Optimize Foundry mechanism parameters against observed targets and diagnostics.

`Calibrator` owns the synthetic-vs-observed boundary for calibration: it
generates synthetic traces with `run_pure_scan()`, compares them to either raw
target series or a `CalibrationTargetBundle`, applies measurement-aware and
auxiliary penalties, and returns a persisted-report-ready `CalibrationReport`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import optax
from jax.flatten_util import ravel_pytree

from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph
from polisyos.core.observability import get_metrics, get_tracer, is_hpc_observability_enabled
from polisyos.foundry.calibration.auxiliary import AuxLossComponent
from polisyos.foundry.calibration.bijectors import (
    from_unconstrained,
    make_bijector,
    to_unconstrained,
)
from polisyos.foundry.calibration.hessian import HessianResult, compute_hessian
from polisyos.foundry.calibration.identifiability import diagnose_identifiability
from polisyos.foundry.calibration.loss import (
    compute_base_loss,
    pointwise_base_loss,
    reduce_weighted_loss,
)
from polisyos.foundry.calibration.measurement import (
    CalibrationTargetBundle,
    DefaultMeasurementAwareLossAdapter,
    MeasurementAwareLossAdapter,
    MeasurementAwareLossConfig,
)
from polisyos.foundry.calibration.preflight import fetch_targets, prepare_targets, resolve_steps
from polisyos.foundry.calibration.pure_executor import (
    StaticBundle,
    apply_trainable_values,
    compile_program,
    extract_trainable_values,
    run_pure_scan,
)
from polisyos.foundry.calibration.report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
    CalibrationSeriesComparison,
    CalibrationUncertainty,
)
from polisyos.foundry.calibration.uncertainty_adapter import envelopes_from_calibration
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    TrainableParamRef,
)
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
)


@dataclass
class CalibratorInputs:
    """Bundle the runtime contracts and callbacks required by `Calibrator.run()`.

    Attributes:
        config: Optimization, target, and loss configuration.
        program_graph: Compiled graph whose nodes will be replayed in-memory.
        exec_plan: Execution order and runtime flags for the graph.
        base_state: Synthetic initial `GlobalState` snapshot used by simulation.
        mechanism_registry: Mechanism registry for node instantiation.
        slot_registry: Slot schema used to evaluate metrics and merge patches.
        merge_registry: Merge rules used by the pure executor.
        selector_field_registry: Optional selector-field mapping for mask
            evaluation.
        parameter_loader: Callback that resolves node parameters/schedules
            deterministically from `params_ref` or node payloads.
        constraint_registry: Optional governance constraints to penalize.
        constraint_values: Optional right-hand-side values for constraint IDs.
        raw_targets: Optional observed series supplied directly by the caller.
        controls_seq: Optional control sequence used to set the scan horizon.
        udf_engine: Optional Fabric query engine for target fetching.
        target_fetcher: Optional custom fetch callback overriding `udf_engine`.
        measurement_bundle: Optional measurement-aware observed target bundle.
        measurement_loss_config: Optional discount config for observation
            metadata.
        measurement_loss_adapter: Optional custom loss adapter; defaults to
            `DefaultMeasurementAwareLossAdapter`.
        aux_loss_components: Optional extra penalties computed from synthetic
            traces, such as interference losses.
    """

    config: CalibrationConfig
    program_graph: ProgramGraph
    exec_plan: ExecPlan
    base_state: GlobalState
    mechanism_registry: MechanismTypeRegistry
    slot_registry: SlotRegistry
    merge_registry: MergeRuleRegistry
    selector_field_registry: SelectorFieldRegistry | None
    parameter_loader: Callable[[Any], dict[str, Any]]
    constraint_registry: ConstraintRegistry | None = None
    constraint_values: Mapping[str, float] | None = None
    raw_targets: Mapping[str, object] | None = None
    controls_seq: jnp.ndarray | None = None
    udf_engine: Any | None = None
    target_fetcher: Callable[[CalibrationTarget, Any], object] | None = None
    measurement_bundle: CalibrationTargetBundle | None = None
    measurement_loss_config: MeasurementAwareLossConfig | None = None
    measurement_loss_adapter: MeasurementAwareLossAdapter | None = None
    aux_loss_components: Sequence[AuxLossComponent] | None = None


@dataclass
class TrainableGroup:
    """Represent one tied optimizer variable shared by multiple mechanism fields."""

    group_id: str
    handle_indices: list[int]
    lower: float | None
    upper: float | None
    prior_mean: float | None = None
    prior_std: float | None = None


@dataclass
class ConstraintHandle:
    """Normalize one constraint into a metric path, operator, and threshold."""

    constraint_id: str
    operator: str
    path: str
    value: float


@dataclass
class CalibrationMetricsCollector:
    """Batch optimizer telemetry and emit it periodically to observability sinks."""

    optimizer_name: str
    emit_interval: int = 10
    enabled: bool = True

    _step_durations: list[tuple[float, bool]] = field(default_factory=list)
    _losses: list[float] = field(default_factory=list)
    _grad_norms: list[float] = field(default_factory=list)
    _current_step: int = 0
    _metrics_cached: Any = None

    def record_step(
        self,
        step: int,
        duration_seconds: float,
        loss: float,
        grad_norm: float,
        is_warmup: bool,
    ) -> None:
        """Record one optimizer step and flush when the emit interval is reached."""
        if not self.enabled:
            return
        self._step_durations.append((duration_seconds, is_warmup))
        self._losses.append(loss)
        self._grad_norms.append(grad_norm)
        self._current_step = step

        if len(self._step_durations) >= self.emit_interval:
            self._flush()

    def _get_metrics(self):
        if self._metrics_cached is None:
            self._metrics_cached = get_metrics()
        return self._metrics_cached

    def _flush(self) -> None:
        if not self.enabled or not self._step_durations:
            return

        metrics = self._get_metrics()
        attrs = {"optimizer": self.optimizer_name}

        if metrics.calibration_step_duration_seconds:
            for duration, is_warmup in self._step_durations:
                metrics.calibration_step_duration_seconds.record(
                    duration,
                    {**attrs, "is_warmup": "true" if is_warmup else "false"},
                )

        if self._losses and metrics.calibration_loss:
            metrics.calibration_loss.set(self._losses[-1], attrs)

        if self._grad_norms and metrics.calibration_grad_norm:
            metrics.calibration_grad_norm.set(self._grad_norms[-1], attrs)

        self._step_durations.clear()
        self._losses.clear()
        self._grad_norms.clear()

    def finalize(self, convergence_reason: str, total_steps: int) -> None:
        """Flush remaining metrics and emit final convergence-step telemetry."""
        if not self.enabled:
            return
        self._flush()

        metrics = self._get_metrics()
        if metrics.calibration_convergence_steps:
            metrics.calibration_convergence_steps.record(
                total_steps,
                {
                    "optimizer": self.optimizer_name,
                    "convergence_reason": convergence_reason,
                },
            )


def _compute_scale_local(
    arr: jnp.ndarray, target_cfg: CalibrationTarget, default_eps: float = 1e-8
) -> float:
    if not target_cfg.loss.relative:
        return 1.0
    method = target_cfg.loss.scale
    abs_arr = jnp.abs(arr)
    if method == "std":
        scale = jnp.std(arr)
    elif method == "max":
        scale = jnp.max(abs_arr)
    elif method == "p95":
        scale = jnp.quantile(abs_arr, 0.95)
    elif method == "none":
        scale = jnp.array(1.0)
    else:
        scale = jnp.mean(abs_arr)
    return float(jnp.maximum(scale, default_eps))


def _measurement_time_axis(values: Sequence[Any] | None) -> list[float] | None:
    if values is None:
        return None
    result: list[float] = []
    for value in values:
        if isinstance(value, (int, float, np.integer, np.floating)):
            result.append(float(value))
            continue
        text = str(value)
        try:
            result.append(float(datetime.fromisoformat(text).date().toordinal()))
        except ValueError:
            result.append(float(len(result)))
    return result


def _selector_key(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump"):
        try:
            return json.dumps(value.model_dump(), sort_keys=True)
        except TypeError:
            return str(value)
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)


def _match_trainable(handle: Any, ref: TrainableParamRef) -> bool:
    if ref.param_id != handle.field_name:
        return False
    if ref.node_id is not None and ref.node_id != handle.node_id:
        return False
    if ref.mechanism_type is not None and ref.mechanism_type != handle.mechanism_type:
        return False
    if ref.selector is not None:
        if handle.selector is None:
            return False
        if _selector_key(handle.selector) != _selector_key(ref.selector):
            return False
    return True


def _resolve_metric_path(path: str, slot_registry: SlotRegistry) -> str:
    slot_spec = slot_registry.slots.get(path)
    if slot_spec is None:
        return path
    if not slot_spec.state_path:
        raise ValueError(f"Slot '{path}' missing state_path for calibration")
    return slot_spec.state_path


def _apply_aggregation(series: jnp.ndarray, aggregation: str) -> jnp.ndarray:
    if aggregation == "none":
        return series
    if series.ndim <= 1:
        return series
    axes = tuple(range(1, series.ndim))
    if aggregation == "mean":
        return jnp.mean(series, axis=axes)
    if aggregation == "sum":
        return jnp.sum(series, axis=axes)
    if aggregation == "min":
        return jnp.min(series, axis=axes)
    if aggregation == "max":
        return jnp.max(series, axis=axes)
    return series


def _as_float_list(values: Any) -> list[float]:
    arr = np.asarray(values, dtype=float).reshape(-1)
    return [float(item) for item in arr]


def _as_float_matrix(values: Any) -> list[list[float]]:
    arr = np.atleast_2d(np.asarray(values, dtype=float))
    return [[float(item) for item in row] for row in arr.tolist()]


def _inspect_bundle_fidelity(bundle: StaticBundle) -> dict[str, Any]:
    modes: set[str] = set()
    temperatures: list[float] = []
    for node in bundle.nodes:
        mech = node.mechanism
        if hasattr(mech, "fidelity"):
            modes.add(str(mech.fidelity))
        if hasattr(mech, "temperature"):
            temp = float(mech.temperature)
            temperatures.append(temp)
    if not modes:
        effective = "unknown"
    elif len(modes) == 1:
        effective = next(iter(modes))
    else:
        effective = "mixed"
    avg_temperature = None
    if temperatures:
        avg_temperature = sum(temperatures) / len(temperatures)
    return {
        "effective_fidelity": effective,
        "modes_found": sorted(modes),
        "avg_temperature": avg_temperature,
        "temperature_samples": temperatures,
    }


class Calibrator:
    """Fit trainable mechanism parameters by minimizing synthetic-vs-observed loss.

    The optimizer updates only mechanism fields marked trainable in the
    registry bundle; schedules, selectors, and merge contracts remain fixed in
    the compiled `StaticBundle`. Use this class when you already have a
    compiled `ProgramGraph`/`ExecPlan` and need a deterministic calibration run
    against aligned observed targets or a measurement-aware target bundle.
    """

    def __init__(self, inputs: CalibratorInputs):
        """Initialize the calibrator with compile/runtime contracts and callbacks."""
        self.inputs = inputs
        self._bundle: StaticBundle | None = None

    def _build_bundle(self) -> StaticBundle:
        if self._bundle is not None:
            return self._bundle
        cfg = self.inputs.config
        bundle = compile_program(
            self.inputs.program_graph,
            self.inputs.exec_plan,
            mechanism_registry=self.inputs.mechanism_registry,
            slot_registry=self.inputs.slot_registry,
            merge_registry=self.inputs.merge_registry,
            selector_field_registry=self.inputs.selector_field_registry,
            base_state=self.inputs.base_state,
            parameter_loader=self.inputs.parameter_loader,
            force_fidelity=cfg.fidelity.mode,
            default_temperature=cfg.fidelity.temperature,
            force_override=cfg.fidelity.force_override,
        )
        self._bundle = bundle
        return bundle

    def _target_meta(self) -> tuple[list[CalibrationTarget], list[str], dict[str, str]]:
        targets = list(self.inputs.config.targets)
        metric_paths: list[str] = []
        path_by_target: dict[str, str] = {}
        for target in targets:
            resolved = _resolve_metric_path(target.model_metric_path, self.inputs.slot_registry)
            path_by_target[target.target_id] = resolved
            if resolved not in metric_paths:
                metric_paths.append(resolved)
        return targets, metric_paths, path_by_target

    def _resolve_constraints(self) -> list[ConstraintHandle]:
        cfg = self.inputs.config
        if not cfg.constraint_loss.enabled:
            return []
        registry = self.inputs.constraint_registry
        if registry is None:
            raise ValueError("constraint_loss enabled but constraint_registry is missing")
        constraint_values: dict[str, float] = {}
        if cfg.constraint_values:
            constraint_values.update(cfg.constraint_values)
        if self.inputs.constraint_values:
            constraint_values.update(self.inputs.constraint_values)
        handles: list[ConstraintHandle] = []
        explicit_constraint_ids = cfg.constraint_loss.constraint_ids
        ids = explicit_constraint_ids or registry.constraints.keys()
        for constraint_id in ids:
            spec = registry.constraints.get(constraint_id)
            if spec is None or spec.slot_id is None or spec.operator is None:
                if not explicit_constraint_ids and spec is not None:
                    continue
                raise ValueError(f"Constraint '{constraint_id}' missing slot_id/operator")
            if constraint_id not in constraint_values:
                raise ValueError(f"Constraint '{constraint_id}' missing value for penalty")
            path = _resolve_metric_path(spec.slot_id, self.inputs.slot_registry)
            handles.append(
                ConstraintHandle(
                    constraint_id=constraint_id,
                    operator=spec.operator,
                    path=path,
                    value=float(constraint_values[constraint_id]),
                )
            )
        return handles

    def _resolve_trainable_groups(
        self, bundle: StaticBundle, targets: Sequence[CalibrationTarget]
    ) -> tuple[list[TrainableGroup], list[str]]:
        diagnostics: list[str] = []
        all_handles = bundle.trainables
        if not all_handles:
            return [], diagnostics
        refs: list[TrainableParamRef] = []
        if self.inputs.config.trainables:
            refs.extend(self.inputs.config.trainables)
        for target in targets:
            if target.trainables:
                refs.extend(target.trainables)
        if not refs:
            groups = [
                TrainableGroup(
                    group_id=f"{handle.node_id}.{handle.field_name}",
                    handle_indices=[idx],
                    lower=handle.lower,
                    upper=handle.upper,
                    prior_mean=handle.prior_mean,
                    prior_std=handle.prior_std,
                )
                for idx, handle in enumerate(all_handles)
            ]
            return groups, diagnostics

        assignments: dict[int, str] = {}
        groups_map: dict[str, list[int]] = {}
        group_order: list[str] = []
        for ref in refs:
            matched = [
                idx for idx, handle in enumerate(all_handles) if _match_trainable(handle, ref)
            ]
            if not matched:
                raise ValueError(f"Trainable ref did not match any parameters: {ref.model_dump()}")
            for idx in matched:
                handle = all_handles[idx]
                group_id = ref.tie_id or f"{handle.node_id}.{handle.field_name}"
                if idx in assignments:
                    if assignments[idx] != group_id:
                        raise ValueError(
                            f"Trainable '{handle.node_id}.{handle.field_name}' assigned to multiple groups"
                        )
                    continue
                assignments[idx] = group_id
                if group_id not in groups_map:
                    groups_map[group_id] = []
                    group_order.append(group_id)
                groups_map[group_id].append(idx)

        groups: list[TrainableGroup] = []
        for group_id in group_order:
            indices = groups_map[group_id]
            lowers = [all_handles[i].lower for i in indices if all_handles[i].lower is not None]
            uppers = [all_handles[i].upper for i in indices if all_handles[i].upper is not None]
            lower = max(lowers) if lowers else None
            upper = min(uppers) if uppers else None
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"Tied group '{group_id}' has incompatible bounds")
            means = [
                all_handles[i].prior_mean for i in indices if all_handles[i].prior_mean is not None
            ]
            stds = [
                all_handles[i].prior_std for i in indices if all_handles[i].prior_std is not None
            ]
            prior_mean = None
            prior_std = None
            if means and stds:
                prior_mean = float(sum(means) / len(means))
                prior_std = float(sum(stds) / len(stds))
                if (max(means) - min(means)) > 1e-6 or (max(stds) - min(stds)) > 1e-6:
                    diagnostics.append(f"Prior mismatch within tied group '{group_id}'")
            elif means or stds:
                diagnostics.append(f"Partial prior for tied group '{group_id}' ignored")
            groups.append(
                TrainableGroup(
                    group_id=group_id,
                    handle_indices=indices,
                    lower=lower,
                    upper=upper,
                    prior_mean=prior_mean,
                    prior_std=prior_std,
                )
            )
        return groups, diagnostics

    def run(self) -> CalibrationReport:
        """Run the optimizer loop and return a report-ready calibration artifact.

        Returns:
            `CalibrationReport` with fitted parameter values, per-target loss,
            synthetic-vs-observed comparisons, fit metrics, uncertainty
            diagnostics, and execution context.

        Raises:
            ValueError: If no usable target series are available, if target
                lengths are inconsistent, if constraints reference unknown
                metrics, or if no trainable parameters can be resolved.

        Example:
            ```python
            report = Calibrator(
                CalibratorInputs(
                    config=config,
                    program_graph=program_graph,
                    exec_plan=exec_plan,
                    base_state=state_snapshot,
                    mechanism_registry=mechanism_registry,
                    slot_registry=slot_registry,
                    merge_registry=merge_registry,
                    selector_field_registry=selector_field_registry,
                    parameter_loader=load_params,
                    raw_targets={"tax_revenue": observed_tax_revenue},
                )
            ).run()
            ```
        """
        cfg = self.inputs.config
        diagnostics: list[str] = []
        bundle = self._build_bundle()
        targets, metric_paths, path_by_target = self._target_meta()
        if cfg.fidelity.mode == "discrete":
            diagnostics.append(
                "Calibration running in 'discrete' mode. Gradient-based optimization (Adam) "
                "requires differentiable logic and may fail to converge (zero/undefined gradients)."
            )
        constraint_handles = self._resolve_constraints()
        path_by_constraint = {handle.constraint_id: handle.path for handle in constraint_handles}
        for handle in constraint_handles:
            if handle.path not in metric_paths:
                metric_paths.append(handle.path)

        raw_targets: dict[str, object] = {}
        measurement_bundle = self.inputs.measurement_bundle
        measurement_adapter = (
            self.inputs.measurement_loss_adapter or DefaultMeasurementAwareLossAdapter()
        )
        measurement_config = self.inputs.measurement_loss_config or MeasurementAwareLossConfig()
        measurement_targets = (
            {target.target_id: target for target in measurement_bundle.targets}
            if measurement_bundle is not None
            else {}
        )
        aux_loss_components = tuple(self.inputs.aux_loss_components or ())
        if aux_loss_components:
            diagnostics.append(
                "Auxiliary loss components enabled: "
                + ", ".join(component.component_name for component in aux_loss_components)
            )

        if measurement_bundle is None:
            if self.inputs.raw_targets:
                raw_targets.update(self.inputs.raw_targets)
            if any(t.fabric_query is not None for t in targets):
                if self.inputs.udf_engine is not None or self.inputs.target_fetcher is not None:
                    fetched = fetch_targets(
                        cfg, udf_engine=self.inputs.udf_engine, fetcher=self.inputs.target_fetcher
                    )
                    raw_targets = {**fetched, **raw_targets}
            steps = resolve_steps(cfg, raw_targets)
            if steps == 0:
                raise ValueError("No target series provided for calibration")
            if self.inputs.controls_seq is not None and len(self.inputs.controls_seq) != steps:
                raise ValueError("controls_seq length must match calibration steps")
            aligned_targets, scales, time_axes = prepare_targets(
                cfg, raw_targets=raw_targets, steps=steps, time_axis=cfg.time_axis
            )
            if not aligned_targets:
                raise ValueError("No aligned target series available for calibration")
            missing_targets = [t.target_id for t in targets if t.target_id not in aligned_targets]
            if missing_targets:
                raise ValueError(f"Missing target series for: {', '.join(missing_targets)}")
        else:
            aligned_targets = {
                target_id: jnp.asarray(series, dtype=jnp.float32)
                for target_id, series in measurement_bundle.observed_value.items()
            }
            if not aligned_targets:
                raise ValueError("measurement_bundle does not contain observed targets")
            missing_targets = [t.target_id for t in targets if t.target_id not in aligned_targets]
            if missing_targets:
                raise ValueError(
                    f"Missing measurement target series for: {', '.join(missing_targets)}"
                )
            missing_specs = [t.target_id for t in targets if t.target_id not in measurement_targets]
            if missing_specs:
                raise ValueError(
                    f"Missing measurement target metadata for: {', '.join(missing_specs)}"
                )
            steps = int(next(iter(aligned_targets.values())).shape[0])
            for target_id, arr in aligned_targets.items():
                if int(arr.shape[0]) != steps:
                    raise ValueError(
                        f"Measurement target '{target_id}' length does not match shared step count"
                    )
            if self.inputs.controls_seq is not None and len(self.inputs.controls_seq) != steps:
                raise ValueError("controls_seq length must match calibration steps")
            scales = {
                target.target_id: _compute_scale_local(aligned_targets[target.target_id], target)
                for target in targets
            }
            time_axes = {
                target.target_id: _measurement_time_axis(
                    measurement_bundle.time_axis.get(target.target_id)
                )
                for target in targets
            }

        loss_configs = {t.target_id: t.loss for t in targets}
        target_ids = [t.target_id for t in targets]

        groups, trainable_diagnostics = self._resolve_trainable_groups(bundle, targets)
        diagnostics.extend(trainable_diagnostics)
        if not groups:
            raise ValueError("No trainable parameters available for calibration")
        base_values = extract_trainable_values(bundle)
        group_values = []
        for group in groups:
            values = [jnp.asarray(base_values[idx]) for idx in group.handle_indices]
            stacked = jnp.stack(values)
            group_values.append(jnp.mean(stacked, axis=0))
        group_bijectors = [make_bijector(group.lower, group.upper) for group in groups]
        u = to_unconstrained(group_values, group_bijectors)

        weights = jnp.asarray([loss_configs[tid].weight for tid in target_ids], dtype=jnp.float32)
        if cfg.clip_grad_norm is None:
            opt = optax.adam(cfg.learning_rate)
        else:
            opt = optax.chain(
                optax.clip_by_global_norm(cfg.clip_grad_norm),
                optax.adam(cfg.learning_rate),
            )
        optimizer_name = "adam"
        hpc_enabled = is_hpc_observability_enabled()
        collector = CalibrationMetricsCollector(
            optimizer_name=optimizer_name,
            emit_interval=10,
            enabled=hpc_enabled,
        )
        tracer = get_tracer() if hpc_enabled else None
        span_cm = (
            tracer.start_as_current_span(
                "calibration.run",
                attributes={
                    "calibration.optimizer": optimizer_name,
                    "calibration.max_steps": cfg.max_steps,
                    "calibration.learning_rate": cfg.learning_rate,
                    "calibration.early_stop_patience": cfg.early_stop_patience,
                },
            )
            if tracer is not None
            else nullcontext()
        )

        def _expand_group_values(values: Sequence[jnp.ndarray]) -> list[Any]:
            expanded = list(base_values)
            for group, value in zip(groups, values):
                for idx in group.handle_indices:
                    expanded[idx] = value
            return expanded

        def _root_key(step_idx: jax.Array) -> jax.Array:
            key = jax.random.PRNGKey(cfg.seed)
            if cfg.seed_strategy == "step":
                key = jax.random.fold_in(key, step_idx)
            return key

        def _constraint_violation(value: jnp.ndarray, handle: ConstraintHandle) -> jnp.ndarray:
            threshold = handle.value
            eps = cfg.constraint_loss.epsilon
            if handle.operator == ">=":
                return jnp.maximum(0.0, threshold - value)
            if handle.operator == ">":
                return jnp.maximum(0.0, threshold - value + eps)
            if handle.operator == "<=":
                return jnp.maximum(0.0, value - threshold)
            if handle.operator == "<":
                return jnp.maximum(0.0, value - threshold + eps)
            if handle.operator == "==":
                return value - threshold
            if handle.operator == "!=":
                return jnp.maximum(0.0, eps - jnp.abs(value - threshold))
            raise ValueError(f"Unsupported constraint operator '{handle.operator}'")

        def _constraint_penalty(traces: Mapping[str, jnp.ndarray]) -> jnp.ndarray:
            if not constraint_handles:
                return jnp.array(0.0)
            total = jnp.array(0.0)
            for handle in constraint_handles:
                series = traces[path_by_constraint[handle.constraint_id]]
                if series.ndim > 1:
                    axes = tuple(range(1, series.ndim))
                    series = jnp.mean(series, axis=axes)
                if cfg.constraint_loss.mode == "final":
                    value = series[-1]
                    violation = _constraint_violation(value, handle)
                    penalty = jnp.square(violation)
                else:
                    violation = _constraint_violation(series, handle)
                    penalty = jnp.square(violation)
                    if cfg.constraint_loss.reduction == "max":
                        penalty = jnp.max(penalty)
                    else:
                        penalty = jnp.mean(penalty)
                total = total + penalty
            return cfg.constraint_loss.weight * total

        def _prior_penalty(theta_groups: Sequence[jnp.ndarray]) -> jnp.ndarray:
            if not cfg.prior_loss.enabled:
                return jnp.array(0.0)
            total = jnp.array(0.0)
            for group, value in zip(groups, theta_groups):
                if group.prior_mean is None or group.prior_std is None:
                    continue
                diff = (value - group.prior_mean) / (group.prior_std + cfg.prior_loss.epsilon)
                total = total + jnp.mean(jnp.square(diff))
            return cfg.prior_loss.weight * total

        def _aux_penalty(traces: Mapping[str, jnp.ndarray]) -> jnp.ndarray:
            if not aux_loss_components:
                return jnp.array(0.0)
            total = jnp.array(0.0, dtype=jnp.float32)
            for component in aux_loss_components:
                penalty, _ = component.compute(traces=traces)
                total = total + jnp.asarray(penalty, dtype=jnp.float32)
            return total

        measurement_enabled = measurement_bundle is not None

        def _target_loss_vec(
            u: Sequence[jnp.ndarray],
            step_idx: jax.Array,
            weights_vec: jnp.ndarray | None = None,
        ) -> jnp.ndarray:
            theta_groups = from_unconstrained(u, group_bijectors)
            theta = _expand_group_values(theta_groups)
            sim_bundle = apply_trainable_values(bundle, theta)
            _, traces = run_pure_scan(
                self.inputs.base_state,
                steps=steps,
                root_key=_root_key(step_idx),
                bundle=sim_bundle,
                metric_paths=metric_paths,
                controls_seq=self.inputs.controls_seq,
            )
            return _base_vec_from_traces(traces, weights_vec=weights_vec)

        def _base_vec_from_traces(
            traces: Mapping[str, jnp.ndarray],
            *,
            weights_vec: jnp.ndarray | None = None,
        ) -> jnp.ndarray:
            losses = []
            for idx, target in enumerate(targets):
                trace = traces[path_by_target[target.target_id]]
                predicted = _apply_aggregation(trace, target.aggregation)
                cfg_loss = loss_configs[target.target_id]
                scale = scales.get(target.target_id, 1.0) if cfg_loss.relative else 1.0
                if not measurement_enabled:
                    losses.append(
                        compute_base_loss(
                            predicted, aligned_targets[target.target_id], cfg_loss, scale
                        )
                    )
                    continue

                pointwise = pointwise_base_loss(
                    predicted,
                    aligned_targets[target.target_id],
                    cfg_loss,
                    scale,
                )
                base_weight = (
                    weights_vec[idx]
                    if weights_vec is not None
                    else jnp.array(target.loss.weight, dtype=jnp.float32)
                )
                adapted = measurement_adapter.adapt(
                    targets=(measurement_targets[target.target_id],),
                    base_weights=base_weight,
                    trust_weight=measurement_bundle.trust_weight[target.target_id],
                    coverage_estimate=measurement_bundle.coverage_estimate[target.target_id],
                    censoring_mask=measurement_bundle.censoring_mask.get(target.target_id),
                    lag_days_estimate=measurement_bundle.lag_days_estimate.get(target.target_id),
                    schema_regime_id=measurement_bundle.schema_regime_id.get(target.target_id),
                    shock_mask=measurement_bundle.shock_mask.get(target.target_id),
                    identification_mode=measurement_bundle.identification_mode.get(
                        target.target_id
                    ),
                    config=measurement_config,
                )
                losses.append(
                    reduce_weighted_loss(
                        pointwise,
                        adapted["effective_weight"],
                        epsilon=cfg_loss.epsilon,
                    )
                )
            if not losses:
                return jnp.zeros((0,), dtype=jnp.float32)
            return jnp.stack(losses)

        def _tree_is_finite(tree: Any) -> jnp.ndarray:
            leaves = jax.tree_util.tree_leaves(tree)
            finite = jnp.array(True)
            for leaf in leaves:
                finite = finite & jnp.all(jnp.isfinite(leaf))
            return finite

        def loss_fn(u: Sequence[jnp.ndarray], weights_vec: jnp.ndarray, step_idx: jax.Array):
            theta_groups = from_unconstrained(u, group_bijectors)
            theta = _expand_group_values(theta_groups)
            sim_bundle = apply_trainable_values(bundle, theta)
            _, traces = run_pure_scan(
                self.inputs.base_state,
                steps=steps,
                root_key=_root_key(step_idx),
                bundle=sim_bundle,
                metric_paths=metric_paths,
                controls_seq=self.inputs.controls_seq,
            )
            base_vec = _base_vec_from_traces(
                traces,
                weights_vec=weights_vec if measurement_enabled else None,
            )
            if measurement_enabled:
                total = jnp.sum(base_vec) if base_vec.size else jnp.array(0.0)
            else:
                total = jnp.sum(base_vec * weights_vec) if base_vec.size else jnp.array(0.0)
            constraint_penalty = _constraint_penalty(traces)
            prior_penalty = _prior_penalty(theta_groups)
            aux_penalty = _aux_penalty(traces)
            total = total + constraint_penalty + prior_penalty + aux_penalty
            aux = (base_vec, constraint_penalty, prior_penalty, aux_penalty)
            return total, aux

        @jax.jit
        def step_fn(
            u_state: Sequence[jnp.ndarray],
            weights_state: jnp.ndarray,
            opt_state_state: optax.OptState,
            step_idx: jax.Array,
        ):
            (loss_val, aux), grads = jax.value_and_grad(loss_fn, has_aux=True)(
                u_state, weights_state, step_idx
            )
            updates, new_opt_state = opt.update(grads, opt_state_state, u_state)
            new_u = optax.apply_updates(u_state, updates)
            grad_norm = optax.global_norm(grads)
            grads_finite = _tree_is_finite(grads)
            return new_u, weights_state, new_opt_state, loss_val, aux, grad_norm, grads_finite

        def _grad_norms_from_jac(jac_tree: Any, eps: float) -> jnp.ndarray:
            leaves = jax.tree_util.tree_leaves(jac_tree)
            if not leaves:
                return jnp.zeros((0,), dtype=jnp.float32)
            n_targets = leaves[0].shape[0]
            norms_sq = jnp.zeros((n_targets,), dtype=jnp.float32)
            for leaf in leaves:
                leaf_sq = jnp.sum(jnp.square(leaf), axis=tuple(range(1, leaf.ndim)))
                norms_sq = norms_sq + leaf_sq
            return jnp.sqrt(norms_sq + eps)

        @jax.jit
        def gradnorm_update(
            u_state: Sequence[jnp.ndarray],
            weights_state: jnp.ndarray,
            base_vec: jnp.ndarray,
            init_vec: jnp.ndarray,
            step_idx: jax.Array,
        ):
            def weighted_losses(params):
                losses = _target_loss_vec(
                    params,
                    step_idx,
                    weights_state if measurement_enabled else None,
                )
                if measurement_enabled:
                    return losses
                return losses * weights_state

            jac = jax.jacrev(weighted_losses)(u_state)
            norms = _grad_norms_from_jac(jac, cfg.grad_norm.epsilon)
            g_avg = jnp.mean(norms) if norms.size else jnp.array(0.0)
            rel = jnp.power(base_vec / (init_vec + cfg.grad_norm.epsilon), cfg.grad_norm.alpha)
            target = g_avg * rel
            scale = jnp.power(target / (norms + cfg.grad_norm.epsilon), cfg.grad_norm.lr)
            new_weights = jnp.clip(
                weights_state * scale,
                cfg.grad_norm.min_weight,
                cfg.grad_norm.max_weight,
            )
            return new_weights, norms

        def _param_names_for_groups(theta_groups: Sequence[jnp.ndarray]) -> list[str]:
            flat_theta, _ = ravel_pytree(theta_groups)
            n_params = int(flat_theta.size)
            if n_params == 0:
                return []
            param_names: list[str] = []
            for group, value in zip(groups, theta_groups):
                arr = np.asarray(value)
                if arr.size == 1:
                    param_names.append(group.group_id)
                else:
                    param_names.extend(f"{group.group_id}[{idx}]" for idx in range(int(arr.size)))
            if len(param_names) != n_params:
                return [f"param_{idx}" for idx in range(n_params)]
            return param_names

        def _compute_run_hessian_summary(
            theta_groups: Sequence[jnp.ndarray],
            weights_vec: jnp.ndarray,
        ) -> tuple[HessianResult | None, Any | None, list[str]]:
            if not cfg.hessian.enabled:
                return None, None, []
            flat_theta, unravel_theta = ravel_pytree(theta_groups)
            n_params = int(flat_theta.size)
            if n_params == 0:
                return None, None, ["Hessian skipped: no parameters"]
            if cfg.hessian.max_params is not None and n_params > cfg.hessian.max_params:
                return (
                    None,
                    None,
                    [
                        f"Hessian skipped: parameter count {n_params} exceeds {cfg.hessian.max_params}"
                    ],
                )

            param_names = _param_names_for_groups(theta_groups)

            def _loss_from_flat(flat_params: jnp.ndarray) -> jnp.ndarray:
                theta_groups_local = unravel_theta(flat_params)
                theta = _expand_group_values(theta_groups_local)
                sim_bundle = apply_trainable_values(bundle, theta)
                _, traces_local = run_pure_scan(
                    self.inputs.base_state,
                    steps=steps,
                    root_key=_root_key(jnp.array(0, dtype=jnp.int32)),
                    bundle=sim_bundle,
                    metric_paths=metric_paths,
                    controls_seq=self.inputs.controls_seq,
                )
                base_vec = _base_vec_from_traces(
                    traces_local,
                    weights_vec=weights_vec if measurement_enabled else None,
                )
                total = (
                    (jnp.sum(base_vec) if measurement_enabled else jnp.sum(base_vec * weights_vec))
                    if base_vec.size
                    else jnp.array(0.0)
                )
                total = (
                    total
                    + _constraint_penalty(traces_local)
                    + _prior_penalty(theta_groups_local)
                    + _aux_penalty(traces_local)
                )
                return total

            local_diagnostics: list[str] = []
            try:
                hessian_result = compute_hessian(
                    _loss_from_flat,
                    jnp.asarray(flat_theta),
                    param_names,
                    damping=cfg.hessian.damping,
                    jitter_floor=cfg.hessian.rank_tol,
                )
            except (FloatingPointError, RuntimeError, TypeError, ValueError) as exc:
                return None, None, [f"Hessian computation failed: {exc}"]

            identifiability_report = None
            try:
                identifiability_report = diagnose_identifiability(hessian_result)
            except (
                FloatingPointError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:  # pragma: no cover - defensive
                local_diagnostics.append(f"Identifiability diagnostics failed: {exc}")
            return hessian_result, identifiability_report, local_diagnostics

        # ------------------------------------------------------------------
        # Multi-start: build list of (u_init, seed_offset) pairs
        # ------------------------------------------------------------------
        start_points: list[tuple[list[jnp.ndarray], int]] = [(u, 0)]
        if cfg.multi_start is not None:
            ms = cfg.multi_start
            key = jax.random.PRNGKey(cfg.seed)
            for i in range(1, ms.n_starts):
                k = jax.random.fold_in(key, i)
                u_perturbed = [
                    v
                    + jax.random.normal(jax.random.fold_in(k, j), shape=v.shape)
                    * ms.perturbation_scale
                    for j, v in enumerate(u)
                ]
                start_points.append((u_perturbed, i))

        multi_start_runs: list[dict[str, Any]] = []

        for u_init, _start_idx in start_points:
            _ms_diagnostics: list[str] = []
            opt_state = opt.init(u_init)
            loss_history: list[float] = []
            grad_norm_history: list[float] = []
            u_state = u_init
            weights_state = weights
            best_loss = float("inf")
            best_eval_loss = float("inf")
            best_u_state = u_state
            best_weights_state = weights_state
            patience = 0
            init_base_vec = None
            early_stop_triggered = False
            grad_failure = False

            with span_cm as span:
                for step in range(cfg.max_steps):
                    step_idx = jnp.array(step, dtype=jnp.int32)
                    step_start = time.perf_counter() if hpc_enabled else None
                    prev_u_state = u_state
                    prev_weights_state = weights_state
                    (
                        u_state,
                        weights_state,
                        opt_state,
                        loss_val,
                        aux,
                        grad_norm,
                        grads_finite,
                    ) = step_fn(u_state, weights_state, opt_state, step_idx)
                    if hpc_enabled:
                        jax.block_until_ready(loss_val)
                        duration = time.perf_counter() - (step_start or 0.0)

                    loss_float = float(loss_val)
                    grad_norm_float = float(grad_norm)
                    loss_history.append(loss_float)
                    grad_norm_history.append(grad_norm_float)
                    if loss_float < best_eval_loss:
                        best_eval_loss = loss_float
                        best_u_state = prev_u_state
                        best_weights_state = prev_weights_state

                    if hpc_enabled:
                        collector.record_step(
                            step=step,
                            duration_seconds=duration,
                            loss=loss_float,
                            grad_norm=grad_norm_float,
                            is_warmup=step == 0,
                        )

                    if not bool(grads_finite):
                        _ms_diagnostics.append(f"Non-finite gradients at step {step}")
                        grad_failure = True
                        break
                    base_vec = aux[0]
                    if cfg.grad_norm.enabled and step % cfg.grad_norm.update_every == 0:
                        if init_base_vec is None:
                            init_base_vec = base_vec
                        weights_state, _ = gradnorm_update(
                            u_state, weights_state, base_vec, init_base_vec, step_idx
                        )
                    if step >= cfg.early_stop_min_steps and cfg.early_stop_patience > 0:
                        if loss_float + cfg.early_stop_min_delta < best_loss:
                            best_loss = loss_float
                            patience = 0
                        else:
                            patience += 1
                        if patience >= cfg.early_stop_patience:
                            _ms_diagnostics.append(f"Early stopping at step {step}")
                            early_stop_triggered = True
                            break

                convergence_reason = "max_steps"
                if grad_failure:
                    convergence_reason = "grad_vanish"
                elif early_stop_triggered:
                    convergence_reason = "early_stop"

                if hpc_enabled:
                    total_steps = len(loss_history)
                    collector.finalize(convergence_reason, total_steps)
                    if span is not None:
                        span.set_attribute("calibration.convergence_reason", convergence_reason)
                        span.set_attribute("calibration.total_steps", total_steps)

            run_u_state = best_u_state if np.isfinite(best_eval_loss) else u_state
            run_weights_state = best_weights_state if np.isfinite(best_eval_loss) else weights_state
            final_loss = (
                best_eval_loss
                if np.isfinite(best_eval_loss)
                else (float(loss_history[-1]) if loss_history else float("inf"))
            )
            run_hessian_result = None
            run_identifiability = None
            if len(start_points) > 1 and cfg.hessian.enabled:
                theta_groups_run = from_unconstrained(run_u_state, group_bijectors)
                run_hessian_result, run_identifiability, hessian_diags = (
                    _compute_run_hessian_summary(
                        theta_groups_run,
                        run_weights_state,
                    )
                )
                _ms_diagnostics.extend(hessian_diags)
            multi_start_runs.append(
                {
                    "u_state": run_u_state,
                    "weights_state": run_weights_state,
                    "loss_history": loss_history,
                    "grad_norm_history": grad_norm_history,
                    "final_loss": final_loss,
                    "diagnostics": _ms_diagnostics,
                    "hessian_result": run_hessian_result,
                    "identifiability": run_identifiability,
                }
            )

        # ------------------------------------------------------------------
        # Multi-start: select best run
        # ------------------------------------------------------------------
        if len(multi_start_runs) > 1:
            from polisyos.foundry.calibration.multi_start import (
                SingleRunResult as _SR,
            )
            from polisyos.foundry.calibration.multi_start import (
                select_best as _select_best,
            )

            _single_results = [
                _SR(
                    loss=r["final_loss"],
                    params=r["u_state"],
                    hessian_result=r["hessian_result"],
                    identifiability=r["identifiability"],
                    loss_history=r["loss_history"],
                    grad_norm_history=r["grad_norm_history"],
                    diagnostics=r["diagnostics"],
                )
                for r in multi_start_runs
            ]
            best_idx, selection_reason = _select_best(_single_results, cfg.multi_start)
            diagnostics.append(
                f"Multi-start: selected run {best_idx}/{len(multi_start_runs)} ({selection_reason})"
            )
            selected_run = multi_start_runs[best_idx]
            u_state = selected_run["u_state"]
            weights_state = selected_run["weights_state"]
            loss_history = selected_run["loss_history"]
            grad_norm_history = selected_run["grad_norm_history"]
            diagnostics.extend(selected_run["diagnostics"])
        else:
            selected_run = multi_start_runs[0]
            u_state = selected_run["u_state"]
            weights_state = selected_run["weights_state"]
            loss_history = selected_run["loss_history"]
            grad_norm_history = selected_run["grad_norm_history"]
            diagnostics.extend(selected_run["diagnostics"])

        final_theta_groups = from_unconstrained(u_state, group_bijectors)
        final_theta = _expand_group_values(final_theta_groups)
        final_bundle = apply_trainable_values(bundle, final_theta)
        calibrated_params: dict[str, float] = {}
        for handle, value in zip(final_bundle.trainables, final_theta):
            node_id = final_bundle.nodes[handle.node_index].node_id
            calibrated_params[f"{node_id}.{handle.field_name}"] = float(value)

        final_target_losses = _target_loss_vec(
            u_state,
            jnp.array(0, dtype=jnp.int32),
            weights_state if measurement_enabled else None,
        )
        if measurement_enabled:
            per_target_final = {
                tid: float(final_target_losses[idx]) for idx, tid in enumerate(target_ids)
            }
        else:
            per_target_final = {
                tid: float(final_target_losses[idx] * weights_state[idx])
                for idx, tid in enumerate(target_ids)
            }
        target_weights = {tid: float(weights_state[idx]) for idx, tid in enumerate(target_ids)}
        final_total_loss, _ = loss_fn(u_state, weights_state, jnp.array(0, dtype=jnp.int32))
        final_total_loss = float(final_total_loss)

        _, traces = run_pure_scan(
            self.inputs.base_state,
            steps=steps,
            root_key=_root_key(jnp.array(0, dtype=jnp.int32)),
            bundle=final_bundle,
            metric_paths=metric_paths,
            controls_seq=self.inputs.controls_seq,
        )
        series_comparison: dict[str, CalibrationSeriesComparison] = {}
        per_target_metrics: dict[str, CalibrationFitMetrics] = {}
        all_real: list[np.ndarray] = []
        all_model: list[np.ndarray] = []

        def _fit_metrics(model_series: Any, real_series: Any) -> CalibrationFitMetrics:
            model_arr = np.asarray(model_series, dtype=float).reshape(-1)
            real_arr = np.asarray(real_series, dtype=float).reshape(-1)
            if model_arr.size == 0 or real_arr.size == 0:
                return CalibrationFitMetrics(mse=0.0, rmse=0.0, mae=0.0, r2=None, n=0)
            diff = model_arr - real_arr
            mse = float(np.mean(diff**2))
            mae = float(np.mean(np.abs(diff)))
            rmse = float(np.sqrt(mse))
            denom = float(np.sum((real_arr - real_arr.mean()) ** 2))
            r2 = None if denom <= 0.0 else float(1.0 - float(np.sum(diff**2)) / denom)
            return CalibrationFitMetrics(mse=mse, rmse=rmse, mae=mae, r2=r2, n=int(real_arr.size))

        for tgt in targets:
            target_id = tgt.target_id
            model_series = _apply_aggregation(traces[path_by_target[target_id]], tgt.aggregation)
            real_list = _as_float_list(aligned_targets[target_id])
            model_list = _as_float_list(model_series)
            series_comparison[target_id] = CalibrationSeriesComparison(
                time=time_axes.get(target_id),
                real=real_list,
                model=model_list,
            )
            per_target_metrics[target_id] = _fit_metrics(model_list, real_list)
            if real_list:
                all_real.append(np.asarray(real_list, dtype=float))
                all_model.append(np.asarray(model_list, dtype=float))

        aggregate_metrics = None
        if all_real:
            aggregate_metrics = _fit_metrics(np.concatenate(all_model), np.concatenate(all_real))
        fit_quality = CalibrationFitQuality(
            per_target=per_target_metrics,
            aggregate=aggregate_metrics,
        )

        uncertainties: CalibrationUncertainty | None = None
        hessian_result: HessianResult | None = None
        if cfg.hessian.enabled:
            flat_theta, unravel_theta = ravel_pytree(final_theta_groups)
            n_params = int(flat_theta.size)
            if n_params == 0:
                diagnostics.append("Hessian skipped: no parameters")
            elif cfg.hessian.max_params is not None and n_params > cfg.hessian.max_params:
                diagnostics.append(
                    f"Hessian skipped: parameter count {n_params} exceeds {cfg.hessian.max_params}"
                )
            else:
                param_names: list[str] = []
                for group, value in zip(groups, final_theta_groups):
                    arr = np.asarray(value)
                    if arr.size == 1:
                        param_names.append(group.group_id)
                    else:
                        param_names.extend(
                            f"{group.group_id}[{idx}]" for idx in range(int(arr.size))
                        )
                if len(param_names) != n_params:
                    diagnostics.append("Hessian param naming mismatch; using generic names")
                    param_names = [f"param_{idx}" for idx in range(n_params)]

                def _loss_from_flat(flat_params: jnp.ndarray) -> jnp.ndarray:
                    theta_groups = unravel_theta(flat_params)
                    theta = _expand_group_values(theta_groups)
                    sim_bundle = apply_trainable_values(bundle, theta)
                    _, traces_local = run_pure_scan(
                        self.inputs.base_state,
                        steps=steps,
                        root_key=_root_key(jnp.array(0, dtype=jnp.int32)),
                        bundle=sim_bundle,
                        metric_paths=metric_paths,
                        controls_seq=self.inputs.controls_seq,
                    )
                    base_vec = _base_vec_from_traces(
                        traces_local,
                        weights_vec=weights_state if measurement_enabled else None,
                    )
                    total = (
                        (
                            jnp.sum(base_vec)
                            if measurement_enabled
                            else jnp.sum(base_vec * weights_state)
                        )
                        if base_vec.size
                        else jnp.array(0.0)
                    )
                    total = (
                        total
                        + _constraint_penalty(traces_local)
                        + _prior_penalty(theta_groups)
                        + _aux_penalty(traces_local)
                    )
                    return total

                try:
                    hessian_result = compute_hessian(
                        _loss_from_flat,
                        jnp.asarray(flat_theta),
                        param_names,
                        damping=cfg.hessian.damping,
                        jitter_floor=cfg.hessian.rank_tol,
                    )
                    hr = hessian_result
                    n_p = len(hr.param_names)

                    # Build correlation from covariance
                    cov_jnp = jnp.asarray(hr.covariance)
                    std_jnp = jnp.asarray(hr.std)
                    denom = (std_jnp[:, None] * std_jnp[None, :]) + cfg.hessian.rank_tol
                    corr = cov_jnp / denom
                    if n_p > 0:
                        corr = corr.at[jnp.diag_indices(n_p)].set(1.0)

                    # Rank via SVD on repaired hessian
                    sv = jnp.linalg.svd(jnp.asarray(hr.hessian), compute_uv=False)
                    rank = int(jnp.sum(sv > cfg.hessian.rank_tol))

                    non_identifiable: list[str] = []
                    for idx, value in enumerate(hr.std):
                        if not np.isfinite(value) or value > cfg.hessian.std_warn:
                            non_identifiable.append(hr.param_names[idx])

                    condition = hr.condition_number
                    if rank < n_p:
                        diagnostics.append(f"Hessian rank deficient: {rank}/{n_p}")
                    if np.isfinite(condition) and condition > cfg.hessian.condition_warn:
                        diagnostics.append(f"Hessian ill-conditioned: {condition:.3g}")
                    if non_identifiable:
                        diagnostics.append(
                            "Non-identifiable params: " + ", ".join(non_identifiable)
                        )

                    uncertainties = CalibrationUncertainty(
                        params=list(hr.param_names),
                        covariance=_as_float_matrix(cov_jnp),
                        correlation=_as_float_matrix(corr),
                        std=_as_float_list(std_jnp),
                        damping=float(cfg.hessian.damping),
                        hessian_rank=rank,
                        hessian_condition=None if not np.isfinite(condition) else float(condition),
                        non_identifiable=non_identifiable,
                    )
                except (
                    FloatingPointError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as exc:  # pragma: no cover - defensive
                    diagnostics.append(f"Hessian computation failed: {exc}")

        identifiability_report = None
        if hessian_result is not None:
            try:
                identifiability_report = diagnose_identifiability(hessian_result)
            except (
                FloatingPointError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:  # pragma: no cover - defensive
                diagnostics.append(f"Identifiability diagnostics failed: {exc}")

        fidelity_stats = _inspect_bundle_fidelity(bundle)
        report = CalibrationReport(
            calibrated_params=calibrated_params,
            total_loss=final_total_loss,
            per_target_loss=per_target_final,
            target_weights=target_weights,
            loss_history=loss_history,
            grad_norm_history=grad_norm_history,
            series_comparison=series_comparison,
            fit_quality=fit_quality,
            uncertainties=uncertainties,
            identifiability=identifiability_report,
            diagnostics=diagnostics,
            execution_context={
                "requested_mode": cfg.fidelity.mode,
                "effective_fidelity": fidelity_stats["effective_fidelity"],
                "temperature": cfg.fidelity.temperature,
                "forced_override": cfg.fidelity.force_override,
                "jax_platform": _jax_platform(),
                "timestamp": datetime.now(UTC).isoformat(),
                "fidelity_stats": fidelity_stats,
            },
        )
        if report.uncertainties is not None:
            envelopes = envelopes_from_calibration(report, confidence_level=0.95)
            if envelopes:
                report = report.model_copy(update={"uncertainty_envelopes": envelopes})
        return report


def _jax_platform() -> str:
    """
    JAX 0.8+ удалил `jax.lib.xla_bridge.get_backend()`.
    Возвращаем строковый идентификатор платформы максимально совместимым способом.
    """
    try:
        # JAX >= 0.8
        import jax.extend as jax_extend  # type: ignore[import-not-found]

        return str(jax_extend.backend.get_backend().platform)
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        try:
            # Старый/универсальный API
            return str(jax.default_backend())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return "unknown"
