"""Tests for namespace utilities — WS3 multi-tenancy isolation."""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")

from polisyos.core.security.namespace import (
    namespaced_artifact_id,
    namespaced_lock_key,
    namespaced_run_id,
    strip_namespace,
)


class TestNamespacedArtifactId:
    def test_namespaced_artifact_id_with_cell(self) -> None:
        result = namespaced_artifact_id("t1", "c1", "base")
        assert result == "t1:c1:base"

    def test_namespaced_artifact_id_without_cell(self) -> None:
        result = namespaced_artifact_id("t1", None, "base")
        assert result == "t1:base"


class TestNamespacedRunId:
    def test_namespaced_run_id(self) -> None:
        assert namespaced_run_id("t1", "c1", "run-1") == "t1:c1:run-1"
        assert namespaced_run_id("t1", None, "run-1") == "t1:run-1"


class TestNamespacedLockKey:
    def test_namespaced_lock_key(self) -> None:
        assert namespaced_lock_key("t1", "c1", "lock-x") == "t1:c1:lock-x"
        assert namespaced_lock_key("t1", None, "lock-x") == "t1:lock-x"


class TestStripNamespace:
    def test_strip_namespace_3parts(self) -> None:
        tenant, cell, base = strip_namespace("t1:c1:base")
        assert tenant == "t1"
        assert cell == "c1"
        assert base == "base"

    def test_strip_namespace_2parts(self) -> None:
        tenant, cell, base = strip_namespace("t1:base")
        assert tenant == "t1"
        assert cell is None
        assert base == "base"

    def test_strip_namespace_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid namespaced ID"):
            strip_namespace("no_separator")
