from __future__ import annotations

import logging

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def test_propagate_uncertainty_node_updates_simulation_result(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_prop")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.propagate"))

    env_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=1.0,
            confidence_interval=(0.8, 1.2),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.TRUST,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )

    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=state_snapshot_ref,
            uncertainty_envelope_ref=env_ref,
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
        Metrics(values={"applied_nodes": 1, "step_latency_ms": 12}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_prop",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id),
        },
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref,
        },
        params={
            "propagation_mc_n_samples": 100,
            "propagation_mc_batch_size": 100,
            "propagation_sensitivity": {
                "applied_nodes": {"data_snapshot": 1.0},
                "step_latency_ms": {"data_snapshot": 1.0},
            },
        },
    )

    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"

    updated_sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    payload = from_canonical_bytes(store.get_bytes(updated_sim_ref.artifact_id))
    updated_sim = SimulationResult.model_validate(payload)

    assert updated_sim.uncertainty_envelopes is not None
    assert set(updated_sim.uncertainty_envelopes.keys()) == {"applied_nodes", "step_latency_ms"}
    assert ARTIFACT_PROPAGATION_REPORT_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["methods"] == [PropagationMethod.DELTA_METHOD.value] * 2


def _posterior_node_fixture(tmp_path, draws, *, weights=None, mutation=None):
    from copy import deepcopy

    from polisyos.core import artifacts as core_artifacts
    from polisyos.core import canon as core_canon
    from polisyos.foundry.calibration import uncertainty_adapter
    from polisyos.foundry.calibration.report import (
        CalibrationReport,
        put_calibration_config,
        put_calibration_report,
    )
    from polisyos.ir import CalibrationConfig
    from polisyos.ir.analytics import PosteriorParameterBinding, PosteriorSummaryContext
    from polisyos.scientist.nodes.builtins.state_keys import INPUT_CALIBRATION_REPORT_REF

    store = FileSystemCAS(tmp_path)
    source = store.put_json(
        {"draws": draws, "weights": weights},
        PutOptions(kind="test.posterior_input", media_type="application/json"),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    context = PosteriorSummaryContext(
        parameters={
            name: PosteriorParameterBinding(
                estimand_id=f"finite:{name}", unit="score", scale="linear"
            )
            for name in draws
        },
        lineage_refs={"source": source.model_dump(include={"artifact_id", "kind", "media_type"})},
        purpose="finite_fixture_predictive",
    )
    summary = uncertainty_adapter.summarize_bayesian_calibration_posterior(
        draws,
        weights=weights,
        context=context,
        draw_ids=[f"source-row:{i}" for i in range(len(next(iter(draws.values()))))],
    )
    envelopes = dict(summary.parameter_envelopes)
    if mutation == "consistent_joint":
        for name, env in envelopes.items():
            payload = deepcopy(env.model_dump(mode="python"))
            payload["metadata"]["posterior_summary_profile"]["joint_law_sha256"] = "0" * 64
            payload["metadata"]["joint_law_sha256"] = "0" * 64
            payload["metadata"]["joint_sample_id"] = "0" * 64
            envelopes[name] = UncertaintyEnvelope.model_validate(payload)
    elif mutation is not None and mutation != "incomplete_joint":
        first = sorted(envelopes)[0]
        payload = deepcopy(envelopes[first].model_dump(mode="python"))
        if mutation == "mean":
            payload["metadata"]["posterior_summary_profile"]["posterior_mean"] = 999.0
        elif mutation == "profile":
            payload["metadata"]["posterior_summary_profile"]["profile_id"] = "unknown"
        elif mutation == "carrier":
            payload["distribution_payload"] = None
        elif mutation == "rows":
            payload["distribution_payload"]["samples"] = tuple(
                reversed(payload["distribution_payload"]["samples"])
            )
        elif mutation == "rename":
            envelopes = {"wrong_target": envelopes[first]}
        elif mutation in {"raw_bool", "raw_string", "inline_bool", "inline_string"}:
            pass
        else:
            payload["metadata"]["joint_law_sha256"] = "0" * 64
        if mutation != "rename" and mutation not in {
            "raw_bool",
            "raw_string",
            "inline_bool",
            "inline_string",
        }:
            envelopes[first] = UncertaintyEnvelope.model_validate(payload)
    refs = {name: persist_uncertainty_envelope(store, env) for name, env in envelopes.items()}
    if mutation == "incomplete_joint":
        refs.pop(sorted(refs)[-1])
    if mutation in {"raw_bool", "raw_string"}:
        from polisyos.ir.registry.refs import UncertaintyEnvelopeRef

        first = sorted(envelopes)[0]
        raw = envelopes[first].model_dump(mode="json")
        raw["distribution_payload"]["samples"][1] = True if mutation == "raw_bool" else "1.0"
        record = store.put_json(
            raw,
            PutOptions(
                kind="ir.uncertainty_envelope",
                media_type="application/json",
                schema=SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
            ),
            canon_spec=core_canon.CanonSpec(forbid_floats=False),
        )
        assert store.verify(record).ok
        refs[first] = UncertaintyEnvelopeRef.model_validate(
            record.model_dump(include={"artifact_id", "kind", "media_type"})
        )
    config = put_calibration_config(store, CalibrationConfig())
    report_ref = put_calibration_report(
        store,
        CalibrationReport(
            total_loss=0,
            calibrated_params=summary.posterior_means,
            uncertainty_envelope_refs=refs,
        ),
        inputs=[core_artifacts.InputRef(artifact_id=config.artifact_id, role="calibration_config")],
    )
    if mutation in {"inline_bool", "inline_string"}:
        raw_report = CalibrationReport(
            total_loss=0, calibrated_params=summary.posterior_means, uncertainty_envelopes=envelopes
        ).model_dump(mode="json")
        raw_report["uncertainty_envelopes"][sorted(envelopes)[0]]["distribution_payload"][
            "samples"
        ][1] = True if mutation == "inline_bool" else "1.0"
        report_ref = store.put_json(
            raw_report,
            PutOptions(
                kind="foundry.calibration_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.foundry.CalibrationReport", version="2.0"),
                inputs=[
                    core_artifacts.InputRef(
                        artifact_id=config.artifact_id, role="calibration_config"
                    )
                ],
            ),
            canon_spec=core_canon.CanonSpec(forbid_floats=False, exclude_none=False),
        )
        assert store.verify(report_ref).ok
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="posterior_native")
    metrics = store.put_json(
        Metrics(values={"y": 0.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    plan = store.put_json(
        {"program_ref": metrics.model_dump(mode="json"), "order": []},
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    sim = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    # The actual consumer uses a fresh instance of the same configured CAS.
    fresh = FileSystemCAS(tmp_path)
    ctx = ExecutionContext(store=fresh, run=run, logger=logging.getLogger("posterior.native"))
    state = ExperimentState(
        run_id="posterior_native",
        inputs={INPUT_CALIBRATION_REPORT_REF: report_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim},
        params={
            "propagation_config": {
                "preferred_method": "monte_carlo",
                "mc_n_samples": 256,
                "mc_sampling_method": "sobol",
                "mc_qmc_scramble": False,
                "compute_sensitivity": False,
            },
            "propagation_sensitivity": {
                "y": {name: 1.0 if i == 0 else -1.0 for i, name in enumerate(sorted(draws))}
            },
        },
    )
    return ctx, state, refs


@pytest.mark.parametrize("sign,expected_variance", [(1, 0.0), (-1, 4.0)])
def test_real_posterior_producer_fresh_node_preserves_joint_rows(tmp_path, sign, expected_variance):
    from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope

    ctx, state, refs = _posterior_node_fixture(tmp_path, {"a": [-1, 1], "b": [-sign, sign]})
    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    fresh = FileSystemCAS(tmp_path)
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(
            fresh.get_bytes(
                outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id
            )
        )
    )
    output = load_uncertainty_envelope(fresh, simulation.uncertainty_envelopes["y"])
    assert len(output.distribution_payload.samples) == 256
    assert np.var(output.distribution_payload.samples) == expected_variance
    assert set(output.distribution_payload.samples) == ({0.0} if sign == 1 else {-2.0, 2.0})
    assert not output.gate_eligible
    assert set(refs) == {"a", "b"}


def test_actual_node_reads_named_mean_instead_of_generic_median(tmp_path):
    from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope

    ctx, state, _ = _posterior_node_fixture(tmp_path, {"x": [0] * 99 + [100]})
    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    fresh = FileSystemCAS(tmp_path)
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(
            fresh.get_bytes(
                outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id
            )
        )
    )
    output = load_uncertainty_envelope(fresh, simulation.uncertainty_envelopes["y"])
    # y is centered at the independently named posterior mean, not median0.
    assert set(output.distribution_payload.samples) == {-1.0, 99.0}


@pytest.mark.parametrize(
    "mutation",
    [
        "mean",
        "profile",
        "carrier",
        "rows",
        "digest",
        "consistent_joint",
        "rename",
        "raw_bool",
        "raw_string",
        "inline_bool",
        "inline_string",
    ],
)
def test_actual_node_refuses_forged_profile_before_evaluator(tmp_path, monkeypatch, mutation):
    from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node

    ctx, state, _ = _posterior_node_fixture(tmp_path, {"x": [0, 1, 4]}, mutation=mutation)
    calls = []
    monkeypatch.setattr(
        node,
        "_build_propagation_fn",
        lambda *a, **kw: calls.append(kw)
        or pytest.fail("invalid profile reached evaluator builder"),
    )
    with pytest.raises(ValueError):
        PropagateUncertaintyNode().execute(ctx, state)
    assert calls == []


def test_multicoordinate_profile_digest_and_missing_projection_refuse_before_builder(
    tmp_path, monkeypatch
):
    from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node

    calls = []
    monkeypatch.setattr(
        node,
        "_build_propagation_fn",
        lambda *args, **kwargs: calls.append(kwargs) or pytest.fail("joint admission removed"),
    )
    for case in ("consistent_joint", "incomplete_joint"):
        ctx, state, _ = _posterior_node_fixture(
            tmp_path / case,
            {"a": [-1, 1], "b": [-1, 1]},
            mutation=case,
        )
        with pytest.raises(ValueError, match="joint"):
            PropagateUncertaintyNode().execute(ctx, state)
    assert calls == []


def test_posterior_canonical_ir_store_adapter_transport(tmp_path, monkeypatch):
    from polisyos.core.artifacts import ir_adapter
    from polisyos.ir.analytics import load_posterior_summary_envelope, posterior_nominal_mean

    _, _, refs = _posterior_node_fixture(tmp_path, {"x": [0, 1]})
    adapter = ir_adapter.CoreToIRArtifactStoreAdapter(FileSystemCAS(tmp_path))
    readback = load_posterior_summary_envelope(adapter, refs["x"])
    assert persist_uncertainty_envelope(adapter, readback) == refs["x"]
    assert posterior_nominal_mean(readback, parameter_name="x") == 0.5

    original = ir_adapter.CoreToIRArtifactStoreAdapter.get_bytes
    reads, callbacks = [], []

    def forged_bytes(self, artifact_id):
        payload = original(self, artifact_id)
        if str(artifact_id) == str(refs["x"].artifact_id):
            reads.append(str(artifact_id))
            return payload + b" "  # Valid JSON, identical law/profile; wrong exact content digest.
        return payload

    monkeypatch.setattr(ir_adapter.CoreToIRArtifactStoreAdapter, "get_bytes", forged_bytes)

    def named_consumer():
        decoded = load_posterior_summary_envelope(adapter, refs["x"])
        callbacks.append(posterior_nominal_mean(decoded, parameter_name="x"))

    with pytest.raises(ValueError, match="CAS kind/schema/content"):
        named_consumer()
    assert reads == [str(refs["x"].artifact_id)]
    assert callbacks == []
