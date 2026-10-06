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
    PosteriorSamplesCarrier,
    UncertaintyEnvelope,
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
    """Reject narrowing overflow before any sampler or evaluator is invoked."""
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)) or np.any(np.abs(array) > np.finfo(np.float32).max):
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


def admit_bounded_mean_response(
    response: object,
    envelopes: Mapping[str, UncertaintyEnvelope],
    plan: BoundedIIDMeanPlan,
) -> tuple[str, str]:
    """Admit the implemented complete response, never a callback-supplied flag."""
    if type(response) is not BoundedIndicatorResponse:
        raise ValueError("bounded mean certificate requires the canonical bounded evaluator")
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
    response = BoundedIndicatorResponse(
        input_name=certificate.evaluator_recipe["input_name"],
        metric_id=certificate.evaluator_recipe["metric_id"],
        threshold=certificate.evaluator_recipe["threshold"],
    )
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
    return certificate


def reconcile_draw_outcomes(receipt: Mapping[str, Any], metric_ids: list[str]) -> set[str]:
    """Reconcile every attempted terminal outcome, not a completeness declaration."""
    attempted = receipt["attempted_draw_count"]
    requested = receipt["requested_draw_count"]
    records = receipt["draw_records"]
    if (
        not isinstance(attempted, int)
        or not isinstance(requested, int)
        or not 0 <= attempted <= requested
        or receipt["unattempted_draw_count"] != requested - attempted
        or len(records) != attempted
        or {row["draw_index"] for row in records} != set(range(attempted))
    ):
        raise ValueError("draw denominator does not reconcile")
    failures = {row["draw_index"]: row for row in receipt["failure_records"]}
    if len(failures) != len(receipt["failure_records"]):
        raise ValueError("duplicate draw failures")
    failed_metrics: set[str] = set()
    successes = 0
    for row in records:
        success = set(row["successful_outputs"])
        failed = set(row["failed_outputs"])
        if success & failed or success | failed != set(metric_ids):
            raise ValueError("draw output denominator does not reconcile")
        failure = failures.get(row["draw_index"])
        declared_failed = (
            set()
            if failure is None
            else {value["output_metric_id"] for value in failure["output_outcomes"]}
        )
        if failed != declared_failed:
            raise ValueError("draw terminal outcomes disagree with failure records")
        if failure is not None and failure["sampled_input_sha256"] != row["sampled_input_sha256"]:
            raise ValueError("draw input identity changed across outcome records")
        failed_metrics.update(failed)
        successes += not failed
    if receipt["successful_draw_count"] != successes:
        raise ValueError("successful draw denominator does not reconcile")
    return failed_metrics
