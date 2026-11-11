from __future__ import annotations

import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.run_index import RunIndexService

TENANT_ID = "tenant-run-index"
CELL_ID = "cell-run-index"


def _persist_owned_run(
    store: FileSystemCAS,
    core_runs_root: Path,
    registry_ref: ArtifactRef,
    *,
    marker: str,
) -> tuple[str, str]:
    run_id = f"R_run_index_{marker}"
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        ref = store.put_json(
            {"marker": marker},
            PutOptions(
                kind="test.run_index.root",
                media_type="application/json",
                schema=SchemaInfo(name="test.run_index.root", version="1.0"),
            ),
            return_selected_profile=True,
        )
        store.record_artifact_owner(
            ref.artifact_id,
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
            writer="test_run_index_generation",
        )
        run = RunContext.start(
            store,
            registry_ref,
            producer=ProducerInfo(component="tests.run_index", version="1.0"),
            run_dir=core_runs_root / run_id,
            run_id=run_id,
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
        )
        run.add_output(ref)
        manifest_ref = run.finalize(status="completed")
        store.record_artifact_owner(
            manifest_ref.artifact_id,
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
            writer="test_run_index_generation",
        )
    return run_id, str(ref.artifact_id)


def _store_and_registry(tmp_path: Path) -> tuple[FileSystemCAS, Path, ArtifactRef]:
    store = FileSystemCAS(tmp_path / "cas", tenant_id=TENANT_ID, cell_id=CELL_ID)
    core_runs_root = tmp_path / "runs"
    core_runs_root.mkdir()
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        registry_ref = store.put_json(
            {"registry": {}},
            PutOptions(
                kind="core.registry_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="core.registry_bundle", version="1.0"),
            ),
            return_selected_profile=True,
        )
    return store, core_runs_root, registry_ref


def test_catalogue_and_owner_lookup_extend_beyond_decoded_cache_limit(tmp_path: Path) -> None:
    store, core_runs_root, registry_ref = _store_and_registry(tmp_path)
    target_run_id = ""
    target_artifact_id = ""
    for index in range(3):
        run_id, artifact_id = _persist_owned_run(
            store,
            core_runs_root,
            registry_ref,
            marker=f"catalogue-{index}",
        )
        if run_id > target_run_id:
            target_run_id = run_id
            target_artifact_id = artifact_id

    index = RunIndexService(
        store=store,
        core_runs_root=core_runs_root,
        max_cached_runs=1,
    )

    summaries, page = index.list_runs(limit=2, tenant_id=TENANT_ID)
    visible_run_ids = {summary.run_id for summary in summaries}
    cursor = page.next_cursor
    while cursor is not None:
        summaries, next_page = index.list_runs(
            limit=2,
            cursor=cursor,
            tenant_id=TENANT_ID,
        )
        assert next_page.total == page.total
        visible_run_ids.update(summary.run_id for summary in summaries)
        cursor = next_page.next_cursor
    assert target_run_id in visible_run_ids
    assert page.total >= 3
    assert index.get_run(target_run_id).details.tenant_id == TENANT_ID
    assert index.get_artifact_tenant(target_artifact_id) == TENANT_ID
    assert len(index._snapshot.decoded_cache) <= 1

    shutil.rmtree(core_runs_root / target_run_id)
    index.refresh(force=True)
    with pytest.raises(KeyError):
        index.get_run(target_run_id)
    assert index.get_artifact_tenant(target_artifact_id) is None
    _, reduced_page = index.list_runs(limit=200, tenant_id=TENANT_ID)
    assert reduced_page.total == page.total - 1


def test_incremental_refresh_preserves_lru_for_hot_unchanged_runs(tmp_path: Path) -> None:
    store, core_runs_root, registry_ref = _store_and_registry(tmp_path)
    for marker in ("a", "b", "c"):
        _persist_owned_run(store, core_runs_root, registry_ref, marker=marker)

    index = RunIndexService(
        store=store,
        core_runs_root=core_runs_root,
        max_cached_runs=2,
    )
    index.refresh(force=True)
    hot_run_id = "R_run_index_a"
    index.get_run(hot_run_id)
    assert hot_run_id in index._snapshot.decoded_cache

    _persist_owned_run(store, core_runs_root, registry_ref, marker="d")
    index.refresh(force=True)

    assert hot_run_id in index._snapshot.decoded_cache
    assert len(index._snapshot.decoded_cache) == 2


def test_forced_refresh_cannot_publish_an_older_run_generation(tmp_path: Path, monkeypatch) -> None:
    store, core_runs_root, registry_ref = _store_and_registry(tmp_path)
    run_id, artifact_id = _persist_owned_run(store, core_runs_root, registry_ref, marker="race")
    index = RunIndexService(store=store, core_runs_root=core_runs_root)
    index.refresh(force=True)
    record = index.get_run(run_id)
    trace_path = record.trace_path
    assert trace_path is not None

    original_refresh_index = index._refresh_index_incremental
    old_built = threading.Event()
    release_old = threading.Event()
    new_builder_started = threading.Event()

    def controlled_refresh():
        if threading.current_thread().name == "run-index-new":
            new_builder_started.set()
        result = original_refresh_index()
        if threading.current_thread().name == "run-index-old":
            old_built.set()
            if not release_old.wait(timeout=10):
                raise TimeoutError("run_index_old_refresh_release_missing")
        return result

    monkeypatch.setattr(index, "_refresh_index_incremental", controlled_refresh)

    with ThreadPoolExecutor(max_workers=2) as pool:

        def refresh_old_generation() -> None:
            threading.current_thread().name = "run-index-old"
            index.refresh(force=True)

        def refresh_new_generation() -> None:
            threading.current_thread().name = "run-index-new"
            index.refresh(force=True)

        old_refresh = pool.submit(refresh_old_generation)
        assert old_built.wait(timeout=10)

        before = trace_path.stat()
        first_record = trace_path.read_text(encoding="utf-8").splitlines()[0]
        with trace_path.open("a", encoding="utf-8") as stream:
            stream.write(first_record + "\n")
        os.utime(trace_path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))

        second_refresh_started = threading.Event()

        def start_new_refresh() -> None:
            second_refresh_started.set()
            refresh_new_generation()

        new_refresh = pool.submit(start_new_refresh)
        try:
            assert second_refresh_started.wait(timeout=10)
            builder_entered_before_release = new_builder_started.wait(timeout=0.2)
        finally:
            release_old.set()
        old_refresh.result(timeout=10)
        new_refresh.result(timeout=10)

    assert not builder_entered_before_release
    refreshed = index.get_run(run_id)
    assert refreshed.sort_mtime_ns == trace_path.stat().st_mtime_ns
    assert index.get_artifact_tenant(artifact_id) == TENANT_ID
