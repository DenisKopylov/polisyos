"""Tests for health_check() across runner backends."""

from __future__ import annotations

import asyncio

import pytest

from polisyos.scientist.engine.runner.local_runner import LocalWorkflowRunner
from polisyos.scientist.engine.runner.protocol import RunnerHealth


class TestLocalRunnerHealthCheck:
    """Local runner is always healthy."""

    def test_local_always_healthy(self) -> None:
        runner = LocalWorkflowRunner()
        health = asyncio.run(runner.health_check())
        assert isinstance(health, RunnerHealth)
        assert health.healthy is True
        assert health.backend == "local"

    def test_local_health_message(self) -> None:
        runner = LocalWorkflowRunner()
        health = asyncio.run(runner.health_check())
        assert health.message == "in-process"


class TestRunnerHealthModel:
    """RunnerHealth model validation."""

    def test_healthy_model(self) -> None:
        h = RunnerHealth(backend="test", healthy=True, latency_ms=1.5, worker_count=4)
        assert h.backend == "test"
        assert h.healthy is True
        assert h.latency_ms == 1.5
        assert h.worker_count == 4

    def test_unhealthy_model(self) -> None:
        h = RunnerHealth(backend="ray", healthy=False, message="connection refused")
        assert h.healthy is False
        assert "connection refused" in h.message

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            RunnerHealth(backend="x", healthy=True, extra_field=1)
