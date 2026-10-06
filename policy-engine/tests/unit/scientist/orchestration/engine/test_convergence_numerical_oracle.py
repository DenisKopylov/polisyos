"""Freshness witnesses execute the existing provenance-aware detector."""

import pytest

from polisyos.scientist.orchestration.engine.convergence import (
    ConvergenceConfig,
    ConvergenceDetector,
    ConvergenceStrategy,
)


class MeasurementStream:
    """Yield known vectors or a failed measurement with mutable provenance."""

    def __init__(self, last: object) -> None:
        self.last = last
        self.calls = 0
        self.model_id = "known-embedding"
        self.model_version = "1.0"

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls < 3:
            return [[1.0, 0.0]]
        if isinstance(self.last, Exception):
            raise self.last
        return [self.last]


@pytest.mark.parametrize("changed", ["failure", "dimension", "model", "version", "missing"])
def test_current_measurement_is_required_despite_two_equal_old_vectors(changed: str) -> None:
    last = RuntimeError("current measurement unavailable") if changed == "failure" else [1.0, 0.0]
    if changed == "dimension":
        last = [1.0, 0.0, 0.0]
    embedder = MeasurementStream(last)
    detector = ConvergenceDetector(
        ConvergenceConfig(strategy=ConvergenceStrategy.EMBEDDING_COSINE, min_iterations=3),
        embedder=embedder,
    )
    for value in [10.0, 20.0]:
        assert not detector.check_with_text(value, "same").converged
    if changed == "model":
        embedder.model_id = "different-model"
    if changed == "version":
        embedder.model_version = "2.0"
    result = detector.check_with_text(30.0, None if changed == "missing" else "same")
    assert not result.converged


def test_two_current_compatible_vectors_have_analytic_cosine_one() -> None:
    detector = ConvergenceDetector(
        ConvergenceConfig(strategy=ConvergenceStrategy.EMBEDDING_COSINE, min_iterations=3),
        embedder=MeasurementStream([1.0, 0.0]),
    )
    results = [detector.check_with_text(value, "same") for value in [10.0, 20.0, 30.0]]
    assert [r.converged for r in results] == [False, False, True]
