import json
import sys
import warnings
from pathlib import Path

import numpy as np

import polisyos.foundry.uncertainty as f


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


R = Path("/workspace/e02-E-continuation-20261006")
observed_o = Path(__file__).parent
rows = []
for label, name, args in [
    ("complex-CDF", "empirical_cdf", (np.array([0.5 + 0.1j, 0.5 - 0.1j]),)),
    ("complex-U", "admit_unit_uniform", (np.array([0.5 + 2j]),)),
    ("complex-weights", "admit_empirical_weights", (np.array([1.0 + 2j, 1.0 - 2j]), 2)),
    ("finite-total-overflow", "admit_empirical_weights", ([1e308, 1e308], 2)),
]:
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        try:
            value = getattr(f, name)(*args)
        except Exception as exc:
            row = {
                "case": label,
                "result": "refused",
                "exception": type(exc).__name__,
                "reason": str(exc),
            }
        else:
            row = {"case": label, "result": "admitted", "projection": value.tolist()}
        row["warnings"] = [str(w.message) for w in observed]
        rows.append(row)
result = {
    "source_sha": "1e0eb2f6c589b74c6adae850b27af6d720dfa5ea",
    "input_description": (
        "complex NumPy arrays; finite huge real weights; exact full inputs in this script"
    ),
    "cases": rows,
    "potential_boundary": (
        "public helper receives object; complex mass/coordinate has n"
        "o probability-domain ordering, imaginary components must not"
        " silently select a real law; investigate actual typed consum"
        "er reachability separately"
    ),
}
(observed_o / "unsupported-dtype-probe.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
