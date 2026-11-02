from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactRef,
    ProducerInfo,
    PutOptions,
    artifact_ref_for_manifest,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointCorruptedError,
    CheckpointWriteResult,
    WorkflowMismatchError,
    compute_workflow_fingerprint,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _journaled_outcome(run_id: str, marker: str) -> NodeOutcome:
    branched = branch_state(
        ExperimentState(run_id=run_id),
        write_paths=("params.marker",),
    )
    branched.state.params["marker"] = marker
    return NodeOutcome(status="ok", state=branched.state)


def test_cache_seed_deduplicates_exact_refs_and_does_not_mark_failed_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_res_01_seed"
    writer = NodeResultCache(store, run_id=run_id)
    entry_ref = writer.put(
        "a" * 64,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "A"),
    )
    missing_ref = entry_ref.model_copy(
        update={"artifact_id": "sha256:" + "f" * 64},
    )

    reads = 0
    failed_manifest_attempts = 0
    original_get_bytes = store.get_bytes
    original_get_raw_manifest_bytes = store.get_raw_manifest_bytes

    def counted_get_bytes(artifact_ref: ArtifactRef):
        nonlocal reads
        reads += 1
        return original_get_bytes(artifact_ref)

    def counted_get_raw_manifest_bytes(artifact_ref: Any, **kwargs: Any) -> bytes:
        nonlocal failed_manifest_attempts
        if artifact_ref == missing_ref:
            failed_manifest_attempts += 1
        return original_get_raw_manifest_bytes(artifact_ref, **kwargs)

    monkeypatch.setattr(store, "get_bytes", counted_get_bytes)
    monkeypatch.setattr(store, "get_raw_manifest_bytes", counted_get_raw_manifest_bytes)
    cache = NodeResultCache(store, run_id=run_id)
    restored = cache.seed_from_entry_refs(
        [entry_ref] * 100 + [missing_ref] * 2,
    )

    assert restored == 1
    # Current canonical admission rejects a missing manifest before payload I/O.
    assert reads == 1
    assert failed_manifest_attempts == 2
    assert cache.seed_from_entry_refs([missing_ref]) == 0
    assert failed_manifest_attempts == 3
    assert reads == 1

    replay = NodeResultCache(store, run_id=run_id)
    assert replay.seed_from_entry_refs([missing_ref]) == 0
    assert failed_manifest_attempts == 4
    assert not replay.has("a" * 64)


def test_full_scan_recovery_reports_duplicate_and_distinct_workloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Measure full scans through the first verified cache result, without an SLA."""
    store = FileSystemCAS(tmp_path / "cas")
    run_id = "R_res_01_full_scan_measurement"
    ctx, _bundle_ref = _context(store, run_id)
    writer = NodeResultCache(store, run_id=run_id)
    refs: list[ArtifactRef] = []
    keys = [f"{index + 1:064x}" for index in range(16)]
    values = [index * index + 2 for index in range(16)]
    try:
        for key, value in zip(keys, values, strict=True):
            branch = branch_state(
                ExperimentState(run_id=run_id), write_paths=("params.measurement_value",)
            )
            branch.state.params["measurement_value"] = value
            written_ref = writer.put(
                key,
                node_id="scientist.node_res_measurement@1.0.0",
                outcome=NodeOutcome(status="ok", state=branch.state),
            )
            # Bind the actual immutable manifest selected by the owner, rather
            # than assuming an ID-only producer handle is the eventual read ref.
            ref = artifact_ref_for_manifest(store.get_manifest(written_ref))
            assert ref.manifest_profile_sha256 is not None
            refs.append(ref)
            ctx.run.emit("res01.measurement", "NODE_CACHE_STORE", outputs=[ref])
        source_lines = [
            line
            for line in ctx.run.trace_path.read_bytes().splitlines(keepends=True)
            if json.loads(line).get("event") == "NODE_CACHE_STORE"
        ]
        assert len(source_lines) == len(refs) == len(set(keys)) == 16
    finally:
        ctx.run.suspend_for_resume()

    # Setup reads are outside the timed interval. These real bytes supply the
    # independent expected I/O denominator, not a second cache decoder.
    payloads = {str(ref.artifact_id): store.get_bytes(ref) for ref in refs}
    input_members = [
        {
            "ref": ref.model_dump(mode="json"),
            "bytes": len(payloads[str(ref.artifact_id)]),
            "sha256": hashlib.sha256(payloads[str(ref.artifact_id)]).hexdigest(),
        }
        for ref in refs
    ]
    original_open = Path.open
    original_get_bytes = store.get_bytes
    original_get_manifest = store.get_manifest
    original_verify = store.verify

    def measure_workload(name: str, copies: int) -> dict[str, Any]:
        trace_path = tmp_path / f"{name}.jsonl"
        trace_bytes = b"".join(source_lines) * copies
        trace_path.write_bytes(trace_bytes)
        checkpoint_refs = refs * copies
        observed = {
            "trace_open_calls": 0,
            "trace_lines": 0,
            "trace_bytes": 0,
            "get_bytes_calls": 0,
            "get_bytes_returned_bytes": 0,
            "get_manifest_calls": 0,
            "verify_calls": 0,
        }
        payload_reads: list[dict[str, Any]] = []

        class MeasuredTrace:
            def __init__(self, handle: Any) -> None:
                self.handle = handle

            def __enter__(self) -> Any:
                self.handle.__enter__()
                return self

            def __exit__(self, *args: Any) -> Any:
                return self.handle.__exit__(*args)

            def __iter__(self) -> Any:
                for line in self.handle:
                    observed["trace_lines"] += 1
                    observed["trace_bytes"] += len(line.encode("utf-8"))
                    yield line

        def measured_open(path: Path, *args: Any, **kwargs: Any) -> Any:
            handle = original_open(path, *args, **kwargs)
            if path == trace_path:
                observed["trace_open_calls"] += 1
                return MeasuredTrace(handle)
            return handle

        def measured_get_bytes(ref: ArtifactRef) -> bytes:
            observed["get_bytes_calls"] += 1
            payload = original_get_bytes(ref)
            observed["get_bytes_returned_bytes"] += len(payload)
            payload_reads.append(
                {
                    "ref": ref.model_dump(mode="json"),
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            return payload

        def measured_get_manifest(ref: Any) -> Any:
            observed["get_manifest_calls"] += 1
            return original_get_manifest(ref)

        def measured_verify(ref: Any) -> Any:
            observed["verify_calls"] += 1
            return original_verify(ref)

        with monkeypatch.context() as measurement:
            measurement.setattr(Path, "open", measured_open)
            measurement.setattr(store, "get_bytes", measured_get_bytes)
            measurement.setattr(store, "get_manifest", measured_get_manifest)
            measurement.setattr(store, "verify", measured_verify)
            restored = NodeResultCache(store, run_id=run_id)
            started_ns = time.perf_counter_ns()
            from_trace = restored.seed_from_trace(trace_path)
            from_checkpoint = restored.seed_from_entry_refs(checkpoint_refs)
            admission_ns = time.perf_counter_ns() - started_ns
            admission_observed = dict(observed)
            useful = restored.get(keys[0])
            first_useful_ns = time.perf_counter_ns() - started_ns

        assert from_trace == 16 and from_checkpoint == 0 and restored.size == 16
        assert useful is not None and useful.state.params["measurement_value"] == values[0]
        assert admission_observed["get_bytes_calls"] == 16
        assert admission_observed["get_bytes_returned_bytes"] == sum(map(len, payloads.values()))
        assert observed["get_bytes_calls"] == 17
        assert observed["get_bytes_returned_bytes"] == (
            sum(map(len, payloads.values())) + len(payloads[str(refs[0].artifact_id)])
        )
        assert payload_reads == [*input_members, input_members[0]]
        assert observed["trace_open_calls"] == 1
        assert observed["trace_lines"] == len(refs) * copies
        assert observed["trace_bytes"] == len(trace_bytes)
        assert observed["get_manifest_calls"] > 0 and observed["verify_calls"] > 0
        assert 0 <= admission_ns <= first_useful_ns
        # Validate the entire recovered index outside the first-result interval.
        actual_values = []
        for key in keys:
            outcome = restored.get(key)
            assert outcome is not None
            actual_values.append(outcome.state.params["measurement_value"])
        assert actual_values == values
        return {
            "workload": name,
            "trace_path": str(trace_path),
            "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
            "trace_records": len(refs) * copies,
            "checkpoint_ref_occurrences": len(checkpoint_refs),
            "unique_exact_refs": len(refs),
            "admission": admission_observed,
            "through_first_useful": observed,
            "actual_payload_reads": payload_reads,
            "full_scan_admission_ns": admission_ns,
            "time_to_first_verified_cache_result_ns": first_useful_ns,
            "accepted_values": actual_values,
        }

    rows = [measure_workload("distinct_refs", 1), measure_workload("duplicate_heavy", 100)]
    record_property(
        "res01_full_scan_measurement",
        json.dumps(
            {
                "backend": "FileSystemCAS; current embedded-outcome cache entries",
                "first_useful": "first verified numerical NodeResultCache.get after both full scans",
                "inputs": input_members,
                "workloads": rows,
                "unresolved_by_construction": [
                    "No fresh-process, residual-node or end-to-end resume latency claim",
                    "Setup and final full-index validation excluded from timing",
                    "Elapsed time includes measurement overhead; no uninstrumented comparison",
                    "Manifest/verify counts include nested API calls, not unique physical reads",
                    "Returned payload/trace bytes exclude manifest bytes, verify internal I/O and OS cache",
                    "Synthetic 16-entry profile; no SLA, tail optimization or speedup claim",
                ],
            },
            sort_keys=True,
        ),
    )


def test_cache_seed_does_not_mix_different_content_under_same_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_res_01_conflict"
    key = "b" * 64
    first = NodeResultCache(store, run_id=run_id).put(
        key,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "first"),
    )
    second = NodeResultCache(store, run_id=run_id).put(
        key,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "second"),
    )

    reads: list[ArtifactRef] = []
    original_get_bytes = store.get_bytes

    def counted_get_bytes(artifact_ref: ArtifactRef):
        reads.append(artifact_ref)
        return original_get_bytes(artifact_ref)

    monkeypatch.setattr(store, "get_bytes", counted_get_bytes)
    replay = NodeResultCache(store, run_id=run_id)
    assert replay.seed_from_entry_refs([first, second]) == 1
    assert reads == [first, second]
    loaded = replay.get(key)
    assert loaded is not None
    assert loaded.state.params["marker"] == "first"


@pytest.mark.parametrize(
    "mismatch_field",
    ["artifact_id", "kind", "media_type", "manifest_profile_sha256"],
)
def test_cache_load_rejects_altered_ref_identity_without_admission_or_eviction(
    tmp_path: Path,
    mismatch_field: str,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_res_01_ref_identity"
    key = "d" * 64
    cache = NodeResultCache(store, run_id=run_id)
    entry_ref = cache.put(
        key,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "identity"),
    )

    if mismatch_field == "manifest_profile_sha256":
        entry_bytes = store.get_bytes(entry_ref)
        entry_manifest = store.get_manifest(entry_ref)
        foreign_producer = ProducerInfo(
            component="tests.res_01.foreign_cache_epoch",
            version="1.0.0",
        )
        altered_ref = store.put_bytes(
            entry_bytes,
            PutOptions(
                kind=entry_ref.kind,
                media_type=entry_ref.media_type,
                schema=entry_manifest.artifact_schema,
                producer=foreign_producer,
            ),
            return_selected_profile=True,
        )
        assert altered_ref.artifact_id == entry_ref.artifact_id
        assert altered_ref.kind == entry_ref.kind
        assert altered_ref.media_type == entry_ref.media_type
        assert altered_ref.manifest_profile_sha256 is not None
        assert altered_ref.manifest_profile_sha256 != entry_ref.manifest_profile_sha256
        assert store.get_bytes(altered_ref) == entry_bytes
        assert store.get_manifest(altered_ref).producer == foreign_producer
    elif mismatch_field == "artifact_id":
        altered_ref = entry_ref.model_copy(
            update={"artifact_id": "sha256:" + "f" * 64},
        )
    else:
        altered_ref = entry_ref.model_copy(
            update={
                "kind": "scientist.other_cache_entry"
                if mismatch_field == "kind"
                else entry_ref.kind,
                "media_type": "text/plain"
                if mismatch_field == "media_type"
                else entry_ref.media_type,
            }
        )
    assert altered_ref != entry_ref

    fresh = NodeResultCache(store, run_id=run_id)
    if mismatch_field == "artifact_id":
        with pytest.raises(FileNotFoundError):
            fresh.load_entry(altered_ref)
    elif mismatch_field == "manifest_profile_sha256":
        with pytest.raises(ValueError, match="cache_custody: immutable_epoch_mismatch"):
            fresh.load_entry(altered_ref)
    else:
        with pytest.raises(
            ArtifactIntegrityError,
            match="Artifact reference type does not match selected manifest",
        ):
            fresh.load_entry(altered_ref)
    assert fresh.size == 0
    assert not fresh.has(key)
    assert fresh.get(key) is None

    replay = NodeResultCache(store, run_id=run_id)
    assert replay.load_entry(entry_ref) is True
    if mismatch_field == "artifact_id":
        with pytest.raises(FileNotFoundError):
            replay.load_entry(altered_ref)
    elif mismatch_field == "manifest_profile_sha256":
        with pytest.raises(ValueError, match="cache_custody: immutable_epoch_mismatch"):
            replay.load_entry(altered_ref)
    else:
        with pytest.raises(
            ArtifactIntegrityError,
            match="Artifact reference type does not match selected manifest",
        ):
            replay.load_entry(altered_ref)
    preserved = replay.get(key)
    assert preserved is not None
    assert preserved.state.params["marker"] == "identity"

    reopened = NodeResultCache(store, run_id=run_id)
    assert reopened.load_entry(entry_ref) is True
    reloaded = reopened.get(key)
    assert reloaded is not None
    assert reloaded.state.params["marker"] == "identity"


def _meta(raw: str, name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(raw),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description=f"{name} RES-01 test node",
        tags=["test", "res-01"],
        capabilities=Capability.SCIENTIST_NODE,
    )


class _ResumeNode:
    _spec: NodeSpec

    def __init__(self, *, node_id: str, name: str, read_path: str | None = None) -> None:
        self.invocations = 0
        self._spec = NodeSpec(
            metadata=_meta(node_id, name),
            state_reads=[read_path] if read_path is not None else [],
            state_writes=["params." + name.lower()],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def _finish(self, state: ExperimentState) -> NodeOutcome:
        updated = state.model_copy(deep=True)
        updated.params[self._spec.metadata.display_name.lower()] = self.invocations
        return NodeOutcome(status="ok", state=updated)

    def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.invocations += 1
        return self._finish(state)


class _FailOnceNode(_ResumeNode):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fail_once = True

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.invocations += 1
        if self.fail_once:
            self.fail_once = False
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="res_01.stop", message="intentional RES-01 stop"),
            )
        return self._finish(state)


def _resume_workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_res_01_resume",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="a",
                node_id=ComponentId.parse("scientist.node_res_a@1.0.0"),
            ),
            NodeInvocation(
                alias="b",
                node_id=ComponentId.parse("scientist.node_res_b@1.0.0"),
                depends_on=["a"],
            ),
            NodeInvocation(
                alias="c",
                node_id=ComponentId.parse("scientist.node_res_c@1.0.0"),
                depends_on=["b"],
            ),
        ],
    )


def _resume_registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(
        _ResumeNode(
            node_id="scientist.node_res_a@1.0.0",
            name="A",
        )
    )
    registry.register(
        _FailOnceNode(
            node_id="scientist.node_res_b@1.0.0",
            name="B",
            read_path="params.a",
        )
    )
    registry.register(
        _FailOnceNode(
            node_id="scientist.node_res_c@1.0.0",
            name="C",
            read_path="params.b",
        )
    )
    return registry


def _context(
    store: FileSystemCAS, run_id: str, *, selected_profile: bool = False
) -> tuple[ExecutionContext, object]:
    bundle = build_default_registry_bundle(store, return_selected_profile=selected_profile)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    return ExecutionContext(
        store=store, run=run, logger=logging.getLogger("res_01")
    ), bundle.bundle_ref


def _write_known_successful_frontier_checkpoint(
    store: FileSystemCAS,
    *,
    run_dir: Path,
    state: ExperimentState,
    completed_node_alias: str,
    completed_node_id: str,
    completed_nodes: list[str],
    workflow: WorkflowSpec,
    cache_entry_ref: ArtifactRef | None = None,
) -> CheckpointWriteResult:
    """Persist a successful test frontier through the canonical checkpoint hook."""
    hook = CASCheckpointHook(store=store, run_dir=run_dir)
    # These fixtures represent prior nodes whose native outcomes were successful.
    hook.mark_completed_node_status_established(prior_completed_nodes=[])
    result = hook.on_node_complete(
        state=state,
        alias=completed_node_alias,
        node_id=completed_node_id,
        completed_nodes=completed_nodes,
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        cache_entry_ref=cache_entry_ref,
    )
    assert result is not None
    return result


def test_resume_preserves_origin_fingerprint_across_two_stops(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    run_id = "R_res_01_double_resume"
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(run_id=run_id, inputs={"registry_bundle_ref": bundle_ref})
    hook = CASCheckpointHook(store=store, run_dir=tmp_path / "runs" / run_id)

    first = WorkflowExecutor(ctx, registry, checkpoint_hook=hook).execute(workflow, state)
    assert first.report.status == "fail"
    assert [record.alias for record in first.report.nodes] == ["a", "b"]
    first_checkpoint = resolve_latest_checkpoint(store, run_id)
    assert first_checkpoint is not None
    original_fingerprint = compute_workflow_fingerprint(workflow)
    assert first_checkpoint[1].metadata.workflow_fingerprint == original_fingerprint
    assert first_checkpoint[1].metadata.origin_workflow_fingerprint == original_fingerprint

    second = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
    )
    assert second.report.status == "fail"
    assert [record.alias for record in second.report.nodes] == ["b", "c"]
    second_checkpoint = resolve_latest_checkpoint(store, run_id)
    assert second_checkpoint is not None
    assert second_checkpoint[1].metadata.origin_workflow_fingerprint == original_fingerprint

    third = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
    )
    assert third.report.status == "ok"
    assert [record.alias for record in third.report.nodes] == ["c"]
    assert registry.get(ComponentId.parse("scientist.node_res_a@1.0.0")).invocations == 1
    assert registry.get(ComponentId.parse("scientist.node_res_b@1.0.0")).invocations == 2
    assert registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).invocations == 2


def test_full_valid_state_resumes_without_unnecessary_cache_seed(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).fail_once = False
    run_id = "R_res_01_full_state"
    state = ExperimentState(
        run_id=run_id,
        params={"a": 1, "b": 2},
    )
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow=workflow,
    )

    ctx, bundle_ref = _context(store, run_id)
    del ctx
    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
    )

    assert resumed.report.status == "ok"
    assert [record.alias for record in resumed.report.nodes] == ["c"]


def test_resume_rejects_missing_state_written_by_completed_node(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    run_id = "R_res_01_missing_state"
    state = ExperimentState(run_id=run_id, params={"a": 1})
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow=workflow,
    )

    with pytest.raises(CheckpointCorruptedError, match=r"params\.b"):
        resume_from_checkpoint(
            store,
            run_id,
            workflow=workflow,
            registry=registry,
        )
    assert registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).invocations == 0


def test_allow_replay_rebuilds_completed_nodes_for_missing_state(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    registry.get(ComponentId.parse("scientist.node_res_b@1.0.0")).fail_once = False
    registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).fail_once = False
    run_id = "R_res_01_allow_replay"
    state = ExperimentState(run_id=run_id, params={"a": 1})
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow=workflow,
    )

    ctx, bundle_ref = _context(store, run_id)
    del ctx
    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
        resume_strategy="allow_replay",
    )

    assert resumed.report.status == "ok"
    assert [record.alias for record in resumed.report.nodes] == ["a", "b", "c"]


def test_allow_replay_restart_publishes_only_new_frontier(tmp_path: Path) -> None:
    class ReplayInterrupted(BaseException):
        pass

    class InterruptOnceNode(_ResumeNode):
        def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            self.invocations += 1
            if self.invocations == 1:
                raise ReplayInterrupted()
            return self._finish(state)

    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    registry.register(
        InterruptOnceNode(node_id="scientist.node_res_b@1.0.0", name="B", read_path="params.a"),
        override=True,
    )
    run_id = "R_res_01_replay_frontier"
    original_state = ExperimentState(run_id=run_id, params={"a": 1})
    node_a = registry.get(ComponentId.parse("scientist.node_res_a@1.0.0"))
    cached_branch = branch_state(original_state, write_paths=("params.a",))
    cached_branch.state.params["a"] = 11
    matching_cache_ref = NodeResultCache(store, run_id=run_id).put(
        compute_idempotency_key(node_a.spec, original_state),
        node_id="scientist.node_res_a@1.0.0",
        outcome=NodeOutcome(status="ok", state=cached_branch.state),
    )
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=original_state,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow=workflow,
        cache_entry_ref=matching_cache_ref,
    )
    ctx, bundle_ref = _context(store, run_id, selected_profile=True)
    ctx.run.suspend_for_resume()
    with pytest.raises(ReplayInterrupted):
        resume_from_checkpoint(
            store,
            run_id,
            workflow=workflow,
            registry=registry,
            registry_bundle_ref=bundle_ref,
            resume_strategy="allow_replay",
        )
    latest = resolve_latest_checkpoint(store, run_id)
    assert latest is not None
    assert latest[1].metadata.completed_nodes == ["a"]
    assert matching_cache_ref in latest[1].metadata.cache_entry_refs
    assert latest[1].metadata.origin_workflow_fingerprint == compute_workflow_fingerprint(workflow)
    assert node_a.invocations == 0

    registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).fail_once = False
    resumed = resume_from_checkpoint(
        store, run_id, workflow=workflow, registry=registry, registry_bundle_ref=bundle_ref
    )
    assert resumed.report.status == "ok"
    assert resumed.state.params["a"] == 11
    assert [record.alias for record in resumed.report.nodes] == ["b", "c"]


def test_strict_budget_executor_refuses_fake_owner_before_dispatch(tmp_path: Path) -> None:
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor

    class FakeBudgetOwner:
        invocation_settlement_profile = "single_owner_local_v1"

    store = FileSystemCAS(tmp_path)
    ctx, _ = _context(store, "R_fake_budget_owner")
    registry = _resume_registry()
    with pytest.raises(ValueError, match="strict_budget_attempts_profile_not_established"):
        AsyncWorkflowExecutor(
            ctx,
            registry,
            budget_middleware=FakeBudgetOwner(),
            max_parallelism=1,
            strict_budget_attempts=True,
        )
    assert all(registry.get(node.node_id).invocations == 0 for node in _resume_workflow().nodes)
    ctx.run.suspend_for_resume()


def test_changed_functional_input_remains_incompatible_with_checkpoint(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow().model_copy(
        update={
            "nodes": [
                _resume_workflow().nodes[0].model_copy(update={"params": {"mode": "v1"}}),
                *_resume_workflow().nodes[1:],
            ]
        }
    )
    run_id = "R_res_01_changed_input"
    state = ExperimentState(run_id=run_id)
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="a",
        completed_node_id="scientist.node_res_a@1.0.0",
        completed_nodes=["a"],
        workflow=workflow,
    )
    changed = workflow.model_copy(
        update={
            "nodes": [
                workflow.nodes[0].model_copy(update={"params": {"mode": "v2"}}),
                *workflow.nodes[1:],
            ]
        }
    )
    with pytest.raises(WorkflowMismatchError):
        resume_from_checkpoint(store, run_id, workflow=changed, registry=_resume_registry())


def test_duplicate_cache_ref_is_not_independent_coverage(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    writer = NodeResultCache(store, run_id="R_res_01_duplicate")
    entry = writer.put(
        "c" * 64,
        node_id="scientist.node_res_a@1.0.0",
        outcome=_journaled_outcome("R_res_01_duplicate", "A"),
    )
    replay = NodeResultCache(store, run_id="R_res_01_duplicate")
    assert replay.seed_from_entry_refs([entry, entry]) == 1
    assert replay.size == 1
    assert replay.seed_from_entry_refs([]) == 0
