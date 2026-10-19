from __future__ import annotations


def test_fabric_facades_preserve_owner_objects() -> None:
    from polisyos.fabric.connectors import SourceProfile
    from polisyos.fabric.connectors.profiles import SourceProfile as OwnerSourceProfile
    from polisyos.fabric.docs import DocChunkOptions
    from polisyos.fabric.docs.types import DocChunkOptions as OwnerDocChunkOptions
    from polisyos.fabric.ingestion import ConnectorManifestSpec
    from polisyos.fabric.ingestion.ingestion import (
        ConnectorManifestSpec as OwnerConnectorManifestSpec,
    )
    from polisyos.fabric.retrieval import RetrievalProviders
    from polisyos.fabric.retrieval.providers import RetrievalProviders as OwnerRetrievalProviders

    assert SourceProfile is OwnerSourceProfile
    assert DocChunkOptions is OwnerDocChunkOptions
    assert ConnectorManifestSpec is OwnerConnectorManifestSpec
    assert RetrievalProviders is OwnerRetrievalProviders
