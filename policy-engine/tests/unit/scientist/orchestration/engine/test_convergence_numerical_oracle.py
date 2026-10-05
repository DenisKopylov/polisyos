"""B41 controls for the real detector, with analytic embedding observations."""

from __future__ import annotations

import pytest

from polisyos.scientist.orchestration.engine.convergence import (
    ConvergenceConfig,
    ConvergenceDetector,
    ConvergenceStrategy,
)


class AnalyticEmbedder:
    """Produce declared vectors and optional failures, dimension/version changes."""

    model_id = "analytic-identity"
    model_version = "v1"

    def __init__(self, change: str) -> None:
        self.change = change
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls == 3 and self.change == "failure":
            raise RuntimeError("declared current measurement failure")
        if self.calls == 3 and self.change == "dimension":
            return [[1.0, 0.0, 0.0]]
        if self.calls == 3 and self.change == "orthogonal":
            return [[0.0, 1.0]]
        return [[1.0, 0.0] for _ in texts]


@pytest.mark.parametrize(
    "change, expected",
    [
        ("same", True),
        ("failure", False),
        ("absent", False),
        ("dimension", False),
        ("version", False),
        ("model", False),
        ("orthogonal", False),
    ],
)
def test_current_compatible_pair_is_required_for_semantic_convergence(
    change: str,
    expected: bool,
) -> None:
    embedder = AnalyticEmbedder(change)
    detector = ConvergenceDetector(
        ConvergenceConfig(
            strategy=ConvergenceStrategy.EMBEDDING_COSINE,
            min_iterations=3,
            max_iterations=10,
            threshold=0.99,
        ),
        embedder=embedder,
    )
    assert not detector.check_with_text(10.0, "iteration-one").converged
    assert not detector.check_with_text(20.0, "iteration-two").converged
    if change == "version":
        embedder.model_version = "v2"
    if change == "model":
        embedder.model_id = "different-model"
    result = detector.check_with_text(30.0, None if change == "absent" else "iteration-three")
    assert result.iteration == 3
    assert result.converged is expected
    assert result.reason == ("converged_embedding_cosine" if expected else "")
    # A failed/absent current measurement must not be disguised by two old records.
    if change in {"failure", "absent"}:
        assert detector.check_with_text(40.0, "iteration-four").converged is False
        assert detector.check_with_text(50.0, "iteration-five").converged is True


def test_freshness_removal_control_retains_records_but_falsifies_no_stale_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the real detector with only the freshness predicate removed in memory."""
    detector = ConvergenceDetector(
        ConvergenceConfig(
            strategy=ConvergenceStrategy.EMBEDDING_COSINE,
            min_iterations=3,
            max_iterations=10,
            threshold=0.99,
        ),
        embedder=AnalyticEmbedder("failure"),
    )
    detector.check_with_text(10.0, "first")
    detector.check_with_text(20.0, "second")
    monkeypatch.setattr(
        detector, "_current_embedding_pair", lambda: tuple(detector._text_embeddings[-2:])
    )
    result = detector.check_with_text(30.0, "third")
    with pytest.raises(AssertionError):
        assert not result.converged
