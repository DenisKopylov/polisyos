"""Scientist compute surface for job execution contracts."""

from __future__ import annotations

import importlib
from typing import Any

from .job_spec import JobKey, JobResult, JobSpec
from .runner import MethodBackend, run_job

__all__ = [
    "C7AdvancedInputs",
    "C7AdvancedSuiteResult",
    "C7PersistedArtifact",
    "JobKey",
    "JobResult",
    "JobSpec",
    "MethodBackend",
    "run_c7_advanced_suite",
    "run_job",
]

_ADVANCED_EXPORTS = {
    "C7AdvancedInputs",
    "C7AdvancedSuiteResult",
    "C7PersistedArtifact",
    "run_c7_advanced_suite",
}


def __getattr__(name: str) -> Any:
    if name not in _ADVANCED_EXPORTS:
        raise AttributeError(f"module 'polisyos.scientist.compute' has no attribute {name!r}")
    module = importlib.import_module("polisyos.scientist.methods.advanced")
    value = getattr(module, name)
    globals()[name] = value
    return value
