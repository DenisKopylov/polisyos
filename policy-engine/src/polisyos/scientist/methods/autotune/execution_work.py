"""Typed, diagnostic-only work packets for source-bound causal MethodJobs."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.foundry.methods.catalog.causal.ci_backends import BootstrapExecutionWork

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore


class MethodInputValueFingerprint(BaseModel):
    """Canonical shape and content identity for one dispatched method input slot."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    dtype: str = Field(min_length=1, max_length=32)
    shape: list[int] = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class MethodDispatchBinding(BaseModel):
    """Producer-recorded method request and input state observed at dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.1"] = "1.1"
    method_fqn: str = Field(min_length=1, max_length=256)
    method_version: str | None = Field(default=None, max_length=64)
    method_seed: int = Field(strict=True)
    method_params_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_refs: dict[str, ArtifactRef]
    input_schemas: dict[str, SchemaInfo | None]
    input_state_fingerprints: dict[str, MethodInputValueFingerprint]

    @model_validator(mode="after")
    def _validate_dispatch_inputs(self) -> MethodDispatchBinding:
        if (
            not self.input_refs
            or set(self.input_refs) != set(self.input_schemas)
            or not self.input_state_fingerprints
        ):
            raise ValueError("dispatch binding requires matched refs, schemas, and slots")
        return self


def fingerprint_method_input_value(value: Any) -> MethodInputValueFingerprint:
    """Fingerprint a numeric or fixed-width array using canonical shape and bytes."""
    array = np.asarray(value)
    if array.ndim == 0 or array.dtype.hasobject:
        raise ValueError("method input must be a non-scalar, non-object array")
    canonical_dtype = array.dtype.newbyteorder("<")
    canonical_array = np.ascontiguousarray(array.astype(canonical_dtype, copy=False))
    return MethodInputValueFingerprint(
        dtype=canonical_dtype.str,
        shape=[int(dimension) for dimension in canonical_array.shape],
        sha256=hashlib.sha256(canonical_array.tobytes(order="C")).hexdigest(),
    )


class MethodJobExecutionWorkPacket(BaseModel):
    """Diagnostic-only, source-bound observation of one native MethodJob's measured work."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.2"] = "1.2"
    authority_purpose: Literal["engineering_execution_observation"] = (
        "engineering_execution_observation"
    )
    candidate_status: Literal["diagnostic_only"] = "diagnostic_only"
    run_id: str = Field(min_length=1, max_length=256)
    evaluation_id: str = Field(min_length=1, max_length=256)
    evaluation_attempt_id: str = Field(min_length=1, max_length=256)
    candidate_ref: ArtifactRef
    benchmark_suite_ref: ArtifactRef
    data_snapshot_ref: ArtifactRef
    data_ref: ArtifactRef
    method_result_ref: ArtifactRef
    method_evidence_ref: ArtifactRef
    method_job_key: str = Field(min_length=1, max_length=256)
    method_fqn: str = Field(min_length=1, max_length=256)
    method_version: str | None = Field(default=None, max_length=64)
    method_seed: int = Field(strict=True)
    configured_method_params: dict[str, Any]
    effective_method_config: dict[str, Any]
    candidate_slot_bindings: dict[str, str] = Field(default_factory=dict)
    data_slot_bindings: dict[str, str]
    method_profile_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_sample_count: int = Field(strict=True, ge=1)
    bootstrap_execution: BootstrapExecutionWork

    @model_validator(mode="after")
    def _validate_work_binding(self) -> MethodJobExecutionWorkPacket:
        if self.data_snapshot_ref.kind != "fabric.data_snapshot":
            raise ValueError("data_snapshot_ref must identify a Fabric DataSnapshot")
        if not self.candidate_slot_bindings and not self.data_slot_bindings:
            raise ValueError("work packet requires source slot bindings")
        if set(self.candidate_slot_bindings) & set(self.data_slot_bindings):
            raise ValueError("candidate and DataSnapshot slot bindings must not overlap")
        if self.configured_method_params.get("capture_execution_work") is not True:
            raise ValueError("work capture must be explicitly enabled for the MethodJob")
        effective_draws = self.effective_method_config.get("bootstrap_draws")
        if (
            isinstance(effective_draws, bool)
            or not isinstance(effective_draws, int)
            or effective_draws != self.bootstrap_execution.requested_draw_count
        ):
            raise ValueError("measured requested draws must match effective method config")
        return self


def persist_method_job_execution_work_packet(
    store: ArtifactStore,
    packet: MethodJobExecutionWorkPacket,
) -> ArtifactRef:
    """Persist measured native MethodJob work with all source and result lineage."""
    inputs = [
        ("candidate", packet.candidate_ref),
        ("benchmark_suite", packet.benchmark_suite_ref),
        ("data_snapshot", packet.data_snapshot_ref),
        ("data", packet.data_ref),
        ("method_result", packet.method_result_ref),
        ("method_evidence", packet.method_evidence_ref),
    ]
    return store.put_json(
        packet,
        ArtifactWriteOptions(
            kind="scientist.autotune.method_execution_work_packet",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.MethodJobExecutionWorkPacket",
                version=packet.schema_version,
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.method_job_work_observer",
                version="1.2",
            ),
            inputs=[input_ref_from_artifact_ref(ref, role=role) for role, ref in inputs],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = [
    "MethodDispatchBinding",
    "MethodInputValueFingerprint",
    "MethodJobExecutionWorkPacket",
    "fingerprint_method_input_value",
    "persist_method_job_execution_work_packet",
]
