"""Served candidate N5, candidate-local N8 refusal, and source-row method."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from polisyos.core.contracts import ModelInputScope


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
    *,
    one_arm_control: bool = False,
    total_n5_units: int = 5,
    measurement_scope: ModelInputScope | None = None,
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
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
    from polisyos.runtime.quality.generic_simulation_admission import GenericCycleN5RequestProfileV3
    from polisyos.scientist.orchestration.engine.budget_ledger import BudgetInvocationQuotaPolicy
    from tests._helpers import candidate_cycle_source_profile
    from tests._helpers import generic_n4_served_replay as replay
    from tests._helpers.candidate_value_source_panel import build_candidate_value_source_panel
    from tests._helpers.runtime_http import _valid_intake_for_mode
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    claims = build_fixture_identity_claims()
    assert claims.cell_id is not None
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    original_problem = replay._current_compiler_problem

    def declared_external_problem(recording: dict[str, Any], **kwargs: Any) -> Any:
        raw_request = (
            "For Ukraine, improve the declared outcome measured in usd. Maximize the "
            "average effect for the specified population over the stated period, "
            "conditioning on baseline_covariate. Ensure all proposals remain candidate-only."
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
            estimand="ATE",
            metric_id="income_ate",
        )
        payload["objectives"] = [
            {
                "objective_id": "candidate_income_ate",
                "description": "Maximize the candidate average income effect in usd.",
                "metric_id": "income_ate",
                "direction": "maximize",
            }
        ]
        return type(problem).model_validate(payload)

    recording = next(
        row
        for row in replay.n4_contract._load_recordings(replay.REPO_ROOT)
        if row.get("design_problem_id") == replay._RECORDING_ID
    )
    external_candidate = declared_external_problem(recording)
    external_arguments = external_candidate.model_dump(mode="json")
    raw_request = external_candidate.nl_provenance.raw_request

    def external_compiler_reply(request_body: Mapping[str, object]) -> Mapping[str, object]:
        # This is the external provider boundary, never a replacement for the
        # product compiler/parser. Its output remains a proposed candidate.
        assert raw_request in json.dumps(request_body, ensure_ascii=False)
        return deepcopy(external_arguments)

    controlled_candidate_gateway.set_fixture(
        recording, problem=external_candidate, compiler_reply_factory=external_compiler_reply
    )
    request_context = {
        "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(mode="json")
    }
    compiled_problem = await compiler_owner.build_design_problem_from_nl_request(
        nl_request=raw_request,
        context=request_context,
        trusted_source_context={},
        model_name=str(recording["model_id"]),
        span_support_client=_DeterministicSpanSupportClient(),
    )
    compiler_bodies = controlled_candidate_gateway.compiler_request_bodies()
    assert compiler_bodies and all(isinstance(body, bytes) for body in compiler_bodies)
    assert all(isinstance(json.loads(body), dict) for body in compiler_bodies)
    assert compiled_problem.outcome_of_interest == external_candidate.outcome_of_interest
    assert compiled_problem.outcome_of_interest.query_coordinate_status == (
        "candidate_proposed_unverified"
    )

    context = build_runtime_api_context(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
    )
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        panel = build_candidate_value_source_panel(
            tmp_path / "source",
            store=context.store,
            one_arm_control=one_arm_control,
            measurement_scope=measurement_scope,
        )

    def actual_compiler_problem(_recording: dict[str, Any], **kwargs: Any) -> Any:
        assert not kwargs
        return compiled_problem

    # Profiles and N4 receive the actual compiler product. Only external
    # replies and compact source selection are configured by these adapters.
    monkeypatch.setattr(replay, "_current_compiler_problem", actual_compiler_problem)
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
    from polisyos.runtime.quality import generation_cycle as gc

    # Reconcile the full real N4 subject against the method's actual owner
    # contract before POST/N5, rather than discovering another coordinate
    # mismatch only after physical execution. This grants no method authority.
    source_candidates = tuple(
        candidate
        for candidate in prepared.organ_run.result.candidates
        if candidate.atom.target_world_slots == ("cells.distress_score",)
    )
    assert len(source_candidates) == 1
    assert (
        gc._value_owner_source_atom_estimand_binding(
            candidate=source_candidates[0],
            problem=prepared.recorded_problem,
            estimand=gc._typed_value_estimand_spec(panel.request.estimand_spec_json),
            measurement_unit=panel.request.outcome_bounds_unit,
        )
        == source_candidates[0].atom.content_hash
    )
    controlled_candidate_gateway.configure_compiler_reply(external_compiler_reply)
    original_compiler = compiler_owner.build_design_problem_from_nl_request

    async def compile_with_external_span_judge(**kwargs: Any) -> Any:
        actual = await original_compiler(
            **{**kwargs, "span_support_client": _DeterministicSpanSupportClient()}
        )
        assert actual.outcome_of_interest == compiled_problem.outcome_of_interest
        assert actual.objectives == compiled_problem.objectives
        assert cycle_job_profile_selection_ref(actual) == cycle_job_profile_selection_ref(
            compiled_problem
        )
        post_bodies = controlled_candidate_gateway.compiler_request_bodies()
        assert post_bodies and all(isinstance(body, bytes) for body in post_bodies)
        assert all(isinstance(json.loads(body), dict) for body in post_bodies)
        return actual

    monkeypatch.setattr(
        compiler_owner, "build_design_problem_from_nl_request", compile_with_external_span_judge
    )
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        source_request_ref = persist_candidate_value_source_request(context.store, panel.request)
    # Keep the real minimum-three diversity gate and source profile unchanged.
    # Every emitted candidate stays inside its existing typed N5 rule.
    assert len(prepared.organ_run.result.candidates) == 3
    _assert_neutral_source_rank(prepared.organ_run)
    rules = tuple(prepared.root_profile.n5.component_rules)
    rules_by_slot = {rule.target_world_slot: rule for rule in rules}
    assert len(rules_by_slot) == len(rules) == 3
    assert set(rules_by_slot) == {
        candidate.atom.target_world_slots[0] for candidate in prepared.organ_run.result.candidates
    }
    world_record = prepared.root_profile.context_inputs.world_model_record
    assert rules_by_slot["cells.distress_score"].unit_id == "binary"
    for candidate in prepared.organ_run.result.candidates:
        (target_slot,) = candidate.atom.target_world_slots
        rule = rules_by_slot[target_slot]
        slot = world_record.slot_binding(target_slot)
        assert slot is not None and slot.unit == rule.unit_id
        literal = Decimal(str(candidate.atom.direct_effect_bundle.params[rule.parameter_id]))
        assert rule.minimum <= literal <= rule.maximum
    n5 = GenericCycleN5RequestProfileV3.model_validate(
        {
            **prepared.root_profile.n5.model_dump(mode="python"),
            "component_rules": rules,
            "replications": 1,
            "invocation_quota_policy": BudgetInvocationQuotaPolicy(
                allocation_id=f"candidate-source-method-{uuid.uuid4().hex}",
                total_units=total_n5_units,
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
            "candidate_value_method_discovery": "controlled_builtins",
        },
        hash_fn=gy_content_hash,
    )
    prepared.app_kwargs["generic_cycle_simulation_profiles"] = (configured,)
    prepared.request_json.update(max_iterations=1, run_budget_usd=10.0)
    return prepared, panel


def _assert_neutral_source_rank(organ_run: Any) -> dict[str, str]:
    """Bind neutral source text to the actual non-promoting N4 ranking order."""
    candidates = tuple(organ_run.result.candidates)
    target_order = tuple(candidate.atom.target_world_slots for candidate in candidates)
    assert target_order == (
        ("global.tax_rate",),
        ("cells.distress_score",),
        ("government.balance",),
    )
    rankings = {row.candidate_id: row for row in organ_run.result.surrogate_rankings}
    assert len(rankings) == len(candidates) == 3
    ordered_rankings = tuple(rankings[candidate.candidate_id] for candidate in candidates)
    assert len({row.score for row in ordered_rankings}) == 1
    assert tuple(row.voi_estimate for row in ordered_rankings) == tuple(
        sorted(row.voi_estimate for row in ordered_rankings)
    )
    assert (
        ordered_rankings[0].voi_estimate
        < ordered_rankings[1].voi_estimate
        < (ordered_rankings[2].voi_estimate)
    )
    assert all(row.promotion_allowed is False for row in ordered_rankings)
    return {
        candidate.atom.target_world_slots[0]: candidate.candidate_id for candidate in candidates
    }


def _install_served_execution_observers(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, list[Any]]:
    """Record real N4 and physical N5 calls plus the same run's quota owner."""
    from polisyos.runtime.http.services.control import run_lifecycle
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.design_generation import DesignGenerationOrganRun
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort

    observed: dict[str, list[Any]] = {
        "n4_port_calls": [],
        "actual_n4_organs": [],
        "physical_n5": [],
        "budget_owners": [],
    }
    original_n4_call = N4GenerationPort.__call__

    async def observe_n4_call(
        port: N4GenerationPort,
        problem: Any,
        *,
        cycle_index: int,
        **kwargs: Any,
    ) -> Any:
        used_prefetched_organ = port._prefetched_organ_run is not None
        result = await original_n4_call(port, problem, cycle_index=cycle_index, **kwargs)
        observed["n4_port_calls"].append(
            {"used_prefetched_organ": used_prefetched_organ, "result": result}
        )
        if not used_prefetched_organ and type(result) is DesignGenerationOrganRun:
            observed["actual_n4_organs"].append(result)
        return result

    monkeypatch.setattr(N4GenerationPort, "__call__", observe_n4_call)
    original_n5_run = gc.JointSimulationHorizonController.run

    def observe_n5_run(controller: Any, request: Any) -> Any:
        observed["physical_n5"].append(request)
        return original_n5_run(controller, request)

    monkeypatch.setattr(gc.JointSimulationHorizonController, "run", observe_n5_run)
    original_budget_builder = run_lifecycle._build_control_nl_producer_budget_reconciler

    def observe_budget_owner(**kwargs: Any) -> Any:
        observer = original_budget_builder(**kwargs)
        observed["budget_owners"].append(observer)
        return observer

    monkeypatch.setattr(
        run_lifecycle,
        "_build_control_nl_producer_budget_reconciler",
        observe_budget_owner,
    )
    return observed


def _assert_candidate_local_quota(
    observed: dict[str, list[Any]],
    *,
    completed_standard_units: int,
    standard_limit_units: int = 4,
) -> Any:
    """Reconcile completed standard N5 work while preserving the protected unit."""
    assert len(observed["budget_owners"]) == 1
    capacity = observed["budget_owners"][0].observe_standard_invocation_capacity()
    remaining = standard_limit_units - completed_standard_units
    assert capacity.status == ("available" if remaining else "exhausted")
    assert capacity.predicate_basis == "independently_reconciled"
    assert capacity.standard_limit_units == standard_limit_units
    assert capacity.standard_remaining_units == remaining
    assert capacity.protected_limit_units == 1
    assert capacity.protected_remaining_units == 1
    assert len(capacity.terminal_witnesses) == completed_standard_units
    return capacity


def _assert_source_method_n4_lineage(
    *,
    prepared: Any,
    job: Any,
    generic: dict[str, Any],
    attempt: dict[str, Any],
    selected: dict[str, Any],
) -> None:
    """Resolve the outer N4 root and both exact per-cycle N5 custody joins."""
    from polisyos.core.artifacts import ArtifactRef, load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceHandoff
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5ExecutionV3,
    )

    store = prepared.runtime_api_context.store
    compiled_ref = ArtifactRef.model_validate(
        job.progress["compiled_recursive_generation_cycle_artifact_ref"]
    )
    outer_ref = ArtifactRef.model_validate(generic["n4_source_ref"])
    cycle_ref = ArtifactRef.model_validate(attempt["n4_source_ref"])
    assert cycle_ref == ArtifactRef.model_validate(selected["n4_source_ref"])
    assert outer_ref != cycle_ref
    assert attempt["n5_execution_ref"] != selected["n5_execution_ref"]
    assert attempt["simulation_result_ref"] != selected["simulation_result_ref"]

    with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            load_core_json_artifact(store, compiled_ref)
        )
        outer_handoff = GenerationSourceHandoff.model_validate(
            load_core_json_artifact(store, outer_ref)
        )
        cycle_handoff = GenerationSourceHandoff.model_validate(
            load_core_json_artifact(store, cycle_ref)
        )
        assert outer_ref == compiled.n4_recursive_source_ref
        assert outer_handoff.run_id == compiled.n4_recursive_source_run_id == job.run_id
        (node,) = compiled.recursive_run.nodes
        assert node.cycle_run is not None
        assert cycle_handoff.run_id == node.cycle_run.run_id != outer_handoff.run_id
        assert cycle_handoff.content_hash != outer_handoff.content_hash
        owner_fields = {"run_id", "content_hash"}
        assert cycle_handoff.model_dump(exclude=owner_fields) == outer_handoff.model_dump(
            exclude=owner_fields
        )

        (retained_attempt,) = (
            summary.evaluation_attempt
            for summary in node.cycle_run.candidate_summaries
            if summary.evaluation_attempt is not None
        )
        (cycle,) = node.cycle_run.cycles
        candidates = {
            candidate.candidate_id: candidate.atom.content_hash
            for candidate in cycle_handoff.generation_result.candidates
        }
        for row, simulation in (
            (attempt, retained_attempt.simulation),
            (selected, cycle.simulation),
        ):
            execution_ref = ArtifactRef.model_validate(row["n5_execution_ref"])
            execution = GenericCycleSimulationN5ExecutionV3.model_validate(
                load_core_json_artifact(store, execution_ref)
            )
            assert (execution.tenant_id, execution.cell_id) == (
                prepared.tenant_id,
                prepared.cell_id,
            )
            assert (execution.job_id, execution.run_id) == (job.job_id, outer_handoff.run_id)
            assert execution.source_run_id == cycle_handoff.run_id
            assert execution.status == simulation.status == "joint_simulated"
            assert execution.candidate_id == simulation.candidate_id == row["candidate_id"]
            assert execution.candidate_atom_hash == candidates[execution.candidate_id]
            assert execution_ref == simulation.generic_n5_execution_ref
            assert execution.n4_source_ref == simulation.generic_n4_source_ref == cycle_ref
            assert (
                execution.input_ref
                == simulation.generic_n5_input_ref
                == ArtifactRef.model_validate(row["n5_input_ref"])
            )
            assert (
                execution.result_ref
                == simulation.simulation_result_ref
                == ArtifactRef.model_validate(row["simulation_result_ref"])
            )


def _assert_source_method_numerics(
    observation: dict[str, Any],
    *,
    expected_ate: float,
    expected_bounds: tuple[float, float],
) -> dict[str, Any]:
    """Compare statistical output with independent truth and a distinct N5 signal."""
    assert observation["status"] == "joint_simulated"
    assert observation["n8_status"] == "value_conditional"
    method = observation["candidate_value_method"]
    assert method["status"] == "completed", method
    assert method["measurement_unit"] == "usd"
    assert method["production_value_eligible"] is False
    assert method["publication_authority"] is False
    assert method["assignment_provenance"] == "consumer_asserted"
    assert method["source_time_status"] == "not_established"
    assert "outcome_query_coordinates_proposed_unverified" in method["limitation_codes"]
    lower, upper = method["statistical_interval"]
    assert lower < method["point_estimate"] < upper
    assert lower <= expected_ate <= upper
    outer = method["value_outer_set"]
    assert len(outer["lower"]) == len(outer["upper"]) == 1
    assert (outer["lower"][0], outer["upper"][0]) == pytest.approx(expected_bounds)
    effects = [
        point["effects"]["agents.income"]
        for trajectory in observation["simulation_result_body"]["trajectories"]
        for point in trajectory["points"]
    ]
    # The declared NCM sets a binary treatment from zero to one with slope
    # 0.5. Bind that independent result before using it as the contrast oracle.
    expected_n5_effect = float(Decimal("1") * Decimal("0.5"))
    assert effects
    assert effects == pytest.approx([expected_n5_effect] * len(effects), rel=0.0, abs=1e-12)
    # Truth comes from the complete balanced source panel. The fitted estimator
    # need not equal that truth bit-for-bit; its reported interval must contain
    # it and distinguish the independently declared N5 model's effect.
    assert effects and all(effect < lower or effect > upper for effect in effects)
    return method


def _assert_and_emit_source_method_profile(
    observed_profile: dict[str, Any],
    emit: Callable[[str, object], None],
) -> None:
    """Verify and expose the actual requested/effective contract distinction."""
    assert observed_profile["requested_parameters"] == {
        "confidence_level": 0.95,
        "direct_model_type": "linear",
        "estimation_backend": "custom",
    }
    assert observed_profile["effective_parameters"]["nuisance_model_family"] == "competitive"
    assert observed_profile["binding_limitation"] == (
        "legacy_backend_hints_are_not_execution_controls"
    )
    emit("candidate_value_method_profile", json.dumps(observed_profile, sort_keys=True))


def _assert_source_method_reader_suffix(
    *,
    prepared: Any,
    method: dict[str, Any],
    physical_n5: list[Any],
    projector_calls: list[dict[str, Any]],
    actual_projector: Any,
    expected_attempt: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    run_id: str,
) -> dict[str, Any]:
    """Check HTTP replay/removal and direct projector guards without another N5."""
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactRef, load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.quality import candidate_value_method as method_owner
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.candidate_value_method import CandidateValueMethodRecord
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
    )

    n5_calls_before = len(physical_n5)
    observed_profile: dict[str, Any] = {}
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
        fresh_generic = fresh.json()["run"]["generic_cycle_simulation"]
        assert fresh_generic["candidate_evaluation_attempts"] == [expected_attempt]
        fresh_observation = fresh_generic["n5_observations"][0]
        assert fresh_observation["candidate_value_method"] == method
        assert len(physical_n5) == n5_calls_before
        with monkeypatch.context() as cap:
            cap.setattr(
                gc,
                "_load_value_data_profile_from_l1_dcat",
                partial(gc._load_value_data_profile_from_l1_dcat, owner_row_limit=119),
            )
            truncated = fresh_client.get(f"/api/v1/runs/{run_id}")
        assert truncated.status_code == 200, truncated.text
        (fallback,) = truncated.json()["run"]["generic_cycle_simulation"]["n5_observations"]
        assert fallback["candidate_id"] == fresh_observation["candidate_id"]
        assert fallback["n8_status"] == "value_conditional"
        assert fallback["n8_value_ref"] == fresh_observation["n8_value_ref"]
        assert fallback["simulation_result_ref"] == fresh_observation["simulation_result_ref"]
        assert fallback["simulation_result_body"] == fresh_observation["simulation_result_body"]
        limited_method = fallback["candidate_value_method"]
        assert limited_method["record_ref"] == method["record_ref"]
        assert limited_method["status"] == "not_established"
        assert limited_method["limitation_codes"] == ["acquire_data:value_owner_rows_truncated"]
        assert "measurement_scope" not in limited_method
        assert limited_method["point_estimate"] is None
        assert limited_method["statistical_interval"] is None
        assert limited_method["publication_authority"] is False
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            record = CandidateValueMethodRecord.model_validate(
                load_core_json_artifact(
                    fresh_context.store, ArtifactRef.model_validate(method["record_ref"])
                )
            )
            refused = CandidateValueMethodRecord.model_validate(
                load_core_json_artifact(
                    fresh_context.store,
                    ArtifactRef.model_validate(expected_attempt["candidate_value_method_ref"]),
                )
            )
            selected_profile = GenericCycleSimulationProfileV1.model_validate(
                load_core_json_artifact(fresh_context.store, record.profile_ref)
            )
        scope_limitation = method_owner._CONTROLLED_BUILTINS_LIMITATION
        assert selected_profile.candidate_value_method_discovery == "controlled_builtins"
        assert selected_profile.candidate_value_source_request_ref == record.source_request_ref
        assert record.discovery_limitations == refused.discovery_limitations == (scope_limitation,)
        assert method["discovery_limitations"] == [scope_limitation]
        assert refused.profile_ref == record.profile_ref
        assert refused.source_request_ref == record.source_request_ref
        assert refused.candidate_id == expected_attempt["candidate_id"]
        assert refused.status == "refused"
        assert refused.failure_kind == "input_refused"
        assert refused.candidate_local_refusal == "method_estimand_binding_mismatch"
        assert refused.run_basis_ref is None and refused.value_ref is None
        from polisyos.core.artifacts import ensure_ir_artifact_store
        from polisyos.ir import CausalEffectReportRef, load_causal_effect_report

        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            basis = load_core_json_artifact(fresh_context.store, record.run_basis_ref)
            native = load_causal_effect_report(
                ensure_ir_artifact_store(fresh_context.store),
                CausalEffectReportRef.model_validate(basis["report_ref"]),
            )
            requested = load_core_json_artifact(fresh_context.store, record.source_request_ref)
        from polisyos.foundry.methods import MethodSelectionReceipt
        from polisyos.runtime.quality.generation_cycle import (
            _value_artifact_ref,
            _value_load_ref_payload,
        )

        ir_store = ensure_ir_artifact_store(fresh_context.store)
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            runner_ref = _value_artifact_ref(basis["runner_request_ref"])
            runner_manifest = ir_store.get_manifest_by_profile(
                runner_ref.artifact_id,
                runner_ref.manifest_profile_sha256,
            )
            receipt_edges = tuple(
                edge for edge in runner_manifest.inputs if edge.role == "method_selection_receipt"
            )
            assert len(receipt_edges) == 1
            receipt_edge = receipt_edges[0]
            assert receipt_edge.manifest_profile_sha256 is not None
            selection_ref = _value_artifact_ref(
                {
                    "artifact_id": str(receipt_edge.artifact_id),
                    "kind": "runtime.value_owner_method_selection_receipt",
                    "manifest_profile_sha256": receipt_edge.manifest_profile_sha256,
                }
            )
            selection_payload = _value_load_ref_payload(ir_store, selection_ref)
        assert isinstance(selection_payload, dict)
        assert set(selection_payload) == {
            "schema_version",
            "selection_receipt",
            "selection_inputs",
        }
        assert (
            selection_payload["schema_version"]
            == "policyos.runtime.value_owner_method_selection_input.v1"
        )
        assert selection_payload["selection_inputs"] == record.selection_inputs
        selection_receipt = MethodSelectionReceipt.model_validate(
            selection_payload["selection_receipt"]
        )
        refused_selection = MethodSelectionReceipt.model_validate(
            refused.candidate_local_selection_receipt
        )
        assert selection_receipt.discovery_scope == "bound_discovery"
        assert refused_selection.discovery_scope == selection_receipt.discovery_scope
        assert selection_receipt.denominator == refused_selection.denominator
        assert selection_receipt.selection_context_hash != refused_selection.selection_context_hash
        assert selection_receipt.selected_method_fqn == record.selected_method_fqn
        assert selection_receipt.selected_method_fqn == refused_selection.selected_method_fqn
        assert selection_receipt.selected_method_fqn == method["selected_method_fqn"]
        assert native.point_estimate == method["point_estimate"]
        assert native.confidence_interval == tuple(method["statistical_interval"])
        assert basis["report_ref"] == method["native_report_ref"]
        effective = native.method_params
        for key, value in {
            "propensity_backend": "lightgbm",
            "outcome_backend": "lightgbm",
            "calibration_mode": "isotonic",
            "crossfit_folds": 5,
            "n_repeats": 3,
            "bootstrap_draws": 500,
            "random_seed": 42,
        }.items():
            assert effective[key] == value
        observed_profile = {
            "requested_parameters": json.loads(requested["method_parameters_json"]),
            "effective_parameters": effective,
            "binding_limitation": "legacy_backend_hints_are_not_execution_controls",
        }
        # The actual persisted cycle omits its in-memory WMR. The consumer
        # must recover the exact selected owner. The three guards below call
        # the canonical projector directly: HTTP does not accept a runtime WMR.
        # HTTP replay and execution-removal controls bracket these direct calls.
        from polisyos.core.artifacts import ensure_ir_artifact_store, input_ref_from_artifact_ref
        from polisyos.ir import CanonSpec, put_json_artifact
        from polisyos.pdc import gy_content_hash

        fresh_args = projector_calls[-1]
        serialized_simulation = fresh_args["simulation"].model_dump_json()
        assert '"world_model_record"' not in serialized_simulation
        restored_simulation = gc.SimulationPortObservation.model_validate_json(
            serialized_simulation
        )
        assert restored_simulation.world_model_record is None
        assert fresh_args["simulation"].world_model_record is None
        other_world = prepared.base_profile.context_inputs.world_model_record
        assert other_world.content_hash != record.world_model_record_content_hash
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            runtime_mismatch = actual_projector(
                **{
                    **fresh_args,
                    "simulation": restored_simulation.model_copy(
                        update={"world_model_record": other_world}
                    ),
                }
            )
        assert runtime_mismatch.status == "not_established"
        assert runtime_mismatch.limitation_codes == (
            "candidate_value_method_runtime_world_binding_mismatch",
        )
        assert runtime_mismatch.point_estimate is None
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            profile, _request = method_owner._profile_and_request(
                fresh_context.store, restored_simulation
            )
            assert profile is not None
            alternate_fields = profile.model_dump(mode="json", exclude={"content_hash"})
            alternate_fields["profile_id"] += "-other-selected-view"
            alternate = type(profile).model_validate(
                {**alternate_fields, "content_hash": gy_content_hash(alternate_fields)}
            )
            alternate_ref = ArtifactRef.model_validate(
                put_json_artifact(
                    ensure_ir_artifact_store(fresh_context.store),
                    alternate.model_dump(mode="json"),
                    kind=record.profile_ref.kind,
                    schema_name="policyos.runtime.generic_cycle_simulation_profile.v1",
                    schema_version="1.0",
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
            )
            profile_mismatch = actual_projector(
                **{
                    **fresh_args,
                    "simulation": restored_simulation.model_copy(
                        update={"generic_profile_ref": alternate_ref}
                    ),
                }
            )
            assert profile_mismatch.status == "not_established"
            assert profile_mismatch.limitation_codes == (
                "candidate_value_method_source_binding_mismatch",
            )
            false_fields = record.model_dump(mode="json", exclude={"content_hash"})
            false_fields["world_model_record_content_hash"] = other_world.content_hash
            false_record = CandidateValueMethodRecord.model_validate(
                {**false_fields, "content_hash": gy_content_hash(false_fields)}
            )
            false_ref = ArtifactRef.model_validate(
                put_json_artifact(
                    ensure_ir_artifact_store(fresh_context.store),
                    false_record.model_dump(mode="json"),
                    kind=method["record_ref"]["kind"],
                    schema_name="policyos.runtime.candidate_value_method.v1",
                    schema_version="1.0",
                    inputs=[
                        input_ref_from_artifact_ref(ref, role=role)
                        for role, ref in false_record.input_refs().items()
                    ],
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
            )
            world_hash_mismatch = actual_projector(**{**fresh_args, "record_ref": false_ref})
            assert world_hash_mismatch.status == "not_established"
            assert world_hash_mismatch.limitation_codes == (
                "candidate_value_method_source_binding_mismatch",
            )
            assert world_hash_mismatch.point_estimate is None
        assert len(physical_n5) == n5_calls_before
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

        def remove_selection_receipt(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if str(getattr(ref, "artifact_id", ref)) == str(selection_ref.artifact_id):
                raise FileNotFoundError("removed method selection receipt")
            return real_get_bytes(ref, *args, **kwargs)

        with monkeypatch.context() as removal:
            removal.setattr(fresh_context.store, "get_bytes", remove_selection_receipt)
            receipt_removed = fresh_client.get(f"/api/v1/runs/{run_id}")
            assert receipt_removed.status_code == 200, receipt_removed.text
            receipt_degraded = receipt_removed.json()["run"]["generic_cycle_simulation"][
                "n5_observations"
            ][0]["candidate_value_method"]
            assert receipt_degraded["status"] == "not_established"
            assert receipt_degraded["point_estimate"] is None
        receipt_restored = fresh_client.get(f"/api/v1/runs/{run_id}")
        assert receipt_restored.status_code == 200, receipt_restored.text
        assert (
            receipt_restored.json()["run"]["generic_cycle_simulation"]["n5_observations"][0][
                "candidate_value_method"
            ]
            == method
        )
        assert len(physical_n5) == n5_calls_before
    return observed_profile


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_method_preparation_uses_real_compiler_and_bound_n4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Reconcile the complete source prefix without an admitted request or N5."""
    from pydantic import ValidationError

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_value_method import _candidate_method_discovery
    from polisyos.runtime.quality.generation_cycle import ValueOwnerSourceProjectionRequestV1
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController

    def refuse_physical_n5(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("source-method preparation attempted physical N5")

    monkeypatch.setattr(JointSimulationHorizonController, "run", refuse_physical_n5)
    prepared, panel = await _prepare_source_candidate(
        tmp_path, monkeypatch, controlled_candidate_gateway
    )
    assert len(prepared.organ_run.result.candidates) == 3
    assert prepared.recorded_problem.outcome_of_interest.estimand == "ATE"
    assert prepared.recorded_problem.outcome_of_interest.metric_id == "income_ate"
    assert prepared.recorded_problem.outcome_of_interest.conditioning_variables == (
        "baseline_covariate",
    )
    assert prepared.recorded_problem.outcome_of_interest.measurement_unit == "usd"
    assert prepared.recorded_problem.outcome_of_interest.query_coordinate_status == (
        "candidate_proposed_unverified"
    )
    assert panel.expected_ate == 2.0
    assert len(prepared.app_kwargs["generic_cycle_simulation_profiles"]) == 1
    (profile,) = prepared.app_kwargs["generic_cycle_simulation_profiles"]
    assert profile.n5.replications == 1
    assert len(panel.source_rows) == 200
    assert panel.cell_counts == {
        (treatment, covariate): 50 for treatment in (0, 1) for covariate in (0, 1)
    }
    with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
        selected_request = ValueOwnerSourceProjectionRequestV1.model_validate(
            load_core_json_artifact(
                prepared.runtime_api_context.store, profile.candidate_value_source_request_ref
            )
        )
    assert selected_request == panel.request
    assert selected_request.seed == 7
    assert selected_request.production_value_eligible is False
    with _candidate_method_discovery(profile.candidate_value_method_discovery) as discovery:
        assert discovery is not None
        registry, report = discovery
        assert report.success
        assert report.discovery_manifest is not None and report.discovery_manifest.is_bound
        assert report.discovery_manifest.entry_point_groups == ()
        assert registry.get(selected_request.selected_method_fqn) is AIPWEstimator

    payload = profile.model_dump(mode="json", exclude={"content_hash"})
    legacy_payload = {
        key: value for key, value in payload.items() if key != "candidate_value_method_discovery"
    }
    legacy_profile = type(profile).model_validate(
        {**legacy_payload, "content_hash": gy_content_hash(legacy_payload)}
    )
    assert legacy_profile.candidate_value_method_discovery is None
    assert legacy_profile.model_dump(mode="json", exclude={"content_hash"}) == legacy_payload
    unbound_payload = {
        key: value for key, value in payload.items() if key != "candidate_value_source_request_ref"
    }
    with pytest.raises(
        ValidationError, match="generic_cycle_candidate_value_method_discovery_requires_source"
    ):
        type(profile).model_validate(
            {**unbound_payload, "content_hash": gy_content_hash(unbound_payload)}
        )

    candidates = {
        candidate.atom.target_world_slots[0]: candidate
        for candidate in prepared.organ_run.result.candidates
    }
    from polisyos.runtime.quality import generation_cycle as gc

    estimand = gc._typed_value_estimand_spec(selected_request.estimand_spec_json)
    with pytest.raises(gc._CandidateLocalMethodEstimandMismatchError) as refused:
        gc._value_owner_source_atom_estimand_binding(
            candidate=candidates["government.balance"],
            problem=prepared.recorded_problem,
            estimand=estimand,
            measurement_unit=selected_request.outcome_bounds_unit,
        )
    assert refused.value.code == "method_estimand_binding_mismatch"
    procurement_candidate = candidates["cells.distress_score"]
    procurement_binding = gc._value_owner_source_atom_estimand_binding(
        candidate=procurement_candidate,
        problem=prepared.recorded_problem,
        estimand=estimand,
        measurement_unit=selected_request.outcome_bounds_unit,
    )
    assert procurement_binding == procurement_candidate.atom.content_hash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ordinary_candidate_executes_source_rows_persists_and_fresh_gets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    record_property: Callable[[str, object], None],
) -> None:
    """A local N8 mismatch preserves N5, tries its ranked sibling, and survives fresh GET."""
    from fastapi.testclient import TestClient

    from polisyos.core.contracts import ModelInputScope
    from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.quality import candidate_value_method as method_owner
    from polisyos.runtime.quality import generation_cycle as gc
    from tests._helpers.control_worker import dispatch_one_control_job

    scope = ModelInputScope(
        population_ref="population:declared-candidate-panel",
        geography_ref="UA",
        jurisdiction_ref="UA",
        period_start=date(1800, 1, 1),
        period_end=date(1919, 12, 31),
        time_role="observation_time",
        period_basis="calendar_year",
    )
    prepared, panel = await _prepare_source_candidate(
        tmp_path, monkeypatch, controlled_candidate_gateway, measurement_scope=scope
    )
    assert len(panel.source.projections["agents.income"].observations) == 121
    monkeypatch.setattr(
        gc,
        "_load_value_data_profile_from_l1_dcat",
        partial(gc._load_value_data_profile_from_l1_dcat, owner_row_limit=120),
    )
    projector_calls: list[dict[str, Any]] = []
    actual_projector = method_owner.project_candidate_value_method

    def observe_actual_projection(**kwargs: Any) -> Any:
        result = actual_projector(**kwargs)
        projector_calls.append(dict(kwargs))
        return result

    monkeypatch.setattr(method_owner, "project_candidate_value_method", observe_actual_projection)
    observed = _install_served_execution_observers(monkeypatch)
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
        generic = initial.json()["run"]["generic_cycle_simulation"]
        (attempt,) = generic["candidate_evaluation_attempts"]
        (selected,) = generic["n5_observations"]
        _assert_source_method_n4_lineage(
            prepared=prepared, job=job, generic=generic, attempt=attempt, selected=selected
        )

    assert len(observed["actual_n4_organs"]) == 1
    assert sum(not call["used_prefetched_organ"] for call in observed["n4_port_calls"]) == 1
    actual_organ = observed["actual_n4_organs"][0]
    candidate_ids_by_slot = _assert_neutral_source_rank(actual_organ)
    n4_provider_calls = actual_organ.result.llm_calls
    assert n4_provider_calls
    assert all(call.status == "success" for call in n4_provider_calls)
    assert all(call.provider == "controlled_synthetic_stage_provider" for call in n4_provider_calls)

    assert generic["artifact_status"] == "resolved"
    assert generic["n4_source_status"] == "resolved"
    assert generic["authority_purpose"] == "cycle_input_candidate_only"
    assert generic["publication_authority"] is False
    assert attempt["candidate_id"] == candidate_ids_by_slot["government.balance"]
    assert attempt["failure_stage"] == "n8"
    assert attempt["simulation_status"] == "joint_simulated"
    assert attempt["value_status"] == "value_conditional"
    assert attempt["selected_method_fqn"] == AIPWEstimator.signature.fqn
    assert attempt["candidate_value_method_local_refusal"] == ("method_estimand_binding_mismatch")
    assert attempt["candidate_value_method_ref"]["kind"] == "runtime.candidate_value_method"
    assert attempt["n5_input_ref"] is not None
    assert attempt["n5_execution_ref"] is not None
    assert attempt["simulation_result_ref"] is not None
    assert attempt["numerical_result_verification"] == "not_established"
    assert attempt["publication_authority"] is False

    assert selected["candidate_id"] == candidate_ids_by_slot["cells.distress_score"]
    assert selected["candidate_id"] != attempt["candidate_id"]
    assert selected["status"] == "joint_simulated"
    method = _assert_source_method_numerics(
        selected,
        expected_ate=panel.expected_ate,
        expected_bounds=panel.expected_bounds,
    )
    assert method["measurement_scope"] == scope.model_dump(mode="json")
    assert [
        (call.replications, call.intervention_atoms[0].target_world_slots)
        for call in observed["physical_n5"]
    ] == [(1, ("government.balance",)), (1, ("cells.distress_score",))]
    capacity_before_fresh_get = _assert_candidate_local_quota(observed, completed_standard_units=2)
    n4_counts_before_fresh_get = (
        len(observed["n4_port_calls"]),
        len(observed["actual_n4_organs"]),
        len(observed["physical_n5"]),
        sum(len(organ.result.llm_calls) for organ in observed["actual_n4_organs"]),
    )
    observed_profile = _assert_source_method_reader_suffix(
        prepared=prepared,
        method=method,
        physical_n5=observed["physical_n5"],
        projector_calls=projector_calls,
        actual_projector=actual_projector,
        expected_attempt=attempt,
        monkeypatch=monkeypatch,
        run_id=run_id,
    )
    assert n4_counts_before_fresh_get == (
        len(observed["n4_port_calls"]),
        len(observed["actual_n4_organs"]),
        len(observed["physical_n5"]),
        sum(len(organ.result.llm_calls) for organ in observed["actual_n4_organs"]),
    )
    capacity_after_fresh_get = _assert_candidate_local_quota(observed, completed_standard_units=2)
    assert (
        capacity_after_fresh_get.standard_remaining_units
        == capacity_before_fresh_get.standard_remaining_units
    )
    assert (
        capacity_after_fresh_get.protected_remaining_units
        == capacity_before_fresh_get.protected_remaining_units
    )
    _assert_and_emit_source_method_profile(observed_profile, record_property)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exhausted_standard_quota_stops_n8_fallback_before_sibling_horizon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """The completed first N5 consumes the one standard unit before the N8 retry."""
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactRef, load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5ExecutionV3,
    )
    from tests._helpers.control_worker import dispatch_one_control_job

    prepared, _ = await _prepare_source_candidate(
        tmp_path, monkeypatch, controlled_candidate_gateway, total_n5_units=2
    )
    prepared.request_json["run_budget_scope"] = "metered_paid_producers_and_bounded_candidate"
    observed = _install_served_execution_observers(monkeypatch)
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
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        assert dispatched == job_id
        job = service._control_store.get_job(job_id)
        assert job is not None and job.state == "completed", getattr(job, "error_message", None)
        run_id = str(job.progress["core_run_id"])
        initial = client.get(f"/api/v1/runs/{run_id}")
        assert initial.status_code == 200, initial.text
        generic = initial.json()["run"]["generic_cycle_simulation"]

        (organ,) = observed["actual_n4_organs"]
        assert sum(not call["used_prefetched_organ"] for call in observed["n4_port_calls"]) == 1
        candidate_ids = _assert_neutral_source_rank(organ)
        (physical_request,) = observed["physical_n5"]
        assert physical_request.replications == 1
        assert physical_request.intervention_atoms[0].target_world_slots == ("government.balance",)

        (attempt,) = generic["candidate_evaluation_attempts"]
        assert attempt["candidate_id"] == candidate_ids["government.balance"]
        assert attempt["simulation_status"] == "joint_simulated"
        assert attempt["failure_stage"] == "n8"
        assert attempt["candidate_value_method_local_refusal"] == "method_estimand_binding_mismatch"
        first_result_ref = ArtifactRef.model_validate(attempt["simulation_result_ref"])
        (sibling,) = generic["n5_observations"]
        assert sibling["candidate_id"] == candidate_ids["cells.distress_score"]
        assert sibling["status"] == "simulation_blocked"
        assert sibling["n5_owner_join_status"] == "resolved"
        assert sibling["n5_request_binding_status"] == "resolved"
        assert "n5_invocation_quota_exhausted" in sibling["authority_blockers"]
        assert (
            sibling["simulation_result_ref"] is None and sibling["simulation_result_body"] is None
        )
        assert sibling["n8_status"] == "value_blocked" and sibling["n8_value_ref"] is None
        assert sibling["publication_authority"] is False
        assert sibling["n4_source_ref"] == attempt["n4_source_ref"]

        first_execution_ref = ArtifactRef.model_validate(attempt["n5_execution_ref"])
        sibling_execution_ref = ArtifactRef.model_validate(sibling["n5_execution_ref"])
        assert sibling_execution_ref != first_execution_ref
        store = prepared.runtime_api_context.store
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            first_execution = GenericCycleSimulationN5ExecutionV3.model_validate(
                load_core_json_artifact(store, first_execution_ref)
            )
            sibling_execution = GenericCycleSimulationN5ExecutionV3.model_validate(
                load_core_json_artifact(store, sibling_execution_ref)
            )
            first_result = load_joint_simulation_result(
                first_result_ref,
                store=store,
                expected_request=first_execution.request_binding.request,
            )
        assert first_execution.candidate_id == attempt["candidate_id"]
        assert first_execution.status == "joint_simulated"
        assert first_execution.result_ref == first_result_ref
        assert sibling_execution.candidate_id == sibling["candidate_id"]
        assert sibling_execution.status == "simulation_blocked"
        assert sibling_execution.result_ref is None
        assert sibling_execution.limitation_code == "n5_invocation_quota_exhausted"
        assert (
            sibling_execution.request_binding.request_content_hash
            == sibling["n5_request_content_hash"]
        )
        assert sibling_execution.n4_source_ref == first_execution.n4_source_ref
        assert sibling_execution.profile_ref == first_execution.profile_ref
        assert sibling_execution.job_id == first_execution.job_id == job_id
        (work,) = first_result.physical_work_observations
        assert work.status == work.invocation_quota_status == "completed"
        assert work.invocation_quota_purpose == "standard"
        capacity = _assert_candidate_local_quota(
            observed, completed_standard_units=1, standard_limit_units=1
        )
        ((operation_id, _),) = capacity.terminal_witnesses
        assert operation_id == work.invocation_quota_operation_id

    fresh_context = build_runtime_api_context(
        cas_root=prepared.cas_root, core_runs_root=prepared.runtime_api_context.core_runs_root
    )
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
        fresh_generic = fresh.json()["run"]["generic_cycle_simulation"]
        assert fresh_generic["candidate_evaluation_attempts"] == [attempt]
        assert fresh_generic["n5_observations"] == [sibling]
    assert observed["physical_n5"] == [physical_request]
    assert observed["actual_n4_organs"] == [organ]
    assert (
        _assert_candidate_local_quota(observed, completed_standard_units=1, standard_limit_units=1)
        == capacity
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_arm_source_preflight_does_not_reuse_local_retry_permission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """A shared AIPW arm failure keeps the actual first N5 and blocks sibling retry."""
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactRef, load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.catalog.causal import treatment_effects
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.quality import candidate_value_method as method_owner
    from polisyos.runtime.quality import generation_cycle as gc
    from tests._helpers.control_worker import dispatch_one_control_job

    preflight_refusals: list[str] = []
    original_preflight = gc._value_owner_source_candidate_local_method_preflight

    def observe_candidate_local_preflight(**kwargs: Any) -> None:
        try:
            original_preflight(**kwargs)
        except ValueError as exc:
            preflight_refusals.append(str(exc))
            raise

    monkeypatch.setattr(
        gc,
        "_value_owner_source_candidate_local_method_preflight",
        observe_candidate_local_preflight,
    )
    aipw_execution_attempts: list[object] = []

    def forbid_aipw_execution(*args: Any, **kwargs: Any) -> Any:
        aipw_execution_attempts.append((args, kwargs))
        raise AssertionError("one_arm_control_reached_aipw_execution")

    # The method route reads the annotated input on AIPWEstimator.pure_step.
    # Keep that contract intact and trap the numerical fit it invokes.
    monkeypatch.setattr(treatment_effects, "fit_aipw_ate", forbid_aipw_execution)
    prepared, panel = await _prepare_source_candidate(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        one_arm_control=True,
    )
    assert panel.expected_ate is None
    assert panel.expected_bounds == pytest.approx((-11.5, 4.5))
    assert len(panel.source_rows) == 200
    assert panel.cell_counts == {(0, 0): 100, (0, 1): 100}
    observed = _install_served_execution_observers(monkeypatch)
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
        generic = initial.json()["run"]["generic_cycle_simulation"]

    assert len(observed["actual_n4_organs"]) == 1
    candidate_ids_by_slot = _assert_neutral_source_rank(observed["actual_n4_organs"][0])
    assert [
        (call.replications, call.intervention_atoms[0].target_world_slots)
        for call in observed["physical_n5"]
    ] == [(1, ("government.balance",))]
    assert len(observed.get("n4_port_calls", ())) >= 1
    assert sum(not call["used_prefetched_organ"] for call in observed["n4_port_calls"]) == 1
    assert generic["authority_purpose"] == "cycle_input_candidate_only"
    assert generic["publication_authority"] is False
    assert generic.get("candidate_evaluation_attempts", []) == []
    assert generic.get("candidate_evaluation_attempts_limitation_code") is None
    observations = generic["n5_observations"]
    assert len(observations) == 1
    observation = observations[0]
    assert observation["candidate_id"] == candidate_ids_by_slot["government.balance"]
    assert observation["status"] == "joint_simulated"
    assert observation["n8_status"] == "value_conditional"
    assert observation["n8_lineage_status"] == "resolved"
    assert observation["n8_value_ref"] == observation["simulation_result_ref"]["artifact_id"]
    refused = observation["candidate_value_method"]
    assert refused["status"] == "refused"
    assert refused["failure_kind"] == "input_refused"
    assert refused["selected_method_fqn"] == treatment_effects.AIPWEstimator.signature.fqn
    assert refused["value_ref"] is None
    assert refused["run_basis_ref"] is None
    assert refused["discovery_limitations"] == [method_owner._CONTROLLED_BUILTINS_LIMITATION]
    assert "value_owner_method_run_intent_unresolved" in refused["limitation_codes"]
    assert "value_owner_source_candidate_local_treatment_arms_not_qualified" in refused["reason"]
    assert preflight_refusals == ["value_owner_source_candidate_local_treatment_arms_not_qualified"]
    assert aipw_execution_attempts == []
    capacity_before_fresh_get = _assert_candidate_local_quota(observed, completed_standard_units=1)
    counts_before_fresh_get = (
        len(observed["n4_port_calls"]),
        len(observed["actual_n4_organs"]),
        len(observed["physical_n5"]),
        sum(len(organ.result.llm_calls) for organ in observed["actual_n4_organs"]),
    )

    fresh_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
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
        fresh_generic = fresh.json()["run"]["generic_cycle_simulation"]
        assert fresh_generic.get("candidate_evaluation_attempts", []) == []
        assert len(fresh_generic["n5_observations"]) == 1
        fresh_observation = fresh_generic["n5_observations"][0]
        assert fresh_observation["candidate_id"] == observation["candidate_id"]
        assert fresh_observation["n5_input_ref"] == observation["n5_input_ref"]
        assert fresh_observation["simulation_result_ref"] == observation["simulation_result_ref"]
        assert fresh_observation["candidate_value_method"] == refused
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            record = method_owner.CandidateValueMethodRecord.model_validate(
                load_core_json_artifact(
                    fresh_context.store, ArtifactRef.model_validate(refused["record_ref"])
                )
            )
        assert record.candidate_local_refusal is None
        assert record.candidate_local_selection_receipt is None
    assert counts_before_fresh_get == (
        len(observed["n4_port_calls"]),
        len(observed["actual_n4_organs"]),
        len(observed["physical_n5"]),
        sum(len(organ.result.llm_calls) for organ in observed["actual_n4_organs"]),
    )
    capacity_after_fresh_get = _assert_candidate_local_quota(observed, completed_standard_units=1)
    assert (
        capacity_after_fresh_get.standard_remaining_units
        == capacity_before_fresh_get.standard_remaining_units
    )
    assert (
        capacity_after_fresh_get.protected_remaining_units
        == capacity_before_fresh_get.protected_remaining_units
    )
