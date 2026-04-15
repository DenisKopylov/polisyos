"""Deterministic frontier helpers for legacy search controller flows."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from polisyos.common.serialization import stable_json_dumps, to_python_data
from polisyos.scientist.search.objective import ObjectiveValue

_VOLATILE_CANDIDATE_KEYS = frozenset(
    {
        "attempt",
        "cache_buster",
        "created_at",
        "fetched_at",
        "generated_at",
        "request_id",
        "retrieved_at",
        "retry",
        "run_id",
        "session_id",
        "span_id",
        "timestamp",
        "trace_id",
        "updated_at",
    }
)
_VOLATILE_CANDIDATE_SUFFIXES = (
    "_at",
    "_ts",
    "_timestamp",
)


@dataclass(frozen=True)
class FrontierPoint:
    """Internal representation of one Pareto-frontier candidate."""

    candidate: dict[str, Any]
    objectives: list[dict[str, Any]]
    normalized_values: tuple[float, ...]
    candidate_hash: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "candidate": dict(self.candidate),
            "candidate_hash": self.candidate_hash,
            "objectives": [dict(item) for item in self.objectives],
        }


def policy_candidate_hash(
    candidate: dict[str, Any],
    *,
    metadata_hash: str | None = None,
    explicit_hash: str | None = None,
) -> str:
    """Return a deterministic cache/frontier key for a candidate payload."""

    if isinstance(metadata_hash, str) and metadata_hash.strip():
        return metadata_hash.strip()
    if isinstance(explicit_hash, str) and explicit_hash.strip():
        return explicit_hash.strip()

    payload = stable_json_dumps(
        _strip_volatile_candidate_fields(to_python_data(candidate, sort_keys=True)),
        ensure_ascii=True,
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def update_legacy_pareto_front(
    frontier: Iterable[FrontierPoint],
    *,
    candidate: dict[str, Any],
    objectives: list[ObjectiveValue],
    cap: int = 100,
) -> list[FrontierPoint]:
    """Insert one candidate into the legacy Pareto frontier payload."""

    new_point = FrontierPoint(
        candidate=dict(candidate),
        objectives=[
            {
                "name": item.name,
                "raw_value": item.raw_value,
                "direction": item.direction.value,
            }
            for item in objectives
        ],
        normalized_values=tuple(item.normalized_value for item in objectives),
        candidate_hash=policy_candidate_hash(candidate),
    )

    surviving: list[FrontierPoint] = []
    for existing in frontier:
        if existing.candidate_hash == new_point.candidate_hash:
            if dominates(existing.normalized_values, new_point.normalized_values):
                return list(frontier)
            continue
        if not dominates(new_point.normalized_values, existing.normalized_values):
            surviving.append(existing)

    is_dominated = any(
        dominates(existing.normalized_values, new_point.normalized_values)
        for existing in surviving
    )
    if is_dominated:
        return surviving[:cap]

    surviving.append(new_point)
    surviving.sort(
        key=lambda item: (
            tuple(-value for value in item.normalized_values),
            item.candidate_hash,
        )
    )
    return surviving[:cap]


def dominates(a: Iterable[float], b: Iterable[float]) -> bool:
    """Return True if *a* dominates *b* (all <= and at least one <)."""

    left = tuple(a)
    right = tuple(b)
    if len(left) != len(right):
        return False
    at_least_one_better = False
    for left_value, right_value in zip(left, right, strict=False):
        if left_value > right_value:
            return False
        if left_value < right_value:
            at_least_one_better = True
    return at_least_one_better


def _strip_volatile_candidate_fields(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if _is_volatile_candidate_key(lowered):
                continue
            sanitized[key] = _strip_volatile_candidate_fields(raw_item)
        return sanitized
    if isinstance(value, list):
        return [_strip_volatile_candidate_fields(item) for item in value]
    return value


def _is_volatile_candidate_key(key: str) -> bool:
    if key.startswith("_"):
        return True
    if key in _VOLATILE_CANDIDATE_KEYS:
        return True
    return key.endswith(_VOLATILE_CANDIDATE_SUFFIXES)


__all__ = [
    "FrontierPoint",
    "dominates",
    "policy_candidate_hash",
    "update_legacy_pareto_front",
]
