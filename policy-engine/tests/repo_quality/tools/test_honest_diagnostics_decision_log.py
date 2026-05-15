from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DECISION_LOG = (
    REPO_ROOT
    / "docs"
    / "system-design-decisions"
    / "honest-diagnostics-substrate-decision-log.md"
)

REQUIRED_ENTRY_FIELDS = {
    "Date",
    "Context",
    "Decision",
    "Affected ADR",
    "Owner",
    "Reversibility",
    "Revisit trigger",
    "Revisit wave",
    "Promotion status",
}
CADENCE_TEMPLATE_FIELDS = REQUIRED_ENTRY_FIELDS | {"Affected invariant id or phase id"}
ALLOWED_REVERSIBILITY = {"reversible", "costly_to_reverse", "irreversible"}
REQUIRED_REVISIT_WAVES = {
    "evidence authority envelope serialization details": "after Wave 1",
    "event-log persistence boundary": "after Wave 2",
    "legacy evidence migration cutoff": "after Wave 4",
    "diagnostic SLO thresholds": "after Wave 4",
    "attestation coverage expansion": "after Wave 5",
    "CI tier budgets": "after Wave 5",
}
SOURCE_OPEN_QUESTIONS = (
    "Which substrate record becomes the primary CAS object for each run",
    "Should provenance vocabulary be one global enum",
    "Which blockers are categorically non-overridable",
    "Should dashboard projection source labels be part of the runtime API",
    "How much historical bundle evidence should be migrated",
    "Which ADRs should this design split into after review",
    "Which diagnostic SLIs are strong enough to quarantine production closeout",
    "Which evidence events must be never-sampled for serious runs",
    "Which semantic binding failures are non-overridable",
    "How should claim-argument-evidence cases be represented in CAS",
)


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _decision_log_text() -> str:
    return DECISION_LOG.read_text(encoding="utf-8")


def _entry_blocks(source: str) -> dict[str, dict[str, str]]:
    entries_source = source.split("\n## Entries\n", maxsplit=1)[1]
    blocks = re.finditer(
        r"^### (?P<title>DL-HDS-\d{4} - .+?)\n(?P<body>.*?)(?=^### DL-HDS-\d{4} - |\Z)",
        entries_source,
        flags=re.MULTILINE | re.DOTALL,
    )
    parsed: dict[str, dict[str, str]] = {}
    for block in blocks:
        fields = dict(
            re.findall(r"^- \*\*(?P<field>[^*]+)\*\*: (?P<value>.+)$", block.group("body"), re.M)
        )
        parsed[block.group("title")] = fields
    return parsed


def test_honest_diagnostics_decision_log_template_matches_cadence_fields() -> None:
    source = _decision_log_text()
    template_source = source.split("\n## Entries\n", maxsplit=1)[0]

    for field in CADENCE_TEMPLATE_FIELDS:
        _check(f"- **{field}**:" in template_source, field)


def test_honest_diagnostics_decision_log_imports_source_open_questions() -> None:
    source = _decision_log_text()

    for question in SOURCE_OPEN_QUESTIONS:
        _check(question in source, question)


def test_honest_diagnostics_decision_log_entries_have_required_fields() -> None:
    entries = _entry_blocks(_decision_log_text())

    _check(bool(entries), "decision log has no parsed entries")
    for title, fields in entries.items():
        _check(fields.keys() >= REQUIRED_ENTRY_FIELDS, title)
        _check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields["Date"]) is not None, title)
        _check("ADR-01" in fields["Affected ADR"], title)
        _check(fields["Reversibility"] in ALLOWED_REVERSIBILITY, title)
        for field in REQUIRED_ENTRY_FIELDS:
            _check(fields[field].strip() not in {"", "TBD", "TODO"}, f"{title}: {field}")


def test_honest_diagnostics_decision_log_open_questions_have_revisit_waves() -> None:
    entries = _entry_blocks(_decision_log_text())

    for question, revisit_wave in REQUIRED_REVISIT_WAVES.items():
        matching = [
            fields
            for title, fields in entries.items()
            if question in title or question in fields["Context"] or question in fields["Decision"]
        ]
        _check(bool(matching), question)
        _check({fields["Revisit wave"] for fields in matching} == {revisit_wave}, question)
