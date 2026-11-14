"""Registry readers require exact profile reads without requiring writes."""

from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core import artifacts
from polisyos.core.registry.builder import build_default_registry_bundle
from polisyos.core.registry.loader import (
    load_registry_bundle,
    load_registry_bundle_content,
    load_registry_bundle_payload,
)


def test_selected_registry_bundle_reopens_through_read_only_cas(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    written = build_default_registry_bundle(store, return_selected_profile=True)
    reader = artifacts.FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    assert not hasattr(reader, "put_json")
    assert load_registry_bundle(reader, written.bundle_ref) == written
    payload = load_registry_bundle_payload(reader, written.bundle_ref)
    assert payload.units_registry == written.units_registry
    content = load_registry_bundle_content(reader, written.bundle_ref)
    assert content.bundle_ref == written.bundle_ref
    assert content.units_registry is not None
    assert "ratio" in content.units_registry.units
    assert content == load_registry_bundle_content(store, written.bundle_ref)


class _ReaderWithoutRawManifest:
    """A weaker facade must not gain exact-profile access from nominal reads."""

    def __init__(self, store: artifacts.FileSystemCAS) -> None:
        self.has = store.has
        self.get_bytes = store.get_bytes
        self.get_manifest = store.get_manifest


def test_registry_reader_still_requires_raw_selected_manifest(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    written = build_default_registry_bundle(store, return_selected_profile=True)
    with pytest.raises(CanonicalProfileRefusalError, match="raw_manifest_unavailable"):
        load_registry_bundle(_ReaderWithoutRawManifest(store), written.bundle_ref)
