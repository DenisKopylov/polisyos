#!/usr/bin/env python
"""CLI entrypoint for the honest head-to-head benchmark."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure src is on path for PolicyOS imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
# Ensure benchmarks root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.honest_comparison.config import BenchmarkConfig, FairnessTier
from benchmarks.honest_comparison.runner import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Honest head-to-head benchmark: PolicyOS vs open-source causal inference"
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Smoke test: K=3, n=500, Tier B only",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output path for JSON report (default: benchmarks/_reports/honest_YYYYMMDD.json)",
    )
    parser.add_argument(
        "--tiers", type=str, default=None,
        help="Comma-separated tiers to run (A,B,C). Default: all (or B for smoke)",
    )
    parser.add_argument(
        "--k", type=int, default=None,
        help="Override number of replications",
    )
    parser.add_argument(
        "--n", type=str, default=None,
        help="Comma-separated sample sizes (e.g., 1000,2500,5000)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Build config from args + env vars
    smoke = args.smoke or os.environ.get("HONEST_SMOKE", "").lower() in ("1", "true")

    tiers_input = args.tiers or os.environ.get("HONEST_TIER")
    if tiers_input:
        tier_map = {"a": FairnessTier.A, "b": FairnessTier.B, "c": FairnessTier.C}
        tiers = tuple(tier_map[t.strip().lower()] for t in tiers_input.split(","))
    else:
        tiers = (FairnessTier.A, FairnessTier.B, FairnessTier.C)

    k_val = args.k or int(os.environ.get("HONEST_K", "100"))
    n_input = args.n or os.environ.get("HONEST_N")
    sample_sizes = tuple(int(x) for x in n_input.split(",")) if n_input else (1000, 2500, 5000)

    cfg = BenchmarkConfig(
        tiers=tiers,
        sample_sizes=sample_sizes,
        k_replications=k_val,
        smoke=smoke,
    )

    # Output path
    if args.output:
        output_path = Path(args.output)
    else:
        reports_dir = Path(__file__).resolve().parents[1] / "_reports"
        output_path = reports_dir / f"honest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    run_benchmark(cfg, output_path)


if __name__ == "__main__":
    main()
