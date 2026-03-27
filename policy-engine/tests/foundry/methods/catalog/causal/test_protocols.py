from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.protocols import (
    FragmentCompositionData,
    GraphCausalData,
    GraphCausalDataV1,
    GraphReconciliationData,
    HTEObservationalData,
    LiteraturePriorBuildData,
    LLMStructuralHint,
    PanelObservationalData,
    RDDObservationalData,
    SCMFitData,
    SCMQueryData,
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from polisyos.ir.analytics.alignment_certification import (
    AlignmentOverallStatus,
    MeasurementComparabilityGrade,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    RefutationResult,
    RefutationTestType,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.cross_graph import InterfaceMapping, SCMFragment


def test_panel_observational_data_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="Shape mismatch"):
        PanelObservationalData(
            outcome=np.zeros((2, 5)),
            treatment=np.array([1, 0, 0]),
            time_treatment=3,
        )


def test_panel_observational_data_rejects_non_binary_treatment():
    with pytest.raises(ValueError, match="binary"):
        PanelObservationalData(
            outcome=np.zeros((2, 5)),
            treatment=np.array([1, 2]),
            time_treatment=3,
        )


def test_panel_observational_data_rejects_repeated_cross_section_metadata():
    with pytest.raises(ValueError, match="repeated cross-section/survey data"):
        PanelObservationalData(
            outcome=np.zeros((2, 5)),
            treatment=np.array([1, 0]),
            time_treatment=3,
            metadata={"data_shape": "survey_repeated_cross_section"},
        )


def test_rdd_observational_data_rejects_short_sample():
    with pytest.raises(ValueError, match="at least 20"):
        RDDObservationalData(
            outcome=np.ones(10),
            running_variable=np.linspace(-1, 1, 10),
            cutoff=0.0,
        )


def test_causal_effect_report_to_envelope_success():
    report = CausalEffectReport(
        method=CausalMethod.SYNTHETIC_CONTROL,
        status=EstimationStatus.SUCCESS,
        estimand="ATT",
        point_estimate=2.0,
        confidence_interval=(1.0, 3.0),
        confidence_level=0.95,
        inference_method="bootstrap",
        sample_size=100,
        n_treated=1,
        n_control=10,
        pre_periods=5,
        post_periods=5,
    )
    env = report.to_uncertainty_envelope()
    assert env is not None
    assert env.point_estimate == 2.0
    assert env.confidence_interval == (1.0, 3.0)


def test_causal_effect_report_to_envelope_failure_returns_non_gate_eligible_envelope():
    report = CausalEffectReport(
        method=CausalMethod.SYNTHETIC_CONTROL,
        status=EstimationStatus.NUMERICAL_FAILURE,
        status_reason="optimizer did not converge",
        estimand="ATT",
        inference_method="none",
        sample_size=100,
        n_treated=1,
        n_control=10,
        pre_periods=5,
        post_periods=5,
    )
    env = report.to_uncertainty_envelope()
    assert env is not None
    assert env.gate_eligible is False
    assert env.is_heuristic_ci is True


def test_causal_effect_report_accepts_refutation_results():
    report = CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=500,
        n_treated=250,
        n_control=250,
        pre_periods=0,
        post_periods=0,
        refutation_results=[
            RefutationResult(
                test_type=RefutationTestType.RANDOM_COMMON_CAUSE,
                original_estimate=1.0,
                refuted_estimate=0.98,
                p_value=0.42,
                passed=True,
                effect_ratio=0.98,
                details={"source": "unit_test"},
            )
        ],
    )

    assert len(report.refutation_results) == 1
    assert report.refutation_results[0].passed is True


def test_hte_observational_data_validates_shapes():
    data = HTEObservationalData(
        outcome=np.arange(50, dtype=float),
        treatment=np.array([0, 1] * 25, dtype=int),
        covariates=np.ones((50, 3), dtype=float),
    )
    assert data.n_obs == 50
    assert data.n_features == 3


def test_hte_observational_data_rejects_non_binary_treatment():
    with pytest.raises(ValueError, match="binary"):
        HTEObservationalData(
            outcome=np.arange(50, dtype=float),
            treatment=np.arange(50, dtype=int),
            covariates=np.ones((50, 2), dtype=float),
        )


def test_graph_causal_data_valid_payload():
    payload = GraphCausalData(
        data=np.array([[1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [2.0, 3.0, 4.0]], dtype=float),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; }",
        graph_ref="cas:graph:123",
        covariates=["Z"],
    )
    assert payload.sample_size == 3


def test_graph_causal_data_v1_valid_payload():
    payload = GraphCausalDataV1(
        data=np.array([[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]], dtype=float),
        column_names=["X", "Y"],
        treatment="X",
        outcome="Y",
        graph_gml="digraph { X -> Y; }",
        graph_ref="cas:graph:legacy",
    )
    assert payload.sample_size == 3


def test_graph_causal_data_rejects_column_name_mismatch():
    with pytest.raises(ValueError, match="data columns != len\\(column_names\\)"):
        GraphCausalData(
            data=np.ones((3, 2), dtype=float),
            column_names=["X", "Y", "Z"],
            treatment="X",
            outcome="Y",
        )


def test_graph_causal_data_rejects_unknown_treatment():
    with pytest.raises(ValueError, match="treatment 'T' not in column_names"):
        GraphCausalData(
            data=np.ones((3, 2), dtype=float),
            column_names=["X", "Y"],
            treatment="T",
            outcome="Y",
        )


def test_graph_causal_data_rejects_non_finite_values():
    with pytest.raises(ValueError, match="non-finite"):
        GraphCausalData(
            data=np.array([[1.0, 2.0], [np.nan, 3.0]], dtype=float),
            column_names=["X", "Y"],
            treatment="X",
            outcome="Y",
        )


def test_scm_fit_data_valid_payload():
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="X", dst="Y"),
            CausalEdge(src="Z", dst="Y"),
        ],
    )
    payload = SCMFitData(
        data=np.array(
            [
                [1.0, 2.0, 3.0],
                [1.5, 2.7, 3.4],
                [2.1, 3.3, 4.1],
            ],
            dtype=float,
        ),
        column_names=["X", "Y", "Z"],
        graph=graph,
        graph_ref="cas:graph:scm",
        literature_priors={
            "Y": {
                "X": {"mean": 0.5, "std": 0.2},
                "Z": {"mean": 0.1, "std": 0.3},
                "__intercept__": {"mean": 0.0, "std": 1.0},
            }
        },
    )
    assert payload.sample_size == 3
    assert isinstance(payload.graph, CausalGraphModel)


def test_scm_fit_data_rejects_columns_missing_in_graph():
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    with pytest.raises(ValueError, match="not present in graph nodes"):
        SCMFitData(
            data=np.array([[1.0, 2.0, 3.0], [1.1, 2.1, 3.1]], dtype=float),
            column_names=["X", "Y", "Z"],
            graph=graph,
        )


def test_scm_query_data_valid_payload() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    scm_spec = {
        "graph": graph.model_dump(mode="json"),
        "mechanisms": [
            {
                "variable": "Y",
                "parents": ["X"],
                "family": "linear",
                "family_params": {
                    "intercept": 0.0,
                    "coefficients": {"X": 1.0},
                    "noise_std": 0.1,
                },
                "source": "data_fitted",
            }
        ],
        "fitted": True,
        "fit_method": "gcm",
    }
    payload = SCMQueryData(
        scm_spec=scm_spec,
        query={
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 128,
        },
    )
    assert payload.query.treatment_variable == "X"
    assert payload.query.outcome_variable == "Y"


def test_scm_query_data_rejects_unknown_variables() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    with pytest.raises(ValueError, match="not in SCM graph nodes"):
        SCMQueryData(
            scm_spec={
                "graph": graph.model_dump(mode="json"),
                "mechanisms": [
                    {
                        "variable": "Y",
                        "parents": ["X"],
                        "family": "linear",
                        "family_params": {
                            "intercept": 0.0,
                            "coefficients": {"X": 1.0},
                            "noise_std": 0.1,
                        },
                        "source": "data_fitted",
                    }
                ],
                "fitted": False,
            },
            query={
                "query_type": "interventional",
                "treatment_variable": "T",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 64,
            },
        )


def test_scm_query_data_rejects_invalid_intervention_config() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    with pytest.raises(ValueError, match="bounds are required"):
        SCMQueryData(
            scm_spec={
                "graph": graph.model_dump(mode="json"),
                "mechanisms": [
                    {
                        "variable": "Y",
                        "parents": ["X"],
                        "family": "linear",
                        "family_params": {
                            "intercept": 0.0,
                            "coefficients": {"X": 1.0},
                            "noise_std": 0.1,
                        },
                        "source": "data_fitted",
                    }
                ],
                "fitted": False,
            },
            query={
                "query_type": "soft_intervention",
                "treatment_variable": "X",
                "outcome_variable": "Y",
                "n_samples": 32,
                "intervention_spec": {"type": "truncated"},
            },
        )


def test_scm_query_data_rejects_counterfactual_without_condition() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    with pytest.raises(ValueError, match="counterfactual queries require non-empty condition"):
        SCMQueryData(
            scm_spec={
                "graph": graph.model_dump(mode="json"),
                "mechanisms": [
                    {
                        "variable": "Y",
                        "parents": ["X"],
                        "family": "linear",
                        "family_params": {
                            "intercept": 0.0,
                            "coefficients": {"X": 1.0},
                            "noise_std": 0.1,
                        },
                        "source": "data_fitted",
                    }
                ],
                "fitted": False,
            },
            query={
                "query_type": "counterfactual",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "condition": {},
                "n_samples": 64,
            },
        )


def test_time_series_causal_data_valid_payload():
    payload = TimeSeriesCausalData(
        data=np.array([[1.0, 0.5], [1.1, 0.7], [1.2, 0.8], [1.4, 1.0]], dtype=float),
        variable_names=["X", "Y"],
        time_index=np.array([0, 1, 2, 3], dtype=int),
    )
    assert payload.n_timesteps == 4
    assert payload.n_variables == 2


def test_time_series_causal_data_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="len\\(variable_names\\) must match"):
        TimeSeriesCausalData(
            data=np.ones((5, 2), dtype=float),
            variable_names=["X", "Y", "Z"],
        )


def test_time_series_causal_data_rejects_duplicate_variable_names():
    with pytest.raises(ValueError, match="variable_names must be unique"):
        TimeSeriesCausalData(
            data=np.ones((5, 2), dtype=float),
            variable_names=["X", "X"],
        )


def test_time_series_causal_data_rejects_non_finite_values():
    with pytest.raises(ValueError, match="non-finite"):
        TimeSeriesCausalData(
            data=np.array([[1.0, 2.0], [2.0, np.nan], [3.0, 4.0]], dtype=float),
            variable_names=["X", "Y"],
        )


def test_tabular_causal_discovery_data_valid_payload():
    payload = TabularCausalDiscoveryData(
        data=np.array(
            [
                [1.0, 2.0, 3.0],
                [1.2, 2.2, 3.3],
                [1.5, 2.5, 3.7],
            ],
            dtype=float,
        ),
        variable_names=["X", "Y", "Z"],
    )
    assert payload.n_samples == 3
    assert payload.n_variables == 3


def test_tabular_causal_discovery_data_rejects_variable_name_mismatch():
    with pytest.raises(ValueError, match="len\\(variable_names\\) must match"):
        TabularCausalDiscoveryData(
            data=np.ones((4, 2), dtype=float),
            variable_names=["X", "Y", "Z"],
        )


def test_literature_prior_build_data_rejects_empty_variables():
    with pytest.raises(ValueError, match="at least one"):
        LiteraturePriorBuildData(variables=[], skg_db_path="/tmp/missing.duckdb")


def test_graph_reconciliation_data_coerces_graph_and_hints():
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["A", "B"],
        edges=[CausalEdge(src="A", dst="B", data_confidence=0.6, combined_confidence=0.6)],
    )
    payload = GraphReconciliationData(
        data_graph=graph.model_dump(mode="json"),
        llm_hints=[{"src": "A", "dst": "B", "confidence": 0.8}],
    )

    assert isinstance(payload.data_graph, CausalGraphModel)
    assert isinstance(payload.llm_hints[0], LLMStructuralHint)


def test_fragment_composition_data_coerces_fragments_graphs_and_alignment() -> None:
    payload = FragmentCompositionData(
        fragments=[
            {
                "fragment_id": "labor_a",
                "graph_ref": "artifact:graph:labor_a",
                "semantic_namespace": "policy.labor",
                "interface_variables": ["employment_rate"],
                "exposed_outputs": ["employment_rate"],
            },
            {
                "fragment_id": "labor_b",
                "graph_ref": "artifact:graph:labor_b",
                "semantic_namespace": "policy.labor",
                "interface_variables": ["employment_rate"],
                "exposed_inputs": ["employment_rate"],
            },
        ],
        fragment_graphs={
            "labor_a": {
                "graph_type": "dag",
                "nodes": ["employment_rate", "tax"],
                "edges": [{"src": "tax", "dst": "employment_rate"}],
            },
            "labor_b": {
                "graph_type": "dag",
                "nodes": ["employment_rate", "wages"],
                "edges": [{"src": "employment_rate", "dst": "wages"}],
            },
        },
        alignment_report={
            "schema_version": "1.0",
            "fragment_ids": ["labor_a", "labor_b"],
            "per_variable_certificates": [],
            "overall_status": "partially_aligned",
            "measurement_comparability_grade": "insufficient",
        },
        interface_mapping=InterfaceMapping(fragment_ids=["labor_a", "labor_b"]).model_dump(mode="json"),
        direct_stitch_pairs=[["labor_a", "labor_b"]],
    )

    assert isinstance(payload.fragments[0], SCMFragment)
    assert isinstance(payload.fragment_graphs["labor_a"], CausalGraphModel)
    assert payload.alignment_report.overall_status is AlignmentOverallStatus.PARTIALLY_ALIGNED
    assert (
        payload.alignment_report.measurement_comparability_grade
        is MeasurementComparabilityGrade.INSUFFICIENT
    )
    assert payload.direct_stitch_pairs == [("labor_a", "labor_b")]
