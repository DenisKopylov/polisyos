"""Internal candidate request quantities and source-owned prepared emissions.

This carrier authenticates no external issuer and grants no authority. Common
knows neither N4 stage vocabulary nor a provider's cost/permission semantics.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from threading import RLock
from typing import Any, NoReturn

_KEY = "polisyos_producer_request"
_SCHEMA = "policyos.internal.producer_request.v1"
_FIELDS = frozenset(
    {
        "schema_version",
        "subject_ref",
        "producer_id",
        "model_id",
        "stage",
        "instance",
        "attempt",
        "source_input_sha256",
        "prepared_input_sha256",
        "preparation",
        "metadata_presence",
        "context_id",
    }
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^sha256:[0-9a-f]{64}$")


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


@dataclass(frozen=True)
class _ProducerBinding:
    subject_ref: str
    model_id: str
    producer_id: str
    _issued: dict[str, int] = field(default_factory=dict, repr=False, compare=False)
    _lock: RLock = field(default_factory=RLock, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.subject_ref) is not str or _REF.fullmatch(self.subject_ref) is None:
            raise ValueError("producer_request_subject_ref_invalid")
        if type(self.model_id) is not str or not self.model_id.strip():
            raise ValueError("producer_request_model_invalid")
        if type(self.producer_id) is not str or not self.producer_id.strip():
            raise ValueError("producer_request_owner_invalid")


@dataclass(frozen=True)
class _ActiveRequest:
    binding: _ProducerBinding
    context_bytes: bytes
    call_bytes: bytes


class _PreparedEmission:
    """Opaque obligation issued only after the canonical body owner reconciles inputs."""

    __slots__ = ("_context_bytes", "_payload_bytes", "_projection")
    _context_bytes: bytes
    _payload_bytes: bytes
    _projection: Callable[[dict[str, Any]], dict[str, Any]] | None

    def __init__(self) -> None:
        raise TypeError("prepared emissions are issued by the request owner")

    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise AttributeError("prepared emissions are immutable")

    def __copy__(self) -> NoReturn:
        raise TypeError("prepared emissions cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        raise TypeError("prepared emissions cannot be copied")

    def __reduce_ex__(self, protocol: int) -> NoReturn:
        raise TypeError("prepared emissions cannot be serialized")


@dataclass
class _PayloadCapture:
    active: _ActiveRequest | None
    projection: Callable[[dict[str, Any]], dict[str, Any]] | None
    emission: _PreparedEmission | None = None

    def finish(self, payload: Mapping[str, Any]) -> _PreparedEmission | None:
        if self.active is None:
            if self.emission is not None:
                raise ValueError("producer_request_unexpected_owned_emission")
            return None
        if self.emission is None:
            raise ValueError("producer_request_prepared_emission_missing")
        if self.emission._context_bytes != self.active.context_bytes:
            raise ValueError("producer_request_preparation_scope_mismatch")
        _validate_prepared_payload(payload, self.emission)
        return self.emission


_ACTIVE: ContextVar[_ActiveRequest | None] = ContextVar("producer_request_binding", default=None)
_CAPTURE: ContextVar[_PayloadCapture | None] = ContextVar("producer_payload_capture", default=None)


@contextmanager
def _capture_payload(
    projection: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Iterator[_PayloadCapture]:
    capture = _PayloadCapture(_ACTIVE.get(), projection)
    token = _CAPTURE.set(capture)
    try:
        yield capture
    finally:
        _CAPTURE.reset(token)


def _parse_context(value: object, *, sealed: bool) -> dict[str, Any]:
    required = _FIELDS | ({"payload_sha256"} if sealed else set())
    if type(value) is not dict or set(value) != required:
        raise ValueError("producer_request_context_fields_invalid")
    if value["schema_version"] != _SCHEMA:
        raise ValueError("producer_request_context_schema_invalid")
    _ProducerBinding(value["subject_ref"], value["model_id"], value["producer_id"])
    for name in ("stage", "instance"):
        if type(value[name]) is not str or not value[name].strip():
            raise ValueError("producer_request_control_identity_invalid")
    if type(value["attempt"]) is not int or value["attempt"] < 0:
        raise ValueError("producer_request_attempt_invalid")
    for name in ("source_input_sha256", "prepared_input_sha256", "context_id"):
        if type(value[name]) is not str or _SHA.fullmatch(value[name]) is None:
            raise ValueError("producer_request_input_identity_invalid")
    if type(value["preparation"]) is not dict:
        raise ValueError("producer_request_preparation_untyped")
    if type(value["metadata_presence"]) is not str or value["metadata_presence"] not in {
        "absent",
        "none",
        "object",
    }:
        raise ValueError("producer_request_metadata_presence_invalid")
    basis = {
        key: item for key, item in value.items() if key not in {"context_id", "payload_sha256"}
    }
    if _digest(basis) != value["context_id"]:
        raise ValueError("producer_request_context_identity_mismatch")
    if sealed and (
        type(value["payload_sha256"]) is not str or _SHA.fullmatch(value["payload_sha256"]) is None
    ):
        raise ValueError("producer_request_payload_identity_invalid")
    return dict(value)


def _without_context(request: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    metadata = request.get("metadata")
    if type(metadata) is not dict or _KEY not in metadata:
        raise ValueError("producer_request_owned_context_missing")
    remaining = {key: item for key, item in metadata.items() if key != _KEY}
    original = dict(request)
    presence = context["metadata_presence"]
    if presence == "object":
        original["metadata"] = remaining
    else:
        if remaining:
            raise ValueError("producer_request_metadata_substituted")
        if presence == "none":
            original["metadata"] = None
        else:
            original.pop("metadata")
    return original


def _issue_args(
    binding: _ProducerBinding,
    *,
    stage: str,
    instance: str | None,
    attempt: int,
    source: Mapping[str, Any],
    prepared: Mapping[str, Any],
    preparation: Mapping[str, Any],
) -> dict[str, Any]:
    if type(binding) is not _ProducerBinding:
        raise TypeError("producer_request_binding_untyped")
    for quantity in (source, prepared):
        metadata = quantity.get("metadata")
        if metadata is not None and type(metadata) is not dict:
            raise ValueError("producer_request_metadata_untyped")
        if isinstance(metadata, Mapping) and _KEY in metadata:
            raise ValueError("producer_request_namespace_reserved")
    metadata = prepared.get("metadata")
    context = {
        "schema_version": _SCHEMA,
        "subject_ref": binding.subject_ref,
        "producer_id": binding.producer_id,
        "model_id": binding.model_id,
        "stage": stage,
        "instance": instance if instance is not None else stage,
        "attempt": attempt,
        "source_input_sha256": _digest(source),
        "prepared_input_sha256": _digest(prepared),
        "preparation": dict(preparation),
        "metadata_presence": "absent"
        if "metadata" not in prepared
        else "none"
        if metadata is None
        else "object",
    }
    context["context_id"] = _digest(context)
    context = _parse_context(context, sealed=False)
    with binding._lock:
        key = context["context_id"]
        binding._issued[key] = binding._issued.get(key, 0) + 1
    return {**prepared, "metadata": {**dict(metadata or {}), _KEY: context}}


def _request_args(
    client: object, *, stage: str, attempt: int = 0, instance: str | None = None, **request: object
) -> dict[str, Any]:
    binding = getattr(client, "_producer_request_binding", None)
    if binding is None:
        return request
    return _issue_args(
        binding,
        stage=stage,
        attempt=attempt,
        instance=instance,
        source=request,
        prepared=request,
        preparation={"kind": "identity"},
    )


def _call_context(
    request: Mapping[str, Any], binding: _ProducerBinding | None
) -> dict[str, Any] | None:
    metadata = request.get("metadata")
    value = metadata.get(_KEY) if isinstance(metadata, Mapping) else None
    if binding is None:
        if isinstance(metadata, Mapping) and _KEY in metadata:
            raise ValueError("producer_request_context_without_owner")
        return None
    context = _parse_context(value, sealed=False)
    if (context["subject_ref"], context["model_id"], context["producer_id"]) != (
        binding.subject_ref,
        binding.model_id,
        binding.producer_id,
    ):
        raise ValueError("producer_request_context_owner_mismatch")
    if _digest(_without_context(request, context)) != context["prepared_input_sha256"]:
        raise ValueError("producer_request_input_substituted")
    with binding._lock:
        key = context["context_id"]
        count = binding._issued.get(key, 0)
        if count <= 0:
            raise ValueError("producer_request_context_not_issued")
        if count == 1:
            binding._issued.pop(key)
        else:
            binding._issued[key] = count - 1
    return context


@contextmanager
def _binding_scope(
    binding: _ProducerBinding | None, context: Mapping[str, Any] | None, call: Mapping[str, Any]
) -> Iterator[None]:
    active = None
    if binding is not None:
        parsed = _parse_context(dict(context) if context is not None else None, sealed=False)
        if _digest(_without_context(call, parsed)) != parsed["prepared_input_sha256"]:
            raise ValueError("producer_request_scope_input_mismatch")
        active = _ActiveRequest(binding, _bytes(parsed), _bytes(call))
    token = _ACTIVE.set(active)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def _unsealed_payload(payload: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    unsealed = {key: item for key, item in context.items() if key != "payload_sha256"}
    return {**payload, "metadata": {**dict(payload["metadata"]), _KEY: unsealed}}


def _read_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    context = _parse_context(
        metadata.get(_KEY) if isinstance(metadata, Mapping) else None, sealed=True
    )
    if payload.get("model") != context["model_id"]:
        raise ValueError("producer_request_payload_model_mismatch")
    if _digest(_unsealed_payload(payload, context)) != context["payload_sha256"]:
        raise ValueError("producer_request_payload_substituted")
    return context


def _new_emission(
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    projection: Callable[[dict[str, Any]], dict[str, Any]] | None,
) -> _PreparedEmission:
    emission = object.__new__(_PreparedEmission)
    object.__setattr__(emission, "_context_bytes", _bytes(context))
    object.__setattr__(emission, "_payload_bytes", _bytes(payload))
    object.__setattr__(emission, "_projection", projection)
    return emission


def _producer_payload[**P](owner: Callable[P, dict[str, Any]]) -> Callable[P, dict[str, Any]]:
    """Bind the complete actual owner signature, not a selected name projection."""
    signature = inspect.signature(owner)
    owner_parameter = next(iter(signature.parameters))

    @wraps(owner)
    def invoke(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        actual = signature.bind(*args, **kwargs)
        actual.apply_defaults()
        active = _ACTIVE.get()
        metadata = actual.arguments.get("metadata")
        if active is None:
            if isinstance(metadata, Mapping) and _KEY in metadata:
                raise ValueError("producer_request_payload_without_owner")
            return owner(*args, **kwargs)
        context = _parse_context(
            metadata.get(_KEY) if isinstance(metadata, Mapping) else None, sealed=False
        )
        if _bytes(context) != active.context_bytes:
            raise ValueError("producer_request_transport_context_substituted")
        expected = signature.bind(
            actual.arguments[owner_parameter], **json.loads(active.call_bytes)
        )
        expected.apply_defaults()
        actual_quantity = {
            key: item for key, item in actual.arguments.items() if key != owner_parameter
        }
        expected_quantity = {
            key: item for key, item in expected.arguments.items() if key != owner_parameter
        }
        if _bytes(actual_quantity) != _bytes(expected_quantity):
            raise ValueError("producer_request_transport_input_substituted")
        payload = owner(*args, **kwargs)
        body_metadata = payload.get("metadata")
        if (
            not isinstance(body_metadata, Mapping)
            or _bytes(body_metadata.get(_KEY)) != active.context_bytes
        ):
            raise ValueError("producer_request_owned_context_missing")
        if payload.get("model") != active.binding.model_id:
            raise ValueError("producer_request_payload_model_mismatch")
        sealed = {**context, "payload_sha256": _digest(payload)}
        payload = {**payload, "metadata": {**body_metadata, _KEY: sealed}}
        capture = _CAPTURE.get()
        if capture is not None:
            if capture.emission is not None:
                raise ValueError("producer_request_multiple_prepared_emissions")
            capture.emission = _new_emission(context, payload, capture.projection)
        return payload

    return invoke


def _validate_prepared_payload(
    payload: Mapping[str, Any], emission: _PreparedEmission | None
) -> None:
    active = _ACTIVE.get()
    metadata = payload.get("metadata")
    owned_metadata = isinstance(metadata, Mapping) and _KEY in metadata
    if emission is None:
        if active is not None or owned_metadata:
            raise ValueError("producer_request_prepared_emission_missing")
        return
    if type(emission) is not _PreparedEmission:
        raise TypeError("producer_request_emission_untyped")
    context = _read_payload(payload)
    unsealed = {key: item for key, item in context.items() if key != "payload_sha256"}
    if _bytes(unsealed) != emission._context_bytes:
        raise ValueError("producer_request_emission_context_mismatch")
    if active is not None and active.context_bytes != emission._context_bytes:
        raise ValueError("producer_request_emission_scope_mismatch")
    if _bytes(payload) != emission._payload_bytes:
        raise ValueError("producer_request_prepared_body_substituted")


def _derive_payload(
    emission: _PreparedEmission | None, previous: dict[str, Any]
) -> tuple[dict[str, Any], _PreparedEmission | None]:
    """Apply only the projection frozen by the actual prepared owner, never caller data."""
    _validate_prepared_payload(previous, emission)
    if emission is None:
        raise ValueError("producer_request_unbound_projection_not_required")
    if emission._projection is None:
        raise ValueError("producer_request_projection_unavailable")
    context = json.loads(emission._context_bytes)
    projected = emission._projection(json.loads(emission._payload_bytes))
    metadata = projected.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("producer_request_projection_context_missing")
    projected = _unsealed_payload(projected, context)
    sealed = {**context, "payload_sha256": _digest(projected)}
    projected = {**projected, "metadata": {**projected["metadata"], _KEY: sealed}}
    return projected, _new_emission(context, projected, emission._projection)


def _owned_request_context(request: Mapping[str, Any]) -> dict[str, Any]:
    """Reconcile an actual active owner occurrence for a lower-layer preparation."""
    active = _ACTIVE.get()
    if active is None:
        raise ValueError("producer_request_active_owner_missing")
    if _bytes(request) != active.call_bytes:
        raise ValueError("producer_request_active_call_substituted")
    context = json.loads(active.context_bytes)
    if _digest(_without_context(request, context)) != context["prepared_input_sha256"]:
        raise ValueError("producer_request_active_prepared_input_mismatch")
    return context
