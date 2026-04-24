"""Shared graph-aware dependence diagnostics for cross-unit workflows."""

from __future__ import annotations

from collections.abc import Mapping
from statistics import NormalDist
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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

from .protocols import (
    DependenceDiagnosticData,
    DependenceDiagnosticResult,
    GraphDependenceDiagnostic,
)

_FLOAT_EPS = 1e-12
_CHI2_95 = 3.841458820694124


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("diagnostic", "json"),
                contract_id=DependenceDiagnosticResult.contract_id,
            )
        }
    )


def _payload(state: Any) -> dict[str, Any]:
    if isinstance(state, DependenceDiagnosticData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        nested = state.get("dependence_data")
        if isinstance(nested, DependenceDiagnosticData):
            return nested.model_dump(mode="python")
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({k: v for k, v in state.items() if k != "dependence_data"})
            return payload
        return dict(state)
    raise TypeError("state must be DependenceDiagnosticData or mapping")


def _row_standardize_weights(weights: np.ndarray) -> np.ndarray:
    arr = np.asarray(weights, dtype=float).copy()
    np.fill_diagonal(arr, 0.0)
    row_sums = np.sum(arr, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return arr / row_sums


def _moran_i(values: np.ndarray, weights: np.ndarray) -> float:
    centered = np.asarray(values, dtype=float) - float(np.mean(values))
    denom = max(float(centered @ centered), _FLOAT_EPS)
    w_sum = max(float(np.sum(weights)), _FLOAT_EPS)
    return float((len(centered) / w_sum) * ((centered @ weights @ centered) / denom))


def _geary_c(values: np.ndarray, weights: np.ndarray) -> float:
    centered = np.asarray(values, dtype=float) - float(np.mean(values))
    denom = max(float(centered @ centered), _FLOAT_EPS)
    diffs = values[:, None] - values[None, :]
    numerator = float(np.sum(weights * (diffs**2)))
    w_sum = max(float(np.sum(weights)), _FLOAT_EPS)
    return float(((len(values) - 1.0) / (2.0 * w_sum)) * (numerator / denom))


def _permutation_p_values(
    values: np.ndarray,
    weights: np.ndarray,
    *,
    n_permutations: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    moran_ref = _moran_i(values, weights)
    geary_ref = _geary_c(values, weights)
    moran_stats = np.empty(n_permutations, dtype=float)
    geary_stats = np.empty(n_permutations, dtype=float)
    for idx in range(n_permutations):
        permuted = rng.permutation(values)
        moran_stats[idx] = _moran_i(permuted, weights)
        geary_stats[idx] = _geary_c(permuted, weights)
    moran_p = float(np.mean(np.abs(moran_stats) >= abs(moran_ref)))
    geary_p = float(np.mean(np.abs(geary_stats - 1.0) >= abs(geary_ref - 1.0)))
    return moran_p, geary_p


def _chi_square1_p_value(statistic: float | None) -> float | None:
    if statistic is None or not np.isfinite(statistic) or statistic < 0.0:
        return None
    tail = 1.0 - NormalDist().cdf(np.sqrt(float(statistic)))
    return float(min(max(2.0 * tail, 0.0), 1.0))


def _normalize_fit_summaries(metadata: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = metadata.get("candidate_fit_summaries")
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return {str(key): value for key, value in raw.items() if isinstance(value, Mapping)}
    summaries: dict[str, Mapping[str, Any]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        graph_id = str(item.get("graph_id", "")).strip()
        if graph_id:
            summaries[graph_id] = item
    return summaries


def _coerce_panel_matrix(value: Any, *, n_units: int) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        return None
    if arr.shape[0] == n_units:
        return arr
    if arr.shape[1] == n_units:
        return arr.T
    return None


def _pesaran_cd_summary(
    data: DependenceDiagnosticData,
) -> dict[str, float | int | bool | None] | None:
    from polisyos.foundry.methods.catalog.econometrics.dependence import (
        _pairwise_correlations,
        _pairwise_summary,
        _panel_residual_matrix,
    )

    matrix = None
    entity_ids = data.metadata.get("entity_ids")
    time_ids = data.metadata.get("time_ids")
    if entity_ids is not None and time_ids is not None:
        try:
            matrix, _, _ = _panel_residual_matrix(
                data.residuals,
                entity_ids=entity_ids,
                time_ids=time_ids,
            )
        except ValueError:
            matrix = None
    if matrix is None:
        matrix = _coerce_panel_matrix(
            data.metadata.get("panel_residual_matrix", data.metadata.get("residual_draws")),
            n_units=data.residuals.shape[0],
        )
    if matrix is None or matrix.shape[0] < 3 or matrix.shape[1] < 3:
        return None
    _, _, correlations, overlaps = _pairwise_correlations(matrix)
    if correlations.size == 0:
        return None
    return _pairwise_summary(correlations, overlaps)


def _coerce_design_matrix(value: Any, *, n_units: int) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2 or arr.shape[0] != n_units or not np.all(np.isfinite(arr)):
        return None
    if np.linalg.matrix_rank(arr) < arr.shape[1]:
        return None
    return arr


def _lm_diagnostics(
    residuals: np.ndarray,
    weights: np.ndarray,
    *,
    y: np.ndarray | None,
    X: np.ndarray | None,
) -> tuple[float | None, float | None, float | None, float | None]:
    if y is None or X is None:
        return None, None, None, None
    sigma2 = max(float(residuals @ residuals) / max(residuals.shape[0], 1), _FLOAT_EPS)
    trace_term = float(np.trace(weights.T @ weights + weights @ weights))
    if trace_term <= _FLOAT_EPS:
        return None, None, None, None

    weighted_residuals = weights @ residuals
    lm_error = float(((residuals @ weighted_residuals) / sigma2) ** 2 / trace_term)

    weighted_y = weights @ y
    xpx_inv = np.linalg.pinv(X.T @ X)
    projection = np.eye(residuals.shape[0], dtype=float) - X @ xpx_inv @ X.T
    lag_scale = float((weighted_y @ projection @ weighted_y) / sigma2 + trace_term)
    if lag_scale <= _FLOAT_EPS:
        lm_lag = None
    else:
        lm_lag = float(((residuals @ weighted_y) / sigma2) ** 2 / lag_scale)

    return lm_error, _chi_square1_p_value(lm_error), lm_lag, _chi_square1_p_value(lm_lag)


def _strength_label(
    *,
    dependence_score: float,
    pesaran_cd: float | None,
    lm_error: float | None,
    lm_lag: float | None,
) -> str:
    if dependence_score < 0.05 and all(
        value is None or abs(float(value)) < 2.0 for value in (pesaran_cd, lm_error, lm_lag)
    ):
        return "none"
    if dependence_score >= 0.25 or any(
        value is not None and float(value) >= 6.0 for value in (lm_error, lm_lag)
    ):
        return "strong"
    if dependence_score >= 0.10 or (pesaran_cd is not None and abs(float(pesaran_cd)) >= 1.96):
        return "weak"
    return "unknown"


@foundry_method(
    namespace="dependence.diagnostic",
    version="1.0.0",
    tags={"dependence", "diagnostic", "graph", "spatial", "network"},
)
class GraphDependenceDiagnosticEstimator:
    """Screen residual dependence against a small family of exogenous graphs."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="graph_dependence",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "residuals", SlotType.VECTOR, Unit("residual", "value"), shape=("n_units",)
                ),
                SlotSpec("candidate_graphs", SlotType.SCALAR, Unit("graph", "json")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="score_threshold", default=0.1),
            ParameterSpec(name="n_permutations", default=0),
            ParameterSpec(name="alpha", default=0.05),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Graph-aware dependence diagnostic using Moran's I, Geary's C, and graph identifiability checks.",
        tags=frozenset({"dependence", "diagnostic", "graph", "autocorrelation"}),
        citations=(
            "Moran, P. (1950). Notes on continuous stochastic phenomena. Biometrika, 37(1/2), 17-23.",
            "Geary, R. (1954). The contiguity ratio and statistical mapping. The Incorporated Statistician, 5(3), 115-145.",
        ),
        when_to_use="Residual cross-unit dependence should be screened against a small set of exogenous spatial or administrative graphs before fitting graph-aware models.",
        output_interpretation="High absolute Moran's I or deviation of Geary's C from 1 suggests graph-local dependence. Weak evidence or non-identifiable graphs should trigger fallback to independence.",
        typical_min_obs=5,
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any], fallback_state: Any
    ) -> DependenceDiagnosticData:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        return DependenceDiagnosticData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: DependenceDiagnosticData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, DependenceDiagnosticData)
            else DependenceDiagnosticData.model_validate(state)
        )
        threshold = max(0.0, float(params.get("score_threshold", 0.1)))
        alpha = min(max(float(params.get("alpha", 0.05)), 0.0), 1.0)
        n_permutations = max(0, int(params.get("n_permutations", 0)))
        seed = int(params.get("__seed__", 0))
        rng = np.random.default_rng(seed)
        fit_summaries = _normalize_fit_summaries(data.metadata)
        panel_summary = _pesaran_cd_summary(data)
        pesaran_cd = None if panel_summary is None else float(panel_summary["statistic"])
        pesaran_cd_p_value = None if panel_summary is None else panel_summary["p_value"]
        y = (
            np.asarray(data.metadata.get("y_direct"), dtype=float)
            if data.metadata.get("y_direct") is not None
            else None
        )
        X = _coerce_design_matrix(data.metadata.get("X"), n_units=data.residuals.shape[0])

        diagnostics: list[GraphDependenceDiagnostic] = []
        residual_var = float(np.var(data.residuals))
        any_identifiable = False

        for graph in data.candidate_graphs:
            weights = _row_standardize_weights(graph.W)
            spectral_radius = (
                float(np.max(np.abs(np.linalg.eigvals(weights)))) if weights.size else 0.0
            )
            nonzero_rows = int(np.sum(np.sum(np.abs(weights), axis=1) > 0.0))
            structural_identifiable = bool(
                spectral_radius > 1e-8 and nonzero_rows >= 2 and residual_var > _FLOAT_EPS
            )

            moran_i = _moran_i(data.residuals, weights)
            geary_c = _geary_c(data.residuals, weights)
            moran_p = None
            geary_p = None
            if structural_identifiable and n_permutations > 0:
                moran_p, geary_p = _permutation_p_values(
                    data.residuals,
                    weights,
                    n_permutations=n_permutations,
                    rng=rng,
                )
            lm_error, lm_error_p, lm_lag, lm_lag_p = _lm_diagnostics(
                data.residuals,
                weights,
                y=y,
                X=X,
            )

            fit_summary = fit_summaries.get(graph.graph_id, {})
            profile_curvature = (
                float(fit_summary["profile_curvature"])
                if fit_summary.get("profile_curvature") is not None
                else None
            )
            information_eigen_min = (
                float(fit_summary["information_eigen_min"])
                if fit_summary.get("information_eigen_min") is not None
                else None
            )
            information_condition_number = (
                float(fit_summary["information_condition_number"])
                if fit_summary.get("information_condition_number") is not None
                else None
            )
            rho_interval_raw = fit_summary.get("rho_confidence_interval")
            rho_confidence_interval = None
            if isinstance(rho_interval_raw, (tuple, list)) and len(rho_interval_raw) == 2:
                rho_confidence_interval = (float(rho_interval_raw[0]), float(rho_interval_raw[1]))
            rho_interval_contains_zero = (
                bool(fit_summary.get("rho_interval_contains_zero"))
                if fit_summary.get("rho_interval_contains_zero") is not None
                else (
                    rho_confidence_interval is not None
                    and rho_confidence_interval[0] <= 0.0 <= rho_confidence_interval[1]
                )
            )
            boundary_hit = (
                bool(fit_summary.get("boundary_hit"))
                if fit_summary.get("boundary_hit") is not None
                else None
            )
            fit_identifiable = (
                bool(fit_summary["identifiable"])
                if fit_summary.get("identifiable") is not None
                else structural_identifiable
            )
            identifiable = bool(structural_identifiable and fit_identifiable)
            any_identifiable = any_identifiable or identifiable
            dependence_score = float(max(abs(moran_i), abs(geary_c - 1.0)))
            detected_by_p = any(
                value is not None and float(value) <= alpha
                for value in (moran_p, geary_p, pesaran_cd_p_value, lm_error_p, lm_lag_p)
            )
            detected = bool(identifiable and (detected_by_p or dependence_score >= threshold))
            decision = (
                "identified"
                if detected
                else ("fallback_independent" if structural_identifiable else "not_identified")
            )
            diagnostics.append(
                GraphDependenceDiagnostic(
                    graph_id=graph.graph_id,
                    family=graph.family,
                    identifiable=identifiable,
                    moran_i=float(moran_i),
                    geary_c=float(geary_c),
                    moran_p_value=moran_p,
                    geary_p_value=geary_p,
                    pesaran_cd=pesaran_cd,
                    pesaran_p_value=pesaran_cd_p_value,
                    lm_error=lm_error,
                    lm_error_p_value=lm_error_p,
                    lm_lag=lm_lag,
                    lm_lag_p_value=lm_lag_p,
                    dependence_score=dependence_score,
                    profile_curvature=profile_curvature,
                    information_eigen_min=information_eigen_min,
                    information_condition_number=information_condition_number,
                    rho_confidence_interval=rho_confidence_interval,
                    rho_interval_contains_zero=rho_interval_contains_zero,
                    boundary_hit=boundary_hit,
                    decision=decision,
                    metadata={
                        "spectral_radius": spectral_radius,
                        "nonzero_rows": nonzero_rows,
                        "structural_identifiable": structural_identifiable,
                    },
                )
            )

        selected_candidates = [item for item in diagnostics if item.decision == "identified"]
        if selected_candidates:
            selected = max(selected_candidates, key=lambda item: item.dependence_score)
            detected = True
            decision = "identified"
        elif any_identifiable:
            selected = max(
                (item for item in diagnostics if item.identifiable),
                key=lambda item: item.dependence_score,
            )
            detected = False
            decision = "fallback_independent"
        else:
            selected = max(diagnostics, key=lambda item: item.dependence_score)
            detected = False
            decision = "not_identified"

        if not any_identifiable:
            class_label = "inconclusive"
            estimator_status = "not_identified"
            fallback_reason = "no_identifiable_candidate_graph"
            strength = "unknown"
        elif detected and len({item.graph_id for item in selected_candidates}) > 1:
            class_label = "mixed"
            estimator_status = "ok"
            fallback_reason = None
            strength = _strength_label(
                dependence_score=selected.dependence_score,
                pesaran_cd=selected.pesaran_cd,
                lm_error=selected.lm_error,
                lm_lag=selected.lm_lag,
            )
        elif detected:
            class_label = "graph_local"
            estimator_status = "ok"
            fallback_reason = None
            strength = _strength_label(
                dependence_score=selected.dependence_score,
                pesaran_cd=selected.pesaran_cd,
                lm_error=selected.lm_error,
                lm_lag=selected.lm_lag,
            )
        else:
            class_label = "weak_or_none"
            estimator_status = "fallback_independent"
            fallback_reason = "dependence_not_detected"
            strength = _strength_label(
                dependence_score=selected.dependence_score,
                pesaran_cd=selected.pesaran_cd,
                lm_error=selected.lm_error,
                lm_lag=selected.lm_lag,
            )

        return {
            "result": DependenceDiagnosticResult(
                method_name="graph_dependence",
                detected=detected,
                class_label=class_label,
                estimator_status=estimator_status,
                decision=decision,
                strength=strength,
                identifiable=any_identifiable,
                selected_graph_id=selected.graph_id if detected else None,
                moran_i=selected.moran_i,
                geary_c=selected.geary_c,
                moran_p_value=selected.moran_p_value,
                geary_p_value=selected.geary_p_value,
                pesaran_cd=selected.pesaran_cd,
                pesaran_cd_p_value=selected.pesaran_p_value,
                lm_error=selected.lm_error,
                lm_error_p_value=selected.lm_error_p_value,
                lm_lag=selected.lm_lag,
                lm_lag_p_value=selected.lm_lag_p_value,
                profile_curvature=selected.profile_curvature,
                information_eigen_min=selected.information_eigen_min,
                information_condition_number=selected.information_condition_number,
                rho_confidence_interval=selected.rho_confidence_interval,
                rho_interval_contains_zero=selected.rho_interval_contains_zero,
                fallback_reason=fallback_reason,
                graph_diagnostics=tuple(diagnostics),
                metadata={
                    "alpha": alpha,
                    "score_threshold": threshold,
                    "n_permutations": n_permutations,
                    "pesaran_summary": panel_summary,
                },
            )
        }


__all__ = [
    "GraphDependenceDiagnosticEstimator",
    "_geary_c",
    "_moran_i",
    "_row_standardize_weights",
]
