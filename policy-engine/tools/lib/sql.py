"""SQL identifier and literal helpers for hardened tooling."""

from __future__ import annotations

import re

IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def validate_sql_identifier(value: str, *, kind: str = "identifier") -> str:
    """Allow only simple lowercase SQL identifiers."""

    candidate = str(value or "").strip()
    if not IDENTIFIER_RE.fullmatch(candidate):
        raise ValueError(f"Unsafe {kind}: {value!r}")
    return candidate


def validate_qualified_sql_identifier(
    value: str,
    *,
    kind: str = "identifier",
    min_parts: int = 1,
    max_parts: int = 2,
) -> tuple[str, ...]:
    """Validate a dotted SQL identifier like `schema.table`."""

    parts = [part.strip() for part in str(value or "").split(".")]
    if not all(parts):
        raise ValueError(f"Unsafe {kind}: {value!r}")
    if not (min_parts <= len(parts) <= max_parts):
        raise ValueError(f"Unsafe {kind}: {value!r}")
    return tuple(validate_sql_identifier(part, kind=kind) for part in parts)


def render_qualified_identifier(*parts: str) -> str:
    """Render a validated dotted identifier."""

    return ".".join(validate_sql_identifier(part) for part in parts if part)


def quote_sql_string_literal(value: str) -> str:
    """Escape a SQL string literal for engines that do not support parameterized ATTACH paths."""

    return "'" + str(value).replace("'", "''") + "'"
