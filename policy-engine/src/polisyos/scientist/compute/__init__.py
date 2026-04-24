"""Scientist compute surface for advanced-method bundles and job execution contracts."""

from .advanced_methods import (
    C7AdvancedInputs,
    C7AdvancedSuiteResult,
    C7PersistedArtifact,
    run_c7_advanced_suite,
)
from .job_spec import JobKey, JobResult, JobSpec
from .runner import MethodBackend, run_job
