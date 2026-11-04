"""Explicit budget accounting choices preserve the legacy NL request wire."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from polisyos.core.contracts import NaturalLanguageRunRequest, RunBudgetScope
from polisyos.core.contracts.control import RunBudgetScope as CanonicalRunBudgetScope


def test_legacy_budget_scope_is_absent_after_json_round_trip() -> None:
    request = NaturalLanguageRunRequest(request="Study the policy", run_budget_usd=5)

    assert request.run_budget_scope is None
    assert "run_budget_scope" not in request.model_fields_set
    assert "run_budget_scope" not in request.model_dump(mode="json")
    assert "candidate_acquisition_intent" not in request.model_dump(mode="json")
    reopened = NaturalLanguageRunRequest.model_validate_json(
        request.model_dump_json(exclude_unset=True)
    )
    assert "run_budget_scope" not in reopened.model_fields_set
    assert reopened.run_budget_usd == 5
    assert "candidate_acquisition_intent" not in reopened.model_fields_set


@pytest.mark.parametrize("scope", get_args(RunBudgetScope))
def test_explicit_budget_scope_is_preserved_in_the_request_wire(scope: str) -> None:
    request = NaturalLanguageRunRequest.model_validate(
        {"request": "Study the policy", "run_budget_usd": 5, "run_budget_scope": scope}
    )

    assert request.model_dump(mode="json")["run_budget_scope"] == scope
    reopened = NaturalLanguageRunRequest.model_validate_json(
        request.model_dump_json(exclude_unset=True)
    )
    assert reopened.run_budget_scope == scope
    assert "run_budget_scope" in reopened.model_fields_set
    assert reopened.run_budget_usd == request.run_budget_usd


def test_explicit_null_remains_distinct_from_omission_without_selecting_a_mode() -> None:
    request = NaturalLanguageRunRequest.model_validate(
        {"request": "Study the policy", "run_budget_scope": None}
    )

    assert request.run_budget_scope is None
    assert "run_budget_scope" in request.model_fields_set
    assert request.model_dump(mode="json")["run_budget_scope"] is None


@pytest.mark.parametrize("scope", [True, 1, "", "allow", "unlimited", {}])
def test_budget_scope_refuses_non_modes(scope: object) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageRunRequest.model_validate(
            {"request": "Study the policy", "run_budget_scope": scope}
        )


def test_budget_scope_public_alias_and_schema_use_the_same_finite_choices() -> None:
    assert RunBudgetScope is CanonicalRunBudgetScope
    field = NaturalLanguageRunRequest.model_json_schema()["properties"]["run_budget_scope"]
    assert field["anyOf"][0]["enum"] == list(get_args(RunBudgetScope))
    assert "run_budget_scope" not in NaturalLanguageRunRequest.model_json_schema()["required"]


def test_explicit_experiment_intent_survives_the_request_wire() -> None:
    request = NaturalLanguageRunRequest.model_validate(
        {
            "request": "Study the policy",
            "run_budget_usd": 5,
            "run_budget_scope": "metered_paid_producers_and_bounded_candidate",
            "candidate_acquisition_intent": "bounded_experiment_voi_unknown",
        }
    )
    reopened = NaturalLanguageRunRequest.model_validate_json(
        request.model_dump_json(exclude_unset=True)
    )
    assert reopened.candidate_acquisition_intent == "bounded_experiment_voi_unknown"
    assert "candidate_acquisition_intent" in reopened.model_fields_set
    assert reopened.run_budget_scope == request.run_budget_scope
    assert reopened.run_budget_usd == 5


def test_explicit_null_experiment_intent_selects_no_experiment() -> None:
    request = NaturalLanguageRunRequest.model_validate(
        {"request": "Study the policy", "candidate_acquisition_intent": None}
    )
    assert request.candidate_acquisition_intent is None
    assert "candidate_acquisition_intent" in request.model_fields_set
    assert request.model_dump(mode="json")["candidate_acquisition_intent"] is None


@pytest.mark.parametrize("intent", [True, 1, "", "allow", "positive_voi", {}])
def test_experiment_intent_refuses_other_values(intent: object) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageRunRequest.model_validate(
            {"request": "Study the policy", "candidate_acquisition_intent": intent}
        )
