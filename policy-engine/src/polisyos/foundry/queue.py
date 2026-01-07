from __future__ import annotations

from typing import Optional

import chex
import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.base import Mechanism
from polisyos.foundry.types import FidelityLevel


@chex.dataclass(frozen=True)
class QueueState:
    queue_length: jnp.ndarray  # shape ()


class QueueMechanism(Mechanism):
    """
    Очередь с тремя уровнями fidelity:
    - SURROGATE_FLUID: непрерывный поток
    - RELAXED_DISCRETE: сглаженная дискретность через temperature
    """

    service_rate: jnp.ndarray
    arrival_rate: jnp.ndarray
    capacity: Optional[jnp.ndarray]
    temperature: jnp.ndarray

    def __init__(
        self,
        service_rate: float,
        arrival_rate: float,
        *,
        capacity: Optional[float] = None,
        temperature: float = 1.0,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
        debug_mode: bool = False,
    ):
        self.service_rate = jnp.array(service_rate)
        self.arrival_rate = jnp.array(arrival_rate)
        self.capacity = jnp.array(capacity) if capacity is not None else None
        self.temperature = jnp.array(temperature)
        self.fidelity = fidelity
        self.debug_mode = debug_mode

    def init_state(self, state: QueueState, key: jax.Array) -> tuple[QueueState, jax.Array]:
        return state, key

    def step(self, state: QueueState, key: jax.Array) -> tuple[QueueState, jax.Array]:
        queue = state.queue_length

        if self.fidelity == FidelityLevel.SURROGATE_FLUID:
            inflow = self.arrival_rate
            outflow = jnp.minimum(queue, self.service_rate)
        elif self.fidelity == FidelityLevel.RELAXED_DISCRETE:
            # RELAXED_DISCRETE: мягкое насыщение и плавный порог
            inflow = self.arrival_rate * jax.nn.sigmoid(queue / self.temperature)
            availability = jax.nn.sigmoid((queue - self.service_rate) / self.temperature)
            outflow = self.service_rate * availability
        else:
            # HARD_DISCRETE: квантуем поток до дискретных значений
            inflow = jnp.round(self.arrival_rate)
            outflow = jnp.minimum(jnp.round(queue), jnp.round(self.service_rate))

        new_queue = jnp.maximum(0.0, queue + inflow - outflow)

        if self.capacity is not None:
            new_queue = jnp.minimum(new_queue, self.capacity)

        if self.debug_mode:
            jax.debug.print(
                "Queue step: q={q}, inflow={i}, outflow={o}",
                q=queue,
                i=inflow,
                o=outflow,
            )

        return QueueState(queue_length=new_queue), key


def simulate_queue(
    mech: QueueMechanism, state: QueueState, key: jax.Array, steps: int
) -> QueueState:
    def scan_step(carry, _):
        current_state, current_key = carry
        current_key, step_key = jax.random.split(current_key)
        next_state, next_key = mech.step(current_state, step_key)
        return (next_state, next_key), next_state

    (final_state, _), _ = jax.lax.scan(
        scan_step, (state, key), xs=jnp.arange(steps)
    )
    return final_state


def fidelity_gap_report(a: QueueState, b: QueueState) -> dict:
    diff = jnp.abs(a.queue_length - b.queue_length)
    denom = jnp.maximum(jnp.abs(a.queue_length), 1e-6)
    rel = diff / denom
    return {
        "abs_diff": float(diff),
        "rel_diff": float(rel),
    }
