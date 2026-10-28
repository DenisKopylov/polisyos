"""Optimize Foundry mechanism parameters against observed targets and diagnostics.

`Calibrator` owns the synthetic-vs-observed boundary for calibration: it
generates synthetic traces with `run_pure_scan()`, compares them to either raw
target series or a `CalibrationTargetBundle`, applies measurement-aware and
auxiliary penalties, and returns a persisted-report-ready `CalibrationReport`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field, replace
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Literal

import jax
import jax.numpy as jnp
import numpy as np
import optax
from jax.flatten_util import ravel_pytree

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    RegistryBundlePayload,
    input_ref_from_artifact_ref,
    resolve_manifest_by_profile,
)
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph
from polisyos.core.observability import (
    get_metrics,
    get_tracer,
    is_hpc_observability_enabled,
)
from polisyos.core.registry import load_registry_bundle_content, load_registry_bundle_payload
from polisyos.foundry.calibration.auxiliary import AuxLossComponent
from polisyos.foundry.calibration.bijectors import (
    from_unconstrained,
    make_bijector,
    to_unconstrained,
)
from polisyos.foundry.calibration.execution_basis import (
    CALIBRATION_RUNTIME_INPUT_CONTRACT,
    CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2,
    CALIBRATION_RUNTIME_INPUT_NAMES_V1_2,
    RUNTIME_REGISTRY_MEMBER_CONTRACT,
    CalibrationExecutionInputBasis,
    CalibrationOrderedBatchInput,
    CalibrationOrderedBatchRow,
    CalibrationParameterUnitIdentity,
    CalibrationResolvedParameterInput,
    CalibrationRuntimeInputBinding,
    CalibrationTargetInputIdentity,
    _ordered_numeric_settings,
    calibration_report_series_sha256,
    calibration_report_time_axis_sha256,
    canonical_input_sha256,
    classify_calibration_source_error,
    put_calibration_execution_input_basis,
    put_calibration_ordered_batch_input,
    read_calibration_model_source,
    read_calibration_registry_source,
    resolve_calibration_ordered_batch_input,
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
from polisyos.foundry.calibration.preflight import (
    fetch_targets,
    prepare_targets,
    resolve_steps,
)
from polisyos.foundry.calibration.pure_executor import (
    StaticBundle,
    apply_nodes_batch,
    apply_trainable_values,
    compile_program,
    extract_trainable_values,
    run_pure_scan,
)
from polisyos.foundry.calibration.report import (
    CalibrationCoordinateProjection,
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationOrderedBatchReport,
    CalibrationReport,
    CalibrationSeriesComparison,
    CalibrationUncertainty,
    ordered_batch_fit_metrics,
    put_calibration_config,
    put_calibration_report,
)
from polisyos.foundry.calibration.uncertainty_adapter import envelopes_from_calibration
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.numeric import is_jax_tracer
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    TargetAlignConfig,
    TargetLossConfig,
    TrainableParamRef,
)
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    UnitsRegistry,
)

_calibration_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderedBatchCalibrationProfile:
    """First supported ordered-row calibration objective.

    Rows are positional identities.  ``states``, ``row_times``, ``row_keys``,
    ``targets`` and ``weights`` must have the same leading dimension.  Each
    row executes exactly one scalar-equivalent executor step; no row is a scan
    start and no time/entity axes are flattened.  The objective is the
    weighted mean squared residual over rows.  Complete caller keys are used
    unchanged, rather than being re-derived or broadcast.
    """

    row_ids: tuple[str, ...]
    states: GlobalState
    row_times: jax.Array
    row_keys: jax.Array
    target_path: str
    targets: jax.Array
    weights: jax.Array

    def __post_init__(self) -> None:
        # Static typed-carrier preflight precedes any outer JIT argument conversion.
        # JAX may reconstruct abstract nodes; the executable entry repeats strict
        # carrier checks before any numerical conversion/execution.
        _validate_ordered_source_dtypes(self, strict_carriers=False)


def _validate_ordered_source_dtypes(
    profile: OrderedBatchCalibrationProfile,
    *,
    strict_carriers: bool,
) -> None:
    values = (profile.states, profile.row_times, profile.row_keys, profile.targets, profile.weights)
    for value in jax.tree_util.tree_leaves(values):
        if (
            strict_carriers
            and not isinstance(value, (jax.Array, np.ndarray, np.generic))
            and not is_jax_tracer(value)
        ):
            raise ValueError("ordered profile requires typed JAX/NumPy array carriers")
        dtype = getattr(value, "dtype", None)
        if dtype is None:
            continue  # abstract tree reconstruction; never executable admission
        try:
            original = np.dtype(dtype)
            effective = np.dtype(jax.dtypes.canonicalize_dtype(original))
        except (TypeError, ValueError) as exc:
            raise ValueError("ordered profile source dtype is unsupported") from exc
        if original != effective:
            raise ValueError(
                "ordered profile source dtype is unavailable in the active JAX precision profile"
            )


def _ordered_input_array(value: Any) -> jax.Array:
    try:
        array = jnp.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("ordered profile array representation is unsupported") from exc
    if np.dtype(array.dtype) != np.dtype(value.dtype):
        raise ValueError("ordered profile array conversion changed source dtype")
    return array


@dataclass(frozen=True)
class OrderedBatchCalibrationEvaluation:
    """Parameter-connected result of an ordered batch objective evaluation."""

    objective: jax.Array
    predictions: jax.Array
    final_states: GlobalState
    final_row_keys: jax.Array
    valid: jax.Array


def _ordered_batch_parameter_dtype(
    profile: OrderedBatchCalibrationProfile,
    bundle: StaticBundle,
) -> np.dtype:
    """Keep trainables in the declared mutable state precision during fitting."""
    value: Any = profile.states
    for part in profile.target_path.split("."):
        value = getattr(value, part)
    dtype = np.dtype(value.dtype)
    if dtype not in (np.dtype("float32"), np.dtype("float64")):
        raise ValueError("ordered batch fitting requires a float32 or float64 scalar metric")
    for node in bundle.nodes:
        for output in node.outputs:
            spec = bundle.slot_registry.slots.get(output)
            if spec is None or not spec.state_path:
                raise ValueError("ordered batch output requires its declared state slot")
            current: Any = profile.states
            for part in spec.state_path.split("."):
                current = getattr(current, part)
            if np.dtype(current.dtype).kind == "f" and np.dtype(current.dtype) != dtype:
                raise ValueError("ordered batch mutable floating slots require one compute dtype")
    return dtype


def _ordered_batch_loss(
    predictions: jax.Array,
    profile: OrderedBatchCalibrationProfile,
    loss_config: TargetLossConfig,
) -> tuple[jax.Array, jax.Array]:
    """Apply the existing pointwise loss and a finite positive row reduction."""
    targets = jnp.asarray(profile.targets)
    # The first profile has one explicit floating reduction law. Integer
    # accumulator wrap and backend-default precision cannot change its support.
    original_weights = jnp.asarray(profile.weights)
    weights = original_weights.astype(jnp.float32)
    pointwise = pointwise_base_loss(predictions, targets, loss_config, 1.0)
    support = jnp.sum(weights)
    inputs_valid = (
        jnp.all(jnp.isfinite(targets))
        & jnp.all(jnp.isfinite(original_weights))
        & jnp.all(original_weights >= 0)
        & jnp.all(jnp.isfinite(weights))
        & jnp.all(weights >= 0)
        & jnp.all((original_weights == 0) | (weights > 0))
        & jnp.isfinite(support)
        & (support > 0)
        & jnp.all(jnp.isfinite(predictions))
    )
    safe_support = jnp.where(inputs_valid, support, jnp.ones_like(support))
    candidate = jnp.sum(weights * pointwise) / safe_support
    valid = inputs_valid & jnp.isfinite(candidate)
    return jnp.where(valid, candidate, jnp.inf), valid


def evaluate_ordered_batch_objective(
    profile: OrderedBatchCalibrationProfile,
    *,
    bundle: StaticBundle,
    loss_config: TargetLossConfig | None = None,
) -> OrderedBatchCalibrationEvaluation:
    """Evaluate ordered scalar rows with an explicit transformed validity result.

    Dynamic invalid targets, weights, support, predictions or reductions return
    ``objective=inf`` and ``valid=False``. Shape, key dtype and unsupported
    configured loss contracts refuse before execution. A finite curvature is
    a numerical diagnostic and supplies no inferential covariance or noise law.
    """
    _validate_ordered_source_dtypes(profile, strict_carriers=True)
    numeric_settings = _ordered_numeric_settings()
    if (
        numeric_settings["jax_default_prng_impl"] != "threefry2x32"
        or numeric_settings["jax_enable_custom_prng"]
        or numeric_settings["jax_legacy_prng_key"] != "allow"
    ):
        raise ValueError("ordered profile requires allowed legacy threefry2x32 uint32 keys")
    rows = len(profile.row_ids)
    if rows == 0 or any(not row.strip() for row in profile.row_ids):
        raise ValueError("batch row_ids must be non-empty strings")
    if len(set(profile.row_ids)) != rows:
        raise ValueError("batch row_ids must be unique")
    config = loss_config or TargetLossConfig(relative=False)
    if config.kind != "mse" or config.relative:
        raise ValueError("ordered batch helper supports absolute MSE only")
    if not np.isfinite(config.epsilon) or config.epsilon < 0:
        raise ValueError("ordered batch loss epsilon must be finite and nonnegative")
    times = _ordered_input_array(profile.row_times)
    keys = _ordered_input_array(profile.row_keys)
    targets = _ordered_input_array(profile.targets)
    weights = _ordered_input_array(profile.weights)
    if times.shape != (rows,) or not jnp.issubdtype(times.dtype, jnp.integer):
        raise ValueError(f"batch row_times must be an integer vector of shape ({rows},)")
    if keys.shape != (rows, 2) or keys.dtype != jnp.uint32:
        raise ValueError(f"batch row_keys must have uint32 shape ({rows}, 2)")
    if targets.shape != (rows,) or weights.shape != (rows,):
        raise ValueError(f"batch targets and weights must have shape ({rows},)")
    if targets.dtype not in (jnp.float32, jnp.float64) or weights.dtype not in (
        jnp.float32,
        jnp.float64,
    ):
        raise ValueError("batch targets and weights require float32 or float64")
    if any(leaf.dtype.kind not in "biuf" for leaf in jax.tree_util.tree_leaves(profile.states)):
        raise ValueError("ordered batch state leaves must use real numeric or boolean dtypes")
    final_states, final_keys = apply_nodes_batch(profile.states, times, keys, bundle=bundle)
    value: Any = final_states
    for part in profile.target_path.split("."):
        value = getattr(value, part)
    predictions = jnp.asarray(value)
    if predictions.shape != (rows,) or predictions.dtype.kind not in "iuf":
        raise ValueError("batch target_path must resolve to exactly one scalar per row")
    objective, valid = _ordered_batch_loss(predictions, profile, config)
    valid = valid & jnp.all(times >= 0)
    for leaf in (
        *jax.tree_util.tree_leaves(profile.states),
        *jax.tree_util.tree_leaves(final_states),
    ):
        valid = valid & jnp.all(jnp.isfinite(leaf))
    objective = jnp.where(valid, objective, jnp.inf)
    return OrderedBatchCalibrationEvaluation(
        objective, predictions, final_states, final_keys, valid
    )


jax.tree_util.register_dataclass(
    OrderedBatchCalibrationProfile,
    data_fields=("states", "row_times", "row_keys", "targets", "weights"),
    meta_fields=("row_ids", "target_path"),
)
jax.tree_util.register_dataclass(
    OrderedBatchCalibrationEvaluation,
    data_fields=("objective", "predictions", "final_states", "final_row_keys", "valid"),
    meta_fields=(),
)


@dataclass
class CalibratorInputs:
    """Bundle the runtime contracts and callbacks required by `Calibrator.run()`.

    Attributes:
        config: Optimization, target, and loss configuration.
        program_graph: Compiled graph whose nodes will be replayed in-memory.
        exec_plan: Execution order and runtime flags for the graph.
        exec_plan_ref: Optional selected CAS reference for that exact plan.
        registry_bundle_ref: Optional selected bundle that supplied registry objects.
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
    exec_plan_ref: ArtifactRef | None = None
    registry_bundle_ref: ArtifactRef | None = None
    mechanism_registry_ref: ArtifactRef | None = None
    units_registry: UnitsRegistry | None = None
    units_registry_ref: ArtifactRef | None = None
    base_state_snapshot_ref: ArtifactRef | None = None
    ordered_batch_profile: OrderedBatchCalibrationProfile | None = None


def _snapshot_calibrator_inputs(inputs: CalibratorInputs) -> CalibratorInputs:
    """Copy value inputs before a fit while retaining opaque executable providers.

    Provider behavior is not made authoritative by this snapshot. Parameter and
    target outputs are captured by the run; custom engines, adapters, and loss
    callbacks remain explicitly limited at the execution-basis boundary.
    """
    opaque_fields = {
        "parameter_loader",
        "udf_engine",
        "target_fetcher",
        "measurement_loss_adapter",
    }
    snapshot: dict[str, Any] = {}
    for item in dataclass_fields(inputs):
        value = getattr(inputs, item.name)
        if item.name in opaque_fields:
            snapshot[item.name] = value
            continue
        if item.name == "aux_loss_components" and value is not None:
            snapshot[item.name] = tuple(value)
            continue
        try:
            snapshot[item.name] = deepcopy(value)
        except Exception as exc:
            raise ValueError(f"calibrator_input_snapshot_failed:{item.name}") from exc
    return CalibratorInputs(**snapshot)


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


@dataclass(frozen=True)
class _HessianReuseKey:
    """Identity of the objective at which a Hessian diagnostic was computed.

    A Hessian is local evidence.  The point, coordinate naming, objective
    weights, stochastic replica, and numerical policy therefore all belong to
    its identity; matching only the parameter count would silently attach a
    diagnostic to a different objective.
    """

    flat_theta: tuple[float, ...]
    param_names: tuple[str, ...]
    weights: tuple[float, ...]
    seed: int
    seed_strategy: str
    steps: int
    dtype: str
    damping: float
    rank_tol: float
    max_params: int | None
    fidelity_mode: str
    fidelity_temperature: float
    fidelity_force_override: bool
    objective_input_sha256: str | None = None


def _select_lower_loss_state(
    *,
    previous_loss: float,
    previous_state: Any,
    candidate_loss: float,
    candidate_state: Any,
) -> tuple[float, Any]:
    """Return the lower finite-loss state after evaluating both candidates.

    The helper deliberately does not infer quality from the candidate's
    position or from the fact that it was produced by an optimizer step.  A
    produced state becomes eligible only after its comparable objective has
    been evaluated.
    """
    try:
        previous_value = float(previous_loss)
    except (TypeError, ValueError, OverflowError):
        previous_value = float("inf")
    try:
        candidate_value = float(candidate_loss)
    except (TypeError, ValueError, OverflowError):
        candidate_value = float("inf")
    if np.isfinite(candidate_value) and (
        not np.isfinite(previous_value) or candidate_value < previous_value
    ):
        return candidate_value, candidate_state
    return previous_value, previous_state


def _hessian_reuse_key_matches(
    first: _HessianReuseKey | None,
    second: _HessianReuseKey | None,
) -> bool:
    """Return whether two Hessian evidence identities are exactly compatible."""
    if first is None or second is None or first != second:
        return False
    return bool(
        np.all(np.isfinite(np.asarray(first.flat_theta, dtype=float)))
        and np.all(np.isfinite(np.asarray(first.weights, dtype=float)))
    )


def _make_hessian_reuse_key(
    flat_theta: jnp.ndarray,
    param_names: Sequence[str],
    weights: jnp.ndarray,
    config: CalibrationConfig,
    *,
    steps: int,
    objective_input_sha256: str | None = None,
) -> _HessianReuseKey:
    """Build a complete local identity for a Hessian diagnostic."""
    return _HessianReuseKey(
        flat_theta=tuple(float(value) for value in np.asarray(flat_theta).reshape(-1)),
        param_names=tuple(param_names),
        weights=tuple(float(value) for value in np.asarray(weights).reshape(-1)),
        seed=int(config.seed),
        seed_strategy=config.seed_strategy,
        steps=int(steps),
        dtype=str(jnp.asarray(flat_theta).dtype),
        damping=float(config.hessian.damping),
        rank_tol=float(config.hessian.rank_tol),
        max_params=config.hessian.max_params,
        fidelity_mode=config.fidelity.mode,
        fidelity_temperature=float(config.fidelity.temperature),
        fidelity_force_override=bool(config.fidelity.force_override),
        objective_input_sha256=objective_input_sha256,
    )


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
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex, init=False)
    _lifecycle_started: bool = field(default=False, init=False)
    _lifecycle_finished: bool = field(default=False, init=False)
    _lifecycle_failure_logged: bool = field(default=False, init=False)

    def start(self) -> None:
        """Begin lifecycle tracking without making telemetry a run dependency."""
        if not self.enabled or self._lifecycle_started or self._lifecycle_finished:
            return
        try:
            self._lifecycle_started = bool(
                self._get_metrics().start_calibration_run(
                    run_id=self.run_id,
                    optimizer=self.optimizer_name,
                )
            )
        except Exception:
            self._log_lifecycle_telemetry_failure("start")

    def _record_progress(self) -> None:
        if not self._lifecycle_started or self._lifecycle_finished:
            return
        try:
            self._get_metrics().record_calibration_progress(run_id=self.run_id)
        except Exception:
            self._log_lifecycle_telemetry_failure("progress")

    def finish(self, status: Literal["completed", "failed"]) -> None:
        """End the active execution and retain only its bounded outcome count."""
        if not self.enabled or self._lifecycle_finished:
            return
        self._lifecycle_finished = True
        if not self._lifecycle_started:
            return
        try:
            self._get_metrics().finish_calibration_run(run_id=self.run_id, status=status)
        except Exception:
            self._log_lifecycle_telemetry_failure("finish")

    def _log_lifecycle_telemetry_failure(self, action: str) -> None:
        if self._lifecycle_failure_logged:
            return
        self._lifecycle_failure_logged = True
        _calibration_logger.warning(
            "Calibration lifecycle %s telemetry could not be recorded",
            action,
            exc_info=True,
        )

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
        self._record_progress()
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


_current_calibration_metrics_collector: ContextVar[CalibrationMetricsCollector | None] = ContextVar(
    "current_calibration_metrics_collector", default=None
)


def _track_calibration_lifecycle(
    method: Callable[[Calibrator], CalibrationReport],
) -> Callable[[Calibrator], CalibrationReport]:
    """Record whole-call calibration lifecycle, including preflight failures."""

    @wraps(method)
    def wrapped(self: Calibrator) -> CalibrationReport:
        collector = CalibrationMetricsCollector(
            optimizer_name="adam",
            emit_interval=10,
            enabled=is_hpc_observability_enabled(),
        )
        token = _current_calibration_metrics_collector.set(collector)
        try:
            collector.start()
            result = method(self)
        except BaseException:
            collector.finish("failed")
            raise
        else:
            collector.finish("completed")
            return result
        finally:
            _current_calibration_metrics_collector.reset(token)

    return wrapped


def _compute_scale_local(
    arr: jnp.ndarray,
    target_cfg: CalibrationTarget,
    default_eps: float = 1e-8,
    *,
    observed_mask: jnp.ndarray | None = None,
    training_mask: jnp.ndarray | None = None,
) -> float:
    values = np.asarray(arr)
    eligible = np.isfinite(values)
    if observed_mask is not None:
        observed = np.asarray(observed_mask, dtype=bool)
        if observed.shape != values.shape:
            raise ValueError(
                "Observed mask must match target shape: "
                f"values={values.shape}, observed_mask={observed.shape}"
            )
        eligible &= observed
    if training_mask is not None:
        training = np.asarray(training_mask, dtype=bool)
        if training.shape != values.shape:
            raise ValueError(
                "Training mask must match target shape: "
                f"values={values.shape}, training_mask={training.shape}"
            )
    if not target_cfg.loss.relative:
        return 1.0
    if training_mask is not None:
        eligible &= training
    selected = values[eligible]
    if selected.size == 0:
        return float(default_eps)
    method = target_cfg.loss.scale
    abs_arr = np.abs(selected)
    if method == "std":
        scale = float(np.std(selected))
    elif method == "max":
        scale = float(np.max(abs_arr))
    elif method == "p95":
        scale = float(np.quantile(abs_arr, 0.95))
    elif method == "none":
        scale = 1.0
    else:
        scale = float(np.mean(abs_arr))
    if not np.isfinite(scale):
        return float(default_eps)
    return float(max(scale, default_eps))


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


def _calibration_span_context(
    tracer: Any | None,
    attributes: Mapping[str, Any],
    *,
    start_index: int,
) -> AbstractContextManager[Any]:
    """Create the observability context for one optimization start.

    OpenTelemetry context managers are commonly single-entry objects.  The
    multi-start loop therefore calls this factory for every start instead of
    retaining one context manager and entering it repeatedly.  The no-op path
    follows the same factory contract so telemetry configuration does not
    alter restart semantics.
    """
    if tracer is None:
        return nullcontext()
    return tracer.start_as_current_span(
        "calibration.run",
        attributes={
            **attributes,
            "calibration.start_index": start_index,
        },
    )


def _string_sequence(value: Any) -> tuple[str, ...] | None:
    """Capture declared label values without inventing labels for opaque objects."""
    if value is None:
        return None
    if not isinstance(value, (tuple, list)):
        return None
    items: list[str] = []
    for item in value:
        raw = item.value if hasattr(item, "value") else item
        if not isinstance(raw, str):
            return None
        items.append(raw)
    return tuple(items)


def _artifact_ref_identity(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    """Return the exact CAS view identity for two typed artifact references."""
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _load_selected_source_model(
    store: ArtifactStore,
    ref: ArtifactRef,
    model_cls: type[Any],
    *,
    expected_kind: str,
    expected_schema: str,
) -> Any:
    """Load a typed JSON artifact from its declared exact manifest view."""
    return read_calibration_model_source(
        store,
        role=expected_kind,
        ref=ref,
        model=model_cls,
        expected_kind=expected_kind,
        expected_schema=expected_schema,
        decoder=lambda _ref, _manifest, value: value,
    ).require_value()


def _state_values_equal(left: GlobalState, right: GlobalState) -> bool:
    """Compare all state leaves without stringifying device or array objects."""
    left_leaves, left_tree = jax.tree_util.tree_flatten(left)
    right_leaves, right_tree = jax.tree_util.tree_flatten(right)
    if left_tree != right_tree or len(left_leaves) != len(right_leaves):
        return False
    for left_value, right_value in zip(left_leaves, right_leaves, strict=True):
        try:
            left_array = np.asarray(left_value)
            right_array = np.asarray(right_value)
        except (TypeError, ValueError):
            return False
        if left_array.shape != right_array.shape or left_array.dtype != right_array.dtype:
            return False
        if not np.array_equal(left_array, right_array, equal_nan=True):
            return False
    return True


def _registry_model_capture(
    store: ArtifactStore,
    *,
    ref: ArtifactRef | None,
    model: Any | None,
    model_cls: type[Any],
    kind: str,
    schema_name: str,
) -> tuple[str | None, str, Any | None]:
    """Capture in-memory registry bytes and compare any supplied selected source."""
    if model is None and ref is None:
        return None, "not_established", None
    model_digest = canonical_input_sha256(model) if model is not None else None
    if ref is None:
        return model_digest, "in_memory_content_bound", model
    try:
        selected_model = _load_selected_source_model(
            store,
            ref,
            model_cls,
            expected_kind=kind,
            expected_schema=schema_name,
        )
    except (FileNotFoundError, PermissionError, TypeError, ValueError, KeyError) as error:
        status = classify_calibration_source_error(error, role=kind).status
        if status == "not_established":
            return (
                model_digest,
                "in_memory_content_bound" if model is not None else "not_established",
                model,
            )
        return model_digest, "selected_source_mismatch", model
    selected_digest = canonical_input_sha256(selected_model)
    if model is not None and selected_model != model:
        return model_digest, "selected_source_mismatch", selected_model
    if ref.manifest_profile_sha256 is None:
        return selected_digest, "in_memory_content_bound", selected_model
    return selected_digest, "selected_source_matched", selected_model


def _state_snapshot_blob_digest(
    store: ArtifactStore,
    state_ref: ArtifactRef,
) -> tuple[str, list[InputRef]]:
    """Verify and digest the single state blob selected by one state snapshot."""
    manifest = store.get_manifest(state_ref)
    edges = [edge for edge in manifest.inputs if edge.role == "state_blob"]
    if len(edges) != 1:
        raise ValueError("calibration_base_state_snapshot_requires_one_state_blob_edge")
    edge = edges[0]
    if edge.manifest_profile_sha256 is None:
        blob_manifest = store.get_manifest(edge.artifact_id)
        blob_profile = None
    else:
        blob_manifest = resolve_manifest_by_profile(
            store,
            edge.artifact_id,
            edge.manifest_profile_sha256,
        )
        blob_profile = edge.manifest_profile_sha256
    blob_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=blob_manifest.kind,
        media_type=blob_manifest.media_type,
        manifest_profile_sha256=blob_profile,
    )
    state_blob = store.get_bytes(blob_ref)
    digest = hashlib.sha256(state_blob).hexdigest()
    if edge.artifact_id.hex != digest:
        raise ValueError("calibration_base_state_blob_checksum_mismatch")
    return digest, [input_ref_from_artifact_ref(blob_ref, role="state_blob")]


def _runtime_input_binding(
    *,
    name: str,
    usage: str,
    source_role: str,
    value: object | None,
    active: bool,
    selected_ref: ArtifactRef | None = None,
    selected_value: object | None = None,
    selected_source_expected: bool = False,
    value_digest_override: str | None = None,
    resolved_by: tuple[str, ...] = (),
    limitations: set[str],
) -> CalibrationRuntimeInputBinding:
    """Capture one declared CalibratorInputs field without hashing callable identity."""
    if not active:
        return CalibrationRuntimeInputBinding(
            input_name=name,
            usage=usage,
            source_role=source_role,
            status="not_consumed",
        )

    value_digest = value_digest_override
    if value_digest is None and value is not None:
        try:
            value_digest = canonical_input_sha256(value)
        except (TypeError, ValueError, OverflowError):
            limitations.add(f"runtime_input_not_canonically_serializable:{name}")

    if source_role == "runtime_registry_member":
        if selected_ref is None:
            if value is None:
                status = "selected_source_absent" if selected_source_expected else "absent"
                return CalibrationRuntimeInputBinding(
                    input_name=name,
                    usage=usage,
                    source_role=source_role,
                    status=status,
                )
            if value_digest is None:
                return CalibrationRuntimeInputBinding(
                    input_name=name,
                    usage=usage,
                    source_role=source_role,
                    status="not_established",
                )
            limitations.add(f"runtime_registry_member_source_not_established:{name}")
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="in_memory_content_bound",
                value_sha256=value_digest,
            )
        if value is None:
            selected_digest = (
                canonical_input_sha256(selected_value) if selected_value is not None else None
            )
            limitations.add(f"runtime_registry_member_missing_from_calibrator_inputs:{name}")
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="selected_source_mismatch",
                source_ref=selected_ref,
                source_payload_sha256=selected_digest,
            )
        if value_digest is None:
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="not_established",
                source_ref=selected_ref,
            )
        selected_digest = None
        if selected_value is not None:
            try:
                selected_digest = canonical_input_sha256(selected_value)
            except (TypeError, ValueError, OverflowError):
                limitations.add(f"selected_runtime_registry_member_not_serializable:{name}")
        if selected_digest is None:
            limitations.add(f"selected_runtime_registry_member_not_established:{name}")
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="not_established",
                value_sha256=value_digest,
                source_ref=selected_ref,
            )
        if value_digest != selected_digest:
            limitations.add(f"runtime_registry_member_source_mismatch:{name}")
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="selected_source_mismatch",
                value_sha256=value_digest,
                source_ref=selected_ref,
                source_payload_sha256=selected_digest,
            )
        if selected_ref.manifest_profile_sha256 is None:
            limitations.add(f"runtime_registry_member_selected_profile_not_established:{name}")
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="not_established",
                value_sha256=value_digest,
                source_ref=selected_ref,
                source_payload_sha256=selected_digest,
            )
        return CalibrationRuntimeInputBinding(
            input_name=name,
            usage=usage,
            source_role=source_role,
            status="selected_source_matched",
            value_sha256=value_digest,
            source_ref=selected_ref,
            source_payload_sha256=selected_digest,
        )

    if value is None:
        return CalibrationRuntimeInputBinding(
            input_name=name,
            usage=usage,
            source_role=source_role,
            status="absent",
        )
    if value_digest is None:
        return CalibrationRuntimeInputBinding(
            input_name=name,
            usage=usage,
            source_role=source_role,
            status="not_established",
            resolved_by=resolved_by,
        )
    if resolved_by:
        return CalibrationRuntimeInputBinding(
            input_name=name,
            usage=usage,
            source_role=source_role,
            status="resolved_output_content_bound",
            value_sha256=value_digest,
            resolved_by=resolved_by,
        )
    if selected_ref is not None:
        selected_digest = None
        if selected_value is not None:
            try:
                selected_digest = canonical_input_sha256(selected_value)
            except (TypeError, ValueError, OverflowError):
                limitations.add(f"selected_runtime_input_not_serializable:{name}")
        if selected_digest is None:
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="not_established",
                value_sha256=value_digest,
                source_ref=selected_ref,
            )
        if value_digest != selected_digest:
            limitations.add(f"runtime_input_selected_source_mismatch:{name}")
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="selected_source_mismatch",
                value_sha256=value_digest,
                source_ref=selected_ref,
                source_payload_sha256=selected_digest,
            )
        if selected_ref.manifest_profile_sha256 is None:
            limitations.add(f"runtime_input_selected_profile_not_established:{name}")
            return CalibrationRuntimeInputBinding(
                input_name=name,
                usage=usage,
                source_role=source_role,
                status="not_established",
                value_sha256=value_digest,
                source_ref=selected_ref,
                source_payload_sha256=selected_digest,
            )
        return CalibrationRuntimeInputBinding(
            input_name=name,
            usage=usage,
            source_role=source_role,
            status="selected_source_matched",
            value_sha256=value_digest,
            source_ref=selected_ref,
            source_payload_sha256=selected_digest,
        )
    return CalibrationRuntimeInputBinding(
        input_name=name,
        usage=usage,
        source_role=source_role,
        status="in_memory_content_bound",
        value_sha256=value_digest,
    )


def _prepare_selected_ordered_input(
    store: ArtifactStore,
    inputs: CalibratorInputs,
    config_ref: ArtifactRef,
) -> tuple[ArtifactRef, OrderedBatchCalibrationProfile]:
    """Publish and reopen the sole full input that the fit will actually consume."""
    profile = inputs.ordered_batch_profile
    if profile is None:
        raise ValueError("ordered_input_profile_missing")
    if len(inputs.config.targets) != 1:
        raise ValueError("ordered_input_requires_exactly_one_target")
    if any(
        np.asarray(value).dtype not in (np.dtype("float32"), np.dtype("float64"))
        for value in (profile.targets, profile.weights)
    ):
        raise ValueError("ordered_input_targets_and_weights_require_float32_or_float64")
    for leaf in jax.tree_util.tree_leaves(profile.states):
        if not bool(jnp.all(jnp.isfinite(leaf))):
            raise ValueError("ordered_input_finite_state_profile_required")
    ordered_row_input_refs = [input_ref_from_artifact_ref(config_ref, role="calibration_config")]
    row_inputs = []
    for ordinal, row_id in enumerate(profile.row_ids):
        row_state = jax.tree_util.tree_map(lambda leaf: leaf[ordinal], profile.states)
        row_ref = put_state_snapshot(
            store,
            state=row_state,
            step=int(profile.row_times[ordinal]),
            return_selected_profile=True,
        )
        row_inputs.append(
            CalibrationOrderedBatchRow(
                row_id=row_id,
                state_snapshot_ref=row_ref,
                state_values_sha256=canonical_input_sha256(row_state),
            )
        )
        ordered_row_input_refs.append(
            input_ref_from_artifact_ref(row_ref, role=f"ordered_batch_row.{ordinal}")
        )
    target = inputs.config.targets[0]
    ordered_profile_basis = CalibrationOrderedBatchInput(
        calibration_config_ref=config_ref,
        **_ordered_numeric_settings(),
        target_id=target.target_id,
        target_metric_id=target.model_metric_path,
        target_path=profile.target_path,
        rows=tuple(row_inputs),
        row_times=tuple(np.asarray(profile.row_times).tolist()),
        row_times_dtype=str(np.asarray(profile.row_times).dtype),
        row_keys=tuple(tuple(row) for row in np.asarray(profile.row_keys).tolist()),
        targets=tuple(np.asarray(profile.targets).tolist()),
        targets_dtype=str(np.asarray(profile.targets).dtype),
        weights=tuple(np.asarray(profile.weights).tolist()),
        weights_dtype=str(np.asarray(profile.weights).dtype),
        consumed_profile_sha256=canonical_input_sha256(profile),
        loss_epsilon=target.loss.epsilon,
        target_priority=target.loss.weight,
    )

    assert ordered_profile_basis is not None
    selected_ref = put_calibration_ordered_batch_input(
        store,
        ordered_profile_basis,
        inputs=ordered_row_input_refs,
    )
    selected, values = resolve_calibration_ordered_batch_input(store, selected_ref)
    if (
        selected.consumed_profile_sha256 != canonical_input_sha256(profile)
        or selected.calibration_config_ref != config_ref
    ):
        raise ValueError("ordered_input_writer_returned_a_foreign_request")
    immutable = OrderedBatchCalibrationProfile(
        **{
            name: (
                jax.tree_util.tree_map(jnp.asarray, value)
                if name == "states"
                else jnp.asarray(value)
                if name not in {"row_ids", "target_path"}
                else value
            )
            for name, value in values.items()
        }
    )
    if canonical_input_sha256(immutable) != selected.consumed_profile_sha256:
        raise ValueError("ordered_input_backend_changed_declared_values_or_precision")
    return selected_ref, immutable


def _persist_calibration_execution_basis(
    store: ArtifactStore,
    *,
    inputs: CalibratorInputs,
    config_ref: ArtifactRef,
    report: CalibrationReport,
    capture: dict[str, Any],
) -> ArtifactRef:
    """Persist the exact local fit inputs and their selected source edges."""
    graph_ref = ArtifactRef.model_validate(inputs.exec_plan.program_ref.model_dump(mode="python"))
    graph_digest = canonical_input_sha256(inputs.program_graph)
    plan_digest = canonical_input_sha256(inputs.exec_plan)
    limitations = set(capture.get("limitations", ()))
    runtime_limitations = set(capture.get("runtime_input_limitations", ()))

    graph_status = "in_memory_snapshot_only"
    selected_graph: ProgramGraph | None = None
    try:
        selected_graph = _load_selected_source_model(
            store,
            graph_ref,
            ProgramGraph,
            expected_kind=ProgramGraph.ARTIFACT_KIND,
            expected_schema=ProgramGraph.ARTIFACT_SCHEMA_NAME,
        )
        if selected_graph != inputs.program_graph:
            graph_status = "selected_source_mismatch"
            limitations.add("program_graph_did_not_match_selected_source")
        elif graph_ref.manifest_profile_sha256 is not None:
            graph_status = "selected_source_matched"
        else:
            limitations.add("program_graph_selected_profile_not_supplied")
    except (FileNotFoundError, PermissionError, TypeError, ValueError, KeyError) as error:
        read_status = classify_calibration_source_error(error, role="program_graph").status
        if read_status == "mismatch":
            graph_status = "selected_source_mismatch"
            limitations.add("selected_program_graph_invalid")
        else:
            limitations.add("selected_program_graph_not_established")

    plan_status = "object_only"
    selected_plan: ExecPlan | None = None
    if inputs.exec_plan_ref is None:
        limitations.add("exec_plan_selected_artifact_ref_not_supplied")
    else:
        try:
            selected_plan = _load_selected_source_model(
                store,
                inputs.exec_plan_ref,
                ExecPlan,
                expected_kind=ExecPlan.ARTIFACT_KIND,
                expected_schema=ExecPlan.ARTIFACT_SCHEMA_NAME,
            )
            if selected_plan != inputs.exec_plan or _artifact_ref_identity(
                selected_plan.program_ref
            ) != _artifact_ref_identity(graph_ref):
                plan_status = "selected_source_mismatch"
                limitations.add("exec_plan_did_not_match_selected_source")
            elif inputs.exec_plan_ref.manifest_profile_sha256 is not None:
                plan_status = "selected_source_matched"
            else:
                limitations.add("exec_plan_selected_profile_not_supplied")
        except (FileNotFoundError, PermissionError, TypeError, ValueError, KeyError) as error:
            read_status = classify_calibration_source_error(error, role="exec_plan").status
            if read_status == "mismatch":
                plan_status = "selected_source_mismatch"
                limitations.add("selected_exec_plan_invalid")
            else:
                limitations.add("selected_exec_plan_not_established")

    registry_bundle_ref = inputs.registry_bundle_ref
    registry_bundle_digest: str | None = None
    registry_bundle_status = "not_established"
    bundle_members = None
    bundle_content = None
    if registry_bundle_ref is not None:
        try:
            bundle_members = read_calibration_model_source(
                store,
                role="registry_bundle",
                model=RegistryBundlePayload,
                ref=registry_bundle_ref,
                expected_kind="core.registry_bundle",
                decoder=lambda _ref, _manifest, value: value,
            ).require_value()
            bundle_content = read_calibration_registry_source(
                store, registry_bundle_ref
            ).require_value()
            registry_bundle_digest = canonical_input_sha256(bundle_members)
            registry_bundle_status = (
                "selected_source_matched"
                if registry_bundle_ref.manifest_profile_sha256 is not None
                else "in_memory_content_bound"
            )
        except (FileNotFoundError, PermissionError, TypeError, ValueError, KeyError) as error:
            read_status = classify_calibration_source_error(error, role="registry_bundle").status
            registry_bundle_status = (
                "selected_source_mismatch" if read_status == "mismatch" else "not_established"
            )
            limitations.add(
                "registry_bundle_invalid"
                if read_status == "mismatch"
                else "registry_bundle_not_established"
            )
    else:
        limitations.add("registry_bundle_selected_source_not_supplied")

    mechanism_registry_ref = inputs.mechanism_registry_ref
    units_registry_ref = inputs.units_registry_ref
    if bundle_members is not None:
        mechanism_registry_ref = mechanism_registry_ref or bundle_members.mechanism_registry
        units_registry_ref = units_registry_ref or bundle_members.units_registry

    mechanism_digest, mechanism_status, selected_mechanism_registry = _registry_model_capture(
        store,
        ref=mechanism_registry_ref,
        model=inputs.mechanism_registry,
        model_cls=MechanismTypeRegistry,
        kind="ir.mechanism_registry",
        schema_name="polisyos.ir.kernel.MechanismTypeRegistry",
    )
    units_registry = inputs.units_registry
    if units_registry is None and units_registry_ref is not None:
        try:
            units_registry = _load_selected_source_model(
                store,
                units_registry_ref,
                UnitsRegistry,
                expected_kind="ir.units_registry",
                expected_schema="polisyos.ir.kernel.UnitsRegistry",
            )
        except (FileNotFoundError, TypeError, ValueError, KeyError):
            units_registry = None
    units_digest, units_status, selected_units_registry = _registry_model_capture(
        store,
        ref=units_registry_ref,
        model=units_registry,
        model_cls=UnitsRegistry,
        kind="ir.units_registry",
        schema_name="polisyos.ir.kernel.UnitsRegistry",
    )
    mechanism_registry = inputs.mechanism_registry
    if selected_mechanism_registry is not None and mechanism_status == "selected_source_matched":
        mechanism_registry = selected_mechanism_registry
    if selected_units_registry is not None and units_status == "selected_source_matched":
        units_registry = selected_units_registry

    if mechanism_status != "selected_source_matched":
        limitations.add("mechanism_registry_selected_source_not_established")
    if units_status != "selected_source_matched":
        limitations.add("unit_registry_selected_source_not_established")
    if registry_bundle_status != "selected_source_matched":
        limitations.add("registry_bundle_selected_source_not_established")

    base_state_ref = inputs.base_state_snapshot_ref
    selected_base_state: GlobalState | None = None
    if base_state_ref is None:
        base_state_ref = put_state_snapshot(
            store,
            state=inputs.base_state,
            step=0,
            return_selected_profile=True,
        )
        base_state_source_status = "snapshot_materialized_only"
        limitations.add("base_state_selected_source_not_supplied")
    else:
        try:
            selected_base_state = load_state_snapshot(store, snapshot_ref=base_state_ref)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("supplied_base_state_snapshot_invalid") from exc
        if not _state_values_equal(selected_base_state, inputs.base_state):
            base_state_source_status = "selected_source_mismatch"
            limitations.add("base_state_snapshot_did_not_match_consumed_state")
        elif base_state_ref.manifest_profile_sha256 is None:
            base_state_source_status = "snapshot_materialized_only"
            limitations.add("base_state_selected_profile_not_supplied")
        else:
            base_state_source_status = "selected_source_matched"
    state_checksum, state_blob_inputs = _state_snapshot_blob_digest(store, base_state_ref)

    if inputs.measurement_loss_adapter is not None:
        runtime_limitations.add(
            "custom_measurement_loss_adapter_behavior_not_independently_recomputed"
        )
    if inputs.aux_loss_components:
        runtime_limitations.add(
            "auxiliary_loss_implementation_behavior_not_independently_recomputed"
        )

    target_inputs: list[CalibrationTargetInputIdentity] = []
    target_source_kinds = capture.get("target_source_kinds", {})
    consumed_values = capture.get("target_values", {})
    captured_time_axes = capture.get("report_time_axes", {})
    measurement_bundle = inputs.measurement_bundle
    for target in inputs.config.targets:
        target_id = target.target_id
        comparison = report.series_comparison.get(target_id)
        if comparison is None or target_id not in consumed_values:
            limitations.add(f"calibration_target_materialization_missing:{target_id}")
            continue
        observed_values = consumed_values[target_id]
        if comparison.real != observed_values or comparison.time != captured_time_axes.get(
            target_id
        ):
            limitations.add(
                f"calibration_report_target_differs_from_captured_objective:{target_id}"
            )
        source_time_axis: Any = inputs.config.time_axis
        time_grain = None
        split_labels = None
        observation_ids = None
        identification_modes = None
        measurement_digest = None
        split_status = "not_established"
        if measurement_bundle is not None:
            source_time_axis = measurement_bundle.time_axis.get(target_id)
            raw_grain = measurement_bundle.time_grain.get(target_id)
            if hasattr(raw_grain, "value"):
                time_grain = raw_grain.value
            elif isinstance(raw_grain, str):
                time_grain = raw_grain
            split_labels = _string_sequence(measurement_bundle.split_label.get(target_id))
            observation_ids = _string_sequence(measurement_bundle.observation_id.get(target_id))
            identification_modes = _string_sequence(
                measurement_bundle.identification_mode.get(target_id)
            )
            if split_labels:
                split_status = "captured"
            metadata = {
                name: getattr(measurement_bundle, name).get(target_id)
                for name in (
                    "trust_weight",
                    "coverage_estimate",
                    "censoring_mask",
                    "lag_days_estimate",
                    "shock_mask",
                    "schema_regime_id",
                    "observation_id",
                    "time_axis",
                    "split_label",
                    "identification_mode",
                    "time_grain",
                )
            }
            try:
                measurement_digest = canonical_input_sha256(metadata)
            except (TypeError, ValueError, OverflowError):
                limitations.add(f"measurement_metadata_content_not_bound:{target_id}")
        if source_time_axis is not None and not isinstance(source_time_axis, (tuple, list)):
            limitations.add(f"source_time_axis_not_captured_as_ordered_sequence:{target_id}")
            source_time_axis = None
        report_time = comparison.time
        target_inputs.append(
            CalibrationTargetInputIdentity(
                target_id=target_id,
                report_series_sha256=calibration_report_series_sha256(
                    real=comparison.real,
                    time=report_time,
                ),
                observed_values_sha256=canonical_input_sha256(observed_values),
                report_time_axis_sha256=calibration_report_time_axis_sha256(report_time),
                source_kind=target_source_kinds.get(target_id, "mixed_or_unknown"),
                source_time_axis=tuple(source_time_axis) if source_time_axis is not None else None,
                time_grain=time_grain,
                split_labels=split_labels,
                observation_ids=observation_ids,
                identification_modes=identification_modes,
                measurement_metadata_sha256=measurement_digest,
                split_status=split_status,
            )
        )

    parameter_unit_identities: list[CalibrationParameterUnitIdentity] = []
    for parameter_input in capture.get("parameter_inputs", ()):
        if parameter_input.node_id is None or parameter_input.mechanism_type is None:
            if parameter_input.parameter_ids:
                limitations.add("parameter_contract_source_not_established")
            continue
        mechanism_spec = mechanism_registry.mechanisms.get(parameter_input.mechanism_type)
        for parameter_id in parameter_input.parameter_ids:
            parameter_spec = (
                mechanism_spec.params.get(parameter_id) if mechanism_spec is not None else None
            )
            if parameter_spec is None:
                parameter_unit_identities.append(
                    CalibrationParameterUnitIdentity(
                        field_name=f"{parameter_input.node_id}.{parameter_id}",
                        mechanism_type=parameter_input.mechanism_type,
                        parameter_id=parameter_id,
                        value_type="not_established",
                        unit_id=None,
                        parameter_spec_status="not_established",
                        unit_definition_status="not_established",
                        status="not_established",
                    )
                )
                limitations.add("resolved_parameter_spec_missing_from_mechanism_registry")
                continue
            parameter_spec_status = (
                "selected_source_content_bound"
                if mechanism_status == "selected_source_matched"
                else "in_memory_content_bound"
            )
            parameter_spec_digest = canonical_input_sha256(parameter_spec)
            unit_digest = None
            unit_definition_status = "not_established"
            unit_id = parameter_spec.unit_id
            if unit_id is None:
                limitations.add("parameter_unit_id_not_declared")
            elif units_registry is None:
                limitations.add("unit_definition_not_established")
            elif unit_id not in units_registry.units:
                unit_definition_status = "selected_source_missing"
                limitations.add(f"selected_unit_definition_missing:{unit_id}")
            else:
                unit_digest = canonical_input_sha256(units_registry.units[unit_id])
                unit_definition_status = (
                    "selected_source_content_bound"
                    if units_status == "selected_source_matched"
                    else "in_memory_content_bound"
                )
                limitations.add("unit_definition_authority_not_established")
            parameter_unit_identities.append(
                CalibrationParameterUnitIdentity(
                    field_name=f"{parameter_input.node_id}.{parameter_id}",
                    mechanism_type=parameter_input.mechanism_type,
                    parameter_id=parameter_id,
                    value_type=parameter_spec.value_type.value,
                    unit_id=unit_id,
                    parameter_spec_sha256=parameter_spec_digest,
                    parameter_spec_status=parameter_spec_status,
                    unit_definition_sha256=unit_digest,
                    unit_definition_status=unit_definition_status,
                    status="parameter_spec_bound",
                )
            )

    report_envelope_digests: dict[str, str] = {}
    for field_name, envelope in (report.uncertainty_envelopes or {}).items():
        report_envelope_digests[field_name] = canonical_input_sha256(envelope)

    input_names = tuple(field.name for field in dataclass_fields(inputs))
    if input_names != CALIBRATION_RUNTIME_INPUT_NAMES_V1_2:
        raise ValueError("calibrator_input_runtime_roster_contract_drift")
    target_resolution_digest = canonical_input_sha256(
        [item.model_dump(mode="json") for item in target_inputs]
    )
    parameter_resolution_digest = canonical_input_sha256(
        [item.model_dump(mode="json") for item in capture.get("parameter_inputs", ())]
    )
    report_horizons = {len(item.model) for item in report.series_comparison.values()}
    report_horizon_digest = (
        canonical_input_sha256({"steps": next(iter(report_horizons))})
        if len(report_horizons) == 1
        else None
    )
    ordered_profile_basis = None
    ordered_input_ref = capture.get("ordered_input_ref")
    if inputs.ordered_batch_profile is not None:
        if ordered_input_ref is None:
            raise ValueError("ordered_fit_requires_its_selected_consumed_input")
        ordered_profile_basis, _ = resolve_calibration_ordered_batch_input(store, ordered_input_ref)
    active_target_queries = any(target.fabric_query is not None for target in inputs.config.targets)
    runtime_input_roster: list[CalibrationRuntimeInputBinding] = []
    registry_member_by_name = {
        name: (ref_field, model_field)
        for name, ref_field, _kind, _schema_name in RUNTIME_REGISTRY_MEMBER_CONTRACT
        for model_field in (name,)
    }
    runtime_contract = (
        CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2
        if ordered_profile_basis is not None
        else CALIBRATION_RUNTIME_INPUT_CONTRACT
    )
    for name, usage, source_role in runtime_contract:
        value = getattr(inputs, name)
        active = True
        resolved_by: tuple[str, ...] = ()
        value_digest_override: str | None = None
        selected_ref: ArtifactRef | None = None
        selected_value: object | None = None
        selected_source_expected = False

        if name == "ordered_batch_profile":
            assert ordered_profile_basis is not None
            value = ordered_profile_basis
            selected_ref, selected_value = ordered_input_ref, ordered_profile_basis
        elif name in {"constraint_registry", "constraint_values"}:
            active = bool(inputs.config.constraint_loss.enabled)
        elif name in {"raw_targets", "udf_engine", "target_fetcher"}:
            active = inputs.measurement_bundle is None and bool(
                inputs.raw_targets or active_target_queries
            )
            if name in {"udf_engine", "target_fetcher"}:
                active = active and active_target_queries and value is not None
            if name == "raw_targets":
                active = active and bool(value)
            if active:
                resolved_by = ("target_inputs",)
                value_digest_override = target_resolution_digest
        elif name == "controls_seq":
            active = value is not None
            if active and report_horizon_digest is not None:
                resolved_by = ("report_series_horizon",)
                value_digest_override = report_horizon_digest
        elif name == "parameter_loader":
            active = bool(capture.get("parameter_inputs"))
            if active:
                resolved_by = ("parameter_inputs",)
                value_digest_override = parameter_resolution_digest
        elif name in {"measurement_bundle", "measurement_loss_config", "measurement_loss_adapter"}:
            active = inputs.measurement_bundle is not None
            if name != "measurement_bundle":
                active = active and value is not None
        elif name == "aux_loss_components":
            active = bool(value)
        elif name == "units_registry":
            # This optional object is used only while creating parameter-unit
            # identities; it is not passed to the fit loop itself.
            active = value is not None

        if name in registry_member_by_name:
            ref_field, model_field = registry_member_by_name[name]
            selected_ref = getattr(bundle_members, ref_field, None)
            selected_value = getattr(bundle_content, model_field, None)
            selected_source_expected = bundle_members is not None
            if name == "constraint_registry" and not active:
                selected_ref = None
                selected_value = None
                selected_source_expected = False
        elif name == "config":
            selected_ref, selected_value = config_ref, inputs.config
        elif name == "program_graph":
            selected_ref, selected_value = graph_ref, selected_graph
        elif name == "exec_plan":
            selected_ref, selected_value = inputs.exec_plan_ref, selected_plan
        elif name == "base_state":
            selected_ref = base_state_ref
            selected_value = selected_base_state
            if base_state_source_status == "selected_source_mismatch":
                value_digest_override = None
        elif source_role in {
            "selected_exec_plan_ref",
            "selected_runtime_registry_bundle_ref",
            "runtime_registry_member_ref",
            "selected_base_state_snapshot_ref",
        }:
            # These fields are themselves references. Their exact identities
            # are separately checked by the corresponding selected-source
            # contract fields above; do not confuse a ref digest with payload bytes.
            selected_ref = None

        if source_role == "runtime_registry_member" and name in registry_member_by_name:
            binding = _runtime_input_binding(
                name=name,
                usage=usage,
                source_role=source_role,
                value=value,
                active=active,
                selected_ref=selected_ref,
                selected_value=selected_value,
                selected_source_expected=selected_source_expected,
                limitations=runtime_limitations,
            )
        elif source_role == "resolved_parameter_inputs" or source_role == "resolved_target_inputs":
            binding = _runtime_input_binding(
                name=name,
                usage=usage,
                source_role=source_role,
                value=value,
                active=active,
                value_digest_override=value_digest_override,
                resolved_by=resolved_by,
                limitations=runtime_limitations,
            )
        elif source_role == "report_series_horizon":
            binding = _runtime_input_binding(
                name=name,
                usage=usage,
                source_role=source_role,
                value=value,
                active=active and report_horizon_digest is not None,
                value_digest_override=value_digest_override,
                resolved_by=resolved_by,
                limitations=runtime_limitations,
            )
        elif source_role in {
            "ordered_batch_profile",
            "selected_calibration_config",
            "selected_program_graph",
            "selected_exec_plan",
            "selected_base_state_snapshot",
        }:
            binding = _runtime_input_binding(
                name=name,
                usage=usage,
                source_role=source_role,
                value=value,
                active=active,
                selected_ref=selected_ref,
                selected_value=selected_value,
                value_digest_override=value_digest_override,
                limitations=runtime_limitations,
            )
        else:
            binding = _runtime_input_binding(
                name=name,
                usage=usage,
                source_role=source_role,
                value=value,
                active=active,
                value_digest_override=value_digest_override,
                resolved_by=resolved_by,
                limitations=runtime_limitations,
            )
        if binding.status == "not_established":
            runtime_limitations.add(f"runtime_input_not_established:{name}")
        if binding.status == "selected_source_mismatch":
            runtime_limitations.add(f"runtime_input_selected_source_mismatch:{name}")
        runtime_input_roster.append(binding)

    input_refs: list[InputRef] = [
        input_ref_from_artifact_ref(config_ref, role="calibration_config"),
        input_ref_from_artifact_ref(graph_ref, role="program_graph"),
        input_ref_from_artifact_ref(base_state_ref, role="base_state_snapshot"),
        *state_blob_inputs,
        *(
            [input_ref_from_artifact_ref(ordered_input_ref, role="ordered_batch_input")]
            if ordered_input_ref is not None
            else []
        ),
    ]
    if inputs.exec_plan_ref is not None:
        input_refs.append(input_ref_from_artifact_ref(inputs.exec_plan_ref, role="exec_plan"))
    if registry_bundle_ref is not None:
        input_refs.append(input_ref_from_artifact_ref(registry_bundle_ref, role="registry_bundle"))
    if mechanism_registry_ref is not None:
        input_refs.append(
            input_ref_from_artifact_ref(mechanism_registry_ref, role="mechanism_registry")
        )
    if units_registry_ref is not None:
        input_refs.append(input_ref_from_artifact_ref(units_registry_ref, role="unit_registry"))
    for parameter_input in capture.get("parameter_inputs", ()):
        if parameter_input.source_ref is None:
            continue
        input_refs.append(
            input_ref_from_artifact_ref(
                parameter_input.source_ref,
                role=f"parameter_input.{parameter_input.ordinal}",
            )
        )

    limitations.update(runtime_limitations)
    limitations.add("external_source_attestation_not_established")
    limitations.add("physical_time_semantics_not_established")
    limitations.add("external_unit_law_not_established")
    expected_target_order = tuple(target.target_id for target in inputs.config.targets)
    target_complete = tuple(item.target_id for item in target_inputs) == expected_target_order
    parameters_complete = all(
        item.status == "content_bound" and item.effective_values_status == "content_bound"
        for item in capture.get("parameter_inputs", ())
    )
    local_capture_complete = (
        target_complete
        and parameters_complete
        and not runtime_limitations
        and len(report.series_comparison) == len(expected_target_order)
    )
    basis = CalibrationExecutionInputBasis(
        schema_version="1.2" if ordered_profile_basis is not None else "1.1",
        input_capture_status="content_bound" if local_capture_complete else "limited",
        calibration_config_ref=config_ref,
        registry_bundle_ref=registry_bundle_ref,
        registry_bundle_sha256=registry_bundle_digest,
        registry_bundle_status=registry_bundle_status,
        exec_plan_ref=inputs.exec_plan_ref,
        exec_plan_sha256=plan_digest,
        program_graph_ref=graph_ref,
        program_graph_sha256=graph_digest,
        program_graph_status=graph_status,
        exec_plan_source_status=plan_status,
        mechanism_registry_ref=mechanism_registry_ref,
        mechanism_registry_sha256=mechanism_digest,
        mechanism_registry_status=mechanism_status,
        unit_registry_ref=units_registry_ref,
        unit_registry_sha256=units_digest,
        unit_registry_status=units_status,
        exec_plan=inputs.exec_plan,
        base_state_snapshot_ref=base_state_ref,
        base_state_checksum_sha256=state_checksum,
        base_state_source_status=base_state_source_status,
        target_order=expected_target_order,
        target_inputs=tuple(target_inputs),
        parameter_inputs=tuple(capture.get("parameter_inputs", ())),
        parameter_unit_identities=tuple(parameter_unit_identities),
        calibrated_parameter_values_sha256=canonical_input_sha256(report.calibrated_params),
        report_envelope_sha256=report_envelope_digests,
        runtime_input_sha256={},
        runtime_input_roster=tuple(runtime_input_roster),
        runtime_input_limitations=tuple(sorted(runtime_limitations)),
        ordered_batch_input_ref=ordered_input_ref,
        ordered_batch_input_value_sha256=(
            canonical_input_sha256(ordered_profile_basis)
            if ordered_profile_basis is not None
            else None
        ),
        limitations=tuple(sorted(limitations)),
    )
    return put_calibration_execution_input_basis(store, basis, inputs=input_refs)


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
        self._execution_capture: dict[str, Any] | None = None

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

    def run_and_persist(self, store: ArtifactStore) -> tuple[CalibrationReport, ArtifactRef]:
        """Run once and persist the report with the exact configuration used.

        A deep value snapshot of all ``CalibratorInputs`` is taken before the fit.
        The optimizer and the persisted execution identity use independent copies of
        that snapshot, so later caller mutation cannot rewrite the recorded inputs.
        Opaque providers retain their callable identity; their consumed parameter or
        target outputs are captured where possible and remaining behavior stays limited.
        The report edge is built from the complete config ArtifactRef, preserving a
        selected non-default manifest profile as well as the content ID. The report's
        fitted coordinates can then be inspected alongside that exact config view.

        This binds the internal config-to-report run. It does not authenticate
        observed data, establish a calibration/noise law, or make heuristic
        uncertainty gate-eligible; callers must keep those source facts and
        authority claims separate.

        Args:
            store: Artifact store used for the configuration and report.

        Returns:
            The report produced by the run and its persisted CAS reference.
        """
        fit_inputs = _snapshot_calibrator_inputs(self.inputs)
        basis_inputs = _snapshot_calibrator_inputs(fit_inputs)
        fit_config = fit_inputs.config.model_copy(deep=True)
        basis_config = basis_inputs.config.model_copy(deep=True)
        selected_config_ref = None
        selected_ordered_ref = None
        if fit_inputs.ordered_batch_profile is not None:
            selected_config_ref = put_calibration_config(
                store, fit_config, return_selected_profile=True
            )
            selected_ordered_ref, consumed = _prepare_selected_ordered_input(
                store,
                replace(fit_inputs, config=fit_config),
                selected_config_ref,
            )
            fit_inputs = replace(fit_inputs, ordered_batch_profile=consumed)
            basis_inputs = _snapshot_calibrator_inputs(fit_inputs)
        capture: dict[str, Any] = {
            "ordered_input_ref": selected_ordered_ref,
            "parameter_inputs": [],
            "runtime_input_limitations": [],
            "limitations": [],
        }
        parameter_sources: list[tuple[Any, str, str, ArtifactRef | None]] = []
        node_by_id = {node.node_id: node for node in fit_inputs.program_graph.nodes}
        order = fit_inputs.exec_plan.order or [
            node.node_id for node in fit_inputs.program_graph.nodes
        ]
        for node_id in order:
            node = node_by_id.get(node_id)
            if node is None or node.node_kind not in {"mechanism", "op"}:
                continue
            mechanism_type = node.mechanism_type
            params_ref = node.params_ref
            if node.node_kind == "op" and node.op is not None:
                if node.op.op_kind != "apply_mechanism":
                    continue
                mechanism_type = node.op.params.get("mechanism_type") or mechanism_type
                params_ref = node.op.params.get("params_ref") or params_ref
            if mechanism_type is None:
                continue
            source = params_ref or node
            source_ref = source if isinstance(source, ArtifactRef) else None
            parameter_sources.append((source, node_id, mechanism_type, source_ref))

        def capture_parameter_payload(source: Any) -> dict[str, Any]:
            payload = fit_inputs.parameter_loader(source) or {}
            match_index = next(
                (
                    index
                    for index, (candidate, _node_id, _mechanism_type, _source_ref) in enumerate(
                        parameter_sources
                    )
                    if candidate is source or candidate == source
                ),
                None,
            )
            if match_index is None:
                node_id = None
                mechanism_type = None
                source_ref = source if isinstance(source, ArtifactRef) else None
                capture["runtime_input_limitations"].append(
                    "parameter_loader_call_source_not_mapped_to_program_node"
                )
            else:
                _candidate, node_id, mechanism_type, source_ref = parameter_sources.pop(match_index)
            try:
                payload_sha256 = canonical_input_sha256(payload)
                status = "content_bound"
            except (TypeError, ValueError, OverflowError):
                payload_sha256 = None
                status = "not_established"
                capture["runtime_input_limitations"].append(
                    "parameter_loader_output_not_canonically_serializable"
                )
            source_payload_sha256 = None
            source_status = "in_memory_only" if source_ref is None else "not_established"
            if source_ref is not None and source_ref.manifest_profile_sha256 is not None:
                try:
                    if not store.verify(source_ref).ok:
                        raise ValueError("parameter_source_integrity_failure")
                    source_payload = from_canonical_bytes(store.get_bytes(source_ref))
                    source_payload_sha256 = canonical_input_sha256(source_payload)
                    if source_payload_sha256 == payload_sha256:
                        source_status = "selected_source_matched"
                    else:
                        source_status = "selected_source_mismatch"
                        capture["runtime_input_limitations"].append(
                            "parameter_loader_output_differs_from_selected_source"
                        )
                except (FileNotFoundError, TypeError, ValueError, KeyError, OverflowError):
                    source_payload_sha256 = None
                    source_status = "selected_source_mismatch"
                    capture["runtime_input_limitations"].append(
                        "selected_parameter_source_unavailable_or_invalid"
                    )
            elif source_ref is not None:
                capture["runtime_input_limitations"].append(
                    "parameter_source_selected_profile_not_supplied"
                )
            capture["parameter_inputs"].append(
                CalibrationResolvedParameterInput(
                    ordinal=len(capture["parameter_inputs"]),
                    node_id=node_id,
                    mechanism_type=mechanism_type,
                    parameter_ids=(
                        tuple(payload["params"].keys())
                        if isinstance(payload.get("params"), Mapping)
                        and all(isinstance(key, str) for key in payload["params"])
                        else ()
                    ),
                    source_ref=source_ref,
                    source_payload_sha256=source_payload_sha256,
                    source_status=source_status,
                    payload_sha256=payload_sha256,
                    status=status,
                )
            )
            return payload

        fit_calibrator = Calibrator(
            replace(
                fit_inputs,
                config=fit_config,
                parameter_loader=capture_parameter_payload,
            )
        )
        fit_calibrator._execution_capture = capture
        report = fit_calibrator.run()
        compiled_bundle = fit_calibrator._bundle
        if compiled_bundle is None:
            capture["runtime_input_limitations"].append(
                "compiled_calibration_bundle_not_available_after_run"
            )
        else:
            prepared_by_node = {node.node_id: node for node in compiled_bundle.nodes}
            resolved_inputs: list[CalibrationResolvedParameterInput] = []
            for parameter_input in capture["parameter_inputs"]:
                prepared = prepared_by_node.get(parameter_input.node_id)
                mechanism_spec = fit_inputs.mechanism_registry.mechanisms.get(
                    parameter_input.mechanism_type
                )
                if prepared is None or mechanism_spec is None:
                    resolved_inputs.append(
                        CalibrationResolvedParameterInput.model_validate(
                            {
                                **parameter_input.model_dump(mode="python"),
                                "parameter_ids": (),
                                "effective_parameter_values_sha256": None,
                                "effective_values_status": "not_established",
                            }
                        )
                    )
                    capture["runtime_input_limitations"].append(
                        "compiled_effective_parameter_values_not_established"
                    )
                    continue
                effective_values: dict[str, Any] = {}
                missing_fields: list[str] = []
                for field_name in mechanism_spec.params:
                    if not hasattr(prepared.mechanism, field_name):
                        missing_fields.append(field_name)
                        continue
                    effective_values[field_name] = getattr(prepared.mechanism, field_name)
                try:
                    effective_values_sha256 = canonical_input_sha256(effective_values)
                    effective_status = "content_bound"
                except (TypeError, ValueError, OverflowError):
                    effective_values_sha256 = None
                    effective_status = "not_established"
                    capture["runtime_input_limitations"].append(
                        f"compiled_effective_parameter_values_not_serializable:{prepared.node_id}"
                    )
                if missing_fields:
                    capture["runtime_input_limitations"].append(
                        f"compiled_effective_parameter_fields_missing:{prepared.node_id}"
                    )
                    effective_status = "not_established"
                    effective_values_sha256 = None
                resolved_inputs.append(
                    CalibrationResolvedParameterInput.model_validate(
                        {
                            **parameter_input.model_dump(mode="python"),
                            "parameter_ids": tuple(mechanism_spec.params),
                            "effective_parameter_values_sha256": effective_values_sha256,
                            "effective_values_status": effective_status,
                        }
                    )
                )
            capture["parameter_inputs"] = resolved_inputs
        config_ref = selected_config_ref or put_calibration_config(
            store,
            basis_config,
            return_selected_profile=True,
        )
        basis_ref = _persist_calibration_execution_basis(
            store,
            inputs=replace(basis_inputs, config=basis_config),
            config_ref=config_ref,
            report=report,
            capture=capture,
        )
        report_ref = put_calibration_report(
            store,
            report,
            inputs=[
                input_ref_from_artifact_ref(config_ref, role="calibration_config"),
                input_ref_from_artifact_ref(
                    basis_ref,
                    role="calibration_execution_input_basis",
                ),
            ],
        )
        return report, report_ref

    @_track_calibration_lifecycle
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
        batch_profile = self.inputs.ordered_batch_profile
        if batch_profile is not None:
            if len(targets) != 1:
                raise ValueError("ordered_batch_profile supports exactly one target")
            target = targets[0]
            if path_by_target[target.target_id] != batch_profile.target_path:
                raise ValueError("ordered_batch_profile target_path must match configured target")
            if (
                target.loss.kind != "mse"
                or target.loss.relative
                or target.aggregation != "none"
                or cfg.grad_norm.enabled
                or cfg.prior_loss.enabled
                or self.inputs.measurement_bundle is not None
                or self.inputs.controls_seq is not None
                or self.inputs.aux_loss_components
                or self.inputs.measurement_loss_adapter is not None
                or self.inputs.measurement_loss_config is not None
                or self.inputs.raw_targets
                or self.inputs.udf_engine is not None
                or self.inputs.target_fetcher is not None
                or target.fabric_query is not None
                or target.fabric_metric is not None
                or target.align != TargetAlignConfig()
                or cfg.seed_strategy != "fixed"
                or cfg.multi_start is not None
                or cfg.constraint_loss.enabled
            ):
                raise ValueError(
                    "ordered_batch_profile supports one absolute MSE target without "
                    "GradNorm, priors, measurements, controls, or auxiliary losses"
                )
            if self._resolve_constraints():
                raise ValueError("ordered_batch_profile does not support constraints")
            # Eager preflight validates structure and numeric support before the
            # optimizer allocates a transformed graph.
            _ordered_batch_parameter_dtype(batch_profile, bundle)
            initial_batch = evaluate_ordered_batch_objective(
                batch_profile, bundle=bundle, loss_config=target.loss
            )
            with np.errstate(over="ignore", under="ignore", invalid="ignore"):
                effective_priority = np.asarray(target.loss.weight, dtype=np.float32)
            if not np.isfinite(effective_priority) or effective_priority <= 0:
                raise ValueError(
                    "ordered_batch_profile requires positive finite effective target priority"
                )
            rows = len(batch_profile.row_ids)
            if cfg.steps not in (None, rows):
                raise ValueError("ordered_batch_profile steps must equal its row count")
            if cfg.time_axis is not None and list(cfg.time_axis) != [
                float(t) for t in batch_profile.row_times
            ]:
                raise ValueError("ordered_batch_profile forbids target resampling or reordering")
            if not bool(initial_batch.valid):
                raise ValueError("ordered_batch_profile has invalid numeric support or prediction")
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
        scale_support: dict[str, bool] = {}
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

        if batch_profile is not None:
            target_id = targets[0].target_id
            steps = len(batch_profile.row_ids)
            aligned_targets = {target_id: batch_profile.targets}
            scales = {target_id: 1.0}
            time_axes = {target_id: [float(t) for t in batch_profile.row_times]}
            fetched_target_ids: set[str] = set()
        elif measurement_bundle is None:
            fetched_target_ids = set()
            if self.inputs.raw_targets:
                raw_targets.update(self.inputs.raw_targets)
            if any(t.fabric_query is not None for t in targets):
                if self.inputs.udf_engine is not None or self.inputs.target_fetcher is not None:
                    fetched = fetch_targets(
                        cfg,
                        udf_engine=self.inputs.udf_engine,
                        fetcher=self.inputs.target_fetcher,
                    )
                    raw_targets = {**fetched, **raw_targets}
                    fetched_target_ids = set(fetched)
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
            scales: dict[str, float] = {}
            for target in targets:
                target_id = target.target_id
                coverage = jnp.asarray(
                    measurement_bundle.coverage_estimate[target_id], dtype=jnp.float32
                )
                if coverage.shape != aligned_targets[target_id].shape:
                    raise ValueError(
                        "Coverage mask must match target shape: "
                        f"target={aligned_targets[target_id].shape}, coverage={coverage.shape}"
                    )
                observed_mask = (coverage > 0.0) & jnp.isfinite(aligned_targets[target_id])
                labels = measurement_bundle.split_label.get(target_id)
                if labels is None:
                    training_mask = jnp.ones_like(observed_mask, dtype=bool)
                else:
                    if observed_mask.ndim != 1 or len(labels) != int(observed_mask.shape[0]):
                        raise ValueError(
                            f"Training split for target '{target_id}' does not match target shape"
                        )
                    training_mask = jnp.asarray(
                        [getattr(label, "value", label) == "train" for label in labels],
                        dtype=bool,
                    )
                if training_mask.shape != observed_mask.shape:
                    raise ValueError(
                        f"Training split for target '{target_id}' does not match target shape"
                    )
                scales[target_id] = _compute_scale_local(
                    aligned_targets[target_id],
                    target,
                    observed_mask=observed_mask,
                    training_mask=training_mask,
                )
                scale_support[target_id] = bool(np.any(np.asarray(observed_mask & training_mask)))
                if not scale_support[target_id]:
                    diagnostics.append(f"no_training_scale_support:{target_id}")
            time_axes = {
                target.target_id: _measurement_time_axis(
                    measurement_bundle.time_axis.get(target.target_id)
                )
                for target in targets
            }

        if self._execution_capture is not None:
            raw_target_ids = set(self.inputs.raw_targets or {})
            target_source_kinds: dict[str, str] = {}
            for target in targets:
                target_id = target.target_id
                if batch_profile is not None:
                    source_kind = "ordered_batch_profile"
                elif measurement_bundle is not None and target_id in aligned_targets:
                    source_kind = "measurement_bundle"
                elif target_id in raw_target_ids:
                    source_kind = "caller_raw_targets"
                elif target_id in locals().get("fetched_target_ids", set()):
                    source_kind = "target_fetcher_or_udf"
                else:
                    source_kind = "mixed_or_unknown"
                target_source_kinds[target_id] = source_kind
            self._execution_capture["target_source_kinds"] = target_source_kinds
            self._execution_capture["target_values"] = {
                target.target_id: _as_float_list(aligned_targets[target.target_id])
                for target in targets
            }
            self._execution_capture["report_time_axes"] = {
                target.target_id: time_axes.get(target.target_id) for target in targets
            }

        measurement_support: dict[str, bool] = {}
        if measurement_bundle is not None:
            for target in targets:
                target_id = target.target_id
                adapted = measurement_adapter.adapt(
                    targets=(measurement_targets[target_id],),
                    base_weights=1.0,
                    trust_weight=measurement_bundle.trust_weight[target_id],
                    coverage_estimate=measurement_bundle.coverage_estimate[target_id],
                    censoring_mask=measurement_bundle.censoring_mask.get(target_id),
                    lag_days_estimate=measurement_bundle.lag_days_estimate.get(target_id),
                    schema_regime_id=measurement_bundle.schema_regime_id.get(target_id),
                    shock_mask=measurement_bundle.shock_mask.get(target_id),
                    identification_mode=measurement_bundle.identification_mode.get(target_id),
                    config=measurement_config,
                )
                quality = adapted.get("sample_quality_weight", adapted["effective_weight"])
                quality_arr = np.asarray(quality, dtype=float)
                if quality_arr.shape != np.asarray(aligned_targets[target_id]).shape:
                    raise ValueError(
                        "Measurement quality weights must match target shape: "
                        f"target={np.asarray(aligned_targets[target_id]).shape}, "
                        f"weights={quality_arr.shape}"
                    )
                measurement_support[target_id] = bool(
                    np.any(np.isfinite(quality_arr) & (quality_arr > 0.0))
                )
                if not measurement_support[target_id]:
                    diagnostics.append(f"no_effective_support:{target_id}")
            if not any(measurement_support.values()):
                raise ValueError("Calibration blocked: no_effective_support for any target")

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
            value = jnp.mean(stacked, axis=0)
            if batch_profile is not None:
                value = jnp.asarray(
                    value, dtype=_ordered_batch_parameter_dtype(batch_profile, bundle)
                )
            group_values.append(value)
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
        collector = _current_calibration_metrics_collector.get()
        if collector is None:
            raise RuntimeError("Calibration lifecycle wrapper is missing")
        optimizer_name = collector.optimizer_name
        hpc_enabled = collector.enabled
        tracer = get_tracer() if hpc_enabled else None
        span_attributes = {
            "calibration.optimizer": optimizer_name,
            "calibration.max_steps": cfg.max_steps,
            "calibration.learning_rate": cfg.learning_rate,
            "calibration.early_stop_patience": cfg.early_stop_patience,
            "calibration.run_id": collector.run_id,
        }

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
        batch_objective_identity = (
            canonical_input_sha256({"profile": batch_profile, "config": cfg})
            if batch_profile is not None
            else None
        )

        def _execute_forward(sim_bundle: StaticBundle, step_idx: jax.Array):
            if batch_profile is not None:
                evaluation = evaluate_ordered_batch_objective(
                    batch_profile,
                    bundle=sim_bundle,
                    loss_config=targets[0].loss,
                )
                return {
                    batch_profile.target_path: evaluation.predictions,
                    "__ordered_batch_valid__": evaluation.valid,
                }
            _, traces = run_pure_scan(
                self.inputs.base_state,
                steps=steps,
                root_key=_root_key(step_idx),
                bundle=sim_bundle,
                metric_paths=metric_paths,
                controls_seq=self.inputs.controls_seq,
            )
            return traces

        def _target_loss_vec(
            u: Sequence[jnp.ndarray],
            step_idx: jax.Array,
        ) -> jnp.ndarray:
            theta_groups = from_unconstrained(u, group_bijectors)
            theta = _expand_group_values(theta_groups)
            sim_bundle = apply_trainable_values(bundle, theta)
            traces = _execute_forward(sim_bundle, step_idx)
            return _base_vec_from_traces(traces)

        def _base_vec_from_traces(
            traces: Mapping[str, jnp.ndarray],
        ) -> jnp.ndarray:
            if batch_profile is not None:
                value, valid = _ordered_batch_loss(
                    jnp.asarray(traces[batch_profile.target_path]), batch_profile, targets[0].loss
                )
                valid = valid & traces["__ordered_batch_valid__"]
                return jnp.asarray([jnp.where(valid, value, jnp.inf)])
            losses = []
            for target in targets:
                trace = traces[path_by_target[target.target_id]]
                predicted = _apply_aggregation(trace, target.aggregation)
                cfg_loss = loss_configs[target.target_id]
                scale = scales.get(target.target_id, 1.0) if cfg_loss.relative else 1.0
                if not measurement_enabled:
                    losses.append(
                        compute_base_loss(
                            predicted,
                            aligned_targets[target.target_id],
                            cfg_loss,
                            scale,
                        )
                    )
                    continue

                pointwise = pointwise_base_loss(
                    predicted,
                    aligned_targets[target.target_id],
                    cfg_loss,
                    scale,
                )
                adapted = measurement_adapter.adapt(
                    targets=(measurement_targets[target.target_id],),
                    # Sample-quality is normalized within the target.  The
                    # inter-target priority is applied by ``loss_fn`` after
                    # this reduction so it cannot cancel in the denominator.
                    base_weights=1.0,
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
                sample_quality = adapted.get("sample_quality_weight", adapted["effective_weight"])
                losses.append(
                    reduce_weighted_loss(
                        pointwise,
                        sample_quality,
                        epsilon=cfg_loss.epsilon,
                    )
                )
            if not losses:
                return jnp.zeros((0,), dtype=jnp.float32)
            return jnp.stack(losses)

        def _forward_evaluation(
            u_state: Sequence[jnp.ndarray],
            weights_state: jnp.ndarray,
            step_idx: jax.Array,
        ) -> tuple[
            jnp.ndarray,
            jnp.ndarray,
            Mapping[str, jnp.ndarray],
            jnp.ndarray,
            jnp.ndarray,
            jnp.ndarray,
        ]:
            """Run one parameter-connected forward and derive all loss views.

            The returned traces remain connected to ``u_state``.  This helper
            is used by the differentiable loss path as well as final report
            projection, so report projections do not need to launch separate
            scans for the target losses, total loss, and series data.
            """
            theta_groups = from_unconstrained(u_state, group_bijectors)
            theta = _expand_group_values(theta_groups)
            sim_bundle = apply_trainable_values(bundle, theta)
            traces = _execute_forward(sim_bundle, step_idx)
            base_vec = _base_vec_from_traces(traces)
            total = jnp.sum(base_vec * weights_state) if base_vec.size else jnp.array(0.0)
            constraint_penalty = _constraint_penalty(traces)
            prior_penalty = _prior_penalty(theta_groups)
            aux_penalty = _aux_penalty(traces)
            total = total + constraint_penalty + prior_penalty + aux_penalty
            return (
                total,
                base_vec,
                traces,
                constraint_penalty,
                prior_penalty,
                aux_penalty,
            )

        def _tree_is_finite(tree: Any) -> jnp.ndarray:
            leaves = jax.tree_util.tree_leaves(tree)
            finite = jnp.array(True)
            for leaf in leaves:
                finite = finite & jnp.all(jnp.isfinite(leaf))
            return finite

        def loss_fn(u: Sequence[jnp.ndarray], weights_vec: jnp.ndarray, step_idx: jax.Array):
            (
                total,
                base_vec,
                _traces,
                constraint_penalty,
                prior_penalty,
                aux_penalty,
            ) = _forward_evaluation(u, weights_vec, step_idx)
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
            return (
                new_u,
                weights_state,
                new_opt_state,
                loss_val,
                aux,
                grad_norm,
                grads_finite,
            )

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
                )
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
        ) -> tuple[HessianResult | None, Any | None, list[str], _HessianReuseKey | None]:
            if not cfg.hessian.enabled:
                return None, None, [], None
            flat_theta, unravel_theta = ravel_pytree(theta_groups)
            n_params = int(flat_theta.size)
            if n_params == 0:
                return None, None, ["Hessian skipped: no parameters"], None
            if cfg.hessian.max_params is not None and n_params > cfg.hessian.max_params:
                return (
                    None,
                    None,
                    [
                        f"Hessian skipped: parameter count {n_params} exceeds {cfg.hessian.max_params}"
                    ],
                    None,
                )

            param_names = _param_names_for_groups(theta_groups)
            reuse_key = _make_hessian_reuse_key(
                flat_theta,
                param_names,
                weights_vec,
                cfg,
                steps=steps,
                objective_input_sha256=batch_objective_identity,
            )

            def _loss_from_flat(flat_params: jnp.ndarray) -> jnp.ndarray:
                theta_groups_local = unravel_theta(flat_params)
                theta = _expand_group_values(theta_groups_local)
                sim_bundle = apply_trainable_values(bundle, theta)
                traces_local = _execute_forward(sim_bundle, jnp.array(0, dtype=jnp.int32))
                base_vec = _base_vec_from_traces(
                    traces_local,
                )
                total = jnp.sum(base_vec * weights_vec) if base_vec.size else jnp.array(0.0)
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
                return None, None, [f"Hessian computation failed: {exc}"], reuse_key

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
            return hessian_result, identifiability_report, local_diagnostics, reuse_key

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

            with _calibration_span_context(
                tracer,
                span_attributes,
                start_index=_start_idx,
            ) as span:
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

            # The optimizer evaluates ``prev_u_state`` before producing the
            # next state.  Evaluate that last produced state on the same
            # designated final replica before allowing it to replace the
            # historical best.  If GradNorm changed the weights, re-evaluate
            # the historical state with those same final weights so the two
            # objectives remain comparable.
            final_step_idx = jnp.array(0, dtype=jnp.int32)
            candidate_forward: (
                tuple[
                    jnp.ndarray,
                    jnp.ndarray,
                    Mapping[str, jnp.ndarray],
                    jnp.ndarray,
                    jnp.ndarray,
                    jnp.ndarray,
                ]
                | None
            ) = None
            candidate_loss = float("inf")
            try:
                candidate_forward = _forward_evaluation(
                    u_state,
                    weights_state,
                    final_step_idx,
                )
                candidate_loss = float(candidate_forward[0])
            except (FloatingPointError, RuntimeError, TypeError, ValueError) as exc:
                _ms_diagnostics.append(f"Last iterate evaluation failed: {exc}")

            weights_comparable = np.array_equal(
                np.asarray(best_weights_state),
                np.asarray(weights_state),
                equal_nan=True,
            )
            baseline_loss = best_eval_loss
            baseline_forward: (
                tuple[
                    jnp.ndarray,
                    jnp.ndarray,
                    Mapping[str, jnp.ndarray],
                    jnp.ndarray,
                    jnp.ndarray,
                    jnp.ndarray,
                ]
                | None
            ) = None
            if np.isfinite(best_eval_loss) and (
                not weights_comparable or cfg.seed_strategy == "step"
            ):
                try:
                    baseline_forward = _forward_evaluation(
                        best_u_state,
                        weights_state,
                        final_step_idx,
                    )
                    baseline_loss = float(baseline_forward[0])
                except (FloatingPointError, RuntimeError, TypeError, ValueError) as exc:
                    _ms_diagnostics.append(f"Historical best re-evaluation failed: {exc}")
                    baseline_loss = float("inf")

            selected_loss, selected_state = _select_lower_loss_state(
                previous_loss=baseline_loss,
                previous_state=best_u_state,
                candidate_loss=candidate_loss,
                candidate_state=u_state,
            )
            candidate_selected = np.isfinite(candidate_loss) and (
                not np.isfinite(baseline_loss) or candidate_loss < baseline_loss
            )
            run_u_state = selected_state
            run_weights_state = weights_state
            final_loss = selected_loss
            selected_forward = candidate_forward if candidate_selected else baseline_forward
            if candidate_selected:
                _ms_diagnostics.append("Last produced iterate admitted after comparable evaluation")
            run_hessian_result = None
            run_identifiability = None
            run_hessian_key: _HessianReuseKey | None = None
            if len(start_points) > 1 and cfg.hessian.enabled:
                theta_groups_run = from_unconstrained(run_u_state, group_bijectors)
                (
                    run_hessian_result,
                    run_identifiability,
                    hessian_diags,
                    run_hessian_key,
                ) = _compute_run_hessian_summary(
                    theta_groups_run,
                    run_weights_state,
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
                    "hessian_reuse_key": run_hessian_key,
                    "forward": selected_forward,
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

        final_forward = selected_run.get("forward")
        if final_forward is None:
            final_forward = _forward_evaluation(
                u_state,
                weights_state,
                jnp.array(0, dtype=jnp.int32),
            )
        final_total_loss_jax, final_target_losses, traces, _, _, _ = final_forward
        per_target_final = {
            tid: float(final_target_losses[idx] * weights_state[idx])
            for idx, tid in enumerate(target_ids)
        }
        target_weights = {tid: float(weights_state[idx]) for idx, tid in enumerate(target_ids)}
        final_total_loss = float(final_total_loss_jax)
        series_comparison: dict[str, CalibrationSeriesComparison] = {}
        per_target_metrics: dict[str, CalibrationFitMetrics] = {}
        all_real: list[np.ndarray] = []
        all_model: list[np.ndarray] = []

        def _fit_metrics(
            model_series: Any, real_series: Any, row_weights: Any | None = None
        ) -> CalibrationFitMetrics:
            model_arr = np.asarray(model_series, dtype=float).reshape(-1)
            real_arr = np.asarray(real_series, dtype=float).reshape(-1)
            if model_arr.size == 0 or real_arr.size == 0:
                return CalibrationFitMetrics(mse=0.0, rmse=0.0, mae=0.0, r2=None, n=0)
            diff = model_arr - real_arr
            if row_weights is not None:
                return ordered_batch_fit_metrics(model_series, real_series, row_weights)
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
            per_target_metrics[target_id] = _fit_metrics(
                model_list,
                real_list,
                batch_profile.weights if batch_profile is not None else None,
            )
            if real_list:
                all_real.append(np.asarray(real_list, dtype=float))
                all_model.append(np.asarray(model_list, dtype=float))

        aggregate_metrics = None
        if batch_profile is not None:
            aggregate_metrics = per_target_metrics[targets[0].target_id]
        elif all_real:
            aggregate_metrics = _fit_metrics(np.concatenate(all_model), np.concatenate(all_real))
        fit_quality = CalibrationFitQuality(
            per_target=per_target_metrics,
            aggregate=aggregate_metrics,
        )

        uncertainties: CalibrationUncertainty | None = None
        hessian_result: HessianResult | None = None
        identifiability_report = None
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
                param_names = _param_names_for_groups(final_theta_groups)
                if len(param_names) != n_params:
                    diagnostics.append("Hessian param naming mismatch; using generic names")
                    param_names = [f"param_{idx}" for idx in range(n_params)]

                final_hessian_key = _make_hessian_reuse_key(
                    flat_theta,
                    param_names,
                    weights_state,
                    cfg,
                    steps=steps,
                    objective_input_sha256=batch_objective_identity,
                )
                cached_hessian = selected_run.get("hessian_result")
                cached_hessian_key = selected_run.get("hessian_reuse_key")
                reused_hessian = cached_hessian is not None and _hessian_reuse_key_matches(
                    cached_hessian_key,
                    final_hessian_key,
                )
                if reused_hessian:
                    hessian_result = cached_hessian
                    identifiability_report = selected_run.get("identifiability")
                    diagnostics.append("Hessian reused from selected start")
                else:

                    def _loss_from_flat(flat_params: jnp.ndarray) -> jnp.ndarray:
                        theta_groups = unravel_theta(flat_params)
                        theta = _expand_group_values(theta_groups)
                        sim_bundle = apply_trainable_values(bundle, theta)
                        traces_local = _execute_forward(sim_bundle, jnp.array(0, dtype=jnp.int32))
                        base_vec = _base_vec_from_traces(
                            traces_local,
                        )
                        total = (
                            jnp.sum(base_vec * weights_state) if base_vec.size else jnp.array(0.0)
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
                    except (
                        FloatingPointError,
                        RuntimeError,
                        TypeError,
                        ValueError,
                    ) as exc:  # pragma: no cover - defensive
                        diagnostics.append(f"Hessian computation failed: {exc}")

                if hessian_result is not None:
                    hr = hessian_result
                    n_p = len(hr.param_names)

                    # Build correlation from covariance
                    cov_jnp = jnp.asarray(hr.covariance)
                    std_jnp = jnp.asarray(hr.std)
                    denom = (std_jnp[:, None] * std_jnp[None, :]) + cfg.hessian.rank_tol
                    corr = cov_jnp / denom
                    if n_p > 0:
                        corr = corr.at[jnp.diag_indices(n_p)].set(1.0)

                    if batch_profile is not None and hr.raw_eigenvalues is not None:
                        rank = int(np.sum(np.abs(hr.raw_eigenvalues) > cfg.hessian.rank_tol))
                    else:
                        # Preserve the legacy scalar report's repaired-rank projection.
                        sv = jnp.linalg.svd(jnp.asarray(hr.hessian), compute_uv=False)
                        rank = int(jnp.sum(sv > cfg.hessian.rank_tol))

                    non_identifiable: list[str] = []
                    for idx, value in enumerate(hr.std):
                        if not np.isfinite(value) or value > cfg.hessian.std_warn:
                            non_identifiable.append(hr.param_names[idx])

                    condition = hr.condition_number
                    if batch_profile is not None and not np.isfinite(condition):
                        diagnostics.append("ordered_batch_hessian_condition_non_finite")
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

        if hessian_result is not None and identifiability_report is None:
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
        coordinate_projection = None
        coordinate_projection_status: Literal[
            "complete", "incomplete", "unsupported", "not_established"
        ] = "not_established"
        if uncertainties is not None:
            coordinate_names = tuple(uncertainties.params)
            scalar_group_names = tuple(group.group_id for group in groups)
            if (
                len(coordinate_names) == len(groups)
                and coordinate_names == scalar_group_names
                and all(np.asarray(value).size == 1 for value in final_theta_groups)
            ):
                group_by_handle = {
                    handle_idx: group_idx
                    for group_idx, group in enumerate(groups)
                    for handle_idx in group.handle_indices
                }
                complete_handle_map = set(group_by_handle) == set(
                    range(len(final_bundle.trainables))
                ) and len(group_by_handle) == sum(len(group.handle_indices) for group in groups)
                if not complete_handle_map:
                    diagnostics.append("coordinate_projection_incomplete_unassigned_fields")
                    coordinate_projection_status = "incomplete"
                else:
                    field_order: list[str] = []
                    projection_rows: list[tuple[float, ...]] = []
                    for handle_idx, handle in enumerate(final_bundle.trainables):
                        group_idx = group_by_handle[handle_idx]
                        field_name = (
                            f"{final_bundle.nodes[handle.node_index].node_id}.{handle.field_name}"
                        )
                        row = tuple(
                            1.0 if column_idx == group_idx else 0.0
                            for column_idx in range(len(coordinate_names))
                        )
                        field_order.append(field_name)
                        projection_rows.append(row)
                    if (
                        len(field_order) == len(set(field_order))
                        and set(field_order) == set(calibrated_params)
                        and field_order
                    ):
                        coordinate_projection = CalibrationCoordinateProjection(
                            field_order=tuple(field_order),
                            coordinate_order=coordinate_names,
                            matrix=tuple(projection_rows),
                        )
                        coordinate_projection_status = "complete"
                    else:
                        diagnostics.append("coordinate_projection_unsupported_field_identity")
                        coordinate_projection_status = "unsupported"
            elif groups:
                diagnostics.append("coordinate_projection_unsupported_coordinate_shape")
                coordinate_projection_status = "unsupported"

        if batch_profile is not None:
            diagnostics.append(
                "ordered_batch_inference_unavailable:generic_weighted_mse_curvature_only"
            )
        selected_input_ref = (
            self._execution_capture.get("ordered_input_ref")
            if self._execution_capture is not None
            else None
        )
        report = CalibrationReport(
            schema_version="2.1" if batch_profile is not None else "2.0",
            ordered_batch_execution=(
                CalibrationOrderedBatchReport(
                    consumed_profile_sha256=canonical_input_sha256(batch_profile),
                    selected_input_ref=selected_input_ref,
                    input_status=(
                        "selected_input_consumed"
                        if selected_input_ref is not None
                        else "in_memory_input_only"
                    ),
                )
                if batch_profile is not None
                else None
            ),
            calibrated_params=calibrated_params,
            total_loss=final_total_loss,
            per_target_loss=per_target_final,
            target_weights=target_weights,
            loss_history=loss_history,
            grad_norm_history=grad_norm_history,
            series_comparison=series_comparison,
            fit_quality=fit_quality,
            uncertainties=uncertainties,
            coordinate_projection=coordinate_projection,
            coordinate_projection_status=coordinate_projection_status,
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
                "support_status": {
                    target_id: (
                        "supported" if measurement_support.get(target_id, True) else "no_support"
                    )
                    for target_id in target_ids
                },
                "scale_support": {
                    target_id: (
                        "supported" if scale_support.get(target_id, True) else "no_training_support"
                    )
                    for target_id in target_ids
                },
            },
        )
        if batch_profile is not None:
            report.execution_context["ordered_batch"] = {
                "profile_kind": "ordered_scalar_mse_v1",
                "objective_kind": "generic_weighted_mse_curvature_only",
                "inference_status": "unavailable_generic_loss",
                "objective_input_sha256": batch_objective_identity,
                "parameter_compute_dtype": str(
                    _ordered_batch_parameter_dtype(batch_profile, bundle)
                ),
                "fit_metric_scope": "positive_weight_rows_with_declared_row_weights",
                "hessian": (
                    {
                        "raw_eigenvalues": (
                            _as_float_list(hessian_result.raw_eigenvalues)
                            if hessian_result.raw_eigenvalues is not None
                            else None
                        ),
                        "condition_status": (
                            "finite"
                            if np.isfinite(hessian_result.condition_number)
                            else "non_finite"
                        ),
                        "n_repaired": hessian_result.n_repaired,
                        "source_dtype": hessian_result.source_dtype,
                        "strategy": hessian_result.strategy,
                        "fallback_cause": hessian_result.fallback_cause,
                        "finite_difference_convergence": (
                            "not_established"
                            if hessian_result.strategy == "finite_diff"
                            else "not_applicable"
                        ),
                    }
                    if hessian_result is not None
                    else None
                ),
            }
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
