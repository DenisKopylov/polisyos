"""Shared result and size-ratchet support for package import gates."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from typing import Any, Protocol


class FindingFactory[FindingT](Protocol):
    """Describe the finding constructor supplied by the public gate module."""

    def __call__(self, check: str, subject: str, message: str, detail: str = "") -> FindingT: ...


def as_int(value: object) -> int:
    """Convert a report scalar to an integer, preserving the gate's zero fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def date_is_after(value: str, limit: str) -> bool:
    """Return whether one ISO date is strictly after another valid ISO date."""
    try:
        parsed = date.fromisoformat(value)
        parsed_limit = date.fromisoformat(limit)
    except ValueError:
        return False
    return parsed > parsed_limit


def count_lines(path: Path) -> int:
    """Count nonblank, noncomment source lines used by size ratchets."""
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip() and not line.lstrip().startswith("#"))


def read_toml(path: Path) -> dict[str, Any]:
    """Read one TOML contract as a mapping."""
    with path.open("rb") as stream:
        return tomllib.load(stream)


def check_module_size_ratchet[FindingT](
    repo_root: Path, *, finding_factory: FindingFactory[FindingT]
) -> list[FindingT]:
    """Evaluate module-size counters and emit the gate's existing findings."""
    budget_path = repo_root / "architecture" / "module_size_budget.toml"
    if not budget_path.exists():
        return []
    data = read_toml(budget_path)
    findings: list[FindingT] = []
    for budget in data.get("budget", []):
        relative = str(budget.get("path", ""))
        if not relative:
            continue
        path = repo_root / relative
        if not path.exists():
            findings.append(
                finding_factory("module-size-ratchet", relative, "budgeted module is missing")
            )
            continue
        current = count_lines(path)
        current_budget = as_int(budget.get("current_lines"))
        if current_budget and current > current_budget:
            findings.append(
                finding_factory(
                    "module-size-ratchet",
                    relative,
                    "module grew above its ratcheted current_lines budget",
                    f"current={current} budget={current_budget}",
                )
            )
        report_only_limit = as_int(budget.get("report_only_limit_lines"))
        if report_only_limit and current > report_only_limit:
            findings.append(
                finding_factory(
                    "module-size-ratchet",
                    relative,
                    "module grew above its report_only_limit_lines ratchet",
                    f"current={current} limit={report_only_limit}",
                )
            )
    return findings
