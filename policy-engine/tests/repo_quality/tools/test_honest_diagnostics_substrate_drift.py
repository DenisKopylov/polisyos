# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from tools.quality.validation import check_substrate_drift as drift

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_ANTI_DRIFT_FIELDS = {
    "xfail_strict_count",
    "xfail_non_strict_count",
    "skip_count_substrate_tests",
    "allow_fallback_count",
    "fixture_serious_consumption_count",
    "warn_closeout_acceptance_count",
    "adr_softening_findings",
    "non_goal_violations",
    "ci_tier_violations",
    "temporary_exception_violations",
    "violations",
    "status",
}


def test_honest_diagnostics_substrate_drift_current_scope_passes() -> None:
    payload = drift.build_substrate_drift_payload(repo_root=REPO_ROOT)

    assert payload["status"] == "pass"
    assert set(payload) >= REQUIRED_ANTI_DRIFT_FIELDS
    assert payload["xfail_strict_count"] == 0
    assert payload["xfail_non_strict_count"] == 0
    assert payload["skip_count_substrate_tests"] == 0
    assert payload["fixture_serious_consumption_count"] == 0
    assert payload["warn_closeout_acceptance_count"] == 0
    assert payload["non_goal_violations"] == []
    assert payload["ci_tier_violations"] == []
    assert payload["temporary_exception_violations"] == []


def test_honest_diagnostics_substrate_drift_scans_archived_wave6_plan() -> None:
    payload = drift.build_substrate_drift_payload(repo_root=REPO_ROOT)

    assert (
        "docs/plans/archive/2026-05-16-policyos-honest-diagnostics-substrate-implementation-plan.md"
        in payload["scan_paths"]
    )
    assert "docs/plans/active/POLICYOS_HONEST_DIAGNOSTICS_SUBSTRATE_IMPLEMENTATION_PLAN.md" not in {
        violation["path"] for violation in payload["violations"]
    }


def test_honest_diagnostics_substrate_drift_rejects_non_strict_xfail(
    tmp_path: Path,
) -> None:
    target = tmp_path / "test_hds_non_strict_xfail.py"
    target.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "@pytest.mark.xfail(reason='temporary')",
                "def test_hds_control():",
                "    assert False",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = drift.build_substrate_drift_payload(repo_root=tmp_path, scan_paths=[target])

    assert payload["status"] == "fail"
    assert payload["xfail_non_strict_count"] == 1
    assert _codes(payload) == {"hds_non_strict_xfail"}


def test_honest_diagnostics_substrate_drift_rejects_permanent_skip(
    tmp_path: Path,
) -> None:
    target = tmp_path / "test_hds_skip.py"
    target.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "@pytest.mark.skip(reason='do not run')",
                "def test_hds_control():",
                "    assert False",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = drift.build_substrate_drift_payload(repo_root=tmp_path, scan_paths=[target])

    assert payload["status"] == "fail"
    assert payload["skip_count_substrate_tests"] == 1
    assert _codes(payload) == {"hds_permanent_skip"}


def test_honest_diagnostics_substrate_drift_rejects_module_level_skip(
    tmp_path: Path,
) -> None:
    target = tmp_path / "test_hds_module_skip.py"
    target.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "pytestmark = pytest.mark.skip(reason='broad skip')",
                "",
                "def test_hds_control():",
                "    assert False",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = drift.build_substrate_drift_payload(repo_root=tmp_path, scan_paths=[target])

    assert payload["status"] == "fail"
    assert payload["skip_count_substrate_tests"] == 1
    assert _codes(payload) == {"hds_permanent_skip"}


def test_honest_diagnostics_substrate_drift_rejects_fixture_serious_consumption(
    tmp_path: Path,
) -> None:
    target = tmp_path / "test_hds_fixture_consumption.py"
    target.write_text(
        "FIXTURE_SERIOUS_CONSUMPTION_ALLOWED = True\n",
        encoding="utf-8",
    )

    payload = drift.build_substrate_drift_payload(repo_root=tmp_path, scan_paths=[target])

    assert payload["status"] == "fail"
    assert payload["fixture_serious_consumption_count"] == 1
    assert _codes(payload) == {"hds_fixture_serious_consumption"}


def test_honest_diagnostics_substrate_drift_rejects_warn_closeout_acceptance(
    tmp_path: Path,
) -> None:
    target = tmp_path / "test_hds_warn_acceptance.py"
    target.write_text(
        "WARN_CLOSEOUT_ACCEPTANCE_ALLOWED = True\n",
        encoding="utf-8",
    )

    payload = drift.build_substrate_drift_payload(repo_root=tmp_path, scan_paths=[target])

    assert payload["status"] == "fail"
    assert payload["warn_closeout_acceptance_count"] == 1
    assert _codes(payload) == {"hds_warn_closeout_acceptance"}


def test_honest_diagnostics_substrate_drift_rejects_adr_softening(
    tmp_path: Path,
) -> None:
    target = tmp_path / "test_hds_adr_softening.py"
    target.write_text(
        "ADR_SOFTENING_ALLOWED = True\n",
        encoding="utf-8",
    )

    payload = drift.build_substrate_drift_payload(repo_root=tmp_path, scan_paths=[target])

    assert payload["status"] == "fail"
    assert _codes(payload) == {"hds_adr_softening"}
    assert payload["adr_softening_findings"] != []


def test_honest_diagnostics_substrate_drift_rejects_non_goal_violation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "test_hds_non_goal.py"
    target.write_text(
        "HDS_NON_GOAL_VIOLATION = True\n",
        encoding="utf-8",
    )

    payload = drift.build_substrate_drift_payload(repo_root=tmp_path, scan_paths=[target])

    assert payload["status"] == "fail"
    assert _codes(payload) == {"hds_non_goal_violation"}
    assert payload["non_goal_violations"] != []


def test_honest_diagnostics_substrate_drift_rejects_duplicate_tier_declaration(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests" / "test_hds_duplicate_tier.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_hds_control():\n    assert True\n", encoding="utf-8")
    ci_tiers = tmp_path / "ci_tiers.toml"
    _write_ci_tiers(
        ci_tiers,
        tests=[
            {"path": "tests/test_hds_duplicate_tier.py", "tier": "fast-pr"},
            {"path": "tests/test_hds_duplicate_tier.py", "tier": "nightly"},
        ],
    )
    decision_log = _write_decision_log(tmp_path / "decision-log.md")
    invariant_registry = _write_invariant_registry(tmp_path / "invariants.toml")

    payload = drift.build_substrate_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        ci_tiers_path=ci_tiers,
        decision_log_path=decision_log,
        invariant_registry_path=invariant_registry,
    )

    assert payload["status"] == "fail"
    assert "hds_test_tier_duplicate" in _codes(payload)


def test_honest_diagnostics_substrate_drift_rejects_slow_test_without_tier(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests" / "test_hds_slow_without_tier.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "@pytest.mark.slow",
                "def test_hds_control():",
                "    assert True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ci_tiers = tmp_path / "ci_tiers.toml"
    _write_ci_tiers(ci_tiers, tests=[])
    decision_log = _write_decision_log(tmp_path / "decision-log.md")
    invariant_registry = _write_invariant_registry(tmp_path / "invariants.toml")

    payload = drift.build_substrate_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        ci_tiers_path=ci_tiers,
        decision_log_path=decision_log,
        invariant_registry_path=invariant_registry,
    )

    assert payload["status"] == "fail"
    assert _codes(payload) >= {"hds_test_tier_missing", "hds_slow_test_tier_missing"}


def test_honest_diagnostics_substrate_drift_rejects_unregistered_strict_xfail(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests" / "test_hds_new_xfail.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "HDS_RED_XFAIL = pytest.mark.xfail(strict=True, reason='temporary')",
                "",
                "@HDS_RED_XFAIL",
                "def test_hds_control():",
                "    assert False",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ci_tiers = tmp_path / "ci_tiers.toml"
    _write_ci_tiers(
        ci_tiers,
        tests=[{"path": "tests/test_hds_new_xfail.py", "tier": "fast-pr"}],
        xfail_strict_count=0,
    )
    decision_log = _write_decision_log(tmp_path / "decision-log.md")
    invariant_registry = _write_invariant_registry(tmp_path / "invariants.toml")

    payload = drift.build_substrate_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        ci_tiers_path=ci_tiers,
        decision_log_path=decision_log,
        invariant_registry_path=invariant_registry,
    )

    assert payload["status"] == "fail"
    assert "hds_strict_xfail_unregistered" in _codes(payload)


def test_honest_diagnostics_substrate_drift_requires_decision_log_for_temporary_exception(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests" / "test_hds_registered_xfail.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "HDS_RED_XFAIL = pytest.mark.xfail(strict=True, reason='temporary')",
                "",
                "@HDS_RED_XFAIL",
                "def test_hds_control():",
                "    assert False",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ci_tiers = tmp_path / "ci_tiers.toml"
    _write_ci_tiers(
        ci_tiers,
        tests=[{"path": "tests/test_hds_registered_xfail.py", "tier": "fast-pr"}],
        xfail_strict_count=1,
        exceptions=[
            {
                "exception_id": "HDS-XFAIL-TEST",
                "kind": "strict_xfail",
                "invariant_id": "HDS-MCG-TEST",
                "decision_id": "DL-HDS-9999",
                "max_count": 1,
                "path_globs": ["tests/test_hds_registered_xfail.py"],
            }
        ],
    )
    decision_log = _write_decision_log(
        tmp_path / "decision-log.md",
        owner="",
        invariant="",
        revisit_wave="",
    )
    invariant_registry = _write_invariant_registry(
        tmp_path / "invariants.toml",
        temporary_exception_ids=["HDS-XFAIL-TEST"],
    )

    payload = drift.build_substrate_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        ci_tiers_path=ci_tiers,
        decision_log_path=decision_log,
        invariant_registry_path=invariant_registry,
    )

    assert payload["status"] == "fail"
    assert "hds_decision_log_exception_incomplete" in _codes(payload)


def test_honest_diagnostics_substrate_drift_rejects_fallback_without_permission(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests" / "test_hds_fallback.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "POLICY = {'allow_mock_fallback': True}\n",
        encoding="utf-8",
    )
    ci_tiers = tmp_path / "ci_tiers.toml"
    _write_ci_tiers(
        ci_tiers,
        tests=[{"path": "tests/test_hds_fallback.py", "tier": "fast-pr"}],
    )
    decision_log = _write_decision_log(tmp_path / "decision-log.md")
    invariant_registry = _write_invariant_registry(tmp_path / "invariants.toml")

    payload = drift.build_substrate_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        ci_tiers_path=ci_tiers,
        decision_log_path=decision_log,
        invariant_registry_path=invariant_registry,
    )

    assert payload["status"] == "fail"
    assert "hds_fallback_allowance_without_registry" in _codes(payload)


def test_honest_diagnostics_substrate_drift_rejects_fallback_without_invariant_permission(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests" / "test_hds_registered_fallback.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "POLICY = {'allow_mock_fallback': True}\n",
        encoding="utf-8",
    )
    ci_tiers = tmp_path / "ci_tiers.toml"
    _write_ci_tiers(
        ci_tiers,
        tests=[{"path": "tests/test_hds_registered_fallback.py", "tier": "fast-pr"}],
        exceptions=[
            {
                "exception_id": "HDS-FALLBACK-TEST",
                "kind": "fallback_allowance",
                "invariant_id": "HDS-MCG-TEST",
                "decision_id": "DL-HDS-9999",
                "max_count": 1,
                "path_globs": ["tests/test_hds_registered_fallback.py"],
                "fallback_flags": ["allow_mock_fallback"],
            }
        ],
    )
    decision_log = _write_decision_log(tmp_path / "decision-log.md")
    invariant_registry = _write_invariant_registry(
        tmp_path / "invariants.toml",
        temporary_exception_ids=[],
    )

    payload = drift.build_substrate_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        ci_tiers_path=ci_tiers,
        decision_log_path=decision_log,
        invariant_registry_path=invariant_registry,
    )

    assert payload["status"] == "fail"
    assert "hds_temporary_exception_invariant_permission_missing" in _codes(payload)


def test_honest_diagnostics_substrate_drift_allows_registered_fallback_exception(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests" / "test_hds_registered_fallback.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "POLICY = {'allow_mock_fallback': True}\n",
        encoding="utf-8",
    )
    ci_tiers = tmp_path / "ci_tiers.toml"
    _write_ci_tiers(
        ci_tiers,
        tests=[{"path": "tests/test_hds_registered_fallback.py", "tier": "fast-pr"}],
        exceptions=[
            {
                "exception_id": "HDS-FALLBACK-TEST",
                "kind": "fallback_allowance",
                "invariant_id": "HDS-MCG-TEST",
                "decision_id": "DL-HDS-9999",
                "max_count": 1,
                "path_globs": ["tests/test_hds_registered_fallback.py"],
                "fallback_flags": ["allow_mock_fallback"],
            }
        ],
    )
    decision_log = _write_decision_log(tmp_path / "decision-log.md")
    invariant_registry = _write_invariant_registry(
        tmp_path / "invariants.toml",
        temporary_exception_ids=["HDS-FALLBACK-TEST"],
    )

    payload = drift.build_substrate_drift_payload(
        repo_root=tmp_path,
        scan_paths=[target],
        ci_tiers_path=ci_tiers,
        decision_log_path=decision_log,
        invariant_registry_path=invariant_registry,
    )

    assert payload["status"] == "pass"
    assert payload["allow_fallback_count"] == 1
    assert payload["violations"] == []


def _write_ci_tiers(
    path: Path,
    *,
    tests: list[dict[str, str]],
    exceptions: list[dict[str, object]] | None = None,
    xfail_strict_count: int = 0,
) -> None:
    lines = [
        'schema_version = "policyos.hds_ci_tiers.v1"',
        'allowed_tiers = ["fast-pr", "integration-pr", "nightly", "weekly-closeout"]',
        "",
        "[anti_drift_baseline]",
        f"xfail_strict_count = {xfail_strict_count}",
        "",
    ]
    for row in tests:
        lines.extend(
            [
                "[[tests]]",
                f'path = "{row["path"]}"',
                f'tier = "{row["tier"]}"',
                'owner = "team-runtime-quality"',
                "",
            ]
        )
    for row in exceptions or []:
        lines.extend(
            [
                "[[temporary_exceptions]]",
                f'exception_id = "{row["exception_id"]}"',
                f'kind = "{row["kind"]}"',
                f'invariant_id = "{row["invariant_id"]}"',
                f'decision_id = "{row["decision_id"]}"',
                f"max_count = {row.get('max_count', 1)}",
                "path_globs = [" + ", ".join(f'"{item}"' for item in row["path_globs"]) + "]",
            ]
        )
        if "fallback_flags" in row:
            lines.append(
                "fallback_flags = ["
                + ", ".join(f'"{item}"' for item in row["fallback_flags"])
                + "]"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_invariant_registry(
    path: Path,
    *,
    temporary_exception_ids: list[str] | None = None,
) -> Path:
    exception_ids = temporary_exception_ids or []
    path.write_text(
        "\n".join(
            [
                "[[invariants]]",
                'invariant_id = "HDS-MCG-TEST"',
                "temporary_exception_ids = ["
                + ", ".join(f'"{item}"' for item in exception_ids)
                + "]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_decision_log(
    path: Path,
    *,
    decision_id: str = "DL-HDS-9999",
    owner: str = "team-runtime-quality",
    invariant: str = "HDS-MCG-TEST",
    revisit_wave: str = "after Wave 2",
) -> Path:
    path.write_text(
        "\n".join(
            [
                "# Decision Log",
                "",
                "## Entries",
                "",
                f"### {decision_id} - temporary exception test",
                "",
                "- **Date**: 2026-05-15",
                "- **Context**: Test-only temporary exception context.",
                "- **Decision**: Test-only temporary exception decision.",
                "- **Affected ADR**: ADR-0149, ADR-0155",
                f"- **Affected invariant id or phase id**: {invariant}",
                f"- **Owner**: {owner}",
                "- **Reversibility**: reversible",
                "- **Revisit trigger**: Test trigger.",
                f"- **Revisit wave**: {revisit_wave}",
                "- **Promotion status**: log_only_pending_revisit",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _codes(payload: dict[str, object]) -> set[str]:
    violations = payload["violations"]
    assert isinstance(violations, list)
    return {str(row["code"]) for row in violations if isinstance(row, dict)}
