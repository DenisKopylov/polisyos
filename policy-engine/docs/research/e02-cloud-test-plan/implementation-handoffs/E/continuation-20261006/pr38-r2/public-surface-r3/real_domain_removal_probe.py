"""Remove shared guard at runtime, retaining public function identities and names."""

import argparse
import contextlib
import hashlib
import json
import sys
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


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


P = argparse.ArgumentParser()
P.add_argument("--entry", choices=["mc", "pilot"], required=True)
args = P.parse_args()
source = Path(c.__file__)
before = hashlib.sha256(source.read_bytes()).hexdigest()
identities = {
    n: getattr(f, n) for n in ["admit_empirical_weights", "empirical_cdf", "admit_unit_uniform"]
}


def unsafe_real(values: object) -> object:
    return np.asarray(values, dtype=np.float64)


c._real_float64.__code__ = unsafe_real.__code__
if not (
    all(
        getattr(f, n) is value is getattr(c, n) and n in f.__all__
        for n, value in identities.items()
    )
    and len(f.__all__) == 19
):
    raise AssertionError
if args.entry == "mc":
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
    result = MonteCarloPropagator(
        f.PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
    ).propagate(lambda **p: calls.append(p) or {"y": p["x"]}, {"x": 0.0}, {"x": env}, ["y"])[0]
    if not (hashlib.sha256(source.read_bytes()).hexdigest() == before):
        raise AssertionError
    _write_stdout(
        json.dumps(
            {
                "entry": "actual native MC",
                "callback_count": len(calls),
                "family": result.envelope.distribution_family.value,
                "export_names_and_canonical_identities_retained": True,
                "source_files_unchanged": True,
            }
        ),
        flush=True,
    )
    if not (calls == []):
        raise AssertionError(
            "shared domain guard removed: actual native MC reached101 cal"
            "lbacks with complex covariance"
        )
else:
    emitted = None
    with contextlib.suppress(ValueError):
        emitted = c.frozen_bernstein_budget(
            np.full(256, 1j), c.BoundedIIDMeanPlan(metric_id="fixture-y")
        )
    if not (hashlib.sha256(source.read_bytes()).hexdigest() == before):
        raise AssertionError
    _write_stdout(
        json.dumps(
            {
                "entry": "actual frozen bounded-pilot budget producer",
                "emitted": emitted,
                "export_names_and_canonical_identities_retained": True,
                "source_files_unchanged": True,
            }
        ),
        flush=True,
    )
    if emitted is not None:
        raise AssertionError(
            "shared domain guard removed: complex pilot emitted mainN408 certificate"
        )
