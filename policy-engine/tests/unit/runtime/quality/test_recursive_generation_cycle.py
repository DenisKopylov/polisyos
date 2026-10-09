from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleError,
    N4GenerationPort,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveCycleFailedNode,
    RecursiveCycleNode,
    RecursiveCyclePendingNode,
    RecursiveGenerationCyclePartialRunV2,
    RecursiveGenerationCyclePartialRunV3,
    build_default_recursive_generation_cycle_controller,
)


@pytest.mark.asyncio
async def test_real_leaf_result_survives_later_independent_sibling_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep an earlier persisted N5 result in a typed partial after sibling N6 fails."""
    from polisyos.runtime.quality import generation_cycle as generation_cycle_module
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _budget,
        _GenerationResult,
        _owner_n5_case_with_selected_ncm_ref,
        _problem,
        _Ranking,
        _runtime_ncm_fixture_store,
    )

    observed_catalog_profiles: list[object] = []
    original_generation_cycle_init = generation_cycle_module.GenerationCycleController.__init__

    def observe_generation_cycle_profile(
        controller: generation_cycle_module.GenerationCycleController,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        observed_catalog_profiles.append(kwargs.get("catalog_run_profile"))
        original_generation_cycle_init(controller, *args, **kwargs)

    monkeypatch.setattr(
        generation_cycle_module.GenerationCycleController,
        "__init__",
        observe_generation_cycle_profile,
    )

    store, _expected_ncm, ncm_ref = _runtime_ncm_fixture_store(tmp_path)
    try:
        hints = {
            "joint_simulation_horizon": {"start": 0, "end": 0, "step": 1},
            "joint_simulation_baseline_state": {"firm_survival": 0.0},
        }
        successful_problem, successful_context, successful_candidate = (
            _owner_n5_case_with_selected_ncm_ref(ncm_ref, runtime_hints=hints)
        )
        failing_problem, failing_context, failing_candidate = _owner_n5_case_with_selected_ncm_ref(
            ncm_ref, runtime_hints=hints
        )
        root_problem = _problem("recursive_sibling_failure_root")
        branch_problem = _problem("recursive_sibling_failure_branch")
        problem_by_node = {
            "design://root": root_problem,
            "design://first": successful_problem,
            "design://branch": branch_problem,
            "design://branch-first": successful_problem,
            "design://second": failing_problem,
            "design://third": successful_problem,
        }
        recursive_graph = derive_recursive_design_graph(
            design_ref="design://root",
            module_refs=(
                "design://first",
                "design://branch",
                "design://branch-first",
                "design://second",
                "design://third",
            ),
            parent_child_edges=(
                ("design://root", "design://first"),
                ("design://root", "design://branch"),
                ("design://branch", "design://branch-first"),
                ("design://branch", "design://second"),
                ("design://root", "design://third"),
            ),
            rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
        )

        class _ControlledN4Port(N4GenerationPort):
            def __init__(self, candidate: Any, *, fail: bool) -> None:
                super().__init__(model_id="controlled-v6-test", repo_root=REPO_ROOT)
                self._candidate = candidate
                self._fail = fail

            async def __call__(self, problem: Any, *, cycle_index: int) -> Any:
                del problem
                assert cycle_index == 0
                if self._fail:
                    raise GenerationCycleError(
                        "controlled_sibling_generation_failure",
                        "later child failed after its earlier sibling completed",
                    )
                return _GenerationResult(
                    status="generated",
                    candidates=(self._candidate,),
                    surrogate_rankings=(
                        _Ranking(
                            candidate_id=self._candidate.candidate_id,
                            score=0.9,
                            voi_estimate=4.0,
                        ),
                    ),
                )

        candidate_by_node = {
            "design://first": successful_candidate,
            "design://branch-first": successful_candidate,
            "design://second": failing_candidate,
            # Every declared leaf needs a typed producer even if it remains
            # pending because an earlier sibling failed.
            "design://third": successful_candidate,
        }
        context_by_node = {
            "design://first": successful_context,
            "design://branch-first": successful_context,
            "design://second": failing_context,
        }
        n4_ports = {
            node_ref: _ControlledN4Port(
                candidate,
                fail=node_ref == "design://second",
            )
            for node_ref, candidate in candidate_by_node.items()
        }

        controller = build_default_recursive_generation_cycle_controller(
            promotion_runtime=PromotionRuntime(store=store),
            repo_root=REPO_ROOT,
            catalog_run_profile="prod_full",
        )
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            partial = await controller.run(
                recursive_graph,
                problems_by_node=problem_by_node,
                budget_state=_budget(),
                recursive_budget=RecursiveCycleBudget(
                    max_depth=2,
                    max_nodes=6,
                    min_cycles_per_leaf=1,
                    max_cycles_per_leaf=1,
                ),
                cycle_substrate_contexts_by_node=context_by_node,
                execution_intents_by_node={
                    "design://first": "simulate_only",
                    "design://branch-first": "simulate_only",
                    "design://second": "simulate_only",
                    # The whole leaf denominator is declared even though the
                    # traversal stops before this later sibling is admitted.
                    "design://third": "candidate_only",
                },
                n4_generation_ports_by_node=n4_ports,
            )

            assert observed_catalog_profiles
            assert set(observed_catalog_profiles) == {"prod_full"}
            assert isinstance(partial, RecursiveGenerationCyclePartialRunV3)
            serialized = partial.model_dump(mode="json")
            replayed = RecursiveGenerationCyclePartialRunV3.model_validate(serialized)
            successful_node = next(
                node for node in replayed.nodes if node.node_ref == "design://first"
            )
            nested_successful_node = next(
                node for node in replayed.nodes if node.node_ref == "design://branch-first"
            )
            branch_node = next(
                node for node in replayed.nodes if node.node_ref == "design://branch"
            )
            root_node = next(node for node in replayed.nodes if node.node_ref == "design://root")
            failed_node = next(
                node for node in replayed.nodes if isinstance(node, RecursiveCycleFailedNode)
            )
            assert successful_node.cycle_run is not None
            assert isinstance(root_node, RecursiveCyclePendingNode)
            assert isinstance(branch_node, RecursiveCyclePendingNode)
            assert nested_successful_node.cycle_run is not None
            assert replayed.traversal_status == "failed"
            assert replayed.traversal_failure_reason == "independent_sibling_failure"
            assert replayed.terminal is None
            assert successful_node.cycle_run.promotion_port.certified_candidate_ids == ()
            assert successful_node.cycle_run.promotion_port.receipts == ()
            assert "design://third" in replayed.pending_node_refs
            assert failed_node.node_ref == "design://second"
            assert failed_node.parent_ref == "design://branch"
            assert failed_node.depth == 2
            assert failed_node.failure.origin_node_ref == "design://second"
            assert replayed.failed_node_ref == "design://second"
            assert failed_node.failure.error_code == "controlled_sibling_generation_failure"
            assert failed_node.failure.error_message == (
                "controlled_sibling_generation_failure: "
                "later child failed after its earlier sibling completed"
            )

            simulation = successful_node.cycle_run.cycles[0].simulation
            assert simulation.simulation_result_ref is not None
            persisted = load_joint_simulation_result(
                simulation.simulation_result_ref,
                store=store,
                expected_world_model_record_content_hash=(
                    successful_context.world_model_record.content_hash
                ),
                expected_atom_ids=tuple(
                    atom.intervention_id for atom in successful_candidate.intervention_atoms
                ),
                expected_selected_outcomes=("firm_survival",),
            )
            assert persisted.world_model_record_content_hash == (
                successful_context.world_model_record.content_hash
            )

            missing_artifact_id = "sha256:" + "0" * 64
            if missing_artifact_id == str(simulation.simulation_result_ref.artifact_id):
                missing_artifact_id = "sha256:" + "1" * 64
            corrupted_ref_payload = simulation.simulation_result_ref.model_dump(mode="python")
            corrupted_ref_payload["artifact_id"] = missing_artifact_id
            corrupted_ref = type(simulation.simulation_result_ref).model_validate(
                corrupted_ref_payload
            )
            with pytest.raises(GenerationCycleError) as unavailable:
                load_joint_simulation_result(
                    corrupted_ref,
                    store=store,
                    expected_world_model_record_content_hash=(
                        successful_context.world_model_record.content_hash
                    ),
                    expected_atom_ids=tuple(
                        atom.intervention_id for atom in successful_candidate.intervention_atoms
                    ),
                    expected_selected_outcomes=("firm_survival",),
                )
            assert unavailable.value.code == "joint_simulation_result_unavailable"

            # Preserve all V3 markers but remove the producer result. Recomputing
            # the content hash must still fail the completed-sibling predicate.
            pending_success = RecursiveCyclePendingNode(
                node_ref=successful_node.node_ref,
                parent_ref=successful_node.parent_ref,
                depth=successful_node.depth,
                child_refs=successful_node.child_refs,
                design_problem_ref=successful_node.design_problem_ref,
            )
            removed_producer_draft = replayed.model_dump(mode="json")
            removed_producer_draft["nodes"] = [
                (
                    pending_success.model_dump(mode="json")
                    if node["node_ref"] == successful_node.node_ref
                    else node
                )
                for node in removed_producer_draft["nodes"]
            ]
            removed_producer_draft.pop("content_hash")
            with pytest.raises(
                ValueError,
                match="recursive_partial_prior_sibling_not_completed",
            ):
                RecursiveGenerationCyclePartialRunV3.model_validate(
                    {
                        **removed_producer_draft,
                        "content_hash": gy_content_hash(removed_producer_draft),
                    }
                )

            budget_alias_draft = replayed.model_dump(mode="json")
            budget_alias_draft["traversal_status"] = "budget_stopped"
            budget_alias_draft.pop("content_hash")
            with pytest.raises(ValidationError, match="traversal_status"):
                RecursiveGenerationCyclePartialRunV3.model_validate(
                    {
                        **budget_alias_draft,
                        "content_hash": gy_content_hash(budget_alias_draft),
                    }
                )
            assert (
                RecursiveGenerationCyclePartialRunV2.model_fields["traversal_status"].default
                == "budget_stopped"
            )

            later_sibling_reuse = RecursiveCycleNode(
                node_ref="design://third",
                parent_ref="design://root",
                depth=1,
                child_refs=(),
                design_problem_ref=successful_node.design_problem_ref,
                cycle_run=successful_node.cycle_run,
                terminal=successful_node.terminal,
            )
            completed_later_draft = replayed.model_dump(mode="json")
            completed_later_draft["nodes"] = [
                (
                    later_sibling_reuse.model_dump(mode="json")
                    if node["node_ref"] == "design://third"
                    else node
                )
                for node in completed_later_draft["nodes"]
            ]
            completed_later_draft.pop("content_hash")
            with pytest.raises(
                ValidationError,
                match="recursive_partial_later_sibling_not_pending",
            ):
                RecursiveGenerationCyclePartialRunV3.model_validate(
                    {
                        **completed_later_draft,
                        "content_hash": gy_content_hash(completed_later_draft),
                    }
                )
    finally:
        store.close()


def test_recursive_leaf_context_owner_rejects_unissued_verified_scope(
    tmp_path,
) -> None:
    """A child owner accepts only a scope issued by the NL execution owner."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        CycleSubstrateContextArtifactOwner,
        VerifiedNLJobScope,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveLeafContextOwner,
    )

    store = FileSystemCAS(tmp_path / "recursive-leaf-scope-cas")
    context_owner = CycleSubstrateContextArtifactOwner(store=store)
    admission_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(),
        store=store,
    )
    unissued_scope = VerifiedNLJobScope.model_validate(
        {
            "admission_status": "established",
            "intent_band": "simulate_only_attempt",
            "canonical_mode": "simulate_only",
            "route_id": "POST /api/v1/control/runs/nl",
            "route_action": "control.launch_nl_run",
            "admission_surface": "served_route",
            "actor_subject": "fixture-actor",
            "actor_authenticated": True,
            "intent_digest": "sha256:" + "a" * 64,
            "job_id": "child-job",
            "run_id": "child-run",
            "tenant_id": "child-tenant",
            "cell_id": "child-cell",
            "worker_id": "fixture-worker",
            "attempt": 1,
        }
    )
    assert not unissued_scope._was_issued_by_verified_nl_execution_owner

    with pytest.raises(ValueError, match="recursive_leaf_verified_scope_not_issued"):
        RecursiveLeafContextOwner(
            store=store,
            context_owner=context_owner,
            admission_owner=admission_owner,
            verified_nl_job_scope=unissued_scope,
        )


def test_recursive_child_currentness_resolver_replays_exact_capsule_and_live_job(
    tmp_path,
    monkeypatch,
) -> None:
    """A child callback binds persisted child identity and the current leased job."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextHandoff,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveGenerationCycleError,
        RecursiveLeafContextCapsule,
        RecursiveLeafContextOwner,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import (
        _authenticated_tenant_scope,
        _cycle_context,
        _design_problem,
        _registry,
        _TestCurrentJobExecutionOwner,
        _world_record,
    )
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method", "learning_outcomes"),
    )
    context = _cycle_context(
        registry=registry,
        world_model_record=world,
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
    )
    profile_payload = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "bounded-child-currentness-profile",
        "purpose": "synthetic_candidate_scenario",
        "profile_selection_ref": cycle_job_profile_selection_ref(problem),
        "context_inputs": CandidateSimulationContextInputs(
            substrate_registry=context.substrate_registry,
            selected_registry_entry_hashes=context.selected_registry_entry_hashes,
            world_model_record=world,
            intervention_substrate=context.intervention_substrate,
            candidate_levers=(),
            transport_context=None,
            source_pack_content_hash=context.source_pack_content_hash,
            substrate_input_content_hash=context.substrate_input_content_hash,
        ).model_dump(mode="json"),
        "rule": CandidateScenarioSetToRule(
            operator_kind="teaching_method_set_to",
            parameter_id="intensity",
            target_world_slot="education.teaching_method",
            unit_id="synthetic_score",
            minimum=0,
            maximum=1,
        ).model_dump(mode="json"),
        "n5": CandidateScenarioN5Config(
            budget_ref="budget://bounded-child-currentness",
            horizon=HorizonSpec(start=0, end=0, step=1),
            baseline_state={
                "education.teaching_method": 0.0,
                "learning_outcomes": 0.0,
            },
            seed=7,
            replications=2,
        ).model_dump(mode="json"),
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **profile_payload,
            "content_hash": gy_content_hash(profile_payload),
        }
    )
    store = FileSystemCAS(tmp_path / "recursive-child-currentness-cas")
    job_owner = _TestCurrentJobExecutionOwner("child-job", "child-run")
    context_owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=job_owner,
    )
    admission_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(profile,),
        store=store,
    )
    owner = RecursiveLeafContextOwner(
        store=store,
        context_owner=context_owner,
        admission_owner=admission_owner,
    )
    scope = {"tenant_id": "child-tenant", "cell_id": "child-cell"}
    with _authenticated_tenant_scope(**scope):
        offer = admission_owner.admit_context(
            problem=problem,
            job_id="child-job",
            run_id="child-run",
            **scope,
        )
        assert offer is not None
        context_ref = context_owner.persist_for_current_job(
            offer.context,
            problem=problem,
        )
        handoff = CandidateSimulationContextHandoff(
            context=offer.context,
            context_job_ref=context_ref,
            profile=profile,
            profile_config_ref=offer.profile_config_ref,
            job_id="child-job",
            run_id="child-run",
            **scope,
        )
        capsule_payload = {
            "schema_version": "policyos.runtime.recursive_leaf_context.v1",
            "authority_purpose": "candidate_leaf_replay_only",
            "node_ref": "design://child",
            "parent_ref": "design://parent",
            "problem": problem.model_dump(mode="json"),
            "handoff": handoff.model_dump(mode="json"),
        }
        capsule = RecursiveLeafContextCapsule.model_validate(
            {
                **capsule_payload,
                "content_hash": gy_content_hash(capsule_payload),
            }
        )
        capsule_ref = owner.persist(capsule)

        check_order: list[str] = []
        original_require_current = owner.require_current
        original_read = owner.read

        def record_require_current(bound_capsule):
            check_order.append("current")
            return original_require_current(bound_capsule)

        def record_read(*args, **kwargs):
            check_order.append("read")
            return original_read(*args, **kwargs)

        monkeypatch.setattr(owner, "require_current", record_require_current)
        monkeypatch.setattr(owner, "read", record_read)

        currentness_resolver = owner.currentness_resolver(capsule_ref, capsule)
        assert currentness_resolver() is True
        assert check_order == ["current", "read"]

        check_order.clear()
        foreign_payload = capsule.model_dump(mode="json", exclude={"content_hash"})
        foreign_payload["node_ref"] = "design://foreign-child"
        foreign_capsule = RecursiveLeafContextCapsule.model_validate(
            {
                **foreign_payload,
                "content_hash": gy_content_hash(foreign_payload),
            }
        )
        foreign_currentness_resolver = owner.currentness_resolver(
            capsule_ref,
            foreign_capsule,
        )
        with pytest.raises(
            ValueError,
            match="recursive_leaf_capsule_reader_binding_mismatch",
        ):
            foreign_currentness_resolver()
        assert check_order == ["current", "read"]

        graph = derive_recursive_design_graph(
            design_ref="design://parent",
            module_refs=("design://child",),
            parent_child_edges=(("design://parent", "design://child"),),
            rule_version_ref="test://recursive-child-currentness",
        )
        controller = build_default_recursive_generation_cycle_controller(
            promotion_runtime=PromotionRuntime(store=store),
        )
        import asyncio

        with pytest.raises(
            RecursiveGenerationCycleError,
            match="recursive_candidate_simulation_currentness_denominator_mismatch",
        ):
            asyncio.run(
                controller.run(
                    graph,
                    problems_by_node={
                        "design://parent": problem,
                        "design://child": problem,
                    },
                    budget_state=_budget(),
                    recursive_budget=RecursiveCycleBudget(
                        max_depth=1,
                        max_nodes=2,
                        min_cycles_per_leaf=1,
                        max_cycles_per_leaf=1,
                    ),
                    cycle_substrate_contexts_by_node={
                        "design://child": handoff.context,
                    },
                    candidate_simulation_handoffs_by_node={
                        "design://child": handoff,
                    },
                    candidate_simulation_currentness_resolvers_by_node={
                        "design://child": lambda: True,
                    },
                    leaf_context_owner=owner,
                    execution_intents_by_node={"design://child": "simulate_only"},
                )
            )

        check_order.clear()
        job_owner.record.job_id = "foreign-current-job"
        with pytest.raises(
            ValueError,
            match="cycle_substrate_context_job_binding_mismatch",
        ):
            currentness_resolver()
        assert check_order == ["current"]
