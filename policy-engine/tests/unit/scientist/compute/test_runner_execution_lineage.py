from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts import (
    CoreJsonReadBoundsRefusalError,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    read_core_manifest_profile_bounded,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecPlanRef,
    LoweredIR,
    LoweredIRRef,
    MethodExecutionBundle,
    MethodMetricBinding,
    MethodMetricBindingSet,
    MethodMetricBindingSetRef,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)
from polisyos.ir.kernel.method_metrics import (
    METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
    METHOD_METRIC_UNIT_ADAPTER_ID,
    METHOD_METRIC_UNIT_ADAPTER_VERSION,
    MethodMetricSemanticContract,
    MethodMetricSourceUnit,
    registered_method_metric_law_metadata,
    registered_method_metric_unit_adapter_metadata,
    resolve_registered_method_metric_unit_adapter,
)
from polisyos.ir.kernel.units import RateUnit
from polisyos.scientist.compute.job_spec import JobKey, JobResult, JobSpec
from polisyos.scientist.compute.runner import (
    ExecutionResult,
    LocalBackend,
    RunnerBackend,
    read_job_result_method_execution_capture,
    run_job,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


class _LegacyBackend(RunnerBackend):
    def __init__(self, *, exec_artifacts: Any, snapshot_ref: Any, final_state: Any) -> None:
        self._exec_artifacts = exec_artifacts
        self._snapshot_ref = snapshot_ref
        self._final_state = final_state

    def run(self, **kwargs: Any) -> ExecutionResult:
        del kwargs
        return ExecutionResult(
            exec_artifacts=self._exec_artifacts,
            applied=SimpleNamespace(state_snapshot_ref=self._snapshot_ref),
            final_state=self._final_state,
        )


class _HTEInputMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="lineage_hte_input",
        namespace="causal.hte",
        version="1.0.0",
        input_slots=frozenset(
            {SlotSpec("hte_data", SlotType.VECTOR, Unit("dimensionless", "array"))}
        ),
        output_slots=frozenset(
            {SlotSpec("values", SlotType.VECTOR, Unit("dimensionless", "array"))}
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="lineage HTE input")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        del params
        return {"values": np.asarray(state["hte_data"])}


def _selected_ref(
    store: FileSystemCAS,
    *,
    kind: str,
    schema_name: str,
    value: Any,
    schema_version: str = "1.0.0",
) -> ArtifactRef:
    return store.put_json(
        value,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
        return_selected_profile=True,
    )


def _summary_ref(store: FileSystemCAS, *, inputs: list[Any]) -> ArtifactRef:
    return store.put_json(
        {"avg_income": 105.0, "n_agents": 2, "gov_balance": 1.5, "step": 7},
        PutOptions(
            kind="scientist.simulation_results",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.SimulationResults",
                version="0.1.0",
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _legacy_job_result(
    tmp_path,
    *,
    exec_artifacts: Any,
) -> tuple[FileSystemCAS, JobResult]:
    store = FileSystemCAS(tmp_path)
    program_ref = _selected_ref(
        store,
        kind="foundry.program_graph",
        schema_name="tests.ProgramGraph",
        value={"nodes": []},
    )
    exec_plan_ref = _selected_ref(
        store,
        kind="foundry.exec_plan",
        schema_name="tests.ExecPlan",
        value={"nodes": []},
    )
    base_snapshot_ref = _selected_ref(
        store,
        kind="foundry.state_snapshot",
        schema_name="tests.StateSnapshot",
        value={"step": 6},
    )
    state_delta_ref = _selected_ref(
        store,
        kind="foundry.state_delta",
        schema_name="tests.StateDelta",
        value={"updates": []},
    )
    metrics_ref = _selected_ref(
        store,
        kind="foundry.metrics",
        schema_name="tests.Metrics",
        value={"metrics": []},
    )
    applied_snapshot_ref = _selected_ref(
        store,
        kind="foundry.state_snapshot",
        schema_name="tests.StateSnapshot",
        value={"step": 7},
    )
    artifacts = SimpleNamespace(
        state_delta_ref=state_delta_ref,
        metrics_ref=metrics_ref,
        environment_ref=None,
        environment_fingerprint=None,
        **exec_artifacts,
    )
    final_state = SimpleNamespace(
        agents=SimpleNamespace(income=np.asarray([100.0, 110.0])),
        government_balance=1.5,
        step=7,
    )
    result = run_job(
        JobSpec(
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            state_snapshot_ref=base_snapshot_ref,
        ),
        backend=_LegacyBackend(
            exec_artifacts=artifacts,
            snapshot_ref=applied_snapshot_ref,
            final_state=final_state,
        ),
        registry_content=SimpleNamespace(),
        base_state=SimpleNamespace(step=6),
        cas_root=tmp_path,
    )
    return store, result


class _CapturedGraphMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="legacy_lineage_scalar",
        namespace="tests.scientist.compute_lineage",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("ratio", "ratio"))}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="real graph method for legacy execution lineage integration"
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, float]:
        del state, params
        return {"result": 0.25}


def _put_selected_contract_model(
    store: FileSystemCAS,
    payload: Any,
    *,
    kind: str,
    inputs: list[Any] | None = None,
) -> ArtifactRef:
    payload_type = type(payload)
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(
                name=payload_type.ARTIFACT_SCHEMA_NAME,
                version=payload_type.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _real_binding_graph_and_plan(
    store: FileSystemCAS,
) -> tuple[ProgramGraphRef, ExecPlanRef, MethodMetricBindingSetRef]:
    policy_ref = _selected_ref(
        store,
        kind="ir.trinity_bundle",
        schema_name="tests.LineagePolicy",
        value={"candidate": "legacy-lineage-capture"},
    )
    registry_ref = _selected_ref(
        store,
        kind="core.registry_bundle",
        schema_name="tests.LineageRegistry",
        value={"candidate": "registry"},
    )
    metric_registry_ref = _selected_ref(
        store,
        kind="ir.metric_registry",
        schema_name="tests.LineageMetricRegistry",
        value={"candidate": "metrics"},
    )
    units_registry_ref = _selected_ref(
        store,
        kind="ir.units_registry",
        schema_name="tests.LineageUnitsRegistry",
        value={"candidate": "units"},
    )
    lowered_ir_ref = _put_selected_contract_model(
        store,
        LoweredIR(ir_ref=policy_ref, mechanisms=[], constraints=[]),
        kind=LoweredIRRef.model_fields["kind"].default,
    )
    lowered_ir_typed_ref = LoweredIRRef.model_validate(lowered_ir_ref.model_dump(mode="python"))
    graph = ProgramGraph(
        ir_ref=policy_ref,
        lowered_ir_ref=lowered_ir_typed_ref,
        nodes=[
            ProgramNode(
                node_id="lineage_method",
                node_kind="method",
                method_fqn=_CapturedGraphMethod.signature.fqn,
                method_version=_CapturedGraphMethod.signature.version,
            )
        ],
        edges=[],
        entrypoints=["lineage_method"],
    )
    graph_ref = _put_selected_contract_model(
        store,
        graph,
        kind=ProgramGraph.ARTIFACT_KIND,
        inputs=[input_ref_from_artifact_ref(lowered_ir_ref, role="lowered_ir")],
    )
    typed_graph_ref = ProgramGraphRef.model_validate(graph_ref.model_dump(mode="python"))

    source_unit = MethodMetricSourceUnit(dimension="ratio", symbol="ratio", scale=1.0)
    target_unit = RateUnit(base="ratio")
    adapter = resolve_registered_method_metric_unit_adapter(source_unit, target_unit)
    law_id, law_version, law_digest = registered_method_metric_law_metadata()
    adapter_id, adapter_version, adapter_digest = registered_method_metric_unit_adapter_metadata()
    signature = _CapturedGraphMethod.signature
    binding = MethodMetricBinding(
        binding_id="metric.binding.legacy_lineage_scalar",
        objective_id="objective.legacy_lineage_scalar",
        metric_id="metric.legacy_lineage_scalar",
        node_id="lineage_method",
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=signature.abi_digest(),
        method_abi_digest_algorithm="blake2b",
        method_build_digest=None,
        method_build_digest_scope="unavailable",
        output_slot_id="result",
        output_shape="scalar",
        semantics=MethodMetricSemanticContract(
            quantity_kind="economic.rate",
            quantity_role="outcome.level",
            population_id="population.eligible",
            axes=("time.simulation_step",),
            denominator_id="population.eligible",
            time_role="period.end",
            producer_contract_id="producer.policy_metric.v1",
        ),
        source_unit=source_unit,
        target_unit=target_unit,
        law_id=METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
        law_version=law_version,
        law_code_digest=law_digest,
        adapter_id=METHOD_METRIC_UNIT_ADAPTER_ID,
        adapter_version=METHOD_METRIC_UNIT_ADAPTER_VERSION,
        adapter_code_digest=adapter.code_digest or adapter_digest,
        conversion_operation=adapter.operation,
        conversion_factor_numerator=adapter.factor_numerator,
        conversion_factor_denominator=adapter.factor_denominator,
        availability="unavailable",
        limitation="test_only_unregistered_metric_semantics",
    )
    assert law_id == METHOD_METRIC_DIRECT_OUTPUT_LAW_ID
    assert adapter_id == METHOD_METRIC_UNIT_ADAPTER_ID
    assert adapter_version == METHOD_METRIC_UNIT_ADAPTER_VERSION
    binding_set = MethodMetricBindingSet(
        program_graph_ref=typed_graph_ref,
        policy_ref=policy_ref,
        registry_bundle_ref=registry_ref,
        metric_registry_ref=metric_registry_ref,
        units_registry_ref=units_registry_ref,
        bindings=[binding],
    )
    binding_set_ref = _put_selected_contract_model(
        store,
        binding_set,
        kind=MethodMetricBindingSet.ARTIFACT_KIND,
        inputs=[
            input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(policy_ref, role="policy"),
            input_ref_from_artifact_ref(registry_ref, role="registry_bundle"),
            input_ref_from_artifact_ref(metric_registry_ref, role="metric_registry"),
            input_ref_from_artifact_ref(units_registry_ref, role="units_registry"),
        ],
    )
    typed_binding_set_ref = MethodMetricBindingSetRef.model_validate(
        binding_set_ref.model_dump(mode="python")
    )
    plan = ExecPlan(program_ref=typed_graph_ref, order=["lineage_method"])
    plan_ref = _put_selected_contract_model(
        store,
        plan,
        kind=ExecPlan.ARTIFACT_KIND,
        inputs=[
            input_ref_from_artifact_ref(typed_graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(
                typed_binding_set_ref,
                role="method_metric_bindings",
            ),
        ],
    )
    return (
        typed_graph_ref,
        ExecPlanRef.model_validate(plan_ref.model_dump(mode="python")),
        typed_binding_set_ref,
    )


class _RecordingLocalBackend(LocalBackend):
    def __init__(self, *, store_factory: Any, strip_capture_refs: bool = False) -> None:
        super().__init__(store_factory=store_factory)
        self.strip_capture_refs = strip_capture_refs
        self.execution_result: ExecutionResult | None = None
        self.producer_capture_refs: tuple[ArtifactRef | None, ArtifactRef | None] | None = None

    def run(
        self,
        *,
        cas_root: Path,
        program_ref: ArtifactRef,
        exec_plan_ref: ArtifactRef,
        base_state: Any,
        registry_content: Any,
        seed: int,
    ) -> ExecutionResult:
        result = super().run(
            cas_root=cas_root,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            registry_content=registry_content,
            seed=seed,
        )
        artifacts = result.exec_artifacts
        self.producer_capture_refs = (
            artifacts.method_execution_bundle_ref,
            artifacts.method_metric_binding_set_ref,
        )
        if self.strip_capture_refs:
            bundle_ref, binding_set_ref = self.producer_capture_refs
            assert bundle_ref is not None and binding_set_ref is not None
            result.exec_artifacts = replace(
                artifacts,
                method_execution_bundle_ref=None,
                method_metric_binding_set_ref=None,
                derived_artifacts=(
                    *artifacts.derived_artifacts,
                    ("method_execution_bundle", bundle_ref),
                    ("method_metric_binding_set", binding_set_ref),
                ),
            )
        self.execution_result = result
        return result


def _run_real_graph_job(
    tmp_path,
    *,
    strip_capture_refs: bool = False,
) -> tuple[FileSystemCAS, JobResult, _RecordingLocalBackend, MethodMetricBindingSetRef]:
    store = FileSystemCAS(tmp_path)
    program_ref, exec_plan_ref, binding_set_ref = _real_binding_graph_and_plan(store)
    MethodRegistry.get_instance().register(_CapturedGraphMethod, override=True)
    backend = _RecordingLocalBackend(
        store_factory=lambda _root: store,
        strip_capture_refs=strip_capture_refs,
    )
    registry_content = SimpleNamespace(
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        constraint_registry=None,
    )
    result = run_job(
        JobSpec(program_ref=program_ref, exec_plan_ref=exec_plan_ref, seed=37),
        backend=backend,
        registry_content=registry_content,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        cas_root=tmp_path,
        store_factory=lambda _root: store,
    )
    return store, result, backend, binding_set_ref


def test_real_local_backend_capture_refs_reach_job_result_and_fresh_bounded_reader(
    tmp_path,
) -> None:
    store, result, backend, binding_set_ref = _run_real_graph_job(tmp_path)

    assert not result.issues
    assert result.simulation_results_ref is not None
    assert backend.execution_result is not None
    assert backend.producer_capture_refs is not None
    producer_bundle_ref, producer_binding_set_ref = backend.producer_capture_refs
    assert producer_bundle_ref is not None
    assert producer_binding_set_ref is not None
    assert producer_bundle_ref.manifest_profile_sha256 is not None
    assert producer_binding_set_ref.manifest_profile_sha256 is not None
    assert producer_binding_set_ref.model_dump(mode="python") == binding_set_ref.model_dump(
        mode="python"
    )

    producer_bundle = validate_core_model_json_artifact(
        MethodExecutionBundle,
        store,
        producer_bundle_ref,
    )
    assert len(producer_bundle.occurrences) == 1
    assert producer_bundle.occurrences[0].status == "succeeded"
    assert producer_bundle.occurrences[0].dispatch is not None
    assert producer_bundle.occurrences[0].dispatch.outcome == "succeeded"
    fresh_store = FileSystemCAS(tmp_path)
    persisted_binding_set = validate_core_model_json_artifact(
        MethodMetricBindingSet,
        fresh_store,
        producer_binding_set_ref,
    )
    assert len(persisted_binding_set.bindings) == 1

    provenance = read_job_result_method_execution_capture(
        fresh_store,
        result,
        max_manifest_bytes=256 * 1024,
    )
    assert provenance.availability == "available"
    assert provenance.method_execution_bundle_ref is not None
    assert provenance.method_metric_binding_set_ref is not None
    assert provenance.method_execution_bundle_ref.model_dump(mode="python") == (
        producer_bundle_ref.model_dump(mode="python")
    )
    assert provenance.method_metric_binding_set_ref.model_dump(mode="python") == (
        producer_binding_set_ref.model_dump(mode="python")
    )
    assert result.method_execution_capture == provenance

    simulation_manifest = read_core_manifest_profile_bounded(
        fresh_store,
        result.simulation_results_ref,
        max_manifest_bytes=256 * 1024,
    ).manifest
    assert simulation_manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.SimulationResults",
        version="0.1.0",
    )
    assert (
        input_ref_from_artifact_ref(
            producer_bundle_ref,
            role="method_execution_bundle",
        )
        in simulation_manifest.inputs
    )
    assert (
        input_ref_from_artifact_ref(
            producer_binding_set_ref,
            role="method_metric_binding_set",
        )
        in simulation_manifest.inputs
    )


def test_real_capture_removal_keeps_markers_non_authoritative_in_job_result(tmp_path) -> None:
    fresh_store, result, backend, _binding_set_ref = _run_real_graph_job(
        tmp_path,
        strip_capture_refs=True,
    )

    assert not result.issues
    assert backend.execution_result is not None
    assert backend.producer_capture_refs is not None
    assert all(ref is not None for ref in backend.producer_capture_refs)
    returned_artifacts = backend.execution_result.exec_artifacts
    assert returned_artifacts.method_execution_bundle_ref is None
    assert returned_artifacts.method_metric_binding_set_ref is None
    assert {role for role, _ref in returned_artifacts.derived_artifacts} >= {
        "method_execution_bundle",
        "method_metric_binding_set",
    }
    assert result.method_execution_capture is not None
    assert result.method_execution_capture.availability == "unavailable"
    assert result.method_execution_capture.method_execution_bundle_ref is None
    assert result.method_execution_capture.method_metric_binding_set_ref is None

    fresh_result = read_job_result_method_execution_capture(
        FileSystemCAS(tmp_path),
        result,
        max_manifest_bytes=256 * 1024,
    )
    assert fresh_result == result.method_execution_capture
    assert fresh_result.limitations == (
        "method_execution_bundle_role_absent",
        "method_metric_binding_set_role_absent",
    )
    simulation_manifest = read_core_manifest_profile_bounded(
        fresh_store,
        result.simulation_results_ref,
        max_manifest_bytes=256 * 1024,
    ).manifest
    assert all(
        edge.role not in {"method_execution_bundle", "method_metric_binding_set"}
        for edge in simulation_manifest.inputs
    )


def test_legacy_job_does_not_infer_capture_from_derived_artifact_labels(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    diagnostic_bundle = _selected_ref(
        store,
        kind="foundry.method_execution_bundle",
        schema_name="polisyos.core.MethodExecutionBundle",
        value={"occurrences": []},
        schema_version="1.0",
    )
    store, result = _legacy_job_result(
        tmp_path,
        exec_artifacts={"derived_artifacts": (("method_execution_bundle", diagnostic_bundle),)},
    )

    assert not result.issues
    assert result.method_execution_capture is not None
    assert result.method_execution_capture.availability == "unavailable"
    assert result.method_execution_capture.method_execution_bundle_ref is None
    assert result.method_execution_capture.method_metric_binding_set_ref is None
    assert result.method_execution_capture.limitations == (
        "method_execution_bundle_role_absent",
        "method_metric_binding_set_role_absent",
    )
    assert result.simulation_results_ref is not None
    manifest = store.get_manifest(result.simulation_results_ref)
    assert all(
        item.role != "method_execution_bundle" and item.role != "method_metric_binding_set"
        for item in manifest.inputs
    )


def test_capture_field_keeps_its_absent_default_out_of_existing_payloads() -> None:
    result = JobResult(job_key=JobKey(value="job:legacy-payload-default"))

    assert result.method_execution_capture is None
    assert "method_execution_capture" not in result.model_dump(mode="python")


def test_legacy_job_preserves_partial_producer_capture_as_limited_provenance(tmp_path) -> None:
    bundle_ref = _selected_ref(
        FileSystemCAS(tmp_path),
        kind="foundry.method_execution_bundle",
        schema_name="polisyos.core.MethodExecutionBundle",
        value={"occurrences": []},
        schema_version="1.0",
    )
    store, result = _legacy_job_result(
        tmp_path,
        exec_artifacts={
            "method_execution_bundle_ref": bundle_ref,
            "derived_artifacts": (("method_metric_binding_set", bundle_ref),),
        },
    )

    assert not result.issues
    assert result.simulation_results_ref is not None
    assert result.method_execution_capture is not None
    assert result.method_execution_capture.availability == "partial"
    assert result.method_execution_capture.method_execution_bundle_ref == bundle_ref
    assert result.method_execution_capture.method_metric_binding_set_ref is None
    assert result.method_execution_capture.limitations == ("method_metric_binding_set_role_absent",)
    manifest = store.get_manifest(result.simulation_results_ref)
    assert [item.role for item in manifest.inputs].count("method_execution_bundle") == 1
    assert "method_metric_binding_set" not in {item.role for item in manifest.inputs}


@pytest.mark.parametrize(
    "invalid_edge",
    [
        pytest.param("wrong_kind", id="changed-kind"),
        pytest.param("wrong_profile", id="changed-selected-profile"),
        pytest.param("wrong_schema", id="changed-schema"),
        pytest.param("missing_profile", id="missing-profile"),
        pytest.param("duplicate_role", id="duplicate-role"),
    ],
)
def test_capture_reader_rejects_malformed_selected_roles(tmp_path, invalid_edge: str) -> None:
    store = FileSystemCAS(tmp_path)
    bundle_ref = _selected_ref(
        store,
        kind="foundry.method_execution_bundle",
        schema_name="polisyos.core.MethodExecutionBundle",
        value={"occurrences": []},
        schema_version="1.0",
    )
    if invalid_edge == "wrong_kind":
        edge_ref = _selected_ref(
            store,
            kind="foundry.other_bundle",
            schema_name="tests.OtherBundle",
            value={"occurrences": []},
        )
        inputs = [input_ref_from_artifact_ref(edge_ref, role="method_execution_bundle")]
    elif invalid_edge == "wrong_schema":
        edge_ref = _selected_ref(
            store,
            kind="foundry.method_execution_bundle",
            schema_name="tests.OtherBundle",
            value={"occurrences": []},
            schema_version="1.0",
        )
        inputs = [input_ref_from_artifact_ref(edge_ref, role="method_execution_bundle")]
    elif invalid_edge == "wrong_profile":
        from polisyos.core.artifacts.manifest import InputRef

        inputs = [
            InputRef(
                artifact_id=bundle_ref.artifact_id,
                role="method_execution_bundle",
                manifest_profile_sha256=f"sha256:{'0' * 64}",
            )
        ]
    elif invalid_edge == "missing_profile":
        from polisyos.core.artifacts.manifest import InputRef

        inputs = [InputRef(artifact_id=bundle_ref.artifact_id, role="method_execution_bundle")]
    else:
        edge = input_ref_from_artifact_ref(bundle_ref, role="method_execution_bundle")
        inputs = [edge, edge]
    selected_summary_ref = _summary_ref(store, inputs=inputs)
    job_result = JobResult(
        job_key=JobKey(value="job:test-lineage"),
        simulation_results_ref=selected_summary_ref,
    )

    with pytest.raises((ValueError, FileNotFoundError)):
        read_job_result_method_execution_capture(
            store,
            job_result,
            max_manifest_bytes=256 * 1024,
        )


def test_capture_reader_applies_explicit_manifest_byte_bound(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    selected_summary_ref = _summary_ref(store, inputs=[])
    job_result = JobResult(
        job_key=JobKey(value="job:bounded-lineage"),
        simulation_results_ref=selected_summary_ref,
    )

    with pytest.raises(CoreJsonReadBoundsRefusalError):
        read_job_result_method_execution_capture(store, job_result, max_manifest_bytes=1)


def test_direct_hte_result_and_evidence_preserve_exact_selected_input_edges(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_HTEInputMethod, override=True)
    store = FileSystemCAS(tmp_path)
    hte_input_ref = _selected_ref(
        store,
        kind="scientist.method_input.hte_observational_data",
        schema_name="tests.HTEObservationalData",
        value=[1, 2],
    )

    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=_HTEInputMethod.signature.fqn,
            input_refs={"hte_data": hte_input_ref},
        ),
        cas_root=tmp_path,
    )

    assert not result.issues
    assert result.method_result_ref is not None
    assert result.method_evidence_ref is not None
    assert result.method_result_ref.manifest_profile_sha256 is not None
    assert result.method_evidence_ref.manifest_profile_sha256 is not None
    assert result.method_execution_capture is None
    assert hte_input_ref.manifest_profile_sha256 is not None
    result_manifest = read_core_manifest_profile_bounded(
        store,
        result.method_result_ref,
        max_manifest_bytes=256 * 1024,
    ).manifest
    evidence_manifest = read_core_manifest_profile_bounded(
        store,
        result.method_evidence_ref,
        max_manifest_bytes=256 * 1024,
    ).manifest
    assert result_manifest.kind == "scientist.method_result.causal.hte"
    assert result_manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.MethodResult",
        version="0.1.0",
    )
    assert result_manifest.inputs == [
        input_ref_from_artifact_ref(hte_input_ref, role="input:hte_data")
    ]
    assert evidence_manifest.kind == "scientist.method_evidence"
    assert evidence_manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.MethodExecutionEvidence",
        version="0.1.0",
    )
    assert evidence_manifest.inputs == [
        input_ref_from_artifact_ref(result.method_result_ref, role="method_result")
    ]
