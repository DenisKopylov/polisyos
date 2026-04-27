"""Phase-5 fail-closed validation preflight for analyst-facing artifacts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Literal

from pydantic import BaseModel

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.governance.validation import (
    Phase5GateComponent,
    ValidationReport,
    persist_validation_report,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_FAIRNESS_AUDIT_REPORT_REF,
    ARTIFACT_DRIFT_READINESS_REF,
    ARTIFACT_EXPLANATION_BUNDLE_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SHIFT_DIAGNOSTIC_REPORT_REF,
)

_BLOCKING_STATUSES = {"fail", "blocked", "not_run"}
_READINESS_ORDER: dict[str, int] = {
    "ready": 0,
    "monitor": 1,
    "restricted": 2,
    "blocked": 3,
}
_JUDGES = {
    "structural",
    "statistical",
    "robustness",
    "governance",
    "reproducibility",
    "compute",
}
_PHASE5_REF_KEYS = {
    ARTIFACT_FAIRNESS_AUDIT_REPORT_REF,
    ARTIFACT_SHIFT_DIAGNOSTIC_REPORT_REF,
    ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
    ARTIFACT_EXPLANATION_BUNDLE_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_DRIFT_READINESS_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    "advisor_consensus_ref",
    "cross_method_consensus_ref",
    "method_advisor_result_ref",
    "prediction_result_ref",
    "prediction_interval_result_ref",
    "prediction_set_result_ref",
    "posterior_result_ref",
}
_PHASE5_REF_HINTS = (
    "advisor",
    "consensus",
    "coverage",
    "drift",
    "explanation",
    "fairness",
    "judge",
    "multimodality",
    "posterior",
    "prediction",
    "prior",
    "readiness",
    "recommendation",
    "sensitivity",
    "shift",
)


@dataclass(frozen=True)
class Phase5ArtifactPreflightInput:
    """Inputs for one analyst-facing artifact publication preflight."""

    artifact_ref: ArtifactRef | str | None = None
    artifact_kind: str | None = None
    artifact_payload: Any | None = None
    generated_for: str | None = None
    analyst_facing: bool = True
    advisor_result: Any | None = None
    base_readiness: Literal["ready", "monitor", "restricted", "blocked"] = "ready"


@dataclass(frozen=True)
class Phase5PublicationResult:
    """Persisted Phase-5 verdict for an artifact publication attempt."""

    validation_report: ValidationReport
    validation_ref: Any
    judge_verdict: Any | None = None
    judge_verdict_ref: ArtifactRef | None = None
    publishable: bool = False
    readiness: str = "blocked"
    blocked_reason: str | None = None


@dataclass(frozen=True)
class Phase5EvidenceBundle:
    """Normalized evidence payloads and ref-resolution diagnostics."""

    payload: dict[str, Any]
    loaded_refs: tuple[str, ...] = ()
    failed_refs: tuple[str, ...] = ()


class Phase5ValidationBlocked(RuntimeError):
    """Raised when an analyst-facing artifact fails the Phase-5 preflight."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(report.error_summary)


def build_phase5_validation_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    artifact_ref: ArtifactRef | str | None = None,
    artifact_payload: Any | None = None,
    artifact_kind: str | None = None,
    advisor_result: Any | None = None,
    base_readiness: Literal["ready", "monitor", "restricted", "blocked"] = "ready",
    generated_for: str | None = None,
    analyst_facing: bool = False,
) -> ValidationReport:
    """Build the additive ValidationReport v2 evidence bundle for Phase 5."""

    evidence = collect_phase5_evidence(
        ctx,
        state,
        artifact_ref=artifact_ref,
        artifact_payload=artifact_payload,
        artifact_kind=artifact_kind,
    )
    payload = evidence.payload
    all_mappings = list(_walk_mappings(payload))
    components = [
        _evidence_resolution_component(evidence),
        _prior_sensitivity_component(all_mappings),
        _multimodality_component(all_mappings),
        _conditional_coverage_component(all_mappings),
        _shift_component(payload, all_mappings),
        _explanation_component(all_mappings),
        _fairness_component(state, payload, all_mappings),
        _sensitivity_component(all_mappings),
        _drift_component(all_mappings),
        _advisor_component(state, payload, advisor_result),
        _six_judges_component(state, payload, all_mappings, analyst_facing=analyst_facing),
    ]

    readiness = _resolve_readiness(base_readiness, components)
    gate_failures = _gate_failures(components)
    verdict = _resolve_verdict(components, readiness)
    artifact_ref_text = _artifact_ref_to_text(artifact_ref)
    evidence_refs = sorted(
        {
            ref
            for component in components
            for ref in component.evidence_refs
            if ref
        }
    )
    judge_verdict_ref = _first_present_string(
        payload.get("judge_verdict_ref"),
        state.artifacts_index.get(ARTIFACT_JUDGE_VERDICT_REF),
        state.reports_index.get(ARTIFACT_JUDGE_VERDICT_REF),
    )
    advisor_consensus = _advisor_consensus_payload(payload, advisor_result)

    return ValidationReport(
        error_summary=_summary(verdict, readiness, gate_failures),
        issues=[],
        verdict=verdict,
        readiness=readiness,
        artifact_ref=artifact_ref_text,
        artifact_kind=artifact_kind,
        phase5_components=components,
        gate_failures=gate_failures,
        evidence_refs=evidence_refs,
        judge_verdict_ref=judge_verdict_ref,
        advisor_consensus=advisor_consensus,
        fairness_audit=_first_fairness_audit_payload(all_mappings),
        normalized_payload={
            "phase5": {
                "component_count": len(components),
                "loaded_evidence_refs": list(evidence.loaded_refs),
                "failed_evidence_refs": list(evidence.failed_refs),
                "blocking_component_names": [
                    component.name
                    for component in components
                    if component.required and component.status in _BLOCKING_STATUSES
                ],
            }
        },
        generated_for=generated_for,
    )


def collect_phase5_evidence(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    artifact_ref: ArtifactRef | str | None = None,
    artifact_payload: Any | None = None,
    artifact_kind: str | None = None,
) -> Phase5EvidenceBundle:
    """Load Phase-5 evidence refs and project them into one validation payload."""

    payload = _as_mapping(artifact_payload)
    evidence_records: list[dict[str, Any]] = []
    loaded_refs: list[str] = []
    failed_refs: list[str] = []
    candidates: dict[str, str] = {}

    _add_ref_candidate(candidates, "target_artifact", artifact_ref)
    for key, ref in getattr(state, "artifacts_index", {}).items():
        if _is_phase5_ref_key(key):
            _add_ref_candidate(candidates, key, ref)
    for key, ref in getattr(state, "reports_index", {}).items():
        if _is_phase5_ref_key(key):
            _add_ref_candidate(candidates, key, ref)
    for key, value in payload.items():
        if _is_phase5_ref_key(key):
            _add_ref_candidate(candidates, key, value)
    for key, value in state.params.items():
        if key in {
            "judge_verdict",
            "phase5_judge_verdict",
            "method_advisor",
            "method_advisor_result",
            "advisor_result",
            "cross_method_consensus",
            "advisor_consensus",
            "ddm_readiness",
            "drift_readiness",
        }:
            evidence_records.append(
                {
                    "kind": f"phase5.state_param.{key}",
                    "payload": _as_mapping(value) or value,
                }
            )

    for role, ref_text in _collect_phase5_ref_candidates(payload):
        candidates.setdefault(role, ref_text)

    for role, ref_text in sorted(candidates.items()):
        loaded = _load_ref_payload(ctx, ref_text)
        if loaded is None:
            if _ctx_store(ctx) is not None:
                failed_refs.append(ref_text)
            continue
        loaded_refs.append(ref_text)
        evidence_records.append(
            {
                "kind": "phase5.loaded_evidence",
                "role": role,
                "artifact_ref": ref_text,
                "payload": loaded,
            }
        )

    if evidence_records:
        payload = dict(payload)
        payload["_phase5_evidence"] = evidence_records
    return Phase5EvidenceBundle(
        payload=payload,
        loaded_refs=tuple(dict.fromkeys(loaded_refs)),
        failed_refs=tuple(dict.fromkeys(failed_refs)),
    )


def run_phase5_artifact_preflight(
    ctx: ExecutionContext,
    state: ExperimentState,
    preflight_input: Phase5ArtifactPreflightInput,
) -> Phase5PublicationResult:
    """Run and persist the common Phase-5 publication preflight."""

    payload = _as_mapping(preflight_input.artifact_payload)
    judge_verdict = None
    judge_verdict_ref = None
    if preflight_input.analyst_facing:
        judge_verdict, judge_verdict_ref = _phase5_judge_verdict(ctx, state, payload)
        payload = dict(payload)
        payload["judge_verdict"] = _as_mapping(judge_verdict)
        payload["judge_verdict_ref"] = _artifact_ref_to_text(judge_verdict_ref)
        payload["requires_six_judges"] = True

    report = build_phase5_validation_report(
        ctx,
        state,
        artifact_ref=preflight_input.artifact_ref,
        artifact_payload=payload,
        artifact_kind=preflight_input.artifact_kind,
        advisor_result=preflight_input.advisor_result,
        base_readiness=preflight_input.base_readiness,
        generated_for=preflight_input.generated_for or preflight_input.artifact_kind,
        analyst_facing=preflight_input.analyst_facing,
    )
    validation_ref = persist_validation_report(
        ctx.store,
        report,
        inputs=_input_refs_for_publication(preflight_input.artifact_ref, judge_verdict_ref),
    )
    publishable = report.verdict not in {"fail", "blocked"} and report.readiness not in {
        "restricted",
        "blocked",
    }
    return Phase5PublicationResult(
        validation_report=report,
        validation_ref=validation_ref,
        judge_verdict=judge_verdict,
        judge_verdict_ref=judge_verdict_ref,
        publishable=publishable,
        readiness=report.readiness,
        blocked_reason=None if publishable else report.error_summary,
    )


def enforce_phase5_publication(result: Phase5PublicationResult) -> Phase5PublicationResult:
    """Fail closed for a persisted analyst-facing artifact publication result."""

    if not result.publishable:
        raise Phase5ValidationBlocked(result.validation_report)
    return result


def enforce_phase5_validation_report(report: ValidationReport) -> ValidationReport:
    """Fail closed for analyst-facing artifacts whose Phase-5 report is not publishable."""

    if report.verdict in {"fail", "blocked"} or report.readiness in {"restricted", "blocked"}:
        raise Phase5ValidationBlocked(report)
    return report


def _evidence_resolution_component(evidence: Phase5EvidenceBundle) -> Phase5GateComponent:
    if not evidence.failed_refs:
        return _component(
            "evidence_resolution",
            "pass",
            required=True,
            evidence_refs=evidence.loaded_refs,
            summary="Phase-5 evidence refs loaded.",
        )
    return _component(
        "evidence_resolution",
        "blocked",
        required=True,
        evidence_refs=evidence.loaded_refs,
        blockers=[
            "Phase-5 referenced evidence could not be loaded: " + ", ".join(evidence.failed_refs)
        ],
    )


def _prior_sensitivity_component(mappings: Iterable[Mapping[str, Any]]) -> Phase5GateComponent:
    records = [record for record in mappings if "prior_sensitivity" in record]
    if not records:
        return _component(
            "prior_sensitivity",
            "not_applicable",
            required=False,
            summary="No Bayesian posterior prior-sensitivity claim found.",
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for record in records:
        prior = _as_mapping(record.get("prior_sensitivity"))
        evidence_refs.extend(_collect_ref_strings(prior))
        status = _norm_status(prior.get("status") or prior.get("gate_status"))
        if status in {"not_run", "not_requested", "missing"}:
            blockers.append("Prior-sensitivity checks were not run.")
        elif status in {"fail", "failed", "blocked", "refuse"}:
            blockers.append(f"Prior-sensitivity status is {status}.")
        requested = _tier_value(
            prior.get("readiness_tier_requested")
            or prior.get("requested_tier")
            or prior.get("required_tier")
        )
        achieved = _tier_value(
            prior.get("readiness_tier_achieved")
            or prior.get("achieved_tier")
            or prior.get("readiness_tier")
        )
        if requested is not None and achieved is not None and achieved < requested:
            blockers.append("Requested prior-sensitivity tier was not achieved.")
        if status in {"warn", "warning", "partial"}:
            warnings.append("Prior-sensitivity checks completed with warnings.")
    return _component(
        "prior_sensitivity",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _multimodality_component(mappings: Iterable[Mapping[str, Any]]) -> Phase5GateComponent:
    records = [record for record in mappings if "multimodality_status" in record]
    if not records:
        return _component(
            "multimodality",
            "not_applicable",
            required=False,
            summary="No posterior multimodality claim found.",
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for record in records:
        status_payload = _as_mapping(record.get("multimodality_status"))
        evidence_refs.extend(_collect_ref_strings(status_payload))
        status = _norm_status(status_payload.get("status") or status_payload.get("posterior_readiness"))
        mode = _norm_status(status_payload.get("mode") or status_payload.get("classification"))
        downgrade = _as_mapping(status_payload.get("downgrade"))
        readiness = _norm_status(downgrade.get("posterior_readiness"))
        joined = {status, mode, readiness}
        if joined & {
            "refuse_single_policy",
            "not_ready",
            "inconclusive_sampler_geometry",
            "inconclusive_sampling_geometry",
            "inconclusive_low_ess",
            "inconclusive_unvisited_modes_possible",
            "multimodality_detected_policy_relevant",
            "blocked",
            "fail",
        }:
            blockers.append("Posterior geometry does not support a single-policy recommendation.")
        elif any("conditional" in value for value in joined if value):
            warnings.append("Posterior modes require conditional readiness.")
    return _component(
        "multimodality",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _conditional_coverage_component(
    mappings: Iterable[Mapping[str, Any]],
) -> Phase5GateComponent:
    interval_records = [
        record
        for record in mappings
        if _is_prediction_interval_or_set(record) or "conditional_coverage_diagnostic" in record
    ]
    if not interval_records:
        return _component(
            "conditional_coverage",
            "not_applicable",
            required=False,
            summary="No interval or set prediction claim found.",
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for record in interval_records:
        diagnostic = _as_mapping(record.get("conditional_coverage_diagnostic"))
        if not diagnostic:
            blockers.append("Prediction interval/set claim is missing conditional coverage diagnostics.")
            continue
        evidence_refs.extend(_collect_ref_strings(diagnostic))
        status = _norm_status(diagnostic.get("status") or diagnostic.get("gate_status"))
        if status in {"fail", "failed", "unsupported", "blocked", "not_run", "missing"}:
            blockers.append(f"Conditional coverage diagnostic status is {status}.")
        elif status in {"warn", "warning", "pending_outcomes"} or diagnostic.get("pending_outcomes"):
            warnings.append("Conditional coverage diagnostic is pending or degraded.")
    return _component(
        "conditional_coverage",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _shift_component(
    payload: Mapping[str, Any],
    mappings: Iterable[Mapping[str, Any]],
) -> Phase5GateComponent:
    records = list(mappings)
    prediction_claim = any(_is_prediction_result(record) for record in records)
    shift_reports = [
        _as_mapping(record.get("shift_diagnostic_report") or record.get("shift_diagnostic"))
        for record in records
        if "shift_diagnostic_report" in record or "shift_diagnostic" in record
    ]
    if not prediction_claim and not shift_reports:
        return _component(
            "shift",
            "not_applicable",
            required=False,
            summary="No prediction artifact requiring shift diagnostics found.",
        )
    if prediction_claim and not any(shift_reports):
        return _component(
            "shift",
            "blocked",
            blockers=["Prediction artifact is missing a ShiftDiagnosticReport."],
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for report in shift_reports:
        evidence_refs.extend(_collect_ref_strings(report))
        status = _norm_status(report.get("status") or report.get("shift_status"))
        severity = _norm_status(report.get("severity") or report.get("shift_severity"))
        readiness = _norm_status(_path(report, "readiness_impact", "resulting_readiness"))
        if status in {"confirmed", "fail", "blocked"} and severity in {"severe", "critical", "high"}:
            blockers.append("Confirmed severe distribution shift blocks analyst readiness.")
        elif readiness in {"restricted", "blocked"}:
            blockers.append("Shift diagnostic downgraded readiness below analyst exposure.")
        elif severity in {"moderate", "high"} or readiness == "monitor":
            warnings.append("Shift diagnostic downgraded readiness to monitoring.")
    if payload.get("shift_diagnostic_report_ref"):
        evidence_refs.append(str(payload["shift_diagnostic_report_ref"]))
    return _component(
        "shift",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _explanation_component(mappings: Iterable[Mapping[str, Any]]) -> Phase5GateComponent:
    records = [
        record
        for record in mappings
        if record.get("kind") == "scientist.explanation_bundle"
        or "faithfulness_claim" in record
        or "bounded_infidelity" in record
    ]
    if not records:
        return _component(
            "explanation",
            "not_applicable",
            required=False,
            summary="No analyst-facing explanation bundle found.",
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for record in records:
        evidence_refs.extend(_collect_ref_strings(record))
        claim = _norm_status(record.get("faithfulness_claim") or record.get("bounded_infidelity"))
        validation = _as_mapping(record.get("validation") or record.get("berl_validation"))
        validation_status = _norm_status(validation.get("status") or validation.get("gate_status"))
        display_policy = _norm_status(record.get("display_policy") or record.get("explanation_policy"))
        berl_result = _run_berl_validation(record)
        if claim not in {"bounded", "pass", "true", "verified"}:
            blockers.append("Explanation bundle lacks a bounded-infidelity envelope.")
        if berl_result is not None:
            if not bool(berl_result.get("passed")):
                blockers.append(
                    "Explanation BERL validation did not pass: "
                    + ", ".join(berl_result.get("violations") or ["unknown"])
                )
            if berl_result.get("display_policy") == "diagnostic_only":
                blockers.append("Explanation bundle is diagnostic-only, not analyst-display safe.")
            warnings.extend(str(item) for item in berl_result.get("warnings") or [])
        elif validation_status in {"fail", "blocked", "not_run", "missing"}:
            blockers.append("Explanation BERL validation did not pass.")
        if display_policy in {"diagnostic_only", "internal_only", "research_only"}:
            blockers.append("Explanation bundle is diagnostic-only, not analyst-display safe.")
        elif validation_status in {"warn", "warning"}:
            warnings.append("Explanation validation passed with warnings.")
    return _component(
        "explanation",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _fairness_component(
    state: ExperimentState,
    payload: Mapping[str, Any],
    mappings: Iterable[Mapping[str, Any]],
) -> Phase5GateComponent:
    required = bool(
        state.params.get("high_impact")
        or state.params.get("phase5_requires_fairness")
        or state.params.get("protected_attributes")
        or payload.get("requires_fairness_audit")
    )
    audit_records = [
        _as_mapping(record.get("fairness_audit") or record.get("fairness_audit_report") or record)
        for record in mappings
        if "fairness_audit" in record
        or "fairness_audit_report" in record
        or record.get("kind") == "scientist.fairness_audit_report"
    ]
    fairness_ref = state.artifacts_index.get(ARTIFACT_FAIRNESS_AUDIT_REPORT_REF)
    if not audit_records and fairness_ref is None:
        return _component(
            "fairness",
            "blocked" if required else "not_applicable",
            required=required,
            blockers=(["Required fairness audit is missing."] if required else []),
            summary=("No fairness audit required." if not required else None),
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs = [str(fairness_ref.artifact_id)] if fairness_ref is not None else []
    for audit in audit_records:
        evidence_refs.extend(_collect_ref_strings(audit))
        status = _norm_status(audit.get("status") or audit.get("gate_status") or audit.get("decision"))
        power = _norm_status(audit.get("power_status") or audit.get("sample_power"))
        deployable = audit.get("deployable")
        auto_allowed = audit.get("auto_decision_allowed")
        if status in {"refuse", "hard_refuse", "not_computable", "blocked", "fail"}:
            blockers.append(f"Fairness audit status is {status}.")
        if required and deployable is False:
            blockers.append("Required fairness audit is not deployable.")
        if required and auto_allowed is False and payload.get("automated_decision"):
            blockers.append("Fairness audit refuses automated decisioning.")
        if required and power in {"underpowered", "not_computable", "insufficient"}:
            blockers.append("Required high-impact fairness audit is underpowered or not computable.")
        elif status in {"warn", "warning"}:
            warnings.append("Fairness audit passed with warnings.")
    return _component(
        "fairness",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        required=required,
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _sensitivity_component(mappings: Iterable[Mapping[str, Any]]) -> Phase5GateComponent:
    records = [
        record
        for record in mappings
        if record.get("kind") == "scientist.sensitivity_analysis_bundle"
        or "sensitivity_analysis_bundle" in record
        or "sensitivity_indices" in record
        or "sensitivity" in record
    ]
    if not records:
        return _component(
            "sensitivity",
            "not_applicable",
            required=False,
            summary="No sensitivity artifact found.",
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for record in records:
        bundle = _as_mapping(record.get("sensitivity_analysis_bundle") or record.get("sensitivity") or record)
        canonical_bundle = (
            bundle.get("kind") == "scientist.sensitivity_analysis_bundle"
            or record.get("kind") == "scientist.sensitivity_analysis_bundle"
            or "sensitivity_analysis_bundle" in record
        )
        evidence_refs.extend(_collect_ref_strings(bundle))
        indices = bundle.get("indices") or bundle.get("sensitivity_indices") or bundle.get("first_order")
        if not isinstance(indices, list) or not indices:
            message = "Sensitivity artifact has no normalized index list to validate."
            if canonical_bundle:
                blockers.append(message)
            else:
                warnings.append(message)
            continue
        for index in indices:
            index_payload = _as_mapping(index)
            has_ci = bool(index_payload.get("ci") or index_payload.get("confidence_interval"))
            has_se = index_payload.get("standard_error") is not None
            has_blocking_reason = bool(index_payload.get("blocking_reason"))
            if has_blocking_reason:
                blockers.append(
                    f"Sensitivity index {index_payload.get('name') or '<unknown>'} has a blocking reason."
                )
            elif not (has_ci or has_se):
                blockers.append(
                    f"Sensitivity index {index_payload.get('name') or '<unknown>'} lacks uncertainty evidence."
                )
    return _component(
        "sensitivity",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _drift_component(mappings: Iterable[Mapping[str, Any]]) -> Phase5GateComponent:
    records = [
        record
        for record in mappings
        if "readiness_state" in record
        or "ddm_readiness" in record
        or "drift_readiness" in record
    ]
    if not records:
        return _component(
            "drift",
            "not_applicable",
            required=False,
            summary="No drift/readiness monitor found.",
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for record in records:
        evidence_refs.extend(_collect_ref_strings(record))
        readiness = str(
            record.get("readiness_state")
            or record.get("ddm_readiness")
            or record.get("drift_readiness")
            or ""
        ).upper()
        if readiness in {"R1", "R0", "BLOCKED"}:
            blockers.append(f"Drift readiness {readiness} blocks analyst exposure.")
        elif readiness in {"R2", "RESTRICTED"}:
            blockers.append(f"Drift readiness {readiness} restricts analyst exposure.")
        elif readiness in {"R3", "MONITOR"}:
            warnings.append("Drift readiness requires monitoring.")
    return _component(
        "drift",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _advisor_component(
    state: ExperimentState,
    payload: Mapping[str, Any],
    advisor_result: Any | None,
) -> Phase5GateComponent:
    required = bool(
        advisor_result is not None
        or state.params.get("phase5_require_advisor_consensus")
        or payload.get("requires_advisor_consensus")
        or payload.get("method_advisor")
    )
    consensus = _advisor_consensus_payload(payload, advisor_result)
    if not required and consensus is None:
        return _component(
            "advisor",
            "not_applicable",
            required=False,
            summary="No analyst-facing method recommendation found.",
        )
    if consensus is None:
        return _component(
            "advisor",
            "blocked",
            blockers=["Method recommendation is missing cross-method consensus."],
        )
    status = _norm_status(consensus.get("status"))
    allowed = consensus.get("recommendation_allowed")
    if status in {"not_enough_methods", "not_comparable", "not_run", "refuse", "hard_refuse"} or allowed is False:
        return _component(
            "advisor",
            "blocked",
            blockers=[f"Advisor consensus status is {status or '<missing>'}."],
        )
    if status in {"warn", "warning"}:
        return _component(
            "advisor",
            "warn",
            warnings=["Advisor consensus is degraded."],
        )
    return _component("advisor", "pass")


def _six_judges_component(
    state: ExperimentState,
    payload: Mapping[str, Any],
    mappings: Iterable[Mapping[str, Any]],
    *,
    analyst_facing: bool = False,
) -> Phase5GateComponent:
    required = bool(
        analyst_facing
        or state.params.get("phase5_require_judge_verdict")
        or payload.get("requires_six_judges")
        or payload.get("judge_verdict")
        or payload.get("judge_verdict_ref")
    )
    verdicts = [
        _as_mapping(record.get("judge_verdict") or record)
        for record in mappings
        if "judge_verdict" in record or "per_judge" in record
    ]
    if not required and not verdicts:
        return _component(
            "six_judges",
            "not_applicable",
            required=False,
            summary="No six-judge verdict attached.",
        )
    if not verdicts:
        return _component(
            "six_judges",
            "blocked",
            blockers=["Phase 5 requires the six-judge stack verdict."],
        )
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_refs: list[str] = []
    for verdict in verdicts:
        evidence_refs.extend(_collect_ref_strings(verdict))
        per_judge = _as_mapping(verdict.get("per_judge"))
        present = {str(name) for name in per_judge}
        missing = sorted(_JUDGES - present)
        if missing:
            blockers.append("Six-judge verdict missing: " + ", ".join(missing))
        for judge_name, judge_verdict in per_judge.items():
            judge_payload = _as_mapping(judge_verdict)
            if not judge_payload:
                blockers.append(f"Judge {judge_name} verdict is unavailable.")
                continue
            if judge_payload.get("passed") is False and judge_payload.get("is_fatal", True):
                blockers.append(f"Judge {judge_name} failed fatally.")
            status = _norm_status(judge_payload.get("status") or judge_payload.get("availability"))
            if status in {"inactive", "unavailable", "not_run"}:
                blockers.append(f"Judge {judge_name} is {status}.")
            elif status in {"warn", "warning"}:
                warnings.append(f"Judge {judge_name} passed with warnings.")
    return _component(
        "six_judges",
        "blocked" if blockers else ("warn" if warnings else "pass"),
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _component(
    name: str,
    status: str,
    *,
    required: bool = True,
    evidence_refs: Iterable[str] | None = None,
    blockers: Iterable[str] | None = None,
    warnings: Iterable[str] | None = None,
    summary: str | None = None,
) -> Phase5GateComponent:
    return Phase5GateComponent(
        name=name,
        status=status,  # type: ignore[arg-type]
        required=required,
        evidence_refs=sorted(set(evidence_refs or [])),
        blockers=list(blockers or []),
        warnings=list(warnings or []),
        summary=summary,
    )


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return dict(value.model_dump(mode="json", exclude_none=False))
    if is_dataclass(value) and not isinstance(value, type):
        return dict(asdict(value))
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(mode="json", exclude_none=False))
    return {}


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list | tuple):
        for child in value:
            yield from _walk_mappings(child)


def _ctx_store(ctx: ExecutionContext) -> Any | None:
    return getattr(ctx, "store", None)


def _is_phase5_ref_key(key: str) -> bool:
    key_text = str(key)
    return key_text in _PHASE5_REF_KEYS or (
        key_text.endswith("_ref") and any(hint in key_text for hint in _PHASE5_REF_HINTS)
    )


def _add_ref_candidate(candidates: dict[str, str], role: str, value: Any) -> None:
    ref_text = _ref_to_artifact_id(value)
    if ref_text:
        candidates.setdefault(role, ref_text)


def _collect_phase5_ref_candidates(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for record in _walk_mappings(payload):
        for key, value in record.items():
            if not _is_phase5_ref_key(str(key)):
                continue
            if isinstance(value, list | tuple):
                for index, item in enumerate(value):
                    ref_text = _ref_to_artifact_id(item)
                    if ref_text:
                        refs.append((f"{key}.{index}", ref_text))
                continue
            ref_text = _ref_to_artifact_id(value)
            if ref_text:
                refs.append((str(key), ref_text))
    return refs


def _ref_to_artifact_id(value: Any) -> str | None:
    if value is None:
        return None
    artifact_id = getattr(value, "artifact_id", None)
    if artifact_id is not None:
        return str(artifact_id)
    if isinstance(value, Mapping):
        mapped = value.get("artifact_id")
        return str(mapped) if mapped else None
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            ArtifactID.model_validate(candidate)
        except (TypeError, ValueError):
            return None
        return candidate
    return None


def _load_ref_payload(ctx: ExecutionContext, ref_text: str) -> Any | None:
    store = _ctx_store(ctx)
    if store is None:
        return None
    try:
        artifact_id = ArtifactID.model_validate(str(ref_text))
        return from_canonical_bytes(store.get_bytes(artifact_id))
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _phase5_judge_verdict(
    ctx: ExecutionContext,
    state: ExperimentState,
    payload: Mapping[str, Any],
) -> tuple[Any, ArtifactRef | None]:
    existing = _extract_existing_judge_verdict(payload)
    if existing is None:
        existing = _extract_existing_judge_verdict(state.params)
    if existing is not None and _has_all_six_judges(_as_mapping(existing)):
        verdict = existing
    else:
        judge_input = _judge_input_bundle_from_state(state)
        if judge_input is not None:
            from polisyos.scientist.search.judge_stack import JudgeStack

            verdict = JudgeStack(store=_ctx_store(ctx)).evaluate_phase5_preflight(judge_input)
        else:
            verdict = _blocked_judge_verdict("phase5_judge_input_missing")

    store = _ctx_store(ctx)
    if store is None:
        return verdict, None
    from polisyos.scientist.search.judge_stack import persist_judge_verdict

    ref = persist_judge_verdict(store, verdict, inputs=_input_refs_for_publication(None, None))
    model_copy = getattr(verdict, "model_copy", None)
    if callable(model_copy):
        verdict = model_copy(update={"audit_log_ref": ref})
    return verdict, ref


def _judge_input_bundle_from_state(state: ExperimentState) -> Any | None:
    for key in ("phase5_judge_input_bundle", "judge_input_bundle"):
        value = state.params.get(key)
        if value is None:
            continue
        from polisyos.scientist.search.judge_stack import JudgeInputBundle

        if isinstance(value, JudgeInputBundle):
            return value
        try:
            return JudgeInputBundle.model_validate(value)
        except (TypeError, ValueError):
            continue
    return None


def _extract_existing_judge_verdict(payload: Any) -> Any | None:
    from polisyos.scientist.search.judge_stack import JudgeVerdict

    for record in _walk_mappings(payload):
        candidate = record.get("judge_verdict") if "judge_verdict" in record else record
        candidate_mapping = _as_mapping(candidate)
        if "per_judge" not in candidate_mapping:
            continue
        try:
            return JudgeVerdict.model_validate(candidate_mapping)
        except (TypeError, ValueError):
            continue
    return None


def _has_all_six_judges(verdict: Mapping[str, Any]) -> bool:
    per_judge = _as_mapping(verdict.get("per_judge"))
    return _JUDGES.issubset({str(name) for name in per_judge})


def _blocked_judge_verdict(reason: str) -> Any:
    from polisyos.scientist.search.failure_cards import FailureSeverity, TypedFailureCard
    from polisyos.scientist.search.judge_stack import JudgeName, JudgeVerdict, SingleJudgeVerdict

    per_judge = {}
    failures = []
    for judge in JudgeName:
        card = TypedFailureCard(
            judge_name=judge.value,
            failure_type=reason,
            severity=FailureSeverity.BLOCKER,
            description="Phase 5 could not build a judge input bundle for this artifact.",
            remediation_hint="Attach phase5_judge_input_bundle or a persisted six-judge verdict.",
        )
        failures.append(card)
        per_judge[judge.value] = SingleJudgeVerdict(
            judge_name=judge.value,
            passed=False,
            is_fatal=True,
            failure_card=card,
            violations=[reason],
            escalation_level="fatal",
        )
    return JudgeVerdict(
        per_judge=per_judge,
        composite_decision="reject",
        blocking_failures=failures,
    )


def _input_refs_for_publication(
    artifact_ref: ArtifactRef | str | None,
    judge_verdict_ref: ArtifactRef | None,
) -> list[InputRef] | None:
    inputs: list[InputRef] = []
    artifact_id = _ref_to_artifact_id(artifact_ref)
    if artifact_id:
        inputs.append(InputRef(artifact_id=ArtifactID.model_validate(artifact_id), role="artifact"))
    if judge_verdict_ref is not None:
        inputs.append(InputRef(artifact_id=judge_verdict_ref.artifact_id, role="judge_verdict"))
    return inputs or None


def _run_berl_validation(record: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        from polisyos.berl.contracts.explanation_bundle import ExplanationBundle
        from polisyos.berl.contracts.validation_rules import validate_explanation_bundle

        bundle = ExplanationBundle.model_validate(record)
        result = validate_explanation_bundle(bundle)
        return {
            "passed": result.passed,
            "display_policy": result.display_policy,
            "violations": list(result.violations),
            "warnings": list(result.warnings),
        }
    except (ImportError, TypeError, ValueError):
        return None


def _first_fairness_audit_payload(mappings: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    for record in mappings:
        if "fairness_audit" in record:
            return _as_mapping(record.get("fairness_audit"))
        if "fairness_audit_report" in record:
            return _as_mapping(record.get("fairness_audit_report"))
        if record.get("kind") == "scientist.fairness_audit_report":
            return _as_mapping(record)
    return None


def _resolve_readiness(base: str, components: Iterable[Phase5GateComponent]) -> str:
    readiness = base
    for component in components:
        if component.required and component.status in {"blocked", "fail", "not_run"}:
            readiness = _max_readiness(readiness, "blocked")
        elif component.status == "warn":
            readiness = _max_readiness(readiness, "monitor")
    return readiness


def _resolve_verdict(components: Iterable[Phase5GateComponent], readiness: str) -> str:
    component_list = list(components)
    if any(
        component.required and component.status in _BLOCKING_STATUSES
        for component in component_list
    ):
        return "blocked"
    if readiness in {"restricted", "blocked"}:
        return "blocked"
    if any(component.status == "warn" for component in component_list) or readiness == "monitor":
        return "warn"
    return "pass"


def _gate_failures(components: Iterable[Phase5GateComponent]) -> list[str]:
    failures: list[str] = []
    for component in components:
        if not component.required or component.status not in _BLOCKING_STATUSES:
            continue
        failures.extend(component.blockers or [f"{component.name}:{component.status}"])
    return failures


def _summary(verdict: str, readiness: str, failures: list[str]) -> str:
    if failures:
        return (
            f"Phase 5 validation {verdict}; readiness={readiness}; "
            f"{len(failures)} gate failure(s)."
        )
    return f"Phase 5 validation {verdict}; readiness={readiness}."


def _max_readiness(left: str, right: str) -> str:
    return left if _READINESS_ORDER.get(left, 0) >= _READINESS_ORDER.get(right, 0) else right


def _norm_status(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower().replace("-", "_")


def _tier_value(value: Any) -> int | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    text = str(raw).strip().upper()
    text = text.replace("READINESSTIER.", "").replace("TIER_", "T").replace("R_", "R")
    if text.startswith("R") and text[1:].isdigit():
        return int(text[1:])
    if text.startswith("T") and text[1:].isdigit():
        return int(text[1:])
    if text.isdigit():
        return int(text)
    aliases = {"low": 1, "medium": 2, "high": 3, "strict": 4}
    return aliases.get(text.lower())


def _path(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _artifact_ref_to_text(ref: ArtifactRef | str | None) -> str | None:
    if ref is None:
        return None
    if isinstance(ref, str):
        return ref
    return str(ref.artifact_id)


def _first_present_string(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        ref_text = _ref_to_artifact_id(value)
        return ref_text or str(value)
    return None


def _collect_ref_strings(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key, value in payload.items():
        if not key.endswith("_ref") and key not in {"artifact_ref", "evidence_refs"}:
            continue
        if isinstance(value, list | tuple):
            refs.extend(_ref_to_artifact_id(item) or str(item) for item in value if item)
        elif value:
            refs.append(_ref_to_artifact_id(value) or str(value))
    return refs


def _is_prediction_interval_or_set(record: Mapping[str, Any]) -> bool:
    contract_id = str(record.get("contract_id") or record.get("kind") or "")
    return (
        "prediction_interval_result" in contract_id
        or "prediction_set_result" in contract_id
        or {"lower", "upper"}.issubset(record.keys())
        or "prediction_set" in record
    )


def _is_prediction_result(record: Mapping[str, Any]) -> bool:
    contract_id = str(record.get("contract_id") or record.get("kind") or "")
    return (
        "prediction_result" in contract_id
        or "prediction_interval_result" in contract_id
        or "prediction_set_result" in contract_id
    )


def _advisor_consensus_payload(
    payload: Mapping[str, Any],
    advisor_result: Any | None,
) -> dict[str, Any] | None:
    if advisor_result is not None:
        consensus = getattr(advisor_result, "cross_method_consensus", None)
        if consensus is not None:
            return _as_mapping(consensus)
    for key in ("advisor_consensus", "cross_method_consensus"):
        value = payload.get(key)
        if value is not None:
            return _as_mapping(value)
    method_advisor = _as_mapping(payload.get("method_advisor"))
    if method_advisor.get("cross_method_consensus") is not None:
        return _as_mapping(method_advisor.get("cross_method_consensus"))
    return None
