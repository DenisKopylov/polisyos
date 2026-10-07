import hashlib
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


EXPECTED = "c0f146702219cd3280c3b7d06e9d2bc4c7b95dd6"
import json  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
import warnings  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer

import numpy as np  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
import polisyos.foundry.uncertainty.sampling_admission as owner  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
from polisyos.foundry.uncertainty import (  # noqa: E402 - source-bound fixture
    PropagationConfig,
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

SOURCE = Path(owner.__file__).resolve()
ROOT = Path("/workspace/e02-E-continuation-20261006")
p = "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py"
expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
    [_resolve_executable("git"), "show", EXPECTED + ":" + p], cwd=ROOT
)
if not (SOURCE.read_bytes() == expected):
    raise AssertionError
before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
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
            "exact_source": EXPECTED,
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

if not (hashlib.sha256(SOURCE.read_bytes()).hexdigest() == before):
    raise AssertionError
if not (len(calls) == 101 and result.envelope.distribution_family is DistributionFamily.NORMAL):
    raise AssertionError
