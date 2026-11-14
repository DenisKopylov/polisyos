"""Real versioned WMR fixture over an already compiled selected-method case."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core import artifacts
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.quality import data_state_substrate as owner
from polisyos.runtime.quality.substrate_registry import (
    SubstrateRegistry,
    persist_substrate_registry,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    FabricWorldRef,
    WorldModelBuildResult,
    WorldModelLimitations,
    build_world_model_record,
)
from tests._helpers import world_model_record as world_fixture
from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase


def build_selected_method_base_world(
    case: ProgramGraphTaxSubsidyInputCase,
    tmp_path: Path,
    *,
    region_or_jurisdiction: str = "UA",
    population_scope: str = "population:government",
    policy_domain: str = "synthetic_accounting",
    resolution: str = "country_year",
    policy_slot_ids: Sequence[str] = ("government.balance", "agents.income"),
) -> tuple[WorldModelBuildResult, SubstrateRegistry, artifacts.ArtifactRef]:
    """Use the existing real publishers over the fixture's actual snapshot."""
    snapshot = artifacts.validate_core_model_json_artifact(
        DataSnapshot, case.store, case.data_snapshot_ref
    )
    snapshot_id = snapshot.stats.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise ValueError("selected_method_base_world_snapshot_version_missing")
    transaction = datetime(2026, 11, 14, tzinfo=UTC).isoformat()
    payload = artifacts.load_core_json_artifact(case.store, case.source_ref)
    binding_path = owner._write_data_forge_snapshot_binding(
        workspace_dir=tmp_path,
        snapshot_id=snapshot_id,
        payload=payload,
        payload_content_hash=str(case.source_ref.artifact_id),
        published_at=transaction,
        corpus_id="test-selected-method-base",
        builder_revision="test.derived-input-world",
        lineage_refs=(owner._cas_data_forge_ref(case.data_snapshot_ref),),
        claim_requirement_bindings=(
            {
                "claim_id": "test-selected-method-base",
                "requirement_id": "test-selected-method-base",
                "requirement_kind": "candidate_model_input",
                "authority_level": "candidate",
                "time_role": "transaction_time",
            },
        ),
    )
    fabric_root = owner._write_acquired_candidate_fabric_snapshot(
        workspace_dir=tmp_path,
        snapshot_id=snapshot_id,
        payload_hash=str(case.source_ref.artifact_id),
        transaction_time=transaction,
        as_of_valid_time=None,
    )
    registry = world_fixture._substrate_registry()
    registry_ref = persist_substrate_registry(case.store, registry)
    trinity = TrinityBundle.model_validate(
        artifacts.load_core_json_artifact(case.store, case.trinity_ref)
    )
    prior_bindings = load_input_bindings(case.store, case.input_bindings_ref)
    built = build_world_model_record(
        case.store,
        fabric_world_ref=FabricWorldRef(
            snapshot_root=str(fabric_root),
            snapshot_id=snapshot_id,
            branch="candidate",
            as_of_valid_time=None,
            as_of_tx_time=transaction,
            world_query_policy="default_allow_public",
            provenance_manifest_ref=f"cas://{case.source_ref.artifact_id.hex}",
        ),
        data_forge_snapshot_binding_path=binding_path,
        data_snapshot_ref=case.data_snapshot_ref,
        model_spec=trinity.model_spec,
        skg_causal_prior_ref=world_fixture._skg_ref(tmp_path, snapshot_id=snapshot_id),
        substrate_registry=registry,
        substrate_registry_artifact_ref=registry_ref,
        registry_bundle_artifact_ref=case.registry_bundle_ref,
        region_or_jurisdiction=region_or_jurisdiction,
        population_scope=population_scope,
        policy_domain=policy_domain,
        valid_time_scope="not_established",
        tx_time_scope=transaction,
        resolution=resolution,
        branch_mode=BranchMode.SCENARIO,
        policy_slot_ids=policy_slot_ids,
        producer_ref="test.derived-input-world.base",
        data_forge_role=owner._data_forge_snapshot_role(),
        foundry_binding_rules=list(prior_bindings.rules),
        program_graph_refs=(str(case.program_graph_ref.artifact_id),),
        program_graph_view_refs=(case.program_graph_ref,),
        limitations=WorldModelLimitations(
            admissibility_blockers=owner.ACQUIRED_DATA_STATE_LIMITATION_CODES
        ),
        candidate_only=True,
        return_selected_profile=True,
        select_foundry_input_profiles=True,
    )
    assert artifacts.artifact_ref_identity_key(built.input_bindings_ref) == (
        artifacts.artifact_ref_identity_key(case.input_bindings_ref)
    )
    return built, registry, registry_ref
