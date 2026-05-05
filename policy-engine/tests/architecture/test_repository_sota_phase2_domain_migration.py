from __future__ import annotations

import ast
import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE_ROOT = REPO_ROOT / "architecture"
REQUIRED_BATCH_IDS = {
    "academic-to-data-forge",
    "catalog-to-data-forge",
    "foundry-public-facade",
    "legal-offline-to-data-forge",
    "lex-runtime-public-facade",
    "scholar-public-facade",
    "scientist-public-facade",
    "shared-batch-to-data-forge-kernel",
    "ukraine-to-data-forge",
}
RETIRED_IMPORT_PREFIXES = (
    "polisyos.academic",
    "polisyos.batch_common",
    "polisyos.batch_snapshot",
    "polisyos.datasets",
    "polisyos.lex.batch",
    "polisyos.lex.corpus",
    "polisyos.ukraine_data",
)
DATA_FORGE_INTERNAL_PREFIXES = (
    "polisyos.data_forge.domains",
    "polisyos.data_forge.kernel",
)
LEGACY_DOMAIN_TEST_ROOTS = (
    "tests/academic",
    "tests/datasets",
    "tests/ukraine_data",
)
TARGET_DOMAIN_TEST_ROOTS = (
    "tests/unit/data_forge/domains/academic",
    "tests/unit/data_forge/domains/catalog",
    "tests/unit/data_forge/domains/ukraine",
    "tests/unit/data_forge/legal_batch",
)
REMOVED_SOURCE_STATUSES = {"removed_after_shim_sunset"}


def test_phase2_domain_migration_batches_are_complete_and_evidenced() -> None:
    payload = _domain_migration_batches()
    batches = {item["id"]: item for item in payload["batch"]}

    assert set(batches) >= REQUIRED_BATCH_IDS
    assert payload["domain_migration_batches"]["status"] == "active"

    for batch in batches.values():
        assert batch["owner"]
        assert batch["risk_class"] in {"L", "M", "H"}
        assert batch["source_paths"]
        assert batch["target_paths"]
        assert batch["public_facades"]
        assert batch["evidence_paths"]
        assert batch["acceptance_tests"]
        assert batch["removal_criteria"]

        for target in batch["target_paths"]:
            assert (REPO_ROOT / target).exists(), f"{batch['id']} target missing: {target}"
        for evidence in batch["evidence_paths"]:
            assert (REPO_ROOT / evidence).exists(), f"{batch['id']} evidence missing: {evidence}"
        for test_path in batch["acceptance_tests"]:
            assert (REPO_ROOT / test_path).exists(), f"{batch['id']} test missing: {test_path}"

        if batch["compatibility_status"] in REMOVED_SOURCE_STATUSES:
            for source in batch["source_paths"]:
                assert not (REPO_ROOT / source).exists(), (
                    f"{batch['id']} retired source still exists: {source}"
                )


def test_phase2_domain_migration_schema_contract_is_registered() -> None:
    payload = _domain_migration_batches()
    schema = json.loads(
        (REPO_ROOT / "schemas" / "topology" / "domain_migration_batches.schema.json").read_text(
            encoding="utf-8"
        )
    )
    required_top_level = set(schema["required"])
    required_batch_fields = set(schema["properties"]["batch"]["items"]["required"])

    assert required_top_level == {"domain_migration_batches", "batch"}
    assert required_batch_fields <= set(payload["batch"][0])
    assert schema["$id"] == "polisyos://schemas/topology/domain_migration_batches.schema.json"


def test_phase2_active_migration_shims_have_required_metadata() -> None:
    migration_shims = tomllib.loads((ARCHITECTURE_ROOT / "shims.toml").read_text(encoding="utf-8"))

    for shim in migration_shims["shim"]:
        assert shim["id"]
        assert shim["source_path"]
        assert shim["target_path"]
        assert shim["owner"]
        assert shim["reason"]
        assert shim["sunset_date"]
        assert shim["issue"]

    shims_by_id = {shim["id"]: shim for shim in migration_shims["shim"]}
    for batch in _domain_migration_batches()["batch"]:
        for shim_id in batch["shim_ids"]:
            assert shim_id in shims_by_id, f"{batch['id']} references unknown shim {shim_id}"


def test_phase2_retired_domain_imports_are_absent_from_source_tools_and_tests() -> None:
    violations: list[str] = []
    for base in (REPO_ROOT / "src", REPO_ROOT / "tools", REPO_ROOT / "tests"):
        for path in _python_files(base):
            for import_name in _direct_imports(path):
                if import_name.startswith(RETIRED_IMPORT_PREFIXES):
                    relative_path = path.relative_to(REPO_ROOT).as_posix()
                    violations.append(f"{relative_path}: {import_name}")

    assert violations == []


def test_phase2_runtime_consumers_use_data_forge_read_api_not_internals() -> None:
    violations: list[str] = []
    for path in _python_files(REPO_ROOT / "src" / "polisyos"):
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        if relative_path.startswith("src/polisyos/data_forge/"):
            continue

        for import_name in _direct_imports(path):
            if import_name.startswith(DATA_FORGE_INTERNAL_PREFIXES):
                violations.append(f"{relative_path}: {import_name}")

    assert violations == []


def test_phase2_domain_regression_tests_mirror_target_topology() -> None:
    for relative_root in LEGACY_DOMAIN_TEST_ROOTS:
        assert not _python_files(REPO_ROOT / relative_root), relative_root

    for relative_root in TARGET_DOMAIN_TEST_ROOTS:
        assert _python_files(REPO_ROOT / relative_root), relative_root


def test_phase2_production_entrypoints_target_new_facades() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    cloud_runner = (REPO_ROOT / "tools" / "ops" / "cloud" / "run_lex_from_manifest.py").read_text(
        encoding="utf-8"
    )
    runtime_control = (
        REPO_ROOT / "src" / "polisyos" / "runtime" / "http" / "services" / "control.py"
    ).read_text(encoding="utf-8")

    assert project["scripts"]["ukraine-data"] == "polisyos.data_forge.domains.ukraine.cli:main"
    assert "polisyos.data_forge.domains.legal.batch" in cloud_runner
    assert "polisyos.lex.batch" not in cloud_runner
    assert "from polisyos.data_forge.read_api.legal" in runtime_control
    assert "from polisyos.lex.batch" not in runtime_control


def _domain_migration_batches() -> dict[str, object]:
    return tomllib.loads(
        (ARCHITECTURE_ROOT / "domain_migration_batches.toml").read_text(encoding="utf-8")
    )


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(item for item in sorted(root.rglob("*.py")) if "__pycache__" not in item.parts)


def _direct_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append(node.module)
    return tuple(imports)
