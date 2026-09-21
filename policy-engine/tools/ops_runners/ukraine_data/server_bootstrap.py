#!/usr/bin/env python3
"""Ops-facing owner for Ukraine server bootstrap composition.

The domain owns the typed configuration and capability manifest contracts.
This module is the executable-side seam that composes those contracts for a
remote server workflow; it intentionally does not import the ops layer from
``src/polisyos``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from polisyos.data_forge.domains.ukraine.models import (
    BuildRootConfig,
    PipelineConfig,
    ServerConfig,
)
from polisyos.data_forge.domains.ukraine.server import (
    build_bootstrap_script,
    probe_local_server_capabilities,
)
from polisyos.data_forge.domains.ukraine.orchestrator import (
    UkraineDataOrchestrator,
    load_pipeline_config,
)

__all__ = [
    "build_bootstrap_script",
    "build_orchestrator",
    "probe_local_server_capabilities",
    "render_bootstrap_script",
]


def render_bootstrap_script(config: ServerConfig, build_root: BuildRootConfig) -> str:
    """Render the reviewed server bootstrap command through the ops seam."""

    return build_bootstrap_script(config, build_root)


def build_orchestrator(
    config: PipelineConfig,
    workspace_root: Path | None,
) -> UkraineDataOrchestrator:
    """Compose the domain orchestrator with the ops-owned renderer callback."""

    return UkraineDataOrchestrator(
        config,
        workspace_root=workspace_root,
        bootstrap_script_renderer=render_bootstrap_script,
        server_capability_probe=probe_local_server_capabilities,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=None, help="Artifact/build root.")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Repository checkout used for server-side composition.",
    )
    parser.add_argument(
        "--write-capabilities",
        action="store_true",
        help="Write the server capability manifest during bootstrap.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run bootstrap through the ops-owned composition seam."""

    args = _build_parser().parse_args(argv)
    config = load_pipeline_config(args.config, root=args.root)
    summary = build_orchestrator(config, args.workspace_root).bootstrap_server(
        write_capabilities=args.write_capabilities,
    )
    print(json.dumps(summary.manifest.model_dump(mode="json"), ensure_ascii=True, indent=2))
    return 0 if summary.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
