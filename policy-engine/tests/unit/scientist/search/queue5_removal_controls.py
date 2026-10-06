"""Run selected pytest witnesses with one runtime property removed in memory.

Execute this driver from the immutable candidate's policy-engine directory.
The driver returns pytest's real exit code; each removal must fail an actual
witness assertion, rather than imports or collection. Production files and
report/profile metadata are retained. This is a falsifier, not a closure gate.
"""

from __future__ import annotations

import argparse

import pytest


class RemovedProperty:
    def __init__(self, case: str) -> None:
        self.case = case

    def pytest_configure(self) -> None:
        if self.case == "absolute_tolerance":
            from polisyos.scientist.methods.search.stopping import ImprovementPlateau

            original = ImprovementPlateau.check

            def relative_only(self, history, state):
                self._absolute_tolerance = 0.0
                return original(self, history, state)

            ImprovementPlateau.check = relative_only
        elif self.case == "current_embedding":
            from polisyos.scientist.orchestration.engine.convergence import ConvergenceDetector

            def stale_pair(self):
                if len(self._text_embeddings) < 2:
                    return None
                return tuple(self._text_embeddings[-2:])

            ConvergenceDetector._current_embedding_pair = stale_pair
        else:
            from polisyos.scientist.methods.search import adversarial

            if self.case == "payload_bound":
                original = adversarial._StressSummary.record

                def retain_every_payload(self, vulnerability):
                    if not hasattr(self, "retained_payloads"):
                        self.retained_payloads = []
                    self.retained_payloads.append(vulnerability)
                    return original(self, vulnerability)

                adversarial._StressSummary.record = retain_every_payload
            elif self.case == "objective_direction":
                original = adversarial._objective_badness
                adversarial._objective_badness = lambda value, direction: -original(
                    value, direction
                )
            else:
                original = adversarial.run_stress_test
                case = self.case

                def grouped_or_available_score(**kwargs):
                    report = original(**kwargs)
                    if case == "scenario_fraction":
                        report.robustness_score = 1.0 - len(report.vulnerabilities) / max(
                            1, report.total_scenarios_evaluated
                        )
                    elif report.robustness_score is None:
                        report.robustness_score = 0.0
                    return report

                adversarial.run_stress_test = grouped_or_available_score


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        required=True,
        choices=[
            "absolute_tolerance",
            "current_embedding",
            "payload_bound",
            "objective_direction",
            "scenario_fraction",
            "zero_denominator",
        ],
    )
    options, pytest_args = parser.parse_known_args()
    return int(pytest.main(pytest_args, plugins=[RemovedProperty(options.case)]))


if __name__ == "__main__":
    raise SystemExit(main())
