"""Compatibility shim for `polisyos.scientist.publisher`.

Canonical module: `polisyos.scientist.publishing`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.publishing",
    public_names=(
        "COMPILER_BACKED_DECISION_CARD_FLAG",
        "DECISION_GRADE_COMPILER_FLAG",
        "DECISION_GRADE_EXPORT_KIND",
        "DECISION_GRADE_EXPORT_SCHEMA_NAME",
        "DECISION_GRADE_EXPORT_SCHEMA_VERSION",
        "FORBIDDEN_PUBLIC_EXPORT_TOKENS",
        "DecisionGradeExport",
        "OutputAudience",
        "OutputOmissionRecord",
        "assert_decision_grade_exports_consistent",
        "compile_decision_grade_export",
        "compile_decision_grade_exports",
        "decision_grade_export_inputs",
        "load_decision_grade_export",
        "persist_decision_grade_export",
        "publish_decision",
    ),
    sunset_date="2026-12-31",
    migration_hint="Use polisyos.scientist.publishing for new imports.",
)
