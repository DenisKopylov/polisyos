from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import ExecPlanRef, ProgramGraphRef
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ProgramGraphInputInterface,
    load_program_graph_input_interface,
    persist_program_graph_input_interface,
    verify_model_input_port_semantics,
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
    load_variable_representation,
    variable_representation_manifest_inputs,
)
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionAuthorityEntry,
    AcquisitionAuthorityError,
    AcquisitionAuthorityRegistry,
    AcquisitionSourceMeasureScope,
    CanonicalAcquisitionAuthority,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.fabric.data_plane import content_sha256
from tests._helpers.acquisition_production import _entry, _resolver


def _put_selected_model_json(
    store: FileSystemCAS,
    value: BaseModel,
    *,
    kind: str,
    name: str,
    manifest_version: str = "1.0",
) -> ArtifactRef:
    return store.put_json(
        value,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=name, version=manifest_version),
        ),
        return_selected_profile=True,
    )


def _put_semantic_definition(
    store: FileSystemCAS,
    definition: VariableSemanticDefinition,
) -> VariableSemanticDefinitionRef:
    return VariableSemanticDefinitionRef.model_validate(
        store.put_json(
            definition,
            PutOptions(
                kind=definition.ARTIFACT_KIND,
                media_type=definition.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=definition.ARTIFACT_SCHEMA_NAME,
                    version=definition.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[
                    input_ref_from_artifact_ref(ref, role="definition_evidence")
                    for ref in definition.definition_evidence_refs
                ],
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )


def _model_inputs(
    store: FileSystemCAS,
    *,
    source_quantity_kind: str = "stock",
    definition_namespace: str = "test.fiscal",
    definition_revision: str = "r1",
    definition_meaning: str = (
        "Government fiscal balance measured for a bounded population and period."
    ),
    source_methodology_ref: SelectedVariableBindingRef | None = None,
    target_methodology_ref: SelectedVariableBindingRef | None = None,
    compare_methodology: bool = False,
) -> tuple[
    VariableSemanticDefinitionRef,
    VariableRepresentationRef,
    MeasurementBindingProfileRef,
    ArtifactRef,
]:
    evidence_ref = store.put_bytes(
        b"Test-owned definition evidence.\n",
        PutOptions(kind="test.variable_definition_evidence", media_type="text/plain"),
        return_selected_profile=True,
    )
    evidence_ref = SelectedVariableBindingRef.model_validate(evidence_ref.model_dump(mode="json"))
    definition = VariableSemanticDefinition(
        namespace=definition_namespace,
        stable_id="balance",
        revision=definition_revision,
        meaning=definition_meaning,
        definition_evidence_refs=(evidence_ref,),
    )
    definition_ref = _put_semantic_definition(store, definition)

    uses_v2_representation = (
        source_methodology_ref is not None or target_methodology_ref is not None
    )
    representation = VariableRepresentation(
        representation_id="test.fiscal.balance.source",
        revision="r1",
        semantic_definition_ref=definition_ref,
        quantity_kind=source_quantity_kind,
        measure_form="absolute",
        unit_id="usd",
        scale_to_unit=Decimal("1"),
        time_support="period_average",
        temporal_granularity="annual",
        aggregation="mean",
        grain=("country", "period"),
        population_ref="population:whole-country",
        **(
            {
                "schema_version": "polisyos.catalog.variable_representation.v2",
                "methodology_ref": source_methodology_ref,
            }
            if uses_v2_representation
            else {}
        ),
    )
    representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            representation,
            PutOptions(
                kind=representation.ARTIFACT_KIND,
                media_type=representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=representation.ARTIFACT_SCHEMA_NAME,
                    version="2.0" if uses_v2_representation else "1.0",
                ),
                inputs=list(variable_representation_manifest_inputs(representation)),
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )

    model_representation = representation.model_copy(
        update={
            "representation_id": "test.fiscal.balance.model",
            "quantity_kind": "stock",
            **({"methodology_ref": target_methodology_ref} if uses_v2_representation else {}),
        }
    )
    model_representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            model_representation,
            PutOptions(
                kind=model_representation.ARTIFACT_KIND,
                media_type=model_representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=model_representation.ARTIFACT_SCHEMA_NAME,
                    version="2.0" if uses_v2_representation else "1.0",
                ),
                inputs=list(variable_representation_manifest_inputs(model_representation)),
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )

    profile = MeasurementBindingProfile(
        profile_id="test.fiscal.balance",
        revision="r1",
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
        **(
            {
                "schema_version": "polisyos.catalog.measurement_binding_profile.v2",
                "optional_axes": (MeasurementAxis.METHODOLOGY_REF,),
            }
            if compare_methodology
            else {}
        ),
    )
    profile_ref = MeasurementBindingProfileRef.model_validate(
        _put_selected_model_json(
            store,
            profile,
            kind=profile.ARTIFACT_KIND,
            name=profile.ARTIFACT_SCHEMA_NAME,
            manifest_version="2.0" if compare_methodology else "1.0",
        ).model_dump(mode="json")
    )

    graph = store.put_bytes(
        b"Selected test graph",
        PutOptions(kind="foundry.program_graph", media_type="application/json"),
        return_selected_profile=True,
    )
    plan = store.put_bytes(
        b"Selected test plan",
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
        return_selected_profile=True,
    )
    registry_bundle = store.put_bytes(
        b"Selected test registry",
        PutOptions(kind="core.registry_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    interface = ProgramGraphInputInterface(
        program_graph_ref=ProgramGraphRef.model_validate(graph.model_dump(mode="json")),
        exec_plan_ref=ExecPlanRef.model_validate(plan.model_dump(mode="json")),
        registry_bundle_ref=registry_bundle,
        ports=(
            ModelInputPort(
                port_id="fiscal-balance-input",
                slot_id="fiscal_balance",
                state_path="government.balance",
                unit_id="usd",
                purpose="simulation_input",
                semantic_definition_ref=definition_ref,
                representation_ref=model_representation_ref,
                binding_profile_ref=profile_ref,
                scope=ModelInputScope(
                    population_ref="population:whole-country",
                    geography_ref="UKR",
                    jurisdiction_ref="UKR",
                    period_start=date(2024, 1, 1),
                    period_end=date(2024, 12, 31),
                    time_role="observation_time",
                    period_basis="calendar_year",
                ),
                physical_encoding=ModelInputPhysicalEncoding(
                    shape=(1,),
                    dtype="float64",
                    max_absolute_error=Decimal("0.001"),
                ),
            ),
        ),
    )
    interface_ref = persist_program_graph_input_interface(store, interface)
    return definition_ref, representation_ref, profile_ref, interface_ref


def _authority_entry(
    definition_ref: VariableSemanticDefinitionRef,
    representation_ref: VariableRepresentationRef,
    *,
    suffix: str = "first",
    temporal_start: str | None = None,
    temporal_end: str | None = None,
) -> AcquisitionAuthorityEntry:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values.update(
        {
            "landing_dataset_id": f"acquisition.test.fiscal_balance.{suffix}",
            "landing_distribution_id": f"acquisition.test.fiscal_balance.{suffix}.json",
            "raw_unit": "usd",
            "canonical_unit": "usd",
            "source_measure_scope": AcquisitionSourceMeasureScope(
                population="population:whole-country",
                temporal_granularity="annual",
            ),
            "source_semantic_definition_ref": definition_ref,
            "source_representation_ref": representation_ref,
        }
    )
    if temporal_start is not None:
        values["temporal_start"] = temporal_start
    if temporal_end is not None:
        values["temporal_end"] = temporal_end
    return build_authority_entry(**values)


def _replace_authority_registry(
    authority: CanonicalAcquisitionAuthority,
    entries: tuple[AcquisitionAuthorityEntry, ...],
) -> None:
    registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=(authority.provision.l5_measurement_registry_content_sha256),
        entries=entries,
    )
    registry_path = authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")


def test_catalog_discovers_one_exact_model_input_source_descriptor(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, source_representation_ref, _, interface_ref = _model_inputs(store)
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=_authority_entry(definition_ref, source_representation_ref),
    )

    candidate = authority.discover_model_input_source_descriptor(
        store,
        model_input_interface_ref=interface_ref,
        port_id="fiscal-balance-input",
    )

    assert (
        candidate.authority_entry_id
        == _authority_entry(definition_ref, source_representation_ref).entry_id
    )
    assert candidate.authority_registry_content_sha256
    assert "query_envelope" not in candidate.model_dump(mode="json")
    assert candidate.source_semantic_definition_ref == definition_ref
    assert candidate.semantic_correspondence == "not_established"
    assert candidate.recomputed_axes == (
        MeasurementAxis.QUANTITY_KIND,
        MeasurementAxis.MEASURE_FORM,
        MeasurementAxis.UNIT_ID,
        MeasurementAxis.TIME_SUPPORT,
        MeasurementAxis.TEMPORAL_GRANULARITY,
        MeasurementAxis.AGGREGATION,
        MeasurementAxis.GRAIN,
        MeasurementAxis.POPULATION_REF,
    )
    assert set(candidate.may_not_use_for) == {
        "measurement_admission",
        "fetch_permission",
        "claim_evidence",
        "source_currentness",
    }


def _methodology_document(store: FileSystemCAS, body: bytes) -> SelectedVariableBindingRef:
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


@pytest.mark.parametrize("source_method_present", [True, False])
def test_catalog_source_discovery_admits_v2_document_edges_without_inventing_authority(
    tmp_path: Path,
    *,
    source_method_present: bool,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    method = _methodology_document(
        store, b"Test-owned measurement protocol, no empirical authority.\n"
    )
    definition_ref, source_ref, _, interface_ref = _model_inputs(
        store,
        source_methodology_ref=method if source_method_present else None,
        target_methodology_ref=method,
        compare_methodology=True,
    )
    authority, _ = _resolver(
        tmp_path / "catalog-owner", authority_entry=_authority_entry(definition_ref, source_ref)
    )

    candidate = authority.discover_model_input_source_descriptor(
        store, model_input_interface_ref=interface_ref, port_id="fiscal-balance-input"
    )

    assert candidate.source_representation_ref == source_ref
    assert candidate.semantic_correspondence == "not_established"
    assert "fetch_permission" in candidate.may_not_use_for
    if source_method_present:
        assert MeasurementAxis.METHODOLOGY_REF in candidate.recomputed_axes
        assert candidate.unknown_optional_axes == ()
    else:
        assert candidate.unknown_optional_axes == (MeasurementAxis.METHODOLOGY_REF,)


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_catalog_source_discovery_checks_source_document_separately_from_valid_target(
    tmp_path: Path,
    damage: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_method = _methodology_document(store, b"Test-owned source protocol.\n")
    target_method = _methodology_document(store, b"Test-owned independent target protocol.\n")
    assert source_method.artifact_id != target_method.artifact_id
    definition_ref, source_ref, _, interface_ref = _model_inputs(
        store, source_methodology_ref=source_method, target_methodology_ref=target_method
    )
    authority, _ = _resolver(
        tmp_path / "catalog-owner", authority_entry=_authority_entry(definition_ref, source_ref)
    )
    (port,) = load_program_graph_input_interface(store, interface_ref).ports
    assert verify_model_input_port_semantics(store, port).methodology_ref == target_method
    assert (
        authority.discover_model_input_source_descriptor(
            store, model_input_interface_ref=interface_ref, port_id=port.port_id
        ).source_representation_ref
        == source_ref
    )
    blob, _ = store._paths(source_method.artifact_id)
    held_blob = tmp_path / "held-source-protocol"
    original = blob.read_bytes()
    if damage == "missing":
        blob.rename(held_blob)
    else:
        blob.write_bytes(b"X" + original[1:])
    try:
        assert verify_model_input_port_semantics(store, port).methodology_ref == target_method
        with pytest.raises(
            AcquisitionAuthorityError, match="model_input_source_descriptor_artifact_unavailable"
        ):
            authority.discover_model_input_source_descriptor(
                store, model_input_interface_ref=interface_ref, port_id=port.port_id
            )
    finally:
        if damage == "missing":
            held_blob.rename(blob)
        else:
            blob.write_bytes(original)
    assert (
        authority.discover_model_input_source_descriptor(
            store, model_input_interface_ref=interface_ref, port_id=port.port_id
        ).source_representation_ref
        == source_ref
    )


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_actual_port_verifier_refuses_target_document_without_harming_valid_source(
    tmp_path: Path,
    damage: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_method = _methodology_document(store, b"Test-owned valid source protocol.\n")
    target_method = _methodology_document(store, b"Test-owned distinct target protocol.\n")
    assert source_method.artifact_id != target_method.artifact_id
    definition_ref, source_ref, _, interface_ref = _model_inputs(
        store, source_methodology_ref=source_method, target_methodology_ref=target_method
    )
    authority, _ = _resolver(
        tmp_path / "catalog-owner", authority_entry=_authority_entry(definition_ref, source_ref)
    )
    (port,) = load_program_graph_input_interface(store, interface_ref).ports
    assert load_variable_representation(store, source_ref).methodology_ref == source_method
    assert verify_model_input_port_semantics(store, port).methodology_ref == target_method
    blob, _ = store._paths(target_method.artifact_id)
    held_blob = tmp_path / "held-target-protocol"
    original = blob.read_bytes()
    if damage == "missing":
        blob.rename(held_blob)
    else:
        blob.write_bytes(b"X" + original[1:])
    try:
        assert load_variable_representation(store, source_ref).methodology_ref == source_method
        expected_error = FileNotFoundError if damage == "missing" else ArtifactIntegrityError
        with pytest.raises(expected_error):
            verify_model_input_port_semantics(store, port)
        with pytest.raises(
            AcquisitionAuthorityError, match="model_input_source_port_semantics_unavailable"
        ):
            authority.discover_model_input_source_descriptor(
                store, model_input_interface_ref=interface_ref, port_id=port.port_id
            )
        assert load_variable_representation(store, source_ref).methodology_ref == source_method
    finally:
        if damage == "missing":
            held_blob.rename(blob)
        else:
            blob.write_bytes(original)
    assert verify_model_input_port_semantics(store, port).methodology_ref == target_method


@pytest.mark.parametrize("side", ["source", "target"])
def test_catalog_source_discovery_refuses_an_available_foreign_document_view_in_wrong_lineage(
    tmp_path: Path,
    side: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    original = _methodology_document(store, b"Test-owned source protocol.\n")
    alternate = SelectedVariableBindingRef.model_validate(
        store.put_bytes(
            store.get_bytes(original),
            PutOptions(
                kind="fabric.doc.raw",
                media_type="text/plain",
                schema=SchemaInfo(name="fabric.doc.raw", version="1.0"),
                producer=ProducerInfo(component="test.protocol-document", version="alternate"),
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    assert original.artifact_id == alternate.artifact_id
    assert original.manifest_profile_sha256 != alternate.manifest_profile_sha256
    assert store.get_bytes(original) == store.get_bytes(alternate)
    store.get_manifest(alternate)
    independent = _methodology_document(store, b"Test-owned independent protocol.\n")
    definition_ref, source_ref, _, interface_ref = _model_inputs(
        store,
        source_methodology_ref=original if side == "source" else independent,
        target_methodology_ref=independent if side == "source" else original,
    )
    interface = load_program_graph_input_interface(store, interface_ref)
    (port,) = interface.ports
    selected_ref = source_ref if side == "source" else port.representation_ref
    selected_representation = load_variable_representation(store, selected_ref)
    changed = selected_representation.model_copy(update={"methodology_ref": alternate})
    wrong_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            changed,
            PutOptions(
                kind=changed.ARTIFACT_KIND,
                media_type=changed.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=changed.ARTIFACT_SCHEMA_NAME, version="2.0"),
                inputs=list(variable_representation_manifest_inputs(selected_representation)),
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    if side == "target":
        wrong_port = port.model_copy(update={"representation_ref": wrong_ref})
        interface_ref = persist_program_graph_input_interface(
            store, interface.model_copy(update={"ports": (wrong_port,)})
        )
        assert load_variable_representation(store, source_ref).methodology_ref == independent
        with pytest.raises(ValueError, match="variable_representation_manifest_inputs_mismatch"):
            verify_model_input_port_semantics(store, wrong_port)
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=_authority_entry(
            definition_ref, wrong_ref if side == "source" else source_ref
        ),
    )

    with pytest.raises(ValueError, match="variable_representation_manifest_inputs_mismatch"):
        load_variable_representation(store, wrong_ref)
    expected = (
        "model_input_source_descriptor_artifact_unavailable"
        if side == "source"
        else "model_input_source_port_semantics_unavailable"
    )
    with pytest.raises(AcquisitionAuthorityError, match=expected):
        authority.discover_model_input_source_descriptor(
            store, model_input_interface_ref=interface_ref, port_id="fiscal-balance-input"
        )


def test_scoped_query_envelope_ignores_unrelated_registry_metadata(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, interface_ref = _model_inputs(store)
    selected = _authority_entry(definition_ref, representation_ref, suffix="selected")
    unrelated = _entry()
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=selected,
    )
    _replace_authority_registry(authority, (selected, unrelated))

    before = authority.discover_model_input_source_descriptor(
        store,
        model_input_interface_ref=interface_ref,
        port_id="fiscal-balance-input",
        include_query_envelope=True,
    )
    assert before.query_envelope is not None

    unrelated_fields = unrelated.model_dump(mode="python", exclude={"entry_id"})
    unrelated_fields["title"] = "An unrelated registry row with revised descriptive metadata."
    unrelated_fields["description"] = "This row is outside the exact-definition query."
    revised_unrelated = build_authority_entry(**unrelated_fields)
    _replace_authority_registry(authority, (selected, revised_unrelated))

    after = authority.discover_model_input_source_descriptor(
        store,
        model_input_interface_ref=interface_ref,
        port_id="fiscal-balance-input",
        include_query_envelope=True,
    )

    assert after.authority_registry_content_sha256 != before.authority_registry_content_sha256
    assert after.query_envelope == before.query_envelope
    assert [row.entry_id for row in after.query_envelope.rows] == [selected.entry_id]
    assert after.query_envelope.rows[0].disposition == "compatible"
    assert after.query_envelope.rows[0].reason_codes == ()


def test_scoped_query_envelope_records_exact_definition_countercandidate(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, interface_ref = _model_inputs(store)
    selected = _authority_entry(definition_ref, representation_ref, suffix="selected")
    countercandidate = _authority_entry(
        definition_ref,
        representation_ref,
        suffix="countercandidate",
    )
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=selected,
    )
    _replace_authority_registry(authority, (selected, countercandidate))

    with pytest.raises(AcquisitionAuthorityError) as error:
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
            include_query_envelope=True,
        )

    assert error.value.code == "model_input_source_descriptor_ambiguous"
    envelope = error.value.query_envelope
    assert envelope is not None
    assert {row.entry_id for row in envelope.rows} == {
        selected.entry_id,
        countercandidate.entry_id,
    }
    assert all(row.disposition == "compatible" for row in envelope.rows)
    assert all(row.reason_codes == () for row in envelope.rows)


def test_exhaustive_definition_oracle_is_order_invariant_and_ignores_aliases(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, interface_ref = _model_inputs(store)
    repeated_definition_ref, flow_representation_ref, _, _ = _model_inputs(
        store,
        source_quantity_kind="flow",
    )
    namespace_alias_ref, namespace_alias_representation_ref, _, _ = _model_inputs(
        store,
        definition_namespace="test.other",
    )
    content_alias_ref, content_alias_representation_ref, _, _ = _model_inputs(
        store,
        definition_meaning=(
            "A different balance definition sharing the same local label and revision."
        ),
    )
    assert repeated_definition_ref == definition_ref
    assert namespace_alias_ref != definition_ref
    assert content_alias_ref != definition_ref

    selected = _authority_entry(definition_ref, representation_ref, suffix="selected")
    exact_incompatible = _authority_entry(
        definition_ref,
        flow_representation_ref,
        suffix="exact-incompatible-countercandidate",
    )
    namespace_alias = _authority_entry(
        namespace_alias_ref,
        namespace_alias_representation_ref,
        suffix="same-local-label-different-namespace",
    )
    content_alias = _authority_entry(
        content_alias_ref,
        content_alias_representation_ref,
        suffix="same-namespace-label-different-meaning",
    )
    entries = (selected, exact_incompatible, namespace_alias, content_alias)
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=selected)

    model_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, definition_ref
    )
    target_definition_key = artifact_ref_identity_key(definition_ref)
    outcomes = []
    for registry_entries in (entries, tuple(reversed(entries))):
        _replace_authority_registry(authority, registry_entries)
        registry = AcquisitionAuthorityRegistry.model_validate_json(
            (authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY).read_bytes()
        )

        # Independently enumerate the complete tiny fixture and reopen each
        # row's selected definition and representation before forming the oracle.
        expected_exact_definition_ids: set[str] = set()
        exact_definition_rows: dict[str, tuple[str, tuple[str, ...]]] = {}
        for entry in registry.entries:
            source_definition_ref = entry.source_semantic_definition_ref
            source_representation_ref = entry.source_representation_ref
            assert source_definition_ref is not None
            assert source_representation_ref is not None
            source_definition = validate_core_model_json_artifact(
                VariableSemanticDefinition,
                store,
                source_definition_ref,
            )
            source_representation = validate_core_model_json_artifact(
                VariableRepresentation,
                store,
                source_representation_ref,
            )
            representation_manifest = store.get_manifest(source_representation_ref)
            assert source_representation.semantic_definition_ref == source_definition_ref
            assert tuple(representation_manifest.inputs) == (
                input_ref_from_artifact_ref(source_definition_ref, role="semantic_definition"),
            )
            if artifact_ref_identity_key(source_definition_ref) != target_definition_key:
                assert source_definition != model_definition
                continue

            assert source_definition == model_definition
            expected_exact_definition_ids.add(entry.entry_id)
            if source_representation.quantity_kind == "stock":
                exact_definition_rows[entry.entry_id] = ("compatible", ())
            else:
                exact_definition_rows[entry.entry_id] = (
                    "incompatible",
                    ("required_axis_mismatch:quantity_kind",),
                )

        assert expected_exact_definition_ids == {selected.entry_id, exact_incompatible.entry_id}
        assert {namespace_alias.entry_id, content_alias.entry_id}.isdisjoint(
            expected_exact_definition_ids
        )

        result = authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
            include_query_envelope=True,
        )
        assert result.authority_entry_id == selected.entry_id
        assert result.source_semantic_definition_ref == definition_ref
        assert result.query_envelope is not None
        actual_rows = {
            row.entry_id: (row.disposition, row.reason_codes) for row in result.query_envelope.rows
        }
        assert actual_rows == exact_definition_rows
        outcomes.append((result.authority_entry_id, actual_rows))

    assert outcomes[0] == outcomes[1]


def test_scoped_query_envelope_tracks_same_definition_reclassification(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, compatible_representation_ref, _, interface_ref = _model_inputs(store)
    flow_definition_ref, incompatible_representation_ref, _, _ = _model_inputs(
        store,
        source_quantity_kind="flow",
    )
    assert flow_definition_ref == definition_ref
    selected = _authority_entry(
        definition_ref,
        compatible_representation_ref,
        suffix="selected",
    )
    reclassifiable = _authority_entry(
        definition_ref,
        incompatible_representation_ref,
        suffix="reclassifiable",
    )
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=selected,
    )
    _replace_authority_registry(authority, (selected, reclassifiable))

    before = authority.discover_model_input_source_descriptor(
        store,
        model_input_interface_ref=interface_ref,
        port_id="fiscal-balance-input",
        include_query_envelope=True,
    )
    assert before.query_envelope is not None
    before_rows = {row.entry_id: row for row in before.query_envelope.rows}
    assert before_rows[selected.entry_id].disposition == "compatible"
    assert before_rows[selected.entry_id].reason_codes == ()
    assert before_rows[reclassifiable.entry_id].disposition == "incompatible"
    assert before_rows[reclassifiable.entry_id].reason_codes

    reclassified_fields = reclassifiable.model_dump(mode="python", exclude={"entry_id"})
    reclassified_fields["source_representation_ref"] = compatible_representation_ref
    reclassified = build_authority_entry(**reclassified_fields)
    _replace_authority_registry(authority, (selected, reclassified))

    with pytest.raises(AcquisitionAuthorityError) as error:
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
            include_query_envelope=True,
        )

    assert error.value.code == "model_input_source_descriptor_ambiguous"
    after = error.value.query_envelope
    assert after is not None
    after_rows = {row.entry_id: row for row in after.rows}
    assert reclassified.entry_id != reclassifiable.entry_id
    assert reclassified.entry_id in after_rows
    assert after_rows[reclassified.entry_id].disposition == "compatible"
    assert after_rows[reclassified.entry_id].reason_codes == ()


def test_catalog_accepts_explicit_full_calendar_date_bounds(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, source_representation_ref, _, interface_ref = _model_inputs(store)
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=_authority_entry(
            definition_ref,
            source_representation_ref,
            temporal_start="2024-01-01",
            temporal_end="2024-12-31",
        ),
    )

    candidate = authority.discover_model_input_source_descriptor(
        store,
        model_input_interface_ref=interface_ref,
        port_id="fiscal-balance-input",
    )

    assert candidate.authority_entry_id


@pytest.mark.parametrize(
    ("temporal_start", "temporal_end"),
    [
        ("2024-10-01", "2024-12-31"),
        ("2024-01-01T00:00:01Z", "2024-12-31T23:59:59Z"),
    ],
)
def test_catalog_refuses_temporal_bounds_that_do_not_cover_full_model_year(
    tmp_path: Path,
    temporal_start: str,
    temporal_end: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, source_representation_ref, _, interface_ref = _model_inputs(store)
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=_authority_entry(
            definition_ref,
            source_representation_ref,
            temporal_start=temporal_start,
            temporal_end=temporal_end,
        ),
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="source_temporal_scope_mismatch",
    ):
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
        )


def test_catalog_refuses_same_label_and_revision_with_different_definition_content(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    model_definition_ref, _, _, interface_ref = _model_inputs(store)
    evidence_ref = store.put_bytes(
        b"Different source-owned evidence.\n",
        PutOptions(kind="test.variable_definition_evidence", media_type="text/plain"),
        return_selected_profile=True,
    )
    source_definition = VariableSemanticDefinition(
        namespace="test.fiscal",
        stable_id="balance",
        revision="r1",
        meaning="A same-label definition with altered meaning and content.",
        definition_evidence_refs=(
            SelectedVariableBindingRef.model_validate(evidence_ref.model_dump(mode="json")),
        ),
    )
    source_definition_ref = _put_semantic_definition(store, source_definition)
    source_representation = VariableRepresentation(
        representation_id="test.fiscal.balance.wrong-source",
        revision="r1",
        semantic_definition_ref=source_definition_ref,
        quantity_kind="stock",
        measure_form="absolute",
        unit_id="usd",
        scale_to_unit=Decimal("1"),
        time_support="period_average",
        temporal_granularity="annual",
        aggregation="mean",
        grain=("country", "period"),
        population_ref="population:whole-country",
    )
    source_representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            source_representation,
            PutOptions(
                kind=source_representation.ARTIFACT_KIND,
                media_type=source_representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=source_representation.ARTIFACT_SCHEMA_NAME,
                    version=source_representation.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[
                    input_ref_from_artifact_ref(source_definition_ref, role="semantic_definition")
                ],
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=_authority_entry(source_definition_ref, source_representation_ref),
    )

    assert source_definition_ref != model_definition_ref
    with pytest.raises(
        AcquisitionAuthorityError,
        match="model_input_source_descriptor_unresolved",
    ):
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
        )


def test_catalog_refuses_port_id_from_another_model_owner(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, source_representation_ref, _, interface_ref = _model_inputs(store)
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=_authority_entry(definition_ref, source_representation_ref),
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="model_input_source_port_ambiguous_or_missing",
    ):
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="foreign-model-port",
        )


def test_catalog_refuses_ambiguous_exact_source_descriptors(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, interface_ref = _model_inputs(store)
    entries = (
        _authority_entry(definition_ref, representation_ref, suffix="first"),
        _authority_entry(definition_ref, representation_ref, suffix="second"),
    )
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=entries[0])
    # Replace only the test-owned registry fixture with the same canonical builder's
    # two content-bound entries, preserving the current baseline/provision anchors.
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
        build_authority_registry,
    )

    registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=authority.provision.l5_measurement_registry_content_sha256,
        entries=entries,
    )
    registry_path = authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")

    with pytest.raises(
        AcquisitionAuthorityError,
        match="model_input_source_descriptor_ambiguous",
    ):
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
        )


def test_catalog_refuses_source_descriptor_with_incompatible_required_quantity_axis(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, source_representation_ref, _, interface_ref = _model_inputs(
        store,
        source_quantity_kind="flow",
    )
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=_authority_entry(definition_ref, source_representation_ref),
    )

    with pytest.raises(AcquisitionAuthorityError) as error:
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
            include_query_envelope=True,
        )

    assert error.value.code == "model_input_source_descriptor_incompatible"
    assert error.value.query_envelope is not None
    assert len(error.value.query_envelope.rows) == 1
    assert error.value.query_envelope.rows[0].disposition == "incompatible"
    assert error.value.query_envelope.rows[0].reason_codes == (
        "required_axis_mismatch:quantity_kind",
    )


def test_legacy_authority_entries_omit_absent_semantic_refs_and_pair_them(
    tmp_path: Path,
) -> None:
    legacy = _entry()
    payload = legacy.model_dump(mode="json")
    assert "source_semantic_definition_ref" not in payload
    assert "source_representation_ref" not in payload
    assert legacy.entry_id == "acquisition-authority:" + content_sha256(legacy.identity_payload())

    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, _, _, _ = _model_inputs(store)
    values = legacy.model_dump(mode="python", exclude={"entry_id"})
    values["source_semantic_definition_ref"] = definition_ref
    with pytest.raises(ValidationError, match="source semantic definition and representation refs"):
        build_authority_entry(**values)


def test_declared_source_geography_preserves_native_and_model_coordinates(tmp_path: Path) -> None:
    import json

    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        _preacquisition_source_scope_refusal,
        verify_declared_source_geography,
    )
    from tests._helpers.acquisition_production import _normalized_rows, _raw_body

    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, source_representation_ref, _, interface_ref = _model_inputs(store)
    original = _authority_entry(definition_ref, source_representation_ref)
    values = original.model_dump(mode="python", exclude={"entry_id"})
    values["source_measure_scope"] = AcquisitionSourceMeasureScope(
        population="population:whole-country",
        temporal_granularity="annual",
        source_geography_id="UA",
        geography_ref="UA",
        jurisdiction_ref="UA",
        time_period_basis="calendar_year",
    )
    entry = build_authority_entry(**values)
    assert entry.country_codes == ("UKR",)
    interface = load_program_graph_input_interface(store, interface_ref)
    (port,) = interface.ports
    port = port.model_copy(
        update={
            "scope": port.scope.model_copy(update={"geography_ref": "UA", "jurisdiction_ref": "UA"})
        }
    )
    scoped_interface = interface.model_copy(update={"ports": (port,)})
    scoped_interface_ref = persist_program_graph_input_interface(store, scoped_interface)
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=entry)
    candidate = authority.discover_model_input_source_descriptor(
        store, model_input_interface_ref=scoped_interface_ref, port_id=port.port_id
    )
    assert candidate.authority_entry_id == entry.entry_id

    source_representation = load_variable_representation(store, source_representation_ref)
    assert _preacquisition_source_scope_refusal(entry, port.scope, source_representation) is None
    mismatched_scope = port.scope.model_copy(update={"jurisdiction_ref": "US"})
    assert (
        _preacquisition_source_scope_refusal(entry, mismatched_scope, source_representation)
        == "source_geography_scope_mismatch"
    )
    assert entry.source_measure_scope is not None
    changed_values = entry.model_dump(mode="python", exclude={"entry_id"})
    changed_values["source_measure_scope"] = entry.source_measure_scope.model_copy(
        update={"time_period_basis": "fiscal_year"}
    )
    changed_period = build_authority_entry(**changed_values)
    assert (
        _preacquisition_source_scope_refusal(changed_period, port.scope, source_representation)
        == "source_period_basis_mismatch"
    )

    raw = _raw_body(_normalized_rows())
    verify_declared_source_geography(entry, connector_id="worldbank.wdi", raw_body=raw)
    altered = json.loads(raw)
    altered[1][0]["country"]["id"] = "US"
    with pytest.raises(AcquisitionAuthorityError, match="source_declared_geography_mismatch"):
        verify_declared_source_geography(
            entry, connector_id="worldbank.wdi", raw_body=json.dumps(altered).encode()
        )
