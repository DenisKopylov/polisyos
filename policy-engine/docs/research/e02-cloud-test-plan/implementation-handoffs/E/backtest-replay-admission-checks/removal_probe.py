"""Run process-local BKT property removal without modifying tracked source."""

from __future__ import annotations

import argparse
import ast
import inspect
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    from polisyos.ir.analytics.backtest import BacktestReport


class _RemoveGuard(ast.NodeTransformer):
    def __init__(self, variable: str) -> None:
        self.variable = variable
        self.removed = 0

    def visit_If(self, node: ast.If) -> ast.If | None:
        test = node.test
        if isinstance(test, ast.Compare):
            left = test.left
            matches = (
                isinstance(left, ast.Attribute)
                and isinstance(left.value, ast.Name)
                and left.value.id == "arr"
                and left.attr == "ndim"
                if self.variable == "shape"
                else isinstance(left, ast.Name) and left.id == "step_size"
            )
            if matches:
                self.removed += 1
                return None
        return self.generic_visit(node)


def _remove_guard(module: ModuleType, function_name: str, variable: str) -> None:
    function = getattr(module, function_name)
    tree = ast.parse(inspect.getsource(function))
    transformer = _RemoveGuard(variable)
    tree = transformer.visit(tree)
    if transformer.removed != 1:
        raise AssertionError(f"expected one actual guard, found {transformer.removed}")
    ast.fix_missing_locations(tree)
    # Execute only the tracked owner function after deleting its one numeric guard.
    exec(compile(tree, inspect.getsourcefile(function) or "<probe>", "exec"), module.__dict__)  # noqa: S102


class _Removal:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        if self.mode == "trust":
            from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer

            TrustScorer.compute = lambda self, **kwargs: (1.0, "A")
        elif self.mode == "replay":
            from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator

            original = BacktestOrchestrator._expand_replay_plans
            BacktestOrchestrator._expand_replay_plans = staticmethod(
                lambda plan: original(plan)[:1]
            )
        elif self.mode == "requested":
            from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator

            original = BacktestOrchestrator._aggregate

            def observed_only(self: BacktestOrchestrator, **kwargs: object) -> BacktestReport:
                kwargs["plans"] = []
                return original(self, **kwargs)

            BacktestOrchestrator._aggregate = observed_only
        elif self.mode == "cas":
            import polisyos.scientist.methods.backtesting.orchestrator as owner

            original = owner.BacktestOrchestrator._predict_with_scientist

            def discard_configured_store(
                self: owner.BacktestOrchestrator, *args: object, **kwargs: object
            ) -> object:
                configured_execution = owner.run_experiment

                def execution_without_configured_store(
                    state: object, **execution_kwargs: object
                ) -> object:
                    execution_kwargs["store"] = None
                    return configured_execution(state, **execution_kwargs)

                owner.run_experiment = execution_without_configured_store
                try:
                    return original(self, *args, **kwargs)
                finally:
                    owner.run_experiment = configured_execution

            owner.BacktestOrchestrator._predict_with_scientist = discard_configured_store
        elif self.mode == "bootstrap":
            import polisyos.scientist.methods.backtesting.bootstrap as owner

            _remove_guard(owner, "bootstrap_metric", "shape")
        elif self.mode == "cv":
            import polisyos.scientist.methods.backtesting.cv as owner

            _remove_guard(owner, "forward_chaining_splits", "step_size")


def main(argv: Sequence[str] | None = None) -> int:
    """Run named runtime removal against explicitly supplied pytest selectors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", required=True, choices=["trust", "replay", "requested", "cas", "bootstrap", "cv"]
    )
    parsed, pytest_args = parser.parse_known_args(argv)
    sys.stdout.write(f"PROPERTY REMOVAL: {parsed.mode}; source files and result markers retained\n")
    sys.stdout.flush()
    return int(pytest.main(pytest_args, plugins=[_Removal(parsed.mode)]))


if __name__ == "__main__":
    raise SystemExit(main())
