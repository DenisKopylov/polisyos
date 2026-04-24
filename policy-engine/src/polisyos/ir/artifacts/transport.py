"""Transport contracts for JSON-first, binary sidecar, and incremental IR delivery."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts.contracts import ArtifactID

if TYPE_CHECKING:
    from datetime import datetime

    from polisyos.ir.observation.contracts import ObservationFamily, ObservationRecord
else:
    from datetime import datetime

    from polisyos.ir.observation.contracts import ObservationFamily, ObservationRecord

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class TransportMode(str, Enum):
    """Classify whether a family is JSON-only or supports optional binary transport."""

    JSON_FIRST = "json_first"
    OPTIONAL_BINARY = "optional_binary"


class BinaryWireFormat(str, Enum):
    """Enumerate candidate binary wire formats considered by the IR transport layer."""

    PROTOBUF = "protobuf"
    MSGPACK = "msgpack"
    ARROW_IPC_STREAM = "arrow_ipc_stream"
    FLATBUFFERS = "flatbuffers"


class DeltaSemantics(str, Enum):
    """Describe how a delta artifact should be interpreted against its base payload."""

    APPEND_ONLY = "append_only"
    UPSERT = "upsert"
    FULL_REPLACE = "full_replace"


class StreamUpdateOperation(str, Enum):
    """Declare whether a streaming update inserts or retracts an observation."""

    UPSERT = "upsert"
    RETRACT = "retract"


class TransportDescriptor(BaseModel):
    """Document the transport contract for one IR payload family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    family: str = Field(min_length=1)
    mode: TransportMode
    json_media_type: str = Field(default="application/json", min_length=1)
    binary_media_type: str | None = None
    wire_format: BinaryWireFormat | None = None
    canonical_manifest_required: bool = True
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_descriptor(self) -> TransportDescriptor:
        if self.mode is TransportMode.OPTIONAL_BINARY:
            if self.binary_media_type is None or self.wire_format is None:
                raise ValueError(
                    "optional binary transport requires binary_media_type and wire_format"
                )
        return self


class ArtifactDeltaEntry(BaseModel):
    """One logical delta item applied against a base artifact family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_key: str = Field(min_length=1)
    operation: StreamUpdateOperation
    payload_artifact_id: ArtifactID | None = None
    payload_offset: int | None = Field(default=None, ge=0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_delta_entry(self) -> ArtifactDeltaEntry:
        if self.operation is StreamUpdateOperation.UPSERT and self.payload_artifact_id is None:
            raise ValueError("upsert delta entries require payload_artifact_id")
        return self


class ArtifactDeltaEnvelope(BaseModel):
    """Generic delta envelope for incremental IR artifact refresh."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    family: str = Field(min_length=1)
    base_artifact_id: ArtifactID | None = None
    semantics: DeltaSemantics = DeltaSemantics.UPSERT
    entries: list[ArtifactDeltaEntry] = Field(default_factory=list)
    emitted_at: datetime
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_delta_envelope(self) -> ArtifactDeltaEnvelope:
        if not self.entries:
            raise ValueError("ArtifactDeltaEnvelope requires at least one delta entry")
        if self.semantics is not DeltaSemantics.APPEND_ONLY and self.base_artifact_id is None:
            raise ValueError("base_artifact_id is required for non-append-only delta semantics")
        return self


class IncrementalRelinkManifest(BaseModel):
    """Describe which linker surfaces must be re-evaluated after a delta lands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    bundle_artifact_id: ArtifactID
    delta_artifact_id: ArtifactID | None = None
    affected_slots: list[str] = Field(default_factory=list)
    affected_mechanisms: list[str] = Field(default_factory=list)
    affected_constraints: list[str] = Field(default_factory=list)
    affected_queries: list[str] = Field(default_factory=list)
    requires_full_relink: bool = False
    notes: list[str] = Field(default_factory=list)


class ObservationBinaryBatchArtifact(BaseModel):
    """Pilot binary sidecar contract for large observation-record batches."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    batch_id: str = Field(min_length=1)
    family: ObservationFamily
    record_count: int = Field(ge=1)
    field_names: list[str] = Field(min_length=1)
    binary_artifact_id: ArtifactID
    binary_media_type: str = Field(
        default="application/vnd.apache.arrow.stream",
        min_length=1,
    )
    wire_format: BinaryWireFormat = BinaryWireFormat.ARROW_IPC_STREAM
    delta_semantics: DeltaSemantics = DeltaSemantics.APPEND_ONLY
    base_artifact_id: ArtifactID | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_binary_batch(self) -> ObservationBinaryBatchArtifact:
        if self.delta_semantics is not DeltaSemantics.APPEND_ONLY and self.base_artifact_id is None:
            raise ValueError("base_artifact_id is required when binary batch is emitted as a delta")
        return self


class ObservationStreamCheckpoint(BaseModel):
    """Stable resume point for observation-heavy streaming ingestion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    stream_id: str = Field(min_length=1)
    cursor: int = Field(ge=0)
    checkpoint_artifact_id: ArtifactID
    emitted_at: datetime
    notes: list[str] = Field(default_factory=list)


class ObservationStreamEntry(BaseModel):
    """One logical observation update emitted by a streaming source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence_no: int = Field(ge=0)
    operation: StreamUpdateOperation
    record: ObservationRecord | None = None
    prior_artifact_id: ArtifactID | None = None

    @model_validator(mode="after")
    def validate_stream_entry(self) -> ObservationStreamEntry:
        if self.operation is StreamUpdateOperation.UPSERT and self.record is None:
            raise ValueError("upsert stream entries require a record payload")
        if self.operation is StreamUpdateOperation.RETRACT and self.record is None:
            if self.prior_artifact_id is None:
                raise ValueError("retract stream entries require record or prior_artifact_id")
        return self


class ObservationStreamUpdate(BaseModel):
    """Streaming update envelope for observation ingestion with optional Arrow sidecars."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    stream_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    sequence_start: int = Field(ge=0)
    sequence_end: int = Field(ge=0)
    entries: list[ObservationStreamEntry] = Field(default_factory=list)
    binary_batch: ObservationBinaryBatchArtifact | None = None
    delta: ArtifactDeltaEnvelope | None = None
    checkpoint: ObservationStreamCheckpoint | None = None
    relink_manifest: IncrementalRelinkManifest | None = None
    emitted_at: datetime
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_update(self) -> ObservationStreamUpdate:
        if self.sequence_end < self.sequence_start:
            raise ValueError("sequence_end must be >= sequence_start")
        if not self.entries and self.binary_batch is None and self.delta is None:
            raise ValueError("ObservationStreamUpdate requires entries, binary_batch, or delta")
        return self


OBSERVATION_STREAM_TRANSPORT = TransportDescriptor(
    family="observation_record_batch",
    mode=TransportMode.OPTIONAL_BINARY,
    binary_media_type="application/vnd.apache.arrow.stream",
    wire_format=BinaryWireFormat.ARROW_IPC_STREAM,
    notes=[
        "Canonical manifest remains JSON-first.",
        "Large observation payloads may travel as Arrow IPC sidecars referenced by artifact id.",
    ],
)


__all__ = [
    "OBSERVATION_STREAM_TRANSPORT",
    "ArtifactDeltaEntry",
    "ArtifactDeltaEnvelope",
    "BinaryWireFormat",
    "DeltaSemantics",
    "IncrementalRelinkManifest",
    "ObservationBinaryBatchArtifact",
    "ObservationStreamCheckpoint",
    "ObservationStreamEntry",
    "ObservationStreamUpdate",
    "StreamUpdateOperation",
    "TransportDescriptor",
    "TransportMode",
]
