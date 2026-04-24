#!/usr/bin/env python3
"""Manual throughput benchmark for the current Foundry agent-sim executor."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from tools._lib.imports import ensure_repo_import_roots, repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

REPO_ROOT, SRC_ROOT = ensure_repo_import_roots(__file__)

import jax
import jax.numpy as jnp
import numpy as np

import jax_bootstrap  # noqa: F401
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.mechanisms import TaxationMechanism
from polisyos.foundry.agent_sim.state import GlobalState


def _block_until_ready(result: Any) -> Any:
    try:
        return jax.block_until_ready(result)
    except Exception:
        return result


def _make_state(n_agents: int, *, seed: int, horizon: int) -> GlobalState:
    state = GlobalState.empty(
        n_agents=n_agents,
        max_agents=n_agents,
        seed=seed,
        simulation_horizon=horizon,
    )
    agents = state.agents.replace(
        active=jnp.ones((n_agents,), dtype=jnp.bool_),
        income=jnp.linspace(800.0, 3200.0, n_agents, dtype=jnp.float32),
        wealth=jnp.linspace(5000.0, 25000.0, n_agents, dtype=jnp.float32),
        consumption=jnp.linspace(300.0, 1200.0, n_agents, dtype=jnp.float32),
    )
    policy = state.policy.replace(tax_rate=jnp.array(0.18, dtype=jnp.float32))
    return state.replace(agents=agents, policy=policy)


def _benchmark_step(
    executor: PureExecutor,
    state: GlobalState,
    *,
    warmup: int,
    repeat: int,
) -> dict[str, float]:
    for _ in range(max(warmup, 0)):
        next_state, _ = executor.step(state)
        _block_until_ready(next_state.agents.income)

    samples_ms: list[float] = []
    for _ in range(max(repeat, 1)):
        start = time.perf_counter()
        next_state, _ = executor.step(state)
        _block_until_ready(next_state.agents.income)
        samples_ms.append((time.perf_counter() - start) * 1000.0)

    arr = np.asarray(samples_ms, dtype=float)
    return {
        "mean_ms": float(np.mean(arr)),
        "median_ms": float(np.median(arr)),
        "p95_ms": float(np.percentile(arr, 95.0)),
    }


def _benchmark_run(
    executor: PureExecutor,
    state: GlobalState,
    *,
    n_steps: int,
    warmup: int,
    repeat: int,
) -> dict[str, float]:
    for _ in range(max(warmup, 0)):
        final_state, _ = executor.run(state, n_steps)
        _block_until_ready(final_state.agents.income)

    samples_ms: list[float] = []
    for _ in range(max(repeat, 1)):
        start = time.perf_counter()
        final_state, _ = executor.run(state, n_steps)
        _block_until_ready(final_state.agents.income)
        samples_ms.append((time.perf_counter() - start) * 1000.0)

    arr = np.asarray(samples_ms, dtype=float)
    mean_ms = float(np.mean(arr))
    agent_steps_per_second = float((state.agents.size * n_steps) / (mean_ms / 1000.0))
    return {
        "mean_ms": mean_ms,
        "median_ms": float(np.median(arr)),
        "p95_ms": float(np.percentile(arr, 95.0)),
        "steps_per_second": float(n_steps / (mean_ms / 1000.0)),
        "agent_steps_per_second": agent_steps_per_second,
    }


def run_benchmark(
    *,
    n_agents: int,
    n_steps: int,
    seed: int,
    warmup: int,
    repeat: int,
) -> dict[str, Any]:
    state = _make_state(n_agents, seed=seed, horizon=max(n_steps, 8))
    executor = PureExecutor(
        [TaxationMechanism(progressive_factor=0.05)],
        aggregate_every=1,
        compute_gini=True,
    )

    return {
        "n_agents": n_agents,
        "n_steps": n_steps,
        "step": _benchmark_step(executor, state, warmup=warmup, repeat=repeat),
        "run_scan": _benchmark_run(
            executor,
            state,
            n_steps=n_steps,
            warmup=warmup,
            repeat=repeat,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Foundry agent-sim throughput")
    parser.add_argument("--agents", type=int, default=10000, help="Number of active agents")
    parser.add_argument("--steps", type=int, default=16, help="Number of executor steps")
    parser.add_argument("--seed", type=int, default=7, help="State construction seed")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup iterations")
    parser.add_argument("--repeat", type=int, default=5, help="Measured iterations")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text summary",
    )
    args = parser.parse_args()

    results = run_benchmark(
        n_agents=args.agents,
        n_steps=args.steps,
        seed=args.seed,
        warmup=args.warmup,
        repeat=args.repeat,
    )
    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
        return 0

    print("Foundry simulation benchmark summary")
    print(
        f"- setup: agents={results['n_agents']} steps={results['n_steps']} "
        f"warmup={args.warmup} repeat={args.repeat}"
    )
    print(
        f"- single step: mean={results['step']['mean_ms']:.2f}ms "
        f"median={results['step']['median_ms']:.2f}ms "
        f"p95={results['step']['p95_ms']:.2f}ms"
    )
    print(
        f"- run scan: mean={results['run_scan']['mean_ms']:.2f}ms "
        f"median={results['run_scan']['median_ms']:.2f}ms "
        f"p95={results['run_scan']['p95_ms']:.2f}ms "
        f"steps/s={results['run_scan']['steps_per_second']:.2f} "
        f"agent-steps/s={results['run_scan']['agent_steps_per_second']:.0f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
