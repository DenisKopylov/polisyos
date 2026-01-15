from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.scientist.orchestrator.workflow import build_workflow


def _build_state(args: argparse.Namespace) -> dict:
    state = {
        "user_request": args.user_request,
        "run_id": args.run_id,
        "baseline_run_id": args.baseline_run_id,
        "db_path": args.db_path,
        "graph_path": args.graph_path,
        "cas_root": args.cas_root,
        "runtime_base_dir": args.runtime_base_dir,
        "max_repair_attempts": args.max_repair_attempts,
        "runner_backend": args.runner_backend,
        "random_seed": args.random_seed,
    }
    return {key: value for key, value in state.items() if value is not None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a Scientist workflow for a policy experiment.",
    )
    parser.add_argument("user_request", help="Natural language policy request")
    parser.add_argument("--run-id", help="Explicit run id (optional)")
    parser.add_argument(
        "--baseline-run-id",
        default="baseline_2023",
        help="Run id used to seed the initial state",
    )
    parser.add_argument(
        "--db-path",
        default="integration.duckdb",
        help="DuckDB path for UDF queries",
    )
    parser.add_argument("--graph-path", help="Optional graph store path")
    parser.add_argument("--cas-root", help="CAS root directory")
    parser.add_argument(
        "--runtime-base-dir",
        default="runs",
        help="Runtime directory for run artifacts",
    )
    parser.add_argument(
        "--max-repair-attempts",
        type=int,
        default=3,
        help="Max repair attempts before pruning",
    )
    parser.add_argument("--runner-backend", help="Compute backend override")
    parser.add_argument("--random-seed", type=int, help="Seed for simulation")

    args = parser.parse_args(argv)
    state = _build_state(args)

    workflow = build_workflow()
    result = workflow.invoke(state)

    payload = {
        "run_id": result.get("run_id"),
        "verdict": (result.get("feedback") or {}).get("verdict"),
        "simulation_results": result.get("simulation_results"),
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
