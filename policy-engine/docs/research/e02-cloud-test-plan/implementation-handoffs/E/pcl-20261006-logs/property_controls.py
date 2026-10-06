"""Reproduce the PCL predecessor proxy and remove-recompute behavioral control."""

from __future__ import annotations

import argparse
import inspect
import json
import subprocess
import sys
import types


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["proxy", "removed", "restored"])
    args = parser.parse_args()
    base = "198076863e143dea9f89f02734b13d50dae3eed5"
    if args.mode == "proxy":
        module = types.ModuleType("pcl_predecessor_diagnostics")
        sys.modules[module.__name__] = module
        path = "policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py"
        # All arguments are literals pinned to the tracked entry base.
        source = subprocess.check_output(  # noqa: S603
            ["/usr/bin/git", "show", f"{base}:{path}"], text=True
        )
        exec(compile(source, path + "@" + base, "exec"), module.__dict__)  # noqa: S102
        from polisyos.ir.analytics._truthfulness import TruthfulnessReceipt

        predecessor = module.CalibrationDiagnosticsReport(
            task="continuous",
            target_type="interval_set",
            metrics=module.CalibrationMetrics(n_obs=100, ece=0.0),
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier="approximate_calibrated"
            ),
        )
        from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticsReport

        candidate = CalibrationDiagnosticsReport.model_validate(predecessor.model_dump(mode="json"))
        old = predecessor.to_truthfulness_receipt().runtime_truthfulness_tier.value
        new = candidate.to_truthfulness_receipt().runtime_truthfulness_tier.value
        sys.stdout.write(
            json.dumps(
                {
                    "source_base": base,
                    "property": "raw positive receipt without ordered pairs",
                    "predecessor_proxy_tier": old,
                    "candidate_tier": new,
                    "negative_control": "same metrics/receipt fields, no persisted pairs",
                }
            )
            + "\n"
        )
        return 0 if (old, new) == ("approximate_calibrated", "unverified") else 1
    if args.mode == "removed":
        import polisyos.calibration.continuous as continuous

        source = inspect.getsource(continuous.load_continuous_evaluation)
        source = source.replace(
            'if reproduced.model_dump(mode="json") != artifact.report:',
            'if False and reproduced.model_dump(mode="json") != artifact.report:',
        )
        source = source.replace(
            'if reproduced.to_truthfulness_receipt().model_dump(mode="json") != artifact.receipt:',
            'if False and reproduced.to_truthfulness_receipt().model_dump(mode="json") '
            "!= artifact.receipt:",
        )
        # Keep report/receipt/schema/ref markers and the actual CAS path. Remove
        # only the deciding recomputation comparisons in this isolated process.
        exec(  # noqa: S102 - isolated property-removal control, never a production path.
            compile(source, "<removed-pcl-recompute-property>", "exec"), continuous.__dict__
        )
    import pytest

    return pytest.main(
        [
            "-o",
            "addopts=",
            "-q",
            "tests/unit/calibration/test_continuous_persistence.py::test_content_valid_fake_result_rejected_after_cas_reopen",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
