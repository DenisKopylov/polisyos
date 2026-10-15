#!/usr/bin/env python3
"""Compose the public Ukraine CLI with its Ops-owned process boundaries."""

from __future__ import annotations

from polisyos.data_forge.domains.ukraine.cli import main as _domain_main
from tools.ops_runners.ukraine_data.server_bootstrap import build_orchestrator


def main(argv: list[str] | None = None) -> int:
    """Run the domain command interface using the complete Ops composition."""

    return _domain_main(argv, orchestrator_factory=build_orchestrator)


if __name__ == "__main__":
    raise SystemExit(main())
