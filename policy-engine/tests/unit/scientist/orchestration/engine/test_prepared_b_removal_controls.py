"""Behavioral matched-removal tests for Prepared-B execution paths.

The tests remove selected properties while preserving markers, then assert the
resulting behavior through real producers and consumers.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import multiprocessing
import textwrap
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from _helpers.run_lifecycle import (
    assert_one_resumed_terminal_lifecycle,
)

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.scientist.orchestration.engine import async_executor as async_engine
from polisyos.scientist.orchestration.engine import state_merge as engine_merge
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
    NodeResultCache,
    _build_journal_proof,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.runner import serialization as wire
from polisyos.scientist.orchestration.engine.runner import state_merge as worker_merge
from polisyos.scientist.orchestration.engine.runner.state_merge import StateMergeConflictError
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state,
    mutation_journal_for_state,
)
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation
from tests.unit.scientist.orchestration.engine.runner.decimal_worker_transport import (
    execute_decimal_worker,
)
from tests.unit.scientist.orchestration.engine.test_async_cache_recovery import (
    GatedPublicationCAS,
    RecoveryNode,
    cold_setup,
)
from tests.unit.scientist.orchestration.engine.test_async_cache_recovery import (
    context as recovery_context,
)
from tests.unit.scientist.orchestration.engine.test_async_cache_recovery import (
    state as recovery_state,
)
from tests.unit.scientist.orchestration.engine.test_async_cache_recovery import (
    workflow as recovery_workflow,
)
from tests.unit.scientist.orchestration.engine.test_async_executor_hardening import (
    _make_ctx,
    _make_node,
    _make_registry,
    _make_workflow,
)
from tests.unit.scientist.orchestration.engine.test_engine_executor_idempotency import (
    test_executor_reexecutes_when_cached_replay_target_is_incompatible as _cache_target_control,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from multiprocessing.connection import Connection
    from pathlib import Path

    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state_branching import BranchedState
    from polisyos.scientist.orchestration.engine.state_merge import MergeResult
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec


def test_branch_isolation_removal_leaks_to_real_parallel_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One branch-state seam covers declared nested COW and failed-node rollback (#1/#9)."""

    async def run_case(
        root: Path,
        *,
        remove_isolation: bool,
        patcher: pytest.MonkeyPatch | None = None,
    ) -> tuple[list[str], list[str]]:
        root.mkdir(parents=True, exist_ok=True)
        writer_finished = threading.Event()
        sibling_observed: list[list[str]] = []

        def fail_after_nested_write(state: ExperimentState) -> NodeOutcome:
            state.params["nested"]["items"].append("failed-branch")
            writer_finished.set()
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="probe.failure", message="expected failed branch", details={}),
            )

        def read_sibling(state: ExperimentState) -> NodeOutcome:
            assert writer_finished.wait(3), "parallel writer did not reach its mutation"
            observed = list(state.params["nested"]["items"])
            sibling_observed.append(observed)
            state.params["observed"] = observed
            return NodeOutcome(status="ok", state=state)

        writer = _make_node(
            fail_after_nested_write,
            node_id="test.prepared_b_failed_nested_writer@1.0.0",
            state_writes=["params.nested.items"],
        )
        sibling = _make_node(
            read_sibling,
            node_id="test.prepared_b_parallel_reader@1.0.0",
            state_writes=["params.observed"],
        )
        registry = _make_registry(
            ("test.prepared_b_failed_nested_writer@1.0.0", writer),
            ("test.prepared_b_parallel_reader@1.0.0", sibling),
        )
        context = _make_ctx(root)
        workflow = _make_workflow(
            NodeInvocation(alias="failed_writer", node_id=str(writer.spec.metadata.component_id)),
            NodeInvocation(alias="sibling", node_id=str(sibling.spec.metadata.component_id)),
            error_policy="continue",
        )
        if remove_isolation:
            actual_branch_state = async_engine.branch_state

            def alias_declared_branch_to_receiver(
                base_state: ExperimentState,
                *,
                write_paths: Iterable[str] = (),
                enforce_write_scope: bool | None = None,
            ) -> BranchedState:
                paths = tuple(write_paths)
                branch = actual_branch_state(
                    base_state, write_paths=paths, enforce_write_scope=enforce_write_scope
                )
                if "params.nested.items" in paths:
                    # Keep the actual branch journal and admitted path marker, but
                    # remove the branch-local receiver at the real executor seam.
                    assert mutation_journal_for_state(branch.state) is branch.journal
                    assert branch.journal.isolated_paths == paths
                    object.__setattr__(branch.state, "params", base_state.params)
                return branch

            assert patcher is not None
            patcher.setattr(async_engine, "branch_state", alias_declared_branch_to_receiver)

        base = ExperimentState(
            run_id="R_prepared_b_branch_removal",
            params={"nested": {"items": ["seed"]}},
        )
        result = await AsyncWorkflowExecutor(context, registry, max_parallelism=2).execute(
            workflow, base
        )
        assert len(sibling_observed) == 1
        return sibling_observed[0], list(result.state.params["nested"]["items"])

    normal_sibling, normal_receiver = asyncio.run(
        run_case(tmp_path / "normal", remove_isolation=False)
    )
    assert normal_sibling == ["seed"]
    assert normal_receiver == ["seed"]

    with monkeypatch.context() as mutation:
        leaked_sibling, leaked_receiver = asyncio.run(
            run_case(tmp_path / "mutant", remove_isolation=True, patcher=mutation)
        )
    # The normal property assertion must turn red after the marker-preserving
    # receiver alias mutant; both the sibling and failed-node receiver show it.
    with pytest.raises(AssertionError):
        assert leaked_sibling == ["seed"]
    assert leaked_sibling == ["seed", "failed-branch"]
    # The returned tier state may be its rollback snapshot; sibling visibility
    # is the decisive consumer property for this failed concurrent producer.
    assert leaked_receiver in (["seed"], ["seed", "failed-branch"])


def _journaled_multi_operation_merge() -> tuple[ExperimentState, MergeResult]:
    base = ExperimentState(
        run_id="R_prepared_b_operation_removal",
        params={"same": 4, "deleted": "remove-me", "safe": "keep"},
    )
    branch = branch_state(base, write_paths=("params",))
    branch.state.params["same"] = 4
    del branch.state.params["deleted"]
    branch.state.params["nullable"] = None
    branch.state.params["added"] = "new"
    outcome = NodeOutcome(status="ok", state=branch.state)
    merged = merge_parallel_outcomes(
        base,
        {"producer": outcome},
        {"producer": ["params"]},
        mutation_journals={"producer": branch.journal},
    )
    return base, merged


def test_merge_operation_removal_is_red_for_direct_and_executor_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one staged-write mechanism spans state merge (#2) and cache replay (#5)."""
    base, normal = _journaled_multi_operation_merge()
    expected = {"same": 4, "safe": "keep", "nullable": None, "added": "new"}
    assert normal.state.params == expected
    assert base.params == {"same": 4, "deleted": "remove-me", "safe": "keep"}

    with monkeypatch.context() as mutation:
        mutation.setattr(engine_merge, "_apply_staged_write", lambda _state, _write: None)
        _, omitted = _journaled_multi_operation_merge()
        with pytest.raises(AssertionError):
            assert omitted.state.params == expected
        assert omitted.state.params == {"same": 4, "deleted": "remove-me", "safe": "keep"}

    # Existing whole executor route is the second real consumer of the same
    # mechanism: skipping application makes an incompatible cache target look
    # compatible and its defining test must turn red.
    _cache_target_control(
        tmp_path / "executor-positive",
    )
    with monkeypatch.context() as mutation:
        mutation.setattr(engine_merge, "_apply_staged_write", lambda _state, _write: None)
        with pytest.raises(AssertionError):
            _cache_target_control(
                tmp_path / "executor-mutant",
            )


def test_replay_proof_removal_admits_stale_real_cache_to_fresh_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A marker-preserving stale epoch reaches the actual fresh cache consumer (#4)."""
    run_id = "R_prepared_b_proof_removal"
    key = "p" * 64
    store = FileSystemCAS(tmp_path / "cas")
    producer = NodeResultCache(store, run_id=run_id)
    outcome_state = branch_state(
        ExperimentState(run_id=run_id, params={"admitted": "value"}), write_paths=()
    ).state
    entry_ref = producer.put(
        key,
        node_id="scientist.node_prepared_b_proof@1.0.0",
        outcome=NodeOutcome(status="ok", state=outcome_state),
    )
    entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(entry_ref.artifact_id))
    )
    manifest = store.get_manifest(entry_ref.artifact_id)
    stale_without_proof = entry.model_copy(update={"replay_epoch": "2.0", "journal_proof": None})
    stale_with_current_custody = stale_without_proof.model_copy(
        update={
            "journal_proof": _build_journal_proof(
                stale_without_proof,
                manifest_schema=manifest.artifact_schema,
                manifest_producer=manifest.producer,
            )
        }
    )
    stale_ref = store.put_json(
        stale_with_current_custody.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
        ),
    )

    ordinary = NodeResultCache(FileSystemCAS(tmp_path / "cas"), run_id=run_id)
    assert ordinary.load_entry(stale_ref) is False
    assert ordinary.get(key) is None

    with monkeypatch.context() as mutation:
        mutation.setattr(NodeResultCache, "_replay_proof_valid", lambda *_args, **_kwargs: True)
        removed_guard = NodeResultCache(FileSystemCAS(tmp_path / "cas"), run_id=run_id)
        assert removed_guard.load_entry(stale_ref) is True
        reused = removed_guard.get(key)
    assert reused is not None
    assert reused.state.params == {"admitted": "value"}


def _install_early_cache_publication_mutant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compile the exact current _recover_cache body with a one-statement mutation."""
    module = inspect.getmodule(AsyncWorkflowExecutor)
    assert module is not None
    source = textwrap.dedent(inspect.getsource(AsyncWorkflowExecutor._recover_cache))
    module_ast = ast.parse(source)
    method = next(
        node
        for node in module_ast.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_recover_cache"
    )
    recover = next(
        node for node in method.body if isinstance(node, ast.FunctionDef) and node.name == "recover"
    )
    cache_assignment = next(
        index
        for index, node in enumerate(recover.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "cache" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "NodeResultCache"
    )
    publish_early = ast.Assign(
        targets=[
            ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr="_cache",
                ctx=ast.Store(),
            )
        ],
        value=ast.Name(id="cache", ctx=ast.Load()),
    )
    recover.body.insert(cache_assignment + 1, publish_early)
    ast.fix_missing_locations(module_ast)
    namespace = dict(module.__dict__)
    filename = inspect.getsourcefile(AsyncWorkflowExecutor._recover_cache) or "<async_executor>"
    exec(compile(module_ast, filename, "exec"), namespace)  # noqa: S102 - actual source-body mutant
    monkeypatch.setattr(AsyncWorkflowExecutor, "_recover_cache", namespace["_recover_cache"])


async def _late_recovery_case(
    tmp_path: Path,
) -> tuple[NodeOutcome | None, bool, NodeOutcome | None]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store, executor, node, _spec, refs = await cold_setup(tmp_path, "trace")
    executor._workflow_timeout_s = None
    key = compute_idempotency_key(node.spec, recovery_state("R_cache_recovery", current=True))
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(
        executor.execute(_spec, recovery_state("R_cache_recovery", current=True))
    )

    def interrupt_then_release() -> None:
        assert store.entered.wait(3), "recovery did not reach the actual CAS trace read"
        loop.call_soon_threadsafe(task.cancel)
        time.sleep(0.15)
        store.release.set()

    helper = threading.Thread(target=interrupt_then_release)
    helper.start()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        store.release.set()
        helper.join(3)
    assert await asyncio.to_thread(store.finished.wait, 3)
    assert store.verify(refs[0].artifact_id).ok
    local_cache = executor._cache
    late_outcome = local_cache.get(key) if local_cache is not None else None
    fresh = NodeResultCache(FileSystemCAS(tmp_path / "cas"), run_id="R_cache_recovery")
    fresh_admitted = fresh.load_entry(refs[0])
    fresh_outcome = fresh.get(key)
    return late_outcome, fresh_admitted, fresh_outcome


@pytest.mark.asyncio
async def test_cancelled_recovery_cache_stays_private_until_owner_accepts_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source-body removal exposes a late real CAS admission after cancellation (#6)."""
    normal_late, normal_fresh, normal_reader = await _late_recovery_case(tmp_path / "normal")
    assert normal_late is None
    assert normal_fresh is True
    assert normal_reader is not None

    with monkeypatch.context() as mutation:
        _install_early_cache_publication_mutant(mutation)
        mutant_late, mutant_fresh, mutant_reader = await _late_recovery_case(tmp_path / "mutant")
    with pytest.raises(AssertionError):
        assert mutant_late is None
    assert mutant_late is not None
    assert mutant_fresh is True
    assert mutant_reader is not None


@dataclass(frozen=True)
class _CancelledPublication:
    context: ExecutionContext
    node: RecoveryNode
    registry: NodeRegistry
    spec: WorkflowSpec
    store: GatedPublicationCAS
    cache: NodeResultCache
    stranded: NodeOutcome | None


async def _cancelled_publication_case(
    tmp_path: Path,
    *,
    patcher: pytest.MonkeyPatch,
    remove_cleanup: bool,
) -> _CancelledPublication:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = GatedPublicationCAS(tmp_path / "cas")
    node = RecoveryNode()
    spec, registry = recovery_workflow(node)
    run_dir = tmp_path / "run"
    execution_context = recovery_context(store, "R_publication", run_dir)
    executor = AsyncWorkflowExecutor(execution_context, registry)
    key = compute_idempotency_key(node.spec, recovery_state("R_publication"))
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(executor.execute(spec, recovery_state("R_publication")))

    def cancel_then_release() -> None:
        assert store.entered.wait(3), "cache writer did not enter the actual CAS publication"
        loop.call_soon_threadsafe(task.cancel)
        time.sleep(0.3)
        store.release.set()

    helper = threading.Thread(target=cancel_then_release)
    helper.start()
    try:
        with patcher.context() as mutation:
            if remove_cleanup:
                mutation.setattr(NodeResultCache, "discard", lambda _self, _key: None)
            with pytest.raises(asyncio.CancelledError):
                await task
    finally:
        store.release.set()
        helper.join(3)
    assert store.published is not None
    assert FileSystemCAS(tmp_path / "cas").verify(store.published.artifact_id).ok
    trace_events = [
        json.loads(line)
        for line in execution_context.run.trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert not any(event.get("event") == "NODE_CACHE_STORE" for event in trace_events)
    local_cache = executor._cache
    assert local_cache is not None
    stranded = local_cache.get(key)
    return _CancelledPublication(
        context=execution_context,
        node=node,
        registry=registry,
        spec=spec,
        store=store,
        cache=local_cache,
        stranded=stranded,
    )


async def _resume_after_cancelled_publication(case: _CancelledPublication, root: Path) -> None:
    first_context = case.context
    first_context.run.suspend_for_resume()
    fresh_store = FileSystemCAS(root / "cas")
    fresh_context = recovery_context(
        fresh_store,
        "R_publication",
        root / "run",
        resume_from=first_context.run,
    )
    result = await AsyncWorkflowExecutor(fresh_context, case.registry).execute(
        case.spec, recovery_state("R_publication", current=True)
    )
    assert case.node.calls == 2
    assert result.state.params == {
        "seed": 7,
        "same": 4,
        "nullable": None,
        "unrelated": "new",
        "result": 14,
    }
    terminal = assert_one_resumed_terminal_lifecycle(fresh_context.run)
    assert sum(event.get("event") == "NODE_CACHE_HIT" for event in terminal) == 0


@pytest.mark.asyncio
async def test_cancelled_cache_put_is_discarded_before_any_fresh_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check actual CAS, old cache, trace, and fresh resume for publication cleanup (#8)."""
    normal_root = tmp_path / "normal"
    normal = await _cancelled_publication_case(
        normal_root, patcher=monkeypatch, remove_cleanup=False
    )
    assert normal.stranded is None
    await _resume_after_cancelled_publication(normal, normal_root)

    mutant_root = tmp_path / "mutant"
    with monkeypatch.context() as mutation:
        mutant = await _cancelled_publication_case(
            mutant_root, patcher=mutation, remove_cleanup=True
        )
    with pytest.raises(AssertionError):
        assert mutant.stranded is None
    assert mutant.stranded is not None
    assert mutant.cache.size == 1
    # The untraced immutable object cannot be consumed by a fresh run. It uses
    # the real trace and therefore recomputes, even while the old owner leaked.
    await _resume_after_cancelled_publication(mutant, mutant_root)


def test_current_wire_schema_removal_accepts_unknown_version_with_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The actual decoder rejects unknown typed outcome versions (#11)."""
    outcome = NodeOutcome(
        status="ok",
        state=ExperimentState(run_id="R_wire_schema_removal", params={"marker": "present"}),
    )
    valid = wire.serialize_outcome(outcome)
    envelope = json.loads(valid)
    assert envelope["wire_schema"] == wire._OUTCOME_WIRE_SCHEMA
    envelope["wire_schema"] = "polisyos.scientist.outcome_wire.v999"
    malformed = json.dumps(envelope, separators=(",", ":")).encode()
    with pytest.raises(wire.DeserializationError):
        wire.deserialize_outcome(malformed)

    original = wire._read_typed_envelope

    def ignore_unknown_outer_schema(raw: object, *, outcome: bool) -> object:
        if (
            outcome
            and isinstance(raw, dict)
            and raw.get("wire_schema") == "polisyos.scientist.outcome_wire.v999"
            and set(raw) == {"wire_schema", "value"}
        ):
            # The bytes retain the unknown-version marker; the mutant skips
            # only its admission check and forwards the actual typed payload.
            return raw["value"]
        return original(raw, outcome=outcome)

    with monkeypatch.context() as mutation:
        mutation.setattr(wire, "_read_typed_envelope", ignore_unknown_outer_schema)
        accepted = wire.deserialize_outcome(malformed)
    assert accepted.status == "ok"
    assert accepted.state.params == {"marker": "present"}


def _execute_decimal_worker_without_budget_tag(
    payload: dict[str, object],
    backend: str,
    expected_budgets: dict[str, Decimal],
    attempts_path: str,
    result_sender: Connection,
) -> None:
    """Spawn target: remove only the typed-budget gate, then run the real worker."""
    from polisyos.scientist.orchestration.engine.runner import serialization as child_wire

    child_wire._typed_state_payload = lambda _payload: None
    execute_decimal_worker(payload, backend, expected_budgets, attempts_path, result_sender)


def _run_decimal_worker(
    target: Callable[..., None],
    payload: dict[str, object],
    expected: dict[str, Decimal],
    attempts_path: Path,
    store_root: Path,
) -> tuple[str, object]:
    payload = dict(payload)
    payload["context_meta"] = {
        "run_id": payload["context_meta"]["run_id"],
        "store_config": {"backend": "filesystem", "root": str(store_root)},
    }
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=target,
        args=(payload, "stdlib", expected, str(attempts_path), sender),
    )
    process.start()
    sender.close()
    try:
        assert receiver.poll(30), "physical decimal worker did not return a typed result"
        message = receiver.recv()
    finally:
        receiver.close()
        process.join(30)
        if process.is_alive():
            process.terminate()
            process.join(5)
        worker_exitcode = process.exitcode
        if not process.is_alive():
            process.close()
    assert worker_exitcode == 0
    return message


def test_typed_decimal_refusal_survives_actual_worker_and_marker_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The child consumes real typed state bytes before running the actual node (#12)."""
    monkeypatch.setattr(wire, "_dumps", lambda obj: json.dumps(obj, separators=(",", ":")).encode())
    monkeypatch.setattr(wire, "_loads", json.loads)
    original = ExperimentState(
        run_id="R_decimal_worker_removal",
        budgets={"run": Decimal("123.4500")},
    )
    expected = dict(original.budgets)
    encoded = json.loads(wire.serialize_state(original))
    assert isinstance(encoded["value"]["budgets"]["run"], dict)
    encoded["value"]["budgets"]["run"] = "123.4500"
    malformed = json.dumps(encoded, separators=(",", ":")).encode()
    payload = {
        "node_id": "scientist.node_decimal_transport@1.0.0",
        "alias": "decimal",
        "state_bytes": malformed,
        "timeout_s": None,
        "context_meta": {"run_id": original.run_id},
    }
    attempts = tmp_path / "attempts.jsonl"
    ordinary = _run_decimal_worker(
        execute_decimal_worker,
        payload,
        expected,
        attempts,
        tmp_path / "ordinary-store",
    )
    assert ordinary[0] == "error"
    assert "DeserializationError" in ordinary[1]
    assert not attempts.exists()

    accepted = _run_decimal_worker(
        _execute_decimal_worker_without_budget_tag,
        payload,
        expected,
        attempts,
        tmp_path / "mutant-store",
    )
    assert accepted[0] == "result"
    outcome = wire.deserialize_outcome(accepted[1])
    assert outcome.status == "ok"
    assert type(outcome.state.budgets["run"]) is Decimal
    assert outcome.state.budgets["run"].as_tuple() == Decimal("123.4500").as_tuple()
    assert len(attempts.read_text(encoding="utf-8").splitlines()) == 1


def test_worker_merge_conflict_removal_changes_real_typed_receiver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typed child outcomes must meet the receiver conflict rule (#13)."""
    base = ExperimentState(run_id="R_worker_merge_removal", params={"shared": "base"})
    alpha = branch_state(base, write_paths=("params.shared",))
    alpha.state.params["shared"] = "alpha"
    beta = branch_state(base, write_paths=("params.shared",))
    beta.state.params["shared"] = "beta"
    encoded = {
        "alpha": wire.serialize_outcome(NodeOutcome(status="ok", state=alpha.state)),
        "beta": wire.serialize_outcome(NodeOutcome(status="ok", state=beta.state)),
    }
    base_bytes = wire.serialize_state(base)
    request = {
        "requested_aliases": ("alpha", "beta"),
        "write_specs": {"alpha": ["params.shared"], "beta": ["params.shared"]},
    }
    with pytest.raises(StateMergeConflictError):
        worker_merge.merge_tier_outcomes(base_bytes, encoded, **request)

    with monkeypatch.context() as mutation:
        mutation.setattr(
            engine_merge,
            "_resolve_conflicts",
            lambda staged, *, conflict_policy: (staged, [], []),
        )
        accepted = worker_merge.merge_tier_outcomes(base_bytes, encoded, **request)
    receiver = wire.deserialize_state(accepted.state_bytes)
    assert set(accepted.node_outcomes) == {"alpha", "beta"}
    assert receiver.params["shared"] == "beta"


# Reused current controls remain in their original full modules, with no duplicate
# local wrapper: #3 native-state presence; #7 selected-view ArtifactRef identity;
# #10 timeout worker declared-operation replay into a changed receiver.
EXISTING_MATCHED_CONTROLS = (
    "tests/unit/scientist/orchestration/engine/test_native_state_cache_semantics.py::"
    "test_removing_presence_discriminator_is_caught_with_markers_intact",
    "tests/unit/scientist/orchestration/engine/test_cache_reference_custody.py::"
    "test_selected_view_identity_removal_probe_rejects_verified_default_reuse",
    "tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py::"
    "test_canonical_timeout_worker_replays_operations_into_changed_receiver",
)
