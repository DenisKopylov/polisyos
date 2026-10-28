"""Finite engineering profile shared by federation production and replay.

These are software work limits, not institutional admissibility rules. The
wire profile is deliberately narrower than pandas' arbitrary object universe.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from polisyos.fabric.connectors.federation.types import (
    AuditLevel,
    CompositionRequest,
    CompositionStrategy,
    FederationError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_SOURCES = 32
MAX_ROWS = 100_000
MAX_COLUMNS = 1_000
MAX_CELLS = 2_000_000
MAX_SCALAR_BYTES = 64 * 1024
MAX_GRAPH_NODES = 64
MAX_GRAPH_DEPTH = 8
MAX_GRAPH_CELLS = 4_000_000
MAX_JSON_DEPTH = 32
MAX_AUDIT_ENTRIES = 5_000


def admit_shape(rows: int, columns: int) -> None:
    """Reject dimensions before copying, decoding or composing their cells."""
    if rows > MAX_ROWS or columns > MAX_COLUMNS or rows * columns > MAX_CELLS:
        raise FederationError("Federation frame exceeds engineering work profile")


def bounded_encode(value: Any, limit: int = MAX_FILE_BYTES) -> bytes:  # noqa: ANN401
    """Encode incrementally, refusing before retaining an over-budget chunk."""
    admit_json_tree(value)
    output = bytearray()
    for chunk in json.JSONEncoder(
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).iterencode(value):
        # Individual supported strings are bounded before the encoder sees them.
        if len(chunk) > limit - len(output):
            raise FederationError("Federation encoded member exceeds engineering byte profile")
        encoded = chunk.encode("utf-8")
        if len(encoded) > limit - len(output):
            raise FederationError("Federation encoded member exceeds engineering byte profile")
        output.extend(encoded)
    return bytes(output)


def encode_scalar(value: Any) -> dict[str, Any]:  # noqa: ANN401
    """Encode one admitted scalar without allocating an unbounded UTF-8 copy."""
    if isinstance(value, np.generic):
        # Masked nullable arrays iterate numpy scalar values; normalize exact
        # Python scalar equivalents before applying the bounded wire profile.
        value = value.item()
    if value is pd.NaT:
        value = None
    if value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value)):
        return {"t": "null"}
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        if value.bit_length() > 4096:
            raise FederationError("Federation integer exceeds wire profile")
        return {"t": "int", "v": str(value)}
    if isinstance(value, float):
        return {"t": "float64", "v": value.hex()}
    if isinstance(value, str):
        if len(value) > MAX_SCALAR_BYTES:
            raise FederationError("Federation string scalar exceeds wire profile")
        size = 0
        for character in value:
            codepoint = ord(character)
            if 0xD800 <= codepoint <= 0xDFFF:
                raise FederationError("Unpaired surrogate is outside the UTF-8 wire profile")
            size += (
                1
                if codepoint < 0x80
                else 2
                if codepoint < 0x800
                else 3
                if codepoint < 0x10000
                else 4
            )
            if size > MAX_SCALAR_BYTES:
                raise FederationError("Federation string scalar exceeds wire profile")
        return {"t": "str", "v": value}
    if isinstance(value, (pd.Timestamp, datetime)):
        stamp = pd.Timestamp(value)
        return {"t": "timestamp", "v": stamp.isoformat(), "ns": str(stamp.value)}
    raise FederationError(f"Unsupported federation artifact scalar: {type(value).__name__}")


def admit_frame(frame: pd.DataFrame) -> int:
    """Scan exact wire size before allocating a projection or dataframe copy."""
    admit_shape(*frame.shape)
    if not frame.columns.is_unique or not all(isinstance(col, str) for col in frame.columns):
        raise FederationError("Federation wire profile requires unique string columns")
    header = {
        "columns": list(frame.columns),
        "dtypes": [str(dtype) for dtype in frame.dtypes],
        "rows": [],
    }
    for column in frame.columns:
        encode_scalar(column)
    size = len(bounded_encode(header))
    for row in frame.itertuples(False, None):
        # Per-row staging is bounded by MAX_COLUMNS and admitted scalar size.
        row_size = 2
        for value in row:
            row_size += len(bounded_encode(encode_scalar(value))) + 1
            if row_size + size > MAX_FILE_BYTES:
                raise FederationError("Federation frame exceeds encoded byte profile")
        size += row_size + 1
        if size > MAX_FILE_BYTES:
            raise FederationError("Federation frame exceeds encoded byte profile")
    return size


def frame_projection(frame: pd.DataFrame) -> dict[str, Any]:
    """Project only after the complete scalar and encoded-work admission pass."""
    admit_frame(frame)
    return {
        "columns": list(frame.columns),
        "dtypes": [str(dtype) for dtype in frame.dtypes],
        "rows": [[encode_scalar(value) for value in row] for row in frame.itertuples(False, None)],
    }


def frame_digest(frame: pd.DataFrame) -> str:
    """Hash the exact scalar projection incrementally without a full JSON copy."""
    admit_frame(frame)
    digest = hashlib.sha256()
    digest.update(
        bounded_encode({"columns": list(frame.columns), "dtypes": [str(t) for t in frame.dtypes]})
    )
    for row in frame.itertuples(False, None):
        for value in row:
            encoded = bounded_encode(encode_scalar(value))
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def admit_json_tree(value: Any, depth: int = 0) -> None:  # noqa: ANN401
    """Reject decoded arbitrary nesting and oversized string members before restoration."""
    if depth > MAX_JSON_DEPTH:
        raise FederationError("Federation JSON exceeds nesting profile")
    if isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str):
                raise FederationError("Federation JSON object keys must be strings")
            encode_scalar(key)
            admit_json_tree(member, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_CELLS:
            raise FederationError("Federation JSON array exceeds work profile")
        for member in value:
            admit_json_tree(member, depth + 1)
    elif isinstance(value, str) or value is not None:
        encode_scalar(value)


def admit_output_envelope(
    sources: list[tuple[pd.DataFrame, object]],
    rows: int,
    *,
    contributors: int = 1,
    token_bytes: int = 0,
    request: CompositionRequest | None = None,
) -> int:
    """Admit conservative wire and lineage bounds before a strategy allocates output.

    This may refuse a compressible/wide sparse result that fits after composition.
    Such a request needs a tighter pre-allocation profile, never a post-hoc cap.
    """
    maxima: dict[str, int] = {}
    dtype_sizes: dict[str, int] = {}
    token_size = token_bytes
    for frame, metadata in sources:
        token_size = max(
            token_size,
            len(
                str(
                    metadata if isinstance(metadata, str) else getattr(metadata, "connector_id", "")
                )
            )
            * 6
            + 67,
        )
        for column, series in frame.items():
            dtype_sizes[column] = max(
                dtype_sizes.get(column, 0), len(bounded_encode(str(series.dtype))), 256
            )
            maximum = 0
            for value in series:
                maximum = max(maximum, len(bounded_encode(encode_scalar(value))))
            # pandas can promote int/null to float64, so an input integer's
            # short wire representation is not an output-type upper bound.
            # 128 bytes covers every supported primitive numeric/timestamp
            # encoding; long strings retain their measured bounded length.
            maxima[column] = max(maxima.get(column, 0), maximum, 128)
    admit_shape(rows, len(maxima))
    header_bound = 256 + sum(len(bounded_encode(column)) + dtype_sizes[column] for column in maxima)
    wire_bound = header_bound + rows * (2 + sum(size + 1 for size in maxima.values()))
    if wire_bound > MAX_FILE_BYTES:
        raise FederationError("Federation output exceeds pre-allocation wire bound")
    relation_row = 2 + sum(
        len(bounded_encode(column)) + contributors * (token_size + 4) + 6 for column in maxima
    )
    if rows * relation_row > MAX_FILE_BYTES // 2:
        raise FederationError("Federation output exceeds pre-allocation lineage bound")

    if request is not None:
        sample_count = 0
        if request.audit_level != AuditLevel.NONE:
            max_conflicts = rows * len(maxima) * len(sources)
            if request.audit_level == AuditLevel.FULL:
                retained = (
                    min(max_conflicts, request.audit_max_entries)
                    if request.audit_max_entries > 0
                    else max_conflicts
                )
            else:
                retained = min(max_conflicts, max(0, request.audit_sample_size))
            if retained > MAX_AUDIT_ENTRIES:
                raise FederationError("Federation audit detail work exceeds engineering profile")
            sample_count = retained if request.audit_level == AuditLevel.SUMMARY else 0
        # Row-valued UNION logs and Python repr escaping can expand display
        # strings; reserve that work before creating sample projection strings.
        sample_bound = sample_count * (6 * sum(maxima.values()) + 2 * token_size + 4096)
        extra_bound = 0
        if request.strategy == CompositionStrategy.CONSENSUS:
            # Numeric participant/exclusion/absence summaries exist even in NONE.
            extra_bound = rows * len(maxima) * contributors * (3 * token_size + 512)
        manifest_bound = MAX_FILE_BYTES // 2 + MAX_SCALAR_BYTES + MAX_SOURCES * 512
        if manifest_bound + sample_bound + extra_bound > MAX_FILE_BYTES:
            raise FederationError("Federation audit/manifest exceeds pre-allocation byte bound")
    return wire_bound


def scalar_rows(frame: pd.DataFrame) -> Iterator[tuple[object, ...]]:
    """Iterate per-column scalars without a homogeneous row Series/array cast."""
    return frame.itertuples(index=False, name=None)


def scalar_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Create an admitted object-backed working carrier preserving individual scalars."""
    admit_frame(frame)
    return pd.DataFrame(
        {column: cast_series_losslessly(frame[column], "object") for column in frame.columns},
        index=frame.index,
    )


def align_scalar_series(series: pd.Series, index: pd.Index) -> pd.Series:
    """Introduce alignment nulls without converting held integer cells to float."""
    return cast_series_losslessly(series, "object").reindex(index)


def cast_series_losslessly(
    series: pd.Series, dtype: str, *, allow_exact_numeric_projection: bool = False
) -> pd.Series:
    """Reconcile a candidate column cast to held scalar content before promotion.

    Numeric representation may change only for an explicitly chosen output dtype
    and only if the exact numeric value round-trips. Artifact decoding requires
    exact tagged scalar equality instead. Null masks and timestamps remain exact.
    """
    try:
        candidate = series.astype(dtype)
    except (TypeError, ValueError, OverflowError) as exc:
        raise FederationError(f"Unsupported lossless output dtype projection {dtype!r}") from exc
    for original, projected in zip(series, candidate, strict=True):
        original_wire, projected_wire = encode_scalar(original), encode_scalar(projected)
        if original_wire == projected_wire:
            continue
        equal = False
        if allow_exact_numeric_projection:
            if original_wire["t"] == "int" and projected_wire["t"] == "float64":
                number = float.fromhex(projected_wire["v"])
                equal = (
                    math.isfinite(number)
                    and number.is_integer()
                    and int(number) == int(original_wire["v"])
                )
            elif original_wire["t"] == "float64" and projected_wire["t"] == "int":
                number = float.fromhex(original_wire["v"])
                equal = (
                    math.isfinite(number)
                    and number.is_integer()
                    and int(number) == int(projected_wire["v"])
                )
        if not equal:
            raise FederationError(
                f"Output dtype {dtype!r} cannot represent the held scalar exactly; "
                "an explicit lossless dtype-join profile is required"
            )
    return candidate


def admit_key_index(frames: list[pd.DataFrame], keys: list[str], index: pd.Index) -> None:
    """Reconcile an actual alignment index to complete held typed key values."""
    expected = {
        tuple(bounded_encode(encode_scalar(value)) for value in row)
        for frame in frames
        for row in zip(*(frame[key] for key in keys), strict=True)
    }
    actual = {
        tuple(bounded_encode(encode_scalar(value)) for value in (key if len(keys) > 1 else (key,)))
        for key in index
    }
    if actual != expected:
        raise FederationError(
            "Alignment changed exact held key scalars; lossless identity profile required"
        )
