"""
Deprecation Workflow for Foundry methods.

Provides a structured, two-phase deprecation process:

Phase 1 — Soft deprecation:
    ``@deprecate_method(since="2.1.0", removal="3.0.0", replacement="new.fqn")``
    emits a ``DeprecationWarning`` on every invocation of ``pure_step``.
    The method remains registered and functional.

Phase 2 — Hard deprecation (retired):
    Setting ``retired=True`` on the decorator causes ``pure_step`` to raise
    ``MethodRetiredException`` immediately, preventing use.

Registry integration:
    ``tag_deprecated_in_registry()`` adds ``"deprecated:X.Y.Z"`` and
    ``"removal:X.Y.Z"`` tags to the method's metadata in the live registry.

Audit:
    ``DeprecationAudit.report()`` scans the registry and returns a
    ``DeprecationAuditReport`` listing all deprecated / retired methods with
    their deprecation timelines.

Usage
-----
::

    from polisyos.foundry.methods.deprecation import deprecate_method

    @foundry_method(namespace="old.ns", version="1.2.0", tags={"legacy"})
    @deprecate_method(
        since="1.2.0",
        removal="2.0.0",
        replacement="new.ns.better_method@1.0.0",
        reason="SupersededByBetterAlgorithm",
    )
    class OldMethod:
        ...

Audit
-----
::

    from polisyos.foundry.methods.deprecation import DeprecationAudit
    audit = DeprecationAudit()
    report = audit.report()
    report.print()
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

__all__ = [
    "DeprecationAudit",
    "DeprecationAuditReport",
    "DeprecationInfo",
    "MethodRetiredException",
    "deprecate_method",
    "tag_deprecated_in_registry",
]

T = TypeVar("T", bound=type)


# ---------------------------------------------------------------------------
# DeprecationInfo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeprecationInfo:
    """Deprecation metadata attached to a method class."""

    since: str  # SemVer — when deprecated
    removal: str  # SemVer — when removed
    replacement: str | None  # FQN of replacement method
    reason: str  # Machine-readable reason code
    retired: bool = False  # If True, pure_step raises immediately
    recorded_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class MethodRetiredException(Exception):
    """Raised when a hard-deprecated (retired) method is called."""

    def __init__(self, fqn: str, info: DeprecationInfo) -> None:
        msg = (
            f"Method {fqn!r} has been retired since v{info.since} "
            f"and will be removed in v{info.removal}."
        )
        if info.replacement:
            msg += f" Use {info.replacement!r} instead."
        super().__init__(msg)
        self.fqn = fqn
        self.info = info


# ---------------------------------------------------------------------------
# @deprecate_method decorator
# ---------------------------------------------------------------------------


def deprecate_method(
    since: str,
    removal: str,
    *,
    replacement: str | None = None,
    reason: str = "Deprecated",
    retired: bool = False,
) -> Callable[[T], T]:
    """
    Class decorator that marks a Foundry method as deprecated.

    Parameters
    ----------
    since:
        SemVer string of the release that deprecated this method.
    removal:
        SemVer string of the planned removal release.
    replacement:
        FQN of the preferred replacement method.
    reason:
        Short machine-readable reason string (e.g. ``"SupersededBy"``).
    retired:
        If True, ``pure_step`` immediately raises ``MethodRetiredException``
        rather than just emitting a warning.

    Notes
    -----
    Apply *after* ``@foundry_method`` so it wraps the final class.
    The decorator attaches a ``__deprecation__`` attribute and wraps
    ``pure_step`` in-place.
    """
    info = DeprecationInfo(
        since=since,
        removal=removal,
        replacement=replacement,
        reason=reason,
        retired=retired,
    )

    def _decorator(cls: T) -> T:
        # Attach deprecation info
        cls.__deprecation__ = info  # type: ignore[attr-defined]

        # Retrieve existing pure_step
        pure_step_attr = getattr(cls, "pure_step", None)
        if pure_step_attr is None:
            return cls

        fqn_str = getattr(getattr(cls, "signature", None), "fqn", cls.__name__)

        if retired:

            @staticmethod  # type: ignore[misc]
            def _retired_pure_step(state: Any, params: Any) -> Any:
                raise MethodRetiredException(fqn_str, info)

            cls.pure_step = _retired_pure_step  # type: ignore[method-assign]
        else:
            original_step = (
                pure_step_attr if callable(pure_step_attr) else staticmethod(pure_step_attr)
            )

            @staticmethod  # type: ignore[misc]
            def _deprecated_pure_step(state: Any, params: Any) -> Any:
                msg = (
                    f"Method {fqn_str!r} is deprecated since v{info.since} "
                    f"and will be removed in v{info.removal}."
                )
                if info.replacement:
                    msg += f" Migrate to {info.replacement!r}."
                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                return original_step(state, params)  # type: ignore[operator]

            cls.pure_step = _deprecated_pure_step  # type: ignore[method-assign]

        # Add deprecation tags to metadata if present
        meta = getattr(cls, "metadata", None)
        if meta is not None and hasattr(meta, "tags"):
            extra = frozenset(
                {
                    f"deprecated:{since}",
                    f"removal:{removal}",
                }
            )
            try:
                object.__setattr__(meta, "tags", meta.tags | extra)  # type: ignore[arg-type]
            except (AttributeError, TypeError):
                pass  # frozen dataclass or immutable — best effort

        return cls

    return _decorator


# ---------------------------------------------------------------------------
# Registry tagging helper
# ---------------------------------------------------------------------------


def tag_deprecated_in_registry(
    fqn: str,
    since: str,
    removal: str,
    registry: Any | None = None,
) -> bool:
    """
    Add deprecation tags to a method's metadata in the live registry.

    Tags added: ``"deprecated:X.Y.Z"`` and ``"removal:X.Y.Z"``.

    Returns True if the method was found and updated, False otherwise.
    """
    from polisyos.foundry.methods.registry import get_registry

    reg = registry or get_registry()
    entry = reg.get_entry(fqn)
    if entry is None:
        return False

    extra = frozenset({f"deprecated:{since}", f"removal:{removal}"})
    meta = entry.metadata
    try:
        object.__setattr__(meta, "tags", meta.tags | extra)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# DeprecationAudit
# ---------------------------------------------------------------------------


@dataclass
class DeprecationAuditEntry:
    """Single entry in a deprecation audit."""

    fqn: str
    since: str
    removal: str
    replacement: str | None
    reason: str
    retired: bool
    tags_match: bool  # True if registry tags include "deprecated:*"


@dataclass
class DeprecationAuditReport:
    """Full deprecation audit report."""

    generated_at: str
    entries: list[DeprecationAuditEntry] = field(default_factory=list)

    @property
    def deprecated(self) -> list[DeprecationAuditEntry]:
        return [e for e in self.entries if not e.retired]

    @property
    def retired(self) -> list[DeprecationAuditEntry]:
        return [e for e in self.entries if e.retired]

    def print(self) -> None:
        print(f"\nDeprecation Audit  (generated: {self.generated_at})")
        print(f"  Deprecated:  {len(self.deprecated)}")
        print(f"  Retired:     {len(self.retired)}")
        if self.entries:
            print("\n  FQN                                          since   removal  replacement")
            print("  " + "-" * 75)
            for e in sorted(self.entries, key=lambda x: x.since):
                status = "[RETIRED]" if e.retired else "[deprecated]"
                repl = e.replacement or "-"
                print(f"  {e.fqn:<44} {e.since:<7} {e.removal:<8} {repl}  {status}")
        else:
            print("  No deprecated methods found.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "n_deprecated": len(self.deprecated),
            "n_retired": len(self.retired),
            "entries": [
                {
                    "fqn": e.fqn,
                    "since": e.since,
                    "removal": e.removal,
                    "replacement": e.replacement,
                    "reason": e.reason,
                    "retired": e.retired,
                }
                for e in self.entries
            ],
        }


class DeprecationAudit:
    """
    Scans the registry (or a list of classes) for deprecated methods.

    Usage
    -----
    ::

        audit = DeprecationAudit()
        report = audit.report()
        report.print()
    """

    def report(self, registry: Any | None = None) -> DeprecationAuditReport:
        """Build a ``DeprecationAuditReport`` from the live registry."""
        from polisyos.foundry.methods.registry import get_registry

        reg = registry or get_registry()
        entries: list[DeprecationAuditEntry] = []

        for reg_entry in reg.list_all():
            try:
                method_class = reg.get(reg_entry.fqn)
            except Exception:
                continue

            dep_info = getattr(method_class, "__deprecation__", None)
            if dep_info is None:
                continue

            tags = set(getattr(getattr(method_class, "metadata", None), "tags", set()))
            tags_match = any(t.startswith("deprecated:") for t in tags)

            entries.append(
                DeprecationAuditEntry(
                    fqn=reg_entry.fqn,
                    since=dep_info.since,
                    removal=dep_info.removal,
                    replacement=dep_info.replacement,
                    reason=dep_info.reason,
                    retired=dep_info.retired,
                    tags_match=tags_match,
                )
            )

        return DeprecationAuditReport(
            generated_at=datetime.now(UTC).isoformat(),
            entries=entries,
        )

    def report_from_classes(self, method_classes: list[type]) -> DeprecationAuditReport:
        """Build a report from an explicit list of classes (no registry needed)."""
        entries: list[DeprecationAuditEntry] = []
        for cls in method_classes:
            dep_info = getattr(cls, "__deprecation__", None)
            if dep_info is None:
                continue
            fqn = getattr(getattr(cls, "signature", None), "fqn", cls.__name__)
            entries.append(
                DeprecationAuditEntry(
                    fqn=fqn,
                    since=dep_info.since,
                    removal=dep_info.removal,
                    replacement=dep_info.replacement,
                    reason=dep_info.reason,
                    retired=dep_info.retired,
                    tags_match=False,
                )
            )
        return DeprecationAuditReport(
            generated_at=datetime.now(UTC).isoformat(),
            entries=entries,
        )
