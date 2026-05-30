"""Public normpack provider registry module API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from polisyos.core.components import (
    ENTRY_POINT_GROUP_LEX_NORMPACKS,
    ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS,
    ComponentEntry,
    ComponentKind,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
    HostAbi,
    discover_components,
    validate_metadata,
)
from polisyos.core.components.ids import SemVer
from polisyos.core.registry.generic import GenericRegistry

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.loading.norm_pack import NormPack


class NormPackProvider(Protocol):
    """Norm pack provider implementation."""

    provider_id: str

    def get_static_norm_pack(
        self,
        cas: FileSystemCAS,
        *,
        jurisdiction: str,
        domain: str | None,
        as_of: str,
    ) -> NormPack | ArtifactRef | str: ...


@dataclass(slots=True)
class ProviderRecord:
    """Provider record data model."""

    component_id: str
    base_id: str
    version: str
    domains: list[str]
    jurisdictions: list[str]
    provider: NormPackProvider
    source: str


@dataclass(slots=True)
class ProviderBootstrapReport:
    """Provider bootstrap report data model."""

    registered: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovery_errors: list[str] = field(default_factory=list)


class NormPackProviderRegistry:
    """Norm pack provider registry implementation."""

    def __init__(self) -> None:
        self._records = GenericRegistry[str, ProviderRecord](
            key_fn=lambda record: record.component_id,
            indexers={
                "base_id": lambda record: record.base_id,
                "domains": lambda record: record.domains,
                "jurisdictions": lambda record: record.jurisdictions,
            },
        )

    def register(self, record: ProviderRecord) -> None:
        self._records.register(record, override=True)

    def resolve(self, *, jurisdiction: str, domain: str | None) -> ProviderRecord | None:
        records = self._records.values()
        if not records:
            return None

        ranked = sorted(
            records,
            key=lambda row: _provider_score(row=row, jurisdiction=jurisdiction, domain=domain),
            reverse=True,
        )
        selected = ranked[0]
        best = _provider_score(row=selected, jurisdiction=jurisdiction, domain=domain)
        if best[0] <= 0:
            return None
        return selected


_GLOBAL_REGISTRY = NormPackProviderRegistry()


def get_norm_pack_provider_registry() -> NormPackProviderRegistry:
    """Return norm pack provider registry."""
    return _GLOBAL_REGISTRY


def bootstrap_component_providers(components_index: ComponentRegistry) -> ProviderBootstrapReport:
    """Bootstrap component providers helper."""
    report = ProviderBootstrapReport()
    host = HostAbi(versions={"ir_abi": "1.0", "world_abi": "1.0"}, strict=True)

    for entry in components_index.query(kind=ComponentKind.NORM_PACK_PROVIDER):
        component_id = str(entry.metadata.component_id)
        issues = validate_metadata(
            entry.metadata,
            host_abi=host,
            available_components=components_index,
        )
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            report.errors.append(f"{component_id}: {'; '.join(issue.message for issue in errors)}")
            continue

        try:
            created = entry.component.create()
        except Exception as exc:
            report.errors.append(f"{component_id}: component.create() failed: {exc}")
            continue

        provider = _coerce_provider(created, component_id=entry.metadata.component_id.base_id)
        if provider is None:
            report.errors.append(f"{component_id}: provider must implement get_static_norm_pack()")
            continue

        _GLOBAL_REGISTRY.register(
            ProviderRecord(
                component_id=component_id,
                base_id=entry.metadata.component_id.base_id,
                version=entry.metadata.component_id.version,
                domains=list(entry.metadata.domains),
                jurisdictions=list(entry.metadata.jurisdictions),
                provider=provider,
                source=str(getattr(entry.source, "source_type", "entry_point")),
            )
        )
        report.registered.append(component_id)

    report.registered.sort()
    report.errors.sort()
    return report


def discover_and_bootstrap_providers(
    *,
    include_dev_scan: bool = True,
    components_index: ComponentRegistry | None = None,
) -> ProviderBootstrapReport:
    """Discover and bootstrap providers helper."""
    if components_index is not None:
        return bootstrap_component_providers(components_index)

    discovered = discover_components(
        groups=[ENTRY_POINT_GROUP_LEX_NORMPACKS, ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS],
        include_dev_scan=include_dev_scan,
    )

    registry = ComponentRegistry()
    for row in discovered.components:
        registry.register(
            ComponentEntry(metadata=row.metadata, component=row.component, source=row.source),
            on_duplicate=DuplicateComponentIdPolicy.WARN,
        )

    report = bootstrap_component_providers(registry)
    report.discovery_errors = [
        f"{error.source}:{error.item or '<unknown>'}: {error.message}"
        for error in discovered.errors
    ]
    report.discovery_errors.sort()
    return report


def _coerce_provider(value: Any, *, component_id: str) -> NormPackProvider | None:
    if hasattr(value, "get_static_norm_pack") and callable(value.get_static_norm_pack):
        if not hasattr(value, "provider_id"):
            value.provider_id = component_id
        return value

    if callable(value):

        class _FnProvider:
            provider_id = component_id

            @staticmethod
            def get_static_norm_pack(
                cas: FileSystemCAS,
                *,
                jurisdiction: str,
                domain: str | None,
                as_of: str,
            ) -> NormPack | ArtifactRef | str:
                return value(
                    cas=cas,
                    jurisdiction=jurisdiction,
                    domain=domain,
                    as_of=as_of,
                )

        return _FnProvider()

    return None


def _provider_score(
    *,
    row: ProviderRecord,
    jurisdiction: str,
    domain: str | None,
) -> tuple[int, int, int, int, str]:
    score = 0

    if domain is not None:
        if domain in row.domains:
            score += 100
        elif not row.domains:
            score += 10
    elif not row.domains:
        score += 1

    if row.jurisdictions:
        if jurisdiction in row.jurisdictions:
            score += 100
        else:
            score -= 1000
    else:
        score += 5

    semver = SemVer.parse(row.version)
    prerelease_rank = 0 if semver.prerelease else 1
    return (score, semver.major, semver.minor, semver.patch + prerelease_rank, row.component_id)


__all__ = [
    "NormPackProvider",
    "NormPackProviderRegistry",
    "ProviderBootstrapReport",
    "discover_and_bootstrap_providers",
    "get_norm_pack_provider_registry",
]
