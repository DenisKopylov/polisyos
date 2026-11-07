"""UQP-01 witnesses for typed uncertainty failures and report persistence."""

from __future__ import annotations

import logging
from statistics import NormalDist

import jax
import jax.numpy as jnp
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.delta import DeltaMethodPropagator
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

pytestmark = pytest.mark.unit


def _normal_env(point: float, std: float) -> UncertaintyEnvelope:
    """Build a small Gaussian input envelope for propagation witnesses."""
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - 1.96 * std, point + 1.96 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


@pytest.mark.parametrize(
    ("method", "sampling"),
    [("delta", "random"), ("auto", "random"), ("monte_carlo", "random"), ("monte_carlo", "sobol")],
)
def test_native_complete_invocation_keeps_fixed_scale_across_backends(
    method: str, sampling: str
) -> None:
    """Actual probe, nominal and sampled calls all retain the same fixed input."""
    calls: list[tuple[float, float]] = []

    def evaluate(x: float, scale: float) -> dict[str, float]:
        if not isinstance(x, jax.core.Tracer):
            calls.append((float(x), scale))
        return {"y": x * scale}

    z = NormalDist().inv_cdf(0.975)
    envelope = UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(10.0 - z, 10.0 + z),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=False,
    )
    result = PropagationDispatcher(
        PropagationConfig(
            preferred_method=method,
            mc_sampling_method=sampling,
            mc_n_samples=128,
            mc_batch_size=128,
            mc_seed=17,
            delta_covariance_jitter=0.0,
        )
    ).propagate(evaluate, {"x": 10.0, "scale": 2.0}, {"x": envelope}, ["y"])[0]

    assert calls and all(scale == 2.0 for _, scale in calls)
    assert any(x == 10.0 for x, _ in calls)
    if method in {"delta", "auto"}:
        assert result.method_used is PropagationMethod.DELTA_METHOD
        assert result.envelope.point_estimate == 20.0
        assert result.envelope.metadata["output_std"] ** 2 == pytest.approx(4.0, rel=1e-5)
    else:
        assert result.method_used is PropagationMethod.MONTE_CARLO
        assert result.envelope.point_estimate == pytest.approx(20.0, abs=0.7)
        assert result.envelope.sample_size == 128


@pytest.mark.parametrize("method", ["delta", "auto"])
@pytest.mark.parametrize(("fit_mean", "fit_std"), [(10.0, 1.0), (42.0, 0.0)])
def test_typed_normal_uses_sampling_law_with_fixed_inputs(
    method: str, fit_mean: float, fit_std: float
) -> None:
    """A typed fit is sampled instead of being replaced by nominal or CI moments."""
    calls: list[tuple[float, float]] = []

    def evaluate(x: float, scale: float) -> dict[str, float]:
        if not isinstance(x, jax.core.Tracer):
            calls.append((float(x), scale))
        return {"y": x * scale}

    envelope = _normal_env(10.0, 1.0).model_copy(
        update={
            "distribution_payload": ParametricFitCarrier(
                family=DistributionFamily.NORMAL,
                parameters={"mean": fit_mean, "std": fit_std},
            ),
            "gate_eligible": False,
        }
    )
    result = PropagationDispatcher(
        PropagationConfig(
            preferred_method=method,
            mc_n_samples=128,
            mc_batch_size=128,
            mc_seed=17,
        )
    ).propagate(evaluate, {"x": 10.0, "scale": 2.0}, {"x": envelope}, ["y"])[0]

    assert result.method_used is PropagationMethod.MONTE_CARLO
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["parametric_fit_payload_used"] is True
    assert result.envelope.sample_size == 128
    assert calls and all(scale == 2.0 for _, scale in calls)
    assert any(x == 10.0 for x, _ in calls)
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    if fit_std == 0.0:
        assert any(x == 42.0 for x, _ in calls)
        assert result.envelope.point_estimate == 84.0
        assert set(payload.samples) == {84.0}
    else:
        assert min(payload.samples) < 20.0 < max(payload.samples)


def test_native_zero_baseline_affine_and_real_nondifferentiable_fallback() -> None:
    """An exact zero response is not missing, and a real JAX refusal still falls back."""
    import math

    def affine(x: float) -> dict[str, float]:
        return {"y": x - 2.0}

    derivative = jax.jacfwd(lambda x: affine(x)["y"])
    assert float(derivative(jnp.asarray(2.0))) == 1.0
    assert float(jax.jit(derivative)(jnp.asarray(2.0))) == 1.0
    config = PropagationConfig(
        preferred_method="auto",
        mc_n_samples=128,
        mc_batch_size=128,
        mc_seed=17,
        delta_covariance_jitter=0.0,
    )
    result = PropagationDispatcher(config).propagate(
        affine, {"x": 2.0}, {"x": _normal_env(2.0, 1.0)}, ["y"]
    )[0]
    assert result.method_used is PropagationMethod.DELTA_METHOD
    assert result.envelope.point_estimate == 0.0
    assert result.envelope.metadata["output_std"] == pytest.approx(1.0, rel=1e-4)

    def non_jax(x: float) -> dict[str, float]:
        return {"y": math.sin(float(x))}

    fallback = PropagationDispatcher(config).propagate(
        non_jax, {"x": 2.0}, {"x": _normal_env(2.0, 0.1)}, ["y"]
    )[0]
    assert fallback.method_used is PropagationMethod.MONTE_CARLO
    assert fallback.envelope.sample_size == 128


def test_mc_missing_output_is_unknown_while_true_zero_remains_valid() -> None:
    """A missing MC metric cannot become an authoritative zero by fallback."""
    config = PropagationConfig(
        mc_n_samples=100,
        mc_batch_size=100,
        mc_min_valid_samples=50,
        mc_seed=17,
    )
    inputs = {"x": _normal_env(0.0, 1.0)}
    propagator = MonteCarloPropagator(config)

    missing = propagator.propagate(
        lambda **params: {"other": params["x"]},
        {"x": 0.0},
        inputs,
        ["missing"],
    )[0].envelope
    genuine_zero = propagator.propagate(
        lambda **params: {"zero": 0.0},
        {"x": 0.0},
        inputs,
        ["zero"],
    )[0].envelope

    assert missing.point_estimate == 0.0
    assert missing.distribution_family is DistributionFamily.UNKNOWN
    assert missing.confidence_level is None
    assert missing.confidence_interval != (0.0, 0.0)
    assert missing.gate_eligible is False
    assert missing.metadata["failure"] == "missing_output"
    assert missing.metadata["missing_output_count"] == 100

    assert genuine_zero.point_estimate == pytest.approx(0.0)
    assert genuine_zero.confidence_interval == (0.0, 0.0)
    assert genuine_zero.distribution_family is DistributionFamily.BOOTSTRAP
    assert genuine_zero.sample_size == 100
    assert genuine_zero.gate_eligible is True


@pytest.mark.parametrize("propagator_type", [DeltaMethodPropagator, MonteCarloPropagator])
def test_effective_inputs_refuse_missing_fixed_parameter_before_evaluation(
    propagator_type: type[DeltaMethodPropagator] | type[MonteCarloPropagator],
) -> None:
    """An unresolved fixed input fails once, before nominal or sampled evaluation."""
    calls = 0

    def requires_fixed(x: float, c: float) -> dict[str, float]:
        nonlocal calls
        calls += 1
        return {"y": x + 5.0 * c}

    with pytest.raises(ValueError, match="required parameters unresolved: c"):
        propagator_type(PropagationConfig(mc_n_samples=100)).propagate(
            requires_fixed,
            {"x": 1.0},
            {"x": _normal_env(1.0, 0.1)},
            ["y"],
        )

    assert calls == 0


@pytest.mark.parametrize("propagator_type", [DeltaMethodPropagator, MonteCarloPropagator])
@pytest.mark.parametrize(
    ("nominal", "expected"),
    [({"x": 1.0}, 36.0), ({"x": 1.0, "c": 0.0}, 1.0)],
)
def test_effective_inputs_distinguish_callable_default_from_explicit_zero(
    propagator_type: type[DeltaMethodPropagator] | type[MonteCarloPropagator],
    nominal: dict[str, float],
    expected: float,
) -> None:
    """An intentional nonzero default and an explicit zero remain distinct fixed inputs."""

    def defaulted_fixed(x: float, c: float = 7.0) -> dict[str, float]:
        return {"y": x + 5.0 * c}

    result = propagator_type(
        PropagationConfig(mc_n_samples=200, mc_batch_size=200, mc_seed=43)
    ).propagate(
        defaulted_fixed,
        nominal,
        {"x": _normal_env(1.0, 0.01)},
        ["y"],
    )[0]

    assert result.envelope.point_estimate == pytest.approx(expected, abs=0.05)


def test_partial_node_persists_limitation_and_disables_gate(tmp_path) -> None:
    """The node consumer persists unresolved mapping and its non-authoritative gate."""
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_uqp01")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.uqp01"))

    input_envelope_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store),
        _normal_env(1.0, 0.1),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=state_snapshot_ref,
            uncertainty_envelope_ref=input_envelope_ref,
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"mapped": 1, "unmapped": 2}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    simulation_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_uqp01",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(
                artifact_id=data_snapshot_ref.artifact_id,
            ),
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_result_ref},
        params={
            "propagation_sensitivity": {"mapped": {"data_snapshot": 1.0}},
        },
    )

    outcome = PropagateUncertaintyNode().execute(ctx, state)

    assert outcome.status == "ok"
    report_ref = outcome.state.artifacts_index["propagation_report_ref"]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["mapping_status"] == "partial"
    assert report["unmapped_metric_ids"] == ["unmapped"]
    assert report["diagnostics"][-1]["metric_id"] == "unmapped"
    assert report["diagnostics"][-1]["diagnostics"]["sensitivity_mapping"] == "unresolved"

    updated_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_payload = from_canonical_bytes(store.get_bytes(updated_ref.artifact_id))
    updated_simulation = SimulationResult.model_validate(updated_payload)
    unresolved_ref = updated_simulation.uncertainty_envelopes["unmapped"]
    unresolved = load_uncertainty_envelope(_ensure_ir_artifact_store(store), unresolved_ref)
    assert unresolved.metadata["sensitivity_mapping"] == "unresolved"
    assert unresolved.gate_eligible is False
