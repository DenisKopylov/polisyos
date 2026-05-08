"""Compatibility shim for `polisyos.scientist.reliability_scorecard`.

Canonical module: `polisyos.scientist.validation.reliability_scorecard`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.validation.reliability_scorecard",
    public_names=(
        "BENCHMARK_EVIDENCE_CASES",
        "OPERATIONAL_EVIDENCE_CASES",
        "REQUIRED_BENCHMARKS",
        "REQUIRED_OPERATIONAL_SIGNALS",
        "REQUIRED_SCENARIOS",
        "SCENARIO_EVIDENCE_CASES",
        "ScientistReliabilityScorecard",
        "build_scientist_reliability_scorecard",
        "build_scientist_reliability_scorecard_from_evidence",
    ),
    sunset_date="2026-12-31",
    migration_hint="Use polisyos.scientist.validation.reliability_scorecard for new imports.",
    shim_id="decomp-scientist-reliability_scorecard",
)
