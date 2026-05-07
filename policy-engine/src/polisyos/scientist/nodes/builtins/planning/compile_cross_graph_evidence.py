"""Public planning compile cross graph evidence module API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
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
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.cross_graph.feedback import (
    append_need_backlog,
    build_need_backlog,
    evaluate_benchmark_suite,
    load_benchmark_suite,
    write_need_backlog,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.evidence.sources import (
    build_path_source_status,
    merge_evidence_sources_payload,
    normalize_evidence_sources_config,
    update_source_status,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)

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


@dataclass(frozen=True)
class CompileCrossGraphEvidenceNode:
    """Compile cross graph evidence node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

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
        causal_graph = _resolve_causal_graph(ctx, state)

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
            profile_ref = persist_cross_graph_evidence_profile(ctx.store, profile)
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
        graph_ref = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
        if graph_ref is not None:
            inputs.append(InputRef(artifact_id=str(graph_ref.artifact_id), role="causal_graph"))
        literature_prior_ref = state.artifacts_index.get(ARTIFACT_LITERATURE_PRIOR_REF)
        if literature_prior_ref is not None:
            inputs.append(
                InputRef(
                    artifact_id=str(literature_prior_ref.artifact_id),
                    role="literature_prior",
                )
            )

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
                payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
                bundle = TrinityBundle.model_validate(payload)
                literature_prior = (
                    load_literature_causal_prior(ctx.store, literature_prior_ref)
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
        profile_ref = persist_cross_graph_evidence_profile(ctx.store, profile, inputs=inputs)
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


def _resolve_causal_graph(
    ctx: ExecutionContext,
    state: ExperimentState,
):
    ref = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
    if ref is None:
        return None
    try:
        return load_causal_graph_model(ctx.store, ref)
    except _CROSS_GRAPH_RUNTIME_ERRORS:
        return None


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
            _assessment_from_prior_edge(edge, source_label="required")
            for edge in bundle.required_edges
        ],
        *[
            _assessment_from_prior_edge(edge, source_label="high_confidence")
            for edge in bundle.high_confidence_edges
        ],
        *[
            _assessment_from_disputed_candidate(
                candidate,
                dispute_id=disputed.dispute_id,
                dispute_reasons=disputed.dispute_reasons,
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


def _assessment_from_prior_edge(edge: Any, *, source_label: str) -> EvidenceNeedAssessment:
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
        labels=[f"discovery_{source_label}"],
    )
    return EvidenceNeedAssessment(
        need=need,
        legal_status=LegalStatus.UNKNOWN,
        observability_status=ObservabilityStatus.UNKNOWN,
        evidence_status=EvidenceStatus.SUPPORTED,
        transport_status=TransportStatus.UNSUPPORTED,
        confidence=float(edge.presence_confidence),
        requires_expert_review=False,
        recommended_actions=[f"preserve_{source_label}_discovery_edge"],
        provenance_refs=list(edge.provenance_refs),
    )


def _assessment_from_disputed_candidate(
    edge: Any,
    *,
    dispute_id: str,
    dispute_reasons: list[str],
) -> EvidenceNeedAssessment:
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
        labels=["discovery_disputed"],
    )
    return EvidenceNeedAssessment(
        need=need,
        legal_status=LegalStatus.UNKNOWN,
        observability_status=ObservabilityStatus.UNKNOWN,
        evidence_status=EvidenceStatus.MIXED,
        transport_status=TransportStatus.UNSUPPORTED,
        confidence=float(edge.presence_confidence),
        requires_expert_review=True,
        recommended_actions=["resolve_disputed_discovery_edge"],
        provenance_refs=list(edge.provenance_refs),
        diagnostics=[
            CrossGraphDiagnostic(
                code="cross_graph.discovery_prior.disputed",
                severity="warn",
                need_id=need.need_id,
                message="Discovery surfaced a disputed causal edge that needs follow-up.",
                details={"dispute_id": dispute_id, "reasons": list(dispute_reasons)},
            )
        ],
    )


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
