"""Admit numerical sampling support without promoting declared source authority.

The bounded evaluators below define their complete mathematical response law;
arbitrary callbacks cannot obtain their fixed-budget mean certificate.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def sampling_content_digest(value: Any) -> str:
    """Bind an admitted recipe to canonical finite JSON content."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def joint_carrier_digest(
    names: list[str], envelopes: Mapping[str, UncertaintyEnvelope], draw_ids: list[str]
) -> str:
    """Bind finite-law coordinate order, exact paired rows, weights and row identity."""
    return sampling_content_digest(
        {
            "parameter_order": names,
            "draw_ids": draw_ids,
            "carriers": [
                envelopes[name].distribution_payload.model_dump(mode="json") for name in names
            ],
        }
    )


def admit_float32_range(values: object) -> np.ndarray:
    """Admit zeros and normal finite float32 values before numerical execution.

    The CPU JAX profile flushes subnormal operands in arithmetic, even when
    storage preserves them. A nonzero covariance must not become a null law.
    """
    array = np.asarray(values, dtype=np.float64)
    limits = np.finfo(np.float32)
    magnitudes = np.abs(array)
    if (
        not np.all(np.isfinite(array))
        or np.any(magnitudes > limits.max)
        or np.any((magnitudes != 0) & (magnitudes < limits.tiny))
    ):
        raise ValueError("sampling law exceeds finite float32 backend range")
    return array


def admit_sampling_support(envelopes: Mapping[str, UncertaintyEnvelope]) -> None:
    """Check every input carrier, covariance row, and support before execution."""
    for envelope in envelopes.values():
        admit_float32_range([envelope.point_estimate, *envelope.confidence_interval])
        row = envelope.metadata.get("covariance_row")
        if row is not None:
            admit_float32_range(row)
        payload = envelope.distribution_payload
        if isinstance(payload, PosteriorSamplesCarrier):
            admit_float32_range(payload.samples)
        elif payload is not None:
            parameters = getattr(payload, "parameters", {})
            admit_float32_range(list(parameters.values()))
            support = getattr(payload, "support", None)
            if support is not None:
                admit_float32_range(support)


class BoundedIIDMeanPlan(BaseModel):
    """Plan only a bounded IID mean using independent pilot and main draws."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    metric_id: str = Field(min_length=1)
    pilot_samples: int = Field(default=256, ge=2)
    absolute_error: float = Field(default=0.05, gt=0, lt=1)
    delta_pilot: float = Field(default=0.025, gt=0, lt=1)
    delta_main: float = Field(default=0.025, gt=0, lt=1)
    response_threshold: float | None = Field(default=None, ge=0, le=1)


class BoundedIIDMeanCertificate(BaseModel):
    """Record a numerical mean certificate separately from predictive spread."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    method: Literal["independent_pilot_frozen_bernstein_mean_v1"] = (
        "independent_pilot_frozen_bernstein_mean_v1"
    )
    estimand: Literal["bounded_iid_mean"] = "bounded_iid_mean"
    metric_id: str
    input_law_sha256: str
    evaluator_sha256: str
    input_law: UncertaintyEnvelope
    evaluator_recipe: dict[str, Any]
    mc_seed: int
    pilot_samples: int
    pilot_mean: float
    pilot_second_moment: float
    variance_upper_bound: float
    frozen_main_samples: int
    main_samples: int
    main_mean: float
    absolute_error: float
    delta_pilot: float
    delta_main: float
    pilot_stream: int
    main_stream: int
    predicate_basis: Literal["recomputed"] = "recomputed"
    authority_scope: Literal["declared_mathematical_input_law_only"] = (
        "declared_mathematical_input_law_only"
    )


@dataclass(frozen=True)
class BoundedIndicatorResponse:
    """Define a Bernoulli response over one explicit Uniform[0,1] input law."""

    input_name: str
    metric_id: str
    threshold: float

    def __call__(self, **params: Any) -> dict[str, float]:
        """Evaluate the complete bounded mathematical response."""
        return {self.metric_id: float(params[self.input_name] < self.threshold)}

    def recipe(self) -> dict[str, Any]:
        """Return all values defining this response law."""
        return {"response": "indicator_less_than", **self.__dict__}


def _admit_indicator_recipe(recipe: Mapping[str, Any]) -> BoundedIndicatorResponse:
    """Use one exact recipe admission at production and persisted readback."""
    if (
        set(recipe) != {"response", "input_name", "metric_id", "threshold"}
        or recipe["response"] != "indicator_less_than"
        or not isinstance(recipe["input_name"], str)
        or not recipe["input_name"]
        or not isinstance(recipe["metric_id"], str)
        or not recipe["metric_id"]
        or type(recipe["threshold"]) not in (int, float)
        or not math.isfinite(recipe["threshold"])
        or not 0 <= recipe["threshold"] <= 1
    ):
        raise ValueError("mean estimator evaluator recipe is not canonical")
    return BoundedIndicatorResponse(
        input_name=recipe["input_name"],
        metric_id=recipe["metric_id"],
        threshold=recipe["threshold"],
    )


def admit_bounded_mean_response(
    response: object,
    envelopes: Mapping[str, UncertaintyEnvelope],
    plan: BoundedIIDMeanPlan,
) -> tuple[str, str]:
    """Admit the implemented complete response, never a callback-supplied flag."""
    if type(response) is not BoundedIndicatorResponse:
        raise ValueError("bounded mean certificate requires the canonical bounded evaluator")
    _admit_indicator_recipe(response.recipe())
    if (
        set(envelopes) != {response.input_name}
        or response.metric_id != plan.metric_id
        or not math.isfinite(response.threshold)
        or not 0 <= response.threshold <= 1
        or plan.delta_pilot + plan.delta_main >= 1
    ):
        raise ValueError("bounded evaluator does not match the requested mean law")
    envelope = envelopes[response.input_name]
    if (
        envelope.distribution_family is not DistributionFamily.UNIFORM
        or envelope.confidence_interval != (0.0, 1.0)
        or envelope.distribution_payload is not None
    ):
        raise ValueError("bounded evaluator requires its exact Uniform[0,1] law")
    return (
        sampling_content_digest(envelope.model_dump(mode="json")),
        sampling_content_digest(response.recipe()),
    )


def frozen_bernstein_budget(pilot: object, plan: BoundedIIDMeanPlan) -> tuple[float, int]:
    """Derive the independent pilot variance upper bound and fixed main budget."""
    values = np.asarray(pilot, dtype=np.float64)
    if values.shape != (plan.pilot_samples,) or not np.all(np.isfinite(values)):
        raise ValueError("pilot is incomplete")
    if np.any(values < 0) or np.any(values > 1):
        raise ValueError("pilot is outside the admitted [0,1] support")
    a = math.sqrt(math.log(4 / plan.delta_pilot) / (2 * plan.pilot_samples))
    upper = min(
        0.25, max(0.0, float(np.mean(values**2)) + a - max(0.0, float(np.mean(values)) - a) ** 2)
    )
    count = math.ceil(
        (2 * upper + 2 * plan.absolute_error / 3)
        * math.log(2 / plan.delta_main)
        / plan.absolute_error**2
    )
    return upper, count


def verify_mean_certificate(envelope: UncertaintyEnvelope) -> BoundedIIDMeanCertificate | None:
    """Recompute certificate budget, scope, denominator and estimate on readback."""
    raw = envelope.metadata.get("mean_estimator_certificate")
    if raw is None:
        return None
    certificate = BoundedIIDMeanCertificate.model_validate(raw)
    recipe = certificate.evaluator_recipe
    response = _admit_indicator_recipe(recipe)
    plan = BoundedIIDMeanPlan(
        metric_id=certificate.metric_id,
        pilot_samples=certificate.pilot_samples,
        absolute_error=certificate.absolute_error,
        delta_pilot=certificate.delta_pilot,
        delta_main=certificate.delta_main,
    )
    law_digest, evaluator_digest = admit_bounded_mean_response(
        response,
        {response.input_name: certificate.input_law},
        plan,
    )
    streams = np.random.SeedSequence(certificate.mc_seed).spawn(2)
    pilot_seed, main_seed = [int(child.generate_state(1)[0]) for child in streams]
    pilot = (
        np.random.default_rng(pilot_seed).uniform(size=plan.pilot_samples) < response.threshold
    ).astype(np.float64)
    a = math.sqrt(math.log(4 / plan.delta_pilot) / (2 * plan.pilot_samples))
    upper = min(
        0.25,
        max(0.0, certificate.pilot_second_moment + a - max(0.0, certificate.pilot_mean - a) ** 2),
    )
    count = math.ceil(
        (2 * upper + 2 * plan.absolute_error / 3)
        * math.log(2 / plan.delta_main)
        / plan.absolute_error**2
    )
    payload = envelope.distribution_payload
    if (
        not isinstance(payload, PosteriorSamplesCarrier)
        or certificate.input_law_sha256 != law_digest
        or certificate.evaluator_sha256 != evaluator_digest
        or certificate.pilot_stream != pilot_seed
        or certificate.main_stream != main_seed
        or certificate.pilot_mean != float(np.mean(pilot))
        or certificate.pilot_second_moment != float(np.mean(pilot**2))
        or certificate.main_samples != count
        or certificate.frozen_main_samples != count
        or len(payload.samples) != count
        or certificate.pilot_stream == certificate.main_stream
        or not math.isclose(certificate.variance_upper_bound, upper, rel_tol=1e-12)
        or not math.isclose(certificate.main_mean, float(np.mean(payload.samples)), abs_tol=1e-12)
        or not math.isclose(certificate.main_mean, envelope.point_estimate, abs_tol=1e-12)
        or any(not 0 <= value <= 1 for value in payload.samples)
        or envelope.metadata.get("draw_failure_count", 0) != 0
    ):
        raise ValueError("mean estimator certificate failed persisted readback reconciliation")
    expected_main = (
        np.random.default_rng(main_seed).uniform(size=count) < response.threshold
    ).astype(np.float64)
    if not np.array_equal(np.asarray(payload.samples), expected_main):
        raise ValueError("mean estimator certificate main draws do not replay")
    advertised_interval = envelope.metadata.get("mean_error_interval")
    expected_interval = [
        max(0.0, certificate.main_mean - plan.absolute_error),
        min(1.0, certificate.main_mean + plan.absolute_error),
    ]
    alpha = plan.delta_pilot + plan.delta_main
    predictive_lo, predictive_hi = np.percentile(expected_main, [50 * alpha, 100 - 50 * alpha])
    expected_predictive = [
        min(float(predictive_lo), certificate.main_mean),
        max(float(predictive_hi), certificate.main_mean),
    ]
    tail = envelope.metadata.get("tail_risk")
    q05 = float(np.percentile(expected_main, 5))
    expected_tail = {
        "cvar_05": float(np.mean(expected_main[expected_main <= q05])),
        "quantile_01": float(np.percentile(expected_main, 1)),
        "quantile_99": float(np.percentile(expected_main, 99)),
    }
    if (
        not isinstance(advertised_interval, (list, tuple))
        or len(advertised_interval) != 2
        or not np.allclose(advertised_interval, expected_interval, rtol=0, atol=1e-12)
        or envelope.metadata.get("predictive_interval_semantics")
        != ("empirical_output_quantiles_v1_compatibility")
        or envelope.metadata.get("mc_n_samples") != count
        or envelope.metadata.get("mc_n_valid") != count
        or envelope.metadata.get("mc_n_failed") != 0
        or envelope.metadata.get("mc_seed") != certificate.mc_seed
        or envelope.metadata.get("mc_sampling_method") != "random"
        or not math.isclose(
            envelope.metadata.get("mc_std", -1), float(np.std(expected_main)), abs_tol=1e-12
        )
        or not np.allclose(envelope.confidence_interval, expected_predictive, rtol=0, atol=1e-12)
        or envelope.distribution_family is not DistributionFamily.BOOTSTRAP
        or envelope.source is not UncertaintySource.ENSEMBLE
        or envelope.propagation_method is not PropagationMethod.MONTE_CARLO
        or envelope.interval_semantics is not IntervalSemantics.CONFIDENCE_INTERVAL
        or envelope.is_heuristic_ci
        or payload.sample_axis != "draw"
        or payload.weights is not None
        or (
            count > 100
            and (
                not isinstance(tail, dict)
                or set(tail) != set(expected_tail)
                or any(
                    not math.isclose(tail[key], value, abs_tol=1e-7)
                    for key, value in expected_tail.items()
                )
            )
        )
        or envelope.sample_size != count
        or envelope.gate_eligible
        or not math.isclose(
            envelope.confidence_level or 0, 1 - plan.delta_pilot - plan.delta_main, abs_tol=1e-12
        )
    ):
        raise ValueError("advertised mean estimator claims do not reconcile")
    return certificate


class _TerminalDraw(BaseModel):
    """Strict persisted terminal record for one attempted draw."""

    model_config = ConfigDict(extra="forbid")
    draw_index: int = Field(ge=0, strict=True)
    sampled_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    successful_outputs: list[str]
    failed_outputs: list[str]


class _TerminalFailureOutput(BaseModel):
    """Strict supported failure code for one output."""

    model_config = ConfigDict(extra="forbid")
    output_metric_id: str = Field(min_length=1, strict=True)
    outcome_code: Literal[
        "simulation_exception",
        "invalid_response",
        "missing_output",
        "non_numeric_output",
        "non_finite_output",
    ]
    error_type: str | None = None


class _TerminalFailure(BaseModel):
    """Bind failure reasons to the exact attempted draw identity."""

    model_config = ConfigDict(extra="forbid")
    draw_index: int = Field(ge=0, strict=True)
    sampled_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    output_outcomes: list[_TerminalFailureOutput] = Field(min_length=1)


def reconcile_draw_outcomes(receipt: Mapping[str, Any], metric_ids: list[str]) -> set[str]:
    """Reconcile every attempted terminal outcome, not a completeness declaration."""
    attempted = receipt["attempted_draw_count"]
    requested = receipt["requested_draw_count"]
    records = [_TerminalDraw.model_validate(row).model_dump() for row in receipt["draw_records"]]
    failure_rows = [
        _TerminalFailure.model_validate(row).model_dump() for row in receipt["failure_records"]
    ]
    if (
        type(attempted) is not int
        or type(requested) is not int
        or len(set(metric_ids)) != len(metric_ids)
        or type(receipt["unattempted_draw_count"]) is not int
        or type(receipt["successful_draw_count"]) is not int
        or type(receipt["outcome_denominator_complete"]) is not bool
        or receipt["outcome_denominator_complete"] != (requested == attempted)
        or not 0 <= attempted <= requested
        or receipt["unattempted_draw_count"] != requested - attempted
        or len(records) != attempted
        or {row["draw_index"] for row in records} != set(range(attempted))
    ):
        raise ValueError("draw denominator does not reconcile")
    failures = {row["draw_index"]: row for row in failure_rows}
    actual_failure_indices = {row["draw_index"] for row in records if row["failed_outputs"]}
    if len(failures) != len(failure_rows) or set(failures) != actual_failure_indices:
        raise ValueError("failure records do not match the attempted draw denominator")
    failed_metrics: set[str] = set(metric_ids) if requested > attempted or attempted == 0 else set()
    successes = 0
    for row in records:
        success = set(row["successful_outputs"])
        failed = set(row["failed_outputs"])
        if (
            success & failed
            or success | failed != set(metric_ids)
            or len(success) != len(row["successful_outputs"])
            or len(failed) != len(row["failed_outputs"])
        ):
            raise ValueError("draw output denominator does not reconcile")
        failure = failures.get(row["draw_index"])
        declared_failed = (
            set()
            if failure is None
            else {value["output_metric_id"] for value in failure["output_outcomes"]}
        )
        if failed != declared_failed:
            raise ValueError("draw terminal outcomes disagree with failure records")
        if failure is not None and len(declared_failed) != len(failure["output_outcomes"]):
            raise ValueError("failure output denominator contains duplicate outcomes")
        if failure is not None and failure["sampled_input_sha256"] != row["sampled_input_sha256"]:
            raise ValueError("draw input identity changed across outcome records")
        failed_metrics.update(failed)
        successes += not failed
    if receipt["successful_draw_count"] != successes:
        raise ValueError("successful draw denominator does not reconcile")
    return failed_metrics
