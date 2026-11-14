"""Produce and reconcile candidate-scoped entity axes from selected views."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core.artifacts import (
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStore,
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    InputRef,
    ProducerInfo,
    PutOptions,
    input_ref_from_artifact_ref,
    read_core_json_artifact_bounded,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts import (
    EntityAxisMemberId,
    EntityAxisValueIdentity,
    SelectedEntityAxis,
)
from polisyos.core.contracts import (
    entity_axis_digest as _axis_digest,
)
from polisyos.core.contracts import (
    entity_axis_member_sort_key as _member_sort_key,
)
from polisyos.core.contracts import (
    entity_axis_membership_digest as _membership_digest,
)

ENTITY_AXIS_PRODUCER = "polisyos.foundry.data_plane.entity_axis"
ENTITY_AXIS_PRODUCER_VERSION = "1.0.0"
_SHA256 = "sha256:"


class EntityAxisStore(CoreJSONArtifactBoundedMemberReader, CoreJSONArtifactStore, Protocol):
    """Selected Core JSON store used to produce and reconcile entity axes."""


class EntityAxisRefusal(ValueError):
    """Refuse an axis operation when identity, source, or alignment is unproven."""


class EntityAxisArtifactResult(BaseModel):
    """Persisted axis and the exact selected artifact reference returned by its producer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ref: ArtifactRef
    axis: SelectedEntityAxis


@dataclass(frozen=True, slots=True)
class AlignedEntityVector:
    """Immutable aligned bytes and identity that must accompany persistence."""

    _value_bytes: bytes = field(repr=False)
    dtype: str
    shape: tuple[int, ...]
    identity: EntityAxisValueIdentity

    @property
    def values(self) -> np.ndarray:
        """Return a fresh read-only view backed by immutable bytes."""
        return np.frombuffer(self._value_bytes, dtype=np.dtype(self.dtype)).reshape(self.shape)


def build_caller_declared_entity_axis(
    *,
    store: EntityAxisStore,
    namespace: str,
    revision: str,
    member_ids: Sequence[EntityAxisMemberId],
    limits: CoreJsonReadLimits,
    governance: ArtifactGovernanceInfo | None = None,
    tenant_context: ArtifactTenantContextInfo | None = None,
) -> EntityAxisArtifactResult:
    """Persist a caller-asserted finite axis without claiming model selection.

    The caller supplies the namespace, revision, and IDs. This artifact records
    that assertion; it does not establish that the axis is selected by a model
    or corresponds to external or representative entities. A future model
    bridge must select this exact artifact reference before method use.
    """
    axis = _axis_from_members(
        identity_basis="caller_declared_model_axis",
        namespace=namespace,
        member_ids=member_ids,
        model_revision=revision,
        membership_provenance="consumer_asserted",
    )
    ref = _persist_axis(
        store=store,
        axis=axis,
        limits=limits,
        governance=governance,
        tenant_context=tenant_context,
        inputs=(),
    )
    return EntityAxisArtifactResult(ref=ref, axis=axis)


def build_selected_source_entity_axis(
    *,
    store: EntityAxisStore,
    source_view_ref: ArtifactRef,
    namespace: str,
    member_values_pointer: str,
    limits: CoreJsonReadLimits,
    governance: ArtifactGovernanceInfo | None = None,
    tenant_context: ArtifactTenantContextInfo | None = None,
) -> EntityAxisArtifactResult:
    """Derive and persist axis membership by reopening a selected source view.

    The selected Core JSON view must contain an array of stable string or
    integer IDs at ``member_values_pointer``. Caller-provided IDs are never
    accepted on this path. The selected view and its profile are re-read using
    the bounded canonical reader before membership is derived.
    """
    if type(source_view_ref) is not ArtifactRef or not source_view_ref.manifest_profile_sha256:
        raise EntityAxisRefusal("entity_axis_selected_view_profile_required")
    selected = _read_selected_view(store, source_view_ref, limits=limits)
    payload = require_declared_profile(selected.profile_read)
    values = _json_pointer(payload, member_values_pointer)
    if type(values) is not list or not values:
        raise EntityAxisRefusal("entity_axis_selected_member_array_required")
    members = tuple(_member_from_json_value(value) for value in values)
    axis = _axis_from_members(
        identity_basis="selected_source_view",
        namespace=namespace,
        member_ids=members,
        source_view_ref=source_view_ref,
        member_values_pointer=member_values_pointer,
        membership_provenance="recomputed_from_selected_view",
    )
    ref = _persist_axis(
        store=store,
        axis=axis,
        limits=limits,
        governance=governance,
        tenant_context=tenant_context,
        inputs=(input_ref_from_artifact_ref(source_view_ref, role="selected_source_view"),),
    )
    return EntityAxisArtifactResult(ref=ref, axis=axis)


def reconcile_entity_axis(
    *,
    store: EntityAxisStore,
    axis_ref: ArtifactRef,
    limits: CoreJsonReadLimits,
) -> SelectedEntityAxis:
    """Reopen an axis artifact and replay only its declared evidence basis.

    Selected-source axes are recomputed from their selected source bytes.
    Caller-declared axes can only have their internal digests checked; their
    membership remains consumer-asserted because no selected model source is
    currently joined to them.
    """
    axis, manifest = _read_axis(store, axis_ref, limits=limits)
    if axis.identity_basis == "selected_source_view":
        assert axis.source_view_ref is not None
        expected_inputs = (
            input_ref_from_artifact_ref(axis.source_view_ref, role="selected_source_view"),
        )
        selected = _read_selected_view(store, axis.source_view_ref, limits=limits)
        values = _json_pointer(
            require_declared_profile(selected.profile_read),
            axis.member_values_pointer or "",
        )
        if type(values) is not list:
            raise EntityAxisRefusal("entity_axis_selected_member_array_required")
        recomputed = _axis_from_members(
            identity_basis="selected_source_view",
            namespace=axis.namespace,
            member_ids=tuple(_member_from_json_value(value) for value in values),
            source_view_ref=axis.source_view_ref,
            member_values_pointer=axis.member_values_pointer or "",
            membership_provenance="recomputed_from_selected_view",
        )
    else:
        expected_inputs = ()
        # The stored IDs are caller assertions, not a source readset. Validate
        # their internal digest but preserve their non-recomputed status.
        recomputed = _axis_from_members(
            identity_basis="caller_declared_model_axis",
            namespace=axis.namespace,
            member_ids=axis.members,
            model_revision=axis.model_revision or "",
            membership_provenance="consumer_asserted",
        )
    if _input_edge_keys(manifest.inputs) != _input_edge_keys(expected_inputs):
        raise EntityAxisRefusal("entity_axis_lineage_mismatch")
    if recomputed != axis:
        raise EntityAxisRefusal("entity_axis_source_recomputation_mismatch")
    return axis


def align_entity_values(
    *,
    axis: SelectedEntityAxis,
    member_ids: Sequence[EntityAxisMemberId],
    values: np.ndarray,
    dtype: str,
    unit_id: str,
) -> AlignedEntityVector:
    """Align a fully labelled one-dimensional vector to the canonical axis order.

    Duplicate, missing, or foreign IDs refuse. Missing-value masks and scalar
    broadcasting are deliberately outside this initial encoding profile.
    """
    if type(axis) is not SelectedEntityAxis:
        raise EntityAxisRefusal("entity_axis_type_invalid")
    if dtype not in {"float32", "float64"} or not unit_id or unit_id != unit_id.strip():
        raise EntityAxisRefusal("entity_axis_value_profile_invalid")
    raw = np.asarray(values)
    if raw.ndim != 1 or raw.shape != (axis.cardinality,):
        raise EntityAxisRefusal("entity_axis_value_shape_mismatch")
    if raw.dtype.name != dtype or not np.issubdtype(raw.dtype, np.floating):
        raise EntityAxisRefusal("entity_axis_value_dtype_mismatch")
    if not np.isfinite(raw).all():
        raise EntityAxisRefusal("entity_axis_missing_or_nonfinite_value")
    if len(member_ids) != axis.cardinality or any(
        type(member) is not EntityAxisMemberId for member in member_ids
    ):
        raise EntityAxisRefusal("entity_axis_input_members_invalid")
    input_keys = tuple(_member_sort_key(member) for member in member_ids)
    if len(set(input_keys)) != len(input_keys):
        raise EntityAxisRefusal("entity_axis_input_duplicate_member")
    expected_keys = tuple(_member_sort_key(member) for member in axis.members)
    input_index = {key: index for index, key in enumerate(input_keys)}
    if set(input_index) != set(expected_keys):
        raise EntityAxisRefusal("entity_axis_input_membership_mismatch")
    aligned = np.ascontiguousarray(raw[[input_index[key] for key in expected_keys]])
    input_order_sha256 = _digest_json([member.model_dump(mode="json") for member in member_ids])
    value_sha256 = _digest_array(raw)
    aligned_sha256 = _digest_array(aligned)
    alignment_sha256 = _digest_json(
        {
            "axis_sha256": axis.axis_sha256,
            "unit_id": unit_id,
            "dtype": dtype,
            "shape": [axis.cardinality],
            "aligned_value_sha256": aligned_sha256,
        }
    )
    identity = EntityAxisValueIdentity(
        axis_sha256=axis.axis_sha256,
        unit_id=unit_id,
        dtype=dtype,
        shape=(axis.cardinality,),
        input_order_sha256=input_order_sha256,
        value_sha256=value_sha256,
        aligned_value_sha256=aligned_sha256,
        alignment_sha256=alignment_sha256,
    )
    return AlignedEntityVector(
        _value_bytes=aligned.tobytes(order="C"),
        dtype=dtype,
        shape=(axis.cardinality,),
        identity=identity,
    )


def _axis_from_members(
    *,
    identity_basis: str,
    namespace: str,
    member_ids: Sequence[EntityAxisMemberId],
    source_view_ref: ArtifactRef | None = None,
    member_values_pointer: str | None = None,
    model_revision: str | None = None,
    membership_provenance: str,
) -> SelectedEntityAxis:
    if not namespace or namespace != namespace.strip() or not member_ids:
        raise EntityAxisRefusal("entity_axis_declaration_invalid")
    if any(type(member) is not EntityAxisMemberId for member in member_ids):
        raise EntityAxisRefusal("entity_axis_member_type_invalid")
    members = tuple(sorted(member_ids, key=_member_sort_key))
    member_keys = tuple(_member_sort_key(member) for member in members)
    if len(set(member_keys)) != len(member_keys):
        raise EntityAxisRefusal("entity_axis_duplicate_member")
    cardinality = len(members)
    membership_sha256 = _membership_digest(members)
    axis_sha256 = _axis_digest(
        identity_basis=identity_basis,
        namespace=namespace,
        source_view_ref=source_view_ref,
        model_revision=model_revision,
        member_values_pointer=member_values_pointer,
        membership_provenance=membership_provenance,
        model_selection_status="not_established",
        members=members,
        cardinality=cardinality,
    )
    try:
        return SelectedEntityAxis.model_validate(
            {
                "identity_basis": identity_basis,
                "namespace": namespace,
                "source_view_ref": source_view_ref,
                "model_revision": model_revision,
                "member_values_pointer": member_values_pointer,
                "membership_provenance": membership_provenance,
                "model_selection_status": "not_established",
                "members": members,
                "cardinality": cardinality,
                "membership_sha256": membership_sha256,
                "axis_sha256": axis_sha256,
            },
            strict=True,
        )
    except Exception as exc:
        raise EntityAxisRefusal("entity_axis_contract_invalid") from exc


def _member_from_json_value(value: object) -> EntityAxisMemberId:
    if type(value) is str and value:
        return EntityAxisMemberId(kind="string", value=value)
    if type(value) is int:
        return EntityAxisMemberId(kind="integer", value=value)
    raise EntityAxisRefusal("entity_axis_source_member_id_invalid")


def _json_pointer(payload: object, pointer: str) -> object:
    if not pointer.startswith("/") or pointer.endswith("/") or "//" in pointer:
        raise EntityAxisRefusal("entity_axis_pointer_invalid")
    current = payload
    for token in pointer[1:].split("/"):
        if any(
            token[index] == "~" and (index + 1 == len(token) or token[index + 1] not in "01")
            for index in range(len(token))
        ):
            raise EntityAxisRefusal("entity_axis_pointer_invalid")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise EntityAxisRefusal("entity_axis_pointer_missing")
            current = current[token]
        elif type(current) is list and token.isdecimal():
            index = int(token)
            if index >= len(current):
                raise EntityAxisRefusal("entity_axis_pointer_missing")
            current = current[index]
        else:
            raise EntityAxisRefusal("entity_axis_pointer_missing")
    return current


def _read_selected_view(
    store: EntityAxisStore,
    ref: ArtifactRef,
    *,
    limits: CoreJsonReadLimits,
) -> Any:
    try:
        selected = read_core_json_artifact_bounded(store, ref, limits=limits)
        if selected.effective_ref != ref or not selected.payload_integrity_verified:
            raise EntityAxisRefusal("entity_axis_source_view_identity_mismatch")
        if selected.profile_read is None:
            raise EntityAxisRefusal("entity_axis_source_view_profile_missing")
        return selected
    except EntityAxisRefusal:
        raise
    except CoreJsonReadBoundsRefusalError as exc:
        raise EntityAxisRefusal("entity_axis_source_view_bounds_refused") from exc
    except Exception as exc:
        raise EntityAxisRefusal("entity_axis_source_view_read_refused") from exc


def _persist_axis(
    *,
    store: EntityAxisStore,
    axis: SelectedEntityAxis,
    limits: CoreJsonReadLimits,
    governance: ArtifactGovernanceInfo | None,
    tenant_context: ArtifactTenantContextInfo | None,
    inputs: Sequence[InputRef],
) -> ArtifactRef:
    if len(axis.members) > limits.max_elements:
        raise EntityAxisRefusal("entity_axis_artifact_exceeds_element_limit")
    payload = axis.model_dump(mode="json", exclude_none=False)
    spec = CanonSpec(
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=False,
        max_depth=limits.max_depth,
    )
    encoded = to_canonical_bytes(payload, spec)
    if len(encoded) > limits.max_bytes:
        raise EntityAxisRefusal("entity_axis_artifact_exceeds_byte_limit")
    try:
        ref = store.put_bytes(
            encoded,
            PutOptions(
                kind=SelectedEntityAxis.ARTIFACT_KIND,
                media_type=SelectedEntityAxis.ARTIFACT_MEDIA_TYPE,
                schema=SelectedEntityAxis.ARTIFACT_SCHEMA,
                producer=ProducerInfo(
                    component=ENTITY_AXIS_PRODUCER,
                    version=ENTITY_AXIS_PRODUCER_VERSION,
                ),
                inputs=list(inputs),
                canon=CanonInfo.from_spec(spec),
                governance=governance,
                tenant_context=tenant_context,
            ),
            return_selected_profile=True,
        )
    except Exception as exc:
        raise EntityAxisRefusal("entity_axis_artifact_write_refused") from exc
    if type(ref) is not ArtifactRef or ref.manifest_profile_sha256 is None:
        raise EntityAxisRefusal("entity_axis_artifact_profile_missing")
    return ref


def _read_axis(
    store: EntityAxisStore,
    ref: ArtifactRef,
    *,
    limits: CoreJsonReadLimits,
) -> tuple[SelectedEntityAxis, ArtifactManifest]:
    try:
        selected = read_core_json_artifact_bounded(store, ref, limits=limits)
        manifest = selected.manifest
        if (
            selected.effective_ref != ref
            or manifest.kind != SelectedEntityAxis.ARTIFACT_KIND
            or manifest.media_type != SelectedEntityAxis.ARTIFACT_MEDIA_TYPE
            or manifest.artifact_schema != SelectedEntityAxis.ARTIFACT_SCHEMA
            or manifest.producer is None
            or manifest.producer.component != ENTITY_AXIS_PRODUCER
            or manifest.producer.version != ENTITY_AXIS_PRODUCER_VERSION
            or selected.profile_read is None
        ):
            raise EntityAxisRefusal("entity_axis_artifact_identity_mismatch")
        payload = require_declared_profile(selected.profile_read)
        if not isinstance(payload, dict):
            raise EntityAxisRefusal("entity_axis_artifact_payload_invalid")
        members = payload.get("members")
        if type(members) is not list:
            raise EntityAxisRefusal("entity_axis_artifact_payload_invalid")
        payload["members"] = tuple(members)
        axis = SelectedEntityAxis.model_validate(payload, strict=True)
        return axis, manifest
    except EntityAxisRefusal:
        raise
    except CoreJsonReadBoundsRefusalError as exc:
        raise EntityAxisRefusal("entity_axis_artifact_bounds_refused") from exc
    except Exception as exc:
        raise EntityAxisRefusal("entity_axis_artifact_read_refused") from exc


def _input_edge_keys(edges: Sequence[InputRef]) -> tuple[tuple[str, str, str | None], ...]:
    return tuple(
        sorted(
            (
                str(edge.artifact_id),
                edge.role,
                edge.manifest_profile_sha256,
            )
            for edge in edges
        )
    )


def _digest_json(value: object) -> str:
    return (
        _SHA256
        + hashlib.sha256(
            to_canonical_bytes(
                value,
                CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
            )
        ).hexdigest()
    )


def _digest_array(value: np.ndarray) -> str:
    payload = value.dtype.str.encode("ascii") + b"\0" + repr(value.shape).encode("ascii") + b"\0"
    payload += np.ascontiguousarray(value).tobytes(order="C")
    return _SHA256 + hashlib.sha256(payload).hexdigest()
