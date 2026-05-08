"""Public fabric segment manifest module API."""

from __future__ import annotations

from pathlib import Path

from polisyos.fabric.io.atomic import atomic_write_text
from polisyos.ir.loading.fact_log import FactSegmentManifest


def write_segment_manifest(manifest: FactSegmentManifest, manifest_path: Path) -> Path:
    """Write segment manifest helper."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path, manifest.model_dump_json(indent=2))
    return manifest_path
