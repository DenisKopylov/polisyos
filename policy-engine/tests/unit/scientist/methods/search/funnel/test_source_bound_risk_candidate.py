from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar

import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    CanonInfo,
    FileSystemCAS,
    InputRef,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    resolve_manifest_by_profile,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts import FoundryExecutionInputBasis, FoundryExecutionInputBasisRef
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecPlanRef,
    ExecuteRequest,
    FeedbackConfig,
    FeedbackConfigRef,
    FoundryInputBindingReportRef,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    Metrics,
    MetricsRef,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    ProgramGraph,
    ProgramGraphRef,
    SimulationResult,
    SimulationResultRef,
    StateDelta,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.data_forge.domains.ukraine.builders.io import _cas_put_json
from polisyos.foundry._quickstart import prepare_trivial_feedback_config
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane import build_input_bindings, load_input_bindings
from polisyos.foundry.data_plane.bindings import load_ukraine_foundry_intake
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.foundry.methods.catalog.simulation.dynamics import build_abm_result_from_simulation
from polisyos.ir.analytics.phase4_dynamics import load_abm_result, persist_abm_result
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
    _source_identity_relation,
    _source_refs_equal,
    load_source_bound_risk_observation,
    persist_source_bound_risk_observation,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope as SearchUncertaintyEnvelope,
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
from tests._helpers.ukraine_foundry_intake import _ukraine_intake_manifests

_SOURCE_KIND = "scientist.search.source_bound_risk_observation"


_ArtifactRefT = TypeVar("_ArtifactRefT", bound=ArtifactRef)


def _producer_ref_payload(value: object) -> Mapping[str, Any]:
    """Read one producer's complete ref DTO without falling back to its ID."""
    if isinstance(value, Mapping):
        payload = value
    else:
        model_dump = getattr(value, "model_dump", None)
        if not callable(model_dump):
            raise TypeError("artifact producer returned no typed ref DTO")
        payload = model_dump(mode="python")
    if not isinstance(payload, Mapping):
        raise TypeError("artifact producer ref DTO is not a mapping")
    return payload


def _producer_output_ref(
    value: object,
    ref_type: type[_ArtifactRefT],
    *,
    expected_kind: str,
) -> _ArtifactRefT:
    """Validate a producer DTO before projecting its known domain ref type."""
    ref = ArtifactRef.model_validate(_producer_ref_payload(value))
    if ref.kind != expected_kind or ref.media_type != "application/json":
        raise ValueError("artifact producer ref type differs from its output role")
    typed_ref = ref_type.model_validate(ref.model_dump(mode="python"))
    if (
        typed_ref.artifact_id != ref.artifact_id
        or typed_ref.kind != ref.kind
        or typed_ref.media_type != ref.media_type
        or typed_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
    ):
        raise ValueError("domain ref projection changed producer identity or selected profile")
    return typed_ref


def _get_json_artifact(store: FileSystemCAS, value: object) -> Any:
    """Read a producer ref through the existing Core-to-IR selector bridge."""
    ref = ArtifactRef.model_validate(_producer_ref_payload(value))
    return get_json_artifact(ensure_ir_artifact_store(store), ref)


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
    return_selected_profile: bool = False,
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
    return persist_policy_candidate_schema(
        store, candidate, inputs=inputs, return_selected_profile=return_selected_profile
    )


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

    def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=1.0,
            is_promising=True,
            stage_name="candidate_observation_test",
            duration_seconds=0.0,
            uncertainty_envelope=SearchUncertaintyEnvelope.unknown(),
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
    link_report_ref: ArtifactRef
    exec_plan_ref: ExecPlanRef
    treasury_plan_ref: ArtifactRef
    input_bindings_ref: FoundryInputBindingsRef
    input_binding_report_ref: FoundryInputBindingReportRef
    simulation_result_ref: SimulationResultRef
    execution_input_basis_ref: FoundryExecutionInputBasisRef | None
    metrics_ref: MetricsRef
    intake_receipt_ref: ArtifactRef


def _build_foundry_source(root: Path) -> _FoundrySource:
    store = FileSystemCAS(root)
    registry_bundle_ref = build_default_registry_bundle(
        store, return_selected_profile=True
    ).bundle_ref
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_snapshot_ref = put_state_snapshot(
        store, state=base_state, step=0, return_selected_profile=True
    )
    state_snapshot_ref = _producer_output_ref(
        base_snapshot_ref, StateSnapshotRef, expected_kind="foundry.state_snapshot"
    )

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
        return_selected_profile=True,
    )
    data_snapshot = DataSnapshot(
        data_ref=state_snapshot_ref,
        notes=["candidate-only fixture; units and risk interpretation are not established"],
    )
    raw_data_snapshot_ref = _cas_put_json(
        store,
        data_snapshot,
        kind=DataSnapshot.ARTIFACT_KIND,
        media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
        schema=SchemaInfo(
            name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
            version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
        ),
        return_selected_profile=True,
        inputs=[
            _input_edge(state_snapshot_ref, role="data_ref"),
        ],
    )
    produced_data_snapshot_ref = _producer_output_ref(
        raw_data_snapshot_ref, DataSnapshotRef, expected_kind="fabric.data_snapshot"
    )
    assert produced_data_snapshot_ref.manifest_profile_sha256 is not None
    stage_root = root / "ukraine-intake"
    intake = load_ukraine_foundry_intake(
        store,
        stage_manifests=_ukraine_intake_manifests(
            stage_root,
            data_snapshot_ref=produced_data_snapshot_ref,
        ),
        allowed_root=stage_root,
    )
    data_snapshot_ref = intake.data_snapshot_ref
    assert data_snapshot_ref == produced_data_snapshot_ref

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
        return_selected_profile=True,
    )
    raw_trinity_bundle_ref = store.put_json(
        trinity_bundle,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                _input_edge(candidate_ref, role="policy_candidate"),
                _input_edge(data_snapshot_ref, role="world_model_data_snapshot"),
                _input_edge(registry_bundle_ref, role="world_model_registry"),
            ],
        ),
        return_selected_profile=True,
    )

    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=raw_trinity_bundle_ref,
            registry_bundle_ref=registry_bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert compile_result.ok, compile_result.notes
    assert compile_result.exec_plan_ref is not None
    assert compile_result.compile_report_ref is not None
    compile_report_ref = _producer_output_ref(
        compile_result.compile_report_ref, ArtifactRef, expected_kind="compiler.compile_report"
    )
    assert compile_report_ref.manifest_profile_sha256 is not None
    graph_edge = next(
        artifact for artifact in compile_result.derived_refs if artifact.role == "program_graph"
    )
    program_graph_ref = _producer_output_ref(
        graph_edge.ref, ProgramGraphRef, expected_kind="foundry.program_graph"
    )
    exec_plan_ref = _producer_output_ref(
        compile_result.exec_plan_ref, ExecPlanRef, expected_kind="foundry.exec_plan"
    )
    link_report_edge = next(
        artifact for artifact in compile_result.derived_refs if artifact.role == "link_report"
    )
    link_report_ref = _producer_output_ref(
        link_report_edge.ref, ArtifactRef, expected_kind="compiler.link_report"
    )
    treasury_plan_edge = next(
        artifact for artifact in compile_result.derived_refs if artifact.role == "treasury_plan"
    )
    treasury_plan_ref = _producer_output_ref(
        treasury_plan_edge.ref, ArtifactRef, expected_kind="foundry.treasury_plan"
    )
    program_graph = ProgramGraph.model_validate(_get_json_artifact(store, program_graph_ref))
    exec_plan = ExecPlan.model_validate(_get_json_artifact(store, exec_plan_ref))
    assert program_graph.ir_ref.artifact_id == raw_trinity_bundle_ref.artifact_id
    assert exec_plan.program_ref.artifact_id == program_graph_ref.artifact_id

    binding_build = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        return_selected_profile=True,
    )
    input_bindings_ref = _producer_output_ref(
        binding_build.input_bindings_ref,
        FoundryInputBindingsRef,
        expected_kind="foundry.input_bindings",
    )
    input_binding_report_ref = _producer_output_ref(
        binding_build.input_binding_report_ref,
        FoundryInputBindingReportRef,
        expected_kind="foundry.input_binding_report",
    )
    bound_state_snapshot_ref = _producer_output_ref(
        binding_build.bound_state_snapshot_ref,
        StateSnapshotRef,
        expected_kind="foundry.state_snapshot",
    )
    raw_feedback_config_ref = store.put_json(
        FeedbackConfig(mode="off"),
        PutOptions(
            kind="foundry.feedback_config",
            media_type="application/json",
            schema=SchemaInfo(
                name=FeedbackConfig.ARTIFACT_SCHEMA_NAME,
                version=FeedbackConfig.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[_input_edge(exec_plan_ref, role="exec_plan")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    feedback_config_ref = _producer_output_ref(
        raw_feedback_config_ref,
        FeedbackConfigRef,
        expected_kind="foundry.feedback_config",
    )
    raw_parameter_override_ref = store.put_json(
        ParameterOverrideBundle(
            overrides={"tax_cut": {"rate": 0.2}},
            sources={"tax_cut": ["explicit_fixed_step_test_input"]},
            notes=["non-empty fixed-step source-bound fixture"],
        ),
        PutOptions(
            kind=ParameterOverrideBundle.ARTIFACT_KIND,
            media_type=ParameterOverrideBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ParameterOverrideBundle.ARTIFACT_SCHEMA_NAME,
                version=ParameterOverrideBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[_input_edge(program_graph_ref, role="program_graph")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    parameter_override_ref = _producer_output_ref(
        raw_parameter_override_ref,
        ParameterOverrideBundleRef,
        expected_kind=ParameterOverrideBundle.ARTIFACT_KIND,
    )
    execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=binding_build.input_bindings_ref,
            registry_bundle_ref=registry_bundle_ref,
            feedback_config_ref=feedback_config_ref,
            parameter_override_bundle_ref=parameter_override_ref,
            return_selected_profile=True,
        ),
    )
    assert execution.ok, execution.notes
    assert execution.simulation_result_ref is not None
    simulation_result_ref = _producer_output_ref(
        execution.simulation_result_ref,
        SimulationResultRef,
        expected_kind="foundry.simulation_result",
    )
    simulation_result = SimulationResult.model_validate(
        _get_json_artifact(store, simulation_result_ref)
    )
    assert simulation_result.execution_input_basis_ref is not None
    execution_input_basis_ref = _producer_output_ref(
        simulation_result.execution_input_basis_ref,
        FoundryExecutionInputBasisRef,
        expected_kind="foundry.execution_input_basis",
    )
    basis = FoundryExecutionInputBasis.model_validate(
        _get_json_artifact(store, execution_input_basis_ref)
    )
    assert basis.parameter_overrides == {"tax_cut": {"rate": 0.2}}
    assert basis.parameter_override_bundle_ref is not None
    assert _ref_key(basis.parameter_override_bundle_ref) == _ref_key(parameter_override_ref)
    assert basis.request.parameter_override_bundle_ref is not None
    assert _ref_key(basis.request.parameter_override_bundle_ref) == _ref_key(parameter_override_ref)
    selected_override = ParameterOverrideBundle.model_validate(
        _get_json_artifact(store, parameter_override_ref)
    )
    assert selected_override.overrides == {"tax_cut": {"rate": 0.2}}
    _assert_parent_edges(
        store,
        execution_input_basis_ref,
        {"basis.source.parameter_override_bundle": parameter_override_ref},
    )
    metrics_ref = _producer_output_ref(
        simulation_result.metrics_ref, MetricsRef, expected_kind="foundry.metrics"
    )
    metrics = Metrics.model_validate(_get_json_artifact(store, metrics_ref))
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
        trinity_bundle_ref=_producer_output_ref(
            raw_trinity_bundle_ref, ArtifactRef, expected_kind="ir.trinity_bundle"
        ),
        program_graph_ref=program_graph_ref,
        link_report_ref=link_report_ref,
        exec_plan_ref=exec_plan_ref,
        treasury_plan_ref=treasury_plan_ref,
        input_bindings_ref=input_bindings_ref,
        input_binding_report_ref=input_binding_report_ref,
        simulation_result_ref=simulation_result_ref,
        execution_input_basis_ref=execution_input_basis_ref,
        metrics_ref=metrics_ref,
        intake_receipt_ref=intake.receipt_ref,
    )


def _selected_manifest(store: FileSystemCAS, value: object) -> tuple[ArtifactRef, Any]:
    ref = ArtifactRef.model_validate(_producer_ref_payload(value))
    assert ref.manifest_profile_sha256 is not None
    manifest = resolve_manifest_by_profile(store, ref.artifact_id, ref.manifest_profile_sha256)
    assert manifest.artifact_id == ref.artifact_id
    assert manifest.kind == ref.kind
    assert manifest.media_type == ref.media_type
    assert store.verify(ref).ok
    return ref, manifest


def _selected_ref_from_edge(store: FileSystemCAS, edge: InputRef) -> ArtifactRef:
    assert edge.manifest_profile_sha256 is not None
    manifest = resolve_manifest_by_profile(store, edge.artifact_id, edge.manifest_profile_sha256)
    ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    _selected_manifest(store, ref)
    return ref


def _manifest_edge(store: FileSystemCAS, ref: ArtifactRef, role: str) -> InputRef:
    _, manifest = _selected_manifest(store, ref)
    matches = [edge for edge in manifest.inputs if edge.role == role]
    assert len(matches) == 1, f"expected one {role} edge, found {len(matches)}"
    return matches[0]


def _ref_key(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    return (str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256)


def _persist_source_observation_variant(
    store: FileSystemCAS,
    source_ref: ArtifactRef,
    payload: Mapping[str, Any],
) -> tuple[ArtifactRef, Any]:
    """Persist a changed observation payload with its actual producer write envelope."""
    _, source_manifest = _selected_manifest(store, source_ref)
    assert source_manifest.artifact_schema is not None
    assert source_manifest.canon is not None
    canonical_spec = CanonSpec(**source_manifest.canon.model_dump(mode="python"))
    variant_ref = store.put_json(
        payload,
        PutOptions(
            kind=source_manifest.kind,
            media_type=source_manifest.media_type,
            schema=source_manifest.artifact_schema,
            producer=source_manifest.producer,
            env=source_manifest.env,
            inputs=source_manifest.inputs,
            canon=source_manifest.canon,
            governance=source_manifest.governance,
            tenant_context=source_manifest.tenant_context,
            same_input_closure=source_manifest.same_input_closure,
            authority=source_manifest.authority,
            warnings=source_manifest.warnings,
        ),
        canon_spec=canonical_spec,
        return_selected_profile=True,
    )
    return variant_ref, source_manifest


def test_source_ref_identity_uses_all_fields_not_pydantic_subclass() -> None:
    selected_profile = f"sha256:{'b' * 64}"
    base_ref = ArtifactRef(
        artifact_id=f"sha256:{'a' * 64}",
        kind="foundry.execution_input_basis",
        media_type="application/json",
        manifest_profile_sha256=selected_profile,
    )
    typed_ref = FoundryExecutionInputBasisRef.model_validate(base_ref.model_dump(mode="python"))
    assert type(typed_ref) is FoundryExecutionInputBasisRef
    assert _source_refs_equal(base_ref, typed_ref)

    def changed_ref(**updates: Any) -> ArtifactRef:
        return ArtifactRef.model_validate({**base_ref.model_dump(mode="python"), **updates})

    assert not _source_refs_equal(base_ref, changed_ref(artifact_id=f"sha256:{'c' * 64}"))
    assert not _source_refs_equal(base_ref, changed_ref(kind="foundry.other"))
    assert not _source_refs_equal(base_ref, changed_ref(media_type="application/cbor"))
    assert not _source_refs_equal(
        base_ref, changed_ref(manifest_profile_sha256=f"sha256:{'d' * 64}")
    )
    assert not _source_refs_equal(base_ref, changed_ref(manifest_profile_sha256=None))
    assert _source_identity_relation(base_ref, typed_ref) == "same_selected_ref"
    assert (
        _source_identity_relation(
            base_ref, changed_ref(manifest_profile_sha256=f"sha256:{'d' * 64}")
        )
        == "same_artifact_id_different_profile"
    )
    with pytest.raises(
        ValueError,
        match="source-bound risk refs share a profile but differ in kind or media type",
    ):
        _source_identity_relation(base_ref, changed_ref(kind="foundry.other"))


def _assert_parent_edges(
    store: FileSystemCAS,
    parent_ref: ArtifactRef,
    expected_children: dict[str, ArtifactRef],
) -> None:
    parent_ref, manifest = _selected_manifest(store, parent_ref)
    for role, child_ref in expected_children.items():
        child_ref, child_manifest = _selected_manifest(store, child_ref)
        matches = [edge for edge in manifest.inputs if edge.role == role]
        assert len(matches) == 1, f"expected one {role} edge on {parent_ref.kind}"
        edge = matches[0]
        assert (str(edge.artifact_id), edge.manifest_profile_sha256) == (
            str(child_ref.artifact_id),
            child_ref.manifest_profile_sha256,
        )
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
    assert source.execution_input_basis_ref is not None
    assert source.data_snapshot_ref.manifest_profile_sha256 is not None
    intake_receipt = from_canonical_bytes(store.get_bytes(source.intake_receipt_ref))
    assert intake_receipt["data_snapshot_ref"] == source.candidate_data_snapshot_ref.model_dump(
        mode="json"
    )
    intake_receipt_manifest = store.get_manifest(source.intake_receipt_ref)
    intake_snapshot_edges = [
        edge for edge in intake_receipt_manifest.inputs if edge.role == "data_snapshot"
    ]
    assert len(intake_snapshot_edges) == 1
    assert intake_snapshot_edges[0].artifact_id == source.candidate_data_snapshot_ref.artifact_id
    assert (
        intake_snapshot_edges[0].manifest_profile_sha256
        == source.candidate_data_snapshot_ref.manifest_profile_sha256
    )
    candidate = load_policy_candidate_schema(store, source.candidate_ref)
    trinity = TrinityBundle.model_validate(_get_json_artifact(store, source.trinity_bundle_ref))
    candidate_snapshot = DataSnapshot.model_validate(
        _get_json_artifact(store, source.candidate_data_snapshot_ref)
    )
    execution_snapshot = DataSnapshot.model_validate(
        _get_json_artifact(store, source.data_snapshot_ref)
    )
    bindings = load_input_bindings(store, source.input_bindings_ref)
    binding_report = _get_json_artifact(store, source.input_binding_report_ref)
    exec_plan = ExecPlan.model_validate(_get_json_artifact(store, source.exec_plan_ref))
    program_graph = ProgramGraph.model_validate(_get_json_artifact(store, source.program_graph_ref))
    simulation_result = SimulationResult.model_validate(
        _get_json_artifact(store, source.simulation_result_ref)
    )
    execution_basis = FoundryExecutionInputBasis.model_validate(
        _get_json_artifact(store, source.execution_input_basis_ref)
    )

    assert simulation_result.execution_source_status == "single_step_basis"
    assert _ref_key(simulation_result.execution_input_basis_ref) == _ref_key(
        source.execution_input_basis_ref
    )
    assert _ref_key(execution_basis.candidate_ref) == _ref_key(source.candidate_ref)
    assert _ref_key(execution_basis.exec_plan_ref) == _ref_key(source.exec_plan_ref)
    assert _ref_key(execution_basis.program_graph_ref) == _ref_key(source.program_graph_ref)
    assert _ref_key(execution_basis.trinity_bundle_ref) == _ref_key(source.trinity_bundle_ref)
    assert _ref_key(execution_basis.candidate_data_snapshot_ref) == _ref_key(
        source.candidate_data_snapshot_ref
    )
    assert _ref_key(execution_basis.data_snapshot_ref) == _ref_key(source.data_snapshot_ref)
    assert _ref_key(execution_basis.input_bindings_ref) == _ref_key(source.input_bindings_ref)
    assert execution_basis.request.return_selected_profile is True

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
    assert candidate_snapshot.uncertainty_envelope_ref is None
    assert execution_snapshot.uncertainty_envelope_ref is None
    assert _ref_key(bindings.data_snapshot_ref) == _ref_key(source.data_snapshot_ref)
    assert _ref_key(bindings.registry_bundle_ref) == _ref_key(source.registry_bundle_ref)
    assert _ref_key(bindings.bound_state_snapshot_ref) == _ref_key(source.bound_state_snapshot_ref)
    assert _ref_key(execution_basis.base_state_snapshot_ref) == _ref_key(
        source.bound_state_snapshot_ref
    )
    assert _ref_key(execution_basis.binding_registry_ref) == _ref_key(source.registry_bundle_ref)
    assert _ref_key(execution_basis.compile_registry_ref) == _ref_key(source.registry_bundle_ref)
    assert _ref_key(execution_basis.runtime_registry_ref) == _ref_key(source.registry_bundle_ref)
    assert binding_report["data_snapshot_ref"] == source.data_snapshot_ref.model_dump(mode="json")
    assert binding_report["registry_bundle_ref"] == source.registry_bundle_ref.model_dump(
        mode="json"
    )
    assert binding_report["bound_state_snapshot_ref"] == source.bound_state_snapshot_ref.model_dump(
        mode="json"
    )
    assert _ref_key(program_graph.ir_ref) == _ref_key(source.trinity_bundle_ref)
    assert _ref_key(exec_plan.program_ref) == _ref_key(source.program_graph_ref)
    assert _ref_key(simulation_result.exec_plan_ref) == _ref_key(source.exec_plan_ref)
    assert _ref_key(simulation_result.metrics_ref) == _ref_key(source.metrics_ref)
    state_delta_edge = _manifest_edge(store, source.simulation_result_ref, "state_delta")
    state_delta_ref = _selected_ref_from_edge(store, state_delta_edge)
    state_delta = StateDelta.model_validate(_get_json_artifact(store, state_delta_ref))
    assert _ref_key(state_delta.base_ref) == _ref_key(source.bound_state_snapshot_ref)
    assert (
        str(source.candidate_data_snapshot_ref.artifact_id)
        == str(source.data_snapshot_ref.artifact_id)
    ) is candidate_source_matches_run

    expected_lineage = (
        (
            source.candidate_data_snapshot_ref,
            {
                "data_ref": source.candidate_state_snapshot_ref,
            },
        ),
        (
            source.data_snapshot_ref,
            {
                "data_ref": source.state_snapshot_ref,
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
            {
                "ir": source.trinity_bundle_ref,
                "registry_bundle": source.registry_bundle_ref,
                "link_report": source.link_report_ref,
            },
        ),
        (
            source.exec_plan_ref,
            {"program_graph": source.program_graph_ref, "treasury_plan": source.treasury_plan_ref},
        ),
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
                "execution_input_basis": source.execution_input_basis_ref,
            },
        ),
        (
            source.metrics_ref,
            {"execution_input_basis": source.execution_input_basis_ref},
        ),
        (
            state_delta_ref,
            {"execution_input_basis": source.execution_input_basis_ref},
        ),
        (
            source.execution_input_basis_ref,
            {
                "basis.source.exec_plan": source.exec_plan_ref,
                "basis.source.program_graph": source.program_graph_ref,
                "basis.source.trinity_bundle": source.trinity_bundle_ref,
                "basis.source.candidate": source.candidate_ref,
                "basis.source.candidate_data_snapshot": source.candidate_data_snapshot_ref,
                "basis.source.actual_data_snapshot": source.data_snapshot_ref,
                "basis.source.input_bindings": source.input_bindings_ref,
                "basis.source.compile_registry_bundle": source.registry_bundle_ref,
                "basis.source.binding_registry_bundle": source.registry_bundle_ref,
                "basis.source.runtime_registry_bundle": source.registry_bundle_ref,
            },
        ),
        (
            welfare_ref,
            {
                "simulation_result": source.simulation_result_ref,
                "metrics": source.metrics_ref,
                "execution_input_basis": source.execution_input_basis_ref,
                "pe_uncertainty.applied_nodes": source.input_envelope_ref,
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
    raw_state_ref = put_state_snapshot(
        store, state=foreign_state, step=0, return_selected_profile=True
    )
    foreign_state_ref = _producer_output_ref(
        raw_state_ref, StateSnapshotRef, expected_kind="foundry.state_snapshot"
    )
    raw_data_ref = store.put_json(
        DataSnapshot(
            data_ref=foreign_state_ref,
            notes=["valid foreign DataSnapshot wrapper for candidate-source mismatch control"],
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[_input_edge(foreign_state_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    foreign_data_snapshot_ref = _producer_output_ref(
        raw_data_ref, DataSnapshotRef, expected_kind="fabric.data_snapshot"
    )
    binding_build = build_input_bindings(
        store,
        data_snapshot_ref=foreign_data_snapshot_ref,
        registry_bundle_ref=source.registry_bundle_ref,
        return_selected_profile=True,
    )
    execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=source.exec_plan_ref,
            input_bindings_ref=binding_build.input_bindings_ref,
            registry_bundle_ref=source.registry_bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert execution.ok, execution.notes
    assert execution.simulation_result_ref is not None
    result_ref = _producer_output_ref(
        execution.simulation_result_ref,
        SimulationResultRef,
        expected_kind="foundry.simulation_result",
    )
    result = SimulationResult.model_validate(_get_json_artifact(store, result_ref))
    metrics_ref = _producer_output_ref(
        result.metrics_ref, MetricsRef, expected_kind="foundry.metrics"
    )
    metrics = Metrics.model_validate(_get_json_artifact(store, metrics_ref))
    assert metrics.values["applied_nodes"] == 1
    assert result.execution_input_basis_ref is not None
    basis_ref = _producer_output_ref(
        result.execution_input_basis_ref,
        FoundryExecutionInputBasisRef,
        expected_kind="foundry.execution_input_basis",
    )
    return replace(
        source,
        data_snapshot_ref=foreign_data_snapshot_ref,
        state_snapshot_ref=foreign_state_ref,
        bound_state_snapshot_ref=binding_build.bound_state_snapshot_ref,
        input_bindings_ref=binding_build.input_bindings_ref,
        input_binding_report_ref=binding_build.input_binding_report_ref,
        simulation_result_ref=result_ref,
        execution_input_basis_ref=basis_ref,
        metrics_ref=metrics_ref,
    )


def _build_feedback_uncomposed_execution(source: _FoundrySource) -> _FoundrySource:
    store = source.store
    feedback_ref = prepare_trivial_feedback_config(
        store,
        exec_plan_ref=source.exec_plan_ref,
        return_selected_profile=True,
    )
    execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=source.exec_plan_ref,
            input_bindings_ref=source.input_bindings_ref,
            registry_bundle_ref=source.registry_bundle_ref,
            feedback_config_ref=feedback_ref,
            return_selected_profile=True,
        ),
    )
    assert execution.ok, execution.notes
    assert execution.simulation_result_ref is not None
    result_ref = _producer_output_ref(
        execution.simulation_result_ref,
        SimulationResultRef,
        expected_kind="foundry.simulation_result",
    )
    result = SimulationResult.model_validate(_get_json_artifact(store, result_ref))
    assert result.schema_version == "1.4"
    assert result.execution_source_status == "feedback_uncomposed"
    assert result.execution_input_basis_ref is None
    assert result.feedback_result_ref is not None
    result_manifest = _selected_manifest(store, result_ref)[1]
    assert not any(edge.role == "execution_input_basis" for edge in result_manifest.inputs)
    feedback_edge = _manifest_edge(store, result_ref, "artifact.feedback_result_ref")
    assert result.feedback_result_ref.manifest_profile_sha256 is not None
    assert (feedback_edge.artifact_id, feedback_edge.manifest_profile_sha256) == (
        result.feedback_result_ref.artifact_id,
        result.feedback_result_ref.manifest_profile_sha256,
    )
    _selected_manifest(store, result.feedback_result_ref)
    metrics_ref = _producer_output_ref(
        result.metrics_ref, MetricsRef, expected_kind="foundry.metrics"
    )
    return replace(
        source,
        simulation_result_ref=result_ref,
        execution_input_basis_ref=None,
        metrics_ref=metrics_ref,
    )


def _build_same_id_different_profile_execution(
    source: _FoundrySource, *, mismatch_data_ref_edge: bool = False
) -> _FoundrySource:
    store = source.store
    source_snapshot = DataSnapshot.model_validate(
        _get_json_artifact(store, source.data_snapshot_ref)
    )
    _, source_manifest = _selected_manifest(store, source.data_snapshot_ref)
    assert source_manifest.artifact_schema is not None
    if mismatch_data_ref_edge:
        raw_foreign_state_ref = put_state_snapshot(
            store,
            state=GlobalState.empty(n_agents=3, n_firms=1),
            step=0,
            return_selected_profile=True,
        )
        foreign_state_ref = _producer_output_ref(
            raw_foreign_state_ref, StateSnapshotRef, expected_kind="foundry.state_snapshot"
        )
        assert foreign_state_ref.manifest_profile_sha256 is not None
        source_data_edges = [edge for edge in source_manifest.inputs if edge.role == "data_ref"]
        assert len(source_data_edges) == 1
        alternate_inputs = [
            _input_edge(foreign_state_ref, role="data_ref") if edge.role == "data_ref" else edge
            for edge in source_manifest.inputs
        ]
    else:
        alternate_inputs = list(reversed(source_manifest.inputs))
    alternate_payload_ref = store.put_json(
        source_snapshot,
        PutOptions(
            kind=source_manifest.kind,
            media_type=source_manifest.media_type,
            schema=source_manifest.artifact_schema,
            inputs=alternate_inputs,
        ),
        return_selected_profile=True,
    )
    alternate_snapshot_ref = _producer_output_ref(
        alternate_payload_ref, DataSnapshotRef, expected_kind="fabric.data_snapshot"
    )
    assert alternate_snapshot_ref.artifact_id == source.data_snapshot_ref.artifact_id
    assert (
        alternate_snapshot_ref.manifest_profile_sha256
        != source.data_snapshot_ref.manifest_profile_sha256
    )

    if mismatch_data_ref_edge:
        # Preserve the real execution/basis and introduce only a consumer-side
        # source snapshot whose persisted edge disagrees with its typed ref.
        # The canonical binding owner already rejects this selected snapshot,
        # so do not claim a second execution was produced from it.
        return replace(source, data_snapshot_ref=alternate_snapshot_ref)

    binding_build = build_input_bindings(
        store,
        data_snapshot_ref=alternate_snapshot_ref,
        registry_bundle_ref=source.registry_bundle_ref,
        return_selected_profile=True,
    )
    execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=source.exec_plan_ref,
            input_bindings_ref=binding_build.input_bindings_ref,
            registry_bundle_ref=source.registry_bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert execution.ok, execution.notes
    assert execution.simulation_result_ref is not None
    result_ref = _producer_output_ref(
        execution.simulation_result_ref,
        SimulationResultRef,
        expected_kind="foundry.simulation_result",
    )
    result = SimulationResult.model_validate(_get_json_artifact(store, result_ref))
    assert result.execution_input_basis_ref is not None
    basis_ref = _producer_output_ref(
        result.execution_input_basis_ref,
        FoundryExecutionInputBasisRef,
        expected_kind="foundry.execution_input_basis",
    )
    metrics_ref = _producer_output_ref(
        result.metrics_ref, MetricsRef, expected_kind="foundry.metrics"
    )
    return replace(
        source,
        data_snapshot_ref=alternate_snapshot_ref,
        bound_state_snapshot_ref=binding_build.bound_state_snapshot_ref,
        input_bindings_ref=binding_build.input_bindings_ref,
        input_binding_report_ref=binding_build.input_binding_report_ref,
        simulation_result_ref=result_ref,
        execution_input_basis_ref=basis_ref,
        metrics_ref=metrics_ref,
    )


def _source_fixture(
    source: _FoundrySource,
    *,
    preferred_method: str = "monte_carlo",
    run_id: str = "R_b161_welfare",
    candidate_source_matches_run: bool = True,
    expect_feedback_uncomposed: bool = False,
    verify_source_lineage: bool = True,
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
                "policy_ref": source.candidate_ref.model_dump(mode="json"),
                "metric_order": ["applied_nodes", "op_nodes"],
                "weights": [2.0, 0.25],
                "input_envelopes": {
                    "applied_nodes": source.input_envelope_ref.model_dump(mode="json")
                },
                "welfare_social_weight_manifest": {
                    "ref": "swr://b161/source-bound-context@1.0.0#weights",
                    "method_fqn": "policy.welfare.state_dependent_inverse_social_weights@1.0.0",
                    "normalization": "mean_one",
                    "income_grid": [0.0, 1.0],
                    "weights_on_grid": [1.2, 0.8],
                    "state_keys": ["applied_nodes"],
                },
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
    assert bundle.pe_uncertainty_refs["applied_nodes"] == source.input_envelope_ref
    persisted_result_ref = maybe_artifact_ref(
        node_outcome.state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    )
    assert persisted_result_ref is not None
    persisted_result = SimulationResult.model_validate(
        _get_json_artifact(store, persisted_result_ref)
    )
    _, persisted_manifest = _selected_manifest(store, persisted_result_ref)
    basis_edges = [
        edge for edge in persisted_manifest.inputs if edge.role == "execution_input_basis"
    ]
    feedback_edges = [
        edge for edge in persisted_manifest.inputs if edge.role == "artifact.feedback_result_ref"
    ]
    if persisted_result.execution_input_basis_ref is None:
        assert not basis_edges
    else:
        assert len(basis_edges) == 1
        assert _selected_ref_from_edge(store, basis_edges[0]) == ArtifactRef.model_validate(
            persisted_result.execution_input_basis_ref.model_dump(mode="python")
        )
    if persisted_result.feedback_result_ref is None:
        assert not feedback_edges
    else:
        assert len(feedback_edges) == 1
        assert _selected_ref_from_edge(store, feedback_edges[0]) == ArtifactRef.model_validate(
            persisted_result.feedback_result_ref.model_dump(mode="python")
        )
    if expect_feedback_uncomposed:
        assert source.execution_input_basis_ref is None
        simulation_result = SimulationResult.model_validate(
            _get_json_artifact(store, source.simulation_result_ref)
        )
        assert simulation_result.execution_source_status == "feedback_uncomposed"
        assert simulation_result.execution_input_basis_ref is None
        _, simulation_manifest = _selected_manifest(store, source.simulation_result_ref)
        assert not any(edge.role == "execution_input_basis" for edge in simulation_manifest.inputs)
        _assert_parent_edges(
            store, welfare_ref, {"simulation_result": source.simulation_result_ref}
        )
    elif verify_source_lineage:
        _assert_actual_source_lineage(
            source,
            welfare_ref,
            bundle,
            candidate_source_matches_run=candidate_source_matches_run,
        )
    else:
        assert source.execution_input_basis_ref is not None
        actual_snapshot = DataSnapshot.model_validate(
            _get_json_artifact(store, source.data_snapshot_ref)
        )
        assert _ref_key(actual_snapshot.data_ref) == _ref_key(source.state_snapshot_ref)
        actual_edge = _manifest_edge(store, source.data_snapshot_ref, "data_ref")
        assert actual_edge.artifact_id != actual_snapshot.data_ref.artifact_id
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

    _, welfare_manifest = _selected_manifest(store, welfare_ref)
    method_ref = ArtifactRef.model_validate(bundle.method_config_ref.model_dump(mode="python"))
    method_config = _get_json_artifact(store, method_ref)
    assert method_config["preferred_method"] == "monte_carlo"
    method_edge = next(edge for edge in welfare_manifest.inputs if edge.role == "method_config")
    assert method_edge.artifact_id == method_ref.artifact_id
    assert method_edge.manifest_profile_sha256 == method_ref.manifest_profile_sha256
    basis_ref = _selected_ref_from_edge(
        store,
        next(edge for edge in welfare_manifest.inputs if edge.role == "execution_input_basis"),
    )
    _assert_parent_edges(store, method_ref, {"execution_input_basis": basis_ref})
    _assert_parent_edges(store, welfare_ref, {"execution_input_basis": basis_ref})

    report_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "propagation_report"
    )
    report_ref = _selected_ref_from_edge(store, report_edge)
    report_manifest = _selected_manifest(store, report_ref)[1]
    assert report_manifest.artifact_schema is not None
    assert report_manifest.artifact_schema.name == "polisyos.foundry.WelfarePropagationReport"
    report = _get_json_artifact(store, report_ref)
    assert report["methods"] == ["monte_carlo"]
    assert report["valid_draw_count"] == 100
    _assert_parent_edges(store, report_ref, {"execution_input_basis": basis_ref})

    sample_edge = next(edge for edge in welfare_manifest.inputs if edge.role == "sample_bundle")
    sample_ref = _selected_ref_from_edge(store, sample_edge)
    _assert_parent_edges(store, sample_ref, {"execution_input_basis": basis_ref})

    sample_bundle = load_welfare_sample_bundle(
        ensure_ir_artifact_store(store), bundle.sample_bundle_ref
    )
    bundle_manifest = store.get_manifest(welfare_ref)
    assert bundle.schema_version == "1.1"
    assert bundle_manifest.artifact_schema is not None
    assert bundle_manifest.artifact_schema.version == bundle.schema_version
    assert sample_bundle.schema_version == "1.1"
    assert len(sample_bundle.welfare_draws) == 100
    assert len(sample_bundle.welfare_pe_draws) == 100
    assert len(sample_bundle.welfare_ge_draws) == 100
    assert bundle.welfare_weights_ref is not None
    assert bundle.welfare_weights_ref.manifest_profile_sha256 is not None
    assert bundle.social_weight_ref is not None
    assert bundle.social_weight_ref.manifest_profile_sha256 is not None
    weights_ref = ArtifactRef.model_validate(bundle.welfare_weights_ref.model_dump(mode="python"))
    _assert_parent_edges(store, sample_ref, {"welfare_weights": weights_ref})
    weight_payload = _get_json_artifact(store, weights_ref)
    assert weight_payload == {"labels": ["applied_nodes", "op_nodes"], "weights": [2.0, 0.25]}
    assert weights_ref.manifest_profile_sha256 is not None
    assert sample_bundle.component_labels == tuple(weight_payload["labels"])
    assert bundle.nominal_component_labels == tuple(weight_payload["labels"])
    assert len(bundle.nominal_welfare_pe_components) == 2
    assert len(bundle.nominal_welfare_total_components) == 2
    simulation_ref = _selected_ref_from_edge(
        store, _manifest_edge(store, welfare_ref, "simulation_result")
    )
    simulation_result = SimulationResult.model_validate(_get_json_artifact(store, simulation_ref))
    metrics_ref = _selected_ref_from_edge(store, _manifest_edge(store, welfare_ref, "metrics"))
    metrics = Metrics.model_validate(_get_json_artifact(store, metrics_ref))
    assert _ref_key(simulation_result.metrics_ref) == _ref_key(metrics_ref)
    expected_pe_components = tuple(
        float(metrics.values[label]) for label in weight_payload["labels"]
    )
    assert bundle.nominal_welfare_pe_components == pytest.approx(expected_pe_components)
    expected_nominal_pe = float(
        np.dot(np.asarray(weight_payload["weights"], dtype=np.float64), expected_pe_components)
    )
    expected_nominal_total = float(
        np.dot(
            np.asarray(weight_payload["weights"], dtype=np.float64),
            np.asarray(bundle.nominal_welfare_total_components, dtype=np.float64),
        )
    )
    assert bundle.point_estimate == pytest.approx(expected_nominal_total, rel=1e-12, abs=1e-12)
    assert bundle.channel_decomposition["pe"] == pytest.approx(
        expected_nominal_pe, rel=1e-12, abs=1e-12
    )
    unweighted_total = float(sum(bundle.nominal_welfare_total_components))
    normalized_total = float(
        np.dot(
            np.asarray(weight_payload["weights"], dtype=np.float64)
            / sum(weight_payload["weights"]),
            np.asarray(bundle.nominal_welfare_total_components, dtype=np.float64),
        )
    )
    assert not np.isclose(expected_nominal_total, unweighted_total)
    assert not np.isclose(expected_nominal_total, normalized_total)
    assert len(sample_bundle.welfare_pe_component_draws) == 100
    assert len(sample_bundle.welfare_total_component_draws) == 100
    weights = weight_payload["weights"]
    for index, (pe_components, total_components) in enumerate(
        zip(
            sample_bundle.welfare_pe_component_draws,
            sample_bundle.welfare_total_component_draws,
            strict=True,
        )
    ):
        assert sum(
            w * value for w, value in zip(weights, pe_components, strict=True)
        ) == pytest.approx(sample_bundle.welfare_pe_draws[index], rel=1e-12, abs=1e-12)
        assert sum(
            w * value for w, value in zip(weights, total_components, strict=True)
        ) == pytest.approx(sample_bundle.welfare_draws[index], rel=1e-12, abs=1e-12)
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
        uncertainty_envelope=SearchUncertaintyEnvelope.unknown(),
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
    build_runtime_funnel_context(session)
    assert isinstance(session.funnel_context, dict)
    return session.funnel_context


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


def test_actual_foundry_basis_ref_survives_abm_ir_cas_roundtrip(
    foundry_source: _FoundrySource,
) -> None:
    source = foundry_source
    assert source.execution_input_basis_ref is not None
    assert source.execution_input_basis_ref.manifest_profile_sha256 is not None
    assert source.store.verify(source.execution_input_basis_ref).ok

    simulation = SimulationResult.model_validate(
        _get_json_artifact(source.store, source.simulation_result_ref)
    )
    assert simulation.execution_input_basis_ref is not None
    produced_basis_ref = _producer_output_ref(
        simulation.execution_input_basis_ref,
        FoundryExecutionInputBasisRef,
        expected_kind="foundry.execution_input_basis",
    )
    assert _ref_key(produced_basis_ref) == _ref_key(source.execution_input_basis_ref)
    assert simulation.execution_source_status == "single_step_basis"
    assert simulation.feedback_result_ref is None
    serialized_simulation = simulation.model_dump(mode="json")
    serialized_basis_ref = serialized_simulation["execution_input_basis_ref"]
    assert isinstance(serialized_basis_ref, dict)
    assert serialized_basis_ref["manifest_profile_sha256"] == (
        produced_basis_ref.manifest_profile_sha256
    )
    received_simulation = SimulationResult.model_validate(serialized_simulation)
    assert received_simulation.execution_source_status == "single_step_basis"
    assert received_simulation.execution_input_basis_ref == produced_basis_ref
    assert received_simulation == simulation
    basis = FoundryExecutionInputBasis.model_validate(
        _get_json_artifact(source.store, produced_basis_ref)
    )
    assert basis.execution_mode == "single_step"

    abm_result = build_abm_result_from_simulation(simulation)
    assert abm_result.execution_input_basis_ref is not None
    converted_basis_ref = ArtifactRef.model_validate(
        abm_result.execution_input_basis_ref.model_dump(mode="python")
    )
    assert _ref_key(converted_basis_ref) == _ref_key(produced_basis_ref)

    ir_store = ensure_ir_artifact_store(source.store)
    abm_ref = persist_abm_result(
        ir_store,
        abm_result,
        inputs=[_input_edge(produced_basis_ref, role="execution_input_basis")],
    )
    fresh_abm_result = load_abm_result(ir_store, abm_ref)
    assert fresh_abm_result == abm_result
    assert fresh_abm_result.execution_input_basis_ref is not None
    fresh_basis_ref = ArtifactRef.model_validate(
        fresh_abm_result.execution_input_basis_ref.model_dump(mode="python")
    )
    assert _ref_key(fresh_basis_ref) == _ref_key(produced_basis_ref)

    abm_core_ref = ArtifactRef.model_validate(abm_ref.model_dump(mode="python"))
    abm_manifest = source.store.get_manifest(abm_core_ref)
    basis_edges = [edge for edge in abm_manifest.inputs if edge.role == "execution_input_basis"]
    assert len(basis_edges) == 1
    assert (str(basis_edges[0].artifact_id), basis_edges[0].manifest_profile_sha256) == (
        str(produced_basis_ref.artifact_id),
        produced_basis_ref.manifest_profile_sha256,
    )


def test_actual_welfare_producer_persists_candidate_observation_for_fresh_funnel_consumer(
    source_bundle,
) -> None:
    from polisyos.scientist.methods.search.uncertainty import _source_typed_json_model

    store, candidate_ref, welfare_ref = source_bundle
    bundle = _assert_real_mixed_nested_monte_carlo_source(store, welfare_ref)
    welfare_manifest = store.get_manifest(welfare_ref)
    benchmark_context = _benchmark_funnel_context(store, candidate_ref, welfare_ref)
    assert benchmark_context["welfare_bundle_ref"] == welfare_ref

    outcome = _funnel_outcome(store, candidate_ref, welfare_ref, context=benchmark_context)
    observation_ref = next(ref for ref in outcome.audit_refs if ref.kind == _SOURCE_KIND)

    observation = load_source_bound_risk_observation(store, observation_ref, candidate_ref)

    assert observation.valid_draw_count == observation.successful_draw_count == 100
    assert observation.nominal_point_estimate == bundle.point_estimate
    assert observation.welfare_draw_mean > 0.0
    assert observation.welfare_draw_std >= 0.0
    assert observation.simulation_attempt_count >= observation.attempted_draw_count
    assert observation.retry_attempt_count == (
        observation.simulation_attempt_count - observation.attempted_draw_count
    )
    assert observation.credible_interval is not None
    assert observation.execution_source.candidate_to_execution_data_relation == "same_selected_ref"
    assert (
        observation.execution_source.candidate_to_compile_registry_relation == "same_selected_ref"
    )
    assert observation.execution_source.binding_to_runtime_registry_relation == "same_selected_ref"
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
    assert bundle.welfare_weights_ref is not None
    assert observation.welfare_weights_ref == ArtifactRef.model_validate(
        bundle.welfare_weights_ref.model_dump(mode="python")
    )
    assert observation.weight_application_status == "recomputed_from_component_draws"
    assert observation.valid_time is None
    assert observation.unit_binding_status == "not_established"
    assert observation.valid_time_status == "not_established"
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )

    # A payload schema-version disagreement in the actual ProgramGraph source must
    # stop the same fresh consumer from emitting a candidate observation.
    def persist_variant(ref: ArtifactRef, payload: object, inputs: list[InputRef]) -> ArtifactRef:
        manifest = store.get_manifest(ref)
        assert manifest.artifact_schema is not None
        assert manifest.canon is not None
        return store.put_json(
            payload,
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                producer=manifest.producer,
                env=manifest.env,
                inputs=inputs,
                canon=manifest.canon,
                governance=manifest.governance,
                tenant_context=manifest.tenant_context,
                same_input_closure=manifest.same_input_closure,
                authority=manifest.authority,
                warnings=manifest.warnings,
            ),
            canon_spec=CanonSpec(**manifest.canon.model_dump(mode="python")),
            return_selected_profile=True,
        )

    simulation_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "simulation_result"
    )
    simulation_ref = _selected_ref_from_edge(store, simulation_edge)
    simulation = _source_typed_json_model(store, SimulationResult, simulation_ref)
    assert simulation.execution_input_basis_ref is not None
    basis_ref = _producer_output_ref(
        simulation.execution_input_basis_ref,
        FoundryExecutionInputBasisRef,
        expected_kind="foundry.execution_input_basis",
    )
    basis = _source_typed_json_model(store, FoundryExecutionInputBasis, basis_ref)
    graph_ref = _producer_output_ref(
        basis.program_graph_ref, ProgramGraphRef, expected_kind="foundry.program_graph"
    )
    graph = _source_typed_json_model(store, ProgramGraph, graph_ref)
    assert graph.schema_version == "0.2"
    assert store.get_manifest(graph_ref).artifact_schema.version == "0.2.0"
    forged_graph_payload = graph.model_dump(mode="json") | {"schema_version": "0.3"}
    graph_manifest = store.get_manifest(graph_ref)
    assert graph_manifest.canon is not None
    forged_graph_ref = persist_variant(
        graph_ref,
        forged_graph_payload,
        graph_manifest.inputs,
    )
    forged_graph_ref = _producer_output_ref(
        forged_graph_ref, ProgramGraphRef, expected_kind="foundry.program_graph"
    )

    with pytest.raises(ValueError, match="canon_profile_typed_artifact_schema_version_mismatch"):
        _source_typed_json_model(store, ProgramGraph, forged_graph_ref)

    exec_plan_ref = _producer_output_ref(
        basis.exec_plan_ref, ExecPlanRef, expected_kind="foundry.exec_plan"
    )
    exec_plan = _source_typed_json_model(store, ExecPlan, exec_plan_ref)
    exec_plan_manifest = store.get_manifest(exec_plan_ref)
    forged_exec_plan_inputs = [
        _input_edge(forged_graph_ref, role=edge.role) if edge.role == "program_graph" else edge
        for edge in exec_plan_manifest.inputs
    ]
    assert sum(edge.role == "program_graph" for edge in exec_plan_manifest.inputs) == 1
    forged_exec_plan_ref = persist_variant(
        exec_plan_ref,
        exec_plan.model_copy(update={"program_ref": forged_graph_ref}).model_dump(mode="json"),
        forged_exec_plan_inputs,
    )
    forged_exec_plan_ref = _producer_output_ref(
        forged_exec_plan_ref, ExecPlanRef, expected_kind="foundry.exec_plan"
    )

    basis_manifest = store.get_manifest(basis_ref)
    basis_source_updates = {
        "basis.source.exec_plan": forged_exec_plan_ref,
        "basis.source.program_graph": forged_graph_ref,
        "basis.edge.exec_plan.program_graph": forged_graph_ref,
    }
    forged_basis_inputs = [
        _input_edge(basis_source_updates[edge.role], role=edge.role)
        if edge.role in basis_source_updates
        else edge
        for edge in basis_manifest.inputs
    ]
    assert set(basis_source_updates) <= {edge.role for edge in basis_manifest.inputs}
    forged_basis = basis.model_copy(
        update={
            "exec_plan_ref": forged_exec_plan_ref,
            "program_graph_ref": forged_graph_ref,
            "request": basis.request.model_copy(update={"exec_plan_ref": forged_exec_plan_ref}),
        }
    )
    forged_basis_ref = persist_variant(
        basis_ref,
        forged_basis.model_dump(mode="json"),
        forged_basis_inputs,
    )
    forged_basis_ref = _producer_output_ref(
        forged_basis_ref,
        FoundryExecutionInputBasisRef,
        expected_kind="foundry.execution_input_basis",
    )

    simulation_manifest = store.get_manifest(simulation_ref)
    assert simulation.exec_plan_ref is not None
    forged_simulation_inputs = [
        _input_edge(forged_exec_plan_ref, role=edge.role)
        if edge.role == "exec_plan"
        else _input_edge(forged_basis_ref, role=edge.role)
        if edge.role == "execution_input_basis"
        else edge
        for edge in simulation_manifest.inputs
    ]
    assert sum(edge.role == "exec_plan" for edge in simulation_manifest.inputs) == 1
    assert sum(edge.role == "execution_input_basis" for edge in simulation_manifest.inputs) == 1
    forged_simulation = simulation.model_copy(
        update={
            "exec_plan_ref": forged_exec_plan_ref,
            "execution_input_basis_ref": forged_basis_ref,
        }
    )
    forged_simulation_ref = persist_variant(
        simulation_ref,
        forged_simulation.model_dump(mode="json"),
        forged_simulation_inputs,
    )
    forged_simulation_ref = _producer_output_ref(
        forged_simulation_ref,
        SimulationResultRef,
        expected_kind="foundry.simulation_result",
    )
    forged_welfare_inputs = [
        _input_edge(forged_simulation_ref, role=edge.role)
        if edge.role == "simulation_result"
        else edge
        for edge in welfare_manifest.inputs
    ]
    forged_welfare_ref = _persist_welfare_bundle_view(store, bundle, forged_welfare_inputs)
    forged_outcome = _funnel_outcome(store, candidate_ref, forged_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in forged_outcome.audit_refs)
    assert forged_outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0
        for estimate in forged_outcome.uncertainty_envelope.uncertainties.values()
    )


def test_nominal_point_estimate_is_rederived_from_nominal_components(source_bundle) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.point_estimate is not None
    forged_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python") | {"point_estimate": bundle.point_estimate + 1.0}
    )
    forged_ref = _persist_welfare_bundle_view(
        store, forged_bundle, store.get_manifest(welfare_ref).inputs
    )
    assert (
        _get_json_artifact(store, forged_ref)["sample_bundle_ref"]
        == (_get_json_artifact(store, welfare_ref)["sample_bundle_ref"])
    )

    outcome = _funnel_outcome(store, candidate_ref, forged_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_nominal_component_source_change_is_withheld_with_markers_intact(source_bundle) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.nominal_welfare_total_components
    changed_components = (
        bundle.nominal_welfare_total_components[0] + 1.0,
        *bundle.nominal_welfare_total_components[1:],
    )
    forged_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python") | {"nominal_welfare_total_components": changed_components}
    )
    forged_ref = _persist_welfare_bundle_view(
        store, forged_bundle, store.get_manifest(welfare_ref).inputs
    )
    payload = _get_json_artifact(store, forged_ref)
    assert payload["point_estimate"] == _get_json_artifact(store, welfare_ref)["point_estimate"]
    assert (
        payload["sample_bundle_ref"] == _get_json_artifact(store, welfare_ref)["sample_bundle_ref"]
    )

    outcome = _funnel_outcome(store, candidate_ref, forged_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_missing_nominal_components_keeps_markers_but_is_withheld(source_bundle) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    forged_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python")
        | {
            "nominal_component_labels": (),
            "nominal_welfare_pe_components": (),
            "nominal_welfare_total_components": (),
        }
    )
    forged_ref = _persist_welfare_bundle_view(
        store, forged_bundle, store.get_manifest(welfare_ref).inputs
    )
    payload = _get_json_artifact(store, forged_ref)
    assert payload["point_estimate"] == _get_json_artifact(store, welfare_ref)["point_estimate"]
    assert (
        payload["sample_bundle_ref"] == _get_json_artifact(store, welfare_ref)["sample_bundle_ref"]
    )

    outcome = _funnel_outcome(store, candidate_ref, forged_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_weight_only_rebind_recomputes_mc_but_cannot_keep_stale_nominal_output(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    welfare_manifest = store.get_manifest(welfare_ref)
    assert bundle.welfare_weights_ref is not None
    assert bundle.sample_bundle_ref is not None
    weight_ref = ArtifactRef.model_validate(bundle.welfare_weights_ref.model_dump(mode="python"))
    sample_ref = ArtifactRef.model_validate(bundle.sample_bundle_ref.model_dump(mode="python"))
    _, weight_manifest = _selected_manifest(store, weight_ref)
    _, sample_manifest = _selected_manifest(store, sample_ref)
    assert sample_manifest.artifact_schema is not None
    alternate_payload = dict(_get_json_artifact(store, weight_ref))
    alternate_payload["weights"] = [0.5, 1.5]
    alternate_weight_ref = store.put_json(
        alternate_payload,
        PutOptions(
            kind=weight_ref.kind,
            media_type=weight_ref.media_type,
            schema=SchemaInfo(
                name=weight_manifest.artifact_schema.name,
                version=weight_manifest.artifact_schema.version,
            ),
            inputs=weight_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    sample = load_welfare_sample_bundle(ensure_ir_artifact_store(store), bundle.sample_bundle_ref)
    alternate_weights = np.asarray(alternate_payload["weights"], dtype=np.float64)
    pe_draws = [
        float(np.dot(alternate_weights, np.asarray(row, dtype=np.float64)))
        for row in sample.welfare_pe_component_draws
    ]
    total_draws = [
        float(np.dot(alternate_weights, np.asarray(row, dtype=np.float64)))
        for row in sample.welfare_total_component_draws
    ]
    ge_draws = [total - pe for total, pe in zip(total_draws, pe_draws, strict=True)]
    sample_payload = sample.model_dump(mode="json")
    sample_payload.update(
        {
            "welfare_pe_draws": pe_draws,
            "welfare_draws": total_draws,
            "welfare_ge_draws": ge_draws,
        }
    )
    sample_inputs = [
        _input_edge(alternate_weight_ref, role="welfare_weights")
        if edge.role == "welfare_weights"
        else edge
        for edge in sample_manifest.inputs
    ]
    alternate_sample_ref = store.put_json(
        sample_payload,
        PutOptions(
            kind=sample_ref.kind,
            media_type=sample_ref.media_type,
            schema=SchemaInfo(
                name=sample_manifest.artifact_schema.name,
                version=sample_manifest.artifact_schema.version,
            ),
            inputs=sample_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    report_ref = _selected_ref_from_edge(
        store, _manifest_edge(store, welfare_ref, "propagation_report")
    )
    _, report_manifest = _selected_manifest(store, report_ref)
    assert report_manifest.artifact_schema is not None
    report_payload = dict(_get_json_artifact(store, report_ref))
    new_summary = {
        "welfare_mean": float(np.mean(np.asarray(total_draws, dtype=np.float64))),
        "welfare_std": float(np.std(np.asarray(total_draws, dtype=np.float64))),
        "welfare_pe_mean": float(np.mean(np.asarray(pe_draws, dtype=np.float64))),
        "welfare_ge_mean": float(np.mean(np.asarray(ge_draws, dtype=np.float64))),
    }
    summary_key = "draw_summary" if "draw_summary" in report_payload else "conditional_draw_summary"
    report_payload[summary_key] = new_summary
    report_inputs = [
        _input_edge(alternate_sample_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else edge
        for edge in report_manifest.inputs
    ]
    alternate_report_ref = store.put_json(
        report_payload,
        PutOptions(
            kind=report_ref.kind,
            media_type=report_ref.media_type,
            schema=SchemaInfo(
                name=report_manifest.artifact_schema.name,
                version=report_manifest.artifact_schema.version,
            ),
            inputs=report_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert bundle.method_config_ref is not None
    method_ref = ArtifactRef.model_validate(bundle.method_config_ref.model_dump(mode="python"))
    method_config = _get_json_artifact(store, method_ref)
    alpha = max((1.0 - float(method_config["confidence_level"])) / 2.0, 0.0)
    alternate_interval = (
        float(np.quantile(np.asarray(total_draws, dtype=np.float64), alpha)),
        float(np.quantile(np.asarray(total_draws, dtype=np.float64), 1.0 - alpha)),
    )
    diagnostics = dict(bundle.diagnostics)
    diagnostics["propagation_report_ref"] = str(alternate_report_ref.artifact_id)
    alternate_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python")
        | {
            "welfare_weights_ref": alternate_weight_ref.model_dump(mode="python"),
            "sample_bundle_ref": alternate_sample_ref.model_dump(mode="python"),
            "credible_interval": alternate_interval,
            "diagnostics": diagnostics,
        }
    )
    bundle_inputs = [
        _input_edge(alternate_weight_ref, role="welfare_weights")
        if edge.role == "welfare_weights"
        else _input_edge(alternate_sample_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else _input_edge(alternate_report_ref, role="propagation_report")
        if edge.role == "propagation_report"
        else edge
        for edge in welfare_manifest.inputs
    ]
    alternate_welfare_ref = _persist_welfare_bundle_view(store, alternate_bundle, bundle_inputs)
    alternate_payload = _get_json_artifact(store, alternate_welfare_ref)
    assert (
        alternate_payload["point_estimate"]
        == _get_json_artifact(store, welfare_ref)["point_estimate"]
    )
    assert alternate_payload["welfare_weights_ref"] == alternate_weight_ref.model_dump(mode="json")
    assert _get_json_artifact(store, alternate_sample_ref)["welfare_draws"] == pytest.approx(
        total_draws
    )

    outcome = _funnel_outcome(store, candidate_ref, alternate_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_real_delta_producer_is_withheld_even_with_monte_carlo_sample_shape(
    source_pair,
) -> None:
    (
        (store, _, mc_welfare_ref),
        (
            delta_store,
            delta_candidate_ref,
            delta_welfare_ref,
        ),
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
    delta_config = _get_json_artifact(store, delta_method_ref)
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
    delta_report = _get_json_artifact(store, delta_report_ref)
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
    forged_inputs = [edge for edge in delta_manifest.inputs if edge.role != "sample_bundle"]
    forged_inputs.append(mc_sample_edge)
    forged_welfare_ref = _persist_welfare_bundle_view(store, forged_bundle, forged_inputs)

    outcome = _funnel_outcome(store, delta_candidate_ref, forged_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_missing_execution_basis_edge_is_not_rescued_by_source_markers(source_bundle) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    _, welfare_manifest = _selected_manifest(store, welfare_ref)
    simulation_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "simulation_result"
    )
    simulation_ref = _selected_ref_from_edge(store, simulation_edge)
    simulation = SimulationResult.model_validate(_get_json_artifact(store, simulation_ref))
    assert simulation.execution_source_status == "single_step_basis"
    assert simulation.execution_input_basis_ref is not None
    _, simulation_manifest = _selected_manifest(store, simulation_ref)
    assert any(edge.role == "execution_input_basis" for edge in simulation_manifest.inputs)
    assert simulation_manifest.artifact_schema is not None
    simulation_payload = _get_json_artifact(store, simulation_ref)
    assert isinstance(simulation_payload, Mapping)
    assert simulation_manifest.canon is not None
    marker_only_simulation_ref = store.put_json(
        simulation_payload,
        PutOptions(
            kind=simulation_manifest.kind,
            media_type=simulation_manifest.media_type,
            schema=simulation_manifest.artifact_schema,
            inputs=[
                edge for edge in simulation_manifest.inputs if edge.role != "execution_input_basis"
            ],
        ),
        canon_spec=CanonSpec(**simulation_manifest.canon.model_dump(mode="python")),
        return_selected_profile=True,
    )
    assert marker_only_simulation_ref.artifact_id == simulation_ref.artifact_id
    assert (
        marker_only_simulation_ref.manifest_profile_sha256 != simulation_ref.manifest_profile_sha256
    )
    marker_payload = SimulationResult.model_validate(
        _get_json_artifact(store, marker_only_simulation_ref)
    )
    assert marker_payload.execution_source_status == "single_step_basis"
    assert marker_payload.execution_input_basis_ref is not None

    marker_only_inputs = [
        InputRef(
            artifact_id=marker_only_simulation_ref.artifact_id,
            role=edge.role,
            manifest_profile_sha256=marker_only_simulation_ref.manifest_profile_sha256,
        )
        if edge.role == "simulation_result"
        else edge
        for edge in welfare_manifest.inputs
    ]
    marker_only_welfare_ref = _persist_welfare_bundle_view(store, bundle, marker_only_inputs)
    outcome = _funnel_outcome(store, candidate_ref, marker_only_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
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
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
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
    assert foreign_source.execution_input_basis_ref is not None
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
    assert (
        observation.execution_source.candidate_to_execution_data_relation == "different_artifact_id"
    )
    assert observation.scope_relation_status == "consumer_asserted"
    assert observation.refinement_status == "not_established"
    assert observation.risk_interpretation_status == "not_established"
    assert observation.unit_binding_status == "not_established"
    assert observation.valid_time_status == "not_established"
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_actual_feedback_source_is_uncomposed_and_fresh_consumer_withholds_it(
    foundry_source,
) -> None:
    feedback_source = _build_feedback_uncomposed_execution(foundry_source)
    store, candidate_ref, welfare_ref = _source_fixture(
        feedback_source,
        run_id="R_b161_feedback_uncomposed",
        expect_feedback_uncomposed=True,
    )
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.method_used is WelfareMethod.MIXED_NESTED
    assert bundle.sample_bundle_ref is not None

    with pytest.raises(ValueError, match="feedback execution basis is uncomposed"):
        persist_source_bound_risk_observation(
            store, candidate_ref=candidate_ref, welfare_bundle_ref=welfare_ref
        )

    outcome = _funnel_outcome(store, candidate_ref, welfare_ref)
    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_same_snapshot_bytes_with_a_different_selected_profile_stays_candidate_only(
    foundry_source,
) -> None:
    profiled_source = _build_same_id_different_profile_execution(foundry_source)
    store, candidate_ref, welfare_ref = _source_fixture(
        profiled_source, run_id="R_b161_same_id_different_profile"
    )
    _assert_actual_source_lineage(
        profiled_source,
        welfare_ref,
        load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref),
    )

    outcome = _funnel_outcome(store, candidate_ref, welfare_ref)

    observation_ref = next(ref for ref in outcome.audit_refs if ref.kind == _SOURCE_KIND)
    observation = load_source_bound_risk_observation(store, observation_ref, candidate_ref)
    assert observation.execution_source.candidate_to_execution_data_relation == (
        "same_artifact_id_different_profile"
    )
    assert observation.admission_status == "candidate_only"
    assert observation.risk_interpretation_status == "not_established"
    assert observation.refinement_status == "not_established"
    assert observation.unit is None
    assert observation.valid_time is None
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_manifest_data_ref_disagreement_is_rejected_before_execution(foundry_source) -> None:
    misbound_source = _build_same_id_different_profile_execution(
        foundry_source, mismatch_data_ref_edge=True
    )
    assert misbound_source.simulation_result_ref == foundry_source.simulation_result_ref
    assert misbound_source.execution_input_basis_ref == foundry_source.execution_input_basis_ref
    assert misbound_source.data_snapshot_ref != foundry_source.data_snapshot_ref

    with pytest.raises(
        ValueError,
        match="DataSnapshot selected nested reference lineage is not established: data_ref",
    ):
        build_input_bindings(
            misbound_source.store,
            data_snapshot_ref=misbound_source.data_snapshot_ref,
            registry_bundle_ref=misbound_source.registry_bundle_ref,
            return_selected_profile=True,
        )


def test_nonconformant_selected_core_profile_is_withheld_with_source_markers_intact(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    _assert_real_mixed_nested_monte_carlo_source(store, welfare_ref)
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    welfare_manifest = store.get_manifest(welfare_ref)
    simulation_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "simulation_result"
    )
    simulation_ref = _selected_ref_from_edge(store, simulation_edge)
    simulation_manifest = store.get_manifest(simulation_ref)
    simulation_result = SimulationResult.model_validate(_get_json_artifact(store, simulation_ref))
    metrics_ref = _producer_output_ref(
        simulation_result.metrics_ref, MetricsRef, expected_kind="foundry.metrics"
    )
    metrics_manifest = store.get_manifest(metrics_ref)
    metrics = Metrics.model_validate(_get_json_artifact(store, metrics_ref))
    false_profile_spec = CanonSpec(forbid_floats=True, exclude_none=False)
    forged_values = dict(metrics.values)
    forged_values["profile_conformance_probe"] = 0.125
    forged_metrics_payload = metrics.model_dump(mode="json") | {"values": forged_values}
    forged_metrics_bytes = to_canonical_bytes(
        forged_metrics_payload,
        CanonSpec(forbid_floats=False, exclude_none=False),
    )
    false_profile_ref = store.put_bytes(
        forged_metrics_bytes,
        PutOptions(
            kind=metrics_ref.kind,
            media_type=metrics_ref.media_type,
            schema=metrics_manifest.artifact_schema,
            inputs=metrics_manifest.inputs,
            canon=CanonInfo.from_spec(false_profile_spec),
        ),
        return_selected_profile=True,
    )
    false_profile_metrics_ref = MetricsRef.model_validate(
        false_profile_ref.model_dump(mode="python")
    )
    false_profile_manifest = store.get_manifest(false_profile_metrics_ref)
    assert store.verify(false_profile_metrics_ref).ok
    assert false_profile_metrics_ref.manifest_profile_sha256 is not None
    assert false_profile_manifest.artifact_schema == metrics_manifest.artifact_schema
    assert false_profile_manifest.canon == CanonInfo.from_spec(false_profile_spec)
    assert any(edge.role == "execution_input_basis" for edge in false_profile_manifest.inputs)

    simulation_payload = simulation_result.model_dump(mode="json")
    simulation_payload["metrics_ref"] = false_profile_metrics_ref.model_dump(mode="json")
    forged_simulation = SimulationResult.model_validate(simulation_payload)
    simulation_inputs = [
        _input_edge(false_profile_metrics_ref, role="metrics") if edge.role == "metrics" else edge
        for edge in simulation_manifest.inputs
    ]
    assert sum(edge.role == "metrics" for edge in simulation_manifest.inputs) == 1
    assert [edge for edge in simulation_inputs if edge.role != "metrics"] == [
        edge for edge in simulation_manifest.inputs if edge.role != "metrics"
    ]
    forged_simulation_ref = store.put_json(
        forged_simulation,
        PutOptions(
            kind=simulation_ref.kind,
            media_type=simulation_ref.media_type,
            schema=simulation_manifest.artifact_schema,
            inputs=simulation_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    forged_welfare_inputs = [
        _input_edge(forged_simulation_ref, role="simulation_result")
        if edge.role == "simulation_result"
        else _input_edge(false_profile_metrics_ref, role="metrics")
        if edge.role == "metrics"
        else edge
        for edge in welfare_manifest.inputs
    ]
    assert sum(edge.role == "simulation_result" for edge in welfare_manifest.inputs) == 1
    assert sum(edge.role == "metrics" for edge in welfare_manifest.inputs) == 1
    assert [
        edge for edge in forged_welfare_inputs if edge.role not in {"simulation_result", "metrics"}
    ] == [
        edge
        for edge in welfare_manifest.inputs
        if edge.role not in {"simulation_result", "metrics"}
    ]
    forged_welfare_ref = _persist_welfare_bundle_view(store, bundle, forged_welfare_inputs)
    assert _ref_key(
        _selected_ref_from_edge(store, _manifest_edge(store, forged_simulation_ref, "metrics"))
    ) == _ref_key(false_profile_metrics_ref)
    assert _ref_key(
        _selected_ref_from_edge(store, _manifest_edge(store, forged_welfare_ref, "metrics"))
    ) == _ref_key(false_profile_metrics_ref)

    outcome = _funnel_outcome(store, candidate_ref, forged_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_generic_core_source_reader_rejects_bad_profiles_for_the_typed_source_quantity(
    source_bundle,
) -> None:
    from polisyos.scientist.methods.search.uncertainty import _source_typed_json_model

    store, candidate_ref, welfare_ref = source_bundle
    welfare_manifest = store.get_manifest(welfare_ref)
    simulation_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "simulation_result"
    )
    simulation_ref = _selected_ref_from_edge(store, simulation_edge)
    simulation = _source_typed_json_model(store, SimulationResult, simulation_ref)
    assert simulation.execution_input_basis_ref is not None
    basis_ref = _producer_output_ref(
        simulation.execution_input_basis_ref,
        ArtifactRef,
        expected_kind="foundry.execution_input_basis",
    )
    basis = _source_typed_json_model(store, FoundryExecutionInputBasis, basis_ref)
    assert basis.request.feedback_config_ref is not None
    exec_plan_ref = _producer_output_ref(
        basis.exec_plan_ref, ArtifactRef, expected_kind="foundry.exec_plan"
    )
    exec_plan = _source_typed_json_model(store, ExecPlan, exec_plan_ref)
    graph_ref = _producer_output_ref(
        exec_plan.program_ref, ArtifactRef, expected_kind="foundry.program_graph"
    )
    state_delta_edge = next(
        edge for edge in store.get_manifest(simulation_ref).inputs if edge.role == "state_delta"
    )
    source_models = [
        (SimulationResult, simulation_ref),
        (FoundryExecutionInputBasis, basis_ref),
        (ExecPlan, exec_plan_ref),
        (ProgramGraph, graph_ref),
        (TrinityBundle, basis.trinity_bundle_ref),
        (FoundryInputBindings, basis.input_bindings_ref),
        (DataSnapshot, basis.candidate_data_snapshot_ref),
        (DataSnapshot, basis.data_snapshot_ref),
        (FeedbackConfig, basis.request.feedback_config_ref),
        (StateDelta, _selected_ref_from_edge(store, state_delta_edge)),
        (Metrics, simulation.metrics_ref),
        (PolicyCandidateSchema, candidate_ref),
    ]
    assert basis.parameter_override_bundle_ref is not None
    source_models.append((ParameterOverrideBundle, basis.parameter_override_bundle_ref))
    assert len({model for model, _ in source_models}) == 12

    owner_kinds = {model.ARTIFACT_KIND for model, _ in source_models}
    for model, raw_ref in source_models:
        ref = ArtifactRef.model_validate(raw_ref.model_dump(mode="python"))
        conformant_value = _source_typed_json_model(store, model, ref)
        assert isinstance(conformant_value, model)
        manifest = store.get_manifest(ref)
        assert manifest.artifact_schema is not None
        assert ref.kind == manifest.kind == model.ARTIFACT_KIND
        assert ref.media_type == manifest.media_type == model.ARTIFACT_MEDIA_TYPE
        original_bytes = store.get_bytes(ref)
        false_profile_ref = store.put_bytes(
            original_bytes,
            PutOptions(
                kind=ref.kind,
                media_type=ref.media_type,
                schema=manifest.artifact_schema,
                inputs=manifest.inputs,
                canon=CanonInfo.from_spec(CanonSpec(max_depth=1)),
            ),
            return_selected_profile=True,
        )
        assert false_profile_ref.artifact_id == ref.artifact_id
        assert false_profile_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
        assert store.verify(false_profile_ref).ok
        false_profile_manifest = store.get_manifest(false_profile_ref)
        assert false_profile_manifest.kind == manifest.kind
        assert false_profile_manifest.media_type == manifest.media_type
        assert false_profile_manifest.artifact_schema == manifest.artifact_schema
        assert false_profile_manifest.canon == CanonInfo.from_spec(CanonSpec(max_depth=1))
        assert false_profile_manifest.inputs == manifest.inputs
        assert store.get_bytes(false_profile_ref) == original_bytes

        with pytest.raises(ValueError, match="canon_profile"):
            _source_typed_json_model(store, model, false_profile_ref)

        expected_schema = SchemaInfo(
            name=model.ARTIFACT_SCHEMA_NAME,
            version=model.ARTIFACT_SCHEMA_VERSION,
        )
        assert manifest.artifact_schema == expected_schema
        for alias_schema in (
            SchemaInfo(name=f"alias.{expected_schema.name}", version=expected_schema.version),
            SchemaInfo(name=expected_schema.name, version="99.99.99"),
        ):
            alias_ref = store.put_bytes(
                original_bytes,
                PutOptions(
                    kind=ref.kind,
                    media_type=ref.media_type,
                    schema=alias_schema,
                    inputs=manifest.inputs,
                    canon=manifest.canon,
                ),
                return_selected_profile=True,
            )
            assert alias_ref.artifact_id == ref.artifact_id
            assert alias_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
            assert store.verify(alias_ref).ok
            alias_manifest = store.get_manifest(alias_ref)
            assert alias_manifest.kind == manifest.kind
            assert alias_manifest.media_type == manifest.media_type
            assert alias_manifest.artifact_schema == alias_schema
            assert alias_manifest.canon == manifest.canon
            assert alias_manifest.inputs == manifest.inputs
            assert store.get_bytes(alias_ref) == original_bytes

            with pytest.raises(ValueError, match="schema"):
                _source_typed_json_model(store, model, alias_ref)

        wrong_identity_options = (
            ("kind", next(kind for kind in owner_kinds if kind != model.ARTIFACT_KIND)),
            ("media_type", "application/vnd.b161.source-alias+json"),
        )
        for identity_field, wrong_value in wrong_identity_options:
            alias_options = {
                "kind": wrong_value if identity_field == "kind" else ref.kind,
                "media_type": (wrong_value if identity_field == "media_type" else ref.media_type),
            }
            alias_ref = store.put_bytes(
                original_bytes,
                PutOptions(
                    **alias_options,
                    schema=manifest.artifact_schema,
                    inputs=manifest.inputs,
                    canon=manifest.canon,
                ),
                return_selected_profile=True,
            )
            assert alias_ref.artifact_id == ref.artifact_id
            assert alias_ref.manifest_profile_sha256 is not None
            assert alias_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
            assert store.verify(alias_ref).ok
            alias_manifest = store.get_manifest(alias_ref)
            assert alias_manifest.artifact_schema == manifest.artifact_schema
            assert alias_manifest.inputs == manifest.inputs
            assert alias_manifest.canon == manifest.canon
            assert store.get_bytes(alias_ref) == original_bytes
            assert alias_manifest.kind == alias_ref.kind == alias_options["kind"]
            assert alias_manifest.media_type == alias_ref.media_type == alias_options["media_type"]
            failure = "kind" if identity_field == "kind" else "media type"
            with pytest.raises(ValueError, match=failure):
                _source_typed_json_model(store, model, alias_ref)


@pytest.mark.parametrize("basis_mutation", ["kind", "media_type", "schema_version"])
def test_fresh_observation_consumer_rejects_mutated_execution_basis_ref(
    source_bundle, basis_mutation: str
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    welfare_ref, welfare_manifest = _selected_manifest(store, welfare_ref)
    simulation_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "simulation_result"
    )
    simulation_ref = _selected_ref_from_edge(store, simulation_edge)
    simulation_manifest = store.get_manifest(simulation_ref)
    simulation_payload = dict(_get_json_artifact(store, simulation_ref))
    simulation = SimulationResult.model_validate(simulation_payload)
    assert simulation.execution_source_status == "single_step_basis"
    assert simulation.feedback_result_ref is None
    assert simulation.schema_version == "1.4"
    assert simulation.execution_input_basis_ref is not None
    basis_payload = simulation_payload["execution_input_basis_ref"]
    assert isinstance(basis_payload, dict)
    basis_ref = _producer_output_ref(
        basis_payload,
        FoundryExecutionInputBasisRef,
        expected_kind="foundry.execution_input_basis",
    )
    basis_manifest = store.get_manifest(basis_ref)
    assert basis_manifest.artifact_schema is not None
    assert basis_manifest.canon is not None
    assert basis_ref.manifest_profile_sha256 is not None
    selected_basis_bytes = store.get_bytes(basis_ref)
    assert store.verify(basis_ref).ok

    def _variant_options(
        ref: ArtifactRef,
        *,
        inputs: list[InputRef] | None = None,
        schema: SchemaInfo | None = None,
    ) -> PutOptions:
        manifest = store.get_manifest(ref)
        return PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=schema if schema is not None else manifest.artifact_schema,
            producer=manifest.producer,
            env=manifest.env,
            inputs=inputs if inputs is not None else manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        )

    def _put_json_variant(
        ref: ArtifactRef,
        payload: Mapping[str, Any],
        *,
        inputs: list[InputRef],
    ) -> ArtifactRef:
        manifest = store.get_manifest(ref)
        assert manifest.canon is not None
        return store.put_json(
            payload,
            _variant_options(ref, inputs=inputs),
            canon_spec=CanonSpec(**manifest.canon.model_dump(mode="python")),
            return_selected_profile=True,
        )

    selected_basis_ref = basis_ref
    changed_basis_payload = dict(basis_payload)
    if basis_mutation == "kind":
        changed_basis_payload["kind"] = "foundry.invalid_execution_input_basis"
    elif basis_mutation == "media_type":
        changed_basis_payload["media_type"] = "application/vnd.invalid-execution-basis+json"
    else:
        alias_schema = SchemaInfo(name=basis_manifest.artifact_schema.name, version="99.99.99")
        selected_basis_ref = store.put_bytes(
            selected_basis_bytes,
            _variant_options(basis_ref, schema=alias_schema),
            return_selected_profile=True,
        )
        assert selected_basis_ref.artifact_id == basis_ref.artifact_id
        assert selected_basis_ref.manifest_profile_sha256 is not None
        assert selected_basis_ref.manifest_profile_sha256 != basis_ref.manifest_profile_sha256
        alias_manifest = store.get_manifest(selected_basis_ref)
        assert alias_manifest.kind == basis_ref.kind
        assert alias_manifest.media_type == basis_ref.media_type
        assert alias_manifest.artifact_schema == alias_schema
        assert alias_manifest.inputs == basis_manifest.inputs
        assert store.get_bytes(selected_basis_ref) == selected_basis_bytes
        changed_basis_payload["manifest_profile_sha256"] = (
            selected_basis_ref.manifest_profile_sha256
        )

    changed_basis_field = (
        "manifest_profile_sha256" if basis_mutation == "schema_version" else basis_mutation
    )
    assert {
        key: value for key, value in changed_basis_payload.items() if key != changed_basis_field
    } == {key: value for key, value in basis_payload.items() if key != changed_basis_field}
    assert changed_basis_payload["artifact_id"] == basis_payload["artifact_id"]

    changed_simulation_payload = dict(simulation_payload)
    changed_simulation_payload["execution_input_basis_ref"] = changed_basis_payload
    assert {
        key: value
        for key, value in changed_simulation_payload.items()
        if key != "execution_input_basis_ref"
    } == {
        key: value
        for key, value in simulation_payload.items()
        if key != "execution_input_basis_ref"
    }
    simulation_inputs = [
        _input_edge(selected_basis_ref, role=edge.role)
        if edge.role == "execution_input_basis"
        else edge
        for edge in simulation_manifest.inputs
    ]
    assert sum(edge.role == "execution_input_basis" for edge in simulation_inputs) == 1
    bad_simulation_ref = _put_json_variant(
        simulation_ref, changed_simulation_payload, inputs=simulation_inputs
    )
    bad_simulation_manifest = store.get_manifest(bad_simulation_ref)
    assert bad_simulation_ref.kind == simulation_ref.kind
    assert bad_simulation_ref.media_type == simulation_ref.media_type
    assert bad_simulation_ref.manifest_profile_sha256 is not None
    assert bad_simulation_manifest.artifact_schema == simulation_manifest.artifact_schema
    assert bad_simulation_manifest.canon == simulation_manifest.canon
    assert bad_simulation_manifest.inputs == simulation_inputs
    assert store.verify(bad_simulation_ref).ok
    assert store.get_bytes(basis_ref) == selected_basis_bytes

    welfare_inputs = [
        _input_edge(bad_simulation_ref, role=edge.role)
        if edge.role == "simulation_result"
        else _input_edge(selected_basis_ref, role=edge.role)
        if basis_mutation == "schema_version" and edge.role == "execution_input_basis"
        else edge
        for edge in welfare_manifest.inputs
    ]
    assert sum(edge.role == "simulation_result" for edge in welfare_inputs) == 1
    welfare_payload = dict(_get_json_artifact(store, welfare_ref))
    bad_welfare_ref = _put_json_variant(welfare_ref, welfare_payload, inputs=welfare_inputs)
    bad_welfare_manifest = store.get_manifest(bad_welfare_ref)
    assert bad_welfare_manifest.artifact_schema == welfare_manifest.artifact_schema
    assert bad_welfare_manifest.producer == welfare_manifest.producer
    assert bad_welfare_manifest.canon == welfare_manifest.canon
    assert bad_welfare_manifest.inputs == welfare_inputs
    assert _get_json_artifact(store, bad_welfare_ref) == welfare_payload

    original_outcome = _funnel_outcome(store, candidate_ref, welfare_ref)
    observation_ref = next(ref for ref in original_outcome.audit_refs if ref.kind == _SOURCE_KIND)
    original_observation = load_source_bound_risk_observation(store, observation_ref, candidate_ref)
    observation_manifest = store.get_manifest(observation_ref)
    observation_payload = dict(_get_json_artifact(store, observation_ref))
    bad_observation_payload = dict(observation_payload)
    bad_observation_payload["welfare_bundle_ref"] = bad_welfare_ref.model_dump(mode="json")
    assert {
        key: value for key, value in bad_observation_payload.items() if key != "welfare_bundle_ref"
    } == {key: value for key, value in observation_payload.items() if key != "welfare_bundle_ref"}
    assert original_observation.risk_interpretation_status == "not_established"
    assert original_observation.refinement_status == "not_established"
    assert original_observation.scope_relation_status == "consumer_asserted"

    changed_observation_inputs = []
    basis_alias_roles = {
        "welfare_bundle.execution_input_basis",
        "simulation_result.execution_input_basis",
        "execution.input_basis",
    }
    for edge in observation_manifest.inputs:
        if edge.role == "source_welfare_bundle":
            changed_observation_inputs.append(_input_edge(bad_welfare_ref, role=edge.role))
        elif edge.role in {"welfare_bundle.simulation_result", "execution.simulation_result"}:
            changed_observation_inputs.append(_input_edge(bad_simulation_ref, role=edge.role))
        elif basis_mutation == "schema_version" and edge.role in basis_alias_roles:
            changed_observation_inputs.append(_input_edge(selected_basis_ref, role=edge.role))
        else:
            changed_observation_inputs.append(edge)
    bad_observation_ref = _put_json_variant(
        observation_ref, bad_observation_payload, inputs=changed_observation_inputs
    )
    bad_observation_manifest = store.get_manifest(bad_observation_ref)
    assert bad_observation_manifest.artifact_schema == observation_manifest.artifact_schema
    assert bad_observation_manifest.kind == observation_manifest.kind
    assert bad_observation_manifest.media_type == observation_manifest.media_type
    assert store.verify(bad_observation_ref).ok

    expected_failure = {
        "kind": r"execution_input_basis_ref\.kind",
        "media_type": r"execution_input_basis_ref\.media_type",
        "schema_version": "source-bound risk execution basis schema mismatch",
    }[basis_mutation]
    with pytest.raises(ValueError, match=expected_failure):
        load_source_bound_risk_observation(store, bad_observation_ref, candidate_ref)


@pytest.mark.parametrize("edge_role", ["simulation_result", "state_delta"])
@pytest.mark.parametrize("identity_field", ["kind", "media_type"])
def test_fresh_consumer_rejects_wrong_typed_parent_edge_identity_with_markers_intact(
    source_bundle, edge_role: str, identity_field: str
) -> None:
    from polisyos.scientist.methods.search.uncertainty import _source_typed_json_model

    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    welfare_ref, welfare_manifest = _selected_manifest(store, welfare_ref)
    simulation_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "simulation_result"
    )
    simulation_ref = _selected_ref_from_edge(store, simulation_edge)
    if edge_role == "simulation_result":
        source_ref = simulation_ref
        expected_model = SimulationResult
    else:
        simulation_manifest = store.get_manifest(simulation_ref)
        delta_edge = next(edge for edge in simulation_manifest.inputs if edge.role == "state_delta")
        source_ref = _selected_ref_from_edge(store, delta_edge)
        expected_model = StateDelta

    source_manifest = store.get_manifest(source_ref)
    source_bytes = store.get_bytes(source_ref)
    if identity_field == "kind":
        wrong_kind = next(
            model.ARTIFACT_KIND
            for model in (SimulationResult, StateDelta, Metrics, ProgramGraph)
            if model.ARTIFACT_KIND != expected_model.ARTIFACT_KIND
        )
        wrong_media_type = source_ref.media_type
    else:
        wrong_kind = source_ref.kind
        wrong_media_type = "application/vnd.b161.parent-edge-alias+json"
    alias_ref = store.put_bytes(
        source_bytes,
        PutOptions(
            kind=wrong_kind,
            media_type=wrong_media_type,
            schema=source_manifest.artifact_schema,
            inputs=source_manifest.inputs,
            canon=source_manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert alias_ref.artifact_id == source_ref.artifact_id
    assert alias_ref.manifest_profile_sha256 is not None
    assert alias_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
    assert store.verify(alias_ref).ok
    alias_manifest = store.get_manifest(alias_ref)
    assert alias_manifest.kind == wrong_kind
    assert alias_manifest.media_type == wrong_media_type
    assert alias_manifest.artifact_schema == source_manifest.artifact_schema
    assert alias_manifest.inputs == source_manifest.inputs
    assert alias_manifest.canon == source_manifest.canon
    assert store.get_bytes(alias_ref) == source_bytes

    if edge_role == "simulation_result":
        changed_welfare_inputs = [
            _input_edge(alias_ref, role="simulation_result")
            if edge.role == "simulation_result"
            else edge
            for edge in welfare_manifest.inputs
        ]
        tampered_welfare_ref = _persist_welfare_bundle_view(store, bundle, changed_welfare_inputs)
    else:
        simulation_payload = _source_typed_json_model(store, SimulationResult, simulation_ref)
        assert isinstance(simulation_payload, SimulationResult)
        simulation_manifest = store.get_manifest(simulation_ref)
        changed_simulation_inputs = [
            _input_edge(alias_ref, role="state_delta") if edge.role == "state_delta" else edge
            for edge in simulation_manifest.inputs
        ]
        tampered_simulation_ref = store.put_bytes(
            store.get_bytes(simulation_ref),
            PutOptions(
                kind=simulation_ref.kind,
                media_type=simulation_ref.media_type,
                schema=simulation_manifest.artifact_schema,
                inputs=changed_simulation_inputs,
                canon=simulation_manifest.canon,
            ),
            return_selected_profile=True,
        )
        assert tampered_simulation_ref.artifact_id == simulation_ref.artifact_id
        assert store.get_bytes(tampered_simulation_ref) == store.get_bytes(simulation_ref)
        changed_welfare_inputs = [
            _input_edge(tampered_simulation_ref, role="simulation_result")
            if edge.role == "simulation_result"
            else edge
            for edge in welfare_manifest.inputs
        ]
        tampered_welfare_ref = _persist_welfare_bundle_view(store, bundle, changed_welfare_inputs)

    # Preserve the actual WelfareNode producer's MC/report/sample properties and markers.
    actual_bundle = _assert_real_mixed_nested_monte_carlo_source(store, tampered_welfare_ref)
    assert actual_bundle.method_used is WelfareMethod.MIXED_NESTED
    assert actual_bundle.sample_bundle_ref is not None
    outcome = _funnel_outcome(store, candidate_ref, tampered_welfare_ref)
    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_selected_method_profile_must_match_the_welfare_source_edge(source_bundle) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.method_config_ref is not None
    method_ref = ArtifactRef.model_validate(bundle.method_config_ref.model_dump(mode="python"))
    method_manifest = store.get_manifest(method_ref)
    alternate_method_ref = store.put_json(
        _get_json_artifact(store, method_ref),
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


@pytest.mark.parametrize(
    "role",
    [
        "policy_scope_claim",
        "welfare_weights",
        "social_weight_manifest",
        "method_config",
        "propagation_report",
        "sample_bundle",
        "simulation_result",
        "metrics",
        "execution_input_basis",
    ],
)
def test_welfare_bundle_role_edges_are_required_even_when_payload_markers_remain(
    source_bundle, role: str
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    _, original_manifest = _selected_manifest(store, welfare_ref)
    original_bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    original_payload = _get_json_artifact(store, welfare_ref)
    assert any(edge.role == role for edge in original_manifest.inputs)
    tampered_inputs = [edge for edge in original_manifest.inputs if edge.role != role]
    tampered_ref = _persist_welfare_bundle_view(store, original_bundle, tampered_inputs)
    assert _get_json_artifact(store, tampered_ref) == original_payload

    outcome = _funnel_outcome(store, candidate_ref, tampered_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


@pytest.mark.parametrize(
    "role", ["policy_scope_claim", "welfare_weights", "social_weight_manifest"]
)
def test_typed_welfare_refs_must_match_their_manifest_roles(source_bundle, role: str) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    _, welfare_manifest = _selected_manifest(store, welfare_ref)
    if role == "policy_scope_claim":
        alternate_ref = _candidate_ref(
            store, "candidate_role_edge_foreign", return_selected_profile=True
        )
    elif role == "welfare_weights":
        assert bundle.welfare_weights_ref is not None
        weight_ref = ArtifactRef.model_validate(
            bundle.welfare_weights_ref.model_dump(mode="python")
        )
        _, weight_manifest = _selected_manifest(store, weight_ref)
        alternate_payload = dict(_get_json_artifact(store, weight_ref))
        alternate_payload["weights"] = [
            float(value) + 0.25 for value in alternate_payload["weights"]
        ]
        alternate_ref = store.put_json(
            alternate_payload,
            PutOptions(
                kind=weight_ref.kind,
                media_type=weight_ref.media_type,
                schema=SchemaInfo(
                    name=weight_manifest.artifact_schema.name,
                    version=weight_manifest.artifact_schema.version,
                ),
                inputs=weight_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    else:
        assert bundle.social_weight_ref is not None
        social_ref = ArtifactRef.model_validate(bundle.social_weight_ref.model_dump(mode="python"))
        _, social_manifest = _selected_manifest(store, social_ref)
        alternate_payload = dict(_get_json_artifact(store, social_ref))
        alternate_payload["method_fqn"] = "policy.welfare.foreign_method@1.0.0"
        alternate_ref = store.put_json(
            alternate_payload,
            PutOptions(
                kind=social_ref.kind,
                media_type=social_ref.media_type,
                schema=SchemaInfo(
                    name=social_manifest.artifact_schema.name,
                    version=social_manifest.artifact_schema.version,
                ),
                inputs=social_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    assert alternate_ref.manifest_profile_sha256 is not None
    original_payload = _get_json_artifact(store, welfare_ref)
    redirected_inputs = [
        _input_edge(alternate_ref, role=role) if edge.role == role else edge
        for edge in welfare_manifest.inputs
    ]
    assert any(edge.role == role for edge in welfare_manifest.inputs)
    redirected_ref = _persist_welfare_bundle_view(store, bundle, redirected_inputs)
    assert _get_json_artifact(store, redirected_ref) == original_payload

    outcome = _funnel_outcome(store, candidate_ref, redirected_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_removed_weighted_component_vectors_keep_mc_markers_but_are_withheld(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.sample_bundle_ref is not None
    sample_ref = ArtifactRef.model_validate(bundle.sample_bundle_ref.model_dump(mode="python"))
    _, sample_manifest = _selected_manifest(store, sample_ref)
    sample_payload = dict(_get_json_artifact(store, sample_ref))
    sample_payload["component_labels"] = []
    sample_payload["welfare_pe_component_draws"] = []
    sample_payload["welfare_total_component_draws"] = []
    sample_without_vectors_ref = store.put_json(
        sample_payload,
        PutOptions(
            kind=sample_ref.kind,
            media_type=sample_ref.media_type,
            schema=SchemaInfo(
                name=sample_manifest.artifact_schema.name,
                version=sample_manifest.artifact_schema.version,
            ),
            inputs=sample_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    report_edge = _manifest_edge(store, welfare_ref, "propagation_report")
    report_ref = _selected_ref_from_edge(store, report_edge)
    _, report_manifest = _selected_manifest(store, report_ref)
    report_payload = _get_json_artifact(store, report_ref)
    report_inputs = [
        _input_edge(sample_without_vectors_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else edge
        for edge in report_manifest.inputs
    ]
    report_without_vectors_ref = store.put_json(
        report_payload,
        PutOptions(
            kind=report_ref.kind,
            media_type=report_ref.media_type,
            schema=SchemaInfo(
                name=report_manifest.artifact_schema.name,
                version=report_manifest.artifact_schema.version,
            ),
            inputs=report_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    changed_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python")
        | {"sample_bundle_ref": sample_without_vectors_ref.model_dump(mode="python")}
    )
    welfare_manifest = _selected_manifest(store, welfare_ref)[1]
    welfare_inputs = [
        _input_edge(sample_without_vectors_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else _input_edge(report_without_vectors_ref, role="propagation_report")
        if edge.role == "propagation_report"
        else edge
        for edge in welfare_manifest.inputs
    ]
    changed_welfare_ref = _persist_welfare_bundle_view(store, changed_bundle, welfare_inputs)
    assert sample_payload["welfare_draws"] == _get_json_artifact(store, sample_ref)["welfare_draws"]
    assert (
        sample_payload["welfare_pe_draws"]
        == _get_json_artifact(store, sample_ref)["welfare_pe_draws"]
    )
    assert report_payload["valid_draw_count"] == 100
    assert (
        report_payload["draw_outcome_provenance"]
        == _get_json_artifact(store, report_ref)["draw_outcome_provenance"]
    )

    outcome = _funnel_outcome(store, candidate_ref, changed_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_weight_payload_change_cannot_relabel_existing_mc_sample_as_weighted_by_new_source(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.welfare_weights_ref is not None
    assert bundle.sample_bundle_ref is not None
    weight_ref = ArtifactRef.model_validate(bundle.welfare_weights_ref.model_dump(mode="python"))
    sample_ref = ArtifactRef.model_validate(bundle.sample_bundle_ref.model_dump(mode="python"))
    _, weight_manifest = _selected_manifest(store, weight_ref)
    _, sample_manifest = _selected_manifest(store, sample_ref)
    assert sample_manifest.artifact_schema is not None

    changed_weights = dict(_get_json_artifact(store, weight_ref))
    changed_weights["weights"] = [float(value) * 2.0 for value in changed_weights["weights"]]
    changed_weight_ref = store.put_json(
        changed_weights,
        PutOptions(
            kind=weight_ref.kind,
            media_type=weight_ref.media_type,
            schema=SchemaInfo(
                name=weight_manifest.artifact_schema.name,
                version=weight_manifest.artifact_schema.version,
            ),
            inputs=weight_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert changed_weight_ref.manifest_profile_sha256 is not None
    assert changed_weight_ref.artifact_id != weight_ref.artifact_id

    sample_payload = _get_json_artifact(store, sample_ref)
    changed_sample_inputs = [
        _input_edge(changed_weight_ref, role="welfare_weights")
        if edge.role == "welfare_weights"
        else edge
        for edge in sample_manifest.inputs
    ]
    changed_sample_ref = store.put_json(
        sample_payload,
        PutOptions(
            kind=sample_ref.kind,
            media_type=sample_ref.media_type,
            schema=SchemaInfo(
                name=sample_manifest.artifact_schema.name,
                version=sample_manifest.artifact_schema.version,
            ),
            inputs=changed_sample_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert _get_json_artifact(store, changed_sample_ref) == sample_payload

    original_manifest = _selected_manifest(store, welfare_ref)[1]
    report_ref = _selected_ref_from_edge(
        store, _manifest_edge(store, welfare_ref, "propagation_report")
    )
    _, report_manifest = _selected_manifest(store, report_ref)
    report_payload = _get_json_artifact(store, report_ref)
    changed_report_inputs = [
        _input_edge(changed_sample_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else edge
        for edge in report_manifest.inputs
    ]
    changed_report_ref = store.put_json(
        report_payload,
        PutOptions(
            kind=report_ref.kind,
            media_type=report_ref.media_type,
            schema=SchemaInfo(
                name=report_manifest.artifact_schema.name,
                version=report_manifest.artifact_schema.version,
            ),
            inputs=changed_report_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    changed_inputs = [
        _input_edge(changed_weight_ref, role="welfare_weights")
        if edge.role == "welfare_weights"
        else _input_edge(changed_sample_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else _input_edge(changed_report_ref, role="propagation_report")
        if edge.role == "propagation_report"
        else edge
        for edge in original_manifest.inputs
    ]
    changed_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python")
        | {
            "welfare_weights_ref": changed_weight_ref.model_dump(mode="python"),
            "sample_bundle_ref": changed_sample_ref.model_dump(mode="python"),
        }
    )
    changed_welfare_ref = _persist_welfare_bundle_view(store, changed_bundle, changed_inputs)
    changed_payload = _get_json_artifact(store, changed_welfare_ref)
    original_payload = _get_json_artifact(store, welfare_ref)
    assert changed_payload["sample_bundle_ref"] == changed_sample_ref.model_dump(mode="json")
    assert changed_payload["method_config_ref"] == original_payload["method_config_ref"]
    assert changed_payload["method_used"] == original_payload["method_used"]
    assert report_payload["valid_draw_count"] == 100
    assert (
        _get_json_artifact(store, changed_report_ref)["draw_outcome_provenance"]
        == (report_payload["draw_outcome_provenance"])
    )

    outcome = _funnel_outcome(store, candidate_ref, changed_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_sample_weight_edge_mismatch_keeps_mc_markers_but_is_withheld(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    bundle = load_welfare_bundle(ensure_ir_artifact_store(store), welfare_ref)
    assert bundle.sample_bundle_ref is not None
    assert bundle.welfare_weights_ref is not None
    sample_ref = ArtifactRef.model_validate(bundle.sample_bundle_ref.model_dump(mode="python"))
    weights_ref = ArtifactRef.model_validate(bundle.welfare_weights_ref.model_dump(mode="python"))
    _, sample_manifest = _selected_manifest(store, sample_ref)
    _, weight_manifest = _selected_manifest(store, weights_ref)
    assert sample_manifest.artifact_schema is not None
    assert any(edge.role == "welfare_weights" for edge in sample_manifest.inputs)

    alternate_payload = dict(_get_json_artifact(store, weights_ref))
    alternate_payload["weights"] = [float(value) + 0.25 for value in alternate_payload["weights"]]
    alternate_weights_ref = store.put_json(
        alternate_payload,
        PutOptions(
            kind=weights_ref.kind,
            media_type=weights_ref.media_type,
            schema=SchemaInfo(
                name=weight_manifest.artifact_schema.name,
                version=weight_manifest.artifact_schema.version,
            ),
            inputs=weight_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert alternate_weights_ref.manifest_profile_sha256 is not None
    assert alternate_weights_ref.artifact_id != weights_ref.artifact_id

    sample_payload = _get_json_artifact(store, sample_ref)
    redirected_sample_inputs = [
        _input_edge(alternate_weights_ref, role="welfare_weights")
        if edge.role == "welfare_weights"
        else edge
        for edge in sample_manifest.inputs
    ]
    redirected_sample_ref = store.put_json(
        sample_payload,
        PutOptions(
            kind=sample_ref.kind,
            media_type=sample_ref.media_type,
            schema=SchemaInfo(
                name=sample_manifest.artifact_schema.name,
                version=sample_manifest.artifact_schema.version,
            ),
            inputs=redirected_sample_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert _get_json_artifact(store, redirected_sample_ref) == sample_payload

    welfare_manifest = _selected_manifest(store, welfare_ref)[1]
    report_ref = _selected_ref_from_edge(
        store, _manifest_edge(store, welfare_ref, "propagation_report")
    )
    _, report_manifest = _selected_manifest(store, report_ref)
    report_payload = _get_json_artifact(store, report_ref)
    redirected_report_inputs = [
        _input_edge(redirected_sample_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else edge
        for edge in report_manifest.inputs
    ]
    redirected_report_ref = store.put_json(
        report_payload,
        PutOptions(
            kind=report_ref.kind,
            media_type=report_ref.media_type,
            schema=SchemaInfo(
                name=report_manifest.artifact_schema.name,
                version=report_manifest.artifact_schema.version,
            ),
            inputs=redirected_report_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    changed_bundle = WelfareBundle.model_validate(
        bundle.model_dump(mode="python")
        | {"sample_bundle_ref": redirected_sample_ref.model_dump(mode="python")}
    )
    redirected_welfare_inputs = [
        _input_edge(redirected_sample_ref, role="sample_bundle")
        if edge.role == "sample_bundle"
        else _input_edge(redirected_report_ref, role="propagation_report")
        if edge.role == "propagation_report"
        else edge
        for edge in welfare_manifest.inputs
    ]
    changed_welfare_ref = _persist_welfare_bundle_view(
        store, changed_bundle, redirected_welfare_inputs
    )
    assert changed_bundle.method_used is bundle.method_used
    assert changed_bundle.welfare_weights_ref == bundle.welfare_weights_ref
    assert (
        _get_json_artifact(store, changed_welfare_ref)["method_used"]
        == (_get_json_artifact(store, welfare_ref)["method_used"])
    )
    assert report_payload["valid_draw_count"] == 100

    outcome = _funnel_outcome(store, candidate_ref, changed_welfare_ref)

    assert all(ref.kind != _SOURCE_KIND for ref in outcome.audit_refs)
    assert outcome.current_uncertainty_envelope is None
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


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
    _, welfare_manifest = _selected_manifest(store, welfare_ref)
    report_edge = next(
        edge for edge in welfare_manifest.inputs if edge.role == "propagation_report"
    )
    report_ref = ArtifactRef(
        artifact_id=report_edge.artifact_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
        manifest_profile_sha256=report_edge.manifest_profile_sha256,
    )
    report_manifest = store.get_manifest(report_ref)
    report_payload = _get_json_artifact(store, report_ref)
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
    assert all(
        estimate.level == 1.0 for estimate in outcome.uncertainty_envelope.uncertainties.values()
    )


def test_fresh_reader_rejects_changed_count_while_candidate_markers_remain(
    source_bundle,
) -> None:
    store, candidate_ref, welfare_ref = source_bundle
    outcome = _funnel_outcome(store, candidate_ref, welfare_ref)
    observation_ref = next(ref for ref in outcome.audit_refs if ref.kind == _SOURCE_KIND)
    observation = load_source_bound_risk_observation(store, observation_ref, candidate_ref)
    original_payload = observation.model_dump(mode="json")
    forged = SourceBoundRiskObservation.model_validate(
        observation.model_dump(mode="python")
        | {"valid_draw_count": observation.valid_draw_count + 1}
    )
    forged_payload = forged.model_dump(mode="json")
    assert forged_payload["valid_draw_count"] == observation.valid_draw_count + 1
    assert {key: value for key, value in forged_payload.items() if key != "valid_draw_count"} == {
        key: value for key, value in original_payload.items() if key != "valid_draw_count"
    }

    forged_ref, source_manifest = _persist_source_observation_variant(
        store, observation_ref, forged_payload
    )
    forged_ref, forged_manifest = _selected_manifest(store, forged_ref)
    assert forged_ref.manifest_profile_sha256 is not None
    dynamic_manifest_fields = {"artifact_id", "byte_size", "created_at", "integrity"}
    assert forged_manifest.model_dump(mode="python", exclude=dynamic_manifest_fields) == (
        source_manifest.model_dump(mode="python", exclude=dynamic_manifest_fields)
    )
    assert forged.risk_interpretation_status == "not_established"
    with pytest.raises(ValueError, match="recomputed source contents"):
        load_source_bound_risk_observation(store, forged_ref, candidate_ref)
