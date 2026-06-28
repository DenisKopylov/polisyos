from __future__ import annotations

from copy import deepcopy
from typing import Any

from polisyos.runtime.quality.assurance_case import (
    build_capability_duty_record,
    build_capability_selection_ledger,
    build_policy_design_case_concept_spine,
    build_policy_design_case_profile,
    build_policy_design_jurisdiction_spine,
    build_policy_intent_envelope,
)
from polisyos.runtime.quality.attestation import build_required_production_attestations
from polisyos.runtime.quality.case_integrity import (
    EVIDENCE_GRAPH_THREAT_MODEL_RECORD_FAMILY,
    EVIDENCE_GRAPH_THREAT_MODEL_SCHEMA_VERSION,
    EVIDENCE_GRAPH_THREATS,
)
from polisyos.runtime.quality.case_maturity import build_case_maturity_profile
from polisyos.runtime.quality.diagnostic_slos import (
    build_diagnostic_slo_report,
    pass_observations_for_all_diagnostic_slos,
)
from polisyos.runtime.quality.external_client_surface import (
    EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
)
from polisyos.runtime.quality.tenant_cas_approval_governance import (
    build_pass1b_tenant_cas_approval_governance_record,
)
from polisyos.runtime.quality.phase_barriers import PhaseBarrierId, PhaseBarrierRecord
from polisyos.runtime.quality.policy_design_case import (
    POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS,
    POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    PROMPT_TOOL_LEDGER_REF_KEY,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    SCHEMA_VERSION as PROMPT_TOOL_LEDGER_SCHEMA_VERSION,
)
from polisyos.runtime.quality.scorecard import (
    POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
    QUALITY_REPORT_FILES,
    QUALITY_REPORT_RUNTIME_REFS,
    build_quality_scorecard,
    normalize_quality_evidence,
)
from polisyos.runtime.quality.semantic_binding import (
    PRODUCER_SPINE_CONSUMER_COMPONENTS,
    PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
    SEMANTIC_BINDING_SCHEMA_VERSION,
)
from polisyos.scholar import build_scholar_academic_evidence_report

HDS_XFAIL_REASON = "HDS red control pending implementation"


def sha(char: str) -> str:
    return "sha256:" + char * 64


def policy_design_capability_ledger() -> dict[str, Any]:
    return build_capability_selection_ledger(
        ledger_ref=sha("5"),
        literature_evidence_required=True,
        duties=[
            build_capability_duty_record(
                capability=capability,
                state="selected",
                evidence_ref=sha(ref_char),
                runtime_event_ref=sha("e"),
            )
            for capability, ref_char in (
                ("lex", "6"),
                ("fabric", "7"),
                ("scholar", "8"),
                ("foundry", "9"),
                ("scientist", "a"),
                ("compiler", "b"),
                ("review", "c"),
                ("publication", "d"),
                ("audit", "f"),
            )
        ],
    )


def policy_design_intent_envelope() -> dict[str, Any]:
    return build_policy_intent_envelope(
        intent_id="intent-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-1",
        policy_problem="Wartime MSMEs face survival risk and constrained credit access.",
        desired_outcome="Improve MSME survival without unbounded fiscal exposure.",
        proposed_intervention="Target wartime credit support to eligible MSMEs.",
        jurisdiction="UA",
        target_population="wartime MSMEs",
        policy_time="2026-05-15",
        data_time="2024-2026",
        requester_preferred_conclusion="expand credit support",
        requested_authority_level="production",
        affected_stakeholders=[
            "MSMEs",
            "participating banks",
            "fiscal authorities",
            "auditors",
        ],
        objectives=["msme survival", "fiscal proportionality"],
        evidence_expectations=[
            "legal authority",
            "production data",
            "literature evidence",
            "method evidence",
        ],
        authoring_provenance={
            "captured_by": "runtime-control",
            "capture_ref": sha("4"),
        },
    )


def runtime_cas_refs() -> dict[str, str]:
    chars = "123456789abcdef0123456789abcdef"
    refs = {
        ref_key: sha(chars[index])
        for index, ref_key in enumerate(QUALITY_REPORT_RUNTIME_REFS.values())
    }
    refs[PROMPT_TOOL_LEDGER_REF_KEY] = sha("4")
    refs.update(
        {
            "policy_intent_envelope_ref": sha("0"),
            "policy_intent_ref": sha("0"),
            "policy_design_capability_ledger_ref": sha("5"),
            "policy_design_case_ref": sha("c"),
        }
    )
    return refs


def complete_scholar_academic_evidence() -> dict[str, Any]:
    return build_scholar_academic_evidence_report(
        scholar_evidence_ref=sha("8"),
        cas_ref=sha("8"),
        runtime_event_ref=sha("e"),
        research_intent={
            "intent_id": "research-intent-msme-survival",
            "question": "Does wartime credit support improve MSME survival?",
            "policy_domain": "wartime_msme_support",
            "jurisdictions": ["UA"],
            "required_source_types": ["academic", "grey_literature"],
        },
        query_graph={
            "graph_id": "query-graph-msme-survival",
            "root_query": "wartime credit support MSME survival Ukraine evidence",
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "wartime credit support MSME survival Ukraine evidence",
                    "perspective": "supporting academic and grey literature",
                }
            ],
        },
        provider_traces=[
            {
                "trace_id": "trace-q1-openalex",
                "provider": "openalex",
                "query_node_id": "q1",
                "hit_count": 2,
                "searched_at": "2026-05-17T08:30:00+00:00",
            }
        ],
        source_scoring=[
            {
                "source_id": "literature:msme-survival-review",
                "quality_score": 0.91,
                "freshness_score": 0.95,
                "relevance_score": 0.89,
                "independence_score": 1.0,
            }
        ],
        snippets=[
            {
                "snippet_id": "snippet:msme-survival-review:1",
                "source_id": "literature:msme-survival-review",
                "query_node_id": "q1",
                "text": "Credit constraints are associated with lower MSME survival.",
                "start_char": 120,
                "end_char": 186,
            }
        ],
        citations=[
            {
                "citation_id": "citation:msme-survival-review",
                "source_id": "literature:msme-survival-review",
                "snippet_ids": ["snippet:msme-survival-review:1"],
                "evidence_ref": sha("8"),
                "provenance_kind": "runtime_emitted",
                "source_surface": "scholar_retrieval",
            }
        ],
        freshness={
            "status": "pass",
            "as_of": "2026-05-17",
            "max_source_age_days": 730,
            "sources": [
                {
                    "source_id": "literature:msme-survival-review",
                    "published_at": "2025-09-01",
                    "age_days": 258,
                    "status": "pass",
                }
            ],
        },
        corpus_lineage={
            "knowledge_bundle_ref": sha("9"),
            "corpus_snapshot_ref": sha("a"),
            "lineage_ref": sha("b"),
        },
        selected_sources=[
            {
                "source_id": "literature:msme-survival-review",
                "source_family": "academic_peer_reviewed",
                "source_family_independence_tag": "academic_peer_reviewed:journal",
                "rights": "open_metadata",
            }
        ],
        rejected_sources=[
            {
                "source_id": "literature:procurement-fixture",
                "reason_code": "off_topic",
                "source_family": "grey_literature",
            }
        ],
        support_links=[
            {
                "link_id": "support:msme-survival-review:rec_1",
                "claim_id": "rec_1",
                "source_ids": ["literature:msme-survival-review"],
                "snippet_ids": ["snippet:msme-survival-review:1"],
                "citation_ids": ["citation:msme-survival-review"],
            }
        ],
        conflict_links=[
            {
                "link_id": "conflict:literature:resolved",
                "claim_id": "rec_1",
                "resolution": "No active contradiction after source screening.",
            }
        ],
        duplicate_markers=[],
        polarity_markers=[
            {
                "marker_id": "polarity:msme-survival-review:rec_1",
                "claim_id": "rec_1",
                "source_id": "literature:msme-survival-review",
                "snippet_id": "snippet:msme-survival-review:1",
                "polarity": "support",
                "support_status": "supported",
            }
        ],
        dependence_records=[
            {
                "record_id": "dependence:academic_peer_reviewed:journal",
                "claim_id": "rec_1",
                "source_ids": ["literature:msme-survival-review"],
                "source_family_independence_tag": "academic_peer_reviewed:journal",
                "dependence_basis": "single_source_family",
                "raw_source_count": 1,
                "effective_source_count": 1,
            }
        ],
        participation_downgrade_records=[
            {
                "record_id": "participation-downgrade:rec_1:none",
                "claim_id": "rec_1",
                "claim_use_requested": "academic_support",
                "claim_use_allowed": "academic_support",
                "authority_boundary": "scholar_academic_support_only",
                "downgrade_reason": "not_participation_claim",
            }
        ],
        literature_deficit_blockers=[],
        source_family_independence_tags={
            "literature:msme-survival-review": "academic_peer_reviewed:journal"
        },
    )


def complete_data_forge_snapshot_binding() -> dict[str, Any]:
    def binding(role: str, surface: str, char: str) -> dict[str, Any]:
        snapshot_ref = sha(char)
        return {
            "role": role,
            "snapshot_id": f"{role}-snapshot-R_hds_red_control",
            "snapshot_ref": snapshot_ref,
            "release_id": f"release-{role}-R_hds_red_control",
            "release_manifest_ref": "cas://sha256/" + char * 64,
            "manifest_ref": "cas://sha256/" + char * 64,
            "manifest_artifact_id": snapshot_ref,
            "artifact_ids": [snapshot_ref, sha("f")],
            "merkle_root": char * 64,
            "data_hash": snapshot_ref,
            "read_api_surface": surface,
            "read_api_module": f"polisyos.data_forge.read_api.{surface}",
            "read_api_identity": f"{surface}@{role}-snapshot-R_hds_red_control",
            "runtime_event_ref": f"event://data-forge/{role}/R_hds_red_control",
            "published_at": "2026-05-15T00:00:00+00:00",
            "freshness_ttl_seconds": 60 * 60 * 24 * 3650,
            "corpus_id": f"corpus-{role}",
            "provenance_manifest_ref": "cas://sha256/" + "e" * 64,
            "creation_time": "2026-05-15T00:00:00+00:00",
            "lineage_refs": [
                "cas://sha256/" + char * 64,
                f"event://data-forge/{role}/ingest",
            ],
            "builder_revision": "git:policyos-w9c-fixture",
            "transform_lineage": [
                {
                    "step_id": f"{role}.normalize",
                    "operation": "normalize",
                    "input_refs": ["cas://sha256/" + char * 64],
                    "output_refs": [snapshot_ref],
                    "code_ref": "git:policyos-w9c-fixture",
                    "config_ref": "cas://sha256/" + "e" * 64,
                }
            ],
            "quality_gates": [
                {
                    "name": f"{role}_publish_quality",
                    "status": "pass",
                    "artifact_id": sha(char),
                }
            ],
            "prov": {
                "entity": f"data-forge:{role}:snapshot",
                "activity": f"data-forge:{role}:publish",
                "agent": "team-data-forge",
            },
            "openlineage": {
                "namespace": "polisyos.data_forge",
                "job": {"name": f"{role}.publish"},
                "run": {"runId": f"run-{role}-R_hds_red_control"},
                "outputs": [
                    {
                        "name": f"{role}-snapshot-R_hds_red_control",
                        "facets": {
                            "dataHash": {"sha256": char * 64},
                            "merkleRoot": {"sha256": char * 64},
                        },
                    }
                ],
            },
            "claim_requirement_bindings": [
                {
                    "claim_id": f"claim-{role}",
                    "requirement_id": f"req-{role}-data",
                    "requirement_kind": "data_source",
                    "authority_level": "closeout",
                    "time_role": "publication_time",
                    "supported_by": [snapshot_ref],
                    "lifecycle_dependency_refs": [
                        f"event://data-forge/{role}/R_hds_red_control"
                    ],
                }
            ],
        }

    return {
        "schema_version": "policyos.runtime.data_forge_snapshot_binding.v1",
        "run_id": "R_hds_red_control",
        "job_id": "job-hds-red-control",
        "bindings": [
            binding("legal", "legal", "1"),
            binding("catalog", "catalog", "2"),
            binding("academic", "academic", "3"),
            binding("domain", "ukraine", "4"),
        ],
    }


def complete_fabric_source_facets() -> dict[str, Any]:
    return {
        "data_forge_snapshot_refs": [sha("4")],
        "source_facets": [
            {
                "source_ref": "production-msme-panel",
                "source_family": "production_msme_panel",
                "source_rights": "government_open_data",
                "dataset_ref": "dataset:production-msme-panel",
                "dictionary_ref": "dictionary:production-msme-panel:v1",
                "schema_ref": "schema:production-msme-panel:v1",
                "field_refs": [
                    "field:production-msme-panel.firm_id",
                    "field:production-msme-panel.survival",
                    "field:production-msme-panel.credit_amount",
                ],
                "unit_refs": ["unit:percent", "unit:UAH"],
                "geography_refs": ["UA"],
                "time_coverage_refs": ["2024-2026"],
                "quality_refs": ["quality:production-msme-panel:v1"],
                "missingness_refs": ["missingness:production-msme-panel:v1"],
                "freshness_refs": ["freshness:production-msme-panel:2026-05-15"],
                "lineage_refs": ["lineage:production-msme-panel:v1"],
                "transformation_refs": ["transform:survival-rate:v1"],
                "data_forge_snapshot_refs": [sha("4")],
                "selected_candidate_ref": "production-msme-panel",
                "rejected_candidate_refs": ["fixture-source"],
            }
        ],
        "derived_features": [
            {
                "feature_ref": "feature:msme_survival_rate",
                "source_ref": "production-msme-panel",
                "source_facet_refs": ["field:production-msme-panel.survival"],
                "claim_ids": ["rec_1"],
                "claim_support_feature_refs": ["claim-feature:rec_1:msme_survival_rate"],
                "lineage_refs": ["lineage:production-msme-panel:v1"],
                "transformation_refs": ["transform:survival-rate:v1"],
            }
        ],
        "claim_support_feature_refs": ["claim-feature:rec_1:msme_survival_rate"],
    }


def complete_policy_design_concept_spine(
    *,
    run_id: str = "R_hds_red_control",
    job_id: str = "job-hds-red-control",
    tenant_id: str = "tenant-1",
    policy_intent_ref: str | None = None,
) -> dict[str, Any]:
    concept_id = "concept.msme_survival_rate"
    return build_policy_design_case_concept_spine(
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        policy_intent_ref=policy_intent_ref or runtime_cas_refs()["policy_intent_ref"],
        fabric_entity_resolution={
            "schema_version": "fabric.entity_resolution.batch.v1",
            "batch_ref": "cas://sha256/" + "a" * 64,
            "records": [
                {
                    "entity_id": "fabric:metric:msme_survival_rate",
                    "canonical_name": "MSME survival rate",
                    "aliases": ["SME survival", "firm survival"],
                    "attributes": {
                        "canonical_concept_id": concept_id,
                        "source_terms": "MSME survival, firm survival",
                        "geography": "UA",
                        "population": "wartime MSMEs",
                        "time": "2024-2026",
                        "unit_id": "percent",
                        "currency": "UAH",
                        "price_base": "not_applicable",
                        "exchange_rate_ref": "not_applicable",
                        "inflation_adjustment_ref": "not_applicable",
                        "calendar": "gregorian",
                        "freshness_ref": "freshness.production_msme_panel.2026-05-17",
                    },
                    "provenance_ref": "cas://sha256/" + "b" * 64,
                }
            ],
        },
        scientist_cross_graph={
            "schema_version": "2.1",
            "ontology_snapshot": [
                {
                    "concept_id": concept_id,
                    "label": "MSME survival rate",
                    "metadata": {
                        "aliases": ["SME survival", "firm survival"],
                        "population": "wartime MSMEs",
                    },
                }
            ],
            "needs": [
                {
                    "need": {
                        "need_id": "need-msme-survival",
                        "metric_id": "msme_survival_rate",
                        "labels": ["MSME survival"],
                        "geography": "UA",
                        "time_window": "2024-2026",
                    },
                    "resolved_concept_ids": [concept_id],
                    "provenance_refs": ["cas://sha256/" + "d" * 64],
                }
            ],
            "bridges": [
                {
                    "src_id": "claim.msme_survival_evidence",
                    "dst_concept_id": concept_id,
                    "src_kind": "claim",
                    "numerical_semantics": {
                        "unit_id": "percent",
                        "currency": "UAH",
                        "price_base": "not_applicable",
                        "exchange_rate_ref": "not_applicable",
                        "inflation_adjustment_ref": "not_applicable",
                        "geography": "UA",
                        "geography_level": "national",
                        "time": "2024-2026",
                        "time_basis": "calendar_year",
                        "calendar": "gregorian",
                        "freshness_ref": "freshness.production_msme_panel.2026-05-17",
                    },
                    "provenance": ["cas://sha256/" + "e" * 64],
                }
            ],
        },
        ir_linker={
            "schema_version": "1.0",
            "ok": True,
            "issues": [],
            "linked_metrics": [
                {
                    "metric_id": "msme_survival_rate",
                    "canonical_concept_id": concept_id,
                    "unit_id": "percent",
                }
            ],
        },
        ir_registry={
            "schema_version": "1.0",
            "concepts": {
                concept_id: {
                    "concept_id": concept_id,
                    "name": "MSME survival rate",
                    "notes": ["alias:SME survival", "source_term:firm survival"],
                }
            },
            "metrics": {
                "msme_survival_rate": {
                    "metric_id": "msme_survival_rate",
                    "unit_id": "percent",
                }
            },
            "units": {
                "percent": {"kind": "rate"},
                "uah": {"kind": "money", "currency": "UAH"},
            },
        },
        ir_world={
            "schema_version": "ir.world.concept_projection.v1",
            "world_refs": [
                {
                    "world_id": "world.msme_survival_rate",
                    "canonical_concept_id": concept_id,
                    "provenance_ref": "cas://sha256/" + "f" * 64,
                }
            ],
            "dataset_bindings": [
                {
                    "dataset_id": "production-msme-panel",
                    "columns": ["firm_id", "survival_status"],
                    "metric_id": "msme_survival_rate",
                    "canonical_concept_id": concept_id,
                }
            ],
            "legal_concept_bindings": [
                {
                    "legal_concept_id": "ua.credit_support.eligibility",
                    "canonical_concept_id": concept_id,
                }
            ],
            "method_requirement_bindings": [
                {
                    "requirement_id": "method.did.minimum_panel",
                    "canonical_concept_id": concept_id,
                }
            ],
            "objective_tradeoff_bindings": [
                {
                    "objective_id": "objective.msme_survival",
                    "tradeoff_id": "tradeoff.fiscal_cost",
                    "canonical_concept_id": concept_id,
                }
            ],
            "geography": ["UA"],
            "population": ["wartime MSMEs"],
            "time": ["2024-2026"],
            "units": ["percent"],
            "currency": ["UAH"],
            "price_bases": ["not_applicable"],
            "exchange_rates": ["not_applicable"],
            "inflation_adjustments": ["not_applicable"],
            "calendars": ["gregorian"],
            "freshness": ["freshness.production_msme_panel.2026-05-17"],
        },
    )


def bundle_local_runtime_refs() -> dict[str, str]:
    return {
        ref_key: f"quality_evidence/{QUALITY_REPORT_FILES[report_key]}"
        for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items()
    }


def complete_semantic_binding_ledger() -> dict[str, Any]:
    claim_ids = [
        "rec_1",
        "legal_1",
        "budget_1",
        "dist_1",
        "risk_1",
        "monitor_survival",
        "uncertainty_1",
    ]
    return {
        "schema_version": SEMANTIC_BINDING_SCHEMA_VERSION,
        "semantic_binding_ref": sha("b"),
        "status": "pass",
        "policy_intent_ref": sha("a"),
        "spine_context": {
            "schema_version": PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
            "context_id": "producer-spine-context-complete",
            "concept_spine_ref": sha("2"),
            "jurisdiction_spine_ref": sha("6"),
            "canonical_concept_refs": ["concept.msme_survival_rate"],
            "jurisdiction_refs": ["UA"],
            "consumer_components": list(PRODUCER_SPINE_CONSUMER_COMPONENTS),
        },
        "intent": {
            "policy_intent_ref": sha("a"),
            "canonical_concept_refs": ["concept.msme_survival_rate"],
            "jurisdiction": "UA",
            "time_context": "2026-05-15",
            "population": "wartime MSMEs",
            "intervention": "wartime credit support",
            "treatment": "credit eligibility",
            "outcome": "msme survival",
            "legal_domain": "wartime_msme_support",
            "data_source_family": "production_msme_panel",
            "dataset": "production-msme-panel",
            "columns": ["firm_id", "survival", "credit_amount"],
            "method_family": "causal_effect_estimation",
            "final_claim": "rec_1",
            "monitoring_signal": "msme_survival_rate",
            "public_artifact_section": "recommendations",
        },
        "lex": [
            {
                "binding_id": "lex-binding-1",
                "legal_query_terms": ["credit support", "wartime MSME eligibility"],
                "legal_query_refs": ["lex-query:welfare-msme"],
                "concept_refs": ["concept.msme_survival_rate"],
                "candidate_norm_refs": [
                    "norm.ua.credit_eligibility",
                    "norm.ua.procurement_fixture",
                ],
                "selected_norm_refs": ["norm.ua.credit_eligibility"],
                "rejected_norm_refs": ["norm.ua.procurement_fixture"],
                "legal_snapshot_refs": [sha("d")],
                "jurisdiction_filters": ["UA"],
                "effective_date_filters": ["2026-05-15"],
                "hierarchy_conflict_refs": ["conflict:resolved-credit-eligibility"],
                "competence_refs": ["competence:norm.ua.credit_eligibility"],
                "no_norm_blocker_refs": [],
                "retrieval_error_blocker_refs": [],
                **_spine_binding_fields("lex"),
            }
        ],
        "fabric": [
            {
                "binding_id": "fabric-binding-1",
                "candidate_dataset_source_refs": [
                    "production-msme-panel",
                    "fixture-source",
                ],
                "selected_dataset_source_refs": ["production-msme-panel"],
                "rejected_dataset_source_refs": ["fixture-source"],
                "metric_bindings": [
                    {
                        "metric_id": "msme_survival_rate",
                        "claim_ids": ["rec_1"],
                        "source_refs": ["production-msme-panel"],
                    }
                ],
                "column_bindings": [
                    {
                        "claim_id": "rec_1",
                        "source_ref": "production-msme-panel",
                        "column_refs": ["firm_id", "survival", "credit_amount"],
                    }
                ],
                "unit_bindings": [{"metric_id": "credit_amount", "unit": "UAH"}],
                "geography_bindings": [{"source_ref": "production-msme-panel", "geo": "UA"}],
                "calendar_time_bindings": [
                    {"source_ref": "production-msme-panel", "time_window": "2024-2026"}
                ],
                "source_freshness": [{"source_ref": "production-msme-panel", "status": "pass"}],
                "data_coverage": [
                    {
                        "source_ref": "production-msme-panel",
                        "claim_ids": claim_ids,
                        "status": "covers",
                    }
                ],
                "dictionary_refs": ["dictionary:production-msme-panel:v1"],
                "lineage_refs": ["lineage:production-msme-panel:v1"],
                **complete_fabric_source_facets(),
                "data_gap_blocker_refs": [],
                "ambiguity_blocker_refs": [],
                **_spine_binding_fields("fabric"),
            }
        ],
        "scholar": [
            {
                "binding_id": "scholar-binding-1",
                "candidate_literature_refs": [
                    "literature:msme-survival-review",
                    "literature:procurement-fixture",
                ],
                "selected_literature_refs": ["literature:msme-survival-review"],
                "rejected_literature_refs": ["literature:procurement-fixture"],
                "support_link_refs": ["support:msme-survival-review:rec_1"],
                "conflict_link_refs": ["conflict:literature:resolved"],
                "retrieval_blocker_refs": [],
                **_spine_binding_fields("scholar"),
            }
        ],
        "foundry": [
            {
                "binding_id": "foundry-binding-1",
                "selected_method_refs": ["causal.difference_in_differences"],
                "rejected_method_refs": ["descriptive.summary"],
                "rejected_method_reasons": [
                    {
                        "method_ref": "descriptive.summary",
                        "reason_code": "insufficient_identification_strategy",
                    }
                ],
                "scenario_method_expectation_refs": ["causal_effect_estimation"],
                "assumptions": ["parallel_trends"],
                "runtime_assumption_gates": [
                    {
                        "gate_ref": (
                            "foundry-assumption-gate:"
                            "causal.difference_in_differences:parallel_trends"
                        ),
                        "assumption": "parallel_trends",
                        "status": "pass",
                    }
                ],
                "assumption_gate_refs": [
                    "foundry-assumption-gate:"
                    "causal.difference_in_differences:parallel_trends"
                ],
                "input_coverage": [{"source_ref": "production-msme-panel", "status": "pass"}],
                "sample_power_adequacy": [{"method_ref": "causal.difference_in_differences"}],
                "placebo_negative_control_refs": ["placebo:pre_period"],
                "sensitivity_refs": ["sensitivity:survival-v1"],
                "method_output_refs": ["method-output:causal.difference_in_differences"],
                "uncertainty_refs": ["uncertainty:survival-v1"],
                "uncertainty_envelopes": [
                    {"status": "pass", "interval": [0.01, 0.07], "ref": "uncertainty:survival-v1"}
                ],
                "limitation_refs": ["method-limit:survival-v1"],
                "method_incompatibility_blocker_refs": [],
                **_spine_binding_fields("foundry"),
            }
        ],
        "scientist": [
            {
                "binding_id": "scientist-binding-1",
                "major_claim_ids": ["rec_1"],
                "recommendation_ids": ["rec_1"],
                "legal_assertion_ids": ["legal_1"],
                "budget_feasibility_ids": ["budget_1"],
                "distributional_impact_ids": ["dist_1"],
                "implementation_risk_ids": ["risk_1"],
                "monitoring_ids": ["monitor_survival"],
                "residual_uncertainty_ids": ["uncertainty_1"],
                "required_data_refs": ["production-msme-panel"],
                "required_method_refs": ["causal.difference_in_differences"],
                "required_norm_refs": ["norm.ua.credit_eligibility"],
                "required_literature_refs": ["literature:msme-survival-review"],
                "required_uncertainty_refs": ["uncertainty:survival-v1"],
                "required_blocker_refs": [],
                "claim_evidence_paths": _complete_claim_evidence_paths(),
                **_spine_binding_fields("scientist"),
            }
        ],
        "final_compiler": [
            {
                "binding_id": "final-binding-1",
                "major_claim_ids": ["rec_1"],
                "recommendation_ids": ["rec_1"],
                "legal_assertion_ids": ["legal_1"],
                "budget_feasibility_ids": ["budget_1"],
                "distributional_impact_ids": ["dist_1"],
                "implementation_risk_ids": ["risk_1"],
                "monitoring_ids": ["monitor_survival"],
                "residual_uncertainty_ids": ["uncertainty_1"],
                "required_data_refs": ["production-msme-panel"],
                "required_method_refs": ["causal.difference_in_differences"],
                "required_norm_refs": ["norm.ua.credit_eligibility"],
                "required_literature_refs": ["literature:msme-survival-review"],
                "required_uncertainty_refs": ["uncertainty:survival-v1"],
                "required_blocker_refs": [],
                "public_artifact_section_refs": ["section:recommendations"],
                "claim_evidence_paths": _complete_claim_evidence_paths(),
                **_spine_binding_fields("final_compiler"),
            }
        ],
    }


def semantic_ledger_missing_claim_axes() -> dict[str, Any]:
    """Cloud-debug fixture shape: producer pass with reader-visible axis gaps."""

    ledger = complete_semantic_binding_ledger()
    ledger["status"] = "pass"
    ledger["runtime_report_status"] = None
    incomplete_path = {
        "claim_id": "rec_1",
        "source_refs": ["production-msme-panel"],
        "selected_norm_refs": ["norm.ua.credit_eligibility"],
        "selected_method_refs": ["causal.difference_in_differences"],
        "method_output_refs": ["method-output:causal.difference_in_differences"],
        "scientist_claim_refs": ["claim:rec_1"],
    }
    for phase in ("scientist", "final_compiler"):
        bindings = ledger.get(phase)
        if not isinstance(bindings, list) or not bindings:
            continue
        binding = dict(bindings[0])
        binding["claim_evidence_paths"] = [dict(incomplete_path)]
        ledger[phase] = [binding]
    return ledger


def _spine_binding_fields(component: str) -> dict[str, Any]:
    return {
        "consumed_concept_spine_ref": sha("2"),
        "consumed_jurisdiction_spine_ref": sha("6"),
        "candidate_spine_binding_refs": [
            f"spine-binding:{component}:concept.msme_survival_rate:UA"
        ],
        "spine_blocker_refs": [],
        "local_labels": [],
    }


def _complete_claim_evidence_paths() -> list[dict[str, Any]]:
    return [
        {
            "claim_id": "rec_1",
            "scenario_requirement_refs": ["scenario-public_golden:msme_survival"],
            "canonical_concept_refs": ["concept.msme_survival_rate"],
            "fabric_binding_refs": ["fabric-binding-1"],
            "source_refs": ["production-msme-panel"],
            "column_refs": ["firm_id", "survival", "credit_amount"],
            "lex_binding_refs": ["lex-binding-1"],
            "selected_norm_refs": ["norm.ua.credit_eligibility"],
            "foundry_binding_refs": ["foundry-binding-1"],
            "selected_method_refs": ["causal.difference_in_differences"],
            "method_output_refs": ["method-output:causal.difference_in_differences"],
            "assumption_gate_refs": [
                "foundry-assumption-gate:"
                "causal.difference_in_differences:parallel_trends"
            ],
            "uncertainty_refs": ["uncertainty:survival-v1"],
            "scientist_claim_refs": ["claim:rec_1"],
            "argument_refs": ["arg-rec-1"],
            "warrant_refs": ["warrant-rec-1"],
            "rebuttal_refs": ["rebuttal-rec-1"],
            "counter_evidence_refs": ["counter-evidence-rec-1"],
            "limitation_refs": ["deficit-assessment-rec-1"],
            "blocker_refs": [],
        }
    ]


def runtime_worker_attestation() -> dict[str, Any]:
    return {
        "schema_version": "polisyos.runtime.attestation.v1",
        "attestation_id": "att-hds-runtime-worker",
        "trust_boundary_id": "runtime_worker",
        "generated_at": "2026-05-15T08:30:00+00:00",
        "expected_materials": [{"key": "run_request", "ref": sha("a"), "sha256": "a" * 64}],
        "observed_materials": [{"key": "run_request", "ref": sha("a"), "sha256": "a" * 64}],
        "expected_products": [{"key": "runtime_quality_refs", "ref": sha("b"), "sha256": "b" * 64}],
        "observed_products": [{"key": "runtime_quality_refs", "ref": sha("b"), "sha256": "b" * 64}],
        "functionary": {
            "functionary_id": "runtime-worker@prod-cell-a",
            "role": "runtime_worker",
            "service_account": "runtime-worker",
        },
        "producer_identity": {
            "component": "polisyos.runtime.worker",
            "version": "2026.05.15+hds-wave1",
            "owner": "team-runtime",
        },
        "environment_identity": {
            "environment_id": "prod-cell-a",
            "execution_profile": "production",
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "runner_id": "worker-1",
        },
        "isolation_status": "isolated",
        "service_generated": True,
        "consumer_verification": "verified",
        "tamper_check_status": "pass",
        "signature_ref": "signature://runtime-worker",
        "evidence_ref": sha("c"),
    }


def attestation_material_refs() -> dict[str, str]:
    return {
        "run_request": sha("a"),
        "execution_profile": "profile://production",
        "input_refs": sha("b"),
        "payload_bytes": sha("c"),
        "schema_identity": "schema://policyos.test.v1",
        "tenant_identity": "tenant://tenant-1",
        "runtime_refs": sha("d"),
        "scorecard_ref": sha("e"),
        "readiness_ref": sha("f"),
        "authority_envelopes": sha("1"),
        "diagnostic_events": sha("2"),
        "quality_scorecard": sha("3"),
        "invariant_registry": "architecture/production_quality/invariant_registry.toml",
        "readiness_summary": sha("4"),
        "review_packet": sha("5"),
        "approval_ref": sha("6"),
        "redaction_policy": "policy://public-export-redaction.v1",
        "source_refs": sha("7"),
        "prompt_ref": sha("8"),
        "model_policy": sha("9"),
        "provider_request": sha("a"),
        "connector_request": sha("b"),
        "source_contract": sha("c"),
        "credential_scope": "env://redacted",
        "jurisdiction_filter": "UA",
        "legal_snapshot_ref": sha("d"),
        "query_ref": sha("e"),
        "tool_contract": sha("f"),
        "parser_schema": "schema://parser.v1",
    }


def attestation_product_refs() -> dict[str, str]:
    return {
        "runtime_quality_refs": sha("1"),
        "authority_evidence": sha("2"),
        "cas_ref": sha("3"),
        "artifact_manifest": sha("4"),
        "observer_bundle": sha("5"),
        "redacted_overlay": sha("6"),
        "quality_scorecard": sha("7"),
        "readiness_summary": sha("8"),
        "approval_packet": sha("9"),
        "dashboard_projection": sha("a"),
        "public_export": sha("b"),
        "provider_response": sha("c"),
        "provider_quality_ledger": sha("d"),
        "source_snapshot": sha("e"),
        "selection_audit": sha("f"),
        "norm_refs": sha("1"),
        "conflict_report": sha("2"),
        "tool_result": sha("3"),
        "parser_result": sha("4"),
        "repair_ledger": sha("5"),
    }


def trust_boundary_attestations() -> list[dict[str, Any]]:
    return [
        record.model_dump(mode="json", exclude_none=True)
        for record in build_required_production_attestations(
            material_refs=attestation_material_refs(),
            product_refs=attestation_product_refs(),
        )
    ]


def authority_envelope_for(
    *,
    report_key: str,
    ref_key: str,
    ref_value: str,
    run_id: str = "R_hds_red_control",
    job_id: str = "job-hds-red-control",
    closure_sha256: str | None = None,
) -> dict[str, Any]:
    closure_digest = closure_sha256 or "c" * 64
    return {
        "evidence_id": f"evidence-{report_key}",
        "artifact_ref": ref_value,
        "artifact_kind": report_key,
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "producer_component": f"polisyos.runtime.quality.{report_key}",
        "producer_version": "2026.05.15+hds-wave1",
        "owner": "team-runtime",
        "runtime_event_ref": sha("e"),
        "cas_ref": ref_value,
        "payload_sha256": ref_value,
        "schema_name": f"runtime_quality.{report_key}.v1",
        "schema_version": "1.0",
        "reader_contract": "runtime_quality.scorecard.reader",
        "reader_contract_version": "1.0",
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": "tenant-1",
        "cell_id": "cell-a",
        "trace_id": "trace-hds-red-control",
        "span_id": f"span-{ref_key}",
        "parent_span_id": "span-scorecard-parent",
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "phase": "quality_evidence",
        "state_before": "running",
        "state_after": "persisted",
        "generated_at": "2026-05-15T08:30:00+00:00",
        "as_of_time": "2026-05-15T08:30:00+00:00",
        "same_input_closure": {
            "closure_id": "closure-hds-red-control",
            "status": "closed",
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "policy_intent_ref": sha("a"),
            "time_context_ref": sha("b"),
            "production_data_manifest_ref": sha("c"),
            "legal_snapshot_ref": sha("d"),
            "method_plan_ref": sha("e"),
            "provider_mode_ref": sha("f"),
            "effective_mode_ref": sha("e"),
            "degradation_ledger_ref": sha("d"),
            "evidence_input_refs": [sha("a"), sha("b")],
            "closure_sha256": closure_digest,
        },
        "input_refs": [sha("a"), sha("b")],
        "output_refs": [ref_value],
        "effective_mode_ref": sha("e"),
        "degradation_ledger_ref": sha("d"),
        "schema_compatibility_ref": sha("c"),
        "semantic_binding_ref": sha("b"),
        "validation_status": "pass",
        "blocking_status": "non_blocking",
        "governance": {
            "classification": "internal",
            "authority_boundary": "runtime",
            "pii": "none",
            "retention_policy": "runtime-quality-90d",
            "review_status": "runtime_verified",
            "override_policy": "not_overridable",
            "approval_policy": "runtime_owner_required",
        },
    }


def diagnostic_events(runtime_refs: dict[str, str] | None = None) -> list[dict[str, Any]]:
    refs = {**runtime_cas_refs(), **(runtime_refs or {})}
    return [
        {
            "event_id": f"evt-{ref_key}",
            "event_name": f"{ref_key}.persisted",
            "severity": "serious",
            "sampling": {"decision": "always_record", "rate": 1.0},
            "artifact_ref": refs[ref_key],
            "runtime_cas_ref": refs[ref_key],
        }
        for ref_key in (
            *QUALITY_REPORT_RUNTIME_REFS.values(),
            *POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
        )
        if ref_key in refs
    ]


def phase_barrier_records() -> list[dict[str, Any]]:
    return [
        PhaseBarrierRecord.pass_record(
            barrier_id=barrier_id,
            run_id="R_hds_red_control",
            tenant_id="tenant-1",
            profile="production",
            evidence_refs=[sha("a"), sha("b")],
            runtime_event_ref=sha("e"),
            cas_ref=sha("f"),
        ).model_dump(mode="json")
        for barrier_id in PhaseBarrierId.scorecard_required()
    ]


def policy_design_record_family_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family_id in POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES:
        slug = family_id.removesuffix(".v1")
        row: dict[str, Any] = {
            "family_id": family_id,
            "status": "present",
            "schema_owner": "team-runtime-quality",
            "producer_owner": "team-runtime-quality",
            "reader_owner": "team-quality-closeout",
            "schema_name": f"policyos.policy_design_case.{family_id}",
            "scorecard_gate": f"policy_design_case.{slug}.present_or_blocked",
            "readiness_gate": "policy_design_case.record_family_coverage",
            "readiness_check": "policy_design_case.record_family_coverage",
            "authority_envelope": {
                "authority_role": "reader_authority",
                "provenance_kind": "runtime_derived",
                "cas_ref": sha("1"),
                "runtime_event_ref": "event://policy-design-case/record-family-coverage",
            },
        }
        governance_surfaces = policy_design_governance_surfaces_for_family(family_id)
        if governance_surfaces:
            row["governance_surfaces"] = governance_surfaces
        rows.append(row)
    return rows


def policy_design_runtime_record_family_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, family_id in enumerate(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES, start=1):
        slug = family_id.removesuffix(".v1").replace("_", "-")
        event_ref = f"event://policy-design-case/records/{slug}/1"
        ref_char = hex(index % 16)[2:]
        rows.append(
            {
                "record_id": f"pdc-{slug}-record-1",
                "family_id": family_id,
                "record_family": family_id,
                "schema_name": f"policyos.policy_design_case.{family_id}",
                "schema_version": f"policyos.policy_design_case.{family_id}",
                "producer_owner": "team-runtime-quality",
                "reader_owner": "team-quality-closeout",
                "readiness_gate": "policy_design_case.record_family_coverage",
                "readiness_check": "policy_design_case.record_family_coverage",
                "evidence_ref": sha(ref_char),
                "cas_ref": sha(ref_char),
                "runtime_event_ref": event_ref,
                "authority_envelope": {
                    "authority_role": "producer_authority",
                    "provenance_kind": "runtime_emitted",
                    "cas_ref": sha(ref_char),
                    "runtime_event_ref": event_ref,
                },
            }
        )
    return rows


def policy_design_governance_surfaces_for_family(family_id: str) -> list[str]:
    return [
        surface
        for surface, required_family in (
            POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS.items()
        )
        if required_family == family_id
    ]


def policy_design_phase28_1_records() -> dict[str, Any]:
    def pdd(pdd_id: str, surfaces: str | list[str]) -> dict[str, Any]:
        surface_list = [surfaces] if isinstance(surfaces, str) else surfaces
        return {
            "pdd_id": pdd_id,
            "surface": surface_list[0],
            "surfaces": surface_list,
            "record_ref": f"policy_design_case.pass1b.{surface_list[0]}",
            "evidence_ref": sha("f"),
            "runtime_event_ref": f"event://policy-design-case/pass1b/{pdd_id}",
            "owner": "team-quality-closeout",
            "status": "implemented",
        }

    case_bindings = {
        "tenant_identity": {
            "record_ref": sha("a"),
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "status": "pass",
            "runtime_event_ref": "event://tenant/identity/1",
        },
        "cas_ownership": {
            "record_ref": sha("b"),
            "owner_index_ref": sha("c"),
            "tenant_id": "tenant-1",
            "read_scope_enforced": True,
            "status": "pass",
            "runtime_event_ref": "event://cas/ownership/1",
        },
        "artifact_tenant_mapping": {
            "record_ref": sha("d"),
            "descendant_map_ref": sha("e"),
            "api_decision_ref": sha("f"),
            "status": "pass",
            "runtime_event_ref": "event://artifacts/tenant-map/1",
        },
        "cas_manifest_governance": {
            "record_ref": sha("1"),
            "producer_metadata_ref": sha("2"),
            "governance_metadata_ref": sha("3"),
            "retention_class": "governed",
            "encryption_metadata_ref": sha("4"),
            "status": "pass",
            "runtime_event_ref": "event://cas/manifest-governance/1",
        },
        "approval_authority": {
            "record_ref": sha("5"),
            "approval_packet_ref": sha("6"),
            "scorecard_digest_ref": sha("7"),
            "projection_policy": "immutable_packet_projection",
            "status": "pass",
            "runtime_event_ref": "event://approval/authority/1",
        },
        "override_signature": {
            "record_ref": sha("8"),
            "override_packet_ref": sha("9"),
            "reviewer_identity_ref": sha("a"),
            "signature_ref": "signature://reviewer-alpha",
            "signature_class": "internal_reviewer_attestation",
            "non_overridable_blockers_enforced": True,
            "status": "pass",
            "runtime_event_ref": "event://approval/override/1",
        },
        "decision_lifecycle": {
            "record_ref": sha("b"),
            "decision_packet_ref": sha("c"),
            "published_artifact_ref": sha("d"),
            "validity_lifecycle_ref": sha("e"),
            "continuous_governance_ref": sha("f"),
            "status": "pass",
            "runtime_event_ref": "event://decision/lifecycle/1",
        },
        "privacy_security_authority": {
            "record_ref": sha("0"),
            "privacy_compliance_report_ref": sha("1"),
            "security_assurance_report_ref": sha("2"),
            "runtime_enforcement_log_refs": [sha("3")],
            "canonical_metadata_ref": sha("4"),
            "status": "pass",
            "runtime_event_ref": "event://privacy-security/authority/1",
        },
        "human_review_authority": {
            "record_ref": sha("5"),
            "human_oversight_ref": sha("6"),
            "reviewer_identity_refs": [sha("7")],
            "separation_of_duty_ref": sha("8"),
            "rubber_stamp_risk": "low",
            "effective_oversight": True,
            "status": "pass",
            "runtime_event_ref": "event://human-review/authority/1",
        },
        "privileged_action_authority": {
            "record_ref": sha("9"),
            "privileged_action_ledger_ref": sha("a"),
            "dual_control_ref": sha("b"),
            "before_after_hash_refs": [sha("c")],
            "tamper_evident_attribution_ref": sha("d"),
            "status": "pass",
            "runtime_event_ref": "event://privileged-action/authority/1",
        },
        "signing_public_trust": {
            "record_ref": sha("e"),
            "signing_authority_matrix_ref": sha("f"),
            "key_lifecycle_refs": [sha("0")],
            "release_attestation_ref": sha("1"),
            "public_packet_signature_ref": "signature://public-packet",
            "trust_status": "valid",
            "status": "pass",
            "runtime_event_ref": "event://signing/public-trust/1",
        },
        "recall_retraction": {
            "record_ref": sha("2"),
            "recall_authority_ref": sha("3"),
            "retraction_authority_ref": sha("4"),
            "contestability_hook_ref": sha("5"),
            "status": "pass",
            "runtime_event_ref": "event://governance/recall-retraction/1",
        },
        "public_trust": {
            "record_ref": sha("6"),
            "public_export_ref": sha("7"),
            "external_audit_archive_ref": sha("8"),
            "standalone_verifier_ref": sha("9"),
            "public_contestability_ref": sha("a"),
            "status": "pass",
            "runtime_event_ref": "event://public-trust/1",
        },
    }
    return {
        "pass1b_tenant_cas_approval_governance": (
            build_pass1b_tenant_cas_approval_governance_record(
                record_id="pass1b-hardening-rec-1",
                case_id="pdc-R_hds_red_control",
                run_id="R_hds_red_control",
                job_id="job-hds-red-control",
                tenant_id="tenant-1",
                cell_id="cell-a",
                case_bindings=case_bindings,
                pdd_bindings=[
                    pdd("PDD-022", "tenant_identity"),
                    pdd("PDD-023", "cas_ownership"),
                    pdd("PDD-024", "artifact_tenant_mapping"),
                    pdd("PDD-025", "cas_manifest_governance"),
                    pdd("PDD-028", "approval_authority"),
                    pdd("PDD-029", "override_signature"),
                    pdd("PDD-030", ["decision_lifecycle", "recall_retraction"]),
                    pdd("PDD-033", "privacy_security_authority"),
                    pdd("PDD-058", ["human_review_authority", "override_signature"]),
                    pdd("PDD-095", "privileged_action_authority"),
                    pdd("PDD-096", ["signing_public_trust", "public_trust"]),
                ],
                evidence_ref=sha("1"),
                runtime_event_ref="event://policy-design-case/pass1b-hardening/1",
            )
        )
    }


def policy_design_phase27_records() -> dict[str, Any]:
    return {
        "implementation_monitoring_evaluation": {
            "schema_version": (
                "policyos.runtime.policy_design_case.implementation_monitoring_evaluation.v1"
            ),
            "record_id": "implementation-monitoring-rec-1",
            "case_id": "pdc-R_hds_red_control",
            "claim_ids": ["rec_1"],
            "implementation_contract": {
                "contract_id": "implementation-contract-rec-1",
                "intervention_ref": "option-targeted-credit",
                "responsible_owner": "team-policy-implementation",
                "start_date": "2026-06-01",
                "affected_claim_ids": ["rec_1"],
                "assumption_refs": ["assumption-parallel-trends"],
                "evidence_ref": sha("a"),
            },
            "monitoring_plan": {
                "plan_id": "monitoring.plan.rec_1",
                "indicators": [
                    {
                        "indicator_id": "msme_survival_rate",
                        "claim_id": "rec_1",
                        "data_source_refs": ["production-msme-panel"],
                        "thresholds": {"degradation_budget": 0.2},
                    }
                ],
                "observation_windows": [
                    {
                        "window_id": "post-publication-q1",
                        "start": "2026-06-01T00:00:00+00:00",
                        "end": "2026-09-01T00:00:00+00:00",
                    }
                ],
                "review_cadence": "monthly",
                "trigger_thresholds": ["ddm_readiness_R2"],
                "responsible_owners": ["team-ddm", "team-policy-implementation"],
                "evidence_ref": sha("b"),
            },
            "evaluation_design": {
                "design_id": "evaluation-design-rec-1",
                "design_type": "difference_in_differences_reassessment",
                "estimand": "ATT",
                "outcome_metrics": ["msme_survival_rate"],
                "comparison_strategy": "matched eligible non-recipients",
                "observation_windows": ["post-publication-q1"],
                "evidence_ref": sha("c"),
            },
            "publication_order": {
                "publication_authority_ref": sha("p"),
                "created_before_publication_authority": True,
            },
            "ddm_monitoring": {
                "shift_events": [
                    {
                        "event_id": "shift-risk-1",
                        "event_type": "ml.problem_15_7.shift_risk.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("d"),
                        "runtime_event_ref": "event://ddm/shift-risk-1",
                    }
                ],
                "degradation_events": [
                    {
                        "event_id": "degradation-1",
                        "event_type": "ml.problem_15_7.degradation.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "readiness_event_ids": ["readiness-1"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("e"),
                        "runtime_event_ref": "event://ddm/degradation-1",
                    }
                ],
                "readiness_events": [
                    {
                        "event_id": "readiness-1",
                        "event_type": "ml.problem_15_7.readiness_state.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "readiness_state": "R2",
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("f"),
                        "runtime_event_ref": "event://ddm/readiness-1",
                    }
                ],
                "incident_events": [
                    {
                        "event_id": "incident-1",
                        "event_type": "ml.problem_15_7.incident_payload.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "root_cause_event_ids": ["root-cause-1"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("8"),
                        "runtime_event_ref": "event://ddm/incident-1",
                    }
                ],
                "root_cause_events": [
                    {
                        "event_id": "root-cause-1",
                        "event_type": "ml.problem_15_7.root_cause_bundle.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("9"),
                        "runtime_event_ref": "event://ddm/root-cause-1",
                    }
                ],
            },
            "evidence_ref": sha("1"),
            "runtime_event_ref": "event://policy-design-case/implementation-monitoring/1",
        },
        "case_lifecycle": {
            "schema_version": "policyos.runtime.policy_design_case.case_lifecycle.v1",
            "ledger_id": "case-lifecycle-rec-1",
            "case_id": "pdc-R_hds_red_control",
            "current_state": "published",
            "events": [
                {
                    "event_id": "lifecycle-published",
                    "event_type": "published",
                    "previous_state": "approved",
                    "new_state": "published",
                    "evidence_refs": [sha("1")],
                    "runtime_event_ref": "event://policy-design-case/lifecycle/published",
                },
                {
                    "event_id": "lifecycle-validity-confirmed",
                    "event_type": "confirmed",
                    "previous_state": "published",
                    "new_state": "confirmed",
                    "evidence_refs": [sha("2")],
                    "runtime_event_ref": "event://policy-design-case/lifecycle/confirmed",
                },
            ],
            "continuous_governance_reports": {
                "reissue": sha("3"),
                "supersede": sha("4"),
                "withdraw": sha("5"),
                "validity": sha("6"),
            },
            "resolution_event_refs": ["lifecycle-validity-confirmed"],
            "evidence_ref": sha("7"),
            "runtime_event_ref": "event://policy-design-case/lifecycle",
        },
        "ex_post_learning": {
            "schema_version": "policyos.runtime.policy_design_case.ex_post_learning.v1",
            "record_id": "ex-post-learning-rec-1",
            "case_id": "pdc-R_hds_red_control",
            "claim_prediction_links": [
                {
                    "link_id": "outcome-link-rec-1",
                    "claim_id": "rec_1",
                    "prediction_ref": "prediction-rec-1",
                    "observed_outcome_ref": "observed-outcome-rec-1",
                    "reassessment_ref": "reassessment-rec-1",
                    "reassessment_status": "confirmed",
                    "future_method_prior_ref": "future-prior-rec-1",
                    "future_uncertainty_prior_ref": "future-prior-rec-1",
                    "evidence_ref": sha("a"),
                    "runtime_event_ref": "event://policy-design-case/ex-post/outcome-link",
                }
            ],
            "calibration": {
                "calibration_report_refs": [sha("b")],
                "backtesting_report_refs": [sha("c")],
                "calibration_leaderboard_ref": sha("d"),
                "track_record_ref": sha("e"),
            },
            "memory_contamination_check": {
                "status": "clean",
                "policy": {
                    "hidden_ref_ids": [],
                    "hidden_suite_ids": [],
                    "canary_tokens": [],
                },
                "findings": [],
                "evidence_ref": sha("f"),
                "runtime_event_ref": "event://policy-design-case/ex-post/memory-clean",
            },
            "learning_records": [
                {
                    "learning_id": "learning-rec-1",
                    "scope": "wartime_msme_support",
                    "applicability": ["UA", "production_msme_panel"],
                    "revocation_conditions": ["new legal regime", "data schema change"],
                    "memory_contamination_controls": ["hidden_eval_scan_clean"],
                    "evidence_ref": sha("0"),
                }
            ],
            "evidence_ref": sha("1"),
            "runtime_event_ref": "event://policy-design-case/ex-post",
        },
    }


def policy_design_phase28_3_records() -> dict[str, Any]:
    return {
        "dormant_capability_inventory": {
            "schema_version": (
                "policyos.runtime.policy_design_case.dormant_capability_inventory.v1"
            ),
            "record_id": "dormant-capability-inventory-rec-1",
            "record_family": "capability_mode_and_fallback_selection.v1",
            "status": "pass",
            "capabilities": [
                _phase28_3_capability(
                    "lex_legal_kg",
                    "normative_applicability_request.v1",
                    "normative_applicability_report",
                    "policy_design_case.legal_authority_and_competence",
                ),
                _phase28_3_capability(
                    "fabric_dataset_catalog_graph",
                    "data_need_contract.v1",
                    "fabric_source_selection_audit",
                    "policy_design_case.data_source_semantic_lineage",
                ),
                _phase28_3_capability(
                    "foundry_method_catalog_expectations",
                    "method_selection_request.v1",
                    "foundry_method_report",
                    "policy_design_case.method_selection_and_validity",
                ),
                _phase28_3_capability(
                    "scientist_workflow_nodes",
                    "scientist_workflow_plan.v1",
                    "scientist_node_events",
                    "policy_design_case.claim_argument_evidence_case",
                ),
            ],
            "evidence_ref": sha("1"),
            "runtime_event_ref": ("event://policy-design-case/pdd-017/dormant-capabilities"),
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_policy_design_case_observability_static_audit.py -q"
            ),
        },
        "skip_causality_ledger": {
            "schema_version": ("policyos.runtime.policy_design_case.skip_causality_ledger.v1"),
            "record_id": "skip-causality-ledger-rec-1",
            "record_family": "capability_mode_and_fallback_selection.v1",
            "status": "pass",
            "projection_preserves_reason_fields": True,
            "skipped_nodes": [
                {
                    "node_id": "scientist.legal_conflict_deep_dive",
                    "reason_code": "prerequisite_not_applicable",
                    "missing_input": "legal_conflict_candidate",
                    "prerequisite_status": "no_conflict_detected",
                    "downstream_impact": (
                        "deep-dive node skipped; final claim keeps no-conflict ref"
                    ),
                    "profile_policy": ("production skips require reason and blocker visibility"),
                    "raw_node_outcome_ref": sha("2"),
                    "progress_event_ref": "event://runtime/progress/scientist/skip/1",
                    "node_event_ref": ("event://scientist/node/legal_conflict_deep_dive/skip"),
                }
            ],
            "evidence_ref": sha("2"),
            "runtime_event_ref": "event://policy-design-case/pdd-018/skip-causality",
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_policy_design_case_observability_static_audit.py -q"
            ),
        },
        "freshness_policy_time_semantics": {
            "schema_version": (
                "policyos.runtime.policy_design_case.freshness_policy_time_semantics.v1"
            ),
            "record_id": "freshness-policy-time-rec-1",
            "record_family": "numeric_time_and_geography_semantics.v1",
            "status": "pass",
            "policy_time": "2026-05-15",
            "evidence_time_bindings": [
                _phase28_3_freshness_binding("legal", "2026-05-14", 30, sha("3")),
                _phase28_3_freshness_binding("data", "2026-05-15", 90, sha("4")),
                _phase28_3_freshness_binding("benchmark", "2026-05-10", 180, sha("5")),
                _phase28_3_freshness_binding("decision", "2026-05-17", 30, sha("6")),
            ],
            "continuous_governance_triggers": [
                {
                    "trigger_id": "reissue-when-source-stale",
                    "trigger": "source_freshness_expired",
                    "action": "reissue_or_withdraw",
                }
            ],
            "final_artifact_date_assumptions": [
                {
                    "artifact": "public_policy_brief",
                    "assumption": "Evidence remains current at publication time.",
                    "evidence_ref": sha("7"),
                }
            ],
            "evidence_ref": sha("3"),
            "runtime_event_ref": ("event://policy-design-case/pdd-045/freshness-policy-time"),
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_policy_design_case_observability_static_audit.py -q"
            ),
        },
    }


def _phase28_3_capability(
    capability: str,
    input_contract: str,
    output_artifact: str,
    consumer: str,
) -> dict[str, Any]:
    return {
        "capability": capability,
        "available": True,
        "invoked": True,
        "input_contract": input_contract,
        "output_artifact": output_artifact,
        "consumer": consumer,
        "current_break_point": "none",
    }


def _phase28_3_freshness_binding(
    evidence_kind: str,
    evidence_as_of: str,
    acceptable_recency_window_days: int,
    evidence_ref: str,
) -> dict[str, Any]:
    return {
        "evidence_kind": evidence_kind,
        "policy_time": "2026-05-15",
        "evidence_as_of": evidence_as_of,
        "freshness_status": "pass",
        "acceptable_recency_window_days": acceptable_recency_window_days,
        "evidence_ref": evidence_ref,
    }


def policy_design_phase28_2_records() -> dict[str, Any]:
    return {
        "substrate_residual_verification": {
            "schema_version": (
                "policyos.runtime.policy_design_case.substrate_residual_verification.v1"
            ),
            "record_family": "substrate_residual_verification.v1",
            "record_id": "substrate-residual-verification-R_hds_red_control",
            "case_id": "pdc-R_hds_red_control",
            "run_id": "R_hds_red_control",
            "job_id": "job-hds-red-control",
            "tenant_id": "tenant-prod",
            "status": "pass",
            "pdd_bindings": [
                _phase28_2_binding(
                    "PDD-019",
                    "capability_mode_and_fallback_selection.v1",
                    ["mode_ledger", "fallback_degradation_ledger"],
                ),
                _phase28_2_binding(
                    "PDD-031",
                    "publication_trust_and_external_governance.v1",
                    [
                        "deterministic_replay_manifest",
                        "rule_evolution_registry",
                        "typed_replay_drift",
                    ],
                ),
                _phase28_2_binding(
                    "PDD-032",
                    "implementation_monitoring_and_evaluation.v1",
                    ["resilience_matrix", "observed_vs_modeled_resilience"],
                ),
                _phase28_2_binding(
                    "PDD-039",
                    "publication_trust_and_external_governance.v1",
                    ["trusted_authority_fields", "authority_spoofing_controls"],
                ),
                _phase28_2_binding(
                    "PDD-040",
                    "integrity_self_fmea_and_maturity.v1",
                    ["partial_state_consistency", "retry_reconciliation"],
                ),
                _phase28_2_binding(
                    "PDD-041",
                    "publication_trust_and_external_governance.v1",
                    ["shared_cas_evidence_graph", "tenant_scoped_cas_ownership"],
                ),
                _phase28_2_binding(
                    "PDD-067",
                    "publication_trust_and_external_governance.v1",
                    ["public_export", "public_export_semantic_preservation"],
                ),
                _phase28_2_binding(
                    "PDD-071",
                    "capability_mode_and_fallback_selection.v1",
                    ["effective_configuration_ledger", "environment_provenance"],
                ),
                _phase28_2_binding(
                    "PDD-084",
                    "publication_trust_and_external_governance.v1",
                    ["tool_transcript_authority", "compaction_audit"],
                ),
                _phase28_2_binding(
                    "PDD-086",
                    "method_selection_and_validity.v1",
                    ["simulation_boundary_ledger", "evidence_mode_ledger"],
                    owner="team-science-quality",
                ),
            ],
            "evidence_ref": sha("2"),
            "runtime_event_ref": "event://policy-design-case/substrate-residual/1",
        }
    }


def policy_design_phase29_2_records() -> dict[str, Any]:
    return {
        "non_adversarial_self_fmea": {
            "schema_version": "policyos.runtime.policy_design_case.non_adversarial_self_fmea.v1",
            "record_id": "self-fmea-R_hds_red_control",
            "record_family": "integrity_self_fmea_and_maturity.v1",
            "case_id": "pdc-R_hds_red_control",
            "run_id": "R_hds_red_control",
            "job_id": "job-hds-red-control",
            "tenant_id": "tenant-prod",
            "status": "verified",
            "failure_modes": [
                _phase29_2_fmea_mode(
                    "schema_migration_errors",
                    "Persisted case schema migration can drop or rename authoritative fields.",
                    "schema_compatibility_ref",
                    sha("c"),
                ),
                _phase29_2_fmea_mode(
                    "partial_case_graphs",
                    "Crash or retry can publish an incomplete evidence graph.",
                    "phase_barrier_records",
                    sha("d"),
                ),
                _phase29_2_fmea_mode(
                    "contradictory_records",
                    "Two authoritative records can disagree after partial replay.",
                    "partial_state_consistency",
                    sha("e"),
                ),
                _phase29_2_fmea_mode(
                    "stale_generated_surfaces",
                    "Generated API, dashboard, or docs surfaces can lag runtime state.",
                    "generated_surface_drift",
                    sha("f"),
                ),
                _phase29_2_fmea_mode(
                    "operator_workarounds",
                    "Manual operator workarounds can bypass intended publication gates.",
                    "runbook_automation",
                    sha("1"),
                ),
                _phase29_2_fmea_mode(
                    "box_ticking_failure",
                    "Nominally complete review can satisfy checklists without substance.",
                    "human_oversight",
                    sha("2"),
                ),
            ],
            "evidence_ref": sha("3"),
            "runtime_event_ref": "event://policy-design-case/self-fmea/1",
        },
        "partial_state_consistency": {
            "schema_version": "policyos.runtime.policy_design_case.partial_state_consistency.v1",
            "record_id": "partial-state-consistency-R_hds_red_control",
            "record_family": "integrity_self_fmea_and_maturity.v1",
            "case_id": "pdc-R_hds_red_control",
            "run_id": "R_hds_red_control",
            "job_id": "job-hds-red-control",
            "tenant_id": "tenant-prod",
            "status": "pass",
            "authoritative_records": [
                {
                    "record_id": "lifecycle-authority-published",
                    "record_family": "lifecycle_ex_post_and_calibration.v1",
                    "field": "case_lifecycle.current_state",
                    "value": "published",
                    "authority_role": "authoritative",
                    "evidence_ref": sha("4"),
                    "runtime_event_ref": "event://policy-design-case/lifecycle/published",
                },
                {
                    "record_id": "approval-authority-production",
                    "record_family": "publication_trust_and_external_governance.v1",
                    "field": "approval.authority_profile",
                    "value": "production",
                    "authority_role": "authoritative",
                    "evidence_ref": sha("5"),
                    "runtime_event_ref": "event://policy-design-case/approval/production",
                },
            ],
            "checked_fields": ["case_lifecycle.current_state", "approval.authority_profile"],
            "contradictions": [],
            "evidence_ref": sha("6"),
            "runtime_event_ref": "event://policy-design-case/partial-state/1",
        },
    }


def _phase29_2_fmea_mode(
    failure_mode: str,
    scenario: str,
    control_ref: str,
    evidence_ref: str,
) -> dict[str, Any]:
    return {
        "failure_mode": failure_mode,
        "scenario": scenario,
        "severity": "serious_closeout_blocking",
        "status": "mitigated",
        "mitigation_controls": [
            {
                "control_id": f"{failure_mode}_control",
                "control_ref": control_ref,
                "status": "pass",
            }
        ],
        "residual_risk": "accepted_with_runtime_evidence",
        "evidence_ref": evidence_ref,
        "runtime_event_ref": f"event://policy-design-case/self-fmea/{failure_mode}",
    }


def policy_design_phase29_3_records() -> dict[str, Any]:
    return {
        "case_maturity_profile": build_case_maturity_profile(
            record_id="case-maturity-R_hds_red_control",
            case_id="pdc-R_hds_red_control",
            run_id="R_hds_red_control",
            job_id="job-hds-red-control",
            tenant_id="tenant-prod",
            family_maturities={
                family_id: {
                    "maturity": "evidence_complete",
                    "record_refs": [sha("1")],
                    "argument_refs": [sha("2")],
                    "evidence_refs": [sha("3")],
                }
                for family_id in POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES
            },
            evidence_ref=sha("1"),
            runtime_event_ref="event://policy-design-case/case-maturity/1",
        )
    }


def _phase28_2_binding(
    diagnostic_id: str,
    record_family_id: str,
    facets: list[str],
    *,
    owner: str = "team-runtime-quality",
) -> dict[str, Any]:
    return {
        "diagnostic_id": diagnostic_id,
        "record_family_id": record_family_id,
        "record_facets": facets,
        "record_refs": [sha(diagnostic_id[-1].lower())],
        "evidence_ref": sha(diagnostic_id[-1].lower()),
        "runtime_event_ref": f"event://policy-design-case/substrate-residual/{diagnostic_id}",
        "owner": owner,
        "status": "pass",
    }


def policy_design_phase28_4_records() -> dict[str, Any]:
    return {
        "config_release_deployment_migration_hardening": {
            "schema_version": (
                "policyos.runtime.policy_design_case."
                "config_release_deployment_migration_hardening.v1"
            ),
            "contract_id": ("policy_design_case.config_release_deployment_migration_hardening.v1"),
            "record_family": "publication_trust_and_external_governance.v1",
            "record_id": "config-release-hardening-R_hds_red_control",
            "run_id": "R_hds_red_control",
            "status": "pass",
            "pdd_ids": [
                "PDD-072",
                "PDD-075",
                "PDD-076",
                "PDD-079",
                "PDD-080",
                "PDD-081",
                "PDD-082",
            ],
            "deployment_parity": {
                "deployment_unit_refs": [sha("1")],
                "required_service_matrix": [
                    _phase28_4_service_matrix_row("authz_opa"),
                    _phase28_4_service_matrix_row("state_store"),
                    _phase28_4_service_matrix_row("generated_clients"),
                    _phase28_4_service_matrix_row("resource_quotas"),
                    _phase28_4_service_matrix_row("release_gates"),
                ],
                "parity_diff": {"status": "match", "diff_ref": sha("2")},
                "topology_ref": sha("3"),
                "promotion_gate_refs": [sha("4")],
            },
            "release_supply_chain": {
                "release_provenance_ref": sha("5"),
                "lockfile_fingerprints": {"uv.lock": sha("6")},
                "generated_artifact_fingerprints": {"runtime_api_client": sha("7")},
                "sbom_ref": sha("8"),
                "attestation_ref": sha("9"),
                "signing_ref": sha("a"),
                "promotion_gate_refs": [sha("b")],
                "dirty_tree_clean": True,
                "untracked_artifact_count": 0,
            },
            "persisted_state_migration": {
                "migration_exercise_refs": [sha("c")],
                "compatibility_fixture_refs": [sha("d")],
                "historical_decision_checks": [
                    {
                        "artifact_family": "policy_design_case",
                        "read_status": "pass",
                        "replay_status": "pass",
                        "migrate_status": "pass",
                        "reissue_status": "pass",
                        "withdraw_status": "pass",
                        "evidence_ref": sha("e"),
                    }
                ],
                "typed_incompatibility_explanations": [],
            },
            "quarantine_shim_lifecycle": {
                "ledger_ref": sha("f"),
                "active_usage_ids": [],
                "expired_usage_ids": [],
                "approved_exception_refs": [],
                "serious_run_usage_scan_ref": sha("0"),
            },
            "generated_surface_drift": {
                "fingerprints": {
                    "openapi": sha("1"),
                    "generated_client": sha("2"),
                    "dashboard_validator": sha("3"),
                    "cli": sha("4"),
                    "docs": sha("5"),
                    "release_snapshot": sha("6"),
                },
                "runtime_to_generated_diff": {"status": "match", "diff_ref": sha("7")},
                "negative_consumer_test_refs": [sha("8")],
            },
            "runbook_automation": {
                "manual_gate_inventory_ref": sha("9"),
                "manual_gates": [
                    {
                        "gate_id": "publication-approval",
                        "owner": "team-quality-closeout",
                        "reviewer_role": "policy_reviewer",
                        "status": "pass",
                        "signed_review_ref": sha("a"),
                        "evidence_ref": sha("b"),
                    }
                ],
                "automation_candidate_classification_ref": sha("c"),
                "stale_manual_gate_ids": [],
            },
            "retention_deletion_replay": {
                "retention_replay_matrix_ref": sha("d"),
                "deletion_minimization_scenario_refs": [sha("e")],
                "public_private_auditability_ref": sha("f"),
                "replay_evidence_ref": sha("0"),
                "jurisdiction_blockers": [],
            },
            "evidence_ref": sha("1"),
            "runtime_event_ref": "event://policy-design-case/config-release-hardening/1",
        }
    }


def _phase28_4_service_matrix_row(service: str) -> dict[str, str]:
    return {
        "service": service,
        "local": "real",
        "staging": "real",
        "production": "real",
    }


def policy_design_phase28_5_records() -> dict[str, Any]:
    return {
        "external_plugin_dependency_client_surface": {
            "schema_version": EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
            "record_family": "publication_trust_and_external_governance.v1",
            "record_id": "external-client-surface-R_hds_red_control",
            "run_id": "R_hds_red_control",
            "status": "pass",
            "connector_acquisition": [
                {
                    "connector_id": "connector.fabric.production_msme_panel",
                    "owner": "team-domain-producers",
                    "acquisition_ledger_ref": sha("1"),
                    "fetch_safety_ref": sha("2"),
                    "source_version_ref": sha("3"),
                    "freshness_strategy_ref": sha("4"),
                    "sla_ref": sha("5"),
                    "quality_contract_ref": sha("6"),
                    "data_classification": "restricted_policy_evidence",
                    "license_ref": sha("7"),
                    "replay_ref": sha("8"),
                    "refusal_policy_ref": sha("9"),
                }
            ],
            "plugin_capability_isolation": [
                {
                    "plugin_id": "plugin.policyos.source_adapter",
                    "component_index_ref": sha("a"),
                    "source_provenance_ref": sha("b"),
                    "abi_compatibility_ref": sha("c"),
                    "dependency_compatibility_ref": sha("d"),
                    "duplicate_check_ref": sha("e"),
                    "allowlist_ref": sha("f"),
                    "owner": "team-runtime-platform",
                    "capability_scope": ["read_source_snapshot"],
                    "isolation_ref": sha("0"),
                    "dev_scan_approved": False,
                    "capability_escalation": False,
                }
            ],
            "external_dependency_contracts": [
                {
                    "dependency_id": "provider.openalex",
                    "provider": "openalex",
                    "contract_ref": sha("1"),
                    "terms_ref": sha("2"),
                    "license_ref": sha("3"),
                    "use_rights_ref": sha("4"),
                    "retention_policy_ref": sha("5"),
                    "export_rights_ref": sha("6"),
                    "jurisdiction_ref": "UA",
                    "outage_plan_ref": sha("7"),
                    "withdrawal_replay_rights_ref": sha("8"),
                    "correction_replay_rights_ref": sha("9"),
                    "risk_status": "pass",
                }
            ],
            "external_evidence_provenance": [
                {
                    "source_id": "production-msme-panel",
                    "claim_ids": ["rec_1"],
                    "provider_source_ref": sha("a"),
                    "provenance_ref": sha("b"),
                    "replay_ref": sha("c"),
                    "freshness_ref": sha("d"),
                    "rights_ref": sha("e"),
                    "support_handoff_ref": sha("f"),
                }
            ],
            "offline_mutation_authority": [
                {
                    "mutation_id": "approval-submit-1",
                    "authority_state": "server_accepted",
                    "queued_state_separated": True,
                    "idempotency_key_ref": sha("1"),
                    "auth_freshness_ref": sha("2"),
                    "attempt_ref": sha("3"),
                    "conflict_resolution_ref": sha("4"),
                    "server_acceptance_ref": sha("5"),
                    "rollback_ref": sha("6"),
                    "approval_packet_ref": sha("7"),
                    "presented_as_authoritative": True,
                }
            ],
            "collaboration_attribution": [
                {
                    "collaboration_id": "review-room-1",
                    "participant_identity_ref": sha("8"),
                    "attribution_ref": sha("9"),
                    "lock_ttl_ref": sha("a"),
                    "staleness_check_ref": sha("b"),
                    "persisted_review_packet_ref": sha("c"),
                    "ephemeral_state_not_authority": True,
                }
            ],
            "assistant_composer_provenance": [
                {
                    "composer_id": "clerk-composer-1",
                    "sanitized_original_prompt_ref": sha("d"),
                    "request_hash": sha("e"),
                    "locale_ref": "uk-UA",
                    "defaults_ref": sha("f"),
                    "model_profile_ref": sha("0"),
                    "flag_refs": [sha("1")],
                    "draft_state_ref": sha("2"),
                    "retention_deletion_ref": sha("3"),
                    "compliance_redaction_ref": sha("4"),
                }
            ],
            "bureaucratic_rendering_export": [
                {
                    "export_id": "public-form-1",
                    "template_review_ref": sha("5"),
                    "template_version_ref": sha("6"),
                    "jurisdiction": "UA",
                    "semantic_section_mapping_ref": sha("7"),
                    "export_parity_ref": sha("8"),
                    "disclaimer_ref": sha("9"),
                    "redaction_ref": sha("a"),
                    "official_use_limitation_ref": sha("b"),
                    "draft_limitation_ref": sha("c"),
                    "official_form_authority": "draft_limited",
                }
            ],
            "client_persistence_privacy": [
                {
                    "inventory_ref": sha("d"),
                    "sensitive_redaction_test_ref": sha("e"),
                    "deletion_minimization_ref": sha("f"),
                    "service_worker_cache_policy_ref": sha("0"),
                    "local_evidence_retention_ref": sha("1"),
                    "generated_export_control_ref": sha("2"),
                    "server_client_gap_report_ref": sha("3"),
                    "public_export_control_ref": sha("4"),
                    "sensitive_local_state_allowed": False,
                }
            ],
            "evidence_ref": sha("5"),
            "runtime_event_ref": "event://policy-design-case/external-client-surface/1",
        }
    }


def policy_design_phase29_1_records() -> dict[str, Any]:
    return {
        "evidence_graph_threat_model": {
            "schema_version": EVIDENCE_GRAPH_THREAT_MODEL_SCHEMA_VERSION,
            "record_family": EVIDENCE_GRAPH_THREAT_MODEL_RECORD_FAMILY,
            "record_id": "evidence-graph-threat-model-R_hds_red_control",
            "case_id": "pdc-R_hds_red_control",
            "run_id": "R_hds_red_control",
            "job_id": "job-hds-red-control",
            "tenant_id": "tenant-prod",
            "status": "pass",
            "threat_records": [
                _phase29_1_threat_record(
                    "prompt_injection",
                    "untrusted source text and prompt/tool handoffs",
                ),
                _phase29_1_threat_record(
                    "poisoned_datasets",
                    "fabric and data-forge source corpora",
                ),
                _phase29_1_threat_record(
                    "stale_indexes",
                    "legal, literature, and dataset indexes",
                ),
                _phase29_1_threat_record(
                    "malicious_tenants",
                    "tenant-scoped CAS evidence graph",
                ),
                _phase29_1_threat_record(
                    "forged_provenance",
                    "authority envelopes and provenance refs",
                ),
                _phase29_1_threat_record(
                    "compromised_plugins",
                    "plugin discovery and external adapters",
                ),
                _phase29_1_threat_record(
                    "local_client_leakage",
                    "offline and local client persistence surfaces",
                ),
                _phase29_1_threat_record(
                    "insider_mutation",
                    "privileged mutation and override paths",
                ),
            ],
            "residual_blockers": [],
            "evidence_ref": sha("1"),
            "runtime_event_ref": "event://policy-design-case/evidence-graph-threat-model/1",
        }
    }


def _phase29_1_threat_record(threat_id: str, surface: str) -> dict[str, Any]:
    if threat_id not in EVIDENCE_GRAPH_THREATS:
        raise ValueError(f"unknown evidence graph threat: {threat_id}")
    return {
        "threat_id": threat_id,
        "status": "mitigated",
        "affected_surfaces": [surface],
        "attack_paths": [f"{threat_id}:authority-graph-compromise"],
        "detection_refs": [sha("2")],
        "mitigation_refs": [sha("3")],
        "blocker_policy_ref": sha("4"),
        "residual_risk": "bounded",
        "owner": "team-quality-closeout",
        "evidence_ref": sha("5"),
        "runtime_event_ref": f"event://policy-design-case/evidence-graph-threat/{threat_id}",
    }


def policy_design_phase30_records() -> dict[str, Any]:
    return {
        "run_cost_proportionality_ledgers": [
            {
                "schema_version": (
                    "policyos.runtime.policy_design_case."
                    "run_cost_proportionality_ledger.v1"
                ),
                "ledger_id": "run-cost-ledger-R_hds_red_control",
                "run_id": "R_hds_red_control",
                "job_id": "job-hds-red-control",
                "authority_level": "production",
                "public_impact": "high",
                "runtime_performance_budget": _phase30_cost_component(3.0, "1"),
                "foundry_cost_model": _phase30_cost_component(4.0, "2"),
                "scientist_budget": _phase30_cost_component(5.0, "3"),
                "doe_search_budget": _phase30_cost_component(2.5, "4"),
                "provider_cost": _phase30_cost_component(1.5, "5"),
                "elapsed_time_budget": {
                    "budget_seconds": 3600,
                    "actual_seconds": 1800,
                    "evidence_ref": sha("6"),
                },
                "human_review_burden": {
                    "budget_reviewer_hours": 3.0,
                    "actual_reviewer_hours": 1.5,
                    "evidence_ref": sha("7"),
                },
                "evidence_depth_budget": {
                    "authority_level": "production",
                    "public_impact": "high",
                    "observed_heterogeneity": "moderate",
                    "effective_independent_evidence_count": 4,
                    "minimum_effective_independent_evidence_count": 4,
                    "stopping_rule": (
                        "stop after saturation and no recent direction changes"
                    ),
                    "stopping_decision": "stop",
                    "stopping_rule_result_ref": sha("8"),
                },
                "proportionality_evidence": {
                    "status": "proportional",
                    "rationale": (
                        "Production authority and high public impact justify "
                        "the observed run cost."
                    ),
                    "evidence_ref": sha("9"),
                },
                "budget_change_records": [],
                "evidence_ref": sha("a"),
                "runtime_event_ref": "event://runtime/run-cost/R_hds_red_control",
            }
        ]
    }


def _phase30_cost_component(cost: float, ref_char: str) -> dict[str, Any]:
    return {
        "budget_usd": cost + 1.0,
        "actual_cost_usd": cost,
        "evidence_ref": sha(ref_char),
    }


def complete_job_payload(
    *,
    runtime_refs: dict[str, str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    progress_details: dict[str, Any] = {
        "data_snapshot_ref": sha("a"),
        "input_bindings_ref": sha("b"),
        "registry_bundle_ref": sha("c"),
        "quality_report_ref": sha("d"),
        "production_data_quality_report_ref": sha("1"),
        "llm_model_variants": [
            {
                "model_variant_id": "qwen_1",
                "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                "provider": "gateway",
                "status": "completed",
                "schema_healing_count": 0,
                "prompt_tokens": 120,
                "completion_tokens": 32,
                "total_tokens": 152,
                "cost_usd": 0.0001,
            }
        ],
        "run_performance_summary": {"status": "pass"},
        "final_policy_claims": {
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_family": "recommendation",
                    "claim_type": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "citation_refs": ["source.msme_panel", "norm.ua.credit_eligibility"],
                    "support_summary": (
                        "Supported by selected panel data, legal norms, and method output."
                    ),
                    "uncertainty": "Estimated effects remain uncertain.",
                    "policy_tradeoffs": "Improves survival while increasing fiscal exposure.",
                    "distributional_impact": "Track rural and women-owned MSMEs separately.",
                    "implementation_feasibility": "Can use existing participating-bank rails.",
                    "budget_implication": "Requires a capped credit envelope.",
                    "stakeholder_impact": (
                        "Affects MSMEs, participating banks, fiscal authorities, "
                        "auditors, and communities in conflict-affected regions."
                    ),
                    "implementation_risks": (
                        "Fraud, adverse selection, and bank capacity remain risks."
                    ),
                    "residual_uncertainty": "Demand and repayment shocks remain uncertain.",
                    "monitoring_plan": (
                        "Monitor uptake, defaults, complaints, and subgroup outcomes."
                    ),
                    "withdrawal_reissue_triggers": (
                        "Withdraw or reissue if default, fraud, complaint, or subgroup "
                        "harm thresholds breach the monitoring plan."
                    ),
                    "section_evidence_refs": {
                        "budget_implication": [sha("b")],
                        "distributional_impact": [sha("d")],
                        "implementation_feasibility": [sha("f")],
                        "implementation_risks": [sha("r")],
                        "monitoring_plan": [sha("m")],
                        "policy_tradeoffs": [sha("t")],
                        "residual_uncertainty": [sha("u")],
                        "stakeholder_impact": [sha("s")],
                        "withdrawal_reissue_triggers": [sha("w")],
                    },
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ]
        },
    }
    progress_details.update(runtime_cas_refs() if runtime_refs is None else runtime_refs)
    progress_details.update(details or {})
    effective_runtime_refs = {
        key: str(progress_details[key])
        for key in (
            *QUALITY_REPORT_RUNTIME_REFS.values(),
            *POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
        )
        if key in progress_details
    }
    if PROMPT_TOOL_LEDGER_REF_KEY in progress_details:
        effective_runtime_refs[PROMPT_TOOL_LEDGER_REF_KEY] = str(
            progress_details[PROMPT_TOOL_LEDGER_REF_KEY]
        )
    progress_details["runtime_quality_refs"] = dict(effective_runtime_refs)
    progress_details.setdefault("diagnostic_event_log_ref", sha("e"))
    progress_details.setdefault("diagnostic_events", diagnostic_events(effective_runtime_refs))
    progress_details.setdefault("trust_boundary_attestations", trust_boundary_attestations())
    return {
        "job_id": "job-hds-red-control",
        "run_id": "R_hds_red_control",
        "state": "completed",
        "progress": {"details": progress_details},
    }


def complete_quality_evidence(*, authority_envelopes: bool = True) -> dict[str, Any]:
    source_truth_payload = {
        "status": "pass",
        "provenance": {"producer": "scientist.claim_compiler"},
        "owner": "team-policy-semantics",
        "schema": {"name": "policyos.claims", "version": "1"},
        "lineage": {"output_ref": sha("c")},
        "tenant": {"tenant_id": "tenant-1", "cell_id": "cell-a"},
        "time_context": {"as_of": "2026-05-15"},
        "jurisdiction": {"code": "UA"},
        "source_family": {"families": ["production_msme_panel"]},
        "method_expectation": {"families": ["causal_effect_estimation"]},
        "claim_sets": {"claim_ids": ["rec_1"], "claim_refs": [sha("d")]},
    }
    evidence = {
        "golden_scenario_contract": {
            "scenario_id": "ukraine_msme_wartime_credit_support",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["production_msme_panel"],
                "foundry_method_expectations": ["causal_effect_estimation"],
            },
        },
        "production_data_quality": {
            "schema_version": "policyos.runtime.production_data_quality.v1",
            "status": "pass",
            "manifest_checksum": sha("e"),
            "data_snapshot_ref": sha("a"),
            "input_bindings_ref": sha("b"),
            "registry_bundle_ref": sha("c"),
            "source_bundle_versions": {"datasets": "production_msme_panel_v1"},
            "row_counts": {"datasets": 240},
            "entity_counts": {"datasets": 120},
            "diagnostics": {
                key: {"status": "pass", "findings": []}
                for key in (
                    "schema_drift",
                    "missingness",
                    "outliers",
                    "duplicate_entity_collisions",
                    "unit_drift",
                    "temporal_leakage",
                    "cohort_leakage",
                    "label_quality",
                    "construct_validity",
                    "coverage",
                    "recency_ttl",
                    "data_dictionary",
                )
            },
            "issues": [],
        },
        "normative_evidence": {
            "schema_version": "policyos.lex.normative_applicability_report.v1",
            "status": "pass",
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-12",
            },
            "retrieval_status": "completed",
            "legal_corpus_snapshot": {
                "snapshot_id": "legal-snapshot-R_hds_red_control",
                "snapshot_ref": sha("6"),
                "manifest_ref": "cas://sha256/" + "6" * 64,
            },
            "query_terms": ["credit support", "wartime MSME eligibility"],
            "concept_refs": ["concept.msme_survival_rate"],
            "jurisdiction_filters": ["UA"],
            "time_filters": ["2026-05-12"],
            "candidate_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "jurisdiction": "UA",
                    "policy_domain": "wartime_msme_support",
                    "effective_from": "2024-01-01",
                    "source_authority": "Verkhovna Rada",
                    "authority_level": "statute",
                }
            ],
            "selected_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "jurisdiction": "UA",
                    "policy_domain": "wartime_msme_support",
                    "effective_from": "2024-01-01",
                    "source_authority": "Verkhovna Rada",
                    "authority_level": "statute",
                }
            ],
            "applied_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "jurisdiction": "UA",
                    "policy_domain": "wartime_msme_support",
                    "effective_from": "2024-01-01",
                    "source_authority": "Verkhovna Rada",
                    "authority_level": "statute",
                }
            ],
            "rejected_norms": [],
            "conflicts": [{"conflict_id": "conflict:resolved-credit-eligibility"}],
            "competence": [
                {
                    "competence_ref": "competence:norm.ua.credit_eligibility",
                    "norm_id": "norm.ua.credit_eligibility",
                    "jurisdiction": "UA",
                    "source_authority": "Verkhovna Rada",
                    "authority_level": "statute",
                    "competent_authority": "Verkhovna Rada",
                }
            ],
            "authority_blockers": [],
            "blockers": [],
            "recommendation_claims": [
                {
                    "claim_id": "rec_1",
                    "major": True,
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        },
        "fabric_retrieval_trace": {
            "schema_version": "policyos.fabric.source_selection_trace.v1",
            "status": "pass",
            "query_intent": {
                "policy_domain": "wartime_msme_support",
                "query_outcome": "msme_survival_rate",
                "query_treatment": "wartime_credit_support",
            },
            "candidate_sources": [
                {
                    "source_id": "production-msme-panel",
                    "source_family": "production_msme_panel",
                    "source_kind": "production_data",
                    "source_rights": "government_open_data",
                    "dataset_ref": "dataset:production-msme-panel",
                    "dictionary_ref": "dictionary:production-msme-panel:v1",
                    "schema_ref": "schema:production-msme-panel:v1",
                    "field_refs": [
                        "field:production-msme-panel.firm_id",
                        "field:production-msme-panel.survival",
                        "field:production-msme-panel.credit_amount",
                    ],
                    "unit_refs": ["unit:percent", "unit:UAH"],
                    "geography_refs": ["UA"],
                    "time_coverage_refs": ["2024-2026"],
                    "quality_refs": ["quality:production-msme-panel:v1"],
                    "missingness_refs": ["missingness:production-msme-panel:v1"],
                    "freshness_refs": ["freshness:production-msme-panel:2026-05-15"],
                    "lineage_refs": ["lineage:production-msme-panel:v1"],
                    "transformation_refs": ["transform:survival-rate:v1"],
                    "data_forge_snapshot_refs": [sha("4")],
                    "derived_features": [
                        {
                            "feature_ref": "feature:msme_survival_rate",
                            "source_ref": "production-msme-panel",
                            "source_facet_refs": ["field:production-msme-panel.survival"],
                            "claim_ids": ["rec_1"],
                            "claim_support_feature_refs": [
                                "claim-feature:rec_1:msme_survival_rate"
                            ],
                            "lineage_refs": ["lineage:production-msme-panel:v1"],
                            "transformation_refs": ["transform:survival-rate:v1"],
                        }
                    ],
                    "freshness": {"status": "pass"},
                    "coverage": {"status": "pass"},
                    "schema_compatibility": {"status": "pass"},
                    "relevance_rationale": "Matches requested outcome and treatment.",
                }
            ],
            "selected_source_ids": ["production-msme-panel"],
            "rejected_sources": [{"source_id": "fixture-source", "reason_code": "fixture"}],
        },
        "foundry_method_report": {
            "schema_version": "policyos.foundry.method_quality_report.v1",
            "status": "pass",
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "method_family": "causal_effect_estimation",
                    "input_refs": {
                        "data_snapshot_ref": sha("a"),
                        "input_bindings_ref": sha("b"),
                    },
                    "assumptions": ["parallel_trends"],
                    "runtime_assumption_gates": [
                        {
                            "gate_ref": (
                                "foundry-assumption-gate:"
                                "causal.difference_in_differences:parallel_trends"
                            ),
                            "assumption": "parallel_trends",
                            "status": "pass",
                        }
                    ],
                    "assumption_gate_refs": [
                        "foundry-assumption-gate:"
                        "causal.difference_in_differences:parallel_trends"
                    ],
                    "identification_requirements": {
                        "estimand": "ATT",
                        "requirements": ["parallel_trends", "overlap"],
                    },
                    "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                    "uncertainty_envelope_refs": ["uncertainty:survival-v1"],
                    "missingness": {"status": "pass", "missing_rate": 0.02},
                    "missingness_handling": {
                        "strategy": "complete_case_with_ipw_sensitivity",
                        "status": "pass",
                    },
                    "sensitivity": {"status": "pass", "robustness": "moderate"},
                    "transportability_limits": {
                        "target_population": "wartime_msmes",
                        "limits": ["No extrapolation outside observed support."],
                    },
                    "limitation_refs": ["method-limit:survival-v1"],
                    "specification_space": {
                        "primary": "two_way_fixed_effects",
                        "alternatives": ["event_study", "matched_did"],
                    },
                    "method_output_refs": ["method-output:causal.difference_in_differences"],
                    "method_result_refs": {"method_result_ref": sha("c")},
                    "validity_surfaces": {
                        "identification": {"status": "present", "ref": sha("1")},
                        "transportability": {"status": "present", "ref": sha("2")},
                        "partial_identification": {"status": "present", "ref": sha("3")},
                        "recoverability": {"status": "present", "ref": sha("4")},
                        "causal_ensemble": {"status": "present", "ref": sha("5")},
                        "falsification": {"status": "present", "ref": sha("6")},
                        "certificate_proof": {"status": "present", "ref": sha("7")},
                    },
                    "input_diagnostics": {"sample_size": 240, "min_required_sample_size": 30},
                    "result_summary": {"effect_estimate": 0.04},
                }
            ],
        },
        "scholar_evidence": complete_scholar_academic_evidence(),
        "policy_grounding_matrix": {
            "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
            "status": "pass",
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_family": "recommendation",
                    "claim_type": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "citation_refs": [
                        "production-msme-panel",
                        "norm.ua.credit_eligibility",
                        "literature:msme-survival-review",
                    ],
                    "support_summary": (
                        "Supported by selected production data, legal authority, "
                        "Scholar evidence, and Foundry method output."
                    ),
                    "uncertainty": "Estimated effects remain uncertain and depend on uptake.",
                    "policy_tradeoffs": (
                        "Improves credit access while preserving fiscal proportionality."
                    ),
                    "distributional_impact": (
                        "Monitor subgroup survival rates for rural and women-owned MSMEs."
                    ),
                    "implementation_feasibility": (
                        "Uses existing participating-bank reporting and monitoring rails."
                    ),
                    "budget_implication": "Requires a capped envelope and loss-reserve monitor.",
                    "stakeholder_impact": (
                        "Affects MSMEs, participating banks, fiscal authorities, and auditors."
                    ),
                    "implementation_risks": (
                        "Bank capacity, adverse selection, and fraud controls remain risks."
                    ),
                    "residual_uncertainty": (
                        "Demand elasticity and repayment shocks remain uncertain."
                    ),
                    "monitoring_plan": (
                        "Monitor uptake, defaults, complaints, and subgroup outcomes monthly."
                    ),
                    "withdrawal_reissue_triggers": (
                        "Withdraw or reissue if default rates exceed cap or legal scope changes."
                    ),
                    "section_evidence_refs": {
                        "budget_implication": [sha("b")],
                        "distributional_impact": [sha("d")],
                        "implementation_feasibility": [sha("f")],
                        "implementation_risks": [sha("r")],
                        "monitoring_plan": [sha("m")],
                        "policy_tradeoffs": [sha("t")],
                        "residual_uncertainty": [sha("u")],
                    },
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                    "portfolio_refs": ["portfolio-rec-1"],
                    "independence_refs": ["independence-rec-1"],
                    "synthesis_refs": ["synthesis-rec-1"],
                    "argument_refs": ["arg-rec-1"],
                    "warrant_refs": ["warrant-rec-1"],
                    "rebuttal_refs": ["rebuttal-rec-1"],
                    "counter_evidence_refs": ["counter-evidence-rec-1"],
                    "limitation_refs": ["deficit-assessment-rec-1"],
                    "accepted_deficit_refs": ["deficit-assessment-rec-1"],
                }
            ],
        },
        "semantic_binding_ledger": complete_semantic_binding_ledger(),
        "conflict_check": {
            "schema_version": "policyos.lex.policy_conflict_check.v1",
            "status": "pass",
            "claims": [],
            "corpus_constraints": [],
        },
        "causal_statistical_validity": {
            "schema_version": "policyos.foundry.causal_statistical_validity.v1",
            "status": "pass",
            "issues": [],
            "summary": {"case_count": 4},
        },
        "replay_manifest": {
            "schema_version": "policyos.replay_manifest.v1",
            "status": "pass",
            "deterministic_fingerprint": sha("f"),
        },
        "drift_explanation": {
            "schema_version": "policyos.drift_explanation.v1",
            "status": "match",
            "production_readiness": "pass",
            "differences": [],
        },
        "resilience_matrix": {
            "schema_version": "policyos.runtime.resilience_matrix.v1",
            "status": "pass",
            "summary": {"status": "pass"},
            "operator_findings": [],
        },
        "human_review_calibration": {
            "schema_version": "policyos.human_review_calibration_report.v1",
            "status": "pass",
            "quality_signals": [],
            "summary": {"review_count": 0},
        },
        "decision_artifact_quality": {
            "schema_version": "policyos.scientist.decision_artifact_quality.v1",
            "status": "pass",
            "issues": [],
            "claim_evidence_contract": {
                "status": "pass",
                "requirement": (
                    "every_major_statement_has_evidence_refs_or_typed_blocker"
                ),
                "statements": [
                    {
                        "claim_id": "rec_1",
                        "statement_id": "rec_1:recommendation",
                        "statement_scope": "recommendation",
                        "statement_type": "recommendation",
                        "has_text": True,
                        "evidence_refs": [
                            "production-msme-panel",
                            "norm.ua.credit_eligibility",
                            "literature:msme-survival-review",
                        ],
                        "typed_blockers": [],
                    },
                    {
                        "claim_id": "rec_1",
                        "statement_id": "rec_1:implementation_feasibility",
                        "statement_scope": "implementation_feasibility",
                        "statement_type": "feasibility_statement",
                        "has_text": True,
                        "evidence_refs": [sha("f")],
                        "typed_blockers": [],
                    },
                    {
                        "claim_id": "rec_1",
                        "statement_id": "rec_1:monitoring_plan",
                        "statement_scope": "monitoring_plan",
                        "statement_type": "monitoring_statement",
                        "has_text": True,
                        "evidence_refs": [sha("m")],
                        "typed_blockers": [],
                    },
                    {
                        "claim_id": "rec_1",
                        "statement_id": "rec_1:implementation_risks",
                        "statement_scope": "implementation_risks",
                        "statement_type": "implementation_risk_statement",
                        "has_text": True,
                        "evidence_refs": [sha("r")],
                        "typed_blockers": [],
                    },
                    {
                        "claim_id": "rec_1",
                        "statement_id": "rec_1:residual_uncertainty",
                        "statement_scope": "residual_uncertainty",
                        "statement_type": "residual_uncertainty_statement",
                        "has_text": True,
                        "evidence_refs": [sha("u")],
                        "typed_blockers": [],
                    },
                    {
                        "claim_id": "rec_1",
                        "statement_id": "rec_1:withdrawal_reissue_triggers",
                        "statement_scope": "withdrawal_reissue_triggers",
                        "statement_type": "contestability_statement",
                        "has_text": True,
                        "evidence_refs": [sha("w")],
                        "typed_blockers": [],
                    },
                ],
                "issues": [],
            },
            "decision_artifact_quality_report_ref": runtime_cas_refs()[
                "decision_artifact_quality_report_ref"
            ],
        },
        "provider_model_quality_ledger": {
            "schema_version": "policyos.provider_model_quality_ledger.v1",
            "status": "pass",
            "summary": {"status": "pass"},
            "entries": [
                {
                    "provider": "gateway",
                    "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                    "status": "pass",
                    "observed_at": "2026-05-15T08:30:00+00:00",
                }
            ],
            "default_model_reviews": [
                {
                    "provider": "gateway",
                    "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                    "action": "approve",
                    "reason": "Fresh runtime provider quality evidence is present.",
                }
            ],
        },
        "prompt_tool_ledger": {
            "schema_version": PROMPT_TOOL_LEDGER_SCHEMA_VERSION,
            "run_id": "R_hds_red_control",
            "job_id": "job-hds-red-control",
            "model_variant_id": "qwen_1",
            PROMPT_TOOL_LEDGER_REF_KEY: runtime_cas_refs()[PROMPT_TOOL_LEDGER_REF_KEY],
            "steps": [
                {
                    "step_id": "qwen_1:formalizer:1",
                    "step_kind": "formalizer",
                    "authority_scopes": ["evidence", "claims", "scorecard", "approval"],
                    "prompt": {
                        "template_id": "scientist.formalizer",
                        "template_version": "2026.05.15",
                        "template_ref": sha("6"),
                        "rendered_prompt_ref": sha("7"),
                        "rendered_input_refs": [sha("a"), sha("b"), sha("c")],
                        "template_variables_fingerprint": sha("8"),
                    },
                    "model_provider": {
                        "provider": "gateway",
                        "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                        "model_fingerprint": "qwen3-2026-05-15",
                        "provider_config_ref": sha("9"),
                        "temperature": 0.0,
                        "max_tokens": 4096,
                        "response_format": {"type": "json_object"},
                    },
                    "tool_allowlist": [],
                    "tool_schemas": [],
                    "tool_call_refs": [],
                    "output_refs": [
                        runtime_cas_refs()["policy_grounding_matrix_ref"],
                        runtime_cas_refs()["decision_artifact_quality_report_ref"],
                    ],
                    "parser_contract": {
                        "parser_id": "trinity_bundle_parser",
                        "parser_version": "1.0",
                        "contract_ref": sha("0"),
                        "input_schema_ref": sha("1"),
                        "output_schema_ref": sha("2"),
                    },
                    "validation_refs": [
                        {
                            "validator_id": "trinity_schema_validator",
                            "status": "pass",
                            "validation_ref": sha("3"),
                        }
                    ],
                    "repair_decisions": [
                        {
                            "decision": "schema_healing_not_required",
                            "status": "not_applicable",
                            "reason": "Strict parser validation passed.",
                            "fmea_annotation": {
                                "failure_mode": "parser_contract_repair",
                                "severity": 1,
                                "cause": "strict_parser_validation_passed",
                                "recommended_mitigation": (
                                    "Keep strict parser validation and retain the "
                                    "no-repair decision for audit replay."
                                ),
                                "residual_risk": (
                                    "No residual repair risk observed for this step."
                                ),
                                "occurrence": 1,
                                "detectability": 1,
                                "owner": "team-runtime-ops",
                                "controls": ["strict parser validation"],
                                "evidence_ref": sha("3"),
                                "authority_effect": "advisory",
                            },
                        }
                    ],
                    "authority_handoff_refs": [
                        {
                            "scope": "evidence",
                            "handoff_ref": runtime_cas_refs()["policy_grounding_matrix_ref"],
                            "consumer": "runtime.evidence",
                            "status": "pass",
                        },
                        {
                            "scope": "claims",
                            "handoff_ref": runtime_cas_refs()[
                                "decision_artifact_quality_report_ref"
                            ],
                            "consumer": "scientist.claim_ledger",
                            "status": "pass",
                        },
                        {
                            "scope": "scorecard",
                            "handoff_ref": runtime_cas_refs()[PROMPT_TOOL_LEDGER_REF_KEY],
                            "consumer": "runtime.scorecard",
                            "status": "pass",
                        },
                        {
                            "scope": "approval",
                            "handoff_ref": runtime_cas_refs()[PROMPT_TOOL_LEDGER_REF_KEY],
                            "consumer": "runtime.approval",
                            "status": "pass",
                        },
                    ],
                }
            ],
        },
        "security_assurance_report": {
            "schema_version": "policyos.security_assurance_report.v1",
            "status": "pass",
            "security_assurance_report_ref": runtime_cas_refs()["security_assurance_report_ref"],
            "assured_paths": [],
            "issues": [],
            "blockers": [],
        },
        "privacy_compliance_report": {
            "schema_version": "policyos.privacy_compliance_report.v1",
            "status": "pass",
            "issues": [],
            "summary": {
                "production_data_source_count": 1,
                "public_artifact_family_count": 1,
            },
        },
        "data_forge_snapshot_binding": complete_data_forge_snapshot_binding(),
        "continuous_governance_stale": {
            "schema_version": "policyos.runtime.governance_lifecycle_report.v1",
            "status": "pass",
            "issues": [],
            "lifecycle_decision": "stale",
            "decision_status": "stale",
            "continuous_governance_stale_report_ref": runtime_cas_refs()[
                "continuous_governance_stale_report_ref"
            ],
            "diagnostic_event": {
                "event_type": "polisyos.runtime.diagnostic.reconciliation_result.v1",
                "artifact_refs": [runtime_cas_refs()["continuous_governance_stale_report_ref"]],
                "sampling_decision": "always_record",
                "sampling_rate": 1.0,
            },
            "cas_artifact_refs": {
                "governance_lifecycle_report_ref": runtime_cas_refs()[
                    "continuous_governance_stale_report_ref"
                ]
            },
            "schema_compatibility": {"decision": "compatible"},
            "effective_mode_ref": sha("e"),
            "fallback_degradation_ref": sha("d"),
            "degradation_ledger_ref": sha("d"),
        },
        "continuous_governance_reissue": {
            "schema_version": "policyos.runtime.governance_lifecycle_report.v1",
            "status": "pass",
            "issues": [],
            "lifecycle_decision": "reissue",
            "decision_status": "reissued",
            "continuous_governance_reissue_report_ref": runtime_cas_refs()[
                "continuous_governance_reissue_report_ref"
            ],
            "diagnostic_event": {
                "event_type": "polisyos.runtime.diagnostic.reconciliation_result.v1",
                "artifact_refs": [runtime_cas_refs()["continuous_governance_reissue_report_ref"]],
                "sampling_decision": "always_record",
                "sampling_rate": 1.0,
            },
            "cas_artifact_refs": {
                "governance_lifecycle_report_ref": runtime_cas_refs()[
                    "continuous_governance_reissue_report_ref"
                ]
            },
            "schema_compatibility": {"decision": "compatible"},
            "effective_mode_ref": sha("e"),
            "fallback_degradation_ref": sha("d"),
            "degradation_ledger_ref": sha("d"),
        },
        "continuous_governance_supersede": {
            "schema_version": "policyos.runtime.governance_lifecycle_report.v1",
            "status": "pass",
            "issues": [],
            "lifecycle_decision": "supersede",
            "decision_status": "superseded",
            "continuous_governance_supersede_report_ref": runtime_cas_refs()[
                "continuous_governance_supersede_report_ref"
            ],
            "diagnostic_event": {
                "event_type": "polisyos.runtime.diagnostic.reconciliation_result.v1",
                "artifact_refs": [runtime_cas_refs()["continuous_governance_supersede_report_ref"]],
                "sampling_decision": "always_record",
                "sampling_rate": 1.0,
            },
            "cas_artifact_refs": {
                "governance_lifecycle_report_ref": runtime_cas_refs()[
                    "continuous_governance_supersede_report_ref"
                ]
            },
            "schema_compatibility": {"decision": "compatible"},
            "effective_mode_ref": sha("e"),
            "fallback_degradation_ref": sha("d"),
            "degradation_ledger_ref": sha("d"),
        },
        "continuous_governance_withdraw": {
            "schema_version": "policyos.runtime.governance_lifecycle_report.v1",
            "status": "pass",
            "issues": [],
            "lifecycle_decision": "withdraw",
            "decision_status": "withdrawn",
            "continuous_governance_withdraw_report_ref": runtime_cas_refs()[
                "continuous_governance_withdraw_report_ref"
            ],
            "diagnostic_event": {
                "event_type": "polisyos.runtime.diagnostic.reconciliation_result.v1",
                "artifact_refs": [runtime_cas_refs()["continuous_governance_withdraw_report_ref"]],
                "sampling_decision": "always_record",
                "sampling_rate": 1.0,
            },
            "cas_artifact_refs": {
                "governance_lifecycle_report_ref": runtime_cas_refs()[
                    "continuous_governance_withdraw_report_ref"
                ]
            },
            "schema_compatibility": {"decision": "compatible"},
            "effective_mode_ref": sha("e"),
            "fallback_degradation_ref": sha("d"),
            "degradation_ledger_ref": sha("d"),
        },
        "source_truth_adapter_surfaces": {
            "runtime.canary_bundle": {"final_claims": source_truth_payload},
            "runtime.scorecard": {"final_claims": deepcopy(source_truth_payload)},
        },
        "source_truth_adapter_paths": ["bundle_to_scorecard"],
        "phase_barrier_records": phase_barrier_records(),
        "assurance_case": {
            "schema_version": "policyos.runtime.assurance_case.v1",
            "claim": {
                "text": "Serious PolicyOS closeout is supported by runtime authority.",
                "status": "supported",
                "run_id": "R_hds_red_control",
                "job_id": "job-hds-red-control",
                "canary_kind": "production",
                "quality_status": "pass",
                "approval_state": "approval_ready",
            },
            "subclaims": [],
            "argument": "Runtime-owned diagnostic evidence supports closeout.",
            "argument_strategy": "runtime_authority_graph",
            "evidence": [{"key": "quality_scorecard", "ref": sha("a")}],
            "assumptions": ["Fixture assurance case is replaced by canary final assembly."],
            "contexts": {"quality_scorecard_ref": sha("a")},
            "defeaters": [],
            "blockers": [],
            "unresolved_uncertainty": [],
            "confidence_limits": {"lower_bound": 0.8, "upper_bound": 0.99},
            "non_overridable_blockers": [],
            "reviewer_attribution": {"reviewer_id": "fixture", "review_status": "pending"},
            "owner": "team-assurance",
            "next_diagnostic_command": (
                "uv run python tools/quality/validation/check_honest_diagnostics_proof_harness.py "
                "--repo-root . --require-passing"
            ),
        },
        "policy_design_case": build_policy_design_case_profile(
            case_id="pdc-R_hds_red_control",
            run_id="R_hds_red_control",
            job_id="job-hds-red-control",
            tenant_id="tenant-1",
            effective_execution_profile="production",
            intent_envelope=policy_design_intent_envelope(),
            capability_ledger=policy_design_capability_ledger(),
            runtime_authority={
                "authority_role": "producer_authority",
                "provenance_kind": "runtime_emitted",
                "cas_ref": sha("1"),
                "runtime_event_ref": sha("e"),
                "same_input_closure_ref": sha("3"),
                "effective_mode_ref": sha("e"),
                "schema_compatibility_ref": sha("c"),
            },
            nodes=[
                complete_policy_design_concept_spine(
                    policy_intent_ref=runtime_cas_refs()["policy_intent_ref"],
                )
            ],
        ),
        "diagnostic_slo_report": build_diagnostic_slo_report(
            observations=pass_observations_for_all_diagnostic_slos(
                observed_at=None,
                evidence_ref=sha("a"),
            ),
            run_id="R_hds_red_control",
            canary_kind="production",
            owner="team-assurance",
        ),
    }
    evidence["policy_design_case"]["claim_registry"] = {
        "schema_version": "policyos.runtime.policy_design_case.claim_registry.v1",
        "runtime_authority": {
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": sha("a"),
            "runtime_event_ref": "event://policy_design_case/claim/rec_1",
        },
        "claims": [
            {
                "claim_id": "rec_1",
                "assurance_node_id": "claim-node-rec-1",
                "claim_ref": sha("a"),
                "runtime_event_ref": "event://policy_design_case/claim/rec_1",
                "concept_refs": ["concept.msme_survival_rate"],
                "legal_norm_refs": ["norm.ua.credit_eligibility"],
                "source_data_refs": ["production-msme-panel", sha("4")],
                "scholar_refs": ["literature:msme-survival-review"],
                "method_refs": ["causal.difference_in_differences"],
                "portfolio_refs": ["portfolio.rec_1"],
                "independence_refs": ["independence.rec_1"],
                "specification_curve_refs": ["specification_curve.rec_1"],
                "disconfirming_refs": ["disconfirming.rec_1"],
                "synthesis_refs": ["synthesis.rec_1"],
                "objective_tradeoff_refs": ["objective.msme_survival"],
                "uncertainty_refs": ["uncertainty:survival-v1"],
                "numerical_semantics_refs": ["num_semantics.rec_1"],
                "monitoring_refs": ["monitoring.plan.rec_1"],
                "selected_producer_refs": {
                    "lex": ["norm.ua.credit_eligibility"],
                    "fabric": ["production-msme-panel"],
                    "data_forge": [sha("4")],
                    "scholar": ["literature:msme-survival-review"],
                    "foundry": [
                        "causal.difference_in_differences",
                        "uncertainty:survival-v1",
                    ],
                    "options_objectives": ["objective.msme_survival"],
                },
            }
        ],
    }
    evidence["policy_design_case"]["jurisdiction_spine"] = build_policy_design_jurisdiction_spine(
        spine_id="jurisdiction-spine-R_hds_red_control",
        jurisdiction_spine_ref=sha("6"),
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-1",
        policy_intent_ref=runtime_cas_refs()["policy_intent_ref"],
        lex_normative_report=evidence["normative_evidence"],
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": sha("6"),
            "runtime_event_ref": sha("e"),
            "same_input_closure_ref": sha("3"),
            "effective_mode_ref": sha("e"),
            "schema_compatibility_ref": sha("c"),
        },
    )
    evidence["policy_design_case"].update(policy_design_phase27_records())
    evidence["policy_design_case"].update(policy_design_phase28_1_records())
    evidence["policy_design_case"].update(policy_design_phase28_2_records())
    evidence["policy_design_case"].update(policy_design_phase28_3_records())
    evidence["policy_design_case"].update(policy_design_phase28_4_records())
    evidence["policy_design_case"].update(policy_design_phase28_5_records())
    evidence["policy_design_case"].update(policy_design_phase29_1_records())
    evidence["policy_design_case"].update(policy_design_phase29_2_records())
    evidence["policy_design_case"].update(policy_design_phase29_3_records())
    evidence["policy_design_case"].update(policy_design_phase30_records())
    evidence["policy_design_case"]["record_families"] = policy_design_record_family_rows()
    evidence["policy_design_case"]["records"] = policy_design_runtime_record_family_records()
    evidence["policy_design_case"]["policy_design_case_ref"] = runtime_cas_refs()[
        "policy_design_case_ref"
    ]
    if authority_envelopes:
        refs = runtime_cas_refs()
        for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
            report = evidence.get(report_key)
            if isinstance(report, dict) and ref_key in refs:
                report["authority_envelope"] = authority_envelope_for(
                    report_key=report_key,
                    ref_key=ref_key,
                    ref_value=refs[ref_key],
                )
    return evidence


def scorecard_for(
    *,
    canary_kind: str = "production",
    job_payload: dict[str, Any] | None = None,
    quality_evidence: dict[str, Any] | None = None,
    normalize: bool = True,
) -> dict[str, Any]:
    evidence = deepcopy(quality_evidence or complete_quality_evidence())
    if normalize:
        evidence = normalize_quality_evidence(evidence, canary_kind=canary_kind)
    return build_quality_scorecard(
        canary_kind=canary_kind,
        job_id="job-hds-red-control",
        run_id="R_hds_red_control",
        execution_status="completed",
        job_payload=job_payload or complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=evidence,
    )


def blocking_codes(scorecard: dict[str, Any]) -> set[str]:
    return {
        str(failure.get("code") or failure.get("gate"))
        for failure in scorecard.get("blocking_quality_failures", [])
        if isinstance(failure, dict)
    }
