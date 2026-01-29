"""Check benchmark regressions from pytest-benchmark JSON output."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


def _load_benchmarks(path: Path) -> Dict[str, float]:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Failed to read benchmark JSON: {path}: {exc}") from exc

    benchmarks = data.get("benchmarks") or []
    results: Dict[str, float] = {}
    for item in benchmarks:
        name = item.get("name")
        stats = item.get("stats") or {}
        mean = stats.get("mean")
        if name and isinstance(mean, (int, float)):
            results[name] = float(mean)
    return results


def _find_latest_baseline(root: Path) -> Path | None:
    candidates = []
    for folder in (root / ".benchmarks", root / "benchmarks"):
        if not folder.exists():
            continue
        for path in folder.rglob("*.json"):
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark_json", type=Path)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--baseline", type=Path, default=None)
    args = parser.parse_args()

    if not args.benchmark_json.exists():
        print(f"Benchmark JSON not found: {args.benchmark_json}")
        return 0

    current = _load_benchmarks(args.benchmark_json)
    if not current:
        print("No benchmark results found in JSON; skipping regression check.")
        return 0

    baseline_path = args.baseline
    if baseline_path is None:
        baseline_path = _find_latest_baseline(Path.cwd())

    if baseline_path is None or not baseline_path.exists():
        print("No baseline benchmark JSON found; skipping regression check.")
        return 0

    baseline = _load_benchmarks(baseline_path)
    if not baseline:
        print("Baseline benchmark JSON contains no results; skipping regression check.")
        return 0

    regressions = []
    for name, current_mean in current.items():
        base_mean = baseline.get(name)
        if base_mean is None or base_mean == 0:
            continue
        delta = (current_mean - base_mean) / base_mean
        if delta > args.threshold:
            regressions.append((name, base_mean, current_mean, delta))

    if regressions:
        print("Performance regressions detected:")
        for name, base, current_mean, delta in regressions:
            print(
                f"- {name}: {current_mean:.6f}s vs {base:.6f}s "
                f"(+{delta*100:.2f}%)"
            )
        return 1

    print("No performance regressions detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
