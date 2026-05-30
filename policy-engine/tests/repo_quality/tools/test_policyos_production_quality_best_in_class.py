# ruff: noqa: ANN001, S101

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.assurance_case import (
    POLICY_DESIGN_REQUIRED_CAPABILITIES,
    build_capability_duty_record,
    build_capability_selection_ledger,
    build_policy_design_case_profile,
    build_policy_intent_envelope,
)
from tests._helpers.hds_quality import complete_semantic_binding_ledger
from tools.ci import check_policyos_production_quality_best_in_class as gate

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_FINDING_IDS = {f"PQL-{index:03d}" for index in range(1, 25)}
EXPECTED_FAILURE_CLASSES = {
    "operational_failure",
    "quality_failure",
    "compliance_failure",
    "resilience_failure",
    "approval_failure",
    "closeout_evidence_gap",
}
EXPECTED_HDS_BACKLOG_IDS = {f"A{index}" for index in range(7, 29)}

MINIMAL_INVARIANT: dict[str, Any] = {
    "invariant_id": "HDS-MCG-TEST",
    "minimum_closeout_gate": "serious_canary_runtime_refs",
    "pql_id": "PQL-001",
    "final_owner": "runtime.quality.closeout",
    "producer_owners": ["lex.normative_applicability"],
    "runtime_event_names": ["polisyos.runtime.evidence.normative_applicability_report.v1"],
    "required_artifact_kinds": ["normative_applicability_report"],
    "required_ref_keys": ["normative_applicability_report_ref"],
    "evidence_classes": ["authority_bearing"],
    "allowed_provenance_kinds": ["runtime_emitted"],
    "required_schema_contracts": ["runtime_quality.normative_applicability_report.v1"],
    "scorecard_gate_names": ["normative_evidence_present"],
    "readiness_check": "production_quality.runtime_required_refs",
    "approval_policy": "requires_verified_scorecard",
    "override_policy": "not_overridable",
    "non_overridable_blockers": ["authority_cas_missing"],
    "dashboard_projection_policy": "projection_only",
    "public_artifact_policy": "not_public_exportable",
    "conflict_policy": "fail_closed",
    "failure_code": "hds_runtime_refs_missing",
    "diagnostic_owner": "team-runtime",
    "dependencies": [],
    "consumers": ["runtime.readiness"],
    "next_diagnostic_command": "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q",
    "negative_tests": [
        "tests/unit/runtime/quality/test_scorecard.py::test_warn_scorecards_fail_serious"
    ],
}


def test_readiness_payload_covers_all_findings_and_failure_classes(monkeypatch) -> None:
    _patch_phase32_sources(monkeypatch)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)

    findings = {finding["finding_id"]: finding for finding in payload["findings"]}

    assert payload["schema_version"] == gate.SCHEMA_VERSION
    assert payload["assessment_id"] == "policyos_production_quality_best_in_class"
    assert payload["deterministic_gate"]["requires_live_llm"] is False
    assert payload["deterministic_gate"]["llm_simulation_mode"] == "1"
    assert payload["live_provider_evidence"]["required_for_deterministic_gate"] is False
    assert set(findings) == EXPECTED_FINDING_IDS
    assert {finding["failure_class"] for finding in findings.values()} >= (EXPECTED_FAILURE_CLASSES)
    assert {finding["status"] for finding in findings.values()} <= {"pass", "fail", "warn"}
    assert payload["summary"]["finding_count"] == 24
    assert set(payload["summary"]["failure_class_counts"]) == EXPECTED_FAILURE_CLASSES


def test_closeout_passes_when_all_required_runtime_evidence_is_emitted(monkeypatch) -> None:
    _patch_phase32_sources(monkeypatch)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)

    assert payload["passes_required"] is True
    assert payload["passes_all"] is True
    assert payload["status"] == "pass"
    assert payload["summary"]["status_counts"]["fail"] == 0


def test_security_and_provider_drift_findings_require_report_refs(monkeypatch) -> None:
    _patch_phase32_sources(monkeypatch)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)
    findings = {finding["finding_id"]: finding for finding in payload["findings"]}

    assert findings["PQL-017"]["report_ids"] == ["runtime.security_assurance_report"]
    assert findings["PQL-022"]["report_ids"] == ["runtime.provider_model_quality_ledger"]


def test_readiness_payload_exposes_wave15_portfolio_design_contract_component(
    monkeypatch,
) -> None:
    _patch_phase32_sources(monkeypatch)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)
    component = payload["component_results"][
        "policy_design_evidence_portfolio_design_contract"
    ]

    assert component["status"] == "pass"
    assert component["producer_guard"] == (
        "validate_portfolio_predeclaration_before_evidence_acceptance"
    )
    assert component["coverage_metric"]["value"] == 100.0
    assert component["coverage_metric"]["measurement_status"].startswith("wave15")
    assert set(component["contract_surfaces"]) >= {
        "strands",
        "authority_level",
        "candidate_data_source_families",
        "candidate_method_families",
        "defensible_specification_space",
        "inclusion_exclusion_rules",
        "disconfirming_lines",
        "synthesis_rules",
        "stopping_rules",
        "cost_proportionality",
    }


def test_readiness_payload_exposes_wave30_run_cost_proportionality_component(
    monkeypatch,
) -> None:
    _patch_phase32_sources(monkeypatch)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)
    component = payload["component_results"][
        "policy_design_run_cost_proportionality_contract"
    ]

    assert component["status"] == "pass"
    assert component["producer_guard"] == (
        "build_run_cost_proportionality_ledger_from_quality_context"
    )
    assert component["scorecard_gate"] == "policy_design_wave30_run_cost_proportionality"
    assert "test_assemble_canary_evidence_projects_wave30_run_cost_ledger" in (
        component["expected_verification_command"]
    )
    assert component["coverage_metric"]["value"] >= 50.0
    assert component["coverage_metric"]["measurement_status"].startswith(("wave30", "wave31"))
    assert set(component["contract_surfaces"]) >= {
        "runtime_performance_budget",
        "foundry_cost_model",
        "scientist_budget",
        "doe_search_budget",
        "provider_cost",
        "elapsed_time_budget",
        "human_review_burden",
        "evidence_depth_budget",
        "proportionality_evidence",
    }


def test_readiness_payload_exposes_wave31_best_in_class_benchmarking_component(
    monkeypatch,
) -> None:
    _patch_phase32_sources(monkeypatch)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)
    component = payload["component_results"][
        "policy_design_best_in_class_benchmarking_contract"
    ]

    assert component["status"] == "pass"
    assert component["validator"] == "validate_policy_benchmarking_record"
    assert component["scorecard_gate"] == "policy_design_wave31_best_in_class_benchmarking"
    assert component["coverage_metric"]["value"] == 100.0
    assert component["coverage_metric"]["measurement_status"].startswith("wave31")
    assert set(component["contract_surfaces"]) >= {
        "external_audit_pass_rate",
        "human_team_benchmark",
        "reversal_rate",
        "retraction_rate",
        "calibration_error",
        "claim_substantiation_rate",
        "triangulation_coverage",
        "operator_time_to_root_cause_seconds",
        "run_cost_ledger_refs",
        "proportionality_evidence_refs",
    }


def test_missing_required_serious_profile_ref_fails_with_owner_phase_and_command(
    monkeypatch,
) -> None:
    inventory_payload = _inventory_payload()
    inventory_payload["serious_profile_required_refs"] = [
        {
            "report_id": "scientist.policy_grounding_matrix",
            "expected_ref": "quality_evidence/policy_grounding_matrix.json",
            "status": "missing",
            "owner_runtime_layer": "scientist_policy_artifacts",
            "producer": "runtime Scientist final-policy grounding emitter",
            "first_missing_producer": "runtime Scientist final-policy grounding emitter",
            "validators": [
                "polisyos.scientist.validation.policy_grounding.normalize_policy_grounding_matrix",
            ],
        }
    ]

    _patch_phase32_sources(monkeypatch, inventory_payload=inventory_payload)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)
    ref_failure = payload["required_serious_profile_ref_failures"][0]
    grounding = next(
        finding for finding in payload["findings"] if finding["finding_id"] == "PQL-002"
    )

    assert payload["status"] == "fail"
    assert payload["passes_all"] is False
    assert grounding["status"] == "fail"
    assert ref_failure["expected_ref"] == "quality_evidence/policy_grounding_matrix.json"
    assert ref_failure["owning_layer"] == "scientist_policy_artifacts"
    assert ref_failure["phase"] == "1.4"
    assert ref_failure["next_action"]
    assert ref_failure["expected_verification_command"].startswith("uv run pytest ")


def test_live_provider_evidence_can_be_attached_without_becoming_deterministic_requirement(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)

    evidence = tmp_path / "live-provider-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "policyos.live_provider_evidence.v1",
                "provider": "gonka_proxy",
                "status": "pass",
                "evidence_ref": "sha256:" + "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        external_evidence_paths=[evidence],
    )

    assert payload["deterministic_gate"]["requires_live_llm"] is False
    assert payload["live_provider_evidence"]["required_for_deterministic_gate"] is False
    assert payload["live_provider_evidence"]["attached_count"] == 1
    assert payload["live_provider_evidence"]["attachments"][0]["status"] == "pass"
    assert payload["live_provider_evidence"]["attachments"][0]["provider"] == "gonka_proxy"


def test_serious_evidence_bundle_missing_required_ref_fails_with_guidance(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)

    bundle_root = tmp_path / "bundle"
    (bundle_root / "quality_evidence").mkdir(parents=True)
    (bundle_root / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_evidence.v1",
                "canary_kind": "production",
                "quality_status": "pass",
            }
        ),
        encoding="utf-8",
    )

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    assert payload["status"] == "fail"
    assert payload["required_serious_profile_ref_failures"]
    assert any(
        failure["expected_ref"] == "runtime_quality_ref#normative_applicability_report_ref"
        and failure["owning_layer"]
        and failure["phase"]
        and failure["next_action"]
        and failure["expected_verification_command"]
        for failure in payload["required_serious_profile_ref_failures"]
    )


def test_serious_bundle_warn_status_fails_unless_explicit_dev_smoke(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    serious_root = _write_phase32_bundle(tmp_path / "serious", quality_status="warn")
    dev_root = _write_phase32_bundle(
        tmp_path / "dev",
        canary_kind="dev_smoke",
        quality_status="warn",
        gate_status="warn",
    )

    serious_payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=serious_root,
    )
    dev_payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=dev_root,
    )

    assert serious_payload["status"] == "fail"
    assert _minimum_closeout_failure_codes(serious_payload) >= {"hds_serious_status_not_pass"}
    assert dev_payload["status"] == "warn"
    assert dev_payload["passes_required"] is True


def test_minimum_closeout_gate_requires_authority_bundle_fields(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(
        tmp_path,
        include_runtime_ref=False,
        include_authority_contract=False,
    )

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    assert payload["status"] == "fail"
    assert _minimum_closeout_failure_codes(payload) >= {
        "hds_runtime_ref_missing",
        "hds_authority_envelope_missing",
        "hds_schema_compatibility_missing",
        "hds_same_input_closure_missing",
        "hds_mode_ledger_missing",
        "hds_degradation_ledger_missing",
        "hds_projection_boundary_missing",
    }


def test_readiness_serious_bundle_requires_policy_design_case_runtime_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path)
    job_path = bundle_root / "job.json"
    job = json.loads(job_path.read_text(encoding="utf-8"))
    details = job["progress"]["details"]
    runtime_refs = details["runtime_quality_refs"]
    for ref_key in (
        "policy_intent_envelope_ref",
        "policy_design_capability_ledger_ref",
        "policy_design_case_ref",
    ):
        runtime_refs.pop(ref_key, None)
        details.pop(ref_key, None)
    job_path.write_text(json.dumps(job), encoding="utf-8")
    scorecard_path = bundle_root / "quality_evidence" / "quality_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    evidence_refs = scorecard["evidence_refs"]
    for ref_key in (
        "policy_intent_envelope_ref",
        "policy_design_capability_ledger_ref",
        "policy_design_case_ref",
    ):
        evidence_refs.pop(ref_key, None)
    scorecard_path.write_text(json.dumps(scorecard), encoding="utf-8")

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    assert payload["status"] == "fail"
    assert _minimum_closeout_failure_codes(payload) >= {
        "policy_intent_envelope_ref_missing",
        "policy_design_capability_ledger_ref_missing",
        "policy_design_case_ref_missing",
    }


def test_readiness_serious_bundle_requires_policy_design_case_registry_entry(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path)
    case_path = bundle_root / "quality_evidence" / "policy_design_case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case.pop("case_registry_entry", None)
    case_path.write_text(json.dumps(case), encoding="utf-8")

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    assert payload["status"] == "fail"
    assert "policy_design_case_registry_entry_missing" in _minimum_closeout_failure_codes(payload)


def test_readiness_serious_bundle_fails_stale_scorecard_on_spine_mismatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path)
    quality_dir = bundle_root / "quality_evidence"
    ledger = complete_semantic_binding_ledger()
    spine_context = copy.deepcopy(ledger["spine_context"])
    assert isinstance(spine_context, dict)
    spine_context.update(
        {
            "unit_refs": ["percent"],
            "period_refs": ["2024-2026"],
            "geography_refs": ["UA"],
        }
    )
    ledger["spine_context"] = spine_context
    fabric_binding = copy.deepcopy(ledger["fabric"][0])
    assert isinstance(fabric_binding, dict)
    fabric_binding.update(
        {
            "canonical_concept_refs": ["concept.credit_volume"],
            "jurisdiction_refs": ["PL"],
            "unit_refs": ["uah"],
            "period_refs": ["2020-2021"],
            "geography_refs": ["EU"],
            "local_labels": ["local-only survival concept"],
        }
    )
    ledger["fabric"] = [fabric_binding]
    (quality_dir / "semantic_binding_ledger.json").write_text(
        json.dumps(ledger),
        encoding="utf-8",
    )

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    failures = {
        str(failure["code"]): failure
        for failure in payload["minimum_closeout_gate_failures"]
        if isinstance(failure, dict)
    }
    assert payload["status"] == "fail"
    assert {
        "semantic_producer_concept_mismatch",
        "semantic_producer_jurisdiction_mismatch",
        "semantic_producer_unit_mismatch",
        "semantic_producer_period_mismatch",
        "semantic_producer_geography_mismatch",
        "semantic_local_concept_leakage",
    } <= set(failures)
    mismatch = failures["semantic_producer_unit_mismatch"]
    assert mismatch["source"] == "semantic_binding_ledger"
    assert mismatch["missing_input"]
    assert mismatch["conflicting_producer"] == "fabric"
    assert mismatch["affected_claim"] == "rec_1"
    assert mismatch["next_command"].startswith("uv run ")


def test_policy_design_case_record_registry_missing_owner_fails_readiness(
    monkeypatch,
) -> None:
    _patch_phase32_sources(monkeypatch)
    monkeypatch.setattr(
        gate,
        "_build_policy_design_case_record_registry_report",
        lambda _repo_root: _policy_design_case_registry_report(
            code="policy_design_case_record_family_owner_missing",
            field="producer_owner",
        ),
    )

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)

    assert payload["status"] == "fail"
    assert payload["passes_required"] is False
    assert "policy_design_case_record_registry" in {
        failure["component"] for failure in payload["component_failures"]
    }
    assert _component_issue_codes(payload, "policy_design_case_record_registry") >= {
        "policy_design_case_record_family_owner_missing"
    }


def test_policy_design_case_record_registry_missing_enforcement_function_fails_readiness(
    monkeypatch,
) -> None:
    _patch_phase32_sources(monkeypatch)
    monkeypatch.setattr(
        gate,
        "_build_policy_design_case_record_registry_report",
        lambda _repo_root: _policy_design_case_registry_report(
            code="policy_design_case_record_family_enforcement_function_missing",
            field="enforcement_function",
        ),
    )

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)

    assert payload["status"] == "fail"
    assert payload["passes_required"] is False
    assert "policy_design_case_record_registry" in {
        failure["component"] for failure in payload["component_failures"]
    }
    assert _component_issue_codes(payload, "policy_design_case_record_registry") >= {
        "policy_design_case_record_family_enforcement_function_missing"
    }


def test_static_inventory_runtime_emitted_support_needs_runtime_bundle_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path, include_runtime_ref=False)

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    assert payload["status"] == "fail"
    assert _minimum_closeout_failure_codes(payload) >= {"hds_runtime_ref_missing"}
    inventory_failure = next(
        failure
        for failure in payload["minimum_closeout_gate_failures"]
        if failure["code"] == "hds_runtime_ref_missing"
    )
    assert inventory_failure["source"] == "static_inventory"
    assert inventory_failure["minimum_closeout_gate"] == "serious_canary_runtime_refs"


def test_readiness_rejects_static_only_producer_map_scorecard_even_if_status_projects_pass(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path)
    scorecard_path = bundle_root / "quality_evidence" / "quality_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    scorecard["quality_status"] = "pass"
    scorecard["status"] = "pass"
    scorecard["approval_state"] = "approval_ready"
    scorecard["quality_gates"].append(
        {
            "name": "policy_design.producer_contract_runtime_evidence",
            "status": "fail",
            "code": "policy_design_producer_static_inventory_not_authority",
            "blocking": True,
            "layer": "policy_design_case",
            "phase": "wave14_producer_scorecard_gates",
            "message": "Static producer maps cannot satisfy producer-owned runtime refs.",
            "evidence_ref": (
                "architecture/baselines/production_quality/evidence_inventory.json"
            ),
            "next_action": "Emit producer-owned runtime refs before readiness projection.",
        }
    )
    scorecard_path.write_text(json.dumps(scorecard), encoding="utf-8")

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    failures = {
        str(failure["code"]): failure
        for failure in payload["minimum_closeout_gate_failures"]
        if isinstance(failure, dict)
    }
    assert payload["status"] == "fail"
    assert "policy_design_producer_static_inventory_not_authority" in failures
    assert failures["policy_design_producer_static_inventory_not_authority"]["source"] == (
        "quality_scorecard"
    )


def test_registry_adr_0155_failures_block_readiness(monkeypatch) -> None:
    registry_report = _registry_report(status="fail")
    registry_report["issues"] = [
        {
            "code": "invariant_override_policy_missing",
            "invariant_id": "HDS-MCG-TEST",
            "field": "override_policy",
            "message": "Invariant must declare override policy.",
        }
    ]
    _patch_phase32_sources(monkeypatch, registry_report=registry_report)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)

    assert payload["status"] == "fail"
    assert payload["component_results"]["invariant_registry"]["status"] == "fail"
    assert payload["component_results"]["invariant_registry"]["issues"][0]["code"] == (
        "invariant_override_policy_missing"
    )


def test_proof_harness_negative_control_failures_block_readiness(monkeypatch) -> None:
    proof_payload = _proof_payload(status="fail")
    proof_payload["violations"] = [
        {
            "code": "hds_invariant_proof_missing",
            "proof_type": "negative_test",
            "invariant_id": "HDS-MCG-TEST",
            "pql_id": "PQL-001",
            "minimum_closeout_gate": "serious_canary_runtime_refs",
            "message": "Invariant negative tests must point at discovered pytest tests.",
            "evidence": {"missing": ["tests/fixtures/fake_test.py::test_fixture"]},
        }
    ]
    _patch_phase32_sources(monkeypatch, proof_payload=proof_payload)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)

    assert payload["status"] == "fail"
    assert payload["component_results"]["hds_proof_harness"]["status"] == "fail"
    assert (
        payload["component_results"]["hds_proof_harness"]["violations"][0]["proof_type"]
        == "negative_test"
    )


def test_readiness_payload_covers_a7_a28_hds_substrate_invariants(monkeypatch) -> None:
    _patch_phase32_sources(monkeypatch)

    payload = gate.build_readiness_payload(repo_root=REPO_ROOT)

    coverage = payload["hds_substrate_coverage"]
    assert {row["backlog_item_id"] for row in coverage} == EXPECTED_HDS_BACKLOG_IDS
    assert all(row["minimum_closeout_gates"] for row in coverage)
    assert all(row["readiness_enforced"] is True for row in coverage)
    assert {
        "continuous_governance_lifecycle",
        "serious_effective_mode_allowed",
        "serious_phase_barriers_closed",
    } <= {gate_name for row in coverage for gate_name in row["minimum_closeout_gates"]}


def test_cli_writes_json_and_require_passing(monkeypatch, tmp_path: Path) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path / "serious")
    output = tmp_path / "readiness.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--serious-evidence-root",
            str(bundle_root),
            "--output",
            str(output),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["passes_all"] is True
    assert payload["passes_required"] is True
    assert payload["summary"]["status_counts"]["fail"] == 0


def test_readiness_require_passing_requires_fresh_serious_bundle_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    output = tmp_path / "readiness.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "fail"
    assert payload["passes_all"] is False
    assert payload["minimum_closeout_gate_failures"]
    assert payload["minimum_closeout_gate_failures"][0]["code"] == (
        "hds_runtime_closeout_bundle_missing"
    )


def test_readiness_require_passing_loads_serious_bundle_from_matrix_run_json(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path / "serious")
    matrix_run = tmp_path / "matrix.json"
    matrix_run.write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_matrix_run.v1",
                "lanes": [
                    {
                        "lane_id": (
                            "profile-research__provider-simulated__data-canonical_production"
                            "__scenario-public_golden__ui-api_only"
                        ),
                        "profile": "research",
                        "status": "passed",
                        "scorecard_status": "pass",
                        "bundle_path": str(bundle_root),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "readiness.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--matrix-run-json",
            str(matrix_run),
            "--output",
            str(output),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["minimum_closeout_gate_failures"] == []
    assert payload["required_serious_profile_ref_failures"] == []
    assert payload["serious_evidence_bundles"][0]["source"] == "matrix_run"


def test_readiness_preserves_failed_live_matrix_lane_as_typed_blocker(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    matrix_run = tmp_path / "matrix.json"
    matrix_run.write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_matrix_run.v1",
                "lanes": [
                    {
                        "lane_id": (
                            "profile-research__provider-live_gonka_proxy"
                            "__data-canonical_production__scenario-public_golden"
                            "__ui-api_only"
                        ),
                        "profile": "research",
                        "status": "failed",
                        "scorecard_status": "fail",
                        "bundle_path": None,
                        "failure_envelope": {
                            "type": "runtime_domain_failure",
                            "code": "source_family_mismatch",
                            "owner": "team-fabric",
                            "root_cause_class": "runtime_domain_failure",
                            "next_action": "Bind Fabric to scenario source contract.",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        matrix_run_json=matrix_run,
    )
    failures = {
        str(failure["code"]): failure
        for failure in payload["minimum_closeout_gate_failures"]
        if isinstance(failure, dict)
    }

    assert payload["status"] == "fail"
    assert "hds_matrix_lane_not_passed" in failures
    assert failures["hds_matrix_lane_not_passed"]["failure_envelope_code"] == (
        "source_family_mismatch"
    )
    assert failures["hds_matrix_lane_not_passed"]["owner"] == "team-fabric"
    assert payload["matrix_run_failures"][0]["root_cause_class"] == "runtime_domain_failure"


def test_readiness_attaches_can_i_closeout_and_blocks_missing_live_revision(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path / "serious")
    bundle_path = bundle_root / "bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["command"] = {
        "matrix_lane_id": (
            "profile-research__provider-live_gonka_proxy__data-canonical_production"
            "__scenario-public_golden__ui-api_only"
        )
    }
    bundle.pop("git_sha", None)
    bundle.pop("code_revision", None)
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )
    failures = _minimum_closeout_failure_codes(payload)

    assert payload["status"] == "fail"
    assert payload["closeout_compatibility"][0]["status"] == "fail"
    assert {"closeout_git_sha_missing", "closeout_code_revision_missing"} <= failures


def test_readiness_rejects_stale_pass_scorecard_when_major_claim_gate_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_phase32_sources(monkeypatch)
    bundle_root = _write_phase32_bundle(tmp_path / "serious")
    case_path = bundle_root / "quality_evidence" / "policy_design_case.json"
    case_payload = json.loads(case_path.read_text(encoding="utf-8"))
    case_payload.update(_phase32_claim_case_without_argument_surfaces())
    case_path.write_text(json.dumps(case_payload), encoding="utf-8")

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    failures = _minimum_closeout_failure_codes(payload)
    assert payload["status"] == "fail"
    assert "policy_design_major_claim_argument_missing" in failures
    assert "policy_design_major_claim_warrant_missing" in failures
    assert "policy_design_major_claim_portfolio_refs_missing" not in failures


def _patch_phase32_sources(
    monkeypatch,
    *,
    inventory_payload: dict[str, Any] | None = None,
    registry_report: dict[str, Any] | None = None,
    proof_payload: dict[str, Any] | None = None,
    coverage_payload: dict[str, Any] | None = None,
) -> None:
    monkeypatch.setattr(
        gate,
        "_build_inventory_payload",
        lambda _repo_root: inventory_payload or _inventory_payload(),
    )
    monkeypatch.setattr(
        gate,
        "_build_invariant_registry_report",
        lambda _repo_root: registry_report or _registry_report(),
    )
    monkeypatch.setattr(
        gate,
        "_build_proof_harness_payload",
        lambda _repo_root: proof_payload or _proof_payload(),
    )
    monkeypatch.setattr(
        gate.build_policy_design_case_coverage,
        "build_coverage_payload",
        lambda *, repo_root: coverage_payload or _coverage_payload(),
    )


def _inventory_payload() -> dict[str, Any]:
    return {
        "schema_version": "policyos.production_quality_evidence_inventory.v1",
        "serious_profile_required_refs": [
            {
                "report_id": "lex.normative_evidence",
                "expected_ref": "runtime_quality_ref#normative_applicability_report_ref",
                "status": "runtime_emitted",
                "owner_runtime_layer": "lex",
                "producer": "lex.normative_applicability",
                "first_missing_producer": None,
                "validators": ["lex.normative_applicability.validate"],
            }
        ],
    }


def _coverage_payload() -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.coverage.v1",
        "metrics": {
            "portfolio_predeclaration_pct": {
                "metric_id": "portfolio_predeclaration_pct",
                "value": 100.0,
                "numerator": 1,
                "denominator": 1,
                "measurement_status": "wave15_portfolio_predeclaration_contract_enforced",
            },
            "benchmarking_proportionality_pct": {
                "metric_id": "benchmarking_proportionality_pct",
                "value": 100.0,
                "numerator": 2,
                "denominator": 2,
                "measurement_status": (
                    "wave31_best_in_class_benchmarking_and_proportionality_gates_enforced"
                ),
            },
        },
    }


def _registry_report(*, status: str = "pass") -> dict[str, Any]:
    return {
        "schema_version": "policyos.production_invariant_registry.validation.v1",
        "status": status,
        "summary": {
            "invariant_count": 1,
            "issue_count": 0 if status == "pass" else 1,
            "known_minimum_closeout_gate_count": 1,
            "referenced_minimum_closeout_gate_count": 1,
        },
        "invariants": [copy.deepcopy(MINIMAL_INVARIANT)],
        "issues": [],
    }


def _policy_design_case_registry_report(*, code: str, field: str) -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.record_registry.validation.v1",
        "status": "fail",
        "summary": {
            "record_family_count": 19,
            "issue_count": 1,
        },
        "record_families": [],
        "issues": [
            {
                "code": code,
                "severity": "error",
                "family_id": "intent_authoring_and_capture_risk.v1",
                "field": field,
                "message": "Injected invalid Policy Design Case registry row.",
            }
        ],
    }


def _proof_payload(*, status: str = "pass") -> dict[str, Any]:
    return {
        "schema_version": "policyos.honest_diagnostics_proof_harness.v1",
        "status": status,
        "summary": {
            "status": status,
            "invariant_count": 1,
            "violation_count": 0 if status == "pass" else 1,
        },
        "invariant_proofs": [
            {
                "invariant_id": "HDS-MCG-TEST",
                "minimum_closeout_gate": "serious_canary_runtime_refs",
                "pql_id": "PQL-001",
                "proof_status": status,
                "negative_tests": MINIMAL_INVARIANT["negative_tests"],
                "admissible_proof_sources": MINIMAL_INVARIANT["negative_tests"],
            }
        ],
        "violations": [],
    }


def _write_phase32_bundle(
    root: Path,
    *,
    canary_kind: str = "production",
    quality_status: str = "pass",
    gate_status: str = "pass",
    include_runtime_ref: bool = True,
    include_authority_contract: bool = True,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    quality_dir = root / "quality_evidence"
    quality_dir.mkdir()
    runtime_ref = _sha("1")
    shared_refs = {
        "same_input_closure_ref": _sha("2"),
        "effective_mode_ledger_ref": _sha("3"),
        "degradation_ledger_ref": _sha("4"),
        "projection_boundaries_ref": _sha("5"),
    }
    runtime_quality_refs = (
        {"normative_applicability_report_ref": runtime_ref} if include_runtime_ref else {}
    )
    policy_design_refs = {
        "policy_intent_envelope_ref": _sha("7"),
        "policy_design_capability_ledger_ref": _sha("8"),
        "policy_design_case_ref": _sha("9"),
    }
    runtime_quality_refs.update(policy_design_refs)
    job_details = {
        "runtime_quality_refs": runtime_quality_refs,
        "diagnostic_event_log_ref": _sha("6"),
        "diagnostic_events": [
            {
                "event_id": "evt-normative",
                "event_name": "polisyos.runtime.evidence.normative_applicability_report.v1",
                "severity": "serious",
                "sampling": {"decision": "always_record", "rate": 1.0},
                "runtime_cas_ref": runtime_ref,
                "artifact_ref": runtime_ref,
            }
        ]
        + [
            {
                "event_id": f"evt-{ref_key}",
                "event_name": f"{ref_key}.persisted",
                "severity": "serious",
                "sampling": {"decision": "always_record", "rate": 1.0},
                "runtime_cas_ref": ref_value,
                "artifact_ref": ref_value,
            }
            for ref_key, ref_value in policy_design_refs.items()
        ],
        **shared_refs,
    }
    report: dict[str, Any] = {
        "schema_version": "policyos.lex.normative_applicability_report.v1",
        "status": "pass",
    }
    if include_authority_contract:
        report.update(
            {
                "diagnostic_event_ref": _sha("6"),
                "cas_artifact_refs": {"normative_applicability_report": runtime_ref},
                "authority_envelope": {
                    "authority_role": "producer_authority",
                    "provenance_kind": "runtime_emitted",
                    "producer_component": "lex.normative_applicability",
                    "runtime_event_ref": _sha("6"),
                    "cas_ref": runtime_ref,
                    "artifact_ref": runtime_ref,
                    "payload_sha256": "a" * 64,
                    "schema_name": "runtime_quality.normative_applicability_report.v1",
                    "run_id": "run-phase32",
                    "tenant_id": "tenant-1",
                },
                "schema_compatibility": {
                    "decision": "compatible",
                    "reader_gate": "normative_evidence_present",
                    "reader_gate_version": "runtime.scorecard.normative_evidence_present.v1",
                    "validation_ref": _sha("a"),
                },
                "same_input_closure_ref": shared_refs["same_input_closure_ref"],
                "effective_mode_ref": shared_refs["effective_mode_ledger_ref"],
                "degradation_ledger_ref": shared_refs["degradation_ledger_ref"],
                "projection_boundaries_ref": shared_refs["projection_boundaries_ref"],
            }
        )
    (quality_dir / "normative_evidence.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )
    intent = build_policy_intent_envelope(
        intent_id="intent-run-phase32",
        run_id="run-phase32",
        job_id="job-phase32",
        tenant_id="tenant-1",
        policy_problem="Wartime MSMEs face liquidity constraints.",
        desired_outcome="Improve MSME survival.",
        proposed_intervention="Target wartime credit support to eligible MSMEs.",
        jurisdiction="UA",
        target_population="wartime MSMEs",
        policy_time="2026-05-15",
        data_time="2024-2026",
        requester_preferred_conclusion="expand credit support",
        requested_authority_level="production",
        authoring_provenance={
            "captured_by": "readiness-test",
            "capture_ref": policy_design_refs["policy_intent_envelope_ref"],
        },
    )
    capability_ledger = build_capability_selection_ledger(
        ledger_ref=policy_design_refs["policy_design_capability_ledger_ref"],
        literature_evidence_required=True,
        duties=[
            build_capability_duty_record(
                capability=capability,
                state="selected",
                evidence_ref=policy_design_refs["policy_design_capability_ledger_ref"],
                runtime_event_ref=policy_design_refs["policy_design_capability_ledger_ref"],
            )
            for capability in POLICY_DESIGN_REQUIRED_CAPABILITIES
        ],
    )
    policy_design_case = build_policy_design_case_profile(
        case_id="pdc-run-phase32",
        run_id="run-phase32",
        job_id="job-phase32",
        tenant_id="tenant-1",
        effective_execution_profile="production",
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": policy_design_refs["policy_design_case_ref"],
            "runtime_event_ref": policy_design_refs["policy_design_case_ref"],
            "same_input_closure_ref": shared_refs["same_input_closure_ref"],
            "effective_mode_ref": shared_refs["effective_mode_ledger_ref"],
            "schema_compatibility_ref": _sha("a"),
        },
        intent_envelope=intent,
        capability_ledger=capability_ledger,
    )
    policy_design_case["policy_design_case_ref"] = policy_design_refs["policy_design_case_ref"]
    (quality_dir / "policy_design_case.json").write_text(
        json.dumps(policy_design_case),
        encoding="utf-8",
    )
    scorecard = {
        "schema_version": "policyos.quality_scorecard.v1",
        "quality_status": quality_status,
        "approval_state": "approval_ready",
        "quality_gates": [
            {
                "name": "normative_evidence_present",
                "status": gate_status,
                "blocking": gate_status == "fail",
                "reader_gate_version": "runtime.scorecard.normative_evidence_present.v1",
            }
        ],
        "evidence_refs": {
            **runtime_quality_refs,
            **shared_refs,
        },
    }
    (quality_dir / "quality_scorecard.json").write_text(
        json.dumps(scorecard),
        encoding="utf-8",
    )
    (root / "job.json").write_text(
        json.dumps(
            {
                "job_id": "job-phase32",
                "run_id": "run-phase32",
                "state": "completed",
                "progress": {"details": job_details},
            }
        ),
        encoding="utf-8",
    )
    (root / "dashboard.json").write_text(
        json.dumps(
            {
                "projection_policy": "projection_only",
                "projection_boundaries_ref": shared_refs["projection_boundaries_ref"],
            }
        ),
        encoding="utf-8",
    )
    cas_dir = root / "cas_manifests"
    cas_dir.mkdir()
    (cas_dir / "quality_artifact_ownership.manifest.json").write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "role": "normative_applicability_report",
                        "artifact_id": runtime_ref,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_evidence.v1",
                "canary_kind": canary_kind,
                "status": "completed",
                "quality_status": quality_status,
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "files": {
                    "quality_evidence": {
                        "normative_evidence": "quality_evidence/normative_evidence.json",
                        "policy_design_case": "quality_evidence/policy_design_case.json",
                        "quality_scorecard": "quality_evidence/quality_scorecard.json",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return root


def _phase32_claim_case_without_argument_surfaces() -> dict[str, Any]:
    return {
        "producer_evidence": [
            {
                "evidence_id": "lex-norm-1",
                "producer": "lex",
                "selected_candidate_refs": ["norm.ua.credit_eligibility"],
                "provenance_kind": "runtime_emitted",
                "cas_ref": _sha("a"),
                "runtime_event_ref": _sha("b"),
            },
            {
                "evidence_id": "fabric-source-1",
                "producer": "fabric",
                "selected_candidate_refs": ["production-msme-panel"],
                "provenance_kind": "runtime_emitted",
                "cas_ref": _sha("c"),
                "runtime_event_ref": _sha("d"),
            },
            {
                "evidence_id": "scholar-lit-1",
                "producer": "scholar",
                "selected_candidate_refs": ["scholar-lit-1"],
                "provenance_kind": "runtime_emitted",
                "cas_ref": _sha("e"),
                "runtime_event_ref": _sha("f"),
            },
            {
                "evidence_id": "foundry-method-1",
                "producer": "foundry",
                "selected_candidate_refs": ["causal.difference_in_differences"],
                "provenance_kind": "runtime_emitted",
                "cas_ref": _sha("0"),
                "runtime_event_ref": _sha("1"),
            },
            {
                "evidence_id": "options-objectives-1",
                "producer": "options_objectives",
                "selected_candidate_refs": ["options-objectives-tradeoffs-rec-1"],
                "provenance_kind": "runtime_emitted",
                "cas_ref": _sha("2"),
                "runtime_event_ref": _sha("3"),
            },
        ],
        "evidence_portfolios": [
            {
                "schema_version": (
                    "policyos.runtime.policy_design_case.evidence_portfolio_design.v1"
                ),
                "portfolio_id": "portfolio-rec-1",
                "claim_ids": ["rec_1"],
                "predeclared": True,
                "declared_before_producer_execution": True,
                "authority_level": "production",
                "strands": [
                    {
                        "strand_id": "data-method-literature",
                        "claim_id": "rec_1",
                        "authority_level": "production",
                        "candidate_data_source_families": ["production_msme_panel"],
                        "candidate_method_families": ["causal_effect_estimation"],
                        "defensible_specification_space": {"primary_estimand": "ATT"},
                        "inclusion_rules": ["Include runtime-owned evidence."],
                        "exclusion_rules": ["Reject static inventory substitutes."],
                        "disconfirming_lines": [
                            {"line_id": "placebo-pre-period", "required": True}
                        ],
                        "synthesis_rules": {"strategy": "triangulate"},
                        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
                        "cost_proportionality": {"budget_tier": "standard"},
                    }
                ],
                "candidate_data_source_families": ["production_msme_panel"],
                "candidate_method_families": ["causal_effect_estimation"],
                "inclusion_rules": ["Include runtime-owned evidence."],
                "exclusion_rules": ["Reject static inventory substitutes."],
                "disconfirming_lines": ["placebo-pre-period"],
                "synthesis_rules": {"strategy": "triangulate"},
                "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "nodes": [
            {
                "node_type": "claim",
                "node_id": "claim-node-rec-1",
                "claim_id": "rec_1",
                "claim_ref": _sha("4"),
                "cas_ref": _sha("4"),
                "runtime_event_ref": _sha("5"),
                "runtime_authority_envelope": {
                    "authority_role": "producer_authority",
                    "provenance_kind": "runtime_emitted",
                },
            }
        ],
        "final_major_claims": [
            {
                "claim_id": "rec_1",
                "assurance_node_id": "claim-node-rec-1",
                "claim_ref": _sha("4"),
                "major": True,
                "concept_refs": ["concept.wartime_msme_credit_support"],
                "legal_norm_refs": ["norm.ua.credit_eligibility"],
                "source_data_refs": ["production-msme-panel"],
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "scholar_refs": ["scholar-lit-1"],
                "portfolio_refs": ["portfolio-rec-1"],
                "independence_refs": ["independence-map-rec-1"],
                "specification_curve_refs": ["multiverse-rec-1"],
                "disconfirming_refs": ["disconfirming-ledger-rec-1"],
                "synthesis_refs": ["synthesis-rec-1"],
                "objective_tradeoff_refs": ["options-objectives-tradeoffs-rec-1"],
                "uncertainty_refs": ["foundry-uncertainty-1"],
                "numerical_semantics_refs": ["ir.numerical_semantics.msme_survival"],
                "monitoring_refs": ["monitoring.plan.rec_1"],
                "selected_producer_refs": {
                    "lex": ["norm.ua.credit_eligibility"],
                    "fabric": ["production-msme-panel"],
                    "data_forge": ["production-msme-panel"],
                    "scholar": ["scholar-lit-1"],
                    "foundry": ["causal.difference_in_differences"],
                    "options_objectives": ["options-objectives-tradeoffs-rec-1"],
                },
            }
        ],
    }


def _minimum_closeout_failure_codes(payload: dict[str, Any]) -> set[str]:
    return {
        str(failure["code"])
        for failure in payload["minimum_closeout_gate_failures"]
        if isinstance(failure, dict)
    }


def _component_issue_codes(payload: dict[str, Any], component_name: str) -> set[str]:
    component = payload["component_results"][component_name]
    return {str(issue["code"]) for issue in component.get("issues", []) if isinstance(issue, dict)}


def _sha(char: str) -> str:
    return "sha256:" + char * 64
