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
