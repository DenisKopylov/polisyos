"""Tests for deterministic search frontier helpers."""

from __future__ import annotations

import pytest

from polisyos.scientist.methods.search.contracts import CandidateProposal, CandidateStrategyContext
from polisyos.scientist.methods.search.frontier import (
    policy_candidate_hash,
    strategy_candidate_payload,
    update_legacy_pareto_front,
)
from polisyos.scientist.methods.search.objective import EmploymentObjective, GDPGrowthObjective


@pytest.mark.parametrize(
    "change",
    [
        {"trace_id": "trace-2"},
        {"_debug": {"attempt": 2}},
        {"metadata": {"generated_at": "2026-04-11T11:00:00Z", "source": "agent"}},
    ],
)
def test_policy_candidate_hash_includes_all_raw_subject_fields(change: dict[str, object]) -> None:
    base = {
        "candidate_id": "policy-a",
        "interventions": [{"target": "households", "rate": 0.1}],
        "trace_id": "trace-1",
        "_debug": {"attempt": 1},
        "metadata": {"generated_at": "2026-04-11T10:00:00Z", "source": "agent"},
    }

    assert policy_candidate_hash(base) != policy_candidate_hash({**base, **change})
    assert policy_candidate_hash(base) == policy_candidate_hash(dict(reversed(list(base.items()))))


def test_legacy_frontier_deduplicates_only_typed_transport_for_the_same_subject() -> None:
    source = {
        "gdp_change": 8.0,
        "employment_rate": 0.5,
        "metric_units": {"gdp_change": "ratio", "employment_rate": "ratio"},
    }
    objectives = [
        GDPGrowthObjective(expected_unit="ratio").evaluate(source),
        EmploymentObjective(expected_unit="ratio").evaluate(source),
    ]
    assert all(objective.is_satisfied for objective in objectives)
    frontier = []
    first_subject = {"starts_at": "2026-04-11T10:00:00Z"}
    second_subject = {"starts_at": "2026-04-12T10:00:00Z"}
    for transport_id, subject in (
        ("trace-1", first_subject),
        ("trace-2", first_subject),
        ("trace-3", second_subject),
    ):
        context = CandidateStrategyContext(
            subject=subject,
            strategy_fields={"candidate_id": transport_id},
        )
        proposal = CandidateProposal(
            candidate_id=transport_id,
            payload=strategy_candidate_payload(context),
            strategy_context=context,
        )
        frontier = update_legacy_pareto_front(
            frontier,
            candidate=proposal.payload,
            objectives=objectives,
            proposal=proposal,
        )

    assert {point.candidate_hash for point in frontier} == {
        policy_candidate_hash(first_subject),
        policy_candidate_hash(second_subject),
    }
    assert all(
        point.as_payload()["objectives"]
        == [
            {"name": "gdp_growth", "raw_value": 8.0, "direction": "maximize"},
            {"name": "employment", "raw_value": 0.5, "direction": "maximize"},
        ]
        for point in frontier
    )
