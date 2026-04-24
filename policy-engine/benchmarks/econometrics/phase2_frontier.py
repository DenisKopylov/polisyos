#!/usr/bin/env python3
"""Lightweight benchmark for Phase 2 econometrics frontier methods."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.econometrics import ensure_econometric_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from tests.foundry.methods.catalog.econometrics.test_advanced import (
    _make_nonstationary_panel_data,
)
from tests.foundry.methods.catalog.econometrics.test_iv import (
    _make_high_dimensional_iv_panel,
)
from tests.foundry.methods.catalog.econometrics.test_thresholds import (
    _make_threshold_data,
)

SUITE_ID = "phase2_econometrics_frontier"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    iv_cls = registry.get("econometrics.iv.high_dimensional_post_selection@1.0.0")
    iv_result = dispatcher.dispatch(
        method_class=iv_cls,
        signature=iv_cls.signature,
        state=_make_high_dimensional_iv_panel(),
        params={"n_endogenous": 1, "n_folds": 3, "seed": 7, "weak_iv_threshold": 5.0},
        seed=7,
    ).output["result"]

    threshold_cls = registry.get("econometrics.thresholds.state_dependent_threshold@1.0.0")
    threshold_result = dispatcher.dispatch(
        method_class=threshold_cls,
        signature=threshold_cls.signature,
        state=_make_threshold_data(),
        params={
            "state_policy_weights": [0.4],
            "grid_size": 35,
            "trim_fraction": 0.1,
            "covariance": "robust",
            "regime_interactions": False,
        },
        seed=41,
    ).output["result"]

    garch_cls = registry.get("econometrics.panel.nonstationary_garch@1.0.0")
    garch_result = dispatcher.dispatch(
        method_class=garch_cls,
        signature=garch_cls.signature,
        state=_make_nonstationary_panel_data(),
        params={"p": 1, "q": 1, "max_breaks": 1, "min_segment_length": 12},
        seed=17,
    ).output["result"]

    payload = {
        "suite_id": SUITE_ID,
        "status": "pass",
        "metrics": {
            "post_selection_ci_count": len(iv_result.post_selection_ci),
            "threshold_shift_abs_error": abs(
                threshold_result.threshold_state_field.threshold_shift - 0.15
            ),
            "nonstationary_break_count": len(garch_result.nonstationary_volatility.breaks),
        },
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    if not args.quiet:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
