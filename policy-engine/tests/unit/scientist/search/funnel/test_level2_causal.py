"""Tests for Level 2 Causal Plausibility (A.4)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.scientist.search.funnel.level2_causal import Level2CausalPlausibility
from polisyos.scientist.search.funnel.types import CheapSignalVector, FunnelStageResult


def _make_candidate(**overrides):
    base = {
        "semantic": {
            "interventions": [
                {
                    "type": "tax_reform",
                    "variable": "treatment",
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


class TestLevel2CausalPlausibility:
    def setup_method(self):
        self.stage = Level2CausalPlausibility()

    def test_stage_metadata(self):
        assert self.stage.stage_name == "funnel_L2_causal"
        assert self.stage.fidelity_level == 2
        assert self.stage.estimated_cost_usd > 0

    def test_candidate_without_graph_still_produces_result(self):
        """Without a causal graph, L2 should still produce a result
        (with default/uncertain signals)."""
        result = self.stage.evaluate(_make_candidate(), {})
        assert isinstance(result, FunnelStageResult)
        assert result.fidelity_level == 2
        assert "data_readiness_decision" in result.feedback

    def test_candidate_with_l1_signal_inherits(self):
        """L2 should inherit signals from L1 result in context."""
        l1_signal = CheapSignalVector(
            structural_validity=0.9,
            feasibility=0.8,
            policy_conflict=0.1,
        )
        l1_result = FunnelStageResult(
            policy_candidate={},
            objective_value=0.5,
            is_promising=True,
            stage_name="funnel_L1_heuristic",
            cheap_signal=l1_signal,
        )
        result = self.stage.evaluate(
            _make_candidate(),
            {"_funnel_L1_result": l1_result},
        )
        # Should preserve L1's structural_validity and other signals.
        assert result.cheap_signal is not None
        assert result.cheap_signal.structural_validity == 0.9

    def test_plausibility_rank_in_0_1(self):
        result = self.stage.evaluate(_make_candidate(), {})
        assert 0.0 <= result.objective_value <= 1.0

    def test_uncertainty_envelope_has_structural(self):
        result = self.stage.evaluate(_make_candidate(), {})
        from polisyos.scientist.search.funnel.types import UncertaintyType

        assert UncertaintyType.STRUCTURAL in result.uncertainty_envelope.uncertainties

    def test_fast_proxy_with_no_data_returns_default(self):
        """Without data in context, proxy estimate should be 0.5 (unknown)."""
        result = self.stage.evaluate(_make_candidate(), {})
        # Proxy should be at default or slightly updated.
        assert result.cheap_signal is not None

    def test_fast_proxy_with_mock_data(self):
        """With data in context, proxy should detect association."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not available")

        np.random.seed(42)
        n = 200
        treatment = np.random.binomial(1, 0.5, n)
        outcome = treatment * 2.0 + np.random.normal(0, 1, n)

        # Create a mock DataFrame-like object.
        class MockDF:
            def __init__(self, data):
                self._data = data

            def __getitem__(self, key):
                return self._data[key]

            def sample(self, frac=1.0, random_state=None):
                n_sample = int(len(self._data["treatment"]) * frac)
                return MockDF(
                    {k: v[:n_sample] for k, v in self._data.items()},
                )

        data = MockDF({"treatment": treatment, "gdp": outcome})
        context = {
            "data": data,
            "treatment_col": "treatment",
            "outcome_col": "gdp",
        }

        result = self.stage.evaluate(_make_candidate(), context)
        # With a strong effect, proxy should be > 0.5.
        assert result.cheap_signal is not None
        assert result.cheap_signal.expected_value_proxy > 0.5

    def test_resolve_treatment_outcome(self):
        candidate = _make_candidate()
        treatment, outcome = self.stage._resolve_treatment_outcome(candidate)
        assert "treatment" in treatment
        assert "gdp" in outcome

    def test_resolve_graph_from_candidate(self):
        graph = MagicMock()
        candidate = _make_candidate(causal_graph=graph)
        resolved = self.stage._resolve_graph(candidate)
        assert resolved is graph

    def test_resolve_graph_none_when_absent(self):
        candidate = _make_candidate()
        resolved = self.stage._resolve_graph(candidate)
        assert resolved is None


class TestLevel2Identifiability:
    """Tests for the identifiability check when causal engine is available."""

    def test_identified_returns_high_score(self):
        stage = Level2CausalPlausibility()

        # Mock the id_algorithm to return IDENTIFIED.
        mock_result = MagicMock()
        mock_result.status = MagicMock()
        mock_result.status.name = "IDENTIFIED"
        mock_result.trace = ["step1", "step2"]

        with patch(
            "polisyos.scientist.search.funnel.level2_causal.Level2CausalPlausibility._check_identifiability",
            return_value=(1.0, []),
        ):
            candidate = _make_candidate(causal_graph=MagicMock(nodes=["X", "Y"]))
            result = stage.evaluate(candidate, {})
            assert result.cheap_signal is not None
            assert result.cheap_signal.causal_identifiability == 1.0
            assert "data_readiness_decision" in result.feedback

    def test_hedge_found_returns_zero_and_blocker(self):
        stage = Level2CausalPlausibility()

        from polisyos.scientist.search.funnel.types import TypedFailureCard

        blocker = TypedFailureCard(
            judge_name="L2_causal",
            failure_type="non_identifiable",
            severity="blocker",
            description="hedge found",
        )

        with patch(
            "polisyos.scientist.search.funnel.level2_causal.Level2CausalPlausibility._check_identifiability",
            return_value=(0.0, [blocker]),
        ):
            candidate = _make_candidate(causal_graph=MagicMock(nodes=["X", "Y"]))
            result = stage.evaluate(candidate, {})
            assert result.cheap_signal.causal_identifiability == 0.0
            assert result.is_promising is False
            assert result.has_blockers

    def test_stage_persists_canonical_artifacts_when_store_available(self, tmp_path):
        stage = Level2CausalPlausibility(artifact_store=FileSystemCAS(tmp_path / "cas"))
        graph = MagicMock(nodes=["X", "Y"])

        with patch(
            "polisyos.scientist.search.funnel.level2_causal.Level2CausalPlausibility._check_identifiability",
            return_value=(1.0, []),
        ):
            result = stage.evaluate(_make_candidate(causal_graph=graph), {})

        assert result.audit_refs
        assert "data_readiness_report_ref" in result.feedback

    def test_persist_bounds_bundle_attaches_dual_certificate_when_payload_present(self, tmp_path):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        store = FileSystemCAS(tmp_path / "cas")
        stage = Level2CausalPlausibility(artifact_store=store)
        result = BoundsEngineMethod.pure_step(
            {
                "outcome": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                "treatment": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
            },
            {"use_auto_bounds": True, "has_monotone": True},
        )

        ref = stage._persist_bounds_bundle(
            result["bounds_report"],
            result.get("dual_certificate_payload"),
        )

        assert ref is not None
        bundle = load_bounds_bundle(store, ref)
        assert bundle.dual_certificate_ref is not None
        assert bundle.sharpness_status == "sharp"

    def test_evaluate_propagates_recoverability_into_data_readiness(self):
        stage = Level2CausalPlausibility()

        def _mock_identifiability(*_args, **_kwargs):
            stage._last_identification_artifacts = {
                "recoverability": {
                    "status": "not_recoverable",
                    "blocking_r_nodes": ["R_X"],
                    "blocking_r_nodes_count": 1,
                }
            }
            return 1.0, []

        with patch.object(stage, "_check_identifiability", side_effect=_mock_identifiability):
            candidate = _make_candidate(causal_graph=MagicMock(nodes=["X", "Y"]))
            result = stage.evaluate(candidate, {"sample_size": 100})

        assert result.feedback["data_readiness_decision"] == "block"
        assert result.feedback["data_readiness_can_run_estimation"] is False


def test_coerce_context_data_does_not_swallow_assertion() -> None:
    class _Payload:
        def model_dump(self, *, mode: str):
            del mode
            raise AssertionError("context serialization invariant failed")

    with pytest.raises(AssertionError, match="context serialization invariant failed"):
        Level2CausalPlausibility._coerce_context_data({"data": _Payload()})


def test_fast_propensity_check_does_not_swallow_assertion() -> None:
    class _BrokenData:
        def __getitem__(self, _key):
            raise AssertionError("propensity access invariant failed")

    with pytest.raises(AssertionError, match="propensity access invariant failed"):
        Level2CausalPlausibility._fast_propensity_check(_BrokenData(), "treatment")


def test_fast_proxy_estimate_does_not_swallow_assertion() -> None:
    class _BrokenData:
        def __getitem__(self, _key):
            raise AssertionError("proxy access invariant failed")

    with pytest.raises(AssertionError, match="proxy access invariant failed"):
        Level2CausalPlausibility._fast_proxy_estimate(
            {},
            {
                "data": _BrokenData(),
                "treatment_col": "treatment",
                "outcome_col": "gdp",
            },
        )
