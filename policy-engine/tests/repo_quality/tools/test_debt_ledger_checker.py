"""Behavioral tests for the published-denominator debt-ledger checker."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKER_PATH = REPO_ROOT / "tools/quality/validation/check_debt_ledger.py"


def _checker() -> ModuleType:
    assert CHECKER_PATH.is_file(), "checker must exist before its behavior can be tested"
    spec = importlib.util.spec_from_file_location("check_debt_ledger", CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_checker_exposes_repository_audit() -> None:
    checker = _checker()

    assert callable(checker.audit_repository)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _ledger(*, row: str | None = None, extra: str = "") -> str:
    rows = "" if row is None else f"{row}\n"
    return f"""# PolicyOS Open Work and Debt Ledger

## Table A — open work

| id | stage | basis | source | branch |
| --- | --- | --- | --- | --- |

## Table B — open debts

| id | status | owner | source | branch |
| --- | --- | --- | --- | --- |
{rows}{extra}
## Denominators
"""


def _debt_row(
    debt_id: str = "open-debt",
    *,
    status: str = "open",
    owner: str = "team-runtime",
    source: str = "[register](DEBT-REGISTER.md#a-open-and-executable-now)",
) -> str:
    return f"| [`{debt_id}`](DEBT-REGISTER.md#a-open-and-executable-now) | `{status}` | {owner} | {source} | — |"


def _fixture(
    tmp_path: Path,
    *,
    a_rows: str = "| `open-debt` | subject | team-runtime | `open` | predicate |",
    g_rows: str = "",
    atlas_slice_rows: str = "",
    atlas_debt_rows: str = "",
    gy: str = "# GY plan\n",
    ledger: str | None = None,
    plans: dict[str, str] | None = None,
) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs/plans/active/layer3-slices").mkdir(parents=True)
    (repo / "docs/plans/active/atlas-slices").mkdir(parents=True)
    (repo / "docs/superpowers/plans").mkdir(parents=True)
    (repo / "architecture/atlas_surfaces").mkdir(parents=True)
    register = f"""# PolicyOS Debt Register

## A. Open and executable now

| id | subject | owner | status | closure signal |
| --- | --- | --- | --- | --- |
{a_rows}

## G. Closed

| id | status | evidence |
| --- | --- | --- |
{g_rows}
"""
    (repo / "docs/plans/active/DEBT-REGISTER.md").write_text(register)
    (repo / "docs/plans/active/layer3-slices/GY-engine-subordination.md").write_text(gy)
    atlas = f"""# Atlas plan

## Slice Sequence (overview)

| Slice | Theme | Gate / prereqs | Phase |
| --- | --- | --- | --- |
{atlas_slice_rows}

## Per-Slice Detail

**Inherited baseline debt of record (measured).**

| Debt | Measured | Owner | Closure expectation |
| --- | --- | --- | --- |
{atlas_debt_rows}
"""
    (repo / "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md").write_text(
        atlas
    )
    disposition = {"ds8_strangle_coverage": {"assignments": []}}
    (repo / "architecture/atlas_surfaces/frontend-disposition-register.json").write_text(
        json.dumps(disposition)
    )
    if ledger is None:
        ledger = _ledger(row=_debt_row())
    (repo / "docs/plans/active/LEDGER.md").write_text(ledger)
    for relative, text in (plans or {}).items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Ledger Test")
    _git(repo, "config", "user.email", "ledger@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo


def _codes(checker: ModuleType, repo: Path) -> set[str]:
    return {finding.code for finding in checker.audit_repository(repo).findings}


def test_falsifier_dropped_ledger_row_is_rejected(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, ledger=_ledger())

    assert "ledger_missing_id" in _codes(checker, repo)


def test_secondary_source_ids_and_statuses_are_reconciled(tmp_path: Path) -> None:
    checker = _checker()
    gy = """# GY
- **GY-GAP3 — source-only debt.**

  **STANDING RECORDED (fixture): open.**
"""
    repo = _fixture(tmp_path, a_rows="", ledger=_ledger(), gy=gy)

    assert "ledger_missing_source_id" in _codes(checker, repo)

    register = repo / "docs/plans/active/DEBT-REGISTER.md"
    register.write_text(
        register.read_text().replace(
            "| --- | --- | --- | --- | --- |\n\n",
            "| --- | --- | --- | --- | --- |\n| `GY-GAP3` | subject | team-runtime | `closed` | CLOSED by `HEAD` |\n\n",
            1,
        )
    )
    (repo / "docs/plans/active/LEDGER.md").write_text(_ledger())

    assert "source_status_disagreement" in _codes(checker, repo)


def test_falsifier_status_flip_is_rejected(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, ledger=_ledger(row=_debt_row(status="blocked")))

    assert "ledger_status_mismatch" in _codes(checker, repo)


def test_falsifier_nonancestor_closure_commit_is_rejected(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, a_rows="", ledger=_ledger())
    _git(repo, "switch", "-c", "side")
    _git(repo, "commit", "--allow-empty", "-m", "side-only closure")
    side_commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "main")
    register = repo / "docs/plans/active/DEBT-REGISTER.md"
    register.write_text(
        register.read_text().replace(
            "| --- | --- | --- |\n\n",
            f"| --- | --- | --- |\n| `closed-debt` | `closed` | CLOSED by `{side_commit}` |\n\n",
        )
    )

    assert "closure_commit_not_on_main" in _codes(checker, repo)


def test_falsifier_planless_slice_cannot_be_owner(tmp_path: Path) -> None:
    checker = _checker()
    source_row = "| `open-debt` | subject | DS9 | `open` | predicate |"
    repo = _fixture(
        tmp_path,
        a_rows=source_row,
        ledger=_ledger(row=_debt_row(owner="DS9")),
    )

    assert "planless_slice_named_owner" in _codes(checker, repo)


def test_falsifier_missing_file_line_citation_is_rejected(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(
        tmp_path,
        ledger=_ledger(row=_debt_row(source="`missing/source.py:9`")),
    )

    assert "ledger_file_reference_missing" in _codes(checker, repo)


def test_falsifier_id_in_open_and_closed_sections_is_rejected(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(
        tmp_path,
        g_rows="| `open-debt` | `closed` | CLOSED by `HEAD` |",
    )

    assert "closed_open_conflict" in _codes(checker, repo)


def test_falsifier_merged_slice_without_closed_marker_is_rejected(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(
        tmp_path,
        atlas_slice_rows="| DS1 | Theme | merged `HEAD` | A |",
    )

    assert "merged_slice_not_closed" in _codes(checker, repo)


def test_falsifier_declared_nonclosure_missing_from_ledger_is_rejected(
    tmp_path: Path,
) -> None:
    checker = _checker()
    repo = _fixture(
        tmp_path,
        plans={
            "docs/plans/active/atlas-slices/DS8-example.md": (
                "# DS8\n\n## Explicit non-closure\n\n- `declared-gap`\n"
            )
        },
    )

    assert "explicit_nonclosure_missing" in _codes(checker, repo)


def test_plan_search_includes_superpowers_directory(tmp_path: Path) -> None:
    checker = _checker()
    source_row = "| `open-debt` | subject | DS7 | `open` | predicate |"
    repo = _fixture(
        tmp_path,
        a_rows=source_row,
        ledger=_ledger(row=_debt_row(owner="DS7")),
        plans={"docs/superpowers/plans/2026-08-20-ds7-plan.md": "# DS7 plan\n"},
    )

    assert "planless_slice_named_owner" not in _codes(checker, repo)


def test_real_census_replays_published_invariants() -> None:
    checker = _checker()
    report = checker.audit_repository(REPO_ROOT)
    metrics = report.metrics

    assert metrics["register_ids"] == 54
    assert metrics["gy_ids"] == 36
    assert metrics["atlas_debt_rows"] == 22
    assert metrics["frontend_disposition_rows"] == 217
    assert metrics["gy_history_blocks"] == 6
    assert metrics["gy_absent_from_register"] == 15
    assert metrics["gy_absent_from_register_closed"] == 15
    assert metrics["ds5_nonclosure_rows"] == 27
    assert metrics["ds5_planless_routes"] == 11
    assert metrics["irregular_section_e_branch_rows"] == 1
    assert "atlas_denominator_mismatch" in {item.code for item in report.findings}
    atlas_ids = {row.debt_id for row in checker._snapshot(REPO_ROOT).atlas_debts}
    assert "ds4-three-canonical-waist-vocabularies" in atlas_ids
    assert "master_inherited_debt_action = flag_for_architect_insertion_at_c20" not in atlas_ids


def test_real_gy_parser_covers_all_six_forms_and_last_hit_wins() -> None:
    checker = _checker()
    text = (REPO_ROOT / "docs/plans/active/layer3-slices/GY-engine-subordination.md").read_text()
    rows = {row.debt_id: row for row in checker._parse_gy(text)}

    assert rows["GY-DEF1"].status == "closed" and rows["GY-DEF1"].hit_count == 2
    assert rows["GY-DEF5"].status == "closed"
    assert rows["GY-DEFC-3"].status == "closed"
    assert rows["GY-DEF13"].status == "closed"
    assert rows["GY-DEF10"].status == "closed"
    assert rows["GY-DEFC-1"].status == "ambiguous" and rows["GY-DEFC-1"].line == 3272
    assert rows["GY-DEF22"].status == "ambiguous" and rows["GY-DEF22"].line == 4141
    assert Counter(row.status for row in rows.values()) == {
        "closed": 26,
        "ambiguous": 7,
        "open": 1,
        "blocked_on_product_decision": 1,
        "prose_only": 1,
    }


def test_report_only_preserves_findings_but_returns_zero(
    tmp_path: Path, capsys: object
) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, ledger=_ledger())

    assert checker.main(["--check", "--repo-root", str(repo)]) == 1
    assert checker.main(["--check", "--report-only", "--repo-root", str(repo)]) == 0
    assert "register_denominator_mismatch" in capsys.readouterr().out


def test_write_regenerates_then_reads_back(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, ledger=_ledger())

    assert checker.main(["--write", "--report-only", "--repo-root", str(repo)]) == 0
    assert (repo / "docs/plans/active/LEDGER.md").read_text() == checker.audit_repository(repo).ledger_text


def test_real_ledger_is_the_deterministic_rendering() -> None:
    checker = _checker()
    report = checker.audit_repository(REPO_ROOT)

    assert (REPO_ROOT / "docs/plans/active/LEDGER.md").read_text() == report.ledger_text


def test_checker_stays_within_declared_size_cap() -> None:
    assert len(CHECKER_PATH.read_text().splitlines()) <= 600


def test_debt_register_publishes_both_lifecycle_tables() -> None:
    register = (REPO_ROOT / "docs/plans/active/DEBT-REGISTER.md").read_text()

    assert "### Task lifecycle" in register
    assert "named → planned → unblocked → in-flight → handed-back → verified → merged → closed" in register
    assert "### Debt lifecycle" in register
    assert "observed → registered → owned → executable → closed" in register
