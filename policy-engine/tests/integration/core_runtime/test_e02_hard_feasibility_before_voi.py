"""N5 hard-feasibility decisions bind candidate selection before VOI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    JointSimulationPort,
    PromotionRuntime,
    SimulationPortObservation,
    load_joint_simulation_result,
    simulation_evaluation_input_ref,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    intervention_atom_content_hash,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecord
from tests.unit.runtime.quality.test_generation_cycle import (
    _budget,
    _owner_n5_case_with_selected_ncm_ref,
    _runtime_ncm_fixture_store,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _atom

_FRESH_N8_CHILD = r"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import polisyos.runtime.quality.generation_cycle as generation_cycle
from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    SimulationPortObservation,
    _DefaultSimulationBoundFoundryValuePort,
)
from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
from polisyos.runtime.quality.world_model_record import WorldModelRecord

handoff = json.load(sys.stdin)
repo_root = Path(handoff["repo_root"]).resolve()
actual_source = Path(generation_cycle.__file__).resolve()
expected_source = (repo_root / "src/polisyos/runtime/quality/generation_cycle.py").resolve()
if actual_source != expected_source:
    raise AssertionError(f"wrong_runtime_source:{actual_source}")

atoms = tuple(
    InterventionAtomBinding.model_validate(item)
    for item in handoff["candidate"]["intervention_atoms"]
)
candidate = SimpleNamespace(
    candidate_id=handoff["candidate"]["candidate_id"],
    atom=atoms[0],
    intervention_atoms=atoms,
)
problem = DesignProblem.model_validate(handoff["problem"])
world = WorldModelRecord.model_validate(handoff["world_model_record"])
simulation = SimulationPortObservation.model_validate(handoff["simulation"]).model_copy(
    update={"world_model_record": world}
)
observation = _DefaultSimulationBoundFoundryValuePort(
    repo_root=repo_root,
    cycle_substrate_context=None,
    artifact_store=FileSystemCAS(Path(handoff["store_root"])),
)(candidate=candidate, simulation=simulation, problem=problem, cycle_index=0)
print(json.dumps({
    "consumer_pid": os.getpid(),
    "runtime_source": str(actual_source),
    "observation": observation.model_dump(mode="json"),
}, sort_keys=True))
"""


@dataclass(frozen=True)
class _FixtureCandidate:
    """Candidate fixture with an explicit identity for its complete atom tuple."""

    candidate_id: str
    atom: InterventionAtomBinding
    intervention_atoms: tuple[InterventionAtomBinding, ...]
    content_hash: str


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[_FixtureCandidate, ...]
    surrogate_rankings: tuple[_Ranking, ...]


class _ControlledGenerator:
    """Provide content-bound fixture candidates without making an N4 claim."""

    def __init__(self, candidates: tuple[_FixtureCandidate, ...]) -> None:
        self._candidates = candidates

    async def __call__(self, problem: object, *, cycle_index: int) -> _GenerationResult:
        del problem
        assert cycle_index == 0
        rankings = tuple(
            _Ranking(
                candidate_id=candidate.candidate_id,
                score=0.99 if index == 0 else 0.9,
                voi_estimate=20.0 if index == 0 else 8.0,
            )
            for index, candidate in enumerate(self._candidates)
        )
        return _GenerationResult(
            status="generated",
            candidates=self._candidates,
            surrogate_rankings=rankings,
        )


class _FixtureGrounding:
    """Keep grounding constant as a test prerequisite, not as evidence."""

    def __call__(
        self,
        *,
        candidate: _FixtureCandidate,
        problem: object,
        cycle_index: int,
        generation_result: object,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=candidate.candidate_id,
            status="grounded_shadow",
            grounding_score=0.72,
            current_valid=False,
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
        )


def _bundle_hash(atoms: tuple[InterventionAtomBinding, ...]) -> str:
    if len(atoms) == 1:
        return atoms[0].content_hash
    return gy_content_hash(
        {"intervention_atom_content_hashes": [atom.content_hash for atom in atoms]}
    )


def _rebind_atom(
    atom: InterventionAtomBinding,
    *,
    problem_ref: str,
    world_model_record_ref: str,
) -> InterventionAtomBinding:
    rebound = atom.model_copy(
        update={
            "problem_frame_ref": problem_ref,
            "world_model_record_ref": world_model_record_ref,
        }
    )
    content_hash = intervention_atom_content_hash(rebound)
    rebound = rebound.model_copy(
        update={
            "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
            "content_hash": content_hash,
        }
    )
    return InterventionAtomBinding.model_validate(rebound.model_dump(mode="python"))


def _owner_fixture(
    tmp_path: Path,
    *,
    values: tuple[float, ...] = (1.0, 2.0),
) -> tuple[Any, Any, Any, _FixtureCandidate, _FixtureCandidate]:
    """Build conflicting and feasible candidates over one CAS-selected owner NCM."""

    store, _ncm, ncm_ref = _runtime_ncm_fixture_store(tmp_path)
    hints = {
        "joint_simulation_horizon": {"start": 0, "end": 0, "step": 1},
        "joint_simulation_baseline_state": {"firm_survival": 0.0},
    }
    problem, context, _base_candidate = _owner_n5_case_with_selected_ncm_ref(
        ncm_ref,
        runtime_hints=hints,
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    world_ref = context.world_model_record.world_model_record_id
    atoms = tuple(
        _rebind_atom(
            _atom(
                intervention_id=("income_feasible" if index == 0 else f"income_conflict_{index}"),
                causal_variable="agents.income",
                engine_variable="income_delta",
                value=value,
                world_model_record_ref=world_ref,
            ),
            problem_ref=problem_ref,
            world_model_record_ref=world_ref,
        )
        for index, value in enumerate(values)
    )
    feasible_atom = atoms[0]
    infeasible_atoms = (atoms[0], atoms[1])
    high = _FixtureCandidate(
        candidate_id="candidate_high_conflict",
        atom=infeasible_atoms[0],
        intervention_atoms=infeasible_atoms,
        content_hash=_bundle_hash(infeasible_atoms),
    )
    low = _FixtureCandidate(
        candidate_id="candidate_feasible_single",
        atom=feasible_atom,
        intervention_atoms=(feasible_atom,),
        content_hash=_bundle_hash((feasible_atom,)),
    )
    return store, problem, context, high, low


def _production_controller(
    *,
    store: FileSystemCAS,
    problem: object,
    context: object,
    candidates: tuple[_FixtureCandidate, ...],
    repo_root: Path,
) -> GenerationCycleController:
    """Use production composition with the default N5/N8 owner ports."""

    runtime = PromotionRuntime(store=store)
    return GenerationCycleController(
        generation_port=_ControlledGenerator(candidates),
        grounding_port=_FixtureGrounding(),
        repo_root=repo_root,
        cycle_substrate_context=context,
        promotion_runtime=runtime,
        authority_scope="production",
    )


def _fresh_n8(
    *,
    repo_root: Path,
    store_root: Path,
    world_model_record: WorldModelRecord,
    problem: object,
    candidate: _FixtureCandidate,
    simulation: SimulationPortObservation,
) -> dict[str, Any]:
    child_problem = problem.model_copy(update={"runtime_hints": {}})
    payload = {
        "repo_root": str(repo_root),
        "store_root": str(store_root),
        "world_model_record": world_model_record.model_dump(mode="json"),
        "problem": child_problem.model_dump(mode="json"),
        "candidate": {
            "candidate_id": candidate.candidate_id,
            "intervention_atoms": [
                atom.model_dump(mode="json") for atom in candidate.intervention_atoms
            ],
        },
        "simulation": simulation.model_copy(update={"world_model_record": None}).model_dump(
            mode="json"
        ),
    }
    env = os.environ.copy()
    source_roots = [str(repo_root / "src"), str(repo_root)]
    if env.get("PYTHONPATH"):
        source_roots.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(source_roots)
    completed = subprocess.run(
        [sys.executable, "-c", _FRESH_N8_CHILD],
        cwd=repo_root,
        env=env,
        input=json.dumps(payload),
        capture_output=True,
        check=False,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, (
        f"fresh_n8_process_failed:{completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


@pytest.mark.asyncio
async def test_hard_n5_feasibility_filters_before_voi_and_serves_real_owner_result(
    tmp_path: Path,
) -> None:
    """The high-ranked conflicting bundle is refused before N6 selects the feasible atom."""

    repo_root = Path(__file__).resolve().parents[3]
    store, problem, context, high, low = _owner_fixture(tmp_path)
    assert high.content_hash != high.atom.content_hash
    assert tuple(atom.world_model_record_ref for atom in high.intervention_atoms) == (
        context.world_model_record.world_model_record_id,
        context.world_model_record.world_model_record_id,
    )
    assert all(
        atom.problem_frame_ref == gy_content_hash(problem.model_dump(mode="json"))
        for atom in high.intervention_atoms + low.intervention_atoms
    )

    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            controller = _production_controller(
                store=store,
                problem=problem,
                context=context,
                candidates=(high, low),
                repo_root=repo_root,
            )
            assert type(controller._simulation_port) is JointSimulationPort
            port = controller._simulation_port
            run = await controller.run(
                problem,
                budget_state=_budget(),
                min_cycles=1,
                max_cycles=1,
            )
            cycle = run.cycles[0]
            # This assertion is the semantic red against the preflight-free source:
            # the old selector sends the higher-ranked conflicting bundle to N5.
            assert cycle.selected_candidate_ref == low.candidate_id

            prepared = port.prepare_candidate(
                candidate=low,
                problem=problem,
                cycle_index=0,
            )
            assert prepared.applicability.status == "eligible"
            assert prepared.request is not None
            assert prepared.applicability.request_digest is not None
            direct_result = port._controller.run(
                prepared.request,
                expected_applicability=prepared.applicability,
            )

            assert cycle.simulation.status == "joint_simulated"
            assert cycle.simulation.simulation_result_ref is not None
            assert cycle.value_port.status == "value_conditional"
            assert cycle.value_port.value_ref == str(
                cycle.simulation.simulation_result_ref.artifact_id
            )
            assert (
                simulation_evaluation_input_ref(
                    cycle.simulation,
                    artifact_store=store,
                )
                is not None
            )

            summary_by_id = {item.candidate_id: item for item in run.candidate_summaries}
            high_summary = summary_by_id[high.candidate_id]
            low_summary = summary_by_id[low.candidate_id]
            assert high_summary.n5_applicability.status == "ineligible"
            assert high_summary.n5_applicability.blockers == ("intervention_assignment_conflict",)
            assert low_summary.n5_applicability.status == "eligible"
            assert low_summary.n5_applicability.request_digest == (
                prepared.applicability.request_digest
            )
            assert high_summary.content_hash == high.content_hash
            assert low_summary.content_hash == low.content_hash
            assert generation_cycle_module._candidate_content_hash(high) == high.content_hash
            assert generation_cycle_module._candidate_content_hash(low) == low.content_hash

            persisted = load_joint_simulation_result(
                cycle.simulation.simulation_result_ref,
                store=store,
                expected_world_model_record_content_hash=context.world_model_record.content_hash,
                expected_world_model_record_ref=context.world_model_record.world_model_record_id,
                expected_atom_ids=tuple(atom.intervention_id for atom in low.intervention_atoms),
                expected_selected_outcomes=("firm_survival",),
                expected_receipt_payload_hash=cycle.simulation.simulation_ref or "",
            )
            assert persisted.receipt.payload_hash == cycle.simulation.simulation_ref
            assert persisted.world_model_record_content_hash == (
                context.world_model_record.content_hash
            )
            assert persisted.atom_ids == (low.atom.intervention_id,)
            assert persisted.engine_decisions == direct_result.engine_decisions
            assert persisted.trajectories == direct_result.trajectories

            child = _fresh_n8(
                repo_root=repo_root,
                store_root=tmp_path / "runtime-cas",
                world_model_record=context.world_model_record,
                problem=problem,
                candidate=low,
                simulation=cycle.simulation,
            )
            assert child["consumer_pid"] != os.getpid()
            assert child["runtime_source"] == str(
                (repo_root / "src/polisyos/runtime/quality/generation_cycle.py").resolve()
            )
            child_value = child["observation"]
            assert child_value["status"] == "value_conditional"
            assert child_value["value_ref"] == str(
                cycle.simulation.simulation_result_ref.artifact_id
            )
            assert "simulation_only_k_sim_not_world_evidence" in child_value["authority_blockers"]
    finally:
        store.close()


@pytest.mark.asyncio
async def test_all_hard_infeasible_candidates_block_before_n5_and_voi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fully refused denominator has no physical N5 execution or VOI scheduling."""

    repo_root = Path(__file__).resolve().parents[3]
    store, problem, context, high, _low = _owner_fixture(tmp_path)
    second = _FixtureCandidate(
        candidate_id="candidate_second_conflict",
        atom=high.atom,
        intervention_atoms=high.intervention_atoms,
        content_hash=high.content_hash,
    )
    n5_run_calls = 0
    owner_run = JointSimulationHorizonController.run

    def count_n5_runs(
        self: JointSimulationHorizonController, request: Any, *args: Any, **kwargs: Any
    ):
        nonlocal n5_run_calls
        n5_run_calls += 1
        return owner_run(self, request, *args, **kwargs)

    monkeypatch.setattr(JointSimulationHorizonController, "run", count_n5_runs)
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            controller = _production_controller(
                store=store,
                problem=problem,
                context=context,
                candidates=(high, second),
                repo_root=repo_root,
            )
            assert type(controller._simulation_port) is JointSimulationPort
            run = await controller.run(
                problem,
                budget_state=_budget(),
                min_cycles=1,
                max_cycles=1,
            )
            cycle = run.cycles[0]
            summary_by_id = {item.candidate_id: item for item in run.candidate_summaries}
            assert {
                candidate_id: summary_by_id[candidate_id].n5_applicability.status
                for candidate_id in (high.candidate_id, second.candidate_id)
            } == {
                high.candidate_id: "ineligible",
                second.candidate_id: "ineligible",
            }
            assert cycle.simulation.status == "simulation_blocked"
            assert cycle.simulation.simulation_result_ref is None
            assert cycle.voi_decision.scheduler_action == "not_run_hard_feasibility_blocked"
            assert n5_run_calls == 0
    finally:
        store.close()


@pytest.mark.asyncio
async def test_removing_candidate_filter_keeps_refusal_marker_but_selects_refused_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1: removing only N5 filtering preserves markers but changes N6 selection."""

    repo_root = Path(__file__).resolve().parents[3]
    store, problem, context, high, low = _owner_fixture(tmp_path)
    original_selector = generation_cycle_module._grounded_candidate_for_evaluation
    removal_applied = 0

    def remove_n5_filter(**kwargs: Any) -> object:
        nonlocal removal_applied
        applicability = kwargs.pop("n5_applicability_by_candidate", None)
        if applicability is not None:
            removal_applied += 1
        return original_selector(**kwargs)

    monkeypatch.setattr(
        generation_cycle_module,
        "_grounded_candidate_for_evaluation",
        remove_n5_filter,
    )
    n5_run_calls = 0
    owner_run = JointSimulationHorizonController.run

    def count_n5_runs(
        self: JointSimulationHorizonController, request: Any, *args: Any, **kwargs: Any
    ):
        nonlocal n5_run_calls
        n5_run_calls += 1
        return owner_run(self, request, *args, **kwargs)

    monkeypatch.setattr(JointSimulationHorizonController, "run", count_n5_runs)
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            controller = _production_controller(
                store=store,
                problem=problem,
                context=context,
                candidates=(high, low),
                repo_root=repo_root,
            )
            run = await controller.run(
                problem,
                budget_state=_budget(),
                min_cycles=1,
                max_cycles=1,
            )
            cycle = run.cycles[0]
            summary_by_id = {item.candidate_id: item for item in run.candidate_summaries}
            assert removal_applied == 1
            assert summary_by_id[high.candidate_id].n5_applicability.status == "ineligible"
            assert summary_by_id[high.candidate_id].n5_applicability.blockers == (
                "intervention_assignment_conflict",
            )
            assert cycle.selected_candidate_ref == high.candidate_id
            assert cycle.simulation.status == "simulation_blocked"
            assert cycle.voi_decision.scheduler_action == "not_run_hard_feasibility_blocked"
            assert n5_run_calls == 0
    finally:
        store.close()


def test_prepared_n5_digest_rejects_changed_atom_problem_and_profile_route(
    tmp_path: Path,
) -> None:
    """The prepared owner request is content-current and excludes profile handoffs."""

    store, problem, context, _high, low = _owner_fixture(tmp_path)
    repo_root = Path(__file__).resolve().parents[3]
    world_ref = context.world_model_record.world_model_record_id
    changed_atom = _rebind_atom(
        _atom(
            intervention_id=low.atom.intervention_id,
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=3.0,
            world_model_record_ref=world_ref,
        ),
        problem_ref=low.atom.problem_frame_ref,
        world_model_record_ref=world_ref,
    )
    changed_candidate = _FixtureCandidate(
        candidate_id=low.candidate_id,
        atom=changed_atom,
        intervention_atoms=(changed_atom,),
        content_hash=_bundle_hash((changed_atom,)),
    )
    changed_problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "joint_simulation_baseline_state": {"firm_survival": 1.0},
            }
        }
    )
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            port = JointSimulationPort(
                repo_root=repo_root,
                cycle_substrate_context=context,
                artifact_store=store,
            )
            prepared = port.prepare_candidate(
                candidate=low,
                problem=problem,
                cycle_index=0,
            )
            assert prepared.applicability.status == "eligible"
            assert changed_candidate.candidate_id == low.candidate_id
            assert not port.prepared_applicability_is_current(
                prepared=prepared,
                candidate=changed_candidate,
                problem=problem,
                cycle_index=0,
            )
            assert not port.prepared_applicability_is_current(
                prepared=prepared,
                candidate=low,
                problem=changed_problem,
                cycle_index=0,
            )

            profile_handoff_port = JointSimulationPort(
                repo_root=repo_root,
                cycle_substrate_context=context,
                artifact_store=store,
                candidate_simulation_handoff=SimpleNamespace(profile_id="fixture-profile"),
            )
            assert port.supports_applicability_preflight(problem)
            assert not profile_handoff_port.supports_applicability_preflight(problem)
    finally:
        store.close()
