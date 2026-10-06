"""Actual export reader controls, independent of runtime authority or backend fit."""

from __future__ import annotations

import ast
import hashlib
import json
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
        "from .exports import PUBLIC_NAMES as names\n__all__ = sorted(names)\n",
        encoding="utf-8",
    )
    mapping.write_text('PUBLIC_NAMES = {"Old": ("owner", "Old")}\n', encoding="utf-8")
    return facade, mapping


def test_actual_analytics_mapping_is_not_reported_as_empty() -> None:
    from polisyos.ir import analytics
    from polisyos.ir.analytics.causal_queries import CausalEstimatorInterval, CausalResultKind
    from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS

    result = guardrails._entrypoint_inventory("polisyos.ir.analytics")
    assert tuple(analytics.__all__) == tuple(sorted(ANALYTICS_FACADE_EXPORTS))
    assert ANALYTICS_FACADE_EXPORTS["CausalEstimatorInterval"] == (
        "polisyos.ir.analytics.causal_queries", "CausalEstimatorInterval",
    )
    assert ANALYTICS_FACADE_EXPORTS["CausalResultKind"] == (
        "polisyos.ir.analytics.causal_queries", "CausalResultKind",
    )
    assert analytics.CausalEstimatorInterval is CausalEstimatorInterval
    assert analytics.CausalResultKind is CausalResultKind
    # The native profile has these names, but the imported source also creates
    # classes outside the finite static grammar. Do not infer an empty namespace.
    assert result.export_count is None
    assert result.known_export_count == 0
    assert result.export_resolution["complete"] is False
    assert result.export_resolution["declared_export_candidates"] == sorted(ANALYTICS_FACADE_EXPORTS)
    assert "pure-declaration grammar" in result.export_resolution["reason"]
    inputs = result.export_resolution["inputs"]
    paths = {row["path"] for row in inputs if row["operation"] == "read_bytes"}
    assert paths == {
        "src/polisyos/ir/api.py",
        "src/polisyos/ir/analytics/__init__.py",
        "src/polisyos/ir/__init__.py",
        "src/polisyos/__init__.py",
    }
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


def test_outside_selector_is_disclosed_and_does_not_become_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    outside = mapping.with_name("unselected.py")
    outside.write_text('PUBLIC_NAMES = {"Outside": None}\nraise RuntimeError("never run")\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("Old",)
    assert all(
        row["path"] != str(outside.relative_to(tmp_path))
        for row in result.export_resolution["inputs"]
    )
    assert "No module execution or runtime dispatch" in result.export_resolution["selector"]
    assert result.export_resolution["unresolved_by_construction"]


@pytest.mark.parametrize("problem", ["missing", "unreadable", "cycle", "computed", "mutated", "subscript", "conditional"])
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
        mapping.write_text('PUBLIC_NAMES = {"Old": None}\nPUBLIC_NAMES.update({"New": None})\n')
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


def test_unsupported_module_effect_is_reported_without_executing_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    mapping.write_text(
        'raise RuntimeError("module execution forbidden")\n'
        'BASE = {"A": unknown_runtime_owner}\n'
        'PUBLIC_NAMES = {**BASE, "B": object}\n',
    )
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None
    assert result.known_export_count == 0
    assert result.export_resolution["complete"] is False
    assert "Unresolved" in result.export_resolution["reason"]
    assert result.export_resolution["declared_export_candidates"] == ["A", "B"]
    policy = guardrails.PackagePolicy(
        module="polisyos.fixture", classification="public_experimental", facade_mode="eager_exports",
        owner="test-owner", readme=facade, reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",), major_subsystem=False, notes="fixture",
    )
    inventory = guardrails.build_public_surface_inventory([policy])
    serialized = json.loads(guardrails.render_public_surface_json(inventory))["packages"][0]
    assert serialized["exports"] == []
    assert serialized["export_count"] is None
    assert serialized["known_export_count"] == 0
    assert serialized["entrypoints"][0]["export_resolution"]["declared_export_candidates"] == ["A", "B"]
    assert "Source-declared candidates (2; native exports unproved)" in guardrails.render_public_surface_markdown(inventory)
    assert [item.detail for item in guardrails._check_public_surface_contracts(inventory)] == ["incomplete_exports"]


def test_local_names_and_sequence_concat_share_same_reader() -> None:
    tree = ast.parse('M = {"B": None, "A": None}\nN = sorted(M)\n__all__ = tuple(N) + ("C",)\n')
    assert guardrails._extract_exports(tree) == ("A", "B", "C")


def test_removed_import_resolution_keeps_facade_markers_but_original_oracle_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _ = _fixture(tmp_path, monkeypatch)
    original = guardrails._extract_exports
    assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("Old",)
    monkeypatch.setattr(guardrails, "_extract_exports", lambda tree, source=None: ())
    assert guardrails._entrypoint_inventory("polisyos.fixture").has___getattr__ is False
    with pytest.raises(AssertionError):
        assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("Old",)
    monkeypatch.setattr(guardrails, "_extract_exports", original)
    assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("Old",)


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


@pytest.mark.parametrize("binding", ["if runtime():\n    from owner import MAP", "def MAP():\n    pass"])
def test_unsupported_symbol_bindings_cannot_be_hidden_by_literal_declaration(binding: str) -> None:
    tree = ast.parse('MAP = {"Actual": None}\n' + binding + '\n__all__ = sorted(MAP)\n')
    with pytest.raises(ValueError, match="conditional/mutated exports"):
        guardrails._extract_exports(tree)


def test_direct_named_all_import_uses_same_finite_owner_reader(tmp_path: Path, monkeypatch) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade.write_text("from .exports import __all__\n")
    mapping.write_text('__all__ = ["B", "A"]\n')
    assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("B", "A")


def test_closed_literal_extension_exposes_prefix_and_fails_complete_contract(
    tmp_path: Path, monkeypatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text('__all__ = ["Prefix"]\n__all__.extend(["Added"])\n')
    policy = guardrails.PackagePolicy(
        module="polisyos.fixture", classification="public_experimental", facade_mode="eager_exports",
        owner="test-owner", readme=facade, reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",), major_subsystem=False, notes="fixture",
    )
    inventory = guardrails.build_public_surface_inventory([policy])
    row = json.loads(guardrails.render_public_surface_json(inventory))["packages"][0]
    assert row["export_count"] is None
    assert row["known_export_count"] == 1
    assert row["exports"] == ["Prefix"]
    resolution = row["entrypoints"][0]["export_resolution"]
    assert resolution["complete"] is False
    assert resolution["complete_verdict"] is False
    assert any(item["operation"] == "read_bytes" for item in resolution["inputs"])
    markdown = guardrails.render_public_surface_markdown(inventory)
    assert "unknown (1 known prefix)" in markdown
    assert "Known literal prefix (1; total unknown)" in markdown
    violations = guardrails._check_public_surface_contracts(inventory)
    assert [(item.subject, item.detail) for item in violations] == [
        ("polisyos.fixture", "incomplete_exports"),
    ]


@pytest.mark.parametrize("mutation", [
    '__all__ = ["Replacement"]', '__all__.clear()', 'alias = __all__',
    '__all__[0] = "Replacement"', 'if runtime():\n    __all__ = ["Replacement"]',
    'from owner import __all__', '__all__.extend(*runtime_names())', 'mutate()',
])
def test_unproved_prefix_rebind_or_mutation_still_refuses(mutation: str) -> None:
    source = '__all__ = ["Prefix"]\n' + mutation + '\n__all__.extend(runtime_names())\n'
    with pytest.raises(ValueError) as caught:
        guardrails._extract_exports(ast.parse(source))
    assert not isinstance(caught.value, guardrails._IncompleteExportDeclarationError)


def test_current_world_optional_profile_has_unknown_static_total() -> None:
    from polisyos.fabric import world

    row = guardrails._entrypoint_inventory("polisyos.fabric.world")
    literal = next(
        node.value for node in ast.parse((guardrails.REPO_ROOT / row.source_file).read_bytes()).body
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        )
    )
    assert row.export_count is None
    # The source has a literal prefix, but preceding optional-import probes are
    # outside the effect grammar. That prefix is not a proved runtime total.
    literal_names = ast.literal_eval(literal)
    assert len(literal_names) == 41
    assert row.known_export_count == 0
    assert row.exports == ()
    assert row.export_resolution["complete"] is False
    assert row.export_resolution["declared_export_candidates"] == literal_names
    assert tuple(world.__all__[:len(literal_names)]) == tuple(literal_names)
    # The maintained native namespace is a separate observed profile.
    if world._MATERIALIZE_AVAILABLE:
        assert len(world.__all__) == 59 > len(literal_names)
    else:
        assert len(world.__all__) == len(literal_names)


@pytest.mark.parametrize("source", [
    'M = {"x": 1}\nmutate(M)\n__all__ = sorted(M)',
    'M = {"x": 1}\nA = M\nA["y"] = 2\n__all__ = sorted(M)',
    '__all__ = ["x"]\nmutate(__all__)',
    'M = {"x": 1}\nA = [M]\nconsume(A)\n__all__ = sorted(M)',
    'M = {"x": 1}\n__all__ = sorted(M)\nconsume(M)',
    'M = {"x": 1}\nglobals()["M"]["y"] = 2\n__all__ = sorted(M)',
    'M = {"x": 1}\nexec("M[\\\"y\\\"] = 2")\n__all__ = sorted(M)',
    'M = {"x": 1}\ndef mutate():\n    M["y"] = 2\nmutate()\n__all__ = sorted(M)',
    'M = {"x": 1}\nclass C:\n    M["y"] = 2\n__all__ = sorted(M)',
    'M = {"x": 1}\nclass C:\n    global M\n    M = {"y": 2}\n__all__ = sorted(M)',
    'M = {"x": 1}\nclass C(metaclass=unknown):\n    pass\n__all__ = sorted(M)',
    'M = {"x": 1}\nclass C(unknown):\n    pass\n__all__ = sorted(M)',
    'globals()["sorted"] = choose\nM = {"x": 1}\n__all__ = sorted(M)',
    'M = {\n    "x": poison(),\n}\n__all__ = sorted(M)',
    'class D:\n    def __set_name__(self, owner, name):\n        M["y"] = 2\nd = D()\nM = {"x": 1}\nclass C:\n    descriptor = d\n__all__ = sorted(M)',
])
def test_bindings_cannot_escape_finite_declaration_consumers(source: str) -> None:
    with pytest.raises(ValueError, match="Unresolved"):
        guardrails._extract_exports(ast.parse(source))


@pytest.mark.parametrize("source", [
    'globals()["__all__"] = ["RuntimeOnly"]',
    'class C:\n    pass',
])
def test_missing_syntactic_binding_does_not_bypass_effect_audit(source: str) -> None:
    with pytest.raises(guardrails._UnresolvedExportDeclarationError, match="import-time"):
        guardrails._extract_exports(ast.parse(source))


@pytest.mark.parametrize("effect", [
    'def poison(f):\n    return f\n@poison\ndef decorated():\n    pass',
    'def default(value=callback()):\n    pass',
    'def default(value=foreign.attribute):\n    pass',
    'def annotation(value: foreign.attribute):\n    pass',
    'def parameterized[T: foreign.attribute]():\n    pass',
    'ignored = foreign.attribute',
    'ignored = foreign[0]',
    'ignored = foreign + 1',
    'if foreign:\n    pass',
    'with foreign:\n    pass',
    'ignored = [value for value in foreign]',
    'import foreign',
    'from foreign import value',
    'from __future__ import annotations',
])
def test_import_time_profile_refuses_implicit_and_foreign_protocol_effects(effect: str) -> None:
    source = effect + '\nM = {"StaticName": None}\n__all__ = sorted(M)\n'
    with pytest.raises(guardrails._UnresolvedExportDeclarationError, match="pure-declaration grammar"):
        guardrails._extract_exports(ast.parse(source))


def test_plain_function_body_and_closed_defaults_are_outside_import_time_execution() -> None:
    source = (
        'DEFAULT = {"answer": 42}\n'
        'def passive(value=DEFAULT, count: int = 1) -> str:\n'
        '    return foreign.callback(value)\n'
        '__all__ = ["passive"]\n'
    )
    assert guardrails._extract_exports(ast.parse(source)) == ("passive",)


def test_local_import_effects_are_read_and_audited_beyond_selected_mapping(
    tmp_path: Path, monkeypatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    effects = mapping.with_name("effects.py")
    mapping.write_text('from .effects import PASSIVE\nPUBLIC_NAMES = {"StaticName": None}\n')
    effects.write_text('PASSIVE = 1\nforeign_callback()\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.export_resolution["declared_export_candidates"] == ["StaticName"]
    assert result.export_resolution["complete"] is False
    read = next(row for row in result.export_resolution["inputs"] if row["path"].endswith("effects.py") and row["operation"] == "read_bytes")
    assert read["sha256"] == hashlib.sha256(effects.read_bytes()).hexdigest()
    effects.write_text('PASSIVE = 1\n')
    resolved = guardrails._entrypoint_inventory("polisyos.fixture")
    assert resolved.export_count == 1 and resolved.exports == ("StaticName",)


def test_unproved_extension_protocol_retains_only_source_candidates(
    tmp_path: Path, monkeypatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    facade.write_text('__all__ = ["Prefix"]\nif available:\n    __all__.extend(runtime_names)\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.exports == ()
    assert result.export_resolution["declared_export_candidates"] == ["Prefix"]


def test_local_named_import_requires_actual_binding_not_module_getattr(
    tmp_path: Path, monkeypatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    effects = mapping.with_name("effects.py")
    mapping.write_text('from .effects import missing\nPUBLIC_NAMES = {"StaticName": None}\n')
    effects.write_text('def __getattr__(name):\n    return foreign_callback()\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.export_resolution["declared_export_candidates"] == ["StaticName"]
    assert "Unresolved" in result.export_resolution["reason"]


def test_canonical_parent_initializer_effects_are_part_of_source_audit(
    tmp_path: Path, monkeypatch,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    parent = facade.parents[1] / "__init__.py"
    parent.write_text('foreign_callback()\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.export_resolution["declared_export_candidates"] == ["Old"]
    read = next(row for row in result.export_resolution["inputs"] if row["path"] == "src/polisyos/__init__.py" and row["operation"] == "read_bytes")
    assert read["sha256"] == hashlib.sha256(parent.read_bytes()).hexdigest()
    parent.write_text('__all__ = []\n')
    resolved = guardrails._entrypoint_inventory("polisyos.fixture")
    assert resolved.exports == ("Old",) and resolved.export_count == 1


@pytest.mark.parametrize("requested", ["PASSIVE", "len"])
def test_local_import_callable_owner_is_unknown_on_actual_cpython_protocol(
    tmp_path: Path, monkeypatch, requested: str,
) -> None:
    facade, _ = _fixture(tmp_path, monkeypatch)
    (facade.parents[1] / "__init__.py").write_text('__all__ = []\n')
    owner = facade.with_name("owner.py")
    owner.write_text(
        'PASSIVE = 1\n'
        'def __getattr__(name):\n'
        '    import builtins\n'
        '    builtins.sorted = lambda values: ["RuntimeShadow"]\n'
        '    if name == "__path__":\n'
        '        raise AttributeError(name)\n'
        '    return builtins.len\n'
    )
    facade.write_text(
        f'from .owner import {requested}\n'
        'M = {"StaticName": None}\n__all__ = sorted(M)\n'
    )
    observed = subprocess.run(
        [sys.executable, "-I", "-c", 'import sys,json;sys.path.insert(0,sys.argv[1]);import polisyos.fixture as f;print(json.dumps(f.__all__))', str(guardrails.SRC_ROOT)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert observed.returncode == 0, observed.stdout + observed.stderr
    assert json.loads(observed.stdout) == ["RuntimeShadow"]
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.export_resolution["declared_export_candidates"] == ["StaticName"]
    assert result.export_resolution["complete"] is False


@pytest.mark.parametrize("declaration", ['def ordinary():\n    return 1\n', 'async def ordinary():\n    return 1\n'])
def test_all_imported_callable_definitions_are_outside_passive_module_profile(
    tmp_path: Path, monkeypatch, declaration: str,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    mapping.write_text('PUBLIC_NAMES = {"StaticName": None}\n' + declaration)
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.export_resolution["declared_export_candidates"] == ["StaticName"]


def test_imported_name_cannot_borrow_ambient_builtin_binding(tmp_path: Path, monkeypatch) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade.write_text('from .exports import len\n__all__ = ["StaticName"]\n')
    mapping.write_text('PASSIVE = 1\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.export_resolution["declared_export_candidates"] == ["StaticName"]


@pytest.mark.parametrize("declaration, import_refused", [
    ('__getattr__ = []\n', True),
    ('__getattr__: list = []\n', True),
    ('__getattr__ = len\n', False),
    ('from .values import PASSIVE as __getattr__\n', True),
])
def test_passive_dependency_protocol_bindings_are_unknown_on_actual_import(
    tmp_path: Path, monkeypatch, declaration: str, import_refused: bool,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    (facade.parents[1] / "__init__.py").write_text('__all__ = []\n')
    facade.with_name("values.py").write_text('PASSIVE = []\n')
    mapping.write_text('PUBLIC_NAMES = {"StaticName": None}\n' + declaration)
    observed = subprocess.run(
        [sys.executable, "-I", "-c", 'import sys;sys.path.insert(0,sys.argv[1]);import polisyos.fixture', str(guardrails.SRC_ROOT)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    if import_refused:
        assert observed.returncode != 0 and "TypeError" in observed.stderr
    else:
        # A callable module hook is also outside the passive data profile,
        # even when this particular named import succeeds.
        assert observed.returncode == 0, observed.stderr
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.known_export_count == 0
    assert result.export_resolution["declared_export_candidates"] == ["StaticName"]
    assert result.export_resolution["complete"] is False


@pytest.mark.parametrize("name", ["__path__", "__loader__", "__future_protocol__"])
def test_passive_import_profile_refuses_generic_dunder_bindings(
    tmp_path: Path, monkeypatch, name: str,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    mapping.write_text(f'PUBLIC_NAMES = {{"StaticName": None}}\n{name} = []\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.export_count is None and result.export_resolution["complete"] is False


def test_unknown_inventory_is_byte_equal_across_canonical_root_relocation(tmp_path: Path, monkeypatch) -> None:
    rendered = []
    for dirname in ("one", "other"):
        root = tmp_path / dirname
        facade, mapping = _fixture(root, monkeypatch)
        mapping.write_text('PUBLIC_NAMES = {"StaticName": None}\nforeign_callback()\n')
        policy = guardrails.PackagePolicy(
            module="polisyos.fixture", classification="public_experimental", facade_mode="eager_exports",
            owner="test-owner", readme=facade, reference_doc=facade,
            supported_entrypoints=("polisyos.fixture",), major_subsystem=False, notes="fixture",
        )
        inventory = guardrails.build_public_surface_inventory([policy])
        encoded = guardrails.render_public_surface_json(inventory)
        assert str(root) not in encoded
        assert inventory[0].export_count is None
        assert [row.detail for row in guardrails._check_public_surface_contracts(inventory)] == ["incomplete_exports"]
        rendered.append(encoded)
    assert rendered[0] == rendered[1]


def test_finite_selected_alias_chain_has_audited_consumers() -> None:
    tree = ast.parse('M = {"B": None, "A": None}\nA = M\nN = sorted(A)\n__all__ = tuple(N)\n')
    assert guardrails._extract_exports(tree) == ("A", "B")


def test_passive_map_alias_table_is_audited_without_calling_runtime_lookup() -> None:
    tree = ast.parse(
        'M = {"B": None, "A": None}\nTABLE = {"package": M}\n'
        'def runtime_lookup():\n    return TABLE["package"]\n__all__ = sorted(M)\n'
    )
    assert guardrails._extract_exports(tree) == ("A", "B")
    mutated = ast.parse(
        'M = {"A": None}\nTABLE = {"package": M}\n'
        'TABLE["package"]["B"] = None\n__all__ = sorted(M)\n'
    )
    with pytest.raises(ValueError, match="consumer"):
        guardrails._extract_exports(mutated)


@pytest.mark.parametrize("error", [ValueError("unexpected"), TypeError("unexpected"), SyntaxError("broken")])
def test_unexpected_reader_failure_is_not_relabelled_as_parser_unknown(
    tmp_path: Path, monkeypatch, error,
) -> None:
    _fixture(tmp_path, monkeypatch)

    def unexpected(*args):
        raise error

    monkeypatch.setattr(guardrails, "_extract_exports", unexpected)
    with pytest.raises(type(error)) as caught:
        guardrails._entrypoint_inventory("polisyos.fixture")
    assert caught.value is error


def test_complete_representation_does_not_grant_complete_inventory_verdict() -> None:
    policies = guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
    inventory = guardrails.build_public_surface_inventory(policies)
    payload = json.loads(guardrails.render_public_surface_json(inventory))
    expected = {entry for policy in policies for entry in policy.supported_entrypoints}
    rows = [row for package in payload["packages"] for row in package["entrypoints"]]
    assert {row["module"] for row in rows} == expected
    unknown = {row["module"] for row in rows if row["export_count"] is None}
    assert "polisyos.fabric.world" in unknown
    assert all(row["export_resolution"]["complete"] is False for row in rows if row["module"] in unknown)
    assert {
        item.subject for item in guardrails._check_public_surface_contracts(inventory)
        if item.detail == "incomplete_exports"
    } == unknown
