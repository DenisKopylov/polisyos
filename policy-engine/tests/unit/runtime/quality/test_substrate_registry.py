from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality.substrate_registry import (
    L5CatalogAuthority,
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistryError,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry_from_existing_catalogs,
    default_substrate_catalog_paths,
    load_l5_catalog_authority,
    load_substrate_registry,
    persist_substrate_registry,
    register_substrate_entry,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
L5_TRUST_TIER_IDS = (
    "administrative_noisy",
    "authoritative_high_coverage",
    "authoritative_partial_coverage",
    "derived_proxy",
    "weak_anchor",
)


def _future_registration(
    schema_regime: SubstrateSchemaRegime,
    *,
    trust_tier: SubstrateTrustTier | None = None,
) -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id="acquisition:test_future_source",
        family_id="future_observation_family",
        layer=SubstrateLayer.L4,
        coverage=SubstrateCoverage(
            coverage_score=0.42,
            coverage_kind="acquisition_receipt.coverage",
            coverage_rule_ref="receipt://acquisition/test-future-source#coverage",
            dataset_count=1,
            metric_binding_count=1,
        ),
        trust_tier=trust_tier
        or SubstrateTrustTier(
            tier="weak_anchor",
            trust_cap=0.25,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref="repo://measurement_registry.json#/trust_tiers/weak_anchor",
        ),
        identification_mode="bounds_only",
        schema_regime=schema_regime,
        data_version="future-source-v1",
        snapshot_id="future-source-snapshot-v1",
        source_snapshot_id="future-source-snapshot-v1",
        provenance_refs=("receipt://acquisition/test-future-source",),
        authority_refs=("repo://measurement_registry.json",),
    )


def test_substrate_registry_lifts_l5_and_l1_catalog_authority() -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)

    firm = registry.resolve(family_id="firm_fundamentals", layer=SubstrateLayer.L5)[0]
    assert firm.coverage.coverage_score == l5.coverage_rules["firm_fundamentals"]
    assert firm.coverage.coverage_rule_ref.endswith(
        "measurement_registry.json#measurement_registry#/coverage_rules/firm_fundamentals"
    )
    assert firm.identification_mode == l5.identification_modes["firm_fundamentals"]
    assert firm.trust_tier.tier == "authoritative_partial_coverage"
    assert firm.schema_regime.schema_regime_id == "ukraine_schema_v2"

    proxy = registry.resolve(family_id="household_distribution", layer=SubstrateLayer.L5)[0]
    expected_proxy_tier = l5.expected_trust_tier("household_distribution")
    assert proxy.identification_mode == "proxy_identified"
    assert proxy.trust_tier.tier == expected_proxy_tier.tier
    assert proxy.trust_tier.trust_cap == expected_proxy_tier.trust_cap

    partial = registry.resolve(family_id="distress_enforcement", layer=SubstrateLayer.L5)[0]
    assert partial.coverage.coverage_score == 0.6
    assert partial.coverage.coverage_score < 1.0
    assert partial.identification_mode == "partially_identified"
    assert partial.trust_tier.tier == "authoritative_partial_coverage"

    weak_l1 = registry.resolve(
        source_id="l1_dcat:data_gov_ua_broad",
        family_id="dcat_source:data_gov_ua_broad",
        layer=SubstrateLayer.L1,
    )[0]
    assert weak_l1.coverage.dataset_count == 39848
    assert weak_l1.coverage.quality_scores["min_execution_readiness"] == pytest.approx(0.16)
    assert weak_l1.trust_tier.tier == "weak_anchor"
    assert weak_l1.trust_tier.trust_cap == l5.trust_tiers["weak_anchor"].trust_cap

    assert registry.substrate_version_id.startswith("substrate_version_")
    assert registry.content_hash.startswith("sha256:")
    assert {entry.layer for entry in registry.entries} >= {
        SubstrateLayer.L1,
        SubstrateLayer.L2,
        SubstrateLayer.L3,
        SubstrateLayer.L4,
        SubstrateLayer.L5,
        SubstrateLayer.L6,
    }


def test_substrate_registry_registers_l6_intervention_control_artifacts() -> None:
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)

    expected = {
        "l6_intervention_knob_dictionary": "intervention_lever_space",
        "l6_lex_intervention_map": "law_to_lever_route_candidate",
        "l6_observation_contract_routes": "value_method_route",
        "l6_policy_scenario_templates": "scenario_template_catalog_deferred",
    }
    for family_id, identification_mode in expected.items():
        entry = registry.resolve(family_id=family_id, layer=SubstrateLayer.L6)[0]
        assert entry.identification_mode == identification_mode
        assert entry.coverage.coverage_score == 1.0
        assert entry.coverage.observation_count and entry.coverage.observation_count > 0
        assert entry.snapshot_id.startswith(f"{family_id}:sha256:")
        assert any(family_id.removeprefix("l6_") in ref for ref in entry.provenance_refs)


def test_l5_trust_tier_selection_uses_numeric_content_not_tier_names() -> None:
    l5 = L5CatalogAuthority(
        measurement_registry_ref="repo://synthetic/measurement_registry.json#measurement_registry",
        identification_mode_registry_ref="repo://synthetic/identification_mode_registry.json#identification_mode_registry",
        schema_regime_registry_ref="repo://synthetic/schema_regime_registry.json#schema_regime_registry",
        coverage_rules={
            "low_family": 0.2,
            "mid_family": 0.5,
            "high_family": 0.9,
        },
        trust_tiers={
            "authoritative_low_name": SubstrateTrustTier(
                tier="authoritative_low_name",
                trust_cap=0.2,
                trust_multiplier=0.2,
                min_coverage=0.0,
                max_coverage=0.3,
                authority_ref="repo://synthetic/measurement_registry.json#/trust_tiers/authoritative_low_name",
            ),
            "mid_name": SubstrateTrustTier(
                tier="mid_name",
                trust_cap=0.6,
                trust_multiplier=0.6,
                min_coverage=0.3,
                max_coverage=0.7,
                authority_ref="repo://synthetic/measurement_registry.json#/trust_tiers/mid_name",
            ),
            "proxy_high_name": SubstrateTrustTier(
                tier="proxy_high_name",
                trust_cap=0.95,
                trust_multiplier=0.95,
                min_coverage=0.7,
                max_coverage=1.0,
                authority_ref="repo://synthetic/measurement_registry.json#/trust_tiers/proxy_high_name",
            ),
        },
        proxy_mappings={},
        identification_modes={
            "low_family": "proxy_identified",
            "mid_family": "proxy_identified",
            "high_family": "proxy_identified",
        },
        schema_regimes={},
    )

    low = l5.expected_trust_tier("low_family")
    mid = l5.expected_trust_tier("mid_family")
    high = l5.expected_trust_tier("high_family")

    assert (low.tier, low.trust_cap) == ("authoritative_low_name", 0.2)
    assert (mid.tier, mid.trust_cap) == ("mid_name", 0.6)
    assert (high.tier, high.trust_cap) == ("proxy_high_name", 0.95)
    assert low.trust_cap < mid.trust_cap < high.trust_cap


def test_substrate_registry_registration_is_free_grow_and_changes_version() -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    registration = _future_registration(l5.latest_schema_regime())

    updated = register_substrate_entry(registry, registration, l5_authority=l5)
    resolved = updated.resolve(
        source_id="acquisition:test_future_source",
        family_id="future_observation_family",
        layer=SubstrateLayer.L4,
    )[0]

    assert updated.substrate_version_id != registry.substrate_version_id
    assert updated.content_hash != registry.content_hash
    assert resolved.source_id == registration.source_id
    assert resolved.family_id == registration.family_id
    assert resolved.entry_content_hash.startswith("sha256:")


@pytest.mark.parametrize("tier_id", L5_TRUST_TIER_IDS)
def test_substrate_registry_rejects_free_grow_trust_cap_inflated_against_l5_tier(
    tier_id: str,
) -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    tier = l5.trust_tiers[tier_id]
    registration = _future_registration(
        l5.latest_schema_regime(),
        trust_tier=tier.model_copy(update={"trust_cap": tier.trust_cap + 0.001}),
    )

    with pytest.raises(SubstrateRegistryError) as exc:
        register_substrate_entry(registry, registration, l5_authority=l5)
    assert exc.value.code == "substrate_trust_cap_inflated"


@pytest.mark.parametrize("tier_id", L5_TRUST_TIER_IDS)
def test_substrate_registry_rejects_free_grow_trust_multiplier_inflated(
    tier_id: str,
) -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    tier = l5.trust_tiers[tier_id]
    registration = _future_registration(
        l5.latest_schema_regime(),
        trust_tier=tier.model_copy(update={"trust_multiplier": tier.trust_multiplier + 0.001}),
    )

    with pytest.raises(SubstrateRegistryError) as exc:
        register_substrate_entry(registry, registration, l5_authority=l5)
    assert exc.value.code == "substrate_trust_multiplier_inflated"


@pytest.mark.parametrize("tier_id", L5_TRUST_TIER_IDS)
def test_substrate_registry_accepts_free_grow_trust_fields_at_l5_tier_boundary(
    tier_id: str,
) -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    tier = l5.trust_tiers[tier_id]
    registration = _future_registration(
        l5.latest_schema_regime(),
        trust_tier=tier,
    )

    updated = register_substrate_entry(registry, registration, l5_authority=l5)
    resolved = updated.resolve(
        source_id="acquisition:test_future_source",
        family_id="future_observation_family",
        layer=SubstrateLayer.L4,
    )[0]

    assert resolved.trust_tier.trust_cap == tier.trust_cap
    assert resolved.trust_tier.trust_multiplier == tier.trust_multiplier


@pytest.mark.parametrize("tier_id", L5_TRUST_TIER_IDS)
def test_substrate_registry_accepts_free_grow_trust_fields_below_l5_tier_caps(
    tier_id: str,
) -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    tier = l5.trust_tiers[tier_id]
    expected_cap = max(0.0, tier.trust_cap - 0.01)
    expected_multiplier = max(0.0, tier.trust_multiplier - 0.01)
    registration = _future_registration(
        l5.latest_schema_regime(),
        trust_tier=tier.model_copy(
            update={
                "trust_cap": expected_cap,
                "trust_multiplier": expected_multiplier,
            }
        ),
    )

    updated = register_substrate_entry(registry, registration, l5_authority=l5)
    resolved = updated.resolve(
        source_id="acquisition:test_future_source",
        family_id="future_observation_family",
        layer=SubstrateLayer.L4,
    )[0]

    assert resolved.trust_tier.trust_cap == expected_cap
    assert resolved.trust_tier.trust_multiplier == expected_multiplier


def test_substrate_registry_rejects_free_grow_unknown_trust_tier_name() -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    registration = _future_registration(
        l5.latest_schema_regime(),
        trust_tier=SubstrateTrustTier(
            tier="future_unregistered_tier",
            trust_cap=0.1,
            trust_multiplier=0.1,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref="receipt://future-unregistered-tier",
        ),
    )

    with pytest.raises(SubstrateRegistryError) as exc:
        register_substrate_entry(registry, registration, l5_authority=l5)
    assert exc.value.code == "substrate_trust_tier_unresolved"


def test_substrate_registry_rejects_inflated_l5_coverage_trust_and_identification() -> None:
    paths = default_substrate_catalog_paths(REPO_ROOT)
    l5 = load_l5_catalog_authority(paths)
    schema_regime = l5.latest_schema_regime()
    inflated = SubstrateRegistration(
        source_id="manual:inflated_household",
        family_id="household_distribution",
        layer=SubstrateLayer.L5,
        coverage=SubstrateCoverage(
            coverage_score=1.0,
            coverage_kind="manual_override",
            coverage_rule_ref="manual://inflated",
        ),
        trust_tier=l5.trust_tiers["authoritative_high_coverage"],
        identification_mode="point_identified",
        schema_regime=schema_regime,
        data_version="inflated-v1",
        snapshot_id="inflated-v1",
        source_snapshot_id="inflated-v1",
        provenance_refs=("manual://inflated",),
        authority_refs=(l5.measurement_registry_ref,),
    )

    with pytest.raises(SubstrateRegistryError, match="substrate_coverage_inflated"):
        l5.validate_registration(inflated)


def test_substrate_registry_persists_and_has_no_plan_named_owner_file(tmp_path: Path) -> None:
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_substrate_registry(store, registry)
    loaded = load_substrate_registry(store, ref)

    assert loaded.content_hash == registry.content_hash
    assert loaded.substrate_version_id == registry.substrate_version_id
    assert not list((REPO_ROOT / "src/polisyos/runtime/quality").rglob("gy_s0_*.py"))
