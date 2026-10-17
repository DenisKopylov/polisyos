from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from importlib import import_module
from pathlib import Path
from typing import Any

import duckdb
import pytest
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/gl"
GL_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gl_legal_mandate_search.v1"
GL_RULE_VERSION = "policyos.layer3.gl.legal_mandate_search.v1"
GL_SURFACE_ID = "layer3_gl_legal_mandate_audit_surface"
GL_PUBLIC_PROJECTION_SURFACE_ID = "layer3_gl_public_export_projection_refs"
CANONICAL_KG_PATH = (
    REPO_ROOT / "production_data/lex/lex-amendment-only-optimized-20260501-v3/"
    "finalize/lex_knowledge_graph.duckdb"
)

EXPECTED_DTOS = {
    "Layer3GLValidationIssue",
    "Layer3GLValidationReport",
    "Layer3GLLegalMandateRequest",
    "Layer3GLL3LegalKgCoverageReport",
    "Layer3GLLegalSearchLedger",
    "Layer3GLLegalQueryTrace",
    "Layer3GLSearchRecallFreshnessReport",
    "Layer3GLL5CalibrationBinding",
    "Layer3GLLegalRequirementBinding",
    "Layer3GLAuthorityFacetBinding",
    "Layer3GLNormCandidateBinding",
    "Layer3GLThresholdAuthorityRecord",
    "Layer3GLMandateAuthorityRecord",
    "Layer3GLTemporalCompetenceRecord",
    "Layer3GLAmendmentLineageRecord",
    "Layer3GLReferenceResolutionRecord",
    "Layer3GLLegalAuthorityReportBinding",
    "Layer3GLLexInterventionMapBinding",
    "Layer3GLClaimRegistryConsumerGate",
    "Layer3GLSemanticBindingConsumerGate",
    "Layer3GLArgumentGraphReadinessConsumerGate",
    "Layer3GLS6MandateConsumerGate",
    "Layer3GLS7DelegationConsumerGate",
    "Layer3GLS8ValueChoiceConsumerGate",
    "Layer3GLPdcCompilerConsumerGate",
    "Layer3GLDesignConstraintConsumerGate",
    "Layer3GLG4PromotionGateConsumerGate",
    "Layer3GLPromotionGateHandoff",
    "Layer3GLLegalMandateAuditSurface",
    "Layer3GLPublicExportProjectionRefSurface",
    "Layer3GLAdapterAdmissionBundle",
    "Layer3GLConformanceReport",
    "Layer3GLReadinessManifest",
    "Layer3GLBundle",
}

EXPECTED_BUILDERS_AND_VALIDATORS = {
    "build_layer3_gl_bundle",
    "validate_layer3_gl_bundle",
    "build_gl_l3_legal_kg_index_coverage",
    "build_gl_legal_search_ledgers",
    "build_gl_search_recall_freshness",
    "build_gl_l5_calibration_bindings",
    "build_gl_legal_requirement_bindings",
    "build_gl_authority_facet_bindings",
    "build_gl_norm_candidate_bindings",
    "build_gl_legal_authority_report_binding",
    "build_gl_threshold_authority_records",
    "build_gl_mandate_authority_records",
    "build_gl_temporal_competence_records",
    "build_gl_amendment_lineage_records",
    "build_gl_reference_resolution_records",
    "build_gl_lex_intervention_map_bindings",
    "build_gl_claim_registry_consumer_gate",
    "build_gl_semantic_binding_consumer_gate",
    "build_gl_argument_graph_readiness_consumer_gate",
    "build_gl_s6_mandate_consumer_gate",
    "build_gl_s7_delegation_consumer_gate",
    "build_gl_s8_value_choice_consumer_gate",
    "build_gl_pdc_compiler_consumer_gate",
    "build_gl_design_constraint_consumer_gate",
    "build_gl_g4_promotion_gate_consumer_gate",
    "build_gl_promotion_gate_handoff",
    "build_gl_audit_surface",
    "build_gl_public_export_projection_refs",
}

REQUIRED_ISSUE_CODES = {
    "layer3_gl_g0_dependency_not_ready",
    "layer3_gl_l3_legal_kg_missing",
    "layer3_gl_l3_legal_kg_route_not_bound",
    "layer3_gl_l3_legal_kg_index_coverage_failed",
    "layer3_gl_noncanonical_legal_route_used_for_closure",
    "layer3_gl_search_ledger_missing",
    "layer3_gl_query_trace_missing",
    "layer3_gl_search_recall_seed_miss_blocks_domain_ceiling",
    "layer3_gl_stale_legal_index_blocks_domain_ceiling",
    "layer3_gl_false_abstention_recall_unmeasured",
    "layer3_gl_text_search_used_as_authority",
    "layer3_gl_read_api_text_search_used_for_closure",
    "layer3_gl_applicability_report_internal_lex_kg_fallback_used_for_closure",
    "layer3_gl_runtime_candidate_norm_snapshot_used_for_closure",
    "layer3_gl_internal_requirement_compile_used_for_closure",
    "layer3_gl_legal_requirement_producer_artifact_ref_missing",
    "layer3_gl_legal_authority_report_missing_gl_producer_artifact_ref",
    "layer3_gl_retrieved_legal_text_used_as_authority",
    "layer3_gl_llm_legal_summary_used_as_authority",
    "layer3_gl_legal_requirement_binding_missing",
    "layer3_gl_legal_requirement_missing_authority_types",
    "layer3_gl_compiler_default_authority_type_unmarked",
    "layer3_gl_compiler_default_authority_type_laundered",
    "layer3_gl_jurisdiction_fallback_policy_missing",
    "layer3_gl_authority_facet_binding_missing",
    "layer3_gl_kg_authority_facets_assumed_present",
    "layer3_gl_text_derived_authority_facet_overclaimed",
    "layer3_gl_authority_facet_binding_semantic_loss",
    "layer3_gl_norm_candidate_binding_missing",
    "layer3_gl_l5_calibration_binding_missing",
    "layer3_gl_norm_temporal_window_missing",
    "layer3_gl_norm_source_authority_missing",
    "layer3_gl_reference_resolution_unresolved",
    "layer3_gl_amendment_lineage_missing",
    "layer3_gl_stale_amendment_lineage",
    "layer3_gl_threshold_authority_record_missing",
    "layer3_gl_threshold_row_not_hydrated",
    "layer3_gl_thresholds_json_used_as_authority",
    "layer3_gl_threshold_unit_or_operator_unparsed",
    "layer3_gl_partial_temporal_row_promoted_to_authority",
    "layer3_gl_mandate_authority_record_missing",
    "layer3_gl_mandate_source_refs_missing",
    "layer3_gl_s6_mandate_semantics_forked",
    "layer3_gl_temporal_competence_record_missing",
    "layer3_gl_legal_authority_report_missing",
    "layer3_gl_selected_norm_without_legal_authority_record",
    "layer3_gl_lex_intervention_map_missing",
    "layer3_gl_lex_intervention_map_used_as_authority",
    "layer3_gl_claim_registry_consumer_gate_missing",
    "layer3_gl_semantic_binding_consumer_gate_missing",
    "layer3_gl_argument_graph_readiness_consumer_gate_missing",
    "layer3_gl_argument_graph_readiness_ref_missing",
    "layer3_gl_s6_mandate_consumer_gate_missing",
    "layer3_gl_s7_delegation_consumer_gate_missing",
    "layer3_gl_s8_value_choice_consumer_gate_missing",
    "layer3_gl_s8_ranking_authorized_without_mandate_pass",
    "layer3_gl_pdc_compiler_consumer_gate_missing",
    "layer3_gl_design_constraint_consumer_gate_missing",
    "layer3_gl_g4_promotion_gate_consumer_gate_missing",
    "layer3_gl_public_raw_legal_payload_leak",
    "layer3_gl_public_export_hook_overclaimed",
    "layer3_gl_public_projection_ref_without_projection_policy",
    "layer3_gl_public_export_projection_mode_mismatch",
    "layer3_gl_public_export_projection_ref_surface_missing",
    "layer3_gl_invariant_readiness_check_unknown",
    "layer3_gl_promotion_authority_leak",
    "layer3_gl_closeout_authority_leak",
    "layer3_gl_adapter_contract_registry_missing",
    "layer3_gl_adapter_registry_summary_only",
    "layer3_gl_adapter_unknown_path",
    "layer3_gl_adapter_semantic_loss",
    "layer3_gl_manifest_runtime_drift",
    "layer3_gl_persisted_artifact_missing",
    "layer3_gl_generated_artifacts_family_missing",
    "layer3_gl_inventory_surface_missing",
    "layer3_gl_reference_index_missing",
    "layer3_gl_public_surface_visibility_missing",
    "layer3_gl_import_laziness_violation",
    "layer3_gl_intervention_resolve_used_in_readiness_import_path",
    "layer3_gl_vector_index_assumed_without_artifact",
}

EXPECTED_BUNDLE_SECTIONS = {
    "adapter_admission_registry",
    "l3_legal_kg_index_coverage",
    "l3_legal_kg_search_ledgers",
    "l3_legal_kg_query_traces",
    "search_recall_freshness",
    "l5_calibration_bindings",
    "legal_requirement_bindings",
    "authority_facet_bindings",
    "norm_candidate_bindings",
    "threshold_authority_records",
    "mandate_authority_records",
    "temporal_competence_records",
    "amendment_lineage_records",
    "reference_resolution_records",
    "legal_authority_report",
    "lex_intervention_map_bindings",
    "claim_registry_consumer_gate",
    "semantic_binding_consumer_gate",
    "argument_graph_readiness_consumer_gate",
    "s6_mandate_consumer_gate",
    "s7_delegation_consumer_gate",
    "s8_value_choice_consumer_gate",
    "pdc_compiler_consumer_gate",
    "design_constraint_consumer_gate",
    "g4_promotion_gate_consumer_gate",
    "promotion_gate_handoff",
    "legal_mandate_audit_surface",
    "public_export_projection_refs",
    "conformance_report",
    "health_metric_delta",
    "adapter_contract_registry",
    "readiness_manifest",
}

EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "rule_version",
    "g0_dependency_status",
    "g1_context_status",
    "g2_context_status",
    "g3_context_status",
    "gl_l3_legal_kg_route_status",
    "gl_l3_legal_kg_table_count",
    "gl_l3_legal_kg_index_coverage_status",
    "gl_search_ledger_count",
    "gl_query_trace_count",
    "gl_search_recall_freshness_status",
    "gl_l5_calibration_binding_status",
    "gl_l5_calibration_binding_count",
    "gl_legal_requirement_binding_count",
    "gl_authority_facet_binding_status",
    "gl_authority_facet_binding_count",
    "gl_norm_candidate_binding_count",
    "gl_legal_authority_report_status",
    "gl_selected_norm_ref_count",
    "gl_legal_authority_record_count",
    "gl_threshold_authority_record_count",
    "gl_mandate_authority_record_count",
    "gl_temporal_competence_status",
    "gl_amendment_lineage_status",
    "gl_reference_resolution_status",
    "gl_lex_intervention_map_binding_status",
    "gl_claim_registry_consumer_gate_status",
    "gl_semantic_binding_consumer_gate_status",
    "gl_argument_graph_readiness_consumer_gate_status",
    "gl_s6_mandate_consumer_gate_status",
    "gl_s7_delegation_consumer_gate_status",
    "gl_s8_value_choice_consumer_gate_status",
    "gl_design_constraint_consumer_gate_status",
    "gl_g4_promotion_gate_consumer_gate_status",
    "gl_public_export_projection_status",
    "gl_public_export_projection_hook_status",
    "gl_public_export_projection_mode",
    "gl_public_export_projection_ref_surface_status",
    "gl_inventory_surface_status",
    "gl_reference_docs_status",
    "gl_invariant_readiness_check_registration_status",
    "gl_adapter_semantic_loss_status",
    "gl_governance_throughput_status",
    "gl_conformance_status",
    "gl_adapter_contract_registry_status",
    "gl_adapter_contract_path_count",
    "gl_health_metric_ids",
}


def _gl() -> Any:
    return import_module("polisyos.runtime.quality.proving_ground.legal_mandate_search")


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return dict(payload)


def _issue_codes(report: Any) -> set[str]:
    return {str(issue["code"]) for issue in _dump(report).get("issues", [])}


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _mutable_gl_runtime_payload() -> dict[str, Any]:
    return json.loads(json.dumps(_dump(_gl().build_layer3_gl_bundle(REPO_ROOT))))


def _validate_mutation(mutator: Any, expected_issue_codes: set[str]) -> None:
    gl = _gl()
    payload = _mutable_gl_runtime_payload()
    mutator(payload)

    report = gl.validate_layer3_gl_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert expected_issue_codes <= _issue_codes(report)


def _write_minimal_legal_kg(repo_root: Path) -> None:
    db_path = repo_root / "production_data/test_lex/finalize/lex_knowledge_graph.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE lex_rule_thresholds (
                threshold_id VARCHAR,
                fact_id VARCHAR,
                metric VARCHAR,
                operator VARCHAR,
                value_decimal VARCHAR,
                value_text VARCHAR,
                unit VARCHAR,
                applies_to VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_rule_thresholds VALUES
            ('threshold-task6-solar-credit', 'fact-task6-credit', 'solar_credit_gap',
             '<=', '0.07', NULL, 'ratio', 'msme_credit_program')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_normative_ready_facts (
                fact_id VARCHAR,
                fact_text VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR,
                effective_from VARCHAR,
                effective_to VARCHAR,
                temporal_resolution_status VARCHAR,
                trust_tier VARCHAR,
                grounding_status VARCHAR,
                canonical_status VARCHAR,
                reference_resolution_status VARCHAR,
                doc_id VARCHAR,
                provision_anchor VARCHAR,
                action_canon VARCHAR,
                norm_type_canon VARCHAR,
                predicate VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_normative_ready_facts VALUES
            ('fact-task6-credit', 'Task 6 credit support threshold.', 'UA', 'economic_policy',
             '2022-03-01', '2022-12-31', 'resolved', 'legal_kg_candidate',
             'grounded', 'canonicalized', 'resolved', 'doc-task6-credit', 'section-1',
             'subsidized_credit', 'threshold', 'credit_support_threshold')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_normative_facts (
                fact_id VARCHAR,
                fact_text VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_normative_facts VALUES
            ('fact-task6-credit', 'Task 6 credit support threshold.', 'UA', 'economic_policy')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_amendments (
                amendment_id VARCHAR,
                amending_doc_id VARCHAR,
                amended_doc_id VARCHAR,
                effective_from VARCHAR,
                target_anchor VARCHAR,
                amendment_type VARCHAR,
                confidence DOUBLE,
                detected_by VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_amendments VALUES
            ('amendment-task6-credit', 'doc-task6-amending', 'doc-task6-credit',
             '2022-05-01', 'section-1', 'update', 0.91, 'task6_temp_kg')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_doc_versions (
                version_row_id VARCHAR,
                doc_id VARCHAR,
                doc_family_id VARCHAR,
                version_id VARCHAR,
                doc_reestr_code VARCHAR,
                doc_type VARCHAR,
                doc_status VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_doc_versions VALUES
            ('version-task6-credit', 'doc-task6-credit', 'family-task6-credit',
             'v1', 'task6-001', 'resolution', 'active')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_doc_temporal (
                doc_id VARCHAR,
                effective_from VARCHAR,
                temporal_resolution_status VARCHAR,
                temporal_state VARCHAR,
                published_at VARCHAR,
                effective_to VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_doc_temporal VALUES
            ('doc-task6-credit', '2022-03-01', 'partial_reissue_required',
             'partial', '2022-03-01', '2022-12-31')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_reference_edges (
                reference_edge_id VARCHAR,
                source_doc_id VARCHAR,
                target_doc_id VARCHAR,
                resolution_status VARCHAR,
                source_anchor VARCHAR,
                target_anchor VARCHAR,
                relation_type VARCHAR,
                resolution_confidence DOUBLE
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_reference_edges VALUES
            ('ref-task6-credit', 'doc-task6-credit', 'doc-task6-target', 'resolved',
             'section-1', 'section-2', 'references', 0.92)
            """
        )
        con.execute(
            """
            CREATE TABLE lex_reference_resolution_audit (
                ref_id VARCHAR,
                source_doc_id VARCHAR,
                resolution_status VARCHAR,
                selected_target_doc_id VARCHAR,
                resolution_method VARCHAR,
                candidate_count INTEGER
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_reference_resolution_audit VALUES
            ('ref-task6-credit', 'doc-task6-credit', 'resolved', 'doc-task6-target',
             'task6_temp_kg', 1)
            """
        )
        con.execute(
            """
            CREATE TABLE lex_temporal_audit (
                audit_id VARCHAR,
                scope VARCHAR,
                doc_id VARCHAR,
                fact_id VARCHAR,
                temporal_resolution_status VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_temporal_audit VALUES
            ('temporal-task6-credit', 'document', 'doc-task6-credit',
             'fact-task6-credit', 'partial_reissue_required')
            """
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def test_layer3_gl_dependency_audit_substrates_are_available_for_task0() -> None:
    g0_manifest = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_g0_readiness_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    g0_counts = g0_manifest["counts"]

    assert (
        g0_manifest["schema_version"] == "policyos.policy_design_case.layer3_g0_discovery_search.v2"
    )
    assert g0_counts["g1_dependency_requirements_status"] == "pass"
    assert g0_counts["engineering_quality_check_status"] == "pass"
    assert g0_counts["search_recall_seed_status"] == "pass"
    assert g0_counts["index_freshness_status"] == "pass"

    context_manifests = {}
    for slice_id in ("g1", "g2", "g3"):
        path = (
            REPO_ROOT / f"architecture/policy_design_case/layer3_{slice_id}_readiness_manifest.json"
        )
        if path.exists():
            context_manifests[slice_id] = json.loads(path.read_text(encoding="utf-8"))
    assert set(context_manifests) == {"g1", "g2", "g3"}

    assert CANONICAL_KG_PATH.exists()
    required_tables = {
        "lex_rule_thresholds",
        "lex_normative_ready_facts",
        "lex_normative_facts",
        "lex_amendments",
        "lex_doc_versions",
        "lex_doc_temporal",
        "lex_reference_edges",
        "lex_reference_resolution_audit",
        "lex_temporal_audit",
    }
    con = duckdb.connect(str(CANONICAL_KG_PATH), read_only=True)
    visible_tables = {
        row[0]
        for row in con.execute(
            "select table_name from information_schema.tables where table_schema='main'"
        ).fetchall()
    }
    assert required_tables <= visible_tables

    import_checks = {
        "polisyos.lex.knowledge.store": "LegalKnowledgeStore",
        "polisyos.lex.knowledge.search": "LegalKnowledgeGraph",
        "polisyos.lex.knowledge.types": None,
        "polisyos.legal_requirement": ("compile_legal_authority_requirements",),
        "polisyos.lex": (
            "build_legal_authority_report",
            "build_normative_applicability_report",
        ),
        "polisyos.lex.interventions.artifacts": "LexProvisionMappingRegistry",
        "polisyos.runtime.quality.claim_registry": None,
        "polisyos.runtime.quality.semantic_binding": None,
        "polisyos.runtime.quality.design_axes.blind_spot_firewalls": "MandateSourceRecord",
        "polisyos.runtime.quality.design_axes.mandate_bounded_delegation": None,
        "polisyos.runtime.quality.design_axes.value_choice_provenance": "AuthorizedValueSchedule",
    }
    for module_name, attrs in import_checks.items():
        module = import_module(module_name)
        if isinstance(attrs, str):
            attrs = (attrs,)
        for attr in attrs or ():
            assert hasattr(module, attr), module_name


def test_layer3_gl_runtime_module_declares_schema_builders_dtos_and_issue_codes() -> None:
    gl = _gl()

    assert gl.LAYER3_GL_SCHEMA_VERSION == GL_SCHEMA_VERSION
    assert gl.LAYER3_GL_RULE_VERSION == GL_RULE_VERSION
    assert gl.GL_SURFACE_ID == GL_SURFACE_ID
    assert gl.GL_PUBLIC_PROJECTION_SURFACE_ID == GL_PUBLIC_PROJECTION_SURFACE_ID
    assert set(gl.ALL_ISSUE_CODES) >= REQUIRED_ISSUE_CODES
    for name in EXPECTED_DTOS | EXPECTED_BUILDERS_AND_VALIDATORS:
        assert hasattr(gl, name), name


def test_layer3_gl_public_dtos_are_strict_pydantic_contracts() -> None:
    gl = _gl()

    for name in EXPECTED_DTOS:
        dto = getattr(gl, name)
        assert issubclass(dto, BaseModel), name
        assert dto.model_config.get("extra") == "forbid", name


def test_layer3_gl_request_dto_is_strict_and_keeps_authority_boundary_defaults() -> None:
    gl = _gl()

    request = gl.Layer3GLLegalMandateRequest(
        request_id="gl-request:test",
        claim_id="claim:gl:test",
        case_id="case:gl:test",
        legal_requirement_ref="legal-requirement://claim/gl/test",
        jurisdiction="UA",
        policy_domain="msme_credit",
        legal_as_of="2022-03-01",
        intervention_family="subsidized_credit",
    )

    assert "legal_authority_without_claim_level_adapter" in request.may_not_use_for
    with pytest.raises(ValidationError):
        gl.Layer3GLLegalMandateRequest(
            request_id="gl-request:test",
            claim_id="claim:gl:test",
            case_id="case:gl:test",
            legal_requirement_ref="legal-requirement://claim/gl/test",
            jurisdiction="UA",
            policy_domain="msme_credit",
            legal_as_of="2022-03-01",
            intervention_family="subsidized_credit",
            surprise_contract=True,
        )


def test_layer3_gl_bundle_contains_required_sections_and_manifest_keys() -> None:
    payload = _dump(_gl().build_layer3_gl_bundle(REPO_ROOT))

    assert set(payload) >= EXPECTED_BUNDLE_SECTIONS
    assert payload["readiness_manifest"]["schema_version"] == GL_SCHEMA_VERSION
    assert set(payload["readiness_manifest"]) >= EXPECTED_MANIFEST_KEYS


def test_layer3_gl_plan_fixtures_fail_closed_without_relation_verification() -> None:
    gl = _gl()

    valid = _fixture("valid_legal_mandate_minimal_bundle.json")
    valid_report = gl.validate_layer3_gl_bundle(REPO_ROOT, valid["payload"])

    assert _dump(valid_report)["status"] == "fail"
    assert "legal_source_relation_verification_not_established" in _issue_codes(valid_report)

    malformed_expectations = {
        "malformed_text_search_used_as_authority.json": {"layer3_gl_text_search_used_as_authority"},
        "malformed_threshold_without_hydrated_rule_row.json": {
            "layer3_gl_threshold_row_not_hydrated",
            "layer3_gl_thresholds_json_used_as_authority",
        },
        "malformed_intervention_map_used_as_authority.json": {
            "layer3_gl_lex_intervention_map_used_as_authority"
        },
    }
    for fixture_name, expected_issue_codes in malformed_expectations.items():
        fixture = _fixture(fixture_name)
        report = gl.validate_layer3_gl_bundle(REPO_ROOT, fixture["payload"])

        assert _dump(report)["status"] == "fail"
        assert expected_issue_codes <= _issue_codes(report), fixture_name


def test_layer3_gl_task8_g0_manifest_counts_pass_satisfies_closeout_dependency() -> None:
    gl = _gl()
    payload = _dump(gl.build_layer3_gl_bundle(REPO_ROOT))

    assert payload["readiness_manifest"]["g0_dependency_status"] == "pass"

    report = gl.validate_layer3_gl_bundle(REPO_ROOT, payload)

    assert "layer3_gl_g0_dependency_not_ready" not in _issue_codes(report)


def test_layer3_gl_task8_reports_unverified_relation_as_limited_authority() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    payload = _dump(bundle)
    conformance = payload["conformance_report"]
    health = payload["health_metric_delta"]

    refusal = "legal_source_relation_verification_not_established"
    report = payload["legal_authority_report"]
    assert conformance["status"] == "fail"
    assert conformance["performance_status"] == "fail"
    assert conformance["closeout_status"] == "fail"
    assert conformance["conformance_gate_statuses"]["g0_dependency"] == "pass"
    assert conformance["conformance_gate_statuses"]["legal_kg_route"] == "pass"
    assert conformance["conformance_gate_statuses"]["search_recall_freshness"] == "pass"
    assert conformance["conformance_gate_statuses"]["claim_level_authority"] == "fail"
    assert conformance["conformance_gate_statuses"]["consumer_gates"] == "fail"
    assert conformance["conformance_gate_statuses"]["public_projection"] == "pass"
    assert conformance["conformance_gate_statuses"]["adapter_registry"] == "pass"
    assert conformance["conformance_gate_statuses"]["performance_scaling"] == "fail"
    assert report["status"] == "fail"
    assert report["selected_norm_refs"] == []
    assert refusal not in report["blocker_refs"]
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report["blocker_refs"]
    assert "layer3_gl_norm_temporal_window_missing" in report["blocker_refs"]
    assert refusal not in report["issue_codes"]
    assert payload["claim_registry_consumer_gate"]["status"] == "fail"
    assert refusal in payload["claim_registry_consumer_gate"]["issue_codes"]
    assert payload["semantic_binding_consumer_gate"]["status"] == "fail"
    assert (
        "layer3_gl_semantic_binding_consumer_gate_missing"
        in payload["semantic_binding_consumer_gate"]["issue_codes"]
    )
    assert refusal not in payload["semantic_binding_consumer_gate"]["issue_codes"]
    assert payload["readiness_manifest"]["gl_conformance_status"] == "fail"
    assert payload["readiness_manifest"]["gl_adapter_semantic_loss_status"] == "fail"
    assert payload["readiness_manifest"]["gl_governance_throughput_status"] == "fail"
    assert health["readings"]["adapter-semantic-loss"] == "fail"
    assert health["readings"]["governance-throughput"] == "fail"

    for trace in payload["l3_legal_kg_query_traces"]:
        assert "LIMIT" in trace["sql_shape"].upper()
        assert trace["bounded_result_limit"] <= 256
        assert trace["query_budget"]["python_full_scan_allowed"] is False
        assert trace["query_budget"]["full_corpus_scan_allowed"] is False
        assert trace["observed_row_count"] <= trace["bounded_result_limit"] + 1
        if trace["observed_row_count"] > trace["bounded_result_limit"]:
            assert trace["observed_row_count"] == trace["bounded_result_limit"] + 1
            assert trace["query_budget"]["completeness_status"] == "budget_cutoff"
    assert not any(
        ledger["used_full_table_scan"] for ledger in payload["l3_legal_kg_search_ledgers"]
    )


def test_layer3_gl_task1_coverage_checks_canonical_kg_tables_columns_and_facet_gap() -> None:
    gl = _gl()

    coverage = gl.build_gl_l3_legal_kg_index_coverage(REPO_ROOT)
    payload = _dump(coverage)

    assert payload["status"] == "pass"
    assert payload["canonical_kg_path"] == gl.CANONICAL_L3_LEGAL_KG_PATH.as_posix()
    assert payload["canonical_route_status"] == "canonical_l3_legal_kg"
    assert payload["required_table_count"] >= 9
    assert payload["missing_required_tables"] == []
    assert payload["missing_required_columns"] == {}
    assert payload["table_counts"]["lex_rule_thresholds"] > 0
    assert payload["table_counts"]["lex_normative_ready_facts"] > 0
    assert payload["authority_facet_source_status"] == "requires_gl_facet_binding"
    assert "lex_rule_thresholds.metric" in payload["required_column_refs"]
    assert "lex_rule_thresholds.operator" in payload["required_column_refs"]
    assert "lex_rule_thresholds.value_decimal" in payload["required_column_refs"]
    assert "lex_rule_thresholds.unit" in payload["required_column_refs"]
    assert payload["db_identity"]["size_bytes"] > 0
    assert payload["companion_file_refs"]


def test_layer3_gl_task1_search_ledgers_use_bounded_canonical_sql_and_hydrate_threshold_rows() -> (
    None
):
    gl = _gl()
    request = gl.Layer3GLLegalMandateRequest(
        request_id="gl-request:task1-threshold",
        claim_id="claim:gl:task1-threshold",
        case_id="case:gl:task1-threshold",
        legal_requirement_ref="legal-requirement://claim/gl/task1-threshold",
        jurisdiction="UA",
        policy_domain="economic_policy",
        legal_as_of="2022-03-01",
        intervention_family="subsidized_credit",
        query_terms=("tax", "credit", "threshold"),
        limit=5,
    )

    ledgers = gl.build_gl_legal_search_ledgers(REPO_ROOT, [request])
    traces = gl.build_gl_legal_query_traces(REPO_ROOT, ledgers)
    ledger_payloads = [_dump(ledger) for ledger in ledgers]
    trace_payloads = [_dump(trace) for trace in traces]

    assert any(
        ledger["status"] in {"complete_with_candidates", "incomplete_budget_cutoff"}
        for ledger in ledger_payloads
    )
    assert any(
        ledger["status"] in {"complete_no_candidate", "incomplete_schema_mismatch"}
        for ledger in ledger_payloads
    )
    canonical_ledgers = [
        ledger for ledger in ledger_payloads if ledger["canonical_route"] == "l3_legal_kg_duckdb"
    ]
    assert canonical_ledgers
    assert {
        "threshold_metric_operator_value_unit",
        "normative_fact",
        "amendment_lineage",
        "provision_source_bundle",
        "reference_resolution",
        "intervention_map_candidate",
    } <= {
        candidate["candidate_path"]
        for ledger in canonical_ledgers
        for candidate in ledger["candidate_rows"]
    }
    assert any("bounded_no_hit_probe" in ledger["no_hit_blockers"] for ledger in canonical_ledgers)
    for ledger in canonical_ledgers:
        assert ledger["authoritative_for"] == []
        assert "legal_authority_without_claim_level_adapter" in ledger["may_not_use_for"]
        assert ledger["bounded_result_limit"] <= request.limit
        assert ledger["query_trace_refs"]
        assert ledger["legal_kg_snapshot_ref"].startswith("sha256:")
        assert ledger["used_full_table_scan"] is False
        assert ledger["transition_input"] is False

    threshold_ledgers = [
        ledger for ledger in canonical_ledgers if "lex_rule_thresholds" in ledger["table_routes"]
    ]
    assert threshold_ledgers
    assert all(
        "lex_normative_ready_facts" in ledger["table_routes"] for ledger in threshold_ledgers
    )
    threshold_hits = [
        candidate
        for ledger in threshold_ledgers
        for candidate in ledger["candidate_rows"]
        if candidate["source_table"] == "lex_rule_thresholds"
    ]
    assert threshold_hits
    assert any(hit["metric"] and hit["operator"] and hit["unit"] for hit in threshold_hits)
    assert all(hit["hydrated_from_table"] == "lex_rule_thresholds" for hit in threshold_hits)
    assert all(hit["threshold_source_field"] != "thresholds_json" for hit in threshold_hits)

    assert trace_payloads
    for trace in trace_payloads:
        assert trace["canonical_route"] == "l3_legal_kg_duckdb"
        assert trace["bounded_result_limit"] <= request.limit
        assert "LIMIT" in trace["sql_shape"].upper()
        assert trace["selected_row_refs"] or trace["no_hit_reasons"]
        assert trace["query_budget"]["python_full_scan_allowed"] is False
    assert {
        "lex_normative_ready_facts",
        "lex_amendments",
        "lex_doc_versions",
        "lex_doc_temporal",
        "lex_reference_edges",
        "lex_reference_resolution_audit",
    } <= {table for trace in trace_payloads for table in trace["table_routes"]}


def test_task6_gl_temp_legal_threshold_insertion_is_replayable_with_temporal_reissue_gate(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from polisyos.runtime.quality.proving_ground.status_decision_reducers import (
        GLLegalAuthorityInputs,
        Layer3ReducerInputRef,
        reduce_gl_legal_authority,
    )

    _write_minimal_legal_kg(tmp_path)
    gl = _gl()
    monkeypatch.setattr(
        gl,
        "CANONICAL_L3_LEGAL_KG_PATH",
        Path("production_data/test_lex/finalize/lex_knowledge_graph.duckdb"),
    )
    gl._cached_coverage.cache_clear()
    request = gl.Layer3GLLegalMandateRequest(
        request_id="gl-request:task6-temp-threshold",
        claim_id="claim:gl:task6-temp-threshold",
        case_id="case:gl:task6-temp-threshold",
        legal_requirement_ref="legal-requirement://claim/gl/task6-temp-threshold",
        jurisdiction="UA",
        policy_domain="economic_policy",
        legal_as_of="2022-03-01",
        intervention_family="subsidized_credit",
        query_terms=("solar", "credit", "threshold"),
        limit=5,
    )

    ledgers = gl.build_gl_legal_search_ledgers(tmp_path, [request])
    threshold_hits = [
        candidate
        for ledger in ledgers
        for candidate in ledger.candidate_rows
        if candidate.get("row_ref") == "lex_rule_thresholds:threshold-task6-solar-credit"
    ]
    temporal_records = gl.build_gl_temporal_competence_records(tmp_path, ledgers=ledgers)
    decision = reduce_gl_legal_authority(
        GLLegalAuthorityInputs(
            legal_basis_status="candidate",
            applicability_status="pass",
            mandate_status="missing",
            input_refs=(
                Layer3ReducerInputRef(
                    ref="duckdb://task6-temp-legal-kg#threshold-task6-solar-credit",
                    content_hash="sha256:" + "9" * 64,
                    producer_ref="measurement://layer3-gl/task6-temp-legal-kg",
                    producer_type="measurement",
                    producer_root_refs=("measurement://layer3-gl/task6-temp-legal-kg-root",),
                ),
            ),
        )
    )

    assert threshold_hits
    assert threshold_hits[0]["metric"] == "solar_credit_gap"
    assert threshold_hits[0]["operator"] == "<="
    assert threshold_hits[0]["hydrated_from_table"] == "lex_rule_thresholds"
    assert all(ledger.authoritative_for == () for ledger in ledgers)
    assert all(
        "legal_authority_without_claim_level_adapter" in ledger.may_not_use_for
        for ledger in ledgers
    )
    assert any(record.status == "reissue_required" for record in temporal_records)
    assert all(
        record.legal_authority_record_refs == ()
        for record in temporal_records
        if record.status == "reissue_required"
    )
    assert decision.status == "typed_blocker"
    assert {
        "layer3_gl_legal_basis_not_authoritative",
        "layer3_gl_mandate_not_authoritative",
    } <= set(decision.blocker_refs)


def test_layer3_gl_task2_search_recall_freshness_tracks_all_known_seed_classes() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    report = _dump(bundle.search_recall_freshness)

    assert report["status"] == "pass"
    assert report["known_seed_status"] == "pass"
    assert report["index_freshness_status"] == "pass"
    assert report["snapshot_consistency_status"] == "pass"
    assert report["companion_freshness_status"] == "pass"
    assert set(report["known_seed_results"]) == {
        "known_threshold_seed",
        "known_norm_seed",
        "known_amendment_seed",
        "known_temporal_seed",
        "known_reference_seed",
        "known_mapping_seed",
    }
    assert {
        seed_class
        for seed_class, seed in report["known_seed_results"].items()
        if seed["status"] == "pass"
    } == set(report["known_seed_results"])
    assert report["missed_known_seed_classes"] == []
    assert report["stale_snapshot_refs"] == []
    assert report["generated_ledger_snapshot_refs"] == [report["legal_kg_snapshot_ref"]]
    assert report["false_abstention_disposition"] == "typed_legal_no_ground_blocker_allowed"
    assert report["typed_no_ground_blocker"] == "legal_no_ground_after_fresh_known_seed_recall"
    assert report["domain_ceiling_allowed"] is False
    assert report["honest_legal_no_ground_allowed"] is True
    assert "search-recall@known-seeds+index-staleness" in bundle.health_metric_delta["metric_ids"]
    assert (
        bundle.health_metric_delta["readings"]["search-recall@known-seeds+index-staleness"]
        == "pass"
    )


def test_layer3_gl_task2_missed_known_seed_blocks_domain_ceiling_claims() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers = tuple(
        ledger.model_copy(update={"candidate_rows": (), "selected_row_refs": ()})
        for ledger in bundle.l3_legal_kg_search_ledgers
    )

    report = _dump(gl.build_gl_search_recall_freshness(REPO_ROOT, ledgers))

    assert report["status"] == "fail"
    assert report["known_seed_status"] == "fail"
    assert set(report["missed_known_seed_classes"]) == set(report["known_seed_results"])
    assert report["false_abstention_disposition"] == "search_ceiling_repair_required"
    assert report["search_ceiling_repair_required"] is True
    assert report["domain_ceiling_allowed"] is False
    assert report["honest_legal_no_ground_allowed"] is False
    assert "layer3_gl_search_recall_seed_miss_blocks_domain_ceiling" in report["issue_codes"]
    assert "domain_ceiling" not in report["typed_no_ground_blocker"]


def test_layer3_gl_task2_stale_snapshot_blocks_honest_no_hit_abstention() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    stale_ledgers = tuple(
        ledger.model_copy(
            update={
                "candidate_rows": (),
                "selected_row_refs": (),
                "legal_kg_snapshot_ref": "sha256:stale-gl-test-snapshot",
                "index_schema_snapshot_ref": "sha256:stale-gl-test-snapshot",
            }
        )
        for ledger in bundle.l3_legal_kg_search_ledgers
    )

    report = _dump(gl.build_gl_search_recall_freshness(REPO_ROOT, stale_ledgers))

    assert report["status"] == "fail"
    assert report["index_freshness_status"] == "fail"
    assert report["snapshot_consistency_status"] == "fail"
    assert report["stale_snapshot_refs"] == ["sha256:stale-gl-test-snapshot"]
    assert report["false_abstention_disposition"] == "search_ceiling_repair_required"
    assert report["search_ceiling_repair_required"] is True
    assert report["honest_legal_no_ground_allowed"] is False
    assert "layer3_gl_stale_legal_index_blocks_domain_ceiling" in report["issue_codes"]


def test_layer3_gl_task3_compiles_persisted_legal_requirement_bindings() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    bindings = [_dump(binding) for binding in bundle.legal_requirement_bindings]

    assert bindings
    binding = bindings[0]
    spec = binding["requirement_spec"]
    artifact = binding["requirement_artifact"]

    assert binding["status"] == "pass"
    assert binding["claim_id"] == "gl_canonical_threshold_seed"
    assert binding["claim_ref"] == "claim:gl:canonical-threshold-seed"
    assert binding["mandatory"] is True
    assert binding["out_of_scope"] is False
    assert binding["authority_types"] == ["implementing"]
    assert binding["authority_type_source"] == "compiler_default"
    assert binding["compiler_default_marked"] is True
    assert binding["compiler_default_fields"] == ["authority_types"]
    assert binding["required_hierarchy_depth"] >= 1
    assert binding["temporal_competence_window"]["legal_as_of"] == "2022-03-01"
    assert binding["fallback_policy"]["config_ref"] == "jurisdiction-fallback:gl-ua-v1"
    assert binding["jurisdiction"] == "UA"
    assert binding["authority_profile_ref"] == "gl_legal_mandate"
    assert binding["rule_version_ref"] == "legal-requirement-compiler:v1"
    assert binding["legal_requirement_artifact_ref"].startswith(
        "repo://architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json#"
    )
    assert spec["requirement_id"] == binding["requirement_ref"]
    assert spec["authority_types"] == ["implementing"]
    assert artifact["schema_version"] == "policyos.legal_requirement_artifact.v1"
    assert artifact["requirements"][0] == spec
    assert (
        "legal_admissibility_without_lex_evaluation"
        in artifact["authority_boundary"]["may_not_use_for"]
    )


def test_layer3_gl_task3_non_legal_claim_compiles_out_of_scope_requirement() -> None:
    gl = _gl()
    claims = [
        {
            "claim_id": "gl_non_legal_context",
            "claim_ref": "claim:gl:non-legal-context",
            "legal_authority_required": False,
            "policy_domain": "economic_policy",
        }
    ]

    bindings = [
        _dump(binding)
        for binding in gl.build_gl_legal_requirement_bindings(REPO_ROOT, claims=claims)
    ]

    assert len(bindings) == 1
    binding = bindings[0]
    assert binding["status"] == "out_of_scope"
    assert binding["mandatory"] is False
    assert binding["out_of_scope"] is True
    assert binding["authority_types"] == []
    assert binding["no_authority_rationale"] == "claim_marked_non_legal_or_no_authority_required"
    assert binding["requirement_spec"]["fallback_policy"]["mode"] == "not_applicable"


def test_layer3_gl_task3_authority_facet_bindings_preserve_sources_and_missing_facets() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    facets = [_dump(binding) for binding in bundle.authority_facet_bindings]

    assert facets
    facet_by_name = {facet["facet_name"]: facet for facet in facets}
    assert facet_by_name["authority_types"]["facet_source"] == "compiler_default"
    assert facet_by_name["authority_types"]["derived_from_compiler_default"] is True
    assert facet_by_name["authority_types"]["validation_status"] == "context_only"
    assert facet_by_name["source_authority"]["facet_source"] in {
        "derived_from_doc_metadata",
        "governed_config",
    }
    assert facet_by_name["source_authority"]["source_column_refs"]
    assert facet_by_name["competent_actor_ref"]["facet_source"] in {"governed_config", "missing"}
    assert facet_by_name["instrument_types"]["facet_source"] in {"governed_config", "missing"}
    assert all(facet["source_row_refs"] for facet in facets)
    assert all("derivation_rule_ref" in facet for facet in facets)
    assert all("semantic_loss_status" in facet for facet in facets)
    assert not any(
        facet["facet_source"] == "lex_discovered" and facet["derived_from_compiler_default"]
        for facet in facets
    )


def test_layer3_gl_candidate_facet_projection_rejects_malformed_present_values() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    candidate = gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert candidate is not None
    requirement = bundle.legal_requirement_bindings[0]
    row_ref = str(candidate.get("row_ref") or "")
    binding_ref = f"gl-norm-candidate:{gl._stable_id(row_ref)}"
    facets = gl._facets_by_name_for_candidate(bundle.authority_facet_bindings, binding_ref)
    binding_refs = gl._facet_refs_for_candidate(bundle.authority_facet_bindings, binding_ref)

    def project(candidate_facets: Mapping[str, Any]) -> dict[str, Any]:
        return gl._candidate_norm_from_facets(
            candidate=candidate,
            requirement=requirement,
            facets=candidate_facets,
            authority_facet_binding_refs=binding_refs,
            ledgers=bundle.l3_legal_kg_search_ledgers,
        )

    existing_projection = project(facets)
    assert existing_projection["candidate_context_status"] == "context_only"
    assert existing_projection["authority_facet_binding_refs"] == binding_refs

    for facet_name in ("hierarchy", "conflict_supersession_preemption", "fallback"):
        facet = facets[facet_name]
        malformed = dict(facets)
        malformed[facet_name] = facet.model_copy(update={"facet_value": ["malformed"]})
        with pytest.raises(TypeError, match=rf"{facet_name!r}.*mapping"):
            project(malformed)

    hierarchy = facets["hierarchy"]
    malformed_authority_level = dict(facets)
    malformed_authority_level["hierarchy"] = hierarchy.model_copy(
        update={"facet_value": {"authority_level": 17}}
    )
    with pytest.raises(TypeError, match=r"authority_level.*text"):
        project(malformed_authority_level)

    malformed_depth = dict(facets)
    malformed_depth["hierarchy"] = hierarchy.model_copy(
        update={"facet_value": {"authority_level": "", "hierarchy_depth": "two"}}
    )
    with pytest.raises(TypeError, match=r"hierarchy_depth.*integer"):
        project(malformed_depth)

    null_depth = dict(facets)
    null_depth["hierarchy"] = hierarchy.model_copy(
        update={"facet_value": {"authority_level": "", "hierarchy_depth": None}}
    )
    with pytest.raises(TypeError, match=r"hierarchy_depth.*integer"):
        project(null_depth)

    explicit_falsy_values = dict(facets)
    explicit_falsy_values["hierarchy"] = hierarchy.model_copy(
        update={"facet_value": {"authority_level": "", "hierarchy_depth": 0}}
    )
    falsy_projection = project(explicit_falsy_values)
    assert falsy_projection["authority_level"] == ""
    assert falsy_projection["hierarchy_depth"] == 0

    conflict = facets["conflict_supersession_preemption"]
    malformed_conflict_field = dict(facets)
    malformed_conflict_field["conflict_supersession_preemption"] = conflict.model_copy(
        update={"facet_value": {"conflict_state": []}}
    )
    with pytest.raises(TypeError, match=r"conflict_state.*text"):
        project(malformed_conflict_field)

    malformed_fallback_field = dict(facets)
    malformed_fallback_field["fallback"] = facets["fallback"].model_copy(
        update={"facet_value": {"config_ref": []}}
    )
    with pytest.raises(TypeError, match=r"config_ref.*text"):
        project(malformed_fallback_field)

    threshold = gl._threshold_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert threshold is not None
    threshold_ref = str(threshold.get("row_ref") or "")
    threshold_binding_ref = f"gl-norm-candidate:{gl._stable_id(threshold_ref)}"
    threshold_facets = gl._facets_by_name_for_candidate(
        bundle.authority_facet_bindings,
        threshold_binding_ref,
    )
    malformed_threshold_facets = dict(threshold_facets)
    malformed_threshold_facets["hierarchy"] = threshold_facets["hierarchy"].model_copy(
        update={"facet_value": ["malformed"]}
    )
    with pytest.raises(TypeError, match=r"hierarchy.*mapping"):
        gl._threshold_candidate_norm_from_facets(
            candidate=threshold,
            requirement=requirement,
            facets=malformed_threshold_facets,
            authority_facet_binding_refs=gl._facet_refs_for_candidate(
                bundle.authority_facet_bindings,
                threshold_binding_ref,
            ),
            ledgers=bundle.l3_legal_kg_search_ledgers,
        )


def test_layer3_gl_missing_source_window_is_typed_before_lex_adapters() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    norm_bindings = [_dump(binding) for binding in bundle.norm_candidate_bindings]
    report = _dump(bundle.legal_authority_report)
    requirements = [_dump(binding) for binding in bundle.legal_requirement_bindings]

    assert norm_bindings
    assert all(binding["status"] == "blocked" for binding in norm_bindings)
    assert all(binding["candidate_norm"] == {} for binding in norm_bindings)
    for binding in norm_bindings:
        if binding["source_table"] == "lex_normative_ready_facts":
            assert "layer3_gl_authority_facet_binding_semantic_loss" in binding["issue_codes"]
            assert "layer3_gl_norm_temporal_window_missing" not in binding["issue_codes"]
        else:
            assert binding["source_table"] == "lex_rule_thresholds"
            assert "layer3_gl_norm_temporal_window_missing" in binding["issue_codes"]

    assert report["candidate_source"] == "gl_norm_candidate_bindings"
    assert report["used_internal_requirement_compile"] is False
    assert report["runtime_candidate_norms_used_for_closure"] is False
    assert report["applicability_internal_kg_fallback_used"] is False
    assert report["adapter_candidate_norm_count"] == 0
    assert report["adapter_input_contract"]["candidate_norm_count"] == 0
    assert report["producer_artifact_ref"].startswith(
        "repo://architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json#"
    )
    assert report["explicit_gl_requirement_spec_refs"] == [requirements[0]["requirement_ref"]]
    assert report["adapter_input_contract"]["legal_requirement_specs"] == [
        requirements[0]["requirement_spec"]
    ]
    assert report["adapter_report"]["legal_requirement_specs"] == [
        requirements[0]["requirement_spec"]
    ]
    assert report["applicability_report"]["legal_requirement_specs"] == [
        requirements[0]["requirement_spec"]
    ]
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report["issue_codes"]
    assert "layer3_gl_norm_temporal_window_missing" in report["issue_codes"]


def test_layer3_gl_task3_missing_fallback_or_required_facets_fails_closed() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["legal_requirement_bindings"][0]["fallback_policy"] = {}
        for facet in payload["authority_facet_bindings"]:
            if facet["facet_name"] in {
                "source_authority",
                "competent_actor_ref",
                "instrument_types",
            }:
                facet["facet_source"] = "missing"
                facet["facet_value"] = None
                facet["validation_status"] = "blocked"
                facet["semantic_loss_status"] = "missing_required_facet"

    _validate_mutation(
        mutate,
        {
            "layer3_gl_jurisdiction_fallback_policy_missing",
            "layer3_gl_norm_source_authority_missing",
            "layer3_gl_authority_facet_binding_semantic_loss",
        },
    )


def test_layer3_gl_task3_internal_applicability_kg_fallback_cannot_close_gl() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["norm_candidate_bindings"] = []
        payload["legal_authority_report"]["candidate_source"] = "applicability_internal_lex_kg"
        payload["legal_authority_report"]["applicability_internal_kg_fallback_used"] = True

    _validate_mutation(
        mutate,
        {
            "layer3_gl_applicability_report_internal_lex_kg_fallback_used_for_closure",
            "layer3_gl_norm_candidate_binding_missing",
        },
    )


def test_layer3_gl_task4_legal_authority_report_selects_norm_and_preserves_adapter_waist() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    report = _dump(bundle.legal_authority_report)

    assert report["status"] == "fail"
    assert report["selected_norm_refs"] == []
    assert report["legal_authority_record_refs"] == []
    assert report["adapter_candidate_norm_count"] == 0
    assert "legal_authority_no_candidate_norm" in report["blocker_refs"]
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report["blocker_refs"]
    assert "layer3_gl_norm_temporal_window_missing" in report["blocker_refs"]
    assert report["used_internal_requirement_compile"] is False
    assert report["runtime_candidate_norms_used_for_closure"] is False
    assert report["applicability_internal_kg_fallback_used"] is False
    assert report["producer_artifact_ref"].startswith(
        "repo://architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json#"
    )
    assert report["adapter_input_contract"]["candidate_norm_count"] == 0
    assert report["adapter_report"]["producer_artifact_ref"] == report["producer_artifact_ref"]
    assert not report["adapter_report"].get("selected_norm_refs")
    assert not report["applicability_report"].get("selected_norm_refs")


def test_layer3_gl_public_authority_builders_refuse_self_attested_source_relation() -> None:
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationVerificationMissingError,
    )

    gl = _gl()
    report = gl.Layer3GLLegalAuthorityReportBinding(
        status="pass",
        claim_id="claim:fake",
        requirement_ref="requirement:fake",
        legal_as_of="2026-01-01",
        jurisdiction="UA",
        selected_norm_refs=("norm.fake",),
        legal_authority_record_refs=("legal-authority-record:fake",),
    )
    norm = gl.Layer3GLNormCandidateBinding(
        status="pass",
        binding_id="candidate:fake",
        kg_row_ref="lex_normative_facts:fake",
        candidate_norm_status="admitted_candidate",
        context_only=False,
        legal_kg_snapshot_ref="snapshot:fake",
        candidate_norm={
            "norm_id": "norm.fake",
            "source_provenance_ref": "fake://no-source",
            "lex_rule_threshold_refs": ["lex_rule_thresholds:fake"],
            "effective_from": "2020-01-01",
            "effective_to": "2030-01-01",
        },
    )
    ledger = gl.Layer3GLLegalSearchLedger(
        status="pass",
        ledger_id="ledger:fake",
        request_ref="request:fake",
        legal_kg_snapshot_ref="snapshot:fake",
        selected_row_refs=("lex_rule_thresholds:fake",),
        candidate_rows=(
            {
                "row_ref": "lex_rule_thresholds:fake",
                "hydrated_from_table": "lex_rule_thresholds",
                "threshold_source_field": "lex_rule_thresholds",
                "metric": "eligibility",
                "operator": "<=",
                "value_decimal": "5",
                "unit": "years",
                "fact_id": "fact.fake",
            },
        ),
    )

    with pytest.raises(LegalSourceRelationVerificationMissingError):
        gl.build_gl_threshold_authority_records(
            REPO_ROOT,
            ledgers=(ledger,),
            legal_authority_report=report,
            norm_candidate_bindings=(norm,),
        )
    with pytest.raises(LegalSourceRelationVerificationMissingError):
        gl.build_gl_temporal_competence_records(
            REPO_ROOT,
            ledgers=(ledger,),
            legal_authority_report=report,
            norm_candidate_bindings=(norm,),
        )
    with pytest.raises(LegalSourceRelationVerificationMissingError):
        gl.build_gl_design_constraint_consumer_gate(
            legal_authority_report=report,
            threshold_authority_records=(),
            mandate_authority_records=(),
        )


def test_layer3_gl_authority_record_argument_roles_refuse_typed_and_serialized_inputs() -> None:
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationVerificationMissingError,
        current_legal_source_relation_disposition,
    )

    gl = _gl()
    report = gl.Layer3GLLegalAuthorityReportBinding(
        status="fail",
        claim_id="claim:unverified",
        requirement_ref="requirement:unverified",
        legal_as_of="2026-01-01",
        jurisdiction="UA",
    )
    mandate = gl.Layer3GLMandateAuthorityRecord(record_id="gl-mandate:unverified")
    threshold = gl.Layer3GLThresholdAuthorityRecord(record_id="gl-threshold:unverified")
    s6_gate = gl.Layer3GLS6MandateConsumerGate(status="fail")
    mandate_inputs = (
        [mandate],
        [mandate.model_dump(mode="json")],
        [{"record_id": mandate.record_id, "unexpected": True}],
        {"record_id": mandate.record_id, "unexpected": True},
    )
    threshold_inputs = (
        [threshold],
        [threshold.model_dump(mode="json")],
        [{"record_id": threshold.record_id, "unexpected": True}],
        {"record_id": threshold.record_id, "unexpected": True},
    )
    assert current_legal_source_relation_disposition().refusal.status == "verification_missing"

    for records in mandate_inputs:
        with pytest.raises(LegalSourceRelationVerificationMissingError):
            gl.build_gl_public_export_projection_refs(
                legal_authority_report=report,
                threshold_authority_records=(),
                mandate_authority_records=records,
            )
        with pytest.raises(LegalSourceRelationVerificationMissingError):
            gl.build_gl_s6_mandate_consumer_gate(
                legal_authority_report=report,
                mandate_authority_records=records,
            )
        with pytest.raises(LegalSourceRelationVerificationMissingError):
            gl.build_gl_s7_delegation_consumer_gate(
                mandate_authority_records=records,
                s6_mandate_consumer_gate=s6_gate,
            )
        with pytest.raises(LegalSourceRelationVerificationMissingError):
            gl.build_gl_s8_value_choice_consumer_gate(
                mandate_authority_records=records,
                s6_mandate_consumer_gate=s6_gate,
            )

    for records in threshold_inputs:
        with pytest.raises(LegalSourceRelationVerificationMissingError):
            gl.build_gl_public_export_projection_refs(
                legal_authority_report=report,
                threshold_authority_records=records,
                mandate_authority_records=(),
            )

    for role_name, records_input_set in (
        ("mandate_authority_records", mandate_inputs),
        ("threshold_authority_records", threshold_inputs),
    ):
        for records in records_input_set:
            payload = _mutable_gl_runtime_payload()
            payload["legal_authority_report"]["selected_norm_refs"] = []
            payload["legal_authority_report"]["legal_authority_record_refs"] = []
            payload["legal_authority_report"]["blocker_refs"] = []
            payload["legal_authority_report"]["issue_codes"] = []
            payload[role_name] = records

            validation = gl.validate_layer3_gl_bundle(REPO_ROOT, payload)
            assert "legal_source_relation_verification_not_established" in _issue_codes(validation)


def test_layer3_gl_mandate_projection_uses_the_strict_serialized_record_contract() -> None:
    gl = _gl()
    mandate = gl.Layer3GLMandateAuthorityRecord(
        record_id="gl-mandate:typed",
        legal_authority_record_refs=("legal-authority-record://typed",),
        limitation_refs=("gl-limitation:typed",),
    )
    serialized = mandate.model_dump(mode="json")

    assert gl._gl_legal_refs_from_mandates((mandate, serialized)) == (
        "legal-authority-record://typed",
    )
    assert gl._gl_mandate_limitations((mandate, serialized)) == ("gl-limitation:typed",)

    malformed_refs = {
        "record_id": "gl-mandate:malformed",
        "legal_authority_record_refs": [None],
    }
    malformed_extra = {"record_id": "gl-mandate:extra", "unexpected": True}
    for malformed in (malformed_refs, malformed_extra):
        with pytest.raises(ValidationError):
            gl._gl_legal_refs_from_mandates((malformed,))


def test_layer3_gl_empty_authority_record_roles_keep_candidate_reference_projection() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)

    assert bundle.norm_candidate_bindings
    assert bundle.mandate_authority_records == ()
    assert bundle.threshold_authority_records == ()
    assert bundle.public_export_projection_refs.projection_refs["mandate_record_refs"] == ()


def test_layer3_gl_validator_recomputes_relation_refusal_after_marker_removal() -> None:
    gl = _gl()
    payload = _fixture("valid_legal_mandate_minimal_bundle.json")["payload"]
    report = payload["legal_authority_report"]
    assert report["selected_norm_refs"]
    assert report["legal_authority_record_refs"]
    report["blocker_refs"] = []
    report["issue_codes"] = []

    validation = gl.validate_layer3_gl_bundle(REPO_ROOT, payload)

    assert _dump(validation)["status"] == "fail"
    assert "legal_source_relation_verification_not_established" in _issue_codes(validation)


def test_layer3_gl_task4_threshold_authority_record_binds_hydrated_rule_row() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    records = [_dump(record) for record in bundle.threshold_authority_records]
    threshold_binding = next(
        binding
        for binding in bundle.norm_candidate_bindings
        if binding.source_table == "lex_rule_thresholds"
    )

    assert records == []
    assert threshold_binding.status == "blocked"
    assert threshold_binding.candidate_norm == {}
    assert "layer3_gl_norm_temporal_window_missing" in threshold_binding.issue_codes
    report = _dump(bundle.legal_authority_report)
    assert report["legal_authority_record_refs"] == []
    assert "legal_authority_no_candidate_norm" in report["blocker_refs"]


def test_layer3_gl_task4_mandate_record_uses_s6_compatible_handoff_without_forking() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    records = [_dump(record) for record in bundle.mandate_authority_records]
    report = _dump(bundle.legal_authority_report)

    assert records == []
    assert bundle.norm_candidate_bindings
    assert report["legal_authority_record_refs"] == []
    assert report["selected_norm_refs"] == []
    assert "layer3_gl_norm_temporal_window_missing" in report["blocker_refs"]
    assert "legal_authority_no_candidate_norm" in report["blocker_refs"]


def test_layer3_gl_task4_l5_calibration_limitation_is_explicit_for_passing_records() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    bindings = [_dump(binding) for binding in bundle.l5_calibration_bindings]

    assert bindings == []
    assert bundle.norm_candidate_bindings
    assert _dump(bundle.legal_authority_report)["selected_norm_refs"] == []


def test_layer3_gl_task4_temporal_amendment_and_reference_records_fail_closed_when_needed() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    temporal_records = [_dump(record) for record in bundle.temporal_competence_records]
    amendment_records = [_dump(record) for record in bundle.amendment_lineage_records]
    reference_records = [_dump(record) for record in bundle.reference_resolution_records]

    assert not any(record["status"] == "pass" for record in temporal_records)
    assert any(record["status"] == "reissue_required" for record in temporal_records)
    assert any(
        "layer3_gl_partial_temporal_row_promoted_to_authority" in record["issue_codes"]
        for record in temporal_records
    )
    assert amendment_records
    assert amendment_records[0]["amendment_id"]
    assert amendment_records[0]["lineage_status"] in {"pass", "reissue_required"}
    assert amendment_records[0]["query_trace_refs"]
    assert reference_records
    assert reference_records[0]["reference_edge_id"]
    assert reference_records[0]["resolution_audit_row_ref"]
    assert reference_records[0]["resolution_status"]
    assert reference_records[0]["query_trace_refs"]


def test_layer3_gl_task4_temporal_partial_cannot_be_promoted_to_authority() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["temporal_competence_records"] = [
            {
                "record_id": "gl-temporal:test",
                "status": "pass",
                "temporal_resolution_status": "partial",
                "claim_implementation_window": {"start": "2022-03-01", "end": "2022-12-31"},
                "legal_effective_window": {"start": "", "end": ""},
                "legal_as_of": "2022-03-01",
            }
        ]

    _validate_mutation(
        mutate,
        {"layer3_gl_partial_temporal_row_promoted_to_authority"},
    )


def test_layer3_gl_task5_lex_intervention_map_binding_has_authority_precondition() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    bindings = [_dump(binding) for binding in bundle.lex_intervention_map_bindings]

    assert bindings == []
    assert bundle.norm_candidate_bindings
    assert _dump(bundle.legal_authority_report)["selected_norm_refs"] == []


def test_layer3_gl_intervention_map_refuses_malformed_supplied_registry() -> None:
    gl = _gl()

    with pytest.raises(TypeError, match="LexProvisionMappingRegistry"):
        gl.build_gl_lex_intervention_map_bindings(
            REPO_ROOT,
            mapping_registry=object(),
        )


def test_layer3_gl_task5_zero_row_production_map_reports_bounded_mapping_coverage() -> None:
    from polisyos.lex import LexProvisionMappingRegistry

    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)

    bindings = [
        _dump(binding)
        for binding in gl.build_gl_lex_intervention_map_bindings(
            REPO_ROOT,
            legal_authority_report=bundle.legal_authority_report,
            norm_candidate_bindings=bundle.norm_candidate_bindings,
            threshold_authority_records=bundle.threshold_authority_records,
            mapping_registry=LexProvisionMappingRegistry(),
            production_mapping_row_count=0,
        )
    ]

    assert bindings == []
    assert bundle.norm_candidate_bindings
    assert _dump(bundle.legal_authority_report)["legal_authority_record_refs"] == []


def test_layer3_gl_task5_intervention_map_without_authority_record_fails_precondition() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["lex_intervention_map_bindings"] = [
            {
                "binding_id": "gl-map-binding:test",
                "status": "pass",
                "mapping_ref": "lex-intervention-map://test",
                "provision_ref": "lex_rule_thresholds:test",
                "legal_authority_record_refs": [],
                "admitted_authority_precondition_status": "missing",
                "used_as_legal_authority": False,
                "executable_compile_status": "out_of_scope",
            }
        ]

    _validate_mutation(mutate, {"layer3_gl_lex_intervention_map_missing"})


def test_layer3_gl_task5_bundle_build_does_not_compile_lex_interventions() -> None:
    script = """
import sys
from pathlib import Path
from polisyos.runtime.quality.proving_ground import legal_mandate_search as gl
root = Path("/Users/deniskopylov/polisyos/policy-engine")
gl.build_layer3_gl_bundle(root)
if "polisyos.lex.interventions" in sys.modules:
    raise SystemExit("polisyos.lex.interventions")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_layer3_gl_task6_claim_and_semantic_consumer_gates_preserve_authority_refs() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    report = _dump(bundle.legal_authority_report)
    claim_gate = _dump(bundle.claim_registry_consumer_gate)
    semantic_gate = _dump(bundle.semantic_binding_consumer_gate)

    assert claim_gate["status"] == "fail"
    assert claim_gate["claim_registry_status"] == "fail"
    assert claim_gate["claim_registry_rows"]
    claim_row = claim_gate["claim_registry_rows"][0]
    assert claim_row["claim_id"] == report["claim_id"]
    assert claim_row["selected_norm_refs"] == []
    assert claim_row["legal_norm_refs"] == []
    assert claim_row["legal_authority_blocker_refs"]
    assert claim_row["threshold_record_refs"] == []
    assert claim_row["mandate_record_refs"] == []
    assert claim_row["authority_role"] == "consumer_projection"
    assert "legal_authority" not in claim_row["authoritative_for"]
    assert "legal_authority_without_claim_level_adapter" in claim_row["may_not_use_for"]
    assert claim_gate["producer_authority_refs"] == []
    assert "legal_source_relation_verification_not_established" in claim_gate["issue_codes"]

    assert semantic_gate["status"] == "fail"
    assert semantic_gate["semantic_binding_status"] == "fail"
    assert semantic_gate["semantic_binding_rows"]
    semantic_row = semantic_gate["semantic_binding_rows"][0]
    assert semantic_row["selected_norm_refs"] == []
    assert semantic_row["legal_authority_record_refs"] == []
    assert semantic_row["legal_admissibility_grades"] == []
    assert "layer3_gl_semantic_binding_consumer_gate_missing" in semantic_gate["issue_codes"]
    assert "legal_source_relation_verification_not_established" not in semantic_gate["issue_codes"]
    semantic_input = gl._gl_lex_semantic_report(report)
    relation_blocker = next(
        row
        for row in semantic_input["authority_blockers"]
        if row["code"] == "legal_source_relation_verification_not_established"
    )
    source_window_blocker = next(
        row
        for row in semantic_input["authority_blockers"]
        if row["code"] == "layer3_gl_norm_temporal_window_missing"
    )
    assert relation_blocker["status"] == "verification_missing"
    assert source_window_blocker["severity"] == "fail"
    assert "status" not in source_window_blocker


def test_layer3_gl_task6_argument_graph_s6_s7_s8_handoffs_preserve_authority_boundaries() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    report = _dump(bundle.legal_authority_report)
    argument_gate = _dump(bundle.argument_graph_readiness_consumer_gate)
    assert argument_gate["status"] == "fail"
    assert argument_gate["diagnostic_only"] is True
    readiness = argument_gate["readiness_rows"][0]
    assert readiness["readiness_check"] == "layer3_gl_legal_mandate_search_readiness_gate"
    assert readiness["status"] == "fail"
    assert not report["legal_authority_record_refs"]
    assert not report["selected_norm_refs"]
    assert "layer3_gl_authority_facet_binding_semantic_loss" in readiness["blocker_refs"]
    assert "layer3_gl_norm_temporal_window_missing" in readiness["blocker_refs"]
    assert "legal_source_relation_verification_not_established" not in readiness["blocker_refs"]
    assert argument_gate["claims_promotion_authority"] is False

    s6_gate = _dump(bundle.s6_mandate_consumer_gate)
    assert s6_gate["status"] == "fail"
    assert s6_gate["s6_gate_disposition"] == "compatibility_only"
    assert s6_gate["does_not_assert_s6_pass"] is True
    assert s6_gate["s6_mandate_source_records"] == []
    assert s6_gate["s6_evaluation_ref"] is None

    s7_gate = _dump(bundle.s7_delegation_consumer_gate)
    assert s7_gate["status"] == "fail"
    assert s7_gate["mandate_record_refs"] == []
    assert s7_gate["human_decision_integrity_authority"] == "s7_not_gl"
    assert s7_gate["p26_boundary_preserved"] is True

    s8_gate = _dump(bundle.s8_value_choice_consumer_gate)
    assert s8_gate["status"] == "out_of_scope"
    assert s8_gate["value_choice_scope"] == "non_ranking_gl_closure"
    assert s8_gate["ranking_authorized"] is False
    assert s8_gate["requires_s6_mandate_pass_for_ranking"] is True


def test_layer3_gl_task6_pdc_design_g4_and_public_projection_do_not_overclaim() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    pdc_gate = _dump(bundle.pdc_compiler_consumer_gate)
    assert pdc_gate["status"] == "fail"
    assert pdc_gate["compatible_with_pdc_input"] is False
    assert pdc_gate["pdc_input_refs"]
    assert pdc_gate["legal_authority_record_refs"] == []
    assert pdc_gate["selected_norm_refs"] == []

    design_gate = _dump(bundle.design_constraint_consumer_gate)
    assert design_gate["status"] == "fail"
    assert design_gate["consumed_as_recommendation_substance"] is False
    assert design_gate["consumed_as_promotion_authority"] is False
    assert design_gate["design_constraint_rows"][0]["source_refs"] == []
    assert design_gate["design_constraint_rows"][0]["legal_authority_record_refs"] == []

    g4_gate = _dump(bundle.g4_promotion_gate_consumer_gate)
    assert g4_gate["status"] == "fail"
    assert g4_gate["promotion_authority_claimed"] is False
    assert g4_gate["closeout_authority_claimed"] is False
    assert g4_gate["future_g4_required_refs"]

    handoff = _dump(bundle.promotion_gate_handoff)
    assert handoff["status"] == "reference_only"
    assert handoff["promotion_authority_claimed"] is False
    assert handoff["handoff_refs"]

    audit_surface = _dump(bundle.legal_mandate_audit_surface)
    assert audit_surface["status"] == "pass"
    assert audit_surface["surface_audiences"] == ["EXPERT", "MACHINE"]
    assert audit_surface["raw_legal_payload_exported"] is False
    assert audit_surface["audit_refs"]["legal_authority_record_refs"] == []

    public_refs = _dump(bundle.public_export_projection_refs)
    assert public_refs["status"] == "pass"
    assert public_refs["projection_mode"] == "reference_only"
    assert public_refs["public_export_hook_status"] == "out_of_scope_reference_only"
    assert public_refs["raw_legal_payload_exported"] is False
    assert public_refs["projection_refs"]["legal_authority_record_refs"] == []
    assert public_refs["projection_policy_ref"]
    assert public_refs["public_payload_fields"] == [
        "surface_id",
        "projection_mode",
        "safe_disclosure_status",
        "projection_refs",
    ]
    assert not set(public_refs) & {
        "raw_legal_rows",
        "source_quotes",
        "provision_text",
        "query_ledgers",
        "unredacted_authority_payloads",
    }


def test_layer3_gl_task6_validator_fails_claim_or_semantic_consumer_gate_ref_loss() -> None:
    gl = _gl()
    payload = _mutable_gl_runtime_payload()
    report = payload["legal_authority_report"]
    report["selected_norm_refs"] = ["norm.unverified.test"]
    report["legal_authority_record_refs"] = ["legal-authority-record:unverified.test"]
    report["blocker_refs"] = list(
        dict.fromkeys(
            [
                *report.get("blocker_refs", []),
                "legal_source_relation_verification_not_established",
            ]
        )
    )
    report["issue_codes"] = list(
        dict.fromkeys(
            [
                *report.get("issue_codes", []),
                "legal_source_relation_verification_not_established",
            ]
        )
    )
    claim_gate = payload["claim_registry_consumer_gate"]
    claim_gate["status"] = "pass"
    claim_gate["selected_norm_refs"] = ["norm.unverified.test"]
    claim_gate["legal_authority_record_refs"] = ["legal-authority-record:unverified.test"]
    claim_gate["claim_registry_rows"] = [
        {"selected_norm_refs": [], "legal_authority_record_refs": []}
    ]
    semantic_gate = payload["semantic_binding_consumer_gate"]
    semantic_gate["status"] = "pass"
    semantic_gate["selected_norm_refs"] = ["norm.unverified.test"]
    semantic_gate["legal_authority_record_refs"] = ["legal-authority-record:unverified.test"]
    semantic_gate["semantic_binding_rows"] = [
        {"selected_norm_refs": [], "legal_authority_record_refs": []}
    ]

    report_result = gl.validate_layer3_gl_bundle(REPO_ROOT, payload)
    issues = _issue_codes(report_result)

    assert _dump(report_result)["status"] == "fail"
    assert "legal_source_relation_verification_not_established" in issues
    assert "layer3_gl_claim_registry_consumer_gate_missing" in issues
    assert "layer3_gl_semantic_binding_consumer_gate_missing" in issues


def test_layer3_gl_task6_validator_blocks_ranking_or_public_projection_overclaim() -> None:
    def mutate_ranking(payload: dict[str, Any]) -> None:
        payload["s8_value_choice_consumer_gate"]["status"] = "pass"
        payload["s8_value_choice_consumer_gate"]["ranking_authorized"] = True
        payload["s6_mandate_consumer_gate"]["s6_gate_disposition"] = "compatibility_only"

    _validate_mutation(
        mutate_ranking,
        {"layer3_gl_s8_ranking_authorized_without_mandate_pass"},
    )

    def mutate_public_projection(payload: dict[str, Any]) -> None:
        payload["public_export_projection_refs"]["raw_legal_payload_exported"] = True
        payload["public_export_projection_refs"]["raw_legal_rows"] = [{"text": "raw"}]

    _validate_mutation(
        mutate_public_projection,
        {"layer3_gl_public_raw_legal_payload_leak"},
    )


def test_layer3_gl_import_does_not_eagerly_import_heavy_intervention_or_research_modules() -> None:
    script = """
import sys
import polisyos.runtime.quality  # noqa: F401
before = set(sys.modules)
import polisyos.runtime.quality.proving_ground.legal_mandate_search  # noqa: F401
loaded = set(sys.modules) - before
forbidden = (
    "polisyos.lex.interventions",
    "polisyos.foundry",
    "polisyos.scientist",
)
violations = sorted(
    name for name in loaded if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
)
if violations:
    raise SystemExit("\\n".join(violations))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_layer3_gl_validator_fails_search_ledger_without_legal_authority_record() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["legal_authority_report"]["selected_norm_refs"] = ["lex-norm://selected"]
        payload["legal_authority_report"]["legal_authority_record_refs"] = []
        payload["threshold_authority_records"] = []
        payload["mandate_authority_records"] = []
        payload["readiness_manifest"]["gl_legal_authority_record_count"] = 0

    _validate_mutation(mutate, {"layer3_gl_selected_norm_without_legal_authority_record"})


def test_layer3_gl_validator_fails_legal_authority_report_without_consumer_gates() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["legal_authority_report"]["status"] = "pass"
        payload["legal_authority_report"]["selected_norm_refs"] = ["lex-norm://unverified-test"]
        payload["legal_authority_report"]["legal_authority_record_refs"] = [
            "legal-authority-record://gl/test"
        ]
        payload["claim_registry_consumer_gate"] = {"status": "missing"}
        payload["semantic_binding_consumer_gate"] = {"status": "missing"}

    _validate_mutation(
        mutate,
        {
            "layer3_gl_claim_registry_consumer_gate_missing",
            "layer3_gl_semantic_binding_consumer_gate_missing",
        },
    )


def test_layer3_gl_validator_fails_when_lex_intervention_map_is_used_as_authority() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["lex_intervention_map_bindings"] = [
            {
                "binding_id": "gl-map-binding:test",
                "status": "admitted_authority",
                "mapping_ref": "lex-intervention-map://test",
                "legal_authority_record_refs": [],
                "authoritative_for": ["legal_authority"],
                "used_as_legal_authority": True,
            }
        ]

    _validate_mutation(mutate, {"layer3_gl_lex_intervention_map_used_as_authority"})


def test_layer3_gl_validator_fails_threshold_from_fact_summary_or_thresholds_json() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["threshold_authority_records"] = [
            {
                "record_id": "gl-threshold:test",
                "status": "admissible",
                "threshold_row_ref": "lex_normative_ready_facts:row-1",
                "hydrated_from_table": "lex_normative_ready_facts",
                "threshold_source_field": "thresholds_json",
                "metric": "interest_rate",
                "operator": None,
                "value_decimal": None,
                "unit": None,
            }
        ]

    _validate_mutation(
        mutate,
        {
            "layer3_gl_threshold_row_not_hydrated",
            "layer3_gl_thresholds_json_used_as_authority",
            "layer3_gl_threshold_unit_or_operator_unparsed",
        },
    )


def test_layer3_gl_validator_fails_kg_authority_facets_assumed_without_binding() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["authority_facet_bindings"] = []
        payload["norm_candidate_bindings"] = [
            {
                "binding_id": "gl-norm-candidate:test",
                "status": "admissible",
                "kg_row_ref": "lex_normative_ready_facts:row-1",
                "authority_facets_source": "kg_native_assumed",
                "authority_facet_binding_refs": [],
            }
        ]

    _validate_mutation(
        mutate,
        {
            "layer3_gl_authority_facet_binding_missing",
            "layer3_gl_kg_authority_facets_assumed_present",
        },
    )


def test_layer3_gl_validator_fails_compiler_default_authority_type_laundering() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["legal_requirement_bindings"] = [
            {
                "binding_id": "gl-legal-requirement:test",
                "status": "pass",
                "authority_types": ["implementing"],
                "authority_type_source": "compiler_default",
                "compiler_default_marked": False,
            }
        ]
        payload["authority_facet_bindings"] = [
            {
                "binding_id": "gl-authority-facet:test",
                "facet_name": "authority_types",
                "facet_value": ["implementing"],
                "facet_source": "lex_discovered",
                "source_row_refs": ["lex_normative_ready_facts:row-1"],
                "derived_from_compiler_default": True,
                "validation_status": "pass",
            }
        ]

    _validate_mutation(
        mutate,
        {
            "layer3_gl_compiler_default_authority_type_unmarked",
            "layer3_gl_compiler_default_authority_type_laundered",
        },
    )


def test_layer3_gl_validator_fails_internal_requirement_compile_or_derived_producer_ref() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["legal_authority_report"] = {
            "status": "pass",
            "selected_norm_refs": ["lex-norm://selected"],
            "legal_authority_record_refs": ["legal-authority-record://gl/test"],
            "used_internal_requirement_compile": True,
            "producer_artifact_ref": "derived://legal-authority/stable-ref",
            "explicit_gl_requirement_spec_refs": [],
        }

    _validate_mutation(
        mutate,
        {
            "layer3_gl_internal_requirement_compile_used_for_closure",
            "layer3_gl_legal_authority_report_missing_gl_producer_artifact_ref",
        },
    )


def test_layer3_gl_validator_fails_inline_runtime_candidate_norms_for_closure() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["legal_authority_report"]["candidate_source"] = "runtime_candidate_norms"
        payload["legal_authority_report"]["runtime_candidate_norms_used_for_closure"] = True
        payload["norm_candidate_bindings"] = []

    _validate_mutation(
        mutate,
        {
            "layer3_gl_runtime_candidate_norm_snapshot_used_for_closure",
            "layer3_gl_norm_candidate_binding_missing",
        },
    )


def test_layer3_gl_validator_fails_s6_mandate_pass_without_s6_handoff() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["mandate_authority_records"] = [
            {
                "record_id": "gl-mandate:test",
                "status": "admissible",
                "mandate_record_ref": "mandate://gl/test",
                "mandate_source_refs": [],
                "s6_mandate_firewall_disposition": "pass",
                "s6_evaluation_ref": None,
                "s6_compatible_source_handoff_refs": [],
            }
        ]
        payload["s6_mandate_consumer_gate"] = {"status": "pass", "s6_evaluation_ref": None}

    _validate_mutation(
        mutate,
        {
            "layer3_gl_mandate_source_refs_missing",
            "layer3_gl_s6_mandate_semantics_forked",
        },
    )


# R2 typed facet-origin boundary cases.


def _r2_facet_subject(
    gl: Any,
    candidate_kind: str,
) -> tuple[Any, Mapping[str, Any], str, str, list[Any], Any]:
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    row = (
        gl._threshold_candidate_row(bundle.l3_legal_kg_search_ledgers)
        if candidate_kind == "threshold"
        else gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
    )
    assert row is not None
    row_ref = str(row.get("row_ref") or "")
    binding_ref = f"gl-norm-candidate:{gl._stable_id(row_ref)}"
    hierarchy = next(
        facet
        for facet in bundle.authority_facet_bindings
        if facet.candidate_binding_ref == binding_ref and facet.facet_name == "hierarchy"
    )
    return bundle, row, row_ref, binding_ref, list(bundle.authority_facet_bindings), hierarchy


def _r2_selected_binding(
    gl: Any,
    bundle: Any,
    row_ref: str,
    facets: list[Any],
) -> Any:
    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=bundle.l3_legal_kg_search_ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=facets,
    )
    return next(binding for binding in bindings if binding.kg_row_ref == row_ref)


@pytest.mark.parametrize("candidate_kind", ["context", "threshold"])
@pytest.mark.parametrize(
    "identity_case",
    ["foreign_row", "wrong_binding", "missing_binding", "malformed_source_rows"],
)
def test_layer3_gl_public_builder_blocks_facet_origin_mismatch(
    candidate_kind: str,
    identity_case: str,
) -> None:
    gl = _gl()
    bundle, _row, row_ref, _binding_ref, facets, hierarchy = _r2_facet_subject(gl, candidate_kind)
    if identity_case == "foreign_row":
        update = {
            "kg_row_ref": "lex_normative_facts:foreign-row",
            "source_row_refs": ("lex_normative_facts:foreign-row",),
            "facet_value": {"authority_level": "foreign-row", "hierarchy_depth": 0},
        }
    elif identity_case == "wrong_binding":
        update = {"candidate_binding_ref": "gl-norm-candidate:foreign-binding"}
    elif identity_case == "missing_binding":
        update = {"candidate_binding_ref": None}
    else:
        update = {"source_row_refs": None}
    mutated = [
        facet.model_copy(update=update) if facet.binding_id == hierarchy.binding_id else facet
        for facet in facets
    ]

    selected = _r2_selected_binding(gl, bundle, row_ref, mutated)

    assert selected.status == "blocked"
    assert selected.candidate_norm_status == "blocked"
    assert selected.context_only is True
    assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes
    assert selected.candidate_norm == {}


@pytest.mark.parametrize("candidate_kind", ["context", "threshold"])
@pytest.mark.parametrize(
    "malformed_value",
    [["malformed"], {"authority_level": 17}, {"hierarchy_depth": "two"}],
)
def test_layer3_gl_public_builder_returns_typed_issue_for_malformed_present_facet(
    candidate_kind: str,
    malformed_value: object,
) -> None:
    gl = _gl()
    bundle, _row, row_ref, _binding_ref, facets, hierarchy = _r2_facet_subject(gl, candidate_kind)
    malformed = [
        facet.model_copy(update={"facet_value": malformed_value})
        if facet.binding_id == hierarchy.binding_id
        else facet
        for facet in facets
    ]

    selected = _r2_selected_binding(gl, bundle, row_ref, malformed)

    assert selected.status == "blocked"
    assert selected.candidate_norm_status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes


@pytest.mark.parametrize("candidate_kind", ["context", "threshold"])
@pytest.mark.parametrize(
    "facet_name",
    [
        "hierarchy",
        "source_authority",
        "competent_actor_ref",
        "instrument_types",
        "conflict_supersession_preemption",
    ],
)
def test_layer3_gl_origin_admission_covers_the_complete_facet_quantity(
    candidate_kind: str,
    facet_name: str,
) -> None:
    gl = _gl()
    bundle, _row, row_ref, binding_ref, facets, _hierarchy = _r2_facet_subject(gl, candidate_kind)
    selected_facet = next(
        facet
        for facet in facets
        if facet.candidate_binding_ref == binding_ref and facet.facet_name == facet_name
    )
    foreign_values: dict[str, Any] = {
        "hierarchy": {"authority_level": "foreign-row", "hierarchy_depth": 0},
        "source_authority": "lex_doc_metadata:foreign-row",
        "competent_actor_ref": "foreign_actor",
        "instrument_types": ("foreign_instrument",),
        "conflict_supersession_preemption": {
            "conflict_state": "contested",
            "supersession_state": "superseded",
            "preemption_state": "preempted",
        },
    }
    mutated = [
        facet.model_copy(
            update={
                "kg_row_ref": "lex_normative_facts:foreign-row",
                "source_row_refs": ("lex_normative_facts:foreign-row",),
                "facet_value": foreign_values[facet_name],
            }
        )
        if facet.binding_id == selected_facet.binding_id
        else facet
        for facet in facets
    ]

    selected = _r2_selected_binding(gl, bundle, row_ref, mutated)

    assert selected.status == "blocked"
    assert selected.candidate_norm_status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes


def test_layer3_gl_candidate_subject_mismatch_blocks_facet_projection() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    candidate = gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert candidate is not None
    row_ref = str(candidate.get("row_ref") or "")
    owner_index = next(
        index
        for index, ledger in enumerate(bundle.l3_legal_kg_search_ledgers)
        if any(row.get("row_ref") == row_ref for row in ledger.candidate_rows)
    )
    ledgers = list(bundle.l3_legal_kg_search_ledgers)
    ledgers[owner_index] = ledgers[owner_index].model_copy(
        update={"claim_id": "claim:foreign-subject"}
    )

    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=tuple(ledgers),
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=bundle.authority_facet_bindings,
    )
    selected = next(binding for binding in bindings if binding.kg_row_ref == row_ref)

    assert selected.status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes


def test_layer3_gl_present_none_is_not_converted_to_facet_absence() -> None:
    gl = _gl()
    bundle, _row, row_ref, _binding_ref, facets, hierarchy = _r2_facet_subject(gl, "threshold")
    mutated = [
        facet.model_copy(update={"facet_value": None})
        if facet.binding_id == hierarchy.binding_id
        else facet
        for facet in facets
    ]

    selected = _r2_selected_binding(gl, bundle, row_ref, mutated)

    assert selected.status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes


def test_layer3_gl_declared_missing_facet_uses_existing_missing_issue() -> None:
    gl = _gl()
    bundle, _row, row_ref, _binding_ref, facets, hierarchy = _r2_facet_subject(gl, "threshold")
    mutated = [
        facet.model_copy(
            update={
                "facet_value": None,
                "facet_status": "missing",
                "facet_source": "missing",
                "validation_status": "blocked",
                "semantic_loss_status": "missing_required_facet",
            }
        )
        if facet.binding_id == hierarchy.binding_id
        else facet
        for facet in facets
    ]

    selected = _r2_selected_binding(gl, bundle, row_ref, mutated)

    assert selected.status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_missing" in selected.issue_codes


def test_layer3_gl_sibling_facet_row_does_not_change_selected_candidate() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, owner_facets, _baseline_bindings = _r3_complete_context_inputs(gl, bundle)
    candidate = gl._primary_norm_candidate_row(ledgers)
    assert candidate is not None
    row_ref = str(candidate.get("row_ref") or "")
    owner_index = next(
        index
        for index, ledger in enumerate(ledgers)
        if any(row.get("row_ref") == row_ref for row in ledger.candidate_rows)
    )
    sibling_row_ref = "lex_normative_ready_facts:sibling-row"
    sibling_binding_ref = f"gl-norm-candidate:{gl._stable_id(sibling_row_ref)}"
    sibling = dict(candidate)
    sibling["row_ref"] = sibling_row_ref
    sibling["candidate_path"] = "other_candidate"
    ledgers = list(ledgers)
    ledgers[owner_index] = ledgers[owner_index].model_copy(
        update={
            "candidate_rows": (*ledgers[owner_index].candidate_rows, sibling),
            "owner_frontier": None,
        }
    )
    sibling_facet = gl._facet_binding(
        binding_ref=sibling_binding_ref,
        row_ref=sibling_row_ref,
        source_table=str(candidate.get("source_table") or ""),
        facet_name="hierarchy",
        facet_value={"authority_level": "sibling-row", "hierarchy_depth": 0},
        facet_source="governed_config",
        facet_status="present",
        source_column_refs=(),
        source_row_refs=(sibling_row_ref,),
        derivation_rule_ref="governed-config:test-sibling-hierarchy.v1",
        validation_status="pass",
        semantic_loss_status="governed_config_only",
    )

    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=tuple(ledgers),
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=(*owner_facets, sibling_facet),
    )
    selected = next(binding for binding in bindings if binding.kg_row_ref == row_ref)

    assert selected.status == "context_only"
    assert selected.candidate_norm["authority_level"] == "national"
    assert selected.candidate_norm["hierarchy_depth"] == 2


def test_layer3_gl_fallback_candidate_row_keeps_its_existing_projection_path() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    candidate = gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert candidate is not None
    row_ref = str(candidate.get("row_ref") or "")
    owner = next(
        ledger
        for ledger in bundle.l3_legal_kg_search_ledgers
        if any(row.get("row_ref") == row_ref for row in ledger.candidate_rows)
    )
    fallback_row = dict(candidate)
    fallback_row["candidate_path"] = "unclassified_fallback_candidate"
    fallback_row["effective_from"] = "2001-01-01"
    fallback_row["effective_to"] = "2099-12-31"
    fallback_ledger = owner.model_copy(
        update={"candidate_rows": (fallback_row,), "owner_frontier": None}
    )
    ledgers = (fallback_ledger,)
    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
    )

    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=facets,
    )

    assert len(bindings) == 1
    assert bindings[0].kg_row_ref == row_ref
    assert bindings[0].status == "context_only"
    assert bindings[0].candidate_norm_status == "context_only"
    assert not bindings[0].issue_codes


def test_layer3_gl_candidate_facet_refusal_reaches_validator_and_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    threshold = gl._threshold_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert threshold is not None
    threshold_ref = str(threshold.get("row_ref") or "")
    threshold_binding_ref = f"gl-norm-candidate:{gl._stable_id(threshold_ref)}"
    hierarchy = next(
        facet
        for facet in bundle.authority_facet_bindings
        if facet.candidate_binding_ref == threshold_binding_ref and facet.facet_name == "hierarchy"
    )
    mutated = tuple(
        facet.model_copy(
            update={
                "kg_row_ref": "lex_normative_facts:foreign-row",
                "source_row_refs": ("lex_normative_facts:foreign-row",),
                "facet_value": {"authority_level": "foreign-row", "hierarchy_depth": 0},
            }
        )
        if facet.binding_id == hierarchy.binding_id
        else facet
        for facet in bundle.authority_facet_bindings
    )
    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=bundle.l3_legal_kg_search_ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=mutated,
    )
    invalid_bundle = bundle.model_copy(
        update={"authority_facet_bindings": mutated, "norm_candidate_bindings": bindings}
    )

    validation = gl.validate_layer3_gl_bundle(REPO_ROOT, invalid_bundle)

    assert any(
        issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
        for issue in validation.issues
    )
    from polisyos import lex

    captured_authority: list[Mapping[str, Any]] = []
    captured_applicability: list[Mapping[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        captured_authority.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        captured_applicability.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)
    report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=bundle.l3_legal_kg_search_ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=mutated,
        norm_candidate_bindings=bindings,
    )

    assert report.adapter_candidate_norm_count == 0
    assert not captured_authority
    assert not captured_applicability
    assert all(norm.get("source_provenance_ref") != threshold_ref for norm in captured_authority)
    assert all(
        norm.get("source_provenance_ref") != threshold_ref for norm in captured_applicability
    )
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report.issue_codes


@pytest.mark.parametrize("candidate_kind", ["context", "threshold"])
@pytest.mark.parametrize(
    ("facet_name", "malformed_value"),
    [("source_authority", ["wrong-shape"]), ("instrument_types", "resolution")],
)
def test_layer3_gl_public_builder_refuses_malformed_scalar_and_sequence_facets(
    candidate_kind: str,
    facet_name: str,
    malformed_value: object,
) -> None:
    gl = _gl()
    bundle, _row, row_ref, binding_ref, facets, _hierarchy = _r2_facet_subject(gl, candidate_kind)
    selected_facet = next(
        facet
        for facet in facets
        if facet.candidate_binding_ref == binding_ref and facet.facet_name == facet_name
    )
    mutated = [
        facet.model_copy(update={"facet_value": malformed_value})
        if facet.binding_id == selected_facet.binding_id
        else facet
        for facet in facets
    ]

    selected = _r2_selected_binding(gl, bundle, row_ref, mutated)

    assert selected.status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes


def test_layer3_gl_candidates_with_unbound_source_windows_are_refused() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    assert len(bundle.norm_candidate_bindings) == 2

    for binding in bundle.norm_candidate_bindings:
        assert binding.status == "blocked"
        assert binding.candidate_norm_status == "blocked"
        assert binding.context_only is True
        assert binding.candidate_norm == {}
        if binding.source_table == "lex_normative_ready_facts":
            assert "layer3_gl_authority_facet_binding_semantic_loss" in binding.issue_codes
        else:
            assert binding.source_table == "lex_rule_thresholds"
            assert "layer3_gl_norm_temporal_window_missing" in binding.issue_codes


# R3 whole-owner-basis controls.

_GL_PLAN_REQUIRED_FACETS = (
    "authority_types",
    "competent_actor_ref",
    "instrument_types",
    "implementation_authority_ref",
    "fiscal_authority_ref",
    "source_authority",
    "hierarchy",
    "conflict_supersession_preemption",
    "fallback",
    "legal_effective_window",
)


def _r3_ledgers_with_explicit_primary_window(gl: Any, bundle: Any) -> tuple[Any, ...]:
    """Use explicit temporal source columns only in an isolated boundary fixture."""

    candidate = gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert candidate is not None
    row_ref = candidate.get("row_ref")
    result = []
    for ledger in bundle.l3_legal_kg_search_ledgers:
        rows = []
        changed = False
        for row in ledger.candidate_rows:
            if row.get("row_ref") == row_ref:
                rows.append(
                    {
                        **row,
                        "effective_from": "2001-01-01",
                        "effective_to": "2099-12-31",
                    }
                )
                changed = True
            else:
                rows.append(row)
        result.append(
            ledger.model_copy(
                update={
                    "candidate_rows": tuple(rows),
                    "owner_frontier": None,
                }
            )
            if changed
            else ledger
        )
    return tuple(result)


def _r3_complete_context_inputs(
    gl: Any, bundle: Any
) -> tuple[Any, tuple[Any, ...], tuple[Any, ...]]:
    ledgers = _r3_ledgers_with_explicit_primary_window(gl, bundle)
    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
    )
    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=facets,
    )
    return ledgers, facets, bindings


def test_layer3_gl_producer_emits_owner_defined_membership_for_each_subject() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    assert gl._GL_REQUIRED_AUTHORITY_FACET_NAMES == _GL_PLAN_REQUIRED_FACETS

    for candidate_kind in ("context", "threshold"):
        row = (
            gl._threshold_candidate_row(bundle.l3_legal_kg_search_ledgers)
            if candidate_kind == "threshold"
            else gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
        )
        assert row is not None
        row_ref = row["row_ref"]
        binding_ref = f"gl-norm-candidate:{gl._stable_id(row_ref)}"
        subject_facets = tuple(
            facet
            for facet in bundle.authority_facet_bindings
            if facet.candidate_binding_ref == binding_ref
        )

        assert {facet.facet_name for facet in subject_facets} == set(_GL_PLAN_REQUIRED_FACETS)
        assert len(subject_facets) == len(_GL_PLAN_REQUIRED_FACETS)
        assert all(facet.kg_row_ref == row_ref for facet in subject_facets)
        assert all(facet.source_row_refs == (row_ref,) for facet in subject_facets)
        assert all(facet.source_table == row["source_table"] for facet in subject_facets)

        temporal = next(
            facet for facet in subject_facets if facet.facet_name == "legal_effective_window"
        )
        if candidate_kind == "threshold":
            assert temporal.facet_status == "missing"
            assert temporal.facet_source == "missing"
            assert temporal.facet_value is None
            fallback = next(facet for facet in subject_facets if facet.facet_name == "fallback")
            assert fallback.facet_source == "governed_config"
            assert fallback.facet_value == bundle.legal_requirement_bindings[0].fallback_policy
        else:
            assert temporal.facet_status == "present"
            assert temporal.facet_source == "lex_explicit"
            assert temporal.validation_status == "blocked"
            assert temporal.semantic_loss_status == "incomplete_or_malformed_source_temporal_window"
            assert set(temporal.source_column_refs) >= {
                f"{row['source_table']}.effective_from",
                f"{row['source_table']}.effective_to",
            }


@pytest.mark.parametrize("facet_name", _GL_PLAN_REQUIRED_FACETS)
def test_layer3_gl_removing_any_required_member_blocks_only_its_subject(
    facet_name: str,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, complete_facets, complete_bindings = _r3_complete_context_inputs(gl, bundle)
    primary = gl._primary_norm_candidate_row(ledgers)
    assert primary is not None
    row_ref = primary["row_ref"]
    binding_ref = f"gl-norm-candidate:{gl._stable_id(row_ref)}"
    selected_facet = next(
        facet
        for facet in complete_facets
        if facet.candidate_binding_ref == binding_ref and facet.facet_name == facet_name
    )
    baseline_sibling = next(
        binding for binding in complete_bindings if binding.kg_row_ref != row_ref
    )

    missing = tuple(
        facet for facet in complete_facets if facet.binding_id != selected_facet.binding_id
    )
    after = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=missing,
    )
    selected = next(binding for binding in after if binding.kg_row_ref == row_ref)
    sibling = next(binding for binding in after if binding.kg_row_ref != row_ref)

    assert selected.status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_missing" in selected.issue_codes
    expected_specific_issue = {
        "source_authority": "layer3_gl_norm_source_authority_missing",
        "fallback": "layer3_gl_jurisdiction_fallback_policy_missing",
        "legal_effective_window": "layer3_gl_norm_temporal_window_missing",
    }.get(facet_name)
    if expected_specific_issue:
        assert expected_specific_issue in selected.issue_codes
    assert sibling.binding_id == baseline_sibling.binding_id
    assert sibling.authority_facet_binding_refs == baseline_sibling.authority_facet_binding_refs
    assert sibling.issue_codes == baseline_sibling.issue_codes


def test_layer3_gl_threshold_missing_source_authority_cannot_borrow_context_facet() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    threshold = gl._threshold_candidate_row(bundle.l3_legal_kg_search_ledgers)
    context = gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert threshold is not None
    assert context is not None
    threshold_ref = threshold["row_ref"]
    context_ref = context["row_ref"]
    threshold_binding_ref = f"gl-norm-candidate:{gl._stable_id(threshold_ref)}"

    mutated = tuple(
        facet
        for facet in bundle.authority_facet_bindings
        if not (
            facet.candidate_binding_ref == threshold_binding_ref
            and facet.facet_name == "source_authority"
        )
    )
    selected = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=bundle.l3_legal_kg_search_ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=mutated,
    )
    threshold_binding = next(item for item in selected if item.kg_row_ref == threshold_ref)
    context_binding = next(item for item in selected if item.kg_row_ref == context_ref)

    assert threshold_binding.status == "blocked"
    assert threshold_binding.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_missing" in threshold_binding.issue_codes
    assert "layer3_gl_norm_source_authority_missing" in threshold_binding.issue_codes
    assert context_binding.status == "blocked"
    assert "layer3_gl_norm_source_authority_missing" not in context_binding.issue_codes


def test_layer3_gl_validator_rechecks_membership_after_candidate_markers_remain() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, bindings = _r3_complete_context_inputs(gl, bundle)
    primary = gl._primary_norm_candidate_row(ledgers)
    assert primary is not None
    row_ref = primary["row_ref"]
    binding_ref = f"gl-norm-candidate:{gl._stable_id(row_ref)}"
    source_authority = next(
        facet
        for facet in facets
        if facet.candidate_binding_ref == binding_ref and facet.facet_name == "source_authority"
    )
    complete = bundle.model_copy(
        update={
            "l3_legal_kg_search_ledgers": ledgers,
            "authority_facet_bindings": facets,
            "norm_candidate_bindings": bindings,
        }
    )
    removed = complete.model_copy(
        update={
            "authority_facet_bindings": tuple(
                facet for facet in facets if facet.binding_id != source_authority.binding_id
            )
        }
    )

    report = gl.validate_layer3_gl_bundle(REPO_ROOT, removed)
    missing_paths = {
        issue.path
        for issue in report.issues
        if issue.code == "layer3_gl_norm_source_authority_missing"
    }

    assert any(path.startswith("$.norm_candidate_bindings[") for path in missing_paths)
    assert any(
        issue.code == "layer3_gl_authority_facet_binding_semantic_loss" for issue in report.issues
    )


def test_layer3_gl_present_null_and_valid_zero_remain_distinct() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, _bindings = _r3_complete_context_inputs(gl, bundle)
    primary = gl._primary_norm_candidate_row(ledgers)
    assert primary is not None
    row_ref = primary["row_ref"]
    binding_ref = f"gl-norm-candidate:{gl._stable_id(row_ref)}"
    hierarchy = next(
        facet
        for facet in facets
        if facet.candidate_binding_ref == binding_ref and facet.facet_name == "hierarchy"
    )

    present_null = tuple(
        facet.model_copy(update={"facet_value": {"authority_level": "", "hierarchy_depth": None}})
        if facet.binding_id == hierarchy.binding_id
        else facet
        for facet in facets
    )
    null_binding = next(
        item
        for item in gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=bundle.legal_requirement_bindings,
            authority_facet_bindings=present_null,
        )
        if item.kg_row_ref == row_ref
    )
    assert null_binding.status == "blocked"
    assert "layer3_gl_authority_facet_binding_semantic_loss" in null_binding.issue_codes
    assert "layer3_gl_authority_facet_binding_missing" not in null_binding.issue_codes

    valid_zero = tuple(
        facet.model_copy(update={"facet_value": {"authority_level": "", "hierarchy_depth": 0}})
        if facet.binding_id == hierarchy.binding_id
        else facet
        for facet in facets
    )
    zero_binding = next(
        item
        for item in gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=bundle.legal_requirement_bindings,
            authority_facet_bindings=valid_zero,
        )
        if item.kg_row_ref == row_ref
    )
    assert zero_binding.status == "context_only"
    assert not zero_binding.issue_codes
    assert zero_binding.candidate_norm["hierarchy_depth"] == 0


def test_layer3_gl_context_candidate_reaches_adapters_while_threshold_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, _facets, bindings = _r3_complete_context_inputs(gl, bundle)
    context = gl._primary_norm_candidate_row(ledgers)
    threshold = gl._threshold_candidate_row(ledgers)
    assert context is not None
    assert threshold is not None
    context_ref = context["row_ref"]
    threshold_ref = threshold["row_ref"]
    context_binding = next(item for item in bindings if item.kg_row_ref == context_ref)
    threshold_binding = next(item for item in bindings if item.kg_row_ref == threshold_ref)
    assert context_binding.status == "context_only"
    assert not context_binding.issue_codes
    assert threshold_binding.status == "blocked"
    assert "layer3_gl_norm_temporal_window_missing" in threshold_binding.issue_codes

    from polisyos import lex

    captured_authority: list[Mapping[str, Any]] = []
    captured_applicability: list[Mapping[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        captured_authority.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        captured_applicability.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)
    report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=_facets,
        norm_candidate_bindings=bindings,
    )

    assert report.adapter_candidate_norm_count == 1
    assert len(captured_authority) == 1
    assert len(captured_applicability) == 1
    assert captured_authority[0]["source_provenance_ref"] == context_ref
    assert captured_applicability[0]["source_provenance_ref"] == context_ref
    assert all(norm.get("source_provenance_ref") != threshold_ref for norm in captured_authority)
    assert all(
        norm.get("source_provenance_ref") != threshold_ref for norm in captured_applicability
    )
    assert "layer3_gl_norm_temporal_window_missing" in report.issue_codes


def test_layer3_gl_empty_facet_sequence_returns_subject_scoped_refusals() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=bundle.l3_legal_kg_search_ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=(),
    )

    assert len(bindings) == 2
    assert all(binding.status == "blocked" for binding in bindings)
    assert all(binding.candidate_norm == {} for binding in bindings)
    assert all(
        "layer3_gl_authority_facet_binding_missing" in binding.issue_codes for binding in bindings
    )
    expected_issues = {
        "layer3_gl_jurisdiction_fallback_policy_missing",
        "layer3_gl_norm_temporal_window_missing",
        "layer3_gl_norm_source_authority_missing",
    }
    assert all(expected_issues.issubset(set(binding.issue_codes)) for binding in bindings)


def test_layer3_gl_foreign_origin_control_covers_every_complete_member() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, _bindings = _r3_complete_context_inputs(gl, bundle)
    context = gl._primary_norm_candidate_row(ledgers)
    assert context is not None
    row_ref = context["row_ref"]
    binding_ref = f"gl-norm-candidate:{gl._stable_id(row_ref)}"
    context_facets = tuple(facet for facet in facets if facet.candidate_binding_ref == binding_ref)
    assert {facet.facet_name for facet in context_facets} == set(_GL_PLAN_REQUIRED_FACETS)
    assert len(context_facets) == len(_GL_PLAN_REQUIRED_FACETS)

    for facet in context_facets:
        mutated = tuple(
            item.model_copy(
                update={
                    "kg_row_ref": f"lex_normative_ready_facts:foreign-{facet.facet_name}",
                    "source_row_refs": (f"lex_normative_ready_facts:foreign-{facet.facet_name}",),
                }
            )
            if item.binding_id == facet.binding_id
            else item
            for item in facets
        )
        after = gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=bundle.legal_requirement_bindings,
            authority_facet_bindings=mutated,
        )
        selected = next(item for item in after if item.kg_row_ref == row_ref)

        assert selected.status == "blocked"
        assert selected.candidate_norm == {}
        assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes


def _r3_replace_candidate_row(
    ledgers: tuple[Any, ...],
    row_ref: str,
    *,
    updates: Mapping[str, object],
    remove_fields: tuple[str, ...] = (),
) -> tuple[Any, ...]:
    replaced = []
    for ledger in ledgers:
        rows = []
        changed = False
        for row in ledger.candidate_rows:
            if row.get("row_ref") != row_ref:
                rows.append(row)
                continue
            updated = dict(row)
            for field_name in remove_fields:
                updated.pop(field_name, None)
            updated.update(updates)
            rows.append(updated)
            changed = True
        replaced.append(
            ledger.model_copy(update={"candidate_rows": tuple(rows), "owner_frontier": None})
            if changed
            else ledger
        )
    return tuple(replaced)


@pytest.mark.parametrize(
    ("updates", "remove_fields"),
    [
        ({"effective_from": "", "effective_to": "2099-12-31"}, ()),
        ({"effective_from": None, "effective_to": "2099-12-31"}, ()),
        ({"effective_from": "2001-01-01"}, ("effective_to",)),
    ],
    ids=("blank-present", "null-present", "partial-window"),
)
def test_layer3_gl_malformed_present_window_is_not_absence_or_default(
    updates: Mapping[str, object],
    remove_fields: tuple[str, ...],
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    baseline = _r3_ledgers_with_explicit_primary_window(gl, bundle)
    primary = gl._primary_norm_candidate_row(baseline)
    assert primary is not None
    row_ref = primary["row_ref"]
    ledgers = _r3_replace_candidate_row(
        baseline,
        row_ref,
        updates=updates,
        remove_fields=remove_fields,
    )
    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
    )
    temporal = next(
        facet
        for facet in facets
        if facet.kg_row_ref == row_ref and facet.facet_name == "legal_effective_window"
    )
    assert temporal.facet_status == "present"
    assert temporal.validation_status == "blocked"
    assert temporal.semantic_loss_status == "incomplete_or_malformed_source_temporal_window"

    binding = next(
        item
        for item in gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=bundle.legal_requirement_bindings,
            authority_facet_bindings=facets,
        )
        if item.kg_row_ref == row_ref
    )
    assert binding.status == "blocked"
    assert binding.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in binding.issue_codes
    assert "layer3_gl_norm_temporal_window_missing" not in binding.issue_codes


@pytest.mark.parametrize(
    ("fallback_policy", "facet_status", "expected_issue"),
    [
        ({}, "missing", "layer3_gl_jurisdiction_fallback_policy_missing"),
        ({"config_ref": None}, "present", "layer3_gl_authority_facet_binding_semantic_loss"),
        ({"mode": "unknown"}, "present", "layer3_gl_authority_facet_binding_semantic_loss"),
    ],
    ids=("absent", "present-null", "present-without-reference"),
)
def test_layer3_gl_fallback_config_distinguishes_missing_from_malformed(
    fallback_policy: Mapping[str, object],
    facet_status: str,
    expected_issue: str,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    requirement = bundle.legal_requirement_bindings[0].model_copy(
        update={"fallback_policy": dict(fallback_policy)}
    )
    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=bundle.l3_legal_kg_search_ledgers,
        legal_requirement_bindings=(requirement,),
    )
    context = gl._primary_norm_candidate_row(bundle.l3_legal_kg_search_ledgers)
    assert context is not None
    row_ref = context["row_ref"]
    fallback = next(
        facet for facet in facets if facet.kg_row_ref == row_ref and facet.facet_name == "fallback"
    )
    assert fallback.facet_status == facet_status
    if facet_status == "present":
        assert fallback.validation_status == "blocked"
        assert fallback.facet_value == dict(fallback_policy)
    else:
        assert fallback.facet_source == "missing"
        assert fallback.facet_value is None

    candidate = next(
        item
        for item in gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=bundle.l3_legal_kg_search_ledgers,
            legal_requirement_bindings=(requirement,),
            authority_facet_bindings=facets,
        )
        if item.kg_row_ref == row_ref
    )
    assert candidate.status == "blocked"
    assert expected_issue in candidate.issue_codes


def test_layer3_gl_projection_uses_source_window_and_preserves_requirement_as_of() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers = _r3_ledgers_with_explicit_primary_window(gl, bundle)
    original = bundle.legal_requirement_bindings[0]
    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=(original,),
    )
    primary = gl._primary_norm_candidate_row(ledgers)
    assert primary is not None
    binding = next(
        item
        for item in gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=(original,),
            authority_facet_bindings=facets,
        )
        if item.kg_row_ref == primary["row_ref"]
    )

    assert binding.status == "context_only"
    assert binding.candidate_norm["effective_from"] == "2001-01-01"
    assert binding.candidate_norm["effective_to"] == "2099-12-31"
    assert binding.candidate_norm["legal_as_of"] == original.legal_as_of
    assert "2040-01-01" not in binding.candidate_norm["norm_version_ref"]


@pytest.mark.parametrize("mismatch", [("foreign_row_same_binding",), ("foreign_binding_same_row",)])
def test_layer3_gl_facet_origin_mismatch_blocks_every_affected_subject(mismatch: str) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, _baseline = _r3_complete_context_inputs(gl, bundle)
    context = gl._primary_norm_candidate_row(ledgers)
    threshold = gl._threshold_candidate_row(ledgers)
    assert context is not None
    assert threshold is not None
    context_ref = context["row_ref"]
    threshold_ref = threshold["row_ref"]
    context_binding_ref = f"gl-norm-candidate:{gl._stable_id(context_ref)}"
    threshold_binding_ref = f"gl-norm-candidate:{gl._stable_id(threshold_ref)}"
    selected = next(
        facet
        for facet in facets
        if facet.candidate_binding_ref == context_binding_ref
        and facet.facet_name == "source_authority"
    )
    if mismatch == "foreign_row_same_binding":
        source_table = threshold.get("source_table")
        updated = selected.model_copy(
            update={
                "kg_row_ref": threshold_ref,
                "source_table": source_table,
                "source_row_refs": (threshold_ref,),
            }
        )
    else:
        updated = selected.model_copy(update={"candidate_binding_ref": threshold_binding_ref})
    altered_facets = tuple(
        updated if facet.binding_id == selected.binding_id else facet for facet in facets
    )

    bindings = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=altered_facets,
    )
    context_result = next(item for item in bindings if item.kg_row_ref == context_ref)
    threshold_result = next(item for item in bindings if item.kg_row_ref == threshold_ref)
    assert context_result.status == "blocked"
    assert "layer3_gl_authority_facet_binding_semantic_loss" in context_result.issue_codes
    assert threshold_result.status == "blocked"
    assert "layer3_gl_authority_facet_binding_semantic_loss" in threshold_result.issue_codes
    assert context_result.candidate_norm == {}
    assert threshold_result.candidate_norm == {}


@pytest.mark.parametrize("refs", [((),), (("unresolved-facet-ref",),), (("",),)])
def test_layer3_gl_validator_rejects_missing_or_malformed_candidate_facet_refs(
    refs: tuple[str, ...],
) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["norm_candidate_bindings"][0]["authority_facet_binding_refs"] = list(refs)

    _validate_mutation(mutate, {"layer3_gl_authority_facet_binding_semantic_loss"})


def test_layer3_gl_selected_subject_identity_blocks_foreign_claim_at_persisted_and_adapter_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, baseline_bindings = _r3_complete_context_inputs(gl, bundle)
    context_binding = next(item for item in baseline_bindings if item.status == "context_only")
    assert context_binding.candidate_norm_status == "context_only"
    foreign = context_binding.model_copy(
        update={
            "claim_id": "claim:foreign-context",
            "requirement_ref": "legal-requirement:foreign-context",
        }
    )
    bindings = tuple(
        foreign if item.binding_id == context_binding.binding_id else item
        for item in bundle.norm_candidate_bindings
    )
    invalid_bundle = bundle.model_copy(
        update={
            "l3_legal_kg_search_ledgers": ledgers,
            "authority_facet_bindings": facets,
            "norm_candidate_bindings": bindings,
        }
    )

    from polisyos import lex

    captured_authority: list[Mapping[str, Any]] = []
    captured_applicability: list[Mapping[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        captured_authority.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        captured_applicability.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)
    baseline_report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=facets,
        norm_candidate_bindings=baseline_bindings,
    )
    foreign_source_ref = context_binding.candidate_norm["source_provenance_ref"]
    assert any(
        norm.get("source_provenance_ref") == foreign_source_ref for norm in captured_authority
    )
    assert any(
        norm.get("source_provenance_ref") == foreign_source_ref for norm in captured_applicability
    )
    assert baseline_report.adapter_candidate_norm_count > 0

    captured_authority.clear()
    captured_applicability.clear()
    validation = gl.validate_layer3_gl_bundle(REPO_ROOT, invalid_bundle)
    assert any(
        issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
        for issue in validation.issues
    )
    report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=bundle.legal_requirement_bindings,
        authority_facet_bindings=facets,
        norm_candidate_bindings=bindings,
    )

    assert all(
        norm.get("source_provenance_ref") != foreign_source_ref for norm in captured_authority
    )
    assert all(
        norm.get("source_provenance_ref") != foreign_source_ref for norm in captured_applicability
    )
    assert report.adapter_candidate_norm_count == 0
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report.issue_codes


def test_layer3_gl_identity_join_rejects_each_candidate_identity_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, baseline_bindings = _r3_complete_context_inputs(gl, bundle)
    context = next(item for item in baseline_bindings if item.status == "context_only")
    source_ref = context.candidate_norm["source_provenance_ref"]
    mutations: tuple[tuple[str, dict[str, Any]], ...] = (
        ("binding_id", {"binding_id": "gl-norm-candidate:foreign"}),
        ("row_ref", {"kg_row_ref": "lex_normative_ready_facts:foreign"}),
        ("source_table", {"source_table": "lex_rule_thresholds"}),
        ("source_rows", {"source_row_refs": ("lex_normative_ready_facts:foreign",)}),
        ("claim_id", {"claim_id": "claim:foreign"}),
        ("requirement_ref", {"requirement_ref": "legal-requirement:foreign"}),
        (
            "requirement_artifact_ref",
            {"legal_requirement_artifact_ref": "sha256:" + "0" * 64},
        ),
        ("request_provenance", {"provenance_refs": ("request:foreign",)}),
        ("jurisdiction", {"jurisdiction": "FR"}),
        ("legal_as_of", {"legal_as_of": "2099-01-01"}),
        ("kg_snapshot", {"legal_kg_snapshot_ref": "sha256:" + "1" * 64}),
        ("query_trace", {"query_trace_refs": ("gl-query-trace:foreign",)}),
        ("search_ledger", {"search_ledger_refs": ("gl-ledger:foreign",)}),
        (
            "facet_refs",
            {"authority_facet_binding_refs": ("gl-authority-facet:foreign",)},
        ),
        (
            "norm_id",
            {
                "candidate_norm": {
                    **context.candidate_norm,
                    "norm_id": "gl-norm:foreign",
                }
            },
        ),
        (
            "norm_source_row",
            {
                "candidate_norm": {
                    **context.candidate_norm,
                    "source_provenance_ref": "lex_normative_ready_facts:foreign",
                }
            },
        ),
    )

    from polisyos import lex

    captured_authority: list[Mapping[str, Any]] = []
    captured_applicability: list[Mapping[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        captured_authority.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        captured_applicability.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)
    for name, change in mutations:
        changed_context = context.model_copy(update=change)
        assert changed_context.status == context.status
        assert changed_context.candidate_norm_status == context.candidate_norm_status
        changed_bindings = tuple(
            changed_context if item.binding_id == context.binding_id else item
            for item in baseline_bindings
        )
        invalid_bundle = bundle.model_copy(
            update={
                "l3_legal_kg_search_ledgers": ledgers,
                "authority_facet_bindings": facets,
                "norm_candidate_bindings": changed_bindings,
            }
        )
        validation = gl.validate_layer3_gl_bundle(REPO_ROOT, invalid_bundle)
        assert any(
            issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
            for issue in validation.issues
        ), name

        captured_authority.clear()
        captured_applicability.clear()
        gl.build_gl_legal_authority_report_binding(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=bundle.legal_requirement_bindings,
            authority_facet_bindings=facets,
            norm_candidate_bindings=changed_bindings,
        )
        assert all(
            norm.get("source_provenance_ref") != source_ref for norm in captured_authority
        ), name
        assert all(
            norm.get("source_provenance_ref") != source_ref for norm in captured_applicability
        ), name


def test_layer3_gl_identity_join_rejects_each_facet_identity_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, baseline_bindings = _r3_complete_context_inputs(gl, bundle)
    context = next(item for item in baseline_bindings if item.status == "context_only")
    source_ref = context.candidate_norm["source_provenance_ref"]
    subject_facet = next(
        facet
        for facet in facets
        if facet.candidate_binding_ref == context.binding_id
        and facet.facet_name == "source_authority"
    )
    mutations: tuple[tuple[str, dict[str, Any]], ...] = (
        ("facet_id", {"binding_id": "gl-authority-facet:foreign"}),
        ("candidate_ref", {"candidate_binding_ref": "gl-norm-candidate:foreign"}),
        ("row_ref", {"kg_row_ref": "lex_normative_ready_facts:foreign"}),
        ("source_table", {"source_table": "lex_rule_thresholds"}),
        ("source_rows", {"source_row_refs": ("lex_normative_ready_facts:foreign",)}),
        ("claim_id", {"claim_id": "claim:foreign"}),
        ("requirement_ref", {"requirement_ref": "legal-requirement:foreign"}),
        (
            "requirement_artifact_ref",
            {"legal_requirement_artifact_ref": "sha256:" + "0" * 64},
        ),
        ("request_provenance", {"provenance_refs": ("request:foreign",)}),
        ("jurisdiction", {"jurisdiction": "FR"}),
        ("legal_as_of", {"legal_as_of": "2099-01-01"}),
        ("kg_snapshot", {"legal_kg_snapshot_ref": "sha256:" + "1" * 64}),
        ("query_trace", {"query_trace_refs": ("gl-query-trace:foreign",)}),
        ("search_ledger", {"search_ledger_refs": ("gl-ledger:foreign",)}),
        (
            "facet_refs",
            {"authority_facet_binding_refs": ("gl-authority-facet:foreign",)},
        ),
    )

    from polisyos import lex

    captured_authority: list[Mapping[str, Any]] = []
    captured_applicability: list[Mapping[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        captured_authority.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        captured_applicability.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)
    for name, change in mutations:
        changed_facet = subject_facet.model_copy(update=change)
        changed_facets = tuple(
            changed_facet if facet.binding_id == subject_facet.binding_id else facet
            for facet in facets
        )
        invalid_bundle = bundle.model_copy(
            update={
                "l3_legal_kg_search_ledgers": ledgers,
                "authority_facet_bindings": changed_facets,
                "norm_candidate_bindings": baseline_bindings,
            }
        )
        validation = gl.validate_layer3_gl_bundle(REPO_ROOT, invalid_bundle)
        assert any(
            issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
            for issue in validation.issues
        ), name

        captured_authority.clear()
        captured_applicability.clear()
        gl.build_gl_legal_authority_report_binding(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=bundle.legal_requirement_bindings,
            authority_facet_bindings=changed_facets,
            norm_candidate_bindings=baseline_bindings,
        )
        assert all(
            norm.get("source_provenance_ref") != source_ref for norm in captured_authority
        ), name
        assert all(
            norm.get("source_provenance_ref") != source_ref for norm in captured_applicability
        ), name


def test_layer3_gl_identity_join_recomputes_requirement_and_ledger_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, facets, baseline_bindings = _r3_complete_context_inputs(gl, bundle)
    context = next(item for item in baseline_bindings if item.status == "context_only")
    source_ref = context.candidate_norm["source_provenance_ref"]
    requirement = bundle.legal_requirement_bindings[0]
    source_owners = tuple(
        index
        for index, ledger in enumerate(ledgers)
        if context.kg_row_ref in ledger.selected_row_refs
    )
    assert source_owners

    artifact = json.loads(json.dumps(requirement.requirement_artifact))
    artifact_spec = next(
        item
        for item in artifact["requirements"]
        if item.get("requirement_id") == requirement.requirement_ref
    )
    artifact_spec["claim_ref"] = "claim:foreign-artifact"
    compiler_spec = {**requirement.requirement_spec, "claim_id": "foreign-compiled-claim"}
    requirement_mutations: tuple[tuple[str, dict[str, Any]], ...] = (
        ("claim_id", {"claim_id": "foreign-compiled-claim"}),
        ("claim_ref", {"claim_ref": "claim:foreign"}),
        ("requirement_id", {"requirement_ref": "legal-requirement:foreign"}),
        (
            "artifact_ref",
            {"legal_requirement_artifact_ref": "sha256:" + "0" * 64},
        ),
        ("producer_artifact_ref", {"producer_artifact_ref": "sha256:" + "1" * 64}),
        ("jurisdiction", {"jurisdiction": "FR"}),
        ("legal_as_of", {"legal_as_of": "2099-01-01"}),
        ("compiler_spec", {"requirement_spec": compiler_spec}),
        ("compiler_artifact", {"requirement_artifact": artifact}),
    )

    from polisyos import lex

    captured_authority: list[Mapping[str, Any]] = []
    captured_applicability: list[Mapping[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        captured_authority.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        captured_applicability.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)

    def assert_source_refused(
        name: str,
        *,
        changed_ledgers: tuple[Any, ...],
        changed_requirements: tuple[Any, ...],
    ) -> None:
        invalid_bundle = bundle.model_copy(
            update={
                "l3_legal_kg_search_ledgers": changed_ledgers,
                "legal_requirement_bindings": changed_requirements,
                "authority_facet_bindings": facets,
                "norm_candidate_bindings": baseline_bindings,
            }
        )
        validation = gl.validate_layer3_gl_bundle(REPO_ROOT, invalid_bundle)
        assert any(
            issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
            for issue in validation.issues
        ), name

        rebuilt = gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=changed_ledgers,
            legal_requirement_bindings=changed_requirements,
            authority_facet_bindings=facets,
        )
        assert not any(
            item.kg_row_ref == context.kg_row_ref and item.status != "blocked" for item in rebuilt
        ), name

        captured_authority.clear()
        captured_applicability.clear()
        gl.build_gl_legal_authority_report_binding(
            REPO_ROOT,
            ledgers=changed_ledgers,
            legal_requirement_bindings=changed_requirements,
            authority_facet_bindings=facets,
            norm_candidate_bindings=baseline_bindings,
        )
        assert all(
            norm.get("source_provenance_ref") != source_ref for norm in captured_authority
        ), name
        assert all(
            norm.get("source_provenance_ref") != source_ref for norm in captured_applicability
        ), name

    for name, change in requirement_mutations:
        changed_requirement = requirement.model_copy(update=change)
        changed_requirements = (changed_requirement,)
        assert_source_refused(
            f"requirement:{name}",
            changed_ledgers=ledgers,
            changed_requirements=changed_requirements,
        )

    foreign_source_table = "lex_rule_thresholds"
    ledger_mutations: tuple[tuple[str, dict[str, Any]], ...] = (
        ("ledger_id", {"ledger_id": "gl-ledger:foreign"}),
        ("request_ref", {"request_ref": "gl-request:foreign"}),
        ("claim_ref", {"claim_id": "claim:foreign"}),
        ("request_requirement_alias", {"requirement_ref": "legal-requirement://foreign"}),
        ("jurisdiction", {"jurisdiction": "FR"}),
        ("legal_as_of", {"legal_as_of": "2099-01-01"}),
        ("kg_snapshot", {"legal_kg_snapshot_ref": "sha256:" + "2" * 64}),
        ("query_trace", {"query_trace_refs": ("gl-query-trace:foreign",)}),
        (
            "selected_membership",
            {
                "selected_row_refs": tuple(
                    ref
                    for ref in ledgers[source_owners[0]].selected_row_refs
                    if ref != context.kg_row_ref
                )
            },
        ),
        ("source_table", {"source_table": foreign_source_table}),
    )
    for name, change in ledger_mutations:
        changed_ledgers = list(ledgers)
        targets = source_owners if name == "selected_membership" else (source_owners[0],)
        for owner_index in targets:
            owner = changed_ledgers[owner_index]
            owner_change = change
            if name == "selected_membership":
                owner_change = {
                    "selected_row_refs": tuple(
                        ref for ref in owner.selected_row_refs if ref != context.kg_row_ref
                    ),
                    "owner_frontier": None,
                }
            elif name == "source_table":
                owner_change = {
                    "candidate_rows": tuple(
                        {
                            **row,
                            "source_table": foreign_source_table,
                        }
                        if row.get("row_ref") == context.kg_row_ref
                        else row
                        for row in owner.candidate_rows
                    ),
                    "owner_frontier": None,
                }
            changed_ledgers[owner_index] = owner.model_copy(update=owner_change)
        assert_source_refused(
            f"ledger:{name}",
            changed_ledgers=tuple(changed_ledgers),
            changed_requirements=bundle.legal_requirement_bindings,
        )


def test_layer3_gl_r5_rejects_outer_requirement_fallback_projection_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, _baseline_facets, _baseline_bindings = _r3_complete_context_inputs(gl, bundle)
    original = bundle.legal_requirement_bindings[0]
    forged_fallback = {
        "mode": "jurisdiction_fallback",
        "config_ref": "test://not-in-compiler-artifact",
    }
    forged = original.model_copy(update={"fallback_policy": forged_fallback})
    assert forged.requirement_spec == original.requirement_spec
    assert forged.requirement_artifact == original.requirement_artifact
    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=(forged,),
    )
    context = gl._primary_norm_candidate_row(ledgers)
    assert context is not None
    context_ref = context["row_ref"]
    context_facets = tuple(facet for facet in facets if facet.kg_row_ref == context_ref)
    assert {facet.facet_name for facet in context_facets} == set(
        gl._GL_REQUIRED_AUTHORITY_FACET_NAMES
    )
    assert len(context_facets) == len(gl._GL_REQUIRED_AUTHORITY_FACET_NAMES)
    assert all(facet.validation_status == "blocked" for facet in context_facets)
    assert all(
        "layer3_gl_authority_facet_binding_semantic_loss" in facet.issue_codes
        for facet in context_facets
    )
    fallback_facet = next(facet for facet in context_facets if facet.facet_name == "fallback")
    assert fallback_facet.facet_value == forged_fallback
    assert fallback_facet.semantic_loss_status == "requirement_binding_projection_unreconciled"
    candidates = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=(forged,),
        authority_facet_bindings=facets,
    )
    context_binding = next(item for item in candidates if item.kg_row_ref == context["row_ref"])
    assert context_binding.status == "blocked"
    assert context_binding.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in context_binding.issue_codes

    invalid_bundle = bundle.model_copy(
        update={
            "l3_legal_kg_search_ledgers": ledgers,
            "legal_requirement_bindings": (forged,),
            "authority_facet_bindings": facets,
            "norm_candidate_bindings": candidates,
        }
    )
    validation = gl.validate_layer3_gl_bundle(REPO_ROOT, invalid_bundle)
    assert any(
        issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
        for issue in validation.issues
    )

    from polisyos import lex

    captured_authority: list[Mapping[str, Any]] = []
    captured_applicability: list[Mapping[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        captured_authority.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        captured_applicability.extend(
            item for item in kwargs.get("candidate_norms", ()) if isinstance(item, Mapping)
        )
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)
    report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=(forged,),
        authority_facet_bindings=facets,
        norm_candidate_bindings=candidates,
    )

    assert report.status == "fail"
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report.issue_codes
    assert report.adapter_candidate_norm_count == 0
    assert not captured_authority
    assert not captured_applicability


def test_layer3_gl_r5_reconciles_every_compiler_binding_field_before_projection() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    requirement = bundle.legal_requirement_bindings[0]
    ledgers, facets, _baseline_bindings = _r3_complete_context_inputs(gl, bundle)
    changed_fields: list[str] = []

    requirement_field_names = type(requirement).model_fields
    for field_name in requirement_field_names:
        value = getattr(requirement, field_name)
        if isinstance(value, bool):
            replacement: object = not value
        elif isinstance(value, str):
            replacement = f"{value}::r5-forged"
        elif isinstance(value, int):
            replacement = value + 1
        elif isinstance(value, tuple):
            replacement = (*value, "r5-forged")
        elif isinstance(value, dict):
            replacement = {**value, "r5-forged-field": "present"}
        elif value is None:
            replacement = "r5-present"
        else:
            pytest.fail(
                f"Compiler binding field {field_name!r} has no generic mutation fixture: "
                f"{type(value).__name__}"
            )

        forged = requirement.model_copy(update={field_name: replacement})
        assert forged.model_dump(mode="json") != requirement.model_dump(mode="json")
        assert gl._recompute_gl_requirement_binding_projection(REPO_ROOT, (forged,)) is None
        blocked = gl.build_gl_norm_candidate_bindings(
            REPO_ROOT,
            ledgers=ledgers,
            legal_requirement_bindings=(forged,),
            authority_facet_bindings=facets,
        )
        assert blocked
        assert all(item.status == "blocked" and item.candidate_norm == {} for item in blocked)
        changed_fields.append(field_name)

    assert set(changed_fields) == set(requirement_field_names)


def test_layer3_gl_r5_custom_present_inputs_are_not_replaced_with_defaults() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers = bundle.l3_legal_kg_search_ledgers
    assert gl.build_gl_legal_requirement_bindings(REPO_ROOT, claims=()) == ()

    custom_claims = (
        {
            "claim_id": "r5_custom_legal_claim",
            "claim_ref": "claim:r5:custom-legal",
            "legal_authority_required": True,
            "required_authority_types": ("implementing",),
            "policy_domain": "economic_policy",
        },
    )
    custom = gl.build_gl_legal_requirement_bindings(REPO_ROOT, claims=custom_claims)
    assert len(custom) == 1
    assert custom[0].claim_id == "r5_custom_legal_claim"
    assert custom[0].claim_ref == "claim:r5:custom-legal"

    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=custom,
    )
    primary = gl._primary_norm_candidate_row(ledgers)
    assert primary is not None
    primary_facets = tuple(facet for facet in facets if facet.kg_row_ref == primary["row_ref"])
    assert {facet.facet_name for facet in primary_facets} == set(
        gl._GL_REQUIRED_AUTHORITY_FACET_NAMES
    )
    assert all(facet.validation_status == "blocked" for facet in primary_facets)

    candidates = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=custom,
        authority_facet_bindings=facets,
    )
    assert candidates
    assert all(item.status == "blocked" and item.candidate_norm == {} for item in candidates)
    report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=custom,
        authority_facet_bindings=facets,
        norm_candidate_bindings=candidates,
    )
    assert report.status == "fail"
    assert report.adapter_candidate_norm_count == 0
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report.issue_codes

    empty_fallback = gl.build_gl_legal_requirement_bindings(
        REPO_ROOT,
        jurisdiction_fallback_config={},
    )
    assert empty_fallback
    assert empty_fallback[0].fallback_policy.get("config_ref") is None
    empty_fallback_facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=empty_fallback,
    )
    empty_fallback_candidates = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=empty_fallback,
        authority_facet_bindings=empty_fallback_facets,
    )
    empty_fallback_bundle = bundle.model_copy(
        update={
            "legal_requirement_bindings": empty_fallback,
            "authority_facet_bindings": empty_fallback_facets,
            "norm_candidate_bindings": empty_fallback_candidates,
        }
    )
    empty_fallback_validation = gl.validate_layer3_gl_bundle(
        REPO_ROOT,
        empty_fallback_bundle,
    )
    assert any(
        issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
        for issue in empty_fallback_validation.issues
    ), [issue.model_dump(mode="json") for issue in empty_fallback_validation.issues]
    assert not any(
        issue.code == "layer3_gl_jurisdiction_fallback_policy_missing"
        and issue.path == "$.legal_requirement_bindings[0].fallback_policy"
        for issue in empty_fallback_validation.issues
    )


def test_layer3_gl_r5_malformed_present_fallback_is_retained_as_typed_refusal() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    ledgers, _facets, _baseline = _r3_complete_context_inputs(gl, bundle)
    malformed = bundle.legal_requirement_bindings[0].model_copy(
        update={"fallback_policy": ["malformed-present"]}
    )
    facets = gl.build_gl_authority_facet_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=(malformed,),
    )
    primary = gl._primary_norm_candidate_row(ledgers)
    assert primary is not None
    subject_facets = tuple(facet for facet in facets if facet.kg_row_ref == primary["row_ref"])
    assert {facet.facet_name for facet in subject_facets} == set(
        gl._GL_REQUIRED_AUTHORITY_FACET_NAMES
    )
    fallback = next(facet for facet in subject_facets if facet.facet_name == "fallback")
    assert fallback.facet_status == "present"
    assert fallback.facet_value == ["malformed-present"]
    assert fallback.validation_status == "blocked"
    assert "layer3_gl_authority_facet_binding_semantic_loss" in fallback.issue_codes

    candidates = gl.build_gl_norm_candidate_bindings(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=(malformed,),
        authority_facet_bindings=facets,
    )
    selected = next(item for item in candidates if item.kg_row_ref == primary["row_ref"])
    assert selected.status == "blocked"
    assert selected.candidate_norm == {}
    assert "layer3_gl_authority_facet_binding_semantic_loss" in selected.issue_codes
    assert "layer3_gl_jurisdiction_fallback_policy_missing" not in selected.issue_codes

    invalid_bundle = bundle.model_copy(
        update={
            "l3_legal_kg_search_ledgers": ledgers,
            "legal_requirement_bindings": (malformed,),
            "authority_facet_bindings": facets,
            "norm_candidate_bindings": candidates,
        }
    )
    validation = gl.validate_layer3_gl_bundle(REPO_ROOT, invalid_bundle)
    assert any(
        issue.code == "layer3_gl_authority_facet_binding_semantic_loss"
        for issue in validation.issues
    )
    report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=ledgers,
        legal_requirement_bindings=(malformed,),
        authority_facet_bindings=facets,
        norm_candidate_bindings=candidates,
    )
    assert report.status == "fail"
    assert report.adapter_candidate_norm_count == 0
    assert "layer3_gl_authority_facet_binding_semantic_loss" in report.issue_codes


def test_layer3_gl_r7_default_full_bundle_persists_canonical_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist the canonical bundle, exercise both Lex adapters, and freshly validate it."""
    from polisyos import lex

    gl = _gl()
    authority_calls: list[dict[str, Any]] = []
    applicability_calls: list[dict[str, Any]] = []
    original_authority = lex.build_legal_authority_report
    original_applicability = lex.build_normative_applicability_report

    def capture_authority(*args: Any, **kwargs: Any) -> Any:
        authority_calls.append(kwargs)
        return original_authority(*args, **kwargs)

    def capture_applicability(*args: Any, **kwargs: Any) -> Any:
        applicability_calls.append(kwargs)
        return original_applicability(*args, **kwargs)

    monkeypatch.setattr(lex, "build_legal_authority_report", capture_authority)
    monkeypatch.setattr(lex, "build_normative_applicability_report", capture_applicability)
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)

    canonical_projection = gl._recompute_gl_requirement_binding_projection(
        REPO_ROOT, bundle.legal_requirement_bindings
    )
    assert canonical_projection is not None
    assert tuple(_dump(item) for item in canonical_projection) == tuple(
        _dump(item) for item in bundle.legal_requirement_bindings
    )
    assert len(authority_calls) == len(applicability_calls) == 1
    assert authority_calls[0]["candidate_norms"] == ()
    assert applicability_calls[0]["candidate_norms"] == []
    assert authority_calls[0]["legal_requirement_specs"]
    assert applicability_calls[0]["legal_requirement_specs"]

    artifact_path = tmp_path / "layer3-gl-default-bundle.json"
    payload = _dump(bundle)
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    persisted_bytes = artifact_path.read_bytes()
    persisted = json.loads(persisted_bytes)
    authority_report = persisted["legal_authority_report"]
    assert authority_report["producer_artifact_ref"].startswith(
        "repo://architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json#"
    )
    assert authority_report["candidate_source"] == "gl_norm_candidate_bindings"
    assert authority_report["adapter_candidate_norm_count"] == 0
    assert authority_report["adapter_input_contract"]["candidate_norm_count"] == 0
    assert authority_report["selected_norm_refs"] == []
    assert authority_report["legal_authority_record_refs"] == []
    assert "layer3_gl_authority_facet_binding_semantic_loss" in authority_report["blocker_refs"]
    assert "layer3_gl_norm_temporal_window_missing" in authority_report["blocker_refs"]
    assert "legal_authority_no_candidate_norm" in authority_report["adapter_report"]["issue_codes"]
    assert (
        "legal_source_relation_verification_not_established"
        in (authority_report["applicability_report"]["issue_codes"])
    )

    validation = gl.validate_layer3_gl_bundle(REPO_ROOT, persisted)
    assert _dump(validation)["status"] == "fail"
    assert {
        "layer3_gl_authority_facet_binding_missing",
        "layer3_gl_authority_facet_binding_semantic_loss",
        "layer3_gl_norm_temporal_window_missing",
        "layer3_gl_selected_norm_without_legal_authority_record",
    } <= _issue_codes(validation)

    persisted_ledgers = tuple(
        gl.Layer3GLLegalSearchLedger.model_validate(item)
        for item in persisted["l3_legal_kg_search_ledgers"]
    )
    persisted_requirements = tuple(
        gl.Layer3GLLegalRequirementBinding.model_validate(item)
        for item in persisted["legal_requirement_bindings"]
    )
    persisted_facets = tuple(
        gl.Layer3GLAuthorityFacetBinding.model_validate(item)
        for item in persisted["authority_facet_bindings"]
    )
    persisted_candidates = tuple(
        gl.Layer3GLNormCandidateBinding.model_validate(item)
        for item in persisted["norm_candidate_bindings"]
    )
    replayed_report = gl.build_gl_legal_authority_report_binding(
        REPO_ROOT,
        ledgers=persisted_ledgers,
        legal_requirement_bindings=persisted_requirements,
        authority_facet_bindings=persisted_facets,
        norm_candidate_bindings=persisted_candidates,
    )
    assert replayed_report.status == "fail"
    assert replayed_report.adapter_candidate_norm_count == 0
    assert replayed_report.selected_norm_refs == ()
    assert replayed_report.legal_authority_record_refs == ()
    assert "legal_authority_no_candidate_norm" in replayed_report.issue_codes
    assert len(authority_calls) == len(applicability_calls) == 2
    assert authority_calls[1]["candidate_norms"] == ()
    assert applicability_calls[1]["candidate_norms"] == []
