import json
import sys
import warnings

import numpy as np
from polisyos.foundry.uncertainty import PropagationConfig
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
with warnings.catch_warnings(record=True) as observed:
    warnings.simplefilter("always")
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
    ).propagate(lambda **p: calls.append(p) or {"y": p["x"]}, {"x": 0.0}, {"x": env}, ["y"])[0]
_write_stdout(
    json.dumps(
        {
            "exact_source": "1e0eb2f6c589b74c6adae850b27af6d720dfa5ea",
            "law": "declared Normal with unsupported complex covariance row[1+5j]",
            "callback_count": len(calls),
            "family": result.envelope.distribution_family.value,
            "gate_eligible": result.envelope.gate_eligible,
            "warnings": [str(w.message) for w in observed],
            "failure": result.envelope.metadata.get("failure"),
        },
        indent=2,
    )
)
