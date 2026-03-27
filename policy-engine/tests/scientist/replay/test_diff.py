"""Tests for replay diff — WS4 provenance replay verification."""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")

from polisyos.scientist.replay.diff import DiffToleranceConfig, compute_replay_diff


class TestIdenticalDicts:
    def test_identical_dicts(self) -> None:
        a = {"x": 1.0, "y": "hello", "nested": {"z": 42}}
        result = compute_replay_diff(a, a)
        assert result.overall_similarity == 1.0
        assert len(result.field_diffs) == 0


class TestNumericTolerance:
    def test_numeric_within_tolerance(self) -> None:
        a = {"val": 1.0}
        b = {"val": 1.0 + 1e-9}
        config = DiffToleranceConfig(numeric_rtol=1e-5, numeric_atol=1e-8)
        result = compute_replay_diff(a, b, config=config)
        # Difference is negligible — all tolerances met
        if result.field_diffs:
            assert all(d.tolerance_met for d in result.field_diffs)

    def test_numeric_beyond_tolerance(self) -> None:
        a = {"val": 1.0}
        b = {"val": 2.0}
        config = DiffToleranceConfig(numeric_rtol=1e-5, numeric_atol=1e-8)
        result = compute_replay_diff(a, b, config=config)
        assert len(result.field_diffs) > 0
        assert not result.field_diffs[0].tolerance_met


class TestStringSimilarity:
    def test_string_similarity(self) -> None:
        a = {"text": "hello world"}
        b = {"text": "hello worlt"}
        result = compute_replay_diff(a, b)
        assert len(result.field_diffs) == 1
        diff = result.field_diffs[0]
        assert 0.0 < diff.similarity < 1.0


class TestNestedDictDiff:
    def test_nested_dict_diff(self) -> None:
        a = {"outer": {"inner": 1.0}}
        b = {"outer": {"inner": 2.0}}
        result = compute_replay_diff(a, b)
        assert len(result.field_diffs) > 0
        paths = [d.path for d in result.field_diffs]
        assert any("inner" in p for p in paths)


class TestListDiff:
    def test_list_diff(self) -> None:
        a = {"items": [1, 2, 3]}
        b = {"items": [1, 2]}
        result = compute_replay_diff(a, b)
        assert len(result.field_diffs) > 0
        # The missing element should produce a diff
        assert any(d.similarity == 0.0 for d in result.field_diffs)


class TestTypeMismatch:
    def test_type_mismatch(self) -> None:
        a = {"val": 42}
        b = {"val": "forty-two"}
        result = compute_replay_diff(a, b)
        assert len(result.field_diffs) > 0
        assert result.field_diffs[0].similarity == 0.0
        assert not result.field_diffs[0].tolerance_met


class TestIgnoreTimestamps:
    def test_ignore_timestamps(self) -> None:
        a = {"created_at": "2026-01-01T00:00:00", "value": 1.0}
        b = {"created_at": "2026-03-22T12:00:00", "value": 1.0}
        config = DiffToleranceConfig(ignore_timestamps=True)
        result = compute_replay_diff(a, b, config=config)
        # Timestamp field should be ignored — no diffs
        assert result.overall_similarity == 1.0
        assert len(result.field_diffs) == 0
