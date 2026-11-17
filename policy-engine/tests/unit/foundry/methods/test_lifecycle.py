"""Focused tests for method lifecycle diagnostics."""

from __future__ import annotations

import inspect
import types
from collections.abc import Callable
from typing import cast

import pytest

from polisyos.foundry.methods import lifecycle
from polisyos.foundry.methods.lifecycle import (
    LifecycleEvent,
    LifecycleLog,
    LifecycleManager,
    MethodLifecycle,
)


def _external_transition(log: LifecycleLog) -> tuple[LifecycleEvent, int]:
    """Make one inferred transition from a stable external call site."""
    frame = inspect.currentframe()
    assert frame is not None
    call_line = frame.f_lineno + 1
    event = LifecycleManager.transition(log, "tests.method@1.0.0", MethodLifecycle.DEFINED)
    return event, call_line


def _forbid_full_stack_inspection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail if actor inference materializes or inspects source frames."""

    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("full_stack_or_source_inspection_used")

    for name in (
        "stack",
        "getframeinfo",
        "getouterframes",
        "getsource",
        "getsourcelines",
        "findsource",
    ):
        monkeypatch.setattr(lifecycle.inspect, name, fail)


def test_inferred_actor_preserves_external_callsite_without_stack_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forbid_full_stack_inspection(monkeypatch)

    event, call_line = _external_transition(LifecycleLog())

    assert event.actor == f"_external_transition:{__file__.rsplit('/', 1)[-1]}:{call_line}"


def test_inferred_actor_skips_nested_lifecycle_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_full_stack_inspection(monkeypatch)
    namespace: dict[str, object] = {
        "__name__": "polisyos.foundry.methods.lifecycle.test_wrapper",
        "LifecycleManager": LifecycleManager,
        "MethodLifecycle": MethodLifecycle,
    }

    def transition_template(log: LifecycleLog) -> LifecycleEvent:
        return LifecycleManager.transition(log, "tests.method@1.0.0", MethodLifecycle.DEFINED)

    transition_from_lifecycle = cast(
        "Callable[[LifecycleLog], LifecycleEvent]",
        types.FunctionType(
            transition_template.__code__, namespace, name="transition_from_lifecycle"
        ),
    )

    log = LifecycleLog()
    frame = inspect.currentframe()
    assert frame is not None
    call_line = frame.f_lineno + 1
    event = transition_from_lifecycle(log)

    assert (
        event.actor
        == f"test_inferred_actor_skips_nested_lifecycle_frames:{__file__.rsplit('/', 1)[-1]}:{call_line}"
    )


def test_explicit_actor_is_preserved() -> None:
    event = LifecycleManager.transition(
        LifecycleLog(),
        "tests.method@1.0.0",
        MethodLifecycle.DEFINED,
        actor="explicit-owner",
    )

    assert event.actor == "explicit-owner"


def test_missing_current_frame_uses_unknown_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle.inspect, "currentframe", lambda: None)

    event = LifecycleManager.transition(
        LifecycleLog(), "tests.method@1.0.0", MethodLifecycle.DEFINED
    )

    assert event.actor == "unknown"
