from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

from polisyos.runtime.quality import policy_design_case as pdc
from polisyos.runtime.quality.assurance_case import (
    build_capability_duty_record,
    build_policy_design_case_profile,
    build_policy_intent_envelope,
)
from polisyos.runtime.quality.policy_design_case import (
    POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS,
    POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES,
    build_policy_design_case_record_registry_report,
    compile_policy_design_case_runtime_record_families,
    policy_design_case_record_family_coverage_scorecard_gates,
    policy_design_case_record_registry_payload,
    validate_policy_design_case_record_family_coverage,
    validate_policy_design_case_record_registry_payload,
)
from tests.unit.runtime.quality.test_policy_design_case_false_passes import (
    _policy_design_case,
    sha,
)

EXPECTED_SDD_FAMILIES = {
    "intent_authoring_and_capture_risk.v1",
    "capability_mode_and_fallback_selection.v1",
    "concept_and_jurisdiction_spine.v1",
    "legal_authority_and_competence.v1",
    "data_source_semantic_lineage.v1",
    "scholar_academic_evidence.v1",
    "numeric_time_and_geography_semantics.v1",
    "method_selection_and_validity.v1",
    "evidence_portfolio_and_synthesis.v1",
    "structured_judgement_and_consultation.v1",
    "options_objectives_and_tradeoffs.v1",
    "claim_argument_evidence_case.v1",
    "implementation_monitoring_and_evaluation.v1",
    "human_oversight_independence_and_review.v1",
    "integrity_self_fmea_and_maturity.v1",
    "lifecycle_ex_post_and_calibration.v1",
    "publication_trust_and_external_governance.v1",
    "best_in_class_benchmarking.v1",
    "formal_substrate_invariant_spec.v1",
}


def test_minimum_record_registry_covers_every_sdd_family_with_typed_evidence() -> None:
    payload = policy_design_case_record_registry_payload()
    rows = payload["record_families"]

    assert payload["schema_version"] == "policyos.policy_design_case.record_registry.v1"
    assert {row["family_id"] for row in rows} == EXPECTED_SDD_FAMILIES
    assert set(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES) == EXPECTED_SDD_FAMILIES

    for row in rows:
        assert row["applicability"] in {
            "required",
            "profile_scoped",
            "not_applicable",
        }
        assert row["applicability_evidence"]["kind"]
        assert row["applicability_evidence"]["source"]
        assert row["producer_owner"].startswith("team-")
        assert row["reader_owner"].startswith("team-")
        assert row["schema_name"].startswith("policyos.policy_design_case.")
        assert row["scorecard_gate"].startswith("policy_design_case.")
        assert row["readiness_check"].startswith("policy_design_case.")
        assert row["enforcement_function"].startswith("polisyos.")
        assert row["next_diagnostic_command"].startswith("uv run ")


def test_minimum_record_registry_report_passes_for_default_rows() -> None:
    report = build_policy_design_case_record_registry_report()

    assert report["status"] == "pass"
    assert report["summary"]["record_family_count"] == len(EXPECTED_SDD_FAMILIES)
    assert report["summary"]["issue_count"] == 0


def test_policy_design_case_status_pass_cannot_replace_runtime_record_families() -> None:
    result = validate_policy_design_case_record_family_coverage({"status": "pass"})

    assert result.status == "fail"
    assert {
        "policy_design_case_records_missing",
        "policy_design_case_record_families_missing",
    } <= _issue_codes(result.as_dict())

    gates = policy_design_case_record_family_coverage_scorecard_gates(
        {"status": "pass"},
        phase="policy_design_phase28_record_family_coverage",
    )

    assert {
        "policy_design_case_records_missing",
        "policy_design_case_record_families_missing",
    } <= {gate["code"] for gate in gates}
    assert {
        gate["phase"]
        for gate in gates
        if gate["code"]
        in {
            "policy_design_case_records_missing",
            "policy_design_case_record_families_missing",
        }
    } == {"policy_design_phase28_record_family_coverage"}


def test_live_profile_pass_is_compiled_to_runtime_record_families_before_closeout() -> None:
    profile_payload = build_policy_design_case_profile(
        case_id="pdc-live-path",
        run_id="run-live-path",
        job_id="job-live-path",
        tenant_id="tenant-prod",
        effective_execution_profile="production",
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": sha("1"),
            "runtime_event_ref": "event://policy-design-case/profile/live-path",
            "same_input_closure_ref": sha("6"),
            "effective_mode_ref": sha("7"),
            "schema_compatibility_ref": sha("8"),
        },
        intent_envelope=build_policy_intent_envelope(
            intent_id="intent-live-path",
            run_id="run-live-path",
            job_id="job-live-path",
            tenant_id="tenant-prod",
            policy_problem="Wartime MSME credit constraints.",
            desired_outcome="Improve MSME survival.",
            proposed_intervention="Targeted wartime credit support.",
            jurisdiction="UA",
            target_population="wartime MSMEs",
            policy_time="2026-05-21",
            data_time="2024-2026",
            requester_preferred_conclusion="expand targeted support",
            requested_authority_level="production",
            affected_stakeholders=["MSMEs", "banks", "fiscal authority"],
            objectives=["survival", "fiscal proportionality"],
            evidence_expectations=["legal authority", "production data"],
            authoring_provenance={"captured_by": "runtime-control", "capture_ref": sha("2")},
        ),
        capability_ledger={
            "schema_version": "policyos.runtime.policy_design_case.capability_ledger.v1",
            "ledger_ref": sha("3"),
            "duties": [
                build_capability_duty_record(
                    capability=capability,
                    state="selected",
                    evidence_ref=sha(ref_char),
                    runtime_event_ref=f"event://policy-design-case/capability/{capability}",
                )
                for capability, ref_char in (
                    ("lex", "4"),
                    ("fabric", "5"),
                    ("scholar", "6"),
                    ("foundry", "7"),
                    ("scientist", "8"),
                    ("compiler", "9"),
                    ("review", "a"),
                    ("publication", "b"),
                    ("audit", "c"),
                )
            ],
        },
    )
    profile_payload["status"] = "pass"

    pre_compile = validate_policy_design_case_record_family_coverage(profile_payload)
    assert pre_compile.status == "fail"
    assert {
        "policy_design_case_records_missing",
        "policy_design_case_record_families_missing",
    } <= _issue_codes(pre_compile.as_dict())

    compiled = compile_policy_design_case_runtime_record_families(profile_payload)
    coverage = validate_policy_design_case_record_family_coverage(compiled)

    assert compiled["status"] == "blocked"
    assert coverage.status == "pass"
    assert {row["family_id"] for row in compiled["record_families"]} == EXPECTED_SDD_FAMILIES
    assert compiled["records"]
    for row in compiled["record_families"]:
        assert row["schema_owner"].startswith("team-")
        assert row["producer_owner"].startswith("team-")
        assert row["reader_owner"].startswith("team-")
        assert row["readiness_gate"].startswith("policy_design_case.")
        assert row["runtime_refs"]
        assert row["authority_envelope"]["provenance_kind"] in {
            "runtime_derived",
            "runtime_blocker",
        }
        if row["status"] in {"blocked", "out_of_scope"}:
            assert row["typed_authority_policy"]["status"] == row["status"]


def test_policy_design_case_runtime_record_family_coverage_passes_for_complete_records() -> None:
    case = _policy_design_case()

    result = validate_policy_design_case_record_family_coverage(case)

    assert result.status == "pass"
    payload = result.as_dict()
    assert payload["summary"]["record_family_count"] == len(EXPECTED_SDD_FAMILIES)
    assert payload["summary"]["runtime_record_count"] >= len(EXPECTED_SDD_FAMILIES)
    assert {row["family_id"] for row in payload["record_families"]} == EXPECTED_SDD_FAMILIES
    for row in payload["record_families"]:
        assert row["schema_owner"].startswith("team-")
        assert row["producer_owner"].startswith("team-")
        assert row["reader_owner"].startswith("team-")
        assert row["readiness_gate"].startswith("policy_design_case.")
        assert row["runtime_record_count"] >= 1
        assert row["authority_status"] == "runtime_authority_present"

    observed_governance_surfaces = {
        surface
        for row in payload["record_families"]
        for surface in row.get("governance_surfaces", [])
    }
    assert set(POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS) <= (
        observed_governance_surfaces
    )


def test_governance_family_may_be_out_of_scope_only_with_typed_authority_policy() -> None:
    case = _policy_design_case()
    family = next(
        row
        for row in case["record_families"]
        if row["family_id"] == "structured_judgement_and_consultation.v1"
    )
    family["status"] = "out_of_scope"
    family["typed_authority_policy"] = {
        "policy_code": "authority_policy.structured_judgement.out_of_scope",
        "status": "out_of_scope",
        "reason": "Research-only local diagnostic case does not publish consultation authority.",
        "evidence_ref": sha("1"),
        "runtime_event_ref": "event://policy-design-case/authority-policy/structured-judgement",
    }
    case["records"] = [
        record
        for record in case["records"]
        if record["family_id"] != "structured_judgement_and_consultation.v1"
    ]

    result = validate_policy_design_case_record_family_coverage(case)

    assert result.status == "pass"

    family.pop("typed_authority_policy")
    result = validate_policy_design_case_record_family_coverage(case)

    assert result.status == "fail"
    assert "policy_design_case_record_family_typed_authority_policy_missing" in _issue_codes(
        result.as_dict()
    )


def test_options_objectives_tradeoffs_registry_covers_phase_12_5_facets() -> None:
    payload = policy_design_case_record_registry_payload()
    row = next(
        row
        for row in payload["record_families"]
        if row["family_id"] == "options_objectives_and_tradeoffs.v1"
    )

    assert {
        "baseline_no_action_option",
        "candidate_options",
        "rejected_options",
        "objective_function",
        "tradeoff_weights",
        "social_weights",
        "welfare_bounds",
        "distributional_effects",
        "qualitative_effects",
        "risk",
        "uncertainty",
        "foundry_welfare_uncertainty_refs",
        "ir_distributional_fairness_mobility_welfare_refs",
    } <= set(row["sdd_facets"])


def test_publication_trust_registry_covers_phase_28_5_external_client_facets() -> None:
    payload = policy_design_case_record_registry_payload()
    row = next(
        row
        for row in payload["record_families"]
        if row["family_id"] == "publication_trust_and_external_governance.v1"
    )

    assert {
        "connector_acquisition",
        "plugin_capability_isolation",
        "dependency_rights",
        "provider_source_risk",
        "external_evidence_provenance",
        "offline_mutation_authority",
        "collaboration_attribution",
        "assistant_composer_provenance",
        "bureaucratic_rendering_export",
        "client_persistence_privacy",
    } <= set(row["sdd_facets"])


def test_best_in_class_registry_covers_wave30_run_cost_facets() -> None:
    payload = policy_design_case_record_registry_payload()
    row = next(
        row
        for row in payload["record_families"]
        if row["family_id"] == "best_in_class_benchmarking.v1"
    )

    assert {
        "run_cost_proportionality_ledger",
        "runtime_performance_budget",
        "foundry_cost_model",
        "scientist_budget",
        "doe_search_budget",
        "provider_cost",
        "elapsed_time_budget",
        "human_review_burden",
        "evidence_depth_budget",
    } <= set(row["sdd_facets"])


def test_substrate_residual_bindings_cover_phase_28_2_pdd_records() -> None:
    payload = policy_design_case_record_registry_payload()
    bindings = payload["substrate_residual_bindings"]
    by_pdd = {binding["diagnostic_id"]: binding for binding in bindings}

    required_diagnostics = pdc.POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS
    assert set(required_diagnostics) == {
        "PDD-019",
        "PDD-031",
        "PDD-032",
        "PDD-039",
        "PDD-040",
        "PDD-041",
        "PDD-067",
        "PDD-071",
        "PDD-084",
        "PDD-086",
    }
    assert set(by_pdd) == set(required_diagnostics)

    expected_facets = {
        "PDD-019": {"mode_ledger", "fallback_degradation_ledger"},
        "PDD-031": {"deterministic_replay_manifest", "typed_replay_drift"},
        "PDD-032": {"resilience_matrix", "observed_vs_modeled_resilience"},
        "PDD-039": {"trusted_authority_fields", "authority_spoofing_controls"},
        "PDD-040": {"partial_state_consistency", "retry_reconciliation"},
        "PDD-041": {"shared_cas_evidence_graph", "tenant_scoped_cas_ownership"},
        "PDD-067": {"public_export_semantic_preservation"},
        "PDD-071": {"effective_configuration_ledger", "environment_provenance"},
        "PDD-084": {"tool_transcript_authority", "compaction_audit"},
        "PDD-086": {"simulation_boundary_ledger", "evidence_mode_ledger"},
    }
    for diagnostic_id, facets in expected_facets.items():
        binding = by_pdd[diagnostic_id]
        assert facets <= set(binding["record_facets"]), diagnostic_id
        assert binding["record_family_id"] in EXPECTED_SDD_FAMILIES
        assert binding["runtime_records"], diagnostic_id
        assert binding["test_paths"], diagnostic_id
        assert binding["scorecard_gate"].startswith("policy_design_case.")
        assert binding["readiness_check"].startswith("policy_design_case.")
        assert binding["next_diagnostic_command"].startswith("uv run ")


def test_substrate_residual_bindings_validate_against_record_registry_facets() -> None:
    payload = policy_design_case_record_registry_payload()

    result = pdc.validate_policy_design_case_substrate_residual_bindings(payload)

    assert result.status == "pass"
    assert result.as_dict()["summary"]["issue_count"] == 0


def test_substrate_residual_bindings_reject_missing_phase_28_2_diagnostic() -> None:
    payload = policy_design_case_record_registry_payload()
    payload["substrate_residual_bindings"] = [
        binding
        for binding in payload["substrate_residual_bindings"]
        if binding["diagnostic_id"] != "PDD-084"
    ]

    result = pdc.validate_policy_design_case_substrate_residual_bindings(payload)

    assert result.status == "fail"
    assert "policy_design_case_substrate_residual_binding_missing" in _issue_codes(result.as_dict())


def test_substrate_residual_binding_gates_include_phase_28_2_registry_failures() -> None:
    payload = policy_design_case_record_registry_payload()
    payload["substrate_residual_bindings"] = [
        binding
        for binding in payload["substrate_residual_bindings"]
        if binding["diagnostic_id"] != "PDD-084"
    ]

    gates = pdc.policy_design_case_record_registry_scorecard_gates(
        registry_payload=payload
    )

    assert "policy_design_case_substrate_residual_binding_missing" in {
        gate["code"] for gate in gates
    }


def test_minimum_record_registry_rejects_wrong_schema_version() -> None:
    payload = policy_design_case_record_registry_payload()
    payload["schema_version"] = "policyos.policy_design_case.record_registry.v0"

    result = validate_policy_design_case_record_registry_payload(payload)

    assert result.status == "fail"
    assert "policy_design_case_record_registry_schema_version_invalid" in _issue_codes(
        result.as_dict()
    )


def test_minimum_record_registry_rejects_missing_owner() -> None:
    payload = policy_design_case_record_registry_payload()
    row = deepcopy(payload["record_families"][0])
    row["producer_owner"] = ""
    payload["record_families"] = [row]

    result = validate_policy_design_case_record_registry_payload(payload)

    assert result.status == "fail"
    assert "policy_design_case_record_family_owner_missing" in _issue_codes(result.as_dict())


def test_minimum_record_registry_rejects_missing_enforcement_function() -> None:
    payload = policy_design_case_record_registry_payload()
    row = deepcopy(payload["record_families"][0])
    row.pop("enforcement_function")
    payload["record_families"] = [row]

    result = validate_policy_design_case_record_registry_payload(payload)

    assert result.status == "fail"
    assert "policy_design_case_record_family_enforcement_function_missing" in _issue_codes(
        result.as_dict()
    )


def _issue_codes(report: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in report.get("issues", []) if isinstance(issue, dict)}
