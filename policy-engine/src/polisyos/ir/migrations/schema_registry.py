"""Declared IR schema compatibility registry.

This module is intentionally side-effectful on import: it registers the
contract-level compatibility rules used by migration and release-review code.
"""
from __future__ import annotations

from polisyos.ir.migrations.base import CompatibilityMode, register_schema_version


def register_default_schema_rules() -> None:
    """Register built-in IR schema compatibility declarations."""

    register_schema_version(
        "trinity_bundle",
        "1.0",
        compatibility=CompatibilityMode.FULL,
        notes=("Canonical Trinity bundle baseline.",),
    )
    register_schema_version(
        "hte_result",
        "1.0",
        compatibility=CompatibilityMode.FULL,
        notes=("HTE 1.0 has no declared schema successors yet.",),
    )
    register_schema_version(
        "policy_recommendation",
        "1.0",
        compatibility=CompatibilityMode.FULL,
        notes=("Policy recommendation 1.0 has no declared schema successors yet.",),
    )
    register_schema_version(
        "literature_causal_prior",
        "1.0",
        compatibility=CompatibilityMode.FULL,
        notes=("Literature causal prior 1.0 has no declared schema successors yet.",),
    )
    register_schema_version(
        "article_extraction_result",
        "1.0",
        compatibility=CompatibilityMode.FORWARD,
        writable_versions=("1.5",),
        notes=("Legacy article extraction payload with publication_year alias.",),
    )
    register_schema_version(
        "article_extraction_result",
        "1.5",
        compatibility=CompatibilityMode.BACKWARD,
        readable_versions=("1.0",),
        additive_optional_fields=(
            "paper_kind",
            "heterogeneity_results",
            "external_validity_assessment",
            "context_attributes",
            "moderation_edges",
            "reconciliation_diagnostics",
        ),
        renamed_fields=(("publication_year", "year"),),
        canonical_defaults=(("schema_version", "1.5"),),
        notes=("New readers normalize v1.0 aliases before model construction.",),
    )
    register_schema_version(
        "transportability_result",
        "1.0",
        compatibility=CompatibilityMode.FORWARD,
        writable_versions=("2.0",),
        notes=("Legacy Phase 8A transportability result.",),
    )
    register_schema_version(
        "transportability_result",
        "2.0",
        compatibility=CompatibilityMode.BACKWARD,
        readable_versions=("1.0",),
        additive_optional_fields=(
            "transport_mode",
            "identification_engine",
            "partial_identification_result",
            "pag_identification_policy",
            "outer_search_truncated",
            "search_events",
        ),
        renamed_fields=(("formula", "transport_formula"),),
        canonical_defaults=(("schema_version", "2.0"),),
        notes=("v2.0 dual-reads v1.0 payloads through explicit normalizers.",),
    )


register_default_schema_rules()


__all__ = [
    "register_default_schema_rules",
]
