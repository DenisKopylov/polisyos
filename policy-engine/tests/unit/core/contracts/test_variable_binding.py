"""Semantic variable bindings are strict, bounded, and replayable."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactIntegrityError
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
)
from polisyos.core.contracts.variable_binding import (
    FixedUnitTransformWitness,
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    ScopedCorrespondenceBasis,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    ScopedSourceSelection,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    evaluate_scoped_correspondence_basis,
    load_variable_representation,
    replay_scoped_measurement_occurrence,
    scoped_source_selection_from_passport_mapping,
    variable_representation_manifest_inputs,
)
from polisyos.data_forge.domains.catalog.knowledge import overlay

_HARD_AXES = (
    MeasurementAxis.QUANTITY_KIND,
    MeasurementAxis.MEASURE_FORM,
    MeasurementAxis.UNIT_ID,
    MeasurementAxis.TIME_SUPPORT,
)


def _ref(ref_type, *, token: int, kind: str):
    return ref_type(
        artifact_id=ArtifactID.from_sha256_hex(f"{token:064x}"),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + f"{token + 100:064x}",
    )


def _correspondence_case(
    *,
    quantity_kind: str = "stock",
    measure_form: str = "absolute",
    target_quantity_kind: str | None = None,
    source_numerator: VariableSemanticDefinitionRef | None = None,
    target_numerator: VariableSemanticDefinitionRef | None = None,
    source_denominator: VariableSemanticDefinitionRef | None = None,
    target_denominator: VariableSemanticDefinitionRef | None = None,
    require_ratio_axes: bool = True,
):
    definition_ref = _ref(
        VariableSemanticDefinitionRef,
        token=1,
        kind=VariableSemanticDefinition.ARTIFACT_KIND,
    )
    evidence_ref = _ref(SelectedVariableBindingRef, token=2, kind="test.definition_evidence")
    representation_ref = _ref(
        VariableRepresentationRef,
        token=3,
        kind=VariableRepresentation.ARTIFACT_KIND,
    )
    target_representation_ref = _ref(
        VariableRepresentationRef,
        token=4,
        kind=VariableRepresentation.ARTIFACT_KIND,
    )
    profile_ref = _ref(
        MeasurementBindingProfileRef,
        token=5,
        kind=MeasurementBindingProfile.ARTIFACT_KIND,
    )
    model_interface_ref = _ref(
        SelectedVariableBindingRef,
        token=6,
        kind="runtime.quality.program_graph_input_interface",
    )
    receipt_ref = _ref(
        SelectedVariableBindingRef,
        token=7,
        kind="epoch.activated_overlay_admission_receipt",
    )
    passport_ref = _ref(
        SelectedVariableBindingRef,
        token=8,
        kind="epoch.acquisition_passport_snapshot",
    )
    boundary_ref = _ref(
        SelectedVariableBindingRef,
        token=9,
        kind="epoch.acquisition_semantic_boundary_candidate",
    )
    record_ref = _ref(SelectedVariableBindingRef, token=10, kind="test.source_record")
    occurrence_ref = _ref(
        ScopedMeasurementOccurrenceRef,
        token=11,
        kind=ScopedMeasurementOccurrence.ARTIFACT_KIND,
    )

    definition = VariableSemanticDefinition(
        namespace="test",
        stable_id="measurement",
        revision="1",
        meaning="A measured scalar used by the selected model port.",
        definition_evidence_refs=(evidence_ref,),
    )
    quantity = target_quantity_kind or quantity_kind
    source_representation = VariableRepresentation(
        representation_id="test.source",
        revision="1",
        semantic_definition_ref=definition_ref,
        quantity_kind=quantity_kind,
        measure_form=measure_form,
        unit_id="usd",
        numerator_ref=source_numerator,
        denominator_ref=source_denominator,
        time_support="state_start",
        temporal_granularity="annual",
        aggregation="identity",
        grain=("geography", "period"),
    )
    target_representation = VariableRepresentation(
        representation_id="test.target",
        revision="1",
        semantic_definition_ref=definition_ref,
        quantity_kind=quantity,
        measure_form=measure_form,
        unit_id="usd",
        numerator_ref=target_numerator,
        denominator_ref=target_denominator,
        time_support="state_start",
        temporal_granularity="annual",
        aggregation="identity",
        grain=("geography", "period"),
    )
    required_axes = list(_HARD_AXES)
    if require_ratio_axes and measure_form in {"ratio", "rate"}:
        required_axes.extend((MeasurementAxis.NUMERATOR_REF, MeasurementAxis.DENOMINATOR_REF))
    profile = MeasurementBindingProfile(
        profile_id="test.strict",
        revision="1",
        required_axes=tuple(required_axes),
        optional_axes=(MeasurementAxis.POPULATION_REF,),
    )
    scope = ModelInputScope(
        population_ref="population:test",
        geography_ref="geography:usa",
        jurisdiction_ref="jurisdiction:usa",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        time_role="observation_time",
        period_basis="calendar_year",
    )
    selection = ScopedSourceSelection(
        source_receipt_ref=receipt_ref,
        source_passport_ref=passport_ref,
        source_boundary_candidate_ref=boundary_ref,
        source_record_ref=record_ref,
        epoch_id=1,
        passport_id="passport:test:1",
        dataset_id="test.dataset",
        dataset_version="2024-01",
        source_watermark="sha256:" + "a" * 64,
        observation_class="observed",
        raw_field="value",
        canonical_variable="test.measurement",
        raw_unit="usd",
        canonical_unit="usd",
        unit_transform="identity",
        unit_transform_ref=None,
        binding_id="field-binding:sha256:" + "b" * 64,
        aggregation_method="identity",
        is_proxy=False,
    )
    occurrence = ScopedMeasurementOccurrence(
        source_scope=scope,
        source_receipt_ref=receipt_ref,
        source_passport_ref=passport_ref,
        source_boundary_candidate_ref=boundary_ref,
        source_record_ref=record_ref,
        observation_id="acquisition-observation:test",
        observation_content_sha256="sha256:" + "c" * 64,
        dataset_id="test.dataset",
        dataset_version="2024-01",
        source_watermark=selection.source_watermark,
        raw_variable="value",
        canonical_variable="test.measurement",
        country_code="USA",
        year=2024,
        observation_class="observed",
        condition_json=json.dumps(
            {
                "unit": "usd",
                "population_ref": "population:test",
                "jurisdiction_ref": "jurisdiction:usa",
                "time_period_basis": "calendar_year",
            },
            sort_keys=True,
        ),
        acquisition_method="registered_identity_identity_lift",
        raw_values=("5",),
        aggregation_method="identity",
        canonical_value="5",
        canonical_unit="usd",
    )
    basis = ScopedCorrespondenceBasis(
        occurrence_ref=occurrence_ref,
        source_definition_ref=definition_ref,
        source_representation_ref=representation_ref,
        source_definition_evidence_refs=(evidence_ref,),
        model_interface_ref=model_interface_ref,
        model_port_id="port:test.measurement",
        target_definition_ref=definition_ref,
        target_representation_ref=target_representation_ref,
        binding_profile_ref=profile_ref,
        scope=scope,
    )
    port = ModelInputPort(
        port_id="port:test.measurement",
        slot_id="slot:test.measurement",
        state_path="state.measurement",
        unit_id="usd",
        purpose="initial_state",
        semantic_definition_ref=definition_ref,
        representation_ref=target_representation_ref,
        binding_profile_ref=profile_ref,
        scope=scope,
        physical_encoding=ModelInputPhysicalEncoding(
            shape=(1,), dtype="float64", max_absolute_error=Decimal("0")
        ),
    )
    return SimpleNamespace(
        definition_ref=definition_ref,
        definition=definition,
        evidence_ref=evidence_ref,
        representation_ref=representation_ref,
        representation=source_representation,
        target_representation_ref=target_representation_ref,
        target_representation=target_representation,
        profile_ref=profile_ref,
        profile=profile,
        model_interface_ref=model_interface_ref,
        receipt_ref=receipt_ref,
        passport_ref=passport_ref,
        boundary_ref=boundary_ref,
        record_ref=record_ref,
        occurrence_ref=occurrence_ref,
        occurrence=occurrence,
        selection=selection,
        basis=basis,
        port=port,
    )


def _evaluate(case):
    return evaluate_scoped_correspondence_basis(
        basis=case.basis,
        occurrence_ref=case.occurrence_ref,
        occurrence=case.occurrence,
        replayed_occurrence=case.occurrence,
        source_selection=case.selection,
        source_definition_ref=case.definition_ref,
        source_definition=case.definition,
        source_representation_ref=case.representation_ref,
        source_representation=case.representation,
        target_definition_ref=case.definition_ref,
        target_definition=case.definition,
        target_representation_ref=case.target_representation_ref,
        target_representation=case.target_representation,
        binding_profile_ref=case.profile_ref,
        profile=case.profile,
        model_interface_ref=case.model_interface_ref,
        model_port=case.port,
    )


def _raw_percent_observation_case(
    *,
    condition: dict[str, object],
    coordinates: dict[str, object] | None = None,
    raw_field: str = "rate_pct",
    raw_value: int = 20,
    raw_unit: str = "percent",
    canonical_unit: str = "ratio",
    unit_transform: str = "fixed_multiplicative",
    valid_max: float = 1.0,
):
    row = {
        raw_field: raw_value,
        "country_code": "USA",
        "year": 2024,
        "condition_json": condition,
    }
    if coordinates:
        row.update(coordinates)
    raw_body = json.dumps([row], separators=(",", ":")).encode()
    source_watermark = "sha256:" + hashlib.sha256(raw_body).hexdigest()
    binding = overlay.build_metric_field_binding(
        dataset_id="test.workforce",
        distribution_id="test.workforce.json",
        raw_field=raw_field,
        canonical_variable="test.unemployment_rate",
        raw_unit=raw_unit,
        canonical_unit=canonical_unit,
        unit_transform=unit_transform,
        unit_transform_ref=(
            "fabric://units/fixed-multiplicative/v1"
            if unit_transform == "fixed_multiplicative"
            else "fabric://units/usd-identity/v1"
        ),
        alignment_method="semantic",
        alignment_confidence=0.9,
        is_proxy=False,
        proxy_penalty=0.0,
        evidence_refs=("repo://test/workforce-definition",),
        valid_min=0.0,
        valid_max=valid_max,
    )
    (owner_row,) = overlay.derive_canonical_observations(
        raw_body,
        passport=SimpleNamespace(
            epoch_id=1,
            source_watermark=source_watermark,
            dataset_version="2024-01",
            observation_class=overlay.ObservationProvenanceClass.OBSERVED,
        ),
        registration=SimpleNamespace(catalog_dataset_id="test.workforce", field_binding=binding),
    )
    selection = ScopedSourceSelection(
        source_receipt_ref=_ref(
            SelectedVariableBindingRef,
            token=30,
            kind="epoch.activated_overlay_admission_receipt",
        ),
        source_passport_ref=_ref(
            SelectedVariableBindingRef,
            token=31,
            kind="epoch.acquisition_passport_snapshot",
        ),
        source_boundary_candidate_ref=_ref(
            SelectedVariableBindingRef,
            token=32,
            kind="epoch.acquisition_semantic_boundary_candidate",
        ),
        source_record_ref=_ref(SelectedVariableBindingRef, token=33, kind="test.raw"),
        epoch_id=1,
        passport_id="passport:workforce:1",
        dataset_id="test.workforce",
        dataset_version="2024-01",
        source_watermark=source_watermark,
        observation_class="observed",
        raw_field=raw_field,
        canonical_variable="test.unemployment_rate",
        raw_unit=raw_unit,
        canonical_unit=canonical_unit,
        unit_transform=unit_transform,
        unit_transform_ref=(
            "fabric://units/fixed-multiplicative/v1"
            if unit_transform == "fixed_multiplicative"
            else "fabric://units/usd-identity/v1"
        ),
        binding_id=binding.binding_id,
        aggregation_method="identity",
        is_proxy=False,
    )
    witness = (
        None
        if owner_row.unit_transform_evidence is None
        else FixedUnitTransformWitness.model_validate(
            owner_row.unit_transform_evidence.model_dump(mode="json")
        )
    )
    return raw_body, owner_row, selection, witness


def test_same_definition_recomputes_only_a_candidate_and_preserves_unknown_origin() -> None:
    result = _evaluate(_correspondence_case())

    assert result.status == "candidate"
    assert result.semantic_correspondence == "recomputed"
    assert result.optional_unknown_axes == (MeasurementAxis.POPULATION_REF,)
    assert "external_empirical_origin_not_established" in result.limitation_codes
    assert "source_currentness_not_established" in result.limitation_codes


def _methodology_document(
    store: FileSystemCAS,
    body: bytes = b"Test-owned measurement protocol r1; external validity is not established.\n",
) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef.model_validate(
        store.put_bytes(
            body,
            PutOptions(
                kind="fabric.doc.raw",
                media_type="text/plain",
                schema=SchemaInfo(name="fabric.doc.raw", version="1.0"),
            ),
            return_selected_profile=True,
        ).model_dump()
    )


def _stored_representation(store: FileSystemCAS) -> VariableRepresentation:
    case = _correspondence_case()
    evidence = store.put_bytes(
        b"Test-owned scalar definition; external empirical meaning is not established.\n",
        PutOptions(kind="test.definition_evidence", media_type="text/plain"),
        return_selected_profile=True,
    )
    definition = case.definition.model_copy(
        update={
            "definition_evidence_refs": (
                SelectedVariableBindingRef.model_validate(evidence.model_dump()),
            )
        }
    )
    definition_ref = store.put_json(
        definition,
        PutOptions(
            kind=definition.ARTIFACT_KIND,
            media_type=definition.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=definition.ARTIFACT_SCHEMA_NAME, version="1.0"),
            inputs=[input_ref_from_artifact_ref(evidence, role="definition_evidence")],
        ),
        return_selected_profile=True,
    )
    return case.representation.model_copy(
        update={
            "semantic_definition_ref": VariableSemanticDefinitionRef.model_validate(
                definition_ref.model_dump()
            )
        }
    )


def _persist_representation(
    store: FileSystemCAS,
    value: VariableRepresentation,
    *,
    manifest_version: str,
    include_inputs: bool = True,
) -> VariableRepresentationRef:
    return VariableRepresentationRef.model_validate(
        store.put_json(
            value,
            PutOptions(
                kind=value.ARTIFACT_KIND,
                media_type=value.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=value.ARTIFACT_SCHEMA_NAME, version=manifest_version),
                inputs=(
                    list(variable_representation_manifest_inputs(value)) if include_inputs else []
                ),
            ),
            return_selected_profile=True,
        ).model_dump()
    )


def test_v1_representation_preserves_its_exact_legacy_field_set_and_selected_read(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    representation = _correspondence_case().representation
    legacy_payload = {
        "schema_version": "polisyos.catalog.variable_representation.v1",
        "representation_id": "test.source",
        "revision": "1",
        "semantic_definition_ref": representation.semantic_definition_ref.model_dump(mode="json"),
        "quantity_kind": "stock",
        "measure_form": "absolute",
        "unit_id": "usd",
        "scale_to_unit": None,
        "numerator_ref": None,
        "denominator_ref": None,
        "time_support": "state_start",
        "temporal_granularity": "annual",
        "aggregation": "identity",
        "grain": ["geography", "period"],
        "population_ref": None,
    }
    legacy_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            {key: value for key, value in legacy_payload.items() if value is not None},
            PutOptions(
                kind=representation.ARTIFACT_KIND,
                media_type=representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=representation.ARTIFACT_SCHEMA_NAME, version="1.0"),
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    current_ref = _persist_representation(
        store, representation, manifest_version="1.0", include_inputs=False
    )

    assert representation.model_dump(mode="json") == legacy_payload
    assert current_ref == legacy_ref
    assert store.get_bytes(current_ref) == store.get_bytes(legacy_ref)
    assert load_variable_representation(store, legacy_ref) == representation


@pytest.mark.parametrize("present_value", [None, "document"])
def test_v1_representation_rejects_a_present_methodology_field(
    tmp_path: Path,
    present_value: str | None,
) -> None:
    payload = _correspondence_case().representation.model_dump()
    payload["methodology_ref"] = (
        _methodology_document(FileSystemCAS(tmp_path / "cas"))
        if present_value is not None
        else None
    )

    with pytest.raises(ValueError, match="variable_representation_methodology_requires_v2"):
        VariableRepresentation.model_validate(payload)


def test_methodology_axis_requires_an_explicit_v2_binding_profile() -> None:
    case = _correspondence_case()
    payload = case.profile.model_dump()
    payload["optional_axes"] = (MeasurementAxis.METHODOLOGY_REF,)

    with pytest.raises(ValueError, match="measurement_binding_profile_methodology_requires_v2"):
        MeasurementBindingProfile.model_validate(payload)
    payload["schema_version"] = "polisyos.catalog.measurement_binding_profile.v2"
    profile = MeasurementBindingProfile.model_validate(payload)
    assert profile.optional_axes == (MeasurementAxis.METHODOLOGY_REF,)


@pytest.mark.parametrize(("payload_version", "manifest_version"), [("v1", "2.0"), ("v2", "1.0")])
def test_representation_manifest_and_payload_versions_must_match(
    tmp_path: Path,
    payload_version: str,
    manifest_version: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    representation = _correspondence_case().representation.model_copy(
        update={"schema_version": f"polisyos.catalog.variable_representation.{payload_version}"}
    )
    ref = _persist_representation(store, representation, manifest_version=manifest_version)

    with pytest.raises(ValueError, match="canon_profile_typed_artifact_schema_version_mismatch"):
        load_variable_representation(store, ref)


def test_v2_representation_requires_exact_document_inputs_and_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    methodology = _methodology_document(store)
    representation = _stored_representation(store).model_copy(
        update={
            "schema_version": "polisyos.catalog.variable_representation.v2",
            "methodology_ref": methodology,
        }
    )
    missing_inputs_ref = _persist_representation(
        store, representation, manifest_version="2.0", include_inputs=False
    )
    with pytest.raises(ValueError, match="variable_representation_manifest_inputs_mismatch"):
        load_variable_representation(store, missing_inputs_ref)

    ref = _persist_representation(store, representation, manifest_version="2.0")
    assert load_variable_representation(store, ref) == representation
    assert store.get_manifest(ref).inputs == [
        input_ref_from_artifact_ref(
            representation.semantic_definition_ref, role="semantic_definition"
        ),
        input_ref_from_artifact_ref(methodology, role="methodology"),
    ]
    read = store.get_bytes

    def reject_full_document_read(selected):
        if selected == methodology:
            raise AssertionError("FileSystemCAS methodology must use its verified member stream")
        return read(selected)

    with monkeypatch.context() as controlled:
        controlled.setattr(store, "get_bytes", reject_full_document_read)
        assert load_variable_representation(store, ref) == representation
    blob_path, _ = store._paths(methodology.artifact_id)
    original_bytes = blob_path.read_bytes()
    blob_path.write_bytes(b"X" + original_bytes[1:])
    try:
        with pytest.raises(ArtifactIntegrityError, match="CAS member changed while streaming"):
            load_variable_representation(store, ref)
    finally:
        blob_path.write_bytes(original_bytes)
    assert load_variable_representation(store, ref) == representation


def test_v2_present_methodology_ref_requires_an_available_selected_view(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    methodology = _methodology_document(store).model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    representation = _stored_representation(store).model_copy(
        update={
            "schema_version": "polisyos.catalog.variable_representation.v2",
            "methodology_ref": methodology,
        }
    )
    ref = _persist_representation(store, representation, manifest_version="2.0")

    with pytest.raises(FileNotFoundError):
        load_variable_representation(store, ref)


def test_v2_representation_reconciles_an_available_document_view_with_its_exact_input(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    original = _methodology_document(store)
    alternate = SelectedVariableBindingRef.model_validate(
        store.put_bytes(
            store.get_bytes(original),
            PutOptions(
                kind="fabric.doc.raw",
                media_type="text/plain",
                schema=SchemaInfo(name="fabric.doc.raw", version="1.0"),
                producer=ProducerInfo(component="test.protocol-document", version="alternate-view"),
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    assert original.artifact_id == alternate.artifact_id
    assert original.manifest_profile_sha256 != alternate.manifest_profile_sha256
    assert store.get_bytes(original) == store.get_bytes(alternate)
    assert store.get_manifest(original).producer != store.get_manifest(alternate).producer
    original_representation = _stored_representation(store).model_copy(
        update={
            "schema_version": "polisyos.catalog.variable_representation.v2",
            "methodology_ref": original,
        }
    )
    changed = original_representation.model_copy(update={"methodology_ref": alternate})
    wrong_inputs_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            changed,
            PutOptions(
                kind=changed.ARTIFACT_KIND,
                media_type=changed.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=changed.ARTIFACT_SCHEMA_NAME, version="2.0"),
                inputs=list(variable_representation_manifest_inputs(original_representation)),
            ),
            return_selected_profile=True,
        ).model_dump()
    )

    with pytest.raises(ValueError, match="variable_representation_manifest_inputs_mismatch"):
        load_variable_representation(store, wrong_inputs_ref)

    rebound_ref = _persist_representation(store, changed, manifest_version="2.0")
    assert load_variable_representation(store, rebound_ref) == changed


def test_v2_representation_reopens_its_selected_document_in_a_fresh_reader(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    methodology = _methodology_document(store)
    representation = _stored_representation(store).model_copy(
        update={
            "schema_version": "polisyos.catalog.variable_representation.v2",
            "methodology_ref": methodology,
        }
    )
    ref = _persist_representation(store, representation, manifest_version="2.0")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json,sys; "
            "from polisyos.core.artifacts.store import FileSystemCAS; "
            "from polisyos.core.contracts.variable_binding import "
            "VariableRepresentationRef,load_variable_representation; "
            "value=load_variable_representation(FileSystemCAS(sys.argv[1]),"
            "VariableRepresentationRef.model_validate_json(sys.argv[2])); "
            "print(value.model_dump_json())",
            str(store.root),
            ref.model_dump_json(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert VariableRepresentation.model_validate_json(result.stdout) == representation


def test_methodology_stream_reads_fixed_chunks_and_still_checks_the_full_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    body = b"Test-owned protocol.\n" * 10_000
    methodology = _methodology_document(store, body)
    representation = _stored_representation(store).model_copy(
        update={
            "schema_version": "polisyos.catalog.variable_representation.v2",
            "methodology_ref": methodology,
        }
    )
    ref = _persist_representation(store, representation, manifest_version="2.0")
    original_open = store.open_member
    observed_bytes: list[int] = []

    @contextmanager
    def counted_open(selected, member):
        with original_open(selected, member) as stream:
            if selected != methodology:
                yield stream
            else:

                class CountedStream:
                    def read(self, size: int = -1) -> bytes:
                        assert size == 64 * 1024
                        chunk = stream.read(size)
                        observed_bytes.append(len(chunk))
                        return chunk

                yield CountedStream()

    monkeypatch.setattr(store, "open_member", counted_open)

    assert load_variable_representation(store, ref) == representation
    assert sum(observed_bytes) == len(body)
    assert len(observed_bytes) >= 4
    assert observed_bytes[-1] == 0


def _aggregated_correspondence_case(
    *,
    operation: str,
    declared_aggregation: str | None,
    raw_values: tuple[int, ...] = (2, 6),
):
    """Use the real source projection and replay, without claiming source authority."""
    case = _correspondence_case()
    condition = {
        "population_ref": case.port.scope.population_ref,
        "geography_ref": case.port.scope.geography_ref,
        "jurisdiction_ref": case.port.scope.jurisdiction_ref,
        "time_period_basis": "calendar_year",
    }
    raw_body = json.dumps(
        [
            {
                "value": value,
                "country_code": "USA",
                "year": 2024,
                "condition_json": condition,
            }
            for value in raw_values
        ],
        separators=(",", ":"),
    ).encode()
    watermark = "sha256:" + hashlib.sha256(raw_body).hexdigest()
    binding = overlay.build_metric_field_binding(
        dataset_id=case.selection.dataset_id,
        distribution_id="test.dataset.json",
        raw_field="value",
        canonical_variable=case.selection.canonical_variable,
        raw_unit="usd",
        canonical_unit="usd",
        unit_transform="identity",
        unit_transform_ref="fabric://units/usd-identity/v1",
        aggregation_method=operation,
        alignment_method="semantic",
        alignment_confidence=0.9,
        is_proxy=False,
        proxy_penalty=0.0,
        evidence_refs=("repo://test/measurement-definition",),
        valid_min=0.0,
        valid_max=100.0,
    )
    (owner_row,) = overlay.derive_canonical_observations(
        raw_body,
        passport=SimpleNamespace(
            epoch_id=case.selection.epoch_id,
            source_watermark=watermark,
            dataset_version=case.selection.dataset_version,
            observation_class=overlay.ObservationProvenanceClass.OBSERVED,
        ),
        registration=SimpleNamespace(
            catalog_dataset_id=case.selection.dataset_id,
            field_binding=binding,
        ),
    )
    case.selection = case.selection.model_copy(
        update={
            "source_watermark": watermark,
            "binding_id": binding.binding_id,
            "aggregation_method": operation,
        }
    )
    case.occurrence = replay_scoped_measurement_occurrence(
        raw_body,
        observation_id=owner_row.observation_id,
        source_selection=case.selection,
        unit_transform_evidence=None,
    )
    assert Decimal(case.occurrence.canonical_value) == Decimal(str(owner_row.value))
    for attribute in ("representation", "target_representation"):
        representation = getattr(case, attribute)
        setattr(
            case,
            attribute,
            representation.model_copy(
                update={
                    "aggregation": declared_aggregation,
                    "population_ref": case.port.scope.population_ref,
                }
            ),
        )
    case.profile = case.profile.model_copy(
        update={
            "required_axes": (
                *_HARD_AXES,
                MeasurementAxis.AGGREGATION,
                MeasurementAxis.POPULATION_REF,
            ),
            "optional_axes": (),
        }
    )
    return case


@pytest.mark.parametrize(
    ("operation", "declared_aggregation", "raw_values", "expected"),
    [
        ("sum", "sum", (2, 6), "8"),
        ("mean", "mean", (2, 6), "4"),
        ("last", "last", (2, 6), "6"),
        # Reading one provider-produced mean does not recompute that upstream mean.
        ("identity", "mean", (6,), "6"),
    ],
)
def test_correspondence_binds_the_performed_projection_without_inventing_upstream_mean(
    operation: str,
    declared_aggregation: str,
    raw_values: tuple[int, ...],
    expected: str,
) -> None:
    case = _aggregated_correspondence_case(
        operation=operation,
        declared_aggregation=declared_aggregation,
        raw_values=raw_values,
    )

    result = _evaluate(case)

    assert Decimal(case.occurrence.canonical_value) == Decimal(expected)
    assert result.status == "candidate"
    assert result.semantic_correspondence == "recomputed"
    assert "external_empirical_origin_not_established" in result.limitation_codes
    assert "source_currentness_not_established" in result.limitation_codes


@pytest.mark.parametrize(
    ("operation", "declared_aggregation"),
    [("sum", "mean"), ("mean", "sum"), ("last", "mean"), ("sum", None)],
)
@pytest.mark.parametrize("axis_selected", [True, False])
def test_equal_aggregation_declarations_do_not_override_the_performed_projection(
    operation: str,
    declared_aggregation: str | None,
    *,
    axis_selected: bool,
) -> None:
    case = _aggregated_correspondence_case(
        operation=operation,
        declared_aggregation=declared_aggregation,
    )
    if not axis_selected:
        case.profile = case.profile.model_copy(
            update={
                "required_axes": tuple(
                    axis
                    for axis in case.profile.required_axes
                    if axis != MeasurementAxis.AGGREGATION
                )
            }
        )

    result = _evaluate(case)

    assert result.status == "refused"
    assert result.semantic_correspondence == "not_established"
    assert "source_occurrence_aggregation_not_established" in result.refusal_codes


@pytest.mark.parametrize("side", ["source", "target", "both"])
@pytest.mark.parametrize("axis_selected", [True, False])
def test_representation_population_is_joined_to_its_occurrence_and_model_scope(
    side: str,
    *,
    axis_selected: bool,
) -> None:
    case = _aggregated_correspondence_case(operation="mean", declared_aggregation="mean")
    if not axis_selected:
        case.profile = case.profile.model_copy(
            update={
                "required_axes": tuple(
                    axis
                    for axis in case.profile.required_axes
                    if axis != MeasurementAxis.POPULATION_REF
                )
            }
        )
    if side in {"source", "both"}:
        case.representation = case.representation.model_copy(
            update={"population_ref": "population:other"}
        )
    if side in {"target", "both"}:
        case.target_representation = case.target_representation.model_copy(
            update={"population_ref": "population:other"}
        )

    result = _evaluate(case)

    assert result.status == "refused"
    assert result.semantic_correspondence == "not_established"
    if side in {"source", "both"}:
        assert "source_representation_population_scope_mismatch" in result.refusal_codes
    if side in {"target", "both"}:
        assert "target_representation_population_scope_mismatch" in result.refusal_codes


def test_model_input_scope_omits_unset_period_basis_for_legacy_wire_shape() -> None:
    scope = ModelInputScope(
        population_ref="population:test",
        geography_ref="geography:usa",
        jurisdiction_ref="jurisdiction:usa",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        time_role="observation_time",
    )

    assert "period_basis" not in scope.model_dump(mode="json")


def test_same_unit_does_not_hide_stock_flow_mismatch() -> None:
    case = _correspondence_case(target_quantity_kind="flow")

    result = _evaluate(case)

    assert result.status == "refused"
    assert "required_axis_mismatch:quantity_kind" in result.refusal_codes


def test_ratio_denominator_is_required_and_compared_by_exact_ref() -> None:
    denominator_a = _ref(
        VariableSemanticDefinitionRef,
        token=20,
        kind=VariableSemanticDefinition.ARTIFACT_KIND,
    )
    denominator_b = _ref(
        VariableSemanticDefinitionRef,
        token=21,
        kind=VariableSemanticDefinition.ARTIFACT_KIND,
    )
    numerator = _ref(
        VariableSemanticDefinitionRef,
        token=22,
        kind=VariableSemanticDefinition.ARTIFACT_KIND,
    )
    mismatch = _evaluate(
        _correspondence_case(
            measure_form="ratio",
            source_numerator=numerator,
            target_numerator=numerator,
            source_denominator=denominator_a,
            target_denominator=denominator_b,
        )
    )
    weakened_profile = _evaluate(
        _correspondence_case(
            measure_form="ratio",
            source_numerator=numerator,
            target_numerator=numerator,
            source_denominator=denominator_a,
            target_denominator=denominator_a,
            require_ratio_axes=False,
        )
    )

    assert mismatch.status == "refused"
    assert "required_axis_mismatch:denominator_ref" in mismatch.refusal_codes
    assert weakened_profile.status == "refused"
    assert "profile_denominator_axis_not_required" in weakened_profile.refusal_codes


def test_fixed_percent_conversion_replays_selected_raw_bytes_once() -> None:
    raw_body = json.dumps(
        [
            {
                "rate_pct": 20,
                "country_code": "USA",
                "year": 2024,
                "condition_json": {
                    "unit": "percent",
                    "population_ref": "population:workforce",
                    "jurisdiction_ref": "jurisdiction:usa",
                    "time_period_basis": "calendar_year",
                },
            }
        ],
        separators=(",", ":"),
    ).encode()
    source_watermark = "sha256:" + hashlib.sha256(raw_body).hexdigest()
    binding = overlay.build_metric_field_binding(
        dataset_id="test.workforce",
        distribution_id="test.workforce.json",
        raw_field="rate_pct",
        canonical_variable="test.unemployment_rate",
        raw_unit="percent",
        canonical_unit="ratio",
        unit_transform="fixed_multiplicative",
        unit_transform_ref="fabric://units/fixed-multiplicative/v1",
        alignment_method="semantic",
        alignment_confidence=0.9,
        is_proxy=False,
        proxy_penalty=0.0,
        evidence_refs=("repo://test/workforce-definition",),
        valid_min=0.0,
        valid_max=1.0,
    )
    (owner_row,) = overlay.derive_canonical_observations(
        raw_body,
        passport=SimpleNamespace(
            epoch_id=1,
            source_watermark=source_watermark,
            dataset_version="2024-01",
            observation_class=overlay.ObservationProvenanceClass.OBSERVED,
        ),
        registration=SimpleNamespace(catalog_dataset_id="test.workforce", field_binding=binding),
    )
    witness = FixedUnitTransformWitness.model_validate(
        owner_row.unit_transform_evidence.model_dump(mode="json")
    )
    selection = ScopedSourceSelection(
        source_receipt_ref=_ref(
            SelectedVariableBindingRef,
            token=30,
            kind="epoch.activated_overlay_admission_receipt",
        ),
        source_passport_ref=_ref(
            SelectedVariableBindingRef,
            token=31,
            kind="epoch.acquisition_passport_snapshot",
        ),
        source_boundary_candidate_ref=_ref(
            SelectedVariableBindingRef,
            token=32,
            kind="epoch.acquisition_semantic_boundary_candidate",
        ),
        source_record_ref=_ref(SelectedVariableBindingRef, token=33, kind="test.raw"),
        epoch_id=1,
        passport_id="passport:workforce:1",
        dataset_id="test.workforce",
        dataset_version="2024-01",
        source_watermark=source_watermark,
        observation_class="observed",
        raw_field="rate_pct",
        canonical_variable="test.unemployment_rate",
        raw_unit="percent",
        canonical_unit="ratio",
        unit_transform="fixed_multiplicative",
        unit_transform_ref="fabric://units/fixed-multiplicative/v1",
        binding_id=binding.binding_id,
        aggregation_method="identity",
        is_proxy=False,
    )

    replayed = replay_scoped_measurement_occurrence(
        raw_body,
        observation_id=owner_row.observation_id,
        source_selection=selection,
        unit_transform_evidence=witness,
    )

    assert replayed.canonical_value == "0.2"
    assert replayed.unit_transform_evidence == witness
    assert replayed.source_scope.population_ref == "population:workforce"
    assert replayed.source_scope.jurisdiction_ref == "jurisdiction:usa"
    assert replayed.source_scope.geography_ref == "USA"
    assert replayed.source_scope.period_basis == "calendar_year"
    with pytest.raises(ValueError, match="scoped_occurrence_replay_watermark_mismatch"):
        replay_scoped_measurement_occurrence(
            raw_body + b" ",
            observation_id=owner_row.observation_id,
            source_selection=selection,
            unit_transform_evidence=witness,
        )


@pytest.mark.parametrize(
    ("period_basis", "expected_error"),
    [
        ("fiscal_year", "scoped_occurrence_period_basis_unsupported"),
        ("unknown", "scoped_occurrence_period_basis_not_established"),
        (None, "scoped_occurrence_period_basis_not_established"),
    ],
)
def test_same_year_fiscal_or_unknown_basis_does_not_match_calendar_year(
    period_basis: str | None, expected_error: str
) -> None:
    condition = {
        "population_ref": "population:workforce",
        "jurisdiction_ref": "jurisdiction:usa",
    }
    if period_basis is not None:
        condition["time_period_basis"] = period_basis
    raw_body, owner_row, selection, witness = _raw_percent_observation_case(condition=condition)

    with pytest.raises(ValueError, match=expected_error):
        replay_scoped_measurement_occurrence(
            raw_body,
            observation_id=owner_row.observation_id,
            source_selection=selection,
            unit_transform_evidence=witness,
        )


def test_identity_binding_refuses_a_contradictory_selected_row_unit() -> None:
    raw_body, owner_row, selection, witness = _raw_percent_observation_case(
        condition={
            "unit": "EUR",
            "population_ref": "population:treasury",
            "jurisdiction_ref": "jurisdiction:fixture",
            "time_period_basis": "calendar_year",
        },
        raw_field="amount",
        raw_value=5,
        raw_unit="USD",
        canonical_unit="USD",
        unit_transform="identity",
        valid_max=10.0,
    )

    with pytest.raises(ValueError, match="scoped_occurrence_condition_unit_mismatch"):
        replay_scoped_measurement_occurrence(
            raw_body,
            observation_id=owner_row.observation_id,
            source_selection=selection,
            unit_transform_evidence=witness,
        )


def test_identity_binding_allows_absent_condition_unit_from_selected_registration() -> None:
    raw_body, owner_row, selection, witness = _raw_percent_observation_case(
        condition={
            "population_ref": "population:treasury",
            "jurisdiction_ref": "jurisdiction:fixture",
            "time_period_basis": "calendar_year",
        },
        raw_field="amount",
        raw_value=5,
        raw_unit="USD",
        canonical_unit="USD",
        unit_transform="identity",
        valid_max=10.0,
    )

    occurrence = replay_scoped_measurement_occurrence(
        raw_body,
        observation_id=owner_row.observation_id,
        source_selection=selection,
        unit_transform_evidence=witness,
    )

    assert occurrence.canonical_value == "5.0"
    assert occurrence.canonical_unit == "USD"


@pytest.mark.parametrize("coordinates", [{"survey_year": 2024}, {"wave": 2}])
def test_competing_survey_or_wave_coordinate_refuses_calendar_year_profile(
    coordinates: dict[str, int],
) -> None:
    raw_body, owner_row, selection, witness = _raw_percent_observation_case(
        condition={
            "population_ref": "population:workforce",
            "jurisdiction_ref": "jurisdiction:usa",
            "time_period_basis": "calendar_year",
        },
        coordinates=coordinates,
    )

    with pytest.raises(ValueError, match="scoped_occurrence_competing_time_coordinate_unsupported"):
        replay_scoped_measurement_occurrence(
            raw_body,
            observation_id=owner_row.observation_id,
            source_selection=selection,
            unit_transform_evidence=witness,
        )


@pytest.mark.parametrize(
    ("coordinates", "expected_error"),
    [
        ({"survey_year": ""}, "scoped_occurrence_time_coordinate_invalid"),
        ({"wave": ""}, "scoped_occurrence_time_coordinate_invalid"),
        ({"year": 2024.5}, "scoped_occurrence_time_coordinate_invalid"),
    ],
)
def test_malformed_present_time_coordinates_do_not_disappear(
    coordinates: dict[str, object], expected_error: str
) -> None:
    raw_body, owner_row, selection, witness = _raw_percent_observation_case(
        condition={
            "population_ref": "population:workforce",
            "jurisdiction_ref": "jurisdiction:usa",
            "time_period_basis": "calendar_year",
        },
        coordinates=coordinates,
    )

    with pytest.raises(ValueError, match=expected_error):
        replay_scoped_measurement_occurrence(
            raw_body,
            observation_id=owner_row.observation_id,
            source_selection=selection,
            unit_transform_evidence=witness,
        )


def test_finer_geography_ref_is_preserved_instead_of_flattened_to_country() -> None:
    raw_body, owner_row, selection, witness = _raw_percent_observation_case(
        condition={
            "population_ref": "population:workforce",
            "jurisdiction_ref": "jurisdiction:usa",
            "geography_ref": "region:usa-ca",
            "time_period_basis": "calendar_year",
        }
    )
    source_occurrence = replay_scoped_measurement_occurrence(
        raw_body,
        observation_id=owner_row.observation_id,
        source_selection=selection,
        unit_transform_evidence=witness,
    )
    case = _correspondence_case()
    country_scope = case.basis.scope
    case.occurrence = case.occurrence.model_copy(
        update={"source_scope": source_occurrence.source_scope}
    )
    case.basis = case.basis.model_copy(update={"scope": country_scope})

    result = _evaluate(case)

    assert source_occurrence.source_scope.geography_ref == "region:usa-ca"
    assert source_occurrence.source_scope != country_scope
    assert result.status == "refused"
    assert "source_occurrence_scope_mismatch" in result.refusal_codes


def test_unrecognized_finer_geography_coordinate_does_not_fall_back_to_country() -> None:
    raw_body, owner_row, selection, witness = _raw_percent_observation_case(
        condition={
            "population_ref": "population:workforce",
            "jurisdiction_ref": "jurisdiction:usa",
            "region_ref": "region:usa-ca",
            "time_period_basis": "calendar_year",
        }
    )

    with pytest.raises(ValueError, match="scoped_occurrence_condition_scope_unrecognized"):
        replay_scoped_measurement_occurrence(
            raw_body,
            observation_id=owner_row.observation_id,
            source_selection=selection,
            unit_transform_evidence=witness,
        )


@pytest.mark.parametrize("period_basis", [None, "unknown", "fiscal_year"])
def test_selected_model_scope_must_declare_calendar_year_basis(
    period_basis: str | None,
) -> None:
    case = _correspondence_case()
    unknown_model_scope = case.basis.scope.model_copy(update={"period_basis": period_basis})
    case.basis = case.basis.model_copy(update={"scope": unknown_model_scope})
    case.port = case.port.model_copy(update={"scope": unknown_model_scope})

    result = _evaluate(case)

    assert result.status == "refused"
    assert "calendar_year_period_basis_not_established" in result.refusal_codes


def test_source_selection_recomputes_owner_binding_and_requires_selected_raw_ref() -> None:
    case = _correspondence_case()
    binding = {
        "dataset_id": "test.dataset",
        "raw_field": "value",
        "canonical_variable": "test.measurement",
        "raw_unit": "usd",
        "canonical_unit": "usd",
        "unit_transform": "identity",
        "unit_transform_ref": "fabric://units/usd-identity/v1",
        "aggregation_method": "identity",
        "is_proxy": False,
    }
    encoded = json.dumps(
        binding, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    binding["binding_id"] = (
        "field-binding:sha256:" + hashlib.sha256((encoded + "\n").encode()).hexdigest()
    )
    passport = {
        "schema_version": "polisyos.runtime.acquisition_admission_passport.v2",
        "epoch_id": 1,
        "passport_id": "passport:test:1",
        "dataset_version": "2024-01",
        "source_watermark": "sha256:" + "a" * 64,
        "observation_class": "observed",
        "registration": {
            "catalog_dataset_id": "test.dataset",
            "metric_id": "test.measurement",
            "field_binding": binding,
        },
        "semantic_boundary_candidate_ref": case.boundary_ref.model_dump(mode="json"),
        "raw_artifact_id": str(case.record_ref.artifact_id),
    }
    selected_refs = {
        "source_receipt_ref": case.receipt_ref,
        "source_passport_ref": case.passport_ref,
        "source_boundary_candidate_ref": case.boundary_ref,
        "source_record_ref": case.record_ref,
    }

    selection = scoped_source_selection_from_passport_mapping(passport, **selected_refs)

    assert selection.canonical_variable == "test.measurement"
    assert selection.binding_id == binding["binding_id"]
    altered = json.loads(json.dumps(passport))
    altered["registration"]["field_binding"]["canonical_variable"] = "test.other"
    with pytest.raises(ValueError, match="scoped_source_passport_binding_identity_mismatch"):
        scoped_source_selection_from_passport_mapping(altered, **selected_refs)
    wrong_record = case.record_ref.model_copy(
        update={"artifact_id": ArtifactID.from_sha256_hex(f"{99:064x}")}
    )
    with pytest.raises(ValueError, match="scoped_source_passport_raw_record_ref_mismatch"):
        scoped_source_selection_from_passport_mapping(
            passport,
            **{**selected_refs, "source_record_ref": wrong_record},
        )
