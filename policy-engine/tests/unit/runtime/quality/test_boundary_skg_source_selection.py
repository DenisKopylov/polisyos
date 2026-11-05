"""Keep boundary SKG priors bound to selected typed L2 source entries."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.runtime.quality.generation_cycle import _build_boundary_world_model_record
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateRegistryEntry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecord, WorldModelRecordError
from tests._helpers.controlled_candidate_profile import _problem

_READINESS = "production_data_root_manifest.readiness"
_ACTUAL_STORE = "l2.duckdb.real_store.table_coverage"


def _l2_entry(
    *,
    source_id: str,
    coverage_kind: str,
    identification_mode: str,
) -> SubstrateRegistryEntry:
    """Build one content-addressed L2 registration through the registry owner."""
    data_version = f"{source_id}:v1"
    registration = SubstrateRegistration(
        source_id=source_id,
        family_id="l2_scholar_kg_causal_priors_transport",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.74,
            coverage_kind=coverage_kind,
            coverage_rule_ref=f"{source_id}#coverage",
            dataset_count=1,
            metric_binding_count=3,
            observation_count=7,
        ),
        trust_tier=SubstrateTrustTier(
            tier="derived_proxy",
            trust_cap=0.5,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref=f"{source_id}#trust",
        ),
        identification_mode=identification_mode,
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"{source_id}.schema.v1",
            authority_ref=f"{source_id}#schema",
            source_version=data_version,
        ),
        data_version=data_version,
        snapshot_id=f"{source_id}:snapshot",
        source_snapshot_id=f"{source_id}:source-snapshot",
        provenance_refs=(f"{source_id}#provenance",),
        authority_refs=(f"{source_id}#authority",),
    )
    return build_substrate_registry_entry(registration)


def _readiness_entry_before(
    *actual_entries: SubstrateRegistryEntry,
) -> SubstrateRegistryEntry:
    """Select a readiness entry whose hash sorts before every actual L2 row."""
    actual_hashes = tuple(entry.entry_content_hash for entry in actual_entries)
    for index in range(64):
        readiness = _l2_entry(
            source_id=f"production_data:scholar_bundle_{index}",
            coverage_kind=_READINESS,
            identification_mode="scholarly_prior_not_direct_identification",
        )
        if readiness.entry_content_hash < min(actual_hashes):
            return readiness
    raise AssertionError("lower_hash_readiness_registration_not_found")


def _registry(*entries: SubstrateRegistryEntry) -> SubstrateRegistry:
    return build_substrate_registry(
        entries,
        producer_ref="tests.unit.runtime.quality.test_boundary_skg_source_selection",
        source_catalog_refs=("fixture://boundary-substrate-registry",),
    )


def _boundary_world(
    registry: SubstrateRegistry, selected_hashes: tuple[str, ...]
) -> WorldModelRecord:
    return _build_boundary_world_model_record(
        repo_root=Path(__file__).resolve().parents[4],
        problem=_problem("boundary_skg_source_selection"),
        outcome="firm_survival",
        policy_slot_ids=("firm_survival",),
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_hashes,
    )


def test_manifest_readiness_entry_does_not_become_an_skg_prior() -> None:
    readiness = _l2_entry(
        source_id="production_data:scholar_bundle",
        coverage_kind=_READINESS,
        identification_mode="scholarly_prior_not_direct_identification",
    )
    registry = _registry(readiness)

    with pytest.raises(WorldModelRecordError) as raised:
        _boundary_world(registry, (readiness.entry_content_hash,))

    assert raised.value.code == "boundary_skg_source_not_established"


def test_actual_store_prior_is_selected_without_truncating_registry_census() -> None:
    actual = _l2_entry(
        source_id="l2_scholar_kg:scholar_knowledge.duckdb",
        coverage_kind=_ACTUAL_STORE,
        identification_mode="credal_interval_prior",
    )
    readiness = _readiness_entry_before(actual)
    registry = _registry(readiness, actual)
    selected_hashes = tuple(entry.entry_content_hash for entry in registry.entries)
    record = _boundary_world(registry, selected_hashes)

    assert readiness.entry_content_hash < actual.entry_content_hash
    assert record.skg_causal_prior_ref.skg_snapshot_ref == actual.provenance_refs[0]
    assert record.skg_causal_prior_ref.skg_version_id == actual.data_version
    assert record.skg_causal_prior_ref.source_data_snapshot_id == actual.source_snapshot_id
    assert record.data_forge_binding_ref.read_api_identity == readiness.source_id
    assert record.data_forge_binding_ref.snapshot_ref == readiness.provenance_refs[0]
    assert record.substrate_registry_ref.content_hash == registry.content_hash
    assert {
        item.entry_content_hash for item in record.substrate_registry_ref.resolved_entries
    } == set(selected_hashes)
    assert record.fabric_world_ref.content_query_row_count == len(selected_hashes)


def test_actual_store_prior_precedes_a_lower_hash_custom_candidate_prior() -> None:
    actual = _l2_entry(
        source_id="l2_scholar_kg:scholar_knowledge.duckdb",
        coverage_kind=_ACTUAL_STORE,
        identification_mode="credal_interval_prior",
    )
    for index in range(64):
        custom = _l2_entry(
            source_id=f"custom_candidate_prior:{index}",
            coverage_kind="controlled_synthetic_prior",
            identification_mode="not_established",
        )
        if custom.entry_content_hash < actual.entry_content_hash:
            break
    assert custom.entry_content_hash < actual.entry_content_hash
    registry = _registry(custom, actual)
    selected = tuple(entry.entry_content_hash for entry in registry.entries)

    record = _boundary_world(registry, selected)

    assert record.skg_causal_prior_ref.skg_snapshot_ref == actual.provenance_refs[0]
    assert record.data_forge_binding_ref.snapshot_ref == custom.provenance_refs[0]
    assert {
        item.entry_content_hash for item in record.substrate_registry_ref.resolved_entries
    } == set(selected)


def test_multiple_custom_candidate_priors_do_not_create_an_arbitrary_fallback() -> None:
    custom = tuple(
        _l2_entry(
            source_id=f"custom_candidate_prior:{index}",
            coverage_kind="controlled_synthetic_prior",
            identification_mode="not_established",
        )
        for index in range(2)
    )
    registry = _registry(*custom)

    with pytest.raises(WorldModelRecordError) as raised:
        _boundary_world(registry, tuple(entry.entry_content_hash for entry in registry.entries))

    assert raised.value.code == "boundary_skg_source_ambiguous"


def test_multiple_selected_actual_store_priors_are_ambiguous() -> None:
    actual_a = _l2_entry(
        source_id="l2_scholar_kg:scholar_knowledge_a.duckdb",
        coverage_kind=_ACTUAL_STORE,
        identification_mode="credal_interval_prior",
    )
    actual_b = _l2_entry(
        source_id="l2_scholar_kg:scholar_knowledge_b.duckdb",
        coverage_kind=_ACTUAL_STORE,
        identification_mode="credal_interval_prior",
    )
    readiness = _readiness_entry_before(actual_a, actual_b)
    registry = _registry(readiness, actual_a, actual_b)
    selected_hashes = tuple(entry.entry_content_hash for entry in registry.entries)

    with pytest.raises(WorldModelRecordError) as raised:
        _boundary_world(registry, selected_hashes)

    assert raised.value.code == "boundary_skg_source_ambiguous"


def test_unselected_actual_store_entry_is_not_borrowed_from_full_registry() -> None:
    actual = _l2_entry(
        source_id="l2_scholar_kg:scholar_knowledge.duckdb",
        coverage_kind=_ACTUAL_STORE,
        identification_mode="credal_interval_prior",
    )
    readiness = _readiness_entry_before(actual)
    registry = _registry(readiness, actual)

    with pytest.raises(WorldModelRecordError) as raised:
        _boundary_world(registry, (readiness.entry_content_hash,))

    assert raised.value.code == "boundary_skg_source_not_established"


def test_one_explicit_custom_l2_prior_remains_a_candidate_input() -> None:
    custom = _l2_entry(
        source_id="lane0:l2_causal_prior_candidate",
        coverage_kind="lane0.causal_claim_coverage",
        identification_mode="causal_prior_candidate",
    )
    registry = _registry(custom)
    record = _boundary_world(registry, (custom.entry_content_hash,))

    assert record.skg_causal_prior_ref.skg_snapshot_ref == custom.provenance_refs[0]
    assert record.skg_causal_prior_ref.skg_version_id == custom.data_version
    assert record.skg_causal_prior_ref.source_data_snapshot_id == custom.source_snapshot_id
    assert record.substrate_registry_ref.resolved_entries[0].entry_content_hash == (
        custom.entry_content_hash
    )
