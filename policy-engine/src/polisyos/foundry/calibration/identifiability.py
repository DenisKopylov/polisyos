"""Identifiability diagnostics via Hessian eigenstructure."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from math import isfinite
from numbers import Real
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    FeedbackConfigRef,
    FoundryExecConfig,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    IdentifiabilityDiagnosticRef,
    Metrics,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.ir.analytics.phase4_dynamics import build_abm_result_from_simulation
from polisyos.ir.refs import ABMResultRef

if TYPE_CHECKING:
    from polisyos.foundry.calibration.hessian import HessianResult
else:  # pragma: no cover - import guard for environments without JAX
    HessianResult = Any

SummaryEvaluator = Callable[[Mapping[str, float], int | None], Mapping[str, float]]


class IdentifiabilityStatus(str, Enum):
    """Per-parameter identifiability classification."""

    IDENTIFIED = "identified"
    SLOPPY = "sloppy"
    NON_IDENTIFIED = "non_identified"


class ParamIdentifiability(BaseModel):
    """Identifiability diagnostic for a single parameter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: IdentifiabilityStatus
    eigenvalue: float
    std: float


class IdentifiabilityReport(BaseModel):
    """Aggregate identifiability diagnostics for all calibrated parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    params: list[ParamIdentifiability] = Field(default_factory=list)
    n_identified: int = 0
    n_sloppy: int = 0
    n_non_identified: int = 0
    effective_dimension: int = 0


def diagnose_identifiability(
    hessian_result: HessianResult,
    *,
    identified_threshold: float = 1e-3,
    sloppy_threshold: float = 1e-8,
) -> IdentifiabilityReport:
    """Check parameter identifiability via Hessian eigenstructure.

    Per-parameter classification based on the diagonal of H (which reflects
    the curvature of the loss w.r.t. each parameter):
      - identified:     eigenvalue contribution > *identified_threshold*
      - sloppy:         eigenvalue contribution in (*sloppy_threshold*, *identified_threshold*]
      - non_identified: eigenvalue contribution <= *sloppy_threshold*
    """
    n = len(hessian_result.param_names)
    hessian_diag = np.diag(hessian_result.hessian)

    params: list[ParamIdentifiability] = []
    n_identified = 0
    n_sloppy = 0
    n_non_identified = 0

    for i in range(n):
        ev = float(hessian_diag[i])
        std_i = float(hessian_result.std[i])

        if ev > identified_threshold:
            status = IdentifiabilityStatus.IDENTIFIED
            n_identified += 1
        elif ev > sloppy_threshold:
            status = IdentifiabilityStatus.SLOPPY
            n_sloppy += 1
        else:
            status = IdentifiabilityStatus.NON_IDENTIFIED
            n_non_identified += 1

        params.append(
            ParamIdentifiability(
                name=hessian_result.param_names[i],
                status=status,
                eigenvalue=ev,
                std=std_i,
            )
        )

    effective_dimension = int(np.sum(hessian_result.eigenvalues > sloppy_threshold))

    return IdentifiabilityReport(
        params=params,
        n_identified=n_identified,
        n_sloppy=n_sloppy,
        n_non_identified=n_non_identified,
        effective_dimension=effective_dimension,
    )


class IdentifiabilityMomentClass(str, Enum):
    """Summary-statistic family used by an aggregate identifiability diagnostic."""

    MEAN_VARIANCE = "mean_variance"
    QUANTILES = "quantiles"
    COMBINED = "combined"


class IdentifiabilityDiagnosticStatus(str, Enum):
    """Run-level aggregate-moment identifiability classification."""

    IDENTIFIED = "identified"
    SLOPPY = "sloppy"
    NON_IDENTIFIED = "non_identified"
    INCONCLUSIVE = "inconclusive"
    NUMERIC_FAILURE = "numeric_failure"


class IdentifiabilityDiagnosticConfig(BaseModel):
    """Controls local aggregate-moment identifiability diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quantiles: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 0.90)
    simulation_reps: int = Field(default=32, ge=1)
    bootstrap_reps: int = Field(default=128, ge=0)
    profile_grid_size: int = Field(default=21, ge=0)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    ridge: float = Field(default=1e-8, gt=0.0)
    finite_diff_rel_step: float = Field(default=1e-4, gt=0.0)
    use_common_random_numbers: bool = True
    rank_tol: float = Field(default=1e-8, ge=0.0)
    sloppy_eigen_tol: float = Field(default=1e-3, ge=0.0)
    condition_warn_threshold: float = Field(default=1e6, gt=0.0)
    condition_block_threshold: float = Field(default=1e10, gt=0.0)
    bootstrap_rank_stability_warn: float = Field(default=0.75, ge=0.0, le=1.0)
    persist_profiles: bool = True
    persist_sensitivity_matrix: bool = True
    allow_underidentified: bool = False
    profile_rel_radius: float = Field(default=0.25, gt=0.0)
    profile_optimize_nuisance: bool = True
    profile_nuisance_grid_size: int = Field(default=3, ge=1)
    profile_nuisance_refinements: int = Field(default=1, ge=0)
    seed: int | None = None

    @field_validator("quantiles")
    @classmethod
    def _validate_quantiles(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        quantiles = tuple(float(item) for item in value)
        if any(not 0.0 < item < 1.0 for item in quantiles):
            raise ValueError("quantiles must be strictly inside (0, 1)")
        if tuple(sorted(quantiles)) != quantiles or len(set(quantiles)) != len(quantiles):
            raise ValueError("quantiles must be unique and sorted ascending")
        return quantiles


_DEFAULT_IDENTIFIABILITY_DIAGNOSTIC_CONFIG = IdentifiabilityDiagnosticConfig()
_DEFAULT_IDENTIFIABILITY_QUANTILES = _DEFAULT_IDENTIFIABILITY_DIAGNOSTIC_CONFIG.quantiles


class IdentifiabilityDiagnosticResult(BaseModel):
    """Persistable aggregate-moment identifiability sidecar payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    status: IdentifiabilityDiagnosticStatus
    moment_classes: tuple[IdentifiabilityMomentClass, ...]
    parameter_names: tuple[str, ...]
    effective_dimension: int | None = Field(default=None, ge=0)
    jacobian_rank: int | None = Field(default=None, ge=0)
    fisher_eigenvalues: tuple[float, ...] = ()
    condition_number: float | None = Field(default=None, ge=0.0)
    min_eigenvalue: float | None = Field(default=None, ge=0.0)
    sloppy_directions: tuple[dict[str, Any], ...] = ()
    profile_intervals: dict[str, tuple[float, float] | None] = Field(default_factory=dict)
    profile_hit_boundary: dict[str, bool] = Field(default_factory=dict)
    bootstrap_rank_stability: float | None = None
    bootstrap_min_eigen_ci: tuple[float, float] | None = None
    observed_moments: dict[str, float] = Field(default_factory=dict)
    fitted_moments: dict[str, float] = Field(default_factory=dict)
    alias_groups: tuple[tuple[str, ...], ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    sensitivity_matrix_ref: ArtifactRef | None = None
    profile_trace_ref: ArtifactRef | None = None
    diagnostic_ref: IdentifiabilityDiagnosticRef | None = Field(default=None, exclude=True)


def identifiability_diagnostic(
    store: FileSystemCAS,
    *,
    simulation_result_ref: SimulationResultRef,
    observed_moment_bundle: Mapping[str, float] | ArtifactRef,
    parameter_center: Mapping[str, Any] | ArtifactRef | None = None,
    config: IdentifiabilityDiagnosticConfig = _DEFAULT_IDENTIFIABILITY_DIAGNOSTIC_CONFIG,
    summary_evaluator: SummaryEvaluator | None = None,
    moment_names: Sequence[str] | None = None,
    parameter_bounds: Mapping[str, tuple[float, float]] | None = None,
) -> IdentifiabilityDiagnosticResult:
    """Compute and persist aggregate-moment identifiability diagnostics.

    `summary_evaluator` maps a parameter vector plus optional seed to simulated
    summary statistics. If it is omitted, the function attempts a conservative
    execute-backed replay using `node_id.parameter` keys from `parameter_center`.
    """

    sim_ref = SimulationResultRef.model_validate(simulation_result_ref.model_dump(mode="python"))
    simulation_result = _load_model(store, sim_ref, SimulationResult)
    observed_ref = (
        observed_moment_bundle if isinstance(observed_moment_bundle, ArtifactRef) else None
    )
    parameter_ref = parameter_center if isinstance(parameter_center, ArtifactRef) else None

    observed = _resolve_float_mapping(store, observed_moment_bundle, label="observed_moment_bundle")
    center = _resolve_parameter_center(store, sim_ref, parameter_center)
    if not center:
        raise ValueError("parameter_center is required for local identifiability diagnostics")

    names = tuple(str(name) for name in (moment_names or observed.keys()))
    missing = [name for name in names if name not in observed]
    if missing:
        raise ValueError(f"observed_moment_bundle is missing requested moments: {missing}")
    observed = {name: float(observed[name]) for name in names}
    parameter_names = tuple(center.keys())
    moment_classes = _infer_moment_classes(names)

    if len(names) < len(parameter_names) and not config.allow_underidentified:
        result = IdentifiabilityDiagnosticResult(
            status=IdentifiabilityDiagnosticStatus.NON_IDENTIFIED,
            moment_classes=moment_classes,
            parameter_names=parameter_names,
            effective_dimension=len(names),
            jacobian_rank=len(names),
            observed_moments=observed,
            blocking_reasons=(
                f"underidentified_summary_vector:{len(names)}<parameters:{len(parameter_names)}",
            ),
            metadata=_base_metadata(config, names),
        )
        return _persist_diagnostic_result(
            store,
            result,
            simulation_result_ref=sim_ref,
            observed_ref=observed_ref,
            parameter_ref=parameter_ref,
        )

    if summary_evaluator is None:
        try:
            summary_evaluator = _build_execute_summary_evaluator(
                store,
                simulation_result_ref=sim_ref,
                simulation_result=simulation_result,
            )
        except Exception as exc:
            result = IdentifiabilityDiagnosticResult(
                status=IdentifiabilityDiagnosticStatus.INCONCLUSIVE,
                moment_classes=moment_classes,
                parameter_names=parameter_names,
                observed_moments=observed,
                warnings=(f"summary_evaluator_unavailable:{type(exc).__name__}:{exc}",),
                blocking_reasons=("summary_evaluator_required_for_local_jacobian",),
                metadata=_base_metadata(config, names),
            )
            return _persist_diagnostic_result(
                store,
                result,
                simulation_result_ref=sim_ref,
                observed_ref=observed_ref,
                parameter_ref=parameter_ref,
            )

    try:
        result = _compute_identifiability_diagnostic(
            store,
            summary_evaluator=summary_evaluator,
            observed=observed,
            center=center,
            config=config,
            moment_classes=moment_classes,
            parameter_bounds=parameter_bounds or {},
        )
    except Exception as exc:
        result = IdentifiabilityDiagnosticResult(
            status=IdentifiabilityDiagnosticStatus.NUMERIC_FAILURE,
            moment_classes=moment_classes,
            parameter_names=parameter_names,
            observed_moments=observed,
            warnings=(f"diagnostic_numeric_failure:{type(exc).__name__}:{exc}",),
            blocking_reasons=("diagnostic_numeric_failure",),
            metadata=_base_metadata(config, names),
        )

    return _persist_diagnostic_result(
        store,
        result,
        simulation_result_ref=sim_ref,
        observed_ref=observed_ref,
        parameter_ref=parameter_ref,
    )


def aggregate_moment_summary(
    values: Sequence[float],
    *,
    quantiles: Sequence[float] = _DEFAULT_IDENTIFIABILITY_QUANTILES,
    prefix: str = "",
) -> dict[str, float]:
    """Build the default mean/variance/quantile summary vector from raw outcomes."""

    array = np.asarray(values, dtype=float).reshape(-1)
    array = array[np.isfinite(array)]
    if array.size == 0:
        raise ValueError("aggregate_moment_summary requires at least one finite value")
    name_prefix = f"{prefix}_" if prefix else ""
    summary = {
        f"{name_prefix}mean": float(np.mean(array)),
        f"{name_prefix}variance": float(np.var(array)),
    }
    for quantile in quantiles:
        q = float(quantile)
        if not 0.0 < q < 1.0:
            raise ValueError("quantiles must be strictly inside (0, 1)")
        label = f"q{int(round(q * 100)):02d}"
        summary[f"{name_prefix}{label}"] = float(np.quantile(array, q))
    return summary


def load_identifiability_diagnostic_result(
    store: FileSystemCAS,
    ref: IdentifiabilityDiagnosticRef,
) -> IdentifiabilityDiagnosticResult:
    """Load a persisted aggregate-moment identifiability sidecar from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    result = IdentifiabilityDiagnosticResult.model_validate(payload)
    return result.model_copy(update={"diagnostic_ref": ref})


def attach_identifiability_diagnostic_ref(
    store: FileSystemCAS,
    *,
    simulation_result_ref: SimulationResultRef,
    diagnostic_ref: IdentifiabilityDiagnosticRef,
) -> SimulationResultRef:
    """Persist a new `SimulationResult` artifact that points at a diagnostic sidecar."""

    sim_ref = SimulationResultRef.model_validate(simulation_result_ref.model_dump(mode="python"))
    simulation_result = _load_model(store, sim_ref, SimulationResult)
    updated = simulation_result.model_copy(
        update={"identifiability_diagnostic_ref": diagnostic_ref}
    )
    ref = store.put_json(
        updated,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
            inputs=[
                InputRef(artifact_id=sim_ref.artifact_id, role="artifact.simulation_result_ref"),
                InputRef(
                    artifact_id=diagnostic_ref.artifact_id,
                    role="artifact.identifiability_diagnostic_ref",
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )
    return SimulationResultRef(artifact_id=ref.artifact_id)


def attach_abm_identifiability_certificate_ref(
    store: FileSystemCAS,
    *,
    simulation_result_ref: SimulationResultRef,
    diagnostic_ref: IdentifiabilityDiagnosticRef,
) -> ABMResultRef:
    """Persist an exact Phase-4 ``ABMResult`` with identifiability certificate populated."""

    sim_ref = SimulationResultRef.model_validate(simulation_result_ref.model_dump(mode="python"))
    simulation_result = _load_model(store, sim_ref, SimulationResult)
    abm_result = build_abm_result_from_simulation(
        simulation_result,
        identifiability_diagnostic_ref=diagnostic_ref,
    )
    ref = store.put_json(
        abm_result,
        PutOptions(
            kind="ir.abm_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ABMResult", version="1.0"),
            inputs=[
                InputRef(artifact_id=sim_ref.artifact_id, role="artifact.simulation_result_ref"),
                InputRef(
                    artifact_id=diagnostic_ref.artifact_id,
                    role="artifact.identifiability_diagnostic_ref",
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )
    return ABMResultRef.model_validate(
        {
            "artifact_id": ref.artifact_id,
            "kind": "ir.abm_result",
            "media_type": "application/json",
        }
    )


def _compute_identifiability_diagnostic(
    store: FileSystemCAS,
    *,
    summary_evaluator: SummaryEvaluator,
    observed: Mapping[str, float],
    center: Mapping[str, float],
    config: IdentifiabilityDiagnosticConfig,
    moment_classes: tuple[IdentifiabilityMomentClass, ...],
    parameter_bounds: Mapping[str, tuple[float, float]],
) -> IdentifiabilityDiagnosticResult:
    moment_names = tuple(observed.keys())
    parameter_names = tuple(center.keys())
    center_theta = {name: float(value) for name, value in center.items()}
    seeds = _replicate_seeds(config)
    observed_vec = np.asarray([observed[name] for name in moment_names], dtype=float)

    center_samples = _evaluate_samples(
        summary_evaluator,
        center_theta,
        seeds,
        moment_names=moment_names,
    )
    fitted_vec = np.mean(center_samples, axis=0)
    fitted_moments = _vector_to_mapping(moment_names, fitted_vec)
    weighting_matrix, weighting_warnings = _weighting_matrix(center_samples, config.ridge)

    jacobian, plus_samples, minus_samples, steps = _finite_difference_jacobian(
        summary_evaluator,
        center_theta,
        seeds,
        moment_names=moment_names,
        config=config,
    )
    fisher = np.asarray(jacobian.T @ weighting_matrix @ jacobian, dtype=float)
    fisher = 0.5 * (fisher + fisher.T)
    eigenvalues, eigenvectors = np.linalg.eigh(fisher)
    eigenvalues = np.maximum(np.asarray(eigenvalues, dtype=float), 0.0)
    jacobian_rank = int(np.sum(eigenvalues > config.rank_tol))
    min_eigenvalue = float(eigenvalues[0]) if eigenvalues.size else 0.0
    max_eigenvalue = float(eigenvalues[-1]) if eigenvalues.size else 0.0
    condition_number = (
        float("inf")
        if min_eigenvalue <= 0.0
        else float(max_eigenvalue / max(min_eigenvalue, np.finfo(float).tiny))
    )

    warnings = list(weighting_warnings)
    if np.allclose(np.ptp(center_samples, axis=0), 0.0):
        warnings.append("zero_replicate_summary_variation")

    bootstrap_rank_stability, bootstrap_ci, bootstrap_warnings = _bootstrap_fisher_stability(
        center_samples=center_samples,
        plus_samples=plus_samples,
        minus_samples=minus_samples,
        steps=steps,
        config=config,
    )
    warnings.extend(bootstrap_warnings)

    profile_intervals: dict[str, tuple[float, float] | None] = {}
    profile_hit_boundary: dict[str, bool] = {}
    profile_trace: dict[str, Any] | None = None
    if config.profile_grid_size >= 2 and config.persist_profiles:
        profile_trace, profile_intervals, profile_hit_boundary = _profile_traces(
            summary_evaluator,
            center_theta,
            observed_vec,
            weighting_matrix,
            seeds,
            moment_names=moment_names,
            config=config,
            parameter_bounds=parameter_bounds,
        )
        for name, hit_boundary in profile_hit_boundary.items():
            if hit_boundary:
                warnings.append(f"profile_hit_boundary:{name}")

    blocking_reasons: list[str] = []
    if jacobian_rank < len(parameter_names):
        blocking_reasons.append(f"rank_deficient:{jacobian_rank}<parameters:{len(parameter_names)}")
    if np.allclose(jacobian, 0.0):
        blocking_reasons.append("zero_summary_sensitivity")
    if condition_number >= config.condition_block_threshold:
        blocking_reasons.append("condition_number_exceeds_block_threshold")
    if (
        bootstrap_ci is not None
        and bootstrap_ci[1] <= config.sloppy_eigen_tol
        and config.bootstrap_reps > 0
    ):
        blocking_reasons.append("bootstrap_min_eigen_ci_below_sloppy_threshold")

    if not np.all(np.isfinite(fisher)):
        status = IdentifiabilityDiagnosticStatus.NUMERIC_FAILURE
        blocking_reasons.append("non_finite_fisher_information")
    elif "bootstrap_success_rate_below_25_percent" in warnings:
        status = IdentifiabilityDiagnosticStatus.INCONCLUSIVE
    elif blocking_reasons:
        status = IdentifiabilityDiagnosticStatus.NON_IDENTIFIED
    elif (
        min_eigenvalue <= config.sloppy_eigen_tol
        or condition_number >= config.condition_warn_threshold
        or (
            bootstrap_rank_stability is not None
            and bootstrap_rank_stability < config.bootstrap_rank_stability_warn
        )
        or any(profile_hit_boundary.values())
    ):
        status = IdentifiabilityDiagnosticStatus.SLOPPY
    else:
        status = IdentifiabilityDiagnosticStatus.IDENTIFIED

    sloppy_directions = _sloppy_directions(
        eigenvalues,
        eigenvectors,
        parameter_names,
        threshold=config.sloppy_eigen_tol,
    )
    alias_groups = tuple(
        tuple(direction["parameters"])
        for direction in sloppy_directions
        if len(direction.get("parameters", ())) >= 2
    )

    sensitivity_ref = None
    if config.persist_sensitivity_matrix:
        sensitivity_ref = _persist_sensitivity_matrix(
            store,
            moment_names=moment_names,
            parameter_names=parameter_names,
            jacobian=jacobian,
            fisher=fisher,
            weighting_matrix=weighting_matrix,
            steps=steps,
        )

    profile_ref = None
    if profile_trace is not None:
        profile_ref = _persist_profile_trace(store, profile_trace)

    return IdentifiabilityDiagnosticResult(
        status=status,
        moment_classes=moment_classes,
        parameter_names=parameter_names,
        effective_dimension=jacobian_rank,
        jacobian_rank=jacobian_rank,
        fisher_eigenvalues=tuple(float(value) for value in eigenvalues.tolist()),
        condition_number=float(condition_number),
        min_eigenvalue=min_eigenvalue,
        sloppy_directions=sloppy_directions,
        profile_intervals=profile_intervals,
        profile_hit_boundary=profile_hit_boundary,
        bootstrap_rank_stability=bootstrap_rank_stability,
        bootstrap_min_eigen_ci=bootstrap_ci,
        observed_moments=dict(observed),
        fitted_moments=fitted_moments,
        alias_groups=alias_groups,
        warnings=tuple(dict.fromkeys(warnings)),
        blocking_reasons=tuple(dict.fromkeys(blocking_reasons)),
        metadata=_base_metadata(config, moment_names),
        sensitivity_matrix_ref=sensitivity_ref,
        profile_trace_ref=profile_ref,
    )


def _finite_difference_jacobian(
    summary_evaluator: SummaryEvaluator,
    center: Mapping[str, float],
    seeds: tuple[int, ...],
    *,
    moment_names: tuple[str, ...],
    config: IdentifiabilityDiagnosticConfig,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, float]]:
    parameter_names = tuple(center.keys())
    jacobian = np.zeros((len(moment_names), len(parameter_names)), dtype=float)
    plus_samples: dict[str, np.ndarray] = {}
    minus_samples: dict[str, np.ndarray] = {}
    steps: dict[str, float] = {}
    base_seed = 0 if config.seed is None else int(config.seed)

    for index, name in enumerate(parameter_names):
        step = config.finite_diff_rel_step * max(abs(float(center[name])), 1.0)
        steps[name] = float(step)
        plus_theta = dict(center)
        minus_theta = dict(center)
        plus_theta[name] = float(center[name]) + step
        minus_theta[name] = float(center[name]) - step
        plus_seeds = seeds
        minus_seeds = seeds
        if not config.use_common_random_numbers:
            minus_seeds = tuple(
                base_seed + 100_000 * (index + 1) + offset for offset in range(len(seeds))
            )
        plus = _evaluate_samples(
            summary_evaluator,
            plus_theta,
            plus_seeds,
            moment_names=moment_names,
        )
        minus = _evaluate_samples(
            summary_evaluator,
            minus_theta,
            minus_seeds,
            moment_names=moment_names,
        )
        plus_samples[name] = plus
        minus_samples[name] = minus
        jacobian[:, index] = (np.mean(plus, axis=0) - np.mean(minus, axis=0)) / (2.0 * step)

    return jacobian, plus_samples, minus_samples, steps


def _bootstrap_fisher_stability(
    *,
    center_samples: np.ndarray,
    plus_samples: Mapping[str, np.ndarray],
    minus_samples: Mapping[str, np.ndarray],
    steps: Mapping[str, float],
    config: IdentifiabilityDiagnosticConfig,
) -> tuple[float | None, tuple[float, float] | None, tuple[str, ...]]:
    if config.bootstrap_reps <= 0:
        return None, None, ()
    n_reps = int(center_samples.shape[0])
    if n_reps < 2:
        return None, None, ("bootstrap_requires_at_least_two_simulation_reps",)

    parameter_names = tuple(steps.keys())
    rng = np.random.default_rng(config.seed)
    ranks: list[int] = []
    min_eigenvalues: list[float] = []
    warnings: list[str] = []

    for _ in range(config.bootstrap_reps):
        sample_idx = rng.integers(0, n_reps, size=n_reps)
        try:
            weighting_matrix, _ = _weighting_matrix(center_samples[sample_idx], config.ridge)
            jacobian = np.zeros((center_samples.shape[1], len(parameter_names)), dtype=float)
            for col, name in enumerate(parameter_names):
                plus = plus_samples[name][sample_idx]
                minus = minus_samples[name][sample_idx]
                jacobian[:, col] = (np.mean(plus, axis=0) - np.mean(minus, axis=0)) / (
                    2.0 * float(steps[name])
                )
            fisher = np.asarray(jacobian.T @ weighting_matrix @ jacobian, dtype=float)
            fisher = 0.5 * (fisher + fisher.T)
            eigenvalues = np.maximum(np.linalg.eigvalsh(fisher), 0.0)
            ranks.append(int(np.sum(eigenvalues > config.rank_tol)))
            min_eigenvalues.append(float(eigenvalues[0]) if eigenvalues.size else 0.0)
        except Exception:
            continue

    success_rate = len(min_eigenvalues) / max(config.bootstrap_reps, 1)
    if success_rate < 0.25:
        return None, None, ("bootstrap_success_rate_below_25_percent",)
    if success_rate < 1.0:
        warnings.append("bootstrap_partial_failures")
    full_rank = len(parameter_names)
    rank_stability = float(sum(rank == full_rank for rank in ranks) / len(ranks))
    lower, upper = np.quantile(
        np.asarray(min_eigenvalues, dtype=float),
        [config.alpha / 2.0, 1.0 - config.alpha / 2.0],
    )
    return rank_stability, (float(lower), float(upper)), tuple(warnings)


def _profile_traces(
    summary_evaluator: SummaryEvaluator,
    center: Mapping[str, float],
    observed_vec: np.ndarray,
    weighting_matrix: np.ndarray,
    seeds: tuple[int, ...],
    *,
    moment_names: tuple[str, ...],
    config: IdentifiabilityDiagnosticConfig,
    parameter_bounds: Mapping[str, tuple[float, float]],
) -> tuple[dict[str, Any], dict[str, tuple[float, float] | None], dict[str, bool]]:
    traces: dict[str, list[dict[str, Any]]] = {}
    intervals: dict[str, tuple[float, float] | None] = {}
    boundary_hits: dict[str, bool] = {}
    threshold = _chi_square_one_threshold(config.alpha)

    for name, value in center.items():
        grid = _profile_grid(float(value), config, parameter_bounds.get(name))
        losses: list[float] = []
        records: list[dict[str, Any]] = []
        for point in grid:
            theta_star, distance = _profile_loss_at_value(
                summary_evaluator,
                center,
                fixed_parameter=name,
                fixed_value=float(point),
                observed_vec=observed_vec,
                weighting_matrix=weighting_matrix,
                seeds=seeds,
                moment_names=moment_names,
                config=config,
                parameter_bounds=parameter_bounds,
            )
            losses.append(distance)
            records.append(
                {
                    "value": float(point),
                    "distance": distance,
                    "theta_star": {key: float(val) for key, val in theta_star.items()},
                }
            )
        traces[name] = records
        if not losses:
            intervals[name] = None
            boundary_hits[name] = False
            continue
        losses_arr = np.asarray(losses, dtype=float)
        cutoff = float(np.nanmin(losses_arr) + threshold)
        inside = np.flatnonzero(losses_arr <= cutoff)
        if inside.size == 0:
            intervals[name] = None
            boundary_hits[name] = False
        else:
            intervals[name] = (float(grid[int(inside[0])]), float(grid[int(inside[-1])]))
            boundary_hits[name] = bool(int(inside[0]) == 0 or int(inside[-1]) == len(grid) - 1)

    return (
        {
            "schema_version": "1.0",
            "profile_method": (
                "grid_coordinate_minimized_nuisance"
                if config.profile_optimize_nuisance
                else "fixed_other_parameters"
            ),
            "moment_names": list(moment_names),
            "traces": traces,
            "alpha": float(config.alpha),
            "threshold": float(threshold),
        },
        intervals,
        boundary_hits,
    )


def _profile_loss_at_value(
    summary_evaluator: SummaryEvaluator,
    center: Mapping[str, float],
    *,
    fixed_parameter: str,
    fixed_value: float,
    observed_vec: np.ndarray,
    weighting_matrix: np.ndarray,
    seeds: tuple[int, ...],
    moment_names: tuple[str, ...],
    config: IdentifiabilityDiagnosticConfig,
    parameter_bounds: Mapping[str, tuple[float, float]],
) -> tuple[dict[str, float], float]:
    theta = {name: float(value) for name, value in center.items()}
    theta[fixed_parameter] = float(fixed_value)
    nuisance_names = tuple(name for name in theta if name != fixed_parameter)
    if not config.profile_optimize_nuisance or not nuisance_names:
        return theta, _profile_distance(
            summary_evaluator,
            theta,
            observed_vec=observed_vec,
            weighting_matrix=weighting_matrix,
            seeds=seeds,
            moment_names=moment_names,
        )

    best_theta = dict(theta)
    best_loss = _profile_distance(
        summary_evaluator,
        best_theta,
        observed_vec=observed_vec,
        weighting_matrix=weighting_matrix,
        seeds=seeds,
        moment_names=moment_names,
    )
    search_bounds = {
        name: _local_profile_bounds(float(center[name]), config, parameter_bounds.get(name))
        for name in nuisance_names
    }

    for _ in range(config.profile_nuisance_refinements + 1):
        improved = False
        for nuisance_name in nuisance_names:
            lower, upper = search_bounds[nuisance_name]
            for candidate in np.linspace(
                lower,
                upper,
                int(config.profile_nuisance_grid_size),
                dtype=float,
            ):
                trial = dict(best_theta)
                trial[nuisance_name] = float(candidate)
                loss = _profile_distance(
                    summary_evaluator,
                    trial,
                    observed_vec=observed_vec,
                    weighting_matrix=weighting_matrix,
                    seeds=seeds,
                    moment_names=moment_names,
                )
                if loss + np.finfo(float).eps < best_loss:
                    best_loss = loss
                    best_theta = trial
                    improved = True
            lower, upper = search_bounds[nuisance_name]
            width = max((upper - lower) / 4.0, config.finite_diff_rel_step)
            center_value = best_theta[nuisance_name]
            bounds = parameter_bounds.get(nuisance_name)
            new_lower = center_value - width
            new_upper = center_value + width
            if bounds is not None:
                new_lower = max(new_lower, float(bounds[0]))
                new_upper = min(new_upper, float(bounds[1]))
            search_bounds[nuisance_name] = (new_lower, new_upper)
        if not improved:
            break

    return best_theta, float(best_loss)


def _profile_distance(
    summary_evaluator: SummaryEvaluator,
    theta: Mapping[str, float],
    *,
    observed_vec: np.ndarray,
    weighting_matrix: np.ndarray,
    seeds: tuple[int, ...],
    moment_names: tuple[str, ...],
) -> float:
    fitted = np.mean(
        _evaluate_samples(summary_evaluator, theta, seeds, moment_names=moment_names),
        axis=0,
    )
    residual = observed_vec - fitted
    return float(residual.T @ weighting_matrix @ residual)


def _local_profile_bounds(
    value: float,
    config: IdentifiabilityDiagnosticConfig,
    bounds: tuple[float, float] | None,
) -> tuple[float, float]:
    if bounds is not None:
        lower, upper = float(bounds[0]), float(bounds[1])
    else:
        radius = config.profile_rel_radius * max(abs(value), 1.0)
        lower, upper = value - radius, value + radius
    if lower > upper:
        lower, upper = upper, lower
    if np.isclose(lower, upper):
        upper = lower + max(abs(lower), 1.0) * config.finite_diff_rel_step
    return lower, upper


def _evaluate_samples(
    summary_evaluator: SummaryEvaluator,
    theta: Mapping[str, float],
    seeds: Sequence[int],
    *,
    moment_names: tuple[str, ...],
) -> np.ndarray:
    rows: list[list[float]] = []
    for seed in seeds:
        summary = summary_evaluator(theta, int(seed))
        rows.append(_summary_vector(summary, moment_names))
    return np.asarray(rows, dtype=float)


def _summary_vector(summary: Mapping[str, float], moment_names: tuple[str, ...]) -> list[float]:
    row: list[float] = []
    for name in moment_names:
        if name not in summary:
            raise KeyError(f"summary_evaluator did not return moment {name!r}")
        value = summary[name]
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(float(value)):
            raise ValueError(f"summary moment {name!r} must be a finite numeric value")
        row.append(float(value))
    return row


def _weighting_matrix(samples: np.ndarray, ridge: float) -> tuple[np.ndarray, tuple[str, ...]]:
    warnings: list[str] = []
    if samples.shape[0] >= 2:
        covariance = np.cov(samples, rowvar=False)
        covariance = np.atleast_2d(np.asarray(covariance, dtype=float))
    else:
        covariance = np.zeros((samples.shape[1], samples.shape[1]), dtype=float)
        warnings.append("weighting_matrix_regularized")
    covariance = 0.5 * (covariance + covariance.T)
    if covariance.size and np.linalg.matrix_rank(covariance) < covariance.shape[0]:
        warnings.append("weighting_matrix_regularized")
    regularized = covariance + float(ridge) * np.eye(covariance.shape[0], dtype=float)
    try:
        condition = np.linalg.cond(regularized)
        if not np.isfinite(condition) or condition > 1.0 / max(float(ridge), np.finfo(float).tiny):
            warnings.append("weighting_matrix_regularized")
        inverse = np.linalg.inv(regularized)
    except np.linalg.LinAlgError:
        warnings.append("weighting_matrix_pseudoinverse_used")
        inverse = np.linalg.pinv(regularized)
    return inverse, tuple(warnings)


def _replicate_seeds(config: IdentifiabilityDiagnosticConfig) -> tuple[int, ...]:
    base = 0 if config.seed is None else int(config.seed)
    return tuple(base + offset for offset in range(config.simulation_reps))


def _profile_grid(
    value: float,
    config: IdentifiabilityDiagnosticConfig,
    bounds: tuple[float, float] | None,
) -> np.ndarray:
    lower, upper = _local_profile_bounds(value, config, bounds)
    return np.linspace(lower, upper, int(config.profile_grid_size), dtype=float)


def _chi_square_one_threshold(alpha: float) -> float:
    if abs(alpha - 0.05) < 1e-12:
        return 3.841458820694124
    if abs(alpha - 0.10) < 1e-12:
        return 2.705543454095404
    if abs(alpha - 0.01) < 1e-12:
        return 6.6348966010212145
    return float(-2.0 * np.log(max(alpha, np.finfo(float).tiny)))


def _sloppy_directions(
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
    parameter_names: tuple[str, ...],
    *,
    threshold: float,
) -> tuple[dict[str, Any], ...]:
    directions: list[dict[str, Any]] = []
    if eigenvalues.size == 0:
        return ()
    cutoff = max(float(threshold), float(eigenvalues[0]))
    for index, eigenvalue in enumerate(eigenvalues):
        if eigenvalue > cutoff and index > 0:
            continue
        vector = np.asarray(eigenvectors[:, index], dtype=float)
        weights = {
            name: float(vector[param_index])
            for param_index, name in enumerate(parameter_names)
            if abs(float(vector[param_index])) >= 0.10
        }
        parameters = tuple(
            name
            for name, _ in sorted(weights.items(), key=lambda item: abs(item[1]), reverse=True)
            if abs(weights[name]) >= 0.25
        )
        directions.append(
            {
                "eigenvalue": float(eigenvalue),
                "weights": weights,
                "parameters": parameters,
            }
        )
    return tuple(directions)


def _persist_sensitivity_matrix(
    store: FileSystemCAS,
    *,
    moment_names: tuple[str, ...],
    parameter_names: tuple[str, ...],
    jacobian: np.ndarray,
    fisher: np.ndarray,
    weighting_matrix: np.ndarray,
    steps: Mapping[str, float],
) -> ArtifactRef:
    payload = {
        "schema_version": "1.0",
        "moment_names": list(moment_names),
        "parameter_names": list(parameter_names),
        "jacobian": np.asarray(jacobian, dtype=float).tolist(),
        "fisher_information": np.asarray(fisher, dtype=float).tolist(),
        "weighting_matrix": np.asarray(weighting_matrix, dtype=float).tolist(),
        "finite_diff_steps": {name: float(step) for name, step in steps.items()},
    }
    return store.put_json(
        payload,
        PutOptions(
            kind="foundry.identifiability_sensitivity_matrix",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.IdentifiabilitySensitivityMatrix", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )


def _persist_profile_trace(store: FileSystemCAS, payload: Mapping[str, Any]) -> ArtifactRef:
    return store.put_json(
        dict(payload),
        PutOptions(
            kind="foundry.identifiability_profile_trace",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.IdentifiabilityProfileTrace", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )


def _persist_diagnostic_result(
    store: FileSystemCAS,
    result: IdentifiabilityDiagnosticResult,
    *,
    simulation_result_ref: SimulationResultRef,
    observed_ref: ArtifactRef | None = None,
    parameter_ref: ArtifactRef | None = None,
) -> IdentifiabilityDiagnosticResult:
    inputs = [InputRef(artifact_id=simulation_result_ref.artifact_id, role="simulation_result")]
    if observed_ref is not None:
        inputs.append(InputRef(artifact_id=observed_ref.artifact_id, role="observed_moment_bundle"))
    if parameter_ref is not None:
        inputs.append(InputRef(artifact_id=parameter_ref.artifact_id, role="parameter_center"))
    if result.sensitivity_matrix_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=result.sensitivity_matrix_ref.artifact_id,
                role="artifact.sensitivity_matrix_ref",
            )
        )
    if result.profile_trace_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=result.profile_trace_ref.artifact_id,
                role="artifact.profile_trace_ref",
            )
        )

    ref = store.put_json(
        result,
        PutOptions(
            kind="foundry.identifiability_diagnostic",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.IdentifiabilityDiagnosticResult",
                version=result.schema_version,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )
    return result.model_copy(
        update={"diagnostic_ref": IdentifiabilityDiagnosticRef(artifact_id=ref.artifact_id)}
    )


def _base_metadata(
    config: IdentifiabilityDiagnosticConfig,
    moment_names: Sequence[str],
) -> dict[str, Any]:
    return {
        "diagnostic_method": "aggregate_moment_local_fisher_profile_bootstrap",
        "moment_names": list(moment_names),
        "config": config.model_dump(mode="json", exclude_none=True),
    }


def _infer_moment_classes(moment_names: Sequence[str]) -> tuple[IdentifiabilityMomentClass, ...]:
    lowered = [name.lower() for name in moment_names]
    has_mean_variance = any(
        "mean" in name or "var" in name or "variance" in name for name in lowered
    )
    has_quantiles = any("quantile" in name or name.startswith("q") for name in lowered)
    if has_mean_variance and has_quantiles:
        return (IdentifiabilityMomentClass.COMBINED,)
    if has_quantiles:
        return (IdentifiabilityMomentClass.QUANTILES,)
    if has_mean_variance:
        return (IdentifiabilityMomentClass.MEAN_VARIANCE,)
    return ()


def _resolve_float_mapping(
    store: FileSystemCAS,
    bundle: Mapping[str, Any] | ArtifactRef,
    *,
    label: str,
) -> dict[str, float]:
    if isinstance(bundle, ArtifactRef):
        payload = from_canonical_bytes(store.get_bytes(bundle.artifact_id))
        if isinstance(payload, Mapping) and isinstance(payload.get("values"), Mapping):
            payload = payload["values"]
    else:
        payload = bundle
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must resolve to a mapping")
    values: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, bool) or not isinstance(value, Real):
            continue
        numeric = float(value)
        if not isfinite(numeric):
            continue
        values[str(key)] = numeric
    if not values:
        raise ValueError(f"{label} contains no finite numeric values")
    return values


def _resolve_parameter_center(
    store: FileSystemCAS,
    simulation_result_ref: SimulationResultRef,
    parameter_center: Mapping[str, Any] | ArtifactRef | None,
) -> dict[str, float]:
    if parameter_center is None:
        manifest = store.get_manifest(simulation_result_ref.artifact_id)
        bundle_input = next(
            (
                item
                for item in manifest.inputs
                if item.role in {"parameter_override_bundle", "feedback.parameter_override_bundle"}
            ),
            None,
        )
        if bundle_input is None:
            return {}
        parameter_center = ParameterOverrideBundleRef(artifact_id=bundle_input.artifact_id)

    if isinstance(parameter_center, ArtifactRef):
        payload = from_canonical_bytes(store.get_bytes(parameter_center.artifact_id))
        if isinstance(payload, Mapping) and "overrides" in payload:
            bundle = ParameterOverrideBundle.model_validate(payload)
            return _flatten_parameter_overrides(bundle.overrides)
        return _resolve_float_mapping(store, parameter_center, label="parameter_center")

    if any(isinstance(value, Mapping) for value in parameter_center.values()):
        nested = {
            str(node_id): dict(values)
            for node_id, values in parameter_center.items()
            if isinstance(values, Mapping)
        }
        return _flatten_parameter_overrides(nested)
    return _resolve_float_mapping(store, parameter_center, label="parameter_center")


def _flatten_parameter_overrides(overrides: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    values: dict[str, float] = {}
    for node_id, node_values in overrides.items():
        for param_name, raw_value in node_values.items():
            if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
                continue
            value = float(raw_value)
            if isfinite(value):
                values[f"{node_id}.{param_name}"] = value
    return values


def _build_execute_summary_evaluator(
    store: FileSystemCAS,
    *,
    simulation_result_ref: SimulationResultRef,
    simulation_result: SimulationResult,
) -> SummaryEvaluator:
    manifest = store.get_manifest(simulation_result_ref.artifact_id)
    input_bindings_input = _find_input(manifest.inputs, "input.input_bindings_ref")
    if input_bindings_input is None:
        raise ValueError("simulation result manifest has no input.input_bindings_ref")

    bindings_ref = FoundryInputBindingsRef(artifact_id=input_bindings_input.artifact_id)
    bindings = _load_model(store, bindings_ref, FoundryInputBindings)
    feedback_config_input = _find_input(manifest.inputs, "input.feedback_config_ref")
    feedback_config_ref = (
        None
        if feedback_config_input is None
        else FeedbackConfigRef(artifact_id=feedback_config_input.artifact_id)
    )

    def evaluate(theta: Mapping[str, float], seed: int | None) -> Mapping[str, float]:
        bundle_ref = _persist_flat_parameter_overrides(store, theta)
        from polisyos.foundry.execute.api import execute

        result = execute(
            store,
            ExecuteRequest(
                exec_plan_ref=simulation_result.exec_plan_ref,
                input_bindings_ref=bindings_ref,
                registry_bundle_ref=bindings.registry_bundle_ref,
                feedback_config_ref=feedback_config_ref,
                parameter_override_bundle_ref=bundle_ref,
                exec_config=FoundryExecConfig(seed=0 if seed is None else int(seed)),
            ),
        )
        if not result.ok or result.simulation_result_ref is None:
            raise RuntimeError(f"execute-backed diagnostic replay failed: {result.notes}")
        replay_simulation = _load_model(store, result.simulation_result_ref, SimulationResult)
        metrics = _load_model(store, replay_simulation.metrics_ref, Metrics)
        return {
            str(key): float(value)
            for key, value in metrics.values.items()
            if isinstance(value, Real) and not isinstance(value, bool)
        }

    return evaluate


def _find_input(inputs: Sequence[InputRef], role: str) -> InputRef | None:
    return next((item for item in inputs if item.role == role), None)


def _persist_flat_parameter_overrides(
    store: FileSystemCAS,
    theta: Mapping[str, float],
) -> ParameterOverrideBundleRef:
    overrides: dict[str, dict[str, float]] = {}
    for key, value in theta.items():
        if "." not in key:
            raise ValueError(
                "execute-backed identifiability diagnostics require node_id.parameter keys"
            )
        node_id, param_name = key.split(".", 1)
        overrides.setdefault(node_id, {})[param_name] = float(value)
    ref = store.put_json(
        ParameterOverrideBundle(
            overrides=overrides,
            sources={node_id: ["identifiability_diagnostic"] for node_id in overrides},
            notes=["aggregate_moment_identifiability_replay"],
        ),
        PutOptions(
            kind="foundry.parameter_override_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ParameterOverrideBundle", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )
    return ParameterOverrideBundleRef(artifact_id=ref.artifact_id)


def _load_model[ModelT: BaseModel](
    store: FileSystemCAS,
    ref: ArtifactRef,
    model_cls: type[ModelT],
) -> ModelT:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)


def _vector_to_mapping(names: Sequence[str], values: np.ndarray) -> dict[str, float]:
    return {str(name): float(value) for name, value in zip(names, values, strict=True)}
