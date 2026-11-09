from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

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


def test_ingestion_facade_binds_owner_and_keeps_legacy_forwarding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import confidence_ledger as ledger

    facade = importlib.import_module("polisyos.fabric.ingestion")
    owner = importlib.import_module("polisyos.fabric.ingestion.ingestion")
    assert facade._ingestion_module is owner
    assert facade.ingestion is owner
    assert facade.ConnectorManifestSpec is owner.ConnectorManifestSpec
    assert facade.run_connectors_ingestion is owner.run_connectors_ingestion

    monkeypatch.delitem(vars(facade), "_load_transform_pipeline", raising=False)
    assert facade._load_transform_pipeline is owner._load_transform_pipeline
    assert vars(facade)["_load_transform_pipeline"] is owner._load_transform_pipeline
    with pytest.raises(AttributeError, match="missing_ingestion_facade_member"):
        facade.__getattr__("missing_ingestion_facade_member")

    root = ledger._loaded_policy_engine_root()
    closure = ((facade.__name__, Path(facade.__file__).relative_to(root).as_posix()),)
    assert ledger._source_facade_runtime_projection(root, closure)[0]
    with monkeypatch.context() as altered:
        altered.setattr(facade, "_ingestion_module", SimpleNamespace())
        with pytest.raises(ledger.ConfidenceLedgerError, match="source module binding differs"):
            ledger._source_facade_runtime_projection(root, closure)


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
