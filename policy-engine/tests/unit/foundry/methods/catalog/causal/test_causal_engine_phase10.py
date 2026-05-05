"""Phase 10 integration tests for CausalEngine high-level methods.

Covers:
  P10-1  identify_with_missing_data: recoverable + non-recoverable routing
  P10-2  mediation_analysis: dispatch to semiparametric / linear / cde
  P10-3  interference_effect: dispatch to all 4 estimators
  P10-4  counterfactual_query: PN/PS/PNS/abduction/all dispatch
  P10-5  fairness_audit: dispatch to tv_decomposition / path_specific / counterfactual
  P10-6  data_fusion: dispatch to DataFusionEngine
  P10-7  CounterfactualNode IR: to_latex, EstimandNode union, make_counterfactual_estimand
  P10-8  MissingDataCausalData protocol: valid, shape mismatch, variable_names mismatch
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_engine() -> CausalEngine:
    return CausalEngine(registry=None, knowledge_base=None)


def _mock_mgraph_meta(recoverable: bool = True) -> MagicMock:
    """Build a minimal MGraph-like mock."""
    from polisyos.ir.analytics.causal_graph import (
        CausalEdge,
        CausalGraphModel,
        EdgeMark,
        GraphType,
    )

    base_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
    )
    meta = MagicMock()
    meta.base_graph = base_graph
    meta.model_dump = MagicMock(return_value={"base_graph": base_graph.model_dump(mode="json")})
    return meta


# ---------------------------------------------------------------------------
# P10-1: identify_with_missing_data
# ---------------------------------------------------------------------------


class TestIdentifyWithMissingData:
    def setup_method(self) -> None:
        self.engine = _make_engine()

    def test_recoverable_delegates_to_identify(self) -> None:
        """When RecoverabilityTest returns 'recoverable', routes to self.identify."""
        meta = _mock_mgraph_meta(recoverable=True)
        rec_output = {"recoverability_result": {"status": "recoverable", "blocking_r_nodes": []}}

        with patch(
            "polisyos.foundry.methods.catalog.causal.missing_data.RecoverabilityTest.pure_step",
            return_value=rec_output,
        ):
            result = self.engine.identify_with_missing_data("X", "Y", meta)

        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate

        assert isinstance(result, (IdentificationResult, NegativeCertificate))

    def test_non_recoverable_returns_negative_cert(self) -> None:
        """When RecoverabilityTest returns 'not_recoverable', returns NegativeCertificate."""
        meta = _mock_mgraph_meta(recoverable=False)
        rec_output = {
            "recoverability_result": {
                "status": "not_recoverable",
                "blocking_r_nodes": ["R_X"],
            }
        }

        with patch(
            "polisyos.foundry.methods.catalog.causal.missing_data.RecoverabilityTest.pure_step",
            return_value=rec_output,
        ):
            result = self.engine.identify_with_missing_data("X", "Y", meta)

        from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type == BlockingType.MISSINGNESS_NOT_RECOVERABLE
        assert result.quantitative_diagnostics["recoverability"]["status"] == "not_recoverable"

    def test_no_base_graph_returns_missing_distribution_cert(self) -> None:
        """MGraph without base_graph returns NegativeCertificate."""
        meta = MagicMock()
        meta.base_graph = None
        meta.graph = None
        meta.model_dump = MagicMock(return_value={})

        rec_output = {"recoverability_result": {"status": "recoverable", "blocking_r_nodes": []}}
        with patch(
            "polisyos.foundry.methods.catalog.causal.missing_data.RecoverabilityTest.pure_step",
            return_value=rec_output,
        ):
            result = self.engine.identify_with_missing_data("X", "Y", meta)

        from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type == BlockingType.MISSING_DISTRIBUTION

    def test_recoverability_failure_falls_through_to_identify(self) -> None:
        """If RecoverabilityTest raises, treat as recoverable and try identify."""
        meta = _mock_mgraph_meta()
        with patch(
            "polisyos.foundry.methods.catalog.causal.missing_data.RecoverabilityTest.pure_step",
            side_effect=ImportError("missing dep"),
        ):
            # Should still produce some result (IdentificationResult or NegativeCertificate)
            from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult
            from polisyos.ir.analytics.negative_certificate import NegativeCertificate

            result = self.engine.identify_with_missing_data("X", "Y", meta)
            assert isinstance(result, (IdentificationResult, NegativeCertificate))


# ---------------------------------------------------------------------------
# P10-2: mediation_analysis
# ---------------------------------------------------------------------------


class TestMediationAnalysis:
    def setup_method(self) -> None:
        self.engine = _make_engine()

    def _make_mediation_data(self) -> dict[str, Any]:
        rng = np.random.default_rng(0)
        n = 200
        T = rng.integers(0, 2, size=n).astype(float)
        M = 0.5 * T + rng.normal(0, 0.3, n)
        Y = 0.3 * M + 0.2 * T + rng.normal(0, 0.3, n)
        X = rng.normal(0, 1, (n, 2))
        return {
            "outcome": Y,
            "treatment": T,
            "mediator": M,
            "covariates": X,
        }

    def test_linear_method_returns_result(self) -> None:
        from polisyos.foundry.methods.catalog.causal.mediation import NaturalEffectEstimator

        data = self._make_mediation_data()
        mock_result = {"result": {"acme": 0.2, "ade": 0.15, "total_effect": 0.35}}
        with patch.object(NaturalEffectEstimator, "pure_step", return_value=mock_result):
            result = self.engine.mediation_analysis(
                data, treatment="T", outcome="Y", mediators=["M"], method="linear"
            )
        assert result is not None

    def test_cde_method_returns_result(self) -> None:
        from polisyos.foundry.methods.catalog.causal.mediation import (
            ControlledDirectEffectEstimator,
        )

        data = self._make_mediation_data()
        mock_result = {"result": {"cde": 0.25, "n_obs": 200}}
        with patch.object(ControlledDirectEffectEstimator, "pure_step", return_value=mock_result):
            result = self.engine.mediation_analysis(
                data, treatment="T", outcome="Y", mediators=["M"], method="cde"
            )
        assert result is not None

    def test_invalid_method_raises_value_error(self) -> None:
        data = self._make_mediation_data()
        with pytest.raises(ValueError, match="Unknown mediation method"):
            self.engine.mediation_analysis(
                data, treatment="T", outcome="Y", mediators=["M"], method="nonexistent"
            )

    def test_dispatches_correct_estimator_for_semiparametric(self) -> None:
        from polisyos.foundry.methods.catalog.causal.path_specific import (
            PathSpecificEffectEstimator,
        )

        data = self._make_mediation_data()
        mock_result = {"mediation_result": {"nde": 0.3, "nie": 0.1, "total_effect": 0.4}}
        with patch.object(PathSpecificEffectEstimator, "pure_step", return_value=mock_result):
            result = self.engine.mediation_analysis(
                data, treatment="T", outcome="Y", mediators=["M"], method="semiparametric"
            )
        assert result == {"nde": 0.3, "nie": 0.1, "total_effect": 0.4}

    def test_dispatches_correct_estimator_for_linear(self) -> None:
        from polisyos.foundry.methods.catalog.causal.mediation import NaturalEffectEstimator

        data = self._make_mediation_data()
        mock_result = {"result": {"acme": 0.2, "ade": 0.15, "total_effect": 0.35}}
        with patch.object(NaturalEffectEstimator, "pure_step", return_value=mock_result):
            result = self.engine.mediation_analysis(
                data, treatment="T", outcome="Y", mediators=["M"], method="linear"
            )
        assert result == {"acme": 0.2, "ade": 0.15, "total_effect": 0.35}


# ---------------------------------------------------------------------------
# P10-3: interference_effect
# ---------------------------------------------------------------------------


class TestInterferenceEffect:
    def setup_method(self) -> None:
        self.engine = _make_engine()

    def _make_network_data(self) -> Any:
        from polisyos.foundry.methods.catalog.causal.protocols import NetworkCausalData

        rng = np.random.default_rng(1)
        n = 100
        return NetworkCausalData(
            outcome=rng.normal(0, 1, n),
            treatment=rng.integers(0, 2, n).astype(float),
            covariates=rng.normal(0, 1, (n, 2)),
            cluster_id=rng.integers(0, 10, n),
        )

    def test_partial_method_dispatches(self) -> None:
        from polisyos.foundry.methods.catalog.causal.interference import (
            PartialInterferenceEstimator,
        )

        data = self._make_network_data()
        mock_result = {"result": MagicMock()}
        with patch.object(PartialInterferenceEstimator, "pure_step", return_value=mock_result):
            result = self.engine.interference_effect(data, "T", "Y", method="partial")
        assert result is not None

    def test_network_aipw_method_dispatches(self) -> None:
        from polisyos.foundry.methods.catalog.causal.interference import NetworkAIPWEstimator

        data = self._make_network_data()
        mock_result = {"result": MagicMock()}
        with patch.object(NetworkAIPWEstimator, "pure_step", return_value=mock_result):
            result = self.engine.interference_effect(data, "T", "Y", method="network_aipw")
        assert result is not None

    def test_spatial_method_dispatches(self) -> None:
        from polisyos.foundry.methods.catalog.causal.interference import (
            SpatialInterferenceEstimator,
        )

        data = self._make_network_data()
        mock_result = {"result": MagicMock()}
        with patch.object(SpatialInterferenceEstimator, "pure_step", return_value=mock_result):
            result = self.engine.interference_effect(data, "T", "Y", method="spatial")
        assert result is not None

    def test_bipartite_method_dispatches(self) -> None:
        from polisyos.foundry.methods.catalog.causal.interference import (
            BipartiteInterferenceEstimator,
        )

        data = self._make_network_data()
        mock_result = {"result": MagicMock()}
        with patch.object(BipartiteInterferenceEstimator, "pure_step", return_value=mock_result):
            result = self.engine.interference_effect(data, "T", "Y", method="bipartite")
        assert result is not None

    def test_invalid_method_raises_value_error(self) -> None:
        data = self._make_network_data()
        with pytest.raises(ValueError, match="Unknown interference method"):
            self.engine.interference_effect(data, "T", "Y", method="bad_method")


# ---------------------------------------------------------------------------
# P10-4: counterfactual_query
# ---------------------------------------------------------------------------


class TestCounterfactualQuery:
    def setup_method(self) -> None:
        self.engine = _make_engine()

    def _make_ncm_query_data(self) -> Any:
        """Build a minimal NCMQueryData using the correct NCMSpec field names."""
        from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
        from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation

        ncm = NCMSpec(
            endogenous_vars=["T", "Y"],
            structural_equations=[
                StructuralEquation(
                    variable="T", parents=[], exogenous="U_T", equation_type="linear"
                ),
                StructuralEquation(
                    variable="Y", parents=["T"], exogenous="U_Y", equation_type="linear"
                ),
            ],
            exogenous_specs=[
                ExogenousSpec(variable="U_T", associated_endogenous="T"),
                ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
            ],
        )
        return NCMQueryData(
            ncm_spec=ncm,
            evidence={"T": 1.0, "Y": 1.0},
            interventions=[{"T": 1.0}, {"T": 0.0}],
            metadata={"treatment_variable": "T", "outcome_variable": "Y"},
        )

    def test_pn_query_dispatches_to_actual_causality(self) -> None:
        from polisyos.foundry.methods.catalog.causal.actual_causality import ActualCausalityEngine

        ncm_data = self._make_ncm_query_data()
        mock_result = {"pn_result": {"point_estimate": 0.8, "lower": 0.6, "upper": 1.0}}
        with patch.object(ActualCausalityEngine, "pure_step", return_value=mock_result):
            result = self.engine.counterfactual_query(
                ncm_data,
                query="pn",
                evidence={"T": 1, "Y": 1},
                treatment="T",
                outcome="Y",
            )
        assert "pn_result" in result

    def test_ps_query_dispatches_to_actual_causality(self) -> None:
        from polisyos.foundry.methods.catalog.causal.actual_causality import ActualCausalityEngine

        ncm_data = self._make_ncm_query_data()
        mock_result = {"ps_result": {"point_estimate": 0.7}}
        with patch.object(ActualCausalityEngine, "pure_step", return_value=mock_result):
            result = self.engine.counterfactual_query(
                ncm_data,
                query="ps",
                evidence={"T": 0, "Y": 0},
                treatment="T",
                outcome="Y",
            )
        assert "ps_result" in result

    def test_pns_query_dispatches_to_actual_causality(self) -> None:
        from polisyos.foundry.methods.catalog.causal.actual_causality import ActualCausalityEngine

        ncm_data = self._make_ncm_query_data()
        mock_result = {"pns_result": {"point_estimate": 0.65}}
        with patch.object(ActualCausalityEngine, "pure_step", return_value=mock_result):
            result = self.engine.counterfactual_query(
                ncm_data,
                query="pns",
                evidence={},
                treatment="T",
                outcome="Y",
            )
        assert "pns_result" in result

    def test_all_query_dispatches_to_actual_causality(self) -> None:
        from polisyos.foundry.methods.catalog.causal.actual_causality import ActualCausalityEngine

        ncm_data = self._make_ncm_query_data()
        mock_result = {"pn_result": {}, "ps_result": {}, "pns_result": {}}
        with patch.object(ActualCausalityEngine, "pure_step", return_value=mock_result):
            result = self.engine.counterfactual_query(
                ncm_data,
                query="all",
                evidence={},
                treatment="T",
                outcome="Y",
            )
        assert result is not None

    def test_abduction_query_dispatches_to_ncm_engine(self) -> None:
        from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod

        ncm_data = self._make_ncm_query_data()
        mock_result = {"counterfactual_result": {"world_summaries": [], "n_worlds": 0}}
        with patch.object(NCMEngineMethod, "pure_step", return_value=mock_result):
            result = self.engine.counterfactual_query(
                ncm_data,
                query="abduction",
                evidence={"T": 1},
                treatment="T",
                outcome="Y",
            )
        assert result is not None

    def test_invalid_query_raises_value_error(self) -> None:
        ncm_data = self._make_ncm_query_data()
        with pytest.raises(ValueError, match="Unknown counterfactual query"):
            self.engine.counterfactual_query(
                ncm_data,
                query="invalid_query",
                evidence={},
            )


# ---------------------------------------------------------------------------
# P10-5: fairness_audit
# ---------------------------------------------------------------------------


class TestFairnessAudit:
    def setup_method(self) -> None:
        self.engine = _make_engine()

    def _make_fairness_data(self) -> Any:
        from polisyos.foundry.methods.catalog.causal.protocols import FairnessObservationalData

        rng = np.random.default_rng(2)
        n = 200
        return FairnessObservationalData(
            outcome=rng.normal(0, 1, n),
            protected=rng.integers(0, 2, n).astype(float),
            covariates=rng.normal(0, 1, (n, 3)),
            mediators=rng.normal(0, 1, (n, 1)),
        )

    def test_tv_decomposition_dispatches(self) -> None:
        from polisyos.foundry.methods.catalog.causal.fairness import TVFairnessDecomposer

        data = self._make_fairness_data()
        mock_result = {"fairness_report": MagicMock()}
        with patch.object(TVFairnessDecomposer, "pure_step", return_value=mock_result):
            result = self.engine.fairness_audit(data, "A", "Y", method="tv_decomposition")
        assert result is not None

    def test_path_specific_dispatches(self) -> None:
        from polisyos.foundry.methods.catalog.causal.fairness import PathSpecificFairnessEstimator

        data = self._make_fairness_data()
        mock_result = {"fairness_report": MagicMock()}
        with patch.object(PathSpecificFairnessEstimator, "pure_step", return_value=mock_result):
            result = self.engine.fairness_audit(data, "A", "Y", method="path_specific")
        assert result is not None

    def test_counterfactual_dispatches(self) -> None:
        from polisyos.foundry.methods.catalog.causal.fairness import CounterfactualFairnessEstimator

        data = self._make_fairness_data()
        mock_result = {"fairness_report": MagicMock()}
        with patch.object(CounterfactualFairnessEstimator, "pure_step", return_value=mock_result):
            result = self.engine.fairness_audit(data, "A", "Y", method="counterfactual")
        assert result is not None

    def test_invalid_method_raises_value_error(self) -> None:
        data = self._make_fairness_data()
        with pytest.raises(ValueError, match="Unknown fairness method"):
            self.engine.fairness_audit(data, "A", "Y", method="unknown")


# ---------------------------------------------------------------------------
# P10-6: data_fusion
# ---------------------------------------------------------------------------


class TestDataFusion:
    def setup_method(self) -> None:
        self.engine = _make_engine()

    def _make_fusion_data(self) -> Any:
        from polisyos.foundry.methods.catalog.causal.protocols import MultiStudyFusionData
        from polisyos.ir.analytics.causal_graph import (
            CausalEdge,
            CausalGraphModel,
            EdgeMark,
            GraphType,
        )

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        )
        return MultiStudyFusionData(
            datasets=[
                {
                    "dataset_ref": "obs",
                    "domain_id": "source",
                    "n_obs": 500,
                    "available_interventions": [],
                    "selection_bias_vars": [],
                    "quality_score": 0.9,
                }
            ],
            graph=graph,
            treatment="X",
            outcome="Y",
        )

    def test_dispatches_to_data_fusion_engine(self) -> None:
        from polisyos.foundry.methods.catalog.causal.data_fusion import DataFusionEngine

        data = self._make_fusion_data()
        mock_result = {"fusion_result": {"estimand_ast": None, "notes": "ok"}}
        with patch.object(DataFusionEngine, "pure_step", return_value=mock_result):
            result = self.engine.data_fusion(data)
        assert result == {"estimand_ast": None, "notes": "ok"}

    def test_different_modes_pass_mode_param(self) -> None:
        from polisyos.foundry.methods.catalog.causal.data_fusion import DataFusionEngine

        data = self._make_fusion_data()
        captured_params: list[dict] = []

        def capture_pure_step(state: Any, params: Any) -> dict:
            captured_params.append(dict(params))
            return {"fusion_result": {}}

        with patch.object(DataFusionEngine, "pure_step", side_effect=capture_pure_step):
            self.engine.data_fusion(data, mode="rct_plus_obs")

        assert captured_params[0]["mode"] == "rct_plus_obs"


# ---------------------------------------------------------------------------
# P10-7: CounterfactualNode IR
# ---------------------------------------------------------------------------


class TestCounterfactualNode:
    def test_to_latex_simple(self) -> None:
        from polisyos.ir.analytics.estimand import CounterfactualNode

        node = CounterfactualNode(variable="Y", intervention={"X": 1})
        latex = node.to_latex()
        assert "Y" in latex
        assert "X=1" in latex

    def test_to_latex_with_conditioning(self) -> None:
        from polisyos.ir.analytics.estimand import CounterfactualNode

        node = CounterfactualNode(variable="Y", intervention={"X": 1}, conditioning=("Z", "W"))
        latex = node.to_latex()
        assert "Z" in latex
        assert "W" in latex

    def test_node_participates_in_estimand_union(self) -> None:
        from polisyos.ir.analytics.estimand import (
            CounterfactualNode,
            EstimandAST,
        )

        node = CounterfactualNode(variable="Y", intervention={"X": 1})
        ast = EstimandAST(
            query_str="P(Y_{X=1})",
            root=node,
            treatment="X",
            outcome="Y",
            all_variables=("Y", "X"),
            identification_method="counterfactual_ncm",
        )
        assert ast.root is node

    def test_make_counterfactual_estimand_factory(self) -> None:
        from polisyos.ir.analytics.estimand import (
            CounterfactualNode,
            make_counterfactual_estimand,
        )

        ast = make_counterfactual_estimand(variable="Y", intervention={"X": 1}, conditioning=("Z",))
        assert isinstance(ast.root, CounterfactualNode)
        assert ast.treatment == "X"
        assert ast.outcome == "Y"
        assert "Y" in ast.all_variables
        assert "X" in ast.all_variables
        assert "Z" in ast.all_variables

    def test_collect_domains_with_counterfactual(self) -> None:
        from polisyos.ir.analytics.estimand import (
            CounterfactualNode,
            DistributionDomain,
            EstimandAST,
        )

        node = CounterfactualNode(
            variable="Y", intervention={"X": 1}, domain=DistributionDomain.TARGET
        )
        ast = EstimandAST(
            query_str="test",
            root=node,
            treatment="X",
            outcome="Y",
            all_variables=("Y", "X"),
        )
        domains = ast.required_domains()
        assert DistributionDomain.TARGET in domains

    def test_required_datasets_with_counterfactual(self) -> None:
        from polisyos.ir.analytics.estimand import (
            CounterfactualNode,
            EstimandAST,
        )

        node = CounterfactualNode(variable="Y", intervention={"X": 1}, dataset_ref="my_dataset")
        ast = EstimandAST(
            query_str="test",
            root=node,
            treatment="X",
            outcome="Y",
            all_variables=("Y", "X"),
        )
        refs = ast.required_datasets()
        assert "my_dataset" in refs

    def test_collect_dist_refs_counterfactual_is_leaf(self) -> None:
        from polisyos.ir.analytics.estimand import (
            CounterfactualNode,
            EstimandAST,
        )

        node = CounterfactualNode(variable="Y", intervention={"X": 1})
        ast = EstimandAST(
            query_str="test",
            root=node,
            treatment="X",
            outcome="Y",
            all_variables=("Y", "X"),
        )
        # Leaf node — no DistributionRef children
        refs = ast.collect_distribution_refs()
        assert refs == []

    def test_counterfactual_node_world_index(self) -> None:
        from polisyos.ir.analytics.estimand import CounterfactualNode

        node = CounterfactualNode(variable="Y", intervention={"X": 0}, world_index=1)
        assert node.world_index == 1

    def test_counterfactual_node_frozen(self) -> None:
        from polisyos.ir.analytics.estimand import CounterfactualNode

        node = CounterfactualNode(variable="Y", intervention={"X": 1})
        with pytest.raises(Exception):  # frozen=True
            node.variable = "Z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P10-8: MissingDataCausalData protocol
# ---------------------------------------------------------------------------


class TestMissingDataCausalData:
    def test_valid_construction(self) -> None:
        from polisyos.foundry.methods.catalog.causal.protocols import MissingDataCausalData

        n, p = 100, 3
        data = MissingDataCausalData(
            observed_data=np.random.randn(n, p),
            missingness_indicators=np.ones((n, p), dtype=int),
            variable_names=("X", "M", "Y"),
            treatment="X",
            outcome="Y",
        )
        assert data.n_obs == n
        assert data.n_vars == p

    def test_nan_values_accepted(self) -> None:
        from polisyos.foundry.methods.catalog.causal.protocols import MissingDataCausalData

        n, p = 50, 2
        obs = np.random.randn(n, p)
        obs[5, 0] = np.nan  # missing value
        data = MissingDataCausalData(
            observed_data=obs,
            missingness_indicators=np.ones((n, p), dtype=int),
            variable_names=("X", "Y"),
            treatment="X",
            outcome="Y",
        )
        assert np.isnan(data.observed_data[5, 0])

    def test_shape_mismatch_raises_validation_error(self) -> None:
        from polisyos.foundry.methods.catalog.causal.protocols import MissingDataCausalData
        from pydantic import ValidationError

        with pytest.raises((ValidationError, ValueError)):
            MissingDataCausalData(
                observed_data=np.random.randn(50, 3),
                missingness_indicators=np.ones((50, 2), dtype=int),  # wrong shape
                variable_names=("X", "M", "Y"),
                treatment="X",
                outcome="Y",
            )

    def test_variable_names_mismatch_raises_validation_error(self) -> None:
        from polisyos.foundry.methods.catalog.causal.protocols import MissingDataCausalData
        from pydantic import ValidationError

        with pytest.raises((ValidationError, ValueError)):
            MissingDataCausalData(
                observed_data=np.random.randn(50, 3),
                missingness_indicators=np.ones((50, 3), dtype=int),
                variable_names=("X", "Y"),  # only 2 names for 3 columns
                treatment="X",
                outcome="Y",
            )

    def test_contract_id_class_var(self) -> None:
        from polisyos.foundry.methods.catalog.causal.protocols import MissingDataCausalData

        assert "missing_data_causal_data" in MissingDataCausalData.contract_id

    def test_in_protocols_all(self) -> None:
        from polisyos.foundry.methods.catalog.causal import protocols

        assert "MissingDataCausalData" in protocols.__all__
