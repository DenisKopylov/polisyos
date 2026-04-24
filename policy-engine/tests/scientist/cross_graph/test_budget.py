"""Tests for compilation budget management."""

from __future__ import annotations

import time

from polisyos.scientist.cross_graph.budget import CompilationBudget


class TestCompilationBudget:
    def test_needs_tracking(self):
        budget = CompilationBudget(max_needs=5)
        budget.start()
        for _ in range(5):
            budget.record_need()
        assert budget.is_needs_exhausted() is True
        assert budget.remaining_needs() == 0

    def test_not_exhausted(self):
        budget = CompilationBudget(max_needs=10)
        budget.start()
        budget.record_need()
        assert budget.is_needs_exhausted() is False
        assert budget.remaining_needs() == 9

    def test_query_tracking(self):
        budget = CompilationBudget(max_queries_per_dimension=3)
        budget.start()
        budget.record_query("legal")
        budget.record_query("legal")
        budget.record_query("legal")
        assert budget.is_dimension_exhausted("legal") is True
        assert budget.is_dimension_exhausted("academic") is False

    def test_time_exhaustion(self):
        budget = CompilationBudget(max_wall_time_s=0.01)
        budget.start()
        time.sleep(0.02)
        assert budget.is_time_exhausted() is True

    def test_summary(self):
        budget = CompilationBudget(max_needs=10)
        budget.start()
        budget.record_need()
        budget.record_query("academic")
        s = budget.summary()
        assert s["needs_processed"] == 1
        assert s["queries_by_dimension"]["academic"] == 1
        assert s["exhausted"] is False

    def test_any_exhausted(self):
        budget = CompilationBudget(max_needs=1)
        budget.start()
        assert budget.is_any_exhausted() is False
        budget.record_need()
        assert budget.is_any_exhausted() is True
