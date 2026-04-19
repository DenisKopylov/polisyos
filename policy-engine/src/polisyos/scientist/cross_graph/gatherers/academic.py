"""Academic evidence gatherer — extracts and assesses scholarly evidence."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from polisyos.ir.analytics.cross_graph import (
    CanonicalConcept,
    CrossGraphDiagnostic,
    EvidenceNeed,
    EvidenceNeedType,
    EvidenceStatus,
)

from ..protocols import GathererResult

_ACADEMIC_SERIALIZATION_ERRORS = (AttributeError, TypeError, ValueError, ValidationError)


class AcademicGatherer:
    """Assesses academic/scholarly evidence for evidence needs.

    Delegates to the existing `_assess_academic_need()` logic in the
    monolithic compiler, wrapping results in the GathererResult protocol.
    """

    @property
    def dimension(self) -> str:
        return "academic"

    def assess(
        self,
        need: EvidenceNeed,
        *,
        concepts: list[CanonicalConcept],
        context: dict[str, Any],
    ) -> GathererResult:
        academic_query = context.get("academic_query")
        target_context = context.get("target_context")
        context_metadata = _context_metadata(context)
        baseline_result = _assess_literature_prior_baseline(
            need,
            literature_prior=context.get("literature_prior"),
            context_metadata=context_metadata,
        )

        if academic_query is None:
            return _attach_environment_audit_diagnostics(
                need,
                _merge_baseline_with_primary(
                    GathererResult(
                        status=EvidenceStatus.INSUFFICIENT.value,
                        confidence=0.3,
                        diagnostics=[],
                        provenance_refs=[],
                        metadata={"reason": "no_academic_query", **context_metadata},
                    ),
                    baseline_result,
                ),
                environment_audit_summary=context_metadata.get(
                    "environment_audit_summary", {}
                ),
            )

        # Delegate to existing compiler function if available
        compiler_fn = context.get("_assess_academic_need")
        if compiler_fn is not None:
            result = compiler_fn(
                need,
                concepts=concepts,
                academic_query=academic_query,
                target_context=target_context,
            )
            gathered = GathererResult(
                status=(
                    result.evidence_status.value
                    if hasattr(result.evidence_status, "value")
                    else str(result.evidence_status)
                ),
                confidence=(
                    result.transport_confidence
                    if hasattr(result, "transport_confidence")
                    else 0.5
                ),
                diagnostics=list(result.diagnostics) if hasattr(result, "diagnostics") else [],
                provenance_refs=(
                    list(result.provenance_refs)
                    if hasattr(result, "provenance_refs")
                    else []
                ),
                metadata={
                    **(
                        {"transport_reasons": list(result.transport_reasons)}
                        if hasattr(result, "transport_reasons")
                        else {}
                    ),
                    **context_metadata,
                },
            )
            return _attach_environment_audit_diagnostics(
                need,
                _merge_baseline_with_primary(gathered, baseline_result),
                environment_audit_summary=context_metadata.get(
                    "environment_audit_summary", {}
                ),
            )

        # Standalone assessment: check for parameter/edge needs
        return _attach_environment_audit_diagnostics(
            need,
            _merge_baseline_with_primary(
                self._fallback_assess(need, concepts, context_metadata=context_metadata),
                baseline_result,
            ),
            environment_audit_summary=context_metadata.get("environment_audit_summary", {}),
        )

    def _fallback_assess(
        self,
        need: EvidenceNeed,
        concepts: list[CanonicalConcept],
        *,
        context_metadata: dict[str, Any],
    ) -> GathererResult:
        if not concepts:
            return GathererResult(
                status=EvidenceStatus.INSUFFICIENT.value,
                confidence=0.2,
                diagnostics=[],
                provenance_refs=[],
                metadata={"reason": "no_matching_concepts", **context_metadata},
            )
        return GathererResult(
            status=EvidenceStatus.INSUFFICIENT.value,
            confidence=0.3,
            diagnostics=[],
            provenance_refs=[],
            metadata={
                "reason": "standalone_fallback",
                "n_concepts": len(concepts),
                **context_metadata,
            },
        )


def _attach_environment_audit_diagnostics(
    need: EvidenceNeed,
    result: GathererResult,
    *,
    environment_audit_summary: dict[str, Any],
) -> GathererResult:
    diagnostics = list(result.diagnostics)
    diagnostics.extend(
        diagnostic
        for diagnostic in _environment_audit_diagnostics(
            need,
            status=result.status,
            environment_audit_summary=environment_audit_summary,
        )
        if diagnostic not in diagnostics
    )
    return GathererResult(
        status=result.status,
        confidence=result.confidence,
        diagnostics=diagnostics,
        provenance_refs=list(result.provenance_refs),
        metadata=dict(result.metadata),
    )


def _assess_literature_prior_baseline(
    need: EvidenceNeed,
    *,
    literature_prior: Any,
    context_metadata: dict[str, Any],
) -> GathererResult | None:
    if need.need_type is not EvidenceNeedType.CAUSAL_EDGE_NEED:
        return None
    if not need.cause or not need.effect:
        return None

    payload = _serialize_value(literature_prior)
    if not isinstance(payload, dict):
        return None
    edges = payload.get("edges")
    if not isinstance(edges, list):
        return None

    matches = [
        edge
        for edge in edges
        if isinstance(edge, dict)
        and str(edge.get("src") or "").strip() == str(need.cause).strip()
        and str(edge.get("dst") or "").strip() == str(need.effect).strip()
    ]
    if not matches:
        return None

    best = sorted(
        matches,
        key=lambda edge: (
            float(edge.get("confidence") or 0.0),
            int(edge.get("n_articles") or 0),
        ),
        reverse=True,
    )[0]
    confidence = float(best.get("confidence") or 0.0)
    n_articles = int(best.get("n_articles") or 0)
    usable = confidence >= 0.5 and n_articles >= 2
    status = EvidenceStatus.MIXED if usable else EvidenceStatus.INSUFFICIENT
    baseline_confidence = min(
        0.7 if usable else 0.45,
        max(0.2, confidence),
    )
    article_refs = [
        str(item)
        for item in list(best.get("article_refs", []) or [])
        if str(item).strip()
    ]
    metadata = {
        **context_metadata,
        "baseline_support_source": "literature_prior",
        "literature_prior_match": {
            "src": str(best.get("src") or need.cause),
            "dst": str(best.get("dst") or need.effect),
            "confidence": confidence,
            "n_articles": n_articles,
            "direction": best.get("direction"),
            "evidence_strength": best.get("evidence_strength"),
        },
        "literature_prior_confidence": confidence,
        "literature_prior_article_refs": list(article_refs),
    }
    diagnostics = [
        CrossGraphDiagnostic(
            code="cross_graph.academic.literature_prior_baseline_used",
            need_id=need.need_id,
            message="Literature prior provided baseline academic evidence for this causal edge.",
            details={
                "status": status.value,
                "confidence": confidence,
                "n_articles": n_articles,
            },
        )
    ]
    return GathererResult(
        status=status.value,
        confidence=baseline_confidence,
        diagnostics=diagnostics,
        provenance_refs=article_refs,
        metadata=metadata,
    )


def _merge_baseline_with_primary(
    primary: GathererResult,
    baseline: GathererResult | None,
) -> GathererResult:
    if baseline is None:
        return primary

    primary_status = _coerce_evidence_status(primary.status)
    baseline_status = _coerce_evidence_status(baseline.status)
    merged_status = primary_status
    if primary_status in {
        EvidenceStatus.INSUFFICIENT,
        EvidenceStatus.UNSUPPORTED,
    } and baseline_status is EvidenceStatus.MIXED:
        merged_status = EvidenceStatus.MIXED
    elif primary_status is EvidenceStatus.UNSUPPORTED and baseline_status is EvidenceStatus.INSUFFICIENT:
        merged_status = EvidenceStatus.INSUFFICIENT

    diagnostics = list(primary.diagnostics)
    diagnostics.extend(
        diagnostic for diagnostic in baseline.diagnostics if diagnostic not in diagnostics
    )
    provenance_refs = _dedupe_strings(
        [*list(primary.provenance_refs), *list(baseline.provenance_refs)]
    )
    metadata = {
        **dict(primary.metadata),
        **{
            key: value
            for key, value in dict(baseline.metadata).items()
            if key not in primary.metadata
        },
    }
    metadata.setdefault("literature_prior_baseline", dict(baseline.metadata))

    return GathererResult(
        status=merged_status.value,
        confidence=max(float(primary.confidence), float(baseline.confidence)),
        diagnostics=diagnostics,
        provenance_refs=provenance_refs,
        metadata=metadata,
    )


def _context_metadata(context: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    literature_prior = context.get("literature_prior")
    if literature_prior is not None:
        metadata["literature_prior"] = _summarize_literature_prior(literature_prior)

    literature_prior_ref = context.get("literature_prior_ref")
    if literature_prior_ref is not None:
        metadata["literature_prior_ref"] = _serialize_value(literature_prior_ref)

    environment_audit = context.get("environment_audit")
    if environment_audit is not None:
        metadata["environment_audit"] = _serialize_value(environment_audit)

    environment_audit_summary = context.get("environment_audit_summary")
    if isinstance(environment_audit_summary, dict):
        metadata["environment_audit_summary"] = dict(environment_audit_summary)
    elif environment_audit is not None:
        metadata["environment_audit_summary"] = _summarize_environment_audit(
            environment_audit
        )

    return metadata


def _summarize_literature_prior(value: Any) -> dict[str, Any]:
    payload = _serialize_value(value)
    if not isinstance(payload, dict):
        return {"available": True}
    edges = payload.get("edges", [])
    metadata = payload.get("metadata", {})
    return {
        "available": True,
        "edge_count": len(edges) if isinstance(edges, list) else 0,
        "skg_version_id": payload.get("skg_version_id"),
        "build_status": metadata.get("build_status") if isinstance(metadata, dict) else None,
    }


def _summarize_environment_audit(value: Any) -> dict[str, Any]:
    payload = _serialize_value(value)
    if not isinstance(payload, dict):
        return {}
    return {
        "status": payload.get("status"),
        "n_environments": payload.get("n_environments"),
        "ks_passed": payload.get("ks_passed"),
        "ks_rejected_variables": list(payload.get("ks_rejected_variables", []) or []),
        "icp_run": bool(payload.get("icp_run", False)),
        "icp_passed": payload.get("icp_passed"),
        "variant_features": list(payload.get("variant_features", []) or []),
        "warnings": list(payload.get("warnings", []) or []),
    }


def _environment_audit_diagnostics(
    need: EvidenceNeed,
    *,
    status: str,
    environment_audit_summary: dict[str, Any],
) -> list[CrossGraphDiagnostic]:
    if not _has_academic_support(status):
        return []
    if not isinstance(environment_audit_summary, dict) or not environment_audit_summary:
        return []

    audit_status = str(environment_audit_summary.get("status") or "").strip().lower()
    ks_passed = environment_audit_summary.get("ks_passed")
    variant_features = list(environment_audit_summary.get("variant_features", []) or [])
    rejected_variables = list(
        environment_audit_summary.get("ks_rejected_variables", []) or []
    )
    unstable = (
        audit_status in {"warning", "degraded"}
        or ks_passed is False
        or bool(variant_features)
        or bool(rejected_variables)
    )
    if not unstable:
        return []

    return [
        CrossGraphDiagnostic(
            code="cross_graph.academic.environment_audit_advisory",
            need_id=need.need_id,
            message=(
                "Academic evidence exists, but the environment audit reported instability or feature drift."
            ),
            details={
                "environment_audit_status": audit_status or None,
                "ks_rejected_variables": rejected_variables,
                "variant_features": variant_features,
            },
        )
    ]


def _coerce_evidence_status(status: str) -> EvidenceStatus:
    normalized = str(status or "").strip().lower()
    for candidate in EvidenceStatus:
        if candidate.value == normalized:
            return candidate
    return EvidenceStatus.INSUFFICIENT


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _has_academic_support(status: str) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {
        EvidenceStatus.SUPPORTED.value,
        EvidenceStatus.MIXED.value,
    }


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump_json"):
        try:
            return value.model_dump(mode="json")
        except _ACADEMIC_SERIALIZATION_ERRORS:
            return str(value)
    return value
