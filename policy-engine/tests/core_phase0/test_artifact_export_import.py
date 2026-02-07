from __future__ import annotations

from polisyos.core.artifacts.graph import resolve_dependency_graph
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


def test_export_and_import_subgraph_roundtrip(tmp_path) -> None:
    source_store = FileSystemCAS(tmp_path / "source")
    leaf = source_store.put_json(
        {"leaf": True},
        PutOptions(kind="test.leaf", media_type="application/json"),
    )
    root = source_store.put_json(
        {"root": True},
        PutOptions(
            kind="test.root",
            media_type="application/json",
            inputs=[InputRef(artifact_id=leaf.artifact_id, role="leaf")],
        ),
    )
    graph = resolve_dependency_graph(source_store, root.artifact_id)
    archive_path = tmp_path / "bundle.tar.gz"

    export_report = source_store.export_subgraph(graph.all_artifact_ids(), archive_path)
    assert export_report.exported_artifacts == 2
    assert export_report.output_path.exists()
    assert not export_report.missing_artifacts

    target_store = FileSystemCAS(tmp_path / "target")
    import_report = target_store.import_subgraph(export_report.output_path, verify_integrity=True)
    assert import_report.imported_artifacts >= 2
    assert not import_report.verification_failed
    assert target_store.has(root.artifact_id)
    assert target_store.has(leaf.artifact_id)
