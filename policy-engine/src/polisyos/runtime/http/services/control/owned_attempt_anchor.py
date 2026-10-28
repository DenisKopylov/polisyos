"""Create and reconcile a CAS-bound pre-output HTE attempt anchor.

The pre-output artifact is written while the Runtime worker fence is live. The
success resolver re-reads the completed owner row and lifecycle event, then
resolves the owner-selected HTE output tuple. A separate refusal resolver
re-reads the failed owner row and terminal event without producing output
association. Caller-supplied run, attempt, failure, or result values are never
treated as owner evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol, overload

from pydantic import BaseModel, TypeAdapter

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.protocol import (
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStore,
)
from polisyos.core.contracts.owned_attempt_anchor import (
    OWNED_ATTEMPT_ANCHOR_KIND,
    OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME,
    OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION,
    OwnedAttemptAnchor,
    OwnedAttemptAnchorAssociation,
    OwnedAttemptAnchorDispatchContext,
    OwnedAttemptAnchorProjectionAssociation,
    OwnedAttemptAnchorRef,
    OwnedAttemptAnchorRefusalAssociation,
    OwnedAttemptHTEInputAdmitted,
    OwnedAttemptHTEInputCapture,
    OwnedAttemptHTEInputRefusal,
    OwnedAttemptHTEInputRefused,
    OwnedAttemptLifecycleEvent,
    OwnedAttemptPhysicalSourceBindingRef,
    OwnedAttemptPredicateOrigins,
    SelectedArtifactRef,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonArtifactBoundedRead,
        CoreJsonReadLimits,
    )
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.contracts.owned_attempt_anchor import OwnedHTERequestContextV1
    from polisyos.core.contracts.runtime import (
        ContentAdmittedObservationalRunIntent,
        DirectMethodExecutionHTEResourceEvidence,
        DirectMethodExecutionSelection,
        ObservationalInputResourcePolicy,
        ObservationalRunIntent,
    )
    from polisyos.foundry.data_plane import (
        HTEInputPreparationRefusal,
        HTEPhysicalSourceMaterializationBinding,
        PreparedHTEObservationalInput,
    )
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        HTEProducerResourceReceiptV1,
        HTEWriterReadyIntervalV1,
        HTEWriterReadyPointV1,
        HTEWriterReadyV1,
        _CaptureFactsV1,
    )
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
    from polisyos.ir.analytics import (
        ATEInferenceBasis,
        HTEOutcome,
        HTEPointResult,
        HTERefusalDiagnostic,
        HTEResourceExecutionEvidenceV1,
        HTEResult,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionAdmission,
        ControlJobExecutionScope,
        ControlJobRecord,
        ControlPlaneStore,
        _ControlJobExecutionLifecycleProof,
        _ControlJobLifecycleSourceEventRecord,
    )
    from polisyos.scientist.compute.runner import (
        MethodExecutionAdmission,
        MethodExecutionWork,
    )

_OBSERVATIONAL_INTENT_KIND = "runtime.observational_run_intent"
_OBSERVATIONAL_INTENT_SCHEMA = "polisyos.runtime.ObservationalRunIntent"
_CONTENT_ADMITTED_INTENT_KIND = "runtime.content_admitted_observational_run_intent"
_CONTENT_ADMITTED_INTENT_SCHEMA = "polisyos.runtime.ContentAdmittedObservationalRunIntent"
_SUCCESSOR_ANCHOR_INTENT_SCHEMAS = frozenset(
    {
        "polisyos.runtime.observational_run_intent.v2",
        "polisyos.runtime.observational_run_intent.v3",
    }
)
_SUCCESSOR_ANCHOR_METHOD_VERSION = "2.0.0"
_SUCCESSOR_ANCHOR_METHODS = frozenset(
    {
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    }
)
_OWNER_SCOPE_UNSET = object()


class OwnedAttemptAnchorVersionRefusalError(ValueError):
    """Typed refusal when a legacy intent reaches the successor-only anchor intake."""

    code = "owned_attempt_successor_intent_required"

    def __init__(self) -> None:
        super().__init__(self.code)


class _OwnedAttemptAnchorArtifactStore(
    CoreJSONArtifactStore,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Compose Core's existing selected-profile writer and bounded-reader ports."""


class OwnedAttemptAnchorRuntimeHost(Protocol):
    """Narrow existing Runtime owners required by the anchor bridge."""

    _artifact_store: ArtifactStore
    _control_store: ControlPlaneStore

    def _require_owned_attempt_anchor_bounded_store(
        self, *, limits: CoreJsonReadLimits
    ) -> _OwnedAttemptAnchorArtifactStore:
        """Require the existing typed bounded-reader ports for selected Core JSON."""
        ...

    def _observational_read_limits(self) -> CoreJsonReadLimits:
        """Return the selected Runtime resource-policy limits."""
        ...

    def resolve_historical_search_uncertainty_task_binding(
        self,
        *,
        binding_ref: SelectedArtifactRef,
        owner_association: OwnedAttemptAnchorAssociation,
    ) -> object:
        """Resolve a binding against the actual completed owner association.

        Runtime implements this narrow port by invoking the Search owner. The
        Core control helper depends only on this structural callback and never
        imports Search models or copies its scope/inventory fields.
        """
        ...


def _canonical_json_digest(value: object) -> str:
    """Hash one finite, canonical JSON value with the repository's Core encoding."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolved_params_digest(params: Mapping[str, object], seed: int) -> str:
    """Bind resolved method params and seed using the HTE capture's canonical recipe."""
    if type(seed) is not int or seed < 0:
        raise ValueError("owned_attempt_seed_invalid")
    return _canonical_json_digest({"params": dict(params), "seed": seed})


def _require_full_profile_ref(value: object, *, code: str) -> ArtifactRef:
    """Parse one exact selected CAS ref and fail closed when its profile is absent."""
    try:
        payload = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
        ref = ArtifactRef.model_validate(payload, strict=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if ref.manifest_profile_sha256 is None:
        raise ValueError(code)
    # The bounded Core reader deliberately accepts only the canonical base
    # ArtifactRef class; normalize structural subtypes without losing profile.
    return ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _selected_profile_ref(value: object, *, code: str) -> SelectedArtifactRef:
    """Parse a strict subtype after retaining the complete selected CAS view."""
    base = _require_full_profile_ref(value, code=code)
    return SelectedArtifactRef.model_validate(base.model_dump(mode="python"), strict=True)


def _owned_attempt_anchor_ref(value: object, *, code: str) -> OwnedAttemptAnchorRef:
    """Parse a Core anchor subtype from any full selected-reference implementation."""
    base = _require_full_profile_ref(value, code=code)
    try:
        return OwnedAttemptAnchorRef.model_validate(base.model_dump(mode="python"), strict=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc


def _anchor_search_binding_ref(anchor: OwnedAttemptAnchor) -> SelectedArtifactRef | None:
    """Return the one Search-owner ref frozen in the admitted request context."""
    raw = anchor.request_context.search_uncertainty_task_binding_ref
    if raw is None:
        return None
    ref = _selected_profile_ref(raw, code="owned_attempt_search_binding_ref_invalid")
    if (
        ref.kind != "scientist.search.uncertainty_task_binding"
        or ref.media_type != "application/json"
    ):
        raise ValueError("owned_attempt_search_binding_ref_kind_mismatch")
    return ref


def _search_binding_input(anchor: OwnedAttemptAnchor) -> tuple[tuple[ArtifactRef, str], ...]:
    """Return the exact optional selected-manifest edge from the anchor."""
    ref = _anchor_search_binding_ref(anchor)
    if ref is None:
        return ()
    return ((ref, "search_uncertainty_task_binding"),)


def _anchor_materialization_binding_ref(
    anchor: OwnedAttemptAnchor,
) -> OwnedAttemptPhysicalSourceBindingRef | None:
    """Return the exact physical binding selected by an admitted attempt."""
    if isinstance(anchor.input_admission, OwnedAttemptHTEInputRefused):
        return None
    ref = anchor.input_admission.input_capture.materialization_binding_ref
    if ref is None:
        if anchor.resource_policy_revision == "r5":
            raise ValueError("owned_attempt_r5_physical_materialization_binding_missing")
        return None
    selected = OwnedAttemptPhysicalSourceBindingRef.model_validate(
        _require_full_profile_ref(
            ref,
            code="owned_attempt_physical_materialization_binding_ref_invalid",
        ).model_dump(mode="python"),
        strict=True,
    )
    if selected.manifest_profile_sha256 is None:
        raise ValueError("owned_attempt_physical_materialization_binding_profile_missing")
    if not _same_ref(anchor.request_context.materialization_binding_ref, selected):
        raise ValueError("owned_attempt_physical_materialization_context_mismatch")
    return selected


def _physical_binding_input(anchor: OwnedAttemptAnchor) -> tuple[tuple[ArtifactRef, str], ...]:
    """Return the optional exact producer-bound materialization edge."""
    ref = _anchor_materialization_binding_ref(anchor)
    if ref is None:
        return ()
    return ((ref, "physical_source_materialization_binding"),)


def _require_physical_binding_content(
    *, service: OwnedAttemptAnchorRuntimeHost, anchor: OwnedAttemptAnchor
) -> tuple[OwnedAttemptPhysicalSourceBindingRef, HTEPhysicalSourceMaterializationBinding] | None:
    """Re-resolve the selected binding for full owner consumers, never as a semantic claim."""
    ref = _anchor_materialization_binding_ref(anchor)
    if ref is None:
        return None
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.foundry.data_plane import prepare_hte_observational_input

    limits = service._observational_read_limits()
    submitted_ref = _require_full_profile_ref(
        anchor.submitted_input_ref,
        code="owned_attempt_selected_profile_required",
    )
    effective_ref = _require_full_profile_ref(
        anchor.effective_input_ref,
        code="owned_attempt_selected_profile_required",
    )
    try:
        bounded_store = service._require_owned_attempt_anchor_bounded_store(limits=limits)
        prepared = prepare_hte_observational_input(
            store=bounded_store,
            source_ref=submitted_ref,
            protocol=anchor.source_protocol,
            method_fqn=anchor.method_fqn,
            limits=limits,
        )
    except CoreJsonReadBoundsRefusalError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_physical_binding_input_recompute_failed") from exc
    if (
        not _same_ref(prepared.submitted_ref, submitted_ref)
        or not _same_ref(prepared.effective_ref, effective_ref)
        or not _same_ref(prepared.effective_ref, anchor.input_capture.source_data_ref)
    ):
        raise ValueError("owned_attempt_physical_binding_input_identity_mismatch")
    return _resolve_physical_source_binding(
        service=service,
        binding_ref=ref,
        submitted_ref=submitted_ref,
        effective_ref=effective_ref,
        data=prepared.data,
    )


def _require_search_binding_manifest(
    *, service: OwnedAttemptAnchorRuntimeHost, anchor: OwnedAttemptAnchor
) -> SelectedArtifactRef | None:
    """Recheck the binding ref's exact selected Search schema before association."""
    ref = _anchor_search_binding_ref(anchor)
    if ref is None:
        return None
    _read_projection_manifest(
        service=service,
        selected_ref=ref,
        expected_kind="scientist.search.uncertainty_task_binding",
        expected_schema_name="polisyos.scientist.SearchUncertaintyTaskBinding",
        expected_schema_version="1.0",
    )
    return ref


def _resolve_historical_search_binding(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    association: OwnedAttemptAnchorAssociation,
) -> None:
    """Require Search's owner recomputation when a binding ref is selected."""
    binding_ref = association.search_uncertainty_task_binding_ref
    if binding_ref is None:
        return
    resolver = getattr(service, "resolve_historical_search_uncertainty_task_binding", None)
    if not callable(resolver):
        raise ValueError("owned_attempt_historical_search_resolver_unavailable")
    try:
        resolution = resolver(binding_ref=binding_ref, owner_association=association)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_historical_search_binding_unavailable") from exc
    if not isinstance(resolution, BaseModel):
        raise ValueError("owned_attempt_historical_search_binding_untyped")
    if (
        getattr(resolution, "schema_version", None) != "1.0"
        or getattr(resolution, "resolution_status", None) != "historical"
        or not _same_ref(getattr(resolution, "binding_ref", None), binding_ref)
        or getattr(resolution, "closure_status", None) != "recomputed"
        or not isinstance(getattr(resolution, "binding", None), BaseModel)
    ):
        raise ValueError("owned_attempt_historical_search_binding_mismatch")


def _same_ref(left: object, right: object) -> bool:
    """Compare complete selected-profile identities across Core and IR ref types."""
    try:
        return _require_full_profile_ref(
            left, code="left_ref_invalid"
        ) == _require_full_profile_ref(right, code="right_ref_invalid")
    except (TypeError, ValueError):
        return False


def _optional_same_ref(left: object | None, right: object | None) -> bool:
    """Compare nullable selected refs without treating two absences as a mismatch."""
    if left is None or right is None:
        return left is None and right is None
    return _same_ref(left, right)


def _read_profiled_value(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    selected_ref: ArtifactRef,
    limits: CoreJsonReadLimits,
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> tuple[CoreJsonArtifactBoundedRead, object]:
    """Resolve one exact bounded JSON view and check its owner-declared manifest identity."""
    from polisyos.core.artifacts import read_core_json_artifact_bounded

    selected_ref = _require_full_profile_ref(
        selected_ref,
        code="owned_attempt_selected_profile_required",
    )
    if selected_ref.manifest_profile_sha256 is None:
        raise ValueError("owned_attempt_selected_profile_required")
    bounded_store = service._require_owned_attempt_anchor_bounded_store(limits=limits)
    bounded = read_core_json_artifact_bounded(bounded_store, selected_ref, limits=limits)
    if not _same_ref(bounded.effective_ref, selected_ref):
        raise ValueError("owned_attempt_selected_profile_drift")
    manifest = bounded.manifest
    if (
        manifest.kind != expected_kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != SchemaInfo(name=expected_schema_name, version=expected_schema_version)
    ):
        raise ValueError("owned_attempt_artifact_manifest_identity_mismatch")
    return bounded, bounded.value


def _read_projection_manifest(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    selected_ref: ArtifactRef,
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> ArtifactManifest:
    """Resolve a selected manifest view without reading its artifact payload."""
    exact_ref = _require_full_profile_ref(
        selected_ref,
        code="owned_attempt_projection_selected_profile_required",
    )
    try:
        manifest = service._artifact_store.get_manifest(exact_ref)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_projection_manifest_unavailable") from exc
    if (
        manifest.artifact_id != exact_ref.artifact_id
        or manifest.kind != expected_kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != SchemaInfo(name=expected_schema_name, version=expected_schema_version)
        or artifact_manifest_profile_sha256(manifest) != exact_ref.manifest_profile_sha256
    ):
        raise ValueError("owned_attempt_projection_manifest_identity_mismatch")
    return manifest


def _require_projection_manifest_inputs(
    *, manifest: ArtifactManifest, inputs: tuple[tuple[ArtifactRef, str], ...], code: str
) -> None:
    """Require the exact selected-profile lineage from a manifest-only read."""
    expected = tuple(input_ref_from_artifact_ref(ref, role=role) for ref, role in inputs)
    if tuple(manifest.inputs) != expected:
        raise ValueError(code)


def _require_projection_manifest_input_variants(
    *,
    manifest: ArtifactManifest,
    alternatives: tuple[tuple[tuple[ArtifactRef, str], ...], ...],
    code: str,
) -> None:
    """Accept only explicitly defined lineage variants for optional evidence."""
    actual = tuple(manifest.inputs)
    if not any(
        actual == tuple(input_ref_from_artifact_ref(ref, role=role) for ref, role in inputs)
        for inputs in alternatives
    ):
        raise ValueError(code)


def _read_profiled_model[ModelT: BaseModel](
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    selected_ref: ArtifactRef,
    limits: CoreJsonReadLimits,
    model: type[ModelT],
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> ModelT:
    """Resolve a typed Core artifact through its owner-bound bounded reader."""
    from polisyos.core.artifacts import validate_core_model_bounded_read

    bounded, _value = _read_profiled_value(
        service=service,
        selected_ref=selected_ref,
        limits=limits,
        expected_kind=expected_kind,
        expected_schema_name=expected_schema_name,
        expected_schema_version=expected_schema_version,
    )
    return validate_core_model_bounded_read(model, bounded)


def _read_versioned_profiled_model[ModelT: BaseModel](
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    selected_ref: ArtifactRef,
    limits: CoreJsonReadLimits,
    model: type[ModelT],
    expected_kind: str,
    expected_schema_name: str,
) -> ModelT:
    """Resolve an exact semantic intent only when its CAS schema version agrees."""
    from polisyos.core.artifacts import (
        read_core_json_artifact_bounded,
        validate_core_model_bounded_read,
    )
    from polisyos.core.contracts.runtime import _observational_intent_manifest_identity

    selected_ref = _require_full_profile_ref(
        selected_ref,
        code="owned_attempt_selected_profile_required",
    )
    bounded_store = service._require_owned_attempt_anchor_bounded_store(limits=limits)
    bounded = read_core_json_artifact_bounded(bounded_store, selected_ref, limits=limits)
    if not _same_ref(bounded.effective_ref, selected_ref):
        raise ValueError("owned_attempt_selected_profile_drift")
    manifest = bounded.manifest
    artifact_schema = manifest.artifact_schema
    if (
        manifest.kind != expected_kind
        or manifest.media_type != "application/json"
        or artifact_schema is None
        or artifact_schema.name != expected_schema_name
    ):
        raise ValueError("owned_attempt_artifact_manifest_identity_mismatch")
    parsed = validate_core_model_bounded_read(model, bounded)
    semantic_version = getattr(parsed, "schema_version", None)
    if type(semantic_version) is not str:
        raise ValueError("owned_attempt_semantic_schema_version_missing")
    try:
        semantic_kind, semantic_name, expected_manifest_version = (
            _observational_intent_manifest_identity(semantic_version)
        )
    except ValueError as exc:
        raise ValueError("owned_attempt_semantic_manifest_version_mismatch") from exc
    if (
        semantic_kind != expected_kind
        or semantic_name != expected_schema_name
        or artifact_schema.version != expected_manifest_version
    ):
        raise ValueError("owned_attempt_semantic_manifest_version_mismatch")
    return parsed


def _read_profiled_adapter[ValueT](
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    selected_ref: ArtifactRef,
    limits: CoreJsonReadLimits,
    adapter: TypeAdapter[ValueT],
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> ValueT:
    """Resolve an exact profiled artifact validated by a discriminated TypeAdapter."""
    _bounded, value = _read_profiled_value(
        service=service,
        selected_ref=selected_ref,
        limits=limits,
        expected_kind=expected_kind,
        expected_schema_name=expected_schema_name,
        expected_schema_version=expected_schema_version,
    )
    return adapter.validate_python(value, strict=True)


def _lifecycle_event(event: _ControlJobLifecycleSourceEventRecord) -> OwnedAttemptLifecycleEvent:
    """Copy only owner-issued event identity and digest into the anchor contract."""
    return OwnedAttemptLifecycleEvent.model_validate(
        {
            "event_id": event.event_id,
            "job_id": event.job_id,
            "event_type": event.event_type,
            "payload_sha256": event.payload_sha256,
            "created_at": event.created_at,
        },
        strict=True,
    )


def _check_live_attempt(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    work: MethodExecutionWork,
    admission: MethodExecutionAdmission,
) -> tuple[
    _ControlJobExecutionLifecycleProof,
    ControlJobExecutionAdmission,
    _ControlJobLifecycleSourceEventRecord,
    ControlJobExecutionScope,
]:
    """Reconcile the fenced running event, immutable creation event, and admitted scope."""
    control_store = service._control_store
    proof = control_store._current_execution_running_job_proof()
    admitted = control_store.current_execution_job_admission()
    job = proof.record
    created_event = control_store._get_job_created_source_event_record(job.job_id)
    running_event = proof.source_event
    scope = admitted.scope
    now = datetime.now(UTC)
    lease_expires_at = job.lease_expires_at
    running_payload = getattr(running_event, "payload", None)
    if (
        job.kind != "workflow_run"
        or job.state != "running"
        or job.job_id != work.job_id
        or job.run_id != work.run_id
        or job.attempt != work.attempt
        or admitted.job.job_id != job.job_id
        or admitted.job.run_id != job.run_id
        or admitted.job.attempt != job.attempt
        or proof.attempt is None
        or proof.attempt != job.attempt
        or proof.worker_id is None
        or proof.worker_id != job.lease_owner
        or not job.lease_owner
        or proof.proof_phase != "running"
        or getattr(running_event, "event_type", None) != "job_running"
        or getattr(running_event, "job_id", None) != job.job_id
        or not isinstance(running_payload, Mapping)
        or running_payload.get("state") != "running"
        or running_payload.get("lease_owner") != job.lease_owner
        or type(running_payload.get("attempt")) is not int
        or running_payload.get("attempt") != job.attempt
        or scope.status != "established"
        or scope.tenant_id is None
        or not scope.tenant_id
        or created_event.event_type != "job_created"
        or created_event.job_id != job.job_id
        or created_event.payload.get("run_id") != work.run_id
        or created_event.payload.get("job_kind") != "workflow_run"
        or lease_expires_at is None
        or lease_expires_at.tzinfo is None
        or lease_expires_at.utcoffset() is None
        or lease_expires_at <= now
    ):
        raise ValueError("owned_attempt_live_owner_fence_mismatch")
    return proof, admitted, created_event, scope


def _checked_live_attempt_values(
    proof: _ControlJobExecutionLifecycleProof,
    scope: ControlJobExecutionScope,
) -> tuple[str, int, str]:
    """Expose owner values only after the live-attempt verifier established them."""
    tenant_id = scope.tenant_id
    attempt = proof.attempt
    worker_id = proof.worker_id
    if tenant_id is None or attempt is None or worker_id is None:
        raise ValueError("owned_attempt_live_owner_fence_mismatch")
    return tenant_id, attempt, worker_id


def _selected_refs_from_creation_event(
    *, created_event: _ControlJobLifecycleSourceEventRecord, work: MethodExecutionWork
) -> tuple[ArtifactRef, ArtifactRef, str]:
    """Read the exact immutable job-created marker that R12 already owns."""
    payload = getattr(created_event, "payload", None)
    if not isinstance(payload, Mapping):
        raise ValueError("owned_attempt_creation_payload_not_established")
    marker = payload.get("observational_method_execution")
    if not isinstance(marker, Mapping):
        raise ValueError("owned_attempt_creation_intent_marker_missing")
    source_ref = _require_full_profile_ref(
        marker.get("requested_source_ref"),
        code="owned_attempt_creation_source_ref_invalid",
    )
    intent_ref = _require_full_profile_ref(
        marker.get("observational_run_intent_ref"),
        code="owned_attempt_creation_intent_ref_invalid",
    )
    digest = marker.get("observational_selection_digest")
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or source_ref != work.requested_source_ref
        or intent_ref != work.observational_run_intent_ref
    ):
        raise ValueError("owned_attempt_creation_selection_marker_mismatch")
    return source_ref, intent_ref, digest


def _read_intents(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    requested_intent_ref: ArtifactRef,
    content_admitted_ref: ArtifactRef,
) -> tuple[ObservationalRunIntent, ContentAdmittedObservationalRunIntent]:
    """Bound-read R12 v1/v2 intents and reconcile semantic with manifest versions."""
    from polisyos.core.contracts.runtime import (
        ContentAdmittedObservationalRunIntent,
        ObservationalRunIntent,
    )

    limits = service._observational_read_limits()
    requested = _read_versioned_profiled_model(
        service=service,
        selected_ref=requested_intent_ref,
        limits=limits,
        model=ObservationalRunIntent,
        expected_kind=_OBSERVATIONAL_INTENT_KIND,
        expected_schema_name=_OBSERVATIONAL_INTENT_SCHEMA,
    )
    admitted = _read_versioned_profiled_model(
        service=service,
        selected_ref=content_admitted_ref,
        limits=limits,
        model=ContentAdmittedObservationalRunIntent,
        expected_kind=_CONTENT_ADMITTED_INTENT_KIND,
        expected_schema_name=_CONTENT_ADMITTED_INTENT_SCHEMA,
    )
    requested_schema = getattr(requested, "schema_version", None)
    admitted_schema = getattr(admitted, "schema_version", None)
    if type(requested_schema) is not str or type(admitted_schema) is not str:
        raise ValueError("owned_attempt_intent_semantic_schema_version_missing")
    requested_version = requested_schema.rsplit(".v", maxsplit=1)[-1]
    admitted_version = admitted_schema.rsplit(".v", maxsplit=1)[-1]
    if requested_version != admitted_version:
        raise ValueError("owned_attempt_request_and_admission_schema_version_mismatch")
    _require_intent_request_context_pair(requested, admitted)
    return requested, admitted


def _require_intent_request_context_pair(
    requested_intent: ObservationalRunIntent,
    admitted_intent: ContentAdmittedObservationalRunIntent | None = None,
) -> None:
    """Enforce each exact request-only or paired owner-intent selector contract."""
    from polisyos.core.contracts.owned_attempt_anchor import OwnedHTERequestContextV1

    schema_version = getattr(requested_intent, "schema_version", None)
    request_context = getattr(requested_intent, "owned_hte_request_context", None)
    admitted_context = (
        getattr(admitted_intent, "owned_hte_request_context", None)
        if admitted_intent is not None
        else request_context
    )
    method_fqn = getattr(requested_intent, "method_fqn", None)
    method_version = getattr(requested_intent, "method_version", None)
    if admitted_intent is not None and (getattr(admitted_intent, "method_fqn", None) != method_fqn):
        raise ValueError("owned_attempt_request_and_admission_method_mismatch")

    legacy_methods = {"causal.hte.forest_dr@1.0.0", "causal.hte.forest_dr@1.1.0"}
    if schema_version == "polisyos.runtime.observational_run_intent.v1":
        if (
            request_context is not None
            or admitted_context is not None
            or method_fqn not in legacy_methods
            or method_version not in {"1.0.0", "1.1.0"}
        ):
            raise ValueError("owned_attempt_legacy_intent_context_or_method_mismatch")
        return
    if schema_version not in _SUCCESSOR_ANCHOR_INTENT_SCHEMAS:
        raise ValueError("owned_attempt_observational_intent_schema_not_supported")
    if (
        type(request_context) is not OwnedHTERequestContextV1
        or type(admitted_context) is not OwnedHTERequestContextV1
        or method_fqn not in _SUCCESSOR_ANCHOR_METHODS
        or method_version != _SUCCESSOR_ANCHOR_METHOD_VERSION
    ):
        raise ValueError("owned_attempt_successor_intent_context_or_method_missing")
    required_statuses = (
        "request_estimand_status",
        "request_target_scope_status",
        "outcome_variable_status",
        "treatment_variable_status",
        "contrast_status",
        "request_alpha_status",
    )
    if any(getattr(request_context, name) != "declared" for name in required_statuses):
        raise ValueError("owned_attempt_successor_request_selector_not_declared")
    if not _json_values_equal(
        request_context.model_dump(mode="json"),
        admitted_context.model_dump(mode="json"),
    ):
        raise ValueError("owned_attempt_request_and_admission_context_mismatch")
    if schema_version == "polisyos.runtime.observational_run_intent.v3":
        request_snapshot = getattr(requested_intent, "search_binding_admission", None)
        request_binding = request_context.search_uncertainty_task_binding_ref
        if (
            request_binding is None
            or request_snapshot is None
            or not _same_ref(request_binding, request_snapshot.binding_ref)
        ):
            raise ValueError("owned_attempt_request_search_snapshot_mismatch")
        if admitted_intent is not None:
            admitted_snapshot = getattr(admitted_intent, "search_binding_admission", None)
            if (
                request_snapshot != admitted_snapshot
                or getattr(admitted_intent, "schema_version", None)
                != "polisyos.runtime.content_admitted_observational_run_intent.v3"
            ):
                raise ValueError("owned_attempt_request_and_admission_search_snapshot_mismatch")


def _require_successor_anchor_intent_pair(
    requested_intent: ObservationalRunIntent,
    admitted_intent: ContentAdmittedObservationalRunIntent | None = None,
) -> None:
    """Refuse legacy intents before either successor anchor producer can write."""
    if getattr(requested_intent, "schema_version", None) not in _SUCCESSOR_ANCHOR_INTENT_SCHEMAS:
        raise OwnedAttemptAnchorVersionRefusalError()
    _require_intent_request_context_pair(requested_intent, admitted_intent)


def _read_requested_intent(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    requested_intent_ref: ArtifactRef,
) -> ObservationalRunIntent:
    """Resolve the immutable request side when content admission refused."""
    from polisyos.core.contracts.runtime import ObservationalRunIntent

    requested = _read_versioned_profiled_model(
        service=service,
        selected_ref=requested_intent_ref,
        limits=service._observational_read_limits(),
        model=ObservationalRunIntent,
        expected_kind=_OBSERVATIONAL_INTENT_KIND,
        expected_schema_name=_OBSERVATIONAL_INTENT_SCHEMA,
    )
    _require_intent_request_context_pair(requested)
    return requested


def _owner_request_context(
    requested_intent: ObservationalRunIntent | ContentAdmittedObservationalRunIntent,
) -> OwnedHTERequestContextV1:
    """Project only immutable request fields into HTE's strict selector model."""
    from polisyos.core.contracts.owned_attempt_anchor import OwnedHTERequestContextV1

    selected = getattr(requested_intent, "owned_hte_request_context", None)
    if selected is None:
        return OwnedHTERequestContextV1(
            request_estimand_status="not_established",
            request_estimand=None,
            request_target_scope_status="not_established",
            request_target_scope=None,
            outcome_variable_status="not_established",
            outcome_variable_id=None,
            treatment_variable_status="not_established",
            treatment_variable_id=None,
            contrast_status="not_established",
            control_value=None,
            treated_value=None,
            request_alpha_status="not_established",
            requested_alpha=None,
            requested_guarantee_status="not_established",
            requested_guarantee=None,
        )
    return OwnedHTERequestContextV1.model_validate(selected, strict=True)


def _request_context_projection(
    context: OwnedHTERequestContextV1 | None,
) -> dict[str, object] | None:
    """Project only immutable request selectors, excluding Runtime materialization evidence."""
    if context is None:
        return None
    payload = context.model_dump(mode="json")
    payload.pop("materialization_binding_ref", None)
    return payload


def _same_request_context(
    left: OwnedHTERequestContextV1 | None,
    right: OwnedHTERequestContextV1 | None,
) -> bool:
    """Compare request selectors without treating post-request input evidence as caller intent."""
    return _json_values_equal(
        _request_context_projection(left),
        _request_context_projection(right),
    )


def _resolve_physical_source_binding(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    binding_ref: ArtifactRef | None,
    submitted_ref: ArtifactRef,
    effective_ref: ArtifactRef,
    data: HTEObservationalData | None = None,
) -> tuple[OwnedAttemptPhysicalSourceBindingRef, HTEPhysicalSourceMaterializationBinding]:
    """Resolve the selected Foundry binding against exact inputs and optional worker data."""
    from polisyos.foundry.data_plane import (
        HTEInputPreparationRefusal,
        load_hte_physical_source_materialization_binding,
    )

    if binding_ref is None:
        raise ValueError("owned_attempt_physical_materialization_binding_missing")
    core_binding_ref = _require_full_profile_ref(
        binding_ref,
        code="owned_attempt_physical_materialization_binding_ref_invalid",
    )
    selected_ref = OwnedAttemptPhysicalSourceBindingRef.model_validate(
        core_binding_ref.model_dump(mode="python"),
        strict=True,
    )
    if selected_ref.manifest_profile_sha256 is None:
        raise ValueError("owned_attempt_physical_materialization_binding_profile_missing")
    limits = service._observational_read_limits()
    bounded_store = service._require_owned_attempt_anchor_bounded_store(limits=limits)
    try:
        binding = load_hte_physical_source_materialization_binding(
            store=bounded_store,
            binding_ref=core_binding_ref,
            expected_submitted_ref=submitted_ref,
            expected_effective_ref=effective_ref,
            limits=limits,
            expected_data=data,
        )
    except HTEInputPreparationRefusal as exc:
        raise ValueError(f"owned_attempt_physical_materialization_binding_{exc.code}") from exc
    if (
        binding.binding_scope != "physical_materialization_only"
        or binding.semantic_alignment_status != "not_established"
        or binding.submitted_ref != submitted_ref
        or binding.effective_ref != effective_ref
    ):
        raise ValueError("owned_attempt_physical_materialization_binding_content_mismatch")
    return selected_ref, binding


def _predicate_origins(
    request_context: OwnedHTERequestContextV1,
    *,
    input_content_recomputed: bool,
    required_estimator_n_jobs: int | None,
    execution_scope: Literal[
        "estimator_n_jobs_one",
        "producer_scoped_joblib_parallelism_one",
    ]
    | None,
    max_jobs: Literal[1] | None,
) -> OwnedAttemptPredicateOrigins:
    """Build P37 labels only after the owner source was read and reconciled."""

    def request_origin(
        status: Literal["declared", "not_established"],
    ) -> Literal["independently_reconciled", "not_established"]:
        return "independently_reconciled" if status == "declared" else "not_established"

    return OwnedAttemptPredicateOrigins(
        owner_attempt_fence="recomputed",
        lifecycle_event_chain="recomputed",
        requested_source_identity="independently_reconciled",
        selected_method_abi="independently_reconciled",
        selected_resource_policy="independently_reconciled",
        resolved_params_and_seed="independently_reconciled",
        selected_input_content=("recomputed" if input_content_recomputed else "not_established"),
        request_estimand=request_origin(request_context.request_estimand_status),
        request_target_scope=request_origin(request_context.request_target_scope_status),
        outcome_variable=request_origin(request_context.outcome_variable_status),
        treatment_variable=request_origin(request_context.treatment_variable_status),
        treatment_contrast=request_origin(request_context.contrast_status),
        requested_alpha=request_origin(request_context.request_alpha_status),
        requested_guarantee=request_origin(request_context.requested_guarantee_status),
        estimator_job_cap=(
            "independently_reconciled" if required_estimator_n_jobs == 1 else "not_established"
        ),
        selected_producer_job_cap=(
            "independently_reconciled"
            if execution_scope == "producer_scoped_joblib_parallelism_one" and max_jobs == 1
            else "not_established"
        ),
        actual_execution_resource_context="not_established",
        search_dependency_inventory="not_established",
        completed_output_owner_association="not_established",
    )


def _refusal_capture_from_exception(
    error: HTEInputPreparationRefusal,
) -> OwnedAttemptHTEInputRefusal:
    """Copy exact safe bounded fields from Core's genuine preparation refusal."""
    from polisyos.foundry.data_plane import HTEInputPreparationRefusal

    if type(error) is not HTEInputPreparationRefusal:
        raise TypeError("owned_attempt_exact_hte_input_preparation_refusal_required")
    usage = (
        error.observed_manifest_selection_bytes,
        error.observed_manifest_verification_bytes,
        error.observed_payload_bytes,
        error.observed_source_bytes,
    )
    if any(value is not None and (type(value) is not int or value < 0) for value in usage):
        raise ValueError("owned_attempt_refusal_usage_field_invalid")
    source_usage_complete = error.source_usage_complete
    payload_integrity_verified = error.payload_integrity_verified
    if type(source_usage_complete) is not bool or type(payload_integrity_verified) is not bool:
        raise ValueError("owned_attempt_refusal_usage_status_invalid")
    failure_code = error.code
    failure_stage = error.failure_stage
    if type(failure_code) is not str or (
        failure_stage is not None and type(failure_stage) is not str
    ):
        raise ValueError("owned_attempt_refusal_identity_invalid")
    return OwnedAttemptHTEInputRefusal(
        refusal_code=failure_code,
        failure_stage=failure_stage,
        observed_manifest_selection_bytes=error.observed_manifest_selection_bytes,
        observed_manifest_verification_bytes=error.observed_manifest_verification_bytes,
        observed_payload_bytes=error.observed_payload_bytes,
        observed_source_bytes=error.observed_source_bytes,
        source_usage_complete=source_usage_complete,
        payload_integrity_verified=payload_integrity_verified,
    )


def _read_selected_resource_policy(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    requested_intent: ObservationalRunIntent,
    content_intent: ContentAdmittedObservationalRunIntent | None,
    admission: MethodExecutionAdmission | None = None,
) -> tuple[ArtifactRef, ObservationalInputResourcePolicy]:
    """Resolve the exact Runtime policy artifact and reconcile its immutable pins."""
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _read_observational_resource_policy_artifact,
    )

    policy_ref_value = getattr(requested_intent, "resource_policy_ref", None)
    if policy_ref_value is None:
        raise ValueError("owned_attempt_resource_policy_ref_not_established")
    policy_ref = _require_full_profile_ref(
        policy_ref_value,
        code="owned_attempt_resource_policy_ref_invalid",
    )
    requested_source_ref = _require_full_profile_ref(
        requested_intent.requested_source_ref,
        code="owned_attempt_requested_source_ref_invalid",
    )
    if (
        content_intent is not None
        and not _same_ref(policy_ref, getattr(content_intent, "resource_policy_ref", None))
    ) or (admission is not None and not _same_ref(policy_ref, admission.resource_policy_ref)):
        raise ValueError("owned_attempt_resource_policy_owner_ref_mismatch")
    limits = service._observational_read_limits()
    bounded_store = service._require_owned_attempt_anchor_bounded_store(limits=limits)
    policy = _read_observational_resource_policy_artifact(
        store=bounded_store,
        policy_ref=policy_ref,
        source_ref=requested_source_ref,
        source_governance=requested_intent.source_governance,
        source_tenant_context=requested_intent.source_tenant_context,
        limits=limits,
    )
    policy_digest = policy.digest()
    if (
        policy != requested_intent.resource_policy
        or policy_digest != requested_intent.resource_policy_digest
        or (
            content_intent is not None
            and policy_digest != getattr(content_intent, "resource_policy_digest", None)
        )
        or (admission is not None and policy_digest != admission.resource_policy_digest)
    ):
        raise ValueError("owned_attempt_resource_policy_content_mismatch")
    return policy_ref, policy


def persist_pre_output_owned_attempt_anchor(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    work: MethodExecutionWork,
    admission: MethodExecutionAdmission,
    prepared: PreparedHTEObservationalInput,
    content_admitted_intent_ref: ArtifactRef,
    method_class: type,
) -> OwnedAttemptAnchorDispatchContext:
    """Persist an acyclic anchor from Runtime owner state and actual prepared HTE input.

    Call this after the typed HTE input and content-admitted intent exist, and
    immediately before estimator dispatch. Input facts are recomputed by the
    HTE-owned capture factory; request selectors come only from the immutable
    Runtime intent and are rechecked against that capture.

    Raises:
        ValueError: If any owner fence, selected profile, request pin, or input
            capture cannot be reconciled before dispatch.
    """
    from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.owned_attempt_anchor import OwnedHTERequestContextV1
    from polisyos.core.contracts.runtime import _expected_content_admitted_limitations

    initial_proof, initial_admission, created_event, scope = _check_live_attempt(
        service=service,
        work=work,
        admission=admission,
    )
    scope_tenant_id, _, _ = _checked_live_attempt_values(initial_proof, scope)
    source_ref, requested_intent_ref, creation_selection_digest = (
        _selected_refs_from_creation_event(created_event=created_event, work=work)
    )
    content_ref = _selected_profile_ref(
        content_admitted_intent_ref,
        code="owned_attempt_content_intent_ref_invalid",
    )
    requested_intent, content_intent = _read_intents(
        service=service,
        requested_intent_ref=requested_intent_ref,
        content_admitted_ref=content_ref,
    )
    _require_successor_anchor_intent_pair(requested_intent, content_intent)
    signature = getattr(method_class, "signature", None)
    request_context = _owner_request_context(requested_intent)
    if type(request_context) is not OwnedHTERequestContextV1:
        raise ValueError("owned_attempt_request_context_type_mismatch")
    resource_policy_ref, selected_resource_policy = _read_selected_resource_policy(
        service=service,
        requested_intent=requested_intent,
        content_intent=content_intent,
        admission=admission,
    )
    materialization_binding_ref = None
    raw_materialization_binding_ref = getattr(prepared, "materialization_binding_ref", None)
    if selected_resource_policy.revision == "r5" or raw_materialization_binding_ref is not None:
        materialization_binding_ref, _ = _resolve_physical_source_binding(
            service=service,
            binding_ref=raw_materialization_binding_ref,
            submitted_ref=prepared.submitted_ref,
            effective_ref=prepared.effective_ref,
            data=prepared.data,
        )
        request_context = request_context.model_copy(
            update={"materialization_binding_ref": materialization_binding_ref}
        )
    if (
        type(prepared.payload_integrity_verified) is not bool
        or not prepared.payload_integrity_verified
        or prepared.effective_ref.manifest_profile_sha256 is None
        or not _same_ref(prepared.effective_ref, content_intent.effective_input_ref)
        or not _same_ref(prepared.submitted_ref, content_intent.submitted_input_ref)
        or not _same_ref(source_ref, requested_intent.requested_source_ref)
        or not _same_ref(requested_intent_ref, content_intent.requested_intent_ref)
        or requested_intent.selection_digest() != creation_selection_digest
        or content_intent.selection_digest != creation_selection_digest
        or not _same_request_context(_owner_request_context(content_intent), request_context)
        or requested_intent.job_id != work.job_id
        or requested_intent.run_id != work.run_id
        or content_intent.job_id != work.job_id
        or content_intent.run_id != work.run_id
        or content_intent.attempt != work.attempt
        or content_intent.source_manifest_sha256 != requested_intent.source_manifest_sha256
        or not _same_ref(content_intent.resource_policy_ref, requested_intent.resource_policy_ref)
        or content_intent.resource_policy_digest != requested_intent.resource_policy_digest
        or content_intent.method_fqn != requested_intent.method_fqn
        or admission.method_fqn != requested_intent.method_fqn
        or admission.method_version != requested_intent.method_version
        or content_intent.source_protocol != requested_intent.protocol
        or signature is None
        or signature.fqn != admission.method_fqn
        or signature.version != admission.method_version
        or requested_intent.method_abi_digest != admission.method_abi_digest
        or requested_intent.method_build_digest != admission.method_build_digest
        or not _json_values_equal(
            requested_intent.resolved_params, dict(admission.effective_params)
        )
        or requested_intent.seed != admission.seed
        or prepared.method_fqn != admission.method_fqn
        or prepared.source_protocol != requested_intent.protocol
        or prepared.source_governance != requested_intent.source_governance
        or content_intent.source_governance != requested_intent.source_governance
        or prepared.source_tenant_context != requested_intent.source_tenant_context
        or prepared.write_tenant_context != admission.derived_tenant_context
        or content_intent.source_tenant_context != requested_intent.source_tenant_context
        or content_intent.payload_integrity_verified is not True
        or content_intent.observed_manifest_bytes != prepared.observed_manifest_bytes
        or content_intent.observed_manifest_selection_bytes
        != prepared.observed_manifest_selection_bytes
        or content_intent.observed_manifest_verification_bytes
        != prepared.observed_manifest_verification_bytes
        or content_intent.observed_payload_bytes != prepared.observed_payload_bytes
        or content_intent.observed_source_bytes != prepared.observed_source_bytes
        or content_intent.observed_bytes != prepared.observed_bytes
        or content_intent.observed_depth != prepared.observed_depth
        or content_intent.observed_elements != prepared.observed_elements
        or content_intent.contract_target_id != prepared.contract_target.contract_id
        or content_intent.contract_target_id != requested_intent.contract_target_id
        or prepared.contract_target.contract_fqn != requested_intent.contract_target_fqn
        or content_intent.contract_target != requested_intent.contract_target_fqn
        or prepared.limitations
        != (
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            *(
                ("legacy_hte_json_v1_source_normalized",)
                if prepared.source_protocol == "legacy_hte_json_v1"
                else ()
            ),
        )
        or content_intent.limitations
        != _expected_content_admitted_limitations(
            content_intent.source_protocol,
            source_access_revalidation_status=content_intent.source_access_revalidation_status,
        )
        or admission.derived_tenant_context
        != ArtifactTenantContextInfo(tenant_id=scope_tenant_id, cell_id=scope.cell_id)
    ):
        raise ValueError("owned_attempt_prepared_input_intent_binding_mismatch")
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        build_owned_hte_input_capture,
    )
    from polisyos.ir.analytics import HTEInputSourceRef

    capture_value = build_owned_hte_input_capture(
        prepared.data,
        source_data_ref=HTEInputSourceRef.model_validate(
            prepared.effective_ref.model_dump(mode="python"),
            strict=True,
        ),
        method_class=method_class,
        method_abi_digest=admission.method_abi_digest,
        resolved_params=admission.effective_params,
        seed=admission.seed,
        request_context=request_context,
    )
    capture_payload = capture_value.model_dump(mode="json")
    if capture_value.source_feature_names is not None:
        capture_payload["source_feature_names"] = capture_value.source_feature_names
    if materialization_binding_ref is not None:
        capture_payload["materialization_binding_ref"] = materialization_binding_ref.model_dump(
            mode="json"
        )
        capture_payload["request_context"]["materialization_binding_ref"] = (
            materialization_binding_ref.model_dump(mode="json")
        )
    capture = OwnedAttemptHTEInputCapture.model_validate(capture_payload, strict=True)
    params_digest = _resolved_params_digest(capture.resolved_params, capture.seed)
    if (
        not _same_ref(capture.source_data_ref, prepared.effective_ref)
        or capture.method_fqn != signature.fqn
        or capture.method_abi != signature.version
        or capture.method_abi_digest != admission.method_abi_digest
        or capture.resolved_params_sha256 != params_digest
        or not _same_request_context(capture.request_context, request_context)
        or not _json_values_equal(capture.resolved_params, requested_intent.resolved_params)
        or capture.seed != requested_intent.seed
    ):
        raise ValueError("owned_attempt_hte_capture_reconciliation_failed")

    # Re-read the same owner fence at the write boundary. This prevents a long
    # capture/read phase from turning an expired or superseded lease into a new
    # owner artifact.
    final_proof, final_admission, final_created_event, final_scope = _check_live_attempt(
        service=service,
        work=work,
        admission=admission,
    )
    final_tenant_id, final_attempt, final_worker_id = _checked_live_attempt_values(
        final_proof, final_scope
    )
    if (
        final_proof.record.job_id != initial_proof.record.job_id
        or final_proof.record.attempt != initial_proof.record.attempt
        or final_proof.worker_id != initial_proof.worker_id
        or final_created_event.event_id != created_event.event_id
        or final_scope != scope
        or final_admission.job.job_id != initial_admission.job.job_id
    ):
        raise ValueError("owned_attempt_owner_fence_changed_before_persist")
    captured_at = datetime.now(UTC)
    lease_expires_at = final_proof.record.lease_expires_at
    if lease_expires_at is None or lease_expires_at <= captured_at:
        raise ValueError("owned_attempt_lease_expired_before_persist")
    anchor = OwnedAttemptAnchor(
        captured_at=captured_at,
        job_id=work.job_id,
        run_id=work.run_id,
        tenant_id=final_tenant_id,
        cell_id=final_scope.cell_id,
        attempt=final_attempt,
        worker_id=final_worker_id,
        lease_expires_at=lease_expires_at,
        job_created_event=_lifecycle_event(created_event),
        job_running_event=_lifecycle_event(final_proof.source_event),
        requested_source_ref=_selected_profile_ref(
            source_ref,
            code="owned_attempt_source_ref_invalid",
        ),
        observational_run_intent_ref=_selected_profile_ref(
            requested_intent_ref,
            code="owned_attempt_request_intent_ref_invalid",
        ),
        resource_policy_ref=_selected_profile_ref(
            resource_policy_ref,
            code="owned_attempt_resource_policy_ref_invalid",
        ),
        selection_digest=creation_selection_digest,
        source_manifest_sha256=requested_intent.source_manifest_sha256,
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=requested_intent.method_abi_digest,
        method_build_digest=requested_intent.method_build_digest,
        resource_policy_digest=requested_intent.resource_policy_digest,
        resource_policy_schema_version=selected_resource_policy.schema_version,
        resource_policy_revision=selected_resource_policy.revision,
        resource_policy_method_contract_target=selected_resource_policy.method_contract_target,
        resource_policy_required_estimator_n_jobs=(
            selected_resource_policy.required_estimator_n_jobs
        ),
        resource_policy_method_fqn=getattr(selected_resource_policy, "method_fqn", None),
        resource_policy_method_profile_id=getattr(
            selected_resource_policy, "method_profile_id", None
        ),
        resource_policy_execution_scope=getattr(selected_resource_policy, "execution_scope", None),
        resource_policy_max_jobs=getattr(selected_resource_policy, "max_jobs", None),
        source_protocol=content_intent.source_protocol,
        resolved_params_sha256=params_digest,
        request_context=request_context,
        input_admission=OwnedAttemptHTEInputAdmitted(
            content_admitted_intent_ref=content_ref,
            submitted_input_ref=_selected_profile_ref(
                content_intent.submitted_input_ref,
                code="owned_attempt_submitted_input_ref_invalid",
            ),
            effective_input_ref=_selected_profile_ref(
                content_intent.effective_input_ref,
                code="owned_attempt_effective_input_ref_invalid",
            ),
            normalization=content_intent.normalization,
            input_capture=capture,
        ),
        predicate_origins=_predicate_origins(
            request_context,
            input_content_recomputed=True,
            required_estimator_n_jobs=selected_resource_policy.required_estimator_n_jobs,
            execution_scope=getattr(selected_resource_policy, "execution_scope", None),
            max_jobs=getattr(selected_resource_policy, "max_jobs", None),
        ),
    )
    _require_search_binding_manifest(service=service, anchor=anchor)
    tenant_context = ArtifactTenantContextInfo(
        tenant_id=final_tenant_id,
        cell_id=final_scope.cell_id,
    )
    upstream_refs = [
        input_ref_from_artifact_ref(anchor.requested_source_ref, role="requested_source"),
        input_ref_from_artifact_ref(
            anchor.observational_run_intent_ref,
            role="observational_run_intent",
        ),
        input_ref_from_artifact_ref(
            anchor.content_admitted_intent_ref,
            role="content_admitted_intent",
        ),
        input_ref_from_artifact_ref(anchor.resource_policy_ref, role="resource_policy"),
        *(
            input_ref_from_artifact_ref(ref, role=role)
            for ref, role in _search_binding_input(anchor)
        ),
        input_ref_from_artifact_ref(anchor.submitted_input_ref, role="submitted_input"),
        input_ref_from_artifact_ref(anchor.effective_input_ref, role="effective_input"),
        *(
            [
                input_ref_from_artifact_ref(
                    materialization_binding_ref,
                    role="physical_source_materialization_binding",
                )
            ]
            if materialization_binding_ref is not None
            else []
        ),
    ]
    stored_ref = service._artifact_store.put_json(
        anchor.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=OWNED_ATTEMPT_ANCHOR_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME,
                version=OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION,
            ),
            inputs=upstream_refs,
            governance=requested_intent.source_governance,
            tenant_context=tenant_context,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    anchor_ref = _owned_attempt_anchor_ref(
        stored_ref,
        code="owned_attempt_anchor_selected_profile_ref_invalid",
    )
    if anchor_ref.manifest_profile_sha256 is None:
        raise ValueError("owned_attempt_anchor_selected_profile_not_returned")
    record_owner = getattr(service._artifact_store, "record_artifact_owner", None)
    if not callable(record_owner):
        raise RuntimeError("owned_attempt_anchor_tenant_owner_record_unavailable")
    record_owner(
        anchor_ref.artifact_id,
        tenant_id=final_tenant_id,
        cell_id=final_scope.cell_id,
        writer="runtime.control.owned_attempt_anchor",
    )
    persisted = _read_owned_attempt_anchor(
        service=service,
        anchor_ref=anchor_ref,
    )
    if persisted != anchor:
        raise ValueError("owned_attempt_anchor_persisted_content_mismatch")
    (
        final_after_write,
        _admitted_after_write,
        _created_after_write,
        _scope_after_write,
    ) = _check_live_attempt(service=service, work=work, admission=admission)
    if (
        final_after_write.record.job_id != work.job_id
        or final_after_write.attempt != work.attempt
        or final_after_write.worker_id != anchor.worker_id
    ):
        raise ValueError("owned_attempt_owner_fence_lost_after_persist")
    return OwnedAttemptAnchorDispatchContext(
        anchor_ref=anchor_ref,
        input_capture=persisted.input_capture,
        method_abi_digest=persisted.method_abi_digest,
    )


def persist_pre_output_hte_input_refusal_anchor(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    work: MethodExecutionWork,
    admission: MethodExecutionAdmission,
    refusal: HTEInputPreparationRefusal,
    method_class: type,
) -> OwnedAttemptAnchorRef:
    """Persist a fenced refusal before content-admitted intent or estimator fit.

    Only the exact Core ``HTEInputPreparationRefusal`` type is accepted. The
    artifact records its safe code/stage and bounded source-usage fields, but
    does not fabricate a content-admitted ref, effective input ref, selected
    row count, method result, or evidence ref. For an empty prepared input,
    Runtime must create this exact typed refusal before persisting an admitted
    intent and must not include the observed zero as a selected-row count.
    """
    from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec

    refusal_value = _refusal_capture_from_exception(refusal)
    initial_proof, initial_admission, created_event, scope = _check_live_attempt(
        service=service,
        work=work,
        admission=admission,
    )
    scope_tenant_id, _, _ = _checked_live_attempt_values(initial_proof, scope)
    source_ref, requested_intent_ref, creation_selection_digest = (
        _selected_refs_from_creation_event(created_event=created_event, work=work)
    )
    requested_intent = _read_requested_intent(
        service=service,
        requested_intent_ref=requested_intent_ref,
    )
    _require_successor_anchor_intent_pair(requested_intent)
    signature = getattr(method_class, "signature", None)
    request_context = _owner_request_context(requested_intent)
    if (
        requested_intent.job_id != work.job_id
        or requested_intent.run_id != work.run_id
        or not _same_ref(source_ref, requested_intent.requested_source_ref)
        or not _same_ref(source_ref, work.requested_source_ref)
        or requested_intent.selection_digest() != creation_selection_digest
        or requested_intent.method_fqn != admission.method_fqn
        or requested_intent.method_version != admission.method_version
        or requested_intent.method_abi_digest != admission.method_abi_digest
        or requested_intent.method_build_digest != admission.method_build_digest
        or not _json_values_equal(
            requested_intent.resolved_params, dict(admission.effective_params)
        )
        or requested_intent.seed != admission.seed
        or signature is None
        or signature.fqn != admission.method_fqn
        or signature.version != admission.method_version
        or requested_intent.protocol != admission.protocol
        or admission.derived_tenant_context
        != ArtifactTenantContextInfo(tenant_id=scope_tenant_id, cell_id=scope.cell_id)
    ):
        raise ValueError("owned_attempt_refusal_request_binding_mismatch")
    policy_ref, selected_resource_policy = _read_selected_resource_policy(
        service=service,
        requested_intent=requested_intent,
        content_intent=None,
        admission=admission,
    )
    final_proof, final_admission, final_created_event, final_scope = _check_live_attempt(
        service=service,
        work=work,
        admission=admission,
    )
    final_tenant_id, final_attempt, final_worker_id = _checked_live_attempt_values(
        final_proof, final_scope
    )
    if (
        final_proof.record.job_id != initial_proof.record.job_id
        or final_proof.record.attempt != initial_proof.record.attempt
        or final_proof.worker_id != initial_proof.worker_id
        or final_created_event.event_id != created_event.event_id
        or final_scope != scope
        or final_admission.job.job_id != initial_admission.job.job_id
    ):
        raise ValueError("owned_attempt_owner_fence_changed_before_refusal_persist")
    captured_at = datetime.now(UTC)
    lease_expires_at = final_proof.record.lease_expires_at
    if lease_expires_at is None or lease_expires_at <= captured_at:
        raise ValueError("owned_attempt_lease_expired_before_refusal_persist")
    params_digest = _resolved_params_digest(admission.effective_params, admission.seed)
    anchor = OwnedAttemptAnchor(
        captured_at=captured_at,
        job_id=work.job_id,
        run_id=work.run_id,
        tenant_id=final_tenant_id,
        cell_id=final_scope.cell_id,
        attempt=final_attempt,
        worker_id=final_worker_id,
        lease_expires_at=lease_expires_at,
        job_created_event=_lifecycle_event(created_event),
        job_running_event=_lifecycle_event(final_proof.source_event),
        requested_source_ref=_selected_profile_ref(
            source_ref, code="owned_attempt_source_ref_invalid"
        ),
        observational_run_intent_ref=_selected_profile_ref(
            requested_intent_ref, code="owned_attempt_request_intent_ref_invalid"
        ),
        resource_policy_ref=_selected_profile_ref(
            policy_ref, code="owned_attempt_resource_policy_ref_invalid"
        ),
        selection_digest=creation_selection_digest,
        source_manifest_sha256=requested_intent.source_manifest_sha256,
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=requested_intent.method_abi_digest,
        method_build_digest=requested_intent.method_build_digest,
        resource_policy_digest=requested_intent.resource_policy_digest,
        resource_policy_schema_version=selected_resource_policy.schema_version,
        resource_policy_revision=selected_resource_policy.revision,
        resource_policy_method_contract_target=selected_resource_policy.method_contract_target,
        resource_policy_required_estimator_n_jobs=(
            selected_resource_policy.required_estimator_n_jobs
        ),
        resource_policy_method_fqn=getattr(selected_resource_policy, "method_fqn", None),
        resource_policy_method_profile_id=getattr(
            selected_resource_policy, "method_profile_id", None
        ),
        resource_policy_execution_scope=getattr(selected_resource_policy, "execution_scope", None),
        resource_policy_max_jobs=getattr(selected_resource_policy, "max_jobs", None),
        source_protocol=requested_intent.protocol,
        resolved_params_sha256=params_digest,
        request_context=request_context,
        input_admission=OwnedAttemptHTEInputRefused(refusal=refusal_value),
        predicate_origins=_predicate_origins(
            request_context,
            input_content_recomputed=False,
            required_estimator_n_jobs=selected_resource_policy.required_estimator_n_jobs,
            execution_scope=getattr(selected_resource_policy, "execution_scope", None),
            max_jobs=getattr(selected_resource_policy, "max_jobs", None),
        ),
    )
    _require_search_binding_manifest(service=service, anchor=anchor)
    tenant_context = ArtifactTenantContextInfo(
        tenant_id=final_tenant_id,
        cell_id=final_scope.cell_id,
    )
    upstream_refs = (
        input_ref_from_artifact_ref(anchor.requested_source_ref, role="requested_source"),
        input_ref_from_artifact_ref(
            anchor.observational_run_intent_ref,
            role="observational_run_intent",
        ),
        input_ref_from_artifact_ref(anchor.resource_policy_ref, role="resource_policy"),
        *(
            input_ref_from_artifact_ref(ref, role=role)
            for ref, role in _search_binding_input(anchor)
        ),
    )
    stored_ref = service._artifact_store.put_json(
        anchor.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=OWNED_ATTEMPT_ANCHOR_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME,
                version=OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION,
            ),
            inputs=list(upstream_refs),
            governance=requested_intent.source_governance,
            tenant_context=tenant_context,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    anchor_ref = _owned_attempt_anchor_ref(
        stored_ref,
        code="owned_attempt_refusal_anchor_selected_profile_ref_invalid",
    )
    if anchor_ref.manifest_profile_sha256 is None:
        raise ValueError("owned_attempt_anchor_selected_profile_not_returned")
    record_owner = getattr(service._artifact_store, "record_artifact_owner", None)
    if not callable(record_owner):
        raise RuntimeError("owned_attempt_anchor_tenant_owner_record_unavailable")
    record_owner(
        anchor_ref.artifact_id,
        tenant_id=final_tenant_id,
        cell_id=final_scope.cell_id,
        writer="runtime.control.owned_attempt_anchor",
    )
    persisted = _read_owned_attempt_anchor(service=service, anchor_ref=anchor_ref)
    if persisted != anchor:
        raise ValueError("owned_attempt_anchor_persisted_content_mismatch")
    after_write, _admitted_after_write, _created_after_write, _scope_after_write = (
        _check_live_attempt(service=service, work=work, admission=admission)
    )
    if (
        after_write.record.job_id != work.job_id
        or after_write.attempt != work.attempt
        or after_write.worker_id != anchor.worker_id
    ):
        raise ValueError("owned_attempt_owner_fence_lost_after_refusal_persist")
    return anchor_ref


def _read_owned_attempt_anchor(
    *, service: OwnedAttemptAnchorRuntimeHost, anchor_ref: OwnedAttemptAnchorRef
) -> OwnedAttemptAnchor:
    """Resolve one exact anchor CAS profile through Core's owner-declared validator."""
    from polisyos.core.artifacts import validate_core_model_bounded_read
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref

    bounded, _raw = _read_profiled_value(
        service=service,
        selected_ref=anchor_ref,
        limits=service._observational_read_limits(),
        expected_kind=OWNED_ATTEMPT_ANCHOR_KIND,
        expected_schema_name=OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME,
        expected_schema_version=OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION,
    )
    anchor = validate_core_model_bounded_read(OwnedAttemptAnchor, bounded)
    _require_search_binding_manifest(service=service, anchor=anchor)
    expected_inputs = [
        input_ref_from_artifact_ref(anchor.requested_source_ref, role="requested_source"),
        input_ref_from_artifact_ref(
            anchor.observational_run_intent_ref,
            role="observational_run_intent",
        ),
    ]
    if isinstance(anchor.input_admission, OwnedAttemptHTEInputAdmitted):
        expected_inputs.append(
            input_ref_from_artifact_ref(
                anchor.content_admitted_intent_ref,
                role="content_admitted_intent",
            )
        )
    expected_inputs.append(
        input_ref_from_artifact_ref(anchor.resource_policy_ref, role="resource_policy")
    )
    expected_inputs.extend(
        input_ref_from_artifact_ref(ref, role=role) for ref, role in _search_binding_input(anchor)
    )
    if isinstance(anchor.input_admission, OwnedAttemptHTEInputAdmitted):
        expected_inputs.extend(
            (
                input_ref_from_artifact_ref(anchor.submitted_input_ref, role="submitted_input"),
                input_ref_from_artifact_ref(anchor.effective_input_ref, role="effective_input"),
            )
        )
        expected_inputs.extend(
            input_ref_from_artifact_ref(ref, role=role)
            for ref, role in _physical_binding_input(anchor)
        )
    if tuple(bounded.manifest.inputs) != tuple(expected_inputs):
        raise ValueError("owned_attempt_anchor_manifest_lineage_mismatch")
    return anchor


def _json_values_equal(left: object, right: object) -> bool:
    """Compare JSON owner rows without coercion, allowing no non-finite values."""
    try:
        left_bytes = json.dumps(
            left,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        right_bytes = json.dumps(
            right,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return False
    return left_bytes == right_bytes


def _numeric_values_match(left: object, right: object) -> bool:
    """Compare two finite numeric copies using the HTE contract tolerance."""
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False
    return (
        math.isfinite(float(left))
        and math.isfinite(float(right))
        and math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1.0e-12)
    )


@overload
def _selection_ref(
    selection: DirectMethodExecutionSelection,
    name: str,
    *,
    required: Literal[True],
) -> SelectedArtifactRef: ...


@overload
def _selection_ref(
    selection: DirectMethodExecutionSelection,
    name: str,
    *,
    required: Literal[False],
) -> SelectedArtifactRef | None: ...


def _selection_ref(
    selection: DirectMethodExecutionSelection,
    name: str,
    *,
    required: bool,
) -> SelectedArtifactRef | None:
    """Read one strict full-profile artifact ref from the typed owner selection."""
    raw = getattr(selection, name, None)
    if raw is None:
        if required:
            raise ValueError(f"owned_attempt_owner_selection_ref_missing:{name}")
        return None
    return _selected_profile_ref(raw, code=f"owned_attempt_owner_selection_ref_invalid:{name}")


def _required_projection_ref(ref: SelectedArtifactRef | None, *, code: str) -> SelectedArtifactRef:
    """Narrow one ref after the matching projection branch has been checked."""
    if ref is None:
        raise ValueError(code)
    return ref


def _outcome_matches_anchor(outcome: HTEOutcome, anchor: OwnedAttemptAnchor) -> bool:
    """Reconcile HTE output selectors and input hashes to the pre-output anchor."""
    capture = anchor.input_capture
    request_context = capture.request_context
    expected_fields = (
        ("method_fqn", capture.method_fqn),
        ("method_abi", capture.method_abi),
        ("method_abi_digest", capture.method_abi_digest),
        ("method_profile_id", capture.method_profile_id),
        ("input_profile_id", capture.input_profile_id),
        ("selected_input_sha256", capture.selected_input_sha256),
        ("selected_rows_sha256", capture.selected_rows_sha256),
        ("selected_x_sha256", capture.selected_x_sha256),
        ("selected_row_order_sha256", capture.selected_row_order_sha256),
        ("resolved_params_sha256", capture.resolved_params_sha256),
        ("n_selected_rows", capture.n_selected_rows),
        ("request_estimand_status", request_context.request_estimand_status),
        ("request_estimand", request_context.request_estimand),
        ("request_target_scope_status", request_context.request_target_scope_status),
        ("request_target_scope", request_context.request_target_scope),
        ("outcome_variable_status", request_context.outcome_variable_status),
        ("outcome_variable_id", request_context.outcome_variable_id),
        ("treatment_variable_status", request_context.treatment_variable_status),
        ("treatment_variable_id", request_context.treatment_variable_id),
        ("request_alpha_status", request_context.request_alpha_status),
        ("requested_alpha", request_context.requested_alpha),
        ("requested_guarantee_status", request_context.requested_guarantee_status),
        ("requested_guarantee", request_context.requested_guarantee),
        (
            "contrast_status",
            "established" if request_context.contrast_status == "declared" else "not_established",
        ),
        ("control_value", request_context.control_value),
        ("treated_value", request_context.treated_value),
    )
    kind = getattr(outcome, "kind", None)
    if kind in {"point_estimate", "interval_estimate"}:
        for name, expected in expected_fields:
            if not hasattr(outcome, name):
                return False
            actual = getattr(outcome, name)
            if name in {"control_value", "treated_value", "requested_alpha"}:
                if not _optional_numeric_values_match(actual, expected):
                    return False
            elif actual != expected:
                return False
        if getattr(outcome, "authority_status", None) != "candidate":
            return False
        if not _same_ref(getattr(outcome, "source_data_ref", None), capture.source_data_ref):
            return False
        point = getattr(outcome, "point_estimate", None)
        if point is None:
            return False
        return (
            getattr(point, "estimand", None) == "mean_effect_over_selected_x"
            and getattr(point, "computed_target_scope_status", None) == "recomputed"
            and getattr(point, "computed_target_scope", None) == "selected_evaluation_rows"
        )
    if kind == "refusal":
        refusal_fields = (
            ("method_fqn", capture.method_fqn),
            ("method_abi", capture.method_abi),
            ("method_abi_digest", capture.method_abi_digest),
            ("method_profile_id", capture.method_profile_id),
            ("anchor_status", "pre_output_anchor_resolved"),
            ("requested_source_status", "declared"),
            ("request_estimand_status", request_context.request_estimand_status),
            ("request_estimand", request_context.request_estimand),
            ("request_target_scope_status", request_context.request_target_scope_status),
            ("request_target_scope", request_context.request_target_scope),
            ("outcome_variable_status", request_context.outcome_variable_status),
            ("outcome_variable_id", request_context.outcome_variable_id),
            ("treatment_variable_status", request_context.treatment_variable_status),
            ("treatment_variable_id", request_context.treatment_variable_id),
            ("request_alpha_status", request_context.request_alpha_status),
            ("requested_alpha", request_context.requested_alpha),
            ("requested_guarantee_status", request_context.requested_guarantee_status),
            ("requested_guarantee", request_context.requested_guarantee),
            (
                "contrast_status",
                "established"
                if request_context.contrast_status == "declared"
                else "not_established",
            ),
            ("control_value", request_context.control_value),
            ("treated_value", request_context.treated_value),
        )
        for name, expected in refusal_fields:
            if name == "owned_attempt_anchor_ref":
                # Compare the actual selected ref with the anchor ref at the callsite.
                continue
            if not hasattr(outcome, name):
                return False
            actual = getattr(outcome, name)
            if name in {"control_value", "treated_value", "requested_alpha"}:
                if not _optional_numeric_values_match(actual, expected):
                    return False
            elif actual != expected:
                return False
        if getattr(outcome, "authority_status", None) != "refusal":
            return False
        if not _same_ref(
            getattr(outcome, "requested_source_ref", None), anchor.requested_source_ref
        ):
            return False
        if getattr(outcome, "source_data_status", None) == "content_bound":
            if not _same_ref(getattr(outcome, "source_data_ref", None), capture.source_data_ref):
                return False
        elif (
            getattr(outcome, "source_data_status", None) != "not_established"
            or getattr(outcome, "source_data_ref", None) is not None
        ):
            return False
        row_fields = (
            "input_profile_id",
            "selected_input_sha256",
            "selected_rows_sha256",
            "selected_x_sha256",
            "selected_row_order_sha256",
            "resolved_params_sha256",
            "n_selected_rows",
        )
        if getattr(outcome, "selected_rows_status", None) == "recomputed":
            if any(
                getattr(outcome, name, None) != getattr(capture, name, None) for name in row_fields
            ):
                return False
        elif getattr(outcome, "selected_rows_status", None) != "not_established" or any(
            getattr(outcome, name, None) is not None for name in row_fields
        ):
            return False
        return getattr(outcome, "point_estimate", None) is None
    return False


def _optional_numeric_values_match(left: object, right: object) -> bool:
    """Compare optional finite numeric request fields without bool coercion."""
    if left is None or right is None:
        return left is None and right is None
    return _numeric_values_match(left, right)


def _request_context_fields(context: OwnedHTERequestContextV1) -> dict[str, object]:
    """Flatten the owner request context using its Runtime/HTE capture field names."""
    return context.model_dump(mode="json")


def _capture_matches_writer_ready(
    *,
    writer_capture: _CaptureFactsV1,
    anchor: OwnedAttemptAnchor,
    anchor_ref: OwnedAttemptAnchorRef,
) -> bool:
    """Reconcile every writer-ready input fact to Runtime's pre-output capture."""
    capture = anchor.input_capture
    request_values = _request_context_fields(capture.request_context)
    expected = {
        "source_data_ref": capture.source_data_ref.model_dump(mode="json"),
        "source_data_ref_status": "capture_matched",
        "source_data_sha256": capture.source_data_sha256,
        "input_profile_id": capture.input_profile_id,
        "selected_input_sha256": capture.selected_input_sha256,
        "selected_rows_sha256": capture.selected_rows_sha256,
        "selected_x_sha256": capture.selected_x_sha256,
        "selected_row_order_sha256": capture.selected_row_order_sha256,
        "fit_rows_sha256": capture.fit_rows_sha256,
        "eval_rows_sha256": capture.eval_rows_sha256,
        "fit_eval_relation": capture.fit_eval_relation,
        "n_selected_rows": capture.n_selected_rows,
        "n_treated": capture.n_treated,
        "n_control": capture.n_control,
        "n_features": capture.n_features,
        "source_feature_names": (
            None if capture.source_feature_names is None else list(capture.source_feature_names)
        ),
        "n_confounders": capture.n_confounders,
        "sample_ids_status": capture.sample_ids_status,
        "sample_ids_sha256": capture.sample_ids_sha256,
        "method_fqn": capture.method_fqn,
        "method_abi": capture.method_abi,
        "method_abi_digest": capture.method_abi_digest,
        "method_profile_id": capture.method_profile_id,
        "owned_attempt_anchor_ref": anchor_ref.model_dump(mode="json"),
        "resolved_params_sha256": capture.resolved_params_sha256,
        "resolved_params": capture.resolved_params,
        **request_values,
    }
    actual = writer_capture.model_dump(mode="json")
    return all(
        _same_ref(actual.get(name), expected_value)
        if name in {"source_data_ref", "owned_attempt_anchor_ref"}
        else _json_values_equal(actual.get(name), expected_value)
        for name, expected_value in expected.items()
    )


def _writer_ready_matches_outcome(writer_ready: HTEWriterReadyV1, outcome: HTEOutcome) -> bool:
    """Reconcile the method-result candidate with the selected persisted outcome."""
    if getattr(writer_ready, "kind", None) != getattr(outcome, "kind", None):
        return False
    kind = getattr(outcome, "kind", None)
    if kind == "refusal":
        return all(
            getattr(writer_ready, field_name, None) == getattr(outcome, field_name, None)
            for field_name in ("refusal_stage", "refusal_reason", "diagnostic_code")
        )
    point = getattr(outcome, "point_estimate", None)
    if point is None or not _numeric_values_match(
        getattr(writer_ready, "point_estimate", None), getattr(point, "value", None)
    ):
        return False
    if kind == "point_estimate":
        return getattr(writer_ready, "inference_status", None) == getattr(
            outcome, "inference_status", None
        ) and getattr(writer_ready, "inference_reason", None) == getattr(
            outcome, "inference_reason", None
        )
    if kind == "interval_estimate":
        return all(
            _numeric_values_match(getattr(writer_ready, left, None), getattr(outcome, right, None))
            for left, right in (
                ("lower_bound", "lower_bound"),
                ("upper_bound", "upper_bound"),
                ("confidence_level", "confidence_level"),
            )
        ) and getattr(writer_ready, "interval_semantics", None) == getattr(
            outcome, "interval_semantics", None
        )
    return False


def _resource_evidence_payload(
    *,
    anchor: OwnedAttemptAnchor,
    receipt: HTEProducerResourceReceiptV1,
    output_kind: str | None = None,
) -> dict[str, object] | None:
    """Recompute the typed resource evidence from owner policy and worker receipt."""
    if anchor.resource_policy_revision == "r5":
        return _resource_evidence_payload_r5(
            anchor=anchor,
            receipt=receipt,
            allow_estimator_not_established=output_kind == "refusal",
        )
    receipt_payload = receipt.model_dump(mode="json")
    execution_status = receipt_payload.get("execution_status")
    if (
        anchor.resource_policy_revision != "r4"
        or anchor.resource_policy_schema_version
        != "polisyos.runtime.observational_input_resource_policy.v4"
        or receipt_payload.get("scope") != anchor.resource_policy_execution_scope
        or execution_status not in {"not_started", "returned", "raised"}
    ):
        return None
    started = execution_status != "not_started"
    estimator_scope = anchor.resource_policy_execution_scope == "estimator_n_jobs_one"
    estimator_observation_status = (
        "not_established" if not started or execution_status == "raised" else "recomputed"
    )
    joblib_started = receipt_payload.get("joblib_started") is True
    joblib_observation_status = (
        "not_established"
        if not started or (not estimator_scope and not joblib_started)
        else "not_applicable"
        if estimator_scope
        else "recomputed"
    )
    payload: dict[str, object] = {
        "owner_policy_ref": anchor.resource_policy_ref.model_dump(mode="json"),
        "owner_policy_digest": anchor.resource_policy_digest,
        "owner_policy_schema_version": anchor.resource_policy_schema_version,
        "owner_policy_revision": anchor.resource_policy_revision,
        "owner_policy_method_fqn": anchor.resource_policy_method_fqn,
        "owner_policy_method_profile_id": anchor.resource_policy_method_profile_id,
        "owner_policy_execution_scope": anchor.resource_policy_execution_scope,
        "owner_policy_max_jobs": anchor.resource_policy_max_jobs,
        "owner_policy_required_estimator_n_jobs": (
            anchor.resource_policy_required_estimator_n_jobs
        ),
        "owner_policy_manifest_schema_version": "1.0",
        "execution_status": execution_status,
        "estimator_observation_status": estimator_observation_status,
        "estimator_before_class_fqn": receipt_payload.get("estimator_before_class_fqn"),
        "estimator_before_n_jobs": receipt_payload.get("estimator_before_n_jobs"),
        "estimator_before_params_sha256": receipt_payload.get("estimator_before_params_sha256"),
        "estimator_after_class_fqn": receipt_payload.get("estimator_after_class_fqn"),
        "estimator_after_n_jobs": receipt_payload.get("estimator_after_n_jobs"),
        "estimator_after_params_sha256": receipt_payload.get("estimator_after_params_sha256"),
        "joblib_observation_status": joblib_observation_status,
        "joblib_started": receipt_payload.get("joblib_started"),
        "joblib_finished": receipt_payload.get("joblib_finished"),
        "joblib_exit_status": receipt_payload.get("joblib_exit_status"),
        "joblib_profile_id": receipt_payload.get("joblib_profile_id"),
        "joblib_profile_revision": receipt_payload.get("joblib_profile_revision"),
        "joblib_implementation": receipt_payload.get("joblib_implementation"),
        "joblib_implementation_version": receipt_payload.get("joblib_implementation_version"),
        "joblib_scope": receipt_payload.get("joblib_scope"),
        "joblib_max_jobs": receipt_payload.get("joblib_max_jobs"),
        "joblib_entry_effective_jobs": receipt_payload.get("joblib_entry_effective_jobs"),
        "joblib_entry_backend_fqn": receipt_payload.get("joblib_entry_backend_fqn"),
        "joblib_entry_config_sha256": receipt_payload.get("joblib_entry_config_sha256"),
        "joblib_entry_implementation_version": receipt_payload.get(
            "joblib_entry_implementation_version"
        ),
        "joblib_exit_effective_jobs": receipt_payload.get("joblib_exit_effective_jobs"),
        "joblib_exit_backend_fqn": receipt_payload.get("joblib_exit_backend_fqn"),
        "joblib_exit_config_sha256": receipt_payload.get("joblib_exit_config_sha256"),
        "joblib_exit_implementation_version": receipt_payload.get(
            "joblib_exit_implementation_version"
        ),
        "physical_thread_limit_status": "not_established",
        "physical_thread_limit": None,
    }
    return payload


def _resource_evidence_payload_r5(
    *,
    anchor: OwnedAttemptAnchor,
    receipt: HTEProducerResourceReceiptV1,
    allow_estimator_not_established: bool = False,
) -> dict[str, object] | None:
    """Recompute hybrid R5 evidence for the producer-wide joblib profile."""
    for field_name in (
        "estimator_before_n_jobs",
        "estimator_after_n_jobs",
        "joblib_max_jobs",
        "joblib_entry_effective_jobs",
        "joblib_exit_effective_jobs",
    ):
        value = getattr(receipt, field_name, None)
        if value is not None and type(value) is not int:
            return None
    receipt_payload = receipt.model_dump(mode="json")
    execution_status = receipt_payload.get("execution_status")
    if (
        anchor.resource_policy_revision != "r5"
        or anchor.resource_policy_schema_version
        != "polisyos.runtime.observational_input_resource_policy.v5"
        or anchor.resource_policy_execution_scope != "producer_scoped_joblib_parallelism_one"
        or type(anchor.resource_policy_max_jobs) is not int
        or anchor.resource_policy_max_jobs != 1
        or receipt_payload.get("scope") != "producer_scoped_joblib_parallelism_one"
        or execution_status not in {"not_started", "returned", "raised"}
        or (execution_status == "raised" and not allow_estimator_not_established)
    ):
        return None

    estimator_fields = (
        "estimator_before_class_fqn",
        "estimator_before_n_jobs",
        "estimator_before_params_sha256",
        "estimator_after_class_fqn",
        "estimator_after_n_jobs",
        "estimator_after_params_sha256",
    )
    estimator_values = tuple(receipt_payload.get(name) for name in estimator_fields)
    estimator_present = tuple(value is not None for value in estimator_values)
    if (
        anchor.resource_policy_required_estimator_n_jobs is not None
        and type(anchor.resource_policy_required_estimator_n_jobs) is not int
    ):
        return None
    if anchor.resource_policy_required_estimator_n_jobs not in {None, 1}:
        return None
    estimator_required = anchor.resource_policy_required_estimator_n_jobs == 1
    if any(estimator_present) and not all(estimator_present):
        return None
    if all(estimator_present) and any(
        type(receipt_payload.get(name)) is not int
        for name in ("estimator_before_n_jobs", "estimator_after_n_jobs")
    ):
        return None
    if not estimator_required and any(estimator_present):
        return None
    if (
        estimator_required
        and execution_status == "returned"
        and not all(estimator_present)
        and not (allow_estimator_not_established and receipt_payload.get("joblib_started") is True)
    ):
        return None
    if (
        estimator_required
        and all(estimator_present)
        and execution_status == "returned"
        and (
            type(receipt_payload.get("estimator_before_n_jobs")) is not int
            or receipt_payload.get("estimator_before_n_jobs") != 1
            or type(receipt_payload.get("estimator_after_n_jobs")) is not int
            or receipt_payload.get("estimator_after_n_jobs") != 1
            or receipt_payload.get("estimator_before_class_fqn")
            != receipt_payload.get("estimator_after_class_fqn")
            or receipt_payload.get("estimator_before_params_sha256")
            != receipt_payload.get("estimator_after_params_sha256")
        )
    ):
        return None

    joblib_fields = (
        "joblib_profile_id",
        "joblib_profile_revision",
        "joblib_implementation",
        "joblib_implementation_version",
        "joblib_scope",
        "joblib_max_jobs",
        "joblib_entry_effective_jobs",
        "joblib_entry_backend_fqn",
        "joblib_entry_config_sha256",
        "joblib_entry_implementation_version",
        "joblib_exit_effective_jobs",
        "joblib_exit_backend_fqn",
        "joblib_exit_config_sha256",
        "joblib_exit_implementation_version",
    )
    joblib_started = receipt_payload.get("joblib_started")
    joblib_finished = receipt_payload.get("joblib_finished")
    joblib_exit_status = receipt_payload.get("joblib_exit_status")
    if type(joblib_started) is not bool or type(joblib_finished) is not bool:
        return None
    joblib_values = tuple(receipt_payload.get(name) for name in joblib_fields)
    joblib_present = tuple(value is not None for value in joblib_values)
    if execution_status == "not_started":
        if (
            joblib_started
            or joblib_finished
            or joblib_exit_status != "not_started"
            or any(joblib_present)
            or any(estimator_present)
        ):
            return None
    elif not joblib_started:
        if (
            execution_status in {"returned", "raised"}
            or joblib_finished
            or joblib_exit_status != "not_started"
            or any(joblib_present)
        ):
            return None
    else:
        if (
            not joblib_finished
            or joblib_exit_status != execution_status
            or not all(joblib_present)
            or receipt_payload.get("joblib_profile_id")
            != "joblib.parallel_config.current_thread@1.0"
            or receipt_payload.get("joblib_profile_revision") != "1.0"
            or receipt_payload.get("joblib_implementation") != "joblib.parallel_config"
            or receipt_payload.get("joblib_scope") != "current_thread_joblib"
            or type(receipt_payload.get("joblib_max_jobs")) is not int
            or receipt_payload.get("joblib_max_jobs") != 1
            or receipt_payload.get("joblib_entry_implementation_version")
            != receipt_payload.get("joblib_implementation_version")
        ):
            return None
        if any(
            type(receipt_payload.get(name)) is not int or receipt_payload.get(name) != 1
            for name in (
                "joblib_max_jobs",
                "joblib_entry_effective_jobs",
                "joblib_exit_effective_jobs",
            )
        ):
            return None
        if execution_status == "returned" and (
            receipt_payload.get("joblib_entry_effective_jobs") != 1
            or receipt_payload.get("joblib_exit_effective_jobs") != 1
            or receipt_payload.get("joblib_entry_backend_fqn")
            != receipt_payload.get("joblib_exit_backend_fqn")
            or receipt_payload.get("joblib_entry_config_sha256")
            != receipt_payload.get("joblib_exit_config_sha256")
            or receipt_payload.get("joblib_entry_implementation_version")
            != receipt_payload.get("joblib_exit_implementation_version")
        ):
            return None

    if not estimator_required:
        estimator_observation_status = "not_applicable"
    elif all(estimator_present):
        estimator_observation_status = "recomputed"
    else:
        estimator_observation_status = "not_established"
    joblib_observation_status = "recomputed" if joblib_started else "not_established"
    payload: dict[str, object] = {
        "owner_policy_ref": anchor.resource_policy_ref.model_dump(mode="json"),
        "owner_policy_digest": anchor.resource_policy_digest,
        "owner_policy_schema_version": anchor.resource_policy_schema_version,
        "owner_policy_revision": anchor.resource_policy_revision,
        "owner_policy_method_fqn": anchor.resource_policy_method_fqn,
        "owner_policy_method_profile_id": anchor.resource_policy_method_profile_id,
        "owner_policy_execution_scope": anchor.resource_policy_execution_scope,
        "owner_policy_max_jobs": anchor.resource_policy_max_jobs,
        "owner_policy_required_estimator_n_jobs": (
            anchor.resource_policy_required_estimator_n_jobs
        ),
        "owner_policy_manifest_schema_version": "1.0",
        "execution_status": execution_status,
        "estimator_observation_status": estimator_observation_status,
        "estimator_before_class_fqn": receipt_payload.get("estimator_before_class_fqn"),
        "estimator_before_n_jobs": receipt_payload.get("estimator_before_n_jobs"),
        "estimator_before_params_sha256": receipt_payload.get("estimator_before_params_sha256"),
        "estimator_after_class_fqn": receipt_payload.get("estimator_after_class_fqn"),
        "estimator_after_n_jobs": receipt_payload.get("estimator_after_n_jobs"),
        "estimator_after_params_sha256": receipt_payload.get("estimator_after_params_sha256"),
        "joblib_observation_status": joblib_observation_status,
        "joblib_started": joblib_started,
        "joblib_finished": joblib_finished,
        "joblib_exit_status": joblib_exit_status,
        "joblib_profile_id": receipt_payload.get("joblib_profile_id"),
        "joblib_profile_revision": receipt_payload.get("joblib_profile_revision"),
        "joblib_implementation": receipt_payload.get("joblib_implementation"),
        "joblib_implementation_version": receipt_payload.get("joblib_implementation_version"),
        "joblib_scope": receipt_payload.get("joblib_scope"),
        "joblib_max_jobs": receipt_payload.get("joblib_max_jobs"),
        "joblib_entry_effective_jobs": receipt_payload.get("joblib_entry_effective_jobs"),
        "joblib_entry_backend_fqn": receipt_payload.get("joblib_entry_backend_fqn"),
        "joblib_entry_config_sha256": receipt_payload.get("joblib_entry_config_sha256"),
        "joblib_entry_implementation_version": receipt_payload.get(
            "joblib_entry_implementation_version"
        ),
        "joblib_exit_effective_jobs": receipt_payload.get("joblib_exit_effective_jobs"),
        "joblib_exit_backend_fqn": receipt_payload.get("joblib_exit_backend_fqn"),
        "joblib_exit_config_sha256": receipt_payload.get("joblib_exit_config_sha256"),
        "joblib_exit_implementation_version": receipt_payload.get(
            "joblib_exit_implementation_version"
        ),
        "physical_thread_limit_status": "not_established",
        "physical_thread_limit": None,
    }
    return payload


def _resource_evidence_payload_for_consumer(
    *,
    payload: dict[str, object] | None,
    consumer: HTEResourceExecutionEvidenceV1 | DirectMethodExecutionHTEResourceEvidence,
) -> dict[str, object] | None:
    """Normalize owner-derived evidence under the exact selected consumer DTO."""
    if payload is None:
        return None

    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionHTEResourceEvidence,
        _validate_strict_json_wire_payload,
    )
    from polisyos.ir.analytics import HTEResourceExecutionEvidenceV1

    try:
        if type(consumer) is HTEResourceExecutionEvidenceV1:
            normalized = _validate_strict_json_wire_payload(
                payload,
                TypeAdapter(HTEResourceExecutionEvidenceV1),
                invalid_code="owned_attempt_resource_evidence_invalid",
            )
        elif type(consumer) is DirectMethodExecutionHTEResourceEvidence:
            normalized = _validate_strict_json_wire_payload(
                payload,
                TypeAdapter(DirectMethodExecutionHTEResourceEvidence),
                invalid_code="owned_attempt_resource_evidence_invalid",
            )
        else:
            return None
    except (TypeError, ValueError):
        return None
    return normalized.model_dump(mode="json")


def _resource_evidence_matches_receipt(
    *,
    evidence: HTEResourceExecutionEvidenceV1 | DirectMethodExecutionHTEResourceEvidence,
    anchor: OwnedAttemptAnchor,
    receipt: HTEProducerResourceReceiptV1,
) -> bool:
    """Require every HTE resource claim to match both owner policy and real receipt."""
    expected = _resource_evidence_payload_for_consumer(
        payload=_resource_evidence_payload(anchor=anchor, receipt=receipt),
        consumer=evidence,
    )
    return expected is not None and _json_values_equal(evidence.model_dump(mode="json"), expected)


def _refusal_diagnostic_matches_writer_ready(
    *,
    diagnostic: HTERefusalDiagnostic,
    writer_ready: HTEWriterReadyV1,
    anchor: OwnedAttemptAnchor,
    anchor_ref: OwnedAttemptAnchorRef,
    method_result_ref: ArtifactRef,
    method_evidence_ref: ArtifactRef,
    materialization_binding_ref: ArtifactRef,
    expected_limitations: tuple[str, ...] | None,
) -> bool:
    """Bind a method refusal diagnostic to the captured input and real execution."""
    capture = anchor.input_capture
    if (
        getattr(diagnostic, "diagnostic_origin", None) != "method_execution"
        or getattr(diagnostic, "method_fqn", None) != capture.method_fqn
        or getattr(diagnostic, "method_abi", None) != capture.method_abi
        or getattr(diagnostic, "method_abi_digest", None) != capture.method_abi_digest
        or getattr(diagnostic, "method_profile_id", None) != capture.method_profile_id
        or getattr(diagnostic, "refusal_stage", None)
        != getattr(writer_ready, "refusal_stage", None)
        or getattr(diagnostic, "refusal_reason", None)
        != getattr(writer_ready, "refusal_reason", None)
        or getattr(diagnostic, "diagnostic_code", None)
        != getattr(writer_ready, "diagnostic_code", None)
        or not _same_ref(getattr(diagnostic, "owned_attempt_anchor_ref", None), anchor_ref)
        or not _same_ref(getattr(diagnostic, "method_result_ref", None), method_result_ref)
        or not _same_ref(getattr(diagnostic, "method_evidence_ref", None), method_evidence_ref)
        or not _same_ref(
            getattr(diagnostic, "materialization_binding_ref", None),
            materialization_binding_ref,
        )
        or expected_limitations is None
        or tuple(getattr(diagnostic, "limitations", ())) != expected_limitations
    ):
        return False

    row_fields = {
        "n_selected_rows": capture.n_selected_rows,
        "selected_input_sha256": capture.selected_input_sha256,
        "selected_rows_sha256": capture.selected_rows_sha256,
        "selected_x_sha256": capture.selected_x_sha256,
        "selected_row_order_sha256": capture.selected_row_order_sha256,
    }
    if getattr(diagnostic, "selected_rows_status", None) == "recomputed":
        if any(
            getattr(diagnostic, name, None) != expected for name, expected in row_fields.items()
        ):
            return False
    elif getattr(diagnostic, "selected_rows_status", None) != "not_established" or any(
        getattr(diagnostic, name, None) is not None for name in row_fields
    ):
        return False

    from polisyos.foundry.methods.catalog.causal.hte_v2 import HTEProducerResourceReceiptV1

    receipt = getattr(writer_ready, "resource_receipt", None)
    if not isinstance(receipt, HTEProducerResourceReceiptV1):
        return False
    expected_resource_evidence = _resource_evidence_payload(
        anchor=anchor,
        receipt=receipt,
        output_kind=writer_ready.kind,
    )
    actual_resource_evidence = getattr(diagnostic, "resource_evidence", None)
    if actual_resource_evidence is None:
        return receipt.execution_status == "not_started"
    expected_resource_evidence = _resource_evidence_payload_for_consumer(
        payload=expected_resource_evidence,
        consumer=actual_resource_evidence,
    )
    return expected_resource_evidence is not None and _json_values_equal(
        actual_resource_evidence.model_dump(mode="json"), expected_resource_evidence
    )


def _point_result_matches_writer_ready(
    *,
    point_result: HTEPointResult,
    writer_ready: HTEWriterReadyPointV1,
    resource_evidence: dict[str, object],
    anchor_ref: OwnedAttemptAnchorRef,
    method_result_ref: ArtifactRef,
    method_evidence_ref: ArtifactRef,
) -> bool:
    """Bind the persisted CATE vector to the complete private writer candidate."""
    capture = getattr(writer_ready, "capture", None)
    if capture is None:
        return False
    capture_payload = capture.model_dump(mode="json")
    expected = {
        name: capture_payload[name]
        for name in type(point_result).model_fields
        if name in capture_payload
    }
    expected.update(
        {
            "schema_version": "1.0",
            "point_estimate": writer_ready.point_estimate,
            "cate_values": writer_ready.cate_values,
            "owned_attempt_anchor_ref": anchor_ref.model_dump(mode="json"),
            "method_result_ref": method_result_ref.model_dump(mode="json"),
            "method_evidence_ref": method_evidence_ref.model_dump(mode="json"),
            "resource_evidence": resource_evidence,
        }
    )
    payload = point_result.model_dump(mode="json")
    return set(payload) == set(expected) and all(
        _json_values_equal(payload[name], value) for name, value in expected.items()
    )


def _basis_matches_writer_ready(
    *,
    basis: ATEInferenceBasis,
    writer_ready: HTEWriterReadyV1,
    outcome: HTEOutcome,
    anchor: OwnedAttemptAnchor,
    anchor_ref: OwnedAttemptAnchorRef,
    point_result_ref: ArtifactRef | None,
    hte_result_ref: ArtifactRef | None,
    method_result_ref: ArtifactRef,
    method_evidence_ref: ArtifactRef,
    invocation_basis_ref: ArtifactRef | None,
    resource_evidence: dict[str, object],
) -> bool:
    """Reconcile every native basis value with the producer capture and owner."""
    capture = anchor.input_capture
    request = capture.request_context
    if outcome.kind == "interval_estimate":
        native = getattr(writer_ready, "native_capture", None)
    elif outcome.kind == "point_estimate":
        native = getattr(writer_ready, "native_diagnostic", None)
    else:
        return False
    if native is None:
        return False
    expected: dict[str, object] = native.model_dump(mode="json")
    legacy_interval_admitted = outcome.kind == "interval_estimate"
    native_result_disposition = (
        "legacy_hte_result_admitted"
        if legacy_interval_admitted
        else "legacy_hte_result_unrepresentable"
    )
    native_result_disposition_reason = None
    if not legacy_interval_admitted:
        native_result_disposition_reason = (
            "native_bounds_unordered"
            if native.native_lower_bound > native.native_upper_bound
            else "point_not_contained_in_legacy_interval"
        )
    expected.update(
        {
            "schema_version": "1.0",
            "method_profile_id": capture.method_profile_id,
            "selected_x_sha256": capture.selected_x_sha256,
            "contrast_status": (
                "established" if request.contrast_status == "declared" else "not_established"
            ),
            "control_value": request.control_value,
            "treated_value": request.treated_value,
            "request_estimand_status": request.request_estimand_status,
            "request_estimand": request.request_estimand,
            "request_target_scope_status": request.request_target_scope_status,
            "request_target_scope": request.request_target_scope,
            "outcome_variable_status": request.outcome_variable_status,
            "outcome_variable_id": request.outcome_variable_id,
            "treatment_variable_status": request.treatment_variable_status,
            "treatment_variable_id": request.treatment_variable_id,
            "request_alpha_status": request.request_alpha_status,
            "requested_alpha": request.requested_alpha,
            "requested_guarantee_status": request.requested_guarantee_status,
            "requested_guarantee": request.requested_guarantee,
            "computed_target_scope_status": "recomputed",
            "computed_target_scope": "selected_evaluation_rows",
            "target_relation": outcome.target_relation.model_dump(mode="json"),
            "source_data_ref": capture.source_data_ref.model_dump(mode="json"),
            "materialization_binding_ref": (
                capture.materialization_binding_ref.model_dump(mode="json")
                if capture.materialization_binding_ref is not None
                else None
            ),
            "invocation_basis_ref": (
                invocation_basis_ref.model_dump(mode="json")
                if invocation_basis_ref is not None
                else None
            ),
            "invocation_basis_status": (
                "established" if invocation_basis_ref is not None else "not_established"
            ),
            "invocation_basis_reason": (
                None
                if invocation_basis_ref is not None
                else "no_invocation_basis_artifact_contract"
            ),
            "owned_attempt_anchor_ref": anchor_ref.model_dump(mode="json"),
            "native_result_disposition": native_result_disposition,
            "native_result_disposition_reason": native_result_disposition_reason,
            "resource_evidence": resource_evidence,
            "hte_result_ref": (
                hte_result_ref.model_dump(mode="json") if hte_result_ref is not None else None
            ),
            "point_result_ref": (
                point_result_ref.model_dump(mode="json") if point_result_ref is not None else None
            ),
            "method_result_ref": method_result_ref.model_dump(mode="json"),
            "method_evidence_ref": method_evidence_ref.model_dump(mode="json"),
        }
    )
    actual = basis.model_dump(mode="json")
    return set(actual) == set(expected) and all(
        _json_values_equal(actual[name], value) for name, value in expected.items()
    )


def _hte_result_matches_writer_ready(
    *,
    hte_result: HTEResult,
    writer_ready: HTEWriterReadyIntervalV1,
) -> bool:
    """Bind the legacy HTEResult v1 carrier to the completed producer output."""
    native = getattr(writer_ready, "native_capture", None)
    capture = getattr(writer_ready, "capture", None)
    if native is None or capture is None:
        return False
    method_name = capture.method_fqn.split("@", maxsplit=1)[0].rsplit(".", maxsplit=1)[-1]
    expected_method = {
        "causal_forest": "causal_forest",
        "forest_dr": "forest_dr",
    }.get(method_name)
    actual_method = getattr(hte_result, "method", None)
    actual_method = getattr(actual_method, "value", actual_method)
    try:
        result_cate_values = tuple(hte_result.cate_values)
    except (AttributeError, TypeError):
        return False
    return (
        expected_method is not None
        and actual_method == expected_method
        and hte_result.schema_version == "1.0"
        and hte_result.ate == writer_ready.point_estimate
        and hte_result.ate_ci_lower == native.native_lower_bound
        and hte_result.ate_ci_upper == native.native_upper_bound
        and hte_result.confidence_level == native.confidence_level
        and result_cate_values == tuple(writer_ready.cate_values)
        and hte_result.n_samples == capture.n_selected_rows
        and hte_result.econml_estimator_class == native.estimator_class
    )


def _expected_method_result_inputs(
    anchor: OwnedAttemptAnchor,
    anchor_ref: OwnedAttemptAnchorRef,
) -> tuple[InputRef, ...]:
    """Return the exact R12 method-result lineage rows for this selected input."""
    return (
        input_ref_from_artifact_ref(anchor.requested_source_ref, role="requested_source"),
        input_ref_from_artifact_ref(
            anchor.observational_run_intent_ref,
            role="observational_run_intent",
        ),
        input_ref_from_artifact_ref(
            anchor.content_admitted_intent_ref,
            role="content_admitted_intent",
        ),
        input_ref_from_artifact_ref(anchor.submitted_input_ref, role="submitted_method_input"),
        input_ref_from_artifact_ref(anchor.effective_input_ref, role="effective_method_input"),
        input_ref_from_artifact_ref(anchor.resource_policy_ref, role="method_resource_policy"),
        *(
            input_ref_from_artifact_ref(ref, role=role)
            for ref, role in _physical_binding_input(anchor)
        ),
        input_ref_from_artifact_ref(anchor_ref, role="owned_attempt_anchor"),
    )


def _require_manifest_input_roles(
    *, bounded: CoreJsonArtifactBoundedRead, inputs: tuple[tuple[ArtifactRef, str], ...], code: str
) -> None:
    """Require exact ordered selected-profile lineage for one HTE artifact."""
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref

    expected = tuple(input_ref_from_artifact_ref(ref, role=role) for ref, role in inputs)
    manifest = getattr(bounded, "manifest", None)
    if manifest is None or tuple(getattr(manifest, "inputs", ())) != expected:
        raise ValueError(code)


def _owner_binding_inputs(
    *,
    physical_binding_ref: ArtifactRef | None,
    search_binding_ref: ArtifactRef | None,
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Return physical and Search owner edges in their canonical order."""
    physical_inputs = (
        ()
        if physical_binding_ref is None
        else ((physical_binding_ref, "physical_source_materialization_binding"),)
    )
    search_inputs = (
        ()
        if search_binding_ref is None
        else ((search_binding_ref, "search_uncertainty_task_binding"),)
    )
    return (*physical_inputs, *search_inputs)


def _numeric_hte_manifest_input_roles(
    *,
    prefix: tuple[tuple[ArtifactRef, str], ...],
    anchor_ref: ArtifactRef,
    source_data_ref: ArtifactRef,
    method_result_ref: ArtifactRef,
    method_evidence_ref: ArtifactRef,
    resource_policy_ref: ArtifactRef,
    owner_binding_inputs: tuple[tuple[ArtifactRef, str], ...],
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Build the ordered lineage shared by numeric HTE outputs and readers."""
    return (
        *prefix,
        (anchor_ref, "owned_attempt_anchor"),
        (source_data_ref, "source_data"),
        (method_result_ref, "method_result"),
        (method_evidence_ref, "method_evidence"),
        (resource_policy_ref, "resource_policy"),
        *owner_binding_inputs,
    )


def _numeric_hte_outcome_input_roles(
    *,
    result_ref: ArtifactRef,
    result_role: Literal["point_result", "hte_result"],
    inference_basis_ref: ArtifactRef | None,
    anchor_ref: ArtifactRef,
    source_data_ref: ArtifactRef,
    method_result_ref: ArtifactRef,
    method_evidence_ref: ArtifactRef,
    resource_policy_ref: ArtifactRef,
    owner_binding_inputs: tuple[tuple[ArtifactRef, str], ...],
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Build outcome lineage, retaining a selected optional basis edge."""
    prefix = ((result_ref, result_role),)
    if inference_basis_ref is not None:
        prefix = (*prefix, (inference_basis_ref, "inference_basis"))
    return _numeric_hte_manifest_input_roles(
        prefix=prefix,
        anchor_ref=anchor_ref,
        source_data_ref=source_data_ref,
        method_result_ref=method_result_ref,
        method_evidence_ref=method_evidence_ref,
        resource_policy_ref=resource_policy_ref,
        owner_binding_inputs=owner_binding_inputs,
    )


def _read_owner_selected_method_outputs(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    anchor: OwnedAttemptAnchor,
    anchor_ref: OwnedAttemptAnchorRef,
    method_result_ref: ArtifactRef,
    method_evidence_ref: ArtifactRef,
) -> tuple[HTEWriterReadyV1, ArtifactManifest]:
    """Resolve method output/evidence and bind their CAS lineage to this anchor."""
    from polisyos.foundry.methods.catalog.causal.hte_v2 import validate_hte_writer_ready_json

    limits = service._observational_read_limits()
    result_bounded, result_payload = _read_profiled_value(
        service=service,
        selected_ref=method_result_ref,
        limits=limits,
        expected_kind="scientist.method_result.causal.hte",
        expected_schema_name="polisyos.scientist.MethodResult",
        expected_schema_version="0.1.0",
    )
    if tuple(result_bounded.manifest.inputs) != _expected_method_result_inputs(anchor, anchor_ref):
        raise ValueError("owned_attempt_method_result_manifest_lineage_mismatch")
    if not isinstance(result_payload, Mapping):
        raise ValueError("owned_attempt_method_result_payload_invalid")
    writer_ready_raw = result_payload.get("hte_outcome_write_ready")
    if not isinstance(writer_ready_raw, Mapping):
        raise ValueError("owned_attempt_hte_writer_ready_payload_missing")
    try:
        writer_ready = validate_hte_writer_ready_json(writer_ready_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_hte_writer_ready_payload_invalid") from exc
    if (
        getattr(writer_ready, "method_fqn", None) != anchor.input_capture.method_fqn
        or getattr(writer_ready, "method_abi", None) != anchor.input_capture.method_abi
        or getattr(writer_ready, "method_profile_id", None)
        != anchor.input_capture.method_profile_id
    ):
        raise ValueError("owned_attempt_hte_writer_ready_method_binding_mismatch")
    if writer_ready.kind in {"point_estimate", "interval_estimate"}:
        if not _capture_matches_writer_ready(
            writer_capture=writer_ready.capture,
            anchor=anchor,
            anchor_ref=anchor_ref,
        ):
            raise ValueError("owned_attempt_hte_writer_ready_capture_mismatch")
    elif writer_ready.kind == "refusal":
        if (
            _resource_evidence_payload(
                anchor=anchor,
                receipt=writer_ready.resource_receipt,
                output_kind=writer_ready.kind,
            )
            is None
        ):
            raise ValueError("owned_attempt_hte_writer_ready_refusal_resource_mismatch")
    else:
        raise ValueError("owned_attempt_hte_writer_ready_kind_not_supported")

    evidence_bounded, evidence_payload = _read_profiled_value(
        service=service,
        selected_ref=method_evidence_ref,
        limits=limits,
        expected_kind="scientist.method_evidence",
        expected_schema_name="polisyos.scientist.MethodExecutionEvidence",
        expected_schema_version="0.1.0",
    )
    expected_evidence_inputs = (
        input_ref_from_artifact_ref(method_result_ref, role="method_result"),
        *_expected_method_result_inputs(anchor, anchor_ref),
    )
    if tuple(evidence_bounded.manifest.inputs) != expected_evidence_inputs:
        raise ValueError("owned_attempt_method_evidence_manifest_lineage_mismatch")
    if not isinstance(evidence_payload, Mapping):
        raise ValueError("owned_attempt_method_evidence_payload_invalid")
    evidence_bindings = {
        "authority_purpose": "method_execution",
        "method_fqn": anchor.method_fqn,
        "method_version": anchor.method_version,
        "method_abi_digest": anchor.method_abi_digest,
        "method_build_digest": anchor.method_build_digest,
        "resource_policy_digest": anchor.resource_policy_digest,
        "source_protocol": anchor.source_protocol,
        "normalization": anchor.normalization,
        "method_result_ref": method_result_ref.model_dump(mode="json"),
        "requested_source_ref": anchor.requested_source_ref.model_dump(mode="json"),
        "observational_run_intent_ref": anchor.observational_run_intent_ref.model_dump(mode="json"),
        "content_admitted_intent_ref": anchor.content_admitted_intent_ref.model_dump(mode="json"),
        "submitted_input_ref": anchor.submitted_input_ref.model_dump(mode="json"),
        "effective_input_ref": anchor.effective_input_ref.model_dump(mode="json"),
        "resource_policy_ref": anchor.resource_policy_ref.model_dump(mode="json"),
        "owned_attempt_anchor_ref": anchor_ref.model_dump(mode="json"),
    }
    materialization_binding_ref = anchor.input_capture.materialization_binding_ref
    if materialization_binding_ref is not None:
        evidence_bindings["materialization_binding_ref"] = materialization_binding_ref.model_dump(
            mode="json"
        )
    elif "materialization_binding_ref" in evidence_payload:
        raise ValueError("owned_attempt_method_evidence_unselected_materialization_binding")
    if not all(
        _json_values_equal(evidence_payload.get(name), expected)
        for name, expected in evidence_bindings.items()
    ):
        raise ValueError("owned_attempt_method_evidence_content_mismatch")
    _require_method_evidence_materialization_binding(
        anchor=anchor,
        evidence_payload=evidence_payload,
    )
    return writer_ready, evidence_bounded.manifest


def _require_method_evidence_materialization_binding(
    *,
    anchor: OwnedAttemptAnchor,
    evidence_payload: Mapping[str, object],
) -> None:
    """Bind the worker evidence payload to the source materialization selected by Runtime."""
    selected_ref = anchor.input_capture.materialization_binding_ref
    if selected_ref is None:
        if "materialization_binding_ref" in evidence_payload:
            raise ValueError("owned_attempt_method_evidence_unselected_materialization_binding")
        return
    if not _json_values_equal(
        evidence_payload.get("materialization_binding_ref"),
        selected_ref.model_dump(mode="json"),
    ):
        raise ValueError("owned_attempt_method_evidence_materialization_binding_mismatch")


@dataclass(frozen=True)
class _CompletedOwnedAttemptFrame:
    """One completed owner frame shared by content and bounded projection readers."""

    anchor_ref: OwnedAttemptAnchorRef
    anchor: OwnedAttemptAnchor
    record: ControlJobRecord
    completed_event: _ControlJobLifecycleSourceEventRecord
    selection: DirectMethodExecutionSelection
    historical_completed_event_id: int | None = None


def _assert_completed_owner_frame_current(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    owner_frame: _CompletedOwnedAttemptFrame,
) -> None:
    """Reject owner or source-event replacement during artifact reconciliation."""
    control_store = service._control_store
    if owner_frame.historical_completed_event_id is not None:
        try:
            latest = control_store.get_job(owner_frame.anchor.job_id)
            terminal = control_store.get_job_lifecycle_event_record(
                job_id=owner_frame.anchor.job_id,
                event_id=owner_frame.historical_completed_event_id,
                expected_event_type="job_completed",
            )
            delivery = control_store.get_search_hte_completion_outbox_event(
                job_id=owner_frame.anchor.job_id,
                completed_event_id=owner_frame.historical_completed_event_id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("owned_attempt_historical_completed_owner_readback_failed") from exc
        if (
            latest is None
            or latest.job_id != owner_frame.record.job_id
            or latest.run_id != owner_frame.anchor.run_id
            or latest.kind != "workflow_run"
            or latest.attempt < owner_frame.anchor.attempt
            or not _json_values_equal(
                latest.method_execution_selection,
                owner_frame.record.method_execution_selection,
            )
            or terminal.event_id != owner_frame.completed_event.event_id
            or terminal.payload_sha256 != owner_frame.completed_event.payload_sha256
            or terminal.event_type != "job_completed"
            or terminal.job_id != owner_frame.record.job_id
            or delivery is None
            or delivery.topic != "control.search.hte_completed"
            or delivery.job_id != owner_frame.record.job_id
            or delivery.payload.get("completed_event_id")
            != owner_frame.historical_completed_event_id
            or delivery.payload.get("completed_event_payload_sha256")
            != owner_frame.completed_event.payload_sha256
        ):
            raise ValueError("owned_attempt_historical_completed_owner_changed_during_resolution")
        return
    try:
        latest = control_store.get_latest_job_by_run(owner_frame.anchor.run_id)
        unique_completed = control_store.get_unique_completed_job_by_run_and_kind(
            run_id=owner_frame.anchor.run_id,
            kind="workflow_run",
        )
        terminal = control_store.get_job_terminal_source_event_record(owner_frame.record.job_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_completed_owner_readback_failed") from exc
    if (
        latest is None
        or latest.job_id != owner_frame.record.job_id
        or latest.run_id != owner_frame.anchor.run_id
        or latest.kind != "workflow_run"
        or latest.state != "completed"
        or latest.attempt != owner_frame.record.attempt
        or latest.lease_owner is not None
        or latest.lease_expires_at is not None
        or not _json_values_equal(
            latest.method_execution_selection,
            owner_frame.record.method_execution_selection,
        )
        or unique_completed is None
        or unique_completed.job_id != owner_frame.record.job_id
        or unique_completed.run_id != owner_frame.anchor.run_id
        or unique_completed.attempt != owner_frame.record.attempt
        or terminal.event_id != owner_frame.completed_event.event_id
        or terminal.payload_sha256 != owner_frame.completed_event.payload_sha256
        or terminal.event_type != "job_completed"
        or terminal.job_id != owner_frame.record.job_id
    ):
        raise ValueError("owned_attempt_completed_owner_changed_during_resolution")


def _resolve_completed_owned_attempt_frame(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    anchor_ref: OwnedAttemptAnchorRef,
    expected_run_id: str | None = None,
    expected_job_id: str | None = None,
    expected_tenant_id: str | None = None,
    expected_cell_id: str | None | object = _OWNER_SCOPE_UNSET,
    expected_completed_event_id: int | None = None,
) -> _CompletedOwnedAttemptFrame:
    """Reconcile one current or exact historical owner row and completion event."""
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        _validate_method_execution_selection_wire_payload,
    )

    typed_anchor_ref = _owned_attempt_anchor_ref(
        anchor_ref,
        code="owned_attempt_anchor_ref_invalid",
    )
    anchor = _read_owned_attempt_anchor(service=service, anchor_ref=typed_anchor_ref)
    if expected_job_id is not None and anchor.job_id != expected_job_id:
        raise ValueError("owned_attempt_projection_job_key_mismatch")
    if expected_tenant_id is not None and anchor.tenant_id != expected_tenant_id:
        raise ValueError("owned_attempt_projection_tenant_key_mismatch")
    if expected_cell_id is not _OWNER_SCOPE_UNSET and anchor.cell_id != expected_cell_id:
        raise ValueError("owned_attempt_projection_cell_key_mismatch")
    if expected_run_id is not None and anchor.run_id != expected_run_id:
        raise ValueError("owned_attempt_projection_run_key_mismatch")
    if isinstance(anchor.input_admission, OwnedAttemptHTEInputRefused):
        raise ValueError("owned_attempt_refused_input_has_no_method_output_association")
    control_store = service._control_store
    try:
        if expected_completed_event_id is None:
            latest_record = control_store.get_latest_job_by_run(anchor.run_id)
            record = control_store.get_unique_completed_job_by_run_and_kind(
                run_id=anchor.run_id,
                kind="workflow_run",
            )
            if (
                latest_record is None
                or latest_record.job_id != anchor.job_id
                or latest_record.run_id != anchor.run_id
                or latest_record.kind != "workflow_run"
                or latest_record.state != "completed"
                or latest_record.attempt != anchor.attempt
                or record is None
                or record.state != "completed"
                or record.job_id != anchor.job_id
                or record.run_id != anchor.run_id
                or record.attempt != anchor.attempt
                or record.lease_owner is not None
                or record.lease_expires_at is not None
                or not isinstance(record.method_execution_selection, Mapping)
            ):
                raise ValueError("owned_attempt_anchor_not_current_completed_winner")
            running_event = control_store._latest_control_job_lifecycle_event_record(
                job_id=record.job_id,
                event_type="job_running",
            )
            completed_event = control_store.get_job_terminal_source_event_record(record.job_id)
        else:
            if type(expected_completed_event_id) is not int or expected_completed_event_id < 1:
                raise ValueError("owned_attempt_historical_completed_event_id_invalid")
            record = control_store.get_job(anchor.job_id)
            if (
                record is None
                or record.job_id != anchor.job_id
                or record.run_id != anchor.run_id
                or record.kind != "workflow_run"
                or record.attempt < anchor.attempt
            ):
                raise ValueError("owned_attempt_historical_completed_job_unavailable")
            running_event = control_store.get_job_lifecycle_event_record(
                job_id=record.job_id,
                event_id=anchor.job_running_event.event_id,
                expected_event_type="job_running",
            )
            completed_event = control_store.get_job_lifecycle_event_record(
                job_id=record.job_id,
                event_id=expected_completed_event_id,
                expected_event_type="job_completed",
            )
            if (
                completed_event.payload.get("state") != "completed"
                or completed_event.payload.get("lease_owner") != anchor.worker_id
                or type(completed_event.payload.get("attempt")) is not int
                or completed_event.payload.get("attempt") != anchor.attempt
                or completed_event.created_at < anchor.captured_at
                or not isinstance(
                    completed_event.payload.get("method_execution_selection"), Mapping
                )
            ):
                raise ValueError("owned_attempt_historical_completed_event_fence_mismatch")
    except (RuntimeError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("owned_attempt_"):
            raise
        raise ValueError("owned_attempt_completed_owner_not_unique") from exc
    created_event = control_store._get_job_created_source_event_record(record.job_id)
    if (
        completed_event.event_type != "job_completed"
        or completed_event.job_id != record.job_id
        or completed_event.payload.get("state") != "completed"
        or completed_event.payload.get("lease_owner") != anchor.worker_id
        or type(completed_event.payload.get("attempt")) is not int
        or completed_event.payload.get("attempt") != anchor.attempt
        or created_event.job_id != anchor.job_id
        or created_event.event_type != "job_created"
        or _lifecycle_event(running_event) != anchor.job_running_event
        or running_event.created_at > completed_event.created_at
        or anchor.captured_at > completed_event.created_at
    ):
        raise ValueError("owned_attempt_completed_event_fence_mismatch")
    from polisyos.runtime.http.services.control_plane_store import (
        _control_job_execution_scope_from_event,
    )

    scope = _control_job_execution_scope_from_event(created_event.payload)
    if (
        scope.status != "established"
        or scope.tenant_id != anchor.tenant_id
        or scope.cell_id != anchor.cell_id
        or (expected_tenant_id is not None and scope.tenant_id != expected_tenant_id)
        or (expected_cell_id is not _OWNER_SCOPE_UNSET and scope.cell_id != expected_cell_id)
        or created_event.event_id != anchor.job_created_event.event_id
        or created_event.payload_sha256 != anchor.job_created_event.payload_sha256
    ):
        raise ValueError("owned_attempt_creation_scope_or_event_mismatch")
    creation_marker = created_event.payload.get("observational_method_execution")
    if not isinstance(creation_marker, Mapping):
        raise ValueError("owned_attempt_creation_marker_not_established")
    marker_source_ref = _require_full_profile_ref(
        creation_marker.get("requested_source_ref"),
        code="owned_attempt_creation_source_ref_invalid",
    )
    marker_intent_ref = _require_full_profile_ref(
        creation_marker.get("observational_run_intent_ref"),
        code="owned_attempt_creation_intent_ref_invalid",
    )
    if (
        not _same_ref(marker_source_ref, anchor.requested_source_ref)
        or not _same_ref(marker_intent_ref, anchor.observational_run_intent_ref)
        or creation_marker.get("observational_selection_digest") != anchor.selection_digest
    ):
        raise ValueError("owned_attempt_creation_marker_anchor_mismatch")
    requested_intent, content_intent = _read_intents(
        service=service,
        requested_intent_ref=anchor.observational_run_intent_ref,
        content_admitted_ref=anchor.content_admitted_intent_ref,
    )
    if (
        requested_intent.job_id != anchor.job_id
        or requested_intent.run_id != anchor.run_id
        or not _same_ref(requested_intent.requested_source_ref, anchor.requested_source_ref)
        or requested_intent.selection_digest() != anchor.selection_digest
        or content_intent.job_id != anchor.job_id
        or content_intent.run_id != anchor.run_id
        or content_intent.attempt != anchor.attempt
        or content_intent.selection_digest != anchor.selection_digest
        or not _same_ref(content_intent.requested_intent_ref, anchor.observational_run_intent_ref)
        or not _same_ref(content_intent.requested_source_ref, anchor.requested_source_ref)
        or not _same_ref(content_intent.submitted_input_ref, anchor.submitted_input_ref)
        or not _same_ref(content_intent.effective_input_ref, anchor.effective_input_ref)
        or content_intent.source_manifest_sha256 != anchor.source_manifest_sha256
        or content_intent.source_protocol != anchor.source_protocol
        or content_intent.normalization != anchor.normalization
        or content_intent.method_fqn != anchor.method_fqn
        or not _same_request_context(
            _owner_request_context(requested_intent),
            anchor.input_capture.request_context,
        )
        or not _same_request_context(
            _owner_request_context(content_intent),
            anchor.input_capture.request_context,
        )
        or not _json_values_equal(
            requested_intent.resolved_params,
            anchor.input_capture.resolved_params,
        )
        or requested_intent.seed != anchor.input_capture.seed
        or requested_intent.method_abi_digest != anchor.method_abi_digest
        or requested_intent.method_build_digest != anchor.method_build_digest
        or requested_intent.resource_policy_digest != anchor.resource_policy_digest
    ):
        raise ValueError("owned_attempt_anchor_intent_fresh_read_mismatch")
    selected_policy_ref, selected_resource_policy = _read_selected_resource_policy(
        service=service,
        requested_intent=requested_intent,
        content_intent=content_intent,
    )
    if (
        not _same_ref(selected_policy_ref, anchor.resource_policy_ref)
        or selected_resource_policy.schema_version != anchor.resource_policy_schema_version
        or selected_resource_policy.revision != anchor.resource_policy_revision
        or selected_resource_policy.method_contract_target
        != anchor.resource_policy_method_contract_target
        or selected_resource_policy.required_estimator_n_jobs
        != anchor.resource_policy_required_estimator_n_jobs
        or getattr(selected_resource_policy, "method_fqn", None)
        != anchor.resource_policy_method_fqn
        or getattr(selected_resource_policy, "method_profile_id", None)
        != anchor.resource_policy_method_profile_id
        or getattr(selected_resource_policy, "execution_scope", None)
        != anchor.resource_policy_execution_scope
        or getattr(selected_resource_policy, "max_jobs", None) != anchor.resource_policy_max_jobs
    ):
        raise ValueError("owned_attempt_anchor_resource_policy_fresh_read_mismatch")

    event_selection_payload = completed_event.payload.get("method_execution_selection")
    if not isinstance(event_selection_payload, Mapping):
        raise ValueError("owned_attempt_completed_selection_owner_mismatch")
    if expected_completed_event_id is None:
        row_selection_payload = record.method_execution_selection
        if not _json_values_equal(row_selection_payload, event_selection_payload):
            raise ValueError("owned_attempt_completed_selection_owner_mismatch")
    else:
        row_selection_payload = event_selection_payload
    try:
        selected = _validate_method_execution_selection_wire_payload(row_selection_payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_completed_selection_invalid") from exc
    if type(selected) is not DirectMethodExecutionSelection:
        raise ValueError("owned_attempt_completed_selection_not_direct_hte")
    if (
        selected.job_id != anchor.job_id
        or selected.run_id != anchor.run_id
        or selected.attempt != anchor.attempt
        or not _same_ref(selected.requested_source_ref, anchor.requested_source_ref)
        or not _same_ref(
            selected.observational_run_intent_ref,
            anchor.observational_run_intent_ref,
        )
        or not _same_ref(
            selected.content_admitted_intent_ref,
            anchor.content_admitted_intent_ref,
        )
        or not _same_ref(selected.resource_policy_ref, anchor.resource_policy_ref)
        or not _same_ref(selected.submitted_input_ref, anchor.submitted_input_ref)
        or not _same_ref(selected.effective_input_ref, anchor.effective_input_ref)
        or selected.method_fqn != anchor.method_fqn
        or selected.method_version != anchor.method_version
        or selected.method_abi_digest != anchor.method_abi_digest
        or selected.method_build_digest != anchor.method_build_digest
        or selected.resource_policy_digest != anchor.resource_policy_digest
        or selected.source_protocol != anchor.source_protocol
        or selected.normalization != anchor.normalization
        or selected.selection_digest != anchor.selection_digest
        or selected.owned_hte_request_context is None
        or not _same_request_context(
            selected.owned_hte_request_context,
            anchor.input_capture.request_context,
        )
    ):
        raise ValueError("owned_attempt_selected_request_fence_mismatch")
    return _CompletedOwnedAttemptFrame(
        anchor_ref=typed_anchor_ref,
        anchor=anchor,
        record=record,
        completed_event=completed_event,
        selection=selected,
        historical_completed_event_id=expected_completed_event_id,
    )


def resolve_owned_attempt_anchor_association(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    anchor_ref: OwnedAttemptAnchorRef,
    expected_completed_event_id: int | None = None,
    expected_job_id: str | None = None,
    expected_tenant_id: str | None = None,
    expected_cell_id: str | None | object = _OWNER_SCOPE_UNSET,
) -> OwnedAttemptAnchorAssociation:
    """Reconcile one anchor to a current or exact historical completed selection.

    The resolver derives job, run, attempt, and every output ref from the owner
    row and immutable ``job_completed`` event. It never accepts those values
    from the HTE caller. Supplying ``expected_completed_event_id`` selects one
    immutable historical event and removes the current-run-winner requirement;
    the job/event/anchor triple and Search delivery outbox are still reconciled.
    The returned association means only that the exact
    owner-selected tuple and typed HTE artifacts reconcile; it does not certify
    the scientific validity of the estimate. Invocation-basis meaning remains
    ``not_established`` until its own strict artifact owner is registered.

    Raises:
        ValueError: If the anchor is not selected by the current unique completed
            owner attempt, or any selected artifact fails resolve/bind checks.
    """
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionHTESummary,
        _validate_strict_json_wire_payload,
    )
    from polisyos.ir.analytics import (
        ATEInferenceBasis,
        HTEIntervalOutcome,
        HTEOutcome,
        HTEPointOutcome,
        HTEPointResult,
        HTERefusalDiagnostic,
        HTERefusalOutcome,
        HTEResult,
    )

    owner_frame = _resolve_completed_owned_attempt_frame(
        service=service,
        anchor_ref=anchor_ref,
        expected_job_id=expected_job_id,
        expected_tenant_id=expected_tenant_id,
        expected_cell_id=expected_cell_id,
        expected_completed_event_id=expected_completed_event_id,
    )
    typed_anchor_ref = owner_frame.anchor_ref
    anchor = owner_frame.anchor
    record = owner_frame.record
    completed_event = owner_frame.completed_event
    selected = owner_frame.selection
    search_binding_ref = _require_search_binding_manifest(service=service, anchor=anchor)
    physical_binding = _require_physical_binding_content(service=service, anchor=anchor)
    if physical_binding is None:
        physical_binding_ref = None
        verified_physical_binding = None
    else:
        physical_binding_ref, verified_physical_binding = physical_binding
    owner_binding_inputs = _owner_binding_inputs(
        physical_binding_ref=physical_binding_ref,
        search_binding_ref=search_binding_ref,
    )
    selected_summary = getattr(selected, "hte", None)
    if type(selected_summary) is not DirectMethodExecutionHTESummary or not _optional_same_ref(
        selected_summary.materialization_binding_ref,
        physical_binding_ref,
    ):
        raise ValueError("owned_attempt_selected_materialization_binding_mismatch")
    selected_anchor_ref = _selection_ref(
        selected,
        "owned_attempt_anchor_ref",
        required=True,
    )
    outcome_ref = _selection_ref(selected, "hte_outcome_ref", required=True)
    method_result_ref = _selection_ref(selected, "method_result_ref", required=True)
    method_evidence_ref = _selection_ref(selected, "method_evidence_ref", required=True)
    invocation_basis_ref = _selection_ref(selected, "invocation_basis_ref", required=False)
    point_result_ref = _selection_ref(selected, "point_result_ref", required=False)
    hte_result_ref = _selection_ref(selected, "hte_result_ref", required=False)
    inference_basis_ref = _selection_ref(selected, "inference_basis_ref", required=False)
    refusal_diagnostic_ref = _selection_ref(selected, "refusal_diagnostic_ref", required=False)
    if not _same_ref(selected_anchor_ref, typed_anchor_ref) or outcome_ref is None:
        raise ValueError("owned_attempt_selected_anchor_or_outcome_mismatch")

    writer_ready, _evidence_manifest = _read_owner_selected_method_outputs(
        service=service,
        anchor=anchor,
        anchor_ref=typed_anchor_ref,
        method_result_ref=method_result_ref,
        method_evidence_ref=method_evidence_ref,
    )
    refusal_expected_limitations: tuple[str, ...] | None = None
    if writer_ready.kind == "refusal":
        if physical_binding_ref is None or verified_physical_binding is None:
            raise ValueError("owned_attempt_refusal_physical_binding_missing")
        from polisyos.scientist.compute.hte_outcome_bridge import (
            _expected_refusal_limitations,
        )

        try:
            refusal_expected_limitations = _expected_refusal_limitations(
                writer_ready,
                verified_physical_binding,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("owned_attempt_refusal_limitation_basis_invalid") from exc
    limits = service._observational_read_limits()
    outcome_bounded, outcome_payload = _read_profiled_value(
        service=service,
        selected_ref=outcome_ref,
        limits=limits,
        expected_kind="ir.hte_outcome",
        expected_schema_name="polisyos.ir.HTEOutcome",
        expected_schema_version="1.0",
    )
    try:
        outcome = _validate_strict_json_wire_payload(
            outcome_payload,
            TypeAdapter(HTEOutcome),
            invalid_code="owned_attempt_hte_outcome_invalid",
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_hte_outcome_invalid") from exc
    if (
        not _same_ref(outcome.owned_attempt_anchor_ref, typed_anchor_ref)
        or not _same_ref(outcome.method_result_ref, method_result_ref)
        or not _same_ref(outcome.method_evidence_ref, method_evidence_ref)
        or not _optional_same_ref(outcome.invocation_basis_ref, invocation_basis_ref)
        or not _optional_same_ref(
            getattr(outcome, "search_uncertainty_task_binding_ref", None),
            search_binding_ref,
        )
        or not _outcome_matches_anchor(outcome, anchor)
        or not _writer_ready_matches_outcome(writer_ready, outcome)
    ):
        raise ValueError("owned_attempt_hte_outcome_binding_mismatch")
    if invocation_basis_ref is None:
        permitted_absence_reasons = {"no_invocation_basis_artifact_contract"}
        if outcome.kind == "refusal":
            permitted_absence_reasons.add("not_available_at_refusal_stage")
        if outcome.invocation_basis_status != "not_established" or (
            outcome.invocation_basis_reason not in permitted_absence_reasons
        ):
            raise ValueError("owned_attempt_invocation_basis_absence_not_explained")
    elif (
        outcome.invocation_basis_status != "established"
        or outcome.invocation_basis_reason is not None
    ):
        raise ValueError("owned_attempt_invocation_basis_present_status_mismatch")

    source_data_ref = anchor.input_capture.source_data_ref
    outcome_variant = outcome.root
    if outcome.kind == "refusal":
        if not isinstance(outcome_variant, HTERefusalOutcome):
            raise ValueError("owned_attempt_refusal_diagnostic_owner_binding_mismatch")
        if any(ref is not None for ref in (point_result_ref, hte_result_ref, inference_basis_ref)):
            raise ValueError("owned_attempt_refusal_has_numeric_owner_result")
        if (
            writer_ready.kind != "refusal"
            or refusal_diagnostic_ref is None
            or not _same_ref(outcome.refusal_diagnostic_ref, refusal_diagnostic_ref)
            or outcome.method_abi_digest != anchor.method_abi_digest
            or physical_binding_ref is None
            or not _same_ref(outcome_variant.materialization_binding_ref, physical_binding_ref)
        ):
            raise ValueError("owned_attempt_refusal_diagnostic_owner_binding_mismatch")
        if (
            refusal_expected_limitations is None
            or tuple(outcome.limitations) != refusal_expected_limitations
        ):
            raise ValueError("owned_attempt_refusal_outcome_content_mismatch")
        receipt = writer_ready.resource_receipt
        expected_resource_evidence = _resource_evidence_payload(
            anchor=anchor,
            receipt=receipt,
            output_kind=writer_ready.kind,
        )
        outcome_resource_evidence = outcome_variant.resource_evidence
        if outcome_resource_evidence is None:
            if receipt.execution_status != "not_started":
                raise ValueError("owned_attempt_refusal_resource_evidence_missing")
        else:
            expected_resource_evidence = _resource_evidence_payload_for_consumer(
                payload=expected_resource_evidence,
                consumer=outcome_resource_evidence,
            )
            if expected_resource_evidence is None or not _json_values_equal(
                outcome_resource_evidence.model_dump(mode="json"), expected_resource_evidence
            ):
                raise ValueError("owned_attempt_refusal_resource_evidence_mismatch")

        diagnostic_bounded, diagnostic_payload = _read_profiled_value(
            service=service,
            selected_ref=refusal_diagnostic_ref,
            limits=limits,
            expected_kind="ir.hte_refusal_diagnostic",
            expected_schema_name="polisyos.ir.HTERefusalDiagnostic",
            expected_schema_version="1.0",
        )
        try:
            refusal_diagnostic = _validate_strict_json_wire_payload(
                diagnostic_payload,
                TypeAdapter(HTERefusalDiagnostic),
                invalid_code="owned_attempt_refusal_diagnostic_invalid",
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("owned_attempt_refusal_diagnostic_invalid") from exc
        diagnostic_inputs: tuple[tuple[ArtifactRef, str], ...] = (
            (typed_anchor_ref, "owned_attempt_anchor"),
            (method_result_ref, "method_result"),
            (method_evidence_ref, "method_evidence"),
        )
        if refusal_diagnostic.resource_evidence is not None:
            diagnostic_inputs += ((anchor.resource_policy_ref, "resource_policy"),)
        diagnostic_inputs += owner_binding_inputs
        _require_manifest_input_roles(
            bounded=diagnostic_bounded,
            inputs=diagnostic_inputs,
            code="owned_attempt_refusal_diagnostic_manifest_lineage_mismatch",
        )
        if not _refusal_diagnostic_matches_writer_ready(
            diagnostic=refusal_diagnostic,
            writer_ready=writer_ready,
            anchor=anchor,
            anchor_ref=typed_anchor_ref,
            method_result_ref=method_result_ref,
            method_evidence_ref=method_evidence_ref,
            materialization_binding_ref=physical_binding_ref,
            expected_limitations=refusal_expected_limitations,
        ):
            raise ValueError("owned_attempt_refusal_diagnostic_content_mismatch")
        if (refusal_diagnostic.resource_evidence is None) != (outcome_resource_evidence is None):
            raise ValueError("owned_attempt_refusal_resource_evidence_chain_mismatch")
        if outcome_resource_evidence is not None:
            diagnostic_resource_evidence = refusal_diagnostic.resource_evidence
            if diagnostic_resource_evidence is None or not _json_values_equal(
                diagnostic_resource_evidence.model_dump(mode="json"),
                outcome_resource_evidence.model_dump(mode="json"),
            ):
                raise ValueError("owned_attempt_refusal_resource_evidence_chain_mismatch")
        outcome_inputs: tuple[tuple[ArtifactRef, str], ...] = (
            (refusal_diagnostic_ref, "refusal_diagnostic"),
            (typed_anchor_ref, "owned_attempt_anchor"),
            (method_result_ref, "method_result"),
            (method_evidence_ref, "method_evidence"),
            (anchor.resource_policy_ref, "resource_policy"),
        )
        if outcome.source_data_status == "content_bound":
            outcome_inputs += ((source_data_ref, "source_data"),)
        outcome_inputs += owner_binding_inputs
        _require_manifest_input_roles(
            bounded=outcome_bounded,
            inputs=outcome_inputs,
            code="owned_attempt_refusal_outcome_manifest_lineage_mismatch",
        )
        _assert_completed_owner_frame_current(
            service=service,
            owner_frame=owner_frame,
        )
        association = OwnedAttemptAnchorAssociation(
            verified_at=datetime.now(UTC),
            anchor_ref=typed_anchor_ref,
            outcome_ref=outcome_ref,
            invocation_basis_ref=invocation_basis_ref,
            invocation_basis_content_status="not_established",
            outcome_kind="refusal",
            source_data_ref=source_data_ref,
            materialization_binding_ref=physical_binding_ref,
            search_uncertainty_task_binding_ref=search_binding_ref,
            method_result_ref=method_result_ref,
            method_evidence_ref=method_evidence_ref,
            refusal_diagnostic_ref=refusal_diagnostic_ref,
            point_result_ref=None,
            hte_result_ref=None,
            inference_basis_ref=None,
            job_completed_event=_lifecycle_event(completed_event),
            job_id=record.job_id,
            run_id=anchor.run_id,
            attempt=record.attempt,
        )
        _resolve_historical_search_binding(service=service, association=association)
        _assert_completed_owner_frame_current(service=service, owner_frame=owner_frame)
        return association

    if refusal_diagnostic_ref is not None:
        raise ValueError("owned_attempt_numeric_outcome_has_refusal_diagnostic")

    if writer_ready.kind != outcome.kind:
        raise ValueError("owned_attempt_outcome_owner_kind_mismatch")
    if not isinstance(outcome_variant, (HTEPointOutcome, HTEIntervalOutcome)):
        raise ValueError("owned_attempt_outcome_owner_kind_mismatch")
    resource_evidence_payload = _resource_evidence_payload(
        anchor=anchor,
        receipt=writer_ready.resource_receipt,
    )
    resource_evidence = _resource_evidence_payload_for_consumer(
        payload=resource_evidence_payload,
        consumer=outcome_variant.resource_evidence,
    )
    if resource_evidence is None or not _resource_evidence_matches_receipt(
        evidence=outcome_variant.resource_evidence,
        anchor=anchor,
        receipt=writer_ready.resource_receipt,
    ):
        raise ValueError("owned_attempt_outcome_resource_evidence_mismatch")

    basis: ATEInferenceBasis | None = None
    hte_result: HTEResult | None = None
    if isinstance(outcome_variant, HTEPointOutcome):
        if writer_ready.kind != "point_estimate":
            raise ValueError("owned_attempt_point_result_content_mismatch")
        if point_result_ref is None or hte_result_ref is not None:
            raise ValueError("owned_attempt_point_result_refs_invalid")
        if not _same_ref(
            getattr(outcome, "point_result_ref", None), point_result_ref
        ) or not _optional_same_ref(
            getattr(outcome, "inference_basis_ref", None),
            inference_basis_ref,
        ):
            raise ValueError("owned_attempt_point_result_outcome_ref_mismatch")
        point_bounded, point_payload = _read_profiled_value(
            service=service,
            selected_ref=point_result_ref,
            limits=limits,
            expected_kind="ir.hte_point_result",
            expected_schema_name="polisyos.ir.HTEPointResult",
            expected_schema_version="1.0",
        )
        try:
            point_result = _validate_strict_json_wire_payload(
                point_payload,
                TypeAdapter(HTEPointResult),
                invalid_code="owned_attempt_point_result_invalid",
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("owned_attempt_point_result_invalid") from exc
        _require_manifest_input_roles(
            bounded=point_bounded,
            inputs=_numeric_hte_manifest_input_roles(
                prefix=(),
                anchor_ref=typed_anchor_ref,
                source_data_ref=source_data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                resource_policy_ref=anchor.resource_policy_ref,
                owner_binding_inputs=owner_binding_inputs,
            ),
            code="owned_attempt_point_result_manifest_lineage_mismatch",
        )
        point_resource_evidence = _resource_evidence_payload_for_consumer(
            payload=resource_evidence_payload,
            consumer=point_result.resource_evidence,
        )
        if (
            point_resource_evidence is None
            or not _resource_evidence_matches_receipt(
                evidence=point_result.resource_evidence,
                anchor=anchor,
                receipt=writer_ready.resource_receipt,
            )
            or not _point_result_matches_writer_ready(
                point_result=point_result,
                writer_ready=writer_ready,
                resource_evidence=point_resource_evidence,
                anchor_ref=typed_anchor_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
            )
        ):
            raise ValueError("owned_attempt_point_result_content_mismatch")
        if inference_basis_ref is not None:
            if getattr(outcome, "inference_reason", None) != "native_inference_invalid":
                raise ValueError("owned_attempt_point_basis_disposition_invalid")
            basis_bounded, basis_payload = _read_profiled_value(
                service=service,
                selected_ref=inference_basis_ref,
                limits=limits,
                expected_kind="ir.ate_inference_basis",
                expected_schema_name="polisyos.ir.ATEInferenceBasis",
                expected_schema_version="1.0",
            )
            try:
                basis = _validate_strict_json_wire_payload(
                    basis_payload,
                    TypeAdapter(ATEInferenceBasis),
                    invalid_code="owned_attempt_inference_basis_invalid",
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("owned_attempt_inference_basis_invalid") from exc
            _require_manifest_input_roles(
                bounded=basis_bounded,
                inputs=_numeric_hte_manifest_input_roles(
                    prefix=((point_result_ref, "point_result"),),
                    anchor_ref=typed_anchor_ref,
                    source_data_ref=source_data_ref,
                    method_result_ref=method_result_ref,
                    method_evidence_ref=method_evidence_ref,
                    resource_policy_ref=anchor.resource_policy_ref,
                    owner_binding_inputs=owner_binding_inputs,
                ),
                code="owned_attempt_inference_basis_manifest_lineage_mismatch",
            )
            basis_resource_evidence = _resource_evidence_payload_for_consumer(
                payload=resource_evidence_payload,
                consumer=basis.resource_evidence,
            )
            if (
                basis_resource_evidence is None
                or not _resource_evidence_matches_receipt(
                    evidence=basis.resource_evidence,
                    anchor=anchor,
                    receipt=writer_ready.resource_receipt,
                )
                or not _basis_matches_writer_ready(
                    basis=basis,
                    writer_ready=writer_ready,
                    outcome=outcome,
                    anchor=anchor,
                    anchor_ref=typed_anchor_ref,
                    point_result_ref=point_result_ref,
                    hte_result_ref=None,
                    method_result_ref=method_result_ref,
                    method_evidence_ref=method_evidence_ref,
                    invocation_basis_ref=invocation_basis_ref,
                    resource_evidence=basis_resource_evidence,
                )
            ):
                raise ValueError("owned_attempt_inference_basis_binding_mismatch")
        _require_manifest_input_roles(
            bounded=outcome_bounded,
            inputs=_numeric_hte_outcome_input_roles(
                result_ref=point_result_ref,
                result_role="point_result",
                inference_basis_ref=inference_basis_ref,
                anchor_ref=typed_anchor_ref,
                source_data_ref=source_data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                resource_policy_ref=anchor.resource_policy_ref,
                owner_binding_inputs=owner_binding_inputs,
            ),
            code="owned_attempt_hte_outcome_manifest_lineage_mismatch",
        )
    elif isinstance(outcome_variant, HTEIntervalOutcome):
        if writer_ready.kind != "interval_estimate":
            raise ValueError("owned_attempt_hte_result_content_mismatch")
        if point_result_ref is not None or hte_result_ref is None or inference_basis_ref is None:
            raise ValueError("owned_attempt_interval_result_refs_incomplete")
        if not _same_ref(getattr(outcome, "hte_result_ref", None), hte_result_ref) or (
            not _same_ref(getattr(outcome, "inference_basis_ref", None), inference_basis_ref)
        ):
            raise ValueError("owned_attempt_interval_outcome_ref_mismatch")
        hte_bounded, hte_payload = _read_profiled_value(
            service=service,
            selected_ref=hte_result_ref,
            limits=limits,
            expected_kind="ir.hte_result",
            expected_schema_name="ir.hte_result",
            expected_schema_version="1.0",
        )
        try:
            hte_result = _validate_strict_json_wire_payload(
                hte_payload,
                TypeAdapter(HTEResult),
                invalid_code="owned_attempt_hte_result_invalid",
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("owned_attempt_hte_result_invalid") from exc
        _require_manifest_input_roles(
            bounded=hte_bounded,
            inputs=_numeric_hte_manifest_input_roles(
                prefix=(),
                anchor_ref=typed_anchor_ref,
                source_data_ref=source_data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                resource_policy_ref=anchor.resource_policy_ref,
                owner_binding_inputs=owner_binding_inputs,
            ),
            code="owned_attempt_hte_result_manifest_lineage_mismatch",
        )
        if not _resource_evidence_matches_receipt(
            evidence=outcome_variant.resource_evidence,
            anchor=anchor,
            receipt=writer_ready.resource_receipt,
        ) or not _hte_result_matches_writer_ready(
            hte_result=hte_result,
            writer_ready=writer_ready,
        ):
            raise ValueError("owned_attempt_hte_result_content_mismatch")
        basis_bounded, basis_payload = _read_profiled_value(
            service=service,
            selected_ref=inference_basis_ref,
            limits=limits,
            expected_kind="ir.ate_inference_basis",
            expected_schema_name="polisyos.ir.ATEInferenceBasis",
            expected_schema_version="1.0",
        )
        try:
            basis = _validate_strict_json_wire_payload(
                basis_payload,
                TypeAdapter(ATEInferenceBasis),
                invalid_code="owned_attempt_inference_basis_invalid",
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("owned_attempt_inference_basis_invalid") from exc
        _require_manifest_input_roles(
            bounded=basis_bounded,
            inputs=_numeric_hte_manifest_input_roles(
                prefix=((hte_result_ref, "hte_result"),),
                anchor_ref=typed_anchor_ref,
                source_data_ref=source_data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                resource_policy_ref=anchor.resource_policy_ref,
                owner_binding_inputs=owner_binding_inputs,
            ),
            code="owned_attempt_inference_basis_manifest_lineage_mismatch",
        )
        basis_resource_evidence = _resource_evidence_payload_for_consumer(
            payload=resource_evidence_payload,
            consumer=basis.resource_evidence,
        )
        if (
            basis_resource_evidence is None
            or not _resource_evidence_matches_receipt(
                evidence=basis.resource_evidence,
                anchor=anchor,
                receipt=writer_ready.resource_receipt,
            )
            or not _basis_matches_writer_ready(
                basis=basis,
                writer_ready=writer_ready,
                outcome=outcome,
                anchor=anchor,
                anchor_ref=typed_anchor_ref,
                point_result_ref=None,
                hte_result_ref=hte_result_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                invocation_basis_ref=invocation_basis_ref,
                resource_evidence=basis_resource_evidence,
            )
        ):
            raise ValueError("owned_attempt_inference_basis_binding_mismatch")
        _require_manifest_input_roles(
            bounded=outcome_bounded,
            inputs=_numeric_hte_outcome_input_roles(
                result_ref=hte_result_ref,
                result_role="hte_result",
                inference_basis_ref=inference_basis_ref,
                anchor_ref=typed_anchor_ref,
                source_data_ref=source_data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                resource_policy_ref=anchor.resource_policy_ref,
                owner_binding_inputs=owner_binding_inputs,
            ),
            code="owned_attempt_hte_outcome_manifest_lineage_mismatch",
        )
    else:
        raise ValueError("owned_attempt_hte_outcome_kind_not_supported")

    _assert_completed_owner_frame_current(
        service=service,
        owner_frame=owner_frame,
    )
    association = OwnedAttemptAnchorAssociation(
        verified_at=datetime.now(UTC),
        anchor_ref=typed_anchor_ref,
        outcome_ref=outcome_ref,
        invocation_basis_ref=invocation_basis_ref,
        invocation_basis_content_status="not_established",
        outcome_kind=outcome_variant.kind,
        source_data_ref=source_data_ref,
        materialization_binding_ref=physical_binding_ref,
        search_uncertainty_task_binding_ref=search_binding_ref,
        method_result_ref=method_result_ref,
        method_evidence_ref=method_evidence_ref,
        point_result_ref=point_result_ref,
        hte_result_ref=hte_result_ref,
        inference_basis_ref=inference_basis_ref,
        job_completed_event=_lifecycle_event(completed_event),
        job_id=record.job_id,
        run_id=anchor.run_id,
        attempt=record.attempt,
    )
    _resolve_historical_search_binding(service=service, association=association)
    _assert_completed_owner_frame_current(service=service, owner_frame=owner_frame)
    return association


def resolve_owned_attempt_anchor_projection_association(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    run_id: str,
    expected_job_id: str,
    tenant_id: str,
    cell_id: str | None,
) -> OwnedAttemptAnchorProjectionAssociation:
    """Reconcile a worker-admitted scalar HTE summary to the current winner.

    This protected-reader path resolves only manifests and owner records. It
    does not read method-result, point-result, HTE-result, or inference-basis
    payloads, and it never refits an estimator. The worker-admitted summary is
    separately marked as not recomputed here; its content binding was completed
    before Runtime persisted the selected completion record.

    Args:
        service: The existing Runtime owner and artifact store.
        run_id: Lookup key for the current workflow run.
        expected_job_id: Route-selected job ID, rechecked against current owner state.
        tenant_id: Authorized tenant scope, rechecked against the creation event.
        cell_id: Authorized cell scope, rechecked against the creation event.

    Returns:
        A bounded proof of the current owner row, selected scalar summary digest,
        typed references, and exact manifest identities.

    Raises:
        ValueError: If the current winner, selected summary, lineage, or any
            selected manifest differs from the immutable pre-output anchor.
    """
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionHTESummary,
        DirectMethodExecutionSelection,
        _validate_method_execution_selection_wire_payload,
    )

    if not all(isinstance(value, str) and value for value in (run_id, expected_job_id, tenant_id)):
        raise ValueError("owned_attempt_projection_lookup_keys_invalid")
    if cell_id is not None and (not isinstance(cell_id, str) or not cell_id):
        raise ValueError("owned_attempt_projection_cell_lookup_invalid")

    control_store = service._control_store
    try:
        current_record = control_store.get_latest_job_by_run(run_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_projection_current_owner_unavailable") from exc
    if (
        current_record is None
        or current_record.job_id != expected_job_id
        or current_record.run_id != run_id
        or current_record.kind != "workflow_run"
        or current_record.state != "completed"
        or not isinstance(current_record.method_execution_selection, Mapping)
    ):
        raise ValueError("owned_attempt_projection_current_completed_winner_mismatch")
    try:
        selected = _validate_method_execution_selection_wire_payload(
            current_record.method_execution_selection
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_projection_selection_invalid") from exc
    if type(selected) is not DirectMethodExecutionSelection:
        raise ValueError("owned_attempt_projection_selection_not_direct_hte")
    raw_anchor_ref = _selection_ref(
        selected,
        "owned_attempt_anchor_ref",
        required=True,
    )
    if raw_anchor_ref is None:
        raise ValueError("owned_attempt_projection_anchor_ref_missing")
    anchor_ref = _owned_attempt_anchor_ref(
        raw_anchor_ref,
        code="owned_attempt_projection_anchor_ref_invalid",
    )
    owner_frame = _resolve_completed_owned_attempt_frame(
        service=service,
        anchor_ref=anchor_ref,
        expected_run_id=run_id,
        expected_job_id=expected_job_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    anchor = owner_frame.anchor
    selected = owner_frame.selection
    summary = selected.hte
    if type(summary) is not DirectMethodExecutionHTESummary:
        raise ValueError("owned_attempt_projection_worker_summary_missing")

    outcome_ref = _selected_profile_ref(
        _selection_ref(selected, "hte_outcome_ref", required=True),
        code="owned_attempt_projection_outcome_ref_invalid",
    )
    method_result_ref = _selected_profile_ref(
        _selection_ref(selected, "method_result_ref", required=True),
        code="owned_attempt_projection_method_result_ref_invalid",
    )
    method_evidence_ref = _selected_profile_ref(
        _selection_ref(selected, "method_evidence_ref", required=True),
        code="owned_attempt_projection_method_evidence_ref_invalid",
    )
    point_result_ref = _selection_ref(selected, "point_result_ref", required=False)
    hte_result_ref = _selection_ref(selected, "hte_result_ref", required=False)
    inference_basis_ref = _selection_ref(selected, "inference_basis_ref", required=False)
    refusal_diagnostic_ref = _selection_ref(
        selected,
        "refusal_diagnostic_ref",
        required=False,
    )
    invocation_basis_ref = _selection_ref(selected, "invocation_basis_ref", required=False)
    capture = anchor.input_capture
    request_context = capture.request_context
    search_binding_ref = _require_search_binding_manifest(service=service, anchor=anchor)
    materialization_binding_ref = _anchor_materialization_binding_ref(anchor)
    owner_binding_inputs = _owner_binding_inputs(
        physical_binding_ref=materialization_binding_ref,
        search_binding_ref=search_binding_ref,
    )
    resource_evidence = summary.resource_evidence

    expected_summary_refs = (
        ("owned_attempt_anchor_ref", anchor_ref),
        ("hte_outcome_ref", outcome_ref),
        ("method_result_ref", method_result_ref),
        ("method_evidence_ref", method_evidence_ref),
        ("point_result_ref", point_result_ref),
        ("hte_result_ref", hte_result_ref),
        ("inference_basis_ref", inference_basis_ref),
        ("refusal_diagnostic_ref", refusal_diagnostic_ref),
        ("search_uncertainty_task_binding_ref", search_binding_ref),
        ("materialization_binding_ref", materialization_binding_ref),
    )
    if any(
        not _optional_same_ref(getattr(summary, name, None), expected)
        for name, expected in expected_summary_refs
    ):
        raise ValueError("owned_attempt_projection_selected_summary_ref_mismatch")
    if (
        summary.method_fqn != anchor.method_fqn
        or summary.method_abi_digest != anchor.method_abi_digest
        or summary.method_profile_id != capture.method_profile_id
        or summary.resolved_params_sha256 != capture.resolved_params_sha256
        or not _same_ref(resource_evidence.owner_policy_ref, anchor.resource_policy_ref)
        or resource_evidence.owner_policy_digest != anchor.resource_policy_digest
        or resource_evidence.owner_policy_schema_version != anchor.resource_policy_schema_version
        or resource_evidence.owner_policy_revision != anchor.resource_policy_revision
        or resource_evidence.owner_policy_method_fqn != anchor.resource_policy_method_fqn
        or resource_evidence.owner_policy_method_profile_id
        != anchor.resource_policy_method_profile_id
        or resource_evidence.owner_policy_execution_scope != anchor.resource_policy_execution_scope
        or resource_evidence.owner_policy_max_jobs != anchor.resource_policy_max_jobs
        or resource_evidence.owner_policy_required_estimator_n_jobs
        != anchor.resource_policy_required_estimator_n_jobs
        or summary.request_estimand_status != request_context.request_estimand_status
        or summary.request_estimand != request_context.request_estimand
        or summary.request_target_scope_status != request_context.request_target_scope_status
        or summary.request_target_scope != request_context.request_target_scope
        or summary.outcome_variable_status != request_context.outcome_variable_status
        or summary.outcome_variable_id != request_context.outcome_variable_id
        or summary.treatment_variable_status != request_context.treatment_variable_status
        or summary.treatment_variable_id != request_context.treatment_variable_id
        or summary.request_contrast_status != request_context.contrast_status
        or summary.control_value != request_context.control_value
        or summary.treated_value != request_context.treated_value
        or summary.request_alpha_status != request_context.request_alpha_status
        or summary.requested_alpha != request_context.requested_alpha
        or summary.requested_guarantee_status != request_context.requested_guarantee_status
        or summary.requested_guarantee != request_context.requested_guarantee
        or not _optional_same_ref(
            getattr(summary, "search_uncertainty_task_binding_ref", None),
            search_binding_ref,
        )
    ):
        raise ValueError("owned_attempt_projection_summary_anchor_mismatch")

    source_summary_ref = getattr(summary, "source_data_ref", None)
    if (
        source_summary_ref is None
        or not _same_ref(source_summary_ref, capture.source_data_ref)
        or not _same_ref(source_summary_ref, selected.effective_input_ref)
    ):
        raise ValueError("owned_attempt_projection_source_summary_mismatch")
    if summary.kind == "point_estimate":
        if (
            summary.selected_rows_status != "recomputed"
            or summary.n_selected_rows != capture.n_selected_rows
            or summary.selected_rows_sha256 != capture.selected_rows_sha256
            or summary.selected_row_order_sha256 != capture.selected_row_order_sha256
            or summary.selected_x_sha256 != capture.selected_x_sha256
            or point_result_ref is None
            or hte_result_ref is not None
        ):
            raise ValueError("owned_attempt_projection_recomputed_rows_mismatch")
        if inference_basis_ref is not None and (
            summary.inference_status != "failed"
            or summary.inference_reason != "native_inference_invalid"
        ):
            raise ValueError("owned_attempt_projection_point_basis_disposition_invalid")
    elif summary.kind == "interval_estimate":
        if (
            summary.selected_rows_status != "recomputed"
            or summary.n_selected_rows != capture.n_selected_rows
            or summary.selected_rows_sha256 != capture.selected_rows_sha256
            or summary.selected_row_order_sha256 != capture.selected_row_order_sha256
            or summary.selected_x_sha256 != capture.selected_x_sha256
            or point_result_ref is not None
            or hte_result_ref is None
            or inference_basis_ref is None
        ):
            raise ValueError("owned_attempt_projection_recomputed_rows_mismatch")
    elif summary.kind == "refusal":
        if (
            point_result_ref is not None
            or hte_result_ref is not None
            or inference_basis_ref is not None
            or refusal_diagnostic_ref is None
            or summary.selected_rows_status != "not_established"
        ):
            raise ValueError("owned_attempt_projection_refusal_summary_mismatch")
    else:
        raise ValueError("owned_attempt_projection_summary_kind_unsupported")

    if not _same_ref(selected.resource_policy_ref, anchor.resource_policy_ref):
        raise ValueError("owned_attempt_projection_selected_policy_mismatch")
    selected_summary_sha256 = _canonical_json_digest(summary.model_dump(mode="json"))

    manifests: dict[str, ArtifactManifest] = {}

    def read_manifest(
        key: str,
        ref: ArtifactRef,
        kind: str,
        schema_name: str,
        schema_version: str,
    ) -> ArtifactManifest:
        manifest = _read_projection_manifest(
            service=service,
            selected_ref=ref,
            expected_kind=kind,
            expected_schema_name=schema_name,
            expected_schema_version=schema_version,
        )
        manifests[key] = manifest
        return manifest

    read_manifest(
        "anchor",
        anchor_ref,
        OWNED_ATTEMPT_ANCHOR_KIND,
        OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME,
        OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION,
    )
    if search_binding_ref is not None:
        read_manifest(
            "search_binding",
            search_binding_ref,
            "scientist.search.uncertainty_task_binding",
            "polisyos.scientist.SearchUncertaintyTaskBinding",
            "1.0",
        )
    if materialization_binding_ref is not None:
        read_manifest(
            "materialization_binding",
            materialization_binding_ref,
            "foundry.hte.physical_source_materialization_binding",
            "polisyos.foundry.HTEPhysicalSourceMaterializationBinding",
            "1.0",
        )
    read_manifest(
        "source",
        capture.source_data_ref,
        "ir.observation_method_input",
        "polisyos.ir.ObservationMethodInputEnvelope",
        "1.0",
    )
    read_manifest(
        "resource_policy",
        anchor.resource_policy_ref,
        "runtime.observational_input_resource_policy",
        "polisyos.runtime.ObservationalInputResourcePolicy",
        "1.0",
    )
    read_manifest(
        "method_result",
        method_result_ref,
        "scientist.method_result.causal.hte",
        "polisyos.scientist.MethodResult",
        "0.1.0",
    )
    read_manifest(
        "method_evidence",
        method_evidence_ref,
        "scientist.method_evidence",
        "polisyos.scientist.MethodExecutionEvidence",
        "0.1.0",
    )
    read_manifest(
        "outcome",
        outcome_ref,
        "ir.hte_outcome",
        "polisyos.ir.HTEOutcome",
        "1.0",
    )
    if summary.kind == "refusal":
        read_manifest(
            "refusal_diagnostic",
            _required_projection_ref(
                refusal_diagnostic_ref,
                code="owned_attempt_projection_refusal_summary_mismatch",
            ),
            "ir.hte_refusal_diagnostic",
            "polisyos.ir.HTERefusalDiagnostic",
            "1.0",
        )
    else:
        if summary.kind == "point_estimate":
            read_manifest(
                "point_result",
                _required_projection_ref(
                    point_result_ref,
                    code="owned_attempt_projection_recomputed_rows_mismatch",
                ),
                "ir.hte_point_result",
                "polisyos.ir.HTEPointResult",
                "1.0",
            )
        elif summary.kind == "interval_estimate":
            read_manifest(
                "hte_result",
                _required_projection_ref(
                    hte_result_ref,
                    code="owned_attempt_projection_recomputed_rows_mismatch",
                ),
                "ir.hte_result",
                "ir.hte_result",
                "1.0",
            )
            read_manifest(
                "inference_basis",
                _required_projection_ref(
                    inference_basis_ref,
                    code="owned_attempt_projection_recomputed_rows_mismatch",
                ),
                "ir.ate_inference_basis",
                "polisyos.ir.ATEInferenceBasis",
                "1.0",
            )
        elif inference_basis_ref is not None:
            read_manifest(
                "point_result",
                _required_projection_ref(
                    point_result_ref,
                    code="owned_attempt_projection_recomputed_rows_mismatch",
                ),
                "ir.hte_point_result",
                "polisyos.ir.HTEPointResult",
                "1.0",
            )
            read_manifest(
                "inference_basis",
                inference_basis_ref,
                "ir.ate_inference_basis",
                "polisyos.ir.ATEInferenceBasis",
                "1.0",
            )
    if invocation_basis_ref is not None:
        try:
            invocation_manifest = service._artifact_store.get_manifest(invocation_basis_ref)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("owned_attempt_projection_invocation_manifest_unavailable") from exc
        if (
            getattr(invocation_manifest, "artifact_id", None) != invocation_basis_ref.artifact_id
            or getattr(invocation_manifest, "kind", None) != invocation_basis_ref.kind
            or getattr(invocation_manifest, "media_type", None) != invocation_basis_ref.media_type
            or getattr(invocation_manifest, "artifact_schema", None) is None
            or artifact_manifest_profile_sha256(invocation_manifest)
            != invocation_basis_ref.manifest_profile_sha256
        ):
            raise ValueError("owned_attempt_projection_invocation_manifest_mismatch")

    if tuple(getattr(manifests["method_result"], "inputs", ())) != (
        _expected_method_result_inputs(anchor, anchor_ref)
    ):
        raise ValueError("owned_attempt_projection_method_result_lineage_mismatch")
    expected_evidence_inputs = (
        input_ref_from_artifact_ref(method_result_ref, role="method_result"),
        *_expected_method_result_inputs(anchor, anchor_ref),
    )
    if tuple(getattr(manifests["method_evidence"], "inputs", ())) != expected_evidence_inputs:
        raise ValueError("owned_attempt_projection_method_evidence_lineage_mismatch")

    source_data_ref = capture.source_data_ref
    resource_policy_ref = anchor.resource_policy_ref
    outcome_variants: tuple[tuple[tuple[ArtifactRef, str], ...], ...] = ()
    if summary.kind == "refusal":
        diagnostic_inputs = (
            (anchor_ref, "owned_attempt_anchor"),
            (method_result_ref, "method_result"),
            (method_evidence_ref, "method_evidence"),
            (resource_policy_ref, "resource_policy"),
            *owner_binding_inputs,
        )
        _require_projection_manifest_inputs(
            manifest=manifests["refusal_diagnostic"],
            inputs=diagnostic_inputs,
            code="owned_attempt_projection_refusal_diagnostic_lineage_mismatch",
        )
        outcome_inputs = (
            (
                _required_projection_ref(
                    refusal_diagnostic_ref,
                    code="owned_attempt_projection_refusal_summary_mismatch",
                ),
                "refusal_diagnostic",
            ),
            (anchor_ref, "owned_attempt_anchor"),
            (method_result_ref, "method_result"),
            (method_evidence_ref, "method_evidence"),
            (resource_policy_ref, "resource_policy"),
            (source_data_ref, "source_data"),
            *owner_binding_inputs,
        )
        outcome_variants = (outcome_inputs,)
    else:
        if summary.kind == "point_estimate":
            point_inputs = (
                *_numeric_hte_manifest_input_roles(
                    prefix=(),
                    anchor_ref=anchor_ref,
                    source_data_ref=source_data_ref,
                    method_result_ref=method_result_ref,
                    method_evidence_ref=method_evidence_ref,
                    resource_policy_ref=resource_policy_ref,
                    owner_binding_inputs=owner_binding_inputs,
                ),
            )
            _require_projection_manifest_inputs(
                manifest=manifests["point_result"],
                inputs=point_inputs,
                code="owned_attempt_projection_point_result_lineage_mismatch",
            )
            outcome_inputs = _numeric_hte_outcome_input_roles(
                result_ref=_required_projection_ref(
                    point_result_ref,
                    code="owned_attempt_projection_recomputed_rows_mismatch",
                ),
                result_role="point_result",
                inference_basis_ref=inference_basis_ref,
                anchor_ref=anchor_ref,
                source_data_ref=source_data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                resource_policy_ref=resource_policy_ref,
                owner_binding_inputs=owner_binding_inputs,
            )
            if inference_basis_ref is not None:
                _require_projection_manifest_inputs(
                    manifest=manifests["inference_basis"],
                    inputs=_numeric_hte_manifest_input_roles(
                        prefix=(
                            (
                                _required_projection_ref(
                                    point_result_ref,
                                    code="owned_attempt_projection_recomputed_rows_mismatch",
                                ),
                                "point_result",
                            ),
                        ),
                        anchor_ref=anchor_ref,
                        source_data_ref=source_data_ref,
                        method_result_ref=method_result_ref,
                        method_evidence_ref=method_evidence_ref,
                        resource_policy_ref=resource_policy_ref,
                        owner_binding_inputs=owner_binding_inputs,
                    ),
                    code="owned_attempt_projection_basis_lineage_mismatch",
                )
        else:
            outcome_inputs = _numeric_hte_outcome_input_roles(
                result_ref=_required_projection_ref(
                    hte_result_ref,
                    code="owned_attempt_projection_recomputed_rows_mismatch",
                ),
                result_role="hte_result",
                inference_basis_ref=_required_projection_ref(
                    inference_basis_ref,
                    code="owned_attempt_projection_recomputed_rows_mismatch",
                ),
                anchor_ref=anchor_ref,
                source_data_ref=source_data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                resource_policy_ref=resource_policy_ref,
                owner_binding_inputs=owner_binding_inputs,
            )
            _require_projection_manifest_inputs(
                manifest=manifests["inference_basis"],
                inputs=_numeric_hte_manifest_input_roles(
                    prefix=(
                        (
                            _required_projection_ref(
                                hte_result_ref,
                                code="owned_attempt_projection_recomputed_rows_mismatch",
                            ),
                            "hte_result",
                        ),
                    ),
                    anchor_ref=anchor_ref,
                    source_data_ref=source_data_ref,
                    method_result_ref=method_result_ref,
                    method_evidence_ref=method_evidence_ref,
                    resource_policy_ref=resource_policy_ref,
                    owner_binding_inputs=owner_binding_inputs,
                ),
                code="owned_attempt_projection_basis_lineage_mismatch",
            )
            _require_projection_manifest_inputs(
                manifest=manifests["hte_result"],
                inputs=_numeric_hte_manifest_input_roles(
                    prefix=(),
                    anchor_ref=anchor_ref,
                    source_data_ref=source_data_ref,
                    method_result_ref=method_result_ref,
                    method_evidence_ref=method_evidence_ref,
                    resource_policy_ref=resource_policy_ref,
                    owner_binding_inputs=owner_binding_inputs,
                ),
                code="owned_attempt_projection_hte_result_lineage_mismatch",
            )
    if summary.kind != "refusal":
        outcome_variants = (outcome_inputs,)
    _require_projection_manifest_input_variants(
        manifest=manifests["outcome"],
        alternatives=outcome_variants,
        code="owned_attempt_projection_outcome_lineage_mismatch",
    )

    _assert_completed_owner_frame_current(
        service=service,
        owner_frame=owner_frame,
    )

    return OwnedAttemptAnchorProjectionAssociation(
        verified_at=datetime.now(UTC),
        anchor_ref=anchor_ref,
        outcome_ref=outcome_ref,
        outcome_kind=summary.kind,
        selected_summary_sha256=selected_summary_sha256,
        source_data_ref=source_data_ref,
        materialization_binding_ref=materialization_binding_ref,
        search_uncertainty_task_binding_ref=search_binding_ref,
        source_data_summary_status="content_bound",
        resource_policy_ref=resource_policy_ref,
        method_result_ref=method_result_ref,
        method_evidence_ref=method_evidence_ref,
        invocation_basis_ref=(
            _selected_profile_ref(
                invocation_basis_ref,
                code="owned_attempt_projection_invocation_ref_invalid",
            )
            if invocation_basis_ref is not None
            else None
        ),
        point_result_ref=(
            _selected_profile_ref(
                point_result_ref,
                code="owned_attempt_projection_point_ref_invalid",
            )
            if point_result_ref is not None
            else None
        ),
        hte_result_ref=(
            _selected_profile_ref(
                hte_result_ref,
                code="owned_attempt_projection_hte_result_ref_invalid",
            )
            if hte_result_ref is not None
            else None
        ),
        inference_basis_ref=(
            _selected_profile_ref(
                inference_basis_ref,
                code="owned_attempt_projection_basis_ref_invalid",
            )
            if inference_basis_ref is not None
            else None
        ),
        refusal_diagnostic_ref=(
            _selected_profile_ref(
                refusal_diagnostic_ref,
                code="owned_attempt_projection_diagnostic_ref_invalid",
            )
            if refusal_diagnostic_ref is not None
            else None
        ),
        job_completed_event=_lifecycle_event(owner_frame.completed_event),
        job_id=owner_frame.record.job_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        attempt=owner_frame.record.attempt,
    )


def resolve_owned_attempt_anchor_refusal_association(
    *,
    service: OwnedAttemptAnchorRuntimeHost,
    anchor_ref: OwnedAttemptAnchorRef,
) -> OwnedAttemptAnchorRefusalAssociation:
    """Reconcile an input-refusal anchor to the current failed worker attempt.

    The resolver reads the latest job row and terminal failure event from the
    Runtime owner, then resolves the exact profile-qualified anchor from the
    event payload. Mutable progress and caller-supplied job, run, attempt, or
    failure fields do not establish the association.

    Raises:
        ValueError: If the anchor is not selected by the current failed job,
            the event fence is stale, or request/source/policy bindings drift.
    """
    typed_anchor_ref = _owned_attempt_anchor_ref(
        anchor_ref,
        code="owned_attempt_anchor_ref_invalid",
    )
    anchor = _read_owned_attempt_anchor(service=service, anchor_ref=typed_anchor_ref)
    if not isinstance(anchor.input_admission, OwnedAttemptHTEInputRefused):
        raise ValueError("owned_attempt_anchor_is_not_input_refused")
    search_binding_ref = _anchor_search_binding_ref(anchor)

    control_store = service._control_store
    try:
        record = control_store.get_latest_job_by_run(anchor.run_id)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_refusal_owner_read_failed") from exc
    if record is None:
        raise ValueError("owned_attempt_refusal_current_job_missing")
    if (
        record.kind != "workflow_run"
        or record.state != "failed"
        or record.job_id != anchor.job_id
        or record.run_id != anchor.run_id
        or type(record.attempt) is not int
        or record.attempt != anchor.attempt
        or record.lease_owner is not None
        or record.lease_expires_at is not None
        or record.method_execution_selection is not None
    ):
        raise ValueError("owned_attempt_refusal_not_current_failed_winner")
    try:
        created_event = control_store._get_job_created_source_event_record(record.job_id)
        running_event = control_store._latest_control_job_lifecycle_event_record(
            job_id=record.job_id,
            event_type="job_running",
        )
        failed_event = control_store.get_job_terminal_source_event_record(record.job_id)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_refusal_owner_read_failed") from exc

    failed_payload = getattr(failed_event, "payload", None)
    if not isinstance(failed_payload, Mapping):
        raise ValueError("owned_attempt_refusal_failed_event_payload_invalid")
    selected_anchor_value = failed_payload.get("owned_attempt_anchor_ref")
    selected_anchor_ref = _require_full_profile_ref(
        selected_anchor_value,
        code="owned_attempt_refusal_event_anchor_ref_invalid",
    )
    if (
        failed_event.event_type != "job_failed"
        or failed_event.job_id != record.job_id
        or failed_payload.get("state") != "failed"
        or failed_payload.get("owned_attempt_failure_disposition") != "input_refused"
        or not _same_ref(selected_anchor_ref, typed_anchor_ref)
        or failed_payload.get("lease_owner") != anchor.worker_id
        or type(failed_payload.get("attempt")) is not int
        or failed_payload.get("attempt") != anchor.attempt
        or created_event.event_type != "job_created"
        or created_event.job_id != anchor.job_id
        or created_event.event_id != anchor.job_created_event.event_id
        or created_event.payload_sha256 != anchor.job_created_event.payload_sha256
        or running_event.event_type != "job_running"
        or running_event.job_id != anchor.job_id
        or _lifecycle_event(running_event) != anchor.job_running_event
        or failed_event.event_id <= running_event.event_id
        or running_event.created_at > failed_event.created_at
        or anchor.captured_at > failed_event.created_at
    ):
        raise ValueError("owned_attempt_refusal_terminal_fence_mismatch")

    from polisyos.runtime.http.services.control_plane_store import (
        _control_job_execution_scope_from_event,
    )

    scope = _control_job_execution_scope_from_event(created_event.payload)
    creation_marker = created_event.payload.get("observational_method_execution")
    if (
        scope.status != "established"
        or scope.tenant_id != anchor.tenant_id
        or scope.cell_id != anchor.cell_id
        or not isinstance(creation_marker, Mapping)
        or created_event.payload.get("run_id") != anchor.run_id
        or created_event.payload.get("job_kind") != "workflow_run"
    ):
        raise ValueError("owned_attempt_refusal_creation_scope_or_marker_invalid")
    marker_source_ref = _require_full_profile_ref(
        creation_marker.get("requested_source_ref"),
        code="owned_attempt_refusal_creation_source_ref_invalid",
    )
    marker_intent_ref = _require_full_profile_ref(
        creation_marker.get("observational_run_intent_ref"),
        code="owned_attempt_refusal_creation_intent_ref_invalid",
    )
    if (
        not _same_ref(marker_source_ref, anchor.requested_source_ref)
        or not _same_ref(marker_intent_ref, anchor.observational_run_intent_ref)
        or creation_marker.get("observational_selection_digest") != anchor.selection_digest
    ):
        raise ValueError("owned_attempt_refusal_creation_marker_anchor_mismatch")

    requested_intent = _read_requested_intent(
        service=service,
        requested_intent_ref=anchor.observational_run_intent_ref,
    )
    policy_ref, selected_policy = _read_selected_resource_policy(
        service=service,
        requested_intent=requested_intent,
        content_intent=None,
    )
    request_context = _owner_request_context(requested_intent)
    if (
        requested_intent.job_id != anchor.job_id
        or requested_intent.run_id != anchor.run_id
        or not _same_ref(requested_intent.requested_source_ref, anchor.requested_source_ref)
        or requested_intent.selection_digest() != anchor.selection_digest
        or not _same_ref(policy_ref, anchor.resource_policy_ref)
        or requested_intent.source_manifest_sha256 != anchor.source_manifest_sha256
        or requested_intent.method_fqn != anchor.method_fqn
        or requested_intent.method_version != anchor.method_version
        or requested_intent.method_abi_digest != anchor.method_abi_digest
        or requested_intent.method_build_digest != anchor.method_build_digest
        or requested_intent.resource_policy_digest != anchor.resource_policy_digest
        or requested_intent.protocol != anchor.source_protocol
        or not _same_request_context(request_context, anchor.request_context)
        or _resolved_params_digest(requested_intent.resolved_params, requested_intent.seed)
        != anchor.resolved_params_sha256
        or selected_policy.schema_version != anchor.resource_policy_schema_version
        or selected_policy.revision != anchor.resource_policy_revision
        or selected_policy.method_contract_target != anchor.resource_policy_method_contract_target
        or selected_policy.required_estimator_n_jobs
        != anchor.resource_policy_required_estimator_n_jobs
        or getattr(selected_policy, "method_fqn", None) != anchor.resource_policy_method_fqn
        or getattr(selected_policy, "method_profile_id", None)
        != anchor.resource_policy_method_profile_id
        or getattr(selected_policy, "execution_scope", None)
        != anchor.resource_policy_execution_scope
        or getattr(selected_policy, "max_jobs", None) != anchor.resource_policy_max_jobs
    ):
        raise ValueError("owned_attempt_refusal_request_or_policy_binding_mismatch")

    # The record and terminal event are both fresh reads; make sure neither
    # moved while the immutable request and policy artifacts were resolved.
    try:
        latest_after = control_store.get_latest_job_by_run(anchor.run_id)
        terminal_after = control_store.get_job_terminal_source_event_record(record.job_id)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("owned_attempt_refusal_owner_readback_failed") from exc
    if (
        latest_after is None
        or latest_after.job_id != record.job_id
        or latest_after.kind != "workflow_run"
        or latest_after.run_id != record.run_id
        or latest_after.state != "failed"
        or latest_after.attempt != record.attempt
        or latest_after.lease_owner is not None
        or latest_after.lease_expires_at is not None
        or latest_after.method_execution_selection is not None
        or terminal_after.event_id != failed_event.event_id
        or terminal_after.payload_sha256 != failed_event.payload_sha256
    ):
        raise ValueError("owned_attempt_refusal_owner_changed_during_resolution")

    return OwnedAttemptAnchorRefusalAssociation(
        verified_at=datetime.now(UTC),
        status="input_refusal_reconciled",
        anchor_ref=typed_anchor_ref,
        refusal=anchor.input_admission.refusal,
        requested_source_ref=anchor.requested_source_ref,
        search_uncertainty_task_binding_ref=search_binding_ref,
        observational_run_intent_ref=anchor.observational_run_intent_ref,
        resource_policy_ref=anchor.resource_policy_ref,
        job_failed_event=_lifecycle_event(failed_event),
        job_id=record.job_id,
        run_id=anchor.run_id,
        attempt=record.attempt,
    )


__all__ = [
    "OwnedAttemptAnchorRuntimeHost",
    "OwnedAttemptAnchorVersionRefusalError",
    "persist_pre_output_hte_input_refusal_anchor",
    "persist_pre_output_owned_attempt_anchor",
    "resolve_owned_attempt_anchor_association",
    "resolve_owned_attempt_anchor_projection_association",
    "resolve_owned_attempt_anchor_refusal_association",
]
