"""Shared Fabric safety helpers for identifiers, literals, paths, and JSON traversal."""
from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import quote

import re

_SQL_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_SPARQL_VARIABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SPARQL_IRI_TOKEN_RE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*|<[^<>{}\"|^`\\\x00-\x20]+>)$"
)
_DATA_PATH_KEY_RE = re.compile(r"^[A-Za-z0-9_$:-][A-Za-z0-9_$:-]{0,63}$")

_MAX_DATA_PATH_DEPTH = 8
_MAX_DATA_PATH_INDEX = 100_000
_MAX_PATH_SEGMENT_LENGTH = 200


class FabricSafetyError(ValueError):
    """Base class for typed Fabric input-validation failures."""


class UnsafeIdentifierError(FabricSafetyError):
    """Raised when an identifier violates the Fabric identifier policy."""


class UnsafeLiteralError(FabricSafetyError):
    """Raised when a literal cannot be encoded safely."""


class UnsafePathSegmentError(FabricSafetyError):
    """Raised when a user-controlled URL path segment is unsafe."""


class UnsafeDataPathError(FabricSafetyError):
    """Raised when a configured JSON data-path is invalid or exceeds bounds."""


class UnsafeFilterExpressionError(FabricSafetyError):
    """Raised when a user-supplied filter expression is unsafe or unsupported."""


def validate_sql_identifier(
    value: str,
    *,
    what: str = "identifier",
    allow_dotted: bool = False,
) -> str:
    """Validate a SQL identifier against the Fabric allow-list policy."""
    candidate = str(value or "")
    if not candidate:
        raise UnsafeIdentifierError(f"Unsafe {what}: empty identifier")

    parts = candidate.split(".") if allow_dotted else [candidate]
    if any(not part or not _SQL_IDENTIFIER_RE.fullmatch(part) for part in parts):
        raise UnsafeIdentifierError(f"Unsafe {what}: {value!r}")
    return candidate


def quote_sql_identifier(
    value: str,
    *,
    what: str = "identifier",
    allow_dotted: bool = False,
) -> str:
    """Validate and quote a SQL identifier for direct interpolation into SQL."""
    validated = validate_sql_identifier(value, what=what, allow_dotted=allow_dotted)
    return ".".join(f'"{part}"' for part in validated.split("."))


def validate_sparql_variable_name(value: str, *, what: str = "SPARQL variable") -> str:
    """Validate a SPARQL variable name without the leading ``?``."""
    candidate = str(value or "").strip()
    if not _SPARQL_VARIABLE_RE.fullmatch(candidate):
        raise UnsafeIdentifierError(f"Unsafe {what}: {value!r}")
    return candidate


def validate_sparql_iri_token(value: str, *, what: str = "SPARQL IRI token") -> str:
    """Validate a SPARQL IRI or prefixed-name token."""
    candidate = str(value or "").strip()
    if not _SPARQL_IRI_TOKEN_RE.fullmatch(candidate):
        raise UnsafeLiteralError(f"Unsafe {what}: {value!r}")
    return candidate


def escape_sparql_literal(value: str) -> str:
    """Return a double-quoted SPARQL literal with control characters escaped."""
    text = str(value)
    escaped: list[str] = []
    for char in text:
        codepoint = ord(char)
        if char == "\\":
            escaped.append("\\\\")
        elif char == '"':
            escaped.append('\\"')
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\t":
            escaped.append("\\t")
        elif codepoint < 0x20:
            escaped.append(f"\\u{codepoint:04X}")
        else:
            escaped.append(char)
    return f'"{"".join(escaped)}"'


def escape_soql_literal(value: str) -> str:
    """Return a single-quoted SoQL literal with embedded quotes escaped."""
    return _escape_single_quoted_literal(value, what="SoQL literal")


def escape_odsql_literal(value: str) -> str:
    """Return a single-quoted ODSQL literal with embedded quotes escaped."""
    return _escape_single_quoted_literal(value, what="ODSQL literal")


def safe_path_segment(
    value: str,
    *,
    what: str = "path segment",
    safe: str = "-._~",
) -> str:
    """Validate and percent-encode one URL path segment."""
    segment = str(value or "")
    if not segment:
        raise UnsafePathSegmentError(f"Unsafe {what}: empty segment")
    if segment in {".", ".."}:
        raise UnsafePathSegmentError(f"Unsafe {what}: traversal segment {value!r}")
    if len(segment) > _MAX_PATH_SEGMENT_LENGTH:
        raise UnsafePathSegmentError(f"Unsafe {what}: segment too long")
    if "/" in segment or "\\" in segment:
        raise UnsafePathSegmentError(f"Unsafe {what}: slash characters are not allowed")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in segment):
        raise UnsafePathSegmentError(f"Unsafe {what}: control characters are not allowed")
    return quote(segment, safe=safe)


def validate_data_path(
    path: str | Iterable[str] | None,
    *,
    max_depth: int = _MAX_DATA_PATH_DEPTH,
) -> tuple[str, ...]:
    """Validate a dot-path used to extract nested JSON payload data."""
    if path is None or path == "":
        return ()

    parts = tuple(path) if not isinstance(path, str) else tuple(path.split("."))
    if len(parts) > max_depth:
        raise UnsafeDataPathError(
            f"Unsafe data_path: depth {len(parts)} exceeds maximum {max_depth}"
        )

    validated: list[str] = []
    for part in parts:
        token = str(part)
        if not token:
            raise UnsafeDataPathError("Unsafe data_path: empty path token")
        if token.startswith("__"):
            raise UnsafeDataPathError(f"Unsafe data_path token: {token!r}")
        if token.isdigit():
            if int(token) > _MAX_DATA_PATH_INDEX:
                raise UnsafeDataPathError(
                    f"Unsafe data_path index: {token} exceeds maximum {_MAX_DATA_PATH_INDEX}"
                )
            validated.append(token)
            continue
        if not _DATA_PATH_KEY_RE.fullmatch(token):
            raise UnsafeDataPathError(f"Unsafe data_path token: {token!r}")
        validated.append(token)
    return tuple(validated)


def extract_bounded_data_path(
    obj: Any,
    path: str | Iterable[str] | None,
    *,
    max_depth: int = _MAX_DATA_PATH_DEPTH,
) -> Any:
    """Traverse a validated data path through nested dict/list JSON payloads."""
    tokens = validate_data_path(path, max_depth=max_depth)
    current = obj
    for token in tokens:
        if isinstance(current, dict):
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit():
                raise KeyError(f"Cannot traverse '{token}' in list")
            index = int(token)
            try:
                current = current[index]
            except IndexError as exc:
                raise KeyError(f"Index {index} out of range") from exc
            continue
        raise KeyError(f"Cannot traverse '{token}' in {type(current).__name__}")
    return current


def _escape_single_quoted_literal(value: str, *, what: str) -> str:
    text = str(value)
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in text):
        raise UnsafeLiteralError(f"Unsafe {what}: control characters are not allowed")
    escaped = text.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


__all__ = [
    "FabricSafetyError",
    "UnsafeDataPathError",
    "UnsafeFilterExpressionError",
    "UnsafeIdentifierError",
    "UnsafeLiteralError",
    "UnsafePathSegmentError",
    "escape_odsql_literal",
    "escape_soql_literal",
    "escape_sparql_literal",
    "extract_bounded_data_path",
    "quote_sql_identifier",
    "safe_path_segment",
    "validate_data_path",
    "validate_sparql_iri_token",
    "validate_sparql_variable_name",
    "validate_sql_identifier",
]
