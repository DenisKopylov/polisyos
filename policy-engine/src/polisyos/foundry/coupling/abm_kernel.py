"""ABM-side kernels for coupled DES/ABM simulations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import jax
import numpy as np

from polisyos.foundry.contracts.mechanism import PatchMap
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.coupling.messages import (
    KIND_CLAIM_ARRIVAL,
    SOURCE_ABM,
    TARGET_DES,
    CouplingMessage,
)


@dataclass(frozen=True)
class NoOpABMKernel:
    """ABM kernel that only consumes DES messages and emits no decisions."""

    def advance(
        self,
        state_a: GlobalState,
        dt: float,
        inbox: list[CouplingMessage] | tuple[CouplingMessage, ...],
        rng: jax.Array,
    ) -> tuple[GlobalState, list[CouplingMessage], PatchMap, dict[str, Any]]:
        del dt, inbox, rng
        return state_a, [], {}, {"abm/messages_emitted": 0}


@dataclass(frozen=True)
class UnemploymentClaimABMKernel:
    """Emit claim-arrival intents for active unemployed agents.

    This is a small default behavioral kernel for benefit-queue benchmarks. It
    deliberately emits intents only; the DES kernel decides admission, rejection,
    and completion.
    """

    arrival_kind: str = KIND_CLAIM_ARRIVAL
    claim_type: str = "ui_new"
    default_priority: int = 0
    vulnerability_scale: float = 10.0

    def advance(
        self,
        state_a: GlobalState,
        dt: float,
        inbox: list[CouplingMessage] | tuple[CouplingMessage, ...],
        rng: jax.Array,
    ) -> tuple[GlobalState, list[CouplingMessage], PatchMap, dict[str, Any]]:
        del rng
        time = float(np.asarray(state_a.step).item()) + max(float(dt), 0.0)
        active = np.asarray(state_a.agents.active, dtype=bool)
        employed = np.asarray(state_a.agents.is_employed, dtype=bool)
        risk = np.asarray(state_a.agents.risk_aversion, dtype=np.float32)

        messages: list[CouplingMessage] = []
        for slot in np.flatnonzero(active & ~employed):
            vulnerability = float(np.clip(risk[int(slot)], 0.0, 1.0))
            priority = max(
                self.default_priority, int(round(vulnerability * self.vulnerability_scale))
            )
            messages.append(
                CouplingMessage(
                    time=time,
                    source=SOURCE_ABM,
                    target=TARGET_DES,
                    kind=self.arrival_kind,
                    entity_id=f"agent-{int(slot)}",
                    priority=priority,
                    causal_parent=f"claim-intent-{int(slot)}-{time:g}",
                    payload={
                        "claim_type": self.claim_type,
                        "search_effort": float(1.0 - vulnerability),
                        "vulnerability_score": vulnerability,
                    },
                )
            )

        metrics = {
            "abm/messages_emitted": len(messages),
            "abm/inbox_consumed": len(inbox),
            "abm/unemployed_active": int(np.sum(active & ~employed)),
        }
        return state_a, messages, {}, metrics


@dataclass(frozen=True)
class AdaptiveAgentABMKernel:
    """ABM kernel adapter around `AdaptiveAgentMechanism` patch emission."""

    mechanism: Any
    emit_claims: bool = False
    claim_kernel: UnemploymentClaimABMKernel = field(default_factory=UnemploymentClaimABMKernel)

    def advance(
        self,
        state_a: GlobalState,
        dt: float,
        inbox: list[CouplingMessage] | tuple[CouplingMessage, ...],
        rng: jax.Array,
    ) -> tuple[GlobalState, list[CouplingMessage], PatchMap, dict[str, Any]]:
        patches, next_key = self.mechanism.emit_patches(state_a, rng)
        messages: list[CouplingMessage] = []
        metrics: dict[str, Any] = {
            "abm/patch_slots": len(patches),
            "abm/inbox_consumed": len(inbox),
        }
        if self.emit_claims:
            _, messages, claim_patches, claim_metrics = self.claim_kernel.advance(
                state_a,
                dt,
                inbox,
                next_key,
            )
            patches = {**patches, **claim_patches}
            metrics.update(claim_metrics)
        else:
            metrics["abm/messages_emitted"] = 0
        return state_a, messages, patches, metrics


__all__ = [
    "AdaptiveAgentABMKernel",
    "NoOpABMKernel",
    "UnemploymentClaimABMKernel",
]
