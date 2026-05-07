"""Tests for Level 3 Medium Fidelity (A.5)."""

from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.scientist.methods.search.funnel.level3_medium import (
    _FORBIDDEN_PRUNING_METRICS,
    Level3MediumFidelity,
)


def _make_candidate():
    return {
        "semantic": {
            "interventions": [
                {"type": "tax_reform", "parameters": {"rate": 0.2}},
            ],
            "objectives": [{"name": "gdp_growth"}],
        },
    }


def _make_mock_engine(result=None):
    engine = MagicMock()
    if result is None:
        result = {
            "simulation_results": {
                "gdp_change": 0.03,
                "gov_balance": -0.01,
            },
            "feedback": {"verdict": "APPROVE"},
        }
    engine.run.return_value = result
    return engine


class TestLevel3MediumFidelity:
    def test_stage_metadata(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        assert stage.stage_name == "funnel_L3_medium"
        assert stage.fidelity_level == 3
        assert stage.estimated_cost_usd > 0

    def test_successful_evaluation(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        result = stage.evaluate(_make_candidate(), {})

        assert result.is_promising is True
        assert result.fidelity_level == 3
        assert result.simulation_results["gdp_change"] == 0.03

    def test_reduced_config_injected(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(
            workflow_engine=engine,
            subsample_fraction=0.15,
            bootstrap_draws=30,
            estimator_tier="matching",
        )
        stage.evaluate(_make_candidate(), {})

        # Inspect what was passed to engine.run().
        call_args = engine.run.call_args[0][0]
        assert call_args["data_config"]["subsample_fraction"] == 0.15
        assert call_args["data_config"]["stratified"] is True
        assert call_args["estimation_config"]["estimator"] == "matching"
        assert call_args["estimation_config"]["n_bootstrap"] == 30
        assert call_args["model_config"]["scm_complexity"] == "reduced"

    def test_cardinal_rule_disclaimer(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        result = stage.evaluate(_make_candidate(), {})

        assert result.feedback["level3_disclaimer"] == "routing_signal_only"
        assert result.feedback["forbidden_for_pruning"] == _FORBIDDEN_PRUNING_METRICS

    def test_fidelity_config_in_feedback(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(
            workflow_engine=engine,
            subsample_fraction=0.3,
            bootstrap_draws=40,
        )
        result = stage.evaluate(_make_candidate(), {})

        fidelity_cfg = result.feedback["fidelity_config"]
        assert fidelity_cfg["subsample_fraction"] == 0.3
        assert fidelity_cfg["bootstrap_draws"] == 40

    def test_workflow_failure_produces_reject(self):
        engine = MagicMock()
        engine.run.side_effect = RuntimeError("engine crash")

        stage = Level3MediumFidelity(workflow_engine=engine)
        result = stage.evaluate(_make_candidate(), {})

        assert result.is_promising is False
        assert result.objective_value == float("inf")
        assert any(fc.failure_type == "workflow_error" for fc in result.failure_cards)

    def test_objective_matches_expensive_stage_formula(self):
        """Objective formula must match ExpensiveStage._compute_default_objective."""
        engine = _make_mock_engine(
            {
                "simulation_results": {"gdp_change": 0.05, "gov_balance": -0.02},
                "feedback": {"verdict": "APPROVE"},
            }
        )
        stage = Level3MediumFidelity(workflow_engine=engine)
        result = stage.evaluate(_make_candidate(), {})

        expected = -(0.05 - 0.5 * 0.02)  # -(gdp - 0.5 * deficit)
        assert abs(result.objective_value - expected) < 1e-10

    def test_compute_actual_usd_positive(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        result = stage.evaluate(_make_candidate(), {})
        assert result.compute_actual_usd >= 0.0

    def test_uncertainty_envelope_has_model(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        result = stage.evaluate(_make_candidate(), {})

        from polisyos.scientist.methods.search.funnel.types import UncertaintyType

        assert UncertaintyType.MODEL in result.uncertainty_envelope.uncertainties

    def test_as_stage_b_callable(self):
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        callable_fn = stage.as_stage_b_callable()

        result = callable_fn(_make_candidate(), {})
        assert "simulation_results" in result
        assert "feedback" in result
        assert result["is_promising"] is True

    def test_context_keys_propagated(self):
        """Non-reserved context keys should be propagated to engine."""
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        stage.evaluate(_make_candidate(), {"custom_key": "value"})

        call_args = engine.run.call_args[0][0]
        assert call_args["custom_key"] == "value"

    def test_funnel_context_keys_excluded(self):
        """Keys starting with _funnel_ should not be propagated."""
        engine = _make_mock_engine()
        stage = Level3MediumFidelity(workflow_engine=engine)
        stage.evaluate(_make_candidate(), {"_funnel_L1_result": "should_not_appear"})

        call_args = engine.run.call_args[0][0]
        assert "_funnel_L1_result" not in call_args
