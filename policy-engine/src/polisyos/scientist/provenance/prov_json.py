"""Compatibility shim for `polisyos.scientist.evidence.provenance.prov_json`."""

from __future__ import annotations

from polisyos.scientist.evidence._shim import (
    install_module_shim,
    shim_dir,
    shim_getattr,
)

install_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.evidence.provenance.prov_json",
    shim_id="scientist.provenance.prov_json-to-evidence.provenance.prov_json",
    sunset_date="2026-11-30",
    migration_hint="Use polisyos.scientist.evidence.provenance.prov_json for new imports.",
    public_names=("from_prov_json", "to_prov_json"),
)


def __getattr__(name: str):
    return shim_getattr(globals(), name)


def __dir__() -> list[str]:
    return shim_dir(globals())
