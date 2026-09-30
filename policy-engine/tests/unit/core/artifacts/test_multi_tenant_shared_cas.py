"""Behavioral witnesses for cross-instance CAS publication custody."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import threading
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import polisyos.core.artifacts.store as store_module
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


def _artifact_paths(root: Path, artifact_id: ArtifactID) -> tuple[Path, Path]:
    directory = (
        root
        / "artifacts"
        / "sha256"
        / artifact_id.hex[:2]
        / artifact_id.hex[2:4]
    )
    return (
        directory / f"{artifact_id.hex}.blob",
        directory / f"{artifact_id.hex}.manifest.json",
    )


def _artifact_id(data: bytes) -> ArtifactID:
    return ArtifactID.from_sha256_hex(hashlib.sha256(data).hexdigest())


def _options() -> PutOptions:
    return PutOptions(kind="test.r9.cas_payload", media_type="application/octet-stream")


def _read_in_second_process(
    root: str,
    artifact_id: str,
    ready: Any,
    attempt: Any,
    finished: Any,
    outcome: Any,
) -> None:
    store = FileSystemCAS(Path(root)).with_ambient_ownership_enforcement()
    store_origin = str(Path(store_module.__file__).resolve())
    ready.set()
    if not attempt.wait(timeout=5):
        outcome.put({"error": "attempt_timeout", "store_origin": store_origin})
        finished.set()
        return
    try:
        outcome.put(
            {
                "payload": store.get_bytes(ArtifactID.model_validate(artifact_id)),
                "store_origin": store_origin,
            }
        )
    except BaseException as exc:
        outcome.put(
            {"error": f"{type(exc).__name__}:{exc}", "store_origin": store_origin}
        )
    finally:
        finished.set()


def test_uncommitted_tenant_publication_is_unreadable_after_writer_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cas"
    payload = b"tenant bytes visible before owner-generation commit"
    artifact_id = _artifact_id(payload)
    writer = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")

    def interrupt_owner_generation(_payload: dict[str, object]) -> None:
        raise RuntimeError("simulated interruption before owner-generation publication")

    monkeypatch.setattr(writer._ownership_index, "_write_payload", interrupt_owner_generation)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        writer.put_bytes(payload, _options())

    blob, manifest = _artifact_paths(root, artifact_id)
    assert blob.read_bytes() == payload
    assert manifest.is_file()
    intent_files = list(
        (root / "artifacts" / "ownership" / "transactions" / "intents").rglob("*.json")
    )
    assert len(intent_files) == 1
    intent = json.loads(intent_files[0].read_bytes())
    assert intent["status"] == "pending"

    reopened_ambient = FileSystemCAS(root).with_ambient_ownership_enforcement()
    with pytest.raises(ArtifactOwnershipError) as refusal:
        reopened_ambient.get_bytes(artifact_id)
    assert getattr(refusal.value, "code", None) == "artifact_transaction_pending"

    with pytest.raises(ArtifactOwnershipError) as owner_refusal:
        reopened_ambient.record_artifact_owner(artifact_id, tenant_id="tenant-b")
    assert getattr(owner_refusal.value, "code", None) == "artifact_transaction_pending"


def test_independent_cas_reader_waits_for_tenant_owner_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cas"
    payload = b"bytes must not cross the publication boundary"
    artifact_id = _artifact_id(payload)
    writer = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    reader = FileSystemCAS(root).with_ambient_ownership_enforcement()
    owner_write_entered = threading.Event()
    release_owner_write = threading.Event()
    reader_entered = threading.Event()
    reader_finished = threading.Event()
    writer_finished = threading.Event()
    outcomes: dict[str, object] = {}
    original_write_payload = writer._ownership_index._write_payload

    def pause_before_owner_generation(owner_payload: dict[str, object]) -> None:
        owner_write_entered.set()
        if not release_owner_write.wait(timeout=5):
            raise TimeoutError("owner-generation test gate was not released")
        original_write_payload(owner_payload)

    monkeypatch.setattr(
        writer._ownership_index,
        "_write_payload",
        pause_before_owner_generation,
    )

    def publish() -> None:
        try:
            writer.put_bytes(payload, _options())
        except BaseException as exc:  # Captured so the test can always release both threads.
            outcomes["writer_error"] = exc
        finally:
            writer_finished.set()

    def read() -> None:
        reader_entered.set()
        try:
            outcomes["reader_bytes"] = reader.get_bytes(artifact_id)
        except BaseException as exc:  # The expected result after publication is a typed denial.
            outcomes["reader_error"] = exc
        finally:
            reader_finished.set()

    writer_thread = threading.Thread(target=publish, name="r9-cas-writer")
    reader_thread = threading.Thread(target=read, name="r9-cas-reader")
    writer_thread.start()
    try:
        assert owner_write_entered.wait(timeout=5)
        blob, manifest = _artifact_paths(root, artifact_id)
        assert blob.read_bytes() == payload
        assert manifest.is_file()
        reader_thread.start()
        assert reader_entered.wait(timeout=5)
        assert not reader_finished.wait(timeout=0.2), (
            "a second CAS instance read bytes while the tenant publication lease was held"
        )
    finally:
        release_owner_write.set()
        writer_thread.join(timeout=5)
        if reader_thread.ident is not None:
            reader_thread.join(timeout=5)

    assert writer_finished.is_set()
    assert "writer_error" not in outcomes
    assert reader_finished.is_set()
    assert isinstance(outcomes.get("reader_error"), ArtifactOwnershipError)
    assert "reader_bytes" not in outcomes


def test_second_process_reader_waits_on_the_canonical_root_stripe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root).with_ambient_ownership_enforcement()
    payload = b"cross-process reads use the same local CAS lease"
    artifact_ref = store.put_bytes(payload, _options())
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    attempt = context.Event()
    finished = context.Event()
    outcome = context.Queue()
    process = context.Process(
        target=_read_in_second_process,
        args=(str(root), str(artifact_ref.artifact_id), ready, attempt, finished, outcome),
    )
    test_import_root = str(Path(__file__).resolve().parents[2])
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(part for part in (test_import_root, existing_pythonpath) if part),
    )
    process.start()
    try:
        assert ready.wait(timeout=10)
        with store._coordinator.artifact_lease(artifact_ref.artifact_id, exclusive=True):
            attempt.set()
            assert not finished.wait(timeout=0.25), (
                "a second process returned CAS bytes while the writer held the artifact stripe"
            )
        assert finished.wait(timeout=10)
    finally:
        attempt.set()
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    assert process.exitcode == 0
    child_result = outcome.get(timeout=1)
    expected_source_root = Path(__file__).resolve().parents[4] / "src" / "polisyos"
    assert Path(child_result["store_origin"]).is_relative_to(expected_source_root)
    assert child_result["payload"] == payload


def test_nested_distinct_artifact_lease_fails_without_deadlock(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    first = _artifact_id(b"first artifact lock")
    second = _artifact_id(b"second artifact lock")
    assert first != second

    with store._coordinator.artifact_lease(first, exclusive=True):
        with pytest.raises(
            RuntimeError,
            match="artifact_transaction_nested_distinct_id_not_supported",
        ):
            with store._coordinator.artifact_lease(second, exclusive=True):
                pytest.fail("distinct nested artifact lease was admitted")


def test_next_writer_recovers_unreferenced_private_stage_directory(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    orphan = root / "artifacts" / "ownership" / "transactions" / "stage" / "orphan-operation"
    orphan.mkdir(parents=True)
    (orphan / "blob.stage").write_bytes(b"private, unpublished bytes")

    candidate = FileSystemCAS(root).with_ambient_ownership_enforcement()
    payload = b"ordinary candidate work remains available"
    artifact_ref = candidate.put_bytes(payload, _options())

    assert candidate.has(artifact_ref)
    assert candidate.get_bytes(artifact_ref) == payload
    assert not orphan.exists()


def test_stage_recovery_never_follows_or_removes_symlink_targets(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    stage_root = root / "artifacts" / "ownership" / "transactions" / "stage"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "preserve.txt"
    sentinel.write_text("outside the CAS stage")
    stage_root.mkdir(parents=True)
    (stage_root / "orphan-link").symlink_to(outside, target_is_directory=True)
    orphan_with_link = stage_root / "orphan-with-link"
    orphan_with_link.mkdir()
    (orphan_with_link / "outside-link").symlink_to(sentinel)

    FileSystemCAS(root)

    assert sentinel.read_text() == "outside the CAS stage"
    assert (stage_root / "orphan-link").is_symlink()
    assert (orphan_with_link / "outside-link").is_symlink()


def test_unclaimed_candidate_put_has_and_read_still_succeed(tmp_path: Path) -> None:
    candidate = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    payload = b"ordinary unclaimed candidate payload"

    artifact_ref = candidate.put_bytes(payload, _options())

    assert candidate.has(artifact_ref)
    assert candidate.get_bytes(artifact_ref) == payload


def test_intent_completion_requires_each_exact_claim_in_one_owner_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    payload = b"owner-generation rows are the commit signal"
    artifact_id = _artifact_id(payload)
    captured: list[dict[str, object]] = []
    index = store._ownership_index
    write_intent = index.write_transaction_intent

    def capture_intent(
        target_id: ArtifactID,
        document: dict[str, object],
        *,
        lease: object,
    ) -> Path:
        captured.append(deepcopy(document))
        return write_intent(target_id, document, lease=lease)  # type: ignore[arg-type]

    monkeypatch.setattr(index, "write_transaction_intent", capture_intent)
    store.put_bytes(payload, _options())
    assert len(captured) == 2
    pending = captured[0]
    current = index._load_snapshot()
    candidate_payload = deepcopy(current.payload)
    records = candidate_payload["artifacts"][str(artifact_id)]
    candidate_payload["artifacts"][str(artifact_id)] = [
        row for row in records if row.get("manifest_profile_sha256") is None
    ]
    monkeypatch.setattr(
        index,
        "_load_snapshot",
        lambda: replace(current, payload=candidate_payload),
    )

    assert not index._intent_completion_is_recomputed(pending)  # type: ignore[arg-type]
    committed_without_view_claim = dict(pending)
    committed_without_view_claim["status"] = "committed"
    assert not index._intent_completion_is_recomputed(  # type: ignore[arg-type]
        committed_without_view_claim
    )


def test_same_request_recovers_missing_stage_with_pinned_manifest_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    payload = b"recovery must reuse the exact manifest bytes"
    captured: list[dict[str, object]] = []
    index = writer._ownership_index
    write_intent = index.write_transaction_intent
    publish_member = writer._publish_transaction_member

    def capture_intent(
        artifact_id: ArtifactID,
        document: dict[str, object],
        *,
        lease: object,
    ) -> Path:
        if document.get("status") == "pending":
            captured.append(deepcopy(document))
        return write_intent(artifact_id, document, lease=lease)  # type: ignore[arg-type]

    def interrupt_before_first_final(
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        raise RuntimeError("simulated process interruption after durable intent")

    monkeypatch.setattr(index, "write_transaction_intent", capture_intent)
    monkeypatch.setattr(writer, "_publish_transaction_member", interrupt_before_first_final)
    with pytest.raises(RuntimeError, match="simulated process interruption"):
        writer.put_bytes(payload, _options())

    assert len(captured) == 1
    pending = captured[0]
    assert pending["status"] == "pending"
    manifest_specs = pending["views"]
    assert isinstance(manifest_specs, list)
    default_spec = next(
        view
        for view in manifest_specs
        if isinstance(view, dict) and view["selector"] == "default"
    )
    default_stage = default_spec["manifest_stage"]
    assert isinstance(default_stage, str)
    expected_manifest_bytes = (root / default_stage).read_bytes()
    expected_default_digest = "sha256:" + hashlib.sha256(expected_manifest_bytes).hexdigest()
    assert default_spec["manifest_sha256"] == expected_default_digest

    stage_rel = pending["blob_stage"]
    assert isinstance(stage_rel, str)
    stage_dir = root / Path(stage_rel).parent
    quarantine = tmp_path / "quarantined-stage-after-simulated-process-loss"
    stage_dir.rename(quarantine)
    assert quarantine.is_dir()

    monkeypatch.setattr(writer, "_publish_transaction_member", publish_member)
    artifact_ref = writer.put_bytes(payload, _options())

    blob, default_manifest = _artifact_paths(root, artifact_ref.artifact_id)
    assert blob.read_bytes() == payload
    persisted_manifest_bytes = default_manifest.read_bytes()
    assert persisted_manifest_bytes == expected_manifest_bytes
    assert "sha256:" + hashlib.sha256(persisted_manifest_bytes).hexdigest() == (
        expected_default_digest
    )
    manifest = writer.get_manifest(artifact_ref)
    assert writer._manifests.profile_sha256(manifest) == default_spec[
        "manifest_profile_sha256"
    ]
    assert manifest.created_at.isoformat() == pending["manifest_created_at"]
    assert writer.get_bytes(artifact_ref) == payload


def test_import_retry_reuses_pinned_manifest_after_transaction_stage_quarantine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    payload = b"import retry must reuse exact manifest bytes and timestamp"
    source_ref = source.put_bytes(payload, _options())
    export = source.export_subgraph([source_ref], tmp_path / "source-export.tar.gz")
    target_root = tmp_path / "target"
    target = FileSystemCAS(target_root)
    captured: list[dict[str, Any]] = []
    index = target._ownership_index
    write_intent = index.write_transaction_intent
    publish_member = target._publish_transaction_member

    def capture_intent(
        artifact_id: ArtifactID,
        document: dict[str, Any],
        *,
        lease: Any,
    ) -> Path:
        if document.get("status") == "pending":
            captured.append(deepcopy(document))
        return write_intent(artifact_id, document, lease=lease)

    def interrupt_before_first_final(
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        raise RuntimeError("simulated import interruption after durable intent")

    monkeypatch.setattr(index, "write_transaction_intent", capture_intent)
    monkeypatch.setattr(target, "_publish_transaction_member", interrupt_before_first_final)
    with pytest.raises(RuntimeError, match="simulated import interruption"):
        target.import_subgraph(export.output_path, verify_integrity=True)

    assert len(captured) == 1
    pending = captured[0]
    manifest_spec = next(
        view
        for view in pending["views"]
        if view["selector"] == "default"
    )
    stage_ref = manifest_spec["manifest_stage"]
    assert isinstance(stage_ref, str)
    expected_manifest = source.get_manifest_bytes(source_ref)
    assert hashlib.sha256(expected_manifest).hexdigest() == manifest_spec[
        "manifest_sha256"
    ].removeprefix("sha256:")
    transaction_stage = target_root / Path(pending["blob_stage"]).parent
    quarantined_stage = tmp_path / "quarantined-import-transaction-stage"
    transaction_stage.rename(quarantined_stage)
    assert quarantined_stage.is_dir()

    monkeypatch.setattr(target, "_publish_transaction_member", publish_member)
    target.import_subgraph(export.output_path, verify_integrity=True)

    _blob, default_manifest = _artifact_paths(target_root, source_ref.artifact_id)
    assert default_manifest.read_bytes() == expected_manifest
    assert target.get_manifest(source_ref).created_at.isoformat() == pending[
        "manifest_created_at"
    ]
    assert target.get_bytes(source_ref) == payload


def test_exact_view_import_uses_deny_only_owner_transaction_and_exact_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    payload = b"exact-view imports must publish through the CAS owner transaction"
    source_ref = source.put_bytes(payload, _options())
    manifest_bytes = source.get_manifest_bytes(source_ref)
    target_root = tmp_path / "target"
    target = FileSystemCAS(target_root).for_tenant("tenant-exact-view")
    index = target._ownership_index
    captured: list[dict[str, Any]] = []
    write_intent = index.write_transaction_intent
    publish_member = target._publish_transaction_member

    def capture_intent(
        artifact_id: ArtifactID,
        document: dict[str, Any],
        *,
        lease: Any,
    ) -> Path:
        if document.get("status") == "pending":
            captured.append(deepcopy(document))
        return write_intent(artifact_id, document, lease=lease)

    def interrupt_before_first_final(
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        raise RuntimeError("simulated exact-view interruption after durable intent")

    monkeypatch.setattr(index, "write_transaction_intent", capture_intent)
    monkeypatch.setattr(target, "_publish_transaction_member", interrupt_before_first_final)
    with pytest.raises(RuntimeError, match="simulated exact-view interruption"):
        target.import_exact_view(
            payload,
            manifest_bytes,
            artifact_id=source_ref,
        )

    assert len(captured) == 1
    pending = captured[0]
    assert pending["status"] == "pending"
    assert pending["mode"] == "import"
    with pytest.raises(ArtifactOwnershipError) as refusal:
        target.get_bytes(source_ref)
    assert getattr(refusal.value, "code", None) == "artifact_transaction_pending"

    monkeypatch.setattr(target, "_publish_transaction_member", publish_member)
    imported_ref = target.import_exact_view(
        payload,
        manifest_bytes,
        artifact_id=source_ref,
    )

    blob, default_manifest = _artifact_paths(target_root, source_ref.artifact_id)
    assert blob.read_bytes() == payload
    assert default_manifest.read_bytes() == manifest_bytes
    assert target.get_manifest(imported_ref).created_at.isoformat() == pending[
        "manifest_created_at"
    ]
    assert target.get_bytes(imported_ref) == payload
    assert target._ownership_index.is_owned_by(
        source_ref.artifact_id,
        tenant_id="tenant-exact-view",
    )
