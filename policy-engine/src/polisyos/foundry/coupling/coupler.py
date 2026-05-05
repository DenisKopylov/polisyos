"""Deterministic projection and merge rules for coupled DES/ABM execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jax.numpy as jnp
import numpy as np

from polisyos.foundry.contracts.mechanism import PatchMap
from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
from polisyos.foundry.coupling.messages import (
    KIND_QUEUE_ADMIT,
    KIND_QUEUE_REJECT,
    KIND_SERVICE_COMPLETE,
    TARGET_ABM,
    TARGET_DES,
    CouplingMessage,
    entity_index,
    sort_messages,
)
from polisyos.foundry.execute._models import get_state_path, set_state_path


def _priority_for_kind(kind: str) -> int:
    if kind == "policy_change":
        return 0
    if kind == KIND_SERVICE_COMPLETE:
        return 10
    if kind in {KIND_QUEUE_ADMIT, KIND_QUEUE_REJECT}:
        return 20
    if kind == "agent_decision":
        return 30
    return 50


def _merge_patch_maps(*maps: PatchMap | None) -> list[tuple[int, str, dict[str, Any]]]:
    records: list[tuple[int, str, dict[str, Any]]] = []
    for patch_map in maps:
        for slot_id, patch_list in (patch_map or {}).items():
            for patch in patch_list:
                priority = int(patch.get("priority", 50))
                records.append((priority, slot_id, dict(patch)))
    return sorted(records, key=lambda item: (item[0], item[1]))


def _apply_patch_records(
    state: GlobalState, records: list[tuple[int, str, dict[str, Any]]]
) -> GlobalState:
    updated = state
    for _priority, slot_id, record in records:
        current = get_state_path(updated, slot_id)
        if "delta" in record:
            value = current + record["delta"]
        elif "value" in record:
            value = record["value"]
        elif "new_value" in record:
            value = record["new_value"]
        else:
            continue
        updated = set_state_path(updated, slot_id, value)
    return updated


@dataclass(frozen=True)
class DefaultPolicyCoupler:
    """Default coupler for benefit/triage-like queue-policy simulations."""

    benefit_amount: float = 0.0
    income_amount: float = 0.0

    def project_a_to_q(
        self,
        state: GlobalState,
        state_q: QueueRuntimeState,
        msgs_a: list[CouplingMessage] | tuple[CouplingMessage, ...],
    ) -> list[CouplingMessage]:
        del state, state_q
        return [
            message.with_route(target=TARGET_DES)
            for message in sort_messages(tuple(msgs_a))
            if message.target == TARGET_DES
        ]

    def project_q_to_a(
        self,
        state: GlobalState,
        state_q: QueueRuntimeState,
        msgs_q: list[CouplingMessage] | tuple[CouplingMessage, ...],
    ) -> list[CouplingMessage]:
        del state, state_q
        return [
            message.with_route(target=TARGET_ABM)
            for message in sort_messages(tuple(msgs_q))
            if message.target == TARGET_ABM
        ]

    def merge(
        self,
        state: GlobalState,
        *,
        patches_q: PatchMap | None = None,
        patches_a: PatchMap | None = None,
        msgs_q: list[CouplingMessage] | tuple[CouplingMessage, ...] = (),
        time: float,
    ) -> tuple[GlobalState, dict[str, Any]]:
        q_outcome_patches = self._patches_from_queue_outcomes(state, msgs_q, time=time)
        prioritized_q = self._with_default_priority(patches_q, default_priority=20)
        prioritized_a = self._with_default_priority(patches_a, default_priority=30)
        records = _merge_patch_maps(q_outcome_patches, prioritized_q, prioritized_a)
        return _apply_patch_records(state, records), {"coupler/patch_records": len(records)}

    def _with_default_priority(
        self,
        patch_map: PatchMap | None,
        *,
        default_priority: int,
    ) -> PatchMap:
        prioritized: PatchMap = {}
        for slot_id, patches in (patch_map or {}).items():
            prioritized[slot_id] = [
                {**patch, "priority": int(patch.get("priority", default_priority))}
                for patch in patches
            ]
        return prioritized

    def _patches_from_queue_outcomes(
        self,
        state: GlobalState,
        msgs_q: list[CouplingMessage] | tuple[CouplingMessage, ...],
        *,
        time: float,
    ) -> PatchMap:
        del time
        savings_delta = jnp.zeros_like(state.agents.savings)
        income_delta = jnp.zeros_like(state.agents.income)
        has_savings = False
        has_income = False

        for message in sort_messages(tuple(msgs_q)):
            if message.kind != KIND_SERVICE_COMPLETE:
                continue
            slot = entity_index(message.entity_id)
            if slot is None or slot < 0 or slot >= state.agents.size:
                continue
            cash_delta = float(message.payload.get("cash_delta", self.benefit_amount))
            wage_delta = float(message.payload.get("income_delta", self.income_amount))
            if cash_delta != 0.0:
                savings_delta = savings_delta.at[slot].add(cash_delta)
                has_savings = True
            if wage_delta != 0.0:
                income_delta = income_delta.at[slot].add(wage_delta)
                has_income = True

        patches: PatchMap = {}
        if has_savings:
            patches["agents.savings"] = [
                {"delta": savings_delta, "priority": _priority_for_kind(KIND_SERVICE_COMPLETE)}
            ]
        if has_income:
            patches["agents.income"] = [
                {"delta": income_delta, "priority": _priority_for_kind(KIND_SERVICE_COMPLETE)}
            ]
        return patches


def assert_coupled_invariants(
    *,
    state: GlobalState,
    state_q: QueueRuntimeState,
    previous_time: float,
    current_time: float,
) -> None:
    """Executable invariants for the minimal coupled runtime."""
    if current_time < previous_time - 1e-9:
        raise AssertionError("coupled time must be monotone")
    queue_length = float(np.asarray(state_q.queue_length).item())
    if queue_length < -1e-6:
        raise AssertionError("queue length cannot be negative")
    if state.queue_runtime is not None:
        runtime_queue = float(np.asarray(state.queue_runtime.queue_length).item())
        if abs(runtime_queue - queue_length) > 1e-6:
            raise AssertionError("GlobalState.queue_runtime diverged from DES queue state")
    calendar = state_q.event_calendar
    active = np.asarray(calendar.event_active, dtype=bool)
    if np.any(active):
        times = np.asarray(calendar.event_time, dtype=np.float32)
        if np.any(~np.isfinite(times[active])):
            raise AssertionError("active queue calendar events must have finite timestamps")
        if np.any(times[active] < current_time - 1e-9):
            raise AssertionError("queue calendar cannot retain events in the past")


__all__ = [
    "DefaultPolicyCoupler",
    "assert_coupled_invariants",
]
