"""Direct ordered-coordinate dominance, independently of the production fast paths."""

from itertools import product
from random import Random

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.methods.autotune.pareto import ParetoFront, ParetoPromoter


@pytest.mark.parametrize(
    "directions",
    [choice for dimension in range(1, 5) for choice in product((-1, 1), repeat=dimension)],
)
def test_declared_direction_lattice_matches_direct_dominance_after_permutation(directions):
    # This expected relation uses only the mathematical coordinate order, not a
    # production dominance helper, coordinate decoder, or member-index selector.
    points = list(product((-1.0, 0.0, 1.0), repeat=len(directions)))
    points.append(tuple(float(direction) for direction in directions))
    normalized = [
        tuple(x * sign for x, sign in zip(point, directions, strict=True)) for point in points
    ]
    expected = {
        f"sha256:{index + 1:064x}"
        for index, point in enumerate(normalized)
        if not any(
            all(a >= b for a, b in zip(other, point, strict=True))
            and any(a > b for a, b in zip(other, point, strict=True))
            for other in normalized
        )
    }
    assert len(expected) == 2  # Equal best values retain their two independent IDs.
    policies = [
        PromotionPolicy(
            loop_id="fixture",
            primary_metric=f"axis-{i}",
            unit=f"declared-axis-{i}-units",
            direction=MetricDirection.MAXIMIZE if sign == 1 else MetricDirection.MINIMIZE,
        )
        for i, sign in enumerate(directions)
    ]
    evaluations = [
        BenchmarkEvaluation(
            loop_id="fixture",
            suite_id="fixture",
            candidate_ref=ArtifactRef(
                artifact_id=f"sha256:{index + 1:064x}",
                kind="fixture",
                media_type="application/json",
            ),
            holdout_metrics={f"axis-{i}": value for i, value in enumerate(point)},
        )
        for index, point in enumerate(points)
    ]
    shuffled = list(evaluations)
    Random(53).shuffle(shuffled)  # noqa: S311 - deterministic permutation, not a security token
    promoter = ParetoPromoter(policies)
    for order in (evaluations, list(reversed(evaluations)), shuffled):
        front = promoter.compute_front(order)
        reopened = ParetoFront.model_validate_json(front.model_dump_json())
        assert {member.candidate_ref_id for member in reopened.members} == expected
        assert reopened.input_assessment.status == "complete"
        for evaluation in evaluations:
            assert promoter.is_dominated(evaluation, reopened) == (
                str(evaluation.candidate_ref.artifact_id) not in expected
            )
