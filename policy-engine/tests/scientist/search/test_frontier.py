"""Tests for deterministic search frontier helpers."""

from __future__ import annotations

from polisyos.scientist.search.frontier import (
    policy_candidate_hash,
    update_legacy_pareto_front,
)
from polisyos.scientist.search.objective import ObjectiveValue, OptimizationDirection


def test_policy_candidate_hash_ignores_volatile_metadata() -> None:
    base = {
        "candidate_id": "policy-a",
        "interventions": [{"target": "households", "rate": 0.1}],
        "trace_id": "trace-1",
        "_debug": {"attempt": 1},
        "metadata": {"generated_at": "2026-04-11T10:00:00Z", "source": "agent"},
    }
    equivalent = {
        "candidate_id": "policy-a",
        "interventions": [{"target": "households", "rate": 0.1}],
        "trace_id": "trace-2",
        "_debug": {"attempt": 2},
        "metadata": {"generated_at": "2026-04-11T11:00:00Z", "source": "agent"},
    }
    semantic_change = {
        "candidate_id": "policy-a",
        "interventions": [{"target": "households", "rate": 0.2}],
        "metadata": {"source": "agent"},
    }

    assert policy_candidate_hash(base) == policy_candidate_hash(equivalent)
    assert policy_candidate_hash(base) != policy_candidate_hash(semantic_change)


def test_update_legacy_pareto_front_dedupes_by_stable_candidate_hash() -> None:
    objectives = [
        ObjectiveValue(
            name="cost",
            raw_value=10.0,
            direction=OptimizationDirection.MINIMIZE,
        ),
        ObjectiveValue(
            name="benefit",
            raw_value=8.0,
            direction=OptimizationDirection.MAXIMIZE,
        ),
    ]

    frontier = update_legacy_pareto_front(
        [],
        candidate={"candidate_id": "a", "trace_id": "trace-1"},
        objectives=objectives,
    )
    frontier = update_legacy_pareto_front(
        frontier,
        candidate={"candidate_id": "a", "trace_id": "trace-2"},
        objectives=objectives,
    )

    assert len(frontier) == 1
    assert frontier[0].as_payload()["objectives"] == [
        {"name": "cost", "raw_value": 10.0, "direction": "minimize"},
        {"name": "benefit", "raw_value": 8.0, "direction": "maximize"},
    ]
