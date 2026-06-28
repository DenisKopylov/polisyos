from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
QUALITY_ROOT = REPO_ROOT / "src" / "polisyos" / "runtime" / "quality"
PYTHON_SCAN_ROOTS = (
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
)

PROVENANCE_FILENAME = re.compile(r"^(gy_|layer2_|layer3_|wave|pass|slice)")
OLD_RUNTIME_QUALITY_MODULE_PREFIXES = (
    "polisyos.runtime.quality.gy_",
    "polisyos.runtime.quality.layer2_",
    "polisyos.runtime.quality.layer3_",
    "polisyos.runtime.quality.wave2_walking_skeleton",
    "polisyos.runtime.quality.pass1b_hardening",
    "polisyos.runtime.quality.producer_pipeline_corpus_stub",
    "polisyos.runtime.quality.legacy_migration_sandbox",
)
OLD_RUNTIME_QUALITY_IMPORT_NAMES = (
    "gy_",
    "layer2_",
    "layer3_",
    "wave2_walking_skeleton",
    "pass1b_hardening",
    "producer_pipeline_corpus_stub",
    "legacy_migration_sandbox",
)


def test_runtime_quality_python_filenames_use_owner_names() -> None:
    offenders = sorted(
        _rel(path)
        for path in QUALITY_ROOT.rglob("*.py")
        if PROVENANCE_FILENAME.match(path.name)
    )

    assert offenders == []


def test_runtime_quality_old_provenance_import_paths_are_retired() -> None:
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _old_module_path(alias.name):
                        offenders.append(f"{_rel(path)}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if _old_module_path(module):
                    offenders.append(f"{_rel(path)}:{node.lineno}: from {module} import ...")
                if module == "polisyos.runtime.quality":
                    for alias in node.names:
                        if _old_import_name(alias.name):
                            offenders.append(
                                f"{_rel(path)}:{node.lineno}: "
                                f"from polisyos.runtime.quality import {alias.name}"
                            )

    assert sorted(offenders) == []


def _python_files() -> list[Path]:
    return sorted(
        path
        for root in PYTHON_SCAN_ROOTS
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _old_module_path(module: str) -> bool:
    return any(module.startswith(prefix) for prefix in OLD_RUNTIME_QUALITY_MODULE_PREFIXES)


def _old_import_name(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in OLD_RUNTIME_QUALITY_IMPORT_NAMES)


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()
