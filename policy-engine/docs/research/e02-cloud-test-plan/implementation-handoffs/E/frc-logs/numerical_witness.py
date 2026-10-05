"""Reproduce the bounded ETS observation control used in the FRC receipt."""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

from polisyos.calibration.forecast_bridge import produce_empirical_calibration_evidence
from polisyos.core.artifacts import FileSystemCAS
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


root = Path(__file__).resolve().parents[7]
test_path = root / "policy-engine/tests/unit/remediation/test_frc_02_owner.py"
spec = importlib.util.spec_from_file_location("frc_owner_fixture", test_path)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
cases = []
with tempfile.TemporaryDirectory(prefix="e02-frc-numerical-") as temporary:
    store = FileSystemCAS(Path(temporary) / "cas")
    rule_ref = fixture._rule(store)
    for label, holdout in [
        ("in_profile", [20.0, 21.0, 22.0]),
        ("out_of_profile", [1000.0, 1001.0, 1002.0]),
    ]:
        source_ref = fixture._source(
            store, training=[float(i) for i in range(10, 20)], holdout=holdout
        )
        request = fixture._request(
            source_ref, rule_ref, report_id=f"frc-witness-{label}", train_end=10, horizon=3
        )
        with contextlib.redirect_stdout(io.StringIO()):
            result = ForecastOwner(store).run(request)
        report = load_backtest_report(store, result.backtest_report_ref)
        evidence = produce_empirical_calibration_evidence(store, result.backtest_report_ref)
        _require(evidence.recomputed_numerator == result.numerator, "numerator readback mismatch")
        _require(
            evidence.recomputed_denominator == result.denominator, "denominator readback mismatch"
        )
        _require(
            evidence.recomputed_pass_rate == result.empirical_coverage, "coverage readback mismatch"
        )
        _require(not evidence.usable_for_calibration, "unbound observations admitted")
        _require(
            evidence.failure_codes == ("explicit_context_missing",), "unexpected evidence status"
        )
        cases.append(
            {
                "fixture_label": label,
                "source_artifact_id": str(source_ref.artifact_id),
                "method_fqn": result.method_fqn,
                "rule_metadata": {
                    key: report.metadata[key]
                    for key in (
                        "method_ref",
                        "method_version",
                        "rule_version_ref",
                        "calibration_rule_version",
                    )
                },
                "point_forecast": result.point_forecast,
                "predictive_intervals": result.predictive_intervals,
                "empirical_numerator": result.numerator,
                "empirical_denominator": result.denominator,
                "empirical_coverage": result.empirical_coverage,
                "empirical_suitability": result.empirical_suitability,
                "backtest_report_id": str(result.backtest_report_ref.artifact_id),
                "context_bound": evidence.context_bound,
                "usable_for_calibration": evidence.usable_for_calibration,
                "failure_codes": evidence.failure_codes,
                "authority_scope": evidence.authority_scope,
                "authority_denials": evidence.may_not_use_for,
                "bridge_status": result.bridge_status,
            }
        )
_require(
    cases[0]["point_forecast"] == cases[1]["point_forecast"], "shape control changed forecasts"
)
_require(
    cases[0]["predictive_intervals"] == cases[1]["predictive_intervals"],
    "shape control changed intervals",
)
_require(
    cases[0]["empirical_coverage"] != cases[1]["empirical_coverage"],
    "observations did not change coverage",
)
sys.stdout.write(
    json.dumps(
        {
            "scope": "bounded synthetic fixture; real registered ETS NumPy execution",
            "fixture_path": str(test_path),
            "cases": cases,
        },
        indent=2,
    )
    + "\n"
)
