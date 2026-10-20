from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

import polisyos.core.contracts.runtime as runtime_contracts
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import RunGenericCycleSimulationN6CycleHistoryEntry
from polisyos.pdc._impl.gy_waist import SearchTerminalKind
from polisyos.pdc._impl.layer2_design_search import RefinementDecisionKind, SearchIteration
from polisyos.runtime.quality.generation_cycle import (
    GroundingStatus,
    LoopNextAction,
    TerminalStatus,
    ValuePortObservation,
    ValuePortStatus,
)


def test_served_n6_status_types_cover_the_complete_producer_denominator() -> None:
    assert (
        RunGenericCycleSimulationN6CycleHistoryEntry
        is runtime_contracts.RunGenericCycleSimulationN6CycleHistoryEntry
    )
    assert set(get_args(runtime_contracts.RunN6CycleSearchTerminalKind)) == {
        member.value for member in SearchTerminalKind
    }
    assert set(get_args(runtime_contracts.RunN6CycleRefinementDecision)) == set(
        get_args(RefinementDecisionKind)
    )
    assert set(get_args(runtime_contracts.RunN6CycleSearchIterationStatus)) == set(
        get_args(SearchIteration.model_fields["status"].annotation)
    )
    assert set(get_args(runtime_contracts.RunN6CycleGroundingStatus)) == set(
        get_args(GroundingStatus)
    )
    assert set(get_args(runtime_contracts.RunN6CycleValueStatus)) == set(get_args(ValuePortStatus))
    source_decision_grade = get_args(
        get_args(ValuePortObservation.model_fields["decision_grade"].annotation)[0]
    )
    assert set(get_args(runtime_contracts.RunN6CycleValueDecisionGrade)) == set(
        source_decision_grade
    )
    assert set(get_args(runtime_contracts.RunN6CycleVoiAction)) == set(get_args(LoopNextAction))
    assert set(get_args(runtime_contracts.RunN6CycleRunTerminalStatus)) == set(
        get_args(TerminalStatus)
    )


def test_removing_n6_history_rows_while_resolved_marker_remains_is_rejected() -> None:
    source_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.compiled_recursive_generation_cycle",
        media_type="application/json",
    )
    with pytest.raises(
        ValidationError,
        match="run_generic_projection_n6_history_resolved_without_rows",
    ):
        runtime_contracts.RunGenericCycleSimulationProjection(
            schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v3",
            run_id="controlled-removal",
            artifact_status="resolved",
            source_ref=source_ref,
            source_content_hash="sha256:" + "b" * 64,
            child_profile_status="not_established",
            child_profile_limitation_code="controlled-child-profile-limitation",
            n6_cycle_history_status="resolved",
            n6_cycle_history=(),
        )


def test_credal_v2_projection_keeps_its_existing_schema_without_n6_extension() -> None:
    compiled_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.compiled_recursive_generation_cycle",
        media_type="application/json",
    )
    attempt_ref = ArtifactRef(
        artifact_id="sha256:" + "b" * 64,
        kind="runtime.quality.candidate_credal_source_attempt",
        media_type="application/json",
    )
    projection = runtime_contracts.RunGenericCycleSimulationProjection(
        schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v2",
        run_id="credal-v2-compatibility",
        artifact_status="resolved",
        source_ref=compiled_ref,
        source_content_hash="sha256:" + "c" * 64,
        credal_source_attempt_ref=attempt_ref,
        credal_source_status="not_established",
        credal_source_limitation_code="candidate_source_authority_not_established",
        child_profile_status="not_established",
        child_profile_limitation_code="generic_n4_source_generation_not_complete",
        n5_limitation_code="generic_n4_source_generation_not_complete",
        limitation_code="candidate_source_authority_not_established",
    )
    assert (
        projection.schema_version == "policyos.runtime.run_generic_cycle_simulation_projection.v2"
    )
    assert projection.n6_cycle_history_status is None
    assert projection.n6_cycle_history == ()
