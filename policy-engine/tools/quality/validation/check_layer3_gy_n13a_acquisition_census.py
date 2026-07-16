#!/usr/bin/env python3
"""Inspect the read-only source identity for the GY-N13a acquisition census.

Task 1 establishes the typed boundary and catalog owner. Later N13a workstreams
extend this command with offline artifact validation and explicit live capture.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CatalogContractError,
    read_catalog_source,
)

DEFAULT_SOURCE_LOCATOR = (
    "production_data/datasets_full_phase3full_20260327_183054/"
    "dataset_catalog.duckdb"
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Task-1 catalog inspection CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-path",
        required=True,
        type=Path,
        help="Read-only path to dataset_catalog.duckdb",
    )
    parser.add_argument(
        "--source-locator",
        default=DEFAULT_SOURCE_LOCATOR,
        help="Stable logical locator recorded in catalog identity",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Print recomputed catalog identity and denominators as JSON."""

    args = build_parser().parse_args(argv)
    try:
        source = read_catalog_source(
            args.catalog_path,
            source_locator=args.source_locator,
        )
    except CatalogContractError as exc:
        print(
            json.dumps(
                {"issues": [{"code": exc.code, "detail": exc.detail}], "status": "fail"},
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {"catalog_source": source.model_dump(mode="json"), "status": "pass"},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
