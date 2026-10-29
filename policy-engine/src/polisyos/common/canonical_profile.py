"""Shared strict profile-conformance mechanics for persisted JSON.

This module owns raw-manifest parsing and byte-conformance mechanics. Callers
supply the decoder and encoder from the actual public codec facade so Core and
IR retain their distinct typed-tag sets and exception types.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    NoReturn,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from polisyos.common.serialization import fast_json_dumps_bytes

if TYPE_CHECKING:
    from pydantic import BaseModel

CanonicalProfileStatus = Literal[
    "declared_bytes_conformant",
    "profile_absent_unqualified_candidate",
    "declared_unknown_candidate",
]
CanonicalProfileDeclarationStatus = Literal["declared", "absent", "declared_unknown_candidate"]
_VERIFIED_READ_TOKEN = object()
_T = TypeVar("_T")
_Selector = TypeVar("_Selector")


class CanonicalProfileRefusalError(ValueError):
    """A typed refusal to consume a malformed or nonconformant profile view."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@runtime_checkable
class _ProfileLike(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def max_depth(self) -> int: ...


def _profile_fields(profile: BaseModel) -> _ProfileLike:
    """Require the typed fields used by the canonical profile bridge."""
    if not isinstance(profile, _ProfileLike):
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    if (
        type(profile.name) is not str
        or type(profile.version) is not str
        or type(profile.max_depth) is not int
    ):
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    return profile


@dataclass(frozen=True)
class CanonicalProfileDeclaration:
    """A complete strict profile or a truly absent declaration."""

    profile: BaseModel | None
    status: CanonicalProfileDeclarationStatus


@dataclass(frozen=True, init=False)
class CanonicalProfileRead:
    """Decoded bytes with profile status and selected identity.

    ``value`` is available only for a declared, byte-conformant profile. An
    explicitly requested unqualified legacy read is candidate-only and must use
    ``unqualified_candidate_value`` so callers cannot mistake it for verified
    semantic input. ``reader_policy_id`` optionally records the concrete decoder
    policy chosen by the reader; it is not producer attestation or authority.
    """

    _decoded_value: Any
    raw_payload_bytes: bytes
    status: CanonicalProfileStatus
    selected_artifact_id: str | None
    selected_manifest_profile_sha256: str | None
    reader_policy_id: str | None
    _reader_validated: bool

    def __init__(
        self,
        value: Any,  # noqa: ANN401
        raw_payload_bytes: bytes,
        status: CanonicalProfileStatus,
        selected_artifact_id: str | None = None,
        selected_manifest_profile_sha256: str | None = None,
        *,
        reader_policy_id: str | None = None,
        _validation_token: object | None = None,
    ) -> None:
        object.__setattr__(self, "_decoded_value", value)
        object.__setattr__(self, "raw_payload_bytes", raw_payload_bytes)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "selected_artifact_id", selected_artifact_id)
        object.__setattr__(
            self, "selected_manifest_profile_sha256", selected_manifest_profile_sha256
        )
        object.__setattr__(self, "reader_policy_id", reader_policy_id)
        object.__setattr__(self, "_reader_validated", _validation_token is _VERIFIED_READ_TOKEN)

    @property
    def value(self) -> Any:  # noqa: ANN401
        """Return a value whose selected bytes matched a declared profile."""
        if self.status != "declared_bytes_conformant" or not self._reader_validated:
            raise CanonicalProfileRefusalError("canon_profile_not_verified")
        return self._decoded_value

    @property
    def unqualified_candidate_value(self) -> Any:  # noqa: ANN401
        """Return an explicitly unqualified value for candidate-only inspection."""
        if self.status != "profile_absent_unqualified_candidate" or not self._reader_validated:
            raise CanonicalProfileRefusalError("canon_profile_candidate_read_not_unqualified")
        return self._decoded_value

    @property
    def raw_only_candidate_bytes(self) -> bytes:
        """Return exact bytes for a declared but unsupported profile, without decoding."""
        if self.status != "declared_unknown_candidate" or not self._reader_validated:
            raise CanonicalProfileRefusalError("canon_profile_candidate_read_not_raw_only")
        return self.raw_payload_bytes


def require_declared_profile(read: CanonicalProfileRead) -> Any:  # noqa: ANN401
    """Return a value only when its selected bytes matched a declared profile.

    This is the shared intake guard for authority, promotion, and issuer owners.
    An explicitly unqualified candidate read is never a substitute for that
    verification, even when its payload happens to decode under current defaults.
    """
    if (
        type(read) is not CanonicalProfileRead
        or read.status != "declared_bytes_conformant"
        or not read._reader_validated
    ):
        raise CanonicalProfileRefusalError("canon_profile_not_verified")
    return read.value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _normalize_canonical_profile_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the one JSON-mode sequence form accepted for profile separators."""
    normalized = dict(payload)
    separators = normalized.get("separators")
    if (
        type(separators) is list
        and len(separators) == 2
        and all(type(separator) is str for separator in separators)
    ):
        normalized["separators"] = tuple(separators)
    return normalized


def _manifest_profile_schema_version(manifest: Mapping[str, Any]) -> str:
    """Return one supported persisted manifest-profile projection version."""
    version = manifest.get("manifest_schema_version", "v1")
    if type(version) is not str or version not in {"v1", "v2", "v3"}:
        raise CanonicalProfileRefusalError("manifest_profile_schema_version_invalid")
    return version


def _manifest_profile_projection(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Project normalized manifest data under the historical CAS profile rules.

    Callers with typed models must first project them to JSON-mode, alias-aware,
    ``exclude_none`` mappings. Raw readers must reconcile that mapping with the
    typed manifest before using the projection as a selected-view identity.
    """
    if not isinstance(manifest, Mapping):
        raise CanonicalProfileRefusalError("manifest_profile_mapping_required")
    version = _manifest_profile_schema_version(manifest)
    excluded = {"artifact_id", "byte_size", "created_at"}
    projection = {
        key: value
        for key, value in manifest.items()
        if key not in excluded and not (version in {"v1", "v2"} and key == "integrity")
    }
    if version == "v3" and isinstance(projection.get("integrity"), Mapping):
        projection["integrity"] = {
            key: value for key, value in projection["integrity"].items() if key != "sha256"
        }
    return projection


def _manifest_profile_sha256(manifest: Mapping[str, Any]) -> str:
    """Hash one normalized manifest projection using its versioned CAS domain."""
    projection = _manifest_profile_projection(manifest)
    payload = fast_json_dumps_bytes(projection, sort_keys=True)
    version = _manifest_profile_schema_version(manifest)
    domain_version = "v2" if version == "v3" else "v1"
    domain = f"polisyos.cas.manifest-profile.{domain_version}\0".encode("ascii")
    return f"sha256:{hashlib.sha256(domain + payload).hexdigest()}"


def parse_canonical_profile(
    raw_manifest_bytes: bytes,
    *,
    profile_model: type[BaseModel],
    allow_profile_absent: bool,
    supported_versions: tuple[str, ...] | None = None,
) -> CanonicalProfileDeclaration:
    """Parse and fully validate the raw selected profile before blob I/O.

    ``supported_versions`` is supplied by the concrete reader owner.  Common
    only compares the declaration; it never decides which tag policy is
    authorized for Core or IR.
    """
    if type(raw_manifest_bytes) is not bytes:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_invalid")
    try:
        manifest = json.loads(
            raw_manifest_bytes,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_invalid") from exc
    if not isinstance(manifest, Mapping):
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_invalid")
    if "canon" not in manifest:
        if not allow_profile_absent:
            raise CanonicalProfileRefusalError("canon_profile_absent")
        return CanonicalProfileDeclaration(profile=None, status="absent")

    raw_canon = manifest["canon"]
    if not isinstance(raw_canon, Mapping):
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    payload = dict(raw_canon)
    if set(profile_model.model_fields) - set(payload):
        raise CanonicalProfileRefusalError("canon_profile_incomplete")
    payload = _normalize_canonical_profile_mapping(payload)
    try:
        parsed_profile = profile_model.model_validate(payload, strict=True)
        profile = _profile_fields(parsed_profile)
        supported = _profile_fields(profile_model())
    except (TypeError, ValueError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_invalid") from exc

    if profile.max_depth < 0:
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    versions = (supported.version,) if supported_versions is None else supported_versions
    if (
        not versions
        or any(type(version) is not str or not version for version in versions)
        or profile.name != supported.name
        or profile.version not in versions
    ):
        return CanonicalProfileDeclaration(
            profile=parsed_profile,
            status="declared_unknown_candidate",
        )
    return CanonicalProfileDeclaration(profile=parsed_profile, status="declared")


def _decode_and_reencode_profiled_bytes(
    raw_payload_bytes: bytes,
    *,
    max_depth: int,
    spec: object,
    decode: Callable[[bytes, int], _T],
    encode: Callable[[_T, object], bytes],
) -> _T:
    """Decode and re-encode bytes under one profile, requiring exact identity."""
    if type(raw_payload_bytes) is not bytes:
        raise CanonicalProfileRefusalError("canon_profile_payload_bytes_invalid")
    try:
        value = decode(raw_payload_bytes, max_depth)
        expected_bytes = encode(value, spec)
    except Exception as exc:
        raise CanonicalProfileRefusalError("canon_profile_payload_nonconformant") from exc
    if type(expected_bytes) is not bytes or expected_bytes != raw_payload_bytes:
        raise CanonicalProfileRefusalError("canon_profile_payload_nonconformant")
    return value


def decode_profiled_canonical_bytes(
    raw_payload_bytes: bytes,
    declaration: CanonicalProfileDeclaration,
    *,
    profile_model: type[BaseModel],
    make_spec: Callable[[BaseModel], object],
    decode: Callable[[bytes, int], Any],
    encode: Callable[[Any, object], bytes],
    reader_policy_id: str | None = None,
) -> CanonicalProfileRead:
    """Decode using the caller-selected reader context after raw profile validation.

    The optional reader policy identifies the concrete owner decoder; it is not
    producer attestation or publication authority.
    """
    if type(raw_payload_bytes) is not bytes:
        raise CanonicalProfileRefusalError("canon_profile_payload_bytes_invalid")
    if reader_policy_id is not None and (
        type(reader_policy_id) is not str or not reader_policy_id.strip()
    ):
        raise CanonicalProfileRefusalError("canon_profile_reader_policy_invalid")
    if declaration.status == "declared_unknown_candidate":
        return CanonicalProfileRead(
            value=None,
            raw_payload_bytes=raw_payload_bytes,
            status="declared_unknown_candidate",
            reader_policy_id=reader_policy_id,
            _validation_token=_VERIFIED_READ_TOKEN,
        )
    if declaration.profile is None:
        default = _profile_fields(profile_model())
        value = decode(raw_payload_bytes, default.max_depth)
        return CanonicalProfileRead(
            value=value,
            raw_payload_bytes=raw_payload_bytes,
            status="profile_absent_unqualified_candidate",
            reader_policy_id=reader_policy_id,
            _validation_token=_VERIFIED_READ_TOKEN,
        )

    profile = declaration.profile
    profile_fields = _profile_fields(profile)
    value = _decode_and_reencode_profiled_bytes(
        raw_payload_bytes,
        max_depth=profile_fields.max_depth,
        spec=make_spec(profile),
        decode=decode,
        encode=encode,
    )
    return CanonicalProfileRead(
        value=value,
        raw_payload_bytes=raw_payload_bytes,
        status="declared_bytes_conformant",
        reader_policy_id=reader_policy_id,
        _validation_token=_VERIFIED_READ_TOKEN,
    )


def _bind_selected_artifact_identity(
    read: CanonicalProfileRead,
    *,
    artifact_id: str,
    manifest_profile_sha256: str,
) -> CanonicalProfileRead:
    """Bind the verified result to the exact selected Core manifest identity."""
    if type(read) is not CanonicalProfileRead or not read._reader_validated:
        raise CanonicalProfileRefusalError("canon_profile_read_not_verified")
    return CanonicalProfileRead(
        value=read._decoded_value,
        raw_payload_bytes=read.raw_payload_bytes,
        status=read.status,
        selected_artifact_id=artifact_id,
        selected_manifest_profile_sha256=manifest_profile_sha256,
        reader_policy_id=read.reader_policy_id,
        _validation_token=_VERIFIED_READ_TOKEN,
    )


def read_canonical_profiled_bytes(
    raw_manifest_bytes: bytes,
    raw_payload_bytes: bytes,
    *,
    profile_model: type[BaseModel],
    make_spec: Callable[[BaseModel], object],
    decode: Callable[[bytes, int], Any],
    encode: Callable[[Any, object], bytes],
    allow_profile_absent: bool,
    reader_policy_id: str | None = None,
) -> CanonicalProfileRead:
    """Parse and verify a selected view under an optional fixed reader identity.

    The identity records which concrete codec policy materialized the value; it
    does not establish the producer or the value's authority.
    """
    declaration = parse_canonical_profile(
        raw_manifest_bytes,
        profile_model=profile_model,
        allow_profile_absent=allow_profile_absent,
    )
    return decode_profiled_canonical_bytes(
        raw_payload_bytes,
        declaration,
        profile_model=profile_model,
        make_spec=make_spec,
        decode=decode,
        encode=encode,
        reader_policy_id=reader_policy_id,
    )


def read_optional_selected_artifact(
    selector: _Selector | None,
    reader: Callable[[_Selector], _T],
    *,
    refusal_code: str,
    expected_errors: tuple[type[Exception], ...],
) -> _T | None:
    """Read a selected view without collapsing refusal into absence.

    ``None`` means the caller supplied no selector. Once a selector is supplied,
    expected storage, decoding, and validation failures become a typed refusal
    carrying the owner-provided code and the original exception as its cause.
    A reader returning ``None`` after selection is also a refusal. Unexpected
    exceptions keep their original type and propagate unchanged.
    """

    if selector is None:
        return None
    try:
        payload = reader(selector)
        if payload is None:
            raise CanonicalProfileRefusalError(refusal_code)
        return payload
    except CanonicalProfileRefusalError:
        raise
    except expected_errors as exc:
        raise CanonicalProfileRefusalError(refusal_code) from exc


__all__ = [
    "CanonicalProfileDeclaration",
    "CanonicalProfileRead",
    "CanonicalProfileRefusalError",
    "CanonicalProfileStatus",
    "decode_profiled_canonical_bytes",
    "parse_canonical_profile",
    "read_canonical_profiled_bytes",
    "read_optional_selected_artifact",
    "require_declared_profile",
]
