"""Queue-backed DES kernel for coupled policy simulations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.contracts.mechanism import PatchMap
from polisyos.foundry.contracts.state import (
    GlobalState,
    QueueEventCalendarState,
    QueueRuntimeState,
)
from polisyos.foundry.coupling.messages import (
    ARRIVAL_KINDS,
    KIND_QUEUE_ADMIT,
    KIND_QUEUE_REJECT,
    KIND_SERVICE_COMPLETE,
    KIND_SERVICE_START,
    SOURCE_DES,
    TARGET_ABM,
    CouplingMessage,
    entity_index,
)

STATUS_NONE = 0
STATUS_QUEUED = 1
STATUS_IN_SERVICE = 2
STATUS_COMPLETED = 3
STATUS_REJECTED = 4

EVENT_NONE = 0
EVENT_SERVICE_START = 1
EVENT_SERVICE_COMPLETE = 2


def ensure_queue_runtime(
    state: GlobalState,
    *,
    capacity: float | None = None,
    queue_length: float = 0.0,
) -> GlobalState:
    """Attach an empty queue runtime block when the canonical state lacks one."""
    if state.queue_runtime is not None:
        return state
    return state.replace(
        queue_runtime=QueueRuntimeState.empty(
            state.agents.size,
            capacity=capacity,
            queue_length=queue_length,
        )
    )


def _as_float(value: Any) -> float:
    return float(np.asarray(value).item())


def _as_int(value: Any) -> int:
    return int(np.asarray(value).item())


def _capacity_from_state(state_q: QueueRuntimeState, override: float | None) -> float | None:
    if override is not None:
        return float(override)
    state_capacity = _as_float(state_q.capacity)
    return None if state_capacity < 0 else state_capacity


def _queue_sort_key(message: CouplingMessage) -> tuple[float, int, str, str]:
    entity = "" if message.entity_id is None else str(message.entity_id)
    return (float(message.time), -int(message.priority), str(message.kind), entity)


def _calendar_next_time(calendar: QueueEventCalendarState) -> float:
    active = np.asarray(calendar.event_active, dtype=bool)
    if not np.any(active):
        return float("inf")
    times = np.asarray(calendar.event_time, dtype=np.float32)
    return float(np.min(times[active]))


def _event_sort_key(
    idx: int,
    event_time: np.ndarray,
    event_kind: np.ndarray,
    event_entity: np.ndarray,
    event_priority: np.ndarray,
) -> tuple[float, int, int, int]:
    kind = int(event_kind[idx])
    kind_order = 0 if kind == EVENT_SERVICE_COMPLETE else 1
    return (
        float(event_time[idx]),
        kind_order,
        -int(event_priority[idx]),
        int(event_entity[idx]),
    )


def _calendar_arrays(
    calendar: QueueEventCalendarState,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.asarray(calendar.event_time, dtype=np.float32).copy(),
        np.asarray(calendar.event_kind, dtype=np.int32).copy(),
        np.asarray(calendar.event_entity, dtype=np.int32).copy(),
        np.asarray(calendar.event_priority, dtype=np.int32).copy(),
        np.asarray(calendar.event_active, dtype=bool).copy(),
    )


def _calendar_from_arrays(
    event_time: np.ndarray,
    event_kind: np.ndarray,
    event_entity: np.ndarray,
    event_priority: np.ndarray,
    event_active: np.ndarray,
) -> QueueEventCalendarState:
    return QueueEventCalendarState(
        event_time=jnp.asarray(event_time, dtype=jnp.float32),
        event_kind=jnp.asarray(event_kind, dtype=jnp.int32),
        event_entity=jnp.asarray(event_entity, dtype=jnp.int32),
        event_priority=jnp.asarray(event_priority, dtype=jnp.int32),
        event_active=jnp.asarray(event_active, dtype=jnp.bool_),
    )


@dataclass(frozen=True)
class QueueDESKernel:
    """Deterministic queue DES kernel with typed per-agent lifecycle messages.

    The kernel is deliberately conservative: ABM may emit arrivals or claim
    intents, but only this DES layer admits, rejects, and completes service.
    """

    service_rate: float = 1.0
    capacity: float | None = None
    time_step: float = 1.0
    default_priority: int = 0

    def next_event_time(self, state_q: QueueRuntimeState) -> float:
        calendar_time = _calendar_next_time(state_q.event_calendar)
        if np.isfinite(calendar_time):
            return calendar_time
        step = max(float(self.time_step), 1e-9)
        return _as_float(state_q.time) + step

    def advance_to(
        self,
        state_q: QueueRuntimeState,
        t: float,
        inbox: list[CouplingMessage] | tuple[CouplingMessage, ...],
        rng: jax.Array,
    ) -> tuple[QueueRuntimeState, list[CouplingMessage], PatchMap, dict[str, Any]]:
        del rng
        current_time = _as_float(state_q.time)
        target_time = float(t)
        if target_time < current_time - 1e-9:
            raise ValueError("DES kernel cannot advance to a timestamp in the past")

        status = np.asarray(state_q.claim_status, dtype=np.int32).copy()
        priority = np.asarray(state_q.claim_priority, dtype=np.int32).copy()
        queued_at = np.asarray(state_q.queued_at, dtype=np.float32).copy()
        service_started_at = np.asarray(state_q.service_started_at, dtype=np.float32).copy()
        completed_at = np.asarray(state_q.completed_at, dtype=np.float32).copy()
        expected_wait = np.asarray(state_q.expected_wait, dtype=np.float32).copy()
        event_time, event_kind, event_entity, event_priority, event_active = _calendar_arrays(
            state_q.event_calendar
        )

        queue_length = max(_as_float(state_q.queue_length), 0.0)
        admitted = _as_int(state_q.admitted_count)
        completed = _as_int(state_q.completed_count)
        rejected = _as_int(state_q.rejected_count)
        capacity = _capacity_from_state(state_q, self.capacity)
        messages: list[CouplingMessage] = []
        calendar_overflow = 0

        queue_length, completed, events_processed = self._process_due_events(
            target_time=target_time,
            status=status,
            priority=priority,
            queued_at=queued_at,
            service_started_at=service_started_at,
            completed_at=completed_at,
            event_time=event_time,
            event_kind=event_kind,
            event_entity=event_entity,
            event_priority=event_priority,
            event_active=event_active,
            queue_length=queue_length,
            completed=completed,
            messages=messages,
        )

        for message in sorted(inbox, key=_queue_sort_key):
            if message.kind not in ARRIVAL_KINDS:
                continue
            slot = entity_index(message.entity_id)
            if slot is not None and (slot < 0 or slot >= status.shape[0]):
                rejected += 1
                messages.append(
                    self._outcome_message(
                        message,
                        target_time,
                        KIND_QUEUE_REJECT,
                        {"reason": "entity_out_of_range", "queue_length": queue_length},
                    )
                )
                continue
            if slot is not None and status[slot] in {
                STATUS_QUEUED,
                STATUS_IN_SERVICE,
                STATUS_COMPLETED,
                STATUS_REJECTED,
            }:
                continue
            if capacity is not None and queue_length >= capacity:
                rejected += 1
                if slot is not None:
                    status[slot] = STATUS_REJECTED
                    expected_wait[slot] = queue_length / max(float(self.service_rate), 1e-9)
                messages.append(
                    self._outcome_message(
                        message,
                        target_time,
                        KIND_QUEUE_REJECT,
                        {"reason": "capacity", "queue_length": queue_length},
                    )
                )
                continue

            if slot is not None:
                status[slot] = STATUS_QUEUED
                priority[slot] = int(message.payload.get("priority", message.priority))
                queued_at[slot] = target_time
                expected_wait[slot] = queue_length / max(float(self.service_rate), 1e-9)
            admitted += 1
            queue_length += 1.0
            messages.append(
                self._outcome_message(
                    message,
                    target_time,
                    KIND_QUEUE_ADMIT,
                    {
                        "queue_length": queue_length,
                        "expected_wait": queue_length / max(float(self.service_rate), 1e-9),
                    },
                )
            )

        calendar_overflow += self._schedule_service_events(
            target_time=target_time,
            status=status,
            priority=priority,
            queued_at=queued_at,
            expected_wait=expected_wait,
            event_time=event_time,
            event_kind=event_kind,
            event_entity=event_entity,
            event_priority=event_priority,
            event_active=event_active,
        )
        queue_length, completed, processed = self._process_due_events(
            target_time=target_time,
            status=status,
            priority=priority,
            queued_at=queued_at,
            service_started_at=service_started_at,
            completed_at=completed_at,
            event_time=event_time,
            event_kind=event_kind,
            event_entity=event_entity,
            event_priority=event_priority,
            event_active=event_active,
            queue_length=queue_length,
            completed=completed,
            messages=messages,
        )
        events_processed += processed

        new_state = state_q.replace(
            time=jnp.asarray(target_time, dtype=jnp.float32),
            queue_length=jnp.asarray(queue_length, dtype=jnp.float32),
            capacity=jnp.asarray(-1.0 if capacity is None else capacity, dtype=jnp.float32),
            claim_status=jnp.asarray(status, dtype=jnp.int32),
            claim_priority=jnp.asarray(priority, dtype=jnp.int32),
            queued_at=jnp.asarray(queued_at, dtype=jnp.float32),
            service_started_at=jnp.asarray(service_started_at, dtype=jnp.float32),
            completed_at=jnp.asarray(completed_at, dtype=jnp.float32),
            expected_wait=jnp.asarray(expected_wait, dtype=jnp.float32),
            admitted_count=jnp.asarray(admitted, dtype=jnp.int32),
            completed_count=jnp.asarray(completed, dtype=jnp.int32),
            rejected_count=jnp.asarray(rejected, dtype=jnp.int32),
            last_update_step=state_q.last_update_step + 1,
            event_calendar=_calendar_from_arrays(
                event_time,
                event_kind,
                event_entity,
                event_priority,
                event_active,
            ),
        )
        metrics = {
            "queue/time": target_time,
            "queue/queue_length": queue_length,
            "queue/admitted_count": admitted,
            "queue/completed_count": completed,
            "queue/rejected_count": rejected,
            "queue/messages_emitted": len(messages),
            "queue/calendar_active": int(np.sum(event_active)),
            "queue/calendar_events_processed": events_processed,
            "queue/calendar_overflow": calendar_overflow,
        }
        return new_state, messages, {}, metrics

    def _process_due_events(
        self,
        *,
        target_time: float,
        status: np.ndarray,
        priority: np.ndarray,
        queued_at: np.ndarray,
        service_started_at: np.ndarray,
        completed_at: np.ndarray,
        event_time: np.ndarray,
        event_kind: np.ndarray,
        event_entity: np.ndarray,
        event_priority: np.ndarray,
        event_active: np.ndarray,
        queue_length: float,
        completed: int,
        messages: list[CouplingMessage],
    ) -> tuple[float, int, int]:
        due_indices = np.flatnonzero(event_active & (event_time <= target_time + 1e-9))
        due_indices = sorted(
            (int(idx) for idx in due_indices),
            key=lambda idx: _event_sort_key(
                idx,
                event_time,
                event_kind,
                event_entity,
                event_priority,
            ),
        )
        events_processed = 0
        service_time = 1.0 / max(float(self.service_rate), 1e-9)
        for event_idx in due_indices:
            if not event_active[event_idx]:
                continue
            kind = int(event_kind[event_idx])
            slot = int(event_entity[event_idx])
            event_timestamp = float(event_time[event_idx])
            event_active[event_idx] = False
            event_time[event_idx] = np.inf
            event_kind[event_idx] = EVENT_NONE
            event_entity[event_idx] = -1
            event_priority[event_idx] = 0
            if slot < 0 or slot >= status.shape[0]:
                continue
            if kind == EVENT_SERVICE_START:
                if status[slot] != STATUS_QUEUED:
                    continue
                status[slot] = STATUS_IN_SERVICE
                service_started_at[slot] = event_timestamp
                wait_time = max(event_timestamp - float(queued_at[slot]), 0.0)
                messages.append(
                    CouplingMessage(
                        time=event_timestamp,
                        source=SOURCE_DES,
                        target=TARGET_ABM,
                        kind=KIND_SERVICE_START,
                        entity_id=f"agent-{slot}",
                        priority=priority[slot],
                        causal_parent=f"queue-calendar-start-{slot}-{event_timestamp:g}",
                        payload={"wait_time": wait_time, "queue_length": queue_length},
                    )
                )
                events_processed += 1
                continue
            if kind != EVENT_SERVICE_COMPLETE:
                continue
            if status[slot] not in {STATUS_QUEUED, STATUS_IN_SERVICE}:
                continue
            if service_started_at[slot] < 0.0:
                service_started_at[slot] = max(
                    float(queued_at[slot]), event_timestamp - service_time
                )
            status[slot] = STATUS_COMPLETED
            completed_at[slot] = event_timestamp
            queue_length = max(queue_length - 1.0, 0.0)
            completed += 1
            events_processed += 1
            wait_time = max(event_timestamp - float(queued_at[slot]), 0.0)
            messages.append(
                CouplingMessage(
                    time=event_timestamp,
                    source=SOURCE_DES,
                    target=TARGET_ABM,
                    kind=KIND_SERVICE_COMPLETE,
                    entity_id=f"agent-{slot}",
                    priority=priority[slot],
                    causal_parent=f"queue-calendar-complete-{slot}-{event_timestamp:g}",
                    payload={"wait_time": wait_time, "queue_length": queue_length},
                )
            )
        return queue_length, completed, events_processed

    def _schedule_service_events(
        self,
        *,
        target_time: float,
        status: np.ndarray,
        priority: np.ndarray,
        queued_at: np.ndarray,
        expected_wait: np.ndarray,
        event_time: np.ndarray,
        event_kind: np.ndarray,
        event_entity: np.ndarray,
        event_priority: np.ndarray,
        event_active: np.ndarray,
    ) -> int:
        service_rate = max(float(self.service_rate), 1e-9)
        service_time = 1.0 / service_rate
        scheduled = {
            int(entity)
            for entity, kind, active in zip(event_entity, event_kind, event_active, strict=False)
            if bool(active)
            and int(kind) in {EVENT_SERVICE_START, EVENT_SERVICE_COMPLETE}
            and int(entity) >= 0
        }
        waiting = [
            int(slot)
            for slot in np.flatnonzero(status == STATUS_QUEUED)
            if int(slot) not in scheduled
        ]
        if not waiting:
            return 0
        waiting = sorted(
            waiting,
            key=lambda slot: (-int(priority[slot]), float(queued_at[slot]), slot),
        )
        active_completion_times = event_time[
            event_active & (event_kind == EVENT_SERVICE_COMPLETE) & np.isfinite(event_time)
        ]
        if active_completion_times.size:
            service_cursor = max(float(np.max(active_completion_times)), target_time)
        else:
            service_cursor = target_time

        overflow = 0
        for slot in waiting:
            free_slots = np.flatnonzero(~event_active)
            if free_slots.size < 2:
                overflow += 1
                continue
            start_time = service_cursor
            completion_time = start_time + service_time
            start_idx = int(free_slots[0])
            complete_idx = int(free_slots[1])
            event_time[start_idx] = start_time
            event_kind[start_idx] = EVENT_SERVICE_START
            event_entity[start_idx] = slot
            event_priority[start_idx] = int(priority[slot])
            event_active[start_idx] = True
            event_time[complete_idx] = completion_time
            event_kind[complete_idx] = EVENT_SERVICE_COMPLETE
            event_entity[complete_idx] = slot
            event_priority[complete_idx] = int(priority[slot])
            event_active[complete_idx] = True
            expected_wait[slot] = max(start_time - target_time, 0.0)
            service_cursor = completion_time
        return overflow

    def _outcome_message(
        self,
        parent: CouplingMessage,
        time: float,
        kind: str,
        payload: dict[str, Any],
    ) -> CouplingMessage:
        return CouplingMessage(
            time=time,
            source=SOURCE_DES,
            target=TARGET_ABM,
            kind=kind,
            entity_id=parent.entity_id,
            priority=parent.priority,
            causal_parent=parent.causal_parent,
            payload={**parent.payload, **payload},
            rng_stream=parent.rng_stream,
        )


__all__ = [
    "STATUS_COMPLETED",
    "STATUS_IN_SERVICE",
    "STATUS_NONE",
    "STATUS_QUEUED",
    "STATUS_REJECTED",
    "EVENT_NONE",
    "EVENT_SERVICE_COMPLETE",
    "EVENT_SERVICE_START",
    "QueueDESKernel",
    "ensure_queue_runtime",
]
