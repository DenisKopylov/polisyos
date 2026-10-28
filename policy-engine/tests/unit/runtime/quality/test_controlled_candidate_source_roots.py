"""Behavioral tests for independent controlled SKG inputs and WMR outputs."""

from __future__ import annotations

import hashlib
import shutil
import stat
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
from polisyos.runtime.quality.world_model_record import load_world_model_record
from tests._helpers.controlled_candidate_profile import (
    ControlledSKGSourceSelection,
    _build_configured_procurement_profile,
    _capture_controlled_skg_source,
    _controlled_profile_cycle_basis,
    _materialize_controlled_world_model_build,
    _problem,
    _seed_controlled_selected_skg_source,
    _validate_controlled_skg_source,
)

_TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL = "controlled-source-roots"


@pytest.fixture
def store(cas_root: Path) -> FileSystemCAS:
    """Record real fixture ownership before the fresh authorized reader opens it."""
    return FileSystemCAS(cas_root, tenant_id=_TENANT, cell_id=_CELL, ownership_enforced=True)


def _input_tree(root: Path) -> dict[str, str | None]:
    """Hash every file and retain every directory in this small fixture root."""
    return {
        str(path.relative_to(root)): (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        for path in sorted(root.rglob("*"))
    }


def _build(
    *,
    tmp_path: Path,
    store: FileSystemCAS,
    source_root: Path | None = None,
    selected: ControlledSKGSourceSelection | None = None,
) -> tuple[ControlledSKGSourceSelection, Any]:
    problem = _problem("controlled_source_roots")
    source = selected or _seed_controlled_selected_skg_source(
        tmp_path, source_root=source_root, recorded_problem=problem
    )
    _, context = _controlled_profile_cycle_basis(problem)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        registry_ref = persist_substrate_registry(store, context.substrate_registry)
    built = _materialize_controlled_world_model_build(
        source_world_model_record=context.world_model_record,
        artifact_store=store,
        tmp_path=tmp_path,
        source_root=source_root,
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        substrate_registry_ref=registry_ref,
        policy_slot_ids=("government_balance",),
        selected_skg_source=source,
        tenant_id=_TENANT,
        cell_id=_CELL,
    )
    return source, built


def _reopen(store: FileSystemCAS, built: Any) -> Any:
    fresh = FileSystemCAS(store.root, tenant_id=_TENANT, cell_id=_CELL, ownership_enforced=True)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        assert fresh.verify(built.record_ref).ok
        observed = load_world_model_record(fresh, built.record_ref)
    assert observed == built.record
    return observed


def test_materializer_preserves_the_legacy_root_and_fresh_record(
    tmp_path: Path, store: FileSystemCAS
) -> None:
    source, built = _build(tmp_path=tmp_path, store=store)
    observed = _reopen(store, built)
    assert (
        source.db_path == (tmp_path / "controlled-candidate-source/academic-skg.duckdb").resolve()
    )
    assert observed.skg_causal_prior_ref.skg_snapshot_ref == source.snapshot_ref
    assert observed.skg_causal_prior_ref.skg_version_id == str(source.version_id)
    assert Path(observed.fabric_world_ref.snapshot_root) == (
        tmp_path / "controlled-candidate-source/fabric-world"
    )


@pytest.mark.parametrize("protect_input", [False, True], ids=["writable", "read_only"])
def test_materializer_keeps_admitted_input_unchanged_and_outputs_separate(
    tmp_path: Path, store: FileSystemCAS, protect_input: bool
) -> None:
    """The root is chosen before seeding, independently of the selected path."""
    source_root = tmp_path / "admitted-input"
    output_root = tmp_path / "owned-output"
    source = _seed_controlled_selected_skg_source(
        output_root,
        source_root=source_root,
        recorded_problem=_problem("controlled_source_roots"),
    )
    before = _input_tree(source_root)
    original_modes = {
        path: stat.S_IMODE(path.stat().st_mode) for path in (source_root, *source_root.rglob("*"))
    }
    try:
        if protect_input:
            for path in original_modes:
                path.chmod(0o555 if path.is_dir() else 0o444)
        selected, built = _build(
            tmp_path=output_root, store=store, source_root=source_root, selected=source
        )
        assert _input_tree(source_root) == before, "admitted_input_tree_changed"
        observed = _reopen(store, built)
        assert selected == source
        assert Path(observed.fabric_world_ref.snapshot_root) == (
            output_root / "controlled-candidate-source/fabric-world"
        )
        assert (output_root / "controlled-candidate-source/fabric-world.duckdb").is_file()
        assert (
            output_root
            / "controlled-candidate-source/data-forge/controlled-candidate-source-v1"
            / "data_forge_snapshot_binding.json"
        ).is_file()
        assert observed.skg_causal_prior_ref.skg_snapshot_ref == source.snapshot_ref
        assert observed.skg_causal_prior_ref.skg_version_id == str(source.version_id)
        assert _validate_controlled_skg_source(source) is source
    finally:
        # Restore only this test's own permissions for normal pytest tmp cleanup.
        for path, mode in original_modes.items():
            path.chmod(mode)


def test_configured_no_selection_seeds_the_independently_admitted_root(
    tmp_path: Path, store: FileSystemCAS
) -> None:
    """The fallback producer forwards the root before its materializer reads it."""
    source_root = tmp_path / "admitted-new-source"
    output_root = tmp_path / "profile-output"
    profile, _declaration, built = _build_configured_procurement_profile(
        recorded_problem=_problem("configured_source_roots"),
        artifact_store=store,
        tenant_id=_TENANT,
        cell_id=_CELL,
        tmp_path=output_root,
        source_root=source_root,
    )
    source = _capture_controlled_skg_source(source_root / "academic-skg.duckdb")
    observed = _reopen(store, built)
    assert observed == profile.context_inputs.world_model_record
    assert observed.skg_causal_prior_ref.skg_snapshot_ref == source.snapshot_ref
    assert observed.skg_causal_prior_ref.skg_version_id == str(source.version_id)
    assert not (output_root / "controlled-candidate-source/academic-skg.duckdb").exists()
    assert not (source_root / "fabric-world").exists()
    assert not (source_root / "data-forge").exists()
    assert Path(observed.fabric_world_ref.snapshot_root) == (
        output_root / "controlled-candidate-source/fabric-world"
    )


def test_materializer_rejects_foreign_root_even_with_identical_bytes(
    tmp_path: Path, store: FileSystemCAS
) -> None:
    source_root = tmp_path / "admitted-input"
    source = _seed_controlled_selected_skg_source(
        tmp_path, source_root=source_root, recorded_problem=_problem("controlled_source_roots")
    )
    foreign_root = tmp_path / "foreign-input"
    foreign_root.mkdir()
    foreign_path = foreign_root / source.db_path.name
    shutil.copyfile(source.db_path, foreign_path)
    foreign = _capture_controlled_skg_source(foreign_path)
    assert foreign.sha256 == source.sha256
    assert foreign.schema_sha256 == source.schema_sha256
    before = _input_tree(source_root)
    output_root = tmp_path / "refused-output"
    with pytest.raises(ValueError, match=r"^controlled_selected_skg_source_path_mismatch$"):
        _build(tmp_path=output_root, store=store, source_root=source_root, selected=foreign)
    assert _input_tree(source_root) == before
    assert not (output_root / "controlled-candidate-source").exists()


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("version_id", 2, "controlled_selected_skg_source_ref_mismatch"),
        ("snapshot_ref", "duckdb:///foreign#v1", "controlled_selected_skg_source_ref_mismatch"),
        ("schema_sha256", "0" * 64, "controlled_selected_skg_source_schema_mismatch"),
    ],
)
def test_materializer_retains_selected_source_identity_checks(
    tmp_path: Path, store: FileSystemCAS, field: str, value: Any, reason: str
) -> None:
    source_root = tmp_path / "admitted-input"
    source = _seed_controlled_selected_skg_source(
        tmp_path, source_root=source_root, recorded_problem=_problem("controlled_source_roots")
    )
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        _build(
            tmp_path=tmp_path / "output",
            store=store,
            source_root=source_root,
            selected=replace(source, **{field: value}),
        )


def test_materializer_rejects_changed_bytes_then_reopens_restored_source(
    tmp_path: Path, store: FileSystemCAS
) -> None:
    source_root = tmp_path / "admitted-input"
    source = _seed_controlled_selected_skg_source(
        tmp_path, source_root=source_root, recorded_problem=_problem("controlled_source_roots")
    )
    original = source.db_path.read_bytes()
    source.db_path.write_bytes(original + b"source-byte-control")
    try:
        with pytest.raises(ValueError, match=r"^controlled_selected_skg_source_bytes_mismatch$"):
            _build(
                tmp_path=tmp_path / "rejected-output",
                store=store,
                source_root=source_root,
                selected=source,
            )
    finally:
        source.db_path.write_bytes(original)
    assert source.db_path.read_bytes() == original
    assert _validate_controlled_skg_source(source) is source
    _, built = _build(
        tmp_path=tmp_path / "restored-output",
        store=store,
        source_root=source_root,
        selected=source,
    )
    assert _reopen(store, built).skg_causal_prior_ref.skg_snapshot_ref == source.snapshot_ref
