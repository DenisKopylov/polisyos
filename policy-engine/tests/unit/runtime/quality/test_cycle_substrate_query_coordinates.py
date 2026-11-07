"""Versioned context-job custody for explicit outcome query coordinates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


def _problem_with_query_coordinates(
    problem: object,
    *,
    conditioning_variables: tuple[str, ...],
    measurement_unit: str,
) -> Any:
    """Create the typed problem before the source-context owner is invoked."""
    from polisyos.runtime.quality.design_problem import DesignProblem

    outcome = problem.outcome_of_interest  # type: ignore[attr-defined]
    outcome_fields = {name: getattr(outcome, name) for name in type(outcome).model_fields}
    outcome_fields.update(
        {
            "conditioning_variables": conditioning_variables,
            "measurement_unit": measurement_unit,
        }
    )
    selected_outcome = type(outcome).model_validate(outcome_fields)
    problem_fields = {name: getattr(problem, name) for name in type(problem).model_fields}
    problem_fields["outcome_of_interest"] = selected_outcome
    return DesignProblem.model_validate(problem_fields)


def test_cycle_substrate_context_job_v6_roundtrips_coordinates_and_preserves_v5_wire(
    tmp_path: Path,
) -> None:
    """Persist explicit query coordinates through V6 while leaving legacy V5 exact."""
    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactReadOnlyUnavailableError,
        FileSystemCAS,
        load_core_json_artifact,
    )
    from polisyos.runtime.quality import cycle_substrate as cycle_substrate_owner
    from polisyos.runtime.quality.cycle_substrate import (
        CYCLE_SUBSTRATE_CONTEXT_JOB_V5_SCHEMA,
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextJobArtifactV5,
        CycleSubstrateContextJobArtifactV6,
        build_candidate_cycle_substrate_context,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
        cycle_substrate_context_job_content_hash,
        parse_cycle_substrate_context_job_artifact,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        _authenticated_fixture_scope,
        _FixtureCurrentJobOwner,
        build_candidate_cycle_substrate_route_inputs,
    )

    inputs = build_candidate_cycle_substrate_route_inputs(tmp_path / "route-inputs")
    problem = _problem_with_query_coordinates(
        inputs.problem,
        conditioning_variables=("education.prior_learning_outcomes",),
        measurement_unit="synthetic_score",
    )
    changed_problem = _problem_with_query_coordinates(
        inputs.problem,
        conditioning_variables=("education.school_quality",),
        measurement_unit="synthetic_score",
    )
    legacy_problem = inputs.problem
    assert problem.outcome_of_interest.query_coordinate_status == "candidate_proposed_unverified"
    assert (
        inputs.world_model_record.slot_binding(problem.outcome_of_interest.target_variable).unit
        is None
    )
    assert problem.outcome_of_interest.measurement_unit == "synthetic_score"
    assert problem.outcome_of_interest.conditioning_variables == (
        "education.prior_learning_outcomes",
    )
    assert cycle_job_design_problem_ref(problem) != cycle_job_design_problem_ref(changed_problem)
    assert cycle_job_profile_selection_ref(problem) != cycle_job_profile_selection_ref(
        changed_problem
    )

    context = build_candidate_cycle_substrate_context(
        inputs.root,
        problem=problem,
        world_model_record=inputs.world_model_record,
        substrate_registry=inputs.substrate_registry,
    )
    legacy_context = build_candidate_cycle_substrate_context(
        inputs.root,
        problem=legacy_problem,
        world_model_record=inputs.world_model_record,
        substrate_registry=inputs.substrate_registry,
    )

    tenant_id = "tenant-cycle-substrate-query-coordinates"
    cell_id = "cell-cycle-substrate-query-coordinates"
    job_id = "job-cycle-substrate-query-coordinates"
    run_id = "run-cycle-substrate-query-coordinates"
    cas_root = tmp_path / "context-job-cas"
    store = FileSystemCAS(
        cas_root,
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    current_job_owner = _FixtureCurrentJobOwner(job_id, run_id)
    owner = CycleSubstrateContextArtifactOwner(
        store=store,
        control_store=current_job_owner,
    )
    with _authenticated_fixture_scope(tenant_id=tenant_id, cell_id=cell_id):
        selected_ref = owner.persist_for_current_job(
            context,
            problem=problem,
            repo_root=inputs.root,
            return_selected_profile=True,
        )
        legacy_ref = owner.persist_for_current_job(
            legacy_context,
            problem=legacy_problem,
            repo_root=inputs.root,
            return_selected_profile=True,
        )
        current = owner.resolve_for_current_job(
            selected_ref,
            problem=problem,
            repo_root=inputs.root,
        )
        selected_payload = load_core_json_artifact(store, selected_ref)
        legacy_payload = load_core_json_artifact(store, legacy_ref)
        selected_bytes = store.get_bytes(selected_ref)
        legacy_bytes = store.get_bytes(legacy_ref)
        selected_manifest = store.get_manifest(selected_ref)

    fresh_store = FileSystemCAS.open_existing_read_only(cas_root)
    fresh_owner = CycleSubstrateContextArtifactOwner(
        store=fresh_store,
        control_store=current_job_owner,
    )
    with _authenticated_fixture_scope(tenant_id=tenant_id, cell_id=cell_id):
        fresh = fresh_owner.resolve_for_current_job(
            selected_ref,
            problem=problem,
            repo_root=inputs.root,
        )

    assert type(current) is CycleSubstrateContextJobArtifactV6
    assert type(fresh) is CycleSubstrateContextJobArtifactV6
    assert current == fresh
    assert current.schema_version == "policyos.runtime.cycle_substrate_context_job_artifact.v6"
    assert current.status == "candidate_limited"
    assert current.profile_admission_status == "not_established"
    assert current.s8_status == "blocked"
    assert current.problem.outcome_of_interest.conditioning_variables == (
        "education.prior_learning_outcomes",
    )
    assert current.problem.outcome_of_interest.measurement_unit == "synthetic_score"
    assert current.problem.outcome_of_interest.query_coordinate_status == (
        "candidate_proposed_unverified"
    )
    assert (
        current.context.world_model_record.slot_binding(
            problem.outcome_of_interest.target_variable
        ).unit
        is None
    )
    assert selected_payload["schema_version"] == current.schema_version
    assert selected_payload["problem"]["outcome_of_interest"]["conditioning_variables"] == [
        "education.prior_learning_outcomes"
    ]
    assert selected_payload["problem"]["outcome_of_interest"]["measurement_unit"] == (
        "synthetic_score"
    )
    assert selected_payload["problem"]["outcome_of_interest"]["query_coordinate_status"] == (
        "candidate_proposed_unverified"
    )
    assert (
        cycle_substrate_context_job_content_hash(selected_payload)
        == selected_payload["content_hash"]
    )
    assert selected_bytes == cycle_substrate_owner.canon.to_canonical_bytes(
        selected_payload,
        cycle_substrate_owner._CONTEXT_JOB_CANON,
    )
    assert selected_manifest.artifact_schema is not None
    assert selected_manifest.artifact_schema.version == "6.0"
    assert selected_ref.manifest_profile_sha256 is not None

    assert type(parse_cycle_substrate_context_job_artifact(legacy_payload)) is (
        CycleSubstrateContextJobArtifactV5
    )
    assert legacy_payload["schema_version"] == CYCLE_SUBSTRATE_CONTEXT_JOB_V5_SCHEMA
    assert set(legacy_payload["problem"]["outcome_of_interest"]) == {
        "target_variable",
        "metric_id",
        "estimand",
        "direction",
    }
    assert (
        cycle_substrate_context_job_content_hash(legacy_payload) == legacy_payload["content_hash"]
    )
    assert legacy_bytes == cycle_substrate_owner.canon.to_canonical_bytes(
        legacy_payload,
        cycle_substrate_owner._CONTEXT_JOB_CANON,
    )
    assert b'"conditioning_variables"' not in legacy_bytes
    assert b'"measurement_unit"' not in legacy_bytes
    assert b'"query_coordinate_status"' not in legacy_bytes

    # A V5-labelled wire record cannot opt into the new query coordinate fields.
    v5_with_coordinates = {
        **legacy_payload,
        "problem": {
            **legacy_payload["problem"],
            "outcome_of_interest": {
                **legacy_payload["problem"]["outcome_of_interest"],
                "conditioning_variables": ["education.prior_learning_outcomes"],
                "measurement_unit": "synthetic_score",
                "query_coordinate_status": "candidate_proposed_unverified",
            },
        },
    }
    with pytest.raises(
        cycle_substrate_owner.CycleSubstrateContextOwnerError,
        match="cycle_substrate_context_job_query_coordinates_require_v6",
    ):
        cycle_substrate_context_job_content_hash(v5_with_coordinates)
    # Independently exercise the frozen V5 model validator with the original
    # V5 hash. Its exact schema still rejects query-coordinate fields.
    with pytest.raises(ValueError):
        parse_cycle_substrate_context_job_artifact(v5_with_coordinates)

    missing_selected_ref = selected_ref.model_copy(
        update={"artifact_id": ArtifactID("sha256:" + "f" * 64)}
    )
    with _authenticated_fixture_scope(tenant_id=tenant_id, cell_id=cell_id):
        # A never-written selected ID has no ownership stripe lock. The fresh
        # read-only store must report that typed availability boundary instead
        # of creating a lock or treating it as an admitted context artifact.
        with pytest.raises(
            ArtifactReadOnlyUnavailableError,
            match="required_lock_file_unavailable",
        ):
            fresh_owner.resolve_for_current_job(
                missing_selected_ref,
                problem=problem,
                repo_root=inputs.root,
            )
        with pytest.raises(cycle_substrate_owner.CycleSubstrateContextOwnerError) as crossbound:
            fresh_owner.resolve_for_current_job(
                selected_ref,
                problem=changed_problem,
                repo_root=inputs.root,
            )
        assert crossbound.value.code == "cycle_substrate_context_job_binding_mismatch"


@pytest.mark.parametrize("wmr_version", ["v1", "v2"])
def test_v6_plain_context_preserves_supported_world_schemas_without_source_role(
    tmp_path: Path,
    wmr_version: str,
) -> None:
    """The new codec preserves plain candidate contexts without minting source admission."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.cycle_substrate import (
        CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA,
        CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA,
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextJobArtifactV6,
        cycle_job_design_problem_ref,
        is_candidate_source_profile_context_job_artifact,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import (
        _authenticated_tenant_scope,
        _cycle_context,
        _fixture_world_with_persisted_substrate_registry,
        _hash,
        _qualified_v3_design_problem,
        _registry,
        _TestCurrentJobExecutionOwner,
        _world_record,
        _world_record_with_selected_views,
    )

    legacy_problem = _qualified_v3_design_problem()
    problem = _problem_with_query_coordinates(
        legacy_problem,
        conditioning_variables=("education.prior_learning_outcomes",),
        measurement_unit="synthetic_score",
    )
    registry = _registry(problem.domain)
    world = _world_record(
        problem.domain,
        registry,
        region_or_jurisdiction=problem.jurisdiction_time.region,
        policy_slot_ids=("education.teaching_method", "education.learning_outcomes"),
    )
    tenant_id, cell_id = "tenant-v6-plain-codec", "cell-v6-plain-codec"
    job_id, run_id = "job-v6-plain-codec", "run-v6-plain-codec"
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=True, ownership_requires_scope=True)
    job_owner = _TestCurrentJobExecutionOwner(job_id, run_id)
    with _authenticated_tenant_scope(tenant_id=tenant_id, cell_id=cell_id):
        if wmr_version == "v2":
            registry_ref, world = _fixture_world_with_persisted_substrate_registry(
                store, registry, world
            )
            world = _world_record_with_selected_views(
                world,
                substrate_registry_artifact_ref=registry_ref,
                selected_profile=_hash("plain-v6-selected-view"),
            )
        context = _cycle_context(
            registry=registry,
            world_model_record=world,
            design_problem_ref=cycle_job_design_problem_ref(problem),
        )
        legacy_context = _cycle_context(
            registry=registry,
            world_model_record=world,
            design_problem_ref=cycle_job_design_problem_ref(legacy_problem),
        )
        owner = CycleSubstrateContextArtifactOwner(store=store, control_store=job_owner)
        selected_ref = owner.persist_for_current_job(
            context, problem=problem, return_selected_profile=True
        )
        legacy_ref = owner.persist_for_current_job(
            legacy_context, problem=legacy_problem, return_selected_profile=True
        )
        legacy = owner.resolve_for_current_job(legacy_ref, problem=legacy_problem)
        fresh_store = FileSystemCAS(
            cas_root, ownership_enforced=True, ownership_requires_scope=True
        )
        fresh_owner = CycleSubstrateContextArtifactOwner(store=fresh_store, control_store=job_owner)
        fresh = fresh_owner.resolve_for_current_job(selected_ref, problem=problem)
        historical = fresh_owner.resolve_historical_job_artifact(
            selected_ref,
            problem=problem,
            expected_job_id=job_id,
            expected_run_id=run_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
    assert type(fresh) is CycleSubstrateContextJobArtifactV6
    assert historical == fresh
    assert fresh.problem == problem
    assert fresh.context.source_profile is None
    assert fresh.context.world_model_record == world
    assert not is_candidate_source_profile_context_job_artifact(fresh)
    assert fresh.profile_admission_status == "not_established"
    assert fresh.s8_status == "blocked"
    assert fresh.problem.outcome_of_interest.query_coordinate_status == (
        "candidate_proposed_unverified"
    )
    assert legacy.schema_version == (
        CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
        if wmr_version == "v1"
        else CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA
    )
    assert legacy.context.world_model_record == world
    assert legacy.problem.outcome_of_interest.conditioning_variables == ()
    assert legacy.problem.outcome_of_interest.measurement_unit is None
