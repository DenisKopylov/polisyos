"""Expose the canonical, versioned manifest profile owned by the CAS lifecycle."""

from __future__ import annotations

from ._manifest_lifecycle import ManifestLifecycle
from .manifest import ArtifactManifest


def artifact_manifest_profile_projection(manifest: ArtifactManifest) -> dict[str, object]:
    """Return the persisted schema version's canonical manifest profile projection."""
    return ManifestLifecycle.profile_projection(manifest)


def artifact_manifest_profile_sha256(manifest: ArtifactManifest) -> str:
    """Return the canonical domain-separated ``sha256:`` digest of a manifest profile."""
    return ManifestLifecycle.profile_sha256(manifest)


__all__ = ["artifact_manifest_profile_projection", "artifact_manifest_profile_sha256"]
