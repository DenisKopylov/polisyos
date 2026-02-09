from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

from polisyos.fabric.world import load_world_fact_manifests

_E = TypeVar("_E", bound=Exception)

__all__ = ["load_world_facts"]


def load_world_facts(
    fact_log_root: Path,
    *,
    columns: list[str],
    read_error_cls: type[_E] | None = None,
    read_error_prefix: str = "failed to read fact segment",
) -> pd.DataFrame:
    manifests = load_world_fact_manifests(fact_log_root)
    frames: list[pd.DataFrame] = []
    for manifest in manifests:
        path = Path(manifest.path)
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path, columns=columns)
        except Exception as exc:
            if read_error_cls is not None:
                raise read_error_cls(f"{read_error_prefix} {path}: {exc}") from exc
            raise
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)
