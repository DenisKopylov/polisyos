"""Core-owned boundary for staging and admitting run-worker receipts."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.trace import JsonlTraceSink

from .context import RunContext, _FinalizeRecoveryError
from .manifest import RunManifest

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.run.child_custody import _ChildControlOwner
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.trace.record import TraceRecord
    from polisyos.core.trace.sink import TraceSink

_LIFECYCLE_REFUSAL = "timeout_worker_run_lifecycle_not_owned"


@dataclass(frozen=True, slots=True, init=False)
class WorkerDispatchBinding:
    """Identify one worker dispatch against an exact run-owner snapshot."""

    run_id: str
    invocation_id: str
    dispatch_sha256: str
    _owner_snapshot_artifact_id: str
    _owner_snapshot_kind: str
    _owner_snapshot_media_type: str
    _owner_snapshot_profile_sha256: str | None

    def __init__(
        self,
        *,
        run_id: str,
        invocation_id: str,
        dispatch_sha256: str,
        owner_snapshot_ref: ArtifactRef,
    ) -> None:
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "invocation_id", invocation_id)
        object.__setattr__(self, "dispatch_sha256", dispatch_sha256)
        object.__setattr__(
            self,
            "_owner_snapshot_artifact_id",
            str(owner_snapshot_ref.artifact_id),
        )
        object.__setattr__(self, "_owner_snapshot_kind", owner_snapshot_ref.kind)
        object.__setattr__(self, "_owner_snapshot_media_type", owner_snapshot_ref.media_type)
        object.__setattr__(
            self,
            "_owner_snapshot_profile_sha256",
            owner_snapshot_ref.manifest_profile_sha256,
        )

    @property
    def owner_snapshot_ref(self) -> ArtifactRef:
        """Return a fresh typed reference so callers cannot mutate the binding."""
        return ArtifactRef(
            artifact_id=self._owner_snapshot_artifact_id,
            kind=self._owner_snapshot_kind,
            media_type=self._owner_snapshot_media_type,
            manifest_profile_sha256=self._owner_snapshot_profile_sha256,
        )


@dataclass(frozen=True, slots=True)
class WorkerRunSnapshot:
    """Detached profile projection needed to serialize a worker run context."""

    run_id: str
    run_manifest: RunManifest
    trace_path: Path | None
    owner_snapshot_ref: ArtifactRef
    access_scope: AccessScope | None
    tenant_id: str | None
    cell_id: str | None
    trace_is_jsonl: bool
    audit_sink_present: bool


_WORKER_VIEW_TOKEN = object()
_CAPABILITY_TOKEN = object()
_CHILD_CAPABILITY_TOKEN = object()


def _require_fixed_runtime_child_control(control: object) -> _ChildControlOwner:
    """Reconcile the fixed Runtime registrar's source and real guard lookup."""
    from polisyos.core.components._provider_origin import _callable_source

    descriptor = inspect.getattr_static(type(control), "_require_parent", None)
    try:
        module, source = _callable_source(descriptor)
        expected = (
            Path(__file__).resolve().parents[2] / "runtime" / "http" / "resilience.py"
        ).resolve(strict=True)
        lookup = module.__dict__.get("_require_runtime_control_store_guard")
        lookup_module, lookup_source = _callable_source(lookup)
    except Exception as exc:
        raise ValueError("child_runtime_control_origin_not_established") from exc
    if (
        module.__name__ != "polisyos.runtime.http.resilience"
        or source != expected
        or lookup_module is not module
        or lookup_source != expected
        or module.__dict__.get("_RuntimeGuardedChildFence") is not type(control)
        or inspect.getattr_static(control, "_require_parent", None) is not descriptor
    ):
        raise ValueError("child_runtime_control_origin_not_established")
    # The exact class is established against its Runtime implementation above.
    return cast("_ChildControlOwner", control)


class ChildRuntimeCapability:
    """Core-owned child purpose for one actual parent and guarded control owner.

    This separate capability does not extend worker receipt authority. It is
    created only after the current Core session and fixed Runtime control owner
    have been independently reconciled; it does not itself publish results.
    """

    __slots__ = ("__control", "__run", "__session")

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("child runtime capability binding is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("child runtime capability binding is immutable")

    def __init__(
        self, run: RunContext, session: object, control: _ChildControlOwner, *, _token: object
    ) -> None:
        if _token is not _CHILD_CAPABILITY_TOKEN:
            raise TypeError("child runtime capabilities are created by their factory")
        self.__run = run
        self.__session = session
        self.__control = control

    @classmethod
    def for_parent(
        cls, run: object, *, session: object, runtime_control: object
    ) -> ChildRuntimeCapability:
        """Bind one live Core session to its fixed, source-verified Runtime owner.

        Args:
            run: The exact active Core run, not a worker or node view.
            session: The Core-owned child session already bound to that run.
            runtime_control: Its fixed Runtime control owner.

        Returns:
            A child-purpose capability scoped to this actual parent session.

        Raises:
            ValueError: If the owner, attempt, service, or guard is not current.
        """
        from .child_custody import ChildComputationCustody

        if (
            type(run) is not RunContext
            or type(session) is not ChildComputationCustody
            or session._root is not run
            or session._fence is not runtime_control
            or session._binding is None
        ):
            raise ValueError("child_runtime_parent_owner_not_established")
        control = _require_fixed_runtime_child_control(runtime_control)
        session._check_root(session._binding)
        return cls(run, session, control, _token=_CHILD_CAPABILITY_TOKEN)

    def _issue_session_operation(self, intent: object) -> object:
        """Issue a one-use session decision from the retained Core owner."""
        from .child_custody import ChildComputationCustody, ChildJobSessionIntent

        session = self.__session
        control_identity: object = self.__control
        if (
            type(session) is not ChildComputationCustody
            or type(intent) is not ChildJobSessionIntent
            or session._root is not self.__run
            or session._fence is not control_identity
        ):
            raise ValueError("child_runtime_session_owner_changed")
        _require_fixed_runtime_child_control(self.__control)
        return session._issue_control_operation(intent, self.__control, kind="session")

    def _issue_scope_operation(self, prepared: object) -> object:
        """Issue a one-use scope decision from the retained Core owner."""
        from .child_custody import ChildComputationCustody, ChildPreparedScope

        session = self.__session
        control_identity: object = self.__control
        if (
            type(session) is not ChildComputationCustody
            or type(prepared) is not ChildPreparedScope
            or session._root is not self.__run
            or session._fence is not control_identity
        ):
            raise ValueError("child_runtime_session_owner_changed")
        _require_fixed_runtime_child_control(self.__control)
        return session._issue_control_operation(prepared, self.__control, kind="scope")

    def _issue_release_operation(self, candidate: object) -> object:
        """Issue a one-use release decision from the retained Core owner."""
        from .child_custody import ChildComputationCustody, ChildJobReleaseCandidate

        session = self.__session
        control_identity: object = self.__control
        if (
            type(session) is not ChildComputationCustody
            or type(candidate) is not ChildJobReleaseCandidate
            or session._root is not self.__run
            or session._fence is not control_identity
        ):
            raise ValueError("child_runtime_session_owner_changed")
        _require_fixed_runtime_child_control(self.__control)
        return session._issue_control_operation(candidate, self.__control, kind="authorization")


class WorkerRunView(RunContext):
    """A RunContext-compatible view that stages work without lifecycle authority."""

    __slots__ = ("__adapter", "__binding")

    _HIDDEN_NAMES = frozenset(
        {
            "_active_lease",
            "_audit_sink",
            "_closed",
            "_owner_snapshot_ref",
            "_runtime_invocation_tail_ref",
            "_suspended",
            "_target",
            "_trace_path",
            "_worker_lifecycle_capability",
            "_worker_merge_lock",
            "_worker_receipt_recovery_invocation_id",
            "_worker_receipt_recovery_required",
            "merge_worker_events",
            "_merge_worker_events_locked",
        }
    )
    _LOCAL_NAMES = frozenset(
        {
            "__class__",
            "__delattr__",
            "__getattribute__",
            "__init__",
            "__repr__",
            "__setattr__",
            "dispatch_binding",
            "_parent_state_transition_lease",
            "_require_active_lease_owner",
            "finalize",
            "suspend_for_resume",
        }
    )
    _IDENTITY_FIELDS = frozenset(
        {"access_scope", "cell_id", "run_manifest", "store", "tenant_id", "trace"}
    )

    def __init__(
        self,
        adapter: object,
        *,
        binding: WorkerDispatchBinding | None,
        _token: object,
    ) -> None:
        if _token is not _WORKER_VIEW_TOKEN:
            raise TypeError("worker run views are created by WorkerLifecycleCapability")
        object.__setattr__(self, "_WorkerRunView__adapter", adapter)
        object.__setattr__(self, "_WorkerRunView__binding", binding)

    def __getattribute__(self, name: str) -> object:
        if name in WorkerRunView._HIDDEN_NAMES or (
            name.startswith("_") and name not in WorkerRunView._LOCAL_NAMES
        ):
            raise AttributeError(name)
        if name in WorkerRunView._LOCAL_NAMES:
            return object.__getattribute__(self, name)
        adapter = object.__getattribute__(self, "_WorkerRunView__adapter")
        value = getattr(adapter, name)
        if name == "run_manifest" and type(value) is RunManifest:
            return value.model_copy(deep=True)
        return value

    def __setattr__(self, name: str, value: object) -> None:
        if (
            name.startswith("_")
            or name in WorkerRunView._IDENTITY_FIELDS
            or name
            in {
                "finalize",
                "suspend_for_resume",
                "trace_path",
            }
        ):
            raise AttributeError("worker run owner fields cannot be rebound")
        adapter = object.__getattribute__(self, "_WorkerRunView__adapter")
        setattr(adapter, name, value)

    def __delattr__(self, name: str) -> None:
        if (
            name.startswith("_")
            or name in WorkerRunView._IDENTITY_FIELDS
            or name
            in {
                "finalize",
                "suspend_for_resume",
                "trace_path",
            }
        ):
            raise AttributeError("worker run owner fields cannot be removed")
        adapter = object.__getattribute__(self, "_WorkerRunView__adapter")
        delattr(adapter, name)

    def __repr__(self) -> str:
        return f"WorkerRunView(run_id={self.run_manifest.run_id!r})"

    @property
    def dispatch_binding(self) -> WorkerDispatchBinding | None:
        """Return the immutable dispatch identity associated with this worker view."""
        return object.__getattribute__(self, "_WorkerRunView__binding")

    def _require_active_lease_owner(self) -> None:
        raise _FinalizeRecoveryError(_LIFECYCLE_REFUSAL)

    def _parent_state_transition_lease(self, *, run_scoped: bool = True) -> Iterator[None]:
        del run_scoped
        raise _FinalizeRecoveryError(_LIFECYCLE_REFUSAL)

    def finalize(
        self,
        status: str = "ok",
        *,
        errors: list[dict[str, object]] | None = None,
    ) -> ArtifactRef:
        del status, errors
        raise _FinalizeRecoveryError(_LIFECYCLE_REFUSAL)

    def suspend_for_resume(self) -> None:
        raise _FinalizeRecoveryError(_LIFECYCLE_REFUSAL)


class WorkerLifecycleCapability:
    """Bind worker operations to a parent-owned run lifecycle.

    Parent capabilities issue dispatch bindings and admit their receipts through
    the run's existing merge_worker_events writer. Worker-only capabilities
    expose a lifecycle-limited run view and cannot admit receipts.
    """

    __slots__ = ("__binding", "__issued", "__mode", "__run")

    def __init__(
        self,
        run: RunContext,
        *,
        mode: str,
        binding: WorkerDispatchBinding | None = None,
        _token: object,
    ) -> None:
        if _token is not _CAPABILITY_TOKEN:
            raise TypeError("worker lifecycle capabilities are created by their factories")
        self.__run = run
        self.__mode = mode
        self.__binding = binding
        self.__issued: dict[str, WorkerDispatchBinding] = {}

    @classmethod
    def for_parent(cls, run: RunContext) -> WorkerLifecycleCapability:
        """Bind to the exact live run whose process owns its active lease.

        Args:
            run: Exact Core run receiving worker receipts.

        Returns:
            A capability that can bind and admit staged worker receipts.

        Raises:
            ValueError: If the run is not the active owner-bound Core context.
        """
        if type(run) is not RunContext:
            raise ValueError("worker_lifecycle_core_run_required")
        if run._active_lease is None or run._closed or run._suspended or run._trace_path is None:
            raise ValueError("worker_lifecycle_parent_run_not_active")
        run._require_active_lease_owner()
        run._validate_timeout_worker_owner_binding()
        return cls(run, mode="parent", _token=_CAPABILITY_TOKEN)

    @classmethod
    def for_worker(
        cls,
        run: RunContext,
        *,
        invocation_id: str | None = None,
        dispatch_sha256: str | None = None,
    ) -> WorkerLifecycleCapability:
        """Bind a reconstructed worker context to its selected owner snapshot.

        This capability can stage ordinary run operations but cannot create a
        parent dispatch or admit a receipt.

        Args:
            run: Reconstructed Core run with its source-bound owner snapshot.
            invocation_id: Parent-issued invocation identifier, when receipted.
            dispatch_sha256: Parent-computed dispatch digest, when receipted.

        Returns:
            A worker-only capability for the staged context.

        Raises:
            ValueError: If the run or supplied dispatch identity is invalid.
        """
        if type(run) is not RunContext:
            raise ValueError("worker_lifecycle_core_run_required")
        if (invocation_id is None) != (dispatch_sha256 is None):
            raise ValueError("worker_lifecycle_dispatch_binding_incomplete")
        run._validate_timeout_worker_owner_binding()
        binding = None
        if invocation_id is not None and dispatch_sha256 is not None:
            owner_ref = run._owner_snapshot_ref
            if type(owner_ref) is not ArtifactRef:
                raise ValueError("worker_lifecycle_owner_snapshot_required")
            cls._validate_digest(invocation_id, "worker_lifecycle_invocation_id_invalid")
            cls._validate_digest(dispatch_sha256, "worker_lifecycle_dispatch_digest_invalid")
            binding = WorkerDispatchBinding(
                run_id=run.run_manifest.run_id,
                invocation_id=invocation_id,
                dispatch_sha256=dispatch_sha256,
                owner_snapshot_ref=owner_ref,
            )
        return cls(run, mode="worker", binding=binding, _token=_CAPABILITY_TOKEN)

    @classmethod
    def for_worker_context(
        cls,
        *,
        store: ArtifactStore,
        trace: TraceSink,
        run_manifest: RunManifest,
        trace_path: Path,
        owner_snapshot_ref: ArtifactRef,
        access_scope: AccessScope | None,
        tenant_id: str | None,
        cell_id: str | None,
        invocation_id: str | None = None,
        dispatch_sha256: str | None = None,
    ) -> WorkerLifecycleCapability:
        """Construct and bind one validated worker run from its typed wire fields.

        Args:
            store: Worker-local handle to the selected artifact store.
            trace: Worker-local staged trace sink.
            run_manifest: Exact manifest reconstructed from the dispatch wire.
            trace_path: Parent trace location used only for source-bound validation.
            owner_snapshot_ref: Selected owner snapshot carried by that wire.
            access_scope: Reconstructed run access scope.
            tenant_id: Run tenant identity.
            cell_id: Run cell identity.
            invocation_id: Parent-issued invocation identifier, when receipted.
            dispatch_sha256: Parent-computed dispatch digest, when receipted.

        Returns:
            A worker-only capability that exposes no parent lifecycle authority.
        """
        run = RunContext(
            store=store,
            trace=trace,
            run_manifest=run_manifest,
            _trace_path=trace_path,
            _audit_sink=None,
            tenant_id=tenant_id,
            cell_id=cell_id,
            access_scope=access_scope,
            _owner_snapshot_ref=owner_snapshot_ref,
        )
        return cls.for_worker(
            run,
            invocation_id=invocation_id,
            dispatch_sha256=dispatch_sha256,
        )

    @staticmethod
    def _validate_digest(value: str, reason: str) -> None:
        if (
            type(value) is not str
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(reason)

    @property
    def binding(self) -> WorkerDispatchBinding | None:
        """Return the immutable binding issued for a reconstructed worker, if any."""
        return self.__binding

    def snapshot(self) -> WorkerRunSnapshot:
        """Revalidate and return only the typed profile needed by a worker bridge.

        Returns:
            A detached run-manifest snapshot and selected owner reference.

        Raises:
            ValueError: If the selected owner snapshot no longer matches the run.
        """
        run = self.__run
        if self.__mode == "parent":
            if (
                run._active_lease is None
                or run._closed
                or run._suspended
                or run._trace_path is None
            ):
                raise ValueError("worker_lifecycle_parent_run_not_active")
            run._validate_timeout_worker_owner_binding()
        else:
            run._validate_timeout_worker_owner_binding()
        owner_ref = run._owner_snapshot_ref
        if type(owner_ref) is not ArtifactRef:
            raise ValueError("worker_lifecycle_owner_snapshot_required")
        if self.__binding is not None and (
            self.__binding.run_id != run.run_manifest.run_id
            or self.__binding.owner_snapshot_ref != owner_ref
        ):
            raise ValueError("worker_lifecycle_binding_stale")
        return WorkerRunSnapshot(
            run_id=run.run_manifest.run_id,
            run_manifest=run.run_manifest.model_copy(deep=True),
            trace_path=run.trace_path,
            owner_snapshot_ref=owner_ref.model_copy(deep=True),
            access_scope=run.access_scope,
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            trace_is_jsonl=type(run.trace) is JsonlTraceSink,
            audit_sink_present=run._audit_sink is not None,
        )

    def _require_parent_snapshot(self) -> RunContext:
        if self.__mode != "parent":
            raise ValueError("worker_lifecycle_parent_capability_required")
        run = self.__run
        if run._active_lease is None or run._closed or run._suspended or run._trace_path is None:
            raise ValueError("worker_lifecycle_parent_run_not_active")
        run._validate_timeout_worker_owner_binding()
        return run

    def _require_parent_owner(self) -> RunContext:
        run = self._require_parent_snapshot()
        run._require_active_lease_owner()
        return run

    def bind_dispatch(
        self,
        *,
        invocation_id: str,
        dispatch_sha256: str,
    ) -> WorkerDispatchBinding:
        """Issue an immutable receipt binding from the current parent snapshot.

        Args:
            invocation_id: Parent-generated 64-character lowercase hex nonce.
            dispatch_sha256: Digest of the complete parent dispatch.

        Returns:
            A binding tied to this capability's exact run and owner reference.

        Raises:
            ValueError: If the capability is worker-only or the run is stale.
        """
        run = self._require_parent_owner()
        self._validate_digest(invocation_id, "worker_lifecycle_invocation_id_invalid")
        self._validate_digest(dispatch_sha256, "worker_lifecycle_dispatch_digest_invalid")
        owner_ref = run._owner_snapshot_ref
        if type(owner_ref) is not ArtifactRef:
            raise ValueError("worker_lifecycle_owner_snapshot_required")
        binding = WorkerDispatchBinding(
            run_id=run.run_manifest.run_id,
            invocation_id=invocation_id,
            dispatch_sha256=dispatch_sha256,
            owner_snapshot_ref=owner_ref,
        )
        if invocation_id in self.__issued:
            raise ValueError("worker_lifecycle_invocation_id_reused")
        self.__issued[invocation_id] = binding
        return binding

    def worker_view(
        self,
        *,
        run_adapter: object | None = None,
        trace: TraceSink | None = None,
        binding: WorkerDispatchBinding | None = None,
    ) -> WorkerRunView:
        """Create a child-compatible run view without lifecycle-owner fields.

        Args:
            run_adapter: Optional existing attempt wrapper for ordinary write gating.
            trace: Optional staged sink installed in this worker process.
            binding: Dispatch identity carried by a parent-issued worker receipt.

        Returns:
            A RunContext-compatible view whose lifecycle operations always refuse.
        """
        run = self.__run
        if self.__mode == "parent":
            self._require_parent_snapshot()
        else:
            run._validate_timeout_worker_owner_binding()
        if binding is None:
            binding = self.__binding
        elif self.__mode == "parent" and self.__issued.get(binding.invocation_id) != binding:
            raise ValueError("worker_lifecycle_dispatch_binding_unissued")
        elif self.__binding is not None and self.__binding != binding:
            raise ValueError("worker_lifecycle_dispatch_binding_mismatch")
        if binding is not None:
            snapshot = self.snapshot()
            if (
                binding.run_id != snapshot.run_id
                or binding.owner_snapshot_ref != snapshot.owner_snapshot_ref
            ):
                raise ValueError("worker_lifecycle_binding_stale")
        run._stage_worker_trace(trace)
        adapter = run if run_adapter is None else run_adapter
        return WorkerRunView(adapter, binding=binding, _token=_WORKER_VIEW_TOKEN)

    def admit_worker_events(
        self,
        binding: WorkerDispatchBinding,
        records: Sequence[TraceRecord],
    ) -> None:
        """Admit one issued receipt through the existing Core merge writer.

        Args:
            binding: Exact binding previously issued by this parent capability.
            records: Typed staged trace records returned by the worker.

        Raises:
            ValueError: If the binding is not issued by this capability.
            _FinalizeRecoveryError: If Core refuses stale, malformed, or replayed input.
        """
        run = self._require_parent_owner()
        if (
            type(binding) is not WorkerDispatchBinding
            or self.__issued.get(binding.invocation_id) != binding
            or binding.run_id != run.run_manifest.run_id
        ):
            raise ValueError("worker_lifecycle_dispatch_binding_unissued")
        run.merge_worker_events(
            invocation_id=binding.invocation_id,
            dispatch_sha256=binding.dispatch_sha256,
            owner_snapshot_ref=binding.owner_snapshot_ref,
            records=records,
        )
        self.__issued.pop(binding.invocation_id, None)


__all__ = [
    "ChildRuntimeCapability",
    "WorkerDispatchBinding",
    "WorkerLifecycleCapability",
    "WorkerRunSnapshot",
    "WorkerRunView",
]
