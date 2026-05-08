"""Compatibility shim for `polisyos.scientist.feedback_utils`.

Canonical module: `polisyos.scientist.feedback.utils`.
Sunset: 2026-11-30.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.feedback.utils",
    public_names=(
        "_aggregate_monitoring_verdict",
        "_as_bool_or_none",
        "_as_float",
        "_as_str",
        "_extract_artifact_id",
        "_extract_feedback_ref",
        "_extract_metric_observation",
        "_extract_numeric_value",
        "_extract_revised_metric_ids",
        "_extract_rows",
        "_outside_range",
        "_path_get",
        "_within_range",
    ),
    sunset_date="2026-11-30",
    migration_hint="Use polisyos.scientist.feedback.utils for new imports.",
    shim_id="decomp-scientist-feedback_utils",
)
