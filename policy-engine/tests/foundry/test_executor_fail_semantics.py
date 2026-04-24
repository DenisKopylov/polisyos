"""Tests for fail-closed execution with typed FailureCard."""

from __future__ import annotations

import time

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecPlanRef,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    ProgramOp,
)
from polisyos.foundry._executor_graph import (
    _MAX_FAILURE_CARDS,
    _append_failure_card,
    _classify_failure,
    _hash_traceback,
    execute_program_graph,
)
from polisyos.foundry._executor_models import (
    ExecutionStrictness,
    FailureCard,
    FailureKind,
    FailureSeverity,
    get_state_path,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.methods.exceptions import (
    BackendAdaptationError,
    ContractViolationError,
    MethodExecutionAbortError,
    SelectorEvaluationError,
    ShapeMismatchError,
    StatePathTraversalError,
)
from polisyos.foundry.methods.lifecycle import (
    LifecycleLog,
    LifecycleManager,
    LifecycleTransitionError,
    MethodLifecycle,
)
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


def _dummy_ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("f" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _put_json(store: FileSystemCAS, payload: object, *, kind: str) -> ArtifactRef:
    return store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))


def _put_graph_and_plan(
    store: FileSystemCAS,
    *,
    nodes: list[ProgramNode],
    order: list[str] | None = None,
) -> tuple[ProgramGraphRef, ExecPlanRef]:
    lowered_ir_ref = _put_json(
        store,
        LoweredIR(ir_ref=_dummy_ir_ref(), mechanisms=[], constraints=[]),
        kind="foundry.lowered_ir",
    )
    graph_ref = _put_json(
        store,
        ProgramGraph(
            ir_ref=_dummy_ir_ref(),
            lowered_ir_ref=LoweredIRRef(artifact_id=lowered_ir_ref.artifact_id),
            nodes=nodes,
            edges=[],
            entrypoints=[node.node_id for node in nodes],
        ),
        kind="foundry.program_graph",
    )
    exec_plan_ref = _put_json(
        store,
        ExecPlan(
            program_ref=ProgramGraphRef(artifact_id=graph_ref.artifact_id),
            order=order or [node.node_id for node in nodes],
        ),
        kind="foundry.exec_plan",
    )
    return (
        ProgramGraphRef(artifact_id=graph_ref.artifact_id),
        ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
    )


# ---------------------------------------------------------------------------
# _classify_failure unit tests
# ---------------------------------------------------------------------------


class TestClassifyFailure:
    def test_type_error_is_fatal(self):
        assert _classify_failure(TypeError("bad")) == FailureSeverity.FATAL

    def test_value_error_is_fatal(self):
        assert _classify_failure(ValueError("bad")) == FailureSeverity.FATAL

    def test_shape_mismatch_is_fatal(self):
        exc = ShapeMismatchError("src", "tgt", (2,), (3,))
        assert _classify_failure(exc) == FailureSeverity.FATAL

    def test_contract_violation_is_fatal(self):
        exc = ContractViolationError("ns.method@1.0", "precondition", "x > 0")
        assert _classify_failure(exc) == FailureSeverity.FATAL

    def test_selector_error_is_fatal(self):
        exc = SelectorEvaluationError("income", "unknown selector field")
        assert _classify_failure(exc) == FailureSeverity.FATAL

    def test_backend_adaptation_error_is_fatal(self):
        exc = BackendAdaptationError("jax", "numpy", "device-native leak")
        assert _classify_failure(exc) == FailureSeverity.FATAL

    def test_module_not_found_is_recoverable(self):
        assert _classify_failure(ModuleNotFoundError("foo")) == FailureSeverity.RECOVERABLE

    def test_import_error_is_recoverable(self):
        assert _classify_failure(ImportError("foo")) == FailureSeverity.RECOVERABLE

    def test_timeout_is_recoverable(self):
        assert _classify_failure(TimeoutError("slow")) == FailureSeverity.RECOVERABLE

    def test_floating_point_error_is_degraded(self):
        assert _classify_failure(FloatingPointError("nan")) == FailureSeverity.DEGRADED

    def test_unknown_exception_defaults_to_fatal(self):
        assert _classify_failure(RuntimeError("unknown")) == FailureSeverity.FATAL


# ---------------------------------------------------------------------------
# _hash_traceback
# ---------------------------------------------------------------------------


class TestHashTraceback:
    def test_produces_hex_string(self):
        try:
            raise ValueError("test")
        except ValueError as exc:
            h = _hash_traceback(exc)
        assert isinstance(h, str)
        assert len(h) == 16
        int(h, 16)  # must be valid hex


# ---------------------------------------------------------------------------
# FailureCard model tests
# ---------------------------------------------------------------------------


class TestFailureCard:
    def test_failure_card_fields_populated(self):
        card = FailureCard(
            node_id="n1",
            method_fqn="ns.method@1.0",
            severity=FailureSeverity.FATAL,
            failure_kind=FailureKind.CONTRACT,
            error_type="TypeError",
            error_message="bad type",
            traceback_hash="abc123",
            timestamp=time.time(),
            retry_eligible=False,
            slot_context=("agents.income",),
            details={"slot_context": ["agents.income"]},
        )
        assert card.node_id == "n1"
        assert card.method_fqn == "ns.method@1.0"
        assert card.severity == FailureSeverity.FATAL
        assert card.failure_kind == FailureKind.CONTRACT
        assert card.error_type == "TypeError"
        assert card.error_message == "bad type"
        assert card.traceback_hash == "abc123"
        assert card.timestamp > 0
        assert card.retry_eligible is False
        assert card.suggested_fallback is None
        assert card.slot_context == ("agents.income",)

    def test_failure_card_immutable(self):
        card = FailureCard(
            node_id="n1",
            method_fqn="ns.method@1.0",
            severity=FailureSeverity.FATAL,
            failure_kind=FailureKind.INTERNAL,
            error_type="TypeError",
            error_message="bad",
            traceback_hash="abc",
            timestamp=1.0,
            retry_eligible=False,
        )
        with pytest.raises(Exception):
            card.node_id = "n2"

    def test_failure_card_forbids_extra_fields(self):
        with pytest.raises(Exception):
            FailureCard(
                node_id="n1",
                method_fqn="ns.method@1.0",
                severity=FailureSeverity.FATAL,
                failure_kind=FailureKind.INTERNAL,
                error_type="TypeError",
                error_message="bad",
                traceback_hash="abc",
                timestamp=1.0,
                retry_eligible=False,
                unknown_field="bad",
            )

    def test_failure_card_collection_is_bounded(self):
        card = FailureCard(
            node_id="n1",
            method_fqn="ns.method@1.0",
            severity=FailureSeverity.DEGRADED,
            failure_kind=FailureKind.INTERNAL,
            error_type="RuntimeError",
            error_message="bad",
            traceback_hash="abc",
            timestamp=1.0,
            retry_eligible=False,
        )
        cards: list[FailureCard] = []
        dropped = sum(_append_failure_card(cards, card) for _ in range(_MAX_FAILURE_CARDS + 3))
        assert len(cards) == _MAX_FAILURE_CARDS
        assert dropped == 3


# ---------------------------------------------------------------------------
# MethodExecutionAbortError
# ---------------------------------------------------------------------------


class TestMethodExecutionAbortError:
    def test_carries_card(self):
        card = FailureCard(
            node_id="n1",
            method_fqn="ns.method@1.0",
            severity=FailureSeverity.FATAL,
            failure_kind=FailureKind.INTERNAL,
            error_type="TypeError",
            error_message="bad",
            traceback_hash="abc",
            timestamp=1.0,
            retry_eligible=False,
        )
        err = MethodExecutionAbortError(card)
        assert err.card is card
        assert "ns.method@1.0" in str(err)
        assert "fatal" in str(err)


# ---------------------------------------------------------------------------
# ExecutionStrictness enum
# ---------------------------------------------------------------------------


class TestExecutionStrictness:
    def test_values(self):
        assert ExecutionStrictness.FAIL_CLOSED.value == "fail_closed"
        assert ExecutionStrictness.DEGRADED.value == "degraded"
        assert ExecutionStrictness.RESEARCH.value == "research"


class TestNodeDispatch:
    def test_unsupported_op_returns_failure_card_in_research_mode(self, tmp_path):
        store = FileSystemCAS(tmp_path)
        base_state = GlobalState.empty(n_agents=1, n_firms=1)
        program_ref, exec_plan_ref = _put_graph_and_plan(
            store,
            nodes=[
                ProgramNode(
                    node_id="bad_apply_method",
                    node_kind="op",
                    op=ProgramOp(op_kind="apply_method"),
                )
            ],
        )

        artifacts = execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            strictness=ExecutionStrictness.RESEARCH,
        )

        assert artifacts.is_degraded is True
        assert len(artifacts.failure_cards) == 1
        card = artifacts.failure_cards[0]
        assert card.node_id == "bad_apply_method"
        assert card.failure_kind == FailureKind.VALIDATION
        assert card.op_kind == "apply_method"

    def test_unsupported_op_aborts_in_fail_closed_mode(self, tmp_path):
        store = FileSystemCAS(tmp_path)
        base_state = GlobalState.empty(n_agents=1, n_firms=1)
        program_ref, exec_plan_ref = _put_graph_and_plan(
            store,
            nodes=[
                ProgramNode(
                    node_id="bad_apply_method",
                    node_kind="op",
                    op=ProgramOp(op_kind="apply_method"),
                )
            ],
        )

        with pytest.raises(MethodExecutionAbortError) as exc_info:
            execute_program_graph(
                store,
                program_ref=program_ref,
                exec_plan_ref=exec_plan_ref,
                base_state=base_state,
                mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
                slot_registry=DEFAULT_SLOT_REGISTRY,
                merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
                strictness=ExecutionStrictness.FAIL_CLOSED,
            )

        assert exc_info.value.card.node_id == "bad_apply_method"

    def test_unknown_exec_plan_node_returns_structured_card_in_research_mode(self, tmp_path):
        store = FileSystemCAS(tmp_path)
        base_state = GlobalState.empty(n_agents=1, n_firms=1)
        program_ref, exec_plan_ref = _put_graph_and_plan(
            store,
            nodes=[],
            order=["ghost_node"],
        )

        artifacts = execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            strictness=ExecutionStrictness.RESEARCH,
        )

        assert len(artifacts.failure_cards) == 1
        assert artifacts.failure_cards[0].node_id == "ghost_node"
        assert artifacts.failure_cards[0].failure_kind == FailureKind.VALIDATION


class TestPathTraversal:
    def test_invalid_state_path_raises_context_rich_error(self):
        state = GlobalState.empty(n_agents=1, n_firms=1)

        with pytest.raises(StatePathTraversalError) as exc_info:
            get_state_path(state, "agents.missing_field")

        assert exc_info.value.path == "agents.missing_field"
        assert exc_info.value.segment == "missing_field"


class TestLifecycleHardening:
    def test_invalid_transition_raises_even_in_non_strict_mode(self):
        log = LifecycleLog()
        LifecycleManager.transition(
            log, "tests.method@1.0.0", MethodLifecycle.DEFINED, strict=False
        )
        LifecycleManager.transition(log, "tests.method@1.0.0", MethodLifecycle.REGISTERED)

        with pytest.raises(LifecycleTransitionError):
            LifecycleManager.transition(
                log,
                "tests.method@1.0.0",
                MethodLifecycle.DEFINED,
                strict=False,
            )

        history = log.history()
        assert len(history) == 3
        assert history[-1].to_state == MethodLifecycle.REGISTERED
        assert "invalid" in history[-1].actor


def test_execute_program_graph_fail_closes_on_unclassified_method_dispatch_error(
    tmp_path,
    monkeypatch,
):
    class _DummyRegistry:
        @staticmethod
        def get(_method_fqn: str, version: str | None = None):
            return type("MethodClass", (), {"signature": object()})

    class _FailingDispatcher:
        @staticmethod
        def dispatch(**_kwargs):
            raise KeyError("unexpected method dispatch lookup")

    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=1, n_firms=1)
    program_ref, exec_plan_ref = _put_graph_and_plan(
        store,
        nodes=[
            ProgramNode(
                node_id="method_node",
                node_kind="method",
                method_fqn="tests.method@1.0.0",
            )
        ],
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.registry.MethodRegistry.get_instance",
        lambda: _DummyRegistry(),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.backends.dispatch.MethodDispatcher.get_instance",
        lambda: _FailingDispatcher(),
    )

    with pytest.raises(KeyError, match="unexpected method dispatch lookup"):
        execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            strictness=ExecutionStrictness.FAIL_CLOSED,
        )
