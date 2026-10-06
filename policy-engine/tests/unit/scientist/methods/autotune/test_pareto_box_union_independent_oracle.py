"""Independent box unions for the canonical autotune Pareto consumer.

Expected volumes use exact rational inclusion-exclusion, never BoTorch or a
production indicator. These small declared fixtures establish geometry and
coordinate custody, not a complete production candidate universe.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations, permutations
from math import prod
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    PromotionPolicy,
    load_model_artifact,
)
from polisyos.scientist.methods.autotune.pareto import ParetoFront, ParetoPromoter

if TYPE_CHECKING:
    from collections.abc import Sequence


def _box_union(points: Sequence[Sequence[int]], reference: Sequence[int]) -> Fraction:
    """Measure the union of lower-reference boxes by inclusion-exclusion."""
    result = Fraction(0)
    for size in range(1, len(points) + 1):
        for subset in combinations(points, size):
            widths = [
                max(Fraction(0), Fraction(min(point[axis] for point in subset) - lower))
                for axis, lower in enumerate(reference)
            ]
            result += (-1) ** (size + 1) * prod(widths)
    return result


def _policies(signs: Sequence[int]) -> list[PromotionPolicy]:
    return [
        PromotionPolicy(
            loop_id="box-union",
            primary_metric=f"axis-{axis}",
            unit=f"physical-axis-{axis}-units",
            direction=MetricDirection.MAXIMIZE if sign == 1 else MetricDirection.MINIMIZE,
        )
        for axis, sign in enumerate(signs)
    ]


def _evaluation(index: int, values: Sequence[int]) -> BenchmarkEvaluation:
    return BenchmarkEvaluation(
        loop_id="box-union",
        suite_id="declared-geometric-fixture",
        candidate_ref=ArtifactRef(
            artifact_id=f"sha256:{index + 1:064x}",
            kind="declared-geometric-fixture",
            media_type="application/json",
        ),
        holdout_metrics={f"axis-{axis}": value for axis, value in enumerate(values)},
    )


def _assert_volume(front: ParetoFront, expected: Fraction) -> None:
    assert front.hypervolume is not None, "numerical geometry positive remains UNRUN if unavailable"
    assert front.hypervolume == pytest.approx(float(expected), rel=1e-12, abs=1e-12)
    if front.hypervolume_assessment is not None:
        assert front.hypervolume_assessment.status == "available"
        assert front.hypervolume_assessment.basis == "recomputed"


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        (((2, 0, 0), (0, 2, 0), (0, 0, 2)), 0),
        (((3, 1, 2), (1, 3, 2), (2, 2, 3)), 16),
        (((2, 2, 0), (1, 3, 0), (3, 1, 0)), 0),
        (((2, 2, 1), (1, 3, 2), (3, 1, 1)), 9),
    ],
)
def test_actual_three_dimensional_front_matches_independent_box_union(
    points: tuple[tuple[int, ...], ...], expected: int
) -> None:
    reference = (0, 0, 0)
    independently_computed = _box_union(points, reference)
    assert independently_computed == expected
    promoter = ParetoPromoter(_policies((1, 1, 1)))
    evaluations = [_evaluation(index, point) for index, point in enumerate((*points, reference))]
    for ordered in permutations(evaluations):
        front = promoter.compute_front(list(ordered))
        _assert_volume(front, independently_computed)
        assert front.input_assessment is not None
        assert front.input_assessment.status == "complete"
        assert front.input_assessment.input_count == 4
        assert len(front.members) == 3
        assert not promoter.is_dominated(evaluations[0], front)
        assert promoter.is_dominated(evaluations[-1], front)


@pytest.mark.parametrize("signs", [(1, 1, 1), (1, -1, 1), (-1, 1, -1)])
def test_mixed_directions_affine_references_preserve_physical_product_units(
    signs: tuple[int, ...],
) -> None:
    points = ((3, 1, 2), (1, 3, 2), (2, 2, 3))
    reference = (10, 100, 1000)
    scales = (2, 5, 10)
    physical_points = [
        tuple(
            lower + sign * scale * value
            for lower, sign, scale, value in zip(reference, signs, scales, point, strict=True)
        )
        for point in (*points, (0, 0, 0))
    ]
    expected = _box_union(points, (0, 0, 0)) * prod(scales)
    assert expected == 1600
    front = ParetoPromoter(_policies(signs)).compute_front(
        [_evaluation(index, point) for index, point in enumerate(physical_points)]
    )
    _assert_volume(front, expected)
    assert front.coordinate_schema is not None
    assert tuple(
        front.coordinate_reference_point[c.coordinate_id]
        for c in front.coordinate_schema.coordinates
    ) == tuple(sign * lower for sign, lower in zip(signs, reference, strict=True))


@pytest.mark.parametrize("points", [((3,), (1,)), ((3, 1), (1, 3), (2, 2))])
def test_existing_lower_dimensional_geometry_retains_exact_value(
    points: tuple[tuple[int, ...], ...],
) -> None:
    reference = (0,) * len(points[0])
    promoter = ParetoPromoter(_policies((1,) * len(reference)))
    front = promoter.compute_front(
        [_evaluation(index, point) for index, point in enumerate((*points, reference))]
    )
    _assert_volume(front, _box_union(points, reference))


def test_original_split_tradeoff_and_display_rename_survive_actual_cas_readback(
    tmp_path: Path,
) -> None:
    policies = [
        PromotionPolicy(
            loop_id="box-union", primary_metric="score", compare_split=split, unit="score-units"
        )
        for split in (BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT)
    ]
    promoter = ParetoPromoter(policies)
    evaluations = [
        _evaluation(index, (0,)).model_copy(
            update={
                "selection_metrics": {"score": selection},
                "holdout_metrics": {"score": holdout},
            }
        )
        for index, (selection, holdout) in enumerate(((10, 1), (1, 10)))
    ]
    original = promoter.compute_front(evaluations)
    assert len(original.members) == 2
    original_markers = original.coordinate_schema
    payload = original.model_dump(mode="json")
    for member in payload["members"]:
        member["objectives"] = {
            f"display-only-{index}": value
            for index, value in enumerate(member["objectives"].values())
        }
    payload["reference_point"] = {
        f"display-only-{index}": value
        for index, value in enumerate(payload["reference_point"].values())
    }
    renamed = ParetoFront.model_validate(payload)
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        renamed,
        ArtifactWriteOptions(
            kind="declared-pareto-front",
            media_type="application/json",
            schema=SchemaInfo(name="declared-pareto-front", version=renamed.schema_version),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    reopened = load_model_artifact(FileSystemCAS(tmp_path / "cas"), ref, ParetoFront)
    assert reopened.coordinate_schema == original_markers
    assert {member.candidate_ref_id for member in reopened.members} == {
        str(evaluation.candidate_ref.artifact_id) for evaluation in evaluations
    }
    assert len(reopened.coordinate_reference_point) == 2
    for evaluation in evaluations:
        assert not promoter.is_dominated(evaluation, reopened)


@pytest.mark.parametrize("mutation", ["unit", "direction", "split", "version"])
def test_same_coordinate_marker_cannot_hide_changed_identity(mutation: str) -> None:
    front = ParetoPromoter(_policies((1, 1, 1))).compute_front(
        [
            _evaluation(index, point)
            for index, point in enumerate(((3, 1, 2), (1, 3, 2), (2, 2, 3), (0, 0, 0)))
        ]
    )
    payload = front.model_dump(mode="json")
    schema = payload["coordinate_schema"]
    if mutation == "version":
        schema["version"] = "pareto-coordinate.v999"
    else:
        schema["coordinates"][0][mutation] = {
            "unit": "other-units",
            "direction": "minimize",
            "split": "selection",
        }[mutation]
    with pytest.raises(ValueError):
        ParetoFront.model_validate(payload)


def test_geometric_oracle_rejects_box_proxy_with_contract_markers_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    points = ((3, 1, 2), (1, 3, 2), (2, 2, 3), (0, 0, 0))
    evaluations = [_evaluation(index, point) for index, point in enumerate(points)]
    promoter = ParetoPromoter(_policies((1, 1, 1)))
    actual_consumer = promoter.compute_front

    def replace_geometry(rows: list[BenchmarkEvaluation]) -> ParetoFront:
        front = actual_consumer(rows)
        front.hypervolume = 27.0
        return front

    marker_control = actual_consumer(evaluations)
    monkeypatch.setattr(promoter, "compute_front", replace_geometry)
    broken = promoter.compute_front(evaluations)
    assert broken.coordinate_schema == marker_control.coordinate_schema
    assert broken.input_assessment == marker_control.input_assessment
    assert broken.hypervolume_assessment == marker_control.hypervolume_assessment
    assert broken.members == marker_control.members
    with pytest.raises(AssertionError):
        _assert_volume(broken, _box_union(points, (0, 0, 0)))


def test_empty_input_does_not_publish_computed_zero_volume() -> None:
    front = ParetoPromoter(_policies((1, 1, 1))).compute_front([])
    assert front.input_assessment is not None
    assert front.input_assessment.status == "no_usable_inputs"
    assert front.hypervolume is None
    assert front.hypervolume_assessment is not None
    assert front.hypervolume_assessment.status == "unavailable"
    assert front.hypervolume_assessment.basis == "not_established"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), 10**400, True, "broken"])
def test_malformed_present_axis_is_omitted_without_crashing_valid_subfront(invalid: object) -> None:
    evaluations = [
        _evaluation(index, point) for index, point in enumerate(((3, 1, 2), (1, 3, 2), (0, 0, 0)))
    ]
    evaluations[1].holdout_metrics["axis-0"] = invalid  # type: ignore[assignment]
    front = ParetoPromoter(_policies((1, 1, 1))).compute_front(evaluations)
    assert front.input_assessment is not None
    assert front.input_assessment.status == "partial"
    assert front.input_assessment.input_count == 3
    assert front.input_assessment.assessed_count == 2
    omitted = front.input_assessment.unassessed_evaluations
    assert len(omitted) == 1
    assert omitted[0].input_index == 1
    assert omitted[0].candidate_ref_id == str(evaluations[1].candidate_ref.artifact_id)
    assert omitted[0].non_finite_coordinate_ids
    assert len(front.members) == 1
    assert front.members[0].candidate_ref_id == str(evaluations[0].candidate_ref.artifact_id)
    _assert_volume(front, Fraction(6))
