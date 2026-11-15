"""Fixture source adoption binds the supplied file without repairing other owners."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.substrate_registry import (
    DEFAULT_L1_DCAT_PATH,
    DEFAULT_ROOT_MANIFEST_PATH,
)
from tests._helpers.acquisition_production import _baseline, bind_fixture_l1_catalog_source


def test_existing_regular_l1_requires_explicit_same_file_adoption(tmp_path: Path) -> None:
    """The actual Catalog bytes stay fixed while an explicit fixture owner binds them."""
    root = tmp_path / "owner"
    baseline = _baseline(root)
    selected = root / DEFAULT_L1_DCAT_PATH
    selected.parent.mkdir(parents=True, exist_ok=True)
    baseline.rename(selected)
    before = selected.read_bytes()
    inode = selected.stat().st_ino
    manifest = root / DEFAULT_ROOT_MANIFEST_PATH

    bind_fixture_l1_catalog_source(root, selected)
    assert not manifest.exists()

    bind_fixture_l1_catalog_source(root, selected, adopt_existing_regular_baseline=True)
    assert json.loads(manifest.read_text()) == {
        "schema_version": "1.0",
        "kind": "policyos.production_data_root",
        "fixture_catalog": {
            "path": DEFAULT_L1_DCAT_PATH.as_posix(),
            "sha256": hashlib.sha256(before).hexdigest(),
        },
    }
    manifest_before = manifest.read_bytes()
    bind_fixture_l1_catalog_source(root, selected, adopt_existing_regular_baseline=True)
    assert manifest.read_bytes() == manifest_before
    assert selected.read_bytes() == before
    assert selected.stat().st_ino == inode
    assert not selected.is_symlink()


@pytest.mark.parametrize(
    "conflict",
    [
        "different_regular_file",
        "matching_l1_symlink",
        "foreign_l1_symlink",
        "conflicting_manifest",
        "manifest_symlink",
    ],
)
def test_existing_source_adoption_preserves_conflicting_or_partial_owners(
    tmp_path: Path, conflict: str
) -> None:
    """Opt-in cannot turn an unrelated file or a partial symlink owner into its source."""
    root = tmp_path / "owner"
    root.mkdir()
    baseline = root / "explicit-baseline.duckdb"
    baseline.write_bytes(b"independently declared baseline bytes")
    selected = root / DEFAULT_L1_DCAT_PATH
    selected.parent.mkdir(parents=True, exist_ok=True)
    manifest = root / DEFAULT_ROOT_MANIFEST_PATH
    if conflict == "different_regular_file":
        # Equal content alone does not identify the explicitly supplied file.
        selected.write_bytes(b"independently declared baseline bytes")
    elif conflict == "matching_l1_symlink":
        selected.symlink_to(baseline)
    elif conflict == "foreign_l1_symlink":
        foreign = root / "foreign.duckdb"
        foreign.write_bytes(b"foreign owner")
        selected.symlink_to(foreign)
    else:
        baseline.rename(selected)
        baseline = selected
        if conflict == "conflicting_manifest":
            manifest.write_text('{"kind":"another.owner"}')
        else:
            foreign_manifest = root / "foreign-manifest.json"
            foreign_manifest.write_text('{"kind":"another.owner"}')
            manifest.symlink_to(foreign_manifest)
    selected_before = selected.read_bytes()
    baseline_before = baseline.read_bytes()
    manifest_before = manifest.read_bytes() if manifest.exists() else None
    selected_link = selected.readlink() if selected.is_symlink() else None
    manifest_link = manifest.readlink() if manifest.is_symlink() else None

    bind_fixture_l1_catalog_source(root, baseline, adopt_existing_regular_baseline=True)

    assert selected.read_bytes() == selected_before
    assert baseline.read_bytes() == baseline_before
    assert (manifest.read_bytes() if manifest.exists() else None) == manifest_before
    assert (selected.readlink() if selected.is_symlink() else None) == selected_link
    assert (manifest.readlink() if manifest.is_symlink() else None) == manifest_link


def test_clean_fixture_root_keeps_legacy_symlink_and_manifest_bytes(tmp_path: Path) -> None:
    """The original default call still declares the same controlled source wire."""
    root = tmp_path / "owner"
    baseline = _baseline(root)
    before = baseline.read_bytes()

    bind_fixture_l1_catalog_source(root, baseline, include_n7_dataset_bundle=True)

    selected = root / DEFAULT_L1_DCAT_PATH
    assert selected.is_symlink()
    assert selected.resolve(strict=True) == baseline.resolve(strict=True)
    expected = {
        "schema_version": "1.0",
        "kind": "policyos.production_data_root",
        "fixture_catalog": {
            "path": DEFAULT_L1_DCAT_PATH.as_posix(),
            "sha256": hashlib.sha256(before).hexdigest(),
        },
        "bundles": {
            "datasets": {
                "version_id": "fixture-only-datasets-v1",
                "path": DEFAULT_L1_DCAT_PATH.parent.relative_to("production_data").as_posix(),
            }
        },
    }
    assert (root / DEFAULT_ROOT_MANIFEST_PATH).read_bytes() == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    ).encode()
    assert baseline.read_bytes() == before
