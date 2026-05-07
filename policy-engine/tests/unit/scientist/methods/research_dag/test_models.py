from __future__ import annotations

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.research_dag.models import (
    ResearchDAGArtifact,
    ResearchDAGEdge,
    ResearchDAGNode,
    ResearchEdgeType,
    ResearchNodeType,
)


def _ref(suffix: str = "a") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.test",
        media_type="application/json",
    )


def _hidden_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "9" * 64,
        kind="scientist.latent.hidden_benchmark",
        media_type="application/json",
    )


def test_research_dag_artifact_validates_node_edge_contract() -> None:
    question = ResearchDAGNode(
        node_id="question",
        node_type=ResearchNodeType.QUESTION,
        run_id="run_1",
        workflow_id="scientist_policy_design",
        producer="test",
        summary="What should be decided?",
    )
    synthesis = ResearchDAGNode(
        node_id="synthesis",
        node_type=ResearchNodeType.SYNTHESIS,
        run_id="run_1",
        workflow_id="scientist_policy_design",
        producer="test",
        summary="Summarize evidence.",
        artifact_refs=[_ref()],
        claim_ids=["claim_1"],
    )

    artifact = ResearchDAGArtifact(
        run_id="run_1",
        workflow_id="scientist_policy_design",
        nodes=[question, synthesis],
        edges=[
            ResearchDAGEdge(
                source_node_id="question",
                target_node_id="synthesis",
                edge_type=ResearchEdgeType.DEPENDS_ON,
            )
        ],
    )

    assert artifact.hidden_content_redacted is True
    assert artifact.nodes[1].claim_ids == ["claim_1"]


def test_orphaned_supports_edge_fails_validation() -> None:
    node = ResearchDAGNode(
        node_id="claim",
        node_type=ResearchNodeType.EXTRACTION,
        run_id="run_1",
        producer="test",
        summary="Extract a claim.",
    )

    with pytest.raises(ValueError, match="orphaned"):
        ResearchDAGArtifact(
            run_id="run_1",
            workflow_id="scientist_policy_design",
            nodes=[node],
            edges=[
                ResearchDAGEdge(
                    source_node_id="missing_source",
                    target_node_id="claim",
                    edge_type=ResearchEdgeType.SUPPORTS,
                )
            ],
        )


def test_cyclic_edges_fail_validation() -> None:
    source = ResearchDAGNode(
        node_id="source",
        node_type=ResearchNodeType.SOURCE_READ,
        run_id="run_1",
        producer="test",
        summary="Read source.",
    )
    synthesis = ResearchDAGNode(
        node_id="synthesis",
        node_type=ResearchNodeType.SYNTHESIS,
        run_id="run_1",
        producer="test",
        summary="Synthesize.",
    )

    with pytest.raises(ValueError, match="acyclic"):
        ResearchDAGArtifact(
            run_id="run_1",
            workflow_id="scientist_policy_design",
            nodes=[source, synthesis],
            edges=[
                ResearchDAGEdge(
                    source_node_id="source",
                    target_node_id="synthesis",
                    edge_type=ResearchEdgeType.SUPPORTS,
                ),
                ResearchDAGEdge(
                    source_node_id="synthesis",
                    target_node_id="source",
                    edge_type=ResearchEdgeType.DERIVES,
                ),
            ],
        )


def test_node_run_id_and_workflow_id_must_match_artifact() -> None:
    node = ResearchDAGNode(
        node_id="source",
        node_type=ResearchNodeType.SOURCE_READ,
        run_id="other_run",
        workflow_id="scientist_policy_verified",
        producer="test",
        summary="Read source.",
    )

    with pytest.raises(ValueError, match="run_id"):
        ResearchDAGArtifact(
            run_id="run_1",
            workflow_id="scientist_policy_design",
            nodes=[node],
        )


def test_public_dag_rejects_hidden_eval_metadata() -> None:
    node = ResearchDAGNode(
        node_id="source",
        node_type=ResearchNodeType.SOURCE_READ,
        run_id="run_1",
        producer="test",
        summary="Read source.",
        metadata={"hidden_benchmark_case": "must not leak"},
    )

    with pytest.raises(ValueError, match="forbidden metadata"):
        ResearchDAGArtifact(
            run_id="run_1",
            workflow_id="scientist_policy_design",
            nodes=[node],
        )


def test_public_dag_rejects_hidden_benchmark_artifact_refs() -> None:
    node = ResearchDAGNode(
        node_id="source",
        node_type=ResearchNodeType.SOURCE_READ,
        run_id="run_1",
        workflow_id="scientist_policy_design",
        producer="test",
        summary="Read source.",
        artifact_refs=[_hidden_ref()],
    )

    with pytest.raises(ValueError, match="hidden artifact ref"):
        ResearchDAGArtifact(
            run_id="run_1",
            workflow_id="scientist_policy_design",
            nodes=[node],
        )
