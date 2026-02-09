from __future__ import annotations

import asyncio

import pytest

jax = pytest.importorskip("jax")
import jax.numpy as jnp

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir.selector_expr import SelectorPredicate
from polisyos.ir.types import SelectorOperator
from polisyos.scientist.agent.feasibility import StateSnapshotFeasibilityProbe


def run(coro):
    return asyncio.run(coro)


def _build_data_snapshot_ref(cas: FileSystemCAS) -> str:
    state = GlobalState.empty(n_agents=5, seed=42)
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.array([100.0, 500.0, 1200.0, 1800.0, 2500.0], dtype=jnp.float32),
            active=jnp.array([True, True, True, True, True], dtype=jnp.bool_),
        )
    )

    state_snapshot_ref = put_state_snapshot(cas, state=state, step=0)
    data_snapshot = DataSnapshot(data_ref=state_snapshot_ref)
    data_snapshot_ref = cas.put_json(
        data_snapshot.model_dump(mode="json"),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    return str(data_snapshot_ref.artifact_id)


def test_state_snapshot_probe_counts_matching_agents(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    data_snapshot_ref = _build_data_snapshot_ref(cas)

    probe = StateSnapshotFeasibilityProbe(cas)
    selector = SelectorPredicate(
        field="income",
        operator=SelectorOperator.LESS_THAN,
        value="1000",
    )

    result = run(
        probe.count_matching_agents(
            selector_expr=selector,
            data_snapshot_ref=data_snapshot_ref,
        )
    )

    assert result.matching_count == 2
    assert result.total_count == 5
    assert 0.39 <= result.match_ratio <= 0.41


def test_state_snapshot_probe_attribute_and_budget_checks(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    data_snapshot_ref = _build_data_snapshot_ref(cas)

    probe = StateSnapshotFeasibilityProbe(cas)
    selector = SelectorPredicate(
        field="income",
        operator=SelectorOperator.GREATER_EQUAL,
        value="1200",
    )

    has_income = run(
        probe.check_attribute_exists(
            attribute_name="income",
            data_snapshot_ref=data_snapshot_ref,
        )
    )
    has_unknown = run(
        probe.check_attribute_exists(
            attribute_name="unknown_field",
            data_snapshot_ref=data_snapshot_ref,
        )
    )
    budget = run(
        probe.estimate_budget_impact(
            selector_expr=selector,
            amount_per_agent=100.0,
            data_snapshot_ref=data_snapshot_ref,
            budget_limit=250.0,
        )
    )

    assert has_income is True
    assert has_unknown is False
    assert budget.matching_count == 3
    assert budget.estimated_total_cost == 300.0
    assert budget.feasible is False
