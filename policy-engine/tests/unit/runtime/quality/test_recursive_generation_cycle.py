from __future__ import annotations

from pathlib import Path
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


def test_runtime_repo_root_invalid_present_refuses_and_omission_keeps_default_config(
    tmp_path,
) -> None:
    """Invalid supplied roots refuse and omission leaves the legacy owner default unset."""
    pytest.importorskip("fastapi")

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError

    with pytest.raises(RuntimeBootstrapError, match="repo_root is invalid"):
        create_runtime_api_app(
            cas_root=tmp_path / "invalid-root-cas",
            repo_root=tmp_path / "missing-source-checkout",
        )
    with pytest.raises(RuntimeBootstrapError, match="repo_root is invalid"):
        create_runtime_api_app(
            cas_root=tmp_path / "relative-root-cas",
            repo_root="relative-source-checkout",
        )

    app = create_runtime_api_app(cas_root=tmp_path / "default-root-cas")
    assert app.state.runtime_container.config.repo_root is None


@pytest.mark.asyncio
async def test_recursive_selected_candidate_source_profile_requires_context_owner_before_n4(
    tmp_path,
) -> None:
    """An explicit profile cannot reach N4 without the current-job context owner."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import GenerationCycleError
    from tests._helpers.candidate_cycle_source_profile import _problem
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    problem = _problem(runtime_hints=None)
    n4_calls: list[int] = []

    class _RecordingN4Port(N4GenerationPort):
        async def __call__(self, problem_arg: Any, *, cycle_index: int) -> Any:
            del problem_arg
            n4_calls.append(cycle_index)
            raise GenerationCycleError("unexpected_candidate_profile_n4_call")

    store = FileSystemCAS(tmp_path / "candidate-profile-owner-required-cas")
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=PromotionRuntime(store=store),
        repo_root=tmp_path,
    )
    graph = derive_recursive_design_graph(
        design_ref="design://candidate-profile-owner-required",
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="test://candidate-profile-owner-required",
    )

    with pytest.raises(
        GenerationCycleError,
        match="n4_candidate_source_profile_context_owner_missing",
    ):
        await controller.run(
            graph,
            problems_by_node={graph.root_design_ref: problem},
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            n4_generation_ports_by_node={
                graph.root_design_ref: _RecordingN4Port(
                    model_id="controlled-candidate-profile-owner-required",
                    repo_root=tmp_path,
                )
            },
            execution_intents_by_node={graph.root_design_ref: "simulate_only"},
        )

    assert n4_calls == []
    assert all(
        b"cycle_substrate_context_job_artifact.v5" not in artifact.read_bytes()
        for artifact in (tmp_path / "candidate-profile-owner-required-cas").rglob("*.blob")
    )


@pytest.mark.asyncio
async def test_recursive_malformed_present_candidate_source_profile_does_not_fall_back(
    tmp_path,
) -> None:
    """Malformed explicit profile intent fails before any N4 invocation."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import GenerationCycleError
    from tests._helpers.candidate_cycle_source_profile import _problem
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    base = _problem(runtime_hints=None)
    hints = dict(base.runtime_hints)
    hints["cycle_substrate_source_profile"] = {"schema_version": "wrong.v99"}
    problem = base.model_copy(update={"runtime_hints": hints})
    n4_calls: list[int] = []

    class _RecordingN4Port(N4GenerationPort):
        async def __call__(self, problem_arg: Any, *, cycle_index: int) -> Any:
            del problem_arg
            n4_calls.append(cycle_index)
            raise GenerationCycleError("unexpected_candidate_profile_n4_call")

    store = FileSystemCAS(tmp_path / "candidate-profile-malformed-cas")
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=PromotionRuntime(store=store),
        repo_root=tmp_path,
    )
    graph = derive_recursive_design_graph(
        design_ref="design://candidate-profile-malformed",
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="test://candidate-profile-malformed",
    )

    with pytest.raises(
        GenerationCycleError,
        match="n4_candidate_source_profile_selection_invalid",
    ):
        await controller.run(
            graph,
            problems_by_node={graph.root_design_ref: problem},
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            n4_generation_ports_by_node={
                graph.root_design_ref: _RecordingN4Port(
                    model_id="controlled-candidate-profile-malformed",
                    repo_root=tmp_path,
                )
            },
            execution_intents_by_node={graph.root_design_ref: "simulate_only"},
        )

    assert n4_calls == []
    assert all(
        b"cycle_substrate_context_job_artifact.v5" not in artifact.read_bytes()
        for artifact in (tmp_path / "candidate-profile-malformed-cas").rglob("*.blob")
    )


@pytest.mark.asyncio
async def test_recursive_absent_candidate_source_profile_preserves_legacy_n4_path(
    tmp_path,
) -> None:
    """No selected profile keeps the established context-free N4 behavior."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import GenerationCycleError
    from tests._helpers.candidate_cycle_source_profile import _problem
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    base = _problem(runtime_hints=None)
    hints = dict(base.runtime_hints)
    hints.pop("cycle_substrate_source_profile")
    problem = base.model_copy(update={"runtime_hints": hints})
    n4_calls: list[int] = []

    class _RecordingN4Port(N4GenerationPort):
        async def __call__(self, problem_arg: Any, *, cycle_index: int) -> Any:
            del problem_arg
            n4_calls.append(cycle_index)
            raise GenerationCycleError("controlled_legacy_n4_stop")

    store = FileSystemCAS(tmp_path / "candidate-profile-legacy-cas")
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=PromotionRuntime(store=store),
        repo_root=tmp_path,
    )
    graph = derive_recursive_design_graph(
        design_ref="design://candidate-profile-legacy",
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="test://candidate-profile-legacy",
    )

    with pytest.raises(GenerationCycleError, match="controlled_legacy_n4_stop"):
        await controller.run(
            graph,
            problems_by_node={graph.root_design_ref: problem},
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            n4_generation_ports_by_node={
                graph.root_design_ref: _RecordingN4Port(
                    model_id="controlled-candidate-profile-legacy",
                    repo_root=tmp_path,
                )
            },
            execution_intents_by_node={graph.root_design_ref: "simulate_only"},
        )

    assert n4_calls == [0]
    assert all(
        b"cycle_substrate_context_job_artifact.v5" not in artifact.read_bytes()
        for artifact in (tmp_path / "candidate-profile-legacy-cas").rglob("*.blob")
    )


@pytest.mark.asyncio
async def test_control_service_rejects_explicit_proposal_only_for_selected_profile(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit N4-only intent cannot be upgraded to the selected source route."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.http.services.control import generation_cycle as service
    from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleBudget
    from tests._helpers.candidate_cycle_source_profile import _problem
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    problem = _problem(runtime_hints=None)

    async def controlled_compiler(**kwargs: Any) -> Any:
        del kwargs
        return problem

    monkeypatch.setattr(service, "build_design_problem_from_nl_request", controlled_compiler)
    store = FileSystemCAS(tmp_path / "explicit-proposal-only-cas")

    class _UnusedVerifier:
        def require_admission(self, context: object, challenge: object) -> object:
            del context, challenge
            raise AssertionError("explicit intent must fail before EvalSafety admission")

    with pytest.raises(
        DesignProblemAuthorityError,
        match="candidate_cycle_source_profile_proposal_only_conflict",
    ):
        await service.compile_and_run_recursive_generation_cycle(
            raw_request=problem.nl_provenance.raw_request,
            context={},
            model_name="controlled-explicit-proposal-only",
            execution_intent="simulate_only",
            n4_proposal_only=True,
            n4_proposal_only_origin="explicit",
            compiler_gateway=None,
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            root_evaluation_context=None,
            eval_safety_verifier=_UnusedVerifier(),
            promotion_runtime=PromotionRuntime(store=store),
        )

    assert all(
        b"cycle_substrate_context_job_artifact.v5" not in artifact.read_bytes()
        for artifact in (tmp_path / "explicit-proposal-only-cas").rglob("*.blob")
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "mutate_owner_source_before_resolve",
    [(False,), (True,)],
    ids=("fresh-v5", "changed-owner-refuses"),
)
def test_recursive_selected_profile_persists_v5_before_n4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mutate_owner_source_before_resolve: bool,
) -> None:
    """The served recursive route hands N4 the freshly owner-resolved V5 context."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality import cycle_substrate as cycle_substrate_module
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CANDIDATE_CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION,
        CYCLE_SUBSTRATE_CONTEXT_JOB_V5_SCHEMA,
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextJobArtifactV5,
        VerifiedNLJobScope,
        cycle_job_profile_selection_ref,
        parse_cycle_substrate_context_job_artifact,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        N4GenerationPort,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )

    fixture = build_candidate_cycle_substrate_route_inputs(tmp_path)
    problem = fixture.problem
    inputs = fixture.seed_context
    profile_payload = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "candidate-source-profile-served-route",
        "purpose": "synthetic_candidate_scenario",
        "profile_selection_ref": cycle_job_profile_selection_ref(problem),
        "context_inputs": CandidateSimulationContextInputs(
            substrate_registry=fixture.substrate_registry,
            selected_registry_entry_hashes=fixture.selected_registry_entry_hashes,
            world_model_record=fixture.world_model_record,
            intervention_substrate=inputs.intervention_substrate,
            candidate_levers=inputs.candidate_levers,
            transport_context=inputs.transport_context,
            source_pack_content_hash=inputs.source_pack_content_hash,
            substrate_input_content_hash=inputs.substrate_input_content_hash,
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
            budget_ref=str(problem.runtime_hints["joint_simulation_budget_ref"]),
            horizon=HorizonSpec.model_validate(problem.runtime_hints["joint_simulation_horizon"]),
            baseline_state={
                "education.teaching_method": 0.0,
                "education.learning_outcomes": 0.0,
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

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    cas_root = tmp_path / ".polisyos"
    app = create_runtime_api_app(
        cas_root=cas_root,
        repo_root=fixture.root,
        candidate_simulation_profiles=(profile,),
        allow_fixture_identity=True,
    )
    runtime_api_context = app.state.runtime_container.runtime_api_context

    async def controlled_compiler(**kwargs: Any) -> Any:
        del kwargs
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        controlled_compiler,
    )
    persisted_v5: list[tuple[object, object]] = []
    resolved_v5: list[CycleSubstrateContextJobArtifactV5] = []
    original_persist = CycleSubstrateContextArtifactOwner.persist_for_current_job
    original_resolve = CycleSubstrateContextArtifactOwner.resolve_for_current_job

    def record_persist(owner: object, context: object, **kwargs: Any) -> object:
        ref = original_persist(owner, context, **kwargs)
        if (
            getattr(context, "schema_version", None)
            == CANDIDATE_CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION
        ):
            persisted_v5.append((context, ref))
        return ref

    def record_resolve(owner: object, ref: object, **kwargs: Any) -> object:
        if mutate_owner_source_before_resolve and persisted_v5 and ref == persisted_v5[-1][1]:
            import duckdb

            persisted_context = persisted_v5[-1][0]
            source_ref = persisted_context.source_profile.skg_snapshot_ref
            assert source_ref.startswith("duckdb://")
            source_path = Path(source_ref.removeprefix("duckdb://").rsplit("#v", 1)[0]).resolve(
                strict=True
            )
            assert source_path.is_relative_to(fixture.root.resolve(strict=True))
            assert source_path.is_file()
            with duckdb.connect(str(source_path)) as connection:
                before = connection.execute(
                    "SELECT COUNT(*) FROM ac_causal_claims WHERE id = ?",
                    ["candidate-source-profile-causal-claim"],
                ).fetchone()[0]
                assert before == 1
                connection.execute(
                    "DELETE FROM ac_causal_claims WHERE id = ?",
                    ["candidate-source-profile-causal-claim"],
                )
                after = connection.execute(
                    "SELECT COUNT(*) FROM ac_causal_claims WHERE id = ?",
                    ["candidate-source-profile-causal-claim"],
                ).fetchone()[0]
                assert after == 0
        resolved = original_resolve(owner, ref, **kwargs)
        if type(resolved) is CycleSubstrateContextJobArtifactV5:
            resolved_v5.append(resolved)
        return resolved

    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner, "persist_for_current_job", record_persist
    )
    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner, "resolve_for_current_job", record_resolve
    )

    n4_observations: list[tuple[object, int]] = []

    async def stop_after_n4_receives_context(
        port: N4GenerationPort,
        problem_arg: object,
        *,
        cycle_index: int,
    ) -> object:
        del problem_arg
        n4_observations.append((port._cycle_substrate_context, cycle_index))
        raise GenerationCycleError("controlled_stop_after_candidate_v5_context")

    monkeypatch.setattr(N4GenerationPort, "__call__", stop_after_n4_receives_context)

    claims = build_fixture_identity_claims()
    tenant_id = claims.tenant_id
    cell_id = claims.cell_id
    assert tenant_id and cell_id
    with TestClient(app) as client:
        accepted_response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": "test-r7-candidate-v5-recursive-bridge"},
            json={
                "request": problem.nl_provenance.raw_request,
                "llm_model": "controlled-r7-candidate-profile",
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                        mode="json"
                    )
                },
            },
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted = accepted_response.json()
        service = app.state._control_service
        route_observations: list[dict[str, Any]] = []
        persisted_v5_payload: bytes | None = None
        original_compile_route = service.compile_and_run_recursive_generation_cycle

        async def observe_compile_route(**kwargs: Any) -> Any:
            route_observations.append(
                {
                    "repo_root": service._repo_root,
                    "recursive_leaf_context_owner": kwargs["recursive_leaf_context_owner"],
                    "passed_verified_nl_job_scope": kwargs["verified_nl_job_scope"],
                    "verified_nl_job_scope": getattr(
                        kwargs["recursive_leaf_context_owner"],
                        "_verified_nl_job_scope",
                        None,
                    ),
                    "n4_proposal_only": kwargs["n4_proposal_only"],
                    "n4_proposal_only_origin": kwargs["n4_proposal_only_origin"],
                }
            )
            return await original_compile_route(**kwargs)

        monkeypatch.setattr(
            service,
            "compile_and_run_recursive_generation_cycle",
            observe_compile_route,
        )
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        job_after_dispatch = service._control_store.get_job(accepted["job_id"])
        if persisted_v5 and not mutate_owner_source_before_resolve:
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                persisted_v5_payload = runtime_api_context.store.get_bytes(persisted_v5[0][1])

    assert len(route_observations) == 1
    route = route_observations[0]
    verified_scope = route["verified_nl_job_scope"]
    leaf_owner = route["recursive_leaf_context_owner"]
    assert route["passed_verified_nl_job_scope"] is None
    assert route["n4_proposal_only"] is True
    assert route["n4_proposal_only_origin"] == "derived_legacy_default"
    assert type(verified_scope) is VerifiedNLJobScope
    assert verified_scope._was_issued_by_verified_nl_execution_owner
    assert verified_scope.job_id == accepted["job_id"]
    assert verified_scope.tenant_id == tenant_id
    assert verified_scope.cell_id == cell_id
    assert leaf_owner is not None
    assert leaf_owner._context_owner._store is runtime_api_context.store
    assert leaf_owner._verified_nl_job_scope is verified_scope
    assert route["repo_root"] == fixture.root
    assert job_after_dispatch is not None
    if mutate_owner_source_before_resolve:
        assert job_after_dispatch.state == "failed"
        assert "candidate_cycle_source_profile_owner_rederive_mismatch" in str(
            job_after_dispatch.error_message
        )
        assert len(persisted_v5) == 1
        assert resolved_v5 == []
        assert n4_observations == []
        return
    assert job_after_dispatch.state == "failed"
    assert str(job_after_dispatch.error_message).startswith(
        "controlled_stop_after_candidate_v5_context"
    )
    assert n4_observations, f"persisted={persisted_v5!r}, resolved={resolved_v5!r}"
    assert len(persisted_v5) == 1
    assert len(resolved_v5) == 1
    assert len(n4_observations) == 1
    resolved = resolved_v5[0]
    n4_context, cycle_index = n4_observations[0]
    assert cycle_index == 0
    assert type(resolved) is CycleSubstrateContextJobArtifactV5
    assert resolved.schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V5_SCHEMA
    assert resolved.job_id == verified_scope.job_id
    assert resolved.run_id == verified_scope.run_id
    assert resolved.tenant_id == verified_scope.tenant_id
    assert resolved.cell_id == verified_scope.cell_id
    assert resolved.design_problem_ref == cycle_substrate_module.cycle_job_design_problem_ref(
        problem
    )
    assert resolved.problem == problem
    assert resolved.context.source_profile is not None
    assert resolved.context.source_profile.authority_purpose == "cycle_input_candidate_only"
    assert resolved.context.source_profile.profile_status == "candidate_only"
    assert resolved.context.source_profile.source_basis_status == "not_established"
    source_ref = resolved.context.source_profile.skg_snapshot_ref
    source_path = Path(source_ref.removeprefix("duckdb://").rsplit("#v", 1)[0])
    assert source_path.resolve(strict=True).is_relative_to(fixture.root.resolve(strict=True))
    assert n4_context == resolved.context

    persisted_context, _context_ref = persisted_v5[0]
    assert persisted_context.content_hash == resolved.context.content_hash
    assert persisted_v5_payload is not None
    payload = from_canonical_bytes(persisted_v5_payload)
    readback = parse_cycle_substrate_context_job_artifact(payload)
    assert type(readback) is CycleSubstrateContextJobArtifactV5
    assert readback == resolved
