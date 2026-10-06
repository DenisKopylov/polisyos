"""Per-run state ownership for the legacy search controller."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from polisyos.scientist.methods.search.contracts import ParetoViewProjection


class GenerationTransition(str, Enum):
    """Typed transitions emitted by the candidate-generation boundary."""

    TRANSIENT_EMPTY = "transient_empty"
    EXHAUSTED = "exhausted"


class _EvaluationDisposition(str, Enum):
    """Classify one evaluated candidate at the run-state boundary."""

    ORDINARY = "ordinary"
    SENTINEL = "sentinel"


@dataclass(frozen=True)
class _EvaluationTransition:
    """Carry one internal candidate disposition and its detached history record."""

    disposition: _EvaluationDisposition
    record: Any


@dataclass
class SearchRunState:
    """Mutable state owned by exactly one controller run."""

    search_id: str = ""
    status: Enum | None = None
    history: list[Any] = field(default_factory=list)
    best_candidate: dict[str, Any] | None = None
    best_objective: float = float("inf")
    pareto_front: list[dict[str, Any]] = field(default_factory=list)
    pareto_points: list[Any] = field(default_factory=list)
    stage_a_evaluations: int = 0
    stage_b_evaluations: int = 0
    sentinel_evaluations: int = 0
    generation_attempts: int = 0
    empty_generation_attempts: int = 0
    evaluation_iterations: int = 0
    training_evaluations: int = 0
    budget_spent: float = 0.0
    budget_available: bool = False
    budget_snapshot: dict[str, float] = field(default_factory=dict)
    budget_snapshot_source: str = "unavailable"
    budget_ledger_id: str | None = None
    budget_ledger_revision: int | None = None
    policy_evaluation_errors: int = 0
    generation_transition: GenerationTransition | None = None
    pareto_projection: ParetoViewProjection | None = None

    @property
    def history_size(self) -> int:
        """Return the number of records available to surrogate consumers."""
        return len(self.history)

    @property
    def new_evaluations(self) -> int:
        """Return ordinary evaluations from the current run.

        Warm-start records and sentinel checks are intentionally not part of
        this stopping counter.  The existing ``evaluation_iterations`` field
        remains the source of truth so a second mutable ledger is not created.
        """
        return self.evaluation_iterations

    @property
    def evaluation_count(self) -> int:
        """Return every Stage B evaluation, including sentinels."""
        return self.stage_b_evaluations

    @property
    def scientific_evaluations(self) -> int:
        """Return non-sentinel Stage B evaluations used by the search signal."""
        return max(0, self.stage_b_evaluations - self.sentinel_evaluations)

    def generation_transition_payload(self) -> dict[str, Any] | None:
        """Return a detached, typed transition payload for a public result."""
        if self.generation_transition is None:
            return None
        return {
            "kind": self.generation_transition.value,
            "generation_attempts": self.generation_attempts,
            "evaluation_iterations": self.evaluation_iterations,
            "budget_spent": self.budget_spent,
            "budget_available": self.budget_available,
            "history_size": self.history_size,
            "training_evaluations": self.training_evaluations,
            "new_evaluations": self.new_evaluations,
            "evaluation_count": self.evaluation_count,
            "scientific_evaluations": self.scientific_evaluations,
            "sentinel_evaluations": self.sentinel_evaluations,
        }

    def apply_evaluation_transition(self, transition: _EvaluationTransition) -> None:
        """Apply one candidate disposition to the sole run-state owner.

        Sentinel evaluations remain observable through their dedicated count but
        do not consume an ordinary evaluation iteration or enter ordinary
        history. Every ordinary transition updates both values together.
        """
        if transition.disposition is _EvaluationDisposition.SENTINEL:
            self.sentinel_evaluations += 1
            return
        self.history.append(transition.record)
        self.evaluation_iterations += 1

    def apply_tell_transition(
        self,
        transition: _EvaluationTransition,
        *,
        stage_a_evaluated: bool,
        stage_b_evaluated: bool = True,
    ) -> None:
        """Apply one externally evaluated candidate through this state owner.

        Ask/tell adapters report evaluator feedback without invoking the
        controller's full loop.  Stage A rejection is a valid terminal path
        for the candidate and therefore must not be counted as a Stage B
        evaluation.  Counters and history still enter through the same
        transition owner used by ``SearchController.run``; adapters must not
        maintain a second mutable ledger.
        """
        if stage_a_evaluated:
            self.stage_a_evaluations += 1
        if stage_b_evaluated:
            self.stage_b_evaluations += 1
        self.apply_evaluation_transition(transition)

    def snapshot(self) -> SearchRunState:
        """Return a deep snapshot that cannot be changed by a later run."""
        return deepcopy(self)

    def checkpoint_state(self) -> dict[str, Any]:
        """Encode the sole ledger without serializing callbacks or owner handles."""
        return checkpoint_json(self)

    @classmethod
    def from_checkpoint(cls, payload: dict[str, Any]) -> SearchRunState:
        """Rebuild typed history/frontier and refuse malformed ledger primitives."""
        from polisyos.scientist.methods.search.controller import SearchIteration, SearchStatus
        from polisyos.scientist.methods.search.frontier import FrontierPoint
        from polisyos.scientist.methods.search.objective import (
            ObjectiveValue,
            OptimizationDirection,
        )
        from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

        raw = checkpoint_value(payload)
        if not isinstance(raw, dict) or set(raw) != {item.name for item in fields(cls)}:
            raise ValueError("search checkpoint ledger fields do not match")
        for item in fields(cls):
            if type(item.default) is int:
                value = raw[item.name]
                if type(value) is not int or value < 0:
                    raise ValueError(f"invalid search counter: {item.name}")
            elif type(item.default) is bool and type(raw[item.name]) is not bool:
                raise ValueError(f"invalid search flag: {item.name}")
        if not isinstance(raw["search_id"], str) or not raw["search_id"]:
            raise ValueError("search checkpoint requires a run identity")
        raw["status"] = SearchStatus(raw["status"])
        transition = raw["generation_transition"]
        raw["generation_transition"] = GenerationTransition(transition) if transition else None
        history = []
        for row in raw["history"]:
            if not isinstance(row, dict) or set(row) != {
                item.name for item in fields(SearchIteration)
            }:
                raise ValueError("invalid search history record")
            if type(row["iteration"]) is not int or row["iteration"] < -1:
                raise ValueError("invalid search history iteration")
            for name in ("is_promising", "stage_a_passed"):
                if type(row[name]) is not bool:
                    raise ValueError(f"invalid search history flag: {name}")
            if not isinstance(row["candidate"], dict):
                raise ValueError("invalid search history candidate")
            for name in ("objective_value", "duration_seconds"):
                if type(row[name]) not in (int, float):
                    raise ValueError(f"invalid search history number: {name}")
            if not math.isfinite(row["duration_seconds"]) or row["duration_seconds"] < 0:
                raise ValueError("invalid search history duration")
            details = []
            for detail in row["objective_details"]:
                if set(detail) != {item.name for item in fields(ObjectiveValue)}:
                    raise ValueError("invalid objective detail")
                if type(detail["is_satisfied"]) is not bool:
                    raise ValueError("invalid objective satisfaction flag")
                for name in ("raw_value", "weight", "threshold"):
                    if detail[name] is not None and type(detail[name]) not in (int, float):
                        raise ValueError("invalid objective detail number")
                detail["direction"] = OptimizationDirection(detail["direction"])
                details.append(ObjectiveValue(**detail))
            row["objective_details"] = details
            if row["policy_evaluation"] is not None:
                row["policy_evaluation"] = PolicyEvaluationVector.model_validate(
                    row["policy_evaluation"]
                )
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])
            if row["timestamp"].tzinfo is None:
                raise ValueError("search history timestamp must be timezone aware")
            history.append(SearchIteration(**row))
            _validate_dataclass(history[-1])
        raw["history"] = history
        if len(history) != raw["evaluation_iterations"] + raw["training_evaluations"]:
            raise ValueError("search checkpoint history/counter mismatch")
        if sum(row.iteration == -1 for row in history) != raw["training_evaluations"]:
            raise ValueError("search checkpoint warm-history mismatch")
        ordinary_stage_b = sum(row.stage_a_passed for row in history if row.iteration != -1)
        if (
            not ordinary_stage_b
            <= raw["stage_b_evaluations"]
            <= ordinary_stage_b + raw["sentinel_evaluations"]
        ):
            raise ValueError("search checkpoint stage-B/counter mismatch")
        if type(raw["best_objective"]) not in (int, float):
            raise ValueError("invalid best objective")
        if raw["best_candidate"] is not None and not isinstance(raw["best_candidate"], dict):
            raise ValueError("invalid best candidate")
        points = []
        for point in raw["pareto_points"]:
            if set(point) != {item.name for item in fields(FrontierPoint)}:
                raise ValueError("invalid frontier point")
            point["normalized_values"] = tuple(point["normalized_values"])
            if any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in point["normalized_values"]
            ):
                raise ValueError("invalid frontier coordinates")
            points.append(FrontierPoint(**point))
        raw["pareto_points"] = points
        if raw["pareto_projection"] is not None:
            raw["pareto_projection"] = ParetoViewProjection.model_validate(raw["pareto_projection"])
        result = cls(**raw)
        _validate_dataclass(result)
        if not math.isfinite(result.budget_spent) or result.budget_spent < 0:
            raise ValueError("invalid recorded budget spend")
        if any(not math.isfinite(value) or value < 0 for value in result.budget_snapshot.values()):
            raise ValueError("invalid recorded budget snapshot")
        if result.budget_ledger_revision is not None and result.budget_ledger_revision < 0:
            raise ValueError("invalid recorded budget revision")
        return result


def _validate_dataclass(value: Any) -> None:
    """Check all declared ledger primitives without Pydantic's legacy coercion."""

    def valid(item: Any, annotation: Any) -> bool:
        if annotation is Any:
            return True
        origin = get_origin(annotation)
        arguments = get_args(annotation)
        if origin is UnionType:
            return any(valid(item, choice) for choice in arguments)
        if origin is list:
            return isinstance(item, list) and all(valid(entry, arguments[0]) for entry in item)
        if origin is dict:
            return isinstance(item, dict) and all(
                valid(key, arguments[0]) and valid(entry, arguments[1])
                for key, entry in item.items()
            )
        if annotation is float:
            return type(item) in (int, float)
        if annotation in (int, bool, str, type(None)):
            return type(item) is annotation
        return isinstance(item, annotation)

    for name, annotation in get_type_hints(type(value)).items():
        if not valid(getattr(value, name), annotation):
            raise ValueError(f"invalid search checkpoint primitive: {name}")


_NONFINITE_KEY = "__search_nonfinite_float__"


def checkpoint_json(value: Any) -> Any:
    """Encode supported JSON data, preserving unavailable objective signals."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return checkpoint_json(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: checkpoint_json(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        if _NONFINITE_KEY in value or any(not isinstance(key, str) for key in value):
            raise ValueError("search checkpoint payload contains a reserved or non-string key")
        return {key: checkpoint_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [checkpoint_json(item) for item in value]
    if type(value) is float and not math.isfinite(value):
        return {_NONFINITE_KEY: "nan" if math.isnan(value) else "inf" if value > 0 else "-inf"}
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError(f"unsupported search checkpoint value: {type(value).__name__}")


def checkpoint_value(value: Any) -> Any:
    """Decode only the reserved nonfinite carrier, never arbitrary object types."""
    if isinstance(value, dict):
        if _NONFINITE_KEY in value:
            if set(value) != {_NONFINITE_KEY} or value[_NONFINITE_KEY] not in (
                "inf",
                "-inf",
                "nan",
            ):
                raise ValueError("invalid search nonfinite carrier")
            return float(value[_NONFINITE_KEY])
        return {key: checkpoint_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [checkpoint_value(item) for item in value]
    return value


__all__ = ["GenerationTransition", "SearchRunState"]
