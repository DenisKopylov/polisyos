# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_policy_design_case_walking_skeleton as smoke

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_research_smoke_proves_ref_path_without_promoting_stub_domains() -> None:
    payload = smoke.build_walking_skeleton_readiness_payload(repo_root=REPO_ROOT)

    research = payload["profiles"]["research"]

    assert payload["schema_version"] == smoke.SCHEMA_VERSION
    assert payload["status"] == "pass"
    assert research["readiness_outcome"] in {"pass", "deficit"}
    assert research["all_refs_present"] is True
    assert research["ref_path"]["status"] == "pass"
    assert research["ref_path"]["edges"] == [
        "intent -> stub spine",
        "stub spine -> stub producer",
        "stub producer -> claim",
        "single_line_evidence_deficit -> claim",
        "claim -> scorecard/readiness",
    ]
    assert research["accepted_deficits"] == ["single_line_evidence_deficit"]
    assert research["implemented_domain_record_families"] == []
    assert research["stub_record_families"] == [
        "walking_skeleton_stub_producer_evidence.v1"
    ]


def test_walking_skeleton_readiness_governed_and_production_fail_with_typed_blockers() -> None:
    payload = smoke.build_walking_skeleton_readiness_payload(repo_root=REPO_ROOT)

    for profile in ("governed", "production"):
        result = payload["profiles"][profile]
        blocker_codes = {blocker["code"] for blocker in result["blockers"]}
        blocker_types = {blocker["blocker_type"] for blocker in result["blockers"]}

        assert result["readiness_outcome"] == "fail"
        assert "policy_design_skeleton_single_line_deficit_not_allowed" in blocker_codes
        assert "policy_design_skeleton_missing_domain_evidence" in blocker_codes
        assert "accepted_deficit_not_allowed" in blocker_types
        assert "missing_domain_evidence" in blocker_types
        assert result["implemented_domain_record_families"] == []
        assert result["stub_record_families"] == [
            "walking_skeleton_stub_producer_evidence.v1"
        ]


def test_walking_skeleton_readiness_main_writes_rebaseline_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "walking_skeleton_readiness.json"

    exit_code = smoke.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output),
            "--output-format",
            "json",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["output"]["path"] == str(output)
