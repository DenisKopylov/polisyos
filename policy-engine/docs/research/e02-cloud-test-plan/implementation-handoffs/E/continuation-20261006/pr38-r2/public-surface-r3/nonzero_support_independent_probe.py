(
    "Independent common nonzero-preservation "  # Exact bound literal continuation.
    "delta, with full native input fixtures."  # Exact bound literal continuation.
)

import hashlib
import json
import math
import numbers
import os
import shutil
import subprocess
import sys
import warnings
from fractions import Fraction
from pathlib import Path

import numpy as np

import polisyos.foundry.uncertainty as f
from polisyos.foundry.uncertainty import sampling_admission as c
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


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
observed_o = Path(__file__).parent
REF = "5cdfe613bf91fffbd578848c9e2f8275edc21ee7"
ACTUAL = subprocess.check_output(  # noqa: S603 - source-bound fixture
    [_resolve_executable("git"), "rev-parse", "HEAD"], cwd=R, text=True
).strip()
paths = [
    "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py",
    "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
    "policy-engine/src/polisyos/foundry/uncertainty/README.md",
    "policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py",
    "policy-engine/src/polisyos/foundry/uncertainty/covariance.py",
]
before = {}
for p in paths:
    expected = subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + p], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not ((R / p).read_bytes() == expected):
        raise AssertionError
    before[p] = hashlib.sha256(expected).hexdigest()
if not (len(f.__all__) == 19):
    raise AssertionError
for name in ["admit_empirical_weights", "empirical_cdf", "admit_unit_uniform"]:
    if getattr(f, name) is not getattr(c, name):
        raise AssertionError
mode = os.environ.get("SUPPORT_REMOVAL_MODE", "positive")
if mode != "positive":

    def previous_real_guard(values: object) -> object:
        array = np.asarray(values)
        if array.dtype.kind not in "biuf" and not (
            array.dtype.kind == "O" and all(isinstance(value, numbers.Real) for value in array.flat)
        ):
            raise ValueError("sampling coordinates and masses require real numeric values")
        return np.asarray(array, dtype=np.float64)

    # Function globals remain canonical owner's globals, including numbers and np.
    c._real_float64.__code__ = previous_real_guard.__code__

small = np.longdouble("1e-400")
if not (small > 0 and float(small) == 0):
    raise AssertionError("native platform must represent the positive longdouble fixture")
plan2 = c.BoundedIIDMeanPlan(metric_id="fixture-y", pilot_samples=2)
inlets = [
    ("weights", lambda v: f.admit_empirical_weights(v, len(v))),
    ("CDF", f.empirical_cdf),
    ("uniform", f.admit_unit_uniform),
    ("range", c.admit_float32_range),
    ("pilot", lambda v: c.frozen_bernstein_budget(v, plan2)),
]
refusals = []
if mode == "positive":
    for representation, tiny, dtype in [
        ("longdouble", small, np.longdouble),
        ("Fraction", Fraction(1, 10**400), object),
    ]:
        for inlet, call in inlets:
            values = np.array([tiny, 1], dtype=dtype)
            if not (values[0] > 0 and float(values[0]) == 0):
                raise AssertionError
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter("always")
                try:
                    call(values)
                except ValueError as exc:
                    if "nonzero sampling support" not in str(exc):
                        raise AssertionError from None
                    if observed:
                        raise AssertionError from None
                    refusals.append(
                        {
                            "representation": representation,
                            "inlet": inlet,
                            "exception": "ValueError",
                            "warnings": 0,
                            "callback_count": 0,
                        }
                    )
                else:
                    raise AssertionError(f"nonzero input admitted as zero by {inlet}")
    # Positions are independently enumerated; categories must not disappear before CDF admission.
    for position in range(3):
        values = np.array([0.5, 0.5, 0.5], dtype=np.longdouble)
        values[position] = small
        try:
            f.admit_empirical_weights(values, 3)
        except ValueError as exc:
            if "nonzero sampling support" not in str(exc):
                raise AssertionError from None
            refusals.append(
                {
                    "representation": "longdouble",
                    "inlet": "weights",
                    "positive_position": position,
                    "exception": "ValueError",
                }
            )
        else:
            raise AssertionError("positive first/interior/last category collapsed")

    # Supported finite-machine dyadic law remains independently known.
    for values in [
        np.array([1, 1, 2], np.int64),
        np.array([1, 1, 2], np.float32),
        np.array([1, 1, 2], np.float64),
        np.array([Fraction(1), Fraction(1), Fraction(2)], object),
        np.array([1, 1, 2], np.longdouble),
    ]:
        weights = f.admit_empirical_weights(values, 3)
        np.testing.assert_array_equal(weights, [0.25, 0.25, 0.5])
        np.testing.assert_array_equal(f.empirical_cdf(weights), [0.25, 0.5, 1.0])
    np.testing.assert_array_equal(
        f.admit_unit_uniform(np.array([0, Fraction(1, 2)], object)), [0, 0.5]
    )
    np.testing.assert_array_equal(c.admit_float32_range([0.0, 1.0]), [0.0, 1.0])

    # Native pre-nominal admission: raw row still represents nonzero support.
    native = []
    for row_kind, row in [("array", np.array([small], np.longdouble)), ("list", [small])]:
        calls = []
        env = UncertaintyEnvelope(
            point_estimate=0.0,
            confidence_interval=(0.0, 0.0),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            gate_eligible=False,
            metadata={"std": 0.0, "covariance_params": ["x"], "covariance_row": row},
        )
        result = MonteCarloPropagator(
            f.PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
        ).propagate(
            lambda *, calls=calls, **p: calls.append(p) or {"y": p["x"]},
            {"x": 0.0},
            {"x": env},
            ["y"],
        )[0]
        if not (
            not calls
            and result.envelope.distribution_family is DistributionFamily.UNKNOWN
            and not result.envelope.gate_eligible
        ):
            raise AssertionError
        native.append(
            {
                "raw_covariance_row_kind": row_kind,
                "callback_count": 0,
                "family": result.envelope.distribution_family.value,
                "gate_eligible": False,
                "limitations": (
                    "Independent covariance builder also refu"
                    "ses these row representations; this is a"
                    " positive admission-order witness, not a"
                    "n effective guard-removal control."
                ),
            }
        )

    # Freeze-N certificate arithmetic is derived independently of the implementation.
    epsilon = 0.05
    m = 256
    delta_pilot = delta_main = 0.025
    a = math.sqrt(math.log(4 / delta_pilot) / (2 * m))
    expected_u = min(0.25, max(0.0, a))
    expected_n = math.ceil(
        (2 * expected_u + 2 * epsilon / 3) * math.log(2 / delta_main) / (epsilon**2)
    )
    observed_u, observed_n = c.frozen_bernstein_budget(
        np.zeros(m), c.BoundedIIDMeanPlan(metric_id="fixture-y", pilot_samples=m)
    )
    if not (observed_u == expected_u and observed_n == expected_n == 408):
        raise AssertionError
    modules = []
    for name, module in sorted(sys.modules.items()):
        if name.startswith("polisyos.") and getattr(module, "__file__", None):
            path = Path(module.__file__).resolve()
            if not (path.is_relative_to(S)):
                raise AssertionError
            rel = "policy-engine/src/" + str(path.relative_to(S))
            expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
                [_resolve_executable("git"), "show", ACTUAL + ":" + rel], cwd=R
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
        "property_source_sha": REF,
        "property_source_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [_resolve_executable("git"), "rev-parse", REF + "^{tree}"], cwd=R, text=True
        ).strip(),
        "actual_import_source_sha": ACTUAL,
        "property_paths": before,
        "before_after_equal": True,
        "refusals": refusals,
        "native_MC": native,
        "pilot_oracle": {"U": observed_u, "N": observed_n},
        "module_origins": modules,
        "module_origin_count": len(modules),
        "verdict": "GO-bounded-common-real-domain-and-nonzero-preservation",
        "authority_or_finding_closure": False,
        "new_Welfare_consumer": "separate frozen consumer review required",
        "law_scope": (
            "Supported real finite-machine representation; no exact arbit"
            "rary-real promise. Refusal preserves unsupported positive at"
            "oms instead of silent loss."
        ),
    }
    (observed_o / "nonzero-support-independent-probe.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    _write_stdout(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "property_source_sha",
                    "property_source_tree",
                    "actual_import_source_sha",
                    "before_after_equal",
                    "refusals",
                    "native_MC",
                    "pilot_oracle",
                    "module_origin_count",
                    "verdict",
                ]
            },
            indent=2,
        )
    )
elif mode == "weights":
    observed = f.admit_empirical_weights(np.array([small, 1], np.longdouble), 2)
    _write_stdout(
        json.dumps(
            {
                "removed_property": "nonzero-preservation only",
                "exports_retained": len(f.__all__),
                "source_files_unchanged": True,
                "weights": observed.tolist(),
                "positive_input": True,
            }
        ),
        flush=True,
    )
    if not (observed[0] > 0):
        raise AssertionError("present-but-fake canonical helpers erase a positive category")
elif mode == "pilot":
    u, n = c.frozen_bernstein_budget(
        np.full(256, small, np.longdouble),
        c.BoundedIIDMeanPlan(metric_id="fixture-y", pilot_samples=256),
    )
    _write_stdout(
        json.dumps(
            {
                "removed_property": "nonzero-preservation only",
                "exports_retained": len(f.__all__),
                "source_files_unchanged": True,
                "pilot_budget": {"U": u, "N": n},
                "positive_raw_pilot_becomes_all_zero": True,
            }
        ),
        flush=True,
    )
    raise AssertionError(
        "present-but-fake common guard emitted a certificate for a pi"
        "lot whose nonzero values were discarded"
    )
else:
    raise AssertionError("unrecognized mode")
