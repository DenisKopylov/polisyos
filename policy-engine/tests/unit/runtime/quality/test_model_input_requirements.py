"""Selected ProgramGraph dependencies drive scoped acquisition requirements."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    CoreJSONArtifactStore,
    WarningRecord,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    ProgramGraphRef,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    load_model_input_obligation,
    load_program_graph_input_interface,
    persist_model_input_obligation,
    persist_model_input_obligation_set,
    persist_model_input_port_declaration,
    persist_program_graph_input_interface,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
)
from polisyos.data_requirement.compiler import (
    DataRequirementCompiler,
    persist_model_input_compilation_report,
    verify_model_input_compilation_report,
)
from polisyos.foundry.execute import load_state_snapshot
from polisyos.foundry.execute.model_input_requirements import verify_program_graph_input_preflight
from polisyos.runtime.quality.model_input_requirements import (
    ProgramGraphInputPreflight,
    derive_program_graph_input_interface,
    preflight_program_graph_inputs,
)
from tests._helpers.program_graph_tax_subsidy_input import (
    ProgramGraphTaxSubsidyInputCase,
    prepare_program_graph_tax_subsidy_input_case,
)

_SUBSIDY_NODE_ID = "fixture_subsidy"


def _opening_stock_port(store: CoreJSONArtifactStore) -> ModelInputPort:
    evidence_ref = store.put_json(
        {"definition": "Nominal treasury dollars in the opening state of the model."},
        PutOptions(
            kind="tests.program_graph_model_definition",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.ProgramGraphModelDefinition", version="1.0"),
        ),
        return_selected_profile=True,
    )
    definition = VariableSemanticDefinition(
        namespace="test.treasury",
        stable_id="opening-stock",
        revision="1",
        meaning="Nominal treasury dollars in the opening state of the model.",
        definition_evidence_refs=(
            SelectedVariableBindingRef.model_validate(evidence_ref.model_dump()),
        ),
    )
    definition_ref = VariableSemanticDefinitionRef.model_validate(
        store.put_json(
            definition,
            PutOptions(
                kind=VariableSemanticDefinition.ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=VariableSemanticDefinition.ARTIFACT_SCHEMA_NAME,
                    version=VariableSemanticDefinition.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[input_ref_from_artifact_ref(evidence_ref, role="definition_evidence")],
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    representation = VariableRepresentation(
        representation_id="test.treasury.opening-stock-usd",
        revision="1",
        semantic_definition_ref=definition_ref,
        quantity_kind="stock",
        measure_form="absolute",
        unit_id="usd",
        scale_to_unit=Decimal("1"),
        time_support="state_start",
        temporal_granularity="annual",
        aggregation="identity",
        grain=("jurisdiction", "period"),
        population_ref="population:treasury",
    )
    representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            representation,
            PutOptions(
                kind=VariableRepresentation.ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=VariableRepresentation.ARTIFACT_SCHEMA_NAME,
                    version=VariableRepresentation.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[input_ref_from_artifact_ref(definition_ref, role="semantic_definition")],
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    profile = MeasurementBindingProfile(
        profile_id="test.treasury.opening-stock",
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
        ),
    )
    profile_ref = MeasurementBindingProfileRef.model_validate(
        store.put_json(
            profile,
            PutOptions(
                kind=MeasurementBindingProfile.ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=MeasurementBindingProfile.ARTIFACT_SCHEMA_NAME,
                    version=MeasurementBindingProfile.ARTIFACT_SCHEMA_VERSION,
                ),
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    return ModelInputPort(
        port_id="opening-stock",
        slot_id="government.balance",
        state_path="government_balance",
        unit_id="usd",
        purpose="initial_state",
        semantic_definition_ref=definition_ref,
        representation_ref=representation_ref,
        binding_profile_ref=profile_ref,
        physical_encoding=ModelInputPhysicalEncoding(
            shape=(), dtype="float32", max_absolute_error=Decimal("0")
        ),
        scope=ModelInputScope(
            population_ref="population:treasury",
            geography_ref="geography:fixture",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2022, 1, 1),
            period_end=date(2022, 12, 31),
            time_role="observation_time",
        ),
    )


def _stock_declaration(
    store: CoreJSONArtifactStore, *, include_non_execution_ports: bool = False
) -> ArtifactRef:
    port = _opening_stock_port(store)
    ports = (port,)
    if include_non_execution_ports:
        ports = (
            port,
            port.model_copy(update={"port_id": "stock-calibration", "purpose": "calibration"}),
            port.model_copy(update={"port_id": "stock-forecast", "purpose": "outcome_validation"}),
        )
    return persist_model_input_port_declaration(store, ModelInputPortDeclaration(ports=ports))


def _context(case: ProgramGraphTaxSubsidyInputCase) -> ModelInputContext:
    return ModelInputContext(
        run_id="model-input-preflight-test",
        candidate_id="program_graph_tax_subsidy_input",
        candidate_content_hash=str(case.policy_candidate_ref.artifact_id),
        design_problem_ref=str(case.trinity_ref.artifact_id),
        candidate_source_ref=case.policy_candidate_ref,
    )


def _interface(case: ProgramGraphTaxSubsidyInputCase) -> ArtifactRef:
    ref = derive_program_graph_input_interface(
        case.store,
        program_graph_ref=ProgramGraphRef.model_validate(case.program_graph_ref.model_dump()),
        exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump()),
        registry_bundle_ref=case.registry_bundle_ref,
    )
    assert ref is not None
    return ref


def _preflight(
    case: ProgramGraphTaxSubsidyInputCase,
    interface_ref: ArtifactRef,
    context: ModelInputContext,
    *,
    steps: tuple[int, ...] = (0, 1),
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None,
    graph_ref: ArtifactRef | None = None,
) -> ProgramGraphInputPreflight:
    return preflight_program_graph_inputs(
        case.store,
        interface_ref=interface_ref,
        program_graph_ref=ProgramGraphRef.model_validate(
            (graph_ref or case.program_graph_ref).model_dump()
        ),
        exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump()),
        registry_bundle_ref=case.registry_bundle_ref,
        input_bindings_ref=case.input_bindings_ref,
        context=context,
        steps=steps,
        parameter_override_bundle_ref=parameter_override_bundle_ref,
    )


def _supplied_rate(case: ProgramGraphTaxSubsidyInputCase) -> ParameterOverrideBundleRef:
    request = ParameterOverrideBundle(
        overrides={_SUBSIDY_NODE_ID: {"rate": "0.125"}},
        sources={_SUBSIDY_NODE_ID: [str(case.policy_candidate_ref.artifact_id)]},
    )
    return ParameterOverrideBundleRef.model_validate(
        case.store.put_json(
            request,
            PutOptions(
                kind=request.ARTIFACT_KIND,
                media_type=request.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=request.ARTIFACT_SCHEMA_NAME, version=request.ARTIFACT_SCHEMA_VERSION
                ),
                inputs=[
                    input_ref_from_artifact_ref(
                        case.program_graph_ref, role="selected_program_graph"
                    ),
                    input_ref_from_artifact_ref(
                        case.policy_candidate_ref, role="selected_candidate_source"
                    ),
                ],
            ),
            return_selected_profile=True,
        ).model_dump()
    )


def test_required_input_is_produced_by_selected_model(tmp_path: Path) -> None:
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=None,
        mechanism_start_step=2,
        model_input_port_declaration_builder=_stock_declaration,
    )
    try:
        interface_ref = _interface(case)
        interface = load_program_graph_input_interface(case.store, interface_ref)
        assert interface.declaration_ref == case.model_input_port_declaration_ref
        assert interface.trinity_bundle_ref == case.trinity_ref
        (port,) = interface.ports
        context = _context(case)
        rate_ref = _supplied_rate(case)

        preflight = _preflight(
            case, interface_ref, context, steps=(0, 1, 2), parameter_override_bundle_ref=rate_ref
        )
        (obligation_ref,) = preflight.obligation_refs
        assert preflight.supplied_initial_slots == ("agents.income",)
        assert preflight.parameter_override_bundle_ref == rate_ref
        assert not _preflight(case, interface_ref, context, steps=(0, 1)).obligation_refs
        wrong_origin = context.model_copy(update={"candidate_source_ref": case.source_ref})
        with pytest.raises(ValueError, match="model_input_override_owner_mismatch"):
            _preflight(case, interface_ref, wrong_origin, parameter_override_bundle_ref=rate_ref)
        assert (
            float(
                load_state_snapshot(
                    case.store, snapshot_ref=case.bound_state_snapshot_ref
                ).government_balance
            )
            == 0.0
        )

        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.context == context
        assert obligation.port == port
        assert obligation.parameter_override_bundle_ref == rate_ref
        assert obligation.prestate_ref == case.bound_state_snapshot_ref
        assert obligation.missing_reason == "required_port_input_not_bound"
        (dependency,) = obligation.dependencies
        assert (dependency.node_id, dependency.kind, dependency.first_required_step) == (
            _SUBSIDY_NODE_ID,
            "additive_prestate",
            2,
        )

        selected_set = verify_program_graph_input_preflight(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            expected_invocation=preflight.invocation,
        )
        assert selected_set.obligation_refs == (obligation_ref,)

        wrong_step_obligation = obligation.model_copy(
            update={"dependencies": (dependency.model_copy(update={"first_required_step": 1}),)}
        )
        wrong_step_ref = persist_model_input_obligation(case.store, wrong_step_obligation)
        for omitted_or_forged in ((), (wrong_step_ref,)):
            changed_set_ref = persist_model_input_obligation_set(
                case.store, selected_set.model_copy(update={"obligation_refs": omitted_or_forged})
            )
            with pytest.raises(ValueError, match="model_input_preflight_replay_mismatch"):
                verify_program_graph_input_preflight(
                    case.store,
                    obligation_set_ref=changed_set_ref,
                    expected_invocation=preflight.invocation,
                )

        expected = {
            "expected_context": context,
            "expected_interface_ref": interface_ref,
        }
        report = DataRequirementCompiler.compile_model_input_obligations(
            case.store, obligation_set_ref=preflight.obligation_set_ref, **expected
        )
        (requirement,) = report.requirements
        assert requirement.port == port
        assert requirement.obligation_ref == obligation_ref
        assert requirement.scope.time == "2022-01-01/2022-12-31"
        assert requirement.scope.time_role == "observation_time"
        report_ref = persist_model_input_compilation_report(case.store, report)
        assert (
            verify_model_input_compilation_report(
                case.store,
                report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                **expected,
            )
            == report
        )

        forged_requirement = requirement.model_copy(
            update={"scope": requirement.scope.model_copy(update={"time": "2023"})}
        )
        forged_ref = persist_model_input_compilation_report(
            case.store, report.model_copy(update={"requirements": (forged_requirement,)})
        )
        with pytest.raises(ValueError, match="model_input_compiler_report_selection_mismatch"):
            verify_model_input_compilation_report(
                case.store,
                forged_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                **expected,
            )
    finally:
        case.close()


def test_calibration_and_predicted_outcome_do_not_supply_the_model_port(tmp_path: Path) -> None:
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=1000,
        model_input_port_declaration_builder=lambda store: _stock_declaration(
            store, include_non_execution_ports=True
        ),
    )
    try:
        interface_ref = _interface(case)
        interface = load_program_graph_input_interface(case.store, interface_ref)
        assert tuple(port.purpose for port in interface.ports) == (
            "initial_state",
            "calibration",
            "outcome_validation",
        )
        preflight = _preflight(case, interface_ref, _context(case))
        (obligation_ref,) = preflight.obligation_refs
        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.port.purpose == "initial_state"
        assert (
            float(
                load_state_snapshot(
                    case.store, snapshot_ref=case.bound_state_snapshot_ref
                ).government_balance
            )
            == 1000.0
        )
    finally:
        case.close()


def test_selected_graph_cannot_be_substituted_by_equal_bytes(tmp_path: Path) -> None:
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=None,
        model_input_port_declaration_builder=_stock_declaration,
    )
    try:
        interface_ref = _interface(case)
        original = case.store.get_manifest(case.program_graph_ref)
        alternative = case.store.put_bytes(
            case.store.get_bytes(case.program_graph_ref),
            PutOptions(
                kind=original.kind,
                media_type=original.media_type,
                schema=original.artifact_schema,
                inputs=original.inputs,
                warnings=[WarningRecord(code="test.alternate_view", msg="Same program bytes")],
            ),
            return_selected_profile=True,
        )
        assert alternative.artifact_id == case.program_graph_ref.artifact_id
        assert alternative.manifest_profile_sha256 != case.program_graph_ref.manifest_profile_sha256
        with pytest.raises(ValueError, match="model_input_selected_graph_mismatch"):
            _preflight(case, interface_ref, _context(case), graph_ref=alternative)
        interface = load_program_graph_input_interface(case.store, interface_ref)
        (port,) = interface.ports
        wrong_scope = port.scope.model_copy(update={"jurisdiction_ref": "jurisdiction:other"})
        foreign_interface_ref = persist_program_graph_input_interface(
            case.store,
            interface.model_copy(
                update={"ports": (port.model_copy(update={"scope": wrong_scope}),)}
            ),
        )
        with pytest.raises(
            ValueError, match="model_input_interface_not_selected_by_compiled_model"
        ):
            _preflight(case, foreign_interface_ref, _context(case))
    finally:
        case.close()
