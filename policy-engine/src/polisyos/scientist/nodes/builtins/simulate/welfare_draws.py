"""Internal welfare draws implementation helpers."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Literal, cast

import numpy as np

from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.foundry.uncertainty import PropagationConfig
from polisyos.foundry.uncertainty.evaluation_failures import (
    EXCEPTION_CHAIN_EDGE_LIMIT,
    EXCEPTION_CHAIN_NODE_LIMIT,
    EvaluationFailureClassification,
    classify_evaluation_failure,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    PosteriorSamplesCarrier,
    UncertaintyEnvelope,
)

from .welfare_types import (
    _ERROR_MONTE_CARLO_NOT_CONVERGED,
    _ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN,
    _ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE,
    _WELFARE_MC_MAX_EXECUTION_ATTEMPTS,
    _CalibrationCoordinateSampler,
    _EmpiricalRowSampler,
    _extract_std,
    _fail_error,
    _WelfareNodeFailure,
)


def _classify_welfare_draw_failure(
    exc: BaseException,
    *,
    sample_domain_error_type: type[BaseException] | None = None,
) -> EvaluationFailureClassification:
    """Use the shared bounded classifier while retaining Welfare's domain signal."""
    return classify_evaluation_failure(
        exc,
        sample_domain_error_type=sample_domain_error_type,
        additional_global_error_types=(_WelfareNodeFailure,),
    )


def _welfare_draw_failure_scope(
    exc: Exception,
    *,
    sample_domain_error_type: type[BaseException],
) -> Literal["transient", "sample_domain", "global", "unknown"]:
    """Classify only explicit PolicyOS retry/domain signals and fatal causes."""
    return _classify_welfare_draw_failure(
        exc,
        sample_domain_error_type=sample_domain_error_type,
    ).scope


def _welfare_exception_type_chain(
    classification: EvaluationFailureClassification,
) -> list[str]:
    """Project bounded shared-classifier evidence into Welfare's diagnostic field."""
    names = [type(cause).__name__ for cause in classification.chain]
    if not classification.chain_complete:
        names.append("ExceptionChainTruncated")
    return names


def _raise_welfare_mc_execution_failure(
    exc: Exception,
    *,
    draw_index: int | None,
    sampled_input_sha256: str | None,
    execution_attempts: list[dict[str, Any]],
    attempted_draw_count: int,
    simulation_attempt_count: int,
    retry_attempt_count: int,
    failure_stage: Literal["sample_generation", "sample_evaluation"],
    sample_domain_error_type: type[BaseException],
) -> None:
    """Fail the node when the evaluator cannot establish a safe draw-local outcome."""
    classification = _classify_welfare_draw_failure(
        exc,
        sample_domain_error_type=sample_domain_error_type,
    )
    scope = classification.scope
    if failure_stage == "sample_generation" or scope in {"global", "unknown"}:
        scope = "global" if scope == "global" else "unknown"
        code = (
            _ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE
            if scope == "global"
            else _ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN
        )
        message = (
            "Welfare Monte Carlo evaluation failed outside a declared sampled-input domain"
            if scope == "global"
            else "Welfare Monte Carlo evaluation failure scope is unknown"
        )
        raise _fail_error(
            code,
            message,
            details={
                "failure_scope": scope,
                "failure_stage": failure_stage,
                "draw_index": draw_index,
                "sampled_input_sha256": sampled_input_sha256,
                "execution_attempt_count": len(execution_attempts),
                "execution_attempts": list(execution_attempts),
                "attempted_draw_count": attempted_draw_count,
                "simulation_attempt_count": simulation_attempt_count,
                "retry_attempt_count": retry_attempt_count,
                "max_attempts_per_draw": _WELFARE_MC_MAX_EXECUTION_ATTEMPTS,
                "error_type": type(exc).__name__,
                "error_message": _bounded_welfare_error_message(exc),
                "cause_type_chain": _welfare_exception_type_chain(classification),
                "cause_chain_complete": classification.chain_complete,
                "cause_chain_cycle_detected": classification.cycle_detected,
                "cause_chain_node_limit": EXCEPTION_CHAIN_NODE_LIMIT,
                "cause_chain_edge_limit": EXCEPTION_CHAIN_EDGE_LIMIT,
                "declared_error_category": (
                    exc.category.value
                    if isinstance(exc, PolicyOSError) and isinstance(exc.category, ErrorCategory)
                    else None
                ),
            },
        ) from exc
    raise AssertionError("draw-local failures must be recorded, not raised as node failures")


def _welfare_execution_attempt(
    *,
    draw_index: int,
    attempt_index: int,
    sampled_input_sha256: str,
    outcome_code: str,
    error: Exception | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one bounded execution record for a fixed sampled input."""
    attempt: dict[str, Any] = {
        "draw_index": draw_index,
        "attempt_index": attempt_index,
        "attempt_number": attempt_index + 1,
        "sampled_input_sha256": sampled_input_sha256,
        "outcome_code": outcome_code,
        "error_type": type(error).__name__ if error is not None else None,
    }
    if error is not None:
        attempt["error_message"] = _bounded_welfare_error_message(error)
    if details:
        attempt.update(details)
    return attempt


def _welfare_draw_terminal_outcome(
    *,
    draw_index: int,
    sampled_input_sha256: str,
    outcome_code: str,
    execution_attempts: list[dict[str, Any]],
    attempt_index: int | None = None,
    sample_index: int | None = None,
    error: Exception | None = None,
    details: Mapping[str, Any] | None = None,
    terminal_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one terminal draw row and retain all attempts against its sampled input."""
    if terminal_attempt is None:
        if attempt_index is None:
            raise ValueError("terminal draw outcomes require an attempt index or terminal record")
        terminal_attempt = _welfare_execution_attempt(
            draw_index=draw_index,
            attempt_index=attempt_index,
            sampled_input_sha256=sampled_input_sha256,
            outcome_code=outcome_code,
            error=error,
            details=details,
        )
        execution_attempts.append(terminal_attempt)
    terminal: dict[str, Any] = {
        "draw_index": draw_index,
        "sampled_input_sha256": sampled_input_sha256,
        "sample_index": sample_index,
        "outcome_code": outcome_code,
        "execution_attempt_count": len(execution_attempts),
        "execution_attempts": list(execution_attempts),
        "error_type": terminal_attempt.get("error_type"),
    }
    if "error_message" in terminal_attempt:
        terminal["error_message"] = terminal_attempt["error_message"]
    if details:
        terminal.update(details)
    return terminal


def _welfare_sampled_input_sha256(params: Mapping[str, float]) -> str:
    """Hash the exact normalized inputs passed to one welfare draw evaluator."""
    normalized = {str(name): float(value) for name, value in params.items()}
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_welfare_error_message(exc: Exception) -> str:
    """Retain a bounded diagnostic without storing sampled callback inputs."""
    return " ".join(str(exc).split())[:256]


def _posterior_sample_probabilities(
    payload: PosteriorSamplesCarrier,
) -> tuple[float, ...] | None:
    """Normalize finite non-negative source weights without inventing support."""
    raw = tuple(1.0 for _ in payload.samples) if payload.weights is None else payload.weights
    try:
        total = math.fsum(float(weight) for weight in raw)
    except OverflowError:
        return None
    if not math.isfinite(total) or total <= 0.0:
        return None
    probabilities = tuple(float(weight) / total for weight in raw)
    if not all(math.isfinite(value) and value >= 0.0 for value in probabilities):
        return None
    return probabilities


def _sample_empirical_row(
    rng: np.random.Generator, sampler: _EmpiricalRowSampler
) -> dict[str, float]:
    row_index = int(rng.choice(len(sampler.probabilities), p=sampler.probabilities))
    return {name: float(sampler.samples_by_name[name][row_index]) for name in sampler.param_names}


def _sample_calibration_coordinates(
    rng: np.random.Generator,
    *,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    sampler: _CalibrationCoordinateSampler,
) -> dict[str, float]:
    draw_params: dict[str, float] = {}
    if sampler.extra_fields:
        joint_draw = rng.multivariate_normal(
            mean=np.zeros(len(param_names), dtype=np.float64),
            cov=sampler.joint_covariance,
            check_valid="raise",
            tol=1e-10,
        )
        assert sampler.projection_pseudoinverse is not None
        sampled_calibration_fields = joint_draw[list(sampler.calibration_indices)]
        coordinate_draw = sampler.projection_pseudoinverse @ sampled_calibration_fields
        calibration_delta = sampler.projection_matrix @ coordinate_draw
        extra_delta = joint_draw[list(sampler.extra_indices)]
        for name, delta in zip(sampler.calibration_fields, calibration_delta, strict=True):
            draw_params[name] = float(input_envelopes[name].point_estimate + delta)
        for index, name in enumerate(sampler.extra_fields):
            envelope = input_envelopes[name]
            if envelope.distribution_family == DistributionFamily.NORMAL:
                draw_params[name] = float(envelope.point_estimate + extra_delta[index])
            else:
                standard_deviation = sampler.extra_stds[index]
                standardized = (
                    float(extra_delta[index] / standard_deviation)
                    if standard_deviation > 0.0
                    else 0.0
                )
                draw_params[name] = _quantile_from_envelope(
                    NormalDist().cdf(standardized), envelope
                )
        return draw_params

    coordinate_draw = rng.multivariate_normal(
        mean=np.zeros(len(sampler.coordinate_order), dtype=np.float64),
        cov=sampler.coordinate_covariance,
        check_valid="raise",
        tol=1e-10,
    )
    calibration_delta = sampler.projection_matrix @ coordinate_draw
    for name, delta in zip(sampler.calibration_fields, calibration_delta, strict=True):
        draw_params[name] = float(input_envelopes[name].point_estimate + delta)
    return draw_params


def _sample_dependent_marginals(
    rng: np.random.Generator,
    *,
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    dependence_sampler: Mapping[str, Any],
) -> dict[str, float]:
    covered = [str(name) for name in dependence_sampler.get("covered_params", ())]
    correlation = np.asarray(dependence_sampler.get("correlation_matrix"), dtype=np.float64)
    latent = rng.multivariate_normal(mean=np.zeros(len(covered), dtype=np.float64), cov=correlation)
    values: dict[str, float] = {}
    for name, latent_value in zip(covered, latent, strict=False):
        u = float(NormalDist().cdf(float(latent_value)))
        values[name] = _quantile_from_envelope(u, input_envelopes[name])
    return values


def _sample_param_draw(
    rng: np.random.Generator,
    *,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    dependence_sampler: Mapping[str, Any],
    calibration_coordinate_sampler: _CalibrationCoordinateSampler | None = None,
    empirical_row_sampler: _EmpiricalRowSampler | None = None,
) -> dict[str, float]:
    if empirical_row_sampler is not None:
        return _sample_empirical_row(rng, empirical_row_sampler)
    if calibration_coordinate_sampler is not None:
        return _sample_calibration_coordinates(
            rng,
            param_names=param_names,
            input_envelopes=input_envelopes,
            sampler=calibration_coordinate_sampler,
        )
    draw_params = (
        _sample_dependent_marginals(
            rng,
            input_envelopes=input_envelopes,
            dependence_sampler=dependence_sampler,
        )
        if bool(dependence_sampler.get("applied"))
        else {}
    )
    for name in param_names:
        if name not in draw_params:
            draw_params[name] = _sample_from_envelope(rng, input_envelopes[name])
    return draw_params


def _quantile_from_envelope(u: float, env: UncertaintyEnvelope) -> float:
    bounded_u = min(max(float(u), 1e-9), 1.0 - 1e-9)
    point = float(env.point_estimate)
    lower = float(env.confidence_interval[0])
    upper = float(env.confidence_interval[1])
    if env.distribution_family == DistributionFamily.NORMAL:
        std = max(_extract_std(env), 1e-12)
        z_value = NormalDist().inv_cdf(bounded_u)
        return float(point + std * z_value)
    if env.distribution_family == DistributionFamily.UNIFORM:
        return float(lower + bounded_u * (upper - lower))
    mode = min(max(point, lower), upper)
    if upper <= lower:
        return point
    c = (mode - lower) / (upper - lower) if upper > lower else 0.5
    if bounded_u <= c and c > 0.0:
        return float(lower + math.sqrt(bounded_u * (upper - lower) * (mode - lower)))
    if c >= 1.0:
        return float(mode)
    return float(upper - math.sqrt((1.0 - bounded_u) * (upper - lower) * (upper - mode)))


def _sample_from_envelope(rng: np.random.Generator, env: UncertaintyEnvelope) -> float:
    point = float(env.point_estimate)
    lower, upper = float(env.confidence_interval[0]), float(env.confidence_interval[1])
    if env.distribution_family == DistributionFamily.NORMAL:
        std = _extract_std(env)
        return float(rng.normal(loc=point, scale=max(std, 1e-12)))
    if env.distribution_family == DistributionFamily.UNIFORM:
        return float(rng.uniform(lower, upper))
    if env.distribution_family == DistributionFamily.TRIANGULAR:
        if upper <= lower:
            return point
        mode = min(max(point, lower), upper)
        return float(rng.triangular(lower, mode, upper))
    return float(rng.normal(loc=point, scale=max((upper - lower) / 4.0, 1e-12)))


def _finite_difference_gradient(
    *,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[dict[str, float], float]:
    """Compute the finite-difference gradient over each envelope's declared support."""
    base_output = simulation_fn(**nominal_params)
    base_value = float(base_output["welfare"])
    gradient: dict[str, float] = {}
    for name, env in input_envelopes.items():
        step = _finite_difference_step(env)
        current = float(nominal_params.get(name, env.point_estimate))
        lower = float(env.confidence_interval[0])
        upper = float(env.confidence_interval[1])
        step_up = min(step, max(upper - current, 0.0))
        step_down = min(step, max(current - lower, 0.0))
        if step_up > 0.0 and step_down > 0.0:
            upper_params = dict(nominal_params)
            lower_params = dict(nominal_params)
            upper_params[name] = current + step_up
            lower_params[name] = current - step_down
            upper_value = float(simulation_fn(**upper_params)["welfare"])
            lower_value = float(simulation_fn(**lower_params)["welfare"])
            gradient[name] = float((upper_value - lower_value) / (step_up + step_down))
        elif step_up > 0.0:
            upper_params = dict(nominal_params)
            upper_params[name] = current + step_up
            upper_value = float(simulation_fn(**upper_params)["welfare"])
            gradient[name] = float((upper_value - base_value) / step_up)
        elif step_down > 0.0:
            lower_params = dict(nominal_params)
            lower_params[name] = current - step_down
            lower_value = float(simulation_fn(**lower_params)["welfare"])
            gradient[name] = float((base_value - lower_value) / step_down)
        else:
            gradient[name] = 0.0
    return gradient, base_value


def _finite_difference_step(env: UncertaintyEnvelope) -> float:
    """Choose the existing support-scaled finite-difference step."""
    point = abs(float(env.point_estimate))
    width = max(
        float(env.confidence_interval[1]) - float(env.confidence_interval[0]),
        0.0,
    )
    std = _extract_std(env)
    return max(std * 0.5, width / 20.0, max(point, 1.0) * 1e-4, 1e-6)


@dataclass
class _MonteCarloCounters:
    attempted_draw_count: int = 0
    simulation_attempt_count: int = 0
    retry_attempt_count: int = 0


@dataclass(frozen=True)
class _MonteCarloDrawSet:
    welfare: list[float]
    welfare_pe: list[float]
    welfare_ge: list[float]
    terminal_outcomes: list[dict[str, Any]]
    counters: _MonteCarloCounters
    requested_draw_count: int
    dependence_sampler: dict[str, Any]
    calibration_resolution: Any


@dataclass(frozen=True)
class _DrawAttemptResult:
    terminal_outcome: dict[str, Any] | None
    values: tuple[float, float, float] | None
    retry: bool = False


def _validate_welfare_draw_outputs(
    outputs: Any,
    *,
    draw_index: int,
    sampled_input_sha256: str,
    execution_attempts: list[dict[str, Any]],
    attempt_index: int,
) -> _DrawAttemptResult:
    if not isinstance(outputs, Mapping):
        terminal = _welfare_draw_terminal_outcome(
            draw_index=draw_index,
            sampled_input_sha256=sampled_input_sha256,
            outcome_code="invalid_response",
            execution_attempts=execution_attempts,
            attempt_index=attempt_index,
        )
        return _DrawAttemptResult(terminal, None)
    required = ("welfare", "welfare_pe", "welfare_ge")
    missing = [name for name in required if name not in outputs]
    if missing:
        terminal = _welfare_draw_terminal_outcome(
            draw_index=draw_index,
            sampled_input_sha256=sampled_input_sha256,
            outcome_code="missing_output",
            execution_attempts=execution_attempts,
            attempt_index=attempt_index,
            details={"missing_output_ids": missing},
        )
        return _DrawAttemptResult(terminal, None)
    try:
        values = tuple(float(outputs[name]) for name in required)
    except (TypeError, ValueError, OverflowError) as exc:
        terminal = _welfare_draw_terminal_outcome(
            draw_index=draw_index,
            sampled_input_sha256=sampled_input_sha256,
            outcome_code="non_numeric_output",
            execution_attempts=execution_attempts,
            attempt_index=attempt_index,
            error=exc,
        )
        return _DrawAttemptResult(terminal, None)
    if not all(math.isfinite(value) for value in values):
        terminal = _welfare_draw_terminal_outcome(
            draw_index=draw_index,
            sampled_input_sha256=sampled_input_sha256,
            outcome_code="non_finite_output",
            execution_attempts=execution_attempts,
            attempt_index=attempt_index,
        )
        return _DrawAttemptResult(terminal, None)
    terminal = _welfare_draw_terminal_outcome(
        draw_index=draw_index,
        sampled_input_sha256=sampled_input_sha256,
        outcome_code="success",
        execution_attempts=execution_attempts,
        attempt_index=attempt_index,
    )
    return _DrawAttemptResult(terminal, values)


def _evaluate_welfare_draw_attempt(
    simulation_fn: Any,
    draw_params: Mapping[str, float],
    *,
    draw_index: int,
    sampled_input_sha256: str,
    attempt_index: int,
    execution_attempts: list[dict[str, Any]],
    counters: _MonteCarloCounters,
    sample_domain_error_type: type[BaseException],
) -> _DrawAttemptResult:
    try:
        outputs = simulation_fn(**draw_params)
    except Exception as exc:
        failure_scope = _welfare_draw_failure_scope(
            exc, sample_domain_error_type=sample_domain_error_type
        )
        if failure_scope in {"global", "unknown"}:
            execution_attempts.append(
                _welfare_execution_attempt(
                    draw_index=draw_index,
                    attempt_index=attempt_index,
                    sampled_input_sha256=sampled_input_sha256,
                    outcome_code=f"{failure_scope}_evaluation_failure",
                    error=exc,
                )
            )
            _raise_welfare_mc_execution_failure(
                exc,
                draw_index=draw_index,
                sampled_input_sha256=sampled_input_sha256,
                execution_attempts=execution_attempts,
                attempted_draw_count=counters.attempted_draw_count,
                simulation_attempt_count=counters.simulation_attempt_count,
                retry_attempt_count=counters.retry_attempt_count,
                failure_stage="sample_evaluation",
                sample_domain_error_type=sample_domain_error_type,
            )
        if failure_scope == "transient":
            outcome_code = (
                "transient_retry"
                if attempt_index + 1 < _WELFARE_MC_MAX_EXECUTION_ATTEMPTS
                else "transient_retry_exhausted"
            )
            attempt = _welfare_execution_attempt(
                draw_index=draw_index,
                attempt_index=attempt_index,
                sampled_input_sha256=sampled_input_sha256,
                outcome_code=outcome_code,
                error=exc,
            )
            execution_attempts.append(attempt)
            if outcome_code == "transient_retry":
                return _DrawAttemptResult(None, None, retry=True)
            return _DrawAttemptResult(
                _welfare_draw_terminal_outcome(
                    draw_index=draw_index,
                    sampled_input_sha256=sampled_input_sha256,
                    outcome_code=outcome_code,
                    execution_attempts=execution_attempts,
                    terminal_attempt=attempt,
                ),
                None,
            )
        domain_error = cast("Any", exc)
        details = {
            "domain_predicate_id": domain_error.predicate_id,
            "domain_declaration_grade": "consumer_asserted",
        }
        attempt = _welfare_execution_attempt(
            draw_index=draw_index,
            attempt_index=attempt_index,
            sampled_input_sha256=sampled_input_sha256,
            outcome_code="sample_domain_inapplicable",
            error=exc,
            details=details,
        )
        execution_attempts.append(attempt)
        return _DrawAttemptResult(
            _welfare_draw_terminal_outcome(
                draw_index=draw_index,
                sampled_input_sha256=sampled_input_sha256,
                outcome_code="sample_domain_inapplicable",
                execution_attempts=execution_attempts,
                details=details,
                terminal_attempt=attempt,
            ),
            None,
        )
    return _validate_welfare_draw_outputs(
        outputs,
        draw_index=draw_index,
        sampled_input_sha256=sampled_input_sha256,
        execution_attempts=execution_attempts,
        attempt_index=attempt_index,
    )


def _evaluate_welfare_draw(
    *,
    rng: np.random.Generator,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    dependence_sampler: Mapping[str, Any],
    coordinate_sampler: Any,
    empirical_sampler: Any,
    simulation_fn: Any,
    draw_index: int,
    counters: _MonteCarloCounters,
    sample_domain_error_type: type[BaseException],
    sample_param_draw: Any,
) -> tuple[dict[str, Any], tuple[float, float, float] | None]:
    try:
        draw_params = sample_param_draw(
            rng,
            param_names=param_names,
            input_envelopes=input_envelopes,
            dependence_sampler=dependence_sampler,
            calibration_coordinate_sampler=coordinate_sampler,
            empirical_row_sampler=empirical_sampler,
        )
        sampled_input_sha256 = _welfare_sampled_input_sha256(draw_params)
    except Exception as exc:
        _raise_welfare_mc_execution_failure(
            exc,
            draw_index=draw_index,
            sampled_input_sha256=None,
            execution_attempts=[],
            attempted_draw_count=counters.attempted_draw_count,
            simulation_attempt_count=counters.simulation_attempt_count,
            retry_attempt_count=counters.retry_attempt_count,
            failure_stage="sample_generation",
            sample_domain_error_type=sample_domain_error_type,
        )
    execution_attempts: list[dict[str, Any]] = []
    for attempt_index in range(_WELFARE_MC_MAX_EXECUTION_ATTEMPTS):
        if attempt_index > 0:
            counters.retry_attempt_count += 1
        counters.simulation_attempt_count += 1
        result = _evaluate_welfare_draw_attempt(
            simulation_fn,
            draw_params,
            draw_index=draw_index,
            sampled_input_sha256=sampled_input_sha256,
            attempt_index=attempt_index,
            execution_attempts=execution_attempts,
            counters=counters,
            sample_domain_error_type=sample_domain_error_type,
        )
        if result.retry:
            continue
        if result.terminal_outcome is None:
            raise AssertionError("welfare draw attempt did not reach a terminal outcome")
        return result.terminal_outcome, result.values
    raise AssertionError("welfare Monte Carlo exhausted attempts without a terminal outcome")


def _run_welfare_monte_carlo_draws(
    config: PropagationConfig,
    *,
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    dependence_sampler: dict[str, Any],
    coordinate_sampler: Any,
    empirical_sampler: Any,
    simulation_fn: Any,
    sample_domain_error_type: type[BaseException],
    sample_param_draw: Any,
    calibration_resolution: Any,
) -> _MonteCarloDrawSet:
    requested_draw_count = int(config.mc_n_samples)
    rng = np.random.default_rng(config.mc_seed)
    param_names = sorted(input_envelopes)
    counters = _MonteCarloCounters()
    welfare: list[float] = []
    welfare_pe: list[float] = []
    welfare_ge: list[float] = []
    terminal_outcomes: list[dict[str, Any]] = []
    for draw_index in range(requested_draw_count):
        counters.attempted_draw_count += 1
        terminal, values = _evaluate_welfare_draw(
            rng=rng,
            param_names=param_names,
            input_envelopes=input_envelopes,
            dependence_sampler=dependence_sampler,
            coordinate_sampler=coordinate_sampler,
            empirical_sampler=empirical_sampler,
            simulation_fn=simulation_fn,
            draw_index=draw_index,
            counters=counters,
            sample_domain_error_type=sample_domain_error_type,
            sample_param_draw=sample_param_draw,
        )
        if values is not None:
            welfare.append(values[0])
            welfare_pe.append(values[1])
            welfare_ge.append(values[2])
            terminal["sample_index"] = len(welfare) - 1
        terminal_outcomes.append(terminal)
    return _MonteCarloDrawSet(
        welfare=welfare,
        welfare_pe=welfare_pe,
        welfare_ge=welfare_ge,
        terminal_outcomes=terminal_outcomes,
        counters=counters,
        requested_draw_count=requested_draw_count,
        dependence_sampler=dependence_sampler,
        calibration_resolution=calibration_resolution,
    )


def _validate_monte_carlo_draw_counts(draws: _MonteCarloDrawSet) -> None:
    """Reject draw, attempt, and terminal-row counts outside their denominator."""
    requested = draws.requested_draw_count
    attempted = draws.counters.attempted_draw_count
    simulation_attempts = draws.counters.simulation_attempt_count
    retry_attempts = draws.counters.retry_attempt_count
    if (
        isinstance(requested, bool)
        or not isinstance(requested, int)
        or requested < 1
        or isinstance(attempted, bool)
        or not isinstance(attempted, int)
        or attempted < 0
        or attempted > requested
    ):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo draw counts are outside the requested denominator",
            details={"requested_draw_count": requested, "attempted_draw_count": attempted},
        )
    if (
        isinstance(simulation_attempts, bool)
        or not isinstance(simulation_attempts, int)
        or simulation_attempts < attempted
        or isinstance(retry_attempts, bool)
        or not isinstance(retry_attempts, int)
        or retry_attempts != simulation_attempts - attempted
    ):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo retry counters do not reconcile with execution attempts",
            details={
                "attempted_draw_count": attempted,
                "simulation_attempt_count": simulation_attempts,
                "retry_attempt_count": retry_attempts,
            },
        )

    outcomes = draws.terminal_outcomes
    if len(outcomes) != attempted:
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo terminal outcomes do not cover attempted draws",
            details={"attempted_draw_count": attempted, "terminal_outcome_count": len(outcomes)},
        )


def _validate_monte_carlo_outcome_identity(
    outcome: Any,
    *,
    expected_draw_index: int,
) -> tuple[list[Mapping[str, Any]], str, Any, str]:
    """Validate one terminal outcome and every retry's immutable draw identity."""
    if not isinstance(outcome, Mapping):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo terminal outcome is malformed",
            details={"draw_index": expected_draw_index},
        )
    attempts = outcome.get("execution_attempts")
    draw_index = outcome.get("draw_index")
    outcome_code = outcome.get("outcome_code")
    sample_index = outcome.get("sample_index")
    input_digest = outcome.get("sampled_input_sha256")
    if (
        isinstance(draw_index, bool)
        or not isinstance(draw_index, int)
        or draw_index != expected_draw_index
        or not isinstance(attempts, list)
        or not attempts
        or len(attempts) > _WELFARE_MC_MAX_EXECUTION_ATTEMPTS
        or isinstance(outcome.get("execution_attempt_count"), bool)
        or outcome.get("execution_attempt_count") != len(attempts)
        or not isinstance(outcome_code, str)
        or not outcome_code
        or not isinstance(input_digest, str)
        or not input_digest
        or (
            sample_index is not None
            and (
                isinstance(sample_index, bool)
                or not isinstance(sample_index, int)
                or sample_index < 0
            )
        )
    ):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo outcome identity or attempt count is inconsistent",
            details={"draw_index": expected_draw_index},
        )

    validated_attempts = cast("list[Mapping[str, Any]]", attempts)
    for attempt_number, attempt in enumerate(validated_attempts, start=1):
        if (
            not isinstance(attempt, Mapping)
            or isinstance(attempt.get("draw_index"), bool)
            or not isinstance(attempt.get("draw_index"), int)
            or attempt.get("draw_index") != expected_draw_index
            or isinstance(attempt.get("attempt_number"), bool)
            or not isinstance(attempt.get("attempt_number"), int)
            or attempt.get("attempt_number") != attempt_number
            or attempt.get("sampled_input_sha256") != input_digest
        ):
            raise _fail_error(
                _ERROR_MONTE_CARLO_NOT_CONVERGED,
                "Welfare Monte Carlo attempt identity does not match its sampled draw",
                details={"draw_index": expected_draw_index, "attempt_number": attempt_number},
            )
    if validated_attempts[-1].get("outcome_code") != outcome_code:
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo terminal outcome does not match its last execution attempt",
            details={"draw_index": expected_draw_index},
        )
    return validated_attempts, outcome_code, sample_index, input_digest


def _advance_successful_draw_count(
    outcome_code: str,
    sample_index: Any,
    *,
    successful_draw_count: int,
    draw_index: int,
) -> int:
    """Require sample indexes to enumerate successful terminal outcomes only."""
    if outcome_code == "success":
        if sample_index != successful_draw_count:
            raise _fail_error(
                _ERROR_MONTE_CARLO_NOT_CONVERGED,
                "Welfare Monte Carlo sample indices do not match successful outcome order",
                details={"draw_index": draw_index, "sample_index": sample_index},
            )
        return successful_draw_count + 1
    if sample_index is not None:
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Failed welfare Monte Carlo outcomes cannot identify a successful sample",
            details={"draw_index": draw_index},
        )
    return successful_draw_count


def _validate_monte_carlo_outcomes(draws: _MonteCarloDrawSet) -> tuple[int, int]:
    """Reconcile terminal rows, successful sample order, and recorded attempts."""
    successful = 0
    recorded_attempts = 0
    for draw_index, outcome in enumerate(draws.terminal_outcomes):
        attempts, outcome_code, sample_index, _ = _validate_monte_carlo_outcome_identity(
            outcome,
            expected_draw_index=draw_index,
        )
        successful = _advance_successful_draw_count(
            outcome_code,
            sample_index,
            successful_draw_count=successful,
            draw_index=draw_index,
        )
        recorded_attempts += len(attempts)
    return successful, recorded_attempts


def _validate_monte_carlo_values(
    draws: _MonteCarloDrawSet,
    *,
    successful: int,
    recorded_attempts: int,
) -> None:
    """Reject value arrays or attempt counters that differ from terminal rows."""
    simulation_attempts = draws.counters.simulation_attempt_count

    try:
        values_finite = all(
            math.isfinite(float(value))
            for values in (draws.welfare, draws.welfare_pe, draws.welfare_ge)
            for value in values
        )
    except (TypeError, ValueError, OverflowError):
        values_finite = False
    value_counts = [len(draws.welfare), len(draws.welfare_pe), len(draws.welfare_ge)]
    if (
        recorded_attempts != simulation_attempts
        or any(count != successful for count in value_counts)
        or not values_finite
    ):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo counters or value arrays do not match terminal outcomes",
            details={
                "successful_draw_count": successful,
                "value_counts": value_counts,
                "simulation_attempt_count": simulation_attempts,
                "recorded_attempt_count": recorded_attempts,
            },
        )


def _validate_monte_carlo_draw_set(draws: _MonteCarloDrawSet) -> None:
    """Reject disagreement between draw rows, counters, and sampled value arrays."""
    _validate_monte_carlo_draw_counts(draws)
    successful, recorded_attempts = _validate_monte_carlo_outcomes(draws)
    _validate_monte_carlo_values(
        draws,
        successful=successful,
        recorded_attempts=recorded_attempts,
    )


def _welfare_draw_set_is_complete(draws: _MonteCarloDrawSet) -> bool:
    """Derive completeness from the reconciled outcomes, counters, and values."""
    _validate_monte_carlo_draw_set(draws)
    return (
        draws.counters.attempted_draw_count == draws.requested_draw_count
        and len(draws.terminal_outcomes) == draws.requested_draw_count
        and all(outcome.get("outcome_code") == "success" for outcome in draws.terminal_outcomes)
    )


def _draw_outcome_provenance(draws: _MonteCarloDrawSet) -> dict[str, Any]:
    _validate_monte_carlo_draw_set(draws)
    successful = sum(
        outcome.get("outcome_code") == "success" for outcome in draws.terminal_outcomes
    )
    failed = len(draws.terminal_outcomes) - successful
    unattempted = draws.requested_draw_count - draws.counters.attempted_draw_count
    if successful + failed + unattempted != draws.requested_draw_count:
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo outcomes do not partition the requested draw budget",
            details={
                "requested_draw_count": draws.requested_draw_count,
                "successful_draw_count": successful,
                "failed_draw_count": failed,
                "unattempted_draw_count": unattempted,
            },
        )
    return {
        "schema_version": "1.2",
        "requested_draw_count": draws.requested_draw_count,
        "attempted_draw_count": draws.counters.attempted_draw_count,
        "simulation_attempt_count": draws.counters.simulation_attempt_count,
        "retry_attempt_count": draws.counters.retry_attempt_count,
        "max_attempts_per_draw": _WELFARE_MC_MAX_EXECUTION_ATTEMPTS,
        "successful_draw_count": successful,
        "failed_draw_count": failed,
        "unattempted_draw_count": unattempted,
        "outcome_denominator_complete": (
            draws.counters.attempted_draw_count == draws.requested_draw_count
            and len(draws.terminal_outcomes) == draws.requested_draw_count
        ),
        "summary_semantics": (
            "successful_draws_only_conditional_on_execution"
            if failed or unattempted
            else "complete_requested_draws"
        ),
        "outcomes": draws.terminal_outcomes,
    }
