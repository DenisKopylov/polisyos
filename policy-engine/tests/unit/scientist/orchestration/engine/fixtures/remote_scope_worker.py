"""Run the actual shared remote activity boundary in a fresh Python process."""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine import registry as registry_module
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.runner._activity_worker import run_node_in_worker_sync
from polisyos.scientist.orchestration.engine.runner.serialization import serialize_state_safe
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state,
    mutation_journal_for_state,
)


class ScopeNode:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.remote_scope_oracle@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Remote scope oracle",
                description="Actual wire/process/guarded-store consumer",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.x"],
            state_writes=["params.owned"],
        )

    def execute(self, ctx, state):
        raise AssertionError("native async entry required")

    async def execute_async(self, ctx, state):
        journal = mutation_journal_for_state(state)
        assert journal is not None and journal.enforce_write_scope
        if self.mode == "neighbor":
            state.params["neighbor"]["v"] = 99
        elif self.mode == "root":
            state.params = {"neighbor": {"v": 99}}
        elif self.mode == "nested":
            branch_state(state, write_paths=["params"]).state.params["neighbor"]["v"] = 99
        else:
            state.params["owned"]["v"] = 5
        ref = ctx.store.put_json(
            state.model_dump(mode="json"),
            PutOptions(kind="test.remote_scope_effect", media_type="application/json"),
        )
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


def main() -> None:
    mode, directory = sys.argv[1:]
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    node = ScopeNode(mode)

    # Discovery is the explicit fixture input. Execution, context reconstruction,
    # CAS publication and typed wire encoding use the canonical worker path.
    registry_module.discover_nodes = lambda registry: registry.register(node)
    state = ExperimentState(
        run_id="R_remote_scope",
        params={"x": 2, "owned": {"v": 1}, "neighbor": {"v": 2}},
        budgets={"neighbor_reserved_usd": Decimal("11")},
    )
    wire, _ = serialize_state_safe(state)
    (root / "input.bin").write_bytes(wire)
    try:
        result = run_node_in_worker_sync(
            {
                "node_id": str(node.spec.metadata.component_id),
                "alias": "remote",
                "state_bytes": wire,
                "context_meta": {
                    "run_id": state.run_id,
                    "store_config": {"backend": "filesystem", "root": str(root / "cas")},
                },
            }
        )
    except ValueError as exc:
        reply = {"pid": os.getpid(), "error": {"type": type(exc).__name__, "message": str(exc)}}
    else:
        (root / "outcome.bin").write_bytes(result)
        reply = {"pid": os.getpid(), "outcome_bytes": len(result)}
    assert (root / "input.bin").read_bytes() == wire
    (root / "reply.json").write_text(json.dumps(reply))


if __name__ == "__main__":
    main()
