#!/usr/bin/env python3
"""Build the Policy Evidence Capability Index release artifacts."""

# ruff: noqa: E501, T201, TC003

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.capability_index_compiler import (  # noqa: E402
    CapabilityIndexCompilerConfig,
    compile_capability_index,
    create_capability_index_fixture_inputs,
    write_phase1_architecture_profile,
)

DEFAULT_PRODUCTION_DATA_ROOT = Path("production_data")
DEFAULT_ARCHITECTURE_PROFILE = Path(
    "architecture/policy_design_case/capability_index_phase1_artifact_profile.json"
)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("fixture", "full", "incremental"),
        default="full",
        help="Build mode. Fixture creates tiny local source assets.",
    )
    parser.add_argument(
        "--production-data-root",
        type=Path,
        default=DEFAULT_PRODUCTION_DATA_ROOT,
        help="Production data root for full or incremental mode.",
    )
    parser.add_argument(
        "--previous-manifest",
        type=Path,
        default=None,
        help="Previous capability_index_v1.manifest.json for incremental mode.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for capability index artifacts.",
    )
    parser.add_argument(
        "--architecture-profile-out",
        type=Path,
        default=DEFAULT_ARCHITECTURE_PROFILE,
        help="Committed artifact profile path written by full mode.",
    )
    args = parser.parse_args(argv)

    output_dir = _resolve_repo_path(args.output_dir)
    if args.mode == "fixture":
        production_data_root = create_capability_index_fixture_inputs(output_dir / "_fixture_inputs")
    else:
        production_data_root = _resolve_repo_path(args.production_data_root)

    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=production_data_root,
            output_dir=output_dir,
            mode=args.mode,
            previous_manifest_path=_resolve_repo_path(args.previous_manifest)
            if args.previous_manifest
            else None,
        )
    )

    if args.mode == "full":
        write_phase1_architecture_profile(
            result.summary_path,
            _resolve_repo_path(args.architecture_profile_out),
        )

    print(
        json.dumps(
            {
                "status": "pass",
                "mode": args.mode,
                "output_dir": output_dir.as_posix(),
                "primary_duckdb": result.primary_duckdb_path.as_posix(),
                "summary": result.summary_path.as_posix(),
                "manifest": result.manifest_path.as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _resolve_repo_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    if path.is_absolute():
        return path
    return REPO_ROOT / path


if __name__ == "__main__":
    sys.exit(main())
