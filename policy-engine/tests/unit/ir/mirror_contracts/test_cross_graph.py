from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    load_cross_graph_evidence_profile,
    persist_cross_graph_evidence_profile,
)
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_cross_graph_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract("ir", "cross_graph")


def test_cross_graph_writer_returns_exact_selected_profile_on_same_bytes(tmp_path) -> None:
    cas_root = tmp_path / "cas"
    store = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    profile = CrossGraphEvidenceProfile(summary=CrossGraphEvidenceSummary())

    legacy_ref = persist_cross_graph_evidence_profile(store, profile)
    selected_ref = persist_cross_graph_evidence_profile(
        store,
        profile,
        schema_version="2.2",
        return_selected_profile=True,
    )

    assert legacy_ref.artifact_id == selected_ref.artifact_id
    assert legacy_ref.manifest_profile_sha256 is None
    assert selected_ref.manifest_profile_sha256 is not None
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    selected_manifest = fresh_reader.get_manifest(selected_ref)
    legacy_manifest = fresh_reader.get_manifest(legacy_ref)
    assert selected_manifest.artifact_schema is not None
    assert selected_manifest.artifact_schema.version == "2.2"
    assert legacy_manifest.artifact_schema is not None
    assert legacy_manifest.artifact_schema.version == "2.1"
    assert load_cross_graph_evidence_profile(fresh_reader, selected_ref) == profile
