"""The feedback ledger follows actual map calls, not solver iteration rows."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    FeedbackConfig,
    FeedbackSolverConfig,
    FeedbackStateSnapshot,
    FeedbackVariableSpec,
)
from polisyos.foundry.feedback.config import prepare_feedback_config
from polisyos.foundry.feedback.fixed_point import (
    FeedbackMapEvaluationRecorder,
    MapEvaluation,
    solve_fixed_point,
)


def _prepared(*, compute_jacobian_diagnostics: bool = True):
    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="x",
                source_kind="state_path",
                source_ref="state.x",
                target_kind="state_path",
                target_ref="state.x",
                initial_value=0.0,
                lower_bound=-10.0,
                upper_bound=10.0,
                scale=1.0,
            )
        ],
        solver=FeedbackSolverConfig(
            mode="picard",
            homotopy_grid=[0.0, 1.0],
            damping_init=1.0,
            damping_min=1.0,
            max_iter=60,
            max_restarts=0,
            anderson_start=61,
            newton_start=61,
            stagnation_patience=61,
            compute_jacobian_diagnostics=compute_jacobian_diagnostics,
            store_alternative_fixed_points=False,
        ),
    )
    return prepare_feedback_config(
        config,
        initial_state=FeedbackStateSnapshot(
            variable_ids=["x"],
            values=[0.0],
            scales=[1.0],
            lower_bounds=[-10.0],
            upper_bounds=[10.0],
            weights=[1.0],
        ),
    )


def _base_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="foundry.state_snapshot",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "2" * 64,
    )


def test_recorder_counts_jacobian_callbacks_separately_from_solver_trace() -> None:
    prepared = _prepared()
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    callback_count = 0

    def evaluate(value: np.ndarray) -> MapEvaluation:
        nonlocal callback_count
        callback_count += 1
        return MapEvaluation(
            map_value=np.asarray([0.5 * value[0] + 1.0]),
            diagnostics={},
            graph_invocation_id=f"graph-invocation.{callback_count:06d}",
        )

    outcome = solve_fixed_point(
        prepared=prepared,
        evaluate_map=recorder.wrap(evaluate, phase="solver_map"),
    )

    assert outcome.converged
    assert outcome.final_residual_norm is not None
    contraction_bound = 0.5
    fixed_point_error_bound = outcome.final_residual_norm / (1.0 - contraction_bound)
    assert abs(float(outcome.solution[0]) - 2.0) <= fixed_point_error_bound
    assert callback_count == len(recorder.records)
    assert callback_count > len(outcome.trace)
    assert len({item.graph_invocation_id for item in recorder.records}) == callback_count
    assert all(item.base_state_ref == recorder.base_state_ref for item in recorder.records)
    assert all(item.phase == "solver_map" for item in recorder.records)
    assert [item.evaluation_id for item in recorder.records] == [
        f"feedback-map-evaluation.{index:06d}" for index in range(1, callback_count + 1)
    ]


def test_recorder_unifies_discovery_and_final_materialization_order() -> None:
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    invocation = 0

    def evaluate(value: np.ndarray) -> MapEvaluation:
        nonlocal invocation
        invocation += 1
        return MapEvaluation(
            map_value=value + 1.0,
            diagnostics={},
            graph_invocation_id=f"graph-invocation.{invocation:06d}",
        )

    recorder.wrap(evaluate, phase="solver_map")(np.asarray([1.0]))
    recorder.wrap(evaluate, phase="equilibrium_discovery")(np.asarray([2.0]))
    final = recorder.record_final_materialization(
        candidate_values=np.asarray([3.0]),
        mapped_values=np.asarray([3.0]),
        graph_invocation_id="graph-invocation.000003",
    )

    assert [item.phase for item in recorder.records] == [
        "solver_map",
        "equilibrium_discovery",
        "final_materialization",
    ]
    assert final.evaluation_id == "feedback-map-evaluation.000003"
    assert [item.graph_invocation_id for item in recorder.records] == [
        "graph-invocation.000001",
        "graph-invocation.000002",
        "graph-invocation.000003",
    ]


def test_recorder_preserves_failed_callback_without_changing_exception() -> None:
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    graph_invocation_id = "graph-invocation.000007"

    def fail(_: np.ndarray) -> MapEvaluation:
        raise ValueError("candidate map failed")

    with pytest.raises(ValueError, match="candidate map failed"):
        recorder.wrap(
            fail,
            execution_link_provider=lambda: graph_invocation_id,
        )(np.asarray([1.0]))

    (record,) = recorder.records
    assert record.outcome == "failed"
    assert record.failure_type == "builtins.ValueError"
    assert record.mapped_values is None
    assert record.graph_invocation_id == graph_invocation_id
    assert record.execution_link_status == "captured"


def test_recorder_preserves_keyboard_interrupt_when_link_and_ledger_fail(monkeypatch) -> None:
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    original_interrupt = KeyboardInterrupt("solver interrupted after callback work")

    def fail(_: np.ndarray) -> MapEvaluation:
        raise original_interrupt

    def fail_link() -> str | None:
        raise SystemExit("capture link unavailable")

    with pytest.raises(KeyboardInterrupt) as caught:
        recorder.wrap(fail, execution_link_provider=fail_link)(np.asarray([1.0]))

    assert caught.value is original_interrupt
    (record,) = recorder.records
    assert record.outcome == "failed"
    assert record.failure_type == "builtins.KeyboardInterrupt"
    assert record.graph_invocation_id is None
    assert record.execution_link_status == "not_established"
    assert any("invocation link unavailable" in note for note in original_interrupt.__notes__)

    second_interrupt = KeyboardInterrupt("ledger append also interrupted")

    def fail_again(_: np.ndarray) -> MapEvaluation:
        raise second_interrupt

    def fail_append(**_: object) -> None:
        raise SystemExit("ledger append unavailable")

    monkeypatch.setattr(recorder, "_append", fail_append)
    with pytest.raises(KeyboardInterrupt) as caught_again:
        recorder.wrap(fail_again)(np.asarray([2.0]))

    assert caught_again.value is second_interrupt
    assert any("failure ledger unavailable" in note for note in second_interrupt.__notes__)


def test_recorder_captures_post_callback_output_conversion_failure() -> None:
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    graph_invocation_id = "graph-invocation.000008"

    def return_unconvertible(_: np.ndarray) -> MapEvaluation:
        return MapEvaluation(
            map_value=np.asarray(["not-a-number"]),
            diagnostics={},
            graph_invocation_id=graph_invocation_id,
        )

    with pytest.raises((TypeError, ValueError)):
        recorder.wrap(return_unconvertible)(np.asarray([1.0]))

    (record,) = recorder.records
    assert record.outcome == "failed"
    assert record.graph_invocation_id == graph_invocation_id
    assert record.execution_link_status == "captured"
    assert record.failure_type in {"builtins.TypeError", "builtins.ValueError"}


def test_final_materialization_records_downstream_failure_and_preserves_exception() -> None:
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    graph_invocation_id = "graph-invocation.000009"
    failure = RuntimeError("state application failed after graph execution")

    def execute_then_fail() -> tuple[None, np.ndarray]:
        raise failure

    with pytest.raises(RuntimeError) as caught:
        recorder.run_final_materialization(
            candidate_values=np.asarray([2.0]),
            materialize=execute_then_fail,
            execution_link_provider=lambda: graph_invocation_id,
        )

    assert caught.value is failure
    (record,) = recorder.records
    assert record.phase == "final_materialization"
    assert record.outcome == "failed"
    assert record.failure_type == "builtins.RuntimeError"
    assert record.graph_invocation_id == graph_invocation_id
    assert record.execution_link_status == "captured"


def test_final_materialization_preserves_interrupt_when_failure_record_append_fails(
    monkeypatch,
) -> None:
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    original_interrupt = KeyboardInterrupt("final materialization interrupted")

    def fail_append(**_: object) -> None:
        raise SystemExit("final failure ledger unavailable")

    def fail_materialization() -> tuple[None, np.ndarray]:
        raise original_interrupt

    monkeypatch.setattr(recorder, "_append", fail_append)
    with pytest.raises(KeyboardInterrupt) as caught:
        recorder.run_final_materialization(
            candidate_values=np.asarray([2.0]),
            materialize=fail_materialization,
        )

    assert caught.value is original_interrupt
    assert recorder.records == ()
    assert any("failure ledger unavailable" in note for note in original_interrupt.__notes__)


def test_final_materialization_records_observed_vector_after_downstream_reads() -> None:
    recorder = FeedbackMapEvaluationRecorder(base_state_ref=_base_ref())
    result = recorder.run_final_materialization(
        candidate_values=np.asarray([2.0]),
        materialize=lambda: ("readback-complete", np.asarray([2.0 + 1.0e-8])),
        execution_link_provider=lambda: "graph-invocation.000010",
    )

    assert result == "readback-complete"
    (record,) = recorder.records
    assert record.phase == "final_materialization"
    assert record.candidate_values == (2.0,)
    assert record.mapped_values == pytest.approx((2.0 + 1.0e-8,))
    assert record.graph_invocation_id == "graph-invocation.000010"
    assert record.outcome == "completed"
