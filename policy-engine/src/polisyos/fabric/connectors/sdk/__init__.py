"""Authoring helpers for Fabric contracted source connectors."""

from polisyos.fabric.connectors.sdk.scaffold import (
    PROFILE_ID_BY_CONNECTOR_ID,
    SourceScaffoldArtifacts,
    SourceScaffoldSpec,
    build_source_contract_scaffold,
    build_source_profile_matrix,
    make_quality_contract_id,
    make_replay_fixture_id,
    make_source_contract_id,
    make_source_doc_stub,
    make_source_profile_id,
    scaffold_source_artifacts,
)

__all__ = [
    "PROFILE_ID_BY_CONNECTOR_ID",
    "SourceScaffoldArtifacts",
    "SourceScaffoldSpec",
    "build_source_contract_scaffold",
    "build_source_profile_matrix",
    "make_quality_contract_id",
    "make_replay_fixture_id",
    "make_source_contract_id",
    "make_source_doc_stub",
    "make_source_profile_id",
    "scaffold_source_artifacts",
]

