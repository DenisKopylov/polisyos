"""Scientist deep-research evidence helpers built on canonical Scholar contracts."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "EvidenceCachePolicy",
    "EvidenceSourcesConfig",
    "EvidenceVerificationResult",
    "LLMCallRecord",
    "SafeFetchPolicy",
    "SnippetLedgerEntry",
    "SnippetLedgerValidation",
    "RunProvenanceDAG",
    "assert_web_evidence_bundle_valid",
    "build_blocked_fetch_result",
    "build_claim_support_links",
    "build_path_source_status",
    "build_snippet_ledger",
    "build_source_quality_report",
    "build_url_fetch_cache",
    "cap_tool_int",
    "claim_support_status",
    "detect_prompt_injection",
    "evaluate_content_type",
    "evaluate_fetch_request",
    "from_prov_json",
    "merge_evidence_sources_payload",
    "neutralize_instruction_markers",
    "normalize_evidence_sources_config",
    "sanitize_untrusted_page_text",
    "score_source_quality",
    "score_web_evidence_bundle_sources",
    "stable_snippet_id",
    "to_prov_json",
    "update_source_status",
    "validate_claim_support_links",
    "validate_snippet_spans",
    "verify_web_evidence_bundle",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "EvidenceCachePolicy": ("polisyos.scientist.evidence.cache", "EvidenceCachePolicy"),
    "build_url_fetch_cache": ("polisyos.scientist.evidence.cache", "build_url_fetch_cache"),
    "EvidenceSourcesConfig": ("polisyos.scientist.evidence.sources", "EvidenceSourcesConfig"),
    "build_path_source_status": (
        "polisyos.scientist.evidence.sources",
        "build_path_source_status",
    ),
    "merge_evidence_sources_payload": (
        "polisyos.scientist.evidence.sources",
        "merge_evidence_sources_payload",
    ),
    "normalize_evidence_sources_config": (
        "polisyos.scientist.evidence.sources",
        "normalize_evidence_sources_config",
    ),
    "update_source_status": ("polisyos.scientist.evidence.sources", "update_source_status"),
    "build_claim_support_links": (
        "polisyos.scientist.evidence.claim_support",
        "build_claim_support_links",
    ),
    "claim_support_status": ("polisyos.scientist.evidence.claim_support", "claim_support_status"),
    "validate_claim_support_links": (
        "polisyos.scientist.evidence.claim_support",
        "validate_claim_support_links",
    ),
    "SafeFetchPolicy": ("polisyos.scientist.evidence.safe_fetch", "SafeFetchPolicy"),
    "build_blocked_fetch_result": (
        "polisyos.scientist.evidence.safe_fetch",
        "build_blocked_fetch_result",
    ),
    "cap_tool_int": ("polisyos.scientist.evidence.safe_fetch", "cap_tool_int"),
    "detect_prompt_injection": (
        "polisyos.scientist.evidence.safe_fetch",
        "detect_prompt_injection",
    ),
    "evaluate_content_type": ("polisyos.scientist.evidence.safe_fetch", "evaluate_content_type"),
    "evaluate_fetch_request": (
        "polisyos.scientist.evidence.safe_fetch",
        "evaluate_fetch_request",
    ),
    "neutralize_instruction_markers": (
        "polisyos.scientist.evidence.safe_fetch",
        "neutralize_instruction_markers",
    ),
    "sanitize_untrusted_page_text": (
        "polisyos.scientist.evidence.safe_fetch",
        "sanitize_untrusted_page_text",
    ),
    "SnippetLedgerEntry": ("polisyos.scientist.evidence.snippet_ledger", "SnippetLedgerEntry"),
    "SnippetLedgerValidation": (
        "polisyos.scientist.evidence.snippet_ledger",
        "SnippetLedgerValidation",
    ),
    "build_snippet_ledger": (
        "polisyos.scientist.evidence.snippet_ledger",
        "build_snippet_ledger",
    ),
    "stable_snippet_id": ("polisyos.scientist.evidence.snippet_ledger", "stable_snippet_id"),
    "validate_snippet_spans": (
        "polisyos.scientist.evidence.snippet_ledger",
        "validate_snippet_spans",
    ),
    "score_source_quality": (
        "polisyos.scientist.evidence.source_quality",
        "score_source_quality",
    ),
    "build_source_quality_report": (
        "polisyos.scientist.evidence.source_quality",
        "build_source_quality_report",
    ),
    "score_web_evidence_bundle_sources": (
        "polisyos.scientist.evidence.source_quality",
        "score_web_evidence_bundle_sources",
    ),
    "EvidenceVerificationResult": (
        "polisyos.scientist.evidence.verifier",
        "EvidenceVerificationResult",
    ),
    "assert_web_evidence_bundle_valid": (
        "polisyos.scientist.evidence.verifier",
        "assert_web_evidence_bundle_valid",
    ),
    "verify_web_evidence_bundle": (
        "polisyos.scientist.evidence.verifier",
        "verify_web_evidence_bundle",
    ),
    "LLMCallRecord": ("polisyos.scientist.evidence.provenance", "LLMCallRecord"),
    "RunProvenanceDAG": ("polisyos.scientist.evidence.provenance", "RunProvenanceDAG"),
    "from_prov_json": ("polisyos.scientist.evidence.provenance", "from_prov_json"),
    "to_prov_json": ("polisyos.scientist.evidence.provenance", "to_prov_json"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.evidence' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
