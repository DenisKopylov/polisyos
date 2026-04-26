"""Asset-centric pipeline contracts for Data Forge."""

from __future__ import annotations

from .assets import AssetGroup, AssetKey, AssetSpec
from .manifests import (
    ChecksumValidationResult,
    ManifestArtifact,
    read_manifest,
    validate_manifest_artifacts,
    write_publish_manifest,
    write_raw_manifest,
    write_stage_manifest,
)
from .materialize import AssetDefinition, MaterializationContext, asset, plan_asset_specs
from .partitions import DailyPartition, HashPartition, NoPartition, PartitionSpec

__all__ = [
    "AssetDefinition",
    "AssetGroup",
    "AssetKey",
    "AssetSpec",
    "ChecksumValidationResult",
    "DailyPartition",
    "HashPartition",
    "ManifestArtifact",
    "MaterializationContext",
    "NoPartition",
    "PartitionSpec",
    "asset",
    "plan_asset_specs",
    "read_manifest",
    "validate_manifest_artifacts",
    "write_publish_manifest",
    "write_raw_manifest",
    "write_stage_manifest",
]
