"Read-only STR/DOE source census and native bounded composition witness."

from __future__ import annotations

import ast
import asyncio
import hashlib
import importlib
import json
import os
import platform
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
E_SHA = "ec042402ec91fbdcb51006852e29fe67f38d9452"
D_SHA = "3f38e7cbdc8ba544fe4d0c69d93dbb3a4a629973"
G_SHA = "363e7ae0cb2929a92d9667334fdc0ac3087daf5e"


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*args: str) -> bytes:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(ROOT), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def blob(sha: str, path: str) -> bytes:
    return git("show", f"{sha}:{path}")


def save(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return dotted(node.value) + "." + node.attr
    return ""


symbols = {
    "run_stress_test",
    "generate_adversarial_samples",
    "analyze_search_space",
    "SensitivityAwareCandidateGenerator",
    "StressTestReport",
    "score_metric",
}
all_paths = (
    git("ls-tree", "-r", "--name-only", E_SHA, "--", "policy-engine/src/polisyos")
    .decode()
    .splitlines()
)
python_paths = [p for p in all_paths if p.endswith(".py")]
hit_paths = (
    git("grep", "-l", "-E", "|".join(sorted(symbols)), E_SHA, "--", "policy-engine/src/polisyos")
    .decode()
    .splitlines()
)
hit_paths = [p.partition(":")[2] for p in hit_paths if p.endswith(".py")]
census = {
    "sha": E_SHA,
    "tree": git("rev-parse", f"{E_SHA}^{{tree}}").decode().strip(),
    "tracked_path_denominator": len(all_paths),
    "python_path_denominator": len(python_paths),
    "lexical_hit_python_paths": len(hit_paths),
    "scope": (
        "complete tracked production source lexical filter followed b"
        "y AST call/import census; dynamic aliases outside this stati"
        "c census are not established"
    ),
    "files": [],
}
for p in hit_paths:
    data = blob(E_SHA, p)
    parsed = ast.parse(data, filename=p)
    rows = []
    for n in ast.walk(parsed):
        if isinstance(n, ast.Call):
            name = dotted(n.func)
            if name.split(".")[-1] in symbols or ("SensitivityAwareCandidateGenerator" in name):
                rows.append({"kind": "call", "line": n.lineno, "symbol": name})
        elif isinstance(n, (ast.ImportFrom, ast.Import)):
            for alias in n.names:
                if alias.name.split(".")[-1] in symbols:
                    rows.append(
                        {
                            "kind": "import",
                            "line": n.lineno,
                            "module": getattr(n, "module", None),
                            "symbol": alias.name,
                            "asname": alias.asname,
                        }
                    )
    census["files"].append(
        {
            "path": p,
            "blob": git("rev-parse", f"{E_SHA}:{p}").decode().strip(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "rows": rows,
        }
    )
save("source-census.json", census)

# Only these explicitly listed D modules are composed from immutable Git blobs;
# all E modules remain the fresh pinned root source. No filesystem/source merge.
required_e = [
    "scientist/methods/doe/designs.py",
    "scientist/methods/doe/sampling.py",
    "scientist/methods/doe/analysis.py",
    "scientist/methods/doe/_receipt.py",
    "scientist/methods/doe/stress_report.py",
    "scientist/methods/search/sensitivity_adapter.py",
    "scientist/methods/autotune/sensitivity_bridge.py",
    "scientist/methods/autotune/runtime.py",
]
source = []
for p in required_e:
    path = "policy-engine/src/polisyos/" + p
    data = blob(E_SHA, path)
    actual = (ROOT / path).read_bytes()
    if not (actual == data):
        raise AssertionError(f"Active module does not match E root SHA: {path}")
    source.append(
        {
            "role": "E/root",
            "sha": E_SHA,
            "path": path,
            "blob": git("rev-parse", f"{E_SHA}:{path}").decode().strip(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )

import numpy as np  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
import scipy  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
from polisyos.core.artifacts import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    ArtifactWriteOptions,
    SchemaInfo,
)
from polisyos.core.artifacts.store import (  # noqa: E402 - source-bound fixture
    FileSystemCAS,
)
from polisyos.core.canon import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    CanonSpec,
    from_canonical_bytes,
)

for p in [
    "scientist/methods/search/objective.py",
    "scientist/methods/search/adversarial.py",
    "scientist/policy_design/adversary.py",
]:
    path = "policy-engine/src/polisyos/" + p
    data = blob(D_SHA, path)
    name = "polisyos." + p[:-3].replace("/", ".")
    module = importlib.import_module(name)
    exec(compile(data, f"git:{D_SHA}:{path}", "exec"), module.__dict__)  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input
    source.append(
        {
            "role": "D in-memory exact Git-blob overlay",
            "sha": D_SHA,
            "path": path,
            "blob": git("rev-parse", f"{D_SHA}:{path}").decode().strip(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )

from polisyos.scientist.methods.autotune import (  # noqa: E402 - source-bound fixture
    SequenceCandidateGenerator,
)
from polisyos.scientist.methods.autotune.sensitivity_bridge import (  # noqa: E402 - source-bound fixture
    SensitivityBridge,
)
from polisyos.scientist.methods.doe import (  # noqa: E402 - source-bound fixture
    sampling as sampling_module,
)
from polisyos.scientist.methods.doe.designs import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import (  # noqa: E402 - source-bound fixture
    StressTestReport,
)
from polisyos.scientist.methods.search.adversarial import (  # noqa: E402 - source-bound fixture
    run_stress_test,
)
from polisyos.scientist.methods.search.objective import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    CompositeObjective,
    GDPGrowthObjective,
)
from polisyos.scientist.methods.search.sensitivity_adapter import (  # noqa: E402 - source-bound fixture
    SensitivityAwareCandidateGenerator,
)
from polisyos.scientist.policy_design.adversary import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    ScenarioAdversaryConfig,
    ScenarioAdversaryWorker,
    ScenarioAttackSurface,
)

cas_path = OUT / "cas"
cas = FileSystemCAS(cas_path)
artifacts = []


def read_report(ref: object) -> tuple[StressTestReport, dict]:
    fresh = FileSystemCAS(cas_path)
    manifest = fresh.get_manifest(ref)
    if not (fresh.verify(ref).ok):
        raise AssertionError
    if not (manifest.kind == "scientist.stress_test_report"):
        raise AssertionError
    if not (manifest.artifact_schema.name == "polisyos.scientist.StressTestReport"):
        raise AssertionError
    payload = from_canonical_bytes(fresh.get_bytes(ref))
    loaded = StressTestReport.model_validate(payload)
    artifacts.append(
        {
            "ref": ref.model_dump(mode="json"),
            "manifest": manifest.model_dump(mode="json"),
            "payload": payload,
        }
    )
    return loaded, payload


async def worker_witness(threshold: float | None) -> dict[str, object]:
    # Existing synchronous propose() detects the already-running event loop and
    # uses its native deterministic fallback; no gateway monkeypatch/network call.
    worker = ScenarioAdversaryWorker(
        ScenarioAdversaryConfig(strategy=AdversarialStrategy.GRID_EXTREME, max_scenarios=12)
    )
    specs = [
        ParameterSpec(name=f"x{i}", lower_bound=0, upper_bound=1, unit="dimensionless")
        for i in range(12)
    ]
    surface = ScenarioAttackSurface(
        candidate_id="bounded_native_str_doe",
        parameter_specs=specs,
        vulnerability_threshold=threshold,
    )
    calls = []

    def evaluator(candidate: object, context: object) -> dict[str, object]:
        calls.append({"parameters": {s.name: candidate[s.name] for s in specs}, "context": context})
        return {"simulation_results": {"gdp_change": 1.0 if threshold is not None else -5.0}}

    yielded = 0
    original_product = sampling_module.itertools.product

    def observe_product(*args: object, **kwargs: object) -> None:
        nonlocal yielded
        for row in original_product(*args, **kwargs):
            yielded += 1
            yield row

    sampling_module.itertools.product = observe_product
    try:
        result = worker.execute(
            surface=surface,
            base_objective=CompositeObjective([GDPGrowthObjective()]),
            stage_b_evaluator=evaluator,
            context={"purpose": "generic bounded mechanism fixture"},
            cas=cas,
        )
    finally:
        sampling_module.itertools.product = original_product
    loaded, payload = read_report(result.stress_test_report_ref)
    if not (result.compiled_plan.max_iterations == 96):
        raise AssertionError
    if not (
        len(calls)
        == yielded
        == loaded.metadata["attempted"]
        == loaded.metadata["finite_evaluated"]
        == 96
    ):
        raise AssertionError
    if payload.get("adversarial_plan_ref") is not None:
        raise AssertionError
    if not ("vulnerability_threshold" not in payload["metadata"]):
        raise AssertionError
    if not ("metric_unit" not in payload["metadata"]):
        raise AssertionError
    return {
        "threshold_input": threshold,
        "compiled_plan": result.compiled_plan.model_dump(mode="json"),
        "grid_full_size": 2**12,
        "native_product_rows_yielded": yielded,
        "native_stage_b_calls": len(calls),
        "actual_rows": calls,
        "fresh_report": loaded.model_dump(mode="json"),
        "scenario_bundle_ref": result.adversary_bundle_ref.model_dump(mode="json"),
        "scope": (
            "declared bounded 96/4096 lexicographic corners; no full-spac"
            "e probability/robustness certificate"
        ),
    }


positive = asyncio.run(worker_witness(0.0))
missing = asyncio.run(worker_witness(None))
if not (missing["fresh_report"]["robustness_score"] == 1.0):
    raise AssertionError
if not (missing["fresh_report"]["high_count"] == 0):
    raise AssertionError
if not (missing["fresh_report"]["set_adequacy_status"] == "complete"):
    raise AssertionError

# D occurrence counters are exercised through its actual native runner and the
# unchanged E seeded random-tail producer, with presentation caps varied.
topk = []
for cap in [1, 10]:
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name="x", lower_bound=0, upper_bound=1, unit="dimensionless")
        ],
        strategy=AdversarialStrategy.RANDOM_TAIL,
        max_iterations=10,
        seed=31415,
        vulnerability_threshold=0,
        stop_on_first_vulnerability=False,
        collect_top_k=cap,
    )
    calls = []

    def evaluate(candidate: object, context: object, *, calls: object = calls) -> dict[str, object]:
        calls.append(candidate["x"])
        return {"simulation_results": {"gdp_change": -5}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([GDPGrowthObjective()]),
        stage_b_evaluator=evaluate,
        cas=cas,
    )
    from polisyos.core.artifacts import ArtifactRef

    loaded, payload = read_report(
        ArtifactRef(
            artifact_id=report.cas_artifact_id,
            kind="scientist.stress_test_report",
            media_type="application/json",
        )
    )
    if not (
        loaded.metadata["attempted"]
        == loaded.metadata["finite_evaluated"]
        == loaded.metadata["violated_scenarios"]
        == 10
    ):
        raise AssertionError
    if not (loaded.robustness_score == 0):
        raise AssertionError
    topk.append({"top_k": cap, "rows": calls, "report": loaded.model_dump(mode="json")})
if not (topk[0]["rows"] == topk[1]["rows"]):
    raise AssertionError

# Canonical seeded SALib producer -> content-bound CAS -> actual candidate
# metadata consumer. Its evaluator is a declared analytic fixture, not a served
# or production model. This API has no automatic production caller in the census.
calls = []


def linear(params: object) -> object:
    calls.append({name: float(value) for name, value in params.items()})
    return 2 * params["x"] + params["z"]


answer = SensitivityBridge().analyze_search_space(
    [
        {"name": "x", "lower": 0, "upper": 1, "unit": "dimensionless"},
        {"name": "z", "lower": 0, "upper": 1, "unit": "dimensionless"},
    ],
    linear,
    n_trajectories=4,
    seed=31415,
    store=cas,
)
fresh = FileSystemCAS(cas_path)
native_base = SequenceCandidateGenerator([{"x": 0.2, "z": 0.3}])
consumer = SensitivityAwareCandidateGenerator.from_artifact(
    native_base, fresh, answer["analysis_ref"]
)
candidate = consumer.generate([], None, {})
if not (candidate["_sensitivity"]["ranking"] == ["x", "z"]):
    raise AssertionError
if not (
    candidate["_sensitivity"]["analysis_ref"]["artifact_id"]
    == str(answer["analysis_ref"].artifact_id)
):
    raise AssertionError
if not (candidate["_sensitivity"]["authority_purpose"] == "exploratory_parameter_experiment"):
    raise AssertionError
if not (candidate["_sensitivity"]["population_law_status"] == "not_established"):
    raise AssertionError
analysis_payload = from_canonical_bytes(fresh.get_bytes(answer["analysis_ref"]))
if not (len(calls) == len(analysis_payload["outputs"]) == len(analysis_payload["samples"]) == 12):
    raise AssertionError
if not (
    [p["unit"] for p in analysis_payload["plan"]["parameter_specs"]]
    == [
        "dimensionless",
        "dimensionless",
    ]
):
    raise AssertionError
# Existing D SEARCH_LOOP consumes the real E ranking decorator after its native
# 32-point SciPy LHS initialization. The receipt is observed by the real stage-B
# seam, although D's final persisted stress report does not bind that input ref.
stress_calls = []


def sensitivity_stress_evaluator(candidate: object, context: object) -> dict[str, object]:
    stress_calls.append(
        {
            "x": float(candidate["x"]),
            "z": float(candidate["z"]),
            "sensitivity": candidate.get("_sensitivity"),
        }
    )
    return {"simulation_results": {"gdp_change": 2 * candidate["x"] + candidate["z"]}}


consumer_stress = run_stress_test(
    adversarial_plan=AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name="x", lower_bound=0, upper_bound=1, unit="dimensionless"),
            ParameterSpec(name="z", lower_bound=0, upper_bound=1, unit="dimensionless"),
        ],
        strategy=AdversarialStrategy.SEARCH_LOOP,
        max_iterations=40,
        seed=31415,
        vulnerability_threshold=-10,
        stop_on_first_vulnerability=False,
    ),
    base_objective=CompositeObjective([GDPGrowthObjective()]),
    stage_b_evaluator=sensitivity_stress_evaluator,
    candidate_generator=consumer,
    cas=cas,
)
from polisyos.core.artifacts import (  # noqa: E402 - source-bound fixture
    ArtifactRef,
)

stress_loaded, stress_payload = read_report(
    ArtifactRef(
        artifact_id=consumer_stress.cas_artifact_id,
        kind="scientist.stress_test_report",
        media_type="application/json",
    )
)
if not (len(stress_calls) == stress_loaded.metadata["attempted"] == 40):
    raise AssertionError
if not (sum(row["sensitivity"] is not None for row in stress_calls) == 8):
    raise AssertionError
if not (
    all(
        row["sensitivity"]["analysis_ref"] == candidate["_sensitivity"]["analysis_ref"]
        for row in stress_calls
        if row["sensitivity"]
    )
):
    raise AssertionError
fake_payload = json.loads(json.dumps(analysis_payload))
fake_payload["result"]["mu_star"]["x"] = 999.0
fake = cas.put_json(
    fake_payload,
    ArtifactWriteOptions(
        kind="doe_sensitivity_analysis",
        media_type="application/json",
        schema=SchemaInfo(name="doe_sensitivity_analysis", version="1.0"),
    ),
    canon_spec=CanonSpec(forbid_floats=False),
)
try:
    SensitivityAwareCandidateGenerator.from_artifact(native_base, FileSystemCAS(cas_path), fake)
except ValueError as exc:
    refusal = {"type": type(exc).__name__, "message": str(exc)}
else:
    raise AssertionError("Fabricated numerical sensitivity index was admitted")

oversize_calls = []
try:
    SensitivityBridge().analyze_search_space(
        [
            {"name": "x", "lower": 0, "upper": 1},
            {"name": "z", "lower": 0, "upper": 1},
        ],
        lambda p: oversize_calls.append(p) or 0.0,
        n_trajectories=4,
        seed=31415,
        max_estimated_runs=11,
    )
except ValueError as exc:
    oversized = {
        "type": type(exc).__name__,
        "message": str(exc),
        "evaluator_calls": len(oversize_calls),
    }
else:
    raise AssertionError("Oversized DOE sensitivity plan was admitted")
if oversize_calls:
    raise AssertionError

save(
    "native-deciding.json",
    {
        "kind": (
            "bounded generic native mechanism; no pro"  # Exact bound literal continuation.
            "duction history/sampling-law admission"  # Exact bound literal continuation.
        ),
        "source": source,
        "E_sha": E_SHA,
        "D_sha": D_SHA,
        "G_audit_sha": G_SHA,
        "composition": (
            "Exact three D Git blobs executed in memory over unchanged E "
            "root modules, not accepted D integration/code"
        ),
        "environment": {
            "executable": sys.executable,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "SALib": importlib.metadata.version("SALib"),
            "cpu_count": os.cpu_count(),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
            "caps_added": False,
        },
        "worker_positive": positive,
        "missing_threshold_D_escape": missing,
        "top_k_occurrence_invariance": topk,
        "sensitivity": {
            "analytic_statistic": "y=2*x+z; expected unit-coordinate Morris mu_star x=2,z=1",
            "calls": calls,
            "receipt_ref": answer["analysis_ref"].model_dump(mode="json"),
            "manifest": fresh.get_manifest(answer["analysis_ref"]).model_dump(mode="json"),
            "payload": analysis_payload,
            "candidate": candidate,
            "stress_actual_generator_consumer": {
                "requested": 40,
                "native_LHS_rows": 32,
                "actual_E_decorated_generator_rows": 8,
                "actual_stage_b_inputs": stress_calls,
                "fresh_report": stress_payload,
                "carrier_scope": (
                    "Existing caller accepts the explicit dec"
                    "orated generator; report manifest has no"
                    " consumed DOE analysis input ref, no aut"
                    "omatic production wiring is claimed"
                ),
            },
            "present_but_fake_ref": fake.model_dump(mode="json"),
            "present_but_fake_refusal": refusal,
            "oversized_pre_callback_refusal": oversized,
        },
        "runtime_checkout": {
            "sha": git("rev-parse", "HEAD").decode().strip(),
            "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
            "E_hot_path_files_match_pinned_root": True,
            "whole_root_checkout_claim": False,
            "other_root_delta_paths": git(
                "diff", "--name-only", E_SHA, "HEAD", "--", "policy-engine/src"
            )
            .decode()
            .splitlines(),
        },
        "stress_artifacts": artifacts,
        "limitations": [
            "No E code merged D source; overlay composition only",
            "D missing-threshold complete/score1 escape remains D-owned",
            (
                "Stress report contains no persisted plan ref/threshold/metri"
                "c unit/statistic version or source-law carrier"
            ),
            (
                "DOE sensitivity owns exploratory_parameter_experiment receip"
                "t, no automatic stress probability/threshold certificate"
            ),
            (
                "Blueprint regrouping denominator remains"
                " D-owned and was not dynamically execute"
                "d here"
            ),
            (
                "Production history and population-law ad"  # Exact bound literal continuation.
                "missibility remain local owner checks"  # Exact bound literal continuation.
            ),
        ],
    },
)
_write_stdout(
    json.dumps(
        {
            "outcome": "bounded E native properties PASS; D missing-threshold escape reproduced",
            "worker_rows": 96,
            "grid_space": 4096,
            "topk_occurrence_counts": [x["report"]["metadata"]["violated_scenarios"] for x in topk],
            "Morris_rows": len(calls),
            "fake_index_refusal": refusal,
            "oversized": oversized,
            "output": str(OUT / "native-deciding.json"),
        }
    )
)
