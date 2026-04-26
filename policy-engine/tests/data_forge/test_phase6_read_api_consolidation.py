from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from polisyos.data_forge import read_api

READ_API_MODULES = (
    "polisyos.data_forge.read_api",
    "polisyos.data_forge.read_api.academic",
    "polisyos.data_forge.read_api.catalog",
    "polisyos.data_forge.read_api.legal",
    "polisyos.data_forge.read_api.ukraine",
)
BLOCKED_IMPORT_PREFIXES = (
    "polisyos.academic",
    "polisyos.batch_common",
    "polisyos.batch_snapshot",
    "polisyos.data_forge.domains",
    "polisyos.data_forge.kernel",
    "polisyos.datasets",
    "polisyos.lex.batch",
    "polisyos.ukraine_data",
)


def test_read_api_surface_registry_is_runtime_safe() -> None:
    assert read_api.available_surfaces() == ("academic", "catalog", "legal", "ukraine")
    assert read_api.surface_module("academic") == "polisyos.data_forge.read_api.academic"
    assert read_api.get_surface("catalog").summary
    assert "surfaces" in read_api.__all__


def test_read_api_imports_do_not_load_domain_or_legacy_internals() -> None:
    for module_name in READ_API_MODULES:
        blocked = _blocked_modules_after_import(module_name)
        assert blocked == [], f"{module_name} loaded internal modules: {blocked}"


def test_read_api_modules_do_not_eagerly_import_domain_internals() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src" / "polisyos" / "data_forge"
    for module_path in sorted((src_root / "read_api").glob("*.py")):
        if module_path.name.startswith("_"):
            continue
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        eager_imports = [
            _import_name(node)
            for node in tree.body
            if isinstance(node, ast.Import | ast.ImportFrom)
            and _import_name(node).startswith(
                ("polisyos.data_forge.domains", "polisyos.data_forge.kernel")
            )
        ]
        assert eager_imports == [], f"{module_path} eagerly imports internals: {eager_imports}"


def test_explicit_surface_load_keeps_legacy_packages_out_of_runtime() -> None:
    script = """
        from polisyos.data_forge import read_api

        academic = read_api.load_surface("academic")
        getattr(academic, "load_academic_shadow_bundle")
        blocked = sorted(
            name
            for name in __import__("sys").modules
            if name.startswith((
                "polisyos.academic",
                "polisyos.batch_common",
                "polisyos.batch_snapshot",
                "polisyos.datasets",
                "polisyos.lex.batch",
                "polisyos.ukraine_data",
            ))
        )
        print(__import__("json").dumps(blocked))
        raise SystemExit(1 if blocked else 0)
    """
    result = _run_python(script)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def _blocked_modules_after_import(module_name: str) -> list[str]:
    script = f"""
        import importlib
        import json
        import sys

        importlib.import_module({module_name!r})
        blocked = sorted(
            name
            for name in sys.modules
            if name.startswith({BLOCKED_IMPORT_PREFIXES!r})
        )
        print(json.dumps(blocked))
        raise SystemExit(1 if blocked else 0)
    """
    result = _run_python(script)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _run_python(script: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        check=False,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )


def _import_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    return node.names[0].name
