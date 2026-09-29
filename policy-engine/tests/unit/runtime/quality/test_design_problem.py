from __future__ import annotations

from typing import Any

import pytest

from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.runtime.quality.assurance_case import build_policy_intent_envelope
from polisyos.runtime.quality.design_problem import DesignProblem, OutcomeOfInterest


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _design_problem(**overrides: Any) -> DesignProblem:
    payload: dict[str, Any] = {
        "design_problem_id": "design_problem_ua_msme_credit",
        "problem_statement": "Wartime MSMEs face liquidity constraints.",
        "domain": "social",
        "nl_provenance": {
            "raw_request": (
                "Design a wartime MSME credit guarantee for Ukraine within the stated "
                "UAH 10b budget cap."
            ),
            "source_surface": "runtime.control.nl_request",
            "source_context": {"run_id": "run-design-problem"},
        },
        "authority_profile": {
            "requester_authority": "research",
            "requested_authority_level": "research",
            "mandate": "Cabinet research mandate; budget cap is requester supplied.",
        },
        "jurisdiction_time": {
            "region": "UA",
            "valid_time": "2026-05-15",
            "as_of": "2026-05-12",
            "policy_time": "2026-05-15",
            "data_time": "2024-2026",
            "time_semantics": {
                "frequency": "Q",
                "start_date": "2024-01-01",
                "step_count": 8,
            },
        },
        "objectives": [
            {
                "objective_id": "increase_msme_survival",
                "description": "Increase MSME survival.",
                "metric_id": "msme_survival_rate",
                "direction": "maximize",
            }
        ],
        "constraints": [
            {
                "constraint_id": "budget_cap",
                "description": "Stay within the stated UAH 10b budget cap.",
                "hard": True,
                "admissibility_basis": "request_text",
                "source_text": "UAH 10b budget cap",
            }
        ],
        "stakeholders": [
            {"stakeholder_id": "wartime_msmes", "name": "wartime MSMEs", "role": "beneficiary"}
        ],
        "outcome_of_interest": {
            "target_variable": "firm_survival",
            "metric_id": "msme_survival_rate",
            "estimand": "P(firm_survival | do(credit_access))",
            "direction": "maximize",
        },
        "candidate_lever_space": {
            "allowed_operator_kinds": ["credit_guarantee"],
            "candidate_levers": [
                {
                    "lever_id": "credit_access_guarantee",
                    "operator_kind": "credit_guarantee",
                    "instrument": "state-backed credit guarantee",
                    "target_slot": "credit_access",
                }
            ],
        },
        "evidence_acquisition_needs": {
            "needs": [
                {
                    "need_id": "credit_panel",
                    "question": "Measure credit access and firm survival for eligible MSMEs.",
                    "required_for": "outcome_of_interest",
                    "status": "required",
                    "source_hint": "measurement_root",
                }
            ]
        },
        "model_spec_ref": "sha256:" + "2" * 64,
    }
    payload.update(overrides)
    return DesignProblem.model_validate(payload)


def _projection_signature(problem: DesignProblem) -> dict[str, Any]:
    return {
        "design_problem_id": problem.design_problem_id,
        "problem_statement": problem.problem_statement,
        "domain": problem.domain,
        "nl_provenance": problem.nl_provenance.model_dump(mode="json"),
        "authority_profile": problem.authority_profile.model_dump(mode="json"),
        "jurisdiction_time": problem.jurisdiction_time.model_dump(mode="json"),
        "objectives": [item.model_dump(mode="json") for item in problem.objectives],
        "constraints": [item.model_dump(mode="json") for item in problem.constraints],
        "stakeholders": [item.model_dump(mode="json") for item in problem.stakeholders],
        "outcome_of_interest": problem.outcome_of_interest.model_dump(mode="json"),
        "candidate_lever_space": problem.candidate_lever_space.model_dump(mode="json"),
        "evidence_acquisition_needs": problem.evidence_acquisition_needs.model_dump(
            mode="json"
        ),
        "model_spec_ref": problem.model_spec_ref,
    }


def test_design_problem_spans_owner_surfaces_and_projects_shared_fields() -> None:
    problem = _design_problem()

    scientist_frame = problem.to_scientist_problem_frame()
    assert scientist_frame.problem_statement == problem.problem_statement
    assert scientist_frame.domain == "social"
    assert scientist_frame.goals == ("Increase MSME survival.",)
    assert scientist_frame.constraints == ("Stay within the stated UAH 10b budget cap.",)
    assert scientist_frame.context["design_problem_id"] == problem.design_problem_id
    assert scientist_frame.context["outcome_of_interest"]["target_variable"] == "firm_survival"

    ir_frame = problem.to_ir_problem_frame()
    assert ir_frame.problem_id == problem.design_problem_id
    assert ir_frame.domain.value == "social"
    assert ir_frame.objectives[0].metric_id == "msme_survival_rate"
    assert ir_frame.hard_constraints[0].constraint_id == "budget_cap"
    assert ir_frame.stakeholders[0].stakeholder_id == "wartime_msmes"

    policy_request = problem.to_policy_request_frame()
    assert policy_request.policy_question == problem.problem_statement
    assert policy_request.jurisdiction == "UA"
    assert policy_request.goals == ["Increase MSME survival."]
    assert policy_request.constraints == ["Stay within the stated UAH 10b budget cap."]

    model_spec = problem.to_model_spec(data_snapshot_ref=_sha("3"))
    assert isinstance(model_spec.time_semantics, TimeSemantics)
    assert model_spec.time_semantics == problem.jurisdiction_time.time_semantics
    assert problem.model_spec_ref == _sha("2")


def test_design_problem_v1_keeps_its_historical_unqualified_slot_grammar() -> None:
    """A current parser must not widen the vocabulary of saved v1 problems."""

    payload = _design_problem().model_dump(mode="json")
    payload["schema_version"] = "policyos.runtime.design_problem.v1"
    payload["candidate_lever_space"]["candidate_levers"][0]["target_slot"] = (
        "government.balance"
    )

    with pytest.raises(ValueError, match="design_problem_v1_target_slot_invalid"):
        DesignProblem.model_validate(payload)


def test_design_problem_default_remains_v1_for_historical_hash_compatibility() -> None:
    """Newly constructed generic models retain the prior source-hash default."""

    assert _design_problem().schema_version == "policyos.runtime.design_problem.v1"


def test_design_problem_v2_accepts_canonical_qualified_slot_and_v1_control() -> None:
    """The current schema admits canonical dotted slots while v1 stays readable."""

    payload = _design_problem().model_dump(mode="json")
    payload["schema_version"] = "policyos.runtime.design_problem.v2"
    payload["candidate_lever_space"]["candidate_levers"][0]["target_slot"] = (
        "government.balance"
    )
    current = DesignProblem.model_validate(payload)
    assert current.candidate_lever_space.candidate_levers[0].target_slot == (
        "government.balance"
    )

    legacy_payload = _design_problem().model_dump(mode="json")
    legacy_payload["schema_version"] = "policyos.runtime.design_problem.v1"
    legacy = DesignProblem.model_validate(legacy_payload)
    assert legacy.candidate_lever_space.candidate_levers[0].target_slot == (
        "credit_access"
    )


def test_v2_projection_decoder_remains_supported_after_v3_becomes_current() -> None:
    """Explicit v2 projections remain reconstructable after the current bump."""

    problem = _design_problem(schema_version="policyos.runtime.design_problem.v2")
    projected = DesignProblem._from_projection_payload(
        problem.model_dump(mode="json")
    )
    assert projected == problem


def test_design_problem_v3_accepts_qualified_outcome_without_widening_v1_v2() -> None:
    """Only v3 problems can bind qualified canonical outcome identifiers."""

    payload = _design_problem().model_dump(mode="json")
    payload["outcome_of_interest"]["target_variable"] = "government.balance"
    for schema_version in (
        "policyos.runtime.design_problem.v1",
        "policyos.runtime.design_problem.v2",
        "policyos.runtime.design_problem.legacy-import",
    ):
        payload["schema_version"] = schema_version
        with pytest.raises(ValueError):
            DesignProblem.model_validate(payload)

    payload["schema_version"] = "policyos.runtime.design_problem.v3"
    problem = DesignProblem.model_validate(payload)
    assert problem.outcome_of_interest.target_variable == "government.balance"
    assert problem.schema_version == "policyos.runtime.design_problem.v3"


def test_design_problem_outcome_json_schema_matches_versioned_runtime_grammar() -> None:
    """The exported DesignProblem schema applies the same parent-version grammar."""

    from jsonschema import Draft202012Validator

    schema = DesignProblem.model_json_schema()
    validator = Draft202012Validator(schema)
    for schema_version, target_variable, expected in (
        ("policyos.runtime.design_problem.v1", "firm_survival", True),
        ("policyos.runtime.design_problem.v1", "government.balance", False),
        ("policyos.runtime.design_problem.v2", "firm_survival", True),
        ("policyos.runtime.design_problem.v2", "government.balance", False),
        ("policyos.runtime.design_problem.v3", "firm_survival", True),
        ("policyos.runtime.design_problem.v3", "government.balance", True),
        ("policyos.runtime.design_problem.legacy-import", "government.balance", False),
    ):
        payload = _design_problem().model_dump(mode="json")
        payload["schema_version"] = schema_version
        payload["outcome_of_interest"]["target_variable"] = target_variable
        assert validator.is_valid(payload) is expected, (schema_version, target_variable)

    for schema_version, target_slot, expected in (
        ("policyos.runtime.design_problem.v1", "credit_access", True),
        ("policyos.runtime.design_problem.v1", "government.balance", False),
        ("policyos.runtime.design_problem.v2", "credit_access", True),
        ("policyos.runtime.design_problem.v2", "government.balance", True),
        ("policyos.runtime.design_problem.v3", "credit_access", True),
        ("policyos.runtime.design_problem.v3", "government.balance", True),
        ("policyos.runtime.design_problem.legacy-import", "government.balance", False),
    ):
        payload = _design_problem().model_dump(mode="json")
        payload["schema_version"] = schema_version
        payload["candidate_lever_space"]["candidate_levers"][0]["target_slot"] = (
            target_slot
        )
        assert validator.is_valid(payload) is expected, (schema_version, target_slot)


def test_standalone_outcome_of_interest_remains_unqualified() -> None:
    """The nested v3 capability does not widen the standalone outcome contract."""

    from jsonschema import Draft202012Validator

    payload = {
        "target_variable": "government.balance",
        "metric_id": "government_balance",
        "estimand": "cash balance after acquisition",
        "direction": "maximize",
    }
    with pytest.raises(ValueError):
        OutcomeOfInterest.model_validate(payload)
    assert not Draft202012Validator(OutcomeOfInterest.model_json_schema()).is_valid(payload)

    valid = OutcomeOfInterest.model_validate(
        {
            **payload,
            "target_variable": "government_balance",
        }
    )
    forged_instance = valid.model_copy(
        update={"target_variable": "government.balance"}
    )
    with pytest.raises(ValueError):
        OutcomeOfInterest.model_validate(forged_instance)

    problem_payload = _design_problem(
        schema_version="policyos.runtime.design_problem.v3"
    ).model_dump(mode="python")
    problem_payload["outcome_of_interest"] = forged_instance
    with pytest.raises(ValueError):
        DesignProblem.model_validate(problem_payload)


def test_design_problem_unknown_historical_schema_keeps_legacy_slot_grammar() -> None:
    """Unknown historical schema strings remain readable without widening slots."""

    payload = _design_problem().model_dump(mode="json")
    payload["schema_version"] = "policyos.runtime.design_problem.legacy-import"
    assert DesignProblem.model_validate(payload).schema_version == payload["schema_version"]

    payload["candidate_lever_space"]["candidate_levers"][0]["target_slot"] = (
        "government.balance"
    )
    with pytest.raises(ValueError, match="design_problem_legacy_target_slot_invalid"):
        DesignProblem.model_validate(payload)


def test_design_problem_json_schema_matches_versioned_slot_grammar() -> None:
    """The exported schema and runtime parser agree for legacy and current slots."""

    from jsonschema import Draft202012Validator

    schema = DesignProblem.model_json_schema()
    validator = Draft202012Validator(schema)
    cases = (
        (None, "government.balance", False),
        ("policyos.runtime.design_problem.v1", "government.balance", False),
        ("policyos.runtime.design_problem.v1", "credit_access", True),
        ("policyos.runtime.design_problem.v2", "government.balance", True),
        ("policyos.runtime.design_problem.legacy-import", "credit_access", True),
        ("policyos.runtime.design_problem.legacy-import", "government.balance", False),
    )
    for schema_version, target_slot, expected in cases:
        payload = _design_problem().model_dump(mode="json")
        if schema_version is None:
            payload.pop("schema_version", None)
        else:
            payload["schema_version"] = schema_version
        payload["candidate_lever_space"]["candidate_levers"][0]["target_slot"] = (
            target_slot
        )
        assert validator.is_valid(payload) is expected, (
            schema_version,
            target_slot,
        )


def test_candidate_lever_accepts_canonical_qualified_ir_slot() -> None:
    problem = _design_problem(
        schema_version="policyos.runtime.design_problem.v2",
        candidate_lever_space={
            "allowed_operator_kinds": ["credit_guarantee"],
            "candidate_levers": [
                {
                    "lever_id": "credit_access_guarantee",
                    "operator_kind": "credit_guarantee",
                    "instrument": "state-backed credit guarantee",
                    "target_slot": "credit_access",
                },
                {
                    "lever_id": "government_balance_guarantee",
                    "operator_kind": "credit_guarantee",
                    "instrument": "state-backed credit guarantee",
                    "target_slot": "government.balance",
                }
            ],
        }
    )

    assert tuple(
        lever.target_slot for lever in problem.candidate_lever_space.candidate_levers
    ) == (
        "credit_access",
        "government.balance",
    )


def test_candidate_lever_rejects_noncanonical_hyphenated_slot() -> None:
    with pytest.raises(ValueError, match="target_slot"):
        _design_problem(
            candidate_lever_space={
                "allowed_operator_kinds": ["credit_guarantee"],
                "candidate_levers": [
                    {
                        "lever_id": "credit_access_guarantee",
                        "operator_kind": "credit_guarantee",
                        "instrument": "state-backed credit guarantee",
                        "target_slot": "government.balance-sheet",
                    }
                ],
            }
        )


def test_design_problem_round_trips_policy_intent_shared_fields() -> None:
    intent = build_policy_intent_envelope(
        intent_id="intent-run-1",
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        policy_problem="Wartime MSMEs face liquidity constraints.",
        desired_outcome="Increase MSME survival.",
        proposed_intervention="Targeted credit guarantee.",
        jurisdiction="UA",
        target_population="wartime MSMEs",
        policy_time="2026-05-15",
        data_time="2024-2026",
        requester_preferred_conclusion=None,
        requested_authority_level="research",
        affected_stakeholders=["wartime MSMEs"],
        constraints=["UAH 10b budget cap"],
        objectives=["Increase MSME survival."],
        evidence_expectations=["audited credit panel"],
        authoring_provenance={"captured_by": "test"},
    )

    problem = DesignProblem.from_policy_intent_envelope(
        intent,
        raw_request="Design a targeted credit guarantee under the UAH 10b budget cap.",
        outcome_of_interest={
            "target_variable": "firm_survival",
            "metric_id": "msme_survival_rate",
            "estimand": "P(firm_survival | do(credit_access))",
            "direction": "maximize",
        },
        candidate_lever_space={
            "allowed_operator_kinds": ["credit_guarantee"],
            "candidate_levers": [
                {
                    "lever_id": "credit_access_guarantee",
                    "operator_kind": "credit_guarantee",
                    "instrument": "credit guarantee",
                    "target_slot": "credit_access",
                }
            ],
        },
    )
    projected = problem.to_policy_intent_envelope()

    assert projected["policy_problem"] == intent["policy_problem"]
    assert projected["desired_outcome"] == intent["desired_outcome"]
    assert projected["jurisdiction"] == intent["jurisdiction"]
    assert projected["policy_time"] == intent["policy_time"]
    assert projected["data_time"] == intent["data_time"]
    assert projected["requested_authority_level"] == intent["requested_authority_level"]


def test_design_problem_projection_round_trips_preserve_shared_fields() -> None:
    problem = _design_problem(
        objectives=[
            {
                "objective_id": "increase_msme_survival",
                "description": "Increase MSME survival.",
                "metric_id": "msme_survival_rate",
                "direction": "maximize",
            },
            {
                "objective_id": "reduce_defaults",
                "description": "Reduce guarantee defaults.",
                "metric_id": "default_rate",
                "direction": "minimize",
            },
        ],
        constraints=[
            {
                "constraint_id": "budget_cap",
                "description": "Stay within the stated UAH 10b budget cap.",
                "hard": True,
                "admissibility_basis": "request_text",
                "source_text": "UAH 10b budget cap",
            },
            {
                "constraint_id": "no_bank_only",
                "description": "Avoid bank-only eligibility.",
                "hard": False,
                "admissibility_basis": "request_text",
                "source_text": "MSME credit guarantee",
            },
        ],
        stakeholders=[
            {
                "stakeholder_id": "wartime_msmes",
                "name": "wartime MSMEs",
                "role": "beneficiary",
            },
            {
                "stakeholder_id": "fiscal_authority",
                "name": "fiscal authority",
                "role": "budget_owner",
            },
        ],
        authority_profile={
            "requester_authority": "cabinet research unit",
            "requested_authority_level": "research",
            "mandate": "Cabinet research mandate; budget cap is requester supplied.",
            "authority_refs": ["cabinet://research/credit-guarantees"],
        },
    )
    expected = _projection_signature(problem)

    intent_round_trip = DesignProblem.from_policy_intent_envelope(
        problem.to_policy_intent_envelope(),
        raw_request=problem.nl_provenance.raw_request,
        outcome_of_interest=problem.outcome_of_interest.model_dump(mode="json"),
        candidate_lever_space=problem.candidate_lever_space.model_dump(mode="json"),
    )
    scientist_round_trip = DesignProblem.from_scientist_problem_frame(
        problem.to_scientist_problem_frame(),
        authority_profile=problem.authority_profile.model_dump(mode="json"),
        jurisdiction_time=problem.jurisdiction_time.model_dump(mode="json"),
        outcome_of_interest=problem.outcome_of_interest.model_dump(mode="json"),
        candidate_lever_space=problem.candidate_lever_space.model_dump(mode="json"),
    )
    ir_round_trip = DesignProblem.from_ir_problem_frame(problem.to_ir_problem_frame())
    model_round_trip = DesignProblem.from_model_spec(
        problem.to_model_spec(data_snapshot_ref=_sha("3"))
    )
    request_round_trip = DesignProblem.from_policy_request_frame(
        problem.to_policy_request_frame(),
        authority_profile=problem.authority_profile.model_dump(mode="json"),
        outcome_of_interest=problem.outcome_of_interest.model_dump(mode="json"),
        candidate_lever_space=problem.candidate_lever_space.model_dump(mode="json"),
    )

    assert _projection_signature(intent_round_trip) == expected
    assert _projection_signature(scientist_round_trip) == expected
    assert _projection_signature(ir_round_trip) == expected
    assert _projection_signature(model_round_trip) == expected
    assert _projection_signature(request_round_trip) == expected
    assert DesignProblem.projection_lossy_fields("policy_intent_envelope") == ()
    assert DesignProblem.projection_lossy_fields("scientist_problem_frame") == ()
    assert DesignProblem.projection_lossy_fields("ir_problem_frame") == ()
    assert DesignProblem.projection_lossy_fields("model_spec") == ()
    assert DesignProblem.projection_lossy_fields("policy_request_frame") == ()


def test_design_problem_rejects_invented_admissibility() -> None:
    with pytest.raises(ValueError, match="invented_admissibility"):
        _design_problem(
            constraints=[
                {
                    "constraint_id": "wto_compliance",
                    "description": "Must satisfy an unstated WTO compliance rule.",
                    "hard": True,
                    "admissibility_basis": "llm_inferred",
                    "source_text": "WTO compliance",
                }
            ]
        )


def test_design_problem_rejects_empty_required_span_dimensions() -> None:
    with pytest.raises(ValueError, match="design_problem_stakeholders_empty"):
        _design_problem(stakeholders=[])
