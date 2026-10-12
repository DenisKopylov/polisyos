"""Public planning compile cross graph evidence module API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts import (
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import (
    CrossGraphDiagnostic,
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    CrossGraphSourceRefs,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
    build_evidence_need_id,
    persist_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.literature import load_literature_causal_prior
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.cross_graph.feedback import (
    append_need_backlog,
    build_need_backlog,
    evaluate_benchmark_suite,
    load_benchmark_suite,
    write_need_backlog,
)
from polisyos.scientist.evidence.sources import (
    build_path_source_status,
    merge_evidence_sources_payload,
    normalize_evidence_sources_config,
    update_source_status,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
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

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
    from polisyos.scientist.cross_graph.compiler import CrossGraphEvidenceConfig

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_compile_cross_graph_evidence@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Compile Cross-Graph Evidence",
    description="Compile legal, dataset, and academic evidence into a unified profile.",
    tags=["builtin", "planning", "evidence"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        f"inputs.{INPUT_GRAPH_PRIOR_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_LITERATURE_PRIOR_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
        "policy_request_ref",
        "params.cross_graph_evidence_config",
        "params.evidence_sources",
        "params.target_context",
        "params.governance_profile",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF}",
        "params.cross_graph_evidence_expected",
        "params.cross_graph_evidence_summary",
        "params.cross_graph_benchmark_summary",
    ],
    produces=[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF],
)

_CROSS_GRAPH_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_CROSS_GRAPH_RUNTIME_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_CROSS_GRAPH_IMPORT_RUNTIME_ERRORS = (
    ImportError,
    ModuleNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_DISCOVERY_IDENTIFICATION_LIMITATION_REASON = "discovery_hypothesis_identification_limited"


@dataclass(frozen=True)
class CompileCrossGraphEvidenceNode:
    """Compile cross graph evidence node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def prepare_cache_input(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> PreparedSKGRead | None:
        """Bind cache lookup to the source database selected by cross-graph config."""
        del ctx
        config_payload = state.params.get("cross_graph_evidence_config")
        if (
            state.inputs.get(INPUT_TRINITY_BUNDLE_REF) is None
            or str(state.params.get("governance_profile", "")).strip().lower() == "fast"
            or not isinstance(config_payload, dict)
            or not bool(config_payload.get("enabled", True))
        ):
            return None
        try:
            from polisyos.scientist.cross_graph.compiler import CrossGraphEvidenceConfig

            evidence_sources = normalize_evidence_sources_config(state.params, config_payload)
            config = CrossGraphEvidenceConfig.model_validate(
                merge_evidence_sources_payload(config_payload, evidence_sources)
            )
        except (TypeError, ValueError, ValidationError):
            return None
        db_path_raw = str(config.academic_db_path or "").strip()
        if not db_path_raw:
            return None
        db_path = Path(db_path_raw)
        index_dir = Path(config.academic_index_dir) if config.academic_index_dir else db_path.parent
        if not index_dir.exists():
            index_dir = db_path.parent
        return SKGQuery.prepare_read(db_path=db_path, index_dir=index_dir)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        config_payload = state.params.get("cross_graph_evidence_config")
        evidence_sources = normalize_evidence_sources_config(state.params, config_payload)
        governance_profile = str(state.params.get("governance_profile", "")).strip().lower()
        expected = isinstance(config_payload, dict) and bool(config_payload.get("enabled", True))
        new_state.params["cross_graph_evidence_expected"] = bool(expected)

        if governance_profile == "fast":
            new_state.params["cross_graph_evidence_expected"] = False
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[
                    NodeEvent(
                        level="info",
                        message="FAST governance profile skips cross-graph evidence compilation.",
                    )
                ],
            )

        if not expected:
            return NodeOutcome(status="skip", state=new_state)

        trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
        target_context = _resolve_target_context(state)
        try:
            causal_graph_ref, causal_graph = _resolve_causal_graph(ctx, state)
        except _InvalidCausalGraphReference as exc:
            return NodeOutcome(
                status="fail",
                state=new_state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid supplied causal graph reference: {exc}",
                    details={"input": ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF},
                ),
            )

        try:
            from polisyos.scientist.cross_graph.compiler import CrossGraphEvidenceConfig

            config = CrossGraphEvidenceConfig.model_validate(
                merge_evidence_sources_payload(config_payload, evidence_sources)
            )
        except _CROSS_GRAPH_VALIDATION_ERRORS as exc:
            profile = CrossGraphEvidenceProfile(
                summary=CrossGraphEvidenceSummary(status="degraded", total_needs=0),
                diagnostics=[
                    CrossGraphDiagnostic(
                        code="cross_graph.invalid_config",
                        message="Cross-graph evidence config validation failed.",
                        details={"error": str(exc)},
                    )
                ],
                source_refs=CrossGraphSourceRefs(
                    academic_db_path=evidence_sources.academic_db_path,
                    academic_index_dir=evidence_sources.academic_index_dir,
                    datasets_db_path=evidence_sources.datasets_db_path,
                    legal_db_path=evidence_sources.legal_db_path,
                ),
                source_statuses=_initial_source_statuses(evidence_sources),
                benchmark_summary={
                    "status": "degraded",
                    "reason": "invalid_config",
                    "detail": str(exc),
                },
                target_context=target_context,
                notes=["cross_graph_invalid_config"],
            )
            profile_ref = persist_cross_graph_evidence_profile(
                _ensure_ir_artifact_store(ctx.store), profile
            )
            new_state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF] = profile_ref
            new_state.params["cross_graph_evidence_summary"] = profile.summary.model_dump(
                mode="json"
            )
            new_state.params["cross_graph_benchmark_summary"] = dict(profile.benchmark_summary)
            return NodeOutcome(
                status="ok",
                state=new_state,
                artifacts=[profile_ref],
                events=[
                    NodeEvent(
                        level="warn",
                        message=f"Invalid cross-graph evidence config; persisted degraded profile ({exc}).",
                    )
                ],
            )

        inputs: list[InputRef] = []
        if trinity_ref is not None:
            inputs.append(InputRef(artifact_id=str(trinity_ref.artifact_id), role="trinity_bundle"))
        graph_prior_ref = state.inputs.get(INPUT_GRAPH_PRIOR_BUNDLE_REF)
        if graph_prior_ref is not None:
            inputs.append(
                InputRef(
                    artifact_id=str(graph_prior_ref.artifact_id),
                    role="graph_prior_bundle",
                )
            )
        graph_ref = causal_graph_ref
        if graph_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                    role="causal_graph",
                )
            )
        literature_prior_ref = state.artifacts_index.get(ARTIFACT_LITERATURE_PRIOR_REF)
        if literature_prior_ref is not None:
            inputs.append(
                InputRef(
                    artifact_id=str(literature_prior_ref.artifact_id),
                    role="literature_prior",
                )
            )

        owned_prepared_read: PreparedSKGRead | None = None
        prepared_read = ctx.prepared_skg_read
        try:
            if trinity_ref is None:
                profile = CrossGraphEvidenceProfile(
                    summary=CrossGraphEvidenceSummary(status="ok", total_needs=0),
                    diagnostics=[
                        CrossGraphDiagnostic(
                            code="cross_graph.policy_request_only",
                            message="Cross-graph evidence compiled without Trinity bundle in policy-verified mode.",
                        )
                    ],
                    source_refs=CrossGraphSourceRefs(
                        academic_db_path=config.academic_db_path,
                        academic_index_dir=config.academic_index_dir,
                        datasets_db_path=config.datasets_db_path,
                        legal_db_path=config.legal_db_path,
                    ),
                    source_statuses=_initial_source_statuses(evidence_sources),
                    benchmark_summary={},
                    target_context=target_context,
                    notes=["policy_request_only_mode"],
                )
            else:
                if prepared_read is None and config.academic_db_path:
                    db_path = Path(config.academic_db_path)
                    index_dir = (
                        Path(config.academic_index_dir)
                        if config.academic_index_dir
                        else db_path.parent
                    )
                    if not index_dir.exists():
                        index_dir = db_path.parent
                    owned_prepared_read = SKGQuery.prepare_read(
                        db_path=db_path,
                        index_dir=index_dir,
                    )
                    prepared_read = owned_prepared_read
                payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref))
                bundle = TrinityBundle.model_validate(payload)
                literature_prior = (
                    load_literature_causal_prior(
                        _ensure_ir_artifact_store(ctx.store), literature_prior_ref
                    )
                    if literature_prior_ref is not None
                    else None
                )
                from polisyos.scientist.cross_graph.compiler import CrossGraphEvidenceCompiler

                profile = CrossGraphEvidenceCompiler(config).compile(
                    bundle,
                    target_context=target_context,
                    causal_graph=causal_graph,
                    literature_prior=literature_prior,
                    literature_prior_ref=(
                        str(literature_prior_ref.artifact_id)
                        if literature_prior_ref is not None
                        else None
                    ),
                    prepared_skg_read=prepared_read,
                )
        except _CROSS_GRAPH_RUNTIME_ERRORS as exc:
            profile = CrossGraphEvidenceProfile(
                summary=CrossGraphEvidenceSummary(status="warning", total_needs=0),
                diagnostics=[
                    CrossGraphDiagnostic(
                        code="cross_graph.compile.failed",
                        message="Cross-graph evidence compilation failed.",
                        details={"error": str(exc)},
                    )
                ],
                source_refs=CrossGraphSourceRefs(
                    academic_db_path=config.academic_db_path,
                    academic_index_dir=config.academic_index_dir,
                    datasets_db_path=config.datasets_db_path,
                    legal_db_path=config.legal_db_path,
                ),
                source_statuses=_initial_source_statuses(evidence_sources),
                benchmark_summary={},
                target_context=target_context,
                notes=["cross_graph_compile_failed"],
            )
        finally:
            if owned_prepared_read is not None:
                owned_prepared_read.close()

        profile = _augment_with_graph_prior(ctx, profile, state)
        extra_events: list[NodeEvent] = []
        benchmark_summary, benchmark_status = _maybe_emit_feedback_outputs(
            config,
            profile,
            new_state.params,
            extra_events,
        )
        profile = profile.model_copy(
            update={
                "source_statuses": {
                    **dict(profile.source_statuses),
                    EvidenceSourceKind.BENCHMARK.value: benchmark_status,
                },
                "benchmark_summary": dict(benchmark_summary),
            }
        )
        profile_ref = persist_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(ctx.store), profile, inputs=inputs
        )
        new_state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF] = profile_ref
        new_state.params["cross_graph_evidence_summary"] = profile.summary.model_dump(mode="json")
        new_state.params["cross_graph_benchmark_summary"] = dict(benchmark_summary)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[profile_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Cross-graph evidence profile compiled "
                        f"(needs={profile.summary.total_needs}, status={profile.summary.status})."
                    ),
                ),
                *extra_events,
            ],
        )


def _resolve_target_context(state: ExperimentState) -> ContextProfile | None:
    payload = state.params.get("target_context")
    if payload is None:
        return None
    try:
        return ContextProfile.model_validate(payload)
    except _CROSS_GRAPH_VALIDATION_ERRORS:
        return None


class _InvalidCausalGraphReference(ValueError):
    """Identify a supplied graph selector that is malformed or stale."""


def _resolve_causal_graph(
    ctx: ExecutionContext,
    state: ExperimentState,
):
    ref = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
    if ref is None:
        return None, None
    store = _ensure_ir_artifact_store(ctx.store)
    try:
        payload = ref.model_dump(mode="json") if hasattr(ref, "model_dump") else ref
        selected_ref = profile_bound_ref(
            store, CausalGraphModelRef.model_validate(payload)
        )
        graph = load_causal_graph_model(store, selected_ref)
    except _CROSS_GRAPH_RUNTIME_ERRORS as exc:
        raise _InvalidCausalGraphReference(
            "the selected graph could not be profile-bound and loaded"
        ) from exc
    return selected_ref, graph


def _augment_with_graph_prior(
    ctx: ExecutionContext,
    profile: CrossGraphEvidenceProfile,
    state: ExperimentState,
) -> CrossGraphEvidenceProfile:
    ref = state.inputs.get(INPUT_GRAPH_PRIOR_BUNDLE_REF)
    if ref is None:
        return profile

    try:
        from polisyos.core.contracts.scientist import GraphPriorBundleRef
        from polisyos.scientist.methods.discovery.priors import load_graph_prior_bundle

        graph_prior_ref = GraphPriorBundleRef.model_validate(ref.model_dump(mode="json"))
        bundle = load_graph_prior_bundle(ctx.store, graph_prior_ref)
        source_identification = _source_verified_identification_rows(ctx.store, graph_prior_ref, bundle)
    except _CROSS_GRAPH_IMPORT_RUNTIME_ERRORS as exc:
        diagnostics = [
            *profile.diagnostics,
            CrossGraphDiagnostic(
                code="cross_graph.graph_prior_bundle.load_failed",
                message="GraphPriorBundle could not be loaded; discovery prior enrichment skipped.",
                details={"error": str(exc)},
            ),
        ]
        notes = [*profile.notes, "graph_prior_bundle_enrichment_failed"]
        enriched = profile.model_copy(update={"diagnostics": diagnostics, "notes": notes})
        return enriched.model_copy(update={"summary": _rebuild_summary(enriched)})

    extra_needs = [
        *[
            _assessment_from_prior_edge(
                edge,
                source_label="required",
                hypothesis_identification=source_identification,
            )
            for edge in bundle.required_edges
        ],
        *[
            _assessment_from_prior_edge(
                edge,
                source_label="high_confidence",
                hypothesis_identification=source_identification,
            )
            for edge in bundle.high_confidence_edges
        ],
        *[
            _assessment_from_disputed_candidate(
                candidate,
                dispute_id=disputed.dispute_id,
                dispute_reasons=disputed.dispute_reasons,
                hypothesis_identification=source_identification,
            )
            for disputed in bundle.disputed_edges
            for candidate in disputed.candidate_edges
        ],
    ]
    extra_diagnostics = [
        *profile.diagnostics,
        *[
            CrossGraphDiagnostic(
                code=f"cross_graph.discovery_prior.{label}",
                severity="info" if label != "disputed" else "warn",
                need_id=assessment.need.need_id,
                message=f"Discovery prior surfaced via GraphPriorBundle ({label}).",
                details={
                    "cause": assessment.need.cause,
                    "effect": assessment.need.effect,
                    "confidence": assessment.confidence,
                },
            )
            for assessment, label in _labeled_assessments(extra_needs)
        ],
    ]
    enriched = profile.model_copy(
        update={
            "needs": [*profile.needs, *extra_needs],
            "diagnostics": extra_diagnostics,
            "notes": [
                *profile.notes,
                "graph_prior_bundle_enriched",
            ],
        }
    )
    return enriched.model_copy(update={"summary": _rebuild_summary(enriched)})


def _assessment_from_prior_edge(
    edge: Any,
    *,
    source_label: str,
    hypothesis_identification: dict[str, Any],
) -> EvidenceNeedAssessment:
    identification_records, identification_limited = _hypothesis_identification_projection(
        edge,
        hypothesis_identification,
    )
    labels = [f"discovery_{source_label}"]
    blocking_reasons: list[str] = []
    diagnostics: list[CrossGraphDiagnostic] = []
    recommended_actions = [f"preserve_{source_label}_discovery_edge"]
    if identification_limited:
        labels.append("discovery_limited")
        blocking_reasons.append(_DISCOVERY_IDENTIFICATION_LIMITATION_REASON)
        recommended_actions.append("review_discovery_hypothesis_identification_before_use")
        diagnostics.append(
            CrossGraphDiagnostic(
                code="cross_graph.discovery_prior.identification_limited",
                severity="warn",
                message=(
                    "Discovery edge support includes hypotheses without fully identified status."
                ),
                details={"hypothesis_identification": identification_records},
            )
        )
    need = EvidenceNeed(
        need_id=build_evidence_need_id(
            EvidenceNeedType.CAUSAL_EDGE_NEED,
            source_path="scientist.discovery.graph_prior_bundle",
            payload={
                "edge_key": edge.edge_key,
                "source_label": source_label,
            },
        ),
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="scientist.discovery.graph_prior_bundle",
        cause=edge.src,
        effect=edge.dst,
        labels=labels,
    )
    diagnostics = [item.model_copy(update={"need_id": need.need_id}) for item in diagnostics]
    return EvidenceNeedAssessment(
        need=need,
        legal_status=LegalStatus.UNKNOWN,
        observability_status=ObservabilityStatus.UNKNOWN,
        evidence_status=(
            EvidenceStatus.INSUFFICIENT if identification_limited else EvidenceStatus.SUPPORTED
        ),
        transport_status=TransportStatus.UNSUPPORTED,
        confidence=float(edge.presence_confidence),
        requires_expert_review=identification_limited,
        blocking_reasons=blocking_reasons,
        recommended_actions=recommended_actions,
        provenance_refs=list(edge.provenance_refs),
        diagnostics=diagnostics,
    )


def _assessment_from_disputed_candidate(
    edge: Any,
    *,
    dispute_id: str,
    dispute_reasons: list[str],
    hypothesis_identification: dict[str, Any],
) -> EvidenceNeedAssessment:
    identification_records, identification_limited = _hypothesis_identification_projection(
        edge,
        hypothesis_identification,
    )
    diagnostics = [
        CrossGraphDiagnostic(
            code="cross_graph.discovery_prior.disputed",
            severity="warn",
            message="Discovery surfaced a disputed causal edge that needs follow-up.",
            details={"dispute_id": dispute_id, "reasons": list(dispute_reasons)},
        )
    ]
    blocking_reasons: list[str] = []
    recommended_actions = ["resolve_disputed_discovery_edge"]
    if identification_limited:
        blocking_reasons.append(_DISCOVERY_IDENTIFICATION_LIMITATION_REASON)
        recommended_actions.append("review_discovery_hypothesis_identification_before_use")
        diagnostics.append(
            CrossGraphDiagnostic(
                code="cross_graph.discovery_prior.identification_limited",
                severity="warn",
                message=(
                    "Discovery edge support includes hypotheses without fully identified status."
                ),
                details={"hypothesis_identification": identification_records},
            )
        )
    labels = ["discovery_disputed"]
    if identification_limited:
        labels.append("discovery_limited")
    need = EvidenceNeed(
        need_id=build_evidence_need_id(
            EvidenceNeedType.CAUSAL_EDGE_NEED,
            source_path="scientist.discovery.graph_prior_bundle.disputed",
            payload={
                "edge_key": edge.edge_key,
                "dispute_id": dispute_id,
            },
        ),
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="scientist.discovery.graph_prior_bundle.disputed",
        cause=edge.src,
        effect=edge.dst,
        labels=labels,
    )
    diagnostics = [item.model_copy(update={"need_id": need.need_id}) for item in diagnostics]
    return EvidenceNeedAssessment(
        need=need,
        legal_status=LegalStatus.UNKNOWN,
        observability_status=ObservabilityStatus.UNKNOWN,
        evidence_status=EvidenceStatus.MIXED,
        transport_status=TransportStatus.UNSUPPORTED,
        confidence=float(edge.presence_confidence),
        requires_expert_review=True,
        blocking_reasons=blocking_reasons,
        recommended_actions=recommended_actions,
        provenance_refs=list(edge.provenance_refs),
        diagnostics=diagnostics,
    )


def _hypothesis_identification_projection(
    edge: Any,
    hypothesis_identification: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    hypothesis_ids = list(edge.supporting_hypothesis_ids or [])
    if not hypothesis_ids:
        return [{"status": "not_established", "reason": "supporting_hypothesis_ids_missing"}], True

    records: list[dict[str, Any]] = []
    limited = False
    for hypothesis_id in hypothesis_ids:
        evidence = hypothesis_identification.get(hypothesis_id)
        if evidence is None:
            records.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "status": "not_established",
                    "reason": "hypothesis_identification_record_missing",
                }
            )
            limited = True
            continue
        payload = (
            evidence.model_dump(mode="json")
            if hasattr(evidence, "model_dump")
            else dict(evidence)
        )
        records.append({"hypothesis_id": hypothesis_id, **payload})
        if (
            payload.get("verification_status") != "recomputed"
            or payload.get("identification_status") != "identified"
            or payload.get("identifiability_score", 0.0) < 1.0
            or payload.get("limitations")
            or payload.get("blocking_certificates")
        ):
            limited = True
    return records, limited


class _IdentificationSourceBindingFailure(ValueError):
    """Stable reason that a persisted identification projection cannot be source-verified."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _source_verified_identification_rows(
    store: Any,
    graph_prior_ref: Any,
    bundle: Any,
) -> dict[str, dict[str, Any]]:
    """Recompute each identification row from the exact report and source artifacts."""
    try:
        return _resolve_source_identification_rows(store, graph_prior_ref, bundle)
    except _IdentificationSourceBindingFailure as exc:
        reason = exc.code
    except (AttributeError, KeyError):
        reason = "source_artifact_shape_invalid"
    except _CROSS_GRAPH_IMPORT_RUNTIME_ERRORS:
        reason = "source_artifact_resolution_failed"

    unverified: dict[str, dict[str, Any]] = {}
    for hypothesis_id, evidence in bundle.hypothesis_identification.items():
        payload = evidence.model_dump(mode="json")
        unverified[hypothesis_id] = {
            **payload,
            "verification_status": "not_established",
            "verification_reason": reason,
            "source_refs": {"graph_prior_bundle": _ref_receipt(graph_prior_ref)},
        }
    return unverified


def _resolve_source_identification_rows(
    store: Any,
    graph_prior_ref: Any,
    bundle: Any,
) -> dict[str, dict[str, Any]]:
    """Resolve source lineage and recompute status with the current identification algorithm."""
    from polisyos.core.contracts.scientist import (
        BootstrapStabilityReportRef,
        DiscoveryTaskProfileRef,
        DownstreamUtilityReportRef,
        EdgeConfidenceMatrixRef,
        GraphHypothesisSetRef,
    )
    from polisyos.scientist.methods.discovery.aggregator import (
        EDGE_CONFIDENCE_MATRIX_SCHEMA_NAME,
        EvidenceWeightedAggregator,
        load_edge_confidence_matrix,
    )
    from polisyos.scientist.methods.discovery.output import (
        DISCOVERY_TASK_PROFILE_SCHEMA_NAME,
        GRAPH_HYPOTHESIS_SET_SCHEMA_NAME,
        load_discovery_task_profile,
        load_graph_hypothesis_set,
    )
    from polisyos.scientist.methods.discovery.priors import (
        GRAPH_PRIOR_BUNDLE_SCHEMA_NAME,
        GraphPriorBuilder,
    )
    from polisyos.scientist.methods.discovery.schema import (
        GRAPH_HYPOTHESIS_SCHEMA_NAME,
        GRAPH_HYPOTHESIS_SCHEMA_VERSION,
        load_graph_hypothesis,
    )
    from polisyos.scientist.methods.discovery.stability import (
        BOOTSTRAP_STABILITY_REPORT_SCHEMA_NAME,
        load_bootstrap_stability_report,
    )
    from polisyos.scientist.methods.discovery.utility_judge import (
        DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME,
        IDENTIFICATION_SOURCE_ALGORITHM_VERSION,
        identify_hypothesis_identification_status,
        load_downstream_utility_report,
    )

    if graph_prior_ref.manifest_profile_sha256 is None:
        raise _IdentificationSourceBindingFailure("graph_prior_manifest_profile_missing")
    graph_prior_manifest = store.get_manifest(graph_prior_ref)
    _require_source_view(
        graph_prior_ref,
        graph_prior_manifest,
        role="graph_prior_bundle",
        name=GRAPH_PRIOR_BUNDLE_SCHEMA_NAME,
        version="1.1",
    )
    if (
        graph_prior_manifest.artifact_schema is None
        or bundle.schema_version != graph_prior_manifest.artifact_schema.version
    ):
        raise _IdentificationSourceBindingFailure("graph_prior_bundle_schema_version_mismatch")
    utility_report_ref = _typed_input_ref(
        DownstreamUtilityReportRef,
        _one_manifest_input(graph_prior_manifest.inputs, role="downstream_utility_report"),
    )
    edge_confidence_matrix_ref = _typed_input_ref(
        EdgeConfidenceMatrixRef,
        _one_manifest_input(graph_prior_manifest.inputs, role="edge_confidence_matrix"),
    )
    bootstrap_stability_report_ref = _typed_input_ref(
        BootstrapStabilityReportRef,
        _one_manifest_input(graph_prior_manifest.inputs, role="bootstrap_stability_report"),
    )
    edge_confidence_matrix_manifest = store.get_manifest(edge_confidence_matrix_ref)
    bootstrap_stability_report_manifest = store.get_manifest(bootstrap_stability_report_ref)
    _require_source_view(
        edge_confidence_matrix_ref,
        edge_confidence_matrix_manifest,
        role="edge_confidence_matrix",
        name=EDGE_CONFIDENCE_MATRIX_SCHEMA_NAME,
        version="1.0",
    )
    _require_source_view(
        bootstrap_stability_report_ref,
        bootstrap_stability_report_manifest,
        role="bootstrap_stability_report",
        name=BOOTSTRAP_STABILITY_REPORT_SCHEMA_NAME,
        version="1.0",
    )
    edge_confidence_matrix = load_edge_confidence_matrix(store, edge_confidence_matrix_ref)
    bootstrap_stability_report = load_bootstrap_stability_report(
        store,
        bootstrap_stability_report_ref,
    )
    utility_report_manifest = store.get_manifest(utility_report_ref)
    _require_source_view(
        utility_report_ref,
        utility_report_manifest,
        role="downstream_utility_report",
        name=DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME,
        version="1.1",
    )
    utility_report = load_downstream_utility_report(store, utility_report_ref)
    if utility_report.schema_version != "1.1":
        raise _IdentificationSourceBindingFailure("utility_report_schema_not_source_bound")
    if (
        utility_report.metadata.get("identification_source_algorithm_version")
        != IDENTIFICATION_SOURCE_ALGORITHM_VERSION
    ):
        raise _IdentificationSourceBindingFailure("identification_algorithm_version_mismatch")

    task_profile_ref = _typed_input_ref(
        DiscoveryTaskProfileRef,
        _one_manifest_input(utility_report_manifest.inputs, role="discovery_task_profile"),
    )
    hypothesis_set_ref = _typed_input_ref(
        GraphHypothesisSetRef,
        _one_manifest_input(utility_report_manifest.inputs, role="graph_hypothesis_set"),
    )
    task_profile_manifest = store.get_manifest(task_profile_ref)
    hypothesis_set_manifest = store.get_manifest(hypothesis_set_ref)
    _require_source_view(
        task_profile_ref,
        task_profile_manifest,
        role="discovery_task_profile",
        name=DISCOVERY_TASK_PROFILE_SCHEMA_NAME,
        version="1.0",
    )
    _require_source_view(
        hypothesis_set_ref,
        hypothesis_set_manifest,
        role="graph_hypothesis_set",
        name=GRAPH_HYPOTHESIS_SET_SCHEMA_NAME,
        version="1.0",
    )
    linked_task_profile_ref = _typed_input_ref(
        DiscoveryTaskProfileRef,
        _one_manifest_input(hypothesis_set_manifest.inputs, role="discovery_task_profile"),
    )
    if (
        linked_task_profile_ref.artifact_id != task_profile_ref.artifact_id
        or linked_task_profile_ref.manifest_profile_sha256
        != task_profile_ref.manifest_profile_sha256
    ):
        raise _IdentificationSourceBindingFailure("hypothesis_task_profile_input_mismatch")
    task_profile = load_discovery_task_profile(store, task_profile_ref)
    hypothesis_set = load_graph_hypothesis_set(store, hypothesis_set_ref)
    if task_profile.causal_query is None:
        raise _IdentificationSourceBindingFailure("causal_query_missing")
    if (
        hypothesis_set.metadata.get("run_id") != task_profile.run_id
        or hypothesis_set.metadata.get("task_id") != task_profile.task_id
    ):
        raise _IdentificationSourceBindingFailure("hypothesis_task_profile_mismatch")

    now = datetime.now(UTC)
    source_manifests = [
        task_profile_manifest,
        hypothesis_set_manifest,
        edge_confidence_matrix_manifest,
        bootstrap_stability_report_manifest,
    ]
    all_manifests = [graph_prior_manifest, utility_report_manifest, *source_manifests]
    if any(manifest.created_at > now for manifest in all_manifests):
        raise _IdentificationSourceBindingFailure("source_manifest_time_invalid")
    if utility_report_manifest.created_at > graph_prior_manifest.created_at:
        raise _IdentificationSourceBindingFailure("source_manifest_time_order_invalid")
    if any(manifest.created_at > utility_report_manifest.created_at for manifest in source_manifests):
        raise _IdentificationSourceBindingFailure("source_manifest_time_order_invalid")

    hypotheses: dict[str, Any] = {}
    hypothesis_refs: dict[str, Any] = {}
    hypothesis_manifests: dict[str, Any] = {}
    for hypothesis_ref in hypothesis_set.graph_hypothesis_refs:
        if hypothesis_ref.manifest_profile_sha256 is None:
            raise _IdentificationSourceBindingFailure("hypothesis_manifest_profile_missing")
        hypothesis_manifest = store.get_manifest(hypothesis_ref)
        _require_source_view(
            hypothesis_ref,
            hypothesis_manifest,
            role="graph_hypothesis",
            name=GRAPH_HYPOTHESIS_SCHEMA_NAME,
            version=GRAPH_HYPOTHESIS_SCHEMA_VERSION,
        )
        if hypothesis_manifest.created_at > utility_report_manifest.created_at:
            raise _IdentificationSourceBindingFailure("source_manifest_time_order_invalid")
        hypothesis = load_graph_hypothesis(store, hypothesis_ref)
        if hypothesis.hypothesis_id in hypotheses:
            raise _IdentificationSourceBindingFailure("hypothesis_id_duplicate")
        hypotheses[hypothesis.hypothesis_id] = hypothesis
        hypothesis_refs[hypothesis.hypothesis_id] = hypothesis_ref
        hypothesis_manifests[hypothesis.hypothesis_id] = hypothesis_manifest

    scores = {score.hypothesis_id: score for score in utility_report.scores}
    if len(scores) != len(utility_report.scores):
        raise _IdentificationSourceBindingFailure("utility_report_hypothesis_id_duplicate")
    if set(scores) != set(hypotheses):
        raise _IdentificationSourceBindingFailure("utility_report_hypothesis_set_mismatch")
    if len(hypothesis_set.graph_hypothesis_refs) != len(hypotheses):
        raise _IdentificationSourceBindingFailure("hypothesis_set_id_duplicate")

    recomputed_matrix = EvidenceWeightedAggregator().aggregate(
        list(hypotheses.values()),
        bootstrap_stability_report,
        utility_report,
    )
    if _canonical_payload_sha256(recomputed_matrix) != _canonical_payload_sha256(
        edge_confidence_matrix
    ):
        raise _IdentificationSourceBindingFailure(
            "edge_confidence_matrix_source_projection_mismatch"
        )
    expected_graph_prior = GraphPriorBuilder().build(recomputed_matrix, utility_report)
    _require_graph_prior_source_projection(bundle, expected_graph_prior)

    supported_hypothesis_ids = {
        hypothesis_id
        for edge in [
            *expected_graph_prior.required_edges,
            *expected_graph_prior.high_confidence_edges,
            *expected_graph_prior.forbidden_edges,
        ]
        for hypothesis_id in (edge.supporting_hypothesis_ids or [])
    }
    supported_hypothesis_ids.update(
        hypothesis_id
        for disputed in expected_graph_prior.disputed_edges
        for edge in disputed.candidate_edges
        for hypothesis_id in (edge.supporting_hypothesis_ids or [])
    )
    expected_by_id: dict[str, dict[str, Any]] = {}
    for hypothesis_id, score in scores.items():
        hypothesis = hypotheses[hypothesis_id]
        projection = identify_hypothesis_identification_status(
            hypothesis,
            task_profile.causal_query,
        )
        if (
            score.identification_status != projection.identification_status
            or float(score.identifiability_score) != projection.identifiability_score
            or not set(projection.reasons).issubset(score.reasons)
            or not set(projection.warnings).issubset(score.warnings)
            or not set(projection.blocking_certificates).issubset(score.blocking_certificates)
        ):
            raise _IdentificationSourceBindingFailure("utility_report_source_projection_mismatch")

        # Recompute the same selected graph that DownstreamUtilityJudge used.
        # A raw/resolved basis difference remains unverified without a qualified translation proof.
        raw_graph_sha256 = _graph_basis_sha256(hypothesis.graph)
        report_graph = hypothesis.graph_for_analysis() or hypothesis.graph
        report_graph_sha256 = _graph_basis_sha256(report_graph)
        source_projection = projection
        source_graph_mismatch = (
            hypothesis_id in supported_hypothesis_ids
            and raw_graph_sha256 != report_graph_sha256
        )

        snapshot = bundle.hypothesis_identification.get(hypothesis_id)
        report_limitations = [
            reason
            for reason in score.reasons
            if reason.startswith("identifiability:") and reason != "identifiability:identified"
        ]
        if (
            snapshot is None
            or snapshot.identification_status != score.identification_status
            or float(snapshot.identifiability_score) != float(score.identifiability_score)
            or snapshot.limitations != report_limitations
            or snapshot.reasons != score.reasons
            or snapshot.warnings != score.warnings
            or snapshot.blocking_certificates != score.blocking_certificates
        ):
            raise _IdentificationSourceBindingFailure("graph_prior_snapshot_mismatch")

        source_reasons = (
            list(source_projection.reasons) if source_graph_mismatch else list(score.reasons)
        )
        source_warnings = (
            list(source_projection.warnings) if source_graph_mismatch else list(score.warnings)
        )
        source_blocking = (
            list(source_projection.blocking_certificates)
            if source_graph_mismatch
            else list(score.blocking_certificates)
        )
        source_limitations = [
            reason
            for reason in source_reasons
            if reason.startswith("identifiability:") and reason != "identifiability:identified"
        ]
        expected_by_id[hypothesis_id] = {
            "identification_status": source_projection.identification_status,
            "identifiability_score": source_projection.identifiability_score,
            "limitations": source_limitations,
            "reasons": source_reasons,
            "warnings": source_warnings,
            "blocking_certificates": source_blocking,
            "reported_identification_status": projection.identification_status,
            "verification_status": "not_established" if source_graph_mismatch else "recomputed",
            "verification_reason": (
                "aggregation_report_graph_basis_mismatch"
                if source_graph_mismatch and raw_graph_sha256 != report_graph_sha256
                else "aggregation_report_projection_mismatch"
                if source_graph_mismatch
                else "source_projection_matches_current_algorithm"
            ),
            "source_algorithm_version": IDENTIFICATION_SOURCE_ALGORITHM_VERSION,
            "source_refs": {
                "graph_prior_bundle": _ref_receipt(graph_prior_ref, graph_prior_manifest),
                "utility_report": _ref_receipt(utility_report_ref, utility_report_manifest),
                "graph_hypothesis_set": _ref_receipt(hypothesis_set_ref, hypothesis_set_manifest),
                "discovery_task_profile": _ref_receipt(task_profile_ref, task_profile_manifest),
                "graph_hypothesis": _ref_receipt(
                    hypothesis_refs[hypothesis_id],
                    hypothesis_manifests[hypothesis_id],
                ),
                "edge_confidence_matrix": _ref_receipt(
                    edge_confidence_matrix_ref,
                    edge_confidence_matrix_manifest,
                ),
                "bootstrap_stability_report": _ref_receipt(
                    bootstrap_stability_report_ref,
                    bootstrap_stability_report_manifest,
                ),
            },
            "source_basis": {
                "aggregation_graph_sha256": raw_graph_sha256,
                "utility_report_graph_sha256": report_graph_sha256,
                "edge_confidence_matrix_sha256": _ref_receipt(
                    edge_confidence_matrix_ref,
                    edge_confidence_matrix_manifest,
                )["payload_sha256"],
                "same_basis": raw_graph_sha256 == report_graph_sha256,
            },
            "recomputed_at": now.isoformat(),
        }

    return expected_by_id


def _one_manifest_input(inputs: list[InputRef], *, role: str) -> InputRef:
    matches = [item for item in inputs if item.role == role]
    if len(matches) != 1:
        raise _IdentificationSourceBindingFailure(f"{role}_input_missing_or_ambiguous")
    return matches[0]


def _typed_input_ref(ref_cls: type[Any], input_ref: InputRef) -> Any:
    if input_ref.manifest_profile_sha256 is None:
        raise _IdentificationSourceBindingFailure(f"{input_ref.role}_manifest_profile_missing")
    return ref_cls.model_validate(
        {
            "artifact_id": str(input_ref.artifact_id),
            "manifest_profile_sha256": input_ref.manifest_profile_sha256,
        }
    )


def _require_source_view(
    ref: Any,
    manifest: Any,
    *,
    role: str,
    name: str,
    version: str,
) -> None:
    if ref.manifest_profile_sha256 is None:
        raise _IdentificationSourceBindingFailure(f"{role}_manifest_profile_missing")
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
    ):
        raise _IdentificationSourceBindingFailure("source_manifest_ref_identity_mismatch")
    _require_source_schema(manifest, name=name, version=version)


def _require_source_schema(manifest: Any, *, name: str, version: str) -> None:
    schema = manifest.artifact_schema
    if schema is None or schema.name != name or schema.version != version:
        raise _IdentificationSourceBindingFailure("source_artifact_schema_mismatch")


def _canonical_payload_sha256(value: Any) -> str:
    from hashlib import sha256

    from polisyos.core.canon import CanonSpec, to_canonical_bytes

    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    digest = sha256(to_canonical_bytes(payload, CanonSpec(forbid_floats=False))).hexdigest()
    return f"sha256:{digest}"


def _graph_basis_sha256(graph: Any) -> str:
    return _canonical_payload_sha256(graph)


def _require_graph_prior_source_projection(bundle: Any, expected: Any) -> None:
    for field_name in (
        "high_confidence_edges",
        "disputed_edges",
        "forbidden_edges",
        "required_edges",
        "equivalence_class_summary",
        "downstream_utility_scores",
        "warnings",
    ):
        if _canonical_payload_sha256(getattr(bundle, field_name)) != _canonical_payload_sha256(
            getattr(expected, field_name)
        ):
            raise _IdentificationSourceBindingFailure("graph_prior_source_projection_mismatch")

    for metadata_key in ("thresholds", "hypothesis_weights"):
        if _canonical_payload_sha256(bundle.metadata.get(metadata_key)) != _canonical_payload_sha256(
            expected.metadata.get(metadata_key)
        ):
            raise _IdentificationSourceBindingFailure("graph_prior_source_projection_mismatch")


def _ref_receipt(ref: Any, manifest: Any | None = None) -> dict[str, Any]:
    receipt = {
        "artifact_id": str(ref.artifact_id),
        "kind": ref.kind,
        "media_type": ref.media_type,
        "manifest_profile_sha256": ref.manifest_profile_sha256,
    }
    if manifest is not None:
        schema = manifest.artifact_schema
        receipt["payload_sha256"] = manifest.integrity.sha256
        receipt["artifact_schema"] = (
            None if schema is None else {"name": schema.name, "version": schema.version}
        )
    return receipt


def _labeled_assessments(
    assessments: list[EvidenceNeedAssessment],
) -> list[tuple[EvidenceNeedAssessment, str]]:
    labeled: list[tuple[EvidenceNeedAssessment, str]] = []
    for assessment in assessments:
        label = next(
            (
                item.replace("discovery_", "")
                for item in assessment.need.labels
                if item.startswith("discovery_")
            ),
            "disputed" if assessment.requires_expert_review else "required",
        )
        labeled.append((assessment, label))
    return labeled


def _rebuild_summary(profile: CrossGraphEvidenceProfile) -> CrossGraphEvidenceSummary:
    legal_counts: dict[str, int] = {}
    observability_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}
    transport_counts: dict[str, int] = {}
    blocking_need_ids: list[str] = []
    requires_expert_review_count = 0
    for assessment in profile.needs:
        _increment_count(legal_counts, assessment.legal_status.value)
        _increment_count(observability_counts, assessment.observability_status.value)
        _increment_count(evidence_counts, assessment.evidence_status.value)
        _increment_count(transport_counts, assessment.transport_status.value)
        if assessment.requires_expert_review:
            requires_expert_review_count += 1
        if assessment.blocking_reasons:
            blocking_need_ids.append(assessment.need.need_id)
    status = profile.summary.status
    if status == "ok" and requires_expert_review_count > 0:
        status = "warning"
    return CrossGraphEvidenceSummary(
        status=status,
        total_needs=len(profile.needs),
        requires_expert_review_count=requires_expert_review_count,
        blocking_need_ids=blocking_need_ids,
        legal_status_counts=legal_counts,
        observability_status_counts=observability_counts,
        evidence_status_counts=evidence_counts,
        transport_status_counts=transport_counts,
    )


def _increment_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _initial_source_statuses(
    evidence_sources,
) -> dict[str, EvidenceSourceStatus]:
    return {
        EvidenceSourceKind.ACADEMIC.value: build_path_source_status(
            EvidenceSourceKind.ACADEMIC,
            evidence_sources.academic_db_path,
            detail="cross_graph_node",
        ),
        EvidenceSourceKind.DATASETS.value: build_path_source_status(
            EvidenceSourceKind.DATASETS,
            evidence_sources.datasets_db_path,
            detail="cross_graph_node",
        ),
        EvidenceSourceKind.LEGAL.value: build_path_source_status(
            EvidenceSourceKind.LEGAL,
            evidence_sources.legal_db_path,
            detail="cross_graph_node",
        ),
    }


def _maybe_emit_feedback_outputs(
    config: CrossGraphEvidenceConfig,
    profile: CrossGraphEvidenceProfile,
    params: dict[str, Any],
    events: list[NodeEvent],
) -> tuple[dict[str, Any], EvidenceSourceStatus]:
    backlog_path_raw = str(config.backlog_output_path or "").strip()
    if backlog_path_raw:
        backlog_path = Path(backlog_path_raw)
        backlog = build_need_backlog(profile)
        write_need_backlog(backlog_path, backlog)
        # Also append to academic pipeline's shared demand backlog for cross-run feedback
        academic_backlog_path_raw = str(config.academic_demand_backlog_path or "").strip()
        if academic_backlog_path_raw:
            appended = append_need_backlog(Path(academic_backlog_path_raw), backlog)
            if appended > 0:
                events.append(
                    NodeEvent(
                        level="info",
                        message=f"Appended {appended} demand signals to academic pipeline backlog.",
                    )
                )
            events.append(
                NodeEvent(
                    level="info",
                    message=f"Cross-graph need backlog written to {backlog_path}.",
                )
            )

    suite_path_raw = str(config.benchmark_suite_path or "").strip()
    report_path_raw = str(config.benchmark_report_path or "").strip()
    if not suite_path_raw or not report_path_raw:
        summary = {
            "status": "degraded",
            "available": False,
            "reason": "benchmark_paths_not_configured",
        }
        params["cross_graph_benchmark_summary"] = dict(summary)
        return (
            summary,
            build_path_source_status(
                EvidenceSourceKind.BENCHMARK,
                report_path_raw or suite_path_raw,
                detail="cross_graph_feedback",
            ),
        )

    suite_path = Path(suite_path_raw)
    report_path = Path(report_path_raw)
    benchmark_status = build_path_source_status(
        EvidenceSourceKind.BENCHMARK,
        suite_path_raw,
        detail="cross_graph_feedback",
    )
    if benchmark_status.status is not EvidenceSourceState.AVAILABLE:
        summary = {
            "status": "degraded",
            "available": False,
            "reason": "benchmark_suite_missing",
        }
        params["cross_graph_benchmark_summary"] = dict(summary)
        return (summary, benchmark_status)

    try:
        suite = load_benchmark_suite(suite_path)
    except _CROSS_GRAPH_RUNTIME_ERRORS as exc:
        summary = {
            "status": "degraded",
            "available": False,
            "reason": "benchmark_suite_load_failed",
            "error": str(exc),
        }
        params["cross_graph_benchmark_summary"] = dict(summary)
        events.append(
            NodeEvent(
                level="warn",
                message=f"Cross-graph benchmark suite load failed: {exc}",
            )
        )
        return (
            summary,
            update_source_status(
                benchmark_status,
                state=EvidenceSourceState.INIT_FAILED,
                detail=f"{type(exc).__name__}:{exc}",
                warnings=[f"benchmark_suite_load_failed:{type(exc).__name__}:{exc}"],
            ),
        )
    scholar_graph = None
    academic_db_path = str(config.academic_db_path or "").strip()
    if academic_db_path:
        try:
            from polisyos.data_forge.read_api.academic import ScholarKnowledgeGraph

            db_path = Path(academic_db_path)
            if db_path.exists():
                index_dir = Path(str(config.academic_index_dir or db_path.parent))
                scholar_graph = ScholarKnowledgeGraph(db_path=db_path, index_dir=index_dir)
        except _CROSS_GRAPH_IMPORT_RUNTIME_ERRORS as exc:
            events.append(
                NodeEvent(
                    level="warn",
                    message=f"Benchmark scholar graph init failed: {exc}",
                )
            )

    try:
        report = evaluate_benchmark_suite(profile, suite, scholar_graph=scholar_graph)
    except _CROSS_GRAPH_RUNTIME_ERRORS as exc:
        summary = {
            "status": "degraded",
            "available": False,
            "reason": "benchmark_evaluation_failed",
            "error": str(exc),
        }
        params["cross_graph_benchmark_summary"] = dict(summary)
        events.append(
            NodeEvent(
                level="warn",
                message=f"Cross-graph benchmark evaluation failed: {exc}",
            )
        )
        return (
            summary,
            update_source_status(
                benchmark_status,
                state=EvidenceSourceState.QUERY_FAILED,
                detail=f"{type(exc).__name__}:{exc}",
                warnings=[f"benchmark_evaluation_failed:{type(exc).__name__}:{exc}"],
            ),
        )
    finally:
        if scholar_graph is not None:
            scholar_graph.close()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json_dumps(report), encoding="utf-8")
    summary = dict(report.get("summary") or {})
    if not summary:
        summary = {"status": "ok", "available": True}
    else:
        summary.setdefault("status", "ok")
        summary.setdefault("available", True)
    params["cross_graph_benchmark_summary"] = dict(summary)
    events.append(
        NodeEvent(
            level="info",
            message=f"Cross-graph benchmark report written to {report_path}.",
        )
    )
    return (
        summary,
        update_source_status(
            benchmark_status,
            state=EvidenceSourceState.AVAILABLE,
            provenance_refs=[str(report_path)],
            detail="benchmark_report_written",
        ),
    )


def json_dumps(payload: dict[str, Any]) -> str:
    """Json dumps helper."""
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["CompileCrossGraphEvidenceNode"]
