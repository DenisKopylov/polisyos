"""Native request equality is not inferred from Python float/model equality."""

from __future__ import annotations

import struct
from dataclasses import fields

import pytest
from pydantic.fields import FieldInfo

import polisyos.runtime.quality.candidate_simulation as candidate_simulation
from polisyos.runtime.quality.candidate_simulation import (
    CandidateN5RequestProjectionV2,
    CandidateN5RequestValues,
    CandidateScenarioN5Config,
    prepare_candidate_n5_request_projection_v2,
    prepare_candidate_n5_request_values,
)
from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy


def _config(zero: float) -> CandidateScenarioN5Config:
    return CandidateScenarioN5Config(
        budget_ref="budget://native-request-test",
        horizon=HorizonSpec(start=0, end=2),
        baseline_state={"target": zero, "outcome": 91.0},
        comparator_refs=("comparator://declared",),
        seed=7,
        replications=2,
    )


def _full_projection_config(
    *,
    budget_ref: str = "budget://projection-a",
    replications: int = 3,
    comparator_refs: tuple[str, ...] = ("evidence://comparator-a",),
) -> CandidateScenarioN5Config:
    return CandidateScenarioN5Config(
        budget_ref=budget_ref,
        horizon=HorizonSpec(
            start=2,
            end=8,
            step=2,
            valid_time_role="fiscal-year",
            transaction_time_role="admission-time",
            scenario_branch_policy="recompute_each_step",
        ),
        baseline_state={"target": -0.0, "outcome": 91.0},
        comparator_refs=comparator_refs,
        seed=17,
        replications=replications,
        invocation_quota_policy=BudgetInvocationQuotaPolicy(
            allocation_id="projection-allocation-7-1",
            total_units=7,
            protected_units=1,
        ),
        invocation_purpose="diagnostic",
    )


def test_native_request_preparation_covers_actual_source_fields_and_value_bits() -> None:
    config = _config(-0.0)
    prepared = prepare_candidate_n5_request_values(config)
    assert {field.name for field in fields(prepared)} == set(type(config).model_fields)
    assert set(dict(prepared.horizon)) == set(type(config.horizon).model_fields)
    assert prepared.horizon_spec == config.horizon
    for name, value in config.baseline_state.items():
        assert dict(prepared.baseline_state)[name] == struct.pack("!d", value)
        assert struct.pack("!d", prepared.baseline_values()[name]) == struct.pack("!d", value)
    for name in type(config).model_fields:
        if name not in {"horizon", "baseline_state"}:
            assert getattr(prepared, name) == getattr(config, name)
    positive = _config(0.0)
    assert config == positive  # cheap proxy's divergent boundary
    assert prepared != prepare_candidate_n5_request_values(positive)
    assert struct.pack("!d", prepared.baseline_values()["target"]) != struct.pack("!d", 0.0)
    assert isinstance(prepared, CandidateN5RequestValues)


def test_new_unclassified_request_field_cannot_silently_disappear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(0.0)
    changed = dict(CandidateScenarioN5Config.model_fields)
    changed["new_required_semantic_input"] = FieldInfo(annotation=str)
    with monkeypatch.context() as patch:
        patch.setattr(CandidateScenarioN5Config, "__pydantic_fields__", changed)
        with pytest.raises(ValueError, match="candidate_n5_request_schema_not_supported"):
            prepare_candidate_n5_request_values(config)


def test_v2_projection_separates_numerical_values_from_budget_and_output_labels() -> None:
    config = _full_projection_config()
    projection = prepare_candidate_n5_request_projection_v2(
        config,
        world_model_record_ref="world-model://selected-a",
        reservation_identities=("reservation-a",),
    )
    budget_only_change = CandidateScenarioN5Config.model_validate(
        config.model_dump(mode="python") | {"budget_ref": "budget://projection-b"}
    )
    budget_projection = prepare_candidate_n5_request_projection_v2(
        budget_only_change,
        world_model_record_ref="world-model://selected-a",
        reservation_identities=("reservation-a",),
    )
    assert budget_projection.numerical == projection.numerical
    assert budget_projection.operational != projection.operational
    assert budget_projection.output_labels == projection.output_labels

    replication_change = _full_projection_config(replications=5)
    replication_projection = prepare_candidate_n5_request_projection_v2(
        replication_change,
        world_model_record_ref="world-model://selected-a",
        reservation_identities=("reservation-a",),
    )
    assert replication_projection.numerical != projection.numerical
    assert replication_projection.operational == projection.operational
    assert replication_projection.numerical.replications == 5
    assert (
        dict(projection.numerical.baseline_state_ieee754_hex)["target"]
        == struct.pack("!d", -0.0).hex()
    )

    label_change = _full_projection_config(comparator_refs=("evidence://comparator-b",))
    label_projection = prepare_candidate_n5_request_projection_v2(
        label_change,
        world_model_record_ref="world-model://selected-b",
        reservation_identities=("reservation-a",),
    )
    assert label_projection.numerical == projection.numerical
    assert label_projection.operational == projection.operational
    assert label_projection.output_labels.world_model_record_ref == "world-model://selected-b"
    assert label_projection.output_labels.comparator_evidence_refs == ("evidence://comparator-b",)

    roles = {row.field_name: row.role for row in projection.field_roles}
    assert len(roles) == len(projection.field_roles)
    assert set(roles) == set(type(config).model_fields)
    assert roles == {
        "schema_version": "numerical",
        "engine_kind": "numerical",
        "budget_ref": "operational",
        "horizon": "numerical",
        "baseline_state": "numerical",
        "comparator_refs": "output_label",
        "seed": "numerical",
        "replications": "numerical",
        "invocation_quota_policy": "operational",
        "invocation_purpose": "operational",
    }
    assert isinstance(projection, CandidateN5RequestProjectionV2)


def test_v2_projection_refuses_incomplete_or_overlapping_role_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _full_projection_config()
    original_roles = candidate_simulation._CANDIDATE_N5_REQUEST_FIELD_ROLES_V2

    with monkeypatch.context() as patch:
        patch.setattr(
            candidate_simulation,
            "_CANDIDATE_N5_REQUEST_FIELD_ROLES_V2",
            original_roles[:-1],
        )
        with pytest.raises(
            ValueError,
            match="candidate_n5_request_field_role_census_mismatch",
        ):
            prepare_candidate_n5_request_projection_v2(config)

    with monkeypatch.context() as patch:
        patch.setattr(
            candidate_simulation,
            "_CANDIDATE_N5_REQUEST_FIELD_ROLES_V2",
            (*original_roles, ("budget_ref", "numerical")),
        )
        with pytest.raises(
            ValueError,
            match="candidate_n5_request_field_role_overlap",
        ):
            prepare_candidate_n5_request_projection_v2(config)


def test_v2_projection_refuses_new_source_field_without_declared_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _full_projection_config()
    changed = dict(CandidateScenarioN5Config.model_fields)
    changed["new_algorithmic_stop_count"] = FieldInfo(annotation=int)
    with monkeypatch.context() as patch:
        patch.setattr(CandidateScenarioN5Config, "__pydantic_fields__", changed)
        with pytest.raises(
            ValueError,
            match="candidate_n5_request_field_role_census_mismatch",
        ):
            prepare_candidate_n5_request_projection_v2(config)
