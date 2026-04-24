from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.network.analysis import NetworkDiffusionEstimator
from polisyos.foundry.methods.catalog.network.missingness import (
    NetworkMissingnessRequest,
    build_network_missingness_assessment,
)
from polisyos.foundry.methods.catalog.network.protocols import (
    NetworkData,
    NetworkIdentificationStatus,
)


def _dyad_prob_matrix(n_nodes: int, value: float) -> np.ndarray:
    matrix = np.full((n_nodes, n_nodes), value, dtype=float)
    np.fill_diagonal(matrix, 1.0)
    return matrix


def test_design_based_edge_count_and_sensitivity_region() -> None:
    data = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
            ]
        )
    )
    request = NetworkMissingnessRequest(
        mode="sensitivity",
        missingness_type="link_censoring",
        estimands=("edge_count", "average_degree"),
        dyad_inclusion_probabilities=_dyad_prob_matrix(3, 0.5),
        sensitivity_values=(-1.0, 0.0, 1.0),
    )

    assessment = build_network_missingness_assessment(data, request)
    edge = assessment.estimands["edge_count"]
    avg_degree = assessment.estimands["average_degree"]

    assert edge.identification_status is NetworkIdentificationStatus.POINT_IDENTIFIED
    assert edge.estimate == pytest.approx(4.0)
    assert edge.std_error == pytest.approx(2.0)
    assert avg_degree.estimate == pytest.approx(8.0 / 3.0)
    assert avg_degree.std_error == pytest.approx(4.0 / 3.0)
    assert edge.sensitivity_region is not None
    sensitivity_points = edge.sensitivity_region["point_estimates"]
    assert sensitivity_points[0] > sensitivity_points[-1]


def test_design_based_clustering_ratio_ht_returns_point_identified() -> None:
    data = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 1.0],
                [1.0, 0.0, 1.0],
                [1.0, 1.0, 0.0],
            ]
        )
    )
    request = NetworkMissingnessRequest(
        mode="design_based",
        missingness_type="link_censoring",
        estimands=("triangle_count", "wedge_count", "clustering"),
        dyad_inclusion_probabilities=_dyad_prob_matrix(3, 1.0),
    )

    assessment = build_network_missingness_assessment(data, request)

    assert assessment.estimands["triangle_count"].estimate == pytest.approx(1.0)
    assert assessment.estimands["wedge_count"].estimate == pytest.approx(3.0)
    assert (
        assessment.estimands["clustering"].identification_status
        is NetworkIdentificationStatus.POINT_IDENTIFIED
    )
    assert assessment.estimands["clustering"].estimate == pytest.approx(1.0)


def test_bounds_mode_returns_sharp_component_and_path_regions() -> None:
    data = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
            ]
        ),
        node_ids=["a", "b", "c", "d"],
    )
    confirmed_absence = np.zeros((4, 4), dtype=bool)
    confirmed_absence[0, 3] = True
    confirmed_absence[3, 0] = True
    request = NetworkMissingnessRequest(
        mode="bounds_only",
        frame_observed=True,
        estimands=(
            "edge_count",
            "average_degree",
            "degree_bounds",
            "giant_component",
            "shortest_paths",
        ),
        confirmed_absence_mask=confirmed_absence,
        shortest_path_pairs=(("a", "d"),),
    )

    assessment = build_network_missingness_assessment(data, request)

    assert assessment.estimands["edge_count"].identification_region == (1, 5)
    assert assessment.estimands["average_degree"].identification_region == pytest.approx((0.5, 2.5))
    assert assessment.estimands["giant_component"].identification_region == pytest.approx(
        (0.5, 1.0)
    )
    assert assessment.estimands["shortest_paths"].identification_region == {"(a,d)": (2, None)}
    assert assessment.estimands["degree_bounds"].identification_region["a"] == (1, 2)


def test_degree_centrality_bounds_are_returned_separately_from_degree_bounds() -> None:
    data = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
            ]
        ),
        node_ids=["a", "b", "c", "d"],
    )
    confirmed_absence = np.zeros((4, 4), dtype=bool)
    confirmed_absence[0, 3] = True
    confirmed_absence[3, 0] = True
    request = NetworkMissingnessRequest(
        mode="bounds_only",
        frame_observed=True,
        estimands=("degree_centrality",),
        confirmed_absence_mask=confirmed_absence,
    )

    assessment = build_network_missingness_assessment(data, request)
    degree_centrality = assessment.estimands["degree_centrality"]

    assert degree_centrality.identification_status is NetworkIdentificationStatus.SET_IDENTIFIED
    assert degree_centrality.identification_region["a"] == pytest.approx((1.0 / 3.0, 2.0 / 3.0))


def test_node_sampling_degree_distribution_is_supported_with_homogeneous_sampling() -> None:
    data = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
            ]
        )
    )
    request = NetworkMissingnessRequest(
        mode="design_based",
        missingness_type="node_sampling",
        estimands=("degree_distribution",),
        node_observed_mask=np.array([True, True, False, True]),
        node_inclusion_probabilities=np.array([0.75, 0.75, 0.75, 0.75]),
    )

    assessment = build_network_missingness_assessment(data, request)
    degree_distribution = assessment.estimands["degree_distribution"]

    assert degree_distribution.identification_status is NetworkIdentificationStatus.POINT_IDENTIFIED
    assert degree_distribution.estimate is not None
    assert abs(sum(degree_distribution.estimate.values()) - 1.0) < 1e-6
    assert degree_distribution.diagnostics["sampled_node_count"] == 3


def test_model_based_mode_returns_posterior_predictive_summary() -> None:
    data = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ]
        ),
        node_ids=["u", "v", "w"],
    )
    request = NetworkMissingnessRequest(
        mode="model_based",
        missingness_type="link_censoring",
        estimands=("edge_count", "giant_component", "betweenness_centrality", "shortest_paths"),
        confirmed_absence_mask=np.array(
            [
                [False, False, False],
                [False, False, True],
                [False, True, False],
            ]
        ),
        shortest_path_pairs=(("u", "w"),),
        posterior_draws=256,
        posterior_seed=7,
    )

    assessment = build_network_missingness_assessment(data, request)
    edge_count = assessment.estimands["edge_count"]
    giant_component = assessment.estimands["giant_component"]
    betweenness = assessment.estimands["betweenness_centrality"]

    assert edge_count.identification_status is NetworkIdentificationStatus.MODEL_DEPENDENT
    assert 1.0 <= edge_count.estimate <= 2.0
    assert "credible_interval" in edge_count.diagnostics
    assert giant_component.identification_status is NetworkIdentificationStatus.MODEL_DEPENDENT
    assert 2.0 / 3.0 <= giant_component.estimate <= 1.0
    assert betweenness.identification_status is NetworkIdentificationStatus.MODEL_DEPENDENT
    assert set(betweenness.estimate) == {"u", "v", "w"}
    assert assessment.diagnostics["model_fit_diagnostics"]["status"] == "ok"


def test_network_estimator_threads_missingness_assessment_into_result() -> None:
    request = NetworkMissingnessRequest(
        mode="design_based",
        missingness_type="link_censoring",
        estimands=("edge_count", "average_degree"),
        dyad_inclusion_probabilities=_dyad_prob_matrix(3, 0.5),
    )
    state = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
            ]
        ),
        node_states=np.array([1.0, 0.0, 0.5]),
        metadata={"missingness": request.model_dump(mode="python")},
    )

    result = NetworkDiffusionEstimator.pure_step(
        state,
        {"diffusion_rate": 0.2, "decay": 0.1, "n_steps": 3},
    )["result"]

    assert result.missingness_assessment is not None
    assert result.missingness_assessment.estimands["edge_count"].estimate == pytest.approx(4.0)
    assert result.missingness_assessment.estimands["average_degree"].identification_status is (
        NetworkIdentificationStatus.POINT_IDENTIFIED
    )
