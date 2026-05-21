# ruff: noqa: S101

from __future__ import annotations

from polisyos.runtime.quality.closeout_compatibility import (
    SCHEMA_VERSION,
    build_closeout_compatibility_record,
)


def test_live_bundle_without_git_or_code_revision_fails_closeout() -> None:
    record = build_closeout_compatibility_record(
        bundle_payload={
            "schema_version": "policyos.canary_evidence.v1",
            "canary_kind": "research",
            "command": {
                "matrix_lane_id": (
                    "profile-research__provider-live_gonka_proxy"
                    "__data-canonical_production__scenario-public_golden__ui-api_only"
                )
            },
        },
        scorecard_payload={"quality_gates": []},
        quality_reports={},
    )

    assert record["schema_version"] == SCHEMA_VERSION
    assert record["status"] == "fail"
    assert {issue["code"] for issue in record["issues"]} >= {
        "closeout_git_sha_missing",
        "closeout_code_revision_missing",
    }
    assert record["deployment_context"]["serious_live_or_cloud_bundle"] is True


def test_reader_consumed_schema_without_verification_fails_closeout() -> None:
    record = build_closeout_compatibility_record(
        bundle_payload={
            "schema_version": "policyos.canary_evidence.v1",
            "canary_kind": "research",
            "git_sha": "abc123",
            "code_revision": {"git_sha": "abc123", "source": "git"},
        },
        scorecard_payload={
            "schema_version": "policyos.quality_scorecard.v1",
            "quality_gates": [
                {
                    "name": "normative_evidence_present",
                    "status": "pass",
                    "reader_gate_version": "runtime.scorecard.normative_evidence_present.v2",
                }
            ],
        },
        quality_reports={
            "normative_evidence": {
                "schema_version": "policyos.lex.normative_applicability_report.v1",
                "status": "pass",
            }
        },
    )

    assert record["status"] == "fail"
    assert {issue["code"] for issue in record["issues"]} == {
        "closeout_reader_schema_pair_unverified"
    }
    assert record["producer_reader_matrix"][0]["report_key"] == "normative_evidence"
    assert record["producer_reader_matrix"][0]["reader_gate"] == "normative_evidence_present"
    assert record["producer_reader_matrix"][0]["status"] == "fail"


def test_verified_reader_schema_matrix_passes() -> None:
    record = build_closeout_compatibility_record(
        bundle_payload={
            "schema_version": "policyos.canary_evidence.v1",
            "canary_kind": "research",
            "git_sha": "abc123",
            "code_revision": {"git_sha": "abc123", "source": "git"},
            "command": {"argv": ["policyos-canary", "--real"]},
        },
        scorecard_payload={
            "schema_version": "policyos.quality_scorecard.v1",
            "quality_gates": [
                {
                    "name": "normative_evidence_present",
                    "status": "pass",
                    "reader_gate_version": "runtime.scorecard.normative_evidence_present.v2",
                }
            ],
        },
        quality_reports={
            "normative_evidence": {
                "schema_version": "policyos.lex.normative_applicability_report.v1",
                "status": "pass",
                "schema_compatibility": {
                    "decision": "compatible",
                    "validation_ref": "sha256:" + "a" * 64,
                    "reader_gate": "normative_evidence_present",
                    "reader_gate_version": "runtime.scorecard.normative_evidence_present.v2",
                },
            }
        },
        authority_profile_version="authority-profile-v1",
    )

    assert record["status"] == "pass"
    assert record["issues"] == []
    assert record["authority_profile"]["version"] == "authority-profile-v1"
    assert record["producer_reader_matrix"][0]["validation_ref"].startswith("sha256:")
