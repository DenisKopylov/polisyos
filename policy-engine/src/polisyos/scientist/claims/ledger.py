"""Compatibility shim for `polisyos.scientist.evidence.claims.ledger`."""

from __future__ import annotations

from polisyos.scientist.evidence._shim import (
    install_module_shim,
    shim_dir,
    shim_getattr,
)

install_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.evidence.claims.ledger",
    shim_id="scientist.claims.ledger-to-evidence.claims.ledger",
    sunset_date="2026-11-30",
    migration_hint="Use polisyos.scientist.evidence.claims.ledger for new imports.",
)


def __getattr__(name: str):
    return shim_getattr(globals(), name)


def __dir__() -> list[str]:
    return shim_dir(globals())
