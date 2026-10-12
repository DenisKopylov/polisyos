"""Require transportability evidence whenever causal effects cross source/target contexts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    TransportabilityProofReviewGrade,
    load_causal_effect_report,
    transportability_proof_review_grade,
)
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceStatus,
    ObservabilityStatus,
    TransportStatus,
    load_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    load_transportability_result,
)
from polisyos.ir.registry.refs import (
    CausalEffectReportRef,
    CrossGraphEvidenceProfileRef,
    TransportabilityResultRef,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path


@dataclass(frozen=True)
class _ReportCandidate:
    """One validated report and the paths that identify its supplied source."""

    source_path: list[str | int]
    transport_path: list[str | int]
    report: CausalEffectReport
    canonical_transport_null_supplied: bool


@dataclass(frozen=True)
class _ReportSelection:
    """Resolved report set plus issues from every supplied source."""

    reports: tuple[_ReportCandidate, ...]
    issues: tuple[ComplianceIssue, ...]


@dataclass(frozen=True)
class _ProfileCandidate:
    """One validated cross-graph profile and the path that supplied it."""

    source_path: list[str | int]
    profile: CrossGraphEvidenceProfile


@dataclass(frozen=True)
class _ProfileSelection:
    """Selected profile plus explicit issues from all supplied profile sources."""

    profile: CrossGraphEvidenceProfile | None
    issues: tuple[ComplianceIssue, ...]


@dataclass(frozen=True)
class _ProfileNeedInput:
    """Frozen profile predicates and their source-derived review grade."""

    path: list[str | int]
    evidence_status: EvidenceStatus
    transport_status: TransportStatus
    observability_status: ObservabilityStatus
    review_grade: TransportabilityProofReviewGrade


@dataclass(frozen=True)
class _TransportResultInput:
    """Typed transport result intake, preserving supplied-invalid state."""

    supplied: bool
    result: TransportabilityResult | None = None
    review_grade: TransportabilityProofReviewGrade | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class _AdmittedReport:
    """Report and result frozen together at the common pass intake."""

    candidate: _ReportCandidate
    transport: _TransportResultInput


@dataclass(frozen=True)
class _PassEvidenceAdmission:
    """All typed transport inputs and gate dispositions resolved before evaluation."""

    reports: tuple[_AdmittedReport, ...]
    direct_result: _TransportResultInput
    profile_needs: tuple[_ProfileNeedInput, ...]
    missing_severity: IssueSeverity
    transport_required: bool
    issues: tuple[ComplianceIssue, ...]


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

        admission = _resolve_pass_evidence(ctx)
        issues = list(admission.issues)
        for need in admission.profile_needs:
            issue = _issue_for_profile_need(
                self.pass_id,
                need,
                missing_severity=admission.missing_severity,
            )
            if issue is not None:
                issues.append(issue)

        for admitted in admission.reports:
            candidate = admitted.candidate
            result_input = admitted.transport
            if not _is_external_source(candidate.report):
                continue
            issue = _issue_for_transport_result(
                self.pass_id,
                candidate.transport_path,
                result_input,
                missing_severity=admission.missing_severity,
                compare_direct_result=(
                    admission.direct_result.result
                    if admission.direct_result.error_code is None
                    else None
                ),
            )
            if issue is not None:
                issues.append(issue)

        direct_input = admission.direct_result
        if direct_input.supplied:
            if direct_input.error_code is not None:
                issues.append(
                    _transport_input_issue(
                        self.pass_id,
                        ["artifacts_index", "transportability_result_ref"],
                        direct_input.error_code,
                        admission.missing_severity,
                    )
                )
            elif direct_input.result is not None:
                matching = [
                    admitted
                    for admitted in admission.reports
                    if admitted.transport.result is not None
                    and _same_transport_result(admitted.transport.result, direct_input.result)
                ]
                conflicting = [
                    admitted
                    for admitted in admission.reports
                    if admitted.transport.result is not None
                    and not _same_transport_result(admitted.transport.result, direct_input.result)
                ]
                if conflicting:
                    issues.append(
                        _transport_input_issue(
                            self.pass_id,
                            ["artifacts_index", "transportability_result_ref"],
                            "TRANSPORT_RESULT_INPUT_CONFLICT",
                            admission.missing_severity,
                        )
                    )
                elif not any(_is_external_source(item.candidate.report) for item in matching):
                    issue = _issue_for_direct_transport_result(
                        self.pass_id,
                        direct_input,
                        missing_severity=admission.missing_severity,
                    )
                    if issue is not None:
                        issues.append(issue)
        if admission.transport_required and not _has_transport_gate_issue(issues):
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["params", "transport_required"],
                    message=(
                        "Transportability is explicitly required, but no admitted result "
                        "establishes a transport disposition."
                    ),
                    severity=IssueSeverity.BLOCKER,
                    code="TRANSPORT_REQUIRED_MISSING",
                    suggestion=(
                        "Supply a resolved transport result or cross-graph need assessment "
                        "that satisfies the required transport gate."
                    ),
                )
            )
        return issues


def _resolve_pass_evidence(ctx: PassContext) -> _PassEvidenceAdmission:
    """Resolve and grade every supplied pass input before applying gate semantics."""
    transport_required, parameter_issues = _transport_required_input(ctx)
    missing_severity = _unsupported_transport_severity(
        ctx, transport_required=transport_required
    )
    report_selection = _resolve_reports_with_paths(ctx, severity=missing_severity)
    direct_result = _resolve_direct_transport_result(ctx)
    profile_selection = _resolve_cross_graph_profile(ctx, severity=missing_severity)
    reports = tuple(
        _AdmittedReport(
            candidate=candidate,
            transport=_transport_result_from_report(
                candidate.report,
                canonical_transport_null_supplied=candidate.canonical_transport_null_supplied,
            ),
        )
        for candidate in report_selection.reports
    )
    profile = profile_selection.profile
    profile_needs = tuple(
        _ProfileNeedInput(
            path=["cross_graph", assessment.need.need_id],
            evidence_status=assessment.evidence_status,
            transport_status=assessment.transport_status,
            observability_status=assessment.observability_status,
            review_grade=(
                TransportabilityProofReviewGrade.REVIEW_REQUIRED
                if assessment.requires_expert_review
                else TransportabilityProofReviewGrade.UNKNOWN
                if assessment.transport_status is TransportStatus.IDENTIFIED
                else TransportabilityProofReviewGrade.NOT_APPLICABLE
            ),
        )
        for assessment in (profile.needs if profile is not None else ())
    )
    return _PassEvidenceAdmission(
        reports=reports,
        direct_result=direct_result,
        profile_needs=profile_needs,
        missing_severity=missing_severity,
        transport_required=transport_required,
        issues=tuple(
            [*parameter_issues, *report_selection.issues, *profile_selection.issues]
        ),
    )


def _issue_for_profile_need(
    pass_id: str,
    need: _ProfileNeedInput,
    *,
    missing_severity: IssueSeverity,
) -> ComplianceIssue | None:
    if (
        need.evidence_status is EvidenceStatus.UNSUPPORTED
        or need.transport_status is TransportStatus.UNSUPPORTED
    ):
        return ComplianceIssue(
            pass_id=pass_id,
            path=need.path,
            message="Unified evidence profile does not establish supported transport for this need.",
            severity=missing_severity,
            code="TRANSPORT_REQUIRED_MISSING",
            suggestion="Run transportability check or obtain target-context evidence.",
        )
    if need.review_grade is TransportabilityProofReviewGrade.REVIEW_REQUIRED:
        return ComplianceIssue(
            pass_id=pass_id,
            path=need.path,
            message="Unified evidence profile marks an identified transport candidate as requiring expert review.",
            severity=missing_severity,
            code="TRANSPORT_REVIEW_REQUIRED",
            suggestion="Resolve the candidate's review requirements before protected reuse.",
        )
    if need.transport_status is TransportStatus.IDENTIFIED:
        # The profile carries a status but no source-bound proof or verifier
        # receipt. Keep it visible as a candidate, but do not let the status
        # itself clear a strict protected gate.
        return _unknown_transport_proof_issue(
            pass_id,
            need.path,
            severity=missing_severity,
        )
    if (
        need.transport_status
        in {TransportStatus.PARTIALLY_IDENTIFIED, TransportStatus.BOUNDED_NON_IDENTIFIED}
        or need.observability_status is not ObservabilityStatus.DIRECT
        or need.evidence_status is EvidenceStatus.INSUFFICIENT
    ):
        return ComplianceIssue(
            pass_id=pass_id,
            path=need.path,
            message="Unified evidence profile leaves a transport premise partial or not established.",
            severity=missing_severity,
            code="TRANSPORT_REQUIRED_MISSING",
            suggestion="Run transportability check before using this estimate.",
        )
    return None


def _resolve_reports_with_paths(
    ctx: PassContext,
    *,
    severity: IssueSeverity,
) -> _ReportSelection:
    """Resolve every supplied report source before choosing the governed set."""
    issues: list[ComplianceIssue] = []
    list_candidates: list[_ReportCandidate] = []
    alias_candidates: list[_ReportCandidate] = []

    state = ctx.state
    if "causal_effect_reports" in state:
        raw_reports = state["causal_effect_reports"]
        if not isinstance(raw_reports, list):
            issues.append(
                _report_input_issue(
                    ["causal_effect_reports"], severity, "causal_effect_reports must be a list"
                )
            )
        else:
            for index, raw_report in enumerate(raw_reports):
                path = ["causal_effect_reports", index]
                report = _resolve_report_value(ctx, raw_report, path=path)
                if report is None:
                    issues.append(_report_input_issue(path, severity, "report input is invalid"))
                    continue
                list_candidates.append(
                    _ReportCandidate(
                        source_path=path,
                        transport_path=[*path, "transport_result"],
                        report=report,
                        canonical_transport_null_supplied=(
                            _explicit_null_transport_result(raw_report)
                        ),
                    )
                )

    if "causal_report" in state:
        path = ["causal_report"]
        report = _resolve_report_value(ctx, state["causal_report"], path=path)
        if report is None:
            issues.append(_report_input_issue(path, severity, "report input is invalid"))
        else:
            alias_candidates.append(
                _ReportCandidate(
                    source_path=path,
                    transport_path=[*path, "transport_result"],
                    report=report,
                    canonical_transport_null_supplied=(
                        _explicit_null_transport_result(state["causal_report"])
                    ),
                )
            )

    index = state.get("artifacts_index")
    if "artifacts_index" in state and not isinstance(index, Mapping):
        issues.append(
            _report_input_issue(["artifacts_index"], severity, "artifact index is not a mapping")
        )
    elif isinstance(index, Mapping) and "causal_report_ref" in index:
        path = ["artifacts_index", "causal_report_ref"]
        report = _resolve_report_value(ctx, index["causal_report_ref"], path=path)
        if report is None:
            issues.append(_report_input_issue(path, severity, "report reference is invalid"))
        else:
            alias_candidates.append(
                _ReportCandidate(
                    source_path=path,
                    transport_path=[*path, "transport_result"],
                    report=report,
                    canonical_transport_null_supplied=False,
                )
            )

    selected_list = _deduplicate_report_candidates(list_candidates)
    selected_aliases = _deduplicate_report_candidates(alias_candidates)
    if selected_list:
        if any(not _candidate_matches(candidate, selected_list) for candidate in selected_aliases):
            conflict_path = next(
                candidate.source_path
                for candidate in selected_aliases
                if not _candidate_matches(candidate, selected_list)
            )
            issues.append(
                _report_input_issue(
                    conflict_path,
                    severity,
                    "report sources do not resolve to one selected report set",
                    code="TRANSPORT_REPORT_SOURCE_CONFLICT",
                )
            )
            return _ReportSelection(reports=(), issues=tuple(issues))
        selected_list = _merge_explicit_null_candidates(selected_list, selected_aliases)
        return _ReportSelection(reports=tuple(selected_list), issues=tuple(issues))

    if len(selected_aliases) > 1:
        issues.append(
            _report_input_issue(
                selected_aliases[1].source_path,
                severity,
                "single and CAS report sources resolve to different report contents",
                code="TRANSPORT_REPORT_SOURCE_CONFLICT",
            )
        )
        return _ReportSelection(reports=(), issues=tuple(issues))
    return _ReportSelection(reports=tuple(selected_aliases), issues=tuple(issues))


def _deduplicate_report_candidates(
    candidates: list[_ReportCandidate],
) -> list[_ReportCandidate]:
    """Keep each exact payload while retaining explicit-null source provenance."""
    unique: list[_ReportCandidate] = []
    for candidate in candidates:
        match = next(
            (
                index
                for index, existing in enumerate(unique)
                if _same_report(candidate.report, existing.report)
            ),
            None,
        )
        if match is None:
            unique.append(candidate)
        elif (
            candidate.canonical_transport_null_supplied
            and not unique[match].canonical_transport_null_supplied
        ):
            unique[match] = candidate
    return unique


def _merge_explicit_null_candidates(
    selected: list[_ReportCandidate],
    aliases: list[_ReportCandidate],
) -> list[_ReportCandidate]:
    """Carry supplied-null facts from matching aliases into the selected set."""
    merged: list[_ReportCandidate] = []
    for candidate in selected:
        explicit_alias = next(
            (
                alias
                for alias in aliases
                if _same_report(alias.report, candidate.report)
                and alias.canonical_transport_null_supplied
            ),
            None,
        )
        merged.append(explicit_alias or candidate)
    return merged


def _same_report(left: CausalEffectReport, right: CausalEffectReport) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _candidate_matches(
    candidate: _ReportCandidate,
    selected: list[_ReportCandidate],
) -> bool:
    return any(_same_report(candidate.report, item.report) for item in selected)


def _report_input_issue(
    path: list[str | int],
    severity: IssueSeverity,
    detail: str,
    *,
    code: str = "TRANSPORT_REPORT_INPUT_INVALID",
) -> ComplianceIssue:
    return ComplianceIssue(
        pass_id="transportability_required",
        path=path,
        message=f"A supplied causal report input could not be resolved safely: {detail}.",
        severity=severity,
        code=code,
        suggestion="Repair or remove the malformed/conflicting source before protected reuse.",
    )


def _profile_input_issue(
    path: list[str | int],
    severity: IssueSeverity,
    detail: str,
    *,
    code: str = "CROSS_GRAPH_PROFILE_INPUT_INVALID",
) -> ComplianceIssue:
    """Return one explicit disposition for a supplied invalid profile source."""
    return ComplianceIssue(
        pass_id="transportability_required",
        path=path,
        message=f"A supplied cross-graph profile could not be admitted safely: {detail}.",
        severity=severity,
        code=code,
        suggestion="Repair or remove the malformed/conflicting profile before protected reuse.",
    )


def _model_payload(value: Any) -> Any:
    """Serialize model-like input without trusting its already-constructed instance."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python", exclude_unset=True)
    return value


def _revalidate_model(model_cls: type[Any], value: Any) -> Any:
    """Revalidate a model instance or mapping at this consumer boundary."""
    return model_cls.model_validate(_model_payload(value))


def _has_transport_gate_issue(issues: list[ComplianceIssue]) -> bool:
    """Whether an already-emitted pass finding blocks a duplicate required-missing issue."""
    return any(issue.pass_id == "transportability_required" for issue in issues)


def _resolve_report_value(
    ctx: PassContext,
    raw_value: Any,
    *,
    path: list[str | int],
) -> CausalEffectReport | None:
    """Resolve a typed report or explicit reference; malformed data never becomes absence."""
    try:
        if isinstance(raw_value, CausalEffectReport):
            return _revalidate_model(CausalEffectReport, raw_value)
        if isinstance(raw_value, CausalEffectReportRef):
            return _load_report_from_ref(ctx, raw_value)

        payload = _model_payload(raw_value)
        if isinstance(payload, Mapping):
            if "kind" in payload or "artifact_id" in payload:
                ref = _revalidate_model(CausalEffectReportRef, payload)
                return _load_report_from_ref(ctx, ref)
            return _revalidate_model(CausalEffectReport, payload)
        raise TypeError("report_source_must_be_typed_report_or_mapping")
    except (
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValidationError,
        ValueError,
    ) as exc:
        emit_degraded_path(
            component="governance.transportability_required_pass",
            operation="resolve_report_input",
            reason="report_source_invalid_or_unresolved",
            exc=exc,
            details={"path": path, "raw_type": type(raw_value).__name__},
        )
        return None


def _explicit_null_transport_result(raw_value: Any) -> bool:
    """Report whether a direct report source explicitly supplied a null result.

    CAS report references return false because the current report serializer
    materializes nullable defaults; CAS provenance cannot distinguish that
    default from an explicit null after persistence.
    """
    if isinstance(raw_value, CausalEffectReport):
        return (
            raw_value.transport_result is None and "transport_result" in raw_value.model_fields_set
        )
    if isinstance(raw_value, CausalEffectReportRef):
        return False
    if isinstance(raw_value, Mapping):
        if "kind" in raw_value or "artifact_id" in raw_value:
            return False
        return "transport_result" in raw_value and raw_value["transport_result"] is None
    if hasattr(raw_value, "model_dump"):
        payload = raw_value.model_dump(mode="json")
        if isinstance(payload, Mapping) and not {
            "kind",
            "artifact_id",
        }.intersection(payload):
            return "transport_result" in payload and payload["transport_result"] is None
    return False


def _load_report_from_ref(
    ctx: PassContext,
    ref: CausalEffectReportRef,
) -> CausalEffectReport:
    store = ctx.state.get("_store")
    if store is None:
        raise ValueError("selected_report_reference_requires_artifact_store")
    validated_ref = _revalidate_model(CausalEffectReportRef, ref)
    report = load_causal_effect_report(_ensure_ir_artifact_store(store), validated_ref)
    return _revalidate_model(CausalEffectReport, report)


def _resolve_cross_graph_profile(
    ctx: PassContext,
    *,
    severity: IssueSeverity,
) -> _ProfileSelection:
    """Resolve both direct and CAS profile sources without collapsing failures."""
    candidates: list[_ProfileCandidate] = []
    issues: list[ComplianceIssue] = []
    state = ctx.state

    if "cross_graph_evidence_profile" in state:
        path = ["cross_graph_evidence_profile"]
        profile = _resolve_profile_value(ctx, state["cross_graph_evidence_profile"])
        if profile is None:
            issues.append(
                _profile_input_issue(path, severity, "direct profile is invalid")
            )
        else:
            candidates.append(_ProfileCandidate(source_path=path, profile=profile))

    index = state.get("artifacts_index")
    if isinstance(index, Mapping) and "cross_graph_evidence_profile_ref" in index:
        path = ["artifacts_index", "cross_graph_evidence_profile_ref"]
        profile = _resolve_profile_value(ctx, index["cross_graph_evidence_profile_ref"])
        if profile is None:
            issues.append(
                _profile_input_issue(path, severity, "profile reference is invalid or unresolved")
            )
        else:
            candidates.append(_ProfileCandidate(source_path=path, profile=profile))

    if len(candidates) > 1:
        first = candidates[0]
        if any(not _same_profile(first.profile, candidate.profile) for candidate in candidates[1:]):
            conflict = next(
                candidate
                for candidate in candidates[1:]
                if not _same_profile(first.profile, candidate.profile)
            )
            issues.append(
                _profile_input_issue(
                    conflict.source_path,
                    severity,
                    "direct and artifact-reference profiles resolve to different contents",
                    code="CROSS_GRAPH_PROFILE_SOURCE_CONFLICT",
                )
            )
            return _ProfileSelection(profile=None, issues=tuple(issues))

    selected = candidates[0].profile if candidates else None
    return _ProfileSelection(profile=selected, issues=tuple(issues))


def _resolve_profile_value(
    ctx: PassContext,
    raw_value: Any,
) -> CrossGraphEvidenceProfile | None:
    """Validate a direct profile or resolve a typed profile reference."""
    try:
        payload = _model_payload(raw_value)
        if isinstance(raw_value, CrossGraphEvidenceProfileRef):
            return _load_profile_from_ref(ctx, raw_value)
        if isinstance(raw_value, CrossGraphEvidenceProfile):
            return _revalidate_model(CrossGraphEvidenceProfile, raw_value)
        if isinstance(payload, Mapping):
            if "kind" in payload or "artifact_id" in payload:
                ref = _revalidate_model(CrossGraphEvidenceProfileRef, payload)
                return _load_profile_from_ref(ctx, ref)
            return _revalidate_model(CrossGraphEvidenceProfile, payload)
        raise TypeError("profile_source_must_be_typed_profile_reference_or_mapping")
    except (
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValidationError,
        ValueError,
    ) as exc:
        emit_degraded_path(
            component="governance.transportability_required_pass",
            operation="resolve_cross_graph_profile",
            reason="profile_source_invalid_or_unresolved",
            exc=exc,
            details={"raw_type": type(raw_value).__name__},
        )
        return None


def _load_profile_from_ref(
    ctx: PassContext,
    ref: CrossGraphEvidenceProfileRef,
) -> CrossGraphEvidenceProfile:
    """Resolve one profile reference through CAS and revalidate its payload."""
    store = ctx.state.get("_store")
    if store is None:
        raise ValueError("selected_cross_graph_profile_ref_requires_artifact_store")
    validated_ref = _revalidate_model(CrossGraphEvidenceProfileRef, ref)
    profile = load_cross_graph_evidence_profile(_ensure_ir_artifact_store(store), validated_ref)
    return _revalidate_model(CrossGraphEvidenceProfile, profile)


def _same_profile(
    left: CrossGraphEvidenceProfile,
    right: CrossGraphEvidenceProfile,
) -> bool:
    """Compare profiles after both sides have been revalidated."""
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _issue_for_direct_transport_result(
    pass_id: str,
    result_input: _TransportResultInput,
    *,
    missing_severity: IssueSeverity,
) -> ComplianceIssue | None:
    path = ["artifacts_index", "transportability_result_ref"]
    if result_input.error_code is not None:
        return _transport_input_issue(pass_id, path, result_input.error_code, missing_severity)
    if result_input.result is None:
        return None
    return _issue_for_transport_result_value(
        pass_id,
        path,
        result_input.result,
        result_input.review_grade,
        missing_severity=missing_severity,
    )


def _resolve_direct_transport_result(ctx: PassContext) -> _TransportResultInput:
    index = ctx.state.get("artifacts_index")
    if not isinstance(index, Mapping) or "transportability_result_ref" not in index:
        return _TransportResultInput(supplied=False)

    raw_ref = index["transportability_result_ref"]
    try:
        if isinstance(raw_ref, TransportabilityResultRef):
            ref = _revalidate_model(TransportabilityResultRef, raw_ref)
        else:
            payload = _model_payload(raw_ref)
            if not isinstance(payload, Mapping):
                raise TypeError("transport_result_ref_must_be_a_mapping")
            ref = _revalidate_model(TransportabilityResultRef, payload)
        store = ctx.state.get("_store")
        if store is None:
            raise ValueError("selected_transport_result_ref_requires_artifact_store")
        result = load_transportability_result(_ensure_ir_artifact_store(store), ref)
        result = _revalidate_model(TransportabilityResult, result)
        return _transport_result_input(result)
    except (
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValidationError,
        ValueError,
    ) as exc:
        emit_degraded_path(
            component="governance.transportability_required_pass",
            operation="resolve_direct_transport_result",
            reason="transport_result_source_invalid_or_unresolved",
            exc=exc,
            details={"raw_type": type(raw_ref).__name__},
        )
        return _TransportResultInput(supplied=True, error_code="TRANSPORT_RESULT_INPUT_INVALID")


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


def _transport_result_from_report(
    report: CausalEffectReport,
    *,
    canonical_transport_null_supplied: bool,
) -> _TransportResultInput:
    canonical = report.transport_result
    legacy_present = "transport_result" in report.method_params

    if canonical is None and canonical_transport_null_supplied:
        return _TransportResultInput(supplied=True, error_code="TRANSPORT_RESULT_INPUT_INVALID")

    legacy: TransportabilityResult | None = None
    if legacy_present:
        raw_legacy = report.method_params["transport_result"]
        try:
            legacy = _revalidate_model(TransportabilityResult, raw_legacy)
        except (AttributeError, TypeError, ValidationError, ValueError):
            return _TransportResultInput(supplied=True, error_code="TRANSPORT_RESULT_INPUT_INVALID")

    if (
        canonical is not None
        and legacy is not None
        and not _same_transport_result(canonical, legacy)
    ):
        return _TransportResultInput(supplied=True, error_code="TRANSPORT_RESULT_INPUT_CONFLICT")
    result = canonical or legacy
    return (
        _transport_result_input(result)
        if result is not None
        else _TransportResultInput(supplied=False)
    )


def _transport_result_input(result: TransportabilityResult) -> _TransportResultInput:
    """Freeze the validated result and its recomputed review grade at intake."""
    validated = _revalidate_model(TransportabilityResult, result)
    return _TransportResultInput(
        supplied=True,
        result=validated,
        review_grade=transportability_proof_review_grade(validated),
    )


def _same_transport_result(
    left: TransportabilityResult,
    right: TransportabilityResult,
) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _transport_input_issue(
    pass_id: str,
    path: list[str | int],
    code: str,
    severity: IssueSeverity,
) -> ComplianceIssue:
    if code == "TRANSPORT_RESULT_INPUT_CONFLICT":
        message = "Supplied transport-result sources conflict after typed validation."
        suggestion = "Resolve the conflicting result fields or references before reuse."
    else:
        message = "A supplied transport-result input could not be validated or resolved."
        suggestion = "Repair or remove the malformed result or reference before protected reuse."
    return ComplianceIssue(
        pass_id=pass_id,
        path=path,
        message=message,
        severity=severity,
        code=code,
        suggestion=suggestion,
    )


def _review_required_transport_issue(
    pass_id: str,
    path: list[str | int],
    transport: TransportabilityResult,
    *,
    severity: IssueSeverity,
) -> ComplianceIssue:
    reasons = ", ".join(transport.expert_review_reasons)
    if not reasons:
        metadata = transport.metadata if isinstance(transport.metadata, dict) else {}
        if metadata.get("backend_id") == "y0":
            reasons = "source-data existence, currentness, and authority remain not established"
        else:
            reasons = "scoped transport evidence requires review"
    return ComplianceIssue(
        pass_id=pass_id,
        path=path,
        message=f"Identified transport candidate requires expert review: {reasons}.",
        severity=severity,
        code="TRANSPORT_REVIEW_REQUIRED",
        suggestion="Resolve the candidate's review requirements before protected reuse.",
    )


def _unknown_transport_proof_issue(
    pass_id: str,
    path: list[str | int],
    *,
    severity: IssueSeverity,
) -> ComplianceIssue:
    return ComplianceIssue(
        pass_id=pass_id,
        path=path,
        message=(
            "Identified transport result has no validated producer and proof scope; "
            "protected reuse remains blocked."
        ),
        severity=severity,
        code="TRANSPORT_PROOF_GRADE_UNKNOWN",
        suggestion=(
            "Recompute the result through a supported scoped producer and retain its proof and review predicates."
        ),
    )


def _unsupported_transport_severity(
    ctx: PassContext,
    *,
    transport_required: bool,
) -> IssueSeverity:
    if transport_required:
        return IssueSeverity.BLOCKER
    return (
        IssueSeverity.BLOCKER if ctx.profile.level is ProfileLevel.STRICT else IssueSeverity.WARNING
    )


def _issue_for_transport_result(
    pass_id: str,
    report_path: list[str | int],
    result_input: _TransportResultInput,
    *,
    missing_severity: IssueSeverity,
    compare_direct_result: TransportabilityResult | None = None,
) -> ComplianceIssue | None:
    if result_input.error_code is not None:
        return _transport_input_issue(
            pass_id, report_path, result_input.error_code, missing_severity
        )
    transport = result_input.result
    if (
        transport is not None
        and compare_direct_result is not None
        and not _same_transport_result(transport, compare_direct_result)
    ):
        # Report and direct CAS results disagree. The shared conflict issue is
        # emitted by validate(); do not also grade one side as if it were the
        # selected value.
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
    return _issue_for_transport_result_value(
        pass_id,
        report_path,
        transport,
        result_input.review_grade,
        missing_severity=missing_severity,
    )


def _issue_for_transport_result_value(
    pass_id: str,
    path: list[str | int],
    transport: TransportabilityResult,
    review_grade: TransportabilityProofReviewGrade | None,
    *,
    missing_severity: IssueSeverity,
) -> ComplianceIssue | None:
    if transport.status is TransportabilityStatus.IDENTIFIED:
        if review_grade is TransportabilityProofReviewGrade.REVIEW_REQUIRED:
            return _review_required_transport_issue(
                pass_id, path, transport, severity=missing_severity
            )
        if review_grade is not TransportabilityProofReviewGrade.NO_ADDITIONAL_REVIEW:
            return _unknown_transport_proof_issue(
                pass_id, path, severity=missing_severity
            )
        return None
    if transport.status is TransportabilityStatus.PARTIALLY_IDENTIFIED:
        return ComplianceIssue(
            pass_id=pass_id,
            path=path,
            message="Transportability artifact is only partially identified.",
            severity=missing_severity,
            code="TRANSPORT_PARTIAL_IDENTIFICATION",
            suggestion=(
                "Review partial-identification regions or add stronger target-context evidence."
            ),
        )
    if transport.status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED:
        return ComplianceIssue(
            pass_id=pass_id,
            path=path,
            message="Transportability artifact is bounds-only.",
            severity=missing_severity,
            code="TRANSPORT_BOUNDS_ONLY",
            suggestion="Treat result as bounds-only or collect target-context evidence.",
        )
    return ComplianceIssue(
        pass_id=pass_id,
        path=path,
        message="Transportability artifact is unsupported.",
        severity=missing_severity,
        code="TRANSPORT_UNSUPPORTED",
        suggestion=(
            "Do not approve automatically; add a causal report/graph, target-context "
            "evidence, or an approved degraded override."
        ),
    )


def _transport_required_input(
    ctx: PassContext,
) -> tuple[bool, tuple[ComplianceIssue, ...]]:
    """Parse the existing transport-required parameter without defaulting malformed input."""
    state = ctx.state
    if "params" not in state:
        return False, ()

    severity = (
        IssueSeverity.BLOCKER
        if ctx.profile.level is ProfileLevel.STRICT
        else IssueSeverity.WARNING
    )
    params = state["params"]
    if not isinstance(params, Mapping):
        return False, (
            _transport_parameter_issue(
                ["params"],
                severity,
                "parameter container must be a mapping",
            ),
        )
    if "transport_required" not in params:
        return False, ()

    raw_value = params["transport_required"]
    if isinstance(raw_value, bool):
        return raw_value, ()
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True, ()
        if normalized in {"0", "false", "no", "off"}:
            return False, ()
    return False, (
        _transport_parameter_issue(
            ["params", "transport_required"],
            severity,
            "supplied value must be a boolean or a recognized boolean string",
        ),
    )


def _transport_parameter_issue(
    path: list[str | int],
    severity: IssueSeverity,
    detail: str,
) -> ComplianceIssue:
    """Report malformed input to the existing requirement parameter."""
    return ComplianceIssue(
        pass_id="transportability_required",
        path=path,
        message=f"Transport requirement input is invalid: {detail}.",
        severity=severity,
        code="TRANSPORT_REQUIREMENT_INPUT_INVALID",
        suggestion="Supply a boolean transport_required value or remove the parameter.",
    )


__all__ = ["TransportabilityRequiredPass"]
