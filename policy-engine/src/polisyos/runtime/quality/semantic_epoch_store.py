"""File-backed native history owner for semantic epochs.

Only semantic-epoch manifests and native members are indexed here.  The
common chronology proof store remains a separate, policy-free CAS consumer.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from polisyos.core import artifacts, canon, contracts
from polisyos.runtime.quality.semantic_epoch import (
    EpochHistoryAppendReceipt,
    EpochHistoryEntry,
    EpochScopeHistory,
    EpochScopeIdentity,
    SemanticEpochManifest,
)

ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore
ArtifactWriteOptions = artifacts.ArtifactWriteOptions
from_canonical_bytes = canon.from_canonical_bytes
chronology_contract = contracts.chronology
epoch_contract = contracts.epoch


def _sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _key(*, scope: EpochScopeIdentity, authority_purpose: str) -> str:
    payload = epoch_contract.canonical_epoch_bytes(
        {
            "scope": scope.model_dump(mode="json"),
            "authority_purpose": authority_purpose,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _reachable_rows(rows: list[dict[str, Any]], *, heads: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return the exact head-reachable DAG and reject ambiguous/corrupt history."""

    by_ref: dict[str, dict[str, Any]] = {}
    for row in rows:
        ref = str(row.get("epoch_ref") or "")
        if not ref or ref in by_ref:
            raise RuntimeError("epoch history contains a duplicate or empty epoch ref")
        by_ref[ref] = row
    reachable: set[str] = set()
    visiting: set[str] = set()

    def visit(ref: str) -> None:
        if ref in reachable:
            return
        if ref in visiting:
            raise RuntimeError("epoch history contains a predecessor cycle")
        row = by_ref.get(ref)
        if row is None:
            raise RuntimeError("epoch history head/predecessor is dangling")
        visiting.add(ref)
        for predecessor in row.get("predecessor_refs", ()):
            visit(str(predecessor))
        visiting.remove(ref)
        reachable.add(ref)

    for head in heads:
        visit(head)
    return [row for row in rows if str(row["epoch_ref"]) in reachable]


def _entry_from_row(row: dict[str, Any]) -> EpochHistoryEntry:
    return EpochHistoryEntry(
        epoch_ref=str(row["epoch_ref"]),
        manifest_ref=ArtifactRef.model_validate(row["manifest_ref"]),
        manifest_content_hash=str(row["manifest_content_hash"]),
        native_member_ref=ArtifactRef.model_validate(row["native_member_ref"]),
        native_member_content_hash=str(row["native_member_content_hash"]),
        predecessor_refs=tuple(row["predecessor_refs"]),
    )


def _scope_history_raw(
    *,
    scope: EpochScopeIdentity,
    authority_purpose: str,
    entries: tuple[EpochHistoryEntry, ...],
    heads: tuple[str, ...],
) -> bytes:
    return chronology_contract._frame_record(
        epoch_contract.canonical_epoch_bytes(
            {
                "schema_version": "polisyos.epoch.scope-history.v1",
                "scope": scope.model_dump(mode="json"),
                "authority_purpose": authority_purpose,
                "entries": [entry.model_dump(mode="json") for entry in entries],
                "head_refs": list(heads),
            }
        )
    )


class FileSemanticEpochHistoryRepository:
    """Atomic compare-and-append history with branch-preserving native heads."""

    def __init__(self, *, root: Path, artifacts: ArtifactStore) -> None:
        self._root = Path(root)
        self._artifacts = artifacts
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._root / "epoch-history.lock"
        self._rows_path = self._root / "epoch-history.jsonl"
        self._heads_path = self._root / "epoch-heads.json"

    def _before_head_replace(self) -> None:
        """Override only in tests to simulate a crash before head movement."""

    def _read_rows(self) -> list[dict[str, Any]]:
        if not self._rows_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self._rows_path.open("rb") as handle:
            for raw in handle:
                if raw.strip():
                    value = json.loads(raw)
                    if not isinstance(value, dict):
                        raise RuntimeError("epoch history row is not a mapping")
                    rows.append(value)
        return rows

    def _read_heads(self) -> dict[str, list[str]]:
        if not self._heads_path.exists():
            return {}
        value = json.loads(self._heads_path.read_bytes())
        if not isinstance(value, dict) or any(
            not isinstance(key, str)
            or not isinstance(heads, list)
            or any(not isinstance(head, str) for head in heads)
            for key, heads in value.items()
        ):
            raise RuntimeError("epoch head index has invalid shape")
        return value

    def _write_heads(self, heads: dict[str, list[str]]) -> None:
        payload = epoch_contract.canonical_epoch_bytes(heads)
        fd, scratch_name = tempfile.mkstemp(prefix="epoch-heads-", dir=self._root)
        scratch = Path(scratch_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(scratch, self._heads_path)
            directory_fd = os.open(self._root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if scratch.exists():
                scratch.unlink()

    def _manifest(self, manifest_ref: ArtifactRef) -> tuple[SemanticEpochManifest, bytes]:
        report = self._artifacts.verify(manifest_ref.artifact_id)
        raw = self._artifacts.get_bytes(manifest_ref.artifact_id)
        manifest = self._artifacts.get_manifest(manifest_ref.artifact_id)
        if (
            manifest_ref.kind != "epoch.semantic_manifest"
            or manifest_ref.media_type != "application/vnd.polisyos.epoch+json"
            or manifest.kind != "epoch.semantic_manifest"
            or manifest.media_type != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("semantic manifest artifact profile mismatch")
        records = chronology_contract._split_framed_records(raw)
        if (
            not report.ok
            or _sha256(raw) != str(manifest_ref.artifact_id)
            or manifest.artifact_id != manifest_ref.artifact_id
            or manifest.kind != manifest_ref.kind
            or manifest.media_type != manifest_ref.media_type
            or len(records) != 1
        ):
            raise ValueError("semantic manifest CAS readback failed")
        return SemanticEpochManifest.model_validate(from_canonical_bytes(records[0])), raw

    def _validate_history_row(
        self,
        row: dict[str, Any],
        *,
        scope: EpochScopeIdentity,
        authority_purpose: str,
    ) -> None:
        manifest_ref = ArtifactRef.model_validate(row.get("manifest_ref"))
        manifest, _ = self._manifest(manifest_ref)
        native_ref = ArtifactRef.model_validate(row.get("native_member_ref"))
        native_report = self._artifacts.verify(native_ref.artifact_id)
        native_raw = self._artifacts.get_bytes(native_ref.artifact_id)
        expected = {
            "scope_key": _key(scope=scope, authority_purpose=authority_purpose),
            "scope": scope.model_dump(mode="json"),
            "authority_purpose": authority_purpose,
            "epoch_ref": manifest.epoch_ref,
            "manifest_ref": manifest_ref.model_dump(mode="json"),
            "manifest_content_hash": manifest.manifest_content_hash,
            "native_member_ref": native_ref.model_dump(mode="json"),
            "native_member_content_hash": _sha256(native_raw),
            "predecessor_refs": list(manifest.predecessor_refs),
        }
        if (
            not native_report.ok
            or _sha256(native_raw) != str(native_ref.artifact_id)
            or row != expected
            or manifest.scope_identity != scope
            or manifest.authority_purpose != authority_purpose
        ):
            raise RuntimeError("epoch history row differs from fixed owner artifacts")

    def append_if_current(
        self,
        *,
        expected_head_refs: tuple[str, ...],
        manifest_ref: ArtifactRef,
        native_member_ref: ArtifactRef,
        predecessor_refs: tuple[str, ...],
        expected_resulting_history_snapshot_hash: str,
    ) -> EpochHistoryAppendReceipt:
        """Append once iff the complete expected native head set is current."""

        manifest, _ = self._manifest(manifest_ref)
        if manifest.predecessor_refs != predecessor_refs:
            raise ValueError("manifest predecessors differ from append request")
        native_report = self._artifacts.verify(native_member_ref.artifact_id)
        native_bytes = self._artifacts.get_bytes(native_member_ref.artifact_id)
        if not native_report.ok or _sha256(native_bytes) != str(native_member_ref.artifact_id):
            raise ValueError("native epoch member failed CAS verification")
        scope_key = _key(
            scope=manifest.scope_identity,
            authority_purpose=manifest.authority_purpose,
        )
        self._lock_path.touch(exist_ok=True)
        with self._lock_path.open("r+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            rows = self._read_rows()
            heads = self._read_heads()
            current = tuple(heads.get(scope_key, ()))
            for stored_row in rows:
                if stored_row.get("scope_key") == scope_key:
                    self._validate_history_row(
                        stored_row,
                        scope=manifest.scope_identity,
                        authority_purpose=manifest.authority_purpose,
                    )
            existing = next(
                (row for row in rows if row.get("epoch_ref") == manifest.epoch_ref),
                None,
            )
            if existing is not None:
                if (
                    existing.get("manifest_ref") != manifest_ref.model_dump(mode="json")
                    or existing.get("native_member_ref")
                    != native_member_ref.model_dump(mode="json")
                    or tuple(existing.get("predecessor_refs", ())) != predecessor_refs
                ):
                    raise RuntimeError("epoch ref already names different native bytes")
                _reachable_rows(rows, heads=current)
                if manifest.epoch_ref in current:
                    current_entries = tuple(
                        _entry_from_row(row) for row in _reachable_rows(rows, heads=current)
                    )
                    current_snapshot_raw = _scope_history_raw(
                        scope=manifest.scope_identity,
                        authority_purpose=manifest.authority_purpose,
                        entries=current_entries,
                        heads=current,
                    )
                    if _sha256(current_snapshot_raw) != expected_resulting_history_snapshot_hash:
                        raise ValueError("current epoch history differs from qualified snapshot")
                    return self._append_receipt(
                        status="idempotent",
                        manifest_ref=manifest_ref,
                        epoch_ref=manifest.epoch_ref,
                        expected_head_refs=expected_head_refs,
                        resulting_head_refs=current,
                        resulting_history_snapshot_raw=current_snapshot_raw,
                    )
            if current != expected_head_refs:
                return EpochHistoryAppendReceipt(
                    status="conflict",
                    manifest_ref=manifest_ref,
                    epoch_ref=manifest.epoch_ref,
                    expected_head_refs=expected_head_refs,
                    resulting_head_refs=current,
                    resulting_history_snapshot_ref=None,
                    resulting_history_snapshot_content_hash=None,
                    history_receipt_ref=None,
                    history_receipt_content_hash=None,
                )
            row = (
                existing
                if existing is not None
                else {
                    "scope_key": scope_key,
                    "scope": manifest.scope_identity.model_dump(mode="json"),
                    "authority_purpose": manifest.authority_purpose,
                    "epoch_ref": manifest.epoch_ref,
                    "manifest_ref": manifest_ref.model_dump(mode="json"),
                    "manifest_content_hash": manifest.manifest_content_hash,
                    "native_member_ref": native_member_ref.model_dump(mode="json"),
                    "native_member_content_hash": _sha256(native_bytes),
                    "predecessor_refs": list(predecessor_refs),
                }
            )
            remaining = [head for head in current if head not in predecessor_refs]
            resulting = tuple(sorted((*remaining, manifest.epoch_ref)))
            reachable_before = _reachable_rows(rows, heads=current)
            prospective_rows = [
                *reachable_before,
                *(
                    []
                    if any(item.get("epoch_ref") == manifest.epoch_ref for item in reachable_before)
                    else [row]
                ),
            ]
            prospective_entries = tuple(_entry_from_row(item) for item in prospective_rows)
            prospective_raw = _scope_history_raw(
                scope=manifest.scope_identity,
                authority_purpose=manifest.authority_purpose,
                entries=prospective_entries,
                heads=resulting,
            )
            prospective_hash = _sha256(prospective_raw)
            if prospective_hash != expected_resulting_history_snapshot_hash:
                raise ValueError("prospective epoch history differs from qualified snapshot")
            if existing is None:
                encoded = epoch_contract.canonical_epoch_bytes(row) + b"\n"
                with self._rows_path.open("ab") as history_handle:
                    history_handle.write(encoded)
                    history_handle.flush()
                    os.fsync(history_handle.fileno())
            updated = {**heads, scope_key: list(resulting)}
            self._before_head_replace()
            self._write_heads(updated)
            return self._append_receipt(
                status="appended",
                manifest_ref=manifest_ref,
                epoch_ref=manifest.epoch_ref,
                expected_head_refs=expected_head_refs,
                resulting_head_refs=resulting,
                resulting_history_snapshot_raw=prospective_raw,
            )

    def _append_receipt(
        self,
        *,
        status: str,
        manifest_ref: ArtifactRef,
        epoch_ref: str,
        expected_head_refs: tuple[str, ...],
        resulting_head_refs: tuple[str, ...],
        resulting_history_snapshot_raw: bytes,
    ) -> EpochHistoryAppendReceipt:
        snapshot_hash = _sha256(resulting_history_snapshot_raw)
        snapshot_ref = self._artifacts.put_bytes(
            resulting_history_snapshot_raw,
            ArtifactWriteOptions(
                kind="epoch.scope_history",
                media_type="application/vnd.polisyos.epoch+json",
            ),
        )
        if str(snapshot_ref.artifact_id) != snapshot_hash:
            raise RuntimeError("resulting epoch history snapshot CAS identity differs")
        statement = {
            "schema_version": "polisyos.epoch.history-append-receipt.v1",
            "status": status,
            "manifest_ref": manifest_ref.model_dump(mode="json"),
            "epoch_ref": epoch_ref,
            "expected_head_refs": list(expected_head_refs),
            "resulting_head_refs": list(resulting_head_refs),
            "resulting_history_snapshot_ref": snapshot_ref.model_dump(mode="json"),
            "resulting_history_snapshot_content_hash": snapshot_hash,
        }
        raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
        receipt_ref = self._artifacts.put_bytes(
            raw,
            ArtifactWriteOptions(
                kind="epoch.history_append_receipt",
                media_type="application/vnd.polisyos.epoch+json",
            ),
        )
        return EpochHistoryAppendReceipt(
            status=status,
            manifest_ref=manifest_ref,
            epoch_ref=epoch_ref,
            expected_head_refs=expected_head_refs,
            resulting_head_refs=resulting_head_refs,
            resulting_history_snapshot_ref=snapshot_ref,
            resulting_history_snapshot_content_hash=snapshot_hash,
            history_receipt_ref=receipt_ref,
            history_receipt_content_hash=_sha256(raw),
        )

    def resolve_scope_history(
        self, *, scope: EpochScopeIdentity, authority_purpose: str
    ) -> EpochScopeHistory:
        """Return and persist the exact complete native history snapshot."""

        scope_key = _key(scope=scope, authority_purpose=authority_purpose)
        self._lock_path.touch(exist_ok=True)
        with self._lock_path.open("r+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_SH)
            rows = [row for row in self._read_rows() if row.get("scope_key") == scope_key]
            heads = tuple(self._read_heads().get(scope_key, ()))
            for row in rows:
                self._validate_history_row(
                    row,
                    scope=scope,
                    authority_purpose=authority_purpose,
                )
            rows = _reachable_rows(rows, heads=heads)
        entries = tuple(_entry_from_row(row) for row in rows)
        raw = _scope_history_raw(
            scope=scope,
            authority_purpose=authority_purpose,
            entries=entries,
            heads=heads,
        )
        snapshot_ref = self._artifacts.put_bytes(
            raw,
            ArtifactWriteOptions(
                kind="epoch.scope_history",
                media_type="application/vnd.polisyos.epoch+json",
            ),
        )
        return EpochScopeHistory(
            scope=scope,
            authority_purpose=authority_purpose,
            entries=entries,
            head_refs=heads,
            history_snapshot_ref=snapshot_ref,
            history_snapshot_content_hash=_sha256(raw),
            predicate_class="recomputed",
        )

    def resolve_scope_history_by_ref(
        self, *, scope_identity_ref: str, authority_purpose: str
    ) -> EpochScopeHistory:
        """Resolve the unique owner scope already bound by its semantic ref."""

        self._lock_path.touch(exist_ok=True)
        with self._lock_path.open("r+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_SH)
            candidates = {
                epoch_contract.canonical_epoch_bytes(row.get("scope", {}))
                for row in self._read_rows()
                if row.get("authority_purpose") == authority_purpose
                and isinstance(row.get("scope"), dict)
                and row["scope"].get("scope_identity_ref") == scope_identity_ref
            }
        if len(candidates) != 1:
            raise ValueError("epoch scope identity ref is absent or ambiguous")
        scope = EpochScopeIdentity.model_validate(from_canonical_bytes(next(iter(candidates))))
        return self.resolve_scope_history(
            scope=scope,
            authority_purpose=authority_purpose,
        )


__all__ = ["FileSemanticEpochHistoryRepository"]
