"Independent exact old source falsifier, replacing SALib sample only with a counted spy."

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
from SALib.sample import fast_sampler, morris, sobol

from polisyos.scientist.methods.doe import analysis, sampling
from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityMethod, SensitivityPlan


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


BASE = "a2677935015e8a0e7f2dfd5412b671e13fb3175a"
LANE = Path("/workspace/e02-E-continuation-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/doe-budget")


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


def git(*args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(LANE), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def sha(x: object) -> str:
    return hashlib.sha256(x).hexdigest()


paths = git("ls-files", "policy-engine/src").decode().splitlines()
before = {p: sha((LANE / p).read_bytes()) for p in paths}
if not (all((LANE / p).read_bytes() == git("show", BASE + ":" + p) for p in paths)):
    raise AssertionError


class BackendReachedError(RuntimeError):
    pass


cases = []
for method, backend in [
    (SensitivityMethod.MORRIS, morris),
    (SensitivityMethod.SOBOL, sobol),
    (SensitivityMethod.FAST, fast_sampler),
]:
    n = 65 if method == SensitivityMethod.FAST else 2
    k = 2
    factor = {
        SensitivityMethod.MORRIS: k + 1,
        SensitivityMethod.SOBOL: 2 * k + 2,
        SensitivityMethod.FAST: k,
    }[method]
    cap = n * factor
    plan = SensitivityPlan(
        method=method,
        parameter_specs=[
            ParameterSpec(name=name, lower_bound=0, upper_bound=1) for name in ["x", "z"]
        ],
        n_trajectories=n,
        max_estimated_runs=cap,
        seed=19,
        input_law="independent",
    )
    if not (plan.estimated_runs == cap):
        raise AssertionError
    plan.n_trajectories = n + 1
    calls = []

    def spy(*args: object, calls: object = calls, **kwargs: object) -> None:
        calls.append({"N": kwargs.get("N"), "num_vars": args[0]["num_vars"]})
        raise BackendReachedError("real SALib sample inlet reached")

    for path in ["generate", "identity"]:
        calls.clear()
        with patch.object(backend, "sample", spy):
            try:
                if path == "generate":
                    sampling.generate_sensitivity_samples(plan)
                else:
                    analysis._analysis_identity(plan, np.zeros((cap, k)), np.zeros(cap))
                outcome = "ACCEPTED_identity_without_budget_admission"
            except BackendReachedError:
                outcome = "BACKEND_REACHED_before_budget_refusal"
            except Exception as e:
                outcome = type(e).__name__ + ":" + str(e)
        if path == "generate" or method == SensitivityMethod.SOBOL:
            if not (calls == [{"N": n + 1, "num_vars": k}]):
                raise AssertionError
        else:
            if not (outcome == "ACCEPTED_identity_without_budget_admission" and not calls):
                raise AssertionError
        cases.append(
            {
                "method": method.value,
                "path": path,
                "admitted_N": n,
                "mutated_N": n + 1,
                "declared_cap": cap,
                "actual_estimated": (n + 1) * factor,
                "backend_calls": list(calls),
                "evaluator_calls": 0,
                "outcome": outcome,
                "property_outcome": "FAIL_expected_escape",
            }
        )
if not (all(before[p] == sha((LANE / p).read_bytes()) for p in paths)):
    raise AssertionError
origins = {
    n: str(Path(m.__file__).resolve())
    for n, m in sys.modules.items()
    if n.startswith("polisyos") and getattr(m, "__file__", None)
}
if not (
    all(
        Path(p).is_relative_to(LANE / "policy-engine/src")
        and Path(p).read_bytes() == git("show", BASE + ":" + str(Path(p).relative_to(LANE)))
        for p in origins.values()
    )
):
    raise AssertionError
result = {
    "source": BASE,
    "tree": git("rev-parse", BASE + "^{tree}").decode().strip(),
    "module_source": {
        n: sha(Path(m.__file__).read_bytes())
        for n, m in sys.modules.items()
        if n
        in [
            "polisyos.scientist.methods.doe.designs",
            "polisyos.scientist.methods.doe.sampling",
            "polisyos.scientist.methods.doe.analysis",
        ]
    },
    "tracked_source_count": len(paths),
    "tracked_source_digest": sha(json.dumps(before, sort_keys=True).encode()),
    "before_after_equal": True,
    "all_module_origins_exact_Git_blobs": True,
    "origin_count": len(origins),
    "environment": {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "SALib": "1.5.2",
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "backend_scope": (
            "actual SALib inlet intercepted before allocation; no numeric estimator claim"
        ),
        "no_caps": True,
    },
    "cases": cases,
    "negative_control_basis": (
        "Only sample function spy replaced; real generate/identity ca"
        "ller and admitted mutation execute exact old source."
    ),
}
(OUT / "baseline-a267-falsifier.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
