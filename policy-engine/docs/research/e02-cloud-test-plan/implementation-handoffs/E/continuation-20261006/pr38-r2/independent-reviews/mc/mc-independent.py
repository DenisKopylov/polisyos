"""Root oracle, independent of the MC author's tests and sampling loop."""

import json
import sys
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np
from polisyos.core.artifacts import FileSystemCAS
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import (
    MonteCarloPropagator,
    _empirical_indices_from_uniform,
)
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


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


root = Path("/workspace/e02-E-mc-20261006/policy-engine/src")
import polisyos.foundry.uncertainty.monte_carlo as native  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer

if not (Path(native.__file__).is_relative_to(root)):
    raise AssertionError(native.__file__)
values, masses = (
    (Fraction(0), Fraction(3), Fraction(9)),
    (Fraction(1, 4), Fraction(1, 4), Fraction(1, 2)),
)
mean = sum(v * w for v, w in zip(values, masses, strict=False))
variance = sum(w * (v - mean) ** 2 for v, w in zip(values, masses, strict=False))
if not (mean == Fraction(21, 4) and variance == Fraction(243, 16)):
    raise AssertionError
names, row_ids = ["a", "b"], ["first", "middle", "last"]
envs = {}
for name, draws, point in [("a", (0, 1, 4), 2.25), ("b", (0, 2, 5), 3.0)]:
    envs[name] = UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(0, 5),
        confidence_level=None,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=False,
        numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
        distribution_payload=PosteriorSamplesCarrier(samples=draws, weights=(1, 1, 2)),
    )
digest = joint_carrier_digest(names, envs, row_ids)
envs = {
    name: env.model_copy(
        update={
            "metadata": {
                "joint_sample_id": "root-independent",
                "joint_draw_ids": row_ids,
                "joint_parameter_order": names,
                "joint_law_sha256": digest,
            }
        }
    )
    for name, env in envs.items()
}
fixture = Path(tempfile.mkdtemp(prefix="e02-mc-root-", dir="/workspace/e02-E-pr38-r2-receipts"))
store = FileSystemCAS(fixture)
refs = {n: persist_uncertainty_envelope(store, e) for n, e in envs.items()}
fresh = {n: load_uncertainty_envelope(FileSystemCAS(fixture), ref) for n, ref in refs.items()}
calls = []


def response(**p: object) -> dict[str, object]:
    calls.append((float(p["a"]), float(p["b"])))
    return {"sum": p["a"] + p["b"]}


config = PropagationConfig(
    mc_n_samples=256, mc_sampling_method="sobol", mc_qmc_scramble=False, compute_sensitivity=False
)
result = MonteCarloPropagator(config).propagate(response, {"a": 2.25, "b": 3.0}, fresh, ["sum"])[0]
if not (
    len(calls) == 257 and Counter(calls[1:]) == {(0.0, 0.0): 64, (1.0, 2.0): 64, (4.0, 5.0): 128}
):
    raise AssertionError
if not (result.envelope.point_estimate == float(mean)):
    raise AssertionError
if not (np.var(result.envelope.distribution_payload.samples) == float(variance)):
    raise AssertionError
if result.envelope.gate_eligible:
    raise AssertionError
probs = np.array([5e-11, 1 - 1e-10, 5e-11])
u = np.array([0.0, np.nextafter(1.0, 0.0)])
if not (_empirical_indices_from_uniform(u, probs).tolist() == [0, 2]):
    raise AssertionError
fake = np.searchsorted(np.cumsum(probs), np.clip(u, 1e-10, 1 - 1e-10), side="right")
if not (fake.tolist() != [0, 2]):
    raise AssertionError
for bad in [-1e-100, 1.0, np.inf, np.nan]:
    try:
        _empirical_indices_from_uniform(np.array([bad]), probs)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid U admitted")
if not (
    _empirical_indices_from_uniform(
        np.array([0.0, 0.25, np.nextafter(0.25, 0.0)]), np.array([0.25, 0.0, 0.75])
    ).tolist()
    == [0, 2, 0]
):
    raise AssertionError
_write_stdout(
    json.dumps(
        {
            "source_sha": "d69d2fad34de9923209fde3e20439e46f36f6750",
            "independent_mean": str(mean),
            "independent_variance": str(variance),
            "native_mean": result.envelope.point_estimate,
            "actual_callback_row_counts": {"0,0": 64, "1,2": 64, "4,5": 128},
            "CDF_boundary_controls": "PASS",
            "old_epsilon_property_removal": "DETECTED",
            "authority": "non-gating",
            "cleanup_candidate": str(fixture),
        }
    )
)
