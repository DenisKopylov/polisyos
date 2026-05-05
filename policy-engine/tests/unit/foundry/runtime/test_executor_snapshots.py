from __future__ import annotations

import dataclasses
import hashlib
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._models import load_model
from polisyos.foundry.execute._snapshots import (
    _build_dataclass,
    _dataclass_type_hints,
    _decode_snapshot_leaf,
    _flatten_state,
    _nest_state,
    _nest_state_from_keys,
    _SnapshotLeaf,
    _validate_snapshot_blob,
    load_state_snapshot,
    put_state_snapshot,
)

if TYPE_CHECKING:
    MissingSnapshotType = Any


@dataclasses.dataclass(frozen=True)
class _ScalarState:
    step: int
    ratio: float
    active: bool


@dataclasses.dataclass(frozen=True)
class _ForwardChild:
    value: Any


@dataclasses.dataclass(frozen=True)
class _ForwardParent:
    child: _ForwardChild
    count: int


@dataclasses.dataclass(frozen=True)
class _UnresolvedAnnotation:
    value: MissingSnapshotType


def test_snapshot_metadata_includes_version_checksum_and_entry_count(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=3, n_firms=2)

    snapshot_ref = put_state_snapshot(store, state=state, step=4)
    snapshot = load_model(store, snapshot_ref, StateSnapshot)
    blob_bytes = store.get_bytes(snapshot.state_ref.artifact_id)

    assert snapshot.schema_version == "2.0"
    assert snapshot.format_version == "npz-v2"
    assert snapshot.codec == "numpy-npz"
    assert snapshot.checksum_sha256 == hashlib.sha256(blob_bytes).hexdigest()
    assert snapshot.entry_count is not None
    assert snapshot.entry_count > 0
    assert snapshot.step == 4
    assert "snapshot_format:npz-v2" in snapshot.notes


def test_load_state_snapshot_rejects_corrupt_blob_checksum(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=2, n_firms=1)
    snapshot_ref = put_state_snapshot(store, state=state, step=0)
    snapshot = load_model(store, snapshot_ref, StateSnapshot)

    blob_path, _manifest_path = store.get_paths(snapshot.state_ref.artifact_id)
    blob_path.write_bytes(b"not a valid snapshot blob")

    with pytest.raises(ValueError, match="Snapshot checksum mismatch"):
        load_state_snapshot(store, snapshot_ref=snapshot_ref)


def test_put_state_snapshot_does_not_publish_snapshot_when_blob_not_visible(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    monkeypatch.setattr(store, "has", lambda _artifact_id: False)

    with pytest.raises(ValueError, match="not fully persisted"):
        put_state_snapshot(store, state=GlobalState.empty(n_agents=1, n_firms=1), step=0)

    persisted_kinds = [
        store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()
    ]
    assert "foundry.state_snapshot" not in persisted_kinds


def test_flatten_state_iterative_codec_handles_scalar_values() -> None:
    flat = dict(_flatten_state(_ScalarState(step=7, ratio=0.25, active=True)))

    assert flat["step"].shape == ()
    assert flat["ratio"].shape == ()
    assert flat["active"].shape == ()

    restored = _build_dataclass(_ScalarState, _nest_state(flat))

    assert int(np.asarray(restored.step)) == 7
    assert float(np.asarray(restored.ratio)) == pytest.approx(0.25)
    assert bool(np.asarray(restored.active)) is True


def test_snapshot_helpers_fail_closed_on_invalid_shapes_and_types() -> None:
    with pytest.raises(ValueError, match="unnamed scalar root"):
        dict(_flatten_state(1))

    with pytest.raises(TypeError, match="Unsupported snapshot value"):
        dict(_flatten_state({"not": "a dataclass"}, prefix="payload."))

    with pytest.raises(ValueError, match="Invalid snapshot key"):
        _nest_state_from_keys(["agents..income"])

    with pytest.raises(ValueError, match="key collision"):
        _nest_state_from_keys(["agents", "agents.income"])

    with pytest.raises(ValueError, match="Expected dataclass type"):
        _build_dataclass(dict, {})

    with pytest.raises(ValueError, match="Missing nested data"):
        _build_dataclass(_ForwardParent, {"count": np.asarray(1)})

    with pytest.raises(ValueError, match="Missing nested data"):
        _build_dataclass(_ForwardParent, {"child": np.asarray(1), "count": np.asarray(1)})

    with pytest.raises(ValueError, match="Missing value"):
        _build_dataclass(_ScalarState, {"step": np.asarray(1), "ratio": np.asarray(1.0)})

    with pytest.raises(ValueError, match="requires an open NPZ blob"):
        _decode_snapshot_leaf(_SnapshotLeaf("missing"), blob=None)

    assert _dataclass_type_hints(_UnresolvedAnnotation) == {}


def test_validate_snapshot_blob_rejects_unknown_format_and_codec() -> None:
    state_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("c" * 64),
        kind="foundry.state_blob",
        media_type="application/x-npz",
    )

    with pytest.raises(ValueError, match="Unsupported snapshot format_version"):
        _validate_snapshot_blob(
            StateSnapshot(state_ref=state_ref, format_version="npz-v99"),
            b"",
        )

    with pytest.raises(ValueError, match="Unsupported snapshot codec"):
        _validate_snapshot_blob(
            StateSnapshot(state_ref=state_ref, codec="native-array"),
            b"",
        )

    _validate_snapshot_blob(
        StateSnapshot(
            state_ref=state_ref,
            checksum_sha256=hashlib.sha256(b"ok").hexdigest(),
        ),
        b"ok",
    )


def test_build_dataclass_resolves_forward_refs_without_eager_blob_materialization() -> None:
    accessed: list[str] = []

    class LazyBlob:
        files = ["child.value", "count"]

        def __getitem__(self, key: str) -> np.ndarray:
            accessed.append(key)
            if key == "child.value":
                return np.asarray([1, 2, 3], dtype=np.int32)
            if key == "count":
                return np.asarray(3, dtype=np.int32)
            raise KeyError(key)

    blob = LazyBlob()
    nested = _nest_state_from_keys(blob.files)

    assert isinstance(nested["child"]["value"], _SnapshotLeaf)

    restored = _build_dataclass(_ForwardParent, nested, blob=blob)

    assert isinstance(restored.child, _ForwardChild)
    assert np.array_equal(np.asarray(restored.child.value), np.asarray([1, 2, 3]))
    assert int(np.asarray(restored.count)) == 3
    assert accessed == ["child.value", "count"]


def test_large_state_snapshot_round_trips_with_bounded_memory(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(
        n_agents=2048,
        n_firms=512,
        n_cells=64,
        n_household_cells=128,
    )

    snapshot_ref = put_state_snapshot(store, state=state, step=8)
    restored = load_state_snapshot(store, snapshot_ref=snapshot_ref)

    assert int(np.asarray(restored.step)) == int(np.asarray(state.step))
    assert restored.agents.income.shape == (2048,)
    assert restored.firms.wage_offer.shape == (512,)
    assert restored.cells is not None
    assert restored.cells.population.shape == (64,)
    assert restored.household_cells is not None
    assert restored.household_cells.disposable_income.shape == (128,)
