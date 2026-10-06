"""Strict, nonauthoritative JSON protocol for the isolated DoWhy computation worker."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

REQUEST_SCHEMA = "polisyos.dowhy.request.v1"
RESPONSE_SCHEMA = "polisyos.dowhy.response.v1"
PROFILE = "dowhy-014"
MAX_BYTES = 8 * 1024 * 1024


def canonical_bytes(value: object) -> bytes:
    """Encode finite JSON with a deterministic byte representation."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(value: object) -> str:
    """Hash the canonical JSON bytes of a protocol value."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(raw: bytes) -> dict[str, Any]:
    """Reject duplicate keys, nonfinite JSON and oversized transport messages."""
    if len(raw) > MAX_BYTES:
        raise ValueError("worker message exceeds byte limit")
    value = json.loads(
        raw,
        object_pairs_hook=_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )
    if not isinstance(value, dict):
        raise ValueError("worker message must be an object")
    return value


def keys(value: dict[str, Any], expected: set[str]) -> None:
    """Require exactly the fields of a supported protocol object."""
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"unsupported fields: expected {sorted(expected)}")


def validate_request(request: dict[str, Any]) -> None:
    """Validate content bindings and the finite operation allowlist, without fetching refs."""
    keys(
        request,
        {
            "schema",
            "profile",
            "operation",
            "request_id",
            "request_sha256",
            "source",
            "basis",
            "graph",
            "parameters",
            "seed",
        },
    )
    if request["schema"] != REQUEST_SCHEMA or request["profile"] != PROFILE:
        raise ValueError("unsupported worker protocol/profile")
    if request["operation"] not in {"linear_ate", "gcm_fit"}:
        raise ValueError("unsupported worker operation")
    if not isinstance(request["request_id"], str) or not request["request_id"]:
        raise ValueError("request_id must be a nonempty string")
    if type(request["seed"]) is not int or not 0 <= request["seed"] < 2**32:
        raise ValueError("seed must be a uint32")
    if request["request_sha256"] != digest(
        {k: v for k, v in request.items() if k != "request_sha256"}
    ):
        raise ValueError("request binding mismatch")
    source = request["source"]
    keys(source, {"artifact_ref", "content_sha256"})
    if not isinstance(source["artifact_ref"], dict) or len(source["content_sha256"]) != 64:
        raise ValueError("source binding malformed")
    basis = request["basis"]
    keys(basis, {"columns", "rows", "row_ids", "data_sha256", "row_sha256"})
    columns, rows, row_ids = basis["columns"], basis["rows"], basis["row_ids"]
    if not isinstance(columns, list) or not columns or len(set(columns)) != len(columns):
        raise ValueError("columns must be unique")
    if any(not isinstance(name, str) or not name for name in columns):
        raise ValueError("column names must be strings")
    if not isinstance(rows, list) or len(rows) < 2 or len(rows) != len(row_ids):
        raise ValueError("aligned rows required")
    if len(set(row_ids)) != len(row_ids) or any(not isinstance(x, str) for x in row_ids):
        raise ValueError("row IDs must be unique strings")
    if any(
        not isinstance(row, list)
        or len(row) != len(columns)
        or any(type(x) not in {int, float} or not math.isfinite(x) for x in row)
        for row in rows
    ):
        raise ValueError("finite rectangular data required")
    if basis["data_sha256"] != digest({"columns": columns, "rows": rows}):
        raise ValueError("data binding mismatch")
    if basis["row_sha256"] != digest(row_ids):
        raise ValueError("row binding mismatch")
    graph = request["graph"]
    keys(graph, {"representation", "payload", "sha256"})
    if graph["sha256"] != digest(graph["payload"]):
        raise ValueError("graph binding mismatch")
    expected = "dot" if request["operation"] == "linear_ate" else "dag"
    if graph["representation"] != expected:
        raise ValueError("graph representation mismatch")
