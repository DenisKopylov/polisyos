from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import duckdb
import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
G2_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g2_causal_forecast.v1"
G2_RULE_VERSION = "policyos.layer3.g2.causal_forecast_search.v1"
G2_SURFACE_ID = "layer3_g2_causal_forecast_audit_surface"

EXPECTED_DTOS = {
    "Layer3G2ValidationIssue",
    "Layer3G2ValidationReport",
    "Layer3G2CausalForecastRequest",
    "Layer3G2SearchLedger",
    "Layer3G2SkgQueryTrace",
    "Layer3G2L2SkgIndexCoverageReport",
    "Layer3G2SearchRecallSeed",
    "Layer3G2IndexFreshnessRecord",
    "Layer3G2SearchRecallFreshnessReport",
    "Layer3G2FoundryMethodRegistryCoverageReport",
    "Layer3G2FoundryMethodRegistrySearchReport",
    "Layer3G2MethodRequirementBinding",
    "Layer3G2MethodValidityTransportRecord",
    "Layer3G2SemanticSpineBinding",
    "Layer3G2ConceptAlignmentRecord",
    "Layer3G2S10PrerequisiteBinding",
    "Layer3G2ForecastSupportBinding",
    "Layer3G2GroundedForecastHandoffRecord",
    "Layer3G2ObservableCalibrationReport",
    "Layer3G2TransportLimitDeclaration",
    "Layer3G2AuthorityEnvelopeBinding",
    "Layer3G2SearchEngineeringQualityReport",
    "Layer3G2AdapterAdmissionBundle",
    "Layer3G2ConformanceReport",
    "Layer3G2CausalForecastAuditSurface",
    "Layer3G2GeneratedArtifactRegistrationStatus",
    "Layer3G2W12DConsumerGateRecord",
    "Layer3G2ReadinessManifest",
    "Layer3G2Bundle",
}

EXPECTED_BUILDERS_AND_VALIDATORS = {
    "build_layer3_g2_bundle",
    "validate_layer3_g2_bundle",
    "build_g2_l2_skg_index_coverage",
    "build_g2_search_recall_freshness",
    "build_g2_free_growth_report",
    "build_g2_search_engineering_quality_report",
    "search_l2_skg_for_forecast_candidates",
    "build_g2_foundry_method_registry_coverage",
    "search_foundry_methods_for_forecast",
    "build_g2_method_requirement_bindings",
    "build_g2_method_validity_transport_record",
    "build_g2_semantic_spine_bindings",
    "build_g2_concept_alignment_records",
    "build_g2_s10_prerequisite_bindings",
    "build_g2_forecast_support_bindings",
    "build_g2_observable_calibration_report",
    "build_g2_transport_limit_declarations",
    "build_g2_grounded_forecast_handoffs",
    "validate_g2_adapter_conformance",
    "build_g2_s10_forecast_posture",
    "build_g2_w12d_consumer_gate",
    "build_g2_causal_forecast_audit_surface",
    "build_g2_generated_artifact_registration_status",
}

REQUIRED_ISSUE_CODES = {
    "layer3_g2_g1_dependency_not_ready",
    "layer3_g2_persisted_artifact_missing",
    "layer3_g2_manifest_runtime_drift",
    "layer3_g2_surface_unsynced",
    "layer3_g2_l2_skg_not_queried",
    "layer3_g2_capability_index_used_as_l2_search",
    "layer3_g2_skg_query_trace_missing",
    "layer3_g2_semantic_retrieval_without_query_vector_producer",
    "layer3_g2_search_ledger_missing",
    "layer3_g2_foundry_method_registry_not_queried",
    "layer3_g2_method_registry_hardcode_closure",
    "layer3_g2_method_requirement_missing",
    "layer3_g2_method_validity_missing",
    "layer3_g2_semantic_binding_spine_missing",
    "layer3_g2_concept_alignment_missing",
    "layer3_g2_s10_prerequisite_binding_missing",
    "layer3_g2_search_hit_used_as_forecast_support",
    "layer3_g2_raw_skg_output_without_adapter",
    "layer3_g2_forecast_support_missing",
    "layer3_g2_observable_calibration_required",
    "layer3_g2_uncertainty_interval_missing",
    "layer3_g2_transport_limit_missing",
    "layer3_g2_claim_authority_leak",
    "layer3_g2_recommendation_authority_leak",
    "layer3_g2_closeout_authority_leak",
    "layer3_g2_useful_design_credit_leak",
    "layer3_g2_s10_consumer_bridge_missing",
    "layer3_g2_s10_posture_not_consumed",
    "layer3_g2_w12d_not_routed_closeout",
    "layer3_g2_w12d_domain_ceiling_gate_missing",
    "layer3_g2_grounded_forecast_handoff_missing",
}

EXPECTED_BUNDLE_SECTIONS = {
    "adapter_admission_registry",
    "l2_skg_search_ledgers",
    "l2_skg_query_traces",
    "l2_skg_index_coverage",
    "search_recall_freshness",
    "foundry_method_registry_coverage",
    "foundry_method_registry_search",
    "method_requirement_bindings",
    "method_validity_transport",
    "semantic_spine_bindings",
    "concept_alignment_records",
    "s10_prerequisite_bindings",
    "forecast_support_bindings",
    "grounded_forecast_handoffs",
    "observable_calibration_report",
    "transport_limit_declarations",
    "authority_envelopes",
    "conformance_report",
    "w12d_consumer_gate",
    "causal_forecast_audit_surface",
    "health_metric_delta",
    "adapter_contract_registry",
    "readiness_manifest",
}


def _g2() -> Any:
    return import_module("polisyos.runtime.quality.proving_ground.causal_forecast_search")


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return dict(payload)


def _issue_codes(report: Any) -> set[str]:
    payload = _dump(report)
    return {str(issue["code"]) for issue in payload.get("issues", [])}


def _conformance_issue_codes(report: Any) -> set[str]:
    payload = _dump(report)
    return {str(code) for code in payload.get("issue_codes", [])}


def _mutable_g2_runtime_payload() -> dict[str, Any]:
    return json.loads(json.dumps(_dump(_g2().build_layer3_g2_bundle(REPO_ROOT))))


def _conformance_payload_with(mutator: Any) -> dict[str, Any]:
    payload = _mutable_g2_runtime_payload()
    mutator(payload)
    return payload


def _create_minimal_skg_fixture(
    tmp_path: Path,
    *,
    include_transport_scores: bool = True,
    include_hnsw_assets: bool = True,
    stale_manifest: bool = False,
) -> tuple[Path, Path]:
    academic_root = tmp_path / "academic"
    graph_dir = academic_root / "graph"
    manifest_dir = academic_root / "manifests"
    graph_dir.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    if include_hnsw_assets:
        (academic_root / "ac_work_index.hnsw").write_bytes(b"hnsw-fixture")
        (academic_root / "ac_work_embeddings.npz").write_bytes(b"npz-fixture")
    (manifest_dir / "graph_index.json").write_text(
        json.dumps(
            {
                "fixture": "g2-skg",
                "tables": sorted(_g2().REQUIRED_SKG_TABLES),
                "freshness_status": "stale" if stale_manifest else "fresh",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "qc.json").write_text(
        json.dumps({"fixture": "g2-skg-qc", "status": "pass"}),
        encoding="utf-8",
    )
    db_path = graph_dir / "scholar_knowledge.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE ac_skg_edges (
            edge_id VARCHAR,
            src VARCHAR,
            dst VARCHAR,
            direction VARCHAR,
            n_articles INTEGER,
            article_refs VARCHAR,
            evidence_strength VARCHAR,
            confidence DOUBLE,
            updated_ts TIMESTAMP
        )
        """
    )
    con.execute(
        "INSERT INTO ac_skg_edges VALUES "
        "('edge-1', 'policy.credit_access', 'firm.survival', 'positive', 1, "
        "'[\"work-1\"]', 'panel_fe', 0.71, now())"
    )
    con.execute(
        """
        CREATE TABLE ac_skg_edge_evidence (
            edge_id VARCHAR,
            claim_id VARCHAR,
            openalex_id VARCHAR,
            src VARCHAR,
            dst VARCHAR,
            direction VARCHAR,
            evidence_strength VARCHAR,
            confidence DOUBLE,
            design_family VARCHAR,
            design_quality_tier INTEGER,
            skg_version INTEGER
        )
        """
    )
    con.execute(
        "INSERT INTO ac_skg_edge_evidence VALUES "
        "('edge-1', 'claim-1', 'work-1', 'policy.credit_access', 'firm.survival', "
        "'positive', 'panel_fe', 0.71, 'panel_fe', 2, 1)"
    )
    con.execute(
        """
        CREATE TABLE ac_causal_claims (
            id VARCHAR,
            work_id VARCHAR,
            cause VARCHAR,
            effect VARCHAR,
            direction VARCHAR,
            strength VARCHAR,
            mechanism VARCHAR,
            domain VARCHAR,
            trust_score DOUBLE
        )
        """
    )
    con.execute(
        "INSERT INTO ac_causal_claims VALUES "
        "('claim-1', 'work-1', 'policy.credit_access', 'firm.survival', "
        "'positive', 'panel_fe', '', '', 0.71)"
    )
    con.execute(
        """
        CREATE TABLE ac_parameter_estimates (
            id VARCHAR,
            work_id VARCHAR,
            variable_name VARCHAR,
            estimate DOUBLE,
            ci_low DOUBLE,
            ci_high DOUBLE,
            std_error DOUBLE,
            unit VARCHAR,
            domain VARCHAR,
            study_design VARCHAR,
            sample_size INTEGER,
            country VARCHAR,
            period_start INTEGER,
            period_end INTEGER,
            trust_score DOUBLE,
            raw_context VARCHAR
        )
        """
    )
    con.execute(
        "INSERT INTO ac_parameter_estimates VALUES "
        "('parameter-1', 'work-1', 'firm.survival', 0.12, 0.01, 0.23, NULL, "
        "'share', 'msme', 'panel_fe', 1000, 'UA', 2020, 2022, 0.6, '')"
    )
    con.execute(
        """
        CREATE TABLE ac_skg_parameters (
            canonical_name VARCHAR,
            parameter_json VARCHAR,
            context_json VARCHAR
        )
        """
    )
    con.execute("INSERT INTO ac_skg_parameters VALUES ('firm.survival', '{\"value\": 0.12}', '{}')")
    if include_transport_scores:
        con.execute(
            """
            CREATE TABLE ac_skg_transport_scores (
                transport_id VARCHAR,
                edge_id VARCHAR,
                target_context_id VARCHAR,
                transport_confidence DOUBLE,
                match_mode VARCHAR,
                matched_moderators_json VARCHAR,
                generic_penalty DOUBLE,
                context_match_reward DOUBLE
            )
            """
        )
        con.execute(
            "INSERT INTO ac_skg_transport_scores VALUES "
            "('transport-1', 'edge-1', 'UA', 0.61, 'fixture', '[]', 0.0, 0.1)"
        )
    con.execute(
        """
        CREATE TABLE ac_skg_contested_edges (
            contested_edge_id VARCHAR,
            src_family VARCHAR,
            dst_family VARCHAR,
            n_articles INTEGER,
            n_claims INTEGER,
            article_refs VARCHAR,
            claim_refs VARCHAR,
            dominant_direction VARCHAR,
            resolution_status VARCHAR,
            runtime_support VARCHAR,
            evidence_strength VARCHAR,
            confidence DOUBLE
        )
        """
    )
    con.execute(
        "INSERT INTO ac_skg_contested_edges VALUES "
        "('contested-1', 'policy.credit_access', 'firm.survival', 1, 1, "
        "'[\"work-1\"]', '[\"claim-1\"]', 'mixed', 'mixed', 'MIXED', 'weak', 0.2)"
    )
    con.execute(
        """
        CREATE TABLE ac_skg_variables (
            canonical_name VARCHAR,
            normalized_name VARCHAR,
            display_name VARCHAR,
            approved_canonical_name VARCHAR,
            mention_count INTEGER
        )
        """
    )
    con.execute(
        "INSERT INTO ac_skg_variables VALUES "
        "('policy.credit_access', 'policy.credit_access', 'Credit access', "
        "'policy.credit_access', 1)"
    )
    con.execute(
        """
        CREATE TABLE ac_skg_variable_synonyms (
            synonym VARCHAR,
            canonical_name VARCHAR,
            method VARCHAR,
            confidence DOUBLE,
            approved BOOLEAN
        )
        """
    )
    con.execute(
        "INSERT INTO ac_skg_variable_synonyms VALUES "
        "('loan access', 'policy.credit_access', 'fixture', 1.0, true)"
    )
    con.execute(
        """
        CREATE TABLE ac_skg_versions (
            version_id INTEGER,
            created_ts TIMESTAMP,
            n_articles INTEGER,
            n_edges INTEGER,
            n_variables INTEGER,
            description VARCHAR
        )
        """
    )
    con.execute("INSERT INTO ac_skg_versions VALUES (1, now(), 1, 1, 1, 'fixture')")
    con.close()
    return db_path, academic_root


def _patch_skg_paths(
    monkeypatch: Any,
    g2: Any,
    tmp_path: Path,
    db_path: Path,
    academic_root: Path,
) -> None:
    monkeypatch.setattr(g2, "ACADEMIC_SKG_DB_PATH", db_path.relative_to(tmp_path))
    monkeypatch.setattr(g2, "ACADEMIC_INDEX_DIR", academic_root.relative_to(tmp_path))
    monkeypatch.setattr(g2, "ACADEMIC_RUNTIME_ROOT", Path("."))
    monkeypatch.setattr(
        g2,
        "ACADEMIC_MANIFEST_REFS",
        (
            academic_root.relative_to(tmp_path) / "manifests/graph_index.json",
            academic_root.relative_to(tmp_path) / "manifests/qc.json",
        ),
    )


def _write_method_registry_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "foundry_method_registry_fixture.json"
    path.write_text(
        json.dumps({"methods": [{"method_ref": "method://fixture.synthetic-causal-forecast"}]}),
        encoding="utf-8",
    )
    return path


def _write_g2_data_home_fixture(tmp_path: Path) -> None:
    pdc = tmp_path / "architecture/policy_design_case"
    pdc.mkdir(parents=True, exist_ok=True)
    case_id = "case:g2-task6-temp-store"
    producer_root = "external-request://layer3-gx"
    (pdc / "layer3_gx_pinned_request.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.policy_design_case.layer3_gx_pinned_request.v1",
                "request_id": "gx-request:g2-task6-temp-store",
                "case_id": case_id,
                "request_ref": "external-request://layer3-gx/request/g2-task6-temp-store",
                "producer_ref": f"{producer_root}/pinned-request/{case_id}",
                "producer_type": "external_request",
                "producer_root_refs": (f"{producer_root}/root/{case_id}",),
                "authority_purpose": "temp_store_free_growth_request_only",
                "expected_consumer_path": ("G1", "G2", "G4", "G5"),
                "requested_constructs": (
                    {
                        "construct_ref": "policy.credit_access",
                        "role": "cause",
                        "g1_request_shape": "construct_to_metric_binding",
                        "g2_variable_ref": "policy.credit_access",
                        "broad_query_terms": ("credit access",),
                    },
                    {
                        "construct_ref": "firm.survival",
                        "role": "effect",
                        "g1_request_shape": "construct_to_metric_binding",
                        "g2_variable_ref": "firm.survival",
                        "broad_query_terms": ("firm survival",),
                    },
                ),
                "g1_requests": (),
                "g2_request": {
                    "request_id": "g2-request:task6-temp-store",
                    "cause": "policy.credit_access",
                    "effect": "firm.survival",
                    "target_context_id": "UA",
                    "limit": 8,
                },
                "g4_promotion_requests": (),
                "may_not_use_for": ("production_authority",),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (pdc / "layer3_gx_concept_alias_seed_rows.json").write_text(
        json.dumps(
            {
                "schema_version": (
                    "policyos.policy_design_case.layer3_gx_concept_alias_seed_rows.v1"
                ),
                "producer_ref": f"{producer_root}/alias/{case_id}",
                "producer_type": "external_request",
                "alias_rows": (
                    {
                        "row_id": "alias:g2-task6-credit-access",
                        "concept_ref": "policy.credit_access",
                        "aliases": ("credit access",),
                    },
                    {
                        "row_id": "alias:g2-task6-firm-survival",
                        "concept_ref": "firm.survival",
                        "aliases": ("firm survival",),
                    },
                ),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (pdc / "layer3_gx_scope_seed_rows.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.policy_design_case.layer3_gx_scope_seed_rows.v1",
                "producer_ref": f"{producer_root}/scope/{case_id}",
                "producer_type": "external_request",
                "scope_rows": (
                    {"scope_key": "entity_type", "value": "firm"},
                    {"scope_key": "population", "value": "msme"},
                    {"scope_key": "geography", "value": "UA"},
                    {"scope_key": "modality", "value": "panel"},
                    {"scope_key": "source_family_alias", "value": "task6_temp_skg"},
                    {"scope_key": "validity_limit", "value": "temp_store_only"},
                ),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (pdc / "layer3_gx_demand_pull_request.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.policy_design_case.layer3_gx_demand_pull_request.v1",
                "request_id": "gx-demand:g2-task6-temp-store",
                "case_id": case_id,
                "producer_ref": f"{producer_root}/demand-pull/{case_id}",
                "producer_type": "external_request",
                "source": "task6_temp_store_test",
                "timestamp": "2026-06-12T00:00:00Z",
                "accountable_principal_ref": "principal://task6-temp-store",
                "replay_key": "gx-demand:g2-task6-temp-store:replay",
                "consumer_path": ("G1", "G2", "G4", "G5"),
                "demand_refs": ("demand://task6-temp-store",),
                "attempted_grounding_path_refs": ("path://task6-temp-store/g2",),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _g2_forecast_request(**overrides: object) -> Any:
    payload: dict[str, object] = {
        "request_id": "g2-request:credit-access-firm-survival",
        "case_id": "ua-msme-affordable-loans-2022",
        "source_contract_refs": ("source-contract://ua-msme/server-support",),
        "cause": "policy.credit_access",
        "effect": "firm.survival",
        "target_context_id": "UA",
        "limit": 8,
        "method_task_tags": (
            "causal_effect_estimation",
            "forecasting",
            "uncertainty",
            "validation",
        ),
        "data_modality": "panel",
        "treatment_structure": "binary_policy",
        "outcome_type": "survival",
        "required_diagnostics": ("identification", "transportability", "uncertainty"),
    }
    payload.update(overrides)
    return _g2().Layer3G2CausalForecastRequest(**payload)


def _runtime_method_candidate(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "method_id": "causal.did.runtime",
        "method_fqn": "causal.did.difference_in_differences@1.0.0",
        "method_family": "causal_effect_estimation",
        "method_expectations": ["causal_effect_estimation", "uncertainty"],
        "truthfulness_status": "runtime_consistent",
        "input_refs": {"data_snapshot_ref": _sha("1"), "input_bindings_ref": _sha("2")},
        "assumptions": {
            "identification_strategy": "pass",
            "overlap_or_support": "pass",
            "transportability": "pass",
        },
        "runtime_assumption_gates": [
            {
                "gate_ref": "gate://identification",
                "assumption": "identification_strategy",
                "status": "pass",
            },
            {
                "gate_ref": "gate://overlap",
                "assumption": "overlap_or_support",
                "status": "pass",
            },
            {
                "gate_ref": "gate://transportability",
                "assumption": "transportability",
                "status": "pass",
            },
        ],
        "identification_requirements": {"estimand": "ATT", "requirements": ["panel_support"]},
        "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
        "uncertainty_refs": {"uncertainty_envelope_ref": _sha("3")},
        "missingness": {"status": "pass", "missing_rate": 0.01},
        "missingness_handling": {"status": "pass", "strategy": "complete_case"},
        "sensitivity": {"status": "pass", "robustness": "moderate"},
        "transportability_limits": {"target_population": "wartime_msmes"},
        "specification_space": {"primary": "two_way_fixed_effects"},
        "method_result_refs": {"method_result_ref": _sha("4")},
        "limitation_refs": {"method_limitation_ref": _sha("5")},
        "validity_surfaces": {
            "identification": {"status": "present", "ref": _sha("a")},
            "transportability": {"status": "present", "ref": _sha("b")},
            "partial_identification": {"status": "present", "ref": _sha("c")},
            "recoverability": {"status": "present", "ref": _sha("d")},
            "causal_ensemble": {"status": "present", "ref": _sha("e")},
            "falsification": {"status": "present", "ref": _sha("f")},
            "certificate_proof": {"status": "present", "ref": _sha("0")},
        },
    }
    payload.update(overrides)
    return payload


def _g2_skg_search_result(g2: Any, request: Any) -> Any:
    ledger = g2.Layer3G2SearchLedger(
        ledger_id="g2-ledger:credit-access-firm-survival",
        event_type="selected_candidate",
        request_ref=request.request_id,
        query_trace_refs=("g2-trace:credit-access-firm-survival",),
        searched_table_refs=(
            "ac_skg_edges",
            "ac_skg_edge_evidence",
            "ac_causal_claims",
            "ac_parameter_estimates",
            "ac_skg_transport_scores",
        ),
        selected_candidate_refs=("skg-edge://edge-1",),
        cutoff_limit=8,
        result_count=1,
        replay_key="g2-ledger:credit-access-firm-survival:replay",
        duckdb_validated_candidate_refs=("skg-edge://edge-1",),
    )
    trace = g2.Layer3G2SkgQueryTrace(
        trace_id="g2-trace:credit-access-firm-survival",
        table_refs=(
            "ac_skg_edges",
            "ac_skg_edge_evidence",
            "ac_causal_claims",
            "ac_parameter_estimates",
            "ac_skg_transport_scores",
        ),
        predicates={"cause": request.cause, "effect": request.effect},
        limit=8,
        result_count=1,
        row_refs=(
            "skg-edge://edge-1",
            "skg-claim://claim-1",
            "skg-parameter://parameter-1",
            "skg-transport://edge-1:UA",
        ),
        selected_candidate_refs=("skg-edge://edge-1",),
        skg_snapshot_ref="duckdb://fixture#v1",
        transport_notes=("fixture:0.610",),
    )
    return g2.Layer3G2SkgSearchResult(ledger=ledger, query_traces=(trace,))


def _g2_contested_search_result(g2: Any, request: Any) -> Any:
    ledger = g2.Layer3G2SearchLedger(
        ledger_id="g2-ledger:contested-credit-access-firm-survival",
        event_type="selected_contested_candidate",
        request_ref=request.request_id,
        query_trace_refs=("g2-trace:contested-credit-access-firm-survival",),
        searched_table_refs=("ac_skg_contested_edges", "ac_causal_claims"),
        selected_candidate_refs=("skg-edge://contested-1",),
        cutoff_limit=8,
        result_count=1,
        replay_key="g2-ledger:contested-credit-access-firm-survival:replay",
        duckdb_validated_candidate_refs=("skg-edge://contested-1",),
    )
    trace = g2.Layer3G2SkgQueryTrace(
        trace_id="g2-trace:contested-credit-access-firm-survival",
        table_refs=("ac_skg_contested_edges", "ac_causal_claims"),
        predicates={"support_mode": "contested"},
        limit=8,
        result_count=1,
        row_refs=("skg-edge://contested-1", "skg-claim://claim-contested-1"),
        selected_candidate_refs=("skg-edge://contested-1",),
        skg_snapshot_ref="duckdb://fixture#v1",
        quality_flags=("directional_conflict", "resolution:mixed"),
    )
    return g2.Layer3G2SkgSearchResult(ledger=ledger, query_traces=(trace,))


def _g2_method_validity_record(g2: Any, request: Any) -> Any:
    search = g2.search_foundry_methods_for_forecast(request)
    binding = g2.build_g2_method_requirement_bindings(
        request,
        search,
        runtime_method_candidates=(_runtime_method_candidate(),),
    )[0]
    return g2.build_g2_method_validity_transport_record(
        request,
        binding,
        method_candidates=(_runtime_method_candidate(),),
    )


def _g2_semantic_spine_kwargs(**overrides: object) -> dict[str, object]:
    request = _g2_forecast_request()
    payload: dict[str, object] = {
        "request": request,
        "concept_spine_ref": "concept-spine://ua-msme/credit-access-survival",
        "jurisdiction_spine_ref": "jurisdiction-spine://UA",
        "canonical_concept_refs": (
            "concept://policy.credit_access",
            "concept://firm.survival",
        ),
        "jurisdiction_refs": ("jurisdiction://UA",),
        "unit_refs": ("unit://firm",),
        "period_refs": ("period://2022-2024",),
        "geography_refs": ("geo://UA",),
        "governed_namespace_refs": (
            "namespace://g1/source-contract/ua-msme",
            "namespace://skg/academic",
            "namespace://foundry/methods",
            "namespace://layer2/s10",
        ),
        "reconciled_concept_statuses": {
            "policy.credit_access": "reconciled",
            "firm.survival": "reconciled",
        },
        "producer_handshake_refs": ("producer-handshake://g1-skg-foundry-s10/credit-survival",),
        "candidate_refs": (
            "source-contract://ua-msme/server-support",
            "skg-variable://policy.credit_access",
            "skg-variable://firm.survival",
            "foundry-slot://treatment",
            "foundry-slot://outcome",
        ),
    }
    payload.update(overrides)
    return payload


def _g2_concept_alignment_kwargs(
    g2: Any, semantic_binding: Any, **overrides: object
) -> dict[str, object]:
    request = _g2_forecast_request()
    payload: dict[str, object] = {
        "request": request,
        "semantic_spine_binding": semantic_binding,
        "source_contract_refs": request.source_contract_refs,
        "g1_target_outcome_refs": ("source-contract://ua-msme/server-support#firm-survival",),
        "g1_metric_refs": ("metric://firm-survival-rate",),
        "skg_cause_variable_ref": "skg-variable://policy.credit_access",
        "skg_effect_variable_ref": "skg-variable://firm.survival",
        "skg_parameter_refs": ("skg-parameter://parameter-1",),
        "foundry_input_slot_refs": ("foundry-slot://treatment", "foundry-slot://panel-data"),
        "foundry_output_slot_refs": ("foundry-slot://effect-estimate",),
        "s10_target_outcome_refs": ("outcome://firm-survival",),
        "alignment_status": "direct",
        "direct_grounding_claimed": True,
    }
    payload.update(overrides)
    return payload


def _g2_s10_prerequisite_kwargs(
    g2: Any,
    semantic_binding: Any,
    concept_alignment: Any,
    method_validity: Any,
    **overrides: object,
) -> dict[str, object]:
    request = _g2_forecast_request()
    payload: dict[str, object] = {
        "request": request,
        "semantic_spine_binding": semantic_binding,
        "concept_alignment_record": concept_alignment,
        "method_validity_record": method_validity,
        "source_design_record_ref": "pdc://layer2/s2/ua-msme/design-record-v0",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "candidate_design_ref": "candidate://ua-msme/targeted-credit",
        "baseline_design_ref": "baseline://ua-msme/no-new-credit",
        "alternative_design_refs": ("alternative://ua-msme/cash-transfer",),
        "prediction_horizon_ref": "horizon://12-months",
        "target_outcome_refs": ("outcome://firm-survival",),
        "jurisdiction_scope_ref": "jurisdiction://UA",
        "s5_forecast_support_ref": "pdc://layer2/s5/ua-msme/system-effect-support",
        "s5_support_label": "validated_local_dynamic_model",
        "s5_base_origin": "validated_local_model",
        "s5_claim_scope": "system_effect",
        "s6_firewall_status_refs": ("pdc://layer2/s6/ua-msme/measurability-adequacy",),
        "s6_limitation_refs": ("pdc://layer2/s6/ua-msme/strategic-response-limitation",),
        "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice-provenance",
        "s8_value_tradeoff_disclosure_ref": ("pdc://layer2/s8/ua-msme/value-tradeoff-disclosure"),
        "source_contract_ref": "source-contract://ua-msme/server-support",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "sensitivity_analysis_ref": "sensitivity://ua-msme/credit-access",
        "dynamic_equilibrium_check_ref": "equilibrium-check://ua-msme/system-effect",
        "equilibrium_caveat_refs": ("caveat://partial-equilibrium",),
        "strategic_response_caveat_refs": ("caveat://strategic-response",),
        "outcome_distribution_refs": ("distribution://ua-msme/credit-access",),
        "welfare_comparison_ref": "welfare://ua-msme/value-grounded",
        "observable_subset_ref": "observable-subset://ua-msme/local-panel",
        "uncertainty_interval_refs": ("interval://ua-msme/credit-access/95",),
        "limitation_refs": ("limitation://forecast/support-only",),
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "source_lineage_refs": ("lineage://ua-msme/source-contract",),
        "method_lineage_refs": ("lineage://ua-msme/foundry-causal",),
    }
    payload.update(overrides)
    return payload


def _g2_calibration_payload(**overrides: object) -> dict[str, object]:
    now = datetime(2026, 6, 2, tzinfo=UTC)
    payload: dict[str, object] = {
        "calibration_id": "layer3.g2.calibration.ua-msme.observable",
        "calibration_ref": "pdc://layer3/g2/ua-msme/calibration/observable-subset",
        "case_id": "ua-msme-affordable-loans-2022",
        "observable_subset_ref": "observable-subset://ua-msme/local-panel",
        "prediction_ref": "forecast://ua-msme/credit-access/prediction",
        "observed_outcome_ref": "outcome://ua-msme/credit-access/observed",
        "historical_implementation_ref": "implementation://ua-msme/credit-2022",
        "evaluation_design_ref": "eval://ua-msme/credible-counterfactual",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "counterfactual_credibility": "credible",
        "prediction_time": now,
        "observation_time": now,
        "policy_effective_time": now,
        "data_valid_time": now,
        "calibration_window_start": now,
        "calibration_window_end": now,
        "denominator": 4,
        "numerator": 4,
        "pass_rate": 1.0,
        "calibration_threshold_ref": "repo://architecture/policy_design_case/layer2_floor_governance.toml#s10",
        "floor_passed": True,
        "calibration_status": "pass",
        "interval_coverage_metric": 1.0,
        "calibration_error_metric": 0.0,
        "source_lineage_refs": ("lineage://ua-msme/source-contract",),
        "method_lineage_refs": ("lineage://ua-msme/foundry-causal",),
    }
    payload.update(overrides)
    return payload


def _g2_task4_positive_objects(**prereq_overrides: object) -> dict[str, object]:
    g2 = _g2()
    request = _g2_forecast_request()
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]
    alignment = g2.build_g2_concept_alignment_records(**_g2_concept_alignment_kwargs(g2, semantic))[
        0
    ]
    method_validity = _g2_method_validity_record(g2, request)
    prerequisite = g2.build_g2_s10_prerequisite_bindings(
        **_g2_s10_prerequisite_kwargs(
            g2,
            semantic,
            alignment,
            method_validity,
            **prereq_overrides,
        )
    )[0]
    return {
        "g2": g2,
        "request": request,
        "semantic": semantic,
        "alignment": alignment,
        "method_validity": method_validity,
        "prerequisite": prerequisite,
    }


def _g2_forecast_binding(
    *,
    search_result: Any | None = None,
    requested_forecast_tier: str = "observable_calibrated",
    calibration_payload: dict[str, object] | None = None,
    requested_adapter_maturity: str | None = None,
    calibrated_dynamics_producer_ref: str | None = None,
    **prereq_overrides: object,
) -> Any:
    objects = _g2_task4_positive_objects(**prereq_overrides)
    g2 = objects["g2"]
    request = objects["request"]
    return g2.build_g2_forecast_support_bindings(
        request=request,
        search_result=search_result or _g2_skg_search_result(g2, request),
        semantic_spine_binding=objects["semantic"],
        concept_alignment_record=objects["alignment"],
        s10_prerequisite_binding=objects["prerequisite"],
        method_validity_record=objects["method_validity"],
        requested_forecast_tier=requested_forecast_tier,
        calibration_payload=calibration_payload,
        requested_adapter_maturity=requested_adapter_maturity,
        calibrated_dynamics_producer_ref=calibrated_dynamics_producer_ref,
    )[0]


def test_g2_runtime_exposes_schema_rule_and_surface_constants() -> None:
    g2 = _g2()

    assert g2.LAYER3_G2_SCHEMA_VERSION == G2_SCHEMA_VERSION
    assert g2.LAYER3_G2_RULE_VERSION == G2_RULE_VERSION
    assert g2.LAYER3_G2_SURFACE_ID == G2_SURFACE_ID


def test_g2_runtime_exposes_plan_dtos_builders_validators_and_issue_codes() -> None:
    g2 = _g2()

    missing_dtos = {name for name in EXPECTED_DTOS if not hasattr(g2, name)}
    missing_functions = {name for name in EXPECTED_BUILDERS_AND_VALIDATORS if not hasattr(g2, name)}
    issue_codes = set(getattr(g2, "ALL_ISSUE_CODES", ()))

    assert not missing_dtos
    assert not missing_functions
    assert issue_codes >= REQUIRED_ISSUE_CODES


def test_g2_default_persisted_request_uses_pinned_credit_survival_semantics() -> None:
    g2 = _g2()

    request = g2._default_g2_method_request()

    assert request.case_id == "ua-msme-affordable-loans-2022"
    assert request.cause == "policy.credit_access"
    assert request.effect == "firm.survival"


def test_g2_synthetic_fixture_candidate_cannot_produce_persisted_calibrated() -> None:
    g2 = _g2()
    bundle = g2.build_layer3_g2_bundle(REPO_ROOT)
    payload = _dump(bundle)

    assert payload["readiness_manifest"]["adapter_maturity"] == "fail_closed"
    assert payload["readiness_manifest"]["status"] == "fail"
    assert (
        "layer3_g2_synthetic_calibration_overclaim" in payload["readiness_manifest"]["issue_codes"]
    )
    assert not any(
        binding["adapter_maturity"] == "calibrated"
        for binding in payload["forecast_support_bindings"]
    )


def test_g2_bundle_builder_returns_all_persisted_contract_sections() -> None:
    bundle = _g2().build_layer3_g2_bundle(REPO_ROOT)

    payload = _dump(bundle)

    assert payload["schema_version"] == G2_SCHEMA_VERSION
    assert payload["rule_version"] == G2_RULE_VERSION
    assert set(payload) >= EXPECTED_BUNDLE_SECTIONS
    assert payload["readiness_manifest"]["schema_version"] == G2_SCHEMA_VERSION
    assert payload["readiness_manifest"]["rule_version"] == G2_RULE_VERSION
    assert payload["readiness_manifest"]["status"] == "fail"
    assert payload["readiness_manifest"]["adapter_maturity"] == "fail_closed"
    assert payload["conformance_report"]["status"] == "fail"
    assert payload["conformance_report"]["conformance_status"] == "fail"
    assert (
        "layer3_g2_synthetic_calibration_overclaim" in payload["conformance_report"]["issue_codes"]
    )


def test_g2_conformance_passes_for_runtime_bundle_and_summarizes_final_gates() -> None:
    g2 = _g2()
    bundle = g2.build_layer3_g2_bundle(REPO_ROOT)

    report = _dump(g2.validate_g2_adapter_conformance(REPO_ROOT, bundle))

    assert report["status"] == "fail"
    assert report["conformance_status"] == "fail"
    assert "layer3_g2_synthetic_calibration_overclaim" in report["issue_codes"]
    assert report["capability_reality_label"] == "semantic_test_missing"
    assert report["check_statuses"]["g2_conformance_status"] == "fail"
    assert report["check_statuses"]["g2_l2_skg_coverage_status"] == "pass"
    assert report["check_statuses"]["g2_foundry_method_registry_search_status"] == "pass"
    assert report["check_statuses"]["g2_method_requirement_status"] == "fail"
    assert report["check_statuses"]["g2_semantic_binding_spine_status"] == "pass"
    assert report["check_statuses"]["g2_w12d_consumer_gate_status"] == "fail"
    assert report["check_statuses"]["g2_engineering_quality_status"] == "pass"


@pytest.mark.parametrize(
    ("case_id", "mutator", "expected_codes"),
    [
        (
            "missing_search_ledger",
            lambda payload: payload.update({"l2_skg_search_ledgers": []}),
            {"layer3_g2_search_ledger_missing"},
        ),
        (
            "missing_query_trace",
            lambda payload: payload.update({"l2_skg_query_traces": []}),
            {"layer3_g2_skg_query_trace_missing"},
        ),
        (
            "bad_l2_coverage",
            lambda payload: payload["l2_skg_index_coverage"].update(
                {
                    "status": "fail",
                    "canonical_l2_route": "capability_index",
                    "skg_query_api_route": "capability_index",
                    "required_tables_present": False,
                    "index_dir_status": "fail",
                }
            ),
            {
                "layer3_g2_l2_skg_index_coverage_missing",
                "layer3_g2_capability_index_used_as_l2_search",
            },
        ),
        (
            "bounded_surrogate_overclaimed",
            lambda payload: payload["l2_skg_index_coverage"].update(
                {"bounded_surrogate_claimed": True}
            ),
            {"layer3_g2_l2_skg_bounded_surrogate_overclaimed"},
        ),
        (
            "hnsw_candidate_without_skg_row",
            lambda payload: payload["l2_skg_search_ledgers"][0].update(
                {
                    "hnsw_candidate_refs": ["hnsw-candidate://unvalidated"],
                    "duckdb_validated_candidate_refs": [],
                }
            ),
            {"layer3_g2_hnsw_candidate_without_skg_row"},
        ),
        (
            "skg_web_evidence_bundle_laundering",
            lambda payload: payload["l2_skg_search_ledgers"][0].update(
                {"web_evidence_bundle_refs": ["web-evidence-bundle://not-skg"]}
            ),
            {"layer3_g2_skg_web_evidence_bundle_laundering"},
        ),
        (
            "no_hit_without_replayable_frontier",
            lambda payload: payload["l2_skg_search_ledgers"][0].update(
                {
                    "event_type": "no_hit",
                    "result_count": 0,
                    "selected_candidate_refs": [],
                    "query_trace_refs": [],
                }
            ),
            {"layer3_g2_no_hit_without_replayable_frontier"},
        ),
        (
            "stale_recall",
            lambda payload: payload["search_recall_freshness"].update(
                {
                    "status": "fail",
                    "search_recall_status": "fail",
                    "index_freshness_status": "fail",
                }
            ),
            {
                "layer3_g2_search_recall_seed_miss_blocks_domain_ceiling",
                "layer3_g2_stale_index_blocks_domain_ceiling",
            },
        ),
        (
            "search_ceiling_not_domain_ceiling",
            lambda payload: (
                payload["search_recall_freshness"].update(
                    {"status": "fail", "search_recall_status": "fail"}
                ),
                payload["w12d_consumer_gate"].update(
                    {"domain_ceiling_status": "causal_forecast_domain_ceiling"}
                ),
            ),
            {"layer3_g2_search_ceiling_not_domain_ceiling"},
        ),
        (
            "failed_search_engineering",
            lambda payload: payload["search_engineering_quality"].update({"status": "fail"}),
            {"layer3_g2_search_engineering_quality_failed"},
        ),
        (
            "failed_free_growth",
            lambda payload: payload["free_growth_report"].update({"status": "fail"}),
            {"layer3_g2_free_growth_fixture_failed"},
        ),
        (
            "single_request_generality",
            lambda payload: payload["free_growth_report"].update({"free_growth_fixture_count": 1}),
            {"layer3_g2_mechanism_generality_single_request"},
        ),
        (
            "method_registry_not_queried",
            lambda payload: payload["foundry_method_registry_search"].update({"status": "fail"}),
            {"layer3_g2_foundry_method_registry_not_queried"},
        ),
        (
            "method_registry_hardcode",
            lambda payload: payload["foundry_method_registry_search"].update(
                {"hardcoded_fqn_closure": True}
            ),
            {"layer3_g2_method_registry_hardcode_closure"},
        ),
        (
            "foundry_discovery_coverage_missing",
            lambda payload: payload["foundry_method_registry_coverage"].update(
                {
                    "status": "fail",
                    "issue_codes": ["layer3_g2_foundry_discovery_coverage_missing"],
                }
            ),
            {"layer3_g2_foundry_discovery_coverage_missing"},
        ),
        (
            "foundry_builtin_bootstrap_missing",
            lambda payload: payload["foundry_method_registry_coverage"].update(
                {"built_in_catalog_bootstrap_refs": []}
            ),
            {"layer3_g2_foundry_builtin_catalog_bootstrap_missing"},
        ),
        (
            "foundry_registry_snapshot_missing",
            lambda payload: payload["foundry_method_registry_coverage"].update(
                {"registry_snapshot_ref": ""}
            ),
            {"layer3_g2_foundry_registry_snapshot_missing"},
        ),
        (
            "foundry_discovery_not_refreshed",
            lambda payload: payload["foundry_method_registry_coverage"].update(
                {"discovery_refresh_status": "fail"}
            ),
            {"layer3_g2_method_registry_discovery_not_refreshed"},
        ),
        (
            "missing_method_requirements",
            lambda payload: payload.update({"method_requirement_bindings": []}),
            {"layer3_g2_method_requirement_missing"},
        ),
        (
            "failed_method_requirement_selection",
            lambda payload: payload["method_requirement_bindings"][0].update(
                {"status": "fail", "selection_status": "fail"}
            ),
            {"layer3_g2_method_requirement_selection_failed"},
        ),
        (
            "missing_method_validity",
            lambda payload: payload.update({"method_validity_transport": []}),
            {"layer3_g2_method_validity_missing"},
        ),
        (
            "method_report_not_persisted",
            lambda payload: payload["method_validity_transport"][0].update(
                {"cas_persistence_status": "missing"}
            ),
            {"layer3_g2_foundry_method_report_persistence_missing"},
        ),
        (
            "missing_semantic_spine",
            lambda payload: payload.update({"semantic_spine_bindings": []}),
            {"layer3_g2_semantic_binding_spine_missing"},
        ),
        (
            "parallel_semantic_lattice",
            lambda payload: payload["semantic_spine_bindings"][0].update(
                {"parallel_concept_lattice_declared": True}
            ),
            {"layer3_g2_parallel_concept_lattice"},
        ),
        (
            "missing_concept_alignment",
            lambda payload: payload.update({"concept_alignment_records": []}),
            {"layer3_g2_concept_alignment_missing"},
        ),
        (
            "proxy_alignment_undisclosed",
            lambda payload: payload["concept_alignment_records"][0].update(
                {"alignment_status": "proxy_only", "proxy_disclosed": False}
            ),
            {"layer3_g2_proxy_alignment_undisclosed"},
        ),
        (
            "ambiguous_alignment_overclaimed",
            lambda payload: payload["concept_alignment_records"][0].update(
                {"alignment_status": "ambiguous", "direct_grounding_claimed": True}
            ),
            {"layer3_g2_ambiguous_alignment_overclaimed"},
        ),
        (
            "missing_s10_prerequisite",
            lambda payload: payload.update({"s10_prerequisite_bindings": []}),
            {"layer3_g2_s10_prerequisite_binding_missing"},
        ),
        (
            "missing_s10_context_refs",
            lambda payload: payload["s10_prerequisite_bindings"][0].update(
                {
                    "prediction_context_ref": None,
                    "s5_forecast_support_ref": None,
                    "s6_firewall_status_refs": [],
                    "s8_value_choice_provenance_ref": None,
                    "s8_value_tradeoff_disclosure_ref": None,
                }
            ),
            {
                "layer3_g2_s5_s6_s8_refs_missing",
                "layer3_g2_design_prediction_context_missing",
            },
        ),
        (
            "missing_forecast_support",
            lambda payload: payload.update({"forecast_support_bindings": []}),
            {"layer3_g2_forecast_support_missing"},
        ),
        (
            "invalid_forecast_support_builder",
            lambda payload: payload["forecast_support_bindings"][0].update(
                {"s10_builder_ref": "parallel.g2.forecast.builder"}
            ),
            {"layer3_g2_forecast_support_invalid"},
        ),
        (
            "forecast_tier_overclaimed",
            lambda payload: payload["forecast_support_bindings"][0].update(
                {"s10_forecast_tier": "simulation_only_advisory"}
            ),
            {"layer3_g2_forecast_tier_overclaimed"},
        ),
        (
            "regime_forecast_tier_laundering",
            lambda payload: payload["forecast_support_bindings"][0].update(
                {
                    "epistemic_regime": "precautionary",
                    "regime_limitation_refs": [],
                }
            ),
            {"layer3_g2_regime_forecast_tier_laundering"},
        ),
        (
            "effect_independence_inflated",
            lambda payload: payload["forecast_support_bindings"][0].update(
                {
                    "effect_independence_claimed": True,
                    "independence_collapse_refs": [],
                }
            ),
            {"layer3_g2_effect_independence_inflated"},
        ),
        (
            "tier_derivation_mismatch",
            lambda payload: payload["forecast_support_bindings"][0].update(
                {
                    "requested_forecast_tier": "observable_calibrated",
                    "s10_forecast_tier": "limited",
                }
            ),
            {"layer3_g2_s10_tier_derivation_mismatch"},
        ),
        (
            "missing_calibration_evidence",
            lambda payload: payload["observable_calibration_report"].update(
                {
                    "status": "fail",
                    "observable_subset_calibration_denominator": 0,
                    "credible_evaluation_evidence_refs": [],
                }
            ),
            {
                "layer3_g2_observable_calibration_denominator_missing",
                "layer3_g2_credible_evaluation_evidence_missing",
            },
        ),
        (
            "missing_uncertainty_interval",
            lambda payload: payload["forecast_support_bindings"][0].update(
                {"uncertainty_interval_refs": []}
            ),
            {"layer3_g2_uncertainty_interval_missing"},
        ),
        (
            "missing_transport_limits",
            lambda payload: payload.update({"transport_limit_declarations": []}),
            {"layer3_g2_transport_limit_missing"},
        ),
        (
            "missing_transportability_limits",
            lambda payload: payload["transport_limit_declarations"][0].update(
                {"method_transportability_limit_refs": []}
            ),
            {"layer3_g2_transportability_limit_missing"},
        ),
        (
            "aggregation_validity_missing",
            lambda payload: payload["transport_limit_declarations"][0].update(
                {"aggregation_scope_ref": None}
            ),
            {"layer3_g2_aggregation_validity_missing"},
        ),
        (
            "strategic_response_missing",
            lambda payload: payload["s10_prerequisite_bindings"][0].update(
                {"strategic_response_caveat_refs": []}
            ),
            {"layer3_g2_strategic_response_missing"},
        ),
        (
            "semantic_loss",
            lambda payload: payload["semantic_spine_bindings"][0].update(
                {"semantic_loss_status": "fail"}
            ),
            {"layer3_g2_semantic_loss"},
        ),
        (
            "authority_leaks",
            lambda payload: payload["forecast_support_bindings"][0].update(
                {
                    "authoritative_for": [
                        "claim_authority",
                        "policy_recommendation",
                        "closeout_authority",
                        "useful_design_credit",
                    ],
                    "may_not_use_for": [],
                }
            ),
            {
                "layer3_g2_claim_authority_leak",
                "layer3_g2_recommendation_authority_leak",
                "layer3_g2_closeout_authority_leak",
                "layer3_g2_useful_design_credit_leak",
            },
        ),
        (
            "w12d_not_routed",
            lambda payload: payload["w12d_consumer_gate"].update(
                {
                    "status": "fail",
                    "posture_consumed": False,
                    "issue_codes": ["layer3_g2_w12d_not_routed_closeout"],
                }
            ),
            {
                "layer3_g2_s10_consumer_bridge_missing",
                "layer3_g2_s10_posture_not_consumed",
                "layer3_g2_w12d_not_routed_closeout",
            },
        ),
        (
            "s2_forecast_producer_import",
            lambda payload: payload["w12d_consumer_gate"].update(
                {"s2_forecast_producer_import_count": 1}
            ),
            {"layer3_g2_s2_forecast_producer_import"},
        ),
        (
            "w12d_full_s2_overreach",
            lambda payload: payload["w12d_consumer_gate"].update(
                {"full_s2_consumer_case_count": 2}
            ),
            {"layer3_g2_w12d_full_s2_overreach"},
        ),
        (
            "missing_handoff",
            lambda payload: payload.update({"grounded_forecast_handoffs": []}),
            {"layer3_g2_grounded_forecast_handoff_missing"},
        ),
        (
            "promoted_handoff",
            lambda payload: payload["grounded_forecast_handoffs"][0].update(
                {
                    "authoritative_for": ["promotion_authority"],
                    "promotion_authority_claimed": True,
                    "conversion_authority_claimed": True,
                    "useful_design_credit_claimed": True,
                    "may_not_use_for": [],
                }
            ),
            {
                "layer3_g2_grounded_forecast_handoff_promoted",
                "layer3_g2_w12d_conversion_outcome_overwrite",
            },
        ),
        (
            "surface_unsynced",
            lambda payload: payload["causal_forecast_audit_surface"].update(
                {"status": "fail", "issue_codes": ["layer3_g2_surface_unsynced"]}
            ),
            {"layer3_g2_surface_unsynced"},
        ),
    ],
)
def test_g2_conformance_fails_closed_for_small_fixture_mutations(
    case_id: str,
    mutator: Any,
    expected_codes: set[str],
) -> None:
    report = _g2().validate_g2_adapter_conformance(
        REPO_ROOT,
        _conformance_payload_with(mutator),
    )

    assert case_id
    assert _dump(report)["status"] == "fail"
    assert expected_codes <= _conformance_issue_codes(report)


def test_g2_validator_fails_closed_when_binding_and_consumer_records_are_missing() -> None:
    payload = {
        "schema_version": G2_SCHEMA_VERSION,
        "rule_version": G2_RULE_VERSION,
        "readiness_manifest": {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "g1_dependency_status": "pass",
            "g2_method_requirement_binding_count": 0,
            "g2_semantic_spine_binding_count": 0,
            "g2_s10_prerequisite_binding_status": "fail",
            "g2_w12d_consumer_gate_status": "not_routed",
        },
        "method_requirement_bindings": [],
        "semantic_spine_bindings": [],
        "s10_prerequisite_bindings": [],
        "w12d_consumer_gate": {"status": "not_routed"},
    }

    report = _g2().validate_layer3_g2_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert {
        "layer3_g2_method_requirement_missing",
        "layer3_g2_semantic_binding_spine_missing",
        "layer3_g2_s10_prerequisite_binding_missing",
        "layer3_g2_s10_consumer_bridge_missing",
        "layer3_g2_w12d_not_routed_closeout",
    } <= _issue_codes(report)


def test_g2_validator_rejects_search_control_and_authority_laundering() -> None:
    payload = {
        "schema_version": G2_SCHEMA_VERSION,
        "rule_version": G2_RULE_VERSION,
        "l2_skg_search_ledgers": [
            {
                "ledger_id": "g2-ledger:capability-index-leak",
                "canonical_l2_route": "capability_index",
                "authoritative_for": ["forecast_support"],
                "may_not_use_for": [],
            }
        ],
        "forecast_support_bindings": [
            {
                "binding_id": "g2-binding:search-hit-as-support",
                "search_ledger_refs": ["g2-ledger:capability-index-leak"],
                "adapter_validation_ref": None,
                "s10_forecast_support_ref": "skg-hit://not-s10-valid",
                "authoritative_for": ["claim_authority", "policy_recommendation"],
                "may_not_use_for": [],
            }
        ],
    }

    report = _g2().validate_layer3_g2_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert {
        "layer3_g2_capability_index_used_as_l2_search",
        "layer3_g2_search_ledger_authority_boundary_leak",
        "layer3_g2_search_hit_used_as_forecast_support",
        "layer3_g2_claim_authority_leak",
        "layer3_g2_recommendation_authority_leak",
    } <= _issue_codes(report)


def test_g2_validator_requires_search_hit_authority_denial_on_ledgers() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "l2_skg_search_ledgers": [
                {
                    "ledger_id": "g2-ledger:missing-search-hit-denial",
                    "event_type": "selected_candidate",
                    "request_ref": "g2-request:missing-search-hit-denial",
                    "canonical_l2_route": "scholar_knowledge.duckdb",
                    "query_trace_refs": ["g2-trace:missing-search-hit-denial"],
                    "searched_table_refs": ["ac_skg_edges"],
                    "selected_candidate_refs": ["skg-edge://edge-1"],
                    "authoritative_for": [],
                    "may_not_use_for": ["claim_authority"],
                    "replay_key": "g2-ledger:missing-search-hit-denial:replay",
                }
            ],
            "l2_skg_query_traces": [
                {
                    "trace_id": "g2-trace:missing-search-hit-denial",
                    "query_api_route": "polisyos.data_forge.read_api.academic.SKGQuery",
                    "canonical_l2_route": "scholar_knowledge.duckdb",
                    "table_refs": ["ac_skg_edges"],
                    "predicates": {},
                    "limit": 1,
                    "result_count": 1,
                    "row_refs": ["skg-edge://edge-1"],
                    "skg_snapshot_ref": "duckdb://fixture#v1",
                }
            ],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert "layer3_g2_search_ledger_authority_boundary_leak" in _issue_codes(report)


def test_g2_task1_core_dtos_are_strict_and_fail_on_extra_fields() -> None:
    g2 = _g2()

    with pytest.raises(ValidationError):
        g2.Layer3G2SearchLedger.model_validate(
            {
                "ledger_id": "g2-ledger:extra",
                "event_type": "selected_candidate",
                "request_ref": "g2-request:extra",
                "canonical_l2_route": "scholar_knowledge.duckdb",
                "query_trace_refs": ["g2-trace:extra"],
                "searched_table_refs": ["ac_skg_edges"],
                "replay_key": "g2-ledger:extra:replay",
                "unexpected": "blocked-by-extra-forbid",
            }
        )


def test_g2_l2_skg_index_coverage_reads_real_snapshot_with_canonical_skgquery_path() -> None:
    coverage = _dump(_g2().build_g2_l2_skg_index_coverage(REPO_ROOT))

    assert coverage["status"] == "pass"
    assert coverage["canonical_l2_route"] == "scholar_knowledge.duckdb"
    assert coverage["skg_query_api_route"] == "polisyos.data_forge.read_api.academic.SKGQuery"
    assert coverage["skg_query_construction_status"] == "pass"
    assert coverage["index_dir_status"] == "pass"
    assert coverage["required_tables_present"] is True
    assert coverage["required_table_counts"]["ac_skg_edges"] >= 7607
    assert coverage["required_table_counts"]["ac_skg_transport_scores"] >= 7607
    assert coverage["skg_snapshot_ref"]
    assert coverage["snapshot_hash_ref"].startswith("sha256:")
    assert {
        "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/manifests/graph_index.json",
        "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/manifests/qc.json",
    } <= set(coverage["manifest_refs"])


def test_g2_l2_skg_coverage_fails_when_required_transport_scores_table_is_missing(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(
        tmp_path,
        include_transport_scores=False,
    )
    g2 = _g2()
    monkeypatch.setattr(g2, "ACADEMIC_SKG_DB_PATH", db_path.relative_to(tmp_path))
    monkeypatch.setattr(g2, "ACADEMIC_INDEX_DIR", academic_root.relative_to(tmp_path))

    coverage = _dump(g2.build_g2_l2_skg_index_coverage(tmp_path))

    assert coverage["status"] == "fail"
    assert "ac_skg_transport_scores" in coverage["missing_tables"]
    assert "layer3_g2_l2_skg_index_coverage_missing" in coverage["issue_codes"]


def test_g2_l2_skg_coverage_fails_when_index_dir_points_at_graph_dir(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(tmp_path)
    g2 = _g2()
    monkeypatch.setattr(g2, "ACADEMIC_SKG_DB_PATH", db_path.relative_to(tmp_path))
    monkeypatch.setattr(g2, "ACADEMIC_INDEX_DIR", (academic_root / "graph").relative_to(tmp_path))

    coverage = _dump(g2.build_g2_l2_skg_index_coverage(tmp_path))

    assert coverage["status"] == "fail"
    assert coverage["index_dir_status"] == "fail"
    assert coverage["hnsw_assets_status"] == "fail"
    assert "layer3_g2_skg_index_dir_misconfigured" in coverage["issue_codes"]


def test_g2_l2_skg_search_emits_replayable_trace_and_control_plane_ledger() -> None:
    g2 = _g2()
    request = g2.Layer3G2CausalForecastRequest(
        request_id="g2-request:credit-access-firm-survival",
        case_id="ua-msme-affordable-loans-2022",
        source_contract_refs=("source-contract://ua-msme/server-support",),
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        target_context_id="UA",
        limit=4,
    )

    result = g2.search_l2_skg_for_forecast_candidates(request, REPO_ROOT)
    ledger = _dump(result.ledger)
    traces = [_dump(trace) for trace in result.query_traces]

    assert ledger["canonical_l2_route"] == "scholar_knowledge.duckdb"
    assert ledger["authoritative_for"] == []
    assert "search_hit_as_authority" in ledger["may_not_use_for"]
    assert ledger["selected_candidate_refs"]
    assert ledger["forecast_support_refs"] == []
    assert ledger["query_trace_refs"]
    assert traces
    assert all(
        trace["query_api_route"] == "polisyos.data_forge.read_api.academic.SKGQuery"
        for trace in traces
    )
    assert any("ac_skg_edges" in trace["table_refs"] for trace in traces)
    assert any(trace["result_count"] >= 1 for trace in traces)
    assert all(trace["skg_snapshot_ref"] for trace in traces)


def test_g2_validator_requires_trace_for_consumed_skg_query_result() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "l2_skg_search_ledgers": [
                {
                    "ledger_id": "g2-ledger:missing-trace",
                    "event_type": "selected_candidate",
                    "request_ref": "g2-request:missing-trace",
                    "canonical_l2_route": "scholar_knowledge.duckdb",
                    "query_trace_refs": ["g2-trace:missing"],
                    "searched_table_refs": ["ac_skg_edges"],
                    "selected_candidate_refs": ["skg-edge://edge-1"],
                    "replay_key": "g2-ledger:missing-trace:replay",
                }
            ],
            "l2_skg_query_traces": [],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert "layer3_g2_skg_query_trace_missing" in _issue_codes(report)


@pytest.mark.parametrize(
    ("surrogate_route", "issue_code"),
    [
        ("capability_index", "layer3_g2_capability_index_used_as_l2_search"),
        ("fixture", "layer3_g2_unjustified_l2_surrogate"),
        ("compiler_claim_view", "layer3_g2_unjustified_l2_surrogate"),
    ],
)
def test_g2_validator_rejects_noncanonical_l2_surrogate_routes(
    surrogate_route: str,
    issue_code: str,
) -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "l2_skg_search_ledgers": [
                {
                    "ledger_id": f"g2-ledger:{surrogate_route}",
                    "event_type": "selected_candidate",
                    "request_ref": "g2-request:surrogate",
                    "canonical_l2_route": surrogate_route,
                    "query_trace_refs": ["g2-trace:surrogate"],
                    "searched_table_refs": ["ac_skg_edges"],
                    "replay_key": f"g2-ledger:{surrogate_route}:replay",
                }
            ],
            "l2_skg_query_traces": [
                {
                    "trace_id": "g2-trace:surrogate",
                    "query_api_route": "polisyos.data_forge.read_api.academic.SKGQuery",
                    "canonical_l2_route": surrogate_route,
                    "table_refs": ["ac_skg_edges"],
                    "predicates": {},
                    "limit": 1,
                    "result_count": 0,
                    "row_refs": [],
                    "skg_snapshot_ref": "duckdb://fixture#v1",
                }
            ],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert issue_code in _issue_codes(report)


def test_g2_validator_blocks_semantic_retrieval_without_query_vector_producer() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "l2_skg_search_ledgers": [
                {
                    "ledger_id": "g2-ledger:semantic-no-vector",
                    "event_type": "semantic_candidate",
                    "request_ref": "g2-request:semantic-no-vector",
                    "canonical_l2_route": "scholar_knowledge.duckdb",
                    "query_trace_refs": ["g2-trace:semantic-no-vector"],
                    "searched_table_refs": ["ac_work_index.hnsw", "ac_skg_edges"],
                    "selected_candidate_refs": ["hnsw-work://work-1"],
                    "semantic_retrieval_required": True,
                    "query_vector_producer_ref": None,
                    "replay_key": "g2-ledger:semantic-no-vector:replay",
                }
            ],
            "l2_skg_query_traces": [
                {
                    "trace_id": "g2-trace:semantic-no-vector",
                    "query_api_route": "polisyos.data_forge.read_api.academic.SKGQuery",
                    "canonical_l2_route": "scholar_knowledge.duckdb",
                    "table_refs": ["ac_work_index.hnsw", "ac_skg_edges"],
                    "predicates": {"semantic_retrieval_required": True},
                    "limit": 4,
                    "result_count": 1,
                    "row_refs": ["hnsw-work://work-1"],
                    "semantic_retrieval_required": True,
                    "query_vector_producer_ref": None,
                    "skg_snapshot_ref": "duckdb://fixture#v1",
                }
            ],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert "layer3_g2_semantic_retrieval_without_query_vector_producer" in _issue_codes(report)


def test_g2_validator_blocks_search_hit_without_adapter_s10_validation_as_support() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "l2_skg_search_ledgers": [
                {
                    "ledger_id": "g2-ledger:hit-as-support",
                    "event_type": "selected_candidate",
                    "request_ref": "g2-request:hit-as-support",
                    "canonical_l2_route": "scholar_knowledge.duckdb",
                    "query_trace_refs": ["g2-trace:hit-as-support"],
                    "searched_table_refs": ["ac_skg_edges"],
                    "selected_candidate_refs": ["skg-edge://edge-1"],
                    "forecast_support_refs": ["forecast-support://forged-from-search-hit"],
                    "replay_key": "g2-ledger:hit-as-support:replay",
                }
            ],
            "l2_skg_query_traces": [
                {
                    "trace_id": "g2-trace:hit-as-support",
                    "query_api_route": "polisyos.data_forge.read_api.academic.SKGQuery",
                    "canonical_l2_route": "scholar_knowledge.duckdb",
                    "table_refs": ["ac_skg_edges"],
                    "predicates": {},
                    "limit": 1,
                    "result_count": 1,
                    "row_refs": ["skg-edge://edge-1"],
                    "skg_snapshot_ref": "duckdb://fixture#v1",
                }
            ],
            "forecast_support_bindings": [],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert "layer3_g2_search_hit_used_as_forecast_support" in _issue_codes(report)


def test_g2_search_recall_freshness_recalls_real_edge_and_transport_seed() -> None:
    report = _dump(_g2().build_g2_search_recall_freshness(REPO_ROOT))

    assert report["status"] == "pass"
    assert report["search_recall_status"] == "pass"
    assert report["index_freshness_status"] == "pass"
    assert report["hnsw_freshness_status"] == "not_required_for_request"
    assert report["hnsw_query_vector_producer_status"] == "not_required_for_request"
    assert {
        "g2-recall-seed:canonical-edge:fertilizer-use-food-nutritional-quality",
        "g2-recall-seed:transport-score:fertilizer-use-food-nutritional-quality:UA",
    } <= set(report["recalled_seed_refs"])
    assert any(
        "skg-edge://06fb46cd681818bc52d1cc01" in seed["expected_row_refs"]
        for seed in report["seed_records"]
    )
    assert any(
        "skg-transport://06fb46cd681818bc52d1cc01:UA" in seed["expected_row_refs"]
        for seed in report["seed_records"]
    )


def test_g2_search_recall_seed_miss_blocks_domain_ceiling() -> None:
    g2 = _g2()
    missing_seed = g2.Layer3G2SearchRecallSeed(
        seed_id="g2-recall-seed:missing-edge",
        cause="missing.cause",
        effect="missing.effect",
        expected_row_refs=("skg-edge://missing-edge",),
    )

    report = _dump(g2.build_g2_search_recall_freshness(REPO_ROOT, seeds=(missing_seed,)))

    assert report["status"] == "fail"
    assert report["search_recall_status"] == "fail"
    assert report["missed_seed_refs"] == ["g2-recall-seed:missing-edge"]
    assert "layer3_g2_search_recall_seed_miss_blocks_domain_ceiling" in report["issue_codes"]


def test_g2_search_recall_freshness_marks_stale_manifest_as_repair_required(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(tmp_path, stale_manifest=True)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    seed = g2.Layer3G2SearchRecallSeed(
        seed_id="g2-recall-seed:fixture-edge",
        cause="policy.credit_access",
        effect="firm.survival",
        expected_row_refs=("skg-edge://edge-1",),
    )

    report = _dump(g2.build_g2_search_recall_freshness(tmp_path, seeds=(seed,)))

    assert report["status"] == "fail"
    assert report["index_freshness_status"] == "fail"
    assert "layer3_g2_stale_index_blocks_domain_ceiling" in report["issue_codes"]


def test_g2_exact_recall_is_not_blocked_by_missing_hnsw_when_semantic_path_not_required(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(tmp_path, include_hnsw_assets=False)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    seed = g2.Layer3G2SearchRecallSeed(
        seed_id="g2-recall-seed:fixture-edge",
        cause="policy.credit_access",
        effect="firm.survival",
        expected_row_refs=("skg-edge://edge-1",),
    )

    report = _dump(g2.build_g2_search_recall_freshness(tmp_path, seeds=(seed,)))

    assert report["status"] == "pass"
    assert report["search_recall_status"] == "pass"
    assert report["hnsw_freshness_status"] == "not_required_for_request"
    assert report["hnsw_query_vector_producer_status"] == "not_required_for_request"


def test_g2_semantic_retrieval_fails_without_hnsw_assets_when_required(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(tmp_path, include_hnsw_assets=False)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    seed = g2.Layer3G2SearchRecallSeed(
        seed_id="g2-recall-seed:fixture-semantic-edge",
        cause="policy.credit_access",
        effect="firm.survival",
        expected_row_refs=("skg-edge://edge-1",),
        requires_semantic_retrieval=True,
    )

    report = _dump(
        g2.build_g2_search_recall_freshness(
            tmp_path,
            seeds=(seed,),
            semantic_retrieval_required=True,
            query_vector_producer_ref="producer://fixture-query-vector",
            query_vector_ref="query-vector://fixture",
        )
    )

    assert report["status"] == "fail"
    assert report["hnsw_freshness_status"] == "fail"
    assert "layer3_g2_stale_index_blocks_domain_ceiling" in report["issue_codes"]


def test_g2_semantic_retrieval_records_query_vector_and_post_hnsw_validation(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(tmp_path)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    seed = g2.Layer3G2SearchRecallSeed(
        seed_id="g2-recall-seed:fixture-semantic-edge",
        cause="policy.credit_access",
        effect="firm.survival",
        expected_row_refs=("skg-edge://edge-1",),
        requires_semantic_retrieval=True,
    )

    report = _dump(
        g2.build_g2_search_recall_freshness(
            tmp_path,
            seeds=(seed,),
            semantic_retrieval_required=True,
            query_vector_producer_ref="producer://fixture-query-vector",
            query_vector_ref="query-vector://fixture",
        )
    )

    assert report["status"] == "pass"
    assert report["hnsw_freshness_status"] == "pass"
    assert report["hnsw_query_vector_producer_status"] == "pass"
    assert report["query_vector_producer_ref"] == "producer://fixture-query-vector"
    assert report["query_vector_ref"] == "query-vector://fixture"
    assert report["hnsw_settings"]["ef"] == 100
    assert report["semantic_candidate_row_refs"] == ["skg-edge://edge-1"]
    assert report["post_hnsw_duckdb_validation_trace_refs"]


def test_g2_free_growth_discovers_added_skg_edge_and_method_fixture(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(tmp_path)
    _write_g2_data_home_fixture(tmp_path)
    method_path = _write_method_registry_fixture(tmp_path)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    monkeypatch.setattr(
        g2, "G2_FREE_GROWTH_METHOD_REGISTRY_PATH", method_path.relative_to(tmp_path)
    )

    report = _dump(g2.build_g2_free_growth_report(tmp_path))

    assert report["status"] == "pass"
    assert report["free_growth_fixture_count"] == 2
    assert report["discovered_skg_edge_ref"] == "skg-edge://edge-1"
    assert report["discovered_method_ref"] == "method://fixture.synthetic-causal-forecast"


def test_g2_free_growth_fails_when_fixture_edge_or_method_is_missing(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path, academic_root = _create_minimal_skg_fixture(tmp_path)
    _write_g2_data_home_fixture(tmp_path)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    monkeypatch.setattr(
        g2,
        "G2_FREE_GROWTH_METHOD_REGISTRY_PATH",
        Path("missing_method_registry_fixture.json"),
    )

    report = _dump(g2.build_g2_free_growth_report(tmp_path))

    assert report["status"] == "fail"
    assert "layer3_g2_free_growth_fixture_failed" in report["issue_codes"]


def test_task6_g2_temp_skg_edge_insertion_is_replayable_but_not_admitted_without_calibration(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from polisyos.runtime.quality.proving_ground.status_decision_reducers import (
        G2ForecastAdmissionInputs,
        Layer3ReducerInputRef,
        reduce_g2_forecast_admission,
    )

    db_path, academic_root = _create_minimal_skg_fixture(tmp_path)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    request = _g2_forecast_request()

    search_result = g2.search_l2_skg_for_forecast_candidates(request, tmp_path)
    binding = _dump(_g2_forecast_binding(search_result=search_result, calibration_payload=None))
    decision = reduce_g2_forecast_admission(
        G2ForecastAdmissionInputs(
            method_binding_status="pass",
            calibration_status="missing",
            skg_edge_type="ForecastSupport",
            input_refs=(
                Layer3ReducerInputRef(
                    ref="duckdb://task6-temp-skg#skg-edge://edge-1",
                    content_hash=_sha("6"),
                    producer_ref="measurement://layer3-g2/task6-temp-skg",
                    producer_type="measurement",
                    producer_root_refs=("measurement://layer3-g2/task6-temp-skg-root",),
                ),
            ),
        )
    )

    ledger = _dump(search_result.ledger)
    traces = [_dump(trace) for trace in search_result.query_traces]
    assert "skg-edge://edge-1" in ledger["selected_candidate_refs"]
    assert ledger["forecast_support_refs"] == []
    assert ledger["authoritative_for"] == []
    assert "search_hit_as_authority" in ledger["may_not_use_for"]
    assert ledger["query_trace_refs"]
    assert ledger["replay_key"]
    assert "skg-edge://edge-1" in ledger["duckdb_validated_candidate_refs"]
    assert traces
    assert any("skg-edge://edge-1" in trace["row_refs"] for trace in traces)
    assert all(trace["skg_snapshot_ref"] for trace in traces)
    assert "skg-edge://edge-1" in binding["skg_edge_refs"]
    assert binding["calibration_record_ref"] is None
    assert "layer3_g2_observable_calibration_required" in binding["issue_codes"]
    assert decision.status == "typed_blocker"
    assert "layer3_g2_calibration_not_admitted" in decision.blocker_refs


def test_task6_g2_temp_skg_edge_plus_governed_calibration_changes_reducer_admission(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from polisyos.runtime.quality.proving_ground.status_decision_reducers import (
        G2ForecastAdmissionInputs,
        Layer3ReducerInputRef,
        reduce_g2_forecast_admission,
    )

    db_path, academic_root = _create_minimal_skg_fixture(tmp_path)
    g2 = _g2()
    _patch_skg_paths(monkeypatch, g2, tmp_path, db_path, academic_root)
    request = _g2_forecast_request()

    search_result = g2.search_l2_skg_for_forecast_candidates(request, tmp_path)
    binding_obj = _g2_forecast_binding(
        search_result=search_result,
        calibration_payload=_g2_calibration_payload(),
    )
    calibration = _dump(g2.build_g2_observable_calibration_report((binding_obj,)))
    decision = reduce_g2_forecast_admission(
        G2ForecastAdmissionInputs(
            method_binding_status="pass",
            calibration_status=calibration["status"],
            skg_edge_type="ForecastSupport",
            input_refs=(
                Layer3ReducerInputRef(
                    ref="pdc://layer3/g2/task6/governed-calibration",
                    content_hash=_sha("7"),
                    producer_ref="measurement://layer3-g2/task6-governed-calibration",
                    producer_type="measurement",
                    producer_root_refs=("measurement://layer3-g2/task6-governed-calibration-root",),
                ),
            ),
        )
    )

    binding = _dump(binding_obj)
    assert "skg-edge://edge-1" in binding["skg_edge_refs"]
    assert binding["status"] == "pass"
    assert binding["calibration_record_ref"]
    assert calibration["status"] == "pass"
    assert calibration["calibration_record_refs"] == [binding["calibration_record_ref"]]
    assert decision.status == "forecast_admitted"
    assert decision.blocker_refs == ()


def test_g2_search_engineering_quality_requires_bounded_indexed_replayable_search() -> None:
    g2 = _g2()
    request = g2.Layer3G2CausalForecastRequest(
        request_id="g2-request:engineering-quality",
        case_id="ua-msme-affordable-loans-2022",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        target_context_id="UA",
        limit=4,
    )
    result = g2.search_l2_skg_for_forecast_candidates(request, REPO_ROOT)

    report = _dump(g2.build_g2_search_engineering_quality_report(REPO_ROOT, result))

    assert report["status"] == "pass"
    assert report["duckdb_predicate_search_status"] == "pass"
    assert report["lazy_bounded_read_status"] == "pass"
    assert report["deterministic_replay_status"] == "pass"
    assert {"duckdb", "SKGQuery"} <= set(report["named_library_refs"])
    assert report["eager_full_corpus_scan_count"] == 0


def test_g2_search_engineering_quality_rejects_eager_or_unbounded_search_markers() -> None:
    report = _dump(
        _g2().build_g2_search_engineering_quality_report(
            REPO_ROOT,
            None,
            eager_full_corpus_scan_count=1,
            unbounded_query_count=1,
        )
    )

    assert report["status"] == "fail"
    assert report["eager_full_corpus_scan_count"] == 1
    assert report["unbounded_query_count"] == 1
    assert "layer3_g2_search_engineering_quality_failed" in report["issue_codes"]


def test_g2_foundry_method_registry_coverage_bootstraps_real_catalog_and_discovery() -> None:
    report = _dump(_g2().build_g2_foundry_method_registry_coverage(REPO_ROOT))

    assert report["status"] == "pass"
    assert report["registered_method_count"] >= 300
    assert report["freshness_status"] == "pass"
    assert report["discovery_refresh_status"] == "pass"
    assert (
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered"
        in report["built_in_catalog_bootstrap_refs"]
    )
    assert "polisyos.foundry.methods.catalog" in report["discovery_source_roots"]
    assert "polisyos.foundry.methods" in report["entry_point_groups"]
    assert report["family_method_counts"]["causal"] > 0
    assert report["family_method_counts"]["forecasting"] > 0
    assert report["family_method_counts"]["econometrics"] > 0
    assert report["family_method_counts"]["sensitivity"] > 0
    assert report["family_method_counts"]["validation"] > 0
    assert report["registry_snapshot_ref"].startswith("foundry-method-registry-snapshot:")
    assert report["registry_version_ref"].startswith("foundry-method-registry-version:")
    assert report["registry_stats"]["total_methods"] == report["registered_method_count"]
    assert report["duplicate_method_refs"] == []
    assert report["discovery_errors"] == []


def test_g2_foundry_method_search_uses_registry_predicates_and_replay_ledger() -> None:
    request = _g2_forecast_request()

    report = _dump(_g2().search_foundry_methods_for_forecast(request))

    assert report["status"] == "pass"
    assert report["search_strategy"] == "registry_metadata_predicate_search"
    assert report["hardcoded_fqn_closure"] is False
    assert report["candidate_methods"]
    assert report["selected_methods"]
    assert report["registry_snapshot_ref"].startswith("foundry-method-registry-snapshot:")
    assert report["search_ledger_refs"]
    assert report["task_affinity_predicates"]["requested_task_tags"] == [
        "causal_effect_estimation",
        "forecasting",
        "uncertainty",
        "validation",
    ]
    assert report["data_affinity_predicates"]["data_modality"] == "panel"
    assert any("tags" in candidate["match_predicates"] for candidate in report["candidate_methods"])
    assert any(
        candidate["method_family"] in {"causal_effect_estimation", "forecasting"}
        for candidate in report["selected_methods"]
    )


def test_g2_foundry_method_search_rejects_hardcoded_fqn_closure() -> None:
    report = _dump(
        _g2().search_foundry_methods_for_forecast(
            _g2_forecast_request(),
            hardcoded_method_fqns=("causal.did.difference_in_differences@1.0.0",),
        )
    )

    assert report["status"] == "fail"
    assert report["hardcoded_fqn_closure"] is True
    assert "layer3_g2_method_registry_hardcode_closure" in report["issue_codes"]


def test_g2_method_requirement_binding_rejects_registered_method_only_support() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    search = g2.search_foundry_methods_for_forecast(request)

    bindings = g2.build_g2_method_requirement_bindings(request, search)
    binding = _dump(bindings[0])

    assert binding["status"] == "fail"
    assert binding["selection_status"] == "fail"
    assert binding["candidate_method_refs"]
    assert binding["selected_method_refs"] == []
    assert binding["method_requirement_refs"]
    assert "layer3_g2_method_requirement_selection_failed" in binding["issue_codes"]
    assert "method_requirement_no_selected_method" in binding["selection_issue_codes"]


def test_g2_method_requirement_binding_selects_runtime_valid_method_candidate() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    search = g2.search_foundry_methods_for_forecast(request)

    bindings = g2.build_g2_method_requirement_bindings(
        request,
        search,
        runtime_method_candidates=(_runtime_method_candidate(),),
    )
    binding = _dump(bindings[0])

    assert binding["status"] == "pass"
    assert binding["selection_status"] == "pass"
    assert binding["selected_method_refs"] == ["causal.did.runtime"]
    assert binding["rejected_method_refs"]
    assert "causal.did.runtime" not in binding["rejected_method_refs"]
    assert binding["method_requirement_statuses"] == {
        "g2-method-req:credit-access-firm-survival": "satisfied"
    }


def test_g2_method_validity_transport_reuses_foundry_report_and_preserves_authority() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    search = g2.search_foundry_methods_for_forecast(request)
    binding = g2.build_g2_method_requirement_bindings(
        request,
        search,
        runtime_method_candidates=(_runtime_method_candidate(),),
    )[0]

    record = _dump(
        g2.build_g2_method_validity_transport_record(
            request,
            binding,
            method_candidates=(_runtime_method_candidate(),),
        )
    )

    assert record["status"] == "pass"
    assert record["foundry_method_report_status"] == "pass"
    assert record["foundry_method_report_ref"].startswith("foundry-method-report:")
    assert record["cas_persistence_status"] == "out_of_scope"
    assert record["identification_requirement_refs"]
    assert record["transportability_limit_refs"]
    assert record["uncertainty_ref_count"] >= 1
    assert "method_validity" in record["authority_envelope"]["authoritative_for"]
    assert "legal_authority" in record["authority_envelope"]["may_not_use_for"]
    assert "claim_support_without_claim_registry_bridge" in record["may_not_use_for"]


def test_g2_method_validity_transport_fails_without_required_method_surfaces() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    search = g2.search_foundry_methods_for_forecast(request)
    invalid_method = _runtime_method_candidate(
        identification_requirements={},
        uncertainty={},
        uncertainty_refs={},
        transportability_limits={},
        method_result_refs={},
        validity_surfaces={},
    )
    binding = g2.build_g2_method_requirement_bindings(
        request,
        search,
        runtime_method_candidates=(invalid_method,),
    )[0]

    record = _dump(
        g2.build_g2_method_validity_transport_record(
            request,
            binding,
            method_candidates=(invalid_method,),
        )
    )

    assert record["status"] == "fail"
    assert "layer3_g2_method_validity_missing" in record["issue_codes"]
    assert "layer3_g2_identification_requirement_missing" in record["issue_codes"]
    assert "layer3_g2_transportability_limit_missing" in record["issue_codes"]


def test_g2_validator_blocks_method_hardcode_and_method_report_authority_overclaim() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "foundry_method_registry_search": {
                "report_id": "layer3-g2-foundry-method-registry-search",
                "status": "fail",
                "search_strategy": "hardcoded_fqn_list",
                "hardcoded_fqn_closure": True,
                "issue_codes": ["layer3_g2_method_registry_hardcode_closure"],
            },
            "method_validity_transport": [
                {
                    "record_id": "layer3-g2-method-validity-overclaim",
                    "status": "pass",
                    "foundry_method_report_status": "pass",
                    "authority_envelope": {
                        "authoritative_for": ["legal_authority", "closeout_pass"],
                        "may_not_use_for": [],
                    },
                    "authoritative_for": ["legal_authority"],
                    "may_not_use_for": [],
                }
            ],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert "layer3_g2_method_registry_hardcode_closure" in _issue_codes(report)
    assert "layer3_g2_foundry_method_report_authority_overclaim" in _issue_codes(report)


def test_g2_semantic_spine_binding_reuses_producer_spine_context_and_fields() -> None:
    g2 = _g2()

    binding = _dump(g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0])

    assert binding["status"] == "pass"
    assert binding["capability_reality_label"] == "implemented"
    assert binding["direct_semantic_grounding_allowed"] is True
    assert binding["producer_spine_context"]["concept_spine_ref"] == (
        "concept-spine://ua-msme/credit-access-survival"
    )
    assert {"scholar", "foundry"} <= {
        view["consumer_component"] for view in binding["producer_spine_views"]
    }
    assert binding["producer_spine_binding_fields"]["candidate_spine_binding_refs"]
    assert "namespace://skg/academic" in binding["governed_namespace_refs"]


def test_g2_semantic_spine_binding_fails_closed_without_spine_or_with_parallel_lattice() -> None:
    g2 = _g2()

    missing = _dump(
        g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs(concept_spine_ref=None))[0]
    )
    parallel = _dump(
        g2.build_g2_semantic_spine_bindings(
            **_g2_semantic_spine_kwargs(parallel_concept_lattice_declared=True)
        )[0]
    )

    assert missing["status"] == "fail"
    assert missing["capability_reality_label"] == "bridge_missing"
    assert "layer3_g2_semantic_binding_spine_missing" in missing["issue_codes"]
    assert parallel["status"] == "fail"
    assert "layer3_g2_parallel_concept_lattice" in parallel["issue_codes"]


def test_g2_concept_alignment_ties_g1_skg_foundry_and_s10_refs() -> None:
    g2 = _g2()
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]

    alignment = _dump(
        g2.build_g2_concept_alignment_records(**_g2_concept_alignment_kwargs(g2, semantic))[0]
    )

    assert alignment["status"] == "pass"
    assert alignment["alignment_status"] == "direct"
    assert alignment["source_contract_refs"] == ["source-contract://ua-msme/server-support"]
    assert alignment["skg_cause_variable_ref"] == "skg-variable://policy.credit_access"
    assert alignment["skg_effect_variable_ref"] == "skg-variable://firm.survival"
    assert alignment["skg_parameter_refs"] == ["skg-parameter://parameter-1"]
    assert alignment["foundry_input_slot_refs"]
    assert alignment["s10_target_outcome_refs"] == ["outcome://firm-survival"]


def test_g2_concept_alignment_blocks_proxy_or_ambiguous_direct_grounding() -> None:
    g2 = _g2()
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]

    proxy = _dump(
        g2.build_g2_concept_alignment_records(
            **_g2_concept_alignment_kwargs(
                g2,
                semantic,
                alignment_status="proxy_only",
                proxy_disclosed=False,
                direct_grounding_claimed=True,
            )
        )[0]
    )
    ambiguous = _dump(
        g2.build_g2_concept_alignment_records(
            **_g2_concept_alignment_kwargs(
                g2,
                semantic,
                alignment_status="ambiguous",
                direct_grounding_claimed=True,
            )
        )[0]
    )

    assert proxy["status"] == "fail"
    assert "layer3_g2_proxy_alignment_undisclosed" in proxy["issue_codes"]
    assert ambiguous["status"] == "fail"
    assert "layer3_g2_ambiguous_alignment_overclaimed" in ambiguous["issue_codes"]


def test_g2_s10_prerequisite_binding_records_required_spine_without_skg_fabrication() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]
    alignment = g2.build_g2_concept_alignment_records(**_g2_concept_alignment_kwargs(g2, semantic))[
        0
    ]
    method_validity = _g2_method_validity_record(g2, request)

    binding = _dump(
        g2.build_g2_s10_prerequisite_bindings(
            **_g2_s10_prerequisite_kwargs(g2, semantic, alignment, method_validity)
        )[0]
    )

    assert binding["status"] == "pass"
    assert binding["s5_forecast_support_ref"].startswith("pdc://layer2/s5/")
    assert binding["s6_firewall_status_refs"]
    assert binding["s8_value_choice_provenance_ref"].startswith("pdc://layer2/s8/")
    assert binding["method_validity_refs"]
    assert binding["semantic_spine_binding_ref"] == _dump(semantic)["binding_id"]
    assert binding["concept_alignment_ref"] == _dump(alignment)["alignment_id"]
    assert not any(ref.startswith("skg-edge://") for ref in binding["s5_s6_s8_refs"])
    assert {
        "claim_authority",
        "policy_recommendation",
        "closeout_authority",
        "useful_design_credit",
    } <= set(binding["may_not_use_for"])


def test_g2_s10_prerequisite_binding_fails_without_s5_s6_s8_or_denials() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]
    alignment = g2.build_g2_concept_alignment_records(**_g2_concept_alignment_kwargs(g2, semantic))[
        0
    ]
    method_validity = _g2_method_validity_record(g2, request)

    binding = _dump(
        g2.build_g2_s10_prerequisite_bindings(
            **_g2_s10_prerequisite_kwargs(
                g2,
                semantic,
                alignment,
                method_validity,
                s5_forecast_support_ref=None,
                s6_firewall_status_refs=(),
                s8_value_choice_provenance_ref=None,
                may_not_use_for=("claim_authority",),
            )
        )[0]
    )

    assert binding["status"] == "fail"
    assert "layer3_g2_s5_s6_s8_refs_missing" in binding["issue_codes"]
    assert "layer3_g2_recommendation_authority_leak" in binding["issue_codes"]
    assert "layer3_g2_closeout_authority_leak" in binding["issue_codes"]
    assert "layer3_g2_useful_design_credit_leak" in binding["issue_codes"]


def test_g2_forecast_support_binding_uses_s10_builders_and_preserves_boundary() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    search_result = _g2_skg_search_result(g2, request)
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]
    alignment = g2.build_g2_concept_alignment_records(**_g2_concept_alignment_kwargs(g2, semantic))[
        0
    ]
    method_validity = _g2_method_validity_record(g2, request)
    prerequisite = g2.build_g2_s10_prerequisite_bindings(
        **_g2_s10_prerequisite_kwargs(g2, semantic, alignment, method_validity)
    )[0]

    binding = _dump(
        g2.build_g2_forecast_support_bindings(
            request=request,
            search_result=search_result,
            semantic_spine_binding=semantic,
            concept_alignment_record=alignment,
            s10_prerequisite_binding=prerequisite,
            method_validity_record=method_validity,
            requested_forecast_tier="observable_calibrated",
            calibration_payload=_g2_calibration_payload(),
        )[0]
    )

    assert binding["status"] == "pass"
    assert binding["s10_builder_ref"].endswith("build_forecast_support")
    assert binding["calibration_builder_ref"].endswith("build_forecast_calibration_record")
    assert binding["authority_envelope_builder_ref"].endswith(
        "verify_prediction_authority_envelope"
    )
    assert binding["integrity_summary_builder_ref"].endswith("summarize_forecast_support_integrity")
    assert binding["s10_forecast_support"]["forecast_tier"] == "observable_calibrated"
    assert binding["s10_forecast_support_ref"].startswith("pdc://layer3/g2/")
    assert binding["authority_envelope"]["denies_claim_authority"] is True
    assert binding["integrity_summary"]["forecast_support_refs"] == [
        binding["s10_forecast_support_ref"]
    ]
    assert binding["skg_edge_refs"] == ["skg-edge://edge-1"]
    assert binding["skg_parameter_refs"] == ["skg-parameter://parameter-1"]
    assert binding["search_ledger_refs"] == ["g2-ledger:credit-access-firm-survival"]
    assert "search_hit_as_authority" in binding["may_not_use_for"]


@pytest.mark.parametrize(
    ("prereq_overrides", "requested_tier", "expected_issue"),
    [
        (
            {"uncertainty_interval_refs": ()},
            "observable_calibrated",
            "layer3_g2_uncertainty_interval_missing",
        ),
        (
            {
                "s5_base_origin": "simulation_only",
                "s5_support_label": "simulation_only_system_effect",
            },
            "observable_calibrated",
            "layer3_g2_simulation_only_laundered",
        ),
        (
            {
                "s5_base_origin": "historical_prior",
                "s5_support_label": "historical_prior_system_context",
            },
            "transported_limited",
            "layer3_g2_historical_prior_laundered",
        ),
        (
            {
                "s5_base_origin": "transported_scholar_estimate",
                "s5_support_label": "transported_with_heavy_limitation",
                "limitation_refs": (),
            },
            "transported_limited",
            "layer3_g2_transport_limit_missing",
        ),
    ],
)
def test_g2_forecast_support_binding_fails_s10_required_negative_controls(
    prereq_overrides: dict[str, object],
    requested_tier: str,
    expected_issue: str,
) -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]
    alignment = g2.build_g2_concept_alignment_records(**_g2_concept_alignment_kwargs(g2, semantic))[
        0
    ]
    method_validity = _g2_method_validity_record(g2, request)
    prerequisite = g2.build_g2_s10_prerequisite_bindings(
        **_g2_s10_prerequisite_kwargs(
            g2,
            semantic,
            alignment,
            method_validity,
            **prereq_overrides,
        )
    )[0]

    binding = _dump(
        g2.build_g2_forecast_support_bindings(
            request=request,
            search_result=_g2_skg_search_result(g2, request),
            semantic_spine_binding=semantic,
            concept_alignment_record=alignment,
            s10_prerequisite_binding=prerequisite,
            method_validity_record=method_validity,
            requested_forecast_tier=requested_tier,
            calibration_payload=_g2_calibration_payload(),
        )[0]
    )

    assert binding["status"] == "fail"
    assert expected_issue in binding["issue_codes"]


def test_g2_forecast_support_binding_fails_observable_without_calibration_builder() -> None:
    g2 = _g2()
    request = _g2_forecast_request()
    semantic = g2.build_g2_semantic_spine_bindings(**_g2_semantic_spine_kwargs())[0]
    alignment = g2.build_g2_concept_alignment_records(**_g2_concept_alignment_kwargs(g2, semantic))[
        0
    ]
    method_validity = _g2_method_validity_record(g2, request)
    prerequisite = g2.build_g2_s10_prerequisite_bindings(
        **_g2_s10_prerequisite_kwargs(g2, semantic, alignment, method_validity)
    )[0]

    binding = _dump(
        g2.build_g2_forecast_support_bindings(
            request=request,
            search_result=_g2_skg_search_result(g2, request),
            semantic_spine_binding=semantic,
            concept_alignment_record=alignment,
            s10_prerequisite_binding=prerequisite,
            method_validity_record=method_validity,
            requested_forecast_tier="observable_calibrated",
            calibration_payload=None,
        )[0]
    )

    assert binding["status"] == "fail"
    assert "layer3_g2_observable_calibration_required" in binding["issue_codes"]
    assert binding["calibration_builder_ref"].endswith("build_forecast_calibration_record")


def test_g2_validator_blocks_malformed_task4_bindings() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "semantic_spine_bindings": [
                {
                    "binding_id": "g2-semantic:bad",
                    "status": "fail",
                    "capability_reality_label": "bridge_missing",
                    "parallel_concept_lattice_declared": True,
                    "issue_codes": [
                        "layer3_g2_semantic_binding_spine_missing",
                        "layer3_g2_parallel_concept_lattice",
                    ],
                }
            ],
            "concept_alignment_records": [
                {
                    "alignment_id": "g2-alignment:bad",
                    "status": "fail",
                    "alignment_status": "proxy_only",
                    "proxy_disclosed": False,
                    "direct_grounding_claimed": True,
                    "issue_codes": ["layer3_g2_proxy_alignment_undisclosed"],
                }
            ],
            "s10_prerequisite_bindings": [
                {
                    "binding_id": "g2-prereq:bad",
                    "status": "fail",
                    "s5_forecast_support_ref": None,
                    "s6_firewall_status_refs": [],
                    "s8_value_choice_provenance_ref": None,
                    "s8_value_tradeoff_disclosure_ref": None,
                    "may_not_use_for": [],
                    "issue_codes": ["layer3_g2_s5_s6_s8_refs_missing"],
                }
            ],
            "forecast_support_bindings": [
                {
                    "binding_id": "g2-forecast:bad",
                    "status": "fail",
                    "adapter_validation_ref": "adapter-validation://g2/bad",
                    "s10_forecast_support_ref": "pdc://layer3/g2/bad/forecast-support",
                    "requested_forecast_tier": "observable_calibrated",
                    "s10_forecast_tier": "simulation_only_advisory",
                    "calibration_record_ref": None,
                    "uncertainty_interval_refs": [],
                    "authoritative_for": ["claim_authority"],
                    "may_not_use_for": [],
                    "issue_codes": ["layer3_g2_s10_tier_derivation_mismatch"],
                }
            ],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert {
        "layer3_g2_semantic_binding_spine_missing",
        "layer3_g2_parallel_concept_lattice",
        "layer3_g2_proxy_alignment_undisclosed",
        "layer3_g2_s5_s6_s8_refs_missing",
        "layer3_g2_s10_tier_derivation_mismatch",
        "layer3_g2_claim_authority_leak",
        "layer3_g2_recommendation_authority_leak",
        "layer3_g2_closeout_authority_leak",
        "layer3_g2_useful_design_credit_leak",
    } <= _issue_codes(report)


def test_g2_observable_calibration_report_preserves_s10_time_roles_and_maturity() -> None:
    g2 = _g2()
    binding = _g2_forecast_binding(calibration_payload=_g2_calibration_payload())

    report = _dump(g2.build_g2_observable_calibration_report((binding,)))

    assert report["status"] == "pass"
    assert report["adapter_maturity"] == "calibrated"
    assert report["observable_subset_calibration_denominator"] == 4
    assert report["observable_subset_calibration_numerator"] == 4
    assert report["observable_subset_calibration_pass_rate"] == 1.0
    assert report["calibration_threshold_ref"].endswith("#s10")
    assert report["credible_evaluation_evidence_refs"] == ["evidence://ua-msme/credible-evaluation"]
    assert report["observed_outcome_refs"] == ["outcome://ua-msme/credit-access/observed"]
    assert set(report["time_role_refs"]) >= {
        "prediction_time",
        "observation_time",
        "policy_effective_time",
        "data_valid_time",
        "calibration_window_start",
        "calibration_window_end",
    }
    assert report["authority_envelope_refs"] == [_dump(binding)["authority_envelope_ref"]]


def test_g2_observable_calibration_report_fails_without_denominator_or_evidence() -> None:
    g2 = _g2()
    binding = _g2_forecast_binding(
        calibration_payload=_g2_calibration_payload(
            denominator=0,
            numerator=0,
            pass_rate=0.0,
            credible_evaluation_evidence_ref=None,
        ),
        requested_adapter_maturity="calibrated",
    )

    report = _dump(g2.build_g2_observable_calibration_report((binding,)))

    assert report["status"] == "fail"
    assert report["adapter_maturity"] == "fail_closed"
    assert "layer3_g2_observable_calibration_denominator_missing" in report["issue_codes"]
    assert "layer3_g2_credible_evaluation_evidence_missing" in report["issue_codes"]
    assert "layer3_g2_adapter_maturity_overclaim" in report["issue_codes"]


def test_g2_transport_limit_declaration_uses_skg_transport_and_method_limits() -> None:
    objects = _g2_task4_positive_objects(
        s5_base_origin="transported_scholar_estimate",
        s5_support_label="transported_with_heavy_limitation",
        limitation_refs=("limitation://transport/ua-msme",),
    )
    g2 = objects["g2"]
    request = objects["request"]
    search_result = _g2_skg_search_result(g2, request)
    binding = g2.build_g2_forecast_support_bindings(
        request=request,
        search_result=search_result,
        semantic_spine_binding=objects["semantic"],
        concept_alignment_record=objects["alignment"],
        s10_prerequisite_binding=objects["prerequisite"],
        method_validity_record=objects["method_validity"],
        requested_forecast_tier="transported_limited",
        calibration_payload=None,
    )[0]

    declaration = _dump(
        g2.build_g2_transport_limit_declarations(
            search_result=search_result,
            forecast_support_bindings=(binding,),
            method_validity_record=objects["method_validity"],
            jurisdiction_scope_ref="jurisdiction://UA",
            aggregation_scope_ref="aggregation://firm-level",
        )[0]
    )

    assert declaration["status"] == "pass"
    assert declaration["transport_status"] == "limited"
    assert declaration["skg_transport_score_refs"] == ["skg-transport://edge-1:UA"]
    assert declaration["transport_confidence_by_ref"] == {"skg-transport://edge-1:UA": 0.61}
    assert declaration["method_transportability_limit_refs"]
    assert declaration["jurisdiction_scope_ref"] == "jurisdiction://UA"
    assert declaration["aggregation_scope_ref"] == "aggregation://firm-level"
    assert declaration["uncertainty_interval_refs"] == ["interval://ua-msme/credit-access/95"]
    assert declaration["limitation_refs"] == ["limitation://transport/ua-msme"]


def test_g2_transport_limit_declaration_fails_transported_estimate_without_limitations() -> None:
    objects = _g2_task4_positive_objects(
        s5_base_origin="transported_scholar_estimate",
        s5_support_label="transported_with_heavy_limitation",
        limitation_refs=(),
    )
    g2 = objects["g2"]
    request = objects["request"]
    search_result = _g2_skg_search_result(g2, request)
    binding = g2.build_g2_forecast_support_bindings(
        request=request,
        search_result=search_result,
        semantic_spine_binding=objects["semantic"],
        concept_alignment_record=objects["alignment"],
        s10_prerequisite_binding=objects["prerequisite"],
        method_validity_record=objects["method_validity"],
        requested_forecast_tier="transported_limited",
        calibration_payload=None,
    )[0]

    declaration = _dump(
        g2.build_g2_transport_limit_declarations(
            search_result=search_result,
            forecast_support_bindings=(binding,),
            method_validity_record=objects["method_validity"],
            jurisdiction_scope_ref="jurisdiction://UA",
            aggregation_scope_ref="aggregation://firm-level",
        )[0]
    )

    assert declaration["status"] == "fail"
    assert "layer3_g2_transport_limit_missing" in declaration["issue_codes"]


def test_g2_contested_skg_edges_become_limitations_and_publish_blockers() -> None:
    objects = _g2_task4_positive_objects()
    g2 = objects["g2"]
    request = objects["request"]
    binding = _dump(
        g2.build_g2_forecast_support_bindings(
            request=request,
            search_result=_g2_contested_search_result(g2, request),
            semantic_spine_binding=objects["semantic"],
            concept_alignment_record=objects["alignment"],
            s10_prerequisite_binding=objects["prerequisite"],
            method_validity_record=objects["method_validity"],
            requested_forecast_tier="observable_calibrated",
            calibration_payload=_g2_calibration_payload(),
        )[0]
    )

    assert binding["status"] == "fail"
    assert binding["contested_edge_refs"] == ["skg-edge://contested-1"]
    assert binding["publish_blocker_refs"] == [
        "publish-blocker://layer3/g2/contested-edge/contested-1"
    ]
    assert "limitation://layer3/g2/contested-edge/contested-1" in binding["limitation_refs"]
    assert "layer3_g2_contested_edge_overclaimed" in binding["issue_codes"]


def test_g2_adapter_maturity_calibrated_requires_passed_calibration_and_bounded_envelope() -> None:
    calibrated = _dump(
        _g2_forecast_binding(
            calibration_payload=_g2_calibration_payload(),
            requested_adapter_maturity="calibrated",
        )
    )
    uncalibrated = _dump(
        _g2_forecast_binding(
            calibration_payload=None,
            requested_adapter_maturity="calibrated",
        )
    )

    assert calibrated["adapter_maturity"] == "calibrated"
    assert calibrated["maturity_blocker_refs"] == []
    assert uncalibrated["status"] == "fail"
    assert uncalibrated["adapter_maturity"] == "fail_closed"
    assert "layer3_g2_adapter_maturity_overclaim" in uncalibrated["issue_codes"]


def test_g2_equilibrium_system_effect_blocks_without_calibrated_dynamics_producer() -> None:
    binding = _dump(
        _g2_forecast_binding(
            s5_base_origin="equilibrium_contested",
            s5_support_label="equilibrium_contested",
            outcome_distribution_refs=("single-point-forecast://probe",),
            requested_forecast_tier="observable_calibrated",
            calibration_payload=_g2_calibration_payload(),
            calibrated_dynamics_producer_ref=None,
        )
    )

    assert binding["status"] == "fail"
    assert binding["s10_forecast_tier"] in {None, "equilibrium_contested_blocked"}
    assert binding["equilibrium_blocker_refs"] == [
        "equilibrium-blocker://layer3/g2/calibrated-dynamics-producer-missing"
    ]
    assert "layer3_g2_equilibrium_authority_overclaim" in binding["issue_codes"]


@pytest.mark.parametrize(
    ("fixture_name", "expected_issue"),
    [
        (
            "uncalibrated_observable_promotion_probe.json",
            "layer3_g2_observable_calibration_required",
        ),
        ("hidden_uncertainty_interval_probe.json", "layer3_g2_uncertainty_interval_missing"),
        ("transported_estimate_without_limitation_probe.json", "layer3_g2_transport_limit_missing"),
        ("simulation_only_evidence_laundering_probe.json", "layer3_g2_simulation_only_laundered"),
        (
            "equilibrium_contested_single_forecast_probe.json",
            "layer3_g2_equilibrium_authority_overclaim",
        ),
        (
            "production_authority_from_forecast_probe.json",
            "layer3_g2_recommendation_authority_leak",
        ),
    ],
)
def test_g2_reuses_s10_negative_probe_fixtures_for_downgrade_issue_codes(
    fixture_name: str,
    expected_issue: str,
) -> None:
    fixture = json.loads(
        (REPO_ROOT / "tests/fixtures/layer2/s10" / fixture_name).read_text(encoding="utf-8")
    )
    requested_tier = str(fixture["forecast_tier"])
    if fixture["failure_pattern"] in {
        "simulation_only_evidence_laundering",
        "equilibrium_contested_single_forecast",
    }:
        requested_tier = "observable_calibrated"
    calibration = (
        None
        if fixture["failure_pattern"] == "uncalibrated_observable_promotion"
        else _g2_calibration_payload()
    )

    binding = _dump(
        _g2_forecast_binding(
            s5_base_origin=fixture["s5_base_origin"],
            s5_support_label=fixture["s5_support_label"],
            s5_claim_scope=fixture["s5_claim_scope"],
            s6_limitation_refs=tuple(fixture.get("s6_limitation_refs", [])),
            limitation_refs=tuple(fixture.get("limitation_refs", [])),
            uncertainty_interval_refs=tuple(fixture.get("uncertainty_interval_refs", [])),
            outcome_distribution_refs=tuple(fixture.get("outcome_distribution_refs", [])),
            may_not_use_for=tuple(fixture["authority_boundary"].get("may_not_use_for", [])),
            requested_forecast_tier=requested_tier,
            calibration_payload=calibration,
        )
    )

    assert binding["status"] == "fail"
    assert expected_issue in binding["issue_codes"]


def test_g2_validator_blocks_malformed_task5_calibration_transport_and_maturity() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "observable_calibration_report": {
                "report_id": "layer3-g2-observable-calibration-report",
                "status": "fail",
                "adapter_maturity": "fail_closed",
                "observable_subset_calibration_denominator": 0,
                "observable_subset_calibration_numerator": 0,
                "observable_subset_calibration_pass_rate": 0.0,
                "credible_evaluation_evidence_refs": [],
                "issue_codes": [
                    "layer3_g2_observable_calibration_denominator_missing",
                    "layer3_g2_credible_evaluation_evidence_missing",
                ],
            },
            "transport_limit_declarations": [
                {
                    "declaration_id": "g2-transport-limit-declaration:bad",
                    "status": "fail",
                    "transport_status": "blocked",
                    "skg_transport_score_refs": [],
                    "method_transportability_limit_refs": [],
                    "uncertainty_interval_refs": [],
                    "limitation_refs": [],
                    "issue_codes": ["layer3_g2_transport_limit_missing"],
                }
            ],
            "forecast_support_bindings": [
                {
                    "binding_id": "g2-forecast:maturity-overclaim",
                    "status": "pass",
                    "adapter_validation_ref": "adapter-validation://g2/maturity-overclaim",
                    "s10_forecast_support_ref": "pdc://layer3/g2/forecast-support",
                    "requested_forecast_tier": "observable_calibrated",
                    "s10_forecast_tier": "observable_calibrated",
                    "calibration_record_ref": "pdc://layer3/g2/calibration",
                    "uncertainty_interval_refs": ["interval://ua-msme/95"],
                    "requested_adapter_maturity": "calibrated",
                    "adapter_maturity": "predictive",
                    "authoritative_for": ["g2_forecast_support_binding_audit"],
                    "may_not_use_for": list(_g2().G2_MAY_NOT_USE_FOR),
                }
            ],
        },
    )

    assert _dump(report)["status"] == "fail"
    assert {
        "layer3_g2_observable_calibration_denominator_missing",
        "layer3_g2_credible_evaluation_evidence_missing",
        "layer3_g2_transport_limit_missing",
        "layer3_g2_transportability_limit_missing",
        "layer3_g2_adapter_maturity_overclaim",
    } <= _issue_codes(report)


def test_g2_s10_forecast_posture_uses_public_pdc_contract_and_preserves_refs() -> None:
    from polisyos.pdc import Layer2S10ForecastPostureInput

    g2 = _g2()
    binding = _g2_forecast_binding(calibration_payload=_g2_calibration_payload())

    posture = g2.build_g2_s10_forecast_posture(binding)

    assert isinstance(posture, Layer2S10ForecastPostureInput)
    payload = posture.model_dump(mode="json")
    binding_payload = _dump(binding)
    assert payload["forecast_tier"] == "observable_calibrated"
    assert payload["forecast_support_ref"] == binding_payload["s10_forecast_support_ref"]
    assert payload["forecast_calibration_record_ref"] == binding_payload["calibration_record_ref"]
    assert payload["source_contract_ref"] == "source-contract://ua-msme/server-support"
    assert payload["method_validity_ref"] == "method-validity://foundry/causal/local"
    assert payload["uncertainty_interval_refs"] == ["interval://ua-msme/credit-access/95"]
    assert payload["s5_forecast_support_ref"].startswith("pdc://layer2/s5/")
    assert payload["s6_firewall_status_refs"]
    assert payload["s8_value_choice_provenance_ref"].startswith("pdc://layer2/s8/")
    assert {
        "claim_authority",
        "policy_recommendation",
        "closeout_authority",
        "useful_design_credit",
    } <= set(payload["may_not_use_for"])


def test_g2_w12d_consumer_gate_consumes_posture_without_authority_or_full_s2_overreach() -> None:
    g2 = _g2()
    binding = _g2_forecast_binding(calibration_payload=_g2_calibration_payload())
    posture = g2.build_g2_s10_forecast_posture(binding)

    gate = _dump(
        g2.build_g2_w12d_consumer_gate(
            forecast_postures=(posture,),
            forecast_support_bindings=(binding,),
            layer3_g1_grounding_gate_ref="layer3.g1.grounding_gate",
            full_s2_consumer_case_refs=("ua-msme-affordable-loans-2022",),
            lightweight_case_refs=("education-case", "housing-case"),
        )
    )

    assert gate["status"] == "pass"
    assert gate["layer3_g1_grounding_gate_ref"] == "layer3.g1.grounding_gate"
    assert gate["consumed_forecast_posture_refs"] == [_dump(binding)["s10_forecast_support_ref"]]
    assert gate["forecast_tiers"] == ["observable_calibrated"]
    assert gate["forecast_calibration_record_refs"] == [_dump(binding)["calibration_record_ref"]]
    assert gate["source_contract_refs"] == ["source-contract://ua-msme/server-support"]
    assert gate["method_validity_refs"] == ["method-validity://foundry/causal/local"]
    assert gate["uncertainty_interval_refs"] == ["interval://ua-msme/credit-access/95"]
    assert gate["full_s2_consumer_case_count"] == 1
    assert gate["lightweight_forecast_posture_ref_count"] == 2
    assert gate["useful_design_delta_count"] == 0
    assert gate["closeout_claimed"] is False
    assert gate["recommendation_authority_claimed"] is False
    assert gate["claim_authority_claimed"] is False
    assert "claim_authority" in gate["may_not_use_for"]
    assert gate["issue_codes"] == []


def test_g2_w12d_gate_fails_not_routed_and_full_s2_overreach_but_routes_domain_ceiling() -> None:
    g2 = _g2()
    binding = _g2_forecast_binding(calibration_payload=_g2_calibration_payload())
    posture = g2.build_g2_s10_forecast_posture(binding)

    not_routed = _dump(g2.build_g2_w12d_consumer_gate())
    overreach = _dump(
        g2.build_g2_w12d_consumer_gate(
            forecast_postures=(posture,),
            full_s2_consumer_case_refs=("ua-msme-affordable-loans-2022", "housing-case"),
        )
    )
    domain_ceiling = _dump(
        g2.build_g2_w12d_consumer_gate(
            domain_ceiling_status="causal_forecast_domain_ceiling",
            layer3_g1_grounding_gate_ref="layer3.g1.grounding_gate",
        )
    )

    assert not_routed["status"] == "fail"
    assert "layer3_g2_w12d_not_routed_closeout" in not_routed["issue_codes"]
    assert overreach["status"] == "fail"
    assert "layer3_g2_w12d_full_s2_overreach" in overreach["issue_codes"]
    assert domain_ceiling["status"] == "pass"
    assert domain_ceiling["domain_ceiling_status"] == "causal_forecast_domain_ceiling"
    assert domain_ceiling["posture_consumed"] is False
    assert domain_ceiling["layer3_g2_gate_injection_order"] == "after_g1_before_summary"
    assert "layer3_g2_w12d_domain_ceiling_gate_missing" not in domain_ceiling["issue_codes"]


def test_g2_grounded_forecast_handoff_preserves_replay_surface_without_promotion_credit() -> None:
    g2 = _g2()
    objects = _g2_task4_positive_objects()
    binding = _g2_forecast_binding(calibration_payload=_g2_calibration_payload())
    calibration = g2.build_g2_observable_calibration_report((binding,))
    transport = g2.build_g2_transport_limit_declarations(
        forecast_support_bindings=(binding,),
        jurisdiction_scope_ref="jurisdiction://UA",
        aggregation_scope_ref="unit://firm",
    )

    handoff = _dump(
        g2.build_g2_grounded_forecast_handoffs(
            forecast_support_bindings=(binding,),
            concept_alignment_records=(objects["alignment"],),
            observable_calibration_report=calibration,
            transport_limit_declarations=transport,
        )[0]
    )

    binding_payload = _dump(binding)
    assert handoff["status"] == "pass"
    assert handoff["s10_forecast_support_ref"] == binding_payload["s10_forecast_support_ref"]
    assert handoff["concept_alignment_ref"] == _dump(objects["alignment"])["alignment_id"]
    assert handoff["source_contract_ref"] == "source-contract://ua-msme/server-support"
    assert handoff["method_validity_refs"] == ["method-validity://foundry/causal/local"]
    assert handoff["calibration_record_refs"] == [binding_payload["calibration_record_ref"]]
    assert handoff["transport_limit_declaration_refs"] == [_dump(transport[0])["declaration_id"]]
    assert handoff["uncertainty_interval_refs"] == ["interval://ua-msme/credit-access/95"]
    assert handoff["adapter_maturity"] == "calibrated"
    assert handoff["search_ledger_refs"] == ["g2-ledger:credit-access-firm-survival"]
    assert handoff["skg_query_trace_refs"] == ["g2-trace:credit-access-firm-survival"]
    assert handoff["method_requirement_refs"]
    assert handoff["g4_g5_readable_handoff_ref"] == handoff["handoff_id"]
    assert handoff["promotion_authority_claimed"] is False
    assert handoff["conversion_authority_claimed"] is False
    assert handoff["useful_design_credit_claimed"] is False
    assert {"promotion_authority", "conversion_authority", "useful_design_credit"} <= set(
        handoff["may_not_use_for"]
    )


def test_g2_validator_blocks_not_routed_unconsumed_or_promoted_task6_records() -> None:
    report = _g2().validate_layer3_g2_bundle(
        REPO_ROOT,
        {
            "schema_version": G2_SCHEMA_VERSION,
            "rule_version": G2_RULE_VERSION,
            "forecast_support_bindings": [
                {
                    "binding_id": "g2-forecast:pass",
                    "status": "pass",
                    "adapter_validation_ref": "adapter-validation://g2/pass",
                    "s10_forecast_support_ref": "pdc://layer3/g2/pass/forecast-support",
                    "requested_forecast_tier": "observable_calibrated",
                    "s10_forecast_tier": "observable_calibrated",
                    "calibration_record_ref": "pdc://layer3/g2/pass/calibration",
                    "uncertainty_interval_refs": ["interval://ua-msme/95"],
                    "authoritative_for": ["g2_forecast_support_binding_audit"],
                    "may_not_use_for": list(_g2().G2_MAY_NOT_USE_FOR),
                }
            ],
            "grounded_forecast_handoffs": [
                {
                    "handoff_id": "g2-handoff:promoted",
                    "status": "pass",
                    "s10_forecast_support_ref": "pdc://layer3/g2/pass/forecast-support",
                    "authoritative_for": ["promotion_authority"],
                    "may_not_use_for": [],
                    "promotion_authority_claimed": True,
                    "conversion_authority_claimed": True,
                    "useful_design_credit_claimed": True,
                    "design_record_ledger_refs": ["pdc://layer2/s2/design-record-v0"],
                    "s2_deterministic_replay_key_refs": ["s2-replay-key://only"],
                    "source_contract_ref": "",
                    "method_validity_refs": [],
                    "skg_query_trace_refs": [],
                    "method_requirement_refs": [],
                }
            ],
            "w12d_consumer_gate": {
                "gate_id": "layer3.g2.w12d.forecast_gate",
                "status": "fail",
                "posture_consumed": False,
                "issue_codes": ["layer3_g2_w12d_not_routed_closeout"],
            },
            "readiness_manifest": {
                "schema_version": G2_SCHEMA_VERSION,
                "rule_version": G2_RULE_VERSION,
                "g1_dependency_status": "pass",
                "g2_method_requirement_binding_count": 1,
                "g2_semantic_spine_binding_count": 1,
                "g2_s10_prerequisite_binding_status": "pass",
                "g2_w12d_consumer_gate_status": "not_routed",
            },
        },
    )

    assert _dump(report)["status"] == "fail"
    assert {
        "layer3_g2_s10_posture_not_consumed",
        "layer3_g2_w12d_not_routed_closeout",
        "layer3_g2_grounded_forecast_handoff_promoted",
        "layer3_g2_s2_design_record_replay_overclaim",
    } <= _issue_codes(report)
