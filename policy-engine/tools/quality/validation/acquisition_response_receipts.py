"""Typed response classification and R1 forensic receipt owners."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactID, FileSystemCAS
from polisyos.fabric.data_plane import (
    JournalEventRef,
    canonical_json_bytes,
    content_sha256,
    resolve_journal_event_ref,
    resolve_live_attempt_terminals,
    resolve_raw_response_body,
)

DEFAULT_R1_FORENSIC_RECEIPT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_r1_forensic_receipt.json"
)


class CarrierDataDisposition(StrEnum):
    """Typed R1 outcome recomputed only from paid response bytes."""

    CARRIER_RETIRED_OR_INVALID = "carrier_retired_or_invalid"
    NO_DATA_FOR_SCOPE = "no_data_for_scope"
    RESPONSE_SHAPE_UNCLASSIFIED = "response_shape_unclassified"


class IndicatorMetadataDisposition(StrEnum):
    """Typed exact-indicator disposition derived after metadata journaling."""

    CARRIER_CURRENT = "carrier_current"
    CARRIER_RETIRED_OR_INVALID = "carrier_retired_or_invalid"
    RESPONSE_SHAPE_UNCLASSIFIED = "response_shape_unclassified"


class AcquisitionSelectionError(RuntimeError):
    """Typed refusal raised when source evidence cannot select one live carrier."""

    def __init__(
        self,
        code: str,
        detail: str | None = None,
        *,
        reason: str | None = None,
    ) -> None:
        self.code = code
        self.detail = detail or code
        self.reason = reason
        suffix = f"/{reason}" if reason is not None else ""
        super().__init__(f"{code}{suffix}: {self.detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorldBankDataResponseClassification(_StrictModel):
    """R1 response classification bound to exact immutable bytes."""

    body_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    disposition: CarrierDataDisposition
    row_count: int | None = Field(default=None, ge=0)
    api_message_count: int = Field(ge=0)


class WorldBankIndicatorMetadataClassification(_StrictModel):
    """Current/retired metadata result with only owner-declared fields."""

    body_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    disposition: IndicatorMetadataDisposition
    indicator_id: str = Field(min_length=1)
    source_id: str | None = None
    source_name: str | None = None
    unit: str | None = None
    coverage_start: str | None = None
    coverage_end: str | None = None
    declared_coverage: str = Field(min_length=1)
    api_message_count: int = Field(ge=0)


class R1AttemptForensicProjection(_StrictModel):
    """Narrow verified projection of one already-paid data attempt."""

    attempt_id: str = Field(min_length=1)
    request_sequence: int = Field(ge=1)
    request_event_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_dataset_id: str = Field(min_length=1)
    terminal_event_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    terminal_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    terminal_outcome: str = Field(min_length=1)
    terminal_failure_code: str = Field(min_length=1)
    raw_evidence_event_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    raw_body_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    raw_byte_count: int | None = Field(default=None, ge=0)
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    max_elapsed_seconds: float = Field(ge=0.0)
    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _attempt_projection_is_recomputed(self) -> Self:
        raw_values = (
            self.raw_evidence_event_sha256,
            self.raw_body_sha256,
            self.raw_byte_count,
        )
        if any(value is None for value in raw_values) != all(value is None for value in raw_values):
            raise ValueError("R1 raw evidence projection must be complete or absent")
        if self.http_status_code is not None and self.raw_body_sha256 is None:
            raise ValueError("R1 HTTP status requires raw evidence")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("R1 attempt projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the exact attempt projection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class R1ForensicReceipt(_StrictModel):
    """E10 receipt binding the paid journal prefix, CAS bytes, and R1 class."""

    schema_version: Literal[
        "policyos.layer3.gy.n13b.r1_forensics.v1",
        "policyos.layer3.gy.n13b.r1_forensics.v2",
    ] = "policyos.layer3.gy.n13b.r1_forensics.v1"
    journal_ref: str = Field(min_length=1)
    journal_prefix_byte_length: int = Field(gt=0)
    journal_prefix_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cas_blob_ref: str = Field(min_length=1)
    cas_manifest_ref: str = Field(min_length=1)
    cas_blob_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_dataset_id: str = Field(min_length=1)
    attempts: tuple[R1AttemptForensicProjection, ...] = Field(min_length=1)
    decisive_attempt_id: str = Field(min_length=1)
    classification: WorldBankDataResponseClassification
    cas_manifest_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _receipt_is_recomputed(self) -> Self:
        attempt_ids = tuple(attempt.attempt_id for attempt in self.attempts)
        if len(attempt_ids) != len(set(attempt_ids)):
            raise ValueError("R1 attempt denominator must be unique")
        if tuple(attempt.request_sequence for attempt in self.attempts) != tuple(
            sorted(attempt.request_sequence for attempt in self.attempts)
        ):
            raise ValueError("R1 attempts must preserve journal order")
        decisive = tuple(
            attempt for attempt in self.attempts if attempt.attempt_id == self.decisive_attempt_id
        )
        if (
            len(decisive) != 1
            or decisive[0].raw_body_sha256 != self.classification.body_sha256
            or decisive[0].raw_byte_count != self.classification.byte_count
            or self.cas_blob_sha256 != self.classification.body_sha256
        ):
            raise ValueError("R1 decisive bytes must bind journal, CAS, and classification")
        if self.schema_version == "policyos.layer3.gy.n13b.r1_forensics.v1":
            if self.cas_manifest_sha256 is not None:
                raise ValueError("historical R1 v1 projection cannot add manifest fields")
        elif (
            self.cas_blob_ref != f"cas://sha256/{self.cas_blob_sha256.removeprefix('sha256:')}/blob"
            or self.cas_manifest_ref
            != f"cas://sha256/{self.cas_blob_sha256.removeprefix('sha256:')}/manifest/default"
            or self.cas_manifest_sha256 is None
        ):
            raise ValueError("R1 v2 must bind logical CAS locators and exact manifest bytes")
        if any(attempt.request_dataset_id != self.request_dataset_id for attempt in self.attempts):
            raise ValueError("R1 attempt denominator must preserve the exact carrier")
        if self.receipt_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("R1 forensic receipt identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the immutable forensic projection without its self-hash."""

        payload = self.model_dump(mode="json")
        payload.pop("receipt_sha256")
        if self.schema_version == "policyos.layer3.gy.n13b.r1_forensics.v1":
            # Keep the historical v1 hashed projection byte-for-byte replayable.
            payload.pop("cas_manifest_sha256")
        return payload


def classify_worldbank_data_response(body: bytes) -> WorldBankDataResponseClassification:
    """Classify paid World Bank data bytes into the exact R1 vocabulary."""

    body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    messages = _worldbank_api_messages(payload)
    disposition = CarrierDataDisposition.RESPONSE_SHAPE_UNCLASSIFIED
    row_count: int | None = None
    if messages:
        disposition = CarrierDataDisposition.CARRIER_RETIRED_OR_INVALID
    elif (
        isinstance(payload, list)
        and len(payload) == 2
        and isinstance(payload[0], Mapping)
        and _nonbool_int(payload[0].get("total")) == 0
        and payload[1] is None
    ):
        disposition = CarrierDataDisposition.NO_DATA_FOR_SCOPE
        row_count = 0
    return WorldBankDataResponseClassification(
        body_sha256=body_sha,
        byte_count=len(body),
        disposition=disposition,
        row_count=row_count,
        api_message_count=len(messages),
    )


def classify_worldbank_indicator_metadata(
    body: bytes,
    *,
    indicator_id: str,
) -> WorldBankIndicatorMetadataClassification:
    """Classify an exact metadata response without inferring missing coverage."""

    requested = str(indicator_id).strip()
    if not requested:
        raise AcquisitionSelectionError("metadata_indicator_id_missing")
    body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    messages = _worldbank_api_messages(payload)
    disposition = IndicatorMetadataDisposition.RESPONSE_SHAPE_UNCLASSIFIED
    record: Mapping[str, object] | None = None
    if messages:
        disposition = IndicatorMetadataDisposition.CARRIER_RETIRED_OR_INVALID
    elif isinstance(payload, list) and len(payload) == 2 and isinstance(payload[0], Mapping):
        total = _nonbool_int(payload[0].get("total"))
        rows = payload[1]
        if total == 0 and rows in (None, []):
            disposition = IndicatorMetadataDisposition.CARRIER_RETIRED_OR_INVALID
        elif total == 1 and isinstance(rows, list) and len(rows) == 1:
            candidate = rows[0]
            if isinstance(candidate, Mapping) and candidate.get("id") == requested:
                disposition = IndicatorMetadataDisposition.CARRIER_CURRENT
                record = candidate
    source = record.get("source") if record is not None else None
    source_mapping = source if isinstance(source, Mapping) else {}
    coverage_start = _optional_owner_string(record, "coverageStart", "coverage_start")
    coverage_end = _optional_owner_string(record, "coverageEnd", "coverage_end")
    declared_coverage = (
        f"{coverage_start or 'open'}:{coverage_end or 'open'}"
        if coverage_start is not None or coverage_end is not None
        else "not_declared_by_indicator_metadata_endpoint"
    )
    return WorldBankIndicatorMetadataClassification(
        body_sha256=body_sha,
        byte_count=len(body),
        disposition=disposition,
        indicator_id=requested,
        source_id=_optional_string(source_mapping.get("id")),
        source_name=_optional_string(source_mapping.get("value")),
        unit=_optional_string(record.get("unit")) if record is not None else None,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        declared_coverage=declared_coverage,
        api_message_count=len(messages),
    )


def derive_r1_forensic_receipt(
    *,
    journal_path: Path,
    cas_root: Path,
    request_dataset_id: str,
) -> R1ForensicReceipt:
    """Reopen the already-paid data attempts and bind decisive bytes to CAS."""

    journal_path = Path(journal_path)
    cas_root = Path(cas_root)
    terminals = {
        terminal.attempt_id: terminal for terminal in resolve_live_attempt_terminals(journal_path)
    }
    records = _canonical_journal_projection(journal_path)
    metadata_cutoffs = tuple(
        ref.sequence
        for ref, event, _payload in records
        if event.get("event_kind") == "request"
        and isinstance(event.get("request"), Mapping)
        and event["request"].get("call_class") == "indicator_metadata"
    )
    cutoff = min(metadata_cutoffs, default=10**18)
    request_records = tuple(
        (ref, event)
        for ref, event, _payload in records
        if ref.sequence < cutoff
        and event.get("event_kind") == "request"
        and isinstance(event.get("request"), Mapping)
        and event["request"].get("request_dataset_id") == request_dataset_id
        and event["request"].get("call_class", "data_fetch") == "data_fetch"
    )
    if not request_records:
        raise AcquisitionSelectionError("r1_data_attempt_denominator_empty", request_dataset_id)
    terminal_event_by_attempt = {
        str(event.get("attempt_id")): (ref, event)
        for ref, event, _payload in records
        if event.get("event_kind") == "live_attempt_terminal"
    }
    projections: list[R1AttemptForensicProjection] = []
    classified_bodies: list[tuple[str, bytes, WorldBankDataResponseClassification]] = []
    terminal_end_offsets: list[int] = []
    for request_ref, request_event in request_records:
        attempt_id = str(request_event.get("attempt_id") or "")
        terminal = terminals.get(attempt_id)
        terminal_event = terminal_event_by_attempt.get(attempt_id)
        if terminal is None or terminal_event is None:
            raise AcquisitionSelectionError("r1_attempt_terminal_unresolved", attempt_id)
        terminal_ref, terminal_payload = terminal_event
        terminal_end_offsets.append(terminal_ref.byte_offset + terminal_ref.byte_length)
        heartbeat_elapsed = tuple(
            float(event["heartbeat"]["elapsed_seconds"])
            for _ref, event, _payload in records
            if event.get("attempt_id") == attempt_id
            and event.get("event_kind") == "heartbeat"
            and isinstance(event.get("heartbeat"), Mapping)
            and isinstance(event["heartbeat"].get("elapsed_seconds"), (int, float))
            and not isinstance(event["heartbeat"].get("elapsed_seconds"), bool)
        )
        raw_body: bytes | None = None
        raw_body_sha: str | None = None
        raw_byte_count: int | None = None
        if terminal.raw_evidence_ref is not None:
            raw_body = resolve_raw_response_body(terminal.raw_evidence_ref)
            raw_body_sha = f"sha256:{hashlib.sha256(raw_body).hexdigest()}"
            raw_byte_count = len(raw_body)
            classified_bodies.append(
                (attempt_id, raw_body, classify_worldbank_data_response(raw_body))
            )
        values: dict[str, object] = {
            "attempt_id": attempt_id,
            "request_sequence": request_ref.sequence,
            "request_event_sha256": request_ref.event_sha256,
            "request_dataset_id": request_dataset_id,
            "terminal_event_sha256": terminal_ref.event_sha256,
            "terminal_sha256": terminal.terminal_sha256,
            "terminal_outcome": terminal.outcome_code,
            "terminal_failure_code": terminal.failure_code,
            "raw_evidence_event_sha256": (
                terminal.raw_evidence_ref.event_sha256
                if terminal.raw_evidence_ref is not None
                else None
            ),
            "raw_body_sha256": raw_body_sha,
            "raw_byte_count": raw_byte_count,
            "http_status_code": terminal.http_status_code,
            "max_elapsed_seconds": max(heartbeat_elapsed, default=0.0),
        }
        projections.append(
            R1AttemptForensicProjection(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
        if terminal_payload.get("terminal_sha256") != terminal.terminal_sha256:
            raise AcquisitionSelectionError("r1_terminal_projection_drift", attempt_id)
    decisive = tuple(
        item
        for item in classified_bodies
        if item[2].disposition is CarrierDataDisposition.NO_DATA_FOR_SCOPE
    )
    if len(decisive) != 1:
        raise AcquisitionSelectionError(
            "r1_decisive_response_unresolved",
            f"{request_dataset_id}:{len(decisive)}",
        )
    decisive_attempt_id, decisive_body, classification = decisive[0]
    if not cas_root.is_dir():
        raise AcquisitionSelectionError("r1_cas_unresolved", cas_root.as_posix())
    artifact_id = ArtifactID.model_validate(classification.body_sha256)
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    cas_body = store.get_bytes(artifact_id)
    if cas_body != decisive_body:
        raise AcquisitionSelectionError("r1_cas_body_drift", classification.body_sha256)
    manifest_bytes = store.get_manifest_bytes(artifact_id)
    manifest_sha256 = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    prefix_length = max(terminal_end_offsets)
    prefix = journal_path.read_bytes()[:prefix_length]
    values = {
        "schema_version": "policyos.layer3.gy.n13b.r1_forensics.v2",
        "journal_ref": _stable_repo_ref(journal_path),
        "journal_prefix_byte_length": prefix_length,
        "journal_prefix_sha256": f"sha256:{hashlib.sha256(prefix).hexdigest()}",
        "cas_blob_ref": f"cas://sha256/{artifact_id.hex}/blob",
        "cas_manifest_ref": f"cas://sha256/{artifact_id.hex}/manifest/default",
        "cas_blob_sha256": classification.body_sha256,
        "cas_manifest_sha256": manifest_sha256,
        "request_dataset_id": request_dataset_id,
        "attempts": tuple(projections),
        "decisive_attempt_id": decisive_attempt_id,
        "classification": classification,
    }
    return R1ForensicReceipt(
        **values,
        receipt_sha256=content_sha256(values),
    )


def _canonical_journal_projection(
    journal_path: Path,
) -> tuple[tuple[JournalEventRef, dict[str, Any], bytes], ...]:
    payloads = journal_path.read_bytes().splitlines(keepends=True)
    if not payloads or b"".join(payloads) != journal_path.read_bytes():
        raise AcquisitionSelectionError("r1_journal_not_canonical", journal_path.as_posix())
    records: list[tuple[JournalEventRef, dict[str, Any], bytes]] = []
    offset = 0
    for expected_sequence, payload in enumerate(payloads, start=1):
        try:
            event = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcquisitionSelectionError(
                "r1_journal_not_canonical",
                journal_path.as_posix(),
            ) from exc
        if (
            not isinstance(event, dict)
            or event.get("sequence") != expected_sequence
            or canonical_json_bytes(event) != payload
            or not isinstance(event.get("event_kind"), str)
        ):
            raise AcquisitionSelectionError(
                "r1_journal_not_canonical",
                journal_path.as_posix(),
            )
        ref = JournalEventRef(
            journal_path=journal_path.as_posix(),
            sequence=expected_sequence,
            event_kind=str(event["event_kind"]),
            event_sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
            byte_offset=offset,
            byte_length=len(payload),
        )
        resolve_journal_event_ref(ref)
        records.append((ref, event, payload))
        offset += len(payload)
    return tuple(records)


def _stable_repo_ref(path: Path) -> str:
    resolved = Path(path).resolve()
    policy_root = Path(__file__).resolve().parents[3]
    try:
        relative = resolved.relative_to(policy_root)
    except ValueError:
        parts = resolved.parts
        policy_indexes = tuple(index for index, part in enumerate(parts) if part == "policy-engine")
        if policy_indexes:
            candidate = Path(*parts[policy_indexes[-1] + 1 :])
            if candidate.parts and candidate.parts[0] == "production_data":
                return f"repo://{candidate.as_posix()}"
        return resolved.as_posix()
    return f"repo://{relative.as_posix()}"


def _worldbank_api_messages(payload: object) -> tuple[object, ...]:
    containers: list[object] = []
    if isinstance(payload, Mapping):
        containers.append(payload.get("message"))
    elif isinstance(payload, list) and payload and isinstance(payload[0], Mapping):
        containers.append(payload[0].get("message"))
    messages: list[object] = []
    for value in containers:
        if isinstance(value, list):
            messages.extend(value)
        elif value is not None:
            messages.append(value)
    return tuple(messages)


def _nonbool_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_owner_string(
    record: Mapping[str, object] | None,
    *keys: str,
) -> str | None:
    if record is None:
        return None
    for key in keys:
        value = _optional_string(record.get(key))
        if value is not None:
            return value
    return None
