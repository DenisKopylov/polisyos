"""Actual export reader controls, independent of runtime authority or backend fit."""

from __future__ import annotations

import ast
import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.devx.architecture import guardrails


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    source = tmp_path / "src"
    package = source / "polisyos" / "fixture"
    package.mkdir(parents=True)
    monkeypatch.setattr(guardrails, "SRC_ROOT", source)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    facade = package / "__init__.py"
    mapping = package / "exports.py"
    facade.write_text(
        "from .exports import PUBLIC_NAMES as names\n"
        "__all__ = sorted(names)\n"
        "Old = None\n"
        "New = None\n"
        "Current = None\n"
        "Candidate = None\n"
        "StaticName = None\n"
        "A = None\n"
        "B = None\n",
        encoding="utf-8",
    )
    mapping.write_text(
        'PUBLIC_NAMES = {"Old": ("polisyos.fixture.owner", "Old")}\n',
        encoding="utf-8",
    )
    return facade, mapping


@pytest.mark.parametrize("annotation", ["", ": dict[str, str]"])
def test_only_empty_static_mapping_loop_is_excluded_from_selected_write_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    annotation: str,
) -> None:
    source_root = tmp_path / "src"
    monkeypatch.setattr(guardrails, "SRC_ROOT", source_root)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    source = source_root / "polisyos" / "fixture" / "__init__.py"
    text = """import importlib
__all__ = ("child",)
_COMPAT_MODULE_ALIASES = {}
def lookup(fullname):
    return _COMPAT_MODULE_ALIASES.get(fullname)
def install():
    for alias_fqn, target_fqn in _COMPAT_MODULE_ALIASES.items():
        parent_fqn, _, leaf = alias_fqn.rpartition(".")
        globals()[leaf] = target_fqn
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    module = importlib.import_module("polisyos.fixture.child")
    globals()[name] = module
    return module
"""
    declaration = f"_COMPAT_MODULE_ALIASES{annotation} = {{}}"
    text = text.replace("_COMPAT_MODULE_ALIASES = {}", declaration)
    tree = ast.parse(text, filename=str(source))
    assert not guardrails._export_namespace_write_may_change(
        tree, frozenset({"child", "__all__", "__getattr__"}), source
    )

    nonempty = ast.parse(
        text.replace(
            declaration,
            '_COMPAT_MODULE_ALIASES = {"polisyos.fixture.child": "polisyos.fixture.child"}',
        ),
        filename=str(source),
    )
    assert guardrails._export_namespace_write_may_change(
        nonempty, frozenset({"child", "__all__", "__getattr__"}), source
    )

    mutated = ast.parse(
        text.replace(
            declaration,
            declaration + "\n_COMPAT_MODULE_ALIASES.update(runtime_aliases)",
        ),
        filename=str(source),
    )
    assert guardrails._export_namespace_write_may_change(
        mutated, frozenset({"child", "__all__", "__getattr__"}), source
    )

    for unsafe_use in (
        "alias = _COMPAT_MODULE_ALIASES",
        "escape(_COMPAT_MODULE_ALIASES)",
        "lookup_method = _COMPAT_MODULE_ALIASES.get",
        "_COMPAT_MODULE_ALIASES['polisyos.fixture.child'] = 'replacement'",
        "_COMPAT_MODULE_ALIASES.clear()",
        "_COMPAT_MODULE_ALIASES = {}",
        "del _COMPAT_MODULE_ALIASES",
        "_COMPAT_MODULE_ALIASES.get('missing', _COMPAT_MODULE_ALIASES)",
    ):
        changed = ast.parse(
            text.replace("def install():", unsafe_use + "\ndef install():"),
            filename=str(source),
        )
        assert guardrails._export_namespace_write_may_change(
            changed, frozenset({"child", "__all__", "__getattr__"}), source
        ), unsafe_use


def test_actual_fabric_facade_empty_compatibility_map_keeps_export_total_resolvable() -> None:
    """Read the real facade without installing its finder or importing backends."""
    source = guardrails._facade_source_for("polisyos.fabric")
    tree = ast.parse(source.read_bytes())
    declarations = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    ]
    assert len(declarations) == 1
    assert guardrails._extract_exports(tree, source) == tuple(declarations[0])


def test_closed_negative_guard_resolves_actual_literal_owner_and_refuses_binding_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    owner = facade.with_name("owner.py")
    owner.write_text("StaticName = None\n__all__ = ('StaticName',)\n", encoding="utf-8")
    text = """from importlib import import_module
__all__ = ('StaticName',)
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    value = getattr(import_module('polisyos.fixture.owner'), name)
    globals()[name] = value
    return value
"""
    facade.write_text(text, encoding="utf-8")
    assert guardrails._extract_exports(ast.parse(text), facade) == ("StaticName",)

    for changed in (
        text.replace("not in __all__", "in __all__"),
        text.replace("    return value", "    return None"),
        text.replace("__all__ =", "getattr = lambda *args: None\n__all__ ="),
        text.replace("__all__ =", "import_module = lambda *args: None\n__all__ ="),
        text.replace("    value =", "    import_module ="),
        text.replace("), name)", "), 'Other')"),
    ):
        with pytest.raises(guardrails._UnresolvedExportDeclarationError):
            guardrails._extract_exports(ast.parse(changed), facade)

    # Keep the selected owner and facade declaration intact; remove the real binding.
    owner.write_text("__all__ = ('StaticName',)\n", encoding="utf-8")
    with pytest.raises(guardrails._UnresolvedExportDeclarationError):
        guardrails._extract_exports(ast.parse(text), facade)


def test_actual_causal_facade_routes_the_complete_metadata_tuple_without_execution() -> None:
    source = guardrails._facade_source_for("polisyos.foundry.methods.causal")
    tree = ast.parse(source.read_bytes())
    exports = guardrails._extract_exports(tree, source)
    metadata = source.with_name("_exports.py")
    declaration = next(
        node
        for node in ast.parse(metadata.read_bytes()).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "CAUSAL_METHOD_EXPORTS"
            for target in node.targets
        )
    )
    assert exports == ast.literal_eval(declaration.value)
    assert exports


def test_lazy_child_route_is_selected_and_unrelated_imports_do_not_affect_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    package = facade.parent
    (package / "child.py").write_text("VALUE = 1\n", encoding="utf-8")
    source = (
        "import re\n"
        "import importlib\n"
        '__all__ = ("child",)\n'
        "def __getattr__(name):\n"
        "    if name not in __all__:\n"
        "        raise AttributeError(name)\n"
        '    module = importlib.import_module("polisyos.fixture.child")\n'
        "    globals()[name] = module\n"
        "    return module\n"
    )
    facade.write_text(source, encoding="utf-8")
    tree = ast.parse(source, filename=str(facade))

    assert (
        guardrails._facade_lazy_child_target("polisyos.fixture", facade, tree, "child")
        == "polisyos.fixture.child"
    )

    mutated = source.replace(
        "import re\n",
        "import re\nimportlib.import_module = lambda name: None\n",
        1,
    )
    facade.write_text(mutated, encoding="utf-8")
    assert (
        guardrails._facade_lazy_child_target(
            "polisyos.fixture", facade, ast.parse(mutated, filename=str(facade)), "child"
        )
        is None
    )


def test_future_import_feature_is_a_real_public_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        "from __future__ import annotations\n__all__ = ['annotations']\n",
        encoding="utf-8",
    )

    result = guardrails._entrypoint_inventory("polisyos.fixture")

    assert result.exports == ("annotations",)
    assert result.export_count == 1
    assert result.export_resolution["complete_verdict"] is True


@pytest.mark.parametrize("docstring", ["", '"""Legal facade."""\n'])
def test_legal_future_annotations_is_passive_to_actual_facade_resolver(
    docstring: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        docstring
        + "from __future__ import annotations\n"
        + "from .exports import PUBLIC_NAMES as names\n"
        + "__all__ = sorted(names)\n"
        + "Old = None\n",
        encoding="utf-8",
    )

    result = guardrails._entrypoint_inventory("polisyos.fixture")

    assert result.exports == ("Old",)
    assert result.export_count == 1
    assert result.export_resolution["complete_verdict"] is True


def test_annotations_outside_export_dependency_cone_do_not_change_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        "from .exports import PUBLIC_NAMES as names\n__all__ = sorted(names)\nOld = None\n",
        encoding="utf-8",
    )
    mapping.write_text(
        "from __future__ import annotations\n"
        'PUBLIC_NAMES: dict[str, tuple[str, str]] = {"Old": ("owner", "Old")}\n',
        encoding="utf-8",
    )
    with_future = guardrails._entrypoint_inventory("polisyos.fixture")
    assert with_future.exports == ("Old",)
    assert with_future.export_resolution["complete_verdict"] is True

    mapping.write_text(
        'PUBLIC_NAMES: dict[str, tuple[str, str]] = {"Old": ("owner", "Old")}\n',
        encoding="utf-8",
    )
    without_future = guardrails._entrypoint_inventory("polisyos.fixture")
    assert without_future.exports == with_future.exports
    assert without_future.export_count == with_future.export_count
    assert without_future.export_resolution["complete_verdict"] is True


def test_misordered_future_directive_keeps_facade_inventory_unresolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        "from .exports import PUBLIC_NAMES as names\n"
        "from __future__ import annotations\n"
        "__all__ = sorted(names)\n",
        encoding="utf-8",
    )

    result = guardrails._entrypoint_inventory("polisyos.fixture")

    assert result.export_count is None
    assert result.known_export_count == 0
    assert result.export_resolution["complete"] is False
    assert "Invalid source syntax" in result.export_resolution["reason"]


def test_unknown_future_feature_is_rejected_by_python_parser() -> None:
    with pytest.raises(SyntaxError, match=r"future feature .* is not defined"):
        ast.parse(
            "from __future__ import unsupported_policyos_future_feature\n__all__ = ['StaticName']\n"
        )


def test_closed_mapping_update_is_resolved_without_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    mapping.write_text(
        'PUBLIC_NAMES = {"Old": ("polisyos.fixture.owner", "Old")}\n'
        'EXTRA_NAMES = ("New", "Current")\n'
        'PUBLIC_NAMES.update({name: ("polisyos.fixture.owner", name) for name in EXTRA_NAMES})\n',
        encoding="utf-8",
    )

    result = guardrails._entrypoint_inventory("polisyos.fixture")

    assert result.exports == ("Current", "New", "Old")
    assert result.export_count == 3
    assert result.export_resolution["complete"] is True


def test_closed_mapping_update_rejects_mutating_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    mapping.write_text(
        'PUBLIC_NAMES = {"Old": ("polisyos.fixture.owner", "Old")}\n'
        "ALIAS = PUBLIC_NAMES\n"
        'PUBLIC_NAMES.update({"New": ("polisyos.fixture.owner", "New")})\n'
        "ALIAS.clear()\n",
        encoding="utf-8",
    )

    result = guardrails._entrypoint_inventory("polisyos.fixture")

    assert result.export_count is None
    assert result.known_export_count == 0
    assert result.export_resolution["complete"] is False


def test_actual_analytics_mapping_has_a_complete_source_export_inventory() -> None:
    from polisyos.ir import analytics
    from polisyos.ir.analytics.causal_queries import CausalEstimatorInterval, CausalResultKind
    from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS

    result = guardrails._entrypoint_inventory("polisyos.ir.analytics")
    expected = tuple(sorted(ANALYTICS_FACADE_EXPORTS))
    assert tuple(analytics.__all__) == expected
    assert ANALYTICS_FACADE_EXPORTS["CausalEstimatorInterval"] == (
        "polisyos.ir.analytics.causal_queries",
        "CausalEstimatorInterval",
    )
    assert ANALYTICS_FACADE_EXPORTS["CausalResultKind"] == (
        "polisyos.ir.analytics.causal_queries",
        "CausalResultKind",
    )
    assert analytics.CausalEstimatorInterval is CausalEstimatorInterval
    assert analytics.CausalResultKind is CausalResultKind
    assert result.exports == expected
    assert result.export_count == len(expected)
    assert result.export_resolution["complete_verdict"] is True
    inputs = result.export_resolution["inputs"]
    paths = {row["path"] for row in inputs if row["operation"] == "read_bytes"}
    assert "src/polisyos/ir/analytics/__init__.py" in paths
    assert "src/polisyos/ir/api.py" in paths
    for row in inputs:
        if row["operation"] == "read_bytes":
            raw = (guardrails.REPO_ROOT / row["path"]).read_bytes()
            assert row["bytes"] == len(raw)
            assert row["sha256"] == hashlib.sha256(raw).hexdigest()


def test_reader_follows_owner_mapping_change_without_facade_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade_before = facade.read_bytes()
    first = guardrails._entrypoint_inventory("polisyos.fixture")
    mapping.write_text('PUBLIC_NAMES = {"New": None, "Old": None}\n', encoding="utf-8")
    second = guardrails._entrypoint_inventory("polisyos.fixture")
    assert facade.read_bytes() == facade_before
    assert first.exports == ("Old",)
    assert second.exports == ("New", "Old")
    assert first.export_resolution != second.export_resolution
    # Real serialization observes the changed dependency, not a facade marker.
    policy = guardrails.PackagePolicy(
        module="polisyos.fixture",
        classification="public_experimental",
        facade_mode="eager_exports",
        owner="test-owner",
        readme=facade,
        reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",),
        major_subsystem=False,
        notes="fixture",
    )
    rendered = json.loads(
        guardrails.render_public_surface_json(guardrails.build_public_surface_inventory([policy]))
    )
    assert rendered["packages"][0]["entrypoints"][0]["exports"] == ["New", "Old"]


def test_starred_mapping_expansion_iterates_keys_and_rejects_non_string_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        "from .exports import PUBLIC_NAMES as names\n__all__ = [*names]\nOld = None\n",
        encoding="utf-8",
    )
    mapping.write_text(
        'PUBLIC_NAMES = {"Old": ("polisyos.fixture.owner", "Old")}\n', encoding="utf-8"
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("Old",)
    assert result.export_count == 1
    assert result.export_resolution["complete"] is True

    mapping.write_text("PUBLIC_NAMES = {1: None}\n", encoding="utf-8")
    rejected = guardrails._entrypoint_inventory("polisyos.fixture")
    assert rejected.export_count is None
    assert rejected.export_resolution["complete"] is False
    assert any(
        marker in rejected.export_resolution["reason"]
        for marker in (
            "Unresolved export expansion",
            "Unresolved export mapping key",
            "Unresolved non-string export item",
        )
    )


def test_closed_lazy_package_importlib_binding_is_declaration_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.with_name("child.py").write_text("VALUE = 1\n", encoding="utf-8")
    facade.write_text(
        "from importlib import import_module\n"
        "__all__ = ('child',)\n"
        "def __getattr__(name):\n"
        "    if name not in __all__:\n"
        "        raise AttributeError(name)\n"
        "    value = import_module(f'{__name__}.{name}')\n"
        "    globals()[name] = value\n"
        "    return value\n",
        encoding="utf-8",
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("child",)
    assert result.export_count == 1
    assert result.export_resolution["complete_verdict"] is True

    facade.write_text(
        "from importlib import import_module\n"
        "__all__ = ('child',)\n"
        "import_module('polisyos.fixture.runtime')\n"
        "def __getattr__(name):\n"
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )
    rejected = guardrails._entrypoint_inventory("polisyos.fixture")
    assert rejected.export_count is None
    assert rejected.export_resolution["complete_verdict"] is False


def test_lazy_owner_map_is_tied_to_the_selected_getattr_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        """import importlib
__all__ = ("Selected",)
def __getattr__(name):
    owners = {"Selected": ("polisyos.fixture.owner", "Selected")}
    if name in owners:
        module_name, attribute_name = owners[name]
        imported_module = importlib.import_module(module_name)
        value = getattr(imported_module, attribute_name)
        globals()[name] = value
        return value
    raise AttributeError(name)
""",
        encoding="utf-8",
    )
    accepted = guardrails._entrypoint_inventory("polisyos.fixture")
    assert accepted.exports == ("Selected",)
    assert accepted.export_count == 1
    assert accepted.export_resolution["complete_verdict"] is True

    source = facade.read_text(encoding="utf-8").replace(
        "    if name in owners:\n",
        '    owners["Selected"] = ("polisyos.fixture.other", "Selected")\n    if name in owners:\n',
        1,
    )
    facade.write_text(source, encoding="utf-8")
    rejected = guardrails._entrypoint_inventory("polisyos.fixture")
    assert rejected.export_count is None
    assert rejected.export_resolution["complete_verdict"] is False


def test_optional_import_outcomes_prove_name_presence_not_backend_callability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        """try:
    from .primary import Selected
except ImportError:
    from .fallback import Selected
__all__ = ["Selected"]
""",
        encoding="utf-8",
    )
    accepted = guardrails._entrypoint_inventory("polisyos.fixture")
    assert accepted.exports == ("Selected",)
    assert accepted.export_count == 1
    assert accepted.export_resolution["complete_verdict"] is True

    facade.write_text(
        """try:
    from .primary import Selected
except ImportError:
    Selected = None
__all__ = ["Selected"]
""",
        encoding="utf-8",
    )
    bound_fallback = guardrails._entrypoint_inventory("polisyos.fixture")
    assert bound_fallback.exports == ("Selected",)
    assert bound_fallback.export_count == 1
    assert bound_fallback.export_resolution["complete_verdict"] is True
    # A real failed optional import leaves a present, non-callable export.
    namespace = runpy.run_path(str(facade))
    assert "Selected" in namespace
    assert namespace["Selected"] is None
    assert not guardrails._module_level_attribute_is_bound(
        ast.parse(facade.read_bytes()), "Selected"
    )


def test_outside_selector_is_disclosed_and_does_not_become_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    outside = mapping.with_name("unselected.py")
    outside.write_text('PUBLIC_NAMES = {"Outside": None}\nraise RuntimeError("never run")\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("Old",)
    outside_reads = [
        row
        for row in result.export_resolution["inputs"]
        if row["path"] == str(outside.relative_to(tmp_path)) and row["operation"] == "read_bytes"
    ]
    assert not outside_reads
    assert "Outside" not in result.exports
    assert "without executing source" in result.export_resolution["selector"]
    assert result.export_resolution["unresolved_by_construction"]


@pytest.mark.parametrize(
    "problem", ["missing", "unreadable", "cycle", "computed", "mutated", "subscript", "conditional"]
)
def test_unresolved_mapping_never_becomes_empty_manifest(
    problem: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    if problem == "missing":
        mapping.rename(mapping.with_suffix(".retained"))
        error = FileNotFoundError
    elif problem == "unreadable":
        original = guardrails.admitted_read_bytes

        def read(path, root):
            if path == mapping:
                raise PermissionError("actual reader refused fixture")
            return original(path, root)

        monkeypatch.setattr(guardrails, "admitted_read_bytes", read)
        error = PermissionError
    elif problem == "cycle":
        mapping.write_text("from . import __all__ as PUBLIC_NAMES\n")
        error = ValueError
    elif problem == "computed":
        mapping.write_text("PUBLIC_NAMES = choose_runtime_exports()\n")
        error = ValueError
    elif problem == "subscript":
        mapping.write_text('PUBLIC_NAMES = {"Old": None}\nPUBLIC_NAMES["New"] = None\n')
        error = ValueError
    elif problem == "conditional":
        mapping.write_text('if backend_available():\n    PUBLIC_NAMES = {"Old": None}\n')
        error = ValueError
    else:
        mapping.write_text('PUBLIC_NAMES = {"Old": None}\nPUBLIC_NAMES.update(runtime_exports())\n')
        error = ValueError
    if error is ValueError:
        result = guardrails._entrypoint_inventory("polisyos.fixture")
        assert result.export_count is None
        assert result.known_export_count == 0
        assert result.exports == ()
        assert result.facade_mode_observed == "unresolved_exports"
        assert result.export_resolution["complete"] is False
        assert "not an empty runtime namespace" in result.export_resolution["exports_scope"]
    else:
        with pytest.raises(error):
            guardrails._entrypoint_inventory("polisyos.fixture")


def test_unselected_owner_values_and_module_effects_do_not_change_export_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    mapping.write_text(
        'raise RuntimeError("module execution forbidden")\n'
        'BASE = {"A": unknown_runtime_owner}\n'
        'PUBLIC_NAMES = {**BASE, "B": object}\n',
        encoding="utf-8",
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("A", "B")
    assert result.export_count == 2
    assert result.export_resolution["complete_verdict"] is True
    policy = guardrails.PackagePolicy(
        module="polisyos.fixture",
        classification="public_experimental",
        facade_mode="eager_exports",
        owner="test-owner",
        readme=facade,
        reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",),
        major_subsystem=False,
        notes="fixture",
    )
    serialized = json.loads(
        guardrails.render_public_surface_json(guardrails.build_public_surface_inventory([policy]))
    )["packages"][0]
    assert serialized["exports"] == ["A", "B"]
    assert serialized["export_count"] == 2
    assert serialized["entrypoints"][0]["export_resolution"]["complete_verdict"] is True


def test_unresolved_reason_and_scopes_are_rendered_as_markdown_literals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    tick = chr(96)

    def unresolved(*args, **kwargs):
        raise guardrails._UnresolvedExportDeclarationError(tick * 3 + "source" + tick * 3)

    monkeypatch.setattr(guardrails, "_exported_names_have_bindings", unresolved)
    facade.write_text('__all__ = ["Selected"]\nSelected = None\n', encoding="utf-8")
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    reason = result.export_resolution["reason"]
    assert reason == tick * 3 + "source" + tick * 3

    policy = guardrails.PackagePolicy(
        module="polisyos.fixture",
        classification="public_experimental",
        facade_mode="eager_exports",
        owner="test-owner",
        readme=facade,
        reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",),
        major_subsystem=False,
        notes="fixture",
    )
    markdown = guardrails.render_public_surface_markdown(
        guardrails.build_public_surface_inventory([policy])
    )
    assert f"- Export resolution incomplete: {tick * 4} {reason} {tick * 4}." in markdown
    assert f"- Export scope: {tick}{result.export_resolution['exports_scope']}{tick}" in markdown
    assert (
        f"- Candidate scope: {tick}{result.export_resolution['candidate_scope']}{tick}" in markdown
    )
    assert result.export_count is None
    assert result.export_resolution["complete_verdict"] is False


def test_local_names_and_sequence_concat_share_same_reader() -> None:
    tree = ast.parse(
        'M = {"B": None, "A": None}\n'
        "A = None\nB = None\nC = None\n"
        'N = sorted(M)\n__all__ = tuple(N) + ("C",)\n'
    )
    assert guardrails._extract_exports(tree) == ("A", "B", "C")


def test_export_marker_without_selected_binding_is_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text('__all__ = ["Selected"]\nSelected = None\n', encoding="utf-8")
    complete = guardrails._entrypoint_inventory("polisyos.fixture")
    assert complete.exports == ("Selected",)
    assert complete.export_resolution["complete_verdict"] is True

    facade.write_text('__all__ = ["Selected"]\n', encoding="utf-8")
    removed = guardrails._entrypoint_inventory("polisyos.fixture")
    assert removed.export_count is None
    assert removed.known_export_count == 0
    assert removed.export_resolution["complete_verdict"] is False
    assert "Unresolved exported binding" in removed.export_resolution["reason"]


def test_conditional_all_is_unresolved_instead_of_absent() -> None:
    with pytest.raises(ValueError, match="conditional"):
        guardrails._extract_exports(ast.parse('if runtime():\n    __all__ = ["A"]\n'))


@pytest.mark.parametrize(
    "binding",
    [
        "sorted = lambda values: []",
        "from external_plugin import choose as sorted",
        "if backend_ready():\n    from external_plugin import choose as sorted",
        "if backend_ready():\n    def sorted(values):\n        return []",
        "for sorted in [choose]:\n    pass",
        "import external_plugin as sorted",
        "from external_plugin import *",
        "(sorted := choose)",
        "def unrelated(value=(sorted := choose)):\n    pass",
        "unrelated = lambda value=(sorted := choose): value",
        "class Unrelated((sorted := choose)):\n    pass",
        "type sorted = tuple[str, ...]",
        "del sorted",
        "with owner() as sorted:\n    pass",
        "try:\n    run()\nexcept RuntimeError as sorted:\n    pass",
        "match configured:\n    case {'handler': sorted}:\n        pass",
    ],
)
def test_shadowed_builtin_keeps_all_marker_but_is_unresolved(binding: str) -> None:
    source = binding + '\nMAP = {"Actual": None}\n__all__ = sorted(MAP)\n'
    tree = ast.parse(source)
    assert any(isinstance(node, ast.Assign) for node in tree.body)
    with pytest.raises(ValueError, match="Unresolved"):
        guardrails._extract_exports(tree)


@pytest.mark.parametrize(
    "binding", ["if runtime():\n    from owner import MAP", "def MAP():\n    pass"]
)
def test_unsupported_symbol_bindings_cannot_be_hidden_by_literal_declaration(binding: str) -> None:
    tree = ast.parse('MAP = {"Actual": None}\n' + binding + "\n__all__ = sorted(MAP)\n")
    with pytest.raises(ValueError, match="conditional/mutated exports"):
        guardrails._extract_exports(tree)


def test_direct_named_all_import_uses_same_finite_owner_reader(tmp_path: Path, monkeypatch) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade.write_text("from .exports import __all__, A, B\n")
    mapping.write_text('__all__ = ["B", "A"]\nA = None\nB = None\n')
    assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("B", "A")


def test_closed_literal_extension_exposes_bound_prefix_and_fails_complete_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text('__all__ = ["Prefix"]\nPrefix = None\n__all__.extend(["Added"])\n')
    policy = guardrails.PackagePolicy(
        module="polisyos.fixture",
        classification="public_experimental",
        facade_mode="eager_exports",
        owner="test-owner",
        readme=facade,
        reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",),
        major_subsystem=False,
        notes="fixture",
    )
    source_tree = ast.parse(facade.read_text(encoding="utf-8"), filename=str(facade))
    assert guardrails._static_string_collection(facade, source_tree, "__all__") == (
        "Prefix",
        "Added",
    )
    inventory = guardrails.build_public_surface_inventory([policy])
    row = json.loads(guardrails.render_public_surface_json(inventory))["packages"][0]
    assert row["export_count"] is None
    assert row["known_export_count"] == 1
    assert row["exports"] == ["Prefix"]
    resolution = row["entrypoints"][0]["export_resolution"]
    assert resolution["complete"] is False
    assert resolution["complete_verdict"] is False
    violations = guardrails._check_public_surface_contracts(inventory)
    assert [(item.subject, item.detail) for item in violations] == [
        ("polisyos.fixture", "incomplete_exports"),
    ]


def test_dynamic_sequence_extension_is_not_a_route_or_complete_export_total(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        '__all__ = ["Prefix"]\n__all__.extend(runtime_names())\n',
        encoding="utf-8",
    )
    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=str(facade))

    assert guardrails._static_string_collection(facade, tree, "__all__") is None
    row = guardrails._entrypoint_inventory("polisyos.fixture")
    assert row.export_count is None
    assert row.export_resolution["complete"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        '__all__ = ["Replacement"]',
        "__all__.clear()",
        "alias = __all__",
        '__all__[0] = "Replacement"',
        'if runtime():\n    __all__ = ["Replacement"]',
        "from owner import __all__",
        "__all__.extend(*runtime_names())",
        "mutate(__all__)",
    ],
)
def test_unproved_prefix_rebind_or_mutation_still_refuses(mutation: str) -> None:
    source = '__all__ = ["Prefix"]\n' + mutation + "\n__all__.extend(runtime_names())\n"
    with pytest.raises(ValueError) as caught:
        guardrails._extract_exports(ast.parse(source))
    assert not isinstance(caught.value, guardrails._IncompleteExportDeclarationError)


def test_current_world_has_complete_conditional_source_profiles_and_separate_native_state() -> None:
    from polisyos.fabric import world

    row = guardrails._entrypoint_inventory("polisyos.fabric.world")
    tree = ast.parse((guardrails.REPO_ROOT / row.source_file).read_bytes())
    literal = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    )
    assert row.export_count is None
    literal_names = ast.literal_eval(literal)
    assert len(literal_names) == 41
    conditional_names = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(node.value, ast.Tuple)
        and node.value.elts
        and any(
            isinstance(target, ast.Name) and target.id == "_MATERIALIZE_EXPORTS"
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    )
    predicate = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_DUCKDB_AVAILABLE"
            for target in node.targets
        )
    )
    assert row.known_export_count == len(literal_names)
    assert row.exports == tuple(literal_names)
    assert row.export_resolution["complete"] is True
    profiles = row.source_export_profiles
    assert [profile.exports for profile in profiles] == [
        tuple(literal_names),
        (*literal_names, *conditional_names),
    ]
    assert [len(profile.exports) for profile in profiles] == [41, 59]
    assert [profile.conditions[0].value for profile in profiles] == [False, True]
    assert all(
        len(profile.conditions) == 1
        and profile.conditions[0].expression == ast.unparse(predicate)
        and profile.runtime_condition_evaluation == "UNRUN"
        and profile.schema_version == "policyos.source-export-profile.v1"
        for profile in profiles
    )
    # A loaded native module is an independent observed profile, not the source condition.
    assert tuple(world.__all__) == profiles[int(world._MATERIALIZE_AVAILABLE)].exports


def test_conditional_profiles_reach_json_markdown_and_the_public_surface_check() -> None:
    policies = [
        policy
        for policy in guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
        if policy.module == "polisyos.fabric"
    ]
    inventory = guardrails.build_public_surface_inventory(policies)
    row = next(
        entry for entry in inventory[0].entrypoints if entry.module == "polisyos.fabric.world"
    )
    payload = json.loads(guardrails.render_public_surface_json(inventory))
    served = next(
        entry for entry in payload["packages"][0]["entrypoints"] if entry["module"] == row.module
    )
    assert served["export_count"] is None
    assert served["exports"] == list(row.exports)
    assert served["export_resolution"]["complete"] is True
    assert [profile["exports"] for profile in served["source_export_profiles"]] == [
        list(profile.exports) for profile in row.source_export_profiles
    ]
    assert all(
        profile["runtime_condition_evaluation"] == "UNRUN"
        for profile in served["source_export_profiles"]
    )
    markdown = guardrails.render_public_surface_markdown(inventory)
    assert "conditional (41/59)" in markdown
    assert "there is no single unconditional export count" in markdown
    assert "runtime condition evaluation: `UNRUN`" in markdown
    assert guardrails._check_public_surface_contracts(inventory) == []


@pytest.mark.parametrize(
    "source",
    [
        'M = {"x": 1}\nmutate(M)\n__all__ = sorted(M)',
        'M = {"x": 1}\nA = M\nA["y"] = 2\n__all__ = sorted(M)',
        '__all__ = ["x"]\nmutate(__all__)',
        'M = {"x": 1}\nA = [M]\nconsume(A)\n__all__ = sorted(M)',
        'M = {"x": 1}\n__all__ = sorted(M)\nconsume(M)',
        'M = {"x": 1}\nglobals()["M"]["y"] = 2\n__all__ = sorted(M)',
        'M = {"x": 1}\nexec("M[\\"y\\"] = 2")\n__all__ = sorted(M)',
        'M = {"x": 1}\ndef mutate():\n    M["y"] = 2\nmutate()\n__all__ = sorted(M)',
        'M = {"x": 1}\nclass C:\n    M["y"] = 2\n__all__ = sorted(M)',
        'M = {"x": 1}\nclass C:\n    global M\n    M = {"y": 2}\n__all__ = sorted(M)',
        'M = {"x": 1}\nclass C(metaclass=unknown):\n    pass\n__all__ = sorted(M)',
        'M = {"x": 1}\nclass C(unknown):\n    pass\n__all__ = sorted(M)',
        'globals()["sorted"] = choose\nM = {"x": 1}\n__all__ = sorted(M)',
        'M = {\n    "x": poison(),\n}\n__all__ = sorted(M)',
        'class D:\n    def __set_name__(self, owner, name):\n        M["y"] = 2\nd = D()\nM = {"x": 1}\nclass C:\n    descriptor = d\n__all__ = sorted(M)',
    ],
)
def test_bindings_cannot_escape_finite_declaration_consumers(source: str) -> None:
    with pytest.raises(ValueError, match="Unresolved"):
        guardrails._extract_exports(ast.parse(source))


@pytest.mark.parametrize(
    "source",
    [
        'globals()["__all__"] = ["RuntimeOnly"]',
        "class C:\n    pass",
    ],
)
def test_missing_syntactic_binding_remains_fail_closed(source: str) -> None:
    with pytest.raises(guardrails._UnresolvedExportDeclarationError):
        guardrails._extract_exports(ast.parse(source))


@pytest.mark.parametrize(
    "effect",
    [
        "import foreign",
        "from foreign import value",
        "ignored = foreign.attribute",
        "ignored = foreign[0]",
        "ignored = foreign + 1",
        "if foreign:\n    pass",
        "with foreign:\n    pass",
        "ignored = [value for value in foreign]",
        "def poison(f):\n    return f\n@poison\ndef unrelated():\n    pass",
        "def unrelated(value=callback()):\n    pass",
    ],
)
def test_unrelated_module_effects_do_not_change_selected_exports(effect: str) -> None:
    source = effect + '\nM = {"StaticName": None}\nStaticName = None\n__all__ = sorted(M)\n'
    assert guardrails._extract_exports(ast.parse(source)) == ("StaticName",)


def test_plain_function_body_and_closed_defaults_are_outside_import_time_execution() -> None:
    source = (
        'DEFAULT = {"answer": 42}\n'
        "def passive(value=DEFAULT, count: int = 1) -> str:\n"
        "    return foreign.callback(value)\n"
        '__all__ = ["passive"]\n'
    )
    assert guardrails._extract_exports(ast.parse(source)) == ("passive",)


def test_unselected_import_effect_is_not_in_source_export_dependency_slice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    effects = mapping.with_name("effects.py")
    mapping.write_text(
        'from .effects import PASSIVE\nPUBLIC_NAMES = {"Old": None}\n',
        encoding="utf-8",
    )
    effects.write_text("PASSIVE = 1\nforeign_callback()\n", encoding="utf-8")

    result = guardrails._entrypoint_inventory("polisyos.fixture")

    assert result.exports == ("Old",)
    assert result.export_count == 1
    assert result.export_resolution["complete_verdict"] is True
    reads = {
        row["path"]
        for row in result.export_resolution["inputs"]
        if row["operation"] == "read_bytes"
    }
    assert "src/polisyos/fixture/exports.py" in reads
    assert "src/polisyos/fixture/effects.py" not in reads


def test_unproved_extension_protocol_retains_only_source_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text('__all__ = ["Prefix"]\nif available:\n    __all__.extend(runtime_names)\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.exports == ()
    assert result.export_resolution["declared_export_candidates"] == ["Prefix"]


@pytest.mark.parametrize("requested", ["PASSIVE", "len"])
def test_runtime_source_effect_is_separate_from_static_export_projection(
    tmp_path: Path,
    monkeypatch,
    requested: str,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    (facade.parents[1] / "__init__.py").write_text("__all__ = []\n")
    owner = facade.with_name("owner.py")
    owner.write_text(
        "PASSIVE = 1\n"
        "def __getattr__(name):\n"
        "    import builtins\n"
        '    builtins.sorted = lambda values: ["RuntimeShadow"]\n'
        '    if name == "__path__":\n'
        "        raise AttributeError(name)\n"
        "    return builtins.len\n"
    )
    facade.write_text(
        f"from .owner import {requested}\n"
        'M = {"StaticName": None}\n'
        "StaticName = None\n"
        "__all__ = sorted(M)\n",
        encoding="utf-8",
    )
    observed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys,json;sys.path.insert(0,sys.argv[1]);import polisyos.fixture as f;print(json.dumps(f.__all__))",
            str(guardrails.SRC_ROOT),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert observed.returncode == 0, observed.stdout + observed.stderr
    assert json.loads(observed.stdout) == ["RuntimeShadow"]

    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("StaticName",)
    assert result.export_count == 1
    assert result.export_resolution["complete_verdict"] is True


def test_parent_initializer_effect_is_outside_selected_export_source_slice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    parent = facade.parents[1] / "__init__.py"
    parent.write_text("foreign_callback()\n", encoding="utf-8")

    result = guardrails._entrypoint_inventory("polisyos.fixture")

    assert result.exports == ("Old",)
    assert result.export_count == 1
    assert result.export_resolution["complete_verdict"] is True
    reads = {
        row["path"]
        for row in result.export_resolution["inputs"]
        if row["operation"] == "read_bytes"
    }
    assert "src/polisyos/__init__.py" not in reads


@pytest.mark.parametrize("requested", ["PASSIVE", "len"])
def test_unselected_imports_do_not_control_source_export_inventory(
    tmp_path: Path,
    monkeypatch,
    requested: str,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    owner = facade.with_name("owner.py")
    owner.write_text(
        "PASSIVE = 1\n"
        "def __getattr__(name):\n"
        "    import builtins\n"
        '    builtins.sorted = lambda values: ["RuntimeShadow"]\n'
        "    return builtins.len\n"
    )
    mapping.write_text(
        f'from .owner import {requested}\nPUBLIC_NAMES = {{"Old": None}}\n',
        encoding="utf-8",
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("Old",)
    assert result.export_count == 1
    assert result.export_resolution["complete_verdict"] is True
    read_paths = {
        row["path"]
        for row in result.export_resolution["inputs"]
        if row["operation"] == "read_bytes"
    }
    assert "src/polisyos/fixture/owner.py" not in read_paths


@pytest.mark.parametrize(
    "declaration", ["def ordinary():\n    return 1\n", "async def ordinary():\n    return 1\n"]
)
def test_unselected_function_body_is_outside_source_export_slice(
    tmp_path: Path,
    monkeypatch,
    declaration: str,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        'M = {"StaticName": None}\nStaticName = None\n__all__ = sorted(M)\n' + declaration,
        encoding="utf-8",
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count == 1
    assert result.exports == ("StaticName",)
    assert result.export_resolution["complete_verdict"] is True


def test_missing_unselected_import_does_not_change_source_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        "from .exports import missing_unselected_name\n"
        'M = {"StaticName": None}\n'
        "StaticName = None\n"
        "__all__ = sorted(M)\n",
        encoding="utf-8",
    )
    mapping.write_text("PASSIVE = 1\n", encoding="utf-8")
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count == 1
    assert result.exports == ("StaticName",)
    assert result.export_resolution["complete_verdict"] is True


@pytest.mark.parametrize(
    "declaration",
    [
        "__getattr__ = []\n",
        "__getattr__: list = []\n",
        "__getattr__ = len\n",
        "from .values import PASSIVE as __getattr__\n",
    ],
)
def test_unselected_getattr_binding_does_not_change_direct_source_export(
    tmp_path: Path,
    monkeypatch,
    declaration: str,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.with_name("values.py").write_text("PASSIVE = []\n", encoding="utf-8")
    facade.write_text(
        'StaticName = None\n__all__ = ["StaticName"]\n' + declaration,
        encoding="utf-8",
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count == 1
    assert result.exports == ("StaticName",)
    assert result.export_resolution["complete_verdict"] is True


@pytest.mark.parametrize("name", ["__path__", "__loader__", "__future_protocol__"])
def test_unselected_dunder_binding_does_not_change_direct_source_export(
    tmp_path: Path,
    monkeypatch,
    name: str,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text(
        f'StaticName = None\n__all__ = ["StaticName"]\n{name} = []\n',
        encoding="utf-8",
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count == 1
    assert result.exports == ("StaticName",)
    assert result.export_resolution["complete_verdict"] is True


def test_unresolved_dynamic_declaration_is_byte_equal_across_root_relocation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    rendered = []
    for dirname in ("one", "other"):
        root = tmp_path / dirname
        facade, _ = _fixture(root, monkeypatch)
        facade.write_text("__all__ = choose_runtime_exports()\n", encoding="utf-8")
        policy = guardrails.PackagePolicy(
            module="polisyos.fixture",
            classification="public_experimental",
            facade_mode="eager_exports",
            owner="test-owner",
            readme=facade,
            reference_doc=facade,
            supported_entrypoints=("polisyos.fixture",),
            major_subsystem=False,
            notes="fixture",
        )
        inventory = guardrails.build_public_surface_inventory([policy])
        encoded = guardrails.render_public_surface_json(inventory)
        assert str(root) not in encoded
        assert inventory[0].export_count is None
        assert [row.detail for row in guardrails._check_public_surface_contracts(inventory)] == [
            "incomplete_exports"
        ]
        rendered.append(encoded)
    assert rendered[0] == rendered[1]


def test_finite_selected_alias_chain_has_audited_consumers() -> None:
    tree = ast.parse(
        'OWNER_MAP = {"Alpha": None, "Beta": None}\n'
        "EXPORT_MAP = OWNER_MAP\n"
        "Alpha = None\nBeta = None\n"
        "NAMES = sorted(EXPORT_MAP)\n"
        "__all__ = tuple(NAMES)\n"
    )
    assert guardrails._extract_exports(tree) == ("Alpha", "Beta")


def test_passive_map_alias_table_does_not_change_static_export_names() -> None:
    tree = ast.parse(
        'EXPORTS = {"Alpha": None, "Beta": None}\n'
        "Alpha = None\nBeta = None\n"
        'TABLE = {"package": EXPORTS}\n'
        'def runtime_lookup():\n    return TABLE["package"]\n'
        "__all__ = sorted(EXPORTS)\n"
    )
    assert guardrails._extract_exports(tree) == ("Alpha", "Beta")
    mutated = ast.parse(
        'EXPORTS = {"Alpha": None}\nAlpha = None\n'
        'TABLE = {"package": EXPORTS}\n'
        'TABLE["package"]["Beta"] = None\n'
        "__all__ = sorted(EXPORTS)\n"
    )
    with pytest.raises(ValueError, match="Unresolved"):
        guardrails._extract_exports(mutated)


@pytest.mark.parametrize(
    "error", [ValueError("unexpected"), TypeError("unexpected"), SyntaxError("broken")]
)
def test_unexpected_reader_failure_is_not_relabelled_as_parser_unknown(
    tmp_path: Path,
    monkeypatch,
    error,
) -> None:
    _fixture(tmp_path, monkeypatch)

    def unexpected(*args):
        raise error

    monkeypatch.setattr(guardrails, "_extract_exports", unexpected)
    with pytest.raises(type(error)) as caught:
        guardrails._entrypoint_inventory("polisyos.fixture")
    assert caught.value is error


def test_complete_representation_does_not_grant_complete_inventory_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policies = guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
    inventory = guardrails.build_public_surface_inventory(policies)
    expected = {entry for policy in policies for entry in policy.supported_entrypoints}
    # Preserve a genuine unknown-source counterexample after the actual world
    # facade gains a complete finite conditional family.
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text("__all__ = runtime_names()\n", encoding="utf-8")
    fixture_policy = guardrails.PackagePolicy(
        module="polisyos.fixture",
        classification="public_experimental",
        facade_mode="eager_exports",
        owner="test-owner",
        readme=facade,
        reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",),
        major_subsystem=False,
        notes="opaque source is represented, never counted as complete",
    )
    inventory.extend(guardrails.build_public_surface_inventory([fixture_policy]))
    expected.add("polisyos.fixture")
    payload = json.loads(guardrails.render_public_surface_json(inventory))
    rows = [row for package in payload["packages"] for row in package["entrypoints"]]
    assert {row["module"] for row in rows} == expected
    conditional = {row["module"] for row in rows if row["source_export_profiles"]}
    assert "polisyos.fabric.world" in conditional
    assert all(
        row["export_resolution"]["complete"] is True
        and all(
            profile["runtime_condition_evaluation"] == "UNRUN"
            for profile in row["source_export_profiles"]
        )
        for row in rows
        if row["module"] in conditional
    )
    unknown = {
        row["module"]
        for row in rows
        if row["export_count"] is None and not row["source_export_profiles"]
    }
    assert "polisyos.fixture" in unknown
    assert all(
        row["export_resolution"]["complete"] is False for row in rows if row["module"] in unknown
    )
    assert {
        item.subject
        for item in guardrails._check_public_surface_contracts(inventory)
        if item.detail == "incomplete_exports"
    } == unknown


def test_catalog_run_profile_is_exported_from_core_contracts_facade() -> None:
    import polisyos.core.contracts as contracts
    from polisyos.core.contracts.control import CatalogRunProfile as ControlCatalogRunProfile

    assert "CatalogRunProfile" in contracts.__all__
    assert contracts.CatalogRunProfile is ControlCatalogRunProfile


def test_public_inventory_readset_is_independent_of_directory_enumeration_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same real facade/children yield identical inventory on fresh filesystems."""
    facade, _mapping = _fixture(tmp_path, monkeypatch)
    package = facade.parent
    facade.write_text(
        "import importlib\n"
        "__all__ = ['alpha', 'omega']\n"
        "def __getattr__(name):\n"
        "    if name not in __all__:\n"
        "        raise AttributeError(name)\n"
        "    module = importlib.import_module(f'polisyos.fixture.{name}')\n"
        "    globals()[name] = module\n"
        "    return module\n",
        encoding="utf-8",
    )
    for name in ("omega.py", "alpha.py", "README.md"):
        (package / name).write_text("", encoding="utf-8")
    original_iterdir = Path.iterdir
    snapshots = []
    for reverse in (False, True):
        with monkeypatch.context() as enumeration:

            def reordered(path: Path, *, reverse: bool = reverse):
                return iter(
                    sorted(original_iterdir(path), key=lambda child: child.name, reverse=reverse)
                )

            enumeration.setattr(Path, "iterdir", reordered)
            snapshots.append(guardrails._entrypoint_inventory("polisyos.fixture"))
    assert snapshots[0].exports == snapshots[1].exports == ("alpha", "omega")
    assert snapshots[0].export_resolution == snapshots[1].export_resolution

    # The complete child census still records an actually added child.
    (package / "added.py").write_text("", encoding="utf-8")
    changed = guardrails._entrypoint_inventory("polisyos.fixture")
    assert changed.export_resolution != snapshots[0].export_resolution
    assert any(
        row["path"] == "src/polisyos/fixture/added.py"
        for row in changed.export_resolution["inputs"]
    )
