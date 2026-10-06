"""Execute the real producer/consumer with one in-memory confidence removal."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

from polisyos.scientist.methods.search.funnel import level5_refutation_governance as consumer
from polisyos.scientist.methods.search.uncertainty import UncertaintyType


def main() -> None:
    mode = sys.argv[1]
    probe_path = Path("tests/integration/scientist/methods/search/funnel/producer_bridge_probe.py")
    probe = runpy.run_path(str(probe_path))
    if mode == "positive":
        probe["main"]()
        return
    if mode != "remove_population_boundary":
        raise ValueError(f"unknown independent removal: {mode}")
    actual = consumer._level5_uncertainty_envelope

    def remove_boundary(**kwargs):
        envelope = actual(**kwargs)
        report = kwargs["stress_report"]
        assert report.robustness_score is not None
        current = envelope.uncertainties[UncertaintyType.MODEL]
        # Retain the new assessment, scope, method and source markers. Change
        # only the effect: make the partial observed fraction imply confidence.
        altered = current.model_copy(update={"level": 1.0 - report.robustness_score})
        return envelope.with_update(UncertaintyType.MODEL, altered)

    consumer._level5_uncertainty_envelope = remove_boundary
    print(
        json.dumps(
            {
                "mutation": mode,
                "mechanism": "partial observed fraction mapped into model uncertainty",
                "retained": "real producer counters/CAS, L5 assessment, scope/source/method markers",
                "expected_result": "actual consumer AssertionError",
            }
        ),
        flush=True,
    )
    probe["run_case"]("partial")


if __name__ == "__main__":
    main()
