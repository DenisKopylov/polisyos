from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
G3_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g3_analytics_search.v1"
G3_RULE_VERSION = "policyos.layer3.g3.analytics_search.v1"
G3_SURFACE_ID = "layer3_g3_proof_carrying_audit_surface"

EXPECTED_DTOS = {
    "Layer3G3ValidationIssue",
    "Layer3G3ValidationReport",
    "Layer3G3AnalyticsRequest",
    "Layer3G3L2SkgProofCandidateBinding",
    "Layer3G3IRCatalogSearchLedger",
    "Layer3G3IRAnalyticsQueryTrace",
    "Layer3G3IRCatalogCoverageReport",
    "Layer3G3ArtifactStoreIndex",
    "Layer3G3CertificateCandidate",
    "Layer3G3CertificateResolutionRecord",
    "Layer3G3CertificateResolutionReport",
    "Layer3G3SearchRecallSeedRecord",
    "Layer3G3SearchRecallFreshnessReport",
    "Layer3G3SearchEngineeringQualityReport",
    "Layer3G3MethodRequirementBinding",
    "Layer3G3SemanticSpineBinding",
    "Layer3G3ProofCarryingAnalyticsBinding",
    "Layer3G3IRAnalyticsBridgeBinding",
    "Layer3G3S11PrerequisiteBinding",
    "Layer3G3S11CalibrationBinding",
    "Layer3G3S11PredictivePostureBinding",
    "Layer3G3ClaimRegistryConsumerGateRecord",
    "Layer3G3BaselineComparisonConsumerGateRecord",
    "Layer3G3W12DConsumerGateRecord",
    "Layer3G3PublicExportProjectionRefSurface",
    "Layer3G3ProofCarryingAuditSurface",
    "Layer3G3AdapterContractRegistryStatus",
    "Layer3G3AdapterAdmissionBundle",
    "Layer3G3GeneratedArtifactRegistrationStatus",
    "Layer3G3ConformanceReport",
    "Layer3G3ReadinessManifest",
    "Layer3G3Bundle",
}

EXPECTED_BUILDERS_AND_VALIDATORS = {
    "build_layer3_g3_bundle",
    "validate_layer3_g3_bundle",
    "build_g3_l2_skg_proof_candidate_bindings",
    "build_g3_ir_catalog_coverage",
    "search_ir_analytics_catalog",
    "produce_g3_deterministic_first_case_certificate",
    "build_g3_ir_artifact_store_index",
    "resolve_g3_certificate_candidates",
    "build_g3_certificate_resolution_report",
    "build_g3_search_recall_freshness",
    "build_g3_search_engineering_quality_report",
    "build_g3_method_requirement_bindings",
    "build_g3_semantic_spine_bindings",
    "build_g3_proof_carrying_analytics_bindings",
    "build_g3_ir_analytics_bridge_bindings",
    "build_g3_s11_prerequisite_bindings",
    "build_g3_s11_calibration_bindings",
    "build_g3_s11_predictive_posture_bindings",
    "build_g3_claim_registry_consumer_gate",
    "build_g3_baseline_comparison_consumer_gate",
    "build_g3_w12d_consumer_gate",
    "build_g3_public_export_projection_ref_surface",
    "build_g3_proof_carrying_audit_surface",
    "build_g3_adapter_contract_registry_status",
    "build_g3_generated_artifact_registration_status",
    "build_g3_conformance_report",
    "validate_g3_adapter_conformance",
}

REQUIRED_ISSUE_CODES = {
    "layer3_g3_g0_dependency_not_ready",
    "layer3_g3_g1_dependency_not_ready",
    "layer3_g3_g2_dependency_not_ready",
    "layer3_g3_l2_skg_dependency_not_ready",
    "layer3_g3_l2_skg_proof_candidate_binding_missing",
    "layer3_g3_ir_catalog_coverage_missing",
    "layer3_g3_ir_catalog_hardcode_closure",
    "layer3_g3_ir_catalog_search_not_indexed",
    "layer3_g3_search_ledger_missing",
    "layer3_g3_query_trace_missing",
    "layer3_g3_search_hit_laundered_as_certificate",
    "layer3_g3_fixture_certificate_laundered",
    "layer3_g3_unresolved_certificate_binding",
    "layer3_g3_certificate_resolution_missing",
    "layer3_g3_negative_certificate_ignored",
    "layer3_g3_proof_composability_bypass",
    "layer3_g3_method_requirement_missing",
    "layer3_g3_method_requirement_bypass",
    "layer3_g3_uncertainty_or_bounds_ref_missing",
    "layer3_g3_bounds_dual_certificate_missing",
    "layer3_g3_proof_carrying_record_missing",
    "layer3_g3_ir_analytics_bridge_missing",
    "layer3_g3_s11_prerequisite_missing",
    "layer3_g3_s11_posture_without_s6_s10",
    "layer3_g3_claim_registry_consumer_gate_missing",
    "layer3_g3_baseline_comparison_consumer_gate_missing",
    "layer3_g3_w12d_consumer_gate_missing",
    "layer3_g3_public_raw_proof_leak",
    "layer3_g3_recommendation_authority_leak",
    "layer3_g3_claim_authority_leak",
    "layer3_g3_closeout_authority_leak",
    "layer3_g3_adapter_contract_registry_missing",
    "layer3_g3_adapter_registry_summary_only",
    "layer3_g3_adapter_unknown_path",
    "layer3_g3_adapter_semantic_loss",
    "layer3_g3_adapter_touchpoint_unregistered",
    "layer3_g3_persisted_artifact_missing",
    "layer3_g3_manifest_runtime_drift",
    "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",
    "layer3_g3_search_ceiling_repair_required",
    "layer3_g3_full_cas_listing_in_request_path",
    "layer3_g3_tenant_scoped_manifest_denied",
    "layer3_g3_stale_artifact_index_claimed_as_proof_ceiling",
    "layer3_g3_store_configuration_missing",
    "layer3_g3_replay_record_missing",
    "layer3_g3_import_laziness_violation",
}

EXPECTED_BUNDLE_SECTIONS = {
    "adapter_admission_registry",
    "l2_skg_proof_candidate_bindings",
    "ir_analytics_search_ledgers",
    "ir_analytics_query_traces",
    "ir_catalog_coverage",
    "ir_artifact_store_index",
    "certificate_resolution_report",
    "search_recall_freshness",
    "method_requirement_bindings",
    "semantic_spine_bindings",
    "proof_carrying_analytics_records",
    "ir_analytics_claim_bridge",
    "s11_prerequisite_bindings",
    "s11_calibration_bindings",
    "s11_predictive_posture_bindings",
    "claim_registry_consumer_gate",
    "baseline_comparison_consumer_gate",
    "w12d_consumer_gate",
    "public_export_projection_refs",
    "proof_carrying_audit_surface",
    "search_engineering_quality",
    "conformance_report",
    "health_metric_delta",
    "adapter_contract_registry",
    "readiness_manifest",
}

EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "rule_version",
    "g0_dependency_status",
    "g1_dependency_status",
    "g2_dependency_status",
    "g3_l2_skg_dependency_status",
    "g3_l2_skg_proof_candidate_binding_count",
    "g3_ir_catalog_coverage_status",
    "g3_ir_artifact_store_index_status",
    "g3_search_ledger_count",
    "g3_query_trace_count",
    "g3_certificate_resolution_status",
    "g3_resolved_certificate_count",
    "g3_search_recall_freshness_status",
    "g3_search_recall_seed_count",
    "g3_search_recall_recalled_seed_count",
    "g3_method_requirement_binding_count",
    "g3_proof_carrying_record_count",
    "g3_ir_analytics_bridge_status",
    "g3_s11_prerequisite_binding_status",
    "g3_s11_predictive_posture_binding_count",
    "g3_claim_registry_consumer_gate_status",
    "g3_baseline_comparison_consumer_gate_status",
    "g3_w12d_consumer_gate_status",
    "g3_public_export_projection_status",
    "g3_search_engineering_quality_status",
    "g3_conformance_status",
    "g3_adapter_contract_registry_status",
    "g3_adapter_contract_path_count",
    "g3_health_metric_ids",
}


def _g3() -> Any:
    return import_module("polisyos.runtime.quality.proving_ground.proof_carrying_analytics_search")


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return dict(payload)


def _issue_codes(report: Any) -> set[str]:
    return {str(issue["code"]) for issue in _dump(report).get("issues", [])}


def test_layer3_g3_runtime_module_declares_schema_builders_dtos_and_issue_codes() -> None:
    g3 = _g3()

    assert g3.LAYER3_G3_SCHEMA_VERSION == G3_SCHEMA_VERSION
    assert g3.LAYER3_G3_RULE_VERSION == G3_RULE_VERSION
    assert g3.LAYER3_G3_SURFACE_ID == G3_SURFACE_ID
    assert set(g3.ALL_ISSUE_CODES) >= REQUIRED_ISSUE_CODES
    for name in EXPECTED_DTOS | EXPECTED_BUILDERS_AND_VALIDATORS:
        assert hasattr(g3, name), name


def test_layer3_g3_public_dtos_are_strict_pydantic_contracts() -> None:
    g3 = _g3()

    for name in EXPECTED_DTOS:
        dto = getattr(g3, name)
        assert issubclass(dto, BaseModel), name
        assert dto.model_config.get("extra") == "forbid", name


def test_layer3_g3_bundle_contains_search_resolution_bridge_s11_and_consumer_sections() -> None:
    g3 = _g3()
    bundle = g3.build_layer3_g3_bundle(REPO_ROOT)
    payload = _dump(bundle)

    assert set(payload) >= EXPECTED_BUNDLE_SECTIONS
    assert payload["readiness_manifest"]["schema_version"] == G3_SCHEMA_VERSION
    assert set(payload["readiness_manifest"]) >= EXPECTED_MANIFEST_KEYS
    assert payload["search_recall_freshness"]["status"] == "pass"
    assert payload["readiness_manifest"]["g3_search_recall_freshness_status"] == "pass"
    assert payload["readiness_manifest"]["g3_search_recall_seed_count"] >= 3
    assert (
        payload["readiness_manifest"]["g3_search_recall_recalled_seed_count"]
        == payload["readiness_manifest"]["g3_search_recall_seed_count"]
    )


def test_layer3_g3_validator_fails_closed_on_unresolved_search_and_authority_laundering() -> None:
    g3 = _g3()
    report = g3.validate_layer3_g3_bundle(REPO_ROOT, g3.build_layer3_g3_bundle(REPO_ROOT))
    payload = _dump(report)

    assert set(payload["summary"]) >= EXPECTED_MANIFEST_KEYS
    assert set(payload.get("issue_code_dictionary", g3.ALL_ISSUE_CODES)) >= REQUIRED_ISSUE_CODES


def test_layer3_g3_validator_fails_closed_when_search_recall_freshness_fails() -> None:
    g3 = _g3()
    bundle = g3.build_layer3_g3_bundle(REPO_ROOT)
    broken_recall = bundle.search_recall_freshness.model_copy(
        update={
            "status": "fail",
            "recalled_seed_count": 0,
            "missed_seed_count": bundle.search_recall_freshness.known_seed_count,
            "issue_codes": ("layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",),
        }
    )

    report = g3.validate_layer3_g3_bundle(
        REPO_ROOT,
        bundle.model_copy(update={"search_recall_freshness": broken_recall}),
    )

    assert report.status == "fail"
    assert "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling" in _issue_codes(report)


def test_layer3_g3_task1_request_and_search_dtos_are_strict() -> None:
    g3 = _g3()

    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:test",
        claim_id="claim:test",
        case_id="case:test",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
    )

    assert request.limit == 16
    assert request.may_not_use_for
    with pytest.raises(ValidationError):
        g3.Layer3G3AnalyticsRequest(
            request_id="g3-request:test",
            claim_id="claim:test",
            case_id="case:test",
            cause="agriculture.fertilizer_use",
            effect="agriculture.food_nutritional_quality",
            surprise_contract=True,
        )


def test_layer3_g3_task1_loads_g2_dependencies_and_builds_control_plane_bindings() -> None:
    g3 = _g3()
    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:l2-binding",
        claim_id="claim:g3:l2-binding",
        case_id="case:g3:l2-binding",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        semantic_spine_refs=("semantic-spine://g2/default",),
        method_requirement_refs=("method-requirement://g2/default",),
    )

    dependencies = g3.load_g3_l2_skg_dependency_artifacts(REPO_ROOT)
    bindings = g3.build_g3_l2_skg_proof_candidate_bindings(request, dependencies)

    assert dependencies.status == "pass"
    assert bindings
    assert bindings[0].status == "pass"
    assert bindings[0].claim_id == request.claim_id
    assert bindings[0].canonical_l2_route == "scholar_knowledge.duckdb"
    assert bindings[0].semantic_spine_refs == request.semantic_spine_refs
    assert bindings[0].method_requirement_refs == request.method_requirement_refs
    assert bindings[0].skg_row_refs
    assert bindings[0].search_frontier_refs
    assert bindings[0].certificate_refs == ()
    assert bindings[0].authoritative_for == ()
    assert "search_hit_as_certificate" in bindings[0].may_not_use_for


def test_layer3_g3_task1_g2_dependency_gate_blocks_missing_or_unhealthy_route(
    tmp_path: Path,
) -> None:
    g3 = _g3()

    dependencies = g3.load_g3_l2_skg_dependency_artifacts(tmp_path)

    assert dependencies.status == "fail"
    assert "layer3_g3_l2_skg_dependency_not_ready" in dependencies.issue_codes
    assert "layer3_g3_search_ceiling_repair_required" in dependencies.issue_codes


def test_layer3_g3_task1_builds_indexed_ir_catalog_coverage_with_certificate_fields() -> None:
    g3 = _g3()

    coverage = g3.build_g3_ir_catalog_coverage(REPO_ROOT)
    proof_rows = [
        row
        for row in coverage.catalog_rows
        if row.name in {"ProofBundle", "ProofComposabilityCertificate", "NegativeCertificate"}
    ]

    assert coverage.status == "pass"
    assert coverage.catalog_backend == "duckdb_materialized"
    assert coverage.full_catalog_route not in {
        "fixture",
        "manual_class_list",
        "curated_facade_only",
        "docs_index_only",
        "compiler_bridge_view",
    }
    assert coverage.docs_index_authoritative is False
    assert coverage.catalog_snapshot_hash_ref.startswith("sha256:")
    assert coverage.analytics_type_count >= len(proof_rows) >= 2
    assert coverage.certificate_type_count >= 1
    assert coverage.ref_field_count >= 1
    assert any(row.certificate_field_refs or row.ref_field_refs for row in proof_rows)


def test_layer3_g3_task1_searches_materialized_ir_catalog_with_replayable_ledgers() -> None:
    g3 = _g3()
    coverage = g3.build_g3_ir_catalog_coverage(REPO_ROOT)
    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:ir-search",
        claim_id="claim:g3:ir-search",
        case_id="case:g3:ir-search",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        certificate_kinds=("proof_bundle", "certificate", "negative_certificate"),
        limit=8,
    )

    result = g3.search_ir_analytics_catalog(request, coverage)

    assert result.ledger.canonical_route == "ir_schema_catalog_duckdb_materialized"
    assert result.ledger.catalog_backend == "duckdb"
    assert result.ledger.result_count > 0
    assert result.ledger.result_count <= request.limit
    assert result.ledger.selected_candidate_refs
    assert result.ledger.authoritative_for == ()
    assert "search_hit_as_certificate" in result.ledger.may_not_use_for
    assert len(result.query_traces) == 1
    assert result.query_traces[0].bounded_result_limit == request.limit
    assert result.query_traces[0].predicate_refs


def test_layer3_g3_task1_search_recall_freshness_replays_known_groundable_seeds() -> None:
    g3 = _g3()
    bundle = g3.build_layer3_g3_bundle(REPO_ROOT)
    payload = _dump(bundle.search_recall_freshness)

    assert payload["status"] == "pass"
    assert payload["freshness_status"] == "pass"
    assert payload["known_seed_count"] >= 3
    assert payload["recalled_seed_count"] == payload["known_seed_count"]
    assert payload["missed_seed_count"] == 0
    assert {
        "g3-known-seed:l2-skg-proof-candidate-route",
        "g3-known-seed:ir-analytics-proof-catalog",
        "g3-known-seed:resolved-proof-certificate",
    } <= {seed["seed_id"] for seed in payload["seed_records"]}
    assert payload["catalog_snapshot_hash_ref"].startswith("sha256:")
    assert payload["artifact_snapshot_hash_ref"].startswith("sha256:")
    assert payload["search_ledger_refs"]
    assert payload["query_trace_refs"]
    assert payload["payload_fingerprint_refs"]
    assert payload["issue_codes"] == []


def test_layer3_g3_task1_search_recall_freshness_fails_before_proof_domain_ceiling() -> None:
    g3 = _g3()
    bundle = g3.build_layer3_g3_bundle(REPO_ROOT)
    broken_resolution = bundle.certificate_resolution_report.model_copy(
        update={
            "status": "fail",
            "resolved_certificate_count": 0,
            "payload_fingerprint_refs": (),
            "issue_codes": ("layer3_g3_unresolved_certificate_binding",),
        }
    )

    report = g3.build_g3_search_recall_freshness(
        dependencies=g3.load_g3_l2_skg_dependency_artifacts(REPO_ROOT),
        ir_catalog_coverage=bundle.ir_catalog_coverage,
        search_ledgers=bundle.ir_analytics_search_ledgers,
        query_traces=(),
        ir_artifact_store_index=bundle.ir_artifact_store_index.model_copy(update={"stale": True}),
        certificate_resolution_report=broken_resolution,
    )
    payload = _dump(report)

    assert payload["status"] == "fail"
    assert payload["freshness_status"] == "fail"
    assert payload["missed_seed_count"] >= 1
    assert "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling" in payload["issue_codes"]
    assert "layer3_g3_search_ceiling_repair_required" in payload["issue_codes"]


def test_layer3_g3_task1_rejects_forbidden_catalog_routes_for_full_coverage() -> None:
    g3 = _g3()
    coverage = g3.build_g3_ir_catalog_coverage(REPO_ROOT).model_copy(
        update={"full_catalog_route": "manual_class_list"}
    )

    report = g3.validate_layer3_g3_bundle(
        REPO_ROOT,
        g3.build_layer3_g3_bundle(REPO_ROOT).model_copy(update={"ir_catalog_coverage": coverage}),
    )

    assert report.status == "fail"
    assert "layer3_g3_ir_catalog_hardcode_closure" in _issue_codes(report)


def test_layer3_g3_task1_free_growth_catalog_entry_is_discoverable_without_code_changes() -> None:
    g3 = _g3()
    synthetic = {
        "entry_id": "ir-analytics-catalog-entry:synthetic-proof-producer",
        "name": "SyntheticProofProducerContract",
        "fqn": "polisyos.ir.analytics.synthetic_fixture.SyntheticProofProducerContract",
        "module": "polisyos.ir.analytics.synthetic_fixture",
        "kind": "pydantic_model",
        "schema_version": "synthetic.v1",
        "public_status": "package_facade",
        "exported": True,
        "field_refs": ("claim_id", "synthetic_certificate_ref"),
        "ref_field_refs": ("synthetic_certificate_ref",),
        "certificate_field_refs": ("synthetic_certificate_ref",),
        "proof_status_field_refs": ("proof_status",),
        "composability_field_refs": ("proof_composability_ref",),
        "persistence_helper_refs": ("put_json_artifact",),
        "producer_refs": ("producer://synthetic/free-growth",),
        "certificate_kinds": ("synthetic_certificate",),
    }
    coverage = g3.build_g3_ir_catalog_coverage(REPO_ROOT, additional_entries=(synthetic,))
    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:free-growth",
        claim_id="claim:g3:free-growth",
        case_id="case:g3:free-growth",
        cause="synthetic",
        effect="proof",
        catalog_query_text="SyntheticProofProducerContract",
        certificate_kinds=("synthetic_certificate",),
        limit=4,
    )

    result = g3.search_ir_analytics_catalog(request, coverage)

    assert "ir-analytics-catalog-entry:synthetic-proof-producer" in (
        result.ledger.selected_candidate_refs
    )
    assert coverage.free_growth_entry_count == 1


def test_task6_g3_ir_proof_candidate_insertion_is_replayable_but_not_certificate_authority() -> (
    None
):
    from polisyos.runtime.quality.proving_ground.status_decision_reducers import (
        G3ProofAuthorityInputs,
        Layer3ReducerInputRef,
        reduce_g3_proof_authority,
    )

    g3 = _g3()
    synthetic = {
        "entry_id": "ir-analytics-catalog-entry:task6-proof-candidate",
        "name": "Task6ProofCandidateContract",
        "fqn": "polisyos.ir.analytics.synthetic_fixture.Task6ProofCandidateContract",
        "module": "polisyos.ir.analytics.synthetic_fixture",
        "kind": "pydantic_model",
        "schema_version": "task6.synthetic.v1",
        "public_status": "package_facade",
        "exported": True,
        "field_refs": ("claim_id", "proof_bundle_ref"),
        "ref_field_refs": ("proof_bundle_ref",),
        "certificate_field_refs": ("proof_bundle_ref",),
        "proof_status_field_refs": ("proof_status",),
        "composability_field_refs": ("proof_composability_ref",),
        "persistence_helper_refs": ("put_json_artifact",),
        "producer_refs": ("producer://synthetic/task6-proof-candidate",),
        "certificate_kinds": ("proof_bundle",),
    }
    coverage = g3.build_g3_ir_catalog_coverage(REPO_ROOT, additional_entries=(synthetic,))
    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:task6-proof-candidate",
        claim_id="claim:g3:task6-proof-candidate",
        case_id="case:g3:task6-proof-candidate",
        cause="task6",
        effect="proof",
        comparison_ref="comparison://g3/task6-proof-candidate",
        baseline_ref="baseline://g3/task6-proof-candidate",
        alternative_refs=("alternative://g3/task6-proof-candidate",),
        concept_refs=("concept://g3/task6-proof-candidate",),
        semantic_spine_refs=("semantic-spine://g3/task6-proof-candidate",),
        method_requirement_refs=("g3-method-req:task6-proof-candidate",),
        catalog_query_text="Task6ProofCandidateContract",
        certificate_kinds=("proof_bundle",),
        limit=4,
    )

    result = g3.search_ir_analytics_catalog(request, coverage)
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_task3_point_requirement(request),),
    )
    proof_bindings = g3.build_g3_proof_carrying_analytics_bindings(
        request=request,
        certificate_resolution_report=g3.Layer3G3CertificateResolutionReport(
            status="fail",
            selected_candidate_count=len(result.ledger.selected_candidate_refs),
            issue_codes=("layer3_g3_search_hit_laundered_as_certificate",),
        ),
        method_requirement_bindings=method_bindings,
    )
    decision = reduce_g3_proof_authority(
        G3ProofAuthorityInputs(
            proof_candidate_status="candidate",
            certificate_status="missing",
            input_refs=(
                Layer3ReducerInputRef(
                    ref="duckdb://memory/layer3_g3_ir_analytics_catalog#task6-proof-candidate",
                    content_hash="sha256:" + "8" * 64,
                    producer_ref="measurement://layer3-g3/task6-ir-catalog-search",
                    producer_type="measurement",
                    producer_root_refs=("measurement://layer3-g3/task6-ir-catalog-root",),
                ),
            ),
        )
    )

    ledger = _dump(result.ledger)
    assert "ir-analytics-catalog-entry:task6-proof-candidate" in (ledger["selected_candidate_refs"])
    assert ledger["replay_key"]
    assert ledger["authoritative_for"] == []
    assert "search_hit_as_certificate" in ledger["may_not_use_for"]
    assert coverage.free_growth_entry_count == 1
    assert proof_bindings[0].status == "fail"
    assert "layer3_g3_search_hit_laundered_as_certificate" in proof_bindings[0].issue_codes
    assert decision.status == "typed_blocker"
    assert {
        "layer3_g3_proof_candidate_not_authority",
        "layer3_g3_certificate_not_valid",
    } <= set(decision.blocker_refs)


def test_layer3_g3_task1_engineering_quality_detects_unindexed_or_unbounded_search() -> None:
    g3 = _g3()
    coverage = g3.build_g3_ir_catalog_coverage(REPO_ROOT)
    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:engineering-quality",
        claim_id="claim:g3:engineering-quality",
        case_id="case:g3:engineering-quality",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        limit=8,
    )
    result = g3.search_ir_analytics_catalog(request, coverage)

    passing = g3.build_g3_search_engineering_quality_report(
        coverage=coverage,
        search_result=result,
    )
    failing = g3.build_g3_search_engineering_quality_report(
        coverage=coverage.model_copy(update={"catalog_backend": "linear_scan"}),
        search_result=result,
        per_request_module_walk_count=1,
        per_request_json_scan_count=1,
        unbounded_query_count=1,
    )

    assert passing.status == "pass"
    assert failing.status == "fail"
    assert "layer3_g3_ir_catalog_search_not_indexed" in failing.issue_codes


def test_layer3_g3_task2_indexes_selected_artifact_refs_without_full_store_listing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task2_request(g3, "selected-index")
    candidates = g3.produce_g3_deterministic_first_case_certificate(request, store=store)

    def _fail_full_listing() -> list[Any]:
        raise AssertionError("normal G3 selected-ref indexing must not call iter_artifact_ids")

    monkeypatch.setattr(store, "iter_artifact_ids", _fail_full_listing)
    index = g3.build_g3_ir_artifact_store_index(
        store=store,
        selected_candidates=candidates,
    )

    assert index.status == "pass"
    assert index.full_listing_used is False
    assert index.selected_candidate_count == 1
    assert index.indexed_artifact_refs
    assert index.payload_fingerprint_refs
    assert "layer3_g3_full_cas_listing_in_request_path" not in index.issue_codes


def test_layer3_g3_task2_resolves_positive_proof_bundle_with_typed_loader(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task2_request(g3, "positive-proof")
    candidates = g3.produce_g3_deterministic_first_case_certificate(request, store=store)
    index = g3.build_g3_ir_artifact_store_index(store=store, selected_candidates=candidates)

    report = g3.build_g3_certificate_resolution_report(
        candidates=candidates,
        artifact_index=index,
        store=store,
    )

    assert report.status == "pass"
    assert report.resolved_certificate_count == 1
    assert report.positive_resolved_certificate_count == 1
    assert report.blocking_certificate_count == 0
    assert report.payload_fingerprint_refs
    assert report.records[0].typed_payload_kind == "ProofBundle"
    assert report.records[0].evidence_role == "positive"
    assert report.records[0].positive_proof_closure is True
    assert report.records[0].payload_fingerprint_ref.startswith("sha256:")


def test_layer3_g3_task2_unresolved_certificate_string_fails_closed() -> None:
    g3 = _g3()
    candidate = g3.Layer3G3CertificateCandidate(
        candidate_id="g3-certificate-candidate:fixture-string",
        certificate_kind="proof_bundle",
        candidate_ref="certificate://layer2/s11/fixture",
        source="fixture_string",
        selected_ref_only=True,
    )

    report = g3.build_g3_certificate_resolution_report(candidates=(candidate,))

    assert report.status == "fail"
    assert report.resolved_certificate_count == 0
    assert "layer3_g3_unresolved_certificate_binding" in report.issue_codes
    assert report.records[0].status == "fail"


def test_layer3_g3_task2_negative_certificate_resolves_and_blocks_positive_closure(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.analytics.negative_certificate import (
        BlockingType,
        NegativeCertificate,
        persist_negative_certificate,
    )

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_negative_certificate(
        store,
        NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description="Synthetic hedge blocks point identification.",
        ),
    )
    candidate = g3.Layer3G3CertificateCandidate(
        candidate_id="g3-certificate-candidate:negative",
        certificate_kind="negative_certificate",
        candidate_ref="g3-candidate://negative",
        source="ir.analytics.negative_certificate.persist_negative_certificate",
        artifact_ref=ref.model_dump(mode="json"),
    )

    report = g3.build_g3_certificate_resolution_report(
        candidates=(candidate,),
        artifact_index=g3.build_g3_ir_artifact_store_index(
            store=store,
            selected_candidates=(candidate,),
        ),
        store=store,
    )

    assert report.status == "blocked"
    assert report.resolved_certificate_count == 1
    assert report.positive_resolved_certificate_count == 0
    assert report.blocking_certificate_count == 1
    assert report.records[0].typed_payload_kind == "NegativeCertificate"
    assert report.records[0].evidence_role == "blocking"
    assert "layer3_g3_negative_certificate_ignored" not in report.issue_codes


def test_layer3_g3_task2_rederive_composability_blocks_reusable_proof(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.analytics.proof_composability import (
        build_proof_composability_certificate,
        persist_proof_composability_certificate,
    )

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_proof_composability_certificate(
        store,
        build_proof_composability_certificate(
            source_fragment_id="fragment:g3",
            checked_query="P(y|do(x))",
            status="rederive",
            broken_witness_ids=("witness:broken",),
        ),
    )
    candidate = g3.Layer3G3CertificateCandidate(
        candidate_id="g3-certificate-candidate:rederive",
        certificate_kind="proof_composability",
        candidate_ref="g3-candidate://rederive",
        source="ir.analytics.proof_composability.persist_proof_composability_certificate",
        artifact_ref=ref.model_dump(mode="json"),
    )

    report = g3.build_g3_certificate_resolution_report(candidates=(candidate,), store=store)

    assert report.status == "blocked"
    assert report.blocking_certificate_count == 1
    assert report.records[0].typed_payload_kind == "ProofComposabilityCertificate"
    assert report.records[0].evidence_role == "blocking"
    assert "layer3_g3_proof_composability_bypass" in report.issue_codes


def test_layer3_g3_task2_stale_artifact_index_cannot_claim_proof_ceiling(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    candidates = g3.produce_g3_deterministic_first_case_certificate(
        _task2_request(g3, "stale-index"),
        store=store,
    )
    stale_index = g3.build_g3_ir_artifact_store_index(
        store=store,
        selected_candidates=candidates,
        stale=True,
    )

    report = g3.build_g3_certificate_resolution_report(
        candidates=candidates,
        artifact_index=stale_index,
        store=store,
    )

    assert report.status == "fail"
    assert "layer3_g3_stale_artifact_index_claimed_as_proof_ceiling" in report.issue_codes
    assert report.resolved_certificate_count == 0


def test_layer3_g3_task2_tenant_manifest_denial_blocks_resolution() -> None:
    g3 = _g3()
    candidate = g3.Layer3G3CertificateCandidate(
        candidate_id="g3-certificate-candidate:tenant-denied",
        certificate_kind="proof_bundle",
        candidate_ref="g3-candidate://tenant-denied",
        source="tenant_scoped_store",
        tenant_scope_status="denied",
        selected_ref_only=True,
    )
    index = g3.build_g3_ir_artifact_store_index(selected_candidates=(candidate,))

    report = g3.build_g3_certificate_resolution_report(
        candidates=(candidate,),
        artifact_index=index,
    )

    assert report.status == "blocked"
    assert "layer3_g3_tenant_scoped_manifest_denied" in report.issue_codes
    assert report.no_hit_count == 0


def test_layer3_g3_task2_bounds_overclaim_without_dual_certificate_blocks(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.analytics.partial_identification import (
        BoundsBundle,
        persist_bounds_bundle,
    )

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_bounds_bundle(
        store,
        BoundsBundle(
            lower_bound=0.1,
            upper_bound=0.7,
            sharpness_status="sharp",
            metadata={"claims_sharp_or_certified_bounds": True},
        ),
    )
    candidate = g3.Layer3G3CertificateCandidate(
        candidate_id="g3-certificate-candidate:bounds-overclaim",
        certificate_kind="bounds_bundle",
        candidate_ref="g3-candidate://bounds-overclaim",
        source="ir.analytics.partial_identification.persist_bounds_bundle",
        artifact_ref=ref.model_dump(mode="json"),
        metadata={"claims_sharp_or_certified_bounds": True},
    )

    report = g3.build_g3_certificate_resolution_report(candidates=(candidate,), store=store)

    assert report.status == "blocked"
    assert report.limiting_certificate_count == 1
    assert "layer3_g3_bounds_dual_certificate_missing" in report.issue_codes


def test_layer3_g3_task2_scientist_warning_without_ref_cannot_resolve() -> None:
    g3 = _g3()
    candidate = g3.Layer3G3CertificateCandidate(
        candidate_id="g3-certificate-candidate:scientist-warning",
        certificate_kind="proof_bundle",
        candidate_ref="scientist-level2-warning://caught-warning",
        source="scientist_level2_warning",
        selected_ref_only=False,
        metadata={"warning": "artifact store missing"},
    )

    report = g3.build_g3_certificate_resolution_report(candidates=(candidate,))

    assert report.status == "fail"
    assert report.resolved_certificate_count == 0
    assert "layer3_g3_unresolved_certificate_binding" in report.issue_codes


def test_layer3_g3_task2_broad_loader_exception_cannot_pass_resolution() -> None:
    g3 = _g3()
    candidate = g3.Layer3G3CertificateCandidate(
        candidate_id="g3-certificate-candidate:missing-store",
        certificate_kind="proof_bundle",
        candidate_ref="g3-candidate://missing-store",
        source="ir.analytics.causal.persist_proof_bundle",
        artifact_ref={
            "artifact_id": "sha256:" + "0" * 64,
            "kind": "ir.proof_bundle",
            "media_type": "application/json",
        },
    )

    report = g3.build_g3_certificate_resolution_report(candidates=(candidate,))

    assert report.status == "fail"
    assert report.resolved_certificate_count == 0
    assert "layer3_g3_certificate_resolution_missing" in report.issue_codes


def test_layer3_g3_task3_consumes_g2_method_requirements_for_claim_bound_bridge() -> None:
    g3 = _g3()
    request = _task3_request(g3, "g2-method")

    bindings = g3.build_g3_method_requirement_bindings(request=request, repo_root=REPO_ROOT)

    assert bindings
    assert bindings[0].status == "pass"
    assert bindings[0].source_route == "g2_method_requirement_bindings"
    assert bindings[0].claim_id == request.claim_id
    assert bindings[0].method_requirement_refs
    assert bindings[0].method_requirement_specs[0]["claim_id"] == request.claim_id
    assert bindings[0].selected_method_refs
    assert "claim_authority" in bindings[0].may_not_use_for


def test_layer3_g3_task3_builds_s11_proof_record_and_existing_ir_bridge(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task3_request(g3, "positive-bridge")
    certificate_report = _task3_positive_certificate_report(g3, request, store)
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_task3_point_requirement(request),),
        selected_method_refs=("ir.method.g3.deterministic_first_case",),
    )

    proof_bindings = g3.build_g3_proof_carrying_analytics_bindings(
        request=request,
        certificate_resolution_report=certificate_report,
        method_requirement_bindings=method_bindings,
    )
    bridge_binding = g3.build_g3_ir_analytics_bridge_bindings(
        proof_carrying_analytics_records=proof_bindings,
        method_requirement_bindings=method_bindings,
    )

    assert len(proof_bindings) == 1
    assert proof_bindings[0].status == "pass"
    assert proof_bindings[0].s11_record["claim_id"] == request.claim_id
    assert proof_bindings[0].s11_record["ir_certificate_refs"]
    assert proof_bindings[0].s11_record["method_requirement_refs"] == [
        "g3-method-req:positive-bridge"
    ]
    assert proof_bindings[0].s11_record["proof_status"] == "identified"
    assert proof_bindings[0].s11_record["proof_composability_status"] == "reusable"
    assert "claim_authority" in proof_bindings[0].s11_record["may_not_use_for"]
    assert bridge_binding.status == "pass"
    assert bridge_binding.bridge_payload["bridge_kind"] == "runtime.ir_analytics_claim_bridge"
    assert bridge_binding.bridge_payload["claim_bindings"][0]["claim_id"] == request.claim_id
    assert bridge_binding.bridge_payload["summary"]["method_requirement_binding_count"] == 1


def test_layer3_g3_task3_search_hit_without_resolved_certificate_cannot_build_proof_record() -> (
    None
):
    g3 = _g3()
    request = _task3_request(g3, "search-hit")
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_task3_point_requirement(request),),
    )

    proof_bindings = g3.build_g3_proof_carrying_analytics_bindings(
        request=request,
        certificate_resolution_report=g3.Layer3G3CertificateResolutionReport(
            status="fail",
            selected_candidate_count=1,
            issue_codes=("layer3_g3_search_hit_laundered_as_certificate",),
        ),
        method_requirement_bindings=method_bindings,
    )

    assert proof_bindings
    assert proof_bindings[0].status == "fail"
    assert "layer3_g3_search_hit_laundered_as_certificate" in proof_bindings[0].issue_codes
    assert "layer3_g3_proof_carrying_record_missing" in proof_bindings[0].issue_codes


def test_layer3_g3_task3_s11_fixture_string_without_resolver_payload_cannot_build_proof_record() -> (
    None
):
    g3 = _g3()
    request = _task3_request(g3, "fixture-string")
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_task3_point_requirement(request),),
    )

    proof_bindings = g3.build_g3_proof_carrying_analytics_bindings(
        request=request,
        certificate_resolution_report=g3.Layer3G3CertificateResolutionReport(
            status="fail",
            records=(
                g3.Layer3G3CertificateResolutionRecord(
                    record_id="g3-resolution:fixture-string",
                    candidate_id="g3-candidate:fixture-string",
                    status="fail",
                    certificate_kind="proof_bundle",
                    source="fixture",
                    artifact_id="certificate://layer2/s11/fixture",
                    issue_codes=("layer3_g3_fixture_certificate_laundered",),
                ),
            ),
            issue_codes=("layer3_g3_fixture_certificate_laundered",),
        ),
        method_requirement_bindings=method_bindings,
    )

    assert proof_bindings[0].status == "fail"
    assert "layer3_g3_fixture_certificate_laundered" in proof_bindings[0].issue_codes


def test_layer3_g3_task3_point_requirement_without_certificate_fails_bridge() -> None:
    g3 = _g3()
    request = _task3_request(g3, "point-missing-certificate")
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_task3_point_requirement(request),),
        selected_method_refs=("ir.method.g3.point",),
    )

    bridge_binding = g3.build_g3_ir_analytics_bridge_bindings(
        claim_bindings=(
            {
                "claim_id": request.claim_id,
                "analytics_ref": "ir.analytics.g3.point",
                "method_output_refs": ["ir.method.g3.point"],
                "proof_status": "identified",
                "proof_composability_status": "reusable",
            },
        ),
        method_requirement_bindings=method_bindings,
    )

    assert bridge_binding.status == "fail"
    assert "layer3_g3_method_requirement_bypass" in bridge_binding.issue_codes
    assert any(
        issue["code"] == "ir_analytics_method_requirement_certificate_missing"
        for issue in bridge_binding.bridge_payload["issues"]
    )


def test_layer3_g3_task3_bounds_requirement_without_uncertainty_refs_fails_bridge() -> None:
    g3 = _g3()
    request = _task3_request(g3, "bounds-missing-uncertainty")
    requirement = _task3_bounds_requirement(request)
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(requirement,),
        selected_method_refs=("ir.method.g3.bounds",),
    )

    bridge_binding = g3.build_g3_ir_analytics_bridge_bindings(
        claim_bindings=(
            {
                "claim_id": request.claim_id,
                "analytics_ref": "ir.analytics.g3.bounds",
                "method_output_refs": ["ir.method.g3.bounds"],
                "certificate_refs": ["ir.certificate.g3.bounds"],
                "proof_status": "bounded",
                "proof_composability_status": "reusable",
            },
        ),
        method_requirement_bindings=method_bindings,
    )

    assert bridge_binding.status == "fail"
    assert "layer3_g3_uncertainty_or_bounds_ref_missing" in bridge_binding.issue_codes
    assert any(
        issue["code"] == "ir_analytics_method_requirement_uncertainty_missing"
        for issue in bridge_binding.bridge_payload["issues"]
    )


def test_layer3_g3_task3_negative_certificate_requirement_not_satisfied_by_positive_output() -> (
    None
):
    g3 = _g3()
    request = _task3_request(g3, "negative-requirement")
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_task3_negative_requirement(request),),
        selected_method_refs=("ir.method.g3.positive-output",),
    )

    bridge_binding = g3.build_g3_ir_analytics_bridge_bindings(
        claim_bindings=(
            {
                "claim_id": request.claim_id,
                "analytics_ref": "ir.analytics.g3.positive-output",
                "method_output_refs": ["ir.method.g3.positive-output"],
                "certificate_refs": ["ir.certificate.g3.positive-output"],
                "proof_status": "identified",
                "proof_composability_status": "reusable",
            },
        ),
        method_requirement_bindings=method_bindings,
    )

    assert bridge_binding.status == "fail"
    assert "layer3_g3_method_requirement_bypass" in bridge_binding.issue_codes
    assert any(
        issue["code"] == "ir_analytics_method_requirement_negative_certificate_missing"
        for issue in bridge_binding.bridge_payload["issues"]
    )


def test_layer3_g3_task3_bridge_row_without_claim_id_fails() -> None:
    g3 = _g3()

    bridge_binding = g3.build_g3_ir_analytics_bridge_bindings(
        claim_bindings=(
            {
                "analytics_ref": "ir.analytics.g3.missing-claim",
                "method_output_refs": ["ir.method.g3.missing-claim"],
                "certificate_refs": ["ir.certificate.g3.missing-claim"],
                "proof_status": "identified",
            },
        ),
    )

    assert bridge_binding.status == "fail"
    assert "layer3_g3_ir_analytics_bridge_missing" in bridge_binding.issue_codes
    assert any(
        issue["code"] == "runtime_claim_registry_ir_analytics_claim_id_missing"
        for issue in bridge_binding.bridge_payload["issues"]
    )


def test_layer3_g3_task3_bridge_row_with_blocking_proof_status_fails_claim_readiness() -> None:
    g3 = _g3()
    request = _task3_request(g3, "blocking-proof")

    bridge_binding = g3.build_g3_ir_analytics_bridge_bindings(
        claim_bindings=(
            {
                "claim_id": request.claim_id,
                "analytics_ref": "ir.analytics.g3.blocked",
                "method_output_refs": ["ir.method.g3.blocked"],
                "negative_certificate_refs": ["ir.negative_certificate.g3.blocked"],
                "proof_status": "not_identified",
                "proof_composability_status": "rederive",
                "proof_composability_refs": ["ir.proof_composability.g3.rederive"],
            },
        ),
    )

    assert bridge_binding.status == "fail"
    assert "layer3_g3_ir_analytics_bridge_missing" in bridge_binding.issue_codes
    assert any(
        issue["code"] == "runtime_claim_registry_ir_analytics_blocked"
        for issue in bridge_binding.bridge_payload["issues"]
    )


def test_layer3_g3_task4_builds_s11_prerequisites_calibration_and_posture(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task3_request(g3, "s11-positive")
    proof_bindings = _task4_g3_proof_bindings(g3, request, store)

    prereqs = g3.build_g3_s11_prerequisite_bindings(
        request=request,
        repo_root=REPO_ROOT,
        s6_floor_status_refs=_task4_s6_floor_refs(),
        s6_axis_rows=_task4_s6_axis_rows(),
        s6_bridge_consumer_rows=_task4_s6_bridge_rows(),
        s6_constraint_store_update_refs=("constraint://s6/g3/measurability",),
        s6_c3_authority_dimension_refs=("pdc://layer2/s6/g3/c3/measurability",),
        post_intervention_dgp_update_ref="pdc://layer2/s6/g3/post-intervention-dgp",
        system_dynamics_handoff_required=True,
    )
    calibrations = g3.build_g3_s11_calibration_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        proof_carrying_analytics_records=proof_bindings,
    )
    postures = g3.build_g3_s11_predictive_posture_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        s11_calibration_bindings=calibrations,
        proof_carrying_analytics_records=proof_bindings,
    )

    assert prereqs[0].status == "pass"
    assert prereqs[0].s10_forecast_support_ref.startswith("pdc://layer3/g2/")
    assert prereqs[0].s10_forecast_tier == "observable_calibrated"
    assert prereqs[0].s6_floor_status_refs == _task4_s6_floor_refs()
    assert calibrations[0].status == "pass"
    assert calibrations[0].calibration_record["calibration_status"] == "pass"
    assert calibrations[0].axis_upgrade_record["proof_carrying_analytics_ref"] == (
        proof_bindings[0].proof_ref
    )
    assert calibrations[0].authority_envelope["envelope_status"] == "pass"
    assert postures[0].status == "pass"
    assert postures[0].posture_payload["proof_carrying_analytics_ref"] == (
        proof_bindings[0].proof_ref
    )
    assert postures[0].posture_payload["s10_forecast_tier"] == "observable_calibrated"
    assert postures[0].posture_payload["effective_predictive_posture"] == "predictive"
    assert "production_authority" in postures[0].posture_payload["may_not_use_for"]
    assert "claim_authority" in postures[0].posture_payload["may_not_use_for"]


def test_layer3_g3_task4_missing_s6_floor_blocks_s11_posture(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task3_request(g3, "missing-s6")
    proof_bindings = _task4_g3_proof_bindings(g3, request, store)

    prereqs = g3.build_g3_s11_prerequisite_bindings(
        request=request,
        repo_root=REPO_ROOT,
        s6_floor_status_refs=(),
        s6_axis_rows=(),
        s6_bridge_consumer_rows=(),
    )
    postures = g3.build_g3_s11_predictive_posture_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        s11_calibration_bindings=(),
        proof_carrying_analytics_records=proof_bindings,
    )

    assert prereqs[0].status == "blocked"
    assert "layer3_g3_s11_prerequisite_missing" in prereqs[0].issue_codes
    assert postures[0].status == "blocked"
    assert "layer3_g3_s11_posture_without_s6_s10" in postures[0].issue_codes


def test_layer3_g3_task4_missing_s10_forecast_support_blocks_s11_posture(
    tmp_path: Path,
) -> None:
    g3 = _g3()
    request = _task3_request(g3, "missing-s10")

    prereqs = g3.build_g3_s11_prerequisite_bindings(
        request=request,
        repo_root=tmp_path,
        s6_floor_status_refs=_task4_s6_floor_refs(),
        s6_axis_rows=_task4_s6_axis_rows(),
        s6_bridge_consumer_rows=_task4_s6_bridge_rows(),
    )

    assert prereqs[0].status == "blocked"
    assert "layer3_g3_s11_prerequisite_missing" in prereqs[0].issue_codes
    assert prereqs[0].s10_forecast_support_ref is None


def test_layer3_g3_task4_stale_or_out_of_scope_calibration_cannot_pass(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task3_request(g3, "stale-calibration")
    proof_bindings = _task4_g3_proof_bindings(g3, request, store)
    prereqs = _task4_prereqs(g3, request)

    calibrations = g3.build_g3_s11_calibration_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        proof_carrying_analytics_records=proof_bindings,
        calibration_status="stale",
        floor_passed=True,
    )

    assert calibrations[0].status == "fail"
    assert "layer3_g3_s11_calibration_invalid" in calibrations[0].issue_codes
    assert calibrations[0].calibration_record == {}


def test_layer3_g3_task4_predictive_upgrade_without_proof_ref_blocks() -> None:
    g3 = _g3()
    request = _task3_request(g3, "missing-proof-ref")
    prereqs = _task4_prereqs(g3, request)

    calibrations = g3.build_g3_s11_calibration_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        proof_carrying_analytics_records=(),
    )

    assert calibrations[0].status == "blocked"
    assert "layer3_g3_s11_predictive_upgrade_missing_proof" in calibrations[0].issue_codes
    assert "layer3_g3_proof_carrying_record_missing" in calibrations[0].issue_codes


def test_layer3_g3_task4_s11_authority_boundary_leak_blocks_binding(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task3_request(g3, "authority-leak")
    proof_bindings = _task4_g3_proof_bindings(g3, request, store)
    prereqs = _task4_prereqs(g3, request)

    calibrations = g3.build_g3_s11_calibration_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        proof_carrying_analytics_records=proof_bindings,
        calibration_authority_boundary={
            "authoritative_for": ["production_authority", "claim_authority"],
            "may_not_use_for": [
                "production_authority",
                "production_recommendation",
                "production_claim_authority",
                "claim_authority",
                "rich_simulation_authority",
                "mandate_legitimacy_predictive_upgrade",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer2.s11.predictive_knowledge.v1"],
        },
    )

    assert calibrations[0].status == "fail"
    assert "layer3_g3_production_authority_leak" in calibrations[0].issue_codes
    assert "layer3_g3_claim_authority_leak" in calibrations[0].issue_codes


def test_layer3_g3_task4_fail_closed_upgrade_limits_posture_without_overriding_s10(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    g3 = _g3()
    store = FileSystemCAS(tmp_path / "cas")
    request = _task3_request(g3, "fail-closed")
    proof_bindings = _task4_g3_proof_bindings(g3, request, store)
    prereqs = _task4_prereqs(g3, request)
    calibrations = g3.build_g3_s11_calibration_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        proof_carrying_analytics_records=proof_bindings,
        effective_maturity="fail_closed",
        relaxation_decision="reverted_fail_closed",
        forecast_quality_disposition="downgraded_by_s11_calibration",
    )
    postures = g3.build_g3_s11_predictive_posture_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        s11_calibration_bindings=calibrations,
        proof_carrying_analytics_records=proof_bindings,
    )

    assert calibrations[0].status == "pass"
    assert postures[0].status == "pass"
    assert postures[0].posture_payload["effective_predictive_posture"] == (
        "limited_by_weakest_boundary"
    )
    assert postures[0].posture_payload["forecast_quality_disposition"] == (
        "downgraded_by_s11_calibration"
    )
    assert postures[0].posture_payload["s10_forecast_tier"] == "observable_calibrated"


def test_layer3_g3_task6_builds_projection_and_audit_surfaces_without_raw_payloads() -> None:
    g3 = _g3()
    bundle = g3.build_layer3_g3_bundle(REPO_ROOT)
    payload = _dump(bundle)

    projection = payload["public_export_projection_refs"]
    audit = payload["proof_carrying_audit_surface"]

    assert projection["status"] == "pass"
    assert projection["authority_role"] == "projection_only"
    assert projection["certificate_resolution_report_ref"].endswith(
        "layer3_g3_certificate_resolution_report.json"
    )
    assert projection["resolved_certificate_count"] >= 1
    assert "claim_authority" in projection["may_not_use_for"]
    assert projection["public_payload_redaction_status"] == "pass"
    assert projection["raw_proof_payload_exported"] is False
    assert projection["raw_cas_manifest_exported"] is False
    assert projection["raw_query_ledger_exported"] is False

    assert audit["status"] == "pass"
    assert set(audit["surface_audiences"]) == {"PUBLIC", "REVIEWER", "EXPERT", "MACHINE"}
    assert audit["public_fields"] == [
        "status",
        "proof_posture",
        "limitation_refs",
        "may_not_use_for",
    ]
    assert audit["expert_fields"]
    assert audit["machine_fields"]


def test_layer3_g3_task6_adapter_registry_loads_and_summary_only_toml_fails(
    tmp_path: Path,
) -> None:
    g3 = _g3()

    status = g3.build_g3_adapter_contract_registry_status(repo_root=REPO_ROOT)

    assert status.status == "pass"
    assert status.adapter_contract_path_count >= 6
    assert "layer3_g3_certificate_resolution_to_proof_record" in status.adapter_path_ids
    assert status.adapter_admission_records

    summary_only = tmp_path / "summary-only.toml"
    summary_only.write_text(
        "\n".join(
            [
                'schema_version = "policyos.policy_design_case.layer3_g3_analytics_search.v1"',
                "",
                "[adapter_contract_registry]",
                'adapter_contract_refs = ["layer3_g3_certificate_resolution_to_proof_record"]',
            ]
        ),
        encoding="utf-8",
    )
    failing = g3.build_g3_adapter_contract_registry_status(path=summary_only)

    assert failing.status == "fail"
    assert "layer3_g3_adapter_registry_summary_only" in failing.issue_codes


def test_layer3_g3_task6_generated_artifact_registration_status_reads_real_surfaces() -> None:
    g3 = _g3()

    status = g3.build_g3_generated_artifact_registration_status(REPO_ROOT)
    payload = _dump(status)

    assert payload["status"] == "pass"
    assert payload["generated_artifact_family_id"] == (
        "policy-design-case-layer3-g3-analytics-search-artifacts"
    )
    assert (
        "architecture/policy_design_case/layer3_g3_readiness_manifest.json"
        in (payload["registered_artifact_paths"])
    )
    assert (
        "architecture/policy_design_case/layer3_g3_search_recall_freshness.json"
        in (payload["registered_artifact_paths"])
    )
    assert "docs/reference/generated-artifacts.md" in payload["registered_doc_refs"]
    assert payload["missing_registration_refs"] == []
    assert payload["issue_codes"] == []


def test_layer3_g3_task7_conformance_report_covers_replay_performance_and_adapter_gates() -> None:
    g3 = _g3()
    bundle = g3.build_layer3_g3_bundle(REPO_ROOT)
    conformance = bundle.conformance_report

    assert conformance.status == "pass"
    assert conformance.replay_check_status == "pass"
    assert conformance.performance_check_status == "pass"
    assert conformance.module_load_check_status == "pass"
    assert conformance.adapter_admission_check_status == "pass"
    assert conformance.artifact_store_check_status == "pass"
    assert conformance.authority_boundary_check_status == "pass"
    assert conformance.replayed_certificate_count >= 1
    assert conformance.checked_adapter_path_count >= 6
    assert conformance.heavy_module_import_refs == ()
    assert set(g3.ALL_ISSUE_CODES) <= set(conformance.issue_code_dictionary)


def test_layer3_g3_task7_conformance_fails_replay_adapter_and_cas_negatives() -> None:
    g3 = _g3()
    bundle = g3.build_layer3_g3_bundle(REPO_ROOT)
    proof_record = bundle.proof_carrying_analytics_records[0]
    broken_proof = proof_record.model_copy(
        update={
            "certificate_resolution_record_refs": (),
            "method_requirement_refs": (),
            "s11_record": {
                key: value
                for key, value in proof_record.s11_record.items()
                if key != "authority_boundary"
            },
        }
    )
    broken = bundle.model_copy(
        update={
            "ir_analytics_search_ledgers": (
                bundle.ir_analytics_search_ledgers[0].model_copy(
                    update={"query_trace_refs": (), "cutoff_limit": 0}
                ),
            ),
            "ir_analytics_query_traces": (),
            "search_engineering_quality": bundle.search_engineering_quality.model_copy(
                update={
                    "status": "fail",
                    "per_request_module_walk_count": 1,
                    "per_request_json_scan_count": 1,
                    "unbounded_query_count": 1,
                    "issue_codes": (
                        "layer3_g3_ir_catalog_search_not_indexed",
                        "layer3_g3_search_ledger_missing",
                    ),
                }
            ),
            "ir_artifact_store_index": bundle.ir_artifact_store_index.model_copy(
                update={
                    "status": "not_configured",
                    "store_backend": "not_configured",
                    "full_listing_used": True,
                    "stale": True,
                    "tenant_scope_status": "denied",
                    "issue_codes": (
                        "layer3_g3_full_cas_listing_in_request_path",
                        "layer3_g3_tenant_scoped_manifest_denied",
                        "layer3_g3_stale_artifact_index_claimed_as_proof_ceiling",
                    ),
                }
            ),
            "adapter_contract_registry": bundle.adapter_contract_registry.model_copy(
                update={
                    "status": "fail",
                    "adapter_path_ids": (
                        *bundle.adapter_contract_registry.adapter_path_ids,
                        "layer3_g3_unknown_adapter_path",
                    ),
                    "issue_codes": (
                        "layer3_g3_adapter_unknown_path",
                        "layer3_g3_adapter_semantic_loss",
                    ),
                }
            ),
            "adapter_admission_registry": bundle.adapter_admission_registry.model_copy(
                update={
                    "status": "fail",
                    "records": (
                        {
                            "adapter_id": "layer3_g3_unknown_adapter_path",
                            "adapter_contract_path_refs": ("layer3_g3_unknown_adapter_path",),
                            "conformance_status": "fail",
                            "semantic_loss_blockers": ["lost_authority_boundary"],
                            "source_touchpoint_refs": [
                                "touchpoint://runtime-quality/unregistered-engine"
                            ],
                        },
                    ),
                    "issue_codes": (
                        "layer3_g3_adapter_unknown_path",
                        "layer3_g3_adapter_semantic_loss",
                        "layer3_g3_adapter_touchpoint_unregistered",
                    ),
                }
            ),
            "proof_carrying_analytics_records": (broken_proof,),
        }
    )

    report = g3.validate_g3_adapter_conformance(REPO_ROOT, broken)

    assert report.status == "fail"
    assert set(report.issue_codes) >= {
        "layer3_g3_replay_record_missing",
        "layer3_g3_query_trace_missing",
        "layer3_g3_search_ledger_missing",
        "layer3_g3_ir_catalog_search_not_indexed",
        "layer3_g3_full_cas_listing_in_request_path",
        "layer3_g3_tenant_scoped_manifest_denied",
        "layer3_g3_stale_artifact_index_claimed_as_proof_ceiling",
        "layer3_g3_store_configuration_missing",
        "layer3_g3_adapter_unknown_path",
        "layer3_g3_adapter_semantic_loss",
        "layer3_g3_adapter_touchpoint_unregistered",
        "layer3_g3_method_requirement_missing",
        "layer3_g3_proof_carrying_record_missing",
        "layer3_g3_claim_authority_leak",
    }


def test_layer3_g3_task7_unknown_adapter_path_in_registry_fails_status(
    tmp_path: Path,
) -> None:
    g3 = _g3()
    registry_text = (
        REPO_ROOT / "architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml"
    ).read_text(encoding="utf-8")
    registry_path = tmp_path / "unknown-adapter.toml"
    registry_path.write_text(
        registry_text.replace(
            "layer3_g3_bridge_to_w12d_consumer_gate",
            "layer3_g3_unregistered_bridge_to_w12d_consumer_gate",
            1,
        ),
        encoding="utf-8",
    )

    status = g3.build_g3_adapter_contract_registry_status(path=registry_path)

    assert status.status == "fail"
    assert "layer3_g3_adapter_unknown_path" in status.issue_codes


def _task2_request(g3: Any, suffix: str) -> Any:
    return g3.Layer3G3AnalyticsRequest(
        request_id=f"g3-request:task2:{suffix}",
        claim_id=f"claim:g3:task2:{suffix}",
        case_id=f"case:g3:task2:{suffix}",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        method_requirement_refs=("method-requirement://g3/task2",),
        certificate_kinds=("proof_bundle",),
    )


def _task3_request(g3: Any, suffix: str) -> Any:
    return g3.Layer3G3AnalyticsRequest(
        request_id=f"g3-request:task3:{suffix}",
        claim_id=f"claim:g3:task3:{suffix}",
        case_id=f"case:g3:task3:{suffix}",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        comparison_ref=f"comparison://g3/task3/{suffix}",
        baseline_ref=f"baseline://g3/task3/{suffix}",
        alternative_refs=(f"alternative://g3/task3/{suffix}",),
        concept_refs=(f"concept://g3/task3/{suffix}",),
        semantic_spine_refs=(f"semantic-spine://g3/task3/{suffix}",),
        method_requirement_refs=(f"g3-method-req:{suffix}",),
        certificate_kinds=("proof_bundle",),
    )


def _task3_positive_certificate_report(g3: Any, request: Any, store: Any) -> Any:
    candidates = g3.produce_g3_deterministic_first_case_certificate(request, store=store)
    artifact_index = g3.build_g3_ir_artifact_store_index(
        store=store,
        selected_candidates=candidates,
    )
    return g3.build_g3_certificate_resolution_report(
        candidates=candidates,
        artifact_index=artifact_index,
        store=store,
    )


def _task3_point_requirement(request: Any) -> dict[str, object]:
    return {
        "requirement_id": request.method_requirement_refs[0],
        "run_id": request.case_id,
        "claim_id": request.claim_id,
        "identification_class": "point",
        "method_expectations": ["causal_identification"],
        "required_method_families": ["causal_identification"],
        "requires_uncertainty_envelope": False,
        "requires_limitation_refs": False,
        "facet_refs": list(request.concept_refs),
        "obligation_refs": [f"obligation://{request.claim_id}"],
        "baseline_refs": [request.baseline_ref],
        "alternative_refs": list(request.alternative_refs),
    }


def _task3_bounds_requirement(request: Any) -> dict[str, object]:
    payload = _task3_point_requirement(request)
    payload.update(
        {
            "identification_class": "bounds",
            "uncertainty_class": "bounds",
            "requires_uncertainty_envelope": True,
            "requires_limitation_refs": False,
            "method_expectations": ["partial_identification"],
            "required_method_families": ["partial_identification"],
        }
    )
    return payload


def _task3_negative_requirement(request: Any) -> dict[str, object]:
    payload = _task3_point_requirement(request)
    payload.update(
        {
            "identification_class": "negative_certificate",
            "method_expectations": ["negative_certificate"],
            "required_method_families": ["negative_certificate"],
        }
    )
    return payload


def _task4_g3_proof_bindings(g3: Any, request: Any, store: Any) -> tuple[Any, ...]:
    certificate_report = _task3_positive_certificate_report(g3, request, store)
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_task3_point_requirement(request),),
        selected_method_refs=("ir.method.g3.deterministic_first_case",),
    )
    return g3.build_g3_proof_carrying_analytics_bindings(
        request=request,
        certificate_resolution_report=certificate_report,
        method_requirement_bindings=method_bindings,
    )


def _task4_prereqs(g3: Any, request: Any) -> tuple[Any, ...]:
    return g3.build_g3_s11_prerequisite_bindings(
        request=request,
        repo_root=REPO_ROOT,
        s6_floor_status_refs=_task4_s6_floor_refs(),
        s6_axis_rows=_task4_s6_axis_rows(),
        s6_bridge_consumer_rows=_task4_s6_bridge_rows(),
        s6_constraint_store_update_refs=("constraint://s6/g3/measurability",),
        s6_c3_authority_dimension_refs=("pdc://layer2/s6/g3/c3/measurability",),
        post_intervention_dgp_update_ref="pdc://layer2/s6/g3/post-intervention-dgp",
        system_dynamics_handoff_required=True,
    )


def _task4_s6_floor_refs() -> tuple[str, ...]:
    return (
        "pdc://layer2/s6/g3/measurability",
        "pdc://layer2/s6/g3/strategic-response",
    )


def _task4_s6_axis_rows() -> tuple[dict[str, object], ...]:
    return (
        {
            "axis": "measurability",
            "cell_ref": "SYSTEM.measurability",
            "record_ref": "pdc://layer2/s6/g3/measurability",
            "disposition": "limit",
        },
        {
            "axis": "strategic_response",
            "cell_ref": "OTHER_AGENTS.strategic_response",
            "record_ref": "pdc://layer2/s6/g3/strategic-response",
            "disposition": "block",
        },
    )


def _task4_s6_bridge_rows() -> tuple[dict[str, object], ...]:
    return (
        {
            "cell_ref": "SYSTEM.measurability",
            "consumer_ref": "KNOWLEDGE.epistemic_regime",
            "producer_ref": "pdc://layer2/s6/g3/measurability",
            "disposition": "limit",
        },
    )
