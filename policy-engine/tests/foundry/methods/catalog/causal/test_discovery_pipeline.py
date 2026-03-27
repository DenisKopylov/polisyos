from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal import discovery_pipeline as pipeline_module
from polisyos.foundry.methods.catalog.causal.protocols import TabularCausalDiscoveryData
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    EdgeAgreement,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)


def _state() -> TabularCausalDiscoveryData:
    return TabularCausalDiscoveryData(
        data=np.array(
            [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                [0.7, 0.8, 0.9],
            ],
            dtype=float,
        ),
        variable_names=["X", "Y", "Z"],
    )


def _report(
    *,
    method: str,
    src: str,
    dst: str,
    algebraic_severity: str,
    violated_by_family: dict[str, int],
) -> CausalDiscoveryReport:
    return CausalDiscoveryReport(
        method=method,
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "Z"],
            edges=[
                CausalEdge(
                    src=src,
                    dst=dst,
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            ],
            discovery_method=method,
        ),
        algebraic_constraints=AlgebraicConstraintReport(
            severity=algebraic_severity,  # type: ignore[arg-type]
            families_run=[AlgebraicConstraintFamily.CI],
            n_implied_constraints=1,
            n_violated_constraints=sum(violated_by_family.values()),
            tested_by_family={"ci": 1},
            violated_by_family=violated_by_family,
        ),
        metadata={"algebraic_constraint_severity": algebraic_severity},
    )


def test_unified_discovery_surfaces_disputed_edges_and_algebraic_summary(
    monkeypatch,
) -> None:
    individual_results = [
        _report(
            method="pc",
            src="X",
            dst="Y",
            algebraic_severity="blocker",
            violated_by_family={"ci": 1},
        ),
        _report(
            method="ges",
            src="Y",
            dst="X",
            algebraic_severity="warning",
            violated_by_family={"ci": 1},
        ),
    ]
    unified_pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.ARROW,
            )
        ],
        discovery_method="unified_consensus_pag",
    )

    monkeypatch.setattr(
        pipeline_module,
        "_run_algorithms_parallel",
        lambda **kwargs: (individual_results, {"pc": 0.5, "ges": 0.5}),
    )
    monkeypatch.setattr(
        pipeline_module,
        "_build_consensus_pag",
        lambda *args, **kwargs: (
            unified_pag,
            [
                EdgeAgreement(
                    edge_key="X|circle>arrow|Y",
                    presence_score=1.0,
                    orientation_confidence=0.5,
                    mark_src="circle",
                    mark_dst="arrow",
                    contributing_algorithms=["pc", "ges"],
                )
            ],
            {"X|Y": 1.0},
            [],
            [],
            [],
        ),
    )
    monkeypatch.setattr(
        pipeline_module,
        "_maybe_reconcile",
        lambda pag, state, params: pag,
    )

    result = pipeline_module._run_unified_discovery(_state(), params={})
    report = result["report"]

    assert report.metadata["disputed_edges"] == ["X--Y"]
    assert report.metadata["disputed_edge_count"] == 1
    assert report.metadata["disputed_edge_fraction"] == 1.0
    assert report.metadata["algebraic_violation_summary"]["blocker_reports"] == 1
    assert report.metadata["algebraic_violation_summary"]["violated_by_family"] == {
        "ci": 2
    }
    assert report.metadata["families_with_blockers"] == ["ci"]
