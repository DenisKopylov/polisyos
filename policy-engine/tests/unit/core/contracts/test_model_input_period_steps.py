from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    FoundryInputBindingsRef,
    ProgramGraphRef,
    StateSnapshotRef,
)
from polisyos.core.contracts.model_input_period_steps import (
    ModelInputPeriodStepProfile,
    ModelInputStepScope,
    derive_model_input_step_scopes,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputObligationSet,
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    ProgramGraphInputDependency,
    ProgramGraphInputInvocation,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementBindingProfileRef,
    ModelInputScope,
    VariableRepresentationRef,
    VariableSemanticDefinitionRef,
)
from polisyos.ir.kernel import TimeSemantics
from polisyos.ir.model_layer.types import TimeFrequency


def _profile() -> ModelInputPeriodStepProfile:
    return ModelInputPeriodStepProfile()


def _scope_envelope(
    *, start: date = date(2020, 1, 1), end: date = date(2021, 12, 31), basis: str = "calendar_year"
) -> ModelInputScope:
    return ModelInputScope(
        population_ref="population:all",
        geography_ref="geography:usa",
        jurisdiction_ref="jurisdiction:usa",
        period_start=start,
        period_end=end,
        time_role="observation_time",
        period_basis=basis,
    )


def _annual_time() -> TimeSemantics:
    return TimeSemantics(
        frequency=TimeFrequency.YEAR,
        start_date="2020-01-01",
        step_count=2,
    )


def _ref(kind: str, token: int) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(f"{token:064x}"),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + f"{token + 10:064x}",
    )


def _typed_ref(ref_type, kind: str, token: int):
    return ref_type.model_validate(_ref(kind, token).model_dump(mode="python"))


def _port(*, shape: tuple[int, ...] = (), axis: bool = False) -> ModelInputPort:
    return ModelInputPort(
        port_id="period_flow",
        slot_id="period_flow_slot",
        carrier="method_input",
        state_path=None,
        unit_id="unit:usd",
        purpose="simulation_input",
        semantic_definition_ref=VariableSemanticDefinitionRef(
            **_ref("catalog.variable_semantic_definition", 1).model_dump(mode="python")
        ),
        representation_ref=VariableRepresentationRef(
            **_ref("catalog.variable_representation", 2).model_dump(mode="python")
        ),
        binding_profile_ref=MeasurementBindingProfileRef(
            **_ref("catalog.measurement_binding_profile", 3).model_dump(mode="python")
        ),
        scope=_scope_envelope(),
        entity_axis_ref=(_ref("foundry.selected_entity_axis", 4) if axis else None),
        physical_encoding=ModelInputPhysicalEncoding(
            shape=shape,
            dtype="float64",
            max_absolute_error=Decimal("0"),
        ),
    )


def test_derive_step_scopes_uses_time_semantics_and_preserves_non_temporal_axes() -> None:
    scopes = derive_model_input_step_scopes(
        _profile(),
        port_id="period_flow",
        scope_envelope=_scope_envelope(),
        time_semantics=_annual_time(),
        steps=(0, 1),
    )

    assert scopes == (
        ModelInputStepScope(
            port_id="period_flow",
            step=0,
            scope=ModelInputScope(
                population_ref="population:all",
                geography_ref="geography:usa",
                jurisdiction_ref="jurisdiction:usa",
                period_start=date(2020, 1, 1),
                period_end=date(2020, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
        ),
        ModelInputStepScope(
            port_id="period_flow",
            step=1,
            scope=ModelInputScope(
                population_ref="population:all",
                geography_ref="geography:usa",
                jurisdiction_ref="jurisdiction:usa",
                period_start=date(2021, 1, 1),
                period_end=date(2021, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
        ),
    )


def test_partial_supplied_period_keeps_full_required_scope_denominator() -> None:
    scopes = derive_model_input_step_scopes(
        _profile(),
        port_id="period_flow",
        scope_envelope=_scope_envelope(),
        time_semantics=_annual_time(),
        steps=(0, 1),
    )
    supplied_steps = {0}
    missing = tuple(item for item in scopes if item.step not in supplied_steps)

    assert tuple(item.step for item in scopes) == (0, 1)
    assert tuple(item.step for item in missing) == (1,)
    assert missing[0].scope.period_start == date(2021, 1, 1)


@pytest.mark.parametrize("steps", [(0, 0), (0, 2), (1, 0), ()])
def test_steps_must_be_sorted_unique_and_contiguous(steps: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="model_input_step_scope_steps_invalid"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(),
            time_semantics=_annual_time(),
            steps=steps,
        )


def test_non_annual_or_non_calendar_year_model_is_refused() -> None:
    quarterly = TimeSemantics(
        frequency=TimeFrequency.QUARTER,
        start_date="2020-01-01",
        step_count=8,
    )
    with pytest.raises(ValueError, match="model_input_step_scope_frequency_unsupported"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(),
            time_semantics=quarterly,
            steps=(0, 1),
        )

    non_january_start = TimeSemantics(
        frequency=TimeFrequency.YEAR,
        start_date="2020-04-01",
        step_count=2,
    )
    with pytest.raises(ValueError, match="model_input_step_scope_calendar_alignment_unsupported"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(start=date(2020, 4, 1)),
            time_semantics=non_january_start,
            steps=(0, 1),
        )


def test_profile_refuses_unknown_or_rate_like_semantics() -> None:
    with pytest.raises(ValidationError):
        ModelInputPeriodStepProfile(profile_id="annual_calendar_year_rate.v1")


def test_scope_envelope_must_cover_each_derived_period_exactly() -> None:
    with pytest.raises(ValueError, match="model_input_step_scope_outside_envelope"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(end=date(2021, 6, 30)),
            time_semantics=_annual_time(),
            steps=(0, 1),
        )


def test_non_calendar_envelope_is_refused() -> None:
    with pytest.raises(ValueError, match="model_input_step_scope_basis_unsupported"):
        derive_model_input_step_scopes(
            _profile(),
            port_id="period_flow",
            scope_envelope=_scope_envelope(basis="fiscal_year"),
            time_semantics=_annual_time(),
            steps=(0, 1),
        )


def test_legacy_port_and_declaration_omit_new_temporal_and_axis_fields() -> None:
    port = _port()
    legacy = ModelInputPortDeclaration(schema_version="1.1", ports=(port,))

    dumped = port.model_dump(mode="json", exclude_defaults=True)
    assert "period_step_profile" not in dumped
    assert "entity_axis_ref" not in dumped
    assert legacy.model_dump(mode="json")["schema_version"] == "1.1"


def test_temporal_profile_requires_declaration_interface_schema_12() -> None:
    port = _port().model_copy(update={"period_step_profile": _profile()})

    with pytest.raises(ValidationError, match="model_input_declaration_version_mismatch"):
        ModelInputPortDeclaration(schema_version="1.1", ports=(port,))

    declaration = ModelInputPortDeclaration(schema_version="1.2", ports=(port,))
    assert declaration.schema_version == "1.2"


def test_new_method_input_vector_requires_exact_axis_ref_but_legacy_vectors_survive() -> None:
    vector = _port(shape=(2,))
    assert vector.physical_encoding is not None
    assert vector.physical_encoding.shape == (2,)
    # Older method-input declarations keep their historical wire and meaning.
    legacy = ModelInputPortDeclaration(schema_version="1.1", ports=(vector,))
    assert legacy.schema_version == "1.1"

    with pytest.raises(ValidationError, match="model_input_declaration_method_vector_axis_missing"):
        ModelInputPortDeclaration(schema_version="1.2", ports=(vector,))

    axis_vector = _port(shape=(2,), axis=True)
    declaration = ModelInputPortDeclaration(schema_version="1.2", ports=(axis_vector,))
    assert declaration.ports[0].entity_axis_ref is not None


def test_state_path_vector_remains_legacy_compatible_without_new_axis_ref() -> None:
    vector = _port(shape=(2,)).model_copy(
        update={"carrier": "state_path", "state_path": "state.flow", "entity_axis_ref": None}
    )
    legacy = ModelInputPortDeclaration(schema_version="1.1", ports=(vector,))

    assert legacy.ports[0].entity_axis_ref is None
    assert legacy.ports[0].physical_encoding is not None
    assert legacy.ports[0].physical_encoding.shape == (2,)


def test_required_steps_are_versioned_and_allow_exact_missing_subsets() -> None:
    legacy = ProgramGraphInputDependency(
        node_id="method-1",
        kind="method_read",
        first_required_step=0,
        method_abi_digest="a" * 64,
    )
    assert "required_steps" not in legacy.model_dump(mode="json")

    partial_gap = ProgramGraphInputDependency(
        node_id="method-1",
        kind="method_read",
        first_required_step=1,
        method_abi_digest="a" * 64,
        required_steps=(1, 3),
    )
    assert partial_gap.required_steps == (1, 3)

    with pytest.raises(ValidationError, match="model_input_dependency_required_steps_invalid"):
        ProgramGraphInputDependency(
            node_id="method-1",
            kind="method_read",
            first_required_step=0,
            method_abi_digest="a" * 64,
            required_steps=(0, 0),
        )


def _obligation_set(*, schema_version: str, required_step_scopes=None) -> ModelInputObligationSet:
    context = ModelInputContext(
        run_id="run:test",
        candidate_id="candidate:test",
        candidate_content_hash="sha256:" + "a" * 64,
        design_problem_ref="problem:test",
    )
    invocation = ProgramGraphInputInvocation(
        context=context,
        interface_ref=_ref("runtime.quality.program_graph_input_interface", 10),
        program_graph_ref=_typed_ref(ProgramGraphRef, "foundry.program_graph", 11),
        exec_plan_ref=_typed_ref(ExecPlanRef, "foundry.exec_plan", 12),
        registry_bundle_ref=_ref("core.registry_bundle", 13),
        input_bindings_ref=_typed_ref(FoundryInputBindingsRef, "foundry.input_bindings", 14),
        steps=(0, 1),
    )
    values = {
        "schema_version": schema_version,
        "invocation": invocation,
        "prestate_ref": _typed_ref(StateSnapshotRef, "foundry.state_snapshot", 15),
        "supplied_initial_slots": (),
        "obligation_refs": (),
    }
    if required_step_scopes is not None:
        values["required_step_scopes"] = required_step_scopes
    return ModelInputObligationSet(**values)


def test_obligation_set_12_requires_explicit_full_scope_field_and_old_wire_omits_it() -> None:
    old_set = _obligation_set(schema_version="1.1")
    assert "required_step_scopes" not in old_set.model_dump(mode="json")

    temporal_set = _obligation_set(schema_version="1.2", required_step_scopes=())
    assert temporal_set.required_step_scopes == ()

    with pytest.raises(ValidationError, match="model_input_obligation_set_step_scopes_missing"):
        _obligation_set(schema_version="1.2")

    with pytest.raises(ValidationError, match="model_input_obligation_set_version_mismatch"):
        _obligation_set(schema_version="1.1", required_step_scopes=())

    scopes = (
        ModelInputStepScope(
            port_id="period_flow",
            step=0,
            scope=ModelInputScope(
                population_ref="population:all",
                geography_ref="geography:usa",
                jurisdiction_ref="jurisdiction:usa",
                period_start=date(2020, 1, 1),
                period_end=date(2020, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
        ),
        ModelInputStepScope(
            port_id="period_flow",
            step=1,
            scope=ModelInputScope(
                population_ref="population:all",
                geography_ref="geography:usa",
                jurisdiction_ref="jurisdiction:usa",
                period_start=date(2021, 1, 1),
                period_end=date(2021, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
        ),
    )
    full_denominator = _obligation_set(schema_version="1.2", required_step_scopes=scopes)
    assert tuple(item.step for item in full_denominator.required_step_scopes or ()) == (0, 1)
    with pytest.raises(ValidationError, match="model_input_obligation_set_step_scopes_invalid"):
        _obligation_set(schema_version="1.2", required_step_scopes=tuple(reversed(scopes)))


def test_single_profiled_step_uses_exact_year_not_the_wider_port_envelope() -> None:
    scopes = derive_model_input_step_scopes(
        _profile(),
        port_id="period_flow",
        scope_envelope=_scope_envelope(),
        time_semantics=_annual_time(),
        steps=(0,),
    )

    assert len(scopes) == 1
    assert scopes[0].step == 0
    assert scopes[0].scope.period_start == date(2020, 1, 1)
    assert scopes[0].scope.period_end == date(2020, 12, 31)
