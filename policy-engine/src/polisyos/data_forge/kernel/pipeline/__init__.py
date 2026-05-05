"""Asset-centric pipeline contracts for Data Forge."""

from __future__ import annotations

from .assets import AssetGroup, AssetKey, AssetSpec
from .manifests import (
    ArtifactRef,
    ChecksumValidationResult,
    ManifestArtifact,
    StageManifest,
    read_manifest,
    utc_now_iso,
    validate_manifest_artifacts,
    write_publish_manifest,
    write_raw_manifest,
    write_stage_manifest,
)
from .materialize import AssetDefinition, MaterializationContext, asset, plan_asset_specs
from .partitions import DailyPartition, HashPartition, NoPartition, PartitionSpec

__all__ = [
    "ArtifactRef",
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
    "StageManifest",
    "asset",
    "plan_asset_specs",
    "read_manifest",
    "utc_now_iso",
    "validate_manifest_artifacts",
    "write_publish_manifest",
    "write_raw_manifest",
    "write_stage_manifest",
]
