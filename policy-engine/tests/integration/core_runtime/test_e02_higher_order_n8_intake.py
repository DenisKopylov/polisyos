"""B26 persisted interaction evidence consumed by the real N8 K_sim bridge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef as CASArtifactRef
from polisyos.core.artifacts import FileSystemCAS
from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation
from polisyos.runtime.quality.generation_cycle import (
    JointSimulationPort,
    SimulationPortObservation,
    load_joint_simulation_result,
    persist_joint_simulation_result,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationResult,
    build_content_bound_simulation_receipt,
    verify_simulation_receipt,
)
from tests.unit.runtime.quality.test_generation_cycle import _problem
from tests.unit.runtime.quality.test_joint_simulation_horizon import _atom, _request

_N8_CHILD = r"""
from __future__ import annotations

import ast
import copy
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
store = FileSystemCAS(Path(handoff["store_root"]))
world = WorldModelRecord.model_validate(handoff["world_model_record"])
outputs = {"consumer_pid": os.getpid(), "runtime_source": str(actual_source), "cases": {}}

def consume(case):
    problem = DesignProblem.model_validate(case["problem"])
    atoms = tuple(
        InterventionAtomBinding.model_validate(item)
        for item in case["candidate"]["intervention_atoms"]
    )
    candidate = SimpleNamespace(
        candidate_id=case["candidate"]["candidate_id"],
        atom=atoms[0],
        intervention_atoms=atoms,
    )
    simulation = SimulationPortObservation.model_validate(case["simulation"]).model_copy(
        update={"world_model_record": world}
    )
    observation = _DefaultSimulationBoundFoundryValuePort(
        repo_root=repo_root,
        cycle_substrate_context=None,
        artifact_store=store,
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    return observation

for name, case in handoff["cases"].items():
    outputs["cases"][name] = consume(case).model_dump(mode="json")

source_tree = ast.parse(actual_source.read_text(encoding="utf-8"))
interaction_validator = next(
    (
        node
        for node in ast.walk(source_tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_recompute_conditional_interaction_evidence"
    ),
    None,
)

class RemoveReasonGuard(ast.NodeTransformer):
    def __init__(self, reason_code):
        self.reason_code = reason_code
        self.removed = 0

    def visit_If(self, node):
        node = self.generic_visit(node)
        if any(
            isinstance(item, ast.Constant) and item.value == self.reason_code
            for item in ast.walk(node)
        ):
            self.removed += 1
            return None
        return node

def install_validator(node):
    isolated = ast.Module(body=[copy.deepcopy(node)], type_ignores=[])
    ast.fix_missing_locations(isolated)
    exec(compile(isolated, str(actual_source), "exec"), generation_cycle.__dict__)

outputs["removal_controls"] = {}
for reason_code, case_name in handoff["removal_controls"].items():
    if interaction_validator is None:
        outputs["removal_controls"][reason_code] = {
            "applied": False,
            "removed_guard_count": 0,
            "case": case_name,
            "detail": "interaction_validator_not_implemented",
        }
        continue
    mutant = copy.deepcopy(interaction_validator)
    remover = RemoveReasonGuard(reason_code)
    mutant = remover.visit(mutant)
    ast.fix_missing_locations(mutant)
    install_validator(interaction_validator)
    if remover.removed:
        install_validator(mutant)
        mutated_observation = consume(handoff["cases"][case_name])
        outputs["removal_controls"][reason_code] = {
            "applied": True,
            "removed_guard_count": remover.removed,
            "case": case_name,
            "observation": mutated_observation.model_dump(mode="json"),
        }
    else:
        outputs["removal_controls"][reason_code] = {
            "applied": False,
            "removed_guard_count": 0,
            "case": case_name,
            "detail": "source_mutant_not_applied",
        }
print(json.dumps(outputs, sort_keys=True))
"""


def _cubic_ncm() -> NCMSpec:
    """Build a deterministic order-three structural equation for the registered NCM."""

    variables = ("income_delta", "balance_delta", "labor_count_delta")
    return NCMSpec(
        endogenous_vars=[*variables, "firm_survival"],
        exogenous_specs=[
            ExogenousSpec(variable=f"u_{variable}", associated_endogenous=variable)
            for variable in (*variables, "firm_survival")
        ],
        structural_equations=[
            StructuralEquation(
                variable=variable,
                parents=[],
                exogenous=f"u_{variable}",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            )
            for variable in variables
        ]
        + [
            StructuralEquation(
                variable="firm_survival",
                parents=list(variables),
                exogenous="u_firm_survival",
                equation_type="nonlinear",
                equation_params={
                    "noise_expression": ("income_delta * balance_delta * labor_count_delta + u")
                },
            )
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="symbolic",
    )


def _cubic_request() -> Any:
    """Reuse the canonical N5 request and atom builders with the real cubic NCM."""

    base = _request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        *base.intervention_atoms,
        _atom(
            intervention_id="labor_market",
            causal_variable="firms.labor_count",
            engine_variable="labor_count_delta",
            value=1.0,
            world_model_record_ref=world_ref,
            mechanism_kind="labor_market",
            mechanism_variables=(
                "agents.employer_id",
                "agents.is_employed",
                "agents.income",
                "firms.labor_count",
            ),
        ),
    )
    plan = base.engine_plan[0].model_copy(update={"ncm_spec": _cubic_ncm()})
    return base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("firm_survival",),
            "horizon": HorizonSpec(start=0, end=0),
            "baseline_state": {
                "income_delta": 0.0,
                "balance_delta": 0.0,
                "labor_count_delta": 0.0,
                "firm_survival": 0.0,
            },
            "evidence_state": {
                "income_delta": 0.0,
                "balance_delta": 0.0,
                "labor_count_delta": 0.0,
                "firm_survival": 0.0,
            },
            "engine_plan": (plan,),
        }
    )


def _content_valid_variant(
    result: JointSimulationResult,
    *,
    store: FileSystemCAS,
    mutation: str,
) -> dict[str, Any]:
    """Persist one semantic mutant with a freshly valid receipt and CAS hash."""

    payload = json.loads(json.dumps(result.content_bound_payload()))
    if mutation == "false_residual":
        payload["higher_order_residuals"]["firm_survival"]["0"] = 0.75
        payload["feedback_classification"]["higher_order_residuals"]["firm_survival"]["0"] = 0.75
    elif mutation == "false_orders":
        payload["feedback_classification"]["checked_interaction_orders"] = [1, 2]
        payload["diagnostics"]["checked_interaction_orders"] = [1, 2]
    elif mutation == "missing_pair_scope":
        trajectories = payload["trajectories"]
        missing = next(
            index
            for index, trajectory in enumerate(trajectories)
            if trajectory["run_level"] == "pairwise"
        )
        del trajectories[missing]
    elif mutation == "wrong_horizon_step":
        trajectory = next(item for item in payload["trajectories"] if item["run_level"] == "joint")
        trajectory["points"][0]["step"] = 1
    elif mutation == "duplicate_grid_point":
        trajectory = next(item for item in payload["trajectories"] if item["run_level"] == "joint")
        trajectory["points"].append(json.loads(json.dumps(trajectory["points"][0])))
    elif mutation == "trajectory_permutation":
        payload["trajectories"] = list(reversed(payload["trajectories"]))
    else:
        raise ValueError(f"unknown_content_valid_n5_mutation:{mutation}")

    receipt = build_content_bound_simulation_receipt(
        engine_kind=str(getattr(result.receipt.engine_kind, "value", result.receipt.engine_kind)),
        payload=payload,
        diagnostics=payload["diagnostics"],
    )
    variant = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    variant._content_payload = payload
    verify_simulation_receipt(variant.receipt, variant.content_bound_payload())
    ref = persist_joint_simulation_result(variant, store=store)
    return {
        "simulation_result_ref": ref.model_dump(mode="json"),
        "simulation_ref": receipt.payload_hash,
        "receipt_payload_hash": receipt.payload_hash,
        "cas_artifact_id": str(ref.artifact_id),
    }


def _case(
    *,
    simulation: SimulationPortObservation,
    problem: Any,
    candidate_id: str,
    atoms: tuple[Any, ...],
) -> dict[str, Any]:
    return {
        "simulation": simulation.model_dump(mode="json"),
        "problem": problem.model_dump(mode="json"),
        "candidate": {
            "candidate_id": candidate_id,
            "intervention_atoms": [atom.model_dump(mode="json") for atom in atoms],
        },
    }


def test_real_n5_cubic_cas_is_recomputed_by_fresh_default_n8_consumer(
    tmp_path: Path,
) -> None:
    """The real N8 consumer accepts verified B26 evidence and rejects content-valid false claims."""

    repo_root = Path(__file__).resolve().parents[3]
    request = _cubic_request()
    atoms = tuple(request.intervention_atoms)
    candidate_id = "candidate_e02_real_ncm_cubic"
    problem = _problem("e02_n8_higher_order").model_copy(
        update={"runtime_hints": {"joint_simulation_request": request}}
    )
    candidate = SimpleNamespace(
        candidate_id=candidate_id,
        atom=atoms[0],
        intervention_atoms=atoms,
    )
    store_root = tmp_path / "n5-cas"
    store = FileSystemCAS(store_root)
    simulation = JointSimulationPort(
        repo_root=repo_root,
        artifact_store=store,
    )(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )
    assert simulation.status == "joint_simulated", simulation.model_dump(mode="json")
    assert simulation.simulation_result_ref is not None
    assert simulation.simulation_ref is not None

    result = load_joint_simulation_result(
        simulation.simulation_result_ref,
        store=store,
        expected_world_model_record_content_hash=request.world_model_record.content_hash,
        expected_world_model_record_ref=request.world_model_record.world_model_record_id,
        expected_atom_ids=tuple(atom.intervention_id for atom in atoms),
        expected_selected_outcomes=("firm_survival",),
        expected_receipt_payload_hash=simulation.simulation_ref,
    )
    assert result.receipt.payload_hash == simulation.simulation_ref
    assert result.receipt.trajectory_count == len(result.trajectories) == 7
    selected_decisions = tuple(
        decision for decision in result.engine_decisions if decision.decision == "selected"
    )
    assert len(selected_decisions) == 1
    assert selected_decisions[0].engine_kind == "ncm_parallel_worlds"
    assert selected_decisions[0].method_fqn is not None
    assert selected_decisions[0].method_fqn.endswith("ncm_engine@1.0.0")
    assert result.feedback_classification.checked_interaction_orders == (1, 2, 3)
    assert result.higher_order_residuals == {"firm_survival": {0: pytest.approx(1.0)}}
    assert all(
        trajectory.points[0].outcomes["firm_survival"]
        == pytest.approx(1.0 if trajectory.run_level == "joint" else 0.0)
        for trajectory in result.trajectories
    )
    assert all(
        tuple(point.step for point in trajectory.points) == (0,)
        for trajectory in result.trajectories
    )

    cases: dict[str, dict[str, Any]] = {}
    consumer_problem = problem.model_copy(update={"runtime_hints": {}})
    valid = simulation.model_copy(update={"world_model_record": None})
    cases["valid"] = _case(
        simulation=valid,
        problem=consumer_problem,
        candidate_id=candidate_id,
        atoms=atoms,
    )

    forged = {
        "false_residual": _content_valid_variant(result, store=store, mutation="false_residual"),
        "false_orders": _content_valid_variant(result, store=store, mutation="false_orders"),
        "missing_pair_scope": _content_valid_variant(
            result, store=store, mutation="missing_pair_scope"
        ),
        "wrong_horizon_step": _content_valid_variant(
            result, store=store, mutation="wrong_horizon_step"
        ),
        "duplicate_grid_point": _content_valid_variant(
            result, store=store, mutation="duplicate_grid_point"
        ),
    }
    for name, persisted in forged.items():
        variant = simulation.model_copy(
            update={
                "simulation_result_ref": CASArtifactRef.model_validate(
                    persisted["simulation_result_ref"]
                ),
                "simulation_ref": persisted["simulation_ref"],
                "world_model_record": None,
            }
        )
        assert persisted["receipt_payload_hash"] == variant.simulation_ref
        assert persisted["cas_artifact_id"] == str(variant.simulation_result_ref.artifact_id)
        cases[name] = _case(
            simulation=variant,
            problem=consumer_problem,
            candidate_id=candidate_id,
            atoms=atoms,
        )

    permuted_ref = _content_valid_variant(
        result,
        store=store,
        mutation="trajectory_permutation",
    )
    permuted = simulation.model_copy(
        update={
            "simulation_result_ref": CASArtifactRef.model_validate(
                permuted_ref["simulation_result_ref"]
            ),
            "simulation_ref": permuted_ref["simulation_ref"],
            "world_model_record": None,
        }
    )
    cases["trajectory_permutation"] = _case(
        simulation=permuted,
        problem=consumer_problem,
        candidate_id=candidate_id,
        atoms=atoms,
    )

    unknown_outcome_problem = consumer_problem.model_copy(
        update={
            "outcome_of_interest": consumer_problem.outcome_of_interest.model_copy(
                update={"target_variable": "foreign_outcome"}
            )
        }
    )
    cases["unknown_outcome"] = _case(
        simulation=valid,
        problem=unknown_outcome_problem,
        candidate_id=candidate_id,
        atoms=atoms,
    )
    sibling_hash = simulation.model_copy(
        update={"simulation_ref": "sha256:" + "0" * 64, "world_model_record": None}
    )
    cases["sibling_receipt_hash"] = _case(
        simulation=sibling_hash,
        problem=consumer_problem,
        candidate_id=candidate_id,
        atoms=atoms,
    )

    removal_controls = {
        "interaction_trajectory_scope_or_grid_mismatch": "duplicate_grid_point",
        "interaction_residual_mismatch": "false_residual",
        "interaction_order_mismatch": "false_orders",
    }
    handoff = {
        "repo_root": str(repo_root),
        "store_root": str(store_root),
        "world_model_record": request.world_model_record.model_dump(mode="json"),
        "producer_pid": os.getpid(),
        "cases": cases,
        "removal_controls": removal_controls,
    }
    env = os.environ.copy()
    source_roots = [str(repo_root / "src"), str(repo_root)]
    if env.get("PYTHONPATH"):
        source_roots.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(source_roots)
    completed = subprocess.run(
        [sys.executable, "-c", _N8_CHILD],
        cwd=repo_root,
        env=env,
        input=json.dumps(handoff),
        capture_output=True,
        check=False,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, (
        f"fresh_n8_process_failed:{completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    observed = json.loads(completed.stdout)
    assert observed["consumer_pid"] != handoff["producer_pid"]
    assert (
        Path(observed["runtime_source"]).resolve()
        == (repo_root / "src/polisyos/runtime/quality/generation_cycle.py").resolve()
    )
    outcomes = observed["cases"]

    failures: list[str] = []
    if outcomes["valid"]["status"] != "value_conditional":
        failures.append(f"valid_artifact_not_conditional:{outcomes['valid']}")
    evidence = outcomes["valid"].get("conditional_interaction_evidence")
    expected_evidence = {
        "schema_version": "policyos.runtime.conditional_simulation_interaction_evidence.v1",
        "horizon_start": 0,
        "horizon_end": 0,
        "horizon_step": 1,
        "requested_steps": [0],
        "observed_steps": [0],
        "trajectory_scope_count": 7,
        "checked_interaction_orders": [1, 2, 3],
        "max_checked_interaction_order": 3,
        "higher_order_residuals": {"firm_survival": {"0": 1.0}},
        "residual_scope": "third_order",
        "predicate_provenance": "recomputed",
        "authority_purpose": "conditional_simulation_only",
        "unit_binding_status": "not_established",
        "time_binding_status": "not_established",
    }
    if evidence != expected_evidence:
        failures.append(f"conditional_interaction_evidence_mismatch:{evidence}")

    for name in (
        "false_residual",
        "false_orders",
        "missing_pair_scope",
        "wrong_horizon_step",
        "duplicate_grid_point",
        "unknown_outcome",
        "sibling_receipt_hash",
    ):
        if outcomes[name]["status"] != "value_blocked":
            failures.append(f"removed_property_keep_markers:{name}:{outcomes[name]}")
        if "joint_simulation_result_integrity_invalid" not in outcomes[name]["authority_blockers"]:
            failures.append(f"wrong_integrity_blocker:{name}:{outcomes[name]}")
    for reason_code, case_name in removal_controls.items():
        probe = observed["removal_controls"][reason_code]
        if probe.get("case") != case_name:
            failures.append(f"wrong_removal_probe_case:{reason_code}:{probe}")
        if not probe["applied"] or probe["removed_guard_count"] < 1:
            failures.append(f"source_mutant_not_applied:{reason_code}:{probe}")
        elif probe["observation"]["status"] != "value_conditional":
            failures.append(f"removal_control_did_not_admit:{reason_code}:{probe}")
    if outcomes["trajectory_permutation"]["status"] != "value_conditional":
        failures.append(f"trajectory_permutation_rejected:{outcomes['trajectory_permutation']}")
    elif outcomes["trajectory_permutation"].get("conditional_interaction_evidence") != evidence:
        failures.append(
            "trajectory_permutation_changed_recomputed_evidence:"
            f"{outcomes['trajectory_permutation']}"
        )
    assert not failures, "\n".join(failures)
