from __future__ import annotations

import ast
import importlib
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_DATA_FORGE_SHIM_IDS: set[str] = set()
DELETED_DATA_FORGE_SHIM_IDS = {
    "polisyos-academic-to-data-forge",
    "polisyos-datasets-to-data-forge",
    "polisyos-ukraine-data-to-data-forge",
    "polisyos-batch-common-to-data-forge-kernel",
    "polisyos-batch-snapshot-to-data-forge-kernel-snapshot",
    "polisyos-lex-batch-to-data-forge-legal",
}
DELETED_LEGACY_PACKAGE_DIRS = (
    REPO_ROOT / "src" / "polisyos" / "academic",
    REPO_ROOT / "src" / "polisyos" / "datasets",
    REPO_ROOT / "src" / "polisyos" / "ukraine_data",
    REPO_ROOT / "src" / "polisyos" / "batch_common",
    REPO_ROOT / "src" / "polisyos" / "batch_snapshot",
    REPO_ROOT / "src" / "polisyos" / "lex" / "batch",
    REPO_ROOT / "src" / "polisyos" / "lex" / "corpus",
)
REMOVED_EXCEPTION_IDS = {
    "E-2026-05-DATA-FORGE-LEGAL-BATCH-COMMON-001",
    "E-2026-04-LEX-BATCH-SCIENTIST-001",
    "E-2026-04-FABRIC-DATASETS-001",
    "E-2026-04-FOUNDRY-UKRAINE-DATA-001",
    "E-2026-04-DATASETS-ACADEMIC-001",
}
RELEASE_NOTES = REPO_ROOT / "docs" / "migration" / "data_forge_shim_sunset_release_notes.md"
ROLLBACK_NOTES = REPO_ROOT / "docs" / "migration" / "data_forge_shim_sunset_rollback.md"


def test_phase8_migrated_consumers_do_not_import_removed_shims() -> None:
    checks = {
        "src/polisyos/data_forge/domains/legal/batch": (
            "polisyos.batch_common",
            "polisyos.batch_snapshot",
        ),
        "tools/ops/cloud/run_lex_from_manifest.py": ("polisyos.batch_common",),
        "src/polisyos/lex": ("polisyos.lex.batch", "polisyos.lex.corpus"),
        "src/polisyos/fabric/retrieval/service.py": ("polisyos.datasets",),
        "src/polisyos/foundry/release_acceptance.py": ("polisyos.ukraine_data",),
        "tools/ops/ukraine_data/build_spending_contracts_procurement_proxy.py": (
            "polisyos.ukraine_data",
        ),
        "tools/ops/ukraine_data/build_edr_identity_seed_candidates.py": ("polisyos.ukraine_data",),
    }

    violations: list[str] = []
    for relative_path, blocked_prefixes in checks.items():
        for module_path in _python_files(REPO_ROOT / relative_path):
            for import_name in _direct_imports(module_path):
                if import_name.startswith(blocked_prefixes):
                    rel = module_path.relative_to(REPO_ROOT).as_posix()
                    violations.append(f"{rel}: {import_name}")

    assert violations == []


def test_phase8_obsolete_import_exceptions_are_removed() -> None:
    exception_ids = {
        item["id"]
        for item in tomllib.loads(
            (REPO_ROOT / "architecture" / "imports" / "exceptions.toml").read_text(encoding="utf-8")
        )["exception"]
    }
    registry_text = (REPO_ROOT / "architecture" / "imports" / "exceptions.md").read_text(
        encoding="utf-8"
    )

    assert REMOVED_EXCEPTION_IDS.isdisjoint(exception_ids)
    for exception_id in REMOVED_EXCEPTION_IDS:
        assert exception_id not in registry_text


def test_phase8_release_and_rollback_notes_cover_deleted_data_forge_shims() -> None:
    release_text = RELEASE_NOTES.read_text(encoding="utf-8")
    rollback_text = ROLLBACK_NOTES.read_text(encoding="utf-8")
    migration_shims = tomllib.loads(
        (REPO_ROOT / "architecture" / "shims.toml").read_text(encoding="utf-8")
    )
    shims = {item["id"]: item for item in migration_shims["shim"]}

    for shim_id in DELETED_DATA_FORGE_SHIM_IDS:
        assert shim_id in release_text
        assert shim_id not in shims

    for shim_id in ACTIVE_DATA_FORGE_SHIM_IDS:
        assert shim_id in release_text
        assert shim_id in shims
        assert shims[shim_id]["issue"].startswith(
            "docs/migration/data_forge_shim_sunset_release_notes.md#"
        )

    assert "Rollback Steps" in rollback_text
    assert "restore the removed shim directories from version control" in rollback_text
    for exception_id in REMOVED_EXCEPTION_IDS:
        assert exception_id in rollback_text


def test_phase8_complexity_exceptions_have_no_data_forge_legacy_god_files() -> None:
    complexity = tomllib.loads(
        (REPO_ROOT / "architecture" / "complexity_exceptions.toml").read_text(encoding="utf-8")
    )
    exception_paths = {item["path"] for item in complexity.get("exception", [])}
    old_data_forge_paths = {
        "src/polisyos/datasets/batch/core_sources_ingest.py",
        "src/polisyos/ukraine_data/builders.py",
    }

    assert old_data_forge_paths.isdisjoint(exception_paths)
    assert all("src/polisyos/lex/batch" not in path for path in exception_paths)
    assert all("src/polisyos/batch_common" not in path for path in exception_paths)
    assert all("src/polisyos/batch_snapshot" not in path for path in exception_paths)


def test_phase8_ukraine_console_entrypoint_targets_data_forge() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["scripts"]["ukraine-data"] == "polisyos.data_forge.domains.ukraine.cli:main"


def test_phase8_fabric_and_foundry_use_data_forge_read_api_only() -> None:
    violations = [
        *_imports_under(
            "src/polisyos/fabric",
            ("polisyos.data_forge.domains", "polisyos.data_forge.kernel"),
        ),
        *_imports_under(
            "src/polisyos/foundry",
            ("polisyos.data_forge.domains", "polisyos.data_forge.kernel"),
        ),
    ]

    assert violations == []


def test_phase8_external_live_consumers_are_migrated_to_data_forge() -> None:
    violations = [
        *_imports_under("src/polisyos/scientist", ("polisyos.academic", "polisyos.datasets")),
        *_text_refs_under(
            "src/polisyos/scientist",
            ("polisyos.academic", "polisyos.datasets", "polisyos.ukraine_data"),
        ),
        *_imports_under("src/polisyos/ir/analytics", ("polisyos.datasets",)),
        *_imports_under("src/polisyos/foundry", ("polisyos.academic",)),
        *_imports_under("tools/ops/cloud", ("polisyos.academic", "polisyos.datasets")),
        *_imports_under("tools/ops/ukraine_data", ("polisyos.lex.batch", "polisyos.lex.corpus")),
        *_imports_under(
            "tools/research/benchmarks/lex", ("polisyos.lex.batch", "polisyos.lex.corpus")
        ),
    ]

    assert violations == []


def test_phase8_ukraine_backtest_contract_fqn_is_data_forge_owned() -> None:
    from polisyos.data_forge.read_api.ukraine import REAL_BACKTEST_BUNDLE_CONTRACT_FQN

    assert REAL_BACKTEST_BUNDLE_CONTRACT_FQN.startswith("polisyos.data_forge.domains.ukraine.")
    module_name, attr_name = REAL_BACKTEST_BUNDLE_CONTRACT_FQN.rsplit(".", 1)

    assert getattr(importlib.import_module(module_name), attr_name).__name__ == attr_name


def test_phase8_data_forge_legacy_package_directories_are_removed() -> None:
    release_text = RELEASE_NOTES.read_text(encoding="utf-8")
    remaining = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in DELETED_LEGACY_PACKAGE_DIRS
        if path.exists()
    ]

    assert "physical removal complete" in release_text
    assert remaining == []


def test_phase8_canonical_domain_tests_do_not_import_legacy_shims() -> None:
    checks = {
        "tests/unit/data_forge/domains/academic": ("polisyos.academic",),
        "tests/unit/data_forge/domains/catalog": ("polisyos.datasets",),
        "tests/unit/data_forge/domains/ukraine": ("polisyos.ukraine_data",),
        "tests/unit/data_forge/legal_batch": ("polisyos.lex.batch", "polisyos.lex.corpus"),
    }
    shim_imports: list[str] = []

    for relative_root, blocked_prefixes in checks.items():
        for module_path in _python_files(REPO_ROOT / relative_root):
            for import_name in _direct_imports(module_path):
                if import_name.startswith(blocked_prefixes):
                    rel = module_path.relative_to(REPO_ROOT).as_posix()
                    shim_imports.append(f"{rel}: {import_name}")

    assert shim_imports == []


def _python_files(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        return (path,)
    return tuple(item for item in sorted(path.rglob("*.py")) if "__pycache__" not in item.parts)


def _direct_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return tuple(imports)


def _imports_under(relative_root: str, blocked_prefixes: tuple[str, ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for module_path in _python_files(REPO_ROOT / relative_root):
        for import_name in _direct_imports(module_path):
            if import_name.startswith(blocked_prefixes):
                rel = module_path.relative_to(REPO_ROOT).as_posix()
                matches.append(f"{rel}: {import_name}")
    return tuple(matches)


def _text_refs_under(relative_root: str, blocked_refs: tuple[str, ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for module_path in _python_files(REPO_ROOT / relative_root):
        text = module_path.read_text(encoding="utf-8")
        for blocked_ref in blocked_refs:
            if blocked_ref in text:
                rel = module_path.relative_to(REPO_ROOT).as_posix()
                matches.append(f"{rel}: {blocked_ref}")
    return tuple(matches)
