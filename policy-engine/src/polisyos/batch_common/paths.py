"""Filesystem layout helpers for snapshot-based batch runs."""

from __future__ import annotations

from pathlib import Path


def snapshot_component_dir(snapshot_root: Path, component: str) -> Path:
    """Return `<snapshot_root>/<component>` and ensure it exists."""
    out = snapshot_root / component
    out.mkdir(parents=True, exist_ok=True)
    return out


def ensure_dirs(*paths: Path) -> None:
    """Create all provided directories if missing."""
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
