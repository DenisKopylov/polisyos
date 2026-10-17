"""Pure text normalization helpers shared across PolicyOS packages.

This module has no domain dependencies and does not establish policy authority.
"""

from __future__ import annotations

import re

__all__ = ["collapse_ws"]


def collapse_ws(text: str) -> str:
    """Collapse every whitespace run to one space and trim the result."""
    return re.sub(r"\s+", " ", text.strip())
