"""State snapshot persistence — load, put, flatten, nest, build."""

from __future__ import annotations

import dataclasses
import hashlib
import math
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import UnionType
from typing import Any, NoReturn, Protocol, Union, get_args, get_origin, get_type_hints
from zipfile import ZIP_STORED, BadZipFile, ZipFile

import jax
import jax.numpy as jnp
import numpy as np
from pydantic import BaseModel

from polisyos.core.artifacts import (
    ArtifactMemberReadBoundsError,
    ArtifactMemberReadIntegrityError,
    ArtifactStore,
    CoreJSONArtifactStore,
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    artifact_manifest_profile_sha256,
    read_core_json_artifact_bounded,
)
from polisyos.core.artifacts import (
    require_return_selected_profile_writer as _require_return_selected_profile_writer,
)
from polisyos.core.artifacts import (
    validate_return_selected_profile as _validate_return_selected_profile,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.protocol import CoreJSONArtifactBoundedMemberReader
from polisyos.core.artifacts.store import ArtifactIntegrityError, PutOptions
from polisyos.core.contracts.foundry import StateSnapshot, StateSnapshotRef
from polisyos.core.contracts.value_outer_set import ValueOuterSet
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.models import artifact_input_ref, load_model

__all__ = [
    "BoundedNumericNPZError",
    "BoundedStateSnapshotInputs",
    "StateSnapshotInputReadUsage",
    "StateSnapshotInputReadRefusal",
    "export_seed_state_npz",
    "import_seed_state_npz",
    "load_state_snapshot",
    "StateSnapshotValueLeaf",
    "state_snapshot_value_projection",
    "put_state_snapshot",
    "read_numeric_npz_bounded",
    "read_state_snapshot_inputs_bounded",
]

_SNAPSHOT_FORMAT_VERSION = "npz-v2"
_SNAPSHOT_CODEC = "numpy-npz"
_MAX_BOUNDED_INPUT_MANIFEST_BYTES = 64 * 1024
_MAX_BOUNDED_INPUT_SNAPSHOT_BYTES = 256 * 1024
_MAX_BOUNDED_INPUT_STATE_BLOB_BYTES = 5 * 1024 * 1024
_MAX_BOUNDED_INPUT_ENTRIES = 32
_MAX_BOUNDED_INPUT_ELEMENTS = 1_000_000


def _is_snapshot_slot_id(value: object) -> bool:
    """Return whether a sparse slot key has one unambiguous NPZ basename."""
    return (
        type(value) is str
        and 0 < len(value) <= 256
        and value.isascii()
        and value.replace("_", "").isalnum()
    )


class _BoundedStateSnapshotStore(
    CoreJSONArtifactStore,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Store surface required for bounded selected snapshot reads."""


@dataclass(frozen=True, slots=True)
class BoundedStateSnapshotInputs:
    """Exact selected state input arrays resolved within explicit byte bounds."""

    snapshot_ref: StateSnapshotRef
    snapshot: StateSnapshot
    snapshot_manifest: ArtifactManifest
    state_blob_ref: ArtifactRef
    arrays: tuple[tuple[str, np.ndarray], ...]
    observed_snapshot_manifest_bytes: int
    observed_snapshot_manifest_verification_bytes: int
    observed_snapshot_payload_bytes: int
    observed_blob_manifest_bytes: int
    observed_blob_manifest_verification_bytes: int
    observed_blob_bytes: int
    observed_entries: int
    observed_elements: int
    snapshot_payload_integrity_verified: bool
    state_blob_payload_integrity_verified: bool

    @property
    def usage(self) -> StateSnapshotInputReadUsage:
        """Return the exact per-call selected-store byte measurements."""
        return StateSnapshotInputReadUsage(
            observed_snapshot_manifest_bytes=self.observed_snapshot_manifest_bytes,
            observed_snapshot_manifest_verification_bytes=(
                self.observed_snapshot_manifest_verification_bytes
            ),
            observed_snapshot_payload_bytes=self.observed_snapshot_payload_bytes,
            observed_blob_manifest_bytes=self.observed_blob_manifest_bytes,
            observed_blob_manifest_verification_bytes=(
                self.observed_blob_manifest_verification_bytes
            ),
            observed_blob_bytes=self.observed_blob_bytes,
            snapshot_payload_integrity_verified=self.snapshot_payload_integrity_verified,
            state_blob_payload_integrity_verified=self.state_blob_payload_integrity_verified,
        )

    @property
    def observed_source_bytes(self) -> int:
        """Return all measured selected-store bytes used by this read."""
        observed = self.usage.observed_source_bytes
        if observed is None:
            raise RuntimeError("successful_state_snapshot_read_has_unmeasured_source_bytes")
        return observed

    @property
    def payload_integrity_verified(self) -> bool:
        """Return whether both selected JSON and NPZ payloads passed integrity checks."""
        return (
            self.snapshot_payload_integrity_verified and self.state_blob_payload_integrity_verified
        )


@dataclass(frozen=True, slots=True)
class StateSnapshotInputReadUsage:
    """Measured selected-store bytes for one bounded snapshot-input read."""

    observed_snapshot_manifest_bytes: int | None
    observed_snapshot_manifest_verification_bytes: int | None
    observed_snapshot_payload_bytes: int | None
    observed_blob_manifest_bytes: int | None
    observed_blob_manifest_verification_bytes: int | None
    observed_blob_bytes: int | None
    snapshot_payload_integrity_verified: bool | None
    state_blob_payload_integrity_verified: bool | None

    @property
    def observed_source_bytes(self) -> int | None:
        """Sum attempted selected-store transfers, or None if any count is unknown."""
        values = (
            self.observed_snapshot_manifest_bytes,
            self.observed_snapshot_manifest_verification_bytes,
            self.observed_snapshot_payload_bytes,
            self.observed_blob_manifest_bytes,
            self.observed_blob_manifest_verification_bytes,
            self.observed_blob_bytes,
        )
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)

    @property
    def payload_integrity_verified(self) -> bool | None:
        """Return True only when both payloads passed their owner integrity checks."""
        flags = (
            self.snapshot_payload_integrity_verified,
            self.state_blob_payload_integrity_verified,
        )
        if any(flag is False for flag in flags):
            return False
        if all(flag is True for flag in flags):
            return True
        return None


class StateSnapshotInputReadRefusal(ValueError):
    """Typed refusal for a selected bounded input-state read."""

    def __init__(
        self,
        reason: str,
        *,
        usage: StateSnapshotInputReadUsage | None = None,
        observed_bytes: int | None = None,
        limit_bytes: int = 0,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.observed_bytes = observed_bytes
        self.limit_bytes = limit_bytes
        self.usage = usage or StateSnapshotInputReadUsage(
            None, None, None, None, None, None, None, None
        )
        self.observed_source_bytes = self.usage.observed_source_bytes
        self.payload_integrity_verified = self.usage.payload_integrity_verified


class BoundedNumericNPZError(ValueError):
    """One bounded numeric NPZ refusal with observed and allowed extents."""

    def __init__(
        self, reason: str, *, observed_bytes: int | None = None, limit_bytes: int = 0
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.observed_bytes = observed_bytes
        self.limit_bytes = limit_bytes


def _read_npz_entry_count(blob: bytes, *, max_entries: int) -> int:
    """Count central-directory entries before constructing an allocating ZIP reader."""
    start = max(0, len(blob) - 65_557)
    end_record = blob.rfind(b"PK\x05\x06", start)
    if end_record < 0 or end_record + 22 > len(blob):
        raise BoundedNumericNPZError("npz_end_record_missing")
    (
        signature,
        disk,
        central_disk,
        disk_entries,
        total_entries,
        central_size,
        central_offset,
        comment,
    ) = struct.unpack_from("<4s4H2LH", blob, end_record)
    if (
        signature != b"PK\x05\x06"
        or disk != 0
        or central_disk != 0
        or disk_entries != total_entries
        or total_entries == 0xFFFF
        or central_size == 0xFFFFFFFF
        or central_offset == 0xFFFFFFFF
        or end_record + 22 + comment != len(blob)
        or central_offset + central_size > end_record
    ):
        raise BoundedNumericNPZError("npz_layout_unsupported")
    if total_entries > max_entries:
        raise BoundedNumericNPZError(
            "npz_entry_limit_exceeded", observed_bytes=total_entries, limit_bytes=max_entries
        )
    cursor = central_offset
    central_end = central_offset + central_size
    actual_entries = 0
    while cursor < central_end:
        if cursor + 46 > central_end:
            raise BoundedNumericNPZError("npz_layout_unsupported")
        fields = struct.unpack_from("<4s6H3I5H2I", blob, cursor)
        if (
            fields[0] != b"PK\x01\x02"
            or fields[8] == 0xFFFFFFFF
            or fields[9] == 0xFFFFFFFF
            or fields[13] != 0
            or fields[16] == 0xFFFFFFFF
        ):
            raise BoundedNumericNPZError("npz_layout_unsupported")
        cursor += 46 + fields[10] + fields[11] + fields[12]
        if cursor > central_end:
            raise BoundedNumericNPZError("npz_layout_unsupported")
        actual_entries += 1
        if actual_entries > max_entries:
            raise BoundedNumericNPZError(
                "npz_entry_limit_exceeded", observed_bytes=actual_entries, limit_bytes=max_entries
            )
    if cursor != central_end or actual_entries != total_entries:
        raise BoundedNumericNPZError("npz_slot_inventory_mismatch")
    return actual_entries


def read_numeric_npz_bounded(
    blob: bytes,
    *,
    names: tuple[str, ...],
    max_entries: int,
    max_elements: int,
    max_member_bytes: int,
    ndim: int,
    allow_empty: bool = False,
    exact_dtype: str | None = None,
) -> tuple[np.ndarray, ...]:
    """Decode exactly named stored numeric arrays under input and allocation bounds.

    Args:
        blob: Complete already-bounded immutable NPZ bytes.
        names: Exact ordered array basenames, without extensions.
        max_entries: Maximum archive members.
        max_elements: Maximum total numeric values across arrays.
        max_member_bytes: Maximum archive and each uncompressed member length.
        ndim: Required number of dimensions for all arrays.
        allow_empty: Permit zero rows only for a two-dimensional matrix.
        exact_dtype: Optional exact NumPy dtype string, such as ``<f4``.

    Returns:
        Read-only arrays in the supplied name order.

    Raises:
        BoundedNumericNPZError: When any count, format or content is unsupported.
    """
    if (
        type(blob) is not bytes
        or type(names) is not tuple
        or not names
        or any(not _is_snapshot_slot_id(name) for name in names)
        or len(set(names)) != len(names)
        or any(
            type(v) is not int or v < 1 for v in (max_entries, max_elements, max_member_bytes, ndim)
        )
        or type(allow_empty) is not bool
        or (allow_empty and ndim != 2)
        or (exact_dtype is not None and type(exact_dtype) is not str)
    ):
        raise BoundedNumericNPZError("npz_contract_invalid")
    if len(blob) > max_member_bytes:
        raise BoundedNumericNPZError(
            "npz_entry_codec_or_size_unsupported",
            observed_bytes=len(blob),
            limit_bytes=max_member_bytes,
        )
    entry_count = _read_npz_entry_count(blob, max_entries=max_entries)
    elements = 0
    arrays_by_name: dict[str, np.ndarray] = {}
    try:
        with ZipFile(BytesIO(blob)) as archive:
            infos = archive.infolist()
            archive_names = tuple(info.filename for info in infos)
            expected = {f"{name}.npy" for name in names}
            if (
                len(infos) != entry_count
                or len(set(archive_names)) != len(archive_names)
                or set(archive_names) != expected
            ):
                raise BoundedNumericNPZError("npz_slot_inventory_mismatch")
            for info in infos:
                if info.compress_type != ZIP_STORED or info.file_size > max_member_bytes:
                    raise BoundedNumericNPZError(
                        "npz_entry_codec_or_size_unsupported",
                        observed_bytes=info.file_size,
                        limit_bytes=max_member_bytes,
                    )
                with archive.open(info) as entry:
                    version = np.lib.format.read_magic(entry)
                    if version == (1, 0):
                        shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(
                            entry, max_header_size=10_000
                        )
                    elif version == (2, 0):
                        shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(
                            entry, max_header_size=10_000
                        )
                    else:
                        raise BoundedNumericNPZError("npz_npy_version_unsupported")
                    shape = tuple(int(size) for size in shape)
                    dtype = np.dtype(dtype)
                    count = math.prod(shape) if shape else 1
                    raw_size = count * dtype.itemsize
                    empty_ok = allow_empty and len(shape) == 2 and shape[0] == 0 and shape[1] > 0
                    if (
                        len(shape) != ndim
                        or any(size < 0 for size in shape)
                        or (count <= 0 and not empty_ok)
                        or dtype.hasobject
                        or dtype.kind not in {"i", "u", "f"}
                        or fortran_order
                        or (exact_dtype is not None and dtype.str != exact_dtype)
                        or count > max_elements - elements
                        or raw_size > max_member_bytes
                        or entry.tell() + raw_size != info.file_size
                    ):
                        raise BoundedNumericNPZError(
                            "npz_array_shape_or_byte_limit_exceeded",
                            observed_bytes=raw_size,
                            limit_bytes=max_member_bytes,
                        )
                    raw = entry.read(raw_size + 1)
                    if len(raw) != raw_size:
                        raise BoundedNumericNPZError("npz_array_length_mismatch")
                    array = np.frombuffer(raw, dtype=dtype).reshape(shape).copy(order="C")
                    if dtype.kind == "f" and not np.isfinite(array).all():
                        raise BoundedNumericNPZError("npz_array_non_finite")
                    array.setflags(write=False)
                    arrays_by_name[info.filename[:-4]] = array
                    elements += count
    except BoundedNumericNPZError:
        raise
    except (BadZipFile, OSError, EOFError, ValueError, TypeError) as exc:
        raise BoundedNumericNPZError("npz_decode_failed") from exc
    return tuple(arrays_by_name[name] for name in names)


def read_state_snapshot_inputs_bounded(
    store: _BoundedStateSnapshotStore,
    *,
    snapshot_ref: StateSnapshotRef,
    slot_ids: tuple[str, ...],
    max_manifest_bytes: int,
    max_snapshot_payload_bytes: int,
    max_state_blob_bytes: int,
    max_entries: int,
    max_elements: int,
) -> BoundedStateSnapshotInputs:
    """Resolve exact numeric slots from a selected state snapshot before inflation.

    Only flat, one-dimensional numeric input slots are accepted. The snapshot
    JSON and NPZ blob are profile-checked and their actual sizes/counts are
    measured before parsing or array allocation.
    """
    measured: dict[str, int | None] = {
        "observed_snapshot_manifest_bytes": 0,
        "observed_snapshot_manifest_verification_bytes": 0,
        "observed_snapshot_payload_bytes": 0,
        "observed_blob_manifest_bytes": 0,
        "observed_blob_manifest_verification_bytes": 0,
        "observed_blob_bytes": 0,
    }
    integrity: dict[str, bool | None] = {
        "snapshot_payload_integrity_verified": None,
        "state_blob_payload_integrity_verified": None,
    }

    def current_usage() -> StateSnapshotInputReadUsage:
        return StateSnapshotInputReadUsage(**measured, **integrity)

    def refuse(
        reason: str,
        *,
        observed_bytes: int | None = None,
        limit_bytes: int = 0,
    ) -> NoReturn:
        usage = current_usage()
        measured_bytes = usage.observed_source_bytes
        raise StateSnapshotInputReadRefusal(
            reason,
            usage=usage,
            observed_bytes=observed_bytes if observed_bytes is not None else measured_bytes,
            limit_bytes=limit_bytes,
        )

    bounds = (
        max_manifest_bytes,
        max_snapshot_payload_bytes,
        max_state_blob_bytes,
        max_entries,
        max_elements,
    )
    if any(type(value) is not int or value < 1 for value in bounds):
        raise ValueError("state_snapshot_input_read_bounds_must_be_positive_integers")
    max_manifest_bytes = min(max_manifest_bytes, _MAX_BOUNDED_INPUT_MANIFEST_BYTES)
    max_snapshot_payload_bytes = min(
        max_snapshot_payload_bytes,
        _MAX_BOUNDED_INPUT_SNAPSHOT_BYTES,
    )
    max_state_blob_bytes = min(max_state_blob_bytes, _MAX_BOUNDED_INPUT_STATE_BLOB_BYTES)
    max_entries = min(max_entries, _MAX_BOUNDED_INPUT_ENTRIES)
    max_elements = min(max_elements, _MAX_BOUNDED_INPUT_ELEMENTS)
    if (
        type(snapshot_ref) is not StateSnapshotRef
        or snapshot_ref.manifest_profile_sha256 is None
        or not slot_ids
        or len(slot_ids) > 32
        or any(not _is_snapshot_slot_id(slot_id) for slot_id in slot_ids)
        or len(set(slot_ids)) != len(slot_ids)
    ):
        refuse("state_snapshot_selected_input_contract_invalid")

    limits = CoreJsonReadLimits(
        max_bytes=max_snapshot_payload_bytes,
        max_depth=16,
        max_elements=max_entries * 16,
        max_manifest_bytes=max_manifest_bytes,
    )
    measured.update(
        {
            "observed_snapshot_manifest_bytes": None,
            "observed_snapshot_manifest_verification_bytes": None,
            "observed_snapshot_payload_bytes": None,
        }
    )
    try:
        bounded = read_core_json_artifact_bounded(
            store,
            ArtifactRef.model_validate(snapshot_ref.model_dump(mode="python")),
            limits=limits,
        )
    except CoreJsonReadBoundsRefusalError as exc:
        measured.update(
            {
                "observed_snapshot_manifest_bytes": getattr(
                    exc, "observed_manifest_selection_bytes", None
                ),
                "observed_snapshot_manifest_verification_bytes": getattr(
                    exc, "observed_manifest_verification_bytes", None
                ),
                "observed_snapshot_payload_bytes": getattr(exc, "observed_payload_bytes", None),
            }
        )
        integrity["snapshot_payload_integrity_verified"] = getattr(
            exc, "payload_integrity_verified", False
        )
        refuse(
            "state_snapshot_core_bounded_read_refused",
            observed_bytes=getattr(exc, "observed_source_bytes", None),
            limit_bytes=max_snapshot_payload_bytes,
        )
    except Exception as exc:
        measured.update(
            {
                "observed_snapshot_manifest_bytes": getattr(
                    exc, "observed_manifest_selection_bytes", None
                ),
                "observed_snapshot_manifest_verification_bytes": getattr(
                    exc, "observed_manifest_verification_bytes", None
                ),
                "observed_snapshot_payload_bytes": getattr(exc, "observed_payload_bytes", None),
            }
        )
        integrity["snapshot_payload_integrity_verified"] = getattr(
            exc, "payload_integrity_verified", False
        )
        refuse("state_snapshot_core_bounded_read_failed")
    measured.update(
        {
            "observed_snapshot_manifest_bytes": getattr(
                bounded,
                "observed_manifest_selection_bytes",
                getattr(bounded, "observed_manifest_bytes", None),
            ),
            "observed_snapshot_manifest_verification_bytes": (
                bounded.observed_manifest_verification_bytes
            ),
            "observed_snapshot_payload_bytes": bounded.observed_payload_bytes,
        }
    )
    integrity["snapshot_payload_integrity_verified"] = bounded.payload_integrity_verified
    method_input_manifest_schema = StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION[
        StateSnapshot.METHOD_INPUT_SCHEMA_VERSION
    ]
    if (
        bounded.effective_ref.artifact_id != snapshot_ref.artifact_id
        or bounded.effective_ref.kind != snapshot_ref.kind
        or bounded.effective_ref.media_type != snapshot_ref.media_type
        or bounded.effective_ref.manifest_profile_sha256 != snapshot_ref.manifest_profile_sha256
        or bounded.manifest.kind != "foundry.state_snapshot"
        or bounded.manifest.media_type != "application/json"
        or bounded.manifest.artifact_schema
        != SchemaInfo(name="polisyos.core.StateSnapshot", version=method_input_manifest_schema)
    ):
        refuse("state_snapshot_manifest_identity_mismatch")
    if not bounded.payload_integrity_verified:
        integrity["snapshot_payload_integrity_verified"] = False
        refuse("state_snapshot_payload_integrity_not_verified")
    try:
        snapshot = StateSnapshot.model_validate(bounded.value)
    except Exception:
        refuse("state_snapshot_payload_parse_failed")
    if (
        snapshot.schema_version != StateSnapshot.METHOD_INPUT_SCHEMA_VERSION
        or snapshot.codec != _SNAPSHOT_CODEC
        or snapshot.format_version != _SNAPSHOT_FORMAT_VERSION
        or snapshot.layout != StateSnapshot.METHOD_INPUT_LAYOUT
        or snapshot.lineage_inputs is None
        or snapshot.entry_count != len(slot_ids)
        or snapshot.state_ref.kind != "foundry.state_blob"
        or snapshot.state_ref.media_type != "application/x-npz"
        or snapshot.state_ref.manifest_profile_sha256 is None
    ):
        refuse("state_snapshot_payload_identity_mismatch")
    expected_blob_edge = artifact_input_ref(snapshot.state_ref, role="state_blob")
    if (
        not snapshot.lineage_inputs
        or snapshot.lineage_inputs[-1] != expected_blob_edge
        or bounded.manifest.inputs != snapshot.lineage_inputs
    ):
        refuse("state_snapshot_blob_lineage_mismatch")

    measured["observed_blob_manifest_bytes"] = None
    try:
        blob_manifest_bytes = store.get_raw_manifest_bytes_bounded(
            snapshot.state_ref,
            max_manifest_bytes=max_manifest_bytes,
        )
    except Exception as exc:
        # ``observed_bytes`` on ArtifactReadBoundsError is the member's declared
        # size, not the transfer count. Only Core's explicit ``bytes_read`` is
        # admissible as usage; otherwise this attempted transfer is unknown.
        measured["observed_blob_manifest_bytes"] = getattr(exc, "bytes_read", None)
        refuse(
            f"state_snapshot_blob_manifest_read_refused:{type(exc).__name__}",
            observed_bytes=getattr(exc, "observed_source_bytes", None),
            limit_bytes=max_manifest_bytes,
        )
    measured["observed_blob_manifest_bytes"] = len(blob_manifest_bytes)
    try:
        blob_manifest = ArtifactManifest.model_validate_json(blob_manifest_bytes)
    except Exception:
        refuse("state_snapshot_blob_manifest_parse_failed")
    if (
        blob_manifest.artifact_id != snapshot.state_ref.artifact_id
        or blob_manifest.kind != "foundry.state_blob"
        or blob_manifest.media_type != "application/x-npz"
        or artifact_manifest_profile_sha256(blob_manifest)
        != snapshot.state_ref.manifest_profile_sha256
    ):
        refuse("state_snapshot_blob_manifest_identity_mismatch")
    expected_manifest_hash = hashlib.sha256(blob_manifest_bytes).hexdigest()
    blob_bytes = bytearray()
    blob_read_failure: str | None = None
    measured["observed_blob_manifest_verification_bytes"] = None
    measured["observed_blob_bytes"] = None
    member: Any | None = None
    try:
        with store.open_member_bounded(
            snapshot.state_ref,
            "blob",
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_hash,
            max_member_bytes=max_state_blob_bytes,
        ) as member:
            observed_blob_size = member.member_size_bytes
            while len(blob_bytes) < observed_blob_size:
                chunk = member.read(min(1024 * 1024, observed_blob_size - len(blob_bytes)))
                if not chunk:
                    blob_read_failure = "state_snapshot_blob_truncated"
                    break
                blob_bytes.extend(chunk)
            if len(blob_bytes) != observed_blob_size:
                blob_read_failure = blob_read_failure or "state_snapshot_blob_truncated"
            trailing = member.read(1)
            if trailing:
                blob_read_failure = "state_snapshot_blob_size_changed_during_read"
        measured["observed_blob_manifest_verification_bytes"] = (
            member.observed_manifest_verification_bytes
        )
        measured["observed_blob_bytes"] = member.observed_payload_bytes
        integrity["state_blob_payload_integrity_verified"] = member.payload_integrity_verified
        if blob_read_failure is not None:
            refuse(
                blob_read_failure,
                observed_bytes=member.observed_payload_bytes,
                limit_bytes=max_state_blob_bytes,
            )
        if not member.payload_integrity_verified:
            refuse("state_snapshot_blob_integrity_not_verified")
    except ArtifactMemberReadBoundsError as exc:
        measured["observed_blob_manifest_verification_bytes"] = getattr(
            exc, "observed_manifest_verification_bytes", None
        )
        measured["observed_blob_bytes"] = getattr(exc, "observed_payload_bytes", None)
        integrity["state_blob_payload_integrity_verified"] = getattr(
            exc, "payload_integrity_verified", False
        )
        refuse(
            "state_snapshot_blob_bounded_read_refused",
            observed_bytes=getattr(exc, "observed_source_bytes", None),
            limit_bytes=max_state_blob_bytes,
        )
    except ArtifactMemberReadIntegrityError as exc:
        measured["observed_blob_manifest_verification_bytes"] = getattr(
            exc, "observed_manifest_verification_bytes", None
        )
        measured["observed_blob_bytes"] = getattr(exc, "observed_payload_bytes", None)
        integrity["state_blob_payload_integrity_verified"] = getattr(
            exc, "payload_integrity_verified", False
        )
        refuse(
            "state_snapshot_blob_integrity_read_failed",
            observed_bytes=getattr(exc, "observed_source_bytes", None),
            limit_bytes=max_state_blob_bytes,
        )
    except StateSnapshotInputReadRefusal:
        raise
    except Exception as exc:
        if member is not None:
            measured["observed_blob_manifest_verification_bytes"] = getattr(
                member, "observed_manifest_verification_bytes", None
            )
            measured["observed_blob_bytes"] = getattr(member, "observed_payload_bytes", None)
            integrity["state_blob_payload_integrity_verified"] = getattr(
                member, "payload_integrity_verified", False
            )
        refuse(f"state_snapshot_blob_read_failed:{type(exc).__name__}")

    try:
        decoded = read_numeric_npz_bounded(
            bytes(blob_bytes),
            names=slot_ids,
            max_entries=max_entries,
            max_elements=max_elements,
            max_member_bytes=max_state_blob_bytes,
            ndim=1,
        )
    except BoundedNumericNPZError as exc:
        if exc.reason in {
            "npz_end_record_missing",
            "npz_layout_unsupported",
            "npz_array_non_finite",
        }:
            raise StateSnapshotInputReadRefusal(
                f"state_snapshot_{exc.reason}", usage=current_usage()
            ) from exc
        refuse(
            f"state_snapshot_{exc.reason}",
            observed_bytes=exc.observed_bytes,
            limit_bytes=exc.limit_bytes,
        )
    entry_count = len(decoded)
    arrays = list(zip(slot_ids, decoded, strict=True))
    elements = sum(array.size for array in decoded)
    usage = current_usage()
    if usage.observed_source_bytes is None or usage.payload_integrity_verified is not True:
        refuse("state_snapshot_input_read_measurement_or_integrity_not_established")
    return BoundedStateSnapshotInputs(
        snapshot_ref=snapshot_ref,
        snapshot=snapshot,
        snapshot_manifest=bounded.manifest,
        state_blob_ref=snapshot.state_ref,
        arrays=tuple(arrays),
        observed_snapshot_manifest_bytes=usage.observed_snapshot_manifest_bytes,
        observed_snapshot_manifest_verification_bytes=(
            usage.observed_snapshot_manifest_verification_bytes
        ),
        observed_snapshot_payload_bytes=usage.observed_snapshot_payload_bytes,
        observed_blob_manifest_bytes=usage.observed_blob_manifest_bytes,
        observed_blob_manifest_verification_bytes=(usage.observed_blob_manifest_verification_bytes),
        observed_blob_bytes=usage.observed_blob_bytes,
        observed_entries=entry_count,
        observed_elements=elements,
        snapshot_payload_integrity_verified=True,
        state_blob_payload_integrity_verified=True,
    )


class _SnapshotStateLayoutError(ValueError):
    """State bytes are valid, but do not reconstruct the canonical GlobalState."""


@dataclasses.dataclass(frozen=True)
class _SnapshotLeaf:
    key: str


@dataclasses.dataclass(frozen=True)
class _SnapshotScalar:
    value: Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_state_snapshot(
    store: CoreJSONArtifactStore, *, snapshot_ref: ArtifactRef | ArtifactID | str
) -> GlobalState:
    """Load state snapshot."""
    snapshot = load_model(store, snapshot_ref, StateSnapshot)
    if snapshot.layout is not None or "layout" in snapshot.model_fields_set:
        raise _SnapshotStateLayoutError(
            "Snapshot layout is explicit and cannot be reconstructed as canonical GlobalState"
        )
    _validate_snapshot_lineage(store, snapshot_ref=snapshot_ref, snapshot=snapshot)
    # v2.0/v2.1 persisted the state-blob edge by bare artifact ID. Preserve
    # that historical projection even when the payload happens to contain a
    # newer selected-view marker. The full-state reader uses v2.2 exact-view lineage;
    # v2.3 also binds its selected blob view but is rejected above as sparse input.
    state_blob_ref: ArtifactRef | ArtifactID = snapshot.state_ref
    if snapshot.schema_version in {"2.0", "2.1"}:
        state_blob_ref = snapshot.state_ref.artifact_id
    try:
        data = store.get_bytes(state_blob_ref)
    except ArtifactIntegrityError as exc:
        raise ValueError(f"Snapshot checksum mismatch: {exc}") from exc
    _validate_snapshot_blob(snapshot, data)
    with np.load(BytesIO(data), allow_pickle=False) as blob:
        nested = _nest_state_from_keys(blob.files)
        try:
            _validate_legacy_global_state_layout(GlobalState, nested)
        except (TypeError, ValueError) as exc:
            raise _SnapshotStateLayoutError(
                "Snapshot state layout is incompatible with canonical GlobalState"
            ) from exc
        try:
            cpu_devices = list(jax.devices("cpu"))
        except (RuntimeError, TypeError, ValueError):
            cpu_devices = []
        try:
            if cpu_devices:
                with jax.default_device(cpu_devices[0]):
                    return _build_dataclass(GlobalState, nested, blob=blob)
            return _build_dataclass(GlobalState, nested, blob=blob)
        except Exception as exc:
            raise _SnapshotStateLayoutError(
                "Snapshot state layout is incompatible with canonical GlobalState"
            ) from exc


def _validate_snapshot_lineage(
    store: ArtifactStore,
    *,
    snapshot_ref: ArtifactRef | ArtifactID | str,
    snapshot: StateSnapshot,
) -> None:
    """Validate historical bare lineage or the current exact-view lineage."""
    if snapshot.schema_version == "2.0":
        return
    if snapshot.schema_version not in StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION:
        raise ValueError(f"Unsupported StateSnapshot schema_version: {snapshot.schema_version}")
    if snapshot.lineage_inputs is None:
        raise ValueError(f"StateSnapshot {snapshot.schema_version} payload missing lineage_inputs")

    if snapshot.schema_version == "2.1":
        # Historical 2.1 records serialized the state_ref object but bound the
        # manifest edge and reader to its bare artifact ID. Do not reinterpret
        # those persisted bytes as exact-view authority.
        expected_state_blob = InputRef(
            artifact_id=snapshot.state_ref.artifact_id, role="state_blob"
        )
        manifest_ref: ArtifactRef | ArtifactID | str = (
            snapshot_ref.artifact_id if isinstance(snapshot_ref, ArtifactRef) else snapshot_ref
        )
    else:
        expected_state_blob = artifact_input_ref(snapshot.state_ref, role="state_blob")
        manifest_ref = snapshot_ref
    schema_version = StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION[
        snapshot.schema_version
    ]

    if not snapshot.lineage_inputs or snapshot.lineage_inputs[-1] != expected_state_blob:
        raise ValueError(
            f"StateSnapshot {snapshot.schema_version} lineage must end with state_blob"
        )
    manifest = store.get_manifest(manifest_ref)
    expected_schema = SchemaInfo(name="polisyos.core.StateSnapshot", version=schema_version)
    if manifest.artifact_schema != expected_schema:
        raise ValueError(
            f"StateSnapshot {snapshot.schema_version} manifest schema does not match payload"
        )
    if manifest.inputs != snapshot.lineage_inputs:
        raise ValueError(
            f"StateSnapshot {snapshot.schema_version} lineage does not match manifest inputs"
        )


@dataclass(frozen=True, slots=True)
class StateSnapshotValueLeaf:
    """One exact consumed snapshot-codec value, without contextual CAS identity."""

    path: str
    dtype: str
    shape: tuple[int, ...]
    value_bytes: bytes

    @property
    def value_sha256(self) -> str:
        """Derive a compact receipt digest after the exact value has been read."""

        return hashlib.sha256(self.value_bytes).hexdigest()


def state_snapshot_value_projection(state: GlobalState) -> tuple[StateSnapshotValueLeaf, ...]:
    """Project every state-codec leaf's path, dtype, shape and exact value bytes.

    The codec's own complete flattener supplies the denominator; no slot list or
    scalar proxy is maintained here. Array order, signed zero and native numeric
    dtype remain observable. The projection describes the values persisted and
    read by this snapshot codec, not all NCM, profile, eligibility or N6 inputs.
    It does not make a supplied state an admitted artifact or complete basis.

    Args:
        state: Complete GlobalState produced or loaded through its real owner.

    Returns:
        Immutable, path-sorted complete snapshot value observations.

    Raises:
        TypeError: If the state or a value is unsupported by the snapshot codec.
        ValueError: If the codec encounters duplicate paths or object arrays.
    """

    if type(state) is not GlobalState:
        raise TypeError("state_value_projection_requires_global_state")
    result: list[StateSnapshotValueLeaf] = []
    paths: set[str] = set()
    for path, value in _flatten_state(state):
        if path in paths or value.dtype.hasobject:
            raise ValueError("state_value_projection_codec_value_not_established")
        paths.add(path)
        result.append(
            StateSnapshotValueLeaf(
                path=path,
                dtype=value.dtype.str,
                shape=tuple(value.shape),
                value_bytes=value.tobytes(order="C"),
            )
        )
    return tuple(sorted(result, key=lambda leaf: leaf.path))


def put_state_snapshot(
    store: ArtifactStore,
    *,
    state: Any,
    step: int | None = None,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> StateSnapshotRef:
    """Persist dataclass state or a flat numeric slot map as an NPZ snapshot.

    Flat slot maps are sparse method-input captures. Their consumer is
    ``read_state_snapshot_inputs_bounded``; ``load_state_snapshot`` remains the
    GlobalState reconstruction path.
    """
    _validate_return_selected_profile(return_selected_profile)
    if return_selected_profile:
        _require_return_selected_profile_writer(store, "put_bytes")
        _require_return_selected_profile_writer(store, "put_json")
    flat = dict(_flatten_state(state))
    buf = BytesIO()
    np.savez(buf, **flat)
    blob_bytes = buf.getvalue()
    checksum = hashlib.sha256(blob_bytes).hexdigest()
    blob_ref = _put_snapshot_blob_two_phase(
        store,
        blob_bytes,
        # The raw NPZ is content-addressed and must not inherit contextual
        # lineage.  The typed wrapper below carries the exact ordered input
        # lineage while identical bytes remain reusable across contexts.
        PutOptions(kind="foundry.state_blob", media_type="application/x-npz"),
        return_selected_profile=return_selected_profile,
    )
    if str(blob_ref.artifact_id.hex) != checksum:
        raise ValueError(
            "Snapshot blob checksum mismatch after CAS write: "
            f"{blob_ref.artifact_id.hex} != {checksum}"
        )
    snapshot_inputs = list(inputs or [])
    snapshot_inputs.append(artifact_input_ref(blob_ref, role="state_blob"))
    is_method_input_snapshot = isinstance(state, Mapping) and not dataclasses.is_dataclass(state)
    payload_schema_version = (
        StateSnapshot.METHOD_INPUT_SCHEMA_VERSION if is_method_input_snapshot else "2.2"
    )
    snapshot_values: dict[str, Any] = {
        "schema_version": payload_schema_version,
        "state_ref": blob_ref,
        "step": step,
        "format_version": _SNAPSHOT_FORMAT_VERSION,
        "checksum_sha256": checksum,
        "entry_count": len(flat),
        "codec": _SNAPSHOT_CODEC,
        "lineage_inputs": snapshot_inputs,
        "notes": [f"snapshot_format:{_SNAPSHOT_FORMAT_VERSION}"],
    }
    if is_method_input_snapshot:
        snapshot_values["layout"] = StateSnapshot.METHOD_INPUT_LAYOUT
    snapshot = StateSnapshot(**snapshot_values)
    snapshot_ref = store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.StateSnapshot",
                version=StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION[
                    payload_schema_version
                ],
            ),
            inputs=snapshot_inputs,
        ),
        return_selected_profile=return_selected_profile,
    )
    return StateSnapshotRef.model_validate(snapshot_ref.model_dump(mode="python"))


def export_seed_state_npz(state: GlobalState, path: str | Path) -> Path:
    """Write a seed GlobalState to an NPZ file for deterministic fixture reuse."""
    destination = Path(path)
    flat = dict(_flatten_state(state))
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez(destination, **flat)
    return destination


def import_seed_state_npz(path: str | Path) -> GlobalState:
    """Load a seed GlobalState from an NPZ file produced by the exporter."""
    with np.load(Path(path), allow_pickle=False) as loaded:
        nested = _nest_state_from_keys(loaded.files)
        try:
            _validate_legacy_global_state_layout(GlobalState, nested)
        except (TypeError, ValueError) as exc:
            raise _SnapshotStateLayoutError(
                "Seed snapshot state layout is incompatible with canonical GlobalState"
            ) from exc
        try:
            cpu_devices = list(jax.devices("cpu"))
        except (RuntimeError, TypeError, ValueError):
            cpu_devices = []
        if cpu_devices:
            with jax.default_device(cpu_devices[0]):
                return _build_dataclass(GlobalState, nested, blob=loaded)
        return _build_dataclass(GlobalState, nested, blob=loaded)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flatten_state(obj: Any, prefix: str = "") -> Iterable[tuple[str, np.ndarray]]:
    """Flatten dataclass state or one bounded, named sparse input map."""
    stack: list[tuple[Any, str]] = [(obj, prefix)]
    while stack:
        current, current_prefix = stack.pop()
        if current is None:
            continue
        if dataclasses.is_dataclass(current):
            fields = list(dataclasses.fields(current))
            for field in reversed(fields):
                stack.append((getattr(current, field.name), f"{current_prefix}{field.name}."))
            continue
        if isinstance(current, Mapping):
            if current_prefix:
                raise ValueError("Sparse snapshot input maps must be at the root")
            if not current:
                raise ValueError("Cannot snapshot an empty mapping")
            items = list(current.items())
            if len(items) > _MAX_BOUNDED_INPUT_ENTRIES:
                raise ValueError("Snapshot input mapping exceeds the slot limit")
            if any(not _is_snapshot_slot_id(name) for name, _value in items) or len(
                {name for name, _value in items}
            ) != len(items):
                raise ValueError("Invalid snapshot mapping key")
            total_elements = 0
            for name, value in items:
                if type(value) is not np.ndarray:
                    raise TypeError("Snapshot input mappings require NumPy arrays")
                if (
                    value.ndim != 1
                    or value.size == 0
                    or value.dtype.hasobject
                    or value.dtype.kind not in {"i", "u", "f"}
                    or (value.dtype.kind == "f" and not np.isfinite(value).all())
                ):
                    raise ValueError("Snapshot input arrays must be finite numeric vectors")
                total_elements += int(value.size)
                if total_elements > _MAX_BOUNDED_INPUT_ELEMENTS:
                    raise ValueError("Snapshot input mapping exceeds the element limit")
            for name, value in sorted(items, key=lambda item: item[0], reverse=True):
                stack.append((value, f"{name}."))
            continue
        key = current_prefix[:-1]
        if not key:
            raise ValueError("Cannot snapshot an unnamed scalar root")
        if isinstance(current, BaseModel):
            yield key, np.asarray(current.model_dump_json())
            continue
        if isinstance(current, (jax.Array, np.ndarray)):
            yield key, np.asarray(current)
            continue
        if isinstance(current, (bool, int, float, np.bool_, np.integer, np.floating)):
            yield key, np.asarray(current)
            continue
        raise TypeError(f"Unsupported snapshot value at '{key}': {type(current).__name__}")


def _nest_state(flat: dict[str, np.ndarray]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = _SnapshotScalar(value)
    return nested


def _nest_state_from_keys(keys: Iterable[str]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for key in sorted(keys):
        parts = key.split(".")
        if not parts or any(not part for part in parts):
            raise ValueError(f"Invalid snapshot key: {key!r}")
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
            if not isinstance(current, dict):
                raise ValueError(f"Snapshot key collision at: {key!r}")
        current[parts[-1]] = _SnapshotLeaf(key)
    return nested


def _field_default(field: dataclasses.Field[Any]) -> Any:
    if field.default is not dataclasses.MISSING:
        return field.default
    if field.default_factory is not dataclasses.MISSING:
        return field.default_factory()
    return dataclasses.MISSING


def _resolve_nested_dataclass_type(field_type: Any) -> tuple[type[Any] | None, bool]:
    if dataclasses.is_dataclass(field_type):
        return field_type, False

    origin = get_origin(field_type)
    if origin not in (Union, UnionType):
        return None, False

    args = [arg for arg in get_args(field_type) if arg is not type(None)]
    if len(args) != 1:
        return None, False

    candidate = args[0]
    if dataclasses.is_dataclass(candidate):
        return candidate, True
    return None, False


def _resolve_basemodel_type(field_type: Any) -> tuple[type[BaseModel] | None, bool]:
    if isinstance(field_type, type) and issubclass(field_type, BaseModel):
        return field_type, False

    origin = get_origin(field_type)
    if origin not in (Union, UnionType):
        return None, False

    args = [arg for arg in get_args(field_type) if arg is not type(None)]
    if len(args) != 1:
        return None, False

    candidate = args[0]
    if isinstance(candidate, type) and issubclass(candidate, BaseModel):
        return candidate, True
    return None, False


def _build_dataclass(cls, data: dict[str, Any], *, blob: Any | None = None) -> Any:
    if not dataclasses.is_dataclass(cls):
        raise ValueError(f"Expected dataclass type, got: {cls}")
    kwargs: dict[str, Any] = {}
    type_hints = _dataclass_type_hints(cls)
    for field in dataclasses.fields(cls):
        value = data.get(field.name, dataclasses.MISSING)
        field_type = type_hints.get(field.name, field.type)
        nested_cls, is_optional_nested = _resolve_nested_dataclass_type(field_type)
        model_cls, is_optional_model = _resolve_basemodel_type(field_type)
        default = _field_default(field)
        if nested_cls is not None:
            if value is dataclasses.MISSING or value is None:
                if default is not dataclasses.MISSING:
                    kwargs[field.name] = default
                    continue
                if is_optional_nested:
                    kwargs[field.name] = None
                    continue
                raise ValueError(f"Missing nested data for '{field.name}'")
            if not isinstance(value, dict):
                raise ValueError(f"Missing nested data for '{field.name}'")
            kwargs[field.name] = _build_dataclass(nested_cls, value, blob=blob)
        elif model_cls is not None:
            if value is dataclasses.MISSING or value is None:
                if default is not dataclasses.MISSING:
                    kwargs[field.name] = default
                    continue
                if is_optional_model:
                    kwargs[field.name] = None
                    continue
                raise ValueError(f"Missing model data for '{field.name}'")
            kwargs[field.name] = _decode_model_leaf(value, blob=blob, model_cls=model_cls)
        else:
            if value is dataclasses.MISSING or value is None:
                if default is not dataclasses.MISSING:
                    kwargs[field.name] = default
                    continue
                raise ValueError(f"Missing value for '{field.name}'")
            kwargs[field.name] = _decode_snapshot_leaf(value, blob=blob)
    return cls(**kwargs)


def _validate_legacy_global_state_layout(cls: type[Any], data: dict[str, Any]) -> None:
    """Require an untyped historical NPZ to contain a complete GlobalState shape."""
    if not dataclasses.is_dataclass(cls) or not isinstance(data, dict):
        raise ValueError("legacy_state_snapshot_layout_not_a_dataclass_mapping")
    known_fields = {field.name: field for field in dataclasses.fields(cls)}
    if set(data) - set(known_fields):
        raise ValueError("legacy_state_snapshot_has_unknown_fields")
    type_hints = _dataclass_type_hints(cls)
    for field_name, field in known_fields.items():
        if field_name not in data:
            has_default = (
                field.default is not dataclasses.MISSING
                or field.default_factory is not dataclasses.MISSING
            )
            field_type = type_hints.get(field_name, field.type)
            _nested_cls, optional_nested = _resolve_nested_dataclass_type(field_type)
            _model_cls, optional_model = _resolve_basemodel_type(field_type)
            if not has_default and not optional_nested and not optional_model:
                raise ValueError("legacy_state_snapshot_missing_required_field")
            continue
        value = data[field_name]
        field_type = type_hints.get(field_name, field.type)
        nested_cls, _optional_nested = _resolve_nested_dataclass_type(field_type)
        model_cls, _optional_model = _resolve_basemodel_type(field_type)
        if nested_cls is not None:
            if not isinstance(value, dict):
                raise ValueError("legacy_state_snapshot_nested_field_is_not_a_mapping")
            _validate_legacy_global_state_layout(nested_cls, value)
        elif model_cls is not None:
            if not isinstance(value, (_SnapshotLeaf, _SnapshotScalar)):
                raise ValueError("legacy_state_snapshot_model_field_is_not_a_leaf")
        elif not isinstance(value, (_SnapshotLeaf, _SnapshotScalar)):
            raise ValueError("legacy_state_snapshot_value_field_is_not_a_leaf")


def _decode_model_leaf(
    value: Any,
    *,
    blob: Any | None,
    model_cls: type[BaseModel],
) -> BaseModel:
    if isinstance(value, _SnapshotLeaf):
        if blob is None:
            raise ValueError(f"Snapshot leaf '{value.key}' requires an open NPZ blob")
        raw = blob[value.key]
    elif isinstance(value, _SnapshotScalar):
        raw = value.value
    else:
        raw = value
    scalar = np.asarray(raw).reshape(()).item()
    if isinstance(scalar, bytes):
        scalar = scalar.decode("utf-8")
    if not isinstance(scalar, str):
        raise ValueError(f"Snapshot model leaf must be a JSON string, got {type(scalar).__name__}")
    if model_cls is ValueOuterSet:
        return ValueOuterSet.from_persisted_payload(scalar)
    return model_cls.model_validate_json(scalar)


def _decode_snapshot_leaf(value: Any, *, blob: Any | None) -> Any:
    if isinstance(value, _SnapshotLeaf):
        if blob is None:
            raise ValueError(f"Snapshot leaf '{value.key}' requires an open NPZ blob")
        return jnp.asarray(blob[value.key])
    if isinstance(value, _SnapshotScalar):
        return jnp.asarray(value.value)
    return jnp.asarray(value)


def _dataclass_type_hints(cls: type[Any]) -> dict[str, Any]:
    try:
        return get_type_hints(cls)
    except (NameError, TypeError, AttributeError):
        return {}


def _validate_snapshot_blob(snapshot: StateSnapshot, data: bytes) -> None:
    if snapshot.format_version not in {"npz-v1", _SNAPSHOT_FORMAT_VERSION}:
        raise ValueError(f"Unsupported snapshot format_version: {snapshot.format_version}")
    if snapshot.codec not in {"numpy-npz", _SNAPSHOT_CODEC}:
        raise ValueError(f"Unsupported snapshot codec: {snapshot.codec}")
    if snapshot.checksum_sha256 is not None:
        actual = hashlib.sha256(data).hexdigest()
        if actual != snapshot.checksum_sha256:
            raise ValueError(f"Snapshot checksum mismatch: {actual} != {snapshot.checksum_sha256}")


def _put_snapshot_blob_two_phase(
    store: ArtifactStore,
    data: bytes,
    options: PutOptions,
    *,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    blob_ref = store.put_bytes(data, options, return_selected_profile=return_selected_profile)
    if not store.has(blob_ref):
        raise ValueError(f"Snapshot blob was not fully persisted: {blob_ref.artifact_id}")
    return blob_ref
