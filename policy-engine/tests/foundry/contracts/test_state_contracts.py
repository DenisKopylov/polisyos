from __future__ import annotations

import dataclasses
import os

os.environ.setdefault("JAX_PLATFORMS", "cpu")

import numpy as np
import jax

from polisyos.foundry._executor_snapshots import _build_dataclass
from polisyos.foundry.contracts.state import (
    AgentSimRuntimeState,
    CellState,
    GlobalState,
    HouseholdCellState,
    ProcurementGraphState,
)
from polisyos.foundry.executor import load_state_snapshot, put_state_snapshot
from polisyos.foundry.executor import export_seed_state_npz, import_seed_state_npz


def test_cell_and_household_cell_contracts_construct() -> None:
    cells = CellState.empty(3)
    household_cells = HouseholdCellState.empty(2)

    assert cells.size == 3
    assert household_cells.size == 2
    assert cells.population.shape == (3,)
    assert household_cells.disposable_income.shape == (2,)


def test_global_state_empty_remains_backward_compatible_without_cells() -> None:
    state = GlobalState.empty(n_agents=4, n_firms=2)
    assert state.agents.size == 4
    assert state.firms.size == 2
    assert state.cells is None
    assert state.household_cells is None


def test_global_state_supports_optional_cell_blocks_when_requested() -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1, n_cells=3, n_household_cells=4)
    assert state.cells is not None
    assert state.household_cells is not None
    assert state.cells.size == 3
    assert state.household_cells.size == 4


def test_global_state_is_a_valid_jax_pytree() -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1, n_cells=1, n_household_cells=1)
    leaves = jax.tree_util.tree_leaves(state)
    assert leaves
    assert all(hasattr(leaf, "shape") for leaf in leaves)


def test_global_state_with_cells_round_trips_through_snapshot(tmp_path) -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1, n_cells=3, n_household_cells=2).replace(
        cells=CellState(
            active=np.asarray([True, True, False]),
            region_code=np.asarray([1, 1, 2], dtype=np.int32),
            sector_id=np.asarray([10, 20, 30], dtype=np.int32),
            population=np.asarray([100.0, 200.0, 50.0], dtype=np.float32),
            employment=np.asarray([60.0, 120.0, 20.0], dtype=np.float32),
            output=np.asarray([1000.0, 2000.0, 500.0], dtype=np.float32),
            distress_score=np.asarray([0.1, 0.2, 0.5], dtype=np.float32),
            public_service_index=np.asarray([0.9, 0.8, 0.7], dtype=np.float32),
        ),
        household_cells=HouseholdCellState(
            active=np.asarray([True, True]),
            cell_id=np.asarray([0, 1], dtype=np.int32),
            household_count=np.asarray([40.0, 30.0], dtype=np.float32),
            disposable_income=np.asarray([500.0, 300.0], dtype=np.float32),
            poverty_rate=np.asarray([0.15, 0.25], dtype=np.float32),
            transfer_intensity=np.asarray([0.3, 0.4], dtype=np.float32),
        ),
    )

    from polisyos.core.artifacts.store import FileSystemCAS

    store = FileSystemCAS(tmp_path)
    snapshot_ref = put_state_snapshot(store, state=state, step=0)
    restored = load_state_snapshot(store, snapshot_ref=snapshot_ref)

    assert restored.cells is not None
    assert restored.household_cells is not None
    assert np.array_equal(np.asarray(restored.cells.region_code), np.asarray(state.cells.region_code))
    assert np.allclose(np.asarray(restored.cells.output), np.asarray(state.cells.output))
    assert np.allclose(
        np.asarray(restored.household_cells.disposable_income),
        np.asarray(state.household_cells.disposable_income),
    )


def test_global_state_with_cells_stays_jittable() -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1, n_cells=3, n_household_cells=2).replace(
        cells=CellState.empty(3).replace(output=np.asarray([1.0, 2.0, 3.0], dtype=np.float32)),
        household_cells=HouseholdCellState.empty(2).replace(
            household_count=np.asarray([10.0, 20.0], dtype=np.float32)
        ),
    )

    @jax.jit
    def advance(current: GlobalState) -> GlobalState:
        cells = current.cells
        household_cells = current.household_cells
        assert cells is not None
        assert household_cells is not None
        return current.replace(
            step=current.step + 1,
            gdp=current.gdp + cells.output.sum() + household_cells.household_count.sum(),
        )

    advanced = advance(state)

    assert int(np.asarray(advanced.step)) == 1
    assert float(np.asarray(advanced.gdp)) == 36.0


def test_global_state_supports_optional_agent_sim_runtime_block() -> None:
    state = GlobalState.empty(n_agents=3, n_firms=2).replace(
        agent_sim_runtime=AgentSimRuntimeState.empty(n_agents=3, n_firms=2, seed=7)
    )

    assert state.agent_sim_runtime is not None
    assert tuple(np.asarray(state.agent_sim_runtime.rng_key).shape) == (2,)
    assert tuple(np.asarray(state.agent_sim_runtime.procurement_graph.senders).shape) == (0,)


def test_global_state_with_agent_sim_runtime_round_trips_through_snapshot(tmp_path) -> None:
    runtime = AgentSimRuntimeState.empty(n_agents=2, n_firms=3, seed=11).replace(
        procurement_graph=ProcurementGraphState(
            senders=np.asarray([0, 1], dtype=np.int32),
            receivers=np.asarray([1, 2], dtype=np.int32),
            weights=np.asarray([1.0, 0.5], dtype=np.float32),
            edge_types=np.asarray([1, 1], dtype=np.int32),
            active=np.asarray([True, False]),
            n_nodes=np.asarray(3, dtype=np.int32),
            last_update_step=np.asarray(4, dtype=np.int32),
        )
    )
    state = GlobalState.empty(n_agents=2, n_firms=3, n_cells=1, n_household_cells=1).replace(
        agent_sim_runtime=runtime
    )

    from polisyos.core.artifacts.store import FileSystemCAS

    store = FileSystemCAS(tmp_path)
    snapshot_ref = put_state_snapshot(store, state=state, step=0)
    restored = load_state_snapshot(store, snapshot_ref=snapshot_ref)

    assert restored.agent_sim_runtime is not None
    assert np.array_equal(
        np.asarray(restored.agent_sim_runtime.procurement_graph.receivers),
        np.asarray([1, 2], dtype=np.int32),
    )
    assert int(np.asarray(restored.agent_sim_runtime.procurement_graph.n_nodes)) == 3


def test_foundry_seed_state_npz_roundtrip_preserves_multiscale_blocks(tmp_path) -> None:
    runtime = AgentSimRuntimeState.empty(n_agents=2, n_firms=3, seed=17).replace(
        procurement_graph=ProcurementGraphState(
            senders=np.asarray([0, 1], dtype=np.int32),
            receivers=np.asarray([1, 2], dtype=np.int32),
            weights=np.asarray([1.0, 0.5], dtype=np.float32),
            edge_types=np.asarray([1, 2], dtype=np.int32),
            active=np.asarray([True, True]),
            n_nodes=np.asarray(3, dtype=np.int32),
            last_update_step=np.asarray(2, dtype=np.int32),
        )
    )
    state = GlobalState.empty(n_agents=2, n_firms=3, n_cells=2, n_household_cells=2).replace(
        cells=CellState.empty(2).replace(
            output=np.asarray([120.0, 240.0], dtype=np.float32),
            population=np.asarray([50.0, 80.0], dtype=np.float32),
        ),
        household_cells=HouseholdCellState.empty(2).replace(
            cell_id=np.asarray([0, 1], dtype=np.int32),
            disposable_income=np.asarray([500.0, 650.0], dtype=np.float32),
        ),
        agent_sim_runtime=runtime,
    )

    path = export_seed_state_npz(state, tmp_path / "foundry_seed_state_v1.npz")
    restored = import_seed_state_npz(path)

    assert path.name == "foundry_seed_state_v1.npz"
    assert restored.cells is not None
    assert restored.household_cells is not None
    assert restored.agent_sim_runtime is not None
    assert np.allclose(np.asarray(restored.cells.output), np.asarray([120.0, 240.0], dtype=np.float32))
    assert np.allclose(
        np.asarray(restored.household_cells.disposable_income),
        np.asarray([500.0, 650.0], dtype=np.float32),
    )
    assert np.array_equal(
        np.asarray(restored.agent_sim_runtime.procurement_graph.receivers),
        np.asarray([1, 2], dtype=np.int32),
    )


def test_snapshot_builder_accepts_legacy_state_without_cell_payloads() -> None:
    base = GlobalState.empty(n_agents=2, n_firms=1)
    nested = {
        "step": np.asarray(base.step),
        "agents": {
            field.name: np.asarray(getattr(base.agents, field.name))
            for field in dataclasses.fields(base.agents)
        },
        "firms": {
            field.name: np.asarray(getattr(base.firms, field.name))
            for field in dataclasses.fields(base.firms)
        },
        "market": {
            field.name: np.asarray(getattr(base.market, field.name))
            for field in dataclasses.fields(base.market)
        },
        "government_balance": np.asarray(base.government_balance),
        "tax_rate": np.asarray(base.tax_rate),
        "gdp": np.asarray(base.gdp),
    }

    restored = _build_dataclass(GlobalState, nested)
    assert restored.cells is None
    assert restored.household_cells is None
    assert restored.agents.size == 2
    assert restored.firms.size == 1
