"""Content snapshots shared by catalog policy readers and producer receipts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class _MaterialFileSnapshot:
    path: Path
    raw: bytes | None
    selected: bool = True

    def generation_member(self, role: str) -> tuple[str, bytes]:
        """Bind file presence separately from the exact current file bytes."""
        presence = (
            "unselected" if not self.selected else ("present" if self.raw is not None else "absent")
        )
        return (f"{role}:{self.path}:{presence}", self.raw if self.raw is not None else b"")


def _material_file_snapshot(
    path: Path, *, required: bool = False, selected: bool = True
) -> _MaterialFileSnapshot:
    """Read one current file; preserve optional absence and propagate other errors."""
    resolved = path.resolve()
    if not selected:
        return _MaterialFileSnapshot(path=resolved, raw=None, selected=False)
    try:
        raw = resolved.read_bytes()
    except FileNotFoundError:
        if required:
            raise
        raw = None
    return _MaterialFileSnapshot(path=resolved, raw=raw)


@lru_cache(maxsize=32)
def _material_yaml_snapshot(snapshot: _MaterialFileSnapshot) -> object:
    """Parse UTF-8 YAML with a cache keyed by path, presence and current bytes."""
    if snapshot.raw is None:
        return None
    import yaml

    return yaml.safe_load(snapshot.raw.decode("utf-8"))
