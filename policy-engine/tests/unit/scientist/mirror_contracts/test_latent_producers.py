import pytest

from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphProjectionStatus,
    GraphType,
    graph_projection_disposition,
)
from polisyos.scientist.methods.discovery.latent_producers import (
    produce_latent_discovery_bundle,
)
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_latent_producers_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract('scientist', 'latent_producers')



def test_latent_producer_rejects_a_graph_that_differs_from_the_admitted_report():
    source_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    different_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="Y", dst="X")],
    )
    report = CausalDiscoveryReport(
        method="fci",
        graph=source_graph,
        projection_disposition=graph_projection_disposition(
            source_graph,
            None,
            status=GraphProjectionStatus.IDENTITY,
        ),
        bootstrap_stability={},
        n_bootstrap=0,
        significance_level=0.05,
        computation_time_seconds=0.0,
        warnings=[],
    )

    with pytest.raises(ValueError, match="latent producer graph input differs"):
        produce_latent_discovery_bundle(report, graph=different_graph)
