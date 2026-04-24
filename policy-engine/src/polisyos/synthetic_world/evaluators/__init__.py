"""Evaluation helpers for synthetic-world benchmarks."""

from .benchmark_hooks import build_hook_diagnostics
from .metrics import evaluate_prediction
from .plots import build_plot_specs

__all__ = ["build_hook_diagnostics", "build_plot_specs", "evaluate_prediction"]
