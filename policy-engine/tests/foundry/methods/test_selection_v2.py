"""Tests for Phase 5 — Evidence-Conditioned Method Selection."""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path

import pytest

from polisyos.core.contracts.execution_plan import MethodCatalogEntry
from polisyos.foundry.methods.selection import (
    COST_PER_MS,
    DataCharacteristics,
    MethodSelectionCriteria,
    _score_entry,
    _score_entry_v2,
    compute_voi,
    rank_method_catalog_entries,
)
from polisyos.foundry.methods.selection_history import (
    MethodExecutionRecord,
    RuntimePredictor,
    SelectionHistoryStore,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(fqn: str = "test.method@1.0.0", **overrides) -> MethodCatalogEntry:
    """Build a MethodCatalogEntry with sensible defaults."""
    defaults = dict(
        fqn=fqn,
        namespace="test",
        name="method",
        version="1.0.0",
        backend="numpy",
        execution_backend="numpy",
        kind="pure",
        family="test",
        variant="default",
        fidelity_tier="medium",
        determinism_tier="library_deterministic",
        data_modalities=["tabular"],
        runtime_stack=[],
        required_deps=[],
        optional_deps=[],
        fallback_policy="skip",
        side_effect_profile="none",
        runnable=True,
        disabled_reasons=[],
        dependency_posture={},
        capability_matrix={},
        input_slots=[],
        output_slots=[],
        parameters=[],
        requires=[],
        conflicts_with=[],
        incompatibilities=[],
        deprecations=[],
        tags=[],
        causal_capability_requirements=[],
    )
    defaults.update(overrides)
    return MethodCatalogEntry(**defaults)


def _make_record(
    fqn: str = "test.method@1.0.0",
    *,
    success: bool = True,
    latency_ms: float = 100.0,
    output_quality: float | None = None,
    data_characteristics: dict | None = None,
    timestamp: float | None = None,
) -> MethodExecutionRecord:
    return MethodExecutionRecord(
        method_fqn=fqn,
        timestamp=timestamp if timestamp is not None else time.time(),
        latency_ms=latency_ms,
        success=success,
        output_quality=output_quality,
        data_characteristics=data_characteristics or {},
    )


def _make_envelope(
    point: float = 5.0,
    ci: tuple[float, float] = (2.0, 8.0),
) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=ci,
        confidence_level=0.95,
        source=UncertaintySource.CALIBRATION,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
    )


# ---------------------------------------------------------------------------
# Core tests from SOTA plan
# ---------------------------------------------------------------------------


class TestEvidenceScorer:
    def test_evidence_scorer_prefers_high_success_rate(self):
        """Method with 90% success rate should score higher than 50% success rate."""
        entry_a = _make_entry(fqn="test.a@1.0.0", name="a")
        entry_b = _make_entry(fqn="test.b@1.0.0", name="b")
        criteria = MethodSelectionCriteria()

        history = SelectionHistoryStore()
        now = time.time()
        for i in range(10):
            history.record(_make_record("test.a@1.0.0", success=(i < 9), timestamp=now))
            history.record(_make_record("test.b@1.0.0", success=(i < 5), timestamp=now))

        score_a = _score_entry_v2(entry_a, criteria, history=history)
        score_b = _score_entry_v2(entry_b, criteria, history=history)
        assert score_a > score_b

    def test_evidence_scorer_penalizes_budget_violation(self):
        """Method predicted to exceed budget gets a -50 penalty."""
        entry = _make_entry()
        criteria = MethodSelectionCriteria()

        predictor = RuntimePredictor()
        # Default predictor at n_obs=1000: exp(2.0 + 0.7*ln(1000)) ≈ exp(6.83) ≈ 924ms
        budget = 10.0  # 10ms budget — will be violated

        score_with_budget = _score_entry_v2(
            entry, criteria, runtime_predictor=predictor, runtime_budget_ms=budget
        )
        score_without = _score_entry_v2(entry, criteria)
        assert score_with_budget < score_without
        assert score_with_budget == pytest.approx(score_without - 50.0)

    def test_evidence_scorer_rewards_within_budget(self):
        """Method well within budget gets a positive bonus."""
        entry = _make_entry()
        criteria = MethodSelectionCriteria()

        predictor = RuntimePredictor()
        budget = 100_000.0  # very generous budget

        score_with = _score_entry_v2(
            entry, criteria, runtime_predictor=predictor, runtime_budget_ms=budget
        )
        score_without = _score_entry_v2(entry, criteria)
        assert score_with > score_without

    def test_backward_compat_without_history(self):
        """_score_entry_v2 with no history/predictor equals _score_entry."""
        entry = _make_entry()
        criteria = MethodSelectionCriteria(preferred_kind="pure", preferred_family="test")

        v1 = _score_entry(entry, criteria)
        v2 = _score_entry_v2(entry, criteria)
        assert v1 == v2


class TestRankMethodCatalogEntriesBackwardCompat:
    def test_same_ordering_without_evidence(self):
        """rank_method_catalog_entries returns identical order with and without evidence args."""
        entries = [
            _make_entry(fqn="a.x@1.0.0", name="x", family="a", kind="pure"),
            _make_entry(fqn="b.y@1.0.0", name="y", family="b", kind="simulation"),
            _make_entry(fqn="a.z@1.0.0", name="z", family="a", kind="pure"),
        ]
        criteria = MethodSelectionCriteria(preferred_kind="pure", preferred_family="a")

        ranked_default = rank_method_catalog_entries(entries, criteria)
        ranked_explicit_none = rank_method_catalog_entries(
            entries, criteria, history=None, runtime_predictor=None, runtime_budget_ms=None
        )
        assert [e.fqn for e in ranked_default] == [e.fqn for e in ranked_explicit_none]


class TestRuntimePredictor:
    def test_runtime_predictor_linear_scaling(self):
        """Larger n_obs → higher predicted latency, following log-linear model."""
        predictor = RuntimePredictor()

        # Fit with synthetic data
        history = SelectionHistoryStore()
        now = time.time()
        for n in [100, 500, 1000, 5000, 10000]:
            latency = 0.5 * n**0.7  # known relationship
            history.record(_make_record(
                "test.m@1.0.0",
                latency_ms=latency,
                data_characteristics={"n_obs": n, "n_features": 1},
                timestamp=now,
            ))

        predictor.fit(history)
        assert predictor.is_fitted

        p_small = predictor.predict_ms("test.m@1.0.0", n_obs=1000)
        p_large = predictor.predict_ms("test.m@1.0.0", n_obs=10000)
        assert p_large > p_small
        # Ratio should be roughly 10^slope_obs
        ratio = p_large / p_small
        assert ratio > 1.5  # at least meaningfully larger

    def test_runtime_predictor_cold_start(self):
        """Unfitted predictor returns a positive finite value."""
        predictor = RuntimePredictor()
        assert not predictor.is_fitted
        result = predictor.predict_ms("any.method@1.0.0", n_obs=1000)
        assert result > 0
        assert math.isfinite(result)

    def test_runtime_predictor_insufficient_data(self):
        """Fewer than 5 records → predictor stays unfitted."""
        predictor = RuntimePredictor()
        history = SelectionHistoryStore()
        now = time.time()
        for n in [100, 200, 300]:
            history.record(_make_record(
                "test.m@1.0.0",
                latency_ms=float(n),
                data_characteristics={"n_obs": n},
                timestamp=now,
            ))
        predictor.fit(history)
        assert not predictor.is_fitted

    def test_runtime_predictor_uses_method_residuals(self):
        """Methods with enough history get method-specific intercept adjustments."""
        predictor = RuntimePredictor()
        history = SelectionHistoryStore()
        now = time.time()
        for n in [100, 500, 1000, 5000, 10000]:
            history.record(_make_record(
                "fast@1.0.0",
                latency_ms=0.1 * n**0.6,
                data_characteristics={"n_obs": n, "n_features": 2},
                timestamp=now,
            ))
            history.record(_make_record(
                "slow@1.0.0",
                latency_ms=1.0 * n**0.6,
                data_characteristics={"n_obs": n, "n_features": 2},
                timestamp=now,
            ))
        predictor.fit(history)
        assert predictor.is_fitted
        assert predictor.predict_ms("slow@1.0.0", 1000, 2) > predictor.predict_ms("fast@1.0.0", 1000, 2)


class TestVOI:
    def test_voi_positive_for_high_stakes(self):
        """Wide CI + high decision value + low cost → positive VOI."""
        envelope = _make_envelope(point=5.0, ci=(0.0, 10.0))  # ci_width = 10
        voi = compute_voi(
            current_uncertainty=envelope,
            method_expected_reduction=5.0,
            method_cost_ms=100.0,
            decision_value=1000.0,
        )
        assert voi > 0

    def test_voi_negative_for_low_stakes_expensive_method(self):
        """Low decision value + high cost → negative VOI."""
        envelope = _make_envelope(point=5.0, ci=(4.0, 6.0))  # ci_width = 2
        voi = compute_voi(
            current_uncertainty=envelope,
            method_expected_reduction=0.5,
            method_cost_ms=100_000.0,
            decision_value=1.0,
        )
        assert voi < 0

    def test_voi_zero_ci_width(self):
        """Zero CI width → VOI is negative (pure cost)."""
        envelope = _make_envelope(point=5.0, ci=(5.0, 5.0))
        voi = compute_voi(
            current_uncertainty=envelope,
            method_expected_reduction=1.0,
            method_cost_ms=100.0,
            decision_value=1000.0,
        )
        assert voi == pytest.approx(-100.0 * COST_PER_MS)


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


class TestSelectionHistoryStore:
    def test_thread_safety(self):
        """Concurrent record() calls from multiple threads don't corrupt data."""
        store = SelectionHistoryStore()
        n_threads = 8
        records_per_thread = 100

        def _writer(thread_id: int) -> None:
            for i in range(records_per_thread):
                store.record(_make_record(
                    f"thread.{thread_id}@1.0.0",
                    latency_ms=float(i),
                    timestamp=time.time(),
                ))

        threads = [threading.Thread(target=_writer, args=(tid,)) for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(store) == n_threads * records_per_thread

    def test_quality_quantiles_insufficient_data(self):
        """Fewer than 3 records with quality → None."""
        store = SelectionHistoryStore()
        store.record(_make_record("m@1.0.0", output_quality=0.5))
        store.record(_make_record("m@1.0.0", output_quality=0.7))
        assert store.quality_quantiles("m@1.0.0") is None

    def test_quality_quantiles_sufficient_data(self):
        """With 5 quality records, returns valid (p25, p50, p75) tuple."""
        store = SelectionHistoryStore()
        for q in [0.1, 0.3, 0.5, 0.7, 0.9]:
            store.record(_make_record("m@1.0.0", output_quality=q))
        result = store.quality_quantiles("m@1.0.0")
        assert result is not None
        p25, p50, p75 = result
        assert p25 < p50 < p75
        assert p50 == pytest.approx(0.5)

    def test_success_rate_window_filtering(self):
        """Records outside the time window are excluded."""
        store = SelectionHistoryStore()
        now = time.time()
        old = now - 200 * 3600  # 200 hours ago (outside 168h window)

        # Old records: all failures
        for _ in range(5):
            store.record(_make_record("m@1.0.0", success=False, timestamp=old))
        # Recent records: all successes
        for _ in range(5):
            store.record(_make_record("m@1.0.0", success=True, timestamp=now))

        sr = store.success_rate("m@1.0.0", window_hours=168)
        assert sr == 1.0  # only recent successes counted

    def test_success_rate_no_records(self):
        """No records → None."""
        store = SelectionHistoryStore()
        assert store.success_rate("nonexistent@1.0.0") is None

    def test_mean_latency(self):
        store = SelectionHistoryStore()
        store.record(_make_record("m@1.0.0", latency_ms=100.0))
        store.record(_make_record("m@1.0.0", latency_ms=200.0))
        assert store.mean_latency_ms("m@1.0.0") == pytest.approx(150.0)
        assert store.mean_latency_ms("other@1.0.0") is None

    def test_jsonl_roundtrip(self, tmp_path):
        store = SelectionHistoryStore(persist_path=tmp_path / "history.jsonl")
        store.record(_make_record("m@1.0.0", latency_ms=100.0, success=True))
        store.record(_make_record("m@1.0.0", latency_ms=200.0, success=False))
        exported = store.export_jsonl()

        restored = SelectionHistoryStore(persist_path=exported)
        imported = restored.import_jsonl()
        assert imported == 2
        assert len(restored) == 2
        assert restored.mean_latency_ms("m@1.0.0") == pytest.approx(150.0)

    def test_auto_persist_append_valid_under_concurrent_writers(self, tmp_path):
        path = tmp_path / "history.jsonl"
        store = SelectionHistoryStore(persist_path=path, auto_persist=True)
        n_threads = 6
        records_per_thread = 40

        def _writer(thread_id: int) -> None:
            for i in range(records_per_thread):
                store.record(_make_record(
                    f"thread.{thread_id}@1.0.0",
                    latency_ms=float(i),
                    timestamp=time.time(),
                ))

        threads = [threading.Thread(target=_writer, args=(idx,)) for idx in range(n_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10.0)

        restored = SelectionHistoryStore(persist_path=path)
        assert restored.import_jsonl() == n_threads * records_per_thread
        assert len(restored) == n_threads * records_per_thread

    def test_persistence_issues_are_bounded(self, tmp_path, monkeypatch):
        path = tmp_path / "history.jsonl"
        store = SelectionHistoryStore(persist_path=path, auto_persist=True)

        def _failing_open(self, *args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "open", _failing_open)

        for i in range(100):
            store.record(_make_record("m@1.0.0", latency_ms=float(i)))

        issues = store.persistence_issues()
        assert len(issues) == store._MAX_PERSISTENCE_ISSUES
        assert all(issue.operation == "append" for issue in issues)
