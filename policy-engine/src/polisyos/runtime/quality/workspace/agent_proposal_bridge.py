"""Agent-as-proposer bridge for GY Phase 2."""

from __future__ import annotations

import importlib
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.pdc import (
    AgentDecisionRecord,
    ApplicabilityResult,
    ArtifactRef,
    MethodPlan,
    OperationClass,
    OperationInvocationRecord,
    SearchBlockerRecord,
    SearchLedgerEvent,
    SearchTerminalKind,
    VOISelectionAudit,
)

AGENT_PROPOSAL_BRIDGE_RULE_VERSION = "policyos.gy.phase2.agent.v1"


class AgentEventBundle(BaseModel):
    """Persisted Ring-1 artifacts for one agent/tool-loop action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_record: AgentDecisionRecord
    invocation: OperationInvocationRecord
    ledger_event: SearchLedgerEvent
    method_plan: MethodPlan


class AgentNoClientBlock(BaseModel):
    """Fail-closed result for an agent run without an LLM/tool-loop client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicability: ApplicabilityResult
    blocker: SearchBlockerRecord
    synthetic_audit_created: Literal[False] = False


class AgentEventBridge:
    """Record agent proposals as Ring-1 events and never as authority."""

    async def run_tool_loop_proposal(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        client: object | None,
        system: str,
        user: str,
        candidate_operations: list[OperationClass],
        toolkit: object | None = None,
        max_iterations: int = 10,
    ) -> AgentEventBundle | AgentNoClientBlock:
        """Run the existing Scientist tool loop and persist its Ring-1 event."""

        if client is None:
            return self.no_client_blocker(workspace_id=workspace_id, invocation_id=invocation_id)
        scientist = importlib.import_module("polisyos.scientist")
        tool_loop_module = importlib.import_module("polisyos.scientist.agent.tools.tool_loop")
        knowledge_toolkit_cls = scientist.KnowledgeToolkit
        build_knowledge_tool_registry = scientist.build_knowledge_tool_registry
        resolved_toolkit = toolkit or knowledge_toolkit_cls()
        loop_result = await tool_loop_module.run_tool_loop(
            client=client,
            system=system,
            user=user,
            tool_registry=build_knowledge_tool_registry(resolved_toolkit),
            max_iterations=max_iterations,
        )
        tool_calls = getattr(loop_result, "tool_calls_made", None)
        if tool_calls is None:
            tool_calls = getattr(loop_result, "tool_calls", [])
        return self.record_tool_loop(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            role="tool_loop",
            selected_proposal_ref=f"tool-loop-result-{_slug(invocation_id)}",
            tool_calls=_tool_call_names(tool_calls),
            candidate_operations=candidate_operations,
        )

    def record_tool_loop(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        role: Literal["pi", "drafter", "critic", "tool_loop"],
        selected_proposal_ref: str | None,
        tool_calls: list[str],
        candidate_operations: list[OperationClass],
    ) -> AgentEventBundle:
        """Persist one candidate-only tool-loop decision."""

        from polisyos.runtime.quality.proving_ground.bounded_request_agent import (
            build_gy_phase2_agent_event_records,
        )

        records = build_gy_phase2_agent_event_records(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            role=role,
            selected_proposal_ref=selected_proposal_ref,
            tool_calls=tool_calls,
            candidate_operations=candidate_operations,
        )
        return AgentEventBundle(
            decision_record=records["decision_record"],  # type: ignore[arg-type]
            invocation=records["invocation"],  # type: ignore[arg-type]
            ledger_event=records["ledger_event"],  # type: ignore[arg-type]
            method_plan=records["method_plan"],  # type: ignore[arg-type]
        )

    def persist_event_bundle(
        self,
        *,
        store: FileSystemCAS,
        bundle: AgentEventBundle,
    ) -> list[ArtifactRef]:
        """Persist all Ring-1 agent event records to CAS."""

        records: list[tuple[str, object]] = [
            ("AgentDecisionRecord", bundle.decision_record),
            ("OperationInvocationRecord", bundle.invocation),
            ("SearchLedgerEvent", bundle.ledger_event),
            ("MethodPlan", bundle.method_plan),
        ]
        refs: list[ArtifactRef] = []
        for artifact_type, record in records:
            payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
            core_ref = store.put_json(
                payload,
                PutOptions(
                    kind=f"gy.agent.{artifact_type}",
                    media_type="application/json",
                    schema=SchemaInfo(name=f"policyos.gy.phase2.{artifact_type}", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            refs.append(
                ArtifactRef.from_payload(
                    artifact_id=str(core_ref.artifact_id),
                    artifact_type=artifact_type,
                    payload=payload,
                    schema_ref=f"policyos.gy.phase2.{artifact_type}.v1",
                    uri=f"cas://{core_ref.artifact_id}",
                    version="phase2.v1",
                )
            )
        return refs

    def no_client_blocker(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
    ) -> AgentNoClientBlock:
        """Return a repair blocker instead of fabricating an agent audit."""

        applicability = ApplicabilityResult(
            result_id="applicability-agent-client",
            invocation_id=invocation_id,
            status="repair_required",
            checked_preconditions=[
                {
                    "predicate_id": "phase2.agent.client_present",
                    "status": "failed",
                    "rule_version": AGENT_PROPOSAL_BRIDGE_RULE_VERSION,
                }
            ],
            failed_preconditions=[
                {
                    "predicate_id": "phase2.agent.client_present",
                    "reason": "agent_client_missing",
                    "severity": "hard",
                }
            ],
            type_errors=[],
            repair_options=[
                {
                    "operation_class": OperationClass.REFINE.value,
                    "reason": "Provide a real agent client or skip the agent proposer.",
                }
            ],
        )
        blocker = SearchBlockerRecord(
            blocker_id="blocker-agent-client",
            workspace_id=workspace_id,
            operation_class=OperationClass.REFINE,
            blocked_port="agent.client",
            missing_input="agent_client",
            reason="No agent client was supplied; synthetic audits are forbidden.",
            applicability_result_ref=applicability.result_id,
            repair_options=applicability.repair_options,
            producer_missing_label="producer_missing",
        )
        return AgentNoClientBlock(applicability=applicability, blocker=blocker)


def normalize_agent_voi_scores(
    *,
    workspace_id: str,
    selected_terminal: str | SearchTerminalKind,
    agent_scores: dict[str, Any],
    supported_action_refs: set[str],
) -> VOISelectionAudit:
    """Normalize candidate-only agent VOI scores through the GY-H audit shape."""

    terminal = (
        selected_terminal
        if isinstance(selected_terminal, SearchTerminalKind)
        else SearchTerminalKind(selected_terminal)
    )
    normalized: dict[str, float] = {}
    rejected_or_clipped: list[dict[str, Any]] = []
    for action_ref, raw_value in sorted(agent_scores.items()):
        if action_ref not in supported_action_refs:
            rejected_or_clipped.append(
                {
                    "action_ref": action_ref,
                    "reason": "unsupported_action",
                    "original_score": _json_score(raw_value),
                }
            )
            continue
        try:
            score = float(raw_value)
        except (TypeError, ValueError):
            rejected_or_clipped.append(
                {
                    "action_ref": action_ref,
                    "reason": "non_numeric_score",
                    "original_score": _json_score(raw_value),
                }
            )
            continue
        if not math.isfinite(score):
            rejected_or_clipped.append(
                {
                    "action_ref": action_ref,
                    "reason": "non_finite_score",
                    "original_score": _json_score(raw_value),
                }
            )
            continue
        clipped = min(1.0, max(0.0, score))
        if clipped != score:
            rejected_or_clipped.append(
                {
                    "action_ref": action_ref,
                    "reason": "score_clipped_to_unit_interval",
                    "original_score": score,
                    "normalized_score": clipped,
                }
            )
        normalized[action_ref] = clipped
    return VOISelectionAudit(
        audit_id=f"voi-agent-{_slug(workspace_id)}",
        workspace_id=workspace_id,
        selected_terminal=terminal,
        candidates=[
            {"action_ref": action_ref, "normalized_score": score}
            for action_ref, score in sorted(normalized.items())
        ],
        selected_action_ref=None,
        continuation_allowed=False,
        decision_rule_ref="policyos.gy.anytime_exit.v1",
        threshold=0.0,
        notes=["Agent VOI scores are candidate-only and normalized before GY-H use."],
        agent_suggested_scores={key: _json_score(value) for key, value in agent_scores.items()},
        normalized_scores=normalized,
        rejected_or_clipped_inputs=rejected_or_clipped,
        selected_action={},
        bias_probe_result={"rule_version": AGENT_PROPOSAL_BRIDGE_RULE_VERSION},
    )


def _json_score(value: object) -> float | str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isfinite(score):
        return score
    return str(score)


def _tool_call_names(tool_calls: object) -> list[str]:
    if not isinstance(tool_calls, list):
        return []
    names: list[str] = []
    for item in tool_calls:
        if isinstance(item, dict):
            name = item.get("name") or item.get("tool_name")
        else:
            name = getattr(item, "name", None) or getattr(item, "tool_name", None)
        if name:
            names.append(str(name))
    return names


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


__all__ = [
    "AgentEventBridge",
    "AgentEventBundle",
    "AgentNoClientBlock",
    "normalize_agent_voi_scores",
]
