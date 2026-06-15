from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g1"
G1_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g1_substrate_grounding.v1"
G1_RULE_VERSION = "policyos.layer3.g1.substrate_grounding_search.v1"
L1_DCAT_REF = (
    "duckdb://production_data/datasets_full_phase3full_20260327_183054/"
    "dataset_catalog.duckdb#ds_metric_bindings"
)
PINNED_CASE_ID = "ua-msme-affordable-loans-2022"
PINNED_CONSTRUCT_BUNDLE_ID = "ukrainian_msme_credit_constructs"
EXPECTED_MAY_NOT_USE_FOR = {
    "claim_authority",
    "causal_effect",
    "policy_recommendation",
    "publishability",
    "adapter_promotion",
    "useful_design_credit",
    "production_authority",
    "search_hit_as_authority",
}
EXPECTED_HEALTH_METRICS = {
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
}
EXPECTED_FIXTURES = {
    "active_flag_only_source_contract.json",
    "capability_index_used_as_l1_search.json",
    "contaminated_data_asset_port.json",
    "fabric_acquisition_without_source_contract.json",
    "firm_survival_source_contract_v2_spike.json",
    "free_growth_metric_binding_fixture.json",
    "hardcoded_construct_fallback_used_for_closure.json",
    "hardcoded_fallback_not_deleted.json",
    "l1_l5_l6_bounded_surrogate_overclaimed.json",
    "l1_l5_l6_index_coverage_missing.json",
    "local_path_lineage_import_manifest.json",
    "lossy_source_contract_projection.json",
    "manifest_runtime_drift.json",
    "mechanism_generality_single_request.json",
    "missing_rights_source_contract.json",
    "raw_data_forge_output_without_adapter.json",
    "search_engineering_quality_unindexed_scan.json",
    "search_no_ledger_abstention.json",
    "search_recall_seed_miss_domain_ceiling.json",
    "stale_index_domain_ceiling.json",
    "stale_or_missing_g0_v2_dependency_artifact.json",
    "unjustified_l1_surrogate.json",
}


def _g1() -> Any:
    return import_module("polisyos.runtime.quality.layer3_substrate_grounding")


def _fixture(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "policyos.tests.layer3.g1.fixture.v1"
    assert payload["fixture_id"].startswith("layer3-g1-")
    assert "payload" in payload
    assert "expected_issue_codes" in payload
    return payload


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return dict(payload)


def _issue_codes(report: Any) -> set[str]:
    payload = _dump(report)
    return {str(issue["code"]) for issue in payload.get("issues", [])}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_gx_scope_data_home(repo_root: Path) -> None:
    pdc = repo_root / "architecture/policy_design_case"
    _write_json(
        pdc / "layer3_gx_pinned_request.json",
        {
            "schema_version": "policyos.policy_design_case.layer3_gx_pinned_request.v1",
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "request_id": "gx-request:custom-scope",
            "case_id": "case:custom-scope",
            "request_ref": "external-request://layer3-gx/case:custom-scope",
            "producer_ref": "external-request://layer3-gx/pinned-request/case:custom-scope",
            "producer_type": "external_request",
            "producer_root_refs": [
                "external-request://layer3-gx/pinned-request/case:custom-scope"
            ],
            "authority_purpose": "pinned_route_replay_input_only",
            "expected_consumer_path": ["G1", "G2", "G4", "G5"],
            "requested_constructs": [
                {
                    "construct_ref": "solar_credit_access",
                    "role": "cause",
                    "g1_request_shape": "construct_to_metric_binding",
                    "g2_variable_ref": "policy.solar_credit_access",
                    "broad_query_terms": ["solar credit access"],
                }
            ],
            "g1_requests": [
                {
                    "request_id": "g1-request:solar-credit-access",
                    "request_shape": "construct_to_metric_binding",
                    "construct_bundle_id": "solar_credit_constructs",
                    "construct_ref": "solar_credit_access",
                    "scenario_family_ref": "solar_credit_support",
                    "metric_intent": "ground solar credit access substrate data",
                }
            ],
            "g2_request": {},
            "g4_promotion_requests": [],
            "may_not_use_for": ["corpus_supply_fact"],
        },
    )
    _write_json(
        pdc / "layer3_gx_concept_alias_seed_rows.json",
        {
            "schema_version": "policyos.policy_design_case.layer3_gx_concept_alias_seed_rows.v1",
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "producer_ref": "external-request://layer3-gx/concept-alias-seeds/case:custom-scope",
            "producer_type": "external_request",
            "alias_rows": [
                {
                    "row_id": "gx-alias:solar_credit_access",
                    "concept_ref": "solar_credit_access",
                    "aliases": ["solar credit access"],
                    "resolution_status": "unverified",
                    "asserts_corpus_supply": False,
                    "corpus_row_refs": [],
                }
            ],
        },
    )
    _write_json(
        pdc / "layer3_gx_scope_seed_rows.json",
        {
            "schema_version": "policyos.policy_design_case.layer3_gx_scope_seed_rows.v1",
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "producer_ref": "external-request://layer3-gx/scope/case:custom-scope",
            "producer_type": "external_request",
            "scope_rows": [
                {"scope_key": "entity_type", "value": "municipality"},
                {"scope_key": "population", "value": "rural_energy_cooperatives"},
                {"scope_key": "geography", "value": "PL"},
                {"scope_key": "modality", "value": "panel"},
                {"scope_key": "source_family_alias", "value": "solar_credit_panel"},
                {"scope_key": "validity_limit", "value": "demand_seed_only"},
            ],
        },
    )
    _write_json(
        pdc / "layer3_gx_demand_pull_request.json",
        {
            "schema_version": "policyos.policy_design_case.layer3_gx_demand_pull_request.v1",
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "request_id": "gx-demand:custom-scope",
            "case_id": "case:custom-scope",
            "producer_ref": "external-request://layer3-gx/demand-pull/case:custom-scope",
            "producer_type": "external_request",
            "source": "test",
            "timestamp": "2026-06-12T00:00:00Z",
            "accountable_principal_ref": "principal://test",
            "replay_key": "gx-demand:custom-scope",
            "consumer_path": ["G5"],
            "demand_refs": ["demand://custom-scope"],
            "attempted_grounding_path_refs": ["path://custom-scope"],
        },
    )


def _task7_graph_payload(*, verification_status: str = "unverified") -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_concept_alias_graph.v1",
        "rule_version": "policyos.layer3.gx.concept_alias_graph.v1",
        "producer_ref": "external-request://layer3-gx/concept-alias-graph/test",
        "producer_type": "external_request",
        "graph_rows": [
            {
                "row_id": "gx-concept-alias:credit_access",
                "concept_ref": "credit_access",
                "aliases": [
                    "credit access",
                    "affordable loans",
                    "working capital lifeline",
                ],
                "metric_ids": ["credit_access"],
                "variable_names": ["policy.credit_access"],
                "source_layer_refs": [L1_DCAT_REF],
                "jurisdiction_constraints": ["UA"],
                "validity_limits": ["demand_seed_only_no_supply_assertion"],
                "producer_owner": "external-request://layer3-gx/concept-alias-seeds/test",
                "producer_type": "external_request",
                "verification_status": verification_status,
                "resolved_corpus_row_refs": [],
                "rule_version": "policyos.layer3.gx.concept_alias_graph.v1",
            }
        ],
    }


def _write_minimal_dcat_metric_binding(
    repo_root: Path,
    *,
    metric_id: str = "solar_credit_gap",
    alias: str = "solar credit liquidity",
    insert_binding: bool = True,
) -> None:
    catalog_path = repo_root / "production_data/test_dcat/dataset_catalog.duckdb"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(catalog_path))
    try:
        con.execute(
            """
            CREATE TABLE ds_datasets (
                id VARCHAR PRIMARY KEY,
                source VARCHAR,
                title VARCHAR,
                execution_tier VARCHAR,
                preferred_distribution_id VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ds_metric_bindings (
                metric_id VARCHAR NOT NULL,
                dataset_id VARCHAR NOT NULL,
                distribution_id VARCHAR NOT NULL,
                connector_id VARCHAR NOT NULL,
                profile_id VARCHAR,
                request_dataset_id VARCHAR NOT NULL,
                confidence FLOAT DEFAULT 0.0,
                metric_inference_confidence FLOAT DEFAULT 0.0,
                default_filters JSON,
                execution_tier VARCHAR DEFAULT 'catalog',
                source VARCHAR,
                PRIMARY KEY (metric_id, dataset_id, distribution_id)
            )
            """
        )
        con.execute(
            "INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?)",
            (
                "dataset-solar-credit",
                "fixture",
                "Solar credit liquidity fixture",
                "fetchable",
                "dist-solar-credit",
            ),
        )
        if insert_binding:
            con.execute(
                """
                INSERT INTO ds_metric_bindings
                (metric_id, dataset_id, distribution_id, connector_id, profile_id,
                 request_dataset_id, confidence, metric_inference_confidence,
                 default_filters, execution_tier, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metric_id,
                    "dataset-solar-credit",
                    "dist-solar-credit",
                    "fixture.connector",
                    "fixture_profile",
                    alias,
                    0.91,
                    0.88,
                    "{}",
                    "fetchable",
                    "task6_temp_dcat",
                ),
            )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _validate_fixture(name: str) -> Any:
    fixture = _fixture(name)
    expected_codes = set(fixture["expected_issue_codes"])
    assert expected_codes, f"{name} must declare the issue code it is pinning"

    report = _g1().validate_layer3_g1_bundle(REPO_ROOT, fixture["payload"])

    assert _dump(report)["status"] == "fail"
    assert expected_codes <= _issue_codes(report)
    return report


def _request_payload(
    *,
    request_shape: str = "construct_to_metric_binding",
    construct_ref: str = "firm_survival",
) -> dict[str, Any]:
    return {
        "request_id": f"g1-test-request:{request_shape}:{construct_ref}",
        "case_id": PINNED_CASE_ID,
        "construct_bundle_id": PINNED_CONSTRUCT_BUNDLE_ID,
        "request_shape": request_shape,
        "construct_ref": construct_ref,
        "scenario_family_ref": "ua_msme_credit_support",
        "metric_intent": "ground existing substrate source contract for construct",
        "authority_purpose": "layer3_g1_construct_grounding_audit",
        "required_route_refs": [
            "duckdb://production_data/datasets_full_phase3full_20260327_183054/"
            "dataset_catalog.duckdb#ds_metric_bindings",
            "repo://architecture/policy_design_case/layer3_data_asset_ports.json",
            "repo://architecture/policy_design_case/layer3_discovery_search_discipline.json",
        ],
        "may_not_use_for": sorted(EXPECTED_MAY_NOT_USE_FOR),
    }


def test_g1_fixture_contracts_are_valid_json_and_named_by_plan() -> None:
    discovered = {path.name for path in FIXTURE_DIR.glob("*.json")}
    assert discovered >= EXPECTED_FIXTURES
    for name in sorted(EXPECTED_FIXTURES):
        _fixture(name)


def test_g1_requires_g0_v2_dependency_contract_before_grounding() -> None:
    _validate_fixture("stale_or_missing_g0_v2_dependency_artifact.json")


def test_substrate_search_adapter_builds_replayable_ledger_for_pinned_ukraine_construct() -> None:
    g1 = _g1()
    request = g1.Layer3G1SubstrateSearchRequest.model_validate(_request_payload())

    results = g1.build_substrate_grounding_search_adapter(REPO_ROOT, [request])

    assert results
    result = _dump(results[0])
    assert result["case_id"] == PINNED_CASE_ID
    assert result["construct_bundle_id"] == PINNED_CONSTRUCT_BUNDLE_ID
    assert result["construct_ref"] == "firm_survival"
    assert result["search_ledger_refs"]
    assert result["l1_l5_l6_index_coverage_ref"]
    assert set(result["may_not_use_for"]) >= EXPECTED_MAY_NOT_USE_FOR
    for ledger in result["search_ledgers"]:
        ledger_payload = _dump(ledger)
        assert ledger_payload["authoritative_for"] == []
        assert set(ledger_payload["may_not_use_for"]) >= EXPECTED_MAY_NOT_USE_FOR
        assert ledger_payload["replay_key"]


def test_g1_ledgers_emit_common_universal_search_contract_fields() -> None:
    from polisyos.core.contracts.search import SearchLedger

    g1 = _g1()
    request = g1.Layer3G1SubstrateSearchRequest.model_validate(_request_payload())

    results = g1.build_substrate_grounding_search_adapter(REPO_ROOT, [request])
    ledger_payload = _dump(results[0].search_ledgers[0])
    common_ledger = SearchLedger.model_validate(g1.search_ledger_contract_payload(ledger_payload))

    assert common_ledger.request_ref == ledger_payload["typed_request_ref"]
    assert common_ledger.corpus_ref == g1.L1_DCAT_REF
    assert common_ledger.corpus_path == g1.L1_DCAT_PATH.as_posix()
    assert common_ledger.corpus_kind == "canonical"
    assert common_ledger.corpus_snapshot_hash.startswith("sha256:")
    assert common_ledger.configured_store_path == g1.L1_DCAT_PATH.as_posix()
    assert common_ledger.index_freshness["status"] == "pass"
    assert common_ledger.replay_command
    assert common_ledger.replay_expected_output_hash.startswith("sha256:")
    assert {
        candidate.match_mode
        for candidate in (*common_ledger.candidates, *common_ledger.rejected_candidates)
    } <= {"exact", "alias", "lexical", "semantic", "relational", "derived"}


def test_task7_g1_ledger_records_alias_graph_expansion_and_match_modes() -> None:
    g1 = _g1()
    request = g1.Layer3G1SubstrateSearchRequest.model_validate(
        _request_payload(construct_ref="credit_access")
    )

    results = g1.build_substrate_grounding_search_adapter(REPO_ROOT, [request])
    ledger = _dump(results[0].search_ledgers[0])
    plan = ledger["query_plan"]
    candidate_modes = {
        candidate["match_mode"]
        for candidate in (*ledger["candidates"], *ledger["rejected_candidates"])
    }

    assert set(plan["allowed_modes"]) >= {
        "exact",
        "alias",
        "lexical",
        "semantic",
        "relational",
    }
    assert plan["alias_graph_ref"].endswith(
        "architecture/policy_design_case/layer3_gx_concept_alias_graph.json"
    )
    assert plan["alias_graph_status"] in {"ready", "limited", "missing"}
    assert plan["semantic_search_status"] in {"enabled", "disabled_missing_index"}
    assert ledger["query_expansion_traces"]
    trace = ledger["query_expansion_traces"][0]
    assert trace["alias_terms"]
    assert trace["metric_ids"]
    assert trace["source_layer_refs"]
    assert set(trace["modes"]) >= {"exact", "alias", "lexical", "semantic", "relational"}
    assert {"exact", "alias", "lexical", "relational"} <= candidate_modes
    if plan["semantic_search_status"] == "enabled":
        assert "semantic" in candidate_modes


def test_task7_absent_alias_graph_degrades_recall_health(tmp_path: Path) -> None:
    g1 = _g1()

    report = g1.validate_g1_search_recall_freshness(tmp_path, [])
    payload = _dump(report)

    assert payload["search_recall_status"] != "pass"
    assert payload["alias_graph_status"] == "missing"
    assert "layer3_gx_concept_alias_graph_missing" in payload["issue_codes"]


def test_task7_search_health_reports_semantic_hnsw_state() -> None:
    g1 = _g1()

    payload = _dump(g1.validate_g1_search_recall_freshness(REPO_ROOT, []))

    assert payload["semantic_search_status"] in {"enabled", "disabled_missing_index"}
    assert payload["hnsw_index_refs"]
    if payload["semantic_search_status"] == "disabled_missing_index":
        assert all("hnsw" in ref for ref in payload["hnsw_index_refs"])


def test_task1_resolver_query_uses_scope_seed_rows_without_python_fallback(
    tmp_path: Path,
) -> None:
    g1 = _g1()
    _write_gx_scope_data_home(tmp_path)

    query = g1._resolver_query("solar_credit_access", tmp_path)

    assert query["entity_scope"] == "municipality"
    assert query["population_filter"] == {"type": "rural_energy_cooperatives"}
    assert query["geography"] == "PL"
    assert query["source_family_alias"] == "solar_credit_panel"


def test_task7_unverified_alias_broadens_query_but_not_positive_recall(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality import layer3_gx_data_home as gx_home

    g1 = _g1()
    _write_json(tmp_path / gx_home.CONCEPT_ALIAS_GRAPH_PATH, _task7_graph_payload())

    expansion = g1._query_expansion_for_construct(tmp_path, "credit_access")

    assert any(
        term["match_mode"] == "alias" and term["term"] == "working capital lifeline"
        for term in expansion.query_terms
    )
    assert expansion.alias_graph_status == "ready"
    assert expansion.can_support_positive_recall is False
    assert expansion.unverified_alias_refs == ("gx-concept-alias:credit_access",)


def test_task7_data_owned_alias_mutation_finds_candidates_without_code_change(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from polisyos.runtime.quality import layer3_gx_data_home as gx_home

    g1 = _g1()
    _write_minimal_dcat_metric_binding(
        tmp_path,
        metric_id="solar_credit_gap",
        alias="solar credit liquidity",
    )
    graph = _task7_graph_payload()
    graph["graph_rows"][0] = {
        **graph["graph_rows"][0],
        "row_id": "gx-concept-alias:rural_finance_barrier",
        "concept_ref": "rural_finance_barrier",
        "aliases": ["solar credit liquidity"],
        "metric_ids": ["unmatched_metric_id"],
        "variable_names": ["policy.rural_finance_barrier"],
        "verification_status": "unverified",
        "resolved_corpus_row_refs": [],
    }
    _write_json(tmp_path / gx_home.CONCEPT_ALIAS_GRAPH_PATH, graph)
    monkeypatch.setattr(
        g1, "L1_DCAT_PATH", Path("production_data/test_dcat/dataset_catalog.duckdb")
    )
    monkeypatch.setattr(g1, "L1_DCAT_INDEX_DIR", Path("production_data/test_dcat"))
    g1._search_l1_dcat_cached.cache_clear()

    measurement = g1._search_l1_dcat(tmp_path, "rural_finance_barrier")

    assert "solar credit liquidity" in measurement.query_text
    assert (
        "dcat-metric-binding://solar_credit_gap/dataset-solar-credit/dist-solar-credit"
        in g1._candidate_refs_for_mode(measurement, "alias")
    )
    assert measurement.can_support_positive_recall is False
    assert measurement.unverified_alias_refs == ("gx-concept-alias:rural_finance_barrier",)


def test_g1_validator_rejects_decorative_search_replay_key() -> None:
    g1 = _g1()
    bundle = _dump(g1.build_layer3_g1_bundle(REPO_ROOT))
    bundle["search_ledgers"][0]["replay_command"] = ""

    report = g1.validate_layer3_g1_bundle(REPO_ROOT, bundle)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g1_search_replay_command_missing" in _issue_codes(report)


def test_g1_validator_marks_noncanonical_search_store_as_bounded_surrogate() -> None:
    g1 = _g1()
    bundle = _dump(g1.build_layer3_g1_bundle(REPO_ROOT))
    bundle["search_ledgers"][0]["configured_store_path"] = "tests/fixtures/layer3/g1"
    bundle["search_ledgers"][0]["corpus_kind"] = "bounded_surrogate"

    report = g1.validate_layer3_g1_bundle(REPO_ROOT, bundle)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g1_search_bounded_surrogate_cannot_full_pass" in _issue_codes(report)


def test_substrate_search_no_hit_abstention_requires_replayable_frontier() -> None:
    _validate_fixture("search_no_ledger_abstention.json")


def test_search_hit_cannot_satisfy_grounding_without_source_contract_binding() -> None:
    _validate_fixture("fabric_acquisition_without_source_contract.json")


def test_selected_grounding_construct_must_belong_to_pinned_construct_bundle() -> None:
    payload = {
        "schema_version": G1_SCHEMA_VERSION,
        "rule_version": G1_RULE_VERSION,
        "readiness_manifest": {
            "pinned_case_id": PINNED_CASE_ID,
            "pinned_construct_bundle_id": PINNED_CONSTRUCT_BUNDLE_ID,
            "grounding_closure_outcome": "grounded_or_uncertain",
        },
        "grounded_source_contracts": {
            "bindings": [
                {
                    "binding_id": "g1-binding:outside-pinned-bundle",
                    "case_id": PINNED_CASE_ID,
                    "construct_bundle_id": PINNED_CONSTRUCT_BUNDLE_ID,
                    "construct_ref": "municipal_tax_arrears",
                    "grounding_status": "grounded_binding",
                    "source_contract_ref": "source-contract://outside-bundle",
                    "source_contract_snapshot_ref": "sha256:outside-bundle",
                    "lineage_refs": ["repo://production_data/outside-bundle/manifest.json"],
                    "authoritative_for": ["layer3_g1_construct_grounding_audit"],
                    "may_not_use_for": sorted(EXPECTED_MAY_NOT_USE_FOR),
                }
            ]
        },
    }

    report = _g1().validate_layer3_g1_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g1_construct_bundle_mismatch" in _issue_codes(report)


def test_raw_data_forge_output_cannot_satisfy_construct_slot_without_adapter() -> None:
    _validate_fixture("raw_data_forge_output_without_adapter.json")


def test_contaminated_or_missing_rights_asset_fails_closed() -> None:
    contamination_report = _validate_fixture("contaminated_data_asset_port.json")
    missing_rights_report = _validate_fixture("missing_rights_source_contract.json")

    assert "layer3_g1_contaminated_lineage" in _issue_codes(contamination_report)
    assert "layer3_g1_missing_rights" in _issue_codes(missing_rights_report)


def test_acquisition_adapter_records_gap_without_overclaiming_coverage() -> None:
    _validate_fixture("fabric_acquisition_without_source_contract.json")


def test_g1_adapter_preservation_blocks_lossy_projection() -> None:
    _validate_fixture("lossy_source_contract_projection.json")


def test_g1_adapter_contract_registry_loads_with_existing_loader_and_two_paths() -> None:
    g1 = _g1()

    report = g1.validate_g1_adapter_conformance(REPO_ROOT, g1.build_layer3_g1_bundle(REPO_ROOT))

    payload = _dump(report)
    assert payload["status"] == "pass"
    assert payload["adapter_contract_path_count"] == 2
    assert set(payload["adapter_path_ids"]) == {
        "layer3_data_asset_port_to_source_contract",
        "layer3_fabric_acquisition_to_source_contract",
    }


def test_g1_manifest_counts_match_runtime_builder() -> None:
    g1 = _g1()
    bundle = g1.build_layer3_g1_bundle(REPO_ROOT)
    report = g1.validate_layer3_g1_bundle(REPO_ROOT, bundle)

    payload = _dump(report)
    assert payload["status"] == "pass"
    assert payload["summary"]["manifest_runtime_drift_count"] == 0
    assert payload["summary"]["g1_substrate_search_ledger_count"] >= 1
    assert (
        payload["summary"]["source_contract_snapshot_count"]
        == payload["summary"]["grounded_source_contract_binding_count"]
    )


def test_g1_zero_source_contracts_cannot_close_as_grounded_or_uncertain() -> None:
    g1 = _g1()

    bundle = g1.build_layer3_g1_bundle(REPO_ROOT)
    payload = _dump(bundle)
    counts = payload["readiness_manifest"]["counts"]

    assert payload["grounded_source_contracts"]["bindings"] == []
    assert counts["grounded_source_contract_binding_count"] == 0
    assert counts["grounding_closure_outcome"] != "grounded_or_uncertain"
    assert (
        payload["readiness_manifest"]["grounding_closure_outcome"]
        == counts["grounding_closure_outcome"]
    )


def test_g1_validation_rejects_zero_bindings_with_grounded_closure() -> None:
    g1 = _g1()
    payload = _dump(g1.build_layer3_g1_bundle(REPO_ROOT))

    payload["grounded_source_contracts"]["bindings"] = []
    payload["grounded_source_contracts"]["source_contract_snapshots"] = {}
    payload["readiness_manifest"]["grounding_closure_outcome"] = "grounded_or_uncertain"
    payload["readiness_manifest"]["counts"]["grounding_closure_outcome"] = "grounded_or_uncertain"
    payload["readiness_manifest"]["counts"]["grounded_source_contract_binding_count"] = 0

    report = g1.validate_layer3_g1_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g1_grounding_closure_overclaim" in _issue_codes(report)


def test_g1_runtime_uses_construct_agnostic_l1_dcat_search_not_pinned_constants() -> None:
    g1 = _g1()

    assert not hasattr(g1, "G1_PREFERRED_EXISTING_ASSET_CONSTRUCT_ID")
    assert not hasattr(g1, "G1_EXPECTED_ACQUISITION_GAP_CONSTRUCT_ID")
    assert not hasattr(g1, "G1_CREDIT_ACCESS_CONSTRUCT_ID")
    assert not hasattr(g1, "G1_FIRM_SURVIVAL_CONSTRUCT_ID")
    assert g1._l1_query_text("credit_access") == "credit access"
    assert g1._l1_query_text("firm_survival") == "firm survival"

    bundle = g1.build_layer3_g1_bundle(REPO_ROOT)
    payload = _dump(bundle)
    ledgers = payload["search_ledgers"]

    assert any(
        ledger["typed_request_ref"].endswith(":credit_access")
        and ledger["selected_candidate_refs"]
        and ledger["candidate_count"] > 0
        and ledger["measurement_provenance"] == "l1_dcat_query"
        and ledger["query_hash"]
        for ledger in ledgers
    )
    assert any(
        ledger["typed_request_ref"].endswith(":firm_survival")
        and not ledger["selected_candidate_refs"]
        and ledger["absence_or_incompleteness_reason"] == "l1_dcat_no_metric_binding"
        and ledger["measurement_provenance"] == "l1_dcat_query"
        for ledger in ledgers
    )


def test_g1_free_growth_uses_live_l1_dcat_search_not_fixture_loader(
    monkeypatch: Any,
) -> None:
    g1 = _g1()

    def _forbidden_fixture_loader(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("G1 free-growth must not be fixture-only")

    monkeypatch.setattr(g1, "_fixture_payload", _forbidden_fixture_loader)

    report = g1.build_g1_free_growth_report(REPO_ROOT)

    assert report.status == "pass"
    assert report.free_growth_fixture_count == 0
    assert "credit_access" in report.discovered_metric_ids
    assert report.search_route == "l1_dcat_ds_metric_bindings"


def test_g1_search_health_and_strangle_reports_are_measured_not_self_attested() -> None:
    g1 = _g1()
    bundle = g1.build_layer3_g1_bundle(REPO_ROOT)
    payload = _dump(bundle)

    recall = payload["search_recall_freshness"]
    assert recall["search_recall_status"] in {"pass", "fail"}
    assert recall["measurement_provenance"] == "l1_dcat_query"
    assert recall["query_trace_refs"]
    assert recall["search_frontier_ref"].startswith("g1-search-frontier:l1-dcat:")

    quality = payload["search_engineering_quality"]
    assert quality["status"] in {"pass", "fail"}
    assert quality["measurement_provenance"] == "l1_dcat_query"
    assert quality["query_trace_refs"]

    hardcode = payload["hardcode_strangle_delta"]
    assert hardcode["fallback_deletion_status"] == "deleted_or_disabled_no_fallback"
    assert hardcode["issue_codes"] == []
    assert any(
        "src/polisyos/core/contracts/capability_resolution.py" in record["measurement_ref"]
        for record in hardcode["delta_records"]
    )


def test_g1_catalog_search_finds_credit_access_from_construct_query() -> None:
    from polisyos.data_forge import read_api as data_forge_read_api

    store = data_forge_read_api.catalog.DatasetCatalogStore(
        REPO_ROOT
        / "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb",
        REPO_ROOT / "production_data/datasets_full_phase3full_20260327_183054",
    )
    try:
        matches = store.search_metric_bindings("credit", top_k=8)
    finally:
        store.close()

    assert any(match.metric_id == "credit_access" for match in matches)


def test_g1_validation_rejects_self_attested_search_health() -> None:
    g1 = _g1()
    bundle = _dump(g1.build_layer3_g1_bundle(REPO_ROOT))
    bundle["search_recall_freshness"] = {
        **bundle["search_recall_freshness"],
        "search_recall_status": "pass",
        "measurement_provenance": "self_attested",
        "query_trace_refs": (),
    }

    report = g1.validate_layer3_g1_bundle(REPO_ROOT, bundle)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g1_search_recall_not_measured" in _issue_codes(report)


def test_g1_does_not_mutate_g0_source_truth_baseline() -> None:
    g1 = _g1()
    report = g1.validate_layer3_g1_bundle(REPO_ROOT, g1.build_layer3_g1_bundle(REPO_ROOT))

    summary = _dump(report)["summary"]
    assert summary["g0_source_truth_adapter_path_count"] == 9
    assert summary["g1_adapter_contract_path_count"] == 2


def test_g1_uses_requirement_to_capability_resolver_outputs_not_parallel_status_ranker() -> None:
    g1 = _g1()
    bundle = g1.build_layer3_g1_bundle(REPO_ROOT)

    payload = _dump(bundle)

    assert payload["readiness_manifest"]["counts"]["parallel_authority_scorer_count"] == 0
    assert payload["readiness_manifest"]["counts"]["resolver_binding_consumed_count"] >= 1
    assert (
        payload["readiness_manifest"]["counts"]["data_requirement_compiler_bridge_test_count"] >= 1
    )


def test_g1_source_contract_snapshot_is_fabric_v2_not_active_flag_echo() -> None:
    _validate_fixture("active_flag_only_source_contract.json")


def test_selected_source_contract_v2_spike_reports_groundable_or_domain_ceiling() -> None:
    fixture = _fixture("firm_survival_source_contract_v2_spike.json")
    g1 = _g1()

    probe = g1.probe_source_contract_v2_groundability(REPO_ROOT)

    payload = _dump(probe)
    assert payload["construct_ref"] == fixture["payload"]["construct_ref"] == "firm_survival"
    assert payload["groundability_status"] in {
        "valid_source_contract",
        "domain_ceiling_data_insufficiency",
    }
    if payload["groundability_status"] == "valid_source_contract":
        assert payload["source_contract_snapshot"]["schema_version"] == "fabric.source_contract.v2"
        assert payload["source_contract_content_hash"].startswith("sha256:")
    else:
        assert payload["blocker_evidence_refs"]


def test_domain_ceiling_abstention_requires_healthy_search_recall_and_freshness() -> None:
    recall_report = _validate_fixture("search_recall_seed_miss_domain_ceiling.json")
    stale_report = _validate_fixture("stale_index_domain_ceiling.json")

    assert "layer3_g1_search_recall_seed_miss_blocks_domain_ceiling" in _issue_codes(recall_report)
    assert "layer3_g1_stale_index_blocks_domain_ceiling" in _issue_codes(stale_report)


def test_search_recall_seed_miss_blocks_domain_ceiling() -> None:
    _validate_fixture("search_recall_seed_miss_domain_ceiling.json")


def test_stale_index_blocks_domain_ceiling() -> None:
    _validate_fixture("stale_index_domain_ceiling.json")


def test_g1_free_growth_metric_binding_requires_no_code_change() -> None:
    g1 = _g1()

    report = g1.build_g1_free_growth_report(REPO_ROOT)

    payload = _dump(report)
    assert payload["status"] == "pass"
    assert payload["free_growth_fixture_count"] == 0
    assert "credit_access" in payload["discovered_metric_ids"]
    assert payload["code_change_required"] is False
    assert payload["search_route"] == "l1_dcat_ds_metric_bindings"


def test_task6_g1_temp_dcat_metric_insertion_changes_candidates_without_authority(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    g1 = _g1()
    _write_minimal_dcat_metric_binding(tmp_path)
    monkeypatch.setattr(
        g1, "L1_DCAT_PATH", Path("production_data/test_dcat/dataset_catalog.duckdb")
    )
    monkeypatch.setattr(g1, "L1_DCAT_INDEX_DIR", Path("production_data/test_dcat"))
    g1._search_l1_dcat_cached.cache_clear()

    report = g1.build_g1_dcat_free_growth_mutation_report(
        tmp_path,
        construct_ref="solar_credit_gap",
    )
    payload = _dump(report)
    ledger = payload["search_ledger"]

    assert payload["status"] == "pass"
    assert payload["production_readiness_status"] == "bounded_surrogate"
    assert payload["corpus_kind"] == "temp_store"
    assert payload["source_contract_ref"] is None
    assert payload["admission_ref"] is None
    assert (
        "dcat-metric-binding://solar_credit_gap/dataset-solar-credit/dist-solar-credit"
        in (payload["candidate_refs"])
    )
    assert ledger["corpus_kind"] == "temp_store"
    assert ledger["configured_store_path"] == "production_data/test_dcat/dataset_catalog.duckdb"
    assert ledger["selected_candidate_refs"] == payload["candidate_refs"]
    assert ledger["authoritative_for"] == []
    assert "search_hit_as_authority" in ledger["may_not_use_for"]


def test_task6_g1_canonical_overlay_seed_is_recall_only_not_grounding(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    canonical_root = tmp_path / "canonical"
    overlay_root = tmp_path / "overlay"
    _write_minimal_dcat_metric_binding(
        canonical_root,
        metric_id="background_credit_context",
        alias="background liquidity",
        insert_binding=False,
    )
    _write_minimal_dcat_metric_binding(
        overlay_root,
        metric_id="solar_credit_gap",
        alias="solar credit liquidity",
    )
    g1 = _g1()
    monkeypatch.setattr(
        g1, "L1_DCAT_PATH", Path("production_data/test_dcat/dataset_catalog.duckdb")
    )
    monkeypatch.setattr(g1, "L1_DCAT_INDEX_DIR", Path("production_data/test_dcat"))
    g1._search_l1_dcat_cached.cache_clear()

    report = g1.build_g1_canonical_overlay_injection_report(
        canonical_root,
        overlay_repo_root=overlay_root,
        construct_ref="solar_credit_gap",
    )
    payload = _dump(report)
    ledger = payload["overlay_search_ledger"]

    assert payload["status"] == "pass"
    assert payload["canonical_candidate_refs"] == []
    assert payload["overlay_injection_status"] == "pass"
    assert payload["production_readiness_status"] == "bounded_surrogate"
    assert payload["recall_adequacy_scope"] == "recall_only"
    assert payload["source_contract_ref"] is None
    assert payload["admission_ref"] is None
    assert payload["promotion_ref"] is None
    assert payload["grounded_conversion_ref"] is None
    assert payload["canonical_corpus_path"] == "production_data/test_dcat/dataset_catalog.duckdb"
    assert payload["canonical_corpus_snapshot_hash"].startswith("sha256:")
    assert (
        "dcat-metric-binding://solar_credit_gap/dataset-solar-credit/dist-solar-credit"
        in (payload["overlay_candidate_refs"])
    )
    assert ledger["selected_candidate_refs"] == payload["overlay_candidate_refs"]
    assert ledger["authoritative_for"] == []
    assert "search_hit_as_authority" in ledger["may_not_use_for"]


def test_g1_mechanism_generality_requires_two_request_shapes() -> None:
    _validate_fixture("mechanism_generality_single_request.json")


def test_hardcoded_construct_fallback_cannot_close_g1() -> None:
    _validate_fixture("hardcoded_construct_fallback_used_for_closure.json")


def test_hardcoded_fallback_must_be_deleted_or_disabled_for_closure() -> None:
    _validate_fixture("hardcoded_fallback_not_deleted.json")


def test_l1_l5_l6_index_coverage_required_for_g1_search_closure() -> None:
    _validate_fixture("l1_l5_l6_index_coverage_missing.json")


def test_l1_l5_l6_bounded_surrogate_cannot_be_overclaimed_as_full_dcat() -> None:
    _validate_fixture("l1_l5_l6_bounded_surrogate_overclaimed.json")


def test_capability_index_cannot_satisfy_l1_dcat_search() -> None:
    _validate_fixture("capability_index_used_as_l1_search.json")


def test_l1_surrogate_is_unjustified_when_production_dcat_exists() -> None:
    _validate_fixture("unjustified_l1_surrogate.json")


def test_g1_search_engineering_quality_rejects_unindexed_scan() -> None:
    _validate_fixture("search_engineering_quality_unindexed_scan.json")


def test_g1_canonicalizes_ukraine_import_manifest_local_paths_before_lineage() -> None:
    _validate_fixture("local_path_lineage_import_manifest.json")


def test_g1_data_requirement_compiler_records_resolver_ref_without_literal_family_fallback() -> (
    None
):
    from polisyos.data_requirement import DataRequirementCompiler

    g1 = _g1()
    resolver = g1.build_g1_requirement_to_capability_resolver(REPO_ROOT)
    construct = "credit_access"
    claim_ledger = {
        "claims": [
            {
                "claim_id": "claim:g1-credit-access-data-need",
                "claim_family": "implementation",
                "claim_type": "implementation",
                "claim_use": "decision_support",
                "text": "Credit access grounding requires observed Ukraine MSME panel data.",
                "facet_refs": ("facet:ua-msme",),
                "concept_spine_refs": (f"concept://policyos/{construct}",),
                "authority_profile_refs": ("authority_profile.governed",),
            }
        ]
    }
    facets = (
        {
            "facet_id": "facet:ua-msme",
            "facet_type": "population_predicate",
            "value": "ukrainian_msme_credit_constructs",
            "concept_ref": f"concept://policyos/{construct}",
            "authority_profile": "authority_profile.governed",
        },
    )

    report = DataRequirementCompiler(
        capability_resolver=resolver,
        require_capability_index=True,
    ).compile_for_claim_ledger(
        run_id="run-layer3-g1",
        scenario_id="ua_msme_wartime_credit_support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={
            "blocking_frontier": [{"metadata": {"required_evidence_constructs": [construct]}}]
        },
        authority_profile_refs=("authority_profile.governed",),
    )

    assert report.specs == ()
    assert report.metadata["capability_index_refs"] == ("layer3-g1:substrate-grounding:l1-dcat",)


def test_g1_parquet_profile_uses_metadata_only_and_never_full_scans() -> None:
    g1 = _g1()
    bundle = g1.build_layer3_g1_bundle(REPO_ROOT)

    counts = _dump(bundle)["readiness_manifest"]["counts"]

    assert counts["parquet_profile_mode"] == "metadata_only"
    assert counts["full_parquet_scan_count"] == 0
