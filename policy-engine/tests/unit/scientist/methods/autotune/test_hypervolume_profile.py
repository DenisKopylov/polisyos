"""Quantity and typed-coordinate consumer checks; synthetic inputs only."""

from itertools import permutations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune import pareto
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.methods.autotune.pareto import (
    ParetoFront,
    ParetoPromoter,
    compute_hypervolume_assessed,
)


def row(index=1, **values):
    return BenchmarkEvaluation(
        loop_id="quantity",
        suite_id="synthetic",
        candidate_ref=ArtifactRef(
            artifact_id=f"sha256:{index:064x}", kind="synthetic", media_type="application/json"
        ),
        holdout_metrics=values,
        promotable=True,
    )


@pytest.mark.parametrize(
    ("points", "ref", "expected"),
    [
        ([(2.0,)], (0.0,), 2.0),
        ([(3.0, 1.0), (1.0, 3.0)], (0.0, 0.0), 5.0),
        ([(2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 2.0)], (0.0, 0.0, 0.0), 0.0),
        ([(3.0, 1.0, 2.0), (1.0, 3.0, 2.0), (2.0, 2.0, 3.0)], (0.0, 0.0, 0.0), 16.0),
        (
            [(3.0, 1.0, 2.0, 1.0), (1.0, 3.0, 2.0, 1.0), (2.0, 2.0, 3.0, 1.0)],
            (0.0, 0.0, 0.0, 0.0),
            16.0,
        ),
    ],
)
def test_actual_quantity_is_exact_and_order_independent(points, ref, expected):
    for ordered in permutations(points):
        result = compute_hypervolume_assessed(list(ordered), ref)
        assert result.value == expected
        assert result.assessment.status == "available"
        assert result.assessment.basis == "recomputed"
        assert result.assessment.profile == "dominated_box_union.float64.maximize.v1"
        if len(ref) > 2 and expected:
            assert result.assessment.algorithm == "botorch_dominated_partitioning"
            assert "botorch=0.16.1" in result.assessment.backend_version


def test_unsupported_backend_has_no_substitute_quantity(monkeypatch):
    monkeypatch.setattr(pareto, "version", lambda package: "unverified")
    result = compute_hypervolume_assessed([(1.0, 1.0, 1.0)], (0.0, 0.0, 0.0))
    assert result.value is None
    assert result.assessment.reason == "unsupported_backend_profile"
    # A mathematically empty box union requires no optional backend.
    assert compute_hypervolume_assessed([(1.0, 0.0, 0.0)], (0.0, 0.0, 0.0)).value == 0.0


@pytest.mark.parametrize("raw", [True, "broken", 10**400, float("nan"), float("inf")])
def test_mutable_scalar_input_is_refused_as_one_original_row(raw):
    good, invalid = row(1, score=2.0), row(2, score=1.0)
    invalid.holdout_metrics["score"] = raw  # post-validation stress, not healthy typed admission
    promoter = ParetoPromoter([PromotionPolicy(loop_id="quantity", primary_metric="score")])
    front = promoter.compute_front([good, invalid])
    assert [member.candidate_ref_id for member in front.members] == [
        str(good.candidate_ref.artifact_id)
    ]
    assert front.input_assessment.status == "partial"
    assert front.input_assessment.unassessed_evaluations[0].input_index == 1
    assert front.input_assessment.unassessed_evaluations[0].non_finite_coordinate_ids


def test_full_coordinate_version_split_unit_roundtrip_and_changed_basis_refusal():
    policies = [
        PromotionPolicy(
            loop_id="quantity",
            primary_metric="score",
            compare_split=split,
            unit="score_units",
            direction=MetricDirection.MAXIMIZE,
        )
        for split in (BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT)
    ]
    promoter = ParetoPromoter(policies, definition_versions=["definition.1", "definition.1"])
    a, b = row(1, score=1.0), row(2, score=10.0)
    a.selection_metrics["score"], b.selection_metrics["score"] = 10.0, 1.0
    front = ParetoFront.model_validate_json(promoter.compute_front([a, b]).model_dump_json())
    assert front.size == 2
    assert front.coordinate_schema.version == "pareto-coordinate.v2"
    assert (
        len({coordinate.coordinate_id for coordinate in front.coordinate_schema.coordinates}) == 2
    )
    assert not promoter.is_dominated(a, front)
    changed = ParetoPromoter(policies, definition_versions=["definition.2", "definition.1"])
    with pytest.raises(ValueError, match="basis differs"):
        changed.is_dominated(a, front)
    with pytest.raises(ValueError, match="unique"):
        ParetoPromoter(
            [policies[0], policies[0]], definition_versions=["definition.1", "definition.1"]
        )


def test_supported_dimension_and_no_input_boundaries_are_explicit():
    unsupported = compute_hypervolume_assessed([(1.0,) * 5], (0.0,) * 5)
    assert unsupported.value is None
    assert unsupported.assessment.reason == "unsupported_dimension_profile"
    empty = compute_hypervolume_assessed([], (0.0, 0.0))
    assert empty.value is None
    assert empty.assessment.reason == "no_usable_inputs"
    known_zero = compute_hypervolume_assessed([(1.0, 0.0)], (0.0, 0.0))
    assert known_zero.value == 0.0
    assert known_zero.assessment.basis == "recomputed"
