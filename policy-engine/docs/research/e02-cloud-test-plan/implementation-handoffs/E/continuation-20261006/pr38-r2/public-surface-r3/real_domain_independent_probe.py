(
    "Independent five-inlet real-domain oracl"  # Exact bound literal continuation.
    "e, covariance callback and pilot control"  # Exact bound literal continuation.
    "s."  # Exact bound literal continuation.
)

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import warnings
from fractions import Fraction
from pathlib import Path

import numpy as np


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


R = Path("/workspace/e02-E-continuation-20261006")
S = R / "policy-engine/src"
REF = "ec042402ec91fbdcb51006852e29fe67f38d9452"
observed_o = Path(__file__).parent
import polisyos.foundry.uncertainty as f  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
from polisyos.foundry.uncertainty import (  # noqa: E402 - source-bound fixture
    sampling_admission as c,
)
from polisyos.foundry.uncertainty.monte_carlo import (  # noqa: E402 - source-bound fixture
    MonteCarloPropagator,
)
from polisyos.ir.analytics.uncertainty import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

property_paths = [
    "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py",
    "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
    "policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py",
]
before = {}
for p in property_paths:
    expected = subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + p], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not ((R / p).read_bytes() == expected):
        raise AssertionError
    before[p] = hashlib.sha256(expected).hexdigest()
mutant = os.environ.get("REMOVE_REAL_DOMAIN_GUARD") == "1"
if mutant:

    def unsafe_real(values: object) -> object:
        return np.asarray(values, dtype=np.float64)

    c._real_float64.__code__ = unsafe_real.__code__
# Canonical object identity and the 19-name package contract survive removal.
for name in ["admit_empirical_weights", "empirical_cdf", "admit_unit_uniform"]:
    if not (getattr(f, name) is getattr(c, name) and name in f.__all__):
        raise AssertionError
if not (len(f.__all__) == 19):
    raise AssertionError
properties = []
refusals = []
plan = c.BoundedIIDMeanPlan(metric_id="fixture-y", pilot_samples=256)
epsilon = 0.05
m = 256
delta_pilot = delta_main = 0.025
a = math.sqrt(math.log(4 / delta_pilot) / (2 * m))
variance = min(0.25, max(0.0, a))
n = math.ceil((2 * variance + 2 * epsilon / 3) * math.log(2 / delta_main) / (epsilon**2))
u, N = c.frozen_bernstein_budget(np.zeros(m), plan)
if not (u == variance and N == n == 408):
    raise AssertionError
properties.append(
    {
        "property": "independent-all-zero-IID-pilot-mean-oracle",
        "U": u,
        "N": N,
        "outcome": "PASS",
        "authority": (
            "numerical formula only; actual independe"  # Exact bound literal continuation.
            "nt bounded law required separately"  # Exact bound literal continuation.
        ),
    }
)
for inlet, call in [
    ("weights", lambda values: f.admit_empirical_weights(values, 2)),
    ("CDF", f.empirical_cdf),
    ("uniform", f.admit_unit_uniform),
    ("range", c.admit_float32_range),
    (
        "pilot",
        lambda values: c.frozen_bernstein_budget(
            values, c.BoundedIIDMeanPlan(metric_id="y", pilot_samples=2)
        ),
    ),
]:
    for label, value in [
        ("nonzero-imag", np.array([0.5 + 0.1j, 0.5 - 0.1j])),
        ("zero-imag", np.array([0.5 + 0j, 0.5 + 0j])),
        ("object-complex", np.array([0.5 + 0.1j, 0.5 - 0.1j], dtype=object)),
        ("strings", np.array([".5", ".5"])),
        ("datetime", np.array(["2026-10-06", "2026-10-07"], dtype="datetime64[D]")),
    ]:
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter("always")
            try:
                call(value)
            except ValueError as exc:
                if "real numeric" not in str(exc):
                    raise AssertionError from None
                if observed:
                    raise AssertionError from None
                refusals.append(
                    {"inlet": inlet, "case": label, "exception": "ValueError", "warnings": 0}
                )
            else:
                raise AssertionError("removed real-domain guard admitted " + inlet + "/" + label)
properties.append(
    {
        "property": "five-common-inlets-non-real-refusal-before-cast",
        "cases": len(refusals),
        "outcome": "PASS",
    }
)
for values in [
    np.array([1, 1, 2], np.int64),
    np.array([1, 1, 2], np.float32),
    np.array([1, 1, 2], np.float64),
    np.array([Fraction(1), Fraction(1), Fraction(2)], object),
]:
    p = f.admit_empirical_weights(values, 3)
    np.testing.assert_array_equal(p, [0.25, 0.25, 0.5])
    np.testing.assert_array_equal(f.empirical_cdf(p), [0.25, 0.5, 1.0])
properties.append(
    {"property": "supported-real-int-float32-float64-Fraction-object-dyadic-law", "outcome": "PASS"}
)
calls = []
env = UncertaintyEnvelope(
    point_estimate=0.0,
    confidence_interval=(-1.96, 1.96),
    confidence_level=0.95,
    distribution_family=DistributionFamily.NORMAL,
    source=UncertaintySource.CALIBRATION,
    propagation_method=PropagationMethod.NONE,
    interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
    gate_eligible=False,
    metadata={"std": 1.0, "covariance_params": ["x"], "covariance_row": np.array([1.0 + 5j])},
)
r = MonteCarloPropagator(
    f.PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
).propagate(lambda **p: calls.append(p) or {"y": p["x"]}, {"x": 0.0}, {"x": env}, ["y"])[0]
if not (
    calls == []
    and r.envelope.distribution_family is DistributionFamily.UNKNOWN
    and not r.envelope.gate_eligible
):
    raise AssertionError
properties.append(
    {
        "property": "actual-native-MC-complex-covariance-pre-nominal-refusal",
        "callback_count": 0,
        "family": r.envelope.distribution_family.value,
        "gate_eligible": False,
        "outcome": "PASS",
    }
)
modules = []
for name, module in sorted(sys.modules.items()):
    if name.startswith("polisyos.") and getattr(module, "__file__", None):
        path = Path(module.__file__).resolve()
        if not (path.is_relative_to(S)):
            raise AssertionError
        rel = "policy-engine/src/" + str(path.relative_to(S))
        expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
            [_resolve_executable("git"), "show", REF + ":" + rel], cwd=R
        )
        if not (path.read_bytes() == expected):
            raise AssertionError
        modules.append(
            {"module": name, "path": rel, "sha256": hashlib.sha256(expected).hexdigest()}
        )
for p, h in before.items():
    if not (hashlib.sha256((R / p).read_bytes()).hexdigest() == h):
        raise AssertionError
result = {
    "source_sha": REF,
    "source_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", REF + "^{tree}"], cwd=R, text=True
    ).strip(),
    "properties": properties,
    "refusals": refusals,
    "module_origin_count": len(modules),
    "module_origins": modules,
    "source_property_paths": before,
    "source_before_after_equal": True,
    "verdict": "GO-bounded-common-real-domain-property",
    "new_Welfare_consumer": "UNRUN-pending-frozen-source",
    "no_finding_closure_or_law_authority": True,
}
(observed_o / "real-domain-independent-probe.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            k: result[k]
            for k in [
                "source_sha",
                "source_tree",
                "properties",
                "module_origin_count",
                "source_property_paths",
                "source_before_after_equal",
                "verdict",
            ]
        },
        indent=2,
    )
)
