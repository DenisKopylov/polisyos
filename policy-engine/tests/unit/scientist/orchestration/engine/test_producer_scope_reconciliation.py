"""Reconcile genuine producer grants with typed publication and reopened replay.

The worker profile exercises the shared serialized activity entrypoint, rather
than claiming a deployed Ray/Temporal service or a separate OS process.
"""

from __future__ import annotations

import json
import logging
from hashlib import sha256
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.registry.refs import ContextAdaptiveParameterBundleRef
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner._activity_worker import run_node_in_worker
from polisyos.scientist.orchestration.engine.runner.serialization import (
    deserialize_outcome,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state,
    mutation_journal_for_state,
)
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_WRITE_PATHS = ["params.owned", "params.alias", "artifacts_index.bundle"]
_CONTOURS = ("sequential", "async", "worker")
_REFUSALS = ("nested_widen", "release_scope", "root_replace", "neighbor_alias")
_REPLAY_KEY = sha256(b"scope-real-outcome").hexdigest()
_MODEL_MUTATIONS = (
    "input_attribute",
    "report_attribute",
    "top_level_attribute",
    "state_copy_update",
    "detached_ref_rebind",
)


class _ScopeProducer:
    def __init__(self, refusal: str | None = None) -> None:
        self.refusal = refusal
        self.calls = 0
        self.held_state: ExperimentState | None = None
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.scope_reconciliation@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Producer scope reconciliation",
                description="Actual grant, mutation intent, and typed publication",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=[],
            state_writes=_WRITE_PATHS,
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        self.held_state = state
        journal = mutation_journal_for_state(state)
        assert journal is not None and journal.enforce_write_scope
        assert journal.isolated_paths == tuple(sorted(_WRITE_PATHS))
        if self.refusal is not None:
            before = state.model_dump(mode="json")
            before_operations = list(journal.operations)
            with pytest.raises(ValueError, match="producer|undeclared state_writes"):
                self._attempt_refused_write(state)
            assert state.model_dump(mode="json") == before
            assert journal.operations == before_operations

        # The ordinary nested API attenuates the original grant. A mutable
        # descendant cannot acquire the sibling artifact or alias permissions.
        child = branch_state(state, write_paths=("params.owned.rows",))
        assert child.journal.enforce_write_scope
        with pytest.raises(ValueError, match="undeclared state_writes"):
            child.state.params["alias"] = {"v": 99}
        child.state.params["owned"]["rows"].append({"id": "child", "v": 3})
        assert state.params["owned"]["rows"] == [{"id": "old", "v": 1}]

        rows = state.params["owned"]["rows"]
        held = rows[0]
        rows.append({"id": "new", "v": 0})
        state.params["alias"] = held
        assert state.params["alias"] is held
        held["v"] = 5
        effect = ctx.store.put_json(
            {"rows": rows, "alias": state.params["alias"]},
            PutOptions(kind="ir.context_adaptive_parameter_bundle", media_type="application/json"),
        )
        offered = ContextAdaptiveParameterBundleRef(artifact_id=str(effect.artifact_id))
        state.artifacts_index["bundle"] = offered
        accepted = state.artifacts_index["bundle"]
        assert isinstance(accepted, ArtifactRef)
        assert accepted.model_dump(mode="json") == offered.model_dump(mode="json")
        assert ctx.store.verify(accepted).ok
        return NodeOutcome(status="ok", state=state, artifacts=[accepted])

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return self.execute(ctx, state)

    def _attempt_refused_write(self, state: ExperimentState) -> None:
        match self.refusal:
            case "nested_widen":
                branch_state(state, write_paths=("params",))
            case "release_scope":
                branch_state(state, write_paths=_WRITE_PATHS, enforce_write_scope=False)
            case "root_replace":
                state.params = {"neighbor": {"v": 99}}
            case "neighbor_alias":
                state.params["neighbor"] = state.params["owned"]["rows"][0]
            case _:
                raise AssertionError("unsupported refusal input")


def _initial_state() -> ExperimentState:
    return ExperimentState(
        run_id="R_scope_reconciliation",
        params={"owned": {"rows": [{"id": "old", "v": 1}]}, "neighbor": {"v": 11}},
    )


async def _run_producer(
    root: Path,
    contour: str,
    producer: _ScopeProducer,
    monkeypatch: pytest.MonkeyPatch,
    *,
    initial: ExperimentState | None = None,
    observe_base_mutation: bool = False,
) -> tuple[NodeOutcome, ExperimentState, ExperimentState]:
    store = FileSystemCAS(root)
    bundle = build_default_registry_bundle(store).bundle_ref
    initial = _initial_state() if initial is None else initial
    before = initial.model_dump(mode="json")
    registry = NodeRegistry()
    registry.register(producer)
    if contour == "worker":
        # Registry injection chooses this controlled node; the actual worker
        # reconstructs its context/store, establishes its grant, runs retry,
        # and transports the outcome plus the versioned mutation journal.
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.registry.discover_nodes",
            lambda target: target.register(producer),
        )
        outcome_bytes = await run_node_in_worker(
            {
                "node_id": str(producer.spec.metadata.component_id),
                "alias": "produce",
                "state_bytes": serialize_state(initial),
                "max_retries": 0,
                "context_meta": {
                    "run_id": initial.run_id,
                    "store_config": {"backend": "filesystem", "root": str(root)},
                },
            }
        )
        outcome = deserialize_outcome(outcome_bytes)
        public_state = outcome.state
    else:
        run = RunContext.start(store, bundle, run_id=initial.run_id)
        ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("scope-producer"))
        workflow = WorkflowSpec(
            workflow_id="producer_scope_reconciliation",
            nodes=[NodeInvocation(alias="produce", node_id=producer.spec.metadata.component_id)],
        )
        executor = (
            WorkflowExecutor(ctx, registry)
            if contour == "sequential"
            else AsyncWorkflowExecutor(ctx, registry)
        )
        result = (
            executor.execute(workflow, initial)
            if contour == "sequential"
            else await executor.execute(workflow, initial)
        )
        assert result.report.status == "ok"
        assert store.verify(result.run_ref).ok
        public_state = result.state
        events = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
        publications = [event for event in events if event["event"] == "NODE_CACHE_STORE"]
        assert len(publications) == 1
        cache_ref = ArtifactRef.model_validate(publications[0]["refs"]["outputs"][0])
        actual_reader = NodeResultCache(FileSystemCAS(root), initial.run_id)
        assert actual_reader.load_entry(cache_ref)
        payload = json.loads(store.get_bytes(cache_ref))
        outcome = actual_reader.get(payload["idempotency_key"])
        assert outcome is not None
    if not observe_base_mutation:
        assert initial.model_dump(mode="json") == before
    assert outcome.status == "ok"
    assert producer.calls == 1
    return outcome, initial, public_state


def _assert_reopened_consumer(root: Path, outcome: NodeOutcome, initial: ExperimentState) -> None:
    store = FileSystemCAS(root)
    original_effect = outcome.artifacts[0]
    assert store.verify(original_effect).ok
    assert json.loads(store.get_bytes(original_effect)) == {
        "rows": [{"id": "old", "v": 5}, {"id": "new", "v": 0}],
        "alias": {"id": "old", "v": 5},
    }
    writer = NodeResultCache(store, initial.run_id)
    ref = writer.put(_REPLAY_KEY, "scientist.scope_reconciliation@1.0.0", outcome)
    reopened = FileSystemCAS(root)
    reader = NodeResultCache(reopened, initial.run_id)
    assert reopened.verify(ref).ok
    assert reader.load_entry(ref)
    cached = reader.get(_REPLAY_KEY)
    assert cached is not None
    journal = mutation_journal_for_state(cached.state)
    assert journal is not None
    assert any(operation.operation_group is not None for operation in journal.operations)
    current = _initial_state()
    current.params["owned"]["rows"].append({"id": "consumer-neighbor", "v": 23})
    current.params["neighbor"]["v"] = 29
    before = current.model_dump(mode="json")
    merged = merge_parallel_outcomes(current, {"produce": cached}, {"produce": _WRITE_PATHS})
    assert merged.applied
    assert current.model_dump(mode="json") == before
    assert merged.state.params == {
        "owned": {
            "rows": [
                {"id": "old", "v": 5},
                {"id": "consumer-neighbor", "v": 23},
                {"id": "new", "v": 0},
            ]
        },
        "neighbor": {"v": 29},
        "alias": {"id": "old", "v": 5},
    }
    accepted = merged.state.artifacts_index["bundle"]
    assert isinstance(accepted, ArtifactRef)
    assert accepted.model_dump(mode="json") == original_effect.model_dump(mode="json")
    assert reopened.verify(accepted).ok
    assert reopened.get_bytes(accepted) == store.get_bytes(original_effect)


@pytest.mark.asyncio
@pytest.mark.parametrize("contour", _CONTOURS)
@pytest.mark.parametrize("refusal", [None, *_REFUSALS])
async def test_real_producer_grants_reconcile_with_reopened_cache_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contour: str, refusal: str | None
) -> None:
    producer = _ScopeProducer(refusal)
    root = tmp_path / "cas"
    outcome, initial, public_state = await _run_producer(root, contour, producer, monkeypatch)
    _assert_reopened_consumer(root, outcome, initial)
    # Completion is a genuine executor/wire boundary. The returned public
    # view permits later ordinary consumer edits; a provider-held old view
    # retains its exact original producer grant after that publication.
    public_state.params["post_completion"] = {"v": 31}
    assert public_state.params["post_completion"] == {"v": 31}
    assert producer.held_state is not None
    held_before = producer.held_state.model_dump(mode="json")
    with pytest.raises(ValueError, match="undeclared state_writes"):
        producer.held_state.params["post_completion"] = {"v": 97}
    assert producer.held_state.model_dump(mode="json") == held_before


class _ModelScopeProducer(_ScopeProducer):
    def __init__(self, mutation: str) -> None:
        super().__init__()
        self.mutation = mutation

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        self.held_state = state
        journal = mutation_journal_for_state(state)
        assert journal is not None and journal.enforce_write_scope
        before = state.model_dump(mode="json")
        operations_before = list(journal.operations)
        error = None
        try:
            match self.mutation:
                case "input_attribute":
                    state.inputs["source"].media_type = "application/octet-stream"
                case "report_attribute":
                    state.reports_index["source"].artifact_id = ArtifactRef(
                        artifact_id="sha256:" + "f" * 64,
                        kind="test.readonly",
                        media_type="application/json",
                    ).artifact_id
                case "top_level_attribute":
                    assert state.preflight_report_ref is not None
                    state.preflight_report_ref.manifest_profile_sha256 = "sha256:" + "e" * 64
                case "state_copy_update":
                    state = state.model_copy(
                        update={
                            "params": {"owned": before["params"]["owned"], "neighbor": {"v": 99}}
                        }
                    )
                case "detached_ref_rebind":
                    detached = state.inputs["source"].model_copy(
                        update={"media_type": "application/octet-stream"}
                    )
                    state.inputs["source"] = detached
                case _:
                    raise AssertionError("unsupported model mutation")
        except ValueError as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        observation = {
            "mutation": self.mutation,
            "error": error,
            "state_before": before,
            "state_after": state.model_dump(mode="json"),
            "journal_before": [
                operation.model_dump(mode="json") for operation in operations_before
            ],
            "journal_after": [
                operation.model_dump(mode="json") for operation in journal.operations
            ],
        }
        effect = ctx.store.put_json(
            observation, PutOptions(kind="test.scope_observation", media_type="application/json")
        )
        state.artifacts_index["bundle"] = effect
        return NodeOutcome(status="ok", state=state, artifacts=[effect])


@pytest.mark.asyncio
@pytest.mark.parametrize("contour", _CONTOURS)
@pytest.mark.parametrize("mutation", list(_MODEL_MUTATIONS))
async def test_existing_typed_model_mutations_refuse_before_state_or_journal_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contour: str, mutation: str
) -> None:
    root = tmp_path / "cas"
    original_store = FileSystemCAS(root)
    original_ref = original_store.put_json(
        {"readonly": 7}, PutOptions(kind="test.readonly", media_type="application/json")
    )
    expected_ref = original_ref.model_dump(mode="json")
    initial = _initial_state()
    # These ordinary model assignments establish genuine typed values after
    # DTO validation. The oracle uses actual post-construction identities.
    initial.inputs["source"] = original_ref
    initial.reports_index["source"] = original_ref
    initial.preflight_report_ref = original_ref
    assert initial.inputs["source"] is initial.reports_index["source"]
    assert initial.inputs["source"] is initial.preflight_report_ref
    before = initial.model_dump(mode="json")
    producer = _ModelScopeProducer(mutation)
    outcome, _, public_state = await _run_producer(
        root, contour, producer, monkeypatch, initial=initial, observe_base_mutation=True
    )
    reopened = FileSystemCAS(root)
    observation_ref = outcome.artifacts[0]
    assert reopened.verify(observation_ref).ok
    observed = json.loads(reopened.get_bytes(observation_ref))
    (tmp_path / "model-scope-observation.json").write_text(
        json.dumps(
            {
                "contour": contour,
                "observation": observed,
                "base_before": before,
                "base_after": initial.model_dump(mode="json"),
                "public_state": public_state.model_dump(mode="json"),
                "observation_ref": observation_ref.model_dump(mode="json"),
            },
            indent=2,
        )
        + "\n"
    )
    assert observed["error"] is not None
    assert "undeclared state_writes" in observed["error"]["message"]
    assert observed["state_after"] == observed["state_before"]
    assert observed["journal_after"] == observed["journal_before"]
    assert initial.model_dump(mode="json") == before
    accepted = ArtifactRef.model_validate(expected_ref)
    assert reopened.verify(accepted).ok
    assert json.loads(reopened.get_bytes(accepted)) == {"readonly": 7}
    assert public_state.inputs["source"].model_dump(mode="json") == expected_ref
