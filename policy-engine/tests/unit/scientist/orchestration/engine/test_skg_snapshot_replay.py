"""Real DuckDB/CAS controls for saved operational SKG source replay.

These fixtures assert numerical read/replay only. They do not certify literature
quality, source issuance, institutional authority, or scientific reproducibility.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import duckdb
import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactIntegrityError,
    ArtifactOwnershipError,
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    artifact_manifest_profile_sha256,
)
from polisyos.core.components import ComponentId
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api.academic import ParameterSelector, SKGQuery
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
from polisyos.scientist.orchestration.engine import skg_snapshot
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.skg_snapshot import (
    SNAPSHOT_INPUT_KEY,
    RetainedSKGSnapshotError,
    load_retained_skg_snapshot,
    materialize_retained_skg_snapshot,
    prepare_retained_skg_read,
    retain_prepared_skg_read,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
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


def _exact_written_ref(store: FileSystemCAS, ref: ArtifactRef) -> ArtifactRef:
    manifest = store.get_manifest(ref)
    selected = ref.model_copy(
        update={"manifest_profile_sha256": artifact_manifest_profile_sha256(manifest)}
    )
    store.get_manifest(selected)
    return selected


def test_capture_selects_actual_manifest_profiles_for_descriptor_and_chunks(tmp_path: Path) -> None:
    _, store, ref = _captured(tmp_path)
    snapshot = load_retained_skg_snapshot(store, ref)
    for selected in (ref, *(chunk.ref for chunk in snapshot.chunks)):
        assert selected.manifest_profile_sha256 is not None
        assert selected.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            store.get_manifest(selected)
        )
        assert store.verify(selected).ok


def test_descriptor_without_selected_profile_is_refused(tmp_path: Path) -> None:
    _, store, ref = _captured(tmp_path)
    legacy_selector = ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(RetainedSKGSnapshotError, match="descriptor_profile_required"):
        load_retained_skg_snapshot(store, legacy_selector)


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
    calls: list[str] = []
    original = store.put_bytes

    def observed_put(payload: bytes, options: ArtifactWriteOptions) -> ArtifactRef:
        calls.append(options.kind)
        return original(payload, options)

    monkeypatch.setattr(store, "put_bytes", observed_put)
    try:
        assert retain_prepared_skg_read(store, prepared, existing_ref=ref) == ref
        assert calls == []
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
    original = store.put_bytes
    replaced = False

    def replace_during_capture(payload: bytes, options: ArtifactWriteOptions) -> ArtifactRef:
        nonlocal replaced
        ref = original(payload, options)
        if not replaced:
            replaced = True
            os.replace(replacement, source)
        return ref

    monkeypatch.setattr(store, "put_bytes", replace_during_capture)
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
    wrong = store.put_bytes(
        snapshot.model_copy(update={"source_sha256": "0" * 64}).model_dump_json().encode(),
        options,
    )
    wrong = _exact_written_ref(store, wrong)
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


def _workflow_fixture(
    tmp_path: Path,
) -> tuple[Path, FileSystemCAS, RunContext, ExecutionContext, ExperimentState, ArtifactRef]:
    source = tmp_path / "live.duckdb"
    _seed(source, 1.25)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("retained-tenant", "retained-cell")
    registry_bundle = build_default_registry_bundle(store)
    run = RunContext.start(store, registry_bundle.bundle_ref, run_id="R_retained_skg")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("retained-skg"))
    graph_ref = persist_causal_graph_model(
        store,
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


@pytest.mark.parametrize("mode", ["sync", "timed", "async"])
def test_real_workflow_selector_replays_saved_source_with_current_live_replacement(
    tmp_path: Path, mode: Literal["sync", "timed", "async"]
) -> None:
    with tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"):
        source, store, run, ctx, state, ref = _workflow_fixture(tmp_path)
        selected = load_retained_skg_snapshot(store, ref)
        replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: ref}})
        registry = NodeRegistry()
        registry.register(ResolveParametersNode())
        result = _execute_workflow(mode, ctx, registry, replay_state)
        assert result.report.status == "ok"
        bundle = load_context_adaptive_parameter_bundle(
            store, result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        )
        assert float(bundle.parameters["fiscal_multiplier"].value) == 1.25
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
            store, result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
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
            invalid = store.put_bytes(
                snapshot.model_copy(update={"source_sha256": "0" * 64}).model_dump_json().encode(),
                ArtifactWriteOptions(
                    kind=ref.kind,
                    media_type=ref.media_type,
                    schema=manifest.artifact_schema,
                    producer=manifest.producer,
                    inputs=manifest.inputs,
                ),
            )
            invalid = _exact_written_ref(store, invalid)
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
