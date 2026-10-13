"""Read Core JSON artifacts against their exact raw manifest profile."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

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
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, CanonInfo
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes

_ModelT = TypeVar("_ModelT", bound=BaseModel)


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


def read_core_manifest_profile(
    store: object,
    selector: object,
    *,
    manifest_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> tuple[ArtifactManifest, CanonicalProfileDeclaration]:
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
            and selector.manifest_profile_sha256
            != artifact_manifest_profile_sha256(typed_manifest)
        )
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    if (
        manifest_profile_sha256 is not None
        and artifact_manifest_profile_sha256(typed_manifest) != manifest_profile_sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    return typed_manifest, declaration


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
    )
    read = decode_profiled_canonical_bytes(
        raw_payload_bytes,
        declaration,
        profile_model=CanonInfo,
        make_spec=_core_spec,
        decode=lambda raw, max_depth: from_canonical_bytes(raw, max_depth=max_depth),
        encode=lambda value, spec: to_canonical_bytes(value, spec),
    )
    return read


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
    if (
        isinstance(selector, ArtifactRef)
        and selector.manifest_profile_sha256 is not None
    ):
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
    read = decode_profiled_canonical_bytes(
        raw_payload_bytes,
        declaration,
        profile_model=CanonInfo,
        make_spec=_core_spec,
        decode=lambda raw, max_depth: from_canonical_bytes(raw, max_depth=max_depth),
        encode=lambda value, spec: to_canonical_bytes(value, spec),
    )
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


def validate_core_model_json_artifact(
    model: type[_ModelT],
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> _ModelT:
    """Strictly validate a Pydantic model after selected-profile byte admission."""
    return model.model_validate(
        load_core_json_artifact(
            store,
            selector,
            raw_payload_bytes=raw_payload_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )
    )


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
    values: list[Any] = []
    for raw_record in records:
        read = decode_profiled_canonical_bytes(
            raw_record,
            declaration,
            profile_model=CanonInfo,
            make_spec=_core_spec,
            decode=lambda raw, max_depth: from_canonical_bytes(raw, max_depth=max_depth),
            encode=lambda value, spec: to_canonical_bytes(value, spec),
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
        raw_manifest = await raw_reader(selector)
        declaration = parse_canonical_profile(
            raw_manifest,
            profile_model=CanonInfo,
            allow_profile_absent=False,
        )
        if declaration.status != "declared":
            raise CanonicalProfileRefusalError("canon_profile_not_verified")
        manifest = await manifest_reader(selector)
        payload = await payload_reader(selector)
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
    "aload_core_json_artifact",
    "artifact_ref_for_manifest",
    "decode_core_json_payload",
    "load_core_json_artifact",
    "load_core_json_frame_records",
    "read_core_json_artifact",
    "read_core_json_artifact_bytes",
    "read_core_manifest_profile",
    "validate_core_model_json_artifact",
]
