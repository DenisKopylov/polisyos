"""Public report helpers for benchmark authority verdicts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.scientist.evals.leakage import (
    detect_benchmark_contamination,
    hidden_benchmark_ref_ids,
    redact_hidden_benchmark_refs,
)

if TYPE_CHECKING:
    from polisyos.scientist.evals.authority import BenchmarkAuthorityVerdict

__all__ = ["export_public_benchmark_authority_verdict"]


def export_public_benchmark_authority_verdict(
    verdict: BenchmarkAuthorityVerdict,
) -> dict[str, Any]:
    """Export a public-safe verdict summary without hidden holdout artifact ids."""

    bundle = verdict.bundle
    payload: dict[str, Any] = {
        "schema_version": verdict.schema_version,
        "request": verdict.request.model_dump(mode="json", exclude_none=True),
        "bundle_summary": {
            "family": bundle.family,
            "claim_mode": bundle.claim_mode,
            "query_type": bundle.query_type,
            "estimator_name": bundle.estimator_name,
            "readiness_target": bundle.readiness_target,
            "selection_present": bundle.selection_evaluation_ref is not None,
            "hidden_holdout_present": bundle.hidden_holdout_evaluation_ref is not None,
            "rotating_challenge_count": len(bundle.rotating_challenge_evaluation_refs),
            "sentinel_count": len(bundle.sentinel_evaluation_refs),
            "adversarial_count": len(bundle.adversarial_artifact_refs),
        },
        "missing": list(verdict.missing),
        "stale": list(verdict.stale),
        "leakage_warnings": list(verdict.leakage_warnings),
        "default_enable_allowed": verdict.default_enable_allowed,
        "rationale": verdict.rationale,
    }
    hidden_refs = hidden_benchmark_ref_ids(bundle)
    payload = redact_hidden_benchmark_refs(payload, hidden_ref_ids=hidden_refs)
    if detect_benchmark_contamination(payload, hidden_ref_ids=hidden_refs):
        raise ValueError("public benchmark authority export leaked hidden benchmark refs")
    return payload
