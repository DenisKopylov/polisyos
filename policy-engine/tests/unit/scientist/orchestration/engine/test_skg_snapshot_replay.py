"""Real DuckDB/CAS controls for saved operational SKG source replay.

These fixtures assert numerical read/replay only. They do not certify literature
quality, source issuance, institutional authority, or scientific reproducibility.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import multiprocessing as mp
import os
import stat
import subprocess
import sys
import time as _time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import duckdb
import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactIntegrityError,
    ArtifactOwnershipError,
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.data_forge.read_api.academic import (
    ParameterSelector,
    PreparedSKGRead,
    SKGQuery,
)
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.parameters import load_context_adaptive_parameter_bundle
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine import executor as executor_module
from polisyos.scientist.orchestration.engine import retry as retry_module
from polisyos.scientist.orchestration.engine import skg_snapshot
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError, WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutor,
    _bind_retained_workflow_input,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_sync
from polisyos.scientist.orchestration.engine.runner._activity_worker import (
    _build_timeout_worker_context,
    run_node_in_worker,
    run_node_in_worker_sync,
)
from polisyos.scientist.orchestration.engine.runner.serialization import (
    serialize_timeout_context,
)
from polisyos.scientist.orchestration.engine.skg_snapshot import (
    SNAPSHOT_INPUT_KEY,
    RetainedSKGSnapshotError,
    load_retained_skg_snapshot,
    materialize_retained_skg_snapshot,
    prepare_retained_skg_read,
    retain_prepared_skg_read,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.replay import replay_dead_letter
from tests._helpers.b61_timeout_worker import run_delayed_timeout_task_after_release

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutionResult


_CONTEXT = {"context_id": "us-2025", "countries": ["US"], "publication_year": 2025}


def _seed(path: Path, value: float) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE ac_skg_versions(version_id INTEGER)")
        con.execute("INSERT INTO ac_skg_versions VALUES (7)")
        con.execute("""
            CREATE TABLE ac_skg_simulation_parameters (
                numeric_id VARCHAR, openalex_id VARCHAR, canonical_name VARCHAR,
                estimate_type VARCHAR, point_estimate DOUBLE, estimate_sign VARCHAR,
                unit VARCHAR, evidence_strength VARCHAR, confidence_interval_json VARCHAR,
                std_error DOUBLE, source_layer VARCHAR, uncertainty_source VARCHAR,
                quality_flags_json VARCHAR, linked_claim_ids_json VARCHAR,
                linked_edges_json VARCHAR, context_json VARCHAR
            )
        """)
        con.execute(
            """INSERT INTO ac_skg_simulation_parameters VALUES
            ('retained-number', 'W1', 'fiscal_multiplier', 'point', ?, 'positive',
             'ratio', 'rct', '[1.0, 2.0]', NULL, 'simulation_ready',
             'confidence_interval', '[]', '[]', '[]', ?)""",
            [value, json.dumps(_CONTEXT)],
        )


def _value(prepared: PreparedSKGRead) -> float:
    parameter, _ = ParameterSelector(prepared.query).select_for_context(
        "fiscal_multiplier",
        ContextProfile.model_validate(_CONTEXT),
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    assert parameter is not None
    return float(parameter.value)


def _captured(tmp_path: Path) -> tuple[Path, FileSystemCAS, ArtifactRef]:
    source = tmp_path / "live.duckdb"
    _seed(source, 1.25)
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    prepared = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    try:
        assert _value(prepared) == 1.25
        ref = retain_prepared_skg_read(store, prepared)
    finally:
        prepared.close()
    return source, store, ref


def _intercept_cas_put_bytes(
    monkeypatch: pytest.MonkeyPatch,
    store: FileSystemCAS,
    *,
    after_write: Callable[[], None] | None = None,
) -> list[ArtifactWriteOptions]:
    """Observe real CAS byte writes while forwarding the selected-profile option."""
    original = store.put_bytes
    observed: list[ArtifactWriteOptions] = []

    def intercept(
        payload: bytes,
        options: ArtifactWriteOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        ref = original(
            payload,
            options,
            return_selected_profile=return_selected_profile,
        )
        observed.append(options)
        if after_write is not None:
            after_write()
        return ref

    monkeypatch.setattr(store, "put_bytes", intercept)
    return observed


def test_capture_selects_actual_manifest_profiles_for_descriptor_and_chunks(tmp_path: Path) -> None:
    _, store, ref = _captured(tmp_path)
    snapshot = load_retained_skg_snapshot(store, ref)
    for selected in (ref, *(chunk.ref for chunk in snapshot.chunks)):
        assert selected.manifest_profile_sha256 is not None
        assert selected.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            store.get_manifest(selected)
        )
        assert store.verify(selected).ok
    descriptor_manifest = json.loads(
        store.get_raw_manifest_bytes(ref, manifest_profile_sha256=ref.manifest_profile_sha256)
    )
    assert isinstance(descriptor_manifest.get("canon"), dict)


def test_attempt_facade_persists_selected_source_for_a_fresh_reader(tmp_path: Path) -> None:
    source = tmp_path / "live.duckdb"
    _seed(source, 1.25)
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    authority = retry_module._AttemptAuthority(None)
    facade = retry_module._AttemptFacade(
        store,
        authority,
        write_methods=frozenset({"put_bytes", "put_json"}),
        raise_on_revoked_write=True,
    )
    prepared = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    try:
        assert _value(prepared) == 1.25
        ref = retain_prepared_skg_read(facade, prepared)
    finally:
        prepared.close()
    assert prepared._closed is True
    assert ref.manifest_profile_sha256 is not None
    raw_manifest = json.loads(
        store.get_raw_manifest_bytes(ref, manifest_profile_sha256=ref.manifest_profile_sha256)
    )
    assert isinstance(raw_manifest.get("canon"), dict)

    fresh_store = FileSystemCAS(store.root, ownership_enforced=False)
    replay = prepare_retained_skg_read(
        fresh_store,
        ref,
        directory=tmp_path / "fresh-reader",
        index_dir=tmp_path,
    )
    try:
        assert _value(replay) == 1.25
        assert replay.source_generation_matches()
    finally:
        replay.close()
    assert replay._closed is True

    before = tuple(sorted(str(artifact_id) for artifact_id in store.iter_artifact_ids()))
    authority.revoke()
    with pytest.raises(retry_module._AttemptWriteDeniedError):
        facade.put_bytes(b"late-write", object(), return_selected_profile=True)
    assert tuple(sorted(str(artifact_id) for artifact_id in store.iter_artifact_ids())) == before


def test_named_but_inert_selected_profile_writer_is_refused(tmp_path: Path) -> None:
    class _InertSelectedProfileCAS(FileSystemCAS):
        def __init__(self, root: Path) -> None:
            super().__init__(root, ownership_enforced=False)
            self.return_selected_profile_calls: list[bool] = []
            self.returned_refs: list[ArtifactRef] = []

        def put_json(
            self,
            obj: object,
            opts: ArtifactWriteOptions,
            canon_spec: Any = None,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            self.return_selected_profile_calls.append(return_selected_profile)
            ref = super().put_json(
                obj,
                opts,
                canon_spec,
                return_selected_profile=False,
            )
            self.returned_refs.append(ref)
            return ref

    source = tmp_path / "live.duckdb"
    _seed(source, 1.25)
    store = _InertSelectedProfileCAS(tmp_path / "cas")
    authority = retry_module._AttemptAuthority(None)
    facade = retry_module._AttemptFacade(
        store,
        authority,
        write_methods=frozenset({"put_bytes", "put_json"}),
        raise_on_revoked_write=True,
    )
    prepared = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    try:
        with pytest.raises(
            RetainedSKGSnapshotError,
            match="retained_skg_selected_written_ref_required",
        ):
            retain_prepared_skg_read(facade, prepared)
    finally:
        prepared.close()

    assert store.return_selected_profile_calls == [True]
    assert len(store.returned_refs) == 1
    returned = store.returned_refs[0]
    assert returned.manifest_profile_sha256 is None
    raw_manifest = json.loads(store.get_raw_manifest_bytes(returned))
    assert isinstance(raw_manifest.get("canon"), dict)


def test_selected_snapshot_reader_accepts_revocable_attempt_read_facade(tmp_path: Path) -> None:
    _, store, ref = _captured(tmp_path)
    authority = retry_module._AttemptAuthority(None)
    facade = retry_module._AttemptFacade(store, authority, write_methods=frozenset({"put_bytes"}))
    authority.revoke()

    prepared = prepare_retained_skg_read(
        facade,
        ref,
        directory=tmp_path / "attempt-reader",
        index_dir=tmp_path,
    )
    try:
        assert _value(prepared) == 1.25
    finally:
        prepared.close()


def test_descriptor_without_selected_profile_is_refused(tmp_path: Path) -> None:
    _, store, ref = _captured(tmp_path)
    legacy_selector = ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(RetainedSKGSnapshotError, match="descriptor_profile_required"):
        load_retained_skg_snapshot(store, legacy_selector)


def test_descriptor_with_malformed_present_profile_refuses_before_payload_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed-present CanonInfo remains a strict pre-payload refusal."""
    _, store, ref = _captured(tmp_path)
    original_raw_reader = store.get_raw_manifest_bytes
    original_payload_reader = store.get_bytes
    payload_reads: list[object] = []

    def malformed_raw_manifest(
        selector: object, *, manifest_profile_sha256: str | None = None
    ) -> bytes:
        raw_manifest = json.loads(
            original_raw_reader(selector, manifest_profile_sha256=manifest_profile_sha256)
        )
        canon = raw_manifest.get("canon")
        assert isinstance(canon, dict)
        canon["name"] = 7
        return json.dumps(raw_manifest, sort_keys=True, separators=(",", ":")).encode()

    def record_payload_read(*args: Any, **kwargs: Any) -> bytes:
        payload_reads.append(args[0] if args else None)
        return original_payload_reader(*args, **kwargs)

    monkeypatch.setattr(store, "get_raw_manifest_bytes", malformed_raw_manifest)
    monkeypatch.setattr(store, "get_bytes", record_payload_read)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"):
        load_retained_skg_snapshot(store, ref)
    assert payload_reads == []


@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_existing_descriptor_refuses_unavailable_retained_chunk_even_with_healthy_live_source(
    tmp_path: Path, fault: Literal["missing", "corrupt"]
) -> None:
    source, store, ref = _captured(tmp_path)
    snapshot = load_retained_skg_snapshot(store, ref)
    chunk_ref = snapshot.chunks[0].ref
    chunk_digest = chunk_ref.artifact_id.hex
    chunk_path = (
        store.root
        / "artifacts"
        / "sha256"
        / chunk_digest[:2]
        / chunk_digest[2:4]
        / f"{chunk_digest}.blob"
    )
    manifest_before = store.get_manifest(chunk_ref).model_dump_json()
    if fault == "missing":
        chunk_path.rename(tmp_path / "unavailable-retained-chunk.blob")
    else:
        original = chunk_path.read_bytes()
        chunk_path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    assert store.get_manifest(chunk_ref).model_dump_json() == manifest_before
    live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    try:
        assert _value(live) == 1.25
        assert live.source_generation_matches()
        with pytest.raises((ArtifactIntegrityError, FileNotFoundError)):
            retain_prepared_skg_read(store, live, existing_ref=ref)
    finally:
        live.close()


def test_saved_source_reads_old_parameter_after_real_live_replacement(tmp_path: Path) -> None:
    source, store, ref = _captured(tmp_path)
    replacement = tmp_path / "replacement.duckdb"
    _seed(replacement, 9.75)
    os.replace(replacement, source)
    live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    try:
        assert _value(live) == 9.75
    finally:
        live.close()
    fresh_store = FileSystemCAS(store.root, ownership_enforced=False)
    saved = prepare_retained_skg_read(
        fresh_store, ref, directory=tmp_path / "restored", index_dir=tmp_path
    )
    try:
        assert _value(saved) == 1.25
        assert saved.source_snapshot_sha256 == load_retained_skg_snapshot(store, ref).source_sha256
        assert saved.db_path != source
        assert saved.source_generation_matches()
    finally:
        saved.close()


def test_snapshot_replays_with_live_path_absent_and_fresh_process(tmp_path: Path) -> None:
    source, store, ref = _captured(tmp_path)
    source.rename(tmp_path / "replaced-original.duckdb")
    program = """
import json, sys
from pathlib import Path
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.data_forge.read_api.academic import ParameterSelector
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.scientist.orchestration.engine.skg_snapshot import prepare_retained_skg_read
store = FileSystemCAS(Path(sys.argv[1]), ownership_enforced=False)
ref = ArtifactRef.model_validate_json(sys.argv[2])
prepared = prepare_retained_skg_read(
    store, ref, directory=Path(sys.argv[3]), index_dir=Path(sys.argv[3])
)
try:
    parameter, _ = ParameterSelector(prepared.query).select_for_context(
        "fiscal_multiplier",
        ContextProfile.model_validate(json.loads(sys.argv[4])),
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    print(json.dumps({
        "value": float(parameter.value),
        "source_sha256": prepared.source_snapshot_sha256,
        "source_path": str(prepared.db_path),
        "generation_matches": prepared.source_generation_matches(),
    }))
finally:
    prepared.close()
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            str(store.root),
            ref.model_dump_json(),
            str(tmp_path / "fresh-process"),
            json.dumps(_CONTEXT),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0
    observed = json.loads(result.stdout.strip().splitlines()[-1])
    assert observed["value"] == 1.25
    assert observed["source_sha256"] == load_retained_skg_snapshot(store, ref).source_sha256
    assert observed["generation_matches"] is True
    assert not source.exists()


def test_exact_existing_descriptor_does_not_write_source_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, store, ref = _captured(tmp_path)
    prepared = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    writes = _intercept_cas_put_bytes(monkeypatch, store)
    try:
        assert retain_prepared_skg_read(store, prepared, existing_ref=ref) == ref
        assert writes == []
        assert _value(prepared) == 1.25
    finally:
        prepared.close()


def test_capture_refuses_actual_source_generation_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.duckdb"
    replacement = tmp_path / "new.duckdb"
    _seed(source, 1.25)
    _seed(replacement, 9.75)
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    prepared = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    replaced = False

    def replace_source_after_write() -> None:
        nonlocal replaced
        if not replaced:
            replaced = True
            os.replace(replacement, source)

    _intercept_cas_put_bytes(monkeypatch, store, after_write=replace_source_after_write)
    try:
        with pytest.raises(RetainedSKGSnapshotError):
            retain_prepared_skg_read(store, prepared)
        assert replaced
        assert not prepared.source_generation_matches()
    finally:
        prepared.close()


def test_missing_or_corrupt_selected_descriptor_never_reads_live_source(tmp_path: Path) -> None:
    source, store, ref = _captured(tmp_path)
    snapshot = load_retained_skg_snapshot(store, ref)
    manifest = store.get_manifest(ref)
    options = replace(
        ArtifactWriteOptions(
            kind=ref.kind,
            media_type=ref.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
        ),
        inputs=manifest.inputs,
    )
    wrong = store.put_json(
        snapshot.model_copy(update={"source_sha256": "0" * 64}).model_dump(mode="json"),
        options,
        return_selected_profile=True,
    )
    with pytest.raises(RetainedSKGSnapshotError, match="retained_skg_retained_digest_mismatch"):
        prepare_retained_skg_read(store, wrong, directory=tmp_path / "bad", index_dir=tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        load_retained_skg_snapshot(
            FileSystemCAS(tmp_path / "empty-cas", ownership_enforced=False), ref
        )
    assert source.exists()
    assert not (tmp_path / "bad" / f"{'0' * 64}.duckdb").exists()


def test_materialization_fsync_failure_does_not_publish_partial_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, store, ref = _captured(tmp_path)
    directory = tmp_path / "restore"
    directory.mkdir()
    snapshot = load_retained_skg_snapshot(store, ref)
    original = os.fsync

    def refuse_file_sync(descriptor: int) -> None:
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("injected materialization file fsync refusal")
        return original(descriptor)

    monkeypatch.setattr(skg_snapshot.os, "fsync", refuse_file_sync)
    with pytest.raises(OSError):
        materialize_retained_skg_snapshot(store, ref, directory=directory)
    assert not (directory / f"{snapshot.source_sha256}.duckdb").exists()
    monkeypatch.setattr(skg_snapshot.os, "fsync", original)
    saved = prepare_retained_skg_read(store, ref, directory=directory, index_dir=tmp_path)
    try:
        assert _value(saved) == 1.25
    finally:
        saved.close()


def test_materialized_corruption_is_refused_without_overwriting_it(tmp_path: Path) -> None:
    _, store, ref = _captured(tmp_path)
    directory = tmp_path / "restore"
    path = materialize_retained_skg_snapshot(store, ref, directory=directory)
    original = path.read_bytes()
    damaged = bytes([original[0] ^ 1]) + original[1:]
    path.write_bytes(damaged)
    with pytest.raises(RetainedSKGSnapshotError):
        prepare_retained_skg_read(store, ref, directory=directory, index_dir=tmp_path)
    assert path.read_bytes() == damaged


@contextmanager
def _access_scope_context(access_scope: AccessScope | None) -> Iterator[None]:
    token = set_current_access_scope(access_scope)
    try:
        yield
    finally:
        reset_current_access_scope(token)


def _workflow_fixture(
    tmp_path: Path,
    *,
    access_scope: AccessScope | None = None,
) -> tuple[Path, FileSystemCAS, RunContext, ExecutionContext, ExperimentState, ArtifactRef]:
    source = tmp_path / "live.duckdb"
    _seed(source, 1.25)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("retained-tenant", "retained-cell")
    registry_bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store,
        registry_bundle.bundle_ref,
        run_id="R_retained_skg",
        tenant_id="retained-tenant",
        cell_id="retained-cell",
        access_scope=access_scope,
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("retained-skg"))
    graph_ref = persist_causal_graph_model(
        _ensure_ir_artifact_store(store),
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id=run.run_manifest.run_id,
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": _CONTEXT,
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(source),
        },
    )
    prepared = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
    try:
        ref = retain_prepared_skg_read(store, prepared)
    finally:
        prepared.close()
    replacement = tmp_path / "replacement.duckdb"
    _seed(replacement, 9.75)
    os.replace(replacement, source)
    return source, store, run, ctx, state, ref


def _spawn_timeout_payload(task: Any) -> dict[str, Any]:
    """Build the exact worker payload from a parent-issued dispatch task."""
    return {
        "node_id": task.node_id,
        "alias": task.alias,
        "params": task.params,
        "state_bytes": task.state_bytes,
        "trace_carrier": task.trace_carrier,
        "timeout_s": task.timeout_s,
        "max_retries": 0,
        "context_meta": task.context_meta,
        "worker_invocation_id": task.worker_invocation_id,
        "worker_dispatch_sha256": task.worker_dispatch_sha256,
    }


async def _run_bound_worker(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    worker_entry: Literal["async", "sync"] = "async",
    timeout_authority: tuple[Any, float] | None = None,
) -> NodeOutcome:
    """Run the current staged-receipt route using a real parent dispatch binding."""
    task = retry_module._build_spawn_timeout_task(
        ResolveParametersNode(),
        ctx,
        state,
        alias="resolve",
        dispatch_params={},
    )
    payload = _spawn_timeout_payload(task)
    if timeout_authority is not None:
        receipt = await run_node_in_worker(payload, timeout_authority=timeout_authority)
    elif worker_entry == "async":
        receipt = await run_node_in_worker(payload, parent_receipt=True)
    else:
        receipt = await asyncio.to_thread(run_node_in_worker_sync, payload, parent_receipt=True)
    owner_snapshot_ref = ctx.run._owner_snapshot_ref
    invocation_id = task.worker_invocation_id
    dispatch_sha256 = task.worker_dispatch_sha256
    assert owner_snapshot_ref is not None
    assert isinstance(invocation_id, str)
    assert isinstance(dispatch_sha256, str)
    return retry_module._admit_worker_execution_receipt(
        ctx,
        receipt,
        invocation_id=invocation_id,
        expected_dispatch=dispatch_sha256,
        owner_snapshot_ref=owner_snapshot_ref,
        expected_run_id=state.run_id,
    )


def _put_dead_letter(
    store: FileSystemCAS,
    *,
    run: RunContext,
    state: ExperimentState,
) -> ArtifactRef:
    """Persist a source-bound DLQ fixture using the real run-owner record contract."""
    workflow = _workflow("sync")
    workflow_ref = store.put_json(
        workflow.model_dump(mode="json"),
        PutOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowSpec",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    input_state_ref = store.put_json(
        state.model_dump(),
        PutOptions(
            kind="scientist.experiment_state",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.ExperimentState",
                version=state.schema_version,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    attempt_id = str(uuid4())
    basis_ref = run._record_runtime_invocation_started(
        attempt_id=attempt_id,
        attempt_number=1,
        workflow_spec_ref=workflow_ref,
        node_alias="resolve",
        component_id="scientist.node_resolve_parameters@1.0.0",
        input_state_ref=input_state_ref,
    )
    run._record_runtime_invocation_completed(
        attempt_id=attempt_id,
        attempt_number=1,
        basis_ref=basis_ref,
        status="unknown",
        outcome_state_ref=None,
        output_refs=[],
    )
    return store.put_json(
        {
            "kind": "scientist.dead_letter",
            "run_id": state.run_id,
            "alias": "resolve",
            "node_id": "scientist.node_resolve_parameters@1.0.0",
            "error_type": "RuntimeError",
            "error_message": "injected prior failure",
            "attempts": 1,
            "dispatch_basis_status": "selected",
            "dispatch_basis_ref": basis_ref.model_dump(mode="json"),
            "policy": {"max_retries": 0},
            "created_at": "2026-10-11T12:00:00Z",
        },
        PutOptions(
            kind="scientist.dead_letter",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.DeadLetter",
                version="2.0",
            ),
            inputs=[input_ref_from_artifact_ref(basis_ref, role="dispatch_basis")],
        ),
    )


def _workflow(mode: Literal["sync", "timed", "async"]) -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="retained_skg_real_selector",
        nodes=[
            NodeInvocation(
                alias="resolve",
                node_id=ComponentId.parse("scientist.node_resolve_parameters@1.0.0"),
                timeout_s=30.0 if mode == "timed" else None,
            )
        ],
    )


def _execute_workflow(
    mode: Literal["sync", "timed", "async"],
    ctx: ExecutionContext,
    registry: NodeRegistry,
    state: ExperimentState,
) -> WorkflowExecutionResult:
    workflow = _workflow(mode)
    if mode == "async":
        return asyncio.run(
            AsyncWorkflowExecutor(ctx, registry, workflow_timeout_s=30.0).execute(workflow, state)
        )
    return WorkflowExecutor(ctx, registry).execute(workflow, state)


@pytest.mark.parametrize("worker_entry", ["async", "sync"])
@pytest.mark.asyncio
async def test_shared_worker_intake_reads_selected_cas_source_before_retry(
    tmp_path: Path,
    worker_entry: Literal["async", "sync"],
) -> None:
    """Serialized worker variants publish owner-readable, selected-source bundles."""
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, _run, ctx, state, selected_ref = _workflow_fixture(tmp_path)
        replay_state = state.model_copy(
            update={
                "inputs": {SNAPSHOT_INPUT_KEY: selected_ref},
                "params": {
                    key: value for key, value in state.params.items() if key != "skg_db_path"
                },
            }
        )
        live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        try:
            assert _value(live) == 9.75
        finally:
            live.close()

        outcome = await _run_bound_worker(ctx, replay_state, worker_entry=worker_entry)

        assert outcome.status == "ok"
        bundle_ref = outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 1.25
        input_roles = {item.role: item for item in store.get_manifest(bundle_ref).inputs}
        assert set(input_roles) == {"causal_graph", "skg_source_snapshot"}
        assert input_roles["skg_source_snapshot"] == input_ref_from_artifact_ref(
            selected_ref, role="skg_source_snapshot"
        )


def test_timeout_worker_v2_roundtrips_persisted_access_scope_and_owner_ref(
    tmp_path: Path,
) -> None:
    scope = AccessScope.for_service(
        tenant_id="retained-tenant",
        cell_id="retained-cell",
        spiffe_id="spiffe://polisyos.test/cell/retained-cell/svc/timeout-worker",
    )
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        with _access_scope_context(scope):
            _source, _store, run, ctx, state, _selected_ref = _workflow_fixture(
                tmp_path, access_scope=scope
            )
            worker_meta = serialize_timeout_context(ctx, expected_run_id=state.run_id)
        assert worker_meta["schema"] == "polisyos.scientist.timeout_context.v2"
        assert worker_meta["run"]["access_scope"] == scope.to_dict()
        assert run._owner_snapshot_ref is not None
        assert worker_meta["run"]["owner_snapshot_ref"] == run._owner_snapshot_ref.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        worker_ctx = _build_timeout_worker_context(worker_meta)
        assert worker_ctx.run.access_scope == scope
        assert worker_ctx.run._owner_snapshot_ref == run._owner_snapshot_ref


def test_timeout_worker_v2_rejects_scope_and_owner_tampering_before_effects(
    tmp_path: Path,
) -> None:
    scope = AccessScope.for_service(
        tenant_id="retained-tenant",
        cell_id="retained-cell",
        spiffe_id="spiffe://polisyos.test/cell/retained-cell/svc/timeout-worker",
    )
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        with _access_scope_context(scope):
            _source, store, _run, ctx, state, _selected_ref = _workflow_fixture(
                tmp_path, access_scope=scope
            )
            original_meta = serialize_timeout_context(ctx, expected_run_id=state.run_id)
        assert ctx.run.trace_path is not None
        trace_before = ctx.run.trace_path.read_bytes()
        before = {
            path.relative_to(store.root): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in store.root.rglob("*")
            if path.is_file()
        }
        mutations = (
            ("missing_scope", "timeout_worker_run_context_invalid"),
            ("missing_owner_ref", "timeout_worker_run_context_invalid"),
            ("extra_scope_field", "timeout_worker_access_scope_shape_invalid"),
            ("tenant", "timeout_worker_access_scope_owner_mismatch"),
            ("cell", "timeout_worker_access_scope_owner_mismatch"),
            ("spiffe", "timeout_worker_owner_inputs_mismatch"),
            ("scope_absent", "timeout_worker_owner_inputs_mismatch"),
            ("roles_type", "timeout_worker_access_scope_invalid"),
            ("mfa_type", "timeout_worker_access_scope_invalid"),
            ("owner_profile", "timeout_worker_owner_snapshot_invalid"),
        )
        for mutation, expected_reason in mutations:
            worker_meta = json.loads(json.dumps(original_meta))
            run_meta = worker_meta["run"]
            if mutation == "missing_scope":
                del run_meta["access_scope"]
            elif mutation == "missing_owner_ref":
                del run_meta["owner_snapshot_ref"]
            elif mutation == "extra_scope_field":
                run_meta["access_scope"]["untyped_extra"] = "present"
            elif mutation == "tenant":
                run_meta["access_scope"]["tenant_id"] = "other-tenant"
            elif mutation == "cell":
                run_meta["access_scope"]["cell_id"] = "other-cell"
            elif mutation == "spiffe":
                run_meta["access_scope"]["spiffe_id"] = "spiffe://other/identity"
            elif mutation == "scope_absent":
                run_meta["access_scope"] = None
            elif mutation == "roles_type":
                run_meta["access_scope"]["roles"] = "service"
            elif mutation == "mfa_type":
                run_meta["access_scope"]["mfa_verified"] = 1
            elif mutation == "owner_profile":
                run_meta["owner_snapshot_ref"]["manifest_profile_sha256"] = "sha256:" + "0" * 64
            else:
                raise AssertionError(f"unrecognized mutation: {mutation}")

            with pytest.raises(ValueError, match=expected_reason):
                _build_timeout_worker_context(worker_meta)
            after = {
                path.relative_to(store.root): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in store.root.rglob("*")
                if path.is_file()
            }
            assert after == before
            assert ctx.run.trace_path.read_bytes() == trace_before


@pytest.mark.asyncio
async def test_timeout_worker_installs_persisted_scope_for_node_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = AccessScope.for_service(
        tenant_id="retained-tenant",
        cell_id="retained-cell",
        spiffe_id="spiffe://polisyos.test/cell/retained-cell/svc/timeout-worker",
    )
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        with _access_scope_context(scope):
            _source, _store, _run, ctx, state, _selected_ref = _workflow_fixture(
                tmp_path, access_scope=scope
            )
        observations: list[tuple[AccessScope | None, AccessScope | None]] = []

        async def inspect_scope(_node, worker_ctx, worker_state, **_kwargs):
            observations.append((worker_ctx.run.access_scope, get_current_access_scope_or_none()))
            return NodeOutcome(status="ok", state=worker_state)

        monkeypatch.setattr(retry_module, "execute_with_retry_async", inspect_scope)
        worker_state = ExperimentState(run_id=state.run_id)
        with _access_scope_context(None):
            outcome = await _run_bound_worker(
                ctx,
                worker_state,
                timeout_authority=(None, _time.monotonic() + 30.0),
            )
            assert get_current_access_scope_or_none() is None
        assert outcome.status == "ok"
        assert observations == [(scope, scope)]


def test_timeout_worker_rejects_store_run_owner_mismatch_before_reconstruction(
    tmp_path: Path,
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _source, _store, _run, ctx, state, _selected_ref = _workflow_fixture(tmp_path)
        worker_meta = serialize_timeout_context(ctx, expected_run_id=state.run_id)
        worker_meta["store"]["tenant_id"] = None
        worker_meta["store"]["cell_id"] = None

        with pytest.raises(ValueError, match="timeout_worker_store_run_owner_mismatch"):
            _build_timeout_worker_context(worker_meta)


@pytest.mark.asyncio
async def test_shared_worker_intake_refuses_tampered_snapshot_without_live_path(
    tmp_path: Path,
) -> None:
    """A corrupt selected materialization cannot fall back to the absent live path."""
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _source, _store, _run, ctx, state, selected_ref = _workflow_fixture(tmp_path)
        replay_state = state.model_copy(
            update={
                "inputs": {SNAPSHOT_INPUT_KEY: selected_ref},
                "params": {
                    key: value for key, value in state.params.items() if key != "skg_db_path"
                },
            }
        )
        assert "skg_db_path" not in replay_state.params
        snapshot = load_retained_skg_snapshot(ctx.store, selected_ref)
        assert ctx.run.trace_path is not None
        snapshot_dir = ctx.run.trace_path.parent / "skg-snapshots"
        materialized = materialize_retained_skg_snapshot(
            ctx.store, selected_ref, directory=snapshot_dir
        )
        original = materialized.read_bytes()
        damaged = bytes([original[0] ^ 1]) + original[1:]
        materialized.write_bytes(damaged)

        with pytest.raises(RetainedSKGSnapshotError, match="materialization_digest"):
            await _run_bound_worker(ctx, replay_state)
        assert materialized.read_bytes() == damaged
        assert not (snapshot_dir / f"{snapshot.source_sha256}.duckdb-wal").exists()


@pytest.mark.asyncio
async def test_public_dead_letter_replay_binds_selected_skg_source_before_resolve(
    tmp_path: Path,
) -> None:
    """Public dead-letter replay consumes and records the exact selected retained source."""
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, run, ctx, state, selected_ref = _workflow_fixture(tmp_path)
        dead_letter_ref = _put_dead_letter(store, run=run, state=state)
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: selected_ref}})

        live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        try:
            assert _value(live) == 9.75
        finally:
            live.close()

        outcome = await replay_dead_letter(
            store,
            dead_letter_ref.artifact_id,
            ctx=ctx,
            state=replay_state,
            node=ResolveParametersNode(),
        )

        assert outcome.status == "ok"
        bundle_ref = outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 1.25
        manifest = store.get_manifest(bundle_ref)
        input_roles = {item.role: item for item in manifest.inputs}
        assert set(input_roles) == {"causal_graph", "skg_source_snapshot"}
        assert input_roles["skg_source_snapshot"] == input_ref_from_artifact_ref(
            selected_ref, role="skg_source_snapshot"
        )
        assert run.run_manifest.inputs.count(selected_ref) == 1


@pytest.mark.asyncio
async def test_public_dead_letter_replay_refuses_profileless_selected_skg_source(
    tmp_path: Path,
) -> None:
    """A malformed explicit source refuses before the consumer can read live bytes."""
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, run, ctx, state, selected_ref = _workflow_fixture(tmp_path)
        dead_letter_ref = _put_dead_letter(store, run=run, state=state)
        profileless_ref = selected_ref.model_copy(update={"manifest_profile_sha256": None})
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: profileless_ref}})
        node_calls: list[bool] = []

        class ObservedResolveParametersNode(ResolveParametersNode):
            def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
                node_calls.append(True)
                return super().execute(ctx, state)

        with pytest.raises(RetainedSKGSnapshotError, match="descriptor_profile_required"):
            await replay_dead_letter(
                store,
                dead_letter_ref.artifact_id,
                ctx=ctx,
                state=replay_state,
                node=ObservedResolveParametersNode(),
            )

        assert node_calls == []
        assert replay_state.params["skg_db_path"] == str(source)
        assert profileless_ref not in run.run_manifest.inputs
        live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        try:
            assert _value(live) == 9.75
        finally:
            live.close()


def test_async_workflow_deadline_cancels_checkpoint_after_real_skg_node_completed(
    tmp_path: Path,
) -> None:
    class BlockingCheckpoint:
        def __init__(self, store: FileSystemCAS) -> None:
            self._store = store
            self.entered = asyncio.Event()
            self.cancelled = asyncio.Event()
            self.never_release = asyncio.Event()
            self.completed_nodes: list[str] = []
            self.output_ref: ArtifactRef | None = None
            self.output_value: float | None = None

        async def on_node_complete_async(
            self,
            *,
            state: ExperimentState,
            alias: str,
            node_id: str,
            completed_nodes: list[str],
            workflow_id: str,
            workflow_fingerprint: str,
            cache_entry_ref: ArtifactRef | None,
        ) -> None:
            del alias, node_id, workflow_id, workflow_fingerprint, cache_entry_ref
            self.completed_nodes = list(completed_nodes)
            self.output_ref = state.artifacts_index.get(
                ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
            )
            if self.output_ref is not None:
                bundle = load_context_adaptive_parameter_bundle(
                    _ensure_ir_artifact_store(self._store), self.output_ref
                )
                self.output_value = float(bundle.parameters["fiscal_multiplier"].value)
            self.entered.set()
            try:
                await self.never_release.wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise

    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _, store, _, ctx, state, ref = _workflow_fixture(tmp_path)
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: ref}})
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        hook = BlockingCheckpoint(store)

        async def execute() -> None:
            await AsyncWorkflowExecutor(
                ctx,
                registry,
                checkpoint_hook=hook,
                workflow_timeout_s=30.0,
            ).execute(_workflow("async"), replay_state)

        with pytest.raises(WorkflowTimeoutError) as timeout:
            asyncio.run(execute())

        assert hook.entered.is_set()
        assert hook.cancelled.is_set()
        assert hook.completed_nodes == ["resolve"]
        assert hook.output_ref is not None
        assert hook.output_value == 1.25
        assert timeout.value.details["execution_state"] == "unknown"
        assert timeout.value.details["publication_operation"] == "checkpoint"


@pytest.mark.parametrize("mode", ["sync", "timed", "async"])
def test_real_workflow_selector_replays_saved_source_with_current_live_replacement(
    tmp_path: Path,
    mode: Literal["sync", "timed", "async"],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, run, ctx, state, ref = _workflow_fixture(tmp_path)
        selected = load_retained_skg_snapshot(store, ref)
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: ref}})
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        process_contexts: list[str | None] = []
        worker_groups: list[tuple[int | None, int | None]] = []
        get_context = mp.get_context
        get_owned_group = retry_module._owned_process_group_id

        def record_process_context(method: str | None = None):
            process_contexts.append(method)
            return get_context(method)

        def record_owned_group(process, group_ready, **kwargs):
            group_id = get_owned_group(process, group_ready, **kwargs)
            worker_groups.append((process.pid, group_id))
            return group_id

        monkeypatch.setattr(mp, "get_context", record_process_context)
        monkeypatch.setattr(retry_module, "_owned_process_group_id", record_owned_group)
        result = _execute_workflow(mode, ctx, registry, replay_state)
        if mode in {"timed", "async"} and sys.platform == "darwin":
            assert "spawn" in process_contexts
            assert "fork" not in process_contexts
            assert len(worker_groups) == 1
            worker_pid, group_id = worker_groups[0]
            assert worker_pid is not None
            assert group_id == worker_pid
            assert not retry_module._owned_process_group_is_alive(group_id)
            assert all(child.pid != worker_pid for child in mp.active_children())
        assert result.report.status == "ok", result.report.model_dump_json(indent=2)
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store),
            result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF],
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 1.25
        bundle_manifest = store.get_manifest(
            result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        )
        assert (
            input_ref_from_artifact_ref(ref, role="skg_source_snapshot") in bundle_manifest.inputs
        )
        assert state.params["skg_db_path"] == str(source)
        assert replay_state.params["skg_db_path"] == str(source)
        assert SNAPSHOT_INPUT_KEY not in state.inputs
        assert result.state.inputs[SNAPSHOT_INPUT_KEY] == ref
        assert ref in run.run_manifest.inputs
        assert ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            store.get_manifest(ref)
        )
        assert run.trace_path is not None
        expected_path = (
            run.trace_path.parent / "skg-snapshots" / (f"{selected.source_sha256}.duckdb")
        )
        assert Path(result.state.params["skg_db_path"]) == expected_path
        assert expected_path != source
        assert hashlib.sha256(expected_path.read_bytes()).hexdigest() == selected.source_sha256
        live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        try:
            assert _value(live) == 9.75
        finally:
            live.close()


def test_executor_keeps_cache_bound_reader_through_query_close_and_reopen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _source, store, run, ctx, state, ref = _workflow_fixture(tmp_path)
        selected = load_retained_skg_snapshot(store, ref)
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: ref}})
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        bindings: list[tuple[PreparedSKGRead, dict[str, str]]] = []
        key_inputs: list[dict[str, Any]] = []
        node_inputs: list[PreparedSKGRead] = []
        query_reads: list[tuple[PreparedSKGRead, tuple[str, ...]]] = []
        closed_reads: list[PreparedSKGRead] = []

        original_binding = PreparedSKGRead.cache_binding
        original_compute = executor_module.compute_idempotency_key
        original_execute = ResolveParametersNode.execute
        original_fingerprints = PreparedSKGRead.query_fingerprints_since
        original_close = PreparedSKGRead.close

        def record_binding(
            prepared: PreparedSKGRead,
            *,
            selector_version: str,
        ) -> dict[str, str]:
            binding = original_binding(prepared, selector_version=selector_version)
            bindings.append((prepared, binding))
            return binding

        def record_key(
            spec: NodeSpec,
            state: ExperimentState,
            bind_params: dict[str, Any] | None = None,
        ) -> str:
            key_inputs.append(dict(bind_params or {}))
            return original_compute(spec=spec, state=state, bind_params=bind_params)

        def record_execute(
            node: ResolveParametersNode,
            execution_ctx: ExecutionContext,
            current_state: ExperimentState,
        ) -> NodeOutcome:
            assert execution_ctx.prepared_skg_read is not None
            node_inputs.append(execution_ctx.prepared_skg_read)
            return original_execute(node, execution_ctx, current_state)

        def record_fingerprints(
            prepared: PreparedSKGRead,
            marker: int,
        ) -> tuple[str, ...]:
            fingerprints = original_fingerprints(prepared, marker)
            query_reads.append((prepared, fingerprints))
            return fingerprints

        def record_close(prepared: PreparedSKGRead) -> None:
            closed_reads.append(prepared)
            original_close(prepared)

        monkeypatch.setattr(PreparedSKGRead, "cache_binding", record_binding)
        monkeypatch.setattr(executor_module, "compute_idempotency_key", record_key)
        monkeypatch.setattr(ResolveParametersNode, "execute", record_execute)
        monkeypatch.setattr(PreparedSKGRead, "query_fingerprints_since", record_fingerprints)
        monkeypatch.setattr(PreparedSKGRead, "close", record_close)

        result = _execute_workflow("sync", ctx, registry, replay_state)

        assert result.report.status == "ok", result.report.model_dump_json(indent=2)
        assert len(bindings) == len(key_inputs) == len(node_inputs) == len(query_reads) == 1
        bound_read, binding = bindings[0]
        assert key_inputs[0]["prepared_skg_read"] == binding
        assert node_inputs[0] is bound_read
        assert query_reads[0][0] is bound_read
        assert query_reads[0][1]
        assert all(len(fingerprint) == 64 for fingerprint in query_reads[0][1])
        assert binding["source_snapshot_sha256"] == selected.source_sha256
        assert binding["source_snapshot_ref"] == bound_read.source_snapshot_ref
        assert binding["source_snapshot_ref"] != selected.source_reference
        assert sum(closed is bound_read for closed in closed_reads) == 1
        assert bound_read._closed
        with pytest.raises(duckdb.Error):
            bound_read.query._con.execute("SELECT 1")

        bundle_ref = result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 1.25
        assert (
            input_ref_from_artifact_ref(ref, role="skg_source_snapshot")
            in store.get_manifest(bundle_ref).inputs
        )
        assert ref in run.run_manifest.inputs

        reopened = prepare_retained_skg_read(
            store,
            ref,
            directory=tmp_path / "reopened-snapshot",
            index_dir=tmp_path,
        )
        try:
            assert reopened is not bound_read
            assert reopened.source_snapshot_sha256 == binding["source_snapshot_sha256"]
            assert _value(reopened) == 1.25
        finally:
            reopened.close()
        assert sum(closed is reopened for closed in closed_reads) == 1


def test_executor_misses_after_same_path_skg_bytes_change_and_reuses_only_stable_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, run, ctx, state, _ref = _workflow_fixture(tmp_path)
        assert SNAPSHOT_INPUT_KEY not in state.inputs
        initial = tmp_path / "initial.duckdb"
        _seed(initial, 1.25)
        os.replace(initial, source)
        changed = tmp_path / "changed.duckdb"
        _seed(changed, 9.75)
        unconsumed = tmp_path / "unconsumed.duckdb"

        bundle_path = f"artifacts_index.{ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF}"

        def _clear_bundle(current_state: ExperimentState) -> ExperimentState:
            next_state = branch_state(current_state, write_paths=(bundle_path,)).state
            next_state.artifacts_index.pop(ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF, None)
            return next_state

        source_update_metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_test_source_update@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Test SKG source update",
            description="Replace the live fixture bytes between real resolver invocations.",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        )
        unrelated_fixture_metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_test_unconsumed_fixture@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Test unconsumed fixture",
            description="Add unrelated bytes before the stable-source resolver invocation.",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        )

        class ReplaceLiveSourceAndClearBundle:
            def __init__(self, source_path: Path, replacement_path: Path) -> None:
                self._source_path = source_path
                self._replacement_path = replacement_path

            @property
            def spec(self) -> NodeSpec:
                return NodeSpec(metadata=source_update_metadata, state_writes=[bundle_path])

            def execute(
                self, _ctx: ExecutionContext, current_state: ExperimentState
            ) -> NodeOutcome:
                os.replace(self._replacement_path, self._source_path)
                return NodeOutcome(status="ok", state=_clear_bundle(current_state))

        class AddUnconsumedFixtureAndClearBundle:
            @property
            def spec(self) -> NodeSpec:
                return NodeSpec(metadata=unrelated_fixture_metadata, state_writes=[bundle_path])

            def execute(
                self, _ctx: ExecutionContext, current_state: ExperimentState
            ) -> NodeOutcome:
                _seed(unconsumed, 3.5)
                return NodeOutcome(status="ok", state=_clear_bundle(current_state))

        resolve_id = ComponentId.parse("scientist.node_resolve_parameters@1.0.0")
        source_update_id = source_update_metadata.component_id
        unconsumed_fixture_id = unrelated_fixture_metadata.component_id
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        registry.register(ReplaceLiveSourceAndClearBundle(source, changed))
        registry.register(AddUnconsumedFixtureAndClearBundle())
        workflow = WorkflowSpec(
            workflow_id="same_run_skg_cache_source_change",
            nodes=[
                NodeInvocation(alias="resolve_before", node_id=resolve_id),
                NodeInvocation(
                    alias="replace_live_source",
                    node_id=source_update_id,
                    depends_on=["resolve_before"],
                ),
                NodeInvocation(
                    alias="resolve_after_change",
                    node_id=resolve_id,
                    depends_on=["replace_live_source"],
                ),
                NodeInvocation(
                    alias="add_unconsumed_fixture",
                    node_id=unconsumed_fixture_id,
                    depends_on=["resolve_after_change"],
                ),
                NodeInvocation(
                    alias="resolve_stable",
                    node_id=resolve_id,
                    depends_on=["add_unconsumed_fixture"],
                ),
            ],
        )

        key_calls: list[tuple[dict[str, Any], str]] = []
        bindings: list[tuple[PreparedSKGRead, dict[str, str]]] = []
        node_inputs: list[PreparedSKGRead] = []
        executed_values: list[float] = []
        query_reads: list[tuple[PreparedSKGRead, tuple[str, ...]]] = []
        closed_reads: list[PreparedSKGRead] = []
        original_binding = PreparedSKGRead.cache_binding
        original_compute = executor_module.compute_idempotency_key
        original_execute = ResolveParametersNode.execute
        original_fingerprints = PreparedSKGRead.query_fingerprints_since
        original_close = PreparedSKGRead.close

        def record_binding(
            prepared: PreparedSKGRead,
            *,
            selector_version: str,
        ) -> dict[str, str]:
            binding = original_binding(prepared, selector_version=selector_version)
            bindings.append((prepared, binding))
            return binding

        def record_key(
            spec: NodeSpec,
            state: ExperimentState,
            bind_params: dict[str, Any] | None = None,
        ) -> str:
            frozen_params = dict(bind_params or {})
            key = original_compute(spec=spec, state=state, bind_params=bind_params)
            if "prepared_skg_read" in frozen_params:
                key_calls.append((frozen_params, key))
            return key

        def record_execute(
            node: ResolveParametersNode,
            execution_ctx: ExecutionContext,
            current_state: ExperimentState,
        ) -> NodeOutcome:
            assert execution_ctx.prepared_skg_read is not None
            node_inputs.append(execution_ctx.prepared_skg_read)
            outcome = original_execute(node, execution_ctx, current_state)
            bundle_ref = outcome.state.artifacts_index[
                ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
            ]
            bundle = load_context_adaptive_parameter_bundle(
                _ensure_ir_artifact_store(store), bundle_ref
            )
            executed_values.append(float(bundle.parameters["fiscal_multiplier"].value))
            return outcome

        def record_fingerprints(
            prepared: PreparedSKGRead,
            marker: int,
        ) -> tuple[str, ...]:
            fingerprints = original_fingerprints(prepared, marker)
            query_reads.append((prepared, fingerprints))
            return fingerprints

        def record_close(prepared: PreparedSKGRead) -> None:
            closed_reads.append(prepared)
            original_close(prepared)

        monkeypatch.setattr(PreparedSKGRead, "cache_binding", record_binding)
        monkeypatch.setattr(executor_module, "compute_idempotency_key", record_key)
        monkeypatch.setattr(ResolveParametersNode, "execute", record_execute)
        monkeypatch.setattr(PreparedSKGRead, "query_fingerprints_since", record_fingerprints)
        monkeypatch.setattr(PreparedSKGRead, "close", record_close)

        result = WorkflowExecutor(ctx, registry).execute(workflow, state)

        assert result.report.status == "ok", result.report.model_dump_json(indent=2)
        assert not changed.exists()
        assert unconsumed.is_file()
        assert len(bindings) == len(key_calls) == 3
        assert len(node_inputs) == len(query_reads) == 2
        assert executed_values == [1.25, 9.75]
        prepared_reads = [prepared for prepared, _binding in bindings]
        source_bindings = [binding for _prepared, binding in bindings]
        assert node_inputs[0] is prepared_reads[0]
        assert node_inputs[1] is prepared_reads[1]
        assert all(query_reads[index][0] is prepared_reads[index] for index in range(2))
        assert all(fingerprints for _read, fingerprints in query_reads)
        hashes = [binding["source_snapshot_sha256"] for binding in source_bindings]
        refs = [binding["source_snapshot_ref"] for binding in source_bindings]
        assert hashes[0] != hashes[1] == hashes[2]
        assert refs[0] == refs[1] == refs[2]
        assert [params["prepared_skg_read"] for params, _key in key_calls] == source_bindings
        cache_keys = [key for _params, key in key_calls]
        assert cache_keys[0] != cache_keys[1] == cache_keys[2]
        assert len(closed_reads) == len(prepared_reads) == 3
        assert all(
            sum(closed is prepared for closed in closed_reads) == 1 for prepared in prepared_reads
        )
        assert all(prepared._closed for prepared in prepared_reads)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == hashes[2]

        assert run.trace_path is not None
        trace_events = [
            json.loads(line)
            for line in run.trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        resolver_hits = [
            event
            for event in trace_events
            if event.get("phase")
            in {
                "scientist.node.resolve_before",
                "scientist.node.resolve_after_change",
                "scientist.node.resolve_stable",
            }
            and event.get("event") == "NODE_CACHE_HIT"
        ]
        assert [event["phase"] for event in resolver_hits] == ["scientist.node.resolve_stable"]
        assert (
            sum(
                event.get("phase") == "core" and event.get("event") == "RUN_STARTED"
                for event in trace_events
            )
            == 1
        )
        assert (
            sum(
                event.get("phase") == "core" and event.get("event") == "RUN_FINALIZED"
                for event in trace_events
            )
            == 1
        )

        bundle_ref = result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 9.75


def test_executor_refuses_reader_swapped_after_cache_key_binds_selected_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, _run, ctx, state, ref = _workflow_fixture(tmp_path)
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: ref}})
        selected = load_retained_skg_snapshot(store, ref)
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        bindings: list[tuple[PreparedSKGRead, dict[str, str]]] = []
        key_calls: list[tuple[dict[str, Any], str]] = []
        original_inputs: list[PreparedSKGRead] = []
        swapped_reads: list[PreparedSKGRead] = []
        query_reads: list[tuple[PreparedSKGRead, tuple[str, ...]]] = []
        closed_reads: list[PreparedSKGRead] = []
        refusals: list[str] = []

        original_binding = PreparedSKGRead.cache_binding
        original_compute = executor_module.compute_idempotency_key
        original_execute = ResolveParametersNode.execute
        original_fingerprints = PreparedSKGRead.query_fingerprints_since
        original_close = PreparedSKGRead.close

        def record_binding(
            prepared: PreparedSKGRead,
            *,
            selector_version: str,
        ) -> dict[str, str]:
            binding = original_binding(prepared, selector_version=selector_version)
            bindings.append((prepared, binding))
            return binding

        def record_key(
            spec: NodeSpec,
            state: ExperimentState,
            bind_params: dict[str, Any] | None = None,
        ) -> str:
            frozen_params = dict(bind_params or {})
            key = original_compute(spec=spec, state=state, bind_params=bind_params)
            key_calls.append((frozen_params, key))
            return key

        def swap_at_consumer(
            node: ResolveParametersNode,
            execution_ctx: ExecutionContext,
            current_state: ExperimentState,
        ) -> NodeOutcome:
            assert execution_ctx.prepared_skg_read is not None
            original_reader = execution_ctx.prepared_skg_read
            original_inputs.append(original_reader)
            changed_reader = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
            swapped_reads.append(changed_reader)
            assert changed_reader.source_snapshot_sha256 != selected.source_sha256
            try:
                try:
                    return original_execute(
                        node,
                        replace(execution_ctx, prepared_skg_read=changed_reader),
                        current_state,
                    )
                except RetainedSKGSnapshotError as exc:
                    refusals.append(str(exc))
                    raise
            finally:
                changed_reader.close()

        def record_fingerprints(
            prepared: PreparedSKGRead,
            marker: int,
        ) -> tuple[str, ...]:
            fingerprints = original_fingerprints(prepared, marker)
            query_reads.append((prepared, fingerprints))
            return fingerprints

        def record_close(prepared: PreparedSKGRead) -> None:
            closed_reads.append(prepared)
            original_close(prepared)

        monkeypatch.setattr(PreparedSKGRead, "cache_binding", record_binding)
        monkeypatch.setattr(executor_module, "compute_idempotency_key", record_key)
        monkeypatch.setattr(ResolveParametersNode, "execute", swap_at_consumer)
        monkeypatch.setattr(PreparedSKGRead, "query_fingerprints_since", record_fingerprints)
        monkeypatch.setattr(PreparedSKGRead, "close", record_close)

        result = _execute_workflow("sync", ctx, registry, replay_state)

        assert result.report.status == "fail"
        assert len(bindings) == len(key_calls) == len(original_inputs) == 1
        bound_reader, binding = bindings[0]
        assert key_calls[0][0]["prepared_skg_read"] == binding
        assert key_calls[0][1]
        assert original_inputs[0] is bound_reader
        assert swapped_reads[0] is not bound_reader
        assert swapped_reads[0].source_snapshot_sha256 != binding["source_snapshot_sha256"]
        assert refusals == ["retained_skg_prepared_source_mismatch"]
        assert len(query_reads) == 1
        assert query_reads[0][0] is bound_reader
        assert query_reads[0][1] == ()
        assert sum(closed is bound_reader for closed in closed_reads) == 1
        assert sum(closed is swapped_reads[0] for closed in closed_reads) == 1
        assert bound_reader._closed
        assert swapped_reads[0]._closed


def test_selected_snapshot_consumer_rechecks_and_recovers_exact_source_after_bind(
    tmp_path: Path,
) -> None:
    """A post-bind replacement is refused; a missing cache file is restored from CAS."""
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, run, ctx, state, ref = _workflow_fixture(tmp_path)
        selected = load_retained_skg_snapshot(store, ref)
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: ref}})
        bound_state = _bind_retained_workflow_input(ctx, replay_state)
        target = Path(bound_state.params["skg_db_path"])
        assert run.trace_path is not None
        assert target == (
            run.trace_path.parent / "skg-snapshots" / f"{selected.source_sha256}.duckdb"
        )

        changed_source = tmp_path / "changed-materialization.duckdb"
        _seed(changed_source, 9.75)
        os.replace(changed_source, target)
        changed_bytes = target.read_bytes()
        with pytest.raises(RetainedSKGSnapshotError, match="retained_skg_materialization_digest"):
            ResolveParametersNode().execute(ctx, bound_state)
        assert target.read_bytes() == changed_bytes

        # Absence is recoverable only from the still-selected typed CAS descriptor.
        target.unlink()
        outcome = ResolveParametersNode().execute(ctx, bound_state)
        assert outcome.status == "ok"
        bundle_ref = outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 1.25
        assert (
            input_ref_from_artifact_ref(ref, role="skg_source_snapshot")
            in store.get_manifest(bundle_ref).inputs
        )
        assert hashlib.sha256(target.read_bytes()).hexdigest() == selected.source_sha256
        live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        try:
            assert _value(live) == 9.75
        finally:
            live.close()


def test_selected_snapshot_ref_cannot_be_reused_as_absent_source(
    tmp_path: Path,
) -> None:
    """A selected descriptor cannot take the no-source cached-bundle shortcut."""
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _, _, _, ctx, state, ref = _workflow_fixture(tmp_path)
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        built = _execute_workflow("sync", ctx, registry, state)
        assert built.report.status == "ok"
        params_without_source = {
            key: value for key, value in built.state.params.items() if key != "skg_db_path"
        }
        selected_without_path = built.state.model_copy(
            update={
                "params": params_without_source,
                "inputs": {SNAPSHOT_INPUT_KEY: ref},
            }
        )
        with pytest.raises(
            RetainedSKGSnapshotError,
            match="retained_skg_selected_path_required",
        ):
            ResolveParametersNode().execute(ctx, selected_without_path)


@pytest.mark.parametrize("executor_mode", ["sync", "async"])
def test_timeout_worker_admission_refusal_is_not_reported_as_elapsed_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    executor_mode: Literal["sync", "async"],
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, _store, _run, ctx, state, _selected_ref = _workflow_fixture(tmp_path)
        prepared_read = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        ctx = replace(ctx, prepared_skg_read=prepared_read)
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        workflow = WorkflowSpec(
            workflow_id="timeout_worker_admission_refusal",
            nodes=[
                NodeInvocation(
                    alias="resolve",
                    node_id=ComponentId.parse("scientist.node_resolve_parameters@1.0.0"),
                    timeout_s=30.0,
                )
            ],
        )
        monkeypatch.setattr(retry_module, "_timeout_worker_start_method", lambda: "spawn")
        try:
            if executor_mode == "sync":
                result = WorkflowExecutor(ctx, registry).execute(workflow, state)
            else:
                result = asyncio.run(
                    AsyncWorkflowExecutor(ctx, registry, workflow_timeout_s=30.0).execute(
                        workflow, state
                    )
                )
        finally:
            prepared_read.close()

        error = result.report.nodes[0].error
        assert error is not None
        assert error.code == "node.timeout_worker_unsupported"
        assert error.details["reason"] == "timeout_worker_optional_context_port_unsupported"
        assert "timeout_seconds_binary64_hex" not in error.details


def test_spawn_timeout_reaps_worker_and_reports_unresolved_group_truthfully(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _, _, _, ctx, state, _ = _workflow_fixture(tmp_path)
        worker_groups: list[tuple[int | None, int | None, bool]] = []
        get_owned_group = retry_module._owned_process_group_id

        def record_owned_group(process, group_ready, **kwargs):
            group_id = get_owned_group(process, group_ready, **kwargs)
            worker_groups.append((process.pid, group_id, group_ready.is_set()))
            return group_id

        monkeypatch.setattr(retry_module, "_timeout_worker_start_method", lambda: "spawn")
        monkeypatch.setattr(retry_module, "_owned_process_group_id", record_owned_group)
        original_state = state.model_dump(mode="python", by_alias=True, exclude_none=False)

        with pytest.raises(NodeTimeoutError) as timeout:
            execute_with_retry_sync(
                ResolveParametersNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.001,
                alias="resolve",
                dispatch_params={},
            )

        assert len(worker_groups) == 1
        worker_pid, group_id, group_ready = worker_groups[0]
        assert worker_pid is not None
        assert all(child.pid != worker_pid for child in mp.active_children())
        if group_id is not None:
            assert group_ready
            assert group_id == worker_pid
            assert not retry_module._owned_process_group_is_alive(group_id)
            assert timeout.value.details["execution_state"] == "owned_processes_reaped"
            assert timeout.value.details["cleanup_complete"] is True
        else:
            assert not group_ready
            assert timeout.value.details["execution_state"] == "external_outcome_unknown"
            assert timeout.value.details["cleanup_complete"] is False
        assert state.model_dump(mode="python", by_alias=True, exclude_none=False) == original_state


@pytest.mark.parametrize("revoke_before_release", [False, True])
def test_spawn_timeout_worker_cannot_write_cas_after_parent_revocation(
    tmp_path: Path,
    revoke_before_release: bool,
) -> None:
    """A delayed canonical node can write only while its shared owner stays active."""
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _, store, _, ctx, state, _ = _workflow_fixture(tmp_path)
        task = retry_module._build_spawn_timeout_task(
            ResolveParametersNode(),
            ctx,
            state,
            alias="resolve-late-write-probe",
            dispatch_params={},
        )
        baseline_files = {
            path.relative_to(store.root) for path in store.root.rglob("*") if path.is_file()
        }

    process_context = mp.get_context("spawn")
    authority_active = process_context.Value("b", True, lock=False)
    started = process_context.Event()
    release = process_context.Event()
    result_receiver, result_sender = process_context.Pipe(duplex=False)
    deadline_monotonic = _time.monotonic() + 30.0
    process = process_context.Process(
        target=run_delayed_timeout_task_after_release,
        args=(
            task,
            authority_active,
            deadline_monotonic,
            started,
            release,
            result_sender,
        ),
    )
    process.start()
    result_sender.close()
    try:
        assert started.wait(timeout=10.0)
        if revoke_before_release:
            authority_active.value = False
        release.set()
        process.join(timeout=20.0)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
        assert not process.is_alive(), "typed timeout probe worker did not stop"
        assert result_receiver.poll(timeout=5.0), "typed timeout worker returned no outcome"
        status, _payload = result_receiver.recv()
    finally:
        release.set()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
        result_receiver.close()

    final_files = {path.relative_to(store.root) for path in store.root.rglob("*") if path.is_file()}
    if revoke_before_release:
        assert final_files == baseline_files
    else:
        assert status == "ok"
        assert final_files > baseline_files


@pytest.mark.parametrize("unsupported_input", ["node", "context", "custom_id"])
def test_spawn_timeout_refuses_unsupported_inputs_without_process_or_thread_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsupported_input: Literal["node", "context", "custom_id"],
) -> None:
    from polisyos.scientist.orchestration.engine import retry as retry_module

    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        _, store, _, ctx, state, _ = _workflow_fixture(tmp_path)
        marker = tmp_path / "unsupported-node-entered.txt"

        class UnsupportedNode:
            def execute(self, _ctx: ExecutionContext, passed_state: ExperimentState) -> NodeOutcome:
                marker.write_text("node body ran", encoding="utf-8")
                return NodeOutcome(status="ok", state=passed_state)

        class WellFormedCustomNode:
            spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse("scientist.node_custom_timeout_probe@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="CustomTimeoutProbe",
                    description="Well-formed custom node outside the closed spawn admission set",
                    tags=["test"],
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                state_reads=[],
                state_writes=[],
            )

            def execute(self, _ctx: ExecutionContext, passed_state: ExperimentState) -> NodeOutcome:
                marker.write_text("node body ran", encoding="utf-8")
                return NodeOutcome(status="ok", state=passed_state)

        node: object = UnsupportedNode()
        worker_ctx = ctx
        expected_reason = "timeout_worker_canonical_node_required"
        if unsupported_input == "context":
            node = ResolveParametersNode()
            worker_ctx = replace(ctx, tracer=object())
            expected_reason = "timeout_worker_optional_context_port_unsupported"
        elif unsupported_input == "custom_id":
            node = WellFormedCustomNode()
            expected_reason = "timeout_worker_node_not_supported"

        baseline_store_entries = {path.relative_to(store.root) for path in store.root.rglob("*")}
        process_starts: list[bool] = []
        thread_attempts: list[bool] = []
        original_get_context = mp.get_context

        class SpawnContextSpy:
            def __init__(self, target: Any) -> None:
                self._target = target

            def __getattr__(self, name: str) -> object:
                if name == "Process":
                    return self._make_process
                return getattr(self._target, name)

            def _make_process(self, *args: object, **kwargs: object) -> object:
                process_starts.append(True)
                return self._target.Process(*args, **kwargs)

        def get_context(method: str | None = None) -> object:
            context = original_get_context(method)
            return SpawnContextSpy(context) if method == "spawn" else context

        def reject_thread_fallback(*_args: object, **_kwargs: object) -> object:
            thread_attempts.append(True)
            raise AssertionError("unsupported timeout input must not fall back to a thread")

        monkeypatch.setattr(retry_module, "_timeout_worker_start_method", lambda: "spawn")
        monkeypatch.setattr(retry_module.mp, "get_context", get_context)
        monkeypatch.setattr(retry_module, "_submit_thread_attempt", reject_thread_fallback)

        with pytest.raises(NodeTimeoutError) as refusal:
            execute_with_retry_sync(
                node,
                worker_ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=30.0,
                alias="unsupported-timeout-input",
                dispatch_params={},
            )

        assert refusal.value.code == "node.timeout_worker_unsupported"
        assert refusal.value.details["reason"] == expected_reason
        assert process_starts == []
        assert thread_attempts == []
        assert not marker.exists()
        assert {path.relative_to(store.root) for path in store.root.rglob("*")} == (
            baseline_store_entries
        )
        assert state.params["skg_db_path"] != ""


def test_workflow_selected_snapshot_supplies_missing_required_source_path(tmp_path: Path) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, run, ctx, state, ref = _workflow_fixture(tmp_path)
        selected = load_retained_skg_snapshot(store, ref)
        replay_state = state.model_copy(
            update={
                "params": {
                    key: value for key, value in state.params.items() if key != "skg_db_path"
                },
                "inputs": {SNAPSHOT_INPUT_KEY: ref},
            }
        )
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        workflow = _workflow("sync").model_copy(update={"required_binds": ["params.skg_db_path"]})
        result = WorkflowExecutor(ctx, registry).execute(workflow, replay_state)
        assert result.report.status == "ok"
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store),
            result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF],
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 1.25
        assert "skg_db_path" not in replay_state.params
        assert state.params["skg_db_path"] == str(source)
        assert result.state.inputs[SNAPSHOT_INPUT_KEY] == ref
        assert ref in run.run_manifest.inputs
        assert run.trace_path is not None
        expected_path = (
            run.trace_path.parent / "skg-snapshots" / (f"{selected.source_sha256}.duckdb")
        )
        assert Path(result.state.params["skg_db_path"]) == expected_path
        assert hashlib.sha256(expected_path.read_bytes()).hexdigest() == selected.source_sha256
        assert expected_path != source


@pytest.mark.parametrize("mode", ["sync", "timed", "async"])
@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_invalid_explicit_workflow_snapshot_refuses_before_real_selector_body(
    tmp_path: Path,
    mode: Literal["sync", "timed", "async"],
    fault: Literal["missing", "corrupt"],
) -> None:
    calls: list[str] = []

    class ObservedSelector(ResolveParametersNode):
        def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            calls.append(str(state.params["skg_db_path"]))
            return super().execute(ctx, state)

    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, _, ctx, state, ref = _workflow_fixture(tmp_path)
        if fault == "missing":
            invalid = ref.model_copy(update={"artifact_id": ArtifactID.from_sha256_hex("0" * 64)})
        else:
            snapshot = load_retained_skg_snapshot(store, ref)
            manifest = store.get_manifest(ref)
            invalid = store.put_json(
                snapshot.model_copy(update={"source_sha256": "0" * 64}).model_dump(mode="json"),
                ArtifactWriteOptions(
                    kind=ref.kind,
                    media_type=ref.media_type,
                    schema=manifest.artifact_schema,
                    producer=manifest.producer,
                    inputs=manifest.inputs,
                ),
                return_selected_profile=True,
            )
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: invalid}})
        registry = NodeRegistry()
        registry.register(ObservedSelector())
        with pytest.raises(
            (
                RetainedSKGSnapshotError,
                ArtifactIntegrityError,
                ArtifactOwnershipError,
                FileNotFoundError,
            )
        ):
            _execute_workflow(mode, ctx, registry, replay_state)
        assert calls == []
        assert replay_state.params["skg_db_path"] == str(source)
        live = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        try:
            assert _value(live) == 9.75
        finally:
            live.close()


def test_published_materialization_sync_failure_is_not_reported_as_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    _, store, ref = _captured(tmp_path)
    directory = tmp_path / "restore"
    directory.mkdir()
    snapshot = load_retained_skg_snapshot(store, ref)
    original = skg_snapshot.fsync_directory

    def refuse_directory_sync(path: Path) -> None:
        raise OSError("injected directory durability refusal")

    monkeypatch.setattr(skg_snapshot, "fsync_directory", refuse_directory_sync)
    with pytest.raises(skg_snapshot.AtomicFileDurabilityError) as failure:
        materialize_retained_skg_snapshot(store, ref, directory=directory)
    assert failure.value.replaced is True
    target = directory / f"{snapshot.source_sha256}.duckdb"
    assert hashlib.sha256(target.read_bytes()).hexdigest() == snapshot.source_sha256
    monkeypatch.setattr(skg_snapshot, "fsync_directory", original)
    fresh = prepare_retained_skg_read(
        FileSystemCAS(store.root, ownership_enforced=False),
        ref,
        directory=directory,
        index_dir=tmp_path,
    )
    try:
        assert _value(fresh) == 1.25
    finally:
        fresh.close()
