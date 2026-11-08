from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import ExecPlanRef, ProgramGraphRef
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ProgramGraphInputInterface,
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
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityEntry,
    AcquisitionAuthorityError,
    AcquisitionSourceMeasureScope,
    build_authority_entry,
)
from polisyos.fabric.data_plane import content_sha256
from tests._helpers.acquisition_production import _entry, _resolver


def _put_selected_model_json(
    store: FileSystemCAS,
    value: BaseModel,
    *,
    kind: str,
    name: str,
) -> ArtifactRef:
    return store.put_json(
        value,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=name, version="1.0"),
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
        namespace="test.fiscal",
        stable_id="balance",
        revision="r1",
        meaning="Government fiscal balance measured for a bounded population and period.",
        definition_evidence_refs=(evidence_ref,),
    )
    definition_ref = _put_semantic_definition(store, definition)

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
    )
    representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            representation,
            PutOptions(
                kind=representation.ARTIFACT_KIND,
                media_type=representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=representation.ARTIFACT_SCHEMA_NAME,
                    version=representation.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[input_ref_from_artifact_ref(definition_ref, role="semantic_definition")],
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )

    model_representation = representation.model_copy(
        update={
            "representation_id": "test.fiscal.balance.model",
            "quantity_kind": "stock",
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
                    version=model_representation.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[input_ref_from_artifact_ref(definition_ref, role="semantic_definition")],
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
    )
    profile_ref = MeasurementBindingProfileRef.model_validate(
        _put_selected_model_json(
            store,
            profile,
            kind=profile.ARTIFACT_KIND,
            name=profile.ARTIFACT_SCHEMA_NAME,
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

    with pytest.raises(
        AcquisitionAuthorityError,
        match="model_input_source_descriptor_incompatible",
    ):
        authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id="fiscal-balance-input",
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
