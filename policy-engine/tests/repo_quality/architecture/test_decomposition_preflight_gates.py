from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tools.quality.validation import decomposition_preflight as preflight
from tools.quality.validation.decomposition_preflight import (
    REPO_ROOT,
    validate_dynamic_imports,
    validate_import_cycles,
    validate_import_time_regression,
    validate_reexport_shim_shapes,
)


def test_dynamic_imports_gate_resolves_registered_targets() -> None:
    findings = validate_dynamic_imports()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_dynamic_imports_gate_rejects_registry_and_target_corruption(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_entries = preflight.collect_dynamic_imports()
    registry_path = tmp_path / "dynamic.toml"
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: source_entries)

    def validate_entries(entries: list[dict[str, object]]):
        registry_path.write_text(
            preflight.render_dynamic_imports_toml(entries),
            encoding="utf-8",
        )
        return preflight.validate_dynamic_imports()

    assert validate_entries(source_entries) == []

    corrupt_field_entries = [
        {**entry, "allowed_targets": list(entry["allowed_targets"])} for entry in source_entries
    ]
    corrupt_field_entries[0]["line"] = int(corrupt_field_entries[0]["line"]) + 100_000
    corrupt_field_findings = validate_entries(corrupt_field_entries)
    assert any(
        finding.message == "dynamic import call is not registered"
        for finding in corrupt_field_findings
    )
    assert any(
        finding.message == "registered dynamic import call no longer exists"
        for finding in corrupt_field_findings
    )

    missing_call_entries = [
        {**entry, "allowed_targets": list(entry["allowed_targets"])} for entry in source_entries
    ]
    missing_call = missing_call_entries.pop(0)
    missing_call_signature = (
        missing_call["source_file"],
        missing_call["line"],
        missing_call["call"],
        missing_call["pattern"],
    )
    missing_call_findings = validate_entries(missing_call_entries)
    assert any(
        finding.message == "dynamic import call is not registered"
        and finding.detail == repr(missing_call_signature)
        for finding in missing_call_findings
    )

    invalid_target_entries = [
        {**entry, "allowed_targets": list(entry["allowed_targets"])} for entry in source_entries
    ]
    target_entry = next(entry for entry in invalid_target_entries if entry["allowed_targets"])
    target_entry["allowed_targets"] = ["polisyos.__not_a_real_dynamic_catalog_target__"]
    target_findings = validate_entries(invalid_target_entries)
    assert any(
        finding.message == "allowed dynamic import target does not resolve"
        for finding in target_findings
    )


def test_import_cycles_gate_allows_only_phase3a_lazy_cycles() -> None:
    findings = validate_import_cycles()

    assert findings == [], "\n".join(finding.render() for finding in findings)



def _write_runtime_import_fixture(
    root: Path,
    sources: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_root = root / "src"
    (src_root / "polisyos" / "foundry").mkdir(parents=True, exist_ok=True)
    for relative_path, source in sources.items():
        path = src_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(preflight, "REPO_ROOT", root)
    monkeypatch.setattr(preflight, "SRC_ROOT", src_root)


def _write_current_full_scc_registry(path: Path) -> str:
    """Register this fixture's canonical full-graph SCC signatures."""
    full_graph = preflight.collect_import_graph()
    assert full_graph["cycles"], "registered-cycle fixture must contain a full-graph SCC"
    registry_text = preflight.render_lazy_toml(full_graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry_text, encoding="utf-8")
    return registry_text


def test_import_cycle_gate_rejects_guard_removal_even_when_markers_remain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)
    assert validate_import_cycles() == []

    source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "if TYPE_ONLY:\n"
        "    pass  # Keep the marker while removing the runtime guard.\n"
        "from polisyos.scientist.b import B\n"
    )
    (tmp_path / "src/polisyos/scientist/a.py").write_text(source, encoding="utf-8")
    findings = validate_import_cycles()
    assert len(findings) == 1
    assert findings[0].message == "registered deferred-cycle signature contains a module-eager cycle"
    assert "polisyos.scientist.a" in findings[0].detail
    assert "polisyos.scientist.b" in findings[0].detail



def test_import_cycle_gate_does_not_trust_shadowed_type_checking_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = {
        "module": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "TYPE_ONLY = True\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
        "class": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "class Scope:\n"
            "    TYPE_ONLY = True\n"
            "    if TYPE_ONLY:\n"
            "        from polisyos.scientist.b import B\n"
        ),
        "called_function": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "def bootstrap():\n"
            "    TYPE_ONLY = True\n"
            "    if TYPE_ONLY:\n"
            "        from polisyos.scientist.b import B\n"
            "bootstrap()\n"
        ),
        "ambiguous_branch": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "if runtime_flag:\n"
            "    TYPE_ONLY = True\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
    }
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)
    for label, a_source in cases.items():
        case_root = tmp_path / label
        _write_runtime_import_fixture(
            case_root,
            {
                "polisyos/scientist/a.py": a_source,
                "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
            },
            monkeypatch,
        )
        _write_current_full_scc_registry(registry)
        findings = validate_import_cycles()
        assert any(
            finding.message == "registered deferred-cycle signature contains a module-eager cycle"
            for finding in findings
        ), label


def test_unused_function_type_checking_binding_does_not_shadow_module_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "def unused():\n"
                "    TYPE_ONLY = True\n"
                "    if TYPE_ONLY:\n"
                "        from polisyos.scientist import deferred_edge\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist import guarded_edge\n"
            ),
            "polisyos/scientist/deferred_edge.py": "Value = object()\n",
            "polisyos/scientist/guarded_edge.py": "Value = object()\n",
        },
        monkeypatch,
    )
    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.guarded_edge") not in edges
    assert ("polisyos.scientist.a", "polisyos.scientist.deferred_edge") not in edges


def test_runtime_import_graph_includes_only_evaluated_function_annotations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = (
        ("eager", False, True),
        ("deferred", True, False),
    )
    for name, future_annotations, expect_cycle in cases:
        root = tmp_path / name
        prefix = "from __future__ import annotations\n" if future_annotations else ""
        _write_runtime_import_fixture(
            root,
            {
                "polisyos/scientist/a.py": (
                    prefix
                    + "def annotation_import():\n"
                    "    from polisyos.scientist import b\n"
                    "    return int\n"
                    "def declared(value: annotation_import()):\n"
                    "    return value\n"
                ),
                "polisyos/scientist/b.py": "from polisyos.scientist.a import declared\n",
            },
            monkeypatch,
        )
        graph = preflight.collect_import_graph(runtime_only=True)
        cycle_modules = {
            module for cycle in graph["cycles"] for module in cycle["modules"]
        }
        has_cycle = {
            "polisyos.scientist.a",
            "polisyos.scientist.b",
        }.issubset(cycle_modules)
        assert has_cycle is expect_cycle, name


def test_function_local_variable_annotations_are_not_evaluated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def annotation_import():\n"
                "    from polisyos.scientist import b\n"
                "    return int\n"
                "def declared():\n"
                "    value: annotation_import()\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import declared\n",
        },
        monkeypatch,
    )
    graph = preflight.collect_import_graph(runtime_only=True)
    cycle_modules = {module for cycle in graph["cycles"] for module in cycle["modules"]}
    assert "polisyos.scientist.a" not in cycle_modules

def test_runtime_import_graph_follows_module_time_calls_and_class_bodies_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist import module_bootstrap\n"
                "def _bootstrap():\n"
                "    from polisyos.scientist import direct_call_edge\n"
                "_bootstrap()\n"
                "def _decorate(value):\n"
                "    from polisyos.scientist import decorator_edge\n"
                "    return value\n"
                "@_decorate\n"
                "def decorated():\n"
                "    return None\n"
                "def _default_factory():\n"
                "    from polisyos.scientist import default_edge\n"
                "    return object()\n"
                "def configured(value=_default_factory()):\n"
                "    return value\n"
                "class Registry:\n"
                "    from polisyos.scientist import class_body_edge\n"
                "def _deferred():\n"
                "    from polisyos.scientist import deferred_edge\n"
                "module_bootstrap.register()\n"
            ),
            "polisyos/scientist/module_bootstrap.py": (
                "def register():\n"
                "    from polisyos.scientist import imported_call_edge\n"
            ),
            "polisyos/scientist/direct_call_edge.py": "from polisyos.scientist.a import _bootstrap\n",
            "polisyos/scientist/decorator_edge.py": "from polisyos.scientist.a import decorated\n",
            "polisyos/scientist/default_edge.py": "from polisyos.scientist.a import configured\n",
            "polisyos/scientist/class_body_edge.py": "from polisyos.scientist.a import Registry\n",
            "polisyos/scientist/imported_call_edge.py": "from polisyos.scientist.a import configured\n",
            "polisyos/scientist/deferred_edge.py": "from polisyos.scientist.a import configured\n",
        },
        monkeypatch,
    )
    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    source_module = "polisyos.scientist.a"
    assert (source_module, "polisyos.scientist.direct_call_edge") in edges
    assert (source_module, "polisyos.scientist.class_body_edge") in edges
    assert (source_module, "polisyos.scientist.default_edge") in edges
    assert (source_module, "polisyos.scientist.module_bootstrap") in edges
    assert ("polisyos.scientist.module_bootstrap", "polisyos.scientist.imported_call_edge") in edges
    assert (source_module, "polisyos.scientist.deferred_edge") not in edges
    assert "polisyos.scientist.deferred_edge" not in {
        module for cycle in graph["cycles"] for module in cycle["modules"]
    }


def test_runtime_import_graph_normalizes_package_import_spellings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edge_sets: list[set[tuple[str, str]]] = []
    for index, import_statement in enumerate(
        (
            "import polisyos.scientist.pkg.child",
            "from polisyos.scientist.pkg import child",
        )
    ):
        root = tmp_path / str(index)
        _write_runtime_import_fixture(
            root,
            {
                "polisyos/scientist/a.py": f"{import_statement}\nValue = object()\n",
                "polisyos/scientist/pkg/__init__.py": "from ..a import Value\n",
                "polisyos/scientist/pkg/child.py": "Value = object()\n",
            },
            monkeypatch,
        )
        graph = preflight.collect_import_graph(runtime_only=True)
        edge_sets.append({(row["source"], row["target"]) for row in graph["edges"]})
    assert edge_sets[0] == edge_sets[1]
    assert ("polisyos.scientist.a", "polisyos.scientist.pkg") in edge_sets[0]
    assert ("polisyos.scientist.a", "polisyos.scientist.pkg.child") in edge_sets[0]




def test_import_cycle_gate_handles_global_and_match_type_checking_rebindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = {
        "global_write": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "def bootstrap():\n"
            "    global TYPE_ONLY\n"
            "    TYPE_ONLY = True\n"
            "bootstrap()\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
        "nested_global_write": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "def set_type_only():\n"
            "    global TYPE_ONLY\n"
            "    TYPE_ONLY = True\n"
            "def bootstrap():\n"
            "    set_type_only()\n"
            "bootstrap()\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
        "match_capture": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "match value:\n"
            "    case TYPE_ONLY:\n"
            "        pass\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
    }
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)
    for label, a_source in cases.items():
        case_root = tmp_path / label
        _write_runtime_import_fixture(
            case_root,
            {
                "polisyos/scientist/a.py": a_source,
                "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
            },
            monkeypatch,
        )
        registry_text = _write_current_full_scc_registry(registry)
        findings = validate_import_cycles()
        assert any(
            finding.message == "registered deferred-cycle signature contains a module-eager cycle"
            for finding in findings
        ), label
        if label != "match_capture":
            edges_before = {
                (row["source"], row["target"])
                for row in preflight.collect_import_graph(runtime_only=True)["edges"]
            }
            assert ("polisyos.scientist.a", "polisyos.scientist.b") in edges_before
            source_path = case_root / "src/polisyos/scientist/a.py"
            source_path.write_text(a_source.replace("bootstrap()\n", "", 1), encoding="utf-8")
            assert "from polisyos.scientist.b import B" in source_path.read_text(encoding="utf-8")
            assert registry.read_text(encoding="utf-8") == registry_text
            edges_after = {
                (row["source"], row["target"])
                for row in preflight.collect_import_graph(runtime_only=True)["edges"]
            }
            assert ("polisyos.scientist.a", "polisyos.scientist.b") not in edges_after
            assert not any(
                finding.message
                == "registered deferred-cycle signature contains a module-eager cycle"
                for finding in validate_import_cycles()
            ), label


def test_runtime_import_graph_revisits_function_after_module_binding_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "def bootstrap():\n"
                "    if TYPE_ONLY:\n"
                "        from polisyos.scientist import edge\n"
                "bootstrap()\n"
                "TYPE_ONLY = True\n"
                "bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import bootstrap\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_resolves_nested_local_calls_by_lexical_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def bootstrap():\n"
                "    def local():\n"
                "        from polisyos.scientist import edge\n"
                "    local()\n"
                "bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import bootstrap\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_joins_all_branch_callable_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "if runtime_flag:\n"
                "    from polisyos.scientist.one import launch as selected\n"
                "else:\n"
                "    from polisyos.scientist.two import launch as selected\n"
                "selected()\n"
            ),
            "polisyos/scientist/one.py": (
                "def launch():\n"
                "    from polisyos.scientist import first_edge\n"
            ),
            "polisyos/scientist/two.py": (
                "def launch():\n"
                "    from polisyos.scientist import second_edge\n"
            ),
            "polisyos/scientist/first_edge.py": "VALUE = 1\n",
            "polisyos/scientist/second_edge.py": "VALUE = 2\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.one", "polisyos.scientist.first_edge") in edges
    assert ("polisyos.scientist.two", "polisyos.scientist.second_edge") in edges


def test_runtime_import_graph_joins_all_branch_local_function_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def left():\n"
                "    from polisyos.scientist import left_edge\n"
                "def right():\n"
                "    from polisyos.scientist import right_edge\n"
                "if runtime_flag:\n"
                "    selected = left\n"
                "else:\n"
                "    selected = right\n"
                "selected()\n"
            ),
            "polisyos/scientist/left_edge.py": "VALUE = 1\n",
            "polisyos/scientist/right_edge.py": "VALUE = 2\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") in edges
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") in edges


def test_runtime_import_graph_resolves_local_class_method_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    @classmethod\n"
                "    def bootstrap(cls):\n"
                "        cls.load()\n"
                "    @classmethod\n"
                "    def load(cls):\n"
                "        from polisyos.scientist import edge\n"
                "Entry.bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_keeps_same_name_branch_definitions_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "if runtime_flag:\n"
                "    def selected():\n"
                "        from polisyos.scientist import edge\n"
                "else:\n"
                "    def selected():\n"
                "        return\n"
                "selected()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import selected\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_resolves_branch_definition_set_across_module_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist.implementation import selected\n"
                "selected()\n"
            ),
            "polisyos/scientist/implementation.py": (
                "if runtime_flag:\n"
                "    def selected():\n"
                "        from polisyos.scientist import edge\n"
                "else:\n"
                "    def selected():\n"
                "        return\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.implementation") in edges
    assert ("polisyos.scientist.implementation", "polisyos.scientist.edge") in edges


def test_runtime_import_graph_resolves_cross_module_source_order_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist.implementation import selected\n"
                "selected()\n"
            ),
            "polisyos/scientist/implementation.py": (
                "def selected():\n"
                "    from polisyos.scientist import edge\n"
                "def selected():\n"
                "    return\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.implementation") in edges
    assert ("polisyos.scientist.implementation", "polisyos.scientist.edge") not in edges


def test_runtime_import_graph_applies_proven_unconditional_definition_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def selected():\n"
                "    from polisyos.scientist import edge\n"
                "def selected():\n"
                "    return\n"
                "selected()\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") not in edges


def test_runtime_import_graph_preserves_class_receiver_in_noarg_nested_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    @classmethod\n"
                "    def bootstrap(cls):\n"
                "        def nested():\n"
                "            cls.load()\n"
                "        nested()\n"
                "    @classmethod\n"
                "    def load(cls):\n"
                "        from polisyos.scientist import edge\n"
                "Entry.bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


@pytest.mark.parametrize(
    "entry_call",
    [
        "Entry().boot()\n",
        "entry = Entry()\nentry.boot()\n",
        "EntryAlias = Entry\nentry = EntryAlias()\nentry.boot()\n",
    ],
)
def test_import_cycle_gate_rejects_named_instance_method_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_call: str,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import edge\n"
                f"{entry_call}"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    findings = validate_import_cycles()

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        and "polisyos.scientist.a" in finding.detail
        and "polisyos.scientist.edge" in finding.detail
        for finding in findings
    )

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n",
        encoding="utf-8",
    )
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_resolves_imported_class_instances_and_constructors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle_modules = [
        "polisyos.scientist.a",
        "polisyos.scientist.implementation",
        "polisyos.scientist.init_edge",
        "polisyos.scientist.method_edge",
        "polisyos.scientist.new_edge",
    ]
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist.implementation import Entry as CandidateEntry\n"
                "candidate = CandidateEntry()\n"
                "candidate.boot()\n"
            ),
            "polisyos/scientist/implementation.py": (
                "class Entry:\n"
                "    def __new__(cls):\n"
                "        from polisyos.scientist import new_edge\n"
                "        return object.__new__(cls)\n"
                "    def __init__(self):\n"
                "        from polisyos.scientist import init_edge\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import method_edge\n"
            ),
            "polisyos/scientist/init_edge.py": "from polisyos.scientist.a import CandidateEntry\n",
            "polisyos/scientist/method_edge.py": "from polisyos.scientist.a import CandidateEntry\n",
            "polisyos/scientist/new_edge.py": "from polisyos.scientist.a import CandidateEntry\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    runtime_graph = preflight.collect_import_graph(runtime_only=True)
    runtime_edges = {(row["source"], row["target"]) for row in runtime_graph["edges"]}
    assert runtime_edges >= {
        ("polisyos.scientist.a", "polisyos.scientist.implementation"),
        ("polisyos.scientist.implementation", "polisyos.scientist.new_edge"),
        ("polisyos.scientist.implementation", "polisyos.scientist.init_edge"),
        ("polisyos.scientist.implementation", "polisyos.scientist.method_edge"),
        ("polisyos.scientist.new_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.init_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.method_edge", "polisyos.scientist.a"),
    }
    findings = validate_import_cycles()
    eager = [
        finding
        for finding in findings
        if finding.message == "registered deferred-cycle signature contains a module-eager cycle"
    ]
    assert len(eager) == 1
    assert all(module in eager[0].detail for module in cycle_modules)

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "from polisyos.scientist.implementation import Entry as CandidateEntry\n",
        encoding="utf-8",
    )
    source_after = (tmp_path / "src/polisyos/scientist/a.py").read_text(encoding="utf-8")
    assert "from polisyos.scientist.implementation import Entry as CandidateEntry" in source_after
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_joins_named_instance_sets_and_follows_both_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Left:\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import left_edge\n"
                "class Right:\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import right_edge\n"
                "if runtime_flag:\n"
                "    selected = Left()\n"
                "else:\n"
                "    selected = Right()\n"
                "selected.boot()\n"
            ),
            "polisyos/scientist/left_edge.py": "from polisyos.scientist.a import Left\n",
            "polisyos/scientist/right_edge.py": "from polisyos.scientist.a import Right\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    findings = validate_import_cycles()
    assert [(finding.message, finding.detail) for finding in findings] == [
        (
            "registered deferred-cycle signature contains a module-eager cycle",
            "polisyos.scientist.a, polisyos.scientist.left_edge, "
            "polisyos.scientist.right_edge",
        )
    ]
    runtime_graph = preflight.collect_import_graph(runtime_only=True)
    eager_targets = {
        edge["target"]
        for edge in runtime_graph["edges"]
        if edge["source"] == "polisyos.scientist.a"
    }
    assert eager_targets == {
        "polisyos.scientist.left_edge",
        "polisyos.scientist.right_edge",
    }

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_text = source_path.read_text(encoding="utf-8")
    source_path.write_text(
        source_text.replace("selected.boot()\n", "", 1), encoding="utf-8"
    )
    source_after = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import left_edge" in source_after
    assert "from polisyos.scientist import right_edge" in source_after
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_follows_source_defined_new_and_init_constructors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    def __new__(cls):\n"
                "        from polisyos.scientist import new_edge\n"
                "        return object.__new__(cls)\n"
                "    def __init__(self):\n"
                "        from polisyos.scientist import init_edge\n"
                "Entry()\n"
            ),
            "polisyos/scientist/new_edge.py": "from polisyos.scientist.a import Entry\n",
            "polisyos/scientist/init_edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    runtime_graph = preflight.collect_import_graph(runtime_only=True)
    runtime_edges = {(row["source"], row["target"]) for row in runtime_graph["edges"]}
    assert runtime_edges >= {
        ("polisyos.scientist.a", "polisyos.scientist.new_edge"),
        ("polisyos.scientist.a", "polisyos.scientist.init_edge"),
        ("polisyos.scientist.new_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.init_edge", "polisyos.scientist.a"),
    }
    findings = validate_import_cycles()
    eager_details = [
        finding.detail
        for finding in findings
        if finding.message == "registered deferred-cycle signature contains a module-eager cycle"
    ]

    assert eager_details == [
        "polisyos.scientist.a, polisyos.scientist.init_edge, polisyos.scientist.new_edge"
    ]

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "class Entry:\n"
        "    def __new__(cls):\n"
        "        from polisyos.scientist import new_edge\n"
        "        return object.__new__(cls)\n"
        "    def __init__(self):\n"
        "        from polisyos.scientist import init_edge\n",
        encoding="utf-8",
    )
    source_after = (tmp_path / "src/polisyos/scientist/a.py").read_text(encoding="utf-8")
    assert "from polisyos.scientist import new_edge" in source_after
    assert "from polisyos.scientist import init_edge" in source_after
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_runtime_import_graph_joins_same_name_branch_class_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    if runtime_flag:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            from polisyos.scientist import edge\n"
                "    else:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            return\n"
                "    @classmethod\n"
                "    def bootstrap(cls):\n"
                "        cls.load()\n"
                "Entry.bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_joins_branch_defined_class_method_sets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "if runtime_flag:\n"
                "    class Entry:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            from polisyos.scientist import edge\n"
                "else:\n"
                "    class Entry:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            return\n"
                "Entry.load()\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges


def test_import_cycle_gate_rejects_new_unregistered_deferred_scc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from polisyos.scientist.a import A\n"
            ),
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text('[lazy_imports]\nversion = 1\n', encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    findings = validate_import_cycles()
    assert any(
        finding.message == "new import cycle without deferred-cycle registration"
        and "polisyos.scientist.a" in finding.detail
        and "polisyos.scientist.b" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize(
    ("bad_bytes", "expected_outcome"),
    [
        (b"def broken(:\n    pass\n", "parse_error"),
        (b"value = \xff\n", "decode_error"),
    ],
)
def test_import_cycle_scan_preserves_partial_cycles_and_parse_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_bytes: bytes,
    expected_outcome: str,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
        },
        monkeypatch,
    )
    bad_path = tmp_path / "src/polisyos/scientist/broken.py"
    bad_path.write_bytes(bad_bytes)
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text(
        '[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n'
        'modules = ["polisyos.scientist.a", "polisyos.scientist.b"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    snapshot = preflight._collect_import_source_snapshot()
    graph = preflight.collect_import_graph(
        source_snapshot=snapshot,
        allow_incomplete=True,
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.b"] in [
        cycle["modules"] for cycle in graph["cycles"]
    ]
    finding = next(
        finding
        for finding in validate_import_cycles(source_snapshot=snapshot)
        if finding.message == "selected source input is incomplete"
    )
    assert "src/polisyos/scientist/broken.py" in finding.detail
    assert f"[{expected_outcome}]" in finding.detail
    manifest_row = next(
        row for row in snapshot.input_manifest if row["path"] == "src/polisyos/scientist/broken.py"
    )
    assert manifest_row["outcome"] == expected_outcome
    assert manifest_row["sha256"] == hashlib.sha256(bad_bytes).hexdigest()


def test_import_cycle_scan_records_portable_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
            "polisyos/scientist/unreadable.py": "VALUE = 1\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text(
        '[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n'
        'modules = ["polisyos.scientist.a", "polisyos.scientist.b"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)
    real_reader = preflight._read_import_source_bytes
    unreadable = tmp_path / "src/polisyos/scientist/unreadable.py"

    def controlled_reader(path: Path) -> bytes:
        if path == unreadable:
            raise OSError("controlled read failure")
        return real_reader(path)

    monkeypatch.setattr(preflight, "_read_import_source_bytes", controlled_reader)
    snapshot = preflight._collect_import_source_snapshot()
    graph = preflight.collect_import_graph(source_snapshot=snapshot, allow_incomplete=True)

    assert ["polisyos.scientist.a", "polisyos.scientist.b"] in [
        cycle["modules"] for cycle in graph["cycles"]
    ]
    finding = next(
        finding
        for finding in validate_import_cycles(source_snapshot=snapshot)
        if finding.message == "selected source input is incomplete"
    )
    assert "src/polisyos/scientist/unreadable.py [read_error]" in finding.detail
    assert "controlled read failure" in finding.detail


def test_gate_cli_emits_complete_import_input_receipt_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": "VALUE = 1\n",
            "polisyos/scientist/b.py": "VALUE = 2\n",
        },
        monkeypatch,
    )
    bad_path = tmp_path / "src/polisyos/scientist/b.py"
    bad_bytes = b"def broken(:\n    pass\n"
    bad_path.write_bytes(bad_bytes)
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text('[lazy_imports]\nversion = 1\n', encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)
    monkeypatch.setattr(preflight, "validate_dynamic_imports", lambda: [])
    monkeypatch.setattr(preflight, "validate_pickle_fixtures", lambda: [])
    monkeypatch.setattr(preflight, "validate_public_surface_snapshot", lambda: [])
    monkeypatch.setattr(preflight, "validate_schema_diff", lambda: [])
    monkeypatch.setattr(preflight, "validate_reexport_shim_shapes", lambda: [])
    monkeypatch.setattr(preflight, "validate_import_time_regression", lambda **_: [])
    output_path = tmp_path / "gate-output.json"

    exit_code = preflight.main(["gate", "--output-json", str(output_path)])

    assert exit_code == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    receipt = payload["import_graph_input_receipt"]
    assert payload["status"] == "failed"
    assert receipt["coverage_status"] == "partial"
    assert receipt["selected_count"] == 2
    assert receipt["outcome_counts"] == {"parse_error": 1, "parsed": 1}
    assert {row["path"] for row in receipt["input_manifest"]} == {
        "src/polisyos/scientist/a.py",
        "src/polisyos/scientist/b.py",
    }
    bad_row = next(row for row in receipt["input_manifest"] if row["path"].endswith("/b.py"))
    assert bad_row["sha256"] == hashlib.sha256(bad_bytes).hexdigest()
    assert bad_row["outcome"] == "parse_error"
    stdout = capsys.readouterr().out
    assert "input_manifest_sha256" in stdout
    assert all(row["path"] in stdout for row in receipt["input_manifest"])
    assert all(row["sha256"] in stdout for row in receipt["input_manifest"])


def test_phase3a_generator_refuses_incomplete_import_input_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {"polisyos/scientist/broken.py": "def broken(:\n    pass\n"},
        monkeypatch,
    )
    generated_root = tmp_path / "generated"
    monkeypatch.setattr(preflight, "BASELINE_DIR", generated_root)

    with pytest.raises(preflight.ImportGraphInputError, match="parse_error"):
        preflight.write_phase3a_artifacts(include_import_time=False)
    assert not generated_root.exists()

    exit_code = preflight.main(["generate", "--skip-import-time"])
    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "NOT generated" in stdout
    assert "src/polisyos/scientist/broken.py" in stdout
    assert "parse_error" in stdout
    assert hashlib.sha256(b"def broken(:\n    pass\n").hexdigest() in stdout
    assert not generated_root.exists()

def test_reexport_shim_shape_gate_forbids_star_import_shims() -> None:
    findings = validate_reexport_shim_shapes()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_import_time_regression_gate_has_phase3a_baseline() -> None:
    baseline = (
        REPO_ROOT
        / "architecture"
        / "baselines"
        / "structure_remediation"
        / "import_time_pre_decomp.json"
    )

    assert baseline.exists()
    if os.environ.get("POLISYOS_RUN_IMPORT_TIME_GATE") == "1":
        findings = validate_import_time_regression(live=True)
        assert findings == [], "\n".join(finding.render() for finding in findings)


def test_phase5_scientist_root_facade_has_no_loose_python_modules() -> None:
    scientist_root = REPO_ROOT / "src" / "polisyos" / "scientist"
    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text())
    registered_root_shims = {
        Path(shim["source_path"]).name
        for shim in shims["shim"]
        if shim.get("type") == "python_reexport"
        and Path(shim.get("source_path", "")).parent == Path("src/polisyos/scientist")
    }
    root_py_files = sorted(path.name for path in scientist_root.glob("*.py"))
    non_shim_root_py_files = [name for name in root_py_files if name not in registered_root_shims]
    top_level_entries = [path for path in scientist_root.iterdir() if path.name != "__pycache__"]
    gate_result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "loose_files",
            "--mode",
            "fail-closed",
            "--package",
            "scientist",
            "--scope",
            "root",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert non_shim_root_py_files == ["__init__.py", "api.py"]
    assert len(top_level_entries) <= 250
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr


def test_phase6_foundry_root_facade_stays_within_loose_python_budget() -> None:
    foundry_root = REPO_ROOT / "src" / "polisyos" / "foundry"
    root_py_files = sorted(path.name for path in foundry_root.glob("*.py"))
    top_level_entries = [path for path in foundry_root.iterdir() if path.name != "__pycache__"]
    gate_result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "loose_files",
            "--mode",
            "fail-closed",
            "--package",
            "foundry",
            "--scope",
            "root",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert "__init__.py" in root_py_files
    assert "api.py" in root_py_files
    assert len(root_py_files) <= 5
    assert len(top_level_entries) <= 250
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr


def test_import_graph_baseline_records_phase3a_collector_contract() -> None:
    baseline = json.loads(
        (
            REPO_ROOT
            / "architecture"
            / "baselines"
            / "structure_remediation"
            / "import_graph_pre_decomp.json"
        ).read_text(encoding="utf-8")
    )

    assert baseline["collector_mode"] == "internal_ast_import_graph"
    assert "pydeps_available" in baseline
    assert "import_linter_available" in baseline


def test_pickle_inventory_includes_canonical_checkpoint_fixtures() -> None:
    inventory = json.loads(
        (
            REPO_ROOT
            / "architecture"
            / "baselines"
            / "structure_remediation"
            / "pickle_checkpoint_inventory.json"
        ).read_text(encoding="utf-8")
    )
    artifacts = {artifact["path"] for artifact in inventory["live_artifacts"]}
    manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((REPO_ROOT / "tests" / "_data" / "checkpoint_compat").glob("*/*.json"))
    ]

    assert "tests/_data/checkpoint_compat/foundry/agent_sim_experiment_result.pkl" in artifacts
    assert "tests/_data/checkpoint_compat/scientist/engine_checkpoint_artifact.pkl" in artifacts
    assert {manifest["producer"] for manifest in manifests} == {
        "polisyos.foundry.agent_sim.experiment.ExperimentRun.log_artifact",
        "polisyos.scientist.orchestration.engine.checkpoint.create_checkpoint/load_checkpoint",
    }


def test_phase3a_gate_registry_lists_new_decomposition_gates() -> None:
    gates = tomllib.loads(
        (REPO_ROOT / "architecture" / "gates" / "structure_remediation.toml").read_text(
            encoding="utf-8"
        )
    )
    gate_ids = {gate["id"] for gate in gates["gate"]}

    assert {
        "dynamic_imports_gate",
        "pickle_compat_gate",
        "public_surface_snapshot_gate",
        "import_cycles_gate",
        "import_time_regression_gate",
        "reexport_shim_shape_gate",
    } <= gate_ids


def test_phase4_1_foundry_executor_lane_closes_legacy_private_siblings() -> None:
    foundry_root = REPO_ROOT / "src" / "polisyos" / "foundry"
    removed_private_siblings = {
        "_execution_posture",
        "_executor_graph",
        "_executor_models",
        "_executor_ops",
        "_executor_patching",
        "_executor_snapshots",
        "_numeric",
    }

    assert {
        path.name for path in foundry_root.iterdir() if path.name in removed_private_siblings
    } == set()

    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text(encoding="utf-8"))[
        "shim"
    ]
    shim_sources = {shim["source_path"] for shim in shims}
    dynamic_sources = {
        entry["source_file"]
        for entry in tomllib.loads(
            (REPO_ROOT / "architecture" / "imports" / "dynamic.toml").read_text(encoding="utf-8")
        )["pattern"]
    }
    removed_source_paths = {
        f"src/polisyos/foundry/{name}/__init__.py" for name in removed_private_siblings
    }
    executor_cycle_markers = (
        "polisyos.foundry.execute",
        "polisyos.foundry.runtime.numeric",
    )

    assert shim_sources.isdisjoint(removed_source_paths)
    assert dynamic_sources.isdisjoint(removed_source_paths)
    assert [
        finding
        for finding in validate_dynamic_imports()
        if "src/polisyos/foundry/execute" in finding.detail
        or "src/polisyos/foundry/executor" in finding.detail
        or any(path in finding.detail for path in removed_source_paths)
    ] == []
    assert [
        finding
        for finding in validate_import_cycles()
        if any(marker in finding.detail for marker in executor_cycle_markers)
    ] == []


def test_move_module_codemod_dry_run_plans_synthetic_world_move() -> None:
    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(script),
            "--from",
            "polisyos.foundry.agent_sim.world.world",
            "--to",
            "polisyos.foundry.agent_sim.world.runtime.world",
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "polisyos.foundry.agent_sim.world.runtime.world" in result.stdout
    assert '"src/polisyos/foundry/agent_sim/world/runtime/__init__.py"' in result.stdout


def test_move_module_codemod_rewrites_parent_leaf_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "polisyos" / "example"
    source_dir.mkdir(parents=True)
    (repo / "architecture").mkdir()
    (repo / "src" / "polisyos" / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "old.py").write_text("class Public:\n    pass\n", encoding="utf-8")
    (source_dir / "consumer.py").write_text(
        "from polisyos.example import old\nfrom polisyos.example.old import Public\n",
        encoding="utf-8",
    )
    (repo / "architecture" / "shims.toml").write_text("", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)

    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo-root",
            str(repo),
            "--from",
            "polisyos.example.old",
            "--to",
            "polisyos.example.new.old",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (source_dir / "new" / "__init__.py").exists()
    assert (source_dir / "new" / "old.py").exists()
    assert "from polisyos.example.new import old" in (source_dir / "consumer.py").read_text(
        encoding="utf-8"
    )
    assert "from polisyos.example.new.old import Public" in (source_dir / "consumer.py").read_text(
        encoding="utf-8"
    )
    assert not (source_dir / "old.py").exists()
    shim = (source_dir / "old" / "__init__.py").read_text(encoding="utf-8")
    assert "import *" not in shim


@pytest.mark.skipif(os.name != "posix", reason="POSIX subprocess lookup honors cwd for PATH entries")
@pytest.mark.parametrize(
    ("path_mode", "expected_shim"),
    [
        ("relative", "repo-bin"),
        ("empty", "repo-root"),
        ("absolute", "absolute-first"),
        ("unset", None),
    ],
)
def test_move_module_git_lookup_preserves_child_cwd_path_search(
    tmp_path: Path, path_mode: str, expected_shim: str | None
) -> None:
    real_git_command = shutil.which("git")
    if real_git_command is None:
        pytest.skip("git is required for the move-module integration test")
    real_git = str(Path(real_git_command).resolve(strict=True))
    if path_mode == "unset" and shutil.which("git", path=os.defpath) is None:
        pytest.skip("git is not available on the platform default PATH")

    repo = tmp_path / "repo"
    caller = tmp_path / "caller"
    caller.mkdir()
    source_dir = repo / "src" / "polisyos" / "example"
    source_dir.mkdir(parents=True)
    (repo / "architecture").mkdir()
    (repo / "src" / "polisyos" / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "old.py").write_text("class Public:\n    pass\n", encoding="utf-8")
    (repo / "architecture" / "shims.toml").write_text("", encoding="utf-8")

    marker = tmp_path / "selected-git-shim.txt"

    def install_git_shim(directory: Path, label: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        executable = directory / "git"
        executable.write_text(
            "#!/bin/sh\n"
            f"printf '%s' {shlex.quote(label)} > \"$GIT_SHIM_MARKER\"\n"
            f"exec {shlex.quote(real_git)} \"$@\"\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)

    env = os.environ.copy()
    env["GIT_SHIM_MARKER"] = str(marker)
    if path_mode == "relative":
        install_git_shim(repo / "bin", "repo-bin")
        install_git_shim(caller / "bin", "caller-bin")
        env["PATH"] = "bin"
    elif path_mode == "empty":
        install_git_shim(repo, "repo-root")
        install_git_shim(caller, "caller-root")
        env["PATH"] = ""
    elif path_mode == "absolute":
        install_git_shim(repo / "absolute-first", "absolute-first")
        install_git_shim(caller / "absolute-second", "absolute-second")
        env["PATH"] = os.pathsep.join(
            (str(repo / "absolute-first"), str(caller / "absolute-second"))
        )
    else:
        env.pop("PATH", None)

    subprocess.run([real_git, "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run([real_git, "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo-root",
            str(repo),
            "--from",
            "polisyos.example.old",
            "--to",
            "polisyos.example.new.old",
        ],
        cwd=caller,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (repo / "src" / "polisyos" / "example" / "new" / "old.py").exists()
    if expected_shim is None:
        assert not marker.exists()
    else:
        assert marker.read_text(encoding="utf-8") == expected_shim


@pytest.mark.parametrize(
    ("scenario", "class_source", "property_call", "expected_reason"),
    [
        (
            "factory_return",
            "class Entry:\n"
            "    def boot(self):\n"
            "        from polisyos.scientist import edge\n"
            "def make():\n"
            "    return Entry()\n",
            "make().boot()",
            "source_callable_return_not_summarized",
        ),
        (
            "custom_new_replacement",
            "class Replacement:\n"
            "    def boot(self):\n"
            "        from polisyos.scientist import edge\n"
            "class Entry:\n"
            "    def __new__(cls):\n"
            "        return Replacement()\n",
            "Entry().boot()",
            "source_derived_receiver_not_summarized",
        ),
    ],
)
def test_import_cycle_gate_fails_closed_for_unresolved_source_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    class_source: str,
    property_call: str,
    expected_reason: str,
) -> None:
    a_source = (
        class_source
        + "class ResolvedReceiver:\n"
        + "    def ping(self):\n"
        + "        return None\n"
        + property_call
        + "\nResolvedReceiver().ping()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    eager_graph = preflight.collect_import_graph(runtime_only=True)
    receipt = eager_graph["dispatch_resolution"]
    assert receipt["status"] == "not_established", scenario
    assert receipt["unmodeled_dispatch_forms"] == [
        {
            "form": "reflective_or_callback_valued_receiver",
            "status": "not_established",
            "reason": "no source-resolved target is available for enumeration",
        }
    ], scenario
    assert receipt["unresolved_count"] == 1, scenario
    assert receipt["resolved_count"] == 1, scenario
    assert {row["status"] for row in receipt["observations"]} == {
        "resolved",
        "not_established",
    }, scenario
    unresolved = receipt["unresolved"][0]
    assert unresolved["status"] == "not_established", scenario
    assert unresolved["source_path"] == "src/polisyos/scientist/a.py", scenario
    assert unresolved["expression"] == property_call, scenario
    assert unresolved["reason"] == expected_reason, scenario

    full_graph = preflight.collect_import_graph()
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in full_graph["cycles"]
    ], scenario
    findings = validate_import_cycles()
    unresolved_findings = [
        finding
        for finding in findings
        if finding.message == "module-time source-known dispatch is not established"
    ]
    assert len(unresolved_findings) == 1, scenario
    assert expected_reason in unresolved_findings[0].detail, scenario

    # Remove only the module-time dispatch. The cycle source, reciprocal edge, and
    # exact deferred-SCC registration remain in place as the negative control.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace(property_call + "\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after_graph = preflight.collect_import_graph(runtime_only=True)
    after_receipt = after_graph["dispatch_resolution"]
    assert after_receipt["status"] == "resolved_within_scope", scenario
    assert after_receipt["unresolved_count"] == 0, scenario
    assert after_receipt["resolved_count"] == 1, scenario
    assert after_receipt["observations"][0]["status"] == "resolved", scenario
    assert after_receipt["unresolved"] == [], scenario
    assert validate_import_cycles() == [], scenario
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ], scenario


def test_import_cycle_gate_resolves_source_inherited_method_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Base:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Entry(Base):\n"
        "    pass\n"
        "Entry().boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    inherited = next(
        row for row in receipt["observations"] if row["expression"] == "Entry().boot()"
    )
    assert inherited["status"] == "resolved"
    assert any(
        target.startswith("polisyos.scientist.a.Base.boot@")
        for target in inherited["known_source_targets"]
    )
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in {
        (row["source"], row["target"]) for row in graph["edges"]
    }
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    # Remove only the inherited method invocation; keep both import markers and
    # the exact full-AST SCC registration to prove the gate's runtime edge.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Entry().boot()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") not in {
        (row["source"], row["target"]) for row in after["edges"]
    }
    assert after["dispatch_resolution"]["unresolved"] == []
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


@pytest.mark.parametrize(
    ("binding_setup", "property_call"),
    [
        ("", "make().child.boot()"),
        ("selected = make()\n", "selected.child.boot()"),
        ("selected = [make()]\n", "selected[0].boot()"),
        (
            "if runtime_flag:\n    selected = Entry()\n"
            "else:\n    selected = make()\n",
            "selected.boot()",
        ),
        (
            "class Namespace:\n    selected = make()\n",
            "Namespace.selected.child.boot()",
        ),
    ],
)
def test_import_cycle_gate_preserves_source_origins_through_expression_transforms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    binding_setup: str,
    property_call: str,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make():\n"
        "    return Entry()\n"
        "runtime_flag = False\n"
        + binding_setup
        + property_call
        + "\n"
    )
    edge_source = "from polisyos.scientist.a import make\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == property_call
    )
    assert receipt["status"] == "not_established"
    assert unresolved["reason"] in {
        "source_callable_return_not_summarized",
        "source_derived_receiver_not_summarized",
    }
    assert unresolved["source_path"] == "src/polisyos/scientist/a.py"
    if "selected = Entry()" in binding_setup:
        assert any(
            target.startswith("polisyos.scientist.a.Entry.boot@")
            for target in unresolved["known_source_targets"]
        )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace(property_call + "\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(
        encoding="utf-8"
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved"] == []
    assert after["status"] == "resolved_within_scope"
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]



@pytest.mark.parametrize(
    ("setup", "property_statement", "without_property_statement", "property_call"),
    [
        (
            "selected = [(make(), None)]\n",
            "for item, ignored in selected:\n    item.boot()\n",
            "for item, ignored in selected:\n    pass\n",
            "item.boot()",
        ),
        (
            "import asyncio\n"
            "async def values():\n    yield make()\n"
            "async def exercise():\n",
            "    async for item in values():\n        item.boot()\n"
            "asyncio.run(exercise())\n",
            "    async for item in values():\n        pass\n"
            "asyncio.run(exercise())\n",
            "item.boot()",
        ),
        (
            "",
            "with Manager() as item:\n    item.boot()\n",
            "with Manager() as item:\n    pass\n",
            "item.boot()",
        ),
        (
            "import asyncio\nasync def exercise():\n",
            "    async with AsyncManager() as item:\n        item.boot()\n"
            "asyncio.run(exercise())\n",
            "    async with AsyncManager() as item:\n        pass\n"
            "asyncio.run(exercise())\n",
            "item.boot()",
        ),
        (
            "",
            "try:\n    pass\nexcept EntryError as item:\n    item.boot()\n",
            "try:\n    pass\nexcept EntryError as item:\n    pass\n",
            "item.boot()",
        ),
        (
            "",
            "match make():\n    case item:\n        item.boot()\n",
            "match make():\n    case item:\n        pass\n",
            "item.boot()",
        ),
        (
            "",
            "match [make()]:\n    case [item]:\n        item.boot()\n",
            "match [make()]:\n    case [item]:\n        pass\n",
            "item.boot()",
        ),
        (
            "selected = [make()]\n",
            "selected += []\nselected[0].boot()\n",
            "selected += []\nselected[0]\n",
            "selected[0].boot()",
        ),
        (
            "selected: list[object] = [make()]\n",
            "selected[0].boot()\n",
            "selected[0]\n",
            "selected[0].boot()",
        ),
        (
            "",
            "if (selected := [make()]):\n    selected[0].boot()\n",
            "if (selected := [make()]):\n    selected[0]\n",
            "selected[0].boot()",
        ),
        (
            "class KnownOwner:\n    def ready(self):\n        return None\n"
            "holder = KnownOwner()\nholder.value = make()\n",
            "holder.ready()\nholder.value.boot()\n",
            "holder.ready()\nholder.value\n",
            "holder.value.boot()",
        ),
        (
            "holder = {}\nholder['value'] = make()\n",
            "holder['value'].boot()\n",
            "holder['value']\n",
            "holder['value'].boot()",
        ),
        (
            "from types import SimpleNamespace\n",
            "SimpleNamespace().value = make()\n",
            "pass\n",
            "SimpleNamespace().value",
        ),
        (
            "",
            "calls = {0: item.boot() for item in [make()]}\n",
            "calls = {0: item for item in [make()]}\n",
            "item.boot()",
        ),
        (
            "",
            "calls = [item.boot() for item in [make()]]\nitem.boot()\n",
            "calls = [item for item in [make()]]\nitem.boot()\n",
            "item.boot()",
        ),
    ],
)
def test_import_cycle_gate_preserves_provenance_at_unknown_binding_sinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    setup: str,
    property_statement: str,
    without_property_statement: str,
    property_call: str,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make():\n"
        "    return Entry()\n"
        "class Manager:\n"
        "    def __enter__(self):\n"
        "        return Entry()\n"
        "    def __exit__(self, *args):\n"
        "        return False\n"
        "class AsyncManager:\n"
        "    async def __aenter__(self):\n"
        "        return Entry()\n"
        "    async def __aexit__(self, *args):\n"
        "        return False\n"
        "class EntryError(Exception):\n"
        "    pass\n"
        + setup
        + property_statement
    )
    edge_source = "from polisyos.scientist.a import make\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    unresolved = [
        row for row in receipt["unresolved"] if row["expression"] == property_call
    ]
    assert len(unresolved) == 1
    assert receipt["status"] == "not_established"
    assert unresolved[0]["reason"] in {
        "source_callable_return_not_summarized",
        "source_derived_receiver_not_summarized",
        "source_derived_binding_target_not_summarized",
    }
    if "holder = KnownOwner()" in setup:
        ready = next(
            row
            for row in receipt["observations"]
            if row["expression"] == "holder.ready()"
        )
        assert ready["status"] == "resolved"
        assert any(
            target.startswith("polisyos.scientist.a.KnownOwner.ready@")
            for target in ready["known_source_targets"]
        )
    assert unresolved[0]["source_path"] == "src/polisyos/scientist/a.py"
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace(property_statement, without_property_statement, 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import edge" in source_path.read_text(
        encoding="utf-8"
    )
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(
        encoding="utf-8"
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved"] == []
    assert after["status"] == "resolved_within_scope"
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_rejects_rebound_method_receiver_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def boot(self):\n"
        "        def nested():\n"
        "            self = make()\n"
        "            self.load()\n"
        "        nested()\n"
        "    def load(self):\n"
        "        return None\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make():\n"
        "    return Replacement()\n"
        "Entry().boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert receipt["status"] == "not_established"
    assert receipt["resolved_count"] == 1
    assert receipt["unresolved_count"] == 1
    unresolved = receipt["unresolved"][0]
    assert unresolved["expression"] == "self.load()"
    assert unresolved["reason"] == "source_callable_return_not_summarized"
    assert not any(
        target.startswith("polisyos.scientist.a.make@")
        for target in unresolved["known_source_targets"]
    )
    assert any(
        origin.startswith("polisyos.scientist.a.make@")
        for origin in unresolved["source_value_origins"]
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]
    findings = validate_import_cycles()
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "source_callable_return_not_summarized" in finding.detail
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("            self.load()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["status"] == "resolved_within_scope"
    assert after["unresolved_count"] == 0
    assert after["resolved_count"] == 1
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_executes_both_joined_known_receiver_methods_and_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import left_edge\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import right_edge\n"
        "def nested(flag, inherited):\n"
        "    if flag:\n"
        "        selected = Entry()\n"
        "    else:\n"
        "        selected = inherited\n"
        "    selected.load()\n"
        "nested(False, Replacement())\n"
    )
    left_edge_source = "from polisyos.scientist.a import Entry\n"
    right_edge_source = "from polisyos.scientist.a import Replacement\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/left_edge.py": left_edge_source,
            "polisyos/scientist/right_edge.py": right_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert before["dispatch_resolution"]["status"] == "resolved_within_scope"
    assert before["dispatch_resolution"]["unresolved"] == []
    assert {
        ("polisyos.scientist.a", "polisyos.scientist.left_edge"),
        ("polisyos.scientist.a", "polisyos.scientist.right_edge"),
        ("polisyos.scientist.left_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.right_edge", "polisyos.scientist.a"),
    } <= edges_before
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("    selected.load()\n", "    pass\n", 1), encoding="utf-8"
    )
    source_after = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import left_edge" in source_after
    assert "from polisyos.scientist import right_edge" in source_after
    assert left_edge_source == (tmp_path / "src/polisyos/scientist/left_edge.py").read_text(
        encoding="utf-8"
    )
    assert right_edge_source == (tmp_path / "src/polisyos/scientist/right_edge.py").read_text(
        encoding="utf-8"
    )
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_after
    assert ("polisyos.scientist.left_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.right_edge", "polisyos.scientist.a") in edges_after
    assert after["dispatch_resolution"]["unresolved"] == []
    assert validate_import_cycles() == []


def test_import_cycle_gate_binds_callee_before_argument_side_effects_and_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def first():\n"
        "    global handler\n"
        "    handler = replacement\n"
        "    return None\n"
        "def handler(value=None):\n"
        "    from polisyos.scientist import first_edge\n"
        "def replacement(value=None):\n"
        "    from polisyos.scientist import second_edge\n"
        "handler(first())\n"
        "handler()\n"
    )
    first_edge_source = "from polisyos.scientist.a import handler\n"
    second_edge_source = "from polisyos.scientist.a import replacement\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/first_edge.py": first_edge_source,
            "polisyos/scientist/second_edge.py": second_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.first_edge") in edges_before
    assert ("polisyos.scientist.a", "polisyos.scientist.second_edge") in edges_before
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    after_source = a_source.replace("handler(first())\n", "", 1)
    after_source = after_source.replace("handler()\n", "replacement()\n", 1)
    source_path.write_text(after_source, encoding="utf-8")
    source_after = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import first_edge" in source_after
    assert "from polisyos.scientist import second_edge" in source_after
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.first_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.second_edge") in edges_after
    assert ("polisyos.scientist.first_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.second_edge", "polisyos.scientist.a") in edges_after

def test_import_cycle_gate_rejects_unresolved_source_base_constructor_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Base:\n"
        "    def __init__(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Entry(Base):\n"
        "    pass\n"
        "Entry()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert receipt["status"] == "not_established"
    assert receipt["unresolved_count"] == 1
    unresolved = receipt["unresolved"][0]
    assert unresolved["expression"] == "Entry()"
    assert unresolved["reason"] == "source_class_base_constructor_lookup_not_summarized"
    assert any(
        target.startswith("polisyos.scientist.a.Base.__init__@")
        for target in unresolved["known_source_targets"]
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]
    findings = validate_import_cycles()
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "source_class_base_constructor_lookup_not_summarized" in finding.detail
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Entry()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["status"] == "resolved_within_scope"
    assert after["unresolved_count"] == 0
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_rejects_joined_known_and_unknown_receiver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def load(self):\n"
        "        return None\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import edge\n"
        "def nested(flag, inherited):\n"
        "    if flag:\n"
        "        selected = Entry()\n"
        "    else:\n"
        "        selected = inherited\n"
        "    selected.load()\n"
        "def source_factory():\n"
        "    return Replacement()\n"
        "nested(False, source_factory())\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert receipt["status"] == "not_established"
    assert receipt["unresolved_count"] == 1
    unresolved = receipt["unresolved"][0]
    assert unresolved["source_path"] == "src/polisyos/scientist/a.py"
    assert unresolved["expression"] == "selected.load()"
    assert unresolved["reason"] in {
        "source_possible_unknown_target",
        "source_callable_return_not_summarized",
    }
    assert any(
        target.startswith("polisyos.scientist.a.Entry.load@")
        for target in unresolved["known_source_targets"]
    )
    full_graph = preflight.collect_import_graph()
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in full_graph["cycles"]
    ]
    findings = validate_import_cycles()
    assert any(
        finding.gate == "import_cycles_gate"
        and finding.message == "module-time source-known dispatch is not established"
        and unresolved["source_path"] in finding.detail
        and unresolved["expression"] in finding.detail
        and f"[{unresolved['reason']}]" in finding.detail
        for finding in findings
    )

    # Keep both imports and the exact SCC registration while removing only the
    # dispatch whose joined binding carries an unknown possibility.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("    selected.load()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert after["unresolved"] == []
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]



def test_import_cycle_gate_preserves_complete_exported_member_knowledge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def inert():\n"
        "    return None\n"
        "class Handler:\n"
        "    def __call__(self):\n"
        "        from polisyos.scientist import edge\n"
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "def invoke_callback(callback):\n"
        "    callback()\n"
        "runtime_flag = False\n"
        "class Entry:\n"
        "    if runtime_flag:\n"
        "        load = inert\n"
        "    else:\n"
        "        load = Handler()\n"
    )
    relay_source = "from polisyos.scientist.a import Entry as RoutedEntry\n"
    caller_source = (
        "from polisyos.scientist.relay import RoutedEntry\n"
        "from polisyos.scientist.a import Handler\n"
        "def inert():\n"
        "    return None\n"
        "class Opaque:\n"
        "    pass\n"
        "runtime_flag = False\n"
        "class Partial:\n"
        "    if runtime_flag:\n"
        "        load = inert\n"
        "    else:\n"
        "        load = Opaque()\n"
        "RoutedEntry().load()\n"
        "Handler()()\n"
        "Partial().load()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/relay.py": relay_source,
            "polisyos/scientist/caller.py": caller_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    routed = next(
        row for row in receipt["observations"] if row["expression"] == "RoutedEntry().load()"
    )
    assert routed["status"] == "resolved"
    assert any(
        target.startswith("polisyos.scientist.a.Handler.__call__@")
        for target in routed["known_source_targets"]
    )
    direct = next(
        row for row in receipt["observations"] if row["expression"] == "Handler()()"
    )
    assert direct["status"] == "resolved"
    partial = next(
        row for row in receipt["unresolved"] if row["expression"] == "Partial().load()"
    )
    assert partial["reason"] == "source_member_call_target_not_summarized"
    assert any(
        target.startswith("polisyos.scientist.caller.inert@")
        for target in partial["known_source_targets"]
    )
    assert {
        (row["source"], row["target"]) for row in graph["edges"]
    } >= {
        ("polisyos.scientist.a", "polisyos.scientist.edge"),
        ("polisyos.scientist.caller", "polisyos.scientist.a"),
    }
    findings = validate_import_cycles()
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in findings
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "Partial().load()" in finding.detail
        for finding in findings
    )
    full_graph = preflight.collect_import_graph()
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in full_graph["cycles"]
    ]

    # Remove only the actual source calls. Keep the class-suite candidates, both
    # import markers, and the exact deferred-SCC registration intact.
    source_path = tmp_path / "src/polisyos/scientist/caller.py"
    after_source = caller_source.replace("RoutedEntry().load()\n", "", 1).replace(
        "Handler()()\n", "", 1
    ).replace("Partial().load()\n", "", 1)
    source_path.write_text(after_source, encoding="utf-8")
    edge_marker = (tmp_path / "src/polisyos/scientist/a.py").read_text(
        encoding="utf-8"
    )
    assert "from polisyos.scientist import edge" in edge_marker
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(
        encoding="utf-8"
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert after["dispatch_resolution"]["unresolved_count"] == 0
    assert after["dispatch_resolution"]["status"] == "resolved_within_scope"
    assert after["dispatch_resolution"]["unresolved"] == []
    assert not any(
        row["source"] == "polisyos.scientist.a"
        and row["target"] == "polisyos.scientist.edge"
        for row in after["edges"]
    )
    # Removing the three actual dispatches leaves the callback and __call__
    # import markers plus the same SCC registry, but no eager source edge.
    assert "from polisyos.scientist import edge" in edge_marker
    assert "def __call__(self):" in edge_marker
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"]
        for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_binds_callback_arguments_across_signature_forms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "def invoke_posonly(callback, /):\n"
        "    callback()\n"
        "def invoke_keyword_only(*, callback):\n"
        "    callback()\n"
        "def invoke_varargs(*callbacks):\n"
        "    callbacks[0]()\n"
        "def invoke_kwargs(**callbacks):\n"
        "    callbacks[\"callback\"]()\n"
        "invoke_posonly(callback_target)\n"
        "invoke_keyword_only(callback=callback_target)\n"
        "invoke_varargs(*(callback_target,))\n"
        "invoke_kwargs(**{\"callback\": callback_target})\n"
    )
    edge_source = "from polisyos.scientist.a import callback_target\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    callback_rows = [
        row
        for row in receipt["unresolved"]
        if row["reason"] == "source_callback_argument_not_summarized"
    ]
    assert receipt["unresolved_count"] == 2
    assert len(callback_rows) == 2
    assert all(row["status"] == "not_established" for row in callback_rows)
    assert {
        row["expression"].split("(", maxsplit=1)[0] for row in callback_rows
    } == {"invoke_varargs", "invoke_kwargs"}
    assert all(
        any(
            target.startswith("polisyos.scientist.a.callback_target@")
            for target in row["known_source_targets"]
        )
        for row in callback_rows
    )
    assert any(
        row["source"] == "polisyos.scientist.a"
        and row["target"] == "polisyos.scientist.edge"
        for row in preflight.collect_import_graph(runtime_only=True)["edges"]
    )

    # Remove only the actual callback calls, preserving the callback's import
    # marker, its source consumer, and the exact deferred-cycle registration.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    after_source = a_source
    for call in (
        "invoke_posonly(callback_target)\n",
        "invoke_keyword_only(callback=callback_target)\n",
        "invoke_varargs(*(callback_target,))\n",
        'invoke_kwargs(**{\"callback\": callback_target})\n',
    ):
        after_source = after_source.replace(call, "", 1)
    source_path.write_text(after_source, encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(
        encoding="utf-8"
    )
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(
        encoding="utf-8"
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert after["unresolved"] == []
    assert validate_import_cycles() == []


def test_import_cycle_gate_uses_definition_time_callback_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "def inert():\n"
        "    return None\n"
        "positional_capture = callback_target\n"
        "def invoke_positional(request, callback=positional_capture, /):\n"
        "    callback()\n"
        "positional_capture = inert\n"
        "keyword_capture = callback_target\n"
        "def invoke_keyword_only(*, mode, callback=keyword_capture):\n"
        "    callback()\n"
        "keyword_capture = inert\n"
    )
    caller_source = (
        "from polisyos.scientist.a import inert, invoke_positional, invoke_keyword_only\n"
        "invoke_positional(None)\n"
        "invoke_positional(None, inert)\n"
        "invoke_keyword_only(mode='run')\n"
    )
    edge_source = "from polisyos.scientist.a import callback_target\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/caller.py": caller_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    callbacks = [
        row
        for row in receipt["unresolved"]
        if row["reason"] == "source_callback_argument_not_summarized"
    ]
    assert callbacks == []
    assert receipt["unresolved_count"] == 0
    assert any(
        row["source"] == "polisyos.scientist.a"
        and row["target"] == "polisyos.scientist.edge"
        for row in preflight.collect_import_graph(runtime_only=True)["edges"]
    )
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    # Definition-time defaults keep the original callback after the names used
    # to construct them are rebound. Remove only the calls; retain both default
    # expressions, callback import markers, and the registered deferred SCC.
    after_source = (
        caller_source.replace("invoke_positional(None)\n", "", 1)
        .replace("invoke_positional(None, inert)\n", "", 1)
        .replace("invoke_keyword_only(mode='run')\n", "", 1)
    )
    caller_path = tmp_path / "src/polisyos/scientist/caller.py"
    caller_path.write_text(after_source, encoding="utf-8")
    assert "from polisyos.scientist import edge" in (
        tmp_path / "src/polisyos/scientist/a.py"
    ).read_text(encoding="utf-8")
    assert "from polisyos.scientist.a import inert" in caller_path.read_text(
        encoding="utf-8"
    )
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(
        encoding="utf-8"
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert after["unresolved"] == []
    assert validate_import_cycles() == []


def test_import_cycle_gate_tracks_member_values_by_shared_owner_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "from builtins import setattr as write_member\n"
        "class Holder:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "holder_alias = Holder\n"
        "stable_owner = holder_alias\n"
        "holder_alias = object()\n"
        "runtime_flag = False\n"
        "if runtime_flag:\n"
        "    stable_owner.item = Entry()\n"
        "else:\n"
        "    write_member(Holder, \"item\", Entry())\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    dispatch = next(
        row for row in receipt["observations"] if row["expression"] == "Holder.item.boot()"
    )
    assert dispatch["status"] == "resolved"
    assert any(
        target.startswith("polisyos.scientist.a.Entry.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in {
        (row["source"], row["target"]) for row in graph["edges"]
    }
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    # Remove only the dispatch; retain the alias chain, both branch writes, the
    # method's source import marker, and the exact deferred-SCC registration.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Holder.item.boot()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert validate_import_cycles() == []


def test_import_cycle_gate_joins_possible_owner_member_mutator_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "from builtins import setattr as write_member\n"
        "class Prior:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Holder:\n"
        "    item = Prior()\n"
        "def noop(owner, name, value):\n"
        "    return None\n"
        "runtime_flag = False\n"
        "if runtime_flag:\n"
        "    write_member = noop\n"
        "write_member(Holder, \"item\", Entry())\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    dispatch = next(
        row for row in receipt["observations"] if row["expression"] == "Holder.item.boot()"
    )
    assert dispatch["status"] == "not_established"
    assert any(
        target.startswith("polisyos.scientist.a.Prior.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert any(
        target.startswith("polisyos.scientist.a.Entry.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "Holder.item.boot()" in finding.detail
        for finding in validate_import_cycles()
    )
    assert "from polisyos.scientist import edge" in a_source
    assert lazy_registry.read_text(encoding="utf-8") == registry_text

    # The setter may be the imported builtin or the source no-op. Remove only
    # the actual member dispatch; the old/new candidates, import markers, and
    # exact deferred-SCC registration remain present.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Holder.item.boot()\n", "", 1), encoding="utf-8")
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert validate_import_cycles() == []
    assert "from polisyos.scientist import edge" in source_path.read_text(
        encoding="utf-8"
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_preserves_owner_member_across_optional_loop_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Prior:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Holder:\n"
        "    item = Prior()\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "candidates = [Entry()]\n"
        "for Holder.item in candidates:\n"
        "    pass\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    dispatch = next(
        row for row in receipt["unresolved"] if row["expression"] == "Holder.item.boot()"
    )
    assert dispatch["status"] == "not_established"
    assert any(
        target.startswith("polisyos.scientist.a.Prior.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert validate_import_cycles()

    # The possible loop write is not itself a dispatch. Removing the member call
    # must clear the finding while all source import markers remain in place.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Holder.item.boot()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(
        encoding="utf-8"
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_marks_source_member_store_without_owner_identity_unestablished(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Holder:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make_holder():\n"
        "    return Holder()\n"
        "owner = make_holder()\n"
        "owner.item = Entry()\n"
        "owner.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "owner.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert unresolved["reason"] in {
        "source_callable_return_not_summarized",
        "source_derived_receiver_not_summarized",
    }
    findings = validate_import_cycles()
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "owner.item.boot()" in finding.detail
        for finding in findings
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_exports_owner_member_knowledge_as_uncertain_cross_module_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder_source = "class Holder:\n    pass\n"
    writer_source = (
        "from polisyos.scientist.holder import Holder\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "alias = Holder\n"
        "alias.item = Entry()\n"
    )
    caller_source = (
        "from polisyos.scientist.holder import Holder\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.holder import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/holder.py": holder_source,
            "polisyos/scientist/writer.py": writer_source,
            "polisyos/scientist/caller.py": caller_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.caller", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "Holder.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert any(
        target.startswith("polisyos.scientist.writer.Entry.boot@")
        for target in unresolved["known_source_targets"]
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_keeps_joined_possible_owners_unestablished_after_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class HolderA:\n"
        "    pass\n"
        "class HolderB:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "runtime_flag = False\n"
        "if runtime_flag:\n"
        "    owner = HolderA\n"
        "else:\n"
        "    owner = HolderB\n"
        "owner.item = Entry()\n"
        "HolderA.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import HolderA\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "HolderA.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert validate_import_cycles()
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_marks_deleted_owner_member_not_established(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Holder:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "owner = Holder\n"
        "owner.item = Entry()\n"
        "delattr(owner, \"item\")\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "Holder.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert validate_import_cycles()
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_rejects_dynamic_builtin_member_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Prior:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Holder:\n"
        "    item = Prior()\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "owner = Holder\n"
        "member_name = \"item\"\n"
        "setattr(owner, member_name, Entry())\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert any(
        row["status"] == "not_established"
        and row["expression"].startswith("setattr(")
        for row in receipt["unresolved"]
    )
    dispatch = next(
        row
        for row in receipt["unresolved"]
        if row["expression"] == "Holder.item.boot()"
    )
    assert any(
        target.startswith("polisyos.scientist.a.Prior.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert any(
        target.startswith("polisyos.scientist.a.Entry.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert validate_import_cycles()
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_models_builtin_dir_values_and_module_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_source = (
        "from polisyos.scientist import artifacts as _artifacts\n"
        "globals().update({name: getattr(_artifacts, name) for name in dir(_artifacts) "
        "if not name.startswith('__')})\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/artifacts.py": (
                "def __dir__():\n"
                "    from polisyos.scientist import a\n"
                "    return ['Exported']\n"
                "class Exported:\n"
                "    pass\n"
            ),
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    edge_pairs = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.artifacts") in edge_pairs
    assert ("polisyos.scientist.artifacts", "polisyos.scientist.a") in edge_pairs
    assert not any(
        row["expression"] == "name.startswith('__')"
        and row["reason"] == "source_derived_receiver_not_summarized"
        for row in graph["dispatch_resolution"]["unresolved"]
    )
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "from polisyos.scientist import artifacts as _artifacts\n", encoding="utf-8"
    )
    assert "from polisyos.scientist import a" in (
        tmp_path / "src/polisyos/scientist/artifacts.py"
    ).read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_follows_source_owned_startswith_method_and_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_source = (
        "class Entry:\n"
        "    def startswith(self):\n"
        "        from polisyos.scientist import edge\n"
        "Entry().startswith()\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Entry().startswith()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_binds_method_receiver_before_callback_formals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "class Entry:\n"
        "    def accept(self, payload):\n"
        "        return None\n"
        "    def invoke(self, callback):\n"
        "        callback()\n"
        "Entry().accept(callback_target)\n"
        "Entry().invoke(callback_target)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        '[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n'
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    callback_rows = [
        row for row in receipt["unresolved"]
        if row["reason"] == "source_callback_argument_not_summarized"
    ]
    assert callback_rows == []
    assert receipt["unresolved_count"] == 0
    assert any(
        row["source"] == "polisyos.scientist.a"
        and row["target"] == "polisyos.scientist.edge"
        for row in preflight.collect_import_graph(runtime_only=True)["edges"]
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("Entry().invoke(callback_target)\n", "", 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    after_graph = preflight.collect_import_graph(runtime_only=True)
    after = after_graph["dispatch_resolution"]
    assert not any(
        row["reason"] == "source_callback_argument_not_summarized"
        for row in after["unresolved"]
    )
    assert not any(
        row["source"] == "polisyos.scientist.a"
        and row["target"] == "polisyos.scientist.edge"
        for row in after_graph["edges"]
    )
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_follows_source_metaclass_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Meta(type):\n"
                "    def __dir__(cls):\n"
                "        from polisyos.scientist import edge\n"
                "        return []\n"
                "class Entry(metaclass=Meta):\n"
                "    pass\n"
                "dir(Entry)\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_resolves_inherited_metaclass_dir_and_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "class RootMeta(type):\n"
        "    def __dir__(cls):\n"
        "        from polisyos.scientist import edge\n"
        "        return []\n"
        "class Meta(RootMeta):\n"
        "    pass\n"
        "class Base(metaclass=Meta):\n"
        "    pass\n"
        "class Child(Base):\n"
        "    pass\n"
        "dir(Child)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Child\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(source.replace("dir(Child)\n", ""), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_resolves_builtin_descriptor_alias_not_custom_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "from builtins import staticmethod as exact_static\n"
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "class Entry:\n"
        "    @exact_static\n"
        "    def invoke(callback):\n"
        "        callback()\n"
        "Entry.invoke(callback_target)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(source.replace("Entry.invoke(callback_target)\n", ""), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_keeps_custom_descriptor_suffix_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "class Decorators:\n"
        "    @staticmethod\n"
        "    def staticmethod(function):\n"
        "        return function\n"
        "class Entry:\n"
        "    @Decorators.staticmethod\n"
        "    def invoke(self, callback):\n"
        "        callback()\n"
        "Entry().invoke(callback_target)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        '[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n'
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"]
        if row["expression"] == "Entry().invoke(callback_target)"
    )
    assert unresolved["reason"] == "source_callback_argument_not_summarized"
    assert any(
        target.startswith("polisyos.scientist.a.callback_target@")
        for target in unresolved["known_source_targets"]
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(source.replace("Entry().invoke(callback_target)\n", ""), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_preserves_source_dir_string_subclass_dispatch_and_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "class Name(str):\n"
        "    def startswith(self, prefix):\n"
        "        from polisyos.scientist import edge\n"
        "        return True\n"
        "class Entry:\n"
        "    def __dir__(self):\n"
        "        return [Name('entry')]\n"
        "for name in dir(Entry()):\n"
        "    name.startswith('e')\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Name\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        '[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n'
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"]
        if row["expression"] == "name.startswith('e')"
    )
    assert unresolved["reason"] == "source_callable_return_not_summarized"
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        source.replace("    name.startswith('e')\n", "    pass\n", 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_captures_bound_receiver_before_argument_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def invoke(self, marker):\n"
        "        self.load()\n"
        "    def load(self):\n"
        "        from polisyos.scientist import left_edge\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import right_edge\n"
        "def rebind_selected():\n"
        "    global selected\n"
        "    selected = Replacement()\n"
        "    return None\n"
        "selected = Entry()\n"
        "selected.invoke(rebind_selected())\n"
    )
    left_edge_source = "from polisyos.scientist.a import Entry\n"
    right_edge_source = "from polisyos.scientist.a import Replacement\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/left_edge.py": left_edge_source,
            "polisyos/scientist/right_edge.py": right_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") in edges_before
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_before
    eager_cycle = next(
        cycle["modules"]
        for cycle in before["cycles"]
        if "polisyos.scientist.left_edge" in cycle["modules"]
    )
    eager_component = frozenset(eager_cycle)
    assert eager_component == frozenset({"polisyos.scientist.a", "polisyos.scientist.left_edge"})
    registered_components = {
        frozenset(row["modules"]) for row in tomllib.loads(registry_text)["allowed_cycle"]
    }
    assert any(eager_component < registered for registered in registered_components)
    findings = validate_import_cycles()
    assert any(
        finding.gate == "import_cycles_gate"
        and "module-eager" in finding.message
        and finding.detail == ", ".join(eager_cycle)
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("selected.invoke(rebind_selected())\n", "", 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import left_edge" in source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import right_edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert after["cycles"] == []
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_after
    assert ("polisyos.scientist.left_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.right_edge", "polisyos.scientist.a") in edges_after
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_captures_callback_before_later_argument_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def original_callback():\n"
        "    from polisyos.scientist import left_edge\n"
        "def replacement_callback():\n"
        "    from polisyos.scientist import right_edge\n"
        "callback_target = original_callback\n"
        "def rebind_callback():\n"
        "    global callback_target\n"
        "    callback_target = replacement_callback\n"
        "    return None\n"
        "def invoke(callback, marker):\n"
        "    callback()\n"
        "invoke(callback_target, rebind_callback())\n"
        "callback_target = original_callback\n"
        "invoke(callback=callback_target, marker=rebind_callback())\n"
    )
    left_edge_source = "from polisyos.scientist.a import original_callback\n"
    right_edge_source = "from polisyos.scientist.a import replacement_callback\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/left_edge.py": left_edge_source,
            "polisyos/scientist/right_edge.py": right_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") in edges_before
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_before
    eager_cycle = next(
        cycle["modules"]
        for cycle in before["cycles"]
        if "polisyos.scientist.left_edge" in cycle["modules"]
    )
    eager_component = frozenset(eager_cycle)
    assert eager_component == frozenset({"polisyos.scientist.a", "polisyos.scientist.left_edge"})
    registered_components = {
        frozenset(row["modules"]) for row in tomllib.loads(registry_text)["allowed_cycle"]
    }
    assert any(eager_component < registered for registered in registered_components)
    findings = validate_import_cycles()
    assert any(
        finding.gate == "import_cycles_gate"
        and "module-eager" in finding.message
        and finding.detail == ", ".join(eager_cycle)
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("invoke(callback_target, rebind_callback())\n", "", 1).replace(
            "invoke(callback=callback_target, marker=rebind_callback())\n", "", 1
        ),
        encoding="utf-8",
    )
    after_source = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import left_edge" in after_source
    assert "from polisyos.scientist import right_edge" in after_source
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert after["cycles"] == []
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_after
    assert ("polisyos.scientist.left_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.right_edge", "polisyos.scientist.a") in edges_after
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_joins_effects_from_same_call_alternatives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "def a_false():\n"
        "    global TYPE_ONLY\n"
        "    TYPE_ONLY = False\n"
        "def z_true():\n"
        "    global TYPE_ONLY\n"
        "    from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "if choose_target:\n"
        "    selected = a_false\n"
        "else:\n"
        "    selected = z_true\n"
        "selected()\n"
        "if TYPE_ONLY:\n"
        "    from polisyos.scientist import deferred_edge\n"
    )
    edge_source = "from polisyos.scientist.a import a_false\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/deferred_edge.py": edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.deferred_edge") in edges_before
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("selected()\n", "", 1), encoding="utf-8")
    after_source = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import deferred_edge" in after_source
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.deferred_edge") not in edges_after
    assert ("polisyos.scientist.deferred_edge", "polisyos.scientist.a") in edges_after
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []
