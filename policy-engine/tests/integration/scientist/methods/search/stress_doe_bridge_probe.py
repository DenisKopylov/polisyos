"""Actual E DOE APIs feed D adaptive stress and blueprint publication."""

from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.autotune.sensitivity_bridge import SensitivityBridge
from polisyos.scientist.methods.doe import sampling
from polisyos.scientist.methods.doe.adaptive import AdaptiveSampler, ConvergenceConfig
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.adversarial import run_stress_test
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _recompute_stress_test_report,
)


def main() -> None:
    store_root = Path(tempfile.mkdtemp(prefix="e02-D-E-bridge-cas-", dir="/dev/shm"))
    store = FileSystemCAS(store_root)
    calls = []

    def physical_cost(parameters):
        calls.append(dict(parameters))
        return 2.0 * parameters["p"] + 0.5 * parameters["q"]

    bounds = [
        {"name": name, "lower": 0.0, "upper": 1.0, "unit": "dimensionless"} for name in ("p", "q")
    ]
    answer = SensitivityBridge().analyze_search_space(
        bounds,
        physical_cost,
        method="morris",
        n_trajectories=2,
        seed=7,
        input_law="independent",
        store=store,
        max_estimated_runs=6,
    )
    assert len(calls) == 6 and answer["ranking"] == ["p", "q"]
    assert math.isclose(answer["result"].mu_star["p"], 2.0)
    assert math.isclose(answer["result"].mu_star["q"], 0.5)

    class BaseGenerator:
        def __init__(self):
            self.calls = 0

        def generate(self, history, current_best, context):
            self.calls += 1
            return {"semantic": {"interventions": []}, "p": 1.0, "q": 1.0}

    streams = []
    reports = []
    for top_k in (1, 20):
        base = BaseGenerator()
        adapter = SensitivityAwareCandidateGenerator.from_artifact(
            base,
            FileSystemCAS(store_root),
            answer["analysis_ref"],
        )
        observed = []

        def evaluate(candidate, context, observed=observed):
            cost = 2.0 * candidate["p"] + 0.5 * candidate["q"]
            observed.append(cost)
            if "_sensitivity" in candidate:
                assert candidate["_sensitivity"]["analysis_ref"]["artifact_id"] == str(
                    answer["analysis_ref"].artifact_id
                )
                assert candidate["_sensitivity"]["population_law_status"] == "not_established"
            return {"simulation_results": {"budget_deficit": cost}}

        report = run_stress_test(
            adversarial_plan=AdversarialPlan(
                parameter_specs=[
                    ParameterSpec(name=name, lower_bound=0, upper_bound=1) for name in ("p", "q")
                ],
                strategy=AdversarialStrategy.SEARCH_LOOP,
                max_iterations=38,
                seed=7,
                stop_on_first_vulnerability=False,
                collect_top_k=top_k,
                vulnerability_threshold=1.75,
            ),
            base_objective=CompositeObjective([BudgetDeficitObjective()]),
            stage_b_evaluator=evaluate,
            candidate_generator=adapter,
        )
        violated = sum(value >= 1.75 for value in observed)
        assert base.calls == 6 and len(observed) == 38
        assert report.robustness_score == (38 - violated) / 38
        assert report.worst_case_objective == max(observed) == 2.5
        published = _recompute_stress_test_report(report)
        assert published.scenario_evidence.violated_scenarios == violated
        assert published.robustness_score == report.robustness_score
        ref = store.put_json(
            published.model_dump(mode="json"),
            PutOptions(
                kind="scientist.stress_test_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.StressTestReport", version=published.schema_version
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        restored = StressTestReport.model_validate(
            from_canonical_bytes(FileSystemCAS(store_root).get_bytes(ref.artifact_id))
        )
        assert restored.scenario_evidence == published.scenario_evidence
        streams.append(observed)
        reports.append(
            {
                "top_k": top_k,
                "report_ref": str(ref.artifact_id),
                "observed": observed,
                "evidence": restored.scenario_evidence.model_dump(mode="json"),
                "observed_fraction": restored.robustness_score,
                "retained_examples": len(restored.vulnerabilities),
            }
        )
    assert streams[0] == streams[1]
    # Real E oversized plan intake must fail before sampling or evaluator work.
    sampling_calls = []
    original_sampling = sampling.generate_sensitivity_samples

    def counted_sampling(plan):
        sampling_calls.append(plan)
        return original_sampling(plan)

    sampling.generate_sensitivity_samples = counted_sampling
    before = len(calls)
    try:
        with pytest.raises(ValueError, match="estimated_runs"):
            SensitivityBridge().analyze_search_space(
                bounds,
                physical_cost,
                method="morris",
                n_trajectories=2,
                seed=7,
                input_law="independent",
                max_estimated_runs=5,
            )
        assert sampling_calls == []
        assert len(calls) == before
    finally:
        sampling.generate_sensitivity_samples = original_sampling
    # The existing real E adaptive producer returns only declared completed rounds.
    adaptive_calls = []

    def adaptive_evaluate(matrix):
        adaptive_calls.append(len(matrix))
        return 2.0 * matrix[:, 0] + 0.5 * matrix[:, 1]

    adaptive = AdaptiveSampler(
        SensitivityPlan(
            method=SensitivityMethod.MORRIS,
            parameter_specs=[
                ParameterSpec(name=name, lower_bound=0, upper_bound=1) for name in ("p", "q")
            ],
            n_trajectories=2,
            seed=7,
            max_estimated_runs=15,
            allow_large_run=False,
        ),
        ConvergenceConfig(max_rounds=2, trajectory_step=2),
    ).run(adaptive_evaluate)
    assert (
        adaptive_calls == [6, 12] and adaptive.total_evaluations == 18 and len(adaptive.rounds) == 2
    )
    # The next estimated round is refused before sampling/materialization.
    from polisyos.scientist.methods.doe import adaptive as adaptive_module

    original_adaptive_sampling = adaptive_module.generate_sensitivity_samples
    admitted_rounds = []
    guarded_calls = []

    def counted_adaptive_sampling(plan):
        admitted_rounds.append(plan.estimated_runs)
        return original_adaptive_sampling(plan)

    def guarded_evaluate(matrix):
        guarded_calls.append(len(matrix))
        return 2.0 * matrix[:, 0] + 0.5 * matrix[:, 1]

    adaptive_module.generate_sensitivity_samples = counted_adaptive_sampling
    try:
        guarded = AdaptiveSampler(
            SensitivityPlan(
                method=SensitivityMethod.MORRIS,
                parameter_specs=[
                    ParameterSpec(name=name, lower_bound=0, upper_bound=1) for name in ("p", "q")
                ],
                n_trajectories=2,
                seed=7,
                max_estimated_runs=9,
                allow_large_run=False,
            ),
            ConvergenceConfig(max_rounds=2, trajectory_step=2),
        ).run(guarded_evaluate)
    finally:
        adaptive_module.generate_sensitivity_samples = original_adaptive_sampling
    assert admitted_rounds == guarded_calls == [6]
    assert guarded.total_evaluations == 6 and len(guarded.rounds) == 1
    assert guarded.stop_reason == "max_estimated_runs_exceeded"
    # Observe the real product iterator before materialization, with a bounded falsifier.
    original_product = sampling.itertools.product
    enumerated = []

    def counted_product(*axes):
        for corner in original_product(*axes):
            enumerated.append(corner)
            assert len(enumerated) <= 3, "exponential materialization before prefix admission"
            yield corner

    sampling.itertools.product = counted_product
    try:
        prefix = sampling.generate_adversarial_samples(
            AdversarialPlan(
                parameter_specs=[
                    ParameterSpec(name=f"p{i}", lower_bound=0, upper_bound=1) for i in range(12)
                ],
                strategy=AdversarialStrategy.GRID_EXTREME,
                max_iterations=3,
            )
        )
    finally:
        sampling.itertools.product = original_product
    assert len(enumerated) == 3 and prefix.shape == (3, 12) and prefix.base is None
    assert np.array_equal(prefix, np.array(enumerated))
    modules = {}
    for name, module in sorted(sys.modules.copy().items()):
        if name in {
            "polisyos.scientist.methods.autotune.sensitivity_bridge",
            "polisyos.scientist.methods.search.sensitivity_adapter",
            "polisyos.scientist.methods.doe.designs",
            "polisyos.scientist.methods.doe.analysis",
            "polisyos.scientist.methods.doe.sampling",
            "polisyos.scientist.methods.doe.adaptive",
            "polisyos.scientist.methods.doe._receipt",
            "polisyos.scientist.methods.doe.stress_report",
            "polisyos.scientist.methods.search.adversarial",
            "polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime",
        }:
            path = Path(module.__file__).resolve()
            modules[name] = {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    print(
        json.dumps(
            {
                "outcome": "PASS",
                "executable": sys.executable,
                "python": sys.version,
                "cas_directory": str(store_root),
                "analysis_ref": str(answer["analysis_ref"].artifact_id),
                "reports": reports,
                "doe_oversize": {"sampling_calls": 0, "evaluator_calls": 0},
                "adaptive": {"rows": adaptive_calls, "rounds": 2, "total_evaluations": 18},
                "adaptive_oversize": {
                    "admitted_sampling_rows": admitted_rounds,
                    "evaluator_rows": guarded_calls,
                    "rounds": len(guarded.rounds),
                    "total_evaluations": guarded.total_evaluations,
                    "stop_reason": guarded.stop_reason,
                },
                "grid_prefix": {
                    "dimensions": 12,
                    "enumerated": 3,
                    "possible_corners": 4096,
                    "owns_memory": True,
                    "whole_space_coverage": "not_established",
                },
                "modules": modules,
                "population_law": "not_established",
                "default_deployment": "not_established",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
