from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest


def test_unresolved_requirement_reaches_served_value_consumer_without_catalog_rewrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise separate N7 and N8 consumers over one unchanged custom request."""
    from polisyos.core.components import DeclaredBuiltinLoader
    from polisyos.foundry.extensions import discovery
    from polisyos.foundry.extensions.registry import bootstrap_foundry_method_registry
    from polisyos.foundry.methods.catalog.bayesian.gp import GaussianProcessRegressionEstimator
    from polisyos.foundry.methods.catalog.econometrics.advanced import EventStudyEstimator
    from polisyos.foundry.methods.selection import advisor as advisor_module
    from polisyos.foundry.methods.selection.history import SelectionHistoryStore
    from polisyos.foundry.methods.selection.registry import registry_scope
    from polisyos.runtime.quality import generation_cycle as generation_cycle_module
    from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        GenerationCycleController,
    )
    from tests.unit.runtime.quality.test_value_gate import (
        _avg_income_candidate,
        _avg_income_problem,
        _controlled_avg_income_owner_profile,
        _simulation,
        _simulation_execution_context,
        _world_record,
    )

    project_root = Path(__file__).resolve().parents[3]
    request_text = "Estimate household income after local support in an unfamiliar domain."
    raw_domain = "unmapped:regional-support-policy"
    required_construct = "economic.gdp"
    scope_profile = {
        "profile_id": "scope:selection-served-usa-2024:v1",
        "jurisdiction": "USA",
        "population": "national_economy",
        "entity_scope": "country",
        "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
        "time_role": "observation_time",
        "granularity": "annual",
        "required_constructs": [required_construct],
    }
    seed_problem = _avg_income_problem()
    problem = seed_problem.model_copy(
        update={
            "domain": raw_domain,
            "problem_statement": request_text,
            "nl_provenance": seed_problem.nl_provenance.model_copy(
                update={"raw_request": request_text}
            ),
            "runtime_hints": {
                **seed_problem.runtime_hints,
                "n7_scope_profile": scope_profile,
            },
        }
    )
    assert isinstance(problem, DesignProblem)

    resolver = RequirementToCapabilityResolver.governed_fixture(project_root)
    n7 = GenerationCycleController(capability_resolver=resolver, repo_root=project_root)
    basis = n7._n7_data_requirement_basis_with_report(problem, acquisition_request={})
    domain_resolution = basis.compilation_report.metadata["scenario_domain_resolution"]
    assert domain_resolution["canonical_domain"] == "custom"
    assert domain_resolution["status"] == "unresolved"
    assert domain_resolution["raw_inputs"] == {"domain": raw_domain}
    resolution = next(
        row
        for row in basis.capability_resolutions or ()
        if row.query.construct == required_construct
    )
    assert resolution.query.construct == required_construct
    assert resolution.query.geography == "USA"
    assert resolution.query.population_filter == {"type": "national_economy"}
    assert resolution.query.entity_scope == "country"
    assert resolution.query.time_window.start == "2024-01-01"
    assert resolution.query.time_window.end == "2024-12-31"
    assert resolution.candidate_discovery is not None
    assert resolution.candidate_discovery.query == resolution.query
    assert resolution.candidate_discovery.satisfies_claim_evidence is False

    # N7's resolver result remains an acquisition artifact. N8 independently
    # binds the same DesignProblem to owner-derived value data before selection.
    requested_method = "bayesian.gp.gp_regression@1.0.0"
    panel_method = "econometrics.panel.event_study@1.0.0"
    # The bounded fixture's independent winner oracle is the declared source
    # tier: GP is exact; EventStudy is unverified. The owner profile is panel
    # shaped and below both typical minimums, so EventStudy's panel/data-shape
    # score is higher; GP must still win at the earlier truthfulness key.
    assert GaussianProcessRegressionEstimator.metadata.declared_truthfulness_tier == "exact"
    assert EventStudyEstimator.metadata.declared_truthfulness_tier is None
    assert GaussianProcessRegressionEstimator.metadata.typical_min_obs == 20
    assert EventStudyEstimator.metadata.typical_min_obs == 50
    monkeypatch.setattr(advisor_module, "get_global_selection_history", SelectionHistoryStore)
    selection_calls: list[dict[str, Any]] = []
    original_select = generation_cycle_module._select_value_method

    def capture_selection(**kwargs: Any) -> dict[str, Any]:
        result = original_select(**kwargs)
        selection_calls.append(
            {
                "problem": kwargs["problem"],
                "requested_method_fqn": kwargs["inputs"].get("method_fqn"),
                "result": result,
            }
        )
        return result

    monkeypatch.setattr(generation_cycle_module, "_select_value_method", capture_selection)
    monkeypatch.setattr(
        discovery,
        "BUILTIN_LOADER",
        DeclaredBuiltinLoader(
            target="tests._helpers.value_selection_fixture:singleton_value_components",
            group=discovery.ENTRY_POINT_GROUP,
        ),
    )
    profile = _controlled_avg_income_owner_profile()
    world = _world_record()
    base_candidate = _avg_income_candidate()
    candidate = replace(
        base_candidate,
        candidate_id="case-panel-alpha",
        atom=replace(base_candidate.atom, intervention_id="panel-id"),
    )

    def consume(
        *,
        consumer_problem: DesignProblem,
        method_request: str | None,
        loader: str,
    ) -> tuple[Any, dict[str, Any], Any]:
        monkeypatch.setattr(
            discovery,
            "BUILTIN_LOADER",
            DeclaredBuiltinLoader(
                target=f"tests._helpers.value_selection_fixture:{loader}",
                group=discovery.ENTRY_POINT_GROUP,
            ),
        )

        class OwnerGateway:
            def load_value_data_profile(
                self,
                *,
                candidate: object,
                problem: DesignProblem,
                world_record: object,
            ) -> Any:
                assert candidate is candidate_arg
                assert problem is consumer_problem
                assert world_record is world_arg
                return profile

        candidate_arg = candidate
        world_arg = world
        with registry_scope() as registry:
            registry_report = bootstrap_foundry_method_registry(
                registry,
                include_builtins=True,
                include_entry_points=False,
                include_dev_scan=False,
                require_bound_discovery_manifest=True,
            )
            assert registry_report.success
            assert registry_report.discovery_manifest is not None
            assert registry_report.discovery_manifest.is_bound
            simulation = _simulation(world, candidate_id=candidate.candidate_id)
            observation = FoundryValuePort(
                evaluation_context=_simulation_execution_context(
                    candidate=candidate,
                    simulation=simulation,
                    problem=consumer_problem,
                ),
                owner_gateway=OwnerGateway(),
                requested_method_fqn=method_request,
                method_registry=registry,
                method_registry_report=registry_report,
            )(
                candidate=candidate,
                simulation=simulation,
                problem=consumer_problem,
                cycle_index=0,
            )
            return observation, selection_calls[-1]["result"], registry_report

    singleton_problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "value_required_data_modalities": ("tabular",),
            }
        }
    )
    singleton_observation, singleton_selection, singleton_report = consume(
        consumer_problem=singleton_problem,
        method_request=requested_method,
        loader="singleton_value_components",
    )
    singleton_receipt = singleton_observation.method_selection_receipt
    assert singleton_selection["status"] == "selected"
    assert singleton_selection["selected_method_fqn"] == requested_method
    assert singleton_selection["denominator"] == (requested_method,)
    assert singleton_receipt is not None
    assert singleton_receipt.selected_method_fqn == requested_method
    assert singleton_receipt.denominator == (requested_method,)
    assert singleton_receipt.discovery_scope == "bound_discovery"
    assert singleton_observation.status == "value_blocked"
    assert singleton_observation.authority_blockers == ("treatment_assignment_not_owner_derived",)
    assert singleton_observation.decision_grade == "blocked"
    assert singleton_report.discovery_manifest is not None
    assert singleton_report.discovery_manifest.is_bound

    panel_problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "value_required_data_modalities": ("panel",),
            }
        }
    )
    panel_observation, panel_selection, _panel_report = consume(
        consumer_problem=panel_problem,
        method_request=requested_method,
        loader="two_value_components",
    )
    dispositions = {row["method_fqn"]: row for row in panel_selection["member_dispositions"]}
    assert panel_selection["status"] == "blocked"
    assert panel_selection["selected_method_fqn"] == requested_method
    assert panel_selection["denominator"] == tuple(sorted((requested_method, panel_method)))
    assert dispositions[requested_method]["reasons"] == ("required_data_modality_missing:panel",)
    assert dispositions[panel_method]["disposition"] == "eligible"
    assert panel_observation.authority_blockers == (
        "value_method_required_data_modality_unavailable",
    )
    assert panel_observation.status == "value_blocked"
    assert panel_observation.decision_grade == "blocked"
    assert panel_observation.selected_method_fqn == requested_method

    panel_success_observation, panel_success_selection, _panel_success_report = consume(
        consumer_problem=panel_problem,
        method_request=panel_method,
        loader="two_value_components",
    )
    panel_success_receipt = panel_success_observation.method_selection_receipt
    panel_success_dispositions = {
        row["method_fqn"]: row for row in panel_success_selection["member_dispositions"]
    }
    assert panel_success_selection["status"] == "selected"
    assert panel_success_selection["selected_method_fqn"] == panel_method
    assert panel_success_selection["denominator"] == tuple(sorted((requested_method, panel_method)))
    assert panel_success_dispositions[panel_method]["disposition"] == "eligible"
    assert panel_success_dispositions[requested_method]["reasons"] == (
        "required_data_modality_missing:panel",
    )
    assert panel_success_receipt is not None
    assert panel_success_receipt.selected_method_fqn == panel_method
    assert panel_success_receipt.denominator == tuple(sorted((requested_method, panel_method)))
    assert panel_success_observation.status == "value_blocked"
    assert panel_success_observation.selected_method_fqn == panel_method
    assert panel_success_observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
    assert panel_success_observation.decision_grade == "blocked"

    ranked_problem = problem.model_copy(update={"runtime_hints": problem.runtime_hints})
    ranked_observation, ranked_selection, _ranked_report = consume(
        consumer_problem=ranked_problem,
        method_request=None,
        loader="two_value_components",
    )
    ranked_receipt = ranked_observation.method_selection_receipt
    assert ranked_selection["status"] == "selected"
    assert ranked_selection["selected_method_fqn"] == requested_method
    assert ranked_receipt is not None
    assert ranked_receipt.selected_method_fqn == requested_method
    selected = next(row for row in ranked_receipt.ranked_alternatives if row.selected)
    loser = next(row for row in ranked_receipt.ranked_alternatives if not row.selected)
    assert selected.method_fqn == requested_method
    assert loser.method_fqn == panel_method
    assert selected.truthfulness_depth > loser.truthfulness_depth
    assert loser.advisor_score > selected.advisor_score
    assert loser.loss_reasons == ("advisor_truthfulness_depth_below_selected",)
    assert {row.method_fqn for row in ranked_receipt.ranked_alternatives} == {
        requested_method,
        panel_method,
    }
    assert ranked_observation.status == "value_blocked"
    assert ranked_observation.selected_method_fqn == requested_method
    assert ranked_observation.authority_blockers == ("treatment_assignment_not_owner_derived",)
    assert ranked_observation.decision_grade == "blocked"

    assert [call["requested_method_fqn"] for call in selection_calls] == [
        requested_method,
        requested_method,
        panel_method,
        None,
    ]
    for call, consumer_problem in zip(
        selection_calls,
        (singleton_problem, panel_problem, panel_problem, ranked_problem),
        strict=True,
    ):
        selected_problem = call["problem"]
        assert selected_problem.domain == raw_domain
        assert selected_problem.problem_statement == request_text
        assert selected_problem.nl_provenance.raw_request == request_text
        assert selected_problem.runtime_hints["n7_scope_profile"] == scope_profile
        assert selected_problem.runtime_hints.get("value_required_data_modalities") == (
            consumer_problem.runtime_hints.get("value_required_data_modalities")
        )
        assert selected_problem.runtime_hints["value_data_profile_content_hash"] == (
            profile.content_hash
        )
        assert consumer_problem.domain == raw_domain
        assert consumer_problem.problem_statement == request_text
        assert consumer_problem.nl_provenance.raw_request == request_text
