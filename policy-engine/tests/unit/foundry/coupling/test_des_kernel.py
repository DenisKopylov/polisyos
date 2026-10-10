from __future__ import annotations

import jax
import numpy as np

from polisyos.foundry.contracts.state import QueueRuntimeState
from polisyos.foundry.coupling.des_kernel import (
    STATUS_COMPLETED,
    STATUS_IN_SERVICE,
    STATUS_QUEUED,
    STATUS_REJECTED,
    QueueDESKernel,
)
from polisyos.foundry.coupling.messages import (
    KIND_CLAIM_ARRIVAL,
    KIND_QUEUE_REJECT,
    KIND_SERVICE_COMPLETE,
    KIND_SERVICE_START,
    SOURCE_ABM,
    TARGET_DES,
    CouplingMessage,
)


def _claim(slot: int, priority: int) -> CouplingMessage:
    return CouplingMessage(
        time=0.0,
        source=SOURCE_ABM,
        target=TARGET_DES,
        kind=KIND_CLAIM_ARRIVAL,
        entity_id=f"agent-{slot}",
        priority=priority,
    )


def test_queue_des_admits_high_priority_first_under_capacity() -> None:
    state = QueueRuntimeState.empty(3, capacity=2)
    kernel = QueueDESKernel(service_rate=1.0, capacity=2, time_step=1.0)

    next_state, messages, _patches, metrics = kernel.advance_to(
        state,
        1.0,
        [_claim(0, 0), _claim(1, 5), _claim(2, 2)],
        jax.random.PRNGKey(0),
    )

    statuses = np.asarray(next_state.claim_status)
    assert statuses[1] == STATUS_IN_SERVICE
    assert statuses[2] == STATUS_QUEUED
    assert statuses[0] == STATUS_REJECTED
    assert float(np.asarray(next_state.queue_length).item()) == 2.0
    assert metrics["queue/rejected_count"] == 1
    assert metrics["queue/calendar_active"] == 3
    assert kernel.next_event_time(next_state) == 2.0
    assert any(
        message.kind == KIND_QUEUE_REJECT and message.entity_id == "agent-0" for message in messages
    )
    assert any(
        message.kind == KIND_SERVICE_START and message.entity_id == "agent-1"
        for message in messages
    )

    completed_state, messages, _patches, metrics = kernel.advance_to(
        next_state,
        2.0,
        [],
        jax.random.PRNGKey(1),
    )

    statuses = np.asarray(completed_state.claim_status)
    assert statuses[1] == STATUS_COMPLETED
    assert statuses[2] == STATUS_IN_SERVICE
    assert float(np.asarray(completed_state.queue_length).item()) == 1.0
    assert metrics["queue/calendar_events_processed"] == 2
    assert any(
        message.kind == KIND_SERVICE_COMPLETE and message.entity_id == "agent-1"
        for message in messages
    )


def test_queue_des_ignores_duplicate_claims_after_completion() -> None:
    state = QueueRuntimeState.empty(1)
    kernel = QueueDESKernel(service_rate=1.0, time_step=1.0)

    completed, _messages, _patches, _metrics = kernel.advance_to(
        state,
        1.0,
        [_claim(0, 1)],
        jax.random.PRNGKey(0),
    )
    repeated, _messages, _patches, metrics = kernel.advance_to(
        completed,
        2.0,
        [_claim(0, 1)],
        jax.random.PRNGKey(1),
    )

    assert np.asarray(repeated.claim_status).tolist() == [STATUS_COMPLETED]
    assert metrics["queue/admitted_count"] == 1
    assert metrics["queue/completed_count"] == 1
