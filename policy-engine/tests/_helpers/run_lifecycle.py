"""Lifecycle-preserving helpers for cache recovery tests."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.run.context import RunContext


class ExpectedRunInterruption(BaseException):
    """Stop immediately before terminal publication to exercise explicit resume."""


def run_trace_events(run: RunContext) -> list[dict[str, object]]:
    """Read the append-only lifecycle trace currently owned by ``run``."""
    assert run.trace_path is not None
    return [
        json.loads(line)
        for line in run.trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _assert_interrupted(events: list[dict[str, object]], *, expected_resumes: int = 0) -> None:
    assert sum(event.get("event") == "RUN_STARTED" for event in events) == 1
    assert sum(event.get("event") == "RUN_RESUMED" for event in events) == expected_resumes
    assert sum(event.get("event") == "RUN_FINALIZED" for event in events) == 0


def interrupt_before_finalize(
    run: RunContext, execute: Callable[[], object], *, expected_resumes: int = 0
) -> list[dict[str, object]]:
    """Execute the real workflow, stopping only at its terminal publication boundary."""
    original_finalize = run.finalize
    attempts = 0

    def interrupt(*_args: object, **_kwargs: object) -> None:
        nonlocal attempts
        attempts += 1
        raise ExpectedRunInterruption

    run.finalize = interrupt
    try:
        try:
            execute()
        except ExpectedRunInterruption:
            pass
        else:
            raise AssertionError("workflow did not reach terminal publication")
    finally:
        run.finalize = original_finalize
    assert attempts == 1
    events = run_trace_events(run)
    _assert_interrupted(events, expected_resumes=expected_resumes)
    return events


async def interrupt_before_finalize_async(
    run: RunContext,
    execute: Callable[[], Awaitable[object]],
    *,
    expected_resumes: int = 0,
) -> list[dict[str, object]]:
    """Async counterpart that preserves executor cancellation and suspend behavior."""
    original_finalize = run.finalize
    attempts = 0

    def interrupt(*_args: object, **_kwargs: object) -> None:
        nonlocal attempts
        attempts += 1
        raise ExpectedRunInterruption

    run.finalize = interrupt
    try:
        try:
            await execute()
        except ExpectedRunInterruption:
            pass
        else:
            raise AssertionError("async workflow did not reach terminal publication")
    finally:
        run.finalize = original_finalize
    assert attempts == 1
    events = run_trace_events(run)
    _assert_interrupted(events, expected_resumes=expected_resumes)
    return events


def interrupt_and_suspend_before_finalize(
    run: RunContext, execute: Callable[[], object], *, expected_resumes: int = 0
) -> list[dict[str, object]]:
    """Leave one genuinely incomplete run paused after real workflow effects."""
    events = interrupt_before_finalize(run, execute, expected_resumes=expected_resumes)
    run.suspend_for_resume()
    assert run._suspended and run._active_lease is None
    return events


async def interrupt_and_suspend_before_finalize_async(
    run: RunContext,
    execute: Callable[[], Awaitable[object]],
    *,
    expected_resumes: int = 0,
) -> list[dict[str, object]]:
    """Async counterpart that explicitly releases the incomplete run for resume."""
    events = await interrupt_before_finalize_async(run, execute, expected_resumes=expected_resumes)
    run.suspend_for_resume()
    assert run._suspended and run._active_lease is None
    return events


def resume_same_run(store: FileSystemCAS, previous: RunContext) -> RunContext:
    """Resume the exact owner-bound incomplete run with its persisted inputs."""
    assert previous.trace_path is not None
    manifest = previous.run_manifest
    return RunContext.resume(
        store,
        run_id=manifest.run_id,
        run_dir=previous.trace_path.parent,
        registry_bundle=manifest.registry_bundle,
        producer=manifest.producer,
        env=manifest.env,
        access_scope=previous.access_scope,
    )


def start_or_resume_run(
    store: FileSystemCAS,
    *,
    run_id: str,
    registry_bundle: ArtifactRef | None = None,
    run_dir: Path | None = None,
    resume_from: RunContext | None = None,
    tenant_id: str | None = None,
    cell_id: str | None = None,
) -> RunContext:
    """Start a new owner or resume only its explicitly paused nonterminal lifecycle."""
    if resume_from is None:
        if registry_bundle is None:
            raise AssertionError("a new run requires its selected registry owner")
        return RunContext.start(
            store,
            registry_bundle,
            run_id=run_id,
            run_dir=run_dir,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    if registry_bundle is not None:
        raise AssertionError("resume must use the prior persisted registry owner")
    if resume_from.run_manifest.run_id != run_id:
        raise AssertionError("resume must keep the exact run identity")
    if resume_from.trace_path is None:
        raise AssertionError("resume requires the prior trace owner")
    if run_dir is not None and run_dir.resolve() != resume_from.trace_path.parent.resolve():
        raise AssertionError("resume must keep the exact run directory")
    if not resume_from._suspended or resume_from._active_lease is not None:
        raise AssertionError("resume requires an explicit nonterminal suspension")
    events = run_trace_events(resume_from)
    _assert_interrupted(
        events,
        expected_resumes=sum(event.get("event") == "RUN_RESUMED" for event in events),
    )
    return resume_same_run(store, resume_from)


def assert_one_resumed_terminal_lifecycle(
    run: RunContext, *, expected_resumes: int = 1
) -> list[dict[str, object]]:
    """Pin one start, the expected resumes, and one terminal event for this run ID."""
    events = run_trace_events(run)
    assert sum(event.get("event") == "RUN_STARTED" for event in events) == 1
    assert sum(event.get("event") == "RUN_RESUMED" for event in events) == expected_resumes
    assert sum(event.get("event") == "RUN_FINALIZED" for event in events) == 1
    return events
