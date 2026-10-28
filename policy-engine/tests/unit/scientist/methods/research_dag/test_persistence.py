from __future__ import annotations

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.methods.research_dag.models import ResearchNodeType
from polisyos.scientist.methods.research_dag.persistence import (
    RESEARCH_DAG_KIND,
    RESEARCH_DAG_SCHEMA_NAME,
    RESEARCH_DAG_SCHEMA_VERSION,
    load_research_dag,
    persist_research_dag,
)
from polisyos.scientist.methods.research_dag.replay import legacy_research_dag_status


def _ref(suffix: str, *, profile: str | None = None) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.source",
        media_type="application/json",
        manifest_profile_sha256=profile,
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
    manifest = store.get_manifest(ref)
    assert ref.manifest_profile_sha256 is not None

    assert ref.kind == RESEARCH_DAG_KIND
    assert loaded == dag
    assert {item.role for item in manifest.inputs} == {
        "claim_ledger",
        "research_node_artifact[0]",
    }


def test_selected_parent_and_real_child_views_survive_ambient_default(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    sources = [
        store.put_json(
            {"same_payload": True},
            PutOptions(
                kind="scientist.source",
                media_type="application/json",
                schema=SchemaInfo(name=f"example.source.{version}", version="1.0"),
            ),
            return_selected_profile=True,
        )
        for version in ("first", "second")
    ]
    first, second = sources
    assert first.artifact_id == second.artifact_id
    assert first.manifest_profile_sha256 != second.manifest_profile_sha256
    assert all(store.verify(ref).ok for ref in sources)
    first_schema = store.get_manifest(first).artifact_schema
    second_schema = store.get_manifest(second).artifact_schema
    assert first_schema is not None
    assert second_schema is not None
    assert first_schema.name == "example.source.first"
    assert second_schema.name == "example.source.second"

    builder = ResearchDAGBuilder(run_id="run_1", workflow_id="scientist_policy_design")
    node = builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="test",
        summary="Read two selected views.",
        artifact_refs=sources,
    )
    dag = builder.artifact()
    # Pre-establish a different ambient/default manifest for the same DAG bytes.
    default_ref = store.put_json(
        dag,
        PutOptions(
            kind=RESEARCH_DAG_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=RESEARCH_DAG_SCHEMA_NAME, version=RESEARCH_DAG_SCHEMA_VERSION),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_ref = persist_research_dag(store, dag)
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(default_ref).inputs == []

    selected_manifest = store.get_manifest(selected_ref)
    assert selected_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        selected_manifest
    )
    assert store.verify(selected_ref).ok
    assert load_research_dag(store, selected_ref) == dag
    assert node.artifact_refs == sources
    assert [item.manifest_profile_sha256 for item in selected_manifest.inputs] == [
        first.manifest_profile_sha256,
        second.manifest_profile_sha256,
    ]
    for manifest_input, child_ref in zip(selected_manifest.inputs, sources, strict=True):
        assert manifest_input.artifact_id == child_ref.artifact_id
        assert manifest_input.manifest_profile_sha256 == child_ref.manifest_profile_sha256
        assert store.verify(child_ref).ok


def test_legacy_research_dag_status_marks_old_runs_loadable() -> None:
    assert legacy_research_dag_status(None) == "legacy_missing"
    assert legacy_research_dag_status(_ref("3")) == "available"
