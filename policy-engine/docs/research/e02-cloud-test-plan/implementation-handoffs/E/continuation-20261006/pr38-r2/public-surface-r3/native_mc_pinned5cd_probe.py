"""Small actual native MC consumer of canonical exported helper objects."""

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import polisyos.foundry.uncertainty as f
from polisyos.core.artifacts import FileSystemCAS
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.foundry.uncertainty.sampling_admission import joint_carrier_digest
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
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
REF = "5cdfe613bf91fffbd578848c9e2f8275edc21ee7"
observed_o = Path(__file__).parent
mutant = os.environ.get("REMOVE_CDF_GUARD") == "1"
c = importlib.import_module("polisyos.foundry.uncertainty.sampling_admission")
if f.empirical_cdf is not c.empirical_cdf:
    raise AssertionError
property_paths = [
    "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py",
    "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
    "policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py",
]
before = {}
for path in property_paths:
    expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "show", REF + ":" + path], cwd=R
    )
    if not ((R / path).read_bytes() == expected):
        raise AssertionError
    before[path] = hashlib.sha256(expected).hexdigest()
if mutant:

    def unsafe_cdf(probabilities: object) -> object:
        return np.cumsum(np.asarray(probabilities, dtype=np.float64), dtype=np.float64)

    f.empirical_cdf.__code__ = unsafe_cdf.__code__
    if not (f.empirical_cdf is c.empirical_cdf and "empirical_cdf" in f.__all__):
        raise AssertionError


def inputs(weights: object) -> object:
    names = ["a", "b"]
    ids = ["draw0", "draw1", "draw2"]
    result = {}
    for n, p, s in [("a", 2.25, (0.0, 1.0, 4.0)), ("b", 3.0, (0.0, 2.0, 5.0))]:
        result[n] = UncertaintyEnvelope(
            point_estimate=p,
            confidence_interval=(0.0, 5.0),
            confidence_level=None,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            gate_eligible=False,
            numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
            distribution_payload=PosteriorSamplesCarrier(samples=s, weights=weights),
        )
    digest = joint_carrier_digest(names, result, ids)
    return {
        n: e.model_copy(
            update={
                "metadata": {
                    "joint_sample_id": "independent-export-oracle",
                    "joint_draw_ids": ids,
                    "joint_parameter_order": names,
                    "joint_law_sha256": digest,
                }
            }
        )
        for n, e in result.items()
    }


store = FileSystemCAS(observed_o / ("cas-5cd-mc-" + ("removed" if mutant else "positive")))
results = []
for label, weights in [("dyadic", (1.0, 1.0, 2.0)), ("collapsed", (0.5, 1e-20, 0.5))]:
    source = inputs(weights)
    refs = {n: persist_uncertainty_envelope(store, e) for n, e in source.items()}
    fresh = {n: load_uncertainty_envelope(FileSystemCAS(store.root), r) for n, r in refs.items()}
    calls = []
    result = MonteCarloPropagator(
        f.PropagationConfig(
            mc_n_samples=256,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda *, calls=calls, **p: calls.append((float(p["a"]), float(p["b"])))
        or {"y": p["a"] + p["b"]},
        {"a": 2.25, "b": 3.0},
        fresh,
        ["y"],
    )[0]
    if label == "dyadic":
        if not (len(calls) == 257):
            raise AssertionError
        if not (Counter(calls[1:]) == {(0.0, 0.0): 64, (1.0, 2.0): 64, (4.0, 5.0): 128}):
            raise AssertionError
        draws = np.asarray(result.envelope.distribution_payload.samples)
        if not (
            draws.mean() == 5.25 and draws.var() == 15.1875 and not result.envelope.gate_eligible
        ):
            raise AssertionError
        results.append(
            {
                "fixture": label,
                "callback_count": len(calls),
                "nominal_count": 1,
                "actual_draw_rows": {str(k): v for k, v in Counter(calls[1:]).items()},
                "mean": float(draws.mean()),
                "variance": float(draws.var()),
                "gate_eligible": False,
            }
        )
    else:
        _write_stdout(
            json.dumps(
                {
                    "fixture": label,
                    "callback_count": len(calls),
                    "family": result.envelope.distribution_family.value,
                    "gate_eligible": result.envelope.gate_eligible,
                    "removed_guard": mutant,
                }
            ),
            flush=True,
        )
        if not (calls == []):
            raise AssertionError(
                "collapsed-law admission guard removed: a"  # Exact bound literal continuation.
                "ctual native producer reached callbacks"  # Exact bound literal continuation.
            )
        if not (
            result.envelope.distribution_family is DistributionFamily.UNKNOWN
            and not result.envelope.gate_eligible
        ):
            raise AssertionError
        results.append(
            {
                "fixture": label,
                "callback_count": 0,
                "family": result.envelope.distribution_family.value,
                "gate_eligible": False,
            }
        )
_write_stdout(
    json.dumps(
        {
            "source_sha": REF,
            "real_native_consumer": (
                "MonteCarloPropagator→configuredCAS persi"
                "sted envelope→fresh read→257 callback dy"
                "adic positive /0 callbacks collapsed-law"
                " refusal"
            ),
            "results": results,
            "new_actual_Welfare_consumer": "UNRUN-pending-frozen-source",
        },
        indent=2,
    )
)

for path, h in before.items():
    if not (hashlib.sha256((R / path).read_bytes()).hexdigest() == h):
        raise AssertionError
_write_stdout(json.dumps({"source_property_paths": before, "before_after_equal": True}, indent=2))
