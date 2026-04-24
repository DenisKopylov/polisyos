"""
Contract Verification & Synthetic Data Generation.

Responsibilities:
1) Runtime contract assertion -- assert_schema_compliance() takes a
   pandas DataFrame and a DataSchema and raises a descriptive
   ContractViolation if the data does not honour the declared contract.
2) Synthetic generation -- generate_dataframe_for_schema() produces
   random DataFrames that conform to a given schema.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    SchemaType,
)

# ---------------------------------------------------------------------------
# Contract violation exception
# ---------------------------------------------------------------------------


@dataclass
class ContractViolation(Exception):
    """
    Structured exception for schema contract failures.

    Attributes:
        schema_id:   The schema that was being checked.
        errors:      Exhaustive list of violation descriptions.
        context:     Optional free-form metadata (connector_id, dataset, ...).
    """

    schema_id: str
    errors: list[str] = field(default_factory=list)
    context: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        header = f"ContractViolation for schema '{self.schema_id}'"
        if self.context:
            ctx = ", ".join(f"{k}={v}" for k, v in self.context.items())
            header = f"{header} [{ctx}]"
        body = "\n".join(f"  -  {e}" for e in self.errors)
        return f"{header}\n{body}"


# ---------------------------------------------------------------------------
# assert_schema_compliance
# ---------------------------------------------------------------------------


def assert_schema_compliance(
    data: pd.DataFrame,
    schema: DataSchema,
    *,
    strict: bool = False,
    context: dict[str, str] | None = None,
) -> None:
    """
    Assert that data fully honours the schema contract.

    Delegates to Phase 2.3's validate_dataframe_against_schema() for
    the actual checks, then wraps any errors into a ContractViolation.
    """
    from polisyos.fabric.connectors.contracts.inference import (
        validate_dataframe_against_schema,
    )

    errors = validate_dataframe_against_schema(data, schema, strict=strict)

    if errors:
        raise ContractViolation(
            schema_id=schema.schema_id,
            errors=errors,
            context=context or {},
        )


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------


_NULL_RATE = 0.10


def generate_dataframe_for_schema(
    schema: DataSchema,
    num_rows: int = 50,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    Generate a random DataFrame that conforms to schema.

    Every FieldSpec constraint is honoured:
        - data_type      -> correct dtype
        - nullable       -> NaN injected at ~10% rate if nullable=True
        - bounds         -> values clamped to (min, max)
        - allowed_values -> values drawn only from allowed set
        - pattern        -> simple pattern expansion for common cases
        - max_length     -> strings truncated
    """
    import random as _rng

    if seed is not None:
        _rng.seed(seed)

    columns: dict[str, list[Any]] = {}
    for fspec in schema.fields:
        columns[fspec.name] = _generate_column(fspec, num_rows, _rng)

    df = pd.DataFrame(columns)

    # Inject nulls after generation so we don't corrupt type inference
    for fspec in schema.fields:
        if fspec.nullable:
            _inject_nulls(df, fspec.name, rate=_NULL_RATE, rng=_rng)

    _apply_schema_dtypes(df, schema)
    return df


# ---------------------------------------------------------------------------
# Per-field generators (private)
# ---------------------------------------------------------------------------


def _inject_nulls(df: pd.DataFrame, col: str, rate: float, rng: Any) -> None:
    """Replace ~rate fraction of values in col with NaN."""
    mask = [rng.random() < rate for _ in range(len(df))]
    df.loc[mask, col] = None


def _apply_schema_dtypes(df: pd.DataFrame, schema: DataSchema) -> None:
    """Cast DataFrame columns to pandas dtypes implied by the schema."""
    for fspec in schema.fields:
        if fspec.name not in df.columns:
            continue

        dtype = fspec.data_type.to_pandas_dtype()

        if fspec.data_type in (SchemaType.DATE, SchemaType.DATETIME):
            df[fspec.name] = pd.to_datetime(df[fspec.name], errors="coerce")
            continue

        if fspec.data_type == SchemaType.TIMESTAMP_TZ:
            df[fspec.name] = pd.to_datetime(df[fspec.name], errors="coerce", utc=True)
            continue

        if fspec.data_type == SchemaType.DURATION:
            df[fspec.name] = pd.to_timedelta(df[fspec.name], errors="coerce")
            continue

        try:
            df[fspec.name] = df[fspec.name].astype(dtype)
        except Exception:
            # Fall back to pandas' best effort if strict cast fails
            df[fspec.name] = df[fspec.name].astype("object")


def _generate_column(fspec: FieldSpec, n: int, rng: Any) -> list[Any]:
    """Dispatch to the correct generator based on data_type."""
    dispatch: dict[SchemaType, Any] = {
        SchemaType.INT8: lambda: _gen_int(fspec, n, rng, lo=-128, hi=127),
        SchemaType.INT16: lambda: _gen_int(fspec, n, rng, lo=-32768, hi=32767),
        SchemaType.INT32: lambda: _gen_int(fspec, n, rng, lo=-(2**31), hi=2**31 - 1),
        SchemaType.INT64: lambda: _gen_int(fspec, n, rng, lo=-(2**63), hi=2**63 - 1),
        SchemaType.UINT8: lambda: _gen_int(fspec, n, rng, lo=0, hi=255),
        SchemaType.UINT16: lambda: _gen_int(fspec, n, rng, lo=0, hi=65535),
        SchemaType.UINT32: lambda: _gen_int(fspec, n, rng, lo=0, hi=2**32 - 1),
        SchemaType.UINT64: lambda: _gen_int(fspec, n, rng, lo=0, hi=2**64 - 1),
        SchemaType.FLOAT32: lambda: _gen_float(fspec, n, rng),
        SchemaType.FLOAT64: lambda: _gen_float(fspec, n, rng),
        SchemaType.BOOLEAN: lambda: [rng.choice([True, False]) for _ in range(n)],
        SchemaType.STRING: lambda: _gen_string(fspec, n, rng),
        SchemaType.CATEGORY: lambda: _gen_category(fspec, n, rng),
        SchemaType.DATETIME: lambda: _gen_datetime(n, rng),
        SchemaType.DATE: lambda: _gen_date(n, rng),
    }

    generator = dispatch.get(fspec.data_type)
    if generator is None:
        # Fallback: generate opaque strings for unsupported types
        return [f"<{fspec.data_type.value}_{i}>" for i in range(n)]

    return generator()


def _gen_int(fspec: FieldSpec, n: int, rng: Any, lo: int, hi: int) -> list[int]:
    """Generate integers respecting bounds from FieldSpec."""
    min_val, max_val = fspec.bounds
    effective_lo = int(min_val) if min_val is not None else lo
    effective_hi = int(max_val) if max_val is not None else hi
    # Clamp to type range
    effective_lo = max(effective_lo, lo)
    effective_hi = min(effective_hi, hi)
    return [rng.randint(effective_lo, effective_hi) for _ in range(n)]


def _gen_float(fspec: FieldSpec, n: int, rng: Any) -> list[float]:
    """Generate floats respecting bounds from FieldSpec."""
    min_val, max_val = fspec.bounds
    lo = min_val if min_val is not None else -1e6
    hi = max_val if max_val is not None else 1e6
    return [round(rng.uniform(lo, hi), 6) for _ in range(n)]


def _gen_string(fspec: FieldSpec, n: int, rng: Any) -> list[str]:
    """
    Generate strings.

    If pattern is set and is a simple literal or character-class
    pattern, we expand it. Otherwise we generate random alphanumeric
    strings of appropriate length.
    """
    max_len = max(int(fspec.max_length or 32), 1)
    min_len = 1 if max_len < 4 else 4
    results: list[str] = []

    for _ in range(n):
        if fspec.pattern:
            results.append(_expand_simple_pattern(fspec.pattern, max_len, rng))
        else:
            length = rng.randint(min_len, max_len)
            results.append("".join(rng.choices(string.ascii_lowercase + string.digits, k=length)))

    return results


def _gen_category(fspec: FieldSpec, n: int, rng: Any) -> list[str]:
    """
    Generate categorical values.

    If allowed_values is set, draw exclusively from that set.
    Otherwise fall back to generic string generation.
    """
    if fspec.allowed_values:
        pool = list(fspec.allowed_values)
        return [rng.choice(pool) for _ in range(n)]
    return _gen_string(fspec, n, rng)


def _gen_datetime(n: int, rng: Any) -> list[str]:
    """Generate ISO-8601 datetime strings spanning 2020-2025."""
    import datetime as _dt

    base = _dt.datetime(2020, 1, 1, tzinfo=_dt.UTC)
    span = (_dt.datetime(2025, 12, 31, tzinfo=_dt.UTC) - base).total_seconds()
    return [(base + _dt.timedelta(seconds=rng.uniform(0, span))).isoformat() for _ in range(n)]


def _gen_date(n: int, rng: Any) -> list[str]:
    """Generate ISO-8601 date strings spanning 2020-2025."""
    import datetime as _dt

    base = _dt.date(2020, 1, 1)
    span = (_dt.date(2025, 12, 31) - base).days
    return [(base + _dt.timedelta(days=rng.randint(0, span))).isoformat() for _ in range(n)]


def _expand_simple_pattern(pattern: str, max_len: int, rng: Any) -> str:
    """
    Best-effort expansion of simple regex patterns.

    Handles common cases seen in connector schemas:
        - ^[A-Z]{2}$             -> 2 uppercase letters
        - ^[a-z0-9_]+$            -> alphanumeric + underscore
        - ^\\d{4}-\\d{2}-\\d{2}$ -> date-like string

    For anything more complex, falls back to a random alphanumeric string.
    """
    # Strip anchors
    p = pattern.lstrip("^").rstrip("$")

    # Try to detect {N} repetition of a character class
    char_class_match = re.fullmatch(r"\[([^\]]+)\]\{(\d+)\}", p)
    if char_class_match:
        chars = _expand_char_class(char_class_match.group(1))
        count = int(char_class_match.group(2))
        return "".join(rng.choices(chars, k=count))

    # Try [class]+ or [class]*
    char_class_plus = re.fullmatch(r"\[([^\]]+)\][+*]", p)
    if char_class_plus:
        chars = _expand_char_class(char_class_plus.group(1))
        length = rng.randint(1, max_len)
        return "".join(rng.choices(chars, k=length))

    # Date-like: \d{4}-\d{2}-\d{2}
    if re.fullmatch(r"\\d\{4\}-\\d\{2\}-\\d\{2\}", p):
        import datetime as _dt

        base = _dt.date(2020, 1, 1)
        span = (_dt.date(2025, 12, 31) - base).days
        return (base + _dt.timedelta(days=rng.randint(0, span))).isoformat()

    # Fallback
    min_len = 1 if max_len < 4 else 4
    length = rng.randint(min_len, max_len)
    return "".join(rng.choices(string.ascii_lowercase + string.digits, k=length))


def _expand_char_class(class_body: str) -> list[str]:
    """
    Expand a regex character class body into a list of characters.

    E.g. "A-Za-z0-9_" -> all ASCII letters, digits, and underscore.
    """
    result: list[str] = []
    i = 0
    while i < len(class_body):
        if i + 2 < len(class_body) and class_body[i + 1] == "-":
            start = class_body[i]
            end = class_body[i + 2]
            result.extend(chr(c) for c in range(ord(start), ord(end) + 1))
            i += 3
        else:
            result.append(class_body[i])
            i += 1
    return result
