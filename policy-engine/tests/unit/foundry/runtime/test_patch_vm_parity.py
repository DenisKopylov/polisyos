from __future__ import annotations

from io import BytesIO

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import StateDelta
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.patching import apply_patch_records, apply_state_delta
from polisyos.foundry.execute.patch_vm import merge_patch_records
from polisyos.ir.kernel import DEFAULT_MERGE_RULE_REGISTRY, DEFAULT_SLOT_REGISTRY


@pytest.mark.parametrize("selected", [False, True])
def test_merge_patch_records_matches_in_memory_sum_semantics(tmp_path, selected) -> None:
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
    unrelated_ref = None
    if selected:
        encoded = BytesIO()
        np.save(encoded, np.full(2, 2.0, dtype=np.float32), allow_pickle=False)
        unrelated_ref = store.put_bytes(
            encoded.getvalue(),
            PutOptions(
                kind="foundry.patch_value",
                media_type="application/x-npy",
                schema=SchemaInfo(name="test.UnrelatedPatchView", version="1.0"),
            ),
            return_selected_profile=True,
        )
    ops = merge_patch_records(
        store,
        patch_records,
        base_values={"agents.income": base_state.agents.income},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        return_selected_profile=selected,
    )
    assert len(ops) == 1
    assert (ops[0].value_ref.manifest_profile_sha256 is not None) is selected
    if selected:
        assert unrelated_ref is not None
        assert ops[0].value_ref.artifact_id == unrelated_ref.artifact_id
        assert ops[0].value_ref.manifest_profile_sha256 != unrelated_ref.manifest_profile_sha256
    state_delta_ref = store.put_json(
        StateDelta(base_ref=None, ops=ops),
        PutOptions(
            kind=StateDelta.ARTIFACT_KIND,
            media_type=StateDelta.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=StateDelta.ARTIFACT_SCHEMA_NAME,
                version=StateDelta.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(ops[0].value_ref, role="patch_value")],
        ),
        return_selected_profile=selected,
    )
    fresh = FileSystemCAS(tmp_path)
    (edge,) = fresh.get_manifest(state_delta_ref).inputs
    assert edge.manifest_profile_sha256 == ops[0].value_ref.manifest_profile_sha256
    if selected:
        assert unrelated_ref is not None
        assert fresh.get_manifest(ops[0].value_ref).artifact_schema is None
        assert fresh.get_manifest(unrelated_ref.artifact_id).artifact_schema is not None
    cas_state = apply_state_delta(
        fresh,
        base_state=base_state,
        state_delta_ref=state_delta_ref,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert jnp.allclose(cas_state.agents.income, expected_state.agents.income)
