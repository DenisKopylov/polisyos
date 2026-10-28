"""Registered SQL producer bridge into the existing source-admission owner.

This module does not appoint an issuer. Only an installed Runtime factory can
supply a source authority bound to an authenticated service and view/use scope.
The driver evidence describes the pandas-produced view, not external database
currentness, completeness, or unchanged raw source representation.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from types import FunctionType
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import load_core_json_artifact, validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import (
    RegisteredMaterialization,
    RegisteredSQLAdmissionBinding,
    RegisteredSQLUseContract,
    SourceAdmissionReceipt,
    SourceRegistrationReceipt,
)
from polisyos.core.contracts.fabric import (
    DataSnapshotOwnerBound,
    DataViewRequestRef,
    FabricBridgeDataSnapshotLineage,
    data_snapshot_manifest_inputs_match,
    data_snapshot_owner_input_requirements,
)
from polisyos.fabric.api import _require_registered_sql_execution
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort, _registered_sql_rows_match
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from polisyos.scientist.validation.source_admission_port import (
    SourceAdmissionAuthority,
    _capture_registered_materialization,
    _read_registered_materialization_candidate,
    _require_source_admission_authority,
    _require_source_admission_scope,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.fabric.connectors.sources.sql_query import SQLQueryExecution


class RegisteredSQLViewContract(BaseModel):
    """Versioned configured view that the selected SQL call must actually apply."""

    ARTIFACT_KIND: ClassVar[str] = "fabric.registered_sql_view"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.fabric.RegisteredSQLViewContract"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    provider_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    config_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    statement: str = Field(min_length=1)
    page_size: int = Field(gt=0, le=10000)
    parameters: tuple[str, ...] = Field(default=(), max_length=0)
    projection: Literal["all_columns"] = "all_columns"
    restrictions: Literal["no_filters_or_temporal_scope"] = "no_filters_or_temporal_scope"


class _RegisteredSQLCapture(BaseModel):
    """Selected protected artifact describing the actual execution occurrence."""

    ARTIFACT_KIND: ClassVar[str] = "fabric.registered_sql_capture"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.fabric.RegisteredSQLCapture"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    connector_id: str
    registration_generation: int = Field(ge=1)
    config_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    driver: Literal["sqlite"] = "sqlite"
    driver_timeout_seconds: int = Field(gt=0)
    execution_mode: Literal["one_direct_query_no_retry_cache_or_fallback"] = (
        "one_direct_query_no_retry_cache_or_fallback"
    )
    produced_view: Literal["pandas_json_scalar_records"] = "pandas_json_scalar_records"
    external_currentness: Literal["not_established"] = "not_established"
    external_completeness: Literal["not_established"] = "not_established"
    statement: str
    parameters: tuple[str, ...] = Field(default=(), max_length=0)
    page_size: int = Field(gt=0, le=10000)
    output_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    columns: tuple[str, ...]
    dtypes: tuple[str, ...]
    request_ref: ArtifactRef
    snapshot_ref: ArtifactRef
    payload_ref: ArtifactRef
    schema_ref: ArtifactRef
    quality_ref: ArtifactRef
    view_ref: ArtifactRef
    use_ref: ArtifactRef


@dataclass(frozen=True, slots=True)
class _RegisteredSQLProducerWitness:
    """Live producer observation held inside the existing C105 proof state."""

    owner: DecisionValidityService
    store: ArtifactStore
    observed: SQLQueryExecution
    snapshot: DataSnapshotOwnerBound
    view: RegisteredSQLViewContract
    use: RegisteredSQLUseContract
    capture: _RegisteredSQLCapture
    capture_ref: ArtifactRef
    edges: tuple[InputRef, ...]
    materialization_json: str


def _selected(ref: ArtifactRef) -> None:
    if ref.manifest_profile_sha256 is None:
        raise ValueError("registered_sql_selected_profile_required")


def _same_ref(left: ArtifactRef, right: ArtifactRef) -> bool:
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)


def _capture_edges(
    snapshot: DataSnapshotOwnerBound,
    snapshot_ref: ArtifactRef,
    registration: SourceRegistrationReceipt,
) -> list[InputRef]:
    refs = [
        input_ref_from_artifact_ref(snapshot_ref, role="source.snapshot"),
        input_ref_from_artifact_ref(registration.effective_view_contract_ref, role="source.view"),
        input_ref_from_artifact_ref(registration.use_contract_ref, role="source.use"),
    ]
    refs.extend(
        input_ref_from_artifact_ref(ref, role="snapshot." + role)
        for ref, role in data_snapshot_owner_input_requirements(snapshot)
    )
    if any(ref.manifest_profile_sha256 is None for ref in refs):
        raise ValueError("registered_sql_selected_profile_required")
    return refs


def _edge_keys(inputs: list[InputRef]) -> Counter[tuple[str, str, str | None]]:
    return Counter((row.role, str(row.artifact_id), row.manifest_profile_sha256) for row in inputs)


class RegisteredSQLProducer:
    """Use the real SQL producer and existing C105 admission owner once installed."""

    def __init__(
        self,
        *,
        port: DefaultFabricPort,
        owner: DecisionValidityService,
        authority: SourceAdmissionAuthority,
    ) -> None:
        if type(port) is not DefaultFabricPort or type(owner) is not DecisionValidityService:
            raise ValueError("registered_sql_producer_owner_not_established")
        if port._require_fresh_registered_sql is not True or port._federation is not None:
            raise ValueError("registered_sql_producer_profile_not_established")
        _require_source_admission_authority(authority)
        self._port = port
        self._owner = owner
        self._authority = authority

    def acquire_and_admit(
        self,
        *,
        store: ArtifactStore,
        request_ref: DataViewRequestRef,
        registration: SourceRegistrationReceipt,
        event_id: str,
        occurrence_id: str,
        expected_predecessor: str,
    ) -> tuple[SourceAdmissionReceipt, RegisteredMaterialization, ArtifactRef]:
        """Capture one actual occurrence or recover the exact committed retry.

        The returned history is not current-use authority; its carrier must be
        included in the actual execution basis and read through the C105 owner.
        """
        if self._owner._store is not store:
            raise ValueError("registered_sql_owner_store_mismatch")
        if (
            not isinstance(event_id, str)
            or not event_id
            or len(event_id) > 256
            or not isinstance(occurrence_id, str)
            or not occurrence_id
            or len(occurrence_id) > 256
            or not isinstance(expected_predecessor, str)
        ):
            raise ValueError("registered_sql_command_identity_invalid")
        _selected(request_ref)
        _selected(registration.effective_view_contract_ref)
        _selected(registration.use_contract_ref)
        # The owner persists declared transport fields, not Python ref subclasses.
        registration = SourceRegistrationReceipt.model_validate_json(
            registration.model_dump_json(), strict=True
        )
        return self._owner._run_source_acquisition_serialized(
            self._authority,
            event_id=event_id,
            action=lambda: self._acquire_and_admit_serialized(
                store=store,
                request_ref=request_ref,
                registration=registration,
                event_id=event_id,
                occurrence_id=occurrence_id,
                expected_predecessor=expected_predecessor,
            ),
        )

    def _acquire_and_admit_serialized(
        self,
        *,
        store: ArtifactStore,
        request_ref: DataViewRequestRef,
        registration: SourceRegistrationReceipt,
        event_id: str,
        occurrence_id: str,
        expected_predecessor: str,
    ) -> tuple[SourceAdmissionReceipt, RegisteredMaterialization, ArtifactRef]:
        previous = self._owner.resolve_source_materialization_event(
            self._authority, event_id=event_id
        )
        if previous is not None:
            receipt, original, predecessor = previous
            if (
                original.registration != registration
                or original.occurrence_id != occurrence_id
                or not _same_ref(original.request_ref, request_ref)
                or predecessor != expected_predecessor
            ):
                raise ValueError("registered_sql_retry_command_mismatch")
            binding_ref = self._persist_binding(store, receipt, original, predecessor)
            return receipt, original, binding_ref

        if (
            self._owner.current_source_admission_head(self._authority, registration)
            != expected_predecessor
        ):
            raise ValueError("source_admission_predecessor_gap")

        view = validate_core_model_json_artifact(
            RegisteredSQLViewContract, store, registration.effective_view_contract_ref
        )
        use = validate_core_model_json_artifact(
            RegisteredSQLUseContract, store, registration.use_contract_ref
        )
        if (
            view.provider_id != registration.provider_id
            or view.connector_id != self._port._connector_id
        ):
            raise ValueError("registered_sql_view_not_executed")
        snapshot_ref, observed = DefaultFabricPort._snapshot_with_execution(
            self._port,
            store,
            request_ref,
            expected_config_fingerprint=view.config_fingerprint,
            expected_dataset_id=view.dataset_id,
            expected_page_size=view.page_size,
            expected_query=view.statement,
        )
        if observed is None:
            raise ValueError("registered_sql_execution_not_observed")
        selected = _require_registered_sql_execution(observed)
        if (
            view.provider_id != registration.provider_id
            or view.connector_id != selected.connector_id
            or view.dataset_id != observed.request.dataset_id
            or view.config_fingerprint != observed.config_fingerprint
            or view.statement != observed.query
            or view.page_size != observed.request.page_size
            or view.parameters != observed.parameters
        ):
            raise ValueError("registered_sql_view_not_executed")
        snapshot = validate_core_model_json_artifact(DataSnapshotOwnerBound, store, snapshot_ref)
        if (
            not isinstance(snapshot.source_lineage, FabricBridgeDataSnapshotLineage)
            or not _same_ref(snapshot.source_lineage.data_view_request_ref, request_ref)
            or snapshot.data_schema_ref is None
            or snapshot.quality_report_ref is None
        ):
            raise ValueError("registered_sql_snapshot_not_bound")
        capture = _RegisteredSQLCapture(
            connector_id=selected.connector_id,
            registration_generation=selected.binding.registration_generation,
            config_fingerprint=observed.config_fingerprint,
            driver_timeout_seconds=selected.config.timeout_seconds,
            statement=observed.query,
            parameters=observed.parameters,
            page_size=observed.request.page_size,
            output_sha256="sha256:" + hashlib.sha256(observed.output_json).hexdigest(),
            columns=observed.columns,
            dtypes=observed.dtypes,
            request_ref=request_ref,
            snapshot_ref=snapshot_ref,
            payload_ref=snapshot.data_ref,
            schema_ref=snapshot.data_schema_ref,
            quality_ref=snapshot.quality_report_ref,
            view_ref=registration.effective_view_contract_ref,
            use_ref=registration.use_contract_ref,
        )
        # Freeze the exact declared wire model before comparing its CAS readback.
        # Request and snapshot refs can be typed subclasses on the producer side.
        capture = _RegisteredSQLCapture.model_validate_json(capture.model_dump_json(), strict=True)
        edges = _capture_edges(snapshot, snapshot_ref, registration)
        capture_ref = store.put_json(
            capture,
            ArtifactWriteOptions(
                kind=_RegisteredSQLCapture.ARTIFACT_KIND,
                media_type=_RegisteredSQLCapture.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=_RegisteredSQLCapture.ARTIFACT_SCHEMA_NAME,
                    version=_RegisteredSQLCapture.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=edges,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        _selected(capture_ref)
        materialization = RegisteredMaterialization(
            registration=registration,
            occurrence_id=occurrence_id,
            producer_rule_version="policyos.registered-sql-execution.v1",
            producer_capture_ref=capture_ref,
            request_ref=request_ref,
            snapshot_ref=snapshot_ref,
            payload_ref=snapshot.data_ref,
            schema_ref=snapshot.data_schema_ref,
            quality_ref=snapshot.quality_report_ref,
            observed_at=observed.result.fetched_at,
        )
        # C105 records and reopens this same strict transport representation.
        materialization = RegisteredMaterialization.model_validate_json(
            materialization.model_dump_json(), strict=True
        )

        def verify_capture() -> None:
            self._verify_capture(store, observed, snapshot, view, use, capture, capture_ref, edges)

        witness = _RegisteredSQLProducerWitness(
            owner=self._owner,
            store=store,
            observed=observed,
            snapshot=snapshot,
            view=view,
            use=use,
            capture=capture,
            capture_ref=capture_ref,
            edges=tuple(edges),
            materialization_json=materialization.model_dump_json(),
        )
        proof = _capture_registered_materialization(
            authority=self._authority,
            materialization=materialization,
            validate_capture=verify_capture,
            producer_witness=witness,
        )
        receipt = self._owner.admit_materialization(
            proof, event_id=event_id, expected_predecessor=expected_predecessor
        )
        binding_ref = self._persist_binding(store, receipt, materialization, expected_predecessor)
        return receipt, materialization, binding_ref

    def _persist_binding(
        self,
        store: ArtifactStore,
        receipt: SourceAdmissionReceipt,
        materialization: RegisteredMaterialization,
        predecessor: str,
    ) -> ArtifactRef:
        """Persist original owner history as selected transport, never current status."""
        committed = self._owner.resolve_source_materialization_event(
            self._authority, event_id=receipt.event_id
        )
        if committed != (receipt, materialization, predecessor):
            raise ValueError("registered_sql_original_event_not_established")
        snapshot = validate_core_model_json_artifact(
            DataSnapshotOwnerBound, store, materialization.snapshot_ref
        )
        manifest = store.get_manifest(materialization.snapshot_ref)
        if not data_snapshot_manifest_inputs_match(
            snapshot,
            manifest.inputs,
            schema_version=manifest.artifact_schema.version if manifest.artifact_schema else None,
        ):
            raise ValueError("registered_sql_snapshot_not_bound")
        payload = RegisteredSQLAdmissionBinding(
            receipt=receipt, materialization=materialization, expected_predecessor=predecessor
        )
        edges = _capture_edges(snapshot, materialization.snapshot_ref, materialization.registration)
        edges.append(
            input_ref_from_artifact_ref(materialization.producer_capture_ref, role="source.capture")
        )
        ref = store.put_json(
            payload,
            ArtifactWriteOptions(
                kind=RegisteredSQLAdmissionBinding.ARTIFACT_KIND,
                media_type=RegisteredSQLAdmissionBinding.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=RegisteredSQLAdmissionBinding.ARTIFACT_SCHEMA_NAME,
                    version=RegisteredSQLAdmissionBinding.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=edges,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        _selected(ref)
        if (
            not store.verify(ref).ok
            or validate_core_model_json_artifact(RegisteredSQLAdmissionBinding, store, ref)
            != payload
            or _edge_keys(store.get_manifest(ref).inputs) != _edge_keys(edges)
        ):
            raise ValueError("registered_sql_binding_not_established")
        return ref

    @staticmethod
    def _verify_capture(
        store: ArtifactStore,
        observed: SQLQueryExecution,
        snapshot: DataSnapshotOwnerBound,
        view: RegisteredSQLViewContract,
        use: RegisteredSQLUseContract,
        capture: _RegisteredSQLCapture,
        capture_ref: ArtifactRef,
        edges: list[InputRef],
    ) -> None:
        _require_registered_sql_execution(observed)
        if (
            validate_core_model_json_artifact(RegisteredSQLViewContract, store, capture.view_ref)
            != view
        ):
            raise ValueError("registered_sql_view_not_executed")
        if (
            validate_core_model_json_artifact(RegisteredSQLUseContract, store, capture.use_ref)
            != use
        ):
            raise ValueError("registered_sql_use_not_established")
        selected_snapshot = validate_core_model_json_artifact(
            DataSnapshotOwnerBound, store, capture.snapshot_ref
        )
        snapshot_manifest = store.get_manifest(capture.snapshot_ref)
        if selected_snapshot != snapshot or not data_snapshot_manifest_inputs_match(
            snapshot,
            snapshot_manifest.inputs,
            schema_version=snapshot_manifest.artifact_schema.version
            if snapshot_manifest.artifact_schema
            else None,
        ):
            raise ValueError("registered_sql_snapshot_not_bound")
        if not _registered_sql_rows_match(
            observed.output_json, load_core_json_artifact(store, snapshot.data_ref)
        ):
            raise ValueError("registered_sql_output_binding_not_established")
        schema = load_core_json_artifact(store, capture.schema_ref)
        expected_schema = {
            "schema_id": observed.result.schema_id,
            "schema_version": observed.result.schema_version,
            "sql_columns": [
                {"name": name, "dtype": dtype}
                for name, dtype in zip(observed.columns, observed.dtypes, strict=True)
            ],
        }
        if schema != expected_schema:
            raise ValueError("registered_sql_schema_binding_not_established")
        quality = load_core_json_artifact(store, capture.quality_ref)
        if (
            not isinstance(quality, dict)
            or type(quality.get("row_count")) is not int
            or quality.get("row_count") != observed.result.row_count
            or quality.get("schema_id") != observed.result.schema_id
            or quality.get("tier") != "unverified"
            or type(quality.get("score")) is not float
            or quality.get("score") != 0.0
            or type(quality.get("quality_flags")) is not list
            or "source_completeness_unknown" not in quality["quality_flags"]
            or not isinstance(quality.get("freshness_status"), dict)
            or quality["freshness_status"].get("level") != "unknown"
            or quality["freshness_status"].get("is_fresh") is not False
        ):
            raise ValueError("registered_sql_quality_binding_not_established")
        persisted = validate_core_model_json_artifact(_RegisteredSQLCapture, store, capture_ref)
        if persisted != capture or _edge_keys(store.get_manifest(capture_ref).inputs) != _edge_keys(
            edges
        ):
            raise ValueError("registered_sql_capture_binding_not_established")


# The selected owner invokes the original verifier code with actual witness
# values. Replacing a saved function object's __code__ cannot turn a callback
# or a caller-created DTO into a driver observation. Runtime module globals and
# the built-in execution boundary are part of the selected trusted profile.
_REGISTERED_SQL_VERIFY_CAPTURE_CODE = RegisteredSQLProducer._verify_capture.__code__


def _require_registered_sql_producer_capture(
    proof: object, *, owner: DecisionValidityService, store: ArtifactStore
) -> tuple[object, RegisteredMaterialization]:
    """Recompute the exact live producer relation for the installed owner."""
    authority, materialization, witness = _read_registered_materialization_candidate(proof)
    if (
        type(witness) is not _RegisteredSQLProducerWitness
        or witness.owner is not owner
        or witness.store is not store
    ):
        raise ValueError("registered_sql_producer_provenance_not_established")
    expected = RegisteredMaterialization.model_validate_json(
        witness.materialization_json, strict=True
    )
    if materialization != expected:
        raise ValueError("registered_sql_producer_relation_changed")
    registration = materialization.registration
    observed, view, capture, snapshot = (
        witness.observed,
        witness.view,
        witness.capture,
        witness.snapshot,
    )
    selected = _require_registered_sql_execution(observed)
    if (
        not isinstance(snapshot.source_lineage, FabricBridgeDataSnapshotLineage)
        or view.provider_id != registration.provider_id
        or view.connector_id != selected.connector_id
        or view.dataset_id != observed.request.dataset_id
        or view.config_fingerprint != observed.config_fingerprint
        or view.statement != observed.query
        or view.parameters != observed.parameters
        or view.page_size != observed.request.page_size
        or capture.connector_id != selected.connector_id
        or capture.registration_generation != selected.binding.registration_generation
        or capture.config_fingerprint != observed.config_fingerprint
        or capture.driver_timeout_seconds != selected.config.timeout_seconds
        or capture.statement != observed.query
        or capture.parameters != observed.parameters
        or capture.page_size != observed.request.page_size
        or capture.output_sha256 != "sha256:" + hashlib.sha256(observed.output_json).hexdigest()
        or capture.columns != observed.columns
        or capture.dtypes != observed.dtypes
        or materialization.producer_rule_version != "policyos.registered-sql-execution.v1"
        or materialization.upstream_asserted_at is not None
        or materialization.observed_at != observed.result.fetched_at
        or not _same_ref(capture.request_ref, materialization.request_ref)
        or not _same_ref(capture.snapshot_ref, materialization.snapshot_ref)
        or not _same_ref(capture.payload_ref, materialization.payload_ref)
        or not _same_ref(capture.schema_ref, materialization.schema_ref)
        or not _same_ref(capture.quality_ref, materialization.quality_ref)
        or not _same_ref(capture.view_ref, registration.effective_view_contract_ref)
        or not _same_ref(capture.use_ref, registration.use_contract_ref)
        or not _same_ref(witness.capture_ref, materialization.producer_capture_ref)
        or not _same_ref(snapshot.source_lineage.data_view_request_ref, materialization.request_ref)
        or not _same_ref(snapshot.data_ref, materialization.payload_ref)
        or snapshot.data_schema_ref is None
        or not _same_ref(snapshot.data_schema_ref, materialization.schema_ref)
        or snapshot.quality_report_ref is None
        or not _same_ref(snapshot.quality_report_ref, materialization.quality_ref)
        or _edge_keys(list(witness.edges))
        != _edge_keys(_capture_edges(snapshot, materialization.snapshot_ref, registration))
    ):
        raise ValueError("registered_sql_producer_relation_not_established")
    verify = FunctionType(_REGISTERED_SQL_VERIFY_CAPTURE_CODE, globals())
    verify(
        store,
        observed,
        snapshot,
        view,
        witness.use,
        capture,
        witness.capture_ref,
        list(witness.edges),
    )
    authority_state = _require_source_admission_authority(authority)
    _require_source_admission_scope(
        authority_state,
        operation="admit",
        registration_key=registration.registration_key,
        effective_view_contract_ref=registration.effective_view_contract_ref,
        use_contract_ref=registration.use_contract_ref,
    )
    if (
        registration.tenant_id,
        registration.cell_id,
        registration.provider_id,
        registration.issuer_key,
    ) != (
        authority_state.tenant_id,
        authority_state.cell_id,
        authority_state.provider_id,
        authority_state.issuer_key,
    ):
        raise ValueError("source_admission_operation_scope_not_established")
    return authority_state, materialization
