#!/usr/bin/env python3
"""Ratchet Phase 2 Scientist maintainability debt on targeted hot-path surfaces."""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TARGETS = (
    "src/polisyos/scientist/engine/async_executor.py",
    "src/polisyos/scientist/engine/fan_out.py",
    "src/polisyos/scientist/autotune/pareto.py",
    "src/polisyos/scientist/discovery/aggregator.py",
    "src/polisyos/scientist/discovery/output.py",
    "src/polisyos/scientist/discovery/portfolio.py",
    "src/polisyos/scientist/discovery/prior_miner.py",
    "src/polisyos/scientist/discovery/priors.py",
    "src/polisyos/scientist/discovery/workers/__init__.py",
    "src/polisyos/scientist/llm/prompt_cache.py",
    "src/polisyos/scientist/search/judge_stack.py",
    "src/polisyos/scientist/search/judge_thresholds.py",
    "src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py",
    "src/polisyos/scientist/nodes/builtins/decide/decision_packet_support.py",
    "src/polisyos/scientist/nodes/builtins/decide/policy_runtime_state.py",
    "src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py",
    "src/polisyos/scientist/cross_graph/alignment.py",
    "src/polisyos/scientist/cross_graph/compiler.py",
    "src/polisyos/scientist/feedback.py",
    "src/polisyos/scientist/feedback_utils.py",
)
DEFAULT_BASELINE = "tools/ci/scientist_phase2_ratchet_baseline.toml"
METRICS = ("explicit_any", "unsafe_cast", "raw_dict_index")


@dataclass(frozen=True)
class RatchetFinding:
    metric: str
    path: str
    actual: int
    baseline: int

    def render(self) -> str:
        delta = self.actual - self.baseline
        return (
            f"{self.path}: [{self.metric}] actual={self.actual} "
            f"baseline={self.baseline} delta=+{delta}"
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Block Phase 2 Scientist debt growth on targeted hot-path files.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root that contains the tracked source files.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(DEFAULT_BASELINE),
        help="TOML file with per-file baseline counts.",
    )
    parser.add_argument(
        "--print-current",
        action="store_true",
        help="Print the current counts in TOML format and exit.",
    )
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        default=None,
        help="Override tracked file list. May be passed multiple times.",
    )
    return parser


def _scan_file(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        "explicit_any": _count_explicit_any(tree),
        "unsafe_cast": _count_unsafe_cast(tree),
        "raw_dict_index": _count_raw_dict_index(tree),
    }


def _count_explicit_any(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "Any":
            count += 1
        elif isinstance(node, ast.Attribute) and node.attr == "Any":
            count += 1
    return count


def _count_unsafe_cast(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "cast":
            count += 1
        elif isinstance(func, ast.Attribute) and func.attr == "cast":
            count += 1
    return count


def _count_raw_dict_index(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        slice_node = node.slice
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            count += 1
    return count


def _load_baseline(path: Path) -> dict[str, dict[str, int]]:
    if not path.exists():
        return {metric: {} for metric in METRICS}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    baseline: dict[str, dict[str, int]] = {metric: {} for metric in METRICS}
    for metric in METRICS:
        entries = payload.get(metric, {})
        if isinstance(entries, dict):
            baseline[metric] = {
                str(file_path): int(value)
                for file_path, value in entries.items()
            }
    return baseline


def _render_baseline_toml(counts: dict[str, dict[str, int]]) -> str:
    lines: list[str] = []
    for metric in METRICS:
        lines.append(f"[{metric}]")
        for path in sorted(counts[metric]):
            lines.append(f'"{path}" = {counts[metric][path]}')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    targets = tuple(args.targets or DEFAULT_TARGETS)
    counts: dict[str, dict[str, int]] = {metric: {} for metric in METRICS}

    for relative_path in targets:
        source_path = (repo_root / relative_path).resolve()
        if not source_path.exists():
            print(f"Missing tracked file: {relative_path}", file=sys.stderr)
            return 1
        file_counts = _scan_file(source_path)
        for metric, value in file_counts.items():
            counts[metric][relative_path] = value

    if args.print_current:
        print(_render_baseline_toml(counts), end="")
        return 0

    baseline = _load_baseline((repo_root / args.baseline).resolve())
    unexpected: list[RatchetFinding] = []
    stale: list[str] = []
    for metric in METRICS:
        for relative_path, actual in counts[metric].items():
            expected = baseline.get(metric, {}).get(relative_path, 0)
            if actual > expected:
                unexpected.append(
                    RatchetFinding(
                        metric=metric,
                        path=relative_path,
                        actual=actual,
                        baseline=expected,
                    )
                )
            elif actual < expected:
                stale.append(
                    f"{relative_path}: [{metric}] actual={actual} baseline={expected}"
                )

    print("Scientist Phase 2 ratchet summary:")
    for metric in METRICS:
        total = sum(counts[metric].values())
        print(f"  - {metric}: total={total}")

    if unexpected:
        print("\nUnexpected debt growth:")
        for finding in unexpected:
            print(f"  - {finding.render()}")

    if stale:
        print("\nStale baseline entries:")
        for entry in stale:
            print(f"  - {entry}")

    return 1 if unexpected or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
