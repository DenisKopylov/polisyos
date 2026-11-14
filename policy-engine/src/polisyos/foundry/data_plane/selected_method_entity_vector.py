"""Reconcile selected method vectors against source-keyed entity axes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core.artifacts import (
    ArtifactRef,
    CoreJsonReadLimits,
    artifact_ref_identity_key,
    read_core_json_artifact_bounded,
)
from polisyos.core.contracts import (
    EntityAxisMemberId,
    EntityAxisValueIdentity,
    ModelInputPort,
    SelectedEntityAxis,
    SelectedEntityVectorSourceDescriptor,
)
from polisyos.foundry.data_plane.entity_axis import (
    AlignedEntityVector,
    EntityAxisRefusal,
    EntityAxisStore,
    align_entity_values,
    reconcile_entity_axis,
)
from polisyos.foundry.data_plane.selected_tensors import (
    encode_selected_tensor,
    selected_tensor_value_sha256,
)


def reconcile_selected_method_entity_vector(
    store: EntityAxisStore,
    *,
    port: ModelInputPort,
    binding_port_id: str,
    binding_slot_id: str,
    source: SelectedEntityVectorSourceDescriptor,
    axis_ref: ArtifactRef,
    expected_alignment: EntityAxisValueIdentity,
    selected_value: np.ndarray,
    selected_value_sha256: str,
    limits: CoreJsonReadLimits,
) -> AlignedEntityVector:
    """Recompute source membership and alignment before admitting an ABI vector.

    The caller must supply the exact selected model port and the value loaded
    from its selected NPY artifact. This helper reopens both the axis and the
    selected JSON source view, reconstructs IDs and numeric values, performs
    the declared physical encoding, aligns by typed ID, and checks both the
    full alignment identity and the actual NPY argument bytes. It makes no
    claim that the source view is representative or semantically authoritative.
    """
    if (
        type(port) is not ModelInputPort
        or port.carrier != "method_input"
        or port.entity_axis_ref is None
        or artifact_ref_identity_key(port.entity_axis_ref) != artifact_ref_identity_key(axis_ref)
        or binding_port_id != port.port_id
        or binding_slot_id != port.slot_id
        or port.physical_encoding is None
        or len(port.physical_encoding.shape) != 1
        or type(source) is not SelectedEntityVectorSourceDescriptor
        or type(expected_alignment) is not EntityAxisValueIdentity
        or type(limits) is not CoreJsonReadLimits
    ):
        raise EntityAxisRefusal("method_entity_vector_selected_binding_mismatch")

    axis = reconcile_entity_axis(store=store, axis_ref=axis_ref, limits=limits)
    if (
        axis.identity_basis != "selected_source_view"
        or axis.source_view_ref is None
        or artifact_ref_identity_key(axis.source_view_ref)
        != artifact_ref_identity_key(source.source_view_ref)
        or axis.member_values_pointer != source.member_ids_pointer
        or port.physical_encoding.shape != (axis.cardinality,)
        or expected_alignment.axis_sha256 != axis.axis_sha256
        or expected_alignment.unit_id != port.unit_id
        or expected_alignment.dtype != port.physical_encoding.dtype
        or expected_alignment.shape != port.physical_encoding.shape
    ):
        raise EntityAxisRefusal("method_entity_vector_axis_or_port_mismatch")

    source_read = read_core_json_artifact_bounded(store, source.source_view_ref, limits=limits)
    payload = require_declared_profile(source_read.profile_read)
    member_values = _json_pointer(payload, source.member_ids_pointer)
    numeric_values = _json_pointer(payload, source.values_pointer)
    if (
        type(member_values) is not list
        or type(numeric_values) is not list
        or len(member_values) != axis.cardinality
        or len(numeric_values) != axis.cardinality
        or axis.cardinality > limits.max_elements
    ):
        raise EntityAxisRefusal("method_entity_vector_source_cardinality_mismatch")
    member_ids = tuple(_member_id(value) for value in member_values)
    if any(type(value) not in {int, float} for value in numeric_values):
        raise EntityAxisRefusal("method_entity_vector_source_value_invalid")

    encoding = port.physical_encoding
    try:
        raw_values = encode_selected_tensor(
            numeric_values,
            shape=encoding.shape,
            dtype=encoding.dtype,
            max_absolute_error=encoding.max_absolute_error,
        )
        aligned = align_entity_values(
            axis=axis,
            member_ids=member_ids,
            values=raw_values,
            dtype=encoding.dtype,
            unit_id=port.unit_id,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise EntityAxisRefusal("method_entity_vector_source_alignment_refused") from exc

    if aligned.identity != expected_alignment:
        raise EntityAxisRefusal("method_entity_vector_alignment_identity_mismatch")
    actual = np.asarray(selected_value)
    if (
        actual.dtype != np.dtype(encoding.dtype)
        or actual.shape != encoding.shape
        or not actual.flags.c_contiguous
    ):
        raise EntityAxisRefusal("method_entity_vector_argument_shape_or_dtype_mismatch")
    try:
        actual_bytes = actual.tobytes(order="C")
        actual_digest = selected_tensor_value_sha256(actual.dtype, actual.shape, actual_bytes)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EntityAxisRefusal("method_entity_vector_argument_identity_invalid") from exc
    if actual_digest != selected_value_sha256 or actual_bytes != aligned.values.tobytes(order="C"):
        raise EntityAxisRefusal("method_entity_vector_argument_alignment_mismatch")
    return aligned


def _member_id(value: object) -> EntityAxisMemberId:
    if type(value) is str and value:
        return EntityAxisMemberId(kind="string", value=value)
    if type(value) is int:
        return EntityAxisMemberId(kind="integer", value=value)
    raise EntityAxisRefusal("method_entity_vector_member_id_invalid")


def _json_pointer(payload: object, pointer: str) -> object:
    if not pointer.startswith("/") or pointer.endswith("/") or "//" in pointer:
        raise EntityAxisRefusal("method_entity_vector_pointer_invalid")
    current: Any = payload
    for raw_token in pointer[1:].split("/"):
        if any(
            raw_token[index] == "~"
            and (index + 1 == len(raw_token) or raw_token[index + 1] not in "01")
            for index in range(len(raw_token))
        ):
            raise EntityAxisRefusal("method_entity_vector_pointer_invalid")
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise EntityAxisRefusal("method_entity_vector_pointer_missing")
            current = current[token]
        elif type(current) is list and token.isdecimal():
            index = int(token)
            if index >= len(current):
                raise EntityAxisRefusal("method_entity_vector_pointer_missing")
            current = current[index]
        else:
            raise EntityAxisRefusal("method_entity_vector_pointer_missing")
    return current
