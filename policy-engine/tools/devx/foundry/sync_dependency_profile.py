#!/usr/bin/env python3
"""Preflight the Foundry-owned N8 dependency profile before any sync.

V1 intentionally has no sync path: the production owner reports the missing
runtime-subtree cutoff before inspecting tool binaries, cache content, an
appointment receipt, or a destination.  Keeping the complete future CLI shape
here prevents a caller from substituting a direct ``uv sync`` while ensuring
the current command performs no write.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from polisyos.foundry.methods.catalog.dependency_authority import (
    AbsoluteRequestPath,
    MethodCatalogDependencyAuthorityRequest,
    build_production_method_catalog_dependency_authority,
)

_PRODUCT_ROOT = Path(__file__).resolve().parents[3]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authority-purpose",
        choices=("n8_method_catalog_reconstruction",),
        required=True,
    )
    parser.add_argument("--tracked-source-root", type=Path, required=True)
    parser.add_argument("--source-freeze", required=True)
    parser.add_argument("--production-data-root", type=Path, required=True)
    parser.add_argument("--production-data-appointment", type=Path, required=True)
    parser.add_argument("--environment-root", type=Path, required=True)
    parser.add_argument("--python-bin", type=Path, required=True)
    parser.add_argument("--uv-bin", type=Path, required=True)
    parser.add_argument("--uv-cache-dir", type=Path, required=True)
    parser.add_argument("--offline", action="store_true", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Return the typed preflight non-receipt without crossing a write edge."""

    args = _parser().parse_args(argv)
    if args.tracked_source_root.resolve() != _PRODUCT_ROOT.resolve():
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "code": "tracked_source_root_mismatch",
                },
                sort_keys=True,
            )
        )
        return 1
    request = MethodCatalogDependencyAuthorityRequest(
        authority_purpose=args.authority_purpose,
        expected_source_freeze_commit=args.source_freeze,
        production_data_root=AbsoluteRequestPath(value=args.production_data_root),
        environment_root=AbsoluteRequestPath(value=args.environment_root),
    )
    result = build_production_method_catalog_dependency_authority().resolve(request)
    print(result.model_dump_json(exclude_none=False))
    return 1


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
