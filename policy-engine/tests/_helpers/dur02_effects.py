"""Source-backed native DUR-02 effect producers, deliberately not pytest rewritten.

These synthetic local SQLite/CAS producers supply no institutional or external
billing authority. Their actual assertions and effects remain part of the loaded
source identity rather than assertion-rewritten test module bytecode.
The independent effect DB is not atomic with the Control SQL lease. The supported
profile is cooperative local execution; an unknown in-flight effect is not replayed.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.run import read_runtime_invocation_attempts
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSettlementOutcomeUnknownError,
    BudgetLedgerSpendReceipt,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import ErrorCategory
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeError,
    NodeInputRule,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore


class _PersistedEffectNode:
    """A real registered fixture producer with deliberately non-idempotent SQLite effects."""

    def __init__(self, database: Path, *, operation_id: str = "fixture-operation-1") -> None:
        self.database = database
        self.operation_id = operation_id
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_dur02_effect@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="DUR02 persisted fixture effect",
                description="Real SQLite/CAS effect",
                tags=["fixture"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.backend"],
            state_writes=["params.effect_ref"],
            produces=[],
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS effects "
                "(operation_id TEXT, backend TEXT, artifact_ref TEXT)"
            )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        backend = str(state.params["backend"])
        payload = {"operation_id": self.operation_id, "backend": backend}
        ref = ctx.store.put_json(
            payload,
            ArtifactWriteOptions(kind="fixture.dur02.effect", media_type="application/json"),
            return_selected_profile=True,
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO effects VALUES (?, ?, ?)",
                (payload["operation_id"], backend, ref.model_dump_json()),
            )
        changed = state.model_copy(deep=True)
        changed.params["effect_ref"] = ref.model_dump(mode="json")
        return NodeOutcome(status="ok", state=changed, artifacts=[ref])

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        await asyncio.sleep(0)
        return self.execute(ctx, state)


def _effects(path: Path) -> list[tuple[str, str, str]]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT operation_id, backend, artifact_ref FROM effects"
        ).fetchall()


class _LostCheckpointReply(BaseException):
    """Interrupt fixture execution without inventing a successful terminal result."""


class _CheckpointedEffectNode(_PersistedEffectNode):
    def __init__(self, database: Path, *, operation_id: str) -> None:
        super().__init__(database, operation_id=operation_id)
        reads = ["params.backend", "run_id", "budgets.run_spent_usd"]
        self.spec = InputAwareNodeSpec(
            metadata=self.spec.metadata,
            state_reads=reads,
            state_writes=[
                "params.effect_ref",
                "artifacts_index.effect_ref",
                "budgets.run_spent_usd",
            ],
            input_rules=tuple(
                NodeInputRule(
                    path=path,
                    availability="optional" if path == "budgets.run_spent_usd" else "required",
                )
                for path in reads
            ),
            produces=[],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        assert state.run_id == self.operation_id == ctx.run.run_manifest.run_id
        outcome = super().execute(ctx, state)
        receipt_ref, spent = _settle_handover_effect(ctx, outcome.artifacts[0], amount=Decimal(2))
        outcome.state.budgets["run_spent_usd"] = spent
        outcome.state.artifacts_index["effect_ref"] = outcome.artifacts[0]
        outcome.artifacts.append(receipt_ref)
        return outcome

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Use the supported local async profile, without a custom spawn admission."""
        await asyncio.sleep(0)
        return self.execute(ctx, state)


class _RemainingEffectNode:
    """Actual remaining local producer, with a deliberately non-idempotent effect."""

    def __init__(self, database: Path, *, expected_spend: Decimal = Decimal(7)) -> None:
        self.database = database
        self.expected_spend = expected_spend
        reads = [
            "artifacts_index.effect_ref",
            "params.lose_remaining_reply",
            "budgets.run_spent_usd",
        ]
        self.spec = InputAwareNodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_dur02_remaining@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="DUR02 remaining fixture producer",
                description="Native SQLite effect after a verified completed frontier",
                tags=["fixture"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=reads,
            input_rules=tuple(NodeInputRule(path=path) for path in reads),
            state_writes=["params.remaining_ref", "budgets.run_spent_usd"],
            produces=[],
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS remaining_effects (operation_id TEXT, ref TEXT)"
            )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        assert state.budgets["run_spent_usd"] == self.expected_spend
        source = state.artifacts_index["effect_ref"]
        source_payload = json.loads(ctx.store.get_bytes(source))
        assert source_payload == {
            "operation_id": ctx.run.run_manifest.run_id,
            "backend": "primary",
        }
        ref = ctx.store.put_json(
            {"operation_id": source_payload["operation_id"], "phase": "remaining-local"},
            ArtifactWriteOptions(kind="fixture.dur02.remaining", media_type="application/json"),
            return_selected_profile=True,
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO remaining_effects VALUES (?, ?)",
                (source_payload["operation_id"], ref.model_dump_json()),
            )
        receipt_ref, spent = _settle_handover_effect(ctx, ref, amount=Decimal(1))
        if state.params["lose_remaining_reply"]:
            raise _LostCheckpointReply("remaining effect happened without a terminal receipt")
        changed = state.model_copy(deep=True)
        changed.params["remaining_ref"] = ref.model_dump(mode="json")
        changed.budgets["run_spent_usd"] = spent
        return NodeOutcome(status="ok", state=changed, artifacts=[ref, receipt_ref])

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Produce the native local effect in the engine's genuine async route."""
        await asyncio.sleep(0)
        return self.execute(ctx, state)


def _settle_handover_effect(
    ctx: ExecutionContext,
    ref: ArtifactRef,
    *,
    amount: Decimal,
) -> tuple[ArtifactRef, Decimal]:
    """Consume only the narrow actual engine-issued accounting capability."""
    binding = ctx._engine_invocation
    assert binding is not None
    view = binding.settlement_view
    assert view is not None
    receipt_ref = view.settle_spend(
        amount,
        payload_ref=ref,
        provider="native-fixture-accounting",
    )
    spent = view.spent
    assert isinstance(spent, Decimal)
    return receipt_ref, spent


def _confirmed_effect_receipt(
    store: ArtifactStore, run_dir: Path, run_id: str
) -> BudgetLedgerSpendReceipt:
    """Fresh-read the real receipt selected by the original Core completion."""
    effects = [
        item
        for item in read_runtime_invocation_attempts(store, run_dir / "trace.jsonl", run_id=run_id)
        if item.basis.node_alias == "effect"
        and item.outcome is not None
        and item.outcome.status == "ok"
    ]
    assert len(effects) == 1
    attempt = effects[0]
    assert attempt.outcome is not None and attempt.outcome.status == "ok"
    ref = attempt.outcome.budget_receipt_ref
    assert ref is not None and ref.manifest_profile_sha256 is not None
    assert ref.kind == "scientist.budget_spend_receipt"
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == (
        "polisyos.scientist.orchestration.engine.budget_ledger.BudgetLedgerSpendReceipt"
    )
    assert manifest.artifact_schema.version == "1.0"
    assert any(
        item.role == "invocation_basis"
        and item.artifact_id == attempt.basis_ref.artifact_id
        and item.manifest_profile_sha256 == attempt.basis_ref.manifest_profile_sha256
        for item in manifest.inputs
    )
    receipt = BudgetLedgerSpendReceipt.model_validate(read_core_json_artifact(store, ref).value)
    assert attempt.basis.budget_start_revision is not None
    assert receipt.revision > attempt.basis.budget_start_revision
    return receipt


class _CostedRetryEffectNode:
    """A real costed local producer using actual Core physical-attempt ordinals."""

    def __init__(self, database: Path, *, mode: str) -> None:
        if mode not in {"retry", "lost_ack", "unknown"}:
            raise ValueError("invalid_costed_fixture_mode")
        self.database = database
        self.mode = mode
        reads = ["run_id", "budgets.run_spent_usd"]
        self.spec = InputAwareNodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_dur02_costed_retry@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="DUR02 costed retry fixture",
                description="Native per-attempt effect and engine-bound settlement",
                tags=["fixture"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=reads,
            input_rules=tuple(NodeInputRule(path=path) for path in reads),
            state_writes=[
                "budgets.run_spent_usd",
                "params.failed_body",
                "params.effect_ref",
                "artifacts_index.effect_ref",
            ],
            produces=[],
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS costed_effects "
                "(run_id TEXT, attempt_number INTEGER, payload_ref TEXT)"
            )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        binding = ctx._engine_invocation
        assert binding is not None and binding.settlement_view is not None
        attempts = [
            item
            for item in ctx.run.read_runtime_invocation_attempts()
            if item.basis_ref == binding.basis_ref
        ]
        assert len(attempts) == 1 and attempts[0].outcome is None
        number = attempts[0].basis.attempt_number
        amount = Decimal(2) if number == 1 else Decimal(1)
        payload_ref = ctx.store.put_json(
            {"operation_id": state.run_id, "backend": "primary"},
            ArtifactWriteOptions(kind="fixture.dur02.costed_effect", media_type="application/json"),
            return_selected_profile=True,
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO costed_effects VALUES (?, ?, ?)",
                (state.run_id, number, payload_ref.model_dump_json()),
            )
        view = binding.settlement_view
        try:
            receipt_ref = view.settle_spend(
                amount, payload_ref=payload_ref, provider="native-fixture-accounting"
            )
        except BudgetLedgerSettlementOutcomeUnknownError:
            if self.mode != "lost_ack":
                raise
            # Recover only the same actual settlement in this still-active
            # attempt. The physical producer above is not dispatched again.
            receipt_ref = view.settle_spend(
                amount, payload_ref=payload_ref, provider="native-fixture-accounting"
            )
        changed = state.model_copy(deep=True)
        changed.budgets["run_spent_usd"] += amount
        changed.params["effect_ref"] = payload_ref.model_dump(mode="json")
        changed.artifacts_index["effect_ref"] = payload_ref
        if self.mode == "retry" and number == 1:
            changed.params["failed_body"] = "must_not_publish"
            return NodeOutcome(
                status="fail",
                state=changed,
                artifacts=[payload_ref, receipt_ref],
                error=NodeError(
                    code="node.exception",
                    category=ErrorCategory.TRANSIENT,
                    message="Known first attempt failure with confirmed cost",
                ),
            )
        return NodeOutcome(status="ok", state=changed, artifacts=[payload_ref, receipt_ref])

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        await asyncio.sleep(0)
        return self.execute(ctx, state)


class _UnbudgetedEffectNode(_PersistedEffectNode):
    """Preserve the actual handoff in the existing typed artifact map."""

    def __init__(self, database: Path, *, operation_id: str, invalid_handoff: bool = False) -> None:
        super().__init__(database, operation_id=operation_id)
        self.invalid_handoff = invalid_handoff
        self.spec = self.spec.model_copy(
            update={"state_writes": ["params.effect_ref", "artifacts_index.effect_ref"]}
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        outcome = super().execute(ctx, state)
        actual = outcome.artifacts[0]
        outcome.state.artifacts_index["effect_ref"] = (
            ArtifactRef.model_validate(
                {**actual.model_dump(mode="python"), "artifact_id": "sha256:" + "0" * 64}
            )
            if self.invalid_handoff
            else actual
        )
        return outcome


class _UnbudgetedRemainingEffectNode:
    """An explicitly unbudgeted native residual producer with passive configuration."""

    def __init__(self, database: Path) -> None:
        self.database = database
        reads = ["artifacts_index.effect_ref", "run_id"]
        self.spec = InputAwareNodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_dur02_unbudgeted_remaining@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="DUR02 unbudgeted remaining fixture",
                description="Actual residual SQLite effect under no-ledger profile",
                tags=["fixture"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=reads,
            input_rules=tuple(NodeInputRule(path=path) for path in reads),
            state_writes=["params.remaining_ref"],
            produces=[],
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS remaining_effects (operation_id TEXT, ref TEXT)"
            )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        original = state.artifacts_index["effect_ref"]
        assert json.loads(ctx.store.get_bytes(original)) == {
            "operation_id": state.run_id,
            "backend": "primary",
        }
        ref = ctx.store.put_json(
            {"operation_id": state.run_id, "phase": "unbudgeted-remaining"},
            ArtifactWriteOptions(kind="fixture.dur02.remaining", media_type="application/json"),
            return_selected_profile=True,
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO remaining_effects VALUES (?, ?)",
                (state.run_id, ref.model_dump_json()),
            )
        changed = state.model_copy(deep=True)
        changed.params["remaining_ref"] = ref.model_dump(mode="json")
        return NodeOutcome(status="ok", state=changed, artifacts=[ref])

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        await asyncio.sleep(0)
        return self.execute(ctx, state)
