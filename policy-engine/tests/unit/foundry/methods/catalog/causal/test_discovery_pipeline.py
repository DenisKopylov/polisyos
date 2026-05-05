from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal import discovery_pipeline as pipeline_module
from polisyos.foundry.methods.catalog.causal.protocols import (
    TabularCausalDiscoveryData,
    UnifiedDiscoveryData,
)
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
    families_run: list[AlgebraicConstraintFamily] | None = None,
    blocker_conditions_met_by_family: dict[str, bool] | None = None,
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
            families_run=families_run or [AlgebraicConstraintFamily.CI],
            n_implied_constraints=1,
            n_violated_constraints=sum(violated_by_family.values()),
            tested_by_family={"ci": 1},
            violated_by_family=violated_by_family,
            blocker_conditions_met_by_family=blocker_conditions_met_by_family or {},
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
    assert report.metadata["algebraic_violation_summary"]["violated_by_family"] == {"ci": 2}
    assert report.metadata["families_with_blockers"] == ["ci"]


def test_unified_discovery_applies_regime_shift_orientations(
    monkeypatch,
) -> None:
    individual_results = [
        _report(
            method="pc",
            src="X",
            dst="Y",
            algebraic_severity="info",
            violated_by_family={},
        ),
    ]
    ambiguous_pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Z", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="unified_consensus_pag",
    )

    monkeypatch.setattr(
        pipeline_module,
        "_run_algorithms_parallel",
        lambda **kwargs: (individual_results, {"pc": 1.0}),
    )
    monkeypatch.setattr(
        pipeline_module,
        "_build_consensus_pag",
        lambda *args, **kwargs: (
            ambiguous_pag,
            [
                EdgeAgreement(
                    edge_key="X|circle>circle|Y",
                    presence_score=1.0,
                    orientation_confidence=0.5,
                    mark_src="circle",
                    mark_dst="circle",
                    contributing_algorithms=["pc"],
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

    rng = np.random.default_rng(2026)
    n = 220
    x_a = rng.normal(loc=0.0, scale=1.0, size=n)
    z_a = rng.normal(size=n)
    y_a = 2.0 * x_a
    x_b = rng.normal(loc=3.0, scale=1.0, size=n)
    z_b = rng.normal(size=n)
    y_b = 2.0 * x_b
    state = UnifiedDiscoveryData(
        data=np.column_stack(
            [
                np.concatenate([x_a, x_b]),
                np.concatenate([z_a, z_b]),
                np.concatenate([y_a, y_b]),
            ]
        ),
        variable_names=["X", "Z", "Y"],
        domain_labels=np.array(["pre"] * n + ["post"] * n),
    )

    result = pipeline_module._run_unified_discovery(
        state,
        params={
            "regime_target_cols": ["Y"],
            "regime_max_set_size": 1,
            "regime_context_exogeneity": "declared",
            "regime_baseline_covariates": ["Z"],
            "regime_selection_max_set_size": 1,
        },
    )
    report = result["report"]

    assert report.regime_shift_certificate is not None
    assert report.regime_shift_certificate.targets[0].estimated_parents == ("X",)
    assert report.metadata["regime_shift_discovery"]["applied"] is True
    assert report.metadata["regime_shift_discovery"]["constraints_applied"] is True
    assert report.metadata["regime_shift_discovery"]["forced_orientation_count"] == 1
    assert report.metadata["regime_shift_discovery"]["shift_type_label"] == (
        "structural_only_consistent"
    )
    assert report.metadata["regime_shift_discovery"]["feasibility_mode"] == "exact"
    assert report.metadata["regime_shift_discovery"]["exact_mode_possible"] is True
    assert report.metadata["regime_shift_discovery"]["exact_mode_applied"] is True
    assert report.metadata["regime_shift_discovery"]["max_candidate_parents"] == 1
    assert report.metadata["regime_shift_discovery"]["expected_test_count"] > 0
    assert (
        report.metadata["regime_shift_discovery"]["shift_type_reproducibility"]["agreement"] == 1.0
    )

    edge = next(edge for edge in report.unified_pag.edges if {edge.src, edge.dst} == {"X", "Y"})
    if edge.src == "X":
        assert edge.mark_src is EdgeMark.TAIL
        assert edge.mark_dst is EdgeMark.ARROW
    else:
        assert edge.mark_src is EdgeMark.ARROW
        assert edge.mark_dst is EdgeMark.TAIL
    assert edge.metadata["regime_shift_forced"] is True


def test_unified_discovery_blocks_regime_shift_orientations_when_pre_screen_is_ambiguous(
    monkeypatch,
) -> None:
    individual_results = [
        _report(
            method="pc",
            src="X",
            dst="Y",
            algebraic_severity="info",
            violated_by_family={},
        ),
    ]
    ambiguous_pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Z", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="unified_consensus_pag",
    )

    monkeypatch.setattr(
        pipeline_module,
        "_run_algorithms_parallel",
        lambda **kwargs: (individual_results, {"pc": 1.0}),
    )
    monkeypatch.setattr(
        pipeline_module,
        "_build_consensus_pag",
        lambda *args, **kwargs: (
            ambiguous_pag,
            [
                EdgeAgreement(
                    edge_key="X|circle>circle|Y",
                    presence_score=1.0,
                    orientation_confidence=0.5,
                    mark_src="circle",
                    mark_dst="circle",
                    contributing_algorithms=["pc"],
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

    rng = np.random.default_rng(2027)
    n = 220
    x_a = rng.normal(loc=0.0, scale=1.0, size=n)
    z_a = rng.normal(size=n)
    y_a = 2.0 * x_a + 0.08 * rng.normal(size=n)
    x_b = rng.normal(loc=3.0, scale=1.0, size=n)
    z_b = rng.normal(size=n)
    y_b = 2.0 * x_b + 0.08 * rng.normal(size=n)
    state = UnifiedDiscoveryData(
        data=np.column_stack(
            [
                np.concatenate([x_a, x_b]),
                np.concatenate([z_a, z_b]),
                np.concatenate([y_a, y_b]),
            ]
        ),
        variable_names=["X", "Z", "Y"],
        domain_labels=np.array(["pre"] * n + ["post"] * n),
    )

    result = pipeline_module._run_unified_discovery(
        state,
        params={
            "regime_target_cols": ["Y"],
            "regime_max_set_size": 1,
            "regime_context_exogeneity": "declared",
        },
    )
    report = result["report"]

    assert report.regime_shift_certificate is not None
    assert report.metadata["regime_shift_discovery"]["applied"] is True
    assert report.metadata["regime_shift_discovery"]["constraints_applied"] is False
    assert report.metadata["regime_shift_discovery"]["shift_type_label"] == "ambiguous"
    assert "regime_shift_pre_screen_blocked:ambiguous" in report.warnings

    edge = next(edge for edge in report.unified_pag.edges if {edge.src, edge.dst} == {"X", "Y"})
    assert edge.mark_src is EdgeMark.CIRCLE
    assert edge.mark_dst is EdgeMark.CIRCLE


def test_unified_discovery_surfaces_prior_track7_blockers_in_regime_shift_summary(
    monkeypatch,
) -> None:
    individual_results = [
        _report(
            method="pc",
            src="X",
            dst="Y",
            algebraic_severity="blocker",
            violated_by_family={"trek_rank": 1},
            families_run=[AlgebraicConstraintFamily.TREK_RANK],
            blocker_conditions_met_by_family={"trek_rank": True},
        ),
    ]
    ambiguous_pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Z", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="unified_consensus_pag",
    )

    monkeypatch.setattr(
        pipeline_module,
        "_run_algorithms_parallel",
        lambda **kwargs: (individual_results, {"pc": 1.0}),
    )
    monkeypatch.setattr(
        pipeline_module,
        "_build_consensus_pag",
        lambda *args, **kwargs: (
            ambiguous_pag,
            [
                EdgeAgreement(
                    edge_key="X|circle>circle|Y",
                    presence_score=1.0,
                    orientation_confidence=0.5,
                    mark_src="circle",
                    mark_dst="circle",
                    contributing_algorithms=["pc"],
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

    rng = np.random.default_rng(2028)
    n = 220
    x_a = rng.normal(loc=0.0, scale=1.0, size=n)
    z_a = rng.normal(size=n)
    y_a = 2.0 * x_a
    x_b = rng.normal(loc=3.0, scale=1.0, size=n)
    z_b = rng.normal(size=n)
    y_b = 2.0 * x_b
    state = UnifiedDiscoveryData(
        data=np.column_stack(
            [
                np.concatenate([x_a, x_b]),
                np.concatenate([z_a, z_b]),
                np.concatenate([y_a, y_b]),
            ]
        ),
        variable_names=["X", "Z", "Y"],
        domain_labels=np.array(["pre"] * n + ["post"] * n),
    )

    result = pipeline_module._run_unified_discovery(
        state,
        params={
            "regime_target_cols": ["Y"],
            "regime_max_set_size": 1,
            "regime_context_exogeneity": "declared",
            "regime_baseline_covariates": ["Z"],
            "regime_selection_max_set_size": 1,
        },
    )
    summary = result["report"].metadata["regime_shift_discovery"]

    assert summary["applied"] is True
    assert summary["feasibility_mode"] == "partial"
    assert summary["exact_mode_possible"] is False
    assert summary["track7_prior_blocker_families"] == ["trek_rank"]
    assert "track7_prior_blocker_conflict:trek_rank" in (
        summary["feasibility_fallback_reason"] or ""
    )
