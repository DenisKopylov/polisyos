"""Independent mutable-plan budget/canonical-snapshot caller controls."""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from SALib.analyze import fast as fast_analyzer
from SALib.analyze import morris as morris_analyzer
from SALib.analyze import sobol as sobol_analyzer
from SALib.sample import fast_sampler, morris, sobol

from polisyos.core.artifacts import FileSystemCAS
from polisyos.scientist.methods.doe import (
    _receipt,
    adaptive,
    analysis,
    designs,
    multi_output,
    sampling,
    stability,
)
from polisyos.scientist.methods.doe.designs import (
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
    SensitivityResult,
)


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


RESULTS = []


def plan(
    method: object = SensitivityMethod.MORRIS,
    n: int | None = None,
    cap: int | None = None,
    allow: bool = False,
) -> object:
    n = (65 if method == SensitivityMethod.FAST else 2) if n is None else n
    factor = {SensitivityMethod.MORRIS: 3, SensitivityMethod.SOBOL: 6, SensitivityMethod.FAST: 2}[
        method
    ]
    return SensitivityPlan(
        method=method,
        parameter_specs=[
            ParameterSpec(name=x, lower_bound=0, upper_bound=1, unit="normalized")
            for x in ["x", "z"]
        ],
        n_trajectories=n,
        max_estimated_runs=n * factor if cap is None else cap,
        allow_large_run=allow,
        seed=29,
        input_law="independent",
    )


def corrupted(kind: str) -> object:
    p = plan()
    if kind == "N":
        p.n_trajectories = 3
    elif kind == "dimension":
        p.parameter_specs.append(ParameterSpec(name="q", lower_bound=0, upper_bound=1))
    elif kind == "method":
        p.method = SensitivityMethod.SOBOL
    elif kind == "cap":
        p.max_estimated_runs = 5
    elif kind == "copy":
        p = p.model_copy(update={"n_trajectories": 3})
    elif kind == "construct":
        p = SensitivityPlan.model_construct(**(p.model_dump(mode="python") | {"n_trajectories": 3}))
    return p


class BackendReachedError(RuntimeError):
    pass


class StoreSpy:
    def __init__(self) -> None:
        self.calls = 0

    def put_json(self, *a: object, **kw: object) -> None:
        self.calls += 1
        raise BackendReachedError("CAS write reached")


def forbidden_callbacks(stack: object) -> object:
    calls = []

    def reached(*a: object, **kw: object) -> None:
        calls.append({"N": kw.get("N"), "kind": "SALib"})
        raise BackendReachedError("SALib inlet reached")

    for mod, fn in [
        (morris, "sample"),
        (sobol, "sample"),
        (fast_sampler, "sample"),
        (morris_analyzer, "analyze"),
        (sobol_analyzer, "analyze"),
        (fast_analyzer, "analyze"),
    ]:
        stack.enter_context(patch.object(mod, fn, reached))
    return calls


@pytest.mark.parametrize("corruption", ["N", "dimension", "method", "cap", "copy", "construct"])
@pytest.mark.parametrize(
    "boundary",
    [
        "generate",
        "problem",
        "identity",
        "prepare",
        "analyze",
        "persist",
        "adaptive",
        "PCA",
        "stability",
    ],
)
def test_same_cap_quantity_every_boundary_before_backend_evaluator_or_cas(
    corruption: object, boundary: object
) -> None:
    p = corrupted(corruption)
    store = StoreSpy()
    evaluations = []
    # Supplied tiny arrays are caller inputs, not backend allocations. Budget
    # denial must precede geometry/analyzer/PCA/evaluator/receipt materialization.
    samples = np.zeros((6, 2))
    outputs = np.arange(6, dtype=float)
    with ExitStack() as stack:
        callbacks = forbidden_callbacks(stack)

        def evaluator(x: object) -> None:
            evaluations.append(x.shape)
            raise BackendReachedError("evaluator reached")

        def run() -> object:
            if boundary == "generate":
                return sampling.generate_sensitivity_samples(p)
            if boundary == "problem":
                return designs._build_salib_problem(p)
            if boundary == "identity":
                return analysis._analysis_identity(p, samples, outputs)
            if boundary == "prepare":
                return analysis._prepare_analysis_inputs(p, samples, outputs)
            if boundary == "analyze":
                return analysis.analyze_sensitivity(p, samples, outputs)
            if boundary == "persist":
                return _receipt._persist_analysis(
                    store,
                    p,
                    samples,
                    outputs,
                    SensitivityResult(method=SensitivityMethod.MORRIS, parameter_names=["x", "z"]),
                )
            if boundary == "adaptive":
                return adaptive.AdaptiveSampler(
                    p, adaptive.ConvergenceConfig(max_rounds=1, trajectory_step=1)
                ).run(evaluator)
            if boundary == "PCA":
                return multi_output.MultiOutputAnalyzer().analyze(
                    p, samples, np.column_stack((outputs, 2 * outputs))
                )
            return stability.RankingStabilityChecker(n_bootstrap=5).check(p, samples, outputs)

        with pytest.raises(ValueError, match="estimated_runs exceeds max_estimated_runs"):
            run()
        if not (callbacks == [] and evaluations == [] and store.calls == 0):
            raise AssertionError
    RESULTS.append(
        {
            "boundary": boundary,
            "corruption": corruption,
            "outcome": "REFUSED_before_backend",
            "SALib_calls": 0,
            "evaluator_calls": 0,
            "CAS_writes": 0,
        }
    )


@pytest.mark.parametrize(
    "method", [SensitivityMethod.MORRIS, SensitivityMethod.SOBOL, SensitivityMethod.FAST]
)
def test_all_sampler_families_mutated_n_refused_before_salib(method: object) -> None:
    p = plan(method)
    p.n_trajectories += 1
    with ExitStack() as stack:
        callbacks = forbidden_callbacks(stack)
        with pytest.raises(ValueError, match="estimated_runs exceeds max_estimated_runs"):
            sampling.generate_sensitivity_samples(p)
        if not (callbacks == []):
            raise AssertionError


@pytest.mark.parametrize(
    "method", [SensitivityMethod.MORRIS, SensitivityMethod.SOBOL, SensitivityMethod.FAST]
)
def test_native_within_cap_preserves_canonical_salib_rows_and_bounds(method: object) -> None:
    p = plan(method)
    samples = sampling.generate_sensitivity_samples(p)
    # Independent run denominator: Morris N(k+1), Sobol N(2k+2), FAST Nk.
    factor = {SensitivityMethod.MORRIS: 3, SensitivityMethod.SOBOL: 6, SensitivityMethod.FAST: 2}[
        method
    ]
    if not (samples.shape == (p.n_trajectories * factor, 2)):
        raise AssertionError
    if not (samples.dtype == np.float64 and np.isfinite(samples).all()):
        raise AssertionError
    if not (np.all((samples >= 0) & (samples <= 1)) and p.estimated_runs == p.max_estimated_runs):
        raise AssertionError
    RESULTS.append(
        {
            "native_method": method.value,
            "N": p.n_trajectories,
            "k": 2,
            "rows": len(samples),
            "cap": p.max_estimated_runs,
            "SALib": version("SALib"),
        }
    )


def test_native_declared_large_run_permission_does_not_silently_widen_cap() -> None:
    p = plan(n=3, cap=6, allow=True)
    samples = sampling.generate_sensitivity_samples(p)
    if not (samples.shape == (9, 2) and p.max_estimated_runs == 6 and p.allow_large_run is True):
        raise AssertionError


def test_generator_callback_mutation_does_not_change_admitted_profile_or_nested_fields() -> None:
    p = plan()
    expected = plan()
    actual = sampling.generate_sensitivity_samples(expected)
    real = morris.sample
    calls = []

    def counted(problem: object, *args: object, **kwargs: object) -> object:
        calls.append(
            {
                "N": kwargs["N"],
                "names": list(problem["names"]),
                "bounds": [list(x) for x in problem["bounds"]],
            }
        )
        p.n_trajectories = 999
        p.parameter_specs[0].upper_bound = 100
        p.parameter_specs.append(ParameterSpec(name="q", lower_bound=0, upper_bound=1))
        return real(problem, *args, **kwargs)

    with patch.object(morris, "sample", counted):
        samples = sampling.generate_sensitivity_samples(p)
    np.testing.assert_array_equal(samples, actual)
    if not (calls == [{"N": 2, "names": ["x", "z"], "bounds": [[0.0, 1.0], [0.0, 1.0]]}]):
        raise AssertionError
    if not (p.n_trajectories == 999 and len(p.parameter_specs) == 3):
        raise AssertionError


def test_identity_backend_mutation_does_not_bind_late_original_plan() -> None:
    p = plan(SensitivityMethod.SOBOL)
    p0 = plan(SensitivityMethod.SOBOL)
    samples = sampling.generate_sensitivity_samples(p0)
    outputs = samples[:, 0] + 2 * samples[:, 1]
    expected = analysis._analysis_identity(p0, samples, outputs)
    real = sobol.sample

    def counted(*args: object, **kwargs: object) -> object:
        p.n_trajectories = 999
        p.seed = 100
        p.parameter_specs[0].unit = "late_fake_unit"
        return real(*args, **kwargs)

    with patch.object(sobol, "sample", counted):
        actual = analysis._analysis_identity(p, samples, outputs)
    if not (
        actual == expected
        and actual["parameter_units"]
        == {
            "x": "normalized",
            "z": "normalized",
        }
    ):
        raise AssertionError


def test_real_native_analysis_cas_fresh_readback_and_overcap_forgery_refusal(
    tmp_path: Path,
) -> None:
    p = plan(n=4)
    samples = sampling.generate_sensitivity_samples(p)
    outputs = samples[:, 0] + 2 * samples[:, 1]
    result = analysis.analyze_sensitivity(p, samples, outputs)
    np.testing.assert_allclose(
        [result.mu_star["x"], result.mu_star["z"]], [1.0, 2.0], rtol=0, atol=1e-14
    )
    if not (
        result.ranking == ["z", "x"]
        and (
            result.total_runs,
            result.successful_runs,
            result.failed_runs,
        )
        == (12, 12, 0)
    ):
        raise AssertionError
    store = FileSystemCAS(tmp_path / "cas")
    ref = _receipt._persist_analysis(store, p, samples, outputs, result)
    fresh = FileSystemCAS(tmp_path / "cas")
    reopened = _receipt._load_analysis(fresh, ref)
    if not (reopened.model_dump(mode="json") == result.model_dump(mode="json")):
        raise AssertionError
    from polisyos.core.artifacts import PutOptions, SchemaInfo
    from polisyos.core.canon import CanonSpec, from_canonical_bytes

    payload = from_canonical_bytes(fresh.get_bytes(ref))
    payload["plan"]["n_trajectories"] = 5
    fake = fresh.put_json(
        payload,
        PutOptions(
            kind="doe_sensitivity_analysis",
            media_type="application/json",
            schema=SchemaInfo(name="doe_sensitivity_analysis", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    if not (fresh.verify(fake).ok):
        raise AssertionError
    with ExitStack() as stack:
        callbacks = forbidden_callbacks(stack)
        with pytest.raises(ValueError, match="estimated_runs exceeds max_estimated_runs"):
            _receipt._load_analysis(FileSystemCAS(tmp_path / "cas"), fake)
        if not (callbacks == []):
            raise AssertionError
    RESULTS.append(
        {
            "native_analysis": "Morris y=x+2z",
            "independent_mu_star": [1, 2],
            "rows": 12,
            "source_plan": p.model_dump(mode="json"),
            "CAS": str(fresh.root),
            "analysis_ref": ref.model_dump(mode="json"),
            "fresh_readback_equal": True,
            "corrupt_receipt_ref": fake.model_dump(mode="json"),
            "corrupt_callback_count": 0,
            "population_law_status": result.metadata["population_law_status"],
        }
    )


def test_adaptive_evaluator_cannot_grant_late_permission_or_widen_captured_cap() -> None:
    p = plan()
    calls = []

    def evaluator(samples: object) -> object:
        calls.append(len(samples))
        p.allow_large_run = True
        p.max_estimated_runs = 100
        p.n_trajectories = 99
        p.parameter_specs[0].upper_bound = 100.0
        return samples[:, 0] + 2 * samples[:, 1]

    outcome = adaptive.AdaptiveSampler(
        p, adaptive.ConvergenceConfig(max_rounds=2, trajectory_step=1)
    ).run(evaluator)
    if not (calls == [6] and outcome.total_evaluations == 6):
        raise AssertionError
    if not (outcome.stop_reason == "max_estimated_runs_exceeded" and len(outcome.rounds) == 1):
        raise AssertionError
    np.testing.assert_allclose(
        [outcome.final_result.mu_star["x"], outcome.final_result.mu_star["z"]],
        [1.0, 2.0],
        rtol=0,
        atol=1e-14,
    )
    RESULTS.append(
        {
            "boundary": "Adaptive original callback mutation",
            "evaluator_calls": 1,
            "rows": 6,
            "captured_cap": 6,
            "late_permission_ignored": True,
            "stop_reason": outcome.stop_reason,
        }
    )


def test_shared_admission_removal_retains_api_but_reopens_budget_inlet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Remove only the canonical re-admission/snapshot while keeping constructor,
    # scalar schemas, all public names, and actual generator/sampler unchanged.
    p = corrupted("N")
    calls = []
    for module in [designs, sampling, analysis, _receipt, adaptive, multi_output, stability]:
        if hasattr(module, "_admit_sensitivity_plan"):
            monkeypatch.setattr(module, "_admit_sensitivity_plan", lambda p: p)

    def reached(problem: object, **kwargs: object) -> None:
        calls.append(kwargs["N"])
        raise BackendReachedError("budget escaped")

    with patch.object(morris, "sample", reached), pytest.raises(BackendReachedError):
        sampling.generate_sensitivity_samples(p)
    if not (calls == [3]):
        raise AssertionError
    RESULTS.append(
        {
            "property_removed": "shared plan snapshot/readmission",
            "present_API_preserved": True,
            "overcap_N": 3,
            "cap": 6,
            "backend_calls": 1,
            "outcome": "EXPECTED_escape",
        }
    )


def teardown_module() -> None:
    lane = Path(os.environ["REVIEW_LANE"])
    candidate = os.environ["REVIEW_SOURCE"]
    origins = {
        n: str(Path(m.__file__).resolve())
        for n, m in sys.modules.items()
        if n.startswith("polisyos") and getattr(m, "__file__", None)
    }
    for _n, p in origins.items():
        path = Path(p)
        if not (path.is_relative_to(lane / "policy-engine/src")):
            raise AssertionError
        if not (
            path.read_bytes()
            == subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
                [
                    _resolve_executable("git"),
                    "-C",
                    str(lane),
                    "show",
                    candidate + ":" + str(path.relative_to(lane)),
                ]
            )
        ):
            raise AssertionError
    Path(os.environ["REVIEW_OUTPUT"]).write_text(
        json.dumps(
            {
                "source": candidate,
                "all_module_origins_exact": True,
                "module_count": len(origins),
                "module_hashes": {
                    n: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                    for n, p in origins.items()
                    if n.startswith("polisyos.scientist.methods.doe")
                },
                "environment": {
                    "python": sys.version,
                    "executable": sys.executable,
                    "platform": platform.platform(),
                    "numpy": np.__version__,
                    "SALib": version("SALib"),
                    "backend": "native SALib sampler/analyzer plus counted inlet controls",
                    "no_artificial_caps": True,
                },
                "results": RESULTS,
            },
            indent=2,
        )
        + "\n"
    )
