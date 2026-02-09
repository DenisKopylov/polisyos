"""State snapshot persistence — load, put, flatten, nest, build."""
from __future__ import annotations

import dataclasses
from io import BytesIO
from typing import Any, Iterable

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.foundry.domain.state import GlobalState

from ._executor_models import load_model

__all__ = [
    "load_state_snapshot",
    "put_state_snapshot",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_state_snapshot(
    store: FileSystemCAS, *, snapshot_ref: ArtifactRef | ArtifactID | str
) -> GlobalState:
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flatten_state(obj: Any, prefix: str = "") -> Iterable[tuple[str, np.ndarray]]:
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


def _build_dataclass(cls, data: dict[str, Any]) -> Any:  # noqa: ANN001
    if not dataclasses.is_dataclass(cls):
        raise ValueError(f"Expected dataclass type, got: {cls}")
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        value = data.get(field.name)
        if dataclasses.is_dataclass(field.type):
            if not isinstance(value, dict):
                raise ValueError(f"Missing nested data for '{field.name}'")
            kwargs[field.name] = _build_dataclass(field.type, value)
        else:
            if value is None:
                raise ValueError(f"Missing value for '{field.name}'")
            kwargs[field.name] = jnp.asarray(value)
    return cls(**kwargs)
