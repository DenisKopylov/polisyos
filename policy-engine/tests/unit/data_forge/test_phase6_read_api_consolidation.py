from __future__ import annotations

import ast
import importlib
import json
import os
import subprocess
import sys
import textwrap
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

from polisyos.data_forge import read_api
from tools.quality.validation import decomposition_preflight as preflight

READ_API_MODULES = (
    "polisyos.data_forge.read_api",
    "polisyos.data_forge.read_api.academic",
    "polisyos.data_forge.read_api.catalog",
    "polisyos.data_forge.read_api.legal",
    "polisyos.data_forge.read_api.ukraine",
)
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / "src" / "polisyos" / "runtime"
PUBLIC_SURFACE_CONTRACT = REPO_ROOT / "architecture" / "public_surface" / "contract.toml"
IMPORT_CONTRACT = REPO_ROOT / "architecture" / "imports" / "contracts.toml"
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
    violations = _data_forge_import_violations(RUNTIME_ROOT)

    assert violations == [], (
        "runtime packages must depend on polisyos.data_forge.read_api.* rather than "
        "Data Forge domain/kernel internals:\n" + "\n".join(violations)
    )


def test_runtime_import_gate_rejects_internal_bypass_and_accepts_public_facade(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        "from polisyos.data_forge.kernel.snapshot import finalize_snapshot\n",
        encoding="utf-8",
    )

    violations = _data_forge_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.kernel.snapshot" in violations[0]

    consumer.write_text(
        "from polisyos.data_forge.read_api import finalize_snapshot\n",
        encoding="utf-8",
    )

    assert _data_forge_import_violations(runtime_root) == []

    consumer.write_text(
        "import polisyos.data_forge as data_forge\ncatalog_api = data_forge.read_api.catalog\n",
        encoding="utf-8",
    )
    assert _data_forge_import_violations(runtime_root) == []

    consumer.write_text(
        "import polisyos.data_forge as data_forge\nsnapshot_api = data_forge.kernel.snapshot\n",
        encoding="utf-8",
    )
    violations = _data_forge_import_violations(runtime_root)
    assert len(violations) == 1
    assert "polisyos.data_forge" in violations[0]


def test_runtime_import_gate_validates_the_full_data_forge_public_path(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        textwrap.dedent(
            """
        import polisyos.data_forge as data_forge

        api = data_forge.read_api
        query_type = api.academic.SKGQuery
        catalog_api = data_forge.read_api.catalog
        """
        ),
        encoding="utf-8",
    )

    assert _data_forge_import_violations(runtime_root) == []

    consumer.write_text(
        textwrap.dedent(
            """
        import polisyos.data_forge as data_forge

        api = data_forge.read_api
        target_registry = api._EXPORTS
        """
        ),
        encoding="utf-8",
    )

    violations = _data_forge_import_violations(runtime_root)

    assert len(violations) == 1
    assert "consumer.py" in violations[0]
    assert "_EXPORTS" in violations[0]


def test_runtime_consumers_do_not_import_legacy_read_facades_directly() -> None:
    violations = _lex_private_import_violations(RUNTIME_ROOT)

    assert violations == [], (
        "runtime consumers may use an exact declared Lex facade entrypoint, but not "
        "unlisted Lex knowledge implementation modules:\n" + "\n".join(violations)
    )


def test_runtime_sources_do_not_reference_blocked_read_internals_dynamically() -> None:
    violations = _runtime_dynamic_import_violations(RUNTIME_ROOT)

    assert violations == [], (
        "runtime dynamic import targets must satisfy the import contracts and exact "
        "public facade routes; provenance strings alone are not imports:\n" + "\n".join(violations)
    )


def test_lex_route_gate_accepts_only_exact_public_knowledge_entrypoint(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "public.py").write_text(
        "from polisyos.lex.knowledge import LegalQueryProfile\n",
        encoding="utf-8",
    )
    private = runtime_root / "private.py"
    private.write_text(
        "from polisyos.lex.knowledge.store import LegalKnowledgeStore\n",
        encoding="utf-8",
    )

    violations = _lex_private_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.lex.knowledge.store" in violations[0]
    private.write_text(
        "source_ref = 'polisyos.lex.knowledge.store:LegalKnowledgeStore'\n",
        encoding="utf-8",
    )
    assert _lex_private_import_violations(runtime_root) == []


def test_dynamic_import_gate_resolves_aliases_and_ignores_provenance_strings(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        textwrap.dedent(
            """
        from importlib import import_module as load_module

        TARGET = "polisyos.data_forge." + "domains.ukraine.manifests"
        source_ref = "polisyos.data_forge.domains.ukraine.manifests:ReleaseManifest"
        load_module(TARGET)
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.domains.ukraine.manifests" in violations[0]
    consumer.write_text(
        "source_ref = 'polisyos.data_forge.domains.ukraine.manifests:ReleaseManifest'\n",
        encoding="utf-8",
    )
    assert _runtime_dynamic_import_violations(runtime_root) == []


@pytest.mark.parametrize(
    "source",
    [
        'import builtins\nbuiltins.__import__("polisyos.data_forge.kernel.snapshot")',
        'import importlib\ngetattr(importlib, "import_module")("polisyos.data_forge.kernel.snapshot")',
        'import importlib\nreflect = getattr\nreflect(importlib, "import_module")("polisyos.data_forge.kernel.snapshot")',
        '__builtins__.__import__("polisyos.data_forge.kernel.snapshot")',
        '__builtins__["__import__"]("polisyos.data_forge.kernel.snapshot")',
        'import builtins\nvars(builtins)["__import__"]("polisyos.data_forge.kernel.snapshot")',
        'import importlib\nglobals()["importlib"].import_module("polisyos.data_forge.kernel.snapshot")',
        'import importlib\nglobals().get("importlib").import_module("polisyos.data_forge.kernel.snapshot")',
        'import sys\nsys.modules["importlib"].import_module("polisyos.data_forge.kernel.snapshot")',
        'import builtins\ngetattr(builtins, supplied_name)("polisyos.data_forge.kernel.snapshot")',
        'import builtins\nname = supplied_name\nvars(builtins).get(name)("polisyos.data_forge.kernel.snapshot")',
        "import importlib\nconsume(importlib.import_module)",
        "exec(\"importlib.import_module(\\'polisyos.data_forge.kernel.snapshot\\')\")",
    ],
)
def test_dynamic_import_gate_rejects_complete_reflection_falsifier_matrix(
    source: str,
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "consumer.py").write_text(source, encoding="utf-8")

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert violations, "a source-visible importer path or capability escape was treated as clean"


def test_dynamic_import_gate_rejects_unresolved_targets_from_data_forge_facade(
    tmp_path: Path,
) -> None:
    actual_private_target = read_api._EXPORTS["write_publish_manifest"][0]
    assert actual_private_target == "polisyos.data_forge.kernel.pipeline.manifests"
    assert _data_forge_dynamic_route_is_forbidden(actual_private_target)

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        textwrap.dedent(
            """
        from importlib import import_module
        import polisyos.data_forge as data_forge

        import_module(data_forge.read_api._EXPORTS["write_publish_manifest"][0])
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert any("consumer.py" in violation for violation in violations)
    assert any(
        "unresolved Data Forge-derived dynamic target" in violation for violation in violations
    )

    consumer.write_text(
        textwrap.dedent(
            """
        from importlib import import_module

        api = import_module("polisyos.data_forge.read_api")
        target = api._EXPORTS["write_publish_manifest"][0]
        import_module(target)
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "consumer.py" in violations[0]
    assert "Data Forge" in violations[0]

    consumer.write_text(
        textwrap.dedent(
            """
        from importlib import import_module
        import polisyos.data_forge as data_forge

        def load_target(target):
            import_module(target)

        def load_owner_target():
            target = data_forge.read_api._EXPORTS["write_publish_manifest"][0]
            load_target(target)
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "unresolved Data Forge-derived dynamic target" in violations[0]

    consumer.write_text(
        textwrap.dedent(
            """
        import importlib as module_loader

        api = module_loader.import_module("polisyos.data_forge.read_api")
        target = api._EXPORTS["write_publish_manifest"][0]
        module_loader.import_module(target)
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "unresolved Data Forge-derived dynamic target" in violations[0]

    consumer.write_text(
        textwrap.dedent(
            """
        api = __import__("polisyos.data_forge.read_api", fromlist=["*"])
        target = api._EXPORTS["write_publish_manifest"][0]
        __import__(target, fromlist=["*"])
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "unresolved Data Forge-derived dynamic target" in violations[0]

    consumer.write_text(
        textwrap.dedent(
            """
        from importlib import import_module

        academic = import_module("polisyos.data_forge.read_api.academic")
        SKGQuery = academic.SKGQuery
        """
        ),
        encoding="utf-8",
    )

    assert _runtime_dynamic_import_violations(runtime_root) == []

    consumer.write_text(
        textwrap.dedent(
            """
        from importlib import import_module as load_module
        import polisyos.data_forge as data_forge

        api = data_forge.read_api
        target = api._EXPORTS["write_publish_manifest"][0]
        load_module(target)
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "consumer.py" in violations[0]
    assert "Data Forge" in violations[0]


def test_dynamic_import_gate_resolves_function_local_importer_aliases(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        textwrap.dedent(
            """
        def load_private_module():
            from importlib import import_module

            import_module("polisyos.data_forge.kernel.snapshot")
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.kernel.snapshot" in violations[0]


def test_static_dynamic_import_resolves_package_name_prefix_from_source_identity() -> None:
    tree = ast.parse(
        textwrap.dedent(
            """
        import importlib

        module_name = f"{__name__}.api"
        importlib.import_module(module_name)
        """
        )
    )

    targets, unresolved = _static_dynamic_import_targets(
        tree,
        module_name="polisyos.runtime.http.services.control",
    )

    assert targets == [(5, "polisyos.runtime.http.services.control.api")]
    assert unresolved == []


def test_dynamic_import_gate_resolves_the_closed_owner_registry(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "design_generation.py"
    consumer.write_text(
        textwrap.dedent(
            """
        import importlib

        _SEARCH_SURROGATE_OWNERS = (
            "polisyos.data_forge.domains.academic.knowledge.skg_query.SKGQuery",
        )

        def _resolve_owner_symbol(owner_ref):
            module_name, _, symbol_name = owner_ref.rpartition(".")
            return getattr(importlib.import_module(module_name), symbol_name)

        def _resolved_surrogate_owner_feature_refs():
            for owner_ref in _SEARCH_SURROGATE_OWNERS:
                _resolve_owner_symbol(owner_ref)
        """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.domains.academic.knowledge.skg_query" in violations[0]
    consumer.write_text(
        consumer.read_text(encoding="utf-8").replace(
            "polisyos.data_forge.domains.academic.knowledge.skg_query.SKGQuery",
            "polisyos.data_forge.read_api.academic.SKGQuery",
        ),
        encoding="utf-8",
    )
    assert _runtime_dynamic_import_violations(runtime_root) == []


def test_dynamic_import_gate_tracks_finite_owner_flow_without_site_names(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        textwrap.dedent(
            """
        import importlib as loader

        _CANDIDATE_OWNER_ROWS = (
            "polisyos.data_forge.read_api.academic.SKGQuery",
        )

        def _split_owner_record(record):
            module_path, _, symbol = record.rpartition(".")
            return getattr(loader.import_module(module_path), symbol)

        def _consume_owner_rows():
            for record in _CANDIDATE_OWNER_ROWS:
                _split_owner_record(record)
        """
        ),
        encoding="utf-8",
    )

    assert _runtime_dynamic_import_violations(runtime_root) == []

    consumer.write_text(
        consumer.read_text(encoding="utf-8").replace(
            "polisyos.data_forge.read_api.academic.SKGQuery",
            "polisyos.data_forge.domains.academic.knowledge.skg_query.SKGQuery",
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.domains.academic.knowledge.skg_query" in violations[0]


def test_dynamic_import_gate_rejects_forbidden_targets_in_runtime_facade_maps(
    tmp_path: Path,
) -> None:
    facade_maps = (
        (
            Path("__init__.py"),
            "polisyos.scientist.replay.deterministic",
        ),
        (
            Path("http/__init__.py"),
            "polisyos.runtime.http.app",
        ),
        (
            Path("http/services/__init__.py"),
            "polisyos.runtime.http.services.debug",
        ),
    )
    runtime_root = tmp_path / "runtime"
    for relative_path, existing_target in facade_maps:
        source = RUNTIME_ROOT / relative_path
        source_text = source.read_text(encoding="utf-8")
        assert existing_target in source_text
        destination = runtime_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            source_text.replace(
                existing_target,
                "polisyos.data_forge.domains.private.runtime_facade",
            ),
            encoding="utf-8",
        )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 3, violations
    assert all("polisyos.data_forge.domains.private.runtime_facade" in x for x in violations)


def test_dynamic_import_gate_joins_closed_mapping_values_for_unknown_get_key(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "consumer.py").write_text(
        textwrap.dedent(
            """
            import importlib

            OWNER_ROUTES = {
                "public": ("polisyos.data_forge.read_api.academic", "SKGQuery"),
                "private": (
                    "polisyos.data_forge.domains.academic.knowledge.skg_query",
                    "SKGQuery",
                ),
            }

            def resolve_owner(route_name):
                module_name, symbol_name = OWNER_ROUTES.get(route_name)
                return getattr(importlib.import_module(module_name), symbol_name)

            resolve_owner(selected_route)
            """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.domains.academic.knowledge.skg_query" in violations[0]


def test_dynamic_import_gate_joins_closed_mapping_values_for_unknown_subscript_key(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "consumer.py").write_text(
        textwrap.dedent(
            """
            from importlib import import_module as load

            ROUTES = {
                "public": ("polisyos.data_forge.read_api.academic", "SKGQuery"),
                "private": (
                    "polisyos.data_forge.domains.academic.knowledge.skg_query",
                    "SKGQuery",
                ),
            }

            def resolve_owner(route_name):
                module_name, symbol_name = ROUTES[route_name]
                return getattr(load(module_name), symbol_name)

            resolve_owner(selected_route)
            """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.domains.academic.knowledge.skg_query" in violations[0]


def test_dynamic_import_gate_joins_mapping_assignments_across_branches(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "consumer.py").write_text(
        textwrap.dedent(
            """
            from importlib import import_module

            def resolve_owner(route_name):
                if route_name:
                    routes = {"public": "polisyos.data_forge.read_api.academic"}
                else:
                    routes = {
                        "private": "polisyos.data_forge.domains.academic.knowledge.skg_query"
                    }
                import_module(routes.get(route_name))

            resolve_owner(selected_route)
            """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.domains.academic.knowledge.skg_query" in violations[0]


def test_dynamic_import_gate_allows_unknown_key_when_closed_mapping_is_public(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "consumer.py").write_text(
        textwrap.dedent(
            """
            from importlib import import_module

            routes = {
                "first": "polisyos.data_forge.read_api.academic",
                "second": "polisyos.data_forge.read_api.academic",
            }

            def resolve_owner(route_name):
                import_module(routes.get(route_name))

            resolve_owner(selected_route)
            """
        ),
        encoding="utf-8",
    )

    assert _runtime_dynamic_import_violations(runtime_root) == []


def test_dynamic_import_gate_includes_mapping_get_default_when_key_may_be_missing(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        textwrap.dedent(
            """
            from importlib import import_module

            routes = {"known": "polisyos.data_forge.read_api.academic"}
            target = routes.get(
                selected_route,
                "polisyos.data_forge.domains.academic.knowledge.skg_query",
            )
            import_module(target)
            """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert len(violations) == 1
    assert "polisyos.data_forge.domains.academic.knowledge.skg_query" in violations[0]


def test_dynamic_import_gate_refuses_oversized_data_forge_mapping(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    routes = ",\n".join(
        f'    "route-{index}": "polisyos.data_forge.read_api.academic"'
        for index in range(_STATIC_VALUE_LIMIT + 1)
    )
    (runtime_root / "consumer.py").write_text(
        "from importlib import import_module\n\n"
        f"ROUTES = {{\n{routes}\n}}\n\n"
        "def resolve_owner(route_name):\n"
        "    import_module(ROUTES.get(route_name))\n\n"
        "resolve_owner(selected_route)\n",
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert any(
        "unresolved Data Forge-derived dynamic target" in violation for violation in violations
    )
    consumer = runtime_root / "consumer.py"
    consumer.write_text(
        consumer.read_text(encoding="utf-8").replace(
            "polisyos.data_forge.read_api.academic",
            "external_package.public_api",
        ),
        encoding="utf-8",
    )
    assert _runtime_dynamic_import_violations(runtime_root) == []


def test_dynamic_import_gate_preserves_target_domains_through_composition(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"

    def write_route_map(*, count: int, value: str, include_default: bool) -> None:
        routes = ",\n".join(
            f'    "route-{index}": {value.format(index=index)}' for index in range(count)
        )
        default = ', "external.safe"' if include_default else ""
        consumer.write_text(
            "from importlib import import_module\n\n"
            f"ROUTES = {{{routes}\n}}\n\n"
            "def load(route_name):\n"
            f"    import_module(ROUTES.get(route_name{default}))\n\n"
            "load(selected_route)\n",
            encoding="utf-8",
        )

    private_fragmented = '"polisyos." + "data_forge.domains.private.module_{index}"'
    write_route_map(count=_STATIC_VALUE_LIMIT + 1, value=private_fragmented, include_default=False)
    violations = _runtime_dynamic_import_violations(runtime_root)
    assert violations, "over-limit composed private targets must not become a clean sink"

    write_route_map(count=_STATIC_VALUE_LIMIT, value=private_fragmented, include_default=True)
    violations = _runtime_dynamic_import_violations(runtime_root)
    assert violations, "unknown-key mapping plus a default must retain every possible target"

    write_route_map(
        count=_STATIC_VALUE_LIMIT + 1,
        value='"external_package.public_api.module_{index}"',
        include_default=False,
    )
    assert _runtime_dynamic_import_violations(runtime_root) == []

    consumer.write_text(
        textwrap.dedent(
            """
            from importlib import import_module

            def load(target):
                import_module(target)

            load(supplied_target)
            """
        ),
        encoding="utf-8",
    )
    assert _runtime_dynamic_import_violations(runtime_root), (
        "a wholly unknown import target is not proof of a safe route"
    )

    safe_prefix_tree = ast.parse(
        textwrap.dedent(
            """
            import importlib

            def load(child_name):
                importlib.import_module(f"{__name__}.{child_name}")
            """
        )
    )
    _, unresolved = _static_dynamic_import_targets(
        safe_prefix_tree,
        module_name="polisyos.runtime.http.services.control",
    )
    assert unresolved == [], "the fixed runtime prefix proves the unknown suffix disjoint"


def test_dynamic_import_gate_preserves_summaries_through_loops_and_fstrings(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    consumer = runtime_root / "consumer.py"
    route_values = ",\n".join(
        f'    "polisyos.data_forge.domains.private.module_{index}"'
        for index in range(_STATIC_VALUE_LIMIT + 1)
    )
    consumer.write_text(
        "import importlib\n\n"
        f"TARGETS = (\n{route_values}\n)\n\n"
        "def load_all():\n"
        "    for target in TARGETS:\n"
        "        importlib.import_module(target)\n\n"
        "load_all()\n",
        encoding="utf-8",
    )
    assert _runtime_dynamic_import_violations(runtime_root), (
        "an over-limit loop summary must preserve its possible private targets"
    )

    route_entries = ",\n".join(
        f'    "route-{index}": "polisyos.data_forge.domains.private.module_{index}"'
        for index in range(_STATIC_VALUE_LIMIT + 1)
    )
    consumer.write_text(
        "import importlib\n\n"
        f"ROUTES = {{{route_entries}\n}}\n\n"
        "def load(route_name):\n"
        "    target = ROUTES.get(route_name)\n"
        '    importlib.import_module(f"{target}.child")\n\n'
        "load(selected_route)\n",
        encoding="utf-8",
    )
    violations = _runtime_dynamic_import_violations(runtime_root)
    assert violations, "an over-limit mapping prefix must survive f-string composition"


def test_dynamic_import_gate_budgets_independent_callable_roots_separately() -> None:
    large_body = "\n".join(f'    temporary_{index} = "bounded"' for index in range(4_300))
    tree = ast.parse(
        "from importlib import import_module\n\n"
        "def a_large_private_route():\n"
        f"{large_body}\n"
        '    target = "polisyos.data_forge.read_api.private"\n'
        "    import_module(target)\n\n"
        "def z_small_public_route():\n"
        '    target = "external.public_api"\n'
        "    import_module(target)\n"
    )

    targets, unresolved = _static_dynamic_import_targets(tree)

    assert targets == [(4_309, "external.public_api")]
    assert unresolved == [(4_305, "unknown_target:analysis_step_limit")]


def test_dynamic_import_gate_accounts_for_sinks_nested_in_unsupported_expressions() -> None:
    tree = ast.parse(
        textwrap.dedent(
            """
            from importlib import import_module

            loader = import_module

            def _sink(module_name):
                return loader(module_name)

            def _row(entry):
                return _sink(entry.module)

            def build(catalog):
                rows = []
                rows.extend(_row(entry) for entry in catalog.types)
                return rows

            build(current_catalog)
            """
        )
    )

    targets, unresolved = _static_dynamic_import_targets(tree)

    assert targets == []
    assert unresolved == [(7, "unknown_target:unvisited_sink_analysis")]


def test_dynamic_import_gate_reconciles_comprehension_lambda_and_default_sinks() -> None:
    tree = ast.parse(
        textwrap.dedent(
            """
            from importlib import import_module

            loader = import_module

            def scan(values):
                generated = (loader(value) for value in values)
                listed = [loader(value) for value in values]
                unique = {loader(value) for value in values}
                indexed = {value: loader(value) for value in values}
                callback = lambda value: loader(value)

                def route(module_name=loader(selected_module)):
                    return module_name

                return generated, listed, unique, indexed, callback, route
            """
        )
    )
    sink_sites = _dynamic_import_sites(tree)
    sinks = [site.node for site in sink_sites]

    targets, unresolved = _static_dynamic_import_targets(tree)

    assert targets == []
    assert unresolved == sorted(
        (sink.lineno, "unknown_target:unvisited_sink_analysis") for sink in sinks
    )


def test_dynamic_import_gate_preserves_data_forge_taint_through_unknown_fstring_parts(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "consumer.py").write_text(
        textwrap.dedent(
            """
            from importlib import import_module

            def load_child(child_name):
                import_module(f"polisyos.data_forge.{child_name}")

            load_child(selected_child)
            """
        ),
        encoding="utf-8",
    )

    violations = _runtime_dynamic_import_violations(runtime_root)

    assert any(
        "unresolved Data Forge-derived dynamic target" in violation for violation in violations
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


@lru_cache(maxsize=1)
def _data_forge_import_rule() -> tuple[tuple[str, ...], tuple[str, ...]]:
    contracts = tomllib.loads(IMPORT_CONTRACT.read_text(encoding="utf-8"))["importlinter"][
        "contracts"
    ]
    contract = next(
        row
        for row in contracts
        if row["name"] == "Runtime and Fabric consumers use Data Forge only through read_api"
    )
    forbidden = tuple(
        module
        for module in contract["forbidden_modules"]
        if module == "polisyos.data_forge" or module.startswith("polisyos.data_forge.")
    )
    ignored = tuple(contract.get("ignore_imports", ()))
    return forbidden, ignored


@lru_cache(maxsize=1)
def _data_forge_supported_entrypoints() -> frozenset[str]:
    packages = tomllib.loads(PUBLIC_SURFACE_CONTRACT.read_text(encoding="utf-8"))["package"]
    package = next(row for row in packages if row["module"] == "polisyos.data_forge")
    return frozenset(package["supported_entrypoints"])


@lru_cache(maxsize=1)
def _lex_knowledge_public_entrypoints() -> frozenset[str]:
    packages = tomllib.loads(PUBLIC_SURFACE_CONTRACT.read_text(encoding="utf-8"))["package"]
    package = next(row for row in packages if row["module"] == "polisyos.lex")
    return frozenset(package["supported_entrypoints"])


def _matches_module_pattern(module_name: str, pattern: str) -> bool:
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return module_name == prefix or module_name.startswith(f"{prefix}.")
    return module_name == pattern or module_name.startswith(f"{pattern}.")


def _is_data_forge_module_path(module_name: str) -> bool:
    root = "polisyos.data_forge"
    return module_name == root or module_name.startswith(f"{root}.")


def _data_forge_route_is_forbidden(module_name: str) -> bool:
    forbidden, _ = _data_forge_import_rule()
    if not any(_matches_module_pattern(module_name, prefix) for prefix in forbidden):
        return False
    return not _data_forge_public_path_is_allowed(module_name)


def _data_forge_dynamic_route_is_forbidden(module_name: str) -> bool:
    forbidden, _ = _data_forge_import_rule()
    if not any(_matches_module_pattern(module_name, prefix) for prefix in forbidden):
        return False
    return module_name not in _data_forge_supported_entrypoints()


def _data_forge_public_path_is_allowed(path: str) -> bool:
    entrypoints = _data_forge_supported_entrypoints()
    if path in entrypoints:
        return True

    read_api = "polisyos.data_forge.read_api"
    if path.startswith(f"{read_api}."):
        remainder = path.removeprefix(f"{read_api}.")
        first, separator, tail = remainder.partition(".")
        child_module = f"{read_api}.{first}"
        if child_module in entrypoints:
            return not separator or tail.split(".", 1)[0] in _data_forge_public_exports(
                child_module
            )
        return first in _data_forge_public_exports(read_api)
    return False


@lru_cache(maxsize=8)
def _data_forge_public_exports(module_name: str) -> frozenset[str]:
    if module_name not in _data_forge_supported_entrypoints():
        return frozenset()
    module = (
        read_api
        if module_name == "polisyos.data_forge.read_api"
        else importlib.import_module(module_name)
    )
    exports = getattr(module, "__all__", ())
    return frozenset(name for name in exports if isinstance(name, str))


def _lex_knowledge_route_is_forbidden(module_name: str) -> bool:
    facade = "polisyos.lex.knowledge"
    return module_name.startswith(f"{facade}.") and module_name not in (
        _lex_knowledge_public_entrypoints()
    )


def _data_forge_import_violations(root: Path) -> list[str]:
    violations: list[str] = []
    repo_root = REPO_ROOT
    for path in sorted(item for item in root.rglob("*.py") if "__pycache__" not in item.parts):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        try:
            relative_path = path.relative_to(repo_root).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            for module_name in _import_names(node):
                if _data_forge_route_is_forbidden(module_name):
                    violations.append(f"{relative_path}:{node.lineno}: {module_name}")
        violations.extend(
            f"{relative_path}:{line}: unsupported Data Forge access path {route}"
            for line, route in _data_forge_alias_access_violations(tree)
        )
    return sorted(set(violations))


def _dynamic_import_sites(
    tree: ast.Module,
    *,
    source_path: Path | None = None,
    relative_path: str = "tests/unit/data_forge/phase6-fixture.py",
) -> tuple[preflight._DynamicImportSite, ...]:
    scanner = preflight._DynamicImportSourceScanner(
        source_path or (REPO_ROOT / "src" / "phase6_fixture.py"),
        relative_path=relative_path,
    )
    _, sites = scanner.scan_with_sites(tree)
    return sites


def _data_forge_alias_origins(
    tree: ast.Module,
    *,
    sink_sites: Sequence[preflight._DynamicImportSite] | None = None,
) -> tuple[dict[str, str], set[str]]:
    origins: dict[str, str] = {}
    tainted: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.partition(".")[0]
                origin = alias.name if alias.asname else alias.name.partition(".")[0]
                if _is_data_forge_module_path(origin) or origin == "polisyos":
                    origins[local_name] = origin
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name == "polisyos" or _is_data_forge_module_path(module_name):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local_name = alias.asname or alias.name
                    origins[local_name] = f"{module_name}.{alias.name}"

    assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign | ast.AnnAssign)]
    site_call_names = {
        id(site.node): site.call_name
        for site in (sink_sites if sink_sites is not None else _dynamic_import_sites(tree))
    }
    string_constants = _module_string_constants(tree)
    for _ in range(len(assignments) + 1):
        changed = False
        for node in assignments:
            value = node.value
            if value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {
                target.id
                for target in targets
                for target in ast.walk(target)
                if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store)
            }
            origin = _module_path_from_expression(value, origins)
            for name in names:
                if origin is not None and _is_data_forge_module_path(origin):
                    if origins.get(name) != origin:
                        origins[name] = origin
                        tainted.discard(name)
                        changed = True
                elif dynamic_origin := _dynamic_import_result_origin(
                    value,
                    site_call_names=site_call_names,
                    string_constants=string_constants,
                ):
                    if origins.get(name) != dynamic_origin:
                        origins[name] = dynamic_origin
                        tainted.discard(name)
                        changed = True
                elif _expression_is_data_forge_derived(value, origins, tainted):
                    if name not in tainted:
                        tainted.add(name)
                        changed = True
        if not changed:
            break
    return origins, tainted


def _dynamic_import_result_origin(
    node: ast.expr,
    *,
    site_call_names: Mapping[int, str],
    string_constants: dict[str, str],
) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    call_name = site_call_names.get(id(node))
    target_expression = _dynamic_import_target(node)
    if target_expression is None:
        return None
    target = _literal_string_value(target_expression, string_constants)
    if (
        call_name is None
        or target is None
        or not (target == "polisyos" or target.startswith("polisyos."))
    ):
        return None
    if call_name == "importlib.import_module":
        return target

    fromlist = (
        node.args[1]
        if len(node.args) > 1
        else next(
            (keyword.value for keyword in node.keywords if keyword.arg == "fromlist"),
            None,
        )
    )
    if (
        isinstance(fromlist, ast.List | ast.Tuple)
        and fromlist.elts
        and all(
            isinstance(item, ast.Constant) and isinstance(item.value, str) for item in fromlist.elts
        )
    ):
        return target
    if isinstance(fromlist, ast.Constant) and fromlist.value in (None, (), []):
        return target.partition(".")[0]
    if fromlist is None:
        return target.partition(".")[0]
    return "polisyos"


def _module_path_from_expression(node: ast.expr, origins: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return origins.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _module_path_from_expression(node.value, origins)
        return f"{base}.{node.attr}" if base is not None else None
    return None


def _expression_is_data_forge_derived(
    node: ast.AST,
    origins: dict[str, str],
    tainted: set[str],
) -> bool:
    module_path = (
        _module_path_from_expression(node, origins) if isinstance(node, ast.expr) else None
    )
    if module_path is not None and _is_data_forge_module_path(module_path):
        return True
    if isinstance(node, ast.Name) and node.id in tainted:
        return True
    return any(
        _expression_is_data_forge_derived(child, origins, tainted)
        for child in ast.iter_child_nodes(node)
    )


def _data_forge_alias_access_violations(tree: ast.Module) -> list[tuple[int, str]]:
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    origins, _ = _data_forge_alias_origins(tree)
    violations: list[tuple[int, str]] = []
    for use in ast.walk(tree):
        if (
            not isinstance(use, ast.Name)
            or not isinstance(use.ctx, ast.Load)
            or use.id not in origins
        ):
            continue
        cursor: ast.expr = use
        while isinstance(parents.get(cursor), ast.Attribute) and parents[cursor].value is cursor:
            cursor = parents[cursor]
        path = _module_path_from_expression(cursor, origins)
        if path is None or not _is_data_forge_module_path(path):
            continue
        if (path == "polisyos.data_forge" and cursor is use) or not (
            _data_forge_public_path_is_allowed(path)
        ):
            violations.append((use.lineno, path))
    return violations


def _lex_private_import_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(item for item in root.rglob("*.py") if "__pycache__" not in item.parts):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        try:
            relative_path = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            for module_name in _import_names(node):
                if _lex_knowledge_route_is_forbidden(module_name):
                    violations.append(f"{relative_path}:{node.lineno}: {module_name}")
    return violations


def _dynamic_import_target(node: ast.Call) -> ast.expr | None:
    """Return the import target passed positionally or by its public keyword."""

    if node.args:
        return node.args[0]
    return next((keyword.value for keyword in node.keywords if keyword.arg == "name"), None)


def _literal_string_value(node: ast.expr, values: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_string_value(node.left, values)
        right = _literal_string_value(node.right, values)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                piece = _literal_string_value(value.value, values)
                if piece is None:
                    return None
                pieces.append(piece)
            else:
                return None
        return "".join(pieces)
    return None


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                resolved = _literal_string_value(value, constants)
                if resolved is not None:
                    constants[target.id] = resolved
    return constants


def _literal_dynamic_import_targets(
    tree: ast.Module,
    *,
    sink_sites: Sequence[preflight._DynamicImportSite] | None = None,
) -> list[tuple[int, str]]:
    constants = _module_string_constants(tree)
    targets: list[tuple[int, str]] = []
    sites = sink_sites if sink_sites is not None else _dynamic_import_sites(tree)
    for site in sites:
        node = site.node
        target_expression = _dynamic_import_target(node)
        if target_expression is None:
            continue
        target = _literal_string_value(target_expression, constants)
        if target is not None:
            targets.append((node.lineno, target))
    return targets


@dataclass(frozen=True)
class _StaticValue:
    """A bounded abstract value for resolving dynamic-import dataflow."""

    strings: frozenset[str] | None = None
    items: tuple[_StaticValue, ...] | None = None
    mapping: tuple[tuple[str, _StaticValue], ...] | None = None
    mapping_required_keys: frozenset[str] | None = None
    data_forge_derived: bool = False
    string_prefixes: frozenset[str] | None = None
    item_values: _StaticValue | None = None
    mapping_values: _StaticValue | None = None
    unknown_reasons: frozenset[str] = frozenset({"unknown_value"})


_UNKNOWN_STATIC_VALUE = _StaticValue()
_STATIC_VALUE_LIMIT = 64
_STATIC_ANALYSIS_STEP_LIMIT = 4096


def _static_string(value: str) -> _StaticValue:
    return _StaticValue(
        strings=frozenset({value}),
        data_forge_derived=_is_data_forge_module_path(value),
        unknown_reasons=frozenset(),
    )


def _unknown_static_value(
    reason: str,
    *,
    data_forge_derived: bool = False,
    string_prefixes: frozenset[str] | None = None,
    items: tuple[_StaticValue, ...] | None = None,
    item_values: _StaticValue | None = None,
    mapping: tuple[tuple[str, _StaticValue], ...] | None = None,
    mapping_values: _StaticValue | None = None,
    mapping_required_keys: frozenset[str] | None = None,
    inherited_reasons: frozenset[str] = frozenset(),
) -> _StaticValue:
    return _StaticValue(
        items=items,
        mapping=mapping,
        mapping_required_keys=mapping_required_keys,
        data_forge_derived=data_forge_derived,
        string_prefixes=string_prefixes,
        item_values=item_values,
        mapping_values=mapping_values,
        unknown_reasons=inherited_reasons | {reason},
    )


def _common_string_prefix(values: list[str] | tuple[str, ...] | frozenset[str]) -> str:
    if not values:
        return ""
    first = min(values)
    last = max(values)
    limit = min(len(first), len(last))
    index = 0
    while index < limit and first[index] == last[index]:
        index += 1
    return first[:index]


def _normalize_string_prefixes(prefixes: list[str]) -> frozenset[str]:
    if not prefixes:
        return frozenset()
    unique = sorted(set(prefixes))
    minimal = [
        prefix
        for prefix in unique
        if not any(other != prefix and prefix.startswith(other) for other in unique)
    ]
    if len(minimal) <= _STATIC_VALUE_LIMIT:
        return frozenset(minimal)
    return frozenset({_common_string_prefix(minimal)})


def _string_prefix_domain(value: _StaticValue) -> frozenset[str] | None:
    if value.strings is not None:
        if not value.strings:
            return frozenset()
        return frozenset({_common_string_prefix(value.strings)})
    return value.string_prefixes


def _joined_string_prefixes(values: list[_StaticValue]) -> frozenset[str] | None:
    prefixes: list[str] = []
    for value in values:
        domain = _string_prefix_domain(value)
        if domain is None:
            return None
        prefixes.extend(domain)
    return _normalize_string_prefixes(prefixes)


def _domain_may_be_data_forge(value: _StaticValue) -> bool:
    if value.data_forge_derived:
        return True
    if value.strings is not None and any(
        _is_data_forge_module_path(item) for item in value.strings
    ):
        return True
    prefixes = _string_prefix_domain(value)
    if prefixes is None:
        return False
    root = "polisyos.data_forge"
    return any(
        prefix == root
        or prefix.startswith(f"{root}.")
        or root.startswith(prefix)
        or f"{root}.".startswith(prefix)
        for prefix in prefixes
    )


def _static_concatenate_strings(left: _StaticValue, right: _StaticValue) -> _StaticValue:
    inherited = left.unknown_reasons | right.unknown_reasons
    derived = left.data_forge_derived or right.data_forge_derived
    if left.strings is not None and right.strings is not None:
        values = {first + second for first in left.strings for second in right.strings}
        if len(values) <= _STATIC_VALUE_LIMIT:
            return _StaticValue(
                strings=frozenset(values),
                data_forge_derived=derived or any(_is_data_forge_module_path(x) for x in values),
                unknown_reasons=inherited,
            )
        prefix = _common_string_prefix(values)
        return _unknown_static_value(
            "string_concatenation_limit",
            data_forge_derived=derived
            or _domain_may_be_data_forge(
                _StaticValue(string_prefixes=frozenset({prefix}), unknown_reasons=inherited)
            ),
            string_prefixes=frozenset({prefix}),
            inherited_reasons=inherited,
        )

    left_prefixes = _string_prefix_domain(left)
    right_prefixes = _string_prefix_domain(right)
    if left_prefixes is None:
        return _unknown_static_value(
            "string_concatenation_unknown_operand",
            data_forge_derived=derived,
            inherited_reasons=inherited,
        )
    if left.strings is not None and len(left.strings) == 1:
        literal_prefix = next(iter(left.strings))
        prefixes = (
            frozenset({literal_prefix})
            if right_prefixes is None
            else _normalize_string_prefixes(
                [literal_prefix + right_prefix for right_prefix in right_prefixes]
            )
        )
    else:
        prefixes = left_prefixes
    return _unknown_static_value(
        "string_concatenation_summary",
        data_forge_derived=derived
        or _domain_may_be_data_forge(
            _StaticValue(string_prefixes=prefixes, unknown_reasons=inherited)
        ),
        string_prefixes=prefixes,
        inherited_reasons=inherited,
    )


def _dynamic_forbidden_namespace_roots() -> frozenset[str]:
    forbidden, _ = _data_forge_import_rule()
    roots = {pattern.removesuffix(".*") for pattern in forbidden}
    lex_entrypoints = _lex_knowledge_public_entrypoints()
    roots.update(
        entrypoint
        for entrypoint in lex_entrypoints
        if any(other.startswith(f"{entrypoint}.") for other in lex_entrypoints)
        or any(
            entrypoint.startswith(f"{other}.") for other in lex_entrypoints if other != entrypoint
        )
    )
    return frozenset(roots)


def _string_prefixes_prove_route_safe(prefixes: frozenset[str] | None) -> bool:
    if prefixes is None:
        return False
    roots = _dynamic_forbidden_namespace_roots()
    for prefix in prefixes:
        for root in roots:
            if (
                prefix == root
                or prefix.startswith(f"{root}.")
                or root.startswith(prefix)
                or f"{root}.".startswith(prefix)
            ):
                return False
    return True


def _static_join(values: list[_StaticValue], *, data_forge_derived: bool = False) -> _StaticValue:
    if not values:
        return _unknown_static_value("empty_join", data_forge_derived=data_forge_derived)
    string_sets = [value.strings for value in values]
    strings: frozenset[str] | None = None
    string_prefixes: frozenset[str] | None = None
    unknown_reasons = frozenset().union(*(value.unknown_reasons for value in values))
    if all(item is not None for item in string_sets):
        combined = frozenset().union(*(item for item in string_sets if item is not None))
        if len(combined) <= _STATIC_VALUE_LIMIT:
            strings = combined
        else:
            string_prefixes = frozenset({_common_string_prefix(combined)})
            unknown_reasons |= {"string_join_limit"}
    else:
        string_prefixes = _joined_string_prefixes(values)
        if string_prefixes is None:
            unknown_reasons |= {"string_domain_unknown"}
        else:
            unknown_reasons |= {"string_domain_join"}
    item_sets = [value.items for value in values]
    items = None
    if all(item is not None for item in item_sets):
        sequences = [item for item in item_sets if item is not None]
        if len(sequences[0]) <= _STATIC_VALUE_LIMIT and len({len(x) for x in sequences}) == 1:
            items = tuple(
                _static_join([sequence[index] for sequence in sequences])
                for index in range(len(sequences[0]))
            )
    item_candidates: list[_StaticValue] = []
    item_unknown = False
    has_items = False
    for value in values:
        if value.items is not None:
            has_items = True
            item_candidates.extend(value.items)
        elif value.item_values is not None:
            has_items = True
            item_candidates.append(value.item_values)
        elif (
            value.unknown_reasons
            and value.strings is None
            and value.string_prefixes is None
            and value.mapping is None
            and value.mapping_values is None
        ):
            item_unknown = True
    item_values = None
    if has_items:
        item_values = (
            _static_join(item_candidates)
            if item_candidates and not item_unknown
            else _unknown_static_value("sequence_join_unknown")
        )
        if items is None and item_candidates:
            unknown_reasons |= {"sequence_join_limit"}
    mapping_sets = [value.mapping for value in values]
    mapping: tuple[tuple[str, _StaticValue], ...] | None = None
    mapping_required_keys: frozenset[str] | None = None
    mapping_candidates: list[_StaticValue] = []
    mapping_unknown = False
    has_mapping = False
    for value in values:
        if value.mapping is not None:
            has_mapping = True
            mapping_candidates.extend(item for _, item in value.mapping)
        elif value.mapping_values is not None:
            has_mapping = True
            mapping_candidates.append(value.mapping_values)
        elif (
            value.unknown_reasons
            and value.strings is None
            and value.string_prefixes is None
            and value.items is None
            and value.item_values is None
        ):
            mapping_unknown = True
    mapping_values = None
    if has_mapping:
        mapping_values = (
            _static_join(mapping_candidates)
            if mapping_candidates and not mapping_unknown
            else _unknown_static_value("mapping_join_unknown")
        )
    if all(item is not None for item in mapping_sets):
        maps = [dict(item) for item in mapping_sets if item is not None]
        keys = set().union(*(set(item) for item in maps))
        if len(keys) <= _STATIC_VALUE_LIMIT:
            mapping = tuple(
                (
                    key,
                    _static_join([item[key] for item in maps if key in item]),
                )
                for key in sorted(keys)
            )
            required_keys = [value.mapping_required_keys or frozenset() for value in values]
            mapping_required_keys = frozenset.intersection(*required_keys)
        elif has_mapping:
            unknown_reasons |= {"mapping_join_limit"}
    elif has_mapping:
        unknown_reasons |= {"mapping_join_unknown"}
    derived = (
        data_forge_derived
        or any(_domain_may_be_data_forge(value) for value in values)
        or (mapping_values is not None and _domain_may_be_data_forge(mapping_values))
        or (item_values is not None and _domain_may_be_data_forge(item_values))
    )
    return _StaticValue(
        strings=strings,
        items=items,
        mapping=mapping,
        mapping_required_keys=mapping_required_keys,
        data_forge_derived=derived,
        string_prefixes=string_prefixes,
        item_values=item_values,
        mapping_values=mapping_values,
        unknown_reasons=unknown_reasons,
    )


def _static_import_environment(tree: ast.Module) -> dict[str, _StaticValue]:
    environment: dict[str, _StaticValue] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.partition(".")[0]
                module_name = alias.name if alias.asname else alias.name.partition(".")[0]
                environment[local_name] = _StaticValue(
                    data_forge_derived=_is_data_forge_module_path(module_name)
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            for alias in node.names:
                if alias.name != "*":
                    imported = f"{module_name}.{alias.name}".strip(".")
                    environment[alias.asname or alias.name] = _StaticValue(
                        data_forge_derived=_is_data_forge_module_path(imported)
                    )
    return environment


def _static_assign_target(
    target: ast.expr, value: _StaticValue, environment: dict[str, _StaticValue]
) -> None:
    if isinstance(target, ast.Name):
        environment[target.id] = value
    elif isinstance(target, ast.Tuple | ast.List):
        items = value.items
        if items is None and value.item_values is not None:
            items = value.item_values.items
        if items is not None and len(items) == len(target.elts):
            for child, item in zip(target.elts, items, strict=True):
                _static_assign_target(child, item, environment)
        else:
            unknown = _unknown_static_value(
                "tuple_unpack_unknown",
                data_forge_derived=_domain_may_be_data_forge(value),
                inherited_reasons=value.unknown_reasons,
            )
            for child in target.elts:
                _static_assign_target(child, unknown, environment)


def _static_dynamic_import_targets(
    tree: ast.Module,
    *,
    module_name: str | None = None,
    sink_sites: Sequence[preflight._DynamicImportSite] | None = None,
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Resolve bounded finite import targets without executing source modules."""

    sites = sink_sites if sink_sites is not None else _dynamic_import_sites(tree)
    site_call_names = {id(site.node): site.call_name for site in sites}
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    targets: set[tuple[int, str]] = set()
    unresolved: dict[int, set[str]] = {}
    dynamic_sinks = {id(site.node): site.node for site in sites}
    analyzed_sinks: set[int] = set()
    constants = _module_string_constants(tree)
    for sink_id, sink in dynamic_sinks.items():
        target_expression = _dynamic_import_target(sink)
        if target_expression is None:
            analyzed_sinks.add(sink_id)
            unresolved.setdefault(sink.lineno, set()).add(
                "unknown_target:missing_target_expression"
            )
            continue
        literal_target = _literal_string_value(target_expression, constants)
        if literal_target is not None:
            analyzed_sinks.add(sink_id)
            targets.add((sink.lineno, literal_target))
    module_environment = _static_import_environment(tree)
    if module_name is not None:
        module_environment["__name__"] = _static_string(module_name)
    active_functions: frozenset[str] = frozenset()
    analysis_steps = 0

    def mark_unresolved_dynamic_calls(node: ast.AST, reason: str) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and id(child) in dynamic_sinks:
                if id(child) in analyzed_sinks:
                    continue
                analyzed_sinks.add(id(child))
                unresolved.setdefault(child.lineno, set()).add(f"unknown_target:{reason}")

    def consume_analysis_step() -> bool:
        nonlocal analysis_steps
        if analysis_steps >= _STATIC_ANALYSIS_STEP_LIMIT:
            return False
        analysis_steps += 1
        return True

    def begin_analysis_scope() -> None:
        """Bound work independently for each module statement or callable root."""

        nonlocal analysis_steps
        analysis_steps = 0

    def derived(node: ast.AST, environment: dict[str, _StaticValue]) -> bool:
        if isinstance(node, ast.Name):
            return environment.get(node.id, _UNKNOWN_STATIC_VALUE).data_forge_derived
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return _is_data_forge_module_path(node.value)
        if isinstance(node, ast.Attribute | ast.Subscript):
            return derived(node.value, environment)
        return any(derived(child, environment) for child in ast.iter_child_nodes(node))

    def evaluate(
        node: ast.expr,
        environment: dict[str, _StaticValue],
        active: frozenset[str],
        depth: int,
    ) -> _StaticValue:
        if not consume_analysis_step():
            mark_unresolved_dynamic_calls(node, "analysis_step_limit")
            return _unknown_static_value("analysis_step_limit")
        if depth > 12:
            return _unknown_static_value(
                "expression_depth_limit", data_forge_derived=derived(node, environment)
            )
        if isinstance(node, ast.Constant):
            return (
                _static_string(node.value) if isinstance(node.value, str) else _UNKNOWN_STATIC_VALUE
            )
        if isinstance(node, ast.Name):
            return environment.get(
                node.id,
                _unknown_static_value(
                    "unbound_name", data_forge_derived=derived(node, environment)
                ),
            )
        if isinstance(node, ast.Tuple | ast.List):
            values: list[_StaticValue] = []
            item_values: _StaticValue | None = None
            for item_node in node.elts:
                item = evaluate(item_node, environment, active, depth + 1)
                if len(values) < _STATIC_VALUE_LIMIT:
                    values.append(item)
                item_values = item if item_values is None else _static_join([item_values, item])
            oversized = len(node.elts) > _STATIC_VALUE_LIMIT
            return _StaticValue(
                items=tuple(values) if not oversized else None,
                item_values=item_values if oversized else None,
                data_forge_derived=any(_domain_may_be_data_forge(value) for value in values)
                or (item_values is not None and _domain_may_be_data_forge(item_values)),
                unknown_reasons=(frozenset({"sequence_item_limit"}) if oversized else frozenset()),
            )
        if isinstance(node, ast.Dict):
            entries: dict[str, _StaticValue] = {}
            value_summary: _StaticValue | None = None
            tainted = derived(node, environment)
            complete = True
            oversized = False
            for key_node, value_node in zip(node.keys, node.values, strict=True):
                value = evaluate(value_node, environment, active, depth + 1)
                tainted = tainted or _domain_may_be_data_forge(value)
                if key_node is None:
                    complete = False
                    unpacked_values = value.mapping_values
                    if value.mapping is not None:
                        unpacked_values = _static_join([item for _, item in value.mapping])
                    if unpacked_values is None:
                        unpacked_values = _unknown_static_value("mapping_unpack_unknown")
                    value_summary = (
                        unpacked_values
                        if value_summary is None
                        else _static_join([value_summary, unpacked_values])
                    )
                    continue
                value_summary = (
                    value if value_summary is None else _static_join([value_summary, value])
                )
                key = evaluate(key_node, environment, active, depth + 1)
                tainted = tainted or _domain_may_be_data_forge(key)
                if key.strings is None or len(key.strings) != 1:
                    complete = False
                    continue
                key_text = next(iter(key.strings))
                if key_text in entries or len(entries) < _STATIC_VALUE_LIMIT:
                    entries[key_text] = value
                else:
                    oversized = True
            if not complete:
                unknown_value = _unknown_static_value(
                    "incomplete_mapping_keys",
                    data_forge_derived=tainted,
                    mapping_values=(
                        value_summary
                        if value_summary is not None
                        else _unknown_static_value("mapping_values_unknown")
                    ),
                )
                return unknown_value
            if oversized:
                return _unknown_static_value(
                    "mapping_entry_limit",
                    data_forge_derived=tainted,
                    mapping_values=value_summary,
                )
            return _StaticValue(
                mapping=tuple(sorted(entries.items())),
                mapping_required_keys=frozenset(entries),
                mapping_values=value_summary,
                data_forge_derived=tainted,
                unknown_reasons=frozenset(),
            )
        if isinstance(node, ast.Subscript):
            receiver = evaluate(node.value, environment, active, depth + 1)
            index = evaluate(node.slice, environment, active, depth + 1)
            if receiver.mapping is not None:
                entries = dict(receiver.mapping)
                values = (
                    [value for _, value in receiver.mapping]
                    if index.strings is None
                    else [entries[key] for key in index.strings if key in entries]
                )
                if not values:
                    return _StaticValue(
                        data_forge_derived=receiver.data_forge_derived or index.data_forge_derived,
                        unknown_reasons=frozenset(),
                    )
                return _static_join(
                    values,
                    data_forge_derived=receiver.data_forge_derived
                    or _domain_may_be_data_forge(index),
                )
            if receiver.mapping_values is not None:
                return _unknown_static_value(
                    "mapping_subscript_from_summary",
                    data_forge_derived=receiver.data_forge_derived
                    or _domain_may_be_data_forge(receiver.mapping_values)
                    or _domain_may_be_data_forge(index),
                    string_prefixes=_string_prefix_domain(receiver.mapping_values),
                    inherited_reasons=receiver.unknown_reasons
                    | receiver.mapping_values.unknown_reasons,
                )
            if receiver.items is not None:
                try:
                    literal_index = ast.literal_eval(node.slice)
                except ValueError, TypeError, SyntaxError:
                    literal_index = None
                if isinstance(literal_index, int) and not isinstance(literal_index, bool):
                    try:
                        selected = [receiver.items[literal_index]]
                    except IndexError:
                        selected = []
                else:
                    selected = list(receiver.items)
                if not selected:
                    return _StaticValue(
                        data_forge_derived=receiver.data_forge_derived,
                        unknown_reasons=frozenset(),
                    )
                return _static_join(selected, data_forge_derived=receiver.data_forge_derived)
            return _unknown_static_value(
                "unsupported_subscript",
                data_forge_derived=receiver.data_forge_derived
                or _domain_may_be_data_forge(index)
                or derived(node, environment),
            )
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = evaluate(node.left, environment, active, depth + 1)
            right = evaluate(node.right, environment, active, depth + 1)
            return _static_concatenate_strings(left, right)
        if isinstance(node, ast.JoinedStr):
            result = _static_string("")
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    value = _static_string(part.value)
                elif isinstance(part, ast.FormattedValue):
                    formatted = evaluate(part.value, environment, active, depth + 1)
                    if part.conversion != -1 or part.format_spec is not None:
                        return _unknown_static_value(
                            "unsupported_fstring_conversion",
                            data_forge_derived=_domain_may_be_data_forge(formatted)
                            or derived(node, environment),
                            inherited_reasons=formatted.unknown_reasons,
                        )
                    value = formatted
                else:
                    return _unknown_static_value(
                        "unsupported_fstring_part", data_forge_derived=derived(node, environment)
                    )
                result = _static_concatenate_strings(result, value)
            return _StaticValue(
                strings=result.strings,
                data_forge_derived=result.data_forge_derived
                or _domain_may_be_data_forge(result)
                or any(derived(part, environment) for part in node.values),
                string_prefixes=result.string_prefixes,
                unknown_reasons=result.unknown_reasons
                | (
                    {"fstring_composition"}
                    | (
                        {"fstring_expansion_limit"}
                        if "string_concatenation_limit" in result.unknown_reasons
                        else set()
                    )
                    if result.strings is None
                    else frozenset()
                ),
            )
        if isinstance(node, ast.Attribute):
            return _unknown_static_value(
                "unsupported_attribute_value", data_forge_derived=derived(node, environment)
            )
        if isinstance(node, ast.Call):
            import_name = site_call_names.get(id(node))
            if import_name is not None:
                analyzed_sinks.add(id(node))
                target_expression = _dynamic_import_target(node)
                if target_expression is None:
                    unresolved.setdefault(node.lineno, set()).add(
                        "unknown_target:missing_target_expression"
                    )
                    return _unknown_static_value("dynamic_import_target_missing")
                target = evaluate(target_expression, environment, active, depth + 1)
                if target.strings is None:
                    prefixes = _string_prefix_domain(target)
                    if not _string_prefixes_prove_route_safe(prefixes):
                        category = (
                            "data_forge_route"
                            if _domain_may_be_data_forge(target)
                            else "unknown_target"
                        )
                        reasons = target.unknown_reasons or frozenset({"unknown_target"})
                        unresolved.setdefault(node.lineno, set()).add(
                            f"{category}:{','.join(sorted(reasons))}"
                        )
                else:
                    targets.update((node.lineno, value) for value in target.strings)
                return _unknown_static_value(
                    "dynamic_import_result",
                    data_forge_derived=_domain_may_be_data_forge(target),
                    inherited_reasons=target.unknown_reasons,
                )
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                receiver = evaluate(node.func.value, environment, active, depth + 1)
                if node.args and (
                    receiver.mapping is not None or receiver.mapping_values is not None
                ):
                    index = evaluate(node.args[0], environment, active, depth + 1)
                    default_node = (
                        node.args[1]
                        if len(node.args) > 1
                        else next(
                            (
                                keyword.value
                                for keyword in node.keywords
                                if keyword.arg == "default"
                            ),
                            None,
                        )
                    )
                    default = (
                        evaluate(default_node, environment, active, depth + 1)
                        if default_node is not None
                        else None
                    )
                    candidates: list[_StaticValue] = []
                    may_be_missing = False
                    if receiver.mapping is None:
                        if receiver.mapping_values is not None:
                            candidates.append(receiver.mapping_values)
                        may_be_missing = True
                    else:
                        entries = dict(receiver.mapping)
                        if index.strings is None:
                            candidates.extend(entries.values())
                            may_be_missing = True
                        else:
                            required_keys = receiver.mapping_required_keys or frozenset()
                            for key in index.strings:
                                if key in entries:
                                    candidates.append(entries[key])
                                if key not in required_keys:
                                    may_be_missing = True
                    if may_be_missing and default is not None:
                        candidates.append(default)
                    joined = _static_join(
                        candidates,
                        data_forge_derived=receiver.data_forge_derived
                        or _domain_may_be_data_forge(index),
                    )
                    if receiver.mapping is None:
                        joined = _unknown_static_value(
                            "mapping_lookup_from_summary",
                            data_forge_derived=joined.data_forge_derived
                            or _domain_may_be_data_forge(joined),
                            string_prefixes=_string_prefix_domain(joined),
                            inherited_reasons=joined.unknown_reasons | receiver.unknown_reasons,
                        )
                    return joined
                if receiver.data_forge_derived:
                    return _unknown_static_value(
                        "unsupported_mapping_lookup", data_forge_derived=True
                    )
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "partition",
                "rpartition",
                "split",
            }:
                receiver = evaluate(node.func.value, environment, active, depth + 1)
                delimiter = (
                    evaluate(node.args[0], environment, active, depth + 1).strings
                    if node.args
                    else frozenset({None})
                )
                if receiver.strings is not None and delimiter is not None:
                    results: list[_StaticValue] = []
                    for value in receiver.strings:
                        for separator in delimiter:
                            if separator is None:
                                pieces = value.split()
                            elif node.func.attr == "partition":
                                pieces = value.partition(separator)
                            elif node.func.attr == "rpartition":
                                pieces = value.rpartition(separator)
                            else:
                                pieces = value.split(separator)
                            results.append(
                                _StaticValue(
                                    items=tuple(_static_string(piece) for piece in pieces),
                                    data_forge_derived=receiver.data_forge_derived,
                                )
                            )
                    return _static_join(results)
            if isinstance(node.func, ast.Name) and node.func.id in functions:
                function_name = node.func.id
                if function_name in active:
                    return _unknown_static_value(
                        "recursive_call", data_forge_derived=derived(node, environment)
                    )
                function = functions[function_name]
                parameters = [*function.args.posonlyargs, *function.args.args]
                local = environment.copy()
                actuals = [
                    evaluate(argument, environment, active, depth + 1) for argument in node.args
                ]
                actuals.extend(
                    _unknown_static_value("unknown_parameter")
                    for _ in range(max(0, len(parameters) - len(actuals)))
                )
                for parameter, value in zip(parameters, actuals, strict=False):
                    local[parameter.arg] = value
                for keyword in node.keywords:
                    if keyword.arg is not None:
                        local[keyword.arg] = evaluate(keyword.value, environment, active, depth + 1)
                return _static_join(run(function.body, local, active | {function_name}, depth + 1))
            tainted = derived(node, environment)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr):
                    evaluate(child, environment, active, depth + 1)
            return _unknown_static_value("unsupported_call", data_forge_derived=tainted)
        return _unknown_static_value(
            "unsupported_expression", data_forge_derived=derived(node, environment)
        )

    def run(
        statements: list[ast.stmt],
        environment: dict[str, _StaticValue],
        active: frozenset[str],
        depth: int,
    ) -> list[_StaticValue]:
        if not consume_analysis_step():
            for statement in statements:
                mark_unresolved_dynamic_calls(statement, "analysis_step_limit")
            return [_unknown_static_value("analysis_step_limit")]
        if depth > 12:
            for statement in statements:
                mark_unresolved_dynamic_calls(statement, "statement_depth_limit")
            return [_unknown_static_value("statement_depth_limit")]
        returned: list[_StaticValue] = []
        for statement in statements:
            if isinstance(statement, ast.Assign):
                value = evaluate(statement.value, environment, active, depth + 1)
                for target in statement.targets:
                    _static_assign_target(target, value, environment)
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                value = evaluate(statement.value, environment, active, depth + 1)
                _static_assign_target(statement.target, value, environment)
            elif isinstance(statement, ast.Expr):
                evaluate(statement.value, environment, active, depth + 1)
            elif isinstance(statement, ast.For | ast.AsyncFor):
                sequence = evaluate(statement.iter, environment, active, depth + 1)
                items = sequence.items
                if items is None and sequence.strings is not None:
                    if len(sequence.strings) <= _STATIC_VALUE_LIMIT:
                        items = tuple(_static_string(value) for value in sorted(sequence.strings))
                if items is None:
                    if sequence.item_values is not None:
                        item = sequence.item_values
                        item = _unknown_static_value(
                            "loop_iteration_limit",
                            data_forge_derived=item.data_forge_derived
                            or _domain_may_be_data_forge(item),
                            string_prefixes=_string_prefix_domain(item),
                            items=item.items,
                            item_values=item.item_values,
                            mapping=item.mapping,
                            mapping_values=item.mapping_values,
                            mapping_required_keys=item.mapping_required_keys,
                            inherited_reasons=item.unknown_reasons | sequence.unknown_reasons,
                        )
                        items = (item,)
                    else:
                        items = (
                            _unknown_static_value(
                                "loop_sequence_unknown",
                                data_forge_derived=_domain_may_be_data_forge(sequence),
                                inherited_reasons=sequence.unknown_reasons,
                            ),
                        )
                    repeated = True
                else:
                    repeated = False
                for item in items:
                    _static_assign_target(statement.target, item, environment)
                    returned.extend(run(statement.body, environment, active, depth + 1))
                if repeated:
                    assigned_names = {
                        node.id
                        for node in ast.walk(statement)
                        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
                    }
                    for name in assigned_names:
                        if name in environment:
                            value = environment[name]
                            environment[name] = _unknown_static_value(
                                "loop_state_widened",
                                data_forge_derived=_domain_may_be_data_forge(value),
                                string_prefixes=_string_prefix_domain(value),
                                items=value.items,
                                item_values=value.item_values,
                                mapping=value.mapping,
                                mapping_values=value.mapping_values,
                                mapping_required_keys=value.mapping_required_keys,
                                inherited_reasons=value.unknown_reasons,
                            )
                returned.extend(run(statement.orelse, environment, active, depth + 1))
            elif isinstance(statement, ast.If):
                for branch in (statement.body, statement.orelse):
                    local = environment.copy()
                    returned.extend(run(branch, local, active, depth + 1))
                    for name, value in local.items():
                        if name in environment:
                            environment[name] = _static_join([environment[name], value])
                        else:
                            environment[name] = value
            elif isinstance(statement, ast.Try):
                returned.extend(run(statement.body, environment, active, depth + 1))
                for handler in statement.handlers:
                    returned.extend(run(handler.body, environment.copy(), active, depth + 1))
                returned.extend(run(statement.orelse, environment, active, depth + 1))
                returned.extend(run(statement.finalbody, environment, active, depth + 1))
            elif isinstance(statement, ast.Return):
                if statement.value is not None:
                    returned.append(evaluate(statement.value, environment, active, depth + 1))
                break
        return returned

    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            begin_analysis_scope()
            value = evaluate(statement.value, module_environment, active_functions, 0)
            for target in statement.targets:
                _static_assign_target(target, value, module_environment)
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            begin_analysis_scope()
            value = evaluate(statement.value, module_environment, active_functions, 0)
            _static_assign_target(statement.target, value, module_environment)

    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def owner_name(node: ast.AST) -> str | None:
        current = parents.get(node)
        while current is not None:
            if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
                return current.name
            current = parents.get(current)
        return None

    selected: set[str] = set()
    top_level_calls: list[ast.Call] = []
    for node in dynamic_sinks.values():
        target_expression = _dynamic_import_target(node)
        if id(node) in analyzed_sinks:
            continue
        if (
            target_expression is not None
            and _literal_string_value(target_expression, constants) is not None
        ):
            continue
        function_name = owner_name(node)
        if function_name is None:
            top_level_calls.append(node)
        else:
            selected.add(function_name)

    callers: dict[str, set[str]] = {}
    for caller, function in functions.items():
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in functions:
                    callers.setdefault(node.func.id, set()).add(caller)
    pending = list(selected)
    while pending:
        for caller in callers.get(pending.pop(), ()):
            if caller not in selected:
                selected.add(caller)
                pending.append(caller)

    top_level_statements: set[int] = set()
    for call in top_level_calls:
        current: ast.AST = call
        while current in parents and parents[current] is not tree:
            current = parents[current]
        if current in tree.body and not isinstance(current, ast.Assign | ast.AnnAssign):
            top_level_statements.add(id(current))
    for statement in tree.body:
        if id(statement) in top_level_statements:
            begin_analysis_scope()
            run([statement], module_environment, active_functions, 0)
    for function_name in sorted(selected):
        if callers.get(function_name):
            continue
        function = functions[function_name]
        environment = module_environment.copy()
        for parameter in [*function.args.posonlyargs, *function.args.args]:
            environment[parameter.arg] = _unknown_static_value("unknown_parameter")
        begin_analysis_scope()
        run(function.body, environment, frozenset({function_name}), 0)
    for sink_id, sink in dynamic_sinks.items():
        if sink_id not in analyzed_sinks:
            unresolved.setdefault(sink.lineno, set()).add("unknown_target:unvisited_sink_analysis")
    return sorted(targets), sorted(
        (line, reason) for line, reasons in unresolved.items() for reason in reasons
    )


def _runtime_dynamic_import_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(item for item in root.rglob("*.py") if "__pycache__" not in item.parts):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        try:
            relative_path = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        scanner = preflight._DynamicImportSourceScanner(path, relative_path=relative_path)
        try:
            _, sink_sites = scanner.scan_with_sites(tree)
        except preflight.DynamicImportCollectionError as error:
            violations.append(
                f"{relative_path}: unresolved dynamic-import capability source "
                f"({type(error).__name__}: {error})"
            )
            continue

        origins, tainted = _data_forge_alias_origins(tree, sink_sites=sink_sites)
        targets = _literal_dynamic_import_targets(tree, sink_sites=sink_sites)
        abstract_targets, abstract_unresolved = _static_dynamic_import_targets(
            tree,
            module_name=_source_module_name(path),
            sink_sites=sink_sites,
        )
        targets.extend(abstract_targets)
        for line, module_name in targets:
            if _data_forge_dynamic_route_is_forbidden(module_name) or (
                _lex_knowledge_route_is_forbidden(module_name)
            ):
                line_suffix = f":{line}" if line else ""
                violations.append(f"{relative_path}{line_suffix}: {module_name}")

        unresolved_data_forge_lines = {
            site.node.lineno
            for site in sink_sites
            if _dynamic_import_target(site.node) is not None
            and _expression_is_data_forge_derived(
                _dynamic_import_target(site.node), origins, tainted
            )
        }
        forbidden_target_lines = {
            line
            for line, module_name in targets
            if _data_forge_dynamic_route_is_forbidden(module_name)
            or _lex_knowledge_route_is_forbidden(module_name)
        }
        unresolved_by_line: dict[int, set[str]] = {}
        for line, reason in abstract_unresolved:
            unresolved_by_line.setdefault(line, set()).add(reason)
        for line, reasons in sorted(unresolved_by_line.items()):
            if line in forbidden_target_lines:
                continue
            reason_text = ";".join(sorted(reasons))
            if any(reason.startswith("data_forge_route:") for reason in reasons) or (
                line in unresolved_data_forge_lines
            ):
                violations.append(
                    f"{relative_path}:{line}: unresolved Data Forge-derived dynamic target ({reason_text})"
                )
            else:
                violations.append(
                    f"{relative_path}:{line}: unresolved dynamic import target ({reason_text})"
                )

        for site in sink_sites:
            node = site.node
            target = _dynamic_import_target(node)
            if target is None:
                continue
            if not any(
                line == node.lineno for line, _ in abstract_unresolved
            ) and _expression_is_data_forge_derived(target, origins, tainted):
                violations.append(
                    f"{relative_path}:{node.lineno}: unresolved Data Forge-derived dynamic target"
                )
    return sorted(set(violations))


def _source_module_name(path: Path) -> str | None:
    """Derive ``__name__`` from a source path inside the project package tree."""

    source_root = REPO_ROOT / "src"
    try:
        relative = path.resolve().relative_to(source_root)
    except ValueError:
        return None
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or None


def _import_names(node: ast.Import | ast.ImportFrom) -> tuple[str, ...]:
    if isinstance(node, ast.ImportFrom):
        module_name = node.module or ""
        if module_name in {"polisyos.data_forge", "polisyos.lex"}:
            return tuple(f"{module_name}.{alias.name}" for alias in node.names)
        return (module_name,)
    return tuple(alias.name for alias in node.names)
