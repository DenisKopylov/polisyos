"""Quantity range and paired axis identity, through actual persisted readers."""

import math
from fractions import Fraction

import pytest

from polisyos.core.artifacts import FileSystemCAS, SchemaInfo
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
    ParetoFront,
    ParetoPromoter,
    compute_hypervolume_assessed,
)
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoRegistry,
    ParetoRegistrySnapshot,
)


@pytest.mark.parametrize("dimensions", [2, 3, 4])
def test_positive_box_below_float64_range_is_unavailable(dimensions):
    if dimensions > 2:
        pytest.importorskip("torch", reason="UNRUN: actual supported partitioning backend")
        pytest.importorskip("botorch", reason="UNRUN: actual supported partitioning backend")
    point = (1e-200,) * dimensions
    exact = math.prod(Fraction.from_float(value) for value in point)
    assert exact > 0 and float(exact) == 0.0
    result = compute_hypervolume_assessed([point], (0.0,) * dimensions)
    assert result.value is None
    assert result.assessment.status == "unavailable"
    assert result.assessment.basis == "not_established"
    assert result.assessment.reason == "nonzero_derived_hypervolume_underflow"


@pytest.mark.parametrize("dimensions", [1, 2, 3, 4])
def test_boundary_zero_and_representable_tiny_quantity_remain_distinct(dimensions):
    if dimensions > 2:
        pytest.importorskip("torch", reason="UNRUN: actual supported partitioning backend")
        pytest.importorskip("botorch", reason="UNRUN: actual supported partitioning backend")
    reference = (0.0,) * dimensions
    zero = compute_hypervolume_assessed([(0.0,) + (1.0,) * (dimensions - 1)], reference)
    assert zero.value == 0.0 and zero.assessment.status == "available"
    tiny = compute_hypervolume_assessed([(1e-200,) + (1.0,) * (dimensions - 1)], reference)
    assert tiny.value == 1e-200 and tiny.assessment.status == "available"


def _persist_front(store, front):
    ref = store.put_json(
        front,
        ArtifactWriteOptions(
            kind="scientist.autotune.pareto_front",
            media_type="application/json",
            schema=SchemaInfo(name="ParetoFront", version="2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return ref


def test_computed_underflow_retains_members_and_availability_after_native_readback(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    policies = [
        PromotionPolicy(loop_id="tiny", primary_metric=name, direction=MetricDirection.MINIMIZE)
        for name in ("a", "b")
    ]
    promoter = ParetoPromoter(policies)
    evaluations = [
        BenchmarkEvaluation(
            loop_id="tiny",
            suite_id="conditional-numeric-input",
            candidate_ref=store.put_json(
                {"candidate": index},
                ArtifactWriteOptions(kind="synthetic.candidate", media_type="application/json"),
            ),
            holdout_metrics={"a": value, "b": value},
            promotable=True,
        )
        for index, value in enumerate((1e-200, 2e-200))
    ]
    front = promoter.compute_front(evaluations)
    assert front.size == 1 and front.input_assessment.assessed_count == 2
    assert front.hypervolume is None
    assert front.hypervolume_assessment.reason == "nonzero_derived_hypervolume_underflow"
    ref = _persist_front(store, front)
    restored = load_model_artifact(FileSystemCAS(tmp_path / "cas"), ref, ParetoFront)
    assert restored == front
    assert promoter.is_dominated(evaluations[1], restored)
    registry = ParetoRegistry(root=tmp_path / "registry")
    snapshot = ParetoRegistrySnapshot(
        loop_id="tiny",
        frontiers={"global_feasible": [front.members[0].candidate_ref_id]},
        hypervolume_by_view={"global_feasible": front.hypervolume},
        hypervolume_assessments={"global_feasible": front.hypervolume_assessment},
    )
    registry._write_snapshot("tiny", snapshot)
    reopened = ParetoRegistry(root=tmp_path / "registry").get_snapshot("tiny")
    assert reopened.frontiers == snapshot.frontiers
    assert reopened.hypervolume_by_view["global_feasible"] is None
    assert reopened.hypervolume_assessments["global_feasible"] == front.hypervolume_assessment


def test_paired_coordinate_reindex_preserves_persisted_quantity_and_dominance(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    refs = [
        store.put_json(
            {"candidate": index},
            ArtifactWriteOptions(kind="synthetic.candidate", media_type="application/json"),
        )
        for index in range(3)
    ]
    evaluations = [
        BenchmarkEvaluation(
            loop_id="paired-axes",
            suite_id="conditional-numeric-input",
            candidate_ref=ref,
            selection_metrics={"yield": gain},
            holdout_metrics={"cost": cost},
            promotable=True,
        )
        for ref, (gain, cost) in zip(refs, [(3.0, 1.0), (1.0, 3.0), (2.0, 2.0)], strict=True)
    ]
    policies = [
        PromotionPolicy(
            loop_id="paired-axes",
            primary_metric="yield",
            unit="tonnes",
            direction=MetricDirection.MAXIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
        ),
        PromotionPolicy(
            loop_id="paired-axes",
            primary_metric="cost",
            unit="currency",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.HOLDOUT,
        ),
    ]
    original = ParetoPromoter(policies, definition_versions=["yield.v1", "cost.v2"])
    reindexed = ParetoPromoter(policies[::-1], definition_versions=["cost.v2", "yield.v1"])
    left_ref = _persist_front(store, original.compute_front(evaluations))
    right_ref = _persist_front(store, reindexed.compute_front(evaluations))
    reopened = FileSystemCAS(tmp_path / "cas")
    left = load_model_artifact(reopened, left_ref, ParetoFront)
    right = load_model_artifact(reopened, right_ref, ParetoFront)
    assert left_ref.artifact_id != right_ref.artifact_id
    assert [c.coordinate_id for c in left.coordinate_schema.coordinates] == [
        c.coordinate_id for c in right.coordinate_schema.coordinates
    ][::-1]
    assert [member.candidate_ref_id for member in left.members] == [
        member.candidate_ref_id for member in right.members
    ]
    assert [member.coordinate_values for member in left.members] == [
        member.coordinate_values for member in right.members
    ]
    assert left.coordinate_reference_point == right.coordinate_reference_point
    assert left.hypervolume == right.hypervolume
    assert left.hypervolume_assessment == right.hypervolume_assessment
    for evaluation in evaluations:
        assert original.is_dominated(evaluation, right) == reindexed.is_dominated(evaluation, left)
    stale = ParetoPromoter(policies[::-1], definition_versions=["yield.v1", "cost.v2"])
    with pytest.raises(ValueError, match="basis differs"):
        stale.is_dominated(evaluations[0], right)
    malformed = right.model_dump(mode="json")
    malformed["coordinate_schema"]["coordinates"][0]["metric"] = "yield"
    bad_ref = _persist_front(store, malformed)
    with pytest.raises(ValueError, match="coordinate_id"):
        load_model_artifact(FileSystemCAS(tmp_path / "cas"), bad_ref, ParetoFront)


def _omission_front(store, omission_field, schema_status):
    """Produce a real partial or wholly unassessed typed coordinate artifact."""
    policies = [
        PromotionPolicy(loop_id="omissions", primary_metric=name, unit="metres")
        for name in ("a", "b")
    ]
    promoter = ParetoPromoter(policies, definition_versions=["a.v1", "b.v1"])
    rows = [
        BenchmarkEvaluation(
            loop_id="omissions",
            suite_id="conditional-numeric-input",
            candidate_ref=store.put_json(
                {"candidate": index},
                ArtifactWriteOptions(kind="synthetic.candidate", media_type="application/json"),
            ),
            holdout_metrics={"a": 1.0, "b": 1.0} if index == 0 else {"a": 2.0},
        )
        for index in range(2)
    ]
    if omission_field == "non_finite_coordinate_ids":
        # Deliberate post-validation mutable-input stress, not successful
        # typed producer admission of a non-finite metric.
        rows[1].holdout_metrics["b"] = float("nan")
    selected = rows if schema_status == "complete" else rows[1:]
    front = promoter.compute_front(selected)
    assert front.coordinate_schema.status == schema_status
    assert front.input_assessment.status == (
        "partial" if schema_status == "complete" else "no_usable_inputs"
    )
    stale = ParetoPromoter(
        [policy.model_copy(update={"unit": "seconds"}) for policy in policies],
        definition_versions=["a.v1", "b.v1"],
    )
    return front, stale.compute_front([]).coordinate_schema.coordinates[1].coordinate_id


@pytest.mark.parametrize("omission_field", ["missing_coordinate_ids", "non_finite_coordinate_ids"])
@pytest.mark.parametrize("schema_status", ["complete", "incomplete"])
@pytest.mark.parametrize("corruption", ["stale", "duplicate"])
def test_omission_coordinate_ids_bind_at_actual_cas_readback(
    tmp_path, omission_field, schema_status, corruption
):
    store = FileSystemCAS(tmp_path / "cas")
    front, stale_id = _omission_front(store, omission_field, schema_status)
    ref = _persist_front(store, front)
    restored = load_model_artifact(FileSystemCAS(tmp_path / "cas"), ref, ParetoFront)
    assert restored == front
    payload = restored.model_dump(mode="json")
    omission = payload["input_assessment"]["unassessed_evaluations"][0]
    current_ids = omission[omission_field]
    assert len(current_ids) == 1
    assert stale_id not in {
        coordinate["coordinate_id"] for coordinate in payload["coordinate_schema"]["coordinates"]
    }
    omission[omission_field] = [stale_id] if corruption == "stale" else current_ids * 2
    bad_ref = _persist_front(store, payload)
    with pytest.raises(ValueError, match="omission coordinates"):
        load_model_artifact(FileSystemCAS(tmp_path / "cas"), bad_ref, ParetoFront)


@pytest.mark.parametrize("schema_status", ["complete", "incomplete"])
@pytest.mark.parametrize("unbound_schema", [None, "legacy_limited"])
def test_omission_coordinate_ids_require_a_bound_schema(tmp_path, schema_status, unbound_schema):
    store = FileSystemCAS(tmp_path / "cas")
    front, _ = _omission_front(store, "missing_coordinate_ids", schema_status)
    good_ref = _persist_front(store, front)
    restored = load_model_artifact(FileSystemCAS(tmp_path / "cas"), good_ref, ParetoFront)
    assert restored == front
    payload = restored.model_dump(mode="json")
    payload["coordinate_schema"] = (
        None if unbound_schema is None else {"status": "legacy_limited", "coordinates": []}
    )
    bad_ref = _persist_front(store, payload)
    with pytest.raises(ValueError, match="omission coordinates require"):
        load_model_artifact(FileSystemCAS(tmp_path / "cas"), bad_ref, ParetoFront)
