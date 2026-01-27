from __future__ import annotations

import json
import time

from polisyos.scientist.orchestrator.run_timeline import RunTimeline, TimelineEventType


class TestRunTimeline:
    def test_record_event(self) -> None:
        timeline = RunTimeline(run_id="test_001")
        idx = timeline.record(TimelineEventType.PHASE_START, phase="FRAME", node_id="draft_ir")
        assert idx == 0
        assert len(timeline.events) == 1
        assert timeline.events[0].event_type == TimelineEventType.PHASE_START
        assert timeline.events[0].phase == "FRAME"
        assert timeline.events[0].node_id == "draft_ir"

    def test_phase_duration_calculation(self) -> None:
        timeline = RunTimeline(run_id="test_002")
        timeline.record(TimelineEventType.PHASE_START, phase="EXECUTE")
        time.sleep(0.02)
        timeline.record(TimelineEventType.PHASE_END, phase="EXECUTE")
        duration = timeline.get_phase_duration("EXECUTE")
        assert duration >= 10

    def test_to_artifact_json_serializable(self) -> None:
        timeline = RunTimeline(run_id="test_003")
        timeline.record_run_start()
        timeline.record(TimelineEventType.ARTIFACT_CREATED, phase="EXECUTE", artifact_ref="sim_001")
        timeline.record_run_end()

        artifact = timeline.to_artifact()
        serialized = json.dumps(artifact, default=str)
        assert serialized
        assert artifact["run_id"] == "test_003"
        assert artifact["event_count"] == 3
        assert "summary" in artifact

    def test_from_artifact_roundtrip(self) -> None:
        original = RunTimeline(run_id="test_004")
        original.record_run_start()
        original.record(TimelineEventType.NODE_ENTER, phase="FRAME", node_id="validate_ir")
        original.record(TimelineEventType.NODE_EXIT, phase="FRAME", node_id="validate_ir")
        original.record_run_end()

        artifact = original.to_artifact()
        reconstructed = RunTimeline.from_artifact(artifact)

        assert reconstructed.run_id == original.run_id
        assert len(reconstructed.events) == len(original.events)
        assert reconstructed.events[1].node_id == "validate_ir"

    def test_get_errors_filters_correctly(self) -> None:
        timeline = RunTimeline(run_id="test_005")
        timeline.record(TimelineEventType.NODE_ENTER, phase="EXECUTE", node_id="run_sim")
        timeline.record(
            TimelineEventType.ERROR,
            phase="EXECUTE",
            node_id="run_sim",
            details={"error": "OOM"},
        )
        timeline.record(TimelineEventType.NODE_EXIT, phase="EXECUTE", node_id="run_sim")

        errors = timeline.get_errors()
        assert len(errors) == 1
        assert errors[0].details["error"] == "OOM"

    def test_get_node_durations(self) -> None:
        timeline = RunTimeline(run_id="test_006")

        timeline.record(TimelineEventType.NODE_ENTER, phase="FRAME", node_id="validate_ir")
        time.sleep(0.01)
        timeline.record(TimelineEventType.NODE_EXIT, phase="FRAME", node_id="validate_ir")

        timeline.record(TimelineEventType.NODE_ENTER, phase="FRAME", node_id="validate_ir")
        time.sleep(0.01)
        timeline.record(TimelineEventType.NODE_EXIT, phase="FRAME", node_id="validate_ir")

        durations = timeline.get_node_durations()
        assert "validate_ir" in durations
        assert durations["validate_ir"] >= 10

