"""Public lex common module API."""

from __future__ import annotations

import re

from polisyos.common.timestamps import latest_object_by_subject, parse_iso_date

__all__ = ["collapse_ws", "latest_object_by_subject", "parse_iso_date"]


def collapse_ws(text: str) -> str:
    """Collapse ws helper."""
    return re.sub(r"\s+", " ", text.strip())
