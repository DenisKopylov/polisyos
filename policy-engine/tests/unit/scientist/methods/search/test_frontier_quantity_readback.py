"""Persisted registry quantity availability is independent of membership."""

from polisyos.scientist.methods.autotune.pareto import HypervolumeAssessment
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry, ParetoRegistrySnapshot


def test_registry_native_disk_reader_retains_quantity_unavailability(tmp_path):
    registry = ParetoRegistry(root=tmp_path)
    snapshot = ParetoRegistrySnapshot(
        loop_id="quantity",
        frontiers={"global_feasible": ["valid-front"]},
        hypervolume_by_view={"global_feasible": None},
        hypervolume_assessments={
            "global_feasible": HypervolumeAssessment(
                version="hypervolume-assessment.v2",
                status="unavailable",
                basis="not_established",
                reason="optional_backend_unavailable",
                profile="dominated_box_union.float64.maximize.v1",
            )
        },
    )
    path = tmp_path / "loops" / "quantity" / "pareto_registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(snapshot.model_dump_json())
    reopened = ParetoRegistry(root=tmp_path).get_snapshot("quantity")
    assert reopened.frontiers["global_feasible"] == ["valid-front"]
    assert reopened.hypervolume_by_view["global_feasible"] is None
    assert (
        reopened.hypervolume_assessments["global_feasible"].reason == "optional_backend_unavailable"
    )
    assert registry._frontier_hashes([], "global_feasible")[1] is None


def test_registry_computed_zero_stays_available_on_readback(tmp_path):
    snapshot = ParetoRegistrySnapshot(
        loop_id="zero",
        hypervolume_by_view={"global_feasible": 0.0},
        hypervolume_assessments={
            "global_feasible": HypervolumeAssessment(
                version="hypervolume-assessment.v2",
                status="available",
                basis="recomputed",
                profile="dominated_box_union.float64.maximize.v1",
                algorithm="exact_empty",
            )
        },
    )
    path = tmp_path / "loops" / "zero" / "pareto_registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(snapshot.model_dump_json())
    reopened = ParetoRegistry(root=tmp_path).get_snapshot("zero")
    assert reopened.hypervolume_by_view["global_feasible"] == 0.0
    assert reopened.hypervolume_assessments["global_feasible"].status == "available"
