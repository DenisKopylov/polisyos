"""Independent rational geometry and coordinate custody at native CAS boundaries.

Expected quantities come from exact binary-input rational box unions. Optional
MO reference checks exercise real Torch arithmetic without fitting a GP. Missing
optional modules are UNRUN, never evidence that a numerical backend passed.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import isfinite, prod
from pathlib import Path
from typing import Any

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
from polisyos.scientist.methods.autotune.pareto import (
    HypervolumeResult,
    ParetoFront,
    ParetoPromoter,
    compute_hypervolume_assessed,
)

pytestmark = pytest.mark.integration


def _union(points: tuple[tuple[float, ...], ...], reference: tuple[float, ...]) -> Fraction:
    """Exact inclusion-exclusion over the supplied finite binary floating inputs."""
    result = Fraction(0)
    for count in range(1, len(points) + 1):
        for subset in combinations(points, count):
            widths = [
                max(
                    Fraction(0),
                    min(Fraction.from_float(point[axis]) for point in subset)
                    - Fraction.from_float(lower),
                )
                for axis, lower in enumerate(reference)
            ]
            result += (-1) ** (count + 1) * prod(widths)
    return result


def _persist_and_reopen(tmp_path: Path, value: Any, model: type[Any], *, suffix: str) -> Any:
    root = tmp_path / suffix
    ref = FileSystemCAS(root).put_json(
        value,
        ArtifactWriteOptions(
            kind="independent-pareto-quantity-fixture",
            media_type="application/json",
            schema=SchemaInfo(name="independent-pareto-quantity-fixture", version="2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return load_model_artifact(FileSystemCAS(root), ref, model)


def _evaluation(
    index: int, selection: dict[str, float], holdout: dict[str, float]
) -> BenchmarkEvaluation:
    return BenchmarkEvaluation(
        loop_id="independent-quantity",
        suite_id="declared-analytic-geometry",
        candidate_ref=ArtifactRef(
            artifact_id=f"sha256:{index + 1:064x}",
            kind="declared-analytic-candidate",
            media_type="application/json",
        ),
        selection_metrics=selection,
        holdout_metrics=holdout,
    )


def _underflow(result: HypervolumeResult) -> None:
    assert result.value is None, "a strictly positive unrepresentable box cannot be computed zero"
    assert result.assessment.status == "unavailable"
    assert result.assessment.basis == "not_established"
    assert result.assessment.reason == "nonzero_derived_hypervolume_underflow"
    assert result.assessment.profile == "dominated_box_union.float64.maximize.v1"


@pytest.mark.parametrize(
    "points",
    [
        ((1e-200, 1e-200),),
        ((3e-200, 1e-200), (1e-200, 3e-200), (2e-200, 2e-200)),
    ],
)
def test_positive_rational_union_is_unavailable_when_float64_underflows(
    tmp_path: Path, points: tuple[tuple[float, ...], ...]
) -> None:
    reference = (0.0, 0.0)
    expected = _union(points, reference)
    assert expected > 0 and float(expected) == 0.0
    result = compute_hypervolume_assessed(list(points), reference)
    reopened = _persist_and_reopen(tmp_path, result, HypervolumeResult, suffix="quantity")
    assert reopened.reference_point == reference
    _underflow(reopened)


@pytest.mark.parametrize("width", [1e-150, 1e-160])
def test_small_representable_union_remains_a_positive_computed_quantity(width: float) -> None:
    expected = _union(((width, width),), (0.0, 0.0))
    assert float(expected) > 0.0
    result = compute_hypervolume_assessed([(width, width)], (0.0, 0.0))
    assert result.value == float(expected)
    assert result.assessment.status == "available"
    assert result.assessment.basis == "recomputed"
    assert result.assessment.reason is None


def test_degenerate_boxes_are_a_genuine_available_zero_after_cas_reopen(tmp_path: Path) -> None:
    points = ((1e-200, 0.0), (0.0, 1e-200))
    expected = _union(points, (0.0, 0.0))
    assert expected == 0
    result = compute_hypervolume_assessed(list(points), (0.0, 0.0))
    reopened = _persist_and_reopen(tmp_path, result, HypervolumeResult, suffix="zero")
    assert reopened.value == 0.0
    assert reopened.assessment.status == "available"
    assert reopened.assessment.basis == "recomputed"
    assert reopened.assessment.reason is None


@pytest.mark.parametrize("first_direction", [MetricDirection.MAXIMIZE, MetricDirection.MINIMIZE])
def test_native_front_retains_full_membership_and_coordinates_when_quantity_underflows(
    tmp_path: Path, first_direction: MetricDirection
) -> None:
    sign = 1.0 if first_direction is MetricDirection.MAXIMIZE else -1.0
    policies = [
        PromotionPolicy(
            loop_id="independent-quantity",
            primary_metric="length",
            unit="metres",
            compare_split=BenchmarkSplit.SELECTION,
            direction=first_direction,
        ),
        PromotionPolicy(
            loop_id="independent-quantity",
            primary_metric="duration",
            unit="seconds",
            compare_split=BenchmarkSplit.HOLDOUT,
        ),
    ]
    rows = [
        _evaluation(0, {"length": 0.0}, {"duration": 0.0}),
        _evaluation(1, {"length": sign * 1e-200}, {"duration": 1e-200}),
    ]
    assert _union(((1e-200, 1e-200),), (0.0, 0.0)) > 0
    front = ParetoPromoter(
        policies, definition_versions=["length.v1", "duration.v1"]
    ).compute_front(rows)
    reopened = _persist_and_reopen(tmp_path, front, ParetoFront, suffix="front")
    assert reopened.input_assessment is not None
    assert reopened.input_assessment.status == "complete"
    assert reopened.input_assessment.input_count == reopened.input_assessment.assessed_count == 2
    assert [m.candidate_ref_id for m in reopened.members] == [
        str(rows[1].candidate_ref.artifact_id)
    ]
    assert reopened.coordinate_schema is not None
    assert len(reopened.coordinate_schema.coordinates) == 2
    assert set(reopened.members[0].coordinate_values.values()) == {1e-200}
    assert set(reopened.coordinate_reference_point.values()) == {0.0}
    assert reopened.hypervolume_assessment is not None
    _underflow(
        HypervolumeResult(value=reopened.hypervolume, assessment=reopened.hypervolume_assessment)
    )


def _reindexed_fixture() -> tuple[ParetoFront, ParetoFront, dict[str, str]]:
    old_policies = [
        PromotionPolicy(
            loop_id="independent-quantity",
            primary_metric="gain",
            compare_split=BenchmarkSplit.SELECTION,
            direction=MetricDirection.MAXIMIZE,
            unit="metres",
        ),
        PromotionPolicy(
            loop_id="independent-quantity",
            primary_metric="cost",
            compare_split=BenchmarkSplit.HOLDOUT,
            direction=MetricDirection.MINIMIZE,
            unit="seconds",
        ),
    ]
    rows = [
        _evaluation(0, {"gain": 4.0}, {"cost": 7.0}),
        _evaluation(1, {"gain": 2.0}, {"cost": 5.0}),
        _evaluation(2, {"gain": 0.0}, {"cost": 10.0}),
        _evaluation(3, {"gain": 3.0}, {}),
    ]
    old = ParetoPromoter(old_policies, definition_versions=["gain.v1", "cost.v1"]).compute_front(
        rows
    )
    new_policies = [
        old_policies[1].model_copy(update={"primary_metric": "cost-renamed"}),
        old_policies[0].model_copy(update={"primary_metric": "gain-renamed"}),
    ]
    renamed_rows = [
        row.model_copy(
            update={
                "selection_metrics": {"gain-renamed": row.selection_metrics["gain"]},
                "holdout_metrics": {"cost-renamed": row.holdout_metrics["cost"]}
                if "cost" in row.holdout_metrics
                else {},
            }
        )
        for row in rows
    ]
    new = ParetoPromoter(new_policies, definition_versions=["cost.v1", "gain.v1"]).compute_front(
        renamed_rows
    )
    assert old.coordinate_schema is not None and new.coordinate_schema is not None
    by_metric = {c.metric: c.coordinate_id for c in new.coordinate_schema.coordinates}
    reindex = {
        c.coordinate_id: by_metric[c.metric + "-renamed"] for c in old.coordinate_schema.coordinates
    }
    return old, new, reindex


def test_paired_policy_name_value_and_reference_reindex_preserves_cas_geometry_and_omissions(
    tmp_path: Path,
) -> None:
    old, new, reindex = _reindexed_fixture()
    expected = _union(((4.0, -7.0), (2.0, -5.0)), (0.0, -10.0))
    assert expected == 16
    assert _union(((-7.0, 4.0), (-5.0, 2.0)), (-10.0, 0.0)) == expected
    old = _persist_and_reopen(tmp_path, old, ParetoFront, suffix="original")
    new = _persist_and_reopen(tmp_path, new, ParetoFront, suffix="reindexed")
    assert old.hypervolume == new.hypervolume == float(expected)
    assert {m.candidate_ref_id for m in old.members} == {m.candidate_ref_id for m in new.members}
    old_values = {m.candidate_ref_id: m.coordinate_values for m in old.members}
    for member in new.members:
        assert member.coordinate_values == {
            reindex[k]: v for k, v in old_values[member.candidate_ref_id].items()
        }
    assert new.coordinate_reference_point == {
        reindex[k]: v for k, v in old.coordinate_reference_point.items()
    }
    assert old.input_assessment is not None and new.input_assessment is not None
    assert old.input_assessment.status == new.input_assessment.status == "partial"
    assert old.input_assessment.input_count == new.input_assessment.input_count == 4
    assert old.input_assessment.assessed_count == new.input_assessment.assessed_count == 3
    left = old.input_assessment.unassessed_evaluations[0]
    right = new.input_assessment.unassessed_evaluations[0]
    assert left.input_index == right.input_index == 3
    assert left.candidate_ref_id == right.candidate_ref_id
    assert right.missing_coordinate_ids == [reindex[k] for k in left.missing_coordinate_ids]


@pytest.mark.parametrize("omission_field", ["missing_coordinate_ids", "non_finite_coordinate_ids"])
def test_stale_omission_coordinate_identity_cannot_survive_actual_cas_reader(
    tmp_path: Path, omission_field: str
) -> None:
    old, new, _ = _reindexed_fixture()
    assert old.input_assessment is not None
    payload = new.model_dump(mode="json")
    omission = payload["input_assessment"]["unassessed_evaluations"][0]
    old_id = old.input_assessment.unassessed_evaluations[0].missing_coordinate_ids[0]
    omission["missing_coordinate_ids"] = []
    omission["non_finite_coordinate_ids"] = []
    omission[omission_field] = [old_id]
    assert old_id not in {c["coordinate_id"] for c in payload["coordinate_schema"]["coordinates"]}
    with pytest.raises(ValueError):
        _persist_and_reopen(tmp_path, payload, ParetoFront, suffix="stale-omission")


@pytest.mark.parametrize("identity_field", ["unit", "definition_version"])
def test_unpaired_typed_identity_change_refuses_actual_cas_readback(
    tmp_path: Path, identity_field: str
) -> None:
    _, front, _ = _reindexed_fixture()
    payload = front.model_dump(mode="json")
    payload["coordinate_schema"]["coordinates"][0][identity_field] = "unpaired-change"
    with pytest.raises(ValueError):
        _persist_and_reopen(tmp_path, payload, ParetoFront, suffix="unpaired-identity")


def test_mo_actual_derived_reference_rejects_finite_input_span_overflow_before_assignment() -> None:
    torch = pytest.importorskip("torch", reason="UNRUN: optional real MO tensor backend required")
    pytest.importorskip("botorch", reason="UNRUN: optional real MO backend required")
    pytest.importorskip("gpytorch", reason="UNRUN: optional real MO backend required")
    from polisyos.scientist.methods.search.objective import OptimizationDirection
    from polisyos.scientist.methods.search.strategies.multi_objective import (
        MOBayesianOptimizer,
        MOConfig,
    )
    from polisyos.scientist.methods.search.strategies.space import SearchSpace
    from polisyos.scientist.methods.search.strategies.types import ParameterBounds

    # The exact final reference is representable. The existing float64
    # subtraction order overflows its intermediate span; that arithmetic
    # limitation must refuse rather than assign a non-finite reference.
    width = Fraction.from_float(1e308) - Fraction.from_float(-1e308)
    reference = Fraction.from_float(-1e308) - Fraction.from_float(0.1) * width
    assert width > 0 and reference < 0
    assert isfinite(float(reference))
    optimizer = MOBayesianOptimizer(
        SearchSpace([ParameterBounds("x", 0.0, 1.0)]),
        ["length", "duration"],
        [OptimizationDirection.MAXIMIZE, OptimizationDirection.MAXIMIZE],
        MOConfig(ref_point_offset=0.1),
    )
    if not optimizer._botorch_ready:
        pytest.skip("UNRUN: configured real MO optional backend unavailable")
    values = torch.tensor([[-1e308, -1e308], [1e308, 1e308]], dtype=torch.float64)
    assert torch.isfinite(values).all()
    assert optimizer._ref_point is None and optimizer._model is None
    with pytest.raises(ValueError, match="invalid_reference_point"):
        optimizer._update_ref_point(values)
    assert optimizer._ref_point is None and optimizer._model is None
