"""Semantic identity witnesses for the evaluated subject and fresh reader."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

# isort: split
import json

import pytest

from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    CandidateStrategyContext,
    EvaluationBundle,
    LegacySearchServiceAdapter,
    ParetoBasisScope,
)
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.frontier import (
    materialize_candidate_proposal,
    policy_candidate_hash,
    strategy_candidate_payload,
    update_legacy_pareto_front,
)
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    EmploymentObjective,
    GDPGrowthObjective,
    ObjectiveValue,
)
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry, ParetoView
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.transfer_context import TransferContext
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchConfig,
    HierarchicalSearchCoordinator,
    PolicyParameterCodec,
)

from .test_contracts import _Generator, _Objective
from .test_pareto_transfer import _candidate, _evaluation_vector


def _rich_candidate() -> PolicyCandidateSchema:
    from polisyos.ir.governance.problem_frame import ConstraintSpec, ConstraintType
    from polisyos.ir.kernel.values import MoneyValue

    candidate = _candidate().model_copy(deep=True)
    candidate.trinity_bundle.problem_frame.hard_constraints.append(
        ConstraintSpec(
            constraint_id="budget_cap",
            constraint_type=ConstraintType.HARD,
            value=MoneyValue(amount=Decimal("100"), currency="USD"),
            operator="<=",
            notes=["budget ceiling"],
        )
    )
    return candidate


def _objectives(cost: float, benefit: float) -> list[ObjectiveValue]:
    source = {
        "gdp_change": benefit,
        "employment_rate": 1.0 / cost,
        "metric_units": {"gdp_change": "fixture-unit", "employment_rate": "fixture-unit"},
    }
    values = [
        GDPGrowthObjective(expected_unit="fixture-unit").evaluate(source),
        EmploymentObjective(expected_unit="fixture-unit").evaluate(source),
    ]
    assert all(value.score_status.value == "available" for value in values)
    return values


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ({"_starts_at": "2026-01-01"}, {"_starts_at": "2026-01-02"}),
        ({"metadata": {"_starts_at": 1}}, {"metadata": {"_starts_at": 2}}),
        ({"execution": {"created_at": 1}}, {"execution": {"created_at": 2}}),
        ({"__user_input": 1}, {"__user_input": 2}),
        ({"_strategy_metadata": {"seed": 1}}, {"_strategy_metadata": {"seed": 2}}),
    ],
)
def test_bare_semantic_keys_reach_two_incomparable_frontier_points(left, right) -> None:
    assert policy_candidate_hash(left) != policy_candidate_hash(right)
    frontier = update_legacy_pareto_front([], candidate=left, objectives=_objectives(1.0, 1.0))
    frontier = update_legacy_pareto_front(
        frontier, candidate=right, objectives=_objectives(2.0, 2.0)
    )
    assert {point.candidate_hash for point in frontier} == {
        policy_candidate_hash(left),
        policy_candidate_hash(right),
    }
    assert policy_candidate_hash({"a": 1, "b": 2}) == policy_candidate_hash({"b": 2, "a": 1})


def test_unexecuted_unknown_metadata_and_non_json_values_refuse() -> None:
    for value in (Decimal("1.25"), (1, 2), {1, 2}, float("nan")):
        with pytest.raises((TypeError, ValueError)):
            policy_candidate_hash({"x": value})
    with pytest.raises(ValueError, match="metadata_not_evaluated"):
        materialize_candidate_proposal(
            CandidateProposal(candidate_id="one", payload={"x": 1}, metadata={"seed": 42})
        )
    assert policy_candidate_hash({"seed": 42}) != policy_candidate_hash({"seed": 43})
    assert policy_candidate_hash({"x": "1.25"})


def test_context_binds_exact_payload_and_only_declared_transport() -> None:
    subject = {"x": 1.0, "_strategy_metadata": {"seed": 1}}
    first = CandidateStrategyContext(subject=subject, strategy_fields={"candidate_id": "a"})
    second = CandidateStrategyContext(subject=subject, strategy_fields={"candidate_id": "b"})
    a = CandidateProposal(
        candidate_id="a",
        payload=strategy_candidate_payload(first),
        strategy_context=first,
    )
    b = CandidateProposal(
        candidate_id="b",
        payload=strategy_candidate_payload(second),
        strategy_context=second,
    )
    assert a.payload == b.payload
    assert a.payload["_strategy_metadata"] == {"seed": 1}
    assert policy_candidate_hash(a) == policy_candidate_hash(b)
    changed = deepcopy(subject)
    changed["_strategy_metadata"]["seed"] = 2
    third = CandidateStrategyContext(subject=changed, strategy_fields={"candidate_id": "a"})
    c = CandidateProposal(
        candidate_id="a",
        payload=strategy_candidate_payload(third),
        strategy_context=third,
    )
    assert policy_candidate_hash(a) != policy_candidate_hash(c)
    forged = a.model_copy(update={"payload": {**a.payload, "x": 2.0}})
    with pytest.raises(ValueError, match="payload_mismatch"):
        policy_candidate_hash(forged)
    with pytest.raises(ValueError, match="supplied_hash_mismatch"):
        policy_candidate_hash(a, metadata_hash="sha256:forged")


def test_registry_refuses_unbound_or_wrong_evaluation_before_any_write(
    tmp_path,
) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    subject = {"x": 1.0, "_starts_at": "2026-01-01"}
    good_subject_id = policy_candidate_hash(subject)
    scope = TransferContext(
        task_family="policy", domain="fiscal", run_id="unbound", tenant_hash="tenant-a"
    )
    other_evaluation = _evaluation_vector(_candidate())
    for evaluation, reason in (
        (other_evaluation, "candidate_evaluation_hash_mismatch"),
        (
            other_evaluation.model_copy(update={"metadata": {}}),
            "candidate_evaluation_subject_binding_missing",
        ),
    ):
        with pytest.raises(ValueError, match=reason):
            registry.update(
                "unbound",
                candidate_hash=good_subject_id,
                evaluation=evaluation,
                seed_payload=subject,
                transfer_context=scope,
            )
        assert not registry._snapshot_path("unbound").exists()
        assert not registry._catalog_path(scope).exists()


def test_policy_strategy_semantic_metadata_refuses_before_evaluation() -> None:
    from polisyos.scientist.methods.search.strategies.types import PolicyCandidate

    candidate = _candidate()
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        )
    )
    spec = coordinator.build_parameter_search_spec(candidate)
    adapter = StrategyAdapter(
        RandomSearchStrategy(space=spec.search_space, seed=1),
        spec.search_space,
        codec=PolicyParameterCodec(spec.parameter_paths, spec.template_values),
        canonical_template=candidate,
    )
    proposal = PolicyCandidate(params={}, metadata={"seed": 7})
    with pytest.raises(ValueError, match="policy_strategy_semantics_not_consumed"):
        adapter._candidate_to_proposal(
            proposal, {"candidate_template": candidate.as_search_payload()}
        )


def test_matching_caller_digest_does_not_establish_source_or_rank(tmp_path) -> None:
    candidate = _candidate()
    context = CandidateStrategyContext(
        producer="policy_design",
        subject=candidate.model_dump(mode="json", exclude_none=True),
        policy_schema=True,
        policy_transport=True,
    )
    proposal = CandidateProposal(
        candidate_id=candidate.candidate_id,
        payload=strategy_candidate_payload(context),
        strategy_context=context,
    )
    evaluation = _evaluation_vector(candidate)
    axes = sorted(evaluation.frontier_objectives("global_feasible"))
    assert axes
    scope = TransferContext(
        task_family="policy", domain="fiscal", run_id="asserted", tenant_hash="tenant-a"
    )
    registry = ParetoRegistry(tmp_path / "registry")
    registry.update(
        "asserted",
        candidate_hash=candidate.candidate_hash(),
        candidate_proposal=proposal,
        seed_payload=proposal.payload,
        evaluation=evaluation,
        transfer_context=scope,
        objective_basis_by_view={
            "global_feasible": ParetoBasisScope(scope="declared", coordinate_ids=axes)
        },
    )
    snapshot = ParetoRegistry(tmp_path / "registry").get_snapshot(
        "asserted", transfer_context=scope
    )
    projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert projection.assessment.status == "no_usable_inputs"
    assert not projection.ranked_frontier_hashes
    assert snapshot.entries[candidate.candidate_hash()].view_membership == []
    assert "global_feasible" not in snapshot.hypervolume_by_view
    assert registry.get_frontier("asserted", transfer_context=scope) == []


def test_tell_mismatch_retains_pending_and_does_not_change_best_or_history() -> None:
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1), objective=CompositeObjective([_Objective()])
        ),
        candidate_generator=_Generator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"objective_value": 1.0}
        },
    )
    service = LegacySearchServiceAdapter(controller)
    proposal = service.ask(None, None, {})[0]
    before = service.owner._service_tell_snapshot()
    with pytest.raises(ValueError, match="supplied_hash_mismatch"):
        service.tell(
            proposal.candidate_id,
            EvaluationBundle(
                objective_value=1.0,
                is_promising=True,
                stage_b_result={
                    "simulation_results": {"objective_value": 1.0},
                    "candidate_hash": "sha256:forged",
                },
            ),
        )
    assert service.owner._service_tell_snapshot() == before
    result = service.tell(
        proposal.candidate_id,
        EvaluationBundle(
            objective_value=1.0,
            is_promising=True,
            stage_b_result={"simulation_results": {"objective_value": 1.0}},
        ),
    )
    assert result.history_length == 1
    assert result.best_candidate == proposal.payload


def test_strategy_policy_identity_survives_registry_restart(tmp_path) -> None:
    candidate = _rich_candidate()
    constraint_value = candidate.model_dump(mode="json", exclude_none=True)["trinity_bundle"][
        "problem_frame"
    ]["hard_constraints"][0]["value"]
    assert "nominal_year" not in constraint_value
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        )
    )
    spec = coordinator.build_parameter_search_spec(candidate)
    adapter = StrategyAdapter(
        RandomSearchStrategy(space=spec.search_space, seed=11),
        spec.search_space,
        codec=PolicyParameterCodec(spec.parameter_paths, spec.template_values),
        canonical_template=candidate,
    )
    proposal = adapter.generate_proposal(
        [], None, {"candidate_template": candidate.as_search_payload()}
    )
    assert proposal.strategy_context is not None and proposal.strategy_context.policy_schema
    reconstructed = PolicyCandidateSchema.model_validate(proposal.strategy_context.subject)
    assert policy_candidate_hash(proposal) == reconstructed.candidate_hash()
    assert materialize_candidate_proposal(proposal) == proposal.payload
    evaluation = _evaluation_vector(reconstructed)
    scope = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="subject-run",
        tenant_hash="tenant-a",
    )
    registry = ParetoRegistry(tmp_path / "registry")
    registry.update(
        "subject-run",
        candidate_hash=reconstructed.candidate_hash(),
        evaluation=evaluation,
        seed_payload=proposal.payload,
        candidate_proposal=proposal,
        transfer_context=scope,
    )
    fresh = ParetoRegistry(tmp_path / "registry").get_snapshot(
        "subject-run", transfer_context=scope
    )
    assert list(fresh.entries) == [reconstructed.candidate_hash()]
    persisted = fresh.entries[reconstructed.candidate_hash()]
    assert persisted.candidate_proposal is not None
    assert persisted.candidate_proposal.payload == proposal.payload
    assert policy_candidate_hash(persisted.candidate_proposal) == reconstructed.candidate_hash()
    target = TransferContext(
        task_family="policy", domain="fiscal", run_id="target", tenant_hash="tenant-a"
    )
    warm = ParetoRegistry(tmp_path / "registry").build_warm_start_evaluations(target)
    assert len(warm) == 1
    assert warm[0]["metadata"]["seed_only"] is True
    assert (
        CandidateProposal.model_validate(warm[0]["candidate_proposal"]).payload == proposal.payload
    )
    registry.update(
        "subject-run",
        candidate_hash=reconstructed.candidate_hash(),
        evaluation=evaluation,
        seed_payload=proposal.payload,
        candidate_proposal=proposal,
        transfer_context=scope,
    )
    assert (
        len(
            ParetoRegistry(tmp_path / "registry")
            .get_snapshot("subject-run", transfer_context=scope)
            .entries
        )
        == 1
    )


def test_rejected_run_result_preserves_real_attempt_without_champion(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([_Objective()]),
            pareto_registry=registry,
        ),
        candidate_generator=_Generator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"objective_value": 1.0},
            "candidate_hash": "sha256:forged",
        },
    )
    result = controller.run({})
    assert result.stage_a_evaluations == 1 and result.stage_b_evaluations == 1
    assert result.best_candidate is None
    assert len(result.history) == 1
    assert result.history[0].policy_evaluation_error == "candidate_identity_mismatch"
    assert not result.history[0].is_promising
    assert not registry._snapshot_path(result.search_id).exists()


def test_legacy_unbound_evaluation_is_neither_rekeyed_nor_ranked(tmp_path) -> None:
    candidate = _candidate()
    subject = candidate.model_dump(mode="json", exclude_none=True)
    context = CandidateStrategyContext(
        producer="policy_design",
        subject=subject,
        policy_schema=True,
        policy_transport=True,
    )
    proposal = CandidateProposal(
        candidate_id=candidate.candidate_id,
        payload=strategy_candidate_payload(context),
        strategy_context=context,
    )
    scope = TransferContext(
        task_family="policy", domain="fiscal", run_id="old-run", tenant_hash="tenant-a"
    )
    registry = ParetoRegistry(tmp_path / "registry")
    registry.update(
        "old-run",
        candidate_hash=candidate.candidate_hash(),
        evaluation=_evaluation_vector(candidate),
        seed_payload=proposal.payload,
        candidate_proposal=proposal,
        transfer_context=scope,
    )
    path = registry._snapshot_path("old-run")
    old = json.loads(path.read_text())
    old["schema_version"] = "3.0"
    old.pop("identity_rule", None)
    for entry in old["entries"].values():
        entry.pop("candidate_proposal", None)
        entry.pop("identity_origin", None)
        # A forged retained subject with no evaluation binding must not acquire
        # the old objective under a new subject key.
        entry["seed_payload"]["_starts_at"] = "2030-01-01"
        entry["evaluation"]["metadata"].pop("candidate_hash", None)
    path.write_text(json.dumps(old))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="legacy_evaluation_subject_unbound"):
        ParetoRegistry(tmp_path / "registry").get_snapshot("old-run", transfer_context=scope)
    assert path.read_bytes() == original
    catalog_path = registry._catalog_path(scope)
    old_catalog = json.loads(catalog_path.read_text())
    old_catalog["schema_version"] = "3.0"
    old_catalog.pop("identity_rule", None)
    for entry in old_catalog["entries"].values():
        entry.pop("candidate_proposal", None)
        entry.pop("identity_origin", None)
        entry["seed_payload"]["_starts_at"] = "2030-01-01"
        entry["evaluation"]["metadata"].pop("candidate_hash", None)
    catalog_path.write_text(json.dumps(old_catalog))
    catalog_original = catalog_path.read_bytes()
    target = TransferContext(
        task_family="policy", domain="fiscal", run_id="target", tenant_hash="tenant-a"
    )
    bundle = ParetoRegistry(tmp_path / "registry").get_seed_bundle(target)
    assert not bundle.entries
    assert bundle.scope_refusals
    assert catalog_path.read_bytes() == catalog_original


def test_real_strategy_lifecycle_persists_and_reloads_two_replicas(tmp_path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.methods.search.objective import (
        EmploymentObjective,
        GDPGrowthObjective,
        configured_objective_rule_spec,
    )
    from polisyos.scientist.methods.search.strategies.space import SearchSpace
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.methods.search.strategies.types import (
        ParameterBounds,
        PolicyCandidate,
    )

    class FixedStrategy(RandomSearchStrategy):
        def suggest(self, evaluations, pending=None):
            del pending
            return PolicyCandidate(
                candidate_id=f"attempt-{len(evaluations)}",
                params={"x": 0.25},
                source_strategy="fixed",
            )

    space = SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)])
    objectives = [
        GDPGrowthObjective(expected_unit="fixture-unit"),
        EmploymentObjective(expected_unit="fixture-unit"),
    ]
    fingerprint = RunFingerprint(
        run_id="provided-run",
        space_hash=space.sobol_space_fingerprint(),
        objective_names=[item.name for item in objectives],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={item.name: "fixture-unit" for item in objectives},
        origin="fixture",
        tenant_id="fixture",
        objective_directions={item.name: item.direction.value for item in objectives},
        objective_rule_specs={
            item.name: configured_objective_rule_spec(item) or "" for item in objectives
        },
    )
    manager = TransferLearningManager(FileSystemCAS(tmp_path / "cas"), object())
    calls = []

    def stage_b(candidate, context):
        del context
        calls.append(deepcopy(candidate))
        return {
            "simulation_results": {
                "gdp_change": 0.0,
                "employment_rate": 0.5,
                "metric_units": {
                    "gdp_change": "fixture-unit",
                    "employment_rate": "fixture-unit",
                },
            },
            "metadata": {"replica_id": len(calls)},
            "feedback": {"verdict": "APPROVE"},
        }

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(2),
            objective=CompositeObjective(objectives),
            transfer_manager=manager,
            transfer_fingerprint=fingerprint,
        ),
        candidate_generator=StrategyAdapter(FixedStrategy(space=space, seed=1), space),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=stage_b,
    )
    result = controller.run({})
    assert len(calls) == 2 and len(result.history) == 2
    assert all(item.candidate == calls[index] for index, item in enumerate(result.history))
    assert policy_candidate_hash(result.history[0].candidate_proposal) == policy_candidate_hash(
        result.history[1].candidate_proposal
    )
    receipt = result.telemetry["transfer_history"]
    assert receipt["status"] == "persisted"
    from polisyos.core.artifacts.manifest import ArtifactRef

    source_fp = RunFingerprint.model_validate(receipt["fingerprint"]).model_copy(
        update={"history_ref": ArtifactRef.model_validate(receipt["history_ref"])}
    )
    target_fp = source_fp.model_copy(update={"run_id": "target-run"})
    fresh = TransferLearningManager(FileSystemCAS(tmp_path / "cas"), object())
    restored = fresh.get_warm_start_evaluations(
        [source_fp], max_evals=2, target_fingerprint=target_fp
    )
    assert len(restored) == 2
    assert all("replica_id" in item.metadata for item in restored)
    assert {item.metadata["replica_id"] for item in restored} == {1, 2}
    assert len({item.candidate_id for item in restored}) == 1
    assert all(item.metadata["search_candidate_proposal"] for item in restored)


def test_typed_policy_missing_vector_cannot_become_best_in_run_or_warm_start() -> None:
    candidate = _candidate()
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        )
    )
    spec = coordinator.build_parameter_search_spec(candidate)

    def make_adapter() -> StrategyAdapter:
        return StrategyAdapter(
            RandomSearchStrategy(space=spec.search_space, seed=5),
            spec.search_space,
            codec=PolicyParameterCodec(spec.parameter_paths, spec.template_values),
            canonical_template=candidate,
        )

    context = {"candidate_template": candidate.as_search_payload()}
    proposal = make_adapter().generate_proposal([], None, context)
    source = {"gdp_change": 0.2, "metric_units": {"gdp_change": "fixture-unit"}}
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([GDPGrowthObjective(expected_unit="fixture-unit")]),
            initial_evaluations=[
                {
                    "candidate": proposal.payload,
                    "candidate_proposal": proposal.model_dump(mode="json"),
                    "objective_value": -0.2,
                    "is_promising": True,
                    "stage_b_result": {"simulation_results": source},
                }
            ],
        ),
        candidate_generator=make_adapter(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": source,
            "feedback": {"verdict": "APPROVE"},
        },
    )
    result = controller.run(context)
    assert result.best_candidate is None
    assert all(item.objective_value is None for item in result.history)
    assert all(not item.is_promising for item in result.history)
    assert all(item.score_status.value == "not_established" for item in result.history)
