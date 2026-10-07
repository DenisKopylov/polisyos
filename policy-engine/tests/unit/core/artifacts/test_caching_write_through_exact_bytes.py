"""Use distinct real stored metadata to distinguish reconstruction from transfer."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


@pytest.mark.parametrize("operation", ["put_bytes", "put_json"])
@pytest.mark.parametrize("seed_local", [False, True])
def test_write_through_transfers_exact_owner_bytes_across_distinct_creation_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, seed_local: bool
) -> None:
    original = ManifestLifecycle.build
    ticks = 0

    def distinct_clock(**kwargs: Any) -> Any:
        nonlocal ticks
        if kwargs.get("created_at") is None:
            kwargs["created_at"] = datetime(2026, 10, 6, tzinfo=UTC) + timedelta(seconds=ticks)
            ticks += 1
        return original(**kwargs)

    monkeypatch.setattr(ManifestLifecycle, "build", staticmethod(distinct_clock))
    local = FileSystemCAS(tmp_path / "local")
    remote = FileSystemCAS(tmp_path / "remote")
    payload = b"exact selected bytes" if operation == "put_bytes" else {"payload": "exact"}

    def options(version: str) -> PutOptions:
        return PutOptions(
            kind="tests.cache.exact-write",
            media_type="application/octet-stream"
            if operation == "put_bytes"
            else "application/json",
            producer=ProducerInfo(component="tests.cache", version=version),
        )

    seeded = local if seed_local else remote
    prior = getattr(seeded, operation)(payload, options("previous-default"))
    prior_default = seeded.get_manifest_bytes(prior)
    composite = CachingArtifactStore(remote=remote, local=local)
    selected = getattr(composite, operation)(payload, options("new-view"))
    owner_manifest = remote.get_manifest(selected)
    exact = ArtifactRef(
        artifact_id=selected.artifact_id,
        kind=selected.kind,
        media_type=selected.media_type,
        manifest_profile_sha256=ManifestLifecycle.profile_sha256(owner_manifest),
    )
    assert local.get_manifest_bytes(exact) == remote.get_manifest_bytes(selected)
    assert seeded.get_manifest_bytes(prior) == prior_default
    assert FileSystemCAS(local.root).get_bytes(exact) == remote.get_bytes(selected)
    assert FileSystemCAS(local.root).verify(exact).ok
