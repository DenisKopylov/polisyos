"""Tests for Level 0 Static Validator (A.2)."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.search.funnel.level0_static import Level0StaticValidator


def _make_candidate(**overrides):
    """Build a minimal valid candidate dict."""
    base = {
        "semantic": {
            "interventions": [
                {
                    "type": "tax_reform",
                    "parameters": {"income_tax_rate": 0.25},
                },
            ],
            "objectives": [
                {"name": "gdp_growth", "variable": "gdp"},
            ],
        },
    }
    base.update(overrides)
    return base


class TestLevel0StaticValidator:
    def setup_method(self):
        self.stage = Level0StaticValidator()

    def test_stage_metadata(self):
        assert self.stage.stage_name == "funnel_L0_static"
        assert self.stage.fidelity_level == 0
        assert self.stage.estimated_cost_usd == 0.0

    # --- Structure checks ---

    def test_valid_candidate_passes(self):
        result = self.stage.evaluate(_make_candidate(), {})
        assert result.is_promising is True
        assert not result.has_blockers

    def test_missing_semantic_is_blocker(self):
        result = self.stage.evaluate({}, {})
        assert result.is_promising is False
        assert any(fc.failure_type == "missing_semantic" for fc in result.failure_cards)

    def test_no_interventions_is_blocker(self):
        candidate = _make_candidate(
            semantic={"interventions": [], "objectives": [{"name": "gdp"}]},
        )
        result = self.stage.evaluate(candidate, {})
        assert result.is_promising is False
        assert any(fc.failure_type == "no_interventions" for fc in result.failure_cards)

    def test_no_objectives_is_warning(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [{"type": "tax", "parameters": {}}],
                "objectives": [],
            },
        )
        result = self.stage.evaluate(candidate, {})
        warnings = [fc for fc in result.failure_cards if fc.severity == "warning"]
        assert any(fc.failure_type == "no_objectives" for fc in warnings)

    # --- Parameter domain checks ---

    def test_nan_parameter_is_blocker(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [
                    {"type": "subsidy", "parameters": {"rate": float("nan")}},
                ],
                "objectives": [{"name": "gdp"}],
            },
        )
        result = self.stage.evaluate(candidate, {})
        assert result.is_promising is False
        blockers = [fc for fc in result.failure_cards if fc.is_blocker]
        assert any("NaN" in fc.description for fc in blockers)

    def test_inf_parameter_is_blocker(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [
                    {"type": "subsidy", "parameters": {"rate": float("inf")}},
                ],
                "objectives": [{"name": "gdp"}],
            },
        )
        result = self.stage.evaluate(candidate, {})
        assert result.is_promising is False

    def test_rate_out_of_bounds_is_warning(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [
                    {"type": "tax", "parameters": {"tax_rate": 1.5}},
                ],
                "objectives": [{"name": "gdp"}],
            },
        )
        result = self.stage.evaluate(candidate, {})
        warnings = [fc for fc in result.failure_cards if fc.severity == "warning"]
        assert any("tax_rate" in fc.description for fc in warnings)

    def test_extreme_value_is_warning(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [
                    {"type": "subsidy", "parameters": {"amount": 2e6}},
                ],
                "objectives": [{"name": "gdp"}],
            },
        )
        result = self.stage.evaluate(candidate, {})
        warnings = [fc for fc in result.failure_cards if fc.severity == "warning"]
        assert any("extreme" in fc.description.lower() for fc in warnings)

    # --- Forbidden combinations ---

    def test_forbidden_combination_is_blocker(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [
                    {"type": "carbon_tax", "parameters": {}},
                    {"type": "fossil_subsidy", "parameters": {}},
                ],
                "objectives": [{"name": "gdp"}],
            },
        )
        result = self.stage.evaluate(candidate, {})
        assert result.is_promising is False
        assert any(fc.failure_type == "forbidden_combination" for fc in result.failure_cards)

    # --- Legal red flags ---

    def test_legal_red_flag(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [
                    {"type": "forced_relocation", "parameters": {}},
                ],
                "objectives": [{"name": "gdp"}],
            },
        )
        result = self.stage.evaluate(candidate, {})
        assert any(fc.failure_type == "legal_red_flag" for fc in result.failure_cards)

    # --- Fiscal sanity ---

    def test_fiscal_sanity_blocker(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [{"type": "spending", "parameters": {}}],
                "objectives": [{"name": "gdp"}],
                "constraints": {"fiscal_budget": 300, "gdp_reference": 100},
            },
        )
        result = self.stage.evaluate(candidate, {})
        assert any(fc.failure_type == "fiscal_sanity" for fc in result.failure_cards)

    # --- Mechanism completeness ---

    def test_interventions_without_objectives_is_blocker(self):
        candidate = _make_candidate(
            semantic={
                "interventions": [{"type": "tax", "parameters": {}}],
                "objectives": [],
            },
        )
        result = self.stage.evaluate(candidate, {})
        assert any(fc.failure_type == "mechanism_incomplete" for fc in result.failure_cards)

    # --- Performance ---

    def test_evaluation_is_fast(self):
        """Level 0 must complete in < 10ms (generous bound for CI)."""
        result = self.stage.evaluate(_make_candidate(), {})
        assert result.duration_seconds < 0.01

    # --- Uncertainty envelope ---

    def test_unassessed_uncertainty_envelope(self):
        result = self.stage.evaluate(_make_candidate(), {})
        for est in result.uncertainty_envelope.uncertainties.values():
            assert est.level == 1.0
            assert "not assessed at this fidelity" in est.source
