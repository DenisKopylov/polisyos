"""Behavioral selected-source code reconstitution and fail-closed residual controls."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from tools.quality.validation import decomposition_preflight as preflight

PREFIX = "from types import FunctionType\nfrom importlib import import_module\n"
BODY = 'def body(callback):\n    return callback("bridge_callback")\n'
CONSTRUCT = "CODE = body.__code__\nrun = FunctionType(CODE, globals())\n"
CASES = {
    "noop": (PREFIX + "def body():\n    return None\n" + CONSTRUCT + "run()\n", set(), None),
    "literal": (
        PREFIX
        + 'def body():\n    return import_module("bridge_literal")\n'
        + CONSTRUCT
        + "run()\n",
        {"bridge_literal"},
        None,
    ),
    "callback": (PREFIX + BODY + CONSTRUCT + "run(import_module)\n", {"bridge_callback"}, None),
    "code-alias": (
        PREFIX
        + BODY
        + "CODE = body.__code__\nALIAS = CODE\nrun = FunctionType(ALIAS, globals())\nrun(import_module)\n",
        {"bridge_callback"},
        None,
    ),
    "constructor-alias": (
        PREFIX
        + BODY
        + "Ctor = FunctionType\nCODE = body.__code__\nrun = Ctor(CODE, globals())\nrun(import_module)\n",
        {"bridge_callback"},
        None,
    ),
    "class-method": (
        PREFIX
        + 'class Plain:\n    def load(self, callback):\n        return callback("bridge_class")\nCODE = Plain.load.__code__\nrun = FunctionType(CODE, globals())\nrun(None, import_module)\n',
        {"bridge_class"},
        None,
    ),
    "nested-selected-dispatch": (
        PREFIX
        + 'def dispatch(callback):\n    return callback()\ndef body(callback):\n    def inner():\n        return callback("bridge_nested")\n    return dispatch(inner)\n'
        + CONSTRUCT
        + "run(import_module)\n",
        {"bridge_nested"},
        None,
    ),
    "deferred-noop": (
        PREFIX + "def body():\n    return None\n" + CONSTRUCT + "def later():\n    return run()\n",
        set(),
        None,
    ),
    "deferred-literal": (
        PREFIX
        + 'def body():\n    return import_module("bridge_deferred")\n'
        + CONSTRUCT
        + "def later():\n    return run()\n",
        {"bridge_deferred"},
        None,
    ),
    "frozen-old-code": (
        PREFIX
        + BODY
        + "def replacement(callback):\n    return None\nCODE = body.__code__\nbody.__code__ = replacement.__code__\nrun = FunctionType(CODE, globals())\nrun(import_module)\n",
        {"bridge_callback"},
        None,
    ),
    "live-global-alias": (
        PREFIX
        + 'def body():\n    return load("bridge_live")\nCODE = body.__code__\nns = globals()\nother = ns\nrun = FunctionType(CODE, ns)\nother["load"] = import_module\nrun()\n',
        {"bridge_live"},
        None,
    ),
    "construction-builtins": (
        PREFIX
        + 'def body():\n    return __import__("bridge_builtin")\n'
        + CONSTRUCT
        + 'globals()["__builtins__"] = {}\nrun()\n',
        {"bridge_builtin"},
        None,
    ),
    "two-code-origins": (
        PREFIX
        + 'def left(callback):\n    return callback("bridge_left")\ndef right(callback):\n    return callback("bridge_right")\nif callable(None):\n    CODE = left.__code__\nelse:\n    CODE = right.__code__\nrun = FunctionType(CODE, globals())\nrun(import_module)\n',
        {"bridge_left", "bridge_right"},
        None,
    ),
    "supplied-default": (
        PREFIX + BODY + 'CODE = body.__code__\nrun = FunctionType(CODE, globals(), "copy", ())\n',
        None,
        "defaults, closure",
    ),
    "supplied-closure": (
        PREFIX
        + BODY
        + 'CODE = body.__code__\nrun = FunctionType(CODE, globals(), "copy", None, ())\n',
        None,
        "defaults, closure",
    ),
    "opaque-code": (PREFIX + "run = FunctionType(opaque_code, globals())\n", None, "code origin"),
    "foreign-globals": (
        PREFIX + BODY + "CODE = body.__code__\nrun = FunctionType(CODE, {})\n",
        None,
        "same-origin live globals",
    ),
    "opaque-constructor": (
        PREFIX + BODY + "CODE = body.__code__\nrun = opaque(CODE, globals())\n",
        None,
        "escapes",
    ),
    "homonym": (
        "def FunctionType(code, namespace):\n    return None\ndef body():\n    return None\nCODE = body.__code__\nrun = FunctionType(CODE, globals())\nrun()\n",
        set(),
        None,
    ),
    "changed-before-capture": (
        PREFIX
        + BODY
        + "def replacement():\n    return None\nbody.__code__ = replacement.__code__\nCODE = body.__code__\nrun = FunctionType(CODE, globals())\n",
        None,
        "code was mutated",
    ),
    "opaque-global-write": (
        PREFIX + BODY + CONSTRUCT + "globals()[unknown_key] = None\nrun(import_module)\n",
        None,
        "opaque writes",
    ),
    "changed-builtins-before": (
        PREFIX + BODY + 'globals()["__builtins__"] = {}\n' + CONSTRUCT,
        None,
        "construction builtins",
    ),
    "opaque-executor": (
        PREFIX
        + 'def body(callback):\n    def inner():\n        return callback("bridge_opaque")\n    return executor.submit(inner)\n'
        + CONSTRUCT
        + "run(import_module)\n",
        None,
        "opaque callable dispatch",
    ),
    "mutable-closure-cell": (
        PREFIX
        + 'def body(callback):\n    def inner():\n        return callback("bridge_cell")\n    callback = opaque\n    return inner()\n'
        + CONSTRUCT
        + "run(import_module)\n",
        None,
        "closure cells",
    ),
    "reconstructed-escape": (PREFIX + BODY + CONSTRUCT + "opaque(run)\n", None, "escapes"),
    "original-default-not-borrowed": (
        PREFIX
        + 'def body(callback=None):\n    return callback("bridge_default")\n'
        + CONSTRUCT
        + "run()\n",
        None,
        "arguments do not bind",
    ),
    "unknown-callback": (
        PREFIX + BODY + CONSTRUCT + "def later(callback):\n    return run(callback)\n",
        None,
        "opaque callable dispatch",
    ),
    "deferred-callback": (
        PREFIX + BODY + CONSTRUCT + "def later():\n    return run(import_module)\n",
        {"bridge_callback"},
        None,
    ),
    "constructed-code-mutation": (
        PREFIX + BODY + CONSTRUCT + "run.__code__ = opaque_code\nrun(import_module)\n",
        None,
        "callable mutation",
    ),
    "constructed-default-mutation": (
        PREFIX + BODY + CONSTRUCT + "run.__defaults__ = ()\nrun(import_module)\n",
        None,
        "callable mutation",
    ),
    "constructed-code-deletion": (
        PREFIX + BODY + CONSTRUCT + "del run.__code__\nrun(import_module)\n",
        None,
        "callable mutation",
    ),
    "function-namespace-introspection": (
        PREFIX
        + BODY
        + "ns = body.__globals__\nCODE = body.__code__\nrun = FunctionType(CODE, ns)\n",
        None,
        "same-origin live globals",
    ),
    "constructor-module-mutation": (
        "import types\nfrom importlib import import_module\n"
        + BODY
        + "CODE = body.__code__\ntypes.FunctionType = opaque\nrun = types.FunctionType(CODE, globals())\nrun(import_module)\n",
        None,
        "ambiguous or unresolved",
    ),
    "unknown-code-alternative": (
        PREFIX
        + BODY
        + "if callable(None):\n    CODE = body.__code__\nelse:\n    CODE = opaque_code\nrun = FunctionType(CODE, globals())\n",
        None,
        "code origin",
    ),
    "live-global-removed": (
        PREFIX
        + 'load = import_module\ndef body():\n    return load("bridge_removed")\n'
        + CONSTRUCT
        + 'globals()["load"] = None\nrun()\n',
        None,
        "opaque callable dispatch",
    ),
    "opaque-executor-context": (
        PREFIX
        + 'def body(callback):\n    def inner():\n        return callback("bridge_context")\n    return executor.submit(context.run, inner)\n'
        + CONSTRUCT
        + "run(import_module)\n",
        None,
        "opaque callable dispatch",
    ),
    "setattr-original-opaque-code": (
        PREFIX + BODY + 'setattr(body, "__code__", opaque_code)\n' + CONSTRUCT,
        None,
        "code was mutated",
    ),
    "setattr-original-known-code": (
        PREFIX
        + BODY
        + 'def replacement(callback):\n    return None\nsetattr(body, "__code__", replacement.__code__)\n'
        + CONSTRUCT,
        None,
        "code was mutated",
    ),
    "setattr-original-after-capture": (
        PREFIX
        + BODY
        + 'CODE = body.__code__\nsetattr(body, "__code__", opaque_code)\nrun = FunctionType(CODE, globals())\nrun(import_module)\n',
        {"bridge_callback"},
        None,
    ),
    "setattr-constructed-opaque-code": (
        PREFIX + BODY + CONSTRUCT + 'setattr(run, "__code__", opaque_code)\nrun(import_module)\n',
        None,
        "callable mutation",
    ),
    "delattr-constructed-code": (
        PREFIX + BODY + CONSTRUCT + 'delattr(run, "__code__")\nrun(import_module)\n',
        None,
        "callable mutation",
    ),
    "opaque-function-storage": (
        PREFIX + BODY + "container.member = body\n" + CONSTRUCT + "run(import_module)\n",
        None,
        "code was mutated",
    ),
    "unresolved-setter-target": (
        PREFIX
        + BODY
        + CONSTRUCT
        + 'setattr(opaque_target, "__code__", opaque_code)\nrun(import_module)\n',
        None,
        "opaque source effects",
    ),
    "unresolved-expanded-setter": (
        PREFIX + BODY + CONSTRUCT + "setattr(*opaque_args)\nrun(import_module)\n",
        None,
        "opaque source effects",
    ),
    "opaque-between-construct-call": (
        PREFIX + BODY + CONSTRUCT + "opaque()\nrun(import_module)\n",
        None,
        "opaque source effects",
    ),
    "opaque-before-construct": (
        PREFIX + BODY + "opaque()\n" + CONSTRUCT + "run(import_module)\n",
        None,
        "opaque source effects",
    ),
    "unknown-code-join-escape": (
        PREFIX
        + "def body():\n    return None\ndef expose(opaque_code):\n    if callable(None):\n        CODE = body.__code__\n    else:\n        CODE = opaque_code\n    opaque(CODE)\n",
        None,
        "escapes",
    ),
    "unknown-callable-join-call": (
        PREFIX
        + "def body():\n    return None\n"
        + CONSTRUCT
        + "def expose(opaque_callable):\n    if callable(None):\n        chosen = run\n    else:\n        chosen = opaque_callable\n    chosen()\n",
        None,
        "ambiguous or unresolved",
    ),
    "unknown-callable-join-escape": (
        PREFIX
        + "def body():\n    return None\n"
        + CONSTRUCT
        + "def expose(opaque_callable):\n    if callable(None):\n        chosen = run\n    else:\n        chosen = opaque_callable\n    opaque(chosen)\n",
        None,
        "escapes",
    ),
    "unknown-code-sequence-escape": (
        PREFIX
        + "def body():\n    return None\ndef expose(opaque_code):\n    if callable(None):\n        CODE = body.__code__\n    else:\n        CODE = opaque_code\n    opaque([CODE])\n",
        None,
        "escapes",
    ),
    "unknown-code-mapping-escape": (
        PREFIX
        + 'def body():\n    return None\ndef expose(opaque_code):\n    if callable(None):\n        CODE = body.__code__\n    else:\n        CODE = opaque_code\n    opaque({"code": CODE})\n',
        None,
        "escapes",
    ),
    "unknown-code-map-lookup-escape": (
        PREFIX
        + 'def body():\n    return None\nCODE = body.__code__\ndef expose(key, fallback):\n    bag = {"code": CODE}\n    chosen = bag.get(key, fallback)\n    opaque(chosen)\n',
        None,
        "unresolved importer provenance",
    ),
    "unknown-callable-return": (
        PREFIX
        + "def body():\n    return None\n"
        + CONSTRUCT
        + "def expose(opaque_callable):\n    if callable(None):\n        chosen = run\n    else:\n        chosen = opaque_callable\n    return chosen\n",
        None,
        "function return",
    ),
    "unknown-callable-storage": (
        PREFIX
        + "def body():\n    return None\n"
        + CONSTRUCT
        + "def expose(opaque_callable):\n    if callable(None):\n        chosen = run\n    else:\n        chosen = opaque_callable\n    container.member = chosen\n",
        None,
        "escapes",
    ),
    "pure-extraction-sibling": (
        PREFIX
        + 'def body():\n    return None\nCODE = body.__code__\nbag = {"code": CODE, "text": "safe"}\nopaque(bag["text"])\n',
        set(),
        None,
    ),
    "pure-len-sibling": (
        PREFIX + "def body():\n    return None\nCODE = body.__code__\nopaque(len([CODE]))\n",
        set(),
        None,
    ),
    "unknown-match-sequence-capture": (
        "def body():\n    return None\ndef expose(unknown):\n    if callable(None):\n        value = [body.__code__]\n    else:\n        value = unknown\n    match value:\n        case [x]:\n            opaque(x)\n",
        None,
        "escapes",
    ),
    "unknown-match-mapping-capture": (
        'def body():\n    return None\ndef expose(unknown):\n    if callable(None):\n        value = {"code": body.__code__}\n    else:\n        value = unknown\n    match value:\n        case {"code": x}:\n            opaque(x)\n',
        None,
        "escapes",
    ),
    "known-match-mapping-capture": (
        'def body():\n    return None\nvalue = {"code": body.__code__}\nmatch value:\n    case {"code": x}:\n        opaque(x)\n',
        None,
        "escapes",
    ),
    "nested-match-sequence-capture": (
        "def body():\n    return None\ndef expose(unknown):\n    if callable(None):\n        value = [[body.__code__]]\n    else:\n        value = unknown\n    match value:\n        case [x]:\n            opaque(x)\n",
        None,
        "escapes",
    ),
    "unknown-match-class-capture": (
        "class Box:\n    pass\ndef body():\n    return None\ndef expose(unknown):\n    if callable(None):\n        value = [body.__code__]\n    else:\n        value = unknown\n    match value:\n        case Box(code=x):\n            opaque(x)\n",
        None,
        "escapes",
    ),
    "known-match-sequence-capture": (
        "def body():\n    return None\nvalue = [body.__code__]\nmatch value:\n    case [x]:\n        opaque(x)\n",
        None,
        "escapes",
    ),
    "known-pure-match-capture": (
        'value = ["safe"]\nmatch value:\n    case [x]:\n        opaque(x)\n',
        set(),
        None,
    ),
}


def collect_case(root: Path, source: str) -> list[dict]:
    """Select a real byte-backed fixture root without executing its source modules."""
    for scope in ("src", "tools", "apps", "packages"):
        (root / scope).mkdir(parents=True, exist_ok=True)
    package = root / "src/polisyos"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "bridge.py").write_text(source, encoding="utf-8")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(preflight, "REPO_ROOT", root)
        patch.setattr(preflight, "SRC_ROOT", root / "src")
        return preflight.collect_dynamic_imports()


@pytest.mark.parametrize("name", CASES)
def test_dynamic_code_reconstitution(name: str, tmp_path: Path) -> None:
    """Observe source-body effects or require the declared bounded refusal."""
    source, expected, refusal = CASES[name]
    if refusal is not None:
        with pytest.raises(preflight.DynamicImportCollectionError, match=refusal):
            collect_case(tmp_path, source)
    else:
        entries = collect_case(tmp_path, source)
        assert {entry["pattern"] for entry in entries} == expected
        assert all(entry["source_file"] == "src/polisyos/bridge.py" for entry in entries)
        assert all(entry["call"] in {"importlib.import_module", "__import__"} for entry in entries)
        locations = {
            node.lineno
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in expected
        }
        assert all(entry["line"] in locations for entry in entries)


def test_dynamic_code_invocation_removal_is_semantic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing only body transfer loses the callback effect while retaining all source."""
    source = CASES["callback"][0]
    positive = collect_case(tmp_path / "positive", source)
    assert {entry["pattern"] for entry in positive} == {"bridge_callback"}
    transfer = preflight._DynamicImportSourceScanner._source_function_call

    def removed(self, node, callee, arguments, environment, scope_info, *, awaited):
        alternatives = callee.items if callee.kind == "union" else (callee,)
        if any(
            item.kind in {"reconstructed_function", "source_closure"} for item in alternatives or ()
        ):
            return preflight._DYNAMIC_OTHER
        return transfer(self, node, callee, arguments, environment, scope_info, awaited=awaited)

    with monkeypatch.context() as patch:
        patch.setattr(preflight._DynamicImportSourceScanner, "_source_function_call", removed)
        removed_entries = collect_case(tmp_path / "removed", source)
        assert "bridge_callback" not in {entry["pattern"] for entry in removed_entries}
    assert preflight._DynamicImportSourceScanner._source_function_call is transfer
    assert collect_case(tmp_path / "restored", source) == positive


def test_dynamic_code_join_provenance_removal_is_semantic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing origin transfer loses the negative despite retained field/constructor markers."""
    source = CASES["unknown-code-join-escape"][0]
    with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
        collect_case(tmp_path / "positive", source)
    transfer = preflight._dynamic_join_with_guarded_origin

    def removed(bindings, result, *, trusted_result=False):
        value = transfer(bindings, result, trusted_result=trusted_result)
        return replace(value, source_execution_origins=())

    with monkeypatch.context() as patch:
        patch.setattr(preflight, "_dynamic_join_with_guarded_origin", removed)
        # Constructor normalization independently retains guarded unknown meaning.
        with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
            collect_case(tmp_path / "removed", source)
    assert preflight._dynamic_join_with_guarded_origin is transfer
    with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
        collect_case(tmp_path / "restored", source)


def test_dynamic_code_normalization_removal_is_semantic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disable only constructor normalization; unchanged match source escapes again."""
    source = CASES["unknown-match-sequence-capture"][0]
    with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
        collect_case(tmp_path / "positive", source)
    normalize = preflight._DynamicImportBinding._normalize_negative_execution
    with monkeypatch.context() as patch:
        patch.setattr(
            preflight._DynamicImportBinding, "_normalize_negative_execution", lambda _self: None
        )
        assert collect_case(tmp_path / "removed", source) == []
    assert preflight._DynamicImportBinding._normalize_negative_execution is normalize
    with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
        collect_case(tmp_path / "restored", source)
