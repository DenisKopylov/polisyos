"""Interference and network causal inference methods.

Implements four estimators that relax SUTVA (Stable Unit Treatment Value
Assumption) by allowing spillover effects across units connected via a
cluster, network, spatial, or bipartite structure.

References
----------
Hudgens, M.G. & Halloran, M.E. (2008). Toward causal inference with
    interference. JASA 103(482).
Aronow, P.M. & Samii, C. (2017). Estimating average causal effects under
    general interference. Ann. Appl. Stat.
Liu, L., Hudgens, M.G. & Becker-Dreps, S. (2016). On sample randomization
    inference of causal effects in the presence of interference. JRSS-B.
Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal inference in
    the presence of interference. Stat. Methods Med. Res.
Zigler, C.M. & Papadogeorgou, G. (2021). Bipartite causal inference with
    interference. Stat. Sci.
Verbitsky-Savitz, N. & Raudenbush, S.W. (2012). Causal inference under
    interference in spatial settings. Epidemiol. Methods.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
from polisyos.foundry.methods.catalog.causal.protocols import NetworkCausalData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InteractionComplex,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    NetworkInterferenceReport,
)
from polisyos.ir.refs import ArtifactRefModel

_PAIRWISE_QUERY_FAMILY = "pairwise_projection_queries"
_CLUSTER_QUERY_FAMILY = "cluster_projection_queries"
_SIMPLICIAL_STAR_LOCAL_QUERY_FAMILY = "simplicial_star_local_queries"
_UNSUPPORTED_COMPLEX_QUERY_FAMILY = "unsupported_complex_queries"

# ──────────────────────────────────────────────────────────────────────────────
# Shared output slots
# ──────────────────────────────────────────────────────────────────────────────

def _interference_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("report", "json"),
                description="NetworkInterferenceReport with effect decomposition",
            ),
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Low-level algorithm helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_network_data(state: Any) -> NetworkCausalData:
    """Coerce *state* to NetworkCausalData."""
    if isinstance(state, NetworkCausalData):
        return state
    if isinstance(state, dict):
        return NetworkCausalData.model_validate(state)
    raise TypeError(f"Expected NetworkCausalData, got {type(state).__name__}")


_UNIT_SUFFIX_RE = re.compile(r"^(?P<base>.+?)(?:__|_|:)(?P<unit>\d+)$")


def _split_unit_suffix(node: str) -> tuple[str, str | None]:
    """Split a node name into (base, unit) when it follows a unit suffix convention."""
    match = _UNIT_SUFFIX_RE.match(node)
    if match is None:
        return node, None
    return match.group("base"), match.group("unit")


def _resolve_graph_variables(graph: CausalGraphModel, variable: str) -> tuple[str, ...]:
    """Resolve a treatment/outcome label to exact or unit-suffixed graph nodes."""
    if variable in graph.nodes:
        return (variable,)
    matches = tuple(sorted(node for node in graph.nodes if _split_unit_suffix(node)[0] == variable))
    return matches


def _resolve_unit_labels(
    graph: CausalGraphModel,
    *,
    cluster_var: str | None = None,
) -> dict[str, str]:
    """Build a node -> unit label map from explicit metadata or suffixes."""
    metadata = graph.metadata or {}

    explicit_unit_map = metadata.get("unit_map")
    if isinstance(explicit_unit_map, dict):
        resolved: dict[str, str] = {}
        for node, unit in explicit_unit_map.items():
            if node in graph.nodes and unit is not None and str(unit) != "":
                resolved[str(node)] = str(unit)
        if resolved:
            return resolved

    explicit_cluster_map = None
    if cluster_var is not None:
        explicit_cluster_map = metadata.get(cluster_var)
    if explicit_cluster_map is None:
        explicit_cluster_map = metadata.get("cluster_map")
    if isinstance(explicit_cluster_map, dict):
        resolved = {}
        for node, unit in explicit_cluster_map.items():
            if node in graph.nodes and unit is not None and str(unit) != "":
                resolved[str(node)] = str(unit)
        if resolved:
            return resolved

    resolved = {}
    for node in graph.nodes:
        _, unit = _split_unit_suffix(node)
        if unit is not None:
            resolved[node] = unit
    return resolved


def _resolve_cluster_partition(
    graph: CausalGraphModel,
    *,
    cluster_var: str | None = None,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Return node clusters as a tuple of sorted tuples plus node->cluster labels."""
    metadata = graph.metadata or {}
    clusters_payload = None
    if cluster_var is not None:
        clusters_payload = metadata.get(cluster_var)
    if clusters_payload is None:
        clusters_payload = metadata.get("cluster_partition")

    if isinstance(clusters_payload, (list, tuple)) and clusters_payload:
        clusters: list[tuple[str, ...]] = []
        node_to_cluster: dict[str, str] = {}
        for cluster_idx, cluster in enumerate(clusters_payload):
            if isinstance(cluster, (list, tuple, set, frozenset)):
                members = tuple(sorted(str(node) for node in cluster if str(node) in graph.nodes))
            else:
                members = tuple()
            if not members:
                continue
            cluster_name = str(cluster_idx)
            clusters.append(members)
            for node in members:
                node_to_cluster[node] = cluster_name
        if clusters:
            return tuple(clusters), node_to_cluster

    node_to_unit = _resolve_unit_labels(graph, cluster_var=cluster_var)
    if not node_to_unit:
        return tuple(), {}

    grouped: dict[str, list[str]] = {}
    for node, unit in node_to_unit.items():
        grouped.setdefault(unit, []).append(node)

    clusters = []
    for unit, members in sorted(grouped.items(), key=lambda item: item[0]):
        clusters.append(tuple(sorted(members)))
    return tuple(clusters), node_to_unit


def _cross_unit_edges(
    graph: CausalGraphModel,
    node_to_cluster: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    """Return edges whose endpoints belong to different units/clusters."""
    cross_unit: list[tuple[str, str]] = []
    for edge in graph.edges:
        src_cluster = node_to_cluster.get(edge.src)
        dst_cluster = node_to_cluster.get(edge.dst)
        if src_cluster is None or dst_cluster is None:
            continue
        if src_cluster != dst_cluster:
            cross_unit.append((edge.src, edge.dst))
    return tuple(cross_unit)


class InterferenceAugmentedGraph(BaseModel):
    """Graph augmentation used by the interference identification layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    original_graph: CausalGraphModel
    augmented_graph: CausalGraphModel
    exposure_nodes: tuple[str, ...] = ()
    cluster_partition: tuple[tuple[str, ...], ...] = ()
    interference_type: Literal["none", "partial", "network", "bipartite", "spatial"] = "network"
    exposure_mapping: ExposureMappingType = ExposureMappingType.FRACTIONAL
    cross_unit_edges: tuple[tuple[str, str], ...] = ()
    node_to_cluster: dict[str, str] = Field(default_factory=dict)
    cluster_var: str | None = None


class InterferenceIdentificationResult(BaseModel):
    """Result of graph-based interference identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    treatment: str
    outcome: str
    status: Literal["identified", "non_identified", "input_invalid"]
    interference_detected: bool
    sutva_violated: bool
    identification_method: str = "graph_based_interference_id"
    augmented_graph: InterferenceAugmentedGraph
    proof_steps: tuple[IRProofStep, ...] = ()
    trace: tuple[str, ...] = ()
    base_identification_status: str | None = None
    estimand_ast: dict[str, Any] | None = None
    required_distributions: tuple[dict[str, Any], ...] = ()
    negative_certificate: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()


def _coerce_topology_contract_source(
    payload: InterferenceAugmentedGraph | InterferenceIdentificationResult | Mapping[str, Any],
) -> tuple[InterferenceAugmentedGraph, InterferenceIdentificationResult | None]:
    if isinstance(payload, InterferenceIdentificationResult):
        return payload.augmented_graph, payload
    if isinstance(payload, InterferenceAugmentedGraph):
        return payload, None
    if isinstance(payload, Mapping):
        try:
            result = InterferenceIdentificationResult.model_validate(payload)
            return result.augmented_graph, result
        except ValidationError:
            graph = InterferenceAugmentedGraph.model_validate(payload)
            return graph, None
    raise TypeError(
        "Expected InterferenceAugmentedGraph, InterferenceIdentificationResult, or mapping payload"
    )


def _resolved_topology_reduction_policy(
    augmented_graph: InterferenceAugmentedGraph,
    reduction_policy: Literal[
        "pairwise_projection",
        "cluster_projection",
        "full_complex",
    ] | None,
) -> Literal["pairwise_projection", "cluster_projection", "full_complex"]:
    if reduction_policy is not None:
        return reduction_policy

    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = metadata.get("topology")
    if isinstance(topology_metadata, Mapping):
        candidate = str(topology_metadata.get("reduction_policy", "")).strip()
        if candidate in {"pairwise_projection", "cluster_projection", "full_complex"}:
            return candidate  # type: ignore[return-value]
    candidate = str(metadata.get("topology_reduction_policy", "")).strip()
    if candidate in {"pairwise_projection", "cluster_projection", "full_complex"}:
        return candidate  # type: ignore[return-value]
    if augmented_graph.cluster_partition:
        return "cluster_projection"
    return "pairwise_projection"


def _topology_fallback_mode(
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"],
) -> Literal["pairwise", "clustered", "unsupported"]:
    if reduction_policy == "pairwise_projection":
        return "pairwise"
    if reduction_policy == "cluster_projection":
        return "clustered"
    return "unsupported"


def _requested_interference_mode(
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"],
) -> Literal["pairwise", "clustered", "complex"]:
    if reduction_policy == "pairwise_projection":
        return "pairwise"
    if reduction_policy == "cluster_projection":
        return "clustered"
    return "complex"


@dataclass(frozen=True)
class _SimplicialSupportGate:
    supported: bool
    assumptions: tuple[str, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class _TopologyCertificatePlan:
    supported_query_family: str
    fallback_mode: Literal["pairwise", "clustered", "unsupported"]
    exposure_assumptions: tuple[str, ...]
    reduction_error_bound: float | None
    mode_requested: Literal["pairwise", "clustered", "complex"]
    mode_used: Literal["pairwise", "clustered", "complex", "unsupported"]
    fallback_triggered: bool
    fallback_reason_codes: tuple[str, ...]
    estimability_checks: dict[str, Literal["pass", "fail", "not_applicable"]]


@dataclass(frozen=True)
class _ReductionErrorBoundPlan:
    reduction_error_bound: float | None
    assumptions: tuple[str, ...] = ()


def _supported_query_family(
    augmented_graph: InterferenceAugmentedGraph,
    *,
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"],
    fallback_mode: Literal["pairwise", "clustered", "unsupported"],
) -> str:
    if reduction_policy == "pairwise_projection" or fallback_mode == "pairwise":
        return _PAIRWISE_QUERY_FAMILY
    if reduction_policy == "cluster_projection" or fallback_mode == "clustered":
        return _CLUSTER_QUERY_FAMILY
    if augmented_graph.cluster_partition:
        return _CLUSTER_QUERY_FAMILY
    return _PAIRWISE_QUERY_FAMILY


def _exposure_operator_ref(augmented_graph: InterferenceAugmentedGraph) -> ArtifactRefModel:
    digest_payload = "|".join(
        [
            augmented_graph.interference_type,
            augmented_graph.exposure_mapping.value,
            augmented_graph.cluster_var or "",
            ",".join(augmented_graph.exposure_nodes),
            ";".join(f"{src}->{dst}" for src, dst in augmented_graph.cross_unit_edges),
        ]
    )
    digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
    return ArtifactRefModel(
        artifact_id=f"sha256:{digest}",
        kind="ir.interference_exposure_operator",
        media_type="application/json",
    )


def _metadata_topology_groups(
    augmented_graph: InterferenceAugmentedGraph,
    *,
    key: str,
) -> tuple[tuple[str, ...], ...]:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = metadata.get("topology")
    payload = None
    if isinstance(topology_metadata, Mapping):
        payload = topology_metadata.get(key)
    if payload is None:
        payload = metadata.get(key)
    if payload is None:
        return ()
    if not isinstance(payload, (list, tuple)):
        raise ValueError(f"{key} metadata must be a list/tuple of node groups")
    groups: list[tuple[str, ...]] = []
    for index, group in enumerate(payload):
        if not isinstance(group, (list, tuple, set, frozenset)):
            raise ValueError(f"{key}[{index}] must be a list/tuple/set of nodes")
        groups.append(tuple(str(node) for node in group))
    return tuple(groups)


def _materialize_simplicial_closure(
    simplices: tuple[tuple[str, ...], ...],
) -> tuple[tuple[str, ...], ...]:
    closure: set[tuple[str, ...]] = set()
    for simplex in simplices:
        ordered = tuple(simplex)
        if len(ordered) < 2:
            continue
        for size in range(2, len(ordered) + 1):
            for subset in combinations(ordered, size):
                closure.add(tuple(subset))
    return tuple(sorted(closure, key=lambda face: (len(face), face)))


def _topology_metadata(augmented_graph: InterferenceAugmentedGraph) -> Mapping[str, Any]:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = metadata.get("topology")
    if isinstance(topology_metadata, Mapping):
        return topology_metadata
    return {}


def _exposure_operator_metadata(augmented_graph: InterferenceAugmentedGraph) -> Mapping[str, Any]:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    for source in (
        topology_metadata.get("exposure_operator"),
        topology_metadata.get("exposure_operator_metadata"),
        topology_metadata.get("simplicial_exposure_operator"),
        metadata.get("exposure_operator"),
        metadata.get("exposure_operator_metadata"),
        metadata.get("simplicial_exposure_operator"),
    ):
        if isinstance(source, Mapping):
            return source
    return {}


def _bound_model_metadata(augmented_graph: InterferenceAugmentedGraph) -> Mapping[str, Any]:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    for source in (
        topology_metadata.get("bound_model"),
        metadata.get("bound_model"),
    ):
        if isinstance(source, Mapping):
            return source
    return {}


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value) and math.isfinite(float(value))
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "verified",
            "satisfied",
            "supported",
            "positive",
            "randomized",
        }
    return False


def _first_metadata_value(
    *sources: Mapping[str, object],
    keys: tuple[str, ...],
) -> object | None:
    for source in sources:
        for key in keys:
            if key in source:
                return source[key]
    return None


def _finite_codomain_declared(operator_metadata: Mapping[str, Any]) -> bool:
    states = _first_metadata_value(
        operator_metadata,
        keys=("exposure_states", "states", "codomain", "codomain_states"),
    )
    if isinstance(states, (list, tuple, set, frozenset)):
        return len(states) > 0
    cardinality = _first_metadata_value(
        operator_metadata,
        keys=("codomain_cardinality", "state_count", "finite_codomain_size"),
    )
    try:
        return int(cardinality) > 0
    except (TypeError, ValueError):
        return _truthy(operator_metadata.get("finite_codomain"))


def _positive_probability_values(value: object) -> bool:
    if isinstance(value, Mapping):
        values = value.values()
    elif isinstance(value, (list, tuple, set, frozenset)):
        values = value
    else:
        return False
    saw_value = False
    for item in values:
        probability = item.get("probability") if isinstance(item, Mapping) else item
        try:
            casted = float(probability)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(casted) or casted <= 0.0:
            return False
        saw_value = True
    return saw_value


def _randomized_assignment_declared(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
) -> bool:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    if _truthy(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=("randomized_assignment", "known_randomized_design"),
        )
    ):
        return True
    design = _first_metadata_value(
        operator_metadata,
        topology_metadata,
        metadata,
        keys=("assignment_design", "design", "treatment_assignment"),
    )
    if design is None:
        return False
    return str(design).strip().lower() in {
        "randomized",
        "known_randomized",
        "known_design",
        "bernoulli",
        "complete_randomization",
        "two_stage_randomization",
    }


def _design_positivity_declared(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
) -> bool:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    if _truthy(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=("design_positivity", "positivity", "support_positive", "positive_support"),
        )
    ):
        return True
    probabilities = _first_metadata_value(
        operator_metadata,
        topology_metadata,
        metadata,
        keys=("exposure_probabilities", "induced_exposure_probabilities"),
    )
    return _positive_probability_values(probabilities)


def _higher_order_separability_declared(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
) -> bool:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    if _truthy(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=(
                "higher_order_separability_verified",
                "separability_verified",
                "complex_separability_verified",
            ),
        )
    ):
        return True

    sigma_min = _first_metadata_value(
        operator_metadata,
        topology_metadata,
        metadata,
        keys=("design_matrix_sigma_min", "min_singular_value", "sigma_min"),
    )
    threshold = _first_metadata_value(
        operator_metadata,
        topology_metadata,
        metadata,
        keys=("separability_threshold", "kappa_min"),
    )
    try:
        sigma = float(sigma_min)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(sigma) or sigma <= 0.0:
        return False
    if threshold is None:
        return True
    try:
        required = float(threshold)
    except (TypeError, ValueError):
        return False
    return math.isfinite(required) and required > 0.0 and sigma >= required


def _inference_regime_declared(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
) -> bool:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    if _truthy(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=("inference_regime_verified", "variance_certificate_present"),
        )
    ):
        return True

    regime = _first_metadata_value(
        operator_metadata,
        topology_metadata,
        metadata,
        keys=("inference_regime", "variance_regime", "uncertainty_regime"),
    )
    if regime is None:
        return False
    return str(regime).strip().lower() in {
        "randomization_based",
        "conditional_randomization",
        "conditioning_mechanism",
        "ani",
        "local_dependence",
        "cluster_robust",
        "design_based",
    }


def _pre_outcome_selection_declared(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
) -> bool:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    if _truthy(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=("pre_outcome_selection", "mode_selection_pre_outcome"),
        )
    ):
        return True

    selection_stage = _first_metadata_value(
        operator_metadata,
        topology_metadata,
        metadata,
        keys=("selection_stage", "mode_selection_stage", "fallback_selection_stage"),
    )
    if selection_stage is None:
        return False
    return str(selection_stage).strip().lower() in {
        "pre_outcome",
        "pre-treatment",
        "pre_treatment",
        "sample_split",
        "split_sample",
        "cross_fit",
        "cross_fitted",
    }


def _normalized_metadata_token(value: object) -> str | None:
    if value is None:
        return None
    token = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return token or None


def _topology_evidence_assumptions(
    augmented_graph: InterferenceAugmentedGraph,
    interaction_complex: InteractionComplex | None,
) -> tuple[bool, tuple[str, ...]]:
    if interaction_complex is None:
        return False, ()

    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    direct_sources = {
        "administrative",
        "administrative_records",
        "audited",
        "clinical_roster",
        "contract",
        "directly_observed",
        "documented",
        "observed",
        "roster",
    }
    controlled_tokens = {
        "audited",
        "audited_or_directly_observed",
        "audited_or_fdr_controlled",
        "directly_observed",
        "documented",
        "fdr_controlled",
        "posterior_threshold_passed",
        "stability_threshold_passed",
    }

    candidate_topology = _normalized_metadata_token(
        _first_metadata_value(
            topology_metadata,
            metadata,
            keys=(
                "candidate_topology",
                "candidate_topology_evidence",
                "topology_evidence",
                "topology_evidence_mode",
            ),
        )
    )
    if candidate_topology in controlled_tokens:
        assumptions = ["candidate_topology:audited_or_fdr_controlled"]
        if candidate_topology not in {
            "audited_or_directly_observed",
            "audited_or_fdr_controlled",
        }:
            assumptions.append(f"topology_evidence:{candidate_topology}")
        return True, tuple(assumptions)

    if _truthy(
        _first_metadata_value(
            topology_metadata,
            metadata,
            keys=(
                "topology_audited",
                "candidate_topology_audited",
                "directly_observed_topology",
                "documented_group_structure",
                "documented_topology",
                "topology_documented",
            ),
        )
    ):
        return True, (
            "candidate_topology:audited_or_fdr_controlled",
            "topology_evidence:directly_observed",
        )

    topology_source = _normalized_metadata_token(
        _first_metadata_value(
            topology_metadata,
            metadata,
            keys=("topology_source", "candidate_topology_source", "group_structure_source"),
        )
    )
    if topology_source in direct_sources:
        return True, (
            "candidate_topology:audited_or_fdr_controlled",
            f"topology_source:{topology_source}",
        )

    if _truthy(
        _first_metadata_value(
            topology_metadata,
            metadata,
            keys=(
                "topology_fdr_controlled",
                "candidate_topology_fdr_controlled",
                "hyperedge_fdr_controlled",
            ),
        )
    ):
        return True, (
            "candidate_topology:audited_or_fdr_controlled",
            "topology_evidence:fdr_controlled",
        )

    if _truthy(
        _first_metadata_value(
            topology_metadata,
            metadata,
            keys=(
                "topology_posterior_threshold_passed",
                "candidate_topology_posterior_threshold_passed",
            ),
        )
    ):
        return True, (
            "candidate_topology:audited_or_fdr_controlled",
            "topology_evidence:posterior_threshold_passed",
        )

    posterior = _first_metadata_value(
        topology_metadata,
        metadata,
        keys=(
            "topology_posterior_inclusion",
            "hyperedge_posterior_inclusion",
            "posterior_inclusion",
        ),
    )
    posterior_threshold = _first_metadata_value(
        topology_metadata,
        metadata,
        keys=("topology_posterior_threshold", "posterior_inclusion_threshold"),
    )
    try:
        posterior_score = float(posterior)
        required_posterior = float(posterior_threshold)
    except (TypeError, ValueError):
        posterior_score = float("nan")
        required_posterior = float("nan")
    if (
        math.isfinite(posterior_score)
        and math.isfinite(required_posterior)
        and 0.0 < required_posterior <= posterior_score <= 1.0
    ):
        return True, (
            "candidate_topology:audited_or_fdr_controlled",
            "topology_evidence:posterior_threshold_passed",
        )

    if _truthy(
        _first_metadata_value(
            topology_metadata,
            metadata,
            keys=(
                "topology_stability_threshold_passed",
                "candidate_topology_stability_threshold_passed",
            ),
        )
    ):
        return True, (
            "candidate_topology:audited_or_fdr_controlled",
            "topology_evidence:stability_threshold_passed",
        )

    stability = _first_metadata_value(
        topology_metadata,
        metadata,
        keys=("topology_stability_score", "stability_score"),
    )
    stability_threshold = _first_metadata_value(
        topology_metadata,
        metadata,
        keys=("topology_stability_threshold", "stability_threshold"),
    )
    try:
        stability_score = float(stability)
        required_stability = float(stability_threshold)
    except (TypeError, ValueError):
        return False, ()
    if (
        math.isfinite(stability_score)
        and math.isfinite(required_stability)
        and 0.0 < required_stability <= stability_score <= 1.0
    ):
        return True, (
            "candidate_topology:audited_or_fdr_controlled",
            "topology_evidence:stability_threshold_passed",
        )
    return False, ()


def _selection_stage_assumption(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
) -> str | None:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    selection_stage = _normalized_metadata_token(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=("selection_stage", "mode_selection_stage", "fallback_selection_stage"),
        )
    )
    if selection_stage is None:
        return None
    if selection_stage in {
        "pre_outcome",
        "pre_treatment",
        "sample_split",
        "split_sample",
        "cross_fit",
        "cross_fitted",
    }:
        return f"selection_stage:{selection_stage}"
    return None


def _inference_regime_assumption(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
) -> str | None:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    regime = _normalized_metadata_token(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=("inference_regime", "variance_regime", "uncertainty_regime"),
        )
    )
    if regime is None:
        return None
    if regime in {
        "randomization_based",
        "conditional_randomization",
        "conditioning_mechanism",
        "ani",
        "local_dependence",
        "cluster_robust",
        "design_based",
    }:
        return f"inference_regime:{regime}"
    return None


def _canonical_faces(contract: InteractionComplex) -> frozenset[frozenset[str]]:
    faces: set[frozenset[str]] = {frozenset((node,)) for node in contract.nodes}
    materialized_simplices = _materialize_simplicial_closure(contract.simplices)
    for group in contract.hyperedges + materialized_simplices:
        faces.add(frozenset(group))
    return frozenset(face for face in faces if face)


def _missing_downward_faces(contract: InteractionComplex) -> tuple[tuple[str, ...], ...]:
    faces = _canonical_faces(contract)
    missing: set[tuple[str, ...]] = set()
    for face in faces:
        if len(face) <= 1:
            continue
        ordered = tuple(sorted(face))
        for size in range(1, len(ordered)):
            for subset in combinations(ordered, size):
                if frozenset(subset) not in faces:
                    missing.add(tuple(subset))
    return tuple(sorted(missing))


def _downward_closure_verified(contract: InteractionComplex) -> bool:
    return not _missing_downward_faces(contract)


def _maximal_faces(contract: InteractionComplex) -> tuple[frozenset[str], ...]:
    faces = _canonical_faces(contract)
    maximal = [
        face
        for face in faces
        if not any(face < candidate for candidate in faces)
    ]
    return tuple(sorted(maximal, key=lambda face: (len(face), tuple(sorted(face)))))


def _maximal_face_size(contract: InteractionComplex) -> int:
    return max((len(face) for face in _canonical_faces(contract)), default=0)


def _maximal_faces_partition_nodes(contract: InteractionComplex) -> bool:
    maximal = _maximal_faces(contract)
    seen: set[str] = set()
    for face in maximal:
        overlap = seen.intersection(face)
        if overlap:
            return False
        seen.update(face)
    return seen == set(contract.nodes)


def _operator_factorizes_through_within_facet_summary(
    operator_metadata: Mapping[str, Any],
) -> bool:
    if _truthy(operator_metadata.get("factorizes_through_within_facet_summary")):
        return True
    factorization = _first_metadata_value(
        operator_metadata,
        keys=("factorizes_through", "factorization", "summary_scope", "reduction_scope"),
    )
    if factorization is None:
        return False
    return str(factorization).strip().lower() in {
        "within_facet_summary",
        "within_simplex_summary",
        "within_cluster_summary",
        "cluster_summary",
        "facet_summary",
    }


def _closed_star_vertex_supports(contract: InteractionComplex) -> dict[str, set[str]]:
    supports: dict[str, set[str]] = {node: {node} for node in contract.nodes}
    for face in _canonical_faces(contract):
        for node in face:
            supports.setdefault(node, {node}).update(face)
    return supports


def _star_overlap_max_degree(contract: InteractionComplex) -> int:
    supports = _closed_star_vertex_supports(contract)
    max_degree = 0
    nodes = tuple(supports)
    for node in nodes:
        degree = sum(
            1
            for other in nodes
            if other != node and bool(supports[node].intersection(supports[other]))
        )
        max_degree = max(max_degree, degree)
    return max_degree


def _bounded_star_overlap_declared(
    augmented_graph: InterferenceAugmentedGraph,
    operator_metadata: Mapping[str, Any],
    contract: InteractionComplex,
) -> bool:
    metadata = augmented_graph.original_graph.metadata or {}
    topology_metadata = _topology_metadata(augmented_graph)
    if _truthy(
        _first_metadata_value(
            operator_metadata,
            topology_metadata,
            metadata,
            keys=("bounded_star_overlap", "bounded_star_overlap_verified"),
        )
    ):
        return True
    bound = _first_metadata_value(
        operator_metadata,
        topology_metadata,
        metadata,
        keys=("max_star_overlap_degree", "star_overlap_max_degree"),
    )
    try:
        return _star_overlap_max_degree(contract) <= int(bound)
    except (TypeError, ValueError):
        return False


def _simplicial_star_local_support_gate(
    augmented_graph: InterferenceAugmentedGraph,
    contract: InteractionComplex,
) -> _SimplicialSupportGate:
    operator_metadata = _exposure_operator_metadata(augmented_graph)
    assumptions: list[str] = []
    failures: list[str] = []

    if _downward_closure_verified(contract):
        assumptions.extend(("known_simplicial_complex", "downward_closure_verified"))
    else:
        failures.append("downward_closure_missing")

    locality_scope = str(operator_metadata.get("locality_scope", "")).strip().lower()
    if locality_scope == "closed_star" and _finite_codomain_declared(operator_metadata):
        assumptions.append("finite_star_local_exposure_mapping")
    else:
        failures.append("finite_star_local_exposure_mapping_missing")

    if _truthy(operator_metadata.get("exposure_consistency")):
        assumptions.append("exposure_consistency")
    else:
        failures.append("exposure_consistency_missing")

    if _randomized_assignment_declared(augmented_graph, operator_metadata):
        assumptions.append("randomized_assignment")
    else:
        failures.append("randomized_assignment_missing")

    if _design_positivity_declared(augmented_graph, operator_metadata):
        assumptions.append("design_positivity")
    else:
        failures.append("design_positivity_missing")

    if _bounded_star_overlap_declared(augmented_graph, operator_metadata, contract):
        assumptions.append("bounded_star_overlap")
    else:
        failures.append("bounded_star_overlap_missing")

    return _SimplicialSupportGate(
        supported=not failures,
        assumptions=tuple(assumptions),
        failures=tuple(failures),
    )


def _complex_estimability_checks(
    augmented_graph: InterferenceAugmentedGraph,
    interaction_complex: InteractionComplex | None,
) -> dict[str, Literal["pass", "fail", "not_applicable"]]:
    operator_metadata = _exposure_operator_metadata(augmented_graph)
    if interaction_complex is None:
        return {
            "topology_evidence": "fail",
            "simplicial_closure": "not_applicable",
            "exposure_positivity": (
                "pass" if _design_positivity_declared(augmented_graph, operator_metadata) else "fail"
            ),
            "higher_order_separability": "not_applicable",
            "inference_regime": (
                "pass" if _inference_regime_declared(augmented_graph, operator_metadata) else "fail"
            ),
            "pre_outcome_selection": (
                "pass"
                if _pre_outcome_selection_declared(augmented_graph, operator_metadata)
                else "fail"
            ),
        }

    has_higher_order = _maximal_face_size(interaction_complex) > 2
    topology_evidence_supported, _ = _topology_evidence_assumptions(
        augmented_graph,
        interaction_complex,
    )
    exact_cluster_projection = (
        has_higher_order
        and _maximal_faces_partition_nodes(interaction_complex)
        and _operator_factorizes_through_within_facet_summary(operator_metadata)
    )
    return {
        "topology_evidence": (
            "pass"
            if has_higher_order and topology_evidence_supported
            else ("fail" if has_higher_order else "not_applicable")
        ),
        "simplicial_closure": (
            "pass"
            if has_higher_order and _downward_closure_verified(interaction_complex)
            else ("fail" if has_higher_order else "not_applicable")
        ),
        "exposure_positivity": (
            "pass" if _design_positivity_declared(augmented_graph, operator_metadata) else "fail"
        ),
        "higher_order_separability": (
            "not_applicable"
            if not has_higher_order
            else (
                "fail"
                if exact_cluster_projection
                else (
                    "pass"
                    if _higher_order_separability_declared(augmented_graph, operator_metadata)
                    else "fail"
                )
            )
        ),
        "inference_regime": (
            "pass" if _inference_regime_declared(augmented_graph, operator_metadata) else "fail"
        ),
        "pre_outcome_selection": (
            "pass"
            if _pre_outcome_selection_declared(augmented_graph, operator_metadata)
            else "fail"
        ),
    }


def _complex_estimator_admissible(
    estimability_checks: Mapping[str, Literal["pass", "fail", "not_applicable"]],
) -> bool:
    required = (
        "topology_evidence",
        "simplicial_closure",
        "exposure_positivity",
        "higher_order_separability",
        "inference_regime",
        "pre_outcome_selection",
    )
    return all(estimability_checks.get(key) == "pass" for key in required)


def _coarsened_estimator_admissible(
    estimability_checks: Mapping[str, Literal["pass", "fail", "not_applicable"]],
) -> bool:
    required = (
        "exposure_positivity",
        "inference_regime",
        "pre_outcome_selection",
    )
    return all(estimability_checks.get(key) == "pass" for key in required)


def _cluster_fallback_available(augmented_graph: InterferenceAugmentedGraph) -> bool:
    return bool(augmented_graph.cluster_partition)


def _complex_fallback_reason_codes(
    *,
    interaction_complex: InteractionComplex | None,
    estimability_checks: Mapping[str, Literal["pass", "fail", "not_applicable"]],
    mode_used: Literal["pairwise", "clustered", "complex", "unsupported"],
    exact_pairwise_reduction: bool = False,
    exact_cluster_reduction: bool = False,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interaction_complex is None or estimability_checks.get("topology_evidence") == "fail":
        reasons.append("topology_not_estimable")
    if exact_pairwise_reduction:
        reasons.append("complex_reduces_exactly_to_pairwise")
    if exact_cluster_reduction:
        reasons.append("complex_reduces_exactly_to_clustered")
    if estimability_checks.get("simplicial_closure") == "fail":
        reasons.append("simplicial_closure_failed")
    if estimability_checks.get("exposure_positivity") == "fail":
        reasons.append("complex_exposure_support_too_low")
    if estimability_checks.get("higher_order_separability") == "fail":
        reasons.append("higher_order_separability_failed")
    if estimability_checks.get("inference_regime") == "fail":
        reasons.append("inference_regime_failed")
    if estimability_checks.get("pre_outcome_selection") == "fail":
        reasons.append("selection_not_pre_outcome")
    if mode_used == "unsupported":
        reasons.append("no_safe_fallback_available")

    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append(reason)
    return tuple(deduped)


def _interaction_complex_from_augmented_graph(
    augmented_graph: InterferenceAugmentedGraph,
    *,
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"],
) -> InteractionComplex | None:
    hyperedges = _metadata_topology_groups(augmented_graph, key="hyperedges")
    simplices = _materialize_simplicial_closure(
        _metadata_topology_groups(augmented_graph, key="simplices")
    )
    if not hyperedges and not simplices and augmented_graph.cluster_partition:
        hyperedges = tuple(tuple(group) for group in augmented_graph.cluster_partition)
    if not hyperedges and not simplices:
        return None
    return InteractionComplex(
        nodes=tuple(augmented_graph.original_graph.nodes),
        hyperedges=hyperedges,
        simplices=simplices,
        exposure_operator_ref=_exposure_operator_ref(augmented_graph),
        reduction_policy=reduction_policy,
    )


def _topology_exposure_assumptions(
    augmented_graph: InterferenceAugmentedGraph,
    *,
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"],
    result: InterferenceIdentificationResult | None,
) -> tuple[str, ...]:
    assumptions: list[str] = [
        f"exposure_mapping:{augmented_graph.exposure_mapping.value}",
        "hypergraph_identification_not_claimed",
        "support_limited_to_pairwise_or_cluster_reduction",
        f"reduction_policy:{reduction_policy}",
    ]
    if augmented_graph.cluster_partition:
        assumptions.append("cluster_partition_used_as_topology_proxy")
    if augmented_graph.cross_unit_edges:
        assumptions.append("cross_unit_edges_detected")
    if augmented_graph.exposure_nodes:
        assumptions.append("exposure_nodes_materialized")
    if result is not None and result.sutva_violated:
        assumptions.append("sutva_violation_detected")
    if result is not None and result.base_identification_status:
        assumptions.append(f"base_identification_status:{result.base_identification_status}")
    deduped: list[str] = []
    seen: set[str] = set()
    for assumption in assumptions:
        if assumption in seen:
            continue
        seen.add(assumption)
        deduped.append(assumption)
    return tuple(deduped)


def _dedupe_assumptions(assumptions: list[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()
    for assumption in assumptions:
        if assumption in seen:
            continue
        seen.add(assumption)
        deduped.append(assumption)
    return tuple(deduped)


def _canonical_triangle(value: object) -> tuple[str, str, str] | None:
    if isinstance(value, str):
        raw_nodes = [
            node.strip()
            for node in re.split(r"[|,;]", value)
            if node.strip()
        ]
    elif isinstance(value, (list, tuple, set, frozenset)):
        raw_nodes = [str(node).strip() for node in value if str(node).strip()]
    else:
        return None
    if len(raw_nodes) != 3 or len(set(raw_nodes)) != 3:
        return None
    return tuple(sorted(raw_nodes))


def _linear_2complex_triangles(
    contract: InteractionComplex,
) -> tuple[tuple[str, str, str], ...] | None:
    if any(len(hyperedge) > 2 for hyperedge in contract.hyperedges):
        return None
    if any(len(simplex) > 3 for simplex in contract.simplices):
        return None

    triangles = {
        canonical
        for simplex in contract.simplices
        if len(simplex) == 3 and (canonical := _canonical_triangle(simplex)) is not None
    }
    if not triangles:
        return None

    edge_to_triangle: dict[tuple[str, str], tuple[str, str, str]] = {}
    for triangle in triangles:
        for edge in combinations(triangle, 2):
            if edge in edge_to_triangle:
                return None
            edge_to_triangle[edge] = triangle
    return tuple(sorted(triangles))


def _bernoulli_iid_rate(bound_model: Mapping[str, Any]) -> float | None:
    design = bound_model.get("design")
    if not isinstance(design, Mapping):
        return None

    kind = str(design.get("kind", "")).strip().lower()
    if kind == "bernoulli":
        if not _truthy(design.get("iid")):
            return None
    elif kind != "bernoulli_iid":
        return None

    try:
        rate = float(design["p"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(rate) or rate <= 0.0 or rate >= 1.0:
        return None
    return rate


def _bound_model_uses_count_exposure(
    augmented_graph: InterferenceAugmentedGraph,
    bound_model: Mapping[str, Any],
) -> bool:
    if augmented_graph.exposure_mapping != ExposureMappingType.COUNT:
        return False
    declared_mapping = bound_model.get("exposure_mapping")
    if declared_mapping is None:
        return True
    return str(declared_mapping).strip().lower() == ExposureMappingType.COUNT.value


def _triangle_response_kind(bound_model: Mapping[str, Any]) -> Literal["linear", "lipschitz"] | None:
    candidate = str(bound_model.get("triangle_response", "")).strip().lower()
    if candidate in {"linear", "lipschitz"}:
        return candidate
    return None


def _triangle_weight_sums_by_node(
    bound_model: Mapping[str, Any],
    *,
    triangles: tuple[tuple[str, str, str], ...],
) -> dict[str, float] | None:
    payload = bound_model.get("triangle_weights")
    if payload is None:
        return None

    triangle_set = set(triangles)
    expected_nodes = {node for triangle in triangles for node in triangle}
    sums_by_node: dict[str, float] = {node: 0.0 for node in expected_nodes}
    seen_triangles: set[tuple[str, str, str]] = set()

    if isinstance(payload, Mapping):
        raw_entries = tuple(payload.items())
    elif isinstance(payload, (list, tuple)):
        raw_entries = tuple((entry, None) for entry in payload)
    else:
        return None

    for raw_key, raw_value in raw_entries:
        if raw_value is None:
            if not isinstance(raw_key, Mapping):
                return None
            simplex_value = raw_key.get("simplex", raw_key.get("triangle", raw_key.get("nodes")))
            weights_value = raw_key.get("weights", raw_key.get("gamma_by_target"))
        else:
            simplex_value = raw_key
            weights_value = raw_value

        triangle = _canonical_triangle(simplex_value)
        if triangle is None or triangle not in triangle_set or triangle in seen_triangles:
            return None
        if not isinstance(weights_value, Mapping):
            return None

        canonical_weights: dict[str, float] = {}
        for node in triangle:
            if node not in weights_value:
                return None
            try:
                weight = float(weights_value[node])
            except (TypeError, ValueError):
                return None
            if not math.isfinite(weight):
                return None
            canonical_weights[node] = abs(weight)

        extra_nodes = {str(node) for node in weights_value if str(node) not in triangle}
        if extra_nodes:
            return None

        for node, weight in canonical_weights.items():
            sums_by_node[node] += weight
        seen_triangles.add(triangle)

    if seen_triangles != triangle_set:
        return None
    return sums_by_node


def _lipschitz_constants_by_node(
    bound_model: Mapping[str, Any],
    *,
    relevant_nodes: set[str],
) -> dict[str, float] | None:
    payload = bound_model.get("lipschitz_by_node")
    if not isinstance(payload, Mapping):
        return None

    constants: dict[str, float] = {}
    for node in relevant_nodes:
        if node not in payload:
            return None
        try:
            constant = float(payload[node])
        except (TypeError, ValueError):
            return None
        if not math.isfinite(constant) or constant < 0.0:
            return None
        constants[node] = constant
    return constants


def _pairwise_projection_reduction_error_bound(
    augmented_graph: InterferenceAugmentedGraph,
    interaction_complex: InteractionComplex | None,
    *,
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"],
) -> _ReductionErrorBoundPlan:
    if reduction_policy != "pairwise_projection" or interaction_complex is None:
        return _ReductionErrorBoundPlan(reduction_error_bound=None)

    triangles = _linear_2complex_triangles(interaction_complex)
    if triangles is None:
        return _ReductionErrorBoundPlan(reduction_error_bound=None)

    bound_model = _bound_model_metadata(augmented_graph)
    if not bound_model or not _bound_model_uses_count_exposure(augmented_graph, bound_model):
        return _ReductionErrorBoundPlan(reduction_error_bound=None)

    design_p = _bernoulli_iid_rate(bound_model)
    if design_p is None:
        return _ReductionErrorBoundPlan(reduction_error_bound=None)

    triangle_response = _triangle_response_kind(bound_model)
    if triangle_response is None:
        return _ReductionErrorBoundPlan(reduction_error_bound=None)

    assumptions = (
        "bound_scope:bernoulli_mean_rate_contrasts_only",
        "design:bernoulli_iid",
        "linear_2complex_required",
        "triangle_projection:design_calibrated",
        f"triangle_response:{triangle_response}",
    )
    if triangle_response == "linear":
        return _ReductionErrorBoundPlan(reduction_error_bound=0.0, assumptions=assumptions)

    weight_sums_by_node = _triangle_weight_sums_by_node(bound_model, triangles=triangles)
    if weight_sums_by_node is None:
        return _ReductionErrorBoundPlan(reduction_error_bound=None)

    lipschitz_by_node = _lipschitz_constants_by_node(
        bound_model,
        relevant_nodes=set(weight_sums_by_node),
    )
    if lipschitz_by_node is None:
        return _ReductionErrorBoundPlan(reduction_error_bound=None)

    total_weight = sum(
        lipschitz_by_node[node] * weight_sums_by_node[node]
        for node in weight_sums_by_node
    )
    bound = (2.0 * design_p ** 2 * (1.0 - design_p) * total_weight) / len(interaction_complex.nodes)
    return _ReductionErrorBoundPlan(reduction_error_bound=bound, assumptions=assumptions)


def _full_complex_certificate_plan(
    augmented_graph: InterferenceAugmentedGraph,
    interaction_complex: InteractionComplex | None,
    *,
    result: InterferenceIdentificationResult | None,
) -> _TopologyCertificatePlan:
    mode_requested = _requested_interference_mode("full_complex")
    assumptions = [
        f"exposure_mapping:{augmented_graph.exposure_mapping.value}",
        "reduction_policy:full_complex",
    ]
    if augmented_graph.cross_unit_edges:
        assumptions.append("cross_unit_edges_detected")
    if augmented_graph.exposure_nodes:
        assumptions.append("exposure_nodes_materialized")
    if result is not None and result.sutva_violated:
        assumptions.append("sutva_violation_detected")
    if result is not None and result.base_identification_status:
        assumptions.append(f"base_identification_status:{result.base_identification_status}")

    operator_metadata = _exposure_operator_metadata(augmented_graph)
    _, topology_evidence_assumptions = _topology_evidence_assumptions(
        augmented_graph,
        interaction_complex,
    )
    assumptions.extend(topology_evidence_assumptions)
    selection_stage_assumption = _selection_stage_assumption(augmented_graph, operator_metadata)
    if selection_stage_assumption is not None:
        assumptions.append(selection_stage_assumption)
    inference_regime_assumption = _inference_regime_assumption(
        augmented_graph,
        operator_metadata,
    )
    if inference_regime_assumption is not None:
        assumptions.append(inference_regime_assumption)

    estimability_checks = _complex_estimability_checks(augmented_graph, interaction_complex)
    pairwise_admissible = _coarsened_estimator_admissible(estimability_checks)
    clustered_admissible = _cluster_fallback_available(augmented_graph) and pairwise_admissible
    if interaction_complex is None:
        assumptions.extend(
            (
                "hypergraph_identification_not_claimed",
                "simplicial_identification_gates_failed",
                "interaction_complex_missing",
                "support_limited_to_pairwise_or_cluster_reduction",
            )
        )
        mode_used: Literal["pairwise", "clustered", "complex", "unsupported"]
        if clustered_admissible:
            mode_used = "clustered"
        elif pairwise_admissible:
            mode_used = "pairwise"
        else:
            mode_used = "unsupported"
        return _TopologyCertificatePlan(
            supported_query_family=(
                _CLUSTER_QUERY_FAMILY
                if mode_used == "clustered"
                else (
                    _PAIRWISE_QUERY_FAMILY
                    if mode_used == "pairwise"
                    else _UNSUPPORTED_COMPLEX_QUERY_FAMILY
                )
            ),
            fallback_mode=(
                mode_used if mode_used in {"pairwise", "clustered"} else "unsupported"
            ),
            exposure_assumptions=_dedupe_assumptions(assumptions),
            reduction_error_bound=None,
            mode_requested=mode_requested,
            mode_used=mode_used,
            fallback_triggered=mode_used != "complex",
            fallback_reason_codes=_complex_fallback_reason_codes(
                interaction_complex=interaction_complex,
                estimability_checks=estimability_checks,
                mode_used=mode_used,
            ),
            estimability_checks=estimability_checks,
        )

    if _maximal_face_size(interaction_complex) <= 2:
        assumptions.extend(
            (
                "pairwise_reduction_exact",
                "hypergraph_identification_not_claimed",
                "support_limited_to_pairwise_or_cluster_reduction",
            )
        )
        mode_used: Literal["pairwise", "clustered", "complex", "unsupported"]
        if pairwise_admissible:
            fallback_mode: Literal["pairwise", "clustered", "unsupported"] = "pairwise"
            supported_query_family = _PAIRWISE_QUERY_FAMILY
            reduction_error_bound = 0.0
            mode_used = "pairwise"
        else:
            fallback_mode = "unsupported"
            supported_query_family = _UNSUPPORTED_COMPLEX_QUERY_FAMILY
            reduction_error_bound = None
            mode_used = "unsupported"
        return _TopologyCertificatePlan(
            supported_query_family=supported_query_family,
            fallback_mode=fallback_mode,
            exposure_assumptions=_dedupe_assumptions(assumptions),
            reduction_error_bound=reduction_error_bound,
            mode_requested=mode_requested,
            mode_used=mode_used,
            fallback_triggered=True,
            fallback_reason_codes=_complex_fallback_reason_codes(
                interaction_complex=interaction_complex,
                estimability_checks=estimability_checks,
                mode_used=mode_used,
                exact_pairwise_reduction=True,
            ),
            estimability_checks=estimability_checks,
        )

    if (
        _maximal_faces_partition_nodes(interaction_complex)
        and _operator_factorizes_through_within_facet_summary(operator_metadata)
    ):
        assumptions.extend(
            (
                "cluster_reduction_exact",
                "hypergraph_identification_not_claimed",
                "support_limited_to_pairwise_or_cluster_reduction",
            )
        )
        mode_used: Literal["pairwise", "clustered", "complex", "unsupported"]
        fallback_mode: Literal["pairwise", "clustered", "unsupported"]
        supported_query_family: str
        reduction_error_bound: float | None
        exact_cluster_admissible = pairwise_admissible and (
            _cluster_fallback_available(augmented_graph)
            or _maximal_faces_partition_nodes(interaction_complex)
        )
        if exact_cluster_admissible:
            fallback_mode = "clustered"
            supported_query_family = _CLUSTER_QUERY_FAMILY
            reduction_error_bound = 0.0
            mode_used = "clustered"
        elif pairwise_admissible:
            fallback_mode = "pairwise"
            supported_query_family = _PAIRWISE_QUERY_FAMILY
            reduction_error_bound = None
            mode_used = "pairwise"
        else:
            fallback_mode = "unsupported"
            supported_query_family = _UNSUPPORTED_COMPLEX_QUERY_FAMILY
            reduction_error_bound = None
            mode_used = "unsupported"
        return _TopologyCertificatePlan(
            supported_query_family=supported_query_family,
            fallback_mode=fallback_mode,
            exposure_assumptions=_dedupe_assumptions(assumptions),
            reduction_error_bound=reduction_error_bound,
            mode_requested=mode_requested,
            mode_used=mode_used,
            fallback_triggered=True,
            fallback_reason_codes=_complex_fallback_reason_codes(
                interaction_complex=interaction_complex,
                estimability_checks=estimability_checks,
                mode_used=mode_used,
                exact_cluster_reduction=True,
            ),
            estimability_checks=estimability_checks,
        )

    gate = _simplicial_star_local_support_gate(augmented_graph, interaction_complex)
    if gate.supported and _complex_estimator_admissible(estimability_checks):
        assumptions.extend(gate.assumptions)
        return _TopologyCertificatePlan(
            supported_query_family=_SIMPLICIAL_STAR_LOCAL_QUERY_FAMILY,
            fallback_mode="unsupported",
            exposure_assumptions=_dedupe_assumptions(assumptions),
            reduction_error_bound=None,
            mode_requested=mode_requested,
            mode_used="complex",
            fallback_triggered=False,
            fallback_reason_codes=(),
            estimability_checks=estimability_checks,
        )
    if gate.supported:
        assumptions.extend(gate.assumptions)

    assumptions.extend(
        (
            "hypergraph_identification_not_claimed",
            "simplicial_identification_gates_failed",
            "support_limited_to_pairwise_or_cluster_reduction",
        )
    )
    assumptions.extend(gate.failures)
    fallback_mode: Literal["pairwise", "clustered", "unsupported"]
    if clustered_admissible:
        fallback_mode = "clustered"
        supported_query_family = _CLUSTER_QUERY_FAMILY
        reduction_error_bound = None
        mode_used = "clustered"
    elif pairwise_admissible:
        fallback_mode = "pairwise"
        supported_query_family = _PAIRWISE_QUERY_FAMILY
        reduction_bound_plan = _pairwise_projection_reduction_error_bound(
            augmented_graph,
            interaction_complex,
            reduction_policy="pairwise_projection",
        )
        reduction_error_bound = reduction_bound_plan.reduction_error_bound
        assumptions.extend(reduction_bound_plan.assumptions)
        mode_used = "pairwise"
    else:
        fallback_mode = "unsupported"
        supported_query_family = _UNSUPPORTED_COMPLEX_QUERY_FAMILY
        reduction_error_bound = None
        mode_used = "unsupported"
    return _TopologyCertificatePlan(
        supported_query_family=supported_query_family,
        fallback_mode=fallback_mode,
        exposure_assumptions=_dedupe_assumptions(assumptions),
        reduction_error_bound=reduction_error_bound,
        mode_requested=mode_requested,
        mode_used=mode_used,
        fallback_triggered=True,
        fallback_reason_codes=_complex_fallback_reason_codes(
            interaction_complex=interaction_complex,
            estimability_checks=estimability_checks,
            mode_used=mode_used,
        ),
        estimability_checks=estimability_checks,
    )


def _topology_certificate_plan(
    augmented_graph: InterferenceAugmentedGraph,
    interaction_complex: InteractionComplex | None,
    *,
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"],
    result: InterferenceIdentificationResult | None,
) -> _TopologyCertificatePlan:
    if reduction_policy == "full_complex":
        return _full_complex_certificate_plan(
            augmented_graph,
            interaction_complex,
            result=result,
        )

    mode_requested = _requested_interference_mode(reduction_policy)
    fallback_mode = _topology_fallback_mode(reduction_policy)
    reduction_bound_plan = _pairwise_projection_reduction_error_bound(
        augmented_graph,
        interaction_complex,
        reduction_policy=reduction_policy,
    )
    exposure_assumptions = list(
        _topology_exposure_assumptions(
            augmented_graph,
            reduction_policy=reduction_policy,
            result=result,
        )
    )
    exposure_assumptions.extend(reduction_bound_plan.assumptions)
    return _TopologyCertificatePlan(
        supported_query_family=_supported_query_family(
            augmented_graph,
            reduction_policy=reduction_policy,
            fallback_mode=fallback_mode,
        ),
        fallback_mode=fallback_mode,
        exposure_assumptions=_dedupe_assumptions(exposure_assumptions),
        reduction_error_bound=reduction_bound_plan.reduction_error_bound,
        mode_requested=mode_requested,
        mode_used=fallback_mode,
        fallback_triggered=False,
        fallback_reason_codes=(),
        estimability_checks={},
    )


def build_interference_topology_contracts(
    payload: InterferenceAugmentedGraph | InterferenceIdentificationResult | Mapping[str, Any],
    *,
    reduction_policy: Literal[
        "pairwise_projection",
        "cluster_projection",
        "full_complex",
    ] | None = None,
) -> tuple[InteractionComplex | None, InterferenceCertificate]:
    """Adapt current interference artifacts into the Phase F.1 topology surface."""
    augmented_graph, result = _coerce_topology_contract_source(payload)
    resolved_policy = _resolved_topology_reduction_policy(augmented_graph, reduction_policy)
    interaction_complex = _interaction_complex_from_augmented_graph(
        augmented_graph,
        reduction_policy=resolved_policy,
    )
    certificate_plan = _topology_certificate_plan(
        augmented_graph,
        interaction_complex,
        reduction_policy=resolved_policy,
        result=result,
    )
    certificate = InterferenceCertificate(
        supported_query_family=certificate_plan.supported_query_family,
        exposure_assumptions=certificate_plan.exposure_assumptions,
        reduction_error_bound=certificate_plan.reduction_error_bound,
        fallback_mode=certificate_plan.fallback_mode,
        mode_requested=certificate_plan.mode_requested,
        mode_used=certificate_plan.mode_used,
        fallback_triggered=certificate_plan.fallback_triggered,
        fallback_reason_codes=certificate_plan.fallback_reason_codes,
        estimability_checks=certificate_plan.estimability_checks,
    )
    return interaction_complex, certificate


def _build_interference_augmented_graph(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    exposure_mapping: ExposureMappingType,
    cluster_var: str | None = None,
) -> tuple[InterferenceAugmentedGraph, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Construct an exposure-augmented graph and return metadata plus resolved nodes."""
    cluster_partition, node_to_cluster = _resolve_cluster_partition(graph, cluster_var=cluster_var)
    treatment_nodes = _resolve_graph_variables(graph, treatment)
    outcome_nodes = _resolve_graph_variables(graph, outcome)

    if not cluster_partition:
        # No explicit unit partition available. Preserve the original graph and
        # record an empty augmentation.
        augmented_graph = CausalGraphModel(
            schema_version=graph.schema_version,
            graph_type=GraphType.ADMG,
            nodes=list(graph.nodes),
            edges=list(graph.edges),
            discovery_method=graph.discovery_method,
            skg_version_id=graph.skg_version_id,
            pag_identification_policy=graph.pag_identification_policy,
            id_confidence_under_pag=graph.id_confidence_under_pag,
            metadata=dict(graph.metadata),
        )
        return (
            InterferenceAugmentedGraph(
                original_graph=graph,
                augmented_graph=augmented_graph,
                exposure_nodes=(),
                cluster_partition=(),
                interference_type="none",
                exposure_mapping=exposure_mapping,
                cross_unit_edges=(),
                node_to_cluster={},
                cluster_var=cluster_var,
            ),
            treatment_nodes,
            outcome_nodes,
            (),
        )

    # Build cluster membership from the resolved partition.
    cluster_lookup: dict[str, str] = {}
    for cluster_idx, members in enumerate(cluster_partition):
        for node in members:
            cluster_lookup[node] = str(cluster_idx)

    if not node_to_cluster:
        node_to_cluster = dict(cluster_lookup)

    cross_unit = _cross_unit_edges(graph, node_to_cluster)

    exposure_nodes: list[str] = []
    augmented_metadata = dict(graph.metadata)
    augmented_metadata["interference"] = {
        "exposure_nodes": exposure_nodes,
        "cluster_partition_size": len(cluster_partition),
        "treatment_nodes": list(treatment_nodes),
        "outcome_nodes": list(outcome_nodes),
        "cross_unit_edges": [list(edge) for edge in cross_unit],
    }

    if cross_unit:
        augmented_nodes = list(graph.nodes)
        augmented_edges = list(graph.edges)
        node_set = set(graph.nodes)

        for cluster_idx, members in enumerate(cluster_partition):
            cluster_name = f"u{cluster_idx}"
            cluster_members = set(members)
            target_treatment_nodes = [
                node for node in treatment_nodes if node not in cluster_members
            ]
            target_outcome_nodes = [
                node for node in outcome_nodes if node in cluster_members
            ]

            if not target_outcome_nodes:
                continue
            exposure_node = f"E__{cluster_name}"
            if exposure_node in node_set:
                exposure_node = f"E__{cluster_name}_spillover"
            exposure_nodes.append(exposure_node)
            augmented_nodes.append(exposure_node)
            if not target_treatment_nodes and treatment_nodes:
                target_treatment_nodes = list(treatment_nodes)

            for src in target_treatment_nodes:
                augmented_edges.append(
                    CausalEdge(
                        src=src,
                        dst=exposure_node,
                        mark_src=EdgeMark.TAIL,
                        mark_dst=EdgeMark.ARROW,
                    )
                )
            for dst in target_outcome_nodes:
                augmented_edges.append(
                    CausalEdge(
                        src=exposure_node,
                        dst=dst,
                        mark_src=EdgeMark.TAIL,
                        mark_dst=EdgeMark.ARROW,
                    )
                )

        augmented_graph = CausalGraphModel(
            schema_version=graph.schema_version,
            graph_type=GraphType.ADMG,
            nodes=augmented_nodes,
            edges=augmented_edges,
            discovery_method=graph.discovery_method,
            skg_version_id=graph.skg_version_id,
            pag_identification_policy=graph.pag_identification_policy,
            id_confidence_under_pag=graph.id_confidence_under_pag,
            metadata=augmented_metadata,
        )
    else:
        augmented_graph = CausalGraphModel(
            schema_version=graph.schema_version,
            graph_type=GraphType.ADMG,
            nodes=list(graph.nodes),
            edges=list(graph.edges),
            discovery_method=graph.discovery_method,
            skg_version_id=graph.skg_version_id,
            pag_identification_policy=graph.pag_identification_policy,
            id_confidence_under_pag=graph.id_confidence_under_pag,
            metadata=augmented_metadata,
        )
    return (
        InterferenceAugmentedGraph(
            original_graph=graph,
            augmented_graph=augmented_graph,
            exposure_nodes=tuple(exposure_nodes),
            cluster_partition=cluster_partition,
            interference_type=(
                "partial" if cluster_var is not None and cross_unit else ("network" if cross_unit else "none")
            ),
            exposure_mapping=exposure_mapping,
            cross_unit_edges=cross_unit,
            node_to_cluster=dict(node_to_cluster),
            cluster_var=cluster_var,
        ),
        treatment_nodes,
        outcome_nodes,
        cross_unit,
    )


def _convert_id_proof_steps(steps: list[Any]) -> tuple[IRProofStep, ...]:
    """Convert internal ID proof steps into public IR proof steps."""
    converted: list[IRProofStep] = []
    for step in steps:
        variables = tuple(sorted(set(step.antecedent_vars) | set(step.consequent_vars)))
        converted.append(
            IRProofStep(
                rule_name=step.rule_name,
                description=step.applied_to_graph_state,
                variables_affected=variables,
                graph_subset=step.applied_to_graph_state,
                rule_formal_name=step.rule_name,
                applicable_theorem="id-algorithm",
                graph_state_before=step.graph_state_before,
                graph_state_after=step.applied_to_graph_state,
            )
        )
    return tuple(converted)


def identify_interference_effect(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    *,
    exposure_mapping: ExposureMappingType = ExposureMappingType.FRACTIONAL,
    cluster_var: str | None = None,
) -> InterferenceIdentificationResult:
    """Run a graph-based SUTVA check and identify the effect on an augmented graph."""
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        id_algorithm,
    )

    trace: list[str] = []
    proof_steps: list[IRProofStep] = []

    augmented_graph, treatment_nodes, outcome_nodes, cross_unit = _build_interference_augmented_graph(
        graph,
        treatment=treatment,
        outcome=outcome,
        exposure_mapping=exposure_mapping,
        cluster_var=cluster_var,
    )

    sutva_violated = bool(cross_unit)
    interference_detected = sutva_violated or bool(augmented_graph.exposure_nodes)
    trace.append(
        "[interference] SUTVA check: "
        f"{'violated' if sutva_violated else 'no violation'}; "
        f"cross_unit_edges={len(cross_unit)}"
    )
    proof_steps.append(
        IRProofStep(
            rule_name="SUTVA_CHECK",
            description=(
                f"Detected {len(cross_unit)} cross-unit edge(s) in the original graph."
            ),
            variables_affected=tuple(sorted({treatment, outcome})),
            graph_subset="original graph",
            rule_formal_name="graph-based SUTVA check",
            applicable_theorem="phase-10-interference",
            graph_state_before=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges",
            graph_state_after=(
                "interference detected" if sutva_violated else "no interference detected"
            ),
        )
    )

    if augmented_graph.exposure_nodes:
        trace.append(
            "[interference] Exposure augmentation: "
            f"added {len(augmented_graph.exposure_nodes)} exposure node(s)"
        )
        proof_steps.append(
            IRProofStep(
                rule_name="EXPOSURE_AUGMENTATION",
                description=(
                    f"Added {len(augmented_graph.exposure_nodes)} exposure node(s) "
                    f"for spillover routing."
                ),
                variables_affected=tuple(sorted({treatment, outcome})),
                graph_subset="augmented graph",
                rule_formal_name="exposure-node augmentation",
                applicable_theorem="phase-10-interference",
                graph_state_before=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges",
                graph_state_after=(
                    f"{len(augmented_graph.augmented_graph.nodes)} nodes / "
                    f"{len(augmented_graph.augmented_graph.edges)} edges"
                ),
            )
        )
    else:
        trace.append("[interference] No exposure nodes were needed; using original graph.")
        proof_steps.append(
            IRProofStep(
                rule_name="NO_INTERFERENCE",
                description="No cross-unit interference detected; original graph is sufficient.",
                variables_affected=tuple(sorted({treatment, outcome})),
                graph_subset="original graph",
                rule_formal_name="no-interference gate",
                applicable_theorem="phase-10-interference",
                graph_state_before=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges",
                graph_state_after="original graph retained",
            )
        )

    resolved_treatment = treatment_nodes or _resolve_graph_variables(graph, treatment)
    resolved_outcome = outcome_nodes or _resolve_graph_variables(graph, outcome)
    if not resolved_treatment or not resolved_outcome:
        trace.append("[interference] input invalid: could not resolve treatment/outcome nodes")
        return InterferenceIdentificationResult(
            treatment=treatment,
            outcome=outcome,
            status="input_invalid",
            interference_detected=interference_detected,
            sutva_violated=sutva_violated,
            augmented_graph=augmented_graph,
            proof_steps=tuple(proof_steps),
            trace=tuple(trace),
            warnings=("Could not resolve treatment/outcome nodes in the graph.",),
        )

    dataset_ref = None
    metadata = graph.metadata or {}
    if isinstance(metadata.get("dataset_ref"), str):
        dataset_ref = str(metadata["dataset_ref"])

    base_trace: list[str] = []
    base_result = id_algorithm(
        treatment=frozenset(resolved_treatment),
        outcome=frozenset(resolved_outcome),
        graph=augmented_graph.augmented_graph if augmented_graph.exposure_nodes else graph,
        dataset_ref=dataset_ref,
        _trace=base_trace,
    )
    trace.extend(base_trace)
    trace.append(f"[interference] base ID status={base_result.status.value}")

    proof_steps.extend(_convert_id_proof_steps(list(base_result.proof_steps)))
    status = "identified" if base_result.status is IdentificationStatus.IDENTIFIED else "non_identified"
    negative_certificate = None
    estimand_ast = None
    if base_result.estimand_ast is not None:
        estimand_ast = base_result.estimand_ast.model_dump(mode="json")
    if base_result.status is not IdentificationStatus.IDENTIFIED:
        negative_certificate = {
            "status": base_result.status.value,
            "trace": list(base_trace),
            "required_distributions": [
                dist.model_dump(mode="json") for dist in base_result.required_distributions
            ],
        }

    return InterferenceIdentificationResult(
        treatment=treatment,
        outcome=outcome,
        status=status,
        interference_detected=interference_detected,
        sutva_violated=sutva_violated,
        augmented_graph=augmented_graph,
        proof_steps=tuple(proof_steps),
        trace=tuple(trace),
        base_identification_status=base_result.status.value,
        estimand_ast=estimand_ast,
        required_distributions=tuple(
            dist.model_dump(mode="json") for dist in base_result.required_distributions
        ),
        negative_certificate=negative_certificate,
    )


def _fractional_exposure(treatment: np.ndarray, cluster_id: np.ndarray) -> np.ndarray:
    """Per-unit fraction of *other* cluster members who are treated.

    Hudgens & Halloran (2008) Eq. (1).
    Returns shape ``(n_units,)`` float in [0, 1].
    """
    clusters = np.unique(cluster_id)
    exposure = np.zeros(len(treatment), dtype=float)
    for c in clusters:
        mask = cluster_id == c
        indices = np.where(mask)[0]
        n_c = int(mask.sum())
        if n_c < 2:
            continue
        for pos, idx in enumerate(indices):
            total_others = float(treatment[mask].sum()) - float(treatment[idx])
            exposure[idx] = total_others / (n_c - 1)
    return exposure


def _threshold_exposure(
    treatment: np.ndarray,
    cluster_id: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Binary indicator: 1 if fractional exposure exceeds *threshold*."""
    return (_fractional_exposure(treatment, cluster_id) > threshold).astype(float)


def _network_exposure(
    treatment: np.ndarray,
    adjacency: np.ndarray,
    mapping_type: str = "fraction",
) -> np.ndarray:
    """Aronow & Samii (2017) exposure mapping via adjacency matrix.

    Parameters
    ----------
    mapping_type:
        ``"fraction"`` — mean neighbour treatment;
        ``"count"`` — number of treated neighbours;
        ``"any"`` — 1 if any neighbour is treated.
    """
    neighbor_sum = adjacency @ treatment.astype(float)
    degree = adjacency.sum(axis=1)
    if mapping_type == "fraction":
        with np.errstate(invalid="ignore", divide="ignore"):
            exp = np.where(degree > 0, neighbor_sum / degree, 0.0)
    elif mapping_type == "count":
        exp = neighbor_sum
    else:  # "any"
        exp = (neighbor_sum > 0).astype(float)
    return exp.astype(float)


def _kernel_weights(coordinates: np.ndarray, bandwidth: float) -> np.ndarray:
    """Gaussian kernel weight matrix; diagonal set to zero (no self-influence).

    W_ij = exp(−‖x_i − x_j‖² / (2h²)).
    """
    diff = coordinates[:, np.newaxis, :] - coordinates[np.newaxis, :, :]  # (n, n, d)
    sq_dist = (diff ** 2).sum(axis=-1)  # (n, n)
    W = np.exp(-sq_dist / (2.0 * bandwidth ** 2))
    np.fill_diagonal(W, 0.0)
    return W


def _auto_bandwidth(coordinates: np.ndarray) -> float:
    """Silverman rule-of-thumb bandwidth for spatial kernel."""
    n = len(coordinates)
    # Mean pairwise distance variance proxy
    sigma = float(np.std(coordinates))
    return max(sigma * (n ** (-0.2)), 1e-6)


def _logistic_propensity(
    treatment: np.ndarray,
    features: np.ndarray,
    C: float = 1.0,
) -> np.ndarray:
    """Fit logistic regression and return P(A=1|features) for each unit."""
    from sklearn.linear_model import LogisticRegression  # lazy import

    lr = LogisticRegression(max_iter=2000, solver="lbfgs", C=C)
    lr.fit(features, treatment.astype(int))
    return lr.predict_proba(features)[:, 1].astype(float)


def _sandwich_var(scores: np.ndarray) -> float:
    """Robust sandwich variance of the sample mean: Var(ȳ) = E[ψ²]/n."""
    n = len(scores)
    if n < 2:
        return float("nan")
    return float(np.mean(scores ** 2) - np.mean(scores) ** 2) / n


def _normal_ci(estimate: float, se: float, level: float = 0.95) -> tuple[float, float]:
    """Gaussian confidence interval."""
    z = _normal_quantile(1.0 - (1.0 - level) / 2.0)
    return float(estimate - z * se), float(estimate + z * se)


def _normal_quantile(p: float) -> float:
    """Rational approximation to the normal quantile (Beasley & Springer 1977)."""
    import math as _math

    if p <= 0.0 or p >= 1.0:
        return float("nan")
    if abs(p - 0.5) < 1e-9:
        return 0.0
    sign = 1.0 if p > 0.5 else -1.0
    q = min(p, 1.0 - p)
    r = _math.sqrt(-2.0 * _math.log(q))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    numer = c0 + c1 * r + c2 * r * r
    denom = 1.0 + d1 * r + d2 * r * r + d3 * r * r * r
    return sign * (r - numer / denom)


def _ipw_potential_outcome(
    outcome: np.ndarray,
    indicator: np.ndarray,
    propensity: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Horvitz-Thompson IPW mean of E[Y(a)] under indicator/propensity.

    Returns ``(estimate, influence_scores)`` where influence scores can be
    used for sandwich variance estimation.
    """
    ps_clipped = np.clip(propensity, 1e-6, 1.0 - 1e-6)
    scores = outcome * indicator / ps_clipped
    estimate = float(np.mean(scores))
    return estimate, scores


def _build_report_failure(
    method: InterferenceMethod,
    exposure_mapping: ExposureMappingType,
    n_units: int,
    n_treated: int,
    reason: str,
    status: str = "input_invalid",
) -> NetworkInterferenceReport:
    return NetworkInterferenceReport(
        method=method,
        status=status,  # type: ignore[arg-type]
        status_reason=reason,
        exposure_mapping=exposure_mapping,
        n_units=n_units,
        n_treated=n_treated,
        warnings=[reason],
    )


def _build_report_success(
    method: InterferenceMethod,
    exposure_mapping: ExposureMappingType,
    de: float,
    se_val: float,
    te: float,
    se_de: float,
    se_se: float,
    se_te: float,
    n_units: int,
    n_treated: int,
    confidence_level: float,
    n_clusters: int | None = None,
    avg_cluster_size: float | None = None,
    alpha_high: float = 0.5,
    alpha_low: float = 0.0,
    exposure_params: dict[str, Any] | None = None,
    assumptions: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> NetworkInterferenceReport:
    ci_de = _normal_ci(de, se_de, confidence_level) if math.isfinite(se_de) and se_de > 0 else None
    ci_se = _normal_ci(se_val, se_se, confidence_level) if math.isfinite(se_se) and se_se > 0 else None
    ci_te = _normal_ci(te, se_te, confidence_level) if math.isfinite(se_te) and se_te > 0 else None

    # Interference detected: spillover SE different from 0 at 5%
    interference_detected = False
    if ci_se is not None and not (ci_se[0] <= 0.0 <= ci_se[1]):
        interference_detected = True
    elif math.isfinite(se_se) and se_se > 0:
        z = abs(se_val) / se_se
        interference_detected = z > 1.96

    effects = InterferenceEffectDecomposition(
        direct_effect=de,
        spillover_effect=se_val,
        total_effect=te,
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        se_direct=se_de if math.isfinite(se_de) else None,
        se_spillover=se_se if math.isfinite(se_se) else None,
        se_total=se_te if math.isfinite(se_te) else None,
        ci_direct=ci_de,
        ci_spillover=ci_se,
        ci_total=ci_te,
        n_units=n_units,
        n_treated=n_treated,
        confidence_level=confidence_level,
        interference_detected=interference_detected,
    )
    return NetworkInterferenceReport(
        method=method,
        status="success",
        effects=effects,
        exposure_mapping=exposure_mapping,
        exposure_mapping_params=exposure_params or {},
        n_units=n_units,
        n_treated=n_treated,
        n_clusters=n_clusters,
        average_cluster_size=avg_cluster_size,
        assumptions=assumptions or {},
        warnings=warnings or [],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Core algorithm implementations
# ──────────────────────────────────────────────────────────────────────────────

def _run_partial_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Hudgens & Halloran (2008) partial interference IPW."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    alpha_bw = float(params.get("alpha_bandwidth", 0.1))
    exposure_map = str(params.get("exposure_mapping", "fractional"))
    threshold = float(params.get("threshold", 0.5))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.cluster_id is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                ExposureMappingType.FRACTIONAL,
                n,
                n_treated,
                "cluster_id is required for PartialInterferenceEstimator",
            )
        }

    C = data.cluster_id
    clusters = np.unique(C)
    n_clusters = int(len(clusters))
    avg_cluster_size = float(n / n_clusters)

    # Compute exposure
    if exposure_map == "threshold":
        f = _threshold_exposure(A, C, threshold)
        exp_type = ExposureMappingType.THRESHOLD
    else:
        f = _fractional_exposure(A, C)
        exp_type = ExposureMappingType.FRACTIONAL

    # Build propensity features
    if data.covariates is not None:
        ps_features = np.column_stack([data.covariates, f])
    else:
        ps_features = f.reshape(-1, 1)

    try:
        ps = _logistic_propensity(A, ps_features)
    except Exception as exc:
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                exp_type,
                n,
                n_treated,
                f"propensity model failed: {exc}",
                status="numerical_failure",
            )
        }

    # Stratum masks: (treatment==a) & exposure near alpha
    def _potential_outcome_stratum(a_val: float, alpha: float) -> tuple[float, np.ndarray]:
        in_stratum = (A == a_val) & (np.abs(f - alpha) <= alpha_bw)
        if in_stratum.sum() < 2:
            return float("nan"), np.full(n, float("nan"))
        ps_a = ps if a_val == 1.0 else (1.0 - ps)
        # P(A=a, |f - alpha| <= alpha_bw) ≈ P(A=a) * P(|f-alpha|<=bw | A=a)
        # Use unit-level IPW within stratum
        est, scores = _ipw_potential_outcome(Y, in_stratum.astype(float), ps_a)
        # Normalise so it's an estimate of E[Y(a, alpha)], not a sum
        return est, scores

    mu11, sc11 = _potential_outcome_stratum(1.0, alpha_high)
    mu10, sc10 = _potential_outcome_stratum(0.0, alpha_high)
    mu01, sc01 = _potential_outcome_stratum(0.0, alpha_low)

    warnings: list[str] = []
    if any(math.isnan(x) for x in (mu11, mu10, mu01)):
        warnings.append(
            "Some alpha-strata have fewer than 2 observations; "
            "estimates may be unreliable."
        )

    # Fallback: simple cluster-level means when strata are sparse
    def _fallback_mean(a_val: float) -> float:
        mask = A == a_val
        return float(Y[mask].mean()) if mask.sum() > 0 else float("nan")

    if math.isnan(mu11):
        mu11 = _fallback_mean(1.0)
    if math.isnan(mu10):
        mu10 = _fallback_mean(0.0)
    if math.isnan(mu01):
        mu01 = _fallback_mean(0.0)

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    # Cluster-level sandwich variance
    def _cluster_var(scores: np.ndarray) -> float:
        """Mean cluster-level variance."""
        if np.any(np.isnan(scores)):
            return float("nan")
        cluster_means = np.array(
            [scores[C == c].mean() for c in clusters], dtype=float
        )
        return float(np.var(cluster_means, ddof=1) / n_clusters)

    var_de = _cluster_var(sc11 - sc10) if not np.any(np.isnan(sc11 + sc10)) else float("nan")
    var_se = _cluster_var(sc10 - sc01) if not np.any(np.isnan(sc10 + sc01)) else float("nan")
    var_te = _cluster_var(sc11 - sc01) if not np.any(np.isnan(sc11 + sc01)) else float("nan")

    se_de = math.sqrt(max(var_de, 0.0)) if math.isfinite(var_de) else float("nan")
    se_se = math.sqrt(max(var_se, 0.0)) if math.isfinite(var_se) else float("nan")
    se_te = math.sqrt(max(var_te, 0.0)) if math.isfinite(var_te) else float("nan")

    if any(not math.isfinite(x) for x in (de, se_val, te)):
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                exp_type,
                n,
                n_treated,
                "Could not estimate one or more potential outcomes; "
                "check treatment variation and alpha bandwidth.",
                status="numerical_failure",
            )
        }

    assumptions = {
        "partial_interference": "Units in different clusters do not interfere.",
        "stratified_interference": "Within a cluster, potential outcome depends on own "
        "treatment and aggregate cluster allocation only.",
        "positivity": "Each unit has positive probability of treatment and each "
        "exposure level under both treatment arms.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.PARTIAL_IPW,
            exposure_mapping=exp_type,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            n_clusters=n_clusters,
            avg_cluster_size=avg_cluster_size,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "exposure_mapping": exposure_map,
                "alpha_bandwidth": alpha_bw,
                "threshold": threshold,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_network_aipw(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Aronow & Samii (2017) network AIPW with general exposure mapping."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    n_bootstrap = int(params.get("n_bootstrap", 200))
    mapping_type = str(params.get("exposure_mapping", "fraction"))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.adjacency_matrix is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.NETWORK_AIPW,
                ExposureMappingType.FRACTIONAL,
                n,
                n_treated,
                "adjacency_matrix is required for NetworkAIPWEstimator",
            )
        }

    W = data.adjacency_matrix.astype(float)
    e = _network_exposure(A, W, mapping_type)

    # Binary indicator: high exposure (e > alpha_high) vs low
    e_high = (e >= alpha_high).astype(float)
    e_low = (e <= alpha_low).astype(float)

    # Build features: [A, e, X] for propensity models
    base_features = np.column_stack([A, e])
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _aipw_for_stratum(
        a_val: float,
        e_indicator: np.ndarray,
    ) -> tuple[float, float]:
        """AIPW estimator for E[Y(a, e_type)] where e_type is high/low."""
        stratum = (A == a_val) & (e_indicator > 0)
        if stratum.sum() < 3:
            return float("nan"), float("nan")

        # Outcome model E[Y | X, A=a, e_type]
        try:
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X_s = scaler.fit_transform(base_features[stratum])
            y_s = Y[stratum]
            ridge = Ridge(alpha=1.0)
            ridge.fit(X_s, y_s)
            mu_hat = ridge.predict(scaler.transform(base_features))
        except Exception:
            mu_hat = np.full(n, float(Y[stratum].mean()))

        # Propensity P(in stratum | X)
        try:
            ps = _logistic_propensity(stratum.astype(int), base_features)
        except Exception:
            ps = np.full(n, float(stratum.mean()) + 1e-6)

        ps_clipped = np.clip(ps, 1e-4, 1 - 1e-4)
        # AIPW scores: IPW + augmentation
        aipw_scores = (
            stratum.astype(float) * Y / ps_clipped
            - (stratum.astype(float) / ps_clipped - 1.0) * mu_hat
        )
        est = float(np.mean(aipw_scores))
        se = math.sqrt(max(_sandwich_var(aipw_scores - est), 0.0))
        return est, se

    mu11, se11 = _aipw_for_stratum(1.0, e_high)
    mu10, se10 = _aipw_for_stratum(0.0, e_high)
    mu01, se01 = _aipw_for_stratum(0.0, e_low)

    warnings: list[str] = []
    if any(math.isnan(x) for x in (mu11, mu10, mu01)):
        warnings.append(
            "Some exposure strata have too few observations. "
            "Consider adjusting alpha_high / alpha_low."
        )
        # Fallback
        if math.isnan(mu11):
            mu11 = float(Y[A == 1.0].mean()) if (A == 1.0).sum() > 0 else 0.0
        if math.isnan(mu10):
            mu10 = float(Y[A == 0.0].mean()) if (A == 0.0).sum() > 0 else 0.0
        if math.isnan(mu01):
            mu01 = mu10

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    # Combined SEs (independent strata approximation)
    def _combined_se(s1: float, s2: float) -> float:
        if math.isnan(s1) or math.isnan(s2):
            return float("nan")
        return math.sqrt(s1 ** 2 + s2 ** 2)

    se_de = _combined_se(se11, se10)
    se_se = _combined_se(se10, se01)
    se_te = _combined_se(se11, se01)

    assumptions = {
        "no_unmeasured_confounding": "Treatment assignment is ignorable given observed covariates.",
        "positivity_exposure": "Each unit has positive probability of each exposure level.",
        "stratified_interference": "Potential outcome depends on own treatment and exposure "
        "level (aggregated from adjacency) only.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.NETWORK_AIPW,
            exposure_mapping=ExposureMappingType.FRACTIONAL,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "mapping_type": mapping_type,
                "n_bootstrap": n_bootstrap,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_spatial_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Kernel-weighted spatial spillover estimator."""
    bandwidth_param = params.get("bandwidth", "auto")
    kernel = str(params.get("kernel", "gaussian"))
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    # Resolve spatial structure
    if data.coordinates is not None:
        coords = data.coordinates[:, :2].astype(float)  # keep only x, y
    elif data.adjacency_matrix is not None:
        # Fallback: use adjacency as weight matrix directly
        W = data.adjacency_matrix.astype(float)
        degree = W.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(degree > 0, (W @ A) / degree, 0.0)
        coords = None
    else:
        return {
            "result": _build_report_failure(
                InterferenceMethod.SPATIAL_KERNEL,
                ExposureMappingType.KERNEL,
                n,
                n_treated,
                "coordinates or adjacency_matrix required for SpatialInterferenceEstimator",
            )
        }

    used_bandwidth: float | None = None
    if coords is not None:
        if bandwidth_param == "auto":
            bw = _auto_bandwidth(coords)
        else:
            try:
                bw = float(bandwidth_param)
            except (TypeError, ValueError):
                bw = _auto_bandwidth(coords)
        if bw <= 0:
            return {
                "result": _build_report_failure(
                    InterferenceMethod.SPATIAL_KERNEL,
                    ExposureMappingType.KERNEL,
                    n,
                    n_treated,
                    f"bandwidth must be positive, got {bw}",
                )
            }
        used_bandwidth = bw
        W = _kernel_weights(coords, bw)
        degree = W.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(degree > 0, (W @ A) / degree, 0.0)

    # Exposure strata
    e_high = (s >= alpha_high).astype(float)
    e_low = (s <= alpha_low).astype(float)

    base_features = np.column_stack([A, s])
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _ipw_mean(a_val: float, e_ind: np.ndarray) -> tuple[float, float]:
        stratum = (A == a_val) & (e_ind > 0)
        if stratum.sum() < 2:
            return float("nan"), float("nan")
        try:
            ps = _logistic_propensity(stratum.astype(int), base_features)
        except Exception:
            ps = np.full(n, float(stratum.mean()) + 1e-6)
        est, scores = _ipw_potential_outcome(Y, stratum.astype(float), ps)
        se = math.sqrt(max(_sandwich_var(scores - est), 0.0))
        return est, se

    mu11, se11 = _ipw_mean(1.0, e_high)
    mu10, se10 = _ipw_mean(0.0, e_high)
    mu01, se01 = _ipw_mean(0.0, e_low)

    warnings: list[str] = []
    for mu, name in ((mu11, "E[Y(1,high)]"), (mu10, "E[Y(0,high)]"), (mu01, "E[Y(0,low)]")):
        if math.isnan(mu):
            warnings.append(f"Stratum for {name} has too few units; using marginal mean.")

    if math.isnan(mu11):
        mu11 = float(Y[A == 1.0].mean()) if (A == 1.0).sum() > 0 else 0.0
    if math.isnan(mu10):
        mu10 = float(Y[A == 0.0].mean()) if (A == 0.0).sum() > 0 else 0.0
    if math.isnan(mu01):
        mu01 = mu10

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    def _cse(s1: float, s2: float) -> float:
        if math.isnan(s1) or math.isnan(s2):
            return float("nan")
        return math.sqrt(s1 ** 2 + s2 ** 2)

    se_de = _cse(se11, se10)
    se_se = _cse(se10, se01)
    se_te = _cse(se11, se01)

    exposure_params: dict[str, Any] = {
        "kernel": kernel,
        "alpha_high": alpha_high,
        "alpha_low": alpha_low,
    }
    if used_bandwidth is not None:
        exposure_params["bandwidth"] = used_bandwidth

    assumptions = {
        "geographic_spillover": "Spillover effects decay with geographic distance as modelled by the kernel.",
        "positivity": "Positive probability of each exposure level in each spatial location.",
        "no_unmeasured_confounding": "Treatment assignment ignorable given covariates.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.SPATIAL_KERNEL,
            exposure_mapping=ExposureMappingType.KERNEL,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params=exposure_params,
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_bipartite_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Zigler & Papadogeorgou (2021) bipartite interference."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    aggregate_fn = str(params.get("aggregate_fn", "fraction"))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.bipartite_edges is None or data.treatment_unit_ids is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.BIPARTITE,
                ExposureMappingType.BIPARTITE,
                n,
                n_treated,
                "bipartite_edges and treatment_unit_ids are required for "
                "BipartiteInterferenceEstimator",
            )
        }

    edges = data.bipartite_edges  # (n_edges, 2): [tx_unit_idx, outcome_unit_idx]
    tx_ids = data.treatment_unit_ids  # (n_tx,) int
    n_tx = len(tx_ids)

    # Treatment of treatment units
    A_tx = A[tx_ids]

    # Aggregate exposure for each outcome unit (all n units, non-outcome units get 0)
    g = np.zeros(n, dtype=float)
    for out_idx in range(n):
        upstream = edges[edges[:, 1] == out_idx, 0]
        if len(upstream) == 0:
            continue
        if aggregate_fn == "fraction":
            g[out_idx] = float(A_tx[upstream].mean())
        elif aggregate_fn == "count":
            g[out_idx] = float(A_tx[upstream].sum())
        else:  # "max"
            g[out_idx] = float(A_tx[upstream].max())

    # For outcome units: high/low exposure indicators
    e_high = (g >= alpha_high).astype(float)
    e_low = (g <= alpha_low).astype(float)

    # Mark outcome units (not treatment units)
    outcome_mask = np.ones(n, dtype=bool)
    outcome_mask[tx_ids] = False
    n_outcome = int(outcome_mask.sum())

    base_features = g.reshape(-1, 1)
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _mean_potential(e_ind: np.ndarray, out_mask: np.ndarray) -> tuple[float, float]:
        stratum = e_ind.astype(bool) & out_mask
        if stratum.sum() < 2:
            return float("nan"), float("nan")
        try:
            ps = _logistic_propensity(stratum[out_mask].astype(int), base_features[out_mask])
        except Exception:
            ps = np.full(int(out_mask.sum()), float(stratum[out_mask].mean()) + 1e-6)
        ps_full = np.zeros(n)
        ps_full[out_mask] = ps
        est, scores = _ipw_potential_outcome(
            Y * out_mask.astype(float),
            stratum.astype(float),
            np.clip(ps_full, 1e-6, 1 - 1e-6),
        )
        se = math.sqrt(max(_sandwich_var(scores - est), 0.0))
        return est, se

    mu_high, se_high = _mean_potential(e_high, outcome_mask)
    mu_low, se_low = _mean_potential(e_low, outcome_mask)

    warnings: list[str] = []
    if math.isnan(mu_high) or math.isnan(mu_low):
        warnings.append(
            "One or more exposure strata have too few outcome units. "
            "Falling back to marginal mean differences."
        )
        mu_high_val = float(Y[outcome_mask & e_high.astype(bool)].mean()) if (outcome_mask & e_high.astype(bool)).sum() > 0 else 0.0
        mu_low_val = float(Y[outcome_mask & e_low.astype(bool)].mean()) if (outcome_mask & e_low.astype(bool)).sum() > 0 else 0.0
        if math.isnan(mu_high):
            mu_high, se_high = mu_high_val, 0.0
        if math.isnan(mu_low):
            mu_low, se_low = mu_low_val, 0.0

    # In bipartite setting: direct effect = contrast in aggregate exposure
    # (no "own treatment" for outcome units)
    de = mu_high - mu_low
    se_val = mu_high - mu_low  # spillover ≡ aggregate exposure contrast
    te = de

    se_de = math.sqrt(se_high ** 2 + se_low ** 2) if math.isfinite(se_high) and math.isfinite(se_low) else float("nan")
    se_se = se_de
    se_te = se_de

    assumptions = {
        "bipartite_structure": "Outcome units are distinct from treatment units; "
        "interference acts only through upstream treatment.",
        "positivity": "Positive probability of each aggregate exposure level.",
        "no_unmeasured_confounding": "Assignment of treatment units is ignorable given observed covariates.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.BIPARTITE,
            exposure_mapping=ExposureMappingType.BIPARTITE,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "aggregate_fn": aggregate_fn,
                "n_treatment_units": n_tx,
                "n_outcome_units": n_outcome,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


# ──────────────────────────────────────────────────────────────────────────────
# Method 1: PartialInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "cluster", "spillover"},
)
class PartialInterferenceEstimator:
    """Clustered partial interference estimator (Hudgens & Halloran 2008).

    Decomposes average causal effects into a **direct effect** (own
    treatment, neighbours' allocation fixed) and a **spillover effect**
    (change in outcome from shifting cluster allocation from α_low to
    α_high, own treatment fixed at 0).

    Requires ``cluster_id`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="partial",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                    description="Observed outcome Y_i for each unit.",
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                    description="Binary treatment indicator A_i ∈ {0, 1}.",
                ),
                SlotSpec(
                    name="cluster_id",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("category", "id"),
                    shape=("n_units",),
                    description="Integer cluster membership c_i.",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                    description="Optional pre-treatment covariates X_i.",
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="alpha_high",
                default=0.5,
                description="High-coverage allocation arm α₁.",
            ),
            ParameterSpec(
                name="alpha_low",
                default=0.0,
                description="Low-coverage allocation arm α₂ (usually 0).",
            ),
            ParameterSpec(
                name="alpha_bandwidth",
                default=0.1,
                description="Tolerance window for α-stratum membership.",
            ),
            ParameterSpec(
                name="exposure_mapping",
                default="fractional",
                description="Exposure mapping type: 'fractional' or 'threshold'.",
            ),
            ParameterSpec(
                name="threshold",
                default=0.5,
                description="Threshold for binary exposure mapping.",
            ),
            ParameterSpec(
                name="confidence_level",
                default=0.95,
                description="Confidence level for interval estimates.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Clustered partial interference estimator. Decomposes ATE into "
            "direct effect DE(α) = E[Y(1,α)] − E[Y(0,α)] and spillover effect "
            "SE(α₁,α₂) = E[Y(0,α₁)] − E[Y(0,α₂)] using IPW with exposure "
            "mapping within clusters."
        ),
        tags=frozenset({"causal", "interference", "cluster", "spillover"}),
        citations=(
            "Hudgens, M.G. & Halloran, M.E. (2008). Toward causal inference with "
            "interference. JASA 103(482).",
            "Sobel, M.E. (2006). What do randomized studies of housing mobility "
            "demonstrate? JASA 101(476).",
            "Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal "
            "inference in the presence of interference. Stat. Methods Med. Res.",
        ),
        equations={
            "direct_effect": "DE(α) = E[Y(1,α)] - E[Y(0,α)]",
            "spillover_effect": "SE(α1,α2) = E[Y(0,α1)] - E[Y(0,α2)]",
            "total_effect": "TE(α1,α2) = E[Y(1,α1)] - E[Y(0,α2)]",
            "exposure_mapping_fractional": "f_i = Σ_{j≠i,c} A_j / (n_c - 1)",
        },
        assumptions={
            "partial_interference": "Units in different clusters do not interfere.",
            "stratified_interference": (
                "Within a cluster, a unit's potential outcome depends only on "
                "its own treatment and the aggregate cluster allocation."
            ),
            "positivity": (
                "P(A_i=a, f_i≈α | X_i) > 0 for all a ∈ {0,1} and α ∈ {α_low, α_high}."
            ),
        },
        when_to_use=(
            "Cluster-randomised experiments or observational studies where "
            "interference is limited to within pre-defined groups (villages, "
            "schools, households, clinics)."
        ),
        when_not_to_use=(
            "Cross-cluster interference; continuous treatment; single-unit "
            "clusters (cluster_size=1)."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: effect of own treatment, holding neighbours' "
            "allocation fixed at α_high. "
            "spillover_effect: effect of shifting cluster allocation from "
            "α_low to α_high, own treatment fixed at 0."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_partial_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 2: NetworkAIPWEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "network", "aipw", "spillover"},
)
class NetworkAIPWEstimator:
    """General network AIPW estimator (Aronow & Samii 2017).

    Uses an arbitrary adjacency matrix to define the exposure mapping
    f(A, N_i) → exposure level, then applies doubly-robust AIPW
    estimation within exposure strata.

    Requires ``adjacency_matrix`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="network_aipw",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="adjacency_matrix",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("adjacency", "weight"),
                    shape=("n_units", "n_units"),
                    description="Network adjacency (weighted or binary).",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="exposure_mapping",
                default="fraction",
                description="'fraction' | 'count' | 'any'",
            ),
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(
                name="n_bootstrap",
                default=200,
                description="Bootstrap draws for variance estimation.",
            ),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Doubly-robust AIPW estimator under general network interference. "
            "Uses an exposure mapping f(A, N_i) derived from the adjacency "
            "matrix to define treatment×exposure strata, then applies AIPW "
            "within each stratum."
        ),
        tags=frozenset({"causal", "interference", "network", "aipw", "spillover"}),
        citations=(
            "Aronow, P.M. & Samii, C. (2017). Estimating average causal "
            "effects under general interference. Ann. Appl. Stat. 11(4).",
            "Liu, L., Hudgens, M.G. & Becker-Dreps, S. (2016). On sample "
            "randomization inference of causal effects in the presence of "
            "interference. JRSS-B.",
        ),
        equations={
            "exposure_fraction": "e_i = (Σ_j W_ij A_j) / (Σ_j W_ij)",
            "aipw_score": "ψ_i = I(stratum)/P(stratum|X) * Y - (I/P - 1) * μ̂(X)",
        },
        assumptions={
            "no_unmeasured_confounding": "Treatment ignorable given covariates.",
            "exposure_positivity": "P(e_i = e | X_i) > 0 for all exposure levels e.",
            "network_structure_known": "Adjacency matrix W is observed without error.",
        },
        when_to_use=(
            "Social network experiments or observational studies with an "
            "observed interaction graph where spillover is mediated by "
            "direct connections."
        ),
        when_not_to_use="Unobserved network structure; very sparse networks.",
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: E[Y(1,high)] - E[Y(0,high)] — effect of own "
            "treatment among units with high network exposure. "
            "spillover_effect: E[Y(0,high)] - E[Y(0,low)] — effect of "
            "having highly-treated neighbours."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_network_aipw(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 3: SpatialInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "spatial", "spillover"},
)
class SpatialInterferenceEstimator:
    """Gaussian kernel spatial spillover estimator.

    Constructs a kernel-weighted exposure mapping
    s_i = Σ_j K(d_ij; h) A_j / Σ_j K(d_ij; h)
    using geographic ``coordinates``, then estimates direct and spillover
    effects across high/low exposure strata.

    Requires ``coordinates`` (or falls back to ``adjacency_matrix``) in
    the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="spatial",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="coordinates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("space", "coordinate"),
                    shape=("n_units", "n_dims"),
                    description="Spatial coordinates [x, y] or [lon, lat].",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="bandwidth",
                default="auto",
                description="Kernel bandwidth h or 'auto' for Silverman ROT.",
            ),
            ParameterSpec(
                name="kernel",
                default="gaussian",
                description="Kernel function: 'gaussian'.",
            ),
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Kernel-weighted geographic spillover estimator. Builds a "
            "Gaussian exposure mapping from spatial coordinates, then "
            "estimates direct effect DE and spillover SE via IPW across "
            "high/low kernel-exposure strata."
        ),
        tags=frozenset({"causal", "interference", "spatial", "spillover"}),
        citations=(
            "Verbitsky-Savitz, N. & Raudenbush, S.W. (2012). Causal "
            "inference under interference in spatial settings. Epidemiol. Methods.",
            "Aronow, P.M. & Samii, C. (2017). Estimating average causal "
            "effects under general interference. Ann. Appl. Stat. 11(4).",
        ),
        equations={
            "kernel_exposure": "s_i = Σ_j K(‖x_i - x_j‖; h) A_j / Σ_j K(‖x_i - x_j‖; h)",
            "gaussian_kernel": "K(d; h) = exp(-d² / (2h²))",
            "bandwidth_rot": "h* = σ_coords · n^(-1/5)",
        },
        assumptions={
            "spatial_spillover": "Interference decays smoothly with geographic distance.",
            "kernel_specification": "Gaussian kernel captures the decay structure adequately.",
            "positivity": "Positive probability of each spatial exposure level.",
        },
        when_to_use=(
            "Geographic policy evaluation (environmental regulations, "
            "infrastructure, epidemics) where spillover is plausibly distance-based."
        ),
        when_not_to_use="Non-geographic networks; sharp spillover cutoffs.",
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: effect of own treatment, controlling for "
            "spatial exposure. spillover_effect: effect of being in a "
            "high-treatment neighbourhood vs a low-treatment neighbourhood."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_spatial_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 4: BipartiteInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "bipartite", "spillover"},
)
class BipartiteInterferenceEstimator:
    """Bipartite causal inference with interference (Zigler & Papadogeorgou 2021).

    For settings where treatment units (e.g. power plants, hospitals) are
    distinct from outcome units (e.g. counties, patients).  Interference
    flows from treatment units to outcome units through a bipartite graph.

    Requires ``bipartite_edges`` and ``treatment_unit_ids`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bipartite",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                    description="Observed Y_i for all n units (tx + outcome units).",
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                    description="Binary treatment A_i; non-zero only for treatment units.",
                ),
                SlotSpec(
                    name="bipartite_edges",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("graph", "edge"),
                    shape=("n_edges", "2"),
                    description="[treatment_unit_idx, outcome_unit_idx] edges.",
                ),
                SlotSpec(
                    name="treatment_unit_ids",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("category", "id"),
                    shape=("n_treatment_units",),
                    description="Integer indices of treatment units within the n-unit array.",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(
                name="aggregate_fn",
                default="fraction",
                description="'fraction' | 'count' | 'max'",
            ),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Bipartite interference estimator for settings with separate "
            "treatment and outcome units linked by a bipartite graph. "
            "Aggregates upstream treatment into a per-outcome-unit exposure "
            "g_i and estimates effects across high/low exposure strata."
        ),
        tags=frozenset({"causal", "interference", "bipartite", "spillover"}),
        citations=(
            "Zigler, C.M. & Papadogeorgou, G. (2021). Bipartite causal "
            "inference with interference. Stat. Sci. 36(3).",
            "Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal "
            "inference in the presence of interference. Stat. Methods Med. Res.",
        ),
        equations={
            "aggregate_exposure_fraction": "g_i = (1/|N_i|) Σ_{j ∈ N_i} A_j",
            "aggregate_exposure_count": "g_i = Σ_{j ∈ N_i} A_j",
        },
        assumptions={
            "bipartite_structure": (
                "Outcome units are distinct from treatment units; "
                "interference acts only through the bipartite graph."
            ),
            "positivity": "P(g_i ≥ α_high | X_i) > 0 and P(g_i ≤ α_low | X_i) > 0.",
            "no_unmeasured_confounding": "Treatment unit assignments ignorable given covariates.",
        },
        when_to_use=(
            "Power-plant emission regulation studies (plants → counties), "
            "hospital interventions (hospitals → patients), "
            "supplier interventions (suppliers → retailers)."
        ),
        when_not_to_use="Treatment and outcome units are the same; treatment is continuous.",
        typical_min_obs=50,
        output_interpretation=(
            "direct_effect ≡ spillover_effect: contrast E[Y(high)] - E[Y(low)] "
            "for outcome units — effect of being downstream of more treated "
            "treatment units."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_bipartite_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


__all__ = [
    "InterferenceAugmentedGraph",
    "InterferenceIdentificationResult",
    "build_interference_topology_contracts",
    "identify_interference_effect",
    "BipartiteInterferenceEstimator",
    "NetworkAIPWEstimator",
    "PartialInterferenceEstimator",
    "SpatialInterferenceEstimator",
]
