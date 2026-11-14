"""Versioned fixed-point trace contracts preserve legacy wires and call identity."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    FeedbackMapEvaluationRecord,
    FeedbackTrace,
    FeedbackTraceRef,
)


def _ref(index: int, *, kind: str = "foundry.state_snapshot") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{index:064x}",
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=f"sha256:{index:064x}",
    )


def _evaluation(
    index: int,
    *,
    base_state_ref: ArtifactRef | None = None,
    phase: str = "solver_map",
    graph_invocation_id: str | None = None,
) -> FeedbackMapEvaluationRecord:
    return FeedbackMapEvaluationRecord(
        evaluation_id=f"feedback-map-evaluation.{index:06d}",
        phase=phase,
        candidate_values=(float(index),),
        mapped_values=(float(index + 1),),
        base_state_ref=base_state_ref,
        graph_invocation_id=graph_invocation_id,
        execution_link_status=(
            "captured" if graph_invocation_id is not None else "not_established"
        ),
    )


def test_feedback_trace_v1_wire_omits_new_optional_fields() -> None:
    trace = FeedbackTrace(schema_version="1.0", records=[], notes=[])

    assert trace.model_dump(mode="json") == {
        "schema_version": "1.0",
        "records": [],
        "notes": [],
    }
    assert FeedbackTrace.model_validate(trace.model_dump(mode="json")) == trace


def test_feedback_trace_v1_refuses_explicit_map_ledger() -> None:
    with pytest.raises(ValueError, match="feedback_trace_v1_cannot_carry_map_evaluations"):
        FeedbackTrace.model_validate(
            {"schema_version": "1.0", "records": [], "map_evaluations": []}
        )


def test_feedback_trace_v1_1_keeps_actual_map_calls_and_one_base() -> None:
    base = _ref(1)
    trace = FeedbackTrace(
        schema_version="1.1",
        evaluation_scope="complete",
        map_evaluations=(
            _evaluation(1, base_state_ref=base, graph_invocation_id="graph-invocation.000001"),
            _evaluation(2, base_state_ref=base, graph_invocation_id="graph-invocation.000002"),
            _evaluation(
                3,
                base_state_ref=base,
                phase="final_materialization",
                graph_invocation_id="graph-invocation.000003",
            ),
        ),
    )

    assert len(trace.map_evaluations or ()) == 3
    assert trace.map_evaluations[-1].phase == "final_materialization"
    assert trace.model_dump(mode="json")["schema_version"] == "1.1"


def test_feedback_trace_rejects_duplicate_call_ids_and_mixed_bases() -> None:
    with pytest.raises(ValueError, match="feedback_trace_duplicate_graph_invocation_id"):
        FeedbackTrace(
            schema_version="1.1",
            evaluation_scope="complete",
            map_evaluations=(
                _evaluation(1, graph_invocation_id="graph-invocation.000001"),
                _evaluation(2, graph_invocation_id="graph-invocation.000001"),
            ),
        )

    with pytest.raises(ValueError, match="feedback_trace_map_evaluations_mixed_base_state"):
        FeedbackTrace(
            schema_version="1.1",
            evaluation_scope="complete",
            map_evaluations=(
                _evaluation(1, base_state_ref=_ref(1)),
                _evaluation(2, base_state_ref=_ref(2)),
            ),
        )


def test_feedback_discovery_ledger_requires_explicit_solver_prefix() -> None:
    evaluation = _evaluation(1, phase="equilibrium_discovery")
    with pytest.raises(
        ValueError,
        match="feedback_trace_complete_discovery_requires_solver_prefix_ref",
    ):
        FeedbackTrace(
            schema_version="1.1",
            evaluation_scope="complete",
            map_evaluations=(evaluation,),
        )

    trace = FeedbackTrace(
        schema_version="1.1",
        evaluation_scope="complete",
        map_evaluations=(evaluation,),
        solver_prefix_trace_ref=FeedbackTraceRef.model_validate(
            _ref(9, kind="foundry.feedback_trace").model_dump()
        ),
    )
    assert trace.solver_prefix_trace_ref is not None
