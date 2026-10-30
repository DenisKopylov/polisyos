"""Operation-scoped Foundry access for an admitted local child workflow.

This is a managed-interface boundary for trusted builtins, not a Python sandbox.
The runtime bootstrap must independently appoint and reconcile the actual port.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    ExecuteRequest,
    ExecuteResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from polisyos.core.artifacts.protocol import ArtifactStore


_CHILD_FOUNDRY_DISPATCH_TOKEN = object()
_COMPILE_NODE = "scientist.node_compile_foundry@1.0.0"
_EXECUTE_NODE = "scientist.node_run_simulation@1.0.1"


class _ScopedChildFoundryPort:
    """Allow only the current appointed builtin to use its selected staged store."""

    def __init__(
        self,
        *,
        delegate: object,
        store: ArtifactStore,
        grant: _BorrowedExecutionGrant,
        fence: Any,
        reconcile_owner: Callable[[], None],
    ) -> None:
        if type(grant) is not _BorrowedExecutionGrant or not callable(reconcile_owner):
            raise ValueError("child_foundry_owner_not_established")
        if not callable(getattr(fence, "admit_producer", None)):
            raise ValueError("child_foundry_owner_not_established")
        methods: dict[str, tuple[object, object]] = {}
        for name in ("compile", "execute"):
            descriptor = inspect.getattr_static(type(delegate), name, None)
            if (
                not inspect.isfunction(descriptor)
                or inspect.getattr_static(delegate, name) is not descriptor
            ):
                raise ValueError("child_foundry_delegate_not_established")
            methods[name] = (descriptor, descriptor.__code__)
        self._delegate = delegate
        self._store = store
        self._grant = grant
        self._fence = fence
        self._reconcile_owner = reconcile_owner
        self._methods = methods
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
        self._grant.check_current()
        if self._current.get() is not None:
            raise ValueError("child_foundry_scope_already_active")
        token = self._current.set(node_id)
        try:
            yield
        finally:
            self._current.reset(token)

    def _admit(self, *, operation: str, node_id: str, store: ArtifactStore) -> None:
        if self._current.get() != node_id:
            raise ValueError("child_foundry_operation_not_admitted")
        if store is not self._store:
            raise ValueError("child_foundry_store_not_admitted")
        self._grant.check_current()
        descriptor, code = self._methods[operation]
        current = inspect.getattr_static(type(self._delegate), operation, None)
        if (
            current is not descriptor
            or getattr(current, "__code__", None) is not code
            or inspect.getattr_static(self._delegate, operation, None) is not descriptor
        ):
            raise ValueError("child_foundry_delegate_changed")
        self._reconcile_owner()
        self._fence.admit_producer()

    def compile(self, store: ArtifactStore, request: CompileRequest) -> CompileResult:
        """Run a typed compile request on the admitted child store."""
        if type(request) is not CompileRequest:
            raise TypeError("child_foundry_compile_request_invalid")
        self._admit(operation="compile", node_id=_COMPILE_NODE, store=store)
        descriptor, _ = self._methods["compile"]
        # The private store has no ambient default view. Ask the existing
        # producer for the exact occurrence rather than inferring a profile
        # from a digest after it has returned.
        selected_request = request.model_copy(update={"return_selected_profile": True})
        result = descriptor(self._delegate, store, selected_request)  # type: ignore[operator]
        self._grant.check_current()
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
        descriptor, _ = self._methods["execute"]
        selected_request = request.model_copy(update={"return_selected_profile": True})
        result = descriptor(self._delegate, store, selected_request)  # type: ignore[operator]
        self._grant.check_current()
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
