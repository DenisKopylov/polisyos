"""Compatibility shim for `polisyos.scientist.evidence_sources`.

Canonical module: `polisyos.scientist.evidence.sources`.
Sunset: 2026-11-30.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.evidence.sources",
    public_names=(
        "EvidenceSourcesConfig",
        "build_path_source_status",
        "merge_evidence_sources_payload",
        "normalize_evidence_sources_config",
        "update_source_status",
    ),
    sunset_date="2026-11-30",
    migration_hint="Use polisyos.scientist.evidence.sources for new imports.",
    shim_id="decomp-scientist-evidence_sources",
)
