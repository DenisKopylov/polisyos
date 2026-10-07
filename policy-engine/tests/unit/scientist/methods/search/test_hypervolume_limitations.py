"""Finite membership and typed unavailable indicators through actual disk readers."""

import json
import math

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.methods.autotune.pareto import ParetoFront, ParetoPromoter
from polisyos.scientist.methods.search.contracts import ParetoBasisScope
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry, ParetoView
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)


def vector(identity, value):
    return PolicyEvaluationVector(
        candidate_id=identity,
        primary={
            key: ObjectiveChannelValue(
                name=key,
                kind=ObjectiveKind.PRIMARY,
                value=value,
                direction=ObjectiveDirection.MAXIMIZE,
            )
            for key in ("policy_value", "employment")
        },
        feasible=True,
    )


def test_extreme_finite_front_roundtrip_retains_membership_without_fake_indicator():
    promoter = ParetoPromoter(
        [
            PromotionPolicy(
                loop_id="fixture", primary_metric=key, direction=MetricDirection.MAXIMIZE
            )
            for key in ("policy_value", "employment")
        ]
    )
    evaluations = [
        BenchmarkEvaluation(
            loop_id="fixture",
            suite_id="fixture",
            candidate_ref=ArtifactRef(
                artifact_id=f"sha256:{i:064x}", kind="fixture", media_type="application/json"
            ),
            holdout_metrics={"policy_value": v, "employment": v},
        )
        for i, v in enumerate((-1e308, 1e308), start=1)
    ]
    front = promoter.compute_front(evaluations)
    assert [m.candidate_ref_id for m in front.members] == [
        str(evaluations[1].candidate_ref.artifact_id)
    ]
    assert front.input_assessment.status == "complete"
    assert all(math.isfinite(v) for m in front.members for v in m.coordinate_values.values())
    assert front.hypervolume is None
    assert front.hypervolume_assessment.status == "unavailable"
    assert front.hypervolume_assessment.reason == "non_finite_derived_hypervolume"
    assert promoter.is_dominated(evaluations[0], front)
    reopened = ParetoFront.model_validate_json(front.model_dump_json())
    assert reopened == front
    for fake in (0, float("inf")):
        payload = front.model_dump(mode="json")
        payload["hypervolume"] = fake
        with pytest.raises(ValueError):
            ParetoFront.model_validate(payload)


def test_registry_actual_disk_catalog_and_voi_consumers_preserve_limitation(tmp_path):
    registry = ParetoRegistry(tmp_path / "registry")
    basis = ParetoBasisScope(
        scope="declared", coordinate_ids=["policy_value", "employment"], basis_ref="fixture:axes.v1"
    )
    for i, value in enumerate((-1e308, 1e308), start=1):
        registry.update(
            "fixture",
            candidate_hash=f"sha256:{i:064x}",
            evaluation=vector(str(i), value),
            objective_basis_by_view={"global_feasible": basis},
        )
    reopened = ParetoRegistry(tmp_path / "registry")
    snapshot = reopened.get_snapshot("fixture")
    view = "global_feasible"
    assert snapshot.hypervolume_by_view[view] is None
    assert snapshot.hypervolume_assessments[view].reason == "non_finite_derived_hypervolume"
    assert snapshot.project_view(ParetoView.GLOBAL_FEASIBLE).ranked_frontier_hashes == (
        f"sha256:{2:064x}",
    )
    assert reopened.to_voi_snapshot("fixture").frontier_candidate_hashes == frozenset(
        {f"sha256:{2:064x}"}
    )
    catalog = reopened.publish_transfer_surface("fixture")
    assert catalog.hypervolume_by_view[view] is None
    assert catalog.hypervolume_assessments[view].reason == "catalog_union_not_recomputed"
    catalog_path = next((tmp_path / "registry" / "catalog").glob("*/*/*/pareto_registry.json"))
    assert json.loads(catalog_path.read_text())["hypervolume_by_view"][view] is None
    snapshot_path = tmp_path / "registry" / "loops" / "fixture" / "pareto_registry.json"
    payload = json.loads(snapshot_path.read_text())
    payload["schema_version"] = "3.0"
    snapshot_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        reopened.get_snapshot("fixture")


def test_observed_axes_without_configured_basis_cannot_create_rank(tmp_path):
    registry = ParetoRegistry(tmp_path / "registry")
    registry.update("fixture", candidate_hash=f"sha256:{1:064x}", evaluation=vector("1", 1))
    projection = registry.get_snapshot("fixture").project_view(ParetoView.GLOBAL_FEASIBLE)
    assert projection.assessment.basis_scope.scope == "observed_axis_union"
    assert projection.assessment.status == "basis_limited"
    assert projection.ranked_frontier_hashes == ()
    assert projection.unassessed_candidate_hashes == (f"sha256:{1:064x}",)


@pytest.mark.parametrize("version", ["3.0", "0.0", None, True, 1.0])
def test_actual_disk_reader_refuses_unsupported_schema_profile(tmp_path, version):
    path = tmp_path / "loops" / "fixture" / "pareto_registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": version,
                "loop_id": "fixture",
                "hypervolume_by_view": {"global_feasible": 0.0},
            }
        )
    )
    with pytest.raises(ValueError):
        ParetoRegistry(tmp_path).get_snapshot("fixture")


@pytest.mark.parametrize("version", ["1.0", "2.0"])
def test_known_historical_finite_schema_reader_remains_supported(tmp_path, version):
    path = tmp_path / "loops" / "fixture" / "pareto_registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": version,
                "loop_id": "fixture",
                "hypervolume_by_view": {"global_feasible": 0.0},
            }
        )
    )
    snapshot = ParetoRegistry(tmp_path).get_snapshot("fixture")
    assert snapshot.schema_version == version
    assert snapshot.project_view(ParetoView.GLOBAL_FEASIBLE).ranked_frontier_hashes == ()
