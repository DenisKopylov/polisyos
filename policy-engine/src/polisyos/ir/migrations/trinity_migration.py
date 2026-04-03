"""Trinity migration helpers."""
from __future__ import annotations

from typing import Any, Mapping

from polisyos.ir.trinity import TrinityBundle


def split_to_bundle(payload: TrinityBundle | Mapping[str, Any]) -> TrinityBundle:
    """Split to bundle helper."""
    if isinstance(payload, TrinityBundle):
        return payload
    return TrinityBundle.model_validate(payload)


def is_trinity_migrated(data: dict) -> bool:
    """Return whether is trinity migrated."""
    try:
        TrinityBundle.model_validate(data)
        return True
    except Exception:
        return False


__all__ = [
    "is_trinity_migrated",
    "split_to_bundle",
]
