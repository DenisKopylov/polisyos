"""Strict, nonauthoritative protocol for the isolated EconML DML prototype."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

REQUEST_SCHEMA = "polisyos.econml-dml.request.v1"
RESPONSE_SCHEMA = "polisyos.econml-dml.response.v1"
PROFILE_ID = "econml-0.16.0-py312-macos-arm64-v4-prototype"
METHOD_FQN = "causal.hte.double_ml_worker_prototype@0.2.0"
OPERATION = "linear_dml"
MAX_BYTES = 8 * 1024 * 1024
EXPECTED_PYTHON_VERSION = "3.12.12"
EXPECTED_SYS_PLATFORM = "darwin"
EXPECTED_MACHINE = "arm64"
EXPECTED_MACOS_VERSION = "27.0.1"

REQUEST_FIELDS = {
    "schema", "profile", "method_fqn", "operation", "job_id", "request_id",
    "request_sha256", "source", "data", "configuration", "seed", "lock_sha256",
}
SOURCE_FIELDS = {"artifact_ref", "content_sha256"}
DATA_FIELDS = {
    "row_ids", "row_order_sha256", "y", "t", "x", "w", "x_names", "w_names",
    "data_sha256",
}
CONFIGURATION = {
    "estimator_fqn": "econml.dml.LinearDML",
    "model_y": "auto",
    "model_t": "auto",
    "cv_folds": 3,
    "confidence_level": 0.95,
    "discrete_treatment": True,
    "control_value": 0,
    "treatment_value": 1,
}


def canonical_bytes(value: object) -> bytes:
    """Return deterministic finite JSON bytes."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(value: object) -> str:
    """Hash deterministic JSON bytes."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode(raw: bytes) -> dict[str, Any]:
    """Decode bounded JSON, rejecting duplicate keys and nonfinite constants."""
    if len(raw) > MAX_BYTES:
        raise ValueError("message exceeds configured byte limit")
    value = json.loads(
        raw,
        object_pairs_hook=_object,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise ValueError("message must be a JSON object")
    return value


def require_keys(
    value: object, expected: set[str], *, optional: frozenset[str] = frozenset()
) -> None:
    """Require an exact object shape, with only explicitly optional fields."""
    if (
        not isinstance(value, dict)
        or not expected <= set(value)
        or set(value) - expected - optional
    ):
        raise ValueError("unexpected protocol object shape")


def _finite_number(value: object) -> bool:
    """Accept JSON integer/float values, excluding bool and nonfinite values."""
    return type(value) in {int, float} and math.isfinite(value)


def _finite_vector(value: object, *, name: str, length: int | None = None) -> list[float]:
    if not isinstance(value, list) or (length is not None and len(value) != length):
        raise ValueError(f"{name} shape mismatch")
    if any(not _finite_number(item) for item in value):
        raise ValueError(f"{name} must contain finite JSON numbers")
    return [float(item) for item in value]


def validate_request(request: dict[str, Any]) -> None:
    """Validate the exact profile, input basis, row order, and content digests."""
    require_keys(request, REQUEST_FIELDS)
    if (
        request["schema"] != REQUEST_SCHEMA
        or request["profile"] != PROFILE_ID
        or request["method_fqn"] != METHOD_FQN
        or request["operation"] != OPERATION
    ):
        raise ValueError("unsupported profile, method identity, or operation")
    if not isinstance(request["job_id"], str) or not request["job_id"]:
        raise ValueError("server-owned MethodJob ID required")
    if type(request["seed"]) is not int or not 0 <= request["seed"] < 2**32:
        raise ValueError("seed must be a uint32 integer")
    if not _digest_string(request["lock_sha256"]):
        raise ValueError("lock digest malformed")
    if request["request_id"] != digest(
        {
            key: value
            for key, value in request.items()
            if key not in {"request_id", "request_sha256"}
        }
    ):
        raise ValueError("request ID binding mismatch")
    if request["request_sha256"] != digest(
        {key: value for key, value in request.items() if key != "request_sha256"}
    ):
        raise ValueError("request digest mismatch")

    source = request["source"]
    require_keys(source, SOURCE_FIELDS)
    ref = source["artifact_ref"]
    require_keys(
        ref,
        {"artifact_id", "kind", "media_type"},
        optional={"manifest_profile_sha256"},
    )
    if any(
        not isinstance(ref[key], str) or not ref[key]
        for key in ("artifact_id", "kind", "media_type")
    ):
        raise ValueError("typed source reference malformed")
    if not _digest_string(source["content_sha256"]):
        raise ValueError("source content digest malformed")

    data = request["data"]
    require_keys(data, DATA_FIELDS)
    row_ids = data["row_ids"]
    if not isinstance(row_ids, list) or len(row_ids) < 40:
        raise ValueError("at least 40 ordered source rows required")
    expected_rows = [f"{ref['artifact_id']}#row:{index}" for index in range(len(row_ids))]
    if row_ids != expected_rows:
        raise ValueError("source row order binding mismatch")
    if data["row_order_sha256"] != digest(row_ids):
        raise ValueError("row order digest mismatch")
    n_rows = len(row_ids)
    _finite_vector(data["y"], name="Y", length=n_rows)
    treatment = _finite_vector(data["t"], name="T", length=n_rows)
    if set(treatment) != {0.0, 1.0}:
        raise ValueError("both binary treatment arms are required")
    x_names = data["x_names"]
    w_names = data["w_names"]
    if not _valid_names(x_names) or not x_names or not _valid_names(w_names):
        raise ValueError("ordered feature names must be unique nonempty strings")
    _matrix(data["x"], name="X", rows=n_rows, columns=len(x_names))
    if data["w"] is None:
        if w_names:
            raise ValueError("W names require a W matrix")
    else:
        if not w_names:
            raise ValueError("W matrix requires ordered confounder names")
        _matrix(data["w"], name="W", rows=n_rows, columns=len(w_names))
    data_content = {key: value for key, value in data.items() if key != "data_sha256"}
    if data["data_sha256"] != digest(data_content):
        raise ValueError("Y/T/X/W/name/order content digest mismatch")
    if request["configuration"] != CONFIGURATION:
        raise ValueError("unsupported effective estimator configuration")


def _valid_names(value: object) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(name, str) and name for name in value)
        and len(value) == len(set(value))
    )


def _matrix(value: object, *, name: str, rows: int, columns: int) -> None:
    if not isinstance(value, list) or len(value) != rows:
        raise ValueError(f"{name} row count mismatch")
    for row in value:
        _finite_vector(row, name=name, length=columns)


def _digest_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_response_shape(response: dict[str, Any]) -> None:
    """Reject malformed top-level replies before their payload reaches the app."""
    require_keys(
        response,
        {
            "schema", "profile", "method_fqn", "operation", "job_id", "request_id",
            "request_sha256", "source", "data_sha256", "row_order_sha256", "lock_sha256",
            "environment", "authority", "outcome",
        },
    )
    if (
        response["schema"] != RESPONSE_SCHEMA
        or response["profile"] != PROFILE_ID
        or response["method_fqn"] != METHOD_FQN
        or response["operation"] != OPERATION
        or response["authority"] != "candidate_computation_only"
    ):
        raise ValueError("unsupported worker response identity")


def _matrix_rows(value: object, *, name: str, row_count: int, column_count: int) -> None:
    _matrix(value, name=name, rows=row_count, columns=column_count)
