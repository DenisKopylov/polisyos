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


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_canonical_cli_uses_selected_fabric_converter_for_json_and_yaml(
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


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_registered_cli_complete_profile_reopens_through_fresh_registry(
    tmp_path: Path, suffix: str
) -> None:
    """Persisted conversion is distinct from actual registry admission."""
    from tools.cli import main as tools_cli_main

    payload = _complete_current_manifest()
    source = tmp_path / f"legacy{suffix}"
    if suffix == ".json":
        source.write_text(json.dumps(payload))
    else:
        yaml = pytest.importorskip("yaml")
        source.write_text(yaml.safe_dump(payload, sort_keys=False))
    before = source.read_bytes()
    outputs = []
    for mode in ("default", "explicit"):
        output = tmp_path / f"{mode}{suffix}"
        args = [
            "migrations",
            "migrate",
            "--timing-log",
            str(tmp_path / "timing.jsonl"),
            "dataset_manifest",
            str(source),
            str(output),
        ]
        if mode == "explicit":
            args.extend(["--to", "1.0"])
        assert tools_cli_main(args) == 0
        converted = (
            json.loads(output.read_text())
            if suffix == ".json"
            else yaml.safe_load(output.read_text())
        )
        outputs.append(converted)
        curated = tmp_path / mode
        curated.mkdir()
        (curated / "baseline_manifest.json").write_text(json.dumps(converted))
        observed = _fresh_registry(curated)
        assert observed["dataset_name"] == "baseline"
        assert observed["raw_hash"] == payload["rawHash"]
        assert observed["created_at"] == payload["created_at"]
        assert observed["schema_version"] == "1.0"
    assert outputs[0] == outputs[1]
    output = tmp_path / f"unsupported{suffix}"
    output.write_bytes(b"old output")
    assert (
        tools_cli_main(
            [
                "migrations",
                "migrate",
                "--timing-log",
                str(tmp_path / "timing.jsonl"),
                "dataset_manifest",
                str(source),
                str(output),
                "--to",
                "2.0",
            ]
        )
        != 0
    )
    assert output.read_bytes() == b"old output"
    assert source.read_bytes() == before


_REGISTRY_READER = r"""
import json
import sys
from pathlib import Path
import polisyos.fabric._internal.registry as registry_module
try:
    registry = registry_module.ManifestRegistry(Path(sys.argv[1]))
    selected = registry.require("baseline")
except ValueError as error:
    print(json.dumps({"accepted": False, "error": str(error)}))
else:
    print(json.dumps({"accepted": True, "payload": selected.model_dump(mode="json"),
                      "origin": str(Path(registry_module.__file__).resolve())}))
"""


def _fresh_registry(curated: Path, *, accepted: bool = True) -> dict[str, Any]:
    """Require a persisted manifest in a new native Fabric reader process."""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", _REGISTRY_READER, str(curated)],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["accepted"] is accepted, result
    if not accepted:
        return result
    import polisyos.fabric._internal.registry as registry_module

    assert result["origin"] == str(Path(registry_module.__file__).resolve())
    return result["payload"]


@pytest.mark.parametrize(
    ("profile", "accepted"),
    [
        ("legacy", True),
        ("current", True),
        ("equal_aliases", False),
        ("conflicting_aliases", False),
        ("unknown", False),
        ("missing_raw_hash", False),
        ("missing_created_at", True),
        ("reconciliation_fail", False),
    ],
)
def test_finite_format_matrix_separates_conversion_from_registry_admission(
    tmp_path: Path, profile: str, accepted: bool
) -> None:
    """Synthetic profile outcomes do not invent provenance or resolve conflicts."""
    from tools.ops_runners.migrations.migrate import main as canonical_main

    payload = _complete_current_manifest()
    if profile == "current":
        payload["dataset_name"] = payload.pop("datasetName")
        payload["raw_hash"] = payload.pop("rawHash")
    elif profile in {"equal_aliases", "conflicting_aliases"}:
        payload["dataset_name"] = "baseline" if profile == "equal_aliases" else "different"
        payload["raw_hash"] = payload["rawHash"] if profile == "equal_aliases" else "other"
    elif profile == "unknown":
        payload["unknown_field"] = {"preserve": True}
    elif profile == "missing_raw_hash":
        del payload["rawHash"]
    elif profile == "missing_created_at":
        del payload["created_at"]
    elif profile == "reconciliation_fail":
        payload["reconciliation"] = {
            "status": "fail",
            "tolerance": 0.0,
            "total_outflow": 1.0,
            "total_inflow": 2.0,
            "diff": 1.0,
        }
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(payload))
    before = source.read_bytes()
    curated = tmp_path / "curated"
    curated.mkdir()
    output = curated / "baseline_manifest.json"
    assert canonical_main(["dataset_manifest", str(source), str(output)]) == 0
    converted = json.loads(output.read_text())
    assert converted["schema_version"] == "1.0"
    assert ("created_at" in converted) == ("created_at" in payload)
    assert ("raw_hash" in converted) == ("rawHash" in payload or "raw_hash" in payload)
    assert source.read_bytes() == before
    observed = _fresh_registry(curated, accepted=accepted)
    if profile in {"equal_aliases", "conflicting_aliases"}:
        assert converted["datasetName"] == payload["datasetName"]
        assert converted["dataset_name"] == payload["dataset_name"]
        assert converted["rawHash"] == payload["rawHash"]
        assert converted["raw_hash"] == payload["raw_hash"]
    if profile == "unknown":
        assert converted["unknown_field"] == {"preserve": True}
    if profile == "missing_created_at":
        # Native DTO's current-clock default is not supplied source provenance.
        assert observed["created_at"]
        assert "created_at" not in converted
    if profile == "reconciliation_fail":
        assert "marked unusable" in observed["error"]
    elif not accepted:
        assert "Invalid manifest" in observed["error"]
        if profile == "missing_raw_hash":
            assert "raw_hash" in observed["error"]
            assert "Field required" in observed["error"]
        elif profile == "unknown":
            assert "unknown_field" in observed["error"]
            assert "Extra inputs are not permitted" in observed["error"]
        else:
            assert "datasetName" in observed["error"]
            assert "Extra inputs are not permitted" in observed["error"]


def test_callback_engine_and_noop_keep_distinct_nested_copy_contracts() -> None:
    """Raw callback identity is separate from deep-isolated public traversal."""
    from copy import deepcopy

    from polisyos.common.migrations import migrate_artifact
    from polisyos.fabric.identity.migrations import migrate_manifest_0_9_to_1_0

    raw = _complete_current_manifest()
    nested = raw["quality"]
    assert migrate_manifest_0_9_to_1_0(raw) is raw
    assert raw["quality"] is nested
    assert raw["schema_version"] == "0.9"
    source = _complete_current_manifest()
    before = deepcopy(source)
    converted = migrate_artifact(
        source,
        "dataset_manifest",
        "1.0",
        selected_edges={"0.9": ("1.0", migrate_manifest_0_9_to_1_0)},
    )
    assert source == before
    assert converted["quality"] is not source["quality"]
    converted["quality"]["coverage"]["region_coverage"] = "changed"
    assert source == before
    noop = migrate_artifact(converted, "dataset_manifest", "1.0")
    assert noop == converted
    assert noop is not converted
    assert noop["quality"] is not converted["quality"]


@pytest.mark.parametrize("order", ["legacy_first", "fabric_first"])
def test_bounded_callback_profiles_and_import_order_in_fresh_process(order: str) -> None:
    """Both explicit registration orders retain equivalent bounded callbacks."""
    code = r"""
import copy
import importlib
import sys
from polisyos.common.migrations import migrate_artifact
assert not any(name.startswith("polisyos.fabric") for name in sys.modules)
names = ["polisyos.common.migrations.manifest", "polisyos.fabric.identity.migrations"]
if sys.argv[1] == "fabric_first":
    names.reverse()
modules = {name: importlib.import_module(name) for name in names}
legacy = modules["polisyos.common.migrations.manifest"]
fabric = modules["polisyos.fabric.identity.migrations"]
assert legacy.MANIFEST_CURRENT_VERSION == fabric.MANIFEST_CURRENT_VERSION == "1.0"
fabric.register_manifest_migration()
corpus = [
    {"schema_version":"0.9", "datasetName":"baseline", "rawHash":"a"},
    {"schema_version":"0.9", "dataset_name":"baseline", "raw_hash":"a"},
    {"schema_version":"0.9", "datasetName":"baseline", "dataset_name":"baseline"},
    {"schema_version":"0.9", "datasetName":"baseline", "dataset_name":"other"},
    {"schema_version":"0.9", "unknown":{"nested":[1]}},
    {"schema_version":"0.9"},
]
for original in corpus:
    left, right = copy.deepcopy(original), copy.deepcopy(original)
    assert legacy.migrate_manifest_0_9_to_1_0(left) is left
    assert fabric.migrate_manifest_0_9_to_1_0(right) is right
    assert left == right
    assert left["schema_version"] == "0.9"
    before = copy.deepcopy(original)
    converted = migrate_artifact(original, "dataset_manifest", "1.0")
    assert original == before
    assert converted == {**right, "schema_version":"1.0"}
for callback in (legacy.migrate_manifest_0_9_to_1_0, fabric.migrate_manifest_0_9_to_1_0):
    try:
        callback(None)
    except TypeError:
        pass
    else:
        raise AssertionError("unsupported input no longer raises TypeError")
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code, order],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
