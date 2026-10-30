from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from polisyos.core.artifacts.manifest import ArtifactID, ArtifactRef, WarningRecord
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
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
    persist_measurement_root_substrate_registry,
    persist_substrate_registry,
    register_substrate_entry,
    resolve_l5_schema_regime_projection,
)

# Code-root for source inspection; catalog data uses the selected fixture root below.
REPO_ROOT = Path(__file__).resolve().parents[4]
L5_TRUST_TIER_IDS = (
    "administrative_noisy",
    "authoritative_high_coverage",
    "authoritative_partial_coverage",
    "derived_proxy",
    "weak_anchor",
)


def _write_catalog_fixture_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_fixture_database(
    path: Path,
    *,
    table_statements: tuple[tuple[str, str, str], ...],
    version_table: str,
    version_value: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    try:
        for table_name, create_statement, insert_statement in table_statements:
            connection.execute(create_statement)
            if table_name == version_table:
                connection.execute(insert_statement, [version_value])
            else:
                connection.execute(insert_statement)
    finally:
        connection.close()


def _write_substrate_catalog_fixture(root: Path, *, include_graphs: bool = True) -> None:
    """Build synthetic registry inputs, optionally composing existing owner graphs.

    ``include_graphs=False`` emits the same L5/root/epoch/L6 fixture inputs;
    the caller supplies its already-produced real L1/L2/L3 graph inputs.
    """

    production_data = root / "production_data"
    manifest_path = production_data / "manifest.json"
    l5_dir = (
        production_data
        / "canonical/local_data_20260501/ukraine_server_support_20260410"
        / "runtime_calibration_internals/calibration/d2"
    )
    schema_v1 = {
        "schema_regime_id": "ukraine_schema_v1",
        "source_version": "fixture-v1",
        "effective_start": "2020-01-01",
        "effective_end": None,
        "boundary_buffer_periods": 0,
    }
    schema_v2 = {
        "schema_regime_id": "ukraine_schema_v2",
        "source_version": "fixture-v2",
        "effective_start": "2023-01-01",
        "effective_end": None,
        "boundary_buffer_periods": 0,
    }
    scope_identity_ref = "sha256:" + hashlib.sha256(b"unit fixture scope").hexdigest()
    relation_ref = "sha256:" + hashlib.sha256(b"unit fixture relation").hexdigest()
    relations = [
        {
            "schema_regime_id": regime["schema_regime_id"],
            "scope_identity_refs": [scope_identity_ref],
            "relation_provenance_ref": {
                "artifact_id": relation_ref,
                "kind": "l5.schema_regime_scope_relation",
                "media_type": "application/json",
            },
            "visibility_knowledge_from": "2020-01-01T00:00:00Z",
            "purpose_admission_from": "2020-01-01T00:00:00Z",
        }
        for regime in (schema_v1, schema_v2)
    ]
    trust_tiers = {
        "administrative_noisy": {
            "tier": "administrative_noisy",
            "trust_cap": 0.10,
            "trust_multiplier": 0.50,
            "min_coverage": 0.0,
            "max_coverage": 0.10,
        },
        "weak_anchor": {
            "tier": "weak_anchor",
            "trust_cap": 0.25,
            "trust_multiplier": 0.60,
            "min_coverage": 0.10,
            "max_coverage": 0.39,
        },
        "derived_proxy": {
            "tier": "derived_proxy",
            "trust_cap": 0.50,
            "trust_multiplier": 0.75,
            "min_coverage": 0.30,
            "max_coverage": 0.59,
        },
        "authoritative_partial_coverage": {
            "tier": "authoritative_partial_coverage",
            "trust_cap": 0.70,
            "trust_multiplier": 0.90,
            "min_coverage": 0.40,
            "max_coverage": 0.79,
        },
        "authoritative_high_coverage": {
            "tier": "authoritative_high_coverage",
            "trust_cap": 0.90,
            "trust_multiplier": 1.0,
            "min_coverage": 0.80,
            "max_coverage": 1.0,
        },
    }
    _write_catalog_fixture_json(
        l5_dir / "measurement_registry.json",
        {
            "coverage_rules": {
                "firm_fundamentals": 0.70,
                "household_distribution": 0.30,
                "distress_enforcement": 0.60,
            },
            "trust_tiers": trust_tiers,
            "proxy_mappings": {
                "household_distribution": {"proxy_source_id": "fixture:household_proxy"}
            },
        },
    )
    _write_catalog_fixture_json(
        l5_dir / "identification_mode_registry.json",
        {
            "firm_fundamentals": {"selected_mode": "partially_identified"},
            "household_distribution": {"selected_mode": "proxy_identified"},
            "distress_enforcement": {"selected_mode": "partially_identified"},
        },
    )
    _write_catalog_fixture_json(
        l5_dir / "schema_regime_registry.json",
        {"regimes": {"ukraine_schema_v1": schema_v1}},
    )
    _write_catalog_fixture_json(
        root / "architecture/policy_design_case/layer3_gy_l5_schema_regime_registry.json",
        {"regimes": {"ukraine_schema_v2": schema_v2}, "changepoints": []},
    )
    _write_catalog_fixture_json(
        root / "architecture/policy_design_case/layer3_gy_l5_schema_regime_scope_registry.json",
        {"relations": relations},
    )

    _write_catalog_fixture_json(
        manifest_path,
        {
            "bundles": {
                "datasets": {
                    "role": "dataset_catalog",
                    "path": "datasets_full_phase3full_20260327_183054",
                    "version_id": "unit-fixture-datasets-v1",
                    "readiness": "ready_with_partial_coverage",
                    "required_files": [],
                    "extra": {
                        "blocking_source_statuses": {},
                        "source_publish_blocking": {},
                    },
                },
                "scholar": {
                    "role": "academic_knowledge",
                    "path": "fixture_scholar",
                    "version_id": "unit-fixture-scholar-v1",
                    "readiness": "ready",
                    "required_files": [],
                },
                "legal": {
                    "role": "legal_knowledge",
                    "path": "fixture_legal",
                    "version_id": "unit-fixture-legal-v1",
                    "readiness": "ready",
                    "required_files": [],
                },
                "policy_context": {
                    "role": "domain_context",
                    "path": "fixture_policy_context",
                    "version_id": "unit-fixture-context-v1",
                    "readiness": "ready_with_partial_coverage",
                    "required_files": [],
                },
                "ukraine_simulation": {
                    "role": "simulation_bundle",
                    "path": "fixture_ukraine_simulation",
                    "version_id": "unit-fixture-simulation-v1",
                    "readiness": "ready",
                    "required_files": [],
                },
            }
        },
    )

    if include_graphs:
        dcat_path = (
            production_data / "datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
        )
        dcat_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(dcat_path))
        try:
            connection.execute(
                """
            CREATE TABLE ds_datasets (
                source VARCHAR,
                quality_execution_readiness_score DOUBLE,
                quality_description_score DOUBLE,
                quality_machine_readable_score DOUBLE,
                quality_parser_support_score DOUBLE,
                quality_freshness_score DOUBLE
            )
            """
            )
            connection.execute("CREATE TABLE ds_metric_bindings (source VARCHAR)")
            connection.executemany(
                "INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("fixture_dataset_source", 0.16, 0.70, 0.80, 0.90, 0.60),
                    ("fixture_dataset_source", 0.40, 0.80, 0.85, 0.95, 0.70),
                ],
            )
            connection.execute(
                "INSERT INTO ds_metric_bindings VALUES (?)",
                ["fixture_dataset_source"],
            )
        finally:
            connection.close()

        l2_table_statements = (
            (
                "ac_parameter_estimates",
                "CREATE TABLE ac_parameter_estimates (fixture_row INTEGER)",
                "INSERT INTO ac_parameter_estimates VALUES (1)",
            ),
            (
                "ac_causal_claims",
                "CREATE TABLE ac_causal_claims (fixture_row INTEGER)",
                "INSERT INTO ac_causal_claims VALUES (1)",
            ),
            (
                "ac_skg_edges",
                "CREATE TABLE ac_skg_edges (fixture_row INTEGER)",
                "INSERT INTO ac_skg_edges VALUES (1)",
            ),
            (
                "ac_skg_transport_scores",
                "CREATE TABLE ac_skg_transport_scores (fixture_row INTEGER)",
                "INSERT INTO ac_skg_transport_scores VALUES (1)",
            ),
            (
                "ac_skg_contested_edges",
                "CREATE TABLE ac_skg_contested_edges (fixture_row INTEGER)",
                "INSERT INTO ac_skg_contested_edges VALUES (1)",
            ),
            (
                "ac_claim_adjudications",
                "CREATE TABLE ac_claim_adjudications (fixture_row INTEGER)",
                "INSERT INTO ac_claim_adjudications VALUES (1)",
            ),
            (
                "ac_skg_variables",
                "CREATE TABLE ac_skg_variables (fixture_row INTEGER)",
                "INSERT INTO ac_skg_variables VALUES (1)",
            ),
            (
                "ac_context_attributes",
                "CREATE TABLE ac_context_attributes (fixture_row INTEGER)",
                "INSERT INTO ac_context_attributes VALUES (1)",
            ),
            (
                "ac_simulation_parameters",
                "CREATE TABLE ac_simulation_parameters (fixture_row INTEGER)",
                "INSERT INTO ac_simulation_parameters VALUES (1)",
            ),
            (
                "ac_boundary_conditions",
                "CREATE TABLE ac_boundary_conditions (fixture_row INTEGER)",
                "INSERT INTO ac_boundary_conditions VALUES (1)",
            ),
            (
                "ac_skg_versions",
                "CREATE TABLE ac_skg_versions (version_id VARCHAR)",
                "INSERT INTO ac_skg_versions VALUES (?)",
            ),
        )
        _write_fixture_database(
            production_data
            / "policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb",
            table_statements=l2_table_statements,
            version_table="ac_skg_versions",
            version_value="unit-fixture-scholar-v1",
        )
        l3_table_statements = (
            (
                "lex_provisions",
                "CREATE TABLE lex_provisions (fixture_row INTEGER)",
                "INSERT INTO lex_provisions VALUES (1)",
            ),
            (
                "lex_normative_ready_facts",
                "CREATE TABLE lex_normative_ready_facts (fixture_row INTEGER)",
                "INSERT INTO lex_normative_ready_facts VALUES (1)",
            ),
            (
                "lex_rule_thresholds",
                "CREATE TABLE lex_rule_thresholds (fixture_row INTEGER)",
                "INSERT INTO lex_rule_thresholds VALUES (1)",
            ),
            (
                "lex_rule_clauses",
                "CREATE TABLE lex_rule_clauses (fixture_row INTEGER)",
                "INSERT INTO lex_rule_clauses VALUES (1)",
            ),
            (
                "lex_amendments",
                "CREATE TABLE lex_amendments (effective_from VARCHAR)",
                "INSERT INTO lex_amendments VALUES (?)",
            ),
            (
                "lex_entities",
                "CREATE TABLE lex_entities (fixture_row INTEGER)",
                "INSERT INTO lex_entities VALUES (1)",
            ),
            (
                "lex_doc_domains",
                "CREATE TABLE lex_doc_domains (fixture_row INTEGER)",
                "INSERT INTO lex_doc_domains VALUES (1)",
            ),
            (
                "lex_temporal_audit",
                "CREATE TABLE lex_temporal_audit (fixture_row INTEGER)",
                "INSERT INTO lex_temporal_audit VALUES (1)",
            ),
        )
        _write_fixture_database(
            production_data
            / "lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb",
            table_statements=l3_table_statements,
            version_table="lex_amendments",
            version_value="2026-01-01",
        )

    l6_root = production_data / "fixture_ukraine_simulation/production_bundle/bundles"
    l6_payloads = (
        (
            "intervention_bundle_v1/intervention_knob_dictionary.json",
            "fixture_intervention_knob",
        ),
        ("intervention_bundle_v1/lex_intervention_map.json", "fixture_lex_intervention"),
        (
            "method_contract_bundle_v1/observation_to_contract_manifest.json",
            "fixture_observation_contract",
        ),
        (
            "intervention_bundle_v1/policy_scenario_templates.json",
            "fixture_policy_scenario",
        ),
    )
    for relative_path, route_id in l6_payloads:
        _write_catalog_fixture_json(
            l6_root / relative_path,
            {"routes": [{"route_id": route_id}], "artifacts": []},
        )


@pytest.fixture(scope="session")
def catalog_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return a physically contained synthetic catalog owner root."""

    root = tmp_path_factory.mktemp("substrate-registry-catalog")
    _write_substrate_catalog_fixture(root)
    return root


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


def test_substrate_registry_lifts_l5_and_l1_catalog_authority(
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
    repo_root = catalog_root.resolve(strict=True)

    for actual_ref, source_path in (
        (l5.measurement_registry_ref, paths.measurement_registry_path),
        (l5.identification_mode_registry_ref, paths.identification_mode_registry_path),
        (l5.schema_regime_registry_ref, paths.schema_regime_registry_path),
    ):
        relative = source_path.resolve(strict=True).relative_to(repo_root).as_posix()
        assert actual_ref.split("#", 1)[0] == f"repo://{relative}"

    registry_refs = set(registry.source_catalog_refs)
    for entry in registry.entries:
        registry_refs.update(entry.provenance_refs)
        registry_refs.update(entry.authority_refs)
        registry_refs.add(entry.coverage.coverage_rule_ref)
    for ref in registry_refs:
        if not ref.startswith("repo://"):
            continue
        raw_path = ref.removeprefix("repo://").split("#", 1)[0]
        assert raw_path and not Path(raw_path).is_absolute()
        resolved = (repo_root / raw_path).resolve(strict=True)
        resolved.relative_to(repo_root)

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
        source_id="l1_dcat:fixture_dataset_source",
        family_id="dcat_source:fixture_dataset_source",
        layer=SubstrateLayer.L1,
    )[0]
    assert weak_l1.coverage.dataset_count == 2
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


def test_l5_refs_resolve_under_nondefault_selected_repo_root(
    tmp_path: Path, catalog_root: Path
) -> None:
    canonical_root = catalog_root.resolve(strict=True)
    canonical_paths = default_substrate_catalog_paths(canonical_root)
    source_paths = (
        canonical_paths.root_manifest_path,
        canonical_paths.measurement_registry_path,
        canonical_paths.identification_mode_registry_path,
        canonical_paths.schema_regime_registry_path,
        canonical_paths.epoch_schema_regime_registry_path,
        canonical_paths.epoch_schema_regime_scope_registry_path,
    )
    assert all(source_path is not None for source_path in source_paths)

    selected_root = tmp_path / "selected-policy-engine"
    for source_path in source_paths:
        assert source_path is not None
        relative = source_path.resolve(strict=True).relative_to(canonical_root)
        selected_path = selected_root / relative
        selected_path.parent.mkdir(parents=True, exist_ok=True)
        selected_path.write_bytes(source_path.read_bytes())

    selected_paths = default_substrate_catalog_paths(selected_root)
    authority = load_l5_catalog_authority(selected_paths, repo_root=selected_root)
    refs = (
        authority.measurement_registry_ref,
        authority.identification_mode_registry_ref,
        authority.schema_regime_registry_ref,
        *(tier.authority_ref for tier in authority.trust_tiers.values()),
        *(regime.authority_ref for regime in authority.schema_regimes.values()),
    )
    selected_root_resolved = selected_root.resolve(strict=True)
    assert refs
    for ref in refs:
        source_uri = ref.split("#", 1)[0]
        assert source_uri.startswith("repo://")
        relative_source = Path(source_uri.removeprefix("repo://"))
        assert not relative_source.is_absolute()
        assert ".." not in relative_source.parts
        assert relative_source.parts[0] == "production_data"
        selected_source = (selected_root_resolved / relative_source).resolve(strict=True)
        selected_source.relative_to(selected_root_resolved)
        assert selected_source.read_bytes()

    measurement_relative = canonical_paths.measurement_registry_path.resolve(
        strict=True
    ).relative_to(canonical_root)
    assert authority.measurement_registry_ref == (
        f"repo://{measurement_relative.as_posix()}#measurement_registry"
    )

    wrong_parent_root = selected_paths.root_manifest_path.parent
    with pytest.raises(
        SubstrateRegistryError,
        match="substrate_source_path_outside_repo_root",
    ):
        load_l5_catalog_authority(
            selected_paths,
            repo_root=wrong_parent_root,
        )


def test_split_catalog_roots_keep_code_epoch_and_selected_data_inputs_separate(
    tmp_path: Path,
) -> None:
    """Selected production metadata cannot re-root code-owned epoch registries."""

    code_root = tmp_path / "code-owner"
    data_root = tmp_path / "physical-data-owner"
    _write_substrate_catalog_fixture(code_root)
    _write_substrate_catalog_fixture(data_root)
    code_paths = default_substrate_catalog_paths(code_root)
    data_paths = default_substrate_catalog_paths(data_root)

    code_epoch = json.loads(
        code_paths.epoch_schema_regime_registry_path.read_text(encoding="utf-8")
    )
    code_epoch["regimes"]["code_root_only"] = {
        "schema_regime_id": "code_root_only",
        "source_version": "code-owned-fixture-v1",
        "effective_start": "2025-01-01",
        "effective_end": None,
        "boundary_buffer_periods": 0,
    }
    _write_catalog_fixture_json(code_paths.epoch_schema_regime_registry_path, code_epoch)
    data_epoch = json.loads(
        data_paths.epoch_schema_regime_registry_path.read_text(encoding="utf-8")
    )
    data_epoch["regimes"]["data_root_decoy"] = {
        "schema_regime_id": "data_root_decoy",
        "source_version": "data-root-decoy-v1",
        "effective_start": "2025-01-01",
        "effective_end": None,
        "boundary_buffer_periods": 0,
    }
    _write_catalog_fixture_json(data_paths.epoch_schema_regime_registry_path, data_epoch)

    data_measurement = json.loads(data_paths.measurement_registry_path.read_text(encoding="utf-8"))
    data_measurement["trust_tiers"]["weak_anchor"]["trust_multiplier"] = 0.61
    _write_catalog_fixture_json(data_paths.measurement_registry_path, data_measurement)
    data_manifest = json.loads(data_paths.root_manifest_path.read_text(encoding="utf-8"))
    data_manifest["bundles"]["ukraine_simulation"]["version_id"] = "selected-data-v2"
    _write_catalog_fixture_json(data_paths.root_manifest_path, data_manifest)

    l6_relative = Path(
        "production_data/fixture_ukraine_simulation/production_bundle/bundles/"
        "intervention_bundle_v1/intervention_knob_dictionary.json"
    )
    selected_l6_payload = {
        "routes": [{"route_id": "selected-data-route-1"}, {"route_id": "selected-data-route-2"}],
        "artifacts": [],
    }
    decoy_l6_payload = {"routes": [{"route_id": "code-root-decoy"}], "artifacts": []}
    _write_catalog_fixture_json(data_root / l6_relative, selected_l6_payload)
    _write_catalog_fixture_json(code_root / l6_relative, decoy_l6_payload)

    def tree_digest(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    data_before = tree_digest(data_root)
    paths = default_substrate_catalog_paths(code_root, source_owner_root=data_root)
    authority = load_l5_catalog_authority(
        paths,
        repo_root=code_root,
        source_owner_root=data_root,
    )
    registry = build_substrate_registry_from_existing_catalogs(
        code_root,
        source_owner_root=data_root,
    )

    assert authority.trust_tiers["weak_anchor"].trust_multiplier == 0.61
    assert "code_root_only" in authority.schema_regimes
    assert "data_root_decoy" not in authority.schema_regimes
    expected_epoch_digest = (
        "sha256:"
        + hashlib.sha256(code_paths.epoch_schema_regime_registry_path.read_bytes()).hexdigest()
    )
    assert str(authority.epoch_schema_regime_registry_ref.artifact_id) == expected_epoch_digest
    selected_l6 = registry.resolve(
        family_id="l6_intervention_knob_dictionary",
        layer=SubstrateLayer.L6,
    )[0]
    assert selected_l6.data_version == "selected-data-v2"
    assert selected_l6.coverage.observation_count == 2
    assert tree_digest(data_root) == data_before

    changed_l6_payload = {
        **selected_l6_payload,
        "routes": [
            *selected_l6_payload["routes"],
            {"route_id": "selected-data-route-3"},
        ],
    }
    _write_catalog_fixture_json(data_root / l6_relative, changed_l6_payload)
    refreshed = build_substrate_registry_from_existing_catalogs(
        code_root,
        source_owner_root=data_root,
    )
    assert refreshed.content_hash != registry.content_hash


def test_split_l5_loader_rejects_missing_malformed_and_escaped_selected_sources(
    tmp_path: Path,
) -> None:
    """A selected root path is resolved and parsed, never accepted by declaration alone."""

    code_root = tmp_path / "code-owner"
    data_root = tmp_path / "physical-data-owner"
    _write_substrate_catalog_fixture(code_root)
    _write_substrate_catalog_fixture(data_root)
    paths = default_substrate_catalog_paths(code_root, source_owner_root=data_root)

    missing_manifest_paths = replace(
        paths,
        root_manifest_path=data_root / "production_data" / "missing-manifest.json",
    )
    with pytest.raises(SubstrateRegistryError, match="substrate_source_path_unavailable"):
        load_l5_catalog_authority(
            missing_manifest_paths,
            repo_root=code_root,
            source_owner_root=data_root,
        )

    malformed_manifest = data_root / "production_data/manifest.json"
    manifest_bytes = malformed_manifest.read_bytes()
    for malformed_bytes in (
        b"{\n",
        b"[]\n",
        b'{"owner": 1, "owner": 2}\n',
        b'{"owner": NaN}\n',
    ):
        malformed_manifest.write_bytes(malformed_bytes)
        with pytest.raises(SubstrateRegistryError, match="substrate_catalog_invalid"):
            load_l5_catalog_authority(
                paths,
                repo_root=code_root,
                source_owner_root=data_root,
            )
    malformed_manifest.write_bytes(manifest_bytes)

    outside = tmp_path / "outside-measurement.json"
    outside.write_text("{}\n", encoding="utf-8")
    link = data_root / "production_data/measurement-link.json"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not permit symlink fixtures")
    escaped_paths = replace(paths, measurement_registry_path=link)
    with pytest.raises(SubstrateRegistryError, match="substrate_source_path_outside_repo_root"):
        load_l5_catalog_authority(
            escaped_paths,
            repo_root=code_root,
            source_owner_root=data_root,
        )

    with pytest.raises(SubstrateRegistryError, match="substrate_source_path_outside_repo_root"):
        load_l5_catalog_authority(
            paths,
            repo_root=data_root,
            source_owner_root=data_root,
        )


def test_repo_ref_resolves_selected_root_and_rejects_symlink_escape(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "selected-checkout"
    source = repo_root / "production_data" / "l5" / "measurement_registry.json"
    source.parent.mkdir(parents=True)
    source.write_text("{}\n", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    linked = source.parent / "external.json"
    try:
        linked.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not permit symlink fixtures")

    assert (
        substrate_module._repo_ref(
            source,
            marker="measurement_registry",
            repo_root=repo_root,
        )
        == "repo://production_data/l5/measurement_registry.json#measurement_registry"
    )
    with pytest.raises(SubstrateRegistryError, match="substrate_source_path_outside_repo_root"):
        substrate_module._repo_ref(
            linked,
            marker="measurement_registry",
            repo_root=repo_root,
        )


def test_repo_ref_rejects_directory_symlink_escape_and_accepts_physical_owner_root(
    tmp_path: Path,
) -> None:
    selected_code_root = tmp_path / "selected-code"
    physical_owner_root = tmp_path / "physical-data-owner"
    selected_code_root.mkdir()
    selected_data_root = physical_owner_root / "production_data"
    manifest_path = selected_data_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{}\n", encoding="utf-8")
    selected_alias = selected_code_root / "production_data"
    try:
        selected_alias.symlink_to(selected_data_root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not permit directory-symlink fixtures")

    selected_manifest = selected_alias / "manifest.json"
    with pytest.raises(
        SubstrateRegistryError,
        match="substrate_source_path_outside_repo_root",
    ):
        substrate_module._repo_ref(
            selected_manifest,
            marker="production_data_root_manifest",
            repo_root=selected_code_root,
        )

    assert (
        substrate_module._repo_ref(
            selected_manifest,
            marker="production_data_root_manifest",
            repo_root=physical_owner_root,
        )
        == "repo://production_data/manifest.json#production_data_root_manifest"
    )


def test_l5_loader_rejects_epoch_source_outside_selected_root(
    tmp_path: Path, catalog_root: Path
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    outside_epoch = tmp_path / "epoch-regime.json"
    outside_epoch.write_text("{}\n", encoding="utf-8")
    paths = replace(paths, epoch_schema_regime_registry_path=outside_epoch)

    with pytest.raises(
        SubstrateRegistryError,
        match="substrate_source_path_outside_repo_root",
    ):
        load_l5_catalog_authority(paths, repo_root=catalog_root)


def test_substrate_registry_registers_l6_intervention_control_artifacts(
    catalog_root: Path,
) -> None:
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)

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


def test_substrate_registry_registration_is_free_grow_and_changes_version(
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
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
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
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
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
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
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
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
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
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


def test_substrate_registry_rejects_free_grow_unknown_trust_tier_name(
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
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


def test_substrate_registry_rejects_inflated_l5_coverage_trust_and_identification(
    catalog_root: Path,
) -> None:
    paths = default_substrate_catalog_paths(catalog_root)
    l5 = load_l5_catalog_authority(paths, repo_root=catalog_root)
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


def test_substrate_registry_persists_and_has_no_plan_named_owner_file(
    tmp_path: Path,
    catalog_root: Path,
) -> None:
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_substrate_registry(store, registry)
    loaded = load_substrate_registry(store, ref)

    assert loaded.content_hash == registry.content_hash
    assert loaded.substrate_version_id == registry.substrate_version_id
    assert not list((REPO_ROOT / "src/polisyos/runtime/quality").rglob("gy_s0_*.py"))


def test_measurement_root_registry_lineage_preserves_selected_profile() -> None:
    """Registry input construction retains the exact selected MeasurementRoot view."""

    selected_profile = "sha256:" + "a" * 64
    measurement_root_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "1" * 64),
        kind="policyos.gy.measurement_root_payload",
        media_type="application/json",
        manifest_profile_sha256=selected_profile,
    )
    fetch_receipt_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "2" * 64),
        kind="fabric.fetch_receipt",
        media_type="application/json",
    )
    catalog_binding_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "3" * 64),
        kind="fabric.catalog_fetch_binding",
        media_type="application/json",
    )

    input_refs = substrate_module._measurement_root_registry_input_refs(
        measurement_root_ref=measurement_root_ref,
        fetch_receipt_ref=fetch_receipt_ref,
        catalog_binding_ref=catalog_binding_ref,
        baseline_registry_ref=None,
    )

    assert len(input_refs) == 3
    assert input_refs[0].role == "measurement_root"
    assert input_refs[0].artifact_id == measurement_root_ref.artifact_id
    assert input_refs[0].manifest_profile_sha256 == selected_profile


@pytest.mark.parametrize(
    "evidence",
    [
        None,
        {
            "measurement_root_ref": "sha256:foreign",
            "fetch_receipt_ref": "sha256:foreign",
        },
        object(),
    ],
)
def test_measurement_root_registration_rejects_shape_only_evidence(
    tmp_path: Path,
    evidence: object,
    catalog_root: Path,
) -> None:
    """Raw or unverified refs never reach registry persistence."""

    l5 = load_l5_catalog_authority(
        default_substrate_catalog_paths(catalog_root), repo_root=catalog_root
    )
    baseline = build_substrate_registry_from_existing_catalogs(catalog_root)
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_substrate_registry(store, baseline)
    registration = _future_registration(l5.latest_schema_regime())

    with pytest.raises(
        SubstrateRegistryError,
        match="substrate_registry_measurement_root_evidence_invalid",
    ):
        persist_measurement_root_substrate_registry(
            store,
            baseline_registry=baseline,
            registration=registration,
            l5_authority=l5,
            evidence=evidence,
            baseline_registry_ref=baseline_ref,
        )

    assert load_substrate_registry(store, baseline_ref) == baseline


def test_l5_scope_relation_not_projection_mapping_decides_applicability(
    catalog_root: Path,
) -> None:
    l5 = load_l5_catalog_authority(
        default_substrate_catalog_paths(catalog_root), repo_root=catalog_root
    )
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
            catalog_root,
            l5_receipt_projections=((receipt, forged),),
        )


def test_l5_projection_recomputes_hash_from_typed_no_profile_refs(
    catalog_root: Path,
) -> None:
    l5 = load_l5_catalog_authority(
        default_substrate_catalog_paths(catalog_root), repo_root=catalog_root
    )
    scope_ref = l5.schema_regime_scope_relations[0].scope_identity_refs[0]
    receipt, projection = resolve_l5_schema_regime_projection(
        l5,
        scope_identity_ref=scope_ref,
        valid_effect_value=date(2021, 1, 1),
        authority_purpose="publication",
    )

    assert isinstance(projection.owner_source_snapshot_ref, ArtifactRef)
    assert isinstance(projection.denominator_receipt_ref, ArtifactRef)
    assert projection.owner_source_snapshot_ref.manifest_profile_sha256 is None
    assert projection.denominator_receipt_ref.manifest_profile_sha256 is None

    preimage = projection.model_dump(mode="python", exclude={"projection_content_hash"})
    preimage["owner_source_snapshot_ref"] = projection.owner_source_snapshot_ref.model_dump(
        mode="json"
    )
    preimage["denominator_receipt_ref"] = projection.denominator_receipt_ref.model_dump(mode="json")
    expected_hash = (
        "sha256:" + hashlib.sha256(epoch_contract.canonical_epoch_bytes(preimage)).hexdigest()
    )
    assert projection.projection_content_hash == expected_hash
    historical_v1_payload = {**preimage, "projection_content_hash": expected_hash}
    assert epoch_contract.canonical_epoch_bytes(projection) == epoch_contract.canonical_epoch_bytes(
        historical_v1_payload
    )

    # The same owner projection must be accepted by a downstream consumer that
    # independently asks L5 to recompute it.
    entries = substrate_module._entries_from_l5(l5, receipt=receipt, projection=projection)
    assert entries


def test_scoped_projection_binds_selected_view_and_rejects_malformed_profile() -> None:
    profile_sha256 = "sha256:" + hashlib.sha256(b"same selected profile").hexdigest()
    owner_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + hashlib.sha256(b"owner").hexdigest()),
        kind="l5.schema_regime_owner_snapshot",
        media_type="application/json",
        manifest_profile_sha256=profile_sha256,
    )
    denominator_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + hashlib.sha256(b"denominator").hexdigest()),
        kind="l5.schema_regime_denominator_receipt",
        media_type="application/vnd.polisyos.epoch+json",
        manifest_profile_sha256=profile_sha256,
    )
    preimage = {
        "scope_identity_ref": "sha256:" + hashlib.sha256(b"scope").hexdigest(),
        "valid_effect_coordinate_ref": "sha256:" + hashlib.sha256(b"valid").hexdigest(),
        "requested_query_context_ref": "sha256:" + hashlib.sha256(b"query").hexdigest(),
        "owner_source_snapshot_ref": owner_ref.model_dump(mode="json"),
        "denominator_receipt_ref": denominator_ref.model_dump(mode="json"),
        "applicable_regime_ids": ("regime-a",),
        "applicable_regime_content_hashes": ("sha256:" + hashlib.sha256(b"regime-a").hexdigest(),),
        "changepoint_refs": (),
        "status": "resolved",
    }
    projection_hash = (
        "sha256:" + hashlib.sha256(epoch_contract.canonical_epoch_bytes(preimage)).hexdigest()
    )
    projection = epoch_contract.ScopedSchemaRegimeProjection.model_validate(
        {**preimage, "projection_content_hash": projection_hash}
    )
    assert projection.owner_source_snapshot_ref.manifest_profile_sha256 == profile_sha256
    assert projection.denominator_receipt_ref.manifest_profile_sha256 == profile_sha256
    assert epoch_contract.canonical_epoch_bytes(projection) == epoch_contract.canonical_epoch_bytes(
        {**preimage, "projection_content_hash": projection_hash}
    )

    changed_view = owner_ref.model_dump(mode="json")
    changed_view["manifest_profile_sha256"] = (
        "sha256:" + hashlib.sha256(b"different selected profile").hexdigest()
    )
    with pytest.raises(ValueError, match="scoped regime projection hash differs"):
        epoch_contract.ScopedSchemaRegimeProjection.model_validate(
            {
                **preimage,
                "owner_source_snapshot_ref": changed_view,
                "projection_content_hash": projection_hash,
            }
        )

    malformed_view = owner_ref.model_dump(mode="json")
    malformed_view["manifest_profile_sha256"] = "sha256:not-a-digest"
    with pytest.raises(ValueError, match="manifest_profile_sha256"):
        ArtifactRef.model_validate(malformed_view)


def test_l5_regime_without_owner_scope_relation_is_epoch_scope_unresolved(
    catalog_root: Path,
) -> None:
    l5 = load_l5_catalog_authority(
        default_substrate_catalog_paths(catalog_root), repo_root=catalog_root
    )
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


def test_third_regime_and_novel_domain_agree_across_epoch_generation_and_l4(
    catalog_root: Path,
) -> None:
    l5 = load_l5_catalog_authority(
        default_substrate_catalog_paths(catalog_root), repo_root=catalog_root
    )
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
        schema_regime_scope_relations=(
            *l5.schema_regime_scope_relations,
            novel_relation,
        ),
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
        (
            "src/polisyos/runtime/quality/substrate_registry.py",
            "load_l5_catalog_authority",
        ),
        ("src/polisyos/runtime/quality/substrate_registry.py", "_entries_from_l1_dcat"),
        (
            "src/polisyos/runtime/quality/substrate_registry.py",
            "_entries_from_l2_l3_knowledge_substrates",
        ),
        (
            "src/polisyos/runtime/quality/substrate_registry.py",
            "_entries_from_l6_agent_sim_control_artifacts",
        ),
        (
            "src/polisyos/runtime/quality/substrate_registry.py",
            "_entries_from_root_manifest",
        ),
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


def test_substrate_registry_loader_reads_the_selected_manifest_view(
    tmp_path: Path,
    catalog_root: Path,
) -> None:
    """A selected registry ref is resolved as that view, not as the default ID."""
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
    store = FileSystemCAS(tmp_path / "cas")
    default_ref = persist_substrate_registry(store, registry)
    manifest = store.get_manifest(default_ref)
    assert manifest.canon is not None
    selected_ref = store.put_bytes(
        store.get_bytes(default_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
            canon=manifest.canon,
            warnings=[
                WarningRecord(
                    code="fixture.selected_registry_view",
                    msg="This registry has a selected manifest profile.",
                )
            ],
        ),
        return_selected_profile=True,
    )
    assert selected_ref.manifest_profile_sha256 is not None

    assert load_substrate_registry(store, selected_ref) == registry


def test_substrate_registry_writer_returns_selected_profile_and_reader_rejects_default_selector(
    tmp_path: Path,
    catalog_root: Path,
) -> None:
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
    store = FileSystemCAS(tmp_path / "cas")
    selected_ref = persist_substrate_registry(store, registry)
    assert selected_ref.manifest_profile_sha256 is not None

    profileless_ref = selected_ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(SubstrateRegistryError, match="substrate_registry_profile_selector_missing"):
        load_substrate_registry(store, profileless_ref)


def test_substrate_registry_reader_rejects_mutated_cas_bytes(
    tmp_path: Path, catalog_root: Path
) -> None:
    registry = build_substrate_registry_from_existing_catalogs(catalog_root)
    store = FileSystemCAS(tmp_path / "cas")
    selected_ref = persist_substrate_registry(store, registry)
    blob_path, _manifest_path = store._paths(selected_ref.artifact_id)
    original_bytes = blob_path.read_bytes()
    try:
        blob_path.write_bytes(original_bytes + b"\nmutation")
        with pytest.raises(SubstrateRegistryError):
            load_substrate_registry(store, selected_ref)
    finally:
        blob_path.write_bytes(original_bytes)

    assert load_substrate_registry(store, selected_ref) == registry
