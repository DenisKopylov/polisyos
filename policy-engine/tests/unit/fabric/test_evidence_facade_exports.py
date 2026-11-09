from __future__ import annotations

import importlib

from polisyos.runtime.quality import confidence_ledger as ledger

_LEGACY_PUBLIC_NAMES = frozenset(
    {
        "AccessRef",
        "Any",
        "ArtifactID",
        "ArtifactRef",
        "AuthoredText",
        "CanonInfo",
        "CanonSpec",
        "DataClassification",
        "Decimal",
        "DecisionDataKind",
        "EvidenceBundle",
        "EvidenceBundleRef",
        "EvidencePayloadError",
        "EvidenceStep",
        "FabricDecisionData",
        "FabricDecisionDataCoverage",
        "FabricDecisionDataResponse",
        "FabricQuantityValue",
        "Fact",
        "FactLegal",
        "FactProvenance",
        "FactSegmentManifest",
        "FactTrust",
        "FileSystemCAS",
        "IngestionExecutionContext",
        "InputRef",
        "LineageRef",
        "LineageStatus",
        "ProvenanceCoreGraph",
        "ProvenanceCoreRef",
        "ProvenanceCoreRefModel",
        "PutOptions",
        "QualityRef",
        "QualityStatus",
        "ReplayRef",
        "ReplayStatus",
        "RetentionScope",
        "SchemaInfo",
        "SourceContractRef",
        "TYPE_CHECKING",
        "TemporalRef",
        "TypedGap",
        "TypedGapState",
        "UnitRef",
        "access_ref_from_source_field_policy",
        "annotations",
        "artifact_manifest_profile_projection",
        "artifact_manifest_profile_sha256",
        "build_composite_evidence_bundle",
        "build_evidence_bundle",
        "build_fact",
        "build_fact_id",
        "content_hash",
        "coverage_from_decision_data",
        "decision_data",
        "evidence",
        "evidence_bundle_manifest_input_refs",
        "expected_artifact_manifest_for_write",
        "fabric_claim_to_authored_text",
        "fabric_event_to_authored_text",
        "fabric_fact_to_quantity_value",
        "fact_writer",
        "facts_from_dataframe",
        "from_canonical_bytes",
        "from_runtime_quantities",
        "from_runtime_quantity",
        "hashlib",
        "input_ref_from_artifact_ref",
        "json",
        "load_provenance_graph",
        "pd",
        "persist_evidence_bundle",
        "persist_provenance_graph",
        "resolve_artifact_governance",
        "time",
        "to_canonical_bytes",
        "to_runtime_quantity_value",
        "utc_tx_time",
        "verify_live_ingestion_evidence_profile",
        "write_fact_segment",
        "write_segment_manifest",
    }
)


def test_evidence_facade_preserves_legacy_namespace_and_exact_owner() -> None:
    facade = importlib.import_module("polisyos.fabric.evidence")
    providers = tuple(
        importlib.import_module(name)
        for name in (
            "polisyos.fabric.evidence.decision_data",
            "polisyos.fabric.evidence.evidence",
            "polisyos.fabric.evidence.fact_writer",
        )
    )

    expected: dict[str, object] = {}
    for provider in providers:
        export_names = getattr(provider, "__all__", None)
        names = (
            export_names
            if export_names is not None
            else (name for name in vars(provider) if not name.startswith("_"))
        )
        expected.update({name: getattr(provider, name) for name in names})
    expected.update({provider.__name__.rsplit(".", 1)[-1]: provider for provider in providers})

    assert not hasattr(facade, "__all__")
    assert {name for name in vars(facade) if not name.startswith("_")} == _LEGACY_PUBLIC_NAMES
    assert set(expected) == _LEGACY_PUBLIC_NAMES
    for name, owner_value in expected.items():
        assert getattr(facade, name) is owner_value

    evidence = providers[1]
    assert facade.persist_provenance_graph is evidence.persist_provenance_graph
    assert facade.persist_provenance_graph is not evidence.load_provenance_graph

    consumer = importlib.import_module("polisyos.fabric.connectors.federation.evidence_aggregation")
    assert consumer.persist_provenance_graph is evidence.persist_provenance_graph

    root = ledger._loaded_policy_engine_root()
    candidate = ledger._source_module_import_route_candidate(
        root,
        facade.__name__,
        "persist_provenance_graph",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert candidate.route == ("symbol", evidence.__name__, "persist_provenance_graph")
    assert candidate.binding_basis == "direct"
