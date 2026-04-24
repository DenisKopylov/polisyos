"""Tests for WS8.5 — Replay Semantic Diff enhancements.

Covers distribution comparison (KS-test), reordered list matching,
custom comparators, causality analysis, and diff report persistence.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.scientist.replay.diff import (
    ComparatorRegistry,
    DiffToleranceConfig,
    compute_replay_diff,
    save_diff_report,
)

# ---------------------------------------------------------------------------
# Distribution comparison
# ---------------------------------------------------------------------------


class TestDistributionComparison:
    def test_distribution_ks_identical(self) -> None:
        """Identical distributions → high similarity."""
        data = list(range(20))
        original = {"values": data}
        replayed = {"values": data}
        cfg = DiffToleranceConfig(distribution_min_samples=10)
        result = compute_replay_diff(original, replayed, cfg)
        assert result.overall_similarity == 1.0
        assert result.structural_match is True

    def test_distribution_ks_different(self) -> None:
        """Very different distributions → low similarity."""
        original = {"values": [float(i) for i in range(20)]}
        replayed = {"values": [float(i * 100 + 500) for i in range(20)]}
        cfg = DiffToleranceConfig(distribution_min_samples=10)
        result = compute_replay_diff(original, replayed, cfg)
        assert result.overall_similarity < 0.5
        assert result.structural_match is False

    def test_distribution_fallback_without_scipy(self) -> None:
        """Graceful degradation when scipy is unavailable."""
        import sys

        # Temporarily hide scipy
        scipy_mods = {k: v for k, v in sys.modules.items() if k.startswith("scipy")}
        for k in scipy_mods:
            sys.modules[k] = None  # type: ignore[assignment]
        try:
            from polisyos.scientist.replay.diff import _distribution_similarity

            # Force re-import by calling directly
            sim, tol = _distribution_similarity(
                [float(i) for i in range(20)],
                [float(i) for i in range(20)],
                0.05,
            )
            assert sim >= 0.9
        finally:
            for k, v in scipy_mods.items():
                sys.modules[k] = v
            # Clean up None entries
            for k in list(sys.modules):
                if k.startswith("scipy") and sys.modules[k] is None:
                    del sys.modules[k]

    def test_distribution_min_samples_bypass(self) -> None:
        """Short lists use element-wise comparison, not distribution."""
        original = {"values": [1.0, 2.0, 3.0]}
        replayed = {"values": [1.0, 2.0, 3.5]}
        cfg = DiffToleranceConfig(distribution_min_samples=10)
        result = compute_replay_diff(original, replayed, cfg)
        # Should produce per-element diff, not distribution
        paths = [d.path for d in result.field_diffs]
        assert any("[2]" in p for p in paths)


# ---------------------------------------------------------------------------
# Reordered list matching
# ---------------------------------------------------------------------------


class TestReorderedListMatching:
    def test_list_reorder_with_key_field(self) -> None:
        """Match list elements by key field, order-independent."""
        original = {
            "items": [
                {"id": "a", "val": 1},
                {"id": "b", "val": 2},
            ]
        }
        replayed = {
            "items": [
                {"id": "b", "val": 2},
                {"id": "a", "val": 1},
            ]
        }
        cfg = DiffToleranceConfig(
            allow_list_reorder=True,
            list_match_key={"items": "id"},
        )
        result = compute_replay_diff(original, replayed, cfg)
        assert result.overall_similarity == 1.0
        assert result.structural_match is True

    def test_list_reorder_greedy_matching(self) -> None:
        """Greedy similarity-based matching without key field."""
        original = {"nums": [1, 2, 3]}
        replayed = {"nums": [3, 1, 2]}
        cfg = DiffToleranceConfig(allow_list_reorder=True)
        result = compute_replay_diff(original, replayed, cfg)
        assert result.overall_similarity == 1.0

    def test_list_reorder_disabled_by_default(self) -> None:
        """Without allow_list_reorder, order matters."""
        original = {"items": [1, 2, 3]}
        replayed = {"items": [3, 2, 1]}
        cfg = DiffToleranceConfig()
        result = compute_replay_diff(original, replayed, cfg)
        # Elements at positions 0 and 2 differ
        assert result.overall_similarity < 1.0


# ---------------------------------------------------------------------------
# Custom comparators
# ---------------------------------------------------------------------------


class TestCustomComparators:
    def test_custom_comparator_date(self) -> None:
        """ISO date comparator compares by timedelta."""
        from polisyos.scientist.replay.comparators import date_comparator

        registry = ComparatorRegistry()
        registry.register("event_date", date_comparator)

        original = {"event_date": "2026-01-01T00:00:00"}
        replayed = {"event_date": "2026-01-01T00:00:01"}
        result = compute_replay_diff(original, replayed, comparators=registry)
        assert result.overall_similarity == 1.0

    def test_custom_comparator_json_string(self) -> None:
        """JSON string comparator parses and compares structurally."""
        from polisyos.scientist.replay.comparators import json_string_comparator

        registry = ComparatorRegistry()
        registry.register("config", json_string_comparator)

        original = {"config": '{"a": 1, "b": 2}'}
        replayed = {"config": '{"a": 1, "b": 2}'}
        result = compute_replay_diff(original, replayed, comparators=registry)
        assert result.overall_similarity == 1.0

    def test_comparator_registry_pattern_lookup(self) -> None:
        """Registry matches by fnmatch patterns."""
        registry = ComparatorRegistry()
        called = []

        def spy(a: object, b: object, cfg: object) -> float:
            called.append((a, b))
            return 1.0

        registry.register("results.*.score", spy)
        # Exact match should not work
        assert registry.get("results.x.score") is not None
        # Pattern match
        assert registry.get("results.y.score") is not None
        # No match
        assert registry.get("other.path") is None


# ---------------------------------------------------------------------------
# Causality analysis
# ---------------------------------------------------------------------------


class TestCausalityAnalysis:
    def test_causality_analysis_shared_prefix(self) -> None:
        """Input diff at path X causes output diff at path X.result."""
        from polisyos.scientist.replay.causality import analyze_causality

        input_diff = compute_replay_diff(
            {"params": {"method": "a"}},
            {"params": {"method": "b"}},
        )
        output_diff = compute_replay_diff(
            {"params": {"result": 1.0}},
            {"params": {"result": 2.0}},
        )
        links = analyze_causality(input_diff, output_diff)
        assert len(links) > 0
        assert links[0].confidence > 0.0

    def test_causality_analysis_no_link(self) -> None:
        """Independent diffs produce no causal links."""
        from polisyos.scientist.replay.causality import analyze_causality

        input_diff = compute_replay_diff(
            {"alpha": {"x": 1}},
            {"alpha": {"x": 2}},
        )
        output_diff = compute_replay_diff(
            {"beta": {"y": 10}},
            {"beta": {"y": 20}},
        )
        links = analyze_causality(input_diff, output_diff)
        # No shared path segments → no links (or very low confidence)
        assert all(l.confidence < 0.3 for l in links)


# ---------------------------------------------------------------------------
# Diff report persistence
# ---------------------------------------------------------------------------


class TestDiffReportPersistence:
    def test_diff_report_save_and_load(self) -> None:
        """Persist diff report to mock store, verify JSON structure."""
        result = compute_replay_diff(
            {"a": 1, "b": "hello"},
            {"a": 2, "b": "hello"},
        )

        store = MagicMock()
        ref = MagicMock()
        store.put_json = MagicMock(return_value=ref)

        ret = save_diff_report(result, store, run_id="run-123")
        assert ret is ref
        store.put_json.assert_called_once()
        saved_data = store.put_json.call_args[0][0]
        assert "overall_similarity" in saved_data
        assert "field_diffs" in saved_data
        assert "causal_links" in saved_data
