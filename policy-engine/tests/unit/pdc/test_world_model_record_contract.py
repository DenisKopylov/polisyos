from __future__ import annotations

from polisyos import pdc


def _world_model_record() -> pdc.WorldModelRecord:
    pending = pdc.WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        schema_version="policyos.runtime.world_model_record.v1",
        authority_status="bound",
        created_at="2026-08-31T00:00:00+00:00",
        producer_ref="test:world-model-record",
        content_hash="sha256:" + "0" * 64,
        region_or_jurisdiction="UA",
        population_scope="national",
        policy_domain="fiscal",
        valid_time_scope="2026",
        tx_time_scope="2026-08-31",
        resolution="household_month",
        branch_mode=pdc.BranchMode.OBSERVED,
        fabric_world_ref=pdc.FabricWorldRef(
            snapshot_root="/tmp/non-content-location",
            snapshot_id="snapshot-1",
            branch="main",
            world_query_policy="world-nodes-v1",
            provenance_manifest_ref="manifest:world",
            content_query_digest="sha256:" + "1" * 64,
            content_query_row_count=1,
        ),
        data_forge_binding_ref=pdc.DataForgeBindingRef(
            snapshot_id="snapshot-1",
            release_id="release-1",
            role="academic",
            read_api_identity="academic-v1",
            snapshot_ref="snapshot:1",
            merkle_root="merkle:1",
            data_hash="sha256:" + "2" * 64,
            provenance_manifest_ref="manifest:data-forge",
            binding_path="/tmp/non-content-binding.json",
        ),
        simulation_model_ref=pdc.SimulationModelRef(
            model_spec_ref="sha256:" + "3" * 64,
            model_spec_hash="sha256:" + "4" * 64,
            model_id="model-1",
            data_snapshot_ref="sha256:" + "5" * 64,
            registry_bundle_ref="sha256:" + "6" * 64,
            fidelity_level="structural",
        ),
        foundry_binding_ref=pdc.FoundryBindingRef(
            input_bindings_ref="sha256:" + "7" * 64,
            bound_state_snapshot_ref="sha256:" + "8" * 64,
            mapping_rules_ref="sha256:" + "9" * 64,
            state_slot_digest="sha256:" + "a" * 64,
        ),
        skg_causal_prior_ref=pdc.SkgCausalPriorRef(
            skg_snapshot_ref="duckdb:///tmp/non-content-path/prior.duckdb#v1",
            skg_version_id="1",
            source_data_snapshot_id="snapshot-1",
        ),
        substrate_registry_ref=pdc.SubstrateRegistryRef(
            substrate_version_id="substrate_version_0123456789abcdef",
            content_hash="sha256:" + "b" * 64,
            registry_artifact_ref="sha256:" + "c" * 64,
            resolved_entries=(
                pdc.ResolvedSubstrateEntryRef(
                    source_id="source-1",
                    family_id="family-1",
                    layer=pdc.SubstrateLayer.L2,
                    coverage_score=0.8,
                    trust_tier="admitted",
                    trust_cap=0.7,
                    identification_mode="point_identified",
                    schema_regime_id="regime-1",
                    data_version="v1",
                    snapshot_id="snapshot-1",
                    source_snapshot_id="snapshot-1",
                    entry_content_hash="sha256:" + "d" * 64,
                ),
            ),
        ),
        policy_slot_map=(
            pdc.PolicySlotBinding(
                slot_id="policy.tax_rate",
                state_path="government.tax_rate",
                entity_scope="national",
                temporal_granularity="month",
            ),
        ),
        limitations=pdc.WorldModelLimitations(),
        deployment_update_refs=pdc.DeploymentUpdateRefs(),
    )
    content_hash = pdc.world_model_record_content_hash(pending)
    return pdc.WorldModelRecord.model_validate(
        {
            **pending.model_dump(mode="json"),
            "world_model_record_id": (
                f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}"
            ),
            "content_hash": content_hash,
        }
    )


def test_world_model_record_runtime_module_reexports_pdc_contract_identities() -> None:
    from polisyos.runtime.quality import world_model_record as runtime_world_model_record

    names = (
        "BranchMode",
        "FabricWorldRef",
        "DataForgeBindingRef",
        "SimulationModelRef",
        "FoundryBindingRef",
        "SkgCausalPriorRef",
        "SubstrateLayer",
        "ResolvedSubstrateEntryRef",
        "SubstrateRegistryRef",
        "PolicySlotBinding",
        "WorldModelLimitations",
        "DeploymentUpdateRefs",
        "WorldModelArtifactViews",
        "WorldModelRecord",
        "world_model_record_content_hash",
    )

    assert {
        name: getattr(runtime_world_model_record, name) is getattr(pdc, name) for name in names
    } == dict.fromkeys(names, True)


def test_world_model_record_pdc_round_trip_preserves_schema_and_hash() -> None:
    record = _world_model_record()
    round_tripped = pdc.WorldModelRecord.model_validate_json(record.model_dump_json())

    assert round_tripped == record
    assert round_tripped.schema_version == "policyos.runtime.world_model_record.v1"
    assert pdc.WORLD_MODEL_RECORD_SCHEMA_NAME == "polisyos.runtime.quality.WorldModelRecord"
    assert pdc.WORLD_MODEL_RECORD_ARTIFACT_KIND == "runtime.quality.world_model_record"
    assert pdc.world_model_record_content_hash(round_tripped) == record.content_hash


def test_world_model_artifact_views_normalize_ref_subclasses_losslessly() -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.contracts.foundry import (
        FoundryInputBindingReportRef,
        FoundryInputBindingsRef,
        ProgramGraphRef,
        StateSnapshotRef,
    )

    def base_ref(label: str, kind: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id="sha256:" + label * 64,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "f" * 64,
        )

    inputs = {
        "data_snapshot_ref": base_ref("1", "fabric.data_snapshot"),
        "registry_bundle_ref": base_ref("2", "core.registry_bundle"),
        "model_spec_ref": base_ref("3", "ir.model_spec"),
        "input_bindings_ref": FoundryInputBindingsRef(
            **base_ref("4", "foundry.input_bindings").model_dump(mode="python")
        ),
        "bound_state_snapshot_ref": StateSnapshotRef(
            **base_ref("5", "foundry.state_snapshot").model_dump(mode="python")
        ),
        "input_binding_report_ref": FoundryInputBindingReportRef(
            **base_ref("6", "foundry.input_binding_report").model_dump(mode="python")
        ),
        "substrate_registry_ref": base_ref(
            "7", "runtime.quality.production_data_substrate_registry"
        ),
        "program_graph_refs": (
            ProgramGraphRef(
                **base_ref("8", "foundry.program_graph").model_dump(mode="python")
            ),
        ),
        "ncm_refs": (base_ref("9", "ir.ncm_spec"),),
    }

    views = pdc.WorldModelArtifactViews.model_validate(inputs)

    for field_name, original in inputs.items():
        normalized = getattr(views, field_name)
        if isinstance(original, tuple):
            assert isinstance(normalized, tuple)
            assert len(normalized) == len(original)
            for actual_ref, original_ref in zip(normalized, original, strict=True):
                assert type(actual_ref) is ArtifactRef
                assert actual_ref.model_dump(mode="python") == original_ref.model_dump(
                    mode="python"
                )
        else:
            assert type(normalized) is ArtifactRef
            assert normalized.model_dump(mode="python") == original.model_dump(
                mode="python"
            )


def test_world_model_record_v1_projection_omits_new_view_bundle() -> None:
    record = _world_model_record()

    assert record.artifact_views is None
    assert "artifact_views" not in record.model_dump(mode="json")
    assert "artifact_views" not in pdc.serialize_world_model_record_for_storage(record)
    assert pdc.world_model_record_content_hash(record) == record.content_hash


def test_world_model_record_v2_hash_binds_ordered_program_and_ncm_views() -> None:
    from polisyos.core.artifacts import ArtifactRef

    base = _world_model_record()
    graph_id = "sha256:" + "e" * 64
    ncm_id = "sha256:" + "f" * 64

    def build_record(profile: str) -> pdc.WorldModelRecord:
        views = pdc.WorldModelArtifactViews(
            data_snapshot_ref=ArtifactRef(
                artifact_id=base.simulation_model_ref.data_snapshot_ref,
                kind="fabric.data_snapshot",
                media_type="application/json",
            ),
            registry_bundle_ref=ArtifactRef(
                artifact_id=base.simulation_model_ref.registry_bundle_ref,
                kind="core.registry_bundle",
                media_type="application/json",
            ),
            model_spec_ref=ArtifactRef(
                artifact_id=base.simulation_model_ref.model_spec_ref,
                kind="ir.model_spec",
                media_type="application/json",
            ),
            input_bindings_ref=ArtifactRef(
                artifact_id=base.foundry_binding_ref.input_bindings_ref,
                kind="foundry.input_bindings",
                media_type="application/json",
            ),
            bound_state_snapshot_ref=ArtifactRef(
                artifact_id=base.foundry_binding_ref.bound_state_snapshot_ref,
                kind="foundry.state_snapshot",
                media_type="application/json",
            ),
            input_binding_report_ref=ArtifactRef(
                artifact_id=base.foundry_binding_ref.mapping_rules_ref,
                kind="foundry.input_binding_report",
                media_type="application/json",
            ),
            substrate_registry_ref=ArtifactRef(
                artifact_id=base.substrate_registry_ref.registry_artifact_ref,
                kind="runtime.quality.production_data_substrate_registry",
                media_type="application/json",
            ),
            program_graph_refs=(
                ArtifactRef(
                    artifact_id=graph_id,
                    kind="foundry.program_graph",
                    media_type="application/json",
                    manifest_profile_sha256=profile,
                ),
            ),
            ncm_refs=(
                ArtifactRef(
                    artifact_id=ncm_id,
                    kind="ir.ncm_spec",
                    media_type="application/json",
                    manifest_profile_sha256=profile,
                ),
            ),
        )
        fields = base.model_dump(mode="json")
        fields.update(
            {
                "schema_version": pdc.WORLD_MODEL_RECORD_SCHEMA_V2_VERSION,
                "simulation_model_ref": {
                    **fields["simulation_model_ref"],
                    "program_graph_refs": [graph_id],
                    "ncm_refs": [ncm_id],
                },
                "artifact_views": views.model_dump(mode="json"),
                "world_model_record_id": "world_model_record_0000000000000000",
                "content_hash": "sha256:" + "0" * 64,
            }
        )
        content_hash = pdc.world_model_record_content_hash_from_fields(fields)
        fields["content_hash"] = content_hash
        fields["world_model_record_id"] = (
            f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}"
        )
        return pdc.WorldModelRecord.model_validate(fields)

    first = build_record("sha256:" + "1" * 64)
    sibling = build_record("sha256:" + "2" * 64)

    assert first.simulation_model_ref.program_graph_refs == (
        sibling.simulation_model_ref.program_graph_refs
    )
    assert first.simulation_model_ref.ncm_refs == sibling.simulation_model_ref.ncm_refs
    assert first.artifact_views is not None and sibling.artifact_views is not None
    assert first.content_hash != sibling.content_hash
