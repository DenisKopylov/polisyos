#!/usr/bin/env python3
"""Run canonical mutmut-based mutation suites for Foundry and Scientist."""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tools._lib.imports import repo_root_from
import sys

sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.runner import run_command


@dataclass(frozen=True, slots=True)
class MutationTarget:
    paths: str
    tests: str
    threshold_pct: float


FOUNDRY_TARGETS: dict[str, MutationTarget] = {
    "backends": MutationTarget(
        paths="src/polisyos/foundry/methods/backends/",
        tests="tests/foundry/methods/backends/",
        threshold_pct=70.0,
    ),
    "base": MutationTarget(
        paths="src/polisyos/foundry/methods/base.py",
        tests="tests/foundry/methods/",
        threshold_pct=70.0,
    ),
    "resolution": MutationTarget(
        paths="src/polisyos/foundry/methods/resolution.py",
        tests="tests/foundry/methods/test_semver_resolution.py",
        threshold_pct=70.0,
    ),
    "full": MutationTarget(
        paths="src/polisyos/foundry/methods/",
        tests="tests/foundry/",
        threshold_pct=70.0,
    ),
}

SCIENTIST_TARGETS: dict[str, MutationTarget] = {
    "governance": MutationTarget(
        paths="src/polisyos/scientist/governance/passes/",
        tests="tests/scientist/governance/",
        threshold_pct=80.0,
    ),
    "condition": MutationTarget(
        paths=(
            "src/polisyos/scientist/engine/condition.py"
        ),
        tests=(
            "tests/scientist/engine/test_condition.py "
            "tests/scientist/engine/test_condition_compound.py "
            "tests/scientist/engine/test_property_condition.py"
        ),
        threshold_pct=80.0,
    ),
    "budget": MutationTarget(
        paths="src/polisyos/scientist/engine/budget.py",
        tests=(
            "tests/scientist/engine/test_budget.py "
            "tests/scientist/engine/test_budget_middleware.py "
            "tests/scientist/engine/test_property_budget.py"
        ),
        threshold_pct=80.0,
    ),
    "retry": MutationTarget(
        paths="src/polisyos/scientist/engine/retry.py",
        tests="tests/scientist/engine/test_retry.py",
        threshold_pct=80.0,
    ),
    "checkpoint": MutationTarget(
        paths="src/polisyos/scientist/engine/checkpoint.py",
        tests=(
            "tests/scientist/engine/test_checkpoint.py "
            "tests/scientist/engine/test_property_checkpoint.py "
            "tests/scientist/engine/test_checkpoint_gc.py"
        ),
        threshold_pct=80.0,
    ),
    "idempotency": MutationTarget(
        paths="src/polisyos/scientist/engine/idempotency.py",
        tests="tests/scientist/engine/test_property_idempotency.py",
        threshold_pct=80.0,
    ),
    "convergence": MutationTarget(
        paths="src/polisyos/scientist/engine/convergence.py",
        tests=(
            "tests/scientist/engine/test_convergence.py "
            "tests/scientist/engine/test_convergence_semantic.py"
        ),
        threshold_pct=80.0,
    ),
    "api": MutationTarget(
        paths="src/polisyos/scientist/api.py",
        tests="tests/scientist/test_api.py",
        threshold_pct=80.0,
    ),
}

TOTAL_RE = re.compile(r"(?m)^(\d+)\s+mutants?\b")


def _targets_for_suite(suite: str) -> dict[str, MutationTarget]:
    if suite == "foundry":
        return FOUNDRY_TARGETS
    if suite == "scientist":
        return SCIENTIST_TARGETS
    raise ValueError(f"unsupported mutation suite: {suite}")


def _parse_total_mutants(output: str) -> int:
    match = TOTAL_RE.search(output)
    if match is None:
        return 0
    return int(match.group(1))


def _print_results(repo_root: Path) -> int:
    results = run_command(["mutmut", "results"], cwd=repo_root, check=False)
    survivors = run_command(
        ["mutmut", "results", "--status", "survived"],
        cwd=repo_root,
        check=False,
    )
    if survivors.returncode != 0:
        print("(none - all mutants killed)")
    return int(results.returncode)


def _run_target(repo_root: Path, *, name: str, target: MutationTarget) -> int:
    first_test_dir = target.tests.split()[0]
    print(f"=== Running mutation target: {name} ===")
    print(f"  Paths: {target.paths}")
    print(f"  Tests: {target.tests}")
    run_result = run_command(
        [
            "mutmut",
            "run",
            "--paths-to-mutate",
            target.paths,
            "--tests-dir",
            first_test_dir,
            "--runner",
            f"python -m pytest {target.tests} -x -q --no-header --tb=no",
            "--simple-output",
        ],
        cwd=repo_root,
        check=False,
    )
    if run_result.returncode != 0:
        return int(run_result.returncode)

    summary = run_command(
        ["mutmut", "results"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    print(summary.stdout or "", end="")
    killed = run_command(
        ["mutmut", "results", "--status", "killed"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    total_mutants = _parse_total_mutants(summary.stdout or "")
    killed_mutants = sum(1 for line in (killed.stdout or "").splitlines() if line.strip())
    if total_mutants <= 0:
        print("No mutants found.")
        return 0

    rate = (killed_mutants * 100.0) / float(total_mutants)
    print(f"Kill rate: {killed_mutants}/{total_mutants} = {rate:.1f}%")
    if rate < target.threshold_pct:
        print(f"WARNING: Kill rate below {target.threshold_pct:.0f}% target.")
        return 1
    print(f"OK: Kill rate meets {target.threshold_pct:.0f}% target.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=("foundry", "scientist"),
        default="foundry",
        help="Mutation target family to run.",
    )
    parser.add_argument(
        "--target",
        default="backends",
        help="Named mutation target or `results`; scientist also supports `all`.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv or ()))
    repo_root = repo_root_from(__file__)
    targets = _targets_for_suite(args.suite)

    if args.target == "results":
        return _print_results(repo_root)

    if args.suite == "scientist" and args.target == "all":
        exit_code = 0
        for name, target in SCIENTIST_TARGETS.items():
            result = _run_target(repo_root, name=name, target=target)
            if result != 0:
                exit_code = result
        return exit_code

    target = targets.get(args.target)
    if target is None:
        known = ", ".join(sorted((*targets.keys(), "results", *(("all",) if args.suite == "scientist" else ()))))
        print(f"Unknown target `{args.target}` for suite `{args.suite}`. Known: {known}")
        return 2
    return _run_target(repo_root, name=args.target, target=target)


if __name__ == "__main__":
    raise SystemExit(main())
