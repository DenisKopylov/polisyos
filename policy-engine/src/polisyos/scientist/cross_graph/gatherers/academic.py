"""Academic evidence gatherer — extracts and assesses scholarly evidence."""

from __future__ import annotations

from typing import Any

from polisyos.ir.analytics.cross_graph import (
    CanonicalConcept,
    CrossGraphDiagnostic,
    EvidenceNeed,
    EvidenceNeedType,
    EvidenceStatus,
)

from ..protocols import GathererResult


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

        if academic_query is None:
            return GathererResult(
                status=EvidenceStatus.INSUFFICIENT.value,
                confidence=0.3,
                diagnostics=[],
                provenance_refs=[],
                metadata={"reason": "no_academic_query", **context_metadata},
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
            status = (
                result.evidence_status.value
                if hasattr(result.evidence_status, "value")
                else str(result.evidence_status)
            )
            diagnostics = list(result.diagnostics) if hasattr(result, "diagnostics") else []
            diagnostics.extend(
                _environment_audit_diagnostics(
                    need,
                    status=status,
                    environment_audit_summary=context_metadata.get(
                        "environment_audit_summary", {}
                    ),
                )
            )
            return GathererResult(
                status=status,
                confidence=result.transport_confidence if hasattr(result, "transport_confidence") else 0.5,
                diagnostics=diagnostics,
                provenance_refs=list(result.provenance_refs) if hasattr(result, "provenance_refs") else [],
                metadata={
                    **(
                        {"transport_reasons": list(result.transport_reasons)}
                        if hasattr(result, "transport_reasons")
                        else {}
                    ),
                    **context_metadata,
                },
            )

        # Standalone assessment: check for parameter/edge needs
        return self._fallback_assess(need, concepts, context_metadata=context_metadata)

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
            diagnostics=_environment_audit_diagnostics(
                need,
                status=EvidenceStatus.INSUFFICIENT.value,
                environment_audit_summary=context_metadata.get(
                    "environment_audit_summary", {}
                ),
            ),
            provenance_refs=[],
            metadata={
                "reason": "standalone_fallback",
                "n_concepts": len(concepts),
                **context_metadata,
            },
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
        except Exception:  # noqa: BLE001
            return str(value)
    return value
