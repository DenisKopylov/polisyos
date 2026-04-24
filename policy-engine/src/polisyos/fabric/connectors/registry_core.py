"""Decomposed module wrapper; implementation moved to `registry_core_parts`."""

from ._registry_errors import (
    AmbiguousConnectorError,
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorNotFoundError,
    RegistryError,
)
from .registry_core_parts import (
    ConnectorEntry,
    ConnectorPreferences,
    ConnectorRegistry,
    RegistryMetrics,
    RegistryStats,
)

__all__ = [
    "AmbiguousConnectorError",
    "ConnectorAlreadyRegisteredError",
    "ConnectorConfigError",
    "ConnectorEntry",
    "ConnectorNotFoundError",
    "ConnectorPreferences",
    "ConnectorRegistry",
    "RegistryError",
    "RegistryMetrics",
    "RegistryStats",
]
