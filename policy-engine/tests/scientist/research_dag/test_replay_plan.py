from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.research_dag.models import ResearchNodeType
from polisyos.scientist.research_dag.replay import (
    ReplayMode,
    legacy_replay_status,
    plan_research_replay,
    public_replay_export,
    replay_research_path,
)


def _ref(suffix: str, *, kind: str = "scientist.source") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
    )


def test_pinned_replay_plan_uses_cas_inputs_without_live_web() -> None:
    source_ref = _ref("1")
    dag_ref = _ref("2", kind="scientist.research_dag")
    builder = ResearchDAGBuilder(run_id="run_replay", workflow_id="scientist_policy_design")
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="tool:safe_fetch",
        summary="Fetched pinned source.",
        artifact_refs=[source_ref],
    )
    builder.add_node(
        node_type=ResearchNodeType.EXTRACTION,
        producer="extractor",
        summary="Snippet extracted.",
        output_fingerprint="sha256:" + "3" * 64,
        metadata={"snippet_id": "snippet_1"},
    )

    plan = plan_research_replay(
        builder.artifact(),
        dag_ref=dag_ref,
        mode=ReplayMode.PINNED_INPUT_REPLAY,
    )

    assert plan.live_fetch_required is False
    assert plan.required_artifact_refs == [source_ref]
    assert plan.unsupported_steps == []
    assert plan.replay_status == "available"


def test_replay_plan_rejects_live_fetch_for_audit_mode() -> None:
    dag_ref = _ref("2", kind="scientist.research_dag")
    builder = ResearchDAGBuilder(run_id="run_replay", workflow_id="scientist_policy_design")
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="tool:web_fetch",
        summary="Would require live fetch.",
        metadata={"live_fetch_required": True},
    )

    with pytest.raises(ValueError, match="audit replay cannot require live web"):
        plan_research_replay(
            builder.artifact(),
            dag_ref=dag_ref,
            mode=ReplayMode.AUDIT_RECONSTRUCTION,
        )


def test_public_replay_export_redacts_hidden_artifact_refs() -> None:
    hidden_ref = _ref("9", kind="scientist.hidden_benchmark.answer")
    builder = ResearchDAGBuilder(run_id="run_replay", workflow_id="scientist_policy_design")
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="hidden_eval",
        summary="Read hidden fixture.",
        artifact_refs=[hidden_ref],
    )
    dag = builder.artifact()
    replay_json = str(public_replay_export(dag))

    assert str(hidden_ref.artifact_id) not in replay_json
    assert "hidden_benchmark" not in replay_json
    assert "hidden_eval" not in replay_json


def test_legacy_minimal_dag_renders_legacy_minimal() -> None:
    builder = ResearchDAGBuilder(run_id="run_replay", workflow_id="scientist_policy_design")
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="legacy_fetch",
        summary="Old node without pinned replay material.",
    )

    replay = replay_research_path(builder.artifact())

    assert replay.replay_status == "legacy_minimal"
    assert legacy_replay_status(builder.artifact()) == "legacy_minimal"


def test_public_replay_export_redacts_hidden_node_text() -> None:
    hidden_ref = _ref("9", kind="scientist.hidden_benchmark.answer")
    builder = ResearchDAGBuilder(run_id="run_replay", workflow_id="scientist_policy_design")
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="hidden_eval",
        summary="hidden_benchmark answer read.",
        artifact_refs=[hidden_ref],
        safety_labels=["hidden_eval"],
    )

    replay = public_replay_export(builder.artifact())
    replay_json = str(replay)

    assert "redacted_node" in replay_json
    assert "hidden_eval" not in replay_json
    assert "hidden_benchmark" not in replay_json
