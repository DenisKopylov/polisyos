"""Regression witnesses for the DatasetManifest migration owner move.

The migration is a format conversion, not a provenance or admission step.  The
tests therefore pin the historical byte-shape behavior separately from the
Fabric model's stricter validation and make registration explicit at the
composition/CLI boundary.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def _legacy_manifest(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "0.9",
        "datasetName": "baseline",
        "rawHash": "sha256:abc",
    }
    payload.update(extra)
    return payload


def _complete_current_manifest(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "0.9",
        "datasetName": "baseline",
        "rawHash": "sha256:abc",
        "source": "catalog",
        "license": "CC-BY-4.0",
        "row_count": 2,
        "pii_flags": {"direct": False},
        "quality": {
            "missing_rate": 0.0,
            "duplicate_rate": 0.0,
            "outlier_rate": 0.0,
            "coverage": {"region_coverage": "global"},
        },
        "created_at": "2026-09-22T00:00:00+00:00",
    }
    payload.update(extra)
    return payload


def test_fabric_owner_exposes_manifest_converter_without_fabricating_fields() -> None:
    """The moved callback preserves the 0.9 rename contract only."""
    from polisyos.fabric.identity.migrations import (
        migrate_manifest_0_9_to_1_0,
    )

    source = _legacy_manifest(unknown_field={"keep": True})
    migrated = migrate_manifest_0_9_to_1_0(source)

    assert migrated == {
        "schema_version": "0.9",
        "dataset_name": "baseline",
        "raw_hash": "sha256:abc",
        "unknown_field": {"keep": True},
    }
    assert "created_at" not in migrated


def test_missing_legacy_fields_are_not_fabricated() -> None:
    """The callback leaves absent raw hash and timestamp fields absent."""
    from polisyos.fabric.identity.migrations import migrate_manifest_0_9_to_1_0

    source = _legacy_manifest()
    del source["rawHash"]

    migrated = migrate_manifest_0_9_to_1_0(source)

    assert migrated == {
        "schema_version": "0.9",
        "dataset_name": "baseline",
    }
    assert "raw_hash" not in migrated
    assert "created_at" not in migrated


@pytest.mark.parametrize(
    ("dataset_name", "raw_hash"),
    [("baseline", "sha256:abc"), ("different", "sha256:def")],
)
def test_equal_and_conflicting_aliases_are_not_silently_resolved(
    dataset_name: str,
    raw_hash: str,
) -> None:
    """Both spellings remain visible until an explicit policy resolves them."""
    from polisyos.fabric.identity.migrations import migrate_manifest_0_9_to_1_0

    migrated = migrate_manifest_0_9_to_1_0(
        _legacy_manifest(dataset_name=dataset_name, raw_hash=raw_hash)
    )

    assert migrated["datasetName"] == "baseline"
    assert migrated["dataset_name"] == dataset_name
    assert migrated["rawHash"] == "sha256:abc"
    assert migrated["raw_hash"] == raw_hash


def test_alias_conflict_is_not_presented_as_a_validated_fabric_manifest() -> None:
    """A successful rename must not bypass the target DTO's extra-key guard."""
    from polisyos.fabric.identity.manifest import DatasetManifest
    from polisyos.fabric.identity.migrations import migrate_manifest_0_9_to_1_0

    migrated = migrate_manifest_0_9_to_1_0(
        _complete_current_manifest(dataset_name="different", raw_hash="sha256:def")
    )

    with pytest.raises(ValidationError):
        DatasetManifest.model_validate(migrated)


def test_complete_legacy_manifest_remains_validatable_by_fabric_dto() -> None:
    """A complete legacy profile can be validated after alias conversion."""
    from polisyos.fabric.identity.manifest import DatasetManifest
    from polisyos.fabric.identity.migrations import migrate_manifest_0_9_to_1_0

    migrated = migrate_manifest_0_9_to_1_0(_complete_current_manifest())

    model = DatasetManifest.model_validate(migrated)
    assert model.dataset_name == "baseline"
    assert model.raw_hash == "sha256:abc"
    assert model.created_at == "2026-09-22T00:00:00+00:00"


def test_common_engine_preserves_current_noop_and_schema_errors() -> None:
    """The shared engine owns stamping, no-op copies, and schema errors."""
    from polisyos.common.migrations.base import migrate_artifact
    from polisyos.fabric.identity.migrations import register_manifest_migration

    register_manifest_migration()
    current = {
        "schema_version": "1.0",
        "dataset_name": "baseline",
        "raw_hash": "sha256:abc",
    }

    migrated = migrate_artifact(current, "dataset_manifest", "1.0")

    assert migrated == current
    assert migrated is not current
    legacy = _legacy_manifest()
    legacy_before = legacy.copy()
    migrated_legacy = migrate_artifact(legacy, "dataset_manifest", "1.0")
    assert legacy == legacy_before
    assert migrated_legacy["schema_version"] == "1.0"
    with pytest.raises(ValueError, match="Missing schema_version"):
        migrate_artifact({"datasetName": "baseline"}, "dataset_manifest", "1.0")
    with pytest.raises(TypeError, match="must be a string"):
        migrate_artifact(
            {"schema_version": 0.9, "datasetName": "baseline"},
            "dataset_manifest",
            "1.0",
        )
    with pytest.raises(ValueError, match="No migrator"):
        migrate_artifact(_legacy_manifest(), "dataset_manifest", "2.0")


def test_legacy_common_adapter_matches_fabric_callback_profile() -> None:
    """The bounded compatibility duplicate keeps the supported rename equal."""
    from polisyos.common.migrations.manifest import (
        migrate_manifest_0_9_to_1_0 as common_converter,
    )
    from polisyos.fabric.identity.migrations import (
        migrate_manifest_0_9_to_1_0 as fabric_converter,
    )

    common_payload = _legacy_manifest(unknown_field={"keep": True})
    fabric_payload = _legacy_manifest(unknown_field={"keep": True})

    assert common_converter(common_payload) == fabric_converter(fabric_payload)


def test_explicit_fabric_registration_is_required_for_common_engine() -> None:
    """The generic Common engine stays neutral until composition registers Fabric."""
    code = """
from polisyos.common.migrations.base import migrate_artifact
from polisyos.fabric.identity.migrations import register_manifest_migration

payload = {"schema_version": "0.9", "datasetName": "baseline", "rawHash": "sha256:abc"}
try:
    migrate_artifact(payload, "dataset_manifest", "1.0")
except ValueError as exc:
    assert "No migrator" in str(exc)
else:
    raise AssertionError("Common engine registered Fabric converter implicitly")

register_manifest_migration()
assert migrate_artifact(payload, "dataset_manifest", "1.0") == {
    "schema_version": "1.0",
    "dataset_name": "baseline",
    "raw_hash": "sha256:abc",
}
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_common_migrations_import_does_not_eagerly_import_fabric() -> None:
    """Importing generic migration primitives does not initialize Fabric."""
    code = """
import sys
import polisyos.common.migrations
from polisyos.common.migrations import MANIFEST_CURRENT_VERSION
assert MANIFEST_CURRENT_VERSION == "1.0"
assert "polisyos.fabric" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_legacy_common_adapter_registers_without_importing_fabric() -> None:
    """The deprecated import path stays a local compatibility registration."""
    code = """
import sys
from polisyos.common.migrations.manifest import migrate_manifest_0_9_to_1_0

payload = {"schema_version": "0.9", "datasetName": "baseline", "rawHash": "sha256:abc"}
assert migrate_manifest_0_9_to_1_0(payload) == {
    "schema_version": "0.9",
    "dataset_name": "baseline",
    "raw_hash": "sha256:abc",
}
assert "polisyos.fabric" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_legacy_common_manifest_module_remains_a_compatibility_adapter() -> None:
    """The old import path remains a narrow adapter while callers transition."""
    from polisyos.common.migrations.manifest import (
        MANIFEST_CURRENT_VERSION,
        migrate_manifest_0_9_to_1_0,
    )

    assert MANIFEST_CURRENT_VERSION == "1.0"
    assert migrate_manifest_0_9_to_1_0(_legacy_manifest())["dataset_name"] == "baseline"


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_canonical_cli_uses_fabric_registration_for_json_and_yaml(
    tmp_path: Path,
    suffix: str,
) -> None:
    """The operational CLI keeps format selection and output isolation intact."""
    from tools.ops_runners.migrations.migrate import main as canonical_main

    payload = _legacy_manifest()
    input_path = tmp_path / f"input{suffix}"
    output_path = tmp_path / f"output{suffix}"
    if suffix == ".json":
        input_path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        yaml = pytest.importorskip("yaml")
        input_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    output_path.write_text("sentinel\n", encoding="utf-8")

    assert canonical_main(["dataset_manifest", str(input_path), str(output_path)]) == 0

    if suffix == ".json":
        observed = json.loads(output_path.read_text(encoding="utf-8"))
        assert json.loads(input_path.read_text(encoding="utf-8")) == payload
    else:
        yaml = pytest.importorskip("yaml")
        observed = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        assert yaml.safe_load(input_path.read_text(encoding="utf-8")) == payload
    assert observed == {
        "schema_version": "1.0",
        "dataset_name": "baseline",
        "raw_hash": "sha256:abc",
    }


def test_operational_binding_points_to_fabric_converter() -> None:
    """The TOML binding resolves and exercises the schema-owner converter."""
    import importlib

    from tools.ops_runners.migrations.contracts import validate_helper_binding

    binding = validate_helper_binding("dataset_manifest")

    assert binding.implementation == (
        "polisyos.fabric.identity.migrations.migrate_manifest_0_9_to_1_0"
    )
    module_name, function_name = binding.implementation.rsplit(".", 1)
    converter = getattr(importlib.import_module(module_name), function_name)
    assert converter(_legacy_manifest()) == {
        "schema_version": "0.9",
        "dataset_name": "baseline",
        "raw_hash": "sha256:abc",
    }
