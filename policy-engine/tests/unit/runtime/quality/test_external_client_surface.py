from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

import pytest

from polisyos.runtime.quality.external_client_surface import (
    EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
    validate_external_client_surface_record,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_quality_evidence,
    scorecard_for,
    sha,
)


def test_external_client_surface_record_passes_for_phase_28_5_pdds() -> None:
    record = _valid_external_client_surface_record()

    validation = validate_external_client_surface_record(record)

    assert validation["status"] == "pass"
    assert validation["summary"]["pdd_count"] == 8
    assert validation["issues"] == []


@pytest.mark.parametrize(
    ("field", "expected_code"),
    [
        ("connector_acquisition", "policy_design_connector_acquisition_governance_missing"),
        ("plugin_capability_isolation", "policy_design_plugin_capability_isolation_missing"),
        ("external_dependency_contracts", "policy_design_external_dependency_rights_missing"),
        ("external_evidence_provenance", "policy_design_external_evidence_provenance_missing"),
        ("offline_mutation_authority", "policy_design_offline_mutation_authority_missing"),
        ("collaboration_attribution", "policy_design_collaboration_attribution_missing"),
        ("assistant_composer_provenance", "policy_design_authoring_provenance_missing"),
        (
            "bureaucratic_rendering_export",
            "policy_design_bureaucratic_rendering_export_missing",
        ),
        ("client_persistence_privacy", "policy_design_client_persistence_privacy_missing"),
    ],
)
def test_external_client_surface_requires_every_phase_28_5_surface(
    field: str,
    expected_code: str,
) -> None:
    record = _valid_external_client_surface_record()
    record.pop(field)

    validation = validate_external_client_surface_record(record)

    assert validation["status"] == "fail"
    assert expected_code in _issue_codes(validation)


def test_external_client_surface_requires_case_bound_runtime_envelope() -> None:
    record = _valid_external_client_surface_record()
    for field in ("record_id", "run_id", "evidence_ref", "runtime_event_ref"):
        record.pop(field)

    validation = validate_external_client_surface_record(record)

    assert validation["status"] == "fail"
    assert "policy_design_external_client_surface_identity_missing" in _issue_codes(
        validation
    )
    assert "policy_design_external_client_surface_runtime_ref_missing" in _issue_codes(
        validation
    )


def test_external_dependency_contract_blocks_revoked_provider_rights() -> None:
    record = _valid_external_client_surface_record()
    dependency = record["external_dependency_contracts"][0]
    dependency["risk_status"] = "revoked"

    validation = validate_external_client_surface_record(record)

    assert validation["status"] == "fail"
    assert "policy_design_external_dependency_provider_risk_blocked" in _issue_codes(
        validation
    )


def test_offline_optimistic_mutation_cannot_mint_approval_authority() -> None:
    record = _valid_external_client_surface_record()
    mutation = record["offline_mutation_authority"][0]
    mutation["authority_state"] = "optimistic"
    mutation["presented_as_authoritative"] = True
    mutation.pop("server_acceptance_ref")

    validation = validate_external_client_surface_record(record)

    assert validation["status"] == "fail"
    assert "policy_design_offline_mutation_authority_missing" in _issue_codes(validation)


def test_scorecard_blocks_missing_external_client_surface_record() -> None:
    evidence = complete_quality_evidence()
    case = deepcopy(evidence["policy_design_case"])
    case["final_major_claims"] = [{"claim_id": "rec_1", "major": True}]
    case.pop("external_plugin_dependency_client_surface", None)
    evidence["policy_design_case"] = case

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "policy_design_external_client_surface_record_missing" in blocking_codes(scorecard)


def _valid_external_client_surface_record() -> dict[str, object]:
    return {
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


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in validation.get("issues", [])
        if isinstance(issue, dict)
    }
