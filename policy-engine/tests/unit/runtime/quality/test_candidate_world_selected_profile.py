"""WMR persistence exposes the exact selected view from the real CAS writer."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.runtime.quality.world_model_record import (
    WORLD_MODEL_RECORD_ARTIFACT_KIND,
    WorldModelBuildResult,
    WorldModelRecordError,
    build_world_model_record,
    load_world_model_record,
    persist_world_model_record,
)
from tests._helpers.world_model_record import _build_record, _substrate_registry

TENANT_ID = "82ce17a2-4df5-43a8-ad8a-a218d973739c"
CELL_ID = "1235b199-5c67-4ea4-8aa2-5ab728532ac5"


def _observe_real_world_writes(
    store: FileSystemCAS, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[bool, ArtifactRef]]:
    """Record the actual writer option and ref without replacing any write result."""
    writes: list[tuple[bool, ArtifactRef]] = []
    real_put_json = store.put_json

    def observe_real_write(
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        written = real_put_json(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )
        if opts.kind == WORLD_MODEL_RECORD_ARTIFACT_KIND:
            writes.append((return_selected_profile, written))
        return written

    monkeypatch.setattr(store, "put_json", observe_real_write)
    return writes


def _rebuild_world_fixture(
    store: FileSystemCAS,
    base: WorldModelBuildResult,
    model: ModelSpec,
    registry_ref: ArtifactRef,
    *,
    return_selected_profile: bool,
) -> WorldModelBuildResult:
    """Run the actual builder against the shared fixture's resolved substrates."""
    record = base.record
    assert record.data_forge_binding_ref.binding_path
    return build_world_model_record(
        store,
        fabric_world_ref=record.fabric_world_ref,
        data_forge_snapshot_binding_path=record.data_forge_binding_ref.binding_path,
        data_snapshot_ref=base.data_snapshot_ref,
        model_spec=model,
        skg_causal_prior_ref=record.skg_causal_prior_ref,
        substrate_registry=_substrate_registry(),
        registry_bundle_artifact_ref=registry_ref,
        region_or_jurisdiction=record.region_or_jurisdiction,
        population_scope=record.population_scope,
        policy_domain=record.policy_domain,
        valid_time_scope=record.valid_time_scope,
        tx_time_scope=record.tx_time_scope,
        resolution=record.resolution,
        branch_mode=record.branch_mode,
        policy_slot_ids=tuple(binding.slot_id for binding in record.policy_slot_map),
        producer_ref=record.producer_ref,
        data_forge_role=record.data_forge_binding_ref.role,
        required_substrate_families=("firm_fundamentals",),
        foundry_binding_rules=load_input_bindings(store, base.input_bindings_ref).rules,
        return_selected_profile=return_selected_profile,
    )


def test_persist_world_selected_profile_is_writer_result_and_reads_exact_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Selected reads cannot fall back to a default or a different schema view."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        store, base, _model, _registry_ref = _build_record(tmp_path)
        writes = _observe_real_world_writes(store, monkeypatch)
        legacy = persist_world_model_record(store, base.record)
        assert len(writes) == 1
        assert writes[0][0] is False
        assert legacy is writes[0][1]
        selected = persist_world_model_record(store, base.record, return_selected_profile=True)
        assert len(writes) == 2
        assert writes[1][0] is True
        assert selected is writes[1][1]
        assert selected.manifest_profile_sha256
        assert selected.artifact_id == legacy.artifact_id

        # Keep the real CAS write and corrupt only its delegated return so the
        # test distinguishes a selected-profile request from a profileless ref.
        real_put_json = store.put_json
        for fault in ("missing_profile", "wrong_kind", "wrong_media", "untyped"):

            def corrupt_selected_write(
                obj: object,
                opts: PutOptions,
                canon_spec: CanonSpec | None = None,
                *,
                return_selected_profile: bool = False,
                _fault: str = fault,
            ) -> ArtifactRef | None:
                written = real_put_json(
                    obj,
                    opts,
                    canon_spec=canon_spec,
                    return_selected_profile=return_selected_profile,
                )
                assert return_selected_profile and written.manifest_profile_sha256
                assert store.verify(written).ok
                if _fault == "untyped":
                    return None
                updates = {
                    "missing_profile": {"manifest_profile_sha256": None},
                    "wrong_kind": {"kind": "runtime.quality.foreign_world"},
                    "wrong_media": {"media_type": "text/plain"},
                }
                return written.model_copy(update=updates[_fault])

            with monkeypatch.context() as defective:
                defective.setattr(store, "put_json", corrupt_selected_write)
                with pytest.raises(
                    WorldModelRecordError, match="world_model_record_writer_profile_not_established"
                ):
                    persist_world_model_record(store, base.record, return_selected_profile=True)
        manifest = store.get_manifest_by_profile(
            selected.artifact_id, selected.manifest_profile_sha256
        )
        assert artifact_manifest_profile_sha256(manifest) == selected.manifest_profile_sha256
        reader = FileSystemCAS.open_existing_read_only(store.root)
        assert load_world_model_record(reader, selected) == base.record
        assert load_world_model_record(reader, legacy) == base.record

        wrong_schema = store.put_json(
            load_core_json_artifact(store, selected),
            PutOptions(
                kind=selected.kind,
                media_type="application/json",
                schema=SchemaInfo(name="test.UnrelatedWorldRecord", version="1.0"),
                inputs=list(manifest.inputs),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert wrong_schema.artifact_id == selected.artifact_id
        assert wrong_schema.manifest_profile_sha256 != selected.manifest_profile_sha256
        with pytest.raises(
            WorldModelRecordError, match="world_model_record_integrity_or_lineage_invalid"
        ):
            load_world_model_record(reader, wrong_schema)

        selected_path = store._manifest_path_for_ref(
            selected.artifact_id, selected.manifest_profile_sha256
        )
        held_path = selected_path.with_name(selected_path.name + ".held")
        assert not held_path.exists()
        selected_path.rename(held_path)
        try:
            with pytest.raises(
                WorldModelRecordError,
                match="world_model_record_integrity_or_lineage_invalid",
            ):
                load_world_model_record(reader, selected)
        finally:
            held_path.rename(selected_path)
        assert load_world_model_record(reader, selected) == base.record


def test_build_world_selected_profile_is_emitted_by_writer_and_legacy_default_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real builder forwards the selected-view request through persistence."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        store, base, model, registry_ref = _build_record(tmp_path)
        writes = _observe_real_world_writes(store, monkeypatch)
        selected = _rebuild_world_fixture(
            store, base, model, registry_ref, return_selected_profile=True
        )
        assert len(writes) == 1
        assert writes[0][0] is True
        assert selected.record_ref is writes[0][1]
        assert selected.record_ref.manifest_profile_sha256
        legacy = _rebuild_world_fixture(
            store, base, model, registry_ref, return_selected_profile=False
        )
        assert len(writes) == 2
        assert writes[1][0] is False
        assert legacy.record_ref is writes[1][1]
        reader = FileSystemCAS.open_existing_read_only(store.root)
        assert load_world_model_record(reader, selected.record_ref) == selected.record
        assert load_world_model_record(reader, legacy.record_ref) == legacy.record
