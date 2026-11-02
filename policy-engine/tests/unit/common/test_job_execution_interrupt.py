"""Typed live-owner admission and compatibility for cooperative job signals."""

from __future__ import annotations

import asyncio
from threading import Event

import pytest

from polisyos.common.job_execution_interrupt import (
    JobExecutionInterrupt,
    JobExecutionInterrupted,
    JobExecutionOwnerNotEstablishedError,
    has_job_execution_owner_check,
    has_job_execution_scope,
    job_execution_interrupt_scope,
    raise_if_job_execution_interrupted,
    require_current_job_execution_owner,
)


def test_event_only_positional_signal_does_not_claim_live_owner() -> None:
    signal = JobExecutionInterrupt("job", "worker", 1, Event())
    with job_execution_interrupt_scope(signal):
        raise_if_job_execution_interrupted(check_current_owner=True)
        with pytest.raises(JobExecutionOwnerNotEstablishedError):
            require_current_job_execution_owner("job")
        signal.lost.set()
        with pytest.raises(JobExecutionInterrupted):
            raise_if_job_execution_interrupted()


def test_missing_or_wrong_job_refuses_without_calling_another_owner() -> None:
    checks = []
    with pytest.raises(JobExecutionOwnerNotEstablishedError):
        require_current_job_execution_owner("job")
    signal = JobExecutionInterrupt(
        "job", "worker", 1, Event(), current_owner_check=lambda: checks.append("checked")
    )
    with job_execution_interrupt_scope(signal), pytest.raises(JobExecutionOwnerNotEstablishedError):
        require_current_job_execution_owner("other-job")
    assert checks == []


def test_polling_is_event_only_and_dispatch_rechecks_the_owner() -> None:
    checks = []
    signal = JobExecutionInterrupt(
        "job", "worker", 1, Event(), current_owner_check=lambda: checks.append("checked")
    )
    with job_execution_interrupt_scope(signal):
        for _ in range(10):
            raise_if_job_execution_interrupted()
        assert checks == []
        require_current_job_execution_owner("job")
        raise_if_job_execution_interrupted(check_current_owner=True)
    assert checks == ["checked", "checked"]


def test_current_owner_loss_prevents_the_producer_and_future_polls() -> None:
    lost = Event()
    produced = []

    def no_longer_current() -> None:
        lost.set()
        raise JobExecutionInterrupted("actual owner refused")

    signal = JobExecutionInterrupt("job", "worker", 1, lost, current_owner_check=no_longer_current)

    def produce() -> None:
        require_current_job_execution_owner("job")
        produced.append("effect")

    with job_execution_interrupt_scope(signal):
        with pytest.raises(JobExecutionInterrupted):
            produce()
        with pytest.raises(JobExecutionInterrupted):
            raise_if_job_execution_interrupted()
    assert produced == [] and lost.is_set()


def test_live_owner_capability_survives_async_context_preserving_handoff() -> None:
    checks = []
    signal = JobExecutionInterrupt(
        "job", "worker", 1, Event(), current_owner_check=lambda: checks.append("checked")
    )

    async def check_in_async_and_thread() -> None:
        require_current_job_execution_owner("job")
        await asyncio.to_thread(require_current_job_execution_owner, "job")

    with job_execution_interrupt_scope(signal):
        asyncio.run(check_in_async_and_thread())
    assert checks == ["checked", "checked"]
    with pytest.raises(JobExecutionOwnerNotEstablishedError):
        require_current_job_execution_owner("job")


def test_lost_signal_never_consults_or_replaces_the_current_owner() -> None:
    checks = []
    lost = Event()
    lost.set()
    signal = JobExecutionInterrupt(
        "job", "worker", 1, lost, current_owner_check=lambda: checks.append("checked")
    )
    with job_execution_interrupt_scope(signal), pytest.raises(JobExecutionInterrupted):
        require_current_job_execution_owner("job")
    assert checks == []


def test_unexpected_owner_lookup_error_cannot_become_a_retryable_node_error() -> None:
    error = OSError("lookup could not establish the owner")
    lost = Event()

    def unavailable() -> None:
        raise error

    signal = JobExecutionInterrupt("job", "worker", 1, lost, current_owner_check=unavailable)
    with job_execution_interrupt_scope(signal), pytest.raises(JobExecutionInterrupted) as caught:
        require_current_job_execution_owner("job")
    assert caught.value.__cause__ is error
    assert lost.is_set()


def test_owner_check_presence_restricts_transport_without_claiming_currentness() -> None:
    checks = []
    assert has_job_execution_owner_check() is False
    legacy = JobExecutionInterrupt("job", "worker", 1, Event())
    with job_execution_interrupt_scope(legacy):
        assert has_job_execution_owner_check() is False
    lost = Event()
    lost.set()
    signal = JobExecutionInterrupt(
        "job", "worker", 1, lost, current_owner_check=lambda: checks.append("checked")
    )
    with job_execution_interrupt_scope(signal):
        assert has_job_execution_owner_check() is True
        assert checks == []
        with pytest.raises(JobExecutionInterrupted):
            require_current_job_execution_owner("job")
    assert has_job_execution_owner_check() is False


@pytest.mark.parametrize("live_check", [False, True])
@pytest.mark.parametrize("already_lost", [False, True])
def test_scope_presence_includes_legacy_and_lost_attempt_without_owner_lookup(
    live_check: bool, already_lost: bool
) -> None:
    checks = []
    lost = Event()
    if already_lost:
        lost.set()
    signal = JobExecutionInterrupt(
        "job",
        "worker",
        1,
        lost,
        current_owner_check=(lambda: checks.append("checked")) if live_check else None,
    )
    assert has_job_execution_scope() is False
    with job_execution_interrupt_scope(signal):
        assert has_job_execution_scope() is True
        assert has_job_execution_owner_check() is live_check
        assert checks == [] and lost.is_set() is already_lost
    assert has_job_execution_scope() is False


def test_private_identity_requires_bound_owner_capability() -> None:
    from polisyos.common.job_execution_interrupt import _current_job_execution_identity

    assert _current_job_execution_identity() is None
    with job_execution_interrupt_scope(JobExecutionInterrupt("j", "w", 2, Event())):
        assert _current_job_execution_identity() is None
    signal = JobExecutionInterrupt("j", "w", 2, Event(), current_owner_check=lambda: None)
    with job_execution_interrupt_scope(signal):
        assert _current_job_execution_identity() is None
    signal = JobExecutionInterrupt(
        "j", "w", 2, Event(), run_id="r", current_owner_check=lambda: None
    )
    with job_execution_interrupt_scope(signal):
        assert _current_job_execution_identity() == ("j", "w", 2, "r")
