"""Compatibility import path for the public selected-artifact intake helper."""

from __future__ import annotations

from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    read_optional_selected_artifact,
)

__all__ = ["CanonicalProfileRefusalError", "read_optional_selected_artifact"]
