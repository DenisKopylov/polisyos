"""Temporal scope binding for registered composition artifacts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts.model_input_period_steps import ModelInputStepScope
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_composition_binding import (
    CandidateDerivedMeasurementRole,
    NativeDerivationSourceProjectionRef,
    RegisteredDerivationRoleBasis,
    RegisteredDerivedInputContext,
    RegisteredDerivedInputContextRef,
    RegisteredDerivedInputCorrespondence,
    RegisteredDerivedInputProfile,
    RegisteredDerivedInputProfileRef,
    RegisteredMeasurementRole,
    RegisteredRoleScope,
    RegisteredSemanticBasis,
    evaluate_registered_derived_input_correspondence,
    load_registered_derived_input_context,
    load_registered_derived_input_correspondence,
    persist_registered_derived_input_context,
    persist_registered_derived_input_correspondence,
)
from polisyos.core.contracts.semantic_step_binding import recompute_resolved_step_input_coverage
from polisyos.core.contracts.variable_binding import (
    MeasurementBindingProfile,
    ScopedMeasurementOccurrenceRef,
    SelectedVariableBindingRef,
    VariableSemanticDefinition,
    load_variable_representation,
)
from tests.unit.core.contracts.test_semantic_composition_binding import _projection_inputs
from tests.unit.core.contracts.test_temporal_semantic_input_binding import _manifest_case

_LEGACY_CONTEXT_WIRE_SHA256 = "d380b170e2dc81a09283b6ad37d20e1d68c36d76f92ea2eaf69b9e8191bd1a5d"


def _selected_ref(ref: SelectedVariableBindingRef, kind: str) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef.model_validate(ref.model_dump(mode="python") | {"kind": kind})


def _context_for_version(
    args: dict[str, object],
    *,
    version: str,
    step_scope: ModelInputStepScope | None = None,
    include_step_scope: bool = False,
) -> RegisteredDerivedInputContext:
    original = args["context"]
    assert isinstance(original, RegisteredDerivedInputContext)
    payload = original.model_dump(mode="python") | {"schema_version": version}
    if include_step_scope:
        payload["step_scope"] = step_scope
    return RegisteredDerivedInputContext.model_validate(payload)


def _correspondence_for(
    args: dict[str, object],
    context: RegisteredDerivedInputContext,
    *,
    context_ref: RegisteredDerivedInputContextRef,
    version: str,
    step_scope: ModelInputStepScope | None = None,
    include_step_scope: bool = False,
) -> RegisteredDerivedInputCorrespondence:
    profile = args["profile"]
    profile_ref = args["profile_ref"]
    assert isinstance(profile, RegisteredDerivedInputProfile)
    assert isinstance(profile_ref, RegisteredDerivedInputProfileRef)
    recipe_ref = _selected_ref(profile_ref, "polisyos.runtime.derivation_recipe")
    certificate_ref = _selected_ref(profile_ref, "polisyos.runtime.derivation_certificate")
    output_ref = _selected_ref(profile_ref, "polisyos.runtime.derived_economic_series")
    roles = tuple(
        CandidateDerivedMeasurementRole(
            role=item.role,
            source_series_ref=_selected_ref(
                item.occurrence_ref, "polisyos.core.candidate_source_series"
            ),
            source_projection_ref=NativeDerivationSourceProjectionRef.model_validate(
                _selected_ref(
                    context_ref, "catalog.native_derivation_source_projection"
                ).model_dump(mode="python")
            ),
        )
        for item in context.roles
    )
    payload: dict[str, object] = {
        "schema_version": version,
        "profile_ref": profile_ref,
        "context_ref": context_ref,
        "model_input_obligation_ref": context.model_input_obligation_ref,
        "model_interface_ref": context.model_interface_ref,
        "model_port_id": context.model_port_id,
        "recipe_ref": recipe_ref,
        "certificate_ref": certificate_ref,
        "output_ref": output_ref,
        "year": context.year,
        "roles": roles,
    }
    if include_step_scope:
        payload["step_scope"] = step_scope
    return RegisteredDerivedInputCorrespondence.model_validate(payload)


def test_context_schema_versions_keep_the_old_wire_and_bind_new_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _, args = _projection_inputs(tmp_path)
    legacy = args["context"]
    legacy_ref = args["context_ref"]
    assert isinstance(legacy, RegisteredDerivedInputContext)
    assert isinstance(legacy_ref, RegisteredDerivedInputContextRef)

    legacy_manifest = store.get_manifest(legacy_ref)
    legacy_bytes = store.get_bytes(legacy_ref.artifact_id)
    assert legacy_manifest.artifact_schema == SchemaInfo(
        name=RegisteredDerivedInputContext.ARTIFACT_SCHEMA_NAME, version="1.0"
    )
    assert "step_scope" not in legacy.model_dump(mode="json")
    assert "step_scope" not in json.loads(legacy_bytes)
    assert sha256(legacy_bytes).hexdigest() == _LEGACY_CONTEXT_WIRE_SHA256
    assert load_registered_derived_input_context(FileSystemCAS(store.root), legacy_ref) == legacy

    step_scope = ModelInputStepScope(
        port_id=legacy.model_port_id,
        step=0,
        scope=legacy.output_scope,
    )
    temporal = _context_for_version(
        args, version="1.1", step_scope=step_scope, include_step_scope=True
    )
    temporal_ref = persist_registered_derived_input_context(store, temporal)
    temporal_manifest = store.get_manifest(temporal_ref)
    temporal_bytes = store.get_bytes(temporal_ref.artifact_id)
    assert temporal_manifest.artifact_schema == SchemaInfo(
        name=RegisteredDerivedInputContext.ARTIFACT_SCHEMA_NAME, version="1.1"
    )
    assert json.loads(temporal_bytes)["step_scope"]["step"] == 0
    assert load_registered_derived_input_context(FileSystemCAS(store.root), temporal_ref) == (
        temporal
    )

    from polisyos.core.contracts import semantic_step_binding

    def forbid_clock_reload(*args: object, **kwargs: object) -> None:
        pytest.fail("context loading must not reopen the origin clock")

    monkeypatch.setattr(
        semantic_step_binding, "resolve_model_input_step_scope", forbid_clock_reload
    )
    assert load_registered_derived_input_context(FileSystemCAS(store.root), temporal_ref) == (
        temporal
    )

    missing_lineage_ref = store.put_json(
        temporal,
        PutOptions(
            kind=temporal.ARTIFACT_KIND,
            media_type=temporal.ARTIFACT_MEDIA_TYPE,
            producer=temporal_manifest.producer,
            schema=temporal_manifest.artifact_schema,
            inputs=list(temporal_manifest.inputs[:-1]),
        ),
        return_selected_profile=True,
    )
    selected_missing_lineage_ref = RegisteredDerivedInputContextRef.model_validate(
        missing_lineage_ref.model_dump(mode="python")
    )
    with pytest.raises(ValueError, match="composition_input_semantic_lineage_mismatch"):
        load_registered_derived_input_context(
            FileSystemCAS(store.root), selected_missing_lineage_ref
        )


@pytest.mark.parametrize(
    ("version", "include_step_scope", "step_scope", "reason"),
    [
        ("1.0", True, None, "composition_input_context_schema_step_scope_mismatch"),
        ("1.1", False, None, "composition_input_context_temporal_step_scope_mismatch"),
        ("1.1", True, None, "composition_input_context_temporal_step_scope_mismatch"),
    ],
)
def test_context_version_field_matrix_refuses_missing_or_forbidden_scope(
    tmp_path: Path,
    version: str,
    include_step_scope: bool,
    step_scope: ModelInputStepScope | None,
    reason: str,
) -> None:
    _, _, args = _projection_inputs(tmp_path)
    with pytest.raises(ValidationError, match=reason):
        _context_for_version(
            args,
            version=version,
            step_scope=step_scope,
            include_step_scope=include_step_scope,
        )


def test_context_one_point_one_requires_exact_port_scope_and_year(tmp_path: Path) -> None:
    _, _, args = _projection_inputs(tmp_path)
    original = args["context"]
    assert isinstance(original, RegisteredDerivedInputContext)
    step_scope = ModelInputStepScope(
        port_id=original.model_port_id,
        step=1,
        scope=original.output_scope,
    )
    context = _context_for_version(
        args, version="1.1", step_scope=step_scope, include_step_scope=True
    )
    assert context.schema_version == "1.1"
    assert context.step_scope == step_scope
    assert tuple(item.role for item in context.roles) == tuple(item.role for item in original.roles)

    with pytest.raises(
        ValidationError, match="composition_input_context_temporal_step_scope_mismatch"
    ):
        _context_for_version(
            args,
            version="1.1",
            step_scope=step_scope.model_copy(update={"port_id": "foreign.port"}),
            include_step_scope=True,
        )

    wrong_year_scope = original.output_scope.model_copy(
        update={"period_start": original.output_scope.period_start.replace(year=2023)}
    )
    with pytest.raises(
        ValidationError, match="composition_input_context_temporal_step_scope_mismatch"
    ):
        _context_for_version(
            args,
            version="1.1",
            step_scope=ModelInputStepScope(
                port_id=original.model_port_id, step=1, scope=wrong_year_scope
            ),
            include_step_scope=True,
        )


def test_correspondence_version_field_matrix_and_schema_binding(tmp_path: Path) -> None:
    store, _, args = _projection_inputs(tmp_path)
    legacy_context = args["context"]
    legacy_context_ref = args["context_ref"]
    assert isinstance(legacy_context, RegisteredDerivedInputContext)
    assert isinstance(legacy_context_ref, RegisteredDerivedInputContextRef)
    legacy = _correspondence_for(
        args,
        legacy_context,
        context_ref=legacy_context_ref,
        version="2.0",
    )
    assert "step_scope" not in legacy.model_dump(mode="json")
    legacy_ref = persist_registered_derived_input_correspondence(store, legacy)
    assert store.get_manifest(legacy_ref).artifact_schema == SchemaInfo(
        name=RegisteredDerivedInputCorrespondence.ARTIFACT_SCHEMA_NAME, version="2.0"
    )
    assert load_registered_derived_input_correspondence(FileSystemCAS(store.root), legacy_ref) == (
        legacy
    )

    step_scope = ModelInputStepScope(
        port_id=legacy_context.model_port_id,
        step=0,
        scope=legacy_context.output_scope,
    )
    temporal = _context_for_version(
        args, version="1.1", step_scope=step_scope, include_step_scope=True
    )
    temporal_ref = persist_registered_derived_input_context(store, temporal)
    temporal_correspondence = _correspondence_for(
        args,
        temporal,
        context_ref=temporal_ref,
        version="2.1",
        step_scope=step_scope,
        include_step_scope=True,
    )
    temporal_correspondence_ref = persist_registered_derived_input_correspondence(
        store, temporal_correspondence
    )
    assert store.get_manifest(temporal_correspondence_ref).artifact_schema == SchemaInfo(
        name=RegisteredDerivedInputCorrespondence.ARTIFACT_SCHEMA_NAME, version="2.1"
    )
    assert "step_scope" in json.loads(store.get_bytes(temporal_correspondence_ref.artifact_id))
    assert (
        load_registered_derived_input_correspondence(
            FileSystemCAS(store.root), temporal_correspondence_ref
        )
        == temporal_correspondence
    )

    old_payload = temporal_correspondence.model_dump(mode="python")
    old_payload.update(schema_version="2.0", step_scope=None)
    with pytest.raises(
        ValidationError, match="composition_input_correspondence_schema_step_scope_mismatch"
    ):
        RegisteredDerivedInputCorrespondence.model_validate(old_payload)
    missing_payload = temporal_correspondence.model_dump(mode="python")
    missing_payload.pop("step_scope")
    with pytest.raises(
        ValidationError, match="composition_input_correspondence_temporal_step_scope_mismatch"
    ):
        RegisteredDerivedInputCorrespondence.model_validate(missing_payload)
    with pytest.raises(
        ValidationError, match="composition_input_correspondence_temporal_step_scope_mismatch"
    ):
        RegisteredDerivedInputCorrespondence.model_validate(
            temporal_correspondence.model_dump(mode="python")
            | {"step_scope": step_scope.model_copy(update={"port_id": "foreign.port"})}
        )


def _temporal_evaluation_inputs(tmp_path: Path):
    case, manifest = _manifest_case(tmp_path)
    selected_set, obligations = load_model_input_obligation_set(
        case.store, manifest.model_input_obligation_set_ref
    )
    coverage = recompute_resolved_step_input_coverage(case.store, manifest)
    assert coverage.is_complete
    first_scope, second_scope = coverage.supplied_step_scopes
    (obligation_ref,) = selected_set.obligation_refs
    (obligation,) = obligations

    profile_ref = RegisteredDerivedInputProfileRef.model_validate(
        _selected_ref(obligation_ref, "catalog.derived_input_profile").model_dump(mode="python")
    )
    basis = RegisteredSemanticBasis(
        semantic_definition_ref=obligation.port.semantic_definition_ref,
        representation_ref=obligation.port.representation_ref,
        binding_profile_ref=obligation.port.binding_profile_ref,
    )
    profile = RegisteredDerivedInputProfile(
        registry_ref=_selected_ref(
            obligation.registry_bundle_ref, "polisyos.runtime.transform_family_registry"
        ),
        family_id="fixture.temporal_composition",
        method_version="1.0",
        ratio_role="ratio",
        denominator_role="base",
        inputs=tuple(
            RegisteredDerivationRoleBasis(role=role, basis=basis) for role in ("base", "ratio")
        ),
        output=basis,
    )
    selected_obligation_ref = SelectedVariableBindingRef.model_validate(
        obligation_ref.model_dump(mode="python")
    )
    selected_interface_ref = SelectedVariableBindingRef.model_validate(
        obligation.interface_ref.model_dump(mode="python")
    )
    selected_set_ref = SelectedVariableBindingRef.model_validate(
        manifest.model_input_obligation_set_ref.model_dump(mode="python")
    )
    role_occurrence_ref = ScopedMeasurementOccurrenceRef.model_validate(
        _selected_ref(obligation_ref, "catalog.scoped_measurement_occurrence").model_dump(
            mode="python"
        )
    )
    context = RegisteredDerivedInputContext(
        schema_version="1.1",
        profile_ref=profile_ref,
        obligation_set_ref=selected_set_ref,
        model_input_obligation_ref=selected_obligation_ref,
        model_interface_ref=selected_interface_ref,
        model_port_id=first_scope.port_id,
        registry_bundle_ref=SelectedVariableBindingRef.model_validate(
            obligation.registry_bundle_ref.model_dump(mode="python")
        ),
        year=first_scope.scope.period_start.year,
        output_scope=first_scope.scope,
        roles=tuple(
            RegisteredMeasurementRole(role=role, occurrence_ref=role_occurrence_ref)
            for role in ("base", "ratio")
        ),
        role_scopes=tuple(
            RegisteredRoleScope(role=role, scope=first_scope.scope) for role in ("base", "ratio")
        ),
        step_scope=first_scope,
    )
    context_ref = RegisteredDerivedInputContextRef.model_validate(
        _selected_ref(obligation_ref, "catalog.registered_derivation_context").model_dump(
            mode="python"
        )
    )
    correspondence = _correspondence_for(
        {"profile": profile, "profile_ref": profile_ref},
        context,
        context_ref=context_ref,
        version="2.1",
        step_scope=first_scope,
        include_step_scope=True,
    )
    target_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, case.store, obligation.port.semantic_definition_ref
    )
    target_representation = load_variable_representation(
        case.store, obligation.port.representation_ref
    )
    binding_profile = validate_core_model_json_artifact(
        MeasurementBindingProfile, case.store, obligation.port.binding_profile_ref
    )
    return (
        case,
        first_scope,
        second_scope,
        correspondence,
        profile,
        context,
        obligation_ref,
        obligation,
        target_definition,
        target_representation,
        binding_profile,
    )


def test_evaluator_uses_recomputed_step_scope_against_original_envelope(tmp_path: Path) -> None:
    (
        case,
        expected_scope,
        wrong_scope,
        correspondence,
        profile,
        context,
        obligation_ref,
        obligation,
        target_definition,
        target_representation,
        binding_profile,
    ) = _temporal_evaluation_inputs(tmp_path)
    try:
        result = evaluate_registered_derived_input_correspondence(
            correspondence=correspondence,
            profile=profile,
            context=context,
            obligation_ref=obligation_ref,
            obligation=obligation,
            target_definition=target_definition,
            target_representation=target_representation,
            binding_profile=binding_profile,
            units_registry=None,
            recipe=None,
            series=None,
            roles=(),
            expected_step_scope=expected_scope,
        )
        # The model-owned port spans two years; a valid temporal subject selects
        # the first year for this predicate. Missing registered role replay still
        # refuses the candidate before arithmetic can be considered.
        assert result.status == "refused"
        assert "exact_role_set_required" in result.refusal_codes
        assert "target_selection_mismatch" not in result.refusal_codes
        assert not any(code.startswith("temporal_step_scope_") for code in result.refusal_codes)

        mismatched = evaluate_registered_derived_input_correspondence(
            correspondence=correspondence,
            profile=profile,
            context=context,
            obligation_ref=obligation_ref,
            obligation=obligation,
            target_definition=target_definition,
            target_representation=target_representation,
            binding_profile=binding_profile,
            units_registry=None,
            recipe=None,
            series=None,
            roles=(),
            expected_step_scope=wrong_scope,
        )
        assert "temporal_step_scope_mismatch" in mismatched.refusal_codes
    finally:
        case.close()


def test_new_evaluator_requires_expected_scope_from_temporal_core(tmp_path: Path) -> None:
    store, _, args = _projection_inputs(tmp_path)
    from tests.unit.core.contracts.test_semantic_derived_binding import _case

    _, semantic = _case(tmp_path)
    context = args["context"]
    assert isinstance(context, RegisteredDerivedInputContext)
    step_scope = ModelInputStepScope(
        port_id=context.model_port_id,
        step=0,
        scope=context.output_scope,
    )
    temporal = _context_for_version(
        args, version="1.1", step_scope=step_scope, include_step_scope=True
    )
    temporal_ref = persist_registered_derived_input_context(store, temporal)
    correspondence = _correspondence_for(
        args,
        temporal,
        context_ref=temporal_ref,
        version="2.1",
        step_scope=step_scope,
        include_step_scope=True,
    )
    profile = args["profile"]
    assert isinstance(profile, RegisteredDerivedInputProfile)
    result = evaluate_registered_derived_input_correspondence(
        correspondence=correspondence,
        profile=profile,
        context=temporal,
        obligation_ref=semantic["obligation_ref"],
        obligation=semantic["obligation"],
        target_definition=semantic["target_definition"],
        target_representation=semantic["target_representation"],
        binding_profile=semantic["binding_profile"],
        units_registry=semantic["units_registry"],
        recipe=semantic["recipe"],
        series=semantic["series"],
        roles=(),
    )
    assert result.status == "refused"
    assert "temporal_step_scope_not_established" in result.refusal_codes
    assert "exact_role_set_required" in result.refusal_codes
