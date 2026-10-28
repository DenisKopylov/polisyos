"""Persist and replay caller-selected temporal intent at the admitted NL job owner.

This owner records requested view identity. Data owners must separately prove
which view they consumed; this artifact supplies no policy or legal authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    ArtifactWriteOptions,
    CanonInfo,
    ProducerInfo,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    expected_artifact_manifest_for_write,
    input_ref_from_artifact_ref,
    read_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import NaturalLanguageRunRequest

from .job_attempt_publication import (
    _NL_AUTHORIZATION_RECEIPT_KEY,
    _NL_REQUEST_SNAPSHOT_KEY,
    _nl_request_snapshot_content_hash,
    _validate_nl_authorization_receipt,
    _validate_nl_request_snapshot,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionScope,
        ControlJobRecord,
    )

TEMPORAL_SCOPE_KIND = "runtime.temporal_scope"
TEMPORAL_SCOPE_SCHEMA = "polisyos.runtime.TemporalScope"
TEMPORAL_SCOPE_SCHEMA_VERSION = "1.0"
TEMPORAL_SCOPE_PRODUCER = "polisyos.runtime.http.services.control.temporal_scope"
_TEMPORAL_SCOPE_CANON = CanonSpec(version="0.2.0", forbid_floats=False, exclude_none=False)
_NL_PAYLOAD_KIND = "runtime.control_job_payload.natural_language_run"


class TemporalScopeRequestBinding(BaseModel):
    """Bind one selected request cursor to its authorized durable queue record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["polisyos.runtime.temporal_scope_request_binding.v1"] = (
        "polisyos.runtime.temporal_scope_request_binding.v1"
    )
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    request_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_snapshot_schema: Literal["polisyos.runtime.control_nl_request_snapshot.v3"]
    request_payload_ref: ArtifactRef
    temporal_scope_ref: ArtifactRef
    predicate_basis: Literal["recomputed"] = "recomputed"
    requested_view_only: Literal[True] = True
    limitation_code: Literal["temporal_scope_consumed_view_not_established"] = (
        "temporal_scope_consumed_view_not_established"
    )


def _selected_ref(value: object, *, kind: str) -> ArtifactRef:
    """Require an explicit selected CAS identity before any store read."""
    if not isinstance(value, Mapping):
        raise ValueError("nl_temporal_scope_selected_ref_missing")
    ref = ArtifactRef.model_validate(dict(value))
    if ref.kind != kind or ref.media_type != "application/json" or not ref.manifest_profile_sha256:
        raise ValueError("nl_temporal_scope_selected_ref_invalid")
    return ref


def read_nl_job_payload(
    *,
    store: ArtifactStore,
    job: ControlJobRecord,
    created: Mapping[str, Any],
    legacy_reader: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Resolve selected queue bytes, retaining the old reader for legacy jobs."""
    if "nl_request_payload_artifact_ref" not in created:
        payload = legacy_reader(job.payload_ref, kind=_NL_PAYLOAD_KIND)
        if "temporal_scope" in payload:
            raise ValueError("nl_temporal_scope_selected_queue_not_established")
        return payload
    return _read_selected_nl_job_payload(store=store, job=job, created=created)


def _read_selected_nl_job_payload(
    *, store: ArtifactStore, job: ControlJobRecord, created: Mapping[str, Any]
) -> dict[str, Any]:
    """Re-read the durable selected queue, never a mutable default manifest."""
    ref = _selected_ref(created.get("nl_request_payload_artifact_ref"), kind=_NL_PAYLOAD_KIND)
    if str(ref.artifact_id) != job.payload_ref or created.get("payload_ref") != job.payload_ref:
        raise ValueError("nl_temporal_scope_selected_queue_binding_mismatch")
    if not store.verify(ref).ok:
        raise ValueError("nl_temporal_scope_selected_queue_integrity_failed")
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if (
        schema is None
        or schema.name != "polisyos.runtime.ControlJobPayload"
        or schema.version != "1.1"
    ):
        raise ValueError("nl_temporal_scope_selected_queue_schema_mismatch")
    value = read_core_json_artifact(store, ref).value
    if not isinstance(value, dict) or "temporal_scope" not in value:
        raise ValueError("nl_temporal_scope_selected_queue_invalid")
    receipt = _validate_nl_authorization_receipt(value.get(_NL_AUTHORIZATION_RECEIPT_KEY))
    _validate_nl_request_snapshot(value, receipt)
    return value


def _request_scope(payload: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    """Recompute cursor presence and request digest from the authorized snapshot."""
    receipt = _validate_nl_authorization_receipt(payload.get(_NL_AUTHORIZATION_RECEIPT_KEY))
    _validate_nl_request_snapshot(payload, receipt)
    snapshot = payload[_NL_REQUEST_SNAPSHOT_KEY]
    request = NaturalLanguageRunRequest.model_validate(snapshot["request"])
    values = request.model_dump(mode="json")
    scope = values.get("temporal_scope")
    if not isinstance(scope, dict) or snapshot["schema_version"] != (
        "polisyos.runtime.control_nl_request_snapshot.v3"
    ):
        raise ValueError("nl_temporal_scope_request_not_selected")
    return scope, _nl_request_snapshot_content_hash(snapshot)


def _scope_options(
    *,
    job: ControlJobRecord,
    scope: ControlJobExecutionScope,
    queue_ref: ArtifactRef,
) -> ArtifactWriteOptions:
    """Construct stable run-scoped provenance without inventing an authority role."""
    if scope.status != "established" or not scope.tenant_id or not scope.cell_id or not job.run_id:
        raise ValueError("nl_temporal_scope_execution_scope_not_established")
    return ArtifactWriteOptions(
        kind=TEMPORAL_SCOPE_KIND,
        media_type="application/json",
        schema=SchemaInfo(name=TEMPORAL_SCOPE_SCHEMA, version=TEMPORAL_SCOPE_SCHEMA_VERSION),
        producer=ProducerInfo(component=TEMPORAL_SCOPE_PRODUCER, version="1.0"),
        canon=CanonInfo.from_spec(_TEMPORAL_SCOPE_CANON),
        inputs=[input_ref_from_artifact_ref(queue_ref, role="authorized_nl_request_payload")],
        tenant_context=ArtifactTenantContextInfo(tenant_id=scope.tenant_id, cell_id=scope.cell_id),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id=f"temporal-scope-request:{job.job_id}",
            status="candidate_only",
            run_id=str(job.run_id),
            job_id=job.job_id,
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
        ),
    )


def resolve_temporal_scope_for_job(
    *,
    store: ArtifactStore,
    job: ControlJobRecord,
    scope: ControlJobExecutionScope,
    created: Mapping[str, Any],
    payload: Mapping[str, Any],
    binding: TemporalScopeRequestBinding,
) -> dict[str, Any]:
    """Replay an exact requested-view profile against the current admitted job."""
    queue_ref = _selected_ref(created.get("nl_request_payload_artifact_ref"), kind=_NL_PAYLOAD_KIND)
    queued_payload = _read_selected_nl_job_payload(store=store, job=job, created=created)
    expected_scope, request_hash = _request_scope(queued_payload)
    if _request_scope(payload) != (expected_scope, request_hash):
        raise ValueError("nl_temporal_scope_mutable_worker_request_mismatch")
    expected_options = _scope_options(job=job, scope=scope, queue_ref=queue_ref)
    expected = TemporalScopeRequestBinding(
        job_id=job.job_id,
        run_id=str(job.run_id),
        tenant_id=str(scope.tenant_id),
        cell_id=str(scope.cell_id),
        request_content_hash=request_hash,
        request_snapshot_schema="polisyos.runtime.control_nl_request_snapshot.v3",
        request_payload_ref=queue_ref,
        temporal_scope_ref=binding.temporal_scope_ref,
    )
    if binding != expected:
        raise ValueError("nl_temporal_scope_request_binding_mismatch")
    ref = _selected_ref(
        binding.temporal_scope_ref.model_dump(mode="json"), kind=TEMPORAL_SCOPE_KIND
    )
    if not store.verify(ref).ok:
        raise ValueError("nl_temporal_scope_integrity_failed")
    manifest = store.get_manifest(ref)
    read = read_core_json_artifact(store, ref)
    expected_manifest = expected_artifact_manifest_for_write(
        artifact_id=ref.artifact_id,
        data=read.raw_payload_bytes,
        opts=expected_options,
        created_at=manifest.created_at,
    )
    if artifact_manifest_profile_sha256(expected_manifest) != ref.manifest_profile_sha256:
        raise ValueError("nl_temporal_scope_owner_profile_mismatch")
    value = read.value
    if value != expected_scope:
        raise ValueError("nl_temporal_scope_request_payload_mismatch")
    return dict(expected_scope)


def materialize_temporal_scope_for_job(
    *,
    store: ArtifactStore,
    job: ControlJobRecord,
    scope: ControlJobExecutionScope,
    created: Mapping[str, Any],
    payload: Mapping[str, Any],
    persisted_binding: object = None,
) -> TemporalScopeRequestBinding:
    """Write or recover the same selected intent, then perform a fresh exact read."""
    queued_payload = _read_selected_nl_job_payload(store=store, job=job, created=created)
    selected_scope, request_hash = _request_scope(queued_payload)
    if _request_scope(payload) != (selected_scope, request_hash):
        raise ValueError("nl_temporal_scope_mutable_worker_request_mismatch")
    queue_ref = _selected_ref(created.get("nl_request_payload_artifact_ref"), kind=_NL_PAYLOAD_KIND)
    options = _scope_options(job=job, scope=scope, queue_ref=queue_ref)
    if persisted_binding is not None:
        binding = TemporalScopeRequestBinding.model_validate(persisted_binding)
    else:
        ref = store.put_json(
            selected_scope, options, canon_spec=_TEMPORAL_SCOPE_CANON, return_selected_profile=True
        )
        binding = TemporalScopeRequestBinding(
            job_id=job.job_id,
            run_id=str(job.run_id),
            tenant_id=str(scope.tenant_id),
            cell_id=str(scope.cell_id),
            request_content_hash=request_hash,
            request_snapshot_schema="polisyos.runtime.control_nl_request_snapshot.v3",
            request_payload_ref=queue_ref,
            temporal_scope_ref=ref,
        )
    resolve_temporal_scope_for_job(
        store=store, job=job, scope=scope, created=created, payload=payload, binding=binding
    )
    return binding
