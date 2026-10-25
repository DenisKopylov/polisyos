from __future__ import annotations

import json
from pathlib import Path

from tests._helpers.hds_quality import complete_job_payload, complete_quality_evidence
from tools.ops_runners.runtime import canary_evidence
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence


def test_full_assembly_persists_the_bundle_migration_report_under_test_root(
    tmp_path: Path,
    canary_diagnostic_output_root: Path,
) -> None:
    output = assemble_canary_evidence(
        output_root=tmp_path / "bundle",
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    bundle_report = json.loads(
        (output / "migration_sandbox" / "legacy_migration_sandbox.json").read_text(encoding="utf-8")
    )
    persisted_dir = (
        canary_diagnostic_output_root / "_build" / "honest-diagnostics" / "migration-sandbox"
    )
    persisted_reports = list(persisted_dir.glob("*.json"))
    assert len(persisted_reports) == 1
    persisted_report = json.loads(persisted_reports[0].read_text(encoding="utf-8"))
    assert persisted_report == bundle_report
    assert persisted_report["canary_kind"] == "production"

    explicit_report = {"status": "fixture-explicit-root", "validation": "preserved"}
    explicit_root = tmp_path / "explicit-migration-sandbox"
    explicit_path = canary_evidence.persist_legacy_migration_sandbox_report(
        explicit_report,
        repo_root=explicit_root,
        validation_id="explicit-validation",
    )
    assert explicit_path == (
        explicit_root
        / "_build"
        / "honest-diagnostics"
        / "migration-sandbox"
        / "explicit-validation.json"
    )
    assert json.loads(explicit_path.read_text(encoding="utf-8")) == explicit_report
