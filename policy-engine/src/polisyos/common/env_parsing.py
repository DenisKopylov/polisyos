"""Shared environment-variable parsing helpers."""
from __future__ import annotations


def parse_bool(value: str | None, default: bool) -> bool:
    """Parse a boolean from an env-var string value."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(value: str | None, default: int) -> int:
    """Parse an int from an env-var string value."""
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def parse_float(value: str | None, default: float) -> float:
    """Parse a float from an env-var string value."""
    if value is None or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


__all__ = ["parse_bool", "parse_float", "parse_int"]
