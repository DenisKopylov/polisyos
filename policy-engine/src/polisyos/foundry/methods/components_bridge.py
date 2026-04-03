"""Bridge component-registry entries into lazy Foundry method registrations."""
from __future__ import annotations

from dataclasses import dataclass, field

from polisyos.core.components import ComponentKind, ComponentRegistry, HostAbi, validate_metadata
from polisyos.foundry.methods.base import FoundryMethod, MethodMetadata, MethodSignature
from polisyos.foundry.methods.discovery import is_foundry_method
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.resolution import ResolutionPolicy

FOUNDRY_METHODS_API_VERSION = "3.5.0"


@dataclass(slots=True)
class ComponentsBridgeError:
    """Record why a component entry could not be promoted into the method registry."""
    component_id: str
    message: str


@dataclass(slots=True)
class ComponentsBridgeReport:
    """Summarize which component-backed methods were registered, skipped, or rejected."""
    registered: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[ComponentsBridgeError] = field(default_factory=list)


def bootstrap_method_registry_from_components(
    components_index: ComponentRegistry,
    registry: MethodRegistry | None = None,
    *,
    resolution_policy: ResolutionPolicy = ResolutionPolicy.LATEST,
    allow_dev_overrides: bool = True,
) -> ComponentsBridgeReport:
    """Load component-backed methods before discovery, snapshots, or CLI catalog listing."""
    method_registry = registry or MethodRegistry.get_instance()
    method_registry.set_default_policy(resolution_policy)

    report = ComponentsBridgeReport()
    entries = components_index.query(kind=ComponentKind.FOUNDRY_METHOD)

    host_abi = HostAbi(
        versions={"foundry_methods_api": FOUNDRY_METHODS_API_VERSION},
        strict=True,
    )

    for entry in entries:
        component_id = str(entry.metadata.component_id)
        issues = validate_metadata(
            entry.metadata,
            host_abi=host_abi,
            available_components=components_index,
        )
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            report.errors.append(
                ComponentsBridgeError(
                    component_id=component_id,
                    message="; ".join(issue.message for issue in errors),
                )
            )
            continue

        try:
            method_cls = entry.component.create()
        except Exception as exc:
            report.errors.append(
                ComponentsBridgeError(
                    component_id=component_id,
                    message=f"component.create() failed: {exc}",
                )
            )
            continue

        if not isinstance(method_cls, type) or not is_foundry_method(method_cls):
            report.errors.append(
                ComponentsBridgeError(
                    component_id=component_id,
                    message="component must create FoundryMethod class",
                )
            )
            continue

        signature = _extract_signature(method_cls)
        metadata = _merge_metadata(method_cls=method_cls, component_tags=entry.metadata.tags, domains=entry.metadata.domains)

        if signature.fqn != component_id:
            report.errors.append(
                ComponentsBridgeError(
                    component_id=component_id,
                    message=(
                        f"component_id must equal method signature fqn: {signature.fqn!r}"
                    ),
                )
            )
            continue

        override = allow_dev_overrides and str(getattr(entry.source, "source_type", "")) == "dev_scan"

        try:
            method_registry.register_lazy(
                signature=signature,
                metadata=metadata,
                factory=lambda cls=method_cls: cls,
                override=override,
            )
            report.registered.append(signature.fqn)
        except Exception as exc:
            message = str(exc)
            if "already registered" in message.casefold():
                report.duplicates.append(signature.fqn)
            else:
                report.errors.append(
                    ComponentsBridgeError(
                        component_id=component_id,
                        message=message,
                    )
                )

    report.registered.sort()
    report.duplicates.sort()
    return report


def _extract_signature(method_cls: type[FoundryMethod]) -> MethodSignature:
    return method_cls.signature


def _merge_metadata(
    *,
    method_cls: type[FoundryMethod],
    component_tags: list[str],
    domains: list[str],
) -> MethodMetadata:
    meta = method_cls.metadata
    tags = set(meta.tags)
    tags.update(component_tags)
    tags.update({f"domain:{domain}" for domain in domains})
    return MethodMetadata(
        description=meta.description,
        tags=frozenset(tags),
        citations=meta.citations,
        equations=meta.equations,
    )


__all__ = [
    "ComponentsBridgeError",
    "ComponentsBridgeReport",
    "bootstrap_method_registry_from_components",
]
FOUNDRY_METHODS_API_VERSION = "3.5.0"
