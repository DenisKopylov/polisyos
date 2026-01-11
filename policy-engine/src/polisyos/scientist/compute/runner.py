from __future__ import annotations

from polisyos.scientist.compute.job_spec import JobResult, JobSpec, JobKey


def run_job(spec: JobSpec) -> JobResult:
    """
    Placeholder compute runner. In future will call Foundry kernel.
    """
    job_key = JobKey.from_spec(spec)
    return JobResult(job_key=job_key, state_delta_ref=None, metrics_ref=None, warnings=["stub runner"])
