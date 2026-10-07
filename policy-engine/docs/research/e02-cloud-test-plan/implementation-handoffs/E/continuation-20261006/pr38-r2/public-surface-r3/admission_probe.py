(
    "Independent exact-source public helper o"  # Exact bound literal continuation.
    "racle; actual caller follow-up is separa"  # Exact bound literal continuation.
    "te."  # Exact bound literal continuation.
)

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.stats import qmc


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
REF = "1e0eb2f6c589b74c6adae850b27af6d720dfa5ea"
observed_o = Path(__file__).parent
f = importlib.import_module("polisyos.foundry.uncertainty")
c = importlib.import_module("polisyos.foundry.uncertainty.sampling_admission")
paths = [
    "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
    "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py",
]
before = {}
for p in paths:
    b = (R / p).read_bytes()
    expected = subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + p], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not (b == expected):
        raise AssertionError
    before[p] = hashlib.sha256(b).hexdigest()
names = ["admit_empirical_weights", "empirical_cdf", "admit_unit_uniform"]
if not (all(n in f.__all__ and getattr(f, n) is getattr(c, n) for n in names)):
    raise AssertionError
if not (len(f.__all__) == 19):
    raise AssertionError
properties = [{"name": "canonical-three-public-identities", "outcome": "PASS"}]
refusals = []


def reject(label: str, fn: object) -> None:
    try:
        fn()
    except (ValueError, TypeError, OverflowError) as e:
        refusals.append({"label": label, "exception": type(e).__name__, "reason": str(e)})
    else:
        raise AssertionError("invalid input admitted " + label)


weights = f.admit_empirical_weights([1, 1, 2], 3)
np.testing.assert_array_equal(weights, [0.25, 0.25, 0.5])
cdf = f.empirical_cdf(weights)
np.testing.assert_array_equal(cdf, [0.25, 0.5, 1.0])
U = qmc.Sobol(1, scramble=False).random_base2(8).reshape(-1)
admitted = f.admit_unit_uniform(U)
index = np.searchsorted(cdf, admitted, side="right")
counts = np.bincount(index, minlength=3)
np.testing.assert_array_equal(counts, [64, 64, 128])
y = np.array([0.0, 3.0, 9.0])[index]
if not (y.mean() == 5.25 and y.var() == 15.1875):
    raise AssertionError
properties.append(
    {
        "name": "native-SciPy-complete256-dyadic-net",
        "outcome": "PASS",
        "oracle": (
            "mass1:1:2 over y(0,3,9), independent exact mean21/4 and vari"
            "ance243/16; expected rows64/64/128"
        ),
        "actual_counts": counts.tolist(),
        "mean": float(y.mean()),
        "variance": float(y.var()),
    }
)
edge = f.admit_unit_uniform(
    [
        0,
        np.nextafter(0.25, 0),
        0.25,
        np.nextafter(0.25, 1),
        np.nextafter(0.5, 0),
        0.5,
        np.nextafter(1.0, 0),
    ]
)
np.testing.assert_array_equal(np.searchsorted(cdf, edge, side="right"), [0, 0, 1, 1, 1, 2, 2])
properties.append({"name": "exact-half-open-and-CDF-boundaries", "outcome": "PASS"})
for label, p in [
    ("tiny-first", [5e-11, 0.5, 0.5 - 5e-11]),
    ("tiny-interior", [0.5, 5e-11, 0.5 - 5e-11]),
    ("tiny-last", [0.5, 0.5 - 5e-11, 5e-11]),
    ("zero-mass", [0, 0.25, 0, 0.75, 0]),
]:
    p = np.array(p)
    cc = f.empirical_cdf(p)
    np.testing.assert_array_equal(np.diff(np.r_[0.0, cc]) > 0, p > 0)
    if not (cc[-1] == 1.0):
        raise AssertionError
    properties.append(
        {"name": label + "-represented-support", "outcome": "PASS", "CDF": cc.tolist()}
    )
for label, fn in [
    ("CDF-collapse", lambda: f.empirical_cdf([0.5, 1e-20, 0.5])),
    ("weights-collapse", lambda: f.admit_empirical_weights([0.5, 1e-20, 0.5], 3)),
    ("weights-normalization-underflow", lambda: f.admit_empirical_weights([1e300, 1e-300], 2)),
    ("weights-zero-total", lambda: f.admit_empirical_weights([0, 0], 2)),
    ("weights-wrong-count", lambda: f.admit_empirical_weights([1, 2], 3)),
    ("weights-negative", lambda: f.admit_empirical_weights([1, -1], 2)),
    ("CDF-not-normalized", lambda: f.empirical_cdf([0.3, 0.3])),
    ("CDF-nonfinite", lambda: f.empirical_cdf([float("nan"), 1.0])),
    ("U-one", lambda: f.admit_unit_uniform([1.0])),
    ("U-negative", lambda: f.admit_unit_uniform([-np.nextafter(0, 1)])),
    ("U-nonfinite", lambda: f.admit_unit_uniform([float("inf")])),
]:
    reject(label, fn)
properties.append(
    {"name": "unsupported-domain-collapse-refusals", "outcome": "PASS", "cases": len(refusals)}
)
# Small API execution harness, not the actual Welfare/default caller.
callback_count = 0


def harness(probabilities: object, uniforms: object) -> object:
    global callback_count
    p = f.admit_empirical_weights(probabilities, len(probabilities))
    cdf = f.empirical_cdf(p)
    u = f.admit_unit_uniform(uniforms)
    rows = np.searchsorted(cdf, u, side="right")
    for _row in rows:
        callback_count += 1
    return rows


for probabilities, uniforms in [([0.5, 1e-20, 0.5], [0.0]), ([1, 1], [1.0])]:
    callback_count = 0
    reject(
        "harness-pre-callback-refusal",
        lambda *, probabilities=probabilities, uniforms=uniforms: harness(probabilities, uniforms),
    )
    if not (callback_count == 0):
        raise AssertionError
properties.append(
    {
        "name": "API-harness-refusal-before-any-callback",
        "outcome": "PASS",
        "limitation": "harness only; actual new Welfare caller awaits frozen source",
    }
)
modules = []
for name, m in sorted(sys.modules.items()):
    if name.startswith("polisyos.") and getattr(m, "__file__", None):
        p = Path(m.__file__).resolve()
        if not (p.is_relative_to(S)):
            raise AssertionError((name, p))
        rel = "policy-engine/src/" + str(p.relative_to(S))
        b = p.read_bytes()
        expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
            [_resolve_executable("git"), "show", REF + ":" + rel], cwd=R
        )
        if not (b == expected):
            raise AssertionError(rel)
        modules.append({"module": name, "path": rel, "sha256": hashlib.sha256(b).hexdigest()})
for p, h in before.items():
    if not (hashlib.sha256((R / p).read_bytes()).hexdigest() == h):
        raise AssertionError
result = {
    "source_sha": REF,
    "source_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", REF + "^{tree}"], cwd=R, text=True
    ).strip(),
    "source_property_paths": before,
    "source_before_after_equal": True,
    "properties": properties,
    "refusals": refusals,
    "full_module_origins": modules,
    "native_backend": {
        "numpy": np.__version__,
        "scipy": importlib.import_module("scipy").__version__,
        "python": sys.version,
    },
    "bounded_API_verdict": "GO",
    "publication_verdict": "HOLD-pending-canonical-inventory19-and-README19",
    "actual_new_Welfare_consumer": "UNRUN-pending-frozen-source",
    "no_closure_or_source_authority": True,
}
(observed_o / "admission-probe.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            k: result[k]
            for k in [
                "source_sha",
                "source_tree",
                "source_property_paths",
                "source_before_after_equal",
                "properties",
                "bounded_API_verdict",
                "publication_verdict",
                "actual_new_Welfare_consumer",
            ]
        },
        indent=2,
    )
)
