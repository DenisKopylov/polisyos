"""Private engine machinery for a trusted, locally admitted child workflow.

A registered workflow or request is never an admission. Only the appointed
engine owner may construct this machinery after a live parent attempt and its
composition policy have been reconciled. It does not sandbox arbitrary Python.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import math
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import uuid4

from pydantic import BaseModel

from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
from polisyos.common.job_execution_interrupt import raise_if_job_execution_interrupted
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.run.child_custody import ChildComputationBinding
from polisyos.scientist.orchestration.engine.component_identity import (
    _capture_configured_component_owner,
    capture_engine_component_identity,
    matches_engine_component_identity,
)
from polisyos.scientist.orchestration.engine.context import (
    ExecutionContext,
    _EngineInvocationBinding,
    _load_engine_owned_invocation_input_state,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.core.run.child_custody import (
        ChildComputationCustody,
        ChildStagingScope,
        PrivateChildHandoff,
    )
    from polisyos.core.run.manifest import RunInvocationImplementationIdentity
    from polisyos.scientist.orchestration.engine.component_identity import (
        _ConfiguredComponentIdentityOwner,
    )
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.sub_workflow import SubWorkflowConfig


def _finite_json(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _require_finite_data(value: object) -> None:
    """Reject opaque, cyclic, nonfinite or unreasonably deep child values."""
    active: set[int] = set()

    def visit(item: object, depth: int) -> None:
        if depth > 64:
            raise ValueError("child_input_depth_exceeded")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ValueError("child_input_nonfinite")
            return
        if type(item) is Decimal:
            if not item.is_finite():
                raise ValueError("child_input_nonfinite")
            return
        if type(item) not in (list, dict):
            raise ValueError("child_input_not_finite_data")
        ident = id(item)
        if ident in active:
            raise ValueError("child_input_cycle")
        active.add(ident)
        try:
            if type(item) is list:
                for child in item:
                    visit(child, depth + 1)
            else:
                for key, child in item.items():
                    if type(key) is not str:
                        raise ValueError("child_input_mapping_key_invalid")
                    visit(child, depth + 1)
        finally:
            active.remove(ident)

    visit(value, 0)


def _state_copy(state: ExperimentState, *, run_id: str) -> ExperimentState:
    _require_finite_data(state.params)
    _require_finite_data(state.causal_method_params)
    payload = state.model_dump(mode="json")
    payload["run_id"] = run_id
    # A previous workflow checkpoint is not a child input or a child recovery grant.
    payload["last_checkpoint_ref"] = None
    return ExperimentState.model_validate_json(_finite_json(payload))


def _resolve_present(state: ExperimentState, path: str) -> tuple[bool, object]:
    """Preserve the difference between an absent key and a present null."""
    current: object = state
    for part in path.split("."):
        if isinstance(current, BaseModel):
            if part not in type(current).model_fields:
                return False, None
            current = getattr(current, part)
        elif isinstance(current, dict):
            if part not in current:
                return False, None
            current = current[part]
        else:
            return False, None
    return True, current


def _selected_state_refs(state: ExperimentState) -> tuple[ArtifactRef, ...]:
    """Select typed state fields, never interpret arbitrary params as authority."""
    refs: list[ArtifactRef] = []
    for value in (state.inputs, state.artifacts_index, state.reports_index):
        refs.extend(value.values())
    for name in type(state).model_fields:
        value = getattr(state, name)
        if isinstance(value, ArtifactRef):
            refs.append(value)
    if any(ref.manifest_profile_sha256 is None for ref in refs):
        raise ValueError("child_input_selected_profile_required")
    return tuple(refs)


def _ref_key(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    return (str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256)


@dataclass(frozen=True)
class _MemberAtBootstrap:
    """Hold trusted bootstrap registration and descriptors before any bind/work."""

    registered: object
    expected_type: type[object]
    execute_descriptor: object
    execute_code: object
    bind_descriptor: object
    bind_code: object
    spec_descriptor: object
    spec_accessor_code: object

    @classmethod
    def capture(cls, registered: object, expected_type: type[object]) -> _MemberAtBootstrap:
        if type(registered) is not expected_type:
            raise ValueError("child_bootstrap_registered_type_mismatch")
        execute = inspect.getattr_static(expected_type, "execute", None)
        bind = inspect.getattr_static(expected_type, "bind", None)
        spec = inspect.getattr_static(expected_type, "spec", None)
        if (
            not inspect.isfunction(execute)
            or not isinstance(spec, property)
            or not inspect.isfunction(spec.fget)
        ):
            raise ValueError("child_bootstrap_implementation_unavailable")
        if bind is not None and not inspect.isfunction(bind):
            raise ValueError("child_bootstrap_bind_unavailable")
        return cls(
            registered,
            expected_type,
            execute,
            execute.__code__,
            bind,
            bind.__code__ if bind is not None else None,
            spec,
            spec.fget.__code__,
        )

    def require_unchanged(self) -> None:
        typ = self.expected_type
        execute = inspect.getattr_static(typ, "execute", None)
        bind = inspect.getattr_static(typ, "bind", None)
        if (
            type(self.registered) is not typ
            or execute is not self.execute_descriptor
            or getattr(execute, "__code__", None) is not self.execute_code
            or bind is not self.bind_descriptor
            or (getattr(bind, "__code__", None) if bind is not None else None) is not self.bind_code
            or inspect.getattr_static(typ, "spec", None) is not self.spec_descriptor
            or getattr(getattr(self.spec_descriptor, "fget", None), "__code__", None)
            is not self.spec_accessor_code
        ):
            raise ValueError("child_bootstrap_implementation_changed")


class _AdmittedChildDispatch:
    """Keep the actual bound method; registry lookup cannot substitute it."""

    def __init__(
        self,
        owner: _ConfiguredComponentIdentityOwner,
        params: dict[str, Any],
        grant: _BorrowedExecutionGrant,
        *,
        fence: Any | None = None,
        scope: ChildStagingScope | None = None,
    ) -> None:
        self._owner = owner
        self._grant = grant
        self._fence = fence
        self._scope = scope
        self._params = _finite_json(params)
        self._spec = owner.bound_node.spec.model_copy(deep=True)

    @property
    def spec(self) -> NodeSpec:
        return self._spec.model_copy(deep=True)

    def bind(self, params: dict[str, Any]) -> _AdmittedChildDispatch:
        if _finite_json(params) != self._params:
            raise ValueError("child_dispatch_params_changed")
        return self

    def implementation_identity(self) -> RunInvocationImplementationIdentity:
        return self._owner.reconcile(
            self._owner.registered_node, self._owner.bound_node, json.loads(self._params)
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        # This is a short owner decision; producer code runs outside the lock.
        if self._fence is None:
            raise ValueError("child_control_dispatch_owner_not_appointed")
        if self._scope is None:
            self._fence.admit_producer()
        else:
            if ctx.store is not self._scope.store:
                raise ValueError("child_dispatch_scope_store_mismatch")
            self._fence.admit_producer(self._scope)
        if ctx.foundry is not None:
            from polisyos.scientist.orchestration.engine.child_foundry import (
                _CHILD_FOUNDRY_DISPATCH_TOKEN,
                _COMPILE_NODE,
                _EXECUTE_NODE,
                _ScopedChildFoundryPort,
            )

            if type(ctx.foundry) is not _ScopedChildFoundryPort:
                raise ValueError("child_foundry_port_not_appointed")
            node_id = str(self._spec.metadata.component_id)
            if node_id in {
                _COMPILE_NODE,
                _EXECUTE_NODE,
            }:
                from polisyos.scientist.nodes.builtins.compile.compile_foundry import (
                    CompileFoundryNode,
                )
                from polisyos.scientist.nodes.builtins.simulate.run_simulation import (
                    RunSimulationNode,
                )

                builtin = CompileFoundryNode if node_id == _COMPILE_NODE else RunSimulationNode
                if (
                    type(self._owner.registered_node) is not builtin
                    or type(self._owner.bound_node) is not builtin
                    or self._owner.implementation.node_type is not builtin
                ):
                    raise ValueError("child_foundry_builtin_owner_not_established")
                with ctx.foundry._producer_scope(node_id, _token=_CHILD_FOUNDRY_DISPATCH_TOKEN):
                    return self._owner.execute(ctx, state)
        return self._owner.execute(ctx, state)


class _AdmittedSourceSelections:
    """Selections recovered from the actual parent basis, not a candidate or manifest."""

    __slots__ = ("__selected",)

    def __init__(self, basis_state: ExperimentState) -> None:
        role_inputs = {
            "model_primary_data_snapshot": "data_snapshot_ref",
            "model_primary_registry": "registry_bundle_ref",
        }
        selected: dict[str, ArtifactRef] = {}
        for role, key in role_inputs.items():
            ref = basis_state.inputs.get(key)
            if ref is not None:
                if type(ref) is not ArtifactRef or ref.manifest_profile_sha256 is None:
                    raise ValueError("child_source_selection_profile_missing")
                selected[role] = ref.model_copy(deep=True)
        self.__selected = selected

    def selected_source_ref(self, role: str) -> ArtifactRef:
        """Return a detached exact ref only for a basis-established supported role."""
        ref = self.__selected.get(role)
        if ref is None:
            raise ValueError("child_source_role_not_established")
        return ref.model_copy(deep=True)


_PARENT_SEAL_TOKEN = object()


class _ParentAttemptSeal:
    """Engine-held result of reconciling the actual pending parent invocation."""

    __slots__ = ("binding", "dispatch", "grant", "input_state_json", "root", "selections")
    input_state_json: bytes

    def __init__(
        self,
        root: Any,
        binding: ChildComputationBinding,
        dispatch: _AdmittedChildDispatch,
        grant: _BorrowedExecutionGrant,
        input_state_json: bytes,
        selections: _AdmittedSourceSelections,
        *,
        token: object,
    ) -> None:
        if token is not _PARENT_SEAL_TOKEN:
            raise TypeError("child_parent_seal_engine_only")
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "binding", binding.model_copy(deep=True))
        object.__setattr__(self, "dispatch", dispatch)
        object.__setattr__(self, "grant", grant)
        object.__setattr__(self, "input_state_json", input_state_json)
        object.__setattr__(self, "selections", selections)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("child_parent_seal_immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("child_parent_seal_immutable")


class _ResourceParentFields(TypedDict):
    run_id: str
    job_id: str | None
    attempt_id: str
    basis_ref: str


def _resource_parent_fields(binding: ChildComputationBinding) -> _ResourceParentFields:
    return {
        "run_id": binding.root_run_id,
        "job_id": binding.control_job_id,
        "attempt_id": binding.parent_attempt_id,
        "basis_ref": json.dumps(
            binding.parent_basis_ref.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ),
    }


def _hold_admitted_parent_dispatch(
    root: Any,
    binding: ChildComputationBinding,
    registered_node: object,
    selected_node: object,
    params: dict[str, Any],
    grant: _BorrowedExecutionGrant,
    input_state: ExperimentState,
) -> _ParentAttemptSeal:
    """Reconcile the real pending attempt before holding its actual method.

    This validates an existing attempt, not an issuer or a grant. The engine
    must use the returned held dispatcher for the parent invocation and appoint
    a separate composition owner before any child is admitted.
    """
    from polisyos.core.run.context import RunContext

    parent_id = "scientist.node_run_hierarchical_policy_search@1.0.0"
    if type(root) is not RunContext or params or type(grant) is not _BorrowedExecutionGrant:
        raise ValueError("child_parent_execution_profile_unsupported")
    if (
        binding.control_job_id is None
        or binding.tenant_id is None
        or binding.cell_id is None
        or (
            root.run_manifest.control_job_id,
            root.run_manifest.tenant_id,
            root.run_manifest.cell_id,
        )
        != (binding.control_job_id, binding.tenant_id, binding.cell_id)
    ):
        raise ValueError("child_parent_job_scope_not_established")
    grant.check_current()
    if root.run_manifest.run_id != binding.root_run_id:
        raise ValueError("child_parent_root_mismatch")
    root._require_active_lease_owner()
    root._validate_run_owner_binding()
    matches = [
        item
        for item in root.read_runtime_invocation_attempts()
        if item.basis_ref == binding.parent_basis_ref
        and item.basis.attempt_id == binding.parent_attempt_id
        and item.outcome is None
    ]
    if len(matches) != 1 or matches[0].basis.component_id != parent_id:
        raise ValueError("child_parent_attempt_not_current")
    source_ctx = ExecutionContext(
        store=root.store,
        run=root,
        logger=logging.getLogger("polisyos.scientist.engine.child_admission"),
        _engine_invocation=_EngineInvocationBinding(
            run_id=binding.root_run_id,
            attempt_id=binding.parent_attempt_id,
            basis_ref=binding.parent_basis_ref,
        ),
    )
    basis_state = _load_engine_owned_invocation_input_state(source_ctx, input_state)
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    workflow = WorkflowSpec.model_validate(
        from_canonical_bytes(root.store.get_bytes(matches[0].basis.workflow_spec_ref))
    )
    invocation = next(inv for inv in workflow.nodes if inv.alias == matches[0].basis.node_alias)
    if invocation.timeout_s is not None or (
        invocation.retry is not None and invocation.retry.max_retries != 0
    ):
        raise ValueError("child_parent_retry_or_timeout_route_unsupported")
    canon = CanonSpec(forbid_floats=False)
    if basis_state is None or to_canonical_bytes(
        basis_state.model_dump(), canon
    ) != to_canonical_bytes(input_state.model_dump(), canon):
        raise ValueError("child_parent_input_state_changed")
    identity = capture_engine_component_identity(selected_node, parent_id, params)
    if (
        identity is None
        or matches[0].basis.implementation_identity != identity
        or not matches_engine_component_identity(identity, parent_id, params)
    ):
        raise ValueError("child_parent_implementation_not_established")
    owner = _capture_configured_component_owner(registered_node, params)
    if owner.bound_node is not selected_node:
        raise ValueError("child_parent_selected_registration_changed")
    if owner.reconcile(registered_node, selected_node, params) != identity:
        raise ValueError("child_parent_held_dispatch_mismatch")
    # Only trusted engine code can reach the actual root and bind this grant;
    # the tuple was just reconciled with the persisted owner basis above.
    grant.bind_parent(**_resource_parent_fields(binding))
    return _ParentAttemptSeal(
        root,
        binding,
        _AdmittedChildDispatch(owner, params, grant),
        grant,
        _finite_json(basis_state.model_dump(mode="json")),
        _AdmittedSourceSelections(basis_state),
        token=_PARENT_SEAL_TOKEN,
    )


class _StagedParentRun:
    """Narrow parent view whose writes enter the one private custody session."""

    def __init__(self, root: Any, custody: ChildComputationCustody, store: Any) -> None:
        from polisyos.core.run.child_custody import ChildComputationCustody
        from polisyos.core.run.context import RunContext

        if (
            type(root) is not RunContext
            or type(custody) is not ChildComputationCustody
            or custody._root is not root
            or custody._parent is not store
        ):
            raise ValueError("child_parent_view_owner_mismatch")
        self.__root = root
        self.__custody = custody
        self.store = store
        self.access_scope = root.access_scope
        self.tenant_id = root.tenant_id
        self.cell_id = root.cell_id
        self.trace_path = root.trace_path
        self.__manifest = root.run_manifest.model_copy(deep=True)

    @property
    def run_manifest(self) -> Any:
        return self.__manifest.model_copy(deep=True)

    def update_manifest(self, **changes: object) -> None:
        self.__custody.stage_parent_run_update(changes)
        payload = self.__manifest.model_dump(mode="python")
        payload.update(changes)
        self.__manifest = type(self.__manifest).model_validate(payload)

    def emit(self, phase: str, event: str, **kwargs: Any) -> None:
        self.__custody.stage_parent_event(phase, event, **kwargs)

    def read_runtime_invocation_attempts(self) -> Any:
        return self.__root.read_runtime_invocation_attempts()

    def read_runtime_owner_output_refs(self) -> Any:
        return self.__root.read_runtime_owner_output_refs()

    def read_runtime_workflow_finalization_ref(self) -> Any:
        return self.__root.read_runtime_workflow_finalization_ref()

    def artifact_tenant_context(self) -> Any:
        return self.__root.artifact_tenant_context()


@dataclass(frozen=True)
class _ApprovedChildPorts:
    """Only engine-appointed ports, never caller-selected ambient context."""

    fabric: Any = None
    foundry: Any = None
    scholar: Any = None
    lex: Any = None
    eval_safety_execution_context: Any = None
    eval_safety_verifier: Any = None


_STAGE_B_SESSION_TOKEN = object()


class _ManagedStageBSession:
    """Expose the appointed candidate operation without exposing the parent grant.

    This restricted interface is for the held parent builtin. It is not a
    sandbox against reflective access to Python process internals.
    """

    __slots__ = ("__runner",)

    def __init__(self, runner: _ManagedChildRunner, *, token: object) -> None:
        if token is not _STAGE_B_SESSION_TOKEN or type(runner) is not _ManagedChildRunner:
            raise TypeError("child_stage_b_session_not_appointed")
        object.__setattr__(self, "_ManagedStageBSession__runner", runner)

    def __getattribute__(self, name: str) -> Any:
        if name == "_ManagedStageBSession__runner":
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("child Stage B session is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("child Stage B session is immutable")

    def evaluate_candidate(
        self, candidate_payload: dict[str, Any], parent_state: ExperimentState
    ) -> PrivateChildHandoff:
        """Run one candidate on the fixed, independently admitted child template."""
        runner: object = object.__getattribute__(self, "_ManagedStageBSession__runner")
        if not isinstance(runner, _ManagedChildRunner) or type(runner) is not _ManagedChildRunner:
            raise ValueError("child_stage_b_session_owner_changed")
        return runner._execute_stage_b_candidate(candidate_payload, parent_state)


class _ManagedChildRunner:
    """Run admitted children serially using normal executor and Core custody.

    Constructed only by the actual parent attempt's appointed owner. It does not
    issue its own authority: the caller must already have verified policy,
    registration, parent basis, inherited budget/deadline and approved ports.
    """

    def __init__(
        self,
        *,
        custody: ChildComputationCustody,
        parent_seal: _ParentAttemptSeal,
        config: SubWorkflowConfig,
        bootstrap_members: Mapping[str, _MemberAtBootstrap],
        allowed_inputs: Sequence[ArtifactRef],
        parent_context: ExecutionContext,
        approved_ports: _ApprovedChildPorts,
        inherited_budgets: Mapping[str, Any],
        monotonic_deadline: float,
        projection_key: str,
    ) -> None:
        if (
            type(parent_seal) is not _ParentAttemptSeal
            or custody._root is not parent_seal.root
            or custody._binding != parent_seal.binding
        ):
            raise ValueError("child_parent_seal_custody_mismatch")
        binding = parent_seal.binding
        if parent_context.depth != 0:
            raise ValueError("child_nested_composition_unsupported")
        if any(
            value is not None
            for value in (
                approved_ports.fabric,
                approved_ports.foundry,
                approved_ports.scholar,
                approved_ports.lex,
                approved_ports.eval_safety_execution_context,
                approved_ports.eval_safety_verifier,
            )
        ):
            raise ValueError("child_effect_port_owner_not_established")
        parent_seal.grant.check_current()
        if (
            monotonic_deadline <= time.monotonic()
            or monotonic_deadline > parent_seal.grant.deadline_monotonic
        ):
            raise ValueError("child_inherited_deadline_invalid")
        if config.error_policy_override is not None or config.workflow.error_policy != "fail_fast":
            raise ValueError("child_workflow_policy_invalid")
        if not projection_key:
            raise ValueError("child_projection_missing")
        frozen_config = config.model_copy(deep=True)
        frozen_workflow = frozen_config.workflow
        payload = _finite_json(
            {
                "sub_workflow": frozen_config.model_dump(mode="json"),
                "projection_key": projection_key,
            }
        )
        if binding.template_sha256 != "sha256:" + hashlib.sha256(payload).hexdigest():
            raise ValueError("child_workflow_template_mismatch")
        ids = [str(inv.node_id) for inv in frozen_workflow.nodes]
        if len(ids) != len(set(ids)) or set(ids) != set(bootstrap_members):
            raise ValueError("child_workflow_member_set_mismatch")
        if any(inv.timeout_s is not None for inv in frozen_workflow.nodes):
            raise ValueError("child_process_timeout_route_unsupported")
        self._custody = custody
        self._binding = binding.model_copy(deep=True)
        self._workflow = frozen_workflow
        self._config_bytes = _finite_json(frozen_config.model_dump(mode="json"))
        self._members = dict(bootstrap_members)
        self._allowed = {_ref_key(ref): ref.model_copy(deep=True) for ref in allowed_inputs}
        if any(ref.manifest_profile_sha256 is None for ref in allowed_inputs):
            raise ValueError("child_input_selected_profile_required")
        self._parent_context = parent_context
        self._ports = approved_ports
        self._budget_bytes = _finite_json(
            ExperimentState(run_id="budget", budgets=dict(inherited_budgets)).model_dump(
                mode="json"
            )["budgets"]
        )
        self._grant = parent_seal.grant
        self._parent_input = parent_seal.input_state_json
        self._deadline = monotonic_deadline
        self._projection_key = projection_key
        self._handoffs: list[PrivateChildHandoff] = []

    def execute_subworkflow(
        self, config: SubWorkflowConfig, parent_state: ExperimentState
    ) -> PrivateChildHandoff:
        """Execute the appointed SubWorkflow mapping inside the private child."""
        return self._execute_subworkflow(config, parent_state)

    def stage_b_session(self) -> _ManagedStageBSession:
        """Restrict the admitted runner to the canonical Stage B template."""
        self._require_stage_b_template()
        return _ManagedStageBSession(self, token=_STAGE_B_SESSION_TOKEN)

    def _require_stage_b_template(self) -> None:
        from polisyos.core.run.worker_lifecycle import (
            ChildRuntimeCapability,
            _require_fixed_runtime_child_control,
        )
        from polisyos.scientist.nodes.builtins.planning.child_stage_b import (
            _PROJECTION_KEY,
            stage_b_child_template,
        )
        from polisyos.scientist.orchestration.engine.protocol import NodeSpec

        custody = self._custody
        control = _require_fixed_runtime_child_control(custody._fence)
        ChildRuntimeCapability.for_parent(custody._root, session=custody, runtime_control=control)
        intent = custody._job_intent
        locator = custody._job_intent_locator
        verifier = custody._job_owner_appointment
        if (
            not custody._guarded_root_required
            or custody._guarded_reader_service is None
            or custody._parent is None
            or intent is None
            or locator is None
            or verifier is None
            or control._job_verifier_for_core() is not verifier
        ):
            raise ValueError("child_stage_b_runtime_session_not_appointed")
        verifier.verify_intent(locator, intent.recompute())
        ChildRuntimeCapability.for_parent(custody._root, session=custody, runtime_control=control)
        config, members = stage_b_child_template()
        if (
            self._projection_key != _PROJECTION_KEY
            or _finite_json(config.model_dump(mode="json")) != self._config_bytes
            or len(members) != len(self._members)
        ):
            raise ValueError("child_stage_b_template_not_appointed")
        for node in members:
            spec = getattr(node, "spec", None)
            if not isinstance(spec, NodeSpec):
                raise ValueError("child_stage_b_member_not_appointed")
            member = self._members.get(str(spec.metadata.component_id))
            if (
                member is None
                or member.expected_type is not type(node)
                or type(member.registered) is not type(node)
            ):
                raise ValueError("child_stage_b_member_not_appointed")
            member.require_unchanged()
        self._grant.require_parent(**_resource_parent_fields(self._binding))

    def _execute_stage_b_candidate(
        self, candidate_payload: dict[str, Any], parent_state: ExperimentState
    ) -> PrivateChildHandoff:
        from polisyos.scientist.nodes.builtins.planning.child_stage_b import (
            stage_b_child_template,
        )
        from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
            _candidate_payload_without_hash,
        )
        from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

        if type(candidate_payload) is not dict:
            raise ValueError("child_stage_b_candidate_invalid")
        _require_finite_data(candidate_payload)
        candidate = json.loads(_finite_json(candidate_payload))
        PolicyCandidateSchema.model_validate(_candidate_payload_without_hash(candidate))
        # Recheck the fixed members and parent for every dynamic evaluator call.
        self._require_stage_b_template()
        if _finite_json(parent_state.model_dump(mode="json")) != self._parent_input:
            raise ValueError("child_parent_input_state_changed")
        admitted_state = ExperimentState.model_validate_json(self._parent_input)
        config, _ = stage_b_child_template()
        return self._execute_subworkflow(config, admitted_state, candidate_payload=candidate)

    def _execute_subworkflow(
        self,
        config: SubWorkflowConfig,
        parent_state: ExperimentState,
        *,
        candidate_payload: dict[str, Any] | None = None,
    ) -> PrivateChildHandoff:
        from polisyos.scientist.orchestration.engine.sub_workflow import _write_to_state

        raise_if_job_execution_interrupted()
        self._grant.require_parent(**_resource_parent_fields(self._binding))
        if _finite_json(config.model_dump(mode="json")) != self._config_bytes:
            raise ValueError("child_subworkflow_configuration_changed")
        child_input = ExperimentState(run_id=parent_state.run_id, budgets=parent_state.budgets)
        for mapping in config.input_mappings:
            present, value = _resolve_present(parent_state, mapping.source_path)
            if not present:
                continue
            target = mapping.target_path
            if "." not in target and target in type(child_input).model_fields:
                if target in {"run_id", "schema_version", "budgets", "last_checkpoint_ref"}:
                    raise ValueError("child_input_mapping_reserved")
                setattr(child_input, target, value)
            elif (target.startswith("params.") and len(target.split(".")) >= 2) or (
                target.split(".", 1)[0] in {"inputs", "artifacts_index"}
                and len(target.split(".")) == 2
            ):
                _write_to_state(child_input, target, value)
            else:
                raise ValueError("child_input_mapping_unsupported")
        # This serializes all mapped values before running any producer; no mutable
        # parent alias is passed across the child boundary.
        child_input = _state_copy(child_input, run_id=parent_state.run_id)
        if candidate_payload is not None:
            from polisyos.scientist.nodes.builtins.planning.child_stage_b import _CANDIDATE_KEY

            if _CANDIDATE_KEY in child_input.params:
                raise ValueError("child_stage_b_candidate_input_reserved")
            child_input.params[_CANDIDATE_KEY] = candidate_payload
        return self._grant.run_child(lambda: self._run_serial(child_input))

    def _run_serial(self, child_input: ExperimentState) -> PrivateChildHandoff:
        raise_if_job_execution_interrupted()
        if time.monotonic() >= self._deadline:
            raise ValueError("child_inherited_deadline_expired")
        if _finite_json(child_input.model_dump(mode="json")["budgets"]) != self._budget_bytes:
            raise ValueError("child_inherited_budget_mismatch")
        requested = _selected_state_refs(child_input)
        if any(_ref_key(ref) not in self._allowed for ref in requested):
            raise ValueError("child_input_reference_not_admitted")
        # Descriptor-only comparison performs no binder, producer or I/O work.
        for inv in self._workflow.nodes:
            self._members[str(inv.node_id)].require_unchanged()
        binding = self._binding.model_copy(update={"child_invocation_id": uuid4().hex})
        prepared = self._custody.prepare_scope(binding, input_refs=requested)
        try:
            scope = self._custody._fence.admit_prepared_scope(prepared)
        except BaseException as trigger:
            try:
                prepared.abandon()
            except BaseException as abandon_error:
                from polisyos.core.run.child_custody import ChildComputationOutcomeUnknown

                if isinstance(trigger, ChildComputationOutcomeUnknown):
                    trigger.add_note(
                        "Prepared scope abandonment also failed: " + type(abandon_error).__name__
                    )
                    raise trigger
                raise abandon_error from trigger
            raise
        try:
            # Actual bind follows Core's parent-attempt admission, never before it.
            registry = NodeRegistry()
            for inv in self._workflow.nodes:
                member = self._members[str(inv.node_id)]
                member.require_unchanged()
                owner = _capture_configured_component_owner(member.registered, dict(inv.params))
                registry.register(
                    _AdmittedChildDispatch(
                        owner,
                        dict(inv.params),
                        self._grant,
                        fence=self._custody._fence,
                        scope=scope,
                    )
                )
            state = _state_copy(child_input, run_id=scope.run.run_manifest.run_id)
            ctx = ExecutionContext(
                store=scope.store,
                run=scope.run,
                depth=1,
                logger=logging.getLogger(f"{self._parent_context.logger.name}.child"),
                fabric=self._ports.fabric,
                foundry=self._ports.foundry,
                scholar=self._ports.scholar,
                lex=self._ports.lex,
                eval_safety_execution_context=self._ports.eval_safety_execution_context,
                eval_safety_verifier=self._ports.eval_safety_verifier,
            )
            from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor

            result = WorkflowExecutor(ctx, registry, _admitted_child=True).execute(
                self._workflow, state
            )
            raise_if_job_execution_interrupted()
            if time.monotonic() >= self._deadline:
                raise ValueError("child_inherited_deadline_expired")
            if result.report.status != "ok":
                raise ValueError("child_workflow_not_successful")
            projection = result.state.artifacts_index.get(self._projection_key)
            if projection is None or projection.manifest_profile_sha256 is None:
                raise ValueError("child_selected_projection_missing")
            self._custody.check_active(scope)
            handoff = self._custody.admit_handoff(scope, projection)
            self._handoffs.append(handoff)
            self._allowed.update((_ref_key(ref), ref) for ref in handoff.selected_refs)
            return handoff
        except BaseException as trigger:
            try:
                self._custody.revoke(scope, reason="child_execution_or_projection_failed")
            except BaseException as revoke_error:
                from polisyos.core.run.child_custody import (
                    ChildComputationOutcomeUnknown,
                    ChildRevocationUnknown,
                )

                if isinstance(trigger, ChildComputationOutcomeUnknown):
                    trigger.add_note(
                        "Child revocation also needs reconciliation: " + type(revoke_error).__name__
                    )
                    raise trigger
                unknown = ChildRevocationUnknown(self._custody._recovery_locator())
                unknown.add_note("Child revocation error: " + type(revoke_error).__name__)
                raise unknown from trigger
            raise
