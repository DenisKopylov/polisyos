from __future__ import annotations

import pytest

from polisyos.data_forge import __version__, read_api
from polisyos.data_forge.errors import DataForgeValidationError
from polisyos.data_forge.kernel.artifacts import (
    ArtifactRef,
    PIILevel,
    ProducerVersion,
    RetentionClass,
)
from polisyos.data_forge.kernel.pipeline import AssetKey, AssetSpec, asset, plan_asset_specs
from polisyos.data_forge.kernel.schemas import CompatibilityMode, SchemaRegistry, SchemaVersion
from polisyos.data_forge.kernel.snapshot import SnapshotTransaction, merkle_root
from polisyos.data_forge.kernel.snapshot.transactions import SnapshotTransactionStatus
from polisyos.data_forge.kernel.testing import capture_golden_file, verify_golden_file


def _artifact_ref(uri: str, sha256: str) -> ArtifactRef:
    return ArtifactRef(
        uri=uri,
        sha256=sha256,
        producer="tests.data_forge.phase0a",
        producer_version=ProducerVersion(code_version="0.1.0", lockfile_hash="c" * 64),
        trace_id="1" * 32,
        span_id="2" * 16,
        config_hash="d" * 64,
        owner="team-data-forge",
        license="test-fixture",
        pii_level=PIILevel.NONE,
        retention_class=RetentionClass.HOT,
        freshness_sla_seconds=3600,
        schema_id="test.schema",
        schema_version="1.0.0",
    )


def test_public_surface_imports_runtime_safe_read_api_modules() -> None:
    assert __version__
    assert set(read_api.available_surfaces()) == {"academic", "catalog", "legal", "ukraine"}
    assert {"academic", "catalog", "legal", "surfaces", "ukraine"}.issubset(read_api.__all__)


def test_asset_decorator_and_planner_return_dependency_order() -> None:
    raw = AssetSpec(
        key=AssetKey.from_parts("academic", "works", "raw"),
        owner="team-data-forge",
    )
    normalized_key = AssetKey.from_parts("academic", "works", "normalized")
    normalized = AssetSpec(
        key=normalized_key,
        deps=(raw.key,),
        schema_id="academic.works.normalized",
        owner="team-data-forge",
    )

    @asset(key=normalized_key, deps=(raw.key,), owner="team-data-forge")
    def build_normalized() -> list[str]:
        return ["ok"]

    definition = build_normalized.__data_forge_asset__
    assert definition.spec.key == normalized_key
    assert plan_asset_specs((normalized, raw)) == (raw, normalized)


def test_planner_rejects_missing_dependencies_and_cycles() -> None:
    first = AssetKey.from_parts("catalog", "first")
    second = AssetKey.from_parts("catalog", "second")
    missing = AssetSpec(key=first, deps=(second,), owner="team-data-forge")

    with pytest.raises(DataForgeValidationError):
        plan_asset_specs((missing,))

    cyclic_a = AssetSpec(key=first, deps=(second,), owner="team-data-forge")
    cyclic_b = AssetSpec(key=second, deps=(first,), owner="team-data-forge")

    with pytest.raises(DataForgeValidationError):
        plan_asset_specs((cyclic_a, cyclic_b))


def test_artifact_refs_build_deterministic_snapshot_transactions() -> None:
    first = _artifact_ref("polisyos://academic/skg@snap-1", "a" * 64)
    second = _artifact_ref("polisyos://catalog/index@snap-1", "b" * 64)

    assert merkle_root((first, second)) == merkle_root((second, first))

    transaction = SnapshotTransaction(
        snapshot_id="snap-1",
        asset_group="phase0a",
        artifacts=(first, second),
    ).commit()

    assert transaction.status == SnapshotTransactionStatus.COMMITTED
    assert transaction.merkle_root == merkle_root((first, second))


def test_schema_registry_registers_versions_and_rejects_duplicates() -> None:
    registry = SchemaRegistry()
    v1 = registry.register(
        SchemaVersion(
            schema_id="legal.spo",
            version="1.0.0",
            compat_mode=CompatibilityMode.BACKWARD,
            json_schema={"type": "object"},
        )
    )
    v2 = registry.register(
        SchemaVersion(
            schema_id="legal.spo",
            version="1.1.0",
            compat_mode=CompatibilityMode.FULL,
            json_schema={"type": "object"},
        )
    )

    assert registry.get("legal.spo", "1.0.0") == v1
    assert registry.latest("legal.spo") == v2
    assert registry.list_versions("legal.spo") == (v1, v2)

    with pytest.raises(DataForgeValidationError):
        registry.register(v1)


def test_golden_harness_captures_and_verifies_files(tmp_path) -> None:
    artifact_path = tmp_path / "tiny.json"
    artifact_path.write_text('{"ok": true}\n', encoding="utf-8")

    golden = capture_golden_file(tmp_path, "tiny.json", name="tiny")
    assert verify_golden_file(tmp_path, golden)

    artifact_path.write_text('{"ok": false}\n', encoding="utf-8")
    assert not verify_golden_file(tmp_path, golden)
