"""Public backends text plain module API."""
from __future__ import annotations


def normalize_plain_text_v1(text: str) -> str:
    """Return plain text as-is; decoding/normalization happens upstream."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    return text


__all__ = ["normalize_plain_text_v1"]
