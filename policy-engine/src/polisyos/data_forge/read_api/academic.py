"""Runtime-safe read API for academic Data Forge artifacts."""

from __future__ import annotations

from ._lazy import lazy_dir, load_lazy_export

_ACADEMIC_DOMAIN = "polisyos.data_forge.domains.academic"
_EXPORTS = {
    "ACADEMIC_ASSET_GROUP": _ACADEMIC_DOMAIN,
    "ACADEMIC_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_EXTRACTED_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_FULLTEXT_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_NORMALIZED_WORKS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_PUBLISHED_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_RAW_WORKS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_READINESS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_SKG_KEY": _ACADEMIC_DOMAIN,
    "AcademicReadinessSummary": _ACADEMIC_DOMAIN,
    "AcademicShadowArtifact": _ACADEMIC_DOMAIN,
    "AcademicShadowBundle": _ACADEMIC_DOMAIN,
    "AcademicShadowDiff": _ACADEMIC_DOMAIN,
    "AcademicStageManifest": _ACADEMIC_DOMAIN,
    "compare_academic_shadow_bundles": _ACADEMIC_DOMAIN,
    "load_academic_shadow_bundle": _ACADEMIC_DOMAIN,
}


def __getattr__(name: str) -> object:
    """Lazily resolve academic exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public academic read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


__all__ = sorted(_EXPORTS)
