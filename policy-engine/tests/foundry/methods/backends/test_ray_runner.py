"""
Tests for RayMethodRunner and RayChainExecutor (T4.3).

All Ray-specific tests are skipped when Ray is not installed.
The import-level tests always run and verify graceful degradation.
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Availability helpers
# ---------------------------------------------------------------------------

def _ray_installed() -> bool:
    try:
        import ray  # noqa: F401
        return True
    except ImportError:
        return False


_ray_mark = pytest.mark.skipif(not _ray_installed(), reason="ray not installed")


# ---------------------------------------------------------------------------
# Import-level tests (always run)
# ---------------------------------------------------------------------------

class TestRayImports:
    def test_runner_importable(self):
        from polisyos.foundry.methods.backends.ray_runner import (
            RayMethodRunner,
            RayNotAvailableError,
            RayTaskResult,
        )
        assert callable(RayMethodRunner)
        assert issubclass(RayNotAvailableError, RuntimeError)

    def test_chain_executor_importable(self):
        from polisyos.foundry.methods.backends.ray_chain_executor import (
            RayChainExecutor,
            RayChainExecutionError,
        )
        assert callable(RayChainExecutor)
        assert issubclass(RayChainExecutionError, RuntimeError)

    def test_runner_not_available_without_ray(self):
        """When Ray is not installed, is_available() returns False gracefully."""
        from polisyos.foundry.methods.backends.ray_runner import RayMethodRunner
        runner = RayMethodRunner()
        # If ray IS installed but not initialised, is_available() still returns False.
        # If ray is NOT installed, also returns False.
        # Either way, it must not raise.
        result = runner.is_available()
        assert isinstance(result, bool)

    def test_runner_run_raises_when_not_available(self):
        """run() must raise RayNotAvailableError (not ImportError) when Ray is absent."""
        from polisyos.foundry.methods.backends.ray_runner import (
            RayMethodRunner,
            RayNotAvailableError,
            _ray_available,
        )
        if _ray_available():
            pytest.skip("Ray is installed — this test only applies when Ray is absent")

        runner = RayMethodRunner()

        class DummyMethod:
            class signature:
                fqn = "test.dummy@1.0.0"

            @staticmethod
            def pure_step(state, params):
                return {}

        with pytest.raises(RayNotAvailableError):
            runner.run(DummyMethod, state={}, params={})

    def test_chain_executor_not_available_raises(self):
        from polisyos.foundry.methods.backends.ray_chain_executor import (
            RayChainExecutor,
            RayChainExecutionError,
        )
        from polisyos.foundry.methods.backends.ray_runner import (
            RayNotAvailableError,
            _ray_available,
        )
        if _ray_available():
            pytest.skip("Ray is installed — this test only applies when Ray is absent")

        executor = RayChainExecutor()
        assert not executor.is_available()

        with pytest.raises(RayNotAvailableError):
            executor.execute(None, initial_state={})

    def test_repr_runner(self):
        from polisyos.foundry.methods.backends.ray_runner import RayMethodRunner
        r = repr(RayMethodRunner(num_cpus=2.0, memory=1024, timeout=30.0))
        assert "RayMethodRunner" in r
        assert "num_cpus" in r

    def test_repr_chain_executor(self):
        from polisyos.foundry.methods.backends.ray_chain_executor import RayChainExecutor
        r = repr(RayChainExecutor(num_cpus_per_node=4.0))
        assert "RayChainExecutor" in r

    def test_task_result_dataclass(self):
        from polisyos.foundry.methods.backends.ray_runner import RayTaskResult
        tr = RayTaskResult(
            method_fqn="a.b@1.0.0",
            output={"x": 1},
            wall_time_ms=42.0,
            worker_pid=12345,
        )
        assert tr.method_fqn == "a.b@1.0.0"
        assert tr.wall_time_ms == 42.0

    def test_chain_error_str(self):
        from polisyos.foundry.methods.backends.ray_chain_executor import RayChainExecutionError
        err = RayChainExecutionError(failures=[("a.b@1.0.0", ValueError("bad"))])
        s = str(err)
        assert "a.b@1.0.0" in s
        assert "1 node" in s


# ---------------------------------------------------------------------------
# Integration tests (only when Ray is installed and initialised)
# ---------------------------------------------------------------------------

@_ray_mark
class TestRayRunnerIntegration:
    @pytest.fixture(autouse=True)
    def ray_init(self):
        import ray
        if not ray.is_initialized():
            ray.init(num_cpus=2, ignore_reinit_error=True)
        yield
        # Do not shutdown after each test — keep the cluster running.

    def test_runner_is_available(self):
        from polisyos.foundry.methods.backends.ray_runner import RayMethodRunner
        runner = RayMethodRunner()
        assert runner.is_available()

    def test_run_simple_pure_step(self):
        """Basic end-to-end: submit pure_step, get result back."""
        import numpy as np
        from polisyos.foundry.methods.backends.ray_runner import (
            RayMethodRunner,
            RayTaskResult,
        )

        class SimpleSumMethod:
            class signature:
                fqn = "test.sum@1.0.0"

            @staticmethod
            def pure_step(state, params):
                x = state.get("x", 0)
                return {"result": x + params.get("bias", 0)}

        runner = RayMethodRunner(num_cpus=1)
        result = runner.run(SimpleSumMethod, state={"x": 10}, params={"bias": 5})

        assert isinstance(result, RayTaskResult)
        assert result.method_fqn == "test.sum@1.0.0"
        assert result.output["result"] == 15
        assert result.wall_time_ms >= 0.0

    def test_run_returns_worker_pid(self):
        """Worker PID should be set when Ray executes the task."""
        from polisyos.foundry.methods.backends.ray_runner import RayMethodRunner

        class PidMethod:
            class signature:
                fqn = "test.pid@1.0.0"

            @staticmethod
            def pure_step(state, params):
                return {"value": 42}

        runner = RayMethodRunner()
        result = runner.run(PidMethod, state={}, params={})
        assert result.worker_pid is not None
        assert isinstance(result.worker_pid, int)

    def test_run_raises_on_exception(self):
        """Remote task exceptions are wrapped in RuntimeError."""
        from polisyos.foundry.methods.backends.ray_runner import RayMethodRunner

        class FailingMethod:
            class signature:
                fqn = "test.fail@1.0.0"

            @staticmethod
            def pure_step(state, params):
                raise ValueError("Intentional remote failure")

        runner = RayMethodRunner()
        with pytest.raises(RuntimeError, match="failed"):
            runner.run(FailingMethod, state={}, params={})
