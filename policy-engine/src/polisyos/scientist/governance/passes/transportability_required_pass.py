from __future__ import annotations

from typing import Any

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal import CausalEffectReport, load_causal_effect_report
from polisyos.ir.refs import CausalEffectReportRef

_EXTERNAL_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "external",
        "external_report",
        "external_literature",
        "literature_external",
    }
)


class TransportabilityRequiredPass(ValidatorPass):
    """
    Law T: external-context causal estimates require transportability evidence.

    FAST   -> skip
    MVP    -> warning
    STRICT -> blocker
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

        severity = (
            IssueSeverity.BLOCKER
            if ctx.profile.level is ProfileLevel.STRICT
            else IssueSeverity.WARNING
        )

        issues: list[ComplianceIssue] = []
        reports = _resolve_reports_with_paths(ctx)
        for report_path, report in reports:
            if not _is_external_source(report):
                continue
            if _has_transportability_result(report):
                continue
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=report_path,
                    message="External CausalEffectReport lacks transportability check.",
                    severity=severity,
                    code="TRANSPORT_REQUIRED_MISSING",
                    suggestion="Run transportability check before using this estimate",
                )
            )
        return issues


def _resolve_reports_with_paths(
    ctx: PassContext,
) -> list[tuple[list[str | int], CausalEffectReport]]:
    # Multi-report contract has priority over single-report fallbacks when present and valid.
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
    ref = artifacts_index.get("causal_report_ref")
    return _load_report_from_ref(ctx, ref)


def _resolve_report_value(ctx: PassContext, raw_value: Any) -> CausalEffectReport | None:
    if isinstance(raw_value, CausalEffectReport):
        return raw_value
    if isinstance(raw_value, dict):
        try:
            return CausalEffectReport.model_validate(raw_value)
        except Exception:
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
        except Exception:
            return None

    try:
        ref = CausalEffectReportRef.model_validate(ref_payload)
    except Exception:
        return None

    try:
        return load_causal_effect_report(store, ref)
    except Exception:
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
        token = candidate.strip().lower()
        if token in _EXTERNAL_SOURCE_TYPES:
            return True
    return False


def _has_transportability_result(report: CausalEffectReport) -> bool:
    if report.transport_result is not None:
        return True
    return report.method_params.get("transport_result") is not None


__all__ = ["TransportabilityRequiredPass"]
