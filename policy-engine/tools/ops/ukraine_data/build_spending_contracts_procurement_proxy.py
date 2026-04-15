#!/usr/bin/env python3
"""Materialize the Spending contracts procurement proxy as a standalone source run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from polisyos.ukraine_data.adapters import SourceExecutionContext, build_default_adapter_registry
from polisyos.ukraine_data.manifests import (
    SkippedSourceManifest,
    write_manifest,
)
from polisyos.ukraine_data.orchestrator import load_pipeline_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_spending_contracts_procurement_proxy",
        description="Build the Spending contracts procurement proxy without running the full D0 stage.",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to JSON pipeline config.")
    parser.add_argument("--root", type=Path, default=None, help="Override build root for manifests and artifacts.")
    parser.add_argument(
        "--local-path",
        type=Path,
        default=None,
        help="Override the raw Spending source directory. Defaults to the spending_full local_path or raw/spending_full.",
    )
    return parser


def _resolve_local_path(config, override: Path | None) -> Path:
    if override is not None:
        return override
    proxy_source = config.sources["spending_contracts_procurement_proxy"]
    if proxy_source.local_path is not None:
        return proxy_source.local_path
    spending_source = config.sources.get("spending_full")
    if spending_source is not None and spending_source.local_path is not None:
        return spending_source.local_path
    return config.build_root.raw_dir / "spending_full"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_pipeline_config(args.config, root=args.root)
    source = config.sources["spending_contracts_procurement_proxy"].model_copy(deep=True)
    source.local_path = _resolve_local_path(config, args.local_path)
    adapter = build_default_adapter_registry()[source.adapter_id]
    ctx = SourceExecutionContext(config.build_root)
    snapshot = adapter.fetch(source, ctx)
    if isinstance(snapshot, SkippedSourceManifest):
        sys.stdout.write(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=True, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return 0

    normalized = adapter.normalize(source, snapshot, ctx)
    findings = adapter.validate(source, normalized)
    if findings:
        normalized = normalized.model_copy(update={"findings": [*normalized.findings, *findings]})
        normalized_path = write_manifest(ctx.manifest_dir(source.source_id) / source.manifest_name, normalized)
    else:
        normalized_path = ctx.manifest_dir(source.source_id) / source.manifest_name
    payload = {
        "source_id": source.source_id,
        "raw_source_path": str(source.local_path),
        "source_snapshot_manifest": str(ctx.manifest_dir(source.source_id) / "source_snapshot_manifest.json"),
        "normalized_manifest": str(normalized_path),
        "normalized_artifact": str(normalized.normalized_artifact.path),
        "row_count": normalized.normalized_artifact.row_count,
        "findings": [finding.model_dump(mode="json") for finding in normalized.findings],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if not any(finding.severity == "error" for finding in normalized.findings) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
