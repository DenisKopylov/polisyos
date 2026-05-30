"""Small helpers for Runtime OpenAPI contract augmentation."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def iter_openapi_operations(schema: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Yield HTTP operations from a mutable OpenAPI schema payload."""
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post"}:
                continue
            if not isinstance(operation, dict):
                continue
            yield path, method.lower(), operation


def runtime_problem_example(
    *,
    status_code: int,
    code: str,
    path: str,
    request_id: str,
) -> dict[str, Any]:
    """Return the standard RuntimeApiProblem example payload for one route."""
    return {
        "type": "about:blank",
        "title": code.replace("_", " ").capitalize(),
        "status": status_code,
        "detail": f"{code} while processing request.",
        "code": code,
        "instance": path,
        "request_id": request_id,
        "error": code,
        "status_code": status_code,
    }
