"""Read Core JSON artifacts against their exact raw manifest profile."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import types
import weakref
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, RootModel, TypeAdapter, ValidationError
from pydantic.errors import PydanticUserError

from polisyos.common.canonical_profile import (
    CanonicalProfileDeclaration,
    CanonicalProfileRead,
    CanonicalProfileRefusalError,
    _bind_selected_artifact_identity,
    decode_profiled_canonical_bytes,
    parse_canonical_profile,
    require_declared_profile,
)
from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts._integrity_ops import (
    ArtifactBoundedManifestRead,
    ArtifactBoundedManifestReadError,
    ArtifactMemberReadIntegrityError,
    ArtifactReadBoundsError,
    ArtifactStoreReadUsage,
    _is_artifact_store_read_usage,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    InputRef,
)
from polisyos.core.artifacts.protocol import (
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
)
from polisyos.core.canon import (
    CanonSpec,
    content_hash,
    from_canonical_bytes,
)
from polisyos.core.canon import (
    to_canonical_bytes as to_canonical_bytes,
)
from polisyos.core.canon.canon_json import (
    CORE_TAG_POLICY_ID,
    CORE_V3_TAG_POLICY_ID,
    _encode_core_canonical_bytes_raw,
)

_ModelT = TypeVar("_ModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class CoreJsonReadLimits:
    """Selected resource-policy bounds for one Core JSON artifact read.

    max_manifest_bytes bounds the exact selected raw manifest before parsing.
    max_bytes, max_depth, and max_elements independently bound the selected
    payload stream. max_elements counts JSON lexical nodes: object/array
    containers, scalar values, and object member-name strings. These are generic
    resource limits, not a scientific shape contract.
    """

    max_bytes: int
    max_depth: int
    max_elements: int
    max_manifest_bytes: int

    def __post_init__(self) -> None:
        """Require explicit positive integer limits; booleans are not integers here."""
        for field_name in (
            "max_bytes",
            "max_depth",
            "max_elements",
            "max_manifest_bytes",
        ):
            value = getattr(self, field_name)
            minimum = 0 if field_name == "max_depth" else 1
            if type(value) is not int or value < minimum:
                raise ValueError(f"core_json_read_limit_invalid:{field_name}")


_GUARDED_CANONICAL_BOOTSTRAP_TOKEN = object()
_GUARDED_CANONICAL_LOCK = threading.RLock()
_GUARDED_CANONICAL_READERS: dict[int, weakref.ReferenceType[object]] = {}


def _register_guarded_canonical_reader(store: object, *, token: object) -> None:
    """Register an exact Core-owned scope; never accept a per-call dispatch owner."""
    if token is not _GUARDED_CANONICAL_BOOTSTRAP_TOKEN:
        raise ValueError("guarded_canonical_bootstrap_required")
    identity = id(store)

    def forget(reference: weakref.ReferenceType[object]) -> None:
        with _GUARDED_CANONICAL_LOCK:
            if _GUARDED_CANONICAL_READERS.get(identity) is reference:
                del _GUARDED_CANONICAL_READERS[identity]

    with _GUARDED_CANONICAL_LOCK:
        if identity in _GUARDED_CANONICAL_READERS:
            raise ValueError("guarded_canonical_reader_already_registered")
        _GUARDED_CANONICAL_READERS[identity] = weakref.ref(store, forget)


def _registered_guarded_identity(store: object) -> bool:
    with _GUARDED_CANONICAL_LOCK:
        reference = _GUARDED_CANONICAL_READERS.get(id(store))
        return reference is not None and reference() is store


def _guarded_canonical_reader(store: object) -> Any | None:
    """Resolve only exact registered owners or the exact Core-to-IR adapter."""
    if _registered_guarded_identity(store):
        return store
    # This prefilter is not authority: exact adapter type and registered
    # underlying object identity are both checked before dispatch.
    if type(store).__module__ != "polisyos.core.artifacts.ir_adapter":
        return None
    from .ir_adapter import CoreToIRArtifactStoreAdapter, _CoreToIRArtifactReaderAdapter

    if type(store) in {CoreToIRArtifactStoreAdapter, _CoreToIRArtifactReaderAdapter}:
        underlying = store.store
        if _registered_guarded_identity(underlying):
            return underlying
    return None


class CoreJsonReadBoundsRefusalError(CanonicalProfileRefusalError):
    """Typed refusal carrying actual selected-manifest and payload measurements."""

    def __init__(
        self,
        code: str,
        *,
        limits: CoreJsonReadLimits | None,
        max_manifest_bytes: int,
        observed_manifest_bytes: int | None,
        observed_bytes: int | None,
        observed_depth: int,
        observed_elements: int,
        limit_name: str | None = None,
        observed_manifest_selection_bytes: int | None = None,
        observed_manifest_verification_bytes: int | None = None,
        observed_payload_size: int | None = None,
        payload_integrity_verified: bool = False,
        source_usage_complete: bool = True,
        failure_stage: str | None = None,
        cleanup_failure_stage: str | None = None,
        cleanup_exception_type: str | None = None,
        cleanup_exception_code: str | None = None,
        original_exception_type: str | None = None,
        original_exception_code: str | None = None,
        original_exception_message: str | None = None,
    ) -> None:
        """Retain selected limits and actual owner-reported transfers on refusal."""
        super().__init__(code)
        self.limits = limits
        self.max_manifest_bytes = max_manifest_bytes
        self.observed_manifest_bytes = observed_manifest_bytes
        self.observed_manifest_selection_bytes = (
            observed_manifest_bytes
            if observed_manifest_selection_bytes is None and source_usage_complete
            else observed_manifest_selection_bytes
        )
        self.observed_manifest_verification_bytes = observed_manifest_verification_bytes
        self.observed_bytes = observed_bytes
        self.observed_payload_size = observed_payload_size
        self.payload_integrity_verified = payload_integrity_verified
        self.source_usage_complete = bool(
            source_usage_complete
            and type(self.observed_manifest_selection_bytes) is int
            and self.observed_manifest_selection_bytes >= 0
            and type(self.observed_manifest_verification_bytes) is int
            and self.observed_manifest_verification_bytes >= 0
            and type(self.observed_payload_bytes) is int
            and self.observed_payload_bytes >= 0
        )
        self.failure_stage = failure_stage
        self.cleanup_failure_stage = cleanup_failure_stage
        self.cleanup_exception_type = cleanup_exception_type
        self.cleanup_exception_code = cleanup_exception_code
        self.original_exception_type = original_exception_type
        self.original_exception_code = original_exception_code
        self.original_exception_message = original_exception_message
        self.observed_depth = observed_depth
        self.observed_elements = observed_elements
        self.limit_name = limit_name
        if limit_name == "max_manifest_bytes":
            self.limit_value = max_manifest_bytes
        elif limit_name is not None and limits is not None:
            self.limit_value = getattr(limits, limit_name)
        else:
            self.limit_value = None

    @property
    def observed_payload_bytes(self) -> int | None:
        """Return payload bytes actually transferred from the selected store API."""
        return self.observed_bytes

    @property
    def observed_source_bytes(self) -> int | None:
        """Return complete selected-store transfers, or ``None`` when an owner hid usage."""
        selection_bytes = self.observed_manifest_selection_bytes
        verification_bytes = self.observed_manifest_verification_bytes
        payload_bytes = self.observed_payload_bytes
        if (
            not self.source_usage_complete
            or type(selection_bytes) is not int
            or type(verification_bytes) is not int
            or type(payload_bytes) is not int
        ):
            return None
        return selection_bytes + verification_bytes + payload_bytes


def _exact_owner_count(owner: object, name: str) -> int | None:
    """Return only an exact owner-reported byte count, never a guessed zero."""
    try:
        value = getattr(owner, name, None)
    except Exception:
        return None
    return value if type(value) is int and value >= 0 else None


def _exact_owner_value(owner: object, name: str) -> object | None:
    """Read an optional owner field without letting a hostile accessor mask refusal."""
    try:
        return getattr(owner, name, None)
    except Exception:
        return None


def _owner_integrity_verified(owner: object) -> bool:
    """Return true only for an explicit owner integrity receipt."""
    return _exact_owner_value(owner, "payload_integrity_verified") is True


def _exact_owner_usage(owner: object) -> ArtifactStoreReadUsage | None:
    """Return only a sealed immutable usage receipt from the filesystem owner."""
    usage = _exact_owner_value(owner, "usage")
    return usage if _is_artifact_store_read_usage(usage) else None


def _refusal_code(error: Exception, fallback: str) -> str:
    """Preserve a typed refusal code, or name the original exception class."""
    try:
        code = getattr(error, "code", None)
    except Exception:
        code = None
    if type(code) is str and code:
        return code
    if type(error) is FileNotFoundError:
        return "selected_artifact_not_found"
    return fallback


@dataclass(frozen=True, slots=True)
class _CoreOwnerRefusalProjection:
    """Map one typed CAS failure axis into the public Core JSON refusal."""

    code: str
    limit_name: str | None = None
    observed_manifest_bytes: int | None = None
    manifest_size_from_owner: bool = False


def _project_core_owner_refusal(
    error: Exception,
    fallback: str,
) -> _CoreOwnerRefusalProjection:
    """Project the owner's typed member axis without confusing transfer counts."""
    if isinstance(error, ArtifactReadBoundsError):
        member = _exact_owner_value(error, "member")
        if member == "manifest":
            return _CoreOwnerRefusalProjection(
                code="canon_profile_bounded_manifest_bytes_exceeded",
                limit_name="max_manifest_bytes",
                observed_manifest_bytes=_exact_owner_count(error, "observed_bytes"),
                manifest_size_from_owner=True,
            )
        if member == "blob":
            return _CoreOwnerRefusalProjection(
                code="canon_profile_bounded_bytes_exceeded",
                limit_name="max_bytes",
            )
    return _CoreOwnerRefusalProjection(code=_refusal_code(error, fallback))


def _refusal_metadata(error: Exception) -> dict[str, str | None]:
    """Retain the original failure identity beside its chained exception."""
    try:
        error_code = getattr(error, "code", None)
    except Exception:
        error_code = None
    try:
        error_message = str(error)
    except Exception:
        error_message = f"<{type(error).__name__} message unavailable>"
    return {
        "original_exception_type": type(error).__name__,
        "original_exception_code": error_code if type(error_code) is str else None,
        "original_exception_message": error_message,
    }


@dataclass(frozen=True, slots=True)
class CoreJsonManifestBoundedRead:
    """Immutable-byte carrier for one bounded default or selected manifest view."""

    _selected_ref: ArtifactID | ArtifactRef | InputRef = dataclass_field(repr=False)
    raw_manifest_bytes: bytes
    max_manifest_bytes: int
    observed_manifest_bytes: int
    usage: ArtifactStoreReadUsage | None = dataclass_field(repr=False, compare=False)
    _selected_profile_sha256: str | None = dataclass_field(default=None, repr=False, compare=False)
    _seal: _CoreJsonManifestBoundedReadSeal | None = dataclass_field(
        default=None, repr=False, compare=False
    )

    @property
    def observed_source_bytes(self) -> int | None:
        """Return exact selected-store transfers for this metadata-only call."""
        return self.usage.observed_source_bytes if self.usage is not None else None

    @property
    def effective_ref(self) -> ArtifactRef:
        """Return a fresh full reference derived from the selected raw manifest."""
        effective_ref, _manifest, _declaration = _verified_core_manifest_bounded_read(self)
        return effective_ref

    @property
    def manifest(self) -> ArtifactManifest:
        """Return a fresh typed manifest parsed from the retained selected bytes."""
        _effective_ref, manifest, _declaration = _verified_core_manifest_bounded_read(self)
        return manifest

    @property
    def declaration(self) -> CanonicalProfileDeclaration:
        """Return a fresh canonical-profile declaration parsed from selected bytes."""
        _effective_ref, _manifest, declaration = _verified_core_manifest_bounded_read(self)
        return declaration


@dataclass(frozen=True, slots=True)
class _CoreJsonManifestBoundedReadSeal:
    """Bind one metadata carrier to its selected identity and immutable bytes."""

    selected_key: tuple[str, ...]
    raw_manifest_bytes: bytes
    max_manifest_bytes: int
    observed_manifest_bytes: int
    usage: ArtifactStoreReadUsage | None
    allow_profile_absent: bool


@dataclass(frozen=True, slots=True)
class _CoreJsonArtifactBoundedReadSeal:
    """Snapshot the immutable inputs that gave one bounded read its provenance."""

    effective_ref: ArtifactRef
    raw_manifest_bytes: bytes
    raw_payload_bytes: bytes
    limits: CoreJsonReadLimits
    observed_manifest_bytes: int
    observed_manifest_verification_bytes: int
    observed_bytes: int
    observed_payload_size: int
    payload_integrity_verified: bool
    observed_depth: int
    observed_elements: int
    profile_read: CanonicalProfileRead | None = dataclass_field(
        default=None, repr=False, compare=False
    )


@dataclass(frozen=True, slots=True)
class CoreJsonArtifactBoundedRead:
    """One bounded Core JSON byte view bound to its exact selected CAS identity.

    The decoded profile view is rebuilt from retained immutable bytes on access.
    No mutable JSON tree is retained as authoritative state on this carrier.
    """

    effective_ref: ArtifactRef
    manifest: ArtifactManifest
    raw_manifest_bytes: bytes
    raw_payload_bytes: bytes
    limits: CoreJsonReadLimits
    observed_manifest_bytes: int
    observed_manifest_verification_bytes: int
    observed_bytes: int
    observed_payload_size: int
    payload_integrity_verified: bool
    observed_depth: int
    observed_elements: int
    _seal: _CoreJsonArtifactBoundedReadSeal | None = dataclass_field(
        default=None, repr=False, compare=False
    )

    @property
    def observed_manifest_selection_bytes(self) -> int:
        """Return exact selected-manifest bytes transferred by the first bounded read."""
        return self.observed_manifest_bytes

    @property
    def observed_payload_bytes(self) -> int:
        """Return exact selected payload bytes transferred by the owner stream."""
        return self.observed_bytes

    @property
    def observed_source_bytes(self) -> int:
        """Return all selected manifest and payload bytes transferred for this call."""
        return (
            self.observed_manifest_selection_bytes
            + self.observed_manifest_verification_bytes
            + self.observed_payload_bytes
        )

    @property
    def profile_read(self) -> CanonicalProfileRead:
        """Return a fresh, reverified decoded profile view over retained bytes."""
        profile_read, _manifest = _verified_core_json_bounded_view(self)
        return profile_read

    @property
    def value(self) -> Any:
        """Return a fresh declared-profile-conformant Core value."""
        return require_declared_profile(self.profile_read)


class _JsonStructureBoundsScanner:
    """Count JSON lexical nodes and nesting without materializing the JSON tree.

    This scanner is not a decoder. Core's existing decoder remains responsible
    for grammar, typed tags, and canonical profile conformance after this pass.
    """

    _DELIMITERS = frozenset((32, 9, 10, 13, 44, 58, 91, 93, 123, 125, 34))

    def __init__(self) -> None:
        self.in_string = False
        self.escaped = False
        self.in_primitive = False
        self.current_depth = 0
        self.max_depth = 0
        self.elements = 0

    def feed(self, payload: bytes) -> None:
        """Update structural measurements from one actual byte-stream chunk."""
        for byte in payload:
            if self.in_string:
                if self.escaped:
                    self.escaped = False
                elif byte == 92:
                    self.escaped = True
                elif byte == 34:
                    self.in_string = False
                continue

            if self.in_primitive:
                if byte not in self._DELIMITERS:
                    continue
                self.in_primitive = False

            if byte in (32, 9, 10, 13, 44, 58):
                continue
            if byte == 34:
                self.elements += 1
                self.in_string = True
                continue
            if byte in (123, 91):
                self.elements += 1
                self.current_depth += 1
                self.max_depth = max(self.max_depth, self.current_depth)
                continue
            if byte in (125, 93):
                self.current_depth = max(0, self.current_depth - 1)
                continue
            self.elements += 1
            self.in_primitive = True


def _enforce_core_json_read_bounds(
    limits: CoreJsonReadLimits,
    *,
    observed_manifest_bytes: int,
    observed_bytes: int,
    observed_depth: int,
    observed_elements: int,
) -> None:
    """Refuse any observed stream or structure beyond its selected policy."""
    failures = (
        (
            "canon_profile_bounded_manifest_bytes_exceeded",
            "max_manifest_bytes",
            observed_manifest_bytes,
            limits.max_manifest_bytes,
        ),
        (
            "canon_profile_bounded_bytes_exceeded",
            "max_bytes",
            observed_bytes,
            limits.max_bytes,
        ),
        (
            "canon_profile_bounded_depth_exceeded",
            "max_depth",
            observed_depth,
            limits.max_depth,
        ),
        (
            "canon_profile_bounded_elements_exceeded",
            "max_elements",
            observed_elements,
            limits.max_elements,
        ),
    )
    for code, limit_name, observed, maximum in failures:
        if observed > maximum:
            raise CoreJsonReadBoundsRefusalError(
                code,
                limits=limits,
                max_manifest_bytes=limits.max_manifest_bytes,
                observed_manifest_bytes=observed_manifest_bytes,
                observed_bytes=observed_bytes,
                observed_depth=observed_depth,
                observed_elements=observed_elements,
                limit_name=limit_name,
            )


def _core_json_next_payload_chunk_size(
    limits: CoreJsonReadLimits,
    *,
    observed_payload_bytes: int,
) -> int | None:
    """Return the next bounded read size, or ``None`` once the byte budget ends."""
    remaining = limits.max_bytes - observed_payload_bytes
    if remaining <= 0:
        return None
    return min(64 * 1024, remaining)


def artifact_ref_for_manifest(manifest: ArtifactManifest) -> ArtifactRef:
    """Return the exact typed CAS view selected by ``manifest``."""
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )


def _core_spec(profile: CanonInfo) -> CanonSpec:
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


def _core_spec_from_profile(profile: BaseModel) -> object:
    """Adapt the shared profile callback to Core's concrete profile model."""
    if not isinstance(profile, CanonInfo):
        raise TypeError("Core canonicalization requires CanonInfo")
    return _core_spec(profile)


def _encode_core_profiled_value(value: Any, spec: object) -> bytes:
    """Encode once with the selected Core spec during decode-and-compare admission.

    The shared profile reader compares these bytes with the exact selected input.
    Calling the public encoder here would repeat that same comparison by decoding
    the encoded bytes a second time, doubling semantic materialization.
    """
    if not isinstance(spec, CanonSpec):
        raise TypeError("Core canonicalization requires CanonSpec")
    return _encode_core_canonical_bytes_raw(value, spec)


def _require_exact_bytes(value: object, refusal_code: str) -> bytes:
    """Narrow an untyped storage result only after checking its runtime type."""
    if type(value) is not bytes:
        raise CanonicalProfileRefusalError(refusal_code)
    return value


def _read_core_manifest_profile_with_bytes(
    store: object,
    selector: object,
    *,
    manifest_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> tuple[ArtifactManifest, CanonicalProfileDeclaration, bytes]:
    """Read and verify the raw profile before typed manifest admission.

    The optional raw-manifest capability preserves the selected storage view while
    allowing malformed-present CanonInfo to remain distinguishable from absence.
    Absence refuses by default; an explicit candidate-only opt-in never establishes
    historical eligibility. Typed resolution follows strict raw profile parsing.
    """
    raw_reader = getattr(store, "get_raw_manifest_bytes", None)
    manifest_reader = getattr(store, "get_manifest", None)
    if not callable(raw_reader):
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable")
    if not callable(manifest_reader):
        raise CanonicalProfileRefusalError("canon_profile_typed_manifest_unavailable")
    try:
        if manifest_profile_sha256 is None:
            raw_manifest_bytes = raw_reader(selector)
        else:
            raw_manifest_bytes = raw_reader(
                selector,
                manifest_profile_sha256=manifest_profile_sha256,
            )
    except FileNotFoundError:
        raise
    except (AttributeError, NotImplementedError, TypeError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable") from exc
    declaration = parse_canonical_profile(
        raw_manifest_bytes,
        profile_model=CanonInfo,
        allow_profile_absent=allow_profile_absent,
        supported_versions=("0.2.0", "0.3.0"),
    )
    try:
        if manifest_profile_sha256 is None:
            typed_manifest = ArtifactManifest.model_validate(manifest_reader(selector))
        else:
            resolver = getattr(store, "get_manifest_by_profile", None)
            selected_artifact_id = getattr(selector, "artifact_id", selector)
            if callable(resolver):
                typed_manifest = ArtifactManifest.model_validate(
                    resolver(selected_artifact_id, manifest_profile_sha256)
                )
            else:
                typed_manifest = ArtifactManifest.model_validate(manifest_reader(selector))
                if artifact_manifest_profile_sha256(typed_manifest) != manifest_profile_sha256:
                    raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
        raw_typed_manifest = ArtifactManifest.model_validate_json(raw_manifest_bytes)
    except FileNotFoundError:
        raise
    except CanonicalProfileRefusalError:
        raise
    except (TypeError, ValidationError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_invalid") from exc
    if raw_typed_manifest != typed_manifest:
        raise CanonicalProfileRefusalError("canon_profile_selected_manifest_changed")
    if isinstance(selector, ArtifactRef) and (
        selector.artifact_id != typed_manifest.artifact_id
        or selector.kind != typed_manifest.kind
        or selector.media_type != typed_manifest.media_type
        or (
            selector.manifest_profile_sha256 is not None
            and selector.manifest_profile_sha256 != artifact_manifest_profile_sha256(typed_manifest)
        )
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    if (
        manifest_profile_sha256 is not None
        and artifact_manifest_profile_sha256(typed_manifest) != manifest_profile_sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    return typed_manifest, declaration, raw_manifest_bytes


def read_core_manifest_profile(
    store: object,
    selector: object,
    *,
    manifest_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> tuple[ArtifactManifest, CanonicalProfileDeclaration]:
    """Read and verify the raw profile before typed manifest admission.

    Profile absence refuses by default. An explicit absence opt-in remains
    candidate-only and never establishes historical eligibility.
    """
    typed_manifest, declaration, _raw_manifest_bytes = _read_core_manifest_profile_with_bytes(
        store,
        selector,
        manifest_profile_sha256=manifest_profile_sha256,
        allow_profile_absent=allow_profile_absent,
    )
    return typed_manifest, declaration


def _read_core_manifest_profile_bounded(
    store: CoreJSONArtifactBoundedManifestReceiptReader,
    selected_ref: ArtifactRef | ArtifactID,
    *,
    max_manifest_bytes: int,
    selected_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
    limits: CoreJsonReadLimits | None = None,
) -> CoreJsonManifestBoundedRead:
    """Read default or exact selected manifest and require the owner receipt."""
    if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
        raise ValueError("max_manifest_bytes must be a positive integer")
    if type(selected_ref) is ArtifactRef:
        selected_ref = _revalidate_core_artifact_ref(selected_ref)
        if (
            selected_profile_sha256 is not None
            and selected_profile_sha256 != selected_ref.manifest_profile_sha256
        ):
            raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
        owner_selector: ArtifactID | ArtifactRef = selected_ref
        owner_profile = None
        normalized_profile = selected_ref.manifest_profile_sha256
    elif type(selected_ref) is ArtifactID:
        selected_ref = ArtifactID.model_validate(selected_ref.root)
        if selected_profile_sha256 is not None and (
            type(selected_profile_sha256) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", selected_profile_sha256) is None
        ):
            raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
        owner_selector = selected_ref
        owner_profile = selected_profile_sha256
        normalized_profile = selected_profile_sha256
    else:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")
    try:
        bounded_manifest_reader = getattr(store, "read_raw_manifest_bytes_bounded", None)
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            _refusal_code(exc, "canon_profile_bounded_manifest_unavailable"),
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=0,
            observed_manifest_verification_bytes=0,
            source_usage_complete=True,
            failure_stage="selected_manifest_reader_preflight",
            **_refusal_metadata(exc),
        ) from exc
    if not callable(bounded_manifest_reader):
        exc = NotImplementedError("filesystem_owner_usage_receipt_unavailable")
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_unavailable",
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=0,
            observed_manifest_verification_bytes=0,
            source_usage_complete=True,
            failure_stage="selected_manifest_reader_preflight",
            **_refusal_metadata(exc),
        ) from exc

    try:
        if owner_profile is None:
            result = bounded_manifest_reader(owner_selector, max_manifest_bytes=max_manifest_bytes)
        else:
            result = bounded_manifest_reader(
                owner_selector,
                max_manifest_bytes=max_manifest_bytes,
                manifest_profile_sha256=owner_profile,
            )
    except ArtifactBoundedManifestReadError as exc:
        usage = exc.usage if _is_artifact_store_read_usage(exc.usage) else None
        original = exc.original_exception
        selection_bytes = usage.observed_manifest_selection_bytes if usage is not None else None
        verification_bytes = (
            usage.observed_manifest_verification_bytes if usage is not None else None
        )
        payload_bytes = usage.observed_payload_bytes if usage is not None else None
        projection = _project_core_owner_refusal(
            original,
            "canon_profile_bounded_manifest_unavailable",
        )
        raise CoreJsonReadBoundsRefusalError(
            projection.code,
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=projection.observed_manifest_bytes,
            observed_bytes=payload_bytes,
            observed_depth=0,
            observed_elements=0,
            limit_name=projection.limit_name,
            observed_manifest_selection_bytes=selection_bytes,
            observed_manifest_verification_bytes=verification_bytes,
            payload_integrity_verified=(
                usage.payload_integrity_verified if usage is not None else False
            ),
            source_usage_complete=(usage is not None and usage.observed_source_bytes is not None),
            failure_stage=(
                usage.failure_stage if usage is not None else "selected_manifest_usage_unknown"
            ),
            cleanup_failure_stage=(usage.cleanup_failure_stage if usage is not None else None),
            cleanup_exception_type=(usage.cleanup_exception_type if usage is not None else None),
            cleanup_exception_code=(usage.cleanup_exception_code if usage is not None else None),
            **_refusal_metadata(original),
        ) from original
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            _refusal_code(exc, "canon_profile_bounded_manifest_unavailable"),
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=None,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=None,
            observed_manifest_verification_bytes=0,
            source_usage_complete=False,
            failure_stage="selected_manifest_usage_unknown",
            **_refusal_metadata(exc),
        ) from exc

    if type(result) is not ArtifactBoundedManifestRead:
        exc = TypeError("bounded_manifest_reader_must_return_owner_receipt")
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_invalid",
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=None,
            observed_bytes=None,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=None,
            observed_manifest_verification_bytes=None,
            source_usage_complete=False,
            failure_stage="selected_manifest_result_validation",
            **_refusal_metadata(exc),
        ) from exc
    usage = result.usage if _is_artifact_store_read_usage(result.usage) else None
    raw_manifest_bytes = result.raw_manifest_bytes
    if (
        type(raw_manifest_bytes) is not bytes
        or usage is None
        or usage.observed_manifest_selection_bytes != len(raw_manifest_bytes)
        or usage.observed_manifest_verification_bytes != 0
        or usage.observed_payload_bytes != 0
        or usage.observed_payload_size is not None
        or usage.payload_integrity_verified is not False
        or usage.observed_source_bytes is None
    ):
        exc = TypeError("bounded_manifest_owner_receipt_mismatch")
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_invalid",
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=(
                len(raw_manifest_bytes) if type(raw_manifest_bytes) is bytes else None
            ),
            observed_bytes=(usage.observed_payload_bytes if usage is not None else None),
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=(
                usage.observed_manifest_selection_bytes if usage is not None else None
            ),
            observed_manifest_verification_bytes=(
                usage.observed_manifest_verification_bytes if usage is not None else None
            ),
            payload_integrity_verified=False,
            source_usage_complete=False,
            failure_stage="selected_manifest_result_validation",
            **_refusal_metadata(exc),
        ) from exc

    try:
        return _core_manifest_profile_from_bytes(
            raw_manifest_bytes,
            selected_ref,
            max_manifest_bytes=max_manifest_bytes,
            limits=limits,
            usage=usage,
            selected_profile_sha256=normalized_profile,
            allow_profile_absent=allow_profile_absent,
        )
    except CoreJsonReadBoundsRefusalError:
        raise
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            _refusal_code(exc, "canon_profile_bounded_manifest_invalid"),
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=len(raw_manifest_bytes),
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=usage.observed_manifest_selection_bytes,
            observed_manifest_verification_bytes=usage.observed_manifest_verification_bytes,
            source_usage_complete=usage.observed_source_bytes is not None,
            failure_stage="selected_manifest_profile_validation",
            **_refusal_metadata(exc),
        ) from exc


def _revalidate_core_input_ref(input_ref: InputRef) -> InputRef:
    """Revalidate the caller's raw input edge without inferring omitted fields."""
    from polisyos.core.artifacts.ids import ArtifactID

    if type(input_ref) is not InputRef:
        raise CanonicalProfileRefusalError("canon_profile_bounded_input_selection_required")
    fields = dict(input_ref.__dict__)
    if set(fields) != {"artifact_id", "role", "manifest_profile_sha256"}:
        raise CanonicalProfileRefusalError("canon_profile_bounded_input_invalid")
    raw_artifact_id = fields.get("artifact_id")
    if isinstance(raw_artifact_id, ArtifactID):
        raw_artifact_id = raw_artifact_id.root
    try:
        artifact_id = ArtifactID.model_validate(raw_artifact_id)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_bounded_input_invalid") from exc
    role = fields.get("role")
    profile = fields.get("manifest_profile_sha256")
    if type(role) is not str:
        raise CanonicalProfileRefusalError("canon_profile_bounded_input_invalid")
    if profile is None:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")
    if type(profile) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", profile) is None:
        raise CanonicalProfileRefusalError("canon_profile_bounded_input_invalid")
    try:
        return InputRef.model_validate(
            {
                "artifact_id": artifact_id,
                "role": role,
                "manifest_profile_sha256": profile,
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_bounded_input_invalid") from exc


def _read_core_input_manifest_profile_bounded(
    store: CoreJSONArtifactBoundedInputManifestReceiptReader,
    input_ref: InputRef,
    *,
    max_manifest_bytes: int,
) -> CoreJsonManifestBoundedRead:
    """Resolve one input edge with a typed filesystem-owner transfer receipt."""
    if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
        raise ValueError("max_manifest_bytes must be a positive integer")
    selected_input = _revalidate_core_input_ref(input_ref)
    try:
        bounded_reader = getattr(store, "read_raw_manifest_bytes_bounded_for_input", None)
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            _refusal_code(exc, "canon_profile_bounded_manifest_unavailable"),
            limits=None,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=0,
            observed_manifest_verification_bytes=0,
            source_usage_complete=True,
            failure_stage="selected_manifest_reader_preflight",
            **_refusal_metadata(exc),
        ) from exc
    if not callable(bounded_reader):
        exc = NotImplementedError("filesystem_owner_usage_receipt_unavailable")
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_unavailable",
            limits=None,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=0,
            observed_manifest_verification_bytes=0,
            source_usage_complete=True,
            failure_stage="selected_manifest_reader_preflight",
            **_refusal_metadata(exc),
        ) from exc
    try:
        result = bounded_reader(selected_input, max_manifest_bytes=max_manifest_bytes)
    except ArtifactBoundedManifestReadError as exc:
        usage = exc.usage if _is_artifact_store_read_usage(exc.usage) else None
        original = exc.original_exception
        selection_bytes = usage.observed_manifest_selection_bytes if usage is not None else None
        verification_bytes = (
            usage.observed_manifest_verification_bytes if usage is not None else None
        )
        payload_bytes = usage.observed_payload_bytes if usage is not None else None
        projection = _project_core_owner_refusal(
            original,
            "canon_profile_bounded_manifest_unavailable",
        )
        raise CoreJsonReadBoundsRefusalError(
            projection.code,
            limits=None,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=projection.observed_manifest_bytes,
            observed_bytes=payload_bytes,
            observed_depth=0,
            observed_elements=0,
            limit_name=projection.limit_name,
            observed_manifest_selection_bytes=selection_bytes,
            observed_manifest_verification_bytes=verification_bytes,
            payload_integrity_verified=(
                usage.payload_integrity_verified if usage is not None else False
            ),
            source_usage_complete=(usage is not None and usage.observed_source_bytes is not None),
            failure_stage=(
                usage.failure_stage if usage is not None else "selected_manifest_usage_unknown"
            ),
            cleanup_failure_stage=(usage.cleanup_failure_stage if usage is not None else None),
            cleanup_exception_type=(usage.cleanup_exception_type if usage is not None else None),
            cleanup_exception_code=(usage.cleanup_exception_code if usage is not None else None),
            **_refusal_metadata(original),
        ) from original
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            _refusal_code(exc, "canon_profile_bounded_manifest_unavailable"),
            limits=None,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=None,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=None,
            observed_manifest_verification_bytes=0,
            source_usage_complete=False,
            failure_stage="selected_manifest_usage_unknown",
            **_refusal_metadata(exc),
        ) from exc
    if type(result) is not ArtifactBoundedManifestRead:
        exc = TypeError("bounded_manifest_reader_must_return_owner_receipt")
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_invalid",
            limits=None,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=None,
            observed_bytes=None,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=None,
            observed_manifest_verification_bytes=None,
            source_usage_complete=False,
            failure_stage="selected_manifest_result_validation",
            **_refusal_metadata(exc),
        ) from exc
    usage = result.usage if _is_artifact_store_read_usage(result.usage) else None
    raw_manifest_bytes = result.raw_manifest_bytes
    if (
        type(raw_manifest_bytes) is not bytes
        or usage is None
        or usage.observed_manifest_selection_bytes != len(raw_manifest_bytes)
        or usage.observed_manifest_verification_bytes != 0
        or usage.observed_payload_bytes != 0
        or usage.observed_payload_size is not None
        or usage.payload_integrity_verified is not False
        or usage.observed_source_bytes is None
    ):
        exc = TypeError("bounded_manifest_owner_receipt_mismatch")
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_invalid",
            limits=None,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=(
                len(raw_manifest_bytes) if type(raw_manifest_bytes) is bytes else None
            ),
            observed_bytes=(usage.observed_payload_bytes if usage is not None else None),
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=(
                usage.observed_manifest_selection_bytes if usage is not None else None
            ),
            observed_manifest_verification_bytes=(
                usage.observed_manifest_verification_bytes if usage is not None else None
            ),
            source_usage_complete=False,
            failure_stage="selected_manifest_result_validation",
            **_refusal_metadata(exc),
        ) from exc
    try:
        return _core_manifest_profile_from_bytes(
            raw_manifest_bytes,
            selected_input,
            max_manifest_bytes=max_manifest_bytes,
            usage=usage,
        )
    except CoreJsonReadBoundsRefusalError:
        raise
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            _refusal_code(exc, "canon_profile_bounded_manifest_invalid"),
            limits=None,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=len(raw_manifest_bytes),
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            observed_manifest_selection_bytes=usage.observed_manifest_selection_bytes,
            observed_manifest_verification_bytes=usage.observed_manifest_verification_bytes,
            source_usage_complete=usage.observed_source_bytes is not None,
            failure_stage="selected_manifest_profile_validation",
            **_refusal_metadata(exc),
        ) from exc


def _revalidate_core_artifact_ref(selected_ref: ArtifactRef) -> ArtifactRef:
    """Revalidate a full typed ref from raw fields without losing kind/media."""
    from polisyos.core.artifacts.ids import ArtifactID

    if type(selected_ref) is not ArtifactRef:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")
    fields = dict(selected_ref.__dict__)
    if set(fields) != {"artifact_id", "kind", "media_type", "manifest_profile_sha256"}:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
    if type(fields.get("kind")) is not str or type(fields.get("media_type")) is not str:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
    raw_artifact_id = fields.get("artifact_id")
    if isinstance(raw_artifact_id, ArtifactID):
        raw_artifact_id = raw_artifact_id.root
    try:
        fields["artifact_id"] = ArtifactID.model_validate(raw_artifact_id)
        selected = ArtifactRef.model_validate(fields)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid") from exc
    if type(selected.manifest_profile_sha256) is not str or not selected.manifest_profile_sha256:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")
    return selected


def _core_manifest_selector_key(
    selected_ref: ArtifactRef | InputRef | ArtifactID,
    *,
    selected_profile_sha256: str | None = None,
) -> tuple[str, ...]:
    """Return immutable identity fields for one exact bounded manifest selector."""
    if type(selected_ref) is ArtifactRef:
        selected = _revalidate_core_artifact_ref(selected_ref)
        if (
            selected_profile_sha256 is not None
            and selected_profile_sha256 != selected.manifest_profile_sha256
        ):
            raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
        return (
            "artifact",
            str(selected.artifact_id),
            selected.kind,
            selected.media_type,
            selected.manifest_profile_sha256,
        )
    if type(selected_ref) is InputRef:
        selected = _revalidate_core_input_ref(selected_ref)
        if (
            selected_profile_sha256 is not None
            and selected_profile_sha256 != selected.manifest_profile_sha256
        ):
            raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
        return ("input", str(selected.artifact_id), selected.manifest_profile_sha256)
    if type(selected_ref) is ArtifactID:
        selected = ArtifactID.model_validate(selected_ref.root)
        if selected_profile_sha256 is not None and (
            type(selected_profile_sha256) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", selected_profile_sha256) is None
        ):
            raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
        return ("artifact_id", str(selected), selected_profile_sha256 or "default")
    raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")


def _parse_core_manifest_profile_components(
    raw_manifest_bytes: bytes,
    selected_ref: ArtifactRef | InputRef | ArtifactID,
    *,
    max_manifest_bytes: int,
    limits: CoreJsonReadLimits | None = None,
    selected_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> tuple[ArtifactRef, ArtifactManifest, CanonicalProfileDeclaration]:
    """Resolve typed/profile components from one retained bounded byte string."""
    if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
        raise ValueError("max_manifest_bytes must be a positive integer")
    if type(selected_ref) is ArtifactRef:
        selected_ref = _revalidate_core_artifact_ref(selected_ref)
        selected_id = selected_ref.artifact_id
        selected_profile = selected_ref.manifest_profile_sha256
        if selected_profile_sha256 is not None and selected_profile_sha256 != selected_profile:
            raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
    elif type(selected_ref) is InputRef:
        selected_ref = _revalidate_core_input_ref(selected_ref)
        selected_id = selected_ref.artifact_id
        selected_profile = selected_ref.manifest_profile_sha256
        if selected_profile_sha256 is not None and selected_profile_sha256 != selected_profile:
            raise CanonicalProfileRefusalError("canon_profile_bounded_selection_invalid")
    elif type(selected_ref) is ArtifactID:
        selected_id = ArtifactID.model_validate(selected_ref.root)
        selected_profile = selected_profile_sha256
    else:
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")
    if selected_profile is not None and (
        type(selected_profile) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", selected_profile) is None
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")
    if type(raw_manifest_bytes) is not bytes:
        raise CanonicalProfileRefusalError("canon_profile_bounded_manifest_invalid")
    observed_manifest_bytes = len(raw_manifest_bytes)
    if observed_manifest_bytes > max_manifest_bytes:
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_bytes_exceeded",
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=observed_manifest_bytes,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            limit_name="max_manifest_bytes",
            observed_manifest_selection_bytes=observed_manifest_bytes,
            observed_manifest_verification_bytes=0,
            source_usage_complete=True,
        )
    try:
        manifest = ArtifactManifest.model_validate_json(raw_manifest_bytes)
        declaration = parse_canonical_profile(
            raw_manifest_bytes,
            profile_model=CanonInfo,
            allow_profile_absent=allow_profile_absent,
            supported_versions=("0.2.0", "0.3.0"),
        )
    except CanonicalProfileRefusalError:
        raise
    except (TypeError, ValidationError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_bounded_manifest_invalid") from exc
    effective_ref = artifact_ref_for_manifest(manifest)
    if manifest.integrity.sha256 != selected_id.hex:
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    if (
        selected_profile is not None
        and artifact_manifest_profile_sha256(manifest) != selected_profile
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    if type(selected_ref) is ArtifactRef and effective_ref != selected_ref:
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    return effective_ref, manifest, declaration


def _core_manifest_profile_from_bytes(
    raw_manifest_bytes: bytes,
    selected_ref: ArtifactRef | InputRef | ArtifactID,
    *,
    max_manifest_bytes: int,
    limits: CoreJsonReadLimits | None = None,
    usage: ArtifactStoreReadUsage | None = None,
    selected_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> CoreJsonManifestBoundedRead:
    """Create a sealed metadata carrier from one bounded raw byte sequence."""
    _parse_core_manifest_profile_components(
        raw_manifest_bytes,
        selected_ref,
        max_manifest_bytes=max_manifest_bytes,
        limits=limits,
        selected_profile_sha256=selected_profile_sha256,
        allow_profile_absent=allow_profile_absent,
    )
    if type(selected_ref) is ArtifactRef:
        normalized: ArtifactID | ArtifactRef | InputRef = _revalidate_core_artifact_ref(
            selected_ref
        )
    elif type(selected_ref) is InputRef:
        normalized = _revalidate_core_input_ref(selected_ref)
    else:
        normalized = ArtifactID.model_validate(selected_ref.root)
    observed = len(raw_manifest_bytes)
    result = CoreJsonManifestBoundedRead(
        _selected_ref=normalized,
        raw_manifest_bytes=raw_manifest_bytes,
        max_manifest_bytes=max_manifest_bytes,
        observed_manifest_bytes=observed,
        usage=usage,
        _selected_profile_sha256=selected_profile_sha256,
    )
    object.__setattr__(
        result,
        "_seal",
        _CoreJsonManifestBoundedReadSeal(
            selected_key=_core_manifest_selector_key(
                normalized, selected_profile_sha256=selected_profile_sha256
            ),
            raw_manifest_bytes=raw_manifest_bytes,
            max_manifest_bytes=max_manifest_bytes,
            observed_manifest_bytes=observed,
            usage=usage,
            allow_profile_absent=allow_profile_absent,
        ),
    )
    return result


def _verified_core_manifest_bounded_read(
    bounded_read: CoreJsonManifestBoundedRead,
) -> tuple[ArtifactRef, ArtifactManifest, CanonicalProfileDeclaration]:
    """Rebind a metadata carrier to its sealed selector and retained raw bytes."""
    if type(bounded_read) is not CoreJsonManifestBoundedRead:
        raise CanonicalProfileRefusalError("canon_profile_bounded_manifest_carrier_unverified")
    seal = bounded_read._seal
    if type(seal) is not _CoreJsonManifestBoundedReadSeal:
        raise CanonicalProfileRefusalError("canon_profile_bounded_manifest_carrier_unverified")
    if (
        type(bounded_read.raw_manifest_bytes) is not bytes
        or type(bounded_read.max_manifest_bytes) is not int
        or type(bounded_read.observed_manifest_bytes) is not int
        or bounded_read.raw_manifest_bytes != seal.raw_manifest_bytes
        or bounded_read.max_manifest_bytes != seal.max_manifest_bytes
        or bounded_read.observed_manifest_bytes != seal.observed_manifest_bytes
        or bounded_read.usage != seal.usage
        or (
            bounded_read._selected_profile_sha256 is not None
            and type(bounded_read._selected_profile_sha256) is not str
        )
        or type(seal.allow_profile_absent) is not bool
        or (
            bounded_read.usage is not None and not _is_artifact_store_read_usage(bounded_read.usage)
        )
        or bounded_read.observed_manifest_bytes != len(bounded_read.raw_manifest_bytes)
        or bounded_read.max_manifest_bytes < 1
        or bounded_read.observed_manifest_bytes > bounded_read.max_manifest_bytes
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_manifest_carrier_mismatch")
    if (
        _core_manifest_selector_key(
            bounded_read._selected_ref,
            selected_profile_sha256=bounded_read._selected_profile_sha256,
        )
        != seal.selected_key
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_manifest_carrier_mismatch")
    return _parse_core_manifest_profile_components(
        bounded_read.raw_manifest_bytes,
        bounded_read._selected_ref,
        max_manifest_bytes=bounded_read.max_manifest_bytes,
        selected_profile_sha256=bounded_read._selected_profile_sha256,
        allow_profile_absent=seal.allow_profile_absent,
    )


def read_core_manifest_profile_bounded(
    store: CoreJSONArtifactBoundedManifestReceiptReader,
    selected_ref: ArtifactRef | ArtifactID,
    *,
    max_manifest_bytes: int,
    manifest_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> CoreJsonManifestBoundedRead:
    """Read default or exact selected manifest metadata under its byte limit.

    An ArtifactID without a profile selects the owner's default view. Supplying a
    profile selects that exact sidecar without default fallback. ArtifactRef retains
    its complete exact selection. Profile absence is refused unless explicitly
    allowed for candidate-only metadata inspection.
    """
    guarded = _guarded_canonical_reader(store)
    if guarded is not None:
        return guarded._guarded_manifest_read(
            selected_ref,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
            allow_profile_absent=allow_profile_absent,
        )
    return _read_core_manifest_profile_bounded(
        store,
        selected_ref,
        max_manifest_bytes=max_manifest_bytes,
        selected_profile_sha256=manifest_profile_sha256,
        allow_profile_absent=allow_profile_absent,
    )


def read_core_input_manifest_profile_bounded(
    store: CoreJSONArtifactBoundedInputManifestReceiptReader,
    input_ref: InputRef,
    *,
    max_manifest_bytes: int,
) -> CoreJsonManifestBoundedRead:
    """Resolve an exact profile-qualified lineage edge under a metadata byte bound.

    The returned effective reference is derived only from the bounded parsed
    manifest. InputRef's absent kind and media type are never synthesized.
    """
    guarded = _guarded_canonical_reader(store)
    if guarded is not None:
        return guarded._guarded_input_manifest_read(
            input_ref, max_manifest_bytes=max_manifest_bytes
        )
    return _read_core_input_manifest_profile_bounded(
        store,
        input_ref,
        max_manifest_bytes=max_manifest_bytes,
    )


def decode_core_json_payload(
    raw_manifest_bytes: bytes,
    raw_payload_bytes: bytes,
    *,
    allow_profile_absent: bool = False,
) -> CanonicalProfileRead:
    """Decode exact signed/selected bytes against a strictly parsed Core profile.

    Profile absence refuses by default. An explicit absence opt-in yields an
    unqualified candidate read whose semantic value cannot enter authority use.
    """
    declaration = parse_canonical_profile(
        raw_manifest_bytes,
        profile_model=CanonInfo,
        allow_profile_absent=allow_profile_absent,
        supported_versions=("0.2.0", "0.3.0"),
    )
    read = _decode_core_payload_under_declaration(raw_payload_bytes, declaration)
    return read


def _decode_core_payload_under_declaration(
    raw_payload_bytes: bytes,
    declaration: CanonicalProfileDeclaration,
) -> CanonicalProfileRead:
    """Use the canonical shared profile bridge and Core's existing tagged decoder."""
    version = (
        declaration.profile.version
        if declaration.status == "declared" and isinstance(declaration.profile, CanonInfo)
        else "0.2.0"
    )
    reader_policy_id = CORE_V3_TAG_POLICY_ID if version == "0.3.0" else CORE_TAG_POLICY_ID
    return decode_profiled_canonical_bytes(
        raw_payload_bytes,
        declaration,
        profile_model=CanonInfo,
        make_spec=_core_spec_from_profile,
        decode=lambda raw, max_depth: from_canonical_bytes(
            raw, max_depth=max_depth, version=version
        ),
        encode=_encode_core_profiled_value,
        reader_policy_id=reader_policy_id,
    )


class _CoreJsonBoundedReadAbortError(Exception):
    """Stop a bounded owner stream without its normal drain-and-verify finish."""

    def __init__(
        self,
        code: str,
        *,
        payload_usage_unknown: bool = False,
        original_exception: Exception | None = None,
    ) -> None:
        self.code = code
        self.payload_usage_unknown = payload_usage_unknown
        self.original_exception = original_exception
        super().__init__(code)


def read_core_json_artifact_bounded(
    store: CoreJSONArtifactBoundedMemberReader,
    selected_ref: ArtifactRef,
    *,
    limits: CoreJsonReadLimits,
    manifest_read: CoreJsonManifestBoundedRead | None = None,
) -> CoreJsonArtifactBoundedRead:
    """Stream one exact selected Core JSON view without unbounded refusal drains.

    This strict route requires a size-known bounded owner stream. It never
    falls back to legacy ``open_member`` because that context drains and hashes
    unread bytes on a normal exit.
    """
    if type(limits) is not CoreJsonReadLimits:
        raise TypeError("core_json_read_limits_required")
    if (
        type(selected_ref) is not ArtifactRef
        or type(selected_ref.manifest_profile_sha256) is not str
        or not selected_ref.manifest_profile_sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_selection_required")

    guarded = _guarded_canonical_reader(store)
    if guarded is not None:
        return guarded._guarded_json_read(selected_ref, limits=limits, manifest_read=manifest_read)
    if manifest_read is None:
        manifest_read = _read_core_manifest_profile_bounded(
            store,
            selected_ref,
            max_manifest_bytes=limits.max_manifest_bytes,
            limits=limits,
        )
    try:
        typed_manifest = manifest_read.manifest
        declaration = manifest_read.declaration
        raw_manifest_bytes = manifest_read.raw_manifest_bytes
        effective_ref = manifest_read.effective_ref
        if effective_ref != selected_ref:
            raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    except CoreJsonReadBoundsRefusalError:
        raise
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            _refusal_code(exc, "canon_profile_bounded_manifest_validation_refused"),
            limits=limits,
            max_manifest_bytes=limits.max_manifest_bytes,
            observed_manifest_bytes=manifest_read.observed_manifest_bytes,
            observed_manifest_selection_bytes=manifest_read.observed_source_bytes,
            observed_manifest_verification_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            source_usage_complete=True,
            failure_stage="selected_manifest_local_validation",
            **_refusal_metadata(exc),
        ) from exc
    if declaration.status != "declared" or declaration.profile is None:
        raise CanonicalProfileRefusalError("canon_profile_not_verified")
    observed_payload_bytes = 0
    source: Any | None = None
    member_attempt: object | None = None
    member_open_invoked = False
    try:
        bounded_member_open = getattr(store, "open_member_bounded", None)
    except Exception as exc:
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_stream_unavailable",
            limits=limits,
            max_manifest_bytes=limits.max_manifest_bytes,
            observed_manifest_bytes=manifest_read.observed_manifest_bytes,
            observed_manifest_selection_bytes=manifest_read.observed_source_bytes,
            observed_manifest_verification_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            source_usage_complete=True,
            failure_stage="bounded_member_open_preflight",
            **_refusal_metadata(exc),
        ) from exc
    if not callable(bounded_member_open):
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_stream_unavailable",
            limits=limits,
            max_manifest_bytes=limits.max_manifest_bytes,
            observed_manifest_bytes=manifest_read.observed_manifest_bytes,
            observed_manifest_selection_bytes=manifest_read.observed_source_bytes,
            observed_manifest_verification_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            source_usage_complete=True,
            failure_stage="bounded_member_open_preflight",
        )
    try:
        member_open_invoked = True
        member_context = bounded_member_open(
            selected_ref,
            "blob",
            max_manifest_bytes=limits.max_manifest_bytes,
            expected_manifest_sha256=hashlib.sha256(raw_manifest_bytes).hexdigest(),
            max_member_bytes=limits.max_bytes,
        )
        member_attempt = member_context
        payload = bytearray()
        digest = hashlib.sha256()
        scanner = _JsonStructureBoundsScanner()
        with member_context as source:
            while True:
                chunk_size = _core_json_next_payload_chunk_size(
                    limits,
                    observed_payload_bytes=observed_payload_bytes,
                )
                if chunk_size is None:
                    if observed_payload_bytes < source.member_size_bytes:
                        bounds_error = CoreJsonReadBoundsRefusalError(
                            "canon_profile_bounded_bytes_exceeded",
                            limits=limits,
                            max_manifest_bytes=limits.max_manifest_bytes,
                            observed_manifest_bytes=manifest_read.observed_manifest_bytes,
                            observed_manifest_selection_bytes=manifest_read.observed_source_bytes,
                            observed_manifest_verification_bytes=_exact_owner_count(
                                source, "observed_manifest_verification_bytes"
                            ),
                            observed_bytes=observed_payload_bytes,
                            observed_payload_size=_exact_owner_count(source, "member_size_bytes"),
                            observed_depth=scanner.max_depth,
                            observed_elements=scanner.elements,
                            limit_name="max_bytes",
                            source_usage_complete=False,
                            failure_stage="bounded_payload_read",
                        )
                        raise _CoreJsonBoundedReadAbortError(
                            bounds_error.code,
                            original_exception=bounds_error,
                        ) from bounds_error
                    break
                try:
                    chunk = source.read(chunk_size)
                except (ArtifactReadBoundsError, ArtifactMemberReadIntegrityError):
                    raise
                except Exception as read_exc:
                    raise _CoreJsonBoundedReadAbortError(
                        _refusal_code(
                            read_exc,
                            "canon_profile_bounded_stream_read_refused",
                        ),
                        payload_usage_unknown=False,
                        original_exception=read_exc,
                    ) from read_exc
                if type(chunk) is not bytes:
                    stream_error = TypeError("bounded_member_stream_must_return_bytes")
                    raise _CoreJsonBoundedReadAbortError(
                        "canon_profile_bounded_stream_invalid",
                        payload_usage_unknown=True,
                        original_exception=stream_error,
                    ) from stream_error
                if not chunk:
                    break
                observed_payload_bytes += len(chunk)
                digest.update(chunk)
                try:
                    _enforce_core_json_read_bounds(
                        limits,
                        observed_manifest_bytes=manifest_read.observed_manifest_bytes,
                        observed_bytes=observed_payload_bytes,
                        observed_depth=scanner.max_depth,
                        observed_elements=scanner.elements,
                    )
                    scanner.feed(chunk)
                    _enforce_core_json_read_bounds(
                        limits,
                        observed_manifest_bytes=manifest_read.observed_manifest_bytes,
                        observed_bytes=observed_payload_bytes,
                        observed_depth=scanner.max_depth,
                        observed_elements=scanner.elements,
                    )
                except CoreJsonReadBoundsRefusalError as exc:
                    raise _CoreJsonBoundedReadAbortError(
                        exc.code,
                        original_exception=exc,
                    ) from exc
                payload.extend(chunk)

        if source is None or not _owner_integrity_verified(source):
            raise CanonicalProfileRefusalError("canon_profile_member_integrity_unverified")
        receipt = source.receipt
        if (
            receipt.sha256 != typed_manifest.integrity.sha256
            or receipt.byte_size != typed_manifest.byte_size
            or source.member_size_bytes != typed_manifest.byte_size
            or observed_payload_bytes != source.member_size_bytes
            or digest.hexdigest() != typed_manifest.integrity.sha256
        ):
            raise CanonicalProfileRefusalError("canon_profile_selected_payload_identity_mismatch")
        raw_payload_bytes = bytes(payload)
        profile_read = _decode_core_payload_under_declaration(raw_payload_bytes, declaration)
        profile_read = _bind_selected_artifact_identity(
            profile_read,
            artifact_id=str(typed_manifest.artifact_id),
            manifest_profile_sha256=artifact_manifest_profile_sha256(typed_manifest),
        )
        require_declared_profile(profile_read)
    except Exception as exc:
        owner_usage = _exact_owner_usage(member_attempt) if member_attempt is not None else None
        if owner_usage is not None:
            verification_bytes = owner_usage.observed_manifest_verification_bytes
            payload_bytes = owner_usage.observed_payload_bytes
            payload_size = owner_usage.observed_payload_size
            payload_verified = owner_usage.payload_integrity_verified
            failure_stage = owner_usage.failure_stage or "bounded_payload_validation"
            cleanup_failure_stage = owner_usage.cleanup_failure_stage
            cleanup_exception_type = owner_usage.cleanup_exception_type
            cleanup_exception_code = owner_usage.cleanup_exception_code
        elif member_open_invoked:
            verification_bytes = None
            payload_bytes = None
            payload_size = None
            payload_verified = False
            failure_stage = "bounded_member_usage_unknown"
            cleanup_failure_stage = None
            cleanup_exception_type = None
            cleanup_exception_code = None
        else:
            verification_bytes = 0
            payload_bytes = 0
            payload_size = None
            payload_verified = False
            failure_stage = "bounded_member_open_preflight"
            cleanup_failure_stage = None
            cleanup_exception_type = None
            cleanup_exception_code = None
        original = (
            exc.original_exception
            if isinstance(exc, _CoreJsonBoundedReadAbortError)
            and exc.original_exception is not None
            else exc
        )
        projection = _project_core_owner_refusal(
            original,
            "canon_profile_bounded_payload_validation_refused"
            if payload_verified
            else "canon_profile_bounded_stream_unavailable",
        )
        refusal_code = (
            exc.code if isinstance(exc, _CoreJsonBoundedReadAbortError) else projection.code
        )
        limit_name = projection.limit_name or {
            "canon_profile_bounded_bytes_exceeded": "max_bytes",
            "canon_profile_bounded_depth_exceeded": "max_depth",
            "canon_profile_bounded_elements_exceeded": "max_elements",
        }.get(refusal_code)
        observed_manifest_bytes = (
            projection.observed_manifest_bytes
            if projection.manifest_size_from_owner
            else manifest_read.observed_manifest_bytes
        )
        raise CoreJsonReadBoundsRefusalError(
            refusal_code,
            limits=limits,
            max_manifest_bytes=limits.max_manifest_bytes,
            observed_manifest_bytes=observed_manifest_bytes,
            observed_manifest_selection_bytes=manifest_read.observed_source_bytes,
            observed_manifest_verification_bytes=verification_bytes,
            observed_bytes=payload_bytes,
            observed_payload_size=payload_size,
            observed_depth=(scanner.max_depth if "scanner" in locals() else 0),
            observed_elements=(scanner.elements if "scanner" in locals() else 0),
            payload_integrity_verified=payload_verified,
            source_usage_complete=(
                type(manifest_read.observed_source_bytes) is int
                and type(verification_bytes) is int
                and type(payload_bytes) is int
            ),
            failure_stage=failure_stage,
            cleanup_failure_stage=cleanup_failure_stage,
            cleanup_exception_type=cleanup_exception_type,
            cleanup_exception_code=cleanup_exception_code,
            limit_name=limit_name,
            **_refusal_metadata(original),
        ) from original

    owner_usage = _exact_owner_usage(member_attempt)
    observed_manifest_verification_bytes = (
        owner_usage.observed_manifest_verification_bytes if owner_usage is not None else None
    )
    observed_payload_size = owner_usage.observed_payload_size if owner_usage is not None else None
    observed_payload_bytes = owner_usage.observed_payload_bytes if owner_usage is not None else None
    payload_integrity_verified = (
        owner_usage.payload_integrity_verified if owner_usage is not None else False
    )
    if (
        owner_usage is None
        or owner_usage.observed_source_bytes is None
        or type(observed_manifest_verification_bytes) is not int
        or type(observed_payload_size) is not int
        or type(observed_payload_bytes) is not int
        or not payload_integrity_verified
        or observed_payload_bytes != _exact_owner_count(source, "observed_payload_bytes")
        or observed_manifest_verification_bytes
        != _exact_owner_count(source, "observed_manifest_verification_bytes")
        or observed_payload_size != _exact_owner_count(source, "member_size_bytes")
    ):
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_usage_or_integrity_unavailable",
            limits=limits,
            max_manifest_bytes=limits.max_manifest_bytes,
            observed_manifest_bytes=manifest_read.observed_manifest_bytes,
            observed_manifest_selection_bytes=manifest_read.observed_source_bytes,
            observed_manifest_verification_bytes=observed_manifest_verification_bytes,
            observed_bytes=observed_payload_bytes,
            observed_payload_size=observed_payload_size,
            payload_integrity_verified=payload_integrity_verified,
            observed_depth=scanner.max_depth,
            observed_elements=scanner.elements,
            source_usage_complete=(
                type(manifest_read.observed_source_bytes) is int
                and owner_usage is not None
                and owner_usage.observed_source_bytes is not None
            ),
            failure_stage=(
                owner_usage.failure_stage
                if owner_usage is not None
                else "bounded_payload_receipt_validation"
            ),
        )
    bounded_read = CoreJsonArtifactBoundedRead(
        effective_ref=effective_ref,
        manifest=typed_manifest,
        raw_manifest_bytes=raw_manifest_bytes,
        raw_payload_bytes=raw_payload_bytes,
        limits=limits,
        observed_manifest_bytes=manifest_read.observed_manifest_bytes,
        observed_manifest_verification_bytes=observed_manifest_verification_bytes,
        observed_bytes=observed_payload_bytes,
        observed_payload_size=observed_payload_size,
        payload_integrity_verified=payload_integrity_verified,
        observed_depth=scanner.max_depth,
        observed_elements=scanner.elements,
    )
    object.__setattr__(
        bounded_read,
        "_seal",
        _CoreJsonArtifactBoundedReadSeal(
            effective_ref=effective_ref,
            raw_manifest_bytes=raw_manifest_bytes,
            raw_payload_bytes=raw_payload_bytes,
            limits=limits,
            observed_manifest_bytes=manifest_read.observed_manifest_bytes,
            observed_manifest_verification_bytes=observed_manifest_verification_bytes,
            observed_bytes=observed_payload_bytes,
            observed_payload_size=observed_payload_size,
            payload_integrity_verified=payload_integrity_verified,
            observed_depth=scanner.max_depth,
            observed_elements=scanner.elements,
            profile_read=profile_read,
        ),
    )
    return bounded_read


def _verified_core_json_bounded_view(
    bounded_read: CoreJsonArtifactBoundedRead,
) -> tuple[CanonicalProfileRead, ArtifactManifest]:
    """Rebind the bounded carrier to its retained bytes and recompute measurements."""
    if type(bounded_read) is not CoreJsonArtifactBoundedRead:
        raise TypeError("bounded_read must be a CoreJsonArtifactBoundedRead")
    seal = bounded_read._seal
    if type(seal) is not _CoreJsonArtifactBoundedReadSeal:
        raise CanonicalProfileRefusalError("canon_profile_bounded_read_unverified")
    if (
        type(bounded_read.effective_ref) is not ArtifactRef
        or type(seal.effective_ref) is not ArtifactRef
        or bounded_read.effective_ref != seal.effective_ref
        or type(bounded_read.raw_manifest_bytes) is not bytes
        or bounded_read.raw_manifest_bytes != seal.raw_manifest_bytes
        or type(bounded_read.raw_payload_bytes) is not bytes
        or bounded_read.raw_payload_bytes != seal.raw_payload_bytes
        or type(bounded_read.limits) is not CoreJsonReadLimits
        or bounded_read.limits != seal.limits
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_read_carrier_mismatch")
    observed = (
        bounded_read.observed_manifest_bytes,
        bounded_read.observed_manifest_verification_bytes,
        bounded_read.observed_bytes,
        bounded_read.observed_payload_size,
        bounded_read.observed_depth,
        bounded_read.observed_elements,
    )
    sealed_observed = (
        seal.observed_manifest_bytes,
        seal.observed_manifest_verification_bytes,
        seal.observed_bytes,
        seal.observed_payload_size,
        seal.observed_depth,
        seal.observed_elements,
    )
    if (
        any(type(value) is not int for value in observed)
        or observed != sealed_observed
        or type(bounded_read.payload_integrity_verified) is not bool
        or bounded_read.payload_integrity_verified is not seal.payload_integrity_verified
        or bounded_read.payload_integrity_verified is not True
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_read_measurement_mismatch")

    manifest_read = _core_manifest_profile_from_bytes(
        seal.raw_manifest_bytes,
        seal.effective_ref,
        max_manifest_bytes=seal.limits.max_manifest_bytes,
        limits=seal.limits,
    )
    manifest = manifest_read.manifest
    if type(bounded_read.manifest) is not ArtifactManifest or bounded_read.manifest != manifest:
        raise CanonicalProfileRefusalError("canon_profile_bounded_read_carrier_mismatch")

    raw_payload_bytes = seal.raw_payload_bytes
    if (
        type(manifest.byte_size) is not int
        or len(raw_payload_bytes) != manifest.byte_size
        or hashlib.sha256(raw_payload_bytes).hexdigest() != manifest.integrity.sha256
        or manifest.artifact_id.hex != manifest.integrity.sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_selected_payload_identity_mismatch")

    scanner = _JsonStructureBoundsScanner()
    scanner.feed(raw_payload_bytes)
    if (
        observed[0] != len(seal.raw_manifest_bytes)
        or observed[1] != len(seal.raw_manifest_bytes)
        or observed[2] != len(raw_payload_bytes)
        or observed[3] != len(raw_payload_bytes)
        or observed[4] != scanner.max_depth
        or observed[5] != scanner.elements
        or bounded_read.observed_source_bytes != observed[0] + observed[1] + observed[2]
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_read_measurement_mismatch")
    _enforce_core_json_read_bounds(
        seal.limits,
        observed_manifest_bytes=observed[0],
        observed_bytes=observed[2],
        observed_depth=observed[4],
        observed_elements=observed[5],
    )

    cached_profile_read = seal.profile_read
    selected_version = manifest_read.declaration.profile.version
    expected_reader_policy = (
        CORE_V3_TAG_POLICY_ID if selected_version == "0.3.0" else CORE_TAG_POLICY_ID
    )
    expected_artifact_id = str(manifest.artifact_id)
    expected_manifest_profile = artifact_manifest_profile_sha256(manifest)
    if cached_profile_read is None:
        # A legacy/internal carrier without a retained decode proof still takes
        # the full profile decoder path; no caller-supplied status substitutes
        # for canonical validation.
        profile_read = _decode_core_payload_under_declaration(
            raw_payload_bytes,
            manifest_read.declaration,
        )
        profile_read = _bind_selected_artifact_identity(
            profile_read,
            artifact_id=expected_artifact_id,
            manifest_profile_sha256=expected_manifest_profile,
        )
    else:
        if (
            type(cached_profile_read) is not CanonicalProfileRead
            or cached_profile_read.status != "declared_bytes_conformant"
            or cached_profile_read._reader_validated is not True
            or cached_profile_read.raw_payload_bytes != raw_payload_bytes
            or cached_profile_read.selected_artifact_id != expected_artifact_id
            or cached_profile_read.selected_manifest_profile_sha256 != expected_manifest_profile
            or cached_profile_read.reader_policy_id != expected_reader_policy
        ):
            raise CanonicalProfileRefusalError("canon_profile_bounded_cached_read_mismatch")
        try:
            # The reader created this cache only after the exact retained bytes
            # passed decode-and-reencode. Give each consumer a detached value so
            # mutation cannot poison a later read from the same carrier.
            profile_read = deepcopy(cached_profile_read)
        except Exception as exc:
            raise CanonicalProfileRefusalError(
                "canon_profile_bounded_cached_value_copy_failed"
            ) from exc
    require_declared_profile(profile_read)
    if (
        profile_read.raw_payload_bytes != raw_payload_bytes
        or profile_read.selected_artifact_id != str(seal.effective_ref.artifact_id)
        or profile_read.selected_manifest_profile_sha256
        != seal.effective_ref.manifest_profile_sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_bounded_read_carrier_mismatch")
    return profile_read, manifest


def read_core_json_artifact(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> CanonicalProfileRead:
    """Read one selected Core JSON view through its raw and typed manifest boundary.

    Profile absence refuses by default. The explicit compatibility option is
    candidate-only; no path here labels a missing profile as historical.
    """
    get_bytes = getattr(store, "get_bytes", None)
    if not callable(get_bytes):
        raise CanonicalProfileRefusalError("canon_profile_payload_unavailable")
    typed_manifest, declaration = read_core_manifest_profile(
        store,
        selector,
        manifest_profile_sha256=manifest_profile_sha256,
        allow_profile_absent=allow_profile_absent,
    )
    selected_ref = artifact_ref_for_manifest(typed_manifest)
    if (
        manifest_profile_sha256 is not None
        and selected_ref.manifest_profile_sha256 != manifest_profile_sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    if isinstance(selector, ArtifactRef) and selector.manifest_profile_sha256 is not None:
        payload_selector: object = selector
    elif declaration.status != "absent" or manifest_profile_sha256 is not None:
        payload_selector = selected_ref
    else:
        # Unqualified compatibility is candidate-only; it does not establish history,
        # producer attestation, or a selected profile identity.
        payload_selector = selector
    if raw_payload_bytes is None:
        raw_payload_bytes = get_bytes(payload_selector)
        if declaration.status == "absent":
            latest_manifest, latest_declaration = read_core_manifest_profile(
                store,
                payload_selector,
                manifest_profile_sha256=manifest_profile_sha256,
                allow_profile_absent=allow_profile_absent,
            )
            if latest_manifest != typed_manifest or latest_declaration != declaration:
                raise CanonicalProfileRefusalError("canon_profile_selected_manifest_changed")
    if (
        type(raw_payload_bytes) is bytes
        and content_hash(raw_payload_bytes) != typed_manifest.artifact_id.hex
    ):
        raise CanonicalProfileRefusalError("canon_profile_selected_payload_identity_mismatch")
    read = _decode_core_payload_under_declaration(raw_payload_bytes, declaration)
    return _bind_selected_artifact_identity(
        read,
        artifact_id=str(typed_manifest.artifact_id),
        manifest_profile_sha256=artifact_manifest_profile_sha256(typed_manifest),
    )


def load_core_json_artifact(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> Any:
    """Return only a selected Core JSON value whose declared profile conforms."""
    return require_declared_profile(
        read_core_json_artifact(
            store,
            selector,
            raw_payload_bytes=raw_payload_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )
    )


def read_core_json_artifact_bytes(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> bytes:
    """Verify a selected Core JSON byte view before a caller's typed decoder."""
    read = read_core_json_artifact(
        store,
        selector,
        raw_payload_bytes=raw_payload_bytes,
        manifest_profile_sha256=manifest_profile_sha256,
    )
    require_declared_profile(read)
    return read.raw_payload_bytes


def _without_annotated(annotation: Any) -> Any:
    """Strip validation metadata for shape adaptation; the model applies it once."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return _without_annotated(args[0])
    if not args:
        return annotation
    stripped = tuple(_without_annotated(argument) for argument in args)
    if origin is types.UnionType:
        result = stripped[0]
        for option in stripped[1:]:
            result = result | option
        return result
    try:
        return origin[stripped[0] if len(stripped) == 1 else stripped]
    except (AttributeError, TypeError):
        return annotation


def _core_type_adapter(annotation: Any, model_config: ConfigDict) -> TypeAdapter[Any]:
    """Build the public Pydantic adapter with the owning model's JSON settings."""
    annotation = _without_annotated(annotation)
    try:
        return TypeAdapter(annotation, config=model_config)
    except PydanticUserError:
        # BaseModel-containing annotations own their configuration on the model class.
        return TypeAdapter(annotation)


def _unwrap_annotated(annotation: Any) -> Any:
    """Return an annotation's structural type while leaving metadata on its adapter."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _base_model_type(annotation: Any) -> type[BaseModel] | None:
    """Return the BaseModel class at an annotation's structural root."""
    annotation = _unwrap_annotated(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _direct_alias_keys(alias: object) -> tuple[str, ...]:
    """Collect direct string aliases from a Pydantic alias or AliasChoices."""
    if isinstance(alias, str):
        return (alias,)
    choices = getattr(alias, "choices", ())
    if not isinstance(choices, (tuple, list)):
        return ()
    return tuple(key for choice in choices for key in _direct_alias_keys(choice))


_CORE_SCHEMA_WRAPPERS = frozenset(
    {
        "default",
        "function-after",
        "function-before",
        "function-wrap",
        "nullable",
    }
)


def _core_schema_model_type(
    schema: Any,
    definitions: Mapping[str, Any],
) -> type[BaseModel] | None:
    """Resolve one CoreSchema branch to its declared model class without validating it."""
    seen: set[str] = set()
    while isinstance(schema, Mapping):
        schema_type = schema.get("type")
        if schema_type == "definition-ref":
            reference = schema.get("schema_ref")
            if not isinstance(reference, str) or reference in seen:
                return None
            seen.add(reference)
            schema = definitions.get(reference)
            continue
        if schema_type in _CORE_SCHEMA_WRAPPERS:
            schema = schema.get("schema")
            continue
        if schema_type == "json-or-python":
            schema = schema.get("python_schema")
            continue
        if schema_type == "model":
            model = schema.get("cls")
            if isinstance(model, type) and issubclass(model, BaseModel):
                return model
            return None
        return None
    return None


def _core_schema_union_model_types(schema: Any) -> tuple[type[BaseModel], ...]:
    """Read declared model branches from one union annotation schema."""
    definitions: dict[str, Any] = {}
    while isinstance(schema, Mapping):
        schema_type = schema.get("type")
        if schema_type == "definitions":
            for definition in schema.get("definitions", ()):
                if isinstance(definition, Mapping):
                    reference = definition.get("ref")
                    if isinstance(reference, str):
                        definitions[reference] = definition
            schema = schema.get("schema")
            continue
        if schema_type in _CORE_SCHEMA_WRAPPERS:
            schema = schema.get("schema")
            continue
        if schema_type == "json-or-python":
            schema = schema.get("python_schema")
            continue
        break

    if not isinstance(schema, Mapping):
        return ()
    if schema.get("type") not in {"tagged-union", "union"}:
        model = _core_schema_model_type(schema, definitions)
        return (model,) if model is not None else ()
    choices = schema.get("choices")
    if isinstance(choices, Mapping):
        branch_values = tuple(choices.values())
    elif isinstance(choices, (tuple, list)):
        branch_values = tuple(
            choice[0] if isinstance(choice, tuple) else choice for choice in choices
        )
    else:
        return ()

    models: list[type[BaseModel]] = []
    for branch in branch_values:
        model = _core_schema_model_type(branch, definitions)
        if model is not None and model not in models:
            models.append(model)
    return tuple(models)


def _literal_values(annotation: Any) -> tuple[Any, ...]:
    """Return direct Literal values used as schema-discriminating descriptors."""
    annotation = _unwrap_annotated(annotation)
    return get_args(annotation) if get_origin(annotation) is Literal else ()


def _literal_wire_value(value: Any) -> Any:
    """Return the JSON-visible value of an Enum Literal without coercing its type."""
    return value.value if isinstance(value, Enum) else value


def _same_literal_value(candidate: Any, expected: Any) -> bool:
    """Compare one decoded JSON value to a declared Literal value strictly."""
    expected_wire = _literal_wire_value(expected)
    return type(candidate) is type(expected_wire) and candidate == expected_wire


def _model_field_keys(field_name: str, field: Any) -> tuple[str, ...]:
    """Collect the direct JSON keys accepted by one declared Pydantic field."""
    return tuple(
        dict.fromkeys(
            key
            for alias in (
                field.serialization_alias,
                field.alias,
                field.validation_alias,
                field_name,
            )
            for key in _direct_alias_keys(alias)
        )
    )


def _model_mapping_shape_matches(model: type[BaseModel], value: Mapping[Any, Any]) -> bool:
    """Check only required keys and extra-field policy; leave values for terminal validation."""
    if any(not isinstance(key, str) for key in value):
        return False
    allowed_keys: set[str] = set()
    for field_name, model_field in model.model_fields.items():
        field_keys = _model_field_keys(field_name, model_field)
        allowed_keys.update(field_keys)
        if model_field.is_required() and not any(key in value for key in field_keys):
            return False
    return not (model.model_config.get("extra") == "forbid" and set(value) - allowed_keys)


def _core_union_model_branch(
    schema: Any,
    models: tuple[type[BaseModel], ...],
    value: Mapping[Any, Any],
    *,
    discriminator: Any = None,
) -> type[BaseModel] | None:
    """Choose only a uniquely described union model; never validate a branch early."""
    if not models:
        return None

    schema_discriminator = (
        schema.get("discriminator")
        if isinstance(schema, Mapping) and schema.get("type") == "tagged-union"
        else None
    )
    explicit_discriminator = discriminator or schema_discriminator

    literal_descriptors: dict[tuple[str, type[Any], Any], set[type[BaseModel]]] = {}
    for model in models:
        for field_name, model_field in model.model_fields.items():
            values = _literal_values(model_field.annotation)
            if not values:
                continue
            for key in _model_field_keys(field_name, model_field):
                for literal in values:
                    wire_value = _literal_wire_value(literal)
                    try:
                        descriptor = (key, type(wire_value), wire_value)
                        literal_descriptors.setdefault(descriptor, set()).add(model)
                    except TypeError:
                        continue

    if isinstance(explicit_discriminator, str):
        if explicit_discriminator not in value:
            return None
        tag = value[explicit_discriminator]
        matches: set[type[BaseModel]] = set()
        for (key, _value_type, expected), owners in literal_descriptors.items():
            if key == explicit_discriminator and _same_literal_value(tag, expected):
                matches.update(owners)
        if len(matches) == 1:
            return next(iter(matches))
        return None

    unique_descriptors = {
        descriptor: next(iter(owners))
        for descriptor, owners in literal_descriptors.items()
        if len(owners) == 1
    }
    matched_models: set[type[BaseModel]] = set()
    for (key, _value_type, expected), model in unique_descriptors.items():
        if key in value and _same_literal_value(value[key], expected):
            matched_models.add(model)
    if len(matched_models) == 1:
        return next(iter(matched_models))
    if len(matched_models) > 1:
        raise _typed_union_refusal(
            value, "Core union input matches multiple unique Literal branches"
        )

    shape_matches = [model for model in models if _model_mapping_shape_matches(model, value)]
    if len(shape_matches) == 1:
        return shape_matches[0]
    return None


def _typed_union_refusal(value: Any, reason: str) -> ValidationError:
    """Create a normal Pydantic typed refusal for an ambiguous schema adaptation."""
    return ValidationError.from_exception_data(
        "Core typed union",
        [
            {
                "type": "value_error",
                "loc": (),
                "input": value,
                "ctx": {"error": ValueError(reason)},
            }
        ],
    )


def _core_model_payload(model: type[_ModelT], value: Any) -> Any:
    """Reify one Core-decoded model mapping without running validators early."""
    if issubclass(model, RootModel):
        root_field = model.model_fields["root"]
        return _core_typed_value(root_field.annotation, value, model.model_config)

    if not isinstance(value, Mapping):
        return value

    normalized = dict(value)
    for name, model_field in model.model_fields.items():
        candidates = tuple(
            dict.fromkeys(
                key
                for alias in (
                    model_field.serialization_alias,
                    model_field.alias,
                    model_field.validation_alias,
                    name,
                )
                for key in _direct_alias_keys(alias)
            )
        )
        present = [key for key in candidates if key in value]
        if len(present) > 1:
            raise ValueError(f"ambiguous Core JSON aliases for field {name!r}")
        if not present:
            continue
        source_key = present[0]
        typed_value = _core_typed_value(
            model_field.annotation,
            value[source_key],
            model.model_config,
            discriminator=model_field.discriminator,
        )
        if source_key != name:
            normalized.pop(source_key, None)
        normalized[name] = typed_value

    return normalized


def _contains_base_model(annotation: Any) -> bool:
    """Return whether an annotation contains a model that must wait for terminal validation."""
    if _base_model_type(annotation) is not None:
        return True
    return any(
        _contains_base_model(argument) for argument in get_args(_unwrap_annotated(annotation))
    )


def _core_typed_value(
    annotation: Any,
    value: Any,
    model_config: ConfigDict,
    *,
    discriminator: Any = None,
) -> Any:
    """Validate a decoded Core value using its declared Pydantic type and strict mode.

    Core's decoder has already reconstructed its declared native tags. This helper
    supplies the remaining JSON-to-Python shape adaptation (for example list to
    tuple and JSON strings to Enum/date/bytes fields) from the requested annotation.
    """
    model_type = _base_model_type(annotation)
    if model_type is not None:
        return _core_model_payload(model_type, value)

    adapter = _core_type_adapter(annotation, model_config)
    contains_model = _contains_base_model(annotation)
    python_error: ValidationError | None = None
    if not contains_model:
        try:
            return adapter.validate_python(value, strict=True)
        except ValidationError as exc:
            python_error = exc

    base = _unwrap_annotated(annotation)
    origin = get_origin(base)
    args = get_args(base)

    if origin in (Union, types.UnionType):
        if value is None:
            return None
        non_null_options = tuple(option for option in args if option is not type(None))
        if len(non_null_options) == 1 and len(non_null_options) < len(args):
            # Null adds no competing shape for a present value. Recurse through
            # its existing owner, including containers of nested models, before
            # the single terminal strict model validation.
            return _core_typed_value(
                non_null_options[0], value, model_config, discriminator=discriminator
            )
        schema = adapter.core_schema
        model_options = _core_schema_union_model_types(schema)
        if isinstance(value, Mapping):
            model_option = _core_union_model_branch(
                schema,
                model_options,
                value,
                discriminator=discriminator,
            )
            if model_option is not None:
                return _core_model_payload(model_option, value)
        for option in args:
            if _contains_base_model(option):
                continue
            try:
                return _core_typed_value(option, value, model_config)
            except ValidationError:
                continue

    if origin is tuple and isinstance(value, (list, tuple)):
        if len(args) == 2 and args[1] is Ellipsis:
            item_annotations = (args[0],) * len(value)
            valid_shape = True
        elif len(args) == len(value):
            item_annotations = args
            valid_shape = True
        else:
            item_annotations = ()
            valid_shape = False
        if valid_shape:
            candidate = tuple(
                _core_typed_value(
                    item_annotation,
                    item,
                    model_config,
                    discriminator=discriminator,
                )
                for item_annotation, item in zip(item_annotations, value, strict=True)
            )
            return candidate if contains_model else adapter.validate_python(candidate, strict=True)

    if isinstance(origin, type) and issubclass(origin, Sequence) and isinstance(value, list):
        item_annotation = args[0] if args else Any
        sequence_candidate = [
            _core_typed_value(item_annotation, item, model_config, discriminator=discriminator)
            for item in value
        ]
        return (
            sequence_candidate
            if contains_model
            else adapter.validate_python(sequence_candidate, strict=True)
        )

    if isinstance(origin, type) and issubclass(origin, Mapping) and isinstance(value, Mapping):
        key_annotation, item_annotation = args if len(args) == 2 else (Any, Any)
        mapping_candidate = {
            _core_typed_value(
                key_annotation, key, model_config, discriminator=discriminator
            ): _core_typed_value(
                item_annotation,
                item,
                model_config,
                discriminator=discriminator,
            )
            for key, item in value.items()
        }
        return (
            mapping_candidate
            if contains_model
            else adapter.validate_python(mapping_candidate, strict=True)
        )

    if origin in (set, frozenset) and isinstance(value, (list, tuple, set, frozenset)):
        item_annotation = args[0] if args else Any
        items = (
            _core_typed_value(item_annotation, item, model_config, discriminator=discriminator)
            for item in value
        )
        set_candidate = set(items) if origin is set else frozenset(items)
        return (
            set_candidate if contains_model else adapter.validate_python(set_candidate, strict=True)
        )

    if contains_model:
        return value

    if python_error is None:
        return value
    if type(value) is float and _unwrap_annotated(annotation) is Decimal:
        # JSON parsing must not turn a forbidden decimal float into an accepted Decimal.
        raise python_error from None
    try:
        raw_json = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError):
        raise python_error from None
    try:
        return adapter.validate_json(raw_json, strict=True)
    except ValidationError:
        raise python_error from None


def _validate_core_model_payload(
    model: type[_ModelT], value: Any, manifest: ArtifactManifest
) -> _ModelT:
    """Apply Core's owner-directed alias adaptation and terminal model validation."""
    normalized = _core_model_payload(model, value)
    typed_model = model.model_validate(normalized, strict=True, by_alias=False, by_name=True)
    _validate_model_payload_schema_version(model, typed_model, manifest)
    return typed_model


def validate_core_model_bounded_read(
    model: type[_ModelT], bounded_read: CoreJsonArtifactBoundedRead
) -> _ModelT:
    """Validate an already bounded Core JSON read with its typed artifact owner.

    This revalidates the carrier and derives a fresh typed value from its retained
    bounded manifest and payload bytes. It does not access a store or reread bytes.

    Args:
        model: The Pydantic model that owns the selected artifact schema.
        bounded_read: A result returned by ``read_core_json_artifact_bounded``.

    Returns:
        The strictly validated model instance.

    Raises:
        TypeError: If ``bounded_read`` is not a bounded Core JSON read result.
        CanonicalProfileRefusalError: If the selected manifest violates the model
            owner's artifact contract.
        ValidationError: If the decoded payload does not validate as ``model``.
    """
    if type(bounded_read) is not CoreJsonArtifactBoundedRead:
        raise TypeError("bounded_read must be a CoreJsonArtifactBoundedRead")
    profile_read, manifest = _verified_core_json_bounded_view(bounded_read)
    _validate_model_artifact_manifest(model, manifest)
    return _validate_core_model_payload(
        model,
        require_declared_profile(profile_read),
        manifest,
    )


def validate_core_model_json_artifact(
    model: type[_ModelT],
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> _ModelT:
    """Strictly validate a Pydantic model after selected-profile byte admission."""
    manifest, _declaration = read_core_manifest_profile(
        store,
        selector,
        manifest_profile_sha256=manifest_profile_sha256,
    )
    selected_profile_sha256 = artifact_manifest_profile_sha256(manifest)
    _validate_model_artifact_manifest(model, manifest)
    read = read_core_json_artifact(
        store,
        selector,
        raw_payload_bytes=raw_payload_bytes,
        manifest_profile_sha256=selected_profile_sha256,
    )
    value = require_declared_profile(read)
    return _validate_core_model_payload(model, value, manifest)


def _validate_model_artifact_manifest(model: type[BaseModel], manifest: ArtifactManifest) -> None:
    """Require a declared typed-artifact owner ABI to match its selected manifest."""
    expected_kind = getattr(model, "ARTIFACT_KIND", None)
    if expected_kind is not None and manifest.kind != expected_kind:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_kind_mismatch")

    expected_media_type = getattr(model, "ARTIFACT_MEDIA_TYPE", None)
    if expected_media_type is not None and manifest.media_type != expected_media_type:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_media_type_mismatch")

    expected_schema_name = getattr(model, "ARTIFACT_SCHEMA_NAME", None)
    expected_schema_version = getattr(model, "ARTIFACT_SCHEMA_VERSION", None)
    schema = manifest.artifact_schema
    if expected_schema_name is not None and (schema is None or schema.name != expected_schema_name):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_name_mismatch")

    if expected_schema_version is not None:
        if not isinstance(expected_schema_version, str) or not expected_schema_version:
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
        if schema is None:
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_missing")
        declared_versions = getattr(model, "ARTIFACT_SCHEMA_VERSIONS", None)
        if declared_versions is None:
            supported_versions = {expected_schema_version}
            legacy_version = getattr(model, "LEGACY_ARTIFACT_SCHEMA_VERSION", None)
            if legacy_version is not None:
                if not isinstance(legacy_version, str) or not legacy_version:
                    raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
                supported_versions.add(legacy_version)
        else:
            if (
                not isinstance(declared_versions, (tuple, list, set, frozenset))
                or not declared_versions
                or any(not isinstance(value, str) or not value for value in declared_versions)
                or expected_schema_version not in declared_versions
            ):
                raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
            supported_versions = set(declared_versions)
        if schema.version not in supported_versions:
            raise CanonicalProfileRefusalError(
                "canon_profile_typed_artifact_schema_version_unsupported"
            )


def _validate_model_payload_schema_version(
    model: type[BaseModel],
    typed_model: BaseModel,
    manifest: ArtifactManifest,
) -> None:
    """Require payload and selected schema versions to follow the owner's exact relation."""
    schema = manifest.artifact_schema
    required_by_version = getattr(model, "ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION", {})
    if not isinstance(required_by_version, Mapping):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    for manifest_version, required_fields in required_by_version.items():
        if not isinstance(manifest_version, str) or not manifest_version:
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
        if not isinstance(required_fields, (tuple, list, set, frozenset)) or any(
            not isinstance(field_name, str) or not field_name for field_name in required_fields
        ):
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    if schema is not None and schema.version in required_by_version:
        for field_name in required_by_version[schema.version]:
            if (
                field_name not in model.model_fields
                or getattr(typed_model, field_name, None) is None
            ):
                raise CanonicalProfileRefusalError(
                    "canon_profile_typed_artifact_required_field_missing"
                )
    if "schema_version" not in model.model_fields:
        return
    current_version = getattr(model, "ARTIFACT_SCHEMA_VERSION", None)
    if current_version is None:
        return
    if not isinstance(current_version, str) or not current_version:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    schema = manifest.artifact_schema
    if schema is None:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_version_mismatch")
    declared_versions = getattr(model, "ARTIFACT_SCHEMA_VERSIONS", None)
    if declared_versions is None:
        supported_manifest_versions = {current_version}
        legacy_version = getattr(model, "LEGACY_ARTIFACT_SCHEMA_VERSION", None)
        if legacy_version is not None:
            supported_manifest_versions.add(legacy_version)
    else:
        if (
            not isinstance(declared_versions, (tuple, list, set, frozenset))
            or not declared_versions
            or any(not isinstance(value, str) or not value for value in declared_versions)
            or current_version not in declared_versions
        ):
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
        supported_manifest_versions = set(declared_versions)
    if schema.version not in supported_manifest_versions:
        raise CanonicalProfileRefusalError(
            "canon_profile_typed_artifact_schema_version_unsupported"
        )
    version_map = getattr(model, "ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST", {})
    if not isinstance(version_map, Mapping) or any(
        not isinstance(manifest_version, str)
        or not manifest_version
        or not isinstance(payload_version, str)
        or not payload_version
        or manifest_version not in supported_manifest_versions
        for manifest_version, payload_version in version_map.items()
    ):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    expected_payload_version = version_map.get(schema.version, schema.version)
    payload_version = getattr(typed_model, "schema_version", None)
    if not isinstance(payload_version, str) or payload_version != expected_payload_version:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_version_mismatch")


def _split_core_json_frames(payload: bytes) -> list[bytes]:
    """Split exact uint64 length-prefixed Core canonical JSON records."""
    if type(payload) is not bytes:
        raise CanonicalProfileRefusalError("canon_profile_payload_bytes_invalid")
    records: list[bytes] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 8:
            raise CanonicalProfileRefusalError("canon_frame_truncated_length")
        size = int.from_bytes(payload[offset : offset + 8], "big")
        offset += 8
        end = offset + size
        if end > len(payload):
            raise CanonicalProfileRefusalError("canon_frame_truncated_payload")
        records.append(payload[offset:end])
        offset = end
    if not records:
        raise CanonicalProfileRefusalError("canon_frame_empty")
    return records


def load_core_json_frame_records(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
) -> list[Any]:
    """Load selected Core JSON frames only after profile and byte conformance."""
    get_bytes = getattr(store, "get_bytes", None)
    if not callable(get_bytes):
        raise CanonicalProfileRefusalError("canon_profile_payload_unavailable")
    manifest, declaration = read_core_manifest_profile(store, selector)
    if declaration.status != "declared" or declaration.profile is None:
        raise CanonicalProfileRefusalError("canon_profile_not_verified")
    selected_ref = artifact_ref_for_manifest(manifest)
    payload = get_bytes(selected_ref) if raw_payload_bytes is None else raw_payload_bytes
    if type(payload) is not bytes or content_hash(payload) != manifest.artifact_id.hex:
        raise CanonicalProfileRefusalError("canon_profile_selected_payload_identity_mismatch")
    records = _split_core_json_frames(payload)
    version = declaration.profile.version
    values: list[Any] = []
    for raw_record in records:
        read = decode_profiled_canonical_bytes(
            raw_record,
            declaration,
            profile_model=CanonInfo,
            make_spec=_core_spec_from_profile,
            decode=lambda raw, max_depth: from_canonical_bytes(
                raw, max_depth=max_depth, version=version
            ),
            encode=_encode_core_profiled_value,
            reader_policy_id=(CORE_V3_TAG_POLICY_ID if version == "0.3.0" else CORE_TAG_POLICY_ID),
        )
        values.append(require_declared_profile(read))
    return values


async def aload_core_json_artifact(
    store: object,
    selector: object,
) -> Any:
    """Asynchronously verify and decode one selected Core JSON artifact."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError

    raw_reader = getattr(store, "get_raw_manifest_bytes", None)
    manifest_reader = getattr(store, "get_manifest", None)
    payload_reader = getattr(store, "get_bytes", None)
    if not callable(raw_reader):
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable")
    if not callable(manifest_reader):
        raise CanonicalProfileRefusalError("canon_profile_typed_manifest_unavailable")
    if not callable(payload_reader):
        raise CanonicalProfileRefusalError("canon_profile_payload_unavailable")

    selected_profile = getattr(selector, "manifest_profile_sha256", None)
    try:
        raw_manifest = _require_exact_bytes(
            await raw_reader(selector), "canon_profile_raw_manifest_invalid"
        )
        declaration = parse_canonical_profile(
            raw_manifest,
            profile_model=CanonInfo,
            allow_profile_absent=False,
            supported_versions=("0.2.0", "0.3.0"),
        )
        if declaration.status != "declared":
            raise CanonicalProfileRefusalError("canon_profile_not_verified")
        manifest = await manifest_reader(selector)
        payload = _require_exact_bytes(
            await payload_reader(selector), "canon_profile_payload_bytes_invalid"
        )
    except (AttributeError, NotImplementedError, TypeError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable") from exc

    class _PrefetchedAsyncView:
        def get_raw_manifest_bytes(self, _selector: object) -> bytes:
            return raw_manifest

        def get_manifest(self, _selector: object) -> object:
            return manifest

        def get_manifest_by_profile(self, _artifact_id: object, profile: str) -> object:
            if profile != selected_profile:
                raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
            return manifest

        def get_bytes(self, _selector: object) -> bytes:
            return payload

    return read_core_json_artifact(
        _PrefetchedAsyncView(),
        selector,
        raw_payload_bytes=payload,
    ).value


__all__ = [
    "CoreJsonArtifactBoundedRead",
    "CoreJsonManifestBoundedRead",
    "CoreJsonReadBoundsRefusalError",
    "CoreJsonReadLimits",
    "aload_core_json_artifact",
    "artifact_ref_for_manifest",
    "decode_core_json_payload",
    "load_core_json_artifact",
    "load_core_json_frame_records",
    "read_core_input_manifest_profile_bounded",
    "read_core_json_artifact",
    "read_core_json_artifact_bounded",
    "read_core_json_artifact_bytes",
    "read_core_manifest_profile",
    "read_core_manifest_profile_bounded",
    "validate_core_model_bounded_read",
    "validate_core_model_json_artifact",
]
