from __future__ import annotations

# ruff: noqa: ANN001, S101
import json

from tests._helpers.hds_quality import complete_job_payload, complete_quality_evidence
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence


def test_serious_canary_bundle_writes_assurance_case_and_diagnostic_slos(tmp_path) -> None:
    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    bundle = json.loads((output / "bundle.json").read_text(encoding="utf-8"))
    assurance_case = json.loads(
        (output / "quality_evidence" / "assurance_case.json").read_text(encoding="utf-8")
    )
    diagnostic_slos = json.loads(
        (output / "quality_evidence" / "diagnostic_slo_report.json").read_text(
            encoding="utf-8"
        )
    )

    assert bundle["files"]["quality_evidence"]["assurance_case"] == (
        "quality_evidence/assurance_case.json"
    )
    assert bundle["files"]["quality_evidence"]["diagnostic_slo_report"] == (
        "quality_evidence/diagnostic_slo_report.json"
    )
    assert assurance_case["claim"]["canary_kind"] == "production"
    assert assurance_case["owner"] == "team-assurance"
    assert diagnostic_slos["status"] == "pass"
    assert diagnostic_slos["error_budget_policy"]["decision"] == "pass"
