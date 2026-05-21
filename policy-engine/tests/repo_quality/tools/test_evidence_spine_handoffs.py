from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_evidence_spine_handoffs as checker


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _bundle_dir(tmp_path: Path, *, ledger: dict[str, object] | None) -> Path:
    bundle_dir = tmp_path / "bundle"
    _write_json(
        bundle_dir / "bundle.json",
        {
            "schema_version": "policyos.canary_evidence.v1",
            "files": {
                "quality_evidence": {
                    "evidence_spine_handoff_ledger": (
                        "quality_evidence/evidence_spine_handoff_ledger.json"
                    )
                }
            },
        },
    )
    _write_json(
        bundle_dir / "job.json",
        {
            "job_id": "job-handoff",
            "run_id": "R_handoff",
            "progress": {
                "quality_evidence_bundle_path": str(bundle_dir),
                "evidence_refs": {
                    "quality_scorecard": "quality_evidence/quality_scorecard.json"
                },
            },
        },
    )
    if ledger is not None:
        _write_json(bundle_dir / "quality_evidence" / "evidence_spine_handoff_ledger.json", ledger)
    return bundle_dir


def _passing_ledger() -> dict[str, object]:
    carrier_ref = "evidence-spine:carrier"
    return {
        "schema_version": "policyos.evidence_spine_handoff_ledger.v1",
        "status": "pass",
        "handoffs": [
            {
                "handoff_id": "handoff-nl-request",
                "handoff_kind": "nl_request_creation",
                "producer_ref": "runtime.api.nl_request",
                "consumer_ref": "runtime.control_plane.create_job",
                "parent_spine_ref": "evidence-spine:parent",
                "input_refs": ["request.sanitized.json"],
                "output_refs": ["job.json"],
                "batch_id": None,
                "message_count": 1,
                "carrier_ref": carrier_ref,
                "carrier_redaction_status": "pass",
                "integrity_status": "pass",
            },
            {
                "handoff_id": "handoff-lease",
                "handoff_kind": "control_plane_job_lease",
                "producer_ref": "runtime.control_plane_store",
                "consumer_ref": "runtime.control_worker",
                "parent_spine_ref": "evidence-spine:parent",
                "input_refs": ["job.json"],
                "output_refs": ["job.json#/lease_owner"],
                "batch_id": None,
                "message_count": 1,
                "carrier_ref": carrier_ref,
                "carrier_redaction_status": "pass",
                "integrity_status": "pass",
            },
            {
                "handoff_id": "handoff-workflow",
                "handoff_kind": "workflow_state_persistence",
                "producer_ref": "runtime.nl_pipeline",
                "consumer_ref": "runtime.canary_evidence",
                "parent_spine_ref": "evidence-spine:parent",
                "input_refs": ["job.json"],
                "output_refs": ["quality_evidence/quality_scorecard.json"],
                "batch_id": None,
                "message_count": 1,
                "carrier_ref": carrier_ref,
                "carrier_redaction_status": "pass",
                "integrity_status": "pass",
            },
            {
                "handoff_id": "handoff-cas",
                "handoff_kind": "cas_artifact_write",
                "producer_ref": "runtime.cas_store",
                "consumer_ref": "runtime.evidence_provenance_manifest",
                "parent_spine_ref": "evidence-spine:parent",
                "input_refs": ["artifacts.json"],
                "output_refs": ["cas_manifests/quality_artifact_ownership.manifest.json"],
                "batch_id": None,
                "message_count": 1,
                "carrier_ref": carrier_ref,
                "carrier_redaction_status": "pass",
                "integrity_status": "pass",
            },
            {
                "handoff_id": "handoff-canary",
                "handoff_kind": "canary_bundle_assembly",
                "producer_ref": "tools.ops_runners.runtime.canary_evidence",
                "consumer_ref": "quality.validation.inspect_evidence_bundles",
                "parent_spine_ref": "evidence-spine:parent",
                "input_refs": ["job.json"],
                "output_refs": ["bundle.json"],
                "batch_id": None,
                "message_count": 1,
                "carrier_ref": carrier_ref,
                "carrier_redaction_status": "pass",
                "integrity_status": "pass",
            },
            {
                "handoff_id": "handoff-readiness",
                "handoff_kind": "readiness_result",
                "producer_ref": "quality.validation.inspect_evidence_bundles",
                "consumer_ref": "ci.production_quality_readiness",
                "parent_spine_ref": "evidence-spine:parent",
                "input_refs": ["bundle.json"],
                "output_refs": ["_build/.tmp/production-quality/final_readiness.json"],
                "batch_id": None,
                "message_count": 1,
                "carrier_ref": carrier_ref,
                "carrier_redaction_status": "pass",
                "integrity_status": "pass",
            },
        ],
        "findings": [],
    }


def test_handoff_checker_flags_missing_ledger(tmp_path: Path) -> None:
    bundle_dir = _bundle_dir(tmp_path, ledger=None)

    report = checker.inspect_bundle(bundle_dir)

    assert report["status"] == "fail"
    assert {finding["code"] for finding in report["findings"]} == {
        "evidence_spine_handoff_ledger_missing"
    }


def test_handoff_checker_accepts_complete_ledger(tmp_path: Path) -> None:
    bundle_dir = _bundle_dir(tmp_path, ledger=_passing_ledger())

    report = checker.inspect_bundle(bundle_dir)

    assert report["status"] == "pass"
    assert report["findings"] == []
    assert report["summary"]["handoff_count"] == 6


def test_handoff_checker_fails_missing_carrier_and_output_refs(tmp_path: Path) -> None:
    ledger = _passing_ledger()
    handoff = dict(ledger["handoffs"][0])  # type: ignore[index]
    handoff["carrier_ref"] = None
    handoff["output_refs"] = []
    ledger["handoffs"] = [handoff]
    bundle_dir = _bundle_dir(tmp_path, ledger=ledger)

    report = checker.inspect_bundle(bundle_dir)

    codes = {finding["code"] for finding in report["findings"]}
    assert report["status"] == "fail"
    assert "evidence_spine_handoff_carrier_ref_missing" in codes
    assert "evidence_spine_handoff_output_refs_missing" in codes


def test_handoff_checker_writes_json_and_require_passing_exit_code(tmp_path: Path) -> None:
    bundle_dir = _bundle_dir(tmp_path, ledger=None)
    output = tmp_path / "handoffs.json"

    exit_code = checker.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle_dir),
            "--json-output",
            str(output),
            "--require-passing",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["schema_version"] == "policyos.evidence_spine_handoff_check.v1"
    assert payload["status"] == "fail"
