from __future__ import annotations

from typing import Any

from polisyos.foundry.methods.testing.suite import MethodTestSuite, TestResult


class JaxMethodTestSuite(MethodTestSuite):
    """Explicit JAX-focused suite alias for clarity in polyglot flows."""

    def run_jax_checks(self, sample_state: Any, sample_params: dict[str, Any]) -> TestResult:
        return self.run_all(sample_state, sample_params)

