"""The selected threshold basis remains tied to the real registry snapshot."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.search.judge_threshold_basis import (
    capture_judge_threshold_basis,
    load_judge_threshold_basis,
    resolve_judge_threshold_basis,
)
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry


def _registry(tmp_path):
    registry = JudgeThresholdRegistry(root=tmp_path / "registry")
    # Persist a synthetic fixture based on this existing owner's entries.
    registry.record(registry.snapshot().entries[0])
    return registry


def test_real_registry_snapshot_is_frozen_and_live_drift_makes_it_stale(tmp_path) -> None:
    registry = _registry(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    frozen, ref = capture_judge_threshold_basis(store, registry)
    assert ref.manifest_profile_sha256 is not None
    admitted = resolve_judge_threshold_basis(store, ref, registry)
    assert admitted.status == "current" and admitted.basis is not None
    assert isinstance(admitted.basis.snapshot.entries, tuple)
    with pytest.raises(ValidationError):
        admitted.basis.snapshot.entries = ()
    with pytest.raises(ValidationError):
        admitted.basis.snapshot.entries[0].threshold_value = 999
    captured = frozen.snapshot()
    entry = registry.snapshot().entries[0]
    registry.record(
        entry.model_copy(update={"threshold_value": entry.threshold_value + 1}),
        allow_loosen=True,
        change_reason="synthetic drift control",
    )
    assert frozen.snapshot() == captured
    assert resolve_judge_threshold_basis(store, ref, registry).status == "stale"


def test_registry_change_during_capture_never_selects_a_basis(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    put = store.put_json

    def put_then_change(obj, opts, canon_spec=None, *, return_selected_profile=False):
        ref = put(obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile)
        entry = registry.snapshot().entries[0]
        registry.record(
            entry.model_copy(update={"threshold_value": entry.threshold_value + 1}),
            allow_loosen=True,
            change_reason="synthetic capture race",
        )
        return ref

    monkeypatch.setattr(store, "put_json", put_then_change)
    with pytest.raises(ValueError, match="threshold_registry_changed"):
        capture_judge_threshold_basis(store, registry)


@pytest.mark.parametrize(
    "override",
    [
        "instance",
        "class",
        "resolver_helper",
        "root_selector",
        "scope_alias",
        "scope_helper",
        "model_reader",
        "trace_owner",
    ],
)
def test_counterfeit_or_removed_registry_owner_is_not_a_basis(
    tmp_path, monkeypatch, override: str
) -> None:
    import polisyos.scientist.methods.search.judge_thresholds as owner
    from polisyos.foundry.calibration import dp_ci

    registry = _registry(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    _frozen, selected = capture_judge_threshold_basis(store, registry)
    ids_before = store.iter_artifact_ids()
    if override == "instance":
        monkeypatch.setattr(registry, "snapshot", lambda: None)
    elif override == "class":
        monkeypatch.setattr(JudgeThresholdRegistry, "_load_snapshot", lambda _self: None)
    elif override == "resolver_helper":
        monkeypatch.setattr(owner, "_scope_match_score", lambda *_args: 999)
    elif override == "root_selector":
        monkeypatch.setattr(owner, "default_search_registry_root", lambda: tmp_path / "foreign")
    elif override == "scope_alias":
        monkeypatch.setattr(owner, "bucket_dp_epsilon", lambda *_args: "counterfeit")
    elif override == "scope_helper":
        monkeypatch.setattr(dp_ci, "_coerce_optional_float", lambda *_args: 0.0)
    elif override == "model_reader":
        monkeypatch.setattr(
            owner.JudgeThresholdSnapshot,
            "model_validate_json",
            classmethod(lambda _cls, *_args, **_kwargs: None),
        )
    else:
        from contextvars import ContextVar

        monkeypatch.setattr(owner, "_THRESHOLD_REQUIREMENTS", ContextVar("counterfeit"))
    with pytest.raises(ValueError, match="threshold_registry_owner_not_established"):
        capture_judge_threshold_basis(store, registry)
    assert resolve_judge_threshold_basis(store, selected, registry).status == "not_established"
    assert store.iter_artifact_ids() == ids_before


def test_changed_registry_selector_is_refused_before_its_callback(tmp_path, monkeypatch) -> None:
    import polisyos.scientist.methods.search.judge_thresholds as owner
    from polisyos.scientist.methods.search.judge_threshold_basis import (
        selected_judge_threshold_registry,
    )

    called = []

    def counterfeit():
        called.append(True)
        return tmp_path / "foreign"

    monkeypatch.setattr(owner, "default_search_registry_root", counterfeit)
    with pytest.raises(ValueError, match="threshold_registry_owner_not_established"):
        selected_judge_threshold_registry()
    assert called == []


def test_absent_and_nonfinite_registry_never_establish_a_basis(tmp_path) -> None:
    import json

    registry = JudgeThresholdRegistry(root=tmp_path / "registry")
    store = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match="threshold_registry_not_established"):
        capture_judge_threshold_basis(store, registry)
    registry.record(registry.snapshot().entries[0])
    path = registry._snapshot_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"][0]["threshold_value"] = float("nan")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="threshold_registry_invalid"):
        capture_judge_threshold_basis(store, registry)


def test_identical_snapshot_from_different_registry_is_not_current(tmp_path) -> None:
    registry = _registry(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    _frozen, ref = capture_judge_threshold_basis(store, registry)
    other = JudgeThresholdRegistry(root=tmp_path / "other")
    other._write_snapshot(registry.snapshot())
    assert other.snapshot() == registry.snapshot()
    result = resolve_judge_threshold_basis(store, ref, other)
    assert result.status == "stale"
    assert result.reason_code == "threshold_registry_source_changed"


def test_removing_selected_registry_after_capture_blocks_admission(tmp_path) -> None:
    registry = _registry(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    _frozen, ref = capture_judge_threshold_basis(store, registry)
    registry._snapshot_path().unlink()
    result = resolve_judge_threshold_basis(store, ref, registry)
    assert result.status == "not_established"
    assert result.reason_code == "threshold_registry_unavailable"


def test_changed_registry_implementation_digest_makes_old_basis_stale(tmp_path) -> None:
    registry = _registry(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    _frozen, ref = capture_judge_threshold_basis(store, registry)
    basis = load_judge_threshold_basis(store, ref)
    changed = basis.model_copy(update={"registry_implementation_sha256": "sha256:" + "0" * 64})
    manifest = store.get_manifest(ref)
    old_implementation = store.put_json(
        changed,
        PutOptions(
            kind=manifest.kind, media_type=manifest.media_type, schema=manifest.artifact_schema
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    result = resolve_judge_threshold_basis(store, old_implementation, registry)
    assert result.status == "stale"
    assert result.reason_code == "threshold_registry_implementation_changed"


def test_selected_implementation_digest_is_stable_across_hash_seeds() -> None:
    import os
    import subprocess
    import sys

    from polisyos.scientist.methods.search import judge_threshold_basis as owner

    command = (
        "from polisyos.scientist.methods.search.judge_threshold_basis "
        "import _REGISTRY_IMPLEMENTATION_SHA256; print(_REGISTRY_IMPLEMENTATION_SHA256)"
    )
    observed = []
    for seed in ("11", "29"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", command],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        observed.append(result.stdout.strip())
    assert observed == [owner._REGISTRY_IMPLEMENTATION_SHA256] * 2


def test_foreign_selected_profile_and_profileless_ref_are_not_basis(tmp_path) -> None:
    registry = _registry(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    _frozen, selected = capture_judge_threshold_basis(store, registry)
    manifest = store.get_manifest(selected)
    foreign = store.put_bytes(
        store.get_bytes(selected),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(name="test.ForeignThresholdBasis", version="1.0"),
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == selected.artifact_id
    assert foreign.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert resolve_judge_threshold_basis(store, foreign, registry).status == "invalid"
    legacy = selected.model_copy(update={"manifest_profile_sha256": None})
    assert resolve_judge_threshold_basis(store, legacy, registry).status == "not_established"
