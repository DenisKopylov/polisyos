from __future__ import annotations

import jax.numpy as jnp
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import StateDelta
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.patching import apply_patch_records, apply_state_delta
from polisyos.foundry.execute.patch_vm import merge_patch_records
from polisyos.ir.kernel import DEFAULT_MERGE_RULE_REGISTRY, DEFAULT_SLOT_REGISTRY


def test_merge_patch_records_matches_in_memory_sum_semantics(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=2, n_firms=1).replace(
        agents=GlobalState.empty(n_agents=2, n_firms=1).agents.replace(
            income=jnp.array([10.0, 10.0], dtype=jnp.float32)
        )
    )
    patch_records = {
        "agents.income": [
            {
                "node_id": "writer",
                "value": jnp.array([12.0, 12.0], dtype=jnp.float32),
            }
        ]
    }

    expected_state = apply_patch_records(
        base_state,
        patch_records,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )
    ops = merge_patch_records(
        store,
        patch_records,
        base_values={"agents.income": base_state.agents.income},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )
    state_delta_ref = store.put_json(
        StateDelta(base_ref=None, ops=ops),
        PutOptions(kind="foundry.state_delta", media_type="application/json"),
    )
    cas_state = apply_state_delta(
        store,
        base_state=base_state,
        state_delta_ref=state_delta_ref,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert jnp.allclose(cas_state.agents.income, expected_state.agents.income)
