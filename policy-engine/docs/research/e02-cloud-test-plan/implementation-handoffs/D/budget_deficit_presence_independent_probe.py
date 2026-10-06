"""Independent B108 raw-value audit; no fiscal unit or billing claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from polisyos.scientist.methods.search import objective as objective_module
from polisyos.scientist.methods.search import controller as controller_module
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchEvaluatorPorts,
)
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.methods.search.stopping import MaxIterations

parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--source-sha", required=True)
args = parser.parse_args()
ROOT = args.source_root.resolve()
SOURCE = args.source_sha
assert len(SOURCE) == 40 and all(char in "0123456789abcdef" for char in SOURCE)
for module in (objective_module, controller_module):
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(ROOT / "src")
    print(
        json.dumps(
            {
                "source": SOURCE,
                "module": module.__name__,
                "origin": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    )


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else "Inf" if value > 0 else "-Inf"
    if type(value) is int and abs(value) > 10**100:
        return {"type": "int", "exact_expression": "10**400", "decimal_digits": len(str(value))}
    return value


CASES = [
    ("absent-all", {}, None),
    (
        "null-all",
        {"gov_balance": None, "government_balance": None, "budget_deficit": None, "deficit": None},
        None,
    ),
    ("absent-primary-valid-deficit", {"budget_deficit": 17.25}, 17.25),
    ("null-primary-valid-deficit", {"gov_balance": None, "budget_deficit": 17.25}, 17.25),
    ("null-primary-valid-balance-alias", {"gov_balance": None, "government_balance": -12.5}, 12.5),
    ("zero-primary-wins", {"gov_balance": 0.0, "budget_deficit": 99.0}, 0.0),
    ("zero-balance-alias-wins", {"government_balance": 0.0, "deficit": 99.0}, 0.0),
    ("negative-balance-deficit", {"gov_balance": -12.5}, 12.5),
    ("positive-balance-surplus", {"gov_balance": 12.5}, 0.0),
    ("negative-deficit-absolute", {"deficit": -12.5}, 12.5),
    ("equal-balance-aliases", {"gov_balance": -12.5, "government_balance": -12.5}, 12.5),
    ("conflicting-balance-aliases", {"gov_balance": -12.5, "government_balance": 12.5}, None),
    ("equal-deficit-aliases", {"budget_deficit": 12.5, "deficit": 12.5}, 12.5),
    ("conflicting-deficit-aliases", {"budget_deficit": 12.5, "deficit": 15.0}, None),
    ("present-malformed-primary-no-fallback", {"gov_balance": "bad", "budget_deficit": 99.0}, None),
    ("present-malformed-deficit-no-fallback", {"budget_deficit": "bad", "deficit": 99.0}, None),
    ("present-nan-primary-no-fallback", {"gov_balance": math.nan, "budget_deficit": 99.0}, None),
    ("present-inf-primary-no-fallback", {"gov_balance": math.inf, "budget_deficit": 99.0}, None),
    ("bool-false-primary-no-favorable-zero", {"gov_balance": False, "budget_deficit": 99.0}, None),
    ("bool-true-primary-no-favorable-zero", {"gov_balance": True}, None),
    ("bool-false-alias-no-favorable-zero", {"government_balance": False}, None),
    ("bool-false-deficit-no-favorable-zero", {"budget_deficit": False}, None),
    ("bool-true-deficit-not-measurement", {"deficit": True}, None),
    ("overflow-integer-primary-unavailable", {"gov_balance": 10**400, "deficit": 99.0}, None),
]
failed = 0
for name, metrics, expected in CASES:
    try:
        value = BudgetDeficitObjective().evaluate(metrics)
        passed = (
            (math.isnan(value.raw_value) and value.is_satisfied is False)
            if expected is None
            else (
                value.raw_value == expected
                and value.is_satisfied is True
                and value.direction.value == "minimize"
            )
        )
        output = {
            "raw_value": clean(value.raw_value),
            "normalized_value": clean(value.normalized_value),
            "weighted_value": clean(value.weighted_value),
            "is_satisfied": value.is_satisfied,
        }
    except Exception as exc:
        passed = False
        output = {"exception_type": type(exc).__name__, "exception": str(exc)}
    failed += not passed
    print(
        json.dumps(
            {
                "cell": name,
                "input": clean(metrics),
                "expected": "unavailable" if expected is None else expected,
                "observed": output,
                "result": "PASS" if passed else "FAIL",
            },
            allow_nan=False,
        )
    )

# Report representational limits without inventing a unit or a stricter legacy codec.
for metrics in (
    {"gov_balance": "0"},
    {"budget_deficit": "12.5"},
    {"gov_balance": -5.0, "budget_deficit": 99.0},
):
    value = BudgetDeficitObjective().evaluate(metrics)
    print(
        json.dumps(
            {
                "cell": "raw-representation-boundary",
                "input": metrics,
                "raw_value": value.raw_value,
                "is_satisfied": value.is_satisfied,
                "unit": "not_established",
                "result": "OBSERVED_ONLY",
            }
        )
    )


class Generator:
    def generate(self, history, current_best, context):
        del history, current_best, context
        return {"candidate_id": "challenger"}


for name, challenger in [
    ("bool-false", {"gov_balance": False, "budget_deficit": 99.0}),
    ("missing", {}),
    ("overflow-int", {"gov_balance": 10**400}),
]:
    calls = []

    def stage_b(candidate, context):
        del context
        calls.append(candidate["candidate_id"])
        return {
            "simulation_results": {"gov_balance": -10.0}
            if candidate["candidate_id"] == "seed"
            else challenger,
            "feedback": {"verdict": "APPROVE"},
        }

    controller = SearchController(
        SearchConfig(
            stopping=MaxIterations(2),
            objective=CompositeObjective([BudgetDeficitObjective()]),
            max_iterations_hard_limit=2,
        ),
        candidate_generator=Generator(),
        evaluators=SearchEvaluatorPorts(
            stage_a=lambda candidate, context: (0.0, True), stage_b=stage_b
        ),
    )
    try:
        result = controller.run({}, {"candidate_id": "seed"})
        passed = (
            result.best_candidate == {"candidate_id": "seed"}
            and result.best_objective == 10.0
            and len(result.history) == 2
        )
        observed = {
            "best_candidate": result.best_candidate,
            "best_objective": clean(result.best_objective),
            "history": [
                {
                    "candidate": row.candidate,
                    "objective_value": clean(row.objective_value),
                    "details": [
                        {"raw_value": clean(detail.raw_value), "is_satisfied": detail.is_satisfied}
                        for detail in row.objective_details
                    ],
                }
                for row in result.history
            ],
            "stage_b_calls": calls,
        }
    except Exception as exc:
        passed = False
        observed = {
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "stage_b_calls": calls,
        }
    failed += not passed
    print(
        json.dumps(
            {
                "cell": "native-service-controller-" + name,
                "input": clean(challenger),
                "expected": "unusable challenger cannot replace seed or escape raw metric normalization",
                "observed": observed,
                "result": "PASS" if passed else "FAIL",
            },
            allow_nan=False,
        )
    )

print(
    json.dumps(
        {
            "deciding_cases": len(CASES) + 3,
            "passed": len(CASES) + 3 - failed,
            "failed": failed,
            "observations_only": 3,
            "unit": "not_established",
            "served_owner_input_binding": "not_established",
        }
    )
)
raise SystemExit(1 if failed else 0)
