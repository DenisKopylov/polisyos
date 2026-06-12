from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g4"
G4_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g4_promotion_gate.v1"
G4_RULE_VERSION = "policyos.layer3.g4.shadow_to_governed_promotion.v1"
G4_SURFACE_ID = "layer3_g4_shadow_to_governed_promotion_surface"
G4_READINESS_CHECK_ID = "layer3_g4_shadow_to_governed_promotion_gate"

EXPECTED_PROMOTION_STATES = ("shadow", "governed_promoted", "promotion_blocked")
EXPECTED_FINAL_PROMOTION_STATES = ("governed_promoted", "promotion_blocked")
EXPECTED_SOURCE_PAYLOAD_STATES = ("full_payload", "ref_only", "manifest_only", "unresolved")
EXPECTED_PUBLIC_EXPORT_HOOK_STATES = (
    "implemented",
    "out_of_scope_reference_only",
    "blocked",
)
EXPECTED_MAY_NOT_USE_FOR = {
    "approval_authority",
    "causal_effect_authority_without_g2",
    "claim_authority",
    "claim_authority_without_upstream_grounding",
    "closeout_authority",
    "closeout_verdict",
    "human_override_of_a_incompleteness",
    "legal_authority_without_gl",
    "policy_recommendation",
    "production_authority",
    "production_claim_authority",
    "proof_authority_without_g3",
    "public_recommendation",
    "publication_authority",
    "rollout_authority",
    "runtime_closeout_authority",
    "scorecard_authority",
    "source_data_truth_authority",
    "useful_design_credit_before_g5",
}

EXPECTED_DTOS = {
    "Layer3G4ValidationIssue",
    "Layer3G4ValidationReport",
    "Layer3G4PromotionRequest",
    "Layer3G4DependencyReadinessSnapshot",
    "Layer3G4DependencyArtifactShape",
    "Layer3G4SourceDesignRecordResolution",
    "Layer3G4SourcePayloadStatus",
    "Layer3G4NamingCollisionGuard",
    "Layer3G4PromotionInputSet",
    "Layer3G4GroundedContractRef",
    "Layer3G4GroundedContractSet",
    "Layer3G4ACompletenessRequirement",
    "Layer3G4ACompletenessLedger",
    "Layer3G4HumanDecisionIntegrityGate",
    "Layer3G4S7DecisionPayloadResolution",
    "Layer3G4WeakestBoundaryComposition",
    "Layer3G4PromotionRecord",
    "Layer3G4CloseoutConsumerGate",
    "Layer3G4PdcCompilerConsumerGate",
    "Layer3G4G5PromotionHandoff",
    "Layer3G4GovernanceThroughputDelta",
    "Layer3G4PromotionAuditSurface",
    "Layer3G4PublicExportProjectionRefSurface",
    "Layer3G4ConformanceNegativeResult",
    "Layer3G4PerformanceContractReport",
    "Layer3G4ConformanceReport",
    "Layer3G4RegistryRatchetDelta",
    "Layer3G4ReadinessManifest",
    "Layer3G4Bundle",
}

EXPECTED_BUILDERS_AND_VALIDATORS = {
    "build_layer3_g4_bundle",
    "validate_layer3_g4_bundle",
    "build_g4_dependency_readiness_snapshot",
    "load_g4_dependency_artifacts",
    "resolve_g4_source_design_record",
    "check_g4_naming_collisions",
    "build_g4_promotion_input_set",
    "build_g4_grounded_contract_set",
    "build_g4_a_completeness_ledger",
    "build_g4_human_decision_integrity_gate",
    "build_g4_weakest_boundary_composition",
    "build_g4_promotion_records",
    "build_g4_closeout_consumer_gate",
    "build_g4_pdc_compiler_consumer_gate",
    "build_g4_g5_promotion_handoff",
    "build_g4_governance_throughput_delta",
    "build_g4_promotion_audit_surface",
    "build_g4_public_export_projection_refs",
    "build_g4_registry_ratchet_delta",
    "validate_g4_conformance",
    "validate_g4_performance_contract",
}

TASK7_CONFORMANCE_NEGATIVE_IDS = {
    "shadow_design_record_self_promotes",
    "promotion_without_g1_grounded_source_contract",
    "source_design_record_resolution_unresolved",
    "source_design_record_digest_missing",
    "dependency_artifact_shape_mismatch",
    "effect_claim_without_g2_forecast_support",
    "proof_claim_without_g3_proof_record",
    "legal_claim_without_gl_legal_authority",
    "missing_a_firewall_ref_promoted",
    "gl_reissue_required_promoted",
    "gl_g4_compatibility_gate_overclaimed_as_legal_authority",
    "readiness_summary_only_promoted",
    "search_ledger_only_promoted",
    "s7_manifest_only_promoted",
    "s2_ledger_ref_only_human_decision",
    "w12d_manifest_only_source_payload",
    "source_design_record_ref_only_promoted",
    "data_promotion_lane_reused_for_g4",
    "generated_artifact_promotion_target_reused_for_g4",
    "upstream_builder_rerun_in_request_path",
    "upstream_may_not_use_for_ignored",
    "weakest_boundary_ignored",
    "human_decision_missing_for_high_stakes",
    "high_stakes_human_decision_not_required_bypass",
    "human_decision_scope_mismatch",
    "human_decision_overrides_a_incompleteness",
    "promotion_record_claims_closeout",
    "promotion_record_rewrites_closeout_reader",
    "promotion_record_claims_pdc_compile_authority",
    "promotion_record_rewrites_pdc_compiler",
    "promotion_record_claims_production",
    "promotion_record_claims_publication",
    "promotion_record_claims_approval",
    "promotion_record_claims_scorecard",
    "promotion_record_claims_useful_design_credit",
    "promotion_record_incomplete_may_not_use_for",
    "public_projection_raw_payload_leak",
    "public_export_hook_overclaimed",
    "policy_design_case_projection_authority_leak",
    "manifest_runtime_drift",
    "promotion_state_vocab_drops_shadow",
    "promotion_gate_admission_without_conformance",
}

EXPECTED_FIXTURES = {
    "generated_artifact_promotion_target_collision.json",
    "high_stakes_missing_human_decision.json",
    "human_decision_overrides_missing_grounded_contracts.json",
    "legal_reissue_required_handoff.json",
    "missing_grounded_contract_rows.json",
    "public_export_hook_overclaimed.json",
    "public_projection_raw_payload_leak.json",
    "readiness_summary_only_promotion.json",
    "runtime_http_promotion_lane_collision.json",
    "s7_manifest_s2_ledger_only_human_decision.json",
    "shadow_self_promotion.json",
    "source_design_record_standalone_json_assumption.json",
    "valid_source_only_promotion_input.json",
    "w12d_manifest_only_source_or_s7_payload.json",
}


def _g4() -> Any:
    try:
        return import_module("polisyos.runtime.quality.layer3_promotion_gate")
    except ModuleNotFoundError as exc:
        if exc.name == "polisyos.runtime.quality.layer3_promotion_gate":
            pytest.fail(
                "G4 runtime module is missing; add "
                "polisyos.runtime.quality.layer3_promotion_gate for D3.8.",
                pytrace=False,
            )
        raise


def _fixture(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "policyos.tests.layer3.g4.fixture.v1"
    assert payload["fixture_id"].startswith("layer3-g4-")
    assert payload["payload"]["schema_version"] == G4_SCHEMA_VERSION
    assert payload["payload"]["rule_version"] == G4_RULE_VERSION
    if payload["fixture_id"] == "layer3-g4-valid-source-only-promotion-input":
        assert payload["expected_promotion_state"] == "governed_promoted"
    else:
        assert payload["expected_issue_codes"], f"{name} must pin at least one issue code"
    assert payload["pattern_ids"], f"{name} must declare the failure-pattern lens"
    assert payload["capability_labels"], f"{name} must declare missing capability labels"
    return payload


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return dict(payload)


def _issue_codes(report: Any) -> set[str]:
    return {str(issue["code"]) for issue in _dump(report).get("issues", [])}


def _assert_fixture_fails(name: str) -> Any:
    fixture = _fixture(name)
    report = _g4().validate_layer3_g4_bundle(REPO_ROOT, fixture["payload"])

    assert _dump(report)["status"] == "fail"
    assert set(fixture["expected_issue_codes"]) <= _issue_codes(report)
    return report


def _source_only_request_copy() -> dict[str, Any]:
    return json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )


def test_g4_runtime_bundle_does_not_promote_placeholder_design_record_digest() -> None:
    g4 = _g4()

    payload = _dump(g4.build_layer3_g4_bundle(REPO_ROOT))

    promoted = [
        record
        for record in payload["promotion_records"]
        if record["promotion_state"] == "governed_promoted"
    ]
    assert not any(
        record["source_design_record_digest"]
        == "sha256:1111111111111111111111111111111111111111111111111111111111111111"
        for record in promoted
    )
    assert "layer3_g4_placeholder_design_record_promoted" in payload[
        "readiness_manifest"
    ]["issue_codes"]


def _authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["mandate_bounded_decision_record"],
        "may_not_use_for": ["production_claim_authority", "ai_self_authorization"],
        "source_authority": "human_governance",
        "posture": "governed",
        "rule_version_refs": ["policyos.layer2.s7.test.v1"],
    }


def _s7_human_decision_request_payload(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.layer2_s7_delegation.v1",
        "request_id": "layer2.s7.request.ua-msme.final-choice",
        "request_ref": "pdc://layer2/s7/ua-msme/human-decision-request/final-choice",
        "case_id": request["case_id"],
        "delegation_contract_ref": "pdc://layer2/s7/ua-msme/delegation-contract",
        "decision_rights_matrix_ref": "pdc://layer2/s7/ua-msme/decision-rights-matrix",
        "decision_class_id": "final_choice",
        "required_role": "principal",
        "interaction_mode": "request_driven",
        "disposition": "request_human_decision",
        "need_reasons": ["high_stakes"],
        "requested_at": "2026-06-01T00:00:00Z",
        "decision_due_at": "2026-06-01T00:00:00Z",
        "decidable_until": "2026-06-01T00:00:00Z",
        "decision_options": [
            {
                "schema_version": "policyos.policy_design_case.layer2_s7_delegation.v1",
                "option_id": "approve",
                "action": "approve",
                "label": "Approve bounded promotion",
                "consequence": "The candidate may enter governed promotion state only.",
            },
            {
                "schema_version": "policyos.policy_design_case.layer2_s7_delegation.v1",
                "option_id": "reject",
                "action": "reject",
                "label": "Reject promotion",
                "consequence": "The candidate remains shadow.",
            },
        ],
        "recommendation_ref": "pdc://layer2/s7/ua-msme/recommendation/final-choice",
        "provenance_refs": ["pdc://layer2/s7/ua-msme/delegation-contract"],
        "source_seed_refs": ["scientist://supervisor-eval/ua-msme"],
        "material_limitations": ["G4 does not grant production or closeout authority."],
        "disconfirming_evidence_refs": [
            "pdc://layer2/s7/ua-msme/disconfirming-evidence/final-choice"
        ],
        "value_stakes_impact": "Promotion affects accountable use of a high-stakes policy design.",
        "what_changes_under_each_choice": [
            "approve records bounded promotion",
            "reject keeps the candidate shadow",
        ],
        "five_rights_requirements": {
            "schema_version": "policyos.policy_design_case.layer2_s7_delegation.v1",
            "right_decision": "Decide bounded G4 promotion.",
            "right_person": "principal",
            "right_information": "Limitations, disconfirming evidence, options, and consequences.",
            "right_format_channel": "reviewer_console",
            "right_time": "Before governed promotion is recorded.",
        },
        "available_actions": ["approve", "reject", "revise_scope"],
        "attention_cost_rank": 1,
        "voi_rank": 1,
        "s6_mandate_record_ref": "pdc://layer2/s6/ua-msme/mandate-record",
        "s6_mandate_firewall_disposition": "pass",
        "authority_boundary": _authority_boundary(),
        "rule_version_ref": "policyos.layer2.s7.test.v1",
        "created_at": "2026-06-01T00:00:00Z",
    }


def _s7_human_decision_record_payload(
    request: dict[str, Any],
    *,
    active_choice: bool = True,
    actor_role: str = "principal",
    five_rights_pass: bool = True,
    responsibility_status: str = "pass",
) -> dict[str, Any]:
    request_payload = _s7_human_decision_request_payload(request)
    return {
        "schema_version": "policyos.policy_design_case.layer2_s7_delegation.v1",
        "record_id": "layer2.s7.record.ua-msme.final-choice",
        "record_ref": "pdc://layer2/s7/ua-msme/human-decision-record/final-choice",
        "case_id": request["case_id"],
        "human_decision_request_ref": request_payload["request_ref"],
        "actor_ref": "principal://ua-msme/accountable-owner",
        "actor_role": actor_role,
        "decided_at": "2026-06-01T00:00:00Z",
        "decision_action_exercised": "approve",
        "evidence_summary_ref": "pdc://layer2/s7/ua-msme/evidence-summary/final-choice",
        "disconfirming_evidence_refs": [
            "pdc://layer2/s7/ua-msme/disconfirming-evidence/final-choice"
        ],
        "active_choice": active_choice,
        "accountability_statement": "I accept the bounded G4 promotion and its limitations.",
        "mandate_record_ref": "pdc://layer2/s6/ua-msme/mandate-record",
        "mandate_source_refs": ["pdc://layer2/s6/ua-msme/mandate-record"],
        "five_rights_check": {
            "schema_version": "policyos.policy_design_case.layer2_s7_delegation.v1",
            "right_decision": five_rights_pass,
            "right_person": five_rights_pass,
            "right_information": five_rights_pass,
            "right_format_channel": five_rights_pass,
            "right_time": five_rights_pass,
        },
        "responsibility_integrity": {
            "schema_version": "policyos.policy_design_case.layer2_s7_delegation.v1",
            "status": responsibility_status,
            "pattern_ids": ["P26"],
            "reason": "Human decision record passed P26 checks.",
            "missing_requirements": [],
            "rule_version_ref": "policyos.layer2.s7.test.v1",
        },
        "authority_boundary": _authority_boundary(),
        "provenance_refs": [request_payload["request_ref"]],
        "rule_version_ref": "policyos.layer2.s7.test.v1",
        "created_at": "2026-06-01T00:00:00Z",
    }


def _human_decision_wrapper(
    request: dict[str, Any],
    **record_overrides: Any,
) -> dict[str, Any]:
    return {
        "record_ref": "pdc://layer2/s7/ua-msme/human-decision-record/final-choice",
        "candidate_ref": request["candidate_ref"],
        "promotion_scope": request["promotion_scope"],
        "accepted_limitation_refs": [],
        "available_alternatives": ["reject", "revise_scope"],
        "required_role": "principal",
        "human_decision_request_payload": _s7_human_decision_request_payload(request),
        "human_decision_record": _s7_human_decision_record_payload(
            request,
            **record_overrides,
        ),
    }


def _promotion_record_with_blockers(
    g4: Any,
    promotion_record_id: str,
    blocker_refs: tuple[str, ...],
) -> Any:
    return g4.Layer3G4PromotionRecord(
        promotion_record_id=promotion_record_id,
        promotion_state="promotion_blocked",
        case_id="ua-msme-affordable-loans-2022",
        source_design_record_ref="cas://s2/design-record/ua-msme-credit-support",
        grounded_contract_set_ref="repo://architecture/policy_design_case/layer3_g4_grounded_contract_set.json",
        a_completeness_ledger_ref="repo://architecture/policy_design_case/layer3_g4_a_completeness_ledger.json",
        weakest_boundary_composition_ref="repo://architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json",
        human_decision_integrity_gate_ref="repo://architecture/policy_design_case/layer3_g4_human_decision_integrity_gate.json",
        blocker_refs=blocker_refs,
        closeout_consumer_gate_ref="repo://architecture/policy_design_case/layer3_g4_closeout_consumer_gate.json",
        pdc_compiler_consumer_gate_ref="repo://architecture/policy_design_case/layer3_g4_pdc_compiler_consumer_gate.json",
        g5_handoff_ref="repo://architecture/policy_design_case/layer3_g4_g5_promotion_handoff.json",
        registry_ratchet_delta_ref="repo://architecture/policy_design_case/layer3_g4_registry_ratchet_delta.json",
    )


def test_g4_runtime_module_declares_contracts_builders_and_shared_vocabulary() -> None:
    g4 = _g4()

    assert g4.LAYER3_G4_SCHEMA_VERSION == G4_SCHEMA_VERSION
    assert g4.LAYER3_G4_RULE_VERSION == G4_RULE_VERSION
    assert g4.G4_SURFACE_ID == G4_SURFACE_ID
    assert g4.G4_READINESS_CHECK_ID == G4_READINESS_CHECK_ID
    assert tuple(g4.PROMOTION_STATE_VALUES) == EXPECTED_PROMOTION_STATES
    assert tuple(g4.G4_FINAL_PROMOTION_RECORD_STATES) == EXPECTED_FINAL_PROMOTION_STATES
    assert tuple(g4.G4_SOURCE_PAYLOAD_STATUS_VALUES) == EXPECTED_SOURCE_PAYLOAD_STATES
    assert tuple(g4.G4_PUBLIC_EXPORT_HOOK_STATUS_VALUES) == EXPECTED_PUBLIC_EXPORT_HOOK_STATES
    assert set(g4.G4_MAY_NOT_USE_FOR) >= EXPECTED_MAY_NOT_USE_FOR
    assert {name for name in EXPECTED_DTOS if hasattr(g4, name)} == EXPECTED_DTOS
    assert {
        name for name in EXPECTED_BUILDERS_AND_VALIDATORS if hasattr(g4, name)
    } == EXPECTED_BUILDERS_AND_VALIDATORS


def test_g4_dependency_readiness_snapshot_reads_hard_and_context_artifacts() -> None:
    g4 = _g4()

    snapshot = g4.build_g4_dependency_readiness_snapshot(REPO_ROOT)
    payload = _dump(snapshot)

    assert payload["schema_version"] == G4_SCHEMA_VERSION
    assert payload["rule_version"] == G4_RULE_VERSION
    assert payload["g0_dependency_status"] == "pass"
    assert payload["g1_dependency_status"] == "pass"
    assert payload["g2_context_status"] == "fail"
    assert payload["g3_context_status"] in {"pass", "missing"}
    assert payload["gl_context_status"] in {"pass", "missing"}
    assert payload["generated_artifacts_ref"] == "architecture/generated_artifacts.toml"
    assert payload["inventory_ref"] == "architecture/policy_design_case/inventory.json"
    assert "layer3_g1_grounded_source_contracts.json" in " ".join(
        payload["loaded_artifact_paths"]
    )


def test_missing_g1_readiness_blocks_all_promotion(tmp_path: Path) -> None:
    g4 = _g4()
    repo_root = tmp_path
    (repo_root / "architecture/policy_design_case").mkdir(parents=True)
    (repo_root / "architecture/generated_artifacts.toml").write_text("family = []\n")
    (repo_root / "architecture/policy_design_case/inventory.json").write_text(
        json.dumps({"artifacts": []}),
        encoding="utf-8",
    )
    (repo_root / "architecture/policy_design_case/layer3_g0_readiness_manifest.json").write_text(
        json.dumps({"status": "pass", "schema_version": "g0"}),
        encoding="utf-8",
    )

    snapshot = g4.build_g4_dependency_readiness_snapshot(repo_root)
    report = g4.validate_layer3_g4_bundle(
        repo_root,
        {
            "schema_version": G4_SCHEMA_VERSION,
            "rule_version": G4_RULE_VERSION,
            "dependency_readiness": _dump(snapshot),
            "promotion_requests": [
                _fixture("valid_source_only_promotion_input.json")["payload"][
                    "promotion_requests"
                ][0]
            ],
        },
    )

    assert _dump(snapshot)["g1_dependency_status"] == "missing"
    assert _dump(report)["status"] == "fail"
    assert "layer3_g4_g1_dependency_not_ready" in _issue_codes(report)


def test_optional_context_artifacts_block_only_when_requested() -> None:
    g4 = _g4()
    source_only = _fixture("valid_source_only_promotion_input.json")["payload"]
    effect_request = json.loads(json.dumps(source_only))
    effect_request["promotion_requests"][0]["promotion_scope"]["claim_families"] = [
        "causal_forecast"
    ]
    effect_request["promotion_requests"][0]["promotion_scope"][
        "requires_causal_or_forecast_authority"
    ] = True
    effect_request["promotion_requests"][0]["required_contract_families"] = [
        "g1_source_contract",
        "g2_forecast_support",
    ]

    source_report = g4.validate_layer3_g4_bundle(REPO_ROOT, source_only)
    effect_report = g4.validate_layer3_g4_bundle(REPO_ROOT, effect_request)

    assert "layer3_g4_context_dependency_missing" not in _issue_codes(source_report)
    if _dump(g4.build_g4_dependency_readiness_snapshot(REPO_ROOT))["g2_context_status"] == "missing":
        assert "layer3_g4_context_dependency_missing" in _issue_codes(effect_report)


def test_source_design_record_ref_only_or_missing_digest_blocks_with_typed_issue() -> None:
    g4 = _g4()
    request = _fixture("source_design_record_standalone_json_assumption.json")["payload"][
        "promotion_requests"
    ][0]

    resolution = g4.resolve_g4_source_design_record(REPO_ROOT, request)

    assert _dump(resolution)["payload_status"] == "unresolved"
    assert {
        "layer3_g4_source_design_record_unresolved",
        "layer3_g4_source_design_record_digest_missing",
    } <= set(_dump(resolution)["issue_codes"])


def test_g4_runtime_bundle_does_not_promote_placeholder_design_record_digest() -> None:
    g4 = _g4()
    bundle = g4.build_layer3_g4_bundle(REPO_ROOT)
    payload = _dump(bundle)

    promoted = [
        record
        for record in payload["promotion_records"]
        if record["promotion_state"] == "governed_promoted"
    ]

    assert payload["readiness_manifest"]["status"] == "fail"
    assert not any(
        record.get("source_design_record_digest", "").endswith("1111111111111111")
        for record in promoted
    )
    assert "layer3_g4_placeholder_design_record_promoted" in payload[
        "readiness_manifest"
    ]["issue_codes"]


def test_dependency_artifact_shape_mismatch_fails_closed(tmp_path: Path) -> None:
    g4 = _g4()
    repo_root = tmp_path
    pdc_dir = repo_root / "architecture/policy_design_case"
    pdc_dir.mkdir(parents=True)
    (repo_root / "architecture/generated_artifacts.toml").write_text("family = []\n")
    (pdc_dir / "inventory.json").write_text(json.dumps({"artifacts": []}), encoding="utf-8")
    (pdc_dir / "layer3_g0_readiness_manifest.json").write_text(
        json.dumps({"schema_version": "g0", "status": "pass"}),
        encoding="utf-8",
    )
    (pdc_dir / "layer3_g1_readiness_manifest.json").write_text(
        json.dumps({"schema_version": "g1", "status": "pass"}),
        encoding="utf-8",
    )
    (pdc_dir / "layer3_g1_grounded_source_contracts.json").write_text(
        json.dumps({"bindings": []}),
        encoding="utf-8",
    )

    artifacts = g4.load_g4_dependency_artifacts(repo_root, required_families=("g1",))

    assert artifacts
    assert "layer3_g4_dependency_artifact_shape_mismatch" in {
        code for artifact in artifacts for code in _dump(artifact)["issue_codes"]
    }


def test_g4_naming_collision_guard_records_non_g4_promotion_surfaces() -> None:
    g4 = _g4()

    guard = g4.check_g4_naming_collisions(REPO_ROOT)
    payload = _dump(guard)

    assert payload["runtime_http_promotion_lane_status"] == "collision_detected"
    assert payload["generated_artifact_promotion_target_status"] == "collision_detected"
    assert {
        "runtime_http_promotion_lane",
        "generated_artifact_promotion_target",
    } <= set(payload["collision_ids"])


def test_promotion_input_set_normalizes_required_fields_and_source_resolution() -> None:
    g4 = _g4()
    request = _fixture("valid_source_only_promotion_input.json")["payload"][
        "promotion_requests"
    ][0]

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    payload = _dump(input_set)
    normalized = payload["promotion_inputs"][0]

    assert payload["status"] == "pass"
    assert normalized["source_design_record_ref"] == request["source_design_record"]["ref"]
    assert normalized["source_design_record_replay_ref"] == request["source_design_record"][
        "replay_ref"
    ]
    assert normalized["source_design_record_digest"] == request["source_design_record"][
        "digest"
    ]
    assert normalized["source_design_record_resolution_status"] == "full_payload"
    assert normalized["case_id"] == request["case_id"]
    assert normalized["candidate_ref"] == request["candidate_ref"]
    assert normalized["candidate_source"] == request["candidate_source"]
    assert normalized["incoming_projection_status"] == "shadow"
    assert normalized["claim_refs"] == request["claim_refs"]
    assert normalized["envelope_ref"] == request["envelope_ref"]
    assert normalized["required_contract_families"] == ["g1_source_contract"]
    assert normalized["human_decision_policy"]["human_decision_required"] is False
    assert normalized["stakes_profile"]["high_stakes"] is False
    assert set(normalized["may_not_use_for"]) >= EXPECTED_MAY_NOT_USE_FOR


def test_grounded_contract_set_normalizes_g1_rows_with_lineage_and_coverage_refs() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["grounded_contract_rows"][0].update(
        {
            "binding_id": "g1-binding:firm-survival",
            "lineage_refs": ["repo://production_data/ua-msme/source-contract.json"],
            "coverage_period_ref": "coverage-period://ua-msme/2022-02-open",
            "freshness_ref": "freshness://ukraine_server_support_20260410",
            "adapter_admission_ref": "repo://architecture/policy_design_case/layer3_g1_adapter_admission_registry.json#g1",
            "conformance_ref": "repo://architecture/policy_design_case/layer3_g1_conformance_report.json#g1",
        }
    )

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    payload = _dump(contract_set)
    ref = payload["grounded_contract_refs"][0]

    assert payload["status"] == "pass"
    assert ref["family"] == "g1_source_contract"
    assert ref["source_binding_ref"] == "g1-binding:firm-survival"
    assert ref["lineage_refs"] == ["repo://production_data/ua-msme/source-contract.json"]
    assert ref["coverage_refs"] == ["coverage-period://ua-msme/2022-02-open"]
    assert ref["freshness_refs"] == ["freshness://ukraine_server_support_20260410"]
    assert ref["adapter_admission_refs"]
    assert ref["conformance_refs"]
    assert set(ref["may_not_use_for"]) >= {"claim_authority", "production_authority"}


def test_grounded_contract_set_normalizes_g2_g3_gl_refs_and_preserves_limitations() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["promotion_scope"]["claim_families"] = [
        "source_data",
        "causal_forecast",
        "proof_analytics",
        "legal_mandate",
    ]
    request["promotion_scope"]["requires_causal_or_forecast_authority"] = True
    request["promotion_scope"]["requires_proof_or_analytics_authority"] = True
    request["promotion_scope"]["requires_legal_or_mandate_authority"] = True
    request["required_contract_families"] = [
        "g1_source_contract",
        "g2_forecast_support",
        "g3_proof_record",
        "gl_legal_mandate",
    ]
    request["grounded_contract_rows"].extend(
        [
            {
                "family": "g2_forecast_support",
                "ref": "repo://architecture/policy_design_case/layer3_g2_forecast_support_bindings.json#forecast_support_bindings/0",
                "forecast_support_binding_ref": "g2-forecast-support-binding:test",
                "grounded_forecast_handoff_ref": "g2-grounded-forecast-handoff:test",
                "calibration_refs": ["pdc://layer3/g2/calibration/test"],
                "method_validity_refs": ["method-validity://g2/test"],
                "uncertainty_refs": ["uncertainty://g2/test"],
                "transport_limitation_refs": ["transport-limit://g2/test"],
                "limitation_refs": ["limited_to_observable_subset"],
                "may_not_use_for": ["claim_authority", "production_authority"],
            },
            {
                "family": "g3_proof_record",
                "ref": "repo://architecture/policy_design_case/layer3_g3_proof_carrying_analytics_records.json#proof_carrying_analytics_records/0",
                "proof_ref": "pdc://layer3/g3/proof/test",
                "certificate_resolution_refs": ["certificate-resolution://g3/test"],
                "method_requirement_refs": ["method-requirement://g3/test"],
                "s11_predictive_posture_refs": ["s11-posture://g3/test"],
                "may_not_use_for": ["claim_authority", "production_authority"],
            },
            {
                "family": "gl_legal_mandate",
                "ref": "repo://architecture/policy_design_case/layer3_gl_promotion_gate_handoff.json",
                "legal_authority_refs": ["legal-authority://gl/test"],
                "mandate_refs": ["mandate://gl/test"],
                "threshold_refs": ["threshold://gl/test"],
                "temporal_competence_refs": ["temporal://gl/test"],
                "amendment_lineage_status": "reissue_required",
                "reference_resolution_status": "reissue_required",
                "g4_compatibility_ref": "repo://architecture/policy_design_case/layer3_gl_g4_promotion_gate_consumer_gate.json",
                "limitation_refs": ["reissue_required"],
                "may_not_use_for": ["legal_authority_without_gl", "production_authority"],
            },
        ]
    )

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    payload = _dump(contract_set)
    refs_by_family = {ref["family"]: ref for ref in payload["grounded_contract_refs"]}

    assert payload["status"] == "pass_with_limitations"
    assert refs_by_family["g2_forecast_support"]["calibration_refs"]
    assert refs_by_family["g2_forecast_support"]["transport_limitation_refs"] == [
        "transport-limit://g2/test"
    ]
    assert refs_by_family["g3_proof_record"]["certificate_resolution_refs"] == [
        "certificate-resolution://g3/test"
    ]
    assert refs_by_family["gl_legal_mandate"]["amendment_lineage_status"] == (
        "reissue_required"
    )
    assert refs_by_family["gl_legal_mandate"]["reference_resolution_status"] == (
        "reissue_required"
    )
    assert "reissue_required" in refs_by_family["gl_legal_mandate"]["limitation_refs"]


def test_search_ledgers_and_readiness_summaries_are_rejected_as_grounded_contracts() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["grounded_contract_rows"] = [
        {
            "family": "search_ledger",
            "ref": "repo://architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json#search_ledgers/0",
        },
        {
            "family": "readiness_manifest",
            "ref": "repo://architecture/policy_design_case/layer3_g1_readiness_manifest.json",
        },
    ]

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)

    assert _dump(contract_set)["status"] == "fail"
    assert {
        "layer3_g4_search_ledger_only_promotion",
        "layer3_g4_readiness_summary_only_promotion",
    } <= set(_dump(contract_set)["issue_codes"])


def test_gl_g4_compatibility_row_alone_does_not_satisfy_legal_mandate_contract() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["promotion_scope"]["claim_families"] = ["legal_mandate"]
    request["promotion_scope"]["requires_legal_or_mandate_authority"] = True
    request["required_contract_families"] = ["gl_legal_mandate"]
    request["grounded_contract_rows"] = [
        {
            "family": "gl_g4_compatibility",
            "ref": "repo://architecture/policy_design_case/layer3_gl_g4_promotion_gate_consumer_gate.json",
            "g4_compatibility_status": "pass",
        }
    ]

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)

    assert _dump(contract_set)["status"] == "fail"
    assert {
        "layer3_g4_gl_compatibility_gate_overclaimed",
        "layer3_g4_missing_gl_legal_authority",
    } <= set(_dump(contract_set)["issue_codes"])


def test_a_completeness_blocks_missing_g2_for_effect_claim() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["promotion_scope"]["claim_families"] = ["causal_forecast"]
    request["promotion_scope"]["requires_causal_or_forecast_authority"] = True
    request["required_contract_families"] = [
        "g1_source_contract",
        "g2_forecast_support",
    ]

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)

    assert _dump(ledger)["status"] == "fail"
    assert "layer3_g4_missing_g2_forecast_support" in set(_dump(ledger)["issue_codes"])


def test_a_completeness_blocks_missing_g3_for_proof_claim() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["promotion_scope"]["claim_families"] = ["proof_analytics"]
    request["promotion_scope"]["requires_proof_or_analytics_authority"] = True
    request["required_contract_families"] = [
        "g1_source_contract",
        "g3_proof_record",
    ]

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)

    assert _dump(ledger)["status"] == "fail"
    assert {
        "layer3_g4_missing_g3_proof_record",
        "layer3_g4_missing_g3_certificate_resolution",
    } <= set(_dump(ledger)["issue_codes"])


def test_a_completeness_blocks_gl_reissue_for_legal_dependent_scope() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["promotion_scope"]["claim_families"] = ["legal_mandate"]
    request["promotion_scope"]["requires_legal_or_mandate_authority"] = True
    request["required_contract_families"] = ["g1_source_contract", "gl_legal_mandate"]
    request["grounded_contract_rows"].append(
        {
            "family": "gl_legal_mandate",
            "ref": "repo://architecture/policy_design_case/layer3_gl_promotion_gate_handoff.json",
            "legal_authority_refs": ["legal-authority://gl/test"],
            "mandate_refs": ["mandate://gl/test"],
            "temporal_competence_refs": ["temporal://gl/test"],
            "amendment_lineage_status": "reissue_required",
            "reference_resolution_status": "reissue_required",
            "may_not_use_for": ["legal_authority_without_gl", "production_authority"],
        }
    )

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)

    assert _dump(ledger)["status"] == "fail"
    assert {
        "layer3_g4_gl_reissue_required_blocks_promotion",
        "layer3_g4_gl_reference_resolution_blocks_promotion",
    } <= set(_dump(ledger)["issue_codes"])


def test_limited_upstream_boundary_blocks_unlimited_promotion_scope() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["promotion_scope"]["claim_families"] = ["causal_forecast"]
    request["promotion_scope"]["requires_causal_or_forecast_authority"] = True
    request["promotion_scope"]["requested_boundary"] = "unlimited"
    request["required_contract_families"] = [
        "g1_source_contract",
        "g2_forecast_support",
    ]
    request["grounded_contract_rows"].append(
        {
            "family": "g2_forecast_support",
            "ref": "repo://architecture/policy_design_case/layer3_g2_forecast_support_bindings.json#forecast_support_bindings/0",
            "forecast_support_binding_ref": "g2-forecast-support-binding:test",
            "grounded_forecast_handoff_ref": "g2-grounded-forecast-handoff:test",
            "calibration_refs": ["pdc://layer3/g2/calibration/test"],
            "method_validity_refs": ["method-validity://g2/test"],
            "limitation_refs": ["limited_to_observable_subset"],
            "transport_limitation_refs": ["transport-limit://g2/test"],
            "adapter_admission_ref": "repo://architecture/policy_design_case/layer3_g2_adapter_admission_registry.json#g2",
            "conformance_ref": "repo://architecture/policy_design_case/layer3_g2_conformance_report.json#g2",
            "may_not_use_for": ["claim_authority", "production_authority"],
        }
    )

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)
    weakest = g4.build_g4_weakest_boundary_composition(input_set, contract_set, ledger)

    assert _dump(ledger)["status"] == "fail"
    assert "layer3_g4_limited_boundary_overpromoted" in set(_dump(ledger)["issue_codes"])
    assert _dump(weakest)["promotion_state"] == "promotion_blocked"
    assert "layer3_g4_limited_boundary_overpromoted" in _dump(weakest)[
        "weakest_boundary_reason"
    ]


def test_adapter_admission_and_conformance_must_be_pass_not_only_ref_present() -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["grounded_contract_rows"][0].update(
        {
            "adapter_admission_ref": "repo://architecture/policy_design_case/layer3_g1_adapter_admission_registry.json#g1",
            "conformance_ref": "repo://architecture/policy_design_case/layer3_g1_conformance_report.json#g1",
            "adapter_admission_status": "fail",
            "adapter_conformance_status": "fail",
        }
    )

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)

    assert {
        "layer3_g4_adapter_admission_failed",
        "layer3_g4_adapter_conformance_failed",
    } <= set(_dump(ledger)["issue_codes"])


def test_search_health_and_stale_index_status_block_promotion() -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["grounded_contract_rows"][0].update(
        {
            "adapter_admission_ref": "repo://architecture/policy_design_case/layer3_g1_adapter_admission_registry.json#g1",
            "conformance_ref": "repo://architecture/policy_design_case/layer3_g1_conformance_report.json#g1",
            "search_recall_status": "fail",
            "index_freshness_status": "stale",
        }
    )

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)

    assert {
        "layer3_g4_search_recall_dependency_unhealthy",
        "layer3_g4_stale_upstream_index_blocks_promotion",
    } <= set(_dump(ledger)["issue_codes"])


@pytest.mark.parametrize(
    ("scope_flag", "row_ref_field", "expected_issue"),
    [
        (
            "requires_s6_mandate_ref",
            "s6_mandate_refs",
            "layer3_g4_missing_s6_mandate_posture",
        ),
        (
            "requires_s8_value_choice_ref",
            "s8_value_choice_refs",
            "layer3_g4_missing_s8_value_choice_posture",
        ),
        (
            "requires_s10_prerequisite_ref",
            "s10_prerequisite_refs",
            "layer3_g4_missing_s10_prerequisite_posture",
        ),
        (
            "requires_s11_predictive_posture_ref",
            "s11_predictive_posture_refs",
            "layer3_g4_missing_s11_predictive_posture",
        ),
        (
            "requires_s12_resource_economics_ref",
            "s12_resource_economics_refs",
            "layer3_g4_missing_s12_resource_economics_posture",
        ),
        (
            "requires_s13_accountability_learning_ref",
            "s13_accountability_learning_refs",
            "layer3_g4_missing_s13_accountability_learning_posture",
        ),
    ],
)
def test_declared_authority_posture_refs_are_required(
    scope_flag: str,
    row_ref_field: str,
    expected_issue: str,
) -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["promotion_scope"][scope_flag] = True

    missing_input = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    missing_contracts = g4.build_g4_grounded_contract_set(REPO_ROOT, missing_input)
    missing_ledger = g4.build_g4_a_completeness_ledger(
        REPO_ROOT,
        missing_input,
        missing_contracts,
    )

    request["grounded_contract_rows"][0][row_ref_field] = [
        f"pdc://layer2/{row_ref_field}/ua-msme"
    ]
    satisfied_input = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    satisfied_contracts = g4.build_g4_grounded_contract_set(REPO_ROOT, satisfied_input)
    satisfied_ledger = g4.build_g4_a_completeness_ledger(
        REPO_ROOT,
        satisfied_input,
        satisfied_contracts,
    )

    assert expected_issue in set(_dump(missing_ledger)["issue_codes"])
    assert expected_issue not in set(_dump(satisfied_ledger)["issue_codes"])


def test_weakest_boundary_composition_is_deterministic_and_preserves_blockers() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["promotion_scope"]["claim_families"] = ["causal_forecast", "proof_analytics"]
    request["promotion_scope"]["requires_causal_or_forecast_authority"] = True
    request["promotion_scope"]["requires_proof_or_analytics_authority"] = True
    request["required_contract_families"] = [
        "g1_source_contract",
        "g2_forecast_support",
        "g3_proof_record",
    ]

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)
    first = g4.build_g4_weakest_boundary_composition(input_set, contract_set, ledger)
    second = g4.build_g4_weakest_boundary_composition(input_set, contract_set, ledger)

    assert _dump(first) == _dump(second)
    assert _dump(first)["promotion_state"] == "promotion_blocked"
    assert _dump(first)["blocker_refs"] == sorted(_dump(first)["blocker_refs"])
    assert {
        "layer3_g4_missing_g2_forecast_support",
        "layer3_g4_missing_g3_proof_record",
    } <= set(_dump(first)["blocker_refs"])


def test_weakest_boundary_promotes_only_declared_scope_when_a_complete() -> None:
    g4 = _g4()
    request = json.loads(
        json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"][
            "promotion_requests"
        ][0])
    )
    request["grounded_contract_rows"][0].update(
        {
            "adapter_admission_ref": "repo://architecture/policy_design_case/layer3_g1_adapter_admission_registry.json#g1",
            "conformance_ref": "repo://architecture/policy_design_case/layer3_g1_conformance_report.json#g1",
        }
    )

    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)
    weakest = g4.build_g4_weakest_boundary_composition(input_set, contract_set, ledger)

    assert _dump(ledger)["status"] == "pass"
    assert _dump(weakest)["status"] == "pass"
    assert _dump(weakest)["promotion_state"] == "governed_promoted"
    assert _dump(weakest)["blocker_refs"] == []
    assert _dump(weakest)["promotion_scope"]["claim_families"] == ["source_data"]


def test_high_stakes_human_decision_not_required_bypass_blocks() -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["promotion_scope"].update(
        {
            "high_stakes": True,
            "value_laden": True,
            "accountability_sensitive": True,
        }
    )
    request["human_decision_policy"] = {
        "human_decision_required": False,
        "rationale": "Attempted no-interrupt route for a high-stakes promotion.",
    }

    gate = g4.build_g4_human_decision_integrity_gate(request)

    assert _dump(gate)["status"] == "fail"
    assert {
        "layer3_g4_human_decision_required",
        "layer3_g4_high_stakes_human_decision_not_required_bypass",
    } <= set(_dump(gate)["issue_codes"])


def test_valid_high_stakes_human_decision_payload_passes_when_a_complete() -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["promotion_scope"].update(
        {
            "high_stakes": True,
            "accountability_sensitive": True,
            "claim_families": ["source_data"],
        }
    )
    request["human_decision_policy"] = {
        "human_decision_required": True,
        "human_decision_record_payloads": [_human_decision_wrapper(request)],
    }
    ledger = g4.Layer3G4ACompletenessLedger(status="pass")

    gate = g4.build_g4_human_decision_integrity_gate(
        request,
        a_completeness_ledger=ledger,
    )

    assert _dump(gate)["status"] == "pass"
    assert _dump(gate)["human_decision_required"] is True
    assert _dump(gate)["human_decision_record_refs"] == [
        "pdc://layer2/s7/ua-msme/human-decision-record/final-choice"
    ]
    assert _dump(gate)["issue_codes"] == []


def test_human_decision_candidate_or_scope_mismatch_blocks() -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["promotion_scope"].update({"high_stakes": True})
    wrapper = _human_decision_wrapper(request)
    wrapper["candidate_ref"] = "s2-design-candidate:wrong-candidate"
    request["human_decision_policy"] = {
        "human_decision_required": True,
        "human_decision_record_payloads": [wrapper],
    }

    gate = g4.build_g4_human_decision_integrity_gate(request)

    assert _dump(gate)["status"] == "fail"
    assert "layer3_g4_human_decision_scope_mismatch" in set(
        _dump(gate)["issue_codes"]
    )


@pytest.mark.parametrize(
    ("wrapper_overrides", "expected_issue"),
    [
        ({"active_choice": False}, "layer3_g4_human_decision_inactive_choice"),
        ({"five_rights_pass": False}, "layer3_g4_human_decision_five_rights_failed"),
        ({"actor_role": "technical_reviewer"}, "layer3_g4_human_decision_five_rights_failed"),
        (
            {"responsibility_status": "limit"},
            "layer3_g4_p26_responsibility_integrity_failed",
        ),
    ],
)
def test_human_decision_integrity_payload_failures_block(
    wrapper_overrides: dict[str, Any],
    expected_issue: str,
) -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["promotion_scope"].update({"high_stakes": True})
    request["human_decision_policy"] = {
        "human_decision_required": True,
        "human_decision_record_payloads": [
            _human_decision_wrapper(request, **wrapper_overrides)
        ],
    }

    gate = g4.build_g4_human_decision_integrity_gate(request)

    assert _dump(gate)["status"] == "fail"
    assert expected_issue in set(_dump(gate)["issue_codes"])


def test_human_decision_cannot_override_failed_a_completeness_ledger() -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["promotion_scope"].update({"high_stakes": True})
    request["human_decision_policy"] = {
        "human_decision_required": True,
        "human_decision_record_payloads": [_human_decision_wrapper(request)],
    }
    ledger = g4.Layer3G4ACompletenessLedger(
        status="fail",
        blocker_refs=("layer3_g4_missing_g1_grounded_source_contract",),
        issue_codes=("layer3_g4_a_completeness_failed",),
    )

    gate = g4.build_g4_human_decision_integrity_gate(
        request,
        a_completeness_ledger=ledger,
    )

    assert _dump(gate)["status"] == "fail"
    assert "layer3_g4_human_decision_overrides_a_incompleteness" in set(
        _dump(gate)["issue_codes"]
    )


def test_non_high_stakes_bounded_scope_can_skip_human_decision_with_rationale() -> None:
    g4 = _g4()
    request = _source_only_request_copy()
    request["promotion_scope"].update(
        {
            "high_stakes": False,
            "requested_boundary": "bounded",
            "routine_in_envelope": True,
        }
    )
    request["human_decision_policy"] = {
        "human_decision_required": False,
        "rationale": "Routine, non-high-stakes source-only promotion within a bounded envelope.",
    }

    gate = g4.build_g4_human_decision_integrity_gate(request)

    assert _dump(gate)["status"] == "not_required"
    assert _dump(gate)["human_decision_required"] is False
    assert _dump(gate)["issue_codes"] == []


def test_promotion_records_emit_promoted_and_blocked_records_with_required_refs() -> None:
    g4 = _g4()
    promoted_request = _source_only_request_copy()
    promoted_request["grounded_contract_rows"][0].update(
        {
            "adapter_admission_ref": "repo://architecture/policy_design_case/layer3_g1_adapter_admission_registry.json#g1",
            "conformance_ref": "repo://architecture/policy_design_case/layer3_g1_conformance_report.json#g1",
        }
    )
    promoted_inputs = g4.build_g4_promotion_input_set(REPO_ROOT, [promoted_request])
    promoted_contracts = g4.build_g4_grounded_contract_set(REPO_ROOT, promoted_inputs)
    promoted_ledger = g4.build_g4_a_completeness_ledger(
        REPO_ROOT,
        promoted_inputs,
        promoted_contracts,
    )
    promoted_weakest = g4.build_g4_weakest_boundary_composition(
        promoted_inputs,
        promoted_contracts,
        promoted_ledger,
    )
    promoted_human_gate = g4.build_g4_human_decision_integrity_gate(promoted_request)

    blocked_request = _source_only_request_copy()
    blocked_request["request_id"] = "g4-request:blocked-effect"
    blocked_request["candidate_ref"] = "s2-design-candidate:blocked-effect"
    blocked_request["promotion_scope"]["claim_families"] = ["causal_forecast"]
    blocked_request["promotion_scope"]["requires_causal_or_forecast_authority"] = True
    blocked_request["required_contract_families"] = [
        "g1_source_contract",
        "g2_forecast_support",
    ]
    blocked_inputs = g4.build_g4_promotion_input_set(REPO_ROOT, [blocked_request])
    blocked_contracts = g4.build_g4_grounded_contract_set(REPO_ROOT, blocked_inputs)
    blocked_ledger = g4.build_g4_a_completeness_ledger(
        REPO_ROOT,
        blocked_inputs,
        blocked_contracts,
    )
    blocked_weakest = g4.build_g4_weakest_boundary_composition(
        blocked_inputs,
        blocked_contracts,
        blocked_ledger,
    )
    blocked_human_gate = g4.build_g4_human_decision_integrity_gate(blocked_request)

    records = g4.build_g4_promotion_records(
        promoted_inputs,
        promoted_contracts,
        promoted_ledger,
        promoted_weakest,
        promoted_human_gate,
    ) + g4.build_g4_promotion_records(
        blocked_inputs,
        blocked_contracts,
        blocked_ledger,
        blocked_weakest,
        blocked_human_gate,
    )
    payloads = [_dump(record) for record in records]
    promoted_record = next(
        record for record in payloads if record["promotion_state"] == "governed_promoted"
    )
    blocked_record = next(
        record for record in payloads if record["promotion_state"] == "promotion_blocked"
    )

    assert promoted_record["source_design_record_ref"] == promoted_request[
        "source_design_record"
    ]["ref"]
    assert promoted_record["grounded_contract_set_ref"].endswith(
        "layer3_g4_grounded_contract_set.json"
    )
    assert promoted_record["a_completeness_ledger_ref"].endswith(
        "layer3_g4_a_completeness_ledger.json"
    )
    assert promoted_record["weakest_boundary_composition_ref"].endswith(
        "layer3_g4_weakest_boundary_composition.json"
    )
    assert promoted_record["human_decision_integrity_gate_ref"].endswith(
        "layer3_g4_human_decision_integrity_gate.json"
    )
    assert promoted_record["closeout_consumer_gate_ref"].endswith(
        "layer3_g4_closeout_consumer_gate.json"
    )
    assert promoted_record["pdc_compiler_consumer_gate_ref"].endswith(
        "layer3_g4_pdc_compiler_consumer_gate.json"
    )
    assert promoted_record["g5_handoff_ref"].endswith("layer3_g4_g5_promotion_handoff.json")
    assert promoted_record["registry_ratchet_delta_ref"].endswith(
        "layer3_g4_registry_ratchet_delta.json"
    )
    assert promoted_record["upstream_contract_refs"]
    assert set(promoted_record["may_not_use_for"]) >= EXPECTED_MAY_NOT_USE_FOR
    assert "production_authority" not in set(promoted_record["authoritative_for"])
    assert "layer3_g4_missing_g2_forecast_support" in blocked_record["blocker_refs"]


def test_consumer_gates_and_g5_handoff_are_reference_only_and_preserve_boundaries() -> None:
    g4 = _g4()
    promoted_request = _source_only_request_copy()
    promoted_request["grounded_contract_rows"][0].update(
        {
            "adapter_admission_ref": "repo://architecture/policy_design_case/layer3_g1_adapter_admission_registry.json#g1",
            "conformance_ref": "repo://architecture/policy_design_case/layer3_g1_conformance_report.json#g1",
        }
    )
    input_set = g4.build_g4_promotion_input_set(REPO_ROOT, [promoted_request])
    contract_set = g4.build_g4_grounded_contract_set(REPO_ROOT, input_set)
    ledger = g4.build_g4_a_completeness_ledger(REPO_ROOT, input_set, contract_set)
    weakest = g4.build_g4_weakest_boundary_composition(input_set, contract_set, ledger)
    human_gate = g4.build_g4_human_decision_integrity_gate(promoted_request)
    records = g4.build_g4_promotion_records(
        input_set,
        contract_set,
        ledger,
        weakest,
        human_gate,
    )

    closeout_gate = g4.build_g4_closeout_consumer_gate(records)
    pdc_gate = g4.build_g4_pdc_compiler_consumer_gate(records)
    handoff = g4.build_g4_g5_promotion_handoff(records)
    throughput = g4.build_g4_governance_throughput_delta(records)

    closeout_payload = _dump(closeout_gate)
    pdc_payload = _dump(pdc_gate)
    handoff_payload = _dump(handoff)

    assert closeout_payload["status"] == "pass"
    assert closeout_payload["promotion_states"] == {"governed_promoted": 1}
    assert set(closeout_payload["may_not_use_for"]) >= EXPECTED_MAY_NOT_USE_FOR
    assert not {"can_closeout", "approval_ready", "publishable", "useful_design_rate"} & set(
        closeout_payload
    )
    assert pdc_payload["status"] == "pass"
    assert pdc_payload["promotion_state_input_refs"] == closeout_payload[
        "promotion_record_refs"
    ]
    assert pdc_payload["compiler_graph_rewrite_attempted"] is False
    assert handoff_payload["status"] == "pass"
    assert handoff_payload["promotion_scopes"][0] == promoted_request["promotion_scope"]
    assert handoff_payload["upstream_contract_refs"]
    assert set(handoff_payload["may_not_use_for"]) >= EXPECTED_MAY_NOT_USE_FOR
    assert _dump(throughput)["admitted_count"] == 1
    assert _dump(throughput)["blocked_count"] == 0


def test_governance_throughput_delta_classifies_block_and_stall_reasons() -> None:
    g4 = _g4()
    records = (
        _promotion_record_with_blockers(
            g4,
            "g4-promotion-record:hard-a",
            ("layer3_g4_missing_g2_forecast_support",),
        ),
        _promotion_record_with_blockers(
            g4,
            "g4-promotion-record:search-stall",
            ("layer3_g4_search_recall_dependency_unhealthy",),
        ),
        _promotion_record_with_blockers(
            g4,
            "g4-promotion-record:legal-reissue",
            ("layer3_g4_gl_reissue_required_blocks_promotion",),
        ),
        _promotion_record_with_blockers(
            g4,
            "g4-promotion-record:human-stall",
            ("layer3_g4_human_decision_required",),
        ),
    )

    throughput = _dump(g4.build_g4_governance_throughput_delta(records))

    assert throughput["blocked_count"] == 4
    assert throughput["stalled_count"] == 3
    assert throughput["block_reason_counts"]["hard_a_incompleteness"] == 1
    assert throughput["stall_reason_counts"]["search_health_stall"] == 1
    assert throughput["stall_reason_counts"]["legal_reissue_stall"] == 1
    assert throughput["stall_reason_counts"]["human_decision_stall"] == 1


def test_adapter_contract_registry_records_semantic_bridge_details() -> None:
    g4 = _g4()
    bundle = g4.build_layer3_g4_bundle(REPO_ROOT)
    registry = _dump(bundle)["adapter_contract_registry"]
    records = {record["bridge_id"]: record for record in registry["bridge_records"]}

    assert registry["status"] == "pass"
    assert set(records) >= set(g4.G4_ADAPTER_PATH_IDS)
    for bridge_id in g4.G4_ADAPTER_PATH_IDS:
        record = records[bridge_id]
        assert record["producer_artifact_family"]
        assert record["producer_artifact_ref"].startswith("repo://")
        assert record["consumer"]
        assert record["authority_purpose"] == "layer3_g4_governed_promotion_state"
        assert set(record["authoritative_for"]) >= set(g4.G4_AUTHORITATIVE_FOR)
        assert set(record["may_not_use_for"]) >= set(g4.G4_MAY_NOT_USE_FOR)
        assert record["semantic_loss_status"] == "no_loss_for_promotion_state_refs"
        assert record["verification_refs"]
        assert record["conformance_negative_refs"]


def test_g4_authority_leaks_from_records_and_consumer_gates_are_rejected() -> None:
    g4 = _g4()
    bundle = _fixture("valid_source_only_promotion_input.json")["payload"]
    bundle = json.loads(json.dumps(bundle))
    bundle["promotion_records"] = [
        {
            "promotion_record_id": "g4-promotion-record:leaky",
            "promotion_state": "governed_promoted",
            "case_id": "ua-msme-affordable-loans-2022",
            "promotion_scope": {"claim_families": ["source_data"]},
            "authoritative_for": [
                "production_authority",
                "publication_authority",
                "approval_authority",
                "scorecard_authority",
                "closeout_verdict",
                "pdc_compile_authority",
                "useful_design_credit",
            ],
            "may_not_use_for": [],
        }
    ]
    bundle["closeout_consumer_gate"] = {
        "promotion_record_refs": ["g4-promotion-record:leaky"],
        "can_closeout": True,
        "closeout_reader_rewrite_attempted": True,
    }
    bundle["pdc_compiler_consumer_gate"] = {
        "promotion_record_refs": ["g4-promotion-record:leaky"],
        "compiler_graph_rewrite_attempted": True,
        "claims_pdc_compile_authority": True,
    }

    report = g4.validate_layer3_g4_bundle(REPO_ROOT, bundle)

    assert {
        "layer3_g4_production_authority_leak",
        "layer3_g4_publication_authority_leak",
        "layer3_g4_approval_authority_leak",
        "layer3_g4_scorecard_authority_leak",
        "layer3_g4_closeout_authority_leak",
        "layer3_g4_pdc_compile_authority_leak",
        "layer3_g4_pdc_compiler_graph_rewrite_attempt",
        "layer3_g4_closeout_reader_rewrite_attempt",
        "layer3_g4_useful_design_credit_leak",
        "layer3_g4_may_not_use_for_incomplete",
    } <= _issue_codes(report)


def test_g4_red_baseline_fixtures_are_valid_json_and_named_by_plan() -> None:
    discovered = {path.name for path in FIXTURE_DIR.glob("*.json")}
    assert discovered >= EXPECTED_FIXTURES | {"dependency_audit_expected.json"}
    for name in sorted(EXPECTED_FIXTURES):
        _fixture(name)


def test_source_design_record_resolution_rejects_standalone_s2_json_assumption() -> None:
    report = _assert_fixture_fails("source_design_record_standalone_json_assumption.json")

    assert {
        "layer3_g4_source_design_record_unresolved",
        "layer3_g4_source_design_record_digest_missing",
    } <= _issue_codes(report)


def test_promotion_without_actual_grounded_contract_rows_fails_closed() -> None:
    report = _assert_fixture_fails("missing_grounded_contract_rows.json")

    assert {
        "layer3_g4_grounded_contract_ref_missing",
        "layer3_g4_missing_g1_grounded_source_contract",
    } <= _issue_codes(report)


def test_shadow_design_record_or_b_candidate_cannot_self_promote() -> None:
    _assert_fixture_fails("shadow_self_promotion.json")


def test_g1_g2_g3_gl_readiness_summaries_alone_cannot_promote() -> None:
    report = _assert_fixture_fails("readiness_summary_only_promotion.json")

    assert "layer3_g4_readiness_summary_only_promotion" in _issue_codes(report)


def test_gl_reissue_required_handoff_blocks_legal_dependent_promotion() -> None:
    report = _assert_fixture_fails("legal_reissue_required_handoff.json")

    assert {
        "layer3_g4_gl_reissue_required_blocks_promotion",
        "layer3_g4_gl_reference_resolution_blocks_promotion",
    } <= _issue_codes(report)


def test_high_stakes_promotion_without_s7_human_decision_record_blocks() -> None:
    report = _assert_fixture_fails("high_stakes_missing_human_decision.json")

    assert {
        "layer3_g4_human_decision_required",
        "layer3_g4_human_decision_record_missing",
    } <= _issue_codes(report)


def test_s7_manifest_s2_ledger_and_w12d_manifest_refs_do_not_satisfy_human_gate() -> None:
    s7_report = _assert_fixture_fails("s7_manifest_s2_ledger_only_human_decision.json")
    w12d_report = _assert_fixture_fails("w12d_manifest_only_source_or_s7_payload.json")

    assert {
        "layer3_g4_s7_manifest_only_human_decision",
        "layer3_g4_s2_ledger_ref_only_human_decision",
    } <= _issue_codes(s7_report)
    assert "layer3_g4_w12d_manifest_only_not_payload" in _issue_codes(w12d_report)


def test_human_decision_cannot_override_missing_grounded_contracts() -> None:
    report = _assert_fixture_fails("human_decision_overrides_missing_grounded_contracts.json")

    assert {
        "layer3_g4_human_decision_overrides_a_incompleteness",
        "layer3_g4_missing_g1_grounded_source_contract",
    } <= _issue_codes(report)


def test_promotion_naming_collisions_are_rejected_as_g4_inputs() -> None:
    lane_report = _assert_fixture_fails("runtime_http_promotion_lane_collision.json")
    target_report = _assert_fixture_fails("generated_artifact_promotion_target_collision.json")

    assert "layer3_g4_data_promotion_lane_confused" in _issue_codes(lane_report)
    assert "layer3_g4_generated_artifact_promotion_target_confused" in _issue_codes(
        target_report
    )


def test_public_projection_cannot_leak_raw_payloads_or_overclaim_export_hook() -> None:
    leak_report = _assert_fixture_fails("public_projection_raw_payload_leak.json")
    hook_report = _assert_fixture_fails("public_export_hook_overclaimed.json")

    assert {
        "layer3_g4_public_raw_payload_leak",
        "layer3_g4_policy_projection_authority_leak",
    } <= _issue_codes(leak_report)
    assert "layer3_g4_public_export_hook_overclaimed" in _issue_codes(hook_report)


def test_task7_conformance_report_executes_all_negatives() -> None:
    g4 = _g4()

    report = g4.validate_g4_conformance(REPO_ROOT)
    payload = _dump(report)
    results = {item["negative_id"]: item for item in payload["negative_results"]}

    assert payload["status"] == "pass"
    assert set(payload["negative_ids"]) >= TASK7_CONFORMANCE_NEGATIVE_IDS
    assert set(results) >= TASK7_CONFORMANCE_NEGATIVE_IDS
    for negative_id in sorted(TASK7_CONFORMANCE_NEGATIVE_IDS):
        result = results[negative_id]
        assert result["status"] == "pass", negative_id
        assert set(result["expected_issue_codes"]) <= set(
            result["observed_issue_codes"]
        ), negative_id
        assert result["fixture_ref"].startswith("g4-conformance-negative:")
        assert result["pattern_ids"], negative_id
        assert result["capability_labels"], negative_id
    assert payload["performance_contract"]["status"] == "pass"


def test_task7_performance_contract_blocks_unbounded_request_path_patterns() -> None:
    g4 = _g4()

    report = g4.validate_g4_performance_contract(REPO_ROOT)
    payload = _dump(report)

    assert payload["status"] == "pass"
    assert payload["bounded_artifact_resolution_status"] == "pass"
    assert payload["json_artifact_load_scope_status"] == "pass"
    assert payload["recursive_repo_scan_status"] == "pass"
    assert payload["upstream_builder_rerun_status"] == "pass"
    assert payload["domain_corpus_duckdb_scan_status"] == "pass"
    assert payload["mutable_global_cache_status"] == "pass"
    assert payload["bounded_artifact_path_count"] >= 1


def test_task7_validator_rejects_closeout_and_conformance_bypasses() -> None:
    g4 = _g4()
    bundle = json.loads(json.dumps(_fixture("valid_source_only_promotion_input.json")["payload"]))
    bundle["promotion_state_values"] = ["governed_promoted", "promotion_blocked"]
    bundle["registry_ratchet_delta"] = {
        "status": "pass",
        "admission_maturity": "implemented",
        "conformance_refs": [],
    }
    bundle["promotion_requests"][0]["upstream_builder_rerun_attempted"] = True
    bundle["weakest_boundary_composition"] = {
        "status": "fail",
        "promotion_state": "promotion_blocked",
        "blocker_refs": ["layer3_g4_missing_g2_forecast_support"],
    }
    bundle["promotion_records"] = [
        {
            "promotion_record_id": "g4-promotion-record:weakest-bypass",
            "promotion_state": "governed_promoted",
            "case_id": "ua-msme-affordable-loans-2022",
            "promotion_scope": {"claim_families": ["causal_forecast"]},
            "authoritative_for": ["governed_promotion_state_for_declared_scope"],
            "may_not_use_for": list(g4.G4_MAY_NOT_USE_FOR),
            "blocker_refs": [],
        }
    ]

    report = g4.validate_layer3_g4_bundle(REPO_ROOT, bundle)

    assert {
        "layer3_g4_shared_promotion_state_vocabulary_dropped_shadow",
        "layer3_g4_promotion_gate_admission_without_conformance",
        "layer3_g4_upstream_builder_rerun_in_request_path",
        "layer3_g4_weakest_boundary_ignored",
    } <= _issue_codes(report)
