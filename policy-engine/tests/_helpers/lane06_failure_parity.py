"""Source-backed, locally costed RUN-03 producer for return/raise parity.

The SQLite record counts actual producer entries. In the uncosted profile it
is only that local observation, not an external action with an unknown result.
The costed profile additionally settles an actual local charge; neither is
external billing authority or an atomic transaction with the budget ledger.
Keeping the producer outside pytest rewriting lets Core capture its real code.
"""

from __future__ import annotations

import asyncio
import sqlite3
from decimal import Decimal
from pathlib import Path

from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import ErrorCategory, NodeExecutionError
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeError,
    NodeInputRule,
    NodeOutcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

PARITY_CODE = "fixture.declared_failure"
PARITY_NODE_ID = ComponentId.parse("scientist.node_lane06_failure_parity@1.0.0")


class CostedFailureNode:
    """A registered synchronous producer with an actual issued settlement view."""

    def __init__(self, database: Path, *, costed: bool = True) -> None:
        self.database = database
        self.costed = costed
        reads = ["params.delivery", "params.category", "run_id"]
        if costed:
            reads.append("budgets.run_spent_usd")
        self.spec = InputAwareNodeSpec(
            metadata=ComponentMetadata(
                component_id=PARITY_NODE_ID,
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="RUN03 native declared failure",
                description="Local costed return/raise policy witness",
                tags=["fixture"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=reads,
            input_rules=tuple(NodeInputRule(path=path) for path in reads),
            state_writes=["params.failed_body", "budgets.run_spent_usd"],
            produces=[],
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE effects "
                "(attempt_id TEXT PRIMARY KEY, basis_ref TEXT, payload_ref TEXT, receipt_ref TEXT)"
            )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Observe one effect, then report the explicitly typed fixture cause."""
        binding = ctx._engine_invocation
        assert binding is not None
        view = binding.settlement_view
        payload_ref = ctx.store.put_json(
            {"run_id": state.run_id, "attempt_id": binding.attempt_id, "cause": PARITY_CODE},
            ArtifactWriteOptions(kind="fixture.run03.effect", media_type="application/json"),
            return_selected_profile=True,
        )
        receipt_ref = None
        if self.costed:
            assert view is not None
            receipt_ref = view.settle_spend(
                Decimal("2"), payload_ref=payload_ref, provider="run03-local-fixture"
            )
        else:
            assert view is None
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO effects VALUES (?, ?, ?, ?)",
                (
                    binding.attempt_id,
                    binding.basis_ref.model_dump_json(),
                    payload_ref.model_dump_json(),
                    receipt_ref.model_dump_json() if receipt_ref is not None else None,
                ),
            )
        if self.costed:
            assert view is not None
            state.budgets["run_spent_usd"] = view.spent
        state.params["failed_body"] = "must_not_be_committed"
        category = ErrorCategory(state.params["category"])
        # The conflicting diagnostic is deliberately not retry authority.
        diagnostic = {"category": "transient"}
        if state.params["delivery"] == "raise":
            raise NodeExecutionError(
                "Declared fixture cause",
                code=PARITY_CODE,
                category=category,
                details=diagnostic,
            )
        return NodeOutcome(
            status="fail",
            state=state,
            artifacts=[payload_ref, receipt_ref] if receipt_ref is not None else [payload_ref],
            error=NodeError(
                code=PARITY_CODE,
                category=category,
                message="Declared fixture cause",
                details=diagnostic,
            ),
        )


class AsyncCostedFailureNode(CostedFailureNode):
    """Use the same actual producer through the genuine-async dispatch route."""

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Yield once, then execute the identical declared cause and actual charge."""
        await asyncio.sleep(0)
        return self.execute(ctx, state)
