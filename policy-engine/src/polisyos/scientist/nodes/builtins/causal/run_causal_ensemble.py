from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.catalog import (
    ensure_all_methods_registered as ensure_causal_methods_registered,
)
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_discovery import load_causal_discovery_report
from polisyos.ir.analytics.causal_ensemble import (
    CausalModelEnsemble,
    EnsembleMember,
    persist_causal_model_ensemble,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    PAGIdentificationPolicy,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    CausalQueryResult,
    load_causal_query_result,
)
from polisyos.ir.analytics.structural_causal_model import (
    StructuralCausalModelSpec,
    load_structural_causal_model_spec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.analytics.uncertainty import persist_uncertainty_envelope
from polisyos.ir.refs import (
    CausalDiscoveryReportRef,
    CausalGraphModelRef,
    CausalQueryResultRef,
    StructuralCausalModelSpecRef,
)
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)

_METHOD_FQN = "causal.structural.gcm_query@1.0.0"
_MAX_MEMBERS = 10
_CONSENSUS_THRESHOLD = 0.5
_MIN_MEMBER_WEIGHT = 1.0e-6

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_causal_ensemble@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Causal Ensemble",
    description=(
        "Build structural-model ensemble, execute shared causal query for members, "
        "and persist ensemble-level uncertainty envelope."
    ),
    tags=["builtin", "causal", "ensemble"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.random_seed",
        "params.causal_query",
        "params.causal_ensemble_enabled",
        "params.causal_ensemble_members",
        f"artifacts_index.{ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_QUERY_RESULT_REF}",
    ],
    state_writes=[
        "params.causal_ensemble_member_count",
        "params.causal_ensemble_methods",
        "params.causal_ensemble_warning",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENSEMBLE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENVELOPE_REF}",
    ],
    produces=[
        ARTIFACT_CAUSAL_ENSEMBLE_REF,
        ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF,
        ARTIFACT_CAUSAL_ENVELOPE_REF,
    ],
)


class _MemberPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    structural_causal_model_spec_ref: Any | None = None
    structural_causal_model_ref: Any | None = None
    scm_ref: Any | None = None
    structural_causal_model_spec: dict[str, Any] | None = None
    graph_ref: Any | None = None
    causal_query_result_ref: Any | None = None
    discovery_report_ref: Any | None = None
    discovery_method: str | None = None
    method: str | None = None
    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    explicit_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    bootstrap_stability: float | None = Field(default=None, ge=0.0, le=1.0)


@dataclass(frozen=True)
class _MemberCandidate:
    order: int
    scm_ref: ArtifactRef | None
    scm_inline: StructuralCausalModelSpec | None
    graph_ref: ArtifactRef | None
    query_result_ref: ArtifactRef | None
    discovery_report_ref: ArtifactRef | None
    discovery_method: str | None
    explicit_weight: float | None
    bootstrap_stability: float | None


@dataclass(frozen=True)
class _ResolvedMember:
    member: EnsembleMember
    graph: CausalGraphModel
    graph_artifact_ref: ArtifactRef
    query_result: CausalQueryResult
    raw_weight: float


def _coerce_ref(raw: Any, *, default_kind: str) -> ArtifactRef | None:
    if raw is None:
        return None
    if isinstance(raw, ArtifactRef):
        return raw
    if isinstance(raw, Mapping):
        try:
            return ArtifactRef.model_validate(raw)
        except Exception:
            return None
    if isinstance(raw, str):
        try:
            artifact_id = ArtifactID.model_validate(raw)
        except Exception:
            return None
        return ArtifactRef(
            artifact_id=artifact_id,
            kind=default_kind,
            media_type="application/json",
        )
    return None


def _edge_key(edge: CausalEdge) -> str:
    base = f"{edge.src}\u2192{edge.dst}"
    if edge.lag is not None and edge.lag != 0:
        return f"{base}@lag={edge.lag}"
    return base


def _has_directed_cycle(nodes: list[str], edges: list[CausalEdge]) -> bool:
    indegree: dict[str, int] = {node: 0 for node in nodes}
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for edge in edges:
        if edge.lag not in (None, 0):
            continue
        adjacency.setdefault(edge.src, []).append(edge.dst)
        indegree.setdefault(edge.dst, 0)
        indegree[edge.dst] += 1
        indegree.setdefault(edge.src, indegree.get(edge.src, 0))

    queue = [node for node, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adjacency.get(node, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited != len(indegree)


def _member_sort_key(candidate: _MemberCandidate) -> tuple[int, float, int]:
    if candidate.explicit_weight is None:
        return (1, 0.0, candidate.order)
    return (0, -float(candidate.explicit_weight), candidate.order)


def _resolve_members(state: ExperimentState) -> tuple[list[_MemberCandidate], list[str]]:
    warnings: list[str] = []
    raw_members = state.params.get("causal_ensemble_members")
    candidates: list[_MemberCandidate] = []
    if isinstance(raw_members, list):
        for idx, raw_member in enumerate(raw_members):
            payload = _MemberPayload.model_validate(raw_member)
            scm_ref = (
                _coerce_ref(
                    payload.structural_causal_model_spec_ref,
                    default_kind="ir.structural_causal_model_spec",
                )
                or _coerce_ref(
                    payload.structural_causal_model_ref,
                    default_kind="ir.structural_causal_model_spec",
                )
                or _coerce_ref(payload.scm_ref, default_kind="ir.structural_causal_model_spec")
            )
            scm_inline = None
            if payload.structural_causal_model_spec is not None:
                scm_inline = StructuralCausalModelSpec.model_validate(
                    payload.structural_causal_model_spec
                )
            candidates.append(
                _MemberCandidate(
                    order=idx,
                    scm_ref=scm_ref,
                    scm_inline=scm_inline,
                    graph_ref=_coerce_ref(payload.graph_ref, default_kind="ir.causal_graph_model"),
                    query_result_ref=_coerce_ref(
                        payload.causal_query_result_ref,
                        default_kind="ir.causal_query_result",
                    ),
                    discovery_report_ref=_coerce_ref(
                        payload.discovery_report_ref,
                        default_kind="ir.causal_discovery_report",
                    ),
                    discovery_method=payload.discovery_method or payload.method,
                    explicit_weight=(
                        payload.explicit_weight
                        if payload.explicit_weight is not None
                        else payload.weight
                    ),
                    bootstrap_stability=payload.bootstrap_stability,
                )
            )

    if not candidates:
        scm_ref = _coerce_ref(
            state.artifacts_index.get(ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF),
            default_kind="ir.structural_causal_model_spec",
        )
        query_ref = _coerce_ref(
            state.artifacts_index.get(ARTIFACT_CAUSAL_QUERY_RESULT_REF),
            default_kind="ir.causal_query_result",
        )
        if scm_ref is not None:
            warnings.append(
                "causal_ensemble_members missing; using single-member fallback from current SCM."
            )
            candidates.append(
                _MemberCandidate(
                    order=0,
                    scm_ref=scm_ref,
                    scm_inline=None,
                    graph_ref=None,
                    query_result_ref=query_ref,
                    discovery_report_ref=None,
                    discovery_method="fallback_single_member",
                    explicit_weight=None,
                    bootstrap_stability=None,
                )
            )

    if len(candidates) > _MAX_MEMBERS:
        capped = sorted(candidates, key=_member_sort_key)[:_MAX_MEMBERS]
        warnings.append(
            f"causal ensemble candidate count exceeded {_MAX_MEMBERS}; deterministic cap applied."
        )
        return capped, warnings

    return candidates, warnings


def _seed_from_run_and_graph(run_id: str, graph: CausalGraphModel, offset: int) -> int:
    graph_hash = hashlib.sha256(
        graph.model_dump_json(exclude_none=False, by_alias=True).encode("utf-8")
    ).hexdigest()
    payload = f"{run_id}|{graph_hash}|{offset}".encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16) % (2**31 - 1)


def _mean_bootstrap_stability(
    ctx: ExecutionContext,
    discovery_report_ref: ArtifactRef | None,
) -> float:
    if discovery_report_ref is None:
        return 0.0
    try:
        report_ref = CausalDiscoveryReportRef.model_validate(discovery_report_ref.model_dump())
        report = load_causal_discovery_report(ctx.store, report_ref)
    except Exception:
        return 0.0
    if not report.bootstrap_stability:
        return 0.0
    values = [float(item) for item in report.bootstrap_stability.values()]
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _load_graph_for_candidate(
    ctx: ExecutionContext,
    *,
    candidate: _MemberCandidate,
    scm_ref: ArtifactRef,
    scm_spec: StructuralCausalModelSpec,
    member_index: int,
) -> tuple[CausalGraphModel, ArtifactRef]:
    if candidate.graph_ref is not None:
        graph_ref = CausalGraphModelRef.model_validate(candidate.graph_ref.model_dump(mode="json"))
        graph = load_causal_graph_model(ctx.store, graph_ref)
        return graph, ArtifactRef.model_validate(graph_ref.model_dump(mode="json"))

    graph_inputs = [InputRef(artifact_id=scm_ref.artifact_id, role=f"member_{member_index}.scm")]
    persisted = persist_causal_graph_model(ctx.store, scm_spec.graph, inputs=graph_inputs)
    graph_ref = ArtifactRef.model_validate(persisted.model_dump(mode="json"))
    return scm_spec.graph, graph_ref


def _run_member_query(
    *,
    ctx: ExecutionContext,
    query: CausalQuery,
    scm_spec: StructuralCausalModelSpec,
    seed: int,
) -> CausalQueryResult:
    method_state = SCMQueryData(scm_spec=scm_spec, query=query)
    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=_METHOD_FQN,
            method_params={},
            seed=seed,
        ),
        cas_root=ctx.store.root,
        method_state=method_state,
    )
    if result.issues:
        raise RuntimeError(f"gcm_query issues={result.issues}")
    output = result.final_state if isinstance(result.final_state, Mapping) else {}
    if "query_result" not in output:
        raise RuntimeError("gcm_query output missing query_result")
    return CausalQueryResult.model_validate(output["query_result"])


def _build_consensus_graph(
    *,
    resolved_members: list[_ResolvedMember],
    frequencies: dict[str, float],
) -> tuple[CausalGraphModel | None, list[str]]:
    if not resolved_members:
        return None, []

    template_by_key: dict[str, CausalEdge] = {}
    all_nodes: set[str] = set()
    graph_types = {item.graph.graph_type for item in resolved_members}
    for member in resolved_members:
        all_nodes.update(member.graph.nodes)
        for edge in member.graph.edges:
            template_by_key.setdefault(_edge_key(edge), edge)

    selected_keys = sorted(key for key, freq in frequencies.items() if freq >= _CONSENSUS_THRESHOLD)
    selected_edges = [template_by_key[key] for key in selected_keys if key in template_by_key]

    removed_edges: list[str] = []
    while selected_edges and _has_directed_cycle(sorted(all_nodes), selected_edges):
        drop_key = min(
            (_edge_key(edge) for edge in selected_edges),
            key=lambda key: (frequencies.get(key, 0.0), key),
        )
        selected_edges = [edge for edge in selected_edges if _edge_key(edge) != drop_key]
        removed_edges.append(drop_key)

    if not all_nodes:
        return None, removed_edges

    graph_type = GraphType.DAG
    if GraphType.PAG in graph_types:
        graph_type = GraphType.PAG
    elif GraphType.CPDAG in graph_types:
        graph_type = GraphType.CPDAG

    consensus_graph = CausalGraphModel(
        graph_type=graph_type,
        nodes=sorted(all_nodes),
        edges=selected_edges,
        discovery_method="ensemble_consensus",
        pag_identification_policy=(
            PAGIdentificationPolicy.PROBABILISTIC
            if graph_type is GraphType.PAG
            else PAGIdentificationPolicy.CONSERVATIVE
        ),
        metadata={
            "consensus_threshold": _CONSENSUS_THRESHOLD,
            "removed_cycle_edges": removed_edges,
            "member_count": len(resolved_members),
        },
    )
    return consensus_graph, removed_edges


@dataclass(frozen=True)
class RunCausalEnsembleNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if state.params.get("causal_ensemble_enabled") is not True:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="params.causal_ensemble_enabled is not true; skip ensemble build.",
                    )
                ],
            )

        try:
            candidates, warnings = _resolve_members(state)
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid params.causal_ensemble_members payload: {exc}",
                ),
            )

        if not candidates:
            new_state = state.model_copy(deep=True)
            new_state.params["causal_ensemble_warning"] = (
                "No causal ensemble candidates available; ensemble node skipped."
            )
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[
                    NodeEvent(
                        level="warn",
                        message="No structural candidates for causal ensemble; skipped.",
                    )
                ],
            )

        query_payload = state.params.get("causal_query")
        query: CausalQuery | None = None
        if query_payload is not None:
            try:
                query = CausalQuery.model_validate(query_payload)
            except Exception as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=f"Invalid params.causal_query payload: {exc}",
                    ),
                )

        if query is None and any(item.query_result_ref is None for item in candidates):
            new_state = state.model_copy(deep=True)
            new_state.params["causal_ensemble_warning"] = (
                "Missing params.causal_query and no member-level causal_query_result_ref fallback."
            )
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[
                    NodeEvent(
                        level="warn",
                        message=(
                            "Causal ensemble requires params.causal_query or precomputed "
                            "member query refs; skipped."
                        ),
                    )
                ],
            )

        if query is not None:
            ensure_causal_methods_registered()

        resolved_members: list[_ResolvedMember] = []
        methods: list[str] = []
        input_refs: list[InputRef] = []
        query_results_for_envelope: dict[str, list[float]] = {}

        run_id = str(state.run_id)
        seed_base = int(state.params.get("random_seed", 0) or 0)

        for idx, candidate in enumerate(candidates):
            if candidate.scm_inline is not None:
                persisted_scm = persist_structural_causal_model_spec(
                    ctx.store,
                    candidate.scm_inline,
                )
                scm_ref = ArtifactRef.model_validate(persisted_scm.model_dump(mode="json"))
                scm_spec = candidate.scm_inline
            elif candidate.scm_ref is not None:
                scm_spec_ref = StructuralCausalModelSpecRef.model_validate(
                    candidate.scm_ref.model_dump(mode="json")
                )
                scm_spec = load_structural_causal_model_spec(ctx.store, scm_spec_ref)
                scm_ref = candidate.scm_ref
            else:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=f"ensemble member #{idx} missing structural model reference",
                    ),
                )

            graph, graph_ref = _load_graph_for_candidate(
                ctx,
                candidate=candidate,
                scm_ref=scm_ref,
                scm_spec=scm_spec,
                member_index=idx,
            )

            if query is not None:
                member_seed = (
                    _seed_from_run_and_graph(run_id, graph, idx)
                    if seed_base == 0
                    else int(seed_base + idx)
                )
                try:
                    query_result = _run_member_query(
                        ctx=ctx,
                        query=query,
                        scm_spec=scm_spec,
                        seed=member_seed,
                    )
                except Exception as exc:
                    return NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                            message=f"Failed to execute member #{idx} gcm_query: {exc}",
                        ),
                    )
            else:
                assert candidate.query_result_ref is not None
                try:
                    query_result_ref = CausalQueryResultRef.model_validate(
                        candidate.query_result_ref.model_dump(mode="json")
                    )
                    query_result = load_causal_query_result(ctx.store, query_result_ref)
                except Exception as exc:
                    return NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code=node_errors.ERROR_MISSING_INPUT,
                            message=f"Failed to load causal_query_result for member #{idx}: {exc}",
                        ),
                    )

            stability = (
                float(candidate.bootstrap_stability)
                if candidate.bootstrap_stability is not None
                else _mean_bootstrap_stability(ctx, candidate.discovery_report_ref)
            )
            if not math.isfinite(stability):
                stability = 0.0
            stability = max(0.0, min(1.0, stability))

            raw_weight = (
                float(candidate.explicit_weight)
                if candidate.explicit_weight is not None
                else max(stability, _MIN_MEMBER_WEIGHT)
            )
            if raw_weight < 0.0 or not math.isfinite(raw_weight):
                raw_weight = _MIN_MEMBER_WEIGHT

            discovery_method = (
                candidate.discovery_method
                or graph.discovery_method
                or scm_spec.fit_method
                or "unknown"
            )

            distribution = query_result.result_distribution or [float(query_result.result_mean)]
            query_results_for_envelope[f"member_{idx}:{graph_ref.artifact_id}"] = [
                float(x) for x in distribution
            ]
            methods.append(str(discovery_method))

            resolved_members.append(
                _ResolvedMember(
                    member=EnsembleMember(
                        graph_ref=str(graph_ref.artifact_id),
                        discovery_method=str(discovery_method),
                        weight=0.0,  # normalized below
                        bootstrap_stability=stability,
                    ),
                    graph=graph,
                    graph_artifact_ref=graph_ref,
                    query_result=query_result,
                    raw_weight=raw_weight,
                )
            )

            input_refs.append(
                InputRef(artifact_id=scm_ref.artifact_id, role=f"member_{idx}.scm_ref")
            )
            input_refs.append(
                InputRef(
                    artifact_id=graph_ref.artifact_id,
                    role=f"member_{idx}.graph_ref",
                )
            )

        total_raw_weight = sum(item.raw_weight for item in resolved_members)
        if total_raw_weight <= 0.0:
            total_raw_weight = float(len(resolved_members))

        normalized_members: list[_ResolvedMember] = []
        for item in resolved_members:
            normalized_weight = float(item.raw_weight / total_raw_weight)
            normalized_members.append(
                _ResolvedMember(
                    member=item.member.model_copy(update={"weight": normalized_weight}),
                    graph=item.graph,
                    graph_artifact_ref=item.graph_artifact_ref,
                    query_result=item.query_result,
                    raw_weight=item.raw_weight,
                )
            )

        edge_frequencies: dict[str, float] = {}
        for item in normalized_members:
            present_edges = {_edge_key(edge) for edge in item.graph.edges}
            for edge_key in present_edges:
                edge_frequencies[edge_key] = float(
                    edge_frequencies.get(edge_key, 0.0) + item.member.weight
                )
        edge_frequencies = {
            key: max(0.0, min(1.0, value)) for key, value in edge_frequencies.items()
        }

        consensus_graph, removed_cycle_edges = _build_consensus_graph(
            resolved_members=normalized_members,
            frequencies=edge_frequencies,
        )
        consensus_graph_ref: ArtifactRef | None = None
        if consensus_graph is not None:
            graph_inputs = [
                InputRef(artifact_id=item.graph_artifact_ref.artifact_id, role=f"member_{idx}.graph")
                for idx, item in enumerate(normalized_members)
            ]
            persisted_consensus = persist_causal_graph_model(
                ctx.store,
                consensus_graph,
                inputs=graph_inputs,
            )
            consensus_graph_ref = ArtifactRef.model_validate(
                persisted_consensus.model_dump(mode="json")
            )
            input_refs.append(
                InputRef(
                    artifact_id=consensus_graph_ref.artifact_id,
                    role="consensus_graph_ref",
                )
            )

        ensemble = CausalModelEnsemble(
            members=[item.member for item in normalized_members],
            consensus_graph_ref=(
                str(consensus_graph_ref.artifact_id) if consensus_graph_ref is not None else None
            ),
            edge_inclusion_frequency=edge_frequencies,
        )
        ensemble_ref = persist_causal_model_ensemble(
            ctx.store,
            ensemble,
            inputs=input_refs,
        )

        envelope = ensemble.to_uncertainty_envelope(query_results_for_envelope)
        envelope_ref = persist_uncertainty_envelope(
            ctx.store,
            envelope,
            inputs=[
                InputRef(artifact_id=str(ensemble_ref.artifact_id), role="causal_ensemble_ref"),
                *input_refs,
            ],
        )

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF] = ArtifactRef.model_validate(
            ensemble_ref.model_dump(mode="json")
        )
        new_state.artifacts_index[
            ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF
        ] = ArtifactRef.model_validate(envelope_ref.model_dump(mode="json"))
        new_state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] = ArtifactRef.model_validate(
            envelope_ref.model_dump(mode="json")
        )
        new_state.params["causal_ensemble_member_count"] = len(normalized_members)
        new_state.params["causal_ensemble_methods"] = sorted({method for method in methods if method})
        if warnings or removed_cycle_edges:
            combined = [*warnings]
            if removed_cycle_edges:
                combined.append(
                    "Consensus graph had directed cycles; removed lowest-frequency edges."
                )
            new_state.params["causal_ensemble_warning"] = "; ".join(combined)
        else:
            new_state.params.pop("causal_ensemble_warning", None)

        produced: list[ArtifactRef] = [
            ArtifactRef.model_validate(ensemble_ref.model_dump(mode="json")),
            ArtifactRef.model_validate(envelope_ref.model_dump(mode="json")),
        ]
        if consensus_graph_ref is not None:
            produced.append(consensus_graph_ref)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=produced,
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Causal ensemble built: "
                        f"members={len(normalized_members)}, "
                        f"consensus_edges={len(consensus_graph.edges) if consensus_graph else 0}"
                    ),
                )
            ],
        )


__all__ = ["RunCausalEnsembleNode"]
