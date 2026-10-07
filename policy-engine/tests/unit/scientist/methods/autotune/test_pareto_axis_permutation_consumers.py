"""Whole coordinate permutations preserve the direct dominance relation at CAS."""

from itertools import permutations

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


def _expected_ids(points):
    return {
        f"sha256:{index + 1:064x}"
        for index, point in enumerate(points)
        if not any(
            all(left >= right for left, right in zip(other, point, strict=True))
            and any(left > right for left, right in zip(other, point, strict=True))
            for other in points
        )
    }


def _reopen(root, payload):
    ref = FileSystemCAS(root).put_json(
        payload,
        ArtifactWriteOptions(
            kind="declared-axis-permutation.front",
            media_type="application/json",
            schema=SchemaInfo(name="declared-axis-permutation.front", version="2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return load_model_artifact(FileSystemCAS(root), ref, ParetoFront)


@pytest.mark.parametrize("dimension", range(1, 5))
@pytest.mark.parametrize("direction_profile", ["maximize", "minimize", "mixed"])
def test_whole_axis_permutations_match_all_pairs_through_fresh_cas_reader(
    tmp_path, dimension, direction_profile
):
    signs = [
        -1 if direction_profile == "minimize" or (direction_profile == "mixed" and axis % 2) else 1
        for axis in range(dimension)
    ]
    axes = [
        tuple(2.0 if axis == special else 0.0 for axis in range(dimension))
        for special in range(dimension)
    ]
    points = [
        *axes,
        (1.0,) * dimension,
        (0.0,) * dimension,
        (-1.0,) * dimension,
        (1.0,) + (0.0,) * (dimension - 1),
        axes[0],
        (1.0,) * dimension,
    ]
    expected = _expected_ids(points)
    assert f"sha256:{1:064x}" in expected
    assert f"sha256:{dimension + 5:064x}" in expected  # Distinct equal maximum/axis ID.
    policies = [
        PromotionPolicy(
            loop_id="axis-permutation",
            primary_metric=f"axis-{axis}",
            compare_split=BenchmarkSplit.SELECTION if axis % 2 else BenchmarkSplit.HOLDOUT,
            unit=f"axis-{axis}-units",
            direction=MetricDirection.MAXIMIZE if sign == 1 else MetricDirection.MINIMIZE,
        )
        for axis, sign in enumerate(signs)
    ]
    rows = []
    for index, point in enumerate(points):
        split_metrics = {BenchmarkSplit.SELECTION: {}, BenchmarkSplit.HOLDOUT: {}}
        for axis, policy in enumerate(policies):
            split_metrics[policy.compare_split][policy.primary_metric] = point[axis] * signs[axis]
        rows.append(
            BenchmarkEvaluation(
                loop_id="axis-permutation",
                suite_id="declared-axis-permutation.v1",
                candidate_ref=ArtifactRef(
                    artifact_id=f"sha256:{index + 1:064x}",
                    kind="declared-geometric-candidate",
                    media_type="application/json",
                ),
                selection_metrics=split_metrics[BenchmarkSplit.SELECTION],
                holdout_metrics=split_metrics[BenchmarkSplit.HOLDOUT],
            )
        )
    original_values = original_reference = None
    for order in permutations(range(dimension)):
        promoter = ParetoPromoter(
            [policies[axis] for axis in order],
            definition_versions=[f"axis-{axis}.v1" for axis in order],
        )
        reordered_rows = rows if order[0] % 2 else list(reversed(rows))
        front = _reopen(tmp_path / str(order), promoter.compute_front(reordered_rows))
        assert {member.candidate_ref_id for member in front.members} == expected
        assert front.input_assessment.status == "complete"
        values = {member.candidate_ref_id: member.coordinate_values for member in front.members}
        if original_values is None:
            original_values, original_reference = (
                values,
                front.coordinate_reference_point,
            )
        assert values == original_values
        assert front.coordinate_reference_point == original_reference
        for row in rows:
            assert promoter.is_dominated(row, front) == (
                str(row.candidate_ref.artifact_id) not in expected
            )
        # Presentation labels are separately mutable from the coordinate contract.
        payload = front.model_dump(mode="json")
        for member in payload["members"]:
            member["objectives"] = {
                "label:" + key: value for key, value in member["objectives"].items()
            }
        payload["reference_point"] = {
            "label:" + key: value for key, value in payload["reference_point"].items()
        }
        labeled = _reopen(tmp_path / (str(order) + "-labels"), payload)
        assert {member.candidate_ref_id for member in labeled.members} == expected
        for row in rows:
            assert promoter.is_dominated(row, labeled) == promoter.is_dominated(row, front)
        stale = ParetoPromoter(
            [policies[axis] for axis in order],
            definition_versions=[f"axis-{axis}.v2" for axis in order],
        )
        with pytest.raises(ValueError, match="basis differs"):
            stale.is_dominated(rows[0], labeled)
