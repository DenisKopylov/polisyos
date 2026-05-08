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


__all__ = [name for name in globals() if not name.startswith("__")]
