from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
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


def _s11(name: str) -> Any:
    module = importlib.import_module("polisyos.runtime.quality")
    return getattr(module, name)


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


def _claim_with_required_evidence(**overrides: object) -> dict[str, object]:
    claim = _major_claim(
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
    claim.update(overrides)
    return claim


def _s11_authority_boundary() -> dict[str, object]:
    return {
        "authoritative_for": ["proof_carrying_analytics_validity"],
        "may_not_use_for": [
            "production_authority",
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "rich_simulation_authority",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
        ],
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": ["policyos.layer2.s11.predictive_knowledge.v1"],
    }


def _s11_proof_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "proof_id": "layer2.s11.proof.ua-msme.credit-access",
        "proof_ref": "pdc://layer2/s11/ua-msme/proof/credit-access",
        "case_id": "ua-msme-affordable-loans-2022",
        "claim_id": "rec_credit_guarantee",
        "design_comparison_ref": "comparison://ua-msme/credit-vs-cash",
        "baseline_design_ref": "baseline://ua-msme/no-new-credit",
        "alternative_design_refs": ["alternative://ua-msme/cash-transfer"],
        "ir_analytics_refs": ["ir.analytics.partial_id.msme_survival"],
        "method_output_refs": ["ir.method.partial_identification.ate"],
        "ir_certificate_refs": ["ir.certificate.dual.msme_survival"],
        "negative_certificate_refs": [],
        "proof_status": "identified",
        "proof_composability_status": "reusable",
        "proof_composability_refs": ["ir.proof_composability.msme_survival"],
        "method_requirement_refs": ["method-requirement://partial-identification"],
        "uncertainty_refs": ["ir.uncertainty.msme_survival"],
        "independence_refs": ["independence://ua-msme/current-run"],
        "effective_independence_collapse_refs": [],
        "counter_evidence_refs": [],
        "limitation_refs": ["limitation://proof/partial-identification"],
        "blocker_refs": [],
        "ir_analytics_bridge_ref": "ir-analytics-bridge://ua-msme/credit-access",
        "claim_registry_entry_ref": "claim-registry://ua-msme/rec_credit_guarantee",
        "comparison_consumer_ref": "design-comparison://ua-msme/credit-vs-cash",
        "source_lineage_refs": ["lineage://ua-msme/source-contract"],
        "method_lineage_refs": ["lineage://ua-msme/ir-analytics"],
        "authority_boundary": _s11_authority_boundary(),
        "may_not_use_for": _s11_authority_boundary()["may_not_use_for"],
        "rule_version_ref": "policyos.layer2.s11.predictive_knowledge.v1",
    }
    payload.update(overrides)
    return payload


def _s11_proof_record(**overrides: object) -> Any:
    return _s11("build_proof_carrying_analytics_record")(
        **_s11_proof_payload(**overrides)
    )


def _record_field(record: Any, field_name: str) -> Any:
    if hasattr(record, field_name):
        return getattr(record, field_name)
    return dict(record)[field_name]


def _bridge_from_s11_proof(record: Any) -> dict[str, object]:
    return build_ir_analytics_claim_bridge(
        claim_bindings=[
            {
                "claim_id": _record_field(record, "claim_id"),
                "analytics_ref": _record_field(record, "ir_analytics_refs")[0],
                "method_output_refs": list(_record_field(record, "method_output_refs")),
                "certificate_refs": list(_record_field(record, "ir_certificate_refs")),
                "negative_certificate_refs": list(
                    _record_field(record, "negative_certificate_refs")
                ),
                "proof_status": _record_field(record, "proof_status"),
                "proof_composability_status": _record_field(
                    record,
                    "proof_composability_status",
                ),
                "proof_composability_refs": list(
                    _record_field(record, "proof_composability_refs")
                ),
                "uncertainty_refs": list(_record_field(record, "uncertainty_refs")),
                "baseline_refs": [_record_field(record, "baseline_design_ref")],
                "comparison_refs": [_record_field(record, "design_comparison_ref")],
                "alternative_refs": list(_record_field(record, "alternative_design_refs")),
                "independence_refs": list(_record_field(record, "independence_refs")),
                "limitation_refs": list(_record_field(record, "limitation_refs")),
                "blocker_refs": list(_record_field(record, "blocker_refs")),
            }
        ],
        run_id="run-s11-proof",
        bridge_ref=_record_field(record, "ir_analytics_bridge_ref"),
    )


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


def test_s11_proof_carrying_record_projects_bridge_refs_into_claim_registry() -> None:
    proof = _s11_proof_record()
    bridge = _bridge_from_s11_proof(proof)

    registry = build_runtime_claim_registry(
        claims=[
            _claim_with_required_evidence(
                baseline_refs=[_record_field(proof, "baseline_design_ref")],
                alternative_refs=list(_record_field(proof, "alternative_design_refs")),
                comparison_refs=[_record_field(proof, "design_comparison_ref")],
            )
        ],
        ir_analytics_bridge=bridge,
        run_id="run-s11-proof",
    )

    row = claim_registry_rows_by_id(registry)["rec_credit_guarantee"]

    assert registry["status"] == "pass"
    assert row["ir_analytics_refs"] == ["ir.analytics.partial_id.msme_survival"]
    assert row["method_output_refs"] == ["ir.method.partial_identification.ate"]
    assert row["ir_certificate_refs"] == ["ir.certificate.dual.msme_survival"]
    assert row["proof_composability_refs"] == ["ir.proof_composability.msme_survival"]
    assert row["uncertainty_refs"] == ["ir.uncertainty.msme_survival"]
    assert row["baseline_refs"] == ["baseline://ua-msme/no-new-credit"]
    assert row["selected_producer_refs"]["ir_analytics"]


def test_s11_proof_carrying_record_preserves_design_comparison_refs() -> None:
    proof = _s11_proof_record()
    bridge = _bridge_from_s11_proof(proof)

    registry = build_runtime_claim_registry(
        claims=[
            _claim_with_required_evidence(
                claim_use="superiority",
                baseline_refs=[_record_field(proof, "baseline_design_ref")],
                alternative_refs=list(_record_field(proof, "alternative_design_refs")),
                comparison_refs=[_record_field(proof, "design_comparison_ref")],
            )
        ],
        ir_analytics_bridge=bridge,
        run_id="run-s11-proof-comparison",
    )

    row = claim_registry_rows_by_id(registry)["rec_credit_guarantee"]

    assert registry["status"] == "pass"
    assert row["baseline_refs"] == ["baseline://ua-msme/no-new-credit"]
    assert row["alternative_refs"] == ["alternative://ua-msme/cash-transfer"]
    assert row["comparison_refs"] == ["comparison://ua-msme/credit-vs-cash"]
    assert row["ir_analytics_bridge_ref"] == "ir-analytics-bridge://ua-msme/credit-access"


def test_s11_negative_certificate_blocks_claim_registry_evidence_upgrade() -> None:
    proof = _s11_proof_record(
        negative_certificate_refs=["ir.negative_certificate.hedge.msme"],
        proof_status="not_identified",
        proof_composability_status="rederive",
        blocker_refs=["ir.negative_certificate.hedge.msme"],
    )
    bridge = _bridge_from_s11_proof(proof)

    registry = build_runtime_claim_registry(
        claims=[
            _claim_with_required_evidence(
                baseline_refs=[_record_field(proof, "baseline_design_ref")],
                alternative_refs=list(_record_field(proof, "alternative_design_refs")),
                comparison_refs=[_record_field(proof, "design_comparison_ref")],
            )
        ],
        ir_analytics_bridge=bridge,
        run_id="run-s11-proof-negative",
    )

    row = claim_registry_rows_by_id(registry)["rec_credit_guarantee"]
    issue_codes = {issue["code"] for issue in registry["issues"]}

    assert registry["status"] == "fail"
    assert "runtime_claim_registry_ir_analytics_blocked" in issue_codes
    assert row["negative_certificate_refs"] == ["ir.negative_certificate.hedge.msme"]
    assert "ir.negative_certificate.hedge.msme" in row["blocker_refs"]
    assert row["rejected_method_refs"] == ["ir.method.partial_identification.ate"]


def test_layer3_g3_resolved_bridge_reaches_claim_registry_consumer_gate(
    tmp_path: Path,
) -> None:
    g3 = importlib.import_module("polisyos.runtime.quality.layer3_analytics_search")
    request, proof_bindings, bridge_binding = _g3_resolved_bridge(g3, tmp_path)

    gate = g3.build_g3_claim_registry_consumer_gate(
        request=request,
        ir_analytics_bridge=bridge_binding,
        proof_carrying_analytics_records=proof_bindings,
        claims=(
            _claim_with_required_evidence(
                claim_id=request.claim_id,
                baseline_refs=(request.baseline_ref,),
                alternative_refs=request.alternative_refs,
                comparison_refs=(request.comparison_ref,),
            ),
        ),
    )

    assert gate.status == "pass"
    assert gate.claim_registry_status == "pass"
    assert gate.ir_analytics_bridge_ref == bridge_binding.bridge_ref
    assert gate.proof_carrying_analytics_refs == (proof_bindings[0].proof_ref,)
    assert gate.claim_registry_payload["summary"]["ir_analytics_binding_count"] == 1
    row = claim_registry_rows_by_id(gate.claim_registry_payload)[request.claim_id]
    assert row["ir_analytics_bridge_ref"] == bridge_binding.bridge_ref
    assert row["ir_analytics_refs"] == proof_bindings[0].s11_record["ir_analytics_refs"]


def _g3_resolved_bridge(g3: Any, tmp_path: Path) -> tuple[Any, tuple[Any, ...], Any]:
    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:task5:claim-registry",
        claim_id="rec_credit_guarantee",
        case_id="ua-msme-affordable-loans-2022",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        comparison_ref="comparison://g3/task5/claim-registry",
        baseline_ref="baseline://g3/task5/claim-registry",
        alternative_refs=("alternative://g3/task5/claim-registry",),
        concept_refs=("concept://g3/task5/claim-registry",),
        semantic_spine_refs=("semantic-spine://g3/task5/claim-registry",),
        method_requirement_refs=("g3-method-req:claim-registry",),
        certificate_kinds=("proof_bundle",),
    )
    store = FileSystemCAS(tmp_path / "g3-cas")
    candidates = g3.produce_g3_deterministic_first_case_certificate(request, store=store)
    artifact_index = g3.build_g3_ir_artifact_store_index(
        store=store,
        selected_candidates=candidates,
    )
    certificate_report = g3.build_g3_certificate_resolution_report(
        candidates=candidates,
        artifact_index=artifact_index,
        store=store,
    )
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(
            {
                "requirement_id": request.method_requirement_refs[0],
                "run_id": request.case_id,
                "claim_id": request.claim_id,
                "identification_class": "point",
                "method_expectations": ["causal_identification"],
                "required_method_families": ["causal_identification"],
                "requires_uncertainty_envelope": False,
                "requires_limitation_refs": False,
                "baseline_refs": [request.baseline_ref],
                "alternative_refs": list(request.alternative_refs),
            },
        ),
        selected_method_refs=("ir.method.g3.task5.claim_registry",),
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
    return request, proof_bindings, bridge_binding
