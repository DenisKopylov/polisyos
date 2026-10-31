"""Operation-scoped Foundry access for an admitted local child workflow.

This is a managed-interface boundary for trusted builtins, not a Python sandbox.
The runtime bootstrap must independently appoint and reconcile the actual port.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.contracts import (
    CompileRequest,
    CompileResult,
    ExecuteRequest,
    ExecuteResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from polisyos.core.artifacts import ArtifactStore


_CHILD_FOUNDRY_DISPATCH_TOKEN = object()
_COMPILE_NODE = "scientist.node_compile_foundry@1.0.0"
_EXECUTE_NODE = "scientist.node_run_simulation@1.0.1"


@dataclass(frozen=True, slots=True)
class _FoundryBinding:
    """One immutable association of the actual delegate, owner and child scope."""

    delegate: object
    store: ArtifactStore
    grant: _BorrowedExecutionGrant
    fence: Any
    reconcile_owner: Callable[[], None]
    scope: object | None
    compile_descriptor: object
    compile_code: object
    execute_descriptor: object
    execute_code: object


class _ScopedChildFoundryPort:
    """Allow only the current appointed builtin to use its selected staged store."""

    __slots__ = ("_binding", "_current")

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("child Foundry binding is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("child Foundry binding is immutable")

    def __init__(
        self,
        *,
        delegate: object,
        store: ArtifactStore,
        grant: _BorrowedExecutionGrant,
        fence: Any,
        reconcile_owner: Callable[[], None],
        scope: object | None = None,
    ) -> None:
        if type(grant) is not _BorrowedExecutionGrant or not callable(reconcile_owner):
            raise ValueError("child_foundry_owner_not_established")
        if not callable(getattr(fence, "admit_producer", None)):
            raise ValueError("child_foundry_owner_not_established")
        if scope is not None and getattr(scope, "store", None) is not store:
            raise ValueError("child_foundry_scope_store_mismatch")
        methods: dict[str, tuple[object, object]] = {}
        for name in ("compile", "execute"):
            descriptor = inspect.getattr_static(type(delegate), name, None)
            if (
                not inspect.isfunction(descriptor)
                or inspect.getattr_static(delegate, name) is not descriptor
            ):
                raise ValueError("child_foundry_delegate_not_established")
            methods[name] = (descriptor, descriptor.__code__)
        self._binding = _FoundryBinding(
            delegate=delegate,
            store=store,
            grant=grant,
            fence=fence,
            reconcile_owner=reconcile_owner,
            scope=scope,
            compile_descriptor=methods["compile"][0],
            compile_code=methods["compile"][1],
            execute_descriptor=methods["execute"][0],
            execute_code=methods["execute"][1],
        )
        self._current: ContextVar[str | None] = ContextVar(
            f"child_foundry_producer_{id(self)}", default=None
        )

    @contextmanager
    def _producer_scope(self, node_id: str, *, _token: object) -> Iterator[None]:
        """Enter a held engine dispatch; a sibling cannot inherit another operation."""
        if _token is not _CHILD_FOUNDRY_DISPATCH_TOKEN or node_id not in {
            _COMPILE_NODE,
            _EXECUTE_NODE,
        }:
            raise ValueError("child_foundry_operation_not_admitted")
        self._binding.grant.check_current()
        if self._current.get() is not None:
            raise ValueError("child_foundry_scope_already_active")
        token = self._current.set(node_id)
        try:
            yield
        finally:
            self._current.reset(token)

    def _for_child_scope(self, scope: object) -> _ScopedChildFoundryPort:
        """Narrow an appointed parent factory to one actual Core child scope."""
        from polisyos.core.run.child_custody import ChildStagingScope

        binding = self._binding
        if binding.scope is not None or type(scope) is not ChildStagingScope:
            raise ValueError("child_foundry_scope_factory_not_appointed")
        binding.grant.check_current()
        binding.reconcile_owner()
        # The real registered owner verifies this scope belongs to the same
        # live parent. Selecting a store does not manufacture a new read grant.
        binding.fence.admit_producer(scope)
        return _ScopedChildFoundryPort(
            delegate=binding.delegate,
            store=scope.store,
            grant=binding.grant,
            fence=binding.fence,
            reconcile_owner=binding.reconcile_owner,
            scope=scope,
        )

    def _admit(self, *, operation: str, node_id: str, store: ArtifactStore) -> None:
        if self._current.get() != node_id:
            raise ValueError("child_foundry_operation_not_admitted")
        binding = self._binding
        if store is not binding.store or (
            binding.scope is not None and getattr(binding.scope, "store", None) is not store
        ):
            raise ValueError("child_foundry_store_not_admitted")
        binding.grant.check_current()
        descriptor, code = (
            (binding.compile_descriptor, binding.compile_code)
            if operation == "compile"
            else (binding.execute_descriptor, binding.execute_code)
        )
        current = inspect.getattr_static(type(binding.delegate), operation, None)
        if (
            current is not descriptor
            or getattr(current, "__code__", None) is not code
            or inspect.getattr_static(binding.delegate, operation, None) is not descriptor
        ):
            raise ValueError("child_foundry_delegate_changed")
        binding.reconcile_owner()
        if binding.scope is None:
            binding.fence.admit_producer()
        else:
            binding.fence.admit_producer(binding.scope)

    def compile(self, store: ArtifactStore, request: CompileRequest) -> CompileResult:
        """Run a typed compile request on the admitted child store."""
        if type(request) is not CompileRequest:
            raise TypeError("child_foundry_compile_request_invalid")
        self._admit(operation="compile", node_id=_COMPILE_NODE, store=store)
        binding = self._binding
        descriptor = binding.compile_descriptor
        # The private store has no ambient default view. Ask the existing
        # producer for the exact occurrence rather than inferring a profile
        # from a digest after it has returned.
        selected_request = request.model_copy(update={"return_selected_profile": True})
        result = descriptor(binding.delegate, store, selected_request)  # type: ignore[operator]
        binding.grant.check_current()
        if type(result) is not CompileResult:
            raise TypeError("child_foundry_compile_result_invalid")
        self._require_selected_refs(
            result.compile_report_ref,
            result.exec_plan_ref,
            *(item.ref for item in result.derived_refs),
        )
        return result

    def execute(self, store: ArtifactStore, request: ExecuteRequest) -> ExecuteResult:
        """Run a typed simulation request on the admitted child store."""
        if type(request) is not ExecuteRequest:
            raise TypeError("child_foundry_execute_request_invalid")
        self._admit(operation="execute", node_id=_EXECUTE_NODE, store=store)
        binding = self._binding
        descriptor = binding.execute_descriptor
        selected_request = request.model_copy(update={"return_selected_profile": True})
        result = descriptor(binding.delegate, store, selected_request)  # type: ignore[operator]
        binding.grant.check_current()
        if type(result) is not ExecuteResult:
            raise TypeError("child_foundry_execute_result_invalid")
        self._require_selected_refs(
            result.simulation_result_ref,
            result.method_execution_bundle_ref,
            *(item.ref for item in result.derived_refs),
        )
        return result

    @staticmethod
    def _require_selected_refs(*refs: ArtifactRef | None) -> None:
        """Refuse an emitted occurrence whose exact profile cannot be resolved."""
        if any(
            ref is not None
            and (not isinstance(ref, ArtifactRef) or not ref.manifest_profile_sha256)
            for ref in refs
        ):
            raise ValueError("child_foundry_output_profile_missing")
