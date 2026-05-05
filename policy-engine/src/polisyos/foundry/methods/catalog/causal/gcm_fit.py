"""Public causal gcm fit module API."""

from __future__ import annotations

from collections.abc import Mapping
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
from polisyos.foundry.methods.catalog.causal._graph_projection import pag_to_dag_projection
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)


def _load_dowhy_gcm_dependencies() -> Any:
    from dowhy import gcm

    return gcm


def _pag_to_dag_projection(graph: CausalGraphModel) -> tuple[CausalGraphModel, list[str]]:
    """
    Backward-compatible alias kept for tests/importers.

    Use `pag_to_dag_projection()` directly in new code.
    """
    return pag_to_dag_projection(graph)


def _parents_by_node(graph: CausalGraphModel) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = {node: [] for node in graph.nodes}
    for edge in graph.edges:
        parents.setdefault(edge.dst, []).append(edge.src)
    return parents


def _fit_linear_ols(y: np.ndarray, x: np.ndarray, parent_names: list[str]) -> dict[str, Any]:
    design = np.column_stack([np.ones(y.shape[0]), x])
    coeff = np.linalg.lstsq(design, y, rcond=None)[0]
    fitted = design @ coeff
    residual = y - fitted
    noise_std = float(np.std(residual))
    return {
        "intercept": float(coeff[0]),
        "coefficients": {name: float(coeff[i + 1]) for i, name in enumerate(parent_names)},
        "noise_std": noise_std,
        "design_rank": int(np.linalg.matrix_rank(design)),
        "fit_mode": "ols",
    }


def _fit_additive_noise_poly(
    y: np.ndarray,
    x: np.ndarray,
    parent_names: list[str],
    *,
    degree: int = 2,
) -> dict[str, Any]:
    """Fit an additive-noise model Y = f(pa_Y) + U using polynomial regression.

    Stores both the linear (OLS) params (for backward-compatible prediction via
    ``_linear_predict``) and the higher-degree polynomial coefficients.  The
    linear params serve as a first-order approximation; downstream abduction
    uses the residual U = Y − f_poly(pa_Y) for a better noise estimate.

    Parameters
    ----------
    y:
        1-D outcome array.
    x:
        2-D parent data array of shape (n_obs, n_parents).
    parent_names:
        Ordered list of parent variable names matching columns of *x*.
    degree:
        Polynomial degree for the non-linear f().  Default 2 (quadratic).

    Returns
    -------
    dict
        ``family_params`` payload compatible with
        :class:`~polisyos.ir.analytics.structural_causal_model.MechanismFamily.ADDITIVE_NOISE`.
    """
    n_parents = x.shape[1] if x.ndim == 2 else 0

    # --- Linear baseline (always computed, used as fallback) -----------------
    ols_params = _fit_linear_ols(y, x, parent_names)

    if n_parents == 0 or degree <= 1:
        # No parents or linear-only: degenerate additive noise == OLS
        return {**ols_params, "fit_mode": "additive_noise_linear"}

    # --- Polynomial design matrix -------------------------------------------
    # For simplicity: degree-d Vandermonde expansion of each parent separately,
    # then concatenate (no cross-terms).  This keeps the design interpretable
    # and serialisable as plain lists.
    poly_cols: list[np.ndarray] = [np.ones(y.shape[0])]
    poly_feature_names: list[str] = ["__intercept__"]
    for i, name in enumerate(parent_names):
        col = x[:, i]
        for d in range(1, degree + 1):
            poly_cols.append(col**d)
            poly_feature_names.append(f"{name}^{d}")
    design_poly = np.column_stack(poly_cols)

    try:
        coeff_poly = np.linalg.lstsq(design_poly, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        # Degenerate: fall back to linear OLS
        return {**ols_params, "fit_mode": "additive_noise_linear"}

    fitted_poly = design_poly @ coeff_poly
    residual_poly = y - fitted_poly
    noise_std_poly = float(np.std(residual_poly))

    return {
        # Linear params kept for backward-compatible _linear_predict calls
        "intercept": float(ols_params["intercept"]),
        "coefficients": ols_params["coefficients"],
        "noise_std": noise_std_poly,  # poly residual std (better for abduction)
        "design_rank": int(np.linalg.matrix_rank(design_poly)),
        "fit_mode": "additive_noise_poly",
        # Polynomial coefficients for exact residual computation
        "poly_degree": int(degree),
        "poly_coefficients": {
            name: float(coeff_poly[idx]) for idx, name in enumerate(poly_feature_names)
        },
    }


def _empirical_params(y: np.ndarray) -> dict[str, Any]:
    return {
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "n_samples": int(y.shape[0]),
    }


def _bayesian_linear_gaussian(
    *,
    y: np.ndarray,
    x: np.ndarray,
    parent_names: list[str],
    prior_spec: Mapping[str, Mapping[str, float]],
    ridge: float = 1e-6,
) -> dict[str, Any]:
    design = np.column_stack([np.ones(y.shape[0]), x])
    names = ["__intercept__", *parent_names]

    prior_mean = np.zeros(len(names), dtype=float)
    prior_std = np.full(len(names), 10.0, dtype=float)
    for idx, name in enumerate(names):
        stats = prior_spec.get(name)
        if stats is None:
            continue
        raw_mean = float(stats.get("mean", 0.0))
        raw_std = float(stats.get("std", 10.0))
        if not np.isfinite(raw_mean):
            raise ValueError(f"prior mean for '{name}' is non-finite")
        if not np.isfinite(raw_std) or raw_std <= 0.0:
            raise ValueError(f"prior std for '{name}' must be > 0")
        prior_mean[idx] = raw_mean
        prior_std[idx] = raw_std

    ols = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y - design @ ols
    sigma2 = float(np.var(residual))
    if not np.isfinite(sigma2) or sigma2 <= 0.0:
        sigma2 = 1.0

    prior_precision = np.diag(1.0 / (prior_std**2))
    posterior_precision = (
        prior_precision + (design.T @ design) / sigma2 + ridge * np.eye(len(names))
    )
    posterior_cov = np.linalg.inv(posterior_precision)
    posterior_mean = posterior_cov @ (prior_precision @ prior_mean + (design.T @ y) / sigma2)
    posterior_std = np.sqrt(np.diag(posterior_cov))
    fit_residual = y - design @ posterior_mean

    return {
        "posterior_mean": {name: float(posterior_mean[idx]) for idx, name in enumerate(names)},
        "posterior_std": {name: float(posterior_std[idx]) for idx, name in enumerate(names)},
        "noise_std": float(np.std(fit_residual)),
        "design_rank": int(np.linalg.matrix_rank(design)),
        "bayes_mode": "linear_gaussian_closed_form",
    }


def _compute_sensitivity_to_latent(
    *,
    variable: str,
    parents: list[str],
    latent_vars: set[str],
    data: np.ndarray,
    column_index: dict[str, int],
) -> float | None:
    latent_parents = [
        parent for parent in parents if parent in latent_vars or parent.startswith("U_")
    ]
    if not latent_parents:
        return None
    if variable not in column_index:
        return 1.0

    y = data[:, column_index[variable]]
    target_std = float(np.std(y))
    if target_std <= 1e-12:
        return 0.0

    observed_parents = [
        parent for parent in parents if parent not in latent_parents and parent in column_index
    ]
    if observed_parents:
        x = data[:, [column_index[parent] for parent in observed_parents]]
        design = np.column_stack([np.ones(y.shape[0]), x])
        coeff = np.linalg.lstsq(design, y, rcond=None)[0]
        residual = y - design @ coeff
    else:
        residual = y - np.mean(y)

    sensitivity = float(np.std(residual) / (target_std + 1e-12))
    if not np.isfinite(sensitivity):
        return 1.0
    return float(np.clip(sensitivity, 0.0, 1.0))


def _fit_method_from_summary(summary: Mapping[str, int]) -> str:
    if (
        summary.get(MechanismSource.HYBRID.value, 0) == 0
        and summary.get(MechanismSource.LITERATURE_PRIOR.value, 0) == 0
        and summary.get(MechanismSource.DEFAULT.value, 0) == 0
    ):
        return "gcm"
    return "hybrid"


@foundry_method(
    namespace="causal.structural",
    version="1.0.0",
    tags={"causal", "gcm", "structural", "hybrid"},
)
class HybridSCMFit:
    """Hybrid SCM fitting: DoWhy GCM (when available) + literature priors."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gcm_fit",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="scm_fit_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="structural_causal_model_spec",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="latent_sensitivity_threshold", default=0.3),
            ParameterSpec(name="bayes_ridge", default=1e-6),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fit StructuralCausalModelSpec mechanisms from data and literature priors.",
        tags=frozenset({"causal", "gcm", "structural", "hybrid"}),
        assumptions={
            "graph_validity": "Input causal graph is valid and acyclic after PAG projection.",
            "linear_hybrid_scope": (
                "Strict Bayesian hybrid fit is implemented for linear-gaussian mechanisms."
            ),
            "law_h": "Mechanism params must remain JSON-serializable.",
        },
        when_to_use="Fit Graphical Causal Model to data given known DAG structure; estimate mechanisms for causal queries",
        citations=(
            "Pearl, J. (2009). Causality: Models, Reasoning, and Inference. Cambridge University Press.",
        ),
        when_not_to_use="DAG unknown and no prior to guide structure; no software dependency on dowhy-gcm",
        typical_min_obs=200,
        output_interpretation="Fitted causal mechanisms (noise models) per node. Use downstream for counterfactual/attribution queries.",
    )

    @staticmethod
    def pure_step(
        state: SCMFitData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        payload = state if isinstance(state, SCMFitData) else SCMFitData.model_validate(state)
        graph = (
            payload.graph
            if isinstance(payload.graph, CausalGraphModel)
            else CausalGraphModel.model_validate(payload.graph)
        )
        threshold = float(params.get("latent_sensitivity_threshold", 0.3))
        ridge = float(params.get("bayes_ridge", 1e-6))
        warnings: list[str] = []

        projected_graph = graph
        latent_vars: list[str] = []
        if graph.graph_type is not GraphType.DAG:
            projected_graph, latent_vars = pag_to_dag_projection(graph)

        dowhy_available = 0.0
        try:
            _load_dowhy_gcm_dependencies()
            dowhy_available = 1.0
        except ModuleNotFoundError:
            warnings.append("DoWhy GCM backend unavailable; using numpy fallback fitting.")
        except Exception as exc:
            warnings.append(f"DoWhy GCM backend unavailable ({exc}); using numpy fallback fitting.")

        data = np.asarray(payload.data, dtype=float)
        column_index = {name: idx for idx, name in enumerate(payload.column_names)}
        parents_map = _parents_by_node(projected_graph)
        non_roots = {edge.dst for edge in projected_graph.edges}

        mechanisms: list[NodeMechanism] = []
        source_summary = {source.value: 0 for source in MechanismSource}
        hybrid_fallback_count = 0
        unstable_due_to_latent = False

        latent_set = set(latent_vars)
        for variable in projected_graph.nodes:
            if variable not in non_roots:
                continue

            parents = list(parents_map.get(variable, []))
            has_node_data = variable in column_index
            has_parent_data = all(parent in column_index for parent in parents)
            prior_spec = payload.literature_priors.get(variable, {})
            has_prior = bool(prior_spec)

            if has_node_data and has_parent_data and has_prior:
                source = MechanismSource.HYBRID
            elif has_node_data and has_parent_data:
                source = MechanismSource.DATA_FITTED
            elif has_prior:
                source = MechanismSource.LITERATURE_PRIOR
            else:
                source = MechanismSource.DEFAULT

            if has_node_data:
                y = data[:, column_index[variable]]
            else:
                y = np.zeros(data.shape[0], dtype=float)
            if has_parent_data and parents:
                x = data[:, [column_index[parent] for parent in parents]]
            else:
                x = np.zeros((data.shape[0], 0), dtype=float)

            family = MechanismFamily.EMPIRICAL
            family_params: dict[str, Any]
            if source is MechanismSource.DATA_FITTED:
                if parents:
                    family = MechanismFamily.LINEAR
                    family_params = _fit_linear_ols(y, x, parents)
                else:
                    family = MechanismFamily.EMPIRICAL
                    family_params = _empirical_params(y)
            elif source is MechanismSource.LITERATURE_PRIOR:
                family = MechanismFamily.PARAMETRIC_PRIOR
                family_params = {"prior": dict(prior_spec), "prior_only": True}
            elif source is MechanismSource.HYBRID:
                try:
                    family = MechanismFamily.LINEAR
                    family_params = _bayesian_linear_gaussian(
                        y=y,
                        x=x,
                        parent_names=parents,
                        prior_spec=prior_spec,
                        ridge=ridge,
                    )
                except Exception as exc:
                    hybrid_fallback_count += 1
                    family = (
                        MechanismFamily.ADDITIVE_NOISE if parents else MechanismFamily.EMPIRICAL
                    )
                    if has_node_data:
                        family_params = _empirical_params(y)
                    else:
                        family_params = {"default_prior": "wide", "uncertainty": "high"}
                    family_params.update(
                        {
                            "hybrid_fallback": "nonlinear_not_supported_phase10",
                            "fallback_reason": str(exc),
                        }
                    )
                    warnings.append(f"Hybrid fallback for '{variable}': {exc}")
            else:
                family = MechanismFamily.EMPIRICAL
                if has_node_data:
                    family_params = _empirical_params(y)
                else:
                    family_params = {"default_prior": "wide", "uncertainty": "high"}

            sensitivity_to_latent = _compute_sensitivity_to_latent(
                variable=variable,
                parents=parents,
                latent_vars=latent_set,
                data=data,
                column_index=column_index,
            )
            if sensitivity_to_latent is not None and sensitivity_to_latent > threshold:
                unstable_due_to_latent = True

            mechanisms.append(
                NodeMechanism(
                    variable=variable,
                    parents=parents,
                    family=family,
                    family_params=family_params,
                    source=source,
                    literature_prior=dict(prior_spec) if has_prior else None,
                    sensitivity_to_latent=sensitivity_to_latent,
                )
            )
            source_summary[source.value] += 1

        fit_metrics: dict[str, float] = {
            "dowhy_available": float(dowhy_available),
            "n_nodes": float(len(projected_graph.nodes)),
            "n_non_roots": float(len(non_roots)),
            "n_mechanisms": float(len(mechanisms)),
            "n_data_fitted": float(source_summary[MechanismSource.DATA_FITTED.value]),
            "n_literature_prior": float(source_summary[MechanismSource.LITERATURE_PRIOR.value]),
            "n_hybrid": float(source_summary[MechanismSource.HYBRID.value]),
            "n_default": float(source_summary[MechanismSource.DEFAULT.value]),
            "n_hybrid_fallback": float(hybrid_fallback_count),
            "latent_vars_count": float(len(latent_vars)),
            "unstable_due_to_latent": 1.0 if unstable_due_to_latent else 0.0,
        }
        fit_method = (
            "hybrid" if dowhy_available == 0.0 else _fit_method_from_summary(source_summary)
        )
        scm_spec = StructuralCausalModelSpec(
            graph=projected_graph,
            mechanisms=mechanisms,
            fitted=True,
            fit_method=fit_method,
            fit_metrics=fit_metrics,
            mechanism_source_summary={k: int(v) for k, v in source_summary.items() if v > 0},
            skg_snapshot_ref=payload.skg_snapshot_ref,
        )

        return {
            "scm_spec": scm_spec,
            "projected_graph": projected_graph,
            "latent_vars": latent_vars,
            "warnings": warnings,
            "__determinism_tier__": DeterminismTier.STATISTICAL,
        }


__all__ = [
    "HybridSCMFit",
    "_pag_to_dag_projection",
]
