"""Resolve SourceProfile -> ConnectionConfig for connector use."""

from __future__ import annotations

from polisyos.fabric.connectors.base import ConnectionConfig

from .models import SourceProfile


def resolve_connection_config(profile: SourceProfile) -> ConnectionConfig:
    """Convert a SourceProfile to a ConnectionConfig usable by connectors."""
    return ConnectionConfig(
        url=profile.base_url,
        headers=dict(profile.headers),
        auth_method=profile.auth_policy if profile.auth_policy != "none" else None,
        timeout_seconds=profile.timeout_seconds,
        max_retries=profile.max_retries,
        rate_limit_rps=profile.rate_limit_rps,
    )


__all__ = ["resolve_connection_config"]
