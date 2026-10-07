(
    "Property-removal and direction controls;"  # Exact bound literal continuation.
    " no source writes or production claims."  # Exact bound literal continuation.
)

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-backtest-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/doe-stress-dependency")
E = "ec042402ec91fbdcb51006852e29fe67f38d9452"
D = "3f38e7cbdc8ba544fe4d0c69d93dbb3a4a629973"


def source(sha: str, p: object) -> object:
    return subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [
            _resolve_executable("git"),
            "-C",
            str(ROOT),
            "show",
            sha + ":policy-engine/src/polisyos/" + p,
        ]
    )


from polisyos.scientist.methods.doe import (  # noqa: E402 - source-bound fixture
    sampling,
)
from polisyos.scientist.methods.doe.designs import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)

original = source(E, "scientist/methods/doe/sampling.py")
needle = (
    b"return np.array(list(itertools.islice(co"  # Exact bound literal continuation.
    b"rners, plan.max_iterations)), dtype=floa"  # Exact bound literal continuation.
    b"t)"  # Exact bound literal continuation.
)
if not (original.count(needle) == 1):
    raise AssertionError
removed = original.replace(
    needle, b"return np.array(list(corners), dtype=float)[:plan.max_iterations].copy()"
)
namespace = dict(sampling.__dict__)
exec(compile(removed, "property-removal:cap-after-materialization", "exec"), namespace)  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input
plan = AdversarialPlan(
    parameter_specs=[ParameterSpec(name=f"x{i}", lower_bound=0, upper_bound=1) for i in range(12)],
    strategy=AdversarialStrategy.GRID_EXTREME,
    max_iterations=3,
)
measurements = []
product = sampling.itertools.product
for label, fn in [
    ("native", sampling.generate_adversarial_samples),
    ("cap-property-removed", namespace["generate_adversarial_samples"]),
]:
    count = [0]

    def observe(*args: object, count: object = count, **kwargs: object) -> None:
        for row in product(*args, **kwargs):
            count[0] += 1
            yield row

    sampling.itertools.product = observe
    try:
        values = fn(plan)
    finally:
        sampling.itertools.product = product
    measurements.append(
        {
            "case": label,
            "product_rows_materialized": count[0],
            "output_shape": list(values.shape),
            "output_owns_memory": values.base is None,
            "output_values": values.tolist(),
            "old_output_shape_proxy": "PASS" if values.shape == (3, 12) else "FAIL",
            "defining_predicate": "PASS" if count[0] == 3 else "FAIL",
        }
    )
if not (measurements[0]["product_rows_materialized"] == 3):
    raise AssertionError
if not (measurements[1]["product_rows_materialized"] == 4096):
    raise AssertionError
if not (measurements[0]["output_values"] == measurements[1]["output_values"]):
    raise AssertionError

for p in ["scientist/methods/search/objective.py", "scientist/methods/search/adversarial.py"]:
    module = importlib.import_module("polisyos." + p[:-3].replace("/", "."))
    exec(compile(source(D, p), "git:" + D + ":" + p, "exec"), module.__dict__)  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input
from polisyos.scientist.methods.search.adversarial import (  # noqa: E402 - source-bound fixture
    run_stress_test,
)
from polisyos.scientist.methods.search.objective import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    BudgetDeficitObjective,
    CompositeObjective,
    GDPGrowthObjective,
)

direction = []
for label, objective, metric in [
    ("maximize-utility", GDPGrowthObjective(), "gdp_change"),
    ("minimize-cost", BudgetDeficitObjective(), "budget_deficit"),
]:
    calls = []
    p = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="x", lower_bound=-5, upper_bound=10)],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=2,
        vulnerability_threshold=0,
        stop_on_first_vulnerability=False,
    )

    def evaluator(
        candidate: object, context: object, *, calls: object = calls, metric: object = metric
    ) -> dict[str, object]:
        calls.append(float(candidate["x"]))
        return {"simulation_results": {metric: candidate["x"]}}

    report = run_stress_test(
        adversarial_plan=p,
        base_objective=CompositeObjective([objective]),
        stage_b_evaluator=evaluator,
    )
    expected = -5 if label == "maximize-utility" else 10
    if not (report.worst_case_parameters["x"] == expected):
        raise AssertionError
    if not (report.metadata["attempted"] == report.metadata["finite_evaluated"] == 2):
        raise AssertionError
    direction.append(
        {
            "case": label,
            "input_raw_values": calls,
            "actual_component_direction": objective.direction.value,
            "composite_normalization": "typed components contribute weighted minimization values",
            "threshold": 0,
            "worst_parameter_oracle": expected,
            "native_report": report.model_dump(mode="json"),
            "outcome": "PASS",
        }
    )

result = {
    "E_source": E,
    "D_overlay": D,
    "negative_source_sha256": hashlib.sha256(removed).hexdigest(),
    "source_mutation": (
        "in-memory only, move cap after full list/array then copy; sh"
        "ape and owned-memory proxies intentionally unchanged"
    ),
    "materialization_control": measurements,
    "direction_controls": direction,
    "authority": (
        "generic analytic table fixtures; declared threshold in norma"
        "lized composite units; no served evaluator or trust probabil"
        "ity"
    ),
}
(OUT / "controls-deciding.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
_write_stdout(
    json.dumps(
        {
            "control_results": [
                {
                    "case": m["case"],
                    "yielded": m["product_rows_materialized"],
                    "proxy": m["old_output_shape_proxy"],
                    "predicate": m["defining_predicate"],
                }
                for m in measurements
            ],
            "direction_cases": [x["case"] for x in direction],
            "output": str(OUT / "controls-deciding.json"),
        }
    )
)
