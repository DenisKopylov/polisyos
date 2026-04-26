"""Read-only legal shadow adapters for Data Forge migration work."""

from __future__ import annotations

from .shadow import (
    LegalShadowArtifact,
    LegalShadowBundle,
    LegalShadowDiff,
    LegalStageManifest,
    compare_lex_shadow_bundles,
    load_lex_shadow_bundle,
)

__all__ = [
    "LegalShadowArtifact",
    "LegalShadowBundle",
    "LegalShadowDiff",
    "LegalStageManifest",
    "compare_lex_shadow_bundles",
    "load_lex_shadow_bundle",
]
