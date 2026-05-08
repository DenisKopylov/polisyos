"""Compatibility shim for `polisyos.scientist.remediation_status`.

Canonical module: `polisyos.scientist.governance.remediation_status`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.governance.remediation_status",
    public_names=(
        "WORKSTREAM_IDS",
        "RemediationStatusLevel",
        "ScientistPhaseStatus",
        "ScientistRemediationStatusReport",
        "ScientistWorkstreamStatus",
        "build_scientist_remediation_status_report",
    ),
    sunset_date="2026-12-31",
    migration_hint="Use polisyos.scientist.governance.remediation_status for new imports.",
    shim_id="decomp-scientist-remediation_status",
)
