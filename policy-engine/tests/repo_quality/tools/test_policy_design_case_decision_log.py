# ruff: noqa: S101

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "docs"
    / "plans"
    / "archive"
    / "2026-05-19-policyos-policy-design-case-implementation-plan.md"
)
DECISION_LOG = (
    REPO_ROOT / "docs" / "system-design-decisions" / "policy-design-case-decision-log.md"
)

REQUIRED_ENTRY_FIELDS = {
    "Date",
    "Context",
    "Decision",
    "Affected ADR or SDD section",
    "Affected wave and phase",
    "Owner",
    "Reversibility",
    "Revisit trigger",
    "Revisit wave",
    "Promotion status",
}
ALLOWED_REVERSIBILITY = {"reversible", "costly_to_reverse", "irreversible"}
EXPECTED_ADRS = {f"ADR-01{number}" for number in range(56, 62)}
EXPECTED_SECOND_PACK_ADRS = {f"ADR-01{number}" for number in range(62, 66)}


def test_phase_1_4_decision_log_has_complete_entries() -> None:
    entries = _entry_blocks(_decision_log_text())

    assert entries, "Policy Design Case decision log must have parsed entries"
    for title, fields in entries.items():
        assert fields.keys() >= REQUIRED_ENTRY_FIELDS, title
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields["Date"]) is not None, title
        assert fields["Reversibility"] in ALLOWED_REVERSIBILITY, title
        for field in REQUIRED_ENTRY_FIELDS:
            assert fields[field].strip() not in {"", "TBD", "TODO"}, f"{title}: {field}"

    assert any(
        "temporary" in title.casefold() or "temporary" in fields["Context"].casefold()
        for title, fields in entries.items()
    ), "Phase 1.4 requires a temporary-exception entry when one is known"


def test_phase_1_4_decision_log_owns_every_target_contract() -> None:
    planned_contracts = _plan_target_contracts()
    logged_contracts = _decision_log_target_contracts()

    assert planned_contracts
    assert logged_contracts.keys() >= planned_contracts.keys()
    for row in logged_contracts.values():
        assert row["Primary owner"].strip("`")
        assert row["First revisit wave"]


def test_phase_1_4_decision_log_owns_every_adr_proof_obligation() -> None:
    rows = list(
        _markdown_table_rows(
            _decision_log_text(),
            "## ADR 0156-0161 Proof Obligation Ownership",
        ).values()
    )

    assert rows
    assert {row["Proof id"].split("-O", maxsplit=1)[0] for row in rows} == EXPECTED_ADRS
    for row in rows:
        assert row["Owner"].strip("`")
        assert row["Revisit wave"]


def test_wave_26_decision_log_owns_second_governance_adr_pack() -> None:
    rows = list(
        _markdown_table_rows(
            _decision_log_text(),
            "## ADR 0162-0165 Proof Obligation Ownership",
        ).values()
    )

    assert rows
    assert {row["Proof id"].split("-O", maxsplit=1)[0] for row in rows} == (
        EXPECTED_SECOND_PACK_ADRS
    )
    for row in rows:
        assert row["Owner"].strip("`")
        assert row["Revisit wave"]


def test_phase_1_4_decision_log_imports_open_questions_with_revisit_waves() -> None:
    rows = list(
        _markdown_table_rows(_decision_log_text(), "## Imported Source Open Questions").values()
    )

    assert len(rows) == 29
    assert {row["Source question"].split(".", maxsplit=1)[0] for row in rows} == {
        str(number) for number in range(1, 30)
    }
    for row in rows:
        assert row["Owner"].strip("`")
        assert row["Revisit wave"].startswith("after Wave ")


def _decision_log_text() -> str:
    return DECISION_LOG.read_text(encoding="utf-8")


def _entry_blocks(source: str) -> dict[str, dict[str, str]]:
    entries_source = source.split("\n## Entries\n", maxsplit=1)[1]
    blocks = re.finditer(
        r"^### (?P<title>DL-PDC-\d{4} - .+?)\n(?P<body>.*?)(?=^### DL-PDC-\d{4} - |\Z)",
        entries_source,
        flags=re.MULTILINE | re.DOTALL,
    )
    parsed: dict[str, dict[str, str]] = {}
    for block in blocks:
        parsed[block.group("title")] = dict(
            re.findall(
                r"^- \*\*(?P<field>[^*]+)\*\*: (?P<value>.+)$",
                block.group("body"),
                re.M,
            )
        )
    return parsed


def _plan_target_contracts() -> dict[str, dict[str, str]]:
    return _markdown_table_rows(PLAN.read_text(encoding="utf-8"), "## Target Contract Names")


def _decision_log_target_contracts() -> dict[str, dict[str, str]]:
    return _markdown_table_rows(_decision_log_text(), "## Target Contract Ownership Skeleton")


def _markdown_table_rows(source: str, heading: str) -> dict[str, dict[str, str]]:
    lines = source.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start is None:
        raise AssertionError(f"missing heading: {heading}")

    table_lines: list[str] = []
    for line in lines[start:]:
        if table_lines and not line.startswith("|"):
            break
        if line.startswith("|"):
            table_lines.append(line)
    if len(table_lines) < 3:
        raise AssertionError(f"missing table under heading: {heading}")

    header = [_clean_cell(cell) for cell in table_lines[0].strip("|").split("|")]
    rows: dict[str, dict[str, str]] = {}
    for line in table_lines[2:]:
        cells = [_clean_cell(cell) for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells, strict=True))
        rows[cells[0]] = row
    return rows


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("`", "").strip())
