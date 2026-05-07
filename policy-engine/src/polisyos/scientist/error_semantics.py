"""Compatibility shim for `polisyos.scientist.error_semantics`.

Canonical module: `polisyos.scientist.orchestration.engine.error_semantics`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.orchestration.engine.error_semantics",
    public_names=("ErrorEnvelope", "build_error_envelope", "emit_degraded_path"),
    sunset_date="2026-12-31",
    migration_hint=(
        "Use polisyos.scientist.orchestration.engine.error_semantics for new imports."
    ),
)
