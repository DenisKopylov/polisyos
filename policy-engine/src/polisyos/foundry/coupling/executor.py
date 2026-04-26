"""Coupled DES/ABM executor over canonical Foundry `GlobalState`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
from polisyos.foundry.coupling.abm_kernel import NoOpABMKernel
from polisyos.foundry.coupling.contracts import ABMKernel, Coupler, DESKernel
from polisyos.foundry.coupling.coupler import DefaultPolicyCoupler, assert_coupled_invariants
from polisyos.foundry.coupling.des_kernel import QueueDESKernel
from polisyos.foundry.coupling.messages import CouplingMessage


@dataclass(frozen=True)
class CoupledRuntimeState:
    """State bundle carried by `CoupledContractsExecutor`."""

    global_state: GlobalState
    queue_state: QueueRuntimeState
    time: float = 0.0
    inbox_abm: tuple[CouplingMessage, ...] = ()
    inbox_des: tuple[CouplingMessage, ...] = ()
    rng_key: jax.Array = field(default_factory=lambda: jax.random.PRNGKey(0))

    @classmethod
    def initialize(
        cls,
        global_state: GlobalState,
        *,
        queue_state: QueueRuntimeState | None = None,
        rng_key: jax.Array | None = None,
        seed: int = 0,
    ) -> CoupledRuntimeState:
        resolved_queue = queue_state
        if resolved_queue is None:
            resolved_queue = global_state.queue_runtime
        if resolved_queue is None:
            resolved_queue = QueueRuntimeState.empty(global_state.agents.size)
        if resolved_queue.size != global_state.agents.size:
            raise ValueError("Queue runtime size must match GlobalState.agents.size")
        state = global_state.replace(queue_runtime=resolved_queue)
        return cls(
            global_state=state,
            queue_state=resolved_queue,
            time=float(np.asarray(resolved_queue.time).item()),
            rng_key=rng_key if rng_key is not None else jax.random.PRNGKey(int(seed)),
        )


@dataclass(frozen=True)
class CoupledStepResult:
    """One coupled executor transition."""

    runtime_state: CoupledRuntimeState
    metrics: dict[str, Any]
    q_to_a: tuple[CouplingMessage, ...]
    a_to_q: tuple[CouplingMessage, ...]


@dataclass
class CoupledContractsExecutor:
    """Synchronize DES queue dynamics with ABM behavior on `GlobalState`."""

    des_kernel: DESKernel = field(default_factory=QueueDESKernel)
    abm_kernel: ABMKernel = field(default_factory=NoOpABMKernel)
    coupler: Coupler = field(default_factory=DefaultPolicyCoupler)
    delta_a_max: float = 1.0
    distribution_executor: Any | None = None
    distribution_kwargs: Mapping[str, Any] = field(default_factory=dict)

    def step(self, runtime_state: CoupledRuntimeState) -> CoupledStepResult:
        previous_time = float(runtime_state.time)
        tau_q = self.des_kernel.next_event_time(runtime_state.queue_state)
        tau = min(float(tau_q), previous_time + max(float(self.delta_a_max), 1e-9))
        dt = max(tau - previous_time, 0.0)

        key, abm_key, des_key = jax.random.split(runtime_state.rng_key, 3)
        state_a, out_a, patches_a, metrics_a = self.abm_kernel.advance(
            runtime_state.global_state,
            dt,
            runtime_state.inbox_abm,
            abm_key,
        )
        inbox_des = list(runtime_state.inbox_des)
        inbox_des.extend(self.coupler.project_a_to_q(state_a, runtime_state.queue_state, out_a))

        queue_next, out_q, patches_q, metrics_q = self.des_kernel.advance_to(
            runtime_state.queue_state,
            tau,
            inbox_des,
            des_key,
        )
        state_with_queue = state_a.replace(queue_runtime=queue_next)
        q_to_a = self.coupler.project_q_to_a(state_with_queue, queue_next, out_q)
        merged_state, metrics_c = self.coupler.merge(
            state_with_queue,
            patches_q=patches_q,
            patches_a=patches_a,
            msgs_q=q_to_a,
            time=tau,
        )
        metrics_distribution: dict[str, Any] = {}
        if self.distribution_executor is not None:
            merged_state, metrics_distribution = self.distribution_executor.apply(
                merged_state,
                **dict(self.distribution_kwargs),
            )
        merged_state = merged_state.replace(
            queue_runtime=queue_next,
            step=merged_state.step + jnp.asarray(1, dtype=merged_state.step.dtype),
        )

        assert_coupled_invariants(
            state=merged_state,
            state_q=queue_next,
            previous_time=previous_time,
            current_time=tau,
        )

        next_runtime = CoupledRuntimeState(
            global_state=merged_state,
            queue_state=queue_next,
            time=tau,
            inbox_abm=tuple(q_to_a),
            inbox_des=(),
            rng_key=key,
        )
        metrics: dict[str, Any] = {
            "coupled/time": tau,
            "coupled/dt": dt,
            "coupled/tau_q": tau_q,
        }
        metrics.update(metrics_a)
        metrics.update(metrics_q)
        metrics.update(metrics_c)
        metrics.update(metrics_distribution)
        return CoupledStepResult(
            runtime_state=next_runtime,
            metrics=metrics,
            q_to_a=tuple(q_to_a),
            a_to_q=tuple(inbox_des),
        )

    def run(
        self,
        runtime_state: CoupledRuntimeState,
        n_steps: int,
    ) -> tuple[CoupledRuntimeState, list[dict[str, Any]]]:
        current = runtime_state
        metrics: list[dict[str, Any]] = []
        for _ in range(max(int(n_steps), 0)):
            result = self.step(current)
            current = result.runtime_state
            metrics.append(result.metrics)
        return current, metrics


__all__ = [
    "CoupledContractsExecutor",
    "CoupledRuntimeState",
    "CoupledStepResult",
]
