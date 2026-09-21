"""ACQ-01 regression coverage for the N7 requirement handoff."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
from polisyos.runtime.quality.acquisition_planner import (
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.design_problem import (
    CandidateLever,
    CandidateLeverSpace,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import GenerationCycleController


def _problem(
    *,
    problem_id: str = "acq_case",
    statement: str = "Ground firm survival with an owner-backed data source.",
    domain: str = "generic_policy",
    runtime_hints: dict[str, Any] | None = None,
) -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement=statement,
        domain=domain,
        nl_provenance=NLProvenance(
            raw_request=statement,
            source_surface="test_acq_01",
        ),
        authority_profile={
            "requester_authority": "research_lab",
            "requested_authority_level": "research",
            "mandate": "test-only acquisition handoff",
        },
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-09-21",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(),
        runtime_hints=runtime_hints or {},
    )


def test_n7_explicit_specs_take_precedence_and_preserve_empty_primary() -> None:
    hinted = ({"source": "runtime-hint"},)
    alias = ({"source": "compiled-alias"},)
    explicit = ({"source": "explicit"},)
    controller = GenerationCycleController()
    problem = _problem(runtime_hints={"n7_data_requirement_specs": hinted})

    assert controller._n7_data_requirement_specs(
        problem,
        acquisition_request={
            "data_requirement_specs": explicit,
            "compiled_requirement_specs": alias,
        },
    ) == explicit
    assert controller._n7_data_requirement_specs(
        problem,
        acquisition_request={
            "data_requirement_specs": (),
            "compiled_requirement_specs": alias,
        },
    ) == ()
    assert controller._n7_data_requirement_specs(
        problem,
        acquisition_request={"compiled_requirement_specs": alias},
    ) == alias


def test_n7_typed_any_of_gap_precedes_explicit_specs() -> None:
    gap = value_input_world_knowledge_requirement_gap(claim_ref="claim:acq")
    controller = GenerationCycleController()

    specs = controller._n7_data_requirement_specs(
        _problem(),
        acquisition_request={
            "requirement_gap": gap.model_dump(mode="json"),
            "data_requirement_specs": ({"source": "must-not-replace-gap"},),
            "compiled_requirement_specs": ({"source": "stale-alias"},),
        },
    )

    assert len(specs) == 1
    assert specs[0] == gap


def test_n7_fallback_handoff_preserves_statement_domain_scope_and_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ResolverPort:
        def resolve(self, _query: object) -> object:
            return object()

    resolver = _ResolverPort()
    captured: list[tuple[object, dict[str, Any]]] = []

    class _RecordingCompiler:
        def __init__(self, *, capability_resolver: object | None = None) -> None:
            captured.append((capability_resolver, {}))

        def compile_for_scenario(self, scenario: dict[str, Any]) -> SimpleNamespace:
            resolver_arg, _ = captured[-1]
            captured[-1] = (resolver_arg, scenario)
            return SimpleNamespace(specs=())

    monkeypatch.setattr(generation_cycle_module, "DataRequirementCompiler", _RecordingCompiler)
    controller = GenerationCycleController(capability_resolver=resolver)
    scope_a = {
        "profile_id": "pilot:ua:2026",
        "jurisdiction": "UA",
        "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
    }
    scope_b = {
        "profile_id": "pilot:pl:2027",
        "jurisdiction": "PL",
        "time_window": {"start": "2027-01-01", "end": "2027-12-31"},
    }

    controller._n7_data_requirement_specs(
        _problem(
            statement="Ground employment retention for Ukrainian firms.",
            domain="fiscal_policy",
        ),
        acquisition_request={
            "required_data_families": ("firm_panel",),
            "scope_profile": scope_a,
        },
    )
    controller._n7_data_requirement_specs(
        _problem(
            statement="Ground school attendance for Polish districts.",
            domain="education_policy",
        ),
        acquisition_request={
            "required_data_families": ("attendance_panel",),
            "scope_profile": scope_b,
        },
    )

    assert len(captured) == 2
    assert all(item[0] is resolver for item in captured)
    first, second = (item[1] for item in captured)
    assert first["text"] != second["text"]
    assert first["domain"] != second["domain"]
    assert first["scenario_profile"] == scope_a
    assert second["scenario_profile"] == scope_b


def test_n7_missing_resolver_or_empty_specs_does_not_call_closed_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    compiler_args: list[object | None] = []

    class _EmptyCompiler:
        def __init__(self, *, capability_resolver: object | None = None) -> None:
            compiler_args.append(capability_resolver)

        def compile_for_scenario(self, _scenario: dict[str, Any]) -> SimpleNamespace:
            return SimpleNamespace(specs=())

    monkeypatch.setattr(generation_cycle_module, "DataRequirementCompiler", _EmptyCompiler)
    controller = GenerationCycleController(repo_root=tmp_path)
    problem = _problem()
    assert controller._n7_data_requirement_specs(
        problem,
        acquisition_request={"required_data_families": ("unresolved_family",)},
    ) == ()
    assert compiler_args == [None]

    monkeypatch.setattr(
        controller,
        "_n7_world_snapshot",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(controller, "_n7_owner_gateway", lambda *_args: object())

    def _unexpected_closed_loop(**_kwargs: object) -> object:
        raise AssertionError("empty specs must not mint an acquisition receipt")

    monkeypatch.setattr(
        generation_cycle_module,
        "run_acquisition_closed_loop",
        _unexpected_closed_loop,
    )
    cycle = SimpleNamespace(
        terminal_kind="acquisition_required",
        cycle_index=0,
        revision_request=SimpleNamespace(
            strategy_payload={
                "acquisition_request": {
                    "required_data_families": ("unresolved_family",),
                }
            }
        ),
    )

    assert controller._run_n7_acquisition_if_requested(problem, cycle=cycle) is None
