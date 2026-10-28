"""Falsify unstable or underspecified code-observation witnesses."""

from __future__ import annotations

from types import CodeType, FunctionType

import pytest
from _helpers.code_identity import code_fingerprint


def _compiled(source: str) -> CodeType:
    module = compile(source, "<identity-test>", "exec", dont_inherit=True, optimize=0)
    return next(value for value in module.co_consts if isinstance(value, CodeType))


def test_code_fingerprint_is_stable_for_the_actual_invoked_code() -> None:
    code = _compiled("def sample(x):\n    return x + 17\n")
    fn = FunctionType(code, {})
    before = code_fingerprint(code)
    for number in range(100):
        assert fn(number) == number + 17
    assert fn.__code__ is code
    assert code_fingerprint(fn.__code__) == before


def test_code_fingerprint_distinguishes_constants_without_bytecode_change() -> None:
    code = _compiled("def sample():\n    return 'original'\n")
    changed = code.replace(
        co_consts=tuple("changed" if item == "original" else item for item in code.co_consts)
    )
    assert changed.co_code == code.co_code
    assert changed.co_names == code.co_names
    assert code_fingerprint(changed) != code_fingerprint(code)
    assert FunctionType(code, {})() == "original"
    assert FunctionType(changed, {})() == "changed"


def test_code_fingerprint_recurses_into_nested_code() -> None:
    outer = _compiled(
        "def outer():\n    def inner():\n        return 'original'\n    return inner\n"
    )
    inner = next(item for item in outer.co_consts if isinstance(item, CodeType))
    assert "original" in inner.co_consts
    changed_inner = inner.replace(
        co_consts=tuple("changed" if item == "original" else item for item in inner.co_consts)
    )
    changed_outer = outer.replace(
        co_consts=tuple(changed_inner if item is inner else item for item in outer.co_consts)
    )
    assert changed_outer.co_code == outer.co_code
    assert changed_inner.co_code == inner.co_code
    assert code_fingerprint(changed_outer) != code_fingerprint(outer)
    original_nested = FunctionType(outer, {})()
    changed_nested = FunctionType(changed_outer, {})()
    assert original_nested.__code__ is inner
    assert changed_nested.__code__ is changed_inner
    assert original_nested() == "original"
    assert changed_nested() == "changed"


def test_code_fingerprint_preserves_literal_bits_and_unordered_values() -> None:
    base = _compiled("def sample():\n    return None\n")
    assert code_fingerprint(base.replace(co_consts=(0.0,))) != code_fingerprint(
        base.replace(co_consts=(-0.0,))
    )
    left = base.replace(co_consts=(frozenset({"x", "y", "z"}),))
    right = base.replace(co_consts=(frozenset({"z", "x", "y"}),))
    assert code_fingerprint(left) == code_fingerprint(right)
    assert code_fingerprint(base.replace(co_filename="different.py")) != code_fingerprint(base)


def test_code_fingerprint_refuses_unsupported_constant_types() -> None:
    base = _compiled("def sample():\n    return None\n")
    altered = base.replace(co_consts=(object(),))
    with pytest.raises(TypeError, match="unsupported code field value"):
        code_fingerprint(altered)
