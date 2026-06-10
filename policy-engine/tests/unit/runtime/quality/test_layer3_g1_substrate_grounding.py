from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g1"
G1_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g1_substrate_grounding.v1"
G1_RULE_VERSION = "policyos.layer3.g1.substrate_grounding_search.v1"
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
    assert payload["summary"]["source_contract_snapshot_count"] >= payload["summary"][
        "grounded_or_uncertain_construct_count"
    ]


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
    assert payload["readiness_manifest"]["counts"]["data_requirement_compiler_bridge_test_count"] >= 1


def test_g1_source_contract_snapshot_is_fabric_v2_not_active_flag_echo() -> None:
    _validate_fixture("active_flag_only_source_contract.json")


def test_firm_survival_source_contract_v2_spike_reports_groundable_or_domain_ceiling() -> None:
    fixture = _fixture("firm_survival_source_contract_v2_spike.json")
    g1 = _g1()

    probe = g1.probe_firm_survival_source_contract_v2_groundability(REPO_ROOT)

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

    assert "layer3_g1_search_recall_seed_miss_blocks_domain_ceiling" in _issue_codes(
        recall_report
    )
    assert "layer3_g1_stale_index_blocks_domain_ceiling" in _issue_codes(stale_report)


def test_search_recall_seed_miss_blocks_domain_ceiling() -> None:
    _validate_fixture("search_recall_seed_miss_domain_ceiling.json")


def test_stale_index_blocks_domain_ceiling() -> None:
    _validate_fixture("stale_index_domain_ceiling.json")


def test_g1_free_growth_metric_binding_requires_no_code_change() -> None:
    fixture = _fixture("free_growth_metric_binding_fixture.json")
    g1 = _g1()

    report = g1.build_g1_free_growth_report(REPO_ROOT)

    payload = _dump(report)
    assert payload["status"] == "pass"
    assert payload["free_growth_fixture_count"] >= 1
    assert fixture["payload"]["metric_binding"]["metric_id"] in payload["discovered_metric_ids"]
    assert payload["code_change_required"] is False
    assert payload["search_route"] == "l1_dcat_ds_metric_bindings"


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


def test_g1_data_requirement_compiler_consumes_binding_via_existing_resolver_port() -> None:
    from polisyos.data_requirement import DataRequirementCompiler

    g1 = _g1()
    resolver = g1.build_g1_requirement_to_capability_resolver(REPO_ROOT)
    claim_ledger = {
        "claims": [
            {
                "claim_id": "claim:g1-firm-survival-data-need",
                "claim_family": "implementation",
                "claim_type": "implementation",
                "claim_use": "decision_support",
                "text": "Firm survival grounding requires observed Ukraine MSME panel data.",
                "facet_refs": ("facet:ua-msme",),
                "concept_spine_refs": ("concept://policyos/firm_survival",),
                "authority_profile_refs": ("authority_profile.governed",),
            }
        ]
    }
    facets = (
        {
            "facet_id": "facet:ua-msme",
            "facet_type": "population_predicate",
            "value": "ukrainian_msme_credit_constructs",
            "concept_ref": "concept://policyos/firm_survival",
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
            "blocking_frontier": [
                {"metadata": {"required_evidence_constructs": ["firm_survival"]}}
            ]
        },
        authority_profile_refs=("authority_profile.governed",),
    )

    assert report.specs
    assert report.metadata["capability_index_refs"]
    assert all(
        str(ref).startswith("layer3-g1:")
        for ref in report.metadata["capability_index_refs"]
    )


def test_g1_parquet_profile_uses_metadata_only_and_never_full_scans() -> None:
    g1 = _g1()
    bundle = g1.build_layer3_g1_bundle(REPO_ROOT)

    counts = _dump(bundle)["readiness_manifest"]["counts"]

    assert counts["parquet_profile_mode"] == "metadata_only"
    assert counts["full_parquet_scan_count"] == 0
