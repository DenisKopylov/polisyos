from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .capabilities import Capability
from .ids import ComponentId, SemVer, SemverRange
from .metadata import ComponentKind, ComponentMetadata
from .protocols import Component


class DuplicateComponentIdPolicy(str, Enum):
    WARN = "warn"
    ERROR = "error"
    IGNORE = "ignore"


class ResolvePolicy(str, Enum):
    EXACT = "exact"
    LATEST = "latest"
    LATEST_COMPATIBLE = "latest_compatible"


@dataclass(slots=True, frozen=True)
class SourcePrecedencePolicy:
    dev_scan_wins_over_entry_points: bool = True


@dataclass(slots=True)
class ComponentEntry:
    metadata: ComponentMetadata
    component: Component
    source: object | None = None


class ComponentRegistry:
    """Multi-version registry for discovered components."""

    def __init__(self) -> None:
        self._by_base_id: dict[str, dict[str, ComponentEntry]] = {}

    def register(
        self,
        entry: ComponentEntry,
        *,
        on_duplicate: DuplicateComponentIdPolicy = DuplicateComponentIdPolicy.ERROR,
        source_precedence: SourcePrecedencePolicy | None = None,
    ) -> None:
        base_id = entry.metadata.component_id.base_id
        version = entry.metadata.component_id.version

        versions = self._by_base_id.setdefault(base_id, {})
        existing = versions.get(version)
        if existing is None:
            versions[version] = entry
            return

        precedence = source_precedence or SourcePrecedencePolicy()
        if _should_replace(existing=existing, incoming=entry, precedence=precedence):
            versions[version] = entry
            return

        if on_duplicate == DuplicateComponentIdPolicy.IGNORE:
            return
        if on_duplicate == DuplicateComponentIdPolicy.WARN:
            return
        raise ValueError(f"Duplicate component_id: {entry.metadata.component_id}")

    def list_all(self) -> list[ComponentEntry]:
        rows: list[ComponentEntry] = []
        for base_id in sorted(self._by_base_id):
            rows.extend(self.list(base_id))
        return rows

    def list(self, base_id: str) -> list[ComponentEntry]:
        versions = self._by_base_id.get(base_id, {})
        ordered = sorted(versions.items(), key=lambda item: _version_sort_key(item[0]), reverse=True)
        return [entry for _, entry in ordered]

    def get(self, component_id: ComponentId | str) -> ComponentEntry | None:
        comp = ComponentId.parse(component_id) if isinstance(component_id, str) else component_id
        versions = self._by_base_id.get(comp.base_id)
        if versions is None:
            return None
        return versions.get(comp.version)

    def resolve(
        self,
        base_id: str,
        *,
        policy: ResolvePolicy = ResolvePolicy.LATEST,
        constraint: SemverRange | str | None = None,
    ) -> ComponentEntry | None:
        entries = self.matching_entries(base_id, constraint=constraint)
        if not entries:
            return None

        if policy == ResolvePolicy.LATEST:
            return entries[0]

        if policy == ResolvePolicy.EXACT:
            if isinstance(constraint, str):
                constraint_str = constraint.strip()
                if _is_exact_version(constraint_str):
                    versions = self._by_base_id.get(base_id, {})
                    return versions.get(constraint_str)
            if isinstance(constraint, SemverRange):
                exacts = [entry for entry in entries if constraint.matches(entry.metadata.component_id.version)]
                return exacts[0] if exacts else None
            return None

        if policy == ResolvePolicy.LATEST_COMPATIBLE:
            return entries[0]

        raise ValueError(f"Unknown resolve policy: {policy}")

    def query(
        self,
        *,
        kind: ComponentKind | None = None,
        domain: str | None = None,
        jurisdiction: str | None = None,
        capabilities: Capability | None = None,
        tags: Sequence[str] | None = None,
    ) -> list[ComponentEntry]:
        results: list[ComponentEntry] = []
        required_tags = set(tags or [])

        for entry in self.list_all():
            meta = entry.metadata
            if kind is not None and meta.kind != kind:
                continue
            if domain is not None and meta.domains and domain not in meta.domains:
                continue
            if jurisdiction is not None and meta.jurisdictions and jurisdiction not in meta.jurisdictions:
                continue
            if capabilities is not None and (meta.capabilities & capabilities) != capabilities:
                continue
            if required_tags and not required_tags.issubset(set(meta.tags)):
                continue
            results.append(entry)

        return results

    def matching_entries(
        self,
        base_id: str,
        *,
        constraint: SemverRange | str | None = None,
        kind: ComponentKind | None = None,
    ) -> list[ComponentEntry]:
        versions = self._by_base_id.get(base_id, {})
        if not versions:
            return []

        semver_range = _coerce_range(constraint)
        rows: list[ComponentEntry] = []
        for version, entry in versions.items():
            if kind is not None and entry.metadata.kind != kind:
                continue
            if semver_range is not None and not semver_range.matches(version):
                continue
            rows.append(entry)

        rows.sort(key=lambda item: _version_sort_key(item.metadata.component_id.version), reverse=True)
        return rows


# Backward compatibility names.
ConflictPolicy = DuplicateComponentIdPolicy


def _is_exact_version(value: str) -> bool:
    try:
        _ = SemVer.parse(value)
    except Exception:
        return False
    return True


def _coerce_range(value: SemverRange | str | None) -> SemverRange | None:
    if value is None:
        return None
    if isinstance(value, SemverRange):
        return value
    raw = value.strip()
    if not raw:
        return None
    if _is_exact_version(raw):
        return SemverRange.parse(raw)
    return SemverRange.parse(raw)


def _version_sort_key(version: str) -> tuple[int, int, int, int, tuple[str, ...]]:
    semver = SemVer.parse(version)
    return (
        semver.major,
        semver.minor,
        semver.patch,
        1 if not semver.prerelease else 0,
        semver.prerelease,
    )


def _source_type(entry: ComponentEntry) -> str:
    source = entry.source
    if source is None:
        return ""
    return str(getattr(source, "source_type", ""))


def _should_replace(
    *,
    existing: ComponentEntry,
    incoming: ComponentEntry,
    precedence: SourcePrecedencePolicy,
) -> bool:
    if not precedence.dev_scan_wins_over_entry_points:
        return False

    existing_source = _source_type(existing)
    incoming_source = _source_type(incoming)
    if existing_source == incoming_source:
        return False
    return existing_source == "entry_point" and incoming_source == "dev_scan"
