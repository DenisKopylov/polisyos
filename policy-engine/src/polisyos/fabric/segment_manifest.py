"""Public fabric segment manifest module API."""

from __future__ import annotations

from pathlib import Path

from polisyos.ir.fact_log import FactSegmentManifest


def write_segment_manifest(manifest: FactSegmentManifest, manifest_path: Path) -> Path:
    """Write segment manifest helper."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest_path
