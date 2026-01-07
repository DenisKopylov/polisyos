#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from polisyos.ir.data_views import AccessTier, DataFilter, DataViewRequest, DataViewType
from polisyos.fabric.udf.engine import UDFEngine


def run_queries(engine: UDFEngine, repeats: int) -> dict[str, float]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="UDF performance regression gate.")
    parser.add_argument("--db-path", type=Path, default=Path("demo_udf.duckdb"))
    parser.add_argument("--kuzu-path", type=Path, default=Path("demo_udf.kuzu"))
    parser.add_argument("--curated-dir", type=Path, default=Path("data/curated"))
    parser.add_argument("--baseline", type=Path, default=Path("data/curated/udf_perf_baseline.json"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-regression", type=float, default=1.2)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    db = SimulationDB(str(args.db_path))
    graph = GraphStore(str(args.kuzu_path))
    engine = UDFEngine(db, graph, curated_dir=args.curated_dir)

    results = run_queries(engine, args.repeats)

    if args.write_baseline:
        payload = {"version": 1, "queries": results}
        args.baseline.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"Wrote baseline: {args.baseline}")
        db.close()
        return 0

    if not args.baseline.exists():
        print(f"Baseline missing: {args.baseline}. Run with --write-baseline.")
        db.close()
        return 2

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_queries = baseline.get("queries", {})
    failures = []
    for name, ms in results.items():
        if name not in baseline_queries:
            failures.append(f"{name}: missing baseline")
            continue
        allowed = float(baseline_queries[name]) * args.max_regression
        if ms > allowed:
            failures.append(f"{name}: {ms:.2f}ms > {allowed:.2f}ms (baseline {baseline_queries[name]:.2f}ms)")

    if failures:
        print("Performance regression detected:")
        for line in failures:
            print(f"- {line}")
        db.close()
        return 1

    print("Performance gate: OK")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
