from __future__ import annotations

import ast
import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactID, ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import data_state_substrate
from polisyos.runtime.quality import substrate_registry as substrate_module
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
    resolve_l5_schema_regime_projection,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
L5_TRUST_TIER_IDS = (
    "administrative_noisy",
    "authoritative_high_coverage",
    "authoritative_partial_coverage",
    "derived_proxy",
    "weak_anchor",
)


def _projection_with(
    projection: epoch_contract.ScopedSchemaRegimeProjection,
    **updates: object,
) -> epoch_contract.ScopedSchemaRegimeProjection:
    mapping = projection.model_dump(mode="python", exclude={"projection_content_hash"})
    mapping.update(updates)
    mapping["projection_content_hash"] = (
        "sha256:" + hashlib.sha256(epoch_contract.canonical_epoch_bytes(mapping)).hexdigest()
    )
    return epoch_contract.ScopedSchemaRegimeProjection.model_validate(mapping)


def _constructor_sites(root: Path, *, extra_source: str | None = None) -> set[tuple[str, str]]:
    sites: set[tuple[str, str]] = set()
    candidates = [(path, path.read_text(encoding="utf-8")) for path in root.rglob("*.py")]
    if extra_source is not None:
        candidates.append((Path("<candidate>"), extra_source))
    for candidate_path, source in candidates:
        tree = ast.parse(source, filename=candidate_path.as_posix())

        class Visitor(ast.NodeVisitor):
            def __init__(self, *, source_name: str) -> None:
                self._source_name = source_name
                self._parents: list[str] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
                self._parents.append(node.name)
                self.generic_visit(node)
                self._parents.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
                self.visit_FunctionDef(node)

            def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name == "SubstrateSchemaRegime":
                    parent = self._parents[-1] if self._parents else "<module>"
                    sites.add((self._source_name, parent))
                self.generic_visit(node)

        Visitor(source_name=candidate_path.as_posix()).visit(tree)
    return sites


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
    empty_registry_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "0" * 64),
        kind="l5.schema_regime_registry",
        media_type="application/json",
    )
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
        schema_regime_rows={},
        schema_regime_scope_relations=(),
        schema_regime_changepoints=(),
        epoch_schema_regime_registry_ref=empty_registry_ref,
        epoch_schema_regime_registry_content_hash="sha256:" + "0" * 64,
        epoch_schema_regime_scope_registry_ref=empty_registry_ref.model_copy(
            update={"kind": "l5.schema_regime_scope_registry"}
        ),
        epoch_schema_regime_scope_registry_content_hash="sha256:" + "0" * 64,
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


def test_l5_scope_relation_not_projection_mapping_decides_applicability() -> None:
    l5 = load_l5_catalog_authority(default_substrate_catalog_paths(REPO_ROOT))
    scope_ref = l5.schema_regime_scope_relations[0].scope_identity_refs[0]
    receipt, projection = resolve_l5_schema_regime_projection(
        l5,
        scope_identity_ref=scope_ref,
        valid_effect_value=date(2025, 1, 1),
        authority_purpose="publication",
    )
    earlier_id = min(
        l5.schema_regimes, key=lambda key: l5.schema_regimes[key].effective_start or ""
    )
    earlier_hash = (
        "sha256:"
        + hashlib.sha256(
            epoch_contract.canonical_epoch_bytes(dict(l5.schema_regime_rows[earlier_id]))
        ).hexdigest()
    )
    forged = _projection_with(
        projection,
        applicable_regime_ids=(earlier_id,),
        applicable_regime_content_hashes=(earlier_hash,),
    )

    with pytest.raises(SubstrateRegistryError, match="evidence_mismatch"):
        build_substrate_registry_from_existing_catalogs(
            REPO_ROOT,
            l5_receipt_projections=((receipt, forged),),
        )


def test_l5_regime_without_owner_scope_relation_is_epoch_scope_unresolved() -> None:
    l5 = load_l5_catalog_authority(default_substrate_catalog_paths(REPO_ROOT))
    scope_ref = l5.schema_regime_scope_relations[0].scope_identity_refs[0]
    latest_id = max(l5.schema_regimes, key=lambda key: l5.schema_regimes[key].effective_start or "")
    missing = replace(
        l5,
        schema_regime_scope_relations=tuple(
            row for row in l5.schema_regime_scope_relations if row.schema_regime_id != latest_id
        ),
    )

    receipt, projection = resolve_l5_schema_regime_projection(
        missing,
        scope_identity_ref=scope_ref,
        valid_effect_value=date(2025, 1, 1),
        authority_purpose="publication",
    )

    assert receipt.status == "unresolved"
    assert receipt.failure_codes == ("schema_regime_scope_missing",)
    assert projection.status == "unresolved"


def test_third_regime_and_novel_domain_agree_across_epoch_generation_and_l4() -> None:
    l5 = load_l5_catalog_authority(default_substrate_catalog_paths(REPO_ROOT))
    current_scope = l5.schema_regime_scope_relations[0].scope_identity_refs[0]
    other_scope = "sha256:" + hashlib.sha256(b"novel-domain").hexdigest()
    novel_id = "novel_domain_schema_v1"
    novel_row = {
        "schema_regime_id": novel_id,
        "source_version": "1.0",
        "effective_start": "2020-01-01",
        "effective_end": None,
        "boundary_buffer_periods": 0,
    }
    novel_regime = SubstrateSchemaRegime(
        schema_regime_id=novel_id,
        authority_ref="repo://novel-domain/schema-regime",
        effective_start="2020-01-01",
        effective_end=None,
        boundary_buffer_periods=0,
        source_version="1.0",
    )
    base_relation = l5.schema_regime_scope_relations[0]
    novel_relation = epoch_contract.L5SchemaRegimeScopeRelation(
        schema_regime_id=novel_id,
        scope_identity_refs=(other_scope,),
        relation_provenance_ref=base_relation.relation_provenance_ref,
        visibility_knowledge_from=datetime(2020, 1, 1, tzinfo=UTC),
        purpose_admission_from=datetime(2020, 1, 1, tzinfo=UTC),
    )
    extended = replace(
        l5,
        schema_regimes={**l5.schema_regimes, novel_id: novel_regime},
        schema_regime_rows={**l5.schema_regime_rows, novel_id: novel_row},
        schema_regime_scope_relations=(*l5.schema_regime_scope_relations, novel_relation),
    )
    receipt, projection = resolve_l5_schema_regime_projection(
        extended,
        scope_identity_ref=current_scope,
        valid_effect_value=date(2021, 1, 1),
        authority_purpose="publication",
    )
    applicable = tuple(
        row.schema_regime_id for row in receipt.assessments if row.disposition == "applicable"
    )
    generation_entries = substrate_module._entries_from_l5(
        extended,
        receipt=receipt,
        projection=projection,
    )
    l4 = data_state_substrate._schema_regime_decision(
        extended,
        receipt=receipt,
        projection=projection,
        period_start="2021-01",
        period_end="2021-01",
    )

    assert applicable == projection.applicable_regime_ids == l4["regime_ids"]
    assert {entry.schema_regime.schema_regime_id for entry in generation_entries} == set(applicable)
    assert novel_id not in applicable


def test_complete_regime_producer_reader_census_rejects_sibling_declaration() -> None:
    sites = _constructor_sites(REPO_ROOT / "src")
    expected = {
        ("src/polisyos/runtime/quality/substrate_registry.py", "load_l5_catalog_authority"),
        ("src/polisyos/runtime/quality/substrate_registry.py", "_entries_from_l1_dcat"),
        (
            "src/polisyos/runtime/quality/substrate_registry.py",
            "_entries_from_l2_l3_knowledge_substrates",
        ),
        (
            "src/polisyos/runtime/quality/substrate_registry.py",
            "_entries_from_l6_agent_sim_control_artifacts",
        ),
        ("src/polisyos/runtime/quality/substrate_registry.py", "_entries_from_root_manifest"),
    }
    normalized = {(Path(path).relative_to(REPO_ROOT).as_posix(), owner) for path, owner in sites}
    assert normalized == expected

    mutated = _constructor_sites(
        REPO_ROOT / "src",
        extra_source="def sibling():\n    return SubstrateSchemaRegime(schema_regime_id='x')\n",
    )
    assert ("<candidate>", "sibling") in mutated - sites


def test_generation_and_data_state_cannot_call_global_latest_schema_regime() -> None:
    forbidden = {"latest_schema_regime", "complete_schema_regime_projection"}
    calls: set[tuple[str, str]] = set()
    for relative in (
        "src/polisyos/runtime/quality/generation_cycle.py",
        "src/polisyos/runtime/quality/data_state_substrate.py",
    ):
        tree = ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden:
                    calls.add((relative, node.func.attr))
    assert calls == set()
