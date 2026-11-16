from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers.hds_quality import complete_job_payload, complete_quality_evidence
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence
from tools.quality.validation.check_wave4_operational_closeout import (
    SCHEMA_VERSION,
    build_wave4_operational_closeout_report,
    main,
)

pytestmark = pytest.mark.usefixtures("canary_diagnostic_output_root")


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
        decision_log=Path(
            "docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md"
        ),
    )


def _item_status(report: dict[str, object], item_id: str) -> str:
    for item in report["exit_fence_items"]:
        if item["item_id"] == item_id:
            return item["status"]
    raise AssertionError(f"missing item: {item_id}")


def test_wave4_operational_closeout_blocks_unappointed_fresh_boundary_declarations(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path)

    report = _report(tmp_path, bundle)

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "fail"
    assert _item_status(report, "trust_boundary_attestation_verified") == "fail"
    assert "attestation_verifier_not_appointed" in {
        finding["code"] for finding in report["blocking_findings"]
    }
    assert _item_status(report, "weekly_baseline_window") == "not_applicable_by_instruction"
    assert report["public_export_ref"] == "quality_evidence/public_export_bundle.json"
    from polisyos.runtime.quality.attestation import (
        iter_required_production_attestation_boundaries,
    )

    assert set(report["attestation_refs"]) == {
        boundary.boundary_id for boundary in iter_required_production_attestation_boundaries()
    }


def test_wave4_operational_closeout_fails_when_public_export_is_missing(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path)
    (bundle / "quality_evidence" / "public_export_bundle.json").unlink()

    report = _report(tmp_path, bundle)

    assert report["status"] == "fail"
    assert _item_status(report, "public_exports_projection_only") == "fail"
    assert {
        finding["code"] for finding in report["blocking_findings"] if isinstance(finding, dict)
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
        finding["code"] for finding in report["blocking_findings"] if isinstance(finding, dict)
    } >= {"assurance_case_provisional"}


def test_wave4_operational_closeout_fails_on_synthetic_attestation_ref(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path)
    path = bundle / "quality_evidence" / "attestation_records.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    from polisyos.runtime.quality.attestation import (
        build_verified_attestation_record,
        load_trust_boundary_registry,
    )

    boundary = load_trust_boundary_registry().require("runtime_worker")
    record = build_verified_attestation_record(
        boundary_id="runtime_worker",
        material_refs={key: f"declared://{key}" for key in boundary.expected_material_kinds},
        product_refs={key: f"declared://{key}" for key in boundary.expected_product_kinds},
    )
    record.observed_materials[0].ref = "attestation://synthetic-runtime-worker"
    payload[0] = record.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = _report(tmp_path, bundle)

    assert report["status"] == "fail"
    assert _item_status(report, "trust_boundary_attestation_verified") == "fail"
    assert {
        finding["code"] for finding in report["blocking_findings"] if isinstance(finding, dict)
    } >= {"attestation_synthetic_material_ref"}


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

    assert code == 1
    assert output.is_file()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "fail"


def test_wave4_checker_uses_the_same_unappointed_authority_owner(monkeypatch) -> None:
    """Removing the canonical denial makes this checker assertion turn red."""
    from dataclasses import replace

    from polisyos.runtime.quality import attestation as owner
    from tools.quality.validation import check_wave4_operational_closeout as checker

    registry = owner.load_trust_boundary_registry()
    records = [
        owner.build_verified_attestation_record(
            boundary_id=boundary.boundary_id,
            material_refs={key: f"declared://{key}" for key in boundary.expected_material_kinds},
            product_refs={key: f"declared://{key}" for key in boundary.expected_product_kinds},
            registry=registry,
        ).model_dump(mode="json")
        for boundary in registry.boundaries.values()
    ]
    quality = {"attestation_records": records}

    def assertion():
        findings = checker._attestation_findings(quality)
        assert len(findings) == len(registry.boundaries)
        assert all(row["code"] == "attestation_verifier_not_appointed" for row in findings)

    assertion()
    original = owner._result

    def removed_denial(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.status == "not_established":
            return replace(result, status="verified", production_closeout_satisfied=True)
        return result

    with monkeypatch.context() as removal:
        removal.setattr(owner, "_result", removed_denial)
        with pytest.raises(AssertionError):
            assertion()
    assertion()
