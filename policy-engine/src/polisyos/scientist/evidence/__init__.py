"""Scientist deep-research evidence helpers built on canonical Scholar contracts."""

from __future__ import annotations

from polisyos.scientist.evidence.cache import EvidenceCachePolicy, build_url_fetch_cache
from polisyos.scientist.evidence.claim_support import (
    build_claim_support_links,
    claim_support_status,
    validate_claim_support_links,
)
from polisyos.scientist.evidence.safe_fetch import (
    SafeFetchPolicy,
    build_blocked_fetch_result,
    cap_tool_int,
    detect_prompt_injection,
    evaluate_content_type,
    evaluate_fetch_request,
    neutralize_instruction_markers,
    sanitize_untrusted_page_text,
)
from polisyos.scientist.evidence.snippet_ledger import (
    SnippetLedgerEntry,
    SnippetLedgerValidation,
    build_snippet_ledger,
    stable_snippet_id,
    validate_snippet_spans,
)
from polisyos.scientist.evidence.source_quality import (
    score_source_quality,
    score_web_evidence_bundle_sources,
)
from polisyos.scientist.evidence.verifier import (
    EvidenceVerificationResult,
    assert_web_evidence_bundle_valid,
    verify_web_evidence_bundle,
)

__all__ = [
    "EvidenceCachePolicy",
    "EvidenceVerificationResult",
    "SafeFetchPolicy",
    "SnippetLedgerEntry",
    "SnippetLedgerValidation",
    "assert_web_evidence_bundle_valid",
    "build_blocked_fetch_result",
    "build_claim_support_links",
    "build_snippet_ledger",
    "build_url_fetch_cache",
    "cap_tool_int",
    "claim_support_status",
    "detect_prompt_injection",
    "evaluate_content_type",
    "evaluate_fetch_request",
    "neutralize_instruction_markers",
    "sanitize_untrusted_page_text",
    "score_source_quality",
    "score_web_evidence_bundle_sources",
    "stable_snippet_id",
    "validate_claim_support_links",
    "validate_snippet_spans",
    "verify_web_evidence_bundle",
]
