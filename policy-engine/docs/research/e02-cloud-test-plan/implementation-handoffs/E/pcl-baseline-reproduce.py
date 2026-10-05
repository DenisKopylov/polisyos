"""Replay exact slice-base calibration modules against a bounded analytic fixture."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

from polisyos.runtime.quality.production_invocation import _git

BASE = "c40d4acae1ce58b597267255026d9356565828fd"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("baseline module loader is unavailable")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


with tempfile.TemporaryDirectory(prefix="pcl-base-") as d:
    modules = {}
    for name in ["curve", "continuous"]:
        src = _git(
            Path.cwd(), "show", BASE + ":policy-engine/src/polisyos/calibration/" + name + ".py"
        ).decode("utf-8")
        p = Path(d) / (name + ".py")
        p.write_text(src)
        modules[name] = _load_module("pcl_base_" + name, p)
    modules["continuous"].compute_calibration_curve = modules["curve"].compute_calibration_curve
    ys = list(map(float, range(100)))
    valid = [(v - 0.1, v + 0.1) for v in ys[:95]] + [(-1000.0, -999.0)] * 5
    curve = modules["curve"].compute_calibration_curve(ys, [[], valid], levels=[0.5, 0.95])
    report = modules["continuous"].evaluate_continuous(
        y_true=ys, intervals=[[], valid], levels=[0.5, 0.95]
    )
    sys.stdout.write(
        json.dumps(
            {
                "base_sha": BASE,
                "input_identity": (
                    "100 analytic observations 0..99; first level skipped; "
                    "second level .95 covers95 observations"
                ),
                "curve_status": curve.evaluation_status,
                "curve_n_comparisons": curve.n_comparisons,
                "curve_ece": curve.ece,
                "curve_positive": curve.is_well_calibrated,
                "native_report_status": report.metadata["interval_coverage"],
                "native_receipt_tier": report.to_truthfulness_receipt().runtime_truthfulness_tier,
                "native_receipt_reasons": report.to_truthfulness_receipt().degradation_reasons,
            },
            indent=2,
        )
        + "\n"
    )
    curve = modules["curve"].compute_calibration_curve(
        [float("nan"), *ys[1:]], [[(-1000.0, 999.0)] * 100], levels=[0.99]
    )
    sys.stdout.write(
        json.dumps(
            {
                "malformed": "one NaN observation at nominal.99",
                "curve_ece": curve.ece,
                "curve_positive": curve.is_well_calibrated,
            }
        )
        + "\n"
    )
    report = modules["continuous"].evaluate_continuous(
        y_true=[1.0] * 100, predictive_samples=[[0.0, 2.0]] * 100, levels=[1.0]
    )
    sys.stdout.write(
        json.dumps(
            {
                "source_alternative": (
                    "predictive_samples level1 bypasses supplied continuous open(0,1)domain"
                ),
                "native_ece": report.metrics.ece,
                "native_tier": report.to_truthfulness_receipt().runtime_truthfulness_tier,
            }
        )
        + "\n"
    )
