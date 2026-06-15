from __future__ import annotations

import json
import subprocess
import sys
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
    return import_module("polisyos.runtime.quality.layer3_legal_mandate_search")


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
        "polisyos.lex.intervention_artifacts": "LexProvisionMappingRegistry",
        "polisyos.runtime.quality.claim_registry": None,
        "polisyos.runtime.quality.semantic_binding": None,
        "polisyos.runtime.quality.layer2_blind_spot_firewalls": "MandateSourceRecord",
        "polisyos.runtime.quality.layer2_delegation": None,
        "polisyos.runtime.quality.layer2_value_choice": "AuthorizedValueSchedule",
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


def test_layer3_gl_plan_fixtures_cover_valid_and_malformed_semantic_bundles() -> None:
    gl = _gl()

    valid = _fixture("valid_legal_mandate_minimal_bundle.json")
    valid_report = gl.validate_layer3_gl_bundle(REPO_ROOT, valid["payload"])

    assert _dump(valid_report)["status"] == "pass"

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


def test_layer3_gl_task8_conformance_and_performance_closeout_gates_pass() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    payload = _dump(bundle)
    conformance = payload["conformance_report"]
    health = payload["health_metric_delta"]

    assert conformance["status"] == "pass"
    assert conformance["issue_codes"] == []
    assert conformance["performance_status"] == "pass"
    assert conformance["closeout_status"] == "pass"
    assert set(conformance["conformance_gate_statuses"].items()) >= set(
        {
            "g0_dependency": "pass",
            "legal_kg_route": "pass",
            "search_recall_freshness": "pass",
            "claim_level_authority": "pass",
            "consumer_gates": "pass",
            "public_projection": "pass",
            "adapter_registry": "pass",
            "performance_scaling": "pass",
        }.items()
    )
    assert payload["readiness_manifest"]["gl_conformance_status"] == "pass"
    assert payload["readiness_manifest"]["gl_adapter_semantic_loss_status"] == "pass"
    assert payload["readiness_manifest"]["gl_governance_throughput_status"] == "pass"
    assert health["readings"]["adapter-semantic-loss"] == "pass"
    assert health["readings"]["governance-throughput"] == "pass"

    for trace in payload["l3_legal_kg_query_traces"]:
        assert "LIMIT" in trace["sql_shape"].upper()
        assert trace["bounded_result_limit"] <= 256
        assert trace["query_budget"]["python_full_scan_allowed"] is False
        assert trace["query_budget"]["full_corpus_scan_allowed"] is False
        assert trace["observed_row_count"] <= trace["bounded_result_limit"]
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

    assert any(ledger["status"] == "complete_with_candidates" for ledger in ledger_payloads)
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
    from polisyos.runtime.quality.layer3_status_reducers import (
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


def test_layer3_gl_task3_norm_candidates_feed_adapters_with_explicit_specs_and_refs() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    requirements = [_dump(binding) for binding in bundle.legal_requirement_bindings]
    norm_bindings = [_dump(binding) for binding in bundle.norm_candidate_bindings]
    report = _dump(bundle.legal_authority_report)

    assert norm_bindings
    candidate_binding = norm_bindings[0]
    candidate_norm = candidate_binding["candidate_norm"]
    assert candidate_binding["status"] in {"context_only", "blocked", "pass"}
    assert candidate_binding["kg_row_ref"].startswith("lex_")
    assert candidate_binding["authority_facet_binding_refs"]
    assert candidate_binding["authority_facets_source"] == "gl_authority_facet_bindings"
    assert candidate_norm["norm_id"].startswith("gl-norm:")
    assert candidate_norm["source_provenance_ref"] == candidate_binding["kg_row_ref"]
    assert candidate_norm["jurisdiction"] == "UA"
    assert "query_trace_refs" in candidate_norm
    assert (
        candidate_norm["authority_facet_binding_refs"]
        == candidate_binding["authority_facet_binding_refs"]
    )

    assert report["candidate_source"] == "gl_norm_candidate_bindings"
    assert report["used_internal_requirement_compile"] is False
    assert report["runtime_candidate_norms_used_for_closure"] is False
    assert report["applicability_internal_kg_fallback_used"] is False
    assert report["producer_artifact_ref"].startswith(
        "repo://architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json#"
    )
    assert report["explicit_gl_requirement_spec_refs"] == [requirements[0]["requirement_ref"]]
    assert report["adapter_input_contract"]["candidate_source"] == "gl_norm_candidate_bindings"
    assert (
        report["adapter_input_contract"]["producer_artifact_ref"] == report["producer_artifact_ref"]
    )
    assert report["adapter_input_contract"]["legal_requirement_specs"] == [
        requirements[0]["requirement_spec"]
    ]
    assert report["adapter_report"]["legal_requirement_specs"] == [
        requirements[0]["requirement_spec"]
    ]
    assert report["adapter_report"]["producer_artifact_ref"] == report["producer_artifact_ref"]
    assert report["applicability_report"]["legal_requirement_specs"] == [
        requirements[0]["requirement_spec"]
    ]


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

    assert report["status"] == "pass"
    assert report["selected_norm_refs"]
    assert report["legal_authority_record_refs"]
    assert report["adapter_legal_authority_record_refs"] == report["legal_authority_record_refs"]
    assert report["adapter_candidate_norm_count"] >= 2
    assert report["used_internal_requirement_compile"] is False
    assert report["runtime_candidate_norms_used_for_closure"] is False
    assert report["applicability_internal_kg_fallback_used"] is False
    assert report["producer_artifact_ref"].startswith(
        "repo://architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json#"
    )
    assert report["adapter_report"]["status"] == "pass"
    assert report["adapter_report"]["producer_artifact_ref"] == report["producer_artifact_ref"]
    assert report["adapter_report"]["issue_codes"] == []
    assert report["issue_codes"] == []


def test_layer3_gl_task4_threshold_authority_record_binds_hydrated_rule_row() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    records = [_dump(record) for record in bundle.threshold_authority_records]

    assert records
    record = records[0]
    assert record["status"] == "pass"
    assert record["legal_authority_record_refs"]
    assert record["threshold_row_ref"].startswith("lex_rule_thresholds:")
    assert record["hydrated_from_table"] == "lex_rule_thresholds"
    assert record["threshold_source_field"] == "lex_rule_thresholds"
    assert record["metric"]
    assert record["operator"]
    assert record["value_decimal"] or record["value_text"]
    assert record["unit"]
    assert record["source_fact_ref"]
    assert record["source_norm_ref"] in _dump(bundle.legal_authority_report)["selected_norm_refs"]
    assert record["legal_admissibility_grade"] == "admissible"
    assert record["query_trace_refs"]


def test_layer3_gl_task4_mandate_record_uses_s6_compatible_handoff_without_forking() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    records = [_dump(record) for record in bundle.mandate_authority_records]

    assert records
    record = records[0]
    assert record["status"] == "compatibility_only"
    assert record["legal_authority_record_refs"]
    assert record["mandate_source_refs"]
    assert record["s6_mandate_firewall_disposition"] == "compatibility_only"
    assert record["s6_evaluation_ref"] is None
    assert record["s6_compatible_source_handoff_refs"]
    assert record["mandate_source_payloads"][0]["compatibility_status"] == (
        "requires_s6_evaluation"
    )
    assert record["authority_type"] == "implementing"
    assert record["competent_actor_ref"]
    assert record["legal_as_of"] == "2022-03-01"


def test_layer3_gl_task4_l5_calibration_limitation_is_explicit_for_passing_records() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    bindings = [_dump(binding) for binding in bundle.l5_calibration_bindings]

    assert bindings
    binding = bindings[0]
    assert binding["status"] == "limitation"
    assert binding["candidate_norm_refs"]
    assert binding["threshold_record_refs"]
    assert binding["mandate_record_refs"]
    assert binding["calibration_status"] == "missing_l5_calibration_limitation"
    assert binding["trust_tier"]
    assert binding["trust_cap"] == "context_or_claim_level_only"
    assert "layer3_gl_l5_calibration_binding_missing" in binding["issue_codes"]


def test_layer3_gl_task4_temporal_amendment_and_reference_records_fail_closed_when_needed() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    temporal_records = [_dump(record) for record in bundle.temporal_competence_records]
    amendment_records = [_dump(record) for record in bundle.amendment_lineage_records]
    reference_records = [_dump(record) for record in bundle.reference_resolution_records]

    assert any(record["status"] == "pass" for record in temporal_records)
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

    assert bindings
    binding = bindings[0]
    assert binding["status"] == "pass"
    assert binding["mapping_ref"].startswith("lex-intervention-map:")
    assert binding["provision_ref"].startswith("lex_rule_thresholds:")
    assert (
        binding["legal_authority_record_refs"]
        == _dump(bundle.legal_authority_report)["legal_authority_record_refs"]
    )
    assert (
        binding["selected_norm_refs"] == _dump(bundle.legal_authority_report)["selected_norm_refs"]
    )
    assert binding["admitted_authority_precondition_status"] == "pass"
    assert binding["used_as_legal_authority"] is False
    assert "legal_authority" not in binding["authoritative_for"]
    assert binding["intervention_kind"]
    assert binding["knob_ids"]
    assert binding["target_population_type"]
    assert binding["target_region_ids"]
    assert binding["target_sector_ids"]
    assert binding["measurement_expectations"]
    assert binding["crosswalk_refs"]
    assert binding["mapping_confidence_score"] is not None
    assert binding["mapping_provenance_refs"]
    assert binding["registry_validation_status"] == "pass"
    assert set(binding["registry_lookup_method_refs"]) >= {
        "LexProvisionMappingRegistry.get_mapping",
        "LexProvisionMappingRegistry.require_mapping",
        "LexProvisionMappingRegistry.require_knob",
        "LexProvisionMappingRegistry.get_crosswalk",
    }
    assert binding["executable_compile_status"] == "out_of_scope"
    assert binding["directive_compiled"] is False
    assert binding["issue_codes"] == []


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

    assert bindings
    binding = bindings[0]
    assert binding["status"] == "pass"
    assert binding["mapping_coverage_status"] == "synthetic_seed_used_zero_row_production_map"
    assert binding["production_mapping_row_count"] == 0
    assert binding["synthetic_mapping_seed_used"] is True
    assert binding["legal_authority_record_refs"]
    assert binding["used_as_legal_authority"] is False


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
from polisyos.runtime.quality import layer3_legal_mandate_search as gl
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

    assert claim_gate["status"] == "pass"
    assert claim_gate["claim_registry_status"] == "pass"
    assert claim_gate["claim_registry_rows"]
    claim_row = claim_gate["claim_registry_rows"][0]
    assert claim_row["claim_id"] == report["claim_id"]
    assert claim_row["selected_norm_refs"] == report["selected_norm_refs"]
    assert claim_row["legal_authority_record_refs"] == report["legal_authority_record_refs"]
    assert claim_row["threshold_record_refs"]
    assert claim_row["mandate_record_refs"]
    assert claim_row["authority_role"] == "consumer_projection"
    assert "legal_authority" not in claim_row["authoritative_for"]
    assert "legal_authority_without_claim_level_adapter" in claim_row["may_not_use_for"]
    assert claim_gate["producer_authority_refs"] == report["legal_authority_record_refs"]

    assert semantic_gate["status"] == "pass"
    assert semantic_gate["semantic_binding_status"] == "pass"
    assert semantic_gate["semantic_binding_rows"]
    semantic_row = semantic_gate["semantic_binding_rows"][0]
    assert semantic_row["selected_norm_refs"] == report["selected_norm_refs"]
    assert semantic_row["legal_authority_record_refs"] == report["legal_authority_record_refs"]
    assert semantic_row["legal_admissibility_grades"] == ["admissible"]
    assert "semantic_lex_legal_authority_record_missing" not in semantic_gate["issue_codes"]


def test_layer3_gl_task6_argument_graph_s6_s7_s8_handoffs_preserve_authority_boundaries() -> None:
    gl = _gl()
    bundle = gl.build_layer3_gl_bundle(REPO_ROOT)
    report = _dump(bundle.legal_authority_report)
    threshold_ref = _dump(bundle.threshold_authority_records[0])["record_id"]
    mandate_ref = _dump(bundle.mandate_authority_records[0])["record_id"]

    argument_gate = _dump(bundle.argument_graph_readiness_consumer_gate)
    assert argument_gate["status"] == "pass"
    assert argument_gate["diagnostic_only"] is True
    readiness = argument_gate["readiness_rows"][0]
    assert readiness["readiness_check"] == "layer3_gl_legal_mandate_search_readiness_gate"
    assert readiness["status"] == "pass"
    assert set(readiness["authority_refs"]) >= {
        report["legal_authority_record_refs"][0],
        threshold_ref,
        mandate_ref,
    }
    assert argument_gate["claims_promotion_authority"] is False

    s6_gate = _dump(bundle.s6_mandate_consumer_gate)
    assert s6_gate["status"] == "pass"
    assert s6_gate["s6_gate_disposition"] == "compatibility_only"
    assert s6_gate["does_not_assert_s6_pass"] is True
    assert s6_gate["s6_mandate_source_records"][0]["mandate_record_ref"] == mandate_ref
    assert s6_gate["s6_evaluation_ref"] is None

    s7_gate = _dump(bundle.s7_delegation_consumer_gate)
    assert s7_gate["status"] == "pass"
    assert s7_gate["mandate_record_refs"] == [mandate_ref]
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
    threshold_ref = _dump(bundle.threshold_authority_records[0])["record_id"]
    mandate_ref = _dump(bundle.mandate_authority_records[0])["record_id"]

    pdc_gate = _dump(bundle.pdc_compiler_consumer_gate)
    assert pdc_gate["status"] == "pass"
    assert pdc_gate["compatible_with_pdc_input"] is True
    assert pdc_gate["pdc_input_refs"]

    design_gate = _dump(bundle.design_constraint_consumer_gate)
    assert design_gate["status"] == "pass"
    assert design_gate["consumed_as_recommendation_substance"] is False
    assert design_gate["consumed_as_promotion_authority"] is False
    assert set(design_gate["design_constraint_rows"][0]["source_refs"]) >= {
        threshold_ref,
        mandate_ref,
    }

    g4_gate = _dump(bundle.g4_promotion_gate_consumer_gate)
    assert g4_gate["status"] == "pass"
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
    assert audit_surface["audit_refs"]["legal_authority_record_refs"]

    public_refs = _dump(bundle.public_export_projection_refs)
    assert public_refs["status"] == "pass"
    assert public_refs["projection_mode"] == "reference_only"
    assert public_refs["public_export_hook_status"] == "out_of_scope_reference_only"
    assert public_refs["raw_legal_payload_exported"] is False
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
    def mutate_claim_gate(payload: dict[str, Any]) -> None:
        payload["claim_registry_consumer_gate"]["claim_registry_rows"][0][
            "legal_authority_record_refs"
        ] = []

    _validate_mutation(
        mutate_claim_gate,
        {"layer3_gl_claim_registry_consumer_gate_missing"},
    )

    def mutate_semantic_gate(payload: dict[str, Any]) -> None:
        payload["semantic_binding_consumer_gate"]["semantic_binding_rows"][0][
            "legal_authority_record_refs"
        ] = []
        payload["semantic_binding_consumer_gate"]["issue_codes"] = [
            "semantic_lex_legal_authority_record_missing"
        ]

    _validate_mutation(
        mutate_semantic_gate,
        {"layer3_gl_semantic_binding_consumer_gate_missing"},
    )


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
import polisyos.runtime.quality.layer3_legal_mandate_search  # noqa: F401
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
