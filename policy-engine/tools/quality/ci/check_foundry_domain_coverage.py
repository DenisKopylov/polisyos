#!/usr/bin/env python3
"""Enforce Foundry coverage thresholds by domain instead of only globally."""

from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DomainTarget:
    name: str
    minimum_percent: float
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class DomainCoverage:
    name: str
    percent_covered: float
    covered_lines: int
    num_statements: int
    matched_files: tuple[str, ...]
    minimum_percent: float


FOUNDRY_DOMAIN_TARGETS: tuple[DomainTarget, ...] = (
    DomainTarget(
        name="executor_internals",
        minimum_percent=90.0,
        patterns=(
            "**/src/polisyos/foundry/execute/_graph.py",
            "**/src/polisyos/foundry/execute/_models.py",
            "**/src/polisyos/foundry/execute/_ops.py",
            "**/src/polisyos/foundry/execute/_patching.py",
            "**/src/polisyos/foundry/execute/_posture.py",
            "**/src/polisyos/foundry/execute/_snapshots.py",
        ),
    ),
    DomainTarget(
        name="core_mechanisms",
        minimum_percent=85.0,
        patterns=(
            "**/src/polisyos/foundry/mechanisms/fiscal.py",
            "**/src/polisyos/foundry/mechanisms/labor.py",
            "**/src/polisyos/foundry/mechanisms/treasury.py",
        ),
    ),
    DomainTarget(
        name="bayesian_methods",
        minimum_percent=80.0,
        patterns=("**/src/polisyos/foundry/methods/catalog/bayesian/*.py",),
    ),
    DomainTarget(
        name="ml_methods",
        minimum_percent=70.0,
        patterns=("**/src/polisyos/foundry/methods/catalog/ml/*.py",),
    ),
    DomainTarget(
        name="spatial_methods",
        minimum_percent=75.0,
        patterns=("**/src/polisyos/foundry/methods/catalog/spatial/*.py",),
    ),
    DomainTarget(
        name="trace_module",
        minimum_percent=1.0,
        patterns=("**/src/polisyos/foundry/runtime/trace.py",),
    ),
    DomainTarget(
        name="queue_module",
        minimum_percent=1.0,
        patterns=("**/src/polisyos/foundry/execute/queue.py",),
    ),
    DomainTarget(
        name="specs_module",
        minimum_percent=1.0,
        patterns=("**/src/polisyos/foundry/contracts/specs.py",),
    ),
    DomainTarget(
        name="profiles_module",
        minimum_percent=1.0,
        patterns=("**/src/polisyos/foundry/runtime/profiles.py",),
    ),
)


def load_coverage_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_path(path: str, *, repo_root: Path | None = None) -> str:
    candidate = Path(path)
    if repo_root is not None:
        try:
            return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            pass
    return candidate.as_posix()


def _match_patterns(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def summarize_domain(
    coverage_payload: dict[str, Any],
    target: DomainTarget,
    *,
    repo_root: Path | None = None,
) -> DomainCoverage:
    files = coverage_payload.get("files", {})
    matched_files: list[str] = []
    covered_lines = 0
    num_statements = 0

    for raw_path, payload in files.items():
        normalized = _normalized_path(raw_path, repo_root=repo_root)
        if not _match_patterns(normalized, target.patterns):
            continue
        summary = payload.get("summary", {})
        matched_files.append(normalized)
        covered_lines += int(summary.get("covered_lines", 0))
        num_statements += int(summary.get("num_statements", 0))

    percent = 0.0 if num_statements == 0 else (covered_lines / num_statements) * 100.0
    return DomainCoverage(
        name=target.name,
        percent_covered=percent,
        covered_lines=covered_lines,
        num_statements=num_statements,
        matched_files=tuple(sorted(matched_files)),
        minimum_percent=target.minimum_percent,
    )


def evaluate_foundry_domain_coverage(
    coverage_payload: dict[str, Any],
    *,
    repo_root: Path | None = None,
    targets: tuple[DomainTarget, ...] = FOUNDRY_DOMAIN_TARGETS,
) -> tuple[list[DomainCoverage], list[str]]:
    summaries = [
        summarize_domain(coverage_payload, target, repo_root=repo_root) for target in targets
    ]

    findings: list[str] = []
    for summary in summaries:
        if not summary.matched_files:
            findings.append(
                f"{summary.name}: no coverage files matched the configured domain patterns"
            )
            continue
        if summary.percent_covered + 1e-9 < summary.minimum_percent:
            findings.append(
                f"{summary.name}: {summary.percent_covered:.1f}% covered, "
                f"target is {summary.minimum_percent:.1f}%"
            )
    return summaries, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Foundry coverage by domain")
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    payload = load_coverage_json(args.coverage_json)
    summaries, findings = evaluate_foundry_domain_coverage(
        payload,
        repo_root=args.repo_root,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "summaries": [summary.__dict__ for summary in summaries],
                    "findings": findings,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for summary in summaries:
            print(
                f"{summary.name}: {summary.percent_covered:.1f}% "
                f"({summary.covered_lines}/{summary.num_statements})"
            )
        if findings:
            for finding in findings:
                print(f"Foundry coverage ratchet: {finding}")
        else:
            print("Foundry coverage ratchet: pass")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
