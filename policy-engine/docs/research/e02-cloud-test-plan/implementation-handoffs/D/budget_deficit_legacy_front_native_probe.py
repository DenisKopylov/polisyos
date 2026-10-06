"""Actual legacy frontier consumption of an unavailable fiscal coordinate."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from polisyos.scientist.methods.search import controller as module
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchEvaluatorPorts,
)
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    GDPGrowthObjective,
)
from polisyos.scientist.methods.search.stopping import MaxIterations


def _emit(value: str) -> None:
    sys.stdout.write(value + "\n")


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--source-sha", required=True)
args = parser.parse_args()
if not Path(module.__file__).resolve().is_relative_to(args.source_root.resolve() / "src"):
    raise ValueError("Probe imported source outside the declared immutable snapshot")


class Generator:
    def generate(
        self, history: list[Any], current_best: dict[str, Any] | None, context: dict[str, Any]
    ) -> dict[str, Any]:
        return {"candidate_id": "unavailable-fiscal"}


def evaluate(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulation_results": {"gdp_change": 1.0, "gov_balance": -10.0}
        if candidate["candidate_id"] == "measured"
        else {"gdp_change": 2.0, "gov_balance": False},
        "feedback": {"verdict": "APPROVE"},
    }


controller = SearchController(
    SearchConfig(
        stopping=MaxIterations(2),
        objective=CompositeObjective([GDPGrowthObjective(), BudgetDeficitObjective()]),
        max_iterations_hard_limit=2,
    ),
    candidate_generator=Generator(),
    evaluators=SearchEvaluatorPorts(
        stage_a=lambda candidate, context: (0.0, True), stage_b=evaluate
    ),
)
result = controller.run({}, {"candidate_id": "measured"})


def clean(value: object) -> object:
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else "Inf"
    return value


passed = len(result.pareto_front) == 1 and result.pareto_front[0]["candidate"] == {
    "candidate_id": "measured"
}
_emit(
    json.dumps(
        {
            "source_sha": args.source_sha,
            "caller": str(module.__file__),
            "inputs": [
                {"candidate_id": "measured", "gdp_change": 1.0, "gov_balance": -10.0},
                {"candidate_id": "unavailable-fiscal", "gdp_change": 2.0, "gov_balance": False},
            ],
            "expected": (
                "Unusable fiscal coordinate cannot dominate or replace "
                "complete measured frontier point"
            ),
            "best_candidate": result.best_candidate,
            "best_objective": result.best_objective,
            "front": clean(result.pareto_front),
            "last_raw_details": clean(
                [
                    {"name": value.name, "raw": value.raw_value, "satisfied": value.is_satisfied}
                    for value in result.history[-1].objective_details
                ]
            ),
            "unit": "not_established",
            "served_owner": "not_established",
            "result": "PASS" if passed else "FAIL",
        },
        allow_nan=False,
    )
)
raise SystemExit(0 if passed else 1)
