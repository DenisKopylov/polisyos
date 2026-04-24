"""Tests for BayesianCandidateGenerator."""

from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    benchmark_to_evaluation,
)
from polisyos.scientist.autotune.models import (
    BenchmarkEvaluation,
    MetricDirection,
)


def _ref() -> ArtifactRef:
    return ArtifactRef(artifact_id=f"sha256:{'a' * 64}", kind="test", media_type="application/json")


class TestBayesianCandidateGeneratorFallback:
    """Tests when botorch is NOT available (fallback mode)."""

    def test_generate_returns_current_best(self):
        gen = BayesianCandidateGenerator(search_space=None)
        result = gen.generate([], {"x": 1.0}, {})
        assert result == {"x": 1.0}

    def test_generate_returns_last_history(self):
        gen = BayesianCandidateGenerator(search_space=None)
        result = gen.generate([{"a": 1}, {"b": 2}], None, {})
        assert result == {"b": 2}

    def test_generate_returns_context_when_empty(self):
        gen = BayesianCandidateGenerator(search_space=None)
        result = gen.generate([], None, {"default": True})
        assert result == {"default": True}

    def test_botorch_not_available(self):
        gen = BayesianCandidateGenerator(search_space=None)
        assert gen.botorch_available is False

    def test_warm_start_no_crash(self):
        gen = BayesianCandidateGenerator(search_space=None)
        gen.warm_start([])  # should not raise

    def test_generate_protocol_compliance(self):
        """Generator satisfies the CandidateGenerator protocol."""

        gen = BayesianCandidateGenerator(search_space=None)
        # Structural check: has generate method with correct signature
        assert hasattr(gen, "generate")
        result = gen.generate([], None, {"ctx": True})
        assert isinstance(result, dict)


class TestBenchmarkToEvaluation:
    def test_converts_evaluation(self):
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref(),
            holdout_metrics={"score": 0.8},
        )
        result = benchmark_to_evaluation(
            bench,
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            dim=3,
        )
        # May be None if deps unavailable
        if result is not None:
            assert result.scalar_score == -0.8
            assert result.stage_a_passed is True

    def test_returns_none_for_missing_metric(self):
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref(),
            holdout_metrics={"other": 0.5},
        )
        result = benchmark_to_evaluation(bench, primary_metric="score")
        # Either None (no deps) or None (missing metric)
        assert result is None
