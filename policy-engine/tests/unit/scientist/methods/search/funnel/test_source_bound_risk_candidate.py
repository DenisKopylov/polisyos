from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    InputRef,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecPlanRef,
    ExecuteRequest,
    FoundryInputBindingReportRef,
    FoundryInputBindingsRef,
    Metrics,
    MetricsRef,
    ProgramGraph,
    ProgramGraphRef,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.data_plane import build_input_bindings, load_input_bindings
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import (
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    load_welfare_bundle,
    load_welfare_sample_bundle,
)
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelStageResult
from polisyos.scientist.methods.search.uncertainty import (
    SourceBoundRiskObservation,
    load_source_bound_risk_observation,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_state import maybe_artifact_ref
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import PropagateWelfareNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    TargetPopulationSpec,
    load_policy_candidate_schema,
    persist_policy_candidate_schema,
)

_SOURCE_KIND = "scientist.search.source_bound_risk_observation"


def _input_edge(ref: ArtifactRef, *, role: str) -> InputRef:
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _trinity_bundle(
    candidate_id: str,
    *,
    data_snapshot_id: str,
    registry_bundle_id: str | None,
) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id=f"problem_{candidate_id}",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id=f"policy_{candidate_id}",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id=f"model_{candidate_id}",
            data_snapshot_ref=data_snapshot_id,
            registry_bundle_ref=registry_bundle_id,
        ),
    )


def _candidate_ref(
    store: FileSystemCAS,
    candidate_id: str,
    *,
    trinity_bundle: TrinityBundle | None = None,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    candidate = PolicyCandidateSchema(
        candidate_id=candidate_id,
        trinity_bundle=trinity_bundle
        or _trinity_bundle(
            candidate_id,
            data_snapshot_id="sha256:" + "0" * 64,
            registry_bundle_id=None,
        ),
        target_population=TargetPopulationSpec(
            population_id=f"population_{candidate_id}",
            description="Candidate-only welfare measurement fixture",
        ),
    )
    return persist_policy_candidate_schema(store, candidate, inputs=inputs)


@dataclass(frozen=True)
class _RoutingStage:
    @property
    def stage_name(self) -> str:
        return "candidate_observation_test"

    @property
    def fidelity_level(self) -> int:
        return 1

    @property
    def estimated_cost_usd(self) -> float:
        return 0.01

    def evaluate(
        self, candidate: dict[str, Any], context: dict[str, Any]
    ) -> FunnelStageResult:
        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=1.0,
            is_promising=True,
            stage_name="candidate_observation_test",
            duration_seconds=0.0,
            uncertainty_envelope=UncertaintyEnvelope.unknown(),
            compute_cost_usd=0.01,
            compute_cost_origin="reported",
            fidelity_level=1,
        )


@dataclass(frozen=True)
class _FoundrySource:
    store: FileSystemCAS
    candidate_ref: ArtifactRef
    candidate_data_snapshot_ref: DataSnapshotRef
    candidate_state_snapshot_ref: StateSnapshotRef
    data_snapshot_ref: DataSnapshotRef
    registry_bundle_ref: ArtifactRef
    state_snapshot_ref: StateSnapshotRef
    bound_state_snapshot_ref: StateSnapshotRef
    input_envelope_ref: ArtifactRef
    trinity_bundle_ref: ArtifactRef
    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    input_bindings_ref: FoundryInputBindingsRef
    input_binding_report_ref: FoundryInputBindingReportRef
    simulation_result_ref: SimulationResultRef
    metrics_ref: MetricsRef


def _build_foundry_source(root: Path) -> _FoundrySource:
    store = FileSystemCAS(root)
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_snapshot_ref = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=base_snapshot_ref.artifact_id)

    input_envelope_ref = persist_uncertainty_envelope(
        ensure_ir_artifact_store(store),
        UncertaintyEnvelope(
            point_estimate=1.0,
            confidence_interval=(1.0, 1.0),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.MANUAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            gate_eligible=False,
            metadata={
                "param_name": "applied_nodes",
                "fixture_role": "single_intervention_execution_count",
            },
        ),
    )
    data_snapshot = DataSnapshot(
        data_ref=state_snapshot_ref,
        uncertainty_envelope_ref=input_envelope_ref,
        notes=["candidate-only fixture; units and risk interpretation are not established"],
    )
    raw_data_snapshot_ref = store.put_json(
        data_snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                _input_edge(state_snapshot_ref, role="data_ref"),
                _input_edge(input_envelope_ref, role="uncertainty_envelope_ref"),
            ],
        ),
        return_selected_profile=True,
    )
    data_snapshot_ref = DataSnapshotRef.model_validate(
        raw_data_snapshot_ref.model_dump(mode="python")
    )

    trinity_bundle = _trinity_bundle(
        "candidate_b161",
        data_snapshot_id=str(data_snapshot_ref.artifact_id),
        registry_bundle_id=str(registry_bundle_ref.artifact_id),
    )
    candidate_ref = _candidate_ref(
        store,
        "candidate_b161",
        trinity_bundle=trinity_bundle,
        inputs=[
            _input_edge(data_snapshot_ref, role="world_model_data_snapshot"),
            _input_edge(registry_bundle_ref, role="world_model_registry"),
        ],
    )
    raw_trinity_bundle_ref = store.put_json(
        trinity_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle",
                version=trinity_bundle.schema_version,
            ),
            inputs=[
                _input_edge(candidate_ref, role="policy_candidate"),
                _input_edge(data_snapshot_ref, role="world_model_data_snapshot"),
                _input_edge(registry_bundle_ref, role="world_model_registry"),
            ],
        ),
    )

    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=raw_trinity_bundle_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    assert compile_result.ok, compile_result.notes
    assert compile_result.exec_plan_ref is not None
    graph_edge = next(
        artifact for artifact in compile_result.derived_refs if artifact.role == "program_graph"
    )
    program_graph_ref = ProgramGraphRef.model_validate(graph_edge.ref.model_dump(mode="python"))
    exec_plan_ref = ExecPlanRef.model_validate(
        compile_result.exec_plan_ref.model_dump(mode="python")
    )
    program_graph = ProgramGraph.model_validate(get_json_artifact(store, program_graph_ref))
    exec_plan = ExecPlan.model_validate(get_json_artifact(store, exec_plan_ref))
    assert program_graph.ir_ref.artifact_id == raw_trinity_bundle_ref.artifact_id
    assert exec_plan.program_ref.artifact_id == program_graph_ref.artifact_id

    binding_build = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
    )
    input_bindings_ref = binding_build.input_bindings_ref
    input_binding_report_ref = binding_build.input_binding_report_ref
    bound_state_snapshot_ref = binding_build.bound_state_snapshot_ref
    execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=binding_build.input_bindings_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    assert execution.ok, execution.notes
    assert execution.simulation_result_ref is not None
    simulation_result_ref = SimulationResultRef.model_validate(
        execution.simulation_result_ref.model_dump(mode="python")
    )
    simulation_result = SimulationResult.model_validate(
        get_json_artifact(store, simulation_result_ref)
    )
    metrics_ref = MetricsRef.model_validate(simulation_result.metrics_ref.model_dump(mode="python"))
    metrics = Metrics.model_validate(get_json_artifact(store, metrics_ref))
    assert metrics.values["applied_nodes"] == 1

    return _FoundrySource(
        store=store,
        candidate_ref=candidate_ref,
        candidate_data_snapshot_ref=data_snapshot_ref,
        candidate_state_snapshot_ref=state_snapshot_ref,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        state_snapshot_ref=state_snapshot_ref,
        bound_state_snapshot_ref=bound_state_snapshot_ref,
        input_envelope_ref=input_envelope_ref,
        trinity_bundle_ref=ArtifactRef.model_validate(raw_trinity_bundle_ref.model_dump(mode="python")),
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        input_bindings_ref=input_bindings_ref,
        input_binding_report_ref=input_binding_report_ref,
        simulation_result_ref=simulation_result_ref,
        metrics_ref=metrics_ref,
    )


def _manifest_edge(store: FileSystemCAS, ref: ArtifactRef, role: str) -> InputRef:
    matches = [edge for edge in store.get_manifest(ref).inputs if edge.role == role]
    assert len(matches) == 1, f"expected one {role} edge, found {len(matches)}"
    return matches[0]


def _ref_key(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    return (str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256)


def _assert_parent_edges(
    store: FileSystemCAS,
    parent_ref: ArtifactRef,
    expected_children: dict[str, ArtifactRef],
) -> None:
    manifest = store.get_manifest(parent_ref)
    for role, child_ref in expected_children.items():
        matches = [edge for edge in manifest.inputs if edge.role == role]
        assert len(matches) == 1, f"expected one {role} edge on {parent_ref.kind}"
        edge = matches[0]
        assert (str(edge.artifact_id), edge.manifest_profile_sha256) == (
            str(child_ref.artifact_id),
            child_ref.manifest_profile_sha256,
        )
        child_manifest = store.get_manifest(child_ref)
        assert child_manifest.kind == child_ref.kind
        assert child_manifest.media_type == child_ref.media_type


def _assert_actual_source_lineage(
    source: _FoundrySource,
    welfare_ref: ArtifactRef,
    bundle: WelfareBundle,
    *,
    candidate_source_matches_run: bool = True,
) -> None:
    store = source.store
    candidate = load_policy_candidate_schema(store, source.candidate_ref)
    trinity = TrinityBundle.model_validate(get_json_artifact(store, source.trinity_bundle_ref))
    candidate_snapshot = DataSnapshot.model_validate(
        get_json_artifact(store, source.candidate_data_snapshot_ref)
    )
    execution_snapshot = DataSnapshot.model_validate(
        get_json_artifact(store, source.data_snapshot_ref)
    )
    bindings = load_input_bindings(store, source.input_bindings_ref)
    binding_report = get_json_artifact(store, source.input_binding_report_ref)
    exec_plan = ExecPlan.model_validate(get_json_artifact(store, source.exec_plan_ref))
    program_graph = ProgramGraph.model_validate(
        get_json_artifact(store, source.program_graph_ref)
    )
    simulation_result = SimulationResult.model_validate(
        get_json_artifact(store, source.simulation_result_ref)
    )

    assert candidate.candidate_id == "candidate_b161"
    assert candidate.trinity_bundle == trinity
    assert candidate.trinity_bundle.model_spec.data_snapshot_ref == str(
        source.candidate_data_snapshot_ref.artifact_id
    )
    assert candidate.trinity_bundle.model_spec.registry_bundle_ref == str(
        source.registry_bundle_ref.artifact_id
    )
    assert _ref_key(candidate_snapshot.data_ref) == _ref_key(source.candidate_state_snapshot_ref)
    assert _ref_key(execution_snapshot.data_ref) == _ref_key(source.state_snapshot_ref)
    assert candidate_snapshot.uncertainty_envelope_ref is not None
    assert execution_snapshot.uncertainty_envelope_ref == source.input_envelope_ref
    assert _ref_key(bindings.data_snapshot_ref) == _ref_key(source.data_snapshot_ref)
    assert _ref_key(bindings.registry_bundle_ref) == _ref_key(source.registry_bundle_ref)
    assert _ref_key(bindings.bound_state_snapshot_ref) == _ref_key(
        source.bound_state_snapshot_ref
    )
    assert binding_report["data_snapshot_ref"] == source.data_snapshot_ref.model_dump(mode="json")
    assert binding_report["registry_bundle_ref"] == source.registry_bundle_ref.model_dump(mode="json")
    assert binding_report["bound_state_snapshot_ref"] == source.bound_state_snapshot_ref.model_dump(
        mode="json"
    )
    assert _ref_key(program_graph.ir_ref) == _ref_key(source.trinity_bundle_ref)
    assert _ref_key(exec_plan.program_ref) == _ref_key(source.program_graph_ref)
    assert _ref_key(simulation_result.exec_plan_ref) == _ref_key(source.exec_plan_ref)
    assert _ref_key(simulation_result.metrics_ref) == _ref_key(source.metrics_ref)
    assert (
        str(source.candidate_data_snapshot_ref.artifact_id)
        == str(source.data_snapshot_ref.artifact_id)
    ) is candidate_source_matches_run

    expected_lineage = (
        (
            source.candidate_data_snapshot_ref,
            {
                "data_ref": source.candidate_state_snapshot_ref,
                "uncertainty_envelope_ref": source.input_envelope_ref,
            },
        ),
        (
            source.data_snapshot_ref,
            {
                "data_ref": source.state_snapshot_ref,
                "uncertainty_envelope_ref": source.input_envelope_ref,
            },
        ),
        (
            source.candidate_ref,
            {
                "world_model_data_snapshot": source.candidate_data_snapshot_ref,
                "world_model_registry": source.registry_bundle_ref,
            },
        ),
        (
            source.trinity_bundle_ref,
            {
                "policy_candidate": source.candidate_ref,
                "world_model_data_snapshot": source.candidate_data_snapshot_ref,
                "world_model_registry": source.registry_bundle_ref,
            },
        ),
        (
            source.program_graph_ref,
            {"ir": source.trinity_bundle_ref, "registry_bundle": source.registry_bundle_ref},
        ),
        (source.exec_plan_ref, {"program_graph": source.program_graph_ref}),
        (
            source.input_bindings_ref,
            {
                "input.data_snapshot_ref": source.data_snapshot_ref,
                "input.registry_bundle_ref": source.registry_bundle_ref,
                "artifact.bound_state_snapshot_ref": source.bound_state_snapshot_ref,
            },
        ),
        (
            source.input_binding_report_ref,
            {
                "artifact.input_bindings_ref": source.input_bindings_ref,
                "artifact.bound_state_snapshot_ref": source.bound_state_snapshot_ref,
                "input.data_snapshot_ref": source.data_snapshot_ref,
                "input.registry_bundle_ref": source.registry_bundle_ref,
            },
        ),
        (
            source.simulation_result_ref,
            {
                "exec_plan": source.exec_plan_ref,
                "metrics": source.metrics_ref,
                "input.input_bindings_ref": source.input_bindings_ref,
                "input.data_snapshot_ref": source.data_snapshot_ref,
                "input.bound_state_snapshot_ref": source.bound_state_snapshot_ref,
            },
        ),
        (
            welfare_ref,
            {
                "simulation_result": source.simulation_result_ref,
                "metrics": source.metrics_ref,
            },
        ),
    )
    for parent_ref, children in expected_lineage:
        _assert_parent_edges(store, parent_ref, children)

    assert bundle.policy_ref is not None
    assert _ref_key(ArtifactRef.model_validate(bundle.policy_ref.model_dump(mode="python"))) == (
        _ref_key(source.candidate_ref)
    )


def _build_foreign_execution(source: _FoundrySource) -> _FoundrySource:
    store = source.store
    foreign_state = GlobalState.empty(n_agents=3, n_firms=1)
    raw_state_ref = put_state_snapshot(store, state=foreign_state, step=0)
    foreign_state_ref = StateSnapshotRef.model_validate(raw_state_ref.model_dump(mode="python"))
    raw_data_ref = store.put_json(
        DataSnapshot(
            data_ref=foreign_state_ref,
            uncertainty_envelope_ref=source.input_envelope_ref,
            notes=["valid foreign DataSnapshot wrapper for candidate-source mismatch control"],
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                _input_edge(foreign_state_ref, role="data_ref"),
                _input_edge(source.input_envelope_ref, role="uncertainty_envelope_ref"),
            ],
        ),
        return_selected_profile=True,
    )
    foreign_data_snapshot_ref = DataSnapshotRef.model_validate(
        raw_data_ref.model_dump(mode="python")
    )
    binding_build = build_input_bindings(
        store,
        data_snapshot_ref=foreign_data_snapshot_ref,
        registry_bundle_ref=source.registry_bundle_ref,
    )
    execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=source.exec_plan_ref,
            input_bindings_ref=binding_build.input_bindings_ref,
            registry_bundle_ref=source.registry_bundle_ref,
        ),
    )
    assert execution.ok, execution.notes
    assert execution.simulation_result_ref is not None
    result_ref = SimulationResultRef.model_validate(
        execution.simulation_result_ref.model_dump(mode="python")
    )
    result = SimulationResult.model_validate(get_json_artifact(store, result_ref))
    metrics_ref = MetricsRef.model_validate(result.metrics_ref.model_dump(mode="python"))
    metrics = Metrics.model_validate(get_json_artifact(store, metrics_ref))
    assert metrics.values["applied_nodes"] == 1
    return replace(
        source,
        data_snapshot_ref=foreign_data_snapshot_ref,
        state_snapshot_ref=foreign_state_ref,
        bound_state_snapshot_ref=binding_build.bound_state_snapshot_ref,
        input_bindings_ref=binding_build.input_bindings_ref,
        input_binding_report_ref=binding_build.input_binding_report_ref,
        simulation_result_ref=result_ref,
        metrics_ref=metrics_ref,
    )


def _source_fixture(
    source: _FoundrySource,
    *,
    preferred_method: str = "monte_carlo",
    run_id: str = "R_b161_welfare",
    candidate_source_matches_run: bool = True,
) -> tuple[FileSystemCAS, ArtifactRef, ArtifactRef]:
    store = source.store
    registry_bundle_ref = source.registry_bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.b161.source_bound_welfare.{run_id}"),
    )
    state = ExperimentState(
        run_id=run_id,
        inputs={INPUT_DATA_SNAPSHOT_REF: source.data_snapshot_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: source.simulation_result_ref},
        params={
            "welfare_config": {
                "weights": {"applied_nodes": 1.0},
                "policy_ref": source.candidate_ref,
            },
            "propagation_config": {
                "preferred_method": preferred_method,
                "mc_n_samples": 100,
                "mc_min_valid_samples": 50,
            },
        },
    )
    node_outcome = PropagateWelfareNode().execute(ctx, state)
    assert node_outcome.status == "ok"
    welfare_ref = maybe_artifact_ref(
        node_outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    )
    assert welfare_ref is not None
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.policy_ref is not None
    assert ArtifactRef.model_validate(bundle.policy_ref.model_dump(mode="python")) == (
        source.candidate_ref
    )
    _assert_actual_source_lineage(
        source,
        welfare_ref,
        bundle,
        candidate_source_matches_run=candidate_source_matches_run,
    )
    return store, source.candidate_ref, welfare_ref



def _persist_welfare_bundle_view(
    store: FileSystemCAS, bundle: WelfareBundle, inputs: list[InputRef]
) -> ArtifactRef:
    return store.put_json(
        bundle.model_dump(mode="json"),
        PutOptions(
            kind="ir.welfare_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="ir.welfare_bundle", version=bundle.schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _funnel_outcome(
    store,
    candidate_ref: ArtifactRef,
    welfare_ref: ArtifactRef,
    *,
    context: dict[str, Any] | None = None,
):
    runtime = FunnelOrchestrator([_RoutingStage()])
    candidate = load_policy_candidate_schema(store, candidate_ref)
    selected_context = (
        dict(context)
        if context is not None
        else {
            "store": store,
            "policy_candidate_ref": candidate_ref,
            "welfare_bundle_ref": welfare_ref,
        }
    )
    ticket = runtime.submit({"candidate_id": candidate.candidate_id}, selected_context)
    return runtime.advance(ticket, target_level=1)

def _assert_real_mixed_nested_monte_carlo_source(
    store: FileSystemCAS, welfare_ref: ArtifactRef
) -> WelfareBundle:
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.method_used is WelfareMethod.MIXED_NESTED
    assert bundle.interval_semantics is WelfareIntervalSemantics.MIXED_NESTED
    assert bundle.credible_interval is not None
    assert bundle.robust_interval is not None
    assert bundle.method_config_ref is not None
    assert bundle.sample_bundle_ref is not None

    welfare_manifest = store.get_manifest(welfare_ref)
    method_ref = ArtifactRef.model_validate(bundle.method_config_ref.model_dump(mode="python"))
    method_config = get_json_artifact(store, method_ref)
    assert method_config["preferred_method"] == "monte_carlo"
    method_edge = next(edge for edge in welfare_manifest.inputs if edge.role == "method_config")
    assert method_edge.artifact_id == method_ref.artifact_id
    assert method_edge.manifest_profile_sha256 == method_ref.manifest_profile_sha256

    report_edge = next(edge for edge in welfare_manifest.inputs if edge.role == "propagation_report")
    report_ref = ArtifactRef(
        artifact_id=report_edge.artifact_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
        manifest_profile_sha256=report_edge.manifest_profile_sha256,
    )
    report_manifest = store.get_manifest(report_ref)
    assert report_manifest.artifact_schema is not None
    assert report_manifest.artifact_schema.name == "polisyos.foundry.WelfarePropagationReport"
    report = get_json_artifact(store, report_ref)
    assert report["methods"] == ["monte_carlo"]
    assert report["valid_draw_count"] == 100

    sample_bundle = load_welfare_sample_bundle(
        ensure_ir_artifact_store(store), bundle.sample_bundle_ref
    )
    assert len(sample_bundle.welfare_draws) == 100
    assert len(sample_bundle.welfare_pe_draws) == 100
    assert len(sample_bundle.welfare_ge_draws) == 100
    return bundle


class _NoopPredictiveVoi:
    def update_calibration_state(self, state: dict[str, Any]) -> None:
        self.state = state

    def model_status(self) -> list[dict[str, Any]]:
        return []


def _benchmark_funnel_context(
    store: FileSystemCAS, candidate_ref: ArtifactRef, welfare_ref: ArtifactRef
) -> dict[str, Any]:
    from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle
    from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_benchmarks import (
        build_runtime_funnel_context,
    )

    run_id = "R_b161_benchmark_bridge"
    scheduler = _NoopPredictiveVoi()
    owner = SimpleNamespace(
        resolve_actionable_store=lambda *, store: store,
        maybe_artifact_ref=lambda value: value if isinstance(value, ArtifactRef) else None,
        _resolve_runtime_correlation_metrics=lambda state, calibration_report: {},
        _load_stress_test_report=lambda ctx, ref: None,
        LessonRegistry=lambda *, root, store: None,
        load_predictive_voi_scheduler=lambda ctx, *, transfer_context: scheduler,
        persist_promotion_evidence_bundle=lambda store, evidence_bundle, *, inputs: candidate_ref,
    )
    session = SimpleNamespace(
        owner=owner,
        ctx=SimpleNamespace(store=store),
        state=SimpleNamespace(
            params={},
            run_id=run_id,
            artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        ),
        candidate=SimpleNamespace(metadata={}),
        candidate_ref=candidate_ref,
        evidence_bundle=PromotionEvidenceBundle(
            run_id=run_id,
            produced_by_run_id=run_id,
            candidate_ref=candidate_ref,
        ),
        evidence_ref=candidate_ref,
        calibration_report=None,
        simulation_metrics=None,
        uncertainty_envelope=UncertaintyEnvelope.unknown(),
        uncertainty_basis_ref=None,
        selection_evaluation=None,
        hidden_holdout=None,
        benchmark_registry=None,
        platform_meta_ref=None,
        governance_report=None,
        stress_report_ref=None,
        causal_report=None,
        distributional_report=None,
        cross_graph_profile=None,
        degradation_mode="normal",
        calibration_ref=None,
        input_signature="b161-test-input-signature",
        selection_vector_ref=candidate_ref,
        selection_ref=candidate_ref,
    )
    return build_runtime_funnel_context(session)


@pytest.fixture(scope="module")
def foundry_source(tmp_path_factory):
    return _build_foundry_source(tmp_path_factory.mktemp("b161-source-bound"))


@pytest.fixture(scope="module")
def source_pair(foundry_source):
    source = foundry_source
    monte_carlo = _source_fixture(
        source, preferred_method="monte_carlo", run_id="R_b161_monte_carlo"
    )
    delta = _source_fixture(source, preferred_method="delta", run_id="R_b161_delta")
    return monte_carlo, delta


@pytest.fixture(scope="module")
def source_bundle(source_pair):
    return source_pair[0]


def test_actual_welfare_producer_persists_candidate_observation_for_fresh_funnel_consumer(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    _assert_real_mixed_nested_monte_carlo_source(store, welfare_ref)
    benchmark_context = _benchmark_funnel_context(store, candidate_ref, welfare_ref)
    assert benchmark_context["welfare_bundle_ref"] == welfare_ref

    outcome = _funnel_outcome(
        store, candidate_ref, welfare_ref, context=benchmark_context
    )
    observation_ref = next(ref for ref in outcome.audit_refs if ref.kind == _SOURCE_KIND)

    observation = load_source_bound_risk_observation(store, observation_ref, candidate_ref)

    assert observation.valid_draw_count == observation.successful_draw_count == 100
    assert observation.nominal_point_estimate == 1.0
    assert observation.welfare_draw_mean > 0.0
    assert observation.welfare_draw_std >= 0.0
    assert observation.simulation_attempt_count >= observation.attempted_draw_count
    assert observation.retry_attempt_count == (
        observation.simulation_attempt_count - observation.attempted_draw_count
    )
    assert observation.credible_interval is not None
    assert observation.risk_interpretation_status == "not_established"
    assert observation.refinement_status == "not_established"
    assert observation.scope_relation_status == "consumer_asserted"
    assert observation.unit is None
    assert observation.authority_purpose == "candidate_only_audit_measurement"
    assert observation.admission_status == "candidate_only"
    assert observation.production_time_role == "source_bundle_manifest_created_at"
    assert observation.observed_at == store.get_manifest(welfare_ref).created_at
    assert observation.candidate_ref == candidate_ref
    assert observation.policy_scope_claim_ref == candidate_ref
    assert observation.valid_time is None
    assert observation.unit_binding_status == "not_established"
    assert observation.valid_time_status == "not_established"
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0
        for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_real_delta_producer_is_withheld_even_with_monte_carlo_sample_shape(
    source_pair,
) -> None:
    (store, _, mc_welfare_ref), (
        delta_store,
        delta_candidate_ref,
        delta_welfare_ref,
    ) = source_pair
    assert store.root == delta_store.root
    mc_bundle = load_welfare_bundle(ensure_ir_artifact_store(store), mc_welfare_ref)
    delta_bundle = load_welfare_bundle(ensure_ir_artifact_store(store), delta_welfare_ref)
    assert mc_bundle.sample_bundle_ref is not None
    assert delta_bundle.sample_bundle_ref is None
    assert delta_bundle.method_used is WelfareMethod.MIXED_NESTED
    assert delta_bundle.interval_semantics is WelfareIntervalSemantics.MIXED_NESTED

    delta_manifest = store.get_manifest(delta_welfare_ref)
    mc_manifest = store.get_manifest(mc_welfare_ref)
    assert delta_bundle.method_config_ref is not None
    delta_method_ref = ArtifactRef.model_validate(
        delta_bundle.method_config_ref.model_dump(mode="python")
    )
    delta_config = get_json_artifact(store, delta_method_ref)
    assert delta_config["preferred_method"] == "delta"
    delta_report_edge = next(
        edge for edge in delta_manifest.inputs if edge.role == "propagation_report"
    )
    delta_report_ref = ArtifactRef(
        artifact_id=delta_report_edge.artifact_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
        manifest_profile_sha256=delta_report_edge.manifest_profile_sha256,
    )
    delta_report_manifest = store.get_manifest(delta_report_ref)
    assert delta_report_manifest.artifact_schema is not None
    assert delta_report_manifest.artifact_schema.name == "polisyos.foundry.WelfarePropagationReport"
    delta_report = get_json_artifact(store, delta_report_ref)
    assert delta_report["methods"] == ["delta"]

    mc_sample_edge = next(edge for edge in mc_manifest.inputs if edge.role == "sample_bundle")
    sample_manifest = store.get_manifest(
        ArtifactRef(
            artifact_id=mc_sample_edge.artifact_id,
            kind="ir.welfare_sample_bundle",
            media_type="application/json",
            manifest_profile_sha256=mc_sample_edge.manifest_profile_sha256,
        )
    )
    assert sample_manifest.artifact_schema is not None
    assert sample_manifest.artifact_schema.name == "ir.welfare_sample_bundle"
    forged_bundle = delta_bundle.model_copy(
        update={"sample_bundle_ref": mc_bundle.sample_bundle_ref}
    )
    forged_inputs = [
        edge for edge in delta_manifest.inputs if edge.role != "sample_bundle"
    ]
    forged_inputs.append(mc_sample_edge)
    forged_welfare_ref = _persist_welfare_bundle_view(store, forged_bundle, forged_inputs)

    outcome = _funnel_outcome(store, delta_candidate_ref, forged_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0
        for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_candidate_claim_mismatch_emits_no_observation_and_does_not_lower_history(
    source_bundle,
) -> None:
    store, _, welfare_ref = source_bundle
    foreign_candidate_ref = _candidate_ref(store, "candidate_foreign")

    outcome = _funnel_outcome(store, foreign_candidate_ref, welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0
        for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_valid_foreign_data_snapshot_stays_candidate_only_and_never_becomes_refinement(
    foundry_source,
) -> None:
    foreign_source = _build_foreign_execution(foundry_source)
    store, candidate_ref, welfare_ref = _source_fixture(
        foreign_source,
        run_id="R_b161_foreign_data_snapshot",
        candidate_source_matches_run=False,
    )
    candidate = load_policy_candidate_schema(store, candidate_ref)
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert candidate.trinity_bundle.model_spec.data_snapshot_ref == str(
        foundry_source.candidate_data_snapshot_ref.artifact_id
    )
    assert foreign_source.data_snapshot_ref.artifact_id != (
        foundry_source.candidate_data_snapshot_ref.artifact_id
    )
    _assert_actual_source_lineage(
        foreign_source,
        welfare_ref,
        bundle,
        candidate_source_matches_run=False,
    )

    outcome = _funnel_outcome(store, candidate_ref, welfare_ref)

    observation_ref = next(ref for ref in outcome.audit_refs if ref.kind == _SOURCE_KIND)
    observation = load_source_bound_risk_observation(store, observation_ref, candidate_ref)
    assert observation.admission_status == "candidate_only"
    assert observation.scope_relation_status == "consumer_asserted"
    assert observation.refinement_status == "not_established"
    assert observation.risk_interpretation_status == "not_established"
    assert observation.unit_binding_status == "not_established"
    assert observation.valid_time_status == "not_established"
    assert outcome.current_uncertainty_envelope is None
    assert all(estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values())


def test_selected_method_profile_must_match_the_welfare_source_edge(source_bundle) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.method_config_ref is not None
    method_ref = ArtifactRef.model_validate(bundle.method_config_ref.model_dump(mode="python"))
    method_manifest = store.get_manifest(method_ref)
    alternate_method_ref = store.put_json(
        get_json_artifact(store, method_ref),
        PutOptions(
            kind=method_ref.kind,
            media_type=method_ref.media_type,
            schema=SchemaInfo(name="alternate_welfare_method_profile", version="1.0"),
            inputs=method_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert alternate_method_ref.artifact_id == method_ref.artifact_id
    assert alternate_method_ref.manifest_profile_sha256 != method_ref.manifest_profile_sha256
    forged_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python")
        | {"method_config_ref": alternate_method_ref.model_dump(mode="python")}
    )
    welfare_inputs = store.get_manifest(welfare_ref).inputs
    forged_welfare_ref = _persist_welfare_bundle_view(store, forged_bundle, welfare_inputs)

    outcome = _funnel_outcome(store, candidate_ref, forged_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)


def test_missing_source_method_edge_keeps_candidate_markers_from_admitting_observation(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    welfare_inputs = [
        edge for edge in store.get_manifest(welfare_ref).inputs if edge.role != "method_config"
    ]
    forged_welfare_ref = _persist_welfare_bundle_view(store, bundle, welfare_inputs)

    outcome = _funnel_outcome(store, candidate_ref, forged_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)


def test_removed_draw_provenance_cannot_emit_candidate_observation_with_markers_intact(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    welfare_manifest = store.get_manifest(welfare_ref)
    report_edge = next(edge for edge in welfare_manifest.inputs if edge.role == "propagation_report")
    report_ref = ArtifactRef(
        artifact_id=report_edge.artifact_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
        manifest_profile_sha256=report_edge.manifest_profile_sha256,
    )
    report_manifest = store.get_manifest(report_ref)
    report_payload = get_json_artifact(store, report_ref)
    assert isinstance(report_payload, dict)
    tampered_report = dict(report_payload)
    tampered_report.pop("draw_outcome_provenance", None)
    assert report_manifest.artifact_schema is not None
    tampered_report_ref = store.put_json(
        tampered_report,
        PutOptions(
            kind=report_ref.kind,
            media_type=report_ref.media_type,
            schema=report_manifest.artifact_schema,
            inputs=report_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert tampered_report_ref.artifact_id != report_ref.artifact_id
    forged_inputs = [edge for edge in welfare_manifest.inputs if edge.role != "propagation_report"]
    forged_inputs.append(
        InputRef(
            artifact_id=tampered_report_ref.artifact_id,
            role="propagation_report",
            manifest_profile_sha256=tampered_report_ref.manifest_profile_sha256,
        )
    )
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    forged_welfare_ref = _persist_welfare_bundle_view(store, bundle, forged_inputs)

    outcome = _funnel_outcome(store, candidate_ref, forged_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values())


def test_fresh_reader_rejects_changed_count_while_candidate_markers_remain(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    outcome = _funnel_outcome(store, candidate_ref, welfare_ref)
    observation_ref = next(ref for ref in outcome.audit_refs if ref.kind == _SOURCE_KIND)
    observation = load_source_bound_risk_observation(store, observation_ref, candidate_ref)
    forged = SourceBoundRiskObservation.model_validate(
        observation.model_dump(mode="python")
        | {"valid_draw_count": observation.valid_draw_count + 1}
    )
    forged_ref = store.put_json(
        forged.model_dump(mode="json"),
        PutOptions(
            kind=_SOURCE_KIND,
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.SourceBoundRiskObservation", version="1.0"),
            inputs=store.get_manifest(observation_ref).inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    assert forged.risk_interpretation_status == "not_established"
    with pytest.raises(ValueError, match="recomputed source contents"):
        load_source_bound_risk_observation(store, forged_ref, candidate_ref)
