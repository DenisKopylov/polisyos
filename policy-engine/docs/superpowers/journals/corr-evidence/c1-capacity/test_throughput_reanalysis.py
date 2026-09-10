"""A first-level error stop cannot locate a concurrency knee."""

from __future__ import annotations

import importlib
import unittest

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


class ThroughputReanalysisTests(unittest.TestCase):
    def test_first_error_stop_without_comparison_is_not_a_knee(self) -> None:
        owner = importlib.import_module(PREFIX + "throughput_reanalysis")
        first = {
            "synthetic": True,
            "concurrency": 1,
            "status": "measured",
            "error_rate": 0.75,
            "typed_success_per_second": 0.2,
        }
        result = owner.corrected_decision(first, None)
        if result["stop_higher_levels"] is not True:
            raise AssertionError("the predeclared error stop was lost")
        if result["knee_established"] is not False:
            raise AssertionError("first error stop invented an unobserved concurrency knee")
        previous = {**first, "error_rate": 0.0}
        next_level = {
            **first,
            "concurrency": 4,
            "error_rate": 0.0,
            "typed_success_per_second": 0.21,
        }
        measured = owner.corrected_decision(next_level, previous)
        if measured["knee_established"] is not True or measured["reason"] != "throughput_plateau":
            raise AssertionError("actual complete-level plateau comparison was discarded")
        incomplete = owner.corrected_decision({**next_level, "status": "not_established"}, previous)
        if incomplete["knee_established"] is not False or not incomplete["stop_higher_levels"]:
            raise AssertionError("incomplete level established a knee")


if __name__ == "__main__":
    unittest.main(verbosity=2)
