"""Public entrypoints for Scientist workflows."""

from __future__ import annotations

import warnings
from typing import Any, Mapping

from polisyos.scientist.orchestrator.workflow import build_workflow

__all__ = ["build_workflow", "run_experiment", "deprecated_import"]


def deprecated_import(message: str) -> None:
    """Emit a uniform DeprecationWarning for legacy Scientist APIs."""
    warnings.warn(message, DeprecationWarning, stacklevel=2)


def run_experiment(state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """
    Official entrypoint to execute the Scientist workflow.

    Parameters
    ----------
    state:
        Initial experiment state (keys match ExperimentState). If None, starts from
        an empty state.

    Returns
    -------
    dict[str, Any]
        Final ExperimentState produced by the workflow.
    """
    workflow = build_workflow()
    return workflow.invoke(dict(state or {}))
