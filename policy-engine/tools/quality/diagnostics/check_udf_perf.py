#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, SRC_ROOT = ensure_repo_import_roots(__file__)

try:
    from polisyos.fabric.io.db import SimulationDB
    from polisyos.fabric.io.graph_store import GraphStore
    from polisyos.fabric.udf.engine import UDFEngine
    from polisyos.ir.analytics.data_views import (
        AccessTier,
        DataFilter,
        DataViewRequest,
        DataViewType,
    )
except ImportError as exc:  # explicit degraded mode for legacy UDF surface.
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None


def run_queries(engine: Any, repeats: int) -> dict[str, float]:
    queries = {
        "panel_macro": DataViewRequest(
            request_id="perf_panel",
            run_id="demo_run",
            view_type=DataViewType.PANEL,
            metrics=["gdp", "unemployment_rate"],
            step_start=0,
            step_end=5,
            access_tier=AccessTier.PUBLIC,
        ),
        "snapshot_income": DataViewRequest(
            request_id="perf_snapshot",
            run_id="demo_run",
            view_type=DataViewType.SNAPSHOT,
            metrics=["income"],
            aggregation="mean",
            step_end=0,
            filters=[DataFilter(column="is_employed", op="==", value=True)],
            access_tier=AccessTier.INTERNAL,
        ),
        "network_neighbors": DataViewRequest(
            request_id="perf_network",
            run_id="demo_run",
            view_type=DataViewType.NETWORK,
            metrics=["neighbor_id", "amount", "type"],
            ego_node_id="agent_1",
            hop_depth=1,
            access_tier=AccessTier.INTERNAL,
        ),
    }
    results: dict[str, float] = {}
    for name, request in queries.items():
        timings = []
        for _ in range(repeats):
            start = time.perf_counter()
            engine.query(request)
            timings.append((time.perf_counter() - start) * 1000.0)
        results[name] = sum(timings) / max(len(timings), 1)
    return results


def _load_baseline(path: Path) -> dict[str, float]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid baseline JSON: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("queries"), dict):
        raise ValueError(f"baseline must be a JSON object with a 'queries' object: {path}")
    baseline: dict[str, float] = {}
    for name, value in payload["queries"].items():
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"baseline query {name!r} must be a finite non-negative number")
        baseline[str(name)] = number
    return baseline


def _close_all(resources: Sequence[Any]) -> None:
    for resource in reversed(resources):
        close = getattr(resource, "close", None)
        if callable(close):
            close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UDF performance regression gate.")
    parser.add_argument("--db-path", type=Path, default=Path("data/databases/demo_udf.duckdb"))
    parser.add_argument("--kuzu-path", type=Path, default=Path("data/databases/demo_udf.kuzu"))
    parser.add_argument("--curated-dir", type=Path, default=Path("data/curated"))
    parser.add_argument(
        "--baseline", type=Path, default=Path("data/curated/udf_perf_baseline.json")
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-regression", type=float, default=1.2)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args(argv)

    if _IMPORT_ERROR is not None:
        print(
            "UDF performance gate is unavailable in this checkout: "
            f"{type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR}",
            file=sys.stderr,
        )
        print(
            "This legacy tool is quarantined; use `polisyos-tools list` for replacement metadata.",
            file=sys.stderr,
        )
        return 78
    if args.repeats <= 0:
        print("--repeats must be positive", file=sys.stderr)
        return 2
    if not math.isfinite(args.max_regression) or args.max_regression <= 0:
        print("--max-regression must be a finite positive number", file=sys.stderr)
        return 2

    resources: list[Any] = []
    try:
        db = SimulationDB(str(args.db_path))
        resources.append(db)
        graph = GraphStore(str(args.kuzu_path))
        resources.append(graph)
        engine = UDFEngine(db, graph, curated_dir=args.curated_dir)

        results = run_queries(engine, args.repeats)

        if args.write_baseline:
            payload = {"version": 1, "queries": results}
            atomic_write_json(args.baseline, payload)
            print(f"Wrote baseline: {args.baseline}")
            return 0

        if not args.baseline.exists():
            print(f"Baseline missing: {args.baseline}. Run with --write-baseline.")
            return 2

        baseline_queries = _load_baseline(args.baseline)
        failures = []
        for name, ms in results.items():
            if name not in baseline_queries:
                failures.append(f"{name}: missing baseline")
                continue
            allowed = baseline_queries[name] * args.max_regression
            if ms > allowed:
                failures.append(
                    f"{name}: {ms:.2f}ms > {allowed:.2f}ms (baseline {baseline_queries[name]:.2f}ms)"
                )

        if failures:
            print("Performance regression detected:")
            for line in failures:
                print(f"- {line}")
            return 1

        print("Performance gate: OK")
        return 0
    finally:
        _close_all(resources)


if __name__ == "__main__":
    raise SystemExit(main())
