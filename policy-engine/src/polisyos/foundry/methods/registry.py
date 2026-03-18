"""
Thread-Safe Method Registry with O(1) Lookup.

This module implements the central registry for all Foundry methods in PolicyOS.
It acts as the "DNS" for simulation methods, enabling lookup by:

- Fully Qualified Name (FQN): namespace.name@version
- Short name with version resolution
- Criteria queries (namespace, tags, slots)

Key Features:
- Thread-safe singleton pattern for process-wide consistency
- O(1) lookup by FQN via dictionary primary index
- Secondary indices (by_name, by_tag, etc.) for efficient filtering
- Lazy loading support to defer class instantiation
- Pluggable resolution policies (EXACT, LATEST_COMPATIBLE, LATEST, PINNED)
- Deterministic iteration order (sorted by FQN)

Architecture Laws:
- Law K: All version resolution uses explicit policies from resolution.py
- Law H: Registry state is deterministic given registration order

Thread Safety:
- Singleton creation uses double-checked locking pattern
- All mutations and reads are protected by RLock
- Lazy loading uses double-checked locking pattern

Usage:
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.foundry.methods.resolution import ResolutionPolicy

    registry = MethodRegistry.get_instance()

    # Register a method
    registry.register(MyTaxMethod)

    # Retrieve with version resolution
    method = registry.get("fiscal.taxation.flat_tax", policy=ResolutionPolicy.LATEST)

    # Query by criteria
    for sig in registry.query(tags={"fiscal"}, input_slots={"income"}):
        print(sig.fqn)
"""
from __future__ import annotations

import contextvars
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Any, Callable, Generator, Iterator, Mapping

from polisyos.core.registry import BaseRegistry
from polisyos.foundry.methods.base import (
    FoundryMethod,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.exceptions import (
    MethodAlreadyRegisteredError,
    MethodNotFoundError,
)
from polisyos.foundry.methods.lifecycle import (
    LifecycleLog,
    LifecycleManager,
    MethodLifecycle,
)

# ---------------------------------------------------------------------------
# Structured logging (optional — no-ops if structlog not installed)
# ---------------------------------------------------------------------------

try:
    import structlog as _structlog
    _log = _structlog.get_logger("foundry.registry")
    _STRUCTLOG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _STRUCTLOG_AVAILABLE = False
    _log = None  # type: ignore[assignment]


def _registry_log(event: str, **kwargs: object) -> None:
    """Emit a structured log event if structlog is available."""
    if _STRUCTLOG_AVAILABLE and _log is not None:
        try:
            _log.info(event, **kwargs)
        except Exception:
            pass  # never let logging break the registry


# ---------------------------------------------------------------------------
# Registry Audit Log
# ---------------------------------------------------------------------------

import time as _time
from typing import Literal

_AuditEventKind = Literal["register", "register_lazy", "unregister", "lazy_load", "conflict_skipped"]


@dataclass(slots=True)
class RegistryAuditEvent:
    """A single entry in the registry audit log."""

    event: str          # AuditEventKind value
    fqn: str
    timestamp: float    # time.time()
    caller: str         # simplified "module:lineno" string
    details: dict       # extra context (backend, version, lazy, ...)


class RegistryAuditLog:
    """
    Thread-safe in-process audit log for registry operations.

    Records every ``register``, ``register_lazy``, ``unregister``, and
    ``lazy_load`` call with caller information for post-mortem analysis.
    """

    def __init__(self) -> None:
        self._events: list[RegistryAuditEvent] = []
        self._lock = threading.Lock()

    def record(
        self,
        event: str,
        fqn: str,
        caller: str = "",
        **details: object,
    ) -> None:
        """Append an audit event (thread-safe)."""
        ev = RegistryAuditEvent(
            event=event,
            fqn=fqn,
            timestamp=_time.time(),
            caller=caller,
            details=dict(details),
        )
        with self._lock:
            self._events.append(ev)

    def get_history(self, fqn: str | None = None) -> list[RegistryAuditEvent]:
        """Return all events, optionally filtered by *fqn*."""
        with self._lock:
            if fqn is None:
                return list(self._events)
            return [e for e in self._events if e.fqn == fqn]

    def clear(self) -> None:
        """Clear all events (for testing)."""
        with self._lock:
            self._events.clear()

    def export_jsonl(self, path: "Path") -> None:
        """Write all events to *path* as newline-delimited JSON."""
        import json as _json
        with self._lock:
            lines = [
                _json.dumps({
                    "event": e.event,
                    "fqn": e.fqn,
                    "timestamp": e.timestamp,
                    "caller": e.caller,
                    **e.details,
                })
                for e in self._events
            ]
        Path(path).write_text("\n".join(lines) + ("\n" if lines else ""))

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)


# Process-wide audit log singleton
_AUDIT_LOG = RegistryAuditLog()


def get_registry_audit_log() -> RegistryAuditLog:
    """Return the global registry audit log."""
    return _AUDIT_LOG


from polisyos.foundry.methods.resolution import (
    ResolutionError,
    ResolutionPolicy,
    VersionConstraint,
    compare_versions,
    resolve_version,
)

__all__ = [
    "MethodEntry",
    "MethodRegistry",
    "RegistrySnapshot",
    "RegistryAuditEvent",
    "RegistryAuditLog",
    "get_registry",
    "get_registry_audit_log",
    "registry_scope",
    "MethodLifecycle",
]

MethodFactory = Callable[[], type[FoundryMethod]]


@dataclass(slots=True)
class MethodEntry:
    """
    Registry entry for a single method version.

    Entries can be in two states:
    - Loaded: _cached_class holds the actual class
    - Unloaded: factory will be called on first access (lazy loading)

    Attributes:
        signature: Method's immutable signature (contains FQN)
        metadata: Method's metadata for discovery
        factory: Callable that returns the method class
        loaded: Whether the class has been loaded
        _cached_class: The loaded class (None if not yet loaded)
        lifecycle_log: Ordered log of lifecycle state transitions
    """

    signature: MethodSignature
    metadata: MethodMetadata
    factory: MethodFactory
    loaded: bool = False
    _cached_class: type[FoundryMethod] | None = field(default=None, repr=False)
    lifecycle_log: LifecycleLog = field(default_factory=LifecycleLog, repr=False)

    @property
    def fqn(self) -> str:
        """Convenience accessor for entry's FQN."""
        return self.signature.fqn


class _MethodEntryStore(BaseRegistry[str, MethodEntry]):
    def __init__(self) -> None:
        super().__init__(
            key_fn=lambda entry: entry.fqn,
            indexers={
                "name": lambda entry: entry.signature.name,
                "namespace": lambda entry: entry.signature.namespace,
                "tag": lambda entry: entry.metadata.tags,
                "input_slot": lambda entry: [slot.name for slot in entry.signature.input_slots],
                "output_slot": lambda entry: [slot.name for slot in entry.signature.output_slots],
                "base_name": lambda entry: f"{entry.signature.namespace}.{entry.signature.name}",
            },
        )

    def duplicate_error(
        self,
        *,
        key: str,
        existing: MethodEntry,
        incoming: MethodEntry,
    ) -> Exception:
        return MethodAlreadyRegisteredError(key)


class RegistrySnapshot:
    """
    Immutable snapshot of registry state for consistent iteration.

    Used to provide atomic views of the registry without holding locks
    during iteration.
    """

    __slots__ = ("_methods", "_timestamp")

    def __init__(self, methods: Mapping[str, MethodEntry], timestamp: float) -> None:
        self._methods = dict(methods)
        self._timestamp = timestamp

    @property
    def timestamp(self) -> float:
        """Timestamp when snapshot was taken."""
        return self._timestamp

    def __len__(self) -> int:
        return len(self._methods)

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._methods.keys()))

    def signatures(self) -> Iterator[MethodSignature]:
        """Iterate over all signatures in deterministic order."""
        for fqn in sorted(self._methods.keys()):
            yield self._methods[fqn].signature


class MethodRegistry:
    """
    Singleton registry for all Foundry methods.

    Thread-safe with O(1) lookup by FQN and efficient queries by criteria.
    Supports lazy loading and multiple resolution policies.

    The registry maintains several indices:
    - Primary: FQN -> MethodEntry (O(1) lookup)
    - By name: short_name -> set[FQN]
    - By namespace: namespace -> set[FQN]
    - By tag: tag -> set[FQN]
    - By input slot: slot_name -> set[FQN]
    - By output slot: slot_name -> set[FQN]
    - Versions: base_name -> sorted[versions]
    """

    _instance: MethodRegistry | None = None
    _instance_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> MethodRegistry:
        """
        Create or return the singleton instance.

        Uses double-checked locking for thread-safe lazy initialization.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialize()
                    cls._instance = instance
        return cls._instance

    def _initialize(self) -> None:
        """Initialize registry state (called once during singleton creation)."""
        self._entries = _MethodEntryStore()

        self._default_policy: ResolutionPolicy = ResolutionPolicy.EXACT

        self._reg_lock = threading.RLock()

        self._registration_count = 0

        import time

        self._last_modified = time.time()

    @classmethod
    def get_instance(cls) -> MethodRegistry:
        """
        Get the singleton registry instance.

        Returns:
            The global MethodRegistry instance
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance.

        WARNING: This is intended for testing only. Resetting the registry
        in production will break any code holding references to registered
        methods.
        """
        with cls._instance_lock:
            cls._instance = None

    @classmethod
    def _create_fresh(cls) -> "MethodRegistry":
        """
        Create a brand-new, isolated MethodRegistry instance (NOT the singleton).

        Intended for use with ``registry_scope()`` to give tests and parallel
        workers their own isolated registries without touching the global singleton.
        """
        instance = object.__new__(cls)
        instance._initialize()
        return instance

    # ---------------------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------------------

    def set_default_policy(self, policy: ResolutionPolicy) -> None:
        """
        Set the default resolution policy for get() calls.

        Args:
            policy: The default policy to use when none is specified
        """
        if not isinstance(policy, ResolutionPolicy):
            raise TypeError(f"Expected ResolutionPolicy, got {type(policy).__name__}")
        self._default_policy = policy

    def get_default_policy(self) -> ResolutionPolicy:
        """Get the current default resolution policy."""
        return self._default_policy

    # ---------------------------------------------------------------------
    # Registration
    # ---------------------------------------------------------------------

    def register(self, method_class: type[FoundryMethod], *, override: bool = False) -> str:
        """
        Register a method class (eager registration).

        The method class must have 'signature' and 'metadata' class attributes
        conforming to the FoundryMethod protocol.

        Args:
            method_class: Class implementing FoundryMethod protocol
            override: If True, replace existing registration with same FQN

        Returns:
            The FQN of the registered method

        Raises:
            MethodAlreadyRegisteredError: If FQN exists and override=False
            TypeError: If method_class doesn't conform to protocol
        """
        if not hasattr(method_class, "signature"):
            raise TypeError(f"{method_class.__name__} missing 'signature' attribute")
        if not hasattr(method_class, "metadata"):
            raise TypeError(f"{method_class.__name__} missing 'metadata' attribute")

        sig = method_class.signature
        meta = method_class.metadata

        if not isinstance(sig, MethodSignature):
            raise TypeError(
                f"{method_class.__name__}.signature must be MethodSignature, "
                f"got {type(sig).__name__}"
            )
        if not isinstance(meta, MethodMetadata):
            raise TypeError(
                f"{method_class.__name__}.metadata must be MethodMetadata, "
                f"got {type(meta).__name__}"
            )

        fqn = sig.fqn

        with self._reg_lock:
            log = LifecycleLog()
            LifecycleManager.transition(log, fqn, MethodLifecycle.DEFINED, strict=False)
            entry = MethodEntry(
                signature=sig,
                metadata=meta,
                factory=lambda cls=method_class: cls,
                loaded=True,
                _cached_class=method_class,
                lifecycle_log=log,
            )

            self._entries.register(entry, override=override)
            LifecycleManager.transition(log, fqn, MethodLifecycle.REGISTERED, actor="registry.register")
            self._registration_count += 1
            self._touch_modified()
            _registry_log(
                "method_registered",
                fqn=fqn,
                namespace=sig.namespace,
                version=sig.version,
                backend=sig.backend.value,
                tags=sorted(str(t) for t in meta.tags),
                override=override,
                lazy=False,
            )
            _AUDIT_LOG.record("register", fqn, backend=sig.backend.value, lazy=False, override=override)

        return fqn

    def register_lazy(
        self,
        signature: MethodSignature,
        metadata: MethodMetadata,
        factory: MethodFactory,
        *,
        override: bool = False,
    ) -> str:
        """
        Register a method for lazy loading.

        The factory function will only be called when the method is first
        accessed via get(). This allows startup time optimization by
        deferring imports of heavy modules.
        """
        if not isinstance(signature, MethodSignature):
            raise TypeError(
                f"signature must be MethodSignature, got {type(signature).__name__}"
            )
        if not isinstance(metadata, MethodMetadata):
            raise TypeError(
                f"metadata must be MethodMetadata, got {type(metadata).__name__}"
            )
        if not callable(factory):
            raise TypeError(f"factory must be callable, got {type(factory).__name__}")

        fqn = signature.fqn

        with self._reg_lock:
            log = LifecycleLog()
            LifecycleManager.transition(log, fqn, MethodLifecycle.DEFINED, strict=False)
            entry = MethodEntry(
                signature=signature,
                metadata=metadata,
                factory=factory,
                loaded=False,
                _cached_class=None,
                lifecycle_log=log,
            )

            self._entries.register(entry, override=override)
            LifecycleManager.transition(log, fqn, MethodLifecycle.REGISTERED, actor="registry.register_lazy")
            self._registration_count += 1
            self._touch_modified()
            _registry_log(
                "method_registered",
                fqn=fqn,
                namespace=signature.namespace,
                version=signature.version,
                backend=signature.backend.value,
                tags=sorted(str(t) for t in metadata.tags),
                override=override,
                lazy=True,
            )
            _AUDIT_LOG.record("register_lazy", fqn, backend=signature.backend.value, lazy=True, override=override)

        return fqn

    def unregister(self, fqn: str) -> bool:
        """
        Remove a method from the registry.

        Args:
            fqn: Fully qualified name of method to remove

        Returns:
            True if method was removed, False if not found
        """
        with self._reg_lock:
            removed = self._entries.unregister(fqn)
            if removed is None:
                return False

            LifecycleManager.transition(
                removed.lifecycle_log, fqn, MethodLifecycle.RETIRED,
                actor="registry.unregister", strict=False,
            )
            self._touch_modified()
            _registry_log("method_unregistered", fqn=fqn)
            _AUDIT_LOG.record("unregister", fqn)
            return True

    # ---------------------------------------------------------------------
    # Index Management (internal)
    # ---------------------------------------------------------------------

    def _sort_versions(self, versions: list[str]) -> list[str]:
        """Sort version strings in descending order (newest first)."""
        return sorted(versions, key=cmp_to_key(compare_versions), reverse=True)

    def _available_versions(self, base_name: str) -> list[str]:
        rows = self._entries.find("base_name", base_name)
        versions = sorted({row.signature.version for row in rows})
        if not versions:
            return []
        return self._sort_versions(versions)

    def _touch_modified(self) -> None:
        """Update the last modified timestamp."""
        import time

        self._last_modified = time.time()

    # ---------------------------------------------------------------------
    # Retrieval
    # ---------------------------------------------------------------------

    def get(
        self,
        name: str,
        version: str | None = None,
        *,
        policy: ResolutionPolicy | None = None,
        constraint: VersionConstraint | None = None,
    ) -> type[FoundryMethod]:
        """
        Get a method by name with version resolution.

        This is the primary retrieval method. It supports:
        - Direct FQN lookup (O(1))
        - Short name lookup with version resolution
        - Base name (namespace.name) with version resolution
        """
        policy = policy or self._default_policy

        if "@" in name:
            with self._reg_lock:
                entry = self._entries.get(name)
            if entry is None:
                raise MethodNotFoundError(name)
            return self._load_entry(entry)

        with self._reg_lock:
            base_name = self._resolve_base_name(name)
            available = self._available_versions(base_name)

            if not available:
                raise MethodNotFoundError(name)

            try:
                resolved = resolve_version(
                    available=available,
                    requested=version,
                    policy=policy,
                    constraint=constraint,
                )
            except ResolutionError as exc:
                raise MethodNotFoundError(f"{name}: {exc.reason}") from exc
            except ValueError as exc:
                raise MethodNotFoundError(f"{name}: {exc}") from exc

            fqn = f"{base_name}@{resolved}"
            entry = self._entries.get(fqn)
            if entry is None:
                raise MethodNotFoundError(name)

        return self._load_entry(entry)

    def get_entry(self, fqn: str) -> MethodEntry | None:
        """
        Get the raw MethodEntry for an FQN.

        Does not trigger lazy loading.
        """
        with self._reg_lock:
            return self._entries.get(fqn)

    def get_signature(self, fqn: str) -> MethodSignature | None:
        """
        Get just the signature for an FQN (no loading).
        """
        with self._reg_lock:
            entry = self._entries.get(fqn)
            return entry.signature if entry else None

    def _resolve_base_name(self, name: str) -> str:
        """
        Resolve a short name or base name to a full base name.

        Args:
            name: Short name (e.g., "flat_tax") or base name

        Returns:
            Full base name (namespace.name)

        Raises:
            MethodNotFoundError: If name not found or ambiguous
        """
        if "." in name:
            if self._available_versions(name):
                return name
            raise MethodNotFoundError(name)

        rows = self._entries.find("name", name)
        if not rows:
            raise MethodNotFoundError(name)

        base_names = {f"{row.signature.namespace}.{row.signature.name}" for row in rows}

        if len(base_names) == 1:
            return next(iter(base_names))

        namespaces = sorted({row.signature.namespace for row in rows})
        raise MethodNotFoundError(
            f"Ambiguous name '{name}', found in namespaces: {namespaces}. "
            f"Please use fully qualified name (e.g., '{namespaces[0]}.{name}')"
        )

    def _load_entry(self, entry: MethodEntry) -> type[FoundryMethod]:
        """
        Load a method entry, triggering lazy loading if needed.

        Uses double-checked locking for thread safety.
        """
        if entry.loaded:
            return entry._cached_class  # type: ignore[return-value]

        with self._reg_lock:
            if not entry.loaded:
                entry._cached_class = entry.factory()
                entry.loaded = True

        return entry._cached_class  # type: ignore[return-value]

    # ---------------------------------------------------------------------
    # Queries
    # ---------------------------------------------------------------------

    def query(
        self,
        *,
        namespace: str | None = None,
        tags: set[str] | None = None,
        input_slots: set[str] | None = None,
        output_slots: set[str] | None = None,
        name_pattern: str | None = None,
    ) -> Iterator[MethodSignature]:
        """
        Query methods by criteria.

        All provided criteria are AND-combined. Results are yielded in
        deterministic order (sorted by FQN).
        """
        with self._reg_lock:
            candidates = set(self._entries.keys())

            if namespace is not None:
                candidates &= {entry.fqn for entry in self._entries.find("namespace", namespace)}

            if tags:
                for tag in tags:
                    candidates &= {entry.fqn for entry in self._entries.find("tag", tag)}

            if input_slots:
                for slot in input_slots:
                    candidates &= {entry.fqn for entry in self._entries.find("input_slot", slot)}

            if output_slots:
                for slot in output_slots:
                    candidates &= {entry.fqn for entry in self._entries.find("output_slot", slot)}

            if name_pattern:
                candidates = {
                    fqn for fqn in candidates
                    if (
                        (entry := self._entries.get(fqn)) is not None
                        and name_pattern in entry.signature.name
                    )
                }

            results = []
            for fqn in sorted(candidates):
                entry = self._entries.get(fqn)
                if entry is not None:
                    results.append(entry.signature)

        for signature in results:
            yield signature

    def find_by_output_slot(self, slot_name: str) -> Iterator[MethodSignature]:
        """Find all methods that produce a given output slot."""
        with self._reg_lock:
            results = [
                entry.signature for entry in sorted(
                    self._entries.find("output_slot", slot_name), key=lambda row: row.fqn
                )
            ]
        for signature in results:
            yield signature

    def find_by_input_slot(self, slot_name: str) -> Iterator[MethodSignature]:
        """Find all methods that consume a given input slot."""
        with self._reg_lock:
            results = [
                entry.signature for entry in sorted(
                    self._entries.find("input_slot", slot_name), key=lambda row: row.fqn
                )
            ]
        for signature in results:
            yield signature

    def find_connectable(self, source_fqn: str) -> Iterator[MethodSignature]:
        """
        Find methods that could consume output from source method.

        Returns methods with at least one input slot name matching
        a source output slot name.
        """
        with self._reg_lock:
            source = self._entries.get(source_fqn)
            if source is None:
                return

            output_names = source.signature.output_slot_names
            matching_fqns: set[str] = set()

            for slot_name in output_names:
                matching_fqns |= {
                    entry.fqn for entry in self._entries.find("input_slot", slot_name)
                }

            matching_fqns.discard(source_fqn)
            results = []
            for fqn in sorted(matching_fqns):
                entry = self._entries.get(fqn)
                if entry is not None:
                    results.append(entry.signature)

        for signature in results:
            yield signature

    # ---------------------------------------------------------------------
    # Listing and Inspection
    # ---------------------------------------------------------------------

    def list_all(self) -> list[MethodSignature]:
        """
        List all registered methods.

        Returns:
            List of MethodSignature, sorted by FQN
        """
        with self._reg_lock:
            return [
                entry.signature
                for _, entry in sorted(self._entries.items(), key=lambda row: row[0])
            ]

    def list_versions(self, base_name: str) -> list[str]:
        """
        List available versions for a method.
        """
        with self._reg_lock:
            if "." not in base_name:
                try:
                    base_name = self._resolve_base_name(base_name)
                except MethodNotFoundError:
                    return []
            return self._available_versions(base_name)

    def list_namespaces(self) -> list[str]:
        """List all registered namespaces."""
        with self._reg_lock:
            return sorted(str(value) for value in self._entries.index_values("namespace"))

    def list_tags(self) -> list[str]:
        """List all registered tags."""
        with self._reg_lock:
            return sorted(str(value) for value in self._entries.index_values("tag"))

    def snapshot(self) -> RegistrySnapshot:
        """
        Create an immutable snapshot of current registry state.

        Useful for consistent iteration without holding locks.
        """
        with self._reg_lock:
            return RegistrySnapshot(
                methods=dict(self._entries.items()),
                timestamp=self._last_modified,
            )

    # ---------------------------------------------------------------------
    # Container Protocol
    # ---------------------------------------------------------------------

    def __len__(self) -> int:
        """Number of registered methods."""
        with self._reg_lock:
            return self._entries.count

    def __contains__(self, fqn: str) -> bool:
        """Check if FQN is registered."""
        with self._reg_lock:
            return self._entries.get(fqn) is not None

    def __iter__(self) -> Iterator[str]:
        """Iterate over FQNs in deterministic order."""
        with self._reg_lock:
            fqns = self._entries.keys()
        return iter(sorted(fqns))

    # ---------------------------------------------------------------------
    # Debugging
    # ---------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """
        Get registry statistics for debugging.
        """
        with self._reg_lock:
            entries = self._entries.values()
            loaded_count = sum(1 for entry in entries if entry.loaded)
            total_methods = len(entries)
            return {
                "total_methods": total_methods,
                "loaded_methods": loaded_count,
                "lazy_methods": total_methods - loaded_count,
                "namespaces": len(self._entries.index_values("namespace")),
                "tags": len(self._entries.index_values("tag")),
                "input_slots": len(self._entries.index_values("input_slot")),
                "output_slots": len(self._entries.index_values("output_slot")),
                "base_names": len(self._entries.index_values("base_name")),
                "registrations": self._registration_count,
                "last_modified": self._last_modified,
            }

    def __repr__(self) -> str:
        return f"<MethodRegistry methods={len(self)}>"


# ---------------------------------------------------------------------------
# Context-variable for isolated registries (testing / parallel workers)
# ---------------------------------------------------------------------------

_registry_ctx: contextvars.ContextVar[MethodRegistry | None] = contextvars.ContextVar(
    "_foundry_registry", default=None
)


@contextmanager
def registry_scope() -> Generator[MethodRegistry, None, None]:
    """
    Context manager that provides an isolated, fresh MethodRegistry.

    Within the ``with`` block, all calls to ``get_registry()`` return the
    isolated instance instead of the global singleton.  This is the
    preferred pattern for tests and parallel execution:

        with registry_scope() as reg:
            ensure_all_methods_registered(reg)
            assert len(reg.list_all()) > 0

    The isolated registry is discarded when the block exits and never
    touches the global singleton.
    """
    fresh = MethodRegistry._create_fresh()
    token = _registry_ctx.set(fresh)
    try:
        yield fresh
    finally:
        _registry_ctx.reset(token)


def get_registry() -> MethodRegistry:
    """
    Get the active MethodRegistry for the current context.

    Returns the context-local registry if one is active (set via
    ``registry_scope()``), otherwise returns the global singleton.
    """
    ctx = _registry_ctx.get()
    if ctx is not None:
        return ctx
    return MethodRegistry.get_instance()
