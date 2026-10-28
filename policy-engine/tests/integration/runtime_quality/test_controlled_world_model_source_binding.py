"""Persisted fixture source binding through configured base and child profiles.

This is a candidate-only fixture bridge test. It does not run ordinary N4,
planner acquisition, ForecastOwner or predictive S10 and grants no authority.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
from polisyos.runtime.quality.world_model_record import load_world_model_record
from tests._helpers.controlled_candidate_profile import (
    _build_configured_procurement_profile,
    _capture_controlled_skg_source,
    _problem,
    _seed_controlled_selected_skg_source,
)
from tests._helpers.generic_n4_served_replay import _generic_profile_for_selection

_TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL = "controlled-source-profiles"


@pytest.fixture
def store(cas_root: Path) -> FileSystemCAS:
    """Record real fixture ownership before the fresh authorized reader opens it."""
    return FileSystemCAS(cas_root, tenant_id=_TENANT, cell_id=_CELL, ownership_enforced=True)


@pytest.mark.integration
def test_configured_base_and_child_reopen_the_independently_admitted_source(
    tmp_path: Path, store: FileSystemCAS
) -> None:
    """Actual source/WMR owners carry one SKG identity into fresh profile reads."""
    problem = _problem("controlled_source_profiles")
    source_root = tmp_path / "admitted-skg-input"
    selected = _seed_controlled_selected_skg_source(
        tmp_path, source_root=source_root, recorded_problem=problem
    )
    source_tree = {
        str(path.relative_to(source_root)): (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        for path in sorted(source_root.rglob("*"))
    }
    base_profile, declaration, base_build = _build_configured_procurement_profile(
        recorded_problem=problem,
        artifact_store=store,
        tenant_id=_TENANT,
        cell_id=_CELL,
        tmp_path=tmp_path / "base-output",
        source_root=source_root,
        selected_skg_source=selected,
    )
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        registry_ref = persist_substrate_registry(
            store, base_profile.context_inputs.substrate_registry
        )
    arguments = {
        "source_root": source_root,
        "base_profile": base_profile,
        "base_declaration": declaration,
        "profile_id": "controlled-source-child",
        "profile_selection_ref": gy_content_hash({"fixture": "independent-source-child"}),
        "profile_selection_kind": "n4_candidate_child",
        "target_world_slot": base_profile.rule.target_world_slot,
        "operator_kind": base_profile.rule.operator_kind,
        "store": store,
        "substrate_registry_ref": registry_ref,
        "selected_skg_source": selected,
        "tenant_id": _TENANT,
        "cell_id": _CELL,
    }
    child = _generic_profile_for_selection(tmp_path=tmp_path / "child-output", **arguments)
    fresh = FileSystemCAS(store.root, tenant_id=_TENANT, cell_id=_CELL, ownership_enforced=True)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        base = load_world_model_record(fresh, base_build.record_ref)
        child_world = load_world_model_record(fresh, child.world_model_record_ref)
        assert fresh.verify(base_build.record_ref).ok
        assert fresh.verify(child.world_model_record_ref).ok
    assert base == base_profile.context_inputs.world_model_record
    assert child_world == child.context_inputs.world_model_record
    assert base_build.record_ref.artifact_id != child.world_model_record_ref.artifact_id
    assert base.skg_causal_prior_ref == child_world.skg_causal_prior_ref
    assert base.skg_causal_prior_ref.skg_snapshot_ref == selected.snapshot_ref
    assert base.skg_causal_prior_ref.skg_version_id == str(selected.version_id)
    for record, owner in ((base, "base-output"), (child_world, "child-output")):
        assert record.authority_status == "limited"
        assert record.foundry_binding_ref.input_bindings_ref
        assert record.foundry_binding_ref.bound_state_snapshot_ref
        assert Path(record.fabric_world_ref.snapshot_root) == (
            tmp_path / owner / "controlled-candidate-source/fabric-world"
        )
    assert {
        str(path.relative_to(source_root)): (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        for path in sorted(source_root.rglob("*"))
    } == source_tree

    foreign_root = tmp_path / "foreign-skg"
    foreign_root.mkdir()
    foreign_path = foreign_root / selected.db_path.name
    shutil.copyfile(selected.db_path, foreign_path)
    foreign = _capture_controlled_skg_source(foreign_path)
    assert foreign.sha256 == selected.sha256
    assert foreign.schema_sha256 == selected.schema_sha256
    with pytest.raises(ValueError, match=r"^controlled_selected_skg_source_path_mismatch$"):
        _generic_profile_for_selection(
            tmp_path=tmp_path / "rejected-child-output",
            **{**arguments, "selected_skg_source": foreign},
        )
    assert not (tmp_path / "rejected-child-output/controlled-candidate-source").exists()
