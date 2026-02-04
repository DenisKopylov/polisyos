from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import CompileRequest, FoundryCompileConfig, FoundryValidationFlags
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_SLOT_LAYOUT_REF,
    ARTIFACT_TREASURY_PLAN_REF,
    INPUT_POLICY_IR_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_compile_foundry@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Compile Foundry",
    description="Compile Trinity policy into Foundry exec plan.",
    tags=["builtin", "compile"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        f"inputs.{INPUT_POLICY_IR_REF}",
        f"inputs.{INPUT_REGISTRY_BUNDLE_REF}",
    ],
    state_writes=[
        f"reports_index.{REPORT_COMPILE_REPORT_REF}",
        f"reports_index.{REPORT_LINK_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_EXEC_PLAN_REF}",
        f"artifacts_index.{ARTIFACT_PROGRAM_GRAPH_REF}",
        f"artifacts_index.{ARTIFACT_SLOT_LAYOUT_REF}",
        f"artifacts_index.{ARTIFACT_TREASURY_PLAN_REF}",
    ],
    produces=[
        REPORT_COMPILE_REPORT_REF,
        REPORT_LINK_REPORT_REF,
        ARTIFACT_EXEC_PLAN_REF,
        ARTIFACT_PROGRAM_GRAPH_REF,
        ARTIFACT_SLOT_LAYOUT_REF,
        ARTIFACT_TREASURY_PLAN_REF,
    ],
)


@dataclass(frozen=True)
class CompileFoundryNode:
    compile_config: FoundryCompileConfig = field(default_factory=FoundryCompileConfig)
    validation_flags: FoundryValidationFlags = field(default_factory=FoundryValidationFlags)

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> "CompileFoundryNode":
        if not params:
            return self
        config = self.compile_config.model_copy(deep=True)
        flags = self.validation_flags.model_copy(deep=True)
        for key, value in params.items():
            if key in config.model_fields:
                setattr(config, key, value)
                continue
            if key in flags.model_fields:
                setattr(flags, key, value)
        return replace(self, compile_config=config, validation_flags=flags)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ctx.foundry is None:
            error = NodeError(
                code=node_errors.ERROR_FOUNDATION_MISSING,
                message="Foundry port is not configured",
            )
            return NodeOutcome(status="fail", state=state, error=error)

        policy_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
        if policy_ref is None:
            policy_ref = state.inputs.get(INPUT_POLICY_IR_REF)
        if policy_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing policy reference for compilation",
                details={"required": [INPUT_TRINITY_BUNDLE_REF, INPUT_POLICY_IR_REF]},
            )
            return NodeOutcome(status="fail", state=state, error=error)

        if policy_ref.kind != "ir.trinity_bundle":
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message="Unsupported policy kind for Foundry compile",
                details={
                    "expected_kind": "ir.trinity_bundle",
                    "actual_kind": policy_ref.kind,
                },
            )
            return NodeOutcome(status="fail", state=state, error=error)

        registry_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)

        request = CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry_ref,
            compile_config=self.compile_config,
            validation_flags=self.validation_flags,
        )

        result = ctx.foundry.compile(ctx.store, request)

        new_state = state.model_copy(deep=True)
        new_state.reports_index[REPORT_COMPILE_REPORT_REF] = result.compile_report_ref

        if result.exec_plan_ref is not None:
            new_state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = result.exec_plan_ref

        for item in result.derived_refs:
            role = item.role
            if role == "program_graph":
                new_state.artifacts_index[ARTIFACT_PROGRAM_GRAPH_REF] = item.ref
            elif role == "exec_plan":
                new_state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = item.ref
            elif role == "link_report":
                new_state.reports_index[REPORT_LINK_REPORT_REF] = item.ref
            elif role == "slot_layout":
                new_state.artifacts_index[ARTIFACT_SLOT_LAYOUT_REF] = item.ref
            elif role == "treasury_plan":
                new_state.artifacts_index[ARTIFACT_TREASURY_PLAN_REF] = item.ref

        artifacts = [result.compile_report_ref]
        if result.exec_plan_ref is not None:
            artifacts.append(result.exec_plan_ref)
        artifacts.extend([item.ref for item in result.derived_refs])

        if not result.ok:
            error = NodeError(
                code=node_errors.ERROR_FOUNDRY_COMPILE_FAILED,
                message="Foundry compile failed",
                details={"compile_report_ref": result.compile_report_ref.model_dump()},
            )
            event = NodeEvent(level="error", message="Foundry compile returned ok=False")
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=artifacts,
                events=[event],
                error=error,
            )

        return NodeOutcome(status="ok", state=new_state, artifacts=artifacts)
