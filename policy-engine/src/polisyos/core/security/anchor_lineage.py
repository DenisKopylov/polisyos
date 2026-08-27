"""Append-only accepted-anchor lineage with compare-and-append heads.

Candidate authenticity is intentionally separate from acceptance.  Only a
successful append against the owner-resolved head set yields an append receipt;
conflicts preserve the candidate but never move the current index.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import chronology as contract

_MEDIA_TYPE = "application/octet-stream"
_STATE_DOMAIN = b"polisyos.chronology.anchor-acceptance-lineage-state.v1\0"
_APPEND_DOMAIN = b"polisyos.chronology.anchor-lineage-append.v1\0"


def _model_bytes(value: BaseModel) -> bytes:
    mapping = contract._raw_model_mapping(value)
    return contract._frame_record(contract._canonical_raw_bytes(mapping))


def _semantic_hash(domain: bytes, payload: bytes) -> contract.Digest:
    return contract._sha256_digest(domain, payload)


def _raw_ref(payload: bytes, *, kind: str) -> ArtifactRef:
    digest = hashlib.sha256(payload).hexdigest()
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(digest),
        kind=kind,
        media_type=_MEDIA_TYPE,
    )


def _parse_framed(payload: bytes, model: type[BaseModel]) -> BaseModel:
    frames = contract._split_framed_records(payload)
    if len(frames) != 1:
        raise ValueError("lineage record must contain exactly one frame")
    raw = from_canonical_bytes(frames[0])
    if not isinstance(raw, dict) or contract._canonical_raw_bytes(raw) != frames[0]:
        raise ValueError("lineage record is not a canonical mapping")
    return model.model_validate(raw)


def _key_token(key: contract.AnchorAcceptanceLineageKey) -> str:
    payload = _model_bytes(key)
    return hashlib.sha256(b"polisyos.chronology.anchor-lineage-key.v1\0" + payload).hexdigest()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError as exc:
        if path.read_bytes() != payload:
            raise ValueError(f"immutable lineage record differs at {path.name}") from exc
        return
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        _fsync_directory(path.parent)


def _atomic_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


@dataclass(slots=True)
class FileAnchorAcceptanceLineageRepository:
    """File-backed lineage with immutable WAL/records and one atomic head index."""

    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _directory(self, key: contract.AnchorAcceptanceLineageKey) -> Path:
        return self.root / _key_token(key)

    def _empty_statement(
        self, key: contract.AnchorAcceptanceLineageKey
    ) -> contract.AnchorAcceptanceLineageStateStatement:
        return contract.AnchorAcceptanceLineageStateStatement(
            key=key,
            current_record_refs=(),
            records=(),
        )

    def _load_index(
        self, key: contract.AnchorAcceptanceLineageKey
    ) -> contract.AnchorAcceptanceLineageStateStatement:
        index = self._directory(key) / "head-index.frame"
        if not index.exists():
            return self._empty_statement(key)
        statement = _parse_framed(
            index.read_bytes(), contract.AnchorAcceptanceLineageStateStatement
        )
        if statement.key != key:
            raise ValueError("lineage index key mismatch")
        return statement

    def _recover_pending(
        self, key: contract.AnchorAcceptanceLineageKey
    ) -> contract.AnchorAcceptanceLineageStateStatement:
        """Complete any durable transaction whose head move was interrupted."""

        directory = self._directory(key)
        state = self._load_index(key)
        transactions = directory / "transactions"
        if not transactions.exists():
            return state
        while True:
            recovered = False
            for transaction_path in sorted(transactions.glob("*.frame")):
                transaction_payload = transaction_path.read_bytes()
                parsed = _parse_framed(
                    transaction_payload,
                    contract.AnchorAcceptanceAppendSuccessStatement,
                )
                if not isinstance(parsed, contract.AnchorAcceptanceAppendSuccessStatement):
                    raise TypeError("lineage transaction decoded to the wrong model")
                if parsed.key != key or parsed.status != "appended":
                    continue
                if parsed.resulting_head_refs == state.current_record_refs:
                    state_payload = _model_bytes(state)
                    if _semantic_hash(_STATE_DOMAIN, state_payload) != (
                        parsed.resulting_state_content_hash
                    ):
                        raise ValueError("current lineage index disagrees with durable transaction")
                    self._persist_success(parsed, transaction_payload, directory)
                    continue
                if parsed.previous_head_refs != state.current_record_refs:
                    continue
                record_path = (
                    directory / "records" / f"{parsed.acceptance_record_ref.artifact_id.hex}.frame"
                )
                record = _parse_framed(record_path.read_bytes(), contract.AcceptedAnchorRecordEntry)
                if not isinstance(record, contract.AcceptedAnchorRecordEntry):
                    raise TypeError("lineage candidate decoded to the wrong model")
                next_state = contract.AnchorAcceptanceLineageStateStatement(
                    key=key,
                    current_record_refs=parsed.resulting_head_refs,
                    records=(*state.records, record),
                )
                next_payload = _model_bytes(next_state)
                if _semantic_hash(_STATE_DOMAIN, next_payload) != (
                    parsed.resulting_state_content_hash
                ):
                    raise ValueError("durable lineage transaction does not bind recovered state")
                _atomic_replace(directory / "head-index.frame", next_payload)
                self._persist_success(parsed, transaction_payload, directory)
                state = next_state
                recovered = True
                break
            if not recovered:
                return state

    def resolve_lineage(
        self, *, key: contract.AnchorAcceptanceLineageKey
    ) -> contract.AnchorAcceptanceLineageState:
        """Return the exact current state without list/time ordering heads."""

        directory = self._directory(key)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".append.lock").open("a+b") as lock_stream:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            statement = self._recover_pending(key)
        payload = _model_bytes(statement)
        return contract.AnchorAcceptanceLineageState(
            statement_bytes=payload,
            state_content_hash=_semantic_hash(_STATE_DOMAIN, payload),
        )

    def append_if_current(
        self,
        *,
        key: contract.AnchorAcceptanceLineageKey,
        expected_head_refs: tuple[ArtifactRef, ...],
        record: contract.AcceptedAnchorRecordEntry,
    ) -> contract.AnchorAcceptanceAppendResult:
        """Compare exact head sets and append one immutable acceptance record."""

        directory = self._directory(key)
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / ".append.lock"
        with lock_path.open("a+b") as lock_stream:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            observed = self._recover_pending(key)
            existing = next(
                (
                    item
                    for item in observed.records
                    if item.acceptance_record_ref == record.acceptance_record_ref
                ),
                None,
            )
            if existing is not None:
                if existing != record:
                    raise ValueError("acceptance ref re-used for different lineage bytes")
                if record.predecessor_record_refs != expected_head_refs:
                    raise ValueError("idempotent append predecessor set differs")
                return self._success(
                    key=key,
                    expected=expected_head_refs,
                    previous=expected_head_refs,
                    resulting=observed.current_record_refs,
                    record=record,
                    state=observed,
                    status="idempotent",
                    directory=directory,
                )
            if observed.current_record_refs != expected_head_refs:
                return contract.AnchorAcceptanceAppendConflict(
                    result_kind="append_conflict",
                    status="head_conflict",
                    key=key,
                    expected_head_refs=expected_head_refs,
                    observed_head_refs=observed.current_record_refs,
                    candidate_record_ref=record.acceptance_record_ref,
                    failure_code="accepted_anchor_lineage_conflict",
                )
            if record.predecessor_record_refs != expected_head_refs:
                raise ValueError("candidate predecessor refs differ from compared heads")

            candidate_payload = _model_bytes(record)
            record_token = record.acceptance_record_ref.artifact_id.hex
            _write_once(directory / "records" / f"{record_token}.frame", candidate_payload)
            next_statement = contract.AnchorAcceptanceLineageStateStatement(
                key=key,
                current_record_refs=(record.acceptance_record_ref,),
                records=(*observed.records, record),
            )
            next_payload = _model_bytes(next_statement)
            next_hash = _semantic_hash(_STATE_DOMAIN, next_payload)
            transaction = contract.AnchorAcceptanceAppendSuccessStatement(
                status="appended",
                key=key,
                expected_head_refs=expected_head_refs,
                previous_head_refs=observed.current_record_refs,
                resulting_head_refs=(record.acceptance_record_ref,),
                acceptance_record_ref=record.acceptance_record_ref,
                resulting_state_content_hash=next_hash,
            )
            transaction_payload = _model_bytes(transaction)
            _write_once(
                directory / "transactions" / f"{record_token}.frame",
                transaction_payload,
            )
            _atomic_replace(directory / "head-index.frame", next_payload)
            return self._persist_success(transaction, transaction_payload, directory)

    def _success(
        self,
        *,
        key: contract.AnchorAcceptanceLineageKey,
        expected: tuple[ArtifactRef, ...],
        previous: tuple[ArtifactRef, ...],
        resulting: tuple[ArtifactRef, ...],
        record: contract.AcceptedAnchorRecordEntry,
        state: contract.AnchorAcceptanceLineageStateStatement,
        status: str,
        directory: Path,
    ) -> contract.PersistedAnchorAcceptanceAppendSuccess:
        state_payload = _model_bytes(state)
        statement = contract.AnchorAcceptanceAppendSuccessStatement(
            status=status,
            key=key,
            expected_head_refs=expected,
            previous_head_refs=previous,
            resulting_head_refs=resulting,
            acceptance_record_ref=record.acceptance_record_ref,
            resulting_state_content_hash=_semantic_hash(_STATE_DOMAIN, state_payload),
        )
        return self._persist_success(statement, _model_bytes(statement), directory)

    def _persist_success(
        self,
        statement: contract.AnchorAcceptanceAppendSuccessStatement,
        payload: bytes,
        directory: Path,
    ) -> contract.PersistedAnchorAcceptanceAppendSuccess:
        receipt = _raw_ref(payload, kind="core.chronology.anchor_lineage_append")
        _write_once(directory / "receipts" / f"{receipt.artifact_id.hex}.frame", payload)
        return contract.PersistedAnchorAcceptanceAppendSuccess(
            result_kind="append_success",
            append_receipt_ref=receipt,
            append_receipt_content_hash=_semantic_hash(_APPEND_DOMAIN, payload),
            statement_bytes=payload,
        )


class InMemoryAnchorAcceptanceLineageRepository:
    """Test-only compare-and-append repository with an explicit token falsifier."""

    def __init__(self) -> None:
        self._states: dict[str, contract.AnchorAcceptanceLineageStateStatement] = {}
        self._lock = threading.Lock()
        self._token_heads: tuple[str, ...] = ()

    @property
    def current_head_refs(self) -> tuple[str, ...]:
        return self._token_heads

    def append_token(self, token: str, *, expected_head_tokens: tuple[str, ...]) -> SimpleNamespace:
        """Exercise stale-head rejection without constructing authority fixtures."""

        with self._lock:
            if self._token_heads != expected_head_tokens:
                return SimpleNamespace(status="head_conflict")
            self._token_heads = (token,)
            return SimpleNamespace(status="appended")

    def resolve_lineage(
        self, *, key: contract.AnchorAcceptanceLineageKey
    ) -> contract.AnchorAcceptanceLineageState:
        statement = self._states.get(_key_token(key))
        if statement is None:
            statement = contract.AnchorAcceptanceLineageStateStatement(
                key=key, current_record_refs=(), records=()
            )
        payload = _model_bytes(statement)
        return contract.AnchorAcceptanceLineageState(
            statement_bytes=payload,
            state_content_hash=_semantic_hash(_STATE_DOMAIN, payload),
        )

    def append_if_current(
        self,
        *,
        key: contract.AnchorAcceptanceLineageKey,
        expected_head_refs: tuple[ArtifactRef, ...],
        record: contract.AcceptedAnchorRecordEntry,
    ) -> contract.AnchorAcceptanceAppendResult:
        with self._lock:
            token = _key_token(key)
            state = self._states.get(
                token,
                contract.AnchorAcceptanceLineageStateStatement(
                    key=key, current_record_refs=(), records=()
                ),
            )
            if state.current_record_refs != expected_head_refs:
                return contract.AnchorAcceptanceAppendConflict(
                    result_kind="append_conflict",
                    status="head_conflict",
                    key=key,
                    expected_head_refs=expected_head_refs,
                    observed_head_refs=state.current_record_refs,
                    candidate_record_ref=record.acceptance_record_ref,
                    failure_code="accepted_anchor_lineage_conflict",
                )
            if record.predecessor_record_refs != expected_head_refs:
                raise ValueError("candidate predecessor refs differ from compared heads")
            existing = next(
                (
                    item
                    for item in state.records
                    if item.acceptance_record_ref == record.acceptance_record_ref
                ),
                None,
            )
            if existing is not None and existing != record:
                raise ValueError("acceptance ref re-used for different lineage bytes")
            next_state = contract.AnchorAcceptanceLineageStateStatement(
                key=key,
                current_record_refs=(record.acceptance_record_ref,),
                records=state.records if existing is not None else (*state.records, record),
            )
            self._states[token] = next_state
            state_payload = _model_bytes(next_state)
            statement = contract.AnchorAcceptanceAppendSuccessStatement(
                status="idempotent" if existing is not None else "appended",
                key=key,
                expected_head_refs=expected_head_refs,
                previous_head_refs=state.current_record_refs,
                resulting_head_refs=next_state.current_record_refs,
                acceptance_record_ref=record.acceptance_record_ref,
                resulting_state_content_hash=_semantic_hash(_STATE_DOMAIN, state_payload),
            )
            payload = _model_bytes(statement)
            receipt = _raw_ref(payload, kind="core.chronology.anchor_lineage_append")
            return contract.PersistedAnchorAcceptanceAppendSuccess(
                result_kind="append_success",
                append_receipt_ref=receipt,
                append_receipt_content_hash=_semantic_hash(_APPEND_DOMAIN, payload),
                statement_bytes=payload,
            )


__all__ = [
    "FileAnchorAcceptanceLineageRepository",
    "InMemoryAnchorAcceptanceLineageRepository",
]
