from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_SKIP_PATTERN = re.compile(
    r'pytest\.skip\((?:f)?["\']([^"\']+)["\']|'
    r'@pytest\.mark\.skip(?:if)?\([^\n]*reason=(?:f)?["\']([^"\']+)["\']'
)

_ENVIRONMENT_GUARD_PATTERNS = (
    "installed",
    "not importable",
    "not available",
    "solver backend not available",
    "runtime stack is available",
    "this environment",
    "causalgraphmodel not available",
    "baseline is empty",
    "no baseline file",
    "allow_breaking_env",
    "skipping breaking change check",
)

_COVERAGE_DEBT_PATTERNS = (
    "registry is empty",
    "no methods registered",
    "not registered",
    "cannot load",
    "could not load",
    "no 1.x methods registered",
    "no runnable entries",
    "all runnable entries",
    "need both large- and small-min-obs",
    "no iv entries found",
    "no cells generated",
    "catalog directory not found",
)

_SCENARIO_GUARD_PATTERNS = (
    "identification failed",
    "not identified",
    "unexpectedly identified",
    "negativecertificate",
    "cannot build snapshot",
    "could not build 3-node chain",
    "need ≥2 registered methods",
    "expected identified query",
)

_MAX_TOTAL_SKIP_MARKERS = 32
_MAX_COVERAGE_DEBT_MARKERS = 0
_MAX_SCENARIO_GUARD_MARKERS = 7
FOUNDRY_TEST_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SkipMarker:
    path: str
    lineno: int
    reason: str
    classification: str


def _classify_skip_reason(reason: str) -> str:
    reason_l = reason.lower()
    if any(token in reason_l for token in _ENVIRONMENT_GUARD_PATTERNS):
        return "environment_guard"
    if any(token in reason_l for token in _COVERAGE_DEBT_PATTERNS):
        return "coverage_debt"
    if any(token in reason_l for token in _SCENARIO_GUARD_PATTERNS):
        return "scenario_guard"
    return "unclassified"


def _collect_skip_markers(root: Path) -> list[SkipMarker]:
    markers: list[SkipMarker] = []
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = _SKIP_PATTERN.search(line)
            if match is None:
                continue
            reason = match.group(1) or match.group(2) or ""
            markers.append(
                SkipMarker(
                    path=str(path.relative_to(root.parent.parent)),
                    lineno=lineno,
                    reason=reason,
                    classification=_classify_skip_reason(reason),
                )
            )
    return markers


def test_foundry_skip_markers_are_fully_classified() -> None:
    markers = _collect_skip_markers(FOUNDRY_TEST_ROOT)
    unclassified = [marker for marker in markers if marker.classification == "unclassified"]
    assert not unclassified, (
        "Foundry skip markers must be classified as environment_guard, "
        "coverage_debt, or scenario_guard:\n"
        + "\n".join(
            f"  - {marker.path}:{marker.lineno}: {marker.reason}" for marker in unclassified
        )
    )


def test_foundry_skip_marker_budgets_do_not_regress() -> None:
    markers = _collect_skip_markers(FOUNDRY_TEST_ROOT)
    counts = Counter(marker.classification for marker in markers)

    assert len(markers) <= _MAX_TOTAL_SKIP_MARKERS, (
        f"Total Foundry skip markers regressed: {len(markers)} > {_MAX_TOTAL_SKIP_MARKERS}"
    )
    assert counts["coverage_debt"] <= _MAX_COVERAGE_DEBT_MARKERS, (
        "Coverage-debt skip markers regressed: "
        f"{counts['coverage_debt']} > {_MAX_COVERAGE_DEBT_MARKERS}"
    )
    assert counts["scenario_guard"] <= _MAX_SCENARIO_GUARD_MARKERS, (
        "Scenario-guard skip markers regressed: "
        f"{counts['scenario_guard']} > {_MAX_SCENARIO_GUARD_MARKERS}"
    )
