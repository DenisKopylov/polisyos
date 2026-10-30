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
    "noop": (
        PREFIX + "def body():\n    return None\n" + CONSTRUCT + "run()\n",
        set(),
        None,
    ),
    "literal": (
        PREFIX
        + 'def body():\n    return import_module("bridge_literal")\n'
        + CONSTRUCT
        + "run()\n",
        {"bridge_literal"},
        None,
    ),
    "callback": (
        PREFIX + BODY + CONSTRUCT + "run(import_module)\n",
        {"bridge_callback"},
        None,
    ),
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
    "opaque-code": (
        PREFIX + "run = FunctionType(opaque_code, globals())\n",
        None,
        "code origin",
    ),
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
    "reconstructed-escape": (
        PREFIX + BODY + CONSTRUCT + "opaque(run)\n",
        None,
        "escapes",
    ),
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
    "untransferred-deferred-source-mutator": (
        'from types import FunctionType\nfrom importlib import import_module\n\ndef body(callback):\n    return None\n\ndef replacement(callback):\n    return callback("deferred_mutator_target")\n\nCODE = body.__code__\nrun = FunctionType(CODE, globals())\n\ndef mutate(target, code):\n    setattr(target, "__code__", code)\n\ndef consume(unknown_target, unknown_code):\n    mutate(unknown_target, unknown_code)\n    return run(import_module)\n',
        None,
        "opaque source effects",
    ),
    "transferred-module-source-helper": (
        PREFIX
        + 'def harmless():\n    return None\ndef body(callback):\n    return callback("deferred_mutator_safe")\n'
        + CONSTRUCT
        + "harmless()\nrun(import_module)\n",
        {"deferred_mutator_safe"},
        None,
    ),
}


# A deferred constructor can hide a real payload without proving its value protocol.
_DEFERRED_OBJECT = """from importlib import import_module
from pydantic import BaseModel
class Carrier(BaseModel):
    loader: object
    def __getattribute__(self, name):
        return super().__getattribute__(name)
def consume(value):
    return None
"""
for _name, _projection in {
    "direct": "value",
    "list": "[value]",
    "tuple": "(value,)",
    "mapping": '{"value": value}',
}.items():
    CASES[f"deferred-object-selected-consumer-{_name}"] = (
        _DEFERRED_OBJECT + "value = Carrier(loader=import_module)\n" + f"consume({_projection})\n",
        None,
        "guarded importer value escapes through a call argument",
    )
CASES["deferred-object-no-sink"] = (
    _DEFERRED_OBJECT + "value = Carrier(loader=import_module)\n",
    set(),
    None,
)
CASES["deferred-object-scalar-consumer"] = (
    _DEFERRED_OBJECT + 'consume(Carrier(loader="ordinary"))\n',
    set(),
    None,
)
for _name, _projection in {
    "unpack": "first, second = value, 1\nopaque(first)\n",
    "unknown-unpack": "def expose(unknown):\n    if callable(None):\n        values = [value]\n    else:\n        values = unknown\n    first, = values\n    opaque(first)\n",
    "dict-unpack": 'def expose(unknown):\n    if callable(None):\n        values = {"code": value}\n    else:\n        values = unknown\n    opaque({**values})\n',
    "star-import": "from unseen import *\nopaque(value)\n",
}.items():
    CASES[f"real-code-unknown-projection-{_name}"] = (
        "def body():\n    return None\nvalue = body.__code__\n" + _projection,
        None,
        "escapes|unresolved",
    )


for _operator in ("left + right", "-left", "left == right"):
    CASES[f"protected-opaque-operator-{_operator}"] = (
        PREFIX
        + f"def body(left, right):\n    return {_operator}\n"
        + CONSTRUCT
        + "run(unknown_left, unknown_right)\n",
        None,
        "opaque operator dispatch",
    )


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
        # Keep every marker and source byte; remove only the actual origin transfer.
        assert collect_case(tmp_path / "removed", source) == []
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
            preflight._DynamicImportBinding,
            "_normalize_negative_execution",
            lambda _self: None,
        )
        assert collect_case(tmp_path / "removed", source) == []
    assert preflight._DynamicImportBinding._normalize_negative_execution is normalize
    with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
        collect_case(tmp_path / "restored", source)


def test_dynamic_deferred_payload_removal_is_semantic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erase only the payload capability; retain source, importer and constructor."""
    source = CASES["deferred-object-selected-consumer-direct"][0]
    with pytest.raises(preflight.DynamicImportCollectionError, match="a call argument"):
        collect_case(tmp_path / "positive", source)
    transfer = preflight._DynamicImportSourceBindings._deferred_source_class_instance_binding

    def removed(self, *args, **kwargs):
        return replace(transfer(self, *args, **kwargs), opaque_payload_origins=())

    with monkeypatch.context() as patch:
        patch.setattr(
            preflight._DynamicImportSourceBindings,
            "_deferred_source_class_instance_binding",
            removed,
        )
        assert collect_case(tmp_path / "removed", source) == []
    assert (
        preflight._DynamicImportSourceBindings._deferred_source_class_instance_binding is transfer
    )
    with pytest.raises(preflight.DynamicImportCollectionError, match="a call argument"):
        collect_case(tmp_path / "restored", source)


_R12_PROTECTED = "from types import FunctionType\ndef body(value):\n    return {expression}\nCODE = body.__code__\nrun = FunctionType(CODE, globals())\ndef later(value):\n    return run(value)\n"
_R12_CASES = {
    "truth-and": (_R12_PROTECTED.format(expression="value and None"), "opaque implicit dispatch"),
    "truth-or": (_R12_PROTECTED.format(expression="value or None"), "opaque implicit dispatch"),
    "format": (_R12_PROTECTED.format(expression='f"{value}"'), "opaque implicit dispatch"),
    "set-hash": (_R12_PROTECTED.format(expression="{value}"), "opaque implicit dispatch"),
    "dict-hash": (_R12_PROTECTED.format(expression="{value: None}"), "opaque implicit dispatch"),
    "builtins-bool": (_R12_PROTECTED.format(expression="bool(value)"), "opaque callable dispatch"),
    "safe-truth": (_R12_PROTECTED.format(expression="True and None"), None),
    "safe-tuple-index": (_R12_PROTECTED.format(expression="(1, 2)[0]"), None),
    "known-code-unknown-star": (
        "def body():\n    return None\ndef expose(unknown):\n    if callable(None):\n        value = [body.__code__]\n    else:\n        value = unknown\n    opaque([*value])\n",
        "escapes",
    ),
    "known-code-star-suffix": (
        "def body():\n    return None\ndef expose(unknown):\n    opaque([body.__code__, *unknown])\n",
        "escapes",
    ),
    "unknown-code-dict-comp": (
        "def body():\n    return None\ndef expose(unknown):\n    opaque({x: body.__code__ for x in unknown})\n",
        "escapes",
    ),
    "unknown-code-list-comp": (
        "def body():\n    return None\ndef expose(unknown):\n    opaque([body.__code__ for x in unknown])\n",
        "escapes",
    ),
    "mapping-spread-keys-not-values": (
        'def body():\n    return None\ndef expose(unknown):\n    opaque([*{"safe": body.__code__}, *unknown])\n',
        None,
    ),
    "unused-code-carrier": (
        "def body():\n    return None\ndef expose(unknown):\n    value = [body.__code__, *unknown]\n",
        None,
    ),
    "control-only-code": (
        "def body():\n    return None\ndef expose(unknown):\n    if body.__code__:\n        result = [1, *unknown]\n    else:\n        result = [2, *unknown]\n    opaque(result)\n",
        None,
    ),
}


@pytest.mark.parametrize("name", _R12_CASES)
def test_dynamic_protected_implicit_and_carrier_projection(name: str, tmp_path: Path) -> None:
    """Protected effects refuse, while only values entering carriers retain origins."""
    source, refusal = _R12_CASES[name]
    if refusal is not None:
        with pytest.raises(preflight.DynamicImportCollectionError, match=refusal):
            collect_case(tmp_path, source)
    else:
        assert collect_case(tmp_path, source) == []


def test_protected_implicit_intake_removal_is_semantic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing the intake alone restores the original empty inventory escape."""
    source = _R12_CASES["truth-and"][0]
    with pytest.raises(preflight.DynamicImportCollectionError, match="opaque implicit dispatch"):
        collect_case(tmp_path / "positive", source)
    original = preflight._dynamic_function_has_unmodeled_implicit_dispatch
    with monkeypatch.context() as patch:
        patch.setattr(
            preflight, "_dynamic_function_has_unmodeled_implicit_dispatch", lambda *_: False
        )
        assert collect_case(tmp_path / "removed", source) == []
    assert preflight._dynamic_function_has_unmodeled_implicit_dispatch is original
    with pytest.raises(preflight.DynamicImportCollectionError, match="opaque implicit dispatch"):
        collect_case(tmp_path / "restored", source)


def test_shape_erasure_member_transfer_removal_is_semantic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing erased-member transfer alone restores the original carrier escape."""
    source = _R12_CASES["known-code-unknown-star"][0]
    with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
        collect_case(tmp_path / "positive", source)
    original = preflight._dynamic_sequence_binding

    def removed(items, **kwargs):
        kwargs.pop("erased_members", None)
        return original(items, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(preflight, "_dynamic_sequence_binding", removed)
        assert collect_case(tmp_path / "removed", source) == []
    assert preflight._dynamic_sequence_binding is original
    with pytest.raises(preflight.DynamicImportCollectionError, match="escapes"):
        collect_case(tmp_path / "restored", source)


@pytest.mark.parametrize(("expression", "refuses"), [("value and None", True), ("None", False)])
def test_protected_cross_module_selected_helper(
    expression: str, refuses: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected helper retains the caller's protected implicit-effect boundary."""
    for scope in ("src", "tools", "apps", "packages"):
        (tmp_path / scope).mkdir(parents=True, exist_ok=True)
    package = tmp_path / "src/polisyos"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helper.py").write_text(
        f"def check(value):\n    return {expression}\n", encoding="utf-8"
    )
    (package / "bridge.py").write_text(
        "from types import FunctionType\nfrom polisyos.helper import check\n"
        "def body(value):\n    return check(value)\nCODE = body.__code__\n"
        "run = FunctionType(CODE, globals())\ndef later(value):\n    return run(value)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(preflight, "SRC_ROOT", tmp_path / "src")
    if refuses:
        with pytest.raises(
            preflight.DynamicImportCollectionError, match="opaque implicit dispatch"
        ):
            preflight.collect_dynamic_imports()
    else:
        assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    ("argument", "refusal"),
    [("value", "opaque implicit dispatch"), ("True", None)],
)
def test_protected_resolved_builtin_truth_protocol(
    argument: str, refusal: str | None, tmp_path: Path
) -> None:
    """A resolved builtin conversion requires a pure operand, not an unknown object."""
    source = (
        "from types import FunctionType\n"
        "from builtins import bool as truth\n"
        "def body(value):\n"
        f"    return truth({argument})\n"
        "CODE = body.__code__\n"
        "run = FunctionType(CODE, globals())\n"
        "def later(value):\n"
        "    return run(value)\n"
    )
    if refusal is not None:
        with pytest.raises(preflight.DynamicImportCollectionError, match=refusal):
            collect_case(tmp_path, source)
    else:
        assert collect_case(tmp_path, source) == []


@pytest.mark.parametrize("module_alias", ["importlib", "loader"])
def test_protected_module_receiver_refuses_without_identity_proof(
    module_alias: str, tmp_path: Path
) -> None:
    """Record the bounded module-attribute precision loss through the collector."""
    import_stmt = (
        "import importlib\n" if module_alias == "importlib" else "import importlib as loader\n"
    )
    source = (
        import_stmt + "from types import FunctionType\n"
        "def body():\n"
        f"    return {module_alias}.import_module('bridge_module')\n"
        "CODE = body.__code__\n"
        "run = FunctionType(CODE, globals())\n"
        "run()\n"
    )
    with pytest.raises(preflight.DynamicImportCollectionError, match="opaque implicit dispatch"):
        collect_case(tmp_path, source)


def test_protected_unknown_receiver_refuses(tmp_path: Path) -> None:
    """An unverified object cannot inherit the admitted module receiver's authority."""
    source = (
        "from types import FunctionType\n"
        "def body(value):\n"
        "    return value.attr('bridge')\n"
        "CODE = body.__code__\n"
        "run = FunctionType(CODE, globals())\n"
        "def later(value):\n"
        "    return run(value)\n"
    )
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match=r"opaque (callable|implicit) dispatch",
    ):
        collect_case(tmp_path, source)


def test_protected_rebound_module_slot_does_not_emit_old_import(tmp_path: Path) -> None:
    """The refused module form must not emit an old target after slot replacement."""
    base = (
        "import importlib\n"
        "from types import FunctionType\n"
        "{before}"
        "def body():\n"
        "    return importlib.import_module('bridge_module')\n"
        "CODE = body.__code__\n"
        "run = FunctionType(CODE, globals())\n"
        "run()\n"
    )
    with pytest.raises(preflight.DynamicImportCollectionError, match="opaque implicit dispatch"):
        collect_case(tmp_path / "stable-module", base.format(before=""))
    replacement = "def replacement(name):\n    return None\nimportlib.import_module = replacement\n"
    error_message = ""
    try:
        changed = collect_case(tmp_path / "changed", base.format(before=replacement))
    except preflight.DynamicImportCollectionError as error:
        error_message = str(error)
        changed = []
    if error_message:
        assert any(
            word in error_message
            for word in ("opaque", "mutat", "unresolved", "ambiguous", "unsupported")
        )
    else:
        assert changed == []


@pytest.mark.parametrize("variant", ["shadowed-parameter", "rebound-global"])
def test_protected_module_receiver_uses_actual_invocation_binding(
    variant: str, tmp_path: Path
) -> None:
    """A module-shaped snapshot cannot authorize a different receiver at a use."""
    stable = (
        "import importlib\n"
        "from types import FunctionType\n"
        "def body():\n"
        "    return importlib.import_module('bridge_module')\n"
        "CODE = body.__code__\n"
        "run = FunctionType(CODE, globals())\n"
        "run()\n"
    )
    with pytest.raises(preflight.DynamicImportCollectionError, match="opaque implicit dispatch"):
        collect_case(tmp_path / "stable-module", stable)
    if variant == "shadowed-parameter":
        unsafe = (
            "import importlib\n"
            "from types import FunctionType\n"
            "def body(importlib):\n"
            "    return importlib.import_module('bridge_module')\n"
            "CODE = body.__code__\n"
            "run = FunctionType(CODE, globals())\n"
            "def later(value):\n"
            "    return run(value)\n"
        )
    else:
        unsafe = (
            "import importlib\n"
            "from types import FunctionType\n"
            "def body():\n"
            "    return importlib.import_module('bridge_module')\n"
            "CODE = body.__code__\n"
            "run = FunctionType(CODE, globals())\n"
            "importlib = unknown\n"
            "run()\n"
        )
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match=(
            r"reconstructed source (?:invocation reaches opaque callable|"
            r"body has opaque implicit) dispatch|"
            r"dynamic importer binding is ambiguous or unresolved through a call target"
        ),
    ):
        collect_case(tmp_path / "unsafe", unsafe)


def test_protected_direct_importer_binding_transfers_effect(tmp_path: Path) -> None:
    """A direct selected importer still emits its source-bound target."""
    source = (
        "from importlib import import_module\n"
        "from types import FunctionType\n"
        "def body():\n"
        "    return import_module('bridge_module')\n"
        "CODE = body.__code__\n"
        "run = FunctionType(CODE, globals())\n"
        "run()\n"
    )
    entries = collect_case(tmp_path, source)
    assert {entry["pattern"] for entry in entries} == {"bridge_module"}
    assert all(entry["call"] == "importlib.import_module" for entry in entries)
    assert all(entry["source_file"] == "src/polisyos/bridge.py" for entry in entries)
