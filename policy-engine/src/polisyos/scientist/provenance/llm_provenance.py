"""Compatibility shim for `polisyos.scientist.evidence.provenance.llm_provenance`."""

from __future__ import annotations

from polisyos.scientist.evidence._shim import (
    install_module_shim,
    shim_dir,
    shim_getattr,
)

install_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.evidence.provenance.llm_provenance",
    shim_id="scientist.provenance.llm_provenance-to-evidence.provenance.llm_provenance",
    sunset_date="2026-11-30",
    migration_hint=(
        "Use polisyos.scientist.evidence.provenance.llm_provenance for new imports."
    ),
    public_names=("LLMCallRecord",),
)


def __getattr__(name: str):
    return shim_getattr(globals(), name)


def __dir__() -> list[str]:
    return shim_dir(globals())
