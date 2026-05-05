"""Require transportability evidence whenever causal effects cross source/target contexts."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal import CausalEffectReport, load_causal_effect_report
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceStatus,
    ObservabilityStatus,
    TransportStatus,
    load_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.transportability import TransportabilityStatus
from polisyos.ir.refs import CausalEffectReportRef, CrossGraphEvidenceProfileRef
from polisyos.scientist.engine.error_semantics import emit_degraded_path

_EXTERNAL_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "external",
        "external_report",
        "external_literature",
        "literature_external",
    }
)


class TransportabilityRequiredPass(ValidatorPass):
    """Apply the external-context transportability rule to causal reports.

    The pass reads direct `causal_effect_reports`/`causal_report` payloads or
    `artifacts_index.causal_report_ref` and
    `artifacts_index.transportability_result_ref` through `_store`. FAST profile
    skips the check. Missing, partial, bounds-only, or unsupported transport
    evidence is a blocker in STRICT mode and usually a warning otherwise, except
    when state explicitly marks transport as required.
    """

    @property
    def pass_id(self) -> str:
        return "transportability_required"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if ctx.profile.level is ProfileLevel.FAST:
            return []

        profile = _resolve_cross_graph_profile(ctx)
        if profile is not None:
            return _issues_from_cross_graph_profile(ctx, profile)

        severity = _unsupported_transport_severity(ctx)

        issues: list[ComplianceIssue] = []
        for report_path, report in _resolve_reports_with_paths(ctx):
            if not _is_external_source(report):
                continue
            issue = _issue_for_transport_result(
                self.pass_id,
                ctx,
                report_path,
                report,
                missing_severity=severity,
            )
            if issue is not None:
                issues.append(issue)
        return issues


def _issues_from_cross_graph_profile(
    ctx: PassContext,
    profile: CrossGraphEvidenceProfile,
) -> list[ComplianceIssue]:
    severity = _unsupported_transport_severity(ctx)
    issues: list[ComplianceIssue] = []
    for assessment in profile.needs:
        if assessment.evidence_status not in {
            EvidenceStatus.SUPPORTED,
            EvidenceStatus.MIXED,
            EvidenceStatus.INSUFFICIENT,
        }:
            continue
        if assessment.transport_status is TransportStatus.UNSUPPORTED:
            issues.append(
                ComplianceIssue(
                    pass_id="transportability_required",
                    path=["cross_graph", assessment.need.need_id],
                    message=(
                        "Unified evidence profile marks this need as unsupported for transport."
                    ),
                    severity=severity,
                    code="TRANSPORT_REQUIRED_MISSING",
                    suggestion="Run transportability check or obtain target-context evidence.",
                )
            )
            continue
        if assessment.transport_status in {
            TransportStatus.PARTIALLY_IDENTIFIED,
            TransportStatus.BOUNDED_NON_IDENTIFIED,
        } or assessment.observability_status in {
            ObservabilityStatus.MISSING,
            ObservabilityStatus.PROXY_ONLY,
        }:
            issues.append(
                ComplianceIssue(
                    pass_id="transportability_required",
                    path=["cross_graph", assessment.need.need_id],
                    message=(
                        "Unified evidence profile requires transportability review before reuse."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="TRANSPORT_REQUIRED_MISSING",
                    suggestion="Run transportability check before using this estimate.",
                )
            )
    return issues


def _resolve_reports_with_paths(
    ctx: PassContext,
) -> list[tuple[list[str | int], CausalEffectReport]]:
    raw_reports = ctx.state.get("causal_effect_reports")
    if isinstance(raw_reports, list):
        resolved: list[tuple[list[str | int], CausalEffectReport]] = []
        for index, raw_report in enumerate(raw_reports):
            report = _resolve_report_value(ctx, raw_report)
            if report is None:
                continue
            resolved.append((["causal_effect_reports", index, "transport_result"], report))
        return resolved

    single_report = _resolve_single_report(ctx)
    if single_report is None:
        return []
    return [(["causal_report", "transport_result"], single_report)]


def _resolve_single_report(ctx: PassContext) -> CausalEffectReport | None:
    direct = ctx.state.get("causal_report")
    resolved = _resolve_report_value(ctx, direct)
    if resolved is not None:
        return resolved

    artifacts_index = ctx.state.get("artifacts_index")
    if not isinstance(artifacts_index, dict):
        return None
    return _load_report_from_ref(ctx, artifacts_index.get("causal_report_ref"))


def _resolve_report_value(ctx: PassContext, raw_value: Any) -> CausalEffectReport | None:
    if isinstance(raw_value, CausalEffectReport):
        return raw_value
    if isinstance(raw_value, dict):
        try:
            return CausalEffectReport.model_validate(raw_value)
        except (AttributeError, TypeError, ValidationError, ValueError) as exc:
            emit_degraded_path(
                component="governance.transportability_required_pass",
                operation="resolve_report_value",
                reason="report_parse_failed",
                exc=exc,
                details={
                    "raw_value_keys": (sorted(raw_value) if isinstance(raw_value, dict) else None)
                },
            )
            return _load_report_from_ref(ctx, raw_value)
    if raw_value is None:
        return None
    return _load_report_from_ref(ctx, raw_value)


def _load_report_from_ref(ctx: PassContext, raw_ref: Any) -> CausalEffectReport | None:
    if raw_ref is None:
        return None
    store = ctx.state.get("_store")
    if store is None:
        return None

    ref_payload = raw_ref
    if hasattr(raw_ref, "model_dump"):
        try:
            ref_payload = raw_ref.model_dump(mode="json")
        except (AttributeError, TypeError, ValidationError, ValueError) as exc:
            emit_degraded_path(
                component="governance.transportability_required_pass",
                operation="load_report_from_ref",
                reason="artifact_ref_serialize_failed",
                exc=exc,
            )
            return None

    try:
        ref = CausalEffectReportRef.model_validate(ref_payload)
    except (AttributeError, TypeError, ValidationError, ValueError) as exc:
        emit_degraded_path(
            component="governance.transportability_required_pass",
            operation="load_report_from_ref",
            reason="artifact_ref_parse_failed",
            exc=exc,
            details={"ref_payload": ref_payload},
        )
        return None

    try:
        return load_causal_effect_report(store, ref)
    except (AttributeError, OSError, RuntimeError, TypeError, ValidationError, ValueError) as exc:
        emit_degraded_path(
            component="governance.transportability_required_pass",
            operation="load_report_from_ref",
            reason="artifact_load_failed",
            exc=exc,
            details={"ref": ref.model_dump(mode="json")},
        )
        return None


def _resolve_cross_graph_profile(ctx: PassContext) -> CrossGraphEvidenceProfile | None:
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
    except (AttributeError, OSError, RuntimeError, TypeError, ValidationError, ValueError) as exc:
        emit_degraded_path(
            component="governance.transportability_required_pass",
            operation="resolve_cross_graph_profile",
            reason="artifact_load_failed",
            exc=exc,
            details={"raw_ref": raw_ref},
        )
        return None


def _is_external_source(report: CausalEffectReport) -> bool:
    source_candidates: list[Any] = [
        report.method_params.get("source_type"),
        report.metadata.get("source_type"),
        report.metadata.get("evidence_source"),
    ]
    for candidate in source_candidates:
        if not isinstance(candidate, str):
            continue
        if candidate.strip().lower() in _EXTERNAL_SOURCE_TYPES:
            return True
    return False


def _has_transportability_result(report: CausalEffectReport) -> bool:
    if report.transport_result is None:
        return report.method_params.get("transport_result") is not None
    return report.transport_result.status in {
        TransportabilityStatus.IDENTIFIED,
        TransportabilityStatus.PARTIALLY_IDENTIFIED,
        TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
    }


def _severity_for_partial_transport(ctx: PassContext) -> IssueSeverity:
    return (
        IssueSeverity.BLOCKER if ctx.profile.level is ProfileLevel.STRICT else IssueSeverity.WARNING
    )


def _unsupported_transport_severity(ctx: PassContext) -> IssueSeverity:
    if _state_transport_required(ctx.state):
        return IssueSeverity.BLOCKER
    return (
        IssueSeverity.BLOCKER if ctx.profile.level is ProfileLevel.STRICT else IssueSeverity.WARNING
    )


def _issue_for_transport_result(
    pass_id: str,
    ctx: PassContext,
    report_path: list[str | int],
    report: CausalEffectReport,
    *,
    missing_severity: IssueSeverity,
) -> ComplianceIssue | None:
    transport = report.transport_result
    if transport is None and report.method_params.get("transport_result") is not None:
        return None
    if transport is None:
        return ComplianceIssue(
            pass_id=pass_id,
            path=report_path,
            message="External CausalEffectReport lacks transportability check.",
            severity=missing_severity,
            code="TRANSPORT_REQUIRED_MISSING",
            suggestion="Run transportability check before using this estimate",
        )
    if transport.status is TransportabilityStatus.IDENTIFIED:
        return None
    if transport.status is TransportabilityStatus.PARTIALLY_IDENTIFIED:
        return ComplianceIssue(
            pass_id=pass_id,
            path=report_path,
            message="External CausalEffectReport is only partially identified under transport.",
            severity=_severity_for_partial_transport(ctx),
            code="TRANSPORT_PARTIAL_IDENTIFICATION",
            suggestion=(
                "Review partial-identification regions or add stronger target-context evidence."
            ),
        )
    if transport.status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED:
        return ComplianceIssue(
            pass_id=pass_id,
            path=report_path,
            message="External CausalEffectReport is only bounded under transport assumptions.",
            severity=_severity_for_partial_transport(ctx),
            code="TRANSPORT_BOUNDS_ONLY",
            suggestion="Treat result as bounds-only or collect target-context evidence.",
        )
    return ComplianceIssue(
        pass_id=pass_id,
        path=report_path,
        message="External CausalEffectReport is unsupported under transport assumptions.",
        severity=missing_severity,
        code="TRANSPORT_UNSUPPORTED",
        suggestion=(
            "Do not reuse this estimate without target-context evidence or an "
            "approved degraded override."
        ),
    )


def _state_transport_required(state: dict[str, Any]) -> bool:
    params = state.get("params")
    if not isinstance(params, dict):
        return False
    value = params.get("transport_required")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


__all__ = ["TransportabilityRequiredPass"]
