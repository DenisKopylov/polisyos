"""Load and validate dataset source registry for staged harvest waves."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceSpec:
    name: str
    family: str
    wave: str
    endpoint: str
    enabled: bool = True
    agency_prefix: str = ""
    agency_allowlist: tuple[str, ...] = ()
    exclude_agencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    version: int
    sources: tuple[SourceSpec, ...] = field(default_factory=tuple)

    def enabled_sources(self, *, wave: str | None = None) -> list[SourceSpec]:
        out = [s for s in self.sources if s.enabled]
        if wave:
            out = [s for s in out if s.wave.upper() == wave.upper()]
        return out


def load_source_registry(path: Path) -> SourceRegistry:
    """Load YAML source registry from disk."""
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}

    if not isinstance(payload, dict):
        raise ValueError("source_registry.yaml must be a mapping")

    version = int(payload.get("version", 1))
    raw_sources = payload.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError("source_registry.yaml 'sources' must be a list")

    parsed: list[SourceSpec] = []
    for row in raw_sources:
        if not isinstance(row, dict):
            continue
        parsed.append(
            SourceSpec(
                name=str(row.get("name", "")).strip(),
                family=str(row.get("family", "")).strip(),
                wave=str(row.get("wave", "")).strip().upper(),
                endpoint=str(row.get("endpoint", "")).strip(),
                enabled=bool(row.get("enabled", True)),
                agency_prefix=str(row.get("agency_prefix", "")).strip(),
                agency_allowlist=tuple(str(v) for v in (row.get("agency_allowlist") or [])),
                exclude_agencies=tuple(str(v) for v in (row.get("exclude_agencies") or [])),
            )
        )

    for spec in parsed:
        if not spec.name or not spec.family or not spec.wave or not spec.endpoint:
            raise ValueError(f"Invalid source spec: {spec}")

    return SourceRegistry(version=version, sources=tuple(parsed))
