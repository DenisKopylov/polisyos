"""Compatibility shim for `polisyos.scientist.evidence.provenance.run_dag`."""

from __future__ import annotations

from polisyos.scientist.evidence._shim import (
    install_module_shim,
    shim_dir,
    shim_getattr,
)

install_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.evidence.provenance.run_dag",
    shim_id="scientist.provenance.run_dag-to-evidence.provenance.run_dag",
    sunset_date="2026-11-30",
    migration_hint="Use polisyos.scientist.evidence.provenance.run_dag for new imports.",
    public_names=("RunProvenanceDAG",),
)


def __getattr__(name: str):
    return shim_getattr(globals(), name)


def __dir__() -> list[str]:
    return shim_dir(globals())
