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
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import ValidationError

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
from polisyos.foundry.methods.catalog.causal._interference_contracts import (
    InterferenceAugmentedGraph,
    InterferenceIdentificationResult,
    _ReductionErrorBoundPlan,
    _SimplicialSupportGate,
    _TopologyCertificatePlan,
)
from polisyos.foundry.methods.catalog.causal.protocols import NetworkCausalData
from polisyos.foundry.methods.catalog.network.generative_protocols import SBMStratificationResult
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InteractionComplex,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    MAUPInvarianceCertificate,
    MAUPPartitionCheck,
    NetworkInterferenceReport,
    SpatialHodgeDiagnostics,
    SpatialHodgeScaleProfile,
    SpatialResult,
)
from polisyos.ir.analytics.network_generative import BlockSupportReport, CausalBlockBridge
from polisyos.ir.refs import ArtifactRefModel

_PAIRWISE_QUERY_FAMILY = "pairwise_projection_queries"
_CLUSTER_QUERY_FAMILY = "cluster_projection_queries"
_SIMPLICIAL_STAR_LOCAL_QUERY_FAMILY = "simplicial_star_local_queries"
_UNSUPPORTED_COMPLEX_QUERY_FAMILY = "unsupported_complex_queries"
_SUPPORTED_MAUP_ESTIMANDS = {"direct", "spillover", "total"}
_MAUP_POSITIVITY_BLOCK_THRESHOLD = 0.01

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


def _coerce_sbm_stratification_result(
    payload: SBMStratificationResult | Mapping[str, Any],
) -> SBMStratificationResult:
    if isinstance(payload, SBMStratificationResult):
        return payload
    if isinstance(payload, Mapping):
        return SBMStratificationResult.model_validate(payload)
    raise TypeError("Expected SBMStratificationResult or mapping payload")


def _block_exposure_summary(
    labels: np.ndarray,
    *,
    adjacency_matrix: np.ndarray | None,
    treatment: np.ndarray,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "treatment_share_by_block": {},
        "mean_degree_by_block": {},
    }
    for block in np.unique(labels):
        mask = labels == block
        summary["treatment_share_by_block"][str(int(block))] = float(np.mean(treatment[mask]))
        if adjacency_matrix is not None:
            summary["mean_degree_by_block"][str(int(block))] = float(
                np.mean(np.sum(adjacency_matrix[mask], axis=1))
            )
    if adjacency_matrix is None:
        return summary
    block_ids = np.unique(labels)
    block_graph = np.zeros((len(block_ids), len(block_ids)), dtype=float)
    for row_idx, row_block in enumerate(block_ids):
        row_mask = labels == row_block
        for col_idx, col_block in enumerate(block_ids):
            col_mask = labels == col_block
            block_graph[row_idx, col_idx] = float(
                np.mean(adjacency_matrix[np.ix_(row_mask, col_mask)])
            )
    summary["block_connectivity"] = block_graph.tolist()
    return summary


def build_block_stratified_network_causal_data(
    *,
    outcome: Any,
    treatment: Any,
    stratification: SBMStratificationResult | Mapping[str, Any],
    covariates: Any | None = None,
    adjacency_matrix: Any | None = None,
    coordinates: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
    min_treated_per_block: int = 1,
    min_control_per_block: int = 1,
) -> tuple[NetworkCausalData, CausalBlockBridge]:
    """Bridge SBM labels into `NetworkCausalData` plus a positivity report."""
    stratified = _coerce_sbm_stratification_result(stratification)
    labels = np.asarray(stratified.labels, dtype=int)
    outcome_arr = np.asarray(outcome, dtype=float)
    treatment_arr = np.asarray(treatment, dtype=float)
    if outcome_arr.ndim != 1 or treatment_arr.ndim != 1:
        raise ValueError("outcome and treatment must be 1D arrays")
    if outcome_arr.shape[0] != labels.shape[0] or treatment_arr.shape[0] != labels.shape[0]:
        raise ValueError("stratification labels must align with outcome/treatment length")

    adjacency_arr = None if adjacency_matrix is None else np.asarray(adjacency_matrix, dtype=float)
    coordinates_arr = None if coordinates is None else np.asarray(coordinates, dtype=float)
    covariates_arr = None if covariates is None else np.asarray(covariates, dtype=float)

    supports: list[BlockSupportReport] = []
    warnings: list[str] = []
    positivity_passed = True
    for block_id in np.unique(labels):
        mask = labels == block_id
        n_units = int(mask.sum())
        n_treated = int(np.sum(treatment_arr[mask]))
        n_control = n_units - n_treated
        treated_share = float(n_treated / max(n_units, 1))
        block_passed = n_treated >= min_treated_per_block and n_control >= min_control_per_block
        positivity_passed &= block_passed
        block_warnings: list[str] = []
        if not block_passed:
            block_warnings.append(
                "Block violates minimum treated/control support for downstream interference estimation."
            )
            warnings.append(f"block_{int(block_id)}_positivity_low_support")
        supports.append(
            BlockSupportReport(
                block_id=int(block_id),
                n_units=n_units,
                n_treated=n_treated,
                n_control=n_control,
                treated_share=treated_share,
                positivity_passed=block_passed,
                warnings=tuple(block_warnings),
            )
        )

    node_ids = stratified.metadata.get("node_ids")
    if not isinstance(node_ids, list) or len(node_ids) != labels.shape[0]:
        node_ids = [str(idx) for idx in range(labels.shape[0])]
    bridge = CausalBlockBridge(
        cluster_id=labels,
        node_to_block={
            str(node_id): int(block) for node_id, block in zip(node_ids, labels, strict=True)
        },
        block_support=tuple(supports),
        positivity_passed=positivity_passed,
        aggregate_exposures=_block_exposure_summary(
            labels,
            adjacency_matrix=adjacency_arr,
            treatment=treatment_arr,
        ),
        warnings=tuple(dict.fromkeys(warnings)),
    )

    merged_metadata = dict(metadata or {})
    merged_metadata.setdefault(
        "sbm_design",
        {
            "method_name": stratified.method_name,
            "effective_blocks": len(np.unique(labels)),
            "overall_stability": stratified.stability.get("overall_stability"),
        },
    )

    data = NetworkCausalData(
        outcome=outcome_arr,
        treatment=treatment_arr,
        covariates=covariates_arr,
        adjacency_matrix=adjacency_arr,
        cluster_id=labels,
        coordinates=coordinates_arr,
        metadata=merged_metadata,
    )
    return data, bridge


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
    ]
    | None,
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
    maximal = [face for face in faces if not any(face < candidate for candidate in faces)]
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
                "pass"
                if _design_positivity_declared(augmented_graph, operator_metadata)
                else "fail"
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
        raw_nodes = [node.strip() for node in re.split(r"[|,;]", value) if node.strip()]
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


def _triangle_response_kind(
    bound_model: Mapping[str, Any],
) -> Literal["linear", "lipschitz"] | None:
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
    sums_by_node: dict[str, float] = dict.fromkeys(expected_nodes, 0.0)
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
        lipschitz_by_node[node] * weight_sums_by_node[node] for node in weight_sums_by_node
    )
    bound = (2.0 * design_p**2 * (1.0 - design_p) * total_weight) / len(interaction_complex.nodes)
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
            fallback_mode=(mode_used if mode_used in {"pairwise", "clustered"} else "unsupported"),
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

    if _maximal_faces_partition_nodes(
        interaction_complex
    ) and _operator_factorizes_through_within_facet_summary(operator_metadata):
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
    ]
    | None = None,
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
            target_outcome_nodes = [node for node in outcome_nodes if node in cluster_members]

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
                "partial"
                if cluster_var is not None and cross_unit
                else ("network" if cross_unit else "none")
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

    augmented_graph, treatment_nodes, outcome_nodes, cross_unit = (
        _build_interference_augmented_graph(
            graph,
            treatment=treatment,
            outcome=outcome,
            exposure_mapping=exposure_mapping,
            cluster_var=cluster_var,
        )
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
            description=(f"Detected {len(cross_unit)} cross-unit edge(s) in the original graph."),
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
    status = (
        "identified" if base_result.status is IdentificationStatus.IDENTIFIED else "non_identified"
    )
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
    sq_dist = (diff**2).sum(axis=-1)  # (n, n)
    W = np.exp(-sq_dist / (2.0 * bandwidth**2))
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
    return float(np.mean(scores**2) - np.mean(scores) ** 2) / n


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


@dataclass(frozen=True)
class _ContrastEstimate:
    theta: float | None
    se: float | None
    ess_min: float | None
    min_positivity: float | None
    cell_counts: Mapping[str, int]
    blocker_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _dedupe_preserve_order(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _coerce_optional_artifact_ref(
    value: Any,
    *,
    field_name: str,
) -> tuple[ArtifactRefModel | None, tuple[str, ...]]:
    if value is None:
        return None, ()
    try:
        ref = (
            value if isinstance(value, ArtifactRefModel) else ArtifactRefModel.model_validate(value)
        )
    except ValidationError:
        return None, (f"{field_name}_invalid",)
    return ref, ()


def _resolve_maup_partitions(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    raw = params.get("candidate_partitions")
    if raw is None:
        raw = data.metadata.get("candidate_partitions")
    if raw is None:
        raw = data.metadata.get("partitions")
    if raw in (None, ()):
        return ()
    if not isinstance(raw, (list, tuple)):
        raise TypeError("candidate_partitions must be a list or tuple")
    partitions: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            partition = dict(item)
        else:
            partition = {"block_of_unit": item}
        partition.setdefault("partition_id", f"partition_{index}")
        partitions.append(partition)
    return tuple(partitions)


def _normalize_partition_labels(
    block_of_unit: Any,
    *,
    n_units: int,
) -> tuple[np.ndarray, tuple[str, ...]]:
    labels_raw = np.asarray(block_of_unit, dtype=object)
    if labels_raw.ndim != 1 or labels_raw.shape[0] != n_units:
        raise ValueError("block_of_unit must be a 1D array aligned with n_units")
    labels: list[str] = []
    for raw_label in labels_raw.tolist():
        if raw_label is None:
            raise ValueError("block_of_unit must not contain null labels")
        if isinstance(raw_label, (float, np.floating)) and not math.isfinite(float(raw_label)):
            raise ValueError("block_of_unit must not contain non-finite labels")
        label = str(raw_label).strip()
        if not label:
            raise ValueError("block_of_unit labels must be non-empty")
        labels.append(label)
    unique_labels, inverse = np.unique(np.asarray(labels, dtype=object), return_inverse=True)
    if unique_labels.size < 2:
        raise ValueError("candidate partition must contain at least two blocks")
    return inverse.astype(int), tuple(str(label) for label in unique_labels.tolist())


def _partition_operators(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n_units = int(labels.shape[0])
    n_blocks = int(labels.max()) + 1
    incidence = np.zeros((n_blocks, n_units), dtype=float)
    incidence[labels, np.arange(n_units)] = 1.0
    block_sizes = np.sum(incidence, axis=1, keepdims=True)
    averaging = incidence / np.clip(block_sizes, 1.0, None)
    return averaging, incidence


def _contrast_compute_lumpability_residual(
    exposure_operator: np.ndarray,
    block_of_unit: Any,
) -> tuple[float, bool, np.ndarray]:
    labels = np.asarray(block_of_unit, dtype=int)
    averaging, incidence = _partition_operators(labels)
    aggregate_operator = averaging @ exposure_operator @ incidence.T
    lhs = averaging @ exposure_operator
    rhs = aggregate_operator @ averaging
    denominator = float(np.linalg.norm(lhs, ord="fro"))
    if denominator <= 1e-12:
        return 0.0, True, aggregate_operator
    residual = float(np.linalg.norm(lhs - rhs, ord="fro") / denominator)
    return residual, residual <= 1e-12, aggregate_operator


def _cell_mean_and_var(
    values: np.ndarray, mask: np.ndarray
) -> tuple[float | None, float | None, int]:
    count = int(mask.sum())
    if count == 0:
        return None, None, 0
    sample = values[mask]
    mean = float(np.mean(sample))
    if count < 2:
        return mean, None, count
    return mean, float(np.var(sample, ddof=1)), count


def _difference_of_means(
    outcome: np.ndarray,
    *,
    left_mask: np.ndarray,
    right_mask: np.ndarray,
    left_label: str,
    right_label: str,
) -> _ContrastEstimate:
    left_mean, left_var, left_count = _cell_mean_and_var(outcome, left_mask)
    right_mean, right_var, right_count = _cell_mean_and_var(outcome, right_mask)
    cell_counts = {left_label: left_count, right_label: right_count}
    support = float(len(outcome))
    min_positivity = min(left_count, right_count) / support if support > 0 else None
    ess_min = float(min(left_count, right_count))
    warnings: list[str] = []
    blocker_codes: list[str] = []
    if left_count == 0 or right_count == 0 or left_mean is None or right_mean is None:
        blocker_codes.append("MAUP_E_POSITIVITY")
        warnings.append(f"Missing support for {left_label} or {right_label}.")
        return _ContrastEstimate(
            theta=None,
            se=None,
            ess_min=ess_min,
            min_positivity=min_positivity,
            cell_counts=cell_counts,
            blocker_codes=_dedupe_preserve_order(blocker_codes),
            warnings=_dedupe_preserve_order(warnings),
        )
    theta = left_mean - right_mean
    if left_var is None or right_var is None:
        blocker_codes.append("MAUP_E_LOW_ESS")
        warnings.append(
            f"Too few observations for a stable variance estimate in {left_label}/{right_label}."
        )
        return _ContrastEstimate(
            theta=theta,
            se=None,
            ess_min=ess_min,
            min_positivity=min_positivity,
            cell_counts=cell_counts,
            blocker_codes=_dedupe_preserve_order(blocker_codes),
            warnings=_dedupe_preserve_order(warnings),
        )
    se = math.sqrt(max(left_var / left_count + right_var / right_count, 0.0))
    return _ContrastEstimate(
        theta=theta,
        se=se,
        ess_min=ess_min,
        min_positivity=min_positivity,
        cell_counts=cell_counts,
    )


def _estimate_maup_contrast(
    outcome: np.ndarray,
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    estimand: Literal["direct", "spillover", "total"],
    alpha_high: float,
    alpha_low: float,
    treatment_threshold: float = 0.5,
) -> _ContrastEstimate:
    treated = treatment >= treatment_threshold
    control = treatment < treatment_threshold
    exposure_high = exposure >= alpha_high
    exposure_low = exposure <= alpha_low
    if estimand == "direct":
        return _difference_of_means(
            outcome,
            left_mask=treated & exposure_high,
            right_mask=control & exposure_high,
            left_label="treated_high",
            right_label="control_high",
        )
    if estimand == "spillover":
        return _difference_of_means(
            outcome,
            left_mask=control & exposure_high,
            right_mask=control & exposure_low,
            left_label="control_high",
            right_label="control_low",
        )
    return _difference_of_means(
        outcome,
        left_mask=treated & exposure_high,
        right_mask=control & exposure_low,
        left_label="treated_high",
        right_label="control_low",
    )


def _contrast_hausman_compare_partition_effects(
    theta_partition: float | None,
    se_partition: float | None,
    theta_micro: float | None,
    se_micro: float | None,
) -> tuple[float | None, float | None, str | None]:
    if theta_partition is None or theta_micro is None or se_partition is None or se_micro is None:
        return None, None, "MAUP_E_SINGULAR_COV"
    if not (
        math.isfinite(theta_partition)
        and math.isfinite(theta_micro)
        and math.isfinite(se_partition)
        and math.isfinite(se_micro)
    ):
        return None, None, "MAUP_E_SINGULAR_COV"
    variance = se_partition**2 + se_micro**2
    if variance <= 1e-12:
        return None, None, "MAUP_E_SINGULAR_COV"
    delta = theta_partition - theta_micro
    stat = (delta**2) / variance
    p_value = math.erfc(abs(delta) / math.sqrt(2.0 * variance))
    return stat, p_value, None


def _holm_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    total = len(p_values)
    for rank, (index, p_value) in enumerate(indexed, start=1):
        candidate = min((total - rank + 1) * p_value, 1.0)
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted


def _recommended_maup_mode(
    status: str,
) -> Literal[
    "micro_only",
    "micro_plus_safe_aggregate",
    "block_aggregate",
]:
    if status == "pass":
        return "micro_plus_safe_aggregate"
    if status in {"block", "not_identified"}:
        return "block_aggregate"
    return "micro_only"


def _attach_maup_certificate(
    report: NetworkInterferenceReport,
    certificate: MAUPInvarianceCertificate | None,
) -> SpatialResult:
    payload = report.model_dump()
    payload["maup_invariance_certificate"] = certificate
    return SpatialResult.model_validate(payload)


def _contrast_compute_maup_invariance_certificate(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
    *,
    exposure_operator: np.ndarray,
    exposure_vector: np.ndarray,
) -> MAUPInvarianceCertificate:
    estimand = str(params.get("estimand", "spillover")).strip().lower()
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    lump_warn = float(params.get("lumpability_warn_threshold", 0.01))
    lump_block = float(params.get("lumpability_block_threshold", 0.05))
    ess_warn = float(params.get("min_cell_ess_warn", 50))
    ess_block = float(params.get("min_cell_ess_block", 20))
    positivity_block = float(
        params.get("min_cell_positivity_block", _MAUP_POSITIVITY_BLOCK_THRESHOLD)
    )
    alpha = float(params.get("maup_alpha", 0.05))
    treatment_threshold = float(params.get("partition_treatment_threshold", 0.5))

    certificate_warnings: list[str] = list(spatial_result.warnings)
    certificate_blockers: list[str] = []
    metadata: dict[str, Any] = {
        "alpha_high": alpha_high,
        "alpha_low": alpha_low,
        "lumpability_warn_threshold": lump_warn,
        "lumpability_block_threshold": lump_block,
        "min_cell_ess_warn": ess_warn,
        "min_cell_ess_block": ess_block,
        "min_cell_positivity_block": positivity_block,
        "partition_treatment_threshold": treatment_threshold,
        "effect_source": "difference_in_means_contrast",
        "report_status": spatial_result.status,
    }

    interaction_complex_ref, ref_warnings = _coerce_optional_artifact_ref(
        params.get("interaction_complex_ref", data.metadata.get("interaction_complex_ref")),
        field_name="interaction_complex_ref",
    )
    certificate_warnings.extend(ref_warnings)
    interference_certificate_ref, cert_ref_warnings = _coerce_optional_artifact_ref(
        params.get(
            "interference_certificate_ref", data.metadata.get("interference_certificate_ref")
        ),
        field_name="interference_certificate_ref",
    )
    certificate_warnings.extend(cert_ref_warnings)

    if estimand not in _SUPPORTED_MAUP_ESTIMANDS:
        certificate_blockers.append("MAUP_E_UNSUPPORTED_EXPOSURE")
        certificate_warnings.append(f"Unsupported MAUP estimand '{estimand}'.")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand="spillover",
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if alpha_low > alpha_high:
        certificate_blockers.append("MAUP_E_UNSUPPORTED_EXPOSURE")
        certificate_warnings.append(
            "alpha_low must be less than or equal to alpha_high for MAUP certification."
        )
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if bool(
        params.get(
            "partitions_selected_post_outcome",
            data.metadata.get("partitions_selected_post_outcome", False),
        )
    ):
        certificate_blockers.append("MAUP_E_OUTCOME_LEAKAGE")
        certificate_warnings.append("Candidate partitions were flagged as post-outcome selections.")
        return MAUPInvarianceCertificate(
            status="block",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("block"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    try:
        partitions = _resolve_maup_partitions(data, params)
    except (TypeError, ValueError) as exc:
        certificate_blockers.append("MAUP_E_BAD_PARTITION")
        certificate_warnings.append(str(exc))
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if not partitions:
        certificate_warnings.append(
            "No candidate partitions were provided; MAUP certificate not tested."
        )
        return MAUPInvarianceCertificate(
            status="not_tested",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_tested"),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    micro_estimate = _estimate_maup_contrast(
        data.outcome.astype(float),
        data.treatment.astype(float),
        exposure_vector.astype(float),
        estimand=estimand,  # type: ignore[arg-type]
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        treatment_threshold=0.5,
    )
    metadata["micro_cell_counts"] = dict(micro_estimate.cell_counts)

    if micro_estimate.theta is None or micro_estimate.se is None:
        certificate_blockers.extend(micro_estimate.blocker_codes)
        certificate_blockers.append("MAUP_E_UNIDENTIFIED")
        certificate_warnings.extend(micro_estimate.warnings)
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            micro_effect=micro_estimate.theta,
            micro_se=micro_estimate.se,
            partitions_tested=0,
            min_positivity=micro_estimate.min_positivity,
            min_ess=micro_estimate.ess_min,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    checks: list[MAUPPartitionCheck] = []
    invalid_partitions: list[str] = []
    min_ess_candidates: list[float] = [
        micro_estimate.ess_min if micro_estimate.ess_min is not None else float("inf")
    ]
    min_pos_candidates: list[float] = [
        micro_estimate.min_positivity if micro_estimate.min_positivity is not None else 1.0
    ]

    for index, partition in enumerate(partitions):
        partition_id = (
            str(partition.get("partition_id", f"partition_{index}")).strip() or f"partition_{index}"
        )
        try:
            labels, unique_labels = _normalize_partition_labels(
                partition.get("block_of_unit"),
                n_units=data.n_units,
            )
        except ValueError:
            invalid_partitions.append(partition_id)
            certificate_blockers.append("MAUP_E_BAD_PARTITION")
            continue

        residual, exact_lumpable, aggregate_operator = _contrast_compute_lumpability_residual(
            exposure_operator,
            labels,
        )
        averaging, _ = _partition_operators(labels)
        outcome_partition = averaging @ data.outcome.astype(float)
        treatment_partition = averaging @ data.treatment.astype(float)
        exposure_partition = aggregate_operator @ treatment_partition
        partition_estimate = _estimate_maup_contrast(
            outcome_partition,
            treatment_partition,
            exposure_partition,
            estimand=estimand,  # type: ignore[arg-type]
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            treatment_threshold=treatment_threshold,
        )
        hausman_stat, p_value, hausman_code = _contrast_hausman_compare_partition_effects(
            partition_estimate.theta,
            partition_estimate.se,
            micro_estimate.theta,
            micro_estimate.se,
        )

        partition_blockers = list(partition_estimate.blocker_codes)
        partition_warnings = list(partition_estimate.warnings)
        if residual >= lump_block:
            partition_blockers.append("MAUP_E_STRUCTURAL_NONINVARIANCE")
        elif residual >= lump_warn:
            partition_warnings.append("lumpability_residual_warn")
        if partition_estimate.ess_min is not None:
            min_ess_candidates.append(partition_estimate.ess_min)
            if partition_estimate.ess_min < ess_block:
                partition_blockers.append("MAUP_E_LOW_ESS")
            elif partition_estimate.ess_min < ess_warn:
                partition_warnings.append("partition_low_ess_warn")
        if partition_estimate.min_positivity is not None:
            min_pos_candidates.append(partition_estimate.min_positivity)
            if partition_estimate.min_positivity < positivity_block:
                partition_blockers.append("MAUP_E_POSITIVITY")
        if hausman_code is not None:
            partition_blockers.append(hausman_code)

        checks.append(
            MAUPPartitionCheck(
                partition_id=partition_id,
                n_blocks=len(unique_labels),
                scale_label=partition.get("scale_label"),
                zoning_label=partition.get("zoning_label"),
                lumpability_residual=residual,
                exact_lumpable=exact_lumpable,
                theta_partition=partition_estimate.theta,
                se_partition=partition_estimate.se,
                hausman_stat=hausman_stat,
                p_value=p_value,
                ess_min=partition_estimate.ess_min,
                blocker_codes=_dedupe_preserve_order(partition_blockers),
                warnings=_dedupe_preserve_order(partition_warnings),
            )
        )

    if invalid_partitions:
        certificate_warnings.append(f"Skipped invalid partitions: {', '.join(invalid_partitions)}.")
        metadata["invalid_partitions"] = tuple(invalid_partitions)

    if not checks:
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            micro_effect=micro_estimate.theta,
            micro_se=micro_estimate.se,
            partitions_tested=0,
            min_positivity=min(min_pos_candidates),
            min_ess=min(min_ess_candidates),
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers or ["MAUP_E_BAD_PARTITION"]),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    indexed_p_values = [idx for idx, check in enumerate(checks) if check.p_value is not None]
    adjusted_p_values = _holm_adjust([float(checks[idx].p_value) for idx in indexed_p_values])
    for idx, adjusted_p in zip(indexed_p_values, adjusted_p_values, strict=True):
        check = checks[idx]
        updated_blockers = list(check.blocker_codes)
        if adjusted_p < alpha:
            updated_blockers.append("MAUP_E_STATISTICAL_NONINVARIANCE")
        checks[idx] = check.model_copy(
            update={
                "adjusted_p_value": adjusted_p,
                "blocker_codes": _dedupe_preserve_order(updated_blockers),
            }
        )

    all_check_blockers = [code for check in checks for code in check.blocker_codes]
    all_check_warnings = [warning for check in checks for warning in check.warnings]
    certificate_blockers.extend(all_check_blockers)
    certificate_warnings.extend(all_check_warnings)

    max_residual = max(
        check.lumpability_residual for check in checks if check.lumpability_residual is not None
    )
    adjusted_p_candidates = [
        check.adjusted_p_value for check in checks if check.adjusted_p_value is not None
    ]
    min_adjusted_p = min(adjusted_p_candidates) if adjusted_p_candidates else None

    hard_block_codes = {
        "MAUP_E_OUTCOME_LEAKAGE",
        "MAUP_E_STRUCTURAL_NONINVARIANCE",
        "MAUP_E_STATISTICAL_NONINVARIANCE",
        "MAUP_E_POSITIVITY",
        "MAUP_E_LOW_ESS",
        "MAUP_E_UNIDENTIFIED",
        "MAUP_E_SINGULAR_COV",
        "MAUP_E_BAD_PARTITION",
    }
    has_hard_block = any(code in hard_block_codes for code in certificate_blockers)
    if has_hard_block:
        status = "block"
    elif certificate_warnings:
        status = "warn"
    else:
        status = "pass"

    exact_invariance = (
        status == "pass"
        and all(check.exact_lumpable is True for check in checks)
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
    )
    near_invariance = (
        status in {"pass", "warn"}
        and max_residual < lump_block
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
    )

    return MAUPInvarianceCertificate(
        status=status,  # type: ignore[arg-type]
        estimand=estimand,  # type: ignore[arg-type]
        effect_scale="mean_difference",
        micro_effect=micro_estimate.theta,
        micro_se=micro_estimate.se,
        partitions_tested=len(checks),
        max_lumpability_residual=max_residual,
        min_adjusted_p_value=min_adjusted_p,
        min_positivity=min(min_pos_candidates),
        min_ess=min(min_ess_candidates),
        exact_invariance=exact_invariance,
        near_invariance=near_invariance,
        recommended_mode=_recommended_maup_mode(status),
        partition_checks=tuple(checks),
        blocker_codes=_dedupe_preserve_order(certificate_blockers),
        warnings=_dedupe_preserve_order(certificate_warnings),
        interaction_complex_ref=interaction_complex_ref,
        interference_certificate_ref=interference_certificate_ref,
        metadata=metadata,
    )


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
    ci_se = (
        _normal_ci(se_val, se_se, confidence_level) if math.isfinite(se_se) and se_se > 0 else None
    )
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
# MAUP invariance helpers
# ──────────────────────────────────────────────────────────────────────────────


def _row_standardize_matrix(weights: np.ndarray) -> np.ndarray:
    matrix = np.asarray(weights, dtype=float).copy()
    if matrix.ndim != 2:
        raise ValueError("weights must be a 2D matrix")
    np.fill_diagonal(matrix, 0.0)
    row_sums = np.sum(matrix, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return matrix / row_sums


def _resolve_maup_estimand(
    params: Mapping[str, Any],
) -> Literal[
    "direct",
    "spillover",
    "total",
    "dose_response",
    "policy_effect",
]:
    candidate = str(params.get("estimand", "spillover")).strip().lower()
    if candidate in {"direct", "spillover", "total", "dose_response", "policy_effect"}:
        return candidate  # type: ignore[return-value]
    return "spillover"


def _resolve_maup_effect_scale(
    params: Mapping[str, Any],
) -> Literal[
    "risk_difference",
    "mean_difference",
    "log_rr",
    "custom",
]:
    candidate = str(params.get("effect_scale", "mean_difference")).strip().lower()
    if candidate in {"risk_difference", "mean_difference", "log_rr", "custom"}:
        return candidate  # type: ignore[return-value]
    return "custom"


def _resolve_spatial_weights_for_maup(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
) -> tuple[np.ndarray | None, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if data.adjacency_matrix is not None:
        metadata["weight_source"] = "adjacency_matrix"
        return _row_standardize_matrix(np.asarray(data.adjacency_matrix, dtype=float)), metadata

    if data.coordinates is None:
        return None, metadata

    coords = np.asarray(data.coordinates[:, :2], dtype=float)
    bandwidth_param = params.get(
        "maup_bandwidth",
        spatial_result.exposure_mapping_params.get("bandwidth", params.get("bandwidth", "auto")),
    )
    if bandwidth_param == "auto":
        bandwidth = _auto_bandwidth(coords)
    else:
        try:
            bandwidth = float(bandwidth_param)
        except (TypeError, ValueError):
            bandwidth = _auto_bandwidth(coords)
    if not math.isfinite(bandwidth) or bandwidth <= 0.0:
        return None, metadata
    metadata["weight_source"] = "coordinates_kernel"
    metadata["bandwidth"] = bandwidth
    return _row_standardize_matrix(_kernel_weights(coords, bandwidth)), metadata


def _resolve_probe_covariates(
    covariates: np.ndarray | None,
    *,
    max_features: int,
) -> tuple[np.ndarray | None, tuple[str, ...]]:
    if covariates is None:
        return None, ()
    array = np.asarray(covariates, dtype=float)
    if array.ndim != 2 or array.shape[0] == 0:
        return None, ("maup_probe_covariates_invalid",)
    if max_features <= 0:
        return None, ()
    if array.shape[1] <= max_features:
        return array, ()
    return array[:, :max_features], ("maup_probe_covariates_truncated",)


def _linear_effect_probe(
    outcome: np.ndarray,
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    estimand: Literal["direct", "spillover", "total", "dose_response", "policy_effect"],
    covariates: np.ndarray | None = None,
    weights: np.ndarray | None = None,
) -> tuple[float | None, float | None]:
    y = np.asarray(outcome, dtype=float)
    a = np.asarray(treatment, dtype=float)
    e = np.asarray(exposure, dtype=float)
    X = np.column_stack([np.ones(y.shape[0], dtype=float), a, e])
    if covariates is not None:
        X = np.column_stack([X, np.asarray(covariates, dtype=float)])

    w = np.ones(y.shape[0], dtype=float) if weights is None else np.asarray(weights, dtype=float)
    finite_mask = np.isfinite(y) & np.isfinite(a) & np.isfinite(e) & np.isfinite(w) & (w > 0.0)
    if covariates is not None:
        finite_mask &= np.isfinite(np.asarray(covariates, dtype=float)).all(axis=1)
    if finite_mask.sum() <= X.shape[1]:
        return None, None

    y = y[finite_mask]
    X = X[finite_mask]
    w = w[finite_mask]
    if np.linalg.matrix_rank(X) < 3:
        return None, None

    sqrt_w = np.sqrt(w)
    Xw = X * sqrt_w[:, None]
    yw = y * sqrt_w
    xtx = Xw.T @ Xw
    xtx_inv = np.linalg.pinv(xtx)
    beta = xtx_inv @ (Xw.T @ yw)
    resid = y - X @ beta
    rw = resid * sqrt_w
    meat = Xw.T @ ((rw[:, None] ** 2) * Xw)
    scale = y.shape[0] / max(y.shape[0] - X.shape[1], 1)
    cov = xtx_inv @ meat @ xtx_inv * scale

    if estimand == "direct":
        effect = float(beta[1])
        variance = float(cov[1, 1])
    elif estimand in {"spillover", "dose_response"}:
        effect = float(beta[2])
        variance = float(cov[2, 2])
    else:
        effect = float(beta[1] + beta[2])
        variance = float(cov[1, 1] + cov[2, 2] + 2.0 * cov[1, 2])
    variance = max(variance, 0.0)
    return effect, math.sqrt(variance)


def _support_metrics(
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    estimand: Literal["direct", "spillover", "total", "dose_response", "policy_effect"],
    alpha_high: float,
    alpha_low: float,
    treatment_threshold: float,
) -> tuple[float | None, float | None]:
    n_obs = len(treatment)
    if n_obs == 0:
        return None, None
    high = np.asarray(exposure, dtype=float) >= alpha_high
    low = np.asarray(exposure, dtype=float) <= alpha_low
    treated = np.asarray(treatment, dtype=float) >= treatment_threshold
    control = np.asarray(treatment, dtype=float) <= (1.0 - treatment_threshold)
    if estimand == "direct":
        fractions = [float(np.mean(treated & high)), float(np.mean(control & high))]
    elif estimand in {"total", "policy_effect"}:
        fractions = [float(np.mean(treated & high)), float(np.mean(control & low))]
    else:
        fractions = [float(np.mean(high)), float(np.mean(low))]
    positivity = min(fractions) if fractions else None
    ess = None if positivity is None else float(n_obs * positivity)
    return positivity, ess


def _coerce_candidate_partition(
    raw_partition: Any,
    *,
    index: int,
    n_units: int,
) -> tuple[str, str | None, str | None, np.ndarray]:
    if isinstance(raw_partition, Mapping):
        partition_id = str(
            raw_partition.get("partition_id") or raw_partition.get("id") or f"partition_{index}"
        ).strip()
        scale_label = (
            None
            if raw_partition.get("scale_label") is None
            else str(raw_partition.get("scale_label")).strip()
        )
        zoning_label = (
            None
            if raw_partition.get("zoning_label") is None
            else str(raw_partition.get("zoning_label")).strip()
        )
        labels_raw = raw_partition.get("block_of_unit")
    else:
        partition_id = f"partition_{index}"
        scale_label = None
        zoning_label = None
        labels_raw = raw_partition
    if not partition_id:
        raise ValueError("partition_id must be non-empty")
    labels = np.asarray(labels_raw, dtype=int)
    if labels.ndim != 1 or labels.shape[0] != n_units:
        raise ValueError("block_of_unit must be a 1D array aligned to n_units")
    if np.unique(labels).size < 2:
        raise ValueError("partition must contain at least two non-empty blocks")
    return partition_id, scale_label, zoning_label, labels


def _make_averaging_operator(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    unique_labels, inverse = np.unique(labels, return_inverse=True)
    counts = np.bincount(inverse).astype(float)
    n_blocks = int(unique_labels.size)
    n_units = int(labels.shape[0])
    M = np.zeros((n_blocks, n_units), dtype=float)
    C = np.zeros((n_units, n_blocks), dtype=float)
    for unit_idx, block_idx in enumerate(inverse):
        M[block_idx, unit_idx] = 1.0 / counts[block_idx]
        C[unit_idx, block_idx] = 1.0
    return M, C, counts


def _aggregate_weight_matrix(M: np.ndarray, W: np.ndarray, C: np.ndarray) -> np.ndarray:
    return _row_standardize_matrix(M @ W @ C)


def compute_lumpability_residual(M: np.ndarray, W: np.ndarray, Wq: np.ndarray) -> float:
    left = M @ W
    denom = float(np.linalg.norm(left))
    if denom <= 1.0e-12:
        return 0.0
    return float(np.linalg.norm(left - (Wq @ M)) / denom)


def hausman_compare_partition_effects(
    theta_micro: float | None,
    se_micro: float | None,
    theta_partition: float | None,
    se_partition: float | None,
) -> tuple[float | None, float | None]:
    if theta_micro is None or se_micro is None or theta_partition is None or se_partition is None:
        return None, None
    if not all(
        math.isfinite(value) for value in (theta_micro, se_micro, theta_partition, se_partition)
    ):
        return None, None
    variance = se_micro**2 + se_partition**2
    if variance <= 0.0:
        return None, None
    statistic = (theta_partition - theta_micro) ** 2 / variance
    p_value = math.erfc(math.sqrt(statistic / 2.0))
    return float(statistic), float(p_value)


def _holm_adjust(p_values: list[float | None]) -> list[float | None]:
    adjusted: list[float | None] = [None] * len(p_values)
    ranked = sorted(
        (float(p_value), index)
        for index, p_value in enumerate(p_values)
        if p_value is not None and math.isfinite(p_value)
    )
    m = len(ranked)
    running_max = 0.0
    for rank, (p_value, index) in enumerate(ranked, start=1):
        candidate = min(1.0, (m - rank + 1) * p_value)
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return adjusted


def _flatten_unique_codes(
    sequences: list[tuple[str, ...]] | tuple[tuple[str, ...], ...],
) -> tuple[str, ...]:
    flattened: list[str] = []
    seen: set[str] = set()
    for sequence in sequences:
        for code in sequence:
            if code in seen:
                continue
            seen.add(code)
            flattened.append(code)
    return tuple(flattened)


def compute_maup_invariance_certificate(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
) -> MAUPInvarianceCertificate:
    estimand = _resolve_maup_estimand(params)
    effect_scale = _resolve_maup_effect_scale(params)
    alpha = float(params.get("maup_alpha", 0.05))
    lumpability_warn = float(params.get("lumpability_warn_threshold", 0.01))
    lumpability_block = float(params.get("lumpability_block_threshold", 0.05))
    ess_warn = float(params.get("min_cell_ess_warn", 50.0))
    ess_block = float(params.get("min_cell_ess_block", 20.0))
    positivity_block = float(
        params.get("min_cell_positivity_block", _MAUP_POSITIVITY_BLOCK_THRESHOLD)
    )

    certificate_warnings: list[str] = list(spatial_result.warnings)
    certificate_blockers: list[str] = []
    metadata: dict[str, Any] = {
        "report_status": spatial_result.status,
        "effect_scale": effect_scale,
        "effect_source": "weighted_linear_probe",
        "lumpability_warn_threshold": lumpability_warn,
        "lumpability_block_threshold": lumpability_block,
        "min_cell_ess_warn": ess_warn,
        "min_cell_ess_block": ess_block,
        "min_cell_positivity_block": positivity_block,
    }

    interaction_complex_ref, ref_warnings = _coerce_optional_artifact_ref(
        params.get("interaction_complex_ref", data.metadata.get("interaction_complex_ref")),
        field_name="interaction_complex_ref",
    )
    certificate_warnings.extend(ref_warnings)
    interference_certificate_ref, cert_ref_warnings = _coerce_optional_artifact_ref(
        params.get(
            "interference_certificate_ref",
            data.metadata.get("interference_certificate_ref"),
        ),
        field_name="interference_certificate_ref",
    )
    certificate_warnings.extend(cert_ref_warnings)

    if estimand not in _SUPPORTED_MAUP_ESTIMANDS:
        certificate_blockers.append("MAUP_E_UNSUPPORTED_EXPOSURE")
        certificate_warnings.append(f"Unsupported MAUP estimand '{estimand}'.")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if bool(
        params.get(
            "partitions_selected_post_outcome",
            data.metadata.get("partitions_selected_post_outcome", False),
        )
    ):
        certificate_blockers.append("MAUP_E_OUTCOME_LEAKAGE")
        certificate_warnings.append("Candidate partitions were flagged as post-outcome selections.")
        return MAUPInvarianceCertificate(
            status="block",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("block"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    try:
        candidate_partitions = _resolve_maup_partitions(data, params)
    except (TypeError, ValueError) as exc:
        certificate_blockers.append("MAUP_E_BAD_PARTITION")
        certificate_warnings.append(str(exc))
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if not candidate_partitions:
        certificate_warnings.append("candidate_partitions_missing")
        return MAUPInvarianceCertificate(
            status="not_tested",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_tested"),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    W, weight_metadata = _resolve_spatial_weights_for_maup(data, spatial_result, params)
    metadata["weight_metadata"] = weight_metadata
    if W is None:
        certificate_blockers.append("MAUP_E_NO_MICRODATA")
        certificate_warnings.append("spatial_weights_unavailable")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    max_covariates = max(0, int(params.get("maup_probe_max_covariates", 3)))
    probe_covariates, probe_warnings = _resolve_probe_covariates(
        data.covariates,
        max_features=max_covariates,
    )
    certificate_warnings.extend(probe_warnings)
    Y = np.asarray(data.outcome, dtype=float)
    A = np.asarray(data.treatment, dtype=float)
    exposure = W @ A
    metadata["max_probe_covariates"] = max_covariates
    micro_effect, micro_se = _linear_effect_probe(
        Y,
        A,
        exposure,
        estimand=estimand,
        covariates=probe_covariates,
    )
    alpha_high = float(
        spatial_result.effects.alpha_high
        if spatial_result.effects is not None
        else params.get("alpha_high", 0.5)
    )
    alpha_low = float(
        spatial_result.effects.alpha_low
        if spatial_result.effects is not None
        else params.get("alpha_low", 0.0)
    )
    treatment_threshold = float(params.get("treatment_threshold", 0.5))
    micro_positivity, micro_ess = _support_metrics(
        A,
        exposure,
        estimand=estimand,
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        treatment_threshold=treatment_threshold,
    )
    metadata["micro_positivity"] = micro_positivity
    metadata["micro_ess"] = micro_ess

    if micro_positivity is not None and micro_positivity < positivity_block:
        certificate_blockers.append("MAUP_E_POSITIVITY")
    if micro_ess is not None and micro_ess < ess_block:
        certificate_blockers.append("MAUP_E_LOW_ESS")
    elif micro_ess is not None and micro_ess < ess_warn:
        certificate_warnings.append("micro_ess_warn")

    if micro_effect is None or micro_se is None:
        certificate_blockers.append("MAUP_E_UNIDENTIFIED")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            micro_effect=micro_effect,
            micro_se=micro_se,
            partitions_tested=0,
            min_positivity=micro_positivity,
            min_ess=micro_ess,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    raw_checks: list[MAUPPartitionCheck] = []
    partition_positivities: list[float] = []
    p_values: list[float | None] = []
    for index, raw_partition in enumerate(candidate_partitions):
        try:
            partition = (
                dict(raw_partition)
                if isinstance(raw_partition, Mapping)
                else {"block_of_unit": raw_partition}
            )
            partition_id = (
                str(partition.get("partition_id", f"partition_{index}")).strip()
                or f"partition_{index}"
            )
            scale_label = (
                None if partition.get("scale_label") is None else str(partition.get("scale_label"))
            )
            zoning_label = (
                None
                if partition.get("zoning_label") is None
                else str(partition.get("zoning_label"))
            )
            labels, unique_labels = _normalize_partition_labels(
                partition.get("block_of_unit"),
                n_units=data.n_units,
            )
        except ValueError as exc:
            raw_checks.append(
                MAUPPartitionCheck(
                    partition_id=f"partition_{index}",
                    n_blocks=0,
                    lumpability_residual=None,
                    exact_lumpable=None,
                    blocker_codes=("MAUP_E_BAD_PARTITION",),
                    warnings=(str(exc),),
                )
            )
            p_values.append(None)
            continue

        M, incidence = _partition_operators(labels)
        counts = np.sum(incidence, axis=1).astype(float)
        Wq = _aggregate_weight_matrix(M, W, incidence.T)
        residual = compute_lumpability_residual(M, W, Wq)
        Y_block = M @ Y
        A_block = M @ A
        exposure_block = Wq @ A_block
        cov_block = None if probe_covariates is None else M @ probe_covariates
        theta_partition, se_partition = _linear_effect_probe(
            Y_block,
            A_block,
            exposure_block,
            estimand=estimand,
            covariates=cov_block,
            weights=counts,
        )
        hausman_stat, p_value = hausman_compare_partition_effects(
            micro_effect,
            micro_se,
            theta_partition,
            se_partition,
        )
        positivity, ess = _support_metrics(
            A_block,
            exposure_block,
            estimand=estimand,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            treatment_threshold=treatment_threshold,
        )
        partition_blockers: list[str] = []
        partition_warnings: list[str] = []
        if residual >= lumpability_block:
            partition_blockers.append("MAUP_E_STRUCTURAL_NONINVARIANCE")
        elif residual >= lumpability_warn:
            partition_warnings.append("lumpability_residual_warn")
        if theta_partition is None or se_partition is None:
            partition_blockers.append("MAUP_E_UNIDENTIFIED")
        if p_value is None and theta_partition is not None:
            partition_blockers.append("MAUP_E_SINGULAR_COV")
        if positivity is not None and positivity < positivity_block:
            partition_blockers.append("MAUP_E_POSITIVITY")
        if ess is not None and ess < ess_block:
            partition_blockers.append("MAUP_E_LOW_ESS")
        elif ess is not None and ess < ess_warn:
            partition_warnings.append("ess_warn")
        if positivity is not None:
            partition_positivities.append(float(positivity))

        raw_checks.append(
            MAUPPartitionCheck(
                partition_id=partition_id,
                n_blocks=len(unique_labels),
                scale_label=scale_label,
                zoning_label=zoning_label,
                lumpability_residual=residual,
                exact_lumpable=residual <= 1.0e-12,
                theta_partition=theta_partition,
                se_partition=se_partition,
                hausman_stat=hausman_stat,
                p_value=p_value,
                ess_min=ess,
                blocker_codes=tuple(partition_blockers),
                warnings=tuple(partition_warnings),
            )
        )
        p_values.append(p_value)

    adjusted_p_values = _holm_adjust(p_values)
    checks: list[MAUPPartitionCheck] = []
    for check, adjusted_p_value in zip(raw_checks, adjusted_p_values, strict=True):
        blocker_codes = list(check.blocker_codes)
        warnings = list(check.warnings)
        if adjusted_p_value is not None and adjusted_p_value < alpha:
            blocker_codes.append("MAUP_E_STATISTICAL_NONINVARIANCE")
        checks.append(
            check.model_copy(
                update={
                    "adjusted_p_value": adjusted_p_value,
                    "blocker_codes": _flatten_unique_codes((tuple(blocker_codes),)),
                    "warnings": _flatten_unique_codes((tuple(warnings),)),
                }
            )
        )

    max_residual = max(
        (check.lumpability_residual for check in checks if check.lumpability_residual is not None),
        default=None,
    )
    min_adjusted_p = min(
        (check.adjusted_p_value for check in checks if check.adjusted_p_value is not None),
        default=None,
    )
    min_ess = min((check.ess_min for check in checks if check.ess_min is not None), default=None)

    report_effect_reference = None
    if spatial_result.effects is not None:
        if estimand == "direct":
            report_effect_reference = spatial_result.effects.direct_effect
        elif estimand in {"spillover", "dose_response"}:
            report_effect_reference = spatial_result.effects.spillover_effect
        else:
            report_effect_reference = spatial_result.effects.total_effect

    metadata["report_effect_reference"] = report_effect_reference

    positivity_values: list[float] = []
    if micro_positivity is not None:
        positivity_values.append(float(micro_positivity))
    positivity_values.extend(partition_positivities)
    min_positivity = min(positivity_values) if positivity_values else None
    if micro_ess is not None:
        min_ess = micro_ess if min_ess is None else min(min_ess, micro_ess)

    blocker_codes = _flatten_unique_codes(
        (tuple(certificate_blockers),) + tuple(check.blocker_codes for check in checks)
    )
    warnings = _flatten_unique_codes(
        (tuple(certificate_warnings),) + tuple(check.warnings for check in checks)
    )

    hard_block_codes = {
        "MAUP_E_OUTCOME_LEAKAGE",
        "MAUP_E_STRUCTURAL_NONINVARIANCE",
        "MAUP_E_STATISTICAL_NONINVARIANCE",
        "MAUP_E_POSITIVITY",
        "MAUP_E_LOW_ESS",
        "MAUP_E_SINGULAR_COV",
        "MAUP_E_BAD_PARTITION",
    }
    status: Literal["pass", "warn", "block", "not_tested", "not_identified"]
    if any(code in hard_block_codes for code in blocker_codes):
        status = "block"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    exact_invariance = (
        status == "pass"
        and len(checks) > 0
        and all(check.exact_lumpable is True for check in checks)
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
    )
    near_invariance = (
        status in {"pass", "warn"}
        and len(checks) > 0
        and (max_residual is None or max_residual < lumpability_block)
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
        and (min_ess is None or min_ess >= ess_block)
        and (min_positivity is None or min_positivity >= positivity_block)
    )

    return MAUPInvarianceCertificate(
        status=status,
        estimand=estimand,
        effect_scale=effect_scale,
        micro_effect=micro_effect,
        micro_se=micro_se,
        partitions_tested=len(checks),
        max_lumpability_residual=max_residual,
        min_adjusted_p_value=min_adjusted_p,
        min_positivity=min_positivity,
        min_ess=min_ess,
        exact_invariance=exact_invariance,
        near_invariance=near_invariance or exact_invariance,
        recommended_mode=_recommended_maup_mode(status),
        partition_checks=tuple(checks),
        blocker_codes=blocker_codes,
        warnings=warnings,
        interaction_complex_ref=interaction_complex_ref,
        interference_certificate_ref=interference_certificate_ref,
        metadata=metadata,
    )


_SUPPORTED_HODGE_AGGREGATION_RULES = {
    "mean",
    "sum",
    "rate",
    "population_weighted_mean",
}


def _normalize_hodge_aggregation_rule(rule: Any) -> str:
    candidate = str(rule or "mean").strip().lower()
    aliases = {
        "avg": "mean",
        "average": "mean",
        "weighted_mean": "population_weighted_mean",
        "population-weighted-mean": "population_weighted_mean",
        "population weighted mean": "population_weighted_mean",
    }
    normalized = aliases.get(candidate, candidate)
    if normalized not in _SUPPORTED_HODGE_AGGREGATION_RULES:
        return "mean"
    return normalized


def _stable_payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.blake2b(encoded, digest_size=16).hexdigest()


def _hash_float_array(values: np.ndarray) -> str:
    array = np.asarray(values)
    if array.dtype.kind in {"f", "c"}:
        array = np.round(array.astype(float), 8)
    return hashlib.blake2b(array.tobytes(), digest_size=16).hexdigest()


def _resolve_weight_spec_label(
    spatial_result: NetworkInterferenceReport,
    weight_metadata: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    suffix: str | None = None,
) -> str:
    candidate = (
        str(params.get("weight_spec", "")).strip()
        or str(weight_metadata.get("weight_spec", "")).strip()
        or str(weight_metadata.get("weight_source", "")).strip()
        or spatial_result.exposure_mapping.value
    )
    if suffix:
        return f"{candidate}:{suffix}"
    return candidate


def _aggregate_partition_array(
    values: np.ndarray | None,
    labels: np.ndarray,
    *,
    rule: str,
    unit_weights: np.ndarray | None = None,
) -> np.ndarray | None:
    if values is None:
        return None
    array = np.asarray(values, dtype=float)
    inverse = np.asarray(labels, dtype=int)
    if array.ndim not in {1, 2}:
        raise ValueError("values must be a 1D or 2D array for partition aggregation")
    n_blocks = int(np.max(inverse)) + 1
    if unit_weights is None:
        weights = np.ones(inverse.shape[0], dtype=float)
    else:
        weights = np.asarray(unit_weights, dtype=float)
        if weights.shape != inverse.shape:
            raise ValueError("unit_weights must align with labels")
        if not np.isfinite(weights).all():
            raise ValueError("unit_weights must be finite")
    normalized_rule = _normalize_hodge_aggregation_rule(rule)

    if array.ndim == 1:
        weighted_values = (
            array * weights if normalized_rule == "population_weighted_mean" else array
        )
        totals = np.bincount(inverse, weights=weighted_values, minlength=n_blocks).astype(float)
        if normalized_rule == "sum":
            return totals
        block_weights = np.bincount(inverse, weights=weights, minlength=n_blocks).astype(float)
        if normalized_rule in {"mean", "rate"}:
            block_weights = np.bincount(inverse, minlength=n_blocks).astype(float)
        block_weights = np.clip(block_weights, 1.0, None)
        return totals / block_weights

    totals = np.zeros((n_blocks, array.shape[1]), dtype=float)
    for feature_idx in range(array.shape[1]):
        column = (
            array[:, feature_idx] * weights
            if normalized_rule == "population_weighted_mean"
            else array[:, feature_idx]
        )
        totals[:, feature_idx] = np.bincount(
            inverse,
            weights=column,
            minlength=n_blocks,
        ).astype(float)
    if normalized_rule == "sum":
        return totals
    block_weights = np.bincount(inverse, weights=weights, minlength=n_blocks).astype(float)
    if normalized_rule in {"mean", "rate"}:
        block_weights = np.bincount(inverse, minlength=n_blocks).astype(float)
    block_weights = np.clip(block_weights, 1.0, None)
    return totals / block_weights[:, None]


def _dominant_hodge_component(
    eta_grad: float,
    eta_curl: float,
    eta_harm: float,
) -> Literal["grad", "curl", "harm", "mixed"]:
    components = {
        "grad": float(eta_grad),
        "curl": float(eta_curl),
        "harm": float(eta_harm),
    }
    winner, value = max(components.items(), key=lambda item: item[1])
    if value <= 0.5:
        return "mixed"
    return winner  # type: ignore[return-value]


def _build_edge_incidence(
    weights: np.ndarray,
    *,
    edge_tol: float = 1.0e-10,
) -> tuple[tuple[tuple[int, int], ...], dict[tuple[int, int], int], np.ndarray, np.ndarray]:
    W = np.asarray(weights, dtype=float)
    support = (np.abs(W) > edge_tol) | (np.abs(W.T) > edge_tol)
    np.fill_diagonal(support, False)
    n_nodes = int(W.shape[0])
    edges: list[tuple[int, int]] = []
    edge_lookup: dict[tuple[int, int], int] = {}
    for src in range(n_nodes - 1):
        for dst in range(src + 1, n_nodes):
            if support[src, dst]:
                edge_lookup[(src, dst)] = len(edges)
                edges.append((src, dst))
    incidence = np.zeros((n_nodes, len(edges)), dtype=float)
    for edge_idx, (src, dst) in enumerate(edges):
        incidence[src, edge_idx] = -1.0
        incidence[dst, edge_idx] = 1.0
    return tuple(edges), edge_lookup, incidence, support


def _enumerate_triangles(
    support: np.ndarray,
    *,
    max_triangles: int,
) -> tuple[tuple[tuple[int, int, int], ...], tuple[str, ...]]:
    n_nodes = int(support.shape[0])
    neighbor_sets = [set(np.flatnonzero(support[node]).tolist()) for node in range(n_nodes)]
    triangles: list[tuple[int, int, int]] = []
    warnings: list[str] = []
    for i in range(n_nodes - 2):
        for j in sorted(neighbor for neighbor in neighbor_sets[i] if neighbor > i):
            common = sorted(node for node in (neighbor_sets[i] & neighbor_sets[j]) if node > j)
            for k in common:
                triangles.append((i, j, k))
                if len(triangles) >= max_triangles:
                    warnings.append("hodge_triangle_limit_applied")
                    return tuple(triangles), tuple(warnings)
    return tuple(triangles), tuple(warnings)


def _build_triangle_incidence(
    edge_lookup: Mapping[tuple[int, int], int],
    triangles: tuple[tuple[int, int, int], ...],
    *,
    n_edges: int,
) -> np.ndarray:
    if not triangles:
        return np.zeros((n_edges, 0), dtype=float)
    incidence = np.zeros((n_edges, len(triangles)), dtype=float)
    for triangle_idx, (i, j, k) in enumerate(triangles):
        incidence[edge_lookup[(i, j)], triangle_idx] = 1.0
        incidence[edge_lookup[(j, k)], triangle_idx] = 1.0
        incidence[edge_lookup[(i, k)], triangle_idx] = -1.0
    return incidence


def _edge_flow_from_scores(
    weights: np.ndarray,
    scores: np.ndarray,
    edges: tuple[tuple[int, int], ...],
) -> np.ndarray:
    W = np.asarray(weights, dtype=float)
    theta = np.asarray(scores, dtype=float)
    flow = np.zeros(len(edges), dtype=float)
    for edge_idx, (src, dst) in enumerate(edges):
        flow[edge_idx] = W[src, dst] * theta[src] - W[dst, src] * theta[dst]
    return flow


def _project_gradient_component(B1: np.ndarray, flow: np.ndarray) -> np.ndarray:
    if B1.size == 0 or flow.size == 0:
        return np.zeros_like(flow)
    laplacian_0 = B1 @ B1.T
    alpha = np.linalg.pinv(laplacian_0) @ (B1 @ flow)
    return B1.T @ alpha


def _project_curl_component(B2: np.ndarray, flow: np.ndarray) -> np.ndarray:
    if B2.size == 0 or flow.size == 0:
        return np.zeros_like(flow)
    laplacian_2 = B2.T @ B2
    beta = np.linalg.pinv(laplacian_2) @ (B2.T @ flow)
    return B2 @ beta


def _compute_zone_spillover_score(
    outcome: np.ndarray,
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    covariates: np.ndarray | None,
) -> tuple[np.ndarray, dict[str, float | None], tuple[str, ...]]:
    warnings: list[str] = []
    spillover_effect, spillover_se = _linear_effect_probe(
        outcome,
        treatment,
        exposure,
        estimand="spillover",
        covariates=covariates,
    )
    direct_effect, direct_se = _linear_effect_probe(
        outcome,
        treatment,
        exposure,
        estimand="direct",
        covariates=covariates,
    )
    centered_exposure = np.asarray(exposure, dtype=float) - float(np.mean(exposure))
    centered_treatment = np.asarray(treatment, dtype=float) - float(np.mean(treatment))

    theta = centered_exposure.copy()
    if spillover_effect is None or not math.isfinite(spillover_effect):
        warnings.append("spillover_probe_unidentified")
    else:
        theta = spillover_effect * centered_exposure

    if float(np.linalg.norm(theta)) <= 1.0e-12:
        if direct_effect is not None and math.isfinite(direct_effect):
            theta = direct_effect * centered_treatment
            warnings.append("spillover_probe_flat_fallback_to_direct")
        else:
            theta = centered_exposure
            warnings.append("spillover_probe_flat_unscaled")

    return (
        theta,
        {
            "spillover_effect": spillover_effect,
            "spillover_se": spillover_se,
            "direct_effect": direct_effect,
            "direct_se": direct_se,
        },
        tuple(warnings),
    )


def _build_spatial_hodge_profile(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    weights: np.ndarray,
    covariates: np.ndarray | None,
    labels: np.ndarray,
    scale_id: str,
    zoning_id: str,
    aggregation_rule: str,
    weight_spec: str,
    support_level: str,
    max_triangles: int,
) -> SpatialHodgeScaleProfile:
    exposure = np.asarray(weights, dtype=float) @ np.asarray(treatment, dtype=float)
    theta, probe_metadata, probe_warnings = _compute_zone_spillover_score(
        np.asarray(outcome, dtype=float),
        np.asarray(treatment, dtype=float),
        exposure,
        covariates=None if covariates is None else np.asarray(covariates, dtype=float),
    )

    edges, edge_lookup, B1, support = _build_edge_incidence(weights)
    flow = _edge_flow_from_scores(weights, theta, edges)
    gradient = _project_gradient_component(B1, flow)
    triangles, triangle_warnings = _enumerate_triangles(support, max_triangles=max_triangles)
    B2 = _build_triangle_incidence(edge_lookup, triangles, n_edges=len(edges))
    curl = _project_curl_component(B2, flow)
    harmonic = flow - gradient - curl

    total_energy = float(np.dot(flow, flow))
    gradient_energy = float(np.dot(gradient, gradient))
    curl_energy = float(np.dot(curl, curl))
    harmonic_energy = float(np.dot(harmonic, harmonic))
    warnings: list[str] = list(probe_warnings) + list(triangle_warnings)
    if total_energy <= 1.0e-12:
        warnings.append("degenerate_edge_flow")
        eta_grad = 0.0
        eta_curl = 0.0
        eta_harm = 0.0
    else:
        eta_grad = gradient_energy / total_energy
        eta_curl = curl_energy / total_energy
        eta_harm = harmonic_energy / total_energy

    return SpatialHodgeScaleProfile(
        scale_id=scale_id,
        zoning_id=zoning_id,
        aggregation_rule=aggregation_rule,
        weight_spec=weight_spec,
        zoning_hash=_hash_float_array(np.asarray(labels, dtype=float)),
        weight_hash=_hash_float_array(np.asarray(weights, dtype=float)),
        aggregation_hash=_stable_payload_hash({"aggregation_rule": aggregation_rule}),
        n_zones=int(np.asarray(treatment, dtype=float).shape[0]),
        n_edges=len(edges),
        n_triangles=len(triangles),
        total_energy=total_energy,
        gradient_energy=gradient_energy,
        curl_energy=curl_energy,
        harmonic_energy=harmonic_energy,
        eta_grad=eta_grad,
        eta_curl=eta_curl,
        eta_harm=eta_harm,
        dominant_component=_dominant_hodge_component(eta_grad, eta_curl, eta_harm),
        warnings=_flatten_unique_codes((tuple(warnings),)),
        metadata={
            "support_level": support_level,
            "mean_exposure": float(np.mean(exposure)),
            "std_exposure": float(np.std(exposure)),
            "max_abs_flow": float(np.max(np.abs(flow))) if flow.size else 0.0,
            **probe_metadata,
        },
    )


def _profile_l1_gap(
    left: SpatialHodgeScaleProfile,
    right: SpatialHodgeScaleProfile,
) -> float:
    return float(
        abs(left.eta_grad - right.eta_grad)
        + abs(left.eta_curl - right.eta_curl)
        + abs(left.eta_harm - right.eta_harm)
    )


def _summarize_spatial_hodge_diagnostics(
    diagnostics: SpatialHodgeDiagnostics,
) -> dict[str, Any]:
    return {
        "declared_scale_id": diagnostics.declared_scale_id,
        "declared_zoning_id": diagnostics.declared_zoning_id,
        "aggregation_rule": diagnostics.aggregation_rule,
        "weight_spec": diagnostics.weight_spec,
        "zoning_hash": diagnostics.zoning_hash,
        "weight_hash": diagnostics.weight_hash,
        "aggregation_hash": diagnostics.aggregation_hash,
        "eta_grad": diagnostics.eta_grad,
        "eta_curl": diagnostics.eta_curl,
        "eta_harm": diagnostics.eta_harm,
        "dominant_component": diagnostics.dominant_component,
        "max_profile_l1_gap": diagnostics.max_profile_l1_gap,
        "scale_instability": diagnostics.scale_instability,
        "zoning_instability": diagnostics.zoning_instability,
        "topology_sensitivity": diagnostics.topology_sensitivity,
        "candidate_partition_ids": list(diagnostics.candidate_partition_ids),
        "warnings": list(diagnostics.warnings),
        "blocker_codes": list(diagnostics.blocker_codes),
    }


def compute_spatial_hodge_diagnostics(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
) -> SpatialHodgeDiagnostics | None:
    W, weight_metadata = _resolve_spatial_weights_for_maup(data, spatial_result, params)
    if W is None:
        return None

    raw_aggregation_rule = params.get("aggregation_rule", data.metadata.get("aggregation_rule"))
    aggregation_rule = _normalize_hodge_aggregation_rule(raw_aggregation_rule)
    declared_scale_id = (
        str(params.get("scale_id", data.metadata.get("scale_id", "declared"))).strip() or "declared"
    )
    declared_zoning_id = (
        str(params.get("zoning_id", data.metadata.get("zoning_id", "observed_support"))).strip()
        or "observed_support"
    )
    max_triangles = max(1, int(params.get("hodge_max_triangles", 4096)))
    weight_spec = _resolve_weight_spec_label(spatial_result, weight_metadata, params)

    warnings: list[str] = []
    raw_aggregation_label = None if raw_aggregation_rule is None else str(raw_aggregation_rule)
    if (
        raw_aggregation_label is not None
        and aggregation_rule != raw_aggregation_label.strip().lower()
    ):
        warnings.append("aggregation_rule_normalized_to_mean")

    micro_labels = np.arange(data.n_units, dtype=int)
    profiles: list[SpatialHodgeScaleProfile] = [
        _build_spatial_hodge_profile(
            outcome=np.asarray(data.outcome, dtype=float),
            treatment=np.asarray(data.treatment, dtype=float),
            weights=np.asarray(W, dtype=float),
            covariates=None
            if data.covariates is None
            else np.asarray(data.covariates, dtype=float),
            labels=micro_labels,
            scale_id=declared_scale_id,
            zoning_id=declared_zoning_id,
            aggregation_rule=aggregation_rule,
            weight_spec=weight_spec,
            support_level="declared",
            max_triangles=max_triangles,
        )
    ]

    unit_weights_raw = params.get("aggregation_weights", data.metadata.get("aggregation_weights"))
    unit_weights = None if unit_weights_raw is None else np.asarray(unit_weights_raw, dtype=float)
    candidate_partition_ids: list[str] = []
    try:
        candidate_partitions = _resolve_maup_partitions(data, params)
    except (TypeError, ValueError) as exc:
        candidate_partitions = ()
        warnings.append(f"candidate_partitions_invalid:{exc}")

    for index, raw_partition in enumerate(candidate_partitions):
        try:
            partition_id, scale_label, zoning_label, labels = _coerce_candidate_partition(
                raw_partition,
                index=index,
                n_units=data.n_units,
            )
        except ValueError as exc:
            warnings.append(f"invalid_partition_skipped:{index}:{exc}")
            continue
        candidate_partition_ids.append(partition_id)
        partition_rule = _normalize_hodge_aggregation_rule(
            raw_partition.get("aggregation_rule", aggregation_rule)
            if isinstance(raw_partition, Mapping)
            else aggregation_rule
        )
        M, C, _ = _make_averaging_operator(labels)
        Wq = _aggregate_weight_matrix(M, W, C)
        aggregated_outcome = _aggregate_partition_array(
            np.asarray(data.outcome, dtype=float),
            labels,
            rule=partition_rule,
            unit_weights=unit_weights,
        )
        aggregated_treatment = _aggregate_partition_array(
            np.asarray(data.treatment, dtype=float),
            labels,
            rule=partition_rule,
            unit_weights=unit_weights,
        )
        aggregated_covariates = (
            None
            if data.covariates is None
            else _aggregate_partition_array(
                np.asarray(data.covariates, dtype=float),
                labels,
                rule=partition_rule,
                unit_weights=unit_weights,
            )
        )
        profiles.append(
            _build_spatial_hodge_profile(
                outcome=np.asarray(aggregated_outcome, dtype=float),
                treatment=np.asarray(aggregated_treatment, dtype=float),
                weights=Wq,
                covariates=(
                    None
                    if aggregated_covariates is None
                    else np.asarray(aggregated_covariates, dtype=float)
                ),
                labels=np.asarray(labels, dtype=int),
                scale_id=scale_label or f"{declared_scale_id}:{partition_id}",
                zoning_id=zoning_label or partition_id,
                aggregation_rule=partition_rule,
                weight_spec=_resolve_weight_spec_label(
                    spatial_result,
                    weight_metadata,
                    params,
                    suffix=f"aggregate:{partition_id}",
                ),
                support_level="aggregate",
                max_triangles=max_triangles,
            )
        )

    pairwise_gaps: list[tuple[float, SpatialHodgeScaleProfile, SpatialHodgeScaleProfile]] = []
    for left_idx in range(len(profiles) - 1):
        for right_idx in range(left_idx + 1, len(profiles)):
            gap = _profile_l1_gap(profiles[left_idx], profiles[right_idx])
            pairwise_gaps.append((gap, profiles[left_idx], profiles[right_idx]))

    max_profile_l1_gap = max((gap for gap, _, _ in pairwise_gaps), default=0.0)
    scale_instability = max(
        (gap for gap, left, right in pairwise_gaps if left.scale_id != right.scale_id),
        default=0.0,
    )
    zoning_instability = max(
        (
            gap
            for gap, left, right in pairwise_gaps
            if left.zoning_id != right.zoning_id and left.scale_id == right.scale_id
        ),
        default=0.0,
    )

    symmetric_weights = _row_standardize_matrix(0.5 * (W + W.T))
    topology_probe = _build_spatial_hodge_profile(
        outcome=np.asarray(data.outcome, dtype=float),
        treatment=np.asarray(data.treatment, dtype=float),
        weights=symmetric_weights,
        covariates=None if data.covariates is None else np.asarray(data.covariates, dtype=float),
        labels=micro_labels,
        scale_id=declared_scale_id,
        zoning_id=declared_zoning_id,
        aggregation_rule=aggregation_rule,
        weight_spec=_resolve_weight_spec_label(
            spatial_result,
            weight_metadata,
            params,
            suffix="symmetric_probe",
        ),
        support_level="topology_probe",
        max_triangles=max_triangles,
    )
    topology_sensitivity = _profile_l1_gap(profiles[0], topology_probe)

    blocker_codes: list[str] = []
    if max_profile_l1_gap >= 1.0:
        blocker_codes.append("HODGE_E_STRONG_MAUP_INSTABILITY")
    if topology_sensitivity >= 1.0:
        blocker_codes.append("HODGE_E_TOPOLOGY_SENSITIVE")

    warnings.extend(warning for profile in profiles for warning in profile.warnings)
    warnings.extend(topology_probe.warnings)

    declared_profile = profiles[0]
    return SpatialHodgeDiagnostics(
        declared_scale_id=declared_scale_id,
        declared_zoning_id=declared_zoning_id,
        aggregation_rule=aggregation_rule,
        weight_spec=weight_spec,
        exposure_mapping=spatial_result.exposure_mapping.value,
        zoning_hash=declared_profile.zoning_hash,
        weight_hash=declared_profile.weight_hash,
        aggregation_hash=declared_profile.aggregation_hash,
        eta_grad=declared_profile.eta_grad,
        eta_curl=declared_profile.eta_curl,
        eta_harm=declared_profile.eta_harm,
        dominant_component=declared_profile.dominant_component,
        max_profile_l1_gap=max_profile_l1_gap,
        scale_instability=scale_instability,
        zoning_instability=zoning_instability,
        topology_sensitivity=topology_sensitivity,
        candidate_partition_ids=tuple(candidate_partition_ids),
        profiles=tuple(profiles),
        blocker_codes=_flatten_unique_codes((tuple(blocker_codes),)),
        warnings=_flatten_unique_codes((tuple(warnings),)),
        metadata={
            "weight_metadata": dict(weight_metadata),
            "topology_probe": {
                "weight_spec": topology_probe.weight_spec,
                "eta_grad": topology_probe.eta_grad,
                "eta_curl": topology_probe.eta_curl,
                "eta_harm": topology_probe.eta_harm,
                "dominant_component": topology_probe.dominant_component,
            },
            "profile_count": len(profiles),
            "candidate_partition_count": len(candidate_partition_ids),
            "areal_support": str(
                params.get("areal_support", data.metadata.get("areal_support", "observed_units"))
            ),
        },
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
    n_clusters = len(clusters)
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
        in_stratum = (a_val == A) & (np.abs(f - alpha) <= alpha_bw)
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
            "Some alpha-strata have fewer than 2 observations; estimates may be unreliable."
        )

    # Fallback: simple cluster-level means when strata are sparse
    def _fallback_mean(a_val: float) -> float:
        mask = a_val == A
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
        cluster_means = np.array([scores[c == C].mean() for c in clusters], dtype=float)
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
        stratum = (a_val == A) & (e_indicator > 0)
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
        return math.sqrt(s1**2 + s2**2)

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
    compute_maup = bool(params.get("compute_maup_certificate", False))
    compute_hodge = bool(params.get("compute_hodge_diagnostics", compute_maup))

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
        base_report = _build_report_failure(
            InterferenceMethod.SPATIAL_KERNEL,
            ExposureMappingType.KERNEL,
            n,
            n_treated,
            "coordinates or adjacency_matrix required for SpatialInterferenceEstimator",
        )
        certificate = (
            compute_maup_invariance_certificate(data, base_report, params) if compute_maup else None
        )
        diagnostics = (
            compute_spatial_hodge_diagnostics(data, base_report, params) if compute_hodge else None
        )
        return {
            "result": SpatialResult(
                **base_report.model_dump(mode="python"),
                maup_invariance_certificate=certificate,
                spatial_hodge_diagnostics=diagnostics,
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
            base_report = _build_report_failure(
                InterferenceMethod.SPATIAL_KERNEL,
                ExposureMappingType.KERNEL,
                n,
                n_treated,
                f"bandwidth must be positive, got {bw}",
            )
            certificate = (
                compute_maup_invariance_certificate(data, base_report, params)
                if compute_maup
                else None
            )
            diagnostics = (
                compute_spatial_hodge_diagnostics(data, base_report, params)
                if compute_hodge
                else None
            )
            return {
                "result": SpatialResult(
                    **base_report.model_dump(mode="python"),
                    maup_invariance_certificate=certificate,
                    spatial_hodge_diagnostics=diagnostics,
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
        stratum = (a_val == A) & (e_ind > 0)
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
        return math.sqrt(s1**2 + s2**2)

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

    base_report = _build_report_success(
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
    diagnostics = (
        compute_spatial_hodge_diagnostics(data, base_report, params) if compute_hodge else None
    )
    certificate = (
        compute_maup_invariance_certificate(data, base_report, params) if compute_maup else None
    )
    if diagnostics is not None:
        summary = _summarize_spatial_hodge_diagnostics(diagnostics)
        updated_metadata = dict(base_report.metadata)
        updated_metadata["spatial_hodge_summary"] = summary
        updated_metadata["spatial_hodge_diagnostics"] = diagnostics.model_dump(mode="python")
        base_report = base_report.model_copy(update={"metadata": updated_metadata})
    if certificate is not None and diagnostics is not None:
        certificate_metadata = dict(certificate.metadata)
        certificate_metadata.setdefault("zoning_hash", diagnostics.zoning_hash)
        certificate_metadata.setdefault("weight_hash", diagnostics.weight_hash)
        certificate_metadata.setdefault("aggregation_hash", diagnostics.aggregation_hash)
        certificate_metadata.setdefault("max_profile_l1_gap", diagnostics.max_profile_l1_gap)
        certificate_metadata.setdefault("scale_instability", diagnostics.scale_instability)
        certificate_metadata.setdefault("zoning_instability", diagnostics.zoning_instability)
        certificate_metadata.setdefault("topology_sensitivity", diagnostics.topology_sensitivity)
        certificate = certificate.model_copy(update={"metadata": certificate_metadata})
    return {
        "result": SpatialResult(
            **base_report.model_dump(mode="python"),
            maup_invariance_certificate=certificate,
            spatial_hodge_diagnostics=diagnostics,
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
        mu_high_val = (
            float(Y[outcome_mask & e_high.astype(bool)].mean())
            if (outcome_mask & e_high.astype(bool)).sum() > 0
            else 0.0
        )
        mu_low_val = (
            float(Y[outcome_mask & e_low.astype(bool)].mean())
            if (outcome_mask & e_low.astype(bool)).sum() > 0
            else 0.0
        )
        if math.isnan(mu_high):
            mu_high, se_high = mu_high_val, 0.0
        if math.isnan(mu_low):
            mu_low, se_low = mu_low_val, 0.0

    # In bipartite setting: direct effect = contrast in aggregate exposure
    # (no "own treatment" for outcome units)
    de = mu_high - mu_low
    se_val = mu_high - mu_low  # spillover ≡ aggregate exposure contrast
    te = de

    se_de = (
        math.sqrt(se_high**2 + se_low**2)
        if math.isfinite(se_high) and math.isfinite(se_low)
        else float("nan")
    )
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
            "positivity": ("P(A_i=a, f_i≈α | X_i) > 0 for all a ∈ {0,1} and α ∈ {α_low, α_high}."),
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
            ParameterSpec(
                name="compute_maup_certificate",
                default=False,
                description="When true, attach a MAUP invariance certificate using candidate_partitions.",
            ),
            ParameterSpec(
                name="compute_hodge_diagnostics",
                default=False,
                description=(
                    "When true, attach multiscale graph-Hodge diagnostics for declared and "
                    "candidate areal supports."
                ),
            ),
            ParameterSpec(
                name="candidate_partitions",
                default=(),
                description="Optional zoning schemes used for MAUP invariance checks.",
            ),
            ParameterSpec(name="scale_id", default="declared"),
            ParameterSpec(name="zoning_id", default="observed_support"),
            ParameterSpec(name="aggregation_rule", default="mean"),
            ParameterSpec(name="weight_spec", default=None),
            ParameterSpec(name="estimand", default="spillover"),
            ParameterSpec(name="effect_scale", default="mean_difference"),
            ParameterSpec(name="maup_alpha", default=0.05),
            ParameterSpec(name="maup_bandwidth", default=None),
            ParameterSpec(name="maup_probe_max_covariates", default=3),
            ParameterSpec(name="hodge_max_triangles", default=4096),
            ParameterSpec(name="treatment_threshold", default=0.5),
            ParameterSpec(name="lumpability_warn_threshold", default=0.01),
            ParameterSpec(name="lumpability_block_threshold", default=0.05),
            ParameterSpec(name="min_cell_ess_warn", default=50),
            ParameterSpec(name="min_cell_ess_block", default=20),
            ParameterSpec(name="min_cell_positivity_block", default=0.01),
            ParameterSpec(name="partitions_selected_post_outcome", default=False),
            ParameterSpec(name="interaction_complex_ref", default=None),
            ParameterSpec(name="interference_certificate_ref", default=None),
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
            "high/low kernel-exposure strata. Optional MAUP and multiscale "
            "Hodge diagnostics surface scale/zoning dependence on aggregated areas."
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
            "high-treatment neighbourhood vs a low-treatment neighbourhood. "
            "When compute_maup_certificate=true, the result also reports whether "
            "the spatial effect is stable across declared alternative partitions. "
            "When compute_hodge_diagnostics=true, the result also reports gradient/curl/"
            "harmonic energy shares across declared spatial supports."
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
    "BipartiteInterferenceEstimator",
    "InterferenceAugmentedGraph",
    "InterferenceIdentificationResult",
    "NetworkAIPWEstimator",
    "PartialInterferenceEstimator",
    "SpatialInterferenceEstimator",
    "build_block_stratified_network_causal_data",
    "build_interference_topology_contracts",
    "identify_interference_effect",
]
