import hashlib
import json
import shutil
import subprocess
import sys
import warnings
from fractions import Fraction
from pathlib import Path

import numpy as np

from polisyos.foundry.uncertainty import sampling_admission as c


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


R = Path("/workspace/e02-E-continuation-20261006")
observed_o = Path(__file__).parent
REF = "ec042402ec91fbdcb51006852e29fe67f38d9452"
p = "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py"
expected = subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + p], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
if not (Path(c.__file__).read_bytes() == expected):
    raise AssertionError
small = np.longdouble("1e-400")
if not (small > 0 and np.isfinite(small)):
    raise AssertionError
rows = []
for label, name, args in [
    (
        "longdouble-first-weight",
        "admit_empirical_weights",
        (np.array([small, 1], dtype=np.longdouble), 2),
    ),
    (
        "longdouble-interior-weight",
        "admit_empirical_weights",
        (np.array([0.5, small, 0.5], dtype=np.longdouble), 3),
    ),
    ("longdouble-first-CDF", "empirical_cdf", (np.array([small, 1], dtype=np.longdouble),)),
    ("longdouble-range", "admit_float32_range", (np.array([[small]], dtype=np.longdouble),)),
    ("longdouble-uniform", "admit_unit_uniform", (np.array([small], dtype=np.longdouble),)),
    (
        "object-Fraction-weight",
        "admit_empirical_weights",
        (np.array([Fraction(1, 10**400), Fraction(1)], dtype=object), 2),
    ),
]:
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        try:
            value = getattr(c, name)(*args)
        except Exception as e:
            row = {
                "case": label,
                "outcome": "refused",
                "exception": type(e).__name__,
                "reason": str(e),
            }
        else:
            row = {
                "case": label,
                "outcome": "admitted",
                "output": value.tolist(),
                "output_first_zero": bool(value.flat[0] == 0),
            }
        row["warnings"] = [str(w.message) for w in observed]
        rows.append(row)
if not (Path(c.__file__).read_bytes() == expected):
    raise AssertionError
result = {
    "source_sha": REF,
    "source_sha256": hashlib.sha256(expected).hexdigest(),
    "longdouble_bits": np.finfo(np.longdouble).bits,
    "raw_1e-400_nonzero": bool(small > 0),
    "cases": rows,
    "scope": (
        "nonzero positive category/range support lost during float128"
        "/object→float64 cast; no arbitrary-real exactness promised"
    ),
}
(observed_o / "longdouble-support-probe.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
