from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.lib import document_references
from tools.quality.validation import check_docs_lifecycle as lifecycle

OLD_DASHBOARD = "frontend" + "/runtime-dashboard"
OLD_CLIENT = "frontend" + "/runtime-api-client"


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)


def _archive_map() -> dict[str, object]:
    return {
        "archive_sha256": "a" * 64,
        "archive_non_directory_members": 1,
        "members": [
            {
                "path": f"{OLD_DASHBOARD}/archive.ts",
                "size": 12,
                "sha256": "b" * 64,
                "ledger_entry_id": "sample",
                "normalization_rule": "exact-member",
                "live_consumer": OLD_CLIENT,
            }
        ],
    }


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        ("docs/superpowers/journals/unseen.md", f"Historical finding: {OLD_DASHBOARD}"),
        (
            "docs/superpowers/journals/unseen.json",
            json.dumps({"findings": [OLD_DASHBOARD]}),
        ),
        (
            "docs/research/topic/audits/new/report.md",
            "---\nkind: research-audit\nresearch_only: true\n"
            f"historical_repository_commit: {'a' * 40}\n"
            f"current_repository_commit: {'b' * 40}\n---\nObserved {OLD_DASHBOARD}",
        ),
        (
            "docs/reference/adoption.md",
            f"| Item / archive evidence | Live consumer |\n| --- | --- |\n"
            f"| `{OLD_DASHBOARD}/archive.ts` | {OLD_CLIENT} |\n",
        ),
        (
            "architecture/another-archive-map.json",
            json.dumps(_archive_map()),
        ),
        (
            "architecture/another-ledger.json",
            json.dumps({"ref": f"design/source.zip::{OLD_DASHBOARD}/archive.ts:1"}),
        ),
    ],
)
def test_historical_reference_roles_do_not_become_live_paths(
    tmp_path: Path, relative: str, text: str
) -> None:
    _write(tmp_path, relative, text)
    findings = lifecycle.check_removed_stub_references(tmp_path)
    assert not any(OLD_DASHBOARD in finding.message for finding in findings)
    if OLD_CLIENT in text:
        assert [(finding.check, finding.path) for finding in findings] == [
            ("removed_stub_reference", relative)
        ]
        assert OLD_CLIENT in findings[0].message


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        ("docs/live.md", f"Use {OLD_DASHBOARD} for development."),
        ("src/evidence.md", f"Use {OLD_DASHBOARD} for development."),
        (
            "docs/research/topic/audits/new/report.md",
            f"---\nkind: research-audit\nresearch_only: true\n---\nUse {OLD_DASHBOARD}.",
        ),
        (
            "architecture/live-map.json",
            json.dumps({"members": [{"path": OLD_DASHBOARD}]}),
        ),
        (
            "docs/reference/live.md",
            f"| Evidence | Live consumer |\n| --- | --- |\n| old | {OLD_DASHBOARD} |\n",
        ),
    ],
)
def test_live_or_unestablished_reference_roles_still_fail(
    tmp_path: Path, relative: str, text: str
) -> None:
    _write(tmp_path, relative, text)
    findings = lifecycle.check_removed_stub_references(tmp_path)
    assert [(finding.check, finding.path) for finding in findings] == [
        ("removed_stub_reference", relative)
    ]
    assert OLD_DASHBOARD in findings[0].message


def test_station_debris_cannot_enter_committed_reference_or_plan_denominator(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _write(tmp_path, ".gitignore", ".tmp/\n")
    _write(tmp_path, "docs/live.md", "Current documentation.\n")
    _git(tmp_path, "add", ".")
    before = lifecycle.check_removed_stub_references(tmp_path)
    archive_before = lifecycle.check_archive_reports(tmp_path)
    _write(tmp_path, ".tmp/evidence.md", OLD_DASHBOARD)
    _write(tmp_path, "docs/untracked.md", OLD_DASHBOARD)
    _write(tmp_path, "docs/plans/active/UNTRACKED.md", "No plan metadata")
    _write(tmp_path, "tests/" + "architecture/README.md", "obsolete station directory")
    _write(tmp_path, "docs/archive/plans/local.md", "station artifact")
    _write(tmp_path, "docs/archive/local.py", "# station artifact")
    _write(tmp_path, "local/README.md", "---\nredirect_stub: true\n---\n")
    assert lifecycle.check_removed_stub_references(tmp_path) == before == []
    assert lifecycle.check_active_plans(tmp_path) == []
    assert lifecycle.check_redirect_stubs(tmp_path) == []
    assert lifecycle.check_archive_reports(tmp_path) == archive_before
    _git(tmp_path, "add", "docs/untracked.md")
    assert [finding.path for finding in lifecycle.check_removed_stub_references(tmp_path)] == [
        "docs/untracked.md"
    ]


@pytest.mark.parametrize("damage", ["missing", "invalid_utf8", "invalid_json"])
def test_unreadable_committed_reference_is_ambiguous(tmp_path: Path, damage: str) -> None:
    _git(tmp_path, "init")
    path = _write(tmp_path, "docs/input.json", '{"path": "current"}')
    _git(tmp_path, "add", ".")
    if damage == "missing":
        path.unlink()
    elif damage == "invalid_utf8":
        path.write_bytes(b"\xff")
    else:
        path.write_text("{bad", encoding="utf-8")
    findings = lifecycle.check_removed_stub_references(tmp_path)
    assert [(finding.check, finding.path) for finding in findings] == [
        ("reference_scan_ambiguous", "docs/input.json")
    ]


def test_generated_ledger_role_does_not_exempt_an_actual_plan(tmp_path: Path) -> None:
    marker = "Generated by `tools/quality/validation/check_debt_ledger.py --write`."
    _write(tmp_path, "docs/plans/active/LEDGER.md", f"# Aggregate\n{marker}\n")
    _write(tmp_path, "docs/plans/active/REAL_PLAN.md", f"# Plan\n{marker}\n")
    findings = lifecycle.check_active_plans(tmp_path)
    assert [(finding.check, finding.path, finding.message) for finding in findings] == [
        (
            "active_plan_metadata",
            "docs/plans/active/REAL_PLAN.md",
            f"active plan missing `{field}` front matter.",
        )
        for field in ("status", "owner")
    ]


def test_malformed_evidence_json_does_not_disappear(tmp_path: Path) -> None:
    relative = "docs/superpowers/journals/new.json"
    _write(tmp_path, relative, "{bad")
    assert [finding.check for finding in lifecycle.check_removed_stub_references(tmp_path)] == [
        "reference_scan_ambiguous"
    ]


def test_generated_aggregate_without_its_producer_is_ambiguous(tmp_path: Path) -> None:
    _write(tmp_path, "docs/plans/active/LEDGER.md", "# Unclassified document\n")
    assert [finding.check for finding in lifecycle.check_active_plans(tmp_path)] == [
        "active_plan_aggregate"
    ]


def test_missing_repository_enumeration_fails_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_repo_root: Path) -> list[Path]:
        raise RuntimeError("committed enumeration unavailable")

    monkeypatch.setattr(lifecycle, "_iter_repository_files", broken)
    findings = lifecycle.run_checks(tmp_path)
    assert any(
        finding.check == "lifecycle_scan_ambiguous"
        and "check_removed_stub_references" in finding.message
        for finding in findings
    )
    assert lifecycle.main(["--repo-root", str(tmp_path)]) == 1


def test_archive_map_keeps_member_paths_when_its_denominator_is_unestablished() -> None:
    payload = _archive_map()
    payload["archive_non_directory_members"] = 2
    text = document_references.reference_scan_text(
        Path("architecture/incomplete-map.json"), json.dumps(payload)
    )
    assert OLD_DASHBOARD in text


def test_adr_producer_uses_the_same_committed_file_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(tmp_path, "init")
    tracked = _write(tmp_path, "docs/adr/0001-tracked.md", "# ADR-0001: Current\n")
    _git(tmp_path, "add", ".")
    _write(tmp_path, "docs/adr/0002-local.md", "# ADR-0002: Station-local\n")
    _write(tmp_path, ".git/info/exclude", "docs/adr/0001-tracked.md\n")
    monkeypatch.setattr(lifecycle.generate_adr_index, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lifecycle.generate_adr_index, "ADR_DIR", tmp_path / "docs/adr")
    assert lifecycle.generate_adr_index._markdown_files() == [tracked]
