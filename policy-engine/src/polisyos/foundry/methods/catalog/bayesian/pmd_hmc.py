"""PMD-HMC sampled-support multimodality diagnostics for posterior draws."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

from .protocols import (
    DetectedModesStatus,
    ModeWeightReliability,
    MultimodalityDowngrade,
    MultimodalityScope,
    MultimodalityState,
    MultimodalityStatus,
    MultimodalityTestMetadata,
    PolicyRelevanceClassification,
    PolicyRelevanceStatus,
    PosteriorModeSummary,
    PosteriorModeWeight,
    PosteriorReadiness,
    SamplerAdequacyStatus,
    _ess_for_dimension,
    _reshape_chain_array,
    _stack_posterior_chains,
)

PMD_HMC_VERSION = "0.2.0"
_DEFAULT_LIMITATIONS = (
    "Sample-only test cannot exclude unvisited modes.",
    "Mode count is a lower bound.",
    "Mode weights are observed draw fractions unless chains mix between modes or reweighting is validated.",
)


@dataclass(frozen=True, slots=True)
class _MatrixBlock:
    name: str
    scope: MultimodalityScope
    matrix: np.ndarray
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ViewSpec:
    kind: str
    direction: np.ndarray
    observer_quantile: float | None = None


@dataclass(frozen=True, slots=True)
class _ViewResult:
    statistic: float
    threshold: float
    left_fraction: float
    statistic_name: str
    spec: _ViewSpec


@dataclass(frozen=True, slots=True)
class _BlockAssessment:
    block: _MatrixBlock
    whitened: np.ndarray
    keep: np.ndarray
    retained_labels: tuple[str, ...]
    specs: tuple[_ViewSpec, ...]
    observed: _ViewResult
    p_global: float | None
    sample_size_used: int
    null_reference: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PmdHmcBenchmarkCase:
    """Small reproducible benchmark case for PMD-HMC detection boundaries."""

    case_id: str
    target_family: str
    dimension: int
    chains: int
    draws_per_chain: int
    separation: float = 0.0
    min_mode_weight: float = 0.50
    covariance_ratio: float = 1.0
    seed: int = 0


def _finite_float(value: Any) -> float | None:
    try:
        scalar = float(value)
    except (TypeError, ValueError):
        return None
    return scalar if np.isfinite(scalar) else None


def _first_metric(*sources: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    for source in sources:
        for key in keys:
            value = _finite_float(source.get(key))
            if value is not None and value >= 0.0:
                return value
    return None


def _parameter_labels(
    samples: Mapping[str, Any],
    *,
    num_chains: int,
    num_samples: int,
    prefix: str = "",
) -> list[str]:
    labels: list[str] = []
    for name in sorted(samples):
        arr = _reshape_chain_array(
            samples[name],
            num_chains=max(1, int(num_chains)),
            num_samples=max(1, int(num_samples)),
        )
        width = int(np.prod(arr.shape[2:]))
        base = f"{prefix}{name}"
        labels.extend([base] if width == 1 else [f"{base}_{idx}" for idx in range(width)])
    return labels


def _chain_matrix(
    samples: Mapping[str, Any],
    *,
    num_chains: int,
    num_samples: int,
    prefix: str = "",
) -> tuple[np.ndarray, tuple[str, ...], np.ndarray]:
    chains = _stack_posterior_chains(
        samples,
        num_chains=max(1, int(num_chains)),
        num_samples=max(1, int(num_samples)),
    )
    matrix = np.asarray(chains, dtype=float).reshape(chains.shape[0] * chains.shape[1], -1)
    labels = _parameter_labels(
        samples,
        num_chains=num_chains,
        num_samples=num_samples,
        prefix=prefix,
    )
    if len(labels) != matrix.shape[1]:
        labels = [f"{prefix}parameter_{idx}" for idx in range(matrix.shape[1])]
    finite_rows = np.all(np.isfinite(matrix), axis=1)
    return matrix[finite_rows], tuple(labels), finite_rows


def _extra_block(
    values: Mapping[str, Any] | None,
    *,
    num_chains: int,
    num_samples: int,
    name: str,
    scope: MultimodalityScope,
    prefix: str,
    finite_rows: np.ndarray,
) -> _MatrixBlock | None:
    if not values:
        return None
    matrix, labels, block_finite = _chain_matrix(
        values,
        num_chains=num_chains,
        num_samples=num_samples,
        prefix=prefix,
    )
    if block_finite.shape == finite_rows.shape and np.array_equal(block_finite, finite_rows):
        aligned = matrix
    else:
        raw = _stack_posterior_chains(
            values,
            num_chains=max(1, int(num_chains)),
            num_samples=max(1, int(num_samples)),
        ).reshape(num_chains * num_samples, -1)
        aligned = np.asarray(raw[finite_rows], dtype=float)
        aligned = aligned[np.all(np.isfinite(aligned), axis=1)]
    if aligned.shape[0] < 20 or aligned.shape[1] == 0:
        return None
    return _MatrixBlock(name=name, scope=scope, matrix=aligned, labels=labels)


def _sampler_adequacy(
    *,
    diagnostics: Mapping[str, Any],
    diagnostics_summary: Mapping[str, Any],
    diagnostic_gates: Mapping[str, Any],
    num_chains: int,
    num_samples: int,
) -> tuple[SamplerAdequacyStatus, bool, bool]:
    rhat_max = _first_metric(diagnostics_summary, diagnostics, keys=("max_rhat", "rhat_max"))
    bulk_ess_min = _first_metric(
        diagnostics_summary,
        diagnostics,
        keys=("min_bulk_ess", "ess_bulk_min", "bulk_ess_min"),
    )
    tail_ess_min = _first_metric(
        diagnostics_summary,
        diagnostics,
        keys=("min_tail_ess", "ess_tail_min", "tail_ess_min"),
    )
    divergences = _first_metric(diagnostics_summary, diagnostics, keys=("divergences",))
    bfmi_min = _first_metric(diagnostics_summary, diagnostics, keys=("min_bfmi", "bfmi_min"))
    treedepth_hits = _first_metric(
        diagnostics_summary,
        diagnostics,
        keys=("max_treedepth_hits", "treedepth_hits"),
    )
    chain_count = int(
        _first_metric(diagnostics_summary, diagnostics, keys=("num_monitored_chains", "num_chains"))
        or num_chains
    )
    total_draws = max(1, chain_count * max(1, int(num_samples)))
    treedepth_rate = None if treedepth_hits is None else float(treedepth_hits / total_draws)
    minimum_required_ess = max(100.0 * max(chain_count, 1), 20.0)

    gates = {str(key): bool(value) for key, value in diagnostic_gates.items()}
    if gates:
        low_ess = any(not gates.get(name, True) for name in ("bulk_ess", "tail_ess"))
        geometry_fail = any(
            not passed
            for name, passed in gates.items()
            if name not in {"bulk_ess", "tail_ess"}
        )
        passed = all(gates.values())
    else:
        low_ess = (
            (bulk_ess_min is not None and bulk_ess_min < minimum_required_ess)
            or (tail_ess_min is not None and tail_ess_min < minimum_required_ess)
        )
        geometry_fail = (
            chain_count < 4
            or (rhat_max is not None and rhat_max > 1.01)
            or (divergences is not None and divergences > 0.0)
            or (bfmi_min is not None and bfmi_min < 0.30)
            or (treedepth_hits is not None and treedepth_hits > 0.0)
        )
        passed = not low_ess and not geometry_fail

    return (
        SamplerAdequacyStatus(
            rhat_max=rhat_max,
            bulk_ess_min=bulk_ess_min,
            tail_ess_min=tail_ess_min,
            divergences=divergences,
            bfmi_min=bfmi_min,
            max_treedepth_saturation_rate=treedepth_rate,
            passed=passed,
        ),
        low_ess,
        geometry_fail,
    )


def _whiten_draws(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if matrix.ndim != 2 or matrix.shape[0] < 8:
        return np.zeros((0, 0), dtype=float), np.zeros(0, dtype=bool)
    variances = np.var(matrix, axis=0)
    keep = np.isfinite(variances) & (variances > 1e-12)
    if not np.any(keep):
        return np.zeros((matrix.shape[0], 0), dtype=float), keep
    selected = np.asarray(matrix[:, keep], dtype=float)
    center = np.median(selected, axis=0)
    centered = selected - center
    if selected.shape[1] == 1:
        scale = float(np.std(centered[:, 0], ddof=1))
        scale = scale if np.isfinite(scale) and scale > 1e-12 else 1.0
        return (centered / scale).reshape(selected.shape[0], 1), keep

    covariance = np.cov(centered, rowvar=False)
    covariance = np.atleast_2d(np.asarray(covariance, dtype=float))
    diagonal = np.diag(np.clip(np.diag(covariance), 1e-12, None))
    covariance = 0.9 * covariance + 0.1 * diagonal
    ridge = max(float(np.trace(covariance)) / max(covariance.shape[0], 1) * 1e-8, 1e-10)
    covariance = covariance + ridge * np.eye(covariance.shape[0])
    eigvals, eigvecs = np.linalg.eigh(covariance)
    eig_keep = np.isfinite(eigvals) & (eigvals > 1e-12)
    if not np.any(eig_keep):
        return np.zeros((matrix.shape[0], 0), dtype=float), keep
    whitening = eigvecs[:, eig_keep] / np.sqrt(eigvals[eig_keep])
    return centered @ whitening, keep


def _subsample_rows(matrix: np.ndarray, *, n_eff: float | None, rng: np.random.Generator) -> np.ndarray:
    if matrix.shape[0] == 0:
        return matrix
    target = int(round(float(n_eff))) if n_eff is not None and np.isfinite(n_eff) else matrix.shape[0]
    target = int(np.clip(target, min(matrix.shape[0], 20), matrix.shape[0]))
    if target >= matrix.shape[0]:
        return matrix
    indices = np.sort(rng.choice(matrix.shape[0], size=target, replace=False))
    return matrix[indices]


def _build_view_specs(
    *,
    dimension: int,
    view_count: int,
    rng: np.random.Generator,
) -> tuple[_ViewSpec, ...]:
    if dimension <= 0 or view_count <= 0:
        return ()
    specs: list[_ViewSpec] = []
    observer_quantiles = (0.80, 0.90, 0.95)
    axis_count = min(dimension, max(1, view_count // 4))
    for dim in range(axis_count):
        direction = np.zeros(dimension, dtype=float)
        direction[dim] = 1.0
        specs.append(_ViewSpec(kind="projection", direction=direction))
    while len(specs) < view_count:
        direction = rng.normal(size=dimension)
        norm = float(np.linalg.norm(direction))
        if not np.isfinite(norm) or norm <= 1e-12:
            continue
        direction = direction / norm
        if len(specs) % 2 == 0:
            specs.append(_ViewSpec(kind="projection", direction=direction))
        else:
            quantile = observer_quantiles[len(specs) % len(observer_quantiles)]
            specs.append(
                _ViewSpec(
                    kind="mahalanobis_observer_distance",
                    direction=direction,
                    observer_quantile=quantile,
                )
            )
    return tuple(specs)


def _view_values(matrix: np.ndarray, spec: _ViewSpec) -> np.ndarray:
    projected = np.asarray(matrix @ spec.direction, dtype=float)
    if spec.kind == "projection":
        return projected
    center = float(np.median(projected))
    radii = np.abs(projected - center)
    quantile = float(spec.observer_quantile or 0.90)
    target_radius = float(np.quantile(radii, np.clip(quantile, 0.0, 1.0)))
    observer_idx = int(np.argmin(np.abs(radii - target_radius)))
    return np.abs(projected - float(projected[observer_idx]))


@lru_cache(maxsize=1)
def _diptest_callable() -> Any | None:
    try:
        import diptest
    except Exception:
        return None
    return getattr(diptest, "diptest", None)


def _dip_statistic(values: np.ndarray) -> float | None:
    callable_ = _diptest_callable()
    if callable_ is None:
        return None
    arr = np.sort(np.asarray(values, dtype=float).reshape(-1))
    arr = arr[np.isfinite(arr)]
    if arr.shape[0] < 20:
        return None
    try:
        _, p_value = callable_(arr)
    except Exception:
        return None
    p_value = float(p_value)
    if not np.isfinite(p_value) or p_value <= 0.0:
        return 300.0
    return float(-np.log10(max(p_value, 1e-300)))


def _view_test_result(values: np.ndarray, *, w_min: float, spec: _ViewSpec) -> _ViewResult:
    arr = np.sort(np.asarray(values, dtype=float).reshape(-1))
    arr = arr[np.isfinite(arr)]
    n = arr.shape[0]
    if n < 20:
        return _ViewResult(
            statistic=0.0,
            threshold=0.0,
            left_fraction=0.0,
            statistic_name="insufficient_sample",
            spec=spec,
        )
    min_side = max(1, int(np.ceil(float(w_min) * n)))
    gaps = np.diff(arr)
    if gaps.size == 0 or 2 * min_side >= n:
        return _ViewResult(
            statistic=0.0,
            threshold=float(np.median(arr)),
            left_fraction=0.5,
            statistic_name="calibrated_projection_spacing",
            spec=spec,
        )
    start = min_side - 1
    stop = n - min_side
    eligible = gaps[start:stop]
    if eligible.size == 0:
        return _ViewResult(
            statistic=0.0,
            threshold=float(np.median(arr)),
            left_fraction=0.5,
            statistic_name="calibrated_projection_spacing",
            spec=spec,
        )
    local_idx = int(np.argmax(eligible)) + start
    max_gap = float(gaps[local_idx])
    baseline = float(np.median(np.maximum(gaps, 0.0)))
    if not np.isfinite(baseline) or baseline <= 1e-12:
        q05, q95 = np.quantile(arr, [0.05, 0.95])
        baseline = max(float(q95 - q05) / max(n, 1), 1e-12)
    gap_statistic = max_gap / baseline
    dip_statistic = _dip_statistic(arr)
    statistic = dip_statistic if dip_statistic is not None else gap_statistic
    threshold = float(0.5 * (arr[local_idx] + arr[local_idx + 1]))
    return _ViewResult(
        statistic=float(statistic) if np.isfinite(statistic) else 0.0,
        threshold=threshold,
        left_fraction=float((local_idx + 1) / n),
        statistic_name="hartigan_dip" if dip_statistic is not None else "calibrated_projection_spacing",
        spec=spec,
    )


def _best_view(
    matrix: np.ndarray,
    *,
    specs: tuple[_ViewSpec, ...],
    w_min: float,
) -> _ViewResult:
    if matrix.shape[0] < 20 or not specs:
        fallback = _ViewSpec(kind="projection", direction=np.ones(max(matrix.shape[1], 1)))
        return _ViewResult(
            statistic=0.0,
            threshold=0.0,
            left_fraction=0.0,
            statistic_name="insufficient_sample",
            spec=fallback,
        )
    best: _ViewResult | None = None
    for spec in specs:
        result = _view_test_result(_view_values(matrix, spec), w_min=w_min, spec=spec)
        if best is None or result.statistic > best.statistic:
            best = result
    if best is None:
        fallback = _ViewSpec(kind="projection", direction=np.ones(max(matrix.shape[1], 1)))
        return _ViewResult(
            statistic=0.0,
            threshold=0.0,
            left_fraction=0.0,
            statistic_name="insufficient_sample",
            spec=fallback,
        )
    return best


def _reference_draws(
    *,
    family: str,
    sample_size: int,
    dimension: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if family == "elliptical_student_t":
        df = 3.0
        draws = rng.standard_t(df=df, size=(sample_size, dimension))
        return draws / np.sqrt(df / (df - 2.0))
    return rng.normal(size=(sample_size, dimension))


def _global_p_value(
    observed: _ViewResult,
    *,
    dimension: int,
    sample_size: int,
    specs: tuple[_ViewSpec, ...],
    n_bootstrap: int,
    w_min: float,
    rng: np.random.Generator,
    reference_families: tuple[str, ...],
) -> float | None:
    if observed.statistic <= 0.0 or dimension <= 0 or sample_size < 20 or n_bootstrap <= 0:
        return None
    family_p_values: list[float] = []
    for family in reference_families:
        exceedances = 0
        for _ in range(int(n_bootstrap)):
            reference = _reference_draws(
                family=family,
                sample_size=sample_size,
                dimension=dimension,
                rng=rng,
            )
            if _best_view(reference, specs=specs, w_min=w_min).statistic >= observed.statistic:
                exceedances += 1
        family_p_values.append(float((exceedances + 1) / (int(n_bootstrap) + 1)))
    return max(family_p_values) if family_p_values else None


def _assess_block(
    block: _MatrixBlock,
    *,
    n_eff: float | None,
    view_count: int,
    n_bootstrap: int,
    w_min: float,
    rng: np.random.Generator,
    reference_families: tuple[str, ...],
) -> _BlockAssessment:
    whitened, keep = _whiten_draws(block.matrix)
    retained_labels = tuple(
        label for label, is_kept in zip(block.labels, keep, strict=False) if bool(is_kept)
    )
    test_matrix = _subsample_rows(whitened, n_eff=n_eff, rng=rng)
    specs = _build_view_specs(dimension=whitened.shape[1], view_count=int(view_count), rng=rng)
    observed = _best_view(test_matrix, specs=specs, w_min=w_min)
    p_global = _global_p_value(
        observed,
        dimension=whitened.shape[1],
        sample_size=int(test_matrix.shape[0]),
        specs=specs,
        n_bootstrap=int(n_bootstrap),
        w_min=w_min,
        rng=rng,
        reference_families=reference_families,
    )
    return _BlockAssessment(
        block=block,
        whitened=whitened,
        keep=keep,
        retained_labels=retained_labels,
        specs=specs,
        observed=observed,
        p_global=p_global,
        sample_size_used=int(test_matrix.shape[0]),
        null_reference=reference_families,
    )


def _best_assessment(assessments: Sequence[_BlockAssessment]) -> _BlockAssessment:
    with_p = [item for item in assessments if item.p_global is not None]
    if with_p:
        return min(with_p, key=lambda item: float(item.p_global))
    return max(assessments, key=lambda item: item.observed.statistic)


def _combine_global_p(assessments: Sequence[_BlockAssessment]) -> float | None:
    p_values = [float(item.p_global) for item in assessments if item.p_global is not None]
    if not p_values:
        return None
    return min(1.0, min(p_values) * len(p_values))


def _downgrade_for_state(state: MultimodalityState) -> MultimodalityDowngrade:
    if state is MultimodalityState.NOT_DETECTED_IN_VISITED_SUPPORT:
        return MultimodalityDowngrade(
            posterior_readiness=PosteriorReadiness.UNCHANGED,
            ordinary_mean_summary_allowed=True,
            mode_conditional_reporting_required=False,
            summary_policy="ordinary_posterior_summaries_allowed_with_unvisited_modes_caveat",
            recommendation_policy="single_policy_recommendation_allowed",
        )
    if state is MultimodalityState.AMBIGUOUS:
        return MultimodalityDowngrade(
            posterior_readiness=PosteriorReadiness.CAUTION,
            ordinary_mean_summary_allowed=False,
            mode_conditional_reporting_required=False,
            summary_policy="robust_intervals_required_no_mean_only_policy",
            recommendation_policy="no_policy_critical_mean_only_recommendation",
        )
    if state in {
        MultimodalityState.INCONCLUSIVE_SAMPLING_GEOMETRY,
        MultimodalityState.INCONCLUSIVE_LOW_ESS,
        MultimodalityState.INCONCLUSIVE_UNVISITED_MODES_POSSIBLE,
    }:
        return MultimodalityDowngrade(
            posterior_readiness=PosteriorReadiness.NOT_READY,
            ordinary_mean_summary_allowed=False,
            mode_conditional_reporting_required=False,
            summary_policy="diagnostics_only_refit_or_more_exploration_required",
            recommendation_policy="single_policy_recommendation_not_allowed",
        )
    if state is MultimodalityState.MULTIMODALITY_DETECTED_POLICY_INVARIANT:
        return MultimodalityDowngrade(
            posterior_readiness=PosteriorReadiness.CONDITIONAL,
            ordinary_mean_summary_allowed=False,
            mode_conditional_reporting_required=True,
            summary_policy="mode_conditional_and_mixture_summary_flagged",
            recommendation_policy="single_policy_allowed_only_if_mode_margin_holds",
        )
    if state is MultimodalityState.MULTIMODALITY_DETECTED_POLICY_RELEVANT:
        return MultimodalityDowngrade(
            posterior_readiness=PosteriorReadiness.REFUSE_SINGLE_POLICY,
            ordinary_mean_summary_allowed=False,
            mode_conditional_reporting_required=True,
            summary_policy="mode_conditional_scenario_report_required",
            recommendation_policy="single_policy_recommendation_not_allowed",
        )
    if state is MultimodalityState.MULTIMODALITY_DETECTED:
        return MultimodalityDowngrade(
            posterior_readiness=PosteriorReadiness.CAUTION,
            ordinary_mean_summary_allowed=False,
            mode_conditional_reporting_required=True,
            summary_policy="mode_conditional_reporting_required",
            recommendation_policy="policy_relevance_assessment_required_before_single_recommendation",
        )
    return MultimodalityDowngrade()


def _state_from_evidence(
    *,
    p_global: float | None,
    sampler_failed_geometry: bool,
    sampler_low_ess: bool,
    alpha_detect: float,
    alpha_warn: float,
) -> MultimodalityState:
    if sampler_failed_geometry:
        return MultimodalityState.INCONCLUSIVE_SAMPLING_GEOMETRY
    if sampler_low_ess:
        return MultimodalityState.INCONCLUSIVE_LOW_ESS
    if p_global is None:
        return MultimodalityState.AMBIGUOUS
    if p_global <= alpha_detect:
        return MultimodalityState.MULTIMODALITY_DETECTED
    if p_global <= alpha_warn:
        return MultimodalityState.AMBIGUOUS
    return MultimodalityState.NOT_DETECTED_IN_VISITED_SUPPORT


def _split_assignments(
    matrix: np.ndarray,
    *,
    specs: tuple[_ViewSpec, ...],
    w_min: float,
    max_modes: int,
    min_statistic: float,
) -> np.ndarray:
    assignments = np.zeros(matrix.shape[0], dtype=int)
    next_label = 1
    while next_label < max_modes:
        best_label: int | None = None
        best_result: _ViewResult | None = None
        best_indices: np.ndarray | None = None
        for label in np.unique(assignments):
            indices = np.flatnonzero(assignments == label)
            if indices.shape[0] < max(40, int(np.ceil(2 * w_min * matrix.shape[0]))):
                continue
            result = _best_view(matrix[indices], specs=specs, w_min=w_min)
            left = result.left_fraction
            if not (w_min <= left <= 1.0 - w_min):
                continue
            if best_result is None or result.statistic > best_result.statistic:
                best_label = int(label)
                best_result = result
                best_indices = indices
        if best_result is None or best_label is None or best_indices is None:
            break
        if best_result.statistic < min_statistic:
            break
        values = _view_values(matrix[best_indices], best_result.spec)
        right_mask = values > best_result.threshold
        if np.sum(right_mask) == 0 or np.sum(~right_mask) == 0:
            break
        assignments[best_indices[right_mask]] = next_label
        assignments[best_indices[~right_mask]] = best_label
        next_label += 1
    return _canonical_mode_labels(assignments)


def _canonical_mode_labels(assignments: np.ndarray) -> np.ndarray:
    result = np.zeros_like(assignments, dtype=int)
    for new_label, old_label in enumerate(sorted(np.unique(assignments))):
        result[assignments == old_label] = new_label
    return result


def _validate_assignments(
    matrix: np.ndarray,
    assignments: np.ndarray,
    *,
    w_min: float,
) -> np.ndarray:
    labels = sorted(np.unique(assignments))
    total = max(matrix.shape[0], 1)
    valid_labels = [
        label for label in labels if float(np.mean(assignments == label)) >= max(float(w_min), 0.01)
    ]
    if len(valid_labels) < 2:
        return np.zeros(matrix.shape[0], dtype=int)
    centers = np.asarray([np.mean(matrix[assignments == label], axis=0) for label in valid_labels])
    if centers.shape[0] >= 2:
        distances = [
            float(np.linalg.norm(centers[i] - centers[j]))
            for i in range(centers.shape[0])
            for j in range(i + 1, centers.shape[0])
        ]
        if distances and min(distances) < 1.0:
            return np.zeros(total, dtype=int)
    remapped = np.zeros_like(assignments, dtype=int)
    for new_label, old_label in enumerate(valid_labels):
        remapped[assignments == old_label] = new_label
    return remapped


def _mode_summaries(
    *,
    matrix: np.ndarray,
    labels: Sequence[str],
    assignments: np.ndarray,
    view_result: _ViewResult,
) -> tuple[PosteriorModeSummary, ...]:
    summaries: list[PosteriorModeSummary] = []
    total = max(int(matrix.shape[0]), 1)
    for mode_idx in sorted(np.unique(assignments).astype(int)):
        mask = assignments == mode_idx
        draw_count = int(np.sum(mask))
        if draw_count <= 0:
            continue
        subset = matrix[mask]
        fraction = draw_count / total
        se = float(np.sqrt(max(fraction * (1.0 - fraction), 0.0) / total))
        ci = (max(0.0, fraction - 1.645 * se), min(1.0, fraction + 1.645 * se))
        center = {
            labels[idx]: float(np.mean(subset[:, idx]))
            for idx in range(min(len(labels), subset.shape[1]))
        }
        parameter_summaries: dict[str, dict[str, float]] = {}
        for idx, label in enumerate(labels[: subset.shape[1]]):
            values = subset[:, idx]
            q05, q50, q95 = np.quantile(values, [0.05, 0.50, 0.95])
            parameter_summaries[str(label)] = {
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)) if values.shape[0] > 1 else 0.0,
                "q05": float(q05),
                "q50": float(q50),
                "q95": float(q95),
            }
        covariance = (
            np.cov(subset, rowvar=False) if subset.shape[0] > 1 else np.zeros((), dtype=float)
        )
        covariance_arr = np.atleast_2d(np.asarray(covariance, dtype=float))
        ess_values = [
            _ess_for_dimension(subset[:, dim].reshape(1, -1))
            for dim in range(subset.shape[1])
            if subset.shape[0] >= 4
        ]
        summaries.append(
            PosteriorModeSummary(
                mode_id=f"M{mode_idx + 1}",
                draw_count=draw_count,
                ess_bulk_min=float(min(ess_values)) if ess_values else None,
                weight=PosteriorModeWeight(
                    estimate=float(fraction),
                    ci_90=(float(ci[0]), float(ci[1])),
                    method="observed_draw_fraction",
                ),
                center=center,
                covariance_summary={
                    "trace": float(np.trace(covariance_arr)),
                    "max_variance": float(np.max(np.diag(covariance_arr)))
                    if covariance_arr.shape[0]
                    else 0.0,
                },
                parameter_summaries=parameter_summaries,
                diagnostics={
                    "view_kind": view_result.spec.kind,
                    "projection_test_statistic": float(view_result.statistic),
                    "projection_test_statistic_name": view_result.statistic_name,
                    "split_threshold": float(view_result.threshold),
                },
            )
        )
    return tuple(summaries)


def _utility_matrix(
    utility_by_action: Mapping[str, Any] | None,
    *,
    num_chains: int,
    num_samples: int,
    finite_rows: np.ndarray,
) -> tuple[np.ndarray, tuple[str, ...]] | None:
    if not utility_by_action:
        return None
    raw = _stack_posterior_chains(
        utility_by_action,
        num_chains=max(1, int(num_chains)),
        num_samples=max(1, int(num_samples)),
    ).reshape(num_chains * num_samples, -1)
    labels = _parameter_labels(
        utility_by_action,
        num_chains=num_chains,
        num_samples=num_samples,
        prefix="utility:",
    )
    matrix = np.asarray(raw[finite_rows], dtype=float)
    finite = np.all(np.isfinite(matrix), axis=1)
    if not np.all(finite):
        matrix = matrix[finite]
    if matrix.shape[1] != len(labels):
        labels = [f"utility:action_{idx}" for idx in range(matrix.shape[1])]
    return matrix, tuple(labels)


def _classify_policy_relevance(
    *,
    utilities: tuple[np.ndarray, tuple[str, ...]] | None,
    assignments: np.ndarray,
    modes: tuple[PosteriorModeSummary, ...],
    margin: float,
) -> tuple[PolicyRelevanceStatus, MultimodalityState | None, tuple[PosteriorModeSummary, ...]]:
    if utilities is None or not modes:
        return (
            PolicyRelevanceStatus(
                assessed=False,
                classification=PolicyRelevanceClassification.NOT_ASSESSED,
                single_recommendation_allowed=False,
            ),
            None,
            modes,
        )
    utility_matrix, action_labels = utilities
    if utility_matrix.shape[0] != assignments.shape[0]:
        return (
            PolicyRelevanceStatus(
                assessed=False,
                classification=PolicyRelevanceClassification.UNKNOWN,
                single_recommendation_allowed=False,
            ),
            None,
            modes,
        )

    recommendations: dict[str, str] = {}
    margins: dict[str, float] = {}
    updated_modes: list[PosteriorModeSummary] = []
    for mode in modes:
        mode_idx = int(mode.mode_id.removeprefix("M")) - 1
        mask = assignments == mode_idx
        means = np.mean(utility_matrix[mask], axis=0)
        order = np.argsort(means)[::-1]
        best = int(order[0])
        second = int(order[1]) if order.shape[0] > 1 else best
        mode_margin = float(means[best] - means[second]) if best != second else float("inf")
        recommended = action_labels[best].replace("utility:", "", 1)
        recommendations[mode.mode_id] = recommended
        margins[mode.mode_id] = mode_margin
        updated_modes.append(
            mode.model_copy(
                update={
                    "policy_summaries": {
                        "recommended_action": recommended,
                        "expected_utility_by_action": {
                            action_labels[idx].replace("utility:", "", 1): float(means[idx])
                            for idx in range(len(action_labels))
                        },
                        "utility_margin": mode_margin,
                    }
                }
            )
        )

    unique_actions = set(recommendations.values())
    if len(unique_actions) > 1:
        return (
            PolicyRelevanceStatus(
                assessed=True,
                classification=PolicyRelevanceClassification.POLICY_SENSITIVE,
                single_recommendation_allowed=False,
            ),
            MultimodalityState.MULTIMODALITY_DETECTED_POLICY_RELEVANT,
            tuple(updated_modes),
        )
    if any(value < margin for value in margins.values()):
        return (
            PolicyRelevanceStatus(
                assessed=True,
                classification=PolicyRelevanceClassification.WEIGHT_SENSITIVE,
                single_recommendation_allowed=False,
            ),
            MultimodalityState.MULTIMODALITY_DETECTED_POLICY_RELEVANT,
            tuple(updated_modes),
        )
    return (
        PolicyRelevanceStatus(
            assessed=True,
            classification=PolicyRelevanceClassification.POLICY_INVARIANT,
            single_recommendation_allowed=True,
        ),
        MultimodalityState.MULTIMODALITY_DETECTED_POLICY_INVARIANT,
        tuple(updated_modes),
    )


def _evidence_strength(state: MultimodalityState) -> str:
    if state in {
        MultimodalityState.MULTIMODALITY_DETECTED,
        MultimodalityState.MULTIMODALITY_DETECTED_POLICY_INVARIANT,
        MultimodalityState.MULTIMODALITY_DETECTED_POLICY_RELEVANT,
    }:
        return "strong"
    if state is MultimodalityState.AMBIGUOUS:
        return "weak"
    if state in {
        MultimodalityState.INCONCLUSIVE_SAMPLING_GEOMETRY,
        MultimodalityState.INCONCLUSIVE_LOW_ESS,
        MultimodalityState.INCONCLUSIVE_UNVISITED_MODES_POSSIBLE,
    }:
        return "exploratory"
    return "none_detected"


def _scopes_from_blocks(blocks: Iterable[_MatrixBlock]) -> tuple[MultimodalityScope, ...]:
    return tuple(dict.fromkeys(block.scope for block in blocks))


def assess_pmd_hmc_multimodality(
    samples: Mapping[str, Any],
    *,
    num_chains: int,
    num_samples: int,
    diagnostics: Mapping[str, Any],
    diagnostics_summary: Mapping[str, Any] | None = None,
    diagnostic_gates: Mapping[str, Any] | None = None,
    policy_functions: Mapping[str, Any] | None = None,
    lp_energy: Mapping[str, Any] | None = None,
    utility_by_action: Mapping[str, Any] | None = None,
    seed: int = 0,
    view_count: int = 200,
    n_bootstrap: int = 250,
    alpha_detect: float = 0.01,
    alpha_warn: float = 0.10,
    w_min: float = 0.05,
    max_modes: int = 8,
    policy_margin: float = 0.0,
    reference_families: tuple[str, ...] = ("elliptical_gaussian", "elliptical_student_t"),
) -> tuple[MultimodalityStatus, tuple[PosteriorModeSummary, ...]]:
    """Assess sampled-support posterior multimodality with conservative PMD-HMC semantics."""

    diagnostics_summary = diagnostics_summary or {}
    diagnostic_gates = diagnostic_gates or {}
    sampler, sampler_low_ess, sampler_failed_geometry = _sampler_adequacy(
        diagnostics=diagnostics,
        diagnostics_summary=diagnostics_summary,
        diagnostic_gates=diagnostic_gates,
        num_chains=num_chains,
        num_samples=num_samples,
    )
    parameter_matrix, parameter_labels, finite_rows = _chain_matrix(
        samples,
        num_chains=num_chains,
        num_samples=num_samples,
    )
    blocks = [
        _MatrixBlock(
            name="joint_unconstrained_parameters",
            scope=MultimodalityScope.JOINT_UNCONSTRAINED_PARAMETERS,
            matrix=parameter_matrix,
            labels=parameter_labels,
        )
    ]
    for block in (
        _extra_block(
            policy_functions,
            num_chains=num_chains,
            num_samples=num_samples,
            name="policy_functions",
            scope=MultimodalityScope.POLICY_FUNCTIONS,
            prefix="policy:",
            finite_rows=finite_rows,
        ),
        _extra_block(
            lp_energy,
            num_chains=num_chains,
            num_samples=num_samples,
            name="lp_energy",
            scope=MultimodalityScope.LP_ENERGY,
            prefix="sampler:",
            finite_rows=finite_rows,
        ),
    ):
        if block is not None:
            blocks.append(block)

    rng = np.random.default_rng(int(seed))
    n_eff = sampler.bulk_ess_min if sampler.bulk_ess_min is not None else float(parameter_matrix.shape[0])
    assessments = [
        _assess_block(
            block,
            n_eff=n_eff,
            view_count=max(1, int(view_count // max(len(blocks), 1))),
            n_bootstrap=int(n_bootstrap),
            w_min=w_min,
            rng=rng,
            reference_families=reference_families,
        )
        for block in blocks
    ]
    best = _best_assessment(assessments)
    p_global = _combine_global_p(assessments)
    state = _state_from_evidence(
        p_global=p_global,
        sampler_failed_geometry=sampler_failed_geometry,
        sampler_low_ess=sampler_low_ess,
        alpha_detect=float(alpha_detect),
        alpha_warn=float(alpha_warn),
    )
    modes: tuple[PosteriorModeSummary, ...] = ()
    mode_ids: tuple[str, ...] = ()
    assignments_available = False
    policy_relevance = PolicyRelevanceStatus(
        assessed=False,
        classification=PolicyRelevanceClassification.NOT_ASSESSED,
        single_recommendation_allowed=state is MultimodalityState.NOT_DETECTED_IN_VISITED_SUPPORT,
    )

    if state is MultimodalityState.MULTIMODALITY_DETECTED and p_global is not None:
        assignments = _split_assignments(
            best.whitened,
            specs=best.specs,
            w_min=w_min,
            max_modes=max(2, int(max_modes)),
            min_statistic=max(6.0, best.observed.statistic * 0.02),
        )
        assignments = _validate_assignments(best.whitened, assignments, w_min=w_min)
        if len(np.unique(assignments)) >= 2:
            raw_mode_matrix = best.block.matrix[:, best.keep] if np.any(best.keep) else best.block.matrix
            modes = _mode_summaries(
                matrix=raw_mode_matrix,
                labels=best.retained_labels or best.block.labels,
                assignments=assignments,
                view_result=best.observed,
            )
            mode_ids = tuple(mode.mode_id for mode in modes)
            assignments_available = True
            policy_relevance, policy_state, modes = _classify_policy_relevance(
                utilities=_utility_matrix(
                    utility_by_action,
                    num_chains=num_chains,
                    num_samples=num_samples,
                    finite_rows=finite_rows,
                ),
                assignments=assignments,
                modes=modes,
                margin=float(policy_margin),
            )
            if policy_state is not None:
                state = policy_state
        else:
            modes = ()
            state = MultimodalityState.AMBIGUOUS

    status = MultimodalityStatus(
        state=state,
        scope=_scopes_from_blocks(blocks),
        test=MultimodalityTestMetadata(
            name="PMD-HMC",
            version=PMD_HMC_VERSION,
            p_global=p_global,
            alpha_detect=float(alpha_detect),
            alpha_warn=float(alpha_warn),
            view_count=int(view_count),
            observer_strategy="percentile_observer_80_90_95",
            projection_strategy="axis_seeded_random_unit_projections_by_scope",
            calibration_method=(
                "autocorrelation_adjusted_projection_distance_bootstrap"
                ":hartigan_dip_when_available"
                ":calibrated_spacing_fallback"
                ":global_min_p:gaussian_and_student_t"
            ),
            n_eff_used=float(max(item.sample_size_used for item in assessments))
            if assessments
            else None,
            null_reference=tuple(reference_families),
        ),
        sampler_adequacy=sampler,
        modes=DetectedModesStatus(
            n_detected_lower_bound=len(mode_ids),
            mode_ids=mode_ids,
            assignments_available=assignments_available,
            mode_weight_reliability=ModeWeightReliability.OBSERVED_DRAW_FRACTION_ONLY
            if mode_ids
            else ModeWeightReliability.UNKNOWN,
        ),
        policy_relevance=policy_relevance,
        downgrade=_downgrade_for_state(state),
        evidence_strength=_evidence_strength(state),
        limitations=_DEFAULT_LIMITATIONS,
    )
    return status, modes


def _simulate_case(case: PmdHmcBenchmarkCase) -> Mapping[str, np.ndarray]:
    rng = np.random.default_rng(case.seed)
    n = int(case.chains * case.draws_per_chain)
    d = int(case.dimension)
    if case.target_family in {"spherical_gaussian", "gaussian"}:
        draws = rng.normal(size=(n, d))
    elif case.target_family == "student_t":
        draws = rng.standard_t(df=3.0, size=(n, d))
    elif case.target_family == "two_component_gaussian_mixture":
        weights = np.asarray([case.min_mode_weight, 1.0 - case.min_mode_weight], dtype=float)
        labels = rng.choice(2, size=n, p=weights / np.sum(weights))
        centers = np.zeros((2, d), dtype=float)
        centers[0, 0] = -0.5 * case.separation
        centers[1, 0] = 0.5 * case.separation
        scales = np.ones((2, d), dtype=float)
        scales[1] = np.sqrt(max(case.covariance_ratio, 1e-9))
        draws = centers[labels] + rng.normal(size=(n, d)) * scales[labels]
    else:
        raise ValueError(f"unsupported PMD-HMC benchmark target: {case.target_family}")
    return {"theta": draws.reshape(case.chains, case.draws_per_chain, d)}


def build_pmd_hmc_benchmark_suite(
    *,
    dimensions: Sequence[int] = (5, 10, 20, 50),
    chains_options: Sequence[int] = (4, 8, 16),
    draws_per_chain_options: Sequence[int] = (500, 1000, 2000, 5000),
    separations: Sequence[float] = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
    min_mode_weights: Sequence[float] = (0.01, 0.025, 0.05, 0.10, 0.25, 0.50),
    covariance_ratios: Sequence[float] = (1.0, 4.0, 16.0),
    seed: int = 6101,
) -> tuple[PmdHmcBenchmarkCase, ...]:
    """Build the default PMD-HMC power/false-positive benchmark grid."""

    cases: list[PmdHmcBenchmarkCase] = []
    counter = 0
    for dimension in dimensions:
        for chains in chains_options:
            for draws in draws_per_chain_options:
                for family in ("spherical_gaussian", "student_t"):
                    cases.append(
                        PmdHmcBenchmarkCase(
                            case_id=f"null_{family}_d{dimension}_c{chains}_n{draws}",
                            target_family=family,
                            dimension=int(dimension),
                            chains=int(chains),
                            draws_per_chain=int(draws),
                            seed=int(seed + counter),
                        )
                    )
                    counter += 1
                for separation in separations:
                    for min_mode_weight in min_mode_weights:
                        for covariance_ratio in covariance_ratios:
                            cases.append(
                                PmdHmcBenchmarkCase(
                                    case_id=(
                                        "alt_mix"
                                        f"_d{dimension}_c{chains}_n{draws}"
                                        f"_sep{separation:g}_w{min_mode_weight:g}"
                                        f"_cr{covariance_ratio:g}"
                                    ),
                                    target_family="two_component_gaussian_mixture",
                                    dimension=int(dimension),
                                    chains=int(chains),
                                    draws_per_chain=int(draws),
                                    separation=float(separation),
                                    min_mode_weight=float(min_mode_weight),
                                    covariance_ratio=float(covariance_ratio),
                                    seed=int(seed + counter),
                                )
                            )
                            counter += 1
    return tuple(cases)


def run_pmd_hmc_benchmark(
    cases: Sequence[PmdHmcBenchmarkCase],
    *,
    view_count: int = 120,
    n_bootstrap: int = 100,
    alpha_detect: float = 0.05,
    w_min: float = 0.05,
) -> dict[str, Any]:
    """Run a reproducible PMD-HMC benchmark over explicit simulation cases."""

    rows: list[dict[str, Any]] = []
    for case in cases:
        samples = _simulate_case(case)
        raw_n = case.chains * case.draws_per_chain
        diagnostics_summary = {
            "num_monitored_chains": float(case.chains),
            "max_rhat": 1.0,
            "min_bulk_ess": float(raw_n),
            "min_tail_ess": float(raw_n),
            "min_bfmi": 0.7,
            "divergences": 0.0,
            "max_treedepth_hits": 0.0,
        }
        gates = {
            "minimum_chains": case.chains >= 4,
            "rhat": True,
            "bulk_ess": True,
            "tail_ess": True,
            "bfmi": True,
            "divergences": True,
            "max_treedepth_hits": True,
        }
        status, _ = assess_pmd_hmc_multimodality(
            samples,
            num_chains=case.chains,
            num_samples=case.draws_per_chain,
            diagnostics={"num_chains": float(case.chains), "num_samples": float(case.draws_per_chain)},
            diagnostics_summary=diagnostics_summary,
            diagnostic_gates=gates,
            seed=case.seed,
            view_count=view_count,
            n_bootstrap=n_bootstrap,
            alpha_detect=alpha_detect,
            w_min=w_min,
        )
        rows.append(
            {
                "case_id": case.case_id,
                "target_family": case.target_family,
                "dimension": case.dimension,
                "ess": raw_n,
                "separation": case.separation,
                "min_mode_weight": case.min_mode_weight,
                "covariance_ratio": case.covariance_ratio,
                "state": status.state.value,
                "p_global": status.test.p_global,
                "n_modes_detected_lower_bound": status.modes.n_detected_lower_bound,
            }
        )
    null_rows = [row for row in rows if "mixture" not in str(row["target_family"])]
    alt_rows = [row for row in rows if "mixture" in str(row["target_family"])]
    return {
        "test_name": "PMD-HMC",
        "test_version": PMD_HMC_VERSION,
        "rows": rows,
        "false_positive_rate": float(
            np.mean([row["state"].startswith("multimodality_detected") for row in null_rows])
        )
        if null_rows
        else None,
        "power": float(
            np.mean([row["state"].startswith("multimodality_detected") for row in alt_rows])
        )
        if alt_rows
        else None,
    }


__all__ = [
    "PMD_HMC_VERSION",
    "PmdHmcBenchmarkCase",
    "assess_pmd_hmc_multimodality",
    "build_pmd_hmc_benchmark_suite",
    "run_pmd_hmc_benchmark",
]
