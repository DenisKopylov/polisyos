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
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext

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


class TemporalScopeContextWorldReadBinding(BaseModel):
    """Bind an actual WMR-owner read to one admitted temporal context input.

    This record qualifies context admission only. It does not establish N5
    numerical consumption, immutable branch replay, or full closure membership.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["polisyos.runtime.temporal_scope_context_world_read.v1"] = (
        "polisyos.runtime.temporal_scope_context_world_read.v1"
    )
    consumer_stage: Literal["cycle_substrate_context_admission"] = (
        "cycle_substrate_context_admission"
    )
    authority_purpose: Literal["candidate_context_input_verification_only"] = (
        "candidate_context_input_verification_only"
    )
    status: Literal["verified", "not_established"]
    predicate_basis: Literal["recomputed", "not_established"]
    request_binding: TemporalScopeRequestBinding
    invocation_key: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    context_job_ref: ArtifactRef
    context_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    world_model_record_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    interpretation_rule: Literal["wmr_exact_snapshot_and_branch_asof_owner_read.v1"] = (
        "wmr_exact_snapshot_and_branch_asof_owner_read.v1"
    )
    resolved_snapshot_id: str | None = None
    content_query_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    content_query_row_count: int | None = Field(default=None, ge=1)
    limitation_codes: tuple[str, ...] = ()
    n5_numeric_consumption: Literal["not_established"] = "not_established"
    immutable_branch_replay: Literal["not_established"] = "not_established"
    same_input_closure_membership: Literal["not_established"] = "not_established"
    query_limit_per_mode: Literal[100_000] = 100_000
    complete_world_row_membership: Literal["not_established"] = "not_established"
    nl_problem_compiler_consumption: Literal["not_established"] = "not_established"


def resolve_temporal_scope_context_world_read(
    *,
    store: ArtifactStore,
    job: ControlJobRecord,
    scope: ControlJobExecutionScope,
    created: Mapping[str, Any],
    payload: Mapping[str, Any],
    request_binding: TemporalScopeRequestBinding,
    context_job_ref: ArtifactRef,
    context: CycleSubstrateContext,
) -> TemporalScopeContextWorldReadBinding:
    """Verify a snapshot-selected request against actual WMR owner rows.

    Only an explicit snapshot and matching declared time axes are supported by
    this bounded admission consumer. Other selections remain limited; the
    caller must withhold this context rather than consume its configured view.
    The selected current-job context owner must have issued ``context`` before
    this function is called. Its immutable artifact remains the input carrier.
    """
    from datetime import UTC, datetime

    from polisyos.runtime.quality.cycle_substrate import (
        revalidate_cycle_substrate_context,
    )
    from polisyos.runtime.quality.world_model_record import (
        WorldModelRecordError,
        read_world_model_record_owner_values,
        world_model_artifact_views,
    )

    selected_scope = resolve_temporal_scope_for_job(
        store=store,
        job=job,
        scope=scope,
        created=created,
        payload=payload,
        binding=request_binding,
    )
    checked_context = revalidate_cycle_substrate_context(context)
    world = checked_context.world_model_record
    selected_context_ref = _selected_ref(
        context_job_ref.model_dump(mode="json"),
        kind="runtime.quality.cycle_substrate_context_job",
    )
    # The job owner has already performed selected current-job replay. Re-read
    # the immutable bytes here so a substituted context cannot carry its gate.
    from polisyos.runtime.quality.cycle_substrate import (
        parse_cycle_substrate_context_job_artifact,
    )

    selected_payload = read_core_json_artifact(store, selected_context_ref).value
    if not isinstance(selected_payload, Mapping):
        raise ValueError("nl_temporal_scope_context_payload_not_object")
    selected_context = parse_cycle_substrate_context_job_artifact(selected_payload)
    if (
        selected_context.context != checked_context
        or selected_context.job_id != request_binding.job_id
        or selected_context.run_id != request_binding.run_id
        or selected_context.tenant_id != request_binding.tenant_id
        or selected_context.cell_id != request_binding.cell_id
    ):
        raise ValueError("nl_temporal_scope_context_job_binding_mismatch")
    from polisyos.pdc import gy_content_hash

    # Root, child and legitimate same-problem reissues coexist. Every exact
    # owner-issued context is independently checked and retained. Its key is
    # content-bound; an earlier admitted identity cannot be overwritten.
    invocation_key = gy_content_hash(
        {
            "consumer_stage": "cycle_substrate_context_admission",
            "job_id": request_binding.job_id,
            "run_id": request_binding.run_id,
            "tenant_id": request_binding.tenant_id,
            "cell_id": request_binding.cell_id,
            "request_content_hash": request_binding.request_content_hash,
            "design_problem_ref": checked_context.design_problem_ref,
            "context_job_ref": selected_context_ref.model_dump(mode="json"),
            "context_content_hash": checked_context.content_hash,
        }
    )
    common: dict[str, Any] = {
        "request_binding": request_binding,
        "invocation_key": invocation_key,
        "design_problem_ref": checked_context.design_problem_ref,
        "context_job_ref": selected_context_ref,
        "context_content_hash": checked_context.content_hash,
        "world_model_record_hash": world.content_hash,
    }

    def limited(code: str) -> TemporalScopeContextWorldReadBinding:
        return TemporalScopeContextWorldReadBinding(
            **common,
            status="not_established",
            predicate_basis="not_established",
            limitation_codes=(code,),
        )

    if selected_scope.get("scenario_id") is not None:
        return limited("nl_temporal_scope_context_scenario_unsupported")
    if selected_scope.get("branch") is not None:
        return limited("nl_temporal_scope_context_mutable_branch_replay_not_established")
    snapshot_id = selected_scope.get("snapshot_id")
    if snapshot_id is None:
        return limited("nl_temporal_scope_context_explicit_snapshot_required")
    fabric = world.fabric_world_ref
    if snapshot_id != fabric.snapshot_id:
        return limited("nl_temporal_scope_context_snapshot_mismatch")
    for requested_key, actual_value in (
        ("valid_at", fabric.as_of_valid_time),
        ("tx_at", fabric.as_of_tx_time),
    ):
        requested_value = selected_scope.get(requested_key)
        if requested_value is None:
            continue
        if actual_value is None:
            return limited("nl_temporal_scope_context_time_axis_not_established")
        try:
            requested_instant = datetime.fromisoformat(str(requested_value))
            actual_instant = datetime.fromisoformat(str(actual_value))
        except ValueError:
            return limited("nl_temporal_scope_context_time_axis_not_established")
        if (
            requested_instant.tzinfo is None
            or requested_instant.utcoffset() is None
            or actual_instant.tzinfo is None
            or actual_instant.utcoffset() is None
        ):
            return limited("nl_temporal_scope_context_time_axis_timezone_not_established")
        if requested_instant.astimezone(UTC) != actual_instant.astimezone(UTC):
            return limited("nl_temporal_scope_context_time_axis_mismatch")
    try:
        owner_values = read_world_model_record_owner_values(
            store,
            world_model_record=world,
            registry_bundle_ref=world_model_artifact_views(world).registry_bundle_ref,
            substrate_registry=checked_context.substrate_registry,
        )
    except WorldModelRecordError as exc:
        return limited(f"nl_temporal_scope_context_world_read_refused:{exc.code}")
    except OSError:
        return limited("nl_temporal_scope_context_world_read_unavailable")
    actual = owner_values.resolved_fabric_world
    if (
        owner_values.record != world
        or actual != fabric
        or actual.content_query_digest is None
        or actual.content_query_row_count is None
        or actual.content_query_row_count < 1
    ):
        return limited("nl_temporal_scope_context_world_read_not_reconciled")
    return TemporalScopeContextWorldReadBinding(
        **common,
        status="verified",
        predicate_basis="recomputed",
        resolved_snapshot_id=actual.snapshot_id,
        content_query_digest=actual.content_query_digest,
        content_query_row_count=actual.content_query_row_count,
    )
