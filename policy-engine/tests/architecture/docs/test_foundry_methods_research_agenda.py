from __future__ import annotations

import re
from pathlib import Path

AGENDA = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "archive"
    / "plans"
    / "FOUNDRY_METHODS_RESEARCH_AGENDA.md"
)


def _phase_section(markdown: str, phase: int) -> str:
    marker = f"## Phase {phase} "
    start = markdown.index(marker)
    next_match = re.search(r"\n## Phase \d+ ", markdown[start + 1 :])
    end = len(markdown) if next_match is None else start + 1 + next_match.start()
    return markdown[start:end]


def _declared_count(section: str) -> int:
    match = re.search(r"Parallel research problems \((\d+) concurrent\)", section)
    assert match is not None
    return int(match.group(1))


def test_phase1_and_phase4_declared_counts_match_task_lists() -> None:
    markdown = AGENDA.read_text(encoding="utf-8")

    phase1 = _phase_section(markdown, 1)
    phase4 = _phase_section(markdown, 4)

    assert _declared_count(phase1) == 13
    assert len(set(re.findall(r"`P1\.\d{2}`", phase1))) == 13
    assert _declared_count(phase4) == 14
    assert len(set(re.findall(r"`P4\.\d{2}`", phase4))) == 14
