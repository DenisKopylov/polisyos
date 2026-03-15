"""
Compilation specialization for deterministic caching (Law H).

This module implements deterministic cache keys for JAX compilation by
capturing all compilation-affecting factors in a frozen dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.core.canon import content_hash, truncated_hash

__all__ = [
    "ShapeSpec",
    "BackendSpec",
    "Specialization",
    "build_specialization",
    "compute_static_params_hash",
    "specialization_from_signature_and_state",
]


# =============================================================================
# Shape Specification
# =============================================================================


@dataclass(frozen=True, slots=True)
class ShapeSpec:
    """
    Shape specification for an input slot.

    Captures array shape and dtype, which affect XLA compilation.
    """

    shape: tuple[int, ...]
    dtype: str

    @classmethod
    def from_array(cls, arr: jnp.ndarray) -> "ShapeSpec":
        """Create ShapeSpec from a JAX/NumPy array."""
        return cls(
            shape=tuple(int(d) for d in arr.shape),
            dtype=str(arr.dtype),
        )

    def __hash__(self) -> int:  # pragma: no cover - trivial
        return hash((self.shape, self.dtype))

    def __eq__(self, other: object) -> bool:  # pragma: no cover - trivial
        if not isinstance(other, ShapeSpec):
            return NotImplemented
        return self.shape == other.shape and self.dtype == other.dtype

    @property
    def canonical_str(self) -> str:
        """Canonical string representation for hashing."""
        shape_str = ",".join(str(d) for d in self.shape)
        return f"({shape_str}):{self.dtype}"

    @property
    def ndim(self) -> int:
        """Number of dimensions."""
        return len(self.shape)

    @property
    def size(self) -> int:
        """Total number of elements."""
        result = 1
        for d in self.shape:
            result *= d
        return result


# =============================================================================
# Backend Specification
# =============================================================================


def _read_config_value(name: str) -> Any | None:
    try:
        return jax.config.read(name)
    except Exception:
        return None


def _config_fingerprint() -> str:
    payload: dict[str, Any] = {}
    for key in (
        "jax_enable_x64",
        "jax_default_matmul_precision",
        "jax_default_dtype_bits",
        "jax_numpy_rank_promotion",
    ):
        value = _read_config_value(key)
        if value is not None:
            payload[key] = value
    if not payload:
        return ""
    try:
        from polisyos.core.canon import to_canonical_bytes

        canonical = to_canonical_bytes(payload)
    except Exception:
        import json

        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    return truncated_hash(canonical, length=16)


@dataclass(frozen=True, slots=True)
class BackendSpec:
    """
    JAX backend specification.

    Captures platform, devices, precision, and config that affect compilation.
    """

    platform: str
    device_count: int
    precision: str
    xla_flags: frozenset[str] = frozenset()
    device_kinds: tuple[str, ...] = ()
    jax_version: str = ""
    jaxlib_version: str = ""
    config_fingerprint: str = ""

    @classmethod
    def current(
        cls,
        precision: str = "float32",
        xla_flags: Sequence[str] | None = None,
    ) -> "BackendSpec":
        """
        Create BackendSpec from current JAX environment.
        """
        backend = jax.default_backend()
        devices = jax.devices()
        device_kinds = tuple(sorted({getattr(d, "device_kind", str(d)) for d in devices}))

        jax_version = getattr(jax, "__version__", "")
        jaxlib_version = ""
        try:
            import jaxlib  # type: ignore

            jaxlib_version = getattr(jaxlib, "__version__", "")
        except Exception:
            try:
                jaxlib_version = getattr(jax.lib.version, "__version__", "")
            except Exception:
                jaxlib_version = ""

        return cls(
            platform=str(backend),
            device_count=len(devices),
            precision=precision,
            xla_flags=frozenset(xla_flags or []),
            device_kinds=device_kinds,
            jax_version=jax_version,
            jaxlib_version=jaxlib_version,
            config_fingerprint=_config_fingerprint(),
        )

    def __hash__(self) -> int:  # pragma: no cover - trivial
        return hash(
            (
                self.platform,
                self.device_count,
                self.precision,
                self.xla_flags,
                self.device_kinds,
                self.jax_version,
                self.jaxlib_version,
                self.config_fingerprint,
            )
        )

    def __eq__(self, other: object) -> bool:  # pragma: no cover - trivial
        if not isinstance(other, BackendSpec):
            return NotImplemented
        return (
            self.platform == other.platform
            and self.device_count == other.device_count
            and self.precision == other.precision
            and self.xla_flags == other.xla_flags
            and self.device_kinds == other.device_kinds
            and self.jax_version == other.jax_version
            and self.jaxlib_version == other.jaxlib_version
            and self.config_fingerprint == other.config_fingerprint
        )

    @property
    def canonical_str(self) -> str:
        """Canonical string representation for hashing."""
        flags_str = ",".join(sorted(self.xla_flags)) if self.xla_flags else ""
        kinds_str = ",".join(self.device_kinds)
        return (
            f"{self.platform}:{self.device_count}:{self.precision}:"
            f"{flags_str}:{kinds_str}:{self.jax_version}:{self.jaxlib_version}:"
            f"{self.config_fingerprint}"
        )


# =============================================================================
# Main Specialization Key
# =============================================================================


@dataclass(frozen=True, slots=True)
class Specialization:
    """
    Complete specialization key for method compilation.

    Identical Specialization => identical compiled function.
    """

    method_fqn: str
    static_params_hash: str
    input_shapes: tuple[tuple[str, ShapeSpec], ...]
    backend: BackendSpec
    jit_enabled: bool = True
    vmap_axis: int | None = None
    donate_argnums: tuple[int, ...] = ()

    def __hash__(self) -> int:  # pragma: no cover - trivial
        return hash(
            (
                self.method_fqn,
                self.static_params_hash,
                self.input_shapes,
                self.backend,
                self.jit_enabled,
                self.vmap_axis,
                self.donate_argnums,
            )
        )

    def __eq__(self, other: object) -> bool:  # pragma: no cover - trivial
        if not isinstance(other, Specialization):
            return NotImplemented
        return (
            self.method_fqn == other.method_fqn
            and self.static_params_hash == other.static_params_hash
            and self.input_shapes == other.input_shapes
            and self.backend == other.backend
            and self.jit_enabled == other.jit_enabled
            and self.vmap_axis == other.vmap_axis
            and self.donate_argnums == other.donate_argnums
        )

    @property
    def cache_key(self) -> str:
        """
        Generate deterministic cache key string.

        Returns a 32-character hexadecimal SHA256 digest.
        """
        components = [
            f"fqn={self.method_fqn}",
            f"static={self.static_params_hash}",
            f"shapes={self._shapes_canonical_str()}",
            f"backend={self.backend.canonical_str}",
            f"jit={self.jit_enabled}",
            f"vmap={self.vmap_axis}",
            f"donate={','.join(str(i) for i in self.donate_argnums)}",
        ]
        combined = "|".join(components)
        return truncated_hash(combined, length=32)

    def _shapes_canonical_str(self) -> str:
        parts = [f"{name}:{spec.canonical_str}" for name, spec in self.input_shapes]
        return ",".join(parts)

    @property
    def signature_summary(self) -> str:
        shape_info = ", ".join(
            f"{name}: {spec.shape}" for name, spec in self.input_shapes
        )
        return (
            f"{self.method_fqn} "
            f"[{self.backend.platform}/{self.backend.precision}] "
            f"({shape_info})"
        )


# =============================================================================
# Helper Functions
# =============================================================================


def _array_digest(value: Any) -> dict[str, Any]:
    arr = np.asarray(value)
    if arr.dtype == object:
        raise TypeError("object dtype arrays are not supported in static params")
    arr = np.ascontiguousarray(arr)
    payload = (
        arr.tobytes(order="C")
        + str(arr.dtype).encode("utf-8")
        + str(tuple(arr.shape)).encode("utf-8")
    )
    return {
        "_type": "array_digest",
        "dtype": str(arr.dtype),
        "shape": list(arr.shape),
        "sha256": content_hash(payload),
    }


def _convert_value_for_canonical(value: Any) -> Any:
    """
    Convert a value to a canonical-serializable form.

    Handles arrays, floats, and other types before to_canonical_bytes().
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        b = bytes(value)
        return {"_type": "bytes_hex", "value": b.hex()}

    if isinstance(value, np.generic):
        if np.issubdtype(value.dtype, np.bool_):
            return bool(value)
        if np.issubdtype(value.dtype, np.integer):
            return int(value)
        if np.issubdtype(value.dtype, np.floating):
            return {"_type": "float_hex", "value": float(value).hex()}

    if hasattr(value, "shape") and hasattr(value, "dtype"):
        return _array_digest(value)

    if isinstance(value, float):
        return {"_type": "float_hex", "value": value.hex()}

    if isinstance(value, Decimal):
        return {"_type": "decimal", "value": str(value)}

    if isinstance(value, Mapping):
        return {k: _convert_value_for_canonical(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)) and not isinstance(value, str):
        return [_convert_value_for_canonical(v) for v in value]

    return value


def compute_static_params_hash(params: Mapping[str, Any]) -> str:
    """
    Compute deterministic hash of static parameters.

    Uses canonical JSON serialization to ensure identical parameters always
    produce identical hashes, regardless of key order.
    """
    sorted_params = {
        k: _convert_value_for_canonical(v)
        for k, v in sorted(params.items())
    }

    try:
        from polisyos.core.canon import to_canonical_bytes

        canonical = to_canonical_bytes(sorted_params)
    except Exception:
        import json

        canonical = json.dumps(
            sorted_params,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

    return truncated_hash(canonical, length=32)


def build_specialization(
    method_fqn: str,
    static_params: Mapping[str, Any],
    input_arrays: Mapping[str, jnp.ndarray],
    *,
    backend: BackendSpec | None = None,
    jit_enabled: bool = True,
    vmap_axis: int | None = None,
    donate_argnums: tuple[int, ...] = (),
) -> Specialization:
    """
    Build specialization from runtime context.
    """
    return Specialization(
        method_fqn=method_fqn,
        static_params_hash=compute_static_params_hash(static_params),
        input_shapes=tuple(
            (name, ShapeSpec.from_array(arr))
            for name, arr in sorted(input_arrays.items())
        ),
        backend=backend or BackendSpec.current(),
        jit_enabled=jit_enabled,
        vmap_axis=vmap_axis,
        donate_argnums=donate_argnums,
    )


def specialization_from_signature_and_state(
    method_fqn: str,
    static_params: Mapping[str, Any],
    signature_input_slots: frozenset,
    state: Any,
    *,
    backend: BackendSpec | None = None,
    jit_enabled: bool = True,
) -> Specialization:
    """
    Build specialization by extracting shapes from a state object.
    """
    input_arrays: dict[str, jnp.ndarray] = {}

    for slot in signature_input_slots:
        slot_name = getattr(slot, "name", None)
        if not slot_name:
            continue
        if hasattr(state, slot_name):
            arr = getattr(state, slot_name)
            if hasattr(arr, "shape"):
                input_arrays[slot_name] = arr

    return build_specialization(
        method_fqn=method_fqn,
        static_params=static_params,
        input_arrays=input_arrays,
        backend=backend,
        jit_enabled=jit_enabled,
    )
