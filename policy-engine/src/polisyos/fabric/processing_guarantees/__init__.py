"""Processing guarantee contracts for Fabric batch, CDC, stream, and scale paths."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProcessingGuarantee(str, Enum):
    """Honest delivery/commit guarantee labels for Fabric execution paths."""

    BATCH_ATOMIC = "batch_atomic"
    AT_LEAST_ONCE = "at_least_once"
    AT_LEAST_ONCE_WITH_DEDUPE = "at_least_once_with_dedupe"
    EFFECTIVELY_ONCE = "effectively_once"
    EXACTLY_ONCE_NARROW = "exactly_once_narrow"
    REPLAY_ONLY = "replay_only"


class OutOfOrderHandling(str, Enum):
    """Explicit handling modes for out-of-order events."""

    WAIT = "wait"
    REORDER = "reorder"
    WATERMARK = "watermark"
    DROP = "drop"
    QUARANTINE = "quarantine"


class CDCSchemaCompatibility(str, Enum):
    """Compatibility classification for CDC/schema-change events."""

    METADATA_ONLY = "metadata_only"
    COMPATIBLE_ADDITIVE = "compatible_additive"
    INCOMPATIBLE_BREAKING = "incompatible_breaking"
    UNKNOWN = "unknown"


class BackpressureStrategy(str, Enum):
    """How a bounded runtime reacts when buffers cross limits."""

    PAUSE = "pause"
    THROTTLE = "throttle"
    SPILL_TO_DISK = "spill_to_disk"
    FAIL_CLOSED = "fail_closed"


class AtomicityProof(BaseModel):
    """Proof obligations for narrow exactly-once claims."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_offsets_committed_atomically: bool = False
    state_updates_committed_atomically: bool = False
    output_writes_committed_atomically: bool = False
    proof_refs: tuple[str, ...] = Field(default=())
    notes: str = Field(default="", max_length=1024)

    @property
    def complete(self) -> bool:
        """Return true when input, state, and output are covered by one proof."""

        return (
            self.input_offsets_committed_atomically
            and self.state_updates_committed_atomically
            and self.output_writes_committed_atomically
            and bool(self.proof_refs)
        )


class IdempotencyDedupePolicy(BaseModel):
    """Idempotency and dedupe-key policy visible in source/runtime contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    key_fields: tuple[str, ...] = ("_message_id", "message_id", "id")
    missing_key_action: Literal["hash_payload", "quarantine", "reject"] = "hash_payload"
    dedupe_window_seconds: int = Field(default=86_400, ge=0)
    max_dedupe_keys: int = Field(default=4_096, ge=1)
    replay_retention_days: int = Field(default=30, ge=0)

    @model_validator(mode="after")
    def _validate_dedupe_contract(self) -> IdempotencyDedupePolicy:
        if self.enabled and not self.key_fields:
            raise ValueError("enabled idempotency requires at least one key field")
        if self.enabled and self.dedupe_window_seconds <= 0:
            raise ValueError("enabled idempotency requires a positive dedupe window")
        return self


class OutOfOrderPolicy(BaseModel):
    """Event-time ordering policy for stream/window processing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    handling: OutOfOrderHandling = OutOfOrderHandling.WATERMARK
    timestamp_field: str = Field(default="event_time", min_length=1, max_length=128)
    max_lateness_seconds: int = Field(default=300, ge=0)
    late_event_action: OutOfOrderHandling = OutOfOrderHandling.QUARANTINE

    @model_validator(mode="after")
    def _validate_late_event_action(self) -> OutOfOrderPolicy:
        if self.late_event_action in {OutOfOrderHandling.WAIT, OutOfOrderHandling.REORDER}:
            raise ValueError("late_event_action must be drop, quarantine, or watermark")
        return self


class CDCSchemaChangePolicy(BaseModel):
    """CDC schema-change compatibility handling policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    additive_change_action: Literal["accept", "review"] = "accept"
    breaking_change_action: Literal["quarantine", "fail_closed", "review"] = "quarantine"
    metadata_only_action: Literal["accept", "review"] = "accept"
    require_lineage_impact: bool = True


class BackpressurePolicy(BaseModel):
    """Bounded runtime backpressure contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: BackpressureStrategy = BackpressureStrategy.PAUSE
    max_buffered_rows: int = Field(default=10_000, ge=1)
    max_buffered_bytes: int = Field(default=16 * 1024 * 1024, ge=1)
    pause_seconds: float = Field(default=0.01, ge=0.0)
    max_backpressure_events: int | None = Field(default=None, ge=1)


class ProcessingGuaranteeContract(BaseModel):
    """End-to-end processing guarantee contract for one Fabric path."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)

    guarantee: ProcessingGuarantee = ProcessingGuarantee.AT_LEAST_ONCE_WITH_DEDUPE
    idempotency: IdempotencyDedupePolicy = Field(default_factory=IdempotencyDedupePolicy)
    out_of_order: OutOfOrderPolicy = Field(default_factory=OutOfOrderPolicy)
    cdc_schema_changes: CDCSchemaChangePolicy = Field(default_factory=CDCSchemaChangePolicy)
    backpressure: BackpressurePolicy = Field(default_factory=BackpressurePolicy)
    atomicity_proof: AtomicityProof | None = None
    notes: str = Field(default="", max_length=2048)

    @model_validator(mode="after")
    def _validate_guarantee_claim(self) -> ProcessingGuaranteeContract:
        guarantee = ProcessingGuarantee(self.guarantee)
        if guarantee == ProcessingGuarantee.EXACTLY_ONCE_NARROW:
            if self.atomicity_proof is None or not self.atomicity_proof.complete:
                raise ValueError(
                    "exactly_once_narrow requires atomic input/state/output proof refs"
                )
        if guarantee in {
            ProcessingGuarantee.AT_LEAST_ONCE_WITH_DEDUPE,
            ProcessingGuarantee.EFFECTIVELY_ONCE,
        } and not self.idempotency.enabled:
            raise ValueError(f"{guarantee.value} requires idempotency/dedupe policy")
        if guarantee == ProcessingGuarantee.EFFECTIVELY_ONCE:
            if self.idempotency.replay_retention_days <= 0:
                raise ValueError("effectively_once requires replay retention")
        return self

    @property
    def guarantee_value(self) -> str:
        return ProcessingGuarantee(self.guarantee).value


def stream_processing_contract(
    *,
    dedupe_key_fields: tuple[str, ...] = ("_message_id", "message_id", "id"),
    max_dedupe_keys: int = 4_096,
    max_buffered_rows: int = 10_000,
    max_buffered_bytes: int = 16 * 1024 * 1024,
    pause_seconds: float = 0.01,
    out_of_order: OutOfOrderHandling = OutOfOrderHandling.WATERMARK,
) -> ProcessingGuaranteeContract:
    """Build the default honest contract for Fabric stream ingestion."""

    return ProcessingGuaranteeContract(
        guarantee=ProcessingGuarantee.AT_LEAST_ONCE_WITH_DEDUPE,
        idempotency=IdempotencyDedupePolicy(
            key_fields=dedupe_key_fields,
            max_dedupe_keys=max_dedupe_keys,
        ),
        out_of_order=OutOfOrderPolicy(handling=out_of_order),
        backpressure=BackpressurePolicy(
            max_buffered_rows=max_buffered_rows,
            max_buffered_bytes=max_buffered_bytes,
            pause_seconds=pause_seconds,
        ),
        notes=(
            "Stream offsets, checkpoints, and CAS writes are not committed in one "
            "external transaction; Fabric therefore claims at-least-once with dedupe."
        ),
    )


def batch_processing_contract() -> ProcessingGuaranteeContract:
    """Build the default contract for batch ingestion/materialization paths."""

    return ProcessingGuaranteeContract(
        guarantee=ProcessingGuarantee.BATCH_ATOMIC,
        idempotency=IdempotencyDedupePolicy(
            key_fields=("connector_id", "dataset_id", "partition_key"),
            missing_key_action="hash_payload",
            dedupe_window_seconds=86_400,
            max_dedupe_keys=16_384,
            replay_retention_days=30,
        ),
        out_of_order=OutOfOrderPolicy(handling=OutOfOrderHandling.WATERMARK),
        notes="Batch paths publish CAS/manifest outputs atomically at artifact boundaries.",
    )


def default_processing_contract_for_connector(connector_id: str) -> ProcessingGuaranteeContract:
    """Choose a conservative processing contract from a connector identifier."""

    normalized = connector_id.casefold()
    if "stream" in normalized or normalized.endswith(".jsonl"):
        return stream_processing_contract()
    return batch_processing_contract()


def classify_cdc_schema_change(
    previous_fields: tuple[str, ...],
    current_fields: tuple[str, ...],
) -> CDCSchemaCompatibility:
    """Classify one CDC/schema change using field-level compatibility semantics."""

    previous = set(previous_fields)
    current = set(current_fields)
    if previous == current:
        return CDCSchemaCompatibility.METADATA_ONLY
    if previous.issubset(current):
        return CDCSchemaCompatibility.COMPATIBLE_ADDITIVE
    if previous - current:
        return CDCSchemaCompatibility.INCOMPATIBLE_BREAKING
    return CDCSchemaCompatibility.UNKNOWN


def processing_contract_snapshot(contract: ProcessingGuaranteeContract) -> dict[str, Any]:
    """Return a JSON-friendly processing contract snapshot."""

    return _canonical_metadata_payload(contract.model_dump(mode="json"))


def _canonical_metadata_payload(value: Any) -> Any:
    """Convert floats to stable strings for cursor metadata canonical JSON."""

    if isinstance(value, float):
        return format(value, ".12g")
    if isinstance(value, dict):
        return {str(key): _canonical_metadata_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_metadata_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_canonical_metadata_payload(item) for item in value)
    return value


__all__ = [
    "AtomicityProof",
    "BackpressurePolicy",
    "BackpressureStrategy",
    "CDCSchemaChangePolicy",
    "CDCSchemaCompatibility",
    "IdempotencyDedupePolicy",
    "OutOfOrderHandling",
    "OutOfOrderPolicy",
    "ProcessingGuarantee",
    "ProcessingGuaranteeContract",
    "batch_processing_contract",
    "classify_cdc_schema_change",
    "default_processing_contract_for_connector",
    "processing_contract_snapshot",
    "stream_processing_contract",
]
