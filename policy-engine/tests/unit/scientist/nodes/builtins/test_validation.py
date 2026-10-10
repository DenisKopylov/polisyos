"""Tests for NodeParamValidator."""

from __future__ import annotations

import pytest

from polisyos.scientist.nodes.builtins.validation import (
    NodeParamError,
    NodeParamValidator,
)


class TestRequireStr:
    def test_happy(self):
        assert NodeParamValidator.require_str({"key": "hello"}, "key") == "hello"

    def test_missing_raises(self):
        with pytest.raises(NodeParamError, match="missing"):
            NodeParamValidator.require_str({}, "key")

    def test_empty_raises(self):
        with pytest.raises(NodeParamError, match="too short"):
            NodeParamValidator.require_str({"key": ""}, "key")

    def test_min_length(self):
        with pytest.raises(NodeParamError, match="too short"):
            NodeParamValidator.require_str({"key": "ab"}, "key", min_length=5)

    def test_strips_whitespace(self):
        assert NodeParamValidator.require_str({"key": "  hi  "}, "key") == "hi"


class TestRequireInt:
    def test_happy(self):
        assert NodeParamValidator.require_int({"n": 5}, "n") == 5

    def test_missing_raises(self):
        with pytest.raises(NodeParamError, match="missing"):
            NodeParamValidator.require_int({}, "n")

    def test_string_int(self):
        assert NodeParamValidator.require_int({"n": "42"}, "n") == 42

    def test_ge_violation(self):
        with pytest.raises(NodeParamError, match=">="):
            NodeParamValidator.require_int({"n": 3}, "n", ge=5)


class TestRequireFloat:
    def test_happy(self):
        assert NodeParamValidator.require_float({"x": 3.14}, "x") == pytest.approx(3.14)

    def test_missing_raises(self):
        with pytest.raises(NodeParamError, match="missing"):
            NodeParamValidator.require_float({}, "x")

    def test_le_violation(self):
        with pytest.raises(NodeParamError, match="<="):
            NodeParamValidator.require_float({"x": 10.0}, "x", le=5.0)


class TestOptionals:
    def test_optional_str_default(self):
        assert NodeParamValidator.optional_str({}, "key", "default") == "default"

    def test_optional_str_present(self):
        assert NodeParamValidator.optional_str({"key": "val"}, "key") == "val"

    def test_optional_float_default(self):
        assert NodeParamValidator.optional_float({}, "x", 1.0) == 1.0

    def test_optional_int_default(self):
        assert NodeParamValidator.optional_int({}, "n", 99) == 99


class TestRequireList:
    def test_happy(self):
        assert NodeParamValidator.require_list({"items": [1, 2]}, "items") == [1, 2]

    def test_missing_raises(self):
        with pytest.raises(NodeParamError, match="missing"):
            NodeParamValidator.require_list({}, "items")

    def test_min_length(self):
        with pytest.raises(NodeParamError, match="at least"):
            NodeParamValidator.require_list({"items": []}, "items", min_length=1)


class TestToNodeError:
    def test_converts(self):
        err = NodeParamError("node.validation_error", "bad param")
        node_error = NodeParamValidator.to_node_error(err)
        assert node_error.code == "node.validation_error"
        assert "bad param" in node_error.message
