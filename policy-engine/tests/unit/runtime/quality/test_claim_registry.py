from __future__ import annotations

from polisyos.runtime.quality.claim_registry import (
    build_runtime_claim_registry,
    claim_registry_rows_by_id,
    normalize_runtime_claim_registry,
)
from polisyos.runtime.quality.ir_analytics_bridge import (
    build_ir_analytics_claim_bridge,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _major_claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "claim_id": "rec_credit_guarantee",
        "claim_family": "recommendation",
        "major": True,
        "text": "Target capped credit guarantees to liquidity-constrained MSMEs.",
    }
    claim.update(overrides)
    return claim


def _hypothesis_ledger() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.hypothesis_ledger.v1",
        "run_id": "run-wave6f",
        "job_id": "job-wave6f",
        "entries": [
            {
                "candidate_id": "hypothesis-candidate:legal-reading-1",
                "candidate_ref": "hypothesis-candidate:legal-reading-1",
                "source_class": "llm_candidate",
                "candidate_kind": "legal_reading",
                "target_authority_slots": ["legal_authority"],
                "target_claim_ids": ["rec_credit_guarantee"],
                "prompt_fingerprint": "sha256:" + "1" * 64,
                "tool_refs": ["tool-output:lex-probe"],
                "repair_decision_lineage": ["repair:none"],
                "authority_envelope": {
                    "authoritative_for": ["candidate_hypothesis"],
                    "may_not_use_for": ["legal_authority", "claim_authority"],
                },
                "admission_state": "candidate_unverified",
            }
        ],
    }


def test_runtime_claim_registry_rejects_global_pools_without_per_claim_entry() -> None:
    registry = normalize_runtime_claim_registry(
        {"schema_version": "policyos.runtime.claim_registry.v1", "claims": []},
        claims=[_major_claim()],
        normative_evidence={
            "status": "pass",
            "applied_norms": [{"norm_id": "norm.ua.credit_guarantee"}],
        },
        foundry_method_report={
            "status": "pass",
            "selected_methods": [{"method_id": "foundry.execute"}],
        },
    )

    issue_codes = {issue["code"] for issue in registry["issues"]}
    assert registry["status"] == "fail"
    assert "runtime_claim_registry_entry_missing" in issue_codes
    assert registry["summary"]["claim_count"] == 0
    assert registry["summary"]["global_norm_ref_count"] == 1
    assert registry["summary"]["generic_global_method_ref_count"] == 1


def test_runtime_claim_registry_blocks_unverified_hypothesis_candidate_in_authority_slot() -> None:
    registry = build_runtime_claim_registry(
        claims=[
            _major_claim(
                scenario_requirement_refs=["scenario.req.credit_support"],
                data_refs=["source.msme_panel"],
                selected_norm_refs=["hypothesis-candidate:legal-reading-1"],
                method_output_refs=["foundry.did.msme_survival"],
                portfolio_refs=["portfolio.rec_credit_guarantee"],
                argument_refs=["argument.rec_credit_guarantee"],
                warrant_refs=["warrant.rec_credit_guarantee"],
                rebuttal_refs=["rebuttal.rec_credit_guarantee"],
                counter_evidence_refs=["counter.rec_credit_guarantee"],
                limitation_refs=["data-quality.recency.msme_panel"],
                accepted_deficit_refs=["deficit.recency.msme_panel"],
                assumption_gate_refs=["assumption-gate.rec_credit_guarantee"],
                uncertainty_refs=["uncertainty.rec_credit_guarantee"],
            )
        ],
        run_id="run-wave6f",
        hypothesis_ledger=_hypothesis_ledger(),
    )

    issue_codes = {issue["code"] for issue in registry["issues"]}
    assert registry["status"] == "fail"
    assert "candidate_firewall_candidate_unverified" in issue_codes


def test_runtime_claim_registry_binds_major_claim_to_all_required_axes() -> None:
    registry = build_runtime_claim_registry(
        claims=[
            _major_claim(
                scenario_requirement_refs=["scenario.req.credit_support"],
                data_refs=["source.msme_panel"],
                selected_norm_refs=["norm.ua.credit_guarantee"],
                rejected_norm_refs=["norm.ua.unrelated"],
                method_output_refs=["foundry.did.msme_survival"],
                portfolio_refs=["portfolio.rec_credit_guarantee"],
                argument_refs=["argument.rec_credit_guarantee"],
                warrant_refs=["warrant.rec_credit_guarantee"],
                rebuttal_refs=["rebuttal.rec_credit_guarantee"],
                counter_evidence_refs=["counter.rec_credit_guarantee"],
                limitation_refs=["data-quality.recency.msme_panel"],
                accepted_deficit_refs=["deficit.recency.msme_panel"],
                assumption_gate_refs=["assumption-gate.rec_credit_guarantee"],
                independence_refs=["independence.rec_credit_guarantee"],
                synthesis_refs=["synthesis.rec_credit_guarantee"],
                scholar_deficit_refs=["scholar-deficit.msme_credit"],
                objective_tradeoff_refs=["objective_tradeoff.rec_credit_guarantee"],
                uncertainty_refs=["uncertainty.rec_credit_guarantee"],
                numerical_semantics_refs=["num_semantics.rec_credit_guarantee"],
                monitoring_refs=["monitoring.rec_credit_guarantee"],
                specification_curve_refs=["spec_curve.rec_credit_guarantee"],
                claim_ref=_sha("a"),
                runtime_event_ref="event://runtime_claim_registry/rec_credit_guarantee",
            )
        ],
        run_id="run-wave6",
    )

    rows = claim_registry_rows_by_id(registry)
    row = rows["rec_credit_guarantee"]

    assert registry["status"] == "pass"
    assert row["scenario_requirement_refs"] == ["scenario.req.credit_support"]
    assert row["data_refs"] == ["source.msme_panel"]
    assert row["selected_norm_refs"] == ["norm.ua.credit_guarantee"]
    assert row["rejected_norm_refs"] == ["norm.ua.unrelated"]
    assert row["method_output_refs"] == ["foundry.did.msme_survival"]
    assert row["portfolio_refs"] == ["portfolio.rec_credit_guarantee"]
    assert row["argument_refs"] == ["argument.rec_credit_guarantee"]
    assert row["warrant_refs"] == ["warrant.rec_credit_guarantee"]
    assert row["rebuttal_refs"] == ["rebuttal.rec_credit_guarantee"]
    assert row["counter_evidence_refs"] == ["counter.rec_credit_guarantee"]
    assert row["limitation_refs"] == ["data-quality.recency.msme_panel"]
    assert row["accepted_deficit_refs"] == ["deficit.recency.msme_panel"]
    assert row["assumption_gate_refs"] == ["assumption-gate.rec_credit_guarantee"]
    assert row["source_data_refs"] == ["source.msme_panel"]
    assert row["legal_norm_refs"] == ["norm.ua.credit_guarantee"]
    assert row["method_refs"] == ["foundry.did.msme_survival"]
    assert row["selected_producer_refs"]["lex"] == ["norm.ua.credit_guarantee"]
    assert row["selected_producer_refs"]["foundry"] == [
        "foundry.did.msme_survival",
        "assumption-gate.rec_credit_guarantee",
        "uncertainty.rec_credit_guarantee",
    ]


def test_superiority_claim_requires_baseline_and_named_alternative_refs() -> None:
    registry = build_runtime_claim_registry(
        claims=[
            _major_claim(
                claim_use="superiority",
                scenario_requirement_refs=["scenario.req.credit_support"],
                data_refs=["source.msme_panel"],
                selected_norm_refs=["norm.ua.credit_guarantee"],
                method_output_refs=["foundry.did.msme_survival"],
                portfolio_refs=["portfolio.rec_credit_guarantee"],
                argument_refs=["argument.rec_credit_guarantee"],
                warrant_refs=["warrant.rec_credit_guarantee"],
                rebuttal_refs=["rebuttal.rec_credit_guarantee"],
                counter_evidence_refs=["counter.rec_credit_guarantee"],
                limitation_refs=["data-quality.recency.msme_panel"],
                accepted_deficit_refs=["deficit.recency.msme_panel"],
                assumption_gate_refs=["assumption-gate.rec_credit_guarantee"],
                uncertainty_refs=["uncertainty.rec_credit_guarantee"],
            )
        ],
        run_id="run-wave6d",
    )

    assert registry["status"] == "fail"
    assert "runtime_claim_registry_superiority_comparator_refs_missing" in {
        issue["code"] for issue in registry["issues"]
    }


def test_runtime_claim_registry_rejects_method_output_without_assumption_refs() -> None:
    registry = build_runtime_claim_registry(
        claims=[
            _major_claim(
                scenario_requirement_refs=["scenario.req.credit_support"],
                data_refs=["source.msme_panel"],
                selected_norm_refs=["norm.ua.credit_guarantee"],
                method_output_refs=["method-output:did"],
                portfolio_refs=["portfolio.rec_credit_guarantee"],
                argument_refs=["argument.rec_credit_guarantee"],
                warrant_refs=["warrant.rec_credit_guarantee"],
                rebuttal_refs=["rebuttal.rec_credit_guarantee"],
                counter_evidence_refs=["counter.rec_credit_guarantee"],
                limitation_refs=["method-limit.did"],
                accepted_deficit_refs=["deficit.recency.msme_panel"],
            )
        ],
        run_id="run-wave3-foundry",
    )

    issue_codes = {issue["code"] for issue in registry["issues"]}
    assert registry["status"] == "fail"
    assert "runtime_claim_registry_assumption_gate_refs_missing" in issue_codes
    assert "runtime_claim_registry_uncertainty_refs_missing" in issue_codes


def test_ir_analytics_bridge_projects_proof_refs_into_claim_registry() -> None:
    bridge = build_ir_analytics_claim_bridge(
        claim_bindings=[
            {
                "claim_id": "rec_credit_guarantee",
                "analytics_ref": "ir.analytics.partial_id.msme_survival",
                "method_output_refs": ["ir.method.partial_identification.ate"],
                "certificate_refs": ["ir.certificate.dual.msme_survival"],
                "proof_status": "identified",
                "proof_composability_status": "reusable",
                "proof_composability_refs": ["ir.proof_composability.msme_survival"],
                "uncertainty_refs": ["ir.uncertainty.msme_survival"],
                "baseline_refs": ["baseline.status_quo.msme_survival"],
                "conflict_refs": ["conflict.method.msme_survival"],
            }
        ],
        run_id="run-w3a-ir",
    )

    assert bridge["capability_reality_status"] == "implemented"
    authoritative_for = bridge["runtime_authority_envelope"]["authoritative_for"]
    assert "claim_bound_ir_proof_status" in authoritative_for
    assert "legal_authority" in bridge["runtime_authority_envelope"]["may_not_use_for"]

    registry = build_runtime_claim_registry(
        claims=[
            _major_claim(
                requires_ir_analytics=True,
                scenario_requirement_refs=["scenario.req.credit_support"],
                data_refs=["source.msme_panel"],
                selected_norm_refs=["norm.ua.credit_guarantee"],
                portfolio_refs=["portfolio.rec_credit_guarantee"],
                argument_refs=["argument.rec_credit_guarantee"],
                warrant_refs=["warrant.rec_credit_guarantee"],
                rebuttal_refs=["rebuttal.rec_credit_guarantee"],
                counter_evidence_refs=["counter.rec_credit_guarantee"],
                limitation_refs=["limitation.rec_credit_guarantee"],
                accepted_deficit_refs=["deficit.rec_credit_guarantee"],
            )
        ],
        ir_analytics_bridge=bridge,
        run_id="run-w3a-ir",
    )

    row = claim_registry_rows_by_id(registry)["rec_credit_guarantee"]

    assert registry["status"] == "pass"
    assert row["ir_analytics_refs"] == ["ir.analytics.partial_id.msme_survival"]
    assert row["method_output_refs"] == ["ir.method.partial_identification.ate"]
    assert row["ir_certificate_refs"] == ["ir.certificate.dual.msme_survival"]
    assert row["proof_composability_refs"] == ["ir.proof_composability.msme_survival"]
    assert row["proof_composability_statuses"] == ["reusable"]
    assert row["uncertainty_refs"] == ["ir.uncertainty.msme_survival"]
    assert row["baseline_refs"] == ["baseline.status_quo.msme_survival"]
    assert row["conflict_refs"] == ["conflict.method.msme_survival"]
    assert row["selected_producer_refs"]["ir_analytics"] == [
        "ir.analytics.partial_id.msme_survival",
        "ir.method.partial_identification.ate",
        "ir.certificate.dual.msme_survival",
        "ir.uncertainty.msme_survival",
        "ir.proof_composability.msme_survival",
    ]
    assert registry["summary"]["ir_analytics_binding_count"] == 1


def test_ir_analytics_required_claim_fails_without_bridge_binding() -> None:
    registry = normalize_runtime_claim_registry(
        {
            "schema_version": "policyos.runtime.claim_registry.v1",
            "claims": [
                {
                    "claim_id": "rec_credit_guarantee",
                    "scenario_requirement_refs": ["scenario.req.credit_support"],
                    "data_refs": ["source.msme_panel"],
                    "selected_norm_refs": ["norm.ua.credit_guarantee"],
                    "method_output_refs": ["ir.method.partial_identification.ate"],
                    "portfolio_refs": ["portfolio.rec_credit_guarantee"],
                    "argument_refs": ["argument.rec_credit_guarantee"],
                    "warrant_refs": ["warrant.rec_credit_guarantee"],
                    "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
                    "counter_evidence_refs": ["counter.rec_credit_guarantee"],
                    "limitation_refs": ["limitation.rec_credit_guarantee"],
                    "accepted_deficit_refs": ["deficit.rec_credit_guarantee"],
                }
            ],
        },
        claims=[_major_claim(requires_ir_analytics=True)],
    )

    issue_codes = {issue["code"] for issue in registry["issues"]}
    assert registry["status"] == "fail"
    assert "runtime_claim_registry_ir_analytics_bridge_missing" in issue_codes


def test_ir_analytics_negative_certificate_blocks_claim_registry_entry() -> None:
    bridge = build_ir_analytics_claim_bridge(
        claim_bindings=[
            {
                "claim_id": "rec_credit_guarantee",
                "analytics_ref": "ir.analytics.id.msme_survival",
                "method_output_refs": ["ir.method.identification.ate"],
                "negative_certificate_refs": ["ir.negative_certificate.hedge.msme"],
                "proof_status": "not_identified",
                "proof_composability_status": "rederive",
                "proof_composability_refs": ["ir.proof_composability.broken.msme"],
            }
        ],
        run_id="run-w3a-negative",
    )

    registry = build_runtime_claim_registry(
        claims=[
            _major_claim(
                requires_ir_analytics=True,
                scenario_requirement_refs=["scenario.req.credit_support"],
                data_refs=["source.msme_panel"],
                selected_norm_refs=["norm.ua.credit_guarantee"],
                portfolio_refs=["portfolio.rec_credit_guarantee"],
                argument_refs=["argument.rec_credit_guarantee"],
                warrant_refs=["warrant.rec_credit_guarantee"],
                rebuttal_refs=["rebuttal.rec_credit_guarantee"],
                counter_evidence_refs=["counter.rec_credit_guarantee"],
                limitation_refs=["limitation.rec_credit_guarantee"],
                accepted_deficit_refs=["deficit.rec_credit_guarantee"],
            )
        ],
        ir_analytics_bridge=bridge,
        run_id="run-w3a-negative",
    )

    row = claim_registry_rows_by_id(registry)["rec_credit_guarantee"]
    issue_codes = {issue["code"] for issue in registry["issues"]}

    assert registry["status"] == "fail"
    assert "runtime_claim_registry_ir_analytics_blocked" in issue_codes
    assert row["negative_certificate_refs"] == ["ir.negative_certificate.hedge.msme"]
    assert "ir.negative_certificate.hedge.msme" in row["blocker_refs"]
    assert "ir.negative_certificate.hedge.msme" in row["counter_evidence_refs"]
    assert row["rejected_method_refs"] == ["ir.method.identification.ate"]
