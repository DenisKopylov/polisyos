"""State snapshot persistence — load, put, flatten, nest, build."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

import jax
import jax.numpy as jnp
import numpy as np
from pydantic import BaseModel

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import ArtifactIntegrityError, FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.core.contracts.value_outer_set import ValueOuterSet
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.models import load_model

__all__ = [
    "export_seed_state_npz",
    "import_seed_state_npz",
    "load_state_snapshot",
    "put_state_snapshot",
]

_SNAPSHOT_FORMAT_VERSION = "npz-v2"
_SNAPSHOT_CODEC = "numpy-npz"


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
    store: FileSystemCAS, *, snapshot_ref: ArtifactRef | ArtifactID | str
) -> GlobalState:
    """Load state snapshot."""
    snapshot = load_model(store, snapshot_ref, StateSnapshot)
    try:
        data = store.get_bytes(snapshot.state_ref.artifact_id)
    except ArtifactIntegrityError as exc:
        raise ValueError(f"Snapshot checksum mismatch: {exc}") from exc
    _validate_snapshot_blob(snapshot, data)
    with np.load(BytesIO(data), allow_pickle=False) as blob:
        nested = _nest_state_from_keys(blob.files)
        try:
            cpu_devices = list(jax.devices("cpu"))
        except (RuntimeError, TypeError, ValueError):
            cpu_devices = []
        if cpu_devices:
            with jax.default_device(cpu_devices[0]):
                return _build_dataclass(GlobalState, nested, blob=blob)
        return _build_dataclass(GlobalState, nested, blob=blob)


def put_state_snapshot(
    store: FileSystemCAS,
    *,
    state: Any,
    step: int | None = None,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a GlobalState-compatible object as a checksummed NPZ snapshot."""
    flat = dict(_flatten_state(state))
    buf = BytesIO()
    np.savez(buf, **flat)
    blob_bytes = buf.getvalue()
    checksum = hashlib.sha256(blob_bytes).hexdigest()
    blob_ref = _put_snapshot_blob_two_phase(
        store,
        blob_bytes,
        PutOptions(kind="foundry.state_blob", media_type="application/x-npz", inputs=inputs),
    )
    if str(blob_ref.artifact_id.hex) != checksum:
        raise ValueError(
            "Snapshot blob checksum mismatch after CAS write: "
            f"{blob_ref.artifact_id.hex} != {checksum}"
        )
    snapshot = StateSnapshot(
        state_ref=blob_ref,
        step=step,
        format_version=_SNAPSHOT_FORMAT_VERSION,
        checksum_sha256=checksum,
        entry_count=len(flat),
        codec=_SNAPSHOT_CODEC,
        notes=[f"snapshot_format:{_SNAPSHOT_FORMAT_VERSION}"],
    )
    snapshot_inputs = list(inputs or [])
    snapshot_inputs.append(InputRef(artifact_id=blob_ref.artifact_id, role="state_blob"))
    return store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="2.0.0"),
            inputs=snapshot_inputs,
        ),
    )


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
    store: FileSystemCAS,
    data: bytes,
    options: PutOptions,
) -> ArtifactRef:
    blob_ref = store.put_bytes(data, options)
    if not store.has(blob_ref.artifact_id):
        raise ValueError(f"Snapshot blob was not fully persisted: {blob_ref.artifact_id}")
    return blob_ref
