from __future__ import annotations

import jax.numpy as jnp
import numpy as np

from polisyos.foundry.agents import build_observations
from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState


def test_adaptive_agent_observations_can_consume_queue_runtime_signals() -> None:
    queue = QueueRuntimeState.empty(2).replace(
        expected_wait=jnp.asarray([1.5, 3.0], dtype=jnp.float32)
    )
    base = GlobalState.empty(n_agents=2, n_firms=1)
    state = base.replace(
        queue_runtime=queue,
        agents=base.agents.replace(risk_aversion=jnp.asarray([0.25, 0.75], dtype=jnp.float32)),
    )

    observations = build_observations(
        state,
        ["queue_runtime.expected_wait", "agents.risk_aversion"],
    )

    np.testing.assert_allclose(
        np.asarray(observations),
        np.asarray([[1.5, 0.25], [3.0, 0.75]], dtype=np.float32),
    )
