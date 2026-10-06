"""Actual producer/cache/reopened consumers retain live list descendant ownership."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_CASES = {
    "no_shift": [{"id": "b", "v": 5}, {"id": "c", "v": 2}],
    "insert_existing": [{"id": "new", "v": 0}, {"id": "b", "v": 5}, {"id": "c", "v": 2}],
    "insert_new": [{"id": "new", "v": 5}, {"id": "b", "v": 1}, {"id": "c", "v": 2}],
    "pop_shift": [{"id": "c", "v": 5}],
    "remove_shift": [{"id": "c", "v": 5}],
    "delete_slice": [{"id": "c", "v": 5}],
    "set_slice": [{"id": "new", "v": 0}, {"id": "extra", "v": 0}, {"id": "c", "v": 5}],
    "reverse": [{"id": "c", "v": 2}, {"id": "b", "v": 5}],
    "sort": [{"id": "c", "v": 2}, {"id": "b", "v": 5}],
    "repeat_alias": [
        {"id": "b", "v": 5},
        {"id": "c", "v": 2},
        {"id": "b", "v": 5},
        {"id": "c", "v": 2},
    ],
    "negative_set": [{"id": "b", "v": 1}, {"id": "new", "v": 5}],
    "sparse_null_delete": [{"id": "b", "v": None}, {"id": "c"}],
    "orphan": [{"id": "c", "v": 2}],
}


class _ListNode:
    def __init__(self, case):
        self.case = case
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.native_list_intent@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Live list journal consumer",
                description="Mutate actual list members after structural edits",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.x", "params.rows"],
            state_writes=["params.rows"],
        )

    def execute(self, ctx, state):
        raise AssertionError("Native async method required")

    async def execute_async(self, ctx, state):
        self.calls += 1
        rows = state.params["rows"]
        first, second = rows
        match self.case:
            case "no_shift":
                first["v"] = 5
            case "insert_existing":
                rows.insert(0, {"id": "new", "v": 0})
                first["v"] = 5
            case "insert_new":
                rows.insert(0, {"id": "new", "v": 0})
                rows[0]["v"] = 5
            case "pop_shift":
                rows.pop(0)
                second["v"] = 5
            case "remove_shift":
                rows.remove(first)
                second["v"] = 5
            case "delete_slice":
                del rows[:1]
                second["v"] = 5
            case "set_slice":
                rows[:1] = [{"id": "new", "v": 0}, {"id": "extra", "v": 0}]
                second["v"] = 5
            case "reverse":
                rows.reverse()
                first["v"] = 5
            case "sort":
                rows.sort(key=lambda row: row["id"], reverse=True)
                first["v"] = 5
            case "repeat_alias":
                rows *= 2
                first["v"] = 5
            case "negative_set":
                rows[-1] = {"id": "new", "v": 0}
                rows[-1]["v"] = 5
            case "sparse_null_delete":
                first["v"] = None
                del second["v"]
            case "orphan":
                removed = rows.pop(0)
                removed["v"] = 99
        ref = ctx.store.put_json(
            {"case": self.case, "rows": rows},
            PutOptions(kind="scientist.native_list_effect", media_type="application/json"),
        )
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


@pytest.mark.asyncio
@pytest.mark.parametrize("case", list(_CASES))
async def test_structural_list_intents_reopen_and_preserve_exact_native_rows(tmp_path, case):
    cas = tmp_path / "cas"
    store = FileSystemCAS(cas)
    bundle = build_default_registry_bundle(store).bundle_ref
    node = _ListNode(case)
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="native_list_ownership",
        nodes=[NodeInvocation(alias="list", node_id=node.spec.metadata.component_id)],
    )
    expected = _CASES[case]
    for warm in (False, True):
        reopened = FileSystemCAS(cas)
        run = RunContext.start(reopened, bundle, run_id="R_list_ownership")
        state = ExperimentState(
            run_id="R_list_ownership",
            params={
                "x": 2,
                "rows": [{"id": "b", "v": 1}, {"id": "c", "v": 2}],
                "unrelated": "new" if warm else "old",
            },
            budgets={"neighbor_reserved_usd": Decimal("11") if warm else Decimal("7")},
        )
        before = state.model_dump(mode="json")
        result = await AsyncWorkflowExecutor(
            ExecutionContext(store=reopened, run=run, logger=logging.getLogger("list-owner")),
            registry,
        ).execute(workflow, state)
        assert result.report.status == "ok"
        assert result.state.params["rows"] == expected
        assert result.state.params["unrelated"] == state.params["unrelated"]
        assert (
            result.state.budgets["neighbor_reserved_usd"] == state.budgets["neighbor_reserved_usd"]
        )
        assert state.model_dump(mode="json") == before
        assert node.calls == 1
        effect = result.report.nodes[0].artifacts[0]
        assert reopened.verify(effect).ok
        assert json.loads(reopened.get_bytes(effect)) == {"case": case, "rows": expected}
        assert reopened.verify(result.run_ref).ok
        records = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
        stores = [event for event in records if event["event"] == "NODE_CACHE_STORE"]
        assert len(stores) == 1
        cache_ref = ArtifactRef.model_validate(stores[0]["refs"]["outputs"][0])
        assert reopened.verify(cache_ref).ok
        entry = json.loads(reopened.get_bytes(cache_ref))
        assert entry["outcome_payload"]["state"]["params"]["rows"] == expected
        assert len([event for event in records if event["event"] == "NODE_CACHE_HIT"]) == int(warm)


def test_narrow_list_descendant_refuses_structural_write_before_mutation(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    retained = store.put_json(
        {"evidence": "retained"}, PutOptions(kind="test", media_type="application/json")
    )
    state = ExperimentState(run_id="R_narrow", params={"rows": [{"v": 1}, {"v": 2}]})
    branch = branch_state(state, write_paths=["params.rows.0.v"])
    branch_before = branch.state.model_dump(mode="json")
    base_before = state.model_dump(mode="json")
    evidence_before = store.get_bytes(retained)
    with pytest.raises(ValueError, match="undeclared state_writes"):
        branch.state.params["rows"].insert(0, {"v": 0})
    assert branch.state.model_dump(mode="json") == branch_before
    assert state.model_dump(mode="json") == base_before
    assert store.get_bytes(retained) == evidence_before
    assert store.verify(retained).ok
    assert branch.journal.operations == []
    branch.state.params["rows"][0]["v"] = 5
    assert branch.state.params["rows"][0]["v"] == 5
    assert state.params["rows"][0]["v"] == 1


@pytest.mark.parametrize("ordinal", [0, 1, 2])
def test_retained_actual_v1_list_journals_are_misses_and_scalar_intents_stay_readable(
    tmp_path, ordinal
):
    from pathlib import Path
    from types import SimpleNamespace

    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.scientist.orchestration.engine.executor import _merge_cached_outcome_state
    from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache

    retained = json.loads(
        (Path(__file__).parent / "fixtures/list-journal-v1-cache.json").read_text()
    )
    assert retained["producer_sha"] == "1bd1fd11b683bbade5411a71b02706ea206b149d"
    row = retained["cases"][ordinal]
    payload = row["payload_bytes"].encode()
    manifest = row["manifest"]
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        payload,
        PutOptions(
            kind=manifest["kind"],
            media_type=manifest["media_type"],
            schema=SchemaInfo.model_validate(manifest["artifact_schema"]),
            producer=ProducerInfo.model_validate(manifest["producer"]),
        ),
    )
    assert ref == ArtifactRef.model_validate(row["cache_ref"])
    assert store.verify(ref).ok
    assert store.get_bytes(ref) == payload
    entry = json.loads(payload)
    assert entry["state_mutations_version"] == "1.0"
    reader = NodeResultCache(FileSystemCAS(store.root), entry["run_id"])
    admitted = reader.load_entry(ref)
    loaded = reader.get(entry["idempotency_key"])
    if ordinal < 2:
        assert not admitted
        assert loaded is None
        assert reader.size == 0
        assert store.get_bytes(ref) == payload
        return
    assert admitted
    assert loaded is not None
    node = SimpleNamespace(
        spec=_ListNode("no_shift").spec.model_copy(update={"state_writes": ["params"]})
    )
    current = ExperimentState(
        run_id=entry["run_id"],
        params={"x": 2, "y": 9, "stale": 1, "nullable": "current", "untouched": "new"},
        budgets={"neighbor_reserved_usd": Decimal("11")},
    )
    applied = _merge_cached_outcome_state(
        alias="producer", node=node, base_state=current, outcome=loaded
    )
    assert applied.params == {"x": 2, "y": 4, "nullable": None, "untouched": "new"}
    assert applied.budgets["neighbor_reserved_usd"] == Decimal("11")
    assert current.params["y"] == 9
    assert current.params["stale"] == 1
