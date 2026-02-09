"""
Golden Record system for regression testing (Law M enforcement).

Provides content-addressed snapshots of method inputs and outputs that enable
regression detection across code and environment changes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any

import jax
import numpy as np

from polisyos.core.canon import content_hash, streaming_hash
from polisyos.foundry.methods.specialization import BackendSpec

try:  # JAX >= 0.4
    from jax.tree_util import tree_flatten_with_path
except Exception:  # pragma: no cover - fallback
    def tree_flatten_with_path(tree: Any):
        leaves, treedef = jax.tree_util.tree_flatten(tree)
        return [((), leaf) for leaf in leaves], treedef


# =============================================================================
# Constants
# =============================================================================


HASH_LENGTH = 32
GOLDEN_SCHEMA_VERSION = "1.0.0"
DEFAULT_RTOL = 1e-5
DEFAULT_ATOL = 1e-8


# =============================================================================
# Verification Result
# =============================================================================


class VerificationStatus(Enum):
    """Status of golden record verification."""

    PASSED = auto()
    FAILED_CONTEXT = auto()
    FAILED_INPUT = auto()
    FAILED_OUTPUT = auto()
    NO_RECORD = auto()
    ERROR = auto()


@dataclass(frozen=True, slots=True)
class GoldenVerificationResult:
    """Result of golden record verification."""

    status: VerificationStatus
    message: str
    expected_hash: str | None = None
    actual_hash: str | None = None
    context_match: bool = True

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED

    def __bool__(self) -> bool:
        return self.passed

    def __str__(self) -> str:
        return f"GoldenVerification({self.status.name}): {self.message}"


# =============================================================================
# Context
# =============================================================================


@dataclass(frozen=True, slots=True)
class GoldenContext:
    """
    Execution context for golden record (must match for valid comparison).
    """

    method_fqn: str
    backend: BackendSpec
    jax_version: str
    jaxlib_version: str
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def current(cls, method_fqn: str, precision: str = "float32") -> "GoldenContext":
        backend = BackendSpec.current(precision=precision)
        return cls(
            method_fqn=method_fqn,
            backend=backend,
            jax_version=backend.jax_version,
            jaxlib_version=backend.jaxlib_version,
        )

    def matches(
        self,
        other: "GoldenContext",
        *,
        strict_version: bool = False,
        strict_backend: bool = False,
    ) -> bool:
        if self.method_fqn != other.method_fqn:
            return False
        if self.backend.platform != other.backend.platform:
            return False
        if self.backend.precision != other.backend.precision:
            return False
        if strict_backend:
            if self.backend.device_count != other.backend.device_count:
                return False
            if self.backend.device_kinds != other.backend.device_kinds:
                return False
            if self.backend.xla_flags != other.backend.xla_flags:
                return False
            if self.backend.config_fingerprint != other.backend.config_fingerprint:
                return False
        if strict_version:
            if self.jax_version != other.jax_version:
                return False
            if self.jaxlib_version != other.jaxlib_version:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "method_fqn": self.method_fqn,
            "backend": {
                "platform": self.backend.platform,
                "device_count": self.backend.device_count,
                "precision": self.backend.precision,
                "xla_flags": sorted(self.backend.xla_flags),
                "device_kinds": list(self.backend.device_kinds),
                "jax_version": self.backend.jax_version,
                "jaxlib_version": self.backend.jaxlib_version,
                "config_fingerprint": self.backend.config_fingerprint,
            },
            "jax_version": self.jax_version,
            "jaxlib_version": self.jaxlib_version,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldenContext":
        backend_data = data.get("backend", {})
        backend = BackendSpec(
            platform=backend_data.get("platform", ""),
            device_count=int(backend_data.get("device_count", 1)),
            precision=backend_data.get("precision", "float32"),
            xla_flags=frozenset(backend_data.get("xla_flags", [])),
            device_kinds=tuple(backend_data.get("device_kinds", [])),
            jax_version=backend_data.get("jax_version", ""),
            jaxlib_version=backend_data.get("jaxlib_version", ""),
            config_fingerprint=backend_data.get("config_fingerprint", ""),
        )
        return cls(
            method_fqn=data.get("method_fqn", ""),
            backend=backend,
            jax_version=data.get("jax_version", backend.jax_version),
            jaxlib_version=data.get("jaxlib_version", backend.jaxlib_version),
            recorded_at=data.get("recorded_at", ""),
        )


# =============================================================================
# Pytree Hashing
# =============================================================================


def _path_to_bytes(path: tuple[Any, ...]) -> bytes:
    parts: list[str] = []
    for key in path:
        if hasattr(key, "key"):
            parts.append(f"dict:{key.key!r}")
        elif hasattr(key, "idx"):
            parts.append(f"seq:{key.idx}")
        elif hasattr(key, "name"):
            parts.append(f"attr:{key.name}")
        else:
            parts.append(f"key:{key!r}")
    return "|".join(parts).encode("utf-8")


def _is_array_like(value: Any) -> bool:
    return hasattr(value, "shape") and hasattr(value, "dtype")


def _quantize_array(arr: np.ndarray, rtol: float, atol: float) -> np.ndarray:
    if not np.issubdtype(arr.dtype, np.floating):
        return arr
    if rtol == 0.0 and atol == 0.0:
        return arr
    if not np.all(np.isfinite(arr)):
        return arr
    scale = atol + rtol * np.abs(arr)
    if atol == 0.0:
        scale = np.where(scale == 0.0, 1.0, scale)
    else:
        scale = np.where(scale == 0.0, atol, scale)
    quantized = np.round(arr / scale) * scale
    return quantized.astype(arr.dtype, copy=False)


def _pack_hash_parts(parts: list[bytes]) -> bytes:
    payload = bytearray()
    for part in parts:
        payload.extend(len(part).to_bytes(8, "big", signed=False))
        payload.extend(part)
    return bytes(payload)


def _hash_leaf_payload(
    leaf: Any,
    *,
    rtol: float | None = None,
    atol: float | None = None,
) -> bytes:
    parts: list[bytes] = []

    if _is_array_like(leaf):
        arr = np.asarray(leaf)
        if arr.dtype == object:
            parts.extend([b"object", repr(leaf).encode("utf-8")])
            return _pack_hash_parts(parts)
        if rtol is not None and atol is not None:
            arr = _quantize_array(arr, rtol, atol)
        arr = np.ascontiguousarray(arr)
        parts.extend(
            [
                b"array",
                str(arr.dtype).encode("utf-8"),
                str(tuple(arr.shape)).encode("utf-8"),
                arr.tobytes(order="C"),
            ]
        )
        return _pack_hash_parts(parts)

    if isinstance(leaf, bool):
        parts.extend([b"bool", b"1" if leaf else b"0"])
        return _pack_hash_parts(parts)
    if isinstance(leaf, int):
        parts.extend([b"int", str(leaf).encode("utf-8")])
        return _pack_hash_parts(parts)
    if isinstance(leaf, float):
        parts.extend([b"float", float(leaf).hex().encode("utf-8")])
        return _pack_hash_parts(parts)
    if isinstance(leaf, str):
        parts.extend([b"str", leaf.encode("utf-8")])
        return _pack_hash_parts(parts)
    if leaf is None:
        parts.append(b"none")
        return _pack_hash_parts(parts)

    parts.extend([b"repr", repr(leaf).encode("utf-8")])
    return _pack_hash_parts(parts)


def hash_pytree(tree: Any, *, rtol: float | None = None, atol: float | None = None) -> str:
    """
    Compute deterministic hash of a pytree.

    If rtol/atol are provided, floating arrays are quantized before hashing.
    """
    paths_and_leaves, _ = tree_flatten_with_path(tree)

    leaf_items: list[tuple[bytes, bytes]] = []
    for path, leaf in paths_and_leaves:
        path_bytes = _path_to_bytes(path)
        leaf_payload = _hash_leaf_payload(leaf, rtol=rtol, atol=atol)
        leaf_hash = bytes.fromhex(content_hash(_pack_hash_parts([path_bytes, leaf_payload])))
        leaf_items.append((path_bytes, leaf_hash))

    final_chunks = [
        _pack_hash_parts([path_bytes, leaf_hash])
        for path_bytes, leaf_hash in sorted(leaf_items, key=lambda item: item[0])
    ]
    return streaming_hash(final_chunks)[:HASH_LENGTH]


def _infer_precision(*trees: Any, default: str = "float32") -> str:
    for tree in trees:
        leaves = jax.tree_util.tree_leaves(tree)
        for leaf in leaves:
            if _is_array_like(leaf):
                arr = np.asarray(leaf)
                if np.issubdtype(arr.dtype, np.floating):
                    dtype = arr.dtype
                    if dtype == np.float64:
                        return "float64"
                    if dtype == np.float32:
                        return "float32"
                    if dtype == np.float16:
                        return "float16"
                    if dtype == np.dtype("bfloat16"):
                        return "bfloat16"
    return default


# =============================================================================
# Golden Record
# =============================================================================


@dataclass(frozen=True, slots=True)
class GoldenRecord:
    """A golden record for regression testing."""

    context: GoldenContext
    input_hash: str
    output_hash: str
    output_hash_quantized: str | None = None
    rtol: float = DEFAULT_RTOL
    atol: float = DEFAULT_ATOL
    schema_version: str = GOLDEN_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        method_fqn: str,
        state: Any,
        params: dict[str, Any],
        output: Any,
        *,
        precision: str | None = None,
        rtol: float = DEFAULT_RTOL,
        atol: float = DEFAULT_ATOL,
    ) -> "GoldenRecord":
        precision = precision or _infer_precision(state, params, output)
        input_hash = hash_pytree({"state": state, "params": params})
        output_hash = hash_pytree(output)
        quantized_hash = None
        if rtol is not None and atol is not None:
            quantized_hash = hash_pytree(output, rtol=rtol, atol=atol)
        return cls(
            context=GoldenContext.current(method_fqn, precision=precision),
            input_hash=input_hash,
            output_hash=output_hash,
            output_hash_quantized=quantized_hash,
            rtol=rtol,
            atol=atol,
        )

    def verify(
        self,
        state: Any,
        params: dict[str, Any],
        output: Any,
        *,
        strict_version: bool = False,
        strict_backend: bool = False,
        strict_output: bool = False,
    ) -> GoldenVerificationResult:
        current_ctx = GoldenContext.current(
            self.context.method_fqn,
            precision=self.context.backend.precision,
        )

        if not self.context.matches(
            current_ctx,
            strict_version=strict_version,
            strict_backend=strict_backend,
        ):
            return GoldenVerificationResult(
                status=VerificationStatus.FAILED_CONTEXT,
                message=(
                    f"Context mismatch: expected {self.context.backend.platform}/"
                    f"{self.context.backend.precision}, got {current_ctx.backend.platform}/"
                    f"{current_ctx.backend.precision}"
                ),
                context_match=False,
            )

        input_hash = hash_pytree({"state": state, "params": params})
        if input_hash != self.input_hash:
            return GoldenVerificationResult(
                status=VerificationStatus.FAILED_INPUT,
                message="Input hash mismatch (test inputs differ from recorded)",
                expected_hash=self.input_hash,
                actual_hash=input_hash,
            )

        output_hash = hash_pytree(output)
        if output_hash == self.output_hash:
            return GoldenVerificationResult(
                status=VerificationStatus.PASSED,
                message="Golden record verification passed",
                expected_hash=self.output_hash,
                actual_hash=output_hash,
            )

        if not strict_output and self.output_hash_quantized:
            quantized_hash = hash_pytree(output, rtol=self.rtol, atol=self.atol)
            if quantized_hash == self.output_hash_quantized:
                return GoldenVerificationResult(
                    status=VerificationStatus.PASSED,
                    message=(
                        "Golden record matched within tolerance "
                        f"(rtol={self.rtol}, atol={self.atol})"
                    ),
                    expected_hash=self.output_hash_quantized,
                    actual_hash=quantized_hash,
                )

        return GoldenVerificationResult(
            status=VerificationStatus.FAILED_OUTPUT,
            message="Output hash mismatch (regression detected)",
            expected_hash=self.output_hash,
            actual_hash=output_hash,
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "context": self.context.to_dict(),
                "input_hash": self.input_hash,
                "output_hash": self.output_hash,
                "output_hash_quantized": self.output_hash_quantized,
                "rtol": self.rtol,
                "atol": self.atol,
            },
            indent=indent,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, data: str) -> "GoldenRecord":
        payload = json.loads(data)
        return cls(
            context=GoldenContext.from_dict(payload["context"]),
            input_hash=payload["input_hash"],
            output_hash=payload["output_hash"],
            output_hash_quantized=payload.get("output_hash_quantized"),
            rtol=payload.get("rtol", DEFAULT_RTOL),
            atol=payload.get("atol", DEFAULT_ATOL),
            schema_version=payload.get("schema_version", GOLDEN_SCHEMA_VERSION),
        )


# =============================================================================
# Golden Store
# =============================================================================


@dataclass(frozen=True, slots=True)
class GoldenRecordRef:
    method_fqn: str
    input_hash: str
    backend_platform: str
    precision: str
    path: Path


class GoldenStore:
    """
    Persistent storage for golden records.

    Directory structure:
        base_path/
        └── method_fqn_safe/
            └── <backend_platform>_<device_count>d/
                └── <precision>/
                    └── <input_hash>.golden.json
    """

    def __init__(self, base_path: Path | str):
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def _method_dir(self, method_fqn: str) -> Path:
        safe_name = (
            method_fqn
            .replace(".", "_")
            .replace("@", "_v")
            .replace("-", "_")
        )
        return self._base / safe_name

    def _context_dir(self, context: GoldenContext) -> Path:
        backend_dir = f"{context.backend.platform}_{context.backend.device_count}d"
        precision_dir = context.backend.precision
        return self._method_dir(context.method_fqn) / backend_dir / precision_dir

    def _record_path(self, context: GoldenContext, input_hash: str) -> Path:
        return self._context_dir(context) / f"{input_hash}.golden.json"

    def save(self, record: GoldenRecord) -> Path:
        path = self._record_path(record.context, record.input_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.to_json())
        return path

    def load(
        self,
        method_fqn: str,
        input_hash: str,
        *,
        context: GoldenContext | None = None,
    ) -> GoldenRecord | None:
        if context is not None:
            path = self._record_path(context, input_hash)
            if not path.exists():
                return None
            try:
                return GoldenRecord.from_json(path.read_text())
            except (json.JSONDecodeError, KeyError):
                return None

        method_dir = self._method_dir(method_fqn)
        if not method_dir.exists():
            return None
        matches = sorted(method_dir.glob(f"**/{input_hash}.golden.json"))
        for path in matches:
            try:
                return GoldenRecord.from_json(path.read_text())
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def _find_records_by_input(self, method_fqn: str, input_hash: str) -> list[GoldenRecord]:
        records: list[GoldenRecord] = []
        method_dir = self._method_dir(method_fqn)
        if not method_dir.exists():
            return records
        for path in method_dir.glob(f"**/{input_hash}.golden.json"):
            try:
                records.append(GoldenRecord.from_json(path.read_text()))
            except (json.JSONDecodeError, KeyError):
                continue
        return records

    def exists(
        self,
        method_fqn: str,
        input_hash: str | None = None,
        *,
        context: GoldenContext | None = None,
    ) -> bool:
        method_dir = self._method_dir(method_fqn)
        if input_hash is None:
            return method_dir.exists() and any(method_dir.glob("**/*.golden.json"))
        if context is None:
            return any(method_dir.glob(f"**/{input_hash}.golden.json"))
        return self._record_path(context, input_hash).exists()

    def delete(
        self,
        method_fqn: str,
        input_hash: str,
        *,
        context: GoldenContext | None = None,
    ) -> bool:
        if context is None:
            method_dir = self._method_dir(method_fqn)
            removed = False
            for path in method_dir.glob(f"**/{input_hash}.golden.json"):
                path.unlink()
                removed = True
            return removed
        path = self._record_path(context, input_hash)
        if path.exists():
            path.unlink()
            return True
        return False

    def verify(
        self,
        method_fqn: str,
        state: Any,
        params: dict[str, Any],
        output: Any,
        *,
        precision: str | None = None,
        strict_version: bool = False,
        strict_backend: bool = False,
        strict_output: bool = False,
    ) -> GoldenVerificationResult:
        input_hash = hash_pytree({"state": state, "params": params})
        precision = precision or _infer_precision(state, params, output)
        context = GoldenContext.current(method_fqn, precision=precision)

        record = self.load(method_fqn, input_hash, context=context)
        if record is None:
            candidates = self._find_records_by_input(method_fqn, input_hash)
            if candidates:
                return GoldenVerificationResult(
                    status=VerificationStatus.FAILED_CONTEXT,
                    message="Golden record exists but context does not match",
                    context_match=False,
                )
            return GoldenVerificationResult(
                status=VerificationStatus.NO_RECORD,
                message=f"No golden record exists for {method_fqn}",
            )

        return record.verify(
            state,
            params,
            output,
            strict_version=strict_version,
            strict_backend=strict_backend,
            strict_output=strict_output,
        )

    def update_or_create(
        self,
        method_fqn: str,
        state: Any,
        params: dict[str, Any],
        output: Any,
        *,
        precision: str | None = None,
        rtol: float = DEFAULT_RTOL,
        atol: float = DEFAULT_ATOL,
    ) -> tuple[GoldenRecord, bool]:
        record = GoldenRecord.create(
            method_fqn,
            state,
            params,
            output,
            precision=precision,
            rtol=rtol,
            atol=atol,
        )
        path = self._record_path(record.context, record.input_hash)
        was_existing = path.exists()
        self.save(record)
        return record, was_existing

    def list_records(self) -> list[GoldenRecordRef]:
        refs: list[GoldenRecordRef] = []
        for path in self._base.glob("**/*.golden.json"):
            try:
                record = GoldenRecord.from_json(path.read_text())
            except (json.JSONDecodeError, KeyError):
                continue
            refs.append(
                GoldenRecordRef(
                    method_fqn=record.context.method_fqn,
                    input_hash=record.input_hash,
                    backend_platform=record.context.backend.platform,
                    precision=record.context.backend.precision,
                    path=path,
                )
            )
        refs.sort(key=lambda r: (r.method_fqn, r.input_hash))
        return refs

    def list_methods(self) -> list[str]:
        methods = {ref.method_fqn for ref in self.list_records()}
        return sorted(methods)

    @property
    def path(self) -> Path:
        return self._base
