import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import GraphPriorBundleRef
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicAssumptionStatus,
    AlgebraicFalsificationScope,
)
from polisyos.scientist.methods.discovery.aggregator import (
    EdgeConfidenceEntry,
    EdgeConfidenceMatrix,
)
from polisyos.scientist.methods.discovery.artifact_refs import profile_bound_written_ref
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
from polisyos.scientist.methods.search.artifact_minimality import ArtifactFunction


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
    payload = from_canonical_bytes(store.get_bytes(ref))
    evidence = payload["hypothesis_identification"]["pc_main"]
    assert "graph_derived_assumption_status" in evidence
    assert evidence["graph_derived_assumption_status"] is None
    assert "graph_derived_scope_of_falsification" in evidence
    assert evidence["graph_derived_scope_of_falsification"] is None
    loaded = load_graph_prior_bundle(FileSystemCAS(store.root), ref)

    assert ref.kind == "scientist.graph_prior_bundle"
    assert loaded == bundle


def test_graph_prior_builder_and_cas_preserve_typed_candidate_scope(tmp_path) -> None:
    matrix = EdgeConfidenceMatrix(entries=[], hypothesis_weights={}, metadata={})
    score = _utility_report().scores[0].model_copy(
        update={
            "graph_derived_assumption_status": AlgebraicAssumptionStatus.UNKNOWN,
            "graph_derived_scope_of_falsification": AlgebraicFalsificationScope.RANKING_ONLY,
        }
    )
    report = _utility_report().model_copy(update={"scores": [score]})
    bundle = GraphPriorBuilder().build(matrix, report)

    evidence = bundle.hypothesis_identification["pc_main"]
    assert bundle.schema_version == "1.2"
    assert evidence.graph_derived_assumption_status is AlgebraicAssumptionStatus.UNKNOWN
    assert evidence.graph_derived_scope_of_falsification is AlgebraicFalsificationScope.RANKING_ONLY

    writer = FileSystemCAS(tmp_path / "current-priors")
    ref = persist_graph_prior_bundle(writer, bundle)
    fresh = load_graph_prior_bundle(FileSystemCAS(tmp_path / "current-priors"), ref)
    assert writer.get_manifest(ref).artifact_schema.version == "1.2"
    assert fresh.schema_version == "1.2"
    assert fresh.hypothesis_identification["pc_main"].graph_derived_scope_of_falsification is (
        AlgebraicFalsificationScope.RANKING_ONLY
    )


def test_graph_prior_v11_is_read_as_routing_only_unknown_scope(tmp_path) -> None:
    matrix = EdgeConfidenceMatrix(entries=[], hypothesis_weights={}, metadata={})
    bundle = GraphPriorBuilder().build(matrix, _utility_report())
    payload = bundle.model_dump(mode="json")
    payload["schema_version"] = "1.1"
    for evidence in payload["hypothesis_identification"].values():
        evidence.pop("graph_derived_assumption_status")
        evidence.pop("graph_derived_scope_of_falsification")

    store = FileSystemCAS(tmp_path / "historical-priors")
    raw_ref = store.put_json(
        payload,
        PutOptions(
            kind="scientist.graph_prior_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.discovery.GraphPriorBundle",
                version="1.1",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = profile_bound_written_ref(
        store,
        GraphPriorBundleRef.model_validate(raw_ref.model_dump(mode="json")),
    )
    fresh = load_graph_prior_bundle(FileSystemCAS(store.root), ref)

    assert fresh.schema_version == "1.1"
    assert fresh.artifact_functions == {ArtifactFunction.ROUTING}
    evidence = fresh.hypothesis_identification["pc_main"]
    assert evidence.graph_derived_assumption_status is AlgebraicAssumptionStatus.UNKNOWN
    assert evidence.graph_derived_scope_of_falsification is AlgebraicFalsificationScope.RANKING_ONLY


@pytest.mark.parametrize(
    ("manifest_version", "payload_version", "include_scope_fields"),
    [
        ("1.2", "1.2", False),
        ("1.1", "1.2", True),
        ("1.3", "1.3", True),
    ],
)
def test_graph_prior_loader_rejects_incomplete_or_unbound_versions(
    tmp_path, manifest_version, payload_version, include_scope_fields
) -> None:
    matrix = EdgeConfidenceMatrix(entries=[], hypothesis_weights={}, metadata={})
    payload = GraphPriorBuilder().build(matrix, _utility_report()).model_dump(mode="json")
    payload["schema_version"] = payload_version
    if not include_scope_fields:
        for evidence in payload["hypothesis_identification"].values():
            evidence.pop("graph_derived_assumption_status", None)
            evidence.pop("graph_derived_scope_of_falsification", None)

    store = FileSystemCAS(tmp_path / f"unbound-priors-{manifest_version}-{payload_version}")
    raw_ref = store.put_json(
        payload,
        PutOptions(
            kind="scientist.graph_prior_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.discovery.GraphPriorBundle",
                version=manifest_version,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = profile_bound_written_ref(
        store,
        GraphPriorBundleRef.model_validate(raw_ref.model_dump(mode="json")),
    )

    with pytest.raises(ValueError, match="schema|version|fields"):
        load_graph_prior_bundle(FileSystemCAS(store.root), ref)


def test_graph_prior_writer_rejects_forged_historical_version_before_cas(tmp_path) -> None:
    matrix = EdgeConfidenceMatrix(entries=[], hypothesis_weights={}, metadata={})
    bundle = GraphPriorBuilder().build(matrix, _utility_report())
    forged = bundle.model_copy(update={"schema_version": "1.1"})
    store = FileSystemCAS(tmp_path / "writer-rejects-legacy")

    with pytest.raises(ValueError, match="writer requires schema version 1.2"):
        persist_graph_prior_bundle(store, forged)


def test_graph_prior_writer_revalidates_nested_scope_before_cas(tmp_path) -> None:
    matrix = EdgeConfidenceMatrix(entries=[], hypothesis_weights={}, metadata={})
    score = _utility_report().scores[0].model_copy(
        update={
            "graph_derived_assumption_status": AlgebraicAssumptionStatus.UNKNOWN,
            "graph_derived_scope_of_falsification": AlgebraicFalsificationScope.RANKING_ONLY,
        }
    )
    report = _utility_report().model_copy(update={"scores": [score]})
    bundle = GraphPriorBuilder().build(matrix, report)
    evidence = bundle.hypothesis_identification["pc_main"].model_copy(
        update={"graph_derived_assumption_status": "invented_status"}
    )
    forged = bundle.model_copy(
        update={"hypothesis_identification": {"pc_main": evidence}}
    )
    store = FileSystemCAS(tmp_path / "writer-revalidates-nested-scope")

    from unittest.mock import patch

    with patch.object(store, "put_json", wraps=store.put_json) as put_json:
        with pytest.raises(ValueError, match="failed current schema validation"):
            persist_graph_prior_bundle(store, forged)

    put_json.assert_not_called()


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
