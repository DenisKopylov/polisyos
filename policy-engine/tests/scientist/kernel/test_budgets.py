"""Tests for polisyos.scientist.kernel.budgets — Pydantic budget models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.scientist.kernel.budgets import (
    ComplexityBudget,
    ComputeBudget,
    EvidenceBudget,
    LegitimacyBudget,
)


# ---------------------------------------------------------------------------
# ComputeBudget
# ---------------------------------------------------------------------------

class TestComputeBudget:
    def test_defaults(self):
        b = ComputeBudget()
        assert b.max_llm_calls == 3.0
        assert b.max_sim_runs == 1.0
        assert b.max_wall_time_s == 120.0

    def test_custom_values(self):
        b = ComputeBudget(max_llm_calls=10.0, max_sim_runs=5.0, max_wall_time_s=600.0)
        assert b.max_llm_calls == 10.0
        assert b.max_sim_runs == 5.0
        assert b.max_wall_time_s == 600.0

    def test_zero_values_valid(self):
        b = ComputeBudget(max_llm_calls=0, max_sim_runs=0, max_wall_time_s=0)
        assert b.max_llm_calls == 0
        assert b.max_sim_runs == 0
        assert b.max_wall_time_s == 0

    def test_negative_llm_calls_rejected(self):
        with pytest.raises(ValidationError):
            ComputeBudget(max_llm_calls=-1)

    def test_negative_sim_runs_rejected(self):
        with pytest.raises(ValidationError):
            ComputeBudget(max_sim_runs=-0.1)

    def test_negative_wall_time_rejected(self):
        with pytest.raises(ValidationError):
            ComputeBudget(max_wall_time_s=-1)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ComputeBudget(unknown_field=42)

    def test_roundtrip(self):
        b = ComputeBudget(max_llm_calls=7.5, max_sim_runs=3.0, max_wall_time_s=300.0)
        data = b.model_dump()
        b2 = ComputeBudget(**data)
        assert b == b2


# ---------------------------------------------------------------------------
# EvidenceBudget
# ---------------------------------------------------------------------------

class TestEvidenceBudget:
    def test_defaults(self):
        b = EvidenceBudget()
        assert b.max_queries == 10

    def test_zero_valid(self):
        b = EvidenceBudget(max_queries=0)
        assert b.max_queries == 0

    def test_negative_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceBudget(max_queries=-1)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceBudget(extra=True)

    def test_roundtrip(self):
        b = EvidenceBudget(max_queries=50)
        assert EvidenceBudget(**b.model_dump()) == b


# ---------------------------------------------------------------------------
# LegitimacyBudget
# ---------------------------------------------------------------------------

class TestLegitimacyBudget:
    def test_defaults(self):
        b = LegitimacyBudget()
        assert b.require_human_gate is False
        assert b.notes == []

    def test_custom_values(self):
        b = LegitimacyBudget(require_human_gate=True, notes=["note1", "note2"])
        assert b.require_human_gate is True
        assert b.notes == ["note1", "note2"]

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            LegitimacyBudget(extra_field="x")

    def test_roundtrip(self):
        b = LegitimacyBudget(require_human_gate=True, notes=["a", "b"])
        assert LegitimacyBudget(**b.model_dump()) == b


# ---------------------------------------------------------------------------
# ComplexityBudget
# ---------------------------------------------------------------------------

class TestComplexityBudget:
    def test_defaults(self):
        b = ComplexityBudget()
        assert b.max_interventions == 10
        assert b.max_scenarios == 10

    def test_zero_valid(self):
        b = ComplexityBudget(max_interventions=0, max_scenarios=0)
        assert b.max_interventions == 0
        assert b.max_scenarios == 0

    def test_negative_interventions_rejected(self):
        with pytest.raises(ValidationError):
            ComplexityBudget(max_interventions=-1)

    def test_negative_scenarios_rejected(self):
        with pytest.raises(ValidationError):
            ComplexityBudget(max_scenarios=-1)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ComplexityBudget(unknown=1)

    def test_roundtrip(self):
        b = ComplexityBudget(max_interventions=5, max_scenarios=20)
        assert ComplexityBudget(**b.model_dump()) == b
