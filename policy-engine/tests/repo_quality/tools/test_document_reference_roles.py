from __future__ import annotations

import gzip
import json
import subprocess
from pathlib import Path

import pytest

from tools.lib.document_references import reference_scan_text
from tools.quality.validation import check_docs_lifecycle as lifecycle

OLD_DASHBOARD = "frontend" + "/runtime-dashboard"
OLD_CLIENT = "frontend" + "/runtime-api-client"


def test_live_authored_scope_names_payloads_without_certifying_their_contents(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    _write(tmp_path, "docs/current.md", "The current guide uses maintained paths.\n")
    _write(tmp_path, "docs/research/topic/owned.py", "SOURCE = 'src/current.py'\n")
    _write(tmp_path, "tests/unit/test_old_paths.py", f"RECORDED = '{OLD_CLIENT}'\n")
    _write(tmp_path, "docs/research/e02/results/received.txt", OLD_CLIENT)
    archive = tmp_path / "vendor" / "source.whl"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(gzip.compress(OLD_CLIENT.encode()))
    _git(tmp_path, "add", ".")
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(
        tmp_path, receipt=receipt, reference_scope="live-authored"
    )

    assert findings == []
    assert receipt["scope"] == "live-authored-removed-stub-reference-scan-only"
    assert receipt["reference_scan_status"] == "complete"
    assert receipt["denominator"]["tracked_path_count"] == 5
    assert receipt["denominator"]["selected_path_count"] == 2
    assert receipt["outside_authored_claim_path_count"] == 3
    assert receipt["file_type_counts"][".py"] == {
        "tracked": 2,
        "selected": 1,
        "outside_authored_claim": 1,
    }
    assert sum(receipt["path_role_counts"].values()) == 5
    assert receipt["receipt_coverage"] == "partial"
    assert "No absence claim" in receipt["measured_property"]
    assert {operation["path"] for operation in receipt["read_evidence"]["operations"]} == {
        "docs/current.md",
        "docs/research/topic/owned.py",
    }
    exhaustive_receipt: dict[str, object] = {}
    exhaustive = lifecycle.check_removed_stub_references(tmp_path, receipt=exhaustive_receipt)
    assert exhaustive_receipt["reference_scope"] == "exhaustive"
    assert exhaustive_receipt["reference_scan_status"] == "partial"
    assert any(finding.check == "reference_scan_unresolved" for finding in exhaustive)
    assert any(finding.check == "removed_stub_reference" for finding in exhaustive)


@pytest.mark.parametrize(
    "relative",
    [
        "docs/current.md",
        "src/current.py",
        "apps/page.ts",
        "architecture/config.json",
        "architecture/config.toml",
        "tools/current.sh",
        "docs/research/topic/owned.py",
        "apps/runtime-dashboard/src/features/runs/page.tsx",
        "src/worker/runs/context.py",
        "tools/owned/production_data/config.toml",
        "tests/fixtures/README.md",
        "tests/fixtures/production_data/README.md",
    ],
)
def test_live_authored_scope_keeps_real_document_and_code_path_failures(
    tmp_path: Path, relative: str
) -> None:
    text = json.dumps({"path": OLD_CLIENT}) if relative.endswith(".json") else OLD_CLIENT
    _write(tmp_path, relative, text)
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(
        tmp_path, receipt=receipt, reference_scope="live-authored"
    )

    assert [(finding.check, finding.path) for finding in findings] == [
        ("removed_stub_reference", relative)
    ]
    assert receipt["selected_reference_scan_complete"] is True


@pytest.mark.parametrize(
    ("relative", "payload"),
    [
        ("docs/current.md", gzip.compress(b"opaque document")),
        ("architecture/current.json", b"{not JSON"),
        ("tools/current.py", b"invalid UTF8: \xff"),
        ("docs/current.md", b"UTF8-decodable binary: \x00"),
        ("tools/current.py", b"UTF8-decodable control: \x01"),
    ],
)
def test_live_authored_scope_does_not_green_unreadable_selected_inputs(
    tmp_path: Path, relative: str, payload: bytes
) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(
        tmp_path, receipt=receipt, reference_scope="live-authored"
    )

    assert receipt["reference_scan_status"] == "partial"
    assert receipt["selected_reference_scan_complete"] is False
    assert {finding.check for finding in findings} <= {
        "reference_scan_unresolved",
        "reference_scan_ambiguous",
    }
    assert findings


def test_live_authored_scope_checks_removed_directories_even_in_payloads(tmp_path: Path) -> None:
    removed = "/".join(("tests", "architecture"))
    target = tmp_path / removed / "production_data" / "retained.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\xff")

    findings = lifecycle.check_removed_stub_references(tmp_path, reference_scope="live-authored")

    assert ("removed_stub_path", removed) in {(finding.check, finding.path) for finding in findings}


def test_docs_gate_explicitly_selects_live_authored_reference_contract() -> None:
    from tools.quality.validation.check_docs_gate import GATE_COMMANDS

    assert GATE_COMMANDS["docs_lifecycle"].argv[-2:] == ("--reference-scope", "live-authored")
    assert lifecycle._build_parser().parse_args([]).reference_scope == "exhaustive"


@pytest.mark.parametrize(
    ("relative", "role"),
    [
        ("apps/feature/runs/node_modules/vendor.js", "dependency-or-environment:node_modules"),
        ("apps/feature/runs/.polisyos/config.toml", "dependency-or-environment:.polisyos"),
        ("apps/feature/runs/package-lock.json", "filename:package-lock.json"),
        ("apps/feature/runs/pnpm-lock.yaml", "filename:pnpm-lock.yaml"),
    ],
)
def test_live_authored_maintained_root_does_not_admit_nested_dependencies(
    tmp_path: Path, relative: str, role: str
) -> None:
    _write(tmp_path, relative, OLD_CLIENT)
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(
        tmp_path, receipt=receipt, reference_scope="live-authored"
    )

    assert findings == []
    assert receipt["denominator"]["tracked_path_count"] == 1
    assert receipt["denominator"]["selected_path_count"] == 0
    assert receipt["outside_authored_claim_path_count"] == 1
    assert receipt["path_role_counts"][f"outside-live-authored:{role}"] == 1


@pytest.mark.parametrize("declared_historical_role", [True, False])
def test_live_authored_scope_discloses_editorial_historical_role_boundary(
    tmp_path: Path, declared_historical_role: bool
) -> None:
    relative = "docs/research/topic/audits/record.md"
    header = "---\nkind: research-audit\nresearch_only: true\n"
    if declared_historical_role:
        header += (
            f"historical_repository_commit: {'a' * 40}\ncurrent_repository_commit: {'b' * 40}\n"
        )
    _write(tmp_path, relative, header + f"---\nRecorded reference: {OLD_CLIENT}\n")
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(
        tmp_path, receipt=receipt, reference_scope="live-authored"
    )

    assert receipt["denominator"]["selected_path_count"] == 1
    assert (
        "after the declared documentary-reference role projection" in receipt["measured_property"]
    )
    assert any("not content-bound proof" in item for item in receipt["unresolved_by_construction"])
    assert bool(findings) is not declared_historical_role
    if findings:
        assert [(finding.check, finding.path) for finding in findings] == [
            ("removed_stub_reference", relative)
        ]


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


def test_archive_table_pipe_inside_code_span_does_not_shift_live_reference_role(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    relative = "docs/reference/archive-ledger.md"
    _write(
        tmp_path,
        relative,
        "| Item / archive evidence | Live consumer |\n"
        "| --- | --- |\n"
        f"| `archive | {OLD_DASHBOARD}/archive.ts` | current consumer |\n",
    )
    _git(tmp_path, "add", ".")

    findings = lifecycle.check_removed_stub_references(tmp_path)

    assert findings == []


def test_utf8_text_with_binary_like_suffix_still_enters_reference_scan(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    relative = "docs/evidence.blob"
    _write(tmp_path, relative, f"Recorded source: {OLD_CLIENT}\n")
    _git(tmp_path, "add", ".")

    findings = lifecycle.check_removed_stub_references(tmp_path)

    assert [(finding.check, finding.path) for finding in findings] == [
        ("removed_stub_reference", relative)
    ]


def test_reference_scan_receipt_preserves_opaque_and_selector_boundaries(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    live = "docs/current.md"
    opaque = "docs/evidence.gz"
    malformed = "docs/unknown.bin"
    excluded = "production_data/source.md"
    _write(tmp_path, live, f"Current reference: {OLD_CLIENT}\n")
    (tmp_path / opaque).write_bytes(gzip.compress(OLD_DASHBOARD.encode("utf-8")))
    (tmp_path / malformed).write_bytes(b"not text: \xff")
    _write(tmp_path, excluded, f"Excluded source: {OLD_DASHBOARD}\n")
    _git(tmp_path, "add", ".")
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(tmp_path, receipt=receipt)

    assert {(finding.check, finding.path) for finding in findings} == {
        ("removed_stub_reference", live),
        ("reference_scan_unresolved", opaque),
        ("reference_scan_ambiguous", malformed),
        ("reference_scan_unresolved", excluded),
    }
    assert receipt["scope"] == "removed-stub-reference-scan-only"
    assert receipt["receipt_coverage"] == "partial"
    assert receipt["reference_scan_status"] == "partial"
    assert receipt["selected_reference_scan_complete"] is False
    denominator = receipt["denominator"]
    assert denominator["tracked_path_count"] == 4
    assert denominator["selected_path_count"] == 3
    assert denominator["excluded_path_count"] == 1
    assert receipt["opaque_formats"] == {"gzip": 1}
    assert receipt["opaque_reference_status"] == "byte-read-but-not-decoded"
    assert receipt["ambiguous_input_count"] == 1
    assert receipt["excluded_inputs"] == {"production_data": [excluded]}
    operations = receipt["read_evidence"]["operations"]
    assert {operation["path"] for operation in operations} == {live, opaque, malformed}
    assert len(operations) == 3
    by_path = {operation["path"]: operation for operation in operations}
    for path in (live, opaque, malformed):
        assert by_path[path]["status"] == "read"
        assert len(by_path[path]["sha256"]) == 64


def test_removed_stub_presence_uses_tracked_paths_outside_text_selector(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    relative = "tests/architecture/production_data/retained.gz"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(gzip.compress(b"retained opaque artifact"))
    _git(tmp_path, "add", ".")
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(tmp_path, receipt=receipt)

    assert ("removed_stub_path", "tests/architecture") in {
        (finding.check, finding.path) for finding in findings
    }
    assert ("removed_stub_reference", relative) in {
        (finding.check, finding.path) for finding in findings
    }
    assert ("reference_scan_unresolved", relative) in {
        (finding.check, finding.path) for finding in findings
    }
    assert relative in receipt["excluded_inputs"]["production_data"]
    assert (
        receipt["selector_exclusions"]["production_data"]["read_status"] == "not-read-by-selector"
    )
    assert relative not in {
        operation["path"] for operation in receipt["read_evidence"]["operations"]
    }
    assert receipt["opaque_formats"] == {}
    assert receipt["opaque_reference_status"] == "none"


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
        pytest.param(
            "docs/live.md",
            f"Read `{OLD_DASHBOARD}/archive.zip::member.md`.",
            id="live_archive_container",
        ),
        pytest.param(
            "architecture/live.json",
            json.dumps({"ref": f"{OLD_DASHBOARD}/archive.zip::member.md"}),
            id="live_archive_container_json",
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


def test_reference_scan_facade_preserves_injected_enumerator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = _write(tmp_path, "docs/selected.md", f"Current: {OLD_CLIENT}\n")
    _write(tmp_path, "docs/unselected.md", f"Not in this input set: {OLD_DASHBOARD}\n")

    def selected_paths(_repo_root: Path) -> tuple[Path, ...]:
        return (selected,)

    monkeypatch.setattr(lifecycle, "_iter_repository_files", selected_paths)
    receipt: dict[str, object] = {}

    findings = lifecycle.check_removed_stub_references(tmp_path, receipt=receipt)

    assert [(finding.check, finding.path) for finding in findings] == [
        ("removed_stub_reference", "docs/selected.md")
    ]
    denominator = receipt["denominator"]
    assert denominator["tracked_path_count"] == 1
    assert denominator["selected_path_count"] == 1


def test_station_debris_cannot_enter_committed_reference_or_plan_denominator(
    tmp_path: Path,
) -> None:
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
    receipt: dict[str, object] = {}
    findings = lifecycle.check_removed_stub_references(tmp_path, receipt=receipt)
    assert [(finding.check, finding.path) for finding in findings] == [
        ("reference_scan_ambiguous", "docs/input.json")
    ]
    operation = receipt["read_evidence"]["operations"][0]
    if damage == "missing":
        assert operation["status"] == "unreadable"
        assert operation["error"] == "FileNotFoundError"
    else:
        assert operation["status"] == "read"
        assert len(operation["sha256"]) == 64


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


@pytest.mark.parametrize("text", ["", "{bad"], ids=["empty", "malformed"])
def test_empty_or_malformed_evidence_json_is_ambiguous_for_lifecycle(
    tmp_path: Path, text: str
) -> None:
    relative = "docs/superpowers/journals/new.json"
    _write(tmp_path, relative, text)
    assert [finding.check for finding in lifecycle.check_removed_stub_references(tmp_path)] == [
        "reference_scan_ambiguous"
    ]


@pytest.mark.parametrize("text", ["", " \t\r\n"], ids=["empty", "whitespace"])
def test_empty_json_reference_input_has_no_reference_text(text: str) -> None:
    assert reference_scan_text(Path("architecture/capture.json"), text) == ""


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
    assert lifecycle.main(["--repo-root", str(tmp_path)]) == 2


def test_archive_map_keeps_member_paths_when_its_denominator_is_unestablished(
    tmp_path: Path,
) -> None:
    payload = _archive_map()
    payload["archive_non_directory_members"] = 2
    relative = "architecture/incomplete-map.json"
    _write(tmp_path, relative, json.dumps(payload))

    findings = lifecycle.check_removed_stub_references(tmp_path, receipt={})

    assert {(finding.check, finding.path) for finding in findings} == {
        ("removed_stub_reference", relative),
    }
    assert OLD_DASHBOARD in findings[0].message


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
