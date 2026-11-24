"""Qualify a selected stochastic outcome through Native, BKT and a fresh packet."""

from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    ensure_ir_artifact_store,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import SimulationResult, SimulationResultRef
from polisyos.core.run.manifest import RunManifest
from polisyos.ir.analytics.backtest import persist_backtest_report
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.methods.backtesting.native_replay import (
    _edge_ref,
    load_native_backtest_report,
)
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
    BuildDecisionPacketNode,
)
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
from polisyos.scientist.nodes.builtins.simulate.native_predictive_interval import (
    NativeModelPredictionInterval,
    load_native_model_prediction,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_BACKTEST_REPORT_REF
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.workflows.builder import build_execution_context
from polisyos.scientist.orchestration.workflows.default import default_workflow_spec
from tests.unit.scientist.methods.backtesting.test_native_replay import _fixture


def _declare_interval(plan, *, plan_id):
    state = deepcopy(plan.scientist_state)
    state["params"]["backtest_native_forecast"]["prediction_interval"] = {
        "law_version": "labor_market.uniform_one_agent_income.v1",
        "nominal_level": 0.95,
    }
    return plan.model_copy(update={"plan_id": plan_id, "scientist_state": state})


def test_registered_labor_state_interval_reopens_exactly_with_model_scope(tmp_path, monkeypatch):
    store, plan = _fixture(
        tmp_path,
        count=1,
        horizon=1,
        mechanism="labor_market",
        mechanism_params={"employment_threshold": Decimal("0.5")},
    )
    _, deterministic_plan = _fixture(tmp_path, count=1, horizon=1)
    plan = _declare_interval(plan, plan_id="labor")
    unsupported = _declare_interval(deterministic_plan, plan_id="unsupported")
    dispatch = DefaultFoundryPort.execute
    physical = []

    def observe(self, selected_store, request, **kwargs):
        physical.append(request)
        return dispatch(self, selected_store, request, **kwargs)

    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    _backtest, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan, unsupported])
    assert len(physical) == 2
    report_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    fresh = FileSystemCAS(store.root)
    backtest = load_native_backtest_report(fresh, report_ref)
    scenario, limited = backtest.scenarios
    assert scenario.metadata["prediction_source_effective"] == "scientist"
    assert backtest.trust_eligible is False
    assert scenario.interval_requested_count == scenario.interval_available_count == 1
    assert scenario.interval_evaluated_count == 1
    assert scenario.interval_hit_count == 0
    row = scenario.outcome_comparisons[0]
    assert (row.ci_lower, row.ci_upper, row.within_ci) == (0.0, 10.0, False)
    assert limited.outcome_comparisons[0].y_pred == 1.5
    assert limited.outcome_comparisons[0].within_ci is None
    assert limited.interval_requested_count == 1
    assert limited.interval_available_count == limited.interval_evaluated_count == 0
    assert limited.coverage_probability is None
    assert "unsupported: native_predictive_interval_not_established" in backtest.degraded_reasons
    assert backtest.overall_coverage_probability == 0.0
    forecast_ref = ArtifactRef.model_validate(scenario.metadata["native_forecast_ref"])
    request_ref = ArtifactRef.model_validate(scenario.metadata["native_request_ref"])
    selected = SimulationResultRef.model_validate(
        scenario.metadata["native_prediction_interval_ref"]
    )
    _assert_selected_interval(
        store,
        selected,
        forecast_ref,
        request_ref,
        expected_point=row.y_pred,
    )
    registry_ref = ArtifactRef.model_validate(plan.scientist_state["inputs"]["registry_bundle_ref"])
    packet = _issue_packet(fresh, registry_ref, report_ref, run_id="native-prediction-positive")
    assert packet["backtest_report_status"] == "available"
    assert packet["overall_coverage_probability"] == 0.0
    assert packet["trust_eligible"] is False
    assert packet["trust_score"] is None
    assert packet["model_conditional_prediction_intervals"] == [
        {
            "scenario_id": "labor",
            "interval_type": "prediction_interval",
            "nominal_confidence_level": 0.95,
            "interval_evaluated_count": 1,
            "interval_hit_count": 0,
            "simulation_result_ref": selected.model_dump(mode="json"),
            "scope": "compiled_model_conditional_on_selected_state",
            "observational_calibration": "not_established",
        }
    ]
    stripped = ArtifactRef.model_validate(
        persist_backtest_report(
            ensure_ir_artifact_store(store),
            backtest,
            inputs=[
                item
                for item in store.get_manifest(report_ref).inputs
                if item.role != "native_prediction_interval:labor"
            ],
        ).model_dump(mode="json")
    )
    with pytest.raises(ValueError, match="native_prediction_interval:labor"):
        load_native_backtest_report(fresh, stripped)
    packet = _issue_packet(fresh, registry_ref, stripped, run_id="native-prediction-removed")
    assert packet["backtest_report_status"] == "unavailable"
    assert packet["trust_eligible"] is False
    assert "model_conditional_prediction_intervals" not in packet
    assert len(physical) == 2


def _issue_packet(store, registry_ref, report_ref, *, run_id):
    default = default_workflow_spec()
    by_alias = {node.alias: node for node in default.nodes}
    workflow = default.model_copy(
        update={
            "nodes": [
                by_alias["run_governance"].model_copy(update={"depends_on": []}),
                by_alias["run_evaluator"],
                by_alias["refresh_governance"],
                by_alias["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    context = build_execution_context(store, registry_ref, run_id=run_id)
    registry = NodeRegistry()
    for node in (RunGovernanceNode(), RunEvaluatorNode(), BuildDecisionPacketNode()):
        registry.register(node)
    initial = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": registry_ref},
        artifacts_index={ARTIFACT_BACKTEST_REPORT_REF: report_ref},
        params={"random_seed": 12},
    )
    result = WorkflowExecutor(context, registry).execute(workflow, initial)
    assert result.run_ref is not None
    reader = FileSystemCAS(store.root)
    run = RunManifest.model_validate(load_core_json_artifact(reader, result.run_ref))
    packet_ref = next(ref for ref in run.outputs if ref.kind == "scientist.decision_packet")
    assert input_ref_from_artifact_ref(report_ref, role="backtest.report_ref") in (
        reader.get_manifest(packet_ref).inputs
    )
    return load_core_json_artifact(reader, packet_ref)["backtest"]


def _assert_selected_interval(store, selected, forecast_ref, request_ref, *, expected_point):
    """Exercise the cold read and counterexamples on an already selected execution."""
    fresh = FileSystemCAS(store.root)
    retained = load_native_model_prediction(
        fresh,
        selected,
        forecast_ref,
        request_ref,
        metric="income",
        coordinate="t2",
        nominal_level=0.95,
    )
    assert retained.state_path == "agents.income"
    assert retained.unit_id == "usd"
    assert retained.cutoff == 2
    assert retained.interval_semantics == "prediction_interval"
    assert retained.interval.coverage_target == 0.95
    assert retained.achieved_model_mass == 1.0
    assert (retained.interval.lower, retained.interval.upper) == (0.0, 10.0)
    assert retained.interval.point == expected_point
    assert retained.interval.point in (0.0, 10.0)
    assert retained.observational_calibration == "not_established"
    assert retained.effective_sample_size == "not_established"
    assert retained.causal_validity == "not_established"
    assert retained.gate_eligible is False

    for nominal, coordinate in ((0.8, "t2"), (0.95, "t3")):
        with pytest.raises(ValueError, match="requested forecast cell"):
            load_native_model_prediction(
                fresh,
                selected,
                forecast_ref,
                request_ref,
                metric="income",
                coordinate=coordinate,
                nominal_level=nominal,
            )

    projection = validate_core_model_json_artifact(SimulationResult, fresh, selected)
    report_ref = projection.propagation_report_ref
    assert report_ref is not None
    law_ref = _edge_ref(
        fresh, report_ref, "native_prediction_interval", NativeModelPredictionInterval.ARTIFACT_KIND
    )
    law_manifest = fresh.get_manifest(law_ref)
    report_manifest = fresh.get_manifest(report_ref)
    projection_manifest = fresh.get_manifest(selected)

    def replace_law(new_law_ref):
        replacement_report = store.put_bytes(
            store.get_bytes(report_ref),
            PutOptions(
                kind=report_manifest.kind,
                media_type=report_manifest.media_type,
                schema=report_manifest.artifact_schema,
                canon=report_manifest.canon,
                producer=report_manifest.producer,
                inputs=[
                    input_ref_from_artifact_ref(new_law_ref, role=edge.role)
                    if edge.role == "native_prediction_interval"
                    else edge
                    for edge in report_manifest.inputs
                ],
            ),
            return_selected_profile=True,
        )
        assert replacement_report.artifact_id == report_ref.artifact_id
        assert replacement_report.manifest_profile_sha256 != report_ref.manifest_profile_sha256
        derived = projection.model_copy(update={"propagation_report_ref": replacement_report})
        replacement = store.put_json(
            derived.to_artifact_payload(),
            PutOptions(
                kind=projection_manifest.kind,
                media_type=projection_manifest.media_type,
                schema=projection_manifest.artifact_schema,
                producer=projection_manifest.producer,
                inputs=[
                    input_ref_from_artifact_ref(replacement_report, role=edge.role)
                    if edge.role == "propagation_report"
                    else edge
                    for edge in projection_manifest.inputs
                ],
            ),
            return_selected_profile=True,
        )
        return SimulationResultRef.model_validate(replacement.model_dump(mode="python"))

    foreign = store.put_bytes(
        store.get_bytes(law_ref),
        PutOptions(
            kind=law_manifest.kind,
            media_type=law_manifest.media_type,
            schema=law_manifest.artifact_schema,
            canon=law_manifest.canon,
            producer=law_manifest.producer,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == law_ref.artifact_id
    assert foreign.manifest_profile_sha256 != law_ref.manifest_profile_sha256
    with pytest.raises(ValueError, match="selected lineage mismatch"):
        load_native_model_prediction(
            fresh,
            replace_law(foreign),
            forecast_ref,
            request_ref,
            metric="income",
            coordinate="t2",
            nominal_level=0.95,
        )

    for field, bad_value, required_literal in (
        ("interval_semantics", "confidence_interval", "'prediction_interval'"),
        ("gate_eligible", True, "False"),
    ):
        law = load_core_json_artifact(fresh, law_ref)
        altered = store.put_json(
            {**law, field: bad_value},
            PutOptions(
                kind=law_manifest.kind,
                media_type=law_manifest.media_type,
                schema=law_manifest.artifact_schema,
                producer=law_manifest.producer,
                inputs=law_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValidationError) as error:
            load_native_model_prediction(
                fresh,
                replace_law(altered),
                forecast_ref,
                request_ref,
                metric="income",
                coordinate="t2",
                nominal_level=0.95,
            )
        (issue,) = error.value.errors(include_url=False)
        assert issue["type"] == "literal_error"
        assert issue["input"] == bad_value
        assert issue["ctx"]["expected"] == required_literal
