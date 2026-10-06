"""Real configured registry consumer; fixture observations carry no source authority."""

from __future__ import annotations

import pytest

pytest.importorskip("torch", reason="UNRUN: optional native search backend")
pytest.importorskip("botorch", reason="UNRUN: optional native search backend")
pytest.importorskip("gpytorch", reason="UNRUN: optional native search backend")

from polisyos.core.security import get_current_tenant_id_or_none, tenant_scope
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry, ParetoView
from polisyos.scientist.methods.search.transfer_context import anonymize_tenant_id
from polisyos.scientist.nodes.builtins.planning import run_hierarchical_policy_search as module
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.output import load_policy_frontier_report
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.search import HierarchicalSearchConfig
from tests.unit.scientist.nodes.builtins.planning.test_run_hierarchical_policy_search import _bundle

pytestmark = pytest.mark.integration


def _candidate(*, parameterless: bool = False) -> PolicyCandidateSchema:
    bundle = _bundle()
    if parameterless:
        bundle = bundle.model_copy(
            update={
                "policy_spec": bundle.policy_spec.model_copy(update={"parameters": []}),
            }
        )
    return PolicyCandidateSchema.from_trinity_bundle(bundle, candidate_id="registry_policy")


def _config() -> HierarchicalSearchConfig:
    return HierarchicalSearchConfig(
        max_structure_candidates=1,
        max_parameter_iterations=3,
        enable_hybrid_seeds=False,
    )


def _evaluate(payload, context, *, empty=False):
    # The fixture uses a declared finite measurement, not a default scalar proxy.
    item = PolicyCandidateSchema.model_validate(
        {k: v for k, v in payload.items() if k != "candidate_hash"}
    )
    amount = float(item.trinity_bundle.policy_spec.interventions[0].params["amount"].amount)
    vector = PolicyEvaluationVector(
        candidate_id=item.candidate_id,
        primary={}
        if empty
        else {
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=amount,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        metadata={
            "candidate_hash": item.candidate_hash(),
            "fixture": "finite_parameter_measurement",
        },
    )
    return {
        "policy_evaluation": vector.model_dump(mode="json"),
        "feasible": True,
        "objective_value": vector.legacy_scalar_proxy,
        "simulation_results": {},
    }


@pytest.mark.parametrize("port", ["instantiate", "validate", "run"])
def test_configured_registry_reaches_every_coordinator_port(tmp_path, port):
    registry = ParetoRegistry(tmp_path / "registry")
    adapter = module.HierarchicalPolicySearchAdapter(pareto_registry=registry)
    item = _candidate()
    if port == "instantiate":
        coordinator = adapter.instantiate_coordinator(
            adapter.build_request(item, search_config=_config())
        )
        assert coordinator._pareto_registry is registry
    elif port == "validate":
        assert (
            adapter.validate_policy_design_api(item, search_config=_config())._pareto_registry
            is registry
        )
    else:
        result = adapter.run_search(
            item, loop_id="port_run", search_config=_config(), stage_b_evaluator=_evaluate
        )
        assert registry.get_snapshot("port_run").entries
        assert result.pareto_projection is not None


@pytest.mark.parametrize("invalid", [{}, "registry", object()])
def test_configured_registry_refuses_noncanonical_object(invalid):
    with pytest.raises(TypeError, match="ParetoRegistry"):
        module.HierarchicalPolicySearchAdapter(pareto_registry=invalid)


@pytest.mark.parametrize("parameterless,expected", [(False, 3), (True, 1)])
def test_actual_typed_rows_reach_disk_and_fresh_projection(
    tmp_path, execution_context, minimal_state, parameterless, expected
):
    root = tmp_path / "registry"
    registry = ParetoRegistry(root)
    result = module.HierarchicalPolicySearchAdapter(pareto_registry=registry).run_search(
        _candidate(parameterless=parameterless),
        loop_id="actual_rows",
        search_config=_config(),
        initial_context={"run_id": "source_run", "tenant_id": "tenant-a", "cell_id": "cell-a"},
        stage_b_evaluator=_evaluate,
    )
    histories = [r.history for r in result.state.parameter_search_results.values()]
    assert sum(map(len, histories)) == expected
    assert all(row.policy_evaluation is not None for history in histories for row in history)
    fresh = ParetoRegistry(root)
    snapshot = fresh.get_snapshot("actual_rows")
    assert (root / "loops" / "actual_rows" / "pareto_registry.json").is_file()
    assert len(snapshot.entries) == expected
    source_ids = {
        row.policy_evaluation.metadata["candidate_hash"] for history in histories for row in history
    }
    assert set(snapshot.entries) == source_ids
    assert all(entry.seed_payload for entry in snapshot.entries.values())
    projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert projection == result.pareto_projection
    assert projection.assessment.status == "basis_limited"
    assert projection.ranked_frontier_hashes == ()
    # Existing observed-coordinate quantity may be positive; it is not a rank/authority grant.
    assert snapshot.hypervolume_by_view["global_feasible"] > 0
    ref = module._persist_frontier_report(
        execution_context, state=minimal_state, loop_id="actual_rows", search_result=result
    )
    report = load_policy_frontier_report(execution_context.store, ref)
    assert set(report.source_feasible_candidate_hashes) == source_ids
    assert report.global_frontier == []
    assert report.candidate_frontier
    assert report.view_projections["global_feasible"].assessment.status == "basis_limited"


def test_parameterless_missing_axes_and_true_empty_history_are_unavailable(tmp_path):
    registry = ParetoRegistry(tmp_path / "registry")
    adapter = module.HierarchicalPolicySearchAdapter(pareto_registry=registry)
    empty = adapter.run_search(
        _candidate(parameterless=True), loop_id="empty", search_config=_config()
    )
    assert empty.state.parameter_search_results == {}
    assert empty.pareto_projection.assessment.input_count == 0
    assert registry.get_snapshot("empty").hypervolume_by_view.get("global_feasible") is None
    result = adapter.run_search(
        _candidate(parameterless=True),
        loop_id="missing",
        search_config=_config(),
        stage_b_evaluator=lambda payload, context: _evaluate(payload, context, empty=True),
    )
    snapshot = ParetoRegistry(registry._root).get_snapshot("missing")
    assert len(snapshot.entries) == 1
    assert snapshot.hypervolume_by_view["global_feasible"] is None
    assert snapshot.hypervolume_assessments["global_feasible"].status == "unavailable"
    assert result.pareto_projection.ranked_frontier_hashes == ()


def test_tenant_scope_covers_real_seed_reads_late_input_change_and_resets(tmp_path, monkeypatch):
    registry = ParetoRegistry(tmp_path / "registry")
    contexts = []
    original = registry.get_seed_bundle

    def observe(context, **kwargs):
        contexts.append(context)
        return original(context, **kwargs)

    monkeypatch.setattr(registry, "get_seed_bundle", observe)
    initial = {"run_id": "scoped", "tenant_id": "tenant-a", "cell_id": "cell-a"}
    calls = []

    def evaluator(payload, context):
        calls.append((get_current_tenant_id_or_none(), context["tenant_hash"], context["cell_id"]))
        initial["tenant_id"] = "tenant-b"
        return _evaluate(payload, context)

    with tenant_scope(None, tenant_id="ambient"):
        module.HierarchicalPolicySearchAdapter(pareto_registry=registry).run_search(
            _candidate(),
            loop_id="scope",
            search_config=_config(),
            initial_context=initial,
            stage_b_evaluator=evaluator,
        )
        assert get_current_tenant_id_or_none() == "ambient"
    assert len(contexts) >= 3  # Actual structure, parameter seed and warm-history reader.
    assert {ctx.tenant_hash for ctx in contexts} == {anonymize_tenant_id("tenant-a")}
    assert calls == [("tenant-a", anonymize_tenant_id("tenant-a"), "cell-a")] * 3
    foreign = original(
        contexts[-1].model_copy(update={"tenant_hash": anonymize_tenant_id("tenant-b")}),
        max_seeds=10,
    )
    assert foreign.entries == []
    local = original(contexts[-1], max_seeds=10)
    assert local.entries


def test_mismatched_tenant_context_refuses_before_observation(tmp_path):
    calls = []
    adapter = module.HierarchicalPolicySearchAdapter(
        pareto_registry=ParetoRegistry(tmp_path / "registry")
    )
    with pytest.raises(ValueError, match="tenant"):
        adapter.run_search(
            _candidate(),
            loop_id="mismatch",
            search_config=_config(),
            initial_context={
                "tenant_id": "tenant-a",
                "tenant_hash": anonymize_tenant_id("tenant-b"),
            },
            stage_b_evaluator=lambda payload, context: calls.append(payload),
        )
    assert calls == []


def test_tenant_scope_resets_when_actual_evaluator_refuses(tmp_path):
    def refuse(payload, context):
        assert get_current_tenant_id_or_none() == "tenant-a"
        raise RuntimeError("declared evaluator refusal")

    with tenant_scope(None, tenant_id="ambient"):
        with pytest.raises(RuntimeError, match="declared evaluator refusal"):
            module.HierarchicalPolicySearchAdapter(
                pareto_registry=ParetoRegistry(tmp_path / "registry")
            ).run_search(
                _candidate(),
                loop_id="refusal",
                search_config=_config(),
                initial_context={"tenant_id": "tenant-a"},
                stage_b_evaluator=refuse,
            )
        assert get_current_tenant_id_or_none() == "ambient"


def test_actual_node_forwards_owner_run_context_and_persists_report(
    execution_context, minimal_state, monkeypatch
):
    execution_context.run.tenant_id = "node-tenant"
    execution_context.run.cell_id = "node-cell"
    state = minimal_state.model_copy(deep=True)
    state.params["policy_candidate_schema"] = _candidate().model_dump(mode="json")
    state.params["hierarchical_policy_search_config"] = _config().model_dump(mode="json")
    calls = []

    def evaluator(ctx, state, *, candidate_payload, context):
        calls.append(
            (
                context["run_id"],
                context["tenant_id"],
                context["cell_id"],
                context["tenant_hash"],
                get_current_tenant_id_or_none(),
            )
        )
        return _evaluate(candidate_payload, context)

    monkeypatch.setattr(module, "_evaluate_candidate_payload", evaluator)
    outcome = module.RunHierarchicalPolicySearchNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert (
        calls
        == [
            (
                state.run_id,
                "node-tenant",
                "node-cell",
                anonymize_tenant_id("node-tenant"),
                "node-tenant",
            )
        ]
        * 3
    )
    report_ref = outcome.state.artifacts_index["policy_frontier_report_ref"]
    report = load_policy_frontier_report(execution_context.store, report_ref)
    assert len(report.source_feasible_candidate_hashes) == 3
    assert report.global_frontier == []  # Node default producer is still unappointed.


def test_real_source_denominator_cannot_be_replaced_by_partial_registry(
    tmp_path, execution_context, minimal_state
):
    registry = ParetoRegistry(tmp_path / "registry")
    result = module.HierarchicalPolicySearchAdapter(pareto_registry=registry).run_search(
        _candidate(), loop_id="denominator", search_config=_config(), stage_b_evaluator=_evaluate
    )
    full = registry.get_snapshot("denominator")
    assert len(full.entries) == 3
    omitted = next(iter(full.entries))
    full.entries.pop(omitted)
    partial = registry._recompute(full)
    registry._write_snapshot("denominator", partial)
    result.pareto_projection = (
        ParetoRegistry(registry._root)
        .get_snapshot("denominator")
        .project_view(ParetoView.GLOBAL_FEASIBLE)
    )
    ref = module._persist_frontier_report(
        execution_context, state=minimal_state, loop_id="denominator", search_result=result
    )
    report = load_policy_frontier_report(execution_context.store, ref)
    assert len(report.source_feasible_candidate_hashes) == 3
    assert report.view_projections["global_feasible"].assessment.status == "denominator_limited"
    assert report.global_frontier == []
    assert omitted in {entry.candidate_hash for entry in report.candidate_frontier}


def test_parameterless_malformed_present_vector_refuses_without_publication(tmp_path):
    registry = ParetoRegistry(tmp_path / "registry")
    with pytest.raises(ValueError):
        module.HierarchicalPolicySearchAdapter(pareto_registry=registry).run_search(
            _candidate(parameterless=True),
            loop_id="malformed",
            search_config=_config(),
            stage_b_evaluator=lambda payload, context: {
                "policy_evaluation": "broken",
                "objective_value": 0.0,
                "feasible": True,
            },
        )
    assert ParetoRegistry(registry._root).get_snapshot("malformed").entries == {}


def test_tenant_scope_resets_after_registry_publication_fault(tmp_path, monkeypatch):
    registry = ParetoRegistry(tmp_path / "registry")

    def fail_update(*args, **kwargs):
        assert get_current_tenant_id_or_none() == "tenant-a"
        raise OSError("registry publication refused")

    monkeypatch.setattr(registry, "update", fail_update)
    with tenant_scope(None, tenant_id="ambient"):
        with pytest.raises(OSError, match="registry publication refused"):
            module.HierarchicalPolicySearchAdapter(pareto_registry=registry).run_search(
                _candidate(parameterless=True),
                loop_id="publication-fault",
                search_config=_config(),
                initial_context={"tenant_id": "tenant-a"},
                stage_b_evaluator=_evaluate,
            )
        assert get_current_tenant_id_or_none() == "ambient"
