"""Public planning run preflight module API."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    MethodCatalogSnapshot,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.llm.cycle import persist_preflight_report, preflight_execution_plan
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXECUTION_PLAN_REF,
    ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF,
    ARTIFACT_PREFLIGHT_REPORT_REF,
    INPUT_EXECUTION_PLAN_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_preflight@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Preflight",
    description="Validate ExecutionPlan against live method catalog before execute.",
    tags=["builtin", "planning", "preflight"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_EXECUTION_PLAN_REF}",
        f"artifacts_index.{ARTIFACT_EXECUTION_PLAN_REF}",
        f"artifacts_index.{ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF}",
    ],
    state_writes=[
        "params.preflight_ready",
        "params.preflight_diagnostics",
        "params.preflight_report_ref",
        f"artifacts_index.{ARTIFACT_PREFLIGHT_REPORT_REF}",
        "preflight_report_ref",
    ],
    produces=[ARTIFACT_PREFLIGHT_REPORT_REF],
)

_PREFLIGHT_INPUT_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


@dataclass(frozen=True)
class RunPreflightNode:
    """Planning gate that checks the execution plan against the available method catalog.

    Requires an execution-plan ref and method-catalog snapshot, persists a preflight
    report, and writes readiness diagnostics that determine whether expensive runtime
    stages are allowed to proceed.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        plan_ref = _resolve_execution_plan_ref(state)
        snapshot_ref = state.artifacts_index.get(ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF)
        if plan_ref is None or snapshot_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Preflight requires execution plan and method catalog snapshot",
                details={
                    "required": [INPUT_EXECUTION_PLAN_REF, ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF],
                },
            )
            return NodeOutcome(status="fail", state=state, error=error)

        try:
            plan_payload = from_canonical_bytes(ctx.store.get_bytes(plan_ref.artifact_id))
            snapshot_payload = from_canonical_bytes(ctx.store.get_bytes(snapshot_ref.artifact_id))
            plan = ExecutionPlan.model_validate(plan_payload)
            snapshot = MethodCatalogSnapshot.model_validate(snapshot_payload)
        except _PREFLIGHT_INPUT_LOAD_ERRORS as exc:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"Failed to load preflight inputs: {exc}",
            )
            return NodeOutcome(status="fail", state=state, error=error)

        report = preflight_execution_plan(plan, snapshot)
        report.plan_ref = plan_ref
        report.catalog_snapshot_ref = snapshot_ref
        report_ref = persist_preflight_report(
            ctx.store,
            report,
            inputs=[
                InputRef(artifact_id=plan_ref.artifact_id, role="execution_plan"),
                InputRef(artifact_id=snapshot_ref.artifact_id, role="method_catalog_snapshot"),
            ],
        )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["preflight_ready"] = bool(report.ready_to_run)
        new_state.params["preflight_diagnostics"] = [
            row.model_dump(mode="json") for row in report.diagnostics
        ]
        new_state.params["preflight_report_ref"] = str(report_ref.artifact_id)
        new_state.artifacts_index[ARTIFACT_PREFLIGHT_REPORT_REF] = report_ref
        new_state.preflight_report_ref = report_ref
        event = NodeEvent(
            level="info" if report.ready_to_run else "warn",
            message=f"Preflight ready={str(report.ready_to_run).lower()}",
            attrs={"diagnostics": len(report.diagnostics)},
        )
        if not report.ready_to_run:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message="Preflight validation failed",
                details={
                    "diagnostics": [item.model_dump(mode="json") for item in report.diagnostics]
                },
            )
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=[report_ref],
                events=[event],
                error=error,
            )
        return NodeOutcome(status="ok", state=new_state, artifacts=[report_ref], events=[event])


def _resolve_execution_plan_ref(state: ExperimentState) -> ArtifactRef | None:
    from_input = state.inputs.get(INPUT_EXECUTION_PLAN_REF)
    if from_input is not None:
        return from_input
    return state.artifacts_index.get(ARTIFACT_EXECUTION_PLAN_REF)


__all__ = ["RunPreflightNode"]
