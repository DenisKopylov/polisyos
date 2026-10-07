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


@pytest.mark.parametrize("field", ["model_id", "model_version"])
@pytest.mark.parametrize(
    "unavailable", ["missing", "empty", "whitespace", "unknown", "bool", "non-string"]
)
def test_undeclared_embedding_basis_cannot_establish_semantic_convergence(
    field: str, unavailable: str
) -> None:
    embedder = MeasurementStream([1.0, 0.0])
    if unavailable == "missing":
        delattr(embedder, field)
    else:
        invalid = {
            "empty": "",
            "whitespace": " \t\n ",
            "unknown": "unknown",
            "bool": True,
            "non-string": 17,
        }
        setattr(embedder, field, invalid[unavailable])
    detector = ConvergenceDetector(
        ConvergenceConfig(strategy=ConvergenceStrategy.EMBEDDING_COSINE, min_iterations=3),
        embedder=embedder,
    )
    # Fresh equal vectors cannot supply an absent owner model/version basis.
    results = [detector.check_with_text(value, "same") for value in [10.0, 20.0, 30.0]]
    assert not any(result.converged for result in results)
    # Restoring a declared owner basis requires two consecutive fresh records;
    # a prior unknown record cannot be relabeled as a compatible observation.
    setattr(embedder, field, "known-embedding" if field == "model_id" else "1.0")
    assert not detector.check_with_text(40.0, "same").converged
    assert detector.check_with_text(50.0, "same").converged


@pytest.mark.parametrize("model_field", ["model_id", "model_name"])
@pytest.mark.parametrize("version_field", ["model_version", "version"])
def test_declared_existing_embedding_owner_aliases_preserve_fresh_cosine(
    model_field: str, version_field: str
) -> None:
    embedder = MeasurementStream([1.0, 0.0])
    del embedder.model_id
    del embedder.model_version
    setattr(embedder, model_field, "known-embedding")
    setattr(embedder, version_field, "1.0")
    detector = ConvergenceDetector(
        ConvergenceConfig(strategy=ConvergenceStrategy.EMBEDDING_COSINE, min_iterations=3),
        embedder=embedder,
    )
    results = [detector.check_with_text(value, "same") for value in [10.0, 20.0, 30.0]]
    assert [result.converged for result in results] == [False, False, True]


@pytest.mark.parametrize(
    "invalid",
    [True, "1", 10**400, float("nan"), float("inf")],
    ids=["bool", "string", "overflow", "nan", "infinity"],
)
def test_invalid_current_embedding_remains_missing_until_two_fresh_records(invalid: object) -> None:
    embedder = MeasurementStream([invalid, 0.0])
    detector = ConvergenceDetector(
        ConvergenceConfig(strategy=ConvergenceStrategy.EMBEDDING_COSINE, min_iterations=3),
        embedder=embedder,
    )
    assert not detector.check_with_text(10.0, "same").converged
    assert not detector.check_with_text(20.0, "same").converged
    # A failed numerical observation is absent evidence, not a leaked decoder
    # exception and not permission to compare the two old identical vectors.
    unavailable = detector.check_with_text(30.0, "same")
    assert not unavailable.converged
    assert unavailable.iteration == 3
    assert unavailable.history == [10.0, 20.0, 30.0]
    assert len(detector._text_embeddings) == 2
    embedder.last = [1.0, 0.0]
    assert not detector.check_with_text(40.0, "same").converged
    assert len(detector._text_embeddings) == 3
    assert detector.check_with_text(50.0, "same").converged
    assert len(detector._text_embeddings) == 4
