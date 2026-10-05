#!/usr/bin/env python3
"""Compose the public Ukraine command with its ops-owned server callbacks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.ukraine import cli as domain_cli
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator

from . import server_bootstrap, validate_part_a

if TYPE_CHECKING:
    from polisyos.data_forge.domains.ukraine.models import PipelineConfig


def build_orchestrator(
    config: PipelineConfig,
    *,
    workspace_root: Path | None,
) -> UkraineDataOrchestrator:
    """Compose the domain facade with ops-owned server and repository-gate seams."""

    return UkraineDataOrchestrator(
        config,
        workspace_root=workspace_root,
        part_a_gate_runner=validate_part_a.run_part_a_gate,
        bootstrap_script_renderer=server_bootstrap.render_bootstrap_script,
        server_capability_probe=server_bootstrap.probe_local_server_capabilities,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the public Ukraine command through the ops composition owner."""

    return domain_cli.main(argv, orchestrator_factory=build_orchestrator)


if __name__ == "__main__":
    raise SystemExit(main())
