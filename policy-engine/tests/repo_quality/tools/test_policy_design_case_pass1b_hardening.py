from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path

from tools.quality.validation import check_policy_design_case_pass1b_hardening as hardening

REPO_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_CLOSEOUT_GROUPS = {
    "tenant_cas_approval_governance": {
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
    },
    "substrate_residual": {
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
    },
    "observability_orchestration_static_audit": {
        "PDD-017",
        "PDD-018",
        "PDD-045",
    },
    "config_release_deployment_migration": {
        "PDD-072",
        "PDD-075",
        "PDD-076",
        "PDD-079",
        "PDD-080",
        "PDD-081",
        "PDD-082",
    },
    "external_dependency": {
        "PDD-073",
        "PDD-085",
        "PDD-102",
    },
    "client_surface": {
        "PDD-089",
        "PDD-091",
        "PDD-092",
        "PDD-093",
        "PDD-094",
    },
}


def test_pass1b_hardening_payload_maps_every_group_to_closeout_evidence() -> None:
    payload = hardening.build_pass1b_hardening_payload(repo_root=REPO_ROOT)

    assert payload["schema_version"] == hardening.SCHEMA_VERSION
    assert payload["status"] == "pass"
    assert payload["wave"] == "32"
    assert payload["phase"] == "32.1"
    assert payload["summary"] == {
        "group_count": 6,
        "pdd_count": 39,
        "implemented_pdd_count": 39,
        "issue_count": 0,
    }
    assert set(payload["groups"]) == set(EXPECTED_CLOSEOUT_GROUPS)

    for group_id, expected_pdds in EXPECTED_CLOSEOUT_GROUPS.items():
        group = payload["groups"][group_id]
        assert set(group["pdds"]) == expected_pdds
        assert group["owner"].startswith("team-")
        assert group["implemented_evidence_contract"]
        assert group["scorecard_gate"].startswith("policy_design")
        assert group["readiness_check"].startswith("policy_design_case.")
        assert group["remaining_blocker"] == "none"
        assert group["authority_boundary"] == "record_is_evidence_only"
        assert set(group["pdd_closeout"]) == expected_pdds

        for pdd_id in expected_pdds:
            closeout = group["pdd_closeout"][pdd_id]
            assert closeout["phase"].startswith("28.")
            assert closeout["owner"].startswith("team-")
            assert closeout["implemented_evidence_contract"]
            assert closeout["scorecard_gate"].startswith("policy_design")
            assert closeout["readiness_check"].startswith("policy_design_case.")
            assert closeout["closeout_gate"].startswith("policy_design")
            assert closeout["remaining_blocker"] == "none"
            assert closeout["coverage_kind"] == "concrete_evidence_contract"
            assert "hardening" not in closeout.get("generic_note", "").casefold()


def test_pass1b_hardening_payload_keeps_tenant_cas_governance_surface_contract() -> None:
    payload = hardening.build_pass1b_hardening_payload(repo_root=REPO_ROOT)

    group = payload["groups"]["tenant_cas_approval_governance"]
    assert group["record_key"] == "pass1b_tenant_cas_approval_governance"
    assert group["record_family"] == "pass1b_tenant_cas_approval_governance.v1"
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
    } <= set(group["required_case_bindings"])


def test_pass1b_hardening_payload_fails_when_phase_28_1_pdd_is_missing() -> None:
    groups = deepcopy(hardening.PASS1B_HARDENING_GROUPS)
    group = dict(groups["tenant_cas_approval_governance"])
    group["pdds"] = tuple(pdd for pdd in group["pdds"] if pdd != "PDD-096")
    groups["tenant_cas_approval_governance"] = group

    payload = hardening.build_pass1b_hardening_payload(
        repo_root=REPO_ROOT,
        groups=groups,
    )

    assert payload["status"] == "fail"
    assert "policy_design_pass1b_pdd_missing" in {
        issue["code"] for issue in payload["issues"]
    }


def test_pass1b_hardening_payload_fails_when_any_required_group_is_missing() -> None:
    for group_id in EXPECTED_CLOSEOUT_GROUPS:
        groups = deepcopy(hardening.PASS1B_HARDENING_GROUPS)
        groups.pop(group_id)

        payload = hardening.build_pass1b_hardening_payload(
            repo_root=REPO_ROOT,
            groups=groups,
        )

        assert payload["status"] == "fail", group_id
        assert _issue_codes(payload) >= {
            "policy_design_pass1b_hardening_group_missing",
            "policy_design_pass1b_pdd_missing",
        }


def test_pass1b_hardening_payload_rejects_generic_hardening_note_only_pdd() -> None:
    groups = deepcopy(hardening.PASS1B_HARDENING_GROUPS)
    group = dict(groups["observability_orchestration_static_audit"])
    closeout = dict(group["pdd_closeout"])
    closeout["PDD-018"] = {
        "phase": "28.3",
        "owner": "team-observability",
        "generic_note": "covered by Pass 1B hardening",
    }
    group["pdd_closeout"] = closeout
    groups["observability_orchestration_static_audit"] = group

    payload = hardening.build_pass1b_hardening_payload(
        repo_root=REPO_ROOT,
        groups=groups,
    )

    assert payload["status"] == "fail"
    assert "policy_design_pass1b_pdd_generic_hardening_note" in _issue_codes(payload)


def test_pass1b_hardening_main_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "pass1b_hardening_coverage.json"

    exit_code = hardening.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["output"]["path"] == str(output)


def _issue_codes(payload: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in payload.get("issues", [])
        if isinstance(issue, dict)
    }
