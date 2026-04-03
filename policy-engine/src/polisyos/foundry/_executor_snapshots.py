"""State snapshot persistence — load, put, flatten, nest, build."""
from __future__ import annotations

import dataclasses
from io import BytesIO
from pathlib import Path
from types import UnionType
from typing import Any, Iterable, Union, get_args, get_origin

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.foundry.contracts.state import GlobalState

from ._executor_models import load_model

__all__ = [
    "export_seed_state_npz",
    "import_seed_state_npz",
    "load_state_snapshot",
    "put_state_snapshot",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_state_snapshot(
    store: FileSystemCAS, *, snapshot_ref: ArtifactRef | ArtifactID | str
) -> GlobalState:
    """Load state snapshot."""
    snapshot = load_model(store, snapshot_ref, StateSnapshot)
    data = store.get_bytes(snapshot.state_ref.artifact_id)
    blob = np.load(BytesIO(data))
    flat = {key: blob[key] for key in blob.files}
    nested = _nest_state(flat)
    try:
        cpu_devices = list(jax.devices("cpu"))
    except Exception:
        cpu_devices = []
    if cpu_devices:
        with jax.default_device(cpu_devices[0]):
            return _build_dataclass(GlobalState, nested)
    return _build_dataclass(GlobalState, nested)


def put_state_snapshot(
    store: FileSystemCAS,
    *,
    state: Any,
    step: int | None = None,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Put state snapshot helper."""
    flat = dict(_flatten_state(state))
    buf = BytesIO()
    np.savez(buf, **flat)
    blob_ref = store.put_bytes(
        buf.getvalue(),
        PutOptions(kind="foundry.state_blob", media_type="application/x-npz", inputs=inputs),
    )
    snapshot = StateSnapshot(state_ref=blob_ref, step=step)
    snapshot_inputs = list(inputs or [])
    snapshot_inputs.append(InputRef(artifact_id=blob_ref.artifact_id, role="state_blob"))
    return store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="0.1.0"),
            inputs=snapshot_inputs,
        ),
    )


def export_seed_state_npz(state: GlobalState, path: str | Path) -> Path:
    """Export seed state npz helper."""
    destination = Path(path)
    flat = dict(_flatten_state(state))
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez(destination, **flat)
    return destination


def import_seed_state_npz(path: str | Path) -> GlobalState:
    """Import seed state npz helper."""
    with np.load(Path(path), allow_pickle=False) as loaded:
        flat = {key: loaded[key] for key in loaded.files}
    nested = _nest_state(flat)
    try:
        cpu_devices = list(jax.devices("cpu"))
    except Exception:
        cpu_devices = []
    if cpu_devices:
        with jax.default_device(cpu_devices[0]):
            return _build_dataclass(GlobalState, nested)
    return _build_dataclass(GlobalState, nested)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flatten_state(obj: Any, prefix: str = "") -> Iterable[tuple[str, np.ndarray]]:
    if obj is None:
        return
    if dataclasses.is_dataclass(obj):
        for field in dataclasses.fields(obj):
            name = field.name
            value = getattr(obj, name)
            yield from _flatten_state(value, f"{prefix}{name}.")
        return
    if isinstance(obj, (jax.Array, np.ndarray)):
        key = prefix[:-1]
        yield key, np.asarray(obj)
        return


def _nest_state(flat: dict[str, np.ndarray]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
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


def _build_dataclass(cls, data: dict[str, Any]) -> Any:  # noqa: ANN001
    if not dataclasses.is_dataclass(cls):
        raise ValueError(f"Expected dataclass type, got: {cls}")
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        value = data.get(field.name, dataclasses.MISSING)
        nested_cls, is_optional_nested = _resolve_nested_dataclass_type(field.type)
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
            kwargs[field.name] = _build_dataclass(nested_cls, value)
        else:
            if value is dataclasses.MISSING or value is None:
                if default is not dataclasses.MISSING:
                    kwargs[field.name] = default
                    continue
                raise ValueError(f"Missing value for '{field.name}'")
            kwargs[field.name] = jnp.asarray(value)
    return cls(**kwargs)
