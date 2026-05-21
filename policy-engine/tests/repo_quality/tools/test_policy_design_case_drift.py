# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from tools.quality.validation import check_policy_design_case_drift as drift

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_policy_design_case_drift_current_scope_passes_initial_checks() -> None:
    payload = drift.build_policy_design_case_drift_payload(repo_root=REPO_ROOT)

    assert payload["schema_version"] == "policyos.policy_design_case.drift.v1"
    assert payload["status"] == "pass", payload["violations"]
    assert payload["reuse_violation_count"] == 0
    assert payload["parallel_case_authority_violation_count"] == 0
    assert payload["capability_map"]["target_capability_count"] == 27
    assert (
        "src/polisyos/runtime/quality/assurance_case.py"
        in payload["runtime_quality_authority_paths"]
    )


def test_policy_design_case_drift_rejects_parallel_case_authority(
    tmp_path: Path,
) -> None:
    target = tmp_path / "src" / "polisyos" / "scientist" / "policy_design_case.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                "class PolicyDesignCaseAuthority:",
                "    pass",
                "",
                "def build_policy_design_case_authority():",
                "    return PolicyDesignCaseAuthority()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = drift.build_policy_design_case_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        sdd_path=None,
    )

    assert payload["status"] == "fail"
    assert payload["parallel_case_authority_violation_count"] == 2
    assert _codes(payload) == {"pdc_parallel_case_authority"}


def test_policy_design_case_drift_rejects_build_new_overlap_without_evidence(
    tmp_path: Path,
) -> None:
    sdd = tmp_path / "sdd.md"
    sdd.write_text(
        "\n".join(
            [
                "## Capability Realization Map",
                "",
                "| Target capability | Existing owner or surface | Status | Design implication |",
                "| --- | --- | --- | --- |",
                (
                    "| Data Forge production corpus rebuild | `src/polisyos/data_forge/*` | "
                    "build-new | Replace the existing owner. |"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = drift.build_policy_design_case_drift_payload(
        repo_root=tmp_path,
        scan_paths=[],
        sdd_path=sdd,
    )

    assert payload["status"] == "fail"
    assert "pdc_build_new_reuse_evidence_missing" in _codes(payload)


def test_policy_design_case_drift_rejects_second_authority_profile_taxonomy(
    tmp_path: Path,
) -> None:
    target = tmp_path / "src" / "polisyos" / "scientist" / "policy_authority_profiles.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                'POLICY_AUTHORITY_PROFILES = ("research", "sandbox", "production")',
                'POLICY_AUTHORITY_TO_VALIDATION_PROFILE = {"sandbox": "strict"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = drift.build_policy_design_case_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        sdd_path=None,
    )

    assert payload["status"] == "fail"
    assert "pdc_second_authority_profile_taxonomy" in _codes(payload)


def test_policy_design_case_drift_rejects_synonymous_authority_level_taxonomy(
    tmp_path: Path,
) -> None:
    target = tmp_path / "src" / "polisyos" / "runtime" / "policy_levels.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                'POLICY_AUTHORITY_LEVELS = ("research", "governed", "production")',
                'POLICY_AUTHORITY_LEVEL_TO_VALIDATION = {"production": "strict"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = drift.build_policy_design_case_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        sdd_path=None,
    )

    assert payload["status"] == "fail"
    assert "pdc_second_authority_profile_taxonomy" in _codes(payload)


def _codes(payload: dict[str, object]) -> set[str]:
    return {str(violation["code"]) for violation in payload["violations"]}  # type: ignore[index]
