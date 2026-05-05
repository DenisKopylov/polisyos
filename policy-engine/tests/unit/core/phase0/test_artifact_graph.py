from __future__ import annotations

from polisyos.core.artifacts.graph import NodeStatus, resolve_dependency_graph
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


def _put_json(
    store: FileSystemCAS,
    payload: dict[str, object],
    *,
    kind: str,
    inputs: list[InputRef] | None = None,
):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            inputs=inputs,
        ),
    )


def test_resolve_dependency_graph_traverses_inputs(store: FileSystemCAS) -> None:
    leaf = _put_json(store, {"leaf": True}, kind="test.leaf")
    mid = _put_json(
        store,
        {"mid": True},
        kind="test.mid",
        inputs=[InputRef(artifact_id=leaf.artifact_id, role="leaf")],
    )
    root = _put_json(
        store,
        {"root": True},
        kind="test.root",
        inputs=[InputRef(artifact_id=mid.artifact_id, role="mid")],
    )

    graph = resolve_dependency_graph(store, root.artifact_id)

    assert graph.total_artifacts == 3
    assert graph.is_complete
    assert graph.nodes[root.artifact_id.hex].status == NodeStatus.PRESENT
    assert graph.nodes[mid.artifact_id.hex].status == NodeStatus.PRESENT
    assert graph.nodes[leaf.artifact_id.hex].status == NodeStatus.PRESENT


def test_resolve_dependency_graph_reports_missing_dependency(store: FileSystemCAS) -> None:
    missing = ArtifactID.from_sha256_hex("f" * 64)
    root = _put_json(
        store,
        {"root": True},
        kind="test.root",
        inputs=[InputRef(artifact_id=missing, role="missing_input")],
    )

    graph = resolve_dependency_graph(store, root.artifact_id)
    missing_node = graph.nodes[missing.hex]

    assert missing_node.status == NodeStatus.MISSING
    assert not graph.is_complete


def test_resolve_dependency_graph_reports_corruption(store: FileSystemCAS) -> None:
    child = _put_json(store, {"child": 1}, kind="test.child")
    root = _put_json(
        store,
        {"root": 1},
        kind="test.root",
        inputs=[InputRef(artifact_id=child.artifact_id, role="child")],
    )
    blob_path, _ = store.get_paths(child.artifact_id)
    blob_path.write_bytes(b"corrupted")

    graph = resolve_dependency_graph(store, root.artifact_id)

    assert graph.nodes[child.artifact_id.hex].status == NodeStatus.CORRUPTED


def test_resolve_dependency_graph_respects_timeout_budget(store: FileSystemCAS) -> None:
    root = _put_json(store, {"root": True}, kind="test.root")

    graph = resolve_dependency_graph(
        store,
        root.artifact_id,
        timeout_seconds=0.0,
        batch_size=1,
    )

    assert graph.timed_out is True
    assert graph.nodes[root.artifact_id.hex].status == NodeStatus.SKIPPED_TIMEOUT
    assert graph.is_complete is False
