"""Offline causal/statistical validity benchmark reports for Foundry methods."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec

SCHEMA_VERSION = "policyos.foundry.causal_statistical_validity.v1"
REPORT_KIND = "foundry.causal_statistical_validity_report"
REPORT_REF_KEY = "causal_statistical_validity_report_ref"

_PASS_STATUSES = {"pass", "passed", "ok", "success"}
_DEGRADED_STATUSES = {"degraded", "degrade", "failed", "fail", "blocked"}
_PLACEBO_SCENARIOS = {"placebo", "placebo_test"}
_NEGATIVE_CONTROL_SCENARIOS = {"negative_control", "negative-control"}
_KNOWN_EFFECT_SCENARIOS = {
    "known_answer",
    "missingness_stress",
    "uncertainty_calibration",
}
_CONFIDENT_RECOMMENDATION_FLOOR = 0.8

_METHOD_FAMILY_CONTRACTS: dict[str, dict[str, Any]] = {
    "difference_in_differences": {
        "method_family": "difference_in_differences",
        "display_name": "Difference-in-differences",
        "expected_assumptions": [
            "parallel_trends",
            "stable_composition",
            "no_anticipation",
        ],
        "input_shape": {
            "panel": True,
            "required_columns": ["unit_id", "period", "treated", "post", "outcome"],
            "minimum_pre_periods": 2,
            "minimum_post_periods": 1,
            "minimum_groups": {"treated": 1, "control": 1},
        },
        "estimand": "ATT",
        "uncertainty_type": "cluster_bootstrap_ci",
        "minimum_sample_diagnostics": {
            "sample_size": 240,
            "effective_sample_size": 180,
            "power": 0.8,
        },
        "failure_modes": [
            "parallel_trends_failure",
            "insufficient_pre_periods",
            "composition_shift",
            "placebo_effect_detected",
            "underpowered_effect_estimate",
        ],
    },
    "synthetic_control": {
        "method_family": "synthetic_control",
        "display_name": "Synthetic control",
        "expected_assumptions": [
            "convex_hull_overlap",
            "pre_treatment_fit",
            "no_interference",
        ],
        "input_shape": {
            "panel": True,
            "required_columns": ["unit_id", "period", "treated_unit", "outcome"],
            "minimum_donor_units": 20,
            "minimum_pre_periods": 4,
        },
        "estimand": "ATT",
        "uncertainty_type": "placebo_permutation_interval",
        "minimum_sample_diagnostics": {
            "sample_size": 180,
            "effective_sample_size": 140,
            "power": 0.8,
        },
        "failure_modes": [
            "poor_pre_treatment_fit",
            "donor_pool_leverage",
            "negative_control_effect_detected",
            "leave_one_donor_instability",
            "underpowered_effect_estimate",
        ],
    },
    "regression_discontinuity": {
        "method_family": "regression_discontinuity",
        "display_name": "Regression discontinuity",
        "expected_assumptions": [
            "continuity_at_cutoff",
            "no_sorting_at_cutoff",
            "bandwidth_robustness",
        ],
        "input_shape": {
            "cross_section": True,
            "required_columns": [
                "running_variable",
                "cutoff",
                "treatment",
                "outcome",
            ],
            "minimum_bandwidth_rows": 120,
        },
        "estimand": "LATE",
        "uncertainty_type": "robust_bias_corrected_ci",
        "minimum_sample_diagnostics": {
            "sample_size": 220,
            "effective_sample_size": 120,
            "power": 0.8,
        },
        "failure_modes": [
            "sorting_at_cutoff",
            "bandwidth_instability",
            "covariate_discontinuity",
            "manipulated_running_variable",
            "underpowered_effect_estimate",
        ],
    },
}


class _ArtifactJsonStore(Protocol):
    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        *,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef: ...


def _text(value: object) -> str:
    return str(value or "").strip()


def _mapping(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


def _to_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status(value: object) -> str:
    return _text(value).casefold()


def _mapping_status(mapping: dict[str, Any]) -> str:
    return _status(mapping.get("status") or mapping.get("quality_status"))


def _status_pass(mapping: dict[str, Any]) -> bool:
    return _mapping_status(mapping) in _PASS_STATUSES


def _status_degraded(value: object) -> bool:
    return _status(value) in _DEGRADED_STATUSES


def _interval_contains_zero(value: object) -> bool:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return False
    low = _to_float(value[0])
    high = _to_float(value[1])
    if low is None or high is None:
        return False
    return min(low, high) <= 0 <= max(low, high)


def _issue(
    *,
    code: str,
    message: str,
    case_id: str | None = None,
    method_family: str | None = None,
    scenario: str | None = None,
    severity: str = "fail",
    failure_mode: str | None = None,
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "foundry_methods",
        "phase": "causal_statistical_validity",
        "case_id": case_id,
        "method_family": method_family,
        "scenario": scenario,
        "failure_mode": failure_mode or code,
        "quality_blocking": severity == "fail",
        "message": message,
        "next_action": next_action,
        **extra,
    }


def _status_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _case_id(case: dict[str, Any], index: int) -> str:
    return _text(case.get("case_id") or case.get("id") or f"case_{index + 1}")


def _method_family(case: dict[str, Any]) -> str:
    return _text(case.get("method_family") or case.get("family")).casefold()


def _scenario(case: dict[str, Any]) -> str:
    return _text(case.get("scenario") or case.get("test_kind")).casefold()


def _known_answer_diagnostic(case: dict[str, Any]) -> dict[str, Any]:
    expected = _to_float(case.get("expected_effect"))
    observed = _to_float(
        case.get("observed_effect")
        if "observed_effect" in case
        else case.get("effect_estimate")
    )
    tolerance = _to_float(case.get("tolerance"))
    delta = (
        abs(observed - expected)
        if observed is not None and expected is not None
        else None
    )
    return {
        "expected_effect": expected,
        "observed_effect": observed,
        "tolerance": tolerance,
        "absolute_error": delta,
        "within_tolerance": (
            delta is not None and tolerance is not None and delta <= tolerance
        ),
    }


def _validate_known_answer(
    case: dict[str, Any],
    *,
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    diagnostic = _known_answer_diagnostic(case)
    if diagnostic["within_tolerance"]:
        return diagnostic, []
    return diagnostic, [
        _issue(
            code="known_answer_outside_tolerance",
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
            failure_mode="known_answer_recovery_failure",
            message=(
                f"Benchmark case {case_id} recovered effect "
                f"{diagnostic['observed_effect']} outside tolerance "
                f"{diagnostic['tolerance']} for expected effect "
                f"{diagnostic['expected_effect']}."
            ),
            next_action=(
                "Inspect the method implementation against the synthetic known-answer "
                "fixture before enabling or recommending this method family."
            ),
            expected_effect=diagnostic["expected_effect"],
            observed_effect=diagnostic["observed_effect"],
            tolerance=diagnostic["tolerance"],
        )
    ]


def _validate_placebo_or_negative_control(
    case: dict[str, Any],
    *,
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    diagnostic = _known_answer_diagnostic(case)
    confidence = _to_float(case.get("recommendation_confidence")) or 0.0
    uncertainty = _mapping(case.get("uncertainty"))
    interval_contains_zero = _interval_contains_zero(uncertainty.get("interval"))
    degraded = _status_degraded(case.get("degradation_status") or case.get("status"))
    near_zero = bool(diagnostic["within_tolerance"])
    guarded = degraded or (near_zero and interval_contains_zero)
    confident = confidence >= _CONFIDENT_RECOMMENDATION_FLOOR
    result = {
        **diagnostic,
        "confidence": confidence,
        "interval_contains_zero": interval_contains_zero,
        "degraded": degraded,
        "guardrail_outcome": "degraded" if degraded else "failed_as_expected",
    }
    if guarded and not confident:
        return result, []

    code = (
        "negative_control_confident_effect"
        if scenario in _NEGATIVE_CONTROL_SCENARIOS
        else "placebo_confident_effect"
    )
    label = "negative-control" if scenario in _NEGATIVE_CONTROL_SCENARIOS else "placebo"
    return result, [
        _issue(
            code=code,
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
            failure_mode=f"{label}_guardrail_failure",
            message=(
                f"Benchmark case {case_id} produced a confident non-zero "
                f"{label} effect instead of failing or degrading."
            ),
            next_action=(
                "Treat the method output as invalid for policy recommendations until "
                "the placebo or negative-control guardrail degrades confidence."
            ),
            observed_effect=diagnostic["observed_effect"],
            tolerance=diagnostic["tolerance"],
            recommendation_confidence=confidence,
            interval_contains_zero=interval_contains_zero,
        )
    ]


def _validate_assumptions(
    case: dict[str, Any],
    *,
    contract: dict[str, Any],
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks = _mapping(case.get("assumption_checks"))
    missing_or_failed: list[str] = []
    for assumption in contract.get("expected_assumptions") or []:
        if _status(checks.get(assumption)) not in _PASS_STATUSES:
            missing_or_failed.append(str(assumption))
    if not missing_or_failed:
        return checks, []
    return checks, [
        _issue(
            code="assumption_check_failure",
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
            failure_mode="method_assumption_failure",
            message=(
                f"Benchmark case {case_id} is missing passing assumption checks: "
                f"{', '.join(missing_or_failed)}."
            ),
            next_action=(
                "Run and persist the declared assumption checks before relying on "
                "this method family."
            ),
            missing_or_failed_assumptions=missing_or_failed,
        )
    ]


def _validate_uncertainty(
    case: dict[str, Any],
    *,
    contract: dict[str, Any],
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    uncertainty = _mapping(case.get("uncertainty"))
    issues: list[dict[str, Any]] = []
    expected_type = _text(contract.get("uncertainty_type"))
    actual_type = _text(uncertainty.get("type") or uncertainty.get("uncertainty_type"))
    if not uncertainty or not actual_type:
        issues.append(
            _issue(
                code="uncertainty_missing",
                case_id=case_id,
                method_family=method_family,
                scenario=scenario,
                failure_mode="uncertainty_missing",
                message=f"Benchmark case {case_id} has no uncertainty envelope.",
                next_action="Attach the declared uncertainty interval for the benchmark.",
            )
        )
    elif expected_type and actual_type != expected_type:
        issues.append(
            _issue(
                code="uncertainty_type_mismatch",
                case_id=case_id,
                method_family=method_family,
                scenario=scenario,
                failure_mode="uncertainty_contract_mismatch",
                message=(
                    f"Benchmark case {case_id} used uncertainty type {actual_type}, "
                    f"expected {expected_type}."
                ),
                next_action=(
                    "Regenerate the benchmark using the uncertainty type declared "
                    "for this method family."
                ),
                expected_uncertainty_type=expected_type,
                observed_uncertainty_type=actual_type,
            )
        )
    if not _interval_contains_zero(uncertainty.get("interval")) and scenario in (
        _PLACEBO_SCENARIOS | _NEGATIVE_CONTROL_SCENARIOS
    ):
        # The placebo/negative-control validator emits the blocking issue; this
        # diagnostic keeps the normalized case explicit without double-counting.
        uncertainty["zero_excluded"] = True
    return uncertainty, issues


def _validate_sample_diagnostics(
    case: dict[str, Any],
    *,
    contract: dict[str, Any],
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    diagnostics = _mapping(case.get("sample_diagnostics"))
    minimums = _mapping(contract.get("minimum_sample_diagnostics"))
    issues: list[dict[str, Any]] = []
    sample_size = _to_float(diagnostics.get("sample_size"))
    minimum_sample_size = _to_float(
        diagnostics.get("min_required_sample_size") or minimums.get("sample_size")
    )
    if sample_size is None or minimum_sample_size is None or sample_size < minimum_sample_size:
        issues.append(
            _issue(
                code="sample_adequacy_failure",
                case_id=case_id,
                method_family=method_family,
                scenario=scenario,
                failure_mode="sample_adequacy_failure",
                message=(
                    f"Benchmark case {case_id} has sample_size={sample_size} below "
                    f"minimum={minimum_sample_size}."
                ),
                next_action=(
                    "Do not rely on this benchmarked method output until the "
                    "effective sample meets the declared adequacy floor."
                ),
                sample_size=sample_size,
                minimum_sample_size=minimum_sample_size,
            )
        )

    power = _to_float(diagnostics.get("power"))
    minimum_power = _to_float(diagnostics.get("min_power") or minimums.get("power"))
    if power is None or minimum_power is None or power < minimum_power:
        issues.append(
            _issue(
                code="power_failure",
                case_id=case_id,
                method_family=method_family,
                scenario=scenario,
                failure_mode="power_failure",
                message=(
                    f"Benchmark case {case_id} has power={power} below "
                    f"minimum={minimum_power}."
                ),
                next_action=(
                    "Treat causal or numerical claims from this method as blocking "
                    "quality failures until power/sample adequacy is restored."
                ),
                power=power,
                minimum_power=minimum_power,
            )
        )
    return diagnostics, issues


def _validate_sensitivity(
    case: dict[str, Any],
    *,
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sensitivity = _mapping(case.get("sensitivity"))
    if _status_pass(sensitivity):
        return sensitivity, []
    return sensitivity, [
        _issue(
            code="sensitivity_failure",
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
            failure_mode="sensitivity_failure",
            message=f"Benchmark case {case_id} failed sensitivity diagnostics.",
            next_action=(
                "Block major causal or numerical claims until sensitivity diagnostics "
                "pass or the method output is explicitly degraded."
            ),
            sensitivity_status=_mapping_status(sensitivity),
        )
    ]


def _validate_missingness(
    case: dict[str, Any],
    *,
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    missingness = _mapping(case.get("missingness"))
    missing_rate = _to_float(missingness.get("missing_rate"))
    max_missing_rate = _to_float(missingness.get("max_missing_rate"))
    passes_status = _status_pass(missingness)
    passes_rate = (
        missing_rate is not None
        and max_missing_rate is not None
        and missing_rate <= max_missing_rate
    )
    if passes_status and passes_rate:
        return missingness, []
    return missingness, [
        _issue(
            code="missingness_stress_failure",
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
            failure_mode="missingness_stress_failure",
            message=f"Benchmark case {case_id} failed missingness stress diagnostics.",
            next_action=(
                "Rerun the benchmark with missingness repair, or block policy claims "
                "that depend on the stressed output."
            ),
            missing_rate=missing_rate,
            max_missing_rate=max_missing_rate,
            missingness_status=_mapping_status(missingness),
        )
    ]


def _validate_uncertainty_calibration(
    case: dict[str, Any],
    *,
    case_id: str,
    method_family: str,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    calibration = _mapping(case.get("uncertainty_calibration"))
    coverage = _to_float(calibration.get("coverage"))
    target = _to_float(calibration.get("target_coverage"))
    tolerance = _to_float(calibration.get("tolerance"))
    close_enough = (
        coverage is not None
        and target is not None
        and tolerance is not None
        and abs(coverage - target) <= tolerance
    )
    if _status_pass(calibration) and close_enough:
        return calibration, []
    return calibration, [
        _issue(
            code="uncertainty_calibration_failure",
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
            failure_mode="uncertainty_calibration_failure",
            message=f"Benchmark case {case_id} failed uncertainty calibration.",
            next_action=(
                "Do not publish calibrated uncertainty claims until empirical "
                "coverage is within the declared tolerance."
            ),
            coverage=coverage,
            target_coverage=target,
            tolerance=tolerance,
            calibration_status=_mapping_status(calibration),
        )
    ]


def _normalize_case(
    case: dict[str, Any],
    *,
    index: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    case_id = _case_id(case, index)
    method_family = _method_family(case)
    scenario = _scenario(case)
    contract = _METHOD_FAMILY_CONTRACTS.get(method_family)
    issues: list[dict[str, Any]] = []
    if contract is None:
        issues.append(
            _issue(
                code="method_family_unsupported",
                case_id=case_id,
                method_family=method_family,
                scenario=scenario,
                failure_mode="method_family_contract_missing",
                message=(
                    f"Benchmark case {case_id} references unsupported method family "
                    f"{method_family!r}."
                ),
                next_action=(
                    "Add a causal/statistical validity contract before accepting this "
                    "benchmark family."
                ),
            )
        )
        contract = {}

    if scenario in _KNOWN_EFFECT_SCENARIOS:
        known_answer, case_issues = _validate_known_answer(
            case,
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
        )
    else:
        known_answer = _known_answer_diagnostic(case)
        case_issues = []
    issues.extend(case_issues)

    placebo_negative_control: dict[str, Any] | None = None
    if scenario in (_PLACEBO_SCENARIOS | _NEGATIVE_CONTROL_SCENARIOS):
        placebo_negative_control, case_issues = _validate_placebo_or_negative_control(
            case,
            case_id=case_id,
            method_family=method_family,
            scenario=scenario,
        )
        issues.extend(case_issues)

    assumption_checks, case_issues = _validate_assumptions(
        case,
        contract=contract,
        case_id=case_id,
        method_family=method_family,
        scenario=scenario,
    )
    issues.extend(case_issues)
    uncertainty, case_issues = _validate_uncertainty(
        case,
        contract=contract,
        case_id=case_id,
        method_family=method_family,
        scenario=scenario,
    )
    issues.extend(case_issues)
    sample_diagnostics, case_issues = _validate_sample_diagnostics(
        case,
        contract=contract,
        case_id=case_id,
        method_family=method_family,
        scenario=scenario,
    )
    issues.extend(case_issues)
    sensitivity, case_issues = _validate_sensitivity(
        case,
        case_id=case_id,
        method_family=method_family,
        scenario=scenario,
    )
    issues.extend(case_issues)
    missingness, case_issues = _validate_missingness(
        case,
        case_id=case_id,
        method_family=method_family,
        scenario=scenario,
    )
    issues.extend(case_issues)
    uncertainty_calibration, case_issues = _validate_uncertainty_calibration(
        case,
        case_id=case_id,
        method_family=method_family,
        scenario=scenario,
    )
    issues.extend(case_issues)

    normalized: dict[str, Any] = {
        "case_id": case_id,
        "method_family": method_family,
        "scenario": scenario,
        "estimand": _text(case.get("estimand") or contract.get("estimand")),
        "fixture_seed": case.get("fixture_seed"),
        "input_shape": _mapping(case.get("input_shape")),
        "method_contract": dict(contract),
        "known_answer": known_answer,
        "assumption_checks": assumption_checks,
        "uncertainty": uncertainty,
        "sample_diagnostics": sample_diagnostics,
        "sensitivity": sensitivity,
        "missingness": missingness,
        "uncertainty_calibration": uncertainty_calibration,
        "status": _status_from_issues(issues),
    }
    if placebo_negative_control is not None:
        normalized["placebo_negative_control"] = placebo_negative_control
    return normalized, issues


def build_causal_statistical_validity_report(
    *,
    benchmark_cases: list[dict[str, Any]],
    benchmark_suite_id: str = "foundry-causal-statistical-validity-offline-v1",
) -> dict[str, Any]:
    """Build an offline deterministic validity benchmark report."""
    normalized_cases: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    if not benchmark_cases:
        issues.append(
            _issue(
                code="no_benchmark_cases",
                message="Causal/statistical validity report has no benchmark cases.",
                next_action="Provide deterministic known-answer benchmark fixtures.",
            )
        )
    for index, case in enumerate(benchmark_cases):
        if not isinstance(case, dict):
            continue
        normalized_case, case_issues = _normalize_case(case, index=index)
        normalized_cases.append(normalized_case)
        issues.extend(case_issues)

    status = _status_from_issues(issues)
    scenarios = sorted(
        {
            _text(case.get("scenario"))
            for case in normalized_cases
            if _text(case.get("scenario"))
        }
    )
    families = sorted(
        {
            _text(case.get("method_family"))
            for case in normalized_cases
            if _text(case.get("method_family"))
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "ref_key": REPORT_REF_KEY,
        "benchmark_suite_id": benchmark_suite_id,
        "deterministic": True,
        "method_defaults_changed": False,
        "method_families": {
            family: dict(contract)
            for family, contract in sorted(_METHOD_FAMILY_CONTRACTS.items())
        },
        "cases": normalized_cases,
        "issues": issues,
        "blocking_issue_count": sum(
            1 for issue in issues if issue.get("severity") == "fail"
        ),
        "summary": {
            "case_count": len(normalized_cases),
            "method_family_count": len(families),
            "method_families": families,
            "scenarios": scenarios,
            "known_answer_count": sum(
                1 for case in normalized_cases if case.get("scenario") == "known_answer"
            ),
            "placebo_or_negative_control_count": sum(
                1
                for case in normalized_cases
                if case.get("scenario") in (_PLACEBO_SCENARIOS | _NEGATIVE_CONTROL_SCENARIOS)
            ),
        },
    }


def normalize_causal_statistical_validity_report(report: dict[str, Any]) -> dict[str, Any]:
    """Recompute status from benchmark cases in an existing report payload."""
    if not isinstance(report, dict):
        report = {}
    raw_cases = report.get("cases") or report.get("benchmark_cases") or []
    cases = [case for case in raw_cases if isinstance(case, dict)] if isinstance(
        raw_cases,
        list,
    ) else []
    normalized = build_causal_statistical_validity_report(
        benchmark_cases=cases,
        benchmark_suite_id=_text(report.get("benchmark_suite_id"))
        or "foundry-causal-statistical-validity-offline-v1",
    )
    return {**report, **normalized}


def persist_causal_statistical_validity_report(
    store: _ArtifactJsonStore,
    report: dict[str, Any],
) -> ArtifactRef:
    """Persist a causal/statistical validity report as a CAS artifact."""
    return store.put_json(
        _jsonable(report),
        ArtifactWriteOptions(
            kind=REPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.CausalStatisticalValidityReport",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = [
    "REPORT_KIND",
    "REPORT_REF_KEY",
    "SCHEMA_VERSION",
    "build_causal_statistical_validity_report",
    "normalize_causal_statistical_validity_report",
    "persist_causal_statistical_validity_report",
]
