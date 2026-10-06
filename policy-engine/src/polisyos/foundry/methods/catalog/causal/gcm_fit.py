"""Public causal gcm fit module API."""

from __future__ import annotations

from collections.abc import Mapping
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
from polisyos.foundry.methods.catalog.causal._graph_projection import pag_to_dag_projection
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    SCMFitProvenance,
    SCMTrainingRows,
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
        if edge.lag not in (None, 0):
            continue
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


def _gcm_spec_from_worker(
    payload: SCMFitData,
    response: Mapping[str, Any],
    model: Mapping[str, Any],
    *,
    seed: int,
    resample_indices: list[int] | None = None,
) -> StructuralCausalModelSpec:
    """Validate exported fitted mechanisms against the bound parent rows."""
    data = np.asarray(payload.data, dtype=float)
    graph = payload.graph
    parents = _parents_by_node(graph)
    if set(model) - {"bootstrap_models"} != {"mechanisms", "fit_function", "row_ids"}:
        raise ValueError("unexpected GCM fitted model fields")
    if model["fit_function"] != "dowhy.gcm.fit":
        raise ValueError("selected GCM model must be produced by dowhy.gcm.fit")
    source = response["source"]
    source_ref = source["artifact_ref"]
    row_ids = [f"{source_ref['artifact_id']}:{i}" for i in range(len(data))]
    selected = resample_indices if resample_indices is not None else list(range(len(data)))
    selected_ids = [row_ids[i] for i in selected]
    if model["row_ids"] != selected_ids:
        raise ValueError("GCM fitted rows differ from the bound source row identities")
    fitted = model["mechanisms"]
    if not isinstance(fitted, Mapping) or set(fitted) != set(graph.nodes):
        raise ValueError("GCM fitted mechanisms must cover the exact declared graph")
    mechanisms: list[NodeMechanism] = []
    columns = {name: i for i, name in enumerate(payload.column_names)}
    frame = data[selected]
    for node in graph.nodes:
        result = fitted[node]
        expected_parents = sorted(parents[node])
        if not isinstance(result, Mapping) or result.get("parents") != expected_parents:
            raise ValueError(f"GCM parent binding mismatch for {node}")
        y = frame[:, columns[node]]
        if not expected_parents:
            if (
                set(result) != {"parents", "family", "observed_samples"}
                or result["family"] != "empirical"
            ):
                raise ValueError(f"unsupported GCM root mechanism for {node}")
            observed = np.asarray(result["observed_samples"], dtype=float)
            if observed.shape != y.shape or not np.array_equal(observed, y):
                raise ValueError(f"GCM root samples differ from source rows for {node}")
            family = MechanismFamily.EMPIRICAL
            params = {
                **_empirical_params(y),
                "observed_samples": observed.tolist(),
                "observed_samples_source": source_ref["artifact_id"],
                "observed_sample_alignment": "source_row_ids",
                "observed_row_ids": selected_ids,
                "joint_sample_group": response["data_sha256"],
            }
        else:
            fields = {
                "parents",
                "family",
                "intercept",
                "coefficients",
                "residual_samples",
                "noise_std",
            }
            if set(result) != fields or result["family"] != "linear_additive_noise":
                raise ValueError(f"unsupported GCM conditional mechanism for {node}")
            coefficients = result["coefficients"]
            if not isinstance(coefficients, Mapping) or set(coefficients) != set(expected_parents):
                raise ValueError(f"GCM coefficient binding mismatch for {node}")
            intercept = float(result["intercept"])
            residual = np.asarray(result["residual_samples"], dtype=float)
            prediction = intercept + sum(
                float(coefficients[parent]) * frame[:, columns[parent]]
                for parent in expected_parents
            )
            # Numerical fields of a persisted reply require a source-row
            # oracle too. This verifies the actual worker export; it never
            # substitutes a native fit for selected backend execution.
            design = np.column_stack(
                [np.ones(len(frame)), frame[:, [columns[p] for p in expected_parents]]]
            )
            if np.linalg.matrix_rank(design) != design.shape[1]:
                raise ValueError(f"GCM linear mechanism is unidentified on source rows for {node}")
            oracle = np.linalg.lstsq(design, y, rcond=None)[0]
            actual = np.asarray(
                [intercept, *(coefficients[p] for p in expected_parents)], dtype=float
            )
            if not np.allclose(actual, oracle, atol=1.0e-8, rtol=1.0e-8):
                raise ValueError(
                    f"GCM exported linear fit differs from source-row oracle for {node}"
                )
            if (
                residual.shape != y.shape
                or not np.isfinite(residual).all()
                or not np.allclose(residual, y - prediction, atol=1.0e-8, rtol=1.0e-8)
            ):
                raise ValueError(f"GCM fitted residuals differ from source rows for {node}")
            if not np.isfinite(prediction).all() or not np.isfinite(float(result["noise_std"])):
                raise ValueError(f"nonfinite GCM conditional mechanism for {node}")
            if not np.isclose(
                float(result["noise_std"]), float(np.std(residual)), atol=1.0e-8, rtol=1.0e-8
            ):
                raise ValueError(
                    f"GCM residual scale differs from actual source-row residuals for {node}"
                )
            family = MechanismFamily.LINEAR
            params = {
                "intercept": intercept,
                "coefficients": dict(coefficients),
                "noise_std": float(result["noise_std"]),
                "residual_samples": residual.tolist(),
                "fit_mode": "dowhy_linear_additive_noise",
            }
        mechanisms.append(
            NodeMechanism(
                variable=node,
                parents=expected_parents,
                family=family,
                family_params=params,
                noise_distribution="empirical",
                source=MechanismSource.DATA_FITTED,
            )
        )
    training = SCMTrainingRows(
        rows=data.tolist(),
        columns=list(payload.column_names),
        row_ids=row_ids,
        source_ref=source_ref,
        source_sha256=source["content_sha256"],
        data_sha256=response["data_sha256"],
        row_sha256=response["row_sha256"],
        graph_sha256=response["graph_sha256"],
        graph_payload={"nodes": list(graph.nodes), "edges": [[e.src, e.dst] for e in graph.edges]},
        fit_input=payload.model_dump(mode="json"),
    )
    provenance = SCMFitProvenance(
        python=response["python"],
        versions={
            name.lower().replace("_", "-"): version
            for name, version in response["versions"].items()
        },
        seed=seed,
        request_id=response["request_id"],
        request_sha256=response["request_sha256"],
        worker_code_sha256=response["parent_observed"]["worker_code_sha256"],
        worker_lock_sha256=response["parent_observed"]["worker_lock_sha256"],
        worker_response=dict(response),
        resample_indices=resample_indices,
    )
    return StructuralCausalModelSpec(
        schema_version="1.1",
        graph=graph,
        mechanisms=mechanisms,
        fitted=True,
        fit_method="gcm",
        training_rows=training,
        fit_provenance=provenance,
        fit_metrics={"dowhy_available": 1.0, "n_nodes": float(len(graph.nodes))},
        mechanism_source_summary={"data_fitted": len(mechanisms)},
        skg_snapshot_ref=payload.skg_snapshot_ref,
    )


def _fit_gcm_specs(
    payload: SCMFitData,
    *,
    seed: int,
    bootstrap_indices: list[list[int]] | None = None,
) -> tuple[StructuralCausalModelSpec, list[StructuralCausalModelSpec]]:
    """Run actual selected GCM fits on complete source-bound frames."""
    if payload.graph.graph_type is not GraphType.DAG or set(payload.column_names) != set(
        payload.graph.nodes
    ):
        raise ValueError("selected GCM profile requires a fully observed declared static DAG")
    if payload.literature_priors:
        raise ValueError("selected GCM profile does not support literature-prior mechanism fitting")
    parents = _parents_by_node(payload.graph)
    try:
        from polisyos.foundry.methods.catalog.causal._dowhy_worker import run_worker
    except ModuleNotFoundError as exc:
        raise RuntimeError("selected GCM worker bridge unavailable") from exc
    indices = bootstrap_indices or []
    response = run_worker(
        operation="gcm_fit",
        state=payload,
        seed=seed,
        payload={
            "graph": {
                "nodes": list(payload.graph.nodes),
                "edges": [[e.src, e.dst] for e in payload.graph.edges],
            },
            "mechanisms": {
                node: "linear_additive_noise" if parents[node] else "empirical"
                for node in payload.graph.nodes
            },
            "bootstrap_indices": indices,
        },
    )
    model = response["result"]
    replicas = model.get("bootstrap_models")
    if not isinstance(replicas, list) or len(replicas) != len(indices):
        raise ValueError("GCM worker must refit every requested bootstrap replicate")
    base = _gcm_spec_from_worker(payload, response, model, seed=seed)
    refits = [
        _gcm_spec_from_worker(payload, response, replica, seed=seed, resample_indices=index)
        for replica, index in zip(replicas, indices, strict=True)
    ]
    return base, refits


def validate_persisted_gcm_spec(scm_spec: StructuralCausalModelSpec, store: Any) -> None:
    """Resolve source custody and reconcile the actual persisted GCM consumer.

    Args:
        scm_spec: The model freshly decoded from its CAS artifact.
        store: The enclosing Scientist job's existing authorized artifact store.
    """
    if scm_spec.schema_version != "1.1" or scm_spec.fit_method != "gcm":
        return  # Historical/manual research models make no new backend assertion.
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.foundry.methods.catalog.causal._dowhy_worker import (
        validate_persisted_worker_response,
    )

    training, provenance = scm_spec.training_rows, scm_spec.fit_provenance
    if training is None or provenance is None:
        raise ValueError("persisted selected GCM model lacks source-bound fit records")
    state = SCMFitData.model_validate(training.fit_input)
    validate_persisted_worker_response(
        response=provenance.worker_response,
        state=state,
        store=store,
        source_ref=ArtifactRef.model_validate(training.source_ref.model_dump(mode="json")),
    )
    expected = _gcm_spec_from_worker(
        state,
        provenance.worker_response,
        provenance.worker_response["result"],
        seed=provenance.seed,
        resample_indices=provenance.resample_indices,
    )
    if expected.model_dump(mode="json") != scm_spec.model_dump(mode="json"):
        raise ValueError("persisted GCM model differs from its content-bound fitted worker output")


@foundry_method(
    namespace="causal.structural",
    version="1.0.0",
    tags={"causal", "gcm", "structural", "hybrid"},
)
class HybridSCMFit:
    """Selected actual GCM fit, or an explicit native hybrid research profile."""

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
            ParameterSpec(name="fit_backend", default="dowhy_gcm"),
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
        description="Fit declared empirical/linear mechanisms with the selected source-bound DoWhy GCM worker, or explicitly request native_hybrid research fitting.",
        tags=frozenset({"causal", "gcm", "structural", "hybrid"}),
        assumptions={
            "graph_validity": "Selected GCM requires a fully observed declared static DAG; no automatic mechanism or DAG assignment is claimed.",
            "linear_hybrid_scope": (
                "Strict Bayesian hybrid fit is implemented for linear-gaussian mechanisms."
            ),
            "law_h": "Mechanism params must remain JSON-serializable.",
        },
        when_to_use="Fit Graphical Causal Model to data given known DAG structure; estimate mechanisms for causal queries",
        citations=(
            "Pearl, J. (2009). Causality: Models, Reasoning, and Inference. Cambridge University Press.",
        ),
        when_not_to_use="Selected GCM worker/profile or actual source custody unavailable; unknown DAG or undeclared iid sampling law for bootstrap inference.",
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
        if any(edge.lag not in (None, 0) for edge in graph.edges):
            raise ValueError(
                "gcm_fit is a static consumer; temporal edges require a temporal "
                "fit/expansion before GCM fitting"
            )
        backend = str(params.get("fit_backend", "dowhy_gcm"))
        if backend == "dowhy_gcm":
            scm_spec, _ = _fit_gcm_specs(payload, seed=int(params.get("__seed__", 0) or 0))
            return {
                "structural_causal_model_spec": scm_spec,
                "scm_spec": scm_spec,
                "projected_graph": scm_spec.graph,
                "latent_vars": [],
                "warnings": [],
                "__determinism_tier__": DeterminismTier.STATISTICAL,
            }
        if backend != "native_hybrid":
            raise ValueError("fit_backend must be dowhy_gcm or native_hybrid")
        threshold = float(params.get("latent_sensitivity_threshold", 0.3))
        ridge = float(params.get("bayes_ridge", 1e-6))
        warnings: list[str] = []

        projected_graph = graph
        latent_vars: list[str] = []
        if graph.graph_type is not GraphType.DAG:
            projected_graph, latent_vars = pag_to_dag_projection(graph)

        dowhy_available = 0.0

        data = np.asarray(payload.data, dtype=float)
        column_index = {name: idx for idx, name in enumerate(payload.column_names)}
        parents_map = _parents_by_node(projected_graph)
        non_roots = {edge.dst for edge in projected_graph.edges}

        mechanisms: list[NodeMechanism] = []
        source_summary = {source.value: 0 for source in MechanismSource}
        hybrid_fallback_count = 0
        unstable_due_to_latent = False
        observed_root_count = 0
        missing_root_count = 0

        latent_set = set(latent_vars)
        for variable in projected_graph.nodes:
            is_root = variable not in non_roots

            parents = list(parents_map.get(variable, []))
            has_node_data = variable in column_index
            has_parent_data = all(parent in column_index for parent in parents)
            prior_spec = payload.literature_priors.get(variable, {})
            has_prior = bool(prior_spec)

            if is_root and not has_node_data and not has_prior:
                missing_root_count += 1
                warnings.append(
                    f"missing root mechanism for '{variable}'; query will use a declared "
                    "hypothesis only when explicitly requested"
                )
                continue

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
            if is_root and has_node_data:
                observed_root_count += 1
                family = MechanismFamily.EMPIRICAL
                family_params = _empirical_params(y)
                family_params.update(
                    {
                        "observed_samples": y.tolist(),
                        "observed_samples_source": "SCMFitData.data",
                        "observed_sample_alignment": "column_row_order",
                        "joint_sample_group": "SCMFitData.observed_roots",
                    }
                )
            elif source is MechanismSource.DATA_FITTED:
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
            "n_observed_roots": float(observed_root_count),
            "n_missing_roots": float(missing_root_count),
            "latent_vars_count": float(len(latent_vars)),
            "unstable_due_to_latent": 1.0 if unstable_due_to_latent else 0.0,
        }
        fit_method = "native_hybrid"
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
            "structural_causal_model_spec": scm_spec,
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
