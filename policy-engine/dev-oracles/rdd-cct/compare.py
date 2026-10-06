"""Run the native product and pinned external sharp-RD numerical oracle.

No rdrobust source is read or copied. Its public callable is used only by
the development coordinator; the product child imports the canonical NumPy
RDD owner under the separately specified PolicyOS Python interpreter.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def dgp(spec: dict[str, object]) -> tuple[np.ndarray, np.ndarray, float]:
    """Independent rows: asymmetric quadratic mean and Gaussian heteroskedastic noise."""
    rng = np.random.default_rng(int(spec["seed"]))
    z = rng.uniform(-1.0, 1.0, int(spec.get("n", 800)))
    cutoff = float(spec.get("cutoff", 0.0))
    mean = 1.0 + 0.4 * z + np.where(z < 0, 2.0 * z**2, float(spec["tau"]) + 6.0 * z**2)
    sigma = 0.3 + 0.2 * np.abs(z) + 0.15 * (z >= 0)
    return z + cutoff, mean + rng.normal(size=len(z)) * sigma, cutoff


def input_digest(x: np.ndarray, y: np.ndarray, cutoff: float) -> str:
    """Recompute the exact admitted array bytes independently of product metadata."""
    h = hashlib.sha256(b"policyos.sharp-rdd.input.v1\0")
    h.update(np.asarray([len(x)], dtype="<i8").tobytes())
    for value in (x, y, [cutoff]):
        h.update(np.asarray(value, dtype="<f8").tobytes())
    return h.hexdigest()


def params(spec: dict[str, object]) -> dict[str, object]:
    return {
        "bias_correction": True,
        "bandwidth": spec.get("h", 0.45),
        "bias_bandwidth": spec.get("b", 0.65),
        "polynomial_order": spec.get("p", 1),
        "bias_polynomial_order": int(spec.get("p", 1)) + 1,
        "kernel": spec.get("kernel", "triangular"),
        "vce": "hc0",
        "masspoints": "off",
        "bandwidth_selector": "fixed",
        "design": "sharp",
        "confidence_level": spec.get("level", 0.95),
        "manipulation_test": False,
    }


def environment() -> dict[str, object]:
    return {
        "python": sys.version,
        "executable": sys.executable,
        "distributions": {
            d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
        },
    }


def product_mode(*, removal: bool) -> None:
    from polisyos.foundry.methods.catalog.causal import rdd
    from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData

    if removal:
        genuine = rdd._fit_rbc_polynomial

        def removed(*args: object, **kwargs: object) -> tuple[float, float, float, float, int, int]:
            us, _, variance_us, _, nh, nb = genuine(*args, **kwargs)
            return us, us, variance_us, variance_us, nh, nb

        rdd._fit_rbc_polynomial = removed
    specs = json.load(sys.stdin)
    rows = []
    for spec in specs:
        x, y, cutoff = dgp(spec)
        settings = params(spec)
        data = RDDObservationalData(running_variable=x, outcome=y, cutoff=cutoff)
        report = rdd.RegressionDiscontinuity.pure_step(data, settings)["report"]
        if report.status.value != "success":
            raise ValueError(f"native product refused {spec}: {report.status_reason}")
        actual = report.method_params
        for key in [
            "bias_correction",
            "bandwidth",
            "bias_bandwidth",
            "polynomial_order",
            "bias_polynomial_order",
            "kernel",
            "vce",
            "masspoints",
            "bandwidth_selector",
            "design",
            "confidence_level",
        ]:
            if actual[key] != settings[key]:
                raise ValueError(f"product option {key} was not bound to executed setting")
        if actual["input_sha256"] != input_digest(x, y, cutoff):
            raise ValueError("product did not content-bind the admitted rows/cutoff")
        rows.append(
            {
                "seed": spec["seed"],
                "input_sha256": actual["input_sha256"],
                "tau_us": actual["tau_us"],
                "tau_bc": report.point_estimate,
                "se_us": actual["se_us"],
                "se_rb": report.standard_error,
                "ci": report.confidence_interval,
            }
        )
    module = Path(rdd.__file__)
    json.dump(
        {
            "environment": environment(),
            "owner_path": str(module),
            "owner_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
            "removal": removal,
            "rows": rows,
        },
        sys.stdout,
    )


def reference(spec: dict[str, object]) -> dict[str, object]:
    from rdrobust import rdrobust

    x, y, cutoff = dgp(spec)
    s = params(spec)
    fit = rdrobust(
        y,
        x,
        c=cutoff,
        p=s["polynomial_order"],
        q=s["bias_polynomial_order"],
        h=s["bandwidth"],
        b=s["bias_bandwidth"],
        kernel=s["kernel"],
        vce="hc0",
        masspoints="off",
        level=100 * float(s["confidence_level"]),
    )
    if fit.bwselect != "Manual" or fit.vce != "HC0":
        raise ValueError("reference did not execute fixed bandwidth HC0")
    if (
        not np.allclose(fit.bws.loc["h"].values, s["bandwidth"])
        or not np.allclose(fit.bws.loc["b"].values, s["bias_bandwidth"])
        or fit.p != s["polynomial_order"]
        or fit.q != s["bias_polynomial_order"]
    ):
        raise ValueError("reference selected different bandwidth or polynomial order")
    e = fit.Estimate.loc["Estimate"]
    return {
        "seed": spec["seed"],
        "input_sha256": input_digest(x, y, cutoff),
        "tau_us": float(e["tau.us"]),
        "tau_bc": float(e["tau.bc"]),
        "se_us": float(e["se.us"]),
        "se_rb": float(e["se.rb"]),
        "ci": [float(v) for v in fit.ci.loc["Robust"].values],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", action="store_true")
    parser.add_argument("--removal", action="store_true")
    parser.add_argument("--product-python", type=Path)
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.product:
        product_mode(removal=args.removal)
        return 0
    if not args.product_python or not args.output:
        parser.error("--product-python and --output are required")
    if importlib.metadata.version("rdrobust") != "2.1.0":
        raise ValueError("pinned rdrobust 2.1.0 is required; no skip or substitute")
    if args.replicates < 2000:
        raise ValueError("selected coverage profile requires at least 2000 replicates per target")
    specs = []
    for p in (1, 2):
        for kernel in ("triangular", "uniform", "epanechnikov"):
            for h, b in ((0.3, 0.55), (0.55, 0.3)):
                for level in (0.8, 0.95, 0.99):
                    specs.append(
                        {
                            "seed": 1043 + len(specs),
                            "tau": 3.0,
                            "p": p,
                            "kernel": kernel,
                            "h": h,
                            "b": b,
                            "level": level,
                            "cutoff": 0.23,
                            "group": "settings",
                        }
                    )
    for tau, first in ((0.0, 271000), (3.0, 821000)):
        specs.extend(
            {"seed": first + i, "tau": tau, "group": f"coverage_tau_{tau}"}
            for i in range(args.replicates)
        )
    cwd = Path(__file__).resolve().parents[2]
    product_python = args.product_python
    if not product_python.is_absolute():
        raise ValueError("product interpreter must use its admitted absolute venv address")
    if not product_python.is_file() or not os.access(product_python, os.X_OK):
        raise ValueError("product interpreter must be an existing executable file")
    argv = [str(product_python), str(Path(__file__).resolve()), "--product"]
    if args.removal:
        argv.append("--removal")
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:."
    began = time.monotonic()
    child = subprocess.run(  # noqa: S603 - explicit admitted absolute interpreter; fixed script, no shell
        argv, cwd=cwd, input=json.dumps(specs).encode(), env=env, capture_output=True, check=False
    )
    wall_product = time.monotonic() - began
    child_path = args.output.with_suffix(".product.json")
    child_path.write_bytes(child.stdout)
    args.output.with_suffix(".product.stderr").write_bytes(child.stderr)
    if child.returncode:
        raise RuntimeError(f"product child exit {child.returncode}: {child.stderr.decode()}")
    product = json.loads(child.stdout)
    began = time.monotonic()
    refs = [reference(spec) for spec in specs]
    wall_reference = time.monotonic() - began
    reference_path = args.output.with_suffix(".reference.json")
    reference_path.write_text(json.dumps({"environment": environment(), "rows": refs}) + "\n")
    maximum = dict.fromkeys(["tau_us", "tau_bc", "se_us", "se_rb", "ci"], 0.0)
    failures = []
    for i, (actual, expected) in enumerate(zip(product["rows"], refs, strict=True)):
        if actual["input_sha256"] != expected["input_sha256"]:
            raise ValueError(f"different product/reference row bytes at index {i}")
        for key in maximum:
            error = float(np.max(np.abs(np.asarray(actual[key]) - np.asarray(expected[key]))))
            maximum[key] = max(maximum[key], error)
            if not np.allclose(actual[key], expected[key], atol=5e-9, rtol=5e-9):
                failures.append(
                    {
                        "index": i,
                        "seed": specs[i]["seed"],
                        "key": key,
                        "actual": actual[key],
                        "reference": expected[key],
                        "abs_error": error,
                    }
                )
    coverage = []
    from scipy.stats import beta

    for tau in (0.0, 3.0):
        indexes = [i for i, s in enumerate(specs) if s["group"] == f"coverage_tau_{tau}"]
        if not indexes:
            continue
        covered = sum(
            product["rows"][i]["ci"][0] <= tau <= product["rows"][i]["ci"][1] for i in indexes
        )
        n = len(indexes)
        low = float(beta.ppf(0.005, covered, n - covered + 1)) if covered else 0.0
        high = float(beta.ppf(0.995, covered + 1, n - covered)) if covered < n else 1.0
        passed = low <= 0.95 <= high and 0.925 <= covered / n <= 0.975
        coverage.append(
            {
                "true_jump": tau,
                "seed_first": specs[indexes[0]]["seed"],
                "seed_last": specs[indexes[-1]]["seed"],
                "replicates": n,
                "covered": covered,
                "coverage": covered / n,
                "binomial_Clopper_Pearson_99pct": [low, high],
                "declared_acceptance": (
                    "99% binomial interval contains .95 and empirical coverage in [.925,.975]"
                ),
                "outcome": "PASS" if passed else "FAIL",
            }
        )
    result = {
        "outcome": "FAIL" if failures or any(c["outcome"] == "FAIL" for c in coverage) else "PASS",
        "scope": (
            "Native CCT vs actual rdrobust2.1.0 external oracle, sharp fixed HC0 only; "
            "simulated iid coverage is not admitted real-data validity"
        ),
        "case_count": len(specs),
        "settings_cases": 36,
        "removal": args.removal,
        "source_sha": subprocess.check_output([shutil.which("git"), "rev-parse", "HEAD"], cwd=cwd)  # noqa: S603 - fixed Git identity read, no shell
        .decode()
        .strip(),
        "product_child_argv": argv,
        "product_cwd": str(cwd),
        "product_returncode": child.returncode,
        "product_source_path": product["owner_path"],
        "product_source_sha256": product["owner_sha256"],
        "product_environment": product["environment"],
        "oracle_environment": environment(),
        "DGP": (
            "n800, X~Uniform[-1,1], left2X²/right6X², slope.4, intercept1, "
            "Gaussian SD .3+.2|X|+.15Iright; independent PCG64 draws; "
            "settings cases shift cutoff to.23"
        ),
        "fixed_coverage_settings": params({}),
        "maximum_abs_differences": maximum,
        "differential_failure_count": len(failures),
        "first_differential_failures": failures[:12],
        "coverage": coverage,
        "wall_product_s": wall_product,
        "wall_reference_s": wall_reference,
        "complete_numeric_outputs": [
            {
                "path": str(p),
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in (child_path, reference_path)
        ],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "outcome",
                    "case_count",
                    "maximum_abs_differences",
                    "differential_failure_count",
                    "coverage",
                    "wall_product_s",
                    "wall_reference_s",
                ]
            },
            indent=2,
        )
        + "\n"
    )
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
