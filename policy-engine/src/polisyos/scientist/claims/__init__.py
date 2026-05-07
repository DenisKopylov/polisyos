"""Compatibility shim for Scientist claim helpers.

Use `polisyos.scientist.evidence.claims` for new imports. This package remains
available until the 2026-11-30 Phase 4.4 shim sunset.
"""

from __future__ import annotations

from polisyos.scientist.evidence._shim import (
    install_module_shim,
    shim_dir,
    shim_getattr,
)

install_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.evidence.claims",
    shim_id="scientist.claims-to-evidence.claims",
    sunset_date="2026-11-30",
    migration_hint="Use polisyos.scientist.evidence.claims for new imports.",
)


def __getattr__(name: str):
    return shim_getattr(globals(), name)


def __dir__() -> list[str]:
    return shim_dir(globals())
