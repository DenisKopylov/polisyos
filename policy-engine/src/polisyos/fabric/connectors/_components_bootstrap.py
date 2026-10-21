"""Private, registry-independent connector component bootstrap implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

from polisyos.core.components import (
    ComponentEntry,
    ComponentKind,
    ComponentRegistry,
    HostAbi,
    validate_metadata,
)

from ._registry_errors import ConnectorAlreadyRegisteredError
from .capabilities import validate_protocol_compliance

if TYPE_CHECKING:
    from collections.abc import Callable

    from .base import ConnectionConfig, SourceConnector


class BootstrapTarget(Protocol):
    """Register-only target used after the component bridge validates a candidate."""

    def register(
        self,
        connector_class: type[SourceConnector[Any]],
        config: ConnectionConfig | None = None,
        *,
        override: bool = False,
        factory: Callable[[], SourceConnector[Any]] | None = None,
    ) -> str: ...


class _ComponentsBootstrapOutcome(NamedTuple):
    """Internal result consumed by lifecycle bootstrap and the public bridge."""

    registered: list[str]
    duplicates: list[str]
    errors: list[str]


def bootstrap_components_into_registry(
    components_index: ComponentRegistry,
    registry: BootstrapTarget,
    *,
    allow_dev_overrides: bool = True,
) -> _ComponentsBootstrapOutcome:
    """Validate connector components and register them into the supplied target."""
    registered: list[str] = []
    duplicates: list[str] = []
    errors: list[str] = []

    host = HostAbi(
        versions={
            "fabric_connectors_api": "2.2.0",
            "fabric_api": "2.2.0",
        },
        strict=True,
    )

    entries = list(components_index.query(kind=ComponentKind.FABRIC_CONNECTOR))

    for entry in sorted(entries, key=lambda item: str(item.metadata.component_id)):
        component_id = str(entry.metadata.component_id)

        issues = validate_metadata(
            entry.metadata,
            host_abi=host,
            available_components=components_index,
            component=entry.component,
        )
        metadata_errors = [issue.message for issue in issues if issue.severity == "error"]
        if metadata_errors:
            errors.append(f"{component_id}: {'; '.join(metadata_errors)}")
            continue

        try:
            created = entry.component.create()
        except Exception as exc:
            errors.append(f"{component_id}: component.create() failed: {exc}")
            continue

        connector_class = _coerce_connector_class(created)
        if connector_class is None:
            errors.append(f"{component_id}: component must create connector class or instance")
            continue

        connector_metadata = getattr(connector_class, "metadata", None)
        if connector_metadata is None:
            errors.append(f"{component_id}: connector class must declare metadata")
            continue

        fqid = getattr(connector_metadata, "fully_qualified_id", None)
        fqid_str = str(fqid) if fqid is not None else ""
        if fqid_str != component_id:
            errors.append(f"{component_id}: component_id must equal connector fqid: {fqid_str!r}")
            continue

        protocol_violations = validate_protocol_compliance(connector_class)
        if protocol_violations:
            errors.append(f"{component_id}: protocol violations: {'; '.join(protocol_violations)}")
            continue

        override = allow_dev_overrides and _is_dev_scan(entry)

        try:
            registered_fqid = registry.register(connector_class, override=override)
            registered.append(registered_fqid)
        except ConnectorAlreadyRegisteredError:
            duplicates.append(component_id)
        except Exception as exc:
            message = str(exc)
            if "already registered" in message.casefold():
                duplicates.append(component_id)
            else:
                errors.append(f"{component_id}: {message}")

    registered.sort()
    duplicates.sort()
    errors.sort()
    return _ComponentsBootstrapOutcome(registered, duplicates, errors)


def _coerce_connector_class(value: object) -> type | None:
    if isinstance(value, type):
        return value
    return type(value) if value is not None else None


def _is_dev_scan(entry: ComponentEntry) -> bool:
    source_type = str(getattr(entry.source, "source_type", ""))
    return source_type == "dev_scan"
