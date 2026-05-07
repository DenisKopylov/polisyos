"""Tests for CandidateGenerator protocol compliance."""

from __future__ import annotations

from polisyos.scientist.methods.autotune.bayesian_generator import BayesianCandidateGenerator
from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator


class TestCandidateProtocol:
    def test_sequence_generator_complies(self):
        gen = SequenceCandidateGenerator([{"x": 1}, {"x": 2}])
        result = gen.generate([], None, {})
        assert isinstance(result, dict)
        assert "x" in result

    def test_bayesian_generator_complies(self):
        gen = BayesianCandidateGenerator(search_space=None)
        result = gen.generate([], {"x": 0.5}, {})
        assert isinstance(result, dict)
