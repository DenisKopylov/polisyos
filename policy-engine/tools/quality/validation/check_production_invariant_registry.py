#!/usr/bin/env python3
"""Validate the Production Invariant Registry against runtime reader catalogs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lib.imports import ensure_repo_import_roots

if TYPE_CHECKING:
    from collections.abc import Sequence

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.invariants import (  # noqa: E402
    DEFAULT_REGISTRY_RELATIVE_PATH,
    build_production_invariant_registry_report,
    dump_registry_report_json,
    render_registry_report_text,
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY_RELATIVE_PATH,
        help="Path to architecture/production_quality/invariant_registry.toml.",
    )
    parser.add_argument(
        "--output-format",
        choices=("text", "json"),
        default="text",
        help="Render a compact text report or the full machine-readable diff.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = build_production_invariant_registry_report(
            repo_root=args.repo_root,
            registry_path=args.registry,
        )
    except (FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"production invariant registry check failed: {exc}\n")
        return 2

    output = (
        dump_registry_report_json(report)
        if args.output_format == "json"
        else render_registry_report_text(report)
    )
    stream = sys.stdout if report["status"] == "pass" else sys.stderr
    stream.write(output)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
