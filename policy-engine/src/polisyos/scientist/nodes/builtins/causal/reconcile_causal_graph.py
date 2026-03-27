from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import (
    ComposeSCMFragments,
    ReconcileCausalGraph,
)
from polisyos.foundry.methods.catalog.causal.composition_failure_cards import (
    CompositionFailureCardBundle,
    persist_composition_failure_card_bundle,
)
from polisyos.foundry.methods.catalog.causal.query_preservation import (
    evaluate_query_preservation_batch,
    update_query_preservation_cache,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    FragmentCompositionData,
    GraphReconciliationData,
    LLMStructuralHint,
)
from polisyos.ir.analytics.alignment_certification import (
    AlignmentVerificationConfig,
    load_alignment_report,
    persist_alignment_report,
    verify_fragment_bundle_alignment,
)
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.cross_graph import (
    SCMFragment,
    load_composition_certificate,
    load_interface_mapping,
    load_scm_fragment,
    persist_composition_certificate,
    persist_interface_mapping,
    persist_scm_fragment,
)
from polisyos.ir.analytics.literature import load_literature_causal_prior
from polisyos.ir.refs import (
    AlignmentReportRef,
    CausalGraphModelRef,
    CompositionCertificateRef,
    InterfaceMappingRef,
    SCMFragmentRef,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
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

logger = get_logger(__name__)

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
    except Exception:
        return float(default)


def _optional_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _extract_graph(payload: Any) -> CausalGraphModel | None:
    if isinstance(payload, CausalGraphModel):
        return payload
    if isinstance(payload, dict):
        if {"graph_type", "nodes", "edges"}.issubset(payload.keys()):
            try:
                return CausalGraphModel.model_validate(payload)
            except Exception:
                return None
        for key in ("graph", "causal_graph", "reconciled_graph", "literature_prior_graph"):
            if key not in payload:
                continue
            try:
                return CausalGraphModel.model_validate(payload[key])
            except Exception:
                continue
    return None


def _load_data_graph(ctx: ExecutionContext, state: ExperimentState) -> tuple[CausalGraphModel | None, Any | None]:
    if "data_causal_graph" in state.params:
        graph = _extract_graph(state.params.get("data_causal_graph"))
        if graph is not None:
            return graph, None

    method_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_METHOD_RESULT_REF)
    if method_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(method_ref.artifact_id))
            graph = _extract_graph(payload)
            if graph is not None:
                return graph, method_ref
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

    return None, None


def _parse_llm_hints(raw: Any) -> list[LLMStructuralHint]:
    if not isinstance(raw, list):
        return []
    hints: list[LLMStructuralHint] = []
    for item in raw:
        try:
            hints.append(LLMStructuralHint.model_validate(item))
        except Exception:
            continue
    return hints


def _composition_requested(state: ExperimentState) -> bool:
    return "scm_fragment_refs" in state.params or "scm_fragments" in state.params


def _parse_fragment_ref(value: Any) -> SCMFragmentRef | None:
    try:
        if isinstance(value, str):
            return SCMFragmentRef.model_validate({"artifact_id": value})
        return SCMFragmentRef.model_validate(value)
    except Exception:
        return None


def _load_scm_fragments(ctx: ExecutionContext, state: ExperimentState) -> list[SCMFragment]:
    raw_fragments = state.params.get("scm_fragments")
    if isinstance(raw_fragments, list):
        fragments: list[SCMFragment] = []
        for item in raw_fragments:
            try:
                fragments.append(item if isinstance(item, SCMFragment) else SCMFragment.model_validate(item))
            except Exception:
                continue
        return fragments

    raw_refs = state.params.get("scm_fragment_refs")
    if not isinstance(raw_refs, list):
        return []
    fragments = []
    for item in raw_refs:
        ref = _parse_fragment_ref(item)
        if ref is None:
            continue
        try:
            fragments.append(load_scm_fragment(ctx.store, ref))
        except Exception:
            continue
    return fragments


def _load_fragment_graphs(
    ctx: ExecutionContext,
    fragments: list[SCMFragment],
) -> dict[str, CausalGraphModel]:
    graphs: dict[str, CausalGraphModel] = {}
    for fragment in fragments:
        ref = CausalGraphModelRef.model_validate({"artifact_id": fragment.graph_ref})
        graphs[fragment.fragment_id] = load_causal_graph_model(ctx.store, ref)
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
                fragment = load_scm_fragment(ctx.store, ref)
            except Exception:
                continue
            source_fragment_refs[fragment.fragment_id] = str(ref.artifact_id)

    for fragment in sorted(fragments, key=lambda item: item.fragment_id):
        if fragment.fragment_id not in source_fragment_refs:
            persisted_ref = persist_scm_fragment(ctx.store, fragment)
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
        try:
            report = load_alignment_report(ctx.store, AlignmentReportRef.model_validate(report_ref))
        except Exception:
            report = None
    if mapping_ref is not None:
        try:
            mapping = load_interface_mapping(ctx.store, InterfaceMappingRef.model_validate(mapping_ref))
        except Exception:
            mapping = None
    return report, mapping, report_ref, mapping_ref


def _parse_query_preservation_queries(raw: Any) -> list[CausalQuery]:
    if not isinstance(raw, list):
        return []
    queries: list[CausalQuery] = []
    for item in raw:
        try:
            queries.append(item if isinstance(item, CausalQuery) else CausalQuery.model_validate(item))
        except Exception:
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
        composed_graph = load_causal_graph_model(
            ctx.store,
            CausalGraphModelRef.model_validate(graph_ref_payload),
        )
        certificate = load_composition_certificate(
            ctx.store,
            CompositionCertificateRef.model_validate(certificate_ref_payload),
        )
        interface_mapping = load_interface_mapping(
            ctx.store,
            InterfaceMappingRef.model_validate(mapping_ref_payload),
        )
    except Exception as exc:
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"failed to load composition artifacts for query preservation: {exc}",
            ),
        )

    fragments = _load_scm_fragments(ctx, state)
    fragment_graphs: dict[str, CausalGraphModel] = {}
    if certificate.source_fragment_refs:
        try:
            provenance_fragments: list[SCMFragment] = []
            for fragment_id, artifact_id in sorted(certificate.source_fragment_refs.items()):
                loaded = load_scm_fragment(
                    ctx.store,
                    SCMFragmentRef.model_validate({"artifact_id": artifact_id}),
                )
                if loaded.fragment_id == fragment_id:
                    provenance_fragments.append(loaded)
            provenance_graph_refs = (
                certificate.source_fragment_graph_refs
                or {
                    fragment.fragment_id: str(fragment.graph_ref)
                    for fragment in provenance_fragments
                }
            )
            fragment_graphs = {
                fragment_id: load_causal_graph_model(
                    ctx.store,
                    CausalGraphModelRef.model_validate({"artifact_id": graph_ref}),
                )
                for fragment_id, graph_ref in sorted(provenance_graph_refs.items())
            }
            if provenance_fragments:
                fragments = provenance_fragments
        except Exception:
            fragment_graphs = {}

    if not fragment_graphs and fragments:
        try:
            fragment_graphs = _load_fragment_graphs(ctx, fragments)
        except Exception:
            fragment_graphs = {}

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
    certificate_ref = persist_composition_certificate(ctx.store, updated_certificate)

    new_state = state.model_copy(deep=True)
    new_state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF] = certificate_ref
    diagnostics = dict(new_state.params.get("reconciliation_diagnostics", {}))
    diagnostics["query_preservation_statuses"] = dict(query_statuses)
    diagnostics["query_preservation_reasons"] = {
        fingerprint: trace.reason_code
        for fingerprint, trace in sorted(traces.items())
    }
    new_state.params["reconciliation_diagnostics"] = diagnostics

    return NodeOutcome(
        status="ok",
        state=new_state,
        artifacts=[certificate_ref],
        events=[
            NodeEvent(
                level="info",
                message=f"Query preservation checked for {len(query_statuses)} query fingerprints.",
            )
        ],
    )


@dataclass(frozen=True)
class ReconcileCausalGraphNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        query_preservation_queries = _parse_query_preservation_queries(
            state.params.get("query_preservation_queries")
        )
        if ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in state.artifacts_index and query_preservation_queries:
            hook_outcome = _apply_query_preservation_hook(ctx, state, query_preservation_queries)
            if hook_outcome is not None:
                return hook_outcome
        if ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        if _composition_requested(state):
            fragments = _load_scm_fragments(ctx, state)
            direct_stitch_pairs = _parse_direct_stitch_pairs(state.params.get("direct_stitch_pairs"))
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
            except Exception as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=f"failed to load fragment graphs for composition: {exc}",
                    ),
                )

            alignment_report, interface_mapping, alignment_report_ref, interface_mapping_ref = (
                _load_precomputed_alignment(ctx, state)
            )
            requested_selected_pairs = sorted(
                tuple(sorted(pair))
                for pair in direct_stitch_pairs
            )
            precomputed_selected_pairs = []
            if alignment_report is not None:
                precomputed_selected_pairs = sorted(
                    tuple(sorted((str(pair[0]), str(pair[1]))))
                    for pair in alignment_report.metadata.get("selected_stitch_pairs", [])
                    if isinstance(pair, (list, tuple)) and len(pair) == 2
                )
            reuse_precomputed_alignment = bool(
                alignment_report is not None
                and interface_mapping is not None
                and (
                    not requested_selected_pairs
                    or requested_selected_pairs == precomputed_selected_pairs
                )
            )
            if not reuse_precomputed_alignment:
                try:
                    verification_config = AlignmentVerificationConfig.model_validate(
                        state.params.get("alignment_verification_config", {})
                    )
                    alignment_report, interface_mapping = verify_fragment_bundle_alignment(
                        fragments,
                        config=verification_config,
                        stitch_pairs=direct_stitch_pairs,
                    )
                except Exception as exc:
                    return NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                            message=f"fragment alignment verification failed: {exc}",
                        ),
                    )
                alignment_report_ref = persist_alignment_report(ctx.store, alignment_report)
                interface_mapping_ref = persist_interface_mapping(ctx.store, interface_mapping)

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
            except Exception as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                        message=f"compose_scm_fragments execution failed: {exc}",
                    ),
                )

            artifacts = []
            graph_ref = None
            composed_graph = result.get("composed_graph")
            if composed_graph is not None:
                graph_ref = persist_causal_graph_model(ctx.store, composed_graph)
                artifacts.append(graph_ref)

            certificate = result["composition_certificate"]
            if graph_ref is not None:
                certificate = certificate.model_copy(
                    update={"composed_graph_ref": str(graph_ref.artifact_id)}
                )
            query_statuses: dict[str, str] = {}
            query_reasons: dict[str, str] = {}
            query_traces: dict[str, dict[str, object]] = {}
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
                query_reasons = {
                    fingerprint: trace.reason_code
                    for fingerprint, trace in sorted(traces.items())
                }
                query_traces = {
                    fingerprint: {
                        "status": trace.status,
                        "reason_code": trace.reason_code,
                        "source_fragment_id": trace.source_fragment_id,
                        "witness_fragment_ids": list(trace.witness_fragment_ids),
                        "source_witness_kind": trace.source_witness_kind,
                        "assumption_boundary": trace.assumption_boundary,
                    }
                    for fingerprint, trace in sorted(traces.items())
                }
            failure_card_bundle_ref = None
            failure_cards = result.get("failure_cards", [])
            if failure_cards:
                failure_card_bundle = CompositionFailureCardBundle(
                    cards=failure_cards,
                    metadata={
                        "composition_status": certificate.status,
                        "structure_status": certificate.structure_status,
                        "review_status": certificate.review_status,
                        "source_fragment_ids": sorted(fragment.fragment_id for fragment in fragments),
                    },
                )
                failure_card_bundle_ref = persist_composition_failure_card_bundle(
                    ctx.store,
                    failure_card_bundle,
                )
                certificate = certificate.model_copy(
                    update={"failure_card_bundle_ref": str(failure_card_bundle_ref.artifact_id)}
                )
            certificate_ref = persist_composition_certificate(ctx.store, certificate)
            artifacts.extend([alignment_report_ref, interface_mapping_ref, certificate_ref])
            if failure_card_bundle_ref is not None:
                artifacts.append(failure_card_bundle_ref)

            new_state = state.model_copy(deep=True)
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

        data_graph, data_graph_ref = _load_data_graph(ctx, state)
        if data_graph is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="No data causal graph; skip reconciliation.")],
            )

        literature_prior_ref = state.artifacts_index.get(ARTIFACT_LITERATURE_PRIOR_REF)
        literature_prior = None
        if literature_prior_ref is not None:
            try:
                literature_prior = load_literature_causal_prior(ctx.store, literature_prior_ref)
            except Exception:
                literature_prior = None

        llm_hints = _parse_llm_hints(state.params.get("llm_structural_hints"))

        try:
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
        except Exception as exc:
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
            inputs.append(InputRef(artifact_id=str(data_graph_ref.artifact_id), role="data_graph"))
        if literature_prior_ref is not None:
            inputs.append(
                InputRef(
                    artifact_id=str(literature_prior_ref.artifact_id),
                    role="literature_prior",
                )
            )
        graph_ref = persist_causal_graph_model(ctx.store, reconciled_graph, inputs=inputs)

        new_state = state.model_copy(deep=True)
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


__all__ = ["ReconcileCausalGraphNode"]
