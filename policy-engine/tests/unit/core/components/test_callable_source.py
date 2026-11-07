"""Real source/forged-code controls for the public descriptive source observer."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import FunctionType

import pytest

from polisyos.core.components import describe_callable_source


def test_public_callable_source_observer_reconciles_actual_code_and_refuses_same_file_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "fixture_callable_source.py"
    path.write_text(
        "def sample():\n    raise AssertionError('must not execute')\n", encoding="utf-8"
    )
    module_name = "fixture_callable_source"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    actual = module.sample
    observed = describe_callable_source(actual, expected_module=module_name)
    assert observed == {
        "basis": "recomputed",
        "module": module_name,
        "qualname": "sample",
        "module_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    assert describe_callable_source(actual, expected_module="other_module") == {
        "basis": "not_established"
    }
    forged_module_code = compile("def sample():\n    return 'forged'\n", str(path), "exec")
    forged_function_code = next(
        code for code in forged_module_code.co_consts if hasattr(code, "co_code")
    )
    forged = FunctionType(forged_function_code, module.__dict__)
    assert forged.__module__ == actual.__module__
    assert forged.__code__.co_filename == actual.__code__.co_filename
    assert describe_callable_source(forged, expected_module=module_name) == {
        "basis": "not_established"
    }
    # Keep the original callable; change only the actual source on disk.
    path.write_text("def sample():\n    return 'changed on disk'\n", encoding="utf-8")
    assert describe_callable_source(actual, expected_module=module_name) == {
        "basis": "not_established"
    }


@pytest.mark.parametrize("value", [len, object(), None])
def test_callable_source_observer_does_not_invent_unsupported_origin(value: object) -> None:
    assert describe_callable_source(value, expected_module="builtins") == {
        "basis": "not_established"
    }
