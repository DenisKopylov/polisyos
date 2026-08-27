"""Scientist-owned command route for academic claim adjudication."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.artifacts import FileSystemCAS

from .claim_adjudication_runtime import (
    ClaimAdjudicationJSONClient,
    run_academic_claim_adjudication,
)
from .registry import ChampionRegistry

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import AcademicBatchConfig


async def run_claim_adjudication_command(
    config: AcademicBatchConfig,
    *,
    client: ClaimAdjudicationJSONClient | None = None,
    store: FileSystemCAS | None = None,
    registry: ChampionRegistry | None = None,
) -> dict[str, int | float]:
    """Execute the supported route, requiring an admitted Scientist champion."""
    if client is not None:
        return await run_academic_claim_adjudication(
            config,
            client=client,
            store=store,
            registry=registry,
        )

    from polisyos.data_forge.read_api.academic import GonkaMultiKeyPool

    async with GonkaMultiKeyPool(config) as pool:
        return await run_academic_claim_adjudication(
            config,
            client=pool,
            store=store,
            registry=registry,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run admitted academic claim adjudication")
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
    parser.add_argument("--temperature", type=float, default=0.1)
    return parser


def main() -> None:
    """Run the Scientist-owned claim-adjudication command."""
    from polisyos.data_forge.read_api.academic import AcademicBatchConfig

    args = _parser().parse_args()
    config = AcademicBatchConfig(
        snapshot_root=Path(args.snapshot_root),
        stages=frozenset({"claim_adjudicate"}),
        llm_model=args.model,
        llm_temperature=args.temperature,
    )
    result = asyncio.run(run_claim_adjudication_command(config))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()


__all__ = ["main", "run_claim_adjudication_command"]
