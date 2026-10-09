"""Public causal reconcile causal graph module API."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactRef, InputRef
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts import build_skip_blocker_record
from polisyos.foundry.methods.catalog.causal.composition_failure_cards import (
    CompositionFailureCardBundle,
    persist_composition_failure_card_bundle,
)
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import (
    ComposeSCMFragments,
    ReconcileCausalGraph,
    _validate_reconciliation_profile,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    FragmentCompositionData,
    GraphReconciliationData,
    LLMStructuralHint,
)
from polisyos.foundry.methods.catalog.causal.query_preservation import (
    evaluate_query_preservation_batch,
    negative_certificate_from_query_preservation_trace,
    update_query_preservation_artifact_refs,
    update_query_preservation_cache,
)
from polisyos.ir.analytics.alignment_certification import (
    AlignmentReport,
    AlignmentVerificationConfig,
    persist_alignment_report,
)
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.cross_graph import (
    CompositionCertificate,
    InterfaceMapping,
    SCMFragment,
    persist_composition_certificate,
    persist_interface_mapping,
    persist_scm_fragment,
)
from polisyos.ir.analytics.literature import LiteratureCausalPrior
from polisyos.ir.analytics.negative_certificate import persist_negative_certificate
from polisyos.ir.registry.refs import (
    AlignmentReportRef,
    CausalGraphModelRef,
    CompositionCertificateRef,
    InterfaceMappingRef,
    SCMFragmentRef,
)
from polisyos.scientist.cross_graph.compiler import (
    _verify_fragment_bundle_alignment_with_governance,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ALIGNMENT_REPORT_REF,
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
    ARTIFACT_COMPOSITION_CERTIFICATE_REF,
    ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF,
    ARTIFACT_INTERFACE_MAPPING_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

logger = get_logger(__name__)

_RECONCILE_NUMERIC_ERRORS = (TypeError, ValueError, OverflowError)
_RECONCILE_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_RECONCILE_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_RECONCILE_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_reconcile_causal_graph@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Reconcile Causal Graph",
    description="Merge data graph, literature prior, and LLM hints into reconciled graph.",
    tags=["builtin", "causal", "prior", "reconciliation"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_LITERATURE_PRIOR_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_RESULT_REF}",
        "params.data_causal_graph",
        "params.llm_structural_hints",
        "params.scm_fragment_refs",
        "params.scm_fragments",
        "params.alignment_verification_config",
        "params.direct_stitch_pairs",
        "params.query_preservation_queries",
        "params.reconciliation_min_edge_confidence",
        "params.reconciliation_max_lag_depth",
        "params.reconciliation_max_lagged_edges",
        "params.reconciliation_max_cycles_to_resolve",
        f"artifacts_index.{ARTIFACT_ALIGNMENT_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_INTERFACE_MAPPING_REF}",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
        f"artifacts_index.{ARTIFACT_ALIGNMENT_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_INTERFACE_MAPPING_REF}",
        f"artifacts_index.{ARTIFACT_COMPOSITION_CERTIFICATE_REF}",
        f"artifacts_index.{ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF}",
        "params.needs_expert_review",
        "params.reconciliation_diagnostics",
        "params.reconciliation_warnings",
        "params.composition_blocking_reasons",
    ],
    produces=[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF],
)


def _optional_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except _RECONCILE_NUMERIC_ERRORS:
        return float(default)


def _optional_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except _RECONCILE_NUMERIC_ERRORS:
        return int(default)


def _extract_graph(payload: Any) -> CausalGraphModel:
    if isinstance(payload, CausalGraphModel):
        return CausalGraphModel.model_validate(payload.model_dump(mode="json"))
    if not isinstance(payload, dict):
        raise ValueError("Supplied data causal graph must be a typed graph or graph payload")
    if {"graph_type", "nodes", "edges"}.issubset(payload):
        return CausalGraphModel.model_validate(payload)
    graphs = [
        CausalGraphModel.model_validate(payload[key])
        for key in ("graph", "causal_graph", "reconciled_graph", "literature_prior_graph")
        if key in payload
    ]
    if not graphs or any(graph != graphs[0] for graph in graphs[1:]):
        raise ValueError("Supplied graph payload is absent or has conflicting graph projections")
    return graphs[0]


def _selected_ref(ref: Any, *, kind: str) -> ArtifactRef:
    typed_ref = (
        ref
        if isinstance(ref, ArtifactRef)
        else ArtifactRef.model_validate(
            {"artifact_id": ref, "kind": kind, "media_type": "application/json"}
            if isinstance(ref, str)
            else ref.model_dump(mode="json")
            if isinstance(ref, BaseModel)
            else ref
        )
    )
    if typed_ref.kind != kind:
        raise ValueError("Supplied source reference has incompatible declared kind")
    return typed_ref


def _resolve_typed_source(ctx: ExecutionContext, ref: Any, *, kind: str, model: Any) -> Any:
    typed_ref = _selected_ref(ref, kind=kind)
    manifest = ctx.store.get_manifest(typed_ref)
    if (
        manifest.kind != kind
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != kind
    ):
        raise ValueError("Source reference has incompatible actual manifest/schema")
    # Pass the whole selected ref: CAS checks the actual bytes and manifest view.
    value = model.model_validate(from_canonical_bytes(ctx.store.get_bytes(typed_ref)))
    if value.schema_version != manifest.artifact_schema.version:
        raise ValueError("Source body version differs from actual manifest schema version")
    return value


def _resolve_graph_ref(ctx: ExecutionContext, ref: Any) -> CausalGraphModel:
    graph = _resolve_typed_source(ctx, ref, kind="ir.causal_graph_model", model=CausalGraphModel)
    if graph.schema_version != "1.0":
        raise ValueError("Unsupported causal graph schema version")
    _validate_reconciliation_profile(graph)
    return graph


def _load_data_graph(
    ctx: ExecutionContext, state: ExperimentState
) -> tuple[CausalGraphModel | None, Any | None]:
    supplied = "data_causal_graph" in state.params
    graph = _extract_graph(state.params["data_causal_graph"]) if supplied else None
    method_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_METHOD_RESULT_REF)
    if method_ref is not None:
        manifest = ctx.store.get_manifest(method_ref)
        if (
            not manifest.kind.startswith("scientist.method_result.causal")
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != "polisyos.scientist.MethodResult"
            or manifest.artifact_schema.version != "0.1.0"
        ):
            raise ValueError("Data graph method reference has incompatible actual manifest/schema")
        actual = _extract_graph(from_canonical_bytes(ctx.store.get_bytes(method_ref)))
        if graph is not None and graph != actual:
            raise ValueError("Supplied data graph differs from current method-result CAS content")
        return actual, method_ref
    return graph, None


def _parse_llm_hints(raw: Any) -> list[LLMStructuralHint]:
    if not isinstance(raw, list):
        raise ValueError("Supplied LLM structural hints must be a list")
    return [LLMStructuralHint.model_validate(item) for item in raw]


def _composition_requested(state: ExperimentState) -> bool:
    return "scm_fragment_refs" in state.params or "scm_fragments" in state.params


def _parse_fragment_ref(value: Any) -> ArtifactRef | None:
    try:
        return _selected_ref(value, kind="ir.scm_fragment")
    except _RECONCILE_VALIDATION_ERRORS:
        return None


def _load_scm_fragments(ctx: ExecutionContext, state: ExperimentState) -> list[SCMFragment]:
    supplied = "scm_fragments" in state.params
    raw_fragments = state.params.get("scm_fragments")
    fragments: list[SCMFragment] = []
    if supplied:
        if not isinstance(raw_fragments, list):
            raise ValueError("Supplied SCM fragments must be a list")
        fragments = [
            SCMFragment.model_validate(
                item.model_dump(mode="json") if isinstance(item, SCMFragment) else item
            )
            for item in raw_fragments
        ]
    if "scm_fragment_refs" in state.params:
        raw_refs = state.params["scm_fragment_refs"]
        if not isinstance(raw_refs, list):
            raise ValueError("Supplied SCM fragment references must be a list")
        resolved: list[SCMFragment] = []
        for item in raw_refs:
            ref = _parse_fragment_ref(item)
            if ref is None:
                raise ValueError("Supplied SCM fragment reference is malformed")
            resolved.append(
                _resolve_typed_source(ctx, ref, kind="ir.scm_fragment", model=SCMFragment)
            )
        if supplied and fragments != resolved:
            raise ValueError("Supplied fragments differ from actual fragment CAS content")
        return resolved
    return fragments


def _load_fragment_graphs(
    ctx: ExecutionContext,
    fragments: list[SCMFragment],
) -> dict[str, CausalGraphModel]:
    graphs: dict[str, CausalGraphModel] = {}
    for fragment in fragments:
        ref = CausalGraphModelRef.model_validate({"artifact_id": fragment.graph_ref})
        graphs[fragment.fragment_id] = _resolve_graph_ref(ctx, ref)
    return graphs


def _resolve_fragment_provenance(
    ctx: ExecutionContext,
    state: ExperimentState,
    fragments: list[SCMFragment],
) -> tuple[dict[str, str], dict[str, str]]:
    source_fragment_refs: dict[str, str] = {}
    raw_refs = state.params.get("scm_fragment_refs")
    if isinstance(raw_refs, list):
        for item in raw_refs:
            ref = _parse_fragment_ref(item)
            if ref is None:
                continue
            try:
                fragment = _resolve_typed_source(
                    ctx, ref, kind="ir.scm_fragment", model=SCMFragment
                )
            except _RECONCILE_LOAD_ERRORS:
                continue
            source_fragment_refs[fragment.fragment_id] = str(ref.artifact_id)

    for fragment in sorted(fragments, key=lambda item: item.fragment_id):
        if fragment.fragment_id not in source_fragment_refs:
            persisted_ref = persist_scm_fragment(_ensure_ir_artifact_store(ctx.store), fragment)
            source_fragment_refs[fragment.fragment_id] = str(persisted_ref.artifact_id)

    source_fragment_graph_refs = {
        fragment.fragment_id: str(fragment.graph_ref)
        for fragment in sorted(fragments, key=lambda item: item.fragment_id)
    }
    return source_fragment_refs, source_fragment_graph_refs


def _load_precomputed_alignment(
    ctx: ExecutionContext,
    state: ExperimentState,
):
    report = None
    mapping = None
    report_ref = state.artifacts_index.get(ARTIFACT_ALIGNMENT_REPORT_REF)
    mapping_ref = state.artifacts_index.get(ARTIFACT_INTERFACE_MAPPING_REF)

    if report_ref is not None:
        report = _resolve_typed_source(
            ctx, report_ref, kind="ir.alignment_report", model=AlignmentReport
        )
    if mapping_ref is not None:
        mapping = _resolve_typed_source(
            ctx, mapping_ref, kind="ir.interface_mapping", model=InterfaceMapping
        )
    return report, mapping, report_ref, mapping_ref


def _parse_query_preservation_queries(raw: Any) -> list[CausalQuery]:
    if not isinstance(raw, list):
        return []
    queries: list[CausalQuery] = []
    for item in raw:
        try:
            queries.append(
                item if isinstance(item, CausalQuery) else CausalQuery.model_validate(item)
            )
        except _RECONCILE_VALIDATION_ERRORS:
            continue
    return queries


def _parse_direct_stitch_pairs(raw: Any) -> list[tuple[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    pairs: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        left = str(item[0]).strip()
        right = str(item[1]).strip()
        if not left or not right or left == right:
            continue
        pairs.append((left, right))
    return pairs


def _graph_signature_payload(graph: CausalGraphModel) -> dict[str, Any]:
    return {
        "graph_type": graph.graph_type.value,
        "nodes": list(graph.nodes),
        "edges": [
            {
                "src": edge.src,
                "dst": edge.dst,
                "mark_src": edge.mark_src.value,
                "mark_dst": edge.mark_dst.value,
                "lag": int(edge.lag or 0),
            }
            for edge in sorted(
                graph.edges,
                key=lambda item: (
                    item.src,
                    item.dst,
                    item.mark_src.value,
                    item.mark_dst.value,
                    int(item.lag or 0),
                ),
            )
        ],
    }


def _persist_query_preservation_artifacts(
    ctx: ExecutionContext,
    *,
    queries: list[CausalQuery],
    traces: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str], list[object]]:
    """Persist latent-projection and impossibility artifacts for query-preservation traces."""
    artifacts: list[object] = []
    projection_refs: dict[str, str] = {}
    negative_refs: dict[str, str] = {}
    query_by_fingerprint = {
        trace.fingerprint: query for query, trace in zip(queries, traces.values(), strict=False)
    }
    projection_ref_by_signature: dict[str, str] = {}

    for fingerprint, trace in sorted(traces.items()):
        projection_graph = getattr(trace, "latent_projection_graph", None)
        if projection_graph is not None:
            signature = json.dumps(
                _graph_signature_payload(projection_graph),
                sort_keys=True,
                separators=(",", ":"),
            )
            projection_ref = projection_ref_by_signature.get(signature)
            if projection_ref is None:
                persisted_projection = persist_causal_graph_model(
                    _ensure_ir_artifact_store(ctx.store), projection_graph
                )
                projection_ref = str(persisted_projection.artifact_id)
                projection_ref_by_signature[signature] = projection_ref
                artifacts.append(persisted_projection)
            projection_refs[fingerprint] = projection_ref

        query = query_by_fingerprint.get(fingerprint)
        if query is None:
            continue
        negative_certificate = negative_certificate_from_query_preservation_trace(query, trace)
        if negative_certificate is None:
            continue
        persisted_negative = persist_negative_certificate(
            _ensure_ir_artifact_store(ctx.store), negative_certificate
        )
        negative_refs[fingerprint] = str(persisted_negative.artifact_id)
        artifacts.append(persisted_negative)

    return projection_refs, negative_refs, artifacts


def _composition_source_basis(certificate: CompositionCertificate) -> dict[str, Any]:
    """Keep the entire producer contract; query caches are recomputed separately."""
    return certificate.model_dump(
        mode="json",
        exclude={"checked_queries", "query_certificates", "failure_card_bundle_ref"},
    )


def _apply_query_preservation_hook(
    ctx: ExecutionContext,
    state: ExperimentState,
    queries: list[CausalQuery],
) -> NodeOutcome | None:
    graph_ref_payload = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
    certificate_ref_payload = state.artifacts_index.get(ARTIFACT_COMPOSITION_CERTIFICATE_REF)
    mapping_ref_payload = state.artifacts_index.get(ARTIFACT_INTERFACE_MAPPING_REF)
    if graph_ref_payload is None or certificate_ref_payload is None or mapping_ref_payload is None:
        return None

    try:
        composed_graph = _resolve_graph_ref(ctx, graph_ref_payload)
        certificate = _resolve_typed_source(
            ctx,
            certificate_ref_payload,
            kind="ir.composition_certificate",
            model=CompositionCertificate,
        )
        interface_mapping = _resolve_typed_source(
            ctx,
            mapping_ref_payload,
            kind="ir.interface_mapping",
            model=InterfaceMapping,
        )
        if not certificate.source_fragment_refs:
            raise ValueError("Current composition source provenance is required for graph reuse")
        fragments = []
        for fragment_id, artifact_id in sorted(certificate.source_fragment_refs.items()):
            fragment = _resolve_typed_source(
                ctx,
                artifact_id,
                kind="ir.scm_fragment",
                model=SCMFragment,
            )
            if fragment.fragment_id != fragment_id:
                raise ValueError("Composition source fragment identity differs from its CAS body")
            fragments.append(fragment)
        actual_graph_refs = {
            fragment.fragment_id: str(fragment.graph_ref) for fragment in fragments
        }
        if actual_graph_refs != certificate.source_fragment_graph_refs:
            raise ValueError("Composition graph sources differ from actual fragment CAS content")
        fragment_graphs = _load_fragment_graphs(ctx, fragments)
        alignment_ref = state.artifacts_index.get(ARTIFACT_ALIGNMENT_REPORT_REF)
        if alignment_ref is None:
            raise ValueError("Actual alignment report is required for graph reuse")
        alignment = _resolve_typed_source(
            ctx,
            alignment_ref,
            kind="ir.alignment_report",
            model=AlignmentReport,
        )
        reproduced = ComposeSCMFragments.pure_step(
            FragmentCompositionData(
                fragments=fragments,
                fragment_graphs=fragment_graphs,
                alignment_report=alignment,
                interface_mapping=interface_mapping,
                source_fragment_refs=dict(certificate.source_fragment_refs),
                source_fragment_graph_refs=actual_graph_refs,
                metadata={
                    "alignment_report_ref": str(
                        _selected_ref(alignment_ref, kind="ir.alignment_report").artifact_id
                    ),
                    "interface_mapping_ref": str(
                        _selected_ref(mapping_ref_payload, kind="ir.interface_mapping").artifact_id
                    ),
                },
                direct_stitch_pairs=_parse_direct_stitch_pairs(
                    state.params.get("direct_stitch_pairs")
                ),
            ),
            params={},
        )
        if reproduced.get("composed_graph") != composed_graph:
            raise ValueError("Cached graph differs from actual composition source content")
        expected_certificate = reproduced["composition_certificate"].model_copy(
            update={
                "composed_graph_ref": str(
                    _selected_ref(graph_ref_payload, kind="ir.causal_graph_model").artifact_id
                )
            }
        )
        # Failure-card refs are persistence outputs: compare their complete bodies.
        cards = reproduced.get("failure_cards", [])
        if cards or certificate.failure_card_bundle_ref is not None:
            if certificate.failure_card_bundle_ref is None:
                raise ValueError("Actual composition failure-card bundle is missing")
            bundle = _resolve_typed_source(
                ctx,
                certificate.failure_card_bundle_ref,
                kind="ir.composition_failure_card_bundle",
                model=CompositionFailureCardBundle,
            )
            expected_bundle = CompositionFailureCardBundle(
                cards=cards,
                metadata={
                    "composition_status": expected_certificate.status,
                    "structure_status": expected_certificate.structure_status,
                    "review_status": expected_certificate.review_status,
                    "source_fragment_ids": sorted(fragment.fragment_id for fragment in fragments),
                },
            )
            if bundle != expected_bundle:
                raise ValueError("Cached failure cards differ from actual composition result")
        # Only query caches and the separately validated persistence pointer are
        # operational. All producer semantics, source refs and metadata must agree.
        if _composition_source_basis(certificate) != _composition_source_basis(
            expected_certificate
        ):
            raise ValueError("Cached certificate differs from actual composition result")
        if expected_certificate.status == "broken":
            raise ValueError("Actual composition result refuses graph admission")
        # Evaluate fresh: an old operational query cache is not source authority.
        certificate = expected_certificate.model_copy(
            update={
                "failure_card_bundle_ref": certificate.failure_card_bundle_ref,
            }
        )
        _validate_reconciliation_profile(composed_graph)
    except _RECONCILE_LOAD_ERRORS as exc:
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"failed to reconcile composition graph content: {exc}",
            ),
        )

    traces = evaluate_query_preservation_batch(
        queries,
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
        composition_certificate=certificate,
    )
    updated_certificate, query_statuses = update_query_preservation_cache(
        certificate,
        queries=queries,
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
    )
    projection_refs, negative_refs, extra_artifacts = _persist_query_preservation_artifacts(
        ctx,
        queries=queries,
        traces=traces,
    )
    updated_certificate = update_query_preservation_artifact_refs(
        updated_certificate,
        latent_projection_refs=projection_refs,
        negative_certificate_refs=negative_refs,
    )
    certificate_ref = persist_composition_certificate(
        _ensure_ir_artifact_store(ctx.store), updated_certificate
    )

    new_state = branch_state(state, write_paths=_SPEC.state_writes).state
    new_state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF] = certificate_ref
    new_state.params["needs_expert_review"] = bool(reproduced.get("needs_expert_review", False))
    new_state.params["reconciliation_warnings"] = list(reproduced.get("warnings", []))
    new_state.params["composition_blocking_reasons"] = list(reproduced.get("blocking_reasons", []))
    diagnostics = dict(new_state.params.get("reconciliation_diagnostics", {}))
    diagnostics.update(
        {
            "composition_status": certificate.status,
            "structure_status": certificate.structure_status,
            "review_status": certificate.review_status,
            "query_preservation_statuses": dict(query_statuses),
        }
    )
    diagnostics["query_preservation_reasons"] = {
        fingerprint: trace.reason_code for fingerprint, trace in sorted(traces.items())
    }
    diagnostics["query_preservation_traces"] = {
        fingerprint: {
            "status": trace.status,
            "reason_code": trace.reason_code,
            "source_fragment_id": trace.source_fragment_id,
            "witness_fragment_ids": list(trace.witness_fragment_ids),
            "source_witness_kind": trace.source_witness_kind,
            "assumption_boundary": trace.assumption_boundary,
            "theorem_family": trace.theorem_family,
            "identification_status": trace.identification_status,
            "identification_method": trace.identification_method,
            "latent_projection_ref": projection_refs.get(fingerprint),
            "negative_certificate_ref": negative_refs.get(fingerprint),
        }
        for fingerprint, trace in sorted(traces.items())
    }
    new_state.params["reconciliation_diagnostics"] = diagnostics

    return NodeOutcome(
        status="ok",
        state=new_state,
        artifacts=[certificate_ref, *extra_artifacts],
        events=[
            NodeEvent(
                level="info",
                message=f"Query preservation checked for {len(query_statuses)} query fingerprints.",
            )
        ],
    )


@dataclass(frozen=True)
class ReconcileCausalGraphNode:
    """Merge data, literature, and fragment evidence into a reconciled graph.

    The node assembles all available graph sources, runs reconciliation and
    alignment checks, then persists the reconciled graph plus diagnostics used
    by causal readiness, transportability, and governance passes.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        query_preservation_queries = _parse_query_preservation_queries(
            state.params.get("query_preservation_queries")
        )
        cached_ref = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
        cached_graph = None
        try:
            if cached_ref is not None:
                cached_graph = _resolve_graph_ref(ctx, cached_ref)
        except _RECONCILE_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"failed to resolve current reconciled graph: {exc}",
                ),
            )
        has_current_data = (
            "data_causal_graph" in state.params
            or ARTIFACT_CAUSAL_METHOD_RESULT_REF in state.artifacts_index
        )
        if (
            cached_graph is not None
            and query_preservation_queries
            and not (has_current_data or _composition_requested(state))
        ):
            hook_outcome = _apply_query_preservation_hook(ctx, state, query_preservation_queries)
            if hook_outcome is not None:
                return hook_outcome
        if cached_graph is not None and not (has_current_data or _composition_requested(state)):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Current source is required to reconcile cached graph content",
                ),
            )

        if _composition_requested(state):
            try:
                fragments = _load_scm_fragments(ctx, state)
            except _RECONCILE_LOAD_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=f"failed to load current fragment sources: {exc}",
                    ),
                )
            direct_stitch_pairs = _parse_direct_stitch_pairs(
                state.params.get("direct_stitch_pairs")
            )
            if not fragments:
                return NodeOutcome(
                    status="skip",
                    state=state,
                    events=[
                        NodeEvent(
                            level="info",
                            message="SCM fragment composition requested but no fragments could be loaded.",
                        )
                    ],
                )
            try:
                fragment_graphs = _load_fragment_graphs(ctx, fragments)
            except _RECONCILE_LOAD_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=f"failed to load fragment graphs for composition: {exc}",
                    ),
                )

            try:
                alignment_report, interface_mapping, alignment_report_ref, interface_mapping_ref = (
                    _load_precomputed_alignment(ctx, state)
                )
                verification_config = AlignmentVerificationConfig.model_validate(
                    state.params.get("alignment_verification_config", {})
                )
                governed_report, governed_mapping = (
                    _verify_fragment_bundle_alignment_with_governance(
                        fragments,
                        config=verification_config,
                        stitch_pairs=direct_stitch_pairs,
                        artifact_store=ctx.store,
                    )
                )
            except _RECONCILE_LOAD_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                        message=f"fragment alignment verification failed: {exc}",
                    ),
                )
            reuse_precomputed_alignment = bool(
                alignment_report is not None
                and interface_mapping is not None
                and alignment_report == governed_report
                and interface_mapping == governed_mapping
            )
            if not reuse_precomputed_alignment:
                alignment_report = governed_report
                interface_mapping = governed_mapping
                alignment_report_ref = persist_alignment_report(
                    _ensure_ir_artifact_store(ctx.store), alignment_report
                )
                interface_mapping_ref = persist_interface_mapping(
                    _ensure_ir_artifact_store(ctx.store), interface_mapping
                )

            try:
                source_fragment_refs, source_fragment_graph_refs = _resolve_fragment_provenance(
                    ctx,
                    state,
                    fragments,
                )
                composition_request = FragmentCompositionData(
                    fragments=fragments,
                    fragment_graphs=fragment_graphs,
                    alignment_report=alignment_report,
                    interface_mapping=interface_mapping,
                    source_fragment_refs=source_fragment_refs,
                    source_fragment_graph_refs=source_fragment_graph_refs,
                    metadata={
                        "alignment_report_ref": str(alignment_report_ref.artifact_id),
                        "interface_mapping_ref": str(interface_mapping_ref.artifact_id),
                    },
                    direct_stitch_pairs=direct_stitch_pairs,
                )
                result = ComposeSCMFragments.pure_step(composition_request, params={})
            except _RECONCILE_EXECUTION_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                        message=f"compose_scm_fragments execution failed: {exc}",
                    ),
                )

            certificate = result["composition_certificate"]
            artifacts = []
            graph_ref = None
            composed_graph = result.get("composed_graph")
            # Only persist the composed graph when the certificate is not "broken".
            # A broken certificate means alignment is incompatible or the composition has
            # unresolvable structural/alignment errors — the graph output is suppressed so
            # downstream nodes cannot accidentally use an invalid composition.
            if composed_graph is not None and certificate.status != "broken":
                graph_ref = persist_causal_graph_model(
                    _ensure_ir_artifact_store(ctx.store), composed_graph
                )
                artifacts.append(graph_ref)

            if graph_ref is not None:
                certificate = certificate.model_copy(
                    update={"composed_graph_ref": str(graph_ref.artifact_id)}
                )
            query_statuses: dict[str, str] = {}
            query_reasons: dict[str, str] = {}
            query_traces: dict[str, dict[str, object]] = {}
            query_projection_refs: dict[str, str] = {}
            query_negative_refs: dict[str, str] = {}
            if composed_graph is not None and query_preservation_queries:
                traces = evaluate_query_preservation_batch(
                    query_preservation_queries,
                    composed_graph=composed_graph,
                    fragments=fragments,
                    fragment_graphs=fragment_graphs,
                    interface_mapping=interface_mapping,
                    composition_certificate=certificate,
                )
                certificate, query_statuses = update_query_preservation_cache(
                    certificate,
                    queries=query_preservation_queries,
                    composed_graph=composed_graph,
                    fragments=fragments,
                    fragment_graphs=fragment_graphs,
                    interface_mapping=interface_mapping,
                )
                query_projection_refs, query_negative_refs, query_artifacts = (
                    _persist_query_preservation_artifacts(
                        ctx,
                        queries=query_preservation_queries,
                        traces=traces,
                    )
                )
                query_reasons = {
                    fingerprint: trace.reason_code for fingerprint, trace in sorted(traces.items())
                }
                query_traces = {
                    fingerprint: {
                        "status": trace.status,
                        "reason_code": trace.reason_code,
                        "source_fragment_id": trace.source_fragment_id,
                        "witness_fragment_ids": list(trace.witness_fragment_ids),
                        "source_witness_kind": trace.source_witness_kind,
                        "assumption_boundary": trace.assumption_boundary,
                        "theorem_family": trace.theorem_family,
                        "identification_status": trace.identification_status,
                        "identification_method": trace.identification_method,
                        "latent_projection_ref": query_projection_refs.get(fingerprint),
                        "negative_certificate_ref": query_negative_refs.get(fingerprint),
                    }
                    for fingerprint, trace in sorted(traces.items())
                }
                certificate = update_query_preservation_artifact_refs(
                    certificate,
                    latent_projection_refs=query_projection_refs,
                    negative_certificate_refs=query_negative_refs,
                )
                artifacts.extend(query_artifacts)
            failure_card_bundle_ref = None
            failure_cards = result.get("failure_cards", [])
            if failure_cards:
                failure_card_bundle = CompositionFailureCardBundle(
                    cards=failure_cards,
                    metadata={
                        "composition_status": certificate.status,
                        "structure_status": certificate.structure_status,
                        "review_status": certificate.review_status,
                        "source_fragment_ids": sorted(
                            fragment.fragment_id for fragment in fragments
                        ),
                    },
                )
                failure_card_bundle_ref = persist_composition_failure_card_bundle(
                    ctx.store,
                    failure_card_bundle,
                )
                certificate = certificate.model_copy(
                    update={"failure_card_bundle_ref": str(failure_card_bundle_ref.artifact_id)}
                )
            certificate_ref = persist_composition_certificate(
                _ensure_ir_artifact_store(ctx.store), certificate
            )
            artifacts.extend([alignment_report_ref, interface_mapping_ref, certificate_ref])
            if failure_card_bundle_ref is not None:
                artifacts.append(failure_card_bundle_ref)

            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
            if graph_ref is not None:
                new_state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
            new_state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF] = alignment_report_ref
            new_state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF] = interface_mapping_ref
            new_state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF] = certificate_ref
            if failure_card_bundle_ref is not None:
                new_state.artifacts_index[ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF] = (
                    failure_card_bundle_ref
                )
            new_state.params["needs_expert_review"] = bool(result.get("needs_expert_review", False))
            new_state.params["reconciliation_warnings"] = [
                str(item) for item in result.get("warnings", [])
            ]
            new_state.params["composition_blocking_reasons"] = [
                str(item) for item in result.get("blocking_reasons", [])
            ]
            new_state.params["reconciliation_diagnostics"] = {
                "composition_status": certificate.status,
                "structure_status": certificate.structure_status,
                "review_status": certificate.review_status,
                "graph_type": certificate.metadata.get("graph_type"),
                "query_preservation_statuses": dict(query_statuses),
                "query_preservation_reasons": dict(query_reasons),
                "query_preservation_traces": dict(query_traces),
                "failure_card_types": [card.failure_type for card in failure_cards],
            }

            message = (
                "SCM fragments composed into reconciled graph."
                if graph_ref is not None
                else "SCM fragment composition evaluated; see composition certificate for blocking reasons."
            )
            return NodeOutcome(
                status="ok",
                state=new_state,
                artifacts=artifacts,
                events=[NodeEvent(level="info", message=message)],
            )

        try:
            data_graph, data_graph_ref = _load_data_graph(ctx, state)
        except _RECONCILE_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"failed to load current data causal graph: {exc}",
                ),
            )
        if data_graph is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(level="info", message="No data causal graph; skip reconciliation.")
                ],
                skip_blocker=_phase2_missing_input_blocker(
                    missing_input="data_causal_graph",
                    reason="No data causal graph was produced for reconciliation.",
                    phase="reconcile_causal_graph",
                ),
            )

        literature_prior_ref = state.artifacts_index.get(ARTIFACT_LITERATURE_PRIOR_REF)
        literature_prior = None
        if literature_prior_ref is not None:
            try:
                manifest = ctx.store.get_manifest(literature_prior_ref)
                if manifest.kind != "ir.literature_causal_prior":
                    raise ValueError("Supplied literature prior has incompatible actual manifest")
                literature_prior = LiteratureCausalPrior.model_validate(
                    from_canonical_bytes(ctx.store.get_bytes(literature_prior_ref))
                )
            except _RECONCILE_LOAD_ERRORS as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=f"failed to load supplied literature prior: {exc}",
                    ),
                )

        try:
            llm_hints = _parse_llm_hints(state.params.get("llm_structural_hints", []))
            request = GraphReconciliationData(
                data_graph=data_graph,
                literature_prior=literature_prior,
                llm_hints=llm_hints,
                min_edge_confidence=_optional_float(
                    state.params.get("reconciliation_min_edge_confidence"),
                    default=0.1,
                ),
                max_lag_depth=_optional_int(
                    state.params.get("reconciliation_max_lag_depth"),
                    default=2,
                ),
                max_lagged_edges=_optional_int(
                    state.params.get("reconciliation_max_lagged_edges"),
                    default=10,
                ),
                max_cycles_to_resolve=_optional_int(
                    state.params.get("reconciliation_max_cycles_to_resolve"),
                    default=8,
                ),
            )
            result = ReconcileCausalGraph.pure_step(request, params={})
        except _RECONCILE_EXECUTION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message=f"reconcile_causal_graph execution failed: {exc}",
                ),
            )

        reconciled_graph = result.get("reconciled_graph")
        diagnostics = result.get("diagnostics")
        if reconciled_graph is None or diagnostics is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="reconcile_causal_graph did not return graph and diagnostics",
                ),
            )

        inputs: list[InputRef] = []
        if data_graph_ref is not None:
            inputs.append(
                InputRef(
                    artifact_id=str(data_graph_ref.artifact_id),
                    role="data_graph",
                    manifest_profile_sha256=data_graph_ref.manifest_profile_sha256,
                )
            )
        if literature_prior_ref is not None:
            inputs.append(
                InputRef(
                    artifact_id=str(literature_prior_ref.artifact_id),
                    role="literature_prior",
                    manifest_profile_sha256=literature_prior_ref.manifest_profile_sha256,
                )
            )
        try:
            # The digest describes the actual typed request, not a caller-supplied seal.
            request_bytes = json.dumps(
                request.model_dump(mode="json"),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            reconciled_graph = CausalGraphModel.model_validate(
                reconciled_graph.model_dump(mode="json")
            )
            _validate_reconciliation_profile(reconciled_graph)
            metadata = dict(reconciled_graph.metadata)
            metadata["reconciliation_input_sha256"] = hashlib.sha256(request_bytes).hexdigest()
            reconciled_graph = reconciled_graph.model_copy(update={"metadata": metadata})
            reuse = (
                cached_graph == reconciled_graph
                and cached_ref is not None
                and (ctx.store.get_manifest(cached_ref).inputs == inputs)
            )
            graph_ref = (
                cached_ref
                if reuse
                else persist_causal_graph_model(
                    _ensure_ir_artifact_store(ctx.store), reconciled_graph, inputs=inputs
                )
            )
        except _RECONCILE_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"failed to admit reconciled graph content: {exc}",
                ),
            )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
        new_state.params["needs_expert_review"] = bool(result.get("needs_expert_review", False))
        new_state.params["reconciliation_diagnostics"] = diagnostics.model_dump(mode="json")
        new_state.params["reconciliation_warnings"] = [
            str(item) for item in result.get("warnings", [])
        ]

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[graph_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Causal graph reconciled; "
                        f"needs_expert_review={new_state.params['needs_expert_review']}."
                    ),
                )
            ],
        )


def _phase2_missing_input_blocker(
    *,
    missing_input: str,
    reason: str,
    phase: str,
):
    return build_skip_blocker_record(
        node_id=str(_SPEC.metadata.component_id),
        alias="reconcile_causal_graph",
        node_kind="causal",
        reason=reason,
        missing_input=missing_input,
        owner="gy_phase2_blocked_input_producer",
        phase=phase,
        downstream_impact="Phase-2 REFINE cannot reconcile causal evidence without this input.",
        allowed_profile="dev",
        closeout_blocking_policy="blocks_authority",
        scorecard_blocking_policy="blocks_authority",
        approval_blocking_policy="blocks_authority",
        public_export_blocking_policy="blocks_authority",
        blocker_code="gy_phase2_blocked_input_producer_missing",
    )


__all__ = ["ReconcileCausalGraphNode"]
