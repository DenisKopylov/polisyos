from __future__ import annotations

from dataclasses import dataclass, field

from polisyos.core.components import (
    ComponentKind,
    ComponentRegistry,
    HostAbi,
    validate_metadata,
)
from polisyos.core.components.registry import ComponentEntry

from .capabilities import validate_protocol_compliance
from .registry import ConnectorAlreadyRegisteredError, ConnectorRegistry


@dataclass(slots=True)
class ComponentsBridgeError:
    component_id: str
    message: str


@dataclass(slots=True)
class ComponentsBridgeReport:
    registered: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def bootstrap_connector_registry_from_components(
    components_index: ComponentRegistry,
    registry: ConnectorRegistry | None = None,
    *,
    allow_dev_overrides: bool = True,
) -> ComponentsBridgeReport:
    connector_registry = ConnectorRegistry.get_instance(bootstrap=False) if registry is None else registry
    report = ComponentsBridgeReport()

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
        errors = [issue.message for issue in issues if issue.severity == "error"]
        if errors:
            report.errors.append(f"{component_id}: {'; '.join(errors)}")
            continue

        try:
            created = entry.component.create()
        except Exception as exc:
            report.errors.append(f"{component_id}: component.create() failed: {exc}")
            continue

        connector_class = _coerce_connector_class(created)
        if connector_class is None:
            report.errors.append(
                f"{component_id}: component must create connector class or instance"
            )
            continue

        fqid = getattr(connector_class.metadata, "fully_qualified_id", None)
        fqid_str = str(fqid) if fqid is not None else ""
        if fqid_str != component_id:
            report.errors.append(
                f"{component_id}: component_id must equal connector fqid: {fqid_str!r}"
            )
            continue

        protocol_violations = validate_protocol_compliance(connector_class)
        if protocol_violations:
            report.errors.append(
                f"{component_id}: protocol violations: {'; '.join(protocol_violations)}"
            )
            continue

        override = allow_dev_overrides and _is_dev_scan(entry)

        try:
            registered_fqid = connector_registry.register(
                connector_class,
                override=override,
            )
            report.registered.append(registered_fqid)
        except ConnectorAlreadyRegisteredError:
            report.duplicates.append(component_id)
        except Exception as exc:
            message = str(exc)
            if "already registered" in message.casefold():
                report.duplicates.append(component_id)
            else:
                report.errors.append(f"{component_id}: {message}")

    report.registered.sort()
    report.duplicates.sort()
    report.errors.sort()
    return report


def _coerce_connector_class(value: object) -> type | None:
    if isinstance(value, type):
        return value
    return type(value) if value is not None else None


def _is_dev_scan(entry: ComponentEntry) -> bool:
    source_type = str(getattr(entry.source, "source_type", ""))
    return source_type == "dev_scan"


__all__ = [
    "ComponentsBridgeError",
    "ComponentsBridgeReport",
    "bootstrap_connector_registry_from_components",
]
