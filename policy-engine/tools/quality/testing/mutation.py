#!/usr/bin/env python3
"""Run canonical mutmut suites with complete, scoped mutation evidence."""

from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import os
import platform
import re
import shlex
import shutil
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.lib.fs import atomic_write_json
from tools.lib.imports import repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

from tools.lib.runner import run_command


@dataclass(frozen=True, slots=True)
class MutationTarget:
    """Source/test selection and minimum measured mutation score."""

    paths: str
    tests: str
    threshold_pct: float


FOUNDRY_TARGETS: dict[str, MutationTarget] = {
    "backends": MutationTarget(
        paths="src/polisyos/foundry/methods/backends/",
        tests="tests/unit/foundry/methods/backends/",
        threshold_pct=70.0,
    ),
    "base": MutationTarget(
        paths="src/polisyos/foundry/methods/base.py",
        tests="tests/unit/foundry/methods/",
        threshold_pct=70.0,
    ),
    "resolution": MutationTarget(
        paths="src/polisyos/foundry/methods/resolution.py",
        tests="tests/unit/foundry/methods/test_semver_resolution.py",
        threshold_pct=70.0,
    ),
    "full": MutationTarget(
        paths="src/polisyos/foundry/methods/",
        tests="tests/unit/foundry/",
        threshold_pct=70.0,
    ),
}

SCIENTIST_TARGETS: dict[str, MutationTarget] = {
    "governance": MutationTarget(
        paths="src/polisyos/scientist/governance/passes/",
        tests="tests/unit/scientist/governance/",
        threshold_pct=80.0,
    ),
    "condition": MutationTarget(
        paths=("src/polisyos/scientist/engine/condition.py"),
        tests=(
            "tests/unit/scientist/engine/test_condition.py "
            "tests/unit/scientist/engine/test_condition_compound.py "
            "tests/unit/scientist/engine/test_property_condition.py"
        ),
        threshold_pct=80.0,
    ),
    "budget": MutationTarget(
        paths="src/polisyos/scientist/engine/budget.py",
        tests=(
            "tests/unit/scientist/engine/test_budget.py "
            "tests/unit/scientist/engine/test_budget_middleware.py "
            "tests/unit/scientist/engine/test_property_budget.py"
        ),
        threshold_pct=80.0,
    ),
    "retry": MutationTarget(
        paths="src/polisyos/scientist/engine/retry.py",
        tests="tests/unit/scientist/engine/test_retry.py",
        threshold_pct=80.0,
    ),
    "checkpoint": MutationTarget(
        paths="src/polisyos/scientist/engine/checkpoint.py",
        tests=(
            "tests/unit/scientist/engine/test_checkpoint.py "
            "tests/unit/scientist/engine/test_property_checkpoint.py "
            "tests/unit/scientist/engine/test_checkpoint_gc.py"
        ),
        threshold_pct=80.0,
    ),
    "idempotency": MutationTarget(
        paths="src/polisyos/scientist/engine/idempotency.py",
        tests="tests/unit/scientist/engine/test_property_idempotency.py",
        threshold_pct=80.0,
    ),
    "convergence": MutationTarget(
        paths="src/polisyos/scientist/engine/convergence.py",
        tests=(
            "tests/unit/scientist/engine/test_convergence.py "
            "tests/unit/scientist/engine/test_convergence_semantic.py"
        ),
        threshold_pct=80.0,
    ),
    "api": MutationTarget(
        paths="src/polisyos/scientist/api.py",
        tests="tests/unit/scientist/facade/test_api.py",
        threshold_pct=80.0,
    ),
}

CORE_RUNTIME_TARGETS: dict[str, MutationTarget] = {
    "subset": MutationTarget(
        paths=(
            "src/polisyos/common/serialization.py "
            "src/polisyos/core/security/authz.py "
            "src/polisyos/runtime/http/dependencies.py"
        ),
        tests=(
            "tests/property/common/test_serialization_properties.py "
            "tests/property/runtime/http/test_access_invariants_properties.py "
            "tests/unit/runtime/http/test_runtime_api_authz.py"
        ),
        # The existing release workflow had no score floor; do not invent one here.
        threshold_pct=0.0,
    ),
}
_MUTANT_NAME = re.compile(r".+__mutmut_\d+$")
_COMPLETE_CODES = {0: "survived", 1: "killed"}


class MutationEvidenceError(ValueError):
    """The mutation apparatus did not produce a complete, scoped measurement."""


def _unsupported_station() -> str | None:
    if (
        sys.implementation.name == "cpython"
        and sys.version_info[:2] == (3, 14)
        and sys.platform == "darwin"
        and platform.machine() == "arm64"
    ):
        return (
            "unsupported mutation station: CPython 3.14 Darwin arm64; pinned mutmut 3.5.0 "
            "can crash in post-fork setproctitle before pytest. Use a supported Linux station."
        )
    return None


def _targets_for_suite(suite: str) -> dict[str, MutationTarget]:
    return {
        "foundry": FOUNDRY_TARGETS,
        "scientist": SCIENTIST_TARGETS,
        "core-runtime": CORE_RUNTIME_TARGETS,
    }[suite]


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MutationEvidenceError(f"expected object: {path}")
    return value


def _scope(root: Path, target: MutationTarget) -> tuple[list[str], list[str]]:
    sources: set[str] = set()
    tests = shlex.split(target.tests)
    for selection in (*shlex.split(target.paths), *tests):
        if Path(selection.split("::", 1)[0]).is_absolute() or selection.startswith("-"):
            raise MutationEvidenceError(f"selection must be repository relative: {selection}")
        path = root / selection.split("::", 1)[0]
        if not path.resolve().is_relative_to(root.resolve()) or not path.exists():
            raise MutationEvidenceError(f"missing or outside-root selection: {selection}")
    for selection in shlex.split(target.paths):
        path = root / selection
        candidates = path.rglob("*.py") if path.is_dir() else (path,)
        sources.update(
            str(item.relative_to(root))
            for item in candidates
            if item.suffix == ".py" and "__pycache__" not in item.parts
        )
    if not sources or not tests:
        raise MutationEvidenceError("empty declared source or test selection")
    return sorted(sources), tests


def _stage(root: Path, work: Path, sources: list[str], tests: list[str]) -> None:
    # Copy source context, never another environment or its cached mutation results.
    context = ("src", "tests", "tools", "schemas", "architecture", "ops", "pytest.ini")
    for name in context:
        source = root / name
        destination = work / name
        if source.is_dir():
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
        elif source.is_file():
            shutil.copy2(source, destination)
    for relative in sources:
        destination = work / relative
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, destination)
    also_copy = [name for name in context if (work / name).exists() and name != "pytest.ini"]
    config = {
        "paths_to_mutate": sources,
        "pytest_add_cli_args": ["--import-mode=importlib", "--rootdir=.", "--no-header"],
        "pytest_add_cli_args_test_selection": tests,
        "also_copy": also_copy,
    }
    (work / "pyproject.toml").write_text(
        "[tool.mutmut]\n"
        + "".join(f"{key} = {json.dumps(value)}\n" for key, value in config.items()),
        encoding="utf-8",
    )


def _selected(node: str, selections: list[str]) -> bool:
    return any(
        node == selected
        or node.startswith(selected + "::")
        or node.startswith(selected.rstrip("/") + "/")
        for selected in selections
    )


def _admit(work: Path, sources: list[str], tests: list[str]) -> dict:
    mutants = work / "mutants"
    counts = {"killed": 0, "survived": 0}
    mutated_sources: list[str] = []
    expected_meta: set[Path] = set()
    for source in sources:
        generated = mutants / source
        names = {
            node.name
            for node in ast.walk(ast.parse(generated.read_text(encoding="utf-8")))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and _MUTANT_NAME.fullmatch(node.name)
        }
        meta_path = generated.with_name(generated.name + ".meta")
        if not names and not meta_path.exists():
            continue
        expected_meta.add(meta_path)
        meta = _object(meta_path)
        codes = meta.get("exit_code_by_key")
        if (
            not isinstance(codes, dict)
            or not all(isinstance(key, str) for key in codes)
            or {key.rsplit(".", 1)[-1] for key in codes} != names
        ):
            raise MutationEvidenceError(f"generated mutant/metadata mismatch: {source}")
        if len(codes) != len(names):
            raise MutationEvidenceError(f"duplicate mutant identity: {source}")
        if codes:
            mutated_sources.append(source)
        for code in codes.values():
            # Pytest internal error 3 is called killed by mutmut; it is not an assertion witness.
            if type(code) is not int or code not in _COMPLETE_CODES:
                raise MutationEvidenceError(f"unmeasured mutant outcome in {source}: {code!r}")
            counts[_COMPLETE_CODES[code]] += 1
    if set(mutants.rglob("*.py.meta")) != expected_meta:
        raise MutationEvidenceError("mutation metadata outside declared source set")
    total = sum(counts.values())
    if not total:
        raise MutationEvidenceError("zero measured mutants")
    summary = _object(mutants / "mutmut-cicd-stats.json")
    if any(type(value) is not int or value < 0 for value in summary.values()):
        raise MutationEvidenceError("invalid mutation summary counts")
    expected = {"total": total, **counts}
    if any(summary.get(key) != value for key, value in expected.items()):
        raise MutationEvidenceError("summary does not reconcile to actual mutant outcomes")
    if any(value != 0 for key, value in summary.items() if key not in expected):
        raise MutationEvidenceError("mutation summary contains incomplete outcomes")
    stats = _object(mutants / "mutmut-stats.json")
    durations = stats.get("duration_by_test")
    if not isinstance(durations, dict) or not durations:
        raise MutationEvidenceError("no executed tests in mutation evidence")
    if not all(isinstance(node, str) for node in durations):
        raise MutationEvidenceError("invalid executed test identities")
    executed = sorted(durations)
    if not all(_selected(node, tests) for node in executed):
        raise MutationEvidenceError("executed tests outside declared selection")
    return {**expected, "mutated_sources": mutated_sources, "executed_tests": executed}


def _print_results(repo_root: Path) -> int:
    results = sorted((repo_root / "_build/mutation").glob("*.json"))
    if not results:
        print("UNRUN: no stored mutation receipts")
        return 2
    verdict = 0
    for path in results:
        payload = _object(path)
        print(f"Stored receipt {path}: {payload['status']}")
        verdict = max(verdict, {"pass": 0, "fail": 1, "unrun": 2}[payload["status"]])
    return verdict


def _run_target(repo_root: Path, *, name: str, target: MutationTarget) -> int:
    result: dict = {
        "status": "unrun",
        "target": name,
        "source_selection": target.paths,
        "test_selection": target.tests,
    }
    output = repo_root / "_build/mutation"
    output.mkdir(parents=True, exist_ok=True)
    code = 2
    try:
        if importlib.metadata.version("mutmut") != "3.5.0":
            raise MutationEvidenceError("mutation runner requires locked mutmut 3.5.0")
        if station_problem := _unsupported_station():
            raise MutationEvidenceError(station_problem)
        sources, tests = _scope(repo_root, target)
        work = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=output))
        result["workspace"] = str(work)
        _stage(repo_root, work, sources, tests)
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS"}
        }
        env["PYTHONNOUSERSITE"] = "1"
        for args in (("run", "--max-children", "1"), ("export-cicd-stats",)):
            # Import the console entry point once, rather than double-importing
            # __main__ with -m, which initializes multiprocessing twice.
            completed = run_command(
                [sys.executable, "-c", "from mutmut.__main__ import cli; cli()", *args],
                cwd=work,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            log = (completed.stdout or "") + (completed.stderr or "")
            (work / f"{args[0]}.log").write_text(log, encoding="utf-8")
            print(log, end="")
            if completed.returncode:
                raise MutationEvidenceError(
                    f"mutmut {args[0]} did not execute successfully: {completed.returncode}"
                )
        result.update(_admit(work, sources, tests))
        result["score_pct"] = result["killed"] * 100.0 / result["total"]
        code = 0 if result["score_pct"] >= target.threshold_pct else 1
        result["status"] = "pass" if code == 0 else "fail"
    except (OSError, ValueError, SyntaxError, importlib.metadata.PackageNotFoundError) as exc:
        result["reason"] = str(exc)
    atomic_write_json(output / f"{name}.json", result)
    print(
        f"Mutation {name}: {result['status'].upper()} ({result.get('reason', str(result.get('score_pct')) + '%')})"
    )
    return code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=("foundry", "scientist", "core-runtime"),
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
                exit_code = max(exit_code, result)
        return exit_code

    target = targets.get(args.target)
    if target is None:
        known = ", ".join(
            sorted((*targets.keys(), "results", *(("all",) if args.suite == "scientist" else ())))
        )
        print(f"Unknown target `{args.target}` for suite `{args.suite}`. Known: {known}")
        return 2
    return _run_target(repo_root, name=args.target, target=target)


if __name__ == "__main__":
    raise SystemExit(main())
