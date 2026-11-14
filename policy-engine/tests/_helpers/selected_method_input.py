"""Real selected compiler/registry fixture for candidate method-carried inputs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.execution_plan import ExecutionPlan, ExecutionPlanRef, MethodDagNode
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import CompileRequest, FoundryInputBindingRule
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
)
from polisyos.core.registry import build_registry_bundle
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
)
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry
from polisyos.ir.kernel.time_semantics import TimeFrequency, TimeSemantics
from polisyos.ir.kernel.units import MoneyUnit
from polisyos.ir.model_layer.model_spec import ModelInputPortDeclarationRef, ModelSpec
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)
from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase
from tests.unit.core.contracts.test_semantic_derived_binding import (
    _definition,
    _put_contract,
    _representation,
)


def prepare_selected_method_input_case(
    tmp_path: Path,
    *,
    method_class: type[Any],
    state_writes: tuple[str, ...] = ("government.balance",),
    declared: bool = True,
    shape: tuple[int, ...] = (),
    time_semantics: TimeSemantics | Literal["default"] | None = "default",
    scope: ModelInputScope | None = None,
) -> tuple[ProgramGraphTaxSubsidyInputCase, dict[str, Any]]:
    """Compile one real method and a model-owned scalar period-flow port.

    Values and definitions are synthetic, candidate-only test inputs. The
    target stock means accumulated period flows since this model's origin;
    the fixture makes no cash-on-hand or empirical fiscal assertion.
    """
    store = FileSystemCAS(tmp_path / "cas")
    MethodRegistry.get_instance().register(method_class, override=True)
    signature = method_class.signature
    slots = dict(DEFAULT_SLOT_REGISTRY.slots)
    slots["period_flow"] = slots["government.balance"].model_copy(
        update={
            "slot_id": "period_flow",
            "state_path": None,
            "kind": SlotKind.FLOW,
            "dtype": "float64",
            "shape": [],
            "description": "One selected scalar total flow over the declared period.",
        }
    )
    registry = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots=slots),
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        units_registry=DEFAULT_UNITS_REGISTRY,
        return_selected_profile=True,
    )
    source_ref = store.put_json(
        {"agents": {"income": [0]}, "government_balance": 10_000_000_000},
        PutOptions(kind="tests.selected_method_prestate", media_type="application/json"),
        return_selected_profile=True,
    )
    snapshot = DataSnapshot(data_ref=source_ref)
    snapshot_ref = store.put_json(
        snapshot,
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
                binding_id="opening-stock",
                source_path="government_balance",
                target_slot_id="government.balance",
            ),
            FoundryInputBindingRule(
                binding_id="one-community",
                source_path="agents.income",
                target_slot_id="agents.income",
            ),
        ],
        return_selected_profile=True,
    )
    target_ref, _ = _definition(store, "aggregate-period-flow")
    money = MoneyUnit(currency="USD", nominal_year=2024, price_base="current")
    representation_ref, representation = _representation(
        store, target_ref, population="population:government", money=money
    )
    profile = MeasurementBindingProfile(
        schema_version="polisyos.catalog.measurement_binding_profile.v3",
        profile_id="fixture.selected_method_flow",
        revision="1",
        required_axes=(
            MeasurementAxis.QUANTITY_KIND,
            MeasurementAxis.MEASURE_FORM,
            MeasurementAxis.UNIT_ID,
            MeasurementAxis.TIME_SUPPORT,
            MeasurementAxis.TEMPORAL_GRANULARITY,
            MeasurementAxis.AGGREGATION,
            MeasurementAxis.GRAIN,
            MeasurementAxis.POPULATION_REF,
            MeasurementAxis.MONEY_UNIT,
        ),
    )
    profile_ref = MeasurementBindingProfileRef.model_validate(
        _put_contract(store, profile, version="3.0").model_dump()
    )
    port = ModelInputPort(
        port_id="period-flow",
        slot_id="period_flow",
        carrier="method_input",
        unit_id="usd",
        purpose="simulation_input",
        semantic_definition_ref=target_ref,
        representation_ref=representation_ref,
        binding_profile_ref=profile_ref,
        scope=scope
        or ModelInputScope(
            population_ref="population:government",
            geography_ref="UA",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
        physical_encoding=ModelInputPhysicalEncoding(
            shape=shape, dtype="float64", max_absolute_error=Decimal("0")
        ),
    )
    declaration_ref = (
        persist_model_input_port_declaration(
            store, ModelInputPortDeclaration(schema_version="1.1", ports=(port,))
        )
        if declared
        else None
    )
    model = ModelSpec(
        model_id="selected_method_input",
        data_snapshot_ref=str(snapshot_ref.artifact_id),
        registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        time_semantics=(
            TimeSemantics(frequency=TimeFrequency.YEAR, start_date="2024-01-01", step_count=1)
            if time_semantics == "default"
            else time_semantics
        ),
        notes=[
            "government.balance is accumulated period flow since the model origin, not cash on hand.",
            "The model is a synthetic candidate; empirical status is not established.",
        ],
    )
    if declaration_ref is not None:
        model = ModelSpec.model_validate(
            model.model_dump(mode="python")
            | {
                "schema_version": "1.1",
                "model_input_port_declaration_ref": ModelInputPortDeclarationRef.model_validate(
                    declaration_ref.model_dump(mode="python")
                ),
            }
        )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="selected_method_input", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="selected_method_input", interventions=[]),
        model_spec=model,
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        PolicyCandidateSchema(
            candidate_id="selected_method_input",
            trinity_bundle=trinity,
            target_population=TargetPopulationSpec(
                population_id="government",
                description="One synthetic aggregate government community.",
            ),
        ),
        inputs=[
            input_ref_from_artifact_ref(snapshot_ref, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    trinity_inputs = [input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")]
    if declaration_ref is not None:
        trinity_inputs.append(
            input_ref_from_artifact_ref(declaration_ref, role="model_input_port_declaration")
        )
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store), trinity, inputs=trinity_inputs
        ).model_dump(mode="python")
    )
    selected_plan = ExecutionPlan(
        schema_version="1.1",
        plan_id="selected-method-input",
        method_dag=[
            MethodDagNode(
                node_id="period_flow_node",
                method_fqn=signature.fqn,
                method_version=signature.version,
                backend=signature.execution_backend.value,
                params={"target_slot": "government.balance"},
                reads_slots=sorted(slot.name for slot in signature.input_slots),
                writes_slots=sorted(slot.name for slot in signature.output_slots),
                state_writes=list(state_writes),
            )
        ],
    )
    plan_ref = store.put_json(
        selected_plan,
        PutOptions(
            kind="scientist.execution_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecutionPlan", version="1.1"),
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
            method_execution_plan_ref=ExecutionPlanRef.model_validate(plan_ref.model_dump()),
            return_selected_profile=True,
        ),
    )
    if not compiled.ok or compiled.exec_plan_ref is None:
        raise AssertionError(f"selected_method_fixture_compile_failed:{compiled.notes!r}")
    (program_ref,) = (item.ref for item in compiled.derived_refs if item.role == "program_graph")
    return (
        ProgramGraphTaxSubsidyInputCase(
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
        ),
        {
            "port": port,
            "target_ref": target_ref,
            "representation_ref": representation_ref,
            "representation": representation,
            "profile_ref": profile_ref,
            "money": money,
        },
    )
