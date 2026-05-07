"""Tests for polisyos.scientist.orchestration.engine.topo — tiered topological sort."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from polisyos.scientist.orchestration.engine.errors import CycleDetectedError
from polisyos.scientist.orchestration.engine.topo import topo_sort_tiers, validate_tier_write_safety
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation


def _inv(alias: str, depends_on: list[str] | None = None) -> NodeInvocation:
    return NodeInvocation(
        alias=alias,
        node_id=f"test.{alias}@1.0.0",
        depends_on=depends_on or [],
    )


# ---------------------------------------------------------------------------
# topo_sort_tiers
# ---------------------------------------------------------------------------


class TestTopoSortTiers:
    def test_linear_dag(self):
        """A→B→C → each tier has 1 node."""
        invocations = {
            "a": _inv("a"),
            "b": _inv("b", ["a"]),
            "c": _inv("c", ["b"]),
        }
        tiers = topo_sort_tiers(invocations)
        assert tiers == [["a"], ["b"], ["c"]]

    def test_diamond_dag(self):
        """A→B, A→C, B→D, C→D → tiers: [A], [B,C], [D]."""
        invocations = {
            "a": _inv("a"),
            "b": _inv("b", ["a"]),
            "c": _inv("c", ["a"]),
            "d": _inv("d", ["b", "c"]),
        }
        tiers = topo_sort_tiers(invocations)
        assert tiers == [["a"], ["b", "c"], ["d"]]

    def test_wide_fan_out(self):
        """A→B,C,D,E → tiers: [A], [B,C,D,E]."""
        invocations = {
            "a": _inv("a"),
            "b": _inv("b", ["a"]),
            "c": _inv("c", ["a"]),
            "d": _inv("d", ["a"]),
            "e": _inv("e", ["a"]),
        }
        tiers = topo_sort_tiers(invocations)
        assert tiers == [["a"], ["b", "c", "d", "e"]]

    def test_single_node(self):
        invocations = {"a": _inv("a")}
        tiers = topo_sort_tiers(invocations)
        assert tiers == [["a"]]

    def test_independent_nodes(self):
        """All independent → single tier with all nodes."""
        invocations = {
            "a": _inv("a"),
            "b": _inv("b"),
            "c": _inv("c"),
        }
        tiers = topo_sort_tiers(invocations)
        assert tiers == [["a", "b", "c"]]

    def test_cycle_detection(self):
        invocations = {
            "a": _inv("a", ["b"]),
            "b": _inv("b", ["a"]),
        }
        with pytest.raises(CycleDetectedError):
            topo_sort_tiers(invocations)

    def test_empty_dag(self):
        tiers = topo_sort_tiers({})
        assert tiers == []

    def test_complex_dag(self):
        """
        A → B → D → F
        A → C → E → F
        B → E
        """
        invocations = {
            "a": _inv("a"),
            "b": _inv("b", ["a"]),
            "c": _inv("c", ["a"]),
            "d": _inv("d", ["b"]),
            "e": _inv("e", ["b", "c"]),
            "f": _inv("f", ["d", "e"]),
        }
        tiers = topo_sort_tiers(invocations)
        assert tiers[0] == ["a"]
        assert set(tiers[1]) == {"b", "c"}
        assert set(tiers[2]) == {"d", "e"}
        assert tiers[3] == ["f"]

    def test_flatten_matches_original_topo_sort(self):
        """Flattened tiers should produce a valid topological order."""
        from polisyos.scientist.orchestration.engine.executor import _topo_sort

        invocations = {
            "a": _inv("a"),
            "b": _inv("b", ["a"]),
            "c": _inv("c", ["a"]),
            "d": _inv("d", ["b", "c"]),
        }

        flat_tiers = [alias for tier in topo_sort_tiers(invocations) for alias in tier]
        flat_original = _topo_sort(invocations)

        # Both should produce the same set of nodes
        assert set(flat_tiers) == set(flat_original)

        # Both should respect dependencies
        for alias, inv in invocations.items():
            for dep in inv.depends_on:
                assert flat_tiers.index(dep) < flat_tiers.index(alias)
                assert flat_original.index(dep) < flat_original.index(alias)


# ---------------------------------------------------------------------------
# validate_tier_write_safety
# ---------------------------------------------------------------------------


class TestValidateTierWriteSafety:
    def _make_registry(self, writes_map: dict[str, list[str]]):
        registry = MagicMock()

        def _get(node_id):
            alias = str(node_id).split("@")[0].split(".")[-1]
            node = MagicMock()
            node.spec.state_writes = writes_map.get(alias, [])
            return node

        registry.get.side_effect = _get
        return registry

    def test_single_node_always_safe(self):
        invocations = {"a": _inv("a")}
        registry = self._make_registry({"a": ["params"]})
        safe, conflicts = validate_tier_write_safety(["a"], registry, invocations)
        assert safe is True
        assert conflicts == []

    def test_disjoint_writes(self):
        invocations = {"a": _inv("a"), "b": _inv("b")}
        registry = self._make_registry(
            {
                "a": ["params"],
                "b": ["artifacts_index"],
            }
        )
        safe, conflicts = validate_tier_write_safety(["a", "b"], registry, invocations)
        assert safe is True
        assert conflicts == []

    def test_overlapping_writes(self):
        invocations = {"a": _inv("a"), "b": _inv("b")}
        registry = self._make_registry(
            {
                "a": ["params", "reports_index"],
                "b": ["params"],
            }
        )
        safe, conflicts = validate_tier_write_safety(["a", "b"], registry, invocations)
        assert safe is False
        assert len(conflicts) == 1
        assert "params" in conflicts[0]

    def test_empty_tier(self):
        safe, conflicts = validate_tier_write_safety([], MagicMock(), {})
        assert safe is True
        assert conflicts == []
