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
    load_core_json_artifact,
    validate_core_model_json_artifact,
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
    ModelInputObligationSet,
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    ProgramGraphInputDependency,
    load_model_input_obligation,
    load_model_input_obligation_set,
    load_program_graph_input_interface,
    model_input_obligation_set_inputs,
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


def test_registered_override_writes_do_not_invent_additive_prestate(tmp_path: Path) -> None:
    from polisyos.core.contracts.foundry import ExecPlan
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.execute.model_input_requirements import _graph_input_dependencies
    from tests.unit.foundry.runtime.test_program_graph_mixed_calls import _joint_case

    case, _metadata = _joint_case(tmp_path)
    try:
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        dependencies, graph_slots = _graph_input_dependencies(
            case.store,
            nodes={node.node_id: node for node in graph.nodes},
            order={node_id: index for index, node_id in enumerate(plan.order)},
            registry=registry,
            steps=(0,),
            overrides={},
            method_input_slots=frozenset({"period_flow"}),
        )
        assert {"agents.employer_id", "agents.is_employed", "firms.labor_count"} <= graph_slots
        assert "firms.labor_count" not in dependencies
        for slot_id in ("agents.employer_id", "agents.is_employed"):
            assert [(item.node_id, item.kind) for item in dependencies[slot_id]] == [
                ("fixture_labor", "mechanism_read")
            ]
        assert {(item.node_id, item.kind) for item in dependencies["agents.income"]} == {
            ("fixture_labor", "mechanism_read"),
            ("fixture_labor", "additive_prestate"),
            ("fixture_subsidy", "mechanism_read"),
            ("fixture_subsidy", "additive_prestate"),
        }
        slots = registry.slot_registry.slots
        mismatched_slot = slots["agents.employer_id"].model_copy(
            update={"merge_rule": slots["agents.income"].merge_rule}
        )
        mismatched_registry = replace(
            registry,
            slot_registry=registry.slot_registry.model_copy(
                update={"slots": slots | {"agents.employer_id": mismatched_slot}}
            ),
        )
        unsupported_registry = replace(
            registry,
            merge_registry=registry.merge_registry.model_copy(
                update={
                    "rules": registry.merge_registry.rules
                    | {
                        "override": registry.merge_registry.rules["priority"].model_copy(
                            update={"rule_id": "override"}
                        )
                    }
                }
            ),
        )
        for wrong_registry, reason in (
            (mismatched_registry, "model_input_additive_prestate_unresolved"),
            (unsupported_registry, "model_input_mechanism_write_merge_unsupported"),
        ):
            with pytest.raises(ValueError, match=f"^{reason}$"):
                _graph_input_dependencies(
                    case.store,
                    nodes={node.node_id: node for node in graph.nodes},
                    order={node_id: index for index, node_id in enumerate(plan.order)},
                    registry=wrong_registry,
                    steps=(0,),
                    overrides={},
                    method_input_slots=frozenset({"period_flow"}),
                )
        preflight = _preflight(case, _interface(case), _context(case), steps=(0,))
        assert set(preflight.supplied_initial_slots) == {
            "agents.income",
            "government.balance",
            "agents.skill_level",
            "agents.is_employed",
            "agents.employer_id",
            "firms.wage_offer",
        }
        selected = verify_program_graph_input_preflight(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            expected_invocation=preflight.invocation,
        )
        assert selected.supplied_initial_slots == preflight.supplied_initial_slots
        (obligation_ref,) = selected.obligation_refs
        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.port.slot_id == "period_flow"
        assert {item.kind for item in obligation.dependencies} == {"method_read"}
    finally:
        case.close()


def test_registered_override_read_still_requires_an_explicit_source(tmp_path: Path) -> None:
    from tests.unit.foundry.runtime.test_program_graph_mixed_calls import _joint_case

    case, _metadata = _joint_case(tmp_path, missing_initial_slot="agents.employer_id")
    try:
        # The canonical state contains the no-employer default, but its presence
        # is not proof that this required read was supplied by the selected source.
        state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        assert state.agents.employer_id.tolist() == [-1] * 64
        with pytest.raises(ValueError, match=r"^model_input_graph_dependency_unexplained$"):
            _preflight(case, _interface(case), _context(case), steps=(0,))
    finally:
        case.close()


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
    candidate = load_core_json_artifact(case.store, case.policy_candidate_ref)
    candidate_id = candidate.get("candidate_id") if isinstance(candidate, dict) else None
    if not isinstance(candidate_id, str) or not candidate_id:
        raise AssertionError("selected_candidate_id_missing_from_persisted_candidate")
    return ModelInputContext(
        run_id="model-input-preflight-test",
        candidate_id=candidate_id,
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


def test_current_use_method_input_revalidation_replays_two_port_source_and_requires_both_again(
    tmp_path: Path,
) -> None:
    from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
    from polisyos.foundry.data_plane.bindings import load_input_bindings
    from polisyos.foundry.execute.model_input_requirements import (
        verify_current_use_method_input_revalidation,
    )
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.runtime.quality.model_input_requirements import (
        preflight_current_use_method_input_revalidation,
    )
    from polisyos.runtime.quality.model_input_routing import (
        materialize_registered_derived_model_inputs,
    )
    from tests._helpers.registered_derived_method_input import (
        prepare_registered_method_input_preflight,
        prepare_registered_method_input_request,
    )
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    slots = ("ledger.a", "ledger.b")
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        method_input_slots=slots,
        mapped=True,
    )
    try:
        source_preflight = prepare_registered_method_input_preflight(case)
        source_set, source_members = load_model_input_obligation_set(
            case.store, source_preflight.obligation_set_ref
        )
        obligation_refs = {
            member.port.slot_id: ref
            for ref, member in zip(source_set.obligation_refs, source_members, strict=True)
        }
        assert set(obligation_refs) == set(slots)

        per_port = metadata["method_inputs_by_slot"]
        requests = tuple(
            prepare_registered_method_input_request(
                case,
                per_port[slot],
                preflight=source_preflight,
                model_input_obligation_ref=obligation_refs[slot],
                ratio_value=Decimal("-0.03") if slot == "ledger.a" else Decimal("0.01"),
                binding_id=f"revalidation-{slot}",
            )
            for slot in slots
        )
        source = materialize_registered_derived_model_inputs(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=source_preflight.obligation_set_ref,
            inputs=requests,
        )
        source_bindings = load_input_bindings(case.store, source.input_bindings_ref)
        assert source_bindings.schema_version == "1.4"
        assert {item.slot_id for item in source_bindings.selected_method_inputs} == set(slots)

        source_manifest = load_resolved_input_binding_manifest(
            case.store, source.resolved_binding_manifest_ref
        )
        old_set, _ = load_model_input_obligation_set(
            case.store, source_manifest.model_input_obligation_set_ref
        )
        current_context = source_preflight.invocation.context.model_copy(
            update={"run_id": "current-use-method-input-revalidation"}
        )
        assert old_set.invocation.context != current_context

        current = preflight_current_use_method_input_revalidation(
            case.store,
            interface_ref=_interface(case),
            program_graph_ref=ProgramGraphRef.model_validate(case.program_graph_ref.model_dump()),
            exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump()),
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=source.input_bindings_ref,
            context=current_context,
            steps=(0,),
        )
        fresh_store = FileSystemCAS(case.store.root)
        selected_set, members = load_model_input_obligation_set(
            fresh_store, current.obligation_set_ref
        )
        assert selected_set.schema_version == "1.3"
        assert selected_set.purpose == "current_use_method_input_revalidation"
        assert selected_set.authority_purpose == "candidate_execution_input_revalidation_only"
        assert selected_set.invocation.context == current_context
        assert selected_set.required_step_scopes is None
        assert {member.port.slot_id for member in members} == set(slots)
        assert all(member.context == current_context for member in members)
        assert len(source_bindings.selected_method_inputs) == len(members) == 2

        assert (
            verify_current_use_method_input_revalidation(
                fresh_store,
                obligation_set_ref=current.obligation_set_ref,
                expected_invocation=current.invocation,
            )
            == selected_set
        )
        with pytest.raises(ValueError, match="model_input_preflight_purpose_mismatch"):
            verify_program_graph_input_preflight(
                fresh_store,
                obligation_set_ref=current.obligation_set_ref,
                expected_invocation=current.invocation,
            )

        missing_source_blob = source_bindings.selected_method_inputs[0].npy_value_ref
        source_blob_path = (
            case.store.root
            / "artifacts"
            / "sha256"
            / missing_source_blob.artifact_id.hex[:2]
            / missing_source_blob.artifact_id.hex[2:4]
            / f"{missing_source_blob.artifact_id.hex}.blob"
        )
        held_source_blob = source_blob_path.with_suffix(".held")
        source_blob_path.rename(held_source_blob)
        try:
            with pytest.raises((ValueError, FileNotFoundError)):
                verify_current_use_method_input_revalidation(
                    fresh_store,
                    obligation_set_ref=current.obligation_set_ref,
                    expected_invocation=current.invocation,
                )
        finally:
            held_source_blob.rename(source_blob_path)

        def persist_tampered_set(value: ModelInputObligationSet) -> ArtifactRef:
            return case.store.put_json(
                value,
                PutOptions(
                    kind=ModelInputObligationSet.ARTIFACT_KIND,
                    media_type=ModelInputObligationSet.ARTIFACT_MEDIA_TYPE,
                    schema=SchemaInfo(
                        name=ModelInputObligationSet.ARTIFACT_SCHEMA_NAME,
                        version=value.schema_version,
                    ),
                    inputs=model_input_obligation_set_inputs(value),
                ),
                return_selected_profile=True,
            )

        omitted = selected_set.model_copy(
            update={"obligation_refs": selected_set.obligation_refs[:1]}
        )
        omitted_ref = persist_tampered_set(omitted)
        with pytest.raises(ValueError, match="model_input_revalidation_method_ports_missing"):
            load_model_input_obligation_set(fresh_store, omitted_ref)

        false_supplied = selected_set.model_copy(
            update={
                "supplied_initial_slots": tuple(
                    sorted((*selected_set.supplied_initial_slots, "ledger.a"))
                )
            }
        )
        false_supplied_ref = persist_tampered_set(false_supplied)
        with pytest.raises(ValueError, match="model_input_obligation_set_membership_mismatch"):
            load_model_input_obligation_set(fresh_store, false_supplied_ref)

        missing_purpose = selected_set.model_copy(update={"purpose": None})
        missing_purpose_ref = persist_tampered_set(missing_purpose)
        with pytest.raises(
            ValueError, match="model_input_obligation_set_revalidation_purpose_required"
        ):
            load_model_input_obligation_set(fresh_store, missing_purpose_ref)

        grafted_prestate = selected_set.prestate_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )

        def persist_untrusted_prestate_member(ref: ArtifactRef, member: object) -> ArtifactRef:
            # The verified producer correctly refuses this graft. Persist
            # adversarial CAS bytes to exercise the independent reader too.
            manifest = case.store.get_manifest(ref)
            assert sum(edge.role == "selected_prestate" for edge in manifest.inputs) == 1
            return case.store.put_json(
                member,
                PutOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    inputs=[
                        input_ref_from_artifact_ref(grafted_prestate, role=edge.role)
                        if edge.role == "selected_prestate"
                        else edge
                        for edge in manifest.inputs
                    ],
                ),
                return_selected_profile=True,
            )

        grafted_member_refs = tuple(
            persist_untrusted_prestate_member(
                ref, member.model_copy(update={"prestate_ref": grafted_prestate})
            )
            for ref, member in zip(selected_set.obligation_refs, members, strict=True)
        )
        grafted_state_set = selected_set.model_copy(
            update={
                "prestate_ref": grafted_prestate,
                "obligation_refs": grafted_member_refs,
            }
        )
        grafted_state_ref = persist_tampered_set(grafted_state_set)
        with pytest.raises(ValueError, match=r"^model_input_obligation_prestate_mismatch$"):
            verify_current_use_method_input_revalidation(
                fresh_store,
                obligation_set_ref=grafted_state_ref,
                expected_invocation=current.invocation,
            )

        method_registry = MethodRegistry.get_instance()
        changed_parameters = (
            replace(PeriodFlowToStock.signature.parameters[0], default="government.balance"),
        )

        class ChangedPeriodFlowToStock(PeriodFlowToStock):
            signature = replace(PeriodFlowToStock.signature, parameters=changed_parameters)

        method_registry.register(ChangedPeriodFlowToStock, override=True)
        try:
            with pytest.raises(ValueError, match="model_input_preflight_replay_mismatch"):
                verify_current_use_method_input_revalidation(
                    fresh_store,
                    obligation_set_ref=current.obligation_set_ref,
                    expected_invocation=current.invocation,
                )
        finally:
            method_registry.register(PeriodFlowToStock, override=True)
    finally:
        case.close()


def test_persistent_model_state_supplies_pathless_method_target_prestate(
    tmp_path: Path,
) -> None:
    from polisyos.core.contracts import ExecPlan, ProgramGraph, ProgramNode
    from polisyos.core.contracts.method_input import RegistrySlotInputPortSource
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.data_plane.bindings import load_input_bindings
    from polisyos.foundry.execute.model_input_requirements import (
        _graph_input_dependencies,
        _open_selected_model_state_context,
    )
    from polisyos.foundry.methods.base import (
        MethodMetadata,
        SideEffectProfile,
        foundry_method,
    )
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.foundry.methods.registry import MethodRegistry
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        state_writes=("model.accumulated_flow",),
        persistent_stock_slot="model.accumulated_flow",
        persistent_stock_value=10_000_000_000.0,
    )
    try:
        bindings = load_input_bindings(case.store, case.input_bindings_ref)
        assert bindings.schema_version == "1.0"
        assert bindings.bound_state_snapshot_ref == case.bound_state_snapshot_ref
        assert (
            case.store.get_manifest(case.bound_state_snapshot_ref).artifact_schema.version
            == "2.4.0"
        )

        interface_ref = _interface(case)
        preflight = _preflight(case, interface_ref, _context(case), steps=(0,))
        assert preflight.supplied_initial_slots == ()
        (obligation_ref,) = preflight.obligation_refs
        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.port.slot_id == "period_flow"
        assert obligation.prestate_ref == case.bound_state_snapshot_ref
        assert obligation.dependencies == (
            ProgramGraphInputDependency(
                node_id="period_flow_node",
                kind="method_read",
                first_required_step=0,
                method_abi_digest=PeriodFlowToStock.signature.abi_digest(),
            ),
        )

        state_context = _open_selected_model_state_context(
            case.store,
            bound_state_snapshot_ref=bindings.bound_state_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
        )
        assert state_context is not None
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        dependencies, graph_slots = _graph_input_dependencies(
            case.store,
            nodes={node.node_id: node for node in graph.nodes},
            order={node_id: index for index, node_id in enumerate(plan.order)},
            registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
            steps=(0,),
            overrides={},
            program_graph_schema_version=graph.schema_version,
            model_state_context=state_context,
            method_input_slots=frozenset({"period_flow"}),
        )
        assert graph_slots == {"model.accumulated_flow", "period_flow"}
        assert dependencies["model.accumulated_flow"] == [
            ProgramGraphInputDependency(
                node_id="period_flow_node",
                kind="additive_prestate",
                first_required_step=0,
            )
        ]

        class PersistentStockReader(PeriodFlowToStock):
            signature = replace(
                PeriodFlowToStock.signature,
                namespace="",
                version="0.0.0",
                parameters=(),
                patch_targets=(),
            )
            side_effect_profile = SideEffectProfile.NONE
            metadata = MethodMetadata(
                description="Read a selected scalar stock without a write target.",
                side_effect_profile=SideEffectProfile.NONE,
            )

            @staticmethod
            def pure_step(
                state: dict[str, object], _params: dict[str, object]
            ) -> dict[str, object]:
                return {"result": state["period_flow"]}

        read_only = foundry_method(namespace="test.accounting", version="1.0.0")(
            PersistentStockReader
        )
        method_registry = MethodRegistry.get_instance()
        method_registry.register(read_only, override=True)
        read_node = ProgramNode(
            node_id="persistent_stock_read",
            node_kind="method",
            method_fqn=read_only.signature.fqn,
            method_version=read_only.signature.version,
            method_params={},
            inputs=["model.accumulated_flow"],
            outputs=[],
            input_ports={
                "period_flow": RegistrySlotInputPortSource(
                    source_kind="registry_slot",
                    slot_id="model.accumulated_flow",
                )
            },
        )
        try:
            read_dependencies, read_slots = _graph_input_dependencies(
                case.store,
                nodes={"persistent_stock_read": read_node},
                order={"persistent_stock_read": 0},
                registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
                steps=(0,),
                overrides={},
                program_graph_schema_version="0.3",
                model_state_context=state_context,
            )
            assert read_slots == {"model.accumulated_flow"}
            assert read_dependencies["model.accumulated_flow"] == [
                ProgramGraphInputDependency(
                    node_id="persistent_stock_read",
                    kind="method_read",
                    first_required_step=0,
                    method_abi_digest=read_only.signature.abi_digest(),
                )
            ]
            with pytest.raises(
                ValueError,
                match="model_scalar_state_input_source_ambiguous",
            ):
                _graph_input_dependencies(
                    case.store,
                    nodes={"persistent_stock_read": read_node},
                    order={"persistent_stock_read": 0},
                    registry=load_registry_bundle_content(case.store, case.registry_bundle_ref),
                    steps=(0,),
                    overrides={},
                    program_graph_schema_version="0.3",
                    model_state_context=state_context,
                    method_input_slots=frozenset({"model.accumulated_flow"}),
                )
        finally:
            method_registry.unregister(read_only.signature.fqn)

        selected_set = verify_program_graph_input_preflight(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            expected_invocation=preflight.invocation,
        )
        assert selected_set.obligation_refs == (obligation_ref,)
    finally:
        case.close()


def test_persistent_model_state_preflight_refuses_absent_pathless_target(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        state_writes=("model.accumulated_flow",),
        persistent_stock_slot="model.accumulated_flow",
        persistent_stock_value=None,
    )
    try:
        interface_ref = _interface(case)
        with pytest.raises(ValueError, match="model_scalar_state_slot_absent"):
            _preflight(case, interface_ref, _context(case), steps=(0,))
    finally:
        case.close()


def test_temporal_method_input_persists_full_step_scope_denominator_and_replays(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.ir.kernel.time_semantics import TimeFrequency, TimeSemantics
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        period_step_profile=True,
        time_semantics=TimeSemantics(
            frequency=TimeFrequency.YEAR,
            start_date="2020-01-01",
            step_count=2,
        ),
        scope=ModelInputScope(
            population_ref="population:government",
            geography_ref="UA",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2020, 1, 1),
            period_end=date(2021, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
    )
    try:
        interface_ref = _interface(case)
        interface = load_program_graph_input_interface(case.store, interface_ref)
        assert interface.schema_version == "1.2"
        (port,) = interface.ports
        assert port.period_step_profile is not None

        preflight = _preflight(case, interface_ref, _context(case), steps=(0, 1))
        (obligation_ref,) = preflight.obligation_refs
        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.schema_version == "1.2"
        (dependency,) = obligation.dependencies
        assert dependency.required_steps == (0, 1)
        assert dependency.first_required_step == 0

        fresh_store = FileSystemCAS(case.store.root)
        selected_set, members = load_model_input_obligation_set(
            fresh_store, preflight.obligation_set_ref
        )
        assert selected_set.schema_version == "1.2"
        assert selected_set.obligation_refs == (obligation_ref,)
        assert tuple(
            (item.port_id, item.step, item.scope.period_start, item.scope.period_end)
            for item in selected_set.required_step_scopes or ()
        ) == (
            (port.port_id, 0, date(2020, 1, 1), date(2020, 12, 31)),
            (port.port_id, 1, date(2021, 1, 1), date(2021, 12, 31)),
        )
        assert len(members) == 1
        assert (
            verify_program_graph_input_preflight(
                fresh_store,
                obligation_set_ref=preflight.obligation_set_ref,
                expected_invocation=preflight.invocation,
            )
            == selected_set
        )

        tampered_set = selected_set.model_copy(
            update={"required_step_scopes": selected_set.required_step_scopes[:-1]}
        )
        tampered_ref = persist_model_input_obligation_set(fresh_store, tampered_set)
        with pytest.raises(
            ValueError, match="model_input_obligation_set_step_scope_denominator_mismatch"
        ):
            load_model_input_obligation_set(FileSystemCAS(case.store.root), tampered_ref)
    finally:
        case.close()


def test_temporal_method_input_refuses_missing_clock_and_short_scope_envelope(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.ir.kernel.time_semantics import TimeFrequency, TimeSemantics
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    temporal_clock = TimeSemantics(
        frequency=TimeFrequency.YEAR,
        start_date="2020-01-01",
        step_count=2,
    )
    envelope = ModelInputScope(
        population_ref="population:government",
        geography_ref="UA",
        jurisdiction_ref="jurisdiction:fixture",
        period_start=date(2020, 1, 1),
        period_end=date(2020, 12, 31),
        time_role="observation_time",
        period_basis="calendar_year",
    )
    for time_semantics, expected in (
        (None, "model_input_temporal_profile_time_semantics_missing"),
        (temporal_clock, "model_input_step_scope_outside_envelope"),
    ):
        case, _ = prepare_selected_method_input_case(
            tmp_path,
            method_class=PeriodFlowToStock,
            period_step_profile=True,
            time_semantics=time_semantics,
            scope=envelope.model_copy(deep=True),
        )
        try:
            interface_ref = _interface(case)
            with pytest.raises(ValueError, match=expected):
                _preflight(case, interface_ref, _context(case), steps=(0, 1))
        finally:
            case.close()


def test_mapped_method_input_preflight_joins_global_slot_for_repeated_method(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts.method_input import RegistrySlotInputPortSource
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        method_input_slot="ledger.flow",
        method_instances=2,
        mapped=True,
    )
    try:
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        assert graph.schema_version == "0.3"
        method_nodes = [node for node in graph.nodes if node.node_kind == "method"]
        assert len(method_nodes) == 2
        assert len({node.method_fqn for node in method_nodes}) == 1
        assert all(node.inputs == ["ledger.flow"] for node in method_nodes)
        assert all(
            node.input_ports
            == {
                "period_flow": RegistrySlotInputPortSource(
                    source_kind="registry_slot",
                    slot_id="ledger.flow",
                )
            }
            for node in method_nodes
        )

        interface_ref = _interface(case)
        preflight = _preflight(case, interface_ref, _context(case), steps=(0,))
        (obligation_ref,) = preflight.obligation_refs
        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.port.slot_id == "ledger.flow"
        assert [
            (dependency.node_id, dependency.kind, dependency.method_abi_digest)
            for dependency in obligation.dependencies
        ] == [
            (node.node_id, "method_read", PeriodFlowToStock.signature.abi_digest())
            for node in method_nodes
        ]
        selected_set = verify_program_graph_input_preflight(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            expected_invocation=preflight.invocation,
        )
        assert selected_set.obligation_refs == (obligation_ref,)
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
    from polisyos.core.contracts.method_input import (
        MethodOutputInputPortSource,
        RegistrySlotInputPortSource,
    )
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

    class AliasedReadOnlyPeriodFlow(ReadOnlyPeriodFlow):
        signature = replace(
            ReadOnlyPeriodFlow.signature,
            namespace="",
            version="0.0.0",
            input_slots=frozenset(
                {
                    period_flow_abi,
                    replace(period_flow_abi, name="matching_flow"),
                }
            ),
        )

        @staticmethod
        def pure_step(state: dict[str, object], _params: dict[str, object]) -> dict[str, object]:
            return {"result": state["period_flow"] + state["matching_flow"]}

    aliased = foundry_method(namespace="test.accounting", version="1.3.0")(
        AliasedReadOnlyPeriodFlow
    )
    method_registry = MethodRegistry.get_instance()
    method_registry.register(alternate, override=True)
    method_registry.register(read_only, override=True)
    method_registry.register(incompatible, override=True)
    method_registry.register(aliased, override=True)
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

        aliased_node = ProgramNode(
            node_id="aliased_first",
            node_kind="method",
            method_fqn=aliased.signature.fqn,
            method_version=aliased.signature.version,
            method_params={},
            inputs=["period_flow"],
            outputs=[],
            input_ports={
                "period_flow": RegistrySlotInputPortSource(
                    source_kind="registry_slot",
                    slot_id="period_flow",
                ),
                "matching_flow": RegistrySlotInputPortSource(
                    source_kind="registry_slot",
                    slot_id="period_flow",
                ),
            },
        )
        aliased_nodes = {
            "aliased_first": aliased_node,
            "aliased_second": aliased_node.model_copy(update={"node_id": "aliased_second"}),
        }
        aliased_dependencies, aliased_slots = _graph_input_dependencies(
            case.store,
            nodes=aliased_nodes,
            order={"aliased_first": 0, "aliased_second": 1},
            registry=selected_registry,
            steps=(0,),
            overrides={},
            program_graph_schema_version="0.3",
        )
        assert aliased_slots == {"period_flow"}
        assert aliased_dependencies["period_flow"] == [
            ProgramGraphInputDependency(
                node_id=node_id,
                kind="method_read",
                first_required_step=0,
                method_abi_digest=aliased.signature.abi_digest(),
            )
            for node_id in ("aliased_first", "aliased_second")
        ]

        unsupported_output_node = ProgramNode(
            node_id="unsupported_output",
            node_kind="method",
            method_fqn=read_only.signature.fqn,
            method_version=read_only.signature.version,
            method_params={},
            inputs=[],
            outputs=[],
            input_ports={
                "period_flow": MethodOutputInputPortSource(
                    source_kind="method_output",
                    producer_node_id="producer",
                    output_slot_id="result",
                )
            },
        )
        with pytest.raises(
            ValueError,
            match="model_input_method_dataflow_not_verified",
        ):
            _graph_input_dependencies(
                case.store,
                nodes={"unsupported_output": unsupported_output_node},
                order={"unsupported_output": 0},
                registry=selected_registry,
                steps=(0,),
                overrides={},
                program_graph_schema_version="0.3",
            )

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

        foreign_mapped_node = read_only_node.model_copy(
            update={
                "inputs": ["foreign.flow"],
                "input_ports": {
                    "period_flow": RegistrySlotInputPortSource(
                        source_kind="registry_slot",
                        slot_id="foreign.flow",
                    )
                },
            }
        )
        with pytest.raises(ValueError, match="model_input_method_slot_unregistered"):
            _graph_input_dependencies(
                case.store,
                nodes={"foreign_mapped": foreign_mapped_node},
                order={"foreign_mapped": 0},
                registry=selected_registry,
                steps=(0,),
                overrides={},
                program_graph_schema_version="0.3",
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
        method_registry.unregister(aliased.signature.fqn)


def test_method_output_transfer_is_internal_to_preflight_dag(tmp_path: Path) -> None:
    from polisyos.core.canon import CanonSpec
    from polisyos.core.compiler.report import CompileReport
    from polisyos.core.contracts.execution_plan import (
        ExecutionPlan,
        ExecutionPlanRef,
        MethodDagNode,
    )
    from polisyos.core.contracts.foundry import CompileRequest, ExecPlan
    from polisyos.core.contracts.method_input import MethodOutputInputPortSource
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.compile.method_dataflow import (
        resolve_program_graph_method_input_sources,
    )
    from polisyos.foundry.methods.base import MethodMetadata, SideEffectProfile, foundry_method
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.foundry.methods.selection.registry import MethodRegistry
    from tests._helpers.selected_method_input import prepare_selected_method_input_case

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
            description="Copy a typed period flow through a pure method output.",
            side_effect_profile=SideEffectProfile.NONE,
        )

        @staticmethod
        def pure_step(state: dict[str, object], _params: dict[str, object]) -> dict[str, object]:
            return {"result": state["period_flow"]}

    pure_method = foundry_method(namespace="test.accounting", version="1.1.0")(ReadOnlyPeriodFlow)
    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
    )
    method_registry = MethodRegistry.get_instance()
    try:
        method_registry.register(pure_method, override=True)
        signature = pure_method.signature
        method_plan = ExecutionPlan(
            schema_version="1.2",
            plan_id="method-output-preflight",
            method_dag=[
                MethodDagNode(
                    node_id="flow_source",
                    method_fqn=signature.fqn,
                    method_version=signature.version,
                    backend=signature.execution_backend.value,
                    reads_slots=["period_flow"],
                    writes_slots=["result"],
                    state_writes=[],
                    input_ports={
                        "period_flow": {
                            "source_kind": "registry_slot",
                            "slot_id": "period_flow",
                        }
                    },
                ),
                MethodDagNode(
                    node_id="flow_consumer",
                    method_fqn=signature.fqn,
                    method_version=signature.version,
                    backend=signature.execution_backend.value,
                    reads_slots=["period_flow"],
                    writes_slots=["result"],
                    state_writes=[],
                    input_ports={
                        "period_flow": {
                            "source_kind": "method_output",
                            "producer_node_id": "flow_source",
                            "output_slot_id": "result",
                        }
                    },
                ),
            ],
        )
        plan_ref = case.store.put_json(
            method_plan,
            PutOptions(
                kind="scientist.execution_plan",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.ExecutionPlan", version="1.2"),
                inputs=[input_ref_from_artifact_ref(case.trinity_ref, role="policy_candidate")],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        compiled = compile_foundry(
            case.store,
            CompileRequest(
                schema_version="1.2",
                input_kind="trinity",
                policy_ref=case.trinity_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                method_execution_plan_ref=ExecutionPlanRef.model_validate(plan_ref.model_dump()),
                return_selected_profile=True,
            ),
        )
        if not compiled.ok or compiled.exec_plan_ref is None:
            compile_report = validate_core_model_json_artifact(
                CompileReport,
                case.store,
                compiled.compile_report_ref,
            )
            pytest.fail(
                "selected method-output plan did not compile: "
                f"report_ref={compiled.compile_report_ref!r}, notes={compile_report.notes!r}"
            )
        (graph_ref,) = (item.ref for item in compiled.derived_refs if item.role == "program_graph")
        selected_case = replace(
            case,
            exec_plan_ref=compiled.exec_plan_ref,
            program_graph_ref=graph_ref,
        )
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, graph_ref)
        assert graph.schema_version == "0.3"
        method_nodes = {node.node_id: node for node in graph.nodes if node.node_kind == "method"}
        assert method_nodes["flow_source"].inputs == ["period_flow"]
        assert method_nodes["flow_consumer"].inputs == []

        selected_registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        selected_exec_plan = validate_core_model_json_artifact(
            ExecPlan, case.store, compiled.exec_plan_ref
        )
        resolution = resolve_program_graph_method_input_sources(
            graph,
            registry=MethodRegistry.get_instance(),
            registry_content=selected_registry,
            order=selected_exec_plan.order,
            allow_method_output=True,
        )
        assert resolution.registry_inputs["flow_source"] == ("period_flow",)
        assert resolution.registry_inputs["flow_consumer"] == ()
        assert resolution.dependency_edges == (("flow_source", "flow_consumer"),)

        missing_edge_graph = graph.model_copy(
            update={
                "edges": [
                    edge
                    for edge in graph.edges
                    if (edge.src, edge.dst) != ("flow_source", "flow_consumer")
                ]
            }
        )
        with pytest.raises(
            ValueError,
            match="method_dataflow_persisted_output_edge_missing",
        ):
            resolve_program_graph_method_input_sources(
                missing_edge_graph,
                registry=MethodRegistry.get_instance(),
                registry_content=selected_registry,
                order=selected_exec_plan.order,
                allow_method_output=True,
            )

        wrong_output_graph = ProgramGraph.model_validate(
            graph.model_dump(mode="python")
            | {
                "nodes": [
                    node.model_dump(mode="python")
                    | {
                        "input_ports": {
                            "period_flow": MethodOutputInputPortSource(
                                source_kind="method_output",
                                producer_node_id="flow_source",
                                output_slot_id="same_value_wrong_slot",
                            ).model_dump(mode="python")
                        }
                    }
                    if node.node_id == "flow_consumer"
                    else node.model_dump(mode="python")
                    for node in graph.nodes
                ]
            }
        )
        with pytest.raises(ValueError, match="method_dataflow_producer_output_slot_missing"):
            resolve_program_graph_method_input_sources(
                wrong_output_graph,
                registry=MethodRegistry.get_instance(),
                registry_content=selected_registry,
                order=selected_exec_plan.order,
                allow_method_output=True,
            )

        interface_ref = _interface(selected_case)
        preflight = _preflight(selected_case, interface_ref, _context(selected_case), steps=(0,))
        (obligation_ref,) = preflight.obligation_refs
        obligation = load_model_input_obligation(case.store, obligation_ref)
        assert obligation.port.slot_id == "period_flow"
        assert obligation.dependencies == (
            ProgramGraphInputDependency(
                node_id="flow_source",
                kind="method_read",
                first_required_step=0,
                method_abi_digest=signature.abi_digest(),
            ),
        )
        assert preflight.supplied_initial_slots == ()
        selected_set = verify_program_graph_input_preflight(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            expected_invocation=preflight.invocation,
        )
        assert selected_set.obligation_refs == (obligation_ref,)
    finally:
        case.close()
        method_registry.unregister(pure_method.signature.fqn)


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
