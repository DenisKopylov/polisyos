"""Exports Scholar source-discovery helpers that normalize manual, URL, and file seeds."""

from __future__ import annotations

from .http_fetch import fetch_url
from .local_files import read_local_file
from .manual import normalize_seed_sources, source_identity_key

__all__ = [
    "fetch_url",
    "normalize_seed_sources",
    "read_local_file",
    "source_identity_key",
]
