"""Real compiled candidate-vector inputs with a fixed, selected typed axis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from polisyos.core.artifacts import CoreJsonReadLimits, ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.entity_axis import SelectedEntityVectorSourceDescriptor
from polisyos.core.contracts.execution_plan import ExecutionPlan, ExecutionPlanRef, MethodDagNode
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    FoundryInputBindingRule,
    MethodMetricBindingRequest,
)
from polisyos.core.contracts.model_input_period_steps import ModelInputPeriodStepProfile
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    load_model_input_obligation_set,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.semantic_step_binding import ModelInputStepSubject
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    SelectedEntityVectorSourceMeaning,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
)
from polisyos.core.registry import build_registry_bundle
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.data_plane.entity_axis import build_selected_source_entity_axis
from polisyos.foundry.methods.catalog.distributional.advanced import GeneralizedGiniEstimator
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    MethodMetricInputRole,
    MethodMetricSemanticContract,
)
from polisyos.ir.kernel.metrics import MetricRegistry, MetricSpec
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType
from polisyos.ir.kernel.time_semantics import TimeFrequency, TimeSemantics
from polisyos.ir.kernel.units import DimensionlessUnit, GenericUnit, UnitRef, UnitsRegistry
from polisyos.ir.model_layer.model_spec import ModelInputPortDeclarationRef, ModelSpec
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)
from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase
from tests._helpers.registered_derived_method_input import prepare_registered_method_input_preflight
from tests.unit.core.contracts.test_semantic_derived_binding import _definition, _put_contract


def vector_read_limits() -> CoreJsonReadLimits:
    """Return bounded candidate JSON limits for the four-member fixture."""
    return CoreJsonReadLimits(
        max_bytes=1_000_000, max_depth=32, max_elements=10_000, max_manifest_bytes=100_000
    )


@dataclass(frozen=True)
class SelectedMethodEntityVectorCase:
    """Compiled model and explicit candidate declarations for two model steps."""

    case: ProgramGraphTaxSubsidyInputCase
    port: ModelInputPort
    source_view_ref: ArtifactRef
    source_inputs: tuple[tuple[ModelInputStepSubject, SelectedEntityVectorSourceMeaning], ...]
    obligation_set_ref: ArtifactRef


def prepare_selected_method_entity_vector_case(tmp_path: Path) -> SelectedMethodEntityVectorCase:
    """Compile genuine GenericUnit vector ports and the existing Gini method.

    The shared JSON view has a fixed typed membership. Meaning and each annual
    scope are explicit consumer assertions; this local fixture does not decode
    empirical time, assert representativeness, or manufacture acquisition acts.
    The selected Gini leaf is persisted through the existing output capture,
    while its unregistered metric law remains explicitly unavailable.
    """
    store = FileSystemCAS(tmp_path / "cas")
    source_view_ref = store.put_json(
        {
            "members": ["b", 1, "1", 2],
            "years": {"2020": [40, 10, 30, 20], "2021": [40, 20, 20, 20]},
        },
        PutOptions(kind="tests.candidate_entity_vector_view", media_type="application/json"),
        return_selected_profile=True,
    )
    axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=source_view_ref,
        namespace="candidate-selected-view",
        member_values_pointer="/members",
        limits=vector_read_limits(),
    )
    slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    slots["selected.amount_vector"] = SlotSpec(
        slot_id="selected.amount_vector",
        scope=SlotScope.GLOBAL,
        value_type=SlotValueType.DECIMAL,
        unit=UnitRef(unit_id="amount"),
        kind=SlotKind.FLOW,
        merge_rule={"rule_id": "sum"},
        state_path=None,
        dtype="float64",
        shape=["n_obs"],
    )
    metric_id = "candidate_gini"
    semantics = MethodMetricSemanticContract(
        quantity_kind="index",
        quantity_role="candidate_distribution_summary",
        population_id="candidate_selected_view_members",
        axes=("typed_entity_axis",),
        denominator_id="selected_axis_cardinality",
        time_role="observation_time",
        producer_contract_id="not_established",
        input_roles=(
            MethodMetricInputRole(role_id="selected_values", method_input_slot_id="values"),
        ),
        output_value_path=("generalized_gini",),
    )
    registry = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots=slots),
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=MetricRegistry(
            schema_version="1.1",
            metrics={
                **DEFAULT_METRIC_REGISTRY.metrics,
                metric_id: MetricSpec(
                    metric_id=metric_id, unit_id="candidate_gini", method_semantics=semantics
                ),
            },
        ),
        units_registry=UnitsRegistry(
            units={
                **DEFAULT_UNITS_REGISTRY.units,
                "amount": GenericUnit(label="amount"),
                "candidate_gini": DimensionlessUnit(label="candidate_gini"),
            }
        ),
        return_selected_profile=True,
    )
    source_ref = store.put_json(
        {"agents": {"income": [0]}},
        PutOptions(kind="tests.candidate_vector_prestate", media_type="application/json"),
        return_selected_profile=True,
    )
    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=source_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(source_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    initial = build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        rules=[
            FoundryInputBindingRule(
                binding_id="opening-community",
                source_path="agents.income",
                target_slot_id="agents.income",
            )
        ],
        return_selected_profile=True,
    )
    definition_ref, _ = _definition(store, "candidate_entity_amount")
    representation = VariableRepresentation(
        representation_id="candidate.entity_amount",
        revision="1",
        semantic_definition_ref=definition_ref,
        quantity_kind="flow",
        measure_form="absolute",
        unit_id="amount",
        scale_to_unit=Decimal(1),
        time_support="period_total",
        temporal_granularity="annual",
        aggregation="identity",
        grain=("entity",),
        population_ref="population:selected-view",
    )
    representation_ref = VariableRepresentationRef.model_validate(
        _put_contract(store, representation).model_dump(mode="python")
    )
    profile = MeasurementBindingProfile(
        profile_id="candidate.entity_amount",
        revision="1",
        required_axes=(
            MeasurementAxis.QUANTITY_KIND,
            MeasurementAxis.MEASURE_FORM,
            MeasurementAxis.UNIT_ID,
            MeasurementAxis.SCALE_TO_UNIT,
            MeasurementAxis.TIME_SUPPORT,
            MeasurementAxis.TEMPORAL_GRANULARITY,
            MeasurementAxis.AGGREGATION,
            MeasurementAxis.GRAIN,
            MeasurementAxis.POPULATION_REF,
        ),
    )
    port = ModelInputPort(
        port_id="selected-entity-amount",
        slot_id="selected.amount_vector",
        carrier="method_input",
        unit_id="amount",
        purpose="simulation_input",
        semantic_definition_ref=definition_ref,
        representation_ref=representation_ref,
        binding_profile_ref=MeasurementBindingProfileRef.model_validate(
            _put_contract(store, profile).model_dump(mode="python")
        ),
        scope=ModelInputScope(
            population_ref="population:selected-view",
            geography_ref="geography:fixture",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2020, 1, 1),
            period_end=date(2021, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
        entity_axis_ref=axis.ref,
        period_step_profile=ModelInputPeriodStepProfile(),
        physical_encoding=ModelInputPhysicalEncoding(
            dtype="float64", shape=(4,), max_absolute_error=Decimal(0)
        ),
    )
    declaration_ref = persist_model_input_port_declaration(
        store, ModelInputPortDeclaration(schema_version="1.2", ports=(port,))
    )
    model = ModelSpec(
        schema_version="1.1",
        model_id="candidate_entity_vector",
        data_snapshot_ref=str(snapshot_ref.artifact_id),
        registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        time_semantics=TimeSemantics(
            frequency=TimeFrequency.YEAR, start_date="2020-01-01", step_count=2
        ),
        model_input_port_declaration_ref=ModelInputPortDeclarationRef.model_validate(
            declaration_ref.model_dump(mode="python")
        ),
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="candidate_entity_vector",
            domain=ProblemDomain.CUSTOM,
            objectives=[
                ObjectiveSpec(
                    objective_id="candidate_gini", metric_id=metric_id, direction="minimize"
                )
            ],
        ),
        policy_spec=PolicySpec(policy_id="candidate_entity_vector", interventions=[]),
        model_spec=model,
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        PolicyCandidateSchema(
            candidate_id="candidate_entity_vector",
            trinity_bundle=trinity,
            target_population=TargetPopulationSpec(
                population_id="selected-view",
                description="Synthetic selected view, not representative.",
            ),
        ),
        inputs=[
            input_ref_from_artifact_ref(snapshot_ref, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            trinity,
            inputs=[
                input_ref_from_artifact_ref(candidate_ref, role="policy_candidate"),
                input_ref_from_artifact_ref(declaration_ref, role="model_input_port_declaration"),
            ],
        ).model_dump(mode="python")
    )
    MethodRegistry.get_instance().register(GeneralizedGiniEstimator, override=True)
    signature = GeneralizedGiniEstimator.signature
    plan = ExecutionPlan(
        schema_version="1.2",
        plan_id="candidate_entity_vector",
        method_dag=[
            MethodDagNode(
                node_id="gini",
                method_fqn=signature.fqn,
                method_version=signature.version,
                backend=signature.execution_backend.value,
                params={"nu": 2},
                reads_slots=["values"],
                writes_slots=["result"],
                state_writes=[],
                input_ports={"values": {"source_kind": "registry_slot", "slot_id": port.slot_id}},
            )
        ],
    )
    plan_ref = store.put_json(
        plan,
        PutOptions(
            kind="scientist.execution_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecutionPlan", version="1.2"),
            inputs=[input_ref_from_artifact_ref(trinity_ref, role="policy_candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    compiled = compile_foundry(
        store,
        CompileRequest(
            schema_version="1.2",
            input_kind="trinity",
            policy_ref=trinity_ref,
            registry_bundle_ref=registry.bundle_ref,
            method_execution_plan_ref=ExecutionPlanRef.model_validate(
                plan_ref.model_dump(mode="python")
            ),
            method_metric_bindings=[
                MethodMetricBindingRequest(
                    objective_id="candidate_gini", node_id="gini", output_slot_id="result"
                )
            ],
            return_selected_profile=True,
        ),
    )
    if not compiled.ok or compiled.exec_plan_ref is None:
        raise AssertionError(f"selected_vector_fixture_compile_failed:{compiled.notes!r}")
    (program_ref,) = (item.ref for item in compiled.derived_refs if item.role == "program_graph")
    case = ProgramGraphTaxSubsidyInputCase(
        store=store,
        store_root=store.root,
        source_ref=source_ref,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        input_bindings_ref=initial.input_bindings_ref,
        bound_state_snapshot_ref=initial.bound_state_snapshot_ref,
        policy_candidate_ref=candidate_ref,
        trinity_ref=trinity_ref,
        compile_report_ref=compiled.compile_report_ref,
        exec_plan_ref=compiled.exec_plan_ref,
        program_graph_ref=program_ref,
        model_input_port_declaration_ref=declaration_ref,
    )
    preflight = prepare_registered_method_input_preflight(case, steps=(0, 1))
    selected_set, _ = load_model_input_obligation_set(store, preflight.obligation_set_ref)
    (obligation_ref,) = selected_set.obligation_refs
    assert selected_set.required_step_scopes is not None
    source_inputs = tuple(
        (
            ModelInputStepSubject(model_input_obligation_ref=obligation_ref, step_scope=step_scope),
            SelectedEntityVectorSourceMeaning(
                source_descriptor=SelectedEntityVectorSourceDescriptor(
                    source_view_ref=source_view_ref,
                    member_ids_pointer="/members",
                    values_pointer=f"/years/{step_scope.scope.period_start.year}",
                ),
                source_definition_ref=definition_ref,
                source_representation_ref=representation_ref,
                source_registry_bundle_ref=SelectedVariableBindingRef.model_validate(
                    registry.bundle_ref.model_dump(mode="python")
                ),
                source_scope=step_scope.scope,
            ),
        )
        for step_scope in selected_set.required_step_scopes
    )
    return SelectedMethodEntityVectorCase(
        case=case,
        port=port,
        source_view_ref=source_view_ref,
        source_inputs=source_inputs,
        obligation_set_ref=preflight.obligation_set_ref,
    )
