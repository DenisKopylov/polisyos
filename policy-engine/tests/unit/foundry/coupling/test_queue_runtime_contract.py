from __future__ import annotations

import numpy as np
from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
from polisyos.foundry.execute.executor import export_seed_state_npz, import_seed_state_npz


def test_global_state_supports_optional_queue_runtime_block() -> None:
    state = GlobalState.empty(n_agents=3, n_firms=1).replace(
        queue_runtime=QueueRuntimeState.empty(n_entities=3, capacity=7)
    )

    assert state.queue_runtime is not None
    assert state.queue_runtime.size == 3
    assert float(np.asarray(state.queue_runtime.capacity).item()) == 7.0
    assert state.queue_runtime.event_calendar.size == 6


def test_queue_runtime_round_trips_through_seed_npz(tmp_path) -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1).replace(
        queue_runtime=QueueRuntimeState.empty(n_entities=2, capacity=3, queue_length=1)
    )

    path = export_seed_state_npz(state, tmp_path / "queue_seed.npz")
    restored = import_seed_state_npz(path)

    assert restored.queue_runtime is not None
    assert float(np.asarray(restored.queue_runtime.queue_length).item()) == 1.0
    assert float(np.asarray(restored.queue_runtime.capacity).item()) == 3.0
    assert restored.queue_runtime.event_calendar.size == 4
