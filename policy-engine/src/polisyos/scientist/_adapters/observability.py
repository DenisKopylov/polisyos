"""Scientist observability adapter backed by core observability."""

from __future__ import annotations

from typing import Any

from polisyos.core.observability import get_metrics as _core_get_metrics


def get_metrics() -> Any:
    """Return the canonical metrics registry for Scientist runtime helpers."""
    return _core_get_metrics()


__all__ = ["get_metrics"]
