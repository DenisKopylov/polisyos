#!/usr/bin/env python3
"""Run basedpyright across the full core-runtime surface plus curated extras."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from ._common import PRODUCT_ROOT

DEFAULT_SCOPE = (
    "src/polisyos/common",
    "src/polisyos/core",
    "src/polisyos/runtime",
)

CURATED_EXTRA_SCOPE = (
    "src/polisyos/scholar/freshness.py",
    "src/polisyos/scholar/orchestrator/bundle.py",
    "src/polisyos/scholar/api.py",
    "src/polisyos/scientist/api.py",
    "src/polisyos/scientist/adapters/fabric_bridge.py",
    "src/polisyos/scientist/agent/drafter_factory.py",
    "src/polisyos/scientist/agent/knowledge_base.py",
    "src/polisyos/scientist/methods/autotune/models.py",
    "src/polisyos/scientist/compute/runner.py",
    "src/polisyos/scientist/decision_validity.py",
    "src/polisyos/scientist/orchestration/engine/checkpoint.py",
    "src/polisyos/scientist/orchestration/engine/metrics_otel.py",
    "src/polisyos/scientist/orchestration/engine/operational_monitoring.py",
    "src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py",
    "src/polisyos/scientist/error_semantics.py",
    "src/polisyos/scientist/governance/pipeline.py",
    "src/polisyos/scientist/governance/preflight.py",
    "src/polisyos/scientist/orchestration/llm/budget_enforcer.py",
    "src/polisyos/scientist/orchestration/llm/factory.py",
    "src/polisyos/scientist/orchestration/llm/profiles/registry.py",
    "src/polisyos/scientist/orchestration/llm/cycle.py",
    "src/polisyos/scientist/replay_backend.py",
    "src/polisyos/scientist/orchestration/workflows/builder.py",
    "src/polisyos/fabric/_connector_bridge.py",
    "src/polisyos/fabric/catalog/providers.py",
    "src/polisyos/fabric/catalog/resolver_fast_lane.py",
    "src/polisyos/fabric/connectors/bindings/registry.py",
    "src/polisyos/fabric/connectors/bindings/resolver.py",
    "src/polisyos/fabric/connectors/cache/_store_core.py",
    "src/polisyos/fabric/connectors/cache/prefetch.py",
    "src/polisyos/fabric/connectors/cache/proxy.py",
    "src/polisyos/fabric/connectors/profiles/registry.py",
    "src/polisyos/fabric/connectors/resilience/circuit_breaker.py",
    "src/polisyos/fabric/connectors/resilience/fallback.py",
    "src/polisyos/fabric/connectors/resilience/rate_limiter.py",
    "src/polisyos/fabric/data_plane/cli.py",
    "src/polisyos/fabric/data_plane/cursor_store.py",
    "src/polisyos/fabric/data_plane/modes.py",
    "src/polisyos/fabric/data_plane/orchestrator.py",
    "src/polisyos/fabric/data_plane/quarantine.py",
    "src/polisyos/fabric/data_plane/streaming.py",
    "src/polisyos/fabric/ingestion.py",
    "src/polisyos/fabric/ingestion_providers.py",
    "src/polisyos/fabric/retrieval/executor.py",
    "src/polisyos/fabric/retrieval/explore_lane.py",
    "src/polisyos/fabric/retrieval/providers.py",
    "src/polisyos/fabric/retrieval/service.py",
    "src/polisyos/fabric/storage/tenant_cas.py",
    "src/polisyos/fabric/world/events.py",
    "src/polisyos/fabric/world/providers.py",
    "src/polisyos/fabric/world/store/persist.py",
    "src/polisyos/fabric/world/store/segments.py",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run basedpyright over the full common/core/runtime surface and "
            "the curated scientist/scholar/fabric extras used by the release gate."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            "Optional files or directories to check instead of the default scopes. "
            "When provided, curated extras are skipped."
        ),
    )
    parser.add_argument(
        "--skip-curated-extras",
        action="store_true",
        help="Skip the curated scientist/scholar/fabric basedpyright pass.",
    )
    return parser


def _resolve_scope(raw_paths: tuple[str, ...] | list[str]) -> list[str]:
    resolved: list[str] = []
    for raw in raw_paths:
        path = Path(raw)
        if not path.is_absolute():
            path = PRODUCT_ROOT / path
        resolved.append(str(path.relative_to(PRODUCT_ROOT)))
    return resolved


def _run_scope(label: str, paths: list[str]) -> int:
    if not paths:
        return 0
    print(f"[basedpyright] {label}")
    completed = subprocess.run(
        ["basedpyright", "--project", "basedpyright.toml", *paths],
        cwd=PRODUCT_ROOT,
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.paths:
        requested = _resolve_scope(args.paths)
        return _run_scope("requested scope", requested)

    runtime_scope = _resolve_scope(DEFAULT_SCOPE)
    if _run_scope("full common/core/runtime surface", runtime_scope) != 0:
        return 1

    if args.skip_curated_extras:
        print("basedpyright passed for the requested core-runtime surface.")
        return 0

    curated_scope = _resolve_scope(CURATED_EXTRA_SCOPE)
    if _run_scope("curated scientist/scholar/fabric extras", curated_scope) != 0:
        return 1

    print("basedpyright passed for the full core-runtime gate surface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
