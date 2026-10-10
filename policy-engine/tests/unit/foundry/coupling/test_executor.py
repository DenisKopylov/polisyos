from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
from polisyos.foundry.coupling.abm_kernel import UnemploymentClaimABMKernel
from polisyos.foundry.coupling.coupler import DefaultPolicyCoupler
from polisyos.foundry.coupling.des_kernel import QueueDESKernel
from polisyos.foundry.coupling.executor import CoupledContractsExecutor, CoupledRuntimeState
from polisyos.foundry.coupling.messages import KIND_SERVICE_COMPLETE


class _FakeDistributionExecutor:
    def apply(self, state: GlobalState, *, income_delta: float = 0.0):
        return (
            state.replace(agents=state.agents.replace(income=state.agents.income + income_delta)),
            {"distribution/fake_income_delta": income_delta},
        )


def _base_state() -> GlobalState:
    base = GlobalState.empty(n_agents=2, n_firms=1)
    return base.replace(
        agents=base.agents.replace(
            active=jnp.asarray([True, True]),
            is_employed=jnp.asarray([False, False]),
            risk_aversion=jnp.asarray([0.1, 0.9], dtype=jnp.float32),
            savings=jnp.asarray([0.0, 0.0], dtype=jnp.float32),
        )
    )


def test_coupled_executor_updates_canonical_state_from_queue_outcomes() -> None:
    executor = CoupledContractsExecutor(
        des_kernel=QueueDESKernel(service_rate=1.0, capacity=10, time_step=1.0),
        abm_kernel=UnemploymentClaimABMKernel(),
        coupler=DefaultPolicyCoupler(benefit_amount=50.0),
        delta_a_max=1.0,
    )
    runtime = CoupledRuntimeState.initialize(
        _base_state(),
        queue_state=QueueRuntimeState.empty(2, capacity=10),
        rng_key=jax.random.PRNGKey(0),
    )

    first = executor.step(runtime)
    result = executor.step(first.runtime_state)
    state = result.runtime_state.global_state

    assert np.asarray(state.agents.savings).tolist() == [0.0, 50.0]
    assert state.queue_runtime is not None
    assert float(np.asarray(state.queue_runtime.queue_length).item()) == 1.0
    assert any(message.kind == KIND_SERVICE_COMPLETE for message in result.q_to_a)


def test_coupled_executor_replay_is_deterministic_with_same_seed() -> None:
    executor = CoupledContractsExecutor(
        des_kernel=QueueDESKernel(service_rate=1.0, capacity=10, time_step=1.0),
        abm_kernel=UnemploymentClaimABMKernel(),
        coupler=DefaultPolicyCoupler(benefit_amount=25.0),
        delta_a_max=1.0,
    )
    runtime_a = CoupledRuntimeState.initialize(
        _base_state(),
        queue_state=QueueRuntimeState.empty(2, capacity=10),
        rng_key=jax.random.PRNGKey(42),
    )
    runtime_b = CoupledRuntimeState.initialize(
        _base_state(),
        queue_state=QueueRuntimeState.empty(2, capacity=10),
        rng_key=jax.random.PRNGKey(42),
    )

    final_a, metrics_a = executor.run(runtime_a, 3)
    final_b, metrics_b = executor.run(runtime_b, 3)

    np.testing.assert_allclose(
        np.asarray(final_a.global_state.agents.savings),
        np.asarray(final_b.global_state.agents.savings),
    )
    assert metrics_a == metrics_b


def test_coupled_executor_can_call_distribution_executor_after_merge() -> None:
    executor = CoupledContractsExecutor(
        des_kernel=QueueDESKernel(service_rate=1.0, capacity=10, time_step=1.0),
        abm_kernel=UnemploymentClaimABMKernel(),
        coupler=DefaultPolicyCoupler(benefit_amount=0.0),
        distribution_executor=_FakeDistributionExecutor(),
        distribution_kwargs={"income_delta": 2.0},
        delta_a_max=1.0,
    )
    runtime = CoupledRuntimeState.initialize(
        _base_state(),
        queue_state=QueueRuntimeState.empty(2, capacity=10),
        rng_key=jax.random.PRNGKey(0),
    )

    result = executor.step(runtime)

    np.testing.assert_allclose(
        np.asarray(result.runtime_state.global_state.agents.income),
        np.asarray([2.0, 2.0], dtype=np.float32),
    )
    assert result.metrics["distribution/fake_income_delta"] == 2.0
