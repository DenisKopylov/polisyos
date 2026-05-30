"""Projection adapters from existing Scientist runtime surfaces into Research DAGs."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.research_dag.builder import (
    ResearchDAGBuilder,
    sanitize_public_metadata,
    stable_fingerprint,
)
from polisyos.scientist.methods.research_dag.models import (
    ResearchDAGArtifact,
    ResearchDAGNode,
    ResearchEdgeType,
    ResearchNodeType,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CLAIMS_REF
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.memory.contracts import ReflexiveMemoryEvent

RESEARCH_DAG_FEATURE_FLAG = "scientist.best_in_class.wave1.phase1_2.research_dag"
REQUIRE_RESEARCH_DAG_FOR_PUBLICATION_FLAG = (
    "scientist.best_in_class.wave1.phase1_2.require_research_dag_for_publication"
)
SELECTED_RESEARCH_DAG_WORKFLOWS: frozenset[str] = frozenset(
    {
        "scientist_policy_design",
        "scientist_policy_verified",
        "scientist_causal_full",
    }
)


def is_research_dag_enabled(params: dict[str, Any] | None = None) -> bool:
    """Return whether Phase 1.2 sidecar generation is enabled for this run."""

    params = params or {}
    if RESEARCH_DAG_FEATURE_FLAG in params:
        return _truthy(params[RESEARCH_DAG_FEATURE_FLAG])
    if "research_dag_enabled" in params:
        return _truthy(params["research_dag_enabled"])
    env_value = os.getenv("POLISYOS_SCIENTIST_RESEARCH_DAG")
    if env_value is not None:
        return _truthy(env_value)
    return False


def is_research_dag_required_for_publication(params: dict[str, Any] | None = None) -> bool:
    """Return whether publication paths should require research_dag_ref."""

    params = params or {}
    if REQUIRE_RESEARCH_DAG_FOR_PUBLICATION_FLAG in params:
        return _truthy(params[REQUIRE_RESEARCH_DAG_FOR_PUBLICATION_FLAG])
    if "require_research_dag_for_publication" in params:
        return _truthy(params["require_research_dag_for_publication"])
    return False


def project_workflow_execution_to_research_dag(
    *,
    run_id: str,
    workflow_id: str,
    records: list[Any],
    state: ExperimentState | None = None,
    claim_ledger_ref: ArtifactRef | None = None,
    producer: str = "workflow_executor",
    created_at: datetime | None = None,
) -> ResearchDAGArtifact:
    """Project workflow node outcomes into a replayable high-level research DAG."""

    if claim_ledger_ref is None and state is not None:
        claim_ledger_ref = state.artifacts_index.get(ARTIFACT_CLAIMS_REF)
    builder = ResearchDAGBuilder(
        run_id=run_id,
        workflow_id=workflow_id,
        claim_ledger_ref=claim_ledger_ref,
        created_at=created_at or datetime.now(UTC),
        metadata={
            "projection_source": "workflow_execution",
            "selected_workflow": workflow_id in SELECTED_RESEARCH_DAG_WORKFLOWS,
        },
    )
    question = builder.add_node(
        node_type=ResearchNodeType.QUESTION,
        producer=producer,
        summary=_question_summary(state, workflow_id),
        input_fingerprint=stable_fingerprint(_question_fingerprint_payload(state, workflow_id)),
        metadata={"workflow_id": workflow_id},
    )
    plan = builder.add_node(
        node_type=ResearchNodeType.PLAN,
        producer=producer,
        summary=f"Execute workflow {workflow_id} and preserve research path as a sidecar DAG.",
        metadata={"node_count": len(records)},
    )
    builder.add_edge(
        source_node_id=question.node_id,
        target_node_id=plan.node_id,
        edge_type=ResearchEdgeType.DEPENDS_ON,
    )

    previous_node_id = plan.node_id
    for index, record in enumerate(records):
        node_type = classify_runtime_step(
            alias=str(getattr(record, "alias", "")),
            node_id=str(getattr(record, "node_id", "")),
        )
        artifact_refs = list(getattr(record, "artifacts", []) or [])
        status = _status_value(getattr(record, "status", "unknown"))
        error = getattr(record, "error", None)
        metadata = {
            "alias": str(getattr(record, "alias", "")),
            "node_id": str(getattr(record, "node_id", "")),
            "status": status,
            "duration_ms": int(getattr(record, "duration_ms", 0) or 0),
            "skip_reason": getattr(record, "skip_reason", None),
        }
        if error is not None:
            metadata["error_code"] = str(getattr(error, "code", ""))
        node = builder.add_node(
            node_type=node_type,
            producer=str(getattr(record, "node_id", "") or producer),
            summary=_record_summary(record, status),
            node_id=f"{workflow_id}:{index + 1}:{getattr(record, 'alias', 'node')}",
            artifact_refs=artifact_refs,
            metadata=metadata,
            output_fingerprint=stable_fingerprint(
                {
                    "alias": getattr(record, "alias", ""),
                    "status": status,
                    "artifacts": [str(ref.artifact_id) for ref in artifact_refs],
                }
            ),
        )
        builder.add_edge(
            source_node_id=previous_node_id,
            target_node_id=node.node_id,
            edge_type=ResearchEdgeType.DEPENDS_ON,
        )
        if node.node_type in {ResearchNodeType.GOVERNANCE, ResearchNodeType.PUBLICATION}:
            builder.add_edge(
                source_node_id=plan.node_id,
                target_node_id=node.node_id,
                edge_type=ResearchEdgeType.GATES,
            )
        previous_node_id = node.node_id

    return builder.artifact(
        metadata={
            "workflow_status": "projected",
            "claim_ledger_status": "available"
            if claim_ledger_ref is not None
            else "legacy_missing",
        }
    )


def project_tool_call_result_to_research_node(
    tool_call_result: Any,
    *,
    run_id: str,
    workflow_id: str | None = None,
    node_id: str | None = None,
) -> ResearchDAGNode:
    """Project one tool call result without storing raw untrusted result text."""

    tool_name = str(getattr(tool_call_result, "tool_name", "tool"))
    raw_result = getattr(tool_call_result, "result", None)
    raw_error = getattr(tool_call_result, "error", None)
    raw_payload = raw_error if raw_error is not None else raw_result
    raw_text = _safe_json_text(raw_payload)
    metadata = {
        "tool_name": tool_name,
        "status": "error" if raw_error is not None else "ok",
        "duration_ms": int(getattr(tool_call_result, "duration_ms", 0) or 0),
        "argument_fingerprint": stable_fingerprint(
            getattr(tool_call_result, "arguments", {}) or {}
        ),
        "error_type": getattr(tool_call_result, "error_type", None),
    }
    builder = ResearchDAGBuilder(
        run_id=run_id,
        workflow_id=workflow_id or "tool_loop",
    )
    return builder.add_node(
        node_type=classify_tool_step(tool_name),
        producer=f"tool:{tool_name}",
        summary=f"Tool {tool_name} returned {'an error' if raw_error is not None else 'untrusted output'}; raw content redacted.",
        node_id=node_id or f"tool:{tool_name}",
        metadata=metadata,
        untrusted_text=raw_text,
    )


def project_tool_loop_result_to_research_dag(
    tool_loop_result: Any,
    *,
    run_id: str,
    workflow_id: str = "tool_loop",
    claim_ledger_ref: ArtifactRef | None = None,
) -> ResearchDAGArtifact:
    """Project a completed tool loop into a compact research DAG."""

    builder = ResearchDAGBuilder(
        run_id=run_id,
        workflow_id=workflow_id,
        claim_ledger_ref=claim_ledger_ref,
        metadata={"projection_source": "tool_loop"},
    )
    plan = builder.add_node(
        node_type=ResearchNodeType.PLAN,
        producer="agent.tool_loop",
        summary="Run tool loop and record summarized tool evidence nodes.",
        metadata={
            "iterations": int(getattr(tool_loop_result, "iterations", 0) or 0),
            "converged": bool(getattr(tool_loop_result, "converged", False)),
        },
    )
    previous_node_id = plan.node_id
    for index, tool_call in enumerate(getattr(tool_loop_result, "tool_calls_made", []) or []):
        projected = project_tool_call_result_to_research_node(
            tool_call,
            run_id=run_id,
            workflow_id=workflow_id,
            node_id=f"{workflow_id}:tool:{index + 1}:{getattr(tool_call, 'tool_name', 'tool')}",
        )
        builder_node = builder.add_node(
            node_type=projected.node_type,
            producer=projected.producer,
            summary=projected.summary,
            node_id=projected.node_id,
            artifact_refs=projected.artifact_refs,
            claim_ids=projected.claim_ids,
            input_fingerprint=projected.input_fingerprint,
            output_fingerprint=projected.output_fingerprint,
            safety_labels=projected.safety_labels,
            metadata=projected.metadata,
        )
        builder.add_edge(
            source_node_id=previous_node_id,
            target_node_id=builder_node.node_id,
            edge_type=ResearchEdgeType.DEPENDS_ON,
        )
        previous_node_id = builder_node.node_id
    return builder.artifact()


def project_provenance_graph_to_research_dag(
    *,
    run_id: str,
    workflow_id: str,
    provenance_graph: Any,
    claim_ledger_ref: ArtifactRef | None = None,
) -> ResearchDAGArtifact:
    """Project the existing run provenance graph into the Phase 1.2 DAG contract."""

    builder = ResearchDAGBuilder(
        run_id=run_id,
        workflow_id=workflow_id,
        claim_ledger_ref=claim_ledger_ref,
        metadata={"projection_source": "provenance.run_dag"},
    )
    root = builder.add_node(
        node_type=ResearchNodeType.PLAN,
        producer="provenance.run_dag",
        summary=f"Project provenance activities for workflow {workflow_id}.",
    )
    previous_node_id = root.node_id
    activities = getattr(provenance_graph, "activities", {}) or {}
    for index, activity in enumerate(activities.values()):
        label = str(getattr(activity, "label", "provenance activity"))
        node = builder.add_node(
            node_type=classify_runtime_step(
                alias=label, node_id=str(getattr(activity, "activity_type", ""))
            ),
            producer="provenance.run_dag",
            summary=label,
            node_id=f"{workflow_id}:provenance:{index + 1}",
            metadata=sanitize_public_metadata(getattr(activity, "parameters", {}) or {}),
        )
        builder.add_edge(
            source_node_id=previous_node_id,
            target_node_id=node.node_id,
            edge_type=ResearchEdgeType.DEPENDS_ON,
        )
        previous_node_id = node.node_id
    return builder.artifact()


def project_web_evidence_bundle_to_research_dag(
    bundle: Any,
    *,
    run_id: str,
    workflow_id: str = "scientist_deep_research",
    claim_ledger_ref: ArtifactRef | None = None,
) -> ResearchDAGArtifact:
    """Project a Scholar WebEvidenceBundle into query/fetch/extract/verify DAG nodes."""

    builder = ResearchDAGBuilder(
        run_id=run_id,
        workflow_id=workflow_id,
        claim_ledger_ref=claim_ledger_ref,
        metadata={
            "projection_source": "scholar.web_evidence_bundle",
            "bundle_id": str(getattr(bundle, "bundle_id", "")),
        },
    )
    brief = getattr(bundle, "brief", None)
    question_text = str(getattr(brief, "question", "") or "Deep research evidence request.")
    question = builder.add_node(
        node_type=ResearchNodeType.QUESTION,
        producer="scholar.search",
        summary=question_text,
        input_fingerprint=stable_fingerprint(
            getattr(brief, "model_dump", lambda **_: {"question": question_text})(mode="json")
            if brief is not None
            else {"question": question_text}
        ),
    )

    query_node_by_id: dict[str, str] = {}
    graph = getattr(bundle, "query_graph", None)
    for query in getattr(graph, "nodes", []) or []:
        node = builder.add_node(
            node_type=ResearchNodeType.SOURCE_ACQUISITION,
            producer="scholar.query_graph",
            summary=f"Search query: {getattr(query, 'query', '')}",
            node_id=f"{workflow_id}:query:{getattr(query, 'node_id', '')}",
            metadata={
                "query_node_id": getattr(query, "node_id", ""),
                "perspective": getattr(query, "perspective", ""),
                "depth": int(getattr(query, "depth", 0) or 0),
                "status": getattr(query, "status", ""),
                "hit_count": int(getattr(query, "hit_count", 0) or 0),
            },
            input_fingerprint=stable_fingerprint(getattr(query, "query", "")),
        )
        query_node_by_id[str(getattr(query, "node_id", ""))] = node.node_id
        builder.add_edge(
            source_node_id=question.node_id,
            target_node_id=node.node_id,
            edge_type=ResearchEdgeType.DEPENDS_ON,
        )

    source_node_by_id: dict[str, str] = {}
    for source in getattr(bundle, "sources", []) or []:
        node = builder.add_node(
            node_type=ResearchNodeType.SOURCE_READ,
            producer="scholar.fetch",
            summary=f"Fetched source {getattr(source, 'title', '') or getattr(source, 'domain', '')}",
            node_id=f"{workflow_id}:source:{getattr(source, 'source_id', '')}",
            metadata={
                "source_id": getattr(source, "source_id", ""),
                "domain": getattr(source, "domain", ""),
                "source_type": getattr(source, "source_type", ""),
                "fetch_status": getattr(source, "fetch_status", ""),
                "content_type": getattr(source, "content_type", ""),
                "content_sha256": getattr(source, "content_sha256", None),
                "quality_score": str(getattr(source, "quality_score", "")),
                "paywalled": bool(getattr(source, "paywalled", False)),
            },
            output_fingerprint=stable_fingerprint(
                {
                    "source_id": getattr(source, "source_id", ""),
                    "content_sha256": getattr(source, "content_sha256", None),
                }
            ),
        )
        source_node_by_id[str(getattr(source, "source_id", ""))] = node.node_id
        query_parent = _source_query_parent_node(source, query_node_by_id)
        if query_parent is not None:
            builder.add_edge(
                source_node_id=query_parent,
                target_node_id=node.node_id,
                edge_type=ResearchEdgeType.DERIVES,
            )

    snippet_node_by_id: dict[str, str] = {}
    for snippet in getattr(bundle, "snippets", []) or []:
        node = builder.add_node(
            node_type=ResearchNodeType.EXTRACTION,
            producer="scholar.snippet_ledger",
            summary=f"Extracted snippet {getattr(snippet, 'snippet_id', '')}",
            node_id=f"{workflow_id}:snippet:{getattr(snippet, 'snippet_id', '')}",
            metadata={
                "snippet_id": getattr(snippet, "snippet_id", ""),
                "source_id": getattr(snippet, "source_id", ""),
                "query_node_id": getattr(snippet, "query_node_id", ""),
                "start_char": int(getattr(snippet, "start_char", 0) or 0),
                "end_char": int(getattr(snippet, "end_char", 0) or 0),
                "relevance_score": str(getattr(snippet, "relevance_score", "")),
            },
            untrusted_text=str(getattr(snippet, "text", "")),
        )
        snippet_node_by_id[str(getattr(snippet, "snippet_id", ""))] = node.node_id
        parent = source_node_by_id.get(str(getattr(snippet, "source_id", "")))
        if parent is not None:
            builder.add_edge(
                source_node_id=parent,
                target_node_id=node.node_id,
                edge_type=ResearchEdgeType.DERIVES,
            )

    for support in getattr(bundle, "claim_supports", []) or []:
        claim_id = str(getattr(support, "claim_id", ""))
        metadata = getattr(support, "metadata", {}) or {}
        node = builder.add_node(
            node_type=ResearchNodeType.VERIFICATION,
            producer="scholar.claim_support",
            summary=f"Mapped snippets to claim {claim_id}.",
            node_id=f"{workflow_id}:support:{claim_id}",
            claim_ids=[claim_id] if claim_id else [],
            metadata={
                "claim_id": claim_id,
                "support_score": str(getattr(support, "support_score", "")),
                "conflict_score": str(getattr(support, "conflict_score", "")),
                "support_status": metadata.get("support_status"),
                "claim_id_namespace": metadata.get("claim_id_namespace", "legacy_local"),
                "snippet_count": len(getattr(support, "snippet_ids", []) or []),
            },
            input_fingerprint=stable_fingerprint(
                {
                    "claim_id": claim_id,
                    "snippet_ids": list(getattr(support, "snippet_ids", []) or []),
                    "source_ids": list(getattr(support, "source_ids", []) or []),
                }
            ),
        )
        for snippet_id in getattr(support, "snippet_ids", []) or []:
            parent = snippet_node_by_id.get(str(snippet_id))
            if parent is None:
                continue
            builder.add_edge(
                source_node_id=parent,
                target_node_id=node.node_id,
                edge_type=ResearchEdgeType.REFUTES
                if float(getattr(support, "conflict_score", 0.0) or 0.0) >= 0.5
                else ResearchEdgeType.SUPPORTS,
                claim_ids=[claim_id] if claim_id else [],
            )

    safety_events = list(getattr(bundle, "fetch_safety_events", []) or [])
    if safety_events:
        node = builder.add_node(
            node_type=ResearchNodeType.GOVERNANCE,
            producer="scholar.safe_fetch",
            summary="Recorded fetch safety events for untrusted web evidence.",
            node_id=f"{workflow_id}:fetch-safety",
            metadata={
                "event_count": len(safety_events),
                "event_types": sorted(
                    {str(getattr(event, "event_type", "")) for event in safety_events}
                ),
                "blocked_count": sum(
                    1 for event in safety_events if getattr(event, "severity", "") == "block"
                ),
            },
        )
        builder.add_edge(
            source_node_id=question.node_id,
            target_node_id=node.node_id,
            edge_type=ResearchEdgeType.GATES,
        )

    return builder.artifact(
        metadata={
            "source_count": len(getattr(bundle, "sources", []) or []),
            "snippet_count": len(getattr(bundle, "snippets", []) or []),
            "claim_support_count": len(getattr(bundle, "claim_supports", []) or []),
        }
    )


def classify_tool_step(tool_name: str) -> ResearchNodeType:
    """Map a tool name to a research DAG node type."""

    lowered = tool_name.lower()
    if any(token in lowered for token in ("search", "query", "discover", "scholar")):
        return ResearchNodeType.SOURCE_ACQUISITION
    if any(token in lowered for token in ("fetch", "read", "open", "pdf", "url", "load")):
        return ResearchNodeType.SOURCE_READ
    if any(token in lowered for token in ("verify", "freshness", "citation", "check")):
        return ResearchNodeType.VERIFICATION
    return ResearchNodeType.EXTRACTION


def project_reflexive_memory_events_to_research_dag(
    events: list[ReflexiveMemoryEvent],
    *,
    run_id: str,
    workflow_id: str = "scientist_reflexive_memory",
    claim_ledger_ref: ArtifactRef | None = None,
) -> ResearchDAGArtifact:
    """Project reflexive-memory influence into a public, redacted Research DAG."""

    builder = ResearchDAGBuilder(
        run_id=run_id,
        workflow_id=workflow_id,
        claim_ledger_ref=claim_ledger_ref,
        metadata={
            "projection_source": "scientist.reflexive_memory",
            "memory_event_count": len(events),
        },
    )
    plan = builder.add_node(
        node_type=ResearchNodeType.PLAN,
        producer="scientist.memory",
        summary="Evaluate scoped failure lessons as warning-only reflexive memory.",
        metadata={"influence_mode": "warning_anti_pattern"},
    )
    previous_node_id = plan.node_id
    for index, event in enumerate(events):
        applicability = event.applicability
        node = builder.add_node(
            node_type=ResearchNodeType.CRITIQUE,
            producer="scientist.memory",
            summary=(
                f"Memory lesson {event.lesson_id} was {event.action}; "
                "influence is warning-only and scope-checked."
            ),
            node_id=f"{workflow_id}:memory:{index + 1}:{event.lesson_id}",
            metadata={
                "event_id": event.event_id,
                "lesson_id": event.lesson_id,
                "action": event.action,
                "applies": applicability.applies,
                "applicability_reasons": list(applicability.reasons),
                "scope": dict(applicability.scope),
                "memory_influence_visible": True,
                "influence_mode": "warning_anti_pattern",
            },
            input_fingerprint=stable_fingerprint(event.model_dump(mode="json")),
            safety_labels=["reflexive_memory", "warning_only"],
        )
        event.research_dag_node_id = node.node_id
        builder.add_edge(
            source_node_id=previous_node_id,
            target_node_id=node.node_id,
            edge_type=ResearchEdgeType.DEPENDS_ON,
        )
        previous_node_id = node.node_id
    return builder.artifact(
        metadata={
            "memory_influence_status": "visible" if events else "no_memory_events",
            "retrieved_event_count": sum(1 for event in events if event.action == "retrieved"),
            "rejected_event_count": sum(1 for event in events if event.action == "rejected"),
        }
    )


def validate_memory_influence_dag_attribution(
    events: list[ReflexiveMemoryEvent],
    dag: ResearchDAGArtifact,
) -> list[str]:
    """Return violations for memory events that can influence a run without DAG attribution."""

    visible: set[tuple[str, str]] = set()
    for node in dag.nodes:
        event_id = str(node.metadata.get("event_id", ""))
        lesson_id = str(node.metadata.get("lesson_id", ""))
        if node.metadata.get("memory_influence_visible") is True:
            visible.add((event_id, lesson_id))

    violations: list[str] = []
    for event in events:
        if event.action not in {"retrieved", "applied"}:
            continue
        if (event.event_id, event.lesson_id) not in visible:
            violations.append(f"memory_influence_missing_dag_node:{event.event_id}")
    return violations


def project_memory_influence_records_to_research_dag(
    records: list[object],
    *,
    run_id: str,
    workflow_id: str = "scientist_balanced_memory",
    claim_ledger_ref: ArtifactRef | None = None,
) -> ResearchDAGArtifact:
    """Project balanced-memory influence records into a redacted Research DAG."""

    builder = ResearchDAGBuilder(
        run_id=run_id,
        workflow_id=workflow_id,
        claim_ledger_ref=claim_ledger_ref,
        metadata={
            "projection_source": "runtime.quality.memory_influence",
            "memory_influence_record_count": len(records),
        },
    )
    plan = builder.add_node(
        node_type=ResearchNodeType.PLAN,
        producer="runtime.quality.memory_influence",
        summary=(
            "Project balanced memory as future routing, search, review, or "
            "acquisition influence, never as current claim evidence."
        ),
        metadata={
            "influence_boundary": "future_only",
            "evidence_slot_admission": "forbidden",
        },
        safety_labels=["balanced_memory", "historical_prior", "not_evidence"],
    )
    previous_node_id = plan.node_id
    for index, record in enumerate(records):
        payload = _memory_influence_payload(record)
        record_id = _payload_text(
            payload,
            "record_id",
            fallback=f"memory-influence-{index + 1}",
        )
        memory_id = _payload_text(payload, "memory_id", fallback=record_id)
        memory_kind = _payload_text(payload, "memory_kind", fallback="unknown")
        influence_modes = _payload_values(payload.get("influence_modes"))
        may_not_use_for = _payload_values(payload.get("may_not_use_for"))
        node = builder.add_node(
            node_type=ResearchNodeType.CRITIQUE,
            producer="runtime.quality.memory_influence",
            summary=(
                f"Balanced memory {memory_id} ({memory_kind}) influenced future "
                "search/review posture only."
            ),
            node_id=f"{workflow_id}:memory_influence:{index + 1}:{memory_id}",
            metadata={
                "record_id": record_id,
                "memory_id": memory_id,
                "memory_kind": memory_kind,
                "source_run_id": _payload_text(payload, "source_run_id"),
                "source_kind": _payload_text(payload, "source_kind"),
                "source_status": _payload_text(payload, "source_status"),
                "influence_modes": influence_modes,
                "authoritative_for": _payload_values(payload.get("authoritative_for")),
                "may_not_use_for": may_not_use_for,
                "scope": dict(payload.get("scope") or {}),
                "applicability_reasons": _payload_values(payload.get("applicability_reasons")),
                "contamination_status": _payload_text(payload, "contamination_status"),
                "contamination_check_ref": _payload_text(payload, "contamination_check_ref"),
                "memory_influence_visible": True,
                "evidence_slot_admission": "forbidden",
            },
            input_fingerprint=stable_fingerprint(payload),
            safety_labels=["balanced_memory", "historical_prior", "not_evidence"],
        )
        builder.add_edge(
            source_node_id=previous_node_id,
            target_node_id=node.node_id,
            edge_type=ResearchEdgeType.DEPENDS_ON,
            metadata={"evidence_slot_admission": "forbidden"},
        )
        previous_node_id = node.node_id
    return builder.artifact(
        metadata={
            "memory_influence_status": "visible" if records else "no_memory_influence_records",
            "memory_influence_record_count": len(records),
            "evidence_slot_admission": "forbidden",
        }
    )


def validate_memory_influence_record_dag_attribution(
    records: list[object],
    dag: ResearchDAGArtifact,
) -> list[str]:
    """Return violations for memory influence records missing visible DAG nodes."""

    visible: set[tuple[str, str]] = set()
    for node in dag.nodes:
        if node.metadata.get("memory_influence_visible") is not True:
            continue
        visible.add(
            (
                str(node.metadata.get("record_id", "")),
                str(node.metadata.get("memory_id", "")),
            )
        )

    violations: list[str] = []
    for record in records:
        payload = _memory_influence_payload(record)
        record_id = _payload_text(payload, "record_id")
        memory_id = _payload_text(payload, "memory_id", fallback=record_id)
        if (record_id, memory_id) not in visible:
            violations.append(f"memory_influence_record_missing_dag_node:{record_id}")
    return violations


def classify_runtime_step(*, alias: str, node_id: str) -> ResearchNodeType:
    """Map existing workflow/node naming into high-level research node families."""

    text = f"{alias} {node_id}".lower()
    if any(token in text for token in ("decision_packet", "publish", "output_bundle", "brief")):
        return ResearchNodeType.PUBLICATION
    if any(token in text for token in ("governance", "gate", "preflight", "validation", "judge")):
        return ResearchNodeType.GOVERNANCE
    if any(token in text for token in ("critic", "critique", "refute", "stress", "challenge")):
        return ResearchNodeType.CRITIQUE
    if any(token in text for token in ("verify", "validity", "readiness", "freshness", "citation")):
        return ResearchNodeType.VERIFICATION
    if any(token in text for token in ("search", "source", "literature", "query", "acquire")):
        return ResearchNodeType.SOURCE_ACQUISITION
    if any(token in text for token in ("fetch", "read", "load", "extract_pdf", "table")):
        return ResearchNodeType.SOURCE_READ
    if any(token in text for token in ("extract", "compile", "translate", "candidate", "legal")):
        return ResearchNodeType.EXTRACTION
    if any(token in text for token in ("plan", "blueprint", "intent", "frame")):
        return ResearchNodeType.PLAN
    if any(token in text for token in ("causal", "simulate", "synthesis", "recommend", "summary")):
        return ResearchNodeType.SYNTHESIS
    return ResearchNodeType.SYNTHESIS


def _question_summary(state: ExperimentState | None, workflow_id: str) -> str:
    if state is None:
        return f"Research request for {workflow_id}."
    for key in (
        "research_question",
        "policy_question",
        "question",
        "user_request",
        "problem_statement",
        "objective",
    ):
        value = state.params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"Research request for {workflow_id}."


def _question_fingerprint_payload(
    state: ExperimentState | None,
    workflow_id: str,
) -> dict[str, Any]:
    if state is None:
        return {"workflow_id": workflow_id}
    return {
        "workflow_id": workflow_id,
        "inputs": sorted(state.inputs),
        "params": {
            key: value
            for key, value in state.params.items()
            if key
            in {
                "research_question",
                "policy_question",
                "question",
                "problem_statement",
                "objective",
            }
        },
    }


def _record_summary(record: Any, status: str) -> str:
    alias = str(getattr(record, "alias", "node"))
    node_id = str(getattr(record, "node_id", ""))
    return f"Workflow node {alias} ({node_id}) completed with status {status}."


def _status_value(status: Any) -> str:
    return str(getattr(status, "value", status))


def _safe_json_text(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _memory_influence_payload(record: object) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        return dict(record.model_dump(mode="json"))
    if isinstance(record, dict):
        return dict(record)
    return {
        key: getattr(record, key)
        for key in (
            "record_id",
            "memory_id",
            "memory_kind",
            "source_run_id",
            "source_kind",
            "source_status",
            "influence_modes",
            "authoritative_for",
            "may_not_use_for",
            "scope",
            "applicability_reasons",
            "contamination_status",
            "contamination_check_ref",
        )
        if hasattr(record, key)
    }


def _payload_text(
    payload: dict[str, Any],
    key: str,
    *,
    fallback: str = "",
) -> str:
    value = payload.get(key, fallback)
    raw = getattr(value, "value", value)
    text = str(raw or "").strip()
    return text or fallback


def _payload_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        return [str(item) for item in value.values() if str(item)]
    if isinstance(value, list | tuple | set):
        return [str(getattr(item, "value", item)) for item in value if str(item)]
    return [str(getattr(value, "value", value))]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _source_query_parent_node(source: Any, query_node_by_id: dict[str, str]) -> str | None:
    query = str(getattr(source, "search_query", "") or "")
    if not query_node_by_id:
        return None
    for query_id, node_id in query_node_by_id.items():
        if query_id and query_id in query:
            return node_id
    return next(iter(query_node_by_id.values()))


__all__ = [
    "REQUIRE_RESEARCH_DAG_FOR_PUBLICATION_FLAG",
    "RESEARCH_DAG_FEATURE_FLAG",
    "SELECTED_RESEARCH_DAG_WORKFLOWS",
    "classify_runtime_step",
    "classify_tool_step",
    "is_research_dag_enabled",
    "is_research_dag_required_for_publication",
    "project_memory_influence_records_to_research_dag",
    "project_provenance_graph_to_research_dag",
    "project_reflexive_memory_events_to_research_dag",
    "project_tool_call_result_to_research_node",
    "project_tool_loop_result_to_research_dag",
    "project_web_evidence_bundle_to_research_dag",
    "project_workflow_execution_to_research_dag",
    "validate_memory_influence_dag_attribution",
    "validate_memory_influence_record_dag_attribution",
]
