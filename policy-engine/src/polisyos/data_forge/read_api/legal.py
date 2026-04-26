"""Runtime-safe read API for shadow legal Data Forge artifacts."""

from __future__ import annotations

from ._lazy import lazy_dir, load_lazy_export

_LEGAL_DOMAIN = "polisyos.data_forge.domains.legal"
_EXPORTS = {
    "LegalShadowArtifact": _LEGAL_DOMAIN,
    "LegalShadowBundle": _LEGAL_DOMAIN,
    "LegalShadowDiff": _LEGAL_DOMAIN,
    "LegalStageManifest": _LEGAL_DOMAIN,
    "compare_lex_shadow_bundles": _LEGAL_DOMAIN,
    "load_lex_shadow_bundle": _LEGAL_DOMAIN,
}


def __getattr__(name: str) -> object:
    """Lazily resolve legal exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public legal read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


__all__ = sorted(_EXPORTS)
