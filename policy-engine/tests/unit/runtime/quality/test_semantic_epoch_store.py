from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, FileSystemCAS
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import semantic_epoch as epoch
from polisyos.runtime.quality.semantic_epoch_store import (
    FileSemanticEpochHistoryRepository,
)


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _scope() -> epoch.EpochScopeIdentity:
    return epoch.build_epoch_scope_identity(
        schema_profile="polisyos.epoch.store-test-scope.v1",
        identity_bytes=b"scope:store-tests",
    )


def _manifest(
    *,
    scope: epoch.EpochScopeIdentity,
    label: str,
    predecessors: tuple[str, ...],
) -> epoch.SemanticEpochManifest:
    values: dict[str, object] = {
        "schema_version": "polisyos.epoch.semantic-manifest.v1",
        "scope_identity": scope.model_dump(mode="json"),
        "authority_purpose": "publication",
        "valid_effect_coordinate_ref": _digest("valid"),
        "visibility_knowledge_cutoff_ref": _digest("knowledge"),
        "purpose_admission_cutoff_ref": _digest("admission"),
        "requested_query_context_ref": _digest("query"),
        "boundary_registry_content_hash": _digest("boundary-registry"),
        "facet_registry_content_hash": _digest("facet-registry"),
        "boundary_denominator_hash": _digest(f"boundary:{label}"),
        "facet_denominator_hash": _digest("facet-denominator"),
        "boundary_semantic_hashes": [_digest(f"semantic:{label}")],
        "facet_semantic_hashes": [_digest("facet")],
        "predecessor_refs": list(predecessors),
    }
    manifest_hash = epoch._model_hash(epoch._MANIFEST_PREFIX, values)
    return epoch.SemanticEpochManifest(
        **values,
        manifest_content_hash=manifest_hash,
        epoch_ref=epoch._sha256(epoch._EPOCH_PREFIX, manifest_hash.encode()),
    )


def _persist_manifest(
    store: FileSystemCAS,
    manifest: epoch.SemanticEpochManifest,
) -> ArtifactRef:
    payload = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(manifest))
    return store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="epoch.semantic_manifest",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )


def _persist_native(store: FileSystemCAS, label: str) -> ArtifactRef:
    return store.put_bytes(
        f"native:{label}".encode(),
        ArtifactWriteOptions(
            kind="epoch.native_member",
            media_type="application/octet-stream",
        ),
    )


def _history_hash(
    *,
    scope: epoch.EpochScopeIdentity,
    entries: tuple[epoch.EpochHistoryEntry, ...],
    heads: tuple[str, ...],
) -> str:
    raw = chronology_contract._frame_record(
        epoch_contract.canonical_epoch_bytes(
            {
                "schema_version": "polisyos.epoch.scope-history.v1",
                "scope": scope.model_dump(mode="json"),
                "authority_purpose": "publication",
                "entries": [entry.model_dump(mode="json") for entry in entries],
                "head_refs": list(heads),
            }
        )
    )
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _entry(
    manifest: epoch.SemanticEpochManifest,
    manifest_ref: ArtifactRef,
    native_ref: ArtifactRef,
) -> epoch.EpochHistoryEntry:
    native_hash = str(native_ref.artifact_id)
    return epoch.EpochHistoryEntry(
        epoch_ref=manifest.epoch_ref,
        manifest_ref=manifest_ref,
        manifest_content_hash=manifest.manifest_content_hash,
        native_member_ref=native_ref,
        native_member_content_hash=native_hash,
        predecessor_refs=manifest.predecessor_refs,
    )


def _append(
    repository: FileSemanticEpochHistoryRepository,
    *,
    scope: epoch.EpochScopeIdentity,
    manifest: epoch.SemanticEpochManifest,
    manifest_ref: ArtifactRef,
    native_ref: ArtifactRef,
    expected_heads: tuple[str, ...],
    resulting_entries: tuple[epoch.EpochHistoryEntry, ...],
    resulting_heads: tuple[str, ...],
) -> epoch.EpochHistoryAppendReceipt:
    return repository.append_if_current(
        expected_head_refs=expected_heads,
        manifest_ref=manifest_ref,
        native_member_ref=native_ref,
        predecessor_refs=manifest.predecessor_refs,
        expected_resulting_history_snapshot_hash=_history_hash(
            scope=scope,
            entries=resulting_entries,
            heads=resulting_heads,
        ),
    )


def test_concurrent_expected_head_conflict_accepts_exactly_one_append(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    scope = _scope()
    candidates = []
    for label in ("left", "right"):
        manifest = _manifest(scope=scope, label=label, predecessors=())
        manifest_ref = _persist_manifest(store, manifest)
        native_ref = _persist_native(store, label)
        candidates.append(
            (
                manifest,
                manifest_ref,
                native_ref,
                _entry(manifest, manifest_ref, native_ref),
            )
        )

    def invoke(row: tuple[Any, ...]) -> epoch.EpochHistoryAppendReceipt:
        manifest, manifest_ref, native_ref, entry = row
        return _append(
            repository,
            scope=scope,
            manifest=manifest,
            manifest_ref=manifest_ref,
            native_ref=native_ref,
            expected_heads=(),
            resulting_entries=(entry,),
            resulting_heads=(manifest.epoch_ref,),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = tuple(pool.map(invoke, candidates))

    assert sorted(row.status for row in receipts) == ["appended", "conflict"]
    history = repository.resolve_scope_history(
        scope=scope,
        authority_purpose="publication",
    )
    assert len(history.entries) == 1
    assert history.head_refs == (history.entries[0].epoch_ref,)


def test_identical_append_is_content_idempotent(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    scope = _scope()
    manifest = _manifest(scope=scope, label="same", predecessors=())
    manifest_ref = _persist_manifest(store, manifest)
    native_ref = _persist_native(store, "same")
    entry = _entry(manifest, manifest_ref, native_ref)
    kwargs = {
        "repository": repository,
        "scope": scope,
        "manifest": manifest,
        "manifest_ref": manifest_ref,
        "native_ref": native_ref,
        "resulting_entries": (entry,),
        "resulting_heads": (manifest.epoch_ref,),
    }

    first = _append(expected_heads=(), **kwargs)
    second = _append(expected_heads=(manifest.epoch_ref,), **kwargs)

    assert first.status == "appended"
    assert second.status == "idempotent"
    assert second.resulting_history_snapshot_content_hash == (
        first.resulting_history_snapshot_content_hash
    )
    assert len((tmp_path / "history" / "epoch-history.jsonl").read_text().splitlines()) == 1


def test_branch_append_preserves_existing_incomparable_head(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    scope = _scope()
    left = _manifest(scope=scope, label="left", predecessors=())
    left_ref = _persist_manifest(store, left)
    left_native = _persist_native(store, "left")
    left_entry = _entry(left, left_ref, left_native)
    _append(
        repository,
        scope=scope,
        manifest=left,
        manifest_ref=left_ref,
        native_ref=left_native,
        expected_heads=(),
        resulting_entries=(left_entry,),
        resulting_heads=(left.epoch_ref,),
    )
    right = _manifest(scope=scope, label="right", predecessors=())
    right_ref = _persist_manifest(store, right)
    right_native = _persist_native(store, "right")
    right_entry = _entry(right, right_ref, right_native)
    heads = tuple(sorted((left.epoch_ref, right.epoch_ref)))

    receipt = _append(
        repository,
        scope=scope,
        manifest=right,
        manifest_ref=right_ref,
        native_ref=right_native,
        expected_heads=(left.epoch_ref,),
        resulting_entries=(left_entry, right_entry),
        resulting_heads=heads,
    )

    assert receipt.status == "appended"
    assert receipt.resulting_head_refs == heads
    assert (
        repository.resolve_scope_history(
            scope=scope,
            authority_purpose="publication",
        ).head_refs
        == heads
    )


def test_crash_before_head_movement_leaves_new_row_non_current(tmp_path: Path) -> None:
    class CrashOnceRepository(FileSemanticEpochHistoryRepository):
        crashed = False

        def _before_head_replace(self) -> None:
            if not self.crashed:
                self.crashed = True
                raise RuntimeError("simulated crash before head replace")

    store = FileSystemCAS(tmp_path / "cas")
    repository = CrashOnceRepository(root=tmp_path / "history", artifacts=store)
    scope = _scope()
    manifest = _manifest(scope=scope, label="crash", predecessors=())
    manifest_ref = _persist_manifest(store, manifest)
    native_ref = _persist_native(store, "crash")
    entry = _entry(manifest, manifest_ref, native_ref)

    with pytest.raises(RuntimeError, match="simulated crash"):
        _append(
            repository,
            scope=scope,
            manifest=manifest,
            manifest_ref=manifest_ref,
            native_ref=native_ref,
            expected_heads=(),
            resulting_entries=(entry,),
            resulting_heads=(manifest.epoch_ref,),
        )
    assert (
        repository.resolve_scope_history(
            scope=scope,
            authority_purpose="publication",
        ).entries
        == ()
    )

    resumed = _append(
        repository,
        scope=scope,
        manifest=manifest,
        manifest_ref=manifest_ref,
        native_ref=native_ref,
        expected_heads=(),
        resulting_entries=(entry,),
        resulting_heads=(manifest.epoch_ref,),
    )
    assert resumed.status == "appended"


def test_scope_history_rebuild_contains_every_native_member(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    scope = _scope()
    first = _manifest(scope=scope, label="first", predecessors=())
    first_ref = _persist_manifest(store, first)
    first_native = _persist_native(store, "first")
    first_entry = _entry(first, first_ref, first_native)
    _append(
        repository,
        scope=scope,
        manifest=first,
        manifest_ref=first_ref,
        native_ref=first_native,
        expected_heads=(),
        resulting_entries=(first_entry,),
        resulting_heads=(first.epoch_ref,),
    )
    second = _manifest(scope=scope, label="second", predecessors=(first.epoch_ref,))
    second_ref = _persist_manifest(store, second)
    second_native = _persist_native(store, "second")
    second_entry = _entry(second, second_ref, second_native)
    _append(
        repository,
        scope=scope,
        manifest=second,
        manifest_ref=second_ref,
        native_ref=second_native,
        expected_heads=(first.epoch_ref,),
        resulting_entries=(first_entry, second_entry),
        resulting_heads=(second.epoch_ref,),
    )

    rebuilt = repository.resolve_scope_history(
        scope=scope,
        authority_purpose="publication",
    )

    assert tuple(row.native_member_ref for row in rebuilt.entries) == (
        first_native,
        second_native,
    )
    assert rebuilt.head_refs == (second.epoch_ref,)
    assert rebuilt.history_snapshot_content_hash == _history_hash(
        scope=scope,
        entries=(first_entry, second_entry),
        heads=(second.epoch_ref,),
    )


def test_manifest_artifact_profile_must_be_exact(tmp_path: Path) -> None:
    """A valid payload under a non-manifest profile is not native history evidence."""

    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    scope = _scope()
    manifest = _manifest(scope=scope, label="wrong-profile", predecessors=())
    framed = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(manifest))
    wrong_ref = store.put_bytes(
        framed,
        ArtifactWriteOptions(
            kind="epoch.not_a_semantic_manifest",
            media_type="application/octet-stream",
        ),
    )
    native_ref = _persist_native(store, "wrong-profile")

    with pytest.raises(ValueError, match="semantic manifest artifact profile mismatch"):
        repository.append_if_current(
            expected_head_refs=(),
            manifest_ref=wrong_ref,
            native_member_ref=native_ref,
            predecessor_refs=(),
            expected_resulting_history_snapshot_hash=_digest("unreachable"),
        )
