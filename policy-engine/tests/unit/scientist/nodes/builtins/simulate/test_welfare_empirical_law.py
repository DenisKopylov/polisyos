"""Exercise declared empirical laws through the actual Welfare GE node."""

from __future__ import annotations

import logging
from copy import deepcopy

import numpy as np
import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    PosteriorSamplesCarrier,
    QuantileSummaryCarrier,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import load_welfare_bundle
from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as module
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _envelope(samples=(0.0, 1.0), weights=(3.0, 1.0)):
    return UncertaintyEnvelope(
        numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
        point_estimate=0.25,
        confidence_interval=(0.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.ENSEMBLE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        distribution_payload=PosteriorSamplesCarrier(
            samples=samples, weights=weights, sample_axis="fixture_row"
        ),
    )


def _native_fixture(tmp_path, envelope=None, *, run_id="native_welfare_atoms"):
    """Supply operational artifacts while keeping the GE evaluator completely native."""
    store = FileSystemCAS(tmp_path)
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(run_id))
    placeholder = store.put_json(
        {}, PutOptions(kind="test.operational", media_type="application/json")
    )
    plan = store.put_json(
        {"program_ref": placeholder.model_dump(mode="json"), "order": []},
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics = store.put_json(
        Metrics(values={"response": 2.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    simulation = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    env = envelope if envelope is not None else _envelope()
    env_ref = persist_uncertainty_envelope(store, env)
    state = ExperimentState(
        run_id=run_id,
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation},
        params={
            "welfare_config": {
                "metric_order": ["response"],
                "pe_response": [2.0],
                "weights": [1.0],
                "ge_technical_coefficients": [[0.25]],
                "ge_entry_map": {"A": [0, 0]},
                "input_envelopes": {"A": env_ref.model_dump(mode="json")},
                "credible_method": "monte_carlo",
            },
            "propagation_config": {
                "mc_n_samples": 128,
                "mc_min_valid_samples": 10,
                "mc_seed": 31415,
            },
        },
    )
    return ctx, state, env_ref


def _run_native(tmp_path, envelope=None):
    ctx, state, env_ref = _native_fixture(tmp_path, envelope)
    outcome = module.PropagateWelfareNode().execute(ctx, state)
    assert outcome.status == "ok", outcome.error
    # Consumer uses a new store instance, not the producer's live objects.
    fresh = FileSystemCAS(tmp_path)
    bundle = load_welfare_bundle(fresh, outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF])
    receipt = module._load_welfare_draw_outcomes(
        fresh, module.ArtifactRef.model_validate(bundle.diagnostics["draw_outcomes_ref"])
    )
    samples = module._load_verified_welfare_samples(fresh, bundle.sample_bundle_ref)
    return fresh, bundle, receipt, samples, env_ref


def test_native_ge_preserves_empirical_atoms_failed_support_and_conditional_values(tmp_path):
    _, bundle, receipt, samples, _ = _run_native(tmp_path)
    uniforms = np.random.default_rng(31415).random(128)
    expected_rows = (uniforms >= 0.75).astype(int).tolist()
    values = [row["sampled_input"]["A"] for row in receipt["sampled_inputs"]]
    assert values == [float(row) for row in expected_rows]
    assert receipt["attempted_draw_count"] == receipt["requested_draw_count"] == 128
    assert receipt["failed_draw_count"] == sum(expected_rows)
    assert receipt["successful_draw_count"] == 128 - sum(expected_rows)
    assert receipt["support_complete"] is False
    assert receipt["gate_eligible"] is False
    assert all(
        failure["error_type"] == "LinAlgError"
        for record in receipt["failure_records"]
        for failure in record["output_outcomes"]
    )
    assert samples.welfare_draws == (2.0,) * (128 - sum(expected_rows))
    assert samples.welfare_pe_draws == samples.welfare_draws
    assert samples.welfare_ge_draws == (0.0,) * len(samples.welfare_draws)
    assert samples.metadata["estimate_scope"] == "conditional_on_all_outputs_finite"
    assert bundle.credible_interval is None
    assert bundle.diagnostics["successful_draw_count"] == len(samples.welfare_draws)


def test_native_ge_preserves_tiny_and_zero_mass_atoms_and_complete_positive_law(tmp_path):
    _, bundle, receipt, samples, _ = _run_native(
        tmp_path, _envelope((0.0, 1e-15, 0.5), (1.0, 0.0, 3.0))
    )
    inputs = [row["sampled_input"]["A"] for row in receipt["sampled_inputs"]]
    assert set(inputs) == {0.0, 0.5}
    assert receipt["support_complete"] is True
    assert receipt["failed_draw_count"] == 0
    assert set(samples.welfare_draws) == {2.0, 4.0}
    assert bundle.credible_interval == (2.0, 4.0)


@pytest.mark.parametrize(
    "envelope",
    [
        _envelope().model_copy(update={"distribution_payload": None}),
        _envelope().model_copy(
            update={"distribution_payload": QuantileSummaryCarrier(quantiles={"0.5": 0.25})}
        ),
        _envelope((0.0, 1.0), (0.0, 0.0)),
        _envelope((0.0, 1.0), (1.0, 1e-320)),
    ],
)
def test_unsupported_law_refuses_before_native_nominal_or_draw_callbacks(
    tmp_path, monkeypatch, envelope
):
    ctx, state, _ = _native_fixture(tmp_path, envelope)
    calls = []
    original = module._build_simulation_fn

    def observe(*args, **kwargs):
        function, *rest = original(*args, **kwargs)

        def counted(**params):
            calls.append(params)
            return function(**params)

        return counted, *rest

    monkeypatch.setattr(module, "_build_simulation_fn", observe)
    outcome = module.PropagateWelfareNode().execute(ctx, state)
    assert calls == []
    assert outcome.status == "fail"
    assert outcome.error.code == "ERROR_WELFARE_INPUT_LAW_UNSUPPORTED"
    assert outcome.error.details["law_status"] == "unknown"
    assert outcome.error.details["gate_eligible"] is False


def test_native_ge_receipt_binds_exact_carrier_rows_and_weights(tmp_path):
    fresh, bundle, receipt, _, env_ref = _run_native(tmp_path)
    original_manifest = fresh.get_manifest(bundle.diagnostics["draw_outcomes_ref"]["artifact_id"])
    law = receipt["empirical_input_laws"]["A"]
    assert law["envelope_ref"]["artifact_id"] == env_ref.artifact_id
    assert law["sample_axis"] == "fixture_row"
    assert [row["row_index"] for row in receipt["empirical_rows"]] == (
        np.random.default_rng(31415).random(128) >= 0.75
    ).astype(int).tolist()
    for corruption in ("row", "weights", "axis", "digest", "removed_rows"):
        fake = deepcopy(receipt)
        if corruption == "row":
            fake["empirical_rows"][0]["row_index"] ^= 1
        elif corruption == "weights":
            fake["empirical_input_laws"]["A"]["probabilities"] = [0.5, 0.5]
        elif corruption == "axis":
            fake["empirical_input_laws"]["A"]["sample_axis"] = "other_axis"
        elif corruption == "digest":
            fake["empirical_input_laws"]["A"]["carrier_sha256"] = "0" * 64
        else:
            fake["empirical_rows"].pop()
        ref = fresh.put_json(
            fake,
            PutOptions(
                kind="foundry.welfare_draw_outcomes",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.foundry.WelfareDrawOutcomes", version="1.0"),
                inputs=original_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        assert fresh.verify(ref).ok
        with pytest.raises(ValueError):
            module._load_welfare_draw_outcomes(FileSystemCAS(tmp_path), ref)
