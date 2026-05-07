"""Tests for WorkflowRunnerConfig and build_workflow_runner factory."""

from __future__ import annotations

import sys

import pytest
from polisyos.scientist.orchestration.engine.runner.config import (
    WorkflowRunnerConfig,
    build_workflow_runner,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# WorkflowRunnerConfig defaults
# ---------------------------------------------------------------------------


class TestWorkflowRunnerConfigDefaults:
    def test_default_backend_is_local(self) -> None:
        cfg = WorkflowRunnerConfig()
        assert cfg.backend == "local"

    def test_default_max_parallelism(self) -> None:
        cfg = WorkflowRunnerConfig()
        assert cfg.max_parallelism == 4

    def test_default_merge_conflict_policy(self) -> None:
        cfg = WorkflowRunnerConfig()
        assert cfg.merge_conflict_policy == "error"

    def test_temporal_fields_default_to_none(self) -> None:
        cfg = WorkflowRunnerConfig()
        assert cfg.temporal_namespace is None
        assert cfg.temporal_task_queue is None
        assert cfg.temporal_server_url is None

    def test_ray_fields_default_to_none(self) -> None:
        cfg = WorkflowRunnerConfig()
        assert cfg.ray_address is None
        assert cfg.ray_namespace is None

    def test_extra_fields_are_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowRunnerConfig(surprise="boom")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# WorkflowRunnerConfig.from_env
# ---------------------------------------------------------------------------


class TestWorkflowRunnerConfigFromEnv:
    def test_reads_backend_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
        cfg = WorkflowRunnerConfig.from_env()
        assert cfg.backend == "local"

    def test_reads_temporal_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "temporal")
        monkeypatch.setenv("POLISYOS_TEMPORAL_NAMESPACE", "my-ns")
        monkeypatch.setenv("POLISYOS_TEMPORAL_TASK_QUEUE", "my-queue")
        monkeypatch.setenv("POLISYOS_TEMPORAL_SERVER_URL", "localhost:7233")
        cfg = WorkflowRunnerConfig.from_env()
        assert cfg.backend == "temporal"
        assert cfg.temporal_namespace == "my-ns"
        assert cfg.temporal_task_queue == "my-queue"
        assert cfg.temporal_server_url == "localhost:7233"

    def test_reads_ray_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "ray")
        monkeypatch.setenv("POLISYOS_RAY_ADDRESS", "ray://head:10001")
        monkeypatch.setenv("POLISYOS_RAY_NAMESPACE", "polisyos-test")
        cfg = WorkflowRunnerConfig.from_env()
        assert cfg.backend == "ray"
        assert cfg.ray_address == "ray://head:10001"
        assert cfg.ray_namespace == "polisyos-test"

    def test_reads_max_parallelism(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLISYOS_RUNNER_MAX_PARALLELISM", "16")
        cfg = WorkflowRunnerConfig.from_env()
        assert cfg.max_parallelism == 16

    def test_defaults_when_env_vars_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POLISYOS_RUNNER_BACKEND", raising=False)
        monkeypatch.delenv("POLISYOS_RUNNER_MAX_PARALLELISM", raising=False)
        cfg = WorkflowRunnerConfig.from_env()
        assert cfg.backend == "local"
        assert cfg.max_parallelism == 4

    def test_reads_merge_conflict_policy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLISYOS_RUNNER_MERGE_CONFLICT_POLICY", "last_write_wins")
        cfg = WorkflowRunnerConfig.from_env()
        assert cfg.merge_conflict_policy == "last_write_wins"


# ---------------------------------------------------------------------------
# build_workflow_runner factory
# ---------------------------------------------------------------------------


class TestBuildWorkflowRunner:
    def test_local_backend_returns_local_runner(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_runner import LocalWorkflowRunner

        cfg = WorkflowRunnerConfig(backend="local", max_parallelism=2)
        runner = build_workflow_runner(cfg)
        assert isinstance(runner, LocalWorkflowRunner)

    def test_temporal_backend_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Temporal backend raises ImportError when temporalio is not installed."""
        monkeypatch.setitem(sys.modules, "temporalio", None)
        monkeypatch.setitem(sys.modules, "temporalio.client", None)
        # Force re-import of temporal_runner by removing cached module
        monkeypatch.delitem(
            sys.modules,
            "polisyos.scientist.orchestration.engine.runner.temporal_runner",
            raising=False,
        )
        cfg = WorkflowRunnerConfig(
            backend="temporal",
            temporal_server_url="localhost:7233",
        )
        with pytest.raises(ImportError):
            build_workflow_runner(cfg)

    def test_ray_backend_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ray backend raises ImportError when ray is not installed."""
        monkeypatch.setitem(sys.modules, "ray", None)
        # Force re-import of ray_runner by removing cached module
        monkeypatch.delitem(
            sys.modules,
            "polisyos.scientist.orchestration.engine.runner.ray_runner",
            raising=False,
        )
        cfg = WorkflowRunnerConfig(backend="ray")
        with pytest.raises(ImportError):
            build_workflow_runner(cfg)

    def test_unknown_backend_raises_value_error(self) -> None:
        # Use model_construct to bypass Literal validation for this test
        cfg = WorkflowRunnerConfig.model_construct(backend="unkown_backend")
        with pytest.raises(ValueError, match="Unknown runner backend"):
            build_workflow_runner(cfg)
