"""Compatibility shim for `polisyos.scientist.decision_validity`.

Canonical module: `polisyos.scientist.validation.decision_validity`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.validation.decision_validity",
    public_names=("DecisionValidityService", "DecisionValidityStateStore"),
    sunset_date="2026-12-31",
    migration_hint="Use polisyos.scientist.validation.decision_validity for new imports.",
    shim_id="decomp-scientist-decision_validity",
)
