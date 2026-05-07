import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.discovery.aggregator import EdgeConfidenceEntry, EdgeConfidenceMatrix
from polisyos.scientist.methods.discovery.priors import (
    GraphPriorBuilder,
    GraphPriorBundle,
    PriorEdge,
    load_graph_prior_bundle,
    persist_graph_prior_bundle,
)
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)


def _utility_report() -> DownstreamUtilityReport:
    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="pc_main",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=0.8,
                composite_score=0.9,
            )
        ]
    )


def test_graph_prior_builder_applies_thresholds_and_provenance_downgrade() -> None:
    matrix = EdgeConfidenceMatrix(
        entries=[
            EdgeConfidenceEntry(
                skeleton_key="X--Y",
                edge_key="X->Y",
                src="X",
                dst="Y",
                presence_confidence=0.90,
                orientation_confidence=0.85,
                directional_support={"X->Y": 0.95, "Y->X": 0.05},
                orientation_support={"X|tail>arrow|Y": 0.85},
                supporting_hypothesis_ids=["pc_main"],
                supporting_families=["constraint_based"],
                provenance_refs=[],
                disputed=False,
            ),
            EdgeConfidenceEntry(
                skeleton_key="A--B",
                edge_key="A->B",
                src="A",
                dst="B",
                presence_confidence=0.88,
                orientation_confidence=0.82,
                directional_support={"A->B": 0.90, "B->A": 0.10},
                orientation_support={"A|tail>arrow|B": 0.82},
                supporting_hypothesis_ids=["pc_main"],
                supporting_families=["constraint_based"],
                provenance_refs=["paper:1"],
                disputed=False,
            ),
        ],
        hypothesis_weights={"pc_main": 1.0},
        metadata={"equivalence_class_summary": {"unresolved_disputes": []}},
    )

    bundle = GraphPriorBuilder().build(matrix, _utility_report())

    assert [edge.edge_key for edge in bundle.required_edges] == ["A->B"]
    assert sorted(edge.edge_key for edge in bundle.high_confidence_edges) == ["A->B", "X->Y"]
    assert "required_edge_downgraded_without_provenance:X->Y" in bundle.warnings
    assert [edge.edge_key for edge in bundle.forbidden_edges] == ["B->A", "Y->X"]
    assert bundle.downstream_utility_scores["pc_main"] == 0.9


def test_graph_prior_bundle_round_trip_preserves_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    matrix = EdgeConfidenceMatrix(
        entries=[],
        hypothesis_weights={},
        metadata={"equivalence_class_summary": {"graph_type_counts": {"dag": 1}}},
    )
    bundle = GraphPriorBuilder().build(matrix, _utility_report())

    ref = persist_graph_prior_bundle(store, bundle)
    loaded = load_graph_prior_bundle(store, ref)

    assert ref.kind == "scientist.graph_prior_bundle"
    assert loaded == bundle


def test_graph_prior_bundle_rejects_required_edges_without_provenance() -> None:
    with pytest.raises(ValueError, match="must carry provenance_refs"):
        GraphPriorBundle(
            required_edges=[
                PriorEdge(
                    edge_key="X->Y",
                    src="X",
                    dst="Y",
                    presence_confidence=0.9,
                    orientation_confidence=0.9,
                )
            ]
        )
