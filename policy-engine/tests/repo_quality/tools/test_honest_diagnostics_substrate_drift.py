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
    "violations",
    "status",
}


def test_honest_diagnostics_substrate_drift_current_scope_passes() -> None:
    payload = drift.build_substrate_drift_payload(repo_root=REPO_ROOT)

    assert payload["status"] == "pass"
    assert REQUIRED_ANTI_DRIFT_FIELDS <= set(payload)
    assert payload["xfail_strict_count"] >= 1
    assert payload["xfail_non_strict_count"] == 0
    assert payload["skip_count_substrate_tests"] == 0
    assert payload["fixture_serious_consumption_count"] == 0
    assert payload["warn_closeout_acceptance_count"] == 0
    assert payload["non_goal_violations"] == []


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


def _codes(payload: dict[str, object]) -> set[str]:
    violations = payload["violations"]
    assert isinstance(violations, list)
    return {str(row["code"]) for row in violations if isinstance(row, dict)}
