"""Candidate vector declarations replay without acquiring empirical authority."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.entity_axis import (
    EntityAxisValueIdentity,
    SelectedEntityVectorSourceDescriptor,
)
from polisyos.core.contracts.foundry import (
    FoundrySelectedMethodInput,
    FoundrySelectedMethodVectorInput,
    selected_method_input_tensor_identity,
)
from polisyos.core.contracts.model_input_period_steps import ModelInputStepScope
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedEntityVectorInput,
    ResolvedEntityVectorInputAtStep,
    ResolvedInputBindingManifest,
    ResolvedMeasurementInput,
)
from polisyos.core.contracts.variable_binding import (
    ENTITY_VECTOR_CANDIDATE_LIMITATIONS,
    EntityVectorCorrespondenceBasis,
    EntityVectorCorrespondenceBasisRef,
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrenceRef,
    SelectedEntityVectorSourceMeaning,
    SelectedEntityVectorSourceMeaningRef,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    entity_vector_correspondence_basis_manifest_inputs,
    evaluate_entity_vector_correspondence_basis,
    load_entity_vector_correspondence_basis,
    load_selected_entity_vector_source_meaning,
    selected_entity_vector_source_meaning_manifest_inputs,
)
from polisyos.ir.kernel import GenericUnit, MoneyUnit


def _ref(index: int, kind: str, ref_type=SelectedVariableBindingRef, *, media="application/json"):
    return ref_type(
        artifact_id=ArtifactID.from_sha256_hex(f"{index:064x}"),
        kind=kind,
        media_type=media,
        manifest_profile_sha256="sha256:" + f"{index + 100:064x}",
    )


def _scope(year: int) -> ModelInputScope:
    return ModelInputScope(
        population_ref="candidate:selected-members",
        geography_ref="candidate:geography",
        jurisdiction_ref="candidate:jurisdiction",
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        time_role="valid_time",
        period_basis="calendar_year",
    )


def _case() -> SimpleNamespace:
    definition_ref = _ref(1, "catalog.variable_semantic_definition", VariableSemanticDefinitionRef)
    source_representation_ref = _ref(
        2, "catalog.variable_representation", VariableRepresentationRef
    )
    target_representation_ref = _ref(
        3, "catalog.variable_representation", VariableRepresentationRef
    )
    profile_ref = _ref(4, "catalog.measurement_binding_profile", MeasurementBindingProfileRef)
    interface_ref = _ref(5, "runtime.quality.program_graph_input_interface")
    registry_ref = _ref(6, "core.registry_bundle")
    view_ref = _ref(7, "candidate.vector_source", ArtifactRef)
    axis_ref = _ref(8, "foundry.selected_entity_axis")
    meaning_ref = _ref(
        9, "catalog.selected_entity_vector_source_meaning", SelectedEntityVectorSourceMeaningRef
    )
    definition = VariableSemanticDefinition(
        namespace="candidate",
        stable_id="synthetic_amount",
        revision="1",
        meaning="Synthetic generic amounts for the explicitly selected candidate members.",
        definition_evidence_refs=(_ref(10, "candidate.definition_evidence"),),
    )
    source = VariableRepresentation(
        representation_id="candidate.source_amount",
        revision="1",
        semantic_definition_ref=definition_ref,
        quantity_kind="flow",
        measure_form="absolute",
        unit_id="amount",
        scale_to_unit=Decimal(1),
        time_support="period_total",
        temporal_granularity="annual",
        aggregation="identity",
        grain=("selected_entity_id",),
        population_ref="candidate:selected-members",
    )
    target = source.model_copy(update={"representation_id": "candidate.target_amount"})
    profile = MeasurementBindingProfile(
        profile_id="candidate.generic_amount",
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
    descriptor = SelectedEntityVectorSourceDescriptor(
        source_view_ref=view_ref,
        member_ids_pointer="/members",
        # This spelling is deliberately unrelated to the declared period.
        values_pointer="/arrays/first",
    )
    meaning = SelectedEntityVectorSourceMeaning(
        source_descriptor=descriptor,
        source_definition_ref=definition_ref,
        source_representation_ref=source_representation_ref,
        source_registry_bundle_ref=registry_ref,
        source_scope=_scope(2020),
    )
    basis = EntityVectorCorrespondenceBasis(
        source_meaning_ref=meaning_ref,
        model_interface_ref=interface_ref,
        model_port_id="candidate.amounts",
        target_definition_ref=definition_ref,
        target_representation_ref=target_representation_ref,
        binding_profile_ref=profile_ref,
        scope=_scope(2020),
    )
    port = ModelInputPort(
        port_id="candidate.amounts",
        slot_id="candidate.amounts",
        carrier="method_input",
        unit_id="amount",
        purpose="simulation_input",
        semantic_definition_ref=definition_ref,
        representation_ref=target_representation_ref,
        binding_profile_ref=profile_ref,
        scope=_scope(2020).model_copy(update={"period_end": date(2021, 12, 31)}),
        entity_axis_ref=axis_ref,
        physical_encoding=ModelInputPhysicalEncoding(
            shape=(4,), dtype="float64", max_absolute_error=Decimal(0)
        ),
    )
    return SimpleNamespace(
        args={
            "basis": basis,
            "source_meaning_ref": meaning_ref,
            "source_meaning": meaning,
            "source_definition_ref": definition_ref,
            "source_definition": definition,
            "source_representation_ref": source_representation_ref,
            "source_representation": source,
            "source_registry_bundle_ref": registry_ref,
            "source_unit": GenericUnit(label="amount"),
            "target_unit": GenericUnit(label="amount"),
            "target_definition_ref": definition_ref,
            "target_definition": definition,
            "target_representation_ref": target_representation_ref,
            "target_representation": target,
            "binding_profile_ref": profile_ref,
            "profile": profile,
            "model_interface_ref": interface_ref,
            "model_port": port,
            "expected_scope": _scope(2020),
        },
        descriptor=descriptor,
        meaning=meaning,
        meaning_ref=meaning_ref,
        basis=basis,
        port=port,
        axis_ref=axis_ref,
        interface_ref=interface_ref,
    )


def test_vector_comparison_preserves_asserted_scope_and_meaning() -> None:
    case = _case()
    result = evaluate_entity_vector_correspondence_basis(**case.args)
    assert result.status == "candidate"
    assert result.semantic_correspondence == "recomputed"
    assert result.limitation_codes == ENTITY_VECTOR_CANDIDATE_LIMITATIONS
    assert case.meaning.source_scope_provenance == "consumer_asserted"
    assert case.meaning.source_meaning_provenance == "consumer_asserted"
    assert case.meaning.empirical_correctness == "not_established"
    assert case.meaning.source_currentness == "not_established"
    assert case.meaning.source_descriptor.values_pointer == "/arrays/first"


@pytest.mark.parametrize(
    ("mutation", "refusal"),
    [
        ("year", "entity_vector_source_or_model_scope_mismatch"),
        ("time_role", "entity_vector_source_or_model_scope_mismatch"),
        ("population", "entity_vector_source_or_model_scope_mismatch"),
        ("unit", "entity_vector_generic_amount_unit_required"),
        ("label", "entity_vector_generic_amount_unit_required"),
        ("meaning_revision", "same_definition_profile_requires_exact_definition"),
        ("meaning_ref", "entity_vector_basis_selected_ref_mismatch"),
        ("required_axis", "required_axis_unknown:time_support"),
        ("limitations", "entity_vector_candidate_declaration_invalid"),
    ],
)
def test_same_numeric_vector_cannot_hide_semantic_grafts(mutation: str, refusal: str) -> None:
    case = _case()
    args = case.args.copy()
    if mutation in {"year", "time_role", "population"}:
        scope = _scope(2021) if mutation == "year" else _scope(2020)
        if mutation == "time_role":
            scope = scope.model_copy(update={"time_role": "observation_time"})
        elif mutation == "population":
            scope = scope.model_copy(update={"population_ref": "foreign:population"})
        args["source_meaning"] = case.meaning.model_copy(update={"source_scope": scope})
    elif mutation == "unit":
        args["source_unit"] = MoneyUnit(currency="USD", nominal_year=2020)
    elif mutation == "label":
        args["source_unit"] = GenericUnit(label="other_amount")
    elif mutation == "meaning_revision":
        args["source_definition"] = args["source_definition"].model_copy(update={"revision": "2"})
    elif mutation == "meaning_ref":
        args["source_meaning_ref"] = _ref(
            29,
            "catalog.selected_entity_vector_source_meaning",
            SelectedEntityVectorSourceMeaningRef,
        )
    elif mutation == "required_axis":
        args["source_representation"] = args["source_representation"].model_copy(
            update={"time_support": None}
        )
    else:
        args["source_meaning"] = case.meaning.model_copy(update={"limitation_codes": ()})
    result = evaluate_entity_vector_correspondence_basis(**args)
    assert result.status == "refused"
    assert result.semantic_correspondence == "not_established"
    assert refusal in result.refusal_codes
    assert result.limitation_codes == ENTITY_VECTOR_CANDIDATE_LIMITATIONS


@pytest.mark.parametrize(
    "subject",
    [
        "source_meaning_ref",
        "model_interface_ref",
        "binding_profile_ref",
        "source_representation_ref",
        "target_representation_ref",
        "model_port",
    ],
)
def test_equal_artifact_ids_do_not_hide_selected_profile_or_port_grafts(subject: str) -> None:
    case = _case()
    args = case.args.copy()
    if subject == "model_port":
        args[subject] = case.port.model_copy(update={"port_id": "foreign.port"})
        refusal = "entity_vector_model_port_mismatch"
    else:
        original = args[subject]
        args[subject] = original.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
        assert args[subject].artifact_id == original.artifact_id
        assert args[subject].kind == original.kind
        assert args[subject].media_type == original.media_type
        refusal = "entity_vector_basis_selected_ref_mismatch"
    result = evaluate_entity_vector_correspondence_basis(**args)
    assert result.status == "refused"
    assert refusal in result.refusal_codes
    assert result.limitation_codes == ENTITY_VECTOR_CANDIDATE_LIMITATIONS


@pytest.mark.parametrize(
    ("source_scale", "target_scale"),
    [
        (Decimal(2), Decimal(2)),
        (Decimal(2), Decimal(1)),
        (Decimal(1), Decimal(2)),
        (None, Decimal(1)),
        (Decimal(1), None),
        (None, None),
    ],
)
def test_direct_vector_profile_refuses_nonidentity_or_unknown_scales(
    source_scale: Decimal | None, target_scale: Decimal | None
) -> None:
    case = _case()
    args = case.args.copy()
    args["source_representation"] = args["source_representation"].model_copy(
        update={"scale_to_unit": source_scale}
    )
    args["target_representation"] = args["target_representation"].model_copy(
        update={"scale_to_unit": target_scale}
    )
    # Direct vector transport has no conversion operator. Its identity scale
    # requirement must hold even when a selected axis policy omits scale.
    args["profile"] = args["profile"].model_copy(
        update={
            "required_axes": tuple(
                axis
                for axis in args["profile"].required_axes
                if axis is not MeasurementAxis.SCALE_TO_UNIT
            )
        }
    )
    result = evaluate_entity_vector_correspondence_basis(**args)
    assert result.status == "refused"
    assert "entity_vector_identity_scale_required" in result.refusal_codes
    assert result.limitation_codes == ENTITY_VECTOR_CANDIDATE_LIMITATIONS


def test_direct_vector_identity_scale_allows_a_profile_without_scale_axis() -> None:
    case = _case()
    args = case.args.copy()
    args["profile"] = args["profile"].model_copy(
        update={
            "required_axes": tuple(
                axis
                for axis in args["profile"].required_axes
                if axis is not MeasurementAxis.SCALE_TO_UNIT
            )
        }
    )
    result = evaluate_entity_vector_correspondence_basis(**args)
    assert result.status == "candidate"
    assert result.limitation_codes == ENTITY_VECTOR_CANDIDATE_LIMITATIONS


def _persist(store: FileSystemCAS, value, ref_type, inputs):
    ref = store.put_json(
        value,
        PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=value.ARTIFACT_SCHEMA_NAME, version="1.0"),
            inputs=list(inputs),
        ),
        return_selected_profile=True,
    )
    return ref_type.model_validate(ref.model_dump(mode="python"))


def _declared_edges(value):
    """State the selected edge contract independently of the production helper."""
    if type(value) is SelectedEntityVectorSourceMeaning:
        subjects = (
            (value.source_descriptor.source_view_ref, "selected_source_view"),
            (value.source_definition_ref, "source_definition"),
            (value.source_representation_ref, "source_representation"),
            (value.source_registry_bundle_ref, "source_registry_bundle"),
        )
    else:
        subjects = (
            (value.source_meaning_ref, "selected_source_meaning"),
            (value.model_interface_ref, "selected_model_interface"),
            (value.target_definition_ref, "model_port_definition"),
            (value.target_representation_ref, "model_port_representation"),
            (value.binding_profile_ref, "selected_binding_profile"),
        )
    return tuple(input_ref_from_artifact_ref(ref, role=role) for ref, role in subjects)


@pytest.mark.parametrize("subject", ["meaning", "basis"])
def test_cold_core_reader_requires_complete_source_relation_lineage(
    tmp_path: Path, subject: str
) -> None:
    case = _case()
    store = FileSystemCAS(tmp_path / "cas")
    if subject == "meaning":
        value = case.meaning
        ref_type = SelectedEntityVectorSourceMeaningRef
        edges = _declared_edges(value)
        assert selected_entity_vector_source_meaning_manifest_inputs(value) == edges
        loader = load_selected_entity_vector_source_meaning
        expected = "entity_vector_source_meaning_lineage_mismatch"
    else:
        value = case.basis
        ref_type = EntityVectorCorrespondenceBasisRef
        edges = _declared_edges(value)
        assert entity_vector_correspondence_basis_manifest_inputs(value) == edges
        loader = load_entity_vector_correspondence_basis
        expected = "entity_vector_correspondence_lineage_mismatch"
    selected = _persist(store, value, ref_type, edges)
    fresh = FileSystemCAS.open_existing_read_only(store.root)
    assert loader(fresh, selected) == value
    # Rehash the same declaration body with one selected dependency removed.
    # Correct bytes and schema must not conceal a missing source relation.
    incomplete = _persist(store, value, ref_type, edges[:-1])
    with pytest.raises(ValueError, match=f"^{expected}$"):
        loader(FileSystemCAS.open_existing_read_only(store.root), incomplete)


@pytest.mark.parametrize("subject", ["meaning", "basis"])
@pytest.mark.parametrize("mutation", ["wrong_role", "foreign_artifact", "foreign_profile"])
def test_cold_core_reader_refuses_wrong_role_or_substituted_selected_edge(
    tmp_path: Path, subject: str, mutation: str
) -> None:
    case = _case()
    store = FileSystemCAS(tmp_path / "cas")
    if subject == "meaning":
        value, ref_type = case.meaning, SelectedEntityVectorSourceMeaningRef
        loader = load_selected_entity_vector_source_meaning
        expected = "entity_vector_source_meaning_lineage_mismatch"
    else:
        value, ref_type = case.basis, EntityVectorCorrespondenceBasisRef
        loader = load_entity_vector_correspondence_basis
        expected = "entity_vector_correspondence_lineage_mismatch"
    # These roles and subjects come from the literal contract above, rather
    # than the implementation used by the deciding reader.
    edges = list(_declared_edges(value))
    original = edges[0]
    if mutation == "wrong_role":
        edges[0] = original.model_copy(update={"role": "foreign_source_role"})
    elif mutation == "foreign_artifact":
        edges[0] = original.model_copy(update={"artifact_id": ArtifactID.from_sha256_hex("e" * 64)})
    else:
        edges[0] = original.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
        assert edges[0].artifact_id == original.artifact_id
        assert edges[0].role == original.role
    selected = _persist(store, value, ref_type, edges)
    with pytest.raises(ValueError, match=f"^{expected}$"):
        loader(FileSystemCAS.open_existing_read_only(store.root), selected)


@pytest.mark.parametrize(
    "update",
    [
        {"source_layout": "world_bank_schema.v1"},
        {"source_meaning_provenance": "recomputed"},
        {"source_scope_provenance": "recomputed"},
        {"empirical_correctness": "recomputed"},
        {"limitation_codes": ()},
    ],
)
def test_declaration_cannot_claim_decoder_or_empirical_authority(update: dict) -> None:
    raw = _case().meaning.model_dump(mode="python") | update
    with pytest.raises(ValidationError):
        SelectedEntityVectorSourceMeaning.model_validate(raw)


def _vector_row(case: SimpleNamespace, *, step: int = 0) -> ResolvedEntityVectorInputAtStep:
    return ResolvedEntityVectorInputAtStep(
        step_scope=ModelInputStepScope(
            port_id=case.port.port_id, step=step, scope=_scope(2020 + step)
        ),
        selection=ResolvedEntityVectorInput(
            binding_id=f"vector_{step}",
            model_input_obligation_ref=_ref(31, "runtime.quality.model_input_obligation"),
            model_interface_ref=case.interface_ref,
            model_port_id=case.port.port_id,
            entity_axis_ref=case.axis_ref,
            source_descriptor=case.descriptor,
            source_meaning_ref=case.meaning_ref,
            correspondence_ref=_ref(
                32 + step,
                "catalog.entity_vector_correspondence_basis",
                EntityVectorCorrespondenceBasisRef,
            ),
        ),
    )


def test_vector_manifest_selects_direct_source_with_canonical_step_inventory() -> None:
    case = _case()
    rows = (_vector_row(case), _vector_row(case, step=1))
    manifest = ResolvedInputBindingManifest(
        schema_version="4.0",
        data_snapshot_ref=_ref(41, "fabric.data_snapshot"),
        model_input_obligation_set_ref=_ref(42, "runtime.quality.model_input_obligation_set"),
        entity_vector_steps=rows,
    )
    raw = manifest.model_dump(mode="json")
    assert not {"measurements", "derivations", "method_input_steps"}.intersection(raw)
    assert [edge.role for edge in manifest.lineage_inputs()][2:8] == [
        "binding.vector_0.obligation",
        "binding.vector_0.interface",
        "binding.vector_0.axis",
        "binding.vector_0.source_view",
        "binding.vector_0.source_meaning",
        "binding.vector_0.correspondence",
    ]
    with pytest.raises(ValidationError, match="vector_step_inventory_invalid"):
        ResolvedInputBindingManifest.model_validate(
            manifest.model_dump(mode="python") | {"entity_vector_steps": rows[::-1]}
        )
    with pytest.raises(ValidationError, match="v4_requires_vectors_only"):
        ResolvedInputBindingManifest.model_validate(
            manifest.model_dump(mode="python") | {"measurements": ()}
        )
    with pytest.raises(ValidationError, match="vector_inputs_version_mismatch"):
        ResolvedInputBindingManifest.model_validate(
            manifest.model_dump(mode="python") | {"schema_version": "2.0", "derivations": ()}
        )


def test_legacy_measurement_manifest_bytes_do_not_gain_vector_fields() -> None:
    measurement = ResolvedMeasurementInput(
        binding_id="legacy",
        model_input_obligation_ref=_ref(51, "runtime.quality.model_input_obligation"),
        selected_occurrence_ref=_ref(
            52, "catalog.scoped_measurement_occurrence", ScopedMeasurementOccurrenceRef
        ),
        correspondence_ref=_ref(
            53, "catalog.scoped_correspondence_basis", ScopedCorrespondenceBasisRef
        ),
        source_path="observed.value",
    )
    original = {
        "schema_version": "1.0",
        "authority_purpose": "candidate_simulation_input_only",
        "data_snapshot_ref": _ref(54, "fabric.data_snapshot").model_dump(mode="json"),
        "model_input_obligation_set_ref": _ref(
            55, "runtime.quality.model_input_obligation_set"
        ).model_dump(mode="json"),
        "measurements": [measurement.model_dump(mode="json")],
        "retained_binding_ids": [],
    }
    legacy = ResolvedInputBindingManifest.model_validate_json(json.dumps(original))
    assert legacy.model_dump(mode="json") == original


@pytest.mark.parametrize("version", ["2.0", "3.0"])
def test_legacy_derived_manifest_wire_rejects_vector_fields(version: str) -> None:
    """Replay existing wire 2/3 fields without a numerical preflight fixture."""
    selected = {
        "binding_id": "legacy_derived",
        "model_input_obligation_ref": _ref(81, "runtime.quality.model_input_obligation").model_dump(
            mode="json"
        ),
        "model_interface_ref": _ref(82, "runtime.quality.program_graph_input_interface").model_dump(
            mode="json"
        ),
        "model_port_id": "candidate.amounts",
        "recipe_ref": _ref(83, "polisyos.runtime.derivation_recipe").model_dump(mode="json"),
        "certificate_ref": _ref(84, "polisyos.runtime.derivation_certificate").model_dump(
            mode="json"
        ),
        "output_ref": _ref(85, "polisyos.runtime.derived_economic_series").model_dump(mode="json"),
        "year": 2020,
        "correspondence_ref": _ref(86, "catalog.derived_input_correspondence").model_dump(
            mode="json"
        ),
        "profile_ref": _ref(87, "catalog.derived_input_profile").model_dump(mode="json"),
        "source_path": "derived_inputs.legacy.value",
    }
    original = {
        "schema_version": version,
        "authority_purpose": "candidate_simulation_input_only",
        "data_snapshot_ref": _ref(88, "fabric.data_snapshot").model_dump(mode="json"),
        "model_input_obligation_set_ref": _ref(
            89, "runtime.quality.model_input_obligation_set"
        ).model_dump(mode="json"),
        "retained_binding_ids": [],
    }
    if version == "2.0":
        original["derivations"] = [selected]
    else:
        original["method_input_steps"] = [
            {
                "step_scope": {
                    "port_id": "candidate.amounts",
                    "step": 0,
                    "scope": _scope(2020).model_dump(mode="json"),
                },
                "selection": selected,
            }
        ]
    loaded = ResolvedInputBindingManifest.model_validate_json(json.dumps(original))
    assert loaded.model_dump(mode="json") == original
    expected = original
    if version == "3.0":
        # The existing canonical profile retains typed dates. A JSON-mode
        # string is not that canonical input, even though it has the same wire
        # spelling after the owner's strict JSON decoder reifies the scope.
        expected = original | {
            "method_input_steps": [
                {
                    "step_scope": {
                        "port_id": "candidate.amounts",
                        "step": 0,
                        "scope": {
                            "population_ref": "candidate:selected-members",
                            "geography_ref": "candidate:geography",
                            "jurisdiction_ref": "candidate:jurisdiction",
                            "period_start": date(2020, 1, 1),
                            "period_end": date(2020, 12, 31),
                            "time_role": "valid_time",
                            "period_basis": "calendar_year",
                        },
                    },
                    "selection": selected,
                }
            ]
        }
    assert to_canonical_bytes(loaded) == to_canonical_bytes(expected)
    assert "entity_vector_steps" not in loaded.model_dump(mode="json")
    with pytest.raises(ValidationError, match="vector_inputs_version_mismatch"):
        ResolvedInputBindingManifest.model_validate_json(
            json.dumps(original | {"entity_vector_steps": []})
        )


def test_record_identity_uses_tensor_digest_without_alignment_digest_alias() -> None:
    case = _case()
    npy = _ref(61, "foundry.selected_method_input_value", media="application/x-npy")
    obligation = _ref(62, "runtime.quality.model_input_obligation")
    scalar = FoundrySelectedMethodInput(
        model_input_obligation_ref=obligation,
        binding_id="scalar",
        port_id="scalar",
        slot_id="scalar",
        canonical_value=Decimal(3),
        dtype="float64",
        shape=(),
        npy_value_ref=npy,
        value_sha256="a" * 64,
    )
    identity = EntityAxisValueIdentity(
        axis_sha256="sha256:" + "b" * 64,
        unit_id="amount",
        dtype="float64",
        shape=(4,),
        input_order_sha256="sha256:" + "c" * 64,
        value_sha256="sha256:" + "d" * 64,
        aligned_value_sha256="sha256:" + "e" * 64,
        alignment_sha256="sha256:" + "f" * 64,
    )
    vector = FoundrySelectedMethodVectorInput(
        model_input_obligation_ref=obligation,
        binding_id="vector",
        port_id=case.port.port_id,
        slot_id=case.port.slot_id,
        npy_value_ref=npy,
        entity_axis_ref=case.axis_ref,
        source_descriptor=case.descriptor,
        alignment_identity=identity,
        tensor_value_sha256="9" * 64,
    )
    assert selected_method_input_tensor_identity(scalar) == ("a" * 64, (), "float64")
    assert selected_method_input_tensor_identity(vector) == ("9" * 64, (4,), "float64")
    with pytest.raises(ValueError, match="record_type_unsupported"):
        selected_method_input_tensor_identity(SimpleNamespace(value_sha256="9" * 64))
