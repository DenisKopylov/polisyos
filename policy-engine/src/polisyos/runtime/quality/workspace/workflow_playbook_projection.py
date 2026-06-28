"""GY Phase-2 playbook projections over legacy Scientist workflows."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.pdc import OperationClass, SearchBlockerRecord
from polisyos.runtime.quality.workspace.scientist_node_adapters import (
    ScientistNodeAdapter,
    validate_scientist_node_adapter_shape,
)

WORKFLOW_PLAYBOOK_RULE_VERSION = "policyos.gy.phase2.playbooks.v1"

_WORKFLOW_ALIAS_ORDER: dict[str, tuple[str, ...]] = {
    "scientist_policy_design": (
        "build_literature_prior",
        "run_causal_evaluation",
        "run_normative_arbitration",
    ),
    "scientist_causal_full": (
        "build_literature_prior",
        "reconcile_causal_graph",
        "run_causal_evaluation",
        "run_normative_arbitration",
    ),
    "scientist_policy_verified": (
        "plan_policy_request",
        "run_causal_evaluation",
        "run_normative_arbitration",
    ),
}
_ALIAS_OPERATION_CLASS: dict[str, OperationClass] = {
    "build_literature_prior": OperationClass.BIND,
    "plan_policy_request": OperationClass.BIND,
    "reconcile_causal_graph": OperationClass.REFINE,
    "run_causal_evaluation": OperationClass.ESTIMATE,
    "run_normative_arbitration": OperationClass.VERIFY,
}


class PlaybookStep(BaseModel):
    """One legacy-node-backed step inside a playbook projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    operation_class: OperationClass
    legacy_alias: str
    adapter_operation_id: str
    adapter_id: str
    source_workflow_id: str
    node_id: str
    required_ports: list[str] = Field(default_factory=list)
    produced_ports: list[str] = Field(default_factory=list)


class PlaybookTrajectory(BaseModel):
    """Default trajectory the loop may follow or deviate from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    playbook_id: str
    source_workflow_id: str
    default_operation_classes: list[OperationClass]
    steps: list[PlaybookStep]
    authority_path_disposition: Literal["loop_only"]


class PlaybookRegistry(BaseModel):
    """Committed Phase-2 playbook registry discovered by the runtime loop."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    playbooks: dict[str, PlaybookTrajectory]
    rule_version: str = WORKFLOW_PLAYBOOK_RULE_VERSION


class PlaybookSelection(BaseModel):
    """Intent-router decision for a Phase-2 request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    playbook_id: str
    selection_source: Literal["intent"]
    matched_intent_keys: list[str]
    legacy_workflow_id: str | None = None
    legacy_workflow_id_disposition: Literal["absent", "legacy_shadow_context"]
    rule_version: str = WORKFLOW_PLAYBOOK_RULE_VERSION


class WorkflowPlaybookTrace(BaseModel):
    """Replay trace proving whether and why the loop deviated from a playbook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    playbook_id: str
    default_operation_classes: list[OperationClass]
    executed_operation_classes: list[OperationClass]
    executed_legacy_aliases: list[str] = Field(default_factory=list)
    out_of_scope_steps: list[dict[str, str]] = Field(default_factory=list)
    deviated_from_default: bool
    deviation_operation: OperationClass | None = None
    deviation_reason: str | None = None
    blockers: list[SearchBlockerRecord] = Field(default_factory=list)
    authority_path_disposition: Literal["loop_only"] = "loop_only"


def build_workflow_playbook_registry(*, node_registry: object | None = None) -> PlaybookRegistry:
    """Project the three Phase-2 playbooks from canonical Scientist workflow specs."""

    workflows = _phase2_workflow_specs()
    registry = node_registry or _default_node_registry()
    return PlaybookRegistry(
        playbooks={
            workflow_id: _trajectory_from_workflow(
                workflow=workflow,
                selected_aliases=_WORKFLOW_ALIAS_ORDER[workflow_id],
                node_registry=registry,
            )
            for workflow_id, workflow in workflows.items()
        }
    )


class _WorkflowInvocation(Protocol):
    alias: str
    node_id: object


class _WorkflowSpec(Protocol):
    workflow_id: str
    nodes: list[_WorkflowInvocation]


class _NodeRegistry(Protocol):
    def get(self, node_id: object) -> object: ...


def select_playbook_for_intent(intent: dict[str, object]) -> PlaybookSelection:
    """Select a playbook from intent semantics; workflow_id is shadow context only."""

    legacy_workflow_id = _string_or_none(intent.get("workflow_id"))
    keys = [
        key
        for key in (
            "design_problem_id",
            "policy_question",
            "causal_variables",
            "verification_required",
        )
        if key in intent
    ]
    if _string_or_none(intent.get("policy_answer_mode")) == "verified_async":
        playbook_id = "scientist_policy_verified"
    elif intent.get("causal_variables") or intent.get("observational_data_ref"):
        playbook_id = "scientist_causal_full"
    elif intent.get("design_problem_id") or intent.get("policy_question"):
        playbook_id = "scientist_policy_design"
    else:
        playbook_id = "scientist_policy_design"
    return PlaybookSelection(
        playbook_id=playbook_id,
        selection_source="intent",
        matched_intent_keys=keys,
        legacy_workflow_id=legacy_workflow_id,
        legacy_workflow_id_disposition=(
            "legacy_shadow_context" if legacy_workflow_id is not None else "absent"
        ),
    )


def trace_playbook_execution(
    *,
    selection: PlaybookSelection,
    executed_operation_classes: list[OperationClass],
    deviated_from_default: bool,
    deviation_operation: OperationClass | None = None,
    deviation_reason: str | None = None,
    blockers: list[SearchBlockerRecord] | None = None,
    executed_legacy_aliases: list[str] | None = None,
    out_of_scope_steps: list[dict[str, str]] | None = None,
) -> WorkflowPlaybookTrace:
    """Build the replay trace for a playbook execution or deviation."""

    registry = build_workflow_playbook_registry()
    playbook = registry.playbooks[selection.playbook_id]
    return WorkflowPlaybookTrace(
        playbook_id=selection.playbook_id,
        default_operation_classes=playbook.default_operation_classes,
        executed_operation_classes=executed_operation_classes,
        executed_legacy_aliases=executed_legacy_aliases or [],
        out_of_scope_steps=out_of_scope_steps or [],
        deviated_from_default=deviated_from_default,
        deviation_operation=deviation_operation,
        deviation_reason=deviation_reason,
        blockers=blockers or [],
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _phase2_workflow_specs() -> dict[str, _WorkflowSpec]:
    from polisyos.scientist.orchestration.workflows.causal_full import (
        causal_full_workflow_spec,
    )
    from polisyos.scientist.orchestration.workflows.policy_design import (
        policy_design_workflow_spec,
    )
    from polisyos.scientist.orchestration.workflows.policy_verified import (
        policy_verified_workflow_spec,
    )

    return {
        "scientist_policy_design": policy_design_workflow_spec(),
        "scientist_causal_full": causal_full_workflow_spec(),
        "scientist_policy_verified": policy_verified_workflow_spec(),
    }


def _default_node_registry() -> _NodeRegistry:
    from polisyos.scientist.orchestration.workflows.builder import (
        build_registry_with_builtin_nodes,
    )

    return build_registry_with_builtin_nodes(include_discovered_nodes=False)


def _trajectory_from_workflow(
    *,
    workflow: _WorkflowSpec,
    selected_aliases: tuple[str, ...],
    node_registry: _NodeRegistry,
) -> PlaybookTrajectory:
    invocations = {item.alias: item for item in workflow.nodes}
    steps = [
        _step_from_invocation(
            workflow_id=workflow.workflow_id,
            invocation=invocations[alias],
            node_registry=node_registry,
        )
        for alias in selected_aliases
        if alias in invocations
    ]
    return PlaybookTrajectory(
        playbook_id=workflow.workflow_id,
        source_workflow_id=workflow.workflow_id,
        default_operation_classes=list(
            dict.fromkeys(step.operation_class for step in steps).keys()
        ),
        authority_path_disposition="loop_only",
        steps=steps,
    )


def _step_from_invocation(
    *,
    workflow_id: str,
    invocation: _WorkflowInvocation,
    node_registry: _NodeRegistry,
) -> PlaybookStep:
    operation_class = _ALIAS_OPERATION_CLASS[invocation.alias]
    node = node_registry.get(invocation.node_id)
    operation_id = f"phase2.{operation_class.value.lower()}.{invocation.alias}"
    adapter = ScientistNodeAdapter.from_node(
        node,
        operation_id=operation_id,
        operation_class=operation_class,
        authority_transform={
            "kind": "hint_only",
            "requested_decision_grade": "descriptive_only",
            "rule_ref": WORKFLOW_PLAYBOOK_RULE_VERSION,
        },
        legacy_alias=invocation.alias,
    )
    shape = validate_scientist_node_adapter_shape(adapter)
    if not shape.passed:
        raise ValueError(f"Phase-2 adapter shape failed for {invocation.alias}: {shape.failures}")
    return PlaybookStep(
        step_id=f"{workflow_id}.{invocation.alias}",
        operation_class=operation_class,
        legacy_alias=invocation.alias,
        adapter_operation_id=operation_id,
        adapter_id=adapter.adapter_id,
        source_workflow_id=workflow_id,
        node_id=str(invocation.node_id),
        required_ports=list(adapter.required_inputs),
        produced_ports=list(adapter.produced_outputs),
    )


__all__ = [
    "PlaybookRegistry",
    "PlaybookSelection",
    "PlaybookStep",
    "PlaybookTrajectory",
    "WorkflowPlaybookTrace",
    "build_workflow_playbook_registry",
    "select_playbook_for_intent",
    "trace_playbook_execution",
]
