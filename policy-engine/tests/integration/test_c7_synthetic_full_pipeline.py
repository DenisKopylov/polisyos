from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from _helpers.c7_synthetic_data import (
    build_c7_synthetic_fixture,
    expected_compile_all_artifact_keys,
    persist_c7_synthetic_snapshot,
)
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.lex import ComplianceIssue
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.agent_sim.wiring import (
    ContractsDistributionAwareExecutor,
    ContractsGraphAwareExecutor,
    ContractsPopulationAwareExecutor,
    FirmLifecycleEventBatch,
    FirmLifecycleEventType,
    InterventionMechanismConfig,
    ProcurementShockBatch,
)
from polisyos.foundry.calibration.loss import pointwise_base_loss, reduce_weighted_loss
from polisyos.foundry.calibration.measurement import (
    DefaultMeasurementAwareLossAdapter,
    MeasurementAwareLossConfig,
)
from polisyos.foundry.contracts.state import AgentSimRuntimeState, ProcurementGraphState
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.execute.executor import (
    export_seed_state_npz,
    import_seed_state_npz,
    load_state_snapshot,
)
from polisyos.ir.analytics.calibration import TargetLossConfig
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    NetworkInterferenceReport,
)
from polisyos.ir.analytics.transportability import load_transportability_result
from polisyos.ir.observation.bundles import (
    BacktestPlanBundle,
    ContractCompatibilityTarget,
    StrategicResponseSpecsBundle,
    TransportabilityCheckBundle,
)
from polisyos.ir.observation.causal_execution import BoundsEstimationTask
from polisyos.ir.observation.compiler import CalibrationTargetBundleCompiler
from polisyos.ir.observation.contract_compilers import ObservationContractCompilerSuite
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.ir.observation.governance import (
    DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY,
    GovernancePassMappingRegistry,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    CausalGraphModelRef,
    PolicyRecommendationRef,
    StrategicPayoffTableRef,
)
from polisyos.runtime.replay import measure_replayable_audit_bundle
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.methods.causal import (
    BoundsEstimationRunner,
    ProxyIdentificationRunner,
    StrategicResponseRunner,
    TransportabilityChecker,
)
from polisyos.scientist.compute import run_c7_advanced_suite
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)
from polisyos.scientist.governance import (
    BacktestKind,
    CalibrationGovernanceInput,
    CalibrationGovernanceRunner,
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
)
from polisyos.scientist.governance.calibration import CalibrationAdversarialSuiteRegistry
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    persist_replayable_audit_bundle,
)
from polisyos.scientist.methods.search.lessons import LessonQuery, LessonRegistry

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("POLISYOS_RUN_INTEGRATION") != "1",
        reason="Set POLISYOS_RUN_INTEGRATION=1 to run C7 synthetic integration tests.",
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("lifelines") is None,
        reason="lifelines is required for C7 synthetic integration tests.",
    ),
]


class _PassingPass(ValidatorPass):
    def __init__(self, pass_id: str) -> None:
        self._pass_id = pass_id

    @property
    def pass_id(self) -> str:
        return self._pass_id

    @property
    def estimated_cost_ms(self) -> int:
        return 5

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        del ctx
        return []


def _put_json(store: FileSystemCAS, payload: object, *, kind: str) -> ArtifactRef:
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _candidate_ref(store: FileSystemCAS) -> ArtifactRef:
    return store.put_json(
        {"candidate_id": "c7_synthetic_candidate", "stage": "integration"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _evaluation_ref(store: FileSystemCAS, *, validation_bundle_ref: ArtifactRef) -> ArtifactRef:
    return store.put_json(
        {
            "candidate_id": "c7_synthetic_candidate",
            "validation_bundle_ref": str(validation_bundle_ref.artifact_id),
            "status": "completed",
        },
        PutOptions(kind="scientist.policy_evaluation_vector", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _run_measurement_aware_calibration(panel) -> dict[str, object]:
    bundle = CalibrationTargetBundleCompiler().compile(panel)
    target = bundle.targets[0]
    target_id = target.target_id
    adapter = DefaultMeasurementAwareLossAdapter()
    config = MeasurementAwareLossConfig()
    observed = jnp.asarray(bundle.observed_value[target_id], dtype=jnp.float32)

    def loss_fn(scale: jax.Array) -> jax.Array:
        prediction = scale * jnp.ones_like(observed)
        pointwise = pointwise_base_loss(
            prediction,
            observed,
            TargetLossConfig(kind="mse", weight=1.0, relative=False, epsilon=1e-8),
            scale=1.0,
        )
        adapted = adapter.adapt(
            targets=(target,),
            base_weights=1.0,
            trust_weight=bundle.trust_weight[target_id],
            coverage_estimate=bundle.coverage_estimate[target_id],
            censoring_mask=bundle.censoring_mask[target_id],
            lag_days_estimate=bundle.lag_days_estimate[target_id],
            schema_regime_id=bundle.schema_regime_id[target_id],
            shock_mask=bundle.shock_mask[target_id],
            identification_mode=bundle.identification_mode[target_id],
            config=config,
        )
        return reduce_weighted_loss(pointwise, adapted["effective_weight"], epsilon=1e-8)

    scale = jnp.array(0.5, dtype=jnp.float32)
    losses: list[float] = []
    for _ in range(10):
        loss, grad = jax.value_and_grad(loss_fn)(scale)
        scale = scale - 0.01 * grad
        losses.append(float(loss))
    return {"target_bundle": bundle, "final_scale": float(scale), "loss_history": losses}


def _strategic_payload() -> dict[str, object]:
    from polisyos.ir.analytics.strategic import FiniteStrategicPayoffTable, StrategicSCM
    from polisyos.scientist.orchestration.kernel.budgets import ComputeBudget

    def _artifact(seed: str, *, kind: str) -> ArtifactRefModel:
        return ArtifactRefModel(
            artifact_id=f"sha256:{seed * 64}",
            kind=kind,
            media_type="application/json",
        )

    contract = StrategicSCM(
        base_graph_ref=CausalGraphModelRef(artifact_id=f"sha256:{'a' * 64}"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": StrategicPayoffTableRef(artifact_id=f"sha256:{'b' * 64}"),
            "follower": StrategicPayoffTableRef(artifact_id=f"sha256:{'c' * 64}"),
        },
        policy_rule_ref=PolicyRecommendationRef(artifact_id=f"sha256:{'d' * 64}"),
        equilibrium_concept="stackelberg",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )
    action_spaces = {"leader": ("low", "high"), "follower": ("stay", "switch")}
    tables = {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 1.0,
                "leader=low|follower=switch": 0.0,
                "leader=high|follower=stay": 2.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 2.0,
                "leader=low|follower=switch": 1.0,
                "leader=high|follower=stay": 0.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
    }
    return {
        "baseline_policy_value": 5.0,
        "strategic_scm": contract.model_dump(mode="json"),
        "strategic_payoff_tables": {
            key: table.model_dump(mode="json") for key, table in tables.items()
        },
    }


def _build_backtest_bundle(tmp_path: Path, kind: BacktestKind) -> BacktestPlanBundle:
    path = tmp_path / f"{kind.value}_history.json"
    path.write_text('{"metric":[1.0,1.0,1.0,1.0]}', encoding="utf-8")
    return BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id=f"{kind.value}_bundle",
            contract_fqn="polisyos.tests.BacktestPlanBundle",
        ),
        required_fields=["metric"],
        holdout_windows=["2024-Q4"],
        plans=[
            HistoricalValidationPlan(
                plan_id=f"{kind.value}_plan",
                historical_data_path=str(path),
                ground_truth_outcomes={"metric": [1.0, 1.0]},
                target_metrics=["metric"],
                prediction_source=PredictionSource.PROVIDED,
                predicted_outcomes={"metric": [0.99, 1.01]},
            )
        ],
        historical_payloads={"metric": {"values": [1.0, 1.0, 1.0, 1.0]}},
    )


def _utility_report() -> DownstreamUtilityReport:
    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="h1",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=0.8,
                transportability_score=0.84,
                composite_score=0.92,
                rank=1,
            )
        ],
        recommended_shortlist=["h1"],
    )


def _interference_report() -> NetworkInterferenceReport:
    return NetworkInterferenceReport(
        method=InterferenceMethod.PARTIAL_IPW,
        status="success",
        effects=InterferenceEffectDecomposition(
            direct_effect=0.1,
            spillover_effect=0.02,
            total_effect=0.12,
            n_units=12,
            n_treated=4,
        ),
        exposure_mapping=ExposureMappingType.FRACTIONAL,
        n_units=12,
        n_treated=4,
    )


def _run_pipeline(tmp_path: Path) -> dict[str, object]:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas")
    source_refs, payload_ref, snapshot_ref = persist_c7_synthetic_snapshot(store, fixture=fixture)
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    bindings = build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=None,
    )
    bound_state = load_state_snapshot(store, snapshot_ref=bindings.bound_state_snapshot_ref)

    compiled = ObservationContractCompilerSuite().compile_all(
        observation_panel=fixture.observation_panel,
        graph_artifacts=fixture.graph_artifacts,
        firm_events=fixture.firm_events,
        firm_panels=fixture.firm_panels,
        region_sector_panels=fixture.region_sector_panels,
        proxy_map=fixture.proxy_map,
        survey_spec=fixture.specs["survey_spec"],  # type: ignore[arg-type]
        network_spec=fixture.specs["network_spec"],  # type: ignore[arg-type]
        network_causal_spec=fixture.specs["network_causal_spec"],  # type: ignore[arg-type]
        panel_spec=fixture.specs["panel_spec"],  # type: ignore[arg-type]
        dynamic_treatment_spec=fixture.specs["dynamic_treatment_spec"],  # type: ignore[arg-type]
        survival_spec=fixture.specs["survival_spec"],  # type: ignore[arg-type]
        panel_econometric_spec=fixture.specs["panel_econometric_spec"],  # type: ignore[arg-type]
        bounds_spec=fixture.specs["bounds_spec"],  # type: ignore[arg-type]
        proxy_spec=fixture.specs["proxy_spec"],  # type: ignore[arg-type]
        historical_validation_spec=fixture.specs["historical_validation_spec"],  # type: ignore[arg-type]
        specification_curve_spec=fixture.specs["specification_curve_spec"],  # type: ignore[arg-type]
        leontief_spec=fixture.specs["leontief_spec"],  # type: ignore[arg-type]
    )

    calibration = _run_measurement_aware_calibration(fixture.observation_panel)
    advanced = run_c7_advanced_suite(store, inputs=fixture.advanced_inputs)

    proxy_entries = ProxyIdentificationRunner(graph=fixture.proxy_map.graph).run(
        compiled.artifacts["proxy_measurement_data"].bundle,
    )
    bounds_entries = BoundsEstimationRunner(store=store).run(
        [
            BoundsEstimationTask(
                task_id="c7_bounds_task",
                bounds_input=compiled.artifacts["bounds_estimation_input"].contract,
                bundle=compiled.artifacts["bounds_estimation_input"].bundle,
                params={"informative_threshold": 0.9},
            )
        ]
    )

    transport_bundle = TransportabilityCheckBundle(
        checks=[
            {
                "check_id": "c7_transport",
                "family": ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                "treatment": "X",
                "outcome": "Y",
                "source_regime_id": "wartime_2024",
                "target_regime_id": "wartime_2024",
                "time_grain": "M",
                "source_context": ContextProfile(context_id="UA").model_dump(mode="json"),
                "target_context": ContextProfile(context_id="UA").model_dump(mode="json"),
            }
        ]
    )
    transport_entries = TransportabilityChecker(
        graph=fixture.proxy_map.graph,
        store=store,
    ).run(transport_bundle)
    transport_result = load_transportability_result(store, transport_entries[0].result_ref)

    candidate_ref = _candidate_ref(store)
    strategic_runner = StrategicResponseRunner(
        store=store,
        causal_component_ref=ArtifactRefModel.model_validate(candidate_ref.model_dump(mode="json")),
        run_metadata={"run_id": "c7_synthetic_full"},
    )
    strategic_entries = strategic_runner.run(
        StrategicResponseSpecsBundle(
            expectations=[
                {
                    "intervention_kind": "procurement_threshold_change",
                    "channels": ["procurement_channel"],
                }
            ]
        ),
        channel_payloads={"procurement_channel": _strategic_payload()},
    )
    strategic_summary = dict(strategic_entries[0].summary)
    strategic_summary.update(
        {
            "equilibrium_selection_dependence": "follower_best_response_tie_breaking",
            "multiplicity_note": "multiple_stackelberg_equilibria",
            "equilibrium_profiles": [
                {"leader": "low", "follower": "stay"},
                {"leader": "high", "follower": "switch"},
            ],
            "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 2},
        }
    )

    procurement_graph = ProcurementGraphState(
        senders=np.asarray([0, 1, 2], dtype=np.int32),
        receivers=np.asarray([1, 2, 3], dtype=np.int32),
        weights=np.asarray([1.0, 0.8, 0.6], dtype=np.float32),
        edge_types=np.asarray([1, 1, 1], dtype=np.int32),
        active=np.asarray([True, True, True]),
        n_nodes=np.asarray(bound_state.firms.size, dtype=np.int32),
        last_update_step=np.asarray(0, dtype=np.int32),
    )
    sim_state = bound_state.replace(
        agent_sim_runtime=AgentSimRuntimeState.empty(
            n_agents=int(bound_state.agents.size),
            n_firms=int(bound_state.firms.size),
            seed=17,
        ).replace(procurement_graph=procurement_graph),
        agents=bound_state.agents.replace(
            active=np.asarray([True] * int(bound_state.agents.size)),
            is_employed=np.asarray([True] * int(bound_state.agents.size)),
            employer_id=np.asarray(
                [i % int(bound_state.firms.size) for i in range(int(bound_state.agents.size))],
                dtype=np.int32,
            ),
        ),
        firms=bound_state.firms.replace(
            active=np.asarray([True] * int(bound_state.firms.size)),
            cell_id=np.asarray(
                [i % 50 for i in range(int(bound_state.firms.size))], dtype=np.int32
            ),
            cash=np.asarray(
                [500.0 + i for i in range(int(bound_state.firms.size))], dtype=np.float32
            ),
            inventory=np.asarray([50.0] * int(bound_state.firms.size), dtype=np.float32),
            productivity=np.asarray([1.0] * int(bound_state.firms.size), dtype=np.float32),
            labor_count=np.asarray([10.0] * int(bound_state.firms.size), dtype=np.float32),
        ),
    )
    pop_state, pop_metrics = ContractsPopulationAwareExecutor().step(
        sim_state,
        firm_events=FirmLifecycleEventBatch.from_records(
            [
                {
                    "event_type": FirmLifecycleEventType.ENTRY,
                    "firm_id": 1001,
                    "cell_id": 0,
                    "firm_type_id": 1,
                    "sector_id": 1,
                    "cash": 250.0,
                },
                {"event_type": FirmLifecycleEventType.EXIT, "firm_id": 3},
            ]
        ),
    )
    graph_state, graph_metrics = ContractsGraphAwareExecutor().step(
        pop_state,
        procurement_shocks=ProcurementShockBatch.from_records(
            [{"origin_firm_id": 0, "magnitude": 5.0, "decay": 0.5, "max_hops": 2}]
        ),
    )
    distribution_state, distribution_metrics = ContractsDistributionAwareExecutor().step(
        graph_state,
        intervention_config=InterventionMechanismConfig.from_params(
            {
                "total_transfer_budget": 120.0,
                "target_percentile": 0.35,
                "transfer_formula": "uniform",
            }
        ),
    )

    mapping_registry = GovernancePassMappingRegistry.from_policy_registry(
        DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
    )
    alias_registry = CalibrationAdversarialSuiteRegistry.default()
    pass_ids = sorted(
        {
            *mapping_registry.global_mandatory_passes,
            *mapping_registry.for_family(ObservationFamily.HOUSEHOLD_DISTRIBUTION),
        }
    )
    fake_passes = [
        _PassingPass(pass_id) for pass_id in pass_ids if pass_id not in alias_registry.suite_aliases
    ]
    lesson_registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
    artifacts_index = {}
    if strategic_entries[0].strategic_response_bundle_ref is not None:
        artifacts_index[ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF] = ArtifactRef.model_validate(
            strategic_entries[0].strategic_response_bundle_ref.model_dump(mode="json")
        )
    governance_report = CalibrationGovernanceRunner(
        passes=fake_passes,
        mapping_registry=mapping_registry,
    ).run(
        CalibrationGovernanceInput(
            run_id="c7_synthetic_full",
            observation_families=[ObservationFamily.HOUSEHOLD_DISTRIBUTION],
            profile=ValidationProfile.mvp(),
            pass_state={"_store": store},
            candidate_ref=candidate_ref,
            artifacts_index=artifacts_index,
            params={
                "loop_id": "c7_synthetic",
                "strategic_response_summary": strategic_summary,
                "uses_abstraction": True,
                "abm_alignment_warnings": ["heuristic_aggregation_without_abstraction_certificate"],
            },
            lesson_registry=lesson_registry,
        )
    )

    validation_runner = CalibrationValidationRunner(store)
    validation_result = validation_runner.run(
        CalibrationValidationRunnerInput(
            run_id="c7_synthetic_full",
            candidate_ref=candidate_ref,
            governance_report=governance_report,
            calibration_fit_score=0.91,
            backtest_plan_bundles={
                kind: _build_backtest_bundle(tmp_path, kind) for kind in BacktestKind
            },
            specification_curve_input=compiled.artifacts["specification_curve_input"].contract,
            downstream_utility_report=_utility_report(),
            transportability_result=transport_result,
            network_interference_report=_interference_report(),
            interference_certificate=InterferenceCertificate(
                supported_query_family="spillover",
                fallback_mode="pairwise",
                reduction_error_bound=0.05,
            ),
            strategic_summary=strategic_summary,
            baseline_metrics={"policy_value": 100.0, "coverage": 0.9},
            lesson_registry=lesson_registry,
        )
    )

    evaluation_ref = _evaluation_ref(store, validation_bundle_ref=validation_result.bundle_ref)
    replay_bundle_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="c7_synthetic_full",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            readiness_ref=validation_result.bundle_ref,
            execution_profile="integration",
            runtime_input_refs={
                "payload_ref": payload_ref,
                "data_snapshot_ref": snapshot_ref,
                "input_bindings_ref": bindings.input_bindings_ref,
            },
            runtime_artifacts_index={
                **advanced.bundle_refs(),
                "bound_state_snapshot_ref": bindings.bound_state_snapshot_ref,
            },
            runtime_reports_index={
                "calibration_validation_bundle_ref": validation_result.bundle_ref
            },
            artifact_refs={
                "source_agent_panel_ref": source_refs["agent_panel"],
                "source_firm_panel_ref": source_refs["firm_panel"],
            },
            runtime_params_snapshot={"calibration_steps": 10, "seed": fixture.advanced_inputs.seed},
            trace_notes=["c7 synthetic replay bundle"],
        ),
    )
    replay_measurement = measure_replayable_audit_bundle(store, replay_bundle_ref)

    return {
        "store": store,
        "fixture": fixture,
        "snapshot_ref": snapshot_ref,
        "bindings": bindings,
        "bound_state": bound_state,
        "compiled": compiled,
        "calibration": calibration,
        "advanced": advanced,
        "proxy_entries": proxy_entries,
        "bounds_entries": bounds_entries,
        "transport_entries": transport_entries,
        "transport_result": transport_result,
        "strategic_entries": strategic_entries,
        "strategic_summary": strategic_summary,
        "distribution_state": distribution_state,
        "population_metrics": pop_metrics,
        "graph_metrics": graph_metrics,
        "distribution_metrics": distribution_metrics,
        "governance_report": governance_report,
        "validation_result": validation_result,
        "lesson_registry": lesson_registry,
        "replay_bundle_ref": replay_bundle_ref,
        "replay_measurement": replay_measurement,
    }


def test_c7_full_pipeline_synthetic_e2e(tmp_path) -> None:
    results = _run_pipeline(tmp_path)
    compiled = results["compiled"]
    calibration = results["calibration"]
    advanced = results["advanced"]
    governance_report = results["governance_report"]
    validation_result = results["validation_result"]
    replay_measurement = results["replay_measurement"]

    assert set(compiled.artifacts) == expected_compile_all_artifact_keys()
    assert compiled.backtest is not None
    assert len(calibration["loss_history"]) == 10
    assert all(np.isfinite(loss) for loss in calibration["loss_history"])
    assert len(advanced.bundle_refs()) == 7
    assert results["proxy_entries"]
    assert results["bounds_entries"][0].status == "ok"
    assert results["transport_entries"][0].status == "identified"
    assert results["strategic_entries"][0].status == "ready"
    assert governance_report.metadata["short_circuited"] is False
    assert {item.alias for item in governance_report.adversarial_results} == {
        "strategic_gaming_adversarial",
        "multiplicity_disclosure_adversarial",
        "abstraction_leakage_adversarial",
    }
    assert validation_result.bundle.status == "completed"
    assert validation_result.bundle.backtest_matrix is not None
    assert validation_result.bundle.stress_scenarios is not None
    assert validation_result.bundle.leaderboard_entry is not None
    assert validation_result.bundle.lesson_card_ref is not None
    hits = results["lesson_registry"].query(
        LessonQuery(source_run_id="c7_synthetic_full", limit=10)
    )
    assert hits
    assert replay_measurement.completeness.level.value == "complete"


def test_c7_replay_bundle_size_budget(tmp_path) -> None:
    replay_measurement = _run_pipeline(tmp_path)["replay_measurement"]
    assert replay_measurement.completeness.total_size_bytes <= 25 * 1024 * 1024
    assert replay_measurement.passed is True


def test_c7_foundry_seed_state_roundtrip(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_seed")
    _, _, snapshot_ref = persist_c7_synthetic_snapshot(store, fixture=fixture)
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    bindings = build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=None,
    )
    state = load_state_snapshot(store, snapshot_ref=bindings.bound_state_snapshot_ref)

    path = export_seed_state_npz(state, tmp_path / "foundry_seed_state_v1.npz")
    restored = import_seed_state_npz(path)

    assert path.name == "foundry_seed_state_v1.npz"
    assert restored.cells is not None
    assert restored.household_cells is not None
    assert np.allclose(np.asarray(restored.cells.output), np.asarray(state.cells.output))
    assert np.allclose(
        np.asarray(restored.household_cells.disposable_income),
        np.asarray(state.household_cells.disposable_income),
    )
