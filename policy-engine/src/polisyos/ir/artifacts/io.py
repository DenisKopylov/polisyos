"""High-level helpers for persisting and loading JSON artifacts through the IR CAS boundary."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, NoReturn, Protocol, cast
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ValidationError

from polisyos.common.canonical import _admit_canon_spec
from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    _manifest_profile_sha256,
    _normalize_canonical_profile_mapping,
    decode_profiled_canonical_bytes,
    parse_canonical_profile,
)
from polisyos.ir.model_layer.canon import (
    IR_TAG_POLICY_ID,
    IR_V3_TAG_POLICY_ID,
    CanonSpec,
    CanonViolation,
    from_canonical_bytes,
    to_canonical_bytes,
)

if TYPE_CHECKING:
    from polisyos.ir.migrations.base import ResolvedSchemaAdmission

from ._lineage import InputRefLike  # noqa: TC001  # noqa: TC001
from .contracts import (
    ArtifactID,
    ArtifactOwnerDeclaration,
    ArtifactSelector,
    ArtifactStore,
    CanonInfo,
    InputRef,
    OwnedArtifactRead,
    OwnedWriteOptionsPreparer,
    PutOptions,
    SchemaInfo,
    StorePutOptions,
    _is_string_root_model,
    _normalize_scalar_artifact_id,
    normalize_artifact_ref,
    normalize_input_refs,
    to_store_put_options,
)


def _duplicate_key_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one raw JSON object and reject ambiguous duplicate fields."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    """Reject non-JSON numeric constants in a persisted sidecar."""
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _normalize_canon_spec(canon_spec: CanonSpec | None) -> CanonSpec:
    """Treat only None as absence and reject malformed canonicalization options."""
    if canon_spec is None:
        return CanonSpec()
    if not any(base is CanonSpec for base in type.__getattribute__(type(canon_spec), "__mro__")):
        raise CanonViolation("ir_artifact_canon_spec_invalid")
    canon_spec = _admit_canon_spec(
        canon_spec, CanonSpec, violation_type=CanonViolation, artifact_writer=True
    )
    try:
        CanonInfo.from_spec(canon_spec)
    except Exception as exc:
        raise CanonViolation("ir_artifact_canon_spec_invalid") from exc
    return canon_spec


def _normalize_lineage_inputs(inputs: Sequence[InputRefLike] | None) -> list[InputRef]:
    """Use the shared contract normalizer and preserve typed refusal at the CAS boundary."""
    try:
        return normalize_input_refs(inputs)
    except CanonViolation:
        raise
    except Exception as exc:
        raise CanonViolation("ir_artifact_inputs_invalid") from exc


def _is_canonical_json_root(value: object) -> bool:
    """Recognize root values the IR JSON codec can represent without DTO projection."""
    if isinstance(value, Mapping):
        return True
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, memoryview)):
        return True
    return value is None or isinstance(
        value,
        (bool, int, float, str, bytes, bytearray, memoryview, date, datetime, Decimal),
    )


def _owner_source_type_tag(value_type: type[object]) -> dict[str, str]:
    """Identify a concrete runtime type without invoking instance equality or dumping."""
    try:
        module = type.__getattribute__(value_type, "__module__")
        qualname = type.__getattribute__(value_type, "__qualname__")
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_projection_source_type_invalid") from exc
    if type(module) is not str or type(qualname) is not str:
        raise CanonViolation("ir_owned_artifact_projection_source_type_invalid")
    return {
        "module": module,
        "qualname": qualname,
        "identity": str(id(value_type)),
    }


def _owner_source_semantic_snapshot(
    value: object,
    active: set[int] | None = None,
) -> object:
    """Build a closed structural snapshot of the data a typed projection receives.

    Pydantic state is read from its stored fields, extras, field-set, and private
    state directly; the model-dump path and object equality are deliberately not used.
    Containers and NumPy values retain concrete type and typed structure so a
    callback cannot hide a mutation behind custom equality or excluded fields.
    Unknown runtime values fail closed.
    """
    if active is None:
        active = set()

    value_type = type(value)
    type_tag = _owner_source_type_tag(value_type)

    if isinstance(value, Enum):
        try:
            name = object.__getattribute__(value, "_name_")
            enum_value = object.__getattribute__(value, "_value_")
        except Exception as exc:
            raise CanonViolation("ir_owned_artifact_projection_source_enum_invalid") from exc
        if type(name) is not str:
            raise CanonViolation("ir_owned_artifact_projection_source_enum_invalid")
        return {
            "kind": "enum",
            "type": type_tag,
            "name": name,
            "value": _owner_source_semantic_snapshot(enum_value, active),
        }

    if value is None or value_type in (
        bool,
        int,
        float,
        str,
        bytes,
        bytearray,
        memoryview,
        date,
        datetime,
        Decimal,
    ):
        try:
            canonical = to_canonical_bytes(
                value,
                CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
            )
        except Exception as exc:
            raise CanonViolation("ir_owned_artifact_projection_source_scalar_invalid") from exc
        return {
            "kind": "canonical_scalar",
            "type": type_tag,
            "canonical_hex": canonical.hex(),
        }

    if value_type is UUID:
        return {"kind": "uuid", "type": type_tag, "hex": value.hex}

    object_id = id(value)
    if object_id in active:
        raise CanonViolation("ir_owned_artifact_projection_source_cycle")
    active.add(object_id)
    try:
        if isinstance(value, np.ndarray):
            if value_type is not np.ndarray:
                raise CanonViolation("ir_owned_artifact_projection_source_array_invalid")
            try:
                dtype = value.dtype
                if dtype.hasobject or dtype.metadata is not None:
                    raise CanonViolation(
                        "ir_owned_artifact_projection_source_array_unsupported_dtype"
                    )
                dtype_description = dtype.descr if dtype.fields is not None else dtype.str
                raw = value.tobytes(order="C")
                shape = [int(item) for item in value.shape]
                strides = [int(item) for item in value.strides]
                flags = {
                    "c_contiguous": bool(value.flags.c_contiguous),
                    "f_contiguous": bool(value.flags.f_contiguous),
                    "writeable": bool(value.flags.writeable),
                }
            except CanonViolation:
                raise
            except Exception as exc:
                raise CanonViolation("ir_owned_artifact_projection_source_array_invalid") from exc
            return {
                "kind": "numpy_array",
                "type": type_tag,
                "dtype": _owner_source_semantic_snapshot(dtype_description, active),
                "itemsize": int(dtype.itemsize),
                "shape": shape,
                "strides": strides,
                "flags": flags,
                "content_length": len(raw),
                "content_sha256": hashlib.sha256(raw).hexdigest(),
            }

        if isinstance(value, np.generic):
            try:
                dtype = value.dtype
                if dtype.hasobject or dtype.metadata is not None:
                    raise CanonViolation(
                        "ir_owned_artifact_projection_source_scalar_unsupported_dtype"
                    )
                raw = value.tobytes()
            except CanonViolation:
                raise
            except Exception as exc:
                raise CanonViolation("ir_owned_artifact_projection_source_scalar_invalid") from exc
            return {
                "kind": "numpy_scalar",
                "type": type_tag,
                "dtype": dtype.str,
                "content_length": len(raw),
                "content_sha256": hashlib.sha256(raw).hexdigest(),
            }

        if isinstance(value, BaseModel):
            try:
                stored = object.__getattribute__(value, "__dict__")
                declared = type.__getattribute__(value_type, "model_fields")
                extra = object.__getattribute__(value, "__pydantic_extra__")
                private = object.__getattribute__(value, "__pydantic_private__")
                field_set = object.__getattribute__(value, "__pydantic_fields_set__")
            except Exception as exc:
                raise CanonViolation("ir_owned_artifact_projection_source_model_invalid") from exc
            if type(stored) is not dict or type(declared) is not dict:
                raise CanonViolation("ir_owned_artifact_projection_source_model_invalid")
            declared_names = tuple(sorted(declared))
            stored_names = tuple(sorted(stored))
            if any(type(name) is not str for name in (*declared_names, *stored_names)):
                raise CanonViolation("ir_owned_artifact_projection_source_model_invalid")
            if type(field_set) not in (set, frozenset) or any(
                type(name) is not str for name in field_set
            ):
                raise CanonViolation("ir_owned_artifact_projection_source_model_invalid")
            return {
                "kind": "pydantic_model",
                "type": type_tag,
                "declared_fields": list(declared_names),
                "stored_fields": list(stored_names),
                "field_values": {
                    name: _owner_source_semantic_snapshot(stored[name], active)
                    for name in stored_names
                },
                "fields_set": sorted(field_set),
                "extra": _owner_source_semantic_snapshot(extra, active),
                "private": _owner_source_semantic_snapshot(private, active),
            }

        if isinstance(value, dict):
            mro = type.__getattribute__(value_type, "__mro__")
            if dict not in mro:
                raise CanonViolation("ir_owned_artifact_projection_source_mapping_invalid")
            for cls in mro[: mro.index(dict)]:
                namespace = type.__getattribute__(cls, "__dict__")
                if namespace.get("__slots__") != ():
                    raise CanonViolation("ir_owned_artifact_projection_source_mapping_invalid")
            pairs = tuple(dict.items(value))
            ordered_pairs: list[tuple[bytes, bytes, object, object]] = []
            snapshot_spec = CanonSpec(
                forbid_floats=False,
                forbid_nan_inf=False,
                exclude_none=False,
            )
            for key, item in pairs:
                key_snapshot = _owner_source_semantic_snapshot(key, active)
                item_snapshot = _owner_source_semantic_snapshot(item, active)
                try:
                    key_bytes = to_canonical_bytes(key_snapshot, snapshot_spec)
                    item_bytes = to_canonical_bytes(item_snapshot, snapshot_spec)
                except Exception as exc:
                    raise CanonViolation(
                        "ir_owned_artifact_projection_source_mapping_invalid"
                    ) from exc
                ordered_pairs.append((key_bytes, item_bytes, key_snapshot, item_snapshot))
            ordered_pairs.sort(key=lambda pair: (pair[0], pair[1]))
            return {
                "kind": "mapping",
                "type": type_tag,
                "items": [
                    {"key": key_snapshot, "value": item_snapshot}
                    for _key_bytes, _item_bytes, key_snapshot, item_snapshot in ordered_pairs
                ],
            }

        mro = type.__getattribute__(value_type, "__mro__")
        list_index = mro.index(list) if list in mro else None
        tuple_index = mro.index(tuple) if tuple in mro else None
        if list_index is not None or tuple_index is not None:
            builtin_sequence = list if list_index is not None else tuple
            builtin_index = list_index if list_index is not None else tuple_index
            for cls in mro[:builtin_index]:
                namespace = type.__getattribute__(cls, "__dict__")
                if namespace.get("__slots__") != ():
                    raise CanonViolation("ir_owned_artifact_projection_source_sequence_invalid")
            items = tuple(builtin_sequence.__iter__(value))
            return {
                "kind": "sequence",
                "type": type_tag,
                "items": [_owner_source_semantic_snapshot(item, active) for item in items],
            }

        if value_type in (set, frozenset):
            item_bytes = [
                to_canonical_bytes(
                    _owner_source_semantic_snapshot(item, active),
                    CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
                )
                for item in value
            ]
            return {
                "kind": "set",
                "type": type_tag,
                "items_hex": sorted(item.hex() for item in item_bytes),
            }

        if is_dataclass(value) and not isinstance(value, type):
            try:
                dataclass_values = {
                    field.name: _owner_source_semantic_snapshot(
                        object.__getattribute__(value, field.name),
                        active,
                    )
                    for field in fields(value)
                }
            except Exception as exc:
                raise CanonViolation(
                    "ir_owned_artifact_projection_source_dataclass_invalid"
                ) from exc
            return {
                "kind": "dataclass",
                "type": type_tag,
                "fields": dataclass_values,
            }

        raise CanonViolation("ir_owned_artifact_projection_source_unsupported")
    finally:
        active.remove(object_id)


def _owner_source_semantic_bytes(value: object) -> bytes:
    """Canonicalize a typed structural snapshot without custom equality callbacks."""
    snapshot = _owner_source_semantic_snapshot(value)
    try:
        return to_canonical_bytes(
            snapshot,
            CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
        )
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_projection_source_invalid") from exc


class _ProfiledJSONReader(Protocol):
    """Minimal raw selected-view reader required by semantic JSON intake."""

    def get_bytes(self, artifact_id: ArtifactSelector) -> bytes: ...

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes: ...


def _validate_return_selected_profile_flag(value: object) -> bool:
    """Require the public selected-profile request to be an exact boolean before writing."""
    if type(value) is not bool:
        raise TypeError("return_selected_profile must be a bool")
    return value


def put_json_artifact(
    store: ArtifactStore,
    payload: object,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: Sequence[InputRefLike] | None = None,
    canon_spec: CanonSpec | None = None,
    return_selected_profile: bool = False,
) -> dict[str, str]:
    """Persist JSON and optionally return the exact profile selected by this write.

    Stores without this write-result capability refuse the request. This helper never
    synthesizes a producer profile from a later default-manifest read.
    """
    return_selected_profile = _validate_return_selected_profile_flag(return_selected_profile)
    canon_spec = _normalize_canon_spec(canon_spec)
    normalized_inputs = _normalize_lineage_inputs(inputs)
    options = PutOptions(
        kind=kind,
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version=schema_version),
        inputs=normalized_inputs,
        canon=CanonInfo.from_spec(canon_spec),
    )
    put_json = store.put_json
    if return_selected_profile:
        try:
            signature = inspect.signature(put_json)
        except (TypeError, ValueError) as exc:
            raise NotImplementedError("artifact_store_return_selected_profile_unsupported") from exc
        parameter = signature.parameters.get("return_selected_profile")
        if parameter is None or parameter.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise NotImplementedError("artifact_store_return_selected_profile_unsupported")
        ref = put_json(
            payload,
            opts=to_store_put_options(options),
            canon_spec=canon_spec,
            return_selected_profile=True,
        )
    else:
        ref = put_json(
            payload,
            opts=to_store_put_options(options),
            canon_spec=canon_spec,
        )
    normalized = normalize_artifact_ref(ref)
    if return_selected_profile and not normalized.get("manifest_profile_sha256"):
        raise ValueError("artifact_write_selected_profile_missing")
    return normalized


def _validated_ir_canon_info(value: object) -> CanonInfo:
    """Validate a complete profile mapping parsed from the raw persisted sidecar."""
    if not isinstance(value, Mapping):
        raise CanonViolation("unsupported_ir_canon_profile")
    payload = dict(value)
    if set(CanonInfo.model_fields) - set(payload):
        raise CanonViolation("unsupported_ir_canon_profile")
    payload = _normalize_canonical_profile_mapping(payload)
    try:
        profile = CanonInfo.model_validate(payload, strict=True)
    except (TypeError, ValueError) as exc:
        raise CanonViolation("unsupported_ir_canon_profile") from exc

    supported = CanonInfo()
    if (
        profile.name != supported.name
        or profile.version not in (supported.version, "0.3.0")
        or profile.max_depth < 0
    ):
        raise CanonViolation("unsupported_ir_canon_profile")
    return profile


def _make_ir_canon_spec(profile: object) -> CanonSpec:
    """Build IR's typed encoder spec from the selected, validated IR profile."""
    if not isinstance(profile, CanonInfo):
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    return CanonSpec(
        name=profile.name,
        version=profile.version,
        forbid_floats=profile.forbid_floats,
        forbid_nan_inf=profile.forbid_nan_inf,
        exclude_none=profile.exclude_none,
        max_depth=profile.max_depth,
        sort_keys=profile.sort_keys,
        separators=profile.separators,
        ensure_ascii=profile.ensure_ascii,
    )


def _encode_ir_profiled_value(value: object, spec: object) -> bytes:
    """Encode with IR's public codec after checking the shared callback result type."""
    if not isinstance(spec, CanonSpec):
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    return to_canonical_bytes(value, spec)


def _require_owner_callback_codec(profile: CanonInfo | CanonSpec) -> None:
    """Keep owned callbacks on their qualified decoder until their cohort migrates.

    Generic selected readers support .3, but the owned callback snapshot path
    below still uses the historical unqualified .2 decoder. An owner callback's
    approval or a registry row cannot qualify a different decoder for it.
    """
    if profile.name == "polisyos.canon.json" and profile.version != "0.2.0":
        raise CanonViolation("ir_owned_artifact_callback_codec_unavailable")


def _decode_owner_callback_payload(
    raw_payload_bytes: bytes,
    spec: CanonSpec,
    *,
    refusal_code: str,
) -> object:
    """Decode a private, callback-local JSON root from the immutable owned payload bytes."""
    _require_owner_callback_codec(spec)
    try:
        return from_canonical_bytes(raw_payload_bytes, max_depth=spec.max_depth)
    except Exception as exc:
        raise CanonViolation(refusal_code) from exc


def _assert_owner_callback_payload_unchanged(
    payload: object,
    raw_payload_bytes: bytes,
    spec: CanonSpec,
    *,
    refusal_code: str,
) -> None:
    """Refuse a callback that mutates its private payload input before returning."""
    try:
        callback_bytes = to_canonical_bytes(payload, spec)
    except Exception as exc:
        raise CanonViolation(refusal_code) from exc
    if callback_bytes != raw_payload_bytes:
        raise CanonViolation(refusal_code)


def _owner_payload_version_from_snapshot[OwnerSourceT, OwnerConsumerT](
    declaration: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    raw_payload_bytes: bytes,
    spec: CanonSpec,
) -> str | None:
    """Read a payload discriminator from a private decode and reject callback mutation."""
    payload = _decode_owner_callback_payload(
        raw_payload_bytes,
        spec,
        refusal_code="ir_owned_artifact_payload_version_invalid",
    )
    try:
        payload_version = declaration.payload_version_of(payload)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_payload_version_invalid") from exc
    _assert_owner_callback_payload_unchanged(
        payload,
        raw_payload_bytes,
        spec,
        refusal_code="ir_owned_artifact_payload_version_input_mutated",
    )
    return payload_version


def _owner_source_from_snapshot[OwnerSourceT, OwnerConsumerT](
    declaration: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    raw_payload_bytes: bytes,
    spec: CanonSpec,
    admission: ResolvedSchemaAdmission,
) -> OwnerSourceT:
    """Validate a private payload decode and refuse a mutating owner validator."""
    payload = _decode_owner_callback_payload(
        raw_payload_bytes,
        spec,
        refusal_code="ir_owned_artifact_payload_invalid",
    )
    try:
        source = declaration.validate_source(payload, admission)
    except CanonViolation:
        raise
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_source_invalid") from exc
    _assert_owner_callback_payload_unchanged(
        payload,
        raw_payload_bytes,
        spec,
        refusal_code="ir_owned_artifact_source_input_mutated",
    )
    try:
        return deepcopy(source)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_source_invalid") from exc


def _project_owner_source[OwnerSourceT, OwnerConsumerT](
    declaration: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    source: OwnerSourceT,
    admission: ResolvedSchemaAdmission,
) -> OwnerConsumerT:
    """Project a private source copy and reject mutation of the callback input."""
    try:
        expected_source = deepcopy(source)
        callback_source = deepcopy(source)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_projection_refused") from exc
    if type(callback_source) is not type(expected_source):
        raise CanonViolation("ir_owned_artifact_projection_refused")
    try:
        expected_snapshot = _owner_source_semantic_bytes(expected_source)
    except CanonViolation as exc:
        raise CanonViolation("ir_owned_artifact_projection_refused") from exc
    try:
        consumer_value = declaration.project_for_consumer(callback_source, admission)
    except CanonViolation:
        raise
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_projection_refused") from exc
    try:
        callback_snapshot = _owner_source_semantic_bytes(callback_source)
    except CanonViolation as exc:
        raise CanonViolation("ir_owned_artifact_projection_refused") from exc
    if callback_snapshot != expected_snapshot:
        raise CanonViolation("ir_owned_artifact_projection_input_mutated")
    return consumer_value


def _artifact_selector(value: ArtifactSelector) -> ArtifactSelector:
    """Validate an artifact ID or typed selected-view ref without dropping its selector."""
    if isinstance(value, (ArtifactID, str)) or _is_string_root_model(value):
        try:
            return _normalize_scalar_artifact_id(value)
        except (TypeError, ValueError) as exc:
            raise CanonViolation("ir_artifact_view_selector_invalid") from exc
    try:
        return normalize_artifact_ref(value)
    except (TypeError, ValueError) as exc:
        raise CanonViolation("ir_artifact_view_selector_invalid") from exc


def _read_json_artifact_with_bytes(
    store: _ProfiledJSONReader,
    artifact_id: ArtifactSelector,
    *,
    before_payload: Callable[[Mapping[str, Any], CanonInfo, ArtifactSelector], None] | None = None,
) -> tuple[Any, bytes]:
    """Read JSON after raw profile completeness and byte conformance checks.

    The stored profile is a declaration used to select the IR decoder and encoder
    settings. A successful round-trip proves those settings reproduce the stored
    bytes; it does not identify or attest the producer.
    """
    selector = _artifact_selector(artifact_id)
    get_manifest_bytes = getattr(store, "get_manifest_bytes", None)
    if not callable(get_manifest_bytes):
        raise CanonViolation("ir_artifact_raw_manifest_unavailable")
    try:
        raw_manifest_bytes = get_manifest_bytes(selector)
    except ValidationError as exc:
        raise CanonViolation("unsupported_ir_canon_profile") from exc
    try:
        declaration = parse_canonical_profile(
            raw_manifest_bytes,
            profile_model=CanonInfo,
            allow_profile_absent=False,
            supported_versions=("0.2.0", "0.3.0"),
        )
    except CanonicalProfileRefusalError as exc:
        code = {
            "canon_profile_raw_manifest_invalid": "ir_artifact_raw_manifest_invalid",
        }.get(exc.code, "unsupported_ir_canon_profile")
        raise CanonViolation(code) from exc
    try:
        raw_manifest = json.loads(
            raw_manifest_bytes,
            object_pairs_hook=_duplicate_key_rejector,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise CanonViolation("ir_artifact_raw_manifest_invalid") from exc
    if not isinstance(raw_manifest, Mapping):
        raise CanonViolation("ir_artifact_raw_manifest_invalid")
    profile = declaration.profile
    if not isinstance(profile, CanonInfo):
        raise CanonViolation("unsupported_ir_canon_profile")
    profile = _validated_ir_canon_info(profile.model_dump(mode="python"))
    selected_id = selector.get("artifact_id") if isinstance(selector, Mapping) else selector
    manifest_id = raw_manifest.get("artifact_id")
    if manifest_id is None or str(manifest_id) != str(selected_id):
        raise CanonViolation("ir_artifact_selected_manifest_mismatch")
    selected_profile = (
        selector.get("manifest_profile_sha256") if isinstance(selector, Mapping) else None
    )
    if isinstance(selector, Mapping):
        for field in ("kind", "media_type"):
            expected = selector.get(field)
            if expected is not None and str(expected) != str(raw_manifest.get(field)):
                raise CanonViolation("ir_artifact_selected_manifest_mismatch")
    manifest_reader = getattr(store, "get_manifest", None)
    manifest = None
    if callable(manifest_reader):
        manifest = manifest_reader(selector)
        typed_dump = getattr(manifest, "model_dump", None)
        if callable(typed_dump):
            typed_manifest = typed_dump(mode="json", by_alias=True, exclude_none=True)
        elif isinstance(manifest, Mapping):
            typed_manifest = dict(manifest)
        else:
            raise CanonViolation("ir_artifact_selected_manifest_invalid")
        if dict(raw_manifest) != typed_manifest:
            raise CanonViolation("ir_artifact_selected_manifest_changed")
        typed_id = (
            manifest.get("artifact_id")
            if isinstance(manifest, Mapping)
            else getattr(manifest, "artifact_id", None)
        )
        if typed_id is None or str(typed_id) != str(selected_id):
            raise CanonViolation("ir_artifact_selected_manifest_mismatch")
        typed_canon = (
            manifest.get("canon")
            if isinstance(manifest, Mapping)
            else getattr(manifest, "canon", None)
        )
        typed_canon_dump = getattr(typed_canon, "model_dump", None)
        if callable(typed_canon_dump):
            typed_canon = typed_canon_dump(mode="python")
        if _validated_ir_canon_info(typed_canon) != profile:
            raise CanonViolation("ir_artifact_selected_profile_mismatch")
        if selected_profile is not None:
            try:
                actual_profile = _manifest_profile_sha256(typed_manifest)
            except CanonicalProfileRefusalError as exc:
                raise CanonViolation("ir_artifact_selected_manifest_invalid") from exc
            except (TypeError, ValueError) as exc:
                raise CanonViolation("ir_artifact_selected_manifest_invalid") from exc
            if actual_profile != selected_profile:
                raise CanonViolation("ir_artifact_selected_profile_mismatch")
    elif selected_profile is not None:
        # A raw-only reader can prove ID-selected bytes, but cannot resolve a
        # profile-bearing view without an exact typed selector capability.
        raise CanonViolation("ir_artifact_selected_manifest_unavailable")
    if before_payload is not None:
        before_payload(raw_manifest, profile, selector)
    raw_bytes = store.get_bytes(selector)
    if not isinstance(raw_bytes, bytes):
        raise CanonViolation("ir_artifact_payload_bytes_invalid")
    expected_hex = str(selected_id).removeprefix("sha256:")
    if hashlib.sha256(raw_bytes).hexdigest() != expected_hex:
        raise CanonViolation("ir_artifact_payload_identity_mismatch")
    try:
        version = profile.version
        result = decode_profiled_canonical_bytes(
            raw_bytes,
            declaration,
            profile_model=CanonInfo,
            make_spec=_make_ir_canon_spec,
            decode=lambda raw, max_depth: from_canonical_bytes(
                raw, max_depth=max_depth, version=version
            ),
            encode=_encode_ir_profiled_value,
            reader_policy_id=(IR_V3_TAG_POLICY_ID if version == "0.3.0" else IR_TAG_POLICY_ID),
        )
    except CanonicalProfileRefusalError as exc:
        code = {
            "canon_profile_raw_manifest_invalid": "ir_artifact_raw_manifest_invalid",
            "canon_profile_payload_bytes_invalid": "ir_artifact_payload_bytes_invalid",
            "canon_profile_payload_nonconformant": (
                "ir_artifact_bytes_do_not_conform_to_persisted_canon_profile"
            ),
        }.get(exc.code, "unsupported_ir_canon_profile")
        cause = exc.__cause__
        if (
            exc.code == "canon_profile_payload_nonconformant"
            and isinstance(cause, CanonViolation)
            and str(cause).startswith("Unknown canonical _type")
        ):
            code = str(cause)
        raise CanonViolation(code) from exc
    return result.value, raw_bytes


_OWNER_UNSET = object()
_WIRE_POLICY_FIELD = "wire_policy_ref"
_WIRE_POLICY_REVISION_FIELD = "wire_policy_revision"


def _require_owner_declaration[OwnerSourceT, OwnerConsumerT](
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
) -> ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT]:
    """Require the exact trusted owner declaration type before store access."""
    if type(owner) is not ArtifactOwnerDeclaration:
        raise CanonViolation("ir_owned_artifact_owner_declaration_invalid")
    return owner


def _owner_wire_policy(registration: object) -> tuple[str, str] | None:
    """Read a registered row's exact code-owned wire-law identity."""
    ref = getattr(registration, _WIRE_POLICY_FIELD, None)
    revision = getattr(registration, _WIRE_POLICY_REVISION_FIELD, None)
    if type(ref) is not str or not ref or type(revision) is not str or not revision:
        return None
    return ref, revision


def _owner_registration_matches[OwnerSourceT, OwnerConsumerT](
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    registration: object,
) -> bool:
    """Bind one immutable registry row to the trusted owner and adapter ABI."""
    return (
        getattr(registration, "registry_key", None) == owner.registry_key
        and getattr(registration, "owner_ref", None) == owner.contract_id
        and getattr(registration, "dto_abi", None) == owner.dto_fqn
        and _owner_wire_policy(registration) in owner.accepted_wire_policies
    )


def _manifest_owner_identity(
    raw_manifest: Mapping[str, Any],
) -> tuple[str, str, str, str]:
    """Extract exact JSON artifact kind, media type, and manifest schema identity."""
    kind = raw_manifest.get("kind")
    media_type = raw_manifest.get("media_type")
    schema = raw_manifest.get("schema")
    if (
        type(kind) is not str
        or not kind
        or type(media_type) is not str
        or not media_type
        or not isinstance(schema, Mapping)
        or set(schema) != {"name", "version"}
    ):
        raise CanonViolation("ir_owned_artifact_manifest_identity_invalid")
    schema_name = schema.get("name")
    schema_version = schema.get("version")
    if (
        type(schema_name) is not str
        or not schema_name.strip()
        or type(schema_version) is not str
        or not schema_version.strip()
    ):
        raise CanonViolation("ir_owned_artifact_manifest_identity_invalid")
    return kind, media_type, schema_name, schema_version


def _checked_owner_profile[OwnerSourceT, OwnerConsumerT](
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    profile: CanonInfo,
    registration: object,
) -> bool:
    """Require the trusted owner callback to accept the exact selected profile and row."""
    _require_owner_callback_codec(profile)
    try:
        accepted = owner.validate_profile(profile, registration)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_profile_refused") from exc
    if type(accepted) is not bool:
        raise CanonViolation("ir_owned_artifact_profile_refused")
    return accepted


def _get_owned_json_artifact_with_bytes[OwnerSourceT, OwnerConsumerT](
    store: _ProfiledJSONReader,
    artifact_id: ArtifactSelector,
    *,
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
) -> OwnedArtifactRead[OwnerConsumerT]:
    """Read, hash, validate, and project JSON through one frozen owner admission."""
    declaration = _require_owner_declaration(owner)
    if declaration.media_type != "application/json":
        raise CanonViolation("ir_owned_artifact_media_type_unsupported")

    from polisyos.ir.migrations.base import (
        find_owned_representation,
        get_ir_owner_registry_snapshot,
        resolve_owned_representation,
    )

    try:
        snapshot = get_ir_owner_registry_snapshot()
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_registry_unavailable") from exc
    preflight: dict[str, Any] = {}

    def preflight_before_payload(
        raw_manifest: Mapping[str, Any],
        profile: CanonInfo,
        _selector: ArtifactSelector,
    ) -> None:
        """Reject wrong owner metadata/profile before asking for payload bytes."""
        kind, media_type, schema_name, schema_version = _manifest_owner_identity(raw_manifest)
        if kind != declaration.kind or media_type != declaration.media_type:
            raise CanonViolation("ir_owned_artifact_manifest_identity_mismatch")
        try:
            found = find_owned_representation(
                snapshot,
                declaration.registry_key,
                owner_ref=declaration.contract_id,
                schema_name=schema_name,
                schema_version=schema_version,
            )
        except Exception as exc:
            raise CanonViolation("ir_owned_artifact_registry_invalid") from exc
        if found is None:
            raise CanonViolation("ir_owned_artifact_representation_unregistered")
        if found.snapshot_revision != snapshot.revision or not found.candidates:
            raise CanonViolation("ir_owned_artifact_registry_invalid")
        candidates = tuple(
            registration
            for registration in found.candidates
            if _owner_registration_matches(declaration, registration)
        )
        if not candidates:
            raise CanonViolation("ir_owned_artifact_owner_contract_mismatch")
        accepted = tuple(
            registration
            for registration in candidates
            if _checked_owner_profile(declaration, profile, registration)
        )
        if not accepted:
            raise CanonViolation("ir_owned_artifact_profile_refused")
        try:
            profile_sha256 = _manifest_profile_sha256(dict(raw_manifest))
        except (CanonicalProfileRefusalError, TypeError, ValueError) as exc:
            raise CanonViolation("ir_owned_artifact_manifest_identity_invalid") from exc
        preflight.update(
            schema_name=schema_name,
            schema_version=schema_version,
            profile=profile,
            profile_sha256=profile_sha256,
            accepted_rows=accepted,
        )

    try:
        _, raw_bytes = _read_json_artifact_with_bytes(
            store,
            artifact_id,
            before_payload=preflight_before_payload,
        )
    except CanonViolation:
        raise
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_read_refused") from exc
    if not preflight:
        raise CanonViolation("ir_owned_artifact_manifest_identity_invalid")
    try:
        selected_spec = _make_ir_canon_spec(preflight["profile"])
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_profile_invalid") from exc
    payload_version = _owner_payload_version_from_snapshot(
        declaration,
        raw_bytes,
        selected_spec,
    )
    if payload_version is not None and (
        type(payload_version) is not str or not payload_version.strip()
    ):
        raise CanonViolation("ir_owned_artifact_payload_version_invalid")
    try:
        admission = resolve_owned_representation(
            snapshot,
            declaration.registry_key,
            owner_ref=declaration.contract_id,
            schema_name=preflight["schema_name"],
            schema_version=preflight["schema_version"],
            payload_version=payload_version,
        )
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_registry_invalid") from exc
    if admission is None:
        raise CanonViolation("ir_owned_artifact_representation_unreadable")
    if admission.snapshot_revision != snapshot.revision:
        raise CanonViolation("ir_owned_artifact_registry_invalid")
    source_registration = admission.source_registration
    current_registration = admission.current_registration
    if (
        not _owner_registration_matches(declaration, source_registration)
        or not _owner_registration_matches(declaration, current_registration)
        or source_registration not in preflight["accepted_rows"]
    ):
        raise CanonViolation("ir_owned_artifact_owner_contract_mismatch")
    source = _owner_source_from_snapshot(
        declaration,
        raw_bytes,
        selected_spec,
        admission,
    )
    consumer_value = _project_owner_source(declaration, source, admission)
    try:
        consumer_value = deepcopy(consumer_value)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_projection_refused") from exc
    return OwnedArtifactRead(
        value=consumer_value,
        raw_bytes=raw_bytes,
        admission=admission,
        contract_id=declaration.contract_id,
        dto_fqn=declaration.dto_fqn,
        abi_key=declaration.abi_key,
        registry_key=declaration.registry_key,
        purpose=declaration.purpose,
        owner_policy_revision=declaration.policy_revision,
        manifest_profile_sha256=preflight["profile_sha256"],
    )


def _get_owned_json_artifact[OwnerSourceT, OwnerConsumerT](
    store: _ProfiledJSONReader,
    artifact_id: ArtifactSelector,
    *,
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
) -> OwnerConsumerT:
    """Return a typed consumer projection after owner admission and same-byte proof."""
    return _get_owned_json_artifact_with_bytes(store, artifact_id, owner=owner).value


def _snapshot_neutral_owned_option_value(value: object, active_ids: set[int]) -> object:
    """Detach one JSON-compatible value returned by the neutral write-options protocol."""
    if value is None or type(value) in (str, bool, int, float):
        return value
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active_ids:
            raise CanonViolation("ir_owned_artifact_write_options_invalid")
        active_ids.add(identity)
        try:
            try:
                pairs = tuple(value.items())
            except Exception as exc:
                raise CanonViolation("ir_owned_artifact_write_options_invalid") from exc
            output: dict[str, object] = {}
            for key, item in pairs:
                if type(key) is not str or key in output:
                    raise CanonViolation("ir_owned_artifact_write_options_invalid")
                output[key] = _snapshot_neutral_owned_option_value(item, active_ids)
            return output
        finally:
            active_ids.remove(identity)
    if type(value) in (list, tuple):
        identity = id(value)
        if identity in active_ids:
            raise CanonViolation("ir_owned_artifact_write_options_invalid")
        active_ids.add(identity)
        try:
            return [_snapshot_neutral_owned_option_value(item, active_ids) for item in tuple(value)]
        finally:
            active_ids.remove(identity)
    raise CanonViolation("ir_owned_artifact_write_options_invalid")


def _clone_neutral_owned_write_options(value: object) -> StorePutOptions:
    """Take a detached IR-owned snapshot of the adapter's neutral options DTO."""
    if type(value) is not StorePutOptions:
        raise CanonViolation("ir_owned_artifact_write_options_invalid")
    try:
        raw_options = object.__getattribute__(value, "__dict__")
    except AttributeError as exc:
        raise CanonViolation("ir_owned_artifact_write_options_invalid") from exc
    option_fields = {field.name for field in fields(StorePutOptions)}
    if type(raw_options) is not dict or set(raw_options) != option_fields:
        raise CanonViolation("ir_owned_artifact_write_options_invalid")
    active_ids: set[int] = set()
    snapshot: dict[str, object] = {}
    for name in option_fields:
        snapshot[name] = _snapshot_neutral_owned_option_value(raw_options[name], active_ids)
    try:
        return StorePutOptions(**snapshot)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_write_options_invalid") from exc


def _snapshot_owned_write_options(store: object, value: object) -> StorePutOptions:
    """Use the store's typed neutral preparer before IR owner-field admission."""
    preparer = getattr(store, "prepare_owned_write_options", None)
    if not callable(preparer):
        raise CanonViolation("ir_owned_artifact_write_options_preparer_unavailable")
    try:
        prepared = cast("OwnedWriteOptionsPreparer", store).prepare_owned_write_options(value)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_write_options_invalid") from exc
    return _clone_neutral_owned_write_options(prepared)


@dataclass(frozen=True, slots=True)
class _OwnedJSONPreparedWrite:
    """Retain one frozen owner admission and exact serialized bytes until emission."""

    payload_bytes: bytes
    persist_payload: object
    canon_spec: CanonSpec
    normalized_inputs: list[InputRef]
    schema_name: str
    schema_version: str
    write_options: object | None


def _prepare_owned_json_artifact_write[OwnerSourceT, OwnerConsumerT](
    store: ArtifactStore,
    payload: object,
    *,
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    schema_name: object = _OWNER_UNSET,
    schema_version: object = _OWNER_UNSET,
    inputs: Sequence[InputRefLike] | None = None,
    canon_spec: CanonSpec | None = None,
    write_options: object = _OWNER_UNSET,
) -> _OwnedJSONPreparedWrite:
    """Run one owner admission and freeze bytes/options before any CAS emission."""
    selected_spec = _normalize_canon_spec(canon_spec)
    declaration = _require_owner_declaration(owner)
    if declaration.media_type != "application/json":
        raise CanonViolation("ir_owned_artifact_media_type_unsupported")
    if not _is_canonical_json_root(payload):
        raise CanonViolation("ir_owned_artifact_payload_version_invalid")
    try:
        frozen_payload_bytes = to_canonical_bytes(payload, selected_spec)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_payload_invalid") from exc
    selected_options: object | None = None
    if write_options is _OWNER_UNSET:
        normalized_inputs = _normalize_lineage_inputs(inputs)
    else:
        selected_options = _snapshot_owned_write_options(store, write_options)
        options_kind = getattr(selected_options, "kind", None)
        options_media = getattr(selected_options, "media_type", None)
        options_schema = getattr(selected_options, "schema", None)
        options_canon_value = getattr(selected_options, "canon", None)
        if (
            type(options_kind) is not str
            or options_kind != declaration.kind
            or type(options_media) is not str
            or options_media != declaration.media_type
            or not isinstance(options_schema, Mapping)
            or type(options_schema.get("name")) is not str
            or type(options_schema.get("version")) is not str
            or not isinstance(options_canon_value, Mapping)
        ):
            raise CanonViolation("ir_owned_artifact_write_options_reserved_field_mismatch")
        options_schema_name = options_schema["name"]
        options_schema_version = options_schema["version"]
        options_canon = _validated_ir_canon_info(options_canon_value)
        if schema_name is not _OWNER_UNSET and schema_name != options_schema_name:
            raise CanonViolation("ir_owned_artifact_write_options_schema_mismatch")
        if schema_version is not _OWNER_UNSET and schema_version != options_schema_version:
            raise CanonViolation("ir_owned_artifact_write_options_schema_mismatch")
        try:
            expected_profile = CanonInfo.from_spec(selected_spec)
        except Exception as exc:
            raise CanonViolation("ir_owned_artifact_profile_invalid") from exc
        if options_canon != expected_profile:
            raise CanonViolation("ir_owned_artifact_write_options_profile_mismatch")
        schema_name = options_schema_name
        schema_version = options_schema_version
        option_inputs = getattr(selected_options, "inputs", None)
        normalized_inputs = _normalize_lineage_inputs(option_inputs)
        if inputs is not None and _normalize_lineage_inputs(inputs) != normalized_inputs:
            raise CanonViolation("ir_owned_artifact_write_options_inputs_mismatch")

    from polisyos.ir.migrations.base import (
        find_writable_representation,
        get_default_write_representation,
        get_ir_owner_registry_snapshot,
        resolve_owned_representation,
    )

    try:
        snapshot = get_ir_owner_registry_snapshot()
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_registry_unavailable") from exc
    payload_version = _owner_payload_version_from_snapshot(
        declaration,
        frozen_payload_bytes,
        selected_spec,
    )
    if payload_version is not None and (
        type(payload_version) is not str or not payload_version.strip()
    ):
        raise CanonViolation("ir_owned_artifact_payload_version_invalid")
    if schema_name is _OWNER_UNSET and schema_version is _OWNER_UNSET:
        try:
            registration = get_default_write_representation(
                snapshot,
                declaration.registry_key,
                owner_ref=declaration.contract_id,
            )
        except Exception as exc:
            raise CanonViolation("ir_owned_artifact_registry_invalid") from exc
        if registration is None:
            raise CanonViolation("ir_owned_artifact_default_writer_unavailable")
    else:
        if (
            schema_name is _OWNER_UNSET
            or schema_version is _OWNER_UNSET
            or type(schema_name) is not str
            or not schema_name.strip()
            or type(schema_version) is not str
            or not schema_version.strip()
        ):
            raise CanonViolation("ir_owned_artifact_write_override_invalid")
        try:
            registration = find_writable_representation(
                snapshot,
                declaration.registry_key,
                owner_ref=declaration.contract_id,
                schema_name=schema_name,
                schema_version=schema_version,
                payload_version=payload_version,
            )
        except Exception as exc:
            raise CanonViolation("ir_owned_artifact_registry_invalid") from exc
        if registration is None or not _owner_registration_matches(declaration, registration):
            raise CanonViolation("ir_owned_artifact_write_override_unregistered")
    if not _owner_registration_matches(declaration, registration):
        raise CanonViolation("ir_owned_artifact_write_registration_invalid")
    selected_schema_name = registration.schema_name
    selected_schema_version = registration.schema_version
    if selected_options is not None and (
        options_schema_name != selected_schema_name
        or options_schema_version != selected_schema_version
    ):
        raise CanonViolation("ir_owned_artifact_write_options_schema_mismatch")
    if payload_version != registration.payload_version:
        raise CanonViolation("ir_owned_artifact_write_payload_version_mismatch")
    if not registration.writable:
        raise CanonViolation("ir_owned_artifact_write_registration_invalid")
    try:
        admission = resolve_owned_representation(
            snapshot,
            declaration.registry_key,
            owner_ref=declaration.contract_id,
            schema_name=selected_schema_name,
            schema_version=selected_schema_version,
            payload_version=payload_version,
        )
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_registry_invalid") from exc
    if (
        admission is None
        or admission.snapshot_revision != snapshot.revision
        or admission.source_registration != registration
        or not _owner_registration_matches(declaration, admission.current_registration)
    ):
        raise CanonViolation("ir_owned_artifact_write_route_unavailable")
    try:
        profile = CanonInfo.from_spec(selected_spec)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_profile_invalid") from exc
    if not _checked_owner_profile(declaration, profile, registration):
        raise CanonViolation("ir_owned_artifact_profile_refused")
    source = _owner_source_from_snapshot(
        declaration,
        frozen_payload_bytes,
        selected_spec,
        admission,
    )
    # Validate the owner reader's real DTO projection on an isolated source copy.
    _project_owner_source(declaration, source, admission)
    persist_payload = _decode_owner_callback_payload(
        frozen_payload_bytes,
        selected_spec,
        refusal_code="ir_owned_artifact_payload_invalid",
    )
    return _OwnedJSONPreparedWrite(
        payload_bytes=frozen_payload_bytes,
        persist_payload=persist_payload,
        canon_spec=selected_spec,
        normalized_inputs=normalized_inputs,
        schema_name=selected_schema_name,
        schema_version=selected_schema_version,
        write_options=selected_options,
    )


def _put_owned_json_artifact[OwnerSourceT, OwnerConsumerT](
    store: ArtifactStore,
    payload: object,
    *,
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    schema_name: object = _OWNER_UNSET,
    schema_version: object = _OWNER_UNSET,
    inputs: Sequence[InputRefLike] | None = None,
    canon_spec: CanonSpec | None = None,
) -> dict[str, str]:
    """Persist through an exact owner row after validation and capture the selected profile."""
    prepared = _prepare_owned_json_artifact_write(
        store,
        payload,
        owner=owner,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=canon_spec,
    )
    try:
        return put_json_artifact(
            store,
            prepared.persist_payload,
            kind=owner.kind,
            schema_name=prepared.schema_name,
            schema_version=prepared.schema_version,
            inputs=prepared.normalized_inputs,
            canon_spec=prepared.canon_spec,
            return_selected_profile=True,
        )
    except CanonViolation:
        raise
    except NotImplementedError as exc:
        if str(exc) == "artifact_store_return_selected_profile_unsupported":
            raise
        raise CanonViolation("ir_owned_artifact_write_refused") from exc
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_write_refused") from exc


def _owned_selected_manifest_matches_options(manifest: object, options: object) -> bool:
    """Compare raw selected manifest fields to the frozen neutral owner options."""
    if not isinstance(manifest, Mapping) or type(options) is not StorePutOptions:
        return False
    try:
        raw_options = object.__getattribute__(options, "__dict__")
    except AttributeError:
        return False
    option_fields = {field.name for field in fields(StorePutOptions)}
    if type(raw_options) is not dict or set(raw_options) != option_fields:
        return False
    missing = object()
    for option_name in option_fields:
        manifest_name = "schema" if option_name == "schema" else option_name
        expected = raw_options[option_name]
        if option_name in {"inputs", "warnings"}:
            expected = list(expected or [])
            actual = manifest.get(manifest_name, [])
        elif expected is None:
            actual = manifest.get(manifest_name)
            if actual is not None:
                return False
            continue
        else:
            actual = manifest.get(manifest_name, missing)
        if actual is missing or actual != expected:
            return False
    return True


def _put_owned_json_artifact_with_selected_view[OwnerSourceT, OwnerConsumerT](
    store: ArtifactStore,
    payload: object,
    *,
    owner: ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT],
    write_options: object,
    canon_spec: CanonSpec,
) -> object:
    """Persist canonical JSON through owner admission and return the store's exact selected ref."""
    prepared = _prepare_owned_json_artifact_write(
        store,
        payload,
        owner=owner,
        canon_spec=canon_spec,
        write_options=write_options,
    )
    if prepared.write_options is None:
        raise CanonViolation("ir_owned_artifact_write_options_invalid")
    writer = getattr(store, "put_bytes", None)
    if not callable(writer):
        raise CanonViolation("ir_owned_artifact_selected_writer_unavailable")
    try:
        parameters = inspect.signature(writer).parameters
    except (TypeError, ValueError) as exc:
        raise CanonViolation("ir_owned_artifact_selected_writer_unavailable") from exc
    selected_parameter = parameters.get("return_selected_profile")
    if selected_parameter is None or selected_parameter.kind not in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    ):
        raise CanonViolation("ir_owned_artifact_selected_writer_unavailable")
    try:
        # The callback receives a detached normalized DTO, so its mutation cannot
        # rewrite the expected context used for post-write reconciliation.
        emission_options = _clone_neutral_owned_write_options(prepared.write_options)
        selected_ref = writer(
            prepared.payload_bytes,
            emission_options,
            return_selected_profile=True,
        )
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_write_refused") from exc

    try:
        checked_ref = normalize_artifact_ref(selected_ref)
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_selected_ref_invalid") from exc
    selected_profile = checked_ref.get("manifest_profile_sha256")
    expected_content_id = "sha256:" + hashlib.sha256(prepared.payload_bytes).hexdigest()
    if (
        checked_ref.get("kind") != owner.kind
        or checked_ref.get("media_type") != owner.media_type
        or type(selected_profile) is not str
        or checked_ref.get("artifact_id") != expected_content_id
    ):
        raise CanonViolation("ir_owned_artifact_selected_ref_invalid")
    try:
        raw_manifest_bytes = store.get_manifest_bytes(selected_ref)
        raw_manifest = json.loads(
            raw_manifest_bytes,
            object_pairs_hook=_duplicate_key_rejector,
            parse_constant=_reject_json_constant,
        )
        if not isinstance(raw_manifest, Mapping):
            raise CanonViolation("ir_owned_artifact_selected_manifest_invalid")
        if _manifest_profile_sha256(
            raw_manifest
        ) != selected_profile or not _owned_selected_manifest_matches_options(
            raw_manifest, prepared.write_options
        ):
            raise CanonViolation("ir_owned_artifact_selected_manifest_options_mismatch")
        admitted = _get_owned_json_artifact_with_bytes(store, selected_ref, owner=owner)
    except CanonViolation:
        raise
    except Exception as exc:
        raise CanonViolation("ir_owned_artifact_selected_write_not_admitted") from exc
    if (
        admitted.raw_bytes != prepared.payload_bytes
        or admitted.manifest_profile_sha256 != selected_profile
    ):
        raise CanonViolation("ir_owned_artifact_selected_write_content_mismatch")
    return selected_ref


def _get_json_artifact_with_bytes(
    store: _ProfiledJSONReader, artifact_id: ArtifactSelector
) -> tuple[Any, bytes]:
    """Keep the generic opaque JSON reader's established callable signature."""
    return _read_json_artifact_with_bytes(store, artifact_id)


get_json_artifact_with_bytes = _get_json_artifact_with_bytes


def get_json_artifact(store: _ProfiledJSONReader, artifact_id: ArtifactSelector) -> object:
    """Read and return JSON after selected-profile and same-byte conformance checks."""
    value, _raw_bytes = _get_json_artifact_with_bytes(store, artifact_id)
    return value


def normalize_input_sequence(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Reuse ``normalize_input_refs`` for callers that still pass generic input sequences."""
    return _normalize_lineage_inputs(inputs)


__all__ = [
    "get_json_artifact",
    "get_json_artifact_with_bytes",
    "normalize_input_sequence",
    "put_json_artifact",
]
