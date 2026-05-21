# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_can_i_closeout


def _write_bundle(
    root: Path,
    *,
    include_revisions: bool = True,
    include_schema_verification: bool = True,
    live: bool = False,
) -> Path:
    quality_dir = root / "quality_evidence"
    quality_dir.mkdir(parents=True)
    bundle = {
        "schema_version": "policyos.canary_evidence.v1",
        "canary_kind": "research",
        "quality_status": "pass",
        "command": {
            "matrix_lane_id": (
                "profile-research__provider-live_gonka_proxy"
                "__data-canonical_production__scenario-public_golden__ui-api_only"
                if live
                else "profile-research__provider-simulated__data-canonical_production"
                "__scenario-public_golden__ui-api_only"
            )
        },
    }
    if include_revisions:
        bundle["git_sha"] = "abc123"
        bundle["code_revision"] = {"git_sha": "abc123", "source": "git"}
    (root / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    (quality_dir / "quality_scorecard.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.quality_scorecard.v1",
                "quality_status": "pass",
                "quality_gates": [
                    {
                        "name": "normative_evidence_present",
                        "status": "pass",
                        "reader_gate_version": (
                            "runtime.scorecard.normative_evidence_present.v2"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = {
        "schema_version": "policyos.lex.normative_applicability_report.v1",
        "status": "pass",
    }
    if include_schema_verification:
        report["schema_compatibility"] = {
            "decision": "compatible",
            "validation_ref": "sha256:" + "a" * 64,
            "reader_gate": "normative_evidence_present",
            "reader_gate_version": "runtime.scorecard.normative_evidence_present.v2",
        }
    (quality_dir / "normative_evidence.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )
    return root


def test_cli_writes_pass_record_for_verified_bundle(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path / "bundle")
    output = tmp_path / "can_i_closeout.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["producer_reader_matrix"][0]["status"] == "pass"


def test_cli_fails_live_bundle_without_revision(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path / "bundle", include_revisions=False, live=True)
    output = tmp_path / "can_i_closeout.json"

    exit_code = check_can_i_closeout.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert {issue["code"] for issue in payload["issues"]} >= {
        "closeout_git_sha_missing",
        "closeout_code_revision_missing",
    }
