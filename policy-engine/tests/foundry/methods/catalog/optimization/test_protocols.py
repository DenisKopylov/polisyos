from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.optimization.protocols import (
    AllocationItem,
    OptimizationProblem,
    ResourceConstraint,
)


def test_optimization_problem_rejects_unknown_item_in_constraint() -> None:
    with pytest.raises(ValueError, match="references unknown item"):
        OptimizationProblem(
            problem_id="p1",
            items=(AllocationItem(item_id="a", cost=1.0, benefit=1.0),),
            constraints=(
                ResourceConstraint(
                    constraint_id="c1",
                    coefficients={"missing": 1.0},
                    bound=1.0,
                ),
            ),
        )


def test_problem_from_mapping_parses_payload() -> None:
    payload = {
        "problem_id": "p2",
        "items": [
            {"item_id": "a", "cost": 2.0, "benefit": 5.0},
            {"item_id": "b", "cost": 1.0, "benefit": 2.0, "is_integer": False},
        ],
        "constraints": [
            {
                "constraint_id": "resource",
                "coefficients": {"a": 1.0, "b": 2.0},
                "bound": 3.0,
                "sense": "<=",
            }
        ],
        "objective": "maximize",
        "budget": 4.0,
    }
    problem = OptimizationProblem.from_mapping(payload)
    assert problem.problem_id == "p2"
    assert len(problem.items) == 2
    assert problem.budget == 4.0
