"""Base configuration contracts for Data Forge pipelines."""

from __future__ import annotations

from typing import Protocol

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel


class SecretBackend(Protocol):
    """Secret provider protocol used by Data Forge config loaders."""

    def get(self, name: str) -> str | None:
        """Return the secret value for `name`, or None when unavailable."""


class DataForgeProfile(DataForgeModel):
    """Small immutable profile contract shared by future config composition."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    environment: str = Field(default="dev", pattern=r"^[a-z][a-z0-9_-]*$")
    labels: dict[str, str] = Field(default_factory=dict)


__all__ = ["DataForgeProfile", "SecretBackend"]
