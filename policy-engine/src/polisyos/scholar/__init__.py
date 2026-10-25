"""Expose Scholar enrichment entrypoints and contracts via lazy imports.

The Scholar package facade is intentionally narrow: it exports enrichment
results, policy knobs, domain-specific exceptions, and the `ScholarService`
boundary used by runtime and CLI callers. Lazy imports avoid loading the
document/claim pipeline until a caller actually invokes Scholar APIs.

Names listed in `__all__` are the supported package-level surface.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__all__ = [
    "SCHOLAR_ACADEMIC_EVIDENCE_FILENAME",
    "SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY",
    "SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION",
    "EnrichResultV1",
    "EnrichmentReportV1",
    "KnowledgeBundlePayloadV1",
    "ScholarAcquireError",
    "ScholarBundleError",
    "ScholarClaimsError",
    "ScholarDiscoverError",
    "ScholarDocsError",
    "ScholarError",
    "ScholarFabricCitation",
    "ScholarPolicy",
    "ScholarReconcileError",
    "ScholarService",
    "ScholarValidationError",
    "SourceSnippet",
    "WebEvidenceBundle",
    "build_scholar_academic_evidence_report",
    "build_scholar_academic_evidence_report_from_web_bundle",
    "build_scholar_spine_evidence_binding",
    "enrich_topic",
    "normalize_scholar_academic_evidence_report",
    "persist_knowledge_bundle_payload",
    "sanitize_untrusted_text",
    "scholar_academic_evidence_required",
    "scholar_citation_from_fabric_decision_data",
    "validate_source_snippet_spans",
    "validate_web_evidence_source_binding",
]

if TYPE_CHECKING:
    from polisyos.scholar._impl.evidence import (
        SCHOLAR_ACADEMIC_EVIDENCE_FILENAME as SCHOLAR_ACADEMIC_EVIDENCE_FILENAME,
    )
    from polisyos.scholar._impl.evidence import (
        scholar_academic_evidence_required as scholar_academic_evidence_required,
    )
    from polisyos.scholar._impl.spine import (
        build_scholar_spine_evidence_binding as build_scholar_spine_evidence_binding,
    )
    from polisyos.scholar.orchestrator.bundle import (
        persist_knowledge_bundle_payload as persist_knowledge_bundle_payload,
    )


_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ScholarService": ("polisyos.scholar.api", "ScholarService"),
    "SourceSnippet": ("polisyos.scholar.search.models", "SourceSnippet"),
    "WebEvidenceBundle": ("polisyos.scholar.search.models", "WebEvidenceBundle"),
    "validate_source_snippet_spans": (
        "polisyos.scholar.search",
        "validate_source_snippet_spans",
    ),
    "validate_web_evidence_source_binding": (
        "polisyos.scholar.search",
        "validate_web_evidence_source_binding",
    ),
    "enrich_topic": ("polisyos.scholar.api", "enrich_topic"),
    "ScholarAcquireError": ("polisyos.scholar.orchestrator.errors", "ScholarAcquireError"),
    "ScholarBundleError": ("polisyos.scholar.orchestrator.errors", "ScholarBundleError"),
    "ScholarClaimsError": ("polisyos.scholar.orchestrator.errors", "ScholarClaimsError"),
    "ScholarDiscoverError": ("polisyos.scholar.orchestrator.errors", "ScholarDiscoverError"),
    "ScholarDocsError": ("polisyos.scholar.orchestrator.errors", "ScholarDocsError"),
    "ScholarError": ("polisyos.scholar.orchestrator.errors", "ScholarError"),
    "ScholarReconcileError": ("polisyos.scholar.orchestrator.errors", "ScholarReconcileError"),
    "ScholarValidationError": ("polisyos.scholar.orchestrator.errors", "ScholarValidationError"),
    "ScholarPolicy": ("polisyos.scholar.orchestrator.policies", "ScholarPolicy"),
    "build_scholar_academic_evidence_report_from_web_bundle": (
        "polisyos.scholar._impl.evidence",
        "build_scholar_academic_evidence_report_from_web_bundle",
    ),
    "build_scholar_academic_evidence_report": (
        "polisyos.scholar._impl.evidence",
        "build_scholar_academic_evidence_report",
    ),
    "normalize_scholar_academic_evidence_report": (
        "polisyos.scholar._impl.evidence",
        "normalize_scholar_academic_evidence_report",
    ),
    "scholar_academic_evidence_required": (
        "polisyos.scholar._impl.evidence",
        "scholar_academic_evidence_required",
    ),
    "SCHOLAR_ACADEMIC_EVIDENCE_FILENAME": (
        "polisyos.scholar._impl.evidence",
        "SCHOLAR_ACADEMIC_EVIDENCE_FILENAME",
    ),
    "SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY": (
        "polisyos.scholar._impl.evidence",
        "SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY",
    ),
    "SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION": (
        "polisyos.scholar._impl.evidence",
        "SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION",
    ),
    "build_scholar_spine_evidence_binding": (
        "polisyos.scholar._impl.spine",
        "build_scholar_spine_evidence_binding",
    ),
    "sanitize_untrusted_text": (
        "polisyos.scholar.search.security",
        "sanitize_untrusted_text",
    ),
    "ScholarFabricCitation": ("polisyos.scholar.orchestrator.provenance", "ScholarFabricCitation"),
    "scholar_citation_from_fabric_decision_data": (
        "polisyos.scholar.orchestrator.provenance",
        "scholar_citation_from_fabric_decision_data",
    ),
    "EnrichResultV1": ("polisyos.core.contracts.scholar", "EnrichResultV1"),
    "EnrichmentReportV1": ("polisyos.core.contracts.scholar", "EnrichmentReportV1"),
    "KnowledgeBundlePayloadV1": ("polisyos.core.contracts.scholar", "KnowledgeBundlePayloadV1"),
    "persist_knowledge_bundle_payload": (
        "polisyos.scholar.orchestrator.bundle",
        "persist_knowledge_bundle_payload",
    ),
}


def __getattr__(name: str) -> object:
    """Resolve one exported Scholar symbol and cache it on the package."""
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scholar' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded globals plus deferred Scholar exports."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
