"""Assess identification under partial network observability."""
from __future__ import annotations

from collections import deque
from enum import Enum
from itertools import combinations
from math import comb
from typing import Any, Mapping, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .protocols import (
    EstimandAssessment,
    MissingnessAssessment,
    MissingnessAssessmentScope,
    NetworkData,
    NetworkEstimandTarget,
    NetworkIdentificationStatus,
    NetworkMissingnessRisk,
)


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class NetworkMissingnessMode(str, Enum):
    """Operational mode for missingness assessment."""

    DESIGN_BASED = "design_based"
    MODEL_BASED = "model_based"
    BOUNDS_ONLY = "bounds_only"
    SENSITIVITY = "sensitivity"


class NetworkMissingnessType(str, Enum):
    """High-level missingness regime for the observed network."""

    NODE_SAMPLING = "node_sampling"
    LINK_CENSORING = "link_censoring"
    MIXED = "mixed"
    STRATEGIC_NON_DISCLOSURE = "strategic_non_disclosure"


class NetworkMissingnessRequest(BaseModel):
    """Input contract for network missingness assessment."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    scope: MissingnessAssessmentScope = MissingnessAssessmentScope.FINITE_POPULATION
    frame_observed: bool = True
    missingness_type: NetworkMissingnessType = NetworkMissingnessType.LINK_CENSORING
    mode: NetworkMissingnessMode = NetworkMissingnessMode.BOUNDS_ONLY
    estimands: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    missingness_hypotheses: tuple[dict[str, Any], ...] = ()
    node_observed_mask: Any | None = None
    dyad_observed_mask: Any | None = None
    confirmed_absence_mask: Any | None = None
    structural_missing_dyad_mask: Any | None = None
    node_inclusion_probabilities: Any | None = None
    dyad_inclusion_probabilities: Any | None = None
    gold_standard_adjacency: Any | None = None
    validation_node_mask: Any | None = None
    shortest_path_pairs: tuple[tuple[Any, Any], ...] = ()
    fixed_choice_limit: int | None = Field(default=None, ge=1)
    sensitivity_parameter: str = "delta"
    sensitivity_values: tuple[float, ...] = ()
    posterior_draws: int = Field(default=256, ge=32, le=4096)
    credible_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    prior_edge_alpha: float = Field(default=1.0, gt=0.0)
    prior_edge_beta: float = Field(default=1.0, gt=0.0)
    posterior_seed: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "node_observed_mask",
        "dyad_observed_mask",
        "confirmed_absence_mask",
        "structural_missing_dyad_mask",
        "node_inclusion_probabilities",
        "dyad_inclusion_probabilities",
        "gold_standard_adjacency",
        "validation_node_mask",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)


def maybe_build_missingness_assessment(
    state: NetworkData | Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
) -> MissingnessAssessment | None:
    """Return a missingness assessment when the caller provides a request block."""

    data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
    params = dict(params or {})
    raw = (
        params.get("missingness_assessment")
        or params.get("missingness")
        or data.metadata.get("missingness_assessment")
        or data.metadata.get("missingness")
    )
    if raw is None:
        return None
    if isinstance(raw, MissingnessAssessment):
        return raw
    if isinstance(raw, Mapping) and "global_risk" in raw and "estimands" in raw and "mode" not in raw:
        return MissingnessAssessment.model_validate(raw)
    request = raw if isinstance(raw, NetworkMissingnessRequest) else NetworkMissingnessRequest.model_validate(raw)
    return build_network_missingness_assessment(data, request)


def build_network_missingness_assessment(
    state: NetworkData | Mapping[str, Any],
    request: NetworkMissingnessRequest | Mapping[str, Any],
) -> MissingnessAssessment:
    """Build an identification-aware missingness assessment for a network."""

    data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
    req = request if isinstance(request, NetworkMissingnessRequest) else NetworkMissingnessRequest.model_validate(request)

    observed_edges, asymmetry_rate = _binary_undirected_adjacency(np.asarray(data.adjacency))
    n_nodes = observed_edges.shape[0]
    node_ids = tuple(data.node_ids or [str(idx) for idx in range(n_nodes)])
    node_observed = _optional_bool_vector(req.node_observed_mask, n_nodes, "node_observed_mask")
    dyad_observed = _optional_bool_matrix(req.dyad_observed_mask, n_nodes, "dyad_observed_mask")
    confirmed_absence = _optional_bool_matrix(req.confirmed_absence_mask, n_nodes, "confirmed_absence_mask")
    structural_missing = _optional_bool_matrix(
        req.structural_missing_dyad_mask,
        n_nodes,
        "structural_missing_dyad_mask",
    )
    if structural_missing is None:
        structural_missing = np.zeros((n_nodes, n_nodes), dtype=bool)
    np.fill_diagonal(structural_missing, True)
    if dyad_observed is not None:
        dyad_observed = dyad_observed & ~structural_missing
    if confirmed_absence is None:
        if dyad_observed is not None:
            confirmed_absence = dyad_observed & ~observed_edges
        else:
            confirmed_absence = np.zeros((n_nodes, n_nodes), dtype=bool)
    else:
        confirmed_absence = confirmed_absence & ~observed_edges & ~structural_missing
    uncertain = ~(observed_edges | confirmed_absence | structural_missing)
    np.fill_diagonal(uncertain, False)

    node_probs, node_prob_source = _resolve_node_inclusion_probabilities(
        request=req,
        node_observed=node_observed,
        n_nodes=n_nodes,
    )
    dyad_probs, dyad_prob_source = _resolve_dyad_inclusion_probabilities(
        request=req,
        dyad_observed=dyad_observed,
        n_nodes=n_nodes,
        structural_missing=structural_missing,
    )
    edge_probs = _combine_edge_inclusion_probabilities(node_probs, dyad_probs)

    observed_summary = _observed_graph_summary(observed_edges, uncertain, confirmed_absence, structural_missing)
    diagnostics = _build_diagnostics(
        data=data,
        request=req,
        observed_edges=observed_edges,
        uncertain=uncertain,
        confirmed_absence=confirmed_absence,
        structural_missing=structural_missing,
        node_observed=node_observed,
        dyad_observed=dyad_observed,
        edge_probs=edge_probs,
        node_probs=node_probs,
        dyad_probs=dyad_probs,
        node_prob_source=node_prob_source,
        dyad_prob_source=dyad_prob_source,
        asymmetry_rate=asymmetry_rate,
    )
    estimands = _assess_estimands(
        data=data,
        request=req,
        node_ids=node_ids,
        node_observed=node_observed,
        dyad_observed=dyad_observed,
        observed_edges=observed_edges,
        uncertain=uncertain,
        confirmed_absence=confirmed_absence,
        edge_probs=edge_probs,
        node_probs=node_probs,
        dyad_probs=dyad_probs,
        node_prob_source=node_prob_source,
        dyad_prob_source=dyad_prob_source,
    )
    risk = _global_risk(req, estimands, diagnostics)
    recommendations = _recommendations(req, estimands, diagnostics)
    return MissingnessAssessment(
        scope=req.scope,
        observed_graph_summary=observed_summary,
        assumptions=req.assumptions,
        missingness_hypotheses=req.missingness_hypotheses,
        diagnostics=diagnostics,
        estimands=estimands,
        global_risk=risk,
        recommendations=recommendations,
    )


def _assess_estimands(
    *,
    data: NetworkData,
    request: NetworkMissingnessRequest,
    node_ids: Sequence[str],
    node_observed: np.ndarray | None,
    dyad_observed: np.ndarray | None,
    observed_edges: np.ndarray,
    uncertain: np.ndarray,
    confirmed_absence: np.ndarray,
    edge_probs: np.ndarray | None,
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
    node_prob_source: str,
    dyad_prob_source: str,
) -> dict[str, EstimandAssessment]:
    estimands = request.estimands or _default_estimands(request.mode)
    assessments: dict[str, EstimandAssessment] = {}
    compatibility = observed_edges | uncertain
    for estimand in estimands:
        key = str(estimand)
        normalized = _normalize_estimand_name(key)
        if normalized in {"edge_count", "average_degree", "triangle_count", "wedge_count", "clustering"}:
            if request.mode in {NetworkMissingnessMode.DESIGN_BASED, NetworkMissingnessMode.SENSITIVITY}:
                assessment = _design_based_estimand(
                    name=normalized,
                    request=request,
                    observed_edges=observed_edges,
                    edge_probs=edge_probs,
                    node_probs=node_probs,
                    dyad_probs=dyad_probs,
                    node_prob_source=node_prob_source,
                    dyad_prob_source=dyad_prob_source,
                )
                if (
                    request.mode is NetworkMissingnessMode.SENSITIVITY
                    and assessment.identification_status is NetworkIdentificationStatus.POINT_IDENTIFIED
                ):
                    assessment = _with_sensitivity_region(
                        name=normalized,
                        base=assessment,
                        request=request,
                        observed_edges=observed_edges,
                        edge_probs=edge_probs,
                        node_probs=node_probs,
                        dyad_probs=dyad_probs,
                    )
            elif request.mode is NetworkMissingnessMode.BOUNDS_ONLY:
                assessment = _bounds_estimand(
                    name=normalized,
                    request=request,
                    node_ids=node_ids,
                    observed_edges=observed_edges,
                    compatibility=compatibility,
                    uncertain=uncertain,
                    confirmed_absence=confirmed_absence,
                )
            else:
                assessment = _model_based_estimand(
                    name=normalized,
                    request=request,
                    node_ids=node_ids,
                    observed_edges=observed_edges,
                    uncertain=uncertain,
                    confirmed_absence=confirmed_absence,
                )
        elif normalized == "degree_distribution":
            if request.mode in {NetworkMissingnessMode.DESIGN_BASED, NetworkMissingnessMode.SENSITIVITY}:
                assessment = _degree_distribution_assessment(
                    request=request,
                    observed_edges=observed_edges,
                    node_observed_mask=node_observed,
                    edge_probs=edge_probs,
                    node_probs=node_probs,
                    dyad_probs=dyad_probs,
                    node_prob_source=node_prob_source,
                    dyad_prob_source=dyad_prob_source,
                )
                if (
                    request.mode is NetworkMissingnessMode.SENSITIVITY
                    and assessment.identification_status is NetworkIdentificationStatus.POINT_IDENTIFIED
                ):
                    assessment = _with_sensitivity_region(
                        name=normalized,
                        base=assessment,
                        request=request,
                        observed_edges=observed_edges,
                        edge_probs=edge_probs,
                        node_probs=node_probs,
                        dyad_probs=dyad_probs,
                    )
            elif request.mode is NetworkMissingnessMode.MODEL_BASED:
                assessment = _model_based_estimand(
                    name=normalized,
                    request=request,
                    node_ids=node_ids,
                    observed_edges=observed_edges,
                    uncertain=uncertain,
                    confirmed_absence=confirmed_absence,
                )
            else:
                assessment = EstimandAssessment(
                    name="degree_distribution",
                    target=NetworkEstimandTarget.REALIZED_GRAPH,
                    identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                    diagnostics={"reason": "degree_distribution_requires_design_or_model_based_mode"},
                    algorithm="binomial_degree_deconvolution",
                    complexity="O(n^3)",
                )
        elif normalized in {"degree_bounds", "degree_centrality", "giant_component", "shortest_paths"}:
            if request.mode is NetworkMissingnessMode.MODEL_BASED:
                assessment = _model_based_estimand(
                    name=normalized,
                    request=request,
                    node_ids=node_ids,
                    observed_edges=observed_edges,
                    uncertain=uncertain,
                    confirmed_absence=confirmed_absence,
                )
            else:
                assessment = _bounds_estimand(
                    name=normalized,
                    request=request,
                    node_ids=node_ids,
                    observed_edges=observed_edges,
                    compatibility=compatibility,
                    uncertain=uncertain,
                    confirmed_absence=confirmed_absence,
                )
        elif normalized.endswith("centrality") or normalized in {
            "diffusion_parameters",
            "contagion_parameters",
            "peer_effects",
        }:
            if request.mode is NetworkMissingnessMode.MODEL_BASED and normalized not in {
                "diffusion_parameters",
                "contagion_parameters",
                "peer_effects",
            }:
                assessment = _model_based_estimand(
                    name=normalized,
                    request=request,
                    node_ids=node_ids,
                    observed_edges=observed_edges,
                    uncertain=uncertain,
                    confirmed_absence=confirmed_absence,
                )
            else:
                assessment = _model_dependent_stub(normalized)
        else:
            assessment = EstimandAssessment(
                name=normalized,
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                assumptions_required=(),
                diagnostics={"reason": "unsupported_estimand"},
                algorithm="unsupported",
                complexity="n/a",
            )
        assessments[key] = assessment
    return assessments


def _design_based_estimand(
    *,
    name: str,
    request: NetworkMissingnessRequest,
    observed_edges: np.ndarray,
    edge_probs: np.ndarray | None,
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
    node_prob_source: str,
    dyad_prob_source: str,
) -> EstimandAssessment:
    n_nodes = observed_edges.shape[0]
    if edge_probs is None:
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
            assumptions_required=("known positive inclusion probabilities",),
            diagnostics={"reason": "missing_inclusion_probabilities"},
            algorithm="horvitz_thompson",
            complexity="O(m_obs)",
        )
    if request.scope is not MissingnessAssessmentScope.FINITE_POPULATION:
        return _model_dependent_stub(name)

    if name == "edge_count":
        point, se = _ht_edge_total(observed_edges, edge_probs)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.POINT_IDENTIFIED,
            assumptions_required=_design_assumptions(
                request,
                node_prob_source=node_prob_source,
                dyad_prob_source=dyad_prob_source,
            ),
            estimator=_design_estimator_name(node_prob_source, dyad_prob_source),
            estimate=point,
            std_error=se,
            diagnostics={
                **_probability_summary(edge_probs),
                "node_probability_source": node_prob_source,
                "dyad_probability_source": dyad_prob_source,
            },
            algorithm="horvitz_thompson",
            complexity="O(n^2)",
        )

    if name == "average_degree":
        point_m, se_m = _ht_edge_total(observed_edges, edge_probs)
        scale = 2.0 / float(n_nodes)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.POINT_IDENTIFIED,
            assumptions_required=_design_assumptions(
                request,
                node_prob_source=node_prob_source,
                dyad_prob_source=dyad_prob_source,
            ),
            estimator=_design_estimator_name(node_prob_source, dyad_prob_source),
            estimate=scale * point_m,
            std_error=scale * se_m if se_m is not None else None,
            diagnostics={
                **_probability_summary(edge_probs),
                "node_probability_source": node_prob_source,
                "dyad_probability_source": dyad_prob_source,
            },
            algorithm="horvitz_thompson",
            complexity="O(n^2)",
        )

    if name in {"triangle_count", "wedge_count", "clustering"}:
        motif_stats = _ht_motif_totals(
            observed_edges=observed_edges,
            node_probs=node_probs,
            dyad_probs=dyad_probs,
        )
        if motif_stats is None:
            return EstimandAssessment(
                name=name,
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                assumptions_required=_design_assumptions(
                    request,
                    node_prob_source=node_prob_source,
                    dyad_prob_source=dyad_prob_source,
                ),
                diagnostics={"reason": "motif_inclusion_probabilities_unavailable"},
                algorithm="ratio_ht" if name == "clustering" else "horvitz_thompson",
                complexity="O(n^3)",
            )
        triangle_point, triangle_se, wedge_point, wedge_se = motif_stats
        if name == "triangle_count":
            return EstimandAssessment(
                name=name,
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.POINT_IDENTIFIED,
                assumptions_required=_design_assumptions(
                    request,
                    node_prob_source=node_prob_source,
                    dyad_prob_source=dyad_prob_source,
                )
                + ("independent node/dyad inclusion for motif probabilities",),
                estimator=_design_estimator_name(node_prob_source, dyad_prob_source),
                estimate=triangle_point,
                std_error=triangle_se,
                diagnostics={
                    **_probability_summary(edge_probs),
                    "motif": "triangle",
                    "node_probability_source": node_prob_source,
                    "dyad_probability_source": dyad_prob_source,
                },
                algorithm="horvitz_thompson",
                complexity="O(n^3)",
            )
        if name == "wedge_count":
            return EstimandAssessment(
                name=name,
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.POINT_IDENTIFIED,
                assumptions_required=_design_assumptions(
                    request,
                    node_prob_source=node_prob_source,
                    dyad_prob_source=dyad_prob_source,
                )
                + ("independent node/dyad inclusion for motif probabilities",),
                estimator=_design_estimator_name(node_prob_source, dyad_prob_source),
                estimate=wedge_point,
                std_error=wedge_se,
                diagnostics={
                    **_probability_summary(edge_probs),
                    "motif": "wedge",
                    "node_probability_source": node_prob_source,
                    "dyad_probability_source": dyad_prob_source,
                },
                algorithm="horvitz_thompson",
                complexity="O(n^3)",
            )
        if wedge_point <= 0.0:
            return EstimandAssessment(
                name=name,
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                assumptions_required=_design_assumptions(
                    request,
                    node_prob_source=node_prob_source,
                    dyad_prob_source=dyad_prob_source,
                ),
                diagnostics={"reason": "wedge_denominator_zero"},
                algorithm="ratio_ht",
                complexity="O(n^3)",
            )
        clustering = 3.0 * triangle_point / wedge_point
        variance = 0.0
        if triangle_se is not None:
            variance += (3.0 / wedge_point) ** 2 * (triangle_se**2)
        if wedge_se is not None:
            variance += ((3.0 * triangle_point) / (wedge_point**2)) ** 2 * (wedge_se**2)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.POINT_IDENTIFIED,
            assumptions_required=_design_assumptions(
                request,
                node_prob_source=node_prob_source,
                dyad_prob_source=dyad_prob_source,
            )
            + ("independent node/dyad inclusion for motif probabilities",),
            estimator="estimated_ratio_HT"
            if node_prob_source != "provided" or dyad_prob_source != "provided"
            else "ratio_HT",
            estimate=clustering,
            std_error=float(np.sqrt(max(variance, 0.0))),
            diagnostics={
                **_probability_summary(edge_probs),
                "triangle_estimate": triangle_point,
                "wedge_estimate": wedge_point,
                "node_probability_source": node_prob_source,
                "dyad_probability_source": dyad_prob_source,
            },
            algorithm="ratio_ht",
            complexity="O(n^3)",
        )

    return _model_dependent_stub(name)


def _degree_distribution_assessment(
    *,
    request: NetworkMissingnessRequest,
    observed_edges: np.ndarray,
    node_observed_mask: np.ndarray | None,
    edge_probs: np.ndarray | None,
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
    node_prob_source: str,
    dyad_prob_source: str,
) -> EstimandAssessment:
    if request.mode not in {NetworkMissingnessMode.DESIGN_BASED, NetworkMissingnessMode.SENSITIVITY}:
        return EstimandAssessment(
            name="degree_distribution",
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
            diagnostics={"reason": "degree_distribution_requires_design_based_mode"},
            algorithm="binomial_degree_deconvolution",
            complexity="O(n^3)",
        )
    if not request.frame_observed:
        return EstimandAssessment(
            name="degree_distribution",
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
            diagnostics={"reason": "full_node_frame_required"},
            algorithm="binomial_degree_deconvolution",
            complexity="O(n^3)",
        )
    if edge_probs is None and node_probs is None:
        return EstimandAssessment(
            name="degree_distribution",
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
            assumptions_required=("known homogeneous edge or node inclusion probability",),
            diagnostics={"reason": "missing_edge_probabilities"},
            algorithm="binomial_degree_deconvolution",
            complexity="O(n^3)",
        )
    observed_degree = np.sum(observed_edges, axis=1).astype(int)
    q: float | None
    sampled_nodes = None if node_observed_mask is None else np.flatnonzero(node_observed_mask)
    if node_observed_mask is not None and not bool(np.all(node_observed_mask)):
        node_sampling_q = _homogeneous_node_sampling_neighbor_capture_probability(node_probs, dyad_probs)
        if node_sampling_q is None:
            return EstimandAssessment(
                name="degree_distribution",
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                assumptions_required=("homogeneous Bernoulli node sampling or mixed homogeneous thinning",),
                diagnostics={"reason": "heterogeneous_node_sampling_probabilities"},
                algorithm="binomial_degree_deconvolution",
                complexity="O(n^3)",
            )
        if sampled_nodes is None or sampled_nodes.size == 0:
            return EstimandAssessment(
                name="degree_distribution",
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                assumptions_required=("non-empty sampled node set",),
                diagnostics={"reason": "no_sampled_nodes"},
                algorithm="binomial_degree_deconvolution",
                complexity="O(n^3)",
            )
        observed_degree = observed_degree[sampled_nodes]
        q = node_sampling_q
    else:
        q = _homogeneous_off_diagonal_probability(edge_probs)
    if q is None:
        return EstimandAssessment(
            name="degree_distribution",
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
            assumptions_required=("homogeneous independent Bernoulli edge censoring",),
            diagnostics={"reason": "heterogeneous_edge_probabilities"},
            algorithm="binomial_degree_deconvolution",
            complexity="O(n^3)",
        )
    probs, diagnostics = _invert_binomial_degree_distribution(observed_degree, q)
    diagnostics["node_probability_source"] = node_prob_source
    diagnostics["dyad_probability_source"] = dyad_prob_source
    diagnostics["sampled_node_count"] = int(len(observed_degree))
    return EstimandAssessment(
        name="degree_distribution",
        target=NetworkEstimandTarget.REALIZED_GRAPH,
        identification_status=NetworkIdentificationStatus.POINT_IDENTIFIED,
        assumptions_required=(
            "known or estimated homogeneous independent Bernoulli thinning",
            "all nodes belong to the observed frame",
        ),
        estimator=(
            "estimated_binomial_degree_deconvolution"
            if node_prob_source != "provided" or dyad_prob_source != "provided"
            else "binomial_degree_deconvolution"
        ),
        estimate={str(degree): float(prob) for degree, prob in enumerate(probs)},
        diagnostics=diagnostics,
        algorithm="binomial_degree_deconvolution",
        complexity="O(n^3)",
    )


def _bounds_estimand(
    *,
    name: str,
    request: NetworkMissingnessRequest,
    node_ids: Sequence[str],
    observed_edges: np.ndarray,
    compatibility: np.ndarray,
    uncertain: np.ndarray,
    confirmed_absence: np.ndarray,
) -> EstimandAssessment:
    if not request.frame_observed:
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
            assumptions_required=("known node frame",),
            diagnostics={"reason": "frame_not_observed"},
            algorithm="observed_compatibility_bounds",
            complexity="O(n + m)",
        )
    n_nodes = observed_edges.shape[0]
    observed_edge_count = _edge_count(observed_edges)
    compatibility_edge_count = _edge_count(compatibility)
    if name == "edge_count":
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("no false positive observed ties", "known node frame"),
            identification_region=(observed_edge_count, compatibility_edge_count),
            diagnostics={"sharp": True, "uncertain_dyad_count": int(_edge_count(uncertain))},
            algorithm="observed_compatibility_bounds",
            complexity="O(n^2)",
        )
    if name == "average_degree":
        scale = 2.0 / float(n_nodes)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("no false positive observed ties", "known node frame"),
            identification_region=(scale * observed_edge_count, scale * compatibility_edge_count),
            diagnostics={"sharp": True},
            algorithm="observed_compatibility_bounds",
            complexity="O(n^2)",
        )
    if name == "triangle_count":
        lower = _triangle_count(observed_edges)
        upper = _triangle_upper_bound(observed_edges, uncertain, confirmed_absence)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("known node frame", "no false positive observed ties"),
            identification_region=(lower, upper),
            diagnostics={"sharp": True},
            algorithm="triangle_completion_bounds",
            complexity="O(n^3)",
        )
    if name == "wedge_count":
        lower = _wedge_count(observed_edges)
        upper = _wedge_count(compatibility)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("known node frame",),
            identification_region=(lower, upper),
            diagnostics={"sharp": True},
            algorithm="observed_compatibility_bounds",
            complexity="O(n^2)",
        )
    if name == "clustering":
        triangle_lower = _triangle_count(observed_edges)
        triangle_upper = _triangle_upper_bound(observed_edges, uncertain, confirmed_absence)
        wedge_lower = _wedge_count(observed_edges)
        wedge_upper = _wedge_count(compatibility)
        if wedge_upper <= 0:
            region: tuple[float | None, float | None] = (None, None)
        else:
            lower = 0.0 if wedge_upper <= 0 else 3.0 * triangle_lower / wedge_upper
            upper = 1.0 if wedge_lower <= 0 else min(1.0, 3.0 * triangle_upper / wedge_lower)
            region = (lower, upper)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("known node frame", "no false positive observed ties"),
            identification_region=region,
            diagnostics={"sharp": False, "outer_bound": True},
            algorithm="triangle_wedge_outer_bounds",
            complexity="O(n^3)",
        )
    if name == "degree_bounds":
        observed_degree = np.sum(observed_edges, axis=1).astype(int)
        compatibility_degree = np.sum(compatibility, axis=1).astype(int)
        region = {
            node_ids[idx]: (int(observed_degree[idx]), int(compatibility_degree[idx]))
            for idx in range(n_nodes)
        }
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("known node frame",),
            identification_region=region,
            diagnostics={"sharp": True},
            algorithm="node_degree_bounds",
            complexity="O(n^2)",
        )
    if name == "degree_centrality":
        observed_degree = np.sum(observed_edges, axis=1).astype(float)
        compatibility_degree = np.sum(compatibility, axis=1).astype(float)
        scale = 1.0 / float(max(n_nodes - 1, 1))
        region = {
            node_ids[idx]: (float(observed_degree[idx] * scale), float(compatibility_degree[idx] * scale))
            for idx in range(n_nodes)
        }
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("known node frame",),
            identification_region=region,
            diagnostics={"sharp": True},
            algorithm="node_degree_centrality_bounds",
            complexity="O(n^2)",
        )
    if name == "giant_component":
        lower = _largest_component_size(observed_edges) / float(n_nodes)
        upper = _largest_component_size(compatibility) / float(n_nodes)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("known node frame", "no false positive observed ties"),
            identification_region=(lower, upper),
            diagnostics={"sharp": True},
            algorithm="observed_compatibility_bounds",
            complexity="O(n + m)",
        )
    if name == "shortest_paths":
        pairs = _resolve_shortest_path_pairs(node_ids, request.shortest_path_pairs, n_nodes)
        if pairs is None:
            return EstimandAssessment(
                name=name,
                target=NetworkEstimandTarget.REALIZED_GRAPH,
                identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                assumptions_required=("known node frame", "explicit shortest_path_pairs or small graph"),
                diagnostics={"reason": "shortest_path_pairs_required_for_large_graph"},
                algorithm="observed_compatibility_bounds",
                complexity="O(|pairs| * (n + m))",
            )
        observed_distances = _distances_for_pairs(observed_edges, pairs)
        compatibility_distances = _distances_for_pairs(compatibility, pairs)
        region = {
            f"({node_ids[src]},{node_ids[dst]})": (
                _distance_or_none(compatibility_distances[(src, dst)]),
                _distance_or_none(observed_distances[(src, dst)]),
            )
            for src, dst in pairs
        }
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.REALIZED_GRAPH,
            identification_status=NetworkIdentificationStatus.SET_IDENTIFIED,
            assumptions_required=("known node frame", "no false positive observed ties"),
            identification_region=region,
            diagnostics={"sharp": True, "n_pairs": len(region)},
            algorithm="observed_compatibility_bounds",
            complexity="O(|pairs| * (n + m))",
        )
    return _model_dependent_stub(name)


def _model_based_estimand(
    *,
    name: str,
    request: NetworkMissingnessRequest,
    node_ids: Sequence[str],
    observed_edges: np.ndarray,
    uncertain: np.ndarray,
    confirmed_absence: np.ndarray,
) -> EstimandAssessment:
    if not request.frame_observed:
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.EXPECTED_UNDER_MODEL,
            identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
            assumptions_required=("known node frame", "declared superpopulation model"),
            diagnostics={"reason": "frame_not_observed"},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * statistic_cost)",
        )
    draws, posterior_summary = _posterior_predictive_draws(
        observed_edges=observed_edges,
        uncertain=uncertain,
        confirmed_absence=confirmed_absence,
        request=request,
    )
    if not draws:
        return _model_dependent_stub(name)
    credible_level = request.credible_level
    if name == "edge_count":
        values = [float(_edge_count(draw)) for draw in draws]
        estimate, interval, std_error = _numeric_posterior_summary(values, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            std_error=std_error,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^2)",
        )
    if name == "average_degree":
        values = [2.0 * _edge_count(draw) / float(draw.shape[0]) for draw in draws]
        estimate, interval, std_error = _numeric_posterior_summary(values, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            std_error=std_error,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^2)",
        )
    if name == "triangle_count":
        values = [float(_triangle_count(draw)) for draw in draws]
        estimate, interval, std_error = _numeric_posterior_summary(values, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            std_error=std_error,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^3)",
        )
    if name == "wedge_count":
        values = [float(_wedge_count(draw)) for draw in draws]
        estimate, interval, std_error = _numeric_posterior_summary(values, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            std_error=std_error,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^2)",
        )
    if name == "clustering":
        values = []
        for draw in draws:
            wedge = _wedge_count(draw)
            values.append(0.0 if wedge <= 0 else 3.0 * _triangle_count(draw) / wedge)
        estimate, interval, std_error = _numeric_posterior_summary(values, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            std_error=std_error,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^3)",
        )
    if name == "degree_distribution":
        per_degree: dict[str, list[float]] = {str(k): [] for k in range(observed_edges.shape[0])}
        for draw in draws:
            distribution = _degree_distribution(draw)
            for degree, value in distribution.items():
                per_degree[str(degree)].append(value)
        estimate, interval = _dict_posterior_summary(per_degree, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^2)",
        )
    if name == "degree_bounds":
        series: dict[str, list[float]] = {node_id: [] for node_id in node_ids}
        for draw in draws:
            degree = np.sum(draw, axis=1)
            for idx, node_id in enumerate(node_ids):
                series[node_id].append(float(degree[idx]))
        estimate, interval = _dict_posterior_summary(series, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^2)",
        )
    if name == "giant_component":
        values = [_largest_component_size(draw) / float(draw.shape[0]) for draw in draws]
        estimate, interval, std_error = _numeric_posterior_summary(values, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            std_error=std_error,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * (n + m))",
        )
    if name == "shortest_paths":
        pairs = _resolve_shortest_path_pairs(node_ids, request.shortest_path_pairs, observed_edges.shape[0])
        if pairs is None:
            return EstimandAssessment(
                name=name,
                target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
                identification_status=NetworkIdentificationStatus.NOT_IDENTIFIED,
                assumptions_required=_model_based_assumptions() + ("explicit shortest_path_pairs for large graphs",),
                diagnostics={"reason": "shortest_path_pairs_required_for_large_graph"},
                algorithm="beta_bernoulli_posterior_predictive",
                complexity="O(draws * |pairs| * (n + m))",
            )
        series: dict[str, list[float]] = {f"({node_ids[src]},{node_ids[dst]})": [] for src, dst in pairs}
        for draw in draws:
            distances = _distances_for_pairs(draw, pairs)
            for src, dst in pairs:
                value = distances[(src, dst)]
                series[f"({node_ids[src]},{node_ids[dst]})"].append(value)
        estimate, interval = _path_posterior_summary(series, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            diagnostics={**posterior_summary, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * |pairs| * (n + m))",
        )
    if name in {
        "degree_centrality",
        "closeness_centrality",
        "betweenness_centrality",
        "eigenvector_centrality",
    }:
        series: dict[str, list[float]] = {node_id: [] for node_id in node_ids}
        centrality_diagnostics: dict[str, Any] = {}
        for draw in draws:
            scores, diag = _centrality_scores(draw, name)
            for idx, node_id in enumerate(node_ids):
                series[node_id].append(float(scores[idx]))
            centrality_diagnostics.update(diag)
        estimate, interval = _dict_posterior_summary(series, credible_level)
        return EstimandAssessment(
            name=name,
            target=NetworkEstimandTarget.POSTERIOR_PREDICTIVE,
            identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
            assumptions_required=_model_based_assumptions(),
            estimator="beta_bernoulli_posterior_predictive",
            estimate=estimate,
            diagnostics={**posterior_summary, **centrality_diagnostics, "credible_interval": interval},
            algorithm="beta_bernoulli_posterior_predictive",
            complexity="O(draws * n^3)",
        )
    return _model_dependent_stub(name)


def _with_sensitivity_region(
    *,
    name: str,
    base: EstimandAssessment,
    request: NetworkMissingnessRequest,
    observed_edges: np.ndarray,
    edge_probs: np.ndarray | None,
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
) -> EstimandAssessment:
    values = request.sensitivity_values
    if not values or edge_probs is None:
        return base
    records: list[Any] = []
    for delta in values:
        adjusted_dyad_probs: np.ndarray | None = None
        adjusted_edge_probs: np.ndarray | None = None
        if dyad_probs is not None:
            adjusted_dyad_probs = _logit_shift(dyad_probs, delta)
            adjusted_edge_probs = _combine_edge_inclusion_probabilities(node_probs, adjusted_dyad_probs)
        else:
            adjusted_edge_probs = _logit_shift(edge_probs, delta)
        if name in {"edge_count", "average_degree"}:
            point, _ = _ht_edge_total(observed_edges, adjusted_edge_probs)
            if name == "average_degree":
                point *= 2.0 / float(observed_edges.shape[0])
            records.append(point)
        elif name in {"triangle_count", "wedge_count", "clustering"}:
            motif_stats = _ht_motif_totals(
                observed_edges=observed_edges,
                node_probs=node_probs,
                dyad_probs=adjusted_dyad_probs if adjusted_dyad_probs is not None else adjusted_edge_probs,
                precombined_edge_probs=adjusted_edge_probs if adjusted_dyad_probs is None else None,
            )
            if motif_stats is None:
                records.append(None)
                continue
            triangle_point, _, wedge_point, _ = motif_stats
            if name == "triangle_count":
                records.append(triangle_point)
            elif name == "wedge_count":
                records.append(wedge_point)
            else:
                records.append(None if wedge_point <= 0 else 3.0 * triangle_point / wedge_point)
        elif name == "degree_distribution":
            degree_assessment = _degree_distribution_assessment(
                request=request.model_copy(
                    update={
                        "node_inclusion_probabilities": node_probs,
                        "dyad_inclusion_probabilities": (
                            adjusted_dyad_probs if adjusted_dyad_probs is not None else adjusted_edge_probs
                        ),
                    }
                ),
                observed_edges=observed_edges,
                node_observed_mask=request.node_observed_mask,
                edge_probs=adjusted_edge_probs,
                node_probs=node_probs,
                dyad_probs=adjusted_dyad_probs if adjusted_dyad_probs is not None else dyad_probs,
                node_prob_source="provided" if node_probs is not None else "missing",
                dyad_prob_source=(
                    "provided"
                    if adjusted_dyad_probs is not None or adjusted_edge_probs is not None
                    else "missing"
                ),
            )
            if degree_assessment.identification_status is not NetworkIdentificationStatus.POINT_IDENTIFIED:
                records.append(None)
            else:
                records.append(degree_assessment.estimate)
        else:
            records.append(None)
    payload = {
        "parameter_name": request.sensitivity_parameter,
        "parameter_values": tuple(float(value) for value in values),
        "point_estimates": tuple(records),
    }
    return base.model_copy(update={"sensitivity_region": payload})


def _model_dependent_stub(name: str) -> EstimandAssessment:
    return EstimandAssessment(
        name=name,
        target=NetworkEstimandTarget.EXPECTED_UNDER_MODEL,
        identification_status=NetworkIdentificationStatus.MODEL_DEPENDENT,
        assumptions_required=("correctly specified network model", "missingness model distinct from graph model"),
        diagnostics={"reason": "requires_likelihood_or_bayesian_network_model"},
        algorithm="model_based_reconstruction",
        complexity="superlinear / sampler-dependent",
    )


def _default_estimands(mode: NetworkMissingnessMode) -> tuple[str, ...]:
    if mode in {NetworkMissingnessMode.DESIGN_BASED, NetworkMissingnessMode.SENSITIVITY}:
        return ("edge_count", "average_degree", "triangle_count", "wedge_count", "clustering")
    if mode is NetworkMissingnessMode.BOUNDS_ONLY:
        return ("edge_count", "average_degree", "degree_bounds", "giant_component", "shortest_paths")
    return ("edge_count", "average_degree", "degree_distribution", "clustering", "giant_component")


def _design_assumptions(
    request: NetworkMissingnessRequest,
    *,
    node_prob_source: str = "missing",
    dyad_prob_source: str = "missing",
) -> tuple[str, ...]:
    items = [
        "no false positive observed ties",
        "provided or estimated positive inclusion probabilities",
        "MAR-like ignorability for design-based weighting",
    ]
    if request.missingness_type is NetworkMissingnessType.MIXED:
        items.append("independent node and dyad inclusion probabilities")
    elif request.missingness_type is NetworkMissingnessType.NODE_SAMPLING:
        items.append("independent node sampling with known inclusion probabilities")
    elif request.missingness_type is NetworkMissingnessType.LINK_CENSORING:
        items.append("independent dyad censoring with known inclusion probabilities")
    if node_prob_source != "provided" or dyad_prob_source != "provided":
        items.append("homogeneous inclusion probabilities estimated from observation masks")
    return tuple(items)


def _design_estimator_name(node_prob_source: str, dyad_prob_source: str) -> str:
    if node_prob_source == "provided" and dyad_prob_source == "provided":
        return "Horvitz-Thompson"
    return "estimated_Horvitz-Thompson"


def _model_based_assumptions() -> tuple[str, ...]:
    return (
        "known node frame",
        "conditionally independent Bernoulli ties for unobserved dyads",
        "MAR-like missingness so unobserved dyads do not update the likelihood beyond the observed frame",
    )


def _resolve_node_inclusion_probabilities(
    *,
    request: NetworkMissingnessRequest,
    node_observed: np.ndarray | None,
    n_nodes: int,
) -> tuple[np.ndarray | None, str]:
    provided = _node_inclusion_probabilities(request.node_inclusion_probabilities, n_nodes)
    if provided is not None:
        return provided, "provided"
    if node_observed is None:
        return None, "missing"
    estimated = float(np.mean(node_observed))
    arr = np.full(n_nodes, estimated, dtype=float)
    return np.clip(arr, 0.0, 1.0), "estimated_from_node_observed_mask"


def _resolve_dyad_inclusion_probabilities(
    *,
    request: NetworkMissingnessRequest,
    dyad_observed: np.ndarray | None,
    n_nodes: int,
    structural_missing: np.ndarray,
) -> tuple[np.ndarray | None, str]:
    provided = _dyad_inclusion_probabilities(request.dyad_inclusion_probabilities, n_nodes)
    if provided is not None:
        return provided, "provided"
    if dyad_observed is None:
        return None, "missing"
    structural_missing_count = int(_edge_count(structural_missing))
    auditable_dyads = max(comb(n_nodes, 2) - structural_missing_count, 0)
    observed_share = (
        float(_edge_count(dyad_observed)) / float(auditable_dyads)
        if auditable_dyads > 0
        else 0.0
    )
    arr = np.full((n_nodes, n_nodes), observed_share, dtype=float)
    np.fill_diagonal(arr, 1.0)
    return np.clip(arr, 0.0, 1.0), "estimated_from_dyad_observed_mask"


def _normalize_estimand_name(name: str) -> str:
    mapping = {
        "n_edges": "edge_count",
        "edges": "edge_count",
        "mean_degree": "average_degree",
        "giant_component_size": "giant_component",
        "shortest_path": "shortest_paths",
    }
    return mapping.get(name, name)


def _build_diagnostics(
    *,
    data: NetworkData,
    request: NetworkMissingnessRequest,
    observed_edges: np.ndarray,
    uncertain: np.ndarray,
    confirmed_absence: np.ndarray,
    structural_missing: np.ndarray,
    node_observed: np.ndarray | None,
    dyad_observed: np.ndarray | None,
    edge_probs: np.ndarray | None,
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
    node_prob_source: str,
    dyad_prob_source: str,
    asymmetry_rate: float,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    n_nodes = observed_edges.shape[0]
    total_dyads = comb(n_nodes, 2)
    structural_missing_count = int(_edge_count(structural_missing))
    auditable_dyads = max(total_dyads - structural_missing_count, 0)
    observed_dyad_share = None
    if dyad_observed is not None and auditable_dyads > 0:
        observed_dyad_share = float(_edge_count(dyad_observed)) / float(auditable_dyads)
    elif node_observed is not None and auditable_dyads > 0:
        node_pair_mask = np.outer(node_observed, node_observed).astype(bool)
        np.fill_diagonal(node_pair_mask, False)
        observed_dyad_share = float(_edge_count(node_pair_mask)) / float(auditable_dyads)
    coverage_audit = {
        "n_nodes": n_nodes,
        "frame_observed": request.frame_observed,
        "sampled_node_share": float(np.mean(node_observed)) if node_observed is not None else (
            1.0 if request.missingness_type is NetworkMissingnessType.LINK_CENSORING else None
        ),
        "observed_dyad_share": observed_dyad_share,
        "structural_missing_share": (
            float(structural_missing_count) / float(total_dyads) if total_dyads > 0 else None
        ),
        "administratively_missing_share": float(_edge_count(uncertain)) / float(auditable_dyads) if auditable_dyads > 0 else None,
    }
    diagnostics["coverage_audit"] = coverage_audit
    diagnostics["positivity_audit"] = _probability_summary(edge_probs)
    diagnostics["positivity_audit"]["node_probability_source"] = node_prob_source
    diagnostics["positivity_audit"]["dyad_probability_source"] = dyad_prob_source
    diagnostics["plausibility_of_mar"] = _mar_plausibility(
        data=data,
        node_observed=node_observed,
        dyad_observed=dyad_observed,
        observed_edges=observed_edges,
    )
    diagnostics["fixed_choice_censoring_test"] = _fixed_choice_test(
        observed_edges=observed_edges,
        limit=request.fixed_choice_limit,
    )
    diagnostics["reciprocity_disagreement_check"] = {
        "asymmetry_rate": asymmetry_rate,
        "strategic_non_disclosure_signal": asymmetry_rate > 0.05,
    }
    diagnostics["validation_gap"] = _validation_gap(
        observed_edges=observed_edges,
        gold_standard=request.gold_standard_adjacency,
        validation_node_mask=request.validation_node_mask,
    )
    if request.mode is NetworkMissingnessMode.MODEL_BASED:
        _, posterior_summary = _posterior_predictive_draws(
            observed_edges=observed_edges,
            uncertain=uncertain,
            confirmed_absence=confirmed_absence,
            request=request,
        )
        diagnostics["model_fit_diagnostics"] = {
            "status": "ok",
            "model_class": "beta_bernoulli_posterior_predictive",
            **posterior_summary,
        }
    else:
        diagnostics["model_fit_diagnostics"] = {
            "status": "not_run",
            "reason": "model_based_mode_not_requested",
        }
    if node_probs is not None:
        diagnostics["node_inclusion_probability_summary"] = {
            "min": float(np.min(node_probs)),
            "max": float(np.max(node_probs)),
        }
    if dyad_probs is not None:
        diagnostics["dyad_inclusion_probability_summary"] = _probability_summary(dyad_probs)
    diagnostics["confirmed_absence_count"] = int(_edge_count(confirmed_absence))
    return diagnostics


def _global_risk(
    request: NetworkMissingnessRequest,
    estimands: Mapping[str, EstimandAssessment],
    diagnostics: Mapping[str, Any],
) -> NetworkMissingnessRisk:
    statuses = {assessment.identification_status for assessment in estimands.values()}
    observed_dyad_share = diagnostics.get("coverage_audit", {}).get("observed_dyad_share")
    min_prob = diagnostics.get("positivity_audit", {}).get("min_edge_inclusion_probability")
    if request.missingness_type is NetworkMissingnessType.STRATEGIC_NON_DISCLOSURE:
        return NetworkMissingnessRisk.SEVERE
    if NetworkIdentificationStatus.NOT_IDENTIFIED in statuses:
        return NetworkMissingnessRisk.HIGH
    if NetworkIdentificationStatus.MODEL_DEPENDENT in statuses:
        return NetworkMissingnessRisk.HIGH
    if observed_dyad_share is not None and observed_dyad_share < 0.35:
        return NetworkMissingnessRisk.HIGH
    if min_prob is not None and min_prob < 0.05:
        return NetworkMissingnessRisk.HIGH
    if NetworkIdentificationStatus.SET_IDENTIFIED in statuses:
        return NetworkMissingnessRisk.MODERATE
    return NetworkMissingnessRisk.LOW


def _recommendations(
    request: NetworkMissingnessRequest,
    estimands: Mapping[str, EstimandAssessment],
    diagnostics: Mapping[str, Any],
) -> tuple[str, ...]:
    items: list[str] = []
    statuses = {assessment.identification_status for assessment in estimands.values()}
    if NetworkIdentificationStatus.NOT_IDENTIFIED in statuses:
        items.append("Provide known node or dyad inclusion probabilities, or a validation subgraph, before reporting nonlocal corrected point estimates.")
    if NetworkIdentificationStatus.SET_IDENTIFIED in statuses:
        items.append("Report interval bounds for path and connectivity metrics instead of a single corrected point estimate.")
    if request.missingness_type is NetworkMissingnessType.STRATEGIC_NON_DISCLOSURE:
        items.append("Run sensitivity mode over a delta grid and report the tipping point where substantive conclusions change.")
    min_prob = diagnostics.get("positivity_audit", {}).get("min_edge_inclusion_probability")
    if min_prob is not None and min_prob < 0.05:
        items.append("Near-zero inclusion probabilities create extreme weights; trim or redesign the sampling frame before trusting HT corrections.")
    if request.mode is NetworkMissingnessMode.MODEL_BASED:
        items.append("Mark any reconstructed graph functional as model-dependent and include posterior predictive checks in the runtime artifact.")
    if not items:
        items.append("Current assumptions support only low-risk local summaries; keep global claims aligned with the returned identification status.")
    return tuple(dict.fromkeys(items))


def _observed_graph_summary(
    observed_edges: np.ndarray,
    uncertain: np.ndarray,
    confirmed_absence: np.ndarray,
    structural_missing: np.ndarray,
) -> dict[str, Any]:
    n_nodes = observed_edges.shape[0]
    observed_edge_count = _edge_count(observed_edges)
    total_dyads = max(comb(n_nodes, 2) - int(_edge_count(structural_missing)), 1)
    components = _component_sizes(observed_edges)
    return {
        "n_nodes": n_nodes,
        "observed_edge_count": int(observed_edge_count),
        "observed_density": float(observed_edge_count) / float(total_dyads),
        "observed_triangle_count": int(_triangle_count(observed_edges)),
        "observed_wedge_count": int(_wedge_count(observed_edges)),
        "observed_component_count": len(components),
        "observed_largest_component_share": float(max(components, default=0)) / float(max(n_nodes, 1)),
        "uncertain_dyad_count": int(_edge_count(uncertain)),
        "confirmed_absence_count": int(_edge_count(confirmed_absence)),
        "structural_missing_dyad_count": int(_edge_count(structural_missing)),
    }


def _mar_plausibility(
    *,
    data: NetworkData,
    node_observed: np.ndarray | None,
    dyad_observed: np.ndarray | None,
    observed_edges: np.ndarray,
) -> dict[str, Any]:
    if node_observed is None and dyad_observed is None:
        return {"status": "not_run", "reason": "missing observation masks"}
    observed_degree = np.sum(observed_edges, axis=1).astype(float)
    payload: dict[str, Any] = {"status": "heuristic"}
    if node_observed is not None:
        payload["node_observed_vs_degree_corr"] = _safe_correlation(node_observed.astype(float), observed_degree)
        if data.node_features is not None:
            features = np.asarray(data.node_features, dtype=float)
            payload["node_observed_feature_r2"] = _linear_fit_r2(features, node_observed.astype(float))
    if dyad_observed is not None:
        dyad_counts = np.sum(dyad_observed, axis=1).astype(float)
        payload["dyad_observed_vs_observed_degree_corr"] = _safe_correlation(dyad_counts, observed_degree)
    degree_corr = payload.get("node_observed_vs_degree_corr")
    if degree_corr is not None and abs(degree_corr) > 0.3:
        payload["mnar_risk"] = "elevated"
    else:
        payload["mnar_risk"] = "limited_evidence"
    return payload


def _fixed_choice_test(*, observed_edges: np.ndarray, limit: int | None) -> dict[str, Any]:
    if limit is None:
        return {"status": "not_run", "reason": "fixed_choice_limit_not_provided"}
    observed_degree = np.sum(observed_edges, axis=1).astype(int)
    at_limit = float(np.mean(observed_degree == limit))
    above_limit = float(np.mean(observed_degree > limit))
    return {
        "status": "heuristic",
        "fixed_choice_limit": int(limit),
        "share_at_limit": at_limit,
        "share_above_limit": above_limit,
        "possible_censoring": at_limit >= 0.1 and above_limit == 0.0,
    }


def _validation_gap(
    *,
    observed_edges: np.ndarray,
    gold_standard: np.ndarray | None,
    validation_node_mask: np.ndarray | None,
) -> dict[str, Any]:
    if gold_standard is None:
        return {"status": "not_run", "reason": "gold_standard_not_provided"}
    gold_edges, _ = _binary_undirected_adjacency(gold_standard)
    if gold_edges.shape != observed_edges.shape:
        return {"status": "invalid", "reason": "gold_standard_shape_mismatch"}
    active = np.ones(observed_edges.shape[0], dtype=bool)
    if validation_node_mask is not None:
        if validation_node_mask.ndim != 1 or validation_node_mask.shape[0] != observed_edges.shape[0]:
            return {"status": "invalid", "reason": "validation_node_mask_shape_mismatch"}
        active = validation_node_mask.astype(bool)
    pairs = np.outer(active, active)
    np.fill_diagonal(pairs, False)
    true_edges = gold_edges & pairs
    observed_true_edges = observed_edges & true_edges
    gold_edge_count = _edge_count(true_edges)
    observed_edge_count = _edge_count(observed_true_edges)
    false_negatives = gold_edge_count - observed_edge_count
    extra_edges = _edge_count(observed_edges & ~gold_edges & pairs)
    return {
        "status": "ok",
        "edge_recall": None if gold_edge_count == 0 else observed_edge_count / gold_edge_count,
        "false_negative_count": int(false_negatives),
        "unexpected_observed_edges": int(extra_edges),
    }


def _binary_undirected_adjacency(adjacency: np.ndarray) -> tuple[np.ndarray, float]:
    arr = np.asarray(adjacency, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError("adjacency must be square")
    asymmetry = float(np.mean(np.abs(arr - arr.T) > 1e-12))
    binary = (arr > 0.0) | (arr.T > 0.0)
    binary = binary.astype(bool)
    np.fill_diagonal(binary, False)
    return binary, asymmetry


def _optional_bool_vector(value: np.ndarray | None, n: int, name: str) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=bool)
    if arr.ndim != 1 or arr.shape[0] != n:
        raise ValueError(f"{name} must have shape ({n},)")
    return arr


def _optional_bool_matrix(value: np.ndarray | None, n: int, name: str) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=bool)
    if arr.ndim != 2 or arr.shape != (n, n):
        raise ValueError(f"{name} must have shape ({n}, {n})")
    arr = arr | arr.T
    np.fill_diagonal(arr, False)
    return arr


def _node_inclusion_probabilities(value: np.ndarray | None, n: int) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1 or arr.shape[0] != n:
        raise ValueError(f"node_inclusion_probabilities must have shape ({n},)")
    return np.clip(arr, 0.0, 1.0)


def _dyad_inclusion_probabilities(value: np.ndarray | None, n: int) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2 or arr.shape != (n, n):
        raise ValueError(f"dyad_inclusion_probabilities must have shape ({n}, {n})")
    arr = 0.5 * (arr + arr.T)
    arr = np.clip(arr, 0.0, 1.0)
    np.fill_diagonal(arr, 1.0)
    return arr


def _combine_edge_inclusion_probabilities(
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
) -> np.ndarray | None:
    if node_probs is None and dyad_probs is None:
        return None
    if node_probs is None:
        combined = np.asarray(dyad_probs, dtype=float)
    elif dyad_probs is None:
        combined = np.outer(node_probs, node_probs)
    else:
        combined = np.outer(node_probs, node_probs) * dyad_probs
    combined = np.asarray(combined, dtype=float)
    np.fill_diagonal(combined, 1.0)
    return np.clip(combined, 0.0, 1.0)


def _probability_summary(probabilities: np.ndarray | None) -> dict[str, Any]:
    if probabilities is None:
        return {"status": "not_available"}
    mask = ~np.eye(probabilities.shape[0], dtype=bool)
    values = probabilities[mask]
    positive = values[values > 0.0]
    return {
        "status": "ok",
        "min_edge_inclusion_probability": float(np.min(positive)) if positive.size else None,
        "max_edge_inclusion_probability": float(np.max(values)) if values.size else None,
        "near_zero_overlap": bool(positive.size and np.min(positive) < 0.05),
    }


def _ht_edge_total(observed_edges: np.ndarray, edge_probs: np.ndarray) -> tuple[float, float | None]:
    point = 0.0
    variance = 0.0
    for i in range(observed_edges.shape[0]):
        for j in range(i + 1, observed_edges.shape[1]):
            if edge_probs[i, j] <= 0.0 and observed_edges[i, j]:
                raise ValueError("observed edge has zero inclusion probability")
            if observed_edges[i, j]:
                point += 1.0 / edge_probs[i, j]
                variance += (1.0 - edge_probs[i, j]) / (edge_probs[i, j] ** 2)
    return float(point), float(np.sqrt(max(variance, 0.0)))


def _ht_motif_totals(
    *,
    observed_edges: np.ndarray,
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
    precombined_edge_probs: np.ndarray | None = None,
) -> tuple[float, float | None, float, float | None] | None:
    n_nodes = observed_edges.shape[0]
    if precombined_edge_probs is None and node_probs is None and dyad_probs is None:
        return None
    if precombined_edge_probs is not None:
        edge_probs = precombined_edge_probs
        node_probs = np.ones(n_nodes, dtype=float)
        dyad_probs = np.asarray(precombined_edge_probs, dtype=float)
    else:
        edge_probs = _combine_edge_inclusion_probabilities(node_probs, dyad_probs)
        if edge_probs is None:
            return None
        if node_probs is None:
            node_probs = np.ones(n_nodes, dtype=float)
        if dyad_probs is None:
            dyad_probs = np.asarray(edge_probs, dtype=float)
    triangle_point = 0.0
    triangle_variance = 0.0
    wedge_point = 0.0
    wedge_variance = 0.0
    for i, j, k in combinations(range(n_nodes), 3):
        triangle_obs = bool(observed_edges[i, j] and observed_edges[i, k] and observed_edges[j, k])
        triangle_prob = (
            node_probs[i]
            * node_probs[j]
            * node_probs[k]
            * dyad_probs[i, j]
            * dyad_probs[i, k]
            * dyad_probs[j, k]
        )
        if triangle_obs:
            if triangle_prob <= 0.0:
                return None
            triangle_point += 1.0 / triangle_prob
            triangle_variance += (1.0 - triangle_prob) / (triangle_prob**2)
        wedge_specs = (
            ((i, j), (i, k), i),
            ((i, j), (j, k), j),
            ((i, k), (j, k), k),
        )
        for (a, b), (c, d), center in wedge_specs:
            wedge_obs = bool(observed_edges[a, b] and observed_edges[c, d])
            neighbor_1 = b if a == center else a
            neighbor_2 = d if c == center else c
            wedge_prob = (
                node_probs[center]
                * node_probs[neighbor_1]
                * node_probs[neighbor_2]
                * dyad_probs[a, b]
                * dyad_probs[c, d]
            )
            if wedge_obs:
                if wedge_prob <= 0.0:
                    return None
                wedge_point += 1.0 / wedge_prob
                wedge_variance += (1.0 - wedge_prob) / (wedge_prob**2)
    return (
        float(triangle_point),
        float(np.sqrt(max(triangle_variance, 0.0))),
        float(wedge_point),
        float(np.sqrt(max(wedge_variance, 0.0))),
    )


def _homogeneous_off_diagonal_probability(edge_probs: np.ndarray | None) -> float | None:
    if edge_probs is None:
        return None
    mask = ~np.eye(edge_probs.shape[0], dtype=bool)
    values = edge_probs[mask]
    if values.size == 0:
        return None
    if float(np.max(values) - np.min(values)) > 1e-8:
        return None
    return float(values[0])


def _invert_binomial_degree_distribution(observed_degree: np.ndarray, q: float) -> tuple[np.ndarray, dict[str, Any]]:
    n_nodes = observed_degree.shape[0]
    max_degree = n_nodes - 1
    empirical = np.bincount(observed_degree, minlength=max_degree + 1).astype(float) / float(max(n_nodes, 1))
    if q <= 0.0:
        raise ValueError("q must be positive")
    matrix = np.zeros((max_degree + 1, max_degree + 1), dtype=float)
    for k in range(max_degree + 1):
        for degree in range(k, max_degree + 1):
            matrix[k, degree] = comb(degree, k) * (q**k) * ((1.0 - q) ** (degree - k))
    raw = np.linalg.solve(matrix, empirical)
    clipped = np.clip(raw, 0.0, None)
    total = float(np.sum(clipped))
    probs = clipped if total <= 0.0 else clipped / total
    condition_number = float(np.linalg.cond(matrix))
    diagnostics = {
        "observed_degree_distribution": {str(k): float(v) for k, v in enumerate(empirical)},
        "edge_observation_probability": float(q),
        "deconvolution_condition_number": condition_number,
        "raw_min_probability": float(np.min(raw)),
        "stabilized": bool(np.min(raw) < -1e-8 or abs(total - 1.0) > 1e-8),
    }
    return probs, diagnostics


def _homogeneous_node_sampling_neighbor_capture_probability(
    node_probs: np.ndarray | None,
    dyad_probs: np.ndarray | None,
) -> float | None:
    if node_probs is None:
        return None
    if float(np.max(node_probs) - np.min(node_probs)) > 1e-8:
        return None
    p = float(node_probs[0])
    if dyad_probs is None:
        return p
    q = _homogeneous_off_diagonal_probability(dyad_probs)
    if q is None:
        return None
    return float(p * q)


def _posterior_predictive_draws(
    *,
    observed_edges: np.ndarray,
    uncertain: np.ndarray,
    confirmed_absence: np.ndarray,
    request: NetworkMissingnessRequest,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    observed_edge_count = _edge_count(observed_edges)
    observed_nonedge_count = _edge_count(confirmed_absence)
    alpha_post = request.prior_edge_alpha + observed_edge_count
    beta_post = request.prior_edge_beta + observed_nonedge_count
    rng = np.random.default_rng(int(request.posterior_seed))
    posterior_p = rng.beta(alpha_post, beta_post, size=request.posterior_draws)
    uncertain_pairs = np.transpose(np.triu(uncertain, k=1).nonzero())
    draws: list[np.ndarray] = []
    for probability in posterior_p:
        draw = observed_edges.copy()
        if uncertain_pairs.size:
            sampled = rng.uniform(size=uncertain_pairs.shape[0]) < float(probability)
            for (i, j), include in zip(uncertain_pairs, sampled, strict=False):
                if include:
                    draw[int(i), int(j)] = True
                    draw[int(j), int(i)] = True
        draws.append(draw)
    credible_interval = _quantile_interval(posterior_p.tolist(), request.credible_level)
    diagnostics = {
        "posterior_draws": int(request.posterior_draws),
        "credible_level": float(request.credible_level),
        "prior_edge_alpha": float(request.prior_edge_alpha),
        "prior_edge_beta": float(request.prior_edge_beta),
        "posterior_edge_probability_mean": float(np.mean(posterior_p)),
        "posterior_edge_probability_interval": credible_interval,
        "observed_edge_count": int(observed_edge_count),
        "observed_nonedge_count": int(observed_nonedge_count),
        "uncertain_dyad_count": int(_edge_count(uncertain)),
        "effective_sample_size": int(request.posterior_draws),
        "fit_converged": True,
    }
    return draws, diagnostics


def _numeric_posterior_summary(
    values: Sequence[float],
    credible_level: float,
) -> tuple[float | None, tuple[float | None, float | None], float | None]:
    if not values:
        return None, (None, None), None
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None, (None, None), None
    interval = _quantile_interval(finite.tolist(), credible_level)
    std_error = float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0
    return float(np.mean(finite)), interval, std_error


def _dict_posterior_summary(
    values: Mapping[str, Sequence[float]],
    credible_level: float,
) -> tuple[dict[str, float | None], dict[str, tuple[float | None, float | None]]]:
    estimate: dict[str, float | None] = {}
    interval: dict[str, tuple[float | None, float | None]] = {}
    for key, series in values.items():
        mean, band, _ = _numeric_posterior_summary(series, credible_level)
        estimate[key] = mean
        interval[key] = band
    return estimate, interval


def _path_posterior_summary(
    values: Mapping[str, Sequence[float]],
    credible_level: float,
) -> tuple[dict[str, float | None], dict[str, tuple[float | None, float | None]]]:
    estimate: dict[str, float | None] = {}
    interval: dict[str, tuple[float | None, float | None]] = {}
    for key, series in values.items():
        finite = [float(value) for value in series if np.isfinite(value)]
        if not finite:
            estimate[key] = None
            interval[key] = (None, None)
            continue
        mean, band, _ = _numeric_posterior_summary(finite, credible_level)
        estimate[key] = mean
        interval[key] = band
    return estimate, interval


def _quantile_interval(
    values: Sequence[float],
    credible_level: float,
) -> tuple[float | None, float | None]:
    if not values:
        return (None, None)
    alpha = max((1.0 - credible_level) / 2.0, 0.0)
    arr = np.asarray(values, dtype=float)
    return (float(np.quantile(arr, alpha)), float(np.quantile(arr, 1.0 - alpha)))


def _degree_distribution(adjacency: np.ndarray) -> dict[int, float]:
    degree = np.sum(adjacency, axis=1).astype(int)
    counts = np.bincount(degree, minlength=adjacency.shape[0]).astype(float)
    counts /= float(max(adjacency.shape[0], 1))
    return {degree_value: float(prob) for degree_value, prob in enumerate(counts)}


def _centrality_scores(adjacency: np.ndarray, name: str) -> tuple[np.ndarray, dict[str, Any]]:
    n_nodes = adjacency.shape[0]
    if name == "degree_centrality":
        scale = max(n_nodes - 1, 1)
        return np.sum(adjacency, axis=1) / float(scale), {"centrality_variant": "degree"}
    if name == "closeness_centrality":
        return _harmonic_closeness(adjacency), {"centrality_variant": "harmonic_closeness"}
    if name == "betweenness_centrality":
        return _betweenness_centrality(adjacency), {"centrality_variant": "brandes_unweighted"}
    if name == "eigenvector_centrality":
        return _eigenvector_centrality(adjacency), {"centrality_variant": "dominant_eigenvector"}
    raise ValueError(f"unsupported centrality name: {name}")


def _harmonic_closeness(adjacency: np.ndarray) -> np.ndarray:
    n_nodes = adjacency.shape[0]
    scores = np.zeros(n_nodes, dtype=float)
    for source in range(n_nodes):
        distances = _bfs_distances(adjacency, source)
        finite = distances[np.isfinite(distances) & (distances > 0)]
        scores[source] = float(np.sum(1.0 / finite)) / float(max(n_nodes - 1, 1)) if finite.size else 0.0
    return scores


def _betweenness_centrality(adjacency: np.ndarray) -> np.ndarray:
    n_nodes = adjacency.shape[0]
    scores = np.zeros(n_nodes, dtype=float)
    neighbors = [np.flatnonzero(adjacency[node]).tolist() for node in range(n_nodes)]
    for source in range(n_nodes):
        stack: list[int] = []
        predecessors: list[list[int]] = [[] for _ in range(n_nodes)]
        sigma = np.zeros(n_nodes, dtype=float)
        sigma[source] = 1.0
        distance = -np.ones(n_nodes, dtype=int)
        distance[source] = 0
        queue: deque[int] = deque([source])
        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            for neighbor in neighbors[vertex]:
                if distance[neighbor] < 0:
                    queue.append(neighbor)
                    distance[neighbor] = distance[vertex] + 1
                if distance[neighbor] == distance[vertex] + 1:
                    sigma[neighbor] += sigma[vertex]
                    predecessors[neighbor].append(vertex)
        dependency = np.zeros(n_nodes, dtype=float)
        while stack:
            vertex = stack.pop()
            for predecessor in predecessors[vertex]:
                if sigma[vertex] > 0.0:
                    dependency[predecessor] += (sigma[predecessor] / sigma[vertex]) * (1.0 + dependency[vertex])
            if vertex != source:
                scores[vertex] += dependency[vertex]
    if n_nodes > 2:
        scores /= float((n_nodes - 1) * (n_nodes - 2) / 2.0)
    return scores


def _eigenvector_centrality(adjacency: np.ndarray) -> np.ndarray:
    if not np.any(adjacency):
        return np.zeros(adjacency.shape[0], dtype=float)
    matrix = adjacency.astype(float)
    eigvals, eigvecs = np.linalg.eigh(matrix)
    dominant = np.abs(eigvecs[:, int(np.argmax(eigvals))])
    total = float(np.sum(dominant))
    if total <= 0.0:
        return dominant
    return dominant / total


def _edge_count(adjacency: np.ndarray) -> int:
    return int(np.sum(np.triu(adjacency.astype(int), k=1)))


def _triangle_count(adjacency: np.ndarray) -> int:
    arr = adjacency.astype(int)
    product = arr @ arr @ arr
    return int(np.trace(product) // 6)


def _triangle_upper_bound(
    observed_edges: np.ndarray,
    uncertain: np.ndarray,
    confirmed_absence: np.ndarray,
) -> int:
    possible = observed_edges | uncertain
    upper = 0
    for i, j, k in combinations(range(observed_edges.shape[0]), 3):
        if confirmed_absence[i, j] or confirmed_absence[i, k] or confirmed_absence[j, k]:
            continue
        if possible[i, j] and possible[i, k] and possible[j, k]:
            upper += 1
    return upper


def _wedge_count(adjacency: np.ndarray) -> int:
    degree = np.sum(adjacency, axis=1)
    return int(np.sum(degree * (degree - 1) / 2))


def _component_sizes(adjacency: np.ndarray) -> list[int]:
    n_nodes = adjacency.shape[0]
    seen = np.zeros(n_nodes, dtype=bool)
    sizes: list[int] = []
    for start in range(n_nodes):
        if seen[start]:
            continue
        queue: deque[int] = deque([start])
        seen[start] = True
        size = 0
        while queue:
            node = queue.popleft()
            size += 1
            neighbors = np.flatnonzero(adjacency[node])
            for neighbor in neighbors:
                if not seen[neighbor]:
                    seen[neighbor] = True
                    queue.append(int(neighbor))
        sizes.append(size)
    return sizes


def _largest_component_size(adjacency: np.ndarray) -> int:
    return max(_component_sizes(adjacency), default=0)


def _resolve_shortest_path_pairs(
    node_ids: Sequence[str],
    pairs: Sequence[tuple[Any, Any]],
    n_nodes: int,
) -> list[tuple[int, int]] | None:
    if pairs:
        mapping = {node_id: idx for idx, node_id in enumerate(node_ids)}
        resolved: list[tuple[int, int]] = []
        for left, right in pairs:
            src = mapping[left] if isinstance(left, str) else int(left)
            dst = mapping[right] if isinstance(right, str) else int(right)
            if src == dst:
                continue
            if src < 0 or src >= n_nodes or dst < 0 or dst >= n_nodes:
                raise ValueError("shortest_path_pairs contain an out-of-range node index")
            resolved.append((min(src, dst), max(src, dst)))
        return sorted(set(resolved))
    if n_nodes <= 32:
        return [(i, j) for i in range(n_nodes) for j in range(i + 1, n_nodes)]
    return None


def _distances_for_pairs(adjacency: np.ndarray, pairs: Sequence[tuple[int, int]]) -> dict[tuple[int, int], float]:
    by_source: dict[int, list[int]] = {}
    for src, dst in pairs:
        by_source.setdefault(src, []).append(dst)
    output: dict[tuple[int, int], float] = {}
    for src, dsts in by_source.items():
        distances = _bfs_distances(adjacency, src)
        for dst in dsts:
            output[(src, dst)] = float(distances[dst])
    return output


def _bfs_distances(adjacency: np.ndarray, source: int) -> np.ndarray:
    n_nodes = adjacency.shape[0]
    distance = np.full(n_nodes, np.inf, dtype=float)
    queue: deque[int] = deque([source])
    distance[source] = 0.0
    while queue:
        node = queue.popleft()
        for neighbor in np.flatnonzero(adjacency[node]):
            if not np.isfinite(distance[neighbor]):
                distance[neighbor] = distance[node] + 1.0
                queue.append(int(neighbor))
    return distance


def _distance_or_none(distance: float) -> int | None:
    if not np.isfinite(distance):
        return None
    return int(distance)


def _safe_correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size == 0 or right.size == 0:
        return None
    if float(np.std(left)) <= 1e-12 or float(np.std(right)) <= 1e-12:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def _linear_fit_r2(features: np.ndarray, target: np.ndarray) -> float | None:
    if features.ndim != 2 or features.shape[0] != target.shape[0]:
        return None
    design = np.column_stack([np.ones(features.shape[0]), features])
    coeffs, *_ = np.linalg.lstsq(design, target, rcond=None)
    fitted = design @ coeffs
    total = float(np.sum((target - np.mean(target)) ** 2))
    if total <= 1e-12:
        return None
    resid = float(np.sum((target - fitted) ** 2))
    return max(0.0, 1.0 - resid / total)


def _logit_shift(probabilities: np.ndarray, delta: float) -> np.ndarray:
    arr = np.asarray(probabilities, dtype=float)
    clipped = np.clip(arr, 1e-6, 1.0 - 1e-6)
    shifted = 1.0 / (1.0 + np.exp(-(np.log(clipped / (1.0 - clipped)) + float(delta))))
    np.fill_diagonal(shifted, 1.0)
    return shifted


__all__ = [
    "NetworkMissingnessMode",
    "NetworkMissingnessRequest",
    "NetworkMissingnessType",
    "build_network_missingness_assessment",
    "maybe_build_missingness_assessment",
]
