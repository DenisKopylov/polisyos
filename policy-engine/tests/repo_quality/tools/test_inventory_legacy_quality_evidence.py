from __future__ import annotations

import json
import tomllib
from pathlib import Path

from tools.quality.validation import inventory_legacy_quality_evidence as inventory

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _case_map(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(row["path"]): row
        for row in payload["entries"]  # type: ignore[index]
    }


def test_legacy_classification_rules_are_source_tracked_and_complete() -> None:
    rules_path = REPO_ROOT / "architecture/production_quality/legacy_evidence_classification.toml"

    assert rules_path.exists()
    rules = tomllib.loads(rules_path.read_text(encoding="utf-8"))

    assert rules["schema_version"] == inventory.RULES_SCHEMA_VERSION
    assert set(rules["classification"]["allowed_classes"]) == set(inventory.CLASSIFICATIONS)
    assert set(rules["classification"]["fail_closed_classes"]) == {
        "legacy_quarantined",
        "legacy_rejected",
        "unknown_schema_blocked",
    }
    assert "_build" in rules["discovery"]["root_paths"]
    assert ".polisyos" in rules["discovery"]["root_paths"]


def test_unknown_schema_and_missing_provenance_are_not_supported(tmp_path: Path) -> None:
    repo_root = tmp_path

    _write_json(
        repo_root / "_build/serious/unknown_schema_report.json",
        {
            "status": "pass",
            "artifact_ref": "cas://sha256/" + "a" * 64,
            "provenance_kind": "runtime_emitted",
        },
    )
    _write_json(
        repo_root / ".polisyos/runs/missing_provenance_report.json",
        {
            "schema_version": "policyos.runtime.quality_scorecard.v1",
            "quality_status": "pass",
            "artifact_ref": "cas://sha256/" + "b" * 64,
        },
    )

    payload = inventory.build_inventory(repo_root=repo_root)
    entries = _case_map(payload)

    unknown_schema = entries["_build/serious/unknown_schema_report.json"]
    assert unknown_schema["classification"] == "unknown_schema_blocked"
    assert unknown_schema["supported_for_serious_closeout"] is False
    assert "unknown_schema" in unknown_schema["reason_codes"]

    missing_provenance = entries[".polisyos/runs/missing_provenance_report.json"]
    assert missing_provenance["classification"] == "legacy_quarantined"
    assert missing_provenance["supported_for_serious_closeout"] is False
    assert "missing_provenance" in missing_provenance["reason_codes"]


def test_bundle_local_ref_payload_mismatch_and_redaction_loss_fail_closed(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path

    _write_json(
        repo_root / "_build/canary/bundle_local_runtime_ref.json",
        {
            "schema_version": "policyos.runtime.quality_scorecard.v1",
            "provenance_kind": "runtime_emitted",
            "quality_status": "pass",
            "runtime_quality_refs": {
                "policy_grounding_matrix_ref": "quality_evidence/policy_grounding_matrix.json",
            },
        },
    )
    _write_json(
        repo_root / "_build/canary/payload_mismatch.json",
        {
            "schema_version": "policyos.runtime.quality_scorecard.v1",
            "provenance_kind": "runtime_emitted",
            "artifact_ref": "cas://sha256/" + "c" * 64,
            "payload_sha256": "d" * 64,
            "payload": {"status": "pass"},
        },
    )
    _write_json(
        repo_root / "docs/archive/reports/redaction_loss_report.json",
        {
            "schema_version": "policyos.runtime.privacy_compliance_report.v1",
            "provenance_kind": "runtime_emitted",
            "artifact_ref": "cas://sha256/" + "e" * 64,
            "redaction": {"lossy": True, "lost_fields": ["claim_evidence_refs"]},
        },
    )

    payload = inventory.build_inventory(repo_root=repo_root)
    entries = _case_map(payload)

    bundle_local_ref = entries["_build/canary/bundle_local_runtime_ref.json"]
    assert bundle_local_ref["classification"] == "legacy_rejected"
    assert bundle_local_ref["supported_for_serious_closeout"] is False
    assert "bundle_local_runtime_ref" in bundle_local_ref["reason_codes"]

    payload_mismatch = entries["_build/canary/payload_mismatch.json"]
    assert payload_mismatch["classification"] == "legacy_rejected"
    assert payload_mismatch["supported_for_serious_closeout"] is False
    assert "payload_sha256_mismatch" in payload_mismatch["reason_codes"]

    redaction_loss = entries["docs/archive/reports/redaction_loss_report.json"]
    assert redaction_loss["classification"] == "legacy_quarantined"
    assert redaction_loss["supported_for_serious_closeout"] is False
    assert "redaction_loss" in redaction_loss["reason_codes"]


def test_cli_writes_generated_json_and_markdown(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_json(
        repo_root / "_build/canary/debug_probe.json",
        {
            "schema_version": "debug.local_probe.v1",
            "debug": True,
            "notes": "operator-only local probe",
        },
    )
    output_dir = repo_root / "_build/honest-diagnostics/legacy"

    assert inventory.main(["--repo-root", str(repo_root), "--output-dir", str(output_dir)]) == 0

    json_output = output_dir / "legacy_inventory.json"
    markdown_output = output_dir / "legacy_inventory.md"
    assert json_output.exists()
    assert markdown_output.exists()

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == inventory.SCHEMA_VERSION
    assert payload["summary"]["entry_count"] == 1
    assert "| `_build/canary/debug_probe.json` |" in markdown_output.read_text(encoding="utf-8")
