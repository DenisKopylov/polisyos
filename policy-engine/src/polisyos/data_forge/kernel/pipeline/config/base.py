"""Base configuration contracts for Data Forge pipelines."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

if TYPE_CHECKING:
    from collections.abc import Mapping


class SecretBackend(Protocol):
    """Secret provider protocol used by Data Forge config loaders."""

    def get(self, name: str) -> str | None:
        """Return the secret value for `name`, or None when unavailable."""


class DataForgeProfile(DataForgeModel):
    """Small immutable profile contract shared by future config composition."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    environment: str = Field(default="dev", pattern=r"^[a-z][a-z0-9_-]*$")
    labels: dict[str, str] = Field(default_factory=dict)


class SecretRef(DataForgeModel):
    """Reference to a named secret required by a batch profile."""

    name: str = Field(min_length=1)
    required: bool = True
    env_var: str | None = Field(default=None, min_length=1)

    def resolve(self, backend: SecretBackend) -> str | None:
        """Resolve this secret through a backend."""
        return backend.get(self.env_var or self.name)


@dataclass(frozen=True)
class MappingSecretBackend:
    """Secret backend backed by an in-memory mapping."""

    values: Mapping[str, str] = field(default_factory=dict)

    def get(self, name: str) -> str | None:
        """Return a secret from the configured mapping."""
        return self.values.get(name)


@dataclass(frozen=True)
class EnvSecretBackend:
    """Secret backend backed by process environment variables."""

    prefix: str = ""

    def get(self, name: str) -> str | None:
        """Return a secret from the process environment."""
        return os.environ.get(f"{self.prefix}{name}")


__all__ = [
    "DataForgeProfile",
    "EnvSecretBackend",
    "MappingSecretBackend",
    "SecretBackend",
    "SecretRef",
]
