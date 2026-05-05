"""Legal Data Forge domain contracts and moved batch runtime."""

from __future__ import annotations

from .shadow import (
    LegalShadowArtifact,
    LegalShadowBundle,
    LegalShadowDiff,
    LegalStageManifest,
    compare_lex_shadow_bundles,
    load_lex_shadow_bundle,
)

LEGAL_BATCH_RUNTIME_MODULE = "polisyos.data_forge.domains.legal.batch"

__all__ = [
    "LEGAL_BATCH_RUNTIME_MODULE",
    "LegalShadowArtifact",
    "LegalShadowBundle",
    "LegalShadowDiff",
    "LegalStageManifest",
    "compare_lex_shadow_bundles",
    "load_lex_shadow_bundle",
]
