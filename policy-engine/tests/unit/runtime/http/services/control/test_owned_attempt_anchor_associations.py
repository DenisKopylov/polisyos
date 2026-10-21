"""Exercise R5 resource evidence branches used by owned HTE resolution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.runtime import DirectMethodExecutionHTEResourceEvidence
from polisyos.runtime.http.services.control.owned_attempt_anchor import (
    _resource_evidence_payload_r5,
)

_METHOD = "causal.hte.causal_forest@2.0.0"
_PROFILE = "econml.causal_forest_dml.native_mean@2.0"
_JOBLIB_CONFIG_SHA = "e" * 64


class _ResourceReceipt(BaseModel):
    """Typed worker receipt shape consumed by owner resource recomputation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    scope: Literal["producer_scoped_joblib_parallelism_one"]
    execution_status: Literal["not_started", "returned", "raised"]
    estimator_before_class_fqn: str | None = None
    estimator_before_n_jobs: int | None = Field(default=None, strict=True)
    estimator_before_params_sha256: str | None = None
    estimator_after_class_fqn: str | None = None
    estimator_after_n_jobs: int | None = Field(default=None, strict=True)
    estimator_after_params_sha256: str | None = None
    joblib_started: bool = False
    joblib_finished: bool = False
    joblib_exit_status: Literal["not_started", "returned", "raised"] = "not_started"
    joblib_profile_id: str | None = None
    joblib_profile_revision: str | None = None
    joblib_implementation: str | None = None
    joblib_implementation_version: str | None = None
    joblib_scope: str | None = None
    joblib_max_jobs: int | None = Field(default=None, strict=True)
    joblib_entry_effective_jobs: int | None = Field(default=None, strict=True)
    joblib_entry_backend_fqn: str | None = None
    joblib_entry_config_sha256: str | None = None
    joblib_entry_implementation_version: str | None = None
    joblib_exit_effective_jobs: int | None = Field(default=None, strict=True)
    joblib_exit_backend_fqn: str | None = None
    joblib_exit_config_sha256: str | None = None
    joblib_exit_implementation_version: str | None = None


def _anchor(
    *,
    required_estimator_n_jobs: int | None = 1,
    max_jobs: int = 1,
) -> SimpleNamespace:
    """Create the exact owner policy identity needed by the resource recomputer."""
    policy_ref = ArtifactRef(
        artifact_id="sha256:" + "b" * 64,
        kind="runtime.observational_input_resource_policy",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "c" * 64,
    )
    return SimpleNamespace(
        resource_policy_revision="r5",
        resource_policy_schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        resource_policy_execution_scope="producer_scoped_joblib_parallelism_one",
        resource_policy_max_jobs=max_jobs,
        resource_policy_required_estimator_n_jobs=required_estimator_n_jobs,
        resource_policy_ref=policy_ref,
        resource_policy_digest="d" * 64,
        resource_policy_method_fqn=_METHOD,
        resource_policy_method_profile_id=_PROFILE,
    )


def _receipt(
    *,
    execution_status: Literal["not_started", "returned", "raised"] = "returned",
    include_estimator: bool = False,
    joblib_exit_status: Literal["not_started", "returned", "raised"] | None = None,
) -> _ResourceReceipt:
    """Return a bounded joblib observation with optional estimator witnesses."""
    estimator: dict[str, object] = {}
    if include_estimator:
        estimator = {
            "estimator_before_class_fqn": "econml.dml.CausalForestDML",
            "estimator_before_n_jobs": 1,
            "estimator_before_params_sha256": "f" * 64,
            "estimator_after_class_fqn": "econml.dml.CausalForestDML",
            "estimator_after_n_jobs": 1,
            "estimator_after_params_sha256": "f" * 64,
        }
    exit_status = joblib_exit_status or execution_status
    return _ResourceReceipt(
        scope="producer_scoped_joblib_parallelism_one",
        execution_status=execution_status,
        joblib_started=True,
        joblib_finished=True,
        joblib_exit_status=exit_status,
        joblib_profile_id="joblib.parallel_config.current_thread@1.0",
        joblib_profile_revision="1.0",
        joblib_implementation="joblib.parallel_config",
        joblib_implementation_version="1.4.2",
        joblib_scope="current_thread_joblib",
        joblib_max_jobs=1,
        joblib_entry_effective_jobs=1,
        joblib_entry_backend_fqn="loky",
        joblib_entry_config_sha256=_JOBLIB_CONFIG_SHA,
        joblib_entry_implementation_version="1.4.2",
        joblib_exit_effective_jobs=1,
        joblib_exit_backend_fqn="loky",
        joblib_exit_config_sha256=_JOBLIB_CONFIG_SHA,
        joblib_exit_implementation_version="1.4.2",
        **estimator,
    )


def test_r5_returned_refusal_retains_unknown_estimator_but_numeric_does_not() -> None:
    """A real joblib observation can accompany refusal without qualifying a point."""
    anchor = _anchor()
    receipt = _receipt(include_estimator=False)

    refusal = _resource_evidence_payload_r5(
        anchor=anchor,
        receipt=receipt,
        allow_estimator_not_established=True,
    )

    assert refusal is not None
    assert refusal["execution_status"] == "returned"
    assert refusal["estimator_observation_status"] == "not_established"
    assert refusal["joblib_observation_status"] == "recomputed"
    assert "schema_version" not in refusal
    DirectMethodExecutionHTEResourceEvidence.model_validate(refusal, strict=True)
    assert _resource_evidence_payload_r5(anchor=anchor, receipt=receipt) is None


def test_r5_numeric_resource_evidence_requires_estimator_and_joblib_observations() -> None:
    """A numeric result gets recomputed evidence only when both witnesses exist."""
    anchor = _anchor()
    valid = _resource_evidence_payload_r5(
        anchor=anchor,
        receipt=_receipt(include_estimator=True),
    )

    assert valid is not None
    assert valid["estimator_observation_status"] == "recomputed"
    assert valid["joblib_observation_status"] == "recomputed"
    DirectMethodExecutionHTEResourceEvidence.model_validate(valid, strict=True)


def test_r5_mismatched_raised_status_is_not_accepted_as_refusal_evidence() -> None:
    """A raised label without the matching joblib context exit is not evidence."""
    anchor = _anchor()
    mismatched_exit = _resource_evidence_payload_r5(
        anchor=anchor,
        receipt=_receipt(execution_status="raised", joblib_exit_status="returned"),
        allow_estimator_not_established=True,
    )
    assert mismatched_exit is None


def test_r5_refuses_boolean_values_that_serialize_as_integer_one() -> None:
    """Strict owner recomputation checks raw receipt attributes before JSON encoding."""
    anchor = _anchor()
    receipt = _receipt()
    for field_name in (
        "joblib_max_jobs",
        "joblib_entry_effective_jobs",
        "joblib_exit_effective_jobs",
    ):
        malformed = receipt.model_copy(update={field_name: True})
        assert (
            _resource_evidence_payload_r5(
                anchor=anchor,
                receipt=malformed,
                allow_estimator_not_established=True,
            )
            is None
        )

    assert (
        _resource_evidence_payload_r5(
            anchor=_anchor(max_jobs=True),
            receipt=receipt,
            allow_estimator_not_established=True,
        )
        is None
    )
