from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.research_dag.models import ResearchNodeType
from polisyos.scientist.research_dag.persistence import (
    RESEARCH_DAG_KIND,
    load_research_dag,
    persist_research_dag,
)
from polisyos.scientist.research_dag.replay import legacy_research_dag_status


def _ref(suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.source",
        media_type="application/json",
    )


def test_research_dag_persists_and_loads_from_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    source_ref = _ref("1")
    claim_ref = _ref("2")
    builder = ResearchDAGBuilder(
        run_id="run_1",
        workflow_id="scientist_policy_design",
        claim_ledger_ref=claim_ref,
    )
    builder.add_node(
        node_type=ResearchNodeType.SOURCE_ACQUISITION,
        producer="test",
        summary="Acquire source.",
        artifact_refs=[source_ref],
    )
    dag = builder.artifact()

    ref = persist_research_dag(store, dag)
    loaded = load_research_dag(store, ref)
    manifest = store.get_manifest(ref.artifact_id)

    assert ref.kind == RESEARCH_DAG_KIND
    assert loaded == dag
    assert {item.role for item in manifest.inputs} == {
        "claim_ledger",
        "research_node_artifact[0]",
    }


def test_legacy_research_dag_status_marks_old_runs_loadable() -> None:
    assert legacy_research_dag_status(None) == "legacy_missing"
    assert legacy_research_dag_status(_ref("3")) == "available"
