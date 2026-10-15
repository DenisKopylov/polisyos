"""Tests for falsification report adapters."""

from polisyos.ir.analytics.falsification_report import (
    FalsificationReport,
    FalsificationTestKind,
)


def test_dowhy_refute_outputs_materialize_reports_and_skip_malformed_nodes() -> None:
    report = FalsificationReport.from_dowhy_refute_outputs(
        {
            "placebo-node": {
                "refutation_result": {
                    "test_name": "placebo-treatment",
                    "test_kind": "placebo_treatment",
                    "passed": False,
                    "statistic": 2.5,
                    "p_value": 0.01,
                    "interpretation": "The placebo effect is too large.",
                }
            },
            "legacy-node": {
                "refutation_result": {
                    "test_kind": "unknown-refutation",
                    "passed": True,
                }
            },
            "malformed-node": {"refutation_result": None},
            "non-mapping-node": ["not", "a", "node-output"],
        }
    )

    assert report.n_passed == 1
    assert report.n_failed == 1
    assert not report.overall_passed
    assert report.critical_failures == ("placebo-treatment",)
    assert report.tests[0].test_kind is FalsificationTestKind.PLACEBO_TREATMENT
    assert report.tests[0].statistic == 2.5
    assert report.tests[0].p_value == 0.01
    assert report.tests[1].test_kind is FalsificationTestKind.DATA_SUBSET
