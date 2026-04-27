"""Verification helpers for Scientist deep-research evidence bundles."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scholar.search.models import WebEvidenceBundle
from polisyos.scientist.evidence.claim_support import validate_claim_support_links
from polisyos.scientist.evidence.safe_fetch import detect_prompt_injection
from polisyos.scientist.evidence.snippet_ledger import validate_snippet_spans


class EvidenceVerificationResult(BaseModel):
    """Machine-readable verification result for WebEvidenceBundle sidecars."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


def verify_web_evidence_bundle(
    bundle: WebEvidenceBundle,
    *,
    require_claim_support: bool = False,
) -> EvidenceVerificationResult:
    """Check bundle integrity without doing live web or LLM work."""

    violations: list[str] = []
    warnings: list[str] = []
    source_ids = [source.source_id for source in bundle.sources]
    snippet_ids = [snippet.snippet_id for snippet in bundle.snippets]

    if len(source_ids) != len(set(source_ids)):
        violations.append("duplicate_source_id")
    if len(snippet_ids) != len(set(snippet_ids)):
        violations.append("duplicate_snippet_id")

    span_result = validate_snippet_spans(bundle.snippets)
    violations.extend(span_result.violations)
    warnings.extend(span_result.warnings)
    violations.extend(validate_claim_support_links(bundle))

    if require_claim_support and bundle.snippets and not bundle.claim_supports:
        violations.append("claim_support_required")

    safety_event_types = {event.event_type for event in bundle.fetch_safety_events}
    for snippet in bundle.snippets:
        if detect_prompt_injection(snippet.text, url=str(snippet.url)):
            if "prompt_injection_suspected" not in safety_event_types:
                warnings.append(f"prompt_injection_text_without_safety_event:{snippet.snippet_id}")

    quality_source_ids = {signal.source_id for signal in bundle.source_quality_signals}
    for source_id in quality_source_ids:
        if source_ids and source_id not in source_ids:
            violations.append(f"quality_signal_missing_source:{source_id}")

    return EvidenceVerificationResult(
        passed=not violations,
        violations=sorted(dict.fromkeys(violations)),
        warnings=sorted(dict.fromkeys(warnings)),
        metadata={
            "source_count": len(bundle.sources),
            "snippet_count": len(bundle.snippets),
            "claim_support_count": len(bundle.claim_supports),
            "fetch_safety_event_count": len(bundle.fetch_safety_events),
            "source_quality_signal_count": len(bundle.source_quality_signals),
        },
    )


def assert_web_evidence_bundle_valid(
    bundle: WebEvidenceBundle,
    *,
    require_claim_support: bool = False,
) -> None:
    """Raise ValueError if a bundle fails Scientist evidence verification."""

    result = verify_web_evidence_bundle(
        bundle,
        require_claim_support=require_claim_support,
    )
    if not result.passed:
        raise ValueError("; ".join(result.violations))


__all__ = [
    "EvidenceVerificationResult",
    "assert_web_evidence_bundle_valid",
    "verify_web_evidence_bundle",
]
