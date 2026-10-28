"""Scientist compute surface for job execution contracts."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from .job_spec import JobKey, JobResult, JobSpec, MethodExecutionCaptureProvenance
from .runner import MethodBackend, read_job_result_method_execution_capture, run_job

if TYPE_CHECKING:
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        MAX_METHOD_METRIC_SOURCE_BYTES,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _BoundedExecutionSourceReader as BoundedMethodMetricSourceReader,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _ProjectionReadBudget as MethodMetricSourceReadBudget,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _read_bounded_method_metric_artifact as read_bounded_method_metric_artifact,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _selected_ref as selected_method_metric_ref,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _VerifiedRestrictedExAnteCall as VerifiedRestrictedExAnteCall,
    )

__all__ = [
    "C7AdvancedInputs",
    "C7AdvancedSuiteResult",
    "C7PersistedArtifact",
    "BoundedMethodMetricSourceReader",
    "MAX_METHOD_METRIC_SOURCE_BYTES",
    "MethodMetricSourceReadBudget",
    "VerifiedRestrictedExAnteCall",
    "read_bounded_method_metric_artifact",
    "selected_method_metric_ref",
    "JobKey",
    "JobResult",
    "JobSpec",
    "MethodExecutionCaptureProvenance",
    "MethodBackend",
    "read_job_result_method_execution_capture",
    "run_c7_advanced_suite",
    "run_job",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "C7AdvancedInputs": ("polisyos.scientist.methods.advanced", "C7AdvancedInputs"),
    "C7AdvancedSuiteResult": ("polisyos.scientist.methods.advanced", "C7AdvancedSuiteResult"),
    "C7PersistedArtifact": ("polisyos.scientist.methods.advanced", "C7PersistedArtifact"),
    "run_c7_advanced_suite": ("polisyos.scientist.methods.advanced", "run_c7_advanced_suite"),
    "BoundedMethodMetricSourceReader": (
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics",
        "_BoundedExecutionSourceReader",
    ),
    "MAX_METHOD_METRIC_SOURCE_BYTES": (
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics",
        "MAX_METHOD_METRIC_SOURCE_BYTES",
    ),
    "MethodMetricSourceReadBudget": (
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics",
        "_ProjectionReadBudget",
    ),
    "VerifiedRestrictedExAnteCall": (
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics",
        "_VerifiedRestrictedExAnteCall",
    ),
    "read_bounded_method_metric_artifact": (
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics",
        "_read_bounded_method_metric_artifact",
    ),
    "selected_method_metric_ref": (
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics",
        "_selected_ref",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.compute' has no attribute {name!r}")
    module_name, attribute_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
