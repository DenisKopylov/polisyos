"""Stage B projection producer/consumer and fail-closed closure witnesses."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.nodes.builtins.planning.stage_b_projection import (
    StageBProjection,
    StageBProjectionRefusalError,
    load_stage_b_projection,
    persist_stage_b_projection,
    stage_b_projection,
)
from polisyos.scientist.orchestration.engine.child_output_closure import (
    ChildOutputClosureRefusalError,
    TypedChildOutputClosureResolver,
)


def test_producer_consumer_preserves_actual_payload_and_selected_input_profiles(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = store.put_json(
        {"id": "test candidate"},
        PutOptions(kind="test.candidate", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation = store.put_json(
        {"id": "test evaluation"},
        PutOptions(kind="test.evaluation", media_type="application/json"),
        return_selected_profile=True,
    )
    simulation = store.put_json(
        {"id": "test simulation"},
        PutOptions(kind="test.simulation", media_type="application/json"),
        return_selected_profile=True,
    )
    result = {
        "simulation_result_ref": simulation.model_dump(mode="json"),
        "candidate_ref": candidate.model_dump(mode="json"),
        "policy_evaluation_ref": evaluation.model_dump(mode="json"),
        "status": "ok",
        "objective_score_status": "available",
        "simulation_results": {"opaque": [1, {"x": "value"}]},
        "counterfactual_gate_summary": {"known": False},
    }
    ref = persist_stage_b_projection(store, result)
    loaded = load_stage_b_projection(store, ref)
    assert loaded.original_result() == result
    assert loaded.candidate_ref == candidate
    assert loaded.evaluation_ref == evaluation
    assert loaded.simulation_result_ref == simulation
    assert loaded.score_status == "available"
    edges = store.get_manifest(ref).inputs
    assert [(edge.role, str(edge.artifact_id), edge.manifest_profile_sha256) for edge in edges] == [
        ("candidate", str(candidate.artifact_id), candidate.manifest_profile_sha256),
        ("evaluation", str(evaluation.artifact_id), evaluation.manifest_profile_sha256),
        ("simulation_result", str(simulation.artifact_id), simulation.manifest_profile_sha256),
    ]
    result["simulation_results"]["opaque"].append("changed")
    assert loaded.original_result()["simulation_results"]["opaque"] == [1, {"x": "value"}]


def test_rejected_observation_does_not_fabricate_selected_sources(tmp_path: Path) -> None:
    result = {"status": "rejected", "objective_score_status": "not_established", "details": {}}
    projection = stage_b_projection(result)
    assert projection.original_result() == result
    assert projection.candidate_ref is None
    assert projection.evaluation_ref is None
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_stage_b_projection(store, result)
    fresh = load_stage_b_projection(FileSystemCAS(tmp_path / "cas"), ref)
    assert fresh.original_result() == result
    assert fresh.candidate_ref is None and fresh.evaluation_ref is None


def test_envelope_cannot_disagree_with_its_actual_score_status() -> None:
    with pytest.raises(ValidationError, match="stage_b_projection_score_status_mismatch"):
        StageBProjection.model_validate(
            {
                "candidate_ref": None,
                "evaluation_ref": None,
                "score_status": "available",
                "result": {"objective_score_status": "not_established"},
            }
        )


def test_profileless_explicit_reference_is_not_silently_promoted(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = store.put_json(
        {"candidate": True}, PutOptions(kind="test.candidate", media_type="application/json")
    )
    value = candidate.model_dump(mode="json")
    value.pop("manifest_profile_sha256", None)
    with pytest.raises(StageBProjectionRefusalError, match="stage_b_source_profile_required"):
        stage_b_projection({"candidate_ref": value})


def test_actual_opaque_payload_remains_a_closure_refusal(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    result = {"status": "rejected", "details": {"hidden_semantics": "not assumed absent"}}
    ref = persist_stage_b_projection(store, result)

    class OwnerFixture:
        def __getattr__(self, name):
            return getattr(store, name)

        def selected_source_ref(self, role):
            return None

        def is_previously_authorized(self, ref):
            return False

    resolver = TypedChildOutputClosureResolver(
        limits=CoreJsonReadLimits(
            max_bytes=100000, max_depth=50, max_elements=10000, max_manifest_bytes=100000
        )
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_schema_unsupported"):
        resolver.resolve(OwnerFixture(), ref)


def test_actual_candidate_producer_binds_model_ids_to_selected_inputs(tmp_path: Path) -> None:
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.planning.stage_b_projection import (
        persist_stage_b_candidate,
    )
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec

    store = FileSystemCAS(tmp_path / "cas")
    data = store.put_json(
        {"data": 1},
        PutOptions(kind="test.data", media_type="application/json"),
        return_selected_profile=True,
    )
    registry = store.put_json(
        {"registry": 1},
        PutOptions(kind="test.registry", media_type="application/json"),
        return_selected_profile=True,
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="candidate_problem", domain=ProblemDomain.SOCIAL),
        policy_spec=PolicySpec(policy_id="candidate_policy", interventions=[]),
        model_spec=ModelSpec(
            model_id="candidate_model",
            data_snapshot_ref=str(data.artifact_id),
            registry_bundle_ref=str(registry.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema(
        candidate_id="candidate_one",
        trinity_bundle=trinity,
        target_population=TargetPopulationSpec(
            population_id="all", description="Fixture population"
        ),
    )
    candidate_ref = persist_stage_b_candidate(
        store, candidate, {"data_snapshot_ref": data, "registry_bundle_ref": registry}
    )
    inputs = store.get_manifest(candidate_ref).inputs
    assert [(x.role, str(x.artifact_id), x.manifest_profile_sha256) for x in inputs] == [
        ("model_primary_data_snapshot", str(data.artifact_id), data.manifest_profile_sha256),
        ("model_primary_registry", str(registry.artifact_id), registry.manifest_profile_sha256),
        ("world_model_data_snapshot", str(data.artifact_id), data.manifest_profile_sha256),
        ("world_model_registry", str(registry.artifact_id), registry.manifest_profile_sha256),
    ]
    with pytest.raises(
        StageBProjectionRefusalError, match="stage_b_candidate_model_input_unresolved"
    ):
        persist_stage_b_candidate(store, candidate, {"registry_bundle_ref": registry})


def test_candidate_model_binding_refuses_ambiguous_profile_for_same_id(tmp_path: Path) -> None:
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.planning.stage_b_projection import (
        bind_candidate_model_inputs,
    )
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec

    store = FileSystemCAS(tmp_path / "cas")
    data = store.put_json(
        {"data": 1},
        PutOptions(kind="test.data", media_type="application/json"),
        return_selected_profile=True,
    )
    other_view = data.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    candidate = PolicyCandidateSchema(
        candidate_id="candidate_one",
        trinity_bundle=TrinityBundle(
            problem_frame=ProblemFrame(problem_id="candidate_problem", domain=ProblemDomain.SOCIAL),
            policy_spec=PolicySpec(policy_id="candidate_policy", interventions=[]),
            model_spec=ModelSpec(
                model_id="candidate_model", data_snapshot_ref=str(data.artifact_id)
            ),
        ),
        target_population=TargetPopulationSpec(
            population_id="all", description="Fixture population"
        ),
    )
    with pytest.raises(
        StageBProjectionRefusalError, match="stage_b_candidate_model_input_unresolved"
    ):
        bind_candidate_model_inputs(candidate, {"first": data, "second": other_view})
