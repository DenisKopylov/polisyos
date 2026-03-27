"""Tests for fail-closed execution with typed FailureCard."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from polisyos.foundry._executor_models import (
    ExecutionStrictness,
    FailureCard,
    FailureSeverity,
)
from polisyos.foundry._executor_graph import _classify_failure, _hash_traceback
from polisyos.foundry.methods.exceptions import (
    ContractViolationError,
    MethodExecutionAbortError,
    ShapeMismatchError,
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
            error_type="TypeError",
            error_message="bad type",
            traceback_hash="abc123",
            timestamp=time.time(),
            retry_eligible=False,
        )
        assert card.node_id == "n1"
        assert card.method_fqn == "ns.method@1.0"
        assert card.severity == FailureSeverity.FATAL
        assert card.error_type == "TypeError"
        assert card.error_message == "bad type"
        assert card.traceback_hash == "abc123"
        assert card.timestamp > 0
        assert card.retry_eligible is False
        assert card.suggested_fallback is None

    def test_failure_card_immutable(self):
        card = FailureCard(
            node_id="n1",
            method_fqn="ns.method@1.0",
            severity=FailureSeverity.FATAL,
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
                error_type="TypeError",
                error_message="bad",
                traceback_hash="abc",
                timestamp=1.0,
                retry_eligible=False,
                unknown_field="bad",
            )


# ---------------------------------------------------------------------------
# MethodExecutionAbortError
# ---------------------------------------------------------------------------


class TestMethodExecutionAbortError:
    def test_carries_card(self):
        card = FailureCard(
            node_id="n1",
            method_fqn="ns.method@1.0",
            severity=FailureSeverity.FATAL,
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
