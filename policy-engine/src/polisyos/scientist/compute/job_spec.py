"""Public compute job spec module API."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import content_hash
from polisyos.ir.analytics import PosteriorPointRole, PosteriorSummaryRef


class JobSpec(BaseModel):
    """Describe a legacy-program or method-based compute job.

    The specification carries the job kind, seed, execution mode, requested metrics,
    optional program and execution-plan references, state snapshot, and method inputs.
    A non-null ``method_fqn`` also classifies the job as method-based. For legacy jobs,
    ``JobKey.from_spec`` omits the method identity, parameters, inputs, and explicit
    job kind when deriving the content key.

    Attributes:
        job_kind: Declared job kind, either ``legacy_program`` or ``method``.
        program_ref: Optional artifact reference for the legacy program.
        exec_plan_ref: Optional artifact reference for the execution plan.
        state_snapshot_ref: Optional artifact reference for the initial state snapshot.
        seed: Seed carried with the job specification.
        mode: Execution mode label.
        required_metrics: Metric identifiers requested for the job.
        notes: Notes carried with the specification.
        method_fqn: Optional fully qualified method name.
        method_version: Optional version of the selected method.
        method_params: Parameters supplied to the selected method.
        input_refs: Named artifact references supplied as method inputs.
    """

    model_config = ConfigDict(extra="forbid")

    job_kind: str = "legacy_program"
    program_ref: ArtifactRef | None = None
    exec_plan_ref: ArtifactRef | None = None
    state_snapshot_ref: ArtifactRef | None = None
    seed: int = 0
    mode: str = "dev"
    required_metrics: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    method_fqn: str | None = None
    method_version: str | None = None
    method_params: dict[str, Any] = Field(default_factory=dict)
    input_refs: dict[str, ArtifactRef] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_job_kind(self) -> JobSpec:
        if self.job_kind not in {"legacy_program", "method"}:
            raise ValueError("job_kind must be either 'legacy_program' or 'method'")
        return self

    @property
    def is_legacy_jax(self) -> bool:
        return not self.is_method_job

    @property
    def is_method_job(self) -> bool:
        return self.job_kind == "method" or self.method_fqn is not None


class JobKey(BaseModel):
    """Job key public type."""

    model_config = ConfigDict(extra="forbid")

    value: str

    @staticmethod
    def from_spec(spec: JobSpec) -> JobKey:
        payload_obj = spec.model_dump(mode="json", exclude_none=True)
        if spec.is_legacy_jax:
            payload_obj.pop("job_kind", None)
            for key in ("method_fqn", "method_version", "method_params", "input_refs"):
                payload_obj.pop(key, None)
        payload = json.dumps(payload_obj, sort_keys=True)
        digest = content_hash(payload)
        return JobKey(value=f"job:{digest}")


class MethodExecutionCaptureProvenance(BaseModel):
    """Report availability of selected method-capture refs on a legacy result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    availability: Literal["available", "partial", "unavailable"]
    method_execution_bundle_ref: ArtifactRef | None = None
    method_metric_binding_set_ref: ArtifactRef | None = None
    limitations: tuple[
        Literal[
            "method_execution_bundle_role_absent",
            "method_metric_binding_set_role_absent",
            "simulation_results_lineage_not_verified",
            "simulation_results_profile_unselected",
            "simulation_results_ref_absent",
        ],
        ...,
    ] = ()

    @model_validator(mode="after")
    def _validate_capture_availability(self) -> MethodExecutionCaptureProvenance:
        refs_present = sum(
            ref is not None
            for ref in (
                self.method_execution_bundle_ref,
                self.method_metric_binding_set_ref,
            )
        )
        expected = (
            "available" if refs_present == 2 else "partial" if refs_present == 1 else "unavailable"
        )
        if self.availability != expected:
            raise ValueError("capture availability must match the number of selected refs")
        if self.availability == "available" and self.limitations:
            raise ValueError("available capture provenance cannot carry availability limitations")
        if self.availability != "available" and not self.limitations:
            raise ValueError("incomplete capture provenance must explain its limitation")
        return self


class JobResult(BaseModel):
    """Bind a compute job key to output references and execution diagnostics.

    The result can reference state, metrics, environment, simulation, and method
    outputs, and can carry posterior summaries, a final state, issues, and warnings.
    ``method_execution_capture`` reports whether its capture references are present
    and requires limitations when that capture is partial or unavailable; it does not
    resolve or verify the referenced artifacts. The field is omitted from serialized
    output when absent. This model has no success status, so its presence alone does
    not establish that execution succeeded.

    Attributes:
        job_key: Content-derived key identifying the compute job.
        state_delta_ref: Optional reference to the persisted state delta.
        metrics_ref: Optional reference to persisted job metrics.
        environment_ref: Optional reference to the recorded environment.
        environment_fingerprint: Optional environment fingerprint string.
        state_snapshot_ref: Optional reference to the persisted state snapshot.
        simulation_results_ref: Optional reference to simulation results.
        method_result_ref: Optional reference to the method result artifact.
        method_evidence_ref: Optional reference to method evidence.
        method_execution_capture: Availability and limitations reported for method
            execution-capture references, when present.
        posterior_summary_refs: Posterior summaries keyed by point role.
        final_state: Optional final state value.
        issues: Structured issue records associated with the result.
        warnings: Warning messages associated with the result.
    """

    model_config = ConfigDict(extra="forbid")

    job_key: JobKey
    state_delta_ref: ArtifactRef | None = None
    metrics_ref: ArtifactRef | None = None
    environment_ref: ArtifactRef | None = None
    environment_fingerprint: str | None = None
    state_snapshot_ref: ArtifactRef | None = None
    simulation_results_ref: ArtifactRef | None = None
    method_result_ref: ArtifactRef | None = None
    method_evidence_ref: ArtifactRef | None = None
    method_execution_capture: MethodExecutionCaptureProvenance | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    posterior_summary_refs: dict[PosteriorPointRole, PosteriorSummaryRef] = Field(
        default_factory=dict
    )
    final_state: Any | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
