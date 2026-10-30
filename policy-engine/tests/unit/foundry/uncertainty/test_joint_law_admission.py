"""Behavioral refusal/binding oracles for the existing MC and dispatcher routes."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from datetime import datetime, time, timedelta, tzinfo
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from functools import wraps
from inspect import Parameter, Signature

import numpy as np
import pytest

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.covariance import has_unknown_dependency
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.foundry.uncertainty.protocol import PropagationResult
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    CompositionProvenance,
    CompositionStep,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    QuantileSummaryCarrier,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal(metadata: dict[str, object] | None = None) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.959963984540054, 1.959963984540054),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata=metadata or {},
    )


def _empirical(*, axis: str = "row", joint_id: str | None = None) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.0, 1.0),
        confidence_level=0.95,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=PosteriorSamplesCarrier(samples=(-1.0, 1.0), sample_axis=axis),
        metadata={} if joint_id is None else {"joint_sample_id": joint_id},
    )


def _gaussian_pair() -> dict[str, UncertaintyEnvelope]:
    return {
        name: _normal({"covariance_row": [1.0, 1.0], "covariance_params": ["a", "b"]})
        for name in ("a", "b")
    }


def _refused_law(kind: str) -> tuple[dict[str, UncertaintyEnvelope], str]:
    if kind == "empirical_unestablished":
        return {"a": _empirical(), "b": _empirical()}, "unestablished_joint_law"
    if kind == "empirical_axis":
        return {
            "a": _empirical(joint_id="declared-candidate-rows"),
            "b": _empirical(axis="other-row", joint_id="declared-candidate-rows"),
        }, "incompatible_joint_law"
    if kind == "empirical_weights":
        a = _empirical(joint_id="declared-candidate-rows")
        b = a.model_copy(
            update={
                "distribution_payload": PosteriorSamplesCarrier(
                    samples=(-1.0, 1.0), sample_axis="row", weights=(0.0, 0.0)
                )
            }
        )
        return {"a": a, "b": b}, "incompatible_joint_law"
    if kind == "empirical_mixed":
        return {"a": _empirical(), "b": _normal()}, "incompatible_joint_law"
    if kind == "unknown_dependency":
        return {name: _normal({"dependency": "unknown"}) for name in ("a", "b")}, kind
    if kind == "unsupported_fit":
        fit = _normal().model_copy(
            update={
                "distribution_payload": ParametricFitCarrier(
                    family=DistributionFamily.NORMAL,
                    parameters={"mean": 0.0, "std": 1.0},
                    support=(-1.0, 1.0),
                )
            }
        )
        return {"a": fit, "b": _normal()}, "unsupported_parametric_fit"
    if kind == "unsupported_payload":
        quantiles = _normal().model_copy(
            update={"distribution_payload": QuantileSummaryCarrier(quantiles={"0.5": 0.0})}
        )
        return {"a": quantiles, "b": _normal()}, "unsupported_distribution_payload"
    if kind == "unsupported_family":
        unknown = _normal().model_copy(update={"distribution_family": DistributionFamily.UNKNOWN})
        return {"a": unknown, "b": _normal()}, "unsupported_distribution_family"
    envelopes = _gaussian_pair()
    if kind == "gaussian_asymmetric":
        envelopes["b"] = _normal({"covariance_row": [-1.0, 1.0], "covariance_params": ["a", "b"]})
        return envelopes, "incompatible_dependency"
    if kind == "gaussian_unlabeled":
        return {
            name: _normal({"covariance_row": [1.0, 1.0]}) for name in ("a", "b")
        }, "incompatible_dependency"
    if kind == "gaussian_mixed":
        envelopes["b"] = envelopes["b"].model_copy(
            update={"distribution_family": DistributionFamily.UNIFORM}
        )
        return envelopes, "unsupported_joint_covariance"
    raise AssertionError(f"unknown test law: {kind}")


def _propagate(
    route: str,
    simulation_fn: Callable[..., Mapping[str, float]],
    nominal: Mapping[str, float],
    envelopes: Mapping[str, UncertaintyEnvelope],
) -> list[PropagationResult]:
    config = PropagationConfig(
        preferred_method="monte_carlo" if route == "dispatcher_mc" else "auto",
        mc_n_samples=100,
        mc_batch_size=100,
        compute_sensitivity=False,
        delta_covariance_jitter=0.0,
    )
    if route == "mc":
        return MonteCarloPropagator(config).propagate(simulation_fn, nominal, envelopes, ["y"])
    return PropagationDispatcher(config).propagate(
        simulation_fn, nominal, envelopes, ["y"], is_jax_differentiable=False
    )


def _evaluator_and_binding(
    fault: str, calls: list[dict[str, float]], signature_reads: list[str]
) -> tuple[Callable[..., Mapping[str, float]], dict[str, float]]:
    def response(a: float, b: float, scale: float) -> dict[str, float]:
        calls.append({"a": a, "b": b, "scale": scale})
        return {"y": scale * (a - b)}

    nominal = {"a": 0.0, "b": 0.0, "scale": 3.0}
    if fault == "missing_nominal":
        return response, {"scale": 3.0}
    if fault == "missing_fixed":
        return response, {"a": 0.0, "b": 0.0}
    if fault == "opaque":

        class OpaqueEvaluator:
            @property
            def __signature__(self) -> None:
                signature_reads.append("inspected")
                raise ValueError("an executable law needs an inspectable adapter")

            def __call__(self, **params: float) -> dict[str, float]:
                calls.append(params)
                return {"y": params["a"] - params["b"]}

        return OpaqueEvaluator(), nominal
    assert fault == "valid"
    return response, nominal


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("fault", ["valid", "missing_nominal", "missing_fixed", "opaque"])
@pytest.mark.parametrize(
    "kind",
    [
        "empirical_unestablished",
        "empirical_axis",
        "empirical_weights",
        "empirical_mixed",
        "unknown_dependency",
        "unsupported_fit",
        "unsupported_payload",
        "unsupported_family",
        "gaussian_asymmetric",
        "gaussian_unlabeled",
        "gaussian_mixed",
    ],
)
def test_refused_sampling_law_precedes_irrelevant_binding_and_never_evaluates(
    route: str, fault: str, kind: str
) -> None:
    envelopes, failure = _refused_law(kind)
    calls: list[dict[str, float]] = []
    signature_reads: list[str] = []
    response, nominal = _evaluator_and_binding(fault, calls, signature_reads)
    error: Exception | None = None
    results: list[PropagationResult] = []
    try:
        results = _propagate(route, response, nominal, envelopes)
    except Exception as exc:
        error = exc

    assert calls == [], "a refused sampling law reached an evaluator effect"
    assert signature_reads == [], "a refused sampling law inspected an irrelevant binding"
    assert error is None, f"typed law refusal was replaced by binding/backend error: {error!r}"
    assert len(results) == 1
    result = results[0]
    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["failure"] == failure
    # A refused law retains its cause and still discloses unbound fixed inputs.
    # Recipe 1.0 does not bind the fixed scale supplied by these binding fixtures.
    expected_diagnostics: dict[str, bool | str] = {failure: True}
    if "scale" in nominal:
        expected_diagnostics["input_identity_status"] = "not_established"
        assert result.envelope.metadata["invocation_identity_status"] == "not_established"
    else:
        assert "invocation_identity_status" not in result.envelope.metadata
    assert result.diagnostics == expected_diagnostics
    assert result.input_envelopes_used == ["a", "b"]
    dispatcher_owned = route != "mc" and kind in {
        "unknown_dependency",
        "gaussian_asymmetric",
        "gaussian_unlabeled",
    }
    expected_method = PropagationMethod.NONE if dispatcher_owned else PropagationMethod.MONTE_CARLO
    assert result.method_used is expected_method


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("kind", ["empirical", "gaussian"])
def test_supported_joint_laws_keep_every_draw_and_fixed_input(route: str, kind: str) -> None:
    envelopes = (
        {name: _empirical(joint_id="declared-candidate-rows") for name in ("a", "b")}
        if kind == "empirical"
        else _gaussian_pair()
    )
    calls: list[dict[str, float]] = []
    response, nominal = _evaluator_and_binding("valid", calls, [])
    result = _propagate(route, response, nominal, envelopes)[0]
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.samples == (0.0,) * 100
    assert result.diagnostics["n_samples"] == 100
    assert result.diagnostics["n_valid"] == 100
    assert result.method_used is PropagationMethod.MONTE_CARLO
    assert result.envelope.gate_eligible is False
    assert len(calls) == 101
    assert all(call["scale"] == 3.0 and call["a"] == call["b"] for call in calls)


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("kind", ["empirical", "gaussian"])
@pytest.mark.parametrize(
    ("fault", "message"),
    [("missing_nominal", "nominal"), ("missing_fixed", "scale"), ("opaque", "inspectable")],
)
def test_supported_laws_still_reject_invalid_binding_before_evaluator_effects(
    route: str, kind: str, fault: str, message: str
) -> None:
    envelopes = (
        {name: _empirical(joint_id="declared-candidate-rows") for name in ("a", "b")}
        if kind == "empirical"
        else _gaussian_pair()
    )
    calls: list[dict[str, float]] = []
    response, nominal = _evaluator_and_binding(fault, calls, [])
    with pytest.raises(ValueError, match=message):
        _propagate(route, response, nominal, envelopes)
    assert calls == []


def test_executable_auto_law_rejects_fixed_input_before_applicability_probe() -> None:
    calls: list[dict[str, float]] = []

    def required_fixed(a: float, b: float, scale: float) -> dict[str, float]:
        return {"y": scale * (a - b)}

    @wraps(required_fixed)
    def observable(**params: float) -> dict[str, float]:
        calls.append(params)
        return required_fixed(**params)

    with pytest.raises(ValueError, match="scale"):
        PropagationDispatcher(PropagationConfig()).propagate(
            observable, {"a": 0.0, "b": 0.0}, _gaussian_pair(), ["y"]
        )
    assert calls == [], "an otherwise executable law was probed before its fixed input was bound"


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
def test_versioned_profile_fence_still_precedes_legacy_law_and_binding(route: str) -> None:
    envelopes, _failure = _refused_law("empirical_unestablished")
    envelopes["a"] = envelopes["a"].model_copy(
        update={
            "metadata": {
                "profile_id": "urn:policyos:ir:bayesian-posterior-summary-profile:1",
                "profile_version": "1.1",
            }
        }
    )
    calls: list[dict[str, float]] = []
    response, nominal = _evaluator_and_binding("missing_fixed", calls, [])
    with pytest.raises(ValueError, match="v1.1 posterior summary profile"):
        _propagate(route, response, nominal, envelopes)
    assert calls == []


@pytest.mark.parametrize("method", ["delta", "analytical"])
def test_explicit_moment_routes_do_not_acquire_mc_gaussian_family_restrictions(method: str) -> None:
    columns = ["a", "b"]
    envelopes = {
        "a": _normal({"covariance_row": [1.0, 0.0], "covariance_params": columns}),
        "b": UncertaintyEnvelope(
            point_estimate=0.0,
            confidence_interval=(-(3.0**0.5), 3.0**0.5),
            confidence_level=None,
            distribution_family=DistributionFamily.UNIFORM,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={"covariance_row": [0.0, 1.0], "covariance_params": columns},
        ),
    }
    result = PropagationDispatcher(
        PropagationConfig(preferred_method=method, delta_covariance_jitter=0.0)
    ).propagate(lambda a, b: {"y": a - b}, {"a": 0.0, "b": 0.0}, envelopes, ["y"])[0]
    assert result.method_used is PropagationMethod.DELTA_METHOD
    assert result.diagnostics["output_variance"] == pytest.approx(2.0, abs=1e-5)
    assert result.envelope.gate_eligible is False


@pytest.mark.parametrize("method", ["delta", "analytical"])
def test_fixed_invocation_identity_limitation_finalizes_every_moment_route(method: str) -> None:
    scale = [2.0]
    kwargs: dict[str, object] = {"is_jax_differentiable": True}
    if method == "analytical":
        kwargs["weights"] = {"x": 1.0}
    result = PropagationDispatcher(
        PropagationConfig(preferred_method=method, delta_covariance_jitter=0.0)
    ).propagate(
        lambda x, scale: {"y": x * scale[0]},
        {"x": 0.0, "scale": scale},
        {"x": _normal()},
        ["y"],
        **kwargs,
    )[0]
    assert result.method_used is (
        PropagationMethod.ANALYTICAL if method == "analytical" else PropagationMethod.DELTA_METHOD
    )
    assert result.envelope.gate_eligible is False
    assert result.diagnostics["input_identity_status"] == "not_established"
    assert result.envelope.metadata["invocation_identity_status"] == "not_established"


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("phase", ["signature", "nominal", "draw"])
def test_invocation_snapshot_binds_law_fixed_inputs_outputs_and_eligibility(
    route: str, phase: str
) -> None:
    envelope = _normal({"note": {"items": [1, 2], "signed": -0.0}})
    envelope = envelope.model_copy(update={"gate_eligible": True})
    nominal = {"x": 0.0, "scale": 3.0}
    metrics = ["y"]
    initial_payload = json.dumps(
        envelope.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    expected_hash = hashlib.sha256(initial_payload).hexdigest()
    calls: list[dict[str, float]] = []
    mutated = False

    def mutate_original() -> None:
        nonlocal mutated
        if mutated:
            return
        mutated = True
        envelope.metadata["dependency"] = "unknown"
        envelope.metadata["note"]["items"].append(99)
        nominal["scale"] = 99.0
        metrics[:] = ["other"]

    class MutatingEvaluator:
        @property
        def __signature__(self) -> Signature:
            if phase == "signature":
                mutate_original()
            return Signature(
                [
                    Parameter("x", Parameter.POSITIONAL_OR_KEYWORD),
                    Parameter("scale", Parameter.POSITIONAL_OR_KEYWORD),
                ]
            )

        def __call__(self, x: float, scale: float) -> dict[str, float]:
            calls.append({"x": x, "scale": scale})
            if (phase == "nominal" and len(calls) == 1) or (phase == "draw" and len(calls) == 2):
                mutate_original()
            return {"y": x * scale}

    config = PropagationConfig(
        preferred_method="monte_carlo" if route == "dispatcher_mc" else "auto",
        mc_n_samples=100,
        mc_batch_size=100,
        compute_sensitivity=False,
    )
    error: Exception | None = None
    results: list[PropagationResult] = []
    try:
        if route == "mc":
            results = MonteCarloPropagator(config).propagate(
                MutatingEvaluator(), nominal, {"x": envelope}, metrics
            )
        else:
            results = PropagationDispatcher(config).propagate(
                MutatingEvaluator(),
                nominal,
                {"x": envelope},
                metrics,
                is_jax_differentiable=False,
            )
    except Exception as exc:
        error = exc
    assert mutated and nominal["scale"] == 99.0 and metrics == ["other"]
    assert envelope.metadata["dependency"] == "unknown"
    assert error is None, f"caller mutation escaped the admitted entry snapshot: {error!r}"
    assert len(results) == 1 and results[0].metric_id == "y"
    result = results[0]
    assert len(calls) == 101 and all(call["scale"] == 3.0 for call in calls)
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert len(payload.samples) == 100
    for observed, draw in zip(payload.samples, calls[1:], strict=True):
        assert observed == pytest.approx(draw["x"] * 3.0, rel=1e-6, abs=1e-6)
    assert result.envelope.gate_eligible is False
    recipe = result.diagnostics["draw_outcome_provenance"]["sampling_recipe"]
    assert recipe["input_envelope_sha256"] == {"x": expected_hash}
    changed_hash = hashlib.sha256(
        json.dumps(
            envelope.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    assert changed_hash != expected_hash


@pytest.mark.parametrize("change", ["add", "clear"])
@pytest.mark.parametrize("differentiable", [False, True])
def test_dispatcher_route_weights_belong_to_the_entry_snapshot(
    change: str, differentiable: bool
) -> None:
    weights = {} if change == "add" else {"x": 1.0}
    calls: list[float] = []

    class MutatingWeights:
        @property
        def __signature__(self) -> Signature:
            if change == "add":
                weights["x"] = 1.0
            else:
                weights.clear()
            return Signature([Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)])

        def __call__(self, x: float) -> dict[str, float]:
            calls.append(x)
            return {"y": x}

    result = PropagationDispatcher(
        PropagationConfig(mc_n_samples=100, mc_batch_size=100, compute_sensitivity=False)
    ).propagate(
        MutatingWeights(),
        {"x": 0.0},
        {"x": _normal()},
        ["y"],
        is_jax_differentiable=differentiable,
        weights=weights,
    )[0]
    if change == "clear":
        assert weights == {}
        assert result.method_used is PropagationMethod.ANALYTICAL and calls == []
        assert result.diagnostics["output_variance"] == pytest.approx(1.0, abs=1e-5)
    elif differentiable:
        assert weights == {"x": 1.0}
        assert result.method_used is PropagationMethod.DELTA_METHOD and calls
        assert result.diagnostics["output_variance"] == pytest.approx(1.0, abs=1e-5)
    else:
        assert weights == {"x": 1.0}
        assert result.method_used is PropagationMethod.MONTE_CARLO
        assert len(calls) == 101


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
def test_snapshot_preserves_refused_covariance_tuple_without_json_coercion(route: str) -> None:
    envelopes = _gaussian_pair()
    envelopes["a"].metadata["covariance_row"] = (1.0, 1.0)
    calls: list[dict[str, float]] = []
    response, nominal = _evaluator_and_binding("valid", calls, [])
    result = _propagate(route, response, nominal, envelopes)[0]
    assert result.envelope.metadata["failure"] == "incompatible_dependency"
    assert result.envelope.gate_eligible is False and calls == []


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
def test_snapshot_preserves_ieee_negative_zero_at_the_actual_legacy_consumer(route: str) -> None:
    envelope = _empirical().model_copy(
        update={
            "point_estimate": -0.0,
            "confidence_interval": (-0.0, 0.0),
            "distribution_payload": PosteriorSamplesCarrier(samples=(-0.0,), sample_axis="row"),
        }
    )
    result = _propagate(
        route, lambda x: {"y": math.copysign(1.0, x)}, {"x": -0.0}, {"x": envelope}
    )[0]
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.samples == (-1.0,) * 100
    assert result.envelope.point_estimate == -1.0


def _raw_identity(envelope: UncertaintyEnvelope) -> str | None:
    try:
        payload = json.dumps(
            envelope.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload).hexdigest()


class _MutableTimezone(tzinfo):
    def __init__(self) -> None:
        self.minutes = 0

    def __repr__(self) -> str:
        return "<MutableTimezone>"

    def __deepcopy__(self, memo: object) -> _MutableTimezone:
        return self

    def utcoffset(self, value: datetime | None) -> timedelta:
        return timedelta(minutes=self.minutes)

    def dst(self, value: datetime | None) -> timedelta:
        return timedelta(0)

    def tzname(self, value: datetime | None) -> str:
        return "MutableTimezone"


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("kind", ["fraction", "decimal", "numpy", "float", "int", "bool"])
def test_supported_fixed_scalars_keep_callback_type_value_and_entry_association(
    route: str, kind: str
) -> None:
    scalar = {
        "fraction": Fraction(1, 3),
        "decimal": Decimal("0.1"),
        "numpy": np.float64(-0.0),
        "float": -0.0,
        "int": 7,
        "bool": True,
    }[kind]
    nominal = {"x": 0.0, "scale": scalar}
    observed: list[tuple[float, object]] = []

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            nominal["scale"] = 99.0
            return Signature(
                [
                    Parameter("x", Parameter.POSITIONAL_OR_KEYWORD),
                    Parameter("scale", Parameter.POSITIONAL_OR_KEYWORD),
                ]
            )

        def __call__(self, x: float, scale: object) -> dict[str, float]:
            observed.append((x, scale))
            assert type(scale) is type(scalar), "a fixed scalar was silently float-coerced"
            assert scale == scalar
            if kind in {"numpy", "float"}:
                assert math.copysign(1.0, float(scale)) == -1.0
            return {"y": float(scale) * x}

    result = _propagate(route, Evaluator(), nominal, {"x": _empirical()})[0]
    assert nominal["scale"] == 99.0 and len(observed) == 101
    assert (
        result.diagnostics["draw_outcome_provenance"]["input_identity_status"] == "not_established"
    )
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert len(payload.samples) == 100
    for value, (draw, fixed) in zip(payload.samples, observed[1:], strict=True):
        assert value == pytest.approx(draw * float(fixed), abs=2e-8)


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("phase", ["signature", "nominal", "draw"])
@pytest.mark.parametrize("kind", ["opaque", "nested_dtype", "timezone"])
def test_inert_sidecars_preserve_original_identity_limitation_and_numerical_law(
    route: str, phase: str, kind: str
) -> None:
    zone = _MutableTimezone()
    marker: list[str] = []
    array = np.zeros(1, dtype=np.dtype([("a", np.dtype("f8", metadata={"probe": marker}))]))
    assert array.dtype.metadata is None and array.dtype["a"].metadata is not None
    extension = {
        "opaque": object(),
        "nested_dtype": array,
        "timezone": datetime(2026, 10, 28, 12, tzinfo=zone),
    }[kind]
    envelope = _normal({"same_extension_key": extension})
    identity = _raw_identity(envelope)
    assert (identity is None) is (kind != "timezone")
    calls: list[float] = []
    changed = False

    def mutate() -> None:
        nonlocal changed
        changed = True
        marker.append("changed")
        array["a"] = 999.0
        zone.minutes = 60

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            if phase == "signature":
                mutate()
            return Signature([Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)])

        def __call__(self, x: float) -> dict[str, float]:
            calls.append(x)
            if (phase == "nominal" and len(calls) == 1) or (phase == "draw" and len(calls) == 2):
                mutate()
            return {"y": x}

    result = _propagate(route, Evaluator(), {"x": 0.0}, {"x": envelope})[0]
    assert changed and len(calls) == 101
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.samples == pytest.approx(calls[1:], abs=1e-10)
    provenance = result.diagnostics["draw_outcome_provenance"]
    assert provenance["sampling_recipe"]["input_envelope_sha256"] == {"x": identity}
    assert provenance["input_identity_status"] == "not_established"
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["metadata_context_status"] == "not_established"


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("phase", ["signature", "nominal", "draw"])
@pytest.mark.parametrize("role", ["dependency", "mc_sampling_method"])
@pytest.mark.parametrize("kind", ["enum", "nested_dtype", "timezone"])
def test_behavioral_metadata_meaning_is_owned_at_actual_mc_law_and_result_consumers(
    route: str, phase: str, role: str, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = "known" if role == "dependency" else "sobol"
    changed = "unknown" if role == "dependency" else "random"
    zone = _MutableTimezone()
    value = datetime(2026, 10, 28, 12, tzinfo=zone)
    array = np.zeros(
        1, dtype=np.dtype([("a", np.dtype("f8", metadata={"state": {"value": initial}}))])
    )
    assert array.dtype.metadata is None
    state = array.dtype["a"].metadata["state"]
    if kind == "enum":

        class Meaning(Enum):
            MARKER = "wire-value-differs-from-consumed-meaning"

            def __str__(self) -> str:
                return self.meaning

        marker = Meaning.MARKER
        marker.meaning = initial
    else:

        class Meaning:
            def __str__(self) -> str:
                if kind == "nested_dtype":
                    return state["value"]
                return initial if value.utcoffset() == timedelta(0) else changed

        marker = Meaning()
    envelope = _normal({role: marker})
    identity = _raw_identity(envelope)
    assert (identity is not None) is (kind == "enum")
    calls: list[float] = []
    contexts: list[tuple[bool, bool]] = []
    original = MonteCarloPropagator._build_results

    def observe(
        self: MonteCarloPropagator, *args: object, **kwargs: object
    ) -> list[PropagationResult]:
        actual_inputs = args[2]
        contexts.append(
            (
                has_unknown_dependency(actual_inputs),
                str(actual_inputs["x"].metadata.get("mc_sampling_method", "")).lower()
                in {"sobol", "halton"},
            )
        )
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MonteCarloPropagator, "_build_results", observe)

    def mutate() -> None:
        if kind == "enum":
            marker.meaning = changed
        state["value"] = changed
        zone.minutes = 60

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            if phase == "signature":
                mutate()
            return Signature([Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)])

        def __call__(self, x: float) -> dict[str, float]:
            calls.append(x)
            if (phase == "nominal" and len(calls) == 1) or (phase == "draw" and len(calls) == 2):
                mutate()
            return {"y": x}

    result = _propagate(route, Evaluator(), {"x": 0.0}, {"x": envelope})[0]
    assert len(calls) == 101 and contexts == [(False, role == "mc_sampling_method")]
    assert str(marker) == changed
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["metadata_context_status"] == "not_established"
    assert (
        result.diagnostics["draw_outcome_provenance"]["input_identity_status"] == "not_established"
    )
    assert result.diagnostics["draw_outcome_provenance"]["sampling_recipe"][
        "input_envelope_sha256"
    ] == {"x": identity}
    if role == "mc_sampling_method":
        provenance = result.envelope.composition_provenance
        assert provenance is not None
        assert provenance.native_flavour is ComposedFlavour.QUASI_MONTE_CARLO
        assert provenance.operator_history[-1].input_flavours == (
            ComposedFlavour.QUASI_MONTE_CARLO,
        )


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("key", ["dependency", "dependence"])
def test_enum_unknown_meaning_refuses_before_any_signature_or_evaluator(
    route: str, key: str
) -> None:
    class Meaning(Enum):
        UNKNOWN = "this-wire-value-is-not-unknown"

        def __str__(self) -> str:
            return "unknown"

    calls: list[float] = []

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            raise AssertionError("an unestablished law must not inspect the signature")

        def __call__(self, x: float) -> dict[str, float]:
            calls.append(x)
            return {"y": x}

    result = _propagate(route, Evaluator(), {}, {"x": _normal({key: Meaning.UNKNOWN})})[0]
    assert result.envelope.metadata["failure"] == "unknown_dependency"
    assert result.envelope.gate_eligible is False and calls == []


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("phase", ["signature", "nominal", "draw"])
def test_mutated_parametric_parameters_cannot_change_the_prepared_marginal_law(
    route: str, phase: str
) -> None:
    payload = ParametricFitCarrier(
        family=DistributionFamily.NORMAL, parameters={"mean": 0.0, "std": 0.0}
    )
    envelope = _normal().model_copy(update={"distribution_payload": payload})
    calls: list[float] = []

    def mutate() -> None:
        payload.parameters.update(mean=12.0, std=9.0)

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            if phase == "signature":
                mutate()
            return Signature([Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)])

        def __call__(self, x: float) -> dict[str, float]:
            calls.append(x)
            if (phase == "nominal" and len(calls) == 1) or (phase == "draw" and len(calls) == 2):
                mutate()
            return {"y": x}

    result = _propagate(route, Evaluator(), {"x": 0.0}, {"x": envelope})[0]
    retained = result.envelope.distribution_payload
    assert isinstance(retained, PosteriorSamplesCarrier)
    assert len(calls) == 101 and payload.parameters == {"mean": 12.0, "std": 9.0}
    assert all(abs(value) < 1e-8 for value in calls)
    assert all(abs(value) < 1e-8 for value in retained.samples)


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
def test_existing_provenance_wire_context_is_fixed_before_callback_mutation(route: str) -> None:
    zone = _MutableTimezone()
    step = CompositionStep(
        op="push_forward",
        stage_name="prior.measured.stage",
        input_flavours=(ComposedFlavour.ANALYTICAL,),
        output_flavour=ComposedFlavour.DELTA,
        notes={"observed_at": datetime(2026, 10, 28, 12, tzinfo=zone), "values": [1]},
    )
    prior = CompositionProvenance(
        native_flavour=ComposedFlavour.ANALYTICAL,
        composed_flavour=ComposedFlavour.DELTA,
        exactness=ExactnessKind.APPROXIMATION,
        certificate_kind=CertificateKind.TAYLOR_REMAINDER,
        certificate_radius={"bound": 1.0},
        origin_envelope_ids=("original-source",),
        operator_history=(step,),
    )
    envelope = _normal().model_copy(update={"composition_provenance": prior})
    original_wire_step = step.model_dump(mode="json")
    identity = _raw_identity(envelope)
    calls: list[float] = []

    def response(x: float) -> dict[str, float]:
        calls.append(x)
        zone.minutes = 60
        step.notes["values"].append(99)
        prior.certificate_radius["bound"] = 999.0
        return {"y": x}

    result = _propagate(route, response, {"x": 0.0}, {"x": envelope})[0]
    actual = result.envelope.composition_provenance
    assert actual is not None and len(calls) == 101
    assert actual.operator_history[0].model_dump(mode="json") == original_wire_step
    assert actual.origin_envelope_ids == ("original-source",)
    assert result.diagnostics["draw_outcome_provenance"]["sampling_recipe"][
        "input_envelope_sha256"
    ] == {"x": identity}


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("kind", ["nested_dtype", "timezone"])
def test_inert_extension_does_not_become_an_admitted_covariance_row(route: str, kind: str) -> None:
    marker: list[str] = []
    array = np.zeros(1, dtype=np.dtype([("a", np.dtype("f8", metadata={"probe": marker}))]))
    value = array if kind == "nested_dtype" else datetime(2026, 10, 28, tzinfo=_MutableTimezone())
    envelopes = _gaussian_pair()
    envelopes["a"].metadata["covariance_row"] = value
    calls: list[dict[str, float]] = []
    evaluator, nominal = _evaluator_and_binding("missing_nominal", calls, [])
    result = _propagate(route, evaluator, nominal, envelopes)[0]
    assert result.envelope.metadata["failure"] == "incompatible_dependency"
    assert result.envelope.gate_eligible is False and calls == []


def test_analytical_weight_numeric_value_is_captured_before_signature_mutation() -> None:
    class Weight:
        value = 1.0

        def __float__(self) -> float:
            return self.value

    weight = Weight()
    calls: list[float] = []

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            weight.value = 99.0
            return Signature([Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)])

        def __call__(self, x: float) -> dict[str, float]:
            calls.append(x)
            return {"y": x}

    result = PropagationDispatcher(PropagationConfig(compute_sensitivity=False)).propagate(
        Evaluator(),
        {"x": 0.0},
        {"x": _normal()},
        ["y"],
        weights={"x": weight},
    )[0]
    assert weight.value == 99.0 and calls == []
    assert result.method_used is PropagationMethod.ANALYTICAL
    assert result.diagnostics["output_variance"] == pytest.approx(1.0, abs=1e-5)
    assert result.envelope.metadata["weights"] == {"x": 1.0}


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
@pytest.mark.parametrize("kind", ["list", "numpy_subclass"])
def test_mutable_fixed_objects_keep_borrowed_computation_without_owned_identity_or_gate(
    route: str,
    kind: str,
) -> None:
    class MutableScalar(np.float64):
        # A namespace spelling is not evidence of a native immutable type.
        __module__ = "numpy"

        def __float__(self) -> float:
            return self.current

    if kind == "list":
        fixed = [2.0]
    else:
        fixed = MutableScalar(2.0)
        fixed.current = 2.0
    calls: list[tuple[float, object]] = []

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            if kind == "list":
                fixed[0] = 3.0
            else:
                fixed.current = 3.0
            return Signature(
                [
                    Parameter("x", Parameter.POSITIONAL_OR_KEYWORD),
                    Parameter("scale", Parameter.POSITIONAL_OR_KEYWORD),
                ]
            )

        def __call__(self, x: float, scale: object) -> dict[str, float]:
            calls.append((x, scale))
            assert scale is fixed
            factor = scale[0] if kind == "list" else float(scale)
            return {"y": factor * x}

    result = _propagate(route, Evaluator(), {"x": 0.0, "scale": fixed}, {"x": _empirical()})[0]
    assert (fixed[0] if kind == "list" else float(fixed)) == 3.0
    assert len(calls) == 101
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.samples == pytest.approx([3.0 * item[0] for item in calls[1:]], abs=1e-12)
    provenance = result.diagnostics["draw_outcome_provenance"]
    assert provenance["input_identity_status"] == "not_established"
    assert provenance["sampling_recipe"]["input_envelope_sha256"]["x"] is not None
    assert result.envelope.gate_eligible is False


@pytest.mark.parametrize("missing_fixed", [False, True])
def test_invalid_analytical_weight_keeps_binding_precedence_and_delta_fallback(
    missing_fixed: bool,
) -> None:
    class InvalidWeight:
        def __float__(self) -> float:
            raise ValueError("weight is unavailable")

    calls: list[float] = []

    def response(x: float, scale: float) -> dict[str, float]:
        calls.append(x)
        return {"y": x * scale}

    nominal = {"x": 0.0} if missing_fixed else {"x": 0.0, "scale": 1.0}
    dispatcher = PropagationDispatcher(
        PropagationConfig(preferred_method="analytical", compute_sensitivity=False)
    )
    if missing_fixed:
        with pytest.raises(ValueError, match="scale"):
            dispatcher.propagate(
                response, nominal, {"x": _normal()}, ["y"], weights={"x": InvalidWeight()}
            )
        assert calls == []
    else:
        result = dispatcher.propagate(
            response, nominal, {"x": _normal()}, ["y"], weights={"x": InvalidWeight()}
        )[0]
        assert result.method_used is PropagationMethod.DELTA_METHOD and calls
        assert result.diagnostics["output_variance"] == pytest.approx(1.0, abs=1e-5)


def test_explicit_mc_does_not_interpret_unconsumed_analytical_weights() -> None:
    class UnconsumedWeight:
        def __float__(self) -> float:
            raise AssertionError("MC does not consume analytical weights")

    calls: list[float] = []

    def response(x: float) -> dict[str, float]:
        calls.append(x)
        return {"y": x}

    result = PropagationDispatcher(
        PropagationConfig(
            preferred_method="monte_carlo",
            mc_n_samples=100,
            mc_batch_size=100,
            compute_sensitivity=False,
        )
    ).propagate(response, {"x": 0.0}, {"x": _normal()}, ["y"], weights={"x": UnconsumedWeight()})[0]
    assert result.method_used is PropagationMethod.MONTE_CARLO and len(calls) == 101


@pytest.mark.parametrize("route", ["mc", "dispatcher_auto", "dispatcher_mc"])
def test_mc_does_not_interpret_std_metadata_unused_by_its_marginal_law(route: str) -> None:
    class MomentOnlyStd(float):
        def __float__(self) -> float:
            raise ValueError("moment std is unavailable")

    envelope = _normal({"std": MomentOnlyStd(1.0)})
    identity = _raw_identity(envelope)
    calls: list[float] = []

    def response(x: float) -> dict[str, float]:
        calls.append(x)
        return {"y": x}

    result = _propagate(route, response, {"x": 0.0}, {"x": envelope})[0]
    assert result.method_used is PropagationMethod.MONTE_CARLO
    assert len(calls) == 101 and result.diagnostics["n_valid"] == 100
    assert result.diagnostics["draw_outcome_provenance"]["sampling_recipe"][
        "input_envelope_sha256"
    ] == {"x": identity}


@pytest.mark.parametrize("missing_fixed", [False, True])
def test_deferred_moment_context_error_keeps_binding_and_actual_mc_fallback(
    missing_fixed: bool,
) -> None:
    class MomentOnlyStd(float):
        def __float__(self) -> float:
            raise ValueError("moment std is unavailable")

    calls: list[float] = []

    def response(x: float, scale: float) -> dict[str, float]:
        calls.append(x)
        return {"y": scale * x}

    dispatcher = PropagationDispatcher(
        PropagationConfig(mc_n_samples=100, mc_batch_size=100, compute_sensitivity=False)
    )
    nominal = {"x": 0.0} if missing_fixed else {"x": 0.0, "scale": 1.0}
    if missing_fixed:
        with pytest.raises(ValueError, match="scale"):
            dispatcher.propagate(
                response, nominal, {"x": _normal({"std": MomentOnlyStd(1.0)})}, ["y"]
            )
        assert calls == []
    else:
        result = dispatcher.propagate(
            response, nominal, {"x": _normal({"std": MomentOnlyStd(1.0)})}, ["y"]
        )[0]
        assert result.method_used is PropagationMethod.MONTE_CARLO
        assert result.diagnostics["n_valid"] == 100 and len(calls) >= 101


def _provenance_with_notes(notes: dict[str, object]) -> CompositionProvenance:
    step = CompositionStep(
        op="push_forward",
        stage_name="prior.domain.probe",
        input_flavours=(ComposedFlavour.ANALYTICAL,),
        output_flavour=ComposedFlavour.DELTA,
        assumptions=("measured",),
        notes=notes,
    )
    return CompositionProvenance(
        native_flavour=ComposedFlavour.ANALYTICAL,
        composed_flavour=ComposedFlavour.DELTA,
        exactness=ExactnessKind.APPROXIMATION,
        certificate_kind=CertificateKind.TAYLOR_REMAINDER,
        certificate_radius={"bound": 1.0},
        origin_envelope_ids=("prior-origin",),
        operator_history=(step,),
    )


def _run_provenance_domain_case(route: str, envelope: UncertaintyEnvelope, mutate):
    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            mutate()
            return Signature([Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)])

        def __call__(self, x: float) -> dict[str, float]:
            return {"y": x}

    if route == "mc":
        return _propagate(route, Evaluator(), {"x": 0.0}, {"x": envelope})[0]
    method = {"dispatcher_mc": "monte_carlo", "delta": "delta", "analytical": "analytical"}[route]
    return PropagationDispatcher(
        PropagationConfig(
            preferred_method=method,
            mc_n_samples=100,
            mc_batch_size=100,
            compute_sensitivity=False,
            delta_covariance_jitter=0.0,
        )
    ).propagate(
        Evaluator(),
        {"x": 0.0},
        {"x": envelope},
        ["y"],
        weights={"x": 1.0} if route == "analytical" else None,
    )[0]


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc", "delta", "analytical"])
def test_nested_datetime_and_containers_own_the_prior_wire_meaning(route: str) -> None:
    zone = _MutableTimezone()
    marker = ["before"]
    timestamp = datetime(2026, 10, 28, 12, tzinfo=zone)
    prior = _provenance_with_notes({"nested": {"events": [(timestamp, marker)]}})
    envelope = _normal().model_copy(update={"composition_provenance": prior})
    expected = prior.operator_history[0].model_dump(mode="json")
    original_digest = _raw_identity(envelope)
    assert original_digest is not None
    mutations = []

    def mutate() -> None:
        mutations.append(True)
        zone.minutes = 60
        marker.append("after")

    result = _run_provenance_domain_case(route, envelope, mutate)
    assert mutations
    assert result.envelope.gate_eligible is True
    history = result.envelope.composition_provenance
    assert history is not None
    assert history.operator_history[0].model_dump(mode="json") == expected
    event = history.operator_history[0].notes["nested"]["events"][0]
    assert isinstance(event, tuple)
    assert isinstance(event[0], datetime)
    assert event[1] == ["before"]
    if result.method_used is PropagationMethod.MONTE_CARLO:
        ledger = result.diagnostics["draw_outcome_provenance"]
        assert ledger["input_identity_status"] == "content_hashed"
        assert ledger["sampling_recipe"]["input_envelope_sha256"]["x"] == original_digest


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc", "delta", "analytical"])
@pytest.mark.parametrize("kind", ["mutable_enum", "mutable_time", "dict_subclass"])
@pytest.mark.parametrize("input_gate_eligible", [False, True])
def test_unsupported_provenance_context_is_declared_and_non_gating(
    route: str, kind: str, input_gate_eligible: bool
) -> None:
    class MutableEnum(Enum):
        VALUE = {"items": ["before"]}

    class MutableDict(dict):
        pass

    zone = _MutableTimezone()
    data = MutableDict({"items": ["before"]})
    value = {
        "mutable_enum": MutableEnum.VALUE,
        "mutable_time": time(12, tzinfo=zone),
        "dict_subclass": data,
    }[kind]
    prior = _provenance_with_notes({"nested": [(value,)]})
    envelope = _normal().model_copy(
        update={"composition_provenance": prior, "gate_eligible": input_gate_eligible}
    )
    original_digest = _raw_identity(envelope)
    assert original_digest is not None
    mutations = []

    def mutate() -> None:
        mutations.append(True)
        MutableEnum.VALUE.value["items"].append("after")
        zone.minutes = 60
        data["items"].append("after")

    result = _run_provenance_domain_case(route, envelope, mutate)
    assert mutations
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["provenance_context_status"] == "not_established"
    assert result.diagnostics["provenance_context_status"] == "not_established"
    assert result.diagnostics["input_identity_status"] == "not_established"
    assert result.envelope.metadata["input_provenance_history"] == "withheld_unowned"
    projected = result.envelope.composition_provenance
    assert projected is not None
    assert projected.origin_envelope_ids == ()
    assert len(projected.operator_history) == 1
    assert projected.operator_history[0].notes["input_provenance_history"] == "withheld_unowned"
    if result.method_used is PropagationMethod.MONTE_CARLO:
        ledger = result.diagnostics["draw_outcome_provenance"]
        assert ledger["input_identity_status"] == "not_established"
        assert ledger["sampling_recipe"]["input_envelope_sha256"]["x"] == original_digest


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc"])
def test_empirical_cache_owns_unvalidated_ndarray_before_signature_mutation(route: str) -> None:
    samples = np.array([2.0, 2.0], dtype=np.float64)
    carrier = PosteriorSamplesCarrier(samples=(2.0, 2.0), sample_axis="row").model_copy(
        update={"samples": samples}
    )
    envelope = _empirical().model_copy(update={"distribution_payload": carrier})
    calls: list[float] = []

    class Evaluator:
        @property
        def __signature__(self) -> Signature:
            samples[:] = 99.0
            return Signature([Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)])

        def __call__(self, x: float) -> dict[str, float]:
            calls.append(x)
            return {"y": x}

    result = _propagate(route, Evaluator(), {"x": 0.0}, {"x": envelope})[0]
    assert list(samples) == [99.0, 99.0]
    assert calls[0] == 0.0
    assert calls[1:] == [2.0] * 100
    assert result.envelope.point_estimate == pytest.approx(2.0)


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc", "delta", "analytical"])
def test_provenance_wire_drift_between_digest_and_preparation_cannot_gate(route: str) -> None:
    class ChangingTimezone(_MutableTimezone):
        def utcoffset(self, value: datetime | None) -> timedelta:
            offset = timedelta(minutes=self.minutes)
            self.minutes += 60
            return offset

    zone = ChangingTimezone()
    prior = _provenance_with_notes({"observed": datetime(2026, 10, 28, 12, tzinfo=zone)})
    envelope = _normal().model_copy(update={"composition_provenance": prior})
    result = _run_provenance_domain_case(route, envelope, lambda: None)
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["provenance_context_status"] == "not_established"
    assert result.diagnostics["input_identity_status"] == "not_established"


def test_analytical_missing_original_digest_cannot_gate() -> None:
    envelope = _normal({"opaque_extension": object()})
    assert _raw_identity(envelope) is None
    result = PropagationDispatcher(
        PropagationConfig(preferred_method="analytical", delta_covariance_jitter=0.0)
    ).propagate(lambda x: {"y": x}, {"x": 0.0}, {"x": envelope}, ["y"], weights={"x": 1.0})[0]
    assert result.method_used is PropagationMethod.ANALYTICAL
    assert result.envelope.gate_eligible is False
    assert result.diagnostics["input_identity_status"] == "not_established"


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc"])
def test_fixed_values_change_outputs_but_are_not_bound_by_the_envelope_recipe(route: str) -> None:
    envelope = _empirical().model_copy(
        update={
            "distribution_payload": PosteriorSamplesCarrier(samples=(2.0, 2.0), sample_axis="row")
        }
    )
    outputs = []
    recipes = []
    for scale in (2.0, 3.0):
        result = _propagate(
            route, lambda x, scale: {"y": x * scale}, {"x": 0.0, "scale": scale}, {"x": envelope}
        )[0]
        outputs.append(result.envelope.point_estimate)
        ledger = result.diagnostics["draw_outcome_provenance"]
        recipes.append(ledger["sampling_recipe"])
        assert ledger["input_identity_status"] == "not_established"
        assert result.envelope.gate_eligible is False
    assert outputs == pytest.approx([4.0, 6.0])
    assert recipes[0] == recipes[1]


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc", "delta", "analytical"])
def test_same_wire_dependency_cannot_support_conflicting_eligible_meaning(route: str) -> None:
    class Meaning(Enum):
        VALUE = "unknown"

        def __str__(self) -> str:
            return "known"

    original = _normal({"dependency": Meaning.VALUE})
    replay = UncertaintyEnvelope.model_validate(json.loads(original.model_dump_json()))
    assert _raw_identity(original) == _raw_identity(replay)
    observed: list[str] = []
    candidate = _run_provenance_domain_case(route, original, lambda: observed.append("called"))
    assert observed
    assert candidate.envelope.gate_eligible is False
    assert candidate.envelope.metadata["metadata_context_status"] == "not_established"
    assert candidate.diagnostics["input_identity_status"] == "not_established"
    observed.clear()
    replayed = _run_provenance_domain_case(route, replay, lambda: observed.append("called"))
    assert not observed
    assert replayed.envelope.gate_eligible is False
    assert replayed.envelope.metadata["failure"] == "unknown_dependency"


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc", "delta", "analytical"])
def test_canonical_json_metadata_still_allows_a_complete_input_gate(route: str) -> None:
    envelope = _normal({"dependency": "known", "detail": {"values": [1, "ok", True, None]}})
    result = _run_provenance_domain_case(route, envelope, lambda: None)
    assert result.envelope.gate_eligible is True
    assert "metadata_context_status" not in result.envelope.metadata


@pytest.mark.parametrize("route", ["delta", "analytical"])
def test_behavioral_numeric_metadata_with_same_wire_is_non_gating(route: str) -> None:
    class SemanticFloat(float):
        def __float__(self) -> float:
            return 3.0

    original = _normal({"std": SemanticFloat(1.0)})
    replay = UncertaintyEnvelope.model_validate(json.loads(original.model_dump_json()))
    assert _raw_identity(original) == _raw_identity(replay)
    candidate = _run_provenance_domain_case(route, original, lambda: None)
    canonical = _run_provenance_domain_case(route, replay, lambda: None)
    assert candidate.diagnostics["output_variance"] == pytest.approx(9.0, abs=1e-5)
    assert canonical.diagnostics["output_variance"] == pytest.approx(1.0, abs=1e-5)
    assert candidate.envelope.gate_eligible is False
    assert candidate.envelope.metadata["metadata_context_status"] == "not_established"
    assert canonical.envelope.gate_eligible is True


@pytest.mark.parametrize("route", ["mc", "dispatcher_mc", "delta", "analytical"])
def test_unconsumed_nested_behavioral_metadata_cannot_grant_a_context_gate(route: str) -> None:
    class Extension(Enum):
        VALUE = "ordinary-wire-text"

    envelope = _normal({"extension": {"nested": [Extension.VALUE]}})
    assert _raw_identity(envelope) is not None
    result = _run_provenance_domain_case(route, envelope, lambda: None)
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["metadata_context_status"] == "not_established"


def test_cross_envelope_serialization_mutation_breaks_metadata_wire_binding() -> None:
    first = _normal({"detail": {"values": [1]}})
    values = first.metadata["detail"]["values"]

    class MutatingTimezone(_MutableTimezone):
        def utcoffset(self, value: datetime | None) -> timedelta:
            values.append(2)
            return timedelta(0)

    second = _normal().model_copy(
        update={
            "composition_provenance": _provenance_with_notes(
                {"observed": datetime(2026, 10, 28, 12, tzinfo=MutatingTimezone())}
            )
        }
    )
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, mc_batch_size=100, compute_sensitivity=False)
    ).propagate(lambda a, b: {"y": a + b}, {"a": 0.0, "b": 0.0}, {"a": first, "b": second}, ["y"])[
        0
    ]
    assert len(values) > 1
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["metadata_context_status"] == "not_established"
    assert (
        result.diagnostics["draw_outcome_provenance"]["input_identity_status"] == "not_established"
    )
