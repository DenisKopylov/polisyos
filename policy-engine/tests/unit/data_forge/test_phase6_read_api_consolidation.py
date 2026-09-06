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
RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "src" / "polisyos" / "runtime"
BLOCKED_IMPORT_PREFIXES = (
    "polisyos.academic",
    "polisyos.batch_common",
    "polisyos.batch_snapshot",
    "polisyos.data_forge.domains",
    "polisyos.data_forge.kernel",
    "polisyos.datasets",
    "polisyos.lex",
    "polisyos.ukraine_data",
)
RUNTIME_BLOCKED_INTERNAL_PREFIXES = (
    "polisyos.data_forge.domains",
    "polisyos.data_forge.kernel",
)
RUNTIME_BLOCKED_LEGACY_READ_PREFIXES = (
    "polisyos.data_forge.domains.academic.knowledge",
    "polisyos.data_forge.domains.catalog.knowledge",
    "polisyos.lex.knowledge",
    "polisyos.ukraine_data",
)
RUNTIME_BLOCKED_SOURCE_FRAGMENTS = (
    "polisyos.data_forge.domains",
    "polisyos.data_forge.kernel",
    "polisyos.data_forge.domains.academic.knowledge",
    "polisyos.data_forge.domains.catalog.knowledge",
    "polisyos.lex.knowledge",
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


def test_academic_claim_vocabulary_exports_are_lazy_and_discoverable() -> None:
    from polisyos.data_forge.read_api import academic

    expected = {
        "CausalClaimResultV1",
        "CausalClaimResultV2",
        "ClaimLineageAuditPage",
        "ClaimVocabularyProjectionBinding",
        "audit_academic_claim_lineage",
        "iter_causal_claim_results_v2",
    }

    assert expected <= set(academic.__all__)
    assert expected <= set(dir(academic))
    assert academic.CausalClaimResult is academic.CausalClaimResultV2


def test_read_api_modules_do_not_eagerly_import_domain_internals() -> None:
    src_root = Path(__file__).resolve().parents[3] / "src" / "polisyos" / "data_forge"
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
                "polisyos.lex",
                "polisyos.ukraine_data",
            ))
        )
        print(__import__("json").dumps(blocked))
        raise SystemExit(1 if blocked else 0)
    """
    result = _run_python(script)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_legal_read_api_searches_graph_without_legacy_lex_imports(tmp_path: Path) -> None:
    import duckdb

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE lex_facts (
                fact_id VARCHAR,
                subject_en VARCHAR,
                predicate VARCHAR,
                object_en VARCHAR,
                fact_text VARCHAR,
                confidence DOUBLE,
                norm_type VARCHAR,
                condition_text_uk VARCHAR,
                exception_text_uk VARCHAR,
                source_quote_uk VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_citation VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_facts VALUES (
                'fact::1',
                'municipality',
                'may_use',
                'procurement',
                'Municipality may use electronic procurement.',
                0.91,
                'permission',
                '',
                '',
                'electronic procurement quote',
                'Public Procurement Act',
                '1234',
                'Article 1'
            )
            """
        )
    finally:
        con.close()

    script = f"""
        import json
        import sys
        from polisyos.data_forge.read_api.legal import search_legal_knowledge_graph

        results = search_legal_knowledge_graph(
            output_dir={str(tmp_path)!r},
            query="procurement",
            top_k=5,
        )
        blocked = sorted(
            name
            for name in sys.modules
            if name.startswith((
                "polisyos.data_forge.domains",
                "polisyos.data_forge.kernel",
                "polisyos.lex",
            ))
        )
        payload = {{
            "blocked": blocked,
            "results": [
                {{
                    "fact_id": item.fact_id,
                    "subject_name": item.subject_name,
                    "object_name": item.object_name,
                    "confidence": item.confidence,
                    "doc_name": item.doc_name,
                    "provision_citation": item.provision_citation,
                }}
                for item in results
            ],
        }}
        print(json.dumps(payload, sort_keys=True))
        raise SystemExit(1 if blocked else 0)
    """
    result = _run_python(script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["blocked"] == []
    assert payload["results"] == [
        {
            "fact_id": "fact::1",
            "subject_name": "municipality",
            "object_name": "procurement",
            "confidence": 0.91,
            "doc_name": "Public Procurement Act",
            "provision_citation": "Article 1",
        }
    ]


def test_runtime_consumers_do_not_import_data_forge_internals_directly() -> None:
    violations = _direct_import_violations(RUNTIME_ROOT, RUNTIME_BLOCKED_INTERNAL_PREFIXES)

    assert violations == [], (
        "runtime packages must depend on polisyos.data_forge.read_api.* rather than "
        "Data Forge domain/kernel internals:\n" + "\n".join(violations)
    )


def test_runtime_consumers_do_not_import_legacy_read_facades_directly() -> None:
    violations = _direct_import_violations(RUNTIME_ROOT, RUNTIME_BLOCKED_LEGACY_READ_PREFIXES)

    assert violations == [], (
        "runtime packages must migrate read consumers to polisyos.data_forge.read_api.* "
        "and keep legacy facades behind shims:\n" + "\n".join(violations)
    )


def test_runtime_sources_do_not_reference_blocked_read_internals_dynamically() -> None:
    violations: list[str] = []
    repo_root = Path(__file__).resolve().parents[3]

    for path in sorted(
        item for item in RUNTIME_ROOT.rglob("*.py") if "__pycache__" not in item.parts
    ):
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(repo_root).as_posix()
        for fragment in RUNTIME_BLOCKED_SOURCE_FRAGMENTS:
            if fragment in text:
                violations.append(f"{relative_path}: {fragment}")

    assert violations == [], (
        "runtime packages must not smuggle Data Forge internals or legacy read "
        "facades through dynamic imports/string references:\n" + "\n".join(violations)
    )


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
    repo_root = Path(__file__).resolve().parents[3]
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


def _direct_import_violations(root: Path, blocked_prefixes: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in sorted(item for item in root.rglob("*.py") if "__pycache__" not in item.parts):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_path = path.relative_to(Path(__file__).resolve().parents[3]).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            for module_name in _import_names(node):
                if any(
                    module_name == prefix or module_name.startswith(f"{prefix}.")
                    for prefix in blocked_prefixes
                ):
                    violations.append(f"{relative_path}:{node.lineno}: {module_name}")
    return violations


def _import_names(node: ast.Import | ast.ImportFrom) -> tuple[str, ...]:
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return tuple(alias.name for alias in node.names)
