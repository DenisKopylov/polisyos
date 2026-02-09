"""Exception hierarchy for the ConnectorRegistry."""

from __future__ import annotations

from polisyos.core.errors import ErrorCategory, PolicyOSError

__all__ = [
    "RegistryError",
    "ConnectorAlreadyRegisteredError",
    "ConnectorNotFoundError",
    "ConnectorConfigError",
    "AmbiguousConnectorError",
]


class RegistryError(PolicyOSError):
    """Base exception for registry-related errors."""

    default_stage = "fabric.connectors.registry"
    default_category = ErrorCategory.FATAL


class ConnectorAlreadyRegisteredError(RegistryError):
    """Raised when attempting to register a connector with existing ID."""

    default_category = ErrorCategory.VALIDATION

    def __init__(self, connector_id: str) -> None:
        self.connector_id = connector_id
        super().__init__(
            f"Connector '{connector_id}' already registered. Use override=True to replace."
        )


class ConnectorNotFoundError(RegistryError):
    """Raised when requested connector is not in registry."""

    default_category = ErrorCategory.VALIDATION

    def __init__(self, connector_id: str, available: list[str] | None = None) -> None:
        self.connector_id = connector_id
        self.available = available or []
        msg = f"Connector '{connector_id}' not found"
        if self.available:
            preview = self.available[:5]
            msg += f". Available: {preview}{'...' if len(self.available) > 5 else ''}"
        super().__init__(msg)


class ConnectorConfigError(RegistryError):
    """Raised when connector configuration is invalid."""

    default_category = ErrorCategory.VALIDATION

    def __init__(self, connector_id: str, reason: str) -> None:
        self.connector_id = connector_id
        self.reason = reason
        super().__init__(f"Configuration error for '{connector_id}': {reason}")


class AmbiguousConnectorError(RegistryError):
    """Raised when connector ID matches multiple connectors."""

    default_category = ErrorCategory.VALIDATION

    def __init__(self, connector_id: str, matches: list[str]) -> None:
        self.connector_id = connector_id
        self.matches = matches
        super().__init__(
            f"Ambiguous connector ID '{connector_id}'. Matches: {matches}"
        )
