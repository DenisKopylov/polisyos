"""Exact candidate labor problem shared by native and served fixture owners."""

from __future__ import annotations

from polisyos.runtime.quality.design_problem import DesignProblem
from tests._helpers.controlled_candidate_profile import _problem

LABOR_SCOPE_SOURCE = (
    "For USA and a 2024 policy time, use 2024 data as of 2024-12-31. "
    "Assess a budget-allocation multiplier on government.balance against the "
    "global.unemployment_rate outcome for the total labor force, seeking to minimize it. "
    "US labor analysts review the candidate."
)


def labor_candidate_problem() -> DesignProblem:
    """Return a typed USA/2024 labor scenario without any empirical effect claim."""
    payload = _problem("lane01_served_labor_candidate").model_dump(mode="json")
    payload.update(
        schema_version="policyos.runtime.design_problem.v3",
        domain="social",
        problem_statement="Compare a candidate modeled unemployment input for USA in 2024.",
        nl_provenance={
            "raw_request": (
                "Compare a candidate modeled unemployment input for USA in 2024. "
                "Do not promote generated candidates."
            ),
            "source_surface": "test_lane01_native_controller",
        },
        jurisdiction_time={
            "region": "USA",
            "valid_time": "2024",
            "as_of": "2026-11-03",
            "policy_time": "2024",
            "data_time": "2024",
        },
        outcome_of_interest={
            "target_variable": "global.unemployment_rate",
            "metric_id": "unemployment_rate",
            "estimand": "candidate_scenario_comparison",
        },
        objectives=[
            {
                "objective_id": "unemployment",
                "description": "Compare the declared modeled rate.",
                "metric_id": "unemployment_rate",
                "direction": "minimize",
            }
        ],
        runtime_hints={
            "n7_scope_profile": {
                "profile_id": "scope:lane01-usa-labor-2024:v1",
                "jurisdiction": "USA",
                "population": "total_labor_force",
                "entity_scope": "country",
                "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
                "time_role": "observation_time",
                "granularity": "annual",
                "required_constructs": ["labor.unemployment_rate"],
            }
        },
    )
    return DesignProblem.model_validate(payload)


def served_labor_candidate_problem(
    fiscal_base: DesignProblem, *, raw_request: str
) -> DesignProblem:
    """Bind a controlled labor request to the same declared multiplier intervention."""
    if LABOR_SCOPE_SOURCE not in raw_request:
        raise ValueError("served_labor_fixture_request_scope_mismatch")
    payload = fiscal_base.model_dump(mode="json")
    labor = labor_candidate_problem().model_dump(mode="json")
    for key in (
        "domain",
        "problem_statement",
        "outcome_of_interest",
        "objectives",
        "runtime_hints",
    ):
        payload[key] = labor[key]
    payload["jurisdiction_time"] = {
        "region": "USA",
        "valid_time": "2024",
        "as_of": "2024-12-31",
        "policy_time": "2024",
        "data_time": "2024",
    }
    payload["nl_provenance"]["raw_request"] = raw_request
    payload["candidate_lever_space"]["candidate_levers"][0]["lever_id"] = "labor_budget_multiplier"
    payload["stakeholders"] = [
        {
            "stakeholder_id": "labor_analysts",
            "name": "US labor analysts",
            "role": "reviewer",
        }
    ]
    payload["constraints"][0].update(
        constraint_id="labor_request_scope",
        description="Keep the candidate within the requested USA 2024 labor scope.",
        source_text=LABOR_SCOPE_SOURCE,
    )
    return DesignProblem.model_validate(payload)
