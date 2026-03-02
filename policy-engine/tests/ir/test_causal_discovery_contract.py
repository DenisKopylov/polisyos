from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import (
    CausalDiscoveryReport,
    load_causal_discovery_report,
    persist_causal_discovery_report,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.refs import CausalDiscoveryReportRef


def _minimal_report() -> CausalDiscoveryReport:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
        discovery_method="fci",
    )
    resolved_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
        discovery_method="fci",
    )
    return CausalDiscoveryReport(
        method="fci",
        graph=graph,
        resolved_graph=resolved_graph,
        bootstrap_stability={"X->Y@lag=1": 0.92},
        n_bootstrap=100,
        significance_level=0.05,
        computation_time_seconds=12.4,
        warnings=[],
    )


def test_causal_discovery_report_contract() -> None:
    report = _minimal_report()
    assert report.method == "fci"
    assert report.graph.graph_type is GraphType.PAG
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG
    assert report.n_bootstrap == 100
    assert report.bootstrap_stability["X->Y@lag=1"] == 0.92


def test_causal_discovery_report_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = _minimal_report()

    ref = persist_causal_discovery_report(store, report)
    loaded = load_causal_discovery_report(store, ref)

    assert isinstance(ref, CausalDiscoveryReportRef)
    assert ref.kind == "ir.causal_discovery_report"
    assert loaded == report
