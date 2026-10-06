"""Run against the declared Q5-producer/FUN-consumer Git composition.

This is a diagnostic entrypoint with an explicit producer dependency, not a
replacement for the mirrored ordinary test suites. CAS outputs are retained.
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path

from polisyos.core import canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search import adversarial
from polisyos.scientist.methods.search.funnel import level5_refutation_governance as consumer
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.uncertainty import UncertaintyType


def main() -> None:
    print(
        json.dumps(
            {
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "producer_origin": adversarial.__file__,
                "consumer_origin": consumer.__file__,
            }
        )
    )
    for mode in ("complete", "partial", "no_finite", "early_stop"):
        run_case(mode)


def run_case(mode: str) -> None:
    cas_path = Path(tempfile.mkdtemp(prefix=f"e02-D-funnel-stress-{mode}-", dir="/tmp"))
    observations: list[float] = []

    def evaluate(candidate, context):
        value = 2.0
        if mode == "no_finite" or (mode == "partial" and candidate["shock"] == 0):
            value = float("nan")
        elif mode == "early_stop":
            value = 0.0
        observations.append(value)
        return {"simulation_results": {"gdp_change": value}}

    report = adversarial.run_stress_test(
        adversarial_plan=AdversarialPlan(
            parameter_specs=[ParameterSpec(name="shock", lower_bound=0, upper_bound=1)],
            strategy=AdversarialStrategy.GRID_EXTREME,
            stop_on_first_vulnerability=mode == "early_stop",
            vulnerability_threshold=-0.5 if mode == "early_stop" else 0.5,
        ),
        base_objective=CompositeObjective([GDPGrowthObjective()]),
        stage_b_evaluator=evaluate,
        cas=FileSystemCAS(cas_path),
    )
    payload = canon.from_canonical_bytes(FileSystemCAS(cas_path).get_bytes(report.cas_artifact_id))
    reopened = StressTestReport.model_validate(payload)
    finite = sum(math.isfinite(value) for value in observations)
    unknown = len(observations) - finite
    violated = sum(
        math.isfinite(value) and -value > (-0.5 if mode == "early_stop" else 0.5)
        for value in observations
    )
    metadata = reopened.metadata
    assert metadata["attempted"] == len(observations)
    assert metadata["finite_evaluated"] == finite
    assert metadata["unknown_or_nonfinite"] == unknown
    assert metadata["violated_scenarios"] == violated
    assert metadata["planned_scenarios"] == 2  # Two endpoints in the declared one-axis grid.
    fraction = (finite - violated) / finite if finite else None
    assert reopened.robustness_score == fraction
    assert reopened.set_adequacy_status == ("complete" if mode == "complete" else "partial")
    stage = consumer.Level5RefutationGovernanceStage(require_hidden_holdout=False)
    funnel = FunnelOrchestrator([stage])
    outcome = funnel.advance(funnel.submit({}, {"stress_test_report": reopened}), policy="full")
    assessment = outcome.final_result.feedback["stress_observed_sample_assessment"]
    assert assessment["status"] == reopened.set_adequacy_status
    assert assessment["observed_fraction"] == fraction
    assert assessment["population_probability"] == "not_established"
    assert outcome.final_result.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1
    assert outcome.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1
    assert outcome.final_result.feedback["stress_robust"] is (
        reopened.is_robust if mode == "complete" else None
    )
    print(
        json.dumps(
            {
                "case": mode,
                "verdict": "PASS",
                "attempted": len(observations),
                "finite_evaluated": finite,
                "violated": violated,
                "unknown": unknown,
                "planned": 2,
                "observed_fraction": fraction,
                "status": assessment["status"],
                "model_uncertainty": 1,
                "population_probability": "not_established",
                "cas_path": str(cas_path),
            }
        )
    )


if __name__ == "__main__":
    main()
