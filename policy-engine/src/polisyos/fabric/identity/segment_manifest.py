"""Public fabric segment manifest module API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.fabric.io.atomic import atomic_write_text

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.ir.loading.fact_log import FactSegmentManifest


def write_segment_manifest(manifest: FactSegmentManifest, manifest_path: Path) -> Path:
    """Serialize a fact-segment manifest as indented JSON at the requested path.

    Parent directories are created when absent, and the text is written through
    the Fabric atomic-write helper.

    Args:
        manifest: Typed segment manifest to serialize.
        manifest_path: Destination path for the serialized manifest.

    Returns:
        The destination path after the write completes.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path, manifest.model_dump_json(indent=2))
    return manifest_path
