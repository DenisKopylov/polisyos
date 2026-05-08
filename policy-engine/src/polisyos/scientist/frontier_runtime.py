"""Compatibility shim for `polisyos.scientist.frontier_runtime`.

Canonical module: `polisyos.scientist.orchestration.engine.frontier_runtime`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.orchestration.engine.frontier_runtime",
    public_names=(
        "FrontierCapability",
        "FrontierCapabilityStatus",
        "FrontierRuntimeConfig",
        "FrontierRuntimeReport",
        "build_frontier_runtime_report",
        "summarize_agent_promotion_frontier_status",
    ),
    sunset_date="2026-12-31",
    migration_hint=(
        "Use polisyos.scientist.orchestration.engine.frontier_runtime for new imports."
    ),
    shim_id="decomp-scientist-frontier_runtime",
)
