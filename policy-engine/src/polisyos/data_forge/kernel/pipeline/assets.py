"""Asset identity and dependency contracts."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.artifacts import RetentionClass

from .partitions import NoPartition, PartitionSpec

ASSET_PART_PATTERN = r"^[a-z][a-z0-9_-]*$"


class AssetKey(DataForgeModel):
    """Stable namespaced key for an asset."""

    domain: str = Field(pattern=ASSET_PART_PATTERN)
    path: tuple[str, ...] = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        import re

        pattern = re.compile(ASSET_PART_PATTERN)
        invalid = [part for part in value if not pattern.fullmatch(part)]
        if invalid:
            raise ValueError(f"invalid asset key parts: {invalid}")
        return value

    @classmethod
    def from_parts(cls, domain: str, *path: str) -> AssetKey:
        """Create an asset key from path parts."""
        return cls(domain=domain, path=tuple(path))

    @classmethod
    def parse(cls, value: str) -> AssetKey:
        """Parse an asset key from `domain/path/...` form."""
        parts = tuple(part for part in value.split("/") if part)
        if len(parts) < 2:
            raise ValueError("asset key must have a domain and at least one path part")
        return cls(domain=parts[0], path=parts[1:])

    def __str__(self) -> str:
        return "/".join((self.domain, *self.path))


class AssetSpec(DataForgeModel):
    """Declarative specification for a materialized asset."""

    key: AssetKey
    deps: tuple[AssetKey, ...] = Field(default_factory=tuple)
    partitions: PartitionSpec = Field(default_factory=NoPartition)
    io: str | None = Field(default=None, min_length=1)
    schema_id: str | None = Field(default=None, min_length=1)
    freshness_sla_seconds: int | None = Field(default=None, ge=0)
    retention: RetentionClass = RetentionClass.HOT
    owner: str = Field(min_length=1)

    @model_validator(mode="after")
    def _cannot_depend_on_self(self) -> AssetSpec:
        if self.key in self.deps:
            raise ValueError(f"asset {self.key} cannot depend on itself")
        return self


class AssetGroup(DataForgeModel):
    """Named set of assets that should be planned or published together."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    assets: dict[str, AssetSpec] = Field(default_factory=dict)

    @classmethod
    def from_specs(cls, name: str, specs: tuple[AssetSpec, ...]) -> AssetGroup:
        """Create a group keyed by each asset's canonical string form."""
        return cls(name=name, assets={str(spec.key): spec for spec in specs})

    @model_validator(mode="after")
    def _keys_match_specs(self) -> AssetGroup:
        for key, spec in self.assets.items():
            if key != str(spec.key):
                raise ValueError(f"asset group key mismatch: {key} != {spec.key}")
        return self


__all__ = ["AssetGroup", "AssetKey", "AssetSpec"]
