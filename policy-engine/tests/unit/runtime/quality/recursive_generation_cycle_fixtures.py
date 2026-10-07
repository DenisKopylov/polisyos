"""Small shared fixtures for recursive generation-cycle tests."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    intervention_atom_content_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _recursive_problem(node_ref: str) -> DesignProblem:
    payload = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json"
        ).read_text(encoding="utf-8")
    )["design_problem"]
    problem = DesignProblem.model_validate(payload)
    return problem.model_copy(
        update={
            "design_problem_id": "recursive_" + node_ref.rsplit("/", 1)[-1],
            "objectives": [
                problem.objectives[0].model_copy(update={"metric_id": "final_queue_length"})
            ],
            "outcome_of_interest": problem.outcome_of_interest.model_copy(
                update={
                    "target_variable": "final_queue_length",
                    "metric_id": "final_queue_length",
                    "estimand": "effect on the final claims queue length",
                    "direction": "minimize",
                }
            ),
        }
    )


def _lane0_coupled_request(
    *,
    parent_ref: str,
    child_refs: tuple[str, str],
    problem: DesignProblem,
) -> Any:
    module = import_module(
        "tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract"
    )
    request = cast("Any", module)._coupled_request()
    graph = request.coupling_graph
    assert graph is not None
    edges = tuple(
        edge.model_copy(
            update={
                "source_module_ref": child_refs[0],
                "target_module_ref": child_refs[1],
            }
        )
        for edge in graph.interaction_edges
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    atoms: list[InterventionAtomBinding] = []
    for atom in request.intervention_atoms:
        draft = atom.model_copy(update={"problem_frame_ref": problem_ref})
        content_hash = intervention_atom_content_hash(draft)
        bound = draft.model_copy(
            update={
                "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
                "content_hash": content_hash,
            }
        )
        atoms.append(InterventionAtomBinding.model_validate(bound.model_dump(mode="python")))
    return request.model_copy(
        update={
            "intervention_atoms": tuple(atoms),
            "coupling_graph": graph.model_copy(
                update={
                    "design_ref": parent_ref,
                    "module_refs": child_refs,
                    "interaction_edges": edges,
                    "evidence_state": "observed",
                }
            ),
        }
    )
