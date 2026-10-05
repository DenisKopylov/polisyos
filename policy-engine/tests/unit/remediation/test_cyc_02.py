"""CYC-02 witnesses for durable N5 output and conditional N8 use."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
import polisyos.runtime.quality.recursive_generation_cycle as recursive_generation_cycle_module
from polisyos.core.artifacts import ArtifactRef as CASArtifactRef
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.backends.config import (
    with_ambient_ownership_enforcement_if_supported,
)
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import (
    ArtifactRef as PDCArtifactRef,
)
from polisyos.pdc import (
    SearchTerminalKind,
    SearchTerminalState,
    gy_content_hash,
)
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)
from polisyos.runtime.http.resilience import guard_runtime_cas
from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
from polisyos.runtime.quality.design_axes.coupling_composition import (
    CouplingEdge,
    build_coupling_graph,
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    GenerationCycleError,
    JointSimulationPort,
    JointSimulationRequest,
    PendingN8ValuePort,
    SimulationPortObservation,
    _DefaultSimulationBoundFoundryValuePort,
    load_joint_simulation_result,
    persist_joint_simulation_result,
    simulation_evaluation_input_ref,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    intervention_atom_content_hash,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
    JointSimulationResult,
    build_content_bound_simulation_receipt,
    verify_simulation_receipt,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    _AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES,
    RecursiveCycleBudget,
    RecursiveCycleNode,
    RecursiveGenerationCycleController,
    RecursiveGenerationCycleError,
    RecursiveGenerationCycleRun,
    _is_authenticated_legacy_v1,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.unit.runtime.quality.test_generation_cycle import (
    _cyc01_owner_bound_n5_case,
    _owner_program_graph_n5_witness,
    _problem,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


def test_legacy_recursive_v1_without_n5_cas_ref_reopens_without_new_evidence() -> None:
    """Read the tracked pre-CAS v1 artifact without upgrading its evidence."""

    artifact_path = (
        Path(__file__).resolve().parents[3]
        / "architecture/policy_design_case/layer3_gy_composition_certificates.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))["recursive_runs"][0]
    legacy_hash = payload["content_hash"]

    parsed = RecursiveGenerationCycleRun.model_validate(payload)
    assert parsed.schema_version == "policyos.runtime.recursive_generation_cycle.v1"
    assert parsed.content_hash == legacy_hash
    assert all(node.joint_simulation_ref is None for node in parsed.nodes)

    replayed_payload = parsed.model_dump(mode="json")
    assert replayed_payload["content_hash"] == legacy_hash
    assert all("joint_simulation_ref" not in node for node in replayed_payload["nodes"])

    legacy_parent_index, legacy_parent = next(
        (index, node)
        for index, node in enumerate(payload["nodes"])
        if node["joint_simulation"]
    )
    with pytest.raises(ValueError, match="recursive_simulation_result_requires_cas_ref"):
        RecursiveCycleNode.model_validate(legacy_parent)

    tampered = dict(payload)
    tampered["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="recursive_simulation_result_requires_cas_ref"):
        RecursiveGenerationCycleRun.model_validate(tampered)

    recomputed = json.loads(json.dumps(payload))
    recomputed["run_id"] = "recursive:untrusted-recomputed-v1"
    recomputed["content_hash"] = gy_content_hash(
        {key: value for key, value in recomputed.items() if key != "content_hash"}
    )
    with pytest.raises(ValueError, match="recursive_simulation_result_requires_cas_ref"):
        RecursiveGenerationCycleRun.model_validate(recomputed)

    injected_root = json.loads(json.dumps(payload))
    injected_root["nodes"][legacy_parent_index]["legacy_v1_missing_joint_simulation_ref"] = True
    with pytest.raises(ValueError, match="extra_forbidden"):
        RecursiveGenerationCycleRun.model_validate(injected_root)

    injected_node = dict(legacy_parent)
    injected_node["legacy_v1_missing_joint_simulation_ref"] = True
    with pytest.raises(ValueError, match="extra_forbidden"):
        RecursiveCycleNode.model_validate(injected_node)


def test_legacy_recursive_v1_allowlist_covers_tracked_sources() -> None:
    """Keep the compatibility allowlist bounded to every tracked v1 identity."""

    repo_root = Path(__file__).resolve().parents[3]
    tracked_paths = subprocess.run(
        [
            "git",
            "grep",
            "-l",
            "--fixed-strings",
            "--",
            "policyos.runtime.recursive_generation_cycle.v1",
            "--",
            "*.json",
            "*.jsonl",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    discovered: list[dict[str, object]] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if value.get("schema_version") == "policyos.runtime.recursive_generation_cycle.v1":
                discovered.append(value)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for relative_path in tracked_paths:
        path = repo_root / relative_path
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".jsonl":
            documents = [json.loads(line) for line in source.splitlines() if line.strip()]
        else:
            documents = [json.loads(source)]
        for document in documents:
            collect(document)

    discovered_hashes = {str(item["content_hash"]) for item in discovered}
    assert len(discovered) == 7
    assert discovered_hashes == _AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES
    assert all(_is_authenticated_legacy_v1(item) for item in discovered)

    invalid = json.loads(json.dumps(discovered[0]))
    invalid["run_id"] = "recursive:untrusted-recomputed-v1"
    invalid["content_hash"] = gy_content_hash(
        {key: value for key, value in invalid.items() if key != "content_hash"}
    )
    assert not _is_authenticated_legacy_v1(invalid)


def _real_n5_observation(
    tmp_path: Path,
    *,
    artifact_store: Any | None = None,
    without_runtime_store: bool = False,
    single_step_horizon: bool = False,
):
    """Run the canonical N5 producer through the real generation-cycle adapter."""

    store = (
        None
        if without_runtime_store
        else artifact_store or FileSystemCAS(tmp_path / "n5-runtime-store")
    )

    problem, context, candidate = _cyc01_owner_bound_n5_case()
    request = _request(
        record=context.world_model_record,
        world_model_record_ref=context.world_model_record.world_model_record_id,
    )
    if single_step_horizon:
        # This static request must not add a separate incomplete-horizon blocker.
        request = request.model_copy(
            update={
                "horizon": request.horizon.model_copy(
                    update={"end": request.horizon.start}
                )
            }
        )
    problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "joint_simulation_request": request,
            }
        }
    )
    # The request is an operational hint, but adding it changes the problem
    # envelope hash.  Rebuild only that envelope around the unchanged WMR and
    # registry so the context remains honestly bound to the final problem.
    context = build_cycle_substrate_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        domain=context.domain,
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        world_model_record=context.world_model_record,
        intervention_substrate=context.intervention_substrate,
        candidate_levers=context.candidate_levers,
        transport_context=context.transport_context,
        source_pack_content_hash=context.source_pack_content_hash,
        substrate_input_content_hash=context.substrate_input_content_hash,
    )
    final_problem_ref = context.design_problem_ref
    rebound_atoms = []
    for atom in candidate.intervention_atoms:
        rebound = atom.model_copy(update={"problem_frame_ref": final_problem_ref})
        rebound_atoms.append(
            rebound.model_copy(
                update={"content_hash": intervention_atom_content_hash(rebound)}
            )
        )
    candidate.intervention_atoms = tuple(rebound_atoms)
    candidate.atom = rebound_atoms[0]
    producer = JointSimulationHorizonController()
    produced_results: list[object] = []

    class _RecordingN5Controller:
        def run(self, concrete_request):
            result = producer.run(concrete_request)
            produced_results.append(result)
            return result

    observation = JointSimulationPort(
        controller=_RecordingN5Controller(),
        repo_root=tmp_path,
        cycle_substrate_context=context,
        artifact_store=store,
    )(candidate=candidate, problem=problem, cycle_index=0)
    if without_runtime_store:
        assert observation.status == "simulation_blocked", observation.model_dump(mode="json")
        assert observation.authority_blockers == ("n5_runtime_store_not_established",)
        assert produced_results == []
    else:
        assert observation.status == "joint_simulated", {
            "status": observation.status,
            "authority_blockers": observation.authority_blockers,
            "diagnostics": observation.diagnostics,
        }
        assert "simulation_only_k_sim_not_world_evidence" in observation.authority_blockers
        assert len(produced_results) == 1
    produced_result = produced_results[0] if produced_results else None
    return problem, context, candidate, observation, produced_result, store


class _RecursiveGenerationPort:
    async def __call__(self, problem: object, *, cycle_index: int) -> SimpleNamespace:
        del problem, cycle_index
        atom = SimpleNamespace(
            intervention_id="recursive_leaf_intervention",
            content_hash="sha256:" + "4" * 64,
            status="candidate_unverified",
            world_model_record_ref="world_model_record_recursive_leaf",
            target_world_slots=("firm_survival",),
        )
        candidate = SimpleNamespace(
            candidate_id="candidate_recursive_leaf",
            atom=atom,
            diversity_key=("recursive", "cyc-02", "leaf", "baseline"),
            status="candidate_unverified",
        )
        ranking = SimpleNamespace(
            candidate_id=candidate.candidate_id,
            score=0.2,
            voi_estimate=0.1,
            trust_level="search_guiding",
            promotion_allowed=False,
        )
        return SimpleNamespace(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(ranking,),
            grounding_dispositions=(),
        )


class _RecursiveGroundingPort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> CandidateGroundingObservation:
        del kwargs
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounded_shadow",
            grounding_score=0.2,
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
            current_valid=False,
        )


class _RecursiveSimulationPort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> SimulationPortObservation:
        del candidate, kwargs
        return SimulationPortObservation(
            candidate_id="candidate_recursive_leaf",
            status="simulation_pending_n5",
            authority_blockers=("recursive_leaf_joint_request_not_owned",),
        )


def _recursive_contract_testing_controller(
    repo_root: Path,
    *,
    artifact_store: Any | None = None,
) -> RecursiveGenerationCycleController:
    """Build the contract-testing router with canonical candidate-only leaves."""

    def factory(_node_ref: str, _problem_input: object) -> GenerationCycleController:
        # Keep the canonical default N9 owner but omit its authority runtime.
        # The outer contract-testing router owns parent N5 storage.
        return GenerationCycleController(
            generation_port=_RecursiveGenerationPort(),
            grounding_port=_RecursiveGroundingPort(),
            simulation_port=_RecursiveSimulationPort(),
            value_port=PendingN8ValuePort(),
            authority_scope="production",
            repo_root=repo_root,
        )

    return RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=factory,
        repo_root=repo_root,
        artifact_store=artifact_store,
    )


def _recursive_leaf_terminal() -> SearchTerminalState:
    return SearchTerminalState(
        kind=SearchTerminalKind.GROUNDED_ABSTENTION,
        reason="Terminal emitted by the canonical generation-cycle owner.",
        blocking_obligations=["value_gate_pending_n8"],
    )


def _recursive_subdesigns(
    *,
    parent_ref: str,
    child_refs: tuple[str, str],
) -> tuple[object, ...]:
    from tools.quality.validation.check_layer3_gy_composition_artifacts import (
        _synthetic_composition_subdesigns,
    )

    originals = _synthetic_composition_subdesigns(
        artifact_ref_factory=PDCArtifactRef.from_payload,
    )
    return tuple(
        child.model_copy(
            update={
                "workspace_id": child_ref,
                "parent_workspace_id": parent_ref,
                "search_exit": child.search_exit.model_copy(
                    update={
                        "workspace_id": child_ref,
                        "terminal_state": _recursive_leaf_terminal(),
                    }
                ),
            }
        )
        for child, child_ref in zip(originals, child_refs, strict=True)
    )


def _recursive_parent_request(
    *,
    parent_ref: str,
    child_refs: tuple[str, str],
    problem: object,
    world_model_record: object,
) -> object:
    request = _request(
        record=world_model_record,
        world_model_record_ref=world_model_record.world_model_record_id,
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    rebound_atoms = []
    for atom in request.intervention_atoms:
        rebound = atom.model_copy(update={"problem_frame_ref": problem_ref})
        content_hash = intervention_atom_content_hash(rebound)
        rebound_atoms.append(
            rebound.model_copy(
                update={
                    "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
                    "content_hash": content_hash,
                }
            )
        )
    graph = build_coupling_graph(
        design_ref=parent_ref,
        module_refs=child_refs,
        module_discovery_ref="discovery://cyc-02/recursive-witness",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://cyc-02/recursive-independent",
                source_module_ref=child_refs[0],
                target_module_ref=child_refs[1],
                relation="independent",
                interaction_strength="none",
                feedback_intensity="none",
                evidence_ref="evidence://cyc-02/recursive-independent",
            ),
        ),
        evidence_state="observed",
        rule_version_ref="repo://rules/cyc-02-recursive-cas",
    )
    return request.model_copy(
        update={"intervention_atoms": tuple(rebound_atoms), "coupling_graph": graph}
    )


def test_k_sim_limitation_remains_a_usable_simulation_input(tmp_path: Path) -> None:
    """A complete static N5 result remains an input despite K_sim limits."""

    _problem, _context, _candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path,
        single_step_horizon=True,
    )

    assert set(simulation.authority_blockers) == {
        "simulation_only_k_sim_not_world_evidence"
    }
    assert simulation_evaluation_input_ref(simulation) is None
    input_ref = simulation_evaluation_input_ref(simulation, artifact_store=store)

    assert input_ref is not None
    assert simulation.simulation_result_ref is not None
    assert input_ref.content_hash == str(simulation.simulation_result_ref.artifact_id)


def test_n5_transient_store_failure_is_unavailable_not_integrity_invalid(
    tmp_path: Path,
) -> None:
    """A transient backend failure does not become a false corruption verdict."""

    _problem, _context, _candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path
    )
    assert simulation.simulation_result_ref is not None

    class _TransientHasStore:
        def __init__(self, delegate: Any) -> None:
            self._delegate = delegate

        def get_manifest(self, artifact_ref: CASArtifactRef) -> Any:
            return self._delegate.get_manifest(artifact_ref)

        def has(self, _artifact_ref: CASArtifactRef) -> bool:
            raise ConnectionError("temporary artifact-store outage")

    with pytest.raises(
        GenerationCycleError,
        match="joint_simulation_result_unavailable",
    ):
        load_joint_simulation_result(
            simulation.simulation_result_ref,
            store=_TransientHasStore(store),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("failure_mode", "expected_cause"),
    [
        ("unavailable", RuntimeDependencyUnavailableError),
        ("timeout", RuntimeDependencyTimeoutError),
    ],
)
def test_n5_guarded_runtime_store_errors_are_typed_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
    expected_cause: type[Exception],
) -> None:
    """Production CAS guard errors become N5 unavailability, not corruption."""

    problem, context, candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path
    )
    assert simulation.simulation_result_ref is not None

    class _GuardFailureTarget:
        def __init__(self, delegate: Any) -> None:
            self._delegate = delegate

        def get_manifest(self, artifact_ref: CASArtifactRef) -> Any:
            return self._delegate.get_manifest(artifact_ref)

        def has(self, _artifact_ref: CASArtifactRef) -> bool:
            if failure_mode == "unavailable":
                raise OSError("temporary CAS I/O failure")
            time.sleep(0.35)
            return True

    if failure_mode == "timeout":
        monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "0.1")
    guarded_store = guard_runtime_cas(_GuardFailureTarget(store))
    original_loader = generation_cycle_module.load_joint_simulation_result
    observed_errors: list[GenerationCycleError] = []

    def observe_loader_error(*args: Any, **kwargs: Any) -> Any:
        try:
            return original_loader(*args, **kwargs)
        except GenerationCycleError as exc:
            observed_errors.append(exc)
            raise

    monkeypatch.setattr(
        generation_cycle_module,
        "load_joint_simulation_result",
        observe_loader_error,
    )
    try:
        observation = _DefaultSimulationBoundFoundryValuePort(
            repo_root=tmp_path,
            cycle_substrate_context=context,
            artifact_store=guarded_store,
        )(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )
        assert observation.status == "value_blocked"
        assert observation.authority_blockers == (
            "joint_simulation_result_unavailable",
        )
        assert len(observed_errors) == 1
        assert isinstance(observed_errors[0].__cause__, expected_cause)
    finally:
        guarded_store.close()


def test_n5_replay_does_not_mask_store_programming_errors(tmp_path: Path) -> None:
    """Unexpected store faults surface instead of being mislabeled as corruption."""

    _problem, _context, _candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path
    )
    assert simulation.simulation_result_ref is not None

    class _BrokenHasStore:
        def __init__(self, delegate: Any) -> None:
            self._delegate = delegate

        def get_manifest(self, artifact_ref: CASArtifactRef) -> Any:
            return self._delegate.get_manifest(artifact_ref)

        def has(self, _artifact_ref: CASArtifactRef) -> bool:
            raise AssertionError("store adapter bug")

    with pytest.raises(AssertionError, match="store adapter bug"):
        load_joint_simulation_result(
            simulation.simulation_result_ref,
            store=_BrokenHasStore(store),  # type: ignore[arg-type]
        )


def test_conditional_n8_status_is_not_authority_ready(tmp_path: Path) -> None:
    """The simulation-only value state is explicit and cannot carry N8 receipts."""

    problem, context, candidate, simulation, produced, store = _real_n5_observation(tmp_path)
    observation = _DefaultSimulationBoundFoundryValuePort(
        repo_root=tmp_path,
        cycle_substrate_context=context,
        artifact_store=store,
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_conditional", observation.model_dump(mode="json")
    assert observation.value_receipt is None
    assert observation.method_selection_receipt is None
    assert "simulation_only_k_sim_not_world_evidence" in observation.authority_blockers
    assert simulation.simulation_result_ref is not None
    assert isinstance(simulation.simulation_result_ref, CASArtifactRef)
    assert observation.value_ref == str(simulation.simulation_result_ref.artifact_id)

    reopened = load_joint_simulation_result(
        simulation.simulation_result_ref,
        store=store,
        expected_world_model_record_content_hash=context.world_model_record.content_hash,
    )
    outcome = problem.outcome_of_interest.target_variable
    trajectory = next(
        trajectory
        for trajectory in reopened.trajectories
        if trajectory.points and outcome in trajectory.points[0].effect
    )
    effect = trajectory.points[0].effect[outcome]
    assert isinstance(effect, float)
    produced_trajectory = next(
        candidate_trajectory
        for candidate_trajectory in produced.trajectories
        if candidate_trajectory.run_level == trajectory.run_level
        and candidate_trajectory.atom_ids == trajectory.atom_ids
        and candidate_trajectory.points
        and outcome in candidate_trajectory.points[0].effect
    )
    assert effect == produced_trajectory.points[0].effect[outcome]


def _n5_readback_witness(result: Any, outcome: str) -> dict[str, Any]:
    """Return one selected numerical point and the result's carried limits."""

    trajectory = next(
        trajectory
        for trajectory in result.trajectories
        if trajectory.points
        and any(outcome in point.effect for point in trajectory.points)
    )
    point = next(point for point in trajectory.points if outcome in point.effect)
    value = float(point.effect[outcome])
    assert math.isfinite(value)
    state_consumption = result.state_consumption
    return {
        "run_level": str(getattr(trajectory.run_level, "value", trajectory.run_level)),
        "atom_ids": list(trajectory.atom_ids),
        "trajectory_identity": {
            "engine_kind": str(
                getattr(trajectory.engine_kind, "value", trajectory.engine_kind)
            ),
            "method_fqn": trajectory.method_fqn,
            "objective_ref": trajectory.objective_ref,
        },
        "point_step": point.step,
        "outcome": outcome,
        "effect": value,
        "result_payload_hash": result.receipt.payload_hash,
        "world_model_record_content_hash": result.world_model_record_content_hash,
        "atom_ids_in_result": list(result.atom_ids),
        "selected_outcomes": list(result.selected_outcomes),
        "horizon": result.horizon.model_dump(mode="json"),
        "promotion_blockers": list(
            result.promotion_ready_value_packet.get("authority_blockers", ())
        ),
        "state_consumption_limitations": (
            list(state_consumption.authority_limitations)
            if state_consumption is not None
            else None
        ),
    }


def _persist_valid_structural_mismatch(
    result: Any,
    *,
    store: Any,
    mismatch: str,
) -> dict[str, Any]:
    """Persist a CAS- and receipt-valid artifact with inconsistent engine identity."""

    payload = json.loads(json.dumps(result.content_bound_payload()))
    selected = [
        decision
        for decision in payload["engine_decisions"]
        if decision["decision"] == "selected"
    ]
    assert len(selected) == 1
    decision = selected[0]
    trajectory_identity: dict[str, str] | None = None
    receipt_engine_kind = str(
        getattr(result.receipt.engine_kind, "value", result.receipt.engine_kind)
    )
    selected_trajectory = next(
        trajectory
        for trajectory in payload["trajectories"]
        if (
            trajectory["engine_kind"],
            trajectory["method_fqn"],
            trajectory["objective_ref"],
        )
        == (
            decision["engine_kind"],
            decision["method_fqn"],
            decision["objective_ref"],
        )
    )
    selected_trajectory_identity = {
        key: selected_trajectory[key]
        for key in ("engine_kind", "method_fqn", "objective_ref")
    }
    if mismatch == "trajectory_selection":
        trajectory = next(
            trajectory
            for trajectory in payload["trajectories"]
            if (
                trajectory["engine_kind"],
                trajectory["method_fqn"],
                trajectory["objective_ref"],
            )
            == (
                decision["engine_kind"],
                decision["method_fqn"],
                decision["objective_ref"],
            )
        )
        trajectory["objective_ref"] = f"{trajectory['objective_ref']}#foreign"
        trajectory_identity = {
            key: trajectory[key]
            for key in ("engine_kind", "method_fqn", "objective_ref")
        }
    elif mismatch == "receipt_engine_selection":
        receipt_engine_kind = next(
            engine_kind
            for engine_kind in (
                "program_graph",
                "ncm_parallel_worlds",
                "coupled_des_abm",
                "system_dynamics",
                "method_registry_estimator",
            )
            if engine_kind != decision["engine_kind"]
        )
    elif mismatch == "no_selected_engine_decision":
        decision["decision"] = "rejected"
    elif mismatch == "multiple_selected_engine_decisions":
        payload["engine_decisions"].append(json.loads(json.dumps(decision)))
    else:
        raise ValueError(f"unknown_structural_mismatch:{mismatch}")
    selected_after = [
        item
        for item in payload["engine_decisions"]
        if item["decision"] == "selected"
    ]

    receipt = build_content_bound_simulation_receipt(
        engine_kind=receipt_engine_kind,
        payload=payload,
        diagnostics=payload["diagnostics"],
    )
    mismatched = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    mismatched._content_payload = payload
    verify_simulation_receipt(mismatched.receipt, mismatched.content_bound_payload())
    ref = persist_joint_simulation_result(mismatched, store=store)
    return {
        "simulation_result_ref": ref.model_dump(mode="json"),
        "simulation_ref": receipt.payload_hash,
        "selected_decision_count": len(selected_after),
        "selected_decision": {
            key: decision[key]
            for key in ("engine_kind", "method_fqn", "objective_ref")
        },
        "selected_trajectory_identity": selected_trajectory_identity,
        "receipt_engine_kind": receipt.engine_kind,
        "trajectory_identity": trajectory_identity,
        "receipt_payload_hash": receipt.payload_hash,
    }


def _n5_readback_producer_child(
    store_root: Path,
    *,
    project_root: Path,
) -> dict[str, Any]:
    """Persist one real N5 result and emit only its cross-process handoff."""

    source_path = Path(generation_cycle_module.__file__).resolve()
    expected_source_path = (
        project_root / "src/polisyos/runtime/quality/generation_cycle.py"
    ).resolve()
    if source_path != expected_source_path:
        raise AssertionError(f"wrong_runtime_source:{source_path}")
    problem, context, candidate, simulation, produced, store = _real_n5_observation(
        store_root.parent,
        artifact_store=FileSystemCAS(store_root),
    )
    assert store is not None
    result_ref = simulation.simulation_result_ref
    assert result_ref is not None
    assert produced is not None
    structural_variants = {
        mismatch: _persist_valid_structural_mismatch(
            produced,
            store=store,
            mismatch=mismatch,
        )
        for mismatch in (
            "trajectory_selection",
            "receipt_engine_selection",
            "no_selected_engine_decision",
            "multiple_selected_engine_decisions",
        )
    }
    outcome = problem.outcome_of_interest.target_variable
    return {
        "producer_pid": os.getpid(),
        "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        "generation_cycle_source": str(source_path),
        "store_root": str(store_root),
        "simulation_status": simulation.status,
        "simulation_ref": simulation.simulation_ref,
        "simulation_result_ref": result_ref.model_dump(mode="json"),
        "simulation_authority_blockers": list(simulation.authority_blockers),
        "candidate_id": candidate.candidate_id,
        "candidate_atoms": [
            atom.model_dump(mode="json") for atom in candidate.intervention_atoms
        ],
        "problem": problem.model_dump(mode="json"),
        "cycle_substrate_context": context.model_dump(mode="json"),
        "world_model_record_content_hash": context.world_model_record.content_hash,
        "result_fingerprint": gy_content_hash(produced.model_dump(mode="json")),
        "result_witness": _n5_readback_witness(produced, outcome),
        "structural_variants": structural_variants,
    }


def _n5_readback_consumer_child(
    handoff: dict[str, Any],
    *,
    project_root: Path,
) -> dict[str, Any]:
    """Reopen and consume the writer's exact result in a separate process."""

    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
    )

    source_path = Path(generation_cycle_module.__file__).resolve()
    expected_source_path = (
        project_root / "src/polisyos/runtime/quality/generation_cycle.py"
    ).resolve()
    if source_path != expected_source_path:
        raise AssertionError(f"wrong_runtime_source:{source_path}")

    store = FileSystemCAS(Path(handoff["store_root"]))
    result_ref = CASArtifactRef.model_validate(handoff["simulation_result_ref"])
    problem = DesignProblem.model_validate(handoff["problem"])
    context = CycleSubstrateContext.model_validate(handoff["cycle_substrate_context"])
    atoms = tuple(
        InterventionAtomBinding.model_validate(payload)
        for payload in handoff["candidate_atoms"]
    )
    candidate = SimpleNamespace(
        candidate_id=handoff["candidate_id"],
        atom=atoms[0],
        intervention_atoms=atoms,
    )
    simulation = SimulationPortObservation(
        candidate_id=handoff["candidate_id"],
        status=handoff["simulation_status"],
        simulation_ref=handoff["simulation_ref"],
        simulation_result_ref=result_ref,
        uncertainty_kind="K_sim",
        authority_blockers=tuple(handoff["simulation_authority_blockers"]),
        k_world_ref_before=handoff["world_model_record_content_hash"],
        k_world_ref_after=handoff["world_model_record_content_hash"],
        world_model_record=context.world_model_record,
    )
    outcome = problem.outcome_of_interest.target_variable
    reopened = load_joint_simulation_result(
        result_ref,
        store=store,
        expected_world_model_record_content_hash=(
            handoff["world_model_record_content_hash"]
        ),
        expected_atom_ids=tuple(atom.intervention_id for atom in atoms),
        expected_selected_outcomes=(outcome,),
    )
    if gy_content_hash(reopened.model_dump(mode="json")) != handoff["result_fingerprint"]:
        raise AssertionError("cross_process_n5_result_content_changed")

    value_port = _DefaultSimulationBoundFoundryValuePort(
        repo_root=project_root,
        cycle_substrate_context=context,
        artifact_store=store,
    )

    def consume(observation: SimulationPortObservation) -> dict[str, Any]:
        return value_port(
            candidate=candidate,
            simulation=observation,
            problem=problem,
            cycle_index=0,
        ).model_dump(mode="json")

    blob_path, _ = store._paths(result_ref.artifact_id)
    original_blob = blob_path.read_bytes()
    try:
        blob_path.write_bytes(original_blob + b"corrupt")
        corrupt_result = consume(simulation)
    finally:
        blob_path.write_bytes(original_blob)

    missing_ref_payload = result_ref.model_dump(mode="json")
    missing_ref_payload["artifact_id"] = "sha256:" + "f" * 64
    missing_simulation = simulation.model_copy(
        update={
            "simulation_result_ref": CASArtifactRef.model_validate(missing_ref_payload)
        }
    )
    missing_result = consume(missing_simulation)

    foreign_simulation = simulation.model_copy(
        update={
            "world_model_record": SimpleNamespace(
                content_hash="sha256:" + "e" * 64
            )
        }
    )
    foreign_world = consume(foreign_simulation)

    divergent_sibling_ref = simulation.model_copy(
        update={"simulation_ref": "sha256:" + "0" * 64}
    )
    sibling_ref_mismatch = consume(divergent_sibling_ref)
    absent_sibling_ref = simulation.model_copy(update={"simulation_ref": None})
    sibling_ref_missing = consume(absent_sibling_ref)

    structural_consumers: dict[str, dict[str, Any]] = {}
    for name, variant in handoff["structural_variants"].items():
        variant_simulation = simulation.model_copy(
            update={
                "simulation_ref": variant["simulation_ref"],
                "simulation_result_ref": CASArtifactRef.model_validate(
                    variant["simulation_result_ref"]
                ),
            }
        )
        structural_consumers[name] = consume(variant_simulation)

    return {
        "consumer_pid": os.getpid(),
        "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        "generation_cycle_source": str(source_path),
        "simulation_result_ref": result_ref.model_dump(mode="json"),
        "result_fingerprint": gy_content_hash(reopened.model_dump(mode="json")),
        "result_witness": _n5_readback_witness(reopened, outcome),
        "simulation_ref_matches_receipt": (
            reopened.receipt.payload_hash == simulation.simulation_ref
        ),
        "value_observation": value_port(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        ).model_dump(mode="json"),
        "negative_consumers": {
            "missing_result": missing_result,
            "foreign_world": foreign_world,
            "corrupt_result": corrupt_result,
            "sibling_ref_mismatch": sibling_ref_mismatch,
            "sibling_ref_missing": sibling_ref_missing,
            **structural_consumers,
        },
    }


_N5_READBACK_CHILD_DISPATCH = """
import json
import sys
from pathlib import Path
from tests.unit.remediation.test_cyc_02 import (
    _n5_readback_consumer_child,
    _n5_readback_producer_child,
)

mode = sys.argv[1]
project_root = Path(sys.argv[2])
if mode == "produce":
    result = _n5_readback_producer_child(Path(sys.argv[3]), project_root=project_root)
elif mode == "consume":
    result = _n5_readback_consumer_child(json.load(sys.stdin), project_root=project_root)
else:
    raise SystemExit(f"unknown mode: {mode}")
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
"""


def _run_n5_readback_child(
    *,
    mode: str,
    project_root: Path,
    store_root: Path,
    handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one isolated writer or reader interpreter with the candidate source."""

    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(project_root / "src"), str(project_root))
    )
    for name in (
        "JAX_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        environment[name] = "1"
    environment["JAX_PLATFORM_NAME"] = "cpu"
    environment["XLA_FLAGS"] = (
        "--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _N5_READBACK_CHILD_DISPATCH,
            mode,
            str(project_root),
            str(store_root),
        ],
        cwd=project_root,
        env=environment,
        input=json.dumps(handoff) if handoff is not None else None,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, (
        f"N5 {mode} child failed ({completed.returncode}):\n"
        f"stderr tail:\n{completed.stderr[-4000:]}\n"
        f"stdout tail:\n{completed.stdout[-2000:]}"
    )
    output_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert output_lines, f"N5 {mode} child returned no JSON output"
    return json.loads(output_lines[-1])


def test_n5_result_reopens_and_n8_consumes_it_across_processes(
    tmp_path: Path,
) -> None:
    """A new process replays the exact numerical N5 artifact through N8."""

    project_root = Path(__file__).resolve().parents[3]
    expected_source_path = (
        project_root / "src/polisyos/runtime/quality/generation_cycle.py"
    ).resolve()
    assert Path(generation_cycle_module.__file__).resolve() == expected_source_path
    store_root = tmp_path / "n5-process-cas"
    produced = _run_n5_readback_child(
        mode="produce",
        project_root=project_root,
        store_root=store_root,
    )
    consumed = _run_n5_readback_child(
        mode="consume",
        project_root=project_root,
        store_root=store_root,
        handoff=produced,
    )

    assert produced["producer_pid"] != consumed["consumer_pid"]
    assert produced["generation_cycle_source"] == str(expected_source_path)
    assert consumed["generation_cycle_source"] == str(expected_source_path)
    assert consumed["simulation_result_ref"] == produced["simulation_result_ref"]
    assert consumed["result_fingerprint"] == produced["result_fingerprint"]
    assert consumed["result_witness"] == produced["result_witness"]
    assert consumed["simulation_ref_matches_receipt"]
    assert "simulation_only_k_sim_not_world_evidence" in produced[
        "simulation_authority_blockers"
    ]
    trajectory_variant = produced["structural_variants"]["trajectory_selection"]
    assert trajectory_variant["selected_decision_count"] == 1
    assert trajectory_variant["selected_trajectory_identity"] == (
        trajectory_variant["selected_decision"]
    )
    assert trajectory_variant["trajectory_identity"] != (
        trajectory_variant["selected_decision"]
    )
    assert trajectory_variant["receipt_engine_kind"] == (
        trajectory_variant["selected_decision"]["engine_kind"]
    )
    receipt_variant = produced["structural_variants"]["receipt_engine_selection"]
    assert receipt_variant["selected_decision_count"] == 1
    assert receipt_variant["receipt_engine_kind"] != (
        receipt_variant["selected_decision"]["engine_kind"]
    )
    assert produced["structural_variants"]["no_selected_engine_decision"][
        "selected_decision_count"
    ] == 0
    assert produced["structural_variants"]["multiple_selected_engine_decisions"][
        "selected_decision_count"
    ] == 2

    value = consumed["value_observation"]
    assert value["status"] == "value_conditional"
    assert value["value_ref"] == produced["simulation_result_ref"]["artifact_id"]
    assert value["evaluation_mode"] == "simulate_only"
    assert value["decision_grade"] == "low"
    assert "simulation_only_k_sim_not_world_evidence" in value["authority_blockers"]
    assert value.get("value_receipt") is None
    assert value.get("method_selection_receipt") is None

    negatives = consumed["negative_consumers"]
    assert negatives["missing_result"]["status"] == "value_blocked"
    assert negatives["missing_result"]["authority_blockers"] == [
        "joint_simulation_result_unavailable"
    ]
    assert negatives["foreign_world"]["status"] == "value_blocked"
    assert negatives["foreign_world"]["authority_blockers"] == [
        "joint_simulation_result_wmr_mismatch"
    ]
    assert negatives["corrupt_result"]["status"] == "value_blocked"
    assert negatives["corrupt_result"]["authority_blockers"] == [
        "joint_simulation_result_integrity_invalid"
    ]
    unblocked = {
        name: observation
        for name, observation in negatives.items()
        if observation["status"] != "value_blocked" or observation["value_ref"] is not None
    }
    assert not unblocked, (
        "N8 accepted result inputs that diverge from their typed engine/result identity: "
        f"{unblocked}"
    )


def test_program_graph_v2_blocker_removal_stays_out_of_eval_safety(
    tmp_path: Path,
) -> None:
    """Persisted ProgramGraph limits survive removal of N5 display markers."""

    witness = _owner_program_graph_n5_witness(
        tmp_path,
        income_values=(1000.0, 2000.0),
    )
    verifier_calls: list[str] = []
    value_owner_calls: list[str] = []

    class _InvocationSpy:
        def __init__(self, calls: list[str]) -> None:
            self._calls = calls

        def __getattr__(self, name: str) -> Any:
            def record_call(*args: Any, **kwargs: Any) -> Any:
                del args, kwargs
                self._calls.append(name)
                raise AssertionError(f"unexpected callback: {name}")

            return record_call

    try:
        simulation = witness.simulation
        assert simulation.simulation_result_ref is not None
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            persisted = load_joint_simulation_result(
                simulation.simulation_result_ref,
                store=witness.store,
                expected_world_model_record_content_hash=(
                    witness.world_model_build.record.content_hash
                ),
            )

        assert persisted.schema_version == "policyos.runtime.joint_simulation_horizon.v2"
        selected_program_graph = tuple(
            decision
            for decision in persisted.engine_decisions
            if decision.engine_kind == "program_graph"
            and decision.decision == "selected"
        )
        assert len(selected_program_graph) == 1
        state_consumption = persisted.state_consumption
        assert state_consumption is not None
        assert state_consumption.authority_limitations
        assert set(state_consumption.authority_limitations).issubset(
            simulation.authority_blockers
        )
        assert set(state_consumption.authority_limitations).issubset(
            persisted.promotion_ready_value_packet.get("authority_blockers", ())
        )

        # Keep the signed v2 bytes and their limitation markers while removing
        # only the observation-side display of those limitations.
        unmarked = simulation.model_copy(update={"authority_blockers": ()})
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            assert simulation_evaluation_input_ref(
                unmarked, artifact_store=witness.store
            ) is None
            observation = _DefaultSimulationBoundFoundryValuePort(
                repo_root=tmp_path,
                cycle_substrate_context=witness.context,
                artifact_store=witness.store,
                eval_safety_verifier=_InvocationSpy(verifier_calls),
                owner_gateway=_InvocationSpy(value_owner_calls),
            )(
                candidate=witness.candidate,
                simulation=unmarked,
                problem=witness.problem,
                cycle_index=0,
            )

        assert observation.status == "value_blocked"
        assert observation.authority_blockers == (
            "n8_state_consumption_limitation_mismatch",
        )
        assert verifier_calls == []
        assert value_owner_calls == []
    finally:
        witness.store.close()


class _GenericDefaultN5Store(FileSystemCAS):
    """Keep a generic JSON view as default while returning N5's selected view."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.generic_view_ref: CASArtifactRef | None = None

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> CASArtifactRef:
        if (
            opts.kind == "polisyos.runtime.joint_simulation_result"
            and self.generic_view_ref is None
        ):
            self.generic_view_ref = super().put_json(
                obj,
                PutOptions(
                    kind="application/json",
                    media_type="application/json",
                    schema=SchemaInfo(name="application/json", version="1"),
                ),
                canon_spec=canon_spec,
            )
        return super().put_json(obj, opts, canon_spec=canon_spec)


def test_n5_result_has_reopenable_cas_reference(tmp_path: Path) -> None:
    """The selected N5 view remains distinct from another honest view of its bytes."""

    store = _GenericDefaultN5Store(tmp_path / "n5-multiview-store")
    _problem, _context, _candidate, simulation, produced, supplied_store = (
        _real_n5_observation(tmp_path, artifact_store=store)
    )
    assert supplied_store is store
    result_ref = simulation.simulation_result_ref
    assert result_ref is not None
    assert result_ref.kind == "polisyos.runtime.joint_simulation_result"
    generic_ref = store.generic_view_ref
    assert generic_ref is not None
    assert generic_ref.artifact_id == result_ref.artifact_id
    assert generic_ref.manifest_profile_sha256 is None
    assert result_ref.manifest_profile_sha256 is not None

    generic_manifest = store.get_manifest(generic_ref)
    assert generic_manifest.kind == "application/json"
    manifest = store.get_manifest(result_ref)
    payload = json.loads(store.get_bytes(result_ref))
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "policyos.runtime.n5.joint_simulation_result"
    assert payload["receipt"]["payload_hash"] == produced.receipt.payload_hash
    assert payload["trajectories"]

    reopened = load_joint_simulation_result(
        result_ref,
        store=store,
        expected_world_model_record_content_hash=(
            produced.world_model_record_content_hash
        ),
        expected_atom_ids=produced.atom_ids,
    )
    assert reopened.trajectories == produced.trajectories
    assert reopened.world_model_record_content_hash == (
        produced.world_model_record_content_hash
    )

    wrong_profile_ref = result_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(
        GenerationCycleError,
        match="joint_simulation_result_unavailable",
    ):
        load_joint_simulation_result(wrong_profile_ref, store=store)

    missing_ref = CASArtifactRef(
        artifact_id="sha256:" + "f" * 64,
        kind=result_ref.kind,
        media_type=result_ref.media_type,
    )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_unavailable"):
        load_joint_simulation_result(missing_ref, store=store)

    blob_path, _ = store._paths(result_ref.artifact_id)
    selected_manifest_path = store._manifest_path_for_ref(
        result_ref.artifact_id,
        result_ref.manifest_profile_sha256,
    )
    default_manifest_path = store._manifest_path_for_ref(
        generic_ref.artifact_id,
        generic_ref.manifest_profile_sha256,
    )
    assert selected_manifest_path != default_manifest_path
    original_blob = blob_path.read_bytes()
    blob_path.write_bytes(original_blob + b"tampered")
    try:
        with pytest.raises(
            GenerationCycleError,
            match="joint_simulation_result_integrity_invalid",
        ):
            load_joint_simulation_result(result_ref, store=store)
    finally:
        blob_path.write_bytes(original_blob)

    original_manifest = selected_manifest_path.read_bytes()
    selected_manifest_path.write_bytes(b"{}")
    try:
        with pytest.raises(
            GenerationCycleError,
            match="joint_simulation_result_integrity_invalid",
        ):
            load_joint_simulation_result(result_ref, store=store)
        assert store.get_manifest(generic_ref).kind == "application/json"
    finally:
        selected_manifest_path.write_bytes(original_manifest)

    with pytest.raises(GenerationCycleError, match="joint_simulation_result_wmr_mismatch"):
        load_joint_simulation_result(
            result_ref,
            store=store,
            expected_world_model_record_content_hash="sha256:" + "e" * 64,
        )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_atom_binding"):
        load_joint_simulation_result(
            result_ref,
            store=store,
            expected_atom_ids=("foreign-model-atom",),
        )


@pytest.mark.asyncio
async def test_recursive_parent_keeps_n5_cas_reference(tmp_path: Path) -> None:
    """The real recursive parent route persists the N5 result before composition."""

    root = "design://cyc-02/recursive-root"
    child_refs = ("design://cyc-02/recursive-a", "design://cyc-02/recursive-b")
    parent_problem, context, _candidate = _cyc01_owner_bound_n5_case()
    problems = {
        root: parent_problem,
        child_refs[0]: _problem("cyc02_recursive_a"),
        child_refs[1]: _problem("cyc02_recursive_b"),
    }
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/cyc-02-recursive-cas",
    )
    request = _recursive_parent_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=parent_problem,
        world_model_record=context.world_model_record,
    )
    store = FileSystemCAS(tmp_path / "recursive-parent-store")
    controller = _recursive_contract_testing_controller(
        tmp_path,
        artifact_store=store,
    )
    subdesigns = _recursive_subdesigns(parent_ref=root, child_refs=child_refs)

    run = await controller.run(
        graph,
        problems_by_node=problems,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
        ),
        recursive_budget=RecursiveCycleBudget(
            max_depth=1,
            max_nodes=3,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        ),
        joint_simulation_requests_by_node={root: request},
        subdesign_contracts_by_node={root: subdesigns},
    )

    routed_by_ref = {node.node_ref: node for node in run.nodes}
    supplied_by_ref = {subdesign.workspace_id: subdesign for subdesign in subdesigns}
    for child_ref in child_refs:
        supplied = supplied_by_ref[child_ref].search_exit.terminal_state.model_dump(mode="json")
        routed = routed_by_ref[child_ref].terminal.model_dump(mode="json")
        differences = {
            field: {"supplied": supplied[field], "routed": routed[field]}
            for field in supplied
            if supplied[field] != routed[field]
        }
        assert not differences, (
            f"{child_ref} terminal mismatch: "
            f"{json.dumps(differences, sort_keys=True, separators=(',', ':'))}"
        )

    root_node = next(node for node in run.nodes if node.node_ref == root)
    assert root_node.joint_simulation is not None
    assert root_node.joint_simulation_ref is not None
    assert root_node.joint_simulation_ref.kind == "polisyos.runtime.joint_simulation_result"
    assert isinstance(request, JointSimulationRequest)

    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    reopened = load_joint_simulation_result(
        root_node.joint_simulation_ref,
        store=store,
        expected_world_model_record_content_hash=(
            request.world_model_record.content_hash
        ),
        expected_atom_ids=tuple(
            atom.intervention_id for atom in request.intervention_atoms
        ),
        expected_selected_outcomes=request.selected_outcomes,
    )
    assert reopened.trajectories == root_node.joint_simulation.trajectories


@pytest.mark.asyncio
async def test_recursive_parent_without_store_refuses_before_n5_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-store refusal precedes parent N5; leaf currentness is outside this seam."""

    root = "design://cyc-02/no-store-root"
    child_refs = ("design://cyc-02/no-store-a", "design://cyc-02/no-store-b")
    parent_problem, context, _candidate = _cyc01_owner_bound_n5_case()
    problems = {
        root: parent_problem,
        child_refs[0]: _problem("cyc02_no_store_a"),
        child_refs[1]: _problem("cyc02_no_store_b"),
    }
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/cyc-02-recursive-no-store",
    )
    request = _recursive_parent_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=parent_problem,
        world_model_record=context.world_model_record,
    )
    controller = _recursive_contract_testing_controller(tmp_path)

    class _N5ControllerSentinel:
        calls = 0

        def run(self, _request: object) -> object:
            self.calls += 1
            raise AssertionError("parent N5 controller ran without its runtime store")

    n5_sentinel = _N5ControllerSentinel()
    controller._joint_simulation_controller = n5_sentinel  # type: ignore[assignment]
    # The pinned public-parent selector fails before this seam at R2 currentness.
    # This narrow run keeps that validator out of the subject under test without
    # changing production validation or claiming a served whole-parent witness.
    monkeypatch.setattr(
        recursive_generation_cycle_module,
        "validate_generation_cycle_candidate_run",
        lambda *_args, **_kwargs: (),
    )

    # The two leaf intents are explicit candidate-only computations. The
    # canonical N9 owner has no runtime; explicit intents keep this negative
    # focused on the parent N5 store gate rather than implicit leaf authority.
    with pytest.raises(
        RecursiveGenerationCycleError,
        match="recursive_n5_runtime_store_not_established",
    ):
        await controller.run(
            graph,
            problems_by_node=problems,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1,
                max_nodes=3,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            joint_simulation_requests_by_node={root: request},
            subdesign_contracts_by_node={
                root: _recursive_subdesigns(parent_ref=root, child_refs=child_refs)
            },
            execution_intents_by_node={
                child_refs[0]: "candidate_only",
                child_refs[1]: "candidate_only",
            },
        )

    assert n5_sentinel.calls == 0


def test_n5_replay_uses_supplied_guarded_tenant_store(tmp_path: Path) -> None:
    """The N5 writer and N8 reader share the caller's tenant-owned store."""

    store = guard_runtime_cas(
        with_ambient_ownership_enforcement_if_supported(
            FileSystemCAS(tmp_path / "guarded-runtime-store")
        )
    )
    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            problem, context, candidate, simulation, _produced, supplied_store = (
                _real_n5_observation(tmp_path, artifact_store=store)
            )
            assert supplied_store is store
            observation = _DefaultSimulationBoundFoundryValuePort(
                repo_root=tmp_path,
                cycle_substrate_context=context,
                artifact_store=supplied_store,
            )(
                candidate=candidate,
                simulation=simulation,
                problem=problem,
                cycle_index=0,
            )
            assert observation.status == "value_conditional"
            assert simulation.simulation_result_ref is not None

        with (
            tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"),
            pytest.raises(
                GenerationCycleError,
                match="joint_simulation_result_unavailable",
            ),
        ):
            load_joint_simulation_result(
                simulation.simulation_result_ref,
                store=store,
            )
    finally:
        store.close()


def test_n5_does_not_execute_without_runtime_owned_store(tmp_path: Path) -> None:
    """A valid request cannot execute if N5 cannot durably replay its result."""

    _problem, _context, _candidate, simulation, _produced, store = _real_n5_observation(
        tmp_path,
        without_runtime_store=True,
    )

    assert store is None
    assert simulation.status == "simulation_blocked"
    assert simulation.simulation_result_ref is None
    assert simulation.authority_blockers == ("n5_runtime_store_not_established",)
