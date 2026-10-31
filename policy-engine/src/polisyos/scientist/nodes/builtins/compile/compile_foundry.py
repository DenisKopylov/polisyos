"""Public compile compile foundry module API."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.core.contracts.execution_plan import ExecutionPlan, ExecutionPlanRef
from polisyos.core.contracts.foundry import (
    METHOD_METRIC_BINDING_LIMIT,
    CompileRequest,
    CompileResult,
    FoundryCompileConfig,
    FoundryValidationFlags,
    MethodMetricBindingRequest,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_METHOD_METRIC_BINDING_SET_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_SLOT_LAYOUT_REF,
    ARTIFACT_TREASURY_PLAN_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_LINK_REPORT_REF,
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

_EXECUTION_PLAN_INPUT_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
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
        f"inputs.{INPUT_REGISTRY_BUNDLE_REF}",
        "execution_plan_ref",
        "params.method_metric_bindings",
    ],
    state_writes=[
        f"reports_index.{REPORT_COMPILE_REPORT_REF}",
        f"reports_index.{REPORT_LINK_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_EXEC_PLAN_REF}",
        f"artifacts_index.{ARTIFACT_LOWERED_IR_REF}",
        f"artifacts_index.{ARTIFACT_METHOD_METRIC_BINDING_SET_REF}",
        f"artifacts_index.{ARTIFACT_PROGRAM_GRAPH_REF}",
        f"artifacts_index.{ARTIFACT_SLOT_LAYOUT_REF}",
        f"artifacts_index.{ARTIFACT_TREASURY_PLAN_REF}",
    ],
    produces=[
        REPORT_COMPILE_REPORT_REF,
        REPORT_LINK_REPORT_REF,
        ARTIFACT_EXEC_PLAN_REF,
        ARTIFACT_LOWERED_IR_REF,
        ARTIFACT_METHOD_METRIC_BINDING_SET_REF,
        ARTIFACT_PROGRAM_GRAPH_REF,
        ARTIFACT_SLOT_LAYOUT_REF,
        ARTIFACT_TREASURY_PLAN_REF,
    ],
)


@dataclass(frozen=True)
class CompileFoundryNode:
    """Compile-stage DAG node that turns a linked Trinity bundle into Foundry runtime artifacts.

    Reads `inputs.trinity_bundle_ref` and the registry bundle, requires a configured
    Foundry port, and writes compile/link reports plus execution-plan, lowered-IR,
    program-graph, slot-layout, and treasury-plan refs back into workflow state.
    """

    compile_config: FoundryCompileConfig = field(default_factory=FoundryCompileConfig)
    validation_flags: FoundryValidationFlags = field(default_factory=FoundryValidationFlags)
    method_metric_bindings: tuple[MethodMetricBindingRequest, ...] = ()

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> CompileFoundryNode:
        if not params:
            return self
        config = self.compile_config.model_copy(deep=False)
        flags = self.validation_flags.model_copy(deep=False)
        method_metric_bindings = self.method_metric_bindings
        for key, value in params.items():
            if key == "method_metric_bindings":
                if not isinstance(value, (list, tuple)):
                    raise ValueError("method_metric_bindings_must_be_a_list_or_tuple")
                method_metric_bindings = tuple(
                    MethodMetricBindingRequest.model_validate(item) for item in value
                )
                continue
            if key in config.model_fields:
                setattr(config, key, value)
                continue
            if key in flags.model_fields:
                setattr(flags, key, value)
        return replace(
            self,
            compile_config=config,
            validation_flags=flags,
            method_metric_bindings=method_metric_bindings,
        )

    def _prepare_request(
        self, ctx: ExecutionContext, state: ExperimentState
    ) -> CompileRequest | NodeOutcome:
        """Prepare the canonical request without assigning an Engine outcome."""
        if ctx.foundry is None:
            error = NodeError(
                code=node_errors.ERROR_FOUNDATION_MISSING,
                message="Foundry port is not configured",
            )
            return NodeOutcome(status="fail", state=state, error=error)

        policy_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
        if policy_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing policy reference for compilation",
                details={"required": [INPUT_TRINITY_BUNDLE_REF]},
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

        # A workflow request may select the same bounded typed compiler inputs
        # as a configured node. The compiler still reconciles these selections
        # against the actual policy, plan, method ABI and registry.
        effective_bindings = self.method_metric_bindings
        if "method_metric_bindings" in state.params:
            raw_bindings = state.params["method_metric_bindings"]
            # Admitted workflow JSON arrays have a journaled list view. Preserve
            # the list contract without requiring the exact builtin class.
            if (
                not isinstance(raw_bindings, list)
                or len(raw_bindings) > METHOD_METRIC_BINDING_LIMIT
            ):
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message="Invalid method_metric_bindings request",
                    ),
                )
            try:
                requested_bindings = tuple(
                    MethodMetricBindingRequest.model_validate(item, strict=True)
                    for item in raw_bindings
                )
            except (TypeError, ValueError, ValidationError):
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message="Invalid method_metric_bindings request",
                    ),
                )
            if effective_bindings and requested_bindings != effective_bindings:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message="Conflicting method_metric_bindings selections",
                    ),
                )
            effective_bindings = requested_bindings

        method_execution_plan_ref: ExecutionPlanRef | None = None
        schema_version = "1.0"
        selected_plan_ref = state.execution_plan_ref
        if not effective_bindings and selected_plan_ref is not None:
            try:
                from polisyos.core.artifacts import load_core_json_artifact

                typed_plan_ref = ExecutionPlanRef.model_validate(
                    selected_plan_ref.model_dump(mode="python")
                )
                if (
                    typed_plan_ref.kind != "scientist.execution_plan"
                    or typed_plan_ref.media_type != "application/json"
                ):
                    raise ValueError("selected_execution_plan_kind_or_media_type_invalid")
                selected_plan = ExecutionPlan.model_validate(
                    load_core_json_artifact(ctx.store, typed_plan_ref)
                )
                if selected_plan.method_edges and not selected_plan.method_dag:
                    error = NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message="Selected edge-only method execution plan is unsupported",
                        details={
                            "execution_plan_ref": typed_plan_ref.model_dump(mode="json"),
                            "method_dag_node_count": 0,
                            "method_edge_count": len(selected_plan.method_edges),
                            "required": ["method_dag"],
                        },
                    )
                    return NodeOutcome(status="fail", state=state, error=error)
                if selected_plan.method_dag:
                    if (
                        typed_plan_ref.manifest_profile_sha256 is None
                        or policy_ref.manifest_profile_sha256 is None
                    ):
                        raise ValueError("selected_method_execution_plan_requires_exact_profiles")
                    method_execution_plan_ref = typed_plan_ref
                    schema_version = "1.2"
            except _EXECUTION_PLAN_INPUT_LOAD_ERRORS as exc:
                error = NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Failed to load selected execution plan: {exc}",
                )
                return NodeOutcome(status="fail", state=state, error=error)

        if effective_bindings:
            selected_plan_ref = state.execution_plan_ref
            if selected_plan_ref is None:
                error = NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Method metric selection requires the selected execution plan",
                    details={"required": ["execution_plan_ref"]},
                )
                return NodeOutcome(status="fail", state=state, error=error)
            try:
                method_execution_plan_ref = ExecutionPlanRef.model_validate(
                    selected_plan_ref.model_dump(mode="python")
                )
            except (TypeError, ValueError) as exc:
                error = NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Selected execution plan ref is invalid: {exc}",
                )
                return NodeOutcome(status="fail", state=state, error=error)
            if (
                method_execution_plan_ref.kind != "scientist.execution_plan"
                or method_execution_plan_ref.media_type != "application/json"
                or method_execution_plan_ref.manifest_profile_sha256 is None
                or policy_ref.manifest_profile_sha256 is None
            ):
                error = NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Method metric selection requires exact selected plan and candidate refs",
                )
                return NodeOutcome(status="fail", state=state, error=error)
            schema_version = "1.2"

        request = CompileRequest(
            schema_version=schema_version,
            input_kind="trinity",
            policy_ref=policy_ref,
            method_execution_plan_ref=method_execution_plan_ref,
            registry_bundle_ref=registry_ref,
            compile_config=self.compile_config,
            validation_flags=self.validation_flags,
            method_metric_bindings=list(effective_bindings),
            return_selected_profile=True,
        )

        return request

    @staticmethod
    def _apply_result(
        state: ExperimentState, result: CompileResult
    ) -> tuple[ExperimentState, list[ArtifactRef]]:
        """Apply canonical compile outputs before a caller chooses its outcome contract."""
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.reports_index[REPORT_COMPILE_REPORT_REF] = result.compile_report_ref

        if result.exec_plan_ref is not None:
            new_state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = result.exec_plan_ref

        for item in result.derived_refs:
            role = item.role
            if role == "program_graph":
                new_state.artifacts_index[ARTIFACT_PROGRAM_GRAPH_REF] = item.ref
            elif role == "lowered_ir":
                new_state.artifacts_index[ARTIFACT_LOWERED_IR_REF] = item.ref
            elif role == "method_metric_binding_set":
                new_state.artifacts_index[ARTIFACT_METHOD_METRIC_BINDING_SET_REF] = item.ref
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
        return new_state, artifacts

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Compile using the canonical producer and retain ordinary fail-fast semantics."""
        prepared = self._prepare_request(ctx, state)
        if isinstance(prepared, NodeOutcome):
            return prepared
        foundry = ctx.foundry
        if foundry is None:
            raise RuntimeError("foundry_port_changed_during_request_preparation")
        result = foundry.compile(ctx.store, prepared)
        new_state, artifacts = self._apply_result(state, result)

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
