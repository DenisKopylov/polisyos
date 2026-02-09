"""Compatibility facade for connector registry APIs.

Implementation was split into ``registry_core.py`` to keep this public module
stable while reducing monolithic file size.
"""

from polisyos.fabric.connectors.registry_core import (
    AmbiguousConnectorError,
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorEntry,
    ConnectorNotFoundError,
    ConnectorPreferences,
    ConnectorRegistry,
    RegistryError,
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
