"""Behavioral tests proposed with the tenant CAS quota admission patch.

These tests are packet content only. They have not been imported or executed in
this task; Root owns native execution after applying and reviewing the patch.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.quota_enforcer import QuotaExceededError
from polisyos.core.security.tenant_quota import TenantQuotaLimits
from polisyos.fabric.storage import tenant_cas as tenant_cas_module
from polisyos.fabric.storage.tenant_cas import TenantScopedCAS

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


class _ProcessGate(Protocol):
    def wait(self, timeout: float | None = None) -> int: ...


class _OutcomeQueue(Protocol):
    def put(self, item: tuple[str, str | None, str | None]) -> None: ...


class _WorkerStageQueue(Protocol):
    def put(self, item: tuple[int, int, str]) -> None: ...


@pytest.fixture(autouse=True)
def _optional_quota_admission_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("E02_REMOVE_TENANT_QUOTA_ADMISSION"):
        monkeypatch.setattr(
            FileSystemCAS,
            "_admit_storage_members",
            lambda _self, _members: None,
        )


def _options(kind: str = "tests.tenant-quota") -> PutOptions:
    return PutOptions(
        kind=kind,
        media_type="application/octet-stream",
        schema=SchemaInfo(name=kind, version="1.0"),
    )


def _materialized_bytes(root: Path) -> int:
    cas_root = root / "artifacts" / "sha256"
    return sum(path.stat().st_size for path in cas_root.rglob("*") if path.is_file())


def test_import_quota_refusal_precedes_first_final_member_and_preserves_prior_owner(
    tmp_path: Path,
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    incoming = source.put_bytes(b"new import payload", _options("tests.import.incoming"))
    export = source.export_subgraph([incoming], tmp_path / "export")

    initial = TenantScopedCAS(tmp_path / "tenant-root", tenant_id=TENANT)
    prior = initial.put_bytes(b"readable prior payload", _options("tests.import.prior"))
    baseline = _materialized_bytes(initial.root)
    limit = baseline + 1
    limited = TenantScopedCAS(
        tmp_path / "tenant-root",
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=limit),
    )
    before = _materialized_bytes(limited.root)

    if os.environ.get("E02_REMOVE_TENANT_QUOTA_ADMISSION"):
        report = limited.import_subgraph(export.output_path, verify_integrity=True)
        reopened = TenantScopedCAS(tmp_path / "tenant-root", tenant_id=TENANT)
        assert reopened.has(incoming.artifact_id)
        assert reopened.get_bytes(incoming) == b"new import payload"
        actual = _materialized_bytes(reopened.root)
        assert actual > limit
        pytest.fail(
            "property-removal witness: exact import is visible and readable after admission "
            f"was removed; imported_refs={report.imported_refs!r}; bytes={actual}; limit={limit}",
            pytrace=False,
        )

    with pytest.raises(QuotaExceededError, match="storage_bytes"):
        limited.import_subgraph(export.output_path, verify_integrity=True)

    reopened = TenantScopedCAS(tmp_path / "tenant-root", tenant_id=TENANT)
    assert reopened.iter_artifact_ids() == [prior.artifact_id]
    assert reopened.get_bytes(prior) == b"readable prior payload"
    assert reopened.has(incoming.artifact_id) is False
    assert _materialized_bytes(reopened.root) == before


def test_import_aggregates_all_new_members_before_publishing_any_artifact(
    tmp_path: Path,
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    first = source.put_bytes(b"first import member", _options("tests.import.first"))
    second = source.put_bytes(b"second import member", _options("tests.import.second"))
    export = source.export_subgraph([first, second], tmp_path / "export")
    target = TenantScopedCAS(
        tmp_path / "tenant-root",
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=1),
    )
    before = _materialized_bytes(target.root)

    with pytest.raises(QuotaExceededError, match="storage_bytes"):
        target.import_subgraph(export.output_path, verify_integrity=True)

    reopened = TenantScopedCAS(tmp_path / "tenant-root", tenant_id=TENANT)
    assert reopened.iter_artifact_ids() == []
    assert _materialized_bytes(reopened.root) == before


def test_exact_reimport_is_zero_delta_when_tenant_is_at_quota(tmp_path: Path) -> None:
    first = TenantScopedCAS(tmp_path / "tenant-root", tenant_id=TENANT)
    ref = first.put_bytes(b"exact already-owned", _options())
    export = first.export_subgraph([ref], tmp_path / "export")
    full_quota = _materialized_bytes(first.root)
    at_limit = TenantScopedCAS(
        tmp_path / "tenant-root",
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=full_quota),
    )

    result = at_limit.import_subgraph(export.output_path, verify_integrity=True)

    assert ref in result.imported_refs
    assert _materialized_bytes(at_limit.root) == full_quota
    assert at_limit.get_bytes(ref) == b"exact already-owned"


def test_profile_only_import_charges_exact_missing_manifest_without_recharging_blob(
    tmp_path: Path,
) -> None:
    payload = b"same content, distinct manifest profile"
    source = FileSystemCAS(tmp_path / "source")
    source_ref = source.put_bytes(payload, _options("tests.profile.source"))
    export = source.export_subgraph([source_ref], tmp_path / "export")

    initial = TenantScopedCAS(tmp_path / "tenant-root", tenant_id=TENANT)
    original = initial.put_bytes(payload, _options("tests.profile.original"))
    assert original.artifact_id == source_ref.artifact_id
    baseline = _materialized_bytes(initial.root)
    source_manifest = source._manifest_path_for_ref(
        source_ref.artifact_id, source_ref.manifest_profile_sha256
    ).read_bytes()
    source_manifest_model = ArtifactManifest.model_validate_json(source_manifest)
    selected_profile = source._manifests.profile_sha256(source_manifest_model)
    selected_ref = ArtifactRef(
        artifact_id=source_ref.artifact_id,
        kind=source_ref.kind,
        media_type=source_ref.media_type,
        manifest_profile_sha256=selected_profile,
    )
    original_default_path = initial._cas._manifest_path_for_ref(original.artifact_id, None)
    original_default_bytes = original_default_path.read_bytes()
    shared_blob_path = initial._cas._paths(original.artifact_id)[0]
    shared_blob_bytes = shared_blob_path.read_bytes()
    limited = TenantScopedCAS(
        tmp_path / "tenant-root",
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=baseline + len(source_manifest)),
    )

    report = limited.import_subgraph(export.output_path, verify_integrity=True)

    assert report.imported_refs == (selected_ref,)
    assert limited.get_bytes(original) == payload
    assert limited.get_bytes(selected_ref) == payload
    assert original_default_path.read_bytes() == original_default_bytes
    selected_manifest_path = limited._cas._manifest_path_for_ref(
        source_ref.artifact_id, selected_profile
    )
    assert selected_manifest_path.read_bytes() == source_manifest
    assert shared_blob_path.read_bytes() == shared_blob_bytes == payload
    assert _materialized_bytes(limited.root) == baseline + len(source_manifest)


def test_independent_tenant_instances_serialize_shared_storage_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tenant-root"
    limit = 20_000
    stores = [
        TenantScopedCAS(
            root,
            tenant_id=TENANT,
            quota_limits=TenantQuotaLimits(max_storage_bytes=limit),
        )
        for _ in range(2)
    ]
    gate = threading.Barrier(2)
    if os.environ.get("E02_REMOVE_TENANT_STORAGE_LOCK"):
        from contextlib import contextmanager

        @contextmanager
        def unlocked_mutation(self: TenantScopedCAS) -> Iterator[None]:
            self._quota.reconcile_storage_usage(self._directory_size(self.root))
            core = cast("Any", self._cas)
            core._storage_admission = tenant_cas_module._TenantQuotaAdmission(
                self.root, self._quota
            )
            try:
                yield
            finally:
                core._storage_admission = None
                self._quota.reconcile_storage_usage(self._directory_size(self.root))

        monkeypatch.setattr(TenantScopedCAS, "_storage_mutation", unlocked_mutation)
        original_admit = store_module.FileSystemCAS._admit_storage_members
        admissions = threading.Barrier(2)

        def overlap_admission(self: FileSystemCAS, members: list[Any]) -> None:
            original_admit(self, members)
            admissions.wait(timeout=5)

        monkeypatch.setattr(store_module.FileSystemCAS, "_admit_storage_members", overlap_admission)

    def write(index: int) -> str:
        gate.wait(timeout=5)
        try:
            stores[index].put_bytes(
                bytes([index + 1]) * 12_000,
                _options(f"tests.concurrent.{index}"),
            )
        except QuotaExceededError:
            return "quota"
        return "written"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(write, range(2)))

    assert outcomes.count("written") == 1
    assert outcomes.count("quota") == 1
    assert len(TenantScopedCAS(root, tenant_id=TENANT).iter_artifact_ids()) == 1
    assert _materialized_bytes(TenantScopedCAS(root, tenant_id=TENANT).root) <= limit


def _cross_process_put_worker(
    root: str,
    index: int,
    gate: _ProcessGate,
    outcomes: _OutcomeQueue,
    stages: _WorkerStageQueue,
    limit: int,
) -> None:
    """Race one real write from a separate process against the shared tenant root."""

    def report(stage: str) -> None:
        stages.put((index, os.getpid(), stage))

    report("worker_started")
    try:
        report("store_construction_started")
        store = TenantScopedCAS(
            root,
            tenant_id=TENANT,
            quota_limits=TenantQuotaLimits(max_storage_bytes=limit),
        )
        report("store_constructed")
        report("barrier_waiting")
        gate.wait(timeout=20)
        report("barrier_released")
        report("write_started")
        ref = store.put_bytes(
            bytes([index + 1]) * 12_000,
            _options(f"tests.cross-process.{index}"),
        )
    except QuotaExceededError:
        report("quota_refused")
        outcomes.put(("quota", None, None))
    except BaseException as exc:
        report(f"error:{type(exc).__name__}")
        outcomes.put(("error", type(exc).__name__, str(exc)))
    else:
        report("write_committed")
        outcomes.put(("written", str(ref.artifact_id), None))


def test_cross_process_instances_serialize_shared_storage_budget(tmp_path: Path) -> None:
    root = tmp_path / "tenant-root"
    initial = TenantScopedCAS(
        root,
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=100_000),
    )
    prior = initial.put_bytes(
        b"prior cross-process generation",
        _options("tests.cross-process.prior"),
    )
    baseline = _materialized_bytes(initial.root)
    limit = baseline + 20_000

    context = mp.get_context("spawn")
    gate = context.Barrier(2)
    outcomes = context.Queue()
    stages = context.Queue()
    processes = [
        context.Process(
            target=_cross_process_put_worker,
            args=(str(root), index, gate, outcomes, stages, limit),
        )
        for index in range(2)
    ]
    started = []
    results = []
    outcome_timeout = False
    stages_at_timeout = []
    try:
        for process in processes:
            process.start()
            started.append(process)
        results = [outcomes.get(timeout=30) for _ in processes]
    except queue.Empty:
        outcome_timeout = True
        deadline = time.monotonic() + 1.0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                stages_at_timeout.append(stages.get(timeout=remaining))
            except queue.Empty:
                break
    finally:
        for process in started:
            if outcome_timeout and process.is_alive():
                process.terminate()
            process.join(timeout=2 if outcome_timeout else 10)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        outcomes.close()
        outcomes.join_thread()

    stage_events = list(stages_at_timeout)
    while True:
        try:
            stage_events.append(stages.get_nowait())
        except queue.Empty:
            break
    stages.close()
    stages.join_thread()
    process_states = [
        {"pid": process.pid, "exitcode": process.exitcode, "alive": process.is_alive()}
        for process in processes
    ]
    assert not outcome_timeout, (
        "cross-process quota workers did not report both outcomes within 30 seconds; "
        f"stages={stage_events!r}; processes={process_states!r}"
    )
    assert all(process.exitcode == 0 for process in processes)
    assert sorted(result[0] for result in results) == ["quota", "written"]
    winner = next(result[1] for result in results if result[0] == "written")
    reopened = TenantScopedCAS(
        root,
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=limit),
    )
    artifact_ids = reopened.iter_artifact_ids()
    new_ids = [artifact_id for artifact_id in artifact_ids if artifact_id != prior.artifact_id]
    assert len(new_ids) == 1
    assert str(new_ids[0]) == winner
    assert reopened.get_bytes(new_ids[0]) in {bytes([1]) * 12_000, bytes([2]) * 12_000}
    assert reopened.get_bytes(prior) == b"prior cross-process generation"
    assert _materialized_bytes(reopened.root) <= limit


def test_concurrent_import_of_same_archive_is_zero_delta_after_first_publish(
    tmp_path: Path,
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(b"one immutable import generation", _options("tests.same-import"))
    export = source.export_subgraph([ref], tmp_path / "export")

    control = TenantScopedCAS(tmp_path / "control", tenant_id=TENANT)
    control.import_subgraph(export.output_path, verify_integrity=True)
    exact_generation_bytes = _materialized_bytes(control.root)

    root = tmp_path / "tenant-root"
    stores = [
        TenantScopedCAS(
            root,
            tenant_id=TENANT,
            quota_limits=TenantQuotaLimits(max_storage_bytes=exact_generation_bytes),
        )
        for _ in range(2)
    ]
    gate = threading.Barrier(2)

    def import_same_archive(store: TenantScopedCAS) -> tuple[Any, ...]:
        gate.wait(timeout=10)
        report = store.import_subgraph(export.output_path, verify_integrity=True)
        return report.imported_refs

    with ThreadPoolExecutor(max_workers=2) as pool:
        imported_refs = list(pool.map(import_same_archive, stores))

    assert imported_refs[0]
    assert imported_refs[1] == imported_refs[0]
    assert all(imported_ref.artifact_id == ref.artifact_id for imported_ref in imported_refs[0])
    reopened = TenantScopedCAS(
        root,
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=exact_generation_bytes),
    )
    assert reopened.iter_artifact_ids() == [ref.artifact_id]
    assert reopened.get_bytes(ref) == b"one immutable import generation"
    assert _materialized_bytes(reopened.root) == exact_generation_bytes


def test_put_bytes_and_json_reconcile_exact_materialized_cas_bytes(tmp_path: Path) -> None:
    store = TenantScopedCAS(
        tmp_path / "tenant-root",
        tenant_id=TENANT,
        quota_limits=TenantQuotaLimits(max_storage_bytes=100_000),
    )
    store.put_bytes(b"payload", _options("tests.put.bytes"))
    store.put_json({"payload": "json"}, _options("tests.put.json"))

    assert store._quota.state.storage_bytes_used == _materialized_bytes(store.root)


def test_sign_on_put_sidecar_is_included_in_the_prepublication_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts.signing import Ed25519Signer, KeyPair, SigningConfig

    signer = Ed25519Signer.from_pem(KeyPair.generate().private_pem())

    def signed_store(root: Path, limit: int) -> TenantScopedCAS:
        store = TenantScopedCAS(
            root,
            tenant_id=TENANT,
            quota_limits=TenantQuotaLimits(max_storage_bytes=limit),
        )
        core = cast("Any", store._cas)
        core._signing_config = SigningConfig(
            enabled=True,
            sign_on_put=True,
            default_identity="quota-test",
        )
        monkeypatch.setattr(core, "_ensure_default_signer", lambda: signer)
        return store

    payload = b"the signature sidecar is billable too"
    successful = signed_store(tmp_path / "control", 100_000)
    ref = successful.put_bytes(payload, _options("tests.signed-quota"))
    exact_generation_size = _materialized_bytes(successful.root)
    assert successful._cas._sig_path(ref.artifact_id).is_file()

    blocked = signed_store(tmp_path / "blocked", exact_generation_size - 1)
    with pytest.raises(QuotaExceededError, match="storage_bytes"):
        blocked.put_bytes(payload, _options("tests.signed-quota"))

    assert blocked.iter_artifact_ids() == []
    assert _materialized_bytes(blocked.root) == 0
