"""Deterministic frontier helpers for legacy search controller flows."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.common.serialization import stable_json_dumps, to_python_data
from polisyos.scientist.methods.autotune.pareto import finite_real_scalar
from polisyos.scientist.methods.search.objective import (
    ObjectiveValue,
    OptimizationDirection,
)

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
_TECHNICAL_CANDIDATE_ENVELOPES = frozenset(
    {
        "audit",
        "execution",
        "metadata",
        "provenance",
        "telemetry",
        "transport",
    }
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
    """Hash actual content; producer markers remain provenance, not equality authority."""

    del metadata_hash, explicit_hash

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

    existing_points: list[FrontierPoint] = []
    existing_basis: tuple[tuple[str, str], ...] | None = None
    for point in frontier:
        admitted = _objective_basis_and_values(point.objectives)
        coordinates = _finite_coordinates(point.normalized_values)
        if admitted is None or coordinates is None or coordinates != admitted[1]:
            continue
        if existing_basis is not None and admitted[0] != existing_basis:
            raise ValueError("Legacy frontier contains inconsistent objective basis")
        existing_basis = admitted[0]
        existing_points.append(point)

    admitted = _objective_basis_and_values(objectives)
    if admitted is None:
        # The caller retains unavailable objective details in search history;
        # they cannot enter this finite-coordinate frontier export.
        return existing_points[:cap]
    if existing_basis is not None and admitted[0] != existing_basis:
        raise ValueError("Legacy frontier objective basis changed")

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
        normalized_values=admitted[1],
        candidate_hash=policy_candidate_hash(candidate),
    )

    surviving: list[FrontierPoint] = []
    for existing in existing_points:
        if existing.candidate_hash == new_point.candidate_hash:
            if dominates(existing.normalized_values, new_point.normalized_values):
                return existing_points[:cap]
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

    left = _finite_coordinates(a)
    right = _finite_coordinates(b)
    if left is None or right is None or not left or len(left) != len(right):
        return False
    at_least_one_better = False
    for left_value, right_value in zip(left, right, strict=False):
        if left_value > right_value:
            return False
        if left_value < right_value:
            at_least_one_better = True
    return at_least_one_better


def _finite_coordinates(values: Iterable[Any]) -> tuple[float, ...] | None:
    coordinates: list[float] = []
    for raw in values:
        value = finite_real_scalar(raw)
        if value is None:
            return None
        coordinates.append(value)
    return tuple(coordinates)


def _objective_basis_and_values(
    objectives: Iterable[ObjectiveValue | Mapping[str, Any]],
) -> tuple[tuple[tuple[str, str], ...], tuple[float, ...]] | None:
    basis: list[tuple[str, str]] = []
    values: list[float] = []
    names: set[str] = set()
    for objective in objectives:
        if isinstance(objective, ObjectiveValue):
            name, raw, direction = (
                objective.name,
                objective.raw_value,
                objective.direction,
            )
            if not isinstance(direction, OptimizationDirection):
                return None
        elif isinstance(objective, Mapping):
            name, raw = objective.get("name"), objective.get("raw_value")
            try:
                direction = OptimizationDirection(objective.get("direction"))
            except (TypeError, ValueError):
                return None
        else:
            return None
        if not isinstance(name, str) or not name or name in names:
            return None
        coordinates = _finite_coordinates((raw,))
        if coordinates is None:
            return None
        names.add(name)
        basis.append((name, direction.value))
        value = coordinates[0]
        values.append(-value if direction == OptimizationDirection.MAXIMIZE else value)
    if not basis:
        return None
    return tuple(basis), tuple(values)


def _strip_volatile_candidate_fields(
    value: Any,
    *,
    technical: bool = False,
    root: bool = True,
) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if key.startswith("_"):
                continue
            if _is_volatile_candidate_key(lowered, technical=technical, root=root):
                continue
            sanitized[key] = _strip_volatile_candidate_fields(
                raw_item,
                technical=technical
                or (root and lowered in _TECHNICAL_CANDIDATE_ENVELOPES),
                root=False,
            )
        return sanitized
    if isinstance(value, list):
        return [
            _strip_volatile_candidate_fields(item, technical=technical, root=False)
            for item in value
        ]
    return value


def _is_volatile_candidate_key(
    key: str,
    *,
    technical: bool = False,
    root: bool = False,
) -> bool:
    if key.startswith("_"):
        return True
    if key in _VOLATILE_CANDIDATE_KEYS and (technical or root):
        return True
    return technical and key.endswith(_VOLATILE_CANDIDATE_SUFFIXES)


__all__ = [
    "FrontierPoint",
    "dominates",
    "policy_candidate_hash",
    "update_legacy_pareto_front",
]
