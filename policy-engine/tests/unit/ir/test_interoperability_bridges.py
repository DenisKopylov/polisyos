from __future__ import annotations

from datetime import UTC, date, datetime

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.ecosystem_bridges import (
    CausalBridgeTarget,
    to_causalnex_graph_bridge,
    to_dowhy_graph_bridge,
    to_econml_design_bridge,
    to_pgmpy_graph_bridge,
    to_tigramite_pcmci_bridge,
)
from polisyos.ir.artifacts import (
    OBSERVATION_STREAM_TRANSPORT,
    ArtifactDeltaEntry,
    ArtifactDeltaEnvelope,
    ArtifactID,
    DeltaSemantics,
    IncrementalRelinkManifest,
    ObservationBinaryBatchArtifact,
    ObservationStreamCheckpoint,
    ObservationStreamEntry,
    ObservationStreamUpdate,
    StreamUpdateOperation,
)
from polisyos.ir.observation.bridges import (
    bridge_observation_panel_to_cdisc,
    bridge_observation_record_to_ddi,
    bridge_observation_record_to_fhir,
    bridge_observation_record_to_sdmx,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.ir.types import TimeFrequency
from polisyos.ir.world.event import (
    EventKind,
    ProvActivity,
    ProvActivityType,
    ProvAgent,
    ProvAgentType,
    WorldEvent,
    WorldObjectRef,
)
from polisyos.ir.world.prov_o import ProvORelationType, to_prov_o_world_event


def _artifact_id(char: str) -> ArtifactID:
    return ArtifactID.from_sha256_hex(char * 64)


def _observation_record() -> ObservationRecord:
    return ObservationRecord(
        observation_id="obs.demo",
        family=ObservationFamily.LABOR_MARKET,
        time_grain=TimeFrequency.MONTH,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        entity_scope=EntityScope.REGION,
        region_code="UA-30",
        metric_id="employment_rate",
        observed_value=0.61,
        unit="ratio",
        coverage_estimate=0.82,
        trust_weight=0.9,
        source_id="labor_registry",
        source_version="2025.01",
        regime_id="baseline",
        schema_regime_id="schema_v1",
        identification_mode=IdentificationMode.POINT_IDENTIFIED,
        source_confidence_tier=SourceConfidenceTier.CORE,
    )


def test_observation_standard_bridges_cover_sdmx_ddi_fhir_and_cdisc() -> None:
    record = _observation_record()
    panel = ObservationPanel(
        panel_id="panel.demo",
        family=record.family,
        time_grain=record.time_grain,
        records=[record],
    )

    sdmx = bridge_observation_record_to_sdmx(record, dataset_id="labor.market")
    ddi = bridge_observation_record_to_ddi(record)
    fhir = bridge_observation_record_to_fhir(record)
    cdisc = bridge_observation_panel_to_cdisc(panel)

    assert sdmx.series_key["METRIC"] == "employment_rate"
    assert ddi.variable_name == "employment_rate"
    assert fhir.resource_type == "Observation"
    assert fhir.subject_reference.endswith("/UA-30")
    assert cdisc.row_count == 1
    assert "OBSERVATION_ID" in cdisc.variable_names


def test_transport_contracts_cover_binary_delta_and_streaming_relink() -> None:
    record = _observation_record()
    binary_batch = ObservationBinaryBatchArtifact(
        batch_id="batch-001",
        family=record.family,
        record_count=1,
        field_names=["observation_id", "metric_id", "observed_value"],
        binary_artifact_id=_artifact_id("a"),
    )
    delta = ArtifactDeltaEnvelope(
        family="observation_record_batch",
        semantics=DeltaSemantics.APPEND_ONLY,
        entries=[
            ArtifactDeltaEntry(
                entity_key=record.observation_id,
                operation=StreamUpdateOperation.UPSERT,
                payload_artifact_id=_artifact_id("b"),
            )
        ],
        emitted_at=datetime(2026, 4, 13, 9, 0, tzinfo=UTC),
    )
    relink = IncrementalRelinkManifest(
        bundle_artifact_id=_artifact_id("c"),
        delta_artifact_id=_artifact_id("d"),
        affected_slots=["slot.employment"],
        affected_queries=["query.labor_market"],
    )
    checkpoint = ObservationStreamCheckpoint(
        stream_id="stream.demo",
        cursor=42,
        checkpoint_artifact_id=_artifact_id("e"),
        emitted_at=datetime(2026, 4, 13, 9, 1, tzinfo=UTC),
    )
    update = ObservationStreamUpdate(
        stream_id="stream.demo",
        chunk_id="chunk-042",
        sequence_start=42,
        sequence_end=42,
        entries=[
            ObservationStreamEntry(
                sequence_no=42,
                operation=StreamUpdateOperation.UPSERT,
                record=record,
            )
        ],
        binary_batch=binary_batch,
        delta=delta,
        checkpoint=checkpoint,
        relink_manifest=relink,
        emitted_at=datetime(2026, 4, 13, 9, 2, tzinfo=UTC),
    )

    assert update.binary_batch == binary_batch
    assert update.relink_manifest == relink
    assert OBSERVATION_STREAM_TRANSPORT.mode.value == "optional_binary"
    assert OBSERVATION_STREAM_TRANSPORT.wire_format.value == "arrow_ipc_stream"


def test_prov_o_mapping_preserves_activity_and_entity_relations() -> None:
    event = WorldEvent(
        event_id="event.demo",
        event_kind=EventKind.INGEST_DATASET,
        agent=ProvAgent(
            agent_id="agent.demo",
            agent_type=ProvAgentType.CONNECTOR,
            label="Labor connector",
        ),
        activity=ProvActivity(
            activity_id="activity.demo",
            activity_type=ProvActivityType.INGEST_DATASET,
            label="Ingest labor dataset",
            started_at=datetime(2026, 4, 13, 8, 0, tzinfo=UTC),
            ended_at=datetime(2026, 4, 13, 8, 0, 30, tzinfo=UTC),
        ),
        inputs=[WorldObjectRef(artifact_id=str(_artifact_id("1")))],
        outputs=[WorldObjectRef(world_id="claim.demo")],
    )

    document = to_prov_o_world_event(event)
    relation_types = {relation.relation for relation in document.relations}
    jsonld = document.to_jsonld()

    assert ProvORelationType.USED in relation_types
    assert ProvORelationType.WAS_GENERATED_BY in relation_types
    assert document.activities[0].duration_seconds == 30.0
    assert jsonld["@context"] == "https://www.w3.org/ns/prov#"


def test_causal_ecosystem_bridges_cover_dowhy_econml_causalnex_pgmpy_and_tigramite() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "T", "Y", "Z"],
        edges=[
            CausalEdge(src="X", dst="T", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="T", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW, lag=1),
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )

    dowhy = to_dowhy_graph_bridge(
        graph,
        treatment="T",
        outcome="Y",
        common_causes=["X"],
        effect_modifiers=["Z"],
    )
    econml = to_econml_design_bridge(
        graph,
        treatment="T",
        outcome="Y",
        effect_modifiers=["Z"],
    )
    causalnex = to_causalnex_graph_bridge(graph)
    pgmpy = to_pgmpy_graph_bridge(graph)
    tigramite = to_tigramite_pcmci_bridge(graph)

    assert dowhy.target is CausalBridgeTarget.DOWHY
    assert '"T" -> "Y"' in dowhy.graph_dot
    assert econml.treatment == "T"
    assert "X" in econml.confounders
    assert ("X", "T") in causalnex.directed_edges
    assert ("Z", "Y") in pgmpy.directed_edges
    assert tigramite.max_lag == 1
    assert any(
        edge.lag == 1 and edge.src == "T" and edge.dst == "Y" for edge in tigramite.lagged_edges
    )
