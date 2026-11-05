"""Ordinary candidate N5 plus a separately selected real source-row method."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Control external proposal bytes while retaining real compiler and producers."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


async def _prepare_source_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> tuple[Any, Any]:
    """Declare compact external inputs before real N4; never mutate emitted atoms."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as compiler_owner
    from polisyos.runtime.quality.candidate_value_method import (
        persist_candidate_value_source_request,
    )
    from polisyos.runtime.quality.generic_simulation_admission import GenericCycleN5RequestProfileV3
    from polisyos.scientist.orchestration.engine.budget_ledger import BudgetInvocationQuotaPolicy
    from tests._helpers import candidate_cycle_source_profile
    from tests._helpers import generic_n4_served_replay as replay
    from tests._helpers.candidate_value_source_panel import build_candidate_value_source_panel
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    claims = build_fixture_identity_claims()
    assert claims.cell_id is not None
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    context = build_runtime_api_context(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
    )
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        panel = build_candidate_value_source_panel(tmp_path / "source", store=context.store)

    original_problem = replay._current_compiler_problem

    def declared_external_problem(recording: dict[str, Any], **kwargs: Any) -> Any:
        raw_request = (
            "For Ukraine, assess procurement_shock_intensity setting cells.distress_score "
            "from 0 to 1 and the alternatives tax_relief_rate and budget_allocation_multiplier. The candidate outcome is "
            "agents.income measured in usd; ask for ATE conditioning on "
            "baseline_covariate. all proposals remain candidate-only."
        )
        problem = original_problem(
            recording,
            raw_request=raw_request,
            outcome_variable="agents.income",
            problem_statement=raw_request,
            **kwargs,
        )
        payload = problem.model_dump(mode="python")
        payload["outcome_of_interest"].update(
            target_variable="agents.income",
            conditioning_variables=("baseline_covariate",),
            measurement_unit="usd",
            estimand="ATE of the declared candidate treatment on agents.income.",
        )
        return type(problem).model_validate(payload)

    # These adapters declare only external test inputs and select actual compact
    # source files. Grounding, atom production, CAS, N5 and method selection stay real.
    monkeypatch.setattr(replay, "_current_compiler_problem", declared_external_problem)
    original_base_profile = replay._configured_procurement_profile

    def binary_candidate_model(**kwargs: Any) -> Any:
        return original_base_profile(**{**kwargs, "rule_unit_id": "binary"})

    monkeypatch.setattr(replay, "_configured_procurement_profile", binary_candidate_model)

    def select_real_panel_source(root: Path) -> tuple[Any, Any]:
        assert root.resolve() == panel.source.repo_root.resolve()
        return panel.selection, panel.catalog_source

    monkeypatch.setattr(
        candidate_cycle_source_profile,
        "build_candidate_cycle_catalog_serving_source",
        select_real_panel_source,
    )
    prepared = await replay.prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=claims.tenant_id,
        cell_id=claims.cell_id,
        runtime_api_context=context,
        source_root=panel.source.repo_root,
        catalog_serving_source=panel.catalog_source,
        child_count=3,
        recording_mode="controlled_overlay",
        materialize_source_parameters=True,
        synthetic_settled_provider=True,
    )
    original_compiler = compiler_owner.build_design_problem_from_nl_request

    async def compile_with_external_span_judge(**kwargs: Any) -> Any:
        return await original_compiler(
            **{**kwargs, "span_support_client": _DeterministicSpanSupportClient()}
        )

    monkeypatch.setattr(
        compiler_owner, "build_design_problem_from_nl_request", compile_with_external_span_judge
    )
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        source_request_ref = persist_candidate_value_source_request(context.store, panel.request)
    # Keep the real minimum-three diversity gate. The external test inputs
    # declare only the procurement binary unit eligible in this numerical profile;
    # candidate-local evaluation must retain any rejected alternatives honestly.
    assert len(prepared.organ_run.result.candidates) == 3
    rules_list = []
    for rule in prepared.root_profile.n5.component_rules:
        if rule.target_world_slot == "cells.distress_score":
            rules_list.append(rule)
            continue
        candidates = tuple(
            candidate
            for candidate in prepared.organ_run.result.candidates
            if candidate.atom.target_world_slots == (rule.target_world_slot,)
        )
        assert len(candidates) == 1
        literal = Decimal(str(candidates[0].atom.direct_effect_bundle.params[rule.parameter_id]))
        width = rule.maximum - rule.minimum
        assert width > 0 and rule.minimum <= literal <= rule.maximum
        margin = width / Decimal("100")
        minimum, maximum = rule.minimum, rule.maximum
        if literal < maximum:
            minimum = min(maximum, literal + margin)
        else:
            maximum = max(minimum, literal - margin)
        assert not minimum <= literal <= maximum
        rules_list.append(
            type(rule).model_validate(
                {**rule.model_dump(mode="python"), "minimum": minimum, "maximum": maximum}
            )
        )
    rules = tuple(rules_list)
    assert any(rule.target_world_slot == "cells.distress_score" for rule in rules)
    n5 = GenericCycleN5RequestProfileV3.model_validate(
        {
            **prepared.root_profile.n5.model_dump(mode="python"),
            "component_rules": rules,
            "invocation_quota_policy": BudgetInvocationQuotaPolicy(
                allocation_id=f"candidate-source-method-{uuid.uuid4().hex}",
                total_units=5,
                protected_units=1,
            ),
            "invocation_purpose": "standard",
        }
    )
    configured = replay._hashed_model(
        type(prepared.root_profile),
        {
            **prepared.root_profile.model_dump(mode="python", exclude={"content_hash"}),
            "n5": n5,
            "candidate_value_source_request_ref": source_request_ref,
        },
        hash_fn=gy_content_hash,
    )
    prepared.app_kwargs["generic_cycle_simulation_profiles"] = (configured,)
    prepared.request_json.update(max_iterations=1, run_budget_usd=10.0)
    return prepared, panel


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ordinary_candidate_executes_source_rows_persists_and_fresh_gets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """A real source estimate differs from N5 and survives an independent fresh API reader."""
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactRef, load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.candidate_value_method import CandidateValueMethodRecord
    from tests._helpers.control_worker import dispatch_one_control_job

    prepared, panel = await _prepare_source_candidate(
        tmp_path, monkeypatch, controlled_candidate_gateway
    )
    physical_n5: list[Any] = []
    real_execute = gc.JointSimulationHorizonController.run

    def observe_real_execute(controller: Any, request: Any) -> Any:
        physical_n5.append(request)
        return real_execute(controller, request)

    monkeypatch.setattr(gc.JointSimulationHorizonController, "run", observe_real_execute)
    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json=prepared.request_json,
        )
        assert accepted.status_code == 200, accepted.text
        service = app.state._control_service
        job_id = accepted.json()["job_id"]
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )
        job = service._control_store.get_job(job_id)
        assert job is not None and job.state == "completed", getattr(job, "error_message", None)
        run_id = str(job.progress["core_run_id"])
        initial = client.get(f"/api/v1/runs/{run_id}")
        assert initial.status_code == 200, initial.text
        initial_run = initial.json()["run"]
    assert len(physical_n5) == 1
    observations = initial_run["generic_cycle_simulation"]["n5_observations"]
    assert len(observations) == 1
    observation = observations[0]
    assert observation["status"] == "joint_simulated"
    assert observation["n8_status"] == "value_conditional"
    method = observation["candidate_value_method"]
    assert method["status"] == "completed", method
    assert method["point_estimate"] == pytest.approx(panel.expected_ate, abs=1e-10)
    assert method["measurement_unit"] == "usd"
    assert method["production_value_eligible"] is False
    assert method["publication_authority"] is False
    assert method["assignment_provenance"] == "consumer_asserted"
    assert method["source_time_status"] == "not_established"
    assert "outcome_query_coordinates_proposed_unverified" in method["limitation_codes"]
    assert method["statistical_interval"][0] < method["point_estimate"]
    assert method["point_estimate"] < method["statistical_interval"][1]
    outer = method["value_outer_set"]
    assert len(outer["lower"]) == len(outer["upper"]) == 1
    assert (outer["lower"][0], outer["upper"][0]) == pytest.approx(panel.expected_bounds)
    # The source estimator's ATE is independently known from all four balanced
    # cells; the candidate NCM is a different declared model, never row evidence.
    effects = [
        point["effects"]["agents.income"]
        for trajectory in observation["simulation_result_body"]["trajectories"]
        for point in trajectory["points"]
    ]
    assert effects and all(abs(effect - panel.expected_ate) > 0.1 for effect in effects)
    fresh_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
    assert fresh_context.store is not prepared.runtime_api_context.store
    fresh_app = create_runtime_api_app(
        **{
            **prepared.app_kwargs,
            "container_overrides": RuntimeContainerOverrides(runtime_api_context=fresh_context),
            "generic_cycle_simulation_profiles": (),
            "generic_cycle_simulation_root_profile_id": None,
        }
    )
    with TestClient(fresh_app) as fresh_client:
        fresh = fresh_client.get(f"/api/v1/runs/{run_id}")
        assert fresh.status_code == 200, fresh.text
        fresh_observation = fresh.json()["run"]["generic_cycle_simulation"]["n5_observations"][0]
        assert fresh_observation["candidate_value_method"] == method
        assert len(physical_n5) == 1
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            record = CandidateValueMethodRecord.model_validate(
                load_core_json_artifact(
                    fresh_context.store, ArtifactRef.model_validate(method["record_ref"])
                )
            )
        real_get_bytes = fresh_context.store.get_bytes

        def remove_exact_execution(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if str(getattr(ref, "artifact_id", ref)) == str(record.n5_execution_ref.artifact_id):
                raise FileNotFoundError("removed selected N5 execution receipt")
            return real_get_bytes(ref, *args, **kwargs)

        with monkeypatch.context() as removal:
            removal.setattr(fresh_context.store, "get_bytes", remove_exact_execution)
            removed = fresh_client.get(f"/api/v1/runs/{run_id}")
            assert removed.status_code == 200, removed.text
            degraded = removed.json()["run"]["generic_cycle_simulation"]["n5_observations"][0]
            assert degraded["n8_status"] == "value_conditional"
            assert degraded["candidate_value_method"]["status"] == "not_established"
            assert degraded["candidate_value_method"]["point_estimate"] is None
        restored = fresh_client.get(f"/api/v1/runs/{run_id}")
        assert restored.status_code == 200, restored.text
        assert (
            restored.json()["run"]["generic_cycle_simulation"]["n5_observations"][0][
                "candidate_value_method"
            ]
            == method
        )
        assert len(physical_n5) == 1
