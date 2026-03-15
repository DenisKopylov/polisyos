from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    persist_cross_graph_evidence_profile,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.cross_graph.compiler import (
    CrossGraphEvidenceCompiler,
    CrossGraphEvidenceConfig,
)
from polisyos.scientist.cross_graph.feedback import (
    build_need_backlog,
    evaluate_benchmark_suite,
    load_benchmark_suite,
    write_need_backlog,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
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
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
        "params.cross_graph_evidence_config",
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


@dataclass(frozen=True)
class CompileCrossGraphEvidenceNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        new_state = state.model_copy(deep=True)
        config_payload = state.params.get("cross_graph_evidence_config")
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
        if trinity_ref is None:
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[NodeEvent(level="warn", message="Missing Trinity bundle; cross-graph evidence skipped.")],
            )

        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
        bundle = TrinityBundle.model_validate(payload)
        target_context = _resolve_target_context(state)
        causal_graph = _resolve_causal_graph(ctx, state)

        try:
            config = CrossGraphEvidenceConfig.model_validate(config_payload)
        except Exception as exc:
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[
                    NodeEvent(
                        level="warn",
                        message=f"Invalid cross-graph evidence config; skipped ({exc}).",
                    )
                ],
            )

        inputs = [InputRef(artifact_id=trinity_ref.artifact_id, role="trinity_bundle")]
        graph_ref = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
        if graph_ref is not None:
            inputs.append(InputRef(artifact_id=graph_ref.artifact_id, role="causal_graph"))

        try:
            profile = CrossGraphEvidenceCompiler(config).compile(
                bundle,
                target_context=target_context,
                causal_graph=causal_graph,
            )
        except Exception as exc:
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
                target_context=target_context,
                notes=["cross_graph_compile_failed"],
            )

        profile_ref = persist_cross_graph_evidence_profile(ctx.store, profile, inputs=inputs)
        new_state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF] = profile_ref
        new_state.params["cross_graph_evidence_summary"] = profile.summary.model_dump(mode="json")
        extra_events: list[NodeEvent] = []
        _maybe_emit_feedback_outputs(config, profile, new_state.params, extra_events)

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
    except Exception:
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
    except Exception:
        return None


def _maybe_emit_feedback_outputs(
    config: CrossGraphEvidenceConfig,
    profile: CrossGraphEvidenceProfile,
    params: dict[str, Any],
    events: list[NodeEvent],
) -> None:
    backlog_path_raw = str(config.backlog_output_path or "").strip()
    if backlog_path_raw:
        backlog_path = Path(backlog_path_raw)
        backlog = build_need_backlog(profile)
        write_need_backlog(backlog_path, backlog)
        events.append(
            NodeEvent(
                level="info",
                message=f"Cross-graph need backlog written to {backlog_path}.",
            )
        )

    suite_path_raw = str(config.benchmark_suite_path or "").strip()
    report_path_raw = str(config.benchmark_report_path or "").strip()
    if not suite_path_raw or not report_path_raw:
        return

    suite_path = Path(suite_path_raw)
    report_path = Path(report_path_raw)
    suite = load_benchmark_suite(suite_path)
    scholar_graph = None
    academic_db_path = str(config.academic_db_path or "").strip()
    if academic_db_path:
        try:
            from polisyos.academic.knowledge.search import ScholarKnowledgeGraph

            db_path = Path(academic_db_path)
            if db_path.exists():
                index_dir = Path(str(config.academic_index_dir or db_path.parent))
                scholar_graph = ScholarKnowledgeGraph(db_path=db_path, index_dir=index_dir)
        except Exception as exc:
            events.append(
                NodeEvent(
                    level="warn",
                    message=f"Benchmark scholar graph init failed: {exc}",
                )
            )

    try:
        report = evaluate_benchmark_suite(profile, suite, scholar_graph=scholar_graph)
    finally:
        if scholar_graph is not None:
            scholar_graph.close()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json_dumps(report), encoding="utf-8")
    params["cross_graph_benchmark_summary"] = dict(report.get("summary") or {})
    events.append(
        NodeEvent(
            level="info",
            message=f"Cross-graph benchmark report written to {report_path}.",
        )
    )


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["CompileCrossGraphEvidenceNode"]
