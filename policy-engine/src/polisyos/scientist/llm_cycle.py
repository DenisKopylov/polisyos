"""Compatibility shim for `polisyos.scientist.llm_cycle`.

Canonical module: `polisyos.scientist.orchestration.llm.cycle`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.orchestration.llm.cycle",
    public_names=(
        "build_causal_execution_plan",
        "build_default_execution_plan",
        "build_reproducibility_manifest",
        "evaluate_iteration",
        "persist_evaluator_report",
        "persist_execution_plan",
        "persist_iteration_state",
        "persist_preflight_report",
        "persist_reproducibility_manifest",
        "preflight_execution_plan",
    ),
    sunset_date="2026-12-31",
    migration_hint="Use polisyos.scientist.orchestration.llm.cycle for new imports.",
    shim_id="decomp-scientist-llm_cycle",
)
