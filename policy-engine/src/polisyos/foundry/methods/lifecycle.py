"""
MethodLifecycle — Formal state machine for Foundry method entries.

Every MethodEntry tracked by the registry moves through a well-defined
sequence of states:

    DEFINED → REGISTERED → VALIDATED → WARM → EXECUTING → RETIRED

Transitions are recorded in a per-entry LifecycleLog so that diagnostics,
auditing, and observability tooling can reconstruct the full history of any
method.

Architecture notes
------------------
- ``LifecycleManager`` is a lightweight, stateless helper that operates on
  ``MethodEntry`` objects.  It does NOT own any global state.
- Thread safety is the responsibility of the caller (usually ``MethodRegistry``
  which already holds ``_reg_lock`` during mutations).
- All timestamps are ``time.monotonic()`` for monotonicity guarantees within a
  process; wall-clock times are NOT used so that serialised logs remain
  consistent across machines.
"""
from __future__ import annotations

import enum
import inspect
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from polisyos.foundry.methods.exceptions import FoundryExecutionError

if TYPE_CHECKING:
    pass  # forward references only

__all__ = [
    "MethodLifecycle",
    "LifecycleEvent",
    "LifecycleLog",
    "LifecycleManager",
    "LifecycleTransitionError",
]

# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------

# Maps from_state → set of allowed to_states
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "defined":    {"registered"},
    "registered": {"validated", "retired"},
    "validated":  {"warm", "executing", "retired"},
    "warm":       {"executing", "retired"},
    "executing":  {"warm", "validated", "retired"},
    "retired":    set(),  # terminal
}


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class MethodLifecycle(enum.Enum):
    """
    States in the Foundry method lifecycle.

    DEFINED
        Class exists in Python, ``@foundry_method`` decorator has run, but
        the method has not yet been registered in any ``MethodRegistry``.

    REGISTERED
        The method has been added to a ``MethodRegistry`` (FQN is known).
        ABI has been checked structurally but full semantic validation
        (slot schema, parameter bounds cross-check, etc.) may be deferred.

    VALIDATED
        Full semantic validation has passed: slot schemas match the global
        ``SLOT_SCHEMA_REGISTRY``, parameter bounds are consistent, any
        required optional deps were found.  The method is ready to run.

    WARM
        The method has been JIT-compiled by the ``MethodCompiler`` and the
        compiled artefact is in the compilation cache.  Subsequent calls
        will skip compilation overhead.

    EXECUTING
        A ``pure_step`` call is in flight.  This state is transient; the
        entry returns to ``WARM`` (or ``VALIDATED`` if the cache was
        evicted) after completion.

    RETIRED
        The method has been deprecated and its sunset date has passed, *or*
        it was explicitly unregistered.  No new calls should be dispatched
        to it.  Existing in-flight calls may still complete.
    """

    DEFINED    = "defined"
    REGISTERED = "registered"
    VALIDATED  = "validated"
    WARM       = "warm"
    EXECUTING  = "executing"
    RETIRED    = "retired"


@dataclass(frozen=True)
class LifecycleEvent:
    """
    Immutable record of a single lifecycle state transition.

    Attributes
    ----------
    fqn:
        Fully-qualified name of the method that transitioned.
    from_state:
        State before the transition.
    to_state:
        State after the transition.
    timestamp:
        ``time.monotonic()`` at the moment of the transition.
    actor:
        Human-readable description of what triggered the transition, e.g.
        ``"registry.register:registry.py:305"`` or ``"jit_compiler"``.
    """

    fqn: str
    from_state: MethodLifecycle
    to_state: MethodLifecycle
    timestamp: float
    actor: str


class LifecycleLog:
    """
    Per-entry ordered log of lifecycle events.

    Designed to be stored inside ``MethodEntry`` (or alongside it).
    Operations are O(1) append and O(n) iteration — suitable for
    diagnostic tooling, not hot paths.
    """

    __slots__ = ("_events",)

    def __init__(self) -> None:
        self._events: list[LifecycleEvent] = []

    def append(self, event: LifecycleEvent) -> None:
        self._events.append(event)

    def history(self) -> list[LifecycleEvent]:
        """Return a copy of all events in chronological order."""
        return list(self._events)

    def current_state(self) -> MethodLifecycle | None:
        """Return the most recent state, or None if no events have been recorded."""
        if not self._events:
            return None
        return self._events[-1].to_state

    def __len__(self) -> int:
        return len(self._events)

    def __repr__(self) -> str:
        state = self.current_state()
        return f"<LifecycleLog state={state.value if state else 'none'} events={len(self._events)}>"


class LifecycleTransitionError(FoundryExecutionError):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, fqn: str, from_state: MethodLifecycle, to_state: MethodLifecycle) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(from_state.value, set())
        message = (
            f"Illegal lifecycle transition for '{fqn}': "
            f"{from_state.value!r} -> {to_state.value!r}. "
            f"Allowed from {from_state.value!r}: {sorted(allowed) or 'none (terminal)'}"
        )
        super().__init__(
            message,
            method_fqn=fqn,
            code="invalid_lifecycle_transition",
            details={
                "from_state": from_state.value,
                "to_state": to_state.value,
                "allowed": sorted(allowed),
            },
        )
        self.fqn = fqn
        self.from_state = from_state
        self.to_state = to_state


# ---------------------------------------------------------------------------
# LifecycleManager
# ---------------------------------------------------------------------------


class LifecycleManager:
    """
    Stateless helper for managing ``MethodEntry`` lifecycle transitions.

    The manager validates transitions, records events in the entry's
    ``LifecycleLog``, and emits structured log messages via the standard
    ``logging`` module.

    Usage
    -----
    Typical call sites:

    * ``MethodRegistry.register()`` calls ``transition(entry, REGISTERED)``
    * ``MethodRegistry._load_entry()`` calls ``transition(entry, VALIDATED)``
      after full semantic validation
    * ``MethodCompiler`` calls ``transition(entry, WARM)``
    * ``MethodDispatcher.dispatch()`` calls ``transition(entry, EXECUTING)``
      before and ``transition(entry, WARM)`` after
    * ``MethodRegistry.unregister()`` calls ``transition(entry, RETIRED)``

    Thread Safety
    -------------
    Callers are responsible for holding appropriate locks before calling
    ``transition()``.  The manager itself is stateless and lock-free.
    """

    @staticmethod
    def transition(
        log: LifecycleLog,
        fqn: str,
        to: MethodLifecycle,
        *,
        actor: str | None = None,
        strict: bool = True,
    ) -> LifecycleEvent:
        """
        Record a lifecycle state transition.

        Parameters
        ----------
        log:
            The ``LifecycleLog`` attached to the method entry.
        fqn:
            Fully-qualified name of the method (for error messages & events).
        to:
            Target state.
        actor:
            Optional description of what is triggering the transition.
            If None, the calling function/module is inferred via ``inspect``.
        strict:
            Retained for API compatibility. Illegal transitions now always
            raise ``LifecycleTransitionError``; when ``strict=False`` the
            invalid attempt is also recorded in the log before raising.

        Returns
        -------
        LifecycleEvent
            The recorded event.

        Raises
        ------
        LifecycleTransitionError
            If the transition is not permitted.
        """
        current = log.current_state()

        # First transition from None → DEFINED is always allowed
        if current is None:
            if to != MethodLifecycle.DEFINED and strict:
                raise LifecycleTransitionError(fqn, MethodLifecycle.DEFINED, to)
            # Treat as if coming from DEFINED for the first recorded event
            from_state = MethodLifecycle.DEFINED
        else:
            from_state = current
            allowed = _ALLOWED_TRANSITIONS.get(from_state.value, set())
            if to.value not in allowed:
                invalid_event = LifecycleEvent(
                    fqn=fqn,
                    from_state=from_state,
                    to_state=from_state,  # no change
                    timestamp=time.monotonic(),
                    actor=(actor or _infer_actor()) + f"[invalid:{to.value}]",
                )
                log.append(invalid_event)
                raise LifecycleTransitionError(fqn, from_state, to)

        if actor is None:
            actor = _infer_actor()

        event = LifecycleEvent(
            fqn=fqn,
            from_state=from_state,
            to_state=to,
            timestamp=time.monotonic(),
            actor=actor,
        )
        log.append(event)
        return event

    @staticmethod
    def ensure_state(
        log: LifecycleLog,
        fqn: str,
        expected: MethodLifecycle,
    ) -> None:
        """
        Assert that *log* is in *expected* state, raising if not.

        Useful for pre-condition checks in method dispatch.
        """
        current = log.current_state()
        if current != expected:
            raise LifecycleTransitionError(fqn, current or MethodLifecycle.DEFINED, expected)

    @staticmethod
    def is_runnable(log: LifecycleLog) -> bool:
        """
        Return True if the method is in a state where ``pure_step`` can be called.

        States ``VALIDATED``, ``WARM``, and ``EXECUTING`` are considered runnable.
        ``RETIRED`` and ``DEFINED``/``REGISTERED`` are not.
        """
        current = log.current_state()
        if current is None:
            return False
        return current in {
            MethodLifecycle.VALIDATED,
            MethodLifecycle.WARM,
            MethodLifecycle.EXECUTING,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_actor() -> str:
    """
    Build a short actor string from the call stack, skipping internal frames.
    """
    for frame_info in inspect.stack()[2:]:
        module = frame_info.frame.f_globals.get("__name__", "")
        if not module.startswith("polisyos.foundry.methods.lifecycle"):
            return f"{frame_info.function}:{frame_info.filename.rsplit('/', 1)[-1]}:{frame_info.lineno}"
    return "unknown"
