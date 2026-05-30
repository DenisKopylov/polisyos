from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import (
    RuntimePolicyDesignCase,
    RuntimePolicyDesignCaseCompilerError,
    compile_runtime_policy_design_case,
    persist_runtime_policy_design_case_graph,
    runtime_policy_design_case_projection_source,
)
from tests._helpers.policy_design_case_projection import policy_design_case, sha

NOW = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)


def test_compiler_emits_runtime_owned_graph_from_existing_runtime_surfaces() -> None:
    graph = compile_runtime_policy_design_case(
        run_id="run-24",
        job_id="job-24",
        tenant_id="tenant-24",
        policy_design_case=policy_design_case(),
        claims=[
            {
                "claim_id": "claim-credit-access",
                "claim_type": "causal",
                "claim_family": "causal",
                "claim_use": "decision_support",
                "text": "Credit guarantees improve MSME survival.",
                "support_status": "supported",
                "publishability": "review_required",
                "readiness_level": "recommendation_ready",
                "facet_refs": ["facet:finance"],
                "obligation_refs": ["obligation:authority", "obligation:data"],
                "baseline_refs": ["baseline:status-quo"],
                "alternative_refs": ["alternative:grant-programme"],
                "evidence_refs": [{"uri": sha("1"), "kind": "cas"}],
            }
        ],
        claim_registry={
            "schema_version": "policyos.runtime.claim_registry.v1",
            "runtime_claim_registry_ref": "cas://claim-registry/run-24",
            "claims": [
                {
                    "claim_id": "claim-credit-access",
                    "data_refs": ["data-binding:msme-survival"],
                    "selected_norm_refs": ["legal-authority:credit-guarantee"],
                    "method_output_refs": ["method-output:did-estimate"],
                    "argument_refs": ["argument:credit-access"],
                    "warrant_refs": ["warrant:identification"],
                    "counter_evidence_refs": ["counter-evidence:bank-channel-risk"],
                    "limitation_refs": ["limitation:wartime-sample"],
                    "accepted_deficit_refs": ["deficit:single-line-evidence"],
                    "independence_refs": ["independence-map:duplicate-collapse"],
                    "conflict_refs": ["conflict:implementation-capacity"],
                    "baseline_refs": ["baseline:status-quo"],
                    "alternative_refs": ["alternative:grant-programme"],
                }
            ],
        },
        semantic_binding={
            "schema_version": "policyos.semantic_binding_ledger.v1",
            "semantic_binding_ref": "cas://semantic-binding/run-24",
            "status": "pass",
        },
        closeout_verdict={
            "schema_version": "policyos.runtime.can_i_closeout.integration.v1",
            "status": "closed_with_limitations",
            "verdict": "can_closeout_with_limitations",
            "can_closeout": True,
            "limitations": [
                {
                    "code": "single_line_evidence_limit",
                    "severity": "limitation",
                    "claim_ids": ["claim-credit-access"],
                    "evidence_ref": "deficit:single-line-evidence",
                }
            ],
            "authority_envelope": {
                "authoritative_for": ["closeout_verdict"],
                "may_not_use_for": ["claim_authority"],
            },
        },
        contested_records=[
            {
                "contested_record_id": "contest:bank-channel-risk",
                "case_ref": "pdc-wave-24",
                "claim_refs": ["claim-credit-access"],
                "contestability_status": "contested",
                "grounds": ["implementation counterevidence"],
                "authority_profile": "production",
                "publication_effect": "review_before_publication",
                "public_projection_effect": "show_contested_state",
            }
        ],
        deficit_register=[
            {
                "deficit_id": "deficit:single-line-evidence",
                "deficit_family": "evidence",
                "deficit_code": "single_line_evidence_limit",
                "claim_ids": ["claim-credit-access"],
                "authority_level": "production",
                "audience_scope": "reviewer",
                "disposition": "publish_with_limitation",
                "owner": "team-policyos-runtime",
                "ttl_expires_at": "2026-06-01T00:00:00Z",
                "runtime_event_ref": "event://deficit/single-line",
                "evidence_ref": "deficit:single-line-evidence",
            }
        ],
        generated_at=NOW,
    )

    assert isinstance(graph, RuntimePolicyDesignCase)
    assert graph.schema_version == "policyos.runtime.pdc.graph.v1"
    assert graph.authority_envelope.authoritative_for == ("pdc_graph_structure",)
    assert {
        "projection_authority",
        "claim_authority",
    } <= set(graph.authority_envelope.may_not_use_for)
    assert graph.claim_registry_ref == "cas://claim-registry/run-24"
    assert graph.semantic_binding_refs == ("cas://semantic-binding/run-24",)
    assert graph.closeout_refs
    assert graph.claim_graph.claims[0].producer_binding_refs == (
        "data-binding:msme-survival",
        "legal-authority:credit-guarantee",
        "method-output:did-estimate",
    )
    assert graph.claim_graph.claims[0].conflict_refs == (
        "conflict:implementation-capacity",
        "counter-evidence:bank-channel-risk",
    )
    assert graph.warrant_structures[0].warrant_refs == ("warrant:identification",)
    assert graph.effective_independence_refs == ("independence-map:duplicate-collapse",)
    assert graph.contested_record_refs == ("contest:bank-channel-risk",)
    assert graph.deficit_register_refs == ("deficit:single-line-evidence",)
    assert graph.capability_reality_label == "implemented"


def test_projection_source_is_derived_from_graph_not_scattered_projection_fields() -> None:
    graph = compile_runtime_policy_design_case(
        run_id="run-24",
        job_id="job-24",
        tenant_id="tenant-24",
        policy_design_case=policy_design_case(),
        claims=[
            {
                "claim_id": "claim-1",
                "claim_type": "factual",
                "claim_use": "decision_support",
                "text": "Policy claim.",
                "support_status": "supported",
                "publishability": "review_required",
                "readiness_level": "recommendation_ready",
                "obligation_refs": ["obligation:1"],
            }
        ],
        claim_registry={
            "claims": [
                {
                    "claim_id": "claim-1",
                    "data_refs": ["data:1"],
                    "selected_norm_refs": ["norm:1"],
                    "method_output_refs": ["method:1"],
                }
            ]
        },
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "claim_registry_missing_anchor",
                    "severity": "fail",
                    "message": "Missing anchor.",
                }
            ],
        },
        generated_at=NOW,
    )

    source = runtime_policy_design_case_projection_source(graph)

    assert source["authority_role"] == "projection_only"
    assert source["projection_policy"] == "reads_runtime_policy_design_case_graph"
    assert source["runtime_pdc_graph_ref"] == graph.graph_ref
    assert source["closeout_verdict"]["status"] == "blocked"
    assert source["claim_graph_summary"]["claim_count"] == 1
    assert "projection_authority" in source["source_authority_boundary"]["may_not_use_for"]


def test_runtime_policy_design_case_graph_persists_as_runtime_artifact(tmp_path: Path) -> None:
    graph = compile_runtime_policy_design_case(
        run_id="run-persist",
        job_id="job-persist",
        tenant_id="tenant-persist",
        policy_design_case=policy_design_case(),
        claims=[
            {
                "claim_id": "claim-persist",
                "claim_type": "factual",
                "claim_use": "decision_support",
                "text": "Persisted runtime graph claim.",
                "obligation_refs": ["obligation:persist"],
            }
        ],
        claim_registry={
            "claims": [
                {
                    "claim_id": "claim-persist",
                    "data_refs": ["data:persist"],
                }
            ]
        },
        generated_at=NOW,
    )
    store = FileSystemCAS(tmp_path)

    ref = persist_runtime_policy_design_case_graph(graph, store=store)
    manifest = store.get_manifest(ref.artifact_id)

    assert ref.kind == "runtime.policy_design_case_graph"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "policyos.runtime.pdc.graph.v1"


def test_compiler_rejects_llm_candidate_laundering_into_claim_graph() -> None:
    with pytest.raises(
        RuntimePolicyDesignCaseCompilerError,
        match="runtime_pdc_graph_llm_authority_laundering",
    ):
        compile_runtime_policy_design_case(
            run_id="run-llm",
            claims=[
                {
                    "claim_id": "claim-llm",
                    "claim_type": "normative",
                    "claim_use": "decision_support",
                    "text": "LLM-generated policy conclusion.",
                    "support_status": "supported",
                    "publishability": "review_required",
                    "readiness_level": "recommendation_ready",
                    "decomposition_source_class": "llm_candidate",
                    "obligation_refs": ["obligation:1"],
                }
            ],
            claim_registry={"claims": [{"claim_id": "claim-llm", "data_refs": ["data:1"]}]},
            generated_at=NOW,
        )
