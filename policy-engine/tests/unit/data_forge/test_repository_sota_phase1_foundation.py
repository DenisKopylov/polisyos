from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import polisyos.data_forge as data_forge
import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCHITECTURE_ROOT = REPO_ROOT / "architecture"
SOURCE_ROOT = REPO_ROOT / "src" / "polisyos"
RUNTIME_CONSUMER_PACKAGES = (
    "ir",
    "runtime",
    "fabric",
    "foundry",
    "lex",
    "scientist",
    "scholar",
    "berl",
    "calibration",
    "ddm",
)
READ_API_IGNORE_IMPORTS = (
    "polisyos.data_forge.read_api",
    "polisyos.data_forge.read_api.*",
)


def test_data_forge_public_facade_exports_phase1_foundation_contracts() -> None:
    expected_exports = {
        "ArtifactRef",
        "AssetDefinition",
        "AssetGroup",
        "AssetKey",
        "AssetSpec",
        "CompatibilityMode",
        "DifferentialComparison",
        "GoldenArtifact",
        "GoldenCase",
        "MaterializationContext",
        "PIILevel",
        "ProducerVersion",
        "QCCheck",
        "QCReport",
        "RetentionClass",
        "SchemaRegistry",
        "SchemaVersion",
        "SnapshotTransaction",
        "SnapshotTransactionStatus",
        "asset",
        "capture_golden_file",
        "compare_file_sha256",
        "compare_json_files",
        "evaluate_fail_fast",
        "merkle_root",
        "plan_asset_specs",
        "read_api",
        "verify_golden_file",
    }

    assert expected_exports <= set(data_forge.__all__)
    assert data_forge.ArtifactRef.__name__ == "ArtifactRef"
    assert data_forge.SchemaRegistry.__name__ == "SchemaRegistry"
    assert data_forge.SnapshotTransaction.__name__ == "SnapshotTransaction"
    assert set(data_forge.read_api.available_surfaces()) == {
        "academic",
        "catalog",
        "legal",
        "ukraine",
    }


def test_read_api_import_does_not_load_kernel_or_domain_internals() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        (
            str(REPO_ROOT / "src"),
            str(REPO_ROOT),
            env.get("PYTHONPATH", ""),
        )
    )
    code = """
import json
import sys

import polisyos.data_forge.read_api as read_api

read_api.available_surfaces()
blocked = sorted(
    name
    for name in sys.modules
    if name.startswith("polisyos.data_forge.kernel")
    or name.startswith("polisyos.data_forge.domains")
)
print(json.dumps(blocked))
raise SystemExit(1 if blocked else 0)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_artifact_ref_requires_reproducibility_governance_metadata() -> None:
    artifact = _artifact_ref()
    payload = artifact.model_dump(mode="json")
    model_required = set(data_forge.ArtifactRef.model_json_schema()["required"])
    schema = json.loads(
        (REPO_ROOT / "schemas" / "artifacts" / "data_forge_artifact_ref_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    required_governance = {
        "owner",
        "producer_version",
        "schema_id",
        "schema_version",
        "freshness_sla_seconds",
        "retention_class",
        "pii_level",
        "license",
        "regeneration_command",
    }

    assert required_governance <= model_required
    assert required_governance <= set(schema["required"])
    assert payload["regeneration_command"].startswith("uv run pytest")

    payload_without_regeneration_command = dict(payload)
    payload_without_regeneration_command.pop("regeneration_command")
    with pytest.raises(ValidationError):
        data_forge.ArtifactRef.model_validate(payload_without_regeneration_command)


def test_schema_snapshot_quality_and_migration_baselines_use_public_facade(
    tmp_path: Path,
) -> None:
    registry = data_forge.SchemaRegistry()
    v1 = registry.register(
        data_forge.SchemaVersion(
            schema_id="repository_sota.phase1",
            version="1.0.0",
            compat_mode=data_forge.CompatibilityMode.BACKWARD,
            json_schema={"type": "object"},
        )
    )
    assert registry.get("repository_sota.phase1", "1.0.0") == v1
    assert registry.latest("repository_sota.phase1") == v1

    artifact = _artifact_ref()
    transaction = data_forge.SnapshotTransaction(
        snapshot_id=artifact.snapshot_id,
        asset_group="repository_sota",
        artifacts=(artifact,),
    ).commit()
    assert transaction.status == data_forge.SnapshotTransactionStatus.COMMITTED
    assert transaction.merkle_root == data_forge.merkle_root((artifact,))

    report = data_forge.QCReport(
        scope="repository_sota.phase1",
        checks=(data_forge.QCCheck(name="artifact_identity", passed=True),),
    )
    data_forge.evaluate_fail_fast(report, fail_fast=True)

    expected = tmp_path / "expected.json"
    observed = tmp_path / "observed.json"
    expected.write_text('{"generated_at": "old", "ok": true}\n', encoding="utf-8")
    observed.write_text('{"generated_at": "new", "ok": true}\n', encoding="utf-8")

    golden = data_forge.capture_golden_file(tmp_path, "expected.json", name="phase1")
    comparison = data_forge.compare_json_files(
        expected,
        observed,
        ignored_top_level_keys=("generated_at",),
        name="phase1",
    )

    assert data_forge.verify_golden_file(tmp_path, golden)
    assert comparison.passed is True


def test_runtime_consumers_are_bound_to_data_forge_read_api() -> None:
    import_contracts = tomllib.loads(
        (ARCHITECTURE_ROOT / "imports" / "contracts.toml").read_text(encoding="utf-8")
    )
    package_boundaries = tomllib.loads(
        (ARCHITECTURE_ROOT / "packages" / "boundaries.toml").read_text(encoding="utf-8")
    )
    contract = _contract_by_name(
        import_contracts,
        "Runtime and Fabric consumers use Data Forge only through read_api",
    )
    public_surface = tomllib.loads(
        (ARCHITECTURE_ROOT / "public_surface" / "contract.toml").read_text(encoding="utf-8")
    )
    package_by_module = {item["module"]: item for item in package_boundaries["package"]}
    public_surface_by_module = {item["module"]: item for item in public_surface["package"]}

    assert {
        "polisyos.data_forge",
        "polisyos.data_forge.kernel",
        "polisyos.data_forge.domains",
    } <= set(contract["forbidden_modules"])
    assert set(contract["ignore_imports"]) == set(READ_API_IGNORE_IMPORTS)
    assert package_by_module["polisyos.data_forge"]["runtime_allowed_submodules"] == [
        "polisyos.data_forge.read_api"
    ]
    assert public_surface_by_module["polisyos.data_forge"]["facade_mode"] == "lazy_facade"

    assert _data_forge_runtime_import_violations() == []


def _artifact_ref() -> data_forge.ArtifactRef:
    return data_forge.ArtifactRef(
        uri="polisyos://academic/skg@snap-1",
        sha256="a" * 64,
        producer="tests.unit.data_forge.repository_sota_phase1",
        producer_version=data_forge.ProducerVersion(
            code_version="0.1.0",
            lockfile_hash="b" * 64,
        ),
        trace_id="1" * 32,
        span_id="2" * 16,
        config_hash="c" * 64,
        owner="team-data-forge",
        license="test-fixture",
        regeneration_command=(
            "uv run pytest tests/unit/data_forge/test_repository_sota_phase1_foundation.py"
        ),
        pii_level=data_forge.PIILevel.NONE,
        retention_class=data_forge.RetentionClass.HOT,
        freshness_sla_seconds=3600,
        schema_id="repository_sota.phase1",
        schema_version="1.0.0",
    )


def _contract_by_name(payload: dict[str, object], name: str) -> dict[str, object]:
    for contract in payload["importlinter"]["contracts"]:
        if contract["name"] == name:
            return contract
    raise AssertionError(f"missing import contract: {name}")


def _data_forge_runtime_import_violations() -> list[str]:
    violations: list[str] = []
    for package in RUNTIME_CONSUMER_PACKAGES:
        root = SOURCE_ROOT / package
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*.py") if "__pycache__" not in item.parts):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                for target in _absolute_import_targets(node):
                    if _is_forbidden_data_forge_runtime_import(target):
                        violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {target}")
    return violations


def _absolute_import_targets(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(str(alias.name) for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        module = str(node.module or "")
        if module == "polisyos":
            return tuple(f"polisyos.{alias.name}" for alias in node.names)
        return (module,) if module else ()
    return ()


def _is_forbidden_data_forge_runtime_import(target: str) -> bool:
    if target == "polisyos.data_forge" or target.startswith("polisyos.data_forge."):
        return not (
            target == "polisyos.data_forge.read_api"
            or target.startswith("polisyos.data_forge.read_api.")
        )
    return False
