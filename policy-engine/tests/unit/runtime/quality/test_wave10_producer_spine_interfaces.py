from __future__ import annotations

# ruff: noqa: S101
from polisyos.fabric.catalog.source_selection_audit import build_fabric_source_selection_trace
from polisyos.foundry.validation.method_quality import build_foundry_method_report
from polisyos.lex.normpack.applicability_report import (
    build_normative_applicability_report,
)
from polisyos.runtime.quality.semantic_binding import (
    build_producer_spine_read_context,
    build_semantic_binding_ledger,
)
from polisyos.scholar import build_scholar_spine_evidence_binding
from polisyos.scientist.artifacts.decision_compiler import compile_draft_decision_packet
from polisyos.scientist.validation.policy_grounding import (
    build_policy_grounding_matrix_report,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _spine_context() -> dict[str, object]:
    return build_producer_spine_read_context(
        concept_spine_ref=_sha("2"),
        jurisdiction_spine_ref=_sha("6"),
        canonical_concept_refs=["concept.msme_survival_rate"],
        jurisdiction_refs=["UA"],
    )


def _assert_spine_fields(report: dict[str, object]) -> None:
    assert report["consumed_concept_spine_ref"] == _sha("2")
    assert report["consumed_jurisdiction_spine_ref"] == _sha("6")
    assert report["candidate_spine_binding_refs"] or report["spine_blocker_refs"]
    assert report.get("local_labels") in ((), [])


def _claim() -> dict[str, object]:
    return {
        "claim_id": "rec_1",
        "claim_type": "recommendation",
        "major": True,
        "text": "Target wartime credit support to improve MSME survival.",
        "data_refs": ["production-msme-panel"],
        "method_refs": ["causal.difference_in_differences"],
        "norm_refs": ["norm.ua.credit_eligibility"],
        "literature_refs": ["literature:msme-survival-review"],
        "uncertainty_refs": ["uncertainty:survival-v1"],
    }


def test_producer_reports_consume_spine_context_and_emit_candidate_bindings() -> None:
    context = _spine_context()

    lex_report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-17",
        },
        candidate_norms=[
            {
                "norm_id": "norm.ua.credit_eligibility",
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "effective_from": "2024-01-01",
                "source_authority": "Ministry of Economy",
                "authority_level": "national",
            }
        ],
        recommendation_claims=[_claim()],
        spine_context=context,
    )
    fabric_report = build_fabric_source_selection_trace(
        query_intent={"query_outcome": "msme_survival_rate"},
        candidate_sources=[
            {
                "source_id": "production-msme-panel",
                "source_family": "production_msme_panel",
                "source_kind": "administrative_panel",
                "freshness": {"status": "pass"},
                "coverage": {"status": "pass"},
                "schema_compatibility": {"status": "pass"},
            }
        ],
        selected_source_ids=["production-msme-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        spine_context=context,
    )
    scholar_report = build_scholar_spine_evidence_binding(
        literature_refs=["literature:msme-survival-review"],
        spine_context=context,
    )
    foundry_report = build_foundry_method_report(
        selected_methods=[
            {
                "method_id": "causal.difference_in_differences",
                "method_family": "causal_effect_estimation",
                "input_refs": {
                    "data_snapshot_ref": _sha("a"),
                    "input_bindings_ref": _sha("b"),
                },
                "assumptions": ["parallel_trends", "stable_composition"],
                "identification_requirements": {
                    "estimand": "ATT",
                    "requirements": ["parallel_trends", "overlap"],
                },
                "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
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
                "specification_space": {
                    "primary": "two_way_fixed_effects",
                    "alternatives": ["event_study", "matched_did"],
                },
                "method_result_refs": {"method_result_ref": _sha("c")},
                "validity_surfaces": {
                    "identification": {"status": "present", "ref": _sha("1")},
                    "transportability": {"status": "present", "ref": _sha("2")},
                    "partial_identification": {"status": "present", "ref": _sha("3")},
                    "recoverability": {"status": "present", "ref": _sha("4")},
                    "causal_ensemble": {"status": "present", "ref": _sha("5")},
                    "falsification": {"status": "present", "ref": _sha("6")},
                    "certificate_proof": {"status": "present", "ref": _sha("7")},
                },
                "input_diagnostics": {
                    "sample_size": 1000,
                    "min_required_sample_size": 100,
                },
                "result_summary": {"effect_estimate": 0.2},
            }
        ],
        expected_method_expectations=["causal_effect_estimation"],
        spine_context=context,
    )
    grounding_report = build_policy_grounding_matrix_report(
        claims=[_claim()],
        normative_evidence=lex_report,
        fabric_retrieval_trace=fabric_report,
        foundry_method_report=foundry_report,
        spine_context=context,
    )
    decision_artifact = compile_draft_decision_packet(
        run_id="run-wave-10",
        final_claims=[_claim()],
        policy_grounding_matrix=grounding_report,
        quality_scorecard={"quality_status": "pass", "approval_state": "approved"},
        conflict_check={"status": "pass"},
        approval_state={"approval_state": "approved"},
        assurance_refs={},
        spine_context=context,
    )
    compiler_contract = decision_artifact["claim_evidence_contract"]

    for report in (
        lex_report,
        fabric_report,
        scholar_report,
        foundry_report,
        grounding_report,
        compiler_contract,
    ):
        assert isinstance(report, dict)
        _assert_spine_fields(report)

    ledger = build_semantic_binding_ledger(
        runtime_refs={
            "policy_intent_ref": _sha("a"),
            "concept_spine_ref": _sha("2"),
            "jurisdiction_spine_ref": _sha("6"),
        },
        normative_evidence=lex_report,
        fabric_retrieval_trace=fabric_report,
        scholar_evidence=scholar_report,
        foundry_method_report=foundry_report,
        policy_grounding_matrix=grounding_report,
        decision_artifact_contract=compiler_contract,
        final_claims=[_claim()],
    )

    for component in (
        "lex",
        "fabric",
        "scholar",
        "foundry",
        "scientist",
        "final_compiler",
    ):
        binding = ledger[component][0]  # type: ignore[index]
        assert binding["consumed_concept_spine_ref"] == _sha("2")
        assert binding["consumed_jurisdiction_spine_ref"] == _sha("6")
        assert binding["candidate_spine_binding_refs"] or binding["spine_blocker_refs"]

    foundry_binding = ledger["foundry"][0]  # type: ignore[index]
    assert foundry_binding["assumption_gate_refs"] == [
        "foundry-assumption-gate:causal.difference_in_differences:parallel_trends",
        "foundry-assumption-gate:causal.difference_in_differences:stable_composition",
    ]
    assert foundry_binding["method_output_refs"] == [_sha("c")]
    assert foundry_binding["uncertainty_refs"]
    assert foundry_binding["limitation_refs"]
    assert foundry_binding["runtime_assumption_gates"][0]["status"] == "pass"
    assert foundry_binding["rejected_method_reasons"] == []
