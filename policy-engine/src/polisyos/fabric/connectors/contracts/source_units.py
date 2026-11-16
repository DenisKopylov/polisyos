"""Metric-scoped declared-unit snapshots over existing Fabric source contracts.

This owner binds physical declaration consistency only. Source adoption,
measurement meaning, rights and current use remain separate consumer checks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts
from polisyos.fabric.quality import ProcessingGuarantee
from polisyos.ir.kernel import UnitRef

from .contract import ConnectorSchemaContract
from .contract_registry import ContractRegistry
from .schema import SchemaType, normalize_unit_id
from .source_contract import (
    SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE,
    SOURCE_CONTRACT_SCHEMA_VERSION,
    SourceContract,
    SourceMetricDefinition,
)


class SourceMetricUnitDeclarationRef(artifacts.ArtifactRef):
    """Selected immutable bytes of a candidate source-unit declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["fabric.source_metric_unit_declaration"] = "fabric.source_metric_unit_declaration"
    media_type: Literal["application/json"] = "application/json"
    manifest_profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$", strict=True)


class SourceMetricUnitDeclaration(BaseModel):
    """Bind a declared physical unit to one metric and exact source selection.

    The retained contracts are declarations, not observed unit truth, source
    permission, or variable meaning. Current adoption belongs to the consuming
    source owner; immutable replay of this record establishes no current use.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ARTIFACT_KIND: ClassVar[str] = "fabric.source_metric_unit_declaration"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.fabric.SourceMetricUnitDeclaration"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.1"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "1.1")
    ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION: ClassVar[dict[str, tuple[str, ...]]] = {
        "1.1": ("source_contract_hash_profile",),
    }
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "fabric.source_metric_unit.v1",
        "1.1": "fabric.source_metric_unit.v1.1",
    }

    schema_version: Literal["fabric.source_metric_unit.v1", "fabric.source_metric_unit.v1.1"] = (
        "fabric.source_metric_unit.v1.1"
    )
    source_contract_hash_profile: Literal["fabric.source_contract.field_sets.v1"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    authority_purpose: Literal["candidate_source_unit_declaration_only"] = (
        "candidate_source_unit_declaration_only"
    )
    source_contract: SourceContract
    connector_contract: ConnectorSchemaContract
    source_contract_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    connector_contract_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schema_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_dataset_id: str = Field(min_length=1)
    catalog_distribution_id: str = Field(min_length=1)
    catalog_metric_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    source_metric_id: str = Field(min_length=1)
    raw_field: str = Field(min_length=1)
    normalized_field: str = Field(min_length=1)
    metric_selector_field: str = Field(min_length=1)
    reported_unit_field: str | None = Field(default=None, min_length=1)
    semantic_authority: Literal["not_established"] = "not_established"
    acquisition_permission: Literal["not_established"] = "not_established"
    source_currentness: Literal["not_established"] = "not_established"

    @field_validator("source_contract", mode="before")
    @classmethod
    def _reify_source_processing_guarantee(cls, value: object) -> object:
        """Restore the existing owner's Enum before its strict terminal check."""
        if not isinstance(value, Mapping):
            return value
        processing = value.get("processing")
        if not isinstance(processing, Mapping) or type(processing.get("guarantee")) is not str:
            return value
        # The processing owner serializes Enum values as strings. Reify that
        # exact closed Enum, without changing any owner predicate or scalar.
        return {
            **value,
            "processing": {
                **processing,
                "guarantee": ProcessingGuarantee(processing["guarantee"]),
            },
        }

    @property
    def hash_replay_limitation_codes(self) -> tuple[str, ...]:
        """Expose the old hash profile without changing any retained v1 bytes."""
        if self.schema_version == "fabric.source_metric_unit.v1":
            return ("source_contract_legacy_hash_portability_not_established",)
        return ()

    @property
    def metric_definition(self) -> SourceMetricDefinition:
        """Return the one explicitly selected source-native metric definition."""
        matches = tuple(
            metric
            for metric in self.source_contract.semantics.metric_definitions
            if metric.metric_id == self.source_metric_id
        )
        if len(matches) != 1:
            raise ValueError("source_unit_metric_definition_unresolved")
        return matches[0]

    @property
    def declared_unit(self) -> UnitRef:
        """Return a declared unit identifier without inferring measure meaning."""
        value = self.metric_definition.unit
        if value is None or not (unit_id := normalize_unit_id(value)):
            raise ValueError("source_unit_metric_unit_missing")
        return UnitRef(unit_id=unit_id)

    @model_validator(mode="after")
    def _selected_owners_and_scope_match(self) -> SourceMetricUnitDeclaration:
        import fnmatch

        source = self.source_contract
        contract = self.connector_contract
        schema = contract.schema
        if self.schema_version == "fabric.source_metric_unit.v1":
            if self.source_contract_hash_profile is not None:
                raise ValueError("source_unit_hash_profile_version_mismatch")
            source_hash = source.content_hash
        else:
            if self.source_contract_hash_profile != SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE:
                raise ValueError("source_unit_hash_profile_version_mismatch")
            source_hash = source.to_canonical_snapshot_record(
                hash_profile=self.source_contract_hash_profile
            )["content_hash"]
        if (
            source.schema_version != SOURCE_CONTRACT_SCHEMA_VERSION
            or source.status != "active"
            or source_hash != self.source_contract_content_hash
        ):
            raise ValueError("source_unit_source_contract_identity_mismatch")
        if contract.content_hash != self.connector_contract_content_hash:
            raise ValueError("source_unit_connector_contract_identity_mismatch")
        if schema.content_hash != self.schema_content_hash:
            raise ValueError("source_unit_full_schema_identity_mismatch")
        if (
            source.source.connector_id != contract.connector_id
            or not fnmatch.fnmatchcase(self.request_dataset_id, source.source.dataset_pattern)
            or not contract.matches_dataset(self.request_dataset_id)
            or source.schema_contract.schema_id != schema.schema_id
            or source.schema_contract.schema_version != str(schema.version)
            or source.schema_contract.fields != schema.fields
        ):
            raise ValueError("source_unit_source_schema_scope_mismatch")
        source_ref = source.schema_contract.schema_contract_ref
        if (
            not source_ref
            or not source_ref.partition("#")[0]
            or source_ref.partition("#")[2] != f"/contracts/{contract.contract_id}"
        ):
            raise ValueError("source_unit_source_connector_contract_mismatch")
        metric = self.metric_definition
        if self.source_metric_id != self.request_dataset_id:
            raise ValueError("source_unit_metric_request_mismatch")
        field = schema.get_field(self.normalized_field)
        selector = schema.get_field(self.metric_selector_field)
        if (
            field is None
            or not (
                (field.data_type.is_numeric() and field.data_type is not SchemaType.BOOLEAN)
                or field.data_type is SchemaType.DECIMAL
            )
            or metric.canonical_field != self.normalized_field
            or selector is None
            or selector.data_type is not SchemaType.STRING
            or self.normalized_field == self.metric_selector_field
        ):
            raise ValueError("source_unit_metric_field_scope_mismatch")
        mappings = tuple(
            mapping
            for mapping in contract.field_mappings
            if mapping.target_field == self.normalized_field
        )
        if (mappings and (len(mappings) != 1 or mappings[0].source_path != self.raw_field)) or (
            not mappings and self.raw_field != self.normalized_field
        ):
            raise ValueError("source_unit_raw_field_mapping_mismatch")
        if field.unit is not None and field.unit != self.declared_unit:
            raise ValueError("source_unit_field_metric_unit_mismatch")
        # Resolve the metric unit even when the shared long-form field has no
        # global unit. A missing declaration cannot borrow the caller's unit.
        _ = self.declared_unit
        selector_mappings = tuple(
            mapping
            for mapping in contract.field_mappings
            if mapping.target_field == self.metric_selector_field
        )
        if selector_mappings and (
            len(selector_mappings) != 1 or selector_mappings[0].transform is not None
        ):
            raise ValueError("source_unit_selector_mapping_unsupported")
        if self.reported_unit_field is not None:
            reported = schema.get_field(self.reported_unit_field)
            if (
                reported is None
                or reported.data_type is not SchemaType.STRING
                or self.reported_unit_field in {self.normalized_field, self.metric_selector_field}
            ):
                raise ValueError("source_unit_reported_unit_field_mismatch")
        return self

    def validate_raw_metric_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Require the actual raw selector, without a normalization fallback."""
        mappings = tuple(
            mapping
            for mapping in self.connector_contract.field_mappings
            if mapping.target_field == self.metric_selector_field
        )
        path = mappings[0].source_path if mappings else self.metric_selector_field
        for row in rows:
            value: object = row
            for part in path.split("."):
                if not isinstance(value, Mapping) or part not in value:
                    raise ValueError("source_unit_raw_metric_missing")
                value = value[part]
            if value != self.request_dataset_id:
                raise ValueError("source_unit_raw_metric_mismatch")

    def reported_units(self, rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
        """Reconcile the selected metric in every row and return explicit labels."""
        units: set[str] = set()
        for row in rows:
            if row.get(self.metric_selector_field) != self.request_dataset_id:
                raise ValueError("source_unit_row_metric_mismatch")
            if self.normalized_field not in row:
                raise ValueError("source_unit_row_value_field_missing")
            if self.reported_unit_field is not None:
                value = row.get(self.reported_unit_field)
                if value not in (None, ""):
                    if not isinstance(value, str):
                        raise ValueError("source_unit_row_unit_type_mismatch")
                    units.add(value)
        return tuple(sorted(units))


def _declaration_json_payload(value: SourceMetricUnitDeclaration) -> dict[str, Any]:
    """Use owner JSON scalars and canonical ordering for schema set fields."""
    payload = value.model_dump(mode="json", by_alias=True)
    if value.source_contract_hash_profile is not None:
        source_record = value.source_contract.to_canonical_snapshot_record(
            hash_profile=value.source_contract_hash_profile
        )
        # Preserve the original created_at scalar as provenance, while the
        # named owner hash intentionally excludes it, exactly as legacy did.
        payload["source_contract"].update(source_record["contract"])
    # DataSchema's governed hash treats these fields as sets. Its complete
    # typed body is retained; JSON lists must not inherit hash-randomized order.
    schema = payload["connector_contract"]["schema"]
    for key in ("tags", "allowed_null_fields"):
        schema[key] = sorted(schema[key])
    for field in schema["fields"]:
        for key in ("tags", "allowed_values"):
            if field[key] is not None:
                field[key] = sorted(field[key])
    # Do not substitute a reduced SourceContract schema or invent another hash
    # law. The original owners must survive the actual persisted projection.
    SourceMetricUnitDeclaration.model_validate(payload)
    return payload


def create_source_metric_unit_declaration(
    store: artifacts.CoreJSONArtifactStore,
    *,
    source_contract: SourceContract,
    contract_registry: ContractRegistry,
    connector_contract_id: str,
    connector_contract_version: str,
    catalog_dataset_id: str,
    catalog_distribution_id: str,
    catalog_metric_id: str,
    request_dataset_id: str,
    source_metric_id: str,
    raw_field: str,
    normalized_field: str,
    metric_selector_field: str,
    reported_unit_field: str | None = None,
) -> SourceMetricUnitDeclarationRef:
    """Resolve actual owners and persist a candidate-only unit declaration.

    The source owner must separately adopt the returned selected ref. This
    producer does not change any production declaration or grant acquisition.
    """
    from polisyos.core.canon import CanonSpec as CoreCanonSpec

    if not isinstance(contract_registry, ContractRegistry):
        raise TypeError("source_unit_contract_registry_required")
    selected = contract_registry.get(connector_contract_id, connector_contract_version)
    source = source_contract.model_copy(deep=True)
    contract = selected.model_copy(deep=True)
    value = SourceMetricUnitDeclaration(
        source_contract=source,
        connector_contract=contract,
        source_contract_hash_profile=SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE,
        source_contract_content_hash=source.to_canonical_snapshot_record(
            hash_profile=SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE
        )["content_hash"],
        connector_contract_content_hash=contract.content_hash,
        schema_content_hash=contract.schema.content_hash,
        catalog_dataset_id=catalog_dataset_id,
        catalog_distribution_id=catalog_distribution_id,
        catalog_metric_id=catalog_metric_id,
        request_dataset_id=request_dataset_id,
        source_metric_id=source_metric_id,
        raw_field=raw_field,
        normalized_field=normalized_field,
        metric_selector_field=metric_selector_field,
        reported_unit_field=reported_unit_field,
    )
    spec = CoreCanonSpec(forbid_floats=False, exclude_none=False)
    ref = store.put_json(
        _declaration_json_payload(value),
        artifacts.PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            schema=artifacts.SchemaInfo(
                name=value.ARTIFACT_SCHEMA_NAME, version=value.ARTIFACT_SCHEMA_VERSION
            ),
            canon=artifacts.CanonInfo.from_spec(spec),
            producer=artifacts.ProducerInfo(
                component="polisyos.fabric.source_metric_units", version="1.1"
            ),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    selected_ref = SourceMetricUnitDeclarationRef.model_validate(ref.model_dump(mode="python"))
    load_source_metric_unit_declaration(store, selected_ref)
    return selected_ref


def load_source_metric_unit_declaration(
    reader: artifacts.CoreJSONArtifactProfileReader,
    ref: artifacts.ArtifactRef,
) -> SourceMetricUnitDeclaration:
    """Replay retained declaration facts without consulting current adoption."""
    selected = SourceMetricUnitDeclarationRef.model_validate(ref.model_dump(mode="python"))
    value = artifacts.validate_core_model_json_artifact(
        SourceMetricUnitDeclaration, reader, selected
    )
    if reader.get_manifest(selected).inputs:
        raise ValueError("source_unit_declaration_unexpected_lineage")
    return value
