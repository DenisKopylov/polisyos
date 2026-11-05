"""Exercise generic root context reissue under an actual admitted NL worker.

The local SCM/source rows are candidate fixtures. These controls establish
selected-ref and worker fences, not empirical source truth or N5 success.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.mark.parametrize("unissued_dto", [False, True])
def test_generic_worker_lease_helper_refuses_missing_or_unissued_scope(
    tmp_path: Path, unissued_dto: bool
) -> None:
    """A helper requiring NL scope cannot fall back to ambient request identity."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextOwnerError,
        VerifiedNLJobScope,
    )

    owner = CycleSubstrateContextArtifactOwner(store=FileSystemCAS(tmp_path / "invalid-scope"))
    scope = VerifiedNLJobScope.model_construct() if unissued_dto else None
    with pytest.raises(
        CycleSubstrateContextOwnerError, match="cycle_substrate_context_job_verified_scope_mismatch"
    ):
        owner.require_current_job_scope(verified_nl_job_scope=scope)


@pytest.mark.parametrize("case", ["current_ref", "missing_skg", "withdrawn_skg"])
def test_generic_root_reissue_uses_current_ref_and_checks_recipe_before_n4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import artifact_ref_identity_key
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control import generation_cycle as service_generation
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextOwnerError,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
        JointSimulationPort,
        N4GenerationPort,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV1,
        GenericCycleSimulationProfileV1,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers.candidate_cycle_source_profile import (
        _problem as source_problem,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.controlled_candidate_profile import (
        _build_configured_procurement_profile,
        _problem,
    )
    from tests.unit.runtime.http.test_control_job_execution_intent import _valid_intake_for_mode
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "cache"))
    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-a"
    problem = _problem("generic_root_reissue")
    if case != "current_ref":
        hints = dict(problem.runtime_hints)
        hints["cycle_substrate_source_profile"] = source_problem(runtime_hints=None).runtime_hints[
            "cycle_substrate_source_profile"
        ]
        problem = problem.model_copy(update={"runtime_hints": hints})
    cas_root = tmp_path / "cas"
    api = build_runtime_api_context(cas_root=cas_root, core_runs_root=cas_root / "runs")
    base, _declaration, world_build = _build_configured_procurement_profile(
        recorded_problem=problem,
        artifact_store=api.store,
        tenant_id=tenant_id,
        cell_id=cell_id,
        tmp_path=tmp_path / "profile",
    )
    views = world_model_artifact_views(base.context_inputs.world_model_record)
    fields = {
        "profile_id": "generic-root-current-ref",
        "profile_selection_kind": "problem",
        "profile_selection_ref": cycle_job_profile_selection_ref(problem),
        "world_model_record_ref": world_build.record_ref,
        "substrate_registry_ref": views.substrate_registry_ref,
        "selected_ncm_ref": views.ncm_refs[0],
        "context_inputs": base.context_inputs,
        "n5": GenericCycleN5RequestProfileV1(
            budget_ref=base.n5.budget_ref,
            horizon=base.n5.horizon,
            baseline_state=base.n5.baseline_state,
            comparator_refs=base.n5.comparator_refs,
            seed=base.n5.seed,
            replications=base.n5.replications,
        ),
        "limitations": (
            "controlled_inputs_only",
            "currentness_not_established",
            "n5_simulation_not_world_evidence",
            "n9_not_admitted",
            "s8_blocked",
            "source_truth_not_established",
        ),
    }
    draft = GenericCycleSimulationProfileV1.model_construct(
        **fields, content_hash="sha256:" + "0" * 64
    )
    profile = GenericCycleSimulationProfileV1.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    app = create_runtime_api_app(
        cas_root=cas_root,
        repo_root=tmp_path,
        generic_cycle_simulation_profiles=(profile,),
        generic_cycle_simulation_root_profile_id=profile.profile_id,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=api),
        allow_fixture_identity=True,
    )

    async def compiled_problem(**_kwargs: Any) -> Any:
        return problem

    monkeypatch.setattr(
        service_generation, "build_design_problem_from_nl_request", compiled_problem
    )
    n4_calls: list[object] = []
    n5_calls: list[object] = []
    observed: list[str] = []

    async def stop_at_n4(_port: Any, actual_problem: Any, *, cycle_index: int) -> Any:
        n4_calls.append((actual_problem, cycle_index))
        raise GenerationCycleError("controlled_current_ref_n4_boundary")

    def forbid_n5(*args: Any, **kwargs: Any) -> Any:
        n5_calls.append((args, kwargs))
        raise AssertionError("current-ref removal control reached physical N5")

    monkeypatch.setattr(N4GenerationPort, "__call__", stop_at_n4)
    monkeypatch.setattr(JointSimulationPort, "__call__", forbid_n5)
    monkeypatch.setattr(JointSimulationHorizonController, "run", forbid_n5)
    with TestClient(app) as client:
        service = app.state._control_service
        original_compile = service.compile_and_run_recursive_generation_cycle

        async def run_owner_controls(**kwargs: Any) -> Any:
            if case != "current_ref":
                source_ref = base.context_inputs.world_model_record.skg_causal_prior_ref
                source_path = Path(
                    source_ref.skg_snapshot_ref.removeprefix("duckdb://").rsplit("#v", 1)[0]
                ).resolve(strict=True)
                assert source_path.is_relative_to(tmp_path)
                if case == "missing_skg":
                    source_path.rename(source_path.with_suffix(".withdrawn"))
                else:
                    import duckdb

                    with duckdb.connect(str(source_path)) as connection:
                        assert connection.execute(
                            "SELECT COUNT(*) FROM ac_skg_versions"
                        ).fetchone()[0]
                        connection.execute("DELETE FROM ac_skg_versions")
                return await original_compile(**kwargs)

            scope = kwargs["verified_nl_job_scope"]
            assert scope._was_issued_by_verified_nl_execution_owner
            handoff = kwargs["generic_cycle_simulation_handoff_resolver"](problem)
            leaf = kwargs["recursive_leaf_context_owner"]
            context_owner = leaf._context_owner
            lease = kwargs["generic_cycle_simulation_currentness_resolver"]
            assert lease() is True
            revoked: set[tuple[Any, ...]] = set()
            reads: list[tuple[Any, ...]] = []

            def admit_selected_ref(ref: Any, _context: Any) -> bool:
                identity = artifact_ref_identity_key(ref)
                reads.append(identity)
                return identity not in revoked

            context_owner._context_admission_verifier = admit_selected_ref
            gate = {"current": True}
            controller = GenerationCycleController(
                generation_port=N4GenerationPort(
                    model_id="controlled-current-ref",
                    cycle_substrate_context=handoff.context,
                ),
                repo_root=tmp_path,
                model_id="controlled-current-ref",
                cycle_substrate_context=handoff.context,
                candidate_cycle_context_artifact_owner=context_owner,
                candidate_cycle_verified_nl_job_scope=scope,
                generic_cycle_simulation_admission_owner=leaf._generic_admission_owner,
                generic_cycle_simulation_handoff=handoff,
                generic_cycle_simulation_currentness_resolver=(lambda: gate["current"] and lease()),
                promotion_runtime=service._promotion_runtime,
                artifact_store=api.store,
                eval_safety_verifier=kwargs["eval_safety_verifier"],
            )
            with pytest.raises(GenerationCycleError, match="controlled_current_ref_n4_boundary"):
                await controller.run(problem, budget_state=_budget(), max_cycles=1)
            assert len(n4_calls) == 1
            revised = problem.model_copy(
                update={
                    "runtime_hints": {
                        **problem.runtime_hints,
                        "generation_cycle_revision": {"revision_strategy": "alternative"},
                    }
                }
            )
            assert cycle_job_profile_selection_ref(revised) == cycle_job_profile_selection_ref(
                problem
            )
            controller._rebind_cycle_substrate_context_for_revision(problem, revised)
            rebound = controller._generic_cycle_simulation_handoff
            assert controller._cycle_substrate_context == rebound.context
            assert controller._generation_port._cycle_substrate_context == rebound.context
            assert controller._simulation_port._cycle_substrate_context == rebound.context
            old = artifact_ref_identity_key(handoff.context_job_ref)
            new = artifact_ref_identity_key(rebound.context_job_ref)
            assert old != new
            reads.clear()
            revoked.add(new)
            with pytest.raises(
                CycleSubstrateContextOwnerError,
                match="cycle_substrate_context_temporal_read_not_established",
            ):
                await controller.run(revised, budget_state=_budget(), max_cycles=1)
            assert reads == [new]
            assert len(n4_calls) == 1
            observed.append("current_ref_revoked_before_effect")
            revoked.clear()
            revoked.add(old)
            reads.clear()
            with pytest.raises(GenerationCycleError, match="controlled_current_ref_n4_boundary"):
                await controller.run(revised, budget_state=_budget(), max_cycles=1)
            assert new in reads and old not in reads
            assert len(n4_calls) == 2
            observed.append("old_ref_does_not_veto_current")
            gate["current"] = False
            reads.clear()
            with pytest.raises(
                GenerationCycleError, match="generation_cycle_generic_upstream_not_current"
            ):
                await controller.run(revised, budget_state=_budget(), max_cycles=1)
            assert not reads and len(n4_calls) == 2
            observed.append("upstream_false_before_effect")
            raise GenerationCycleError("controlled_current_ref_controls_complete")

        monkeypatch.setattr(
            service, "compile_and_run_recursive_generation_cycle", run_owner_controls
        )
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": "generic-root-reissue-" + case},
            json={
                "request": problem.nl_provenance.raw_request,
                "llm_model": "controlled-current-ref",
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                        mode="json"
                    )
                },
            },
        )
        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )
        job = service._control_store.get_job(job_id)
        assert job is not None and job.state == "failed"
        assert not n5_calls
        if case == "current_ref":
            assert observed == [
                "current_ref_revoked_before_effect",
                "old_ref_does_not_veto_current",
                "upstream_false_before_effect",
            ], job.error_message
            assert job.error_message == "controlled_current_ref_controls_complete"
        else:
            assert not n4_calls
            assert "n4_candidate_source_profile_owner_refused" in str(job.error_message)
            assert (
                "candidate_cycle_source_profile_skg_source_outside_root"
                if case == "missing_skg"
                else "candidate_cycle_source_profile_skg_version_unresolved"
            ) in str(job.error_message)
