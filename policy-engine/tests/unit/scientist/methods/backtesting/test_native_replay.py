"""Default Scientist/Foundry replay controls with a known fiscal transition."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.ir.analytics.backtest import BacktestReport
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import EnvironmentParam, ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource


def _fixture(tmp_path, *, count=3):
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store)
    history = {
        "income": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["t0", "t1", "t2", "t3"],
        "row_ids": ["r0", "r1", "r2", "r3"],
    }
    data = store.put_json(
        history,
        PutOptions(kind="test.historical_rows", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    snapshot = store.put_json(
        DataSnapshot(data_ref=data),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    model = ModelSpec(
        model_id="fiscal_model",
        data_snapshot_ref=str(snapshot.artifact_id),
        registry_bundle_ref=str(registry.bundle_ref.artifact_id),
    )
    policy = PolicySpec(
        policy_id="tax_policy",
        interventions=[
            InterventionSpec(
                intervention_id="tax",
                kind="income_tax",
                target={
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": 0,
                },
                schedule={"start_step": 0, "duration_steps": 2},
                params={"rate": Decimal("0.25")},
            )
        ],
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="predictive_fixture", domain=ProblemDomain.FISCAL),
        policy_spec=policy,
        model_spec=model,
    )
    trinity_ref = store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
        ),
    )
    state = {
        "run_id": "native-fiscal",
        "inputs": {
            "trinity_bundle_ref": trinity_ref.model_dump(mode="json"),
            "registry_bundle_ref": registry.bundle_ref.model_dump(mode="json"),
            "data_snapshot_ref": snapshot.model_dump(mode="json"),
        },
        "params": {
            "workflow_id": "scientist_default",
            "foundry_input_binding_rules": [
                {
                    "binding_id": "income",
                    "source_path": "income.1",
                    "target_slot_id": "agents.income",
                },
                {
                    "binding_id": "reported_income",
                    "source_path": "income.1",
                    "target_slot_id": "agents.reported_income",
                },
            ],
            "backtest_native_forecast": {
                "purpose": "predictive_simulation",
                "origin": "t2",
                "time_index": ["t2", "t3"],
                "history_columns": ["income"],
                "targets": [
                    {
                        "metric": "income",
                        "slot_id": "agents.income",
                        "unit_id": "usd",
                        "reduction": "mean",
                    }
                ],
            },
        },
    }
    plan = HistoricalValidationPlan(
        plan_id="native",
        historical_data_ref=str(data.artifact_id),
        intervention_date="t2",
        intervention_step=2,
        ground_truth_outcomes={"income": [1.5, 1.0]},
        prediction_source=PredictionSource.SCIENTIST,
        scientist_state=state,
        n_simulation_runs=count,
        random_seed=12,
    )
    return store, plan


@pytest.mark.parametrize("count", [1, 7])
def test_default_native_forecast_replays_consume_masked_rows_and_actual_seeds(
    tmp_path, monkeypatch, count
):
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.methods.backtesting.native_replay import load_native_forecast

    store, plan = _fixture(tmp_path, count=count)
    calls = []
    native_execute = DefaultFoundryPort.execute

    def observe(port, actual_store, request):
        assert actual_store.root == store.root
        calls.append(request)
        return native_execute(port, actual_store, request)

    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    report = BacktestOrchestrator(cas=store).run([plan])
    # Reopen the public persisted report and its CAS using fresh reader instances.
    store = FileSystemCAS(tmp_path / "cas")
    report = BacktestReport.model_validate(
        from_canonical_bytes(store.get_bytes(report.cas_artifact_id))
    )
    assert report.prediction_mode_effective == "scientist", report.degraded_reasons
    assert {
        key: report.metadata["replay_denominators"][0][key]
        for key in ["requested", "attempted", "completed", "failed"]
    } == {"requested": count, "attempted": count, "completed": count, "failed": 0}
    assert len(calls) == 2 * count
    for scenario in report.scenarios:
        assert [row.y_pred for row in scenario.outcome_comparisons] == pytest.approx([1.5, 1.0])
        assert scenario.metadata["native_forecast_ref"]
        snapshot = from_canonical_bytes(
            store.get_bytes(scenario.metadata["historical_snapshot_ref"]["artifact_id"])
        )
        rows = from_canonical_bytes(store.get_bytes(snapshot["data_ref"]["artifact_id"]))
        assert rows["income"] == [1.0, 2.0]
        assert rows["row_ids"] == ["r0", "r1"]
        assert rows["time_index"] == ["t0", "t1"]
        forecast, request = load_native_forecast(
            store,
            ArtifactRef.model_validate(scenario.metadata["native_forecast_ref"]),
            ArtifactRef.model_validate(scenario.metadata["native_request_ref"]),
        )
        assert forecast.values == {"income": [1.5, 1.0]}
        assert request.profile.purpose == "predictive_simulation"
        assert request.profile.time_index == ["t2", "t3"]
        assert request.row_ids == ["r0", "r1"]
        assert request.seed == scenario.metadata["actual_foundry_seed"]
        actual_calls = [call for call in calls if call.exec_config.seed == request.seed]
        assert len(actual_calls) == 2
        assert [call.input_bindings_ref.model_dump(mode="json") for call in actual_calls] == [
            ref.model_dump(mode="json") for ref in forecast.execution_bindings_refs
        ]
        child = TrinityBundle.model_validate(
            from_canonical_bytes(store.get_bytes(request.trinity_bundle_ref))
        )
        assert child.model_spec.data_snapshot_ref == str(request.data_snapshot_ref.artifact_id)
        # A present forecast with the right markers and a fabricated value must fail readback.
        fake = forecast.model_copy(update={"values": {"income": [2.0, 2.0]}})
        fake_ref = store.put_json(
            fake,
            PutOptions(
                kind="scientist.backtest.native_forecast",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.backtesting.NativeForecastTrajectory", version="1.0"
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        with pytest.raises(ValueError, match="recomputed state observations"):
            load_native_forecast(store, fake_ref, forecast.request_ref)
        wrong_schema = store.put_json(
            forecast,
            PutOptions(
                kind="scientist.backtest.native_forecast",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.backtesting.NativeForecastTrajectory", version="9.0"
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        with pytest.raises(ValueError, match="schema version differs"):
            load_native_forecast(store, wrong_schema, forecast.request_ref)
    assert len({s.metadata["backend_run_id"] for s in report.scenarios}) == count
    assert len({s.metadata["actual_foundry_seed"] for s in report.scenarios}) == count
    original_snapshot = from_canonical_bytes(
        store.get_bytes(plan.scientist_state["inputs"]["data_snapshot_ref"]["artifact_id"])
    )
    assert from_canonical_bytes(store.get_bytes(original_snapshot["data_ref"]["artifact_id"]))[
        "income"
    ] == [1.0, 2.0, 900.0, 901.0]


@pytest.mark.parametrize(
    "escape",
    [
        "missing_trinity",
        "mismatched_trinity",
        "future_binding",
        "wrong_target",
        "wrong_unit",
        "wrong_horizon",
        "wrong_time",
        "hidden_future_parameter",
        "prebound_state",
        "model_future_dependency",
    ],
)
def test_native_replay_refuses_unadmitted_inputs_before_backend(tmp_path, monkeypatch, escape):
    import polisyos.scientist.api as api

    store, plan = _fixture(tmp_path, count=1)
    state = plan.scientist_state
    profile = state["params"]["backtest_native_forecast"]
    if escape == "missing_trinity":
        state["inputs"].pop("trinity_bundle_ref")
    elif escape == "mismatched_trinity":
        ref = ArtifactRef.model_validate(state["inputs"]["trinity_bundle_ref"])
        trinity = TrinityBundle.model_validate(from_canonical_bytes(store.get_bytes(ref)))
        model = trinity.model_spec.model_copy(update={"data_snapshot_ref": "sha256:" + "0" * 64})
        fake_ref = store.put_json(
            trinity.model_copy(update={"model_spec": model}),
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
            ),
        )
        state["inputs"]["trinity_bundle_ref"] = fake_ref.model_dump(mode="json")
    elif escape == "future_binding":
        state["params"]["foundry_input_binding_rules"][0]["source_path"] = "income.2"
    elif escape == "wrong_target":
        profile["targets"][0]["metric"] = "government_balance"
    elif escape == "wrong_unit":
        profile["targets"][0]["unit_id"] = "count"
    elif escape == "wrong_horizon":
        profile["time_index"] = ["t2"]
    elif escape == "wrong_time":
        profile["time_index"] = ["t2", "t99"]
    elif escape == "hidden_future_parameter":
        state["params"]["future_income"] = [900, 901]
    elif escape == "prebound_state":
        state["artifacts_index"] = {"exec_plan_ref": state["inputs"]["trinity_bundle_ref"]}
    elif escape == "model_future_dependency":
        ref = ArtifactRef.model_validate(state["inputs"]["trinity_bundle_ref"])
        trinity = TrinityBundle.model_validate(from_canonical_bytes(store.get_bytes(ref)))
        environment = trinity.model_spec.environment_config.model_copy(
            update={
                "params": [
                    EnvironmentParam(
                        param_id="future",
                        value=0,
                        time_varying=True,
                        time_series_ref=plan.historical_data_ref,
                    )
                ]
            }
        )
        model = trinity.model_spec.model_copy(update={"environment_config": environment})
        fake_ref = store.put_json(
            trinity.model_copy(update={"model_spec": model}),
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
            ),
        )
        state["inputs"]["trinity_bundle_ref"] = fake_ref.model_dump(mode="json")

    def forbidden(*args, **kwargs):
        pytest.fail("native admission failure reached the Scientist backend")

    monkeypatch.setattr(api, "run_experiment", forbidden)
    report = BacktestOrchestrator(cas=store).run([plan])
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert report.degraded_reasons
    assert not any(s.outcome_comparisons for s in report.scenarios)
    assert report.metadata["replay_denominators"][0]["completed"] == 0
    assert report.metadata["replay_denominators"][0]["failed"] == 1


def test_native_replay_counters_cannot_bypass_trajectory_requirement(tmp_path, monkeypatch):
    from polisyos.core.contracts.foundry import DerivedArtifact, ExecuteResult
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

    store, plan = _fixture(tmp_path, count=1)
    calls = []

    def counter_only(port, actual_store, request):
        calls.append(request)
        counter = actual_store.put_json(
            {"mechanisms_executed": 1, "income": 1.5},
            PutOptions(kind="foundry.metrics", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return ExecuteResult(ok=True, derived_refs=[DerivedArtifact(role="metrics", ref=counter)])

    monkeypatch.setattr(DefaultFoundryPort, "execute", counter_only)
    report = BacktestOrchestrator(cas=store).run([plan])
    assert len(calls) == 1
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert not any(s.outcome_comparisons for s in report.scenarios)
    assert report.metadata["replay_denominators"][0]["completed"] == 0
    assert report.metadata["replay_denominators"][0]["failed"] == 1
