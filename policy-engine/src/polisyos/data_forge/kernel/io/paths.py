"""Filesystem layout helpers shared by snapshot-based batch runs."""

from __future__ import annotations

from pathlib import Path


def snapshot_component_dir(snapshot_root: str | Path, component: str) -> Path:
    """Return `<snapshot_root>/<component>` and ensure it exists."""
    out = Path(snapshot_root) / component
    out.mkdir(parents=True, exist_ok=True)
    return out


def ensure_dirs(*paths: str | Path) -> None:
    """Create all provided directories if missing."""
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


__all__ = ["ensure_dirs", "snapshot_component_dir"]
