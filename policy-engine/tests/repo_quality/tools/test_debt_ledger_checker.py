"""Behavioral tests for the published-denominator debt-ledger checker."""

from __future__ import annotations

import importlib.util
import json
import re
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

    # register=closed against source=open is terminal vs non-terminal — a real
    # contradiction, so it must surface as a conflict and not as compatibility.
    assert "source_status_conflict" in _codes(checker, repo)


def test_write_projects_source_only_open_debts_but_not_reconciled_closures(
    tmp_path: Path,
) -> None:
    checker = _checker()
    gy = """# GY
- **GY-GAP3 — source-only debt.**

  **STANDING RECORDED (fixture): open.**
"""
    repo = _fixture(
        tmp_path,
        a_rows="",
        atlas_debt_rows="| Atlas source-only debt | measured | team | open |",
        gy=gy,
        ledger=_ledger(),
    )

    assert checker.main(["--write", "--report-only", "--repo-root", str(repo)]) == 0
    written = (repo / "docs/plans/active/LEDGER.md").read_text()

    assert "`GY-GAP3`" in written
    assert "`atlas-source-only-debt`" in written
    assert "GY-engine-subordination.md#" in written
    assert "POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md#per-slice-detail" in written


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


def test_nonancestor_closure_commit_is_checked_in_gy_and_atlas(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, a_rows="", ledger=_ledger())
    _git(repo, "switch", "-c", "side")
    _git(repo, "commit", "--allow-empty", "-m", "secondary closure")
    side_commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "main")
    gy = repo / "docs/plans/active/layer3-slices/GY-engine-subordination.md"
    gy.write_text(
        "# GY\n- **GY-DEF1 — closed elsewhere.**\n\n"
        f"  **STANDING RECORDED (fixture at {side_commit}): closed.**\n"
    )
    atlas = repo / "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md"
    atlas.write_text(
        atlas.read_text().replace(
            "| Debt | Measured | Owner | Closure expectation |\n| --- | --- | --- | --- |\n",
            "| Debt | Measured | Owner | Closure expectation |\n"
            "| --- | --- | --- | --- |\n"
            f"| ~~Atlas closed elsewhere~~ | measured | team | CLOSED ({side_commit}) |\n",
            1,
        )
    )

    details = [
        finding.detail
        for finding in checker.audit_repository(repo).findings
        if finding.code == "closure_commit_not_on_main"
    ]

    assert any(detail.startswith("GY:GY-DEF1:") for detail in details)
    assert any(detail.startswith("Atlas:atlas-closed-elsewhere:") for detail in details)


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


def test_falsifier_missing_basename_line_citation_is_rejected(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(
        tmp_path,
        ledger=_ledger(row=_debt_row(source="`missing.py:9`")),
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


def test_merged_slice_property_is_recognized_across_the_entire_row(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(
        tmp_path,
        atlas_slice_rows="| DS1 | MERGED delivery | evidence; merged `HEAD`; verified | A |",
    )

    report = checker.audit_repository(repo)

    assert "merged_slice_not_closed" in {finding.code for finding in report.findings}
    assert checker._snapshot(repo).work[0].stage == "merged"


def test_slice_state_distinguishes_closure_from_partial_merge_prose(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(
        tmp_path,
        atlas_slice_rows=(
            "| DS1 | Theme CLOSED and MERGED | completed | A |\n"
            "| DS2 | Authority half merged / successor planned | evidence | A |"
        ),
    )

    report = checker.audit_repository(repo)
    work = {row.slice_id: row.stage for row in checker._snapshot(repo).work}

    assert "merged_slice_not_closed" not in {finding.code for finding in report.findings}
    assert "DS1" not in work
    assert work["DS2"] == "named"


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


def test_discovered_slice_plan_overrides_static_unblocked_fallback(tmp_path: Path) -> None:
    """A real attached plan must supersede the old planless posture."""
    checker = _checker()
    repo = _fixture(
        tmp_path,
        atlas_slice_rows="| DS9 | Human Decision Integrity | none | active |",
        plans={
            "docs/plans/active/atlas-slices/DS9-human-decision-integrity.md": """---
status: execution_authorized_in_progress
branch: codex/ds9-fixture
---

# DS9
"""
        },
    )

    rendered = checker.render_ledger(checker._snapshot(repo))
    ds9 = next(line for line in rendered.splitlines() if "| `DS9` |" in line)

    assert "| `in-flight` |" in ds9
    assert "attached branch declared by slice plan" in ds9
    assert "codex/ds9-fixture" in ds9
    assert "no plan file in either plan root" not in ds9


def test_real_census_replays_published_invariants() -> None:
    checker = _checker()
    report = checker.audit_repository(REPO_ROOT)
    metrics = report.metrics

    assert metrics["register_ids"] == 76
    assert metrics["gy_ids"] == 38
    assert metrics["atlas_debt_rows"] == 22
    assert metrics["frontend_disposition_rows"] == 217
    assert metrics["gy_history_blocks"] == 6
    assert metrics["gy_absent_from_register"] == 15
    assert metrics["gy_absent_from_register_closed"] == 15
    assert metrics["ds5_nonclosure_rows"] == 27
    assert metrics["ds5_planless_routes"] == 6
    assert metrics["irregular_section_e_branch_rows"] == 1
    # The Atlas mismatch this once pinned (published 13, observed 22) was the census
    # error itself and is repaired. Pin the exact live class set instead: any change —
    # a new class, or one of these resolving — must be acknowledged here, not absorbed.
    assert {item.code for item in report.findings} == {
        "register_supplies_missing_standing",
        "register_withholds_source_standing",
    }
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
    # Line numbers are NAVIGATION, never a binding: `DS5-LINE-ADDRESS-01` ratified that a
    # gate must not fail because a line moved. Inserting §8.5 shifted this file by ~70 lines
    # and broke the old absolute pins. Bind the properties that matter — the status and that
    # a line was resolved at all — and let the address be advisory.
    for ambiguous_id in ("GY-DEFC-1", "GY-DEF22"):
        assert rows[ambiguous_id].status == "ambiguous"
        assert rows[ambiguous_id].line > 0
    # GY-DEF23 and GY-GAP8 landed on main with Cluster 1 (911657027); both parse as
    # `ambiguous` because the GY plan states their standing in prose the six recognised
    # forms do not cover. Merging registered them; it did not close them.
    assert Counter(row.status for row in rows.values()) == {
        "closed": 26,
        "ambiguous": 9,
        "open": 1,
        "blocked_on_product_decision": 1,
        "prose_only": 1,
    }


def test_gy_parser_lets_the_last_unknown_candidate_win_and_parses_status_generically() -> None:
    checker = _checker()
    unknown_last = """# GY
- **GY-GAP3 — witness.**

  **STANDING RECORDED (fixture): open.**

  **Standing: unknown.**
"""
    defect_open = """# GY
- **GY-GAP3 — witness.**

  `defect_standing` = `open`
"""

    unknown = checker._parse_gy(unknown_last)[0]
    defect = checker._parse_gy(defect_open)[0]

    assert unknown.status == "ambiguous" and unknown.line == 6
    assert defect.status == "open"


def test_gy_parser_uses_exact_status_tokens_and_ignores_explanatory_mentions() -> None:
    checker = _checker()
    text = """# GY
- **GY-GAP3 — blocked.**

  **STANDING RECORDED (fixture): blocked.**

  Explanatory prose mentions `defect_standing` after the final standing.
- **GY-GAP4 — unmerged.**

  **STANDING RECORDED (fixture): open_unmerged.**
- **GY-GAP5 — foreign.**

  **STANDING RECORDED (fixture): foreign.**
- **GY-GAP6 — folded.**

  **STANDING RECORDED (fixture): folded.**
"""

    rows = {row.debt_id: row for row in checker._parse_gy(text)}

    assert rows["GY-GAP3"].status == "blocked"
    assert rows["GY-GAP4"].status == "open_unmerged"
    assert rows["GY-GAP5"].status == "foreign"
    assert rows["GY-GAP6"].status == "folded"


def test_real_ledger_exposes_every_gy_block_receipt_and_typed_state() -> None:
    checker = _checker()
    snapshot = checker._snapshot(REPO_ROOT)
    rendered = checker.render_ledger(snapshot)

    for row in snapshot.gy:
        assert f"`{row.debt_id}`={row.hit_count}@{row.line}" in rendered

    expected_states = {
        "GY-PA1": "producer_missing",
        "GY-GAP3": "absent/unallocated",
        "GY-GAP5": "absent/unallocated",
        "GY-DEF23": "producer_missing",
        "GY-GAP8": "implemented_but_not_orchestrated",
    }
    for debt_id, state in expected_states.items():
        row = next(line for line in rendered.splitlines() if f"[`{debt_id}`]" in line)
        assert f"`{state}`" in row
    gap3 = next(line for line in rendered.splitlines() if "[`GY-GAP3`]" in line)
    gap8 = next(line for line in rendered.splitlines() if "[`GY-GAP8`]" in line)
    assert "contract_only" not in gap3
    assert "bridge_missing" not in gap8
    assert "| `DEBT-REGISTER.md` | 76 | 76 | 52 |" in rendered
    assert "| Atlas master debt table | 22 | 22 | 9 |" in rendered


def test_real_register_contains_the_ratified_import_policy_class_rows() -> None:
    checker = _checker()
    snapshot = checker._snapshot(REPO_ROOT)
    registered = {row.debt_id for row in snapshot.debts}

    assert {
        "import-policy-relocate-data-forge-to-lex",
        "import-policy-relocate-ir-to-foundry",
        "import-policy-relocate-data-forge-to-foundry",
        "import-policy-relocate-ir-to-scientist",
        "import-policy-relocate-data-forge-to-scientist",
        "import-policy-relocate-foundry-to-scientist",
        "import-policy-relocate-lex-to-scientist",
        "import-policy-relocate-core-to-scientist",
        "import-policy-relocate-lex-to-foundry",
        "import-policy-relocate-ir-to-core",
        "import-policy-relocate-foundry-to-lex",
        "import-policy-relocate-ir-to-jax",
        "import-policy-ratify-candidates",
        "import-policy-governance-fabric-world-surface",
        "import-policy-governance-runtime-corpus-dependency",
        "import-policy-governance-runtime-pdc-search-iteration",
    } <= registered


def test_capability_states_require_evidence_scoped_to_the_debt_subject() -> None:
    checker = _checker()
    rendered = checker.render_ledger(checker._snapshot(REPO_ROOT))

    decision = next(
        line for line in rendered.splitlines() if "[`ds4-waist-decision-grade`]" in line
    )
    unavailable = next(
        line for line in rendered.splitlines() if "[`three-unavailable-governed-producers`]" in line
    )
    atlas = next(
        line
        for line in rendered.splitlines()
        if "[`ds4-three-canonical-waist-vocabularies`]" in line
    )

    assert "`not_established`" in decision and "producer_missing" not in decision
    assert "`not_established`" in unavailable and "artifact_missing" not in unavailable
    assert "`not_established`" in atlas and "producer_missing" not in atlas
    assert "#per-slice-detail" in atlas


def test_open_work_records_property_posture_and_branch_relevance() -> None:
    checker = _checker()
    rendered = checker.render_ledger(checker._snapshot(REPO_ROOT))

    # DS9 merged 2026-08-25 (`fd243d1ad`) and its master-plan row carries `CLOSED`,
    # so it must leave Table A entirely. Table A answers "what is open"; a closed
    # slice lingering there is loss mode 5, the class the ledger exists to catch.
    assert not [line for line in rendered.splitlines() if "| `DS9` |" in line]

    for slice_id in ("DS10", "DS12", "DS14", "DS15", "DS17"):
        row = next(line for line in rendered.splitlines() if f"| `{slice_id}` |" in line)
        assert "unblocking property `not_established`" in row
        assert "measured 2026-08-22" in row
        assert "no plan file in either plan root" in row
    ds16 = next(line for line in rendered.splitlines() if "| `DS16` |" in line)
    assert '"a surface exists that renders values rather than refusals"' in ds16
    assert "codex/atlas-ds16-value-grammar" not in ds16
    landed = next(line for line in rendered.splitlines() if "[`GY-DEF23`]" in line)
    assert "| `open` |" in landed


def test_ds9_claims_and_splits_only_approved_debt_scope() -> None:
    checker = _checker()
    rows = {row.debt_id: row for row in checker._snapshot(REPO_ROOT).debts}

    approval = rows["ds8-approval-authority"]
    assert approval.section == "A"
    assert approval.status == "closed"
    assert approval.owner == "DS9"

    notes = rows["ds8-local-reviewer-note-persistence"]
    assert notes.section == "B"
    assert notes.status == "open"
    assert notes.owner == "absent/unallocated"

    public = rows["ds8-signed-public-decision-surface"]
    assert public.section == "B"
    assert public.status == "open"
    assert public.owner == "absent/unallocated"

    assert "DS20-B scorecard producer provenance" not in rows
    intake = rows["DS20-B-scorecard-provenance-intake-effect"]
    assert intake.section == "A"
    assert intake.status == "closed"
    assert intake.owner == "DS9"
    trust = rows["DS20-B-scorecard-provenance-producer-trust"]
    assert trust.section == "D"
    assert trust.status == "foreign"
    assert trust.owner == "ops config"

    concurrency = rows["decision-validity-fixed-temp-concurrency"]
    assert concurrency.section == "C"
    assert concurrency.status == "open_unmerged"
    assert concurrency.owner == "Scientist Decision Validity / GY-N12 Cluster 4 Task 4.4"

    dashboard_import = rows["case-workspace-route-bypasses-feature-barrel"]
    assert dashboard_import.section == "C"
    assert dashboard_import.status == "open_unmerged"
    assert dashboard_import.owner == "team-frontend"

    rendered = checker.render_ledger(checker._snapshot(REPO_ROOT))
    assert "[`ds8-approval-authority`]" not in rendered
    assert "[`DS20-B-scorecard-provenance-intake-effect`]" not in rendered
    assert "[`decision-validity-fixed-temp-concurrency`]" in rendered
    assert "[`case-workspace-route-bypasses-feature-barrel`]" in rendered


def test_reconciled_secondary_closures_are_not_reported_as_missing() -> None:
    checker = _checker()
    report = checker.audit_repository(REPO_ROOT)

    missing = [item.detail for item in report.findings if item.code == "ledger_missing_source_id"]

    assert "GY:GY-DEF15" not in missing
    assert "GY:GY-DEF19" not in missing
    assert "GY:GY-DEFC-1" not in missing
    assert "Atlas:producer-availability-denominator" not in missing
    assert "Atlas:run-lifecycle-terminal-fact" not in missing


def test_report_only_preserves_findings_but_returns_zero(tmp_path: Path, capsys: object) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, ledger=_ledger())

    assert checker.main(["--check", "--repo-root", str(repo)]) == 1
    assert checker.main(["--check", "--report-only", "--repo-root", str(repo)]) == 0
    assert "register_denominator_mismatch" in capsys.readouterr().out


def test_write_regenerates_then_reads_back(tmp_path: Path) -> None:
    checker = _checker()
    repo = _fixture(tmp_path, ledger=_ledger())

    assert checker.main(["--write", "--report-only", "--repo-root", str(repo)]) == 0
    assert (repo / "docs/plans/active/LEDGER.md").read_text() == checker.audit_repository(
        repo
    ).ledger_text


def test_real_ledger_is_the_deterministic_rendering() -> None:
    checker = _checker()
    report = checker.audit_repository(REPO_ROOT)

    assert (REPO_ROOT / "docs/plans/active/LEDGER.md").read_text() == report.ledger_text


def test_checker_remains_a_reconciler_and_never_an_execution_harness() -> None:
    """Guard the property the line cap was a proxy for.

    The cap moved three times in one day — 600 -> 650 for a semantic repair, -> 800 once the
    file turned out never to have been `ruff format`-clean (633 unformatted, 784 formatted),
    and a GY task parser then pushed it again. Twice it moved for reasons that had nothing to
    do with the code growing, which is the signature of a proxy measuring the wrong thing
    (`P38`).

    What actually needs guarding is what GY-N12's bootstrap became: a checker that policed
    execution — held locks, wrote governed artifacts, gated merges, needed a trust root of its
    own. These assertions bound that directly. A line ceiling is kept only as a coarse smoke
    signal, deliberately loose, and is no longer the gate.
    """
    source = CHECKER_PATH.read_text()

    writes = re.findall(
        r"\b(atomic_write_text|write_text|write_bytes|mkdir|unlink|rename)\(", source
    )
    assert writes == ["atomic_write_text"], f"exactly one write primitive expected, found {writes}"
    assert source.count("atomic_write_text(") == 1, "the single write site must stay single"
    assert "LEDGER_PATH" in source.split("atomic_write_text(")[1][:120], (
        "the one write must target the generated ledger and nothing else"
    )

    assert not re.search(r"\b(flock|lockf|FileLock|acquire_lock|index\.lock)\b", source), (
        "a reconciler holds no lock; holding one makes it an execution gate"
    )

    for call in re.findall(r"subprocess\.\w+\(\s*\[([^\]]*)\]", source, re.S):
        assert '"git"' in call, f"subprocess is for reading git only, got: {call[:60]}"
        assert not re.search(r'"(commit|push|merge|checkout|reset|update-ref)"', call), (
            f"git must be read-only here, got: {call[:60]}"
        )

    assert len(source.splitlines()) <= 1000, "coarse smoke signal only, not the gate"


def test_debt_register_publishes_both_lifecycle_tables() -> None:
    register = (REPO_ROOT / "docs/plans/active/DEBT-REGISTER.md").read_text()

    assert "### Task lifecycle" in register
    assert (
        "named → planned → unblocked → in-flight → handed-back → verified → merged → closed"
        in register
    )
    assert "### Debt lifecycle" in register
    assert "observed → registered → owned → executable → closed" in register
