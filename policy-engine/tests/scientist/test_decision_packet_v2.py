from __future__ import annotations

from datetime import datetime, timezone

from polisyos.scientist.orchestrator.decision_packet import DecisionPacket, build_decision_packet
from polisyos.scientist.orchestrator.decision_card import DecisionCard
from polisyos.scientist.orchestrator.run_record import GeneratorInfo, RunRecord
from polisyos.scientist.orchestrator.run_timeline import RunTimeline, TimelineEventType


def _make_run_record(run_id: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        parent_run_id=None,
        seed=0,
        backend="cpu",
        python_version="3.x",
        platform="test",
        generator=GeneratorInfo(name="tests", version="0.0.0"),
        library_versions={},
        flags={},
    )


class TestDecisionPacketV2:
    def test_build_packet_includes_timeline(self) -> None:
        state = {
            "run_id": "int_test_001",
            "ir": None,
            "simulation_results": {"gdp_change": 0.01},
            "feedback": {"verdict": "APPROVE", "issues": []},
            "audit_trail": [],
            "validation_trace": None,
        }
        run_record = _make_run_record("int_test_001")

        timeline = RunTimeline(run_id="int_test_001")
        timeline.record_run_start()
        timeline.record(TimelineEventType.NODE_ENTER, phase="EXECUTE", node_id="run_sim")
        timeline.record(TimelineEventType.NODE_EXIT, phase="EXECUTE", node_id="run_sim")
        timeline.record_run_end()

        packet = build_decision_packet(state, run_record, timeline=timeline)

        assert packet.run_timeline is not None
        assert packet.run_timeline["run_id"] == "int_test_001"
        assert len(packet.run_timeline["events"]) == 4

    def test_build_packet_generates_card(self) -> None:
        state = {
            "run_id": "int_test_002",
            "ir": None,
            "simulation_results": {"gdp_change": -0.05},
            "feedback": {
                "verdict": "REJECT",
                "issues": [{"severity": "blocker", "pass_id": "safety", "message": "Budget exceeded"}],
            },
            "audit_trail": [],
            "validation_trace": None,
        }
        run_record = _make_run_record("int_test_002")

        packet = build_decision_packet(state, run_record, include_card=True)

        assert packet.decision_card is not None
        assert packet.decision_card["verdict"] == "REJECT"
        assert packet.decision_card["issues"]["blocker_count"] == 1

    def test_get_decision_card_generates_fresh(self) -> None:
        packet = DecisionPacket(
            run_id="int_test_003",
            run_record=_make_run_record("int_test_003"),
            simulation_results={"gdp_change": 0.02},
            feedback={"verdict": "APPROVE", "issues": []},
        )

        card = packet.get_decision_card()
        assert isinstance(card, DecisionCard)
        assert card.run_id == "int_test_003"
        assert card.verdict == "APPROVE"

    def test_get_timeline_reconstructs(self) -> None:
        timeline = RunTimeline(run_id="int_test_004")
        timeline.record_run_start()
        timeline.record(TimelineEventType.ARTIFACT_CREATED, phase="EXECUTE", artifact_ref="sim_001")
        timeline.record_run_end()

        packet = DecisionPacket(
            run_id="int_test_004",
            run_record=_make_run_record("int_test_004"),
            run_timeline=timeline.to_artifact(),
        )

        reconstructed = packet.get_timeline()
        assert reconstructed is not None
        assert reconstructed.run_id == "int_test_004"
        assert len(reconstructed.events) == 3

    def test_schema_version_bumped(self) -> None:
        packet = DecisionPacket(run_id="int_test_005", run_record=_make_run_record("int_test_005"))
        assert packet.schema_version == "1.1"

    def test_end_to_end_workflow_simulation(self) -> None:
        run_id = "e2e_test_001"

        timeline = RunTimeline(run_id=run_id)
        timeline.record_run_start()

        timeline.record(TimelineEventType.PHASE_START, phase="FRAME")
        timeline.record(TimelineEventType.NODE_ENTER, phase="FRAME", node_id="draft_ir")
        timeline.record(TimelineEventType.NODE_EXIT, phase="FRAME", node_id="draft_ir")
        timeline.record(TimelineEventType.NODE_ENTER, phase="FRAME", node_id="validate_ir")
        timeline.record(
            TimelineEventType.VALIDATION_PASS,
            phase="FRAME",
            node_id="validate_ir",
            details={"pass_id": "schema"},
        )
        timeline.record(TimelineEventType.NODE_EXIT, phase="FRAME", node_id="validate_ir")
        timeline.record(TimelineEventType.PHASE_END, phase="FRAME")

        timeline.record(TimelineEventType.PHASE_START, phase="EXECUTE")
        timeline.record(TimelineEventType.NODE_ENTER, phase="EXECUTE", node_id="run_sim")
        timeline.record(
            TimelineEventType.ARTIFACT_CREATED,
            phase="EXECUTE",
            node_id="run_sim",
            artifact_ref="sim_results_001",
        )
        timeline.record(TimelineEventType.NODE_EXIT, phase="EXECUTE", node_id="run_sim")
        timeline.record(TimelineEventType.PHASE_END, phase="EXECUTE")

        timeline.record_run_end(success=True)

        state = {
            "run_id": run_id,
            "ir": None,
            "simulation_results": {"gdp_change": 0.015, "gini_coefficient": 0.32},
            "feedback": {"verdict": "APPROVE", "issues": []},
            "audit_trail": [],
            "validation_trace": None,
        }

        packet = build_decision_packet(state, _make_run_record(run_id), timeline=timeline, include_card=True)

        assert packet.run_timeline is not None
        assert len(packet.run_timeline["events"]) == 14
        assert packet.run_timeline["summary"]["artifact_count"] == 1

        assert packet.decision_card is not None
        assert packet.decision_card["verdict"] == "APPROVE"
        assert packet.decision_card["confidence"] == "HIGH"

        card = packet.get_decision_card()
        markdown = card.render_markdown()
        assert "✅ **APPROVE**" in markdown
        assert "GDP Change" in markdown

