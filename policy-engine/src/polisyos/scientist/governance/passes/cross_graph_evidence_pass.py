from __future__ import annotations

from typing import Any

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
    load_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.transportability import TransportMode
from polisyos.ir.refs import CrossGraphEvidenceProfileRef


class CrossGraphEvidencePass(ValidatorPass):
    @property
    def pass_id(self) -> str:
        return "cross_graph_evidence"

    @property
    def estimated_cost_ms(self) -> int:
        return 25

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if ctx.profile.level is ProfileLevel.FAST:
            return []

        profile = _resolve_profile(ctx)
        expected = _expected_profile(ctx.state)
        severity = (
            IssueSeverity.BLOCKER
            if ctx.profile.level is ProfileLevel.STRICT
            else IssueSeverity.WARNING
        )
        issues: list[ComplianceIssue] = []

        if profile is None:
            if expected:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["cross_graph_evidence_profile_ref"],
                        message="Cross-graph evidence profile is expected but unavailable.",
                        severity=severity,
                        code="CROSS_GRAPH_PROFILE_MISSING",
                        suggestion="Compile cross-graph evidence before governance checks.",
                    )
                )
            return issues

        for diagnostic in profile.diagnostics:
            if diagnostic.code != "cross_graph.ontology.unknown_concept":
                continue
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["cross_graph", diagnostic.need_id or "unknown"],
                    message=diagnostic.message,
                    severity=severity,
                    code="CROSS_GRAPH_UNKNOWN_CONCEPT",
                    suggestion="Add explicit ontology bridges for unresolved policy needs.",
                )
            )

        for assessment in profile.needs:
            path = ["cross_graph", assessment.need.need_id]
            if assessment.legal_status is LegalStatus.PROHIBITED:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=path,
                        message="Cross-graph evidence marks this need as legally prohibited.",
                        severity=severity,
                        code="CROSS_GRAPH_LEGAL_PROHIBITED",
                        suggestion="Remove the prohibited mechanism or change jurisdiction/domain assumptions.",
                    )
                )
            elif assessment.legal_status is LegalStatus.CONSTRAINED:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=path,
                        message="Cross-graph evidence marks this need as legally constrained.",
                        severity=IssueSeverity.WARNING,
                        code="CROSS_GRAPH_LEGAL_CONSTRAINED",
                        suggestion="Review applicable soft constraints and legal tradeoffs.",
                    )
                )

            if assessment.observability_status is ObservabilityStatus.PROXY_ONLY:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=path,
                        message="Only proxy-only dataset observability is available for this need.",
                        severity=IssueSeverity.WARNING,
                        code="CROSS_GRAPH_DATA_PROXY_ONLY",
                        suggestion="Validate proxy quality or add direct target data.",
                    )
                )
            elif assessment.observability_status is ObservabilityStatus.MISSING:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=path,
                        message="No dataset observability is available for this need.",
                        severity=severity,
                        code="CROSS_GRAPH_DATA_MISSING",
                        suggestion="Add a direct dataset mapping or acceptable proxy chain.",
                    )
                )

            if assessment.evidence_status is EvidenceStatus.UNSUPPORTED:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=path,
                        message="Cross-graph evidence marks this need as unsupported by literature.",
                        severity=severity,
                        code="CROSS_GRAPH_EVIDENCE_UNSUPPORTED",
                        suggestion="Add external evidence or relax unsupported edges/parameters.",
                    )
                )

            if assessment.transport_status is TransportStatus.UNSUPPORTED:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=path,
                        message="Cross-graph evidence marks this need as unsupported for transport.",
                        severity=severity,
                        code="CROSS_GRAPH_TRANSPORT_REVIEW_REQUIRED",
                        suggestion="Collect target-context evidence or run transportability analysis.",
                    )
                )
            elif (
                assessment.transport_status in {
                    TransportStatus.PARTIALLY_IDENTIFIED,
                    TransportStatus.BOUNDED_NON_IDENTIFIED,
                }
                or (
                    assessment.transport_status is TransportStatus.IDENTIFIED
                    and assessment.transport_mode is TransportMode.TRANSPORT_FORMULA
                    and assessment.requires_expert_review
                )
            ):
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=path,
                        message="This need is only transportable with expert review.",
                        severity=IssueSeverity.WARNING,
                        code="CROSS_GRAPH_TRANSPORT_REVIEW_REQUIRED",
                        suggestion="Review transport assumptions and proxy penalties before approval.",
                    )
                )

        return issues


def _resolve_profile(ctx: PassContext) -> CrossGraphEvidenceProfile | None:
    direct = ctx.state.get("cross_graph_evidence_profile")
    if isinstance(direct, CrossGraphEvidenceProfile):
        return direct
    if isinstance(direct, dict):
        try:
            return CrossGraphEvidenceProfile.model_validate(direct)
        except Exception:
            return None

    artifacts_index = ctx.state.get("artifacts_index")
    if not isinstance(artifacts_index, dict):
        return None
    raw_ref = artifacts_index.get("cross_graph_evidence_profile_ref")
    if raw_ref is None:
        return None
    store = ctx.state.get("_store")
    if store is None:
        return None
    try:
        ref = CrossGraphEvidenceProfileRef.model_validate(raw_ref)
        return load_cross_graph_evidence_profile(store, ref)
    except Exception:
        return None


def _expected_profile(state: dict[str, Any]) -> bool:
    params = state.get("params")
    if isinstance(params, dict):
        return bool(params.get("cross_graph_evidence_expected"))
    return bool(state.get("cross_graph_evidence_expected"))


__all__ = ["CrossGraphEvidencePass"]
