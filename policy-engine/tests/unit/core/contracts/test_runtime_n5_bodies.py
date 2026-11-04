"""Candidate and generic N5 result bodies keep distinct typed purposes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.runtime import (
    RunCandidateSimulationN5Observation,
    RunCandidateSimulationN5ResultBody,
    RunGenericCycleSimulationN5Observation,
    RunGenericCycleSimulationN5ResultBody,
)

_CANDIDATE_SCHEMA = "policyos.runtime.run_candidate_simulation_n5_result_body.v1"
_GENERIC_SCHEMA = "policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1"
_WORLD_HASH = "sha256:" + "a" * 64
_PROFILE_HASH = "sha256:" + "b" * 64
_REQUEST_HASH = "sha256:" + "c" * 64
_ATOM_IDS = ("atom-configured",)
_OUTCOMES = ("government.balance",)


def _artifact_ref(
    kind: str,
    fill: str,
    *,
    manifest_profile_sha256: str | None = _PROFILE_HASH,
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + fill * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=manifest_profile_sha256,
    )


def _result_body_payload(*, candidate: bool) -> dict[str, object]:
    result_ref = _artifact_ref("polisyos.runtime.joint_simulation_result", "d")
    return {
        "schema_version": _CANDIDATE_SCHEMA if candidate else _GENERIC_SCHEMA,
        "artifact_ref": result_ref,
        "artifact_schema_name": "policyos.runtime.n5.joint_simulation_result",
        "artifact_schema_version": "1.0.0",
        "result_schema_version": "policyos.runtime.joint_simulation_horizon.v1",
        "selected_manifest_profile_sha256": _PROFILE_HASH,
        "world_model_record_ref": "world-model:configured-test",
        "world_model_record_content_hash": _WORLD_HASH,
        "atom_ids": _ATOM_IDS,
        "selected_outcomes": _OUTCOMES,
        "horizon": {
            "start": 0,
            "end": 1,
            "step": 1,
            "valid_time_role": "policy_horizon",
            "transaction_time_role": "recorded_at",
            "scenario_branch_policy": "selected_branch_only",
        },
        "trajectories": (
            {
                "run_level": "joint",
                "atom_ids": _ATOM_IDS,
                "points": (
                    {
                        "step": 0,
                        "outcomes": {"government.balance": 0.25},
                        "effects": {"government.balance": 0.0},
                    },
                    {
                        "step": 1,
                        "outcomes": {"government.balance": 0.30},
                        "effects": {"government.balance": 0.05},
                    },
                ),
            },
        ),
        "uncertainty_kind": "K_sim",
        "authority_purpose": (
            "candidate_scenario_n5_only" if candidate else "cycle_input_candidate_only"
        ),
        "candidate_status": "candidate_unverified",
        "currentness_status": "not_established",
        "publication_authority": False,
    }


def _generic_observation(body: object) -> RunGenericCycleSimulationN5Observation:
    return RunGenericCycleSimulationN5Observation.model_validate(
        {
            "node_ref": "design-problem://configured-test",
            "design_problem_ref": _WORLD_HASH,
            "cycle_index": 0,
            "candidate_id": "configured-candidate",
            "status": "joint_simulated",
            "simulation_result_ref": _artifact_ref("polisyos.runtime.joint_simulation_result", "d"),
            "simulation_result_body": body,
            "simulation_result_body_status": "resolved",
            "n4_source_ref": _artifact_ref("runtime.generation_source_handoff", "e"),
            "context_job_ref": _artifact_ref("runtime.quality.cycle_substrate_context_job", "f"),
            "profile_ref": _artifact_ref("runtime.quality.generic_cycle_simulation_profile", "1"),
            "n5_input_ref": _artifact_ref("runtime.quality.generic_cycle_simulation_n5_input", "2"),
            "n5_execution_ref": _artifact_ref(
                "runtime.quality.generic_cycle_simulation_n5_execution", "3"
            ),
            "n5_request_binding_status": "resolved",
            "n5_request_content_hash": _REQUEST_HASH,
            "profile_selection_ref": _REQUEST_HASH,
            "atom_ids": _ATOM_IDS,
            "selected_outcomes": _OUTCOMES,
            "world_model_record_content_hash": _WORLD_HASH,
            "n8_status": "value_pending_n8",
            "n8_lineage_status": "not_established",
            "n8_limitation_code": "generic_n8_candidate_value_not_established",
        }
    )


def _candidate_observation(
    body: object,
    *,
    lineage_status: str = "resolved",
    context_manifest_profile_sha256: str | None = _PROFILE_HASH,
) -> RunCandidateSimulationN5Observation:
    return RunCandidateSimulationN5Observation.model_validate(
        {
            "node_ref": "design-problem://configured-test",
            "design_problem_ref": _WORLD_HASH,
            "cycle_index": 0,
            "candidate_id": "configured-candidate",
            "atom_ids": _ATOM_IDS,
            "selected_outcomes": _OUTCOMES,
            "status": "joint_simulated",
            "simulation_result_ref": _artifact_ref("polisyos.runtime.joint_simulation_result", "d"),
            "n5_execution_ref": _artifact_ref(
                "runtime.quality.candidate_simulation_execution", "4"
            ),
            "result_body_status": "resolved",
            "result_body": body,
            "world_model_record_content_hash": _WORLD_HASH,
            "n4_source_ref": _artifact_ref("runtime.quality.n4_candidate_scenario_source", "5"),
            "context_job_ref": _artifact_ref(
                "runtime.quality.cycle_substrate_context_job",
                "f",
                manifest_profile_sha256=context_manifest_profile_sha256,
            ),
            "n5_input_ref": _artifact_ref("runtime.quality.candidate_simulation_n5_input", "6"),
            "profile_config_ref": "configured-candidate-profile",
            "profile_selection_ref": _REQUEST_HASH,
            "lineage_status": lineage_status,
            "lineage_limitation_code": (
                None if lineage_status == "resolved" else "candidate_lineage_not_established"
            ),
        }
    )


def test_n5_body_purposes_are_sibling_types_at_observation_boundaries() -> None:
    """Concrete body instances cannot cross the generic/candidate observation seam."""
    generic_body = RunGenericCycleSimulationN5ResultBody.model_validate(
        _result_body_payload(candidate=False)
    )
    candidate_body = RunCandidateSimulationN5ResultBody.model_validate(
        _result_body_payload(candidate=True)
    )

    assert type(generic_body) is RunGenericCycleSimulationN5ResultBody
    assert generic_body.schema_version == _GENERIC_SCHEMA
    assert generic_body.authority_purpose == "cycle_input_candidate_only"
    assert type(candidate_body) is RunCandidateSimulationN5ResultBody
    assert candidate_body.schema_version == _CANDIDATE_SCHEMA
    assert candidate_body.authority_purpose == "candidate_scenario_n5_only"

    assert _generic_observation(generic_body).simulation_result_body is generic_body
    assert _candidate_observation(candidate_body).result_body is candidate_body
    with pytest.raises(ValidationError):
        _generic_observation(candidate_body)
    with pytest.raises(ValidationError):
        _candidate_observation(generic_body)


@pytest.mark.parametrize(
    ("candidate_observation", "field", "value"),
    [
        (False, "schema_version", _GENERIC_SCHEMA),
        (False, "authority_purpose", "cycle_input_candidate_only"),
        (True, "schema_version", _CANDIDATE_SCHEMA),
        (True, "authority_purpose", "candidate_scenario_n5_only"),
    ],
)
def test_n5_observation_rejects_cross_purpose_json_literals(
    candidate_observation: bool,
    field: str,
    value: str,
) -> None:
    """JSON-shaped bodies must independently match the consuming purpose and schema."""
    wrong_body = _result_body_payload(candidate=not candidate_observation)
    wrong_body[field] = value
    with pytest.raises(ValidationError):
        if candidate_observation:
            _candidate_observation(wrong_body)
        else:
            _generic_observation(wrong_body)


def test_candidate_n5_body_requires_all_refs_but_not_resolved_child_lineage() -> None:
    """A body needs its full source/input scope while preserving declared uncertainty."""
    candidate_body = RunCandidateSimulationN5ResultBody.model_validate(
        _result_body_payload(candidate=True)
    )
    observation = _candidate_observation(candidate_body, lineage_status="not_established")
    assert observation.result_body is candidate_body
    assert observation.lineage_status == "not_established"
    assert observation.lineage_limitation_code == "candidate_lineage_not_established"
    context_without_selected_profile = _candidate_observation(
        candidate_body,
        lineage_status="not_established",
        context_manifest_profile_sha256=None,
    )
    assert context_without_selected_profile.context_job_ref is not None
    assert context_without_selected_profile.context_job_ref.manifest_profile_sha256 is None

    unlinked_payload = observation.model_dump(mode="python")
    for field in (
        "n4_source_ref",
        "context_job_ref",
        "n5_input_ref",
        "profile_config_ref",
        "profile_selection_ref",
        "lineage_status",
        "lineage_limitation_code",
    ):
        unlinked_payload.pop(field)
    with pytest.raises(
        ValidationError,
        match="run_n5_candidate_result_body_lineage_binding_missing",
    ):
        RunCandidateSimulationN5Observation.model_validate(unlinked_payload)


@pytest.mark.parametrize(
    "selected_ref_field",
    ["n4_source_ref", "n5_input_ref"],
)
def test_candidate_n5_body_requires_selected_source_and_input_views(
    selected_ref_field: str,
) -> None:
    """A candidate result body cannot omit its selected N4 or N5 input manifest view."""
    candidate_body = RunCandidateSimulationN5ResultBody.model_validate(
        _result_body_payload(candidate=True)
    )
    payload = _candidate_observation(candidate_body).model_dump(mode="python")
    selected_ref = payload[selected_ref_field]
    assert isinstance(selected_ref, dict)
    selected_ref["manifest_profile_sha256"] = None

    with pytest.raises(
        ValidationError,
        match="run_n5_candidate_result_body_selected_view_missing",
    ):
        RunCandidateSimulationN5Observation.model_validate(payload)


def test_generic_n5_result_body_schema_and_purpose_remain_stable() -> None:
    """The generic body retains its established schema and authority purpose."""
    generic = RunGenericCycleSimulationN5ResultBody.model_validate(
        _result_body_payload(candidate=False)
    )
    serialized = generic.model_dump(mode="json")

    assert serialized["schema_version"] == _GENERIC_SCHEMA
    assert serialized["authority_purpose"] == "cycle_input_candidate_only"
    expected_wire_fields = (
        "schema_version",
        "artifact_ref",
        "artifact_schema_name",
        "artifact_schema_version",
        "result_schema_version",
        "selected_manifest_profile_sha256",
        "world_model_record_ref",
        "world_model_record_content_hash",
        "atom_ids",
        "selected_outcomes",
        "horizon",
        "trajectories",
        "uncertainty_kind",
        "authority_purpose",
        "candidate_status",
        "currentness_status",
        "publication_authority",
    )
    assert tuple(serialized) == expected_wire_fields
    assert tuple(RunGenericCycleSimulationN5ResultBody.model_json_schema()["properties"]) == (
        expected_wire_fields
    )


def test_configured_units_require_the_exact_declared_outcome_denominator() -> None:
    """The display contract neither invents units nor permits a partial unit map."""
    legacy = RunCandidateSimulationN5ResultBody.model_validate(_result_body_payload(candidate=True))
    assert legacy.unit_provenance == "not_established"
    assert legacy.outcome_units == {}
    payload = {
        **_result_body_payload(candidate=True),
        "outcome_units": {"government.balance": "declared_currency_unit"},
        "unit_provenance": "declared_candidate_model",
        "model_declaration_ref": _artifact_ref(
            "runtime.quality.candidate_simulation_model_declaration", "e"
        ),
    }
    body = RunCandidateSimulationN5ResultBody.model_validate(payload)
    assert body.outcome_units == {"government.balance": "declared_currency_unit"}
    assert body.publication_authority is False
    for changes in (
        {"outcome_units": {}},
        {"outcome_units": {"foreign.outcome": "declared_currency_unit"}},
        {"outcome_units": {"government.balance": " "}},
        {"model_declaration_ref": None},
        {"unit_provenance": "not_established"},
    ):
        with pytest.raises(ValidationError):
            RunCandidateSimulationN5ResultBody.model_validate({**payload, **changes})


@pytest.mark.parametrize("candidate", [False, True])
def test_v5_body_keeps_its_exact_selected_artifact_epoch(candidate: bool) -> None:
    payload = {
        **_result_body_payload(candidate=candidate),
        "artifact_schema_version": "5.0.0",
        "result_schema_version": "policyos.runtime.joint_simulation_horizon.v5",
    }
    record_type = (
        RunCandidateSimulationN5ResultBody if candidate else RunGenericCycleSimulationN5ResultBody
    )
    body = record_type.model_validate(payload)
    assert body.result_schema_version == "policyos.runtime.joint_simulation_horizon.v5"
    with pytest.raises(ValidationError, match="manifest_binding_invalid"):
        record_type.model_validate({**payload, "artifact_schema_version": "4.0.0"})


def _authored_joint_projection_payload() -> dict[str, object]:
    """A display contract fixture; the served route verifies actual owner bytes."""
    derived_ids = ("atom_8888888888888888", "atom_9999999999999999")
    intervention_ids = ("industrial_retention_tax_credit", "procurement_distress_backstop")
    result_ref = _artifact_ref("polisyos.runtime.joint_simulation_result", "d")
    return {
        "node_ref": "joint-parent",
        "design_problem_ref": _WORLD_HASH,
        "atom_ids": intervention_ids,
        "selected_outcomes": _OUTCOMES,
        "executed_steps": (0,),
        "replication_seeds": (41, 42),
        "status": "joint_simulated",
        "simulation_result_ref": result_ref,
        "n5_interaction_evidence": {
            "schema_version": "policyos.runtime.joint_simulation_horizon.v5",
            "numeric_interaction": "unsupported",
            "numeric_interaction_basis": "finite_checked_model_point_estimate_only",
            "interaction_sampling_status": "estimated",
            "interaction_terms": (
                {
                    "atom_ids": intervention_ids,
                    "outcome": _OUTCOMES[0],
                    "by_step": {0: 0.0},
                    "replication_sampling_by_step": {
                        0: {
                            "status": "estimated",
                            "replicate_count": 2,
                            "seeds": (41, 42),
                            "samples": ({"seed": 41, "value": 0.0}, {"seed": 42, "value": 0.0}),
                            "mean": 0.0,
                            "standard_error": 0.0,
                        }
                    },
                },
            ),
            "checked_interaction_orders": (1, 2),
        },
        "n8_numeric_interaction": "unsupported",
        "n8_numeric_interaction_basis": "finite_checked_model_point_estimate_only",
        "n8_interaction_sampling_status": "estimated",
        "n8_status": "value_conditional",
        "n8_candidate_value_ref": str(result_ref.artifact_id),
        "n8_candidate_decision_grade": "low",
        "n8_authority_blockers": (
            "n5_execution_request_provenance_not_established",
            "authored_candidate_coupling_not_established",
            "child_to_parent_refinement_rule_not_established",
            "parent_joint_coupling_evidence_not_established",
            "interaction_numeric_classification_unsupported",
        ),
        "n8_joint_scope_status": "not_established",
        "n8_joint_scope_limitation_code": "parent_joint_coupling_evidence_not_established",
        "n8_candidate_joint_selection_status": "resolved",
        "n8_candidate_joint_selection_content_hash": _REQUEST_HASH,
        "n8_candidate_parent_atom_ids": ("atom_4444444444444444", "atom_5555555555555555"),
        "n8_candidate_parent_atom_content_hashes": ("sha256:" + "4" * 64, "sha256:" + "5" * 64),
        "n8_candidate_derived_atom_ids": derived_ids,
        "n8_candidate_derived_atom_content_hashes": ("sha256:" + "8" * 64, "sha256:" + "9" * 64),
        "n8_candidate_parent_intervention_ids": intervention_ids,
        "n8_candidate_parent_child_refs": ("child-a", "child-b"),
        "n8_candidate_member_basis": "authored_materialized_n4_source_members",
        "n8_source_candidate_relationship": "alternatives",
        "n8_selected_member_relationship": "joint_components",
        "n8_policy_composition_status": "authored_candidate",
        "n8_policy_composition_limitation_code": "authored_candidate_coupling_not_established",
        "n8_child_to_parent_refinement_status": "not_established",
        "n8_child_to_parent_refinement_limitation_code": "child_to_parent_refinement_rule_not_established",
        "n8_authored_joint_relation_ref": _artifact_ref(
            "runtime.quality.recursive_authored_joint_relation", "6"
        ),
        "n8_authored_joint_request_payload_ref": _artifact_ref(
            "runtime.control_job_payload.natural_language_run", "7"
        ),
        "n8_authored_joint_intent_digest": _REQUEST_HASH,
    }


def test_authored_joint_projection_distinguishes_source_and_materialized_members() -> None:
    payload = _authored_joint_projection_payload()
    observation = RunCandidateSimulationN5Observation.model_validate(payload)
    assert observation.n8_source_candidate_relationship == "alternatives"
    assert observation.n8_selected_member_relationship == "joint_components"
    assert observation.n8_candidate_parent_atom_ids != observation.n8_candidate_derived_atom_ids
    assert observation.n8_candidate_parent_intervention_ids == observation.atom_ids
    assert observation.n8_candidate_derived_atom_ids != observation.atom_ids
    assert observation.n8_status == "value_conditional"
    assert observation.n8_joint_scope_status == "not_established"
    assert observation.currentness_status == "not_established"
    assert (
        RunCandidateSimulationN5Observation.model_validate_json(observation.model_dump_json())
        == observation
    )


@pytest.mark.parametrize(
    "change",
    [
        {"n8_authored_joint_relation_ref": None},
        {"n8_authored_joint_request_payload_ref": None},
        {"n8_authored_joint_intent_digest": None},
        {"n8_candidate_derived_atom_ids": ("atom_aaaaaaaaaaaaaaaa", "atom_9999999999999999")},
        {"n8_candidate_derived_atom_content_hashes": ("sha256:" + "a" * 64, "sha256:" + "9" * 64)},
        {"n8_candidate_derived_atom_ids": ("atom_9999999999999999", "atom_8888888888888888")},
        {"n8_candidate_derived_atom_ids": ("atom_8888888888888888", "atom_8888888888888888")},
        {
            "n8_candidate_parent_intervention_ids": (
                "procurement_distress_backstop",
                "industrial_retention_tax_credit",
            )
        },
        {
            "n8_candidate_derived_atom_ids": ("atom_4444444444444444", "atom_9999999999999999"),
            "n8_candidate_derived_atom_content_hashes": (
                "sha256:" + "4" * 64,
                "sha256:" + "9" * 64,
            ),
        },
        {"n8_policy_composition_status": "not_established"},
        {"n8_joint_scope_status": "resolved"},
    ],
)
def test_authored_joint_projection_refuses_lost_binding_or_claimed_coupling(
    change: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        RunCandidateSimulationN5Observation.model_validate(
            {**_authored_joint_projection_payload(), **change}
        )


def test_recursive_capacity_checkpoint_requires_typed_frontier_and_hides_legacy_extension() -> None:
    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import RunRecursiveCycleCheckpoint

    row = {
        "schema_version": "policyos.runtime.recursive_cycle_checkpoint.v3",
        "pending_frontier": ["pending-child"],
        "completed_design_refs": ["completed-child"],
        "capacity_stop_parent_node_ref": "root",
        "capacity_pending_child_node_ref": "pending-child",
        "capacity_pending_child_index": 1,
        "capacity_source_content_hash": "sha256:" + "a" * 64,
        "capacity_limitation_code": "physical_need_not_established",
    }
    checkpoint = RunRecursiveCycleCheckpoint.model_validate(row)
    assert checkpoint.root_n9_status == "not_run"
    assert checkpoint.publication_authority is False
    for change in (
        {"capacity_pending_child_node_ref": "foreign-child"},
        {"capacity_source_content_hash": None},
        {"capacity_limitation_code": None},
        {"publication_authority": True},
        {"budget_stop_node_ref": "old-budget-stop"},
    ):
        with pytest.raises(ValidationError):
            RunRecursiveCycleCheckpoint.model_validate({**row, **change})
    legacy = RunRecursiveCycleCheckpoint(budget_stop_node_ref="old-budget-stop")
    assert "capacity_source_content_hash" not in legacy.model_dump(mode="json")
