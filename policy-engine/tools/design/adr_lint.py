"""Lint Wave 1 ADRs for status, template shape, and concrete impact."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"
CANONICAL_TEMPLATE = ADR_DIR / "_template.md"
WAVE1_ADRS = [
    ADR_DIR / "ADR-042-janus-atlas-dual-brand.md",
    ADR_DIR / "ADR-043-provenance-law.md",
    ADR_DIR / "ADR-044-time-as-primitive.md",
    ADR_DIR / "ADR-045-glyph-alphabet-limit-10.md",
    ADR_DIR / "ADR-046-authored-text-registry.md",
]
REQUIRED_HEADINGS = [
    "## Status",
    "## Date",
    "## Context",
    "## Decision",
    "## Consequences",
    "## Concrete impact",
    "## Related Decisions",
]
VALID_STATUSES = {"Proposed", "Approved", "Rejected", "Superseded"}


def _extract_section(text: str, heading: str) -> str | None:
    marker = f"{heading}\n"
    start = text.find(marker)
    if start == -1:
        return None
    start += len(marker)
    next_heading = text.find("\n## ", start)
    if next_heading == -1:
        return text[start:].strip()
    return text[start:next_heading].strip()


def main() -> int:
    failures: list[str] = []

    if not CANONICAL_TEMPLATE.exists():
        failures.append(f"Missing canonical ADR template: {CANONICAL_TEMPLATE}")

    for path in WAVE1_ADRS:
        if not path.exists():
            failures.append(f"Missing Wave 1 ADR: {path}")
            continue

        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED_HEADINGS:
            if heading not in text:
                failures.append(f"{path.name}: missing heading `{heading}`")

        status = _extract_section(text, "## Status")
        if status is None:
            continue
        status_line = status.splitlines()[0].strip()
        if status_line not in VALID_STATUSES:
            failures.append(
                f"{path.name}: invalid status `{status_line}`; expected one of "
                f"{', '.join(sorted(VALID_STATUSES))}"
            )
        elif status_line != "Approved":
            failures.append(f"{path.name}: Wave 1 ADRs must be `Approved`, found `{status_line}`")

        concrete_impact = _extract_section(text, "## Concrete impact")
        if concrete_impact is None or not concrete_impact.strip():
            failures.append(f"{path.name}: `## Concrete impact` must not be empty")

    if failures:
        print("ADR lint failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("ADR lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
