"""Trinity migration helpers."""
from __future__ import annotations

import logging
from typing import Any, Mapping

from pydantic import ValidationError

from polisyos.ir.trinity import TrinityBundle

logger = logging.getLogger(__name__)


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
    except ValidationError:
        return False
    except (TypeError, ValueError) as exc:
        logger.warning("Unexpected Trinity migration probe failure: %s", exc)
        return False


__all__ = [
    "is_trinity_migrated",
    "split_to_bundle",
]
