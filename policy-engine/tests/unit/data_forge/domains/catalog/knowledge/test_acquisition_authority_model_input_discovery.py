from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
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
from polisyos.data_forge.domains.catalog.knowledge import acquisition_authority as authority_module
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionAuthorityEntry,
    AcquisitionAuthorityError,
    AcquisitionAuthorityRegistry,
    AcquisitionSourceMeasureScope,
    AuthoritySchemaColumn,
    CanonicalAcquisitionAuthority,
    _AuthoritySemanticDefinitionIndex,
    build_acquisition_authority_provision,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.fabric.connectors.contracts import (
    SchemaType,
    SourceContract,
    SourceContractSemantics,
    SourceMetricDefinition,
    build_contract_registry,
    create_source_metric_unit_declaration,
)
from polisyos.fabric.connectors.sources._contracts import WDI_GENERIC_CONTRACT
from polisyos.fabric.data_plane import content_sha256
from tests._helpers.acquisition_production import (
    _baseline,
    _entry,
    _resolver,
    _sha,
    _write_l5,
    _write_provision,
)


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
    unit_id: str = "usd",
    source_quantity_kind: str = "stock",
    target_quantity_kind: str = "stock",
    definition_namespace: str = "test.fiscal",
    definition_stable_id: str = "balance",
    definition_revision: str = "r1",
    definition_meaning: str = (
        "Government fiscal balance measured for a bounded population and period."
    ),
    representation_id_prefix: str = "test.fiscal.balance",
    profile_id: str = "test.fiscal.balance",
    port_id: str = "fiscal-balance-input",
    slot_id: str = "fiscal_balance",
    state_path: str = "government.balance",
    population_ref: str = "population:whole-country",
    geography_ref: str = "UKR",
    jurisdiction_ref: str = "UKR",
    period_start: date = date(2024, 1, 1),
    period_end: date = date(2024, 12, 31),
    period_basis: str = "calendar_year",
    time_support: str = "period_average",
    temporal_granularity: str = "annual",
    measure_form: str = "absolute",
    aggregation: str = "mean",
    grain: tuple[str, ...] = ("country", "period"),
    physical_shape: tuple[int, ...] = (1,),
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
        stable_id=definition_stable_id,
        revision=definition_revision,
        meaning=definition_meaning,
        definition_evidence_refs=(evidence_ref,),
    )
    definition_ref = _put_semantic_definition(store, definition)

    uses_v2_representation = (
        source_methodology_ref is not None or target_methodology_ref is not None
    )
    representation = VariableRepresentation(
        representation_id=f"{representation_id_prefix}.source",
        revision="r1",
        semantic_definition_ref=definition_ref,
        quantity_kind=source_quantity_kind,
        measure_form=measure_form,
        unit_id=unit_id,
        scale_to_unit=Decimal("1"),
        time_support=time_support,
        temporal_granularity=temporal_granularity,
        aggregation=aggregation,
        grain=grain,
        population_ref=population_ref,
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
            "representation_id": f"{representation_id_prefix}.model",
            "quantity_kind": target_quantity_kind,
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
        profile_id=profile_id,
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
                port_id=port_id,
                slot_id=slot_id,
                state_path=state_path,
                unit_id=unit_id,
                purpose="simulation_input",
                semantic_definition_ref=definition_ref,
                representation_ref=model_representation_ref,
                binding_profile_ref=profile_ref,
                scope=ModelInputScope(
                    population_ref=population_ref,
                    geography_ref=geography_ref,
                    jurisdiction_ref=jurisdiction_ref,
                    period_start=period_start,
                    period_end=period_end,
                    time_role="observation_time",
                    period_basis=period_basis,
                ),
                physical_encoding=ModelInputPhysicalEncoding(
                    shape=physical_shape,
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
    dataset_prefix: str = "fiscal_balance",
    unit_id: str = "usd",
    population: str = "population:whole-country",
    temporal_granularity: str = "annual",
    jurisdiction_ref: str | None = None,
    geography_ref: str | None = None,
    time_period_basis: str | None = None,
    temporal_start: str | None = None,
    temporal_end: str | None = None,
) -> AcquisitionAuthorityEntry:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    source_scope = {
        "population": population,
        "temporal_granularity": temporal_granularity,
    }
    if jurisdiction_ref is not None:
        source_scope["jurisdiction_ref"] = jurisdiction_ref
    if geography_ref is not None:
        source_scope["geography_ref"] = geography_ref
    if time_period_basis is not None:
        source_scope["time_period_basis"] = time_period_basis
    values.update(
        {
            "raw_unit": unit_id,
            "canonical_unit": unit_id,
            "landing_dataset_id": f"acquisition.test.{dataset_prefix}.{suffix}",
            "landing_distribution_id": (f"acquisition.test.{dataset_prefix}.{suffix}.json"),
            "source_measure_scope": AcquisitionSourceMeasureScope(**source_scope),
            "source_semantic_definition_ref": definition_ref,
            "source_representation_ref": representation_ref,
        }
    )
    if temporal_start is not None:
        values["temporal_start"] = temporal_start
    if temporal_end is not None:
        values["temporal_end"] = temporal_end
    return build_authority_entry(**values)


def _p07_metadata_entry(
    definition_ref: VariableSemanticDefinitionRef,
    representation_ref: VariableRepresentationRef,
    metadata: dict[str, str],
) -> AcquisitionAuthorityEntry:
    """Bind a synthetic source descriptor to its own typed Catalog metadata."""
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    raw_field = metadata["raw_field"]
    logical_type = metadata["logical_type"]
    if metadata.get("schema_contract_ref") == "fabric://worldbank.wdi.generic@2.0.0":
        logical_types = {
            SchemaType.STRING: "string",
            SchemaType.CATEGORY: "string",
            SchemaType.INT8: "integer",
            SchemaType.INT16: "integer",
            SchemaType.INT32: "integer",
            SchemaType.INT64: "integer",
            SchemaType.UINT8: "integer",
            SchemaType.UINT16: "integer",
            SchemaType.UINT32: "integer",
            SchemaType.UINT64: "integer",
            SchemaType.FLOAT16: "number",
            SchemaType.FLOAT32: "number",
            SchemaType.FLOAT64: "number",
            SchemaType.DECIMAL: "number",
            SchemaType.BOOLEAN: "boolean",
            SchemaType.DATE: "date",
            SchemaType.DATETIME: "datetime",
            SchemaType.TIMESTAMP_TZ: "datetime",
            SchemaType.TIME: "time",
            SchemaType.DURATION: "duration",
            SchemaType.ARRAY: "array",
            SchemaType.JSON: "json",
            SchemaType.BINARY: "binary",
        }
        schema_columns = tuple(
            sorted(
                (
                    AuthoritySchemaColumn(
                        name=field.name,
                        logical_types=tuple(
                            sorted(
                                {"null", logical_types[field.data_type]}
                                if field.nullable
                                else {logical_types[field.data_type]}
                            )
                        ),
                        nullable=field.nullable,
                    )
                    for field in WDI_GENERIC_CONTRACT.schema.fields
                ),
                key=lambda column: column.name,
            )
        )
        assert logical_types[WDI_GENERIC_CONTRACT.schema.get_field(raw_field).data_type] == (
            logical_type
        )
    else:
        schema_columns = tuple(
            sorted(
                (
                    AuthoritySchemaColumn(
                        name="country_code",
                        logical_types=("string",),
                        nullable=False,
                    ),
                    AuthoritySchemaColumn(
                        name="year",
                        logical_types=("integer",),
                        nullable=False,
                    ),
                    AuthoritySchemaColumn(
                        name=raw_field,
                        logical_types=(logical_type,),
                        nullable=False,
                    ),
                ),
                key=lambda column: column.name,
            )
        )
    values.update(
        {
            "target_variable": metadata["target_variable"],
            "landing_dataset_id": f"acquisition.test.p07.{metadata['slug']}",
            "landing_distribution_id": f"acquisition.test.p07.{metadata['slug']}.json",
            "source_catalog_dataset_id": metadata["dataset_id"],
            "source_catalog_distribution_id": metadata["distribution_id"],
            "upstream_metric_id": metadata["metric_id"],
            "catalog_raw_variable": metadata["request_dataset_id"],
            "raw_field": raw_field,
            "raw_unit": metadata["unit_id"],
            "canonical_unit": metadata["unit_id"],
            "unit_transform": "identity",
            "unit_transform_ref": f"fabric://units/{metadata['unit_id']}-identity/v1",
            "alignment_method": "meta_analytic",
            "alignment_confidence": 0.8,
            "is_proxy": False,
            "proxy_penalty": 0.0,
            "evidence_refs": ("fixture://p07/metadata-only",),
            "schema_contract_ref": metadata.get(
                "schema_contract_ref",
                f"fixture://p07/{metadata['slug']}@1.0.0",
            ),
            "schema_columns": schema_columns,
            "l5_family_id": "p07_metadata_only",
            "source_provenance_class": None,
            "source_measure_scope": AcquisitionSourceMeasureScope(
                population=metadata["population_ref"],
                temporal_granularity="annual",
                jurisdiction_ref="UKR",
                time_period_basis="calendar_year",
                source_geography_id="UKR",
                geography_ref="UKR",
            ),
            "source_semantic_definition_ref": definition_ref,
            "source_representation_ref": representation_ref,
            "title": metadata["title"],
            "description": metadata["description"],
            "country_codes": ("UKR",),
            "temporal_start": "2020",
            "temporal_end": "2024",
        }
    )
    return build_authority_entry(**values)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            {
                "namespace": "public.health",
                "stable_id": "annual_visits",
                "meaning": "Annual count of outpatient visits in the declared population.",
                "unit_id": "count",
                "quantity_kind": "count",
                "state_path": "public.health.annual_visits",
                "population_ref": "population:residents",
                "port_id": "health-visits-input",
                "slot_id": "annual_visits",
                "time_support": "period_total",
                "aggregation": "sum",
                "slug": "health-annual-visits",
                "target_variable": "health.annual_outpatient_visits",
                "dataset_id": "fixture-health-annual-visits",
                "distribution_id": "fixture-health-annual-visits-metadata",
                "metric_id": "health_annual_outpatient_visits",
                "request_dataset_id": "annual_outpatient_visits_count",
                "source_locator": "fixture://p07/health/annual-visits-metadata-only",
                "raw_field": "value",
                "logical_type": "number",
                "schema_contract_ref": "fabric://worldbank.wdi.generic@2.0.0",
                "connector_id": "worldbank.wdi",
                "profile_id": "worldbank_wdi",
                "title": "Annual outpatient visit count",
                "description": "Test-owned metadata only; contains no source observations.",
                "expected_resolution_error": "catalog_unit_unresolved",
            },
            id="health-count",
        ),
        pytest.param(
            {
                "namespace": "public.transport",
                "stable_id": "annual_fare_revenue",
                "meaning": "Annual fare revenue collected by the declared transit system.",
                "unit_id": "usd",
                "quantity_kind": "flow",
                "state_path": "transport.accumulated_fare_revenue",
                "population_ref": "population:transit-riders",
                "port_id": "transport-fare-revenue-input",
                "slot_id": "annual_fare_revenue",
                "time_support": "period_total",
                "aggregation": "sum",
                "slug": "transport-annual-fare-revenue",
                "target_variable": "transport.annual_fare_revenue",
                "dataset_id": "fixture-transport-annual-fare-revenue",
                "distribution_id": "fixture-transport-annual-fare-revenue-metadata",
                "metric_id": "transport_annual_fare_revenue",
                "request_dataset_id": "annual_fare_revenue_current_usd",
                "source_locator": "fixture://p07/transport/annual-fare-revenue-metadata-only",
                "raw_field": "annual_fare_revenue_current_usd",
                "logical_type": "number",
                "title": "Annual transit fare revenue (current USD)",
                "description": "Test-owned metadata only; contains no source observations.",
                "expected_resolution_error": "",
            },
            id="transport-usd-flow",
        ),
    ],
)
def test_indexed_semantic_lookup_preserves_held_out_domain_candidates_and_fresh_reader(
    tmp_path: Path,
    case: dict[str, str],
) -> None:
    """Exact Catalog indexing narrows candidates without granting semantic authority."""
    store = FileSystemCAS(tmp_path / "cas")
    domain_namespace = case["namespace"]
    stable_id = case["stable_id"]
    unit_id = case["unit_id"]
    population_ref = case["population_ref"]
    port_id = case["port_id"]
    quantity_kind = case["quantity_kind"]
    model_inputs: dict[str, object] = {
        "unit_id": unit_id,
        "source_quantity_kind": quantity_kind,
        "target_quantity_kind": quantity_kind,
        "definition_namespace": domain_namespace,
        "definition_stable_id": stable_id,
        "definition_meaning": case["meaning"],
        "representation_id_prefix": f"{domain_namespace}.{stable_id}",
        "profile_id": f"{domain_namespace}.{stable_id}",
        "port_id": port_id,
        "slot_id": case["slot_id"],
        "state_path": case["state_path"],
        "population_ref": population_ref,
        "period_basis": "calendar_year",
        "time_support": case["time_support"],
        "temporal_granularity": "annual",
        "measure_form": "count" if quantity_kind == "count" else "absolute",
        "aggregation": case["aggregation"],
        "grain": ("population", "period"),
        "physical_shape": (),
    }
    definition_ref, representation_ref, _, interface_ref = _model_inputs(store, **model_inputs)
    # A same-label row with a different definition is not an exact candidate.
    # Local source labels are unrelated to the selected definition: lookup is
    # by exact selected reference, not a label or prose similarity.
    wrong_meaning_inputs = {
        **model_inputs,
        "definition_revision": "r2",
        "definition_meaning": f"{case['meaning']} This is a distinct, non-equivalent definition.",
        "representation_id_prefix": f"{domain_namespace}.{stable_id}.wrong-meaning",
        "profile_id": f"{domain_namespace}.{stable_id}.wrong-meaning",
    }
    same_label_wrong_meaning_ref, same_label_wrong_meaning_representation, _, _ = _model_inputs(
        store,
        **wrong_meaning_inputs,
    )
    same_wording_other_definition_inputs = {
        **model_inputs,
        "definition_stable_id": f"{stable_id}_alternate_label",
        "representation_id_prefix": f"{domain_namespace}.{stable_id}.alternate-label",
        "profile_id": f"{domain_namespace}.{stable_id}.alternate-label",
    }
    same_wording_other_definition_ref, same_wording_other_definition_representation, _, _ = (
        _model_inputs(store, **same_wording_other_definition_inputs)
    )

    selected = _p07_metadata_entry(definition_ref, representation_ref, case)
    wrong_meaning = _p07_metadata_entry(
        same_label_wrong_meaning_ref,
        same_label_wrong_meaning_representation,
        {**case, "slug": f"{case['slug']}-wrong-meaning"},
    )
    same_wording_other_definition = _p07_metadata_entry(
        same_wording_other_definition_ref,
        same_wording_other_definition_representation,
        {**case, "slug": f"{case['slug']}-other-definition"},
    )
    source_row = {
        key: case[key]
        for key in (
            "dataset_id",
            "distribution_id",
            "metric_id",
            "request_dataset_id",
            "source_locator",
            "title",
            "description",
        )
    }
    source_row.update({key: case[key] for key in ("connector_id", "profile_id") if key in case})
    authority = _p07_fixture_authority(
        tmp_path / "catalog-owner",
        (selected, wrong_meaning, same_wording_other_definition),
        (source_row,),
    )
    for ordered_entries in (
        (wrong_meaning, same_wording_other_definition, selected),
        (selected, same_wording_other_definition, wrong_meaning),
    ):
        _replace_authority_registry(authority, ordered_entries)
        candidate = authority.discover_model_input_source_descriptor(
            store,
            model_input_interface_ref=interface_ref,
            port_id=port_id,
            include_query_envelope=True,
        )
        assert candidate.authority_entry_id == selected.entry_id
        assert candidate.source_semantic_definition_ref == definition_ref
        assert candidate.semantic_correspondence == "not_established"
        assert candidate.may_not_use_for == (
            "measurement_admission",
            "fetch_permission",
            "claim_evidence",
            "source_currentness",
        )
        assert candidate.query_envelope is not None
        assert {row.entry_id for row in candidate.query_envelope.rows} == {selected.entry_id}

    registry = authority._load_registry()
    indexed = authority._source_entries_for_semantic_definition(
        registry,
        artifact_ref_identity_key(definition_ref),
    )
    target_key = artifact_ref_identity_key(definition_ref)
    exhaustive_ids: set[str] = set()
    for entry in registry.entries:
        source_definition_ref = entry.source_semantic_definition_ref
        source_representation_ref = entry.source_representation_ref
        assert source_definition_ref is not None
        assert source_representation_ref is not None
        loaded_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition,
            store,
            source_definition_ref,
        )
        loaded_representation = load_variable_representation(store, source_representation_ref)
        assert loaded_representation.semantic_definition_ref == source_definition_ref
        assert tuple(store.get_manifest(source_representation_ref).inputs) == (
            *variable_representation_manifest_inputs(loaded_representation),
        )
        if artifact_ref_identity_key(source_definition_ref) == target_key:
            exhaustive_ids.add(entry.entry_id)
        else:
            assert loaded_definition != validate_core_model_json_artifact(
                VariableSemanticDefinition, store, definition_ref
            )
    assert exhaustive_ids == {selected.entry_id}
    assert {entry.entry_id for entry in indexed} == exhaustive_ids
    assert indexed == (selected,)
    assert authority._semantic_definition_index_cache is not None
    assert authority._semantic_definition_index_cache.is_complete
    assert authority._semantic_definition_index_cache.eligible_entry_count == 3

    fresh_store = FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    fresh_candidate = authority.discover_model_input_source_descriptor(
        fresh_store,
        model_input_interface_ref=interface_ref,
        port_id=port_id,
        include_query_envelope=True,
    )
    assert fresh_candidate == candidate
    if case["expected_resolution_error"]:
        with pytest.raises(AcquisitionAuthorityError) as resolution_error:
            authority.resolve(selected.entry_id)
        assert resolution_error.value.code == case["expected_resolution_error"]
        if case["namespace"] == "public.health":
            adopted_authority, adopted_entry, unit_ref = _adopt_p07_test_source_unit(
                authority,
                (selected, wrong_meaning, same_wording_other_definition),
                selected,
                store,
            )
            assert adopted_entry.source_unit_declaration_ref == unit_ref
            assert adopted_entry.source_semantic_definition_ref == definition_ref
            assert wrong_meaning.source_semantic_definition_ref != definition_ref
            assert wrong_meaning.raw_unit == adopted_entry.raw_unit == "count"

            adopted_reader = FileSystemCAS.open_existing_read_only(tmp_path / "cas")
            adopted_candidate = adopted_authority.discover_model_input_source_descriptor(
                adopted_reader,
                model_input_interface_ref=interface_ref,
                port_id=port_id,
                include_query_envelope=True,
            )
            assert adopted_candidate.authority_entry_id == adopted_entry.entry_id
            assert adopted_candidate.source_semantic_definition_ref == definition_ref
            assert adopted_candidate.semantic_correspondence == "not_established"
            assert adopted_candidate.query_envelope is not None
            assert {row.entry_id for row in adopted_candidate.query_envelope.rows} == {
                adopted_entry.entry_id
            }

            resolved = adopted_authority.resolve(adopted_entry.entry_id)
            assert resolved.entry.source_unit_declaration_ref == unit_ref
            assert resolved.field_binding.raw_unit == "count"
            assert resolved.upstream_catalog_projection is not None
            unit_projection = resolved.upstream_catalog_projection["source_unit_declaration"]
            assert unit_projection["ref"] == unit_ref.model_dump(mode="json")
            assert unit_projection["unit_truth"] == "declared"
            assert unit_projection["semantic_authority"] == "not_established"
            assert unit_projection["source_currentness"] == "not_established"

            from polisyos.data_forge.read_api import catalog as catalog_read_api

            supplier_ref = catalog_read_api.persist_acquisition_supplier_declaration(
                store,
                adopted_authority,
                entry_id=adopted_entry.entry_id,
            )
            fresh_reader = FileSystemCAS.open_existing_read_only(tmp_path / "cas")
            historical = catalog_read_api.load_acquisition_supplier_declaration(
                fresh_reader,
                supplier_ref,
            )
            assert historical.entry.entry_id == adopted_entry.entry_id
            assert historical.entry.source_unit_declaration_ref == unit_ref
            assert historical.semantic_authority == "not_established"
            assert historical.acquisition_permission == "not_established"
            assert historical.source_unit_provision_ref is not None
            provision_bytes = fresh_reader.get_bytes(historical.source_unit_provision_ref)
            assert "sha256:" + hashlib.sha256(provision_bytes).hexdigest() == (
                historical.authority_provision_content_sha256
            )
    else:
        from polisyos.data_forge.read_api import catalog as catalog_read_api

        resolved = authority.resolve(selected.entry_id)
        assert resolved.entry.target_variable == case["target_variable"]
        assert resolved.upstream_catalog_projection is not None
        assert resolved.upstream_catalog_projection["catalog_unit"] == unit_id
        declaration_ref = catalog_read_api.persist_acquisition_supplier_declaration(
            store,
            authority,
            entry_id=selected.entry_id,
        )
        declaration = catalog_read_api.load_acquisition_supplier_declaration(
            FileSystemCAS.open_existing_read_only(tmp_path / "cas"),
            declaration_ref,
        )
        assert declaration.entry.entry_id == selected.entry_id
        assert declaration.semantic_authority == "not_established"
        assert declaration.acquisition_permission == "not_established"


def _supplier_declaration_entry(
    definition_ref: VariableSemanticDefinitionRef,
    representation_ref: VariableRepresentationRef,
    *,
    suffix: str,
) -> AcquisitionAuthorityEntry:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values.update(
        {
            "landing_dataset_id": f"acquisition.test.supplier_declaration.{suffix}",
            "landing_distribution_id": (f"acquisition.test.supplier_declaration.{suffix}.json"),
            "source_semantic_definition_ref": definition_ref,
            "source_representation_ref": representation_ref,
            "source_measure_scope": AcquisitionSourceMeasureScope(
                population="population:whole-country",
                temporal_granularity="annual",
            ),
        }
    )
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


def _adopt_p07_test_source_unit(
    authority: CanonicalAcquisitionAuthority,
    entries: tuple[AcquisitionAuthorityEntry, ...],
    selected: AcquisitionAuthorityEntry,
    store: FileSystemCAS,
) -> tuple[
    CanonicalAcquisitionAuthority,
    AcquisitionAuthorityEntry,
    ArtifactRef,
]:
    """Adopt a test-owned count declaration through actual Fabric/Catalog owners."""
    contracts = build_contract_registry((WDI_GENERIC_CONTRACT,))
    source = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        profile_id="worldbank_wdi",
    )
    source = source.model_copy(
        update={
            "semantics": SourceContractSemantics(
                domain=source.semantics.domain,
                metric_definitions=(
                    SourceMetricDefinition(
                        metric_id=selected.catalog_raw_variable,
                        unit="count",
                        canonical_field="value",
                    ),
                ),
            )
        }
    )
    unit_ref = create_source_metric_unit_declaration(
        store,
        source_contract=source,
        contract_registry=contracts,
        connector_contract_id=WDI_GENERIC_CONTRACT.contract_id,
        connector_contract_version=str(WDI_GENERIC_CONTRACT.schema_version),
        catalog_dataset_id=selected.source_catalog_dataset_id,
        catalog_distribution_id=selected.source_catalog_distribution_id,
        catalog_metric_id=selected.upstream_metric_id,
        request_dataset_id=selected.catalog_raw_variable,
        source_metric_id=selected.catalog_raw_variable,
        raw_field="value",
        normalized_field="value",
        metric_selector_field="indicator_id",
        reported_unit_field="unit",
    )
    adopted = build_authority_entry(
        **{
            **selected.model_dump(mode="python", exclude={"entry_id"}),
            "source_unit_declaration_ref": unit_ref,
        }
    )
    adopted_entries = tuple(
        adopted if entry.entry_id == selected.entry_id else entry for entry in entries
    )
    _replace_authority_registry(authority, adopted_entries)

    provision_values = authority.provision.identity_payload()
    provision_values.pop("authority_purpose")
    provision = build_acquisition_authority_provision(
        **provision_values,
        source_unit_declaration_refs=(unit_ref,),
        source_unit_reader=store,
    )
    provision_path = authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
    provision_path.write_text(provision.model_dump_json(), encoding="utf-8")
    current = CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority.repo_root,
        baseline_path=authority.baseline_path,
        source_unit_reader=store,
        source_unit_contract_registry=contracts,
    )
    return current, adopted, unit_ref


def _p07_fixture_authority(
    repo_root: Path,
    entries: tuple[AcquisitionAuthorityEntry, ...],
    source_rows: tuple[dict[str, object], ...],
) -> CanonicalAcquisitionAuthority:
    """Build test-owned Catalog/L5 metadata and provision only after bytes are final."""
    baseline = _baseline(repo_root)
    con = duckdb.connect(str(baseline))
    try:
        for row in source_rows:
            connector_id = row.get("connector_id", "test.fixture")
            profile_id = row.get("profile_id", "p07_metadata_only")
            con.execute(
                """
                INSERT INTO ds_datasets (
                    id, source, agency, title, description, access_license,
                    execution_tier, polisyos_metrics, preferred_distribution_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["dataset_id"],
                    "test_fixture",
                    "PolicyOS P07 test fixture",
                    row["title"],
                    row["description"],
                    "CC-BY-4.0",
                    "transport_ready",
                    [row["metric_id"]],
                    row["distribution_id"],
                ],
            )
            con.execute(
                """
                INSERT INTO ds_distributions (
                    id, dataset_id, connector_type, profile_id, source_locator,
                    parser_supported, machine_readable, quality_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["distribution_id"],
                    row["dataset_id"],
                    connector_id,
                    profile_id,
                    row["source_locator"],
                    True,
                    True,
                    0.9,
                ],
            )
            con.execute(
                """
                INSERT INTO ds_metric_bindings (
                    metric_id, dataset_id, distribution_id, connector_id, profile_id,
                    request_dataset_id, confidence, metric_inference_confidence,
                    default_filters, execution_tier, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["metric_id"],
                    row["dataset_id"],
                    row["distribution_id"],
                    connector_id,
                    profile_id,
                    row["request_dataset_id"],
                    0.9,
                    0.9,
                    "{}",
                    "transport_ready",
                    "test_fixture",
                ],
            )
            con.execute(
                """
                INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["dataset_id"],
                    row["request_dataset_id"],
                    row["metric_id"],
                    "meta_analytic",
                    0.9,
                    "Synthetic metadata-only P07 alignment; no source observations.",
                    False,
                    0.0,
                ],
            )
    finally:
        con.close()

    l5_path = _write_l5(repo_root)
    l5_payload = json.loads(l5_path.read_text(encoding="utf-8"))
    l5_payload["coverage_rules"]["p07_metadata_only"] = 0.95
    l5_path.write_text(
        json.dumps(l5_payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5_path),
        entries=entries,
    )
    registry_path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    _write_provision(
        repo_root,
        baseline=baseline,
        l5_path=l5_path,
        baseline_owner_ref="repo://catalog/catalog.duckdb",
    )
    return CanonicalAcquisitionAuthority.from_provision(
        repo_root=repo_root,
        baseline_path=baseline,
    )


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


def test_catalog_supplier_declaration_replays_selected_owner_refs_and_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist a real authority resolution without promoting it to permission."""
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from tests._helpers import acquisition_production

    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, interface_ref = _model_inputs(
        store, unit_id="percent_gdp", period_start=date(2022, 1, 1), period_end=date(2022, 12, 31)
    )
    entry = _supplier_declaration_entry(
        definition_ref,
        representation_ref,
        suffix="supplier-declaration",
    )

    def baseline_with_observation(repo_root: Path, *, license_id: str) -> Path:
        baseline = _baseline(repo_root, license_id=license_id)
        with duckdb.connect(str(baseline)) as connection:
            connection.execute(
                """
                INSERT INTO ds_observations (
                    observation_id, dataset_id, raw_variable, canonical_var,
                    country_code, year, value
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "fixture-observation-ukr-2022",
                    entry.source_catalog_dataset_id,
                    entry.catalog_raw_variable,
                    entry.upstream_metric_id,
                    "UKR",
                    2022,
                    -0.175,
                ],
            )
        return baseline

    with monkeypatch.context() as context:
        # Seed the real fixture relation before the resolver hashes its baseline.
        context.setattr(acquisition_production, "_baseline", baseline_with_observation)
        authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=entry)
    resolved = authority.resolve(entry.entry_id)
    reader = catalog_read_api.DatasetCatalogStore(
        authority.baseline_path, authority.baseline_path.parent
    )
    try:
        assert reader.database_identity.content_sha256 == resolved.baseline_content_sha256
        assert reader.variable_availability_counts(entry.upstream_metric_id) == (1, 1, 1)
        (binding,) = reader.reconciled_metric_binding_population(entry.upstream_metric_id)
        assert (binding.metric_id, binding.catalog_dataset_id, binding.distribution_id) == (
            entry.upstream_metric_id,
            entry.source_catalog_dataset_id,
            entry.source_catalog_distribution_id,
        )
    finally:
        reader.close()

    declaration_ref = catalog_read_api.persist_acquisition_supplier_declaration(
        store,
        authority,
        entry_id=entry.entry_id,
    )
    declaration = catalog_read_api.load_acquisition_supplier_declaration(
        store,
        declaration_ref,
    )

    assert declaration.entry == resolved.entry
    assert declaration.entry.target_variable == entry.target_variable
    assert declaration.entry.source_semantic_definition_ref == definition_ref
    assert declaration.entry.source_representation_ref == representation_ref
    assert declaration.entry.source_measure_scope == entry.source_measure_scope
    assert declaration.connector_id == resolved.registration.connector_id
    assert declaration.authority_provision_id == resolved.authority_provision_id
    assert (
        declaration.authority_provision_content_sha256
        == resolved.authority_provision_content_sha256
    )
    assert declaration.registry_content_sha256 == resolved.registry_content_sha256
    assert declaration.baseline_content_sha256 == resolved.baseline_content_sha256
    assert (
        declaration.upstream_catalog_projection_sha256
        == resolved.upstream_catalog_projection_sha256
    )
    assert declaration.l5_owner_content_sha256 == resolved.l5_trust.owner_content_sha256
    assert declaration.semantic_refs_status == "declared"
    assert declaration.source_scope_status == "declared"
    assert declaration.semantic_authority == "not_established"
    assert declaration.acquisition_permission == "not_established"
    assert declaration.source_currentness == "not_established"
    assert "effective_authority_score" not in declaration.model_dump(mode="json")
    assert "license_disposition" not in declaration.model_dump(mode="json")

    manifest = store.get_manifest(declaration_ref)
    assert {item.role for item in manifest.inputs} == {
        "source_semantic_definition",
        "source_representation",
    }
    assert declaration_ref.manifest_profile_sha256 is not None
    fresh_store = FileSystemCAS(store.root)
    assert (
        catalog_read_api.load_acquisition_supplier_declaration(
            fresh_store,
            declaration_ref,
        )
        == declaration
    )

    interface = load_program_graph_input_interface(fresh_store, interface_ref)
    (port,) = interface.ports
    matching_scope = port.scope
    assert (
        catalog_read_api.acquisition_supplier_declaration_scope_refusal(
            fresh_store,
            declaration_ref,
            scope=matching_scope,
        )
        is None
    )
    foreign_geography = matching_scope.model_copy(
        update={"geography_ref": "CAN", "jurisdiction_ref": "CAN"}
    )
    assert (
        catalog_read_api.acquisition_supplier_declaration_scope_refusal(
            fresh_store,
            declaration_ref,
            scope=foreign_geography,
        )
        == "source_geography_scope_mismatch"
    )
    outside_declared_period = matching_scope.model_copy(
        update={
            "period_start": date(2025, 1, 1),
            "period_end": date(2025, 12, 31),
        }
    )
    assert (
        catalog_read_api.acquisition_supplier_declaration_scope_refusal(
            fresh_store,
            declaration_ref,
            scope=outside_declared_period,
        )
        == "source_temporal_scope_mismatch"
    )

    candidate = authority.discover_model_input_source_descriptor(
        fresh_store,
        model_input_interface_ref=interface_ref,
        port_id=port.port_id,
        include_query_envelope=True,
    )
    assert candidate.authority_entry_id == declaration.entry.entry_id
    assert candidate.semantic_correspondence == "not_established"
    assert candidate.query_envelope is not None
    (matching_row,) = candidate.query_envelope.rows
    assert matching_row.entry_id == entry.entry_id and matching_row.disposition == "compatible"

    for bad_scope, reason in (
        (foreign_geography, "source_geography_scope_mismatch"),
        (outside_declared_period, "source_temporal_scope_mismatch"),
    ):
        wrong_interface_ref = persist_program_graph_input_interface(
            store,
            interface.model_copy(update={"ports": (port.model_copy(update={"scope": bad_scope}),)}),
        )
        with pytest.raises(AcquisitionAuthorityError) as refused:
            authority.discover_model_input_source_descriptor(
                fresh_store,
                model_input_interface_ref=wrong_interface_ref,
                port_id=port.port_id,
                include_query_envelope=True,
            )
        assert refused.value.code == "model_input_source_descriptor_incompatible"
        envelope = refused.value.query_envelope
        assert envelope is not None
        assert (
            envelope.model_input_interface_ref,
            envelope.model_input_port_id,
            envelope.scope,
        ) == (wrong_interface_ref, port.port_id, bad_scope)
        (row,) = envelope.rows
        assert (row.entry_id, row.disposition, row.reason_codes) == (
            entry.entry_id,
            "incompatible",
            (reason,),
        )

    annual_representation = load_variable_representation(store, representation_ref)
    wrong_unit_representation = annual_representation.model_copy(
        update={
            "representation_id": "test.fiscal.balance.wrong-canonical-unit",
            "unit_id": "usd",
        }
    )
    wrong_unit_representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            wrong_unit_representation,
            PutOptions(
                kind=wrong_unit_representation.ARTIFACT_KIND,
                media_type=wrong_unit_representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=wrong_unit_representation.ARTIFACT_SCHEMA_NAME,
                    version="1.0",
                ),
                inputs=list(variable_representation_manifest_inputs(wrong_unit_representation)),
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )
    wrong_unit_entry = _supplier_declaration_entry(
        definition_ref,
        wrong_unit_representation_ref,
        suffix="wrong-canonical-unit",
    )
    wrong_unit_authority, _ = _resolver(
        tmp_path / "wrong-unit-catalog-owner",
        authority_entry=wrong_unit_entry,
    )
    wrong_unit_declaration_ref = catalog_read_api.persist_acquisition_supplier_declaration(
        store,
        wrong_unit_authority,
        entry_id=wrong_unit_entry.entry_id,
    )
    assert (
        catalog_read_api.acquisition_supplier_declaration_scope_refusal(
            fresh_store,
            wrong_unit_declaration_ref,
            scope=matching_scope,
        )
        == "source_descriptor_definition_or_unit_mismatch"
    )

    quarterly_representation = annual_representation.model_copy(
        update={
            "representation_id": "test.fiscal.balance.quarterly-source",
            "temporal_granularity": "quarterly",
        }
    )
    quarterly_representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            quarterly_representation,
            PutOptions(
                kind=quarterly_representation.ARTIFACT_KIND,
                media_type=quarterly_representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=quarterly_representation.ARTIFACT_SCHEMA_NAME,
                    version="1.0",
                ),
                inputs=list(variable_representation_manifest_inputs(quarterly_representation)),
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )
    quarterly_entry = _supplier_declaration_entry(
        definition_ref,
        quarterly_representation_ref,
        suffix="quarterly-supplier",
    )
    quarterly_authority, _ = _resolver(
        tmp_path / "quarterly-catalog-owner",
        authority_entry=quarterly_entry,
    )
    quarterly_declaration_ref = catalog_read_api.persist_acquisition_supplier_declaration(
        store,
        quarterly_authority,
        entry_id=quarterly_entry.entry_id,
    )
    assert (
        catalog_read_api.acquisition_supplier_declaration_scope_refusal(
            fresh_store,
            quarterly_declaration_ref,
            scope=matching_scope,
        )
        == "source_temporal_granularity_unresolved"
    )

    foreign_definition_ref, foreign_representation_ref, _, _ = _model_inputs(
        store,
        definition_namespace="test.foreign.fiscal",
    )
    forged_entry = entry.model_dump(mode="json")
    forged_entry["source_semantic_definition_ref"] = foreign_definition_ref.model_dump(mode="json")
    forged_entry["source_representation_ref"] = foreign_representation_ref.model_dump(mode="json")
    with pytest.raises(ValidationError, match="authority entry identity must be recomputed"):
        AcquisitionAuthorityEntry.model_validate(forged_entry)

    removed_ref = representation_ref
    actual_get_bytes = fresh_store.get_bytes

    def get_bytes_without_representation(ref):
        if isinstance(ref, ArtifactRef) and artifact_ref_identity_key(
            ref
        ) == artifact_ref_identity_key(removed_ref):
            raise FileNotFoundError("test removed the selected source representation")
        return actual_get_bytes(ref)

    with monkeypatch.context() as context:
        context.setattr(fresh_store, "get_bytes", get_bytes_without_representation)
        with pytest.raises(
            AcquisitionAuthorityError,
            match="supplier_declaration_source_artifact_unavailable",
        ):
            catalog_read_api.load_acquisition_supplier_declaration(
                fresh_store,
                declaration_ref,
            )


def test_catalog_supplier_declaration_keeps_missing_semantics_not_established(
    tmp_path: Path,
) -> None:
    """A real unresolved registry row remains candidate-only with explicit unknowns."""
    from polisyos.data_forge.read_api import catalog as catalog_read_api

    store = FileSystemCAS(tmp_path / "cas")
    entry = _entry()
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=entry)
    declaration_ref = catalog_read_api.persist_acquisition_supplier_declaration(
        store,
        authority,
        entry_id=entry.entry_id,
    )
    declaration = catalog_read_api.load_acquisition_supplier_declaration(
        store,
        declaration_ref,
    )

    assert declaration.entry.source_semantic_definition_ref is None
    assert declaration.entry.source_representation_ref is None
    assert declaration.entry.source_measure_scope is None
    assert declaration.semantic_refs_status == "not_established"
    assert declaration.source_scope_status == "not_established"
    assert (
        catalog_read_api.acquisition_supplier_declaration_scope_refusal(
            store,
            declaration_ref,
            scope=ModelInputScope(
                population_ref="population:whole-country",
                geography_ref="UKR",
                jurisdiction_ref="UKR",
                period_start=date(2022, 1, 1),
                period_end=date(2022, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
        )
        == "model_input_source_descriptor_ref_pair_missing"
    )


def test_exact_semantic_definition_index_is_snapshot_bound_and_reused(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, _ = _model_inputs(store)
    entry = _authority_entry(definition_ref, representation_ref)
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=entry)
    target_key = artifact_ref_identity_key(definition_ref)

    first_registry = authority._load_registry()
    first_entries = authority._source_entries_for_semantic_definition(
        first_registry,
        target_key,
    )
    first_index = authority._semantic_definition_index_cache
    second_registry = authority._load_registry()
    second_entries = authority._source_entries_for_semantic_definition(
        second_registry,
        target_key,
    )

    assert second_registry is first_registry
    assert first_entries == second_entries == (entry,)
    assert authority._semantic_definition_index_cache is first_index
    assert first_index is not None
    assert first_index.registry_content_sha256 == first_registry.content_sha256
    assert first_index.is_complete


def test_incomplete_semantic_definition_index_falls_back_to_exact_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, _ = _model_inputs(store)
    entry = _authority_entry(definition_ref, representation_ref)
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=entry)
    registry = authority._load_registry()
    incomplete = _AuthoritySemanticDefinitionIndex(
        registry_content_sha256=registry.content_sha256,
        entries_by_definition={},
        indexed_entry_count=0,
        eligible_entry_count=1,
    )
    monkeypatch.setattr(
        authority_module,
        "_build_authority_semantic_definition_index",
        lambda _: incomplete,
    )

    candidates = authority._source_entries_for_semantic_definition(
        registry,
        artifact_ref_identity_key(definition_ref),
    )

    assert not incomplete.is_complete
    assert candidates == (entry,)


def test_stale_semantic_definition_index_is_rebuilt_for_current_snapshot(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, _ = _model_inputs(store)
    entry = _authority_entry(definition_ref, representation_ref)
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=entry)
    registry = authority._load_registry()
    authority._semantic_definition_index_cache = _AuthoritySemanticDefinitionIndex(
        registry_content_sha256="0" * 64,
        entries_by_definition={},
        indexed_entry_count=0,
        eligible_entry_count=0,
    )

    candidates = authority._source_entries_for_semantic_definition(
        registry,
        artifact_ref_identity_key(definition_ref),
    )

    assert candidates == (entry,)
    assert authority._semantic_definition_index_cache is not None
    assert authority._semantic_definition_index_cache.registry_content_sha256 == (
        registry.content_sha256
    )


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
