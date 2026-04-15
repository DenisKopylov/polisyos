from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.components._cli_store import build_cli_artifact_store, build_cli_filesystem_cas


def test_build_cli_artifact_store_uses_declarative_factory(tmp_path) -> None:
    store = build_cli_artifact_store(tmp_path / "cas")
    ref = store.put_json(
        {"hello": "cli"},
        ArtifactWriteOptions(
            kind="tests.cli_store",
            media_type="application/json",
            schema=SchemaInfo(name="tests.CliStore", version="1.0"),
        ),
    )

    payload = store.get_bytes(ArtifactID.model_validate(str(ref.artifact_id)))

    assert payload


def test_build_cli_filesystem_cas_returns_filesystem_store(tmp_path) -> None:
    store = build_cli_filesystem_cas(tmp_path / "cas")

    assert isinstance(store, FileSystemCAS)
