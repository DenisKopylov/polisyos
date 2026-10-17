"""Pure selection policy for safe local JAX backend defaults."""

from __future__ import annotations


def should_default_cpu_backend(
    *,
    platform: str,
    allow_metal: str | None,
    platforms: str | None,
    platform_name: str | None,
) -> bool:
    """Return whether macOS should receive Common's CPU backend defaults."""
    if platform != "darwin" or allow_metal == "1":
        return False
    requested = (platforms or platform_name or "").lower()
    return not requested or "metal" in requested
