"""Load and query the PolicyOS metrics → dataset indicator mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def load_metrics_map(path: Path) -> dict[str, dict[str, Any]]:
    """Load metrics_map.yaml into a dict keyed by metric_id."""
    import yaml

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"metrics_map.yaml must be a dict, got {type(data).__name__}")
    return data
