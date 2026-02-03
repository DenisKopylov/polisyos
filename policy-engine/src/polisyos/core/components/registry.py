from __future__ import annotations

from enum import Enum
from typing import Iterable

from .capabilities import Capability
from .ids import ComponentId
from .metadata import ComponentMetadata
from .protocols import ComponentProvider


class ConflictPolicy(str, Enum):
    ERROR = "error"
    PREFER_HIGHEST_SEMVER = "prefer_highest_semver"
    FIRST_WINS = "first_wins"


def _semver_key(version: str) -> tuple[int, int, int, int, str]:
    """Best-effort semver ordering key.

    Returns (major, minor, patch, is_release, prerelease).
    """
    parts = version.split("-", 1)
    core = parts[0].split("+", 1)[0]
    prerelease = parts[1] if len(parts) > 1 else ""
    core_parts = core.split(".")
    try:
        major = int(core_parts[0])
        minor = int(core_parts[1])
        patch = int(core_parts[2])
    except Exception:
        return (0, 0, 0, 0, version)
    is_release = 1 if not prerelease else 0
    return (major, minor, patch, is_release, prerelease)


class ComponentRegistry:
    """Registry for discovered/installed components."""

    def __init__(self) -> None:
        self._components: dict[str, ComponentMetadata] = {}
        self._providers: dict[str, ComponentProvider] = {}

    @staticmethod
    def _component_key(component_id: ComponentId) -> str:
        return f"{component_id.namespace}.{component_id.name}"

    def register(
        self,
        metadata: ComponentMetadata,
        provider: ComponentProvider | None = None,
        *,
        policy: ConflictPolicy = ConflictPolicy.ERROR,
    ) -> None:
        key = self._component_key(metadata.component_id)
        if key not in self._components:
            self._components[key] = metadata
            if provider is not None:
                self._providers[key] = provider
            return

        if policy == ConflictPolicy.FIRST_WINS:
            return
        if policy == ConflictPolicy.ERROR:
            raise ValueError(f"Duplicate component_id: {metadata.component_id}")

        if policy == ConflictPolicy.PREFER_HIGHEST_SEMVER:
            existing = self._components[key]
            existing_key = _semver_key(existing.component_id.version)
            incoming_key = _semver_key(metadata.component_id.version)
            if incoming_key >= existing_key:
                self._components[key] = metadata
                if provider is not None:
                    self._providers[key] = provider
            return

        raise ValueError(f"Unknown conflict policy: {policy}")

    def get(self, component_id: ComponentId | str) -> ComponentMetadata | None:
        comp = ComponentId.parse(component_id) if isinstance(component_id, str) else component_id
        key = self._component_key(comp)
        meta = self._components.get(key)
        if meta is None or meta.component_id != comp:
            return None
        return meta

    def get_provider(self, component_id: ComponentId | str) -> ComponentProvider | None:
        comp = ComponentId.parse(component_id) if isinstance(component_id, str) else component_id
        key = self._component_key(comp)
        meta = self._components.get(key)
        if meta is None or meta.component_id != comp:
            return None
        return self._providers.get(key)

    def list(self) -> list[ComponentMetadata]:
        return list(self._components.values())

    def query(
        self,
        *,
        capabilities: Capability | None = None,
        domain: str | None = None,
        jurisdiction: str | None = None,
        tag: str | None = None,
    ) -> list[ComponentMetadata]:
        items: Iterable[ComponentMetadata] = self._components.values()
        results: list[ComponentMetadata] = []
        for meta in items:
            if capabilities is not None and not (meta.capabilities & capabilities) == capabilities:
                continue
            if domain is not None and domain not in meta.domains:
                continue
            if jurisdiction is not None and jurisdiction not in meta.jurisdictions:
                continue
            if tag is not None and tag not in meta.tags:
                continue
            results.append(meta)
        return results
