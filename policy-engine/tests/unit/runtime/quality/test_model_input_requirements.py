"""Selected ProgramGraph dependencies drive scoped acquisition requirements."""

from __future__ import annotations

from dataclasses import replace
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
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    ProgramGraph,
    ProgramGraphRef,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    ProgramGraphInputDependency,
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
from polisyos.foundry.execute.model_input_requirements import (
    _selected_model_input_bundle,
    program_graph_declares_model_input_ports,
    verify_program_graph_input_preflight,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.quality.model_input_requirements import (
    ProgramGraphInputPreflight,
    SelectedProgramGraphInputBasis,
    derive_program_graph_input_interface,
    preflight_program_graph_inputs,
    replay_selected_program_graph_input_obligations,
)
from tests._helpers.program_graph_tax_subsidy_input import (
    ProgramGraphTaxSubsidyInputCase,
    prepare_program_graph_tax_subsidy_input_case,
)

_SUBSIDY_NODE_ID = "fixture_subsidy"


def _persist_graph_with_ir(store: FileSystemCAS, ir_ref: ArtifactRef) -> ArtifactRef:
    graph = ProgramGraph(ir_ref=ir_ref)
    return store.put_json(
        graph,
        PutOptions(
            kind=ProgramGraph.ARTIFACT_KIND,
            media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
                version=ProgramGraph.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        return_selected_profile=True,
    )


def test_unselected_missing_legacy_trinity_anchor_keeps_raw_graph_path(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    missing_ir = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind=TrinityBundle.ARTIFACT_KIND,
        media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
    )
    graph_ref = _persist_graph_with_ir(store, missing_ir)

    assert program_graph_declares_model_input_ports(store, graph_ref) is False


def test_selected_missing_trinity_anchor_is_not_treated_as_legacy(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    missing_ir = ArtifactRef(
        artifact_id="sha256:" + "b" * 64,
        kind=TrinityBundle.ARTIFACT_KIND,
        media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
        manifest_profile_sha256="sha256:" + "c" * 64,
    )
    graph = ProgramGraph(ir_ref=missing_ir)

    with pytest.raises(FileNotFoundError):
        _selected_model_input_bundle(store, graph)


def test_malformed_trinity_anchor_is_not_treated_as_legacy(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    malformed_ir = store.put_json(
        {"schema_version": "1.0", "model_spec": {"model_input_port_declaration_ref": "invalid"}},
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        return_selected_profile=True,
    )
    graph = ProgramGraph(ir_ref=malformed_ir)

    with pytest.raises(ValueError):
        _selected_model_input_bundle(store, graph)


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
        assert interface.schema_version == "1.0"
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
        assert selected_set.schema_version == "1.0"
        assert selected_set.obligation_refs == (obligation_ref,)
        assert obligation.schema_version == "1.0"
        selected_basis = SelectedProgramGraphInputBasis(
            context=context,
            program_graph_ref=ProgramGraphRef.model_validate(case.program_graph_ref.model_dump()),
            exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump()),
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=case.input_bindings_ref,
            steps=(0, 1, 2),
            parameter_override_bundle_ref=rate_ref,
        )
        assert (
            replay_selected_program_graph_input_obligations(
                case.store,
                obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
            )
            == selected_set
        )
        for wrong_basis in (
            replace(selected_basis, steps=(0, 1)),
            replace(selected_basis, context=context.model_copy(update={"candidate_id": "foreign"})),
        ):
            with pytest.raises(ValueError, match="model_input_preflight_invocation_mismatch"):
                replay_selected_program_graph_input_obligations(
                    case.store,
                    obligation_set_ref=preflight.obligation_set_ref,
                    selected_basis=wrong_basis,
                )

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


def test_selected_method_input_emits_versioned_abi_obligation(tmp_path: Path) -> None:
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    try:
        interface_ref = _interface(case)
        interface = load_program_graph_input_interface(case.store, interface_ref)
        assert interface.schema_version == "1.1"
        (port,) = interface.ports
        assert port == metadata["port"]

        preflight = _preflight(case, interface_ref, _context(case), steps=(0,))
        assert preflight.supplied_initial_slots == ("government.balance",)
        (obligation_ref,) = preflight.obligation_refs
        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.schema_version == "1.1"
        assert obligation.port == port
        (dependency,) = obligation.dependencies
        assert (
            dependency.node_id,
            dependency.kind,
            dependency.first_required_step,
            dependency.method_abi_digest,
        ) == (
            "period_flow_node",
            "method_read",
            0,
            PeriodFlowToStock.signature.abi_digest(),
        )
        selected_set = verify_program_graph_input_preflight(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            expected_invocation=preflight.invocation,
        )
        assert selected_set.schema_version == "1.1"
        assert selected_set.obligation_refs == (obligation_ref,)

        with pytest.raises(ValueError, match="model_input_method_multi_step_reuse_unsupported"):
            _preflight(case, interface_ref, _context(case), steps=(0, 1))
    finally:
        case.close()


@pytest.mark.parametrize(
    ("time_semantics", "scope", "error"),
    [
        (None, None, "model_input_method_time_semantics_not_established"),
        (
            "monthly",
            None,
            "model_input_method_time_semantics_not_established",
        ),
        (
            "default",
            ModelInputScope(
                population_ref="population:government",
                geography_ref="UA",
                jurisdiction_ref="jurisdiction:fixture",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
            "model_input_method_transition_period_mismatch",
        ),
        (
            "default",
            ModelInputScope(
                population_ref="population:government",
                geography_ref="UA",
                jurisdiction_ref="jurisdiction:fixture",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                time_role="observation_time",
                period_basis="unknown",
            ),
            "model_input_method_period_basis_not_established",
        ),
    ],
)
def test_method_input_requires_exact_selected_annual_transition(
    tmp_path: Path, time_semantics, scope, error: str
) -> None:
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.ir.kernel.time_semantics import TimeFrequency, TimeSemantics
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    selected_time = (
        TimeSemantics(frequency=TimeFrequency.MONTH, start_date="2024-01-01", step_count=1)
        if time_semantics == "monthly"
        else None
        if time_semantics is None
        else "default"
    )
    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        time_semantics=selected_time,
        scope=scope,
    )
    try:
        interface_ref = _interface(case)
        with pytest.raises(ValueError, match=error):
            _preflight(case, interface_ref, _context(case), steps=(0,))
    finally:
        case.close()


def test_method_input_dependency_closure_supports_distinct_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.contracts.foundry import ProgramNode
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.execute.model_input_requirements import _graph_input_dependencies
    from polisyos.foundry.methods.base import (
        MethodMetadata,
        SideEffectProfile,
        Unit,
        foundry_method,
    )
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.foundry.methods.registry import MethodRegistry
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    class AlternatePeriodFlowToStock(PeriodFlowToStock):
        signature = replace(
            PeriodFlowToStock.signature,
            namespace="",
            version="0.0.0",
        )
        pure_step = staticmethod(PeriodFlowToStock.pure_step)

    alternate = foundry_method(namespace="test.accounting", version="1.0.0")(
        AlternatePeriodFlowToStock
    )

    class ReadOnlyPeriodFlow(PeriodFlowToStock):
        signature = replace(
            PeriodFlowToStock.signature,
            namespace="",
            version="0.0.0",
            parameters=(),
            patch_targets=(),
        )
        side_effect_profile = SideEffectProfile.NONE
        metadata = MethodMetadata(
            description="Return a selected scalar period flow without writing state.",
            side_effect_profile=SideEffectProfile.NONE,
        )

        @staticmethod
        def pure_step(state: dict[str, object], _params: dict[str, object]) -> dict[str, object]:
            return {"result": state["period_flow"]}

    read_only = foundry_method(namespace="test.accounting", version="1.1.0")(ReadOnlyPeriodFlow)

    period_flow_abi = next(iter(PeriodFlowToStock.signature.input_slots))

    class IncompatibleReadOnlyPeriodFlow(ReadOnlyPeriodFlow):
        signature = replace(
            ReadOnlyPeriodFlow.signature,
            namespace="",
            version="0.0.0",
            input_slots=frozenset({replace(period_flow_abi, unit=Unit("currency", "EUR"))}),
        )

    incompatible = foundry_method(namespace="test.accounting", version="1.2.0")(
        IncompatibleReadOnlyPeriodFlow
    )
    method_registry = MethodRegistry.get_instance()
    method_registry.register(alternate, override=True)
    method_registry.register(read_only, override=True)
    method_registry.register(incompatible, override=True)
    case, _ = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    try:
        selected_registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        nodes = {
            "first": ProgramNode(
                node_id="first",
                node_kind="method",
                method_fqn=PeriodFlowToStock.signature.fqn,
                method_version=PeriodFlowToStock.signature.version,
                method_params={"target_slot": "government.balance"},
                inputs=["period_flow"],
                outputs=["government.balance"],
            ),
            "second": ProgramNode(
                node_id="second",
                node_kind="method",
                method_fqn=alternate.signature.fqn,
                method_version=alternate.signature.version,
                method_params={"target_slot": "government.balance"},
                inputs=["period_flow"],
                outputs=["government.balance"],
            ),
        }
        dependencies, graph_slots = _graph_input_dependencies(
            case.store,
            nodes=nodes,
            order={"first": 0, "second": 1},
            registry=selected_registry,
            steps=(0,),
            overrides={},
        )
        assert graph_slots == {"period_flow", "government.balance"}
        assert {
            (item.node_id, item.kind, item.method_abi_digest)
            for item in dependencies["period_flow"]
        } == {
            ("first", "method_read", PeriodFlowToStock.signature.abi_digest()),
            ("second", "method_read", alternate.signature.abi_digest()),
        }
        assert {(item.node_id, item.kind) for item in dependencies["government.balance"]} == {
            ("first", "additive_prestate"),
            ("second", "additive_prestate"),
        }

        read_only_node = ProgramNode(
            node_id="read_only",
            node_kind="method",
            method_fqn=read_only.signature.fqn,
            method_version=read_only.signature.version,
            method_params={},
            inputs=["period_flow"],
            outputs=[],
        )
        read_only_dependencies, read_only_slots = _graph_input_dependencies(
            case.store,
            nodes={"read_only": read_only_node},
            order={"read_only": 0},
            registry=selected_registry,
            steps=(0,),
            overrides={},
        )
        assert read_only_slots == {"period_flow"}
        assert read_only_dependencies["period_flow"] == [
            ProgramGraphInputDependency(
                node_id="read_only",
                kind="method_read",
                first_required_step=0,
                method_abi_digest=read_only.signature.abi_digest(),
            )
        ]

        incompatible_node = read_only_node.model_copy(
            update={
                "method_fqn": incompatible.signature.fqn,
                "method_version": incompatible.signature.version,
            }
        )
        with pytest.raises(ValueError, match="model_input_method_slot_profile_unsupported"):
            _graph_input_dependencies(
                case.store,
                nodes={"incompatible": incompatible_node},
                order={"incompatible": 0},
                registry=selected_registry,
                steps=(0,),
                overrides={},
            )

        duplicate = nodes["second"].model_copy(
            update={
                "method_fqn": PeriodFlowToStock.signature.fqn,
                "method_version": PeriodFlowToStock.signature.version,
            }
        )
        with pytest.raises(ValueError, match="model_input_graph_method_instance_duplicate"):
            _graph_input_dependencies(
                case.store,
                nodes={**nodes, "second": duplicate},
                order={"first": 0, "second": 1},
                registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
                steps=(0,),
                overrides={},
            )

        extra_abi_input = nodes["first"].model_copy(
            update={"inputs": ["period_flow", "foreign.slot"]}
        )
        with pytest.raises(ValueError, match="model_input_method_abi_join_not_exact"):
            _graph_input_dependencies(
                case.store,
                nodes={"first": extra_abi_input},
                order={"first": 0},
                registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
                steps=(0,),
                overrides={},
            )

        unregistered = nodes["first"].model_copy(
            update={
                "method_fqn": "tests.unregistered_method_input@1.0.0",
                "method_version": "1.0.0",
            }
        )
        with pytest.raises(ValueError, match="model_input_method_registry_unresolved"):
            _graph_input_dependencies(
                case.store,
                nodes={"first": unregistered},
                order={"first": 0},
                registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
                steps=(0,),
                overrides={},
            )

        original_signature = PeriodFlowToStock.signature
        target_parameter = next(
            parameter
            for parameter in original_signature.parameters
            if parameter.name == "target_slot"
        )
        changed_signature = replace(
            original_signature,
            parameters=(replace(target_parameter, default="government.balance"),),
        )
        monkeypatch.setattr(PeriodFlowToStock, "signature", changed_signature)
        changed_dependencies, _ = _graph_input_dependencies(
            case.store,
            nodes={"first": nodes["first"]},
            order={"first": 0},
            registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
            steps=(0,),
            overrides={},
        )
        assert changed_dependencies["period_flow"][0].method_abi_digest == (
            changed_signature.abi_digest()
        )
        assert changed_dependencies["period_flow"][0].method_abi_digest != (
            original_signature.abi_digest()
        )

        monkeypatch.setattr(
            PeriodFlowToStock,
            "signature",
            replace(changed_signature, version="1.0.1"),
        )
        with pytest.raises(ValueError, match="model_input_method_registry_mismatch"):
            _graph_input_dependencies(
                case.store,
                nodes={"first": nodes["first"]},
                order={"first": 0},
                registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
                steps=(0,),
                overrides={},
            )
    finally:
        case.close()
        method_registry.unregister(alternate.signature.fqn)
        method_registry.unregister(read_only.signature.fqn)
        method_registry.unregister(incompatible.signature.fqn)


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
