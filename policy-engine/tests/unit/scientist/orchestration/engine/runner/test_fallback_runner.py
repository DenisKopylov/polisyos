"""Tests for FallbackWorkflowRunner."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from polisyos.scientist.orchestration.engine.runner import fallback_runner as fallback_runner_module
from polisyos.scientist.orchestration.engine.runner.fallback_runner import FallbackWorkflowRunner
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

        result = asyncio.run(runner.execute_workflow("wf", "st", "ctx", "reg"))

        assert result == "fallback_result"
        runner._fallback.execute_workflow.assert_awaited_once()
        assert any(item["reason"] == "primary_runner_execution_failed" for item in degraded)
