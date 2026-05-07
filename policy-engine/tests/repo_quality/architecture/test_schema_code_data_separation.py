from __future__ import annotations

import re
from pathlib import Path

from polisyos.schemas.abi_models import ABI_MODELS

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_ROOT = REPO_ROOT / "schemas"
PYTHON_IMPORT_ROOTS = (
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
)
LEGACY_IMPORT_RE = re.compile(r"(?m)^\s*(?:from\s+schemas(?:\.|\s+import)|import\s+schemas(?:\.|\s|$))")


def test_top_level_schemas_is_not_a_python_package() -> None:
    offenders: list[str] = []

    if (SCHEMAS_ROOT / "__init__.py").exists():
        offenders.append("schemas/__init__.py")

    for path in sorted(SCHEMAS_ROOT.rglob("*")):
        if path.name == "__pycache__" or path.suffix in {".py", ".pyc"}:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


def test_schema_registry_imports_use_polisyos_namespace() -> None:
    assert len(ABI_MODELS) > 0

    offenders: list[str] = []
    for root in PYTHON_IMPORT_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            content = path.read_text(encoding="utf-8")
            if LEGACY_IMPORT_RE.search(content):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []
