"""Independent persisted-codec oracles for the complete native state projection."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import FileSystemCAS, load_core_json_artifact
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
from polisyos.foundry.execute._internal.snapshots import put_state_snapshot


def test_value_projection_covers_all_persisted_native_codec_leaves(tmp_path: Path) -> None:
    """Fresh NPZ reader supplies the full denominator independently of projection."""
    store = FileSystemCAS(tmp_path / "cas")
    state = GlobalState.empty(n_agents=2, n_firms=1, n_cells=2, n_household_cells=3)
    dtype = np.asarray(state.agents.savings).dtype
    state = state.replace(agents=state.agents.replace(savings=np.asarray([-0.0, 3.5], dtype=dtype)))
    snapshot_ref = put_state_snapshot(store, state=state)
    reader = FileSystemCAS(tmp_path / "cas")
    snapshot = StateSnapshot.model_validate(load_core_json_artifact(reader, snapshot_ref))
    reopened = load_state_snapshot(reader, snapshot_ref=snapshot_ref)
    projection = state_snapshot_value_projection(reopened)
    assert state_snapshot_value_projection(state) == projection
    by_path = {leaf.path: leaf for leaf in projection}
    assert len(by_path) == len(projection)
    with np.load(BytesIO(reader.get_bytes(snapshot.state_ref)), allow_pickle=False) as archive:
        assert set(by_path) == set(archive.files)
        for path in archive.files:
            actual = archive[path]
            assert by_path[path].dtype == actual.dtype.str
            assert by_path[path].shape == actual.shape
            assert by_path[path].value_bytes == actual.tobytes(order="C")
            assert (
                by_path[path].value_sha256 == hashlib.sha256(actual.tobytes(order="C")).hexdigest()
            )
    # Changing contextual snapshot wrapper lineage is immaterial to this values
    # projection; every actual value is still derived from the real state owner.
    assert by_path["agents.savings"].shape == (2,)


@pytest.mark.parametrize("mutation", ["signed_zero", "shape", "dtype", "other_component"])
def test_value_projection_distinguishes_same_scalar_and_non_target_mutants(mutation: str) -> None:
    """Keep scalar/subject markers while changing actual consumed representation."""
    state = GlobalState.empty(n_agents=2, n_firms=1)
    original = np.asarray(state.agents.savings)
    if mutation == "other_component":
        cash = np.asarray(state.firms.cash)
        changed = state.replace(
            firms=state.firms.replace(cash=np.full(cash.shape, 17, dtype=cash.dtype))
        )
    else:
        savings = (
            np.full(original.shape, -0.0, dtype=original.dtype)
            if mutation == "signed_zero"
            else np.asarray(0.0, dtype=original.dtype)
            if mutation == "shape"
            else original.astype(np.float64 if original.dtype != np.float64 else np.float32)
        )
        changed = state.replace(agents=state.agents.replace(savings=savings))
    assert state_snapshot_value_projection(changed) != state_snapshot_value_projection(state)
