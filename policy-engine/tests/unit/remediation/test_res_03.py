"""Regression witnesses for RES-03 partial async-chain results."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any, ClassVar

import pytest

from polisyos.foundry.methods.backends.async_chain_executor import (
    AsyncChainExecutionError,
    AsyncChainExecutor,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.composer import MethodComposer
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Keep synthetic RES-03 methods isolated between tests."""
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _make_method(
    name: str,
    *,
    requires: frozenset[str] = frozenset(),
    output_slot_names: frozenset[str] = frozenset(),
    step: Callable[[Any, Mapping[str, Any]], Any] | None = None,
) -> type:
    """Build a small real registry method for an async-chain witness."""
    output_slots = frozenset(
        SlotSpec(
            name=slot_name,
            slot_type=SlotType.SCALAR,
            unit=Unit(dimension="res03", symbol="json"),
            shape=(),
        )
        for slot_name in output_slot_names
    )
    method_signature = MethodSignature(
        name=name,
        namespace="tests.res03",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=output_slots,
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
        requires=requires,
    )

    class TestMethod:
        signature: ClassVar[MethodSignature] = method_signature
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description=f"RES-03 test method: {name}",
            tags=frozenset({"res03", "test"}),
        )

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            if step is None:
                return None
            return step(state, params)

    TestMethod.__name__ = name.replace("_", " ").title().replace(" ", "")
    return TestMethod


def _register(*method_classes: type) -> MethodRegistry:
    """Register synthetic methods in the isolated process registry."""
    registry = MethodRegistry.get_instance()
    for method_class in method_classes:
        registry.register(method_class, override=True)
    return registry


def _partial_chain(
    *,
    fail_b: bool = True,
    right_error: Exception | None = None,
) -> tuple[MethodComposer, MethodRegistry, dict[str, Any]]:
    """Build a previous level, an independent A/B level, and dependent C."""
    right_error = right_error or ValueError("right node failed exactly")
    observations: dict[str, Any] = {"c_calls": 0, "right_error": right_error}

    previous = _make_method(
        "previous",
        output_slot_names=frozenset({"previous", "scope", "artifact_ref"}),
        step=lambda _state, _params: {
            "previous": "previous-value",
            "scope": "world:previous",
            "artifact_ref": "sha256:previous",
        },
    )
    left = _make_method(
        "left",
        requires=frozenset({"tests.res03.previous@1.0.0"}),
        output_slot_names=frozenset({"left", "scope", "artifact_ref"}),
        step=lambda _state, _params: {
            "left": 7,
            "scope": "world:left",
            "artifact_ref": "sha256:left",
        },
    )

    def right_step(_state: Any, _params: Mapping[str, Any]) -> Any:
        if fail_b:
            raise right_error
        return {
            "right": 11,
            "scope": "world:right",
            "artifact_ref": "sha256:right",
        }

    right = _make_method(
        "right",
        requires=frozenset({"tests.res03.previous@1.0.0"}),
        output_slot_names=frozenset({"right", "scope", "artifact_ref"}),
        step=right_step,
    )

    def dependent_step(_state: Any, _params: Mapping[str, Any]) -> Any:
        observations["c_calls"] += 1
        return {"dependent": True}

    dependent = _make_method(
        "dependent",
        requires=frozenset({"tests.res03.right@1.0.0"}),
        output_slot_names=frozenset({"dependent"}),
        step=dependent_step,
    )

    registry = _register(previous, left, right, dependent)
    composer = MethodComposer(registry=registry)
    composer.add("tests.res03.previous@1.0.0")
    composer.add("tests.res03.left@1.0.0")
    composer.add("tests.res03.right@1.0.0")
    composer.add("tests.res03.dependent@1.0.0")
    return composer, registry, observations


def test_independent_success_survives_sibling_failure_with_exact_error_and_scope() -> None:
    """A's result remains readable with its scope while B's exact error stays terminal."""
    composer, registry, observations = _partial_chain()
    chain = composer.build(validate_semantics=False)

    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    error = raised.value
    assert len(error.node_errors) == 1
    assert error.node_errors[0].method_fqn == "tests.res03.right@1.0.0"
    assert type(error.node_errors[0].error) is ValueError
    assert error.node_errors[0].error is observations["right_error"]
    assert str(error.node_errors[0].error) == "right node failed exactly"

    partial = error.partial_result
    assert partial.final_state["left"] == 7
    assert partial.final_state["scope"] == "world:left"
    assert partial.final_state["artifact_ref"] == "sha256:left"
    assert [node_id for node_id, _result in partial.node_results] == [
        node_id
        for node_id, _node in chain.dag.nodes.items()
        if _node.method_fqn in {"tests.res03.previous@1.0.0", "tests.res03.left@1.0.0"}
    ]
    assert error.failed_level_index == 1

    # Each completed node retains its own scope even when the shallow merged
    # state legitimately selects the later node's value for the same key.
    outputs = {
        chain.get_node(node_id).method_fqn: result.output
        for node_id, result in partial.node_results
    }
    assert outputs == {
        "tests.res03.previous@1.0.0": {
            "previous": "previous-value",
            "scope": "world:previous",
            "artifact_ref": "sha256:previous",
        },
        "tests.res03.left@1.0.0": {
            "left": 7,
            "scope": "world:left",
            "artifact_ref": "sha256:left",
        },
    }


def test_terminal_partial_preserves_the_original_typed_error_instance() -> None:
    """A real dispatched failure is retained, rather than reconstructed from prose."""

    class TypedValueError(RuntimeError):
        code: ClassVar[str] = "res03.value_failed"

    failure = TypedValueError("selected value failed after its sibling completed")
    composer, registry, observations = _partial_chain(right_error=failure)
    chain = composer.build(validate_semantics=False)

    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    error = raised.value
    assert error.node_errors[0].error is failure
    assert error.node_errors[0].error.code == "res03.value_failed"
    assert str(error.node_errors[0].error) == str(failure)
    assert error.partial_result.final_state["left"] == 7
    assert observations["c_calls"] == 0


def test_completed_result_oracle_detects_removed_level_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing only A's merge loses its result while preserving B's real failure."""
    composer, registry, observations = _partial_chain()
    chain = composer.build(validate_semantics=False)
    original_merge = AsyncChainExecutor._merge_level_results

    def remove_left_merge(**kwargs: Any) -> Any:
        kwargs["level_results"] = tuple(
            (node_id, result)
            for node_id, result in kwargs["level_results"]
            if not isinstance(result.output, dict) or "left" not in result.output
        )
        return original_merge(**kwargs)

    def execute_and_require_completed_result() -> None:
        with pytest.raises(AsyncChainExecutionError) as raised:
            asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))
        error = raised.value
        assert error.node_errors[0].error is observations["right_error"]
        assert observations["c_calls"] == 0
        assert error.partial_result.final_state["previous"] == "previous-value"
        assert "left" in error.partial_result.final_state, "completed numerical result was lost"
        assert error.partial_result.final_state["left"] == 7

    with monkeypatch.context() as removed:
        removed.setattr(AsyncChainExecutor, "_merge_level_results", staticmethod(remove_left_merge))
        with pytest.raises(AssertionError, match="completed numerical result was lost"):
            execute_and_require_completed_result()

    execute_and_require_completed_result()


def test_dependent_node_is_not_reported_as_successful_partial_result() -> None:
    """A dependent node is withheld when its common basis failed."""
    composer, registry, observations = _partial_chain()
    chain = composer.build(validate_semantics=False)

    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    error = raised.value
    partial_ids = {node_id for node_id, _result in error.partial_result.node_results}
    dependent_id = next(
        node_id
        for node_id, node in chain.dag.nodes.items()
        if node.method_fqn == "tests.res03.dependent@1.0.0"
    )
    assert dependent_id not in partial_ids
    assert dependent_id in error.blocked_node_ids
    assert observations["c_calls"] == 0


def test_previous_completed_level_survives_later_level_failure() -> None:
    """Completed levels remain available after a later parallel level fails."""
    composer, registry, _observations = _partial_chain()
    chain = composer.build(validate_semantics=False)

    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    partial = raised.value.partial_result
    assert partial.final_state["previous"] == "previous-value"
    assert partial.final_state["scope"] == "world:left"
    assert [result.output["previous"] for _node_id, result in partial.node_results[:1]] == [
        "previous-value"
    ]


def test_all_success_control_returns_all_levels_without_partial_metadata() -> None:
    """The all-success path remains a normal complete ChainExecutionResult."""
    composer, registry, observations = _partial_chain(fail_b=False)
    chain = composer.build(validate_semantics=False)

    result = asyncio.run(AsyncChainExecutor(registry=registry).execute(chain, initial_state={}))

    assert result.final_state["previous"] == "previous-value"
    assert result.final_state["left"] == 7
    assert result.final_state["right"] == 11
    assert result.final_state["dependent"] is True
    assert len(result.node_results) == 4
    assert observations["c_calls"] == 1


def _read_retained_configured_n5_in_fresh_process(
    handoff: dict[str, Any],
) -> dict[str, Any]:
    """Consume the failed leaf's exact persisted result without its producer memory."""
    import hashlib
    import os
    from pathlib import Path

    from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from polisyos.runtime.quality import generation_cycle as generation_cycle_module
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_cycle import (
        SimulationPortObservation,
        _DefaultSimulationBoundFoundryValuePort,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    project_root = Path(handoff["project_root"])
    source_path = Path(generation_cycle_module.__file__).resolve()
    assert (
        source_path == (project_root / "src/polisyos/runtime/quality/generation_cycle.py").resolve()
    )
    selected = {
        name: ArtifactRef.model_validate(value) for name, value in handoff["selected_refs"].items()
    }
    expected_scope = {
        "expected_run_id": handoff["run_id"],
        "expected_job_id": handoff["job_id"],
        "expected_tenant_id": handoff["tenant_id"],
        "expected_cell_id": handoff["cell_id"],
    }
    with tenant_scope(
        None,
        tenant_id=handoff["tenant_id"],
        cell_id=handoff["cell_id"],
    ):
        store = guard_runtime_cas(
            FileSystemCAS(Path(handoff["cas_root"])).with_ambient_ownership_enforcement()
        )
        repository = GenerationSourceRepository(store)
        input_record = repository.resolve_candidate_simulation_v5(
            ref=selected["input"], **expected_scope
        )
        execution = repository.resolve_candidate_simulation_v5(
            ref=selected["execution"], **expected_scope
        )
        assert type(input_record) is CandidateSimulationN5InputV5
        assert type(execution) is CandidateSimulationExecutionV5
        assert execution.n5_input_ref == selected["input"]
        assert execution.n4_source_ref == input_record.n4_source_ref == selected["source"]
        assert execution.n5_result_ref == selected["result"]
        assert input_record.context_job_ref == selected["context"]
        source = repository.load_candidate_scenario_source_for_n5(
            selected["source"], **expected_scope
        )
        context_job = CycleSubstrateContextArtifactOwner(
            store=store
        ).resolve_historical_job_artifact(
            selected["context"], problem=source.problem, **expected_scope
        )
        assert source.candidate.candidate_id == input_record.original_candidate_id
        assert source.problem.design_problem_id == handoff["problem_id"]
        world = context_job.context.world_model_record
        assert world.content_hash == input_record.materialization.world_model_record_hash
        simulation = SimulationPortObservation.model_validate(
            {**handoff["simulation"], "world_model_record": world}
        )
        assert simulation.candidate_simulation_n5_input_ref == selected["input"]
        assert simulation.simulation_result_ref == selected["result"]
        assert simulation.simulation_ref == execution.n5_result_content_hash
        result_bytes = store.get_bytes(selected["result"])
        result_hash = "sha256:" + hashlib.sha256(result_bytes).hexdigest()
        assert result_hash == str(selected["result"].artifact_id) == handoff["result_sha256"]
        result = load_joint_simulation_result(
            selected["result"],
            store=store,
            expected_world_model_record_content_hash=world.content_hash,
            expected_atom_ids=(input_record.materialization.derived_n5_atom.intervention_id,),
            expected_selected_outcomes=(input_record.outcome_variable,),
            expected_receipt_payload_hash=simulation.simulation_ref,
        )
        assert result.receipt.payload_hash == execution.n5_result_content_hash
        port = _DefaultSimulationBoundFoundryValuePort(
            repo_root=project_root,
            cycle_substrate_context=context_job.context,
            artifact_store=store,
        )

        def consume(observation: SimulationPortObservation) -> dict[str, Any]:
            return port(
                candidate=source.candidate,
                simulation=observation,
                problem=source.problem,
                cycle_index=handoff["cycle_index"],
            ).model_dump(mode="json")

        positive = consume(simulation)
        wrong_world = consume(
            simulation.model_copy(
                update={
                    "world_model_record": world.model_copy(
                        update={"content_hash": "sha256:" + "e" * 64}
                    )
                }
            )
        )
        missing_result = consume(
            simulation.model_copy(update={"simulation_result_ref": None, "simulation_ref": None})
        )
        # The refusal controls alter only the receiving binding, not the
        # historical artifact. Reopen it after both controls through its owner.
        restored = load_joint_simulation_result(
            selected["result"],
            store=store,
            expected_world_model_record_content_hash=world.content_hash,
            expected_atom_ids=result.atom_ids,
            expected_selected_outcomes=result.selected_outcomes,
            expected_receipt_payload_hash=execution.n5_result_content_hash,
        )
        assert restored == result
        assert store.get_bytes(selected["result"]) == result_bytes
        replay = consume(simulation)
        output = {
            "consumer_pid": os.getpid(),
            "generation_cycle_source": str(source_path),
            "selected_refs": {name: ref.model_dump(mode="json") for name, ref in selected.items()},
            "input_content_hash": input_record.content_hash,
            "execution_content_hash": execution.content_hash,
            "result_sha256": result_hash,
            "receipt_payload_hash": result.receipt.payload_hash,
            "outcome_unit_id": source.model_declaration.outcome_unit_id,
            "model_declaration_ref": input_record.model_declaration_ref.model_dump(mode="json"),
            "ncm_ref": input_record.ncm_ref.model_dump(mode="json"),
            "trajectories": [
                trajectory.model_dump(mode="json") for trajectory in result.trajectories
            ],
            "positive": positive,
            "wrong_world": wrong_world,
            "missing_result": missing_result,
            "restored": replay,
        }
        store.close()
        return output


@pytest.mark.integration
def test_configured_candidate_n5_persists_before_same_leaf_value_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, str], None],
) -> None:
    """A real configured N5 survives CAS persistence before its value projection fails."""
    import hashlib
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.control import ControlJobResponse
    from polisyos.core.contracts.runtime import RunDetailsResponse, RuntimeApiProblem
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import dev_identity_middleware
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.http.services.control.job_nl_execution import (
        ControlNLJobExecutionMixin,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        _control_job_execution_scope_from_event,
    )
    from polisyos.runtime.quality import generation_cycle as generation_cycle_module
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_generation import N4CandidateScenarioProposalCandidate
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        JointSimulationPort,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveGenerationCycleController,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.controlled_candidate_profile import (
        ControlledCandidateGateway,
        _build_configured_procurement_profile,
        _controlled_registered_tax_recording,
        _current_compiler_problem,
        _seed_controlled_selected_skg_source,
        synthetic_controlled_candidate_provider_profile,
    )
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )
    from tools.quality.validation import check_layer3_gy_design_generation_contract as n4_contract

    repo_root = Path(__file__).resolve().parents[3]
    recording_id = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_FALLBACK_URLS", "")
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-a"
    normal_cas_root = tmp_path / ".polisyos-normal"
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control-normal.sqlite3").as_posix()
    )
    normal_api_context = build_runtime_api_context(
        cas_root=normal_cas_root,
        core_runs_root=normal_cas_root / "runs",
    )
    recording = next(
        item
        for item in n4_contract._load_recordings(repo_root)
        if item.get("design_problem_id") == recording_id
    )
    original_problem = _current_compiler_problem(recording)
    raw_request = (
        original_problem.nl_provenance.raw_request
        + "\n\nFor this controlled software fixture only, set the intervention target "
        "to global.tax_rate and measure government.balance as the outcome; this does "
        "not establish legal authority or empirical grounding."
    )
    controlled_recording = _controlled_registered_tax_recording(
        recording,
        outcome_variable="government.balance",
        rate=0,
    )
    recorded_problem = _current_compiler_problem(
        controlled_recording,
        raw_request=raw_request,
        outcome_variable="government.balance",
        problem_statement="Exercise a registered NCM outcome in a controlled served fixture.",
    )
    assert recorded_problem.design_problem_id != original_problem.design_problem_id
    assert recorded_problem.outcome_of_interest.target_variable == "government.balance"
    assert (
        recorded_problem.outcome_of_interest.metric_id
        == original_problem.outcome_of_interest.metric_id
    )
    assert recorded_problem.nl_provenance.raw_request == raw_request
    assert controlled_recording["recording_id"] != recording["recording_id"]
    assert controlled_recording["recording_content_hash"] != recording["recording_content_hash"]
    assert controlled_recording["derived_from_recording_id"] == recording["recording_id"]
    assert controlled_recording["derived_from_content_hash"] == recording["recording_content_hash"]
    assert all(
        constraint.source_text is None or constraint.source_text in raw_request
        for constraint in original_problem.constraints
    )
    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "bounded-configured-source",
        outcome_variable="government.balance",
        include_owner_slot_manifest=True,
        owner_knob_dictionary={
            "tax_relief_rate": {
                "default": 0.1,
                "type": "float",
                "min": 0.0,
                "max": 0.5,
                "mechanism_id": "tax_relief_rate",
                "param_path": "params.rate",
            },
        },
    )
    selected_skg_source = _seed_controlled_selected_skg_source(
        tmp_path / "bounded-selected-skg",
        recorded_problem=recorded_problem,
        source_root=source_inputs.root,
    )

    def build_profile(artifact_store: Any, profile_root: Path) -> tuple[Any, Any]:
        profile, declaration, _world_build = _build_configured_procurement_profile(
            recorded_problem=recorded_problem,
            tmp_path=profile_root,
            artifact_store=artifact_store,
            tenant_id=tenant_id,
            cell_id=cell_id,
            source_root=source_inputs.root,
            selected_skg_source=selected_skg_source,
            repo_root=repo_root,
            basis_repo_root=source_inputs.root,
            l6_source_owner_root=source_inputs.root,
            rule_operator_kind="tax_relief_rate",
            rule_parameter_id="rate",
            rule_target_world_slot="global.tax_rate",
            rule_unit_id="ratio",
            rule_minimum=0,
            rule_maximum=0,
            target_baseline=0.25,
        )
        assert profile.profile_selection_ref == cycle_job_profile_selection_ref(recorded_problem)
        assert profile.rule.operator_kind == "tax_relief_rate"
        assert profile.rule.parameter_id == "rate"
        assert profile.rule.target_world_slot == "global.tax_rate"
        assert profile.rule.unit_id == "ratio"
        assert (profile.rule.minimum, profile.rule.maximum) == (0, 0)
        assert profile.n5.baseline_state == {
            "global.tax_rate": 0.25,
            "government.balance": 0.0,
        }
        assert declaration.profile_selection_ref == profile.profile_selection_ref
        assert declaration.target_world_slot == "global.tax_rate"
        assert declaration.target_unit_id == "ratio"
        assert declaration.outcome_variable == "government.balance"
        assert declaration.outcome_unit_id == "usd"
        assert declaration.assumption == "declared_candidate_scm_not_empirically_grounded"
        assert {
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        }.issubset(profile.limitations)
        assert profile.context_inputs.intervention_substrate.knob_dictionary == {
            "tax_relief_rate": {
                "default": 0.1,
                "type": "float",
                "min": 0.0,
                "max": 0.5,
                "mechanism_id": "tax_relief_rate",
                "param_path": "params.rate",
            }
        }
        world_record = profile.context_inputs.world_model_record
        assert world_record.slot_binding("global.tax_rate").unit == "ratio"
        assert world_record.slot_binding("government.balance").unit == "usd"
        return profile, declaration

    model_id = str(recording["model_id"])
    profile, model_declaration = build_profile(
        normal_api_context.store,
        tmp_path / "normal-profile",
    )
    normal_provider_profile = synthetic_controlled_candidate_provider_profile(
        recording,
        controlled_recording,
        problem=recorded_problem,
        evidence_root=tmp_path / "normal-provider-exchanges",
    )

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems: list[object] = []
    gateway_holder: list[ControlledCandidateGateway | None] = [None]

    async def run_real_compiler(**kwargs: Any) -> Any:
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        problem = await original_compiler(**kwargs)
        compiled_problems.append(problem)
        gateway = gateway_holder[0]
        assert gateway is not None
        gateway.admit_compiled_problem(problem)
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )

    original_preserve_failed_n5 = ControlNLJobExecutionMixin._preserve_failed_nl_candidate_n5
    preservation_attempts: list[Exception] = []
    preservation_errors: list[dict[str, str | None]] = []

    def observe_failed_n5_preservation(
        service: Any,
        context: Any,
        *,
        error: Exception,
    ) -> None:
        preservation_attempts.append(error)
        try:
            original_preserve_failed_n5(service, context, error=error)
        except Exception as preservation_error:
            code = getattr(preservation_error, "code", None)
            preservation_errors.append(
                {
                    "type": type(preservation_error).__name__,
                    "code": None if code is None else str(code),
                    "string": str(preservation_error),
                }
            )
            raise

    monkeypatch.setattr(
        ControlNLJobExecutionMixin,
        "_preserve_failed_nl_candidate_n5",
        observe_failed_n5_preservation,
    )

    n5_port_calls: dict[
        str,
        tuple[
            CandidateSimulationN5InputV5,
            Any,
            ArtifactRef,
            N4CandidateScenarioProposalCandidate,
            DesignProblem,
        ],
    ] = {}
    value_observations: dict[str, tuple[str, Any]] = {}
    active_job_id: list[str | None] = [None]
    active_case: list[str] = ["normal"]
    original_n5_call = JointSimulationPort.__call__

    def observe_n5_call(
        port: JointSimulationPort,
        *,
        candidate: N4CandidateScenarioProposalCandidate,
        problem: DesignProblem,
        cycle_index: int,
        **kwargs: Any,
    ) -> Any:
        observation = original_n5_call(
            port,
            candidate=candidate,
            problem=problem,
            cycle_index=cycle_index,
            **kwargs,
        )
        input_record = kwargs.get("candidate_simulation_input")
        input_ref = kwargs.get("candidate_simulation_input_ref")
        if input_record is not None:
            assert type(input_record) is CandidateSimulationN5InputV5
            assert isinstance(input_ref, ArtifactRef)
            assert type(candidate) is N4CandidateScenarioProposalCandidate
            assert type(problem) is DesignProblem
            # The real compiler adds trusted runtime provenance. Compare its
            # full semantic selection, not fixture-owned runtime identity.
            assert problem.nl_provenance.raw_request == raw_request
            assert problem.outcome_of_interest == recorded_problem.outcome_of_interest
            assert problem.constraints == recorded_problem.constraints
            assert problem.candidate_lever_space == recorded_problem.candidate_lever_space
            assert cycle_job_profile_selection_ref(problem) == profile.profile_selection_ref
            assert candidate.status == "candidate_unverified"
            assert candidate.atom.operator_kind.trinity_kind == "tax_relief_rate"
            assert candidate.atom.target_world_slots == ("global.tax_rate",)
            assert candidate.atom.causal_do_expr.write_variables == ("global.tax_rate",)
            assert candidate.atom.direct_effect_bundle.params == {"rate": 0}
            materialization = input_record.materialization
            assert materialization.operator_kind == "tax_relief_rate"
            assert materialization.parameter_id == "rate"
            assert materialization.value == 0
            assert materialization.target_world_slot == "global.tax_rate"
            assert materialization.unit_id == "ratio"
            assert materialization.outcome_variable == "government.balance"
            assert materialization.derived_n5_atom.target_world_slots == ("global.tax_rate",)
            assert materialization.derived_n5_atom.causal_do_expr.write_variables == (
                "global.tax_rate",
            )
            assert materialization.derived_n5_atom.direct_effect_bundle.params == {"rate": 0}
            assert input_record.outcome_variable == problem.outcome_of_interest.target_variable
            n5_port_calls[input_record.job_id] = (
                input_record,
                observation,
                input_ref,
                candidate,
                problem,
            )
        return observation

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_n5_call)

    original_value_observer = generation_cycle_module._configured_candidate_value_observation
    original_cause = RuntimeError("controlled original N5 value-cause witness")

    class HostileGenerationCycleError(GenerationCycleError):
        """Keep public failure facts readable while denying private metadata hooks."""

        def __getattribute__(self, name: str) -> Any:
            if name == "__dict__" or name.startswith("_polisyos"):
                raise AttributeError("private generation-cycle metadata is inaccessible")
            return super().__getattribute__(name)

        def __setattr__(self, name: str, value: Any) -> None:
            if name.startswith("_polisyos"):
                raise AttributeError("private generation-cycle metadata is immutable")
            super().__setattr__(name, value)

        def __delattr__(self, name: str) -> None:
            if name.startswith("_polisyos"):
                raise AttributeError("private generation-cycle metadata is immutable")
            super().__delattr__(name)

    late_failure = HostileGenerationCycleError(
        "res03.configured_candidate_late_value_failure",
        "controlled failure after real N5 persistence",
    )
    assert isinstance(late_failure, GenerationCycleError)
    assert type(late_failure) is HostileGenerationCycleError
    assert late_failure.args == (
        "res03.configured_candidate_late_value_failure: controlled failure after real N5 persistence",
    )
    assert late_failure.code == "res03.configured_candidate_late_value_failure"
    assert str(late_failure) == (
        "res03.configured_candidate_late_value_failure: controlled failure after real N5 persistence"
    )
    private_packet_attribute = "_polisyos_generation_cycle_completed_n5"
    private_dict_attribute = "__dict__"
    with pytest.raises(AttributeError, match="private generation-cycle metadata"):
        getattr(late_failure, private_dict_attribute)
    with pytest.raises(AttributeError, match="private generation-cycle metadata"):
        getattr(late_failure, private_packet_attribute)
    with pytest.raises(AttributeError, match="private generation-cycle metadata"):
        setattr(late_failure, private_packet_attribute, object())
    with pytest.raises(AttributeError, match="private generation-cycle metadata"):
        delattr(late_failure, private_packet_attribute)

    def observe_or_fail_value(candidate_id: str, simulation: Any) -> Any:
        job_id = active_job_id[0]
        assert job_id is not None
        if simulation.status == "joint_simulated":
            assert job_id in n5_port_calls
            input_record, _port_observation, port_input_ref, _candidate, _problem = n5_port_calls[
                job_id
            ]
            assert candidate_id == input_record.original_candidate_id
            assert (
                port_input_ref.artifact_id
                == ArtifactRef.model_validate(
                    simulation.diagnostics["candidate_simulation_n5_input_selected_ref"]
                ).artifact_id
            )
            assert simulation.simulation_result_ref is not None
            assert simulation.diagnostics.get("candidate_simulation_execution_selected_ref")
            value_observations[job_id] = (active_case[0], simulation)
            if active_case[0] == "late_failure":
                raise late_failure from original_cause
        return original_value_observer(candidate_id, simulation)

    monkeypatch.setattr(
        generation_cycle_module,
        "_configured_candidate_value_observation",
        observe_or_fail_value,
    )

    recursive_errors: list[Exception] = []
    original_recursive_run = RecursiveGenerationCycleController.run

    async def preserve_recursive_error(controller: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await original_recursive_run(controller, *args, **kwargs)
        except Exception as exc:
            if active_case[0] == "late_failure":
                recursive_errors.append(exc)
            raise

    monkeypatch.setattr(RecursiveGenerationCycleController, "run", preserve_recursive_error)

    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        gateway_holder[0] = gateway
        gateway.set_fixture(
            controlled_recording,
            problem=recorded_problem,
            provider_profile=normal_provider_profile,
        )
        app = create_runtime_api_app(
            cas_root=normal_cas_root,
            repo_root=source_inputs.root,
            container_overrides=RuntimeContainerOverrides(runtime_api_context=normal_api_context),
            allow_fixture_identity=True,
            candidate_simulation_profiles=(profile,),
            candidate_simulation_model_declarations=(model_declaration,),
        )
        with TestClient(app) as client:
            service = app.state._control_service

            def submit_and_dispatch(
                active_client: Any,
                active_service: Any,
                idempotency_key: str,
            ) -> Any:
                response = active_client.post(
                    "/api/v1/control/runs/nl",
                    headers={"Idempotency-Key": idempotency_key},
                    json={
                        "request": raw_request,
                        "llm_model": model_id,
                        "context": {
                            "evaluation_safety_attempt": _valid_intake_for_mode(
                                "simulate_only"
                            ).model_dump(mode="json")
                        },
                    },
                )
                assert response.status_code == 200, response.text
                accepted = response.json()
                assert accepted["status"] == "accepted"
                active_job_id[0] = accepted["job_id"]
                dispatched = dispatch_one_control_job(
                    store=active_service._control_store,
                    handler=active_service._process_control_job,
                    expected_job_id=accepted["job_id"],
                )
                assert dispatched == accepted["job_id"]
                job = active_service._control_store.get_job(accepted["job_id"])
                assert job is not None
                return job

            def assert_real_engine_work(result: Any) -> None:
                assert result.diagnostics.get("engine_run_claimed") is True
                assert any(decision.decision == "selected" for decision in result.engine_decisions)
                assert result.trajectories
                assert all(trajectory.points for trajectory in result.trajectories)
                assert any(
                    point.outcomes and point.effect
                    for trajectory in result.trajectories
                    for point in trajectory.points
                )
                work = result.physical_work_observations
                assert result.diagnostics["physical_work_capture_status"] == "observed"
                assert work
                assert result.diagnostics["physical_work_units"] == len(work)
                assert sum(item.work_units for item in work) > 0
                assert all(item.status == "completed" for item in work)

            normal_job = submit_and_dispatch(
                client,
                service,
                "res03-configured-normal-1d697b0e0f8e43a5b91d21fc7a571d26",
            )
            assert normal_job.state == "completed", {
                "state": normal_job.state,
                "error_message": normal_job.error_message,
                "run_id": normal_job.run_id,
                "compiled_problem_count": len(compiled_problems),
                "n5_job_ids": sorted(n5_port_calls),
            }
            assert normal_job.run_id is not None
            assert len(compiled_problems) == 1
            assert type(compiled_problems[0]) is DesignProblem
            assert cycle_job_profile_selection_ref(compiled_problems[0]) == (
                cycle_job_profile_selection_ref(recorded_problem)
            )
            assert compiled_problems[0].nl_provenance.raw_request == raw_request
            assert normal_job.job_id in value_observations
            normal_case, normal_simulation = value_observations[normal_job.job_id]
            assert normal_case == "normal"
            assert normal_simulation.status == "joint_simulated"
            assert normal_simulation.simulation_result_ref is not None
            normal_input_record = n5_port_calls[normal_job.job_id][0]
            normal_result_ref = ArtifactRef.model_validate(
                normal_simulation.simulation_result_ref.model_dump(mode="json")
            )
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                normal_result = load_joint_simulation_result(
                    normal_result_ref,
                    store=service._artifact_store,
                    expected_world_model_record_content_hash=(
                        normal_input_record.materialization.world_model_record_hash
                    ),
                    expected_atom_ids=(
                        normal_input_record.materialization.derived_n5_atom.intervention_id,
                    ),
                )
            assert_real_engine_work(normal_result)
            failure_cas_root = tmp_path / ".polisyos-late-failure"
            assert failure_cas_root != normal_cas_root
            monkeypatch.setenv(
                "POLISYOS_CONTROL_SQLITE_PATH",
                (tmp_path / "control-late-failure.sqlite3").as_posix(),
            )
            failure_api_context = build_runtime_api_context(
                cas_root=failure_cas_root,
                core_runs_root=failure_cas_root / "runs",
            )
            failure_profile, failure_model_declaration = build_profile(
                failure_api_context.store,
                tmp_path / "failure-profile",
            )
            failure_provider_profile = synthetic_controlled_candidate_provider_profile(
                recording,
                controlled_recording,
                problem=recorded_problem,
                evidence_root=tmp_path / "failure-provider-exchanges",
            )
            failure_app = create_runtime_api_app(
                cas_root=failure_cas_root,
                repo_root=source_inputs.root,
                container_overrides=RuntimeContainerOverrides(
                    runtime_api_context=failure_api_context
                ),
                allow_fixture_identity=True,
                candidate_simulation_profiles=(failure_profile,),
                candidate_simulation_model_declarations=(failure_model_declaration,),
            )
            with TestClient(failure_app) as failure_client:
                failure_service = failure_app.state._control_service
                active_case[0] = "late_failure"
                gateway.set_fixture(
                    controlled_recording,
                    problem=recorded_problem,
                    provider_profile=failure_provider_profile,
                )
                failed_job = submit_and_dispatch(
                    failure_client,
                    failure_service,
                    "res03-configured-late-failure-305a3fe297ae4c03b06ce8b59c82f0ac",
                )
                assert failed_job.state == "failed"
                assert failed_job.job_id != normal_job.job_id
                assert failed_job.run_id != normal_job.run_id
                assert failed_job.run_id is not None
                assert failed_job.error_message == str(late_failure)
                assert isinstance(late_failure, GenerationCycleError)
                assert type(late_failure) is HostileGenerationCycleError
                assert recursive_errors == [late_failure]
                assert recursive_errors[0] is late_failure
                assert recursive_errors[0].__cause__ is original_cause
                assert failed_job.job_id in value_observations
                assert preservation_attempts == [late_failure]
                assert preservation_attempts[0] is late_failure
                assert not preservation_errors, preservation_errors
                assert len(compiled_problems) == 2
                assert type(compiled_problems[1]) is DesignProblem
                assert cycle_job_profile_selection_ref(compiled_problems[1]) == (
                    cycle_job_profile_selection_ref(recorded_problem)
                )
                assert compiled_problems[1].nl_provenance.raw_request == raw_request
                failed_case, failed_simulation = value_observations[failed_job.job_id]
                assert failed_case == "late_failure"
                assert failed_simulation.status == "joint_simulated"
                assert failed_simulation.simulation_result_ref is not None

                input_record, _port_observation, port_input_ref, _candidate, _problem = (
                    n5_port_calls[failed_job.job_id]
                )
                assert type(input_record) is CandidateSimulationN5InputV5
                assert input_record.job_id == failed_job.job_id
                assert input_record.run_id == failed_job.run_id
                assert input_record.tenant_id == tenant_id
                assert input_record.cell_id == cell_id
                assert input_record.context_job_ref.manifest_profile_sha256 is None
                input_ref = ArtifactRef.model_validate(
                    failed_simulation.diagnostics["candidate_simulation_n5_input_selected_ref"]
                )
                execution_ref = ArtifactRef.model_validate(
                    failed_simulation.diagnostics["candidate_simulation_execution_selected_ref"]
                )
                result_ref = ArtifactRef.model_validate(
                    failed_simulation.simulation_result_ref.model_dump(mode="json")
                )
                assert input_ref == port_input_ref
                assert input_ref.kind == "runtime.quality.candidate_simulation_n5_input"
                assert input_ref.manifest_profile_sha256 is not None
                assert input_record.n4_source_ref.kind == (
                    "runtime.quality.n4_candidate_scenario_source"
                )
                assert execution_ref.kind == "runtime.quality.candidate_simulation_execution"
                assert execution_ref.manifest_profile_sha256 is not None
                assert result_ref.kind == "polisyos.runtime.joint_simulation_result"
                assert result_ref.manifest_profile_sha256 is not None

                created_event = failure_service._control_store.get_job_created_event_payload(
                    failed_job.job_id
                )
                scope = _control_job_execution_scope_from_event(created_event)
                assert scope.status == "established"
                assert scope.tenant_id is not None and scope.cell_id is not None
                assert (scope.tenant_id, scope.cell_id) == (tenant_id, cell_id)
                assert created_event["run_id"] == failed_job.run_id
                with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
                    repository = GenerationSourceRepository(failure_service._artifact_store)
                    persisted_input = repository.resolve_candidate_simulation_v5(
                        ref=input_ref,
                        expected_run_id=failed_job.run_id,
                        expected_job_id=failed_job.job_id,
                        expected_tenant_id=scope.tenant_id,
                        expected_cell_id=scope.cell_id,
                    )
                    persisted_execution = repository.resolve_candidate_simulation_v5(
                        ref=execution_ref,
                        expected_run_id=failed_job.run_id,
                        expected_job_id=failed_job.job_id,
                        expected_tenant_id=scope.tenant_id,
                        expected_cell_id=scope.cell_id,
                    )
                    assert type(persisted_input) is CandidateSimulationN5InputV5
                    assert persisted_input == input_record
                    assert type(persisted_execution) is CandidateSimulationExecutionV5
                    assert persisted_execution.n5_input_ref == input_ref
                    assert persisted_execution.n4_source_ref == input_record.n4_source_ref
                    assert persisted_execution.n5_result_ref == result_ref
                    selected_source = repository.load_candidate_scenario_source_for_n5(
                        persisted_input.n4_source_ref,
                        expected_run_id=failed_job.run_id,
                        expected_job_id=failed_job.job_id,
                        expected_tenant_id=scope.tenant_id,
                        expected_cell_id=scope.cell_id,
                    )
                    assert type(selected_source) is N4CandidateScenarioSourceRecordV3
                    selected_candidate = n5_port_calls[failed_job.job_id][3]
                    assert selected_source.status == "candidate_unverified"
                    assert selected_source.n9_status == "not_admitted"
                    assert selected_source.s8_status == "blocked"
                    assert selected_source.problem == compiled_problems[1]
                    assert n5_port_calls[failed_job.job_id][4] == compiled_problems[1]
                    assert selected_source.profile == failure_profile
                    assert selected_source.candidate == selected_candidate
                    assert selected_source.candidate.atom.status == "candidate_unverified"
                    assert selected_source.candidate.atom.target_world_slots == ("global.tax_rate",)
                    assert selected_source.candidate.atom.causal_do_expr.write_variables == (
                        "global.tax_rate",
                    )
                    source_interventions = tuple(
                        intervention
                        for intervention in selected_source.proposal.trinity_bundle.policy_spec.interventions
                        if intervention.intervention_id == selected_candidate.intervention_id
                    )
                    assert len(source_interventions) == 1
                    assert source_interventions[0].kind == "tax_relief_rate"
                    assert source_interventions[0].params == {"rate": 0}
                    assert (
                        selected_source.candidate.atom.direct_effect_bundle.params
                        == source_interventions[0].params
                    )
                    context_job = CycleSubstrateContextArtifactOwner(
                        store=failure_service._artifact_store
                    ).resolve_historical_job_artifact(
                        persisted_input.context_job_ref,
                        problem=selected_source.problem,
                        expected_run_id=failed_job.run_id,
                        expected_job_id=failed_job.job_id,
                        expected_tenant_id=scope.tenant_id,
                        expected_cell_id=scope.cell_id,
                    )
                    assert context_job.context.world_model_record.content_hash == (
                        input_record.materialization.world_model_record_hash
                    )
                    result_bytes = failure_service._artifact_store.get_bytes(result_ref)
                    loaded_result = load_joint_simulation_result(
                        result_ref,
                        store=failure_service._artifact_store,
                        expected_world_model_record_content_hash=(
                            input_record.materialization.world_model_record_hash
                        ),
                        expected_atom_ids=(
                            input_record.materialization.derived_n5_atom.intervention_id,
                        ),
                    )
                assert str(result_ref.artifact_id) == (
                    "sha256:" + hashlib.sha256(result_bytes).hexdigest()
                )
                assert loaded_result.receipt.payload_hash == (
                    persisted_execution.n5_result_content_hash
                )
                assert_real_engine_work(loaded_result)

        # DA-01 joins this exact partial configured result to CYC's canonical
        # conditional N8 in another interpreter. No compiler, N5 producer,
        # worker callback or successful cycle object is inherited by the child.
        handoff = {
            "project_root": str(repo_root),
            "cas_root": str(failure_cas_root),
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "run_id": failed_job.run_id,
            "job_id": failed_job.job_id,
            "problem_id": compiled_problems[1].design_problem_id,
            "cycle_index": 0,
            "simulation": failed_simulation.model_dump(mode="json"),
            "selected_refs": {
                "input": input_ref.model_dump(mode="json"),
                "execution": execution_ref.model_dump(mode="json"),
                "source": persisted_input.n4_source_ref.model_dump(mode="json"),
                "context": persisted_input.context_job_ref.model_dump(mode="json"),
                "result": result_ref.model_dump(mode="json"),
            },
            "result_sha256": "sha256:" + hashlib.sha256(result_bytes).hexdigest(),
        }
        child_environment = dict(os.environ)
        child_environment["PYTHONPATH"] = os.pathsep.join((str(repo_root / "src"), str(repo_root)))
        child_environment["PYTHONDONTWRITEBYTECODE"] = "1"
        for thread_setting in (
            "JAX_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        ):
            child_environment[thread_setting] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                "import json,sys; "
                "from tests.unit.remediation.test_res_03 import "
                "_read_retained_configured_n5_in_fresh_process; "
                "print(json.dumps(_read_retained_configured_n5_in_fresh_process("
                "json.load(sys.stdin)),sort_keys=True,separators=(',',':')))",
            ],
            cwd=repo_root,
            env=child_environment,
            input=json.dumps(handoff),
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
        fresh_n8 = json.loads(completed.stdout.splitlines()[-1])
        assert fresh_n8["consumer_pid"] != os.getpid()
        assert fresh_n8["selected_refs"] == handoff["selected_refs"]
        assert fresh_n8["result_sha256"] == handoff["result_sha256"]
        assert fresh_n8["input_content_hash"] == persisted_input.content_hash
        assert fresh_n8["execution_content_hash"] == persisted_execution.content_hash
        assert fresh_n8["receipt_payload_hash"] == loaded_result.receipt.payload_hash
        assert fresh_n8["outcome_unit_id"] == failure_model_declaration.outcome_unit_id
        assert fresh_n8[
            "model_declaration_ref"
        ] == persisted_input.model_declaration_ref.model_dump(mode="json")
        assert fresh_n8["ncm_ref"] == persisted_input.ncm_ref.model_dump(mode="json")
        assert fresh_n8["trajectories"] == [
            trajectory.model_dump(mode="json") for trajectory in loaded_result.trajectories
        ]
        for label in ("positive", "restored"):
            observation = fresh_n8[label]
            assert observation["status"] == "value_conditional", observation
            assert observation["value_ref"] == str(result_ref.artifact_id)
            assert observation["evaluation_mode"] == "simulate_only"
            assert observation["decision_grade"] == "low"
            assert observation["value_receipt"] is None
            assert observation["method_selection_receipt"] is None
            assert set(failed_simulation.authority_blockers).issubset(
                observation["authority_blockers"]
            )
            assert "simulation_only_k_sim_not_world_evidence" in observation["authority_blockers"]
        assert fresh_n8["wrong_world"]["status"] == "value_blocked"
        assert fresh_n8["wrong_world"]["authority_blockers"] == [
            "joint_simulation_result_wmr_mismatch"
        ]
        assert fresh_n8["missing_result"]["status"] == "value_blocked"
        assert fresh_n8["missing_result"]["value_ref"] is None

        # Reopen the failed CAS and control database through a fresh API context.
        fresh_context = build_runtime_api_context(
            cas_root=failure_cas_root,
            core_runs_root=failure_cas_root / "runs",
        )
        fresh_app = create_runtime_api_app(
            cas_root=failure_cas_root,
            repo_root=source_inputs.root,
            container_overrides=RuntimeContainerOverrides(runtime_api_context=fresh_context),
            allow_fixture_identity=True,
            candidate_simulation_profiles=(failure_profile,),
            candidate_simulation_model_declarations=(failure_model_declaration,),
        )
        with (
            tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id),
            TestClient(fresh_app) as fresh_reader,
        ):
            job_response = fresh_reader.get(f"/api/v1/control/jobs/{failed_job.job_id}")
            assert job_response.status_code == 200, job_response.text
            job_view = ControlJobResponse.model_validate(job_response.json())
            assert job_view.job_id == failed_job.job_id
            assert job_view.state == "failed"
            assert job_view.error_message == str(late_failure)
            assert isinstance(late_failure, GenerationCycleError)
            assert type(late_failure) is HostileGenerationCycleError
            assert recursive_errors == [late_failure]
            assert recursive_errors[0] is late_failure
            assert recursive_errors[0].__cause__ is original_cause
            assert job_view.progress["state"] == "failed"
            assert job_view.progress["authority_result"] == "candidate_only"
            assert job_view.progress["core_terminal_status"] == "error"
            assert job_view.progress["failure"] == {
                "code": late_failure.code,
                "exception_type": type(late_failure).__name__,
                "message": str(late_failure),
                "layer": "generation_cycle",
                "phase": "value_projection",
                "run_id": failed_job.run_id,
                "job_id": failed_job.job_id,
                "attempt": failed_job.attempt,
            }
            partial_candidate_simulation = job_view.progress["partial_candidate_simulation"]
            assert partial_candidate_simulation["artifact_status"] == "resolved"
            assert partial_candidate_simulation["authority_purpose"] == "candidate_scenario_n5_only"
            assert partial_candidate_simulation["completed_stage"] == "n5_simulation"
            assert partial_candidate_simulation["failed_stage"] == "value_projection"
            assert partial_candidate_simulation["cycle_completed"] is False
            assert partial_candidate_simulation["publication_authority"] is False
            partial_selected_refs = {
                "n5_input_ref": input_ref,
                "execution_ref": execution_ref,
                "n4_source_ref": persisted_input.n4_source_ref,
                "context_job_ref": persisted_input.context_job_ref,
                "simulation_result_ref": result_ref,
            }
            for field_name, expected_ref in partial_selected_refs.items():
                selected_progress_ref = ArtifactRef.model_validate(
                    partial_candidate_simulation[field_name]
                )
                assert selected_progress_ref == expected_ref
                if field_name == "context_job_ref":
                    assert selected_progress_ref.manifest_profile_sha256 is None
                else:
                    assert selected_progress_ref.manifest_profile_sha256 is not None
            assert not {
                "compiled_recursive_generation_cycle_ref",
                "candidate_simulation_n5_input_ref",
                "candidate_simulation_execution_ref",
                "simulation_result_ref",
            }.intersection(job_view.progress)

            core_run_response = fresh_reader.get(
                f"/api/v1/runs/{failed_job.progress['core_run_id']}"
            )
            assert core_run_response.status_code == 200, core_run_response.text
            failed_run_view = RunDetailsResponse.model_validate_json(core_run_response.content)
            assert failed_run_view.run.run_id == failed_job.progress["core_run_id"]
            assert failed_run_view.run.control_job_id == failed_job.job_id
            assert failed_run_view.run.status == "error"
            core_selected_refs = (
                execution_ref,
                input_ref,
                persisted_input.n4_source_ref,
                result_ref,
            )
            assert all(
                ref in failed_run_view.run.root_artifacts
                and ref.manifest_profile_sha256 is not None
                for ref in core_selected_refs
            )
            assert all(
                ref.kind != "runtime.compiled_recursive_generation_cycle"
                for ref in failed_run_view.run.root_artifacts
            )
            failed_candidate_projection = failed_run_view.run.candidate_simulation
            assert failed_candidate_projection is not None
            assert failed_candidate_projection.publication_authority is False
            failed_n5_observation = next(
                row
                for row in failed_candidate_projection.n5_observations
                if row.simulation_result_ref == result_ref
            )
            assert failed_n5_observation.cycle_index == partial_candidate_simulation["cycle_index"]
            assert failed_n5_observation.status == "joint_simulated"
            assert failed_n5_observation.n5_input_ref == input_ref
            assert failed_n5_observation.result_body_status == "resolved"
            assert failed_n5_observation.result_body_limitation_code is None
            public_result_body = failed_n5_observation.result_body
            assert public_result_body is not None
            assert public_result_body.artifact_ref == result_ref
            assert (
                public_result_body.selected_manifest_profile_sha256
                == result_ref.manifest_profile_sha256
            )
            assert public_result_body.world_model_record_ref == loaded_result.world_model_record_ref
            assert (
                public_result_body.world_model_record_content_hash
                == loaded_result.world_model_record_content_hash
            )
            assert public_result_body.atom_ids == loaded_result.atom_ids
            assert public_result_body.selected_outcomes == loaded_result.selected_outcomes
            assert public_result_body.uncertainty_kind == loaded_result.uncertainty_kind
            assert public_result_body.authority_purpose == "candidate_scenario_n5_only"
            assert public_result_body.candidate_status == "candidate_unverified"
            assert public_result_body.currentness_status == "not_established"
            assert public_result_body.publication_authority is False
            assert (
                public_result_body.horizon.start,
                public_result_body.horizon.end,
                public_result_body.horizon.step,
                public_result_body.horizon.valid_time_role,
                public_result_body.horizon.transaction_time_role,
                public_result_body.horizon.scenario_branch_policy,
            ) == (
                loaded_result.horizon.start,
                loaded_result.horizon.end,
                loaded_result.horizon.step,
                loaded_result.horizon.valid_time_role,
                loaded_result.horizon.transaction_time_role,
                loaded_result.horizon.scenario_branch_policy,
            )
            assert len(public_result_body.trajectories) == len(loaded_result.trajectories)
            for public_trajectory, stored_trajectory in zip(
                public_result_body.trajectories,
                loaded_result.trajectories,
                strict=True,
            ):
                assert public_trajectory.run_level == stored_trajectory.run_level
                assert public_trajectory.atom_ids == stored_trajectory.atom_ids
                assert tuple(
                    (point.step, point.outcomes, point.effects)
                    for point in public_trajectory.points
                ) == tuple(
                    (point.step, point.outcomes, point.effect) for point in stored_trajectory.points
                )

            artifact_response = fresh_reader.get(
                f"/api/v1/artifacts/{result_ref.artifact_id}/content",
                params={"manifest_profile_sha256": result_ref.manifest_profile_sha256},
                headers={"Accept": "application/octet-stream"},
            )
            assert artifact_response.status_code == 409, artifact_response.text
            artifact_problem = RuntimeApiProblem.model_validate(artifact_response.json())
            assert artifact_problem.code == "authority_surface_admission_blocked"
            assert artifact_problem.extensions is not None
            raw_authority_decision = artifact_problem.extensions["authority_surface_decision"]
            assert raw_authority_decision["surface"] == "artifact"
            assert raw_authority_decision["purpose"] == "runtime_closeout_authority"
            assert raw_authority_decision["reason"] == "authority_surface_signal_missing"
            assert raw_authority_decision["blocking"] is True
            assert raw_authority_decision["visible_downgrade"] is True
            assert raw_authority_decision["integrity_status"] == "verified"
            assert raw_authority_decision["integrity_error"] is None
            assert raw_authority_decision["secret_pii_finding_kinds"] == []
            assert raw_authority_decision["time_source_dispositions"] == []
            assert raw_authority_decision["s12_issue_codes"] == []
            assert raw_authority_decision["candidate_firewall_issue_codes"] == []
            assert raw_authority_decision["authority_contributors"] == [
                {
                    "basis": "base_surface",
                    "status": "blocked",
                    "authority_result": "not_applicable",
                    "transition_disposition": None,
                    "authority_boundary_ref": None,
                    "consumed_authority_boundary": False,
                    "may_not_use_for": [],
                    "reason": "authority_surface_signal_missing",
                    "blocking": True,
                    "visible_downgrade": True,
                    "resolution_error": None,
                }
            ]

            wrong_profile_sha256 = execution_ref.manifest_profile_sha256
            assert wrong_profile_sha256 is not None
            assert wrong_profile_sha256 != result_ref.manifest_profile_sha256
            wrong_profile_response = fresh_reader.get(
                f"/api/v1/artifacts/{result_ref.artifact_id}/content",
                params={"manifest_profile_sha256": wrong_profile_sha256},
                headers={"Accept": "application/octet-stream"},
            )
            assert wrong_profile_response.status_code == 404, wrong_profile_response.text
            wrong_profile_problem = RuntimeApiProblem.model_validate(wrong_profile_response.json())
            assert wrong_profile_problem.code == "artifact_manifest_profile_not_found"

            owner_claims = build_fixture_identity_claims()
            wrong_tenant_claims_payload = owner_claims.model_dump(mode="python")
            wrong_tenant_claims_payload.update(
                {
                    "sub": "fixture-other-tenant-analyst",
                    "email": "fixture-other-tenant@polisyos.local",
                    "tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "cell_id": "cell-b",
                    "jti": "fixture-other-tenant-jti",
                }
            )
            wrong_tenant_claims = type(owner_claims).model_validate(wrong_tenant_claims_payload)
            with monkeypatch.context() as wrong_tenant_identity:
                wrong_tenant_identity.setattr(
                    dev_identity_middleware,
                    "build_fixture_identity_claims",
                    lambda: wrong_tenant_claims,
                )
                wrong_tenant_response = fresh_reader.get(
                    f"/api/v1/artifacts/{result_ref.artifact_id}/content",
                    params={"manifest_profile_sha256": result_ref.manifest_profile_sha256},
                    headers={"Accept": "application/octet-stream"},
                )
            assert wrong_tenant_response.status_code == 403, wrong_tenant_response.text
            wrong_tenant_problem = RuntimeApiProblem.model_validate(wrong_tenant_response.json())
            assert wrong_tenant_problem.code == "artifact_tenant_mismatch"

            # Check the successful public projection only after the late-fault
            # bytes and successful selected-view read have been characterized.
            normal_fresh_context = build_runtime_api_context(
                cas_root=normal_cas_root,
                core_runs_root=normal_cas_root / "runs",
            )
            normal_fresh_app = create_runtime_api_app(
                cas_root=normal_cas_root,
                repo_root=source_inputs.root,
                container_overrides=RuntimeContainerOverrides(
                    runtime_api_context=normal_fresh_context
                ),
                allow_fixture_identity=True,
                candidate_simulation_profiles=(profile,),
                candidate_simulation_model_declarations=(model_declaration,),
            )
            with (
                tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
                TestClient(normal_fresh_app) as normal_reader,
            ):
                normal_details = normal_reader.get(
                    f"/api/v1/runs/{normal_job.progress['core_run_id']}"
                )
            assert normal_details.status_code == 200, normal_details.text
            normal_run_view = RunDetailsResponse.model_validate_json(normal_details.content)
            normal_candidate_projection = normal_run_view.run.candidate_simulation
            assert normal_candidate_projection is not None
            assert normal_candidate_projection.artifact_status == "resolved"
            assert normal_candidate_projection.publication_authority is False
            assert normal_candidate_projection.run_id == normal_job.progress["core_run_id"]
            assert any(
                row.status == "joint_simulated"
                and row.simulation_result_ref is not None
                and str(row.simulation_result_ref.artifact_id)
                == str(normal_simulation.simulation_result_ref.artifact_id)
                for row in normal_candidate_projection.n5_observations
            )
            failure_work = loaded_result.physical_work_observations
            witness_diagnostic = loaded_result.diagnostics.get(
                "n5_execution_implementation_witness"
            )
            implementation_witness = None
            if isinstance(witness_diagnostic, Mapping):
                implementation_witness = {
                    "comparison_scope": witness_diagnostic.get("comparison_scope"),
                    "predicate_provenance": witness_diagnostic.get("predicate_provenance"),
                    "reason_codes": witness_diagnostic.get("reason_codes"),
                }
            diagnostic = {
                "schema": "res03.same_leaf_native_n5_late_value_failure.v1",
                "normal": {
                    "job_id": normal_job.job_id,
                    "run_id": normal_job.run_id,
                    "core_run_id": normal_job.progress["core_run_id"],
                    "n5_input_ref": n5_port_calls[normal_job.job_id][2].model_dump(mode="json"),
                    "result_ref": normal_result_ref.model_dump(mode="json"),
                    "trajectory_count": len(normal_result.trajectories),
                    "physical_work_units": normal_result.diagnostics["physical_work_units"],
                    "projection": {
                        "http_status": normal_details.status_code,
                        "run_id": normal_candidate_projection.run_id,
                        "artifact_status": normal_candidate_projection.artifact_status,
                        "publication_authority": normal_candidate_projection.publication_authority,
                    },
                },
                "late_failure": {
                    "job_id": failed_job.job_id,
                    "run_id": failed_job.run_id,
                    "core_run_id": failed_job.progress.get("core_run_id"),
                    "selected_refs": {
                        "n5_input": input_ref.model_dump(mode="json"),
                        "n4_source": persisted_input.n4_source_ref.model_dump(mode="json"),
                        "context_job": persisted_input.context_job_ref.model_dump(mode="json"),
                        "execution": execution_ref.model_dump(mode="json"),
                        "result": result_ref.model_dump(mode="json"),
                    },
                    "content": {
                        "byte_length": len(result_bytes),
                        "sha256": "sha256:" + hashlib.sha256(result_bytes).hexdigest(),
                        "artifact_id": str(result_ref.artifact_id),
                        "input_content_hash": persisted_input.content_hash,
                        "execution_content_hash": persisted_execution.content_hash,
                        "execution_result_content_hash": persisted_execution.n5_result_content_hash,
                        "receipt_payload_hash": loaded_result.receipt.payload_hash,
                    },
                    "trajectory_count": len(loaded_result.trajectories),
                    "physical_work": {
                        "capture_status": loaded_result.diagnostics["physical_work_capture_status"],
                        "observation_count": len(failure_work),
                        "units": sum(item.work_units for item in failure_work),
                    },
                    "error": {
                        "type": type(late_failure).__name__,
                        "code": late_failure.code,
                        "string": str(late_failure),
                        "cause_type": type(original_cause).__name__,
                        "implementation_witness": implementation_witness,
                    },
                    "failed_n5_preservation": {
                        "attempt_count": len(preservation_attempts),
                        "exceptions": preservation_errors,
                    },
                    "fresh_job_reader": {
                        "http_status": job_response.status_code,
                        "state": job_view.state,
                        "error_message": job_view.error_message,
                    },
                    "core_run_reader": {
                        "http_status": core_run_response.status_code,
                        "run_id": failed_run_view.run.run_id,
                        "terminal_status": failed_run_view.run.status,
                        "linked_selected_ref_count": len(core_selected_refs),
                        "numeric_result_body": {
                            "status": failed_n5_observation.result_body_status,
                            "limitation_code": failed_n5_observation.result_body_limitation_code,
                            "body": public_result_body.model_dump(mode="json"),
                        },
                    },
                    "fresh_artifact_reader": {
                        "http_status": artifact_response.status_code,
                        "code": artifact_problem.code,
                        "purpose": raw_authority_decision["purpose"],
                        "reason": raw_authority_decision["reason"],
                    },
                    "wrong_profile_reader": {
                        "http_status": wrong_profile_response.status_code,
                        "code": wrong_profile_problem.code,
                    },
                    "wrong_tenant_reader": {
                        "http_status": wrong_tenant_response.status_code,
                        "code": wrong_tenant_problem.code,
                    },
                    "execution_scope": {
                        "tenant_id": scope.tenant_id,
                        "cell_id": scope.cell_id,
                    },
                    "fresh_process_conditional_n8": fresh_n8,
                },
            }
            record_property(
                "res03_same_leaf_native_characterization",
                json.dumps(diagnostic, sort_keys=True, separators=(",", ":")),
            )


@pytest.mark.integration
def test_da01_late_fault_n5_reaches_fresh_terminal_source_and_conditional_reader(tmp_path) -> None:
    """A real failed leaf crosses terminal/source heads into fresh limited CYC value.

    The unchanged procurement profile's normal counterpart is the CYC02
    cross-process integration regression. This case executes one N5 only and
    injects its fault after that N5's selected CAS publication. It does not run
    the historical tax-profile suite or manufacture a completed cycle.
    """
    from tests.integration.runtime_quality.test_configured_ncm_fresh_process import _child

    produced = _child("produce_late_fault", tmp_path)
    consumed = _child("consume_late_fault", tmp_path, produced)
    _assert_da01_late_fault_projection(produced, consumed)


def _assert_da01_late_fault_projection(produced: dict[str, Any], consumed: dict[str, Any]) -> None:
    """Verify exact failed-source identity and the real limited fresh consumer."""
    import os

    from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key

    assert produced["job_state"] == "failed"
    assert produced["fault_stage"] == "value_projection"
    assert produced["cycle_completed"] is False
    assert produced["fault_code"] == "res03.configured_candidate_late_value_failure"
    assert produced["physical_work_units"] == 2
    assert produced["producer_pid"] != consumed["consumer_pid"] != os.getpid()
    assert consumed["job_state"] == "failed"
    assert consumed["terminal_status"] == "error"
    assert consumed["fault_code"] == produced["fault_code"]
    assert consumed["cycle_completed"] is False
    assert (
        consumed["protected_completed_source_refusal"]
        == "control_job_core_run_source_not_completed"
    )
    assert consumed["witness"] == produced["witness"]
    assert consumed["witness"]["expected_effect"] == 0.5
    assert artifact_ref_identity_key(
        ArtifactRef.model_validate(consumed["terminal_manifest_ref"])
    ) == (artifact_ref_identity_key(ArtifactRef.model_validate(produced["terminal_manifest_ref"])))
    value = consumed["conditional_value"]
    assert value["status"] == "value_conditional"
    assert value["evaluation_mode"] == "simulate_only"
    assert value["decision_grade"] == "low"
    assert value["value_receipt"] is value["method_selection_receipt"] is None
    assert set(produced["witness"]["persisted_blockers"]).issubset(value["authority_blockers"])
    projection = consumed["projection"]
    assert projection["artifact_status"] == "resolved"
    assert projection["cycle_completed"] is projection["publication_authority"] is False
    assert projection["failed_stage"] == "value_projection"
    assert projection["source_ref"] == produced["execution_ref"]
    assert consumed["terminal_selected_outputs_verified"] is True
    assert consumed["no_new_n5"] is True
