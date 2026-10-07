"""Regression tests for the tracked Python compiler-caller census."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCANNER_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/research/e02-cloud-test-plan/implementation-handoffs/A/compiler-full/census_tracked_python.py"
)
_SCANNER_SPEC = importlib.util.spec_from_file_location(
    "e02_census_tracked_python", _SCANNER_PATH
)
if _SCANNER_SPEC is None or _SCANNER_SPEC.loader is None:
    raise RuntimeError("tracked_python_census_spec_unavailable")
_CENSUS = importlib.util.module_from_spec(_SCANNER_SPEC)
sys.modules[_SCANNER_SPEC.name] = _CENSUS
_SCANNER_SPEC.loader.exec_module(_CENSUS)

_COMPILER_MODULE = "polisyos.data_requirement.compiler"
_PACKAGE_INIT_PATHS = {
    "polisyos/__init__.py",
    "polisyos/data_requirement/__init__.py",
}


def _source_findings(source: str) -> dict[str, list[dict[str, object]]]:
    return _CENSUS.source_findings(
        "synthetic_req_01_caller.py",
        source,
        _PACKAGE_INIT_PATHS,
    )


def test_unrebound_global_and_nonlocal_import_aliases_remain_resolved() -> None:
    source = f'''\
from importlib import import_module as module_loader

def use_global_alias():
    global module_loader
    module_loader("{_COMPILER_MODULE}")

def import_global_alias_in_function():
    global function_loader
    from importlib import import_module as function_loader
    function_loader("{_COMPILER_MODULE}")

def outer():
    from importlib import import_module as enclosing_loader
    def use_nonlocal_alias():
        nonlocal enclosing_loader
        enclosing_loader("{_COMPILER_MODULE}")
'''

    findings = _source_findings(source)

    assert [row["module"] for row in findings["dynamic_import_literals"]] == [
        _COMPILER_MODULE,
        _COMPILER_MODULE,
        _COMPILER_MODULE,
    ]
    assert findings["unresolved_reflective_calls"] == []


def test_global_and_nonlocal_rebindings_are_unresolved_for_the_sibling_scope() -> None:
    source = f'''\
from importlib import import_module as module_loader

def rebind_global_alias():
    global module_loader
    module_loader = lambda name: None
    return module_loader("{_COMPILER_MODULE}")

def use_global_alias_from_sibling():
    return module_loader("{_COMPILER_MODULE}")

def outer():
    from importlib import import_module as enclosing_loader
    def rebind_nonlocal_alias():
        nonlocal enclosing_loader
        enclosing_loader = lambda name: None
        return enclosing_loader("{_COMPILER_MODULE}")
    return rebind_nonlocal_alias()
'''
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - execute the controlled fixture to prove its rebindings are real.
        compile(source, "synthetic_global_nonlocal_rebinding.py", "exec"), namespace
    )
    assert namespace["rebind_global_alias"]() is None  # type: ignore[operator]
    assert namespace["use_global_alias_from_sibling"]() is None  # type: ignore[operator]
    assert namespace["outer"]() is None  # type: ignore[operator]

    findings = _source_findings(source)

    assert findings["dynamic_import_literals"] == []
    unresolved = findings["unresolved_reflective_calls"]
    assert len(unresolved) == 3
    assert {row["target"] for row in unresolved} == {_COMPILER_MODULE}
    assert {row["classification"] for row in unresolved} == {"UNRESOLVED"}


def test_rebound_global_and_nonlocal_getattr_receivers_are_unresolved() -> None:
    source = f'''\
import {_COMPILER_MODULE} as module_alias

def fake_global_receiver():
    global module_alias
    module_alias = object()
    return getattr(module_alias, "_digest")

def outer():
    import {_COMPILER_MODULE} as enclosing_alias
    def fake_nonlocal_receiver():
        nonlocal enclosing_alias
        enclosing_alias = object()
        return getattr(enclosing_alias, "_digest")
    return fake_nonlocal_receiver()
'''

    findings = _source_findings(source)

    assert findings["reflection_literals"] == []
    unresolved = findings["unresolved_reflective_calls"]
    assert len(unresolved) == 2
    assert {row["target"] for row in unresolved} == {_COMPILER_MODULE}
    assert {row["classification"] for row in unresolved} == {"UNRESOLVED"}


def test_unrelated_global_and_nonlocal_callbacks_are_not_reflection_evidence() -> None:
    source = '''\
def global_callback_case(value, receiver):
    global callback
    callback = lambda *args: None
    callback(value)
    callback(receiver, "_digest")

def global_callback_sibling(value):
    callback(value)

def outer():
    callback = lambda *args: None
    def nonlocal_callback_case(value, receiver):
        nonlocal callback
        callback = lambda *args: None
        callback(value)
        callback(receiver, "_digest")
'''

    findings = _source_findings(source)

    assert findings["unresolved_reflective_calls"] == []


def test_unknown_callback_with_compiler_receiver_and_retired_name_is_unresolved() -> None:
    source = f'''\
import {_COMPILER_MODULE} as compiler_alias

def unknown_reflector():
    global callback
    callback = lambda *args: None
    callback(compiler_alias, "_digest")
'''

    findings = _source_findings(source)

    unresolved = findings["unresolved_reflective_calls"]
    assert len(unresolved) == 1
    assert unresolved[0]["target"] == _COMPILER_MODULE
    assert unresolved[0]["retired_name"] == "_digest"
    assert unresolved[0]["classification"] == "UNRESOLVED"


def test_known_import_rebound_with_dynamic_argument_stays_unresolved() -> None:
    source = '''\
from importlib import import_module as module_loader

def dynamic_import_call(module_name):
    global module_loader
    module_loader = lambda name: None
    return module_loader(module_name)
'''

    findings = _source_findings(source)

    unresolved = findings["unresolved_reflective_calls"]
    assert len(unresolved) == 1
    assert unresolved[0]["possible_apis"] == ["import_module"]
    assert unresolved[0]["target"] is None
    assert unresolved[0]["classification"] == "UNRESOLVED"


def test_local_shadow_does_not_change_the_sibling_import_binding() -> None:
    source = f'''\
from importlib import import_module as module_loader

def local_shadow():
    module_loader = lambda name: None
    return module_loader("{_COMPILER_MODULE}")

def unaffected_sibling():
    return module_loader("{_COMPILER_MODULE}")
'''

    findings = _source_findings(source)

    assert [row["module"] for row in findings["dynamic_import_literals"]] == [
        _COMPILER_MODULE
    ]
    assert len(findings["unresolved_reflective_calls"]) == 1
    assert findings["unresolved_reflective_calls"][0]["classification"] == "UNRESOLVED"
