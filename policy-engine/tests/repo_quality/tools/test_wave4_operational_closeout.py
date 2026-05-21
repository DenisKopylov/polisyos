from __future__ import annotations

import json
from pathlib import Path

from tests._helpers.hds_quality import complete_job_payload, complete_quality_evidence
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence
from tools.quality.validation.check_wave4_operational_closeout import (
    SCHEMA_VERSION,
    build_wave4_operational_closeout_report,
    main,
)


def _fresh_serious_bundle(tmp_path: Path) -> Path:
    return assemble_canary_evidence(
        output_root=tmp_path,
        output_dir=tmp_path / "bundle",
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )


def _report(tmp_path: Path, bundle: Path) -> dict[str, object]:
    return build_wave4_operational_closeout_report(
        repo_root=Path.cwd(),
        bundle_dir=bundle,
        ignore_weekly_baseline_window=True,
        decision_log=Path("docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md"),
    )


def _item_status(report: dict[str, object], item_id: str) -> str:
    for item in report["exit_fence_items"]:
        if item["item_id"] == item_id:
            return item["status"]
    raise AssertionError(f"missing item: {item_id}")


def test_wave4_operational_closeout_accepts_fresh_serious_bundle(tmp_path: Path) -> None:
    bundle = _fresh_serious_bundle(tmp_path)

    report = _report(tmp_path, bundle)

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "pass"
    assert report["blocking_findings"] == []
    assert _item_status(report, "weekly_baseline_window") == "not_applicable_by_instruction"
    assert report["public_export_ref"] == "quality_evidence/public_export_bundle.json"
    assert "semantic_binding_ledger_ref" in report["runtime_refs"]


def test_wave4_operational_closeout_fails_when_public_export_is_missing(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path)
    (bundle / "quality_evidence" / "public_export_bundle.json").unlink()

    report = _report(tmp_path, bundle)

    assert report["status"] == "fail"
    assert _item_status(report, "public_exports_projection_only") == "fail"
    assert {
        finding["code"]
        for finding in report["blocking_findings"]
        if isinstance(finding, dict)
    } >= {"public_export_bundle_missing"}


def test_wave4_operational_closeout_fails_on_provisional_assurance_case(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path)
    path = bundle / "quality_evidence" / "assurance_case.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["assumptions"] = ["provisional marker should not survive final closeout"]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = _report(tmp_path, bundle)

    assert report["status"] == "fail"
    assert _item_status(report, "serious_bundle_assurance_and_slos") == "fail"
    assert {
        finding["code"]
        for finding in report["blocking_findings"]
        if isinstance(finding, dict)
    } >= {"assurance_case_provisional"}


def test_wave4_operational_closeout_fails_on_synthetic_attestation_ref(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path)
    path = bundle / "quality_evidence" / "attestation_records.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[0]["observed_materials"][0]["ref"] = "attestation://synthetic-runtime-worker"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = _report(tmp_path, bundle)

    assert report["status"] == "fail"
    assert _item_status(report, "trust_boundary_attestation_verified") == "fail"
    assert {
        finding["code"]
        for finding in report["blocking_findings"]
        if isinstance(finding, dict)
    } >= {"attestation_synthetic_ref"}


def test_wave4_operational_closeout_cli_writes_report(tmp_path: Path) -> None:
    bundle = _fresh_serious_bundle(tmp_path)
    output = tmp_path / "wave4_closeout.json"

    code = main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle),
            "--ignore-weekly-baseline-window",
            "--json-output",
            str(output),
        ]
    )

    assert code == 0
    assert output.is_file()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "pass"
