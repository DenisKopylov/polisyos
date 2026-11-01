"""Engine-owned child runs for synchronous, local sub-workflows.

The parent keeps its lifecycle.  A child has its own Core writer and a stable
logical identity, and a repeated delivery can only reuse a verified terminal
result.  Incomplete or ambiguous children are never started again implicitly.
This local route does not provide a control-job fence or a Python sandbox.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core import run as core_run
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.orchestration.engine.execution_admission import (
    ManagedSubWorkflowDefinition,
    capture_managed_subworkflow_definition,
)
from polisyos.scientist.orchestration.engine.finalization import (
    FINAL_WORKFLOW_REPORT_STATE_PATH,
    FINALIZATION_KIND,
    FINALIZATION_SCHEMA_NAME,
    WorkflowStateFinalization,
)
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutionResult
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.sub_workflow import SubWorkflowNode

_CANON = CanonSpec(forbid_floats=False)
_BINDING_KIND = "scientist.child_workflow_binding"
_BINDING_SCHEMA = "polisyos.scientist.orchestration.engine.ChildWorkflowBinding"
_BINDING_VERSION = "1.2"
_ADMISSION_KIND = "scientist.child_workflow_input_admission"
_ADMISSION_SCHEMA = "polisyos.scientist.orchestration.engine.ChildWorkflowInputAdmission"


class ChildWorkflowOutcomeUnknownError(core_run.ChildOutcomeUnknownError):
    """The child may have executed; reconcile its stable run before another dispatch."""

    def __init__(self, *, run_id: str, run_dir: Path, reason: str) -> None:
        super().__init__(run_id=run_id, run_dir=run_dir, message=reason)
        self.reason = reason


class _ChildBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.2"] = "1.2"
    parent_run_id: str
    parent_alias: str
    parent_basis_ref: ArtifactRef
    child_run_id: str
    registry_bundle: ArtifactRef
    node_alias: str
    config_sha256: str
    wrapper_definition: ManagedSubWorkflowDefinition
    workflow_sha256: str
    input_sha256: str


class _ChildInputAdmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    child_run_id: str
    parent_basis_ref: ArtifactRef
    binding_ref: ArtifactRef
    workflow_ref: ArtifactRef
    state_ref: ArtifactRef
    requested_sha256: str
    admitted_sha256: str


def _digest(value: object) -> str:
    return hashlib.sha256(to_canonical_bytes(value, _CANON)).hexdigest()


def _child_id(parent_run_id: str, alias: str) -> str:
    return "child-" + _digest({"parent_run_id": parent_run_id, "alias": alias})


def _ref_payload(
    store: Any, ref: ArtifactRef, *, kind: str, schema: str, version: str | None = "1.0"
) -> Any:
    if (
        type(ref) is not ArtifactRef
        or ref.kind != kind
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
        or not store.verify(ref).ok
    ):
        raise ValueError("child_selected_artifact_not_verified")
    manifest = store.get_manifest(ref)
    if (
        manifest.kind != kind
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != schema
        or (version is not None and manifest.artifact_schema.version != version)
    ):
        raise ValueError("child_selected_artifact_schema_mismatch")
    return from_canonical_bytes(store.get_bytes(ref))


def _verified_state(store: Any, ref: ArtifactRef) -> ExperimentState:
    state = ExperimentState.model_validate(
        _ref_payload(
            store,
            ref,
            kind="scientist.experiment_state",
            schema="polisyos.scientist.orchestration.engine.ExperimentState",
            version=None,
        )
    )
    manifest = store.get_manifest(ref)
    if manifest.artifact_schema is None or manifest.artifact_schema.version != state.schema_version:
        raise ValueError("child_state_schema_version_mismatch")
    return state


def _binding_edges(binding: _ChildBinding) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(binding.parent_basis_ref, role="parent_basis"),
        input_ref_from_artifact_ref(binding.registry_bundle, role="registry_bundle"),
    ]


def _admission_edges(admission: _ChildInputAdmission) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(admission.parent_basis_ref, role="parent_basis"),
        input_ref_from_artifact_ref(admission.binding_ref, role="child_binding"),
        input_ref_from_artifact_ref(admission.workflow_ref, role="child_workflow"),
        input_ref_from_artifact_ref(admission.state_ref, role="admitted_state"),
    ]


def _verify_child_input(
    store: Any, manifest: core_run.RunManifest, binding: _ChildBinding, binding_ref: ArtifactRef
) -> _ChildInputAdmission:
    """Verify both the requested mapping and the actual pre-node admitted state."""
    admission_refs = [ref for ref in manifest.inputs if ref.kind == _ADMISSION_KIND]
    states = [ref for ref in manifest.inputs if ref.kind == "scientist.experiment_state"]
    if len(admission_refs) != 1 or not states:
        raise ValueError("child_input_admission_not_established")
    admission_ref = admission_refs[0]
    admission = _ChildInputAdmission.model_validate(
        _ref_payload(store, admission_ref, kind=_ADMISSION_KIND, schema=_ADMISSION_SCHEMA)
    )
    if (
        admission.child_run_id != binding.child_run_id
        or admission.parent_basis_ref != binding.parent_basis_ref
        or admission.binding_ref != binding_ref
        or admission.requested_sha256 != binding.input_sha256
        or admission.state_ref != states[0]
        or admission.workflow_ref not in manifest.inputs
        or store.get_manifest(admission_ref).inputs != _admission_edges(admission)
        or store.get_manifest(binding_ref).inputs != _binding_edges(binding)
    ):
        raise ValueError("child_input_admission_mismatch")
    initial_state = _verified_state(store, admission.state_ref)
    if (
        initial_state.run_id != binding.child_run_id
        or _digest(initial_state.model_dump(mode="json")) != admission.admitted_sha256
    ):
        raise ValueError("child_admitted_state_mismatch")
    admitted_workflow = WorkflowSpec.model_validate(
        _ref_payload(
            store,
            admission.workflow_ref,
            kind="scientist.workflow_spec",
            schema="polisyos.scientist.orchestration.engine.WorkflowSpec",
        )
    )
    if _digest(admitted_workflow.model_dump(mode="json")) != binding.workflow_sha256:
        raise ValueError("child_admitted_workflow_mismatch")
    return admission


def _active_parent(parent: core_run.RunContext, binding: Any, alias: str) -> None:
    """Reconcile the real parent owner and its still-pending engine attempt."""
    if type(parent) is not core_run.RunContext or binding is None:
        raise ValueError("child_parent_owner_missing")
    parent._require_active_lease_owner()
    tail = parent._runtime_invocation_tail_ref
    parent._validate_run_owner_binding()
    attempts = parent.read_runtime_invocation_attempts()
    matching = [
        item
        for item in attempts
        if item.basis_ref == binding.basis_ref
        and item.basis.attempt_id == binding.attempt_id
        and item.basis.node_alias == alias
        and item.basis.run_id == binding.run_id
        and item.outcome is None
    ]
    with parent._parent_state_transition_lease(run_scoped=False):
        parent._require_worker_receipt_reconciled()
        if (
            len(matching) != 1
            or binding.run_id != parent.run_manifest.run_id
            or parent._closed
            or parent._suspended
            or parent._active_lease is None
            or parent._runtime_invocation_tail_ref != tail
        ):
            raise ValueError("child_parent_attempt_not_active")


def _terminal_child_binding(
    *,
    parent: core_run.RunContext,
    child_id: str,
    run_dir: Path,
) -> tuple[core_run.TerminalRunRead, _ChildBinding, ArtifactRef]:
    """Read the selected child binding before any recovered mapping executes."""
    terminal_run = core_run.read_terminal_run(
        parent.store, run_dir, run_id=child_id, access_scope=parent.access_scope
    )
    run_manifest = terminal_run.run_manifest
    snapshot = terminal_run.owner_snapshot
    if (
        snapshot.run_manifest.parent_run_id != parent.run_manifest.run_id
        or snapshot.run_manifest.registry_bundle != parent.run_manifest.registry_bundle
    ):
        raise ValueError("child_owner_binding_mismatch")
    if (
        run_manifest.run_id != child_id
        or run_manifest.parent_run_id != parent.run_manifest.run_id
        or run_manifest.registry_bundle != parent.run_manifest.registry_bundle
        or (run_manifest.tenant_id, run_manifest.cell_id) != (parent.tenant_id, parent.cell_id)
    ):
        raise ValueError("child_manifest_binding_mismatch")
    bindings = [ref for ref in run_manifest.inputs if ref.kind == _BINDING_KIND]
    if len(bindings) != 1:
        raise ValueError("child_binding_not_established")
    actual = _ChildBinding.model_validate(
        _ref_payload(
            parent.store,
            bindings[0],
            kind=_BINDING_KIND,
            schema=_BINDING_SCHEMA,
            version=_BINDING_VERSION,
        )
    )
    return terminal_run, actual, bindings[0]


def _recover_terminal(
    *,
    parent: core_run.RunContext,
    child_id: str,
    run_dir: Path,
    expected: _ChildBinding,
    workflow: WorkflowSpec,
    terminal_binding: tuple[core_run.TerminalRunRead, _ChildBinding, ArtifactRef] | None = None,
) -> WorkflowExecutionResult:
    """Fresh-read an exact terminal child; an incomplete child remains unknown."""
    from polisyos.scientist.orchestration.engine.executor import (
        WorkflowExecutionResult,
        WorkflowReport,
    )

    terminal_run, actual, binding_ref = terminal_binding or _terminal_child_binding(
        parent=parent, child_id=child_id, run_dir=run_dir
    )
    run_manifest = terminal_run.run_manifest
    run_ref = terminal_run.run_ref
    if (
        actual.model_copy(update={"parent_basis_ref": expected.parent_basis_ref}) != expected
        or actual.parent_basis_ref not in run_manifest.inputs
    ):
        raise ValueError("child_binding_changed")
    input_admission = _verify_child_input(parent.store, run_manifest, actual, binding_ref)
    parent_attempts = parent.read_runtime_invocation_attempts()
    if not any(
        item.basis_ref == actual.parent_basis_ref
        and item.basis.run_id == expected.parent_run_id
        and item.basis.node_alias == expected.parent_alias
        for item in parent_attempts
    ):
        raise ValueError("child_original_attempt_not_established")
    if len(terminal_run.terminal_inputs) != 1:
        raise ValueError("child_terminal_transition_not_established")
    final_ref = terminal_run.terminal_inputs[0]
    if final_ref not in run_manifest.outputs:
        raise ValueError("child_terminal_transition_not_owner_linked")
    finalization = WorkflowStateFinalization.model_validate(
        _ref_payload(
            parent.store,
            final_ref,
            kind=FINALIZATION_KIND,
            schema=FINALIZATION_SCHEMA_NAME,
        )
    )
    report_refs = [
        item.artifact_ref
        for item in finalization.output_bindings
        if item.state_path == FINAL_WORKFLOW_REPORT_STATE_PATH
    ]
    if (
        finalization.run_id != child_id
        or finalization.workflow_id != workflow.workflow_id
        or finalization.workflow_spec_ref != input_admission.workflow_ref
        or finalization.workflow_spec_ref not in run_manifest.inputs
        or finalization.final_state_ref not in run_manifest.outputs
        or len(report_refs) != 1
        or report_refs[0] not in run_manifest.outputs
    ):
        raise ValueError("child_terminal_transition_mismatch")
    selected_workflow = WorkflowSpec.model_validate(
        _ref_payload(
            parent.store,
            finalization.workflow_spec_ref,
            kind="scientist.workflow_spec",
            schema="polisyos.scientist.orchestration.engine.WorkflowSpec",
        )
    )
    if selected_workflow != workflow:
        raise ValueError("child_workflow_changed")
    state = _verified_state(parent.store, finalization.final_state_ref)
    report = WorkflowReport.model_validate(
        _ref_payload(
            parent.store,
            report_refs[0],
            kind="scientist.workflow_report",
            schema="polisyos.scientist.orchestration.engine.WorkflowReport",
        )
    )
    if (
        state.run_id != child_id
        or state.reports_index.get("workflow_report") != report_refs[0]
        or report.run_id != child_id
        or report.workflow_id != workflow.workflow_id
        or report.status != run_manifest.status
    ):
        raise ValueError("child_terminal_result_mismatch")
    return WorkflowExecutionResult(state=state, report=report, run_ref=run_ref)


class _ManagedSubWorkflowDispatch:
    """Give only the registered SubWorkflow implementation a child executor."""

    def __init__(
        self,
        node: SubWorkflowNode,
        parent_context: ExecutionContext,
        *,
        alias: str,
        timeout_s: float | None,
        recover_only: bool = False,
    ) -> None:
        self._node = node
        self._parent_context = parent_context
        self._alias = alias
        self._timeout_s = timeout_s
        self._recover_only = recover_only
        self._config = node._config.model_copy(deep=True)
        self._registry = node._registry
        self._node_alias = node._alias

    @property
    def spec(self) -> Any:
        return self._node.spec

    def _unsupported_reason(self, state: ExperimentState) -> str | None:
        from polisyos.scientist.orchestration.engine.registry import NodeRegistry

        parent = self._parent_context.run
        if self._timeout_s is not None:
            return "timeout_worker_not_supported"
        if type(parent) is not core_run.RunContext or parent.trace_path is None:
            return "parent_owner_not_established"
        if parent.run_manifest.control_job_id is not None:
            return "control_job_fence_not_established"
        if (
            parent.tenant_id is not None or parent.cell_id is not None
        ) and parent.access_scope is None:
            return "access_scope_not_established"
        if state.budgets:
            return "child_budget_settlement_not_established"
        if parent.run_manifest.registry_bundle.manifest_profile_sha256 is None:
            return "registry_profile_not_established"
        if (
            type(self._registry) is not NodeRegistry
            or self._node._registry is not self._registry
            or self._node._config != self._config
            or self._node._alias != self._node_alias
        ):
            return "selected_configuration_changed"
        return None

    @staticmethod
    def _refused(state: ExperimentState, reason: str) -> NodeOutcome:
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(code=f"sub_workflow.{reason}", message=reason),
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        from polisyos.scientist.orchestration.engine.registry import NodeRegistry
        from polisyos.scientist.orchestration.engine.sub_workflow import SubWorkflowNode

        parent = self._parent_context.run
        reason = self._unsupported_reason(state)
        if reason is not None:
            return self._refused(state, reason)
        if state.run_id != parent.run_manifest.run_id:
            raise ValueError("child_parent_state_run_mismatch")
        attempt = ctx._engine_invocation
        _active_parent(parent, attempt, self._alias)

        # Hold the selected registration set before exposing the child callback.
        # The snapshot preserves node objects, not an arbitrary-code sandbox.
        selected_registry = NodeRegistry()
        selected_ids: set[str] = set()
        if not self._recover_only:
            for invocation in self._config.workflow.nodes:
                component_id = str(invocation.node_id)
                if component_id not in selected_ids:
                    selected_registry.register(self._registry.get(invocation.node_id))
                    selected_ids.add(component_id)
        selected_node = SubWorkflowNode(
            self._config.model_copy(deep=True), selected_registry, alias=self._node_alias
        )
        selected_workflow = self._config.workflow
        if self._config.error_policy_override is not None:
            selected_workflow = selected_workflow.model_copy(
                update={"error_policy": self._config.error_policy_override}
            )

        def execute_child(
            workflow: WorkflowSpec,
            child_state: ExperimentState,
            registry: NodeRegistry,
            node_alias: str,
        ) -> WorkflowExecutionResult:
            if (
                registry is not selected_registry
                or node_alias != self._node_alias
                or workflow != selected_workflow
            ):
                raise ValueError("child_selected_workflow_changed")
            return self._run_child(
                parent, attempt, workflow, child_state, registry, ctx, selected_node
            )

        return SubWorkflowNode._execute_admitted(selected_node, ctx, state, execute_child)

    async def execute_managed_async(
        self, ctx: ExecutionContext, state: ExperimentState
    ) -> NodeOutcome:
        """Keep the parent lease until the actual local child worker has stopped."""
        from polisyos.common import async_tools

        reason = self._unsupported_reason(state)
        if reason is not None:
            return self._refused(state, reason)
        if async_tools.is_current_shared_executor_worker():
            return self._refused(state, "async_reentrant_worker_not_supported")

        parent = self._parent_context.run
        release_pin = parent._pin_active_execution()
        admission_gate = Event()
        admitted = False

        def outcome_unknown(reason: str) -> ChildWorkflowOutcomeUnknownError:
            child_id = _child_id(parent.run_manifest.run_id, self._alias)
            assert parent.trace_path is not None
            return ChildWorkflowOutcomeUnknownError(
                run_id=child_id,
                run_dir=parent.trace_path.parent / "children" / child_id,
                reason=reason,
            )

        def run_child() -> tuple[NodeOutcome | None, BaseException | None]:
            try:
                if (
                    not admission_gate.is_set()
                    and not async_tools.is_current_shared_executor_worker()
                ):
                    # The shared helper may invoke inline in an owner callback
                    # slot. Waiting for submit to return would deadlock there.
                    return self._refused(state, "async_reentrant_worker_not_supported"), None
                admission_gate.wait()
                if not admitted:
                    return None, None
                try:
                    return self.execute(ctx, state), None
                except BaseException as exc:
                    return None, exc.with_traceback(None)
            finally:
                release_pin()

        try:
            handle = async_tools.submit_shared_executor_cancellable(run_child)
        except BaseException as exc:
            # The executor may have enqueued before failing to start a thread.
            # The closed gate makes that queued body a no-op even after release.
            admission_gate.set()
            try:
                release_pin()
            except BaseException as cleanup:
                exc.add_note(f"child_execution_pin_release_failed: {cleanup!r}")
            raise
        try:
            admitted = True
        finally:
            admission_gate.set()
        try:
            completion = await handle.result_async()
        except asyncio.CancelledError as exc:
            try:
                if handle.cancel():
                    release_pin()
            except BaseException as cleanup:
                exc.add_note(f"child_execution_pin_release_failed: {cleanup!r}")
            raise
        except BaseException as exc:
            if handle.done():
                try:
                    release_pin()
                except BaseException as cleanup:
                    exc.add_note(f"child_execution_pin_release_failed: {cleanup!r}")
            if isinstance(exc, Exception):
                raise outcome_unknown("child_async_completion_unknown") from exc
            exc.add_note("child_async_completion_unknown")
            raise
        # A terminal handle means its body has returned, or never entered.
        # This also closes the pin if the executor wrapper failed before body.
        try:
            release_pin()
        except Exception as exc:
            raise outcome_unknown("child_execution_pin_release_unknown") from exc
        except BaseException as exc:
            exc.add_note("child_execution_pin_release_unknown")
            raise
        if completion.status != "completed" or completion.value is None:
            raise outcome_unknown("child_async_worker_outcome_unknown")
        outcome, error = completion.value
        if error is not None:
            raise error
        if not isinstance(outcome, NodeOutcome):
            raise outcome_unknown("child_async_worker_outcome_unknown")
        return outcome

    def preflight_terminal_recovery(
        self,
        state: ExperimentState,
        *,
        original_basis_ref: ArtifactRef,
        original_state: ExperimentState,
    ) -> None:
        """Reconcile an existing terminal child without starting a new attempt."""
        from polisyos.scientist.orchestration.engine.state_branching import branch_state
        from polisyos.scientist.orchestration.engine.sub_workflow import SubWorkflowNode

        parent = self._parent_context.run
        reason = self._unsupported_reason(state)
        if reason is not None:
            raise ValueError(f"child_recovery_{reason}")
        parent._require_active_lease_owner()
        parent._validate_run_owner_binding()
        tail = parent._runtime_invocation_tail_ref
        if state.run_id != parent.run_manifest.run_id:
            raise ValueError("child_parent_state_run_mismatch")
        child_id = _child_id(parent.run_manifest.run_id, self._alias)
        assert parent.trace_path is not None
        run_dir = parent.trace_path.parent / "children" / child_id
        try:
            terminal_binding = _terminal_child_binding(
                parent=parent, child_id=child_id, run_dir=run_dir
            )
            actual = terminal_binding[1]
            if (
                actual.parent_basis_ref != original_basis_ref
                or actual.parent_alias != self._alias
                or actual.node_alias != self._node_alias
                or actual.wrapper_definition != capture_managed_subworkflow_definition(self._node)
                or actual.config_sha256 != _digest(self._config.model_dump(mode="json"))
            ):
                raise ValueError("child_original_binding_changed")
            current_state = branch_state(
                state,
                write_paths=getattr(self._node.spec, "state_writes", ()),
                enforce_write_scope=True,
            ).state
            if to_canonical_bytes(original_state.model_dump(), _CANON) != to_canonical_bytes(
                current_state.model_dump(), _CANON
            ):
                raise ValueError("child_original_input_changed")
            workflow, child_state = SubWorkflowNode._prepare_child_input(self._node, current_state)
            child_state = child_state.model_copy(update={"run_id": child_id}, deep=True)
            expected = _ChildBinding(
                parent_run_id=parent.run_manifest.run_id,
                parent_alias=self._alias,
                parent_basis_ref=original_basis_ref,
                child_run_id=child_id,
                registry_bundle=parent.run_manifest.registry_bundle,
                node_alias=self._node_alias,
                config_sha256=_digest(self._config.model_dump(mode="json")),
                wrapper_definition=actual.wrapper_definition,
                workflow_sha256=_digest(workflow.model_dump(mode="json")),
                input_sha256=_digest(child_state.model_dump(mode="json")),
            )
            _recover_terminal(
                parent=parent,
                child_id=child_id,
                run_dir=run_dir,
                expected=expected,
                workflow=workflow,
                terminal_binding=terminal_binding,
            )
            with parent._parent_state_transition_lease(run_scoped=False):
                parent._require_active_lease_owner()
                parent._require_worker_receipt_reconciled()
                if (
                    parent._closed
                    or parent._suspended
                    or parent._active_lease is None
                    or parent._runtime_invocation_tail_ref != tail
                ):
                    raise ValueError("child_parent_attempt_not_active")
        except Exception as exc:
            raise ChildWorkflowOutcomeUnknownError(
                run_id=child_id, run_dir=run_dir, reason="child_recovery_not_established"
            ) from exc

    def _run_child(
        self,
        parent: core_run.RunContext,
        attempt: Any,
        workflow: WorkflowSpec,
        child_state: ExperimentState,
        registry: NodeRegistry,
        node_context: ExecutionContext,
        selected_node: SubWorkflowNode,
    ) -> WorkflowExecutionResult:
        from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor

        child_id = _child_id(parent.run_manifest.run_id, self._alias)
        assert parent.trace_path is not None
        children = parent.trace_path.parent / "children"
        if children.is_symlink():
            raise ValueError("child_run_directory_symlink")
        children.mkdir(exist_ok=True)
        run_dir = children / child_id
        child_state = child_state.model_copy(update={"run_id": child_id}, deep=True)
        expected = _ChildBinding(
            parent_run_id=parent.run_manifest.run_id,
            parent_alias=self._alias,
            parent_basis_ref=attempt.basis_ref,
            child_run_id=child_id,
            registry_bundle=parent.run_manifest.registry_bundle,
            node_alias=self._node_alias,
            config_sha256=_digest(self._config.model_dump(mode="json")),
            wrapper_definition=capture_managed_subworkflow_definition(selected_node),
            workflow_sha256=_digest(workflow.model_dump(mode="json")),
            input_sha256=_digest(child_state.model_dump(mode="json")),
        )
        _active_parent(parent, attempt, self._alias)
        if os.path.lexists(run_dir):
            try:
                result = _recover_terminal(
                    parent=parent,
                    child_id=child_id,
                    run_dir=run_dir,
                    expected=expected,
                    workflow=workflow,
                )
                _active_parent(parent, attempt, self._alias)
                return result
            except Exception as exc:
                raise ChildWorkflowOutcomeUnknownError(
                    run_id=child_id, run_dir=run_dir, reason="child_recovery_not_established"
                ) from exc
        if self._recover_only:
            raise ChildWorkflowOutcomeUnknownError(
                run_id=child_id, run_dir=run_dir, reason="child_recovery_not_established"
            )
        child = core_run.RunContext.start_child(
            parent,
            store=parent.store,
            parent_basis_ref=attempt.basis_ref,
            run_id=child_id,
            run_dir=run_dir,
        )
        try:
            binding_ref = node_context.store.put_json(
                expected.model_dump(mode="json"),
                ArtifactWriteOptions(
                    kind=_BINDING_KIND,
                    media_type="application/json",
                    schema=SchemaInfo(name=_BINDING_SCHEMA, version=_BINDING_VERSION),
                    inputs=_binding_edges(expected),
                    tenant_context=child.artifact_tenant_context(),
                ),
                canon_spec=_CANON,
                return_selected_profile=True,
            )
            if _ChildBinding.model_validate(
                _ref_payload(
                    parent.store,
                    binding_ref,
                    kind=_BINDING_KIND,
                    schema=_BINDING_SCHEMA,
                    version=_BINDING_VERSION,
                )
            ) != expected or parent.store.get_manifest(binding_ref).inputs != _binding_edges(
                expected
            ):
                raise ValueError("child_binding_write_not_reconciled")
            child.add_input(binding_ref)
            _active_parent(parent, attempt, self._alias)
            child_context = replace(
                node_context,
                run=child,
                depth=node_context.depth + 1,
                logger=logging.getLogger(f"{node_context.logger.name}.child"),
                _engine_invocation=None,
            )

            def admit_child_input(workflow_ref: ArtifactRef, state_ref: ArtifactRef) -> None:
                _active_parent(parent, attempt, self._alias)
                admitted_state = _verified_state(parent.store, state_ref)
                admitted_workflow = WorkflowSpec.model_validate(
                    _ref_payload(
                        parent.store,
                        workflow_ref,
                        kind="scientist.workflow_spec",
                        schema="polisyos.scientist.orchestration.engine.WorkflowSpec",
                    )
                )
                if (
                    admitted_state.run_id != child_id
                    or _digest(admitted_workflow.model_dump(mode="json"))
                    != expected.workflow_sha256
                ):
                    raise ValueError("child_admission_input_mismatch")
                admission = _ChildInputAdmission(
                    child_run_id=child_id,
                    parent_basis_ref=attempt.basis_ref,
                    binding_ref=binding_ref,
                    workflow_ref=workflow_ref,
                    state_ref=state_ref,
                    requested_sha256=expected.input_sha256,
                    admitted_sha256=_digest(admitted_state.model_dump(mode="json")),
                )
                admission_ref = node_context.store.put_json(
                    admission.model_dump(mode="json"),
                    ArtifactWriteOptions(
                        kind=_ADMISSION_KIND,
                        media_type="application/json",
                        schema=SchemaInfo(name=_ADMISSION_SCHEMA, version="1.0"),
                        inputs=_admission_edges(admission),
                        tenant_context=child.artifact_tenant_context(),
                    ),
                    canon_spec=_CANON,
                    return_selected_profile=True,
                )
                if _ChildInputAdmission.model_validate(
                    _ref_payload(
                        parent.store,
                        admission_ref,
                        kind=_ADMISSION_KIND,
                        schema=_ADMISSION_SCHEMA,
                    )
                ) != admission or parent.store.get_manifest(
                    admission_ref
                ).inputs != _admission_edges(admission):
                    raise ValueError("child_admission_write_not_reconciled")
                child.add_input(admission_ref)
                _active_parent(parent, attempt, self._alias)

            result = WorkflowExecutor(
                child_context, registry, _child_input_hook=admit_child_input
            ).execute(workflow, child_state)
            recovered = _recover_terminal(
                parent=parent,
                child_id=child_id,
                run_dir=run_dir,
                expected=expected,
                workflow=workflow,
            )
            if recovered.run_ref != result.run_ref:
                raise ValueError("child_terminal_result_changed")
            _active_parent(parent, attempt, self._alias)
            return recovered
        except Exception as exc:
            try:
                child.suspend_for_resume()
            except BaseException as cleanup:
                exc.add_note(f"child_suspend_failed: {cleanup!r}")
            if isinstance(exc, core_run.ChildOutcomeUnknownError):
                exc.add_note(
                    f"enclosing_child_outcome_unknown: run_id={child_id}, run_dir={run_dir}"
                )
                raise
            raise ChildWorkflowOutcomeUnknownError(
                run_id=child_id, run_dir=run_dir, reason="child_execution_outcome_unknown"
            ) from exc
        except BaseException as exc:
            exc.add_note(f"child_outcome_unknown: run_id={child_id}, run_dir={run_dir}")
            try:
                child.suspend_for_resume()
            except BaseException as cleanup:
                exc.add_note(f"child_suspend_failed: {cleanup!r}")
            raise
