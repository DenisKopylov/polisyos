"""Data Forge public facade for build-time artifact contracts and read APIs."""

from __future__ import annotations

from importlib import import_module

from . import read_api
from ._version import __version__

_EXPORTS = {
    "ArtifactRef": ("polisyos.data_forge.kernel.artifacts", "ArtifactRef"),
    "AssetDefinition": ("polisyos.data_forge.kernel.pipeline", "AssetDefinition"),
    "AssetGroup": ("polisyos.data_forge.kernel.pipeline", "AssetGroup"),
    "AssetKey": ("polisyos.data_forge.kernel.pipeline", "AssetKey"),
    "AssetSpec": ("polisyos.data_forge.kernel.pipeline", "AssetSpec"),
    "CompatibilityMode": ("polisyos.data_forge.kernel.schemas", "CompatibilityMode"),
    "DataForgeError": ("polisyos.data_forge.errors", "DataForgeError"),
    "DataForgeValidationError": (
        "polisyos.data_forge.errors",
        "DataForgeValidationError",
    ),
    "DifferentialComparison": (
        "polisyos.data_forge.kernel.testing",
        "DifferentialComparison",
    ),
    "GoldenArtifact": ("polisyos.data_forge.kernel.testing", "GoldenArtifact"),
    "GoldenCase": ("polisyos.data_forge.kernel.testing", "GoldenCase"),
    "MaterializationContext": (
        "polisyos.data_forge.kernel.pipeline",
        "MaterializationContext",
    ),
    "PIILevel": ("polisyos.data_forge.kernel.artifacts", "PIILevel"),
    "ProducerVersion": ("polisyos.data_forge.kernel.artifacts", "ProducerVersion"),
    "QCCheck": ("polisyos.data_forge.kernel.quality", "QCCheck"),
    "QCReport": ("polisyos.data_forge.kernel.quality", "QCReport"),
    "RetentionClass": ("polisyos.data_forge.kernel.artifacts", "RetentionClass"),
    "SchemaCompatibilityError": (
        "polisyos.data_forge.errors",
        "SchemaCompatibilityError",
    ),
    "SchemaRegistry": ("polisyos.data_forge.kernel.schemas", "SchemaRegistry"),
    "SchemaVersion": ("polisyos.data_forge.kernel.schemas", "SchemaVersion"),
    "SnapshotCommitError": ("polisyos.data_forge.errors", "SnapshotCommitError"),
    "SnapshotTransaction": ("polisyos.data_forge.kernel.snapshot", "SnapshotTransaction"),
    "SnapshotTransactionStatus": (
        "polisyos.data_forge.kernel.snapshot",
        "SnapshotTransactionStatus",
    ),
    "asset": ("polisyos.data_forge.kernel.pipeline", "asset"),
    "capture_golden_file": (
        "polisyos.data_forge.kernel.testing",
        "capture_golden_file",
    ),
    "compare_file_sha256": (
        "polisyos.data_forge.kernel.testing",
        "compare_file_sha256",
    ),
    "compare_json_files": ("polisyos.data_forge.kernel.testing", "compare_json_files"),
    "evaluate_fail_fast": ("polisyos.data_forge.kernel.quality", "evaluate_fail_fast"),
    "merkle_root": ("polisyos.data_forge.kernel.snapshot", "merkle_root"),
    "plan_asset_specs": ("polisyos.data_forge.kernel.pipeline", "plan_asset_specs"),
    "verify_golden_file": ("polisyos.data_forge.kernel.testing", "verify_golden_file"),
}


def __getattr__(name: str) -> object:
    """Resolve build-time Data Forge exports without loading the kernel for read_api."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return public facade names without resolving build-time contracts."""
    return sorted({*globals(), *_EXPORTS})


__all__ = [
    "ArtifactRef",
    "AssetDefinition",
    "AssetGroup",
    "AssetKey",
    "AssetSpec",
    "CompatibilityMode",
    "DataForgeError",
    "DataForgeValidationError",
    "DifferentialComparison",
    "GoldenArtifact",
    "GoldenCase",
    "MaterializationContext",
    "PIILevel",
    "ProducerVersion",
    "QCCheck",
    "QCReport",
    "RetentionClass",
    "SchemaCompatibilityError",
    "SchemaRegistry",
    "SchemaVersion",
    "SnapshotCommitError",
    "SnapshotTransaction",
    "SnapshotTransactionStatus",
    "__version__",
    "asset",
    "capture_golden_file",
    "compare_file_sha256",
    "compare_json_files",
    "evaluate_fail_fast",
    "merkle_root",
    "plan_asset_specs",
    "read_api",
    "verify_golden_file",
]
