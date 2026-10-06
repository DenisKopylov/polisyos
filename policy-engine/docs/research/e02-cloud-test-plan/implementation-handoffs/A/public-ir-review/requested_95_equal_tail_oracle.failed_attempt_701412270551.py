"""Reproduction program for the 95%-mass finite-sample oracle and v1.1 control.

The recorded execution used an ephemeral inline NumPy program. Its exact stdin
was not retained. This saved reproduction was written after that run and is not
claimed to be byte-identical to the executed source; it has not itself been run.
Run from policy-engine with .venv/bin/python and this file path.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

PIN = "198076863e143dea9f89f02734b13d50dae3eed5"
GIT_SOURCE = "policy-engine/src/polisyos/ir/analytics/uncertainty.py"
PRODUCT_SOURCE = Path("src/polisyos/ir/analytics/uncertainty.py")
PRODUCT_ROOT = Path.cwd()
REPO_ROOT = PRODUCT_ROOT.parent
PRODUCT_SRC = PRODUCT_ROOT / "src"
sys.path.insert(0, str(PRODUCT_SRC))

import polisyos.ir.analytics.uncertainty as uncertainty_module
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
)


def main() -> None:
    """Run the discrete oracle and current v1.1 validation control."""

    pinned_blob = subprocess.check_output(
        ["git", "rev-parse", f"{PIN}:{GIT_SOURCE}"], cwd=REPO_ROOT, text=True
    ).strip()
    loaded_blob = subprocess.check_output(
        ["git", "hash-object", str(PRODUCT_SOURCE)], cwd=REPO_ROOT, text=True
    ).strip()
    assert pinned_blob == "0a2495855d707a6548da6983bdef9abed9c4b0c7"
    assert loaded_blob == pinned_blob
    assert Path(uncertainty_module.__file__) == PRODUCT_SRC / "polisyos/ir/analytics/uncertainty.py"

    draws = np.asarray([0] * 99 + [100], dtype=np.float64)
    mean = float(np.mean(draws))
    q025, q975 = np.quantile(draws, [0.025, 0.975], method="inverted_cdf")
    assert mean == 1.0
    assert (float(q025), float(q975)) == (0.0, 0.0)

    schema_default = UncertaintyEnvelope.model_fields["schema_version"].default
    assert schema_default == "1.1"
    try:
        UncertaintyEnvelope(
            point_estimate=mean,
            confidence_interval=(float(q025), float(q975)),
            confidence_level=0.95,
            source=UncertaintySource.CALIBRATION,
            interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
        )
    except ValidationError as exc:
        rejection = str(exc)
        expected = "point_estimate (1.0) must lie within confidence_interval [0.0, 0.0]"
        assert expected in rejection
    else:
        raise AssertionError("v1.1 unexpectedly accepted mean 1 with interval [0, 0]")

    result: dict[str, Any] = {
        "source_pin": PIN,
        "pinned_source_blob": pinned_blob,
        "loaded_source_blob": loaded_blob,
        "loaded_source_matches_pin": loaded_blob == pinned_blob,
        "schema_version_default": schema_default,
        "numpy_version": np.__version__,
        "oracle": {
            "draw_count": int(draws.size),
            "mean": mean,
            "equal_tail_q025": float(q025),
            "equal_tail_q975": float(q975),
            "interval_mass": 0.95,
            "quantile_method": "numpy.quantile(method='inverted_cdf')",
            "numeric_estimator_called": False,
        },
        "v1_1_control": {
            "expected_rejection": True,
            "rejection": rejection,
        },
        "scope": [
            "This finite-data oracle does not ratify public quantile semantics.",
            "This validation control does not replay a historical production payload.",
            "No v2 schema or identity is created or tested.",
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
