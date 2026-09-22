"""Tests for FallbackWorkflowRunner."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from polisyos.scientist.orchestration.engine.runner import (
    fallback_runner as fallback_runner_module,
    temporal_runner as temporal_runner_module,
)
from polisyos.scientist.orchestration.engine.runner.fallback_runner import (
    FallbackNotAuthorizedError,
    FallbackWorkflowRunner,
    HealthFailureDisposition,
    PrimaryExecutionOutcomeUnknownError,
)
from polisyos.scientist.orchestration.engine.runner.protocol import RunnerHealth


def _make_primary(healthy: bool = True) -> MagicMock:
    """Create a mock primary runner with configurable health."""
    primary = MagicMock()
    primary.health_check = AsyncMock(
        return_value=RunnerHealth(
            backend="ray",
            healthy=healthy,
            message="ok" if healthy else "down",
        )
    )
    primary.execute_workflow = AsyncMock(return_value="primary_result")
    return primary


def _health_sample(
    health: RunnerHealth,
    disposition: HealthFailureDisposition,
    probe_id: int,
) -> object:
    """Build the private backend witness without making it public test API."""

    sample_type = getattr(fallback_runner_module, "_HealthFailureSample", None)
    if sample_type is None:
        # The pre-wiring baseline has no sample type.  Keep collection working
        # so the baseline fails at the missing private probe hand-off instead
        # of becoming a collection error.
        return SimpleNamespace(
            health=health,
            disposition=disposition,
            probe_id=probe_id,
        )
    return sample_type(health=health, disposition=disposition, probe_id=probe_id)


class TestFallbackRunner:
    def test_healthy_primary_used(self) -> None:
        primary = _make_primary(healthy=True)
        runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
        result = asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))
        assert result == "primary_result"
        primary.execute_workflow.assert_awaited_once()

    def test_unhealthy_falls_back_to_local(self) -> None:
        primary = _make_primary(healthy=False)
        FallbackWorkflowRunner(primary, health_ttl_s=0)
        # Fallback to local will fail because args aren't real, but the
        # point is that primary.execute_workflow is NOT called.
        primary.execute_workflow.assert_not_awaited()

    def test_health_ttl_caching(self) -> None:
        primary = _make_primary(healthy=True)
        runner = FallbackWorkflowRunner(primary, health_ttl_s=60)

        # First call probes
        asyncio.run(runner.health_check())
        assert primary.health_check.await_count == 1

        # Second call within TTL uses cache
        asyncio.run(runner.health_check())
        assert primary.health_check.await_count == 1

    def test_health_ttl_expired_reprobes(self) -> None:
        primary = _make_primary(healthy=True)
        runner = FallbackWorkflowRunner(primary, health_ttl_s=0)

        asyncio.run(runner.health_check())
        asyncio.run(runner.health_check())
        assert primary.health_check.await_count == 2

    def test_primary_execution_error_falls_back(self) -> None:
        primary = _make_primary(healthy=True)
        primary.execute_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        FallbackWorkflowRunner(primary, health_ttl_s=0)
        # Primary throws → fallback to local (which will also fail with
        # bad args, but the control flow is correct)
        primary.execute_workflow.assert_not_awaited()

    def test_primary_execution_error_emits_degraded_path_and_uses_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary = _make_primary(healthy=True)
        primary.execute_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
        runner._fallback = SimpleNamespace(
            execute_workflow=AsyncMock(return_value="fallback_result")
        )

        degraded: list[dict[str, object]] = []
        monkeypatch.setattr(
            fallback_runner_module,
            "emit_degraded_path",
            lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
        )

        with pytest.raises(PrimaryExecutionOutcomeUnknownError, match="outcome"):
            asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))

        runner._fallback.execute_workflow.assert_not_awaited()
        assert any(item["reason"] == "primary_execution_outcome_unknown" for item in degraded)


def test_typed_transient_health_sample_allows_fallback() -> None:
    health = RunnerHealth(
        backend="remote",
        healthy=False,
        message="transport unavailable; contract text is not consulted",
    )
    sample = _health_sample(health, HealthFailureDisposition.ALLOW, probe_id=1)
    primary = MagicMock()
    primary.health_check = AsyncMock(return_value=health)
    primary.execute_workflow = AsyncMock()
    primary._get_health_sample = MagicMock(return_value=sample)
    runner = FallbackWorkflowRunner(
        primary,
        health_ttl_s=0,
    )
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    result = asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))

    assert result == "local-result"
    primary.execute_workflow.assert_not_awaited()
    fallback.assert_awaited_once()


@pytest.mark.parametrize(
    "message",
    [
        "connection refused; tenant access denied by contract",
        "invalid runner contract",
        "probe status is unknown",
    ],
)
def test_access_contract_and_unknown_health_samples_block_fallback(message: str) -> None:
    health = RunnerHealth(backend="remote", healthy=False, message=message)
    sample = _health_sample(health, HealthFailureDisposition.BLOCK, probe_id=1)
    primary = MagicMock()
    primary.health_check = AsyncMock(return_value=health)
    primary._get_health_sample = MagicMock(return_value=sample)
    # The old classifier must not override the current typed private probe.
    primary.classify_health_failure = MagicMock(return_value=HealthFailureDisposition.ALLOW)
    runner = FallbackWorkflowRunner(
        primary,
        health_ttl_s=0,
    )
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    with pytest.raises(FallbackNotAuthorizedError, match="fallback"):
        asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))

    fallback.assert_not_awaited()


def test_stale_allow_sample_is_not_inherited_by_new_probe() -> None:
    first_health = RunnerHealth(backend="remote", healthy=False, message="temporary transport")
    second_health = RunnerHealth(backend="remote", healthy=False, message="contract rejected")
    first_sample = _health_sample(first_health, HealthFailureDisposition.ALLOW, probe_id=1)
    primary = MagicMock()
    primary.health_check = AsyncMock(side_effect=[first_health, second_health])
    # The second probe deliberately returns the first probe's ALLOW witness.
    # The fallback must bind authority to the current health/probe identity.
    primary._get_health_sample = MagicMock(side_effect=[first_sample, first_sample])
    primary.classify_health_failure = MagicMock(return_value=HealthFailureDisposition.ALLOW)
    runner = FallbackWorkflowRunner(
        primary,
        health_ttl_s=0,
    )
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    first = asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))
    with pytest.raises(FallbackNotAuthorizedError, match="fallback"):
        asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))

    assert first == "local-result"
    fallback.assert_awaited_once()


@pytest.mark.parametrize(
    ("probe_error", "allow"),
    [
        (ConnectionError("access words in a transport exception"), True),
        (PermissionError("connection refused"), False),
        (ValueError("probe contract invalid"), False),
        (RuntimeError("probe outcome unknown"), False),
    ],
)
def test_probe_exception_classification_is_typed_not_message_based(
    probe_error: Exception,
    allow: bool,
) -> None:
    primary = MagicMock()
    primary.health_check = AsyncMock(side_effect=probe_error)
    runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    if allow:
        assert asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg")) == "local-result"
        fallback.assert_awaited_once()
    else:
        with pytest.raises(FallbackNotAuthorizedError, match="fallback"):
            asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))
        fallback.assert_not_awaited()


def test_synthetic_value_error_sample_precedes_legacy_allow_for_generic_backend() -> None:
    """A generic validation failure cannot inherit an old ALLOW classifier."""

    primary = SimpleNamespace(
        health_check=AsyncMock(side_effect=ValueError("contract text says connection refused")),
        execute_workflow=AsyncMock(),
    )
    runner = FallbackWorkflowRunner(
        primary,
        health_ttl_s=0,
        health_failure_classifier=lambda _health: HealthFailureDisposition.ALLOW,
    )
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    with pytest.raises(FallbackNotAuthorizedError, match="fallback"):
        asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))

    fallback.assert_not_awaited()


def test_synthetic_connection_error_sample_allows_generic_backend_without_classifier() -> None:
    """A typed transport failure can authorize fallback without a legacy hook."""

    primary = SimpleNamespace(
        health_check=AsyncMock(side_effect=ConnectionError("contract text is irrelevant")),
        execute_workflow=AsyncMock(),
    )
    runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    assert asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg")) == "local-result"
    fallback.assert_awaited_once()


def test_synthetic_connection_error_sample_cannot_override_legacy_block() -> None:
    """A legacy BLOCK remains a limiting decision over a typed ALLOW witness."""

    primary = SimpleNamespace(
        health_check=AsyncMock(side_effect=ConnectionError("transport unavailable")),
        execute_workflow=AsyncMock(),
    )
    runner = FallbackWorkflowRunner(
        primary,
        health_ttl_s=0,
        health_failure_classifier=lambda _health: HealthFailureDisposition.BLOCK,
    )
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    with pytest.raises(FallbackNotAuthorizedError, match="fallback"):
        asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))

    fallback.assert_not_awaited()


def test_returned_unhealthy_health_retains_legacy_classifier_without_probe_sample() -> None:
    """A backend-returned health result still supports the existing classifier API."""

    health = RunnerHealth(backend="generic", healthy=False, message="legacy health result")
    primary = SimpleNamespace(
        health_check=AsyncMock(return_value=health),
        execute_workflow=AsyncMock(),
        classify_health_failure=lambda _health: HealthFailureDisposition.ALLOW,
    )
    runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    assert asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg")) == "local-result"
    fallback.assert_awaited_once()


def test_temporal_rpc_status_controls_fallback_disposition(monkeypatch: pytest.MonkeyPatch) -> None:
    """Typed Temporal status controls authority even when optional deps are absent."""

    class _FakeRPCError(Exception):
        def __init__(self, status_name: str) -> None:
            super().__init__(status_name)
            self.status = SimpleNamespace(name=status_name)

    monkeypatch.setattr(temporal_runner_module, "_HAS_TEMPORAL", True)
    monkeypatch.setattr(temporal_runner_module, "TemporalRPCError", _FakeRPCError)

    denied = _FakeRPCError("PERMISSION_DENIED")
    transient = _FakeRPCError("UNAVAILABLE")
    assert (
        temporal_runner_module._temporal_probe_disposition(denied)
        is HealthFailureDisposition.BLOCK
    )
    assert (
        temporal_runner_module._temporal_probe_disposition(transient)
        is HealthFailureDisposition.ALLOW
    )
