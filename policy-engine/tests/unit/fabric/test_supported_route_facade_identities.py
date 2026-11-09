from __future__ import annotations

import importlib

import pytest


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


def test_data_plane_facade_preserves_lazy_owners_and_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = importlib.import_module("polisyos.fabric.data_plane")
    exports = {
        "parse_datetime_utc": "polisyos.fabric.data_plane.temporal",
        "run_orchestrated_ingestion": "polisyos.fabric.data_plane.orchestrator",
        "query_world_table": "polisyos.fabric.world.query",
        "LiveAttemptTerminal": "polisyos.fabric.data_plane.evidence_journal",
    }
    assert set(facade.__all__) == set(vars(facade)["_LAZY_IMPORTS"])
    for name, provider_name in exports.items():
        provider = importlib.import_module(provider_name)
        monkeypatch.delitem(vars(facade), name, raising=False)
        assert getattr(facade, name) is getattr(provider, name)
        assert vars(facade)[name] is getattr(provider, name)
    assert set(facade.__all__).issubset(dir(facade))

    with pytest.raises(AttributeError, match="missing_fabric_facade_member") as missing:
        facade.__getattr__("missing_fabric_facade_member")
    assert isinstance(missing.value.__cause__, KeyError)
    assert missing.value.__cause__.args == ("missing_fabric_facade_member",)
