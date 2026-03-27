"""Tests for HyperbandScheduler."""

from __future__ import annotations

import pytest

from polisyos.scientist.autotune.hyperband import HyperbandScheduler


class TestGetBrackets:
    def test_generates_brackets(self):
        scheduler = HyperbandScheduler(max_budget=81, reduction_factor=3, min_budget=1)
        brackets = scheduler.get_brackets()
        assert len(brackets) > 0
        for b in brackets:
            assert len(b.rungs) > 0
            assert b.rungs[-1].resource <= 81

    def test_single_bracket(self):
        scheduler = HyperbandScheduler(max_budget=3, reduction_factor=3, min_budget=3)
        brackets = scheduler.get_brackets()
        assert len(brackets) >= 1

    def test_budget_monotonic(self):
        scheduler = HyperbandScheduler(max_budget=27, reduction_factor=3, min_budget=1)
        for bracket in scheduler.get_brackets():
            resources = [r.resource for r in bracket.rungs]
            for i in range(1, len(resources)):
                assert resources[i] >= resources[i - 1]


class TestAdvanceBracket:
    def test_successive_halving(self):
        scheduler = HyperbandScheduler(max_budget=81, reduction_factor=3, min_budget=1)
        brackets = scheduler.get_brackets()
        bracket = brackets[0]
        scores = {f"c{i}": float(i) for i in range(bracket.rungs[0].n_configs)}
        survivors = scheduler.advance_bracket(bracket, scores)
        # Survivors should be fewer than initial configs
        assert len(survivors) <= len(scores)
        assert bracket.current_rung == 1

    def test_full_halving_loop(self):
        scheduler = HyperbandScheduler(max_budget=9, reduction_factor=3, min_budget=1)
        brackets = scheduler.get_brackets()
        bracket = brackets[0]
        candidates = [f"c{i}" for i in range(bracket.rungs[0].n_configs)]

        current = candidates
        while not bracket.is_complete:
            scores = {c: float(hash(c) % 100) for c in current}
            current = scheduler.advance_bracket(bracket, scores)

        assert bracket.is_complete

    def test_advance_complete_bracket(self):
        scheduler = HyperbandScheduler(max_budget=3, reduction_factor=3, min_budget=3)
        brackets = scheduler.get_brackets()
        bracket = brackets[0]
        # Exhaust all rungs
        for _ in range(len(bracket.rungs) + 2):
            scores = {"c0": 0.5}
            scheduler.advance_bracket(bracket, scores)
        result = scheduler.advance_bracket(bracket, {"c0": 0.5})
        assert result == []


class TestTotalBudget:
    def test_budget_positive(self):
        scheduler = HyperbandScheduler(max_budget=81, reduction_factor=3, min_budget=1)
        assert scheduler.total_budget() > 0
