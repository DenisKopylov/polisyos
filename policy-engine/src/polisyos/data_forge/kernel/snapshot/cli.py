"""CLI entrypoints for Data Forge snapshot utilities."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .finalize import finalize_snapshot


def main() -> None:
    """Run Data Forge snapshot commands."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Data Forge snapshot utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    finalize = sub.add_parser("finalize", help="Aggregate pipeline publish manifests")
    finalize.add_argument("--snapshot-root", required=True)
    finalize.add_argument("--no-latest-symlink", action="store_true")

    args = parser.parse_args()
    if args.command == "finalize":
        finalize_snapshot(
            Path(args.snapshot_root),
            update_latest_symlink=not args.no_latest_symlink,
        )


if __name__ == "__main__":
    main()
