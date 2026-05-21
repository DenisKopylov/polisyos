from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from typing import Any

from tests.unit.runtime.quality.test_policy_design_case_false_passes import (
    _policy_design_case,
    _scorecard_blocking_codes_for_case,
    sha,
)

EXPECTED_PHASE_28_1_PDDS = {
    "PDD-022",
    "PDD-023",
    "PDD-024",
    "PDD-025",
    "PDD-028",
    "PDD-029",
    "PDD-030",
    "PDD-033",
    "PDD-058",
    "PDD-095",
    "PDD-096",
}


def test_pass1b_hardening_record_binds_phase_28_1_pdds_to_case_records() -> None:
    from polisyos.runtime.quality.pass1b_hardening import (
        PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS,
        build_pass1b_tenant_cas_approval_governance_record,
        validate_pass1b_tenant_cas_approval_governance_record,
    )

    record = build_pass1b_tenant_cas_approval_governance_record(
        record_id="pass1b-hardening-rec-1",
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-prod",
        cell_id="cell-a",
        case_bindings=_complete_case_bindings(),
        pdd_bindings=_complete_pdd_bindings(),
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/pass1b-hardening/1",
    )

    validated = validate_pass1b_tenant_cas_approval_governance_record(record)

    assert set(PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS) == EXPECTED_PHASE_28_1_PDDS
    assert validated["status"] == "pass"
    assert {row["pdd_id"] for row in validated["pdd_bindings"]} == EXPECTED_PHASE_28_1_PDDS
    assert {
        "tenant_identity",
        "cas_ownership",
        "artifact_tenant_mapping",
        "cas_manifest_governance",
        "approval_authority",
        "override_signature",
        "decision_lifecycle",
        "privacy_security_authority",
        "human_review_authority",
        "privileged_action_authority",
        "signing_public_trust",
        "recall_retraction",
        "public_trust",
    } <= set(validated["case_bindings"])


def test_scorecard_blocks_missing_pass1b_hardening_record_for_production_case() -> None:
    case = _policy_design_case()
    case.pop("pass1b_tenant_cas_approval_governance", None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_pass1b_hardening_record_missing" in codes


def test_pass1b_gates_reject_status_pass_without_concrete_record_families() -> None:
    from polisyos.runtime.quality.pass1b_hardening import (
        policy_design_pass1b_hardening_scorecard_gates,
    )

    gates = policy_design_pass1b_hardening_scorecard_gates(
        {
            "status": "pass",
            "pass1b_tenant_cas_approval_governance": _complete_pass1b_record(),
        }
    )

    codes = {gate["code"] for gate in gates}
    assert {
        "policy_design_case_records_missing",
        "policy_design_case_record_families_missing",
    } <= codes
    assert {
        gate["phase"]
        for gate in gates
        if gate["code"]
        in {
            "policy_design_case_records_missing",
            "policy_design_case_record_families_missing",
        }
    } == {"policy_design_pass1b_hardening"}


def test_runtime_record_family_compiler_binds_pass1b_hardening_record() -> None:
    from polisyos.runtime.quality.policy_design_case import (
        compile_policy_design_case_runtime_record_families,
        validate_policy_design_case_record_family_coverage,
    )

    case = _policy_design_case()
    case.pop("records", None)
    case.pop("record_families", None)
    case["status"] = "pass"
    case["pass1b_tenant_cas_approval_governance"] = _complete_pass1b_record()

    compiled = compile_policy_design_case_runtime_record_families(case)
    result = validate_policy_design_case_record_family_coverage(compiled)

    assert result.status == "pass"
    assert compiled["status"] in {"pass", "blocked"}
    assert any(
        "pass1b_tenant_cas_approval_governance" in record.get("source_keys", [])
        for record in compiled["records"]
    )


def test_scorecard_blocks_missing_case_bound_surface_for_each_phase_28_1_pdd() -> None:
    case = _policy_design_case()
    record = _complete_pass1b_record()
    record["case_bindings"].pop("privileged_action_authority")
    case["pass1b_tenant_cas_approval_governance"] = record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_pass1b_privileged_action_authority_missing" in codes
    assert "policy_design_pass1b_pdd_binding_incomplete" in codes


def test_scorecard_blocks_failed_pass1b_record_and_blocked_pdd_binding() -> None:
    case = _policy_design_case()
    record = _complete_pass1b_record()
    record["status"] = "fail"
    record["pdd_bindings"][0]["status"] = "blocked"
    case["pass1b_tenant_cas_approval_governance"] = record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_pass1b_hardening_status_not_pass" in codes
    assert "policy_design_pass1b_pdd_binding_not_pass" in codes


def test_scorecard_blocks_digest_only_override_and_frontend_only_public_signature() -> None:
    case = _policy_design_case()
    record = _complete_pass1b_record()
    record["case_bindings"]["override_signature"]["signature_class"] = "digest_only"
    record["case_bindings"]["signing_public_trust"]["trust_status"] = "frontend_only"
    case["pass1b_tenant_cas_approval_governance"] = record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_pass1b_override_signature_not_external_or_attested" in codes
    assert "policy_design_pass1b_public_trust_signature_invalid" in codes


def test_scorecard_blocks_recall_retraction_without_public_contestability() -> None:
    case = _policy_design_case()
    record = _complete_pass1b_record()
    record["case_bindings"]["recall_retraction"]["contestability_hook_ref"] = ""
    record["case_bindings"]["public_trust"]["public_contestability_ref"] = ""
    case["pass1b_tenant_cas_approval_governance"] = record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_pass1b_recall_retraction_authority_missing" in codes
    assert "policy_design_pass1b_public_trust_contestability_missing" in codes


def _complete_pass1b_record() -> dict[str, Any]:
    from polisyos.runtime.quality.pass1b_hardening import (
        build_pass1b_tenant_cas_approval_governance_record,
    )

    return build_pass1b_tenant_cas_approval_governance_record(
        record_id="pass1b-hardening-rec-1",
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-prod",
        cell_id="cell-a",
        case_bindings=deepcopy(_complete_case_bindings()),
        pdd_bindings=deepcopy(_complete_pdd_bindings()),
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/pass1b-hardening/1",
    )


def _complete_case_bindings() -> dict[str, dict[str, Any]]:
    return {
        "tenant_identity": {
            "record_ref": sha("a"),
            "tenant_id": "tenant-prod",
            "cell_id": "cell-a",
            "status": "pass",
            "runtime_event_ref": "event://tenant/identity/1",
        },
        "cas_ownership": {
            "record_ref": sha("b"),
            "owner_index_ref": sha("c"),
            "tenant_id": "tenant-prod",
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


def _complete_pdd_bindings() -> list[dict[str, Any]]:
    return [
        _pdd("PDD-022", "tenant_identity"),
        _pdd("PDD-023", "cas_ownership"),
        _pdd("PDD-024", "artifact_tenant_mapping"),
        _pdd("PDD-025", "cas_manifest_governance"),
        _pdd("PDD-028", "approval_authority"),
        _pdd("PDD-029", "override_signature"),
        _pdd("PDD-030", ["decision_lifecycle", "recall_retraction"]),
        _pdd("PDD-033", "privacy_security_authority"),
        _pdd("PDD-058", ["human_review_authority", "override_signature"]),
        _pdd("PDD-095", "privileged_action_authority"),
        _pdd("PDD-096", ["signing_public_trust", "public_trust"]),
    ]


def _pdd(pdd_id: str, surfaces: str | list[str]) -> dict[str, Any]:
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
