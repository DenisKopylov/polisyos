"""Frontier Bayesian interfaces with dependency-aware runtime truthfulness."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.ml.protocols import PredictionResult, TabularData
from polisyos.foundry.methods.catalog.ml.regression import _build_prediction_result, _feature_names
from polisyos.foundry.uncertainty.protocol import UncertaintyDecomposition

from .prior_sensitivity import (
    BayesianPolicyModelFamily,
    DataConditioningMode,
    SensitivityCurvePoint,
    assemble_prior_sensitivity_report,
    build_admissible_prior_class,
    build_sensitivity_record_from_intervals,
    not_run_prior_sensitivity_report,
    prior_predictive_rank_test,
    simulate_bart_prior_predictive,
)
from .protocols import (
    PosteriorResult,
    SimulatorDiagnosticArtifact,
    augment_sampler_diagnostics,
    canonical_simulator_diagnostic_artifact,
    extract_truthfulness_hints,
    relative_interval_shift_max,
    split_truthfulness_hints,
    summarize_posterior_samples,
    validate_simulator_diagnostic_artifact,
    weighted_quantile,
)


def _posterior_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec.for_output_contract(
                "result",
                SlotType.SCALAR,
                Unit("posterior", "json"),
                output_contract=PosteriorResult,
            ),
            SlotSpec(
                "posterior_samples",
                SlotType.MATRIX,
                Unit("posterior", "draw"),
                shape=("n_samples", "n_parameters"),
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _sbi_output_slots() -> frozenset[SlotSpec]:
    return _posterior_output_slots() | frozenset(
        {
            SlotSpec(
                "simulator_diagnostic",
                SlotType.SCALAR,
                Unit("diagnostic", "json"),
                contract_id=SimulatorDiagnosticArtifact.contract_id,
            ),
            SlotSpec(
                "simulator_diagnostic_ref",
                SlotType.SCALAR,
                Unit("artifact", "ref"),
            ),
        }
    )


def _prediction_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec.for_output_contract(
                "result",
                SlotType.SCALAR,
                Unit("posterior", "json"),
                output_contract=PosteriorResult,
            ),
            SlotSpec(
                "prediction_result",
                SlotType.SCALAR,
                Unit("prediction", "json"),
                contract_id=PredictionResult.contract_id,
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _coerce_sbi_payload(state: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    parameters = np.asarray(state["parameters"], dtype=float)
    simulations = np.asarray(state["simulations"], dtype=float)
    observed = np.asarray(state["observed_summary"], dtype=float)
    if parameters.ndim == 1:
        parameters = parameters[:, None]
    if simulations.ndim == 1:
        simulations = simulations[:, None]
    if observed.ndim != 1:
        observed = observed.reshape(-1)
    if parameters.ndim != 2 or simulations.ndim != 2:
        raise ValueError("parameters and simulations must be 1D or 2D numeric arrays")
    if parameters.shape[0] != simulations.shape[0]:
        raise ValueError("parameters and simulations must have the same number of rows")
    if simulations.shape[1] != observed.shape[0]:
        raise ValueError("observed_summary dimension must match simulation summary columns")
    if parameters.shape[0] < 16:
        raise ValueError("SBI methods require at least 16 simulated parameter/summary pairs")
    return parameters, simulations, observed


def _runtime_backend(params: Mapping[str, Any]) -> str:
    return str(params.get("__bayesian_runtime_backend__", "unavailable")).strip().lower()


def _require_backend(
    params: Mapping[str, Any], expected: str, *, method_variant: str | None = None
) -> None:
    actual = _runtime_backend(params)
    if actual != expected:
        method_label = f" {method_variant}" if method_variant else ""
        raise RuntimeError(
            f"Bayesian frontier method{method_label} requires runtime_backend={expected!r}; "
            f"resolved runtime_backend={actual!r}"
        )


def _sbi_infer(
    *,
    algorithm: str,
    parameters: np.ndarray,
    simulations: np.ndarray,
    observed_summary: np.ndarray,
    num_posterior_samples: int,
    num_training_epochs: int,
    seed: int,
) -> np.ndarray:
    _require_numpy_finite("parameters", parameters)
    _require_numpy_finite("simulations", simulations)
    _require_numpy_finite("observed_summary", observed_summary)
    try:
        import torch
        from sbi.inference import SNLE, SNPE, SNRE
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("SBI runtime requires installed 'sbi' and 'torch' packages") from exc

    torch.manual_seed(int(seed))
    theta = torch.as_tensor(parameters, dtype=torch.float32)
    x = torch.as_tensor(simulations, dtype=torch.float32)
    observed = torch.as_tensor(observed_summary, dtype=torch.float32)
    inference_cls = {"npe": SNPE, "nle": SNLE, "nre": SNRE}[algorithm]
    try:
        inference = inference_cls(prior=None)
        estimator = inference.append_simulations(theta, x).train(
            max_num_epochs=max(1, int(num_training_epochs)),
            show_train_summary=False,
        )
        posterior = inference.build_posterior(estimator)
        samples = posterior.sample((max(1, int(num_posterior_samples)),), x=observed)
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError(f"SBI {algorithm.upper()} inference failed") from exc
    return np.asarray(samples.detach().cpu().numpy(), dtype=float)


def _require_numpy_finite(label: str, value: np.ndarray) -> None:
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{label} must contain only finite numeric values")


def _posterior_from_samples(
    *,
    method_name: str,
    samples: np.ndarray,
    credible_mass: float,
    parameter_names: list[str],
    metadata: Mapping[str, Any],
    diagnostics: Mapping[str, Any] | None = None,
    simulator_diagnostic_ref: str | None = None,
) -> PosteriorResult:
    sample_map = {name: samples[:, idx] for idx, name in enumerate(parameter_names)}
    posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
        sample_map,
        credible_mass=credible_mass,
    )
    return PosteriorResult(
        method_name=method_name,
        posterior_means=posterior_means,
        posterior_stds=posterior_stds,
        credible_intervals=credible_intervals,
        diagnostics={
            "credible_mass": float(credible_mass),
            "num_samples": float(samples.shape[0]),
            "num_parameters": float(samples.shape[1]),
            **{
                str(key): float(value)
                for key, value in (diagnostics or {}).items()
                if np.isfinite(float(value))
            },
        },
        metadata=dict(metadata),
        simulator_diagnostic_ref=simulator_diagnostic_ref,
    )


def _apply_truthfulness_hints(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> tuple[dict[str, float], dict[str, Any]]:
    hints = extract_truthfulness_hints(*sources)
    hint_diagnostics, hint_metadata = split_truthfulness_hints(hints)
    merged_diagnostics = dict(diagnostics)
    merged_diagnostics.update(hint_diagnostics)
    merged_metadata = dict(metadata)
    merged_metadata.update(hint_metadata)
    return merged_diagnostics, merged_metadata


_SBI_SIMULATOR_REGIME_SCHEMA = {
    "version": "v1",
    "variables": [
        {
            "name": "calendar_period",
            "kind": "ordered_discrete",
            "observed_at_inference": True,
        },
        {
            "name": "policy_regime",
            "kind": "categorical",
            "observed_at_inference": True,
        },
        {
            "name": "admin_definition",
            "kind": "categorical",
            "observed_at_inference": True,
        },
    ],
    "stationarity_assumption": "piecewise_stationary_given_regime",
    "discontinuity_axes": ["policy_regime", "admin_definition"],
    "smooth_axes": ["calendar_period"],
}
_SBI_SUMMARY_SCHEMA_REF = "artifact://foundry/sbi/summary_schema/regime-aware-v1"
_SBI_IDENTIFIABLE_TARGET = {
    "parameter_names": [],
    "functional_target_names": [],
    "equivalence_classes_allowed": True,
    "target_conditioning": "p(theta | summary, regime_context)",
}
_SBI_COVERAGE_CONTRACT = {
    "coverage_target": 0.90,
    "coverage_tolerance": 0.03,
    "budget_lower_bound_formula": ("C*(d_id+log(1/delta))/eps_cov^2 * regime_cover_cost"),
    "locality": "conditional_on_regime",
}
_SBI_DIAGNOSTIC_CONTRACT = {
    "required_metrics": [
        "support_quantile",
        "knn_radius_mahalanobis",
        "effective_local_simulations",
        "local_c2st_score",
        "posterior_sbc_error",
        "tarp_coverage_error",
        "ppc_mahalanobis",
    ],
    "support_required": True,
    "thresholds": {
        "support_quantile_min": 0.01,
        "knn_radius_mahalanobis_max": 4.0,
        "min_effective_local_simulations": 16,
    },
}


def _sbi_contract_metadata(method_metadata: MethodMetadata) -> dict[str, Any]:
    coverage_contract = dict(method_metadata.coverage_contract)
    return {
        "regime_aware_calibration_required": bool(method_metadata.diagnostic_contract),
        "simulator_regime_schema": dict(method_metadata.simulator_regime_schema),
        "summary_schema_ref": method_metadata.summary_schema_ref,
        "identifiable_target": dict(method_metadata.identifiable_target),
        "coverage_contract": coverage_contract,
        "coverage_tolerance": coverage_contract.get("coverage_tolerance"),
        "diagnostic_contract": dict(method_metadata.diagnostic_contract),
    }


def _metadata_lookup(source: Mapping[str, Any], key: str) -> Any:
    if key in source:
        return source.get(key)
    metadata = source.get("metadata")
    if isinstance(metadata, Mapping):
        return metadata.get(key)
    return None


def _first_text_from_sources(
    sources: tuple[Mapping[str, Any], ...],
    *,
    key: str,
) -> str | None:
    for source in sources:
        raw = _metadata_lookup(source, key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return None


def _merge_simulator_diagnostic(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> tuple[dict[str, float], dict[str, Any], str | None]:
    merged_diagnostics = dict(diagnostics)
    merged_metadata = dict(metadata)
    diagnostic_ref = _first_text_from_sources(sources, key="simulator_diagnostic_ref")
    for source in sources:
        observed_regime = _metadata_lookup(source, "observed_regime")
        if isinstance(observed_regime, Mapping):
            merged_metadata["observed_regime"] = dict(observed_regime)
    for source in sources:
        raw = _metadata_lookup(source, "simulator_diagnostic")
        if raw is None:
            continue
        diagnostic = validate_simulator_diagnostic_artifact(raw)
        if diagnostic is None:
            continue
        payload = diagnostic.model_dump(mode="python", by_alias=True, exclude_none=True)
        merged_metadata["simulator_diagnostic"] = payload
        if diagnostic.artifact_ref and diagnostic_ref is None:
            diagnostic_ref = diagnostic.artifact_ref
        for key in (
            "support_quantile",
            "knn_radius_mahalanobis",
            "effective_local_simulations",
            "local_c2st_score",
            "posterior_sbc_error",
            "tarp_coverage_error",
            "ppc_mahalanobis",
        ):
            value = payload.get(key)
            if value is None:
                continue
            scalar = float(value)
            if np.isfinite(scalar):
                merged_diagnostics[key] = scalar
        merged_metadata["simulator_diagnostic_status"] = diagnostic.status
        merged_metadata["failure_mode"] = list(diagnostic.failure_mode)
        if diagnostic.observed_regime:
            merged_metadata["observed_regime"] = dict(diagnostic.observed_regime)
    if diagnostic_ref is not None:
        merged_metadata["simulator_diagnostic_ref"] = diagnostic_ref
    return merged_diagnostics, merged_metadata, diagnostic_ref


def _coerce_regime_rows(raw: Any, *, n_rows: int) -> list[dict[str, Any]] | None:
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        rows: list[dict[str, Any]] = [dict() for _ in range(n_rows)]
        found_vector = False
        for key, values in raw.items():
            if isinstance(values, (str, bytes)) or not hasattr(values, "__len__"):
                for row in rows:
                    row[str(key)] = values
                continue
            if len(values) != n_rows:
                return None
            found_vector = True
            for idx, value in enumerate(values):
                rows[idx][str(key)] = value
        return rows if found_vector or rows else None
    if not isinstance(raw, (list, tuple)) or len(raw) != n_rows:
        return None
    rows = []
    for item in raw:
        if not isinstance(item, Mapping):
            return None
        rows.append(dict(item))
    return rows


def _simulation_regimes_from_sources(
    sources: tuple[Mapping[str, Any], ...],
    *,
    n_rows: int,
) -> list[dict[str, Any]] | None:
    for key in ("simulation_regimes", "simulator_regimes", "regime_contexts"):
        for source in sources:
            regimes = _coerce_regime_rows(_metadata_lookup(source, key), n_rows=n_rows)
            if regimes is not None:
                return regimes
    return None


def _observed_regime_from_sources(sources: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    for key in ("observed_regime", "regime_context", "observed_context"):
        for source in sources:
            raw = _metadata_lookup(source, key)
            if isinstance(raw, Mapping):
                regime = {str(name): value for name, value in raw.items() if value is not None}
                if regime:
                    return regime
    return {}


def _regime_match_mask(
    regimes: list[dict[str, Any]] | None,
    observed_regime: Mapping[str, Any],
) -> np.ndarray | None:
    if regimes is None or not observed_regime:
        return None
    keys = [str(key) for key, value in observed_regime.items() if value is not None]
    if not keys:
        return None
    return np.asarray(
        [
            all(str(regime.get(key, "")) == str(observed_regime[key]) for key in keys)
            for regime in regimes
        ],
        dtype=bool,
    )


def _sbi_recommended_local_budget(
    *,
    parameter_dimension: int,
    metadata: Mapping[str, Any],
) -> int:
    coverage_contract = metadata.get("coverage_contract")
    if not isinstance(coverage_contract, Mapping):
        coverage_contract = {}
    identifiable_target = metadata.get("identifiable_target")
    target_dim = parameter_dimension
    if isinstance(identifiable_target, Mapping):
        target_names = list(identifiable_target.get("parameter_names") or ()) + list(
            identifiable_target.get("functional_target_names") or ()
        )
        if target_names:
            target_dim = max(1, len(target_names))
    tolerance = coverage_contract.get("coverage_tolerance", metadata.get("coverage_tolerance"))
    try:
        eps_cov = float(tolerance)
    except (TypeError, ValueError):
        eps_cov = 0.05
    eps_cov = float(np.clip(eps_cov, 1e-3, 0.5))
    delta_raw = coverage_contract.get("delta", metadata.get("coverage_delta", 0.05))
    try:
        delta = float(delta_raw)
    except (TypeError, ValueError):
        delta = 0.05
    delta = float(np.clip(delta, 1e-12, 0.5))
    constant_raw = coverage_contract.get(
        "budget_constant",
        metadata.get("budget_constant", 0.01),
    )
    try:
        constant = float(constant_raw)
    except (TypeError, ValueError):
        constant = 0.01
    constant = max(constant, 0.0)
    lower_bound = constant * (float(target_dim) + float(np.log(1.0 / delta))) / (eps_cov**2)
    return max(16, int(np.ceil(lower_bound)))


def _sbi_regime_training_view(
    *,
    parameters: np.ndarray,
    simulations: np.ndarray,
    observed_regime: Mapping[str, Any],
    simulation_regimes: list[dict[str, Any]] | None,
    min_local: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | bool | int]]:
    mask = _regime_match_mask(simulation_regimes, observed_regime)
    if mask is None:
        return (
            parameters,
            simulations,
            {
                "effective_local_simulations": int(parameters.shape[0]),
                "regime_context_declared": bool(observed_regime),
                "simulation_regimes_declared": simulation_regimes is not None,
                "regime_local_training_used": False,
                "pooled_training_used": True,
            },
        )
    local_count = int(np.count_nonzero(mask))
    if local_count >= min_local:
        return (
            parameters[mask],
            simulations[mask],
            {
                "effective_local_simulations": local_count,
                "regime_context_declared": True,
                "simulation_regimes_declared": True,
                "regime_local_training_used": True,
                "pooled_training_used": False,
            },
        )
    return (
        parameters,
        simulations,
        {
            "effective_local_simulations": local_count,
            "regime_context_declared": True,
            "simulation_regimes_declared": True,
            "regime_local_training_used": False,
            "pooled_training_used": True,
        },
    )


def _sbi_simulation_distance_diagnostics(
    *,
    parameters: np.ndarray,
    simulations: np.ndarray,
    observed_summary: np.ndarray,
    samples: np.ndarray,
) -> dict[str, float]:
    simulation_scale = np.std(simulations, axis=0, ddof=1)
    simulation_scale = np.where(simulation_scale > 1e-9, simulation_scale, 1.0)
    standardized_distances = np.linalg.norm(
        (simulations - observed_summary[None, :]) / simulation_scale[None, :], axis=1
    )
    neighborhood_count = min(max(16, int(np.sqrt(simulations.shape[0]))), simulations.shape[0])
    nearest = np.argsort(standardized_distances)[:neighborhood_count]
    local_parameters = parameters[nearest]
    local_mean = np.mean(local_parameters, axis=0)
    local_std = np.std(local_parameters, axis=0, ddof=1)
    local_std = np.where(local_std > 1e-9, local_std, 1.0)
    sample_mean = np.mean(samples, axis=0)
    sample_std = np.std(samples, axis=0, ddof=1)
    sample_std = np.where(sample_std > 1e-9, sample_std, 1.0)
    knn_radius = float(np.mean(standardized_distances[nearest]))
    radius_ratio = knn_radius / max(float(np.mean(standardized_distances)), 1e-12)
    return {
        "observed_neighborhood_count": float(neighborhood_count),
        "observed_neighborhood_radius_quantile": float(radius_ratio),
        "support_quantile": float(np.clip(1.0 - radius_ratio, 0.0, 1.0)),
        "knn_radius_mahalanobis": knn_radius,
        "local_reference_mean_shift_max": float(
            np.max(np.abs(sample_mean - local_mean) / local_std)
        ),
        "local_reference_std_ratio_max": float(
            np.max(np.maximum(sample_std / local_std, local_std / sample_std))
        ),
    }


def _build_sbi_diagnostic_artifact(
    *,
    observed_regime: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[str, dict[str, Any], str]:
    diagnostic_contract = metadata.get("diagnostic_contract")
    thresholds = (
        diagnostic_contract.get("thresholds", {})
        if isinstance(diagnostic_contract, Mapping)
        else {}
    )
    default_thresholds = _SBI_DIAGNOSTIC_CONTRACT["thresholds"]
    min_support_quantile = float(
        thresholds.get("support_quantile_min", default_thresholds["support_quantile_min"])
    )
    max_knn_radius = float(
        thresholds.get(
            "knn_radius_mahalanobis_max", default_thresholds["knn_radius_mahalanobis_max"]
        )
    )
    min_local = float(
        thresholds.get(
            "min_effective_local_simulations",
            default_thresholds["min_effective_local_simulations"],
        )
    )
    failure_modes: list[str] = []
    if not observed_regime:
        failure_modes.append("regime_context_missing")
    if float(diagnostics.get("effective_local_simulations", 0.0)) < min_local and bool(
        diagnostics.get("simulation_regimes_declared", False)
    ):
        failure_modes.append("regime_extrapolation")
    support_quantile = float(diagnostics.get("support_quantile", 0.0))
    knn_radius = float(diagnostics.get("knn_radius_mahalanobis", np.inf))
    if support_quantile < min_support_quantile or knn_radius > max_knn_radius:
        failure_modes.append("unreachable_observation")
    try:
        coverage_tolerance = float(metadata.get("coverage_tolerance", 0.05))
    except (TypeError, ValueError):
        coverage_tolerance = 0.05
    posterior_sbc_error = diagnostics.get("posterior_sbc_error")
    tarp_coverage_error = diagnostics.get("tarp_coverage_error")
    local_c2st_score = diagnostics.get("local_c2st_score")
    if (
        posterior_sbc_error is None
        or float(posterior_sbc_error) > coverage_tolerance
        or tarp_coverage_error is None
        or float(tarp_coverage_error) > coverage_tolerance
        or local_c2st_score is None
        or float(local_c2st_score) > 0.6
    ):
        failure_modes.append("local_miscalibration")
    ppc_mahalanobis = diagnostics.get("ppc_mahalanobis")
    if ppc_mahalanobis is None or float(ppc_mahalanobis) > 2.5:
        failure_modes.append("structural_misspecification")
    failure_modes = list(dict.fromkeys(failure_modes))
    actions = []
    if any(mode in failure_modes for mode in ("regime_context_missing", "regime_extrapolation")):
        actions.append("expand_regime_support")
    if "unreachable_observation" in failure_modes:
        actions.append("add_adjustment_parameter")
    if "local_miscalibration" in failure_modes:
        actions.append("increase_regime_local_simulations")
    if "structural_misspecification" in failure_modes:
        actions.append("switch_to_generalized_bayes")
    diagnostic = SimulatorDiagnosticArtifact(
        observed_regime=dict(observed_regime),
        support_quantile=support_quantile,
        knn_radius_mahalanobis=knn_radius,
        effective_local_simulations=int(float(diagnostics.get("effective_local_simulations", 0))),
        local_c2st_score=None if local_c2st_score is None else float(local_c2st_score),
        posterior_sbc_error=None if posterior_sbc_error is None else float(posterior_sbc_error),
        tarp_coverage_error=None if tarp_coverage_error is None else float(tarp_coverage_error),
        ppc_mahalanobis=None if ppc_mahalanobis is None else float(ppc_mahalanobis),
        status="fail" if failure_modes else "pass",
        failure_mode=tuple(failure_modes),
        recommended_action=tuple(actions),
    )
    return canonical_simulator_diagnostic_artifact(diagnostic)


def _sample_intervals(
    *,
    samples: np.ndarray,
    parameter_names: list[str],
    credible_mass: float,
    weights: np.ndarray | None = None,
) -> dict[str, tuple[float, float]]:
    alpha = max(1e-6, 1.0 - float(credible_mass))
    intervals: dict[str, tuple[float, float]] = {}
    for idx, name in enumerate(parameter_names):
        lower, upper = weighted_quantile(
            samples[:, idx],
            [alpha / 2.0, 1.0 - alpha / 2.0],
            sample_weight=weights,
        )
        intervals[str(name)] = (float(lower), float(upper))
    return intervals


def _normalized_mean_shift(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref_mean = np.mean(reference, axis=0)
    cand_mean = np.mean(candidate, axis=0)
    ref_scale = np.std(reference, axis=0, ddof=1)
    ref_scale = np.where(ref_scale > 1e-9, ref_scale, 1.0)
    return float(np.max(np.abs(cand_mean - ref_mean) / ref_scale))


def _relative_covariance_error(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref_cov = np.atleast_2d(np.cov(reference, rowvar=False))
    cand_cov = np.atleast_2d(np.cov(candidate, rowvar=False))
    denominator = max(float(np.linalg.norm(ref_cov)), 1e-12)
    return float(np.linalg.norm(cand_cov - ref_cov) / denominator)


def _split_interval_shift_max(
    *,
    samples: np.ndarray,
    parameter_names: list[str],
    credible_mass: float,
) -> float:
    if samples.shape[0] < 8:
        return float("inf")
    midpoint = samples.shape[0] // 2
    first = _sample_intervals(
        samples=samples[:midpoint],
        parameter_names=parameter_names,
        credible_mass=credible_mass,
    )
    second = _sample_intervals(
        samples=samples[midpoint:],
        parameter_names=parameter_names,
        credible_mass=credible_mass,
    )
    return relative_interval_shift_max(first, second)


def _stein_ksd_rbf(
    *,
    particles: np.ndarray,
    scores: np.ndarray,
    bandwidth: float,
) -> float:
    if particles.shape[0] < 2:
        return float("inf")
    safe_bandwidth = max(float(bandwidth), 1e-6)
    diffs = particles[:, None, :] - particles[None, :, :]
    dist_sq = np.sum(diffs * diffs, axis=-1)
    kernel = np.exp(-dist_sq / safe_bandwidth)
    score_dot = scores @ scores.T
    score_grad_y = (2.0 / safe_bandwidth) * np.einsum("id,ijd->ij", scores, diffs)
    score_grad_x = -(2.0 / safe_bandwidth) * np.einsum("jd,ijd->ij", scores, diffs)
    trace_term = (
        (2.0 * particles.shape[1] / safe_bandwidth)
        - (4.0 * dist_sq / (safe_bandwidth * safe_bandwidth))
    ) * kernel
    stein_kernel = kernel * score_dot + kernel * score_grad_y + kernel * score_grad_x + trace_term
    return float(np.sqrt(max(float(np.mean(stein_kernel)), 0.0)))


def _logsumexp(values: np.ndarray, axis: int | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    max_value = np.max(arr, axis=axis, keepdims=True)
    stable = np.exp(arr - max_value)
    result = np.log(np.sum(stable, axis=axis, keepdims=True)) + max_value
    if axis is None:
        return np.asarray(result.reshape(()), dtype=float)
    return np.squeeze(result, axis=axis)


def _linear_regression_grad_particles(
    particles: np.ndarray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> np.ndarray:
    gradients = np.zeros_like(particles, dtype=float)
    prior_var = max(prior_scale * prior_scale, 1e-9)
    for idx, theta in enumerate(particles):
        intercept = float(theta[0])
        beta = theta[1:-1]
        log_sigma = float(theta[-1])
        sigma = float(np.exp(np.clip(log_sigma, -20.0, 20.0)))
        residual = y - (intercept + x @ beta)
        inv_sigma_sq = 1.0 / max(sigma * sigma, 1e-9)
        gradients[idx, 0] = float(np.sum(residual) * inv_sigma_sq - intercept / prior_var)
        gradients[idx, 1:-1] = (x.T @ residual) * inv_sigma_sq - beta / prior_var
        gradients[idx, -1] = (
            -float(y.shape[0]) + float(np.sum(residual**2) * inv_sigma_sq) - log_sigma / prior_var
        )
    return gradients


def _median_bandwidth(particles: np.ndarray) -> float:
    diffs = particles[:, None, :] - particles[None, :, :]
    dist_sq = np.sum(diffs * diffs, axis=-1)
    positive = dist_sq[dist_sq > 0.0]
    if positive.size == 0:
        return 1.0
    median = float(np.median(positive))
    return max(median / np.log(particles.shape[0] + 1.0), 1e-6)


@foundry_method(
    namespace="bayesian.approximation",
    version="1.0.0",
    tags={"bayesian", "expectation-propagation", "ep", "structural", "uncertainty"},
)
class ExpectationPropagationGaussianEstimator:
    """Combine Gaussian site approximations into a posterior approximation; this is EP for Gaussian sites, not arbitrary black-box EP."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "ep"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="expectation_propagation_gaussian",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "site_means",
                    SlotType.MATRIX,
                    Unit("parameter", "value"),
                    shape=("n_sites", "n_parameters"),
                ),
                SlotSpec(
                    "site_variances",
                    SlotType.MATRIX,
                    Unit("variance", "value"),
                    shape=("n_sites", "n_parameters"),
                ),
            }
        ),
        output_slots=_posterior_output_slots(),
        parameters=(
            ParameterSpec(name="prior_mean", default=None),
            ParameterSpec(name="prior_variance", default=None),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Expectation-propagation style product of Gaussian site approximations.",
        tags=frozenset({"bayesian", "expectation-propagation", "ep", "structural", "uncertainty"}),
        when_to_use="Distributed or factorized Gaussian site approximations where EP sites are already computed.",
        when_not_to_use="Non-Gaussian site approximations that require iterative moment projection.",
        citations=(
            "Minka, T. P. (2001). Expectation propagation for approximate Bayesian inference. UAI.",
        ),
        output_interpretation="Gaussian posterior approximation obtained by multiplying prior and site precisions.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        site_means = np.asarray(state["site_means"], dtype=float)
        site_vars = np.asarray(state["site_variances"], dtype=float)
        if site_means.ndim != 2 or site_vars.shape != site_means.shape:
            raise ValueError("site_means and site_variances must be aligned 2D arrays")
        if not np.all(np.isfinite(site_means)) or not np.all(np.isfinite(site_vars)):
            raise ValueError("site means/variances must be finite")
        if np.any(site_vars <= 0.0):
            raise ValueError("site_variances must be strictly positive")
        n_params = site_means.shape[1]
        prior_mean = params.get("prior_mean")
        prior_var = params.get("prior_variance")
        prior_mean_arr = (
            np.zeros(n_params, dtype=float)
            if prior_mean is None
            else np.broadcast_to(np.asarray(prior_mean, dtype=float), (n_params,))
        )
        prior_var_arr = (
            np.full(n_params, 1e6, dtype=float)
            if prior_var is None
            else np.broadcast_to(np.asarray(prior_var, dtype=float), (n_params,))
        )
        if np.any(prior_var_arr <= 0.0):
            raise ValueError("prior_variance must be strictly positive")
        precision = (1.0 / prior_var_arr) + np.sum(1.0 / site_vars, axis=0)
        posterior_var = 1.0 / precision
        posterior_mean = posterior_var * (
            prior_mean_arr / prior_var_arr + np.sum(site_means / site_vars, axis=0)
        )
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        site_precision = 1.0 / site_vars
        cavity_precision = precision[None, :] - site_precision
        site_residual = (site_means - posterior_mean[None, :]) / np.sqrt(
            np.maximum(site_vars + posterior_var[None, :], 1e-12)
        )
        site_centered = site_residual - np.mean(site_residual, axis=0, keepdims=True)
        site_scale = np.std(site_centered, axis=0, ddof=1)
        site_scale = np.where(site_scale > 1e-9, site_scale, 1.0)
        standardized = site_centered / site_scale
        site_skewness_proxy = float(np.max(np.abs(np.mean(standardized**3, axis=0))))
        site_kurtosis_proxy = float(np.max(np.abs(np.mean(standardized**4, axis=0) - 3.0)))
        base_diagnostics = {
            "num_sites": float(site_means.shape[0]),
            "cavity_precision_min": float(np.min(cavity_precision)),
            "site_precision_cv": float(
                np.max(
                    np.std(site_precision, axis=0, ddof=1)
                    / np.maximum(np.mean(site_precision, axis=0), 1e-9)
                )
            )
            if site_precision.shape[0] > 1
            else 0.0,
            "site_mean_z_residual_max": float(np.max(np.abs(site_residual))),
            "site_skewness_proxy": site_skewness_proxy,
            "site_kurtosis_proxy": site_kurtosis_proxy,
        }
        base_metadata = {
            "approximation_family": "gaussian_site_product",
            "num_sites": int(site_means.shape[0]),
        }
        diagnostics, metadata = _apply_truthfulness_hints(
            diagnostics=base_diagnostics,
            metadata=base_metadata,
            sources=(state, params),
        )
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        samples = rng.normal(
            loc=posterior_mean,
            scale=np.sqrt(np.maximum(posterior_var, 1e-12)),
            size=(max(64, site_means.shape[0] * 8), n_params),
        )
        names = [
            str(item)
            for item in state.get("parameter_names", [f"theta_{idx}" for idx in range(n_params)])
        ]
        if len(names) != n_params:
            names = [f"theta_{idx}" for idx in range(n_params)]
        posterior = _posterior_from_samples(
            method_name="expectation_propagation_gaussian",
            samples=samples,
            credible_mass=credible_mass,
            parameter_names=names,
            metadata=metadata,
            diagnostics=diagnostics,
        )
        return {
            "result": posterior,
            "posterior_samples": samples,
            "uncertainty_envelope": posterior.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="bayesian.variational",
    version="1.0.0",
    tags={"bayesian", "svgd", "regression", "tabular", "uncertainty"},
)
class SVGDRegressionEstimator:
    """Approximate a Bayesian linear-regression posterior with Stein variational gradient descent particles."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "svgd"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="svgd_regression",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=1.5),
            ParameterSpec(name="num_particles", default=48),
            ParameterSpec(name="num_steps", default=96),
            ParameterSpec(name="step_size", default=0.01),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Stein variational gradient descent approximation for Bayesian linear regression.",
        tags=frozenset({"bayesian", "svgd", "regression", "tabular", "uncertainty"}),
        when_to_use="Fast particle posterior approximation when MCMC is too slow and linear-Gaussian likelihood is acceptable.",
        when_not_to_use="Strongly multimodal or non-differentiable posteriors; use HMC/NUTS where exactness matters.",
        citations=(
            "Liu, Q. & Wang, D. (2016). Stein variational gradient descent: A general purpose Bayesian inference algorithm. NeurIPS.",
        ),
        output_interpretation="Particles approximate the coefficient posterior; intervals are empirical particle quantiles.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else fallback_state
        if isinstance(payload, Mapping):
            merged = dict(payload)
            merged.update(bound_inputs)
            return TabularData.model_validate(merged)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | TabularData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x = np.asarray(data.features, dtype=float)
        y = np.asarray(data.target, dtype=float)
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")
        _require_numpy_finite("features", x)
        _require_numpy_finite("target", y)
        prior_scale = max(1e-3, float(params.get("prior_scale", 1.5)))
        num_particles = max(8, int(params.get("num_particles", 48)))
        num_steps = max(1, int(params.get("num_steps", 96)))
        step_size = min(max(float(params.get("step_size", 0.01)), 1e-5), 0.2)
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        design = np.column_stack([np.ones(x.shape[0]), x])
        ols_coef = np.linalg.pinv(design) @ y
        residual = y - design @ ols_coef
        sigma0 = max(float(np.std(residual, ddof=max(design.shape[1], 1))), 0.1)
        center = np.concatenate([ols_coef, np.array([np.log(sigma0)], dtype=float)])
        particles = center + rng.normal(scale=0.15, size=(num_particles, center.shape[0]))
        for _ in range(num_steps):
            gradients = _linear_regression_grad_particles(
                particles,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            diffs = particles[:, None, :] - particles[None, :, :]
            bandwidth = _median_bandwidth(particles)
            kernel = np.exp(-np.sum(diffs * diffs, axis=-1) / bandwidth)
            attraction = kernel @ gradients
            repulsion = (2.0 / bandwidth) * np.sum(kernel[:, :, None] * (-diffs), axis=1)
            particles = particles + (step_size / num_particles) * (attraction + repulsion)
        posterior_samples = np.column_stack([particles[:, :-1], np.exp(particles[:, -1])])
        parameter_names = ["intercept", *(_feature_names(data)), "sigma"]
        final_gradients = _linear_regression_grad_particles(
            particles,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )

        def _particle_log_posterior(theta: np.ndarray) -> float:
            intercept = float(theta[0])
            beta = theta[1:-1]
            log_sigma = float(theta[-1])
            sigma = float(np.exp(np.clip(log_sigma, -20.0, 20.0)))
            residual = y - (intercept + x @ beta)
            prior_var = max(prior_scale * prior_scale, 1e-9)
            return float(
                -float(y.shape[0]) * np.log(max(sigma, 1e-12))
                - 0.5 * float(np.sum(residual**2)) / max(sigma * sigma, 1e-12)
                - 0.5
                * float(intercept * intercept + np.sum(beta**2) + log_sigma * log_sigma)
                / prior_var
            )

        log_weights = np.asarray(
            [_particle_log_posterior(theta) for theta in particles], dtype=float
        )
        normalized_weights = np.exp(log_weights - float(np.max(log_weights)))
        normalized_weights = normalized_weights / np.maximum(np.sum(normalized_weights), 1e-12)
        raw_intervals = _sample_intervals(
            samples=posterior_samples,
            parameter_names=parameter_names,
            credible_mass=credible_mass,
        )
        weighted_intervals = _sample_intervals(
            samples=posterior_samples,
            parameter_names=parameter_names,
            credible_mass=credible_mass,
            weights=normalized_weights,
        )
        base_diagnostics = {
            "num_particles": float(num_particles),
            "num_steps": float(num_steps),
            "ksd_rbf": _stein_ksd_rbf(
                particles=particles,
                scores=final_gradients,
                bandwidth=_median_bandwidth(particles),
            ),
            "unique_particle_fraction": float(
                np.unique(np.round(particles, decimals=4), axis=0).shape[0] / max(num_particles, 1)
            ),
            "split_interval_shift_max": _split_interval_shift_max(
                samples=posterior_samples,
                parameter_names=parameter_names,
                credible_mass=credible_mass,
            ),
            "posthoc_interval_shift_max": relative_interval_shift_max(
                raw_intervals, weighted_intervals
            ),
        }
        diagnostics, metadata = _apply_truthfulness_hints(
            diagnostics=base_diagnostics,
            metadata={
                "num_particles": num_particles,
                "num_steps": num_steps,
            },
            sources=((state if isinstance(state, Mapping) else {}), params),
        )
        posterior = _posterior_from_samples(
            method_name="svgd_regression",
            samples=posterior_samples,
            credible_mass=credible_mass,
            parameter_names=parameter_names,
            metadata=metadata,
            diagnostics=diagnostics,
        )
        coefficients = np.asarray(
            [posterior.posterior_means.get(name, 0.0) for name in _feature_names(data)],
            dtype=float,
        )
        predictions = posterior.posterior_means["intercept"] + x @ coefficients
        prediction_output = _build_prediction_result(
            method_name="svgd_regression",
            predictions=predictions,
            target=y,
            coefficients={
                "intercept": posterior.posterior_means["intercept"],
                **{name: posterior.posterior_means.get(name, 0.0) for name in _feature_names(data)},
            },
            model_info={"library": "numpy", "estimator": "SVGDRegression"},
            metadata={"num_particles": num_particles, "num_steps": num_steps},
        )
        return {
            "result": posterior,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior.to_uncertainty_envelope(param_name="sigma"),
        }


@foundry_method(
    namespace="bayesian.flow",
    version="1.0.0",
    tags={"bayesian", "normalizing-flow", "affine-flow", "structural", "uncertainty"},
)
class AffineNormalizingFlowPosteriorAdapter:
    """Fit a truthful affine normalizing-flow surrogate to posterior samples."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "flow"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="affine_normalizing_flow",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "posterior_samples",
                    SlotType.MATRIX,
                    Unit("posterior", "draw"),
                    shape=("n_samples", "n_parameters"),
                )
            }
        ),
        output_slots=_posterior_output_slots(),
        parameters=(
            ParameterSpec(name="num_flow_samples", default=256),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="jitter", default=1e-6),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Affine normalizing-flow posterior adapter fitted to existing posterior samples.",
        tags=frozenset(
            {"bayesian", "normalizing-flow", "affine-flow", "structural", "uncertainty"}
        ),
        when_to_use="Compress posterior samples into a lightweight affine flow baseline for replay and downstream sampling.",
        when_not_to_use="Need expressive nonlinear flows; use a dedicated trainable flow stack instead.",
        citations=(
            "Rezende, D. & Mohamed, S. (2015). Variational inference with normalizing flows. ICML.",
        ),
        output_interpretation="Generated samples preserve posterior mean/covariance through an affine Gaussianizing map; metadata marks this as an affine-flow baseline.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        samples = np.asarray(state["posterior_samples"], dtype=float)
        if samples.ndim == 1:
            samples = samples[:, None]
        if samples.ndim != 2 or samples.shape[0] < 4:
            raise ValueError("posterior_samples must be a 2D array with at least 4 rows")
        _require_numpy_finite("posterior_samples", samples)
        num_flow_samples = max(16, int(params.get("num_flow_samples", 256)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        jitter = max(float(params.get("jitter", 1e-6)), 1e-12)
        mean = np.mean(samples, axis=0)
        cov = np.cov(samples, rowvar=False)
        cov = np.atleast_2d(cov) + jitter * np.eye(samples.shape[1])
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        generated = rng.multivariate_normal(mean=mean, cov=cov, size=num_flow_samples)
        names = [
            str(item)
            for item in state.get(
                "parameter_names", [f"theta_{idx}" for idx in range(samples.shape[1])]
            )
        ]
        if len(names) != samples.shape[1]:
            names = [f"theta_{idx}" for idx in range(samples.shape[1])]
        source_intervals = _sample_intervals(
            samples=samples,
            parameter_names=names,
            credible_mass=credible_mass,
        )
        generated_intervals = _sample_intervals(
            samples=generated,
            parameter_names=names,
            credible_mass=credible_mass,
        )
        base_metadata = {
            "flow_family": "affine_gaussian",
            "source_num_samples": int(samples.shape[0]),
        }
        for key in ("source_truthfulness_tier", "source_truthfulness_receipt"):
            if key in state:
                base_metadata[key] = state[key]
        base_diagnostics = {
            "source_mean_shift_max": _normalized_mean_shift(samples, generated),
            "source_covariance_error_fro": _relative_covariance_error(samples, generated),
            "source_interval_shift_max": relative_interval_shift_max(
                source_intervals, generated_intervals
            ),
            "jacobian_condition_number": float(np.linalg.cond(cov)),
        }
        diagnostics, metadata = _apply_truthfulness_hints(
            diagnostics=base_diagnostics,
            metadata=base_metadata,
            sources=(state, params),
        )
        posterior = _posterior_from_samples(
            method_name="affine_normalizing_flow",
            samples=generated,
            credible_mass=credible_mass,
            parameter_names=names,
            metadata=metadata,
            diagnostics=diagnostics,
        )
        return {
            "result": posterior,
            "posterior_samples": generated,
            "uncertainty_envelope": posterior.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="bayesian.graphical",
    version="1.0.0",
    tags={"bayesian", "factor-graph", "belief-propagation", "network", "uncertainty"},
)
class FactorGraphBeliefPropagationEstimator:
    """Run loopy sum-product belief propagation on a pairwise discrete factor graph."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "factor_graph"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="factor_graph_belief_propagation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "unary_log_potentials",
                    SlotType.MATRIX,
                    Unit("log_potential", "value"),
                    shape=("n_variables", "n_states"),
                ),
                SlotSpec("edges", SlotType.MATRIX, Unit("edge", "id"), shape=("n_edges", 2)),
                SlotSpec(
                    "pairwise_log_potentials", SlotType.SCALAR, Unit("log_potential", "tensor")
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec.for_output_contract(
                    "result",
                    SlotType.SCALAR,
                    Unit("posterior", "json"),
                    output_contract=PosteriorResult,
                ),
                SlotSpec(
                    "marginals",
                    SlotType.MATRIX,
                    Unit("probability", "value"),
                    shape=("n_variables", "n_states"),
                ),
                SlotSpec(
                    "map_assignment", SlotType.VECTOR, Unit("state", "id"), shape=("n_variables",)
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="max_iter", default=64),
            ParameterSpec(name="damping", default=0.2),
            ParameterSpec(name="tol", default=1e-6),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Pairwise discrete factor-graph inference via loopy belief propagation.",
        tags=frozenset(
            {"bayesian", "factor-graph", "belief-propagation", "network", "uncertainty"}
        ),
        when_to_use="Discrete graphical-model inference where exact junction-tree inference is too expensive.",
        when_not_to_use="Continuous latent variables or graphs requiring guaranteed convergence/exact marginals.",
        citations=(
            "Kschischang, F. R., Frey, B. J. & Loeliger, H. A. (2001). Factor graphs and the sum-product algorithm. IEEE TIT.",
        ),
        output_interpretation="Approximate node marginals and MAP states; diagnostics include convergence delta.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        unary = np.asarray(state["unary_log_potentials"], dtype=float)
        edges = np.asarray(state["edges"], dtype=int)
        pairwise = np.asarray(state["pairwise_log_potentials"], dtype=float)
        if unary.ndim != 2:
            raise ValueError("unary_log_potentials must be a 2D array")
        if edges.ndim != 2 or edges.shape[1] != 2:
            raise ValueError("edges must have shape (n_edges, 2)")
        if pairwise.shape != (edges.shape[0], unary.shape[1], unary.shape[1]):
            raise ValueError(
                "pairwise_log_potentials must have shape (n_edges, n_states, n_states)"
            )
        _require_numpy_finite("unary_log_potentials", unary)
        _require_numpy_finite("pairwise_log_potentials", pairwise)
        if np.any(edges < 0) or np.any(edges >= unary.shape[0]):
            raise ValueError("edges contain variable indexes outside unary_log_potentials")
        max_iter = max(1, int(params.get("max_iter", 64)))
        damping = min(max(float(params.get("damping", 0.2)), 0.0), 0.99)
        tol = max(float(params.get("tol", 1e-6)), 0.0)
        n_edges, n_states = edges.shape[0], unary.shape[1]
        messages_forward = np.full((n_edges, n_states), -np.log(n_states), dtype=float)
        messages_backward = np.full((n_edges, n_states), -np.log(n_states), dtype=float)
        incident: list[list[tuple[int, int]]] = [[] for _ in range(unary.shape[0])]
        for edge_idx, (src, dst) in enumerate(edges):
            incident[int(src)].append((edge_idx, 1))
            incident[int(dst)].append((edge_idx, -1))
        visited = set()
        agenda = [0] if unary.shape[0] else []
        while agenda:
            node = agenda.pop()
            if node in visited:
                continue
            visited.add(node)
            for edge_idx, direction in incident[node]:
                neighbour = int(edges[edge_idx, 1] if direction == 1 else edges[edge_idx, 0])
                if neighbour not in visited:
                    agenda.append(neighbour)
        graph_exact_regime = bool(
            unary.shape[0] > 0 and n_edges == unary.shape[0] - 1 and len(visited) == unary.shape[0]
        )
        delta = float("inf")
        iterations = 0
        for iterations in range(1, max_iter + 1):
            next_forward = messages_forward.copy()
            next_backward = messages_backward.copy()
            for edge_idx, (src_raw, dst_raw) in enumerate(edges):
                src = int(src_raw)
                dst = int(dst_raw)
                src_belief = unary[src].copy()
                for other_edge, direction in incident[src]:
                    if other_edge == edge_idx:
                        continue
                    src_belief += (
                        messages_backward[other_edge]
                        if direction == 1
                        else messages_forward[other_edge]
                    )
                candidate_forward = _logsumexp(src_belief[:, None] + pairwise[edge_idx], axis=0)
                candidate_forward -= _logsumexp(candidate_forward)
                dst_belief = unary[dst].copy()
                for other_edge, direction in incident[dst]:
                    if other_edge == edge_idx:
                        continue
                    dst_belief += (
                        messages_backward[other_edge]
                        if direction == 1
                        else messages_forward[other_edge]
                    )
                candidate_backward = _logsumexp(dst_belief[None, :] + pairwise[edge_idx], axis=1)
                candidate_backward -= _logsumexp(candidate_backward)
                next_forward[edge_idx] = (
                    damping * messages_forward[edge_idx] + (1.0 - damping) * candidate_forward
                )
                next_backward[edge_idx] = (
                    damping * messages_backward[edge_idx] + (1.0 - damping) * candidate_backward
                )
            delta = max(
                float(np.max(np.abs(next_forward - messages_forward))),
                float(np.max(np.abs(next_backward - messages_backward))),
            )
            messages_forward = next_forward
            messages_backward = next_backward
            if delta <= tol:
                break
        log_marginals = unary.copy()
        for node_idx, incoming in enumerate(incident):
            for edge_idx, direction in incoming:
                log_marginals[node_idx] += (
                    messages_backward[edge_idx] if direction == 1 else messages_forward[edge_idx]
                )
            log_marginals[node_idx] -= _logsumexp(log_marginals[node_idx])
        marginals = np.exp(log_marginals)
        map_assignment = np.argmax(marginals, axis=1).astype(int)
        posterior = PosteriorResult(
            method_name="factor_graph_belief_propagation",
            posterior_means={
                f"variable_{idx}": float(np.sum(marginals[idx] * np.arange(n_states)))
                for idx in range(marginals.shape[0])
            },
            posterior_stds={
                f"variable_{idx}": float(
                    np.sqrt(
                        np.sum(
                            marginals[idx]
                            * (np.arange(n_states) - np.sum(marginals[idx] * np.arange(n_states)))
                            ** 2
                        )
                    )
                )
                for idx in range(marginals.shape[0])
            },
            credible_intervals={
                f"variable_{idx}": (float(map_assignment[idx]), float(map_assignment[idx]))
                for idx in range(marginals.shape[0])
            },
            diagnostics={
                "iterations": float(iterations),
                "final_delta": float(delta),
                "num_edges": float(n_edges),
                "num_states": float(n_states),
                **split_truthfulness_hints(extract_truthfulness_hints(state, params))[0],
            },
            metadata={
                "inference_family": "loopy_sum_product",
                "graph_exact_regime": graph_exact_regime,
                "graph_exact_tolerance": float(tol),
                **split_truthfulness_hints(extract_truthfulness_hints(state, params))[1],
            },
        )
        return {
            "result": posterior,
            "marginals": marginals,
            "map_assignment": map_assignment,
        }


class _SBIBase:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("sbi", "torch", "numpy")
    optional_deps: ClassVar[tuple[str, ...]] = ("sbi", "torch")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sbi_base",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "parameters",
                    SlotType.MATRIX,
                    Unit("parameter", "value"),
                    shape=("n_simulations", "n_parameters"),
                ),
                SlotSpec(
                    "simulations",
                    SlotType.MATRIX,
                    Unit("summary", "value"),
                    shape=("n_simulations", "n_summaries"),
                ),
                SlotSpec(
                    "observed_summary",
                    SlotType.VECTOR,
                    Unit("summary", "value"),
                    shape=("n_summaries",),
                ),
                SlotSpec(
                    "simulation_regimes",
                    SlotType.VECTOR,
                    Unit("regime", "json"),
                    shape=("n_simulations",),
                ),
                SlotSpec(
                    "observed_regime",
                    SlotType.SCALAR,
                    Unit("regime", "json"),
                ),
                SlotSpec(
                    "simulator_diagnostic",
                    SlotType.SCALAR,
                    Unit("diagnostic", "json"),
                    contract_id=SimulatorDiagnosticArtifact.contract_id,
                ),
            }
        ),
        output_slots=_sbi_output_slots(),
        parameters=(
            ParameterSpec(name="runtime_backend", default="auto"),
            ParameterSpec(name="num_training_epochs", default=64),
            ParameterSpec(name="num_posterior_samples", default=256),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    @classmethod
    def _run(
        cls, state: Mapping[str, Any], params: Mapping[str, Any], *, algorithm: str
    ) -> dict[str, Any]:
        _require_backend(params, "sbi", method_variant=algorithm)
        parameter_draws, simulations, observed_summary = _coerce_sbi_payload(state)
        num_training_epochs = max(1, int(params.get("num_training_epochs", 64)))
        num_posterior_samples = max(32, int(params.get("num_posterior_samples", 256)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        contract_metadata = _sbi_contract_metadata(cls.metadata)
        observed_regime = _observed_regime_from_sources((state, params))
        simulation_regimes = _simulation_regimes_from_sources(
            (state, params),
            n_rows=parameter_draws.shape[0],
        )
        if observed_regime:
            contract_metadata["observed_regime"] = observed_regime
        recommended_budget = _sbi_recommended_local_budget(
            parameter_dimension=parameter_draws.shape[1],
            metadata=contract_metadata,
        )
        threshold_payload = cls.metadata.diagnostic_contract.get("thresholds", {})
        min_local = int(
            threshold_payload.get(
                "min_effective_local_simulations",
                _SBI_DIAGNOSTIC_CONTRACT["thresholds"]["min_effective_local_simulations"],
            )
        )
        training_parameters, training_simulations, regime_diagnostics = _sbi_regime_training_view(
            parameters=parameter_draws,
            simulations=simulations,
            observed_regime=observed_regime,
            simulation_regimes=simulation_regimes,
            min_local=min_local,
        )
        samples = _sbi_infer(
            algorithm=algorithm,
            parameters=training_parameters,
            simulations=training_simulations,
            observed_summary=observed_summary,
            num_posterior_samples=num_posterior_samples,
            num_training_epochs=num_training_epochs,
            seed=int(params.get("__seed__", 0)),
        )
        parameter_names = [
            str(item)
            for item in state.get(
                "parameter_names",
                [f"theta_{idx}" for idx in range(samples.shape[1])],
            )
        ]
        if len(parameter_names) != samples.shape[1]:
            parameter_names = [f"theta_{idx}" for idx in range(samples.shape[1])]
        base_diagnostics = _sbi_simulation_distance_diagnostics(
            parameters=training_parameters,
            simulations=training_simulations,
            observed_summary=observed_summary,
            samples=samples,
        )
        base_diagnostics.update(
            {
                "total_simulations": float(parameter_draws.shape[0]),
                "training_simulations": float(training_parameters.shape[0]),
                "recommended_effective_local_simulations": float(recommended_budget),
                **{key: float(value) for key, value in regime_diagnostics.items()},
            }
        )
        diagnostics, metadata = _apply_truthfulness_hints(
            diagnostics=base_diagnostics,
            metadata={
                "sbi_algorithm": algorithm.upper(),
                "runtime_backend_used": "sbi",
                "num_training_epochs": num_training_epochs,
                "summary_dimension": int(training_simulations.shape[1]),
                "observed_summary": observed_summary.tolist(),
                **contract_metadata,
            },
            sources=(state, params),
        )
        diagnostics, metadata, simulator_diagnostic_ref = _merge_simulator_diagnostic(
            diagnostics=diagnostics,
            metadata=metadata,
            sources=(state, params),
        )
        if "simulator_diagnostic" in metadata and simulator_diagnostic_ref is None:
            simulator_diagnostic_ref, simulator_diagnostic, simulator_diagnostic_hash = (
                canonical_simulator_diagnostic_artifact(metadata["simulator_diagnostic"])
            )
            metadata["simulator_diagnostic"] = simulator_diagnostic
            metadata["simulator_diagnostic_ref"] = simulator_diagnostic_ref
            metadata["simulator_diagnostic_hash"] = simulator_diagnostic_hash
        elif "simulator_diagnostic" not in metadata:
            simulator_diagnostic_ref, simulator_diagnostic, simulator_diagnostic_hash = (
                _build_sbi_diagnostic_artifact(
                    observed_regime=observed_regime,
                    diagnostics=diagnostics,
                    metadata=metadata,
                )
            )
            metadata["simulator_diagnostic"] = simulator_diagnostic
            metadata["simulator_diagnostic_ref"] = simulator_diagnostic_ref
            metadata["simulator_diagnostic_hash"] = simulator_diagnostic_hash
            metadata["simulator_diagnostic_status"] = simulator_diagnostic.get("status")
            metadata["failure_mode"] = list(simulator_diagnostic.get("failure_mode", ()))
        posterior = _posterior_from_samples(
            method_name=f"simulation_based_{algorithm}",
            samples=samples,
            credible_mass=credible_mass,
            parameter_names=parameter_names,
            metadata=metadata,
            diagnostics=diagnostics,
            simulator_diagnostic_ref=simulator_diagnostic_ref,
        )
        return {
            "result": posterior,
            "posterior_samples": samples,
            "simulator_diagnostic": metadata.get("simulator_diagnostic"),
            "simulator_diagnostic_ref": simulator_diagnostic_ref,
            "uncertainty_envelope": posterior.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="bayesian.sbi",
    version="1.0.0",
    tags={"bayesian", "sbi", "npe", "likelihood-free", "structural"},
)
class SimulationBasedNPEEstimator(_SBIBase):
    """Run neural posterior estimation for likelihood-free policy simulators; requires the real `sbi` runtime."""

    method_variant: ClassVar[str] = "npe"
    signature: ClassVar[MethodSignature] = replace(_SBIBase.signature, name="npe")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simulation-based neural posterior estimation using the installed SBI stack.",
        tags=frozenset({"bayesian", "sbi", "npe", "likelihood-free", "structural"}),
        when_to_use="Likelihood-free calibration where simulator summaries, parameter draws, observed regime context, and regime-local diagnostic artifacts are available.",
        when_not_to_use="Installed runtime lacks sbi/torch, the prior/simulation design is poorly specified, or observed policy regimes are not declared and locally supported.",
        citations=(
            "Papamakarios, G. & Murray, I. (2016). Fast epsilon-free inference of simulation models with Bayesian conditional density estimation. NeurIPS.",
        ),
        simulator_regime_schema=_SBI_SIMULATOR_REGIME_SCHEMA,
        summary_schema_ref=_SBI_SUMMARY_SCHEMA_REF,
        identifiable_target=_SBI_IDENTIFIABLE_TARGET,
        coverage_contract=_SBI_COVERAGE_CONTRACT,
        diagnostic_contract=_SBI_DIAGNOSTIC_CONTRACT,
        output_interpretation="Posterior samples over simulator parameters conditioned on observed summary statistics and the declared regime context.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return SimulationBasedNPEEstimator._run(state, params, algorithm="npe")


@foundry_method(
    namespace="bayesian.sbi",
    version="1.0.0",
    tags={"bayesian", "sbi", "nle", "likelihood-free", "structural"},
)
class SimulationBasedNLEEstimator(_SBIBase):
    """Run neural likelihood estimation for likelihood-free policy simulators; requires the real `sbi` runtime."""

    method_variant: ClassVar[str] = "nle"
    signature: ClassVar[MethodSignature] = replace(_SBIBase.signature, name="nle")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simulation-based neural likelihood estimation using the installed SBI stack.",
        tags=frozenset({"bayesian", "sbi", "nle", "likelihood-free", "structural"}),
        when_to_use="Likelihood-free policy models where likelihood estimation is preferable and regime-local simulator diagnostics certify the observed context.",
        when_not_to_use="Installed runtime lacks sbi/torch, posterior sampling through the learned likelihood is ill-conditioned, or simulator support around the observed regime is not certified.",
        citations=("Papamakarios, G. et al. (2019). Sequential neural likelihood. AISTATS.",),
        simulator_regime_schema=_SBI_SIMULATOR_REGIME_SCHEMA,
        summary_schema_ref=_SBI_SUMMARY_SCHEMA_REF,
        identifiable_target=_SBI_IDENTIFIABLE_TARGET,
        coverage_contract=_SBI_COVERAGE_CONTRACT,
        diagnostic_contract=_SBI_DIAGNOSTIC_CONTRACT,
        output_interpretation="Posterior samples drawn through the learned likelihood conditioned on observed summaries and declared regime context.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return SimulationBasedNLEEstimator._run(state, params, algorithm="nle")


@foundry_method(
    namespace="bayesian.sbi",
    version="1.0.0",
    tags={"bayesian", "sbi", "nre", "likelihood-free", "structural"},
)
class SimulationBasedNREEstimator(_SBIBase):
    """Run neural ratio estimation for likelihood-free policy simulators; requires the real `sbi` runtime."""

    method_variant: ClassVar[str] = "nre"
    signature: ClassVar[MethodSignature] = replace(_SBIBase.signature, name="nre")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simulation-based neural ratio estimation using the installed SBI stack.",
        tags=frozenset({"bayesian", "sbi", "nre", "likelihood-free", "structural"}),
        when_to_use="Likelihood-free policy models where ratio estimation is more stable and regime-local support/calibration diagnostics are available.",
        when_not_to_use="Installed runtime lacks sbi/torch, simulator coverage around observed summaries is weak, or policy-regime drift is not represented in the conditioning context.",
        citations=(
            "Hermans, J., Begy, V. & Louppe, G. (2020). Likelihood-free MCMC with amortized approximate ratio estimators. ICML.",
        ),
        simulator_regime_schema=_SBI_SIMULATOR_REGIME_SCHEMA,
        summary_schema_ref=_SBI_SUMMARY_SCHEMA_REF,
        identifiable_target=_SBI_IDENTIFIABLE_TARGET,
        coverage_contract=_SBI_COVERAGE_CONTRACT,
        diagnostic_contract=_SBI_DIAGNOSTIC_CONTRACT,
        output_interpretation="Posterior samples obtained from learned likelihood-to-evidence ratio estimates conditioned on observed summaries and declared regime context.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return SimulationBasedNREEstimator._run(state, params, algorithm="nre")


def _bart_prior_sensitivity_report(
    *,
    x: np.ndarray,
    y: np.ndarray,
    predictive_mean_draws: np.ndarray,
    credible_intervals: Mapping[str, tuple[float, float]],
    num_trees: int,
    credible_mass: float,
    params: Mapping[str, Any],
) -> Any:
    seed = int(params.get("__seed__", params.get("seed", 0))) + 4409
    rng = np.random.default_rng(seed)
    n_simulations = max(32, int(params.get("prior_predictive_simulations", 96)))
    function_scale = max(float(np.std(y, ddof=1)) if y.shape[0] > 1 else 1.0, 1e-3)
    simulations, tree_summary = simulate_bart_prior_predictive(
        x,
        num_trees=num_trees,
        tree_split_alpha=float(params.get("tree_split_alpha", params.get("a", 0.95))),
        tree_split_beta=float(params.get("tree_split_beta", params.get("b", 2.0))),
        leaf_scale_k=float(params.get("leaf_scale_k", params.get("k", 2.0))),
        function_scale=function_scale,
        noise_scale=function_scale,
        n_simulations=n_simulations,
        rng=rng,
    )
    conditioning_mode = DataConditioningMode(
        str(params.get("data_conditioning_mode", DataConditioningMode.INVALID.value))
    )
    admissible = build_admissible_prior_class(
        BayesianPolicyModelFamily.BART,
        hyperparameters={
            **tree_summary,
            "uses_outcome_to_set_prior": True,
            "data_conditioning_mode": conditioning_mode,
        },
        policy_context={
            "terminal_nodes_max": float(params.get("terminal_nodes_max", 8.0)),
            "auditable": True,
        },
        prior_predictive_simulations=simulations,
    )
    prior_predictive = prior_predictive_rank_test(
        y,
        simulations,
        alpha=float(params.get("prior_predictive_alpha", 0.05)),
        model_family=BayesianPolicyModelFamily.BART,
        features=x,
        conditioned_on=("covariates", "sampling_design"),
    )
    baseline_interval = credible_intervals["posterior_predictive_mean"]
    baseline_center = (baseline_interval[0] + baseline_interval[1]) / 2.0
    baseline_half_width = max((baseline_interval[1] - baseline_interval[0]) / 2.0, 1e-12)
    points = tuple(
        SensitivityCurvePoint(
            hyperparameter="leaf_scale_k",
            multiplier=multiplier,
            interval=(
                float(baseline_center - baseline_half_width * multiplier),
                float(baseline_center + baseline_half_width * multiplier),
            ),
            half_width=float(baseline_half_width * multiplier),
            refit_required=True,
        )
        for multiplier in (0.5, 2.0)
    )
    sensitivity = build_sensitivity_record_from_intervals(
        estimand_id="posterior_predictive_mean",
        baseline_interval=baseline_interval,
        perturbation_intervals=points,
        credible_interval_level=credible_mass,
    ).model_copy(update={"warnings": ("bart_prior_sensitivity_requires_refit",)})
    return assemble_prior_sensitivity_report(
        model_family=BayesianPolicyModelFamily.BART,
        selected_prior_id="bart_response_scaled_sum_of_trees_prior_v1",
        admissible_prior_class=admissible,
        prior_predictive_check=prior_predictive,
        sensitivity=sensitivity,
        readiness_tier_requested=str(params.get("prior_sensitivity_readiness_tier", "tier_1")),
        uses_outcome_to_set_prior=True,
        data_conditioning_mode=conditioning_mode,
        metadata={
            "estimand_id": "posterior_predictive_mean",
            "prior_predictive_seed": seed,
            "predictive_draws": int(predictive_mean_draws.shape[0]),
        },
        warnings=sensitivity.warnings,
    )


@foundry_method(
    namespace="bayesian.nonparametric",
    version="1.0.0",
    tags={"bayesian", "bart", "nonparametric", "heterogeneity"},
)
class BayesianBARTRegressorEstimator:
    """Fit Bayesian additive regression trees for nonlinear policy heterogeneity; requires PyMC-BART."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("pymc", "pymc-bart", "arviz", "numpy")
    optional_deps: ClassVar[tuple[str, ...]] = ("pymc", "pymc-bart", "arviz")
    method_variant: ClassVar[str] = "bart"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bart_regression",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="runtime_backend", default="auto"),
            ParameterSpec(name="num_trees", default=50),
            ParameterSpec(name="num_warmup", default=128),
            ParameterSpec(name="num_samples", default=256),
            ParameterSpec(name="num_chains", default=2),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Bayesian additive regression trees for nonlinear heterogeneous policy response surfaces.",
        tags=frozenset({"bayesian", "bart", "nonparametric", "heterogeneity"}),
        when_to_use="Nonlinear policy heterogeneity with enough observations and an installed PyMC-BART runtime.",
        when_not_to_use="PyMC-BART is unavailable, exact structural interpretation is required, or dataset is too small for tree ensembles.",
        citations=(
            "Chipman, H. A., George, E. I. & McCulloch, R. E. (2010). BART: Bayesian additive regression trees. Annals of Applied Statistics.",
        ),
        output_interpretation="Posterior predictive draws and credible intervals over nonlinear response surfaces.",
        typical_min_obs=80,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else fallback_state
        if isinstance(payload, Mapping):
            merged = dict(payload)
            merged.update(bound_inputs)
            return TabularData.model_validate(merged)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | TabularData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        _require_backend(params, "pymc_bart")
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x = np.asarray(data.features, dtype=float)
        y = np.asarray(data.target, dtype=float)
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")
        _require_numpy_finite("features", x)
        _require_numpy_finite("target", y)
        try:
            import pymc as pm
            import pymc_bart as pmb
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "BART runtime requires installed 'pymc' and 'pymc_bart' packages"
            ) from exc

        num_trees = max(5, int(params.get("num_trees", 50)))
        num_warmup = max(32, int(params.get("num_warmup", 128)))
        num_samples = max(32, int(params.get("num_samples", 256)))
        num_chains = max(1, int(params.get("num_chains", 2)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        seed = int(params.get("__seed__", 0))
        with pm.Model() as model:
            sigma = pm.HalfNormal("sigma", sigma=max(float(np.std(y, ddof=1)), 1e-3))
            mu = pmb.BART("mu", X=x, Y=y, m=num_trees)
            pm.Normal("obs", mu=mu, sigma=sigma, observed=y)
            idata = pm.sample(
                draws=num_samples,
                tune=num_warmup,
                chains=num_chains,
                random_seed=seed,
                progressbar=False,
                compute_convergence_checks=False,
            )

        mu_draws = np.asarray(idata.posterior["mu"], dtype=float).reshape(-1, x.shape[0])
        sigma_draws = np.asarray(idata.posterior["sigma"], dtype=float).reshape(-1)
        predictions = np.mean(mu_draws, axis=0)
        posterior_means = {
            "posterior_predictive_mean": float(np.mean(predictions)),
            "sigma": float(np.mean(sigma_draws)),
        }
        posterior_stds = {
            "posterior_predictive_mean": float(np.std(np.mean(mu_draws, axis=1), ddof=1)),
            "sigma": float(np.std(sigma_draws, ddof=1)) if sigma_draws.shape[0] > 1 else 0.0,
        }
        alpha = max(1e-6, 1.0 - credible_mass)
        predictive_mean_draws = np.mean(mu_draws, axis=1)
        credible_intervals = {
            "posterior_predictive_mean": tuple(
                float(item)
                for item in np.quantile(predictive_mean_draws, [alpha / 2.0, 1.0 - alpha / 2.0])
            ),
            "sigma": tuple(
                float(item) for item in np.quantile(sigma_draws, [alpha / 2.0, 1.0 - alpha / 2.0])
            ),
        }
        decomposition = UncertaintyDecomposition.from_gaussian_components(
            metric_id="bart_prediction",
            point_estimate=float(np.mean(predictions)),
            confidence_level=credible_mass,
            epistemic_std=float(np.std(predictive_mean_draws, ddof=1))
            if predictive_mean_draws.shape[0] > 1
            else 0.0,
            aleatoric_std=float(np.mean(sigma_draws)) if sigma_draws.size else 0.0,
            metadata={
                "method_name": "bayesian_bart_regression",
                "runtime_backend_used": "pymc_bart",
            },
        )
        prediction_output = _build_prediction_result(
            method_name="bayesian_bart_regression",
            predictions=predictions,
            target=y,
            coefficients={},
            model_info={"library": "pymc_bart", "estimator": "BART"},
            metadata={
                "num_trees": num_trees,
                "num_samples": num_samples,
                "num_chains": num_chains,
                "runtime_backend_used": "pymc_bart",
            },
        )
        diagnostics = augment_sampler_diagnostics(
            {
                "posterior_predictive_mean": np.mean(
                    np.asarray(idata.posterior["mu"], dtype=float), axis=2
                ),
                "sigma": np.asarray(idata.posterior["sigma"], dtype=float),
            },
            diagnostics={
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "num_trees": float(num_trees),
            },
            num_chains=num_chains,
            num_samples=num_samples,
            credible_mass=credible_mass,
        )
        try:
            prior_sensitivity = _bart_prior_sensitivity_report(
                x=x,
                y=y,
                predictive_mean_draws=predictive_mean_draws,
                credible_intervals=credible_intervals,
                num_trees=num_trees,
                credible_mass=credible_mass,
                params=params,
            )
        except Exception as exc:
            prior_sensitivity = not_run_prior_sensitivity_report(
                model_family=BayesianPolicyModelFamily.BART,
                selected_prior_id="bart_response_scaled_sum_of_trees_prior_v1",
                admissible_prior_class_id="bart_sum_of_trees_policy_v1",
                reason=f"prior_sensitivity_gate_error:{type(exc).__name__}",
            )
        posterior = PosteriorResult(
            method_name="bayesian_bart_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics=diagnostics,
            sampler_family="mcmc",
            sampler_kernel="bart",
            metadata={
                "feature_names": _feature_names(data),
                "uncertainty_decomposition": decomposition.as_dict(),
                "runtime_backend_used": "pymc_bart",
            },
            prior_sensitivity=prior_sensitivity,
        )
        return {
            "result": posterior,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior.to_uncertainty_envelope(
                param_name="posterior_predictive_mean"
            ),
        }


__all__ = [
    "AffineNormalizingFlowPosteriorAdapter",
    "BayesianBARTRegressorEstimator",
    "ExpectationPropagationGaussianEstimator",
    "FactorGraphBeliefPropagationEstimator",
    "SVGDRegressionEstimator",
    "SimulationBasedNLEEstimator",
    "SimulationBasedNPEEstimator",
    "SimulationBasedNREEstimator",
]
